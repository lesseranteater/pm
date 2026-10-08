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

    output = release_semantic_version.release_semantic_version("Hotfix.ps-dev-1.26.4.3", True)

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
