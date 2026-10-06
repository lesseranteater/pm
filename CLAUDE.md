# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Read `AGENTS.md` (root), `frontend/AGENTS.md`, and `backend/AGENTS.md` before changing code. `docs/PLAN.md` is the authoritative roadmap; the MVP is complete through Part 10, and features outside it need explicit approval. The functional scope (one board, five fixed renameable columns, title/details cards, `user`/`password` login, a non-drag way to move cards) must be preserved.

## Commands

Backend (from repo root, Python 3.12+, `uv`):

```bash
uv sync
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
uv run pytest                                   # all backend tests
uv run pytest backend/tests/test_ai.py::test_all_supported_operations_apply_in_one_batch   # single test
```

Frontend (from `frontend/`, Node 22+, pnpm 10):

```bash
pnpm dev                    # Vite dev server on :5173
pnpm check && pnpm lint     # svelte-check; prettier --check + eslint
pnpm test:unit --run        # Vitest (omit --run for watch)
pnpm test:e2e               # Playwright; run against a production build
pnpm build                  # writes frontend/build/
```

Full app: `./scripts/start.sh` / `./scripts/stop.sh` (build frontend if missing, run uvicorn on `PORT`, default 8000; PID in `.pm-server.pid`, log in `.pm-server.log`). Docker: `docker build -t project-management-mvp .`, then run with `--env-file .env -v pm_data:/app/data`. See `docs/RELEASE.md` for release verification.

## Architecture

One process serves everything: FastAPI (`backend/app/main.py`, `create_app()`) owns all `/api` routes and also serves the static SvelteKit output from `frontend/build/` through a catch-all `/{path}` route. It falls back to `200.html`/`index.html` for SPA routes and returns 503 if no build exists. After frontend changes, rebuild (`pnpm build`) for FastAPI to see them; the start script only builds when `index.html` is absent.

Backend modules in `backend/app/`:
- `main.py`: app factory, login/logout/me routes, and the `require_user` dependency that is passed into each `register_*_routes` function. `create_app` accepts `frontend_build_dir`, `database_path`, and `openrouter_client` overrides, which tests use for isolation and for injecting a fake OpenRouter client.
- `database.py`, `auth.py`: raw `sqlite3` (no ORM); schema and deterministic seed data; server-side sessions delivered through an HTTP-only cookie.
- `board.py`: board, column, and card CRUD, scoped per authenticated user.
- `openrouter.py`: the only place that calls OpenRouter (`openai/gpt-oss-120b`), plus a connectivity-check route.
- `ai.py`: `POST /api/ai/board`. The model must return JSON `{response, operations?}`, and operations are pydantic-validated (`create_card`, `edit_card`, `move_card`, `delete_card`, `rename_column`; max 20). The whole batch is validated against the current board first, then applied in one SQLite transaction (all or nothing). Contract in `docs/AI-OPERATIONS.md`.

Environment: `OPENROUTER_API_KEY` (server-side only, `.env` is gitignored and excluded from the Docker context), `DATABASE_PATH` (default `data/app.db`), `FRONTEND_BUILD_DIR`, `COOKIE_SECURE`.

Frontend (`frontend/src/`): SvelteKit 2, Svelte 5 runes, strict TS, Tailwind 4, adapter-static with prerendering. It is a static client only: no SvelteKit server routes or actions; it talks to FastAPI through the typed client `src/lib/api.ts` using same-origin `/api` calls. Board logic is in `src/lib/board.ts` (unit-tested in `board.test.ts`); the UI is in `src/routes/+page.svelte`. Playwright specs are in `frontend/e2e/`, and `production.spec.ts` checks the build as served.

Docs in `docs/` (`API.md`, `DATABASE.md`, `database-schema.json`, `AI-OPERATIONS.md`, `OPENROUTER.md`) describe the contracts. The database schema and the structured AI contract were approval-gated, so update these docs together with any change to either.

## Conventions

- Svelte: runes only (`$state`/`$derived`; no `$:` or `on:click`), keyed `{#each}`, card content rendered as text (never `{@html}`), and brand colors from `frontend/AGENTS.md`.
- Every backend endpoint and data boundary needs deterministic pytest coverage; mock OpenRouter in tests.
- No emojis in docs. Do not commit `.env`, `data/`, `frontend/build/`, or `.pm-server.*`.
