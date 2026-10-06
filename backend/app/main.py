from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .auth import (
    SESSION_COOKIE_NAME,
    SESSION_TTL,
    create_session,
    delete_session,
    get_user_for_session,
    verify_password,
)
from .board import register_board_routes
from .database import DEFAULT_DATABASE_PATH, connect, initialize_database
from .main_paths import PROJECT_ROOT

DEFAULT_FRONTEND_BUILD = PROJECT_ROOT / "frontend" / "build"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


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
    database_path: Path | str | None = None,
) -> FastAPI:
    build_dir = Path(
        frontend_build_dir
        or os.environ.get("FRONTEND_BUILD_DIR", DEFAULT_FRONTEND_BUILD)
    ).resolve()
    db_path = Path(database_path or os.environ.get("DATABASE_PATH", DEFAULT_DATABASE_PATH)).resolve()
    secure_cookie = os.environ.get("COOKIE_SECURE", "false").lower() in {
        "1",
        "true",
        "yes",
    }

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        initialize_database(db_path)
        yield

    app = FastAPI(title="Project Management MVP API", version="0.1.0", lifespan=lifespan)

    def require_user(request: Request) -> dict[str, str]:
        with connect(db_path) as connection:
            user = get_user_for_session(connection, request.cookies.get(SESSION_COOKIE_NAME))
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        return {"id": user["user_id"], "username": user["username"]}

    @app.post("/api/auth/login", tags=["auth"])
    async def login(credentials: LoginRequest, response: Response) -> dict[str, str]:
        with connect(db_path) as connection:
            user = connection.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (credentials.username,),
            ).fetchone()
            if not user or not verify_password(credentials.password, user["password_hash"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password",
                )
            token, _ = create_session(connection, user["id"])

        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            max_age=int(SESSION_TTL.total_seconds()),
            httponly=True,
            secure=secure_cookie,
            samesite="lax",
            path="/",
        )
        return {"username": user["username"]}

    @app.get("/api/auth/me", tags=["auth"])
    async def current_user(user: dict[str, str] = Depends(require_user)) -> dict[str, str]:
        return {"username": user["username"]}

    @app.post("/api/auth/logout", tags=["auth"])
    async def logout(request: Request, response: Response) -> dict[str, bool]:
        with connect(db_path) as connection:
            delete_session(connection, request.cookies.get(SESSION_COOKIE_NAME))
        response.delete_cookie(
            key=SESSION_COOKIE_NAME,
            httponly=True,
            secure=secure_cookie,
            samesite="lax",
            path="/",
        )
        return {"logged_out": True}

    register_board_routes(app, db_path, require_user)

    @app.get("/api/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/example", tags=["system"])
    async def example() -> dict[str, str]:
        return {"message": "Hello from the Project Management MVP backend"}

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
