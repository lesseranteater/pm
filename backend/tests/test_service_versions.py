from types import SimpleNamespace

from backend.app import service_versions


def issue(issue_type: str, subtasks=None, fix_versions=None):
    return SimpleNamespace(
        fields=SimpleNamespace(
            issuetype=SimpleNamespace(name=issue_type),
            subtasks=subtasks,
            fixVersions=fix_versions,
        )
    )


def version(version_id: str, name: str, release_date=None):
    return SimpleNamespace(id=version_id, name=name, releaseDate=release_date)


def test_report_filters_released_and_semantic_versions(monkeypatch) -> None:
    subtask_reference = SimpleNamespace(key="IGM-2")
    client = SimpleNamespace(
        search_issues=lambda *args, **kwargs: [issue("Story", [subtask_reference])],
        issue=lambda *args, **kwargs: issue(
            "Sub-task",
            fix_versions=[
                version("2", "ignore-this.bo.26.4.1"),
                version("1", "ignore-this.be.26.4.1"),
                version("1", "ignore-this.be.26.4.1"),
                version("3", "Deploy.ai-data.26.4.1"),
                version("4", "released-service.26.4.1", "2026-10-08"),
            ],
        ),
    )
    monkeypatch.setattr(service_versions, "_jira_client", lambda: client)

    report = service_versions.get_service_versions_without_release_date()

    assert report == [
        service_versions.ServiceVersion(id="1", name="ignore-this.be.26.4.1"),
        service_versions.ServiceVersion(id="2", name="ignore-this.bo.26.4.1"),
    ]
