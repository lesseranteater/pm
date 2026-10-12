import sys
import threading
from types import SimpleNamespace

from jira.exceptions import JIRAError

from backend.app import release_check


def issue(key, versions=(), parent=None, subtasks=(), links=()):
    return SimpleNamespace(key=key, fields=SimpleNamespace(
        summary=f"Summary {key}", issuetype=SimpleNamespace(name="Story"),
        fixVersions=[SimpleNamespace(name=name) for name in versions],
        parent=SimpleNamespace(key=parent) if parent else None,
        subtasks=[SimpleNamespace(key=child) for child in subtasks],
        issuelinks=[SimpleNamespace(outwardIssue=SimpleNamespace(key=linked)) for linked in links],
    ))


class ReadOnlyJira:
    def __init__(self, issues):
        self.issues = issues
        self.requests = []

    def issue(self, key, fields):
        self.requests.append(key)
        result = self.issues[key]
        if isinstance(result, Exception):
            raise result
        return result


def run(monkeypatch, issues):
    jira = ReadOnlyJira(issues)
    monkeypatch.setattr(release_check, "create_jira_client", lambda: jira)
    return "".join(release_check.stream_release_check("IGM-1")), jira


def test_reports_issue_parent_and_subtask_mismatches_without_modifying_jira(monkeypatch):
    issues = {
        "IGM-1": issue("IGM-1", ["expected"], links=["IGM-2", "IGM-2", "IGM-3", "IGM-4"]),
        "IGM-2": issue("IGM-2", ["expected", "extra-issue"], parent="IGM-5", subtasks=["IGM-6"]),
        "IGM-3": issue("IGM-3", ["expected"]),
        "IGM-4": issue("IGM-4"),
        "IGM-5": issue("IGM-5", ["extra-parent"]),
        "IGM-6": issue("IGM-6", ["extra-child"]),
    }
    output, jira = run(monkeypatch, issues)
    assert "Total linked issues checked: 3" in output
    assert "Linked issue mismatching version(s): extra-issue" in output
    assert "Parent IGM-5 mismatching version(s): extra-parent" in output
    assert "IGM-6: extra-child" in output
    assert "Linked issues with mismatches: 1" in output
    assert "Summary IGM-3" not in output and "Summary IGM-4" not in output
    assert jira.requests.count("IGM-2") == 1


def test_missing_plan_and_plan_without_versions_are_reported(monkeypatch):
    output, _ = run(monkeypatch, {"IGM-1": JIRAError(status_code=404, text="missing")})
    assert "| ERROR | Release Plan IGM-1 could not be loaded" in output
    output, jira = run(monkeypatch, {"IGM-1": issue("IGM-1", links=["IGM-2"])})
    assert "does not have any Fix Version/s" in output
    assert jira.requests == ["IGM-1"]


def test_unavailable_related_issues_are_logged_and_check_continues(monkeypatch):
    output, _ = run(monkeypatch, {
        "IGM-1": issue("IGM-1", ["expected"], links=["IGM-2", "IGM-3"]),
        "IGM-2": JIRAError(status_code=403, text="forbidden"),
        "IGM-3": issue("IGM-3", ["extra"], parent="IGM-4", subtasks=["IGM-5"]),
        "IGM-4": JIRAError(status_code=404, text="missing"),
        "IGM-5": JIRAError(status_code=404, text="missing"),
    })
    assert "Could not load linked issue IGM-2" in output
    assert "Could not load parent issue IGM-4" in output
    assert "Could not load subtask IGM-5" in output
    assert "CHECK COMPLETE" in output


def test_log_streams_before_check_finishes_and_stdout_is_not_replaced(monkeypatch):
    started = threading.Event()
    finish = threading.Event()
    stdout = sys.stdout

    class WaitingJira(ReadOnlyJira):
        def issue(self, key, fields):
            if key == "IGM-2":
                assert sys.stdout is stdout
                started.set()
                assert finish.wait(timeout=5)
            return super().issue(key, fields)

    jira = WaitingJira({
        "IGM-1": issue("IGM-1", ["expected"], links=["IGM-2"]),
        "IGM-2": issue("IGM-2", ["expected"]),
    })
    monkeypatch.setattr(release_check, "create_jira_client", lambda: jira)
    stream = release_check.stream_release_check("IGM-1")
    try:
        assert "Finding Fix Version mismatches" in next(stream)
        assert started.wait(timeout=5)
        assert sys.stdout is stdout
    finally:
        finish.set()
    assert "CHECK COMPLETE" in "".join(stream)


def test_a_parent_shared_by_several_linked_issues_is_loaded_once(monkeypatch):
    issues = {
        "IGM-1": issue("IGM-1", ["expected"], links=["IGM-2", "IGM-3"]),
        "IGM-2": issue("IGM-2", ["expected"], parent="IGM-5"),
        "IGM-3": issue("IGM-3", ["expected"], parent="IGM-5"),
        "IGM-5": issue("IGM-5", ["extra-parent"]),
    }
    output, jira = run(monkeypatch, issues)
    assert jira.requests.count("IGM-5") == 1
    assert output.count("Parent IGM-5 mismatching version(s): extra-parent") == 2
