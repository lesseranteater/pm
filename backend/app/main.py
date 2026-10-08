from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from .main_paths import PROJECT_ROOT

DEFAULT_FRONTEND_BUILD = PROJECT_ROOT / "frontend" / "build"


def _frontend_file(build_dir: Path, request_path: str) -> Path | None:
    """Return a safe file inside the frontend build directory, if it exists."""
    candidate = (build_dir / request_path).resolve()
    try:
        candidate.relative_to(build_dir.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def create_app(frontend_build_dir: Path | str | None = None) -> FastAPI:
    build_dir = Path(
        frontend_build_dir or os.environ.get("FRONTEND_BUILD_DIR", DEFAULT_FRONTEND_BUILD)
    ).resolve()
    app = FastAPI(title="Svelte FastAPI Starter API", version="0.1.0")

    @app.get("/api/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/message", tags=["system"])
    async def message() -> dict[str, str]:
        return {"message": "Hello from the Python backend."}

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
