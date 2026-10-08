# Svelte FastAPI Starter

## Purpose

Maintain a small local starter application with a SvelteKit frontend and a
FastAPI backend. The frontend is built as static files and served by FastAPI.

## Architecture

- Keep frontend code in `frontend/` and backend code in `backend/`.
- SvelteKit uses `@sveltejs/adapter-static` and produces `frontend/build/`.
- FastAPI serves the frontend at `/` and owns same-origin `/api` routes.
- The application runs in one Docker container for local use.
- Use `uv` for Python dependency management.

## Working Rules

- Keep changes focused and avoid speculative features or abstractions.
- Read relevant code before editing and preserve unrelated user changes.
- Establish the root cause of bugs before fixing them; verify relevant behavior.
- Keep API boundaries explicit and validate external data at those boundaries.
- Keep documentation concise and do not use emojis.
- Do not commit secrets, generated output, or dependencies.

## Delivery

- Keep project documentation in `README.md` and `docs/` when needed.
- Run checks appropriate to the change and report results accurately.
- At handoff, report how to run the application, checks performed, and blockers.
