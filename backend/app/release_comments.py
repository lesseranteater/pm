"""The explanatory comment added to a story when its Release State changes."""

from jira.resources import Issue

from .jira_rules import RELEASABLE_SUBTASK_TYPES
from .release_rules import (
    DONE_STATUS,
    NON_RELEASABLE_SUBTASK_TERMINAL_STATUSES,
    STATE_NOT_RELEASED,
    STATE_PARTIALLY_RELEASED,
    has_released_service_version,
    is_semantic_version,
    unreleased_service_versions,
)


def build_release_state_comment(
    state: str,
    parent_issue: Issue,
    all_subtasks: list[Issue],
    releasable_subtasks: list[Issue],
    is_whole_story_release: bool,
    dry_run_released_version_id: str | None,
) -> str:
    """Explain why the calculated Release State is Partially Released or Not Released."""

    reasons: list[str] = []
    service_version_is_optional = parent_issue.fields.issuetype.name == "Config Change"

    if state == STATE_NOT_RELEASED and not releasable_subtasks:
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
        # Only the Partially Released comment lists this; a Config Change does not need a service version.
        if state == STATE_PARTIALLY_RELEASED and not service_version_is_optional:
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

    return f"Release State changed to {state} because: " + "; ".join(reasons)
