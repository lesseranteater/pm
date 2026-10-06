# Project Management MVP Plan

## Architecture Decisions

- **Frontend:** SvelteKit 2, Svelte 5, TypeScript, and Tailwind CSS.
- **Frontend deployment:** SvelteKit uses `@sveltejs/adapter-static`. FastAPI
  serves the generated `frontend/build/` directory and owns production `/api`
  routes.
- **Backend:** Python FastAPI managed with `uv`.
- **Database:** SQLite, created automatically when it does not exist. Use
  Python's built-in `sqlite3` module for the MVP.
- **Authentication:** One hardcoded user, `user` / `password`, authenticated by
  FastAPI with an HTTP-only server-side session cookie stored in SQLite.
- **AI:** OpenRouter using `openai/gpt-oss-120b`. The API key remains server-side
  in `OPENROUTER_API_KEY`.
- **Packaging:** One Docker container for the FastAPI server and static frontend.
- **State ownership:** Before backend integration, the frontend uses in-memory
  demo state. After integration, SQLite and FastAPI are authoritative.
- **Scope:** Exactly one board per user, five fixed renameable columns, and
  cards with only a title and details. No unrequested features.

## Working Rules

- Complete and verify each phase before starting the next dependent phase.
- Obtain approval at the gates marked **Approval required**.
- Keep API contracts and database schema documented beside the implementation.
- Keep tests deterministic. Mock external services by default.
- Never commit secrets, local databases, generated build output, or dependency
  directories.

## Part 1: Plan And Baseline

### Tasks

- [x] Establish the frontend technology and deployment architecture.
- [x] Define the functional MVP requirements.
- [x] Record the decisions in this document and get user approval.
- [x] Confirm the existing frontend passes its checks before backend work begins.
- [x] Record the API, database, and Docker assumptions that later phases depend on.

### Tests And Verification

- [x] Run `pnpm check`, `pnpm lint`, `pnpm test:unit --run`, `pnpm build`, and
      `pnpm test:e2e` in `frontend/`.
- [x] Confirm the static build is suitable for FastAPI to serve.

### Success Criteria

- [x] The roadmap and architecture decisions are approved.
- [x] The existing frontend remains functional and its baseline checks pass.

## Part 2: Backend And Docker Scaffolding

### Tasks

- [x] Create the FastAPI application under `backend/`.
- [x] Add a health endpoint and a simple example API endpoint.
- [x] Add development and production dependency configuration using `uv`.
- [x] Add configuration loading without committing secrets.
- [x] Build the SvelteKit frontend with `pnpm build` as part of the container build.
- [x] Configure FastAPI to serve `frontend/build/` at `/` and serve the SPA
      fallback for frontend routes while preserving `/api/*` routing.
- [x] Create a Dockerfile for the combined application.
- [x] Add Linux, macOS, and Windows start and stop scripts under `scripts/`.
- [x] Add backend test configuration and a minimal test application fixture.

### Tests And Verification

- [x] Test the health endpoint and example API endpoint.
- [x] Test that the built frontend is served at `/`.
- [x] Test unknown frontend routes use the configured fallback.
- [x] Build the Docker image from a clean dependency install.
- [x] Start the container and verify frontend and API requests.
- [x] Verify the Linux start and stop scripts terminate the application cleanly.
- [ ] Verify the Windows start and stop scripts on Windows. The scripts are
      present but have not been executed in this Linux environment.

### Success Criteria

- [x] One local command starts the complete application.
- [x] The application is reachable through one host port.
- [x] `/` serves the SvelteKit application and `/api/health` responds successfully.
- [x] The container starts without requiring a local Python or Node runtime.

## Part 3: Database Schema And Initialization

**Approval required before implementation.**

### Tasks

- [x] Add the proposed schema as `docs/database-schema.json`.
- [x] Document the database approach in `docs/DATABASE.md`.
- [x] Define tables for users, boards, columns, cards, and sessions.
- [x] Store explicit column and card ordering values.
- [x] Enforce one board per user and ownership relationships with foreign keys.
- [x] Add database initialization that creates the SQLite file and schema if absent.
- [x] Seed the hardcoded user and one five-column board with deterministic demo data.
- [x] Make initialization safe to run repeatedly.

### Proposed Entities

- `users`: user ID, username, password representation, timestamps.
- `boards`: board ID, user ID, name, timestamps.
- `columns`: column ID, board ID, name, fixed position, timestamps.
- `cards`: card ID, column ID, title, details, position, timestamps.
- `sessions`: session ID or token hash, user ID, expiration, timestamps.

### Tests And Verification

- [x] Create the database on a clean temporary path.
- [x] Verify schema creation and foreign-key enforcement.
- [x] Verify deterministic seed data.
- [x] Verify repeated initialization does not duplicate records.
- [x] Verify ordering survives initialization and reload.
- [x] Verify FastAPI startup initializes the database.
- [x] Verify the Docker container creates its database on startup.

### Success Criteria

- [x] The schema is approved and documented.
- [x] A new application instance creates a usable database automatically.
- [x] The seeded user owns exactly one board with five columns.

## Part 4: Authentication

### Tasks

- [x] Add login and logout API routes.
- [x] Accept only `user` / `password` for the MVP.
- [x] Store sessions server-side in SQLite and send an HTTP-only cookie.
- [x] Set secure cookie attributes appropriate for local development and production.
- [x] Add an authenticated-user dependency for protected routes.
- [x] Avoid returning passwords, session tokens, or secret configuration.
- [x] Add a SvelteKit login view and protect the board view.
- [ ] Add logout behavior and unauthenticated redirects.

### Tests And Verification

- [x] Test valid login.
- [x] Test invalid username and password.
- [x] Test missing fields and validation responses.
- [x] Test protected routes without a session.
- [x] Test logout invalidates the session.
- [x] Test session expiration behavior.
- [x] Test browser login, refresh, board access, and logout.

### Success Criteria

- [x] The board cannot be accessed without authentication.
- [x] The supplied credentials provide access.
- [x] Logout removes access immediately.
- [x] Authentication state survives a page refresh while the session is valid.

## Part 5: Kanban Backend API

### Tasks

- [x] Add an authenticated endpoint to read the current user's board.
- [x] Add endpoints to rename columns, create cards, edit cards, delete cards,
      and move cards.
- [x] Validate title, details, IDs, column membership, and ordering inputs.
- [x] Enforce board ownership for every operation.
- [x] Define consistent JSON response and error formats.
- [x] Apply card moves without losing ordering or cards.
- [x] Use transactions for mutations that update multiple records.

### Tests And Verification

- [x] Test every endpoint with valid input.
- [x] Test invalid input and missing resources.
- [x] Test cross-user access prevention.
- [x] Test card ordering after moves.
- [x] Test column rename persistence.
- [x] Test database persistence after application restart.
- [x] Test transaction rollback on mutation failure.

### Success Criteria

- [x] All required Kanban operations are available through authenticated API routes.
- [x] Changes persist in SQLite.
- [x] A user cannot read or modify another user's board.

## Part 6: Frontend And Backend Integration

### Tasks

- [x] Replace frontend-only board state with the FastAPI board API.
- [x] Keep browser requests same-origin through `/api`.
- [x] Centralize repeated requests in a small typed API client.
- [x] Load board data after authentication.
- [x] Refresh or reconcile state after successful mutations.
- [x] Add loading, empty, saving, and error states.
- [x] Preserve unsaved form input after failed requests.
- [x] Ensure the static frontend build is served correctly by FastAPI.

### Tests And Verification

- [x] Test loading the board from the API.
- [x] Test add, edit, delete, move, and rename through the UI.
- [x] Reload after each mutation and verify persistence.
- [x] Test unauthorized API responses and login recovery.
- [x] Test API failures and preserved input.
- [x] Run browser tests against the production container.

### Success Criteria

- [x] The board is persistent and API-backed.
- [x] Refreshing the application preserves changes.
- [x] Existing accessibility and responsive workflows remain functional.

## Part 7: OpenRouter Connectivity

### Tasks

- [ ] Add an OpenRouter client in the backend.
- [ ] Read `OPENROUTER_API_KEY` only from server environment configuration.
- [ ] Use `openai/gpt-oss-120b`.
- [ ] Add request timeouts and clear upstream error handling.
- [ ] Add a backend-only connectivity operation for the `2+2` test.
- [ ] Keep live connectivity tests opt-in when an API key is present.

### Tests And Verification

- [ ] Mock a successful OpenRouter response.
- [ ] Mock timeout and upstream failure responses.
- [ ] Test missing API key behavior.
- [ ] Test invalid upstream response handling.
- [ ] Run the optional live `2+2` connectivity test when credentials are available.

### Success Criteria

- [ ] The backend can make a valid OpenRouter request.
- [ ] Secrets never enter frontend code, API responses, or committed files.
- [ ] Default tests do not require a live API key.

## Part 8: Structured AI Board Operations

### Tasks

- [ ] Define and document the structured AI response schema.
- [ ] Include assistant response text and optional board operations.
- [ ] Send the current board JSON, user question, and conversation history.
- [ ] Support create, edit, move, delete, and column rename operations.
- [ ] Validate the complete AI response before applying changes.
- [ ] Reject unknown IDs, invalid fields, unauthorized changes, and conflicting operations.
- [ ] Apply multiple valid operations transactionally.
- [ ] Return the assistant response and updated board state.

### Tests And Verification

- [ ] Test a valid response with no board changes.
- [ ] Test each supported operation.
- [ ] Test multiple operations in one response.
- [ ] Test malformed structured output.
- [ ] Test unknown IDs and invalid values.
- [ ] Test rollback when one operation in a batch fails.
- [ ] Test conversation history forwarding.

### Success Criteria

- [ ] AI output cannot corrupt persisted board state.
- [ ] Invalid output produces no partial mutation.
- [ ] Valid multi-card changes are applied consistently.

## Part 9: AI Sidebar

### Tasks

- [ ] Add an accessible responsive chat sidebar to the SvelteKit UI.
- [ ] Display conversation history, pending state, and errors.
- [ ] Submit authenticated questions to the backend.
- [ ] Display assistant responses.
- [ ] Refresh the board automatically after AI mutations.
- [ ] Prevent duplicate submissions while a request is pending.
- [ ] Support keyboard and narrow-screen use.

### Tests And Verification

- [ ] Test opening and closing the sidebar.
- [ ] Test submitting a question and displaying the response.
- [ ] Test backend errors and retry behavior.
- [ ] Test one AI board update.
- [ ] Test multiple AI board updates.
- [ ] Verify the board refreshes without a full page reload.

### Success Criteria

- [ ] Users can manage the board manually and through AI chat.
- [ ] AI changes are visible immediately and remain persisted after reload.

## Part 10: Final Container And Release Verification

### Tasks

- [ ] Build the static frontend as part of the Docker build.
- [ ] Serve the built frontend and FastAPI routes from one container.
- [ ] Store SQLite data in a documented mounted volume.
- [ ] Pass environment variables safely without baking secrets into the image.
- [ ] Verify start and stop scripts on supported platforms.
- [ ] Update README files with development, testing, build, and container commands.
- [ ] Review logs for accidental secrets and excessive sensitive data.

### Tests And Verification

- [ ] Build from a clean checkout.
- [ ] Start the container with an empty data volume.
- [ ] Complete login and all core board workflows.
- [ ] Restart the container and verify data survives with the volume retained.
- [ ] Verify the AI path with mocked upstream responses.
- [ ] Verify the frontend, API, authentication, database, and AI boundaries together.

### Success Criteria

- [ ] A clean checkout can build and start the complete application.
- [ ] SQLite data survives container restarts when its volume is retained.
- [ ] The complete authenticated Kanban and AI workflows pass in the container.
- [ ] Known limitations and verification results are documented.

## Approval Gates

1. **Plan approval:** approve this roadmap and architecture decisions before
   backend scaffolding.
2. **Schema approval:** approve `docs/database-schema.json` and database
   documentation before implementing persistence.
3. **AI contract approval:** approve the structured AI response schema before
   connecting AI mutations to the board.
4. **Release approval:** review the complete Docker workflow and test results
   before considering the broader MVP complete.
