# Project Management MVP

## Current Goal

Build the complete local Project Management MVP described in `docs/PLAN.md`.
The frontend-only Kanban demo is complete. The active roadmap now includes
FastAPI, authentication, SQLite persistence, Docker packaging, and OpenRouter
AI functionality.

Read `docs/PLAN.md` before starting work. It is the authoritative source for
project phases, architecture decisions, approval gates, tests, and success
criteria. Read `frontend/AGENTS.md` for SvelteKit-specific implementation,
accessibility, and frontend testing guidance.

## Functional Scope

- Exactly one board with five fixed, renameable columns.
- Cards with a title and details; support adding, editing, deleting, and
  drag-and-drop movement between columns.
- A hardcoded MVP login using `user` / `password`.
- One board per authenticated user, persisted in SQLite.
- An AI sidebar capable of creating, editing, moving, deleting, and renaming
  board content through validated structured operations.
- A polished, responsive, accessible UI, including a non-drag way to move cards.
- No features outside the approved roadmap without explicit approval.

## Architecture

- SvelteKit uses `@sveltejs/adapter-static` and produces the frontend build.
- FastAPI serves the static SvelteKit output at `/` and owns `/api` routes.
- FastAPI owns authentication, SQLite persistence, and OpenRouter calls.
- The application is packaged into one Docker container for local use.
- Use `uv` for Python dependency management.
- Keep `OPENROUTER_API_KEY` server-side and never expose it to browser code.
- Use `openai/gpt-oss-120b` for OpenRouter requests.

## Working Rules

- Preserve the functional requirements during simplification and refactoring.
- Keep changes focused and avoid speculative features or abstractions.
- Establish the root cause of bugs before fixing them; verify relevant behavior.
- Keep documentation concise and do not use emojis.
- Do not commit secrets, local databases, generated output, or dependencies.

## Planning And Delivery

- Store project planning and architecture documents in `docs/`.
- Work through `docs/PLAN.md` in order and respect its approval gates.
- Do not skip database-schema or structured-AI-contract approval.
- Treat the frontend-only limitations in `frontend/AGENTS.md` as applying to
  the completed demo phase; they do not prohibit explicitly approved roadmap
  phases.
- At implementation handoff, verify the required user journeys, leave the
  local application ready when practical, and report the URL, checks, and any
  blockers accurately.
