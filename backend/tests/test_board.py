import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.auth import password_hash
from backend.app.main import create_app


def make_client(tmp_path: Path) -> tuple[TestClient, Path]:
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "index.html").write_text("<html>home</html>")
    database_path = tmp_path / "app.db"
    return TestClient(create_app(frontend_dir, database_path)), database_path


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert response.status_code == 200


def test_board_requires_authentication(tmp_path: Path) -> None:
    with make_client(tmp_path)[0] as client:
        response = client.get("/api/board")

    assert response.status_code == 401


def test_read_board_returns_ordered_seed_data(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    with client:
        login(client)
        response = client.get("/api/board")

    assert response.status_code == 200
    board = response.json()
    assert board["id"] == "board-mvp"
    assert [column["name"] for column in board["columns"]] == [
        "Backlog",
        "Planned",
        "In progress",
        "Review",
        "Done",
    ]
    assert board["columns"][0]["cards"][0]["title"] == "Shape the product brief"


def test_card_and_column_mutations_preserve_order(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    with client:
        login(client)
        created = client.post(
            "/api/board/cards",
            json={
                "column_id": "column-review",
                "title": "  Prepare demo  ",
                "details": "  Confirm the walkthrough  ",
            },
        )
        assert created.status_code == 200
        card = next(
            card
            for column in created.json()["columns"]
            for card in column["cards"]
            if card["title"] == "Prepare demo"
        )

        updated = client.patch(
            f"/api/board/cards/{card['id']}",
            json={"title": "Run the demo", "details": "Invite the team"},
        )
        assert updated.status_code == 200

        moved = client.post(
            f"/api/board/cards/{card['id']}/move",
            json={"column_id": "column-backlog", "position": 0},
        )
        assert moved.status_code == 200
        assert [
            item["title"] for item in moved.json()["columns"][0]["cards"]
        ] == ["Run the demo", "Shape the product brief"]

        renamed = client.patch(
            "/api/board/columns/column-review",
            json={"name": "Ready for review"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["columns"][3]["name"] == "Ready for review"

        deleted = client.delete(f"/api/board/cards/{card['id']}")
        assert deleted.status_code == 200
        assert all(
            item["id"] != card["id"]
            for column in deleted.json()["columns"]
            for item in column["cards"]
        )


def test_invalid_resources_and_positions_do_not_mutate_board(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    with client:
        login(client)
        before = client.get("/api/board").json()
        unknown_card = client.patch(
            "/api/board/cards/missing-card",
            json={"title": "Nope"},
        )
        invalid_column = client.post(
            "/api/board/cards",
            json={"column_id": "missing-column", "title": "Nope"},
        )
        invalid_position = client.post(
            "/api/board/cards/card-brief/move",
            json={"column_id": "column-done", "position": 99},
        )
        after = client.get("/api/board").json()

    assert unknown_card.status_code == 404
    assert invalid_column.status_code == 404
    assert invalid_position.status_code == 422
    assert after == before


def test_board_ownership_is_enforced(tmp_path: Path) -> None:
    client, database_path = make_client(tmp_path)
    with client:
        login(client)
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
                ("other-user", "other", password_hash("other-password")),
            )
            connection.execute(
                "INSERT INTO boards (id, user_id, name) VALUES (?, ?, ?)",
                ("other-board", "other-user", "Other board"),
            )
            connection.execute(
                "INSERT INTO columns (id, board_id, name, position) VALUES (?, ?, ?, ?)",
                ("other-column", "other-board", "Other", 0),
            )
            connection.execute(
                """
                INSERT INTO cards (id, column_id, title, details, position)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("other-card", "other-column", "Private card", "", 0),
            )
            connection.commit()

        board = client.get("/api/board")
        update = client.patch("/api/board/cards/other-card", json={"title": "Changed"})

    assert board.status_code == 200
    assert all(
        card["id"] != "other-card"
        for column in board.json()["columns"]
        for card in column["cards"]
    )
    assert update.status_code == 404


def test_board_changes_persist_across_app_instances(tmp_path: Path) -> None:
    client, database_path = make_client(tmp_path)
    with client:
        login(client)
        response = client.post(
            "/api/board/cards",
            json={"column_id": "column-done", "title": "Persist me"},
        )
        assert response.status_code == 200

    second_client = TestClient(create_app(tmp_path / "frontend", database_path))
    with second_client:
        login(second_client)
        board = second_client.get("/api/board").json()

    assert any(
        card["title"] == "Persist me"
        for column in board["columns"]
        for card in column["cards"]
    )
