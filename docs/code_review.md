# Code Review

Date: 2026-10-06. Scope: the whole repository at commit `634a005` (backend,
frontend, Docker, scripts, docs, tests).

## Method

- Read every backend module, the frontend client and page, the Dockerfile,
  scripts, ignore files, and all project docs.
- Ran the full test suite: backend 37 passed (including the live OpenRouter
  test), frontend check, lint, unit, build, and 11 Playwright tests all passed.
- Reproduced suspected defects with throwaway scripts against temporary
  databases (results are marked "Verified" below). Findings without that mark
  come from reading the code only.
- Not reviewed: runtime color contrast (no measurement taken), the Windows
  scripts (cannot be run here), and `frontend/src/app.css` beyond color usage.

## Summary

The architecture matches `docs/PLAN.md` and the layering is clean: one process,
raw `sqlite3`, ownership checks on every query, hashed session tokens, a safe
static-file resolver, and a strictly validated, transactional AI contract. The
tests are deterministic and pass.

The main problems are behavioral rather than structural: deleted demo cards come
back after a restart, the AI chat stops working after about 11 exchanges, the
documented start script cannot use the AI key, and the AI path is fragile on
compound requests. There is also no CI and no `pnpm dev` to backend wiring.

Severity: High = user-visible defect or exposure in normal use. Medium = real
defect with limited impact, or a significant maintenance or quality gap.
Low = polish.

## Findings

### High

**H1. Deleted seed cards reappear after every restart. (Verified)**
`initialize_database` runs `INSERT OR IGNORE` for the seed cards on each
startup (`backend/app/database.py:142`). The IDs are fixed, so a card the user
deleted is inserted again at the next start. Moved or edited cards survive, which
makes the behavior inconsistent. Reproduced: delete `card-brief`, re-initialize,
the card exists again. `docs/DATABASE.md` claims seeding is safe to repeat; it is
only safe for an empty database.
Action: seed only when the user row does not yet exist (or the database is
empty), in one transaction. Add a regression test for delete-then-restart.

**H2. The AI conversation breaks after about 11 exchanges. (Verified)**
The frontend sends the entire history (`+page.svelte:130`), but the backend
accepts at most 20 messages (`ai.py:94`). The request that carries 22 messages
returns 422 with a list in `detail`, and `api.ts:36` turns that into
`"[object Object]"` as the error text. After that point every question fails
until the user logs out (history is cleared only in `logout`).
Action: send only the most recent messages (for example the last 20), or raise
the limit deliberately. Make `api.ts` render FastAPI's list-shaped `detail`
(see M5). Add an e2e or unit test with a long history.

**H3. `scripts/start.sh` and `start.ps1` never load `.env`, so the AI is
unavailable through the documented local start path.** (Verified by grep:
neither script mentions `.env`; the app has no dotenv loader.) The README
presents these scripts as "start the complete app" and keeps the key in
`.env`, so `POST /api/ai/board` returns 503 "OpenRouter is not configured"
unless the user exported the variable in their shell.
Action: have the scripts load `.env` when present (`set -a; . .env; set +a` and
the PowerShell equivalent), add a `.env.example`, and document
`OPENROUTER_API_KEY`, `DATABASE_PATH`, `FRONTEND_BUILD_DIR`, and
`COOKIE_SECURE` in the README.

**H4. Known credentials plus a paid upstream key, bound to all interfaces in
Docker.** The login is `user` / `password` by design, and the login page prints
it. The documented `docker run -p 8000:8000` publishes on every host interface,
and the container listens on `0.0.0.0`. Anyone on the network can sign in and
spend OpenRouter credits through `/api/ai/board`. There is also no login rate
limit.
Action: document and use `-p 127.0.0.1:8000:8000` in the README and
`docs/RELEASE.md`. Consider a simple cap on AI requests per session or per
minute. The hardcoded login itself is an approved MVP decision and is not
flagged as a defect.

### Medium

**M1. The AI path fails on some compound or legitimate requests.**
Live runs against `openai/gpt-oss-120b` on a temporary database:
- A single-operation request succeeded in 2.4 s.
- "Create three cards, move one, and rename a column" returned 502 "invalid
  JSON" after 27.5 s. A follow-up direct call with the same prompt returned
  valid JSON in 4.8 s (and 16.7 s with a larger token limit), so this is
  intermittent. Token truncation at `max_tokens=512` (`openrouter.py:100`) is a
  plausible cause but is not confirmed.
- "Edit a card's title and move it" returned 422 "Operation references an
  unknown or conflicting card", because `_validate_operations` allows each card
  to be targeted only once (`ai.py:136`). Editing and moving one card is a
  natural request.
Action: allow multiple non-conflicting operations per card (apply in order),
add one retry on invalid JSON, raise `max_tokens` with headroom for 20
operations, and make the error text actionable. Add an opt-in live test for
`/api/ai/board`; today only the `2+2` call is covered live. Also return 502,
not 422, when the model's operations are invalid, since the client did nothing
wrong.

**M2. `GET /api/<unknown>` returns the SPA page with status 200. (Verified)**
The catch-all route (`main.py:121`) also matches unknown API paths, so a typo
returns HTML instead of a JSON 404. `PLAN.md` Part 2 asks to preserve `/api/*`
routing.
Action: raise 404 for paths starting with `api/` in the catch-all. Add a test.

**M3. Database connections are never closed. (Verified)**
`with connect(...) as connection` commits or rolls back but does not close the
connection. Running the suite with `-W always::ResourceWarning` produced 121
"unclosed database" warnings. CPython closes them at garbage collection, so it
works today, but it is fragile and noisy.
Action: make `connect` a context manager that commits, rolls back, and closes
(`contextlib.closing` or a small wrapper). Consider `PRAGMA busy_timeout` and WAL
mode at the same time.

**M4. Synchronous SQLite and a 120k-round PBKDF2 inside `async def` routes.**
All board and auth routes are `async def` but perform blocking work, so each
request blocks the event loop. The AI route is a plain `def` (threadpool) and can
write concurrently with them. A concurrent write can wait on the SQLite lock (up
to the default 5 s) while holding the event loop. Create-card also computes
`MAX(position)+1` outside any explicit write transaction.
Action: make the board and auth routes plain `def` so FastAPI runs them in the
threadpool, and use `BEGIN IMMEDIATE` for read-modify-write mutations. Fine to
defer for a single-user local app, but record the limitation.

**M5. Frontend error handling: FastAPI validation errors and a sticky banner.**
- `api.ts:36` and `+page.svelte:89` assume `detail` is a string. A 422 from
  Pydantic has a list, producing `"[object Object]"` (verified for the login
  and AI endpoints).
- `boardError` is set by `handleApiError` and cleared only by `loadBoard`, so a
  failed action leaves the error banner visible after later actions succeed.
Action: normalize `detail` (string, or join `msg` fields) in one helper; clear
`boardError` at the start of each mutation.

**M6. Duplicated business logic between `board.py` and `ai.py`.**
Card move, delete, and create are implemented twice (the move logic is about
50 lines in each place), and `ai.py` imports private `_`-prefixed helpers from
`board.py`. A fix in one copy can miss the other.
Action: extract a small `board_service` (create, edit, move, delete, rename on a
connection) used by both the routes and the AI operation applier.

**M7. Frontend structure and API-client bypass.**
`+page.svelte` is 644 lines containing auth, board, drag and drop, and the AI
sidebar. Login, session check, and logout call `fetch` directly instead of the
typed client, although `PLAN.md` Part 6 says requests are centralized there.
`frontend/AGENTS.md` expects shared components in `src/lib/components/`.
Action: move auth calls into `api.ts`; split the page into `LoginForm`,
`BoardColumn`, `TaskCard`, and `AssistantSidebar` components.

**M8. Frontend test coverage is thin and partly tests dead code.**
`board.ts` `createDemoBoard` and `createCard` are used only by their own unit
tests, not by the app. The two unit tests cover nothing the app runs. Component
tests (the Vitest browser project that `frontend/AGENTS.md` describes) are not
configured. All 10 default e2e tests mock the API with `page.route`; the one
real-stack test (`production.spec.ts`) skips unless `PRODUCTION_BASE_URL` is set.
Action: delete the dead helpers and their tests (or cover `api.ts` and
`toColumns` instead), add component tests for the card and sidebar behaviors,
and run the production spec in CI.

**M9. No CI and no backend lint or type checking.**
There is no `.github/` workflow, so nothing enforces the many checks documented
in the README. The Python side has no linter or type checker. Local runs use
Python 3.13 while the Docker image uses 3.12, so the declared floor
(`>=3.12`) is not tested anywhere.
Action: add a CI workflow that runs backend tests on 3.12, the five frontend
checks, and the production spec against a started server; add `ruff` (and
optionally `mypy`) to the dev dependency group.

**M10. `pnpm dev` cannot reach the backend.**
`vite.config.ts` has no `/api` proxy, so the dev server at :5173 shows
"Unable to reach the server" (the README tells people to use it).
Action: add `server.proxy` for `/api` to `http://127.0.0.1:8000`, and document
running uvicorn alongside. This is a development-only setting and does not
replace production routing.

**M11. Accessibility gaps against `frontend/AGENTS.md`.**
- The assistant is a `<dialog open>` rather than a modal: no focus trap, the
  page behind stays reachable, and focus is not returned to "Ask Northstar" on
  close.
- Focus is lost after deleting a card or saving an edit (the focused element
  leaves the DOM); the guidance asks for focus management after dialogs and
  deletions.
- The backdrop is a focusable button with the same name as the real close
  button, creating a duplicate tab stop.
- `aria-label` is set on plain `div`s (`.board-summary`, `.card-list`) where
  it is not reliably announced.
- `.eyebrow` text uses `#888` (`app.css:200`). The frontend guidance itself says
  `#888888` on white fails 4.5:1 for normal text. Several other light grays
  (`#96a1ac`, `#9aa6b1`, `#9aa7b2`) should be measured too.
Action: use `showModal()` or an inert background, restore focus on close, move
focus to a sensible target after delete or save, hide the backdrop from
assistive tech, and run a contrast check over `app.css`.

### Low

- **L1. Weak password storage parameters.** A single static salt
  (`auth.py:12`) and 120,000 PBKDF2-SHA256 rounds (current guidance is far
  higher). Verification only hashes when the user exists, so response time can
  reveal a valid username. Acceptable for the approved hardcoded MVP login;
  revisit if real users are ever added.
- **L2. Sessions are never pruned.** Each login adds a 7-day session row and
  only the one presented is deleted on expiry. Add periodic deletion of expired
  rows.
- **L3. Concurrent UI actions.** `savingAction` holds one value, so overlapping
  actions overwrite each other, and out-of-order responses can briefly show a
  stale board. A single in-flight lock per board would be enough.
- **L4. AI validation stricter than apply in one case.** The simulation ignores
  cards created earlier in the same batch when checking a later move `position`
  (`ai.py:157`). This only rejects valid requests; it cannot corrupt data.
- **L5. Docker.** No `HEALTHCHECK`; `CMD` goes through `uv run` instead of the
  built environment; `.dockerignore` omits `data/` and `*.log` (harmless to the
  image because `COPY` is selective, but it bloats the build context); bind-mounted
  `/app/data` needs write permission for the non-root `app` user.
- **L6. `start.sh` reports success without checking.** It prints "Server
  started" without waiting for the port or detecting an immediate crash, and
  only builds the frontend when `build/index.html` is missing, so stale builds
  are served after frontend changes.
- **L7. Leftover scaffolding.** `/api/example` and `main_paths.py` (a 4-line
  module that exists to avoid an import cycle) could be removed or documented.
- **L8. Same-column reordering is not possible in the UI.** `moveCard` never
  sends `position`, and same-column drops are ignored. This matches the stated
  scope (movement between columns), but the backend `position` support and the
  AI `position` field are unreachable from the UI.
- **L9. Documentation drift.**
  - `DATABASE.md` still says authentication and API work are future phases.
  - `README.md` lists only the health and example endpoints.
  - `scripts/AGENTS.md` and `backend/AGENTS.md` still describe unimplemented
    phases.
  - `PLAN.md` Part 10 marks start and stop verification on "supported
    platforms" as done while `RELEASE.md` says the Windows scripts were never
    run. The Part 2 Windows item is correctly open.
  - `docs/database-schema.json` was not checked against `SCHEMA_SQL`.

## Verified Good

- Every board query joins through `boards.user_id`; no cross-user access path
  was found.
- Session tokens are random, stored only as SHA-256 hashes, sent HTTP-only with
  `SameSite=Lax`, and invalidated on logout and expiry.
- `_frontend_file` resolves and bounds paths, preventing traversal.
- The AI contract rejects extra fields, unknown IDs, conflicting targets, and
  oversized batches, validates the whole batch first, and applies it in one
  transaction. Model output cannot touch another user's data.
- Card content is rendered as text, never with `{@html}`.
- `.env`, databases, logs, and build output are ignored; `.env` is not tracked
  and does not appear in the history for that path. The Docker build excludes
  `.env`, and the container runs as a non-root user.
- `OPENROUTER_API_KEY` is read only on the server and never returned.

## Recommended Order

1. H1 (seed resurrection), H2 (history limit plus error text), H3 (`.env` in the
   start scripts), H4 (localhost binding in docs).
2. M1 (AI robustness and a live AI test), M2 (`/api` 404), M5 (error handling).
3. M9 (CI) and M10 (dev proxy), then M3 and M4.
4. M6 and M7 (refactors), M8 (tests), M11 (accessibility), then the Low items.

Items that change the database schema or the AI contract (M1 multi-operation
per card) need approval under the gates in `docs/PLAN.md` and should update
`docs/AI-OPERATIONS.md` in the same change.
