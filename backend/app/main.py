from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from .main_paths import PROJECT_ROOT
from .release_semantic_version import get_semantic_versions, release_semantic_version
from .service_versions import (
    ServiceVersion,
    get_service_versions_without_release_date,
    is_semantic_release_version,
)

DEFAULT_FRONTEND_BUILD = PROJECT_ROOT / "frontend" / "build"
log = logging.getLogger(__name__)


class ServiceVersionResponse(BaseModel):
    id: str
    name: str


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


class SemanticReleaseResponse(BaseModel):
    log: str


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
    service_version_reporter: Callable[[str, str], list[ServiceVersion]] = get_service_versions_without_release_date,
    semantic_version_releaser: Callable[[str, bool], str] = release_semantic_version,
    semantic_version_lister: Callable[[str, str], list[str]] = get_semantic_versions,
) -> FastAPI:
    build_dir = Path(
        frontend_build_dir or os.environ.get("FRONTEND_BUILD_DIR", DEFAULT_FRONTEND_BUILD)
    ).resolve()
    app = FastAPI(title="Svelte FastAPI Starter API", version="0.1.0")

    @app.get("/api/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/service-versions", tags=["service-versions"])
    async def service_versions(request: ServiceVersionRequest) -> list[ServiceVersionResponse]:
        try:
            return [
                ServiceVersionResponse(id=version.id, name=version.name)
                for version in service_version_reporter(request.project_key, request.release_version)
            ]
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
        except Exception:
            log.exception("Unable to retrieve semantic versions")
            raise HTTPException(
                status_code=503,
                detail="Unable to retrieve semantic versions",
            ) from None

    @app.post("/api/release-semantic-version", tags=["release-semantic-version"])
    async def release_version(request: SemanticReleaseRequest) -> SemanticReleaseResponse:
        try:
            return SemanticReleaseResponse(
                log=semantic_version_releaser(request.version_name, request.is_dry_run)
            )
        except Exception:
            log.exception("Unable to release semantic version")
            raise HTTPException(
                status_code=503,
                detail="Unable to release semantic version",
            ) from None

    @app.get("/{request_path:path}", include_in_schema=False)
    async def frontend(request_path: str):
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
