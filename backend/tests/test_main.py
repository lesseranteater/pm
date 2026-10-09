from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.release_semantic_version import ProjectNotFoundError


def make_frontend_build(tmp_path: Path) -> Path:
    build_dir = tmp_path / "build"
    (build_dir / "_app").mkdir(parents=True)
    (build_dir / "index.html").write_text("<html>home</html>")
    (build_dir / "200.html").write_text("<html>fallback</html>")
    (build_dir / "_app" / "app.js").write_text("console.log('app')")
    return build_dir


def make_client(
    tmp_path: Path,
    service_version_reporter=lambda project_key, release_version: "",
    semantic_version_releaser=lambda version_name, is_dry_run: "",
    semantic_version_lister=lambda status, project_key: [],
    released_version_archiver=lambda project_key, is_dry_run, archive_until: "",
    released_version_previewer=lambda project_key, archive_until: {"count": 0, "semantic": 0, "service": 0},
    jira_configured=lambda: True,
    release_checker=lambda deployment_plan_key: "",
) -> TestClient:
    return TestClient(
        create_app(
            make_frontend_build(tmp_path),
            service_version_reporter,
            semantic_version_releaser,
            semantic_version_lister,
            released_version_archiver,
            released_version_previewer,
            jira_configured,
            release_checker,
        )
    )


def test_health_endpoint(tmp_path: Path) -> None:
    response = make_client(tmp_path).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "jira_configured": True}


def test_health_endpoint_reports_missing_jira_configuration(tmp_path: Path) -> None:
    response = make_client(tmp_path, jira_configured=lambda: False).get("/api/health")

    assert response.json() == {"status": "ok", "jira_configured": False}


def test_service_versions_endpoint_returns_the_report(tmp_path: Path) -> None:
    requested_parameters = []

    def report(project_key: str, release_version: str) -> str:
        requested_parameters.append((project_key, release_version))
        return "Service version without release date: ignore-this.bo.26.4.1"

    client = make_client(
        tmp_path,
        report,
    )

    response = client.post(
        "/api/service-versions",
        json={"project_key": "IGM", "release_version": "Deploy.ai-data.26.4.1"},
    )

    assert response.status_code == 200
    assert response.text == "Service version without release date: ignore-this.bo.26.4.1"
    assert requested_parameters == [("IGM", "Deploy.ai-data.26.4.1")]


def test_service_versions_endpoint_hides_upstream_errors(tmp_path: Path) -> None:
    def fail(project_key: str, release_version: str) -> str:
        raise RuntimeError("Jira token must not be exposed")

    response = make_client(tmp_path, fail).post(
        "/api/service-versions",
        json={"project_key": "IGM", "release_version": "Deploy.ai-data.26.4.1"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Unable to retrieve service versions from Jira"}


def test_service_versions_endpoint_rejects_invalid_parameters(tmp_path: Path) -> None:
    response = make_client(tmp_path).post(
        "/api/service-versions",
        json={"project_key": "IGM OR 1=1", "release_version": "not-a-release"},
    )

    assert response.status_code == 422


def test_release_semantic_version_returns_the_captured_log(tmp_path: Path) -> None:
    requests = []

    def release(version_name: str, is_dry_run: bool) -> str:
        requests.append((version_name, is_dry_run))
        return "DRY RUN: would release version"

    response = make_client(tmp_path, semantic_version_releaser=release).post(
        "/api/release-semantic-version",
        json={"version_name": "Hotfix.ps-dev-1.26.4.3", "is_dry_run": True},
    )

    assert response.status_code == 200
    assert response.text == "DRY RUN: would release version"
    assert requests == [("Hotfix.ps-dev-1.26.4.3", True)]


def test_release_semantic_version_rejects_invalid_version(tmp_path: Path) -> None:
    response = make_client(tmp_path).post(
        "/api/release-semantic-version",
        json={"version_name": "not-a-release", "is_dry_run": True},
    )

    assert response.status_code == 422


def test_semantic_versions_returns_names_for_the_requested_status(tmp_path: Path) -> None:
    requests = []

    def lister(status: str, project_key: str) -> list[str]:
        requests.append((status, project_key))
        return ["Config.core-dev-1.26.4.4", "Deploy.fe-dev.26.4.3"]

    client = make_client(tmp_path, semantic_version_lister=lister)

    response = client.get("/api/semantic-versions", params={"status": "archived", "project_key": "ABC"})

    assert response.status_code == 200
    assert response.json() == ["Config.core-dev-1.26.4.4", "Deploy.fe-dev.26.4.3"]
    assert requests == [("archived", "ABC")]


def test_semantic_versions_default_to_unreleased_for_igm(tmp_path: Path) -> None:
    requests = []

    def lister(status: str, project_key: str) -> list[str]:
        requests.append((status, project_key))
        return []

    make_client(tmp_path, semantic_version_lister=lister).get("/api/semantic-versions")

    assert requests == [("unreleased", "IGM")]


def test_semantic_versions_reject_unknown_status_and_project_key(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    assert client.get("/api/semantic-versions", params={"status": "deleted"}).status_code == 422
    assert client.get("/api/semantic-versions", params={"project_key": "bad key"}).status_code == 422


def test_semantic_versions_report_unknown_project(tmp_path: Path) -> None:
    def missing(status: str, project_key: str) -> list[str]:
        raise ProjectNotFoundError(project_key)

    response = make_client(tmp_path, semantic_version_lister=missing).get(
        "/api/semantic-versions", params={"project_key": "ABC"}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Jira project ABC was not found"}


def test_semantic_versions_report_jira_failure(tmp_path: Path) -> None:
    def fail(status: str, project_key: str) -> list[str]:
        raise RuntimeError("JIRA_TOKEN environment variable is not configured")

    response = make_client(tmp_path, semantic_version_lister=fail).get("/api/semantic-versions")

    assert response.status_code == 503


def test_archive_released_versions_returns_the_captured_log(tmp_path: Path) -> None:
    requests = []

    def archive(project_key: str, is_dry_run: bool, archive_until: date) -> str:
        requests.append((project_key, is_dry_run, archive_until))
        return "Dry run: no changes were made."

    response = make_client(tmp_path, released_version_archiver=archive).post(
        "/api/archive-released-versions",
        json={"project_key": "IGM", "is_dry_run": True, "archive_until": "2026-09-30"},
    )

    assert response.status_code == 200
    assert response.text == "Dry run: no changes were made."
    assert requests == [("IGM", True, date(2026, 9, 30))]


def test_archive_released_versions_rejects_invalid_requests(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    valid = {"project_key": "IGM", "is_dry_run": True, "archive_until": "2026-09-30"}

    def post(**changes):
        return client.post("/api/archive-released-versions", json={**valid, **changes})

    assert post(project_key="igm").status_code == 422
    assert post(archive_until="not-a-date").status_code == 422
    assert post(archive_until="2999-01-01").status_code == 422  # future dates are rejected
    assert client.post(
        "/api/archive-released-versions", json={"project_key": "IGM", "is_dry_run": True}
    ).status_code == 422


def test_archive_released_versions_reports_failure(tmp_path: Path) -> None:
    def fail(project_key: str, is_dry_run: bool, archive_until: date) -> str:
        raise RuntimeError("boom")

    response = make_client(tmp_path, released_version_archiver=fail).post(
        "/api/archive-released-versions",
        json={"project_key": "IGM", "is_dry_run": False, "archive_until": "2026-09-30"},
    )

    assert response.status_code == 503


def test_release_check_returns_the_script_log(tmp_path: Path) -> None:
    requests = []

    def check(deployment_plan_key: str) -> str:
        requests.append(deployment_plan_key)
        return "CHECK COMPLETE"

    response = make_client(tmp_path, release_checker=check).post(
        "/api/release-check", json={"deployment_plan_key": "IGM-123"}
    )

    assert response.status_code == 200
    assert response.text == "CHECK COMPLETE"
    assert requests == ["IGM-123"]


def test_release_check_rejects_invalid_deployment_plan_key(tmp_path: Path) -> None:
    response = make_client(tmp_path).post(
        "/api/release-check", json={"deployment_plan_key": "not-a-key"}
    )

    assert response.status_code == 422


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


def test_script_endpoints_stream_the_log_as_plain_text(tmp_path: Path) -> None:
    def archive(project_key: str, is_dry_run: bool, archive_until: date):
        yield "first line\n"
        yield "second line\n"

    response = make_client(tmp_path, released_version_archiver=archive).post(
        "/api/archive-released-versions",
        json={"project_key": "IGM", "is_dry_run": True, "archive_until": "2026-09-30"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["cache-control"] == "no-store"
    assert response.text == "first line\nsecond line\n"


def test_archive_preview_returns_the_counts(tmp_path: Path) -> None:
    requests = []

    def preview(project_key: str, archive_until: date) -> dict[str, int]:
        requests.append((project_key, archive_until))
        return {"count": 3, "semantic": 2, "service": 1}

    response = make_client(tmp_path, released_version_previewer=preview).get(
        "/api/archive-released-versions/preview",
        params={"project_key": "IGM", "archive_until": "2026-09-30"},
    )

    assert response.status_code == 200
    assert response.json() == {"count": 3, "semantic": 2, "service": 1}
    assert requests == [("IGM", date(2026, 9, 30))]


def test_archive_preview_rejects_invalid_requests(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    url = "/api/archive-released-versions/preview"

    assert client.get(url, params={"project_key": "igm", "archive_until": "2026-09-30"}).status_code == 422
    assert client.get(url, params={"project_key": "IGM", "archive_until": "nope"}).status_code == 422
    assert client.get(url, params={"project_key": "IGM", "archive_until": "2999-01-01"}).status_code == 422
    assert client.get(url, params={"archive_until": "2026-09-30"}).status_code == 422


def test_archive_preview_reports_unknown_projects_and_failures(tmp_path: Path) -> None:
    def missing(project_key: str, archive_until: date) -> dict[str, int]:
        raise ProjectNotFoundError(project_key)

    def rejected(project_key: str, archive_until: date) -> dict[str, int]:
        raise RuntimeError("JIRA_TOKEN environment variable is not configured")

    params = {"project_key": "ABC", "archive_until": "2026-09-30"}
    url = "/api/archive-released-versions/preview"

    not_found = make_client(tmp_path, released_version_previewer=missing).get(url, params=params)
    assert not_found.status_code == 404
    assert not_found.json() == {"detail": "Jira project ABC was not found"}

    (tmp_path / "second").mkdir()
    failed = make_client(tmp_path / "second", released_version_previewer=rejected).get(
        url, params=params
    )
    assert failed.status_code == 503
    assert "JIRA_TOKEN" in failed.json()["detail"]


def test_semantic_versions_failures_explain_the_cause(tmp_path: Path) -> None:
    from requests.exceptions import ConnectionError as RequestsConnectionError

    def unreachable(status: str, project_key: str) -> list[str]:
        raise RequestsConnectionError("dns failure for secret-host")

    response = make_client(tmp_path, semantic_version_lister=unreachable).get("/api/semantic-versions")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Could not reach Jira. Check your network or VPN connection and try again."
    }


def test_renamed_pages_redirect_to_their_new_addresses(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    expected = {
        "/service-versions": "/list-service-versions-without-a-release-date",
        "/service-versions/": "/list-service-versions-without-a-release-date",
        "/release-semantic-version": "/release-a-deployment-version",
        "/release-a-semantic-version": "/release-a-deployment-version",
    }

    for old, new in expected.items():
        response = client.get(old, follow_redirects=False)
        assert response.status_code == 308, old
        assert response.headers["location"] == new, old
