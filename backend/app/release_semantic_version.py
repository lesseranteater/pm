import logging
from threading import Lock
from typing import Iterator

from jira import JIRA
from jira.exceptions import JIRAError
from jira.resources import Issue, Version

from .errors import ProjectNotFoundError, UserFacingError, explain_exception
from .jira_credentials import create_jira_client
from .script_runner import stream_script_log
from .release_comments import build_release_state_comment
from .release_rules import (
    DONE_STATUS,
    NON_RELEASABLE_SUBTASK_STATUSES,
    PROJECT_KEY,
    RELEASE_STATE_FIELD,
    STATE_FULLY_RELEASED,
    STATE_NOT_RELEASED,
    STATE_PARTIALLY_RELEASED,
    find_deployment_plan_status_blockers,
    find_parent_status_blockers,
    get_release_state,
    is_parent_ready_for_full_release,
    is_parent_semantic_version,
    is_semantic_version,
    meets_full_release_prerequisites,
    unreleased_service_versions,
    version_status,
)
from .jira_rules import (
    PARENT_ISSUE_TYPES,
    RELEASABLE_SUBTASK_TYPES,
    is_semantic_release_version,
    jql_project,
    jql_quote,
)

# ============================================================================
# CONFIGURATION
# ============================================================================

# ============================================================================
# SEMANTIC VERSION CLASSIFICATION
# ============================================================================
# The naming pattern lives in service_versions.is_semantic_release_version.


# ============================================================================
# LOGGING
# ============================================================================

server_log = logging.getLogger(__name__)
log = logging.getLogger("release-state")
log.setLevel(logging.INFO)
log.propagate = False
release_lock = Lock()


# ============================================================================
# JIRA CONNECTION
# ============================================================================


# ============================================================================
# HELPERS
# ============================================================================


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
        raise UserFacingError(f"Version '{version_name}' does not exist in project " f"'{project_key}'.")

    if len(matching_versions) > 1:
        raise UserFacingError(f"More than one version named '{version_name}' was found " f"in project '{project_key}'.")

    return matching_versions[0]


def list_semantic_versions(jira: JIRA, project_key: str, status: str) -> list[str]:
    """Return names of semantic versions in the project with the given status."""

    try:
        project_versions = jira.project_versions(project_key)
    except JIRAError as error:
        if error.status_code == 404:
            raise ProjectNotFoundError(f"Jira project '{project_key}' was not found.") from error
        raise

    return sorted(
        version.name
        for version in project_versions
        if is_semantic_release_version(getattr(version, "name", "") or "")
        and version_status(version) == status
    )


def get_semantic_versions(status: str, project_key: str = PROJECT_KEY) -> list[str]:
    """Return semantic version names with the given status for a Jira project."""

    return list_semantic_versions(create_jira_client(), project_key, status)


def search_all_issues(
    jira: JIRA,
    jql: str,
    fields: str,
) -> list[Issue]:
    """
    Execute paginated Jira search.
    """

    results: list[Issue] = []

    while True:
        page = jira.search_issues(
            jql,
            startAt=len(results),
            maxResults=100,
            fields=fields,
        )

        results.extend(page)

        # Jira may return fewer issues per page than requested, so a short page is not the end.
        total = getattr(page, "total", None)
        if not page or (total is not None and len(results) >= total):
            break

    return results


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


def load_subtasks_by_parent(jira: JIRA, parent_issues: list[Issue]) -> dict[str, list[Issue]]:
    """Load every parent's sub-tasks once, so several checks can share the Jira calls."""

    return {parent_issue.key: get_all_subtasks(jira, parent_issue) for parent_issue in parent_issues}


def find_unreleased_service_version_blockers(
    jira: JIRA,
    parent_issues: list[Issue],
    subtasks_by_parent: dict[str, list[Issue]] | None = None,
) -> list[tuple[str, str, list[str]]]:
    """Return sub-tasks with unreleased service versions that block a parent semantic release."""

    blockers: list[tuple[str, str, list[str]]] = []

    for parent_issue in parent_issues:
        subtasks = (
            subtasks_by_parent[parent_issue.key]
            if subtasks_by_parent is not None
            else get_all_subtasks(jira, parent_issue)
        )
        for subtask in subtasks:
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
    subtasks_by_parent: dict[str, list[Issue]] | None = None,
) -> list[tuple[str, str, str]]:
    """Return target-version sub-tasks that are not Done and block a release."""

    blockers: list[tuple[str, str, str]] = []
    target_version_id = str(target_version.id)

    for parent_issue in parent_issues:
        subtasks = (
            subtasks_by_parent[parent_issue.key]
            if subtasks_by_parent is not None
            else get_all_subtasks(jira, parent_issue)
        )
        for subtask in subtasks:
            if subtask.fields.issuetype.name not in RELEASABLE_SUBTASK_TYPES:
                continue

            if subtask.fields.status.name in NON_RELEASABLE_SUBTASK_STATUSES:
                continue

            if not any(str(version.id) == target_version_id for version in subtask.fields.fixVersions or []):
                continue

            if subtask.fields.status.name != DONE_STATUS:
                blockers.append((parent_issue.key, subtask.key, subtask.fields.status.name))

    return blockers


def add_release_state_comment(
    jira: JIRA,
    state: str,
    parent_issue: Issue,
    all_subtasks: list[Issue],
    releasable_subtasks: list[Issue],
    is_whole_story_release: bool,
    dry_run_released_version_id: str | None,
    is_dry_run: bool,
) -> None:
    """Explain on the parent why its Release State is Partially Released or Not Released."""

    comment = build_release_state_comment(
        state, parent_issue, all_subtasks, releasable_subtasks, is_whole_story_release, dry_run_released_version_id
    )

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
                add_release_state_comment(
                    jira,
                    STATE_NOT_RELEASED,
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
        add_release_state_comment(
            jira,
            STATE_PARTIALLY_RELEASED,
            parent_issue,
            all_subtasks,
            releasable_subtasks,
            is_whole_story_release,
            dry_run_released_version_id,
            is_dry_run,
        )

    if target_state == STATE_NOT_RELEASED and get_release_state(parent_issue) != target_state:
        add_release_state_comment(
            jira,
            STATE_NOT_RELEASED,
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

    if not is_semantic_release_version(version_name):
        raise UserFacingError(f"'{version_name}' is not a valid semantic release version.")

    if is_dry_run:
        log.info("DRY RUN enabled: Jira updates will not be executed.")

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

    jql = f"project = {jql_project(PROJECT_KEY)} AND fixVersion = {jql_quote(version_name)}"

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

        # Both checks run before the release changes anything, so they can share one load.
        subtasks_by_parent = load_subtasks_by_parent(jira, affected_parent_issues)

        not_done_blockers = find_not_done_target_version_blockers(
            jira, affected_parent_issues, target_version, subtasks_by_parent
        )

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

        service_version_blockers = find_unreleased_service_version_blockers(
            jira, affected_parent_issues, subtasks_by_parent
        )

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

        except Exception as error:
            # The traceback stays in the server log; the stream gets only the explained cause.
            server_log.exception("%s: release state update failed", parent_issue.key)
            log.error("%s: FAILED. %s", parent_issue.key, explain_exception(error))

    log.info("======================================================================")

    log.info(
        "Processing finished for released version '%s'.",
        version_name,
    )


def stream_release_semantic_version(version_name: str, is_dry_run: bool) -> Iterator[str]:
    """Run the Jira release workflow, yielding its operational log as it is written."""
    return stream_script_log(
        log,
        release_lock,
        lambda: _release_version(create_jira_client(), version_name, is_dry_run),
        "Release processing failed.",
    )
