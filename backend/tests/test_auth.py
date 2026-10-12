import json
import time

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from backend.app.auth import Authentication, configured_users
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


def attempt(connection, username="alice@example.com", password="wrong"):
    return connection.post("/api/auth/login", json={"username": username, "password": password})


def test_repeated_failures_lock_the_username_with_a_retry_delay():
    connection = client()
    for _ in range(5):
        assert attempt(connection).status_code == 401

    locked = attempt(connection)
    assert locked.status_code == 429
    assert int(locked.headers["retry-after"]) > 0
    assert "Too many failed sign-in attempts" in locked.json()["detail"]
    # Even the right password waits out the lockout.
    assert attempt(connection, password="correct-password").status_code == 429


def test_unknown_usernames_are_throttled_the_same_way():
    connection = client()
    for _ in range(5):
        assert attempt(connection, username="nobody@example.com").status_code == 401
    assert attempt(connection, username="nobody@example.com").status_code == 429


def test_a_successful_sign_in_resets_the_failure_count():
    connection = client()
    for _ in range(4):
        assert attempt(connection).status_code == 401
    assert attempt(connection, password="correct-password").status_code == 200
    for _ in range(4):
        assert attempt(connection).status_code == 401
    assert attempt(connection, password="correct-password").status_code == 200


def test_lockout_ends_and_failures_are_forgotten(monkeypatch):
    connection = client()
    authentication = connection.app.state.authentication
    for _ in range(5):
        attempt(connection)
    assert attempt(connection).status_code == 429
    count, last = authentication.failures["alice@example.com"]
    authentication.failures["alice@example.com"] = (count, last - 60)
    assert attempt(connection, password="correct-password").status_code == 200


def test_lockout_delay_doubles_and_is_capped():
    authentication = Authentication({})
    for _ in range(5):
        authentication.record_failure("a")
    first = authentication.lockout_remaining("a")
    authentication.record_failure("a")
    assert authentication.lockout_remaining("a") > first
    for _ in range(30):
        authentication.record_failure("a")
    assert authentication.lockout_remaining("a") <= 15 * 60 + 1


def test_the_failure_table_stays_bounded(monkeypatch):
    monkeypatch.setattr("backend.app.auth.MAX_TRACKED_USERNAMES", 3)
    authentication = Authentication({})
    for name in "abcdef":
        authentication.record_failure(name)
    assert len(authentication.failures) == 3


def test_allowed_origin_is_used_instead_of_the_request_origin(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGIN", "https://tools.example.com/")
    connection = client()
    ok = connection.post(
        "/api/auth/login", headers={"Origin": "https://tools.example.com"},
        json={"username": "alice@example.com", "password": "correct-password"},
    )
    assert ok.status_code == 200
    other = connection.post("/api/auth/login", headers={"Origin": "http://testserver"})
    assert other.status_code == 403


def test_without_allowed_origin_the_request_origin_still_works():
    connection = client()
    ok = connection.post(
        "/api/auth/login", headers={"Origin": "http://testserver"},
        json={"username": "alice@example.com", "password": "correct-password"},
    )
    assert ok.status_code == 200


@pytest.mark.parametrize("value", ["tools.example.com", "ftp://x.example.com", "https://x.example.com/path"])
def test_malformed_allowed_origin_fails_at_startup(monkeypatch, value):
    monkeypatch.setenv("ALLOWED_ORIGIN", value)
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGIN"):
        client()
