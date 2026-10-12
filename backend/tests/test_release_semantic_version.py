from backend.app import release_semantic_version


def test_release_service_captures_its_log(monkeypatch) -> None:
    monkeypatch.setattr(release_semantic_version, "create_jira_client", lambda: object())
    monkeypatch.setattr(
        release_semantic_version,
        "_release_version",
        lambda jira, version_name, is_dry_run: release_semantic_version.log.info(
            "Processed %s with dry_run=%s", version_name, is_dry_run
        ),
    )

    output = "".join(
        release_semantic_version.stream_release_semantic_version("Hotfix.ps-dev-1.26.4.3", True)
    )

    assert "Processed Hotfix.ps-dev-1.26.4.3 with dry_run=True" in output


def test_unknown_jira_project_raises_project_not_found() -> None:
    from jira.exceptions import JIRAError

    class FakeJira:
        def project_versions(self, project_key: str):
            raise JIRAError(status_code=404, text="No project could be found")

    try:
        release_semantic_version.list_semantic_versions(FakeJira(), "ABC", "unreleased")
    except release_semantic_version.ProjectNotFoundError as error:
        assert "ABC" in str(error)
    else:
        raise AssertionError("expected ProjectNotFoundError")


def test_semantic_versions_are_partitioned_by_status() -> None:
    from types import SimpleNamespace

    def version(name: str, released: bool, archived: bool) -> SimpleNamespace:
        return SimpleNamespace(name=name, released=released, archived=archived)

    class FakeJira:
        def project_versions(self, project_key: str):
            return [
                version("Deploy.fe-dev.26.4.3", released=False, archived=False),
                version("Deploy.fe-dev.26.3.6", released=True, archived=False),
                version("Deploy.fe-dev.26.2.1", released=True, archived=True),
                version("Deploy.fe-dev.26.2.2", released=False, archived=True),
                version("not-a-semantic-version", released=False, archived=False),
                version("UNKNOWN", released=False, archived=False),
                version("Deploy.fe-dev.26.5.1", released=False, archived=False),
                version("Deploy.unknown-service.26.4.1", released=False, archived=False),
                version("Deploy.fe-dev.26.4", released=False, archived=False),
                version("deploy.FE-DEV.26.4.4.1", released=False, archived=False),
            ]

    def names(status: str) -> list[str]:
        return release_semantic_version.list_semantic_versions(FakeJira(), "IGM", status)

    assert names("unreleased") == ["Deploy.fe-dev.26.4.3", "deploy.FE-DEV.26.4.4.1"]
    assert names("released") == ["Deploy.fe-dev.26.3.6"]
    assert names("archived") == ["Deploy.fe-dev.26.2.1", "Deploy.fe-dev.26.2.2"]


class _Page(list):
    def __init__(self, items, total):
        super().__init__(items)
        self.total = total


def test_search_all_issues_keeps_paging_when_jira_caps_the_page_size() -> None:
    issues = [f"IGM-{number}" for number in range(120)]

    class CappedJira:
        def search_issues(self, jql, startAt, maxResults, fields):
            return _Page(issues[startAt : startAt + 50], total=len(issues))

    assert release_semantic_version.search_all_issues(CappedJira(), "project = IGM", "key") == issues


def test_search_all_issues_stops_on_an_empty_page_without_a_total() -> None:
    pages = [["IGM-1", "IGM-2"], []]

    class PlainJira:
        def search_issues(self, jql, startAt, maxResults, fields):
            return pages.pop(0)

    assert release_semantic_version.search_all_issues(PlainJira(), "project = IGM", "key") == ["IGM-1", "IGM-2"]


def test_partial_release_comment_does_not_require_a_service_version_for_config_changes() -> None:
    from types import SimpleNamespace

    def subtask(key: str, status: str, versions: list):
        return SimpleNamespace(
            key=key,
            fields=SimpleNamespace(
                issuetype=SimpleNamespace(name="Sub-task"),
                status=SimpleNamespace(name=status),
                fixVersions=versions,
            ),
        )

    semantic = SimpleNamespace(name="Deploy.fe-dev.26.3.6", id="1", released=True)
    done = subtask("IGM-2", "Done", [semantic])
    open_ = subtask("IGM-3", "In Progress", [])
    comments: list[str] = []
    jira = SimpleNamespace(add_comment=lambda key, text: comments.append(text))

    for issue_type, expect_service_reason in (("Config Change", False), ("Story", True)):
        comments.clear()
        parent = SimpleNamespace(key="IGM-1", fields=SimpleNamespace(issuetype=SimpleNamespace(name=issue_type)))
        release_semantic_version.add_partial_release_comment(
            jira, parent, [done, open_], [done, open_], False, None, False
        )
        assert "IGM-3 is in status 'In Progress'" in comments[0]
        assert ("IGM-2 has no released service Fix Version" in comments[0]) is expect_service_reason


def test_blocker_checks_reuse_loaded_subtasks_without_calling_jira() -> None:
    from types import SimpleNamespace

    target = SimpleNamespace(id="10")
    subtask = SimpleNamespace(
        key="IGM-2",
        fields=SimpleNamespace(
            issuetype=SimpleNamespace(name="Sub-task"),
            status=SimpleNamespace(name="In Progress"),
            fixVersions=[SimpleNamespace(id="10", name="Deploy.fe-dev.26.3.6", released=False)],
        ),
    )
    parent = SimpleNamespace(key="IGM-1")
    loaded = {"IGM-1": [subtask]}

    not_done = release_semantic_version.find_not_done_target_version_blockers(None, [parent], target, loaded)
    service = release_semantic_version.find_unreleased_service_version_blockers(None, [parent], loaded)

    assert not_done == [("IGM-1", "IGM-2", "In Progress")]
    assert service == []
