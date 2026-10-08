# Svelte FastAPI Starter

Read `AGENTS.md`, `frontend/AGENTS.md`, and `backend/AGENTS.md` before changing
code. Keep the project as a small SvelteKit and FastAPI starter unless the user
explicitly expands its scope.

## Architecture

- `frontend/` contains the static SvelteKit application.
- `backend/` contains the FastAPI app and pytest tests.
- FastAPI serves `frontend/build/` at `/` and owns same-origin `/api` routes.
- Docker builds the frontend and runs the combined application on port 8000.
- Python dependencies are managed with `uv`; frontend dependencies use pnpm.

## Commands

- Complete application: `./scripts/start.sh` and `./scripts/stop.sh`.
- Backend tests: `uv run pytest`.
- Frontend checks: run `pnpm check`, `pnpm lint`, `pnpm test:unit --run`, and
  `pnpm build` in `frontend/`.
- Docker: `docker build -t svelte-fastapi-starter .` followed by
  `docker run --rm -p 8000:8000 svelte-fastapi-starter`.

## Conventions

- Keep API boundaries explicit and validate external data.
- Use Svelte runes and same-origin `/api` requests.
- Avoid speculative features and preserve unrelated user changes.
- Do not commit secrets, generated output, or dependencies.
