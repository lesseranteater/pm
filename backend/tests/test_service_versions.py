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


def make_client(parents, subtask):
    requested_jql: list[str] = []

    def search_issues(jql, **kwargs):
        requested_jql.append(jql)
        return parents

    client = SimpleNamespace(search_issues=search_issues, issue=lambda *args, **kwargs: subtask)
    return client, requested_jql


def messages(output: str) -> list[str]:
    return [line.split(" | ", 2)[2] for line in output.splitlines()]


def test_report_logs_service_versions_without_release_date(monkeypatch) -> None:
    client, requested_jql = make_client(
        [issue("Story", [SimpleNamespace(key="IGM-2")])],
        issue(
            "Sub-task",
            fix_versions=[
                version("2", "ignore-this.bo.26.4.1"),
                version("1", "Ignore-this.be.26.4.1"),
                version("1", "Ignore-this.be.26.4.1"),
                version("3", "Deploy.ai-data.26.4.1"),
                version("4", "released-service.26.4.1", "2026-10-08"),
            ],
        ),
    )
    monkeypatch.setattr(service_versions, "_jira_client", lambda: client)

    output = service_versions.report_service_versions_without_release_date(
        "IGM", "Deploy.ai-data.26.4.1"
    )

    assert messages(output) == [
        "Searching Jira for parents assigned to 'Deploy.ai-data.26.4.1'.",
        "Found 1 matching parent issue(s).",
        "Service versions without release date: 2",
        "Service version without release date: Ignore-this.be.26.4.1",
        "Service version without release date: ignore-this.bo.26.4.1",
    ]
    assert "| INFO |" in output
    assert "project = IGM" in requested_jql[0]
    assert 'fixVersion = "Deploy.ai-data.26.4.1"' in requested_jql[0]


def test_report_ignores_non_releasable_subtasks_and_parents(monkeypatch) -> None:
    client, _ = make_client(
        [issue("Epic", [SimpleNamespace(key="IGM-1")]), issue("Story", [SimpleNamespace(key="IGM-2")])],
        issue("Task", fix_versions=[version("1", "service.26.4.1")]),
    )
    monkeypatch.setattr(service_versions, "_jira_client", lambda: client)

    output = service_versions.report_service_versions_without_release_date(
        "IGM", "Deploy.ai-data.26.4.1"
    )

    assert "Service versions without release date: 0" in messages(output)


def test_report_logs_failures_instead_of_raising(monkeypatch) -> None:
    def no_token():
        raise RuntimeError("JIRA_TOKEN environment variable is not configured")

    monkeypatch.setattr(service_versions, "_jira_client", no_token)

    output = service_versions.report_service_versions_without_release_date(
        "IGM", "Deploy.ai-data.26.4.1"
    )

    assert "| ERROR | Service version report failed." in output
    assert "JIRA_TOKEN environment variable is not configured" in output


def test_report_rejects_a_non_semantic_release_version(monkeypatch) -> None:
    monkeypatch.setattr(service_versions, "_jira_client", lambda: SimpleNamespace())

    output = service_versions.report_service_versions_without_release_date("IGM", "not-a-release")

    assert "'not-a-release' is not a valid semantic release version." in output
