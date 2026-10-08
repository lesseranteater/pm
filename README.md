# Svelte FastAPI Starter

A minimal local application with a SvelteKit frontend and FastAPI backend. The
frontend fetches and displays a message from the Python API. The production
frontend is built as static files and served by FastAPI.

## Requirements

- Python 3.12 or newer with `uv`
- Node.js 22 or newer with pnpm 10
- Docker for the container workflow

## Run Locally

Install dependencies:

```bash
uv sync
pnpm --dir frontend install
```

Build the frontend and start the combined application:

```bash
pnpm --dir frontend build
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. The frontend requests `GET /api/message`, which
returns the message it displays. `GET /api/health` reports backend health.

The cross-platform scripts build the frontend when needed and run the same
combined application:

```bash
./scripts/start.sh
./scripts/stop.sh
```

On Windows PowerShell, use `./scripts/start.ps1` and `./scripts/stop.ps1`.

## Frontend Development

Run the Svelte development server from `frontend/`:

```bash
pnpm dev
```

For this standalone frontend server, requests to `/api/message` require a
separately running backend or a development proxy. Use the combined server
workflow above to exercise the complete application.

## Verification

```bash
uv run pytest
pnpm --dir frontend check
pnpm --dir frontend lint
pnpm --dir frontend test:unit --run
pnpm --dir frontend build
```

## Docker

Build and run the combined image:

```bash
docker build -t svelte-fastapi-starter .
docker run --rm -p 8000:8000 svelte-fastapi-starter
```

Open `http://localhost:8000/`. The image builds the Svelte frontend in a Node
build stage and runs FastAPI in the final Python image.

## Project Structure

- `frontend/`: SvelteKit application and frontend tests.
- `backend/`: FastAPI application and backend tests.
- `scripts/`: cross-platform start and stop scripts.
- `Dockerfile`: combined frontend build and FastAPI runtime image.
