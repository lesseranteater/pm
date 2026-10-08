from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.service_versions import ServiceVersion


def make_frontend_build(tmp_path: Path) -> Path:
    build_dir = tmp_path / "build"
    (build_dir / "_app").mkdir(parents=True)
    (build_dir / "index.html").write_text("<html>home</html>")
    (build_dir / "200.html").write_text("<html>fallback</html>")
    (build_dir / "_app" / "app.js").write_text("console.log('app')")
    return build_dir


def make_client(
    tmp_path: Path, service_version_reporter=lambda: []
) -> TestClient:
    return TestClient(create_app(make_frontend_build(tmp_path), service_version_reporter))


def test_health_endpoint(tmp_path: Path) -> None:
    response = make_client(tmp_path).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_message_endpoint(tmp_path: Path) -> None:
    response = make_client(tmp_path).get("/api/message")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello from the Python backend."}


def test_service_versions_endpoint_returns_the_report(tmp_path: Path) -> None:
    client = make_client(
        tmp_path,
        lambda: [ServiceVersion(id="2", name="ignore-this.bo.26.4.1")],
    )

    response = client.get("/api/service-versions")

    assert response.status_code == 200
    assert response.json() == [{"id": "2", "name": "ignore-this.bo.26.4.1"}]


def test_service_versions_endpoint_hides_upstream_errors(tmp_path: Path) -> None:
    def fail() -> list[ServiceVersion]:
        raise RuntimeError("Jira token must not be exposed")

    response = make_client(tmp_path, fail).get("/api/service-versions")

    assert response.status_code == 503
    assert response.json() == {"detail": "Unable to retrieve service versions from Jira"}


def test_frontend_root_serves_index(tmp_path: Path) -> None:
    response = make_client(tmp_path).get("/")

    assert response.status_code == 200
    assert response.text == "<html>home</html>"


def test_frontend_asset_is_served(tmp_path: Path) -> None:
    response = make_client(tmp_path).get("/_app/app.js")

    assert response.status_code == 200
    assert response.text == "console.log('app')"


def test_unknown_frontend_route_uses_fallback(tmp_path: Path) -> None:
    response = make_client(tmp_path).get("/another-page")

    assert response.status_code == 200
    assert response.text == "<html>fallback</html>"


def test_missing_frontend_build_returns_service_unavailable(tmp_path: Path) -> None:
    response = TestClient(create_app(tmp_path / "missing")).get("/")

    assert response.status_code == 503
    assert response.json() == {"detail": "Frontend build is not available"}
