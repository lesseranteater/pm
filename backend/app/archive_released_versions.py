"""Archive Jira versions that were released in the past.

Web-service port of ``tools/archive_released_versions_in_the_past.py``. The workflow
writes to a request-scoped logger and returns the captured log to the caller.
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime
from threading import Lock
from typing import Iterable

from jira import JIRA
from jira.exceptions import JIRAError
from jira.resources import Version

from .release_semantic_version import ProjectNotFoundError, create_jira_client
from .service_versions import is_semantic_release_version

log = logging.getLogger("archive-released-versions")
log.setLevel(logging.INFO)
log.propagate = False

archive_lock = Lock()


def _flag(version: Version, name: str) -> bool:
    """Read a boolean attribute from the Version resource or its raw JSON."""
    value = getattr(version, name, None)
    if value is None:
        value = (getattr(version, "raw", None) or {}).get(name)
    return bool(value)


def parse_release_date(version: Version) -> date | None:
    """Return the version's release date, or None when it is missing or unparsable."""
    raw_date = getattr(version, "releaseDate", None) or (getattr(version, "raw", None) or {}).get(
        "releaseDate"
    )
    if not raw_date:
        return None
    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return None


def find_versions_to_archive(versions: Iterable[Version], today: date) -> list[Version]:
    """Return released, unarchived versions whose release date is before ``today``."""
    candidates = []
    for version in versions:
        if not _flag(version, "released") or _flag(version, "archived"):
            continue
        release_date = parse_release_date(version)
        if release_date is not None and release_date < today:
            candidates.append(version)
    return candidates


def group_versions(versions: Iterable[Version]) -> tuple[list[Version], list[Version]]:
    """Split versions into (semantic, service) lists, each sorted alphabetically by name."""
    ordered = sorted(versions, key=lambda version: version.name.casefold())
    semantic = [version for version in ordered if is_semantic_release_version(version.name)]
    service = [version for version in ordered if not is_semantic_release_version(version.name)]
    return semantic, service


def archive_version(jira: JIRA, version: Version) -> None:
    """Archive a version by setting ``archived`` through Jira's REST API."""
    server = jira._options.get("server")
    if not server:
        raise JIRAError("JIRA server URL not available on client._options")

    response = jira._session.put(
        f"{server.rstrip('/')}/rest/api/2/version/{version.id}",
        json={"archived": True},
    )
    response.raise_for_status()


def _archive(jira: JIRA, project_key: str, is_dry_run: bool, today: date) -> None:
    log.info("Project: %s", project_key)
    log.info("Dry run: %s", is_dry_run)
    if is_dry_run:
        log.info("DRY RUN enabled: no versions will be archived.")

    try:
        versions = jira.project_versions(project_key)
    except JIRAError as error:
        if error.status_code == 404:
            raise ProjectNotFoundError(f"Jira project '{project_key}' was not found.") from error
        raise

    semantic, service = group_versions(find_versions_to_archive(versions, today))
    candidates = semantic + service
    if not candidates:
        log.info("No released versions with past release dates to archive.")
        return

    log.info("Found %d version(s) to archive:", len(candidates))
    for title, group in (("Semantic", semantic), ("Service", service)):
        log.info("%s (%d):", title, len(group))
        for version in group:
            log.info(
                " - %s (id=%s) releaseDate=%s",
                version.name,
                version.id,
                parse_release_date(version),
            )

    if is_dry_run:
        log.info("Dry run: no changes were made.")
        return

    archived = 0
    for version in candidates:
        try:
            log.info("Archiving %s (id=%s)...", version.name, version.id)
            archive_version(jira, version)
            archived += 1
        except Exception as error:
            log.warning("Failed to archive %s (id=%s): %s", version.name, version.id, error)

    log.info("Archived %d of %d version(s).", archived, len(candidates))


def archive_released_versions(project_key: str, is_dry_run: bool) -> str:
    """Run the archive workflow and return its operational log."""
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    # The workflow changes shared Jira state, and its logger is request-scoped.
    with archive_lock:
        log.addHandler(handler)
        try:
            _archive(create_jira_client(), project_key, is_dry_run, date.today())
        except Exception:
            log.exception("Archive processing failed.")
        finally:
            log.removeHandler(handler)
    return output.getvalue()

