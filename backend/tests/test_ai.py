from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.app.main import create_app


class FakeAIClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.messages: list[dict[str, str]] = []

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        self.messages = messages
        return self.response


def make_client(tmp_path: Path, response: dict[str, Any]) -> tuple[TestClient, FakeAIClient]:
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("<html>home</html>")
    ai_client = FakeAIClient(response)
    return TestClient(create_app(frontend_dir, tmp_path / "app.db", ai_client)), ai_client


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert response.status_code == 200


def board(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/board")
    assert response.status_code == 200
    return response.json()


def test_ai_route_requires_authentication(tmp_path: Path) -> None:
    with make_client(tmp_path, {"response": "No changes"})[0] as client:
        response = client.post("/api/ai/board", json={"question": "Summarize the board"})

    assert response.status_code == 401


def test_ai_response_without_operations_and_history_forwarding(tmp_path: Path) -> None:
    client, fake = make_client(tmp_path, {"response": "The board is ready."})
    with client:
        login(client)
        response = client.post(
            "/api/ai/board",
            json={
                "question": "What should I work on next?",
                "history": [
                    {"role": "user", "content": "I need focus."},
                    {"role": "assistant", "content": "Review the backlog."},
                ],
            },
        )

    assert response.status_code == 200
    assert response.json()["response"] == "The board is ready."
    assert response.json()["board"]["id"] == "board-mvp"
    assert [message["role"] for message in fake.messages] == ["system", "user", "assistant", "user"]
    assert "What should I work on next?" in fake.messages[-1]["content"]
    assert "card-brief" in fake.messages[-1]["content"]


def test_all_supported_operations_apply_in_one_batch(tmp_path: Path) -> None:
    response = {
        "response": "I organized the board.",
        "operations": [
            {"op": "create_card", "column_id": "column-review", "title": "Demo", "details": "Prepare slides"},
            {"op": "edit_card", "card_id": "card-brief", "title": "Shape the focused brief"},
            {"op": "move_card", "card_id": "card-research", "column_id": "column-progress", "position": 0},
            {"op": "delete_card", "card_id": "card-release"},
            {"op": "rename_column", "column_id": "column-review", "name": "Ready"},
        ],
    }
    client, _ = make_client(tmp_path, response)
    with client:
        login(client)
        result = client.post("/api/ai/board", json={"question": "Organize this board"})

    assert result.status_code == 200
    updated = result.json()["board"]
    assert updated["columns"][0]["cards"][0]["title"] == "Shape the focused brief"
    assert updated["columns"][2]["cards"][0]["id"] == "card-research"
    assert updated["columns"][3]["name"] == "Ready"
    assert updated["columns"][3]["cards"][0]["title"] == "Demo"
    assert all(card["id"] != "card-release" for column in updated["columns"] for card in column["cards"])


def test_malformed_ai_output_is_rejected_without_mutation(tmp_path: Path) -> None:
    client, _ = make_client(
        tmp_path,
        {"response": "Bad", "operations": [{"op": "unknown_operation", "card_id": "card-brief"}]},
    )
    with client:
        login(client)
        before = board(client)
        response = client.post("/api/ai/board", json={"question": "Do something"})
        after = board(client)

    assert response.status_code == 502
    assert response.json() == {"detail": "AI response did not match the required contract"}
    assert after == before


def test_unknown_and_conflicting_operations_are_rejected_atomically(tmp_path: Path) -> None:
    client, _ = make_client(
        tmp_path,
        {
            "response": "Partial work",
            "operations": [
                {"op": "rename_column", "column_id": "column-review", "name": "Changed"},
                {"op": "delete_card", "card_id": "missing-card"},
            ],
        },
    )
    with client:
        login(client)
        response = client.post("/api/ai/board", json={"question": "Make two changes"})
        unchanged = board(client)

    assert response.status_code == 422
    assert unchanged["columns"][3]["name"] == "Review"

    conflicting_client, _ = make_client(
        tmp_path / "conflict",
        {
            "response": "Conflicting work",
            "operations": [
                {"op": "edit_card", "card_id": "card-brief", "title": "First"},
                {"op": "delete_card", "card_id": "card-brief"},
            ],
        },
    )
    with conflicting_client:
        login(conflicting_client)
        conflicting = conflicting_client.post("/api/ai/board", json={"question": "Conflict"})

    assert conflicting.status_code == 422


def test_invalid_operation_values_are_rejected(tmp_path: Path) -> None:
    client, _ = make_client(
        tmp_path,
        {
            "response": "Invalid",
            "operations": [{"op": "create_card", "column_id": "column-review", "title": "   "}],
        },
    )
    with client:
        login(client)
        response = client.post("/api/ai/board", json={"question": "Create it"})

    assert response.status_code == 422
    assert response.json() == {"detail": "Card title cannot be empty"}
