import re
import os
import logging

from dotenv import load_dotenv
from jira import JIRA

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_KEY = "IGM"


# ---------------------------------------------------------------------------
# Release model
# ---------------------------------------------------------------------------

RELEASABLE_SUBTASK_TYPES = {
    "Sub-task",
    "Sub-bug",
}

PARENT_ISSUE_TYPES = {
    "Story",
    "Enabler",
    "Bug",
    "Config Change",
}


SEMANTIC_VERSION_PATTERN = re.compile(
    r"^(Deploy|Hotfix|Config)\."
    r"(ai-data|"
    r"core-dev-1|"
    r"core-dev-2|"
    r"core-dev-3|"
    r"core-dev-3-Payments|"
    r"core-dev-3-Sport|"
    r"cust-onb-1|"
    r"cust-onb-2|"
    r"cust-onb-2-Integrations|"
    r"cust-onb-2-Reporting|"
    r"ps-dev-1|"
    r"ps-dev-2|"
    r"prod-care|"
    r"fe-dev|"
    r"sw-arch)"
    r"\.\d{2}\.[1-4]\.\d+(\.\d+)?$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

log = logging.getLogger("service-version-report")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def create_jira_client() -> JIRA:
    """Create a Jira client using the shared environment-based token setup."""

    load_dotenv()

    jira_url = os.getenv("JIRA_URL", "https://jira.egt-digital.com")
    jira_token = os.getenv("JIRA_TOKEN", "")

    if not jira_token:
        raise RuntimeError(
            "JIRA_TOKEN environment variable is not configured. "
            "Create a .env file and add your Jira Personal Access Token."
        )

    return JIRA(server=jira_url, token_auth=jira_token)


def is_semantic_version(version_name: str) -> bool:
    """Return True if the Jira version is a semantic release version."""
    return bool(SEMANTIC_VERSION_PATTERN.fullmatch(version_name))


def get_release_date(version):
    """
    Return the version release date, or None when no release date
    has been configured.
    """
    return getattr(version, "releaseDate", None)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    semantic_version_name = "Deploy.ai-data.26.4.1"

    if not is_semantic_version(semantic_version_name):
        raise RuntimeError(f"'{semantic_version_name}' is not a valid semantic release version.")

    jira = create_jira_client()

    jql = f"""
        project = {PROJECT_KEY}
        AND issuetype IN ("Story", "Enabler", "Bug", "Config Change")
        AND fixVersion = "{semantic_version_name}"
        ORDER BY key ASC
    """

    log.info("Searching Jira for parents assigned to '%s'.", semantic_version_name)

    parent_issues = jira.search_issues(
        jql,
        maxResults=False,
        fields="key,issuetype,subtasks",
    )

    log.info("Found %d matching parent issue(s).", len(parent_issues))

    service_versions_without_release_date = {}

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
                if is_semantic_version(version.name) or get_release_date(version) is not None:
                    continue

                service_versions_without_release_date[str(version.id)] = {
                    "service_version": version.name,
                    "service_version_id": version.id,
                }

    results = sorted(
        service_versions_without_release_date.values(),
        key=lambda result: result["service_version"].casefold(),
    )

    log.info("Service versions without release date: %d", len(results))

    for result in results:
        log.info("Service version without release date: %s", result["service_version"])


if __name__ == "__main__":
    main()
