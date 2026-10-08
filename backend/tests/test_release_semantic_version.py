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
