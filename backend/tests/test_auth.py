from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "index.html").write_text("<html>home</html>")
    return TestClient(create_app(frontend_dir, tmp_path / "app.db"))


def test_unauthenticated_me_is_rejected(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_valid_login_sets_http_only_session_cookie_and_me_returns_user(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "user", "password": "password"},
        )
        current_user = client.get("/api/auth/me")

    assert login.status_code == 200
    assert login.json() == {"username": "user"}
    set_cookie = login.headers["set-cookie"]
    assert "pm_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert current_user.status_code == 200
    assert current_user.json() == {"username": "user"}


def test_invalid_credentials_are_rejected(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "user", "password": "wrong"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}
    assert "pm_session=" not in response.headers.get("set-cookie", "")


def test_logout_removes_access(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        assert client.post(
            "/api/auth/login",
            json={"username": "user", "password": "password"},
        ).status_code == 200
        logout = client.post("/api/auth/logout")
        current_user = client.get("/api/auth/me")

    assert logout.status_code == 200
    assert logout.json() == {"logged_out": True}
    assert current_user.status_code == 401


def test_session_is_removed_when_expired(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.post(
            "/api/auth/login",
            json={"username": "user", "password": "password"},
        )
        database_path = tmp_path / "app.db"
        import sqlite3

        with sqlite3.connect(database_path) as connection:
            connection.execute(
                "UPDATE sessions SET expires_at = ?",
                ("2000-01-01T00:00:00+00:00",),
            )
            connection.commit()
        response = client.get("/api/auth/me")

    assert response.status_code == 401
