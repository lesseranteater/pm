from __future__ import annotations

import os
import sys
from datetime import date, datetime
from typing import Optional, List

from dotenv import load_dotenv
from jira import JIRA
from jira.exceptions import JIRAError
from jira.resources import Version

load_dotenv()

JIRA_URL = os.getenv("JIRA_URL", "https://jira.egt-digital.com")
TOKEN = os.getenv("JIRA_TOKEN", "")


def ensure_token() -> None:
    if not TOKEN:
        raise RuntimeError(
            "JIRA_TOKEN environment variable is not configured. "
            "Create a .env file and add your Jira Personal Access Token."
        )


def get_project_versions(jira_client: JIRA, project_key: str) -> List[Version]:
    """Return all versions for a project."""
    # jira.project_versions returns list of Version resources
    return jira_client.project_versions(project_key)


def parse_release_date(version: Version) -> Optional[date]:
    """Safely parse the releaseDate attribute from a Version resource."""
    # Version may expose releaseDate as an attribute or in raw dict
    raw = getattr(version, "raw", None) or {}
    rd = getattr(version, "releaseDate", None) or raw.get("releaseDate")
    if not rd:
        return None
    try:
        return datetime.strptime(rd, "%Y-%m-%d").date()
    except Exception:
        # ignore unparsable formats
        return None


def archive_version(jira_client: JIRA, version: Version) -> None:
    """Archive the given version by setting archived=True via the API."""
    # The python-jira client doesn't expose a convenience method on all
    # versions for updating arbitrary Version attributes in some installs,
    # so call the REST API directly using the client's session.
    try:
        server = jira_client._options.get("server")
        if not server:
            raise JIRAError("JIRA server URL not available on client._options")

        url = f"{server.rstrip('/')}/rest/api/2/version/{version.id}"
        resp = jira_client._session.put(url, json={"archived": True})
        resp.raise_for_status()
    except Exception as exc:
        # Wrap non-JIRA exceptions so callers can handle JIRAError uniformly
        raise JIRAError(f"Failed to archive version {getattr(version, 'id', None)}: {exc}")


def main() -> int:
    ensure_token()

    project_key = "IGM"
    dry_run = False  # Set to True to skip actual archiving and just log what would be done

    # simple CLI: optional project key and --dry-run
    args = [a for a in sys.argv[1:]]
    for a in args[:]:
        if a in ("--dry-run", "-n"):
            dry_run = True
            args.remove(a)

    if args:
        project_key = args[0].strip().upper()

    jira = JIRA(server=JIRA_URL, token_auth=TOKEN)

    print(f"Connecting to JIRA: {JIRA_URL}")
    print(f"Project: {project_key}")
    print("Dry run:", dry_run)

    try:
        versions = get_project_versions(jira, project_key)
    except JIRAError as exc:
        print(f"Could not load versions for project {project_key}: {exc}")
        return 1

    today = date.today()
    candidates: List[Version] = []

    for v in versions:
        released = getattr(v, "released", False) or v.raw.get("released")
        archived = getattr(v, "archived", False) or v.raw.get("archived")
        if not released:
            continue
        if archived:
            continue
        rd = parse_release_date(v)
        if rd is None:
            # skip versions without a parseable release date
            continue
        if rd < today:
            candidates.append(v)

    if not candidates:
        print("No released versions with past release dates to archive.")
        return 0

    print(f"Found {len(candidates)} version(s) to archive:")
    for v in candidates:
        rd = parse_release_date(v)
        print(f" - {v.name} (id={v.id}) released={v.released} releaseDate={rd}")

    if dry_run:
        print("Dry run: no changes will be made.")
        return 0

    archived_count = 0
    for v in candidates:
        try:
            print(f"Archiving {v.name} (id={v.id})...")
            archive_version(jira, v)
            archived_count += 1
        except JIRAError as exc:
            print(f"Failed to archive {v.name} (id={v.id}): {exc}")

    print(f"Archived {archived_count} version(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
