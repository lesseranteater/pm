# Backend Guidance

- FastAPI owns authentication, SQLite persistence, OpenRouter calls, and `/api`
  routes for the local MVP.
- FastAPI also serves the compiled SvelteKit static output from `frontend/build/`.
- Manage Python dependencies with `uv` and keep the backend compatible with
  Python 3.12 or newer.
- Keep secrets in environment variables. Never commit `.env` files, API keys,
  local SQLite databases, or generated output.
- Add deterministic pytest coverage for every endpoint and data boundary.
- Keep backend changes focused on the current phase in `docs/PLAN.md`; do not
  implement authentication, persistence, or AI before their approval gates.
