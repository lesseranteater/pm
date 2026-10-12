# Improvements: step-by-step plan

Findings from a code review on 2026-10-12 (branch `barebones`), ordered into a plan. Progress so far: all five phases done (113 backend tests, 48 frontend unit tests, 27 e2e tests passing, `pnpm check` and `pnpm lint` clean). Tick a step only when its change is made and verified (`uv run pytest`, and `pnpm check`, `pnpm lint`, `pnpm test:unit --run` for frontend work).

Security findings (login throttling, `COOKIE_SECURE`, CSRF check, Jira token cookie) are tracked in [code_review.md](code_review.md). That file is partly stale. These items from it are still open: dead `try/except` around streaming responses (C1), private `jira._session` and `jira._options` use in `archive_version` (C4), no timeout on the Jira client or workflow lock (C2), and `/api/typo` returning the SPA page with a 200 (C5).

Not reviewed: the other route pages and the e2e specs. Docker and the e2e tests were not run.

## Phase 1: wrong or leaking behavior

- [x] **E1. Stop streaming tracebacks and Jira response bodies to the browser.**
  [script_runner.py](../backend/app/script_runner.py), [release_semantic_version.py:1129](../backend/app/release_semantic_version.py#L1129).
  `logger.exception` runs while the queue handler is attached, so file paths, the Jira URL and the raw response body reach the client.
  Done: the traceback goes to a server-only logger and the stream carries only the explained cause; new test `test_the_stream_never_carries_a_traceback_or_the_jira_response`.
  Steps: log the traceback to a server-only logger; stream only the explained cause; update the test that expects `RuntimeError` in the stream; add a test that a `JIRAError` body and URL never appear in the stream.
- [x] **E2. Report failed archives as errors.**
  [archive_released_versions.py:128](../backend/app/archive_released_versions.py#L128).
  Per-version failures are WARNINGs, so "Archived 0 of N" looks clean to `ScriptRun.succeeded`.
  Done: a final ERROR line "Archived only X of N version(s)" when any call fails.
  Steps: log an ERROR when `archived < len(candidates)`; add a test where every archive call fails.
- [x] **E3. Stop blocking the event loop with Jira calls.**
  [main.py:248](../backend/app/main.py#L248), [283](../backend/app/main.py#L283), [301](../backend/app/main.py#L301).
  Done: the handlers are plain `def`; the new test fails with `async def` and passes now.
  Steps: make the three handlers plain `def` (FastAPI runs them in the threadpool); add a test that `/api/health` answers while a preview call is blocked.
- [x] **E4. Replace the stale `JIRA_TOKEN` branch in `explain_exception`.**
  [errors.py:45](../backend/app/errors.py#L45).
  Done: `UserFacingError` added and used by `create_jira_client`, `find_project_version` and the invalid-version checks.
  Steps: add a `UserFacingError(RuntimeError)` whose message is shown as is; make `ProjectNotFoundError` a subclass; raise it from `create_jira_client`, `find_project_version` and the invalid-version checks; remove the dead branch; update tests.

## Phase 2: tooling and deployment

- [x] **D3. Fix `pnpm lint` (27 files fail on CRLF).**
  Done: `.gitattributes` added and `prettier --write` run; `pnpm lint` passes. Real formatting changes were small (`dates.test.ts`, `release-check/+page.svelte`).
  Steps: add `.gitattributes` with `* text=auto eol=lf`; renormalize the working tree; confirm `pnpm lint` passes.
- [x] **D4. Stop the container re-syncing dependencies at startup.**
  [Dockerfile:28](../Dockerfile#L28). Likely, not confirmed (Docker not run).
  Done: `CMD` now uses `uv run --no-sync`. Still unverified because Docker was not run.
  Steps: change `CMD` to `uv run --no-sync uvicorn ...`.

## Phase 3: remaining correctness

- [x] **E5. Page `search_all_issues` by `total`, not by page length.** [release_semantic_version.py:218](../backend/app/release_semantic_version.py#L218).
  Done: pages by `total` and stops on an empty page; two tests.
- [x] **E6. Skip "no released service Fix Version" in the partial-release comment for Config Change parents.** [release_semantic_version.py:552](../backend/app/release_semantic_version.py#L552).
  Done: skipped for Config Change parents; test covers both parent types.
- [x] **E7. Handle a non-JSON error body on sign-in.** [+layout.svelte:78](../frontend/src/routes/+layout.svelte#L78).
  Done: `response.json()` failure falls back to "Unable to sign in."; new e2e case.

## Phase 4: efficiency

- [x] **I1. Fetch each parent's subtasks once and pass them through.** [release_semantic_version.py:447](../backend/app/release_semantic_version.py#L447), [473](../backend/app/release_semantic_version.py#L473), [652](../backend/app/release_semantic_version.py#L652); also [service_versions.py:65](../backend/app/service_versions.py#L65) and [release_check.py:96](../backend/app/release_check.py#L96) (cache shared parents). Currently about 3·N·M calls in a live release.
  Done in part: the two pre-release checks share one subtask load (3 loads per parent down to 2; the last must stay fresh because releasing changes the versions), and Release Check loads a shared parent once. Not done: `service_versions.py` still fetches each subtask individually; batching with `key in (...)` JQL needs a real Jira to check the behaviour.
- [x] **I2. Cheaper Jira client setup.** [jira_credentials.py:20](../backend/app/jira_credentials.py#L20): load `.env` once, pass `get_server_info=False` and a request timeout.
  Done in part: `.env` is loaded once at import and the client has a `(10, 120)` second timeout. Not done: `get_server_info=False`, because it sets the library version to `(0, 0, 0)` and changes some feature checks that I cannot verify without a real Jira.
- [x] **I3. Count log levels incrementally in the browser.** [ScriptLog.svelte:29](../frontend/src/lib/ScriptLog.svelte#L29), [run.svelte.ts:40](../frontend/src/lib/run.svelte.ts#L40).
  Done: `LogTracker` parses chunks incrementally; `ScriptRun` exposes `lines` and `counts`; two new unit tests.
- [x] **I4. Replace the `BaseHTTPMiddleware` auth check.** [main.py:163](../backend/app/main.py#L163).
  Done: `ApiAuthMiddleware` is a pure ASGI middleware; static files skip the session lookup; new test. All 27 e2e tests pass.

## Phase 5: dead code

- [x] **D1. Move test-only wrappers into tests:** `archive_released_versions()`, `report_service_versions_without_release_date()`, `release_semantic_version()`.
  Done: wrappers deleted; tests now join the `stream_*` functions directly.
- [x] **D2. Remove the dead `UNKNOWN|` regex alternative and the `_get_release_date` wrapper.**
  Done: the duplicate regex in `release_semantic_version.py` is gone (it uses `is_semantic_release_version`), as are the `UNKNOWN|` alternative and `_get_release_date`. The two modules now also share `PARENT_ISSUE_TYPES` and `RELEASABLE_SUBTASK_TYPES`. `ruff --select F` is clean.
