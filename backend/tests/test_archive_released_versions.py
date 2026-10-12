from datetime import date
from types import SimpleNamespace

from jira.exceptions import JIRAError

from backend.app import archive_released_versions

TODAY = date(2026, 10, 8)


def version(name: str, released: bool, archived: bool, release_date: str | None, id: str = "1"):
    return SimpleNamespace(
        id=id, name=name, released=released, archived=archived, releaseDate=release_date, raw={}
    )


VERSIONS = [
    version("old-released", True, False, "2026-01-15", id="1"),
    version("future-released", True, False, "2026-12-01", id="2"),
    version("same-day", True, False, "2026-10-08", id="3"),
    version("already-archived", True, True, "2026-01-15", id="4"),
    version("unreleased", False, False, "2026-01-15", id="5"),
    version("no-date", True, False, None, id="6"),
    version("bad-date", True, False, "15/01/2026", id="7"),
]


class FakeJira:
    def __init__(self, versions=VERSIONS, error: Exception | None = None) -> None:
        self._versions = versions
        self._error = error

    def project_versions(self, project_key: str):
        if self._error:
            raise self._error
        return self._versions


def test_only_released_unarchived_versions_up_to_the_date_are_candidates() -> None:
    names = [v.name for v in archive_released_versions.find_versions_to_archive(VERSIONS, TODAY)]

    # The chosen date is inclusive; later, archived, unreleased and undated versions are skipped.
    assert names == ["old-released", "same-day"]


def test_an_earlier_date_selects_fewer_versions() -> None:
    names = [
        v.name
        for v in archive_released_versions.find_versions_to_archive(VERSIONS, date(2026, 10, 7))
    ]

    assert names == ["old-released"]


def test_raw_json_is_used_when_attributes_are_missing() -> None:
    bare = SimpleNamespace(id="9", name="raw-only", raw={"released": True, "releaseDate": "2026-02-01"})

    assert archive_released_versions.find_versions_to_archive([bare], TODAY) == [bare]


def test_versions_are_grouped_into_sorted_semantic_and_service_sections() -> None:
    mixed = [
        version("sport-fe-1.36.0", True, False, "2026-01-01"),
        version("Hotfix.ps-dev-1.26.4.2", True, False, "2026-01-01"),
        version("Config.core-dev-1.26.4.4", True, False, "2026-01-01"),
        version("Platform-fe-2.83.0", True, False, "2026-01-01"),
        version("deploy.fe-dev.26.3.6", True, False, "2026-01-01"),
        version("ews-api-1.2.0", True, False, "2026-01-01"),
    ]

    semantic, service = archive_released_versions.group_versions(mixed)

    assert [v.name for v in semantic] == [
        "Config.core-dev-1.26.4.4",
        "deploy.fe-dev.26.3.6",
        "Hotfix.ps-dev-1.26.4.2",
    ]
    assert [v.name for v in service] == ["ews-api-1.2.0", "Platform-fe-2.83.0", "sport-fe-1.36.0"]


def test_dry_run_log_has_semantic_and_service_sections(monkeypatch) -> None:
    mixed = [
        version("sport-fe-1.36.0", True, False, "2026-01-01", id="1"),
        version("Deploy.fe-dev.26.3.6", True, False, "2026-01-02", id="2"),
        version("Config.core-dev-1.26.4.4", True, False, "2026-01-03", id="3"),
        version("ews-api-1.2.0", True, False, "2026-01-04", id="4"),
    ]

    output = run(monkeypatch, True, FakeJira(mixed), [])

    lines = [line.split(" | ", 2)[2] for line in output.splitlines() if " | " in line]
    section = lines.index("Semantic (2):")
    assert lines[section : section + 7] == [
        "Semantic (2):",
        " - Config.core-dev-1.26.4.4 (id=3) releaseDate=2026-01-03",
        " - Deploy.fe-dev.26.3.6 (id=2) releaseDate=2026-01-02",
        "Service (2):",
        " - ews-api-1.2.0 (id=4) releaseDate=2026-01-04",
        " - sport-fe-1.36.0 (id=1) releaseDate=2026-01-01",
        "Dry run: no changes were made.",
    ]


def test_real_run_archives_semantic_versions_before_service_versions(monkeypatch) -> None:
    mixed = [
        version("alpha-service", True, False, "2026-01-01", id="1"),
        version("Deploy.fe-dev.26.3.6", True, False, "2026-01-02", id="2"),
    ]
    archived: list[str] = []

    run(monkeypatch, False, FakeJira(mixed), archived)

    assert archived == ["Deploy.fe-dev.26.3.6", "alpha-service"]


def run(monkeypatch, is_dry_run: bool, jira: FakeJira, archived: list[str], fail: set[str] = frozenset()) -> str:
    def fake_archive(v):
        if v.name in fail:
            raise JIRAError("nope")
        archived.append(v.name)

    monkeypatch.setattr(archive_released_versions, "create_jira_client", lambda: jira)
    monkeypatch.setattr(archive_released_versions, "archive_version", fake_archive)
    return "".join(archive_released_versions.stream_archive_released_versions("IGM", is_dry_run, TODAY))


def test_dry_run_lists_candidates_without_archiving(monkeypatch) -> None:
    archived: list[str] = []

    output = run(monkeypatch, True, FakeJira(), archived)

    assert archived == []
    assert "DRY RUN enabled" in output
    assert "Archiving released versions with a release date on or before 2026-10-08." in output
    assert "Found 2 version(s) to archive:" in output
    assert "old-released" in output
    assert "Dry run: no changes were made." in output


def test_real_run_archives_candidates(monkeypatch) -> None:
    archived: list[str] = []

    output = run(monkeypatch, False, FakeJira(), archived)

    assert archived == ["old-released", "same-day"]
    assert "Archiving old-released (id=1)..." in output
    assert "Archived 2 of 2 version(s)." in output


def test_failed_archive_is_logged_as_a_warning_and_the_run_continues(monkeypatch) -> None:
    versions = [
        version("first", True, False, "2026-01-01", id="1"),
        version("second", True, False, "2026-01-02", id="2"),
    ]
    archived: list[str] = []

    output = run(monkeypatch, False, FakeJira(versions), archived, fail={"first"})

    assert archived == ["second"]
    assert "| WARNING | Failed to archive first (id=1)" in output
    assert "| ERROR | Archived only 1 of 2 version(s)" in output


def test_every_archive_failing_is_reported_as_an_error(monkeypatch) -> None:
    versions = [version("only", True, False, "2026-01-01", id="1")]

    output = run(monkeypatch, False, FakeJira(versions), [], fail={"only"})

    assert "| ERROR | Archived only 0 of 1 version(s)" in output


def test_nothing_to_archive_is_reported(monkeypatch) -> None:
    output = run(monkeypatch, False, FakeJira([]), [])

    assert "No released versions on or before 2026-10-08 to archive." in output


def test_unknown_project_is_logged_instead_of_raised(monkeypatch) -> None:
    jira = FakeJira(error=JIRAError(status_code=404, text="missing"))

    output = run(monkeypatch, True, jira, [])

    assert "| ERROR | Archive processing failed." in output
    assert "Jira project 'IGM' was not found." in output


def test_preview_counts_the_versions_without_changing_anything(monkeypatch) -> None:
    mixed = [
        version("Deploy.fe-dev.26.3.6", True, False, "2026-01-02", id="1"),
        version("Config.core-dev-1.26.4.4", True, False, "2026-01-03", id="2"),
        version("sport-fe-1.36.0", True, False, "2026-01-04", id="3"),
        version("too-new", True, False, "2026-12-01", id="4"),
    ]
    archived: list[str] = []
    monkeypatch.setattr(archive_released_versions, "create_jira_client", lambda: FakeJira(mixed))
    monkeypatch.setattr(archive_released_versions, "archive_version", lambda _version: archived.append("x"))

    result = archive_released_versions.preview_archive("IGM", TODAY)

    assert result == {"count": 3, "semantic": 2, "service": 1}
    assert archived == []


def test_preview_reports_an_unknown_project(monkeypatch) -> None:
    import pytest

    jira = FakeJira(error=JIRAError(status_code=404, text="missing"))
    monkeypatch.setattr(archive_released_versions, "create_jira_client", lambda: jira)

    with pytest.raises(archive_released_versions.ProjectNotFoundError):
        archive_released_versions.preview_archive("ABC", TODAY)


def test_named_selection_ignores_dates_and_explains_exclusions():
    selected, excluded = archive_released_versions.select_named_versions(
        VERSIONS, ["future-released", "no-date", "old-released", "old-released", "unreleased", "already-archived", "missing"],
    )
    assert [item.name for item in selected] == ["future-released", "no-date", "old-released"]
    assert excluded == {"unknown": ["missing"], "unreleased": ["unreleased"], "already_archived": ["already-archived"]}


def test_named_archive_dry_run_and_live_only_touch_listed_released_versions(monkeypatch):
    archived = []
    monkeypatch.setattr(archive_released_versions, "create_jira_client", lambda: FakeJira())
    monkeypatch.setattr(archive_released_versions, "archive_version", lambda item: archived.append(item.name))
    names = ["no-date", "future-released", "unreleased", "already-archived", "no-date"]
    output = "".join(archive_released_versions.stream_archive_versions("IGM", True, names))
    assert archived == []
    assert "Found 2 version(s)" in output
    assert "Skipping unreleased" in output and "Skipping already archived" in output
    "".join(archive_released_versions.stream_archive_versions("IGM", False, names))
    assert archived == ["future-released", "no-date"]


def test_unknown_name_blocks_all_changes_even_if_other_names_are_valid(monkeypatch):
    archived = []
    monkeypatch.setattr(archive_released_versions, "create_jira_client", lambda: FakeJira())
    monkeypatch.setattr(archive_released_versions, "archive_version", lambda item: archived.append(item.name))
    output = "".join(archive_released_versions.stream_archive_versions("IGM", False, ["old-released", "missing"]))
    assert archived == []
    assert "Unknown version names: missing" in output


def test_named_preview_is_read_only(monkeypatch):
    monkeypatch.setattr(archive_released_versions, "create_jira_client", lambda: FakeJira())
    result = archive_released_versions.preview_archive_versions("IGM", ["no-date", "unreleased", "missing", "already-archived"])
    assert result == {"count": 1, "semantic": 0, "service": 1, "eligible": ["no-date"], "unknown": ["missing"], "unreleased": ["unreleased"], "already_archived": ["already-archived"]}


def test_archive_version_uses_the_public_update_call() -> None:
    calls: list[dict] = []
    item = SimpleNamespace(update=lambda **fields: calls.append(fields))

    archive_released_versions.archive_version(item)

    assert calls == [{"archived": True}]


def test_a_forbidden_archive_is_explained_and_the_run_continues(monkeypatch) -> None:
    versions = [
        version("first", True, False, "2026-01-01", id="1"),
        version("second", True, False, "2026-01-02", id="2"),
    ]
    archived: list[str] = []

    def update(name):
        def run(**fields):
            if name == "first":
                raise JIRAError(status_code=403, url="https://jira.internal/x", text="no permission")
            archived.append(name)

        return run

    for item in versions:
        item.update = update(item.name)
    monkeypatch.setattr(archive_released_versions, "create_jira_client", lambda: FakeJira(versions))

    output = "".join(archive_released_versions.stream_archive_released_versions("IGM", False, TODAY))

    assert archived == ["second"]
    assert "Failed to archive first (id=1): Jira denied access (HTTP 403)" in output
    assert "jira.internal" not in output
    assert "| ERROR | Archived only 1 of 2 version(s)" in output
