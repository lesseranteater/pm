from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from typing import Callable, Iterable, Literal

from fastapi import FastAPI, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

from .archive_released_versions import (
    preview_archive, stream_archive_released_versions, preview_archive_versions, stream_archive_versions,
)
from .auth import Authentication, SESSION_COOKIE, SESSION_TTL, configured_users
from .jira_credentials import JIRA_TOKEN_COOKIE, jira_token, jira_token_configured
from .errors import ProjectNotFoundError, explain_exception
from .main_paths import PROJECT_ROOT
from .release_check import stream_release_check
from .release_semantic_version import (
    get_semantic_versions,
    stream_release_semantic_version,
)
from .jira_rules import PROJECT_KEY_REGEX, is_semantic_release_version
from .service_versions import stream_service_versions_report

DEFAULT_FRONTEND_BUILD = PROJECT_ROOT / "frontend" / "build"
log = logging.getLogger(__name__)

# Page URLs that were renamed. Old bookmarks are sent to the new address.
LEGACY_PAGE_REDIRECTS = {
    "service-versions": "/list-service-versions-without-a-release-date",
    "release-semantic-version": "/release-a-deployment-version",
    "release-a-semantic-version": "/release-a-deployment-version",
}

ScriptLog = str | Iterable[str]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class JiraTokenRequest(BaseModel):
    token: SecretStr = Field(min_length=1, max_length=2048)

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: SecretStr) -> SecretStr:
        if any(ord(character) < 33 or ord(character) > 126 for character in value.get_secret_value()):
            raise ValueError("Token must contain printable characters without spaces")
        return value


class ServiceVersionRequest(BaseModel):
    project_key: str = Field(pattern=PROJECT_KEY_REGEX)
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


class VersionListRequest(BaseModel):
    project_key: str = Field(pattern=PROJECT_KEY_REGEX)
    version_names: list[str] = Field(min_length=1, max_length=500)

    @field_validator("version_names")
    @classmethod
    def validate_names(cls, values: list[str]) -> list[str]:
        names = [value.strip() for value in values]
        if any(not name or len(name) > 255 for name in names):
            raise ValueError("Version names must contain between 1 and 255 characters")
        return list(dict.fromkeys(names))


class ArchiveRequest(BaseModel):
    project_key: str = Field(pattern=PROJECT_KEY_REGEX)
    is_dry_run: bool
    archive_by: Literal["date", "versions"] = "date"
    archive_until: date | None = None
    version_names: list[str] | None = None

    @model_validator(mode="after")
    def validate_selection(self):
        if self.archive_by == "date":
            if self.archive_until is None or self.archive_until > date.today():
                raise ValueError("Choose an archive date that is not in the future")
            if self.version_names is not None:
                raise ValueError("Version list cannot be used with date mode")
        else:
            if self.archive_until is not None:
                raise ValueError("Archive date cannot be used with version-list mode")
            self.version_names = VersionListRequest(
                project_key=self.project_key, version_names=self.version_names or [],
            ).version_names
        return self


class ReleaseCheckRequest(BaseModel):
    deployment_plan_key: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,9}-\d+$")


class ApiAuthMiddleware:
    """Authenticate `/api/` requests and expose the signed-in user's Jira token to the handlers.

    A plain ASGI middleware, so streaming responses and client disconnects pass straight through,
    and static files skip the session lookup.
    """

    PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/api/auth/logout"}

    def __init__(self, app: ASGIApp, authentication: Authentication, allowed_origin: str = "") -> None:
        self.app = app
        self.authentication = authentication
        # Behind a TLS-terminating proxy the app sees http, so the public origin is configured.
        # Unset, the origin is taken from the request itself, as before.
        self.allowed_origin = allowed_origin

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        path = request.url.path
        user = self.authentication.user(request.cookies.get(SESSION_COOKIE))
        token = self.authentication.jira_token(request.cookies.get(SESSION_COOKIE)) if user else ""

        rejection = self._rejection(request, path, user, token)
        if rejection is not None:
            await rejection(scope, receive, send)
            return

        async def send_without_caching(message: Message) -> None:
            if message["type"] == "http.response.start" and path.startswith("/api/auth/"):
                MutableHeaders(scope=message)["Cache-Control"] = "no-store"
            await send(message)

        context_token = jira_token.set(token)
        try:
            await self.app(scope, receive, send_without_caching)
        finally:
            jira_token.reset(context_token)

    def _rejection(self, request: Request, path: str, user: str | None, token: str) -> JSONResponse | None:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            expected = self.allowed_origin or str(request.base_url).rstrip("/")
            if origin and origin != expected:
                return JSONResponse(status_code=403, content={"detail": "Cross-origin request rejected"})
        if path in self.PUBLIC_PATHS:
            return None
        if not user:
            return JSONResponse(
                status_code=401, content={"detail": "Not authenticated"}, headers={"Cache-Control": "no-store"},
            )
        if not path.startswith("/api/auth/") and not token:
            return JSONResponse(
                status_code=428, content={"detail": "Enter your Jira token to use this tool"},
                headers={"Cache-Control": "no-store"},
            )
        return None


def _log_response(result: ScriptLog) -> StreamingResponse:
    """Stream a script log as plain text, one chunk per log line."""
    chunks = [result] if isinstance(result, str) else result
    return StreamingResponse(
        chunks,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def _configured_origin(value: str) -> str:
    """Validate the optional ALLOWED_ORIGIN setting, for example https://tools.example.com."""
    origin = value.strip().rstrip("/")
    if not origin:
        return ""
    parsed = urlsplit(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path or parsed.query:
        raise RuntimeError("ALLOWED_ORIGIN must look like https://tools.example.com (scheme and host only)")
    return origin


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
    auth_users: dict[str, str] | None = None,
    named_version_archiver: Callable[[str, bool, list[str]], ScriptLog] = stream_archive_versions,
    named_version_previewer: Callable[[str, list[str]], dict[str, int | list[str]]] = preview_archive_versions,
) -> FastAPI:
    build_dir = Path(
        frontend_build_dir or os.environ.get("FRONTEND_BUILD_DIR", DEFAULT_FRONTEND_BUILD)
    ).resolve()
    app = FastAPI(title="Release Management Tools API", version="0.1.0")
    authentication = Authentication(configured_users() if auth_users is None else auth_users)
    # uvicorn's logger is configured at INFO, so this shows in the server log by default.
    startup_log = logging.getLogger("uvicorn.error")
    if authentication.users:
        startup_log.info("Authentication: %d user(s) configured", len(authentication.users))
    else:
        startup_log.warning("Authentication: no users configured, so sign-in is disabled (set AUTH_USERS_JSON)")
    app.state.authentication = authentication
    secure_cookie = os.environ.get("COOKIE_SECURE", "false").lower() in {"true", "1", "yes"}
    allowed_origin = _configured_origin(os.environ.get("ALLOWED_ORIGIN", ""))
    if not secure_cookie:
        log.warning(
            "Cookies are not marked Secure (COOKIE_SECURE is off). This is fine over plain HTTP; "
            "set COOKIE_SECURE=true once the app is served over HTTPS."
        )

    app.add_middleware(ApiAuthMiddleware, authentication=authentication, allowed_origin=allowed_origin)

    @app.post("/api/auth/login", tags=["auth"])
    async def login(credentials: LoginRequest, request: Request, response: Response) -> dict[str, str]:
        if not authentication.users:
            raise HTTPException(status_code=503, detail="Authentication is not configured")
        username = credentials.username.strip().lower()
        wait = authentication.lockout_remaining(username)
        if wait:
            log.warning("Sign-in throttled for a username after repeated failures")
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed sign-in attempts. Try again in {wait} seconds.",
                headers={"Retry-After": str(wait), "Cache-Control": "no-store"},
            )
        if not await run_in_threadpool(authentication.verify, username, credentials.password):
            authentication.record_failure(username)
            log.warning("Failed sign-in attempt")
            raise HTTPException(status_code=401, detail="Invalid username or password")
        authentication.record_success(username)
        authentication.logout(request.cookies.get(SESSION_COOKIE))
        response.set_cookie(
            SESSION_COOKIE, authentication.create_session(username), max_age=SESSION_TTL,
            httponly=True, secure=secure_cookie, samesite="lax", path="/",
        )
        # The token used to be a cookie; clear any left in the browser by an earlier version.
        response.delete_cookie(JIRA_TOKEN_COOKIE, path="/", httponly=True, secure=secure_cookie, samesite="lax")
        return {"username": username}

    @app.get("/api/auth/me", tags=["auth"])
    async def current_user(request: Request) -> dict[str, str | bool]:
        username = authentication.user(request.cookies.get(SESSION_COOKIE))
        if username is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return {
            "username": username,
            "jira_configured": bool(authentication.jira_token(request.cookies.get(SESSION_COOKIE))),
        }

    @app.post("/api/auth/jira-token", tags=["auth"])
    async def save_jira_token(credentials: JiraTokenRequest, request: Request, response: Response) -> dict[str, bool]:
        if not authentication.set_jira_token(
            request.cookies.get(SESSION_COOKIE), credentials.token.get_secret_value()
        ):
            raise HTTPException(status_code=401, detail="Not authenticated")
        # Clear any token cookie left in the browser by an earlier version.
        response.delete_cookie(JIRA_TOKEN_COOKIE, path="/", httponly=True, secure=secure_cookie, samesite="lax")
        return {"jira_configured": True}

    @app.post("/api/auth/logout", tags=["auth"])
    async def logout(request: Request, response: Response) -> dict[str, bool]:
        authentication.logout(request.cookies.get(SESSION_COOKIE))
        response.delete_cookie(SESSION_COOKIE, httponly=True, secure=secure_cookie, samesite="lax", path="/")
        response.delete_cookie(JIRA_TOKEN_COOKIE, httponly=True, secure=secure_cookie, samesite="lax", path="/")
        return {"logged_out": True}

    @app.get("/api/health", tags=["system"])
    async def health() -> dict[str, str | bool]:
        return {"status": "ok", "jira_configured": jira_configured()}

    @app.post("/api/service-versions", tags=["service-versions"])
    async def service_versions(request: ServiceVersionRequest) -> StreamingResponse:
        # The runners are generators: nothing runs until the response is iterated, and a failure
        # is explained in the streamed log, so there is nothing to catch here.
        return _log_response(service_version_reporter(request.project_key, request.release_version))

    @app.get("/api/semantic-versions", tags=["release-semantic-version"])
    def semantic_versions(
        status: Literal["unreleased", "released", "archived"] = "unreleased",
        project_key: str = Query(default="IGM", pattern=PROJECT_KEY_REGEX),
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
        if request.archive_by == "versions":
            return _log_response(
                named_version_archiver(request.project_key, request.is_dry_run, request.version_names)
            )
        return _log_response(
            released_version_archiver(request.project_key, request.is_dry_run, request.archive_until)
        )

    @app.get("/api/archive-released-versions/preview", tags=["archive-released-versions"])
    def archive_preview(
        archive_until: date,
        project_key: str = Query(pattern=PROJECT_KEY_REGEX),
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

    @app.post("/api/archive-released-versions/preview", tags=["archive-released-versions"])
    def preview_version_list(request: VersionListRequest) -> dict[str, int | list[str]]:
        try:
            return named_version_previewer(request.project_key, request.version_names)
        except ProjectNotFoundError:
            raise HTTPException(status_code=404, detail=f"Jira project {request.project_key} was not found") from None
        except Exception as error:
            log.exception("Unable to preview named versions")
            raise HTTPException(status_code=503, detail=explain_exception(error)) from None

    @app.post("/api/release-semantic-version", tags=["release-semantic-version"])
    async def release_version(request: SemanticReleaseRequest) -> StreamingResponse:
        return _log_response(semantic_version_releaser(request.version_name, request.is_dry_run))

    @app.post("/api/release-check", tags=["release-check"])
    async def release_check(request: ReleaseCheckRequest) -> StreamingResponse:
        return _log_response(release_checker(request.deployment_plan_key))

    @app.get("/{request_path:path}", include_in_schema=False)
    async def frontend(request_path: str):
        if request_path == "api" or request_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})

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
