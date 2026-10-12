"""Archive released Jira versions by date or name, streaming the operational log."""

from __future__ import annotations

import logging
from datetime import date, datetime
from threading import Lock
from typing import Iterable, Iterator

from jira import JIRA
from jira.exceptions import JIRAError
from jira.resources import Version

from .errors import ProjectNotFoundError
from .release_semantic_version import create_jira_client
from .script_runner import stream_script_log
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


def find_versions_to_archive(versions: Iterable[Version], archive_until: date) -> list[Version]:
    """Return released, unarchived versions released on or before ``archive_until``."""
    candidates = []
    for version in versions:
        if not _flag(version, "released") or _flag(version, "archived"):
            continue
        release_date = parse_release_date(version)
        if release_date is not None and release_date <= archive_until:
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


def _archive(jira: JIRA, project_key: str, is_dry_run: bool, archive_until: date) -> None:
    log.info("Project: %s", project_key)
    log.info("Archiving released versions with a release date on or before %s.", archive_until)
    log.info("Dry run: %s", is_dry_run)
    if is_dry_run:
        log.info("DRY RUN enabled: no versions will be archived.")

    try:
        versions = jira.project_versions(project_key)
    except JIRAError as error:
        if error.status_code == 404:
            raise ProjectNotFoundError(f"Jira project '{project_key}' was not found.") from error
        raise

    candidates = find_versions_to_archive(versions, archive_until)
    if not candidates:
        log.info("No released versions on or before %s to archive.", archive_until)
        return

    _archive_candidates(jira, candidates, is_dry_run)


def _archive_candidates(jira: JIRA, candidates: list[Version], is_dry_run: bool) -> None:
    semantic, service = group_versions(candidates)
    candidates = semantic + service

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

    if archived < len(candidates):
        log.error("Archived only %d of %d version(s); see the warnings above.", archived, len(candidates))
    else:
        log.info("Archived %d of %d version(s).", archived, len(candidates))


def stream_archive_released_versions(
    project_key: str, is_dry_run: bool, archive_until: date
) -> Iterator[str]:
    """Run the archive workflow, yielding its operational log as it is written."""
    return stream_script_log(
        log,
        archive_lock,
        lambda: _archive(create_jira_client(), project_key, is_dry_run, archive_until),
        "Archive processing failed.",
    )


def archive_released_versions(project_key: str, is_dry_run: bool, archive_until: date) -> str:
    """Run the archive workflow and return its complete operational log."""
    return "".join(stream_archive_released_versions(project_key, is_dry_run, archive_until))


def preview_archive(project_key: str, archive_until: date) -> dict[str, int]:
    """Count the versions an archive run would touch, without changing anything."""
    try:
        versions = create_jira_client().project_versions(project_key)
    except JIRAError as error:
        if error.status_code == 404:
            raise ProjectNotFoundError(f"Jira project '{project_key}' was not found.") from error
        raise

    semantic, service = group_versions(find_versions_to_archive(versions, archive_until))
    return {
        "count": len(semantic) + len(service),
        "semantic": len(semantic),
        "service": len(service),
    }


def select_named_versions(versions: Iterable[Version], names: list[str]) -> tuple[list[Version], dict[str, list[str]]]:
    """Select exact names, independently of release date, and explain excluded names."""
    by_name = {version.name: version for version in versions}
    candidates = []
    excluded: dict[str, list[str]] = {"unknown": [], "unreleased": [], "already_archived": []}
    for name in dict.fromkeys(name.strip() for name in names if name.strip()):
        version = by_name.get(name)
        if version is None:
            excluded["unknown"].append(name)
        elif _flag(version, "archived"):
            excluded["already_archived"].append(name)
        elif not _flag(version, "released"):
            excluded["unreleased"].append(name)
        else:
            candidates.append(version)
    return candidates, excluded


def _named_selection(jira: JIRA, project_key: str, names: list[str]):
    try:
        versions = jira.project_versions(project_key)
    except JIRAError as error:
        if error.status_code == 404:
            raise ProjectNotFoundError(f"Jira project '{project_key}' was not found.") from error
        raise
    return select_named_versions(versions, names)


def preview_archive_versions(project_key: str, names: list[str]) -> dict[str, int | list[str]]:
    candidates, excluded = _named_selection(create_jira_client(), project_key, names)
    semantic, service = group_versions(candidates)
    return {
        "count": len(candidates), "semantic": len(semantic), "service": len(service),
        "eligible": [version.name for version in semantic + service], **excluded,
    }


def _archive_named(jira: JIRA, project_key: str, is_dry_run: bool, names: list[str]) -> None:
    log.info("Project: %s", project_key)
    log.info("Archiving named released versions, regardless of release date.")
    log.info("Dry run: %s", is_dry_run)
    candidates, excluded = _named_selection(jira, project_key, names)
    if excluded["unknown"]:
        log.error("Unknown version names: %s. No versions will be archived.", ", ".join(excluded["unknown"]))
        return
    for reason in ("unreleased", "already_archived"):
        if excluded[reason]:
            log.warning("Skipping %s versions: %s", reason.replace("_", " "), ", ".join(excluded[reason]))
    if not candidates:
        log.info("No eligible released versions in the list to archive.")
        return
    _archive_candidates(jira, candidates, is_dry_run)


def stream_archive_versions(project_key: str, is_dry_run: bool, names: list[str]) -> Iterator[str]:
    return stream_script_log(
        log, archive_lock,
        lambda: _archive_named(create_jira_client(), project_key, is_dry_run, names),
        "Archive processing failed.",
    )
