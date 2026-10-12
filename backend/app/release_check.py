"""Read-only Deployment Plan Fix Version checks with a streaming Script Log."""

from __future__ import annotations

import logging
from threading import Lock
from typing import Iterator

from jira import JIRA
from jira.exceptions import JIRAError
from jira.resources import Issue

from .errors import explain_exception
from .jira_credentials import create_jira_client
from .script_runner import stream_script_log

log = logging.getLogger("release-check")
log.setLevel(logging.INFO)
log.propagate = False
release_check_lock = Lock()


def get_fix_version_names(issue: Issue | None) -> set[str]:
    """Return the names of all Fix Versions assigned to an issue."""
    if issue is None:
        return set()
    return {
        version.name
        for version in getattr(issue.fields, "fixVersions", None) or []
        if getattr(version, "name", None)
    }


def get_linked_issue_keys(issue: Issue) -> list[str]:
    """Return unique inward and outward linked issue keys in stable order."""
    keys: set[str] = set()
    for link in getattr(issue.fields, "issuelinks", None) or []:
        for direction in ("outwardIssue", "inwardIssue"):
            linked_issue = getattr(link, direction, None)
            if linked_issue is not None:
                keys.add(linked_issue.key)
    return sorted(keys)


def get_parent_issue(jira: JIRA, issue: Issue, cache: dict[str, Issue | None] | None = None) -> Issue | None:
    """Load an issue's parent. A cache shares one lookup between linked issues with the same parent."""
    parent = getattr(issue.fields, "parent", None)
    if parent is None:
        return None
    if cache is not None and parent.key in cache:
        return cache[parent.key]
    try:
        loaded = jira.issue(parent.key, fields="summary,issuetype,fixVersions,parent,subtasks")
    except JIRAError as error:
        log.warning("Could not load parent issue %s: %s", parent.key, explain_exception(error))
        loaded = None
    if cache is not None:
        cache[parent.key] = loaded
    return loaded


def get_subtask_issues(jira: JIRA, issue: Issue) -> list[Issue]:
    subtasks = []
    for reference in getattr(issue.fields, "subtasks", None) or []:
        try:
            subtasks.append(jira.issue(reference.key, fields="summary,issuetype,fixVersions,parent"))
        except JIRAError as error:
            log.warning("Could not load subtask %s: %s", reference.key, explain_exception(error))
    return subtasks


def find_mismatching_version_sources(jira: JIRA, release_plan_key: str) -> None:
    """Report extra Fix Versions on linked issues, their parents and direct subtasks.

    Issues without Fix Versions are ignored, as in the original Release Check.
    """
    try:
        plan = jira.issue(release_plan_key, fields="summary,issuetype,fixVersions,issuelinks")
    except JIRAError as error:
        log.error("Release Plan %s could not be loaded: %s", release_plan_key, explain_exception(error))
        return

    expected = get_fix_version_names(plan)
    if not expected:
        log.warning("Release Plan %s does not have any Fix Version/s.", release_plan_key)
        return

    log.info("=== Finding Fix Version mismatches for Release Plan %s ===", release_plan_key)
    log.info("Expected Release Plan version(s): %s", ", ".join(sorted(expected)))
    keys = get_linked_issue_keys(plan)
    log.info("Total linked issues checked: %d", len(keys))
    mismatches_found = 0
    parents: dict[str, Issue | None] = {}

    for key in keys:
        try:
            issue = jira.issue(key, fields="summary,issuetype,fixVersions,parent,subtasks")
        except JIRAError as error:
            log.warning("Could not load linked issue %s: %s", key, explain_exception(error))
            continue

        issue_versions = get_fix_version_names(issue) - expected
        parent = get_parent_issue(jira, issue, parents)
        parent_versions = get_fix_version_names(parent) - expected
        mismatching_subtasks = []
        for subtask in get_subtask_issues(jira, issue):
            extra = get_fix_version_names(subtask) - expected
            if extra:
                mismatching_subtasks.append((subtask.key, extra))

        if not (issue_versions or parent_versions or mismatching_subtasks):
            continue
        mismatches_found += 1
        log.info("%s", "-" * 80)
        log.info(
            "%s | %s | %s", issue.key,
            getattr(issue.fields.issuetype, "name", "Unknown"),
            getattr(issue.fields, "summary", ""),
        )
        if issue_versions:
            log.info("  Linked issue mismatching version(s): %s", ", ".join(sorted(issue_versions)))
        if parent_versions:
            log.info("  Parent %s mismatching version(s): %s", parent.key, ", ".join(sorted(parent_versions)))
        if mismatching_subtasks:
            log.info("  Subtasks with mismatching version(s):")
            for subtask_key, versions in mismatching_subtasks:
                log.info("    %s: %s", subtask_key, ", ".join(sorted(versions)))

    log.info("=== CHECK COMPLETE | Linked issues with mismatches: %d ===", mismatches_found)


def stream_release_check(deployment_plan_key: str) -> Iterator[str]:
    """Check a deployment plan using the signed-in user's request-scoped Jira token."""
    return stream_script_log(
        log, release_check_lock,
        lambda: find_mismatching_version_sources(create_jira_client(), deployment_plan_key),
        "Release check failed.",
    )
