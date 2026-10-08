import io
import logging
import os
import re
from threading import Lock
from typing import Iterable

from dotenv import load_dotenv
from jira import JIRA
from jira.resources import Issue, Version

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_KEY = "IGM"

RELEASE_STATE_FIELD_ID = 14889
RELEASE_STATE_FIELD = f"customfield_{RELEASE_STATE_FIELD_ID}"

PARENT_ISSUE_TYPES = {
    "Story",
    "Enabler",
    "Bug",
    "Config Change",
}

RELEASABLE_SUBTASK_TYPES = {
    "Sub-task",
    "Sub-bug",
}

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


# ============================================================================
# SEMANTIC VERSION CLASSIFICATION
# ============================================================================

SEMANTIC_VERSION_PATTERN = re.compile(
    r"^(?:UNKNOWN|(Deploy|Hotfix|Config)\."
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
    r"\.\d{2}\.[1-4]\.\d+(\.\d+)?)$",
    re.IGNORECASE,
)


# ============================================================================
# LOGGING
# ============================================================================

log = logging.getLogger("release-state")
log.setLevel(logging.INFO)
log.propagate = False
release_lock = Lock()


# ============================================================================
# JIRA CONNECTION
# ============================================================================


def create_jira_client() -> JIRA:
    load_dotenv()

    jira_url = os.getenv(
        "JIRA_URL",
        "https://jira.egt-digital.com",
    )
    jira_token = os.getenv("JIRA_TOKEN", "")

    if not jira_token:
        raise RuntimeError(
            "JIRA_TOKEN environment variable is not configured. "
            "Create a .env file and add your Jira Personal Access Token."
        )

    return JIRA(
        server=jira_url,
        token_auth=jira_token,
    )


# ============================================================================
# HELPERS
# ============================================================================


def is_semantic_version(version: Version) -> bool:
    """
    Return True when the Jira version matches our semantic release naming
    convention.
    """

    name = getattr(version, "name", None)

    if not name:
        return False

    return name.casefold() != "unknown" and bool(SEMANTIC_VERSION_PATTERN.fullmatch(name))


def is_parent_semantic_version(version: Version) -> bool:
    """Return whether a parent Fix Version can define a semantic release target."""

    return is_semantic_version(version) or getattr(version, "name", "").casefold() == "unknown"


def find_project_version(
    jira: JIRA,
    project_key: str,
    version_name: str,
) -> Version:
    """
    Find an exact Jira version by name inside the configured project.
    """

    versions = jira.project_versions(project_key)

    matching_versions = [version for version in versions if version.name == version_name]

    if not matching_versions:
        raise RuntimeError(f"Version '{version_name}' does not exist in project " f"'{project_key}'.")

    if len(matching_versions) > 1:
        raise RuntimeError(f"More than one version named '{version_name}' was found " f"in project '{project_key}'.")

    return matching_versions[0]


def list_unreleased_semantic_versions(jira: JIRA, project_key: str) -> list[str]:
    """Return names of unreleased semantic versions in the project."""

    return sorted(
        version.name
        for version in jira.project_versions(project_key)
        if is_semantic_version(version) and not bool(getattr(version, "released", False))
    )


def search_all_issues(
    jira: JIRA,
    jql: str,
    fields: str,
) -> list[Issue]:
    """
    Execute paginated Jira search.
    """

    results: list[Issue] = []

    start_at = 0
    page_size = 100

    while True:
        page = jira.search_issues(
            jql,
            startAt=start_at,
            maxResults=page_size,
            fields=fields,
        )

        results.extend(page)

        if len(page) < page_size:
            break

        start_at += len(page)

    return results


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


def set_release_state(
    jira: JIRA,
    issue: Issue,
    target_state: str,
    is_dry_run: bool = False,
) -> None:
    """
    Update Release State only when its value actually needs to change.
    """

    current_state = get_release_state(issue)

    log.info(
        "%s: Release State current='%s', target='%s'",
        issue.key,
        current_state or "[EMPTY]",
        target_state,
    )

    if current_state == target_state:
        log.info(
            "%s: Release State already correct.",
            issue.key,
        )
        return

    log.info(
        "%s: updating Release State -> %s",
        issue.key,
        target_state,
    )

    if is_dry_run:
        log.info("%s: DRY RUN: would update Release State -> %s", issue.key, target_state)
        return

    issue.update(
        fields={
            RELEASE_STATE_FIELD: {
                "value": target_state,
            }
        }
    )

    # Verify.
    refreshed = jira.issue(
        issue.key,
        fields=RELEASE_STATE_FIELD,
    )

    new_state = get_release_state(refreshed)

    log.info(
        "%s: Release State after update='%s'",
        issue.key,
        new_state or "[EMPTY]",
    )


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


def publish_parent_if_eligible(
    jira: JIRA,
    parent_issue: Issue,
    all_subtasks: list[Issue],
    is_dry_run: bool = False,
) -> None:
    """Transition an eligible parent to Published when every sub-task type is Done."""

    if parent_issue.fields.status.name == "Published":
        return

    if parent_issue.fields.status.name in NON_RELEASABLE_SUBTASK_STATUSES:
        log.info("%s: not publishing; parent status is '%s'.", parent_issue.key, parent_issue.fields.status.name)
        return

    if not is_parent_ready_for_full_release(parent_issue):
        return

    if not meets_full_release_prerequisites(parent_issue, all_subtasks):
        log.info("%s: not publishing; child release prerequisites are not met.", parent_issue.key)
        return

    published_transition = next(
        (
            transition
            for transition in jira.transitions(parent_issue)
            if transition.get("name", "").casefold() == "published"
            or transition.get("to", {}).get("name", "").casefold() == "published"
        ),
        None,
    )

    if published_transition is None:
        log.warning("%s: no available transition to Published.", parent_issue.key)
        return

    if is_dry_run:
        log.info("%s: DRY RUN: would transition to Published.", parent_issue.key)
        return

    log.info("%s: transitioning to Published.", parent_issue.key)
    jira.transition_issue(parent_issue.key, published_transition["id"])


def get_full_subtask(
    jira: JIRA,
    subtask_reference: Issue,
) -> Issue:
    """
    fields.subtasks contains lightweight issue objects, so load the complete
    issue before inspecting status and Fix Version/s.
    """

    return jira.issue(
        subtask_reference.key,
        fields="key,issuetype,status,fixVersions,parent",
    )


def get_all_subtasks(
    jira: JIRA,
    parent_issue: Issue,
) -> list[Issue]:
    """
    Load all subtasks belonging to a parent issue.
    """

    subtask_references = (
        getattr(
            parent_issue.fields,
            "subtasks",
            [],
        )
        or []
    )

    return [get_full_subtask(jira, reference) for reference in subtask_references]


def find_unreleased_service_version_blockers(
    jira: JIRA,
    parent_issues: list[Issue],
) -> list[tuple[str, str, list[str]]]:
    """Return sub-tasks with unreleased service versions that block a parent semantic release."""

    blockers: list[tuple[str, str, list[str]]] = []

    for parent_issue in parent_issues:
        for subtask in get_all_subtasks(jira, parent_issue):
            if subtask.fields.issuetype.name not in RELEASABLE_SUBTASK_TYPES:
                continue

            if subtask.fields.status.name in NON_RELEASABLE_SUBTASK_STATUSES:
                continue

            unreleased_versions = unreleased_service_versions(subtask)

            if unreleased_versions:
                blockers.append((parent_issue.key, subtask.key, unreleased_versions))

    return blockers


def find_not_done_target_version_blockers(
    jira: JIRA,
    parent_issues: list[Issue],
    target_version: Version,
) -> list[tuple[str, str, str]]:
    """Return target-version sub-tasks that are not Done and block a release."""

    blockers: list[tuple[str, str, str]] = []
    target_version_id = str(target_version.id)

    for parent_issue in parent_issues:
        for subtask in get_all_subtasks(jira, parent_issue):
            if subtask.fields.issuetype.name not in RELEASABLE_SUBTASK_TYPES:
                continue

            if subtask.fields.status.name in NON_RELEASABLE_SUBTASK_STATUSES:
                continue

            if not any(str(version.id) == target_version_id for version in subtask.fields.fixVersions or []):
                continue

            if subtask.fields.status.name != DONE_STATUS:
                blockers.append((parent_issue.key, subtask.key, subtask.fields.status.name))

    return blockers


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


def add_partial_release_comment(
    jira: JIRA,
    parent_issue: Issue,
    all_subtasks: list[Issue],
    releasable_subtasks: list[Issue],
    is_whole_story_release: bool,
    dry_run_released_version_id: str | None,
    is_dry_run: bool,
) -> None:
    """Explain why the calculated Release State is Partially Released."""

    reasons: list[str] = []

    for subtask in releasable_subtasks:
        if subtask.fields.status.name != DONE_STATUS:
            reasons.append(f"{subtask.key} is in status '{subtask.fields.status.name}'")
            continue

        semantic_versions = [version for version in subtask.fields.fixVersions or [] if is_semantic_version(version)]
        unreleased_service_version_names = unreleased_service_versions(subtask)
        unreleased_semantic_versions = [
            version.name
            for version in semantic_versions
            if not bool(getattr(version, "released", False)) and str(version.id) != dry_run_released_version_id
        ]

        if not semantic_versions and not is_whole_story_release:
            reasons.append(f"{subtask.key} has no semantic Fix Version")
        if unreleased_service_version_names:
            reasons.append(
                f"{subtask.key} has unreleased service Fix Version(s): "
                f"{', '.join(unreleased_service_version_names)}"
            )
        if unreleased_semantic_versions:
            reasons.append(
                f"{subtask.key} has unreleased semantic Fix Version(s): {', '.join(unreleased_semantic_versions)}"
            )
        if not has_released_service_version(subtask):
            reasons.append(f"{subtask.key} has no released service Fix Version")

    for subtask in all_subtasks:
        if (
            subtask.fields.issuetype.name not in RELEASABLE_SUBTASK_TYPES
            and subtask.fields.status.name not in NON_RELEASABLE_SUBTASK_TERMINAL_STATUSES
        ):
            reasons.append(
                f"{subtask.key} ({subtask.fields.issuetype.name}) is in status '{subtask.fields.status.name}'"
            )

    comment = "Release State changed to Partially Released because: " + "; ".join(reasons)

    if is_dry_run:
        log.warning("%s: DRY RUN: would add comment: %s", parent_issue.key, comment)
        return

    jira.add_comment(parent_issue.key, comment)


def add_not_released_comment(
    jira: JIRA,
    parent_issue: Issue,
    all_subtasks: list[Issue],
    releasable_subtasks: list[Issue],
    is_whole_story_release: bool,
    dry_run_released_version_id: str | None,
    is_dry_run: bool,
) -> None:
    """Explain why the calculated Release State is Not Released."""

    reasons: list[str] = []

    if not releasable_subtasks:
        reasons.append("there are no active releasable Sub-task/Sub-bug issues")

    for subtask in releasable_subtasks:
        if subtask.fields.status.name != DONE_STATUS:
            reasons.append(f"{subtask.key} is in status '{subtask.fields.status.name}'")
            continue

        semantic_versions = [version for version in subtask.fields.fixVersions or [] if is_semantic_version(version)]
        unreleased_service_version_names = unreleased_service_versions(subtask)
        unreleased_semantic_versions = [
            version.name
            for version in semantic_versions
            if not bool(getattr(version, "released", False)) and str(version.id) != dry_run_released_version_id
        ]

        if not semantic_versions and not is_whole_story_release:
            reasons.append(f"{subtask.key} has no semantic Fix Version")
        if unreleased_service_version_names:
            reasons.append(
                f"{subtask.key} has unreleased service Fix Version(s): "
                f"{', '.join(unreleased_service_version_names)}"
            )
        if unreleased_semantic_versions:
            reasons.append(
                f"{subtask.key} has unreleased semantic Fix Version(s): {', '.join(unreleased_semantic_versions)}"
            )

    for subtask in all_subtasks:
        if (
            subtask.fields.issuetype.name not in RELEASABLE_SUBTASK_TYPES
            and subtask.fields.status.name not in NON_RELEASABLE_SUBTASK_TERMINAL_STATUSES
        ):
            reasons.append(
                f"{subtask.key} ({subtask.fields.issuetype.name}) is in status '{subtask.fields.status.name}'"
            )

    comment = "Release State changed to Not Released because: " + "; ".join(reasons)

    if is_dry_run:
        log.warning("%s: DRY RUN: would add comment: %s", parent_issue.key, comment)
        return

    jira.add_comment(parent_issue.key, comment)


# ============================================================================
# RELEASE-STATE CALCULATION
# ============================================================================


def evaluate_parent(
    jira: JIRA,
    parent_issue: Issue,
    is_dry_run: bool = False,
    dry_run_released_version_id: str | None = None,
) -> None:

    log.info("======================================================================")

    log.info(
        "Evaluating %s [%s]",
        parent_issue.key,
        parent_issue.fields.issuetype.name,
    )

    all_subtasks = get_all_subtasks(
        jira,
        parent_issue,
    )

    log.info(
        "%s: total subtasks=%d",
        parent_issue.key,
        len(all_subtasks),
    )

    for subtask in all_subtasks:
        versions = [
            (
                version.name,
                version.id,
                getattr(version, "released", False),
                is_semantic_version(version),
            )
            for version in subtask.fields.fixVersions or []
        ]

        log.info(
            "%s / %s: type='%s', status='%s', versions=%s",
            parent_issue.key,
            subtask.key,
            subtask.fields.issuetype.name,
            subtask.fields.status.name,
            versions,
        )

    # ========================================================================
    # FIND ACTIVE RELEASABLE SUBTASKS
    # ========================================================================

    releasable_subtasks = [
        subtask
        for subtask in all_subtasks
        if (subtask.fields.issuetype.name in RELEASABLE_SUBTASK_TYPES)
        and (subtask.fields.status.name not in NON_RELEASABLE_SUBTASK_STATUSES)
    ]

    excluded_subtasks = [
        subtask
        for subtask in all_subtasks
        if (subtask.fields.issuetype.name in RELEASABLE_SUBTASK_TYPES)
        and (subtask.fields.status.name in NON_RELEASABLE_SUBTASK_STATUSES)
    ]

    log.info(
        "%s: active releasable subtasks=%s",
        parent_issue.key,
        [
            f"{subtask.key} " f"({subtask.fields.issuetype.name}, " f"{subtask.fields.status.name})"
            for subtask in releasable_subtasks
        ],
    )

    if excluded_subtasks:
        log.info(
            "%s: excluded Rejected/Canceled subtasks=%s",
            parent_issue.key,
            [f"{subtask.key} ({subtask.fields.status.name})" for subtask in excluded_subtasks],
        )

    # ========================================================================
    # NO ACTIVE RELEASABLE CHILDREN
    # ========================================================================
    #
    # The target version has already been released in Jira before processing.
    # ========================================================================

    if not releasable_subtasks:
        log.info(
            "%s: no active releasable Sub-task/Sub-bug.",
            parent_issue.key,
        )

        if is_parent_ready_for_full_release(parent_issue) and meets_full_release_prerequisites(
            parent_issue, all_subtasks
        ):
            set_release_state(
                jira,
                parent_issue,
                STATE_FULLY_RELEASED,
                is_dry_run,
            )
        else:
            if get_release_state(parent_issue) != STATE_NOT_RELEASED:
                add_not_released_comment(
                    jira,
                    parent_issue,
                    all_subtasks,
                    releasable_subtasks,
                    False,
                    dry_run_released_version_id,
                    is_dry_run,
                )
            set_release_state(jira, parent_issue, STATE_NOT_RELEASED, is_dry_run)

        publish_parent_if_eligible(jira, parent_issue, all_subtasks, is_dry_run)
        return

    # ========================================================================
    # CALCULATE RELEASE STATE
    # ========================================================================
    #
    # A releasable child counts as released only when:
    #
    #   1. its status is Done;
    #   2. it has at least one semantic version; and
    #   3. EVERY semantic version on it is released.
    #   4. EVERY non-semantic version on it is released.
    #
    # Missing semantic version => not released.
    # Any unreleased semantic version => not released.
    # Any unreleased non-semantic version => not released.
    # ========================================================================

    releasable_subtask_count = len(releasable_subtasks)
    released_subtask_count = 0
    parent_semantic_versions = [
        version for version in parent_issue.fields.fixVersions or [] if is_parent_semantic_version(version)
    ]
    is_whole_story_release = (
        len(parent_semantic_versions) == 1
        and (
            bool(getattr(parent_semantic_versions[0], "released", False))
            or str(parent_semantic_versions[0].id) == dry_run_released_version_id
        )
        and not any(
            any(is_semantic_version(version) for version in subtask.fields.fixVersions or [])
            for subtask in releasable_subtasks
        )
    )

    for subtask in releasable_subtasks:

        if subtask.fields.status.name != DONE_STATUS:
            log.info(
                "%s / %s: NOT RELEASED - status is '%s', not Done.",
                parent_issue.key,
                subtask.key,
                subtask.fields.status.name,
            )
            continue

        semantic_versions = [version for version in subtask.fields.fixVersions or [] if is_semantic_version(version)]
        non_semantic_versions = [
            version for version in subtask.fields.fixVersions or [] if not is_semantic_version(version)
        ]

        log.info(
            "%s / %s: semanticVersions=%s",
            parent_issue.key,
            subtask.key,
            [
                (
                    version.name,
                    version.id,
                    getattr(version, "released", False),
                )
                for version in semantic_versions
            ],
        )

        # Missing semantic version.
        if not semantic_versions:
            if is_whole_story_release:
                released_subtask_count += 1
                log.info(
                    "%s / %s: RELEASED (%d/%d) via the parent's sole released semantic version.",
                    parent_issue.key,
                    subtask.key,
                    released_subtask_count,
                    releasable_subtask_count,
                )
                continue

            log.info(
                "%s / %s: NOT RELEASED - no semantic version.",
                parent_issue.key,
                subtask.key,
            )
            continue

        unreleased_non_semantic_versions = [
            version.name for version in non_semantic_versions if not bool(getattr(version, "released", False))
        ]

        if unreleased_non_semantic_versions:
            log.info(
                "%s / %s: NOT RELEASED - unreleased non-semantic versions=%s",
                parent_issue.key,
                subtask.key,
                unreleased_non_semantic_versions,
            )
            continue

        subtask_is_released = all(
            bool(getattr(version, "released", False)) or str(version.id) == dry_run_released_version_id
            for version in semantic_versions
        )

        if subtask_is_released:
            released_subtask_count += 1

            log.info(
                "%s / %s: RELEASED (%d/%d)",
                parent_issue.key,
                subtask.key,
                released_subtask_count,
                releasable_subtask_count,
            )

        else:
            unreleased_versions = [
                version.name for version in semantic_versions if not bool(getattr(version, "released", False))
            ]

            log.info(
                "%s / %s: NOT RELEASED - unreleased semantic versions=%s",
                parent_issue.key,
                subtask.key,
                unreleased_versions,
            )

    # ========================================================================
    # DERIVE PARENT RELEASE STATE
    # ========================================================================

    if released_subtask_count == 0:

        target_state = STATE_NOT_RELEASED

    elif released_subtask_count == releasable_subtask_count:

        target_state = STATE_FULLY_RELEASED

    else:

        target_state = STATE_PARTIALLY_RELEASED

    if target_state == STATE_FULLY_RELEASED and not meets_full_release_prerequisites(parent_issue, all_subtasks):
        target_state = STATE_PARTIALLY_RELEASED if released_subtask_count else STATE_NOT_RELEASED

    log.info(
        "%s: released subtasks=%d/%d -> Release State='%s'",
        parent_issue.key,
        released_subtask_count,
        releasable_subtask_count,
        target_state,
    )

    if target_state == STATE_FULLY_RELEASED:
        if not is_parent_ready_for_full_release(parent_issue):
            log.info("%s: not setting Fully Released until it has the required status.", parent_issue.key)
            return

    if target_state == STATE_PARTIALLY_RELEASED and get_release_state(parent_issue) != target_state:
        add_partial_release_comment(
            jira,
            parent_issue,
            all_subtasks,
            releasable_subtasks,
            is_whole_story_release,
            dry_run_released_version_id,
            is_dry_run,
        )

    if target_state == STATE_NOT_RELEASED and get_release_state(parent_issue) != target_state:
        add_not_released_comment(
            jira,
            parent_issue,
            all_subtasks,
            releasable_subtasks,
            is_whole_story_release,
            dry_run_released_version_id,
            is_dry_run,
        )

    set_release_state(
        jira,
        parent_issue,
        target_state,
        is_dry_run,
    )

    if target_state == STATE_FULLY_RELEASED:
        publish_parent_if_eligible(jira, parent_issue, all_subtasks, is_dry_run)


# ============================================================================
# MAIN
# ============================================================================


def _release_version(jira: JIRA, version_name: str, is_dry_run: bool) -> None:

    # ========================================================================
    # VALIDATE VERSION NAME
    # ========================================================================

    if not SEMANTIC_VERSION_PATTERN.fullmatch(version_name):
        raise RuntimeError(f"'{version_name}' is not a valid semantic release version.")

    if is_dry_run:
        log.info("DRY RUN enabled: Jira updates will not be executed.")

    log.info("Unreleased semantic versions:")
    unreleased_semantic_versions = list_unreleased_semantic_versions(jira, PROJECT_KEY)
    log.info("%s", "\n".join(unreleased_semantic_versions) if unreleased_semantic_versions else "None")

    # ========================================================================
    # FIND VERSION
    # ========================================================================

    target_version = find_project_version(
        jira,
        PROJECT_KEY,
        version_name,
    )

    log.info(
        "Version='%s', ID=%s, released=%s",
        target_version.name,
        target_version.id,
        target_version.released,
    )

    # ========================================================================
    # FIND ALL ISSUES CARRYING THIS VERSION
    # ========================================================================

    jql = f"project = {PROJECT_KEY} " f'AND fixVersion = "{version_name}"'

    issues = search_all_issues(
        jira,
        jql,
        fields=("key," "project," "issuetype," "status," "fixVersions," "subtasks," f"{RELEASE_STATE_FIELD}"),
    )

    log.info(
        "Version '%s' is assigned to %d issue(s).",
        version_name,
        len(issues),
    )

    for issue in issues:
        log.info(
            "Issue carrying version: %s | type='%s'",
            issue.key,
            issue.fields.issuetype.name,
        )

    # ========================================================================
    # KEEP ONLY SUPPORTED STORY-LEVEL ISSUES
    # ========================================================================

    affected_parent_issues = [issue for issue in issues if issue.fields.issuetype.name in PARENT_ISSUE_TYPES]

    log.info(
        "Supported parent issues=%d -> %s",
        len(affected_parent_issues),
        [issue.key for issue in affected_parent_issues],
    )

    if not affected_parent_issues:
        log.warning(
            "No Story / Enabler / Bug / Config Change carries version '%s'; "
            "releasing it without Release State updates.",
            version_name,
        )

    # ========================================================================
    # RELEASE TARGET VERSION
    # ========================================================================

    deployment_plan_blockers = find_deployment_plan_status_blockers(issues)

    if deployment_plan_blockers:
        log.warning(
            "Deployment plan(s) for semantic version '%s' must be updated manually to a terminal status; continuing with release.",
            version_name,
        )
        for plan_key, status in deployment_plan_blockers:
            log.warning(
                "Deployment Plan %s has non-terminal status '%s'.",
                plan_key,
                status,
            )

    if target_version.released:
        log.warning(
            "Version '%s' is already released; continuing with Release State updates.",
            target_version.name,
        )
    else:
        for parent_issue in affected_parent_issues:
            if parent_issue.fields.status.name == "Published":
                log.warning(
                    "Story-level issue %s (%s) is already Published; continuing with semantic version release.",
                    parent_issue.key,
                    parent_issue.fields.issuetype.name,
                )

        parent_status_blockers = find_parent_status_blockers(affected_parent_issues)

        if parent_status_blockers:
            log.error(
                "Cannot release semantic version '%s': assigned story-level issues are not at their required status.",
                version_name,
            )
            for parent_key, issue_type, current_status, required_status in parent_status_blockers:
                log.error(
                    "Parent %s (%s) has status '%s'; required status is '%s'.",
                    parent_key,
                    issue_type,
                    current_status,
                    required_status,
                )
            return

        not_done_blockers = find_not_done_target_version_blockers(jira, affected_parent_issues, target_version)

        if not_done_blockers:
            log.error(
                "Cannot release semantic version '%s': assigned sub-tasks carrying it are not Done.",
                version_name,
            )
            for parent_key, subtask_key, status in not_done_blockers:
                log.error(
                    "Blocked by parent %s, sub-task %s with status '%s'.",
                    parent_key,
                    subtask_key,
                    status,
                )
            return

        service_version_blockers = find_unreleased_service_version_blockers(jira, affected_parent_issues)

        if service_version_blockers:
            log.error(
                "Cannot release semantic version '%s': unreleased service versions exist on assigned sub-tasks.",
                version_name,
            )
            for parent_key, subtask_key, service_versions in service_version_blockers:
                log.error(
                    "Parent %s, sub-task %s: unreleased non-semantic service version(s): %s.",
                    parent_key,
                    subtask_key,
                    service_versions,
                )
            return

        if is_dry_run:
            log.info("DRY RUN: would release version '%s'.", version_name)
        else:
            log.info("Releasing version '%s'.", version_name)
            target_version.update(released=True)

    # ========================================================================
    # PROCESS EACH PARENT
    # ========================================================================

    dry_run_released_version_id = str(target_version.id) if is_dry_run and not target_version.released else None

    for parent_issue in affected_parent_issues:
        try:
            refreshed_parent_issue = jira.issue(
                parent_issue.key,
                fields=("key," "issuetype," "status," "fixVersions," "subtasks," f"{RELEASE_STATE_FIELD}"),
            )
            evaluate_parent(
                jira,
                refreshed_parent_issue,
                is_dry_run,
                dry_run_released_version_id,
            )

        except Exception:
            log.exception(
                "%s: FAILED.",
                parent_issue.key,
            )

    log.info("======================================================================")

    log.info(
        "Processing finished for released version '%s'.",
        version_name,
    )


def release_semantic_version(version_name: str, is_dry_run: bool) -> str:
    """Run the Jira release workflow and return its operational log."""
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    # The workflow changes shared Jira state, and its logger is request-scoped.
    with release_lock:
        log.addHandler(handler)
        try:
            _release_version(create_jira_client(), version_name, is_dry_run)
        except Exception:
            log.exception("Release processing failed.")
        finally:
            log.removeHandler(handler)
    return output.getvalue()
