"""Release rules: configuration and pure decisions about Jira issues and versions.

Nothing here talks to Jira or logs, so every rule can be read and tested on its own.
"""

from jira.resources import Issue, Version

from .jira_rules import RELEASABLE_SUBTASK_TYPES, is_semantic_release_version

PROJECT_KEY = "IGM"

RELEASE_STATE_FIELD_ID = 14889
RELEASE_STATE_FIELD = f"customfield_{RELEASE_STATE_FIELD_ID}"

DONE_STATUS = "Done"

# Rejected / Canceled Sub-tasks and Sub-bugs are ignored completely.
NON_RELEASABLE_SUBTASK_STATUSES = {
    "Rejected",
    "Canceled",
}
NON_RELEASABLE_SUBTASK_TERMINAL_STATUSES = {
    DONE_STATUS,
    *NON_RELEASABLE_SUBTASK_STATUSES,
}

STATE_NOT_RELEASED = "Not Released"
STATE_PARTIALLY_RELEASED = "Partially Released"
STATE_FULLY_RELEASED = "Fully Released"

FULLY_RELEASED_PARENT_STATUSES = {
    "Story": "Accepted",
    "Enabler": "Accepted",
    "Bug": "Done",
    "Config Change": "Accepted",
}

SEMANTIC_RELEASE_ALLOWED_PARENT_STATUSES = {
    *FULLY_RELEASED_PARENT_STATUSES.values(),
    "Published",
}

DEPLOYMENT_PLAN_ISSUE_TYPE = "Deployment Plan"
TERMINAL_DEPLOYMENT_PLAN_STATUSES = {
    "Deployed on Prod",
    "Rolled Back",
    "Canceled/Not Happened",
    "Rejected",
}
TERMINAL_DEPLOYMENT_PLAN_STATUS_NAMES = {status.casefold() for status in TERMINAL_DEPLOYMENT_PLAN_STATUSES}


def is_semantic_version(version: Version) -> bool:
    """
    Return True when the Jira version matches our semantic release naming
    convention.
    """

    name = getattr(version, "name", None)

    if not name:
        return False

    return is_semantic_release_version(name)


def is_parent_semantic_version(version: Version) -> bool:
    """Return whether a parent Fix Version can define a semantic release target."""

    return is_semantic_version(version) or getattr(version, "name", "").casefold() == "unknown"


def version_status(version: Version) -> str:
    """Classify a Jira version as archived, released, or unreleased (archived wins)."""

    if bool(getattr(version, "archived", False)):
        return "archived"
    return "released" if bool(getattr(version, "released", False)) else "unreleased"


def get_release_state(issue: Issue) -> str | None:
    """
    Return the current value of the Release State custom field.
    """

    value = getattr(
        issue.fields,
        RELEASE_STATE_FIELD,
        None,
    )

    if value is None:
        return None

    # Select-list fields normally come back as an object with .value.
    if hasattr(value, "value"):
        return value.value

    return str(value)


def is_parent_ready_for_full_release(parent_issue: Issue) -> bool:
    """Return whether the parent has the required status for Fully Released."""

    return parent_issue.fields.status.name in {
        FULLY_RELEASED_PARENT_STATUSES.get(parent_issue.fields.issuetype.name),
        "Published",
    }


def unreleased_service_versions(issue: Issue) -> list[str]:
    """Return unreleased non-semantic Fix Versions assigned to an issue."""

    return [
        version.name
        for version in issue.fields.fixVersions or []
        if not is_semantic_version(version) and not bool(getattr(version, "released", False))
    ]


def has_released_service_version(issue: Issue) -> bool:
    """Return whether an issue has at least one released service Fix Version."""

    return any(
        not is_semantic_version(version) and bool(getattr(version, "released", False))
        for version in issue.fields.fixVersions or []
    )


def meets_full_release_prerequisites(parent_issue: Issue, all_subtasks: list[Issue]) -> bool:
    """Return whether every child satisfies the Done and service-version requirements."""

    releasable_subtasks = [
        subtask
        for subtask in all_subtasks
        if subtask.fields.issuetype.name in RELEASABLE_SUBTASK_TYPES
        and subtask.fields.status.name not in NON_RELEASABLE_SUBTASK_STATUSES
    ]
    non_releasable_subtasks = [
        subtask for subtask in all_subtasks if subtask.fields.issuetype.name not in RELEASABLE_SUBTASK_TYPES
    ]

    service_version_is_optional = parent_issue.fields.issuetype.name == "Config Change"

    return all(
        subtask.fields.status.name == DONE_STATUS
        and not unreleased_service_versions(subtask)
        and (service_version_is_optional or has_released_service_version(subtask))
        for subtask in releasable_subtasks
    ) and all(
        subtask.fields.status.name in NON_RELEASABLE_SUBTASK_TERMINAL_STATUSES for subtask in non_releasable_subtasks
    )


def find_parent_status_blockers(parent_issues: list[Issue]) -> list[tuple[str, str, str, str]]:
    """Return parents whose current status does not permit semantic version release."""

    blockers: list[tuple[str, str, str, str]] = []

    for parent_issue in parent_issues:
        required_status = FULLY_RELEASED_PARENT_STATUSES[parent_issue.fields.issuetype.name]
        current_status = parent_issue.fields.status.name

        if current_status not in SEMANTIC_RELEASE_ALLOWED_PARENT_STATUSES:
            blockers.append((parent_issue.key, parent_issue.fields.issuetype.name, current_status, required_status))

    return blockers


def find_deployment_plan_status_blockers(issues: list[Issue]) -> list[tuple[str, str]]:
    """Return target-version deployment plans that have not reached a terminal status."""

    return [
        (issue.key, issue.fields.status.name)
        for issue in issues
        if issue.fields.issuetype.name == DEPLOYMENT_PLAN_ISSUE_TYPE
        and issue.fields.status.name.casefold() not in TERMINAL_DEPLOYMENT_PLAN_STATUS_NAMES
    ]
