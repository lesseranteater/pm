from __future__ import annotations

import os
import sys
from typing import Optional

from dotenv import load_dotenv
from jira import JIRA
from jira.exceptions import JIRAError
from jira.resources import Issue


load_dotenv()

JIRA_URL = os.getenv(
    "JIRA_URL",
    "https://jira.egt-digital.com",
)

TOKEN = os.getenv("JIRA_TOKEN", "")


# ============================================================
# JIRA CONNECTION
# ============================================================

if not TOKEN:
    raise RuntimeError(
        "JIRA_TOKEN environment variable is not configured. "
        "Create a .env file and add your Jira Personal Access Token."
    )

jira = JIRA(
    server=JIRA_URL,
    token_auth=TOKEN,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_fix_version_names(issue: Optional[Issue]) -> set[str]:
    """Return all Fix Version/s names assigned to an issue."""
    if issue is None:
        return set()

    fix_versions = getattr(issue.fields, "fixVersions", None) or []

    return {
        version.name
        for version in fix_versions
        if getattr(version, "name", None)
    }


def get_linked_issue_keys(issue: Issue) -> list[str]:
    """Return the keys of all inward and outward linked issues."""
    linked_issue_keys: set[str] = set()
    issue_links = getattr(issue.fields, "issuelinks", None) or []

    for issue_link in issue_links:
        outward_issue = getattr(issue_link, "outwardIssue", None)
        inward_issue = getattr(issue_link, "inwardIssue", None)

        if outward_issue is not None:
            linked_issue_keys.add(outward_issue.key)

        if inward_issue is not None:
            linked_issue_keys.add(inward_issue.key)

    return sorted(linked_issue_keys)


def get_parent_issue(
    jira_client: JIRA,
    issue: Issue,
) -> Optional[Issue]:
    """Load the parent issue when the current issue is a subtask."""
    parent_reference = getattr(issue.fields, "parent", None)

    if parent_reference is None:
        return None

    try:
        return jira_client.issue(
            parent_reference.key,
            fields="summary,issuetype,fixVersions,parent,subtasks",
        )
    except JIRAError as exc:
        print(
            f"Could not load parent issue "
            f"{parent_reference.key}: {exc}"
        )
        return None


def get_subtask_issues(
    jira_client: JIRA,
    issue: Issue,
) -> list[Issue]:
    """Load all direct subtasks of an issue."""
    subtask_references = getattr(issue.fields, "subtasks", None) or []
    subtask_issues: list[Issue] = []

    for subtask_reference in subtask_references:
        try:
            subtask_issue = jira_client.issue(
                subtask_reference.key,
                fields="summary,issuetype,fixVersions,parent",
            )
            subtask_issues.append(subtask_issue)

        except JIRAError as exc:
            print(
                f"Could not load subtask "
                f"{subtask_reference.key}: {exc}"
            )

    return subtask_issues


def get_release_plan_key() -> str:
    """
    Read the Release Plan key from the first command-line argument.
    If it is missing, ask the user to enter it.
    """
    if len(sys.argv) >= 2:
        return sys.argv[1].strip().upper()

    return input("Enter the Release Plan issue key: ").strip().upper()


# ============================================================
# MAIN LOGIC
# ============================================================

def find_mismatching_version_sources(
    jira_client: JIRA,
    release_plan_key: str,
) -> None:
    """
    Check every issue linked to the Release Plan.

    Display only linked issues where at least one Fix Version/s value
    differs from the version or versions assigned to the Release Plan.

    The check covers:
    1. The linked issue
    2. Its parent
    3. Its direct subtasks

    Issues without Fix Version/s are ignored.
    """

    try:
        release_plan = jira_client.issue(
            release_plan_key,
            fields="summary,issuetype,fixVersions,issuelinks",
        )
    except JIRAError as exc:
        print(
            f"Release Plan {release_plan_key} "
            f"could not be loaded: {exc}"
        )
        return

    release_plan_versions = get_fix_version_names(release_plan)

    if not release_plan_versions:
        print(
            f"Release Plan {release_plan_key} "
            "does not have any Fix Version/s."
        )
        return

    print(
        "=== Finding Fix Version mismatches "
        f"for Release Plan {release_plan_key} ==="
    )
    print(
        "Expected Release Plan version(s): "
        + ", ".join(sorted(release_plan_versions))
    )

    linked_issue_keys = get_linked_issue_keys(release_plan)

    print(f"Total linked issues checked: {len(linked_issue_keys)}")

    mismatches_found = 0

    for linked_issue_key in linked_issue_keys:
        try:
            linked_issue = jira_client.issue(
                linked_issue_key,
                fields="summary,issuetype,fixVersions,parent,subtasks",
            )
        except JIRAError as exc:
            print(
                f"Could not load linked issue "
                f"{linked_issue_key}: {exc}"
            )
            continue

        issue_type = getattr(
            linked_issue.fields.issuetype,
            "name",
            "Unknown",
        )
        summary = getattr(linked_issue.fields, "summary", "")

        linked_issue_versions = get_fix_version_names(linked_issue)
        mismatching_issue_versions = (
            linked_issue_versions - release_plan_versions
        )

        parent_issue = get_parent_issue(jira_client, linked_issue)
        parent_versions = get_fix_version_names(parent_issue)
        mismatching_parent_versions = (
            parent_versions - release_plan_versions
        )

        subtask_issues = get_subtask_issues(
            jira_client,
            linked_issue,
        )

        mismatching_subtasks: list[tuple[str, set[str]]] = []

        for subtask_issue in subtask_issues:
            subtask_versions = get_fix_version_names(subtask_issue)
            mismatching_versions = (
                subtask_versions - release_plan_versions
            )

            if mismatching_versions:
                mismatching_subtasks.append(
                    (
                        subtask_issue.key,
                        mismatching_versions,
                    )
                )

        if not (
            mismatching_issue_versions
            or mismatching_parent_versions
            or mismatching_subtasks
        ):
            continue

        mismatches_found += 1

        print("-" * 80)
        print(
            f"{linked_issue.key} | "
            f"{issue_type} | "
            f"{summary}"
        )

        if mismatching_issue_versions:
            print(
                "  Linked issue mismatching version(s): "
                + ", ".join(sorted(mismatching_issue_versions))
            )

        if mismatching_parent_versions:
            parent_key = (
                parent_issue.key
                if parent_issue is not None
                else "Unknown"
            )
            print(
                f"  Parent {parent_key} mismatching version(s): "
                + ", ".join(sorted(mismatching_parent_versions))
            )

        if mismatching_subtasks:
            print("  Subtasks with mismatching version(s):")

            for subtask_key, mismatching_versions in mismatching_subtasks:
                print(
                    f"    {subtask_key}: "
                    + ", ".join(sorted(mismatching_versions))
                )

    print(
        "=== CHECK COMPLETE | "
        f"Linked issues with mismatches: {mismatches_found} ==="
    )


# ============================================================
# ENTRY POINT
# ============================================================

def main() -> int:
    try:
        release_plan_key = get_release_plan_key()

        if not release_plan_key:
            print("A Release Plan issue key is required.")
            return 1

        find_mismatching_version_sources(
            jira_client=jira,
            release_plan_key=release_plan_key,
        )
        return 0

    except JIRAError as exc:
        print(f"Jira error: {exc}")
        return 1

    except Exception as exc:
        print(f"Unexpected error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
