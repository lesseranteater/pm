import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.database import connect, initialize_database
from backend.app.main import create_app


def test_initialization_creates_schema_and_seed_data(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "app.db"

    result = initialize_database(database_path)

    assert result == database_path.resolve()
    assert database_path.exists()
    with connect(database_path) as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert tables == {"users", "boards", "columns", "cards", "sessions"}
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM boards").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM columns").fetchone()[0] == 5
        assert connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 4


def test_initialization_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "app.db"

    initialize_database(database_path)
    initialize_database(database_path)

    with connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM boards").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM columns").fetchone()[0] == 5
        assert connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 4


def test_seed_order_is_deterministic(tmp_path: Path) -> None:
    database_path = tmp_path / "app.db"
    initialize_database(database_path)

    with connect(database_path) as connection:
        columns = connection.execute(
            "SELECT name FROM columns ORDER BY position"
        ).fetchall()
        cards = connection.execute(
            """
            SELECT cards.title
            FROM cards
            JOIN columns ON columns.id = cards.column_id
            ORDER BY columns.position, cards.position
            """
        ).fetchall()

    assert [row["name"] for row in columns] == [
        "Backlog",
        "Planned",
        "In progress",
        "Review",
        "Done",
    ]
    assert [row["title"] for row in cards] == [
        "Shape the product brief",
        "Review interview notes",
        "Prototype the board flow",
        "Prepare release notes",
    ]


def test_foreign_keys_are_enforced(tmp_path: Path) -> None:
    database_path = tmp_path / "app.db"
    initialize_database(database_path)

    with connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO boards (id, user_id, name) VALUES (?, ?, ?)",
                ("orphan-board", "missing-user", "Invalid"),
            )


def test_database_creates_parent_directory(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "app.db"

    initialize_database(database_path)

    assert database_path.parent.is_dir()


def test_fastapi_startup_initializes_database(tmp_path: Path) -> None:
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "index.html").write_text("<html>home</html>")
    database_path = tmp_path / "startup" / "app.db"

    with TestClient(create_app(frontend_dir, database_path)) as client:
        assert client.get("/api/health").status_code == 200

    assert database_path.exists()
    with connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM columns").fetchone()[0] == 5
