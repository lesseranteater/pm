"""Characterization tests for the release workflow.

A fake Jira runs several scenarios through `_release_version`. The normalized log and every
write made to Jira are compared with files in `golden/`. They pin today's behavior so the
module can be restructured safely. Regenerate deliberately with `UPDATE_GOLDEN=1 uv run pytest`.
"""

import logging
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app import release_semantic_version as workflow

GOLDEN = Path(__file__).parent / "golden"
STATE_FIELD = workflow.RELEASE_STATE_FIELD
TARGET = "Deploy.fe-dev.26.3.6"


class FakeVersion(SimpleNamespace):
    def update(self, **fields):
        self.writes.append(("version.update", self.name, fields))
        for key, value in fields.items():
            setattr(self, key, value)


class FakeIssue(SimpleNamespace):
    def update(self, fields):
        self.writes.append(("issue.update", self.key, fields))
        for key, value in fields.items():
            setattr(self.fields, key, SimpleNamespace(**value))


class FakeJira:
    def __init__(self, versions, issues, writes):
        self.versions = versions
        self.issues = {issue.key: issue for issue in issues}
        self.writes = writes
        self.reads: list[str] = []

    def project_versions(self, project_key):
        return self.versions

    def search_issues(self, jql, startAt, maxResults, fields):
        self.reads.append(f"search {jql}")
        found = [issue for issue in self.issues.values() if issue.carries_target]
        page = found[startAt : startAt + maxResults]
        return _Results(page, len(found))

    def issue(self, key, fields=None):
        self.reads.append(f"issue {key}")
        return self.issues[key]

    def transitions(self, issue):
        return [{"id": "31", "name": "Publish", "to": {"name": "Published"}}]

    def transition_issue(self, key, transition_id):
        self.writes.append(("transition", key, transition_id))
        self.issues[key].fields.status = SimpleNamespace(name="Published")

    def add_comment(self, key, text):
        self.writes.append(("comment", key, text))


class _Results(list):
    def __init__(self, items, total):
        super().__init__(items)
        self.total = total


def version(name, vid, released=False):
    return SimpleNamespace(name=name, id=vid, released=released)


def build(writes):
    target = FakeVersion(name=TARGET, id="10", released=False, writes=writes)
    service_done = version("svc-released", "20", released=True)
    service_open = version("svc-open", "21", released=False)
    sem = lambda: target  # one shared object, as a refetch from Jira would show  # noqa: E731

    def issue(key, kind, status, subtasks=(), fixes=(), state=None, carries=False):
        fields = SimpleNamespace(
            issuetype=SimpleNamespace(name=kind),
            status=SimpleNamespace(name=status),
            fixVersions=list(fixes),
            subtasks=[SimpleNamespace(key=sub.key) for sub in subtasks],
        )
        if state:
            setattr(fields, STATE_FIELD, SimpleNamespace(value=state))
        return FakeIssue(key=key, fields=fields, writes=writes, carries_target=carries)

    def sub(key, status, fixes, kind="Sub-task"):
        return issue(key, kind, status, fixes=fixes)

    subs = {
        "A-1": sub("A-1", "Done", [sem(), service_done]),
        "B-1": sub("B-1", "Done", [sem(), service_done]),
        "B-2": sub("B-2", "In Progress", []),
        "D-1": sub("D-1", "Done", [sem()]),
        "F-1": sub("F-1", "Done", [sem(), service_done]),
        "F-2": sub("F-2", "Rejected", []),
        "F-3": issue("F-3", "Task", "To Do"),
        "G-1": sub("G-1", "To Do", []),
    }
    parents = [
        issue("A", "Story", "Accepted", [subs["A-1"]], [sem()], carries=True),
        issue("B", "Story", "Accepted", [subs["B-1"], subs["B-2"]], [sem()], carries=True),
        issue("C", "Bug", "Done", [], [sem()], carries=True),
        issue("D", "Config Change", "Accepted", [subs["D-1"]], [sem()], carries=True),
        issue("F", "Story", "Accepted", [subs["F-1"], subs["F-2"], subs["F-3"]], [sem()], carries=True),
        issue("G", "Story", "Accepted", [subs["G-1"]], [sem()], carries=True),
        issue("H", "Bug", "Accepted", [], [sem()], carries=True),
        issue("PLAN", "Deployment Plan", "Planned", fixes=[sem()], carries=True),
    ]
    return target, service_open, parents, list(subs.values())


def status_blocked_build(writes):
    target, _service_open, parents, subs = build(writes)
    stuck = FakeIssue(
        key="X",
        fields=SimpleNamespace(
            issuetype=SimpleNamespace(name="Story"),
            status=SimpleNamespace(name="In Progress"),
            fixVersions=[target],
            subtasks=[],
        ),
        writes=writes,
        carries_target=True,
    )
    return target, parents + [stuck], subs


def blocked_build(writes):
    target, service_open, parents, subs = build(writes)
    blocked_sub = FakeIssue(
        key="E-1",
        fields=SimpleNamespace(
            issuetype=SimpleNamespace(name="Sub-task"),
            status=SimpleNamespace(name="Done"),
            fixVersions=[target, service_open],
            subtasks=[],
        ),
        writes=writes,
        carries_target=False,
    )
    blocked_parent = FakeIssue(
        key="E",
        fields=SimpleNamespace(
            issuetype=SimpleNamespace(name="Story"),
            status=SimpleNamespace(name="Accepted"),
            fixVersions=[target],
            subtasks=[SimpleNamespace(key="E-1")],
        ),
        writes=writes,
        carries_target=True,
    )
    return target, [blocked_parent, parents[0]], subs + [blocked_sub]


def normalized_log(run):
    log = logging.getLogger("release-state")
    records: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record):
            text = self.format(record)
            records.append(re.sub(r"0x[0-9a-f]+", "0x?", text))

    handler = Capture()
    handler.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
    log.addHandler(handler)
    try:
        run()
    finally:
        log.removeHandler(handler)
    return records


def render(records, writes, reads):
    lines = ["== log =="] + records + ["== writes =="] + [repr(item) for item in writes]
    lines += ["== reads =="] + reads
    return "\n".join(lines) + "\n"


def scenario(name, is_dry_run, blocked=False):
    writes: list = []
    if blocked == "status":
        target, parents, subs = status_blocked_build(writes)
        all_issues = parents + subs
    elif blocked:
        target, parents, subs = blocked_build(writes)
        all_issues = parents + subs
    else:
        target, _service_open, parents, subs = build(writes)
        all_issues = parents + subs
    jira = FakeJira([target], all_issues, writes)
    records = normalized_log(lambda: workflow._release_version(jira, TARGET, is_dry_run))
    actual = render(records, writes, jira.reads)
    path = GOLDEN / f"{name}.txt"
    if os.environ.get("UPDATE_GOLDEN"):
        path.write_text(actual, newline="\n")
    assert actual == path.read_text().replace("\r\n", "\n"), f"{name} changed"


@pytest.mark.parametrize(
    "name, dry_run, blocked",
    [
        ("release_dry_run", True, False),
        ("release_live", False, False),
        ("release_blocked_by_unreleased_service_version", False, True),
        ("release_blocked_by_parent_status", False, "status"),
    ],
)
def test_release_workflow_output_and_writes_are_unchanged(name, dry_run, blocked):
    scenario(name, dry_run, blocked)
