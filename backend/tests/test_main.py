from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


def make_frontend_build(tmp_path: Path) -> Path:
    build_dir = tmp_path / "build"
    (build_dir / "_app").mkdir(parents=True)
    (build_dir / "index.html").write_text("<html>home</html>")
    (build_dir / "200.html").write_text("<html>fallback</html>")
    (build_dir / "_app" / "app.js").write_text("console.log('app')")
    return build_dir


def make_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(make_frontend_build(tmp_path), tmp_path / "app.db"))


def test_health_endpoint(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_example_endpoint(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.get("/api/example")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello from the Project Management MVP backend"}


def test_frontend_root_serves_index(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert response.text == "<html>home</html>"


def test_frontend_asset_is_served(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.get("/_app/app.js")

    assert response.status_code == 200
    assert response.text == "console.log('app')"


def test_unknown_frontend_route_uses_fallback(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.get("/board")

    assert response.status_code == 200
    assert response.text == "<html>fallback</html>"


def test_api_routes_take_priority_over_frontend_fallback(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.get("/api/health")

    assert response.text != "<html>fallback</html>"


def test_missing_frontend_build_returns_service_unavailable(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "missing", tmp_path / "app.db"))

    response = client.get("/")

    assert response.status_code == 503
    assert response.json() == {"detail": "Frontend build is not available"}
