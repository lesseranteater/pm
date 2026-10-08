import os
import re
from dataclasses import dataclass

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


@dataclass(frozen=True)
class ServiceVersion:
    id: str
    name: str


def _jira_client() -> JIRA:
    load_dotenv()
    token = os.getenv("JIRA_TOKEN", "")
    if not token:
        raise RuntimeError("JIRA_TOKEN environment variable is not configured")
    return JIRA(server=os.getenv("JIRA_URL", "https://jira.egt-digital.com"), token_auth=token)


def is_semantic_release_version(name: str) -> bool:
    return bool(SEMANTIC_VERSION_PATTERN.fullmatch(name))


def get_service_versions_without_release_date(
    project_key: str, release_version: str
) -> list[ServiceVersion]:
    """Return unique non-semantic service versions without a Jira release date."""
    jira = _jira_client()
    parents = jira.search_issues(
        f'''project = {project_key}
        AND issuetype IN ("Story", "Enabler", "Bug", "Config Change")
        AND fixVersion = "{release_version}"
        ORDER BY key ASC''',
        maxResults=False,
        fields="key,issuetype,subtasks",
    )
    versions: dict[str, ServiceVersion] = {}

    for parent in parents:
        if parent.fields.issuetype.name not in PARENT_ISSUE_TYPES:
            continue
        for reference in parent.fields.subtasks or []:
            subtask = jira.issue(reference.key, fields="key,issuetype,fixVersions")
            if subtask.fields.issuetype.name not in RELEASABLE_SUBTASK_TYPES:
                continue
            for version in subtask.fields.fixVersions or []:
                if is_semantic_release_version(version.name) or getattr(version, "releaseDate", None):
                    continue
                versions[str(version.id)] = ServiceVersion(id=str(version.id), name=version.name)

    return sorted(versions.values(), key=lambda version: version.name.casefold())
