from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from .archive_released_versions import preview_archive, stream_archive_released_versions
from .errors import ProjectNotFoundError, explain_exception
from .main_paths import PROJECT_ROOT
from .release_check import stream_release_check
from .release_semantic_version import (
    get_semantic_versions,
    jira_token_configured,
    stream_release_semantic_version,
)
from .service_versions import is_semantic_release_version, stream_service_versions_report

DEFAULT_FRONTEND_BUILD = PROJECT_ROOT / "frontend" / "build"
log = logging.getLogger(__name__)

# Page URLs that were renamed. Old bookmarks are sent to the new address.
LEGACY_PAGE_REDIRECTS = {
    "service-versions": "/list-service-versions-without-a-release-date",
    "release-semantic-version": "/release-a-deployment-version",
    "release-a-semantic-version": "/release-a-deployment-version",
}

ScriptLog = str | Iterable[str]


class ServiceVersionRequest(BaseModel):
    project_key: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,9}$")
    release_version: str = Field(min_length=1, max_length=120)

    @field_validator("release_version")
    @classmethod
    def validate_release_version(cls, value: str) -> str:
        if not is_semantic_release_version(value):
            raise ValueError("Release version is not supported")
        return value


class SemanticReleaseRequest(BaseModel):
    version_name: str = Field(min_length=1, max_length=120)
    is_dry_run: bool

    @field_validator("version_name")
    @classmethod
    def validate_version_name(cls, value: str) -> str:
        if not is_semantic_release_version(value):
            raise ValueError("Deployment version is not supported")
        return value


class ArchiveRequest(BaseModel):
    project_key: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,9}$")
    is_dry_run: bool
    archive_until: date

    @field_validator("archive_until")
    @classmethod
    def validate_archive_until(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Archive date cannot be in the future")
        return value


class ReleaseCheckRequest(BaseModel):
    deployment_plan_key: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,9}-\d+$")


def _log_response(result: ScriptLog) -> StreamingResponse:
    """Stream a script log as plain text, one chunk per log line."""
    chunks = [result] if isinstance(result, str) else result
    return StreamingResponse(
        chunks,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def _frontend_file(build_dir: Path, request_path: str) -> Path | None:
    """Return a safe file inside the frontend build directory, if it exists."""
    candidate = (build_dir / request_path).resolve()
    try:
        candidate.relative_to(build_dir.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def create_app(
    frontend_build_dir: Path | str | None = None,
    service_version_reporter: Callable[[str, str], ScriptLog] = stream_service_versions_report,
    semantic_version_releaser: Callable[[str, bool], ScriptLog] = stream_release_semantic_version,
    semantic_version_lister: Callable[[str, str], list[str]] = get_semantic_versions,
    released_version_archiver: Callable[[str, bool, date], ScriptLog] = stream_archive_released_versions,
    released_version_previewer: Callable[[str, date], dict[str, int]] = preview_archive,
    jira_configured: Callable[[], bool] = jira_token_configured,
    release_checker: Callable[[str], ScriptLog] = stream_release_check,
) -> FastAPI:
    build_dir = Path(
        frontend_build_dir or os.environ.get("FRONTEND_BUILD_DIR", DEFAULT_FRONTEND_BUILD)
    ).resolve()
    app = FastAPI(title="Svelte FastAPI Starter API", version="0.1.0")

    @app.get("/api/health", tags=["system"])
    async def health() -> dict[str, str | bool]:
        return {"status": "ok", "jira_configured": jira_configured()}

    @app.post("/api/service-versions", tags=["service-versions"])
    async def service_versions(request: ServiceVersionRequest) -> StreamingResponse:
        try:
            return _log_response(
                service_version_reporter(request.project_key, request.release_version)
            )
        except Exception:
            log.exception("Unable to retrieve service versions from Jira")
            raise HTTPException(
                status_code=503,
                detail="Unable to retrieve service versions from Jira",
            ) from None

    @app.get("/api/semantic-versions", tags=["release-semantic-version"])
    async def semantic_versions(
        status: Literal["unreleased", "released", "archived"] = "unreleased",
        project_key: str = Query(default="IGM", pattern=r"^[A-Z][A-Z0-9_]{1,9}$"),
    ) -> list[str]:
        try:
            return semantic_version_lister(status, project_key)
        except ProjectNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"Jira project {project_key} was not found",
            ) from None
        except Exception as error:
            log.exception("Unable to retrieve semantic versions")
            raise HTTPException(status_code=503, detail=explain_exception(error)) from None

    @app.post("/api/archive-released-versions", tags=["archive-released-versions"])
    async def archive_versions(request: ArchiveRequest) -> StreamingResponse:
        try:
            return _log_response(
                released_version_archiver(
                    request.project_key, request.is_dry_run, request.archive_until
                )
            )
        except Exception:
            log.exception("Unable to archive released versions")
            raise HTTPException(
                status_code=503,
                detail="Unable to archive released versions",
            ) from None

    @app.get("/api/archive-released-versions/preview", tags=["archive-released-versions"])
    async def archive_preview(
        archive_until: date,
        project_key: str = Query(pattern=r"^[A-Z][A-Z0-9_]{1,9}$"),
    ) -> dict[str, int]:
        if archive_until > date.today():
            raise HTTPException(status_code=422, detail="Archive date cannot be in the future")
        try:
            return released_version_previewer(project_key, archive_until)
        except ProjectNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"Jira project {project_key} was not found",
            ) from None
        except Exception as error:
            log.exception("Unable to preview archived versions")
            raise HTTPException(status_code=503, detail=explain_exception(error)) from None

    @app.post("/api/release-semantic-version", tags=["release-semantic-version"])
    async def release_version(request: SemanticReleaseRequest) -> StreamingResponse:
        try:
            return _log_response(
                semantic_version_releaser(request.version_name, request.is_dry_run)
            )
        except Exception:
            log.exception("Unable to release semantic version")
            raise HTTPException(
                status_code=503,
                detail="Unable to release semantic version",
            ) from None

    @app.post("/api/release-check", tags=["release-check"])
    async def release_check(request: ReleaseCheckRequest) -> StreamingResponse:
        try:
            return _log_response(release_checker(request.deployment_plan_key))
        except Exception:
            log.exception("Unable to run release check")
            raise HTTPException(status_code=503, detail="Unable to run release check") from None

    @app.get("/{request_path:path}", include_in_schema=False)
    async def frontend(request_path: str):
        legacy_target = LEGACY_PAGE_REDIRECTS.get(request_path.strip("/"))
        if legacy_target:
            return RedirectResponse(legacy_target, status_code=308)

        requested_file = _frontend_file(build_dir, request_path or "index.html")
        if requested_file:
            return FileResponse(requested_file)

        fallback = _frontend_file(build_dir, "200.html") or _frontend_file(build_dir, "index.html")
        if fallback:
            return FileResponse(fallback)

        return JSONResponse(
            status_code=503,
            content={"detail": "Frontend build is not available"},
        )

    return app


app = create_app()
