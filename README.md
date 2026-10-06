# Project Management MVP

Local project-management application built with a SvelteKit frontend and a
FastAPI backend. The frontend is built as static files and served by FastAPI.

## Current Status

The frontend demo, backend persistence foundation, and Part 6 API integration
are complete. AI remains.

Available now:

- Kanban board with five fixed, renameable columns.
- Add, edit, delete, and move cards.
- Static SvelteKit build served by FastAPI.
- Health and example API endpoints.
- SQLite schema creation and deterministic seed data.
- Hardcoded login with server-side SQLite sessions.
- Authenticated persistent Kanban API for board and card operations.
- Docker image and cross-platform start/stop scripts.

Not implemented yet:

- OpenRouter AI integration.

These are planned phases documented in [`docs/PLAN.md`](docs/PLAN.md).

## Requirements

For local development:

- Docker
- Python 3.12 or newer
- `uv`
- Node.js 22 or newer
- pnpm 10

## Start The Complete App

The scripts build the frontend when needed and start FastAPI on port `8000`.

### Linux and macOS

From the repository root:

```bash
./scripts/start.sh
```

Open:

```text
http://127.0.0.1:8000/
```

Stop the server:

```bash
./scripts/stop.sh
```

The scripts store the process ID in `.pm-server.pid` and application output in
`.pm-server.log`. These files are ignored by Git.

### Windows PowerShell

From the repository root:

```powershell
.\scripts\start.ps1
```

Stop the server:

```powershell
.\scripts\stop.ps1
```

### Windows Command Prompt

```bat
scripts\start.bat
scripts\stop.bat
```

Set a different local port with the `PORT` environment variable. For example:

```bash
PORT=8080 ./scripts/start.sh
```

## Frontend Development

From `frontend/`:

```bash
pnpm install
pnpm dev
```

Open `http://localhost:5173/`. Stop the development server with `Ctrl+C`.

Run frontend checks:

```bash
pnpm check
pnpm lint
pnpm test:unit --run
pnpm test:e2e
pnpm build
```

Install the Playwright browser if needed:

```bash
pnpm exec playwright install chromium
```

The production frontend output is generated in `frontend/build/` and is served
by FastAPI.

## Backend Development

Install or synchronize Python dependencies from the repository root:

```bash
uv sync
```

Run FastAPI directly:

```bash
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Available endpoints:

- `GET /api/health` returns the backend health status.
- `GET /api/example` returns a sample API response.
- `GET /` serves the compiled SvelteKit frontend.

Run backend tests:

```bash
uv run pytest
```

## Docker

Build the combined image from the repository root:

```bash
docker build -t project-management-mvp .
```

Run it:

```bash
docker run --rm -p 8000:8000 project-management-mvp
```

Open `http://localhost:8000/`.

The image builds the SvelteKit frontend in a Node build stage, then runs only
FastAPI in the final Python image. The `/app/data` volume is reserved for the
SQLite database planned in a later phase:

```bash
docker run --rm -p 8000:8000 -v pm_data:/app/data project-management-mvp
```

## Project Structure

- `frontend/`: SvelteKit application and frontend tests.
- `backend/`: FastAPI application and backend tests.
- `scripts/`: cross-platform local start and stop scripts.
- `docs/PLAN.md`: authoritative implementation roadmap and approval gates.
- `Dockerfile`: combined frontend build and FastAPI runtime image.
- `pyproject.toml`: Python dependencies and pytest configuration.

## Development Rules

- Read [`AGENTS.md`](AGENTS.md) before making changes.
- Read [`frontend/AGENTS.md`](frontend/AGENTS.md) for frontend-specific rules.
- Keep secrets, local databases, generated output, and dependencies out of Git.
- Follow the phases and approval gates in `docs/PLAN.md`.
