import logging
import re
from threading import Lock
from typing import Iterator

from jira import JIRA

from .errors import UserFacingError
from .script_runner import stream_script_log
from .jira_credentials import create_jira_client as _jira_client

RELEASABLE_SUBTASK_TYPES = {"Sub-task", "Sub-bug"}
PARENT_ISSUE_TYPES = {"Story", "Enabler", "Bug", "Config Change"}
SEMANTIC_VERSION_PATTERN = re.compile(
    r"^(Deploy|Hotfix|Config)\."
    r"(ai-data|core-dev-1|core-dev-2|core-dev-3|core-dev-3-Payments|core-dev-3-Sport|"
    r"cust-onb-1|cust-onb-2|cust-onb-2-Integrations|cust-onb-2-Reporting|ps-dev-1|"
    r"ps-dev-2|prod-care|fe-dev|sw-arch)"
    r"\.\d{2}\.[1-4]\.\d+(\.\d+)?$",
    re.IGNORECASE,
)

log = logging.getLogger("service-version-report")
log.setLevel(logging.INFO)
log.propagate = False

report_lock = Lock()


def is_semantic_release_version(name: str) -> bool:
    return bool(SEMANTIC_VERSION_PATTERN.fullmatch(name))


def _report(jira: JIRA, project_key: str, release_version: str) -> None:
    if not is_semantic_release_version(release_version):
        raise UserFacingError(f"'{release_version}' is not a valid semantic release version.")

    jql = f'''
        project = {project_key}
        AND issuetype IN ("Story", "Enabler", "Bug", "Config Change")
        AND fixVersion = "{release_version}"
        ORDER BY key ASC
    '''

    log.info("Searching Jira for parents assigned to '%s'.", release_version)

    parent_issues = jira.search_issues(
        jql,
        maxResults=False,
        fields="key,issuetype,subtasks",
    )

    log.info("Found %d matching parent issue(s).", len(parent_issues))

    versions_without_release_date: dict[str, dict[str, str]] = {}

    for parent_issue in parent_issues:
        if parent_issue.fields.issuetype.name not in PARENT_ISSUE_TYPES:
            continue

        for subtask_reference in parent_issue.fields.subtasks or []:
            subtask = jira.issue(
                subtask_reference.key,
                fields="key,issuetype,fixVersions",
            )

            if subtask.fields.issuetype.name not in RELEASABLE_SUBTASK_TYPES:
                continue

            for version in subtask.fields.fixVersions or []:
                if is_semantic_release_version(version.name) or getattr(version, "releaseDate", None) is not None:
                    continue

                versions_without_release_date[str(version.id)] = {
                    "service_version": version.name,
                    "service_version_id": str(version.id),
                }

    results = sorted(
        versions_without_release_date.values(),
        key=lambda result: result["service_version"].casefold(),
    )

    log.info("Service versions without release date: %d", len(results))

    for result in results:
        log.info("Service version without release date: %s", result["service_version"])


def stream_service_versions_report(project_key: str, release_version: str) -> Iterator[str]:
    """Run the service version report, yielding its log as it is written."""
    return stream_script_log(
        log,
        report_lock,
        lambda: _report(_jira_client(), project_key, release_version),
        "Service version report failed.",
    )
