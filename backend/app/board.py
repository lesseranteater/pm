from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .database import connect


class RenameColumnRequest(BaseModel):
    name: str = Field(min_length=1, max_length=28)


class CreateCardRequest(BaseModel):
    column_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=80)
    details: str = Field(default="", max_length=240)


class UpdateCardRequest(BaseModel):
    title: str | None = Field(default=None, max_length=80)
    details: str | None = Field(default=None, max_length=240)


class MoveCardRequest(BaseModel):
    column_id: str = Field(min_length=1, max_length=80)
    position: int | None = Field(default=None, ge=0)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _validation_error(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


def _board_response(connection: sqlite3.Connection, user_id: str) -> dict[str, Any]:
    board = connection.execute(
        "SELECT id, name FROM boards WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not board:
        raise _not_found("Board not found")

    columns = connection.execute(
        """
        SELECT id, name, position
        FROM columns
        WHERE board_id = ?
        ORDER BY position
        """,
        (board["id"],),
    ).fetchall()
    cards = connection.execute(
        """
        SELECT id, column_id, title, details, position
        FROM cards
        WHERE column_id IN (SELECT id FROM columns WHERE board_id = ?)
        ORDER BY column_id, position
        """,
        (board["id"],),
    ).fetchall()
    cards_by_column: dict[str, list[dict[str, Any]]] = {column["id"]: [] for column in columns}
    for card in cards:
        cards_by_column[card["column_id"]].append(
            {
                "id": card["id"],
                "title": card["title"],
                "details": card["details"],
                "position": card["position"],
            }
        )

    return {
        "id": board["id"],
        "name": board["name"],
        "columns": [
            {
                "id": column["id"],
                "name": column["name"],
                "position": column["position"],
                "cards": cards_by_column[column["id"]],
            }
            for column in columns
        ],
    }


def _owned_column(
    connection: sqlite3.Connection, user_id: str, column_id: str
) -> sqlite3.Row:
    column = connection.execute(
        """
        SELECT columns.id, columns.board_id
        FROM columns
        JOIN boards ON boards.id = columns.board_id
        WHERE columns.id = ? AND boards.user_id = ?
        """,
        (column_id, user_id),
    ).fetchone()
    if not column:
        raise _not_found("Column not found")
    return column


def _owned_card(connection: sqlite3.Connection, user_id: str, card_id: str) -> sqlite3.Row:
    card = connection.execute(
        """
        SELECT cards.id, cards.column_id, cards.title, cards.details, cards.position,
               columns.board_id
        FROM cards
        JOIN columns ON columns.id = cards.column_id
        JOIN boards ON boards.id = columns.board_id
        WHERE cards.id = ? AND boards.user_id = ?
        """,
        (card_id, user_id),
    ).fetchone()
    if not card:
        raise _not_found("Card not found")
    return card


def _reorder_column(connection: sqlite3.Connection, column_id: str, card_ids: list[str]) -> None:
    for card_id in card_ids:
        connection.execute(
            "UPDATE cards SET position = position + 1000000 WHERE id = ?",
            (card_id,),
        )
    for position, card_id in enumerate(card_ids):
        connection.execute(
            "UPDATE cards SET position = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (position, card_id),
        )


def _set_positions(connection: sqlite3.Connection, card_ids: list[str]) -> None:
    for position, card_id in enumerate(card_ids):
        connection.execute(
            "UPDATE cards SET position = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (position, card_id),
        )


def register_board_routes(
    app: FastAPI,
    database_path: Path,
    require_user: Callable[..., dict[str, str]],
) -> None:
    @app.get("/api/board", tags=["board"])
    async def get_board(user: dict[str, str] = Depends(require_user)) -> dict[str, Any]:
        with connect(database_path) as connection:
            return _board_response(connection, user["id"])

    @app.patch("/api/board/columns/{column_id}", tags=["board"])
    async def rename_column(
        column_id: str,
        payload: RenameColumnRequest,
        user: dict[str, str] = Depends(require_user),
    ) -> dict[str, Any]:
        name = payload.name.strip()
        if not name:
            raise _validation_error("Column name cannot be empty")
        with connect(database_path) as connection:
            _owned_column(connection, user["id"], column_id)
            connection.execute(
                "UPDATE columns SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (name, column_id),
            )
            return _board_response(connection, user["id"])

    @app.post("/api/board/cards", tags=["board"])
    async def create_card(
        payload: CreateCardRequest,
        user: dict[str, str] = Depends(require_user),
    ) -> dict[str, Any]:
        title = payload.title.strip()
        if not title:
            raise _validation_error("Card title cannot be empty")
        with connect(database_path) as connection:
            _owned_column(connection, user["id"], payload.column_id)
            position = connection.execute(
                "SELECT COALESCE(MAX(position) + 1, 0) FROM cards WHERE column_id = ?",
                (payload.column_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO cards (id, column_id, title, details, position)
                VALUES (lower(hex(randomblob(16))), ?, ?, ?, ?)
                """,
                (payload.column_id, title, payload.details.strip(), position),
            )
            return _board_response(connection, user["id"])

    @app.patch("/api/board/cards/{card_id}", tags=["board"])
    async def update_card(
        card_id: str,
        payload: UpdateCardRequest,
        user: dict[str, str] = Depends(require_user),
    ) -> dict[str, Any]:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise _validation_error("At least one card field is required")
        with connect(database_path) as connection:
            _owned_card(connection, user["id"], card_id)
            values: dict[str, str] = {}
            if "title" in updates:
                title = (updates["title"] or "").strip()
                if not title:
                    raise _validation_error("Card title cannot be empty")
                values["title"] = title
            if "details" in updates:
                values["details"] = (updates["details"] or "").strip()
            assignments = ", ".join(f"{field} = ?" for field in values)
            connection.execute(
                f"UPDATE cards SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (*values.values(), card_id),
            )
            return _board_response(connection, user["id"])

    @app.delete("/api/board/cards/{card_id}", tags=["board"])
    async def delete_card(
        card_id: str,
        user: dict[str, str] = Depends(require_user),
    ) -> dict[str, Any]:
        with connect(database_path) as connection:
            card = _owned_card(connection, user["id"], card_id)
            column_id = card["column_id"]
            connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
            remaining = connection.execute(
                "SELECT id FROM cards WHERE column_id = ? ORDER BY position",
                (column_id,),
            ).fetchall()
            _reorder_column(connection, column_id, [row["id"] for row in remaining])
            return _board_response(connection, user["id"])

    @app.post("/api/board/cards/{card_id}/move", tags=["board"])
    async def move_card(
        card_id: str,
        payload: MoveCardRequest,
        user: dict[str, str] = Depends(require_user),
    ) -> dict[str, Any]:
        with connect(database_path) as connection:
            card = _owned_card(connection, user["id"], card_id)
            destination = _owned_column(connection, user["id"], payload.column_id)
            source_id = card["column_id"]
            destination_id = destination["id"]
            if source_id == destination_id and payload.position is None:
                return _board_response(connection, user["id"])

            source_rows = connection.execute(
                "SELECT id FROM cards WHERE column_id = ? ORDER BY position",
                (source_id,),
            ).fetchall()
            source_ids = [row["id"] for row in source_rows if row["id"] != card_id]
            if source_id == destination_id:
                destination_ids = source_ids
            else:
                destination_rows = connection.execute(
                    "SELECT id FROM cards WHERE column_id = ? ORDER BY position",
                    (destination_id,),
                ).fetchall()
                destination_ids = [row["id"] for row in destination_rows]

            target_position = payload.position
            if target_position is None:
                target_position = len(destination_ids)
            if target_position > len(destination_ids):
                raise _validation_error("Card position is outside the destination column")
            destination_ids.insert(target_position, card_id)

            if source_id != destination_id:
                all_affected_ids = [
                    row["id"]
                    for row in source_rows
                ] + [
                    row["id"]
                    for row in connection.execute(
                        "SELECT id FROM cards WHERE column_id = ? ORDER BY position",
                        (destination_id,),
                    ).fetchall()
                ]
                for affected_id in all_affected_ids:
                    connection.execute(
                        "UPDATE cards SET position = position + 1000000 WHERE id = ?",
                        (affected_id,),
                    )
                connection.execute(
                    "UPDATE cards SET position = 1000000000 WHERE id = ?",
                    (card_id,),
                )
                connection.execute(
                    "UPDATE cards SET column_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (destination_id, card_id),
                )
                _set_positions(connection, source_ids)
                _set_positions(connection, destination_ids)
            else:
                _reorder_column(connection, destination_id, destination_ids)
            return _board_response(connection, user["id"])
