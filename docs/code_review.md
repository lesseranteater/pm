# Code review: step-by-step plan

Review of 2026-10-12 (branch `barebones`), converted into a plan. Tick a step only when its change is made and verified. Run `uv run pytest` for backend work, and `pnpm check`, `pnpm lint`, `pnpm test:unit --run` (plus `pnpm exec playwright test` after a `pnpm build`) for frontend work.

Related: [improvements.md](improvements.md) holds the second review (errors, dead code, efficiency). All of its steps are done. Items below that overlap with it are marked as such.

**Scope of the original review:** FastAPI backend, SvelteKit frontend, former standalone scripts, Dockerfile and start scripts. Not reviewed: the Svelte route pages beyond the archive page, and the e2e specs.

**Current baseline:** 155 backend tests, 48 frontend unit tests and 28 e2e tests pass; `pnpm check` and `pnpm lint` are clean.

**Summary of the original findings:** the app is well structured and tested, inputs are validated at the API boundary, and Argon2id with a dummy hash, hashed session tokens and HttpOnly cookies are sound. The main risks were in the authentication layer (no login throttling, secure cookies off by default, Jira token in a plain cookie) and in how long-running Jira scripts are run (lock waits, abandoned runs).

## Constraint: HTTPS is not available yet

The app currently runs over plain HTTP, and a domain name with TLS is planned. Until TLS is live, no step may change behavior that depends on HTTPS. In particular:

- Browsers do not send `Secure` cookies over plain HTTP (except on `localhost`), so turning them on breaks login.
- Behind a TLS-terminating proxy, uvicorn sees `http` while the browser sends an `https://` `Origin`, so the current origin check would reject every POST.

Each step below is marked **now** (safe over HTTP today) or **at TLS** (do it when HTTPS goes live). Every change must keep working over HTTP with no new required settings.

## SSL and domain: recommendations

Recommendation recorded 2026-10-12. The app will later run behind a domain name with SSL/TLS. This section says how that changes the findings. The actions are tracked in the steps below and in the cut-over checklist (Phase 1b). Whether TLS ends at a reverse proxy, a load balancer or uvicorn itself is not decided yet, and several points depend on it.

**What changes**

- **S4 (CSRF check) becomes a deployment blocker behind a TLS-terminating proxy.** The middleware compares the browser's `Origin` header with `request.base_url`. Behind a proxy, uvicorn sees `http` while the browser sends `https://<domain>`, so every POST, including login, would get a 403.
  - Recommended: a configured `ALLOWED_ORIGIN=https://<domain>`, set before traffic moves to the proxy. Alternatively run uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy>`.
  - If uvicorn terminates TLS itself, the scheme is correct and nothing breaks. The configured origin is still preferred.
- **S1 (login throttling) needs the real client IP.** Behind a proxy every request appears to come from the proxy, so a per-IP limit would lock all users out together.
  - Recommended: take the IP from `X-Forwarded-For` only when the request comes from the configured proxy, so the header cannot be spoofed.
  - A per-username limit does not depend on the proxy and can be done now.
- **S2 (secure cookies) gets simpler.** Set `COOKIE_SECURE=true` in the deployment, and flip the default to secure once HTTPS is live.
  - With a fixed domain, `__Host-` cookie names (`Secure`, `Path=/`, no `Domain`) are worth considering.
- **The container must not be reachable directly.** The image listens on `0.0.0.0:8000`. If that port is published, the app can be reached over plain HTTP, bypassing TLS. Recommended: bind it to `127.0.0.1` or an internal network so only the proxy can reach it.

**New items to add once HTTPS is live**

- Redirect HTTP to HTTPS at the proxy.
- `Strict-Transport-Security` (start with a short `max-age`, then lengthen it).
- `TrustedHostMiddleware` with the domain.
- `X-Content-Type-Options`, `Content-Security-Policy` and `frame-ancestors` headers. The original review did not cover these.

**What does not change**

- **S3 (Jira token in a cookie):** TLS protects it in transit, and `Secure` plus `HttpOnly` help, but the token still outlives the session and is not tied to the user. The server-side fix stays worthwhile.
- **C1, C2, C4 and O2:** unaffected by TLS.

**Ordering rule:** nothing that depends on HTTPS may be switched on before HTTPS exists. `Secure` cookies are not sent over plain HTTP (except on `localhost`), so enabling them early breaks login. Steps marked "now" are safe over HTTP today; steps marked "at TLS" wait for the cut-over.

## Dependency audit (2026-10-12)

- Python (`pip-audit` on the locked runtime dependencies): no known vulnerabilities.
- Frontend (`pnpm audit`): one low-severity advisory, `cookie` below 0.7 via `@sveltejs/kit`. The app is a static build, so that code is not shipped. Update SvelteKit when a release pulls in `cookie` 0.7 or newer.

## Real Jira findings (2026-10-12)

A read-only probe ran against the real Jira (self-hosted, version 9.17.0) with the `JIRA_TOKEN` from `.env`. Only GET and HEAD requests were allowed, and none were refused. The release steps were dry runs. Project: IGM, test version `Deploy.ai-data.26.4.1`.

| Question | Result | Consequence |
| --- | --- | --- |
| Page size cap (improvements.md E5) | Asking for 1000 issues returned 1000; IGM has 18,995. | The old "short page means the end" logic would not have truncated here. The `total`-based paging stays as a harmless safeguard. |
| `get_server_info=False` (I2) | Works, with the same search and version results. Saves one request (about 0.3 s) per client and leaves the library version at `(0, 0, 0)`. | **Do not do it.** The saving is negligible. |
| `myself()` with a personal access token (S3) | Works. | Verifying the token on save is feasible. It remains a decision: a Jira outage would then block saving a token. |
| Archive request shape (C4) | The version's own URL has the `/rest/api/2/version/{id}` form, the endpoint the old code called. | `version.update(archived=True)` is equivalent. The call itself is still untested, because nothing was archived. |
| Dry-run release (real app code) | 11 requests in 0.4 s, no errors, 4 warnings (a non-terminal deployment plan, an already Published story, a dry-run comment, the manual-update notice). | The workflow behaves as expected on real data. |
| Service-version report, release check | 5 requests each, 0.2 s, no errors. | |
| Archive previews | Each preview builds a fresh client, which costs one extra `serverInfo` request. By date up to today: 302 versions (158 semantic, 144 service). | Minor. A live archive dated today would archive all 302, so choose the date deliberately. |

Not measured: the saving from I1 (subtasks loaded once per parent for the pre-release checks), because the old code could not be run and this version has few parents.

Open observation: the release tool is hard-wired to project IGM (`PROJECT_KEY` in `release_semantic_version.py`), and its page has no project field. The probe had to patch the constant to use another project.

## Status at a glance

| ID | Severity | Title | Status |
| --- | --- | --- | --- |
| S1 | High | No rate limiting or lockout on login | Partly done (per-username; per-IP at TLS) |
| S2 | High | Secure cookie flag is off by default | Partly done (warning and docs; flip at TLS) |
| S3 | Medium | Jira token kept in a client-side cookie, not bound to the session | Done (no Jira verification call) |
| S4 | Medium | CSRF check trusts a missing `Origin` header and `base_url` behind proxies | Partly done (`ALLOWED_ORIGIN`; stricter rules at TLS) |
| C1 | Medium | `try/except` around streaming responses can never fire | Done |
| C2 | Medium | Queued runs wait on the lock with no timeout; abandoned runs keep going | Done |
| C3 | Medium | Release Check redirected `sys.stdout` process-wide | Done earlier |
| C4 | Low | Archive uses private Jira client internals and mishandles HTTP errors | Done |
| C5 | Low | Unknown `/api/...` GET paths return the SPA HTML with status 200 | Done |
| C6 | Low | `app = create_app()` runs at import time | Partly done (startup message; `--factory` skipped) |
| M1 | Medium | Business rules and patterns are duplicated | Done |
| M2 | Low | `release_semantic_version.py` is a very large module | Partly done |
| M3 | Low | Scope has drifted from the "small starter" in `CLAUDE.md` | Done (names kept) |
| M4 | Low | Defense-in-depth gaps in JQL construction | Done |
| O1 | Low | Lint fails | Done |
| O2 | Low | Sessions are in memory and process-local | Done (documented) |
| O3 | Info | Docker image has no healthcheck; start script and image differ | Done, unverified (Docker not installed here) |
| T1 | Low | Gaps in test coverage for the risky paths | Partly done |

## Phase 1: close the largest security gaps (S1 now; S2 and S4 prepared now, switched on at TLS)

- [ ] **S2. Make secure cookies the default.** High, small. **Prepare now, flip at TLS.**
  [main.py](../backend/app/main.py) (`COOKIE_SECURE`), [Dockerfile](../Dockerfile).
  Problem: `COOKIE_SECURE` defaults to `false` while the container listens on `0.0.0.0`. A deployment that forgets the variable sends the session and Jira token cookies in clear text.
  - [x] **Now:** keep the default `COOKIE_SECURE=false`. Document in the README that production must set `COOKIE_SECURE=true` once TLS is on.
  - [x] **Now:** log a startup warning when `COOKIE_SECURE` is off. (Done as an always-on warning, because the app cannot see its bind address.)
  - [ ] **At TLS:** set `COOKIE_SECURE=true` in the deployment, then flip the default to secure with an explicit `COOKIE_SECURE=false` opt-out for local HTTP. Set the opt-out in `scripts/start.sh`, `start.ps1` and the README.
  - [ ] **At TLS:** consider `__Host-` cookie names (needs `Secure`, `Path=/`, no `Domain`).
  - [ ] Test that cookies are `Secure` when enabled and not when opted out.
- [ ] **S1. Add login throttling.** High, small. **Now.**
  [main.py](../backend/app/main.py) (`login`), [auth.py](../backend/app/auth.py).
  Problem: every attempt runs a full Argon2 verification, so login is a guessing target and a CPU-exhaustion vector that also starves the shared threadpool.
  - [x] Add a per-username attempt limit with exponential backoff, in memory (single process; see O2). This works over HTTP and does not depend on a proxy.
  - [ ] Add a per-IP limit only with the real client IP. Behind a proxy every request shares the proxy's IP, so trust `X-Forwarded-For` only from the configured proxy (see S4); until then, skip the per-IP limit or key it on the direct peer address.
  - [x] Return the same 401 for every failure, and a 429 with `Retry-After` when throttled.
  - [x] Log failed attempts without the password.
  - [x] Tests: lockout after N failures, reset on success, throttling does not reveal whether a user exists.
- [ ] **S4. Harden the CSRF check.** Medium, small. **Backward compatible now; stricter at TLS.**
  `ApiAuthMiddleware` in [main.py](../backend/app/main.py).
  Problem: a mutating request with no `Origin` is allowed, and `request.base_url` is built from the `Host` header and scheme the app sees, which is wrong behind a TLS-terminating proxy.
  - [x] **Now:** add an optional `ALLOWED_ORIGIN` setting. When unset, keep today's comparison with `request.base_url`, so the app behaves exactly as before over HTTP.
  - [ ] **At TLS:** set `ALLOWED_ORIGIN=https://<domain>` (or run uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy>`) **before** switching traffic to the proxy, or every POST returns 403.
  - [ ] **At TLS:** require `Origin`, or fall back to `Referer` or `Sec-Fetch-Site: same-origin`, on non-safe methods; consider `SameSite=Strict` (the app has no cross-site entry flows).
  - [x] Tests: `ALLOWED_ORIGIN` set and unset, mismatched `Origin`, proxy scheme.

## Phase 1b: TLS cut-over checklist (do when HTTPS goes live, not before)

- [ ] Terminate TLS at a proxy or in uvicorn; redirect HTTP to HTTPS.
- [ ] Set `ALLOWED_ORIGIN=https://<domain>` and `COOKIE_SECURE=true`; verify login and a tool run over HTTPS in a browser.
- [ ] Do not publish container port 8000 directly; bind it to `127.0.0.1` or an internal network so only the proxy reaches it.
- [ ] Add `TrustedHostMiddleware` with the domain.
- [ ] Send `Strict-Transport-Security` once HTTPS is confirmed working (start with a short `max-age`).
- [ ] Add `X-Content-Type-Options`, `Content-Security-Policy` and `frame-ancestors` headers.
- [ ] Configure the trusted proxy address for `X-Forwarded-For`, then enable the per-IP login limit (S1).
- [ ] Flip the `COOKIE_SECURE` default (S2) and tighten the `Origin` rule (S4).

## Phase 2: remove misleading code and duplication (C1, C5, M1)

- [x] **C1. Remove the dead `try/except` around streaming responses.** Medium, small.
  The four streaming handlers in [main.py](../backend/app/main.py) wrap `_log_response(...)` in `try/except` and map failures to a 503. The runners return generators, so nothing runs until the response is iterated, and failures arrive through the log instead.
  - [x] Remove the dead branches and their `log.exception` calls (keep the handler for errors raised while building the request, if any).
  - [x] Replace the tests that inject a fake raising immediately with one using a generator that raises on first iteration, to pin the real behavior.
- [x] **C5. Return 404 JSON for unknown `/api/...` GET paths.** Low, small.
  The catch-all `frontend` route in [main.py](../backend/app/main.py) serves `200.html` for `/api/typo`.
  - [x] Return `404 {"detail": "Not found"}` when the path starts with `api/`.
  - [x] Test it.
- [x] **M1. Finish de-duplicating shared rules.** Medium, small. *Partly done.*
  - [x] One version pattern and the issue-type constants now live in `service_versions.py` (done in improvements.md D2).
  - [x] `archive_released_versions.py` imports `create_jira_client` from `jira_credentials`.
  - [x] The shared rules now live in `backend/app/jira_rules.py` (version pattern, issue types, project-key regex), imported everywhere.

## Phase 3: run lifecycle and token handling (C2, S3)

- [x] **C2. Bound waiting and document abandoned runs.** Medium, medium. *Partly done.*
  [script_runner.py](../backend/app/script_runner.py).
  - [x] The Jira client now has a `(10, 120)` second timeout (improvements.md I2).
  - [x] Use `lock.acquire(timeout=...)` (15 minutes, `LOCK_WAIT_SECONDS`) and report a clear "still busy" message when it expires, instead of waiting forever with a held thread.
  - [x] Result queue stays unbounded on purpose, documented in `stream_script_log`: a bounded queue would let a slow client block a run that holds the lock.
  - [x] Document, and log, that a started run completes even if the client leaves (stopping a release half-way is worse). A queued run whose client has left now never starts.
  - [x] Test: two concurrent callers, the waiting message, and the timeout; plus abandoned-while-queued and abandoned-mid-run.
- [x] **S3. Bind the Jira token to the session.** Medium, medium. Done, except the optional Jira verification call (see below).
  `save_jira_token` and `ApiAuthMiddleware` in [main.py](../backend/app/main.py), [jira_credentials.py](../backend/app/jira_credentials.py).
  Problem: the token is a raw cookie sent on every request, outlives the server-side session, and is never checked against the signed-in user.
  - [x] The token is kept server-side in `Authentication.jira_tokens`, keyed by session, and dropped on logout, expiry and restart. The `pm_jira_token` cookie is no longer set; a leftover one is ignored and cleared at sign-in.
  - [ ] Verify the token with a cheap Jira call (for example `jira.myself()`) before accepting it. Not done: a real Jira confirmed `myself()` works with a personal access token (see "Real Jira findings"), but a Jira outage would then block saving a token. Decide first.
  - [x] `/api/auth/me` and the middleware read the server-side token; the frontend needed no change because the API is the same. Tests rewritten, and a live HTTP check confirmed the token never appears in a cookie.
- [x] **C3. Release Check no longer redirects `sys.stdout` and now streams.** Done earlier; see `release_check.py`.

## Phase 4: tests for the risky paths (T1)

Add each test alongside the fix it covers.

- [x] Login throttling (with S1).
- [x] A streaming endpoint whose generator raises on first iteration (with C1).
- [x] Concurrent callers on the same workflow lock and the waiting message (with C2).
- [ ] Cross-origin rejection when `Origin` is absent, and behind a proxy (with S4). `ALLOWED_ORIGIN` set and unset is tested; the absent-`Origin` rule waits for TLS.
- [x] A failed per-version archive call: one 403 is reported and the run continues (with C4).
- [x] `release_check` output isolation from other threads (covered since C3 was resolved).
- [x] Tracebacks and Jira response bodies never reach the stream (improvements.md E1).

## Phase 5: remaining low-severity fixes

- [x] **C4. Use the public Jira API to archive.** Low, small.
  `archive_version` in [archive_released_versions.py](../backend/app/archive_released_versions.py) calls private `jira._options` and `jira._session`, and `raise_for_status()` raises `requests.HTTPError`, which `explain_exception` reports as "Unexpected error".
  - [x] Use `version.update(archived=True)` (same `PUT {"archived": true}`, public API, raises `JIRAError`).
  - [x] Log the explained cause per version, not `str(error)`.
  - [x] Test a 403 on one version while the run continues.
- [ ] **C6. Build the app at startup, not import.** Low, small.
  `app = create_app()` in [main.py](../backend/app/main.py) loads `.env` and parses `AUTH_USERS_JSON` at import; a malformed value raises at import and "0 users configured" is easy to miss.
  - [x] Log a clear startup message with the number of users configured (warns when there are none).
  - [ ] Consider `uvicorn --factory` in the start scripts and Dockerfile so the app is built at startup.
- [x] **M4. Validate where JQL is built.** Low, small.
  `service_versions.py` and `release_semantic_version.py` build JQL with f-strings from `project_key` and the version name. The API validates both today, so it is not exploitable.
  - [x] `jql_project` and `jql_quote` in `jira_rules.py` are used where both JQL strings are built.
  - [x] Unit tests with hostile values.
- [ ] **O2. Document in-memory sessions.** Low, small.
  - [x] Note in the README that sessions are process-local and lost on restart, and that the container must keep a single worker.
  - [ ] Prune expired sessions on a timer if the user count grows (currently pruned only on login).
- [ ] **O3. Finish the Docker cleanup.** Info, small. *Partly done.*
  - [x] `CMD` uses `uv run --no-sync` (improvements.md D4; Docker not run to confirm).
  - [x] Add a `HEALTHCHECK` that calls `/api/health` (Python one-liner; Docker is not installed here, so it is unverified).
  - [ ] Confirm the image builds and starts as the non-root user.
- [x] **O1. `pnpm lint` passes.** Done: `.gitattributes` with `* text=auto eol=lf` and `prettier --write` (improvements.md D3).

## Phase 6: structural changes, last and behavior-neutral

- [ ] **M2. Split `release_semantic_version.py`.** Low, large. Partly done: 1,154 lines became 908, plus `release_rules.py` (178) and `release_comments.py` (71).
  It mixes configuration, classification, Jira calls, blockers, comment writing and orchestration in one file, and `add_partial_release_comment` and `add_not_released_comment` are near-duplicates.
  - [x] Safety net first: `test_release_workflow_golden.py` runs four scenarios through a fake Jira and compares the full log and every Jira write with files in `backend/tests/golden/`. The refactor left them untouched.
  - [x] Configuration and the pure rules moved to `release_rules.py`.
  - [ ] Jira I/O and the workflow still share `release_semantic_version.py`, and `evaluate_parent` is still one long function. Splitting it further is optional.
  - [x] The two comment builders are merged into `build_release_state_comment` in `release_comments.py`, with one poster, `add_release_state_comment`.
- [x] **M3. Update the project description.** Low, small. Wording done; package and image rename skipped.
  `CLAUDE.md` says to keep the project a small starter, but the app now ships authentication, four Jira workflows and a token dialog. The API title is still "Svelte FastAPI Starter API" and the package is `svelte-fastapi-starter`.
  - [x] `CLAUDE.md`, `AGENTS.md`, the README, the API title, and the package docstring and description now describe a release-management tool.
  - [ ] Rename the Python package, the Docker image name and the `.starter-server.*` file names. Skipped on purpose: it changes `uv.lock`, the build commands and the start scripts for no functional gain.

## Positive notes

- Request models validate keys, versions and dates, and reject future archive dates both in the model and in the preview route.
- `explain_exception` gives actionable messages, and tracebacks and Jira response bodies no longer reach the stream.
- Auth: Argon2id parameters are checked at startup, unknown users still pay for a hash comparison, session tokens are stored only as SHA-256 hashes, cookies are HttpOnly and SameSite, and the old session is dropped on login.
- Static file serving guards against path traversal with `relative_to` on the resolved path.
- Every Jira-writing workflow has a dry-run mode and runs under a lock.
- The frontend uses runes and a shared `ScriptRun` state class, and the layout emits events for 401 and 428 so expiry is handled in one place.
