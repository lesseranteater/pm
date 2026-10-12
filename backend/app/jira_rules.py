"""Jira naming and issue-type rules shared by every tool, plus safe JQL building."""

import re

from .errors import UserFacingError

RELEASABLE_SUBTASK_TYPES = {"Sub-task", "Sub-bug"}
PARENT_ISSUE_TYPES = {"Story", "Enabler", "Bug", "Config Change"}

PROJECT_KEY_REGEX = r"^[A-Z][A-Z0-9_]{1,9}$"
PROJECT_KEY_PATTERN = re.compile(PROJECT_KEY_REGEX)
SEMANTIC_VERSION_PATTERN = re.compile(
    r"^(Deploy|Hotfix|Config)\."
    r"(ai-data|core-dev-1|core-dev-2|core-dev-3|core-dev-3-Payments|core-dev-3-Sport|"
    r"cust-onb-1|cust-onb-2|cust-onb-2-Integrations|cust-onb-2-Reporting|ps-dev-1|"
    r"ps-dev-2|prod-care|fe-dev|sw-arch)"
    r"\.\d{2}\.[1-4]\.\d+(\.\d+)?$",
    re.IGNORECASE,
)


def is_semantic_release_version(name: str) -> bool:
    return bool(SEMANTIC_VERSION_PATTERN.fullmatch(name))


def jql_project(project_key: str) -> str:
    """Return ``project_key`` for use in JQL, refusing anything that is not a plain project key."""
    if not PROJECT_KEY_PATTERN.fullmatch(project_key):
        raise UserFacingError(f"'{project_key}' is not a valid Jira project key.")
    return project_key


def jql_quote(value: str) -> str:
    """Return ``value`` as a double-quoted JQL string with quotes and backslashes escaped."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
