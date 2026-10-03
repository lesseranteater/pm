from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone


SESSION_COOKIE_NAME = "pm_session"
SESSION_TTL = timedelta(days=7)
PASSWORD_SALT = b"project-management-mvp-seed"


def password_hash(password: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), PASSWORD_SALT, 120_000).hex()


def verify_password(password: str, stored_hash: str) -> bool:
    return hmac.compare_digest(password_hash(password), stored_hash)


def create_session(connection: sqlite3.Connection, user_id: str) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + SESSION_TTL
    connection.execute(
        """
        INSERT INTO sessions (id, user_id, token_hash, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (secrets.token_hex(16), user_id, token_hash, expires_at.isoformat()),
    )
    return token, expires_at


def get_user_for_session(
    connection: sqlite3.Connection, token: str | None
) -> sqlite3.Row | None:
    if not token:
        return None

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = connection.execute(
        """
        SELECT sessions.id, sessions.user_id, sessions.expires_at, users.username
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token_hash = ?
        """,
        (token_hash,),
    ).fetchone()
    if not session:
        return None

    expires_at = datetime.fromisoformat(session["expires_at"])
    if expires_at <= datetime.now(timezone.utc):
        connection.execute("DELETE FROM sessions WHERE id = ?", (session["id"],))
        return None
    return session


def delete_session(connection: sqlite3.Connection, token: str | None) -> None:
    if token:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
