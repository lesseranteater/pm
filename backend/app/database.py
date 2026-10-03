from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from .main_paths import PROJECT_ROOT


DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "app.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS boards (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS columns (
    id TEXT PRIMARY KEY,
    board_id TEXT NOT NULL,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    position INTEGER NOT NULL CHECK (position >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (board_id, position),
    UNIQUE (board_id, id),
    FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    column_id TEXT NOT NULL,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    details TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL CHECK (position >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (column_id, position),
    FOREIGN KEY (column_id) REFERENCES columns(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_columns_board_id ON columns(board_id);
CREATE INDEX IF NOT EXISTS idx_cards_column_id ON cards(column_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
"""

SEED_COLUMNS = (
    ("column-backlog", "Backlog", 0),
    ("column-planned", "Planned", 1),
    ("column-progress", "In progress", 2),
    ("column-review", "Review", 3),
    ("column-done", "Done", 4),
)

SEED_CARDS = (
    (
        "card-brief",
        "column-backlog",
        "Shape the product brief",
        "Turn the strongest customer needs into a focused one-page brief.",
        0,
    ),
    (
        "card-research",
        "column-planned",
        "Review interview notes",
        "Pull out recurring themes and questions for the next sprint.",
        0,
    ),
    (
        "card-prototype",
        "column-progress",
        "Prototype the board flow",
        "Try the quickest path from a new card to a completed task.",
        0,
    ),
    (
        "card-release",
        "column-done",
        "Prepare release notes",
        "Capture the decisions and improvements that matter to the team.",
        0,
    ),
)


def _password_hash(password: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), b"project-management-mvp-seed", 120_000
    ).hex()


def connect(database_path: Path | str) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: Path | str | None = None) -> Path:
    path = Path(database_path or DEFAULT_DATABASE_PATH).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    with connect(path) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            """
            INSERT OR IGNORE INTO users (id, username, password_hash)
            VALUES (?, ?, ?)
            """,
            ("user-mvp", "user", _password_hash("password")),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO boards (id, user_id, name)
            VALUES (?, ?, ?)
            """,
            ("board-mvp", "user-mvp", "Spring launch"),
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO columns (id, board_id, name, position)
            VALUES (?, ?, ?, ?)
            """,
            ((column_id, "board-mvp", name, position) for column_id, name, position in SEED_COLUMNS),
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO cards (id, column_id, title, details, position)
            VALUES (?, ?, ?, ?, ?)
            """,
            SEED_CARDS,
        )

    return path
