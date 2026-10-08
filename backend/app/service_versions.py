import io
import logging
import os
import re
from threading import Lock

from dotenv import load_dotenv
from jira import JIRA

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


def _jira_client() -> JIRA:
    load_dotenv()
    token = os.getenv("JIRA_TOKEN", "")
    if not token:
        raise RuntimeError("JIRA_TOKEN environment variable is not configured")
    return JIRA(server=os.getenv("JIRA_URL", "https://jira.egt-digital.com"), token_auth=token)


def is_semantic_release_version(name: str) -> bool:
    return bool(SEMANTIC_VERSION_PATTERN.fullmatch(name))


def _get_release_date(version):
    """Return the version release date, or None when none has been configured."""
    return getattr(version, "releaseDate", None)


def _report(jira: JIRA, project_key: str, release_version: str) -> None:
    if not is_semantic_release_version(release_version):
        raise RuntimeError(f"'{release_version}' is not a valid semantic release version.")

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
                if is_semantic_release_version(version.name) or _get_release_date(version) is not None:
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


def report_service_versions_without_release_date(project_key: str, release_version: str) -> str:
    """Run the service version report and return its operational log."""
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    # The logger is shared, so serialize runs to keep each request's log separate.
    with report_lock:
        log.addHandler(handler)
        try:
            _report(_jira_client(), project_key, release_version)
        except Exception:
            log.exception("Service version report failed.")
        finally:
            log.removeHandler(handler)
    return output.getvalue()
