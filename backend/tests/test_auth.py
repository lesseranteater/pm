import json
import time

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from backend.app.auth import configured_users
from backend.app.main import create_app

HASH = PasswordHasher().hash("correct-password")


def client():
    return TestClient(create_app(auth_users={"alice@example.com": HASH}))


def login(connection):
    return connection.post("/api/auth/login", json={
        "username": "ALICE@example.com", "password": "correct-password",
    })


def test_login_cookie_refresh_and_logout():
    connection = client()
    assert connection.get("/api/auth/me").status_code == 401
    result = login(connection)
    assert result.status_code == 200
    assert result.json() == {"username": "alice@example.com"}
    cookie = result.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Max-Age=604800" in cookie
    assert result.headers["cache-control"] == "no-store"
    assert connection.get("/api/auth/me").json() == {"username": "alice@example.com", "jira_configured": False}
    token = connection.cookies.get("pm_session")
    assert connection.post("/api/auth/logout").status_code == 200
    connection.cookies.set("pm_session", token)
    assert connection.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("username,password", [
    ("alice@example.com", "wrong"), ("unknown@example.com", "correct-password"),
])
def test_invalid_login(username, password):
    result = client().post("/api/auth/login", json={"username": username, "password": password})
    assert result.status_code == 401
    assert "set-cookie" not in result.headers


@pytest.mark.parametrize("path,method", [
    ("/api/service-versions", "post"), ("/api/release-semantic-version", "post"),
    ("/api/archive-released-versions", "post"), ("/api/release-check", "post"),
    ("/api/semantic-versions", "get"), ("/api/archive-released-versions/preview", "get"),
])
def test_all_jira_routes_require_authentication(path, method):
    assert getattr(client(), method)(path).status_code == 401


def test_session_expiration_and_restart():
    connection = client()
    login(connection)
    authentication = connection.app.state.authentication
    for key, (username, _) in list(authentication.sessions.items()):
        authentication.sessions[key] = (username, time.time() - 1)
    assert connection.get("/api/auth/me").status_code == 401
    assert not authentication.sessions
    login(connection)
    restarted = client()
    restarted.cookies.update(connection.cookies)
    assert restarted.get("/api/auth/me").status_code == 401


def test_cross_origin_posts_are_rejected():
    response = client().post("/api/auth/login", headers={"Origin": "https://other.example"})
    assert response.status_code == 403


def test_secure_cookie(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "true")
    assert "Secure" in login(client()).headers["set-cookie"]


def test_configuration_validation(monkeypatch):
    monkeypatch.setenv("AUTH_USERS_JSON", json.dumps([{"username": "alice@example.com", "password_hash": HASH}]))
    assert configured_users() == {"alice@example.com": HASH}
    monkeypatch.setenv("AUTH_USERS_JSON", '[{"username":"alice","password_hash":"secret"}]')
    with pytest.raises(RuntimeError, match="AUTH_USERS_JSON"):
        configured_users()


def test_unconfigured_login_fails_closed():
    response = TestClient(create_app(auth_users={})).post(
        "/api/auth/login", json={"username": "alice", "password": "password"},
    )
    assert response.status_code == 503
