from __future__ import annotations

import json
import secrets
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .board import _board_response, _owned_card, _owned_column, _reorder_column, _set_positions
from .database import connect
from .openrouter import OpenRouterClient, OpenRouterError


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class CreateCardOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["create_card"]
    column_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=80)
    details: str = Field(default="", max_length=240)


class EditCardOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["edit_card"]
    card_id: str = Field(min_length=1, max_length=80)
    title: str | None = Field(default=None, max_length=80)
    details: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def has_editable_field(self) -> "EditCardOperation":
        if self.title is None and self.details is None:
            raise ValueError("edit_card requires title or details")
        return self


class MoveCardOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["move_card"]
    card_id: str = Field(min_length=1, max_length=80)
    column_id: str = Field(min_length=1, max_length=80)
    position: int | None = Field(default=None, ge=0)


class DeleteCardOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["delete_card"]
    card_id: str = Field(min_length=1, max_length=80)


class RenameColumnOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["rename_column"]
    column_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=28)


Operation = Annotated[
    CreateCardOperation
    | EditCardOperation
    | MoveCardOperation
    | DeleteCardOperation
    | RenameColumnOperation,
    Field(discriminator="op"),
]


class AIResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str = Field(min_length=1, max_length=4000)
    operations: list[Operation] = Field(default_factory=list, max_length=20)


class AIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)
    history: list[ConversationMessage] = Field(default_factory=list, max_length=20)


class AIValidationError(Exception):
    pass


def _clean(value: str, field: str) -> str:
    value = value.strip()
    if not value:
        raise AIValidationError(f"{field} cannot be empty")
    return value


def _simulation_state(board: dict[str, Any]) -> tuple[set[str], dict[str, list[str]]]:
    columns = {column["id"]: [card["id"] for card in column["cards"]] for column in board["columns"]}
    return set(columns), columns


def _validate_operations(connection: sqlite3.Connection, user_id: str, operations: list[Operation]) -> None:
    board = _board_response(connection, user_id)
    column_ids, cards_by_column = _simulation_state(board)
    card_locations = {card_id: column_id for column_id, card_ids in cards_by_column.items() for card_id in card_ids}
    touched_cards: set[str] = set()
    touched_columns: set[str] = set()

    for operation in operations:
        if isinstance(operation, CreateCardOperation):
            if operation.column_id not in column_ids:
                raise AIValidationError("Operation references an unknown column")
            _clean(operation.title, "Card title")
            continue

        if isinstance(operation, RenameColumnOperation):
            if operation.column_id not in column_ids:
                raise AIValidationError("Operation references an unknown column")
            if operation.column_id in touched_columns:
                raise AIValidationError("Conflicting operations target the same column")
            _clean(operation.name, "Column name")
            touched_columns.add(operation.column_id)
            continue

        if operation.card_id not in card_locations or operation.card_id in touched_cards:
            raise AIValidationError("Operation references an unknown or conflicting card")
        touched_cards.add(operation.card_id)

        if isinstance(operation, EditCardOperation):
            if operation.title is not None:
                _clean(operation.title, "Card title")
            continue

        if isinstance(operation, DeleteCardOperation):
            source = card_locations.pop(operation.card_id)
            cards_by_column[source].remove(operation.card_id)
            continue

        if isinstance(operation, MoveCardOperation):
            if operation.column_id not in column_ids:
                raise AIValidationError("Operation references an unknown column")
            source = card_locations[operation.card_id]
            cards_by_column[source].remove(operation.card_id)
            destination_cards = cards_by_column[operation.column_id]
            position = len(destination_cards) if operation.position is None else operation.position
            if position > len(destination_cards):
                raise AIValidationError("Operation position is outside the destination column")
            destination_cards.insert(position, operation.card_id)
            card_locations[operation.card_id] = operation.column_id


def _move_card(
    connection: sqlite3.Connection,
    user_id: str,
    card_id: str,
    column_id: str,
    position: int | None,
) -> None:
    card = _owned_card(connection, user_id, card_id)
    _owned_column(connection, user_id, column_id)
    source_id = card["column_id"]
    source_rows = connection.execute(
        "SELECT id FROM cards WHERE column_id = ? ORDER BY position", (source_id,)
    ).fetchall()
    source_ids = [row["id"] for row in source_rows if row["id"] != card_id]
    destination_rows = connection.execute(
        "SELECT id FROM cards WHERE column_id = ? ORDER BY position", (column_id,)
    ).fetchall()
    destination_ids = [row["id"] for row in destination_rows if row["id"] != card_id]
    target = len(destination_ids) if position is None else position
    if target > len(destination_ids):
        raise AIValidationError("Operation position is outside the destination column")
    destination_ids.insert(target, card_id)

    if source_id == column_id:
        _reorder_column(connection, column_id, destination_ids)
        return
    affected_ids = [row["id"] for row in source_rows] + [row["id"] for row in destination_rows]
    for affected_id in affected_ids:
        connection.execute("UPDATE cards SET position = position + 1000000 WHERE id = ?", (affected_id,))
    connection.execute("UPDATE cards SET position = 1000000000, column_id = ? WHERE id = ?", (column_id, card_id))
    _set_positions(connection, source_ids)
    _set_positions(connection, destination_ids)


def _apply_operations(
    connection: sqlite3.Connection,
    user_id: str,
    operations: list[Operation],
) -> None:
    for operation in operations:
        if isinstance(operation, CreateCardOperation):
            column = _owned_column(connection, user_id, operation.column_id)
            title = _clean(operation.title, "Card title")
            position = connection.execute(
                "SELECT COALESCE(MAX(position) + 1, 0) FROM cards WHERE column_id = ?",
                (column["id"],),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO cards (id, column_id, title, details, position) VALUES (?, ?, ?, ?, ?)",
                (secrets.token_hex(16), column["id"], title, operation.details.strip(), position),
            )
        elif isinstance(operation, EditCardOperation):
            _owned_card(connection, user_id, operation.card_id)
            values: dict[str, str] = {}
            if operation.title is not None:
                values["title"] = _clean(operation.title, "Card title")
            if operation.details is not None:
                values["details"] = operation.details.strip()
            assignments = ", ".join(f"{field} = ?" for field in values)
            connection.execute(
                f"UPDATE cards SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (*values.values(), operation.card_id),
            )
        elif isinstance(operation, MoveCardOperation):
            _move_card(connection, user_id, operation.card_id, operation.column_id, operation.position)
        elif isinstance(operation, DeleteCardOperation):
            card = _owned_card(connection, user_id, operation.card_id)
            column_id = card["column_id"]
            connection.execute("DELETE FROM cards WHERE id = ?", (operation.card_id,))
            remaining = connection.execute(
                "SELECT id FROM cards WHERE column_id = ? ORDER BY position", (column_id,)
            ).fetchall()
            _reorder_column(connection, column_id, [row["id"] for row in remaining])
        elif isinstance(operation, RenameColumnOperation):
            _owned_column(connection, user_id, operation.column_id)
            connection.execute(
                "UPDATE columns SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (_clean(operation.name, "Column name"), operation.column_id),
            )


def _prompt(board: dict[str, Any], request: AIRequest) -> list[dict[str, str]]:
    schema = json.dumps(AIResponse.model_json_schema(), separators=(",", ":"))
    system = (
        "You are a project board assistant. Return only JSON matching this schema: "
        f"{schema}. Operations must use IDs from the current board. "
        "Do not invent IDs or add operations outside the schema."
    )
    messages = [{"role": "system", "content": system}]
    messages.extend(message.model_dump() for message in request.history)
    messages.append(
        {
            "role": "user",
            "content": f"Current board JSON:\n{json.dumps(board)}\n\nUser request:\n{request.question}",
        }
    )
    return messages


def register_ai_routes(
    app: FastAPI,
    database_path: Path,
    require_user: Callable[..., dict[str, str]],
    client: OpenRouterClient,
) -> None:
    @app.post("/api/ai/board", tags=["ai"])
    def board_assistant(
        request: AIRequest,
        user: dict[str, str] = Depends(require_user),
    ) -> dict[str, Any]:
        try:
            with connect(database_path) as connection:
                board = _board_response(connection, user["id"])
                raw_response = client.complete_json(_prompt(board, request))
                parsed_response = AIResponse.model_validate(raw_response)
                _validate_operations(connection, user["id"], parsed_response.operations)
                _apply_operations(connection, user["id"], parsed_response.operations)
                updated_board = _board_response(connection, user["id"])
        except ValidationError as error:
            raise HTTPException(status_code=502, detail="AI response did not match the required contract") from error
        except AIValidationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except OpenRouterError as error:
            raise HTTPException(status_code=error.http_status, detail=str(error)) from error
        return {"response": parsed_response.response, "board": updated_board}
