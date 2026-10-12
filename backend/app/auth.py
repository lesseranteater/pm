"""Environment-configured Argon2id credentials and in-memory cookie sessions."""

import hashlib
import json
import os
import secrets
import time
from threading import Lock

from argon2 import PasswordHasher, extract_parameters
from argon2.exceptions import VerificationError
from argon2.low_level import Type
from dotenv import load_dotenv

from .main_paths import PROJECT_ROOT

SESSION_COOKIE = "pm_session"
SESSION_TTL = 7 * 24 * 60 * 60


def configured_users() -> dict[str, str]:
    load_dotenv(PROJECT_ROOT / ".env")
    try:
        records = json.loads(os.environ.get("AUTH_USERS_JSON", "[]"))
        if not isinstance(records, list):
            raise ValueError()
        users = {}
        for record in records:
            username = record["username"].strip().lower()
            password_hash = record["password_hash"]
            if not username or username in users or extract_parameters(password_hash).type != Type.ID:
                raise ValueError()
            users[username] = password_hash
        return users
    except (ValueError, TypeError, KeyError, AttributeError):
        raise RuntimeError("AUTH_USERS_JSON must contain unique usernames and valid Argon2id hashes") from None


class Authentication:
    def __init__(self, users: dict[str, str]):
        self.users = users
        self.hasher = PasswordHasher()
        self.dummy_hash = self.hasher.hash(secrets.token_urlsafe(32))
        self.sessions: dict[str, tuple[str, float]] = {}
        self.lock = Lock()

    def verify(self, username: str, password: str) -> bool:
        stored = self.users.get(username, self.dummy_hash)
        try:
            valid = self.hasher.verify(stored, password)
            return valid and username in self.users
        except VerificationError:
            return False

    def create_session(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        with self.lock:
            now = time.time()
            self.sessions = {key: value for key, value in self.sessions.items() if value[1] > now}
            self.sessions[self._hash(token)] = (username, now + SESSION_TTL)
        return token

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def user(self, token: str | None) -> str | None:
        if not token:
            return None
        with self.lock:
            key = self._hash(token)
            session = self.sessions.get(key)
            if session and session[1] > time.time():
                return session[0]
            self.sessions.pop(key, None)
        return None

    def logout(self, token: str | None) -> None:
        if token:
            with self.lock:
                self.sessions.pop(self._hash(token), None)
