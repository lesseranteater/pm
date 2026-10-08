# Backend Guidance

- FastAPI owns `/api` routes and serves the compiled SvelteKit output from
  `frontend/build/`.
- Manage Python dependencies with `uv` and keep the backend compatible with
  Python 3.12 or newer.
- Keep secrets in environment variables and never commit `.env` files.
- Add deterministic pytest coverage for API behavior and file-serving changes.
- Keep API responses small, explicit, and validated at the boundary.
