import logging
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from backend.app import jira_credentials, release_check
from backend.app.main import create_app
from backend.app.script_runner import stream_script_log

HASH = PasswordHasher().hash("password")


def authenticated_client(app=None):
    client = TestClient(app or create_app(auth_users={"alice@example.com": HASH}))
    assert client.post("/api/auth/login", json={"username": "alice@example.com", "password": "password"}).status_code == 200
    return client


def test_token_is_kept_on_the_server_and_never_sent_to_the_browser():
    client = authenticated_client()
    result = client.post("/api/auth/jira-token", json={"token": "my-personal-token"})
    assert result.status_code == 200
    assert result.json() == {"jira_configured": True}
    assert "my-personal-token" not in "".join(result.headers.get_list("set-cookie"))
    assert "my-personal-token" not in "".join(client.cookies.values())
    assert client.get("/api/auth/me").json()["jira_configured"] is True


def test_token_is_dropped_with_its_session():
    app = create_app(auth_users={"alice@example.com": HASH})
    client = authenticated_client(app)
    client.post("/api/auth/jira-token", json={"token": "my-personal-token"})
    authentication = app.state.authentication
    assert list(authentication.jira_tokens.values()) == ["my-personal-token"]

    client.post("/api/auth/logout")
    assert authentication.jira_tokens == {}
    assert client.get("/api/auth/me").status_code == 401


def test_token_expires_with_the_session():
    import time

    app = create_app(auth_users={"alice@example.com": HASH})
    client = authenticated_client(app)
    client.post("/api/auth/jira-token", json={"token": "my-personal-token"})
    authentication = app.state.authentication
    for key, (username, _) in list(authentication.sessions.items()):
        authentication.sessions[key] = (username, time.time() - 1)

    assert client.get("/api/auth/me").status_code == 401
    assert authentication.jira_tokens == {}


def test_a_token_belongs_to_one_session_only():
    app = create_app(auth_users={"alice@example.com": HASH})
    first, second = authenticated_client(app), authenticated_client(app)
    first.post("/api/auth/jira-token", json={"token": "first-token"})
    assert first.get("/api/auth/me").json()["jira_configured"] is True
    assert second.get("/api/auth/me").json()["jira_configured"] is False


def test_a_legacy_token_cookie_is_ignored():
    client = authenticated_client()
    client.cookies.set("pm_jira_token", "old-cookie-token")
    assert client.get("/api/auth/me").json()["jira_configured"] is False
    assert client.post("/api/service-versions", json={
        "project_key": "IGM", "release_version": "Deploy.ai-data.26.4.1",
    }).status_code == 428


def test_new_login_discards_previous_jira_token():
    client = authenticated_client()
    client.post("/api/auth/jira-token", json={"token": "old-token"})
    client.post("/api/auth/login", json={"username": "alice@example.com", "password": "password"})
    assert client.get("/api/auth/me").json()["jira_configured"] is False


@pytest.mark.parametrize("token", ["", "has spaces", "line\nbreak", "x" * 2049])
def test_invalid_cookie_tokens_are_rejected(token):
    response = authenticated_client().post("/api/auth/jira-token", json={"token": token})
    assert response.status_code == 422


def test_token_endpoint_requires_login():
    client = TestClient(create_app(auth_users={"alice@example.com": HASH}))
    assert client.post("/api/auth/jira-token", json={"token": "token"}).status_code == 401


@pytest.mark.parametrize("path,method", [
    ("/api/service-versions", "post"), ("/api/release-semantic-version", "post"),
    ("/api/archive-released-versions", "post"), ("/api/release-check", "post"),
    ("/api/semantic-versions", "get"), ("/api/archive-released-versions/preview", "get"),
])
def test_tool_routes_require_a_user_token_even_if_env_token_exists(monkeypatch, path, method):
    monkeypatch.setenv("JIRA_TOKEN", "server-token-must-not-be-used")
    assert getattr(authenticated_client(), method)(path).status_code == 428


def test_clients_and_streaming_workers_use_the_request_cookie(monkeypatch):
    seen = []
    monkeypatch.setenv("JIRA_TOKEN", "unused-server-token")
    monkeypatch.setenv("JIRA_URL", "https://jira.example.com")
    monkeypatch.setattr(jira_credentials, "JIRA", lambda **kwargs: seen.append(kwargs))
    logger = logging.getLogger("test-jira-token-workers")
    logger.setLevel(logging.INFO)
    lock = threading.Lock()

    def report(project, version):
        def work():
            jira_credentials.create_jira_client()
            logger.info("Report complete")
        return stream_script_log(logger, lock, work, "Failed")

    app = create_app(auth_users={"alice@example.com": HASH}, service_version_reporter=report)
    first, second = authenticated_client(app), authenticated_client(app)
    first.post("/api/auth/jira-token", json={"token": "first-user-token"})
    second.post("/api/auth/jira-token", json={"token": "second-user-token"})

    def run(client):
        result = client.post("/api/service-versions", json={
            "project_key": "IGM", "release_version": "Deploy.ai-data.26.4.1",
        })
        assert result.status_code == 200 and "Report complete" in result.text
        assert "user-token" not in result.text

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, [first, second]))
    assert sorted(value["token_auth"] for value in seen) == ["first-user-token", "second-user-token"]
    assert all(value["server"] == "https://jira.example.com" for value in seen)
    assert all(value["timeout"] == jira_credentials.JIRA_TIMEOUT for value in seen)
    assert not jira_credentials.jira_token_configured()


def test_no_environment_fallback_for_direct_client(monkeypatch):
    monkeypatch.setenv("JIRA_TOKEN", "unused-server-token")
    with pytest.raises(RuntimeError, match="Enter your Jira token"):
        jira_credentials.create_jira_client()


def test_release_check_import_does_not_create_an_environment_client(monkeypatch):
    import importlib
    monkeypatch.setattr(jira_credentials, "JIRA", lambda **kwargs: pytest.fail("Import must not connect to Jira"))
    assert callable(importlib.reload(release_check).find_mismatching_version_sources)
