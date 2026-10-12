# Code review: step-by-step plan

Review of 2026-10-12 (branch `barebones`), converted into a plan. Tick a step only when its change is made and verified. Run `uv run pytest` for backend work, and `pnpm check`, `pnpm lint`, `pnpm test:unit --run` (plus `pnpm exec playwright test` after a `pnpm build`) for frontend work.

Related: [improvements.md](improvements.md) holds the second review (errors, dead code, efficiency). All of its steps are done. Items below that overlap with it are marked as such.

**Scope of the original review:** FastAPI backend, SvelteKit frontend, former standalone scripts, Dockerfile and start scripts. Not reviewed: the Svelte route pages beyond the archive page, and the e2e specs.

**Current baseline:** 113 backend tests, 48 frontend unit tests and 27 e2e tests pass; `pnpm check` and `pnpm lint` are clean.

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

## Status at a glance

| ID | Severity | Title | Status |
| --- | --- | --- | --- |
| S1 | High | No rate limiting or lockout on login | Open |
| S2 | High | Secure cookie flag is off by default | Open |
| S3 | Medium | Jira token kept in a client-side cookie, not bound to the session | Open |
| S4 | Medium | CSRF check trusts a missing `Origin` header and `base_url` behind proxies | Open |
| C1 | Medium | `try/except` around streaming responses can never fire | Open |
| C2 | Medium | Queued runs wait on the lock with no timeout; abandoned runs keep going | Partly done (Jira timeout added) |
| C3 | Medium | Release Check redirected `sys.stdout` process-wide | Done earlier |
| C4 | Low | Archive uses private Jira client internals and mishandles HTTP errors | Open |
| C5 | Low | Unknown `/api/...` GET paths return the SPA HTML with status 200 | Open |
| C6 | Low | `app = create_app()` runs at import time | Open |
| M1 | Medium | Business rules and patterns are duplicated | Partly done |
| M2 | Low | `release_semantic_version.py` is a very large module | Open |
| M3 | Low | Scope has drifted from the "small starter" in `CLAUDE.md` | Open |
| M4 | Low | Defense-in-depth gaps in JQL construction | Open |
| O1 | Low | Lint fails | Done |
| O2 | Low | Sessions are in memory and process-local | Open |
| O3 | Info | Docker image has no healthcheck; start script and image differ | Partly done (`--no-sync` added) |
| T1 | Low | Gaps in test coverage for the risky paths | Partly done |

## Phase 1: close the largest security gaps (S1 now; S2 and S4 prepared now, switched on at TLS)

- [ ] **S2. Make secure cookies the default.** High, small. **Prepare now, flip at TLS.**
  [main.py](../backend/app/main.py) (`COOKIE_SECURE`), [Dockerfile](../Dockerfile).
  Problem: `COOKIE_SECURE` defaults to `false` while the container listens on `0.0.0.0`. A deployment that forgets the variable sends the session and Jira token cookies in clear text.
  - [ ] **Now:** keep the default `COOKIE_SECURE=false`. Document in the README that production must set `COOKIE_SECURE=true` once TLS is on.
  - [ ] **Now:** log a startup warning when `COOKIE_SECURE` is off and the app binds to a non-loopback address.
  - [ ] **At TLS:** set `COOKIE_SECURE=true` in the deployment, then flip the default to secure with an explicit `COOKIE_SECURE=false` opt-out for local HTTP. Set the opt-out in `scripts/start.sh`, `start.ps1` and the README.
  - [ ] **At TLS:** consider `__Host-` cookie names (needs `Secure`, `Path=/`, no `Domain`).
  - [ ] Test that cookies are `Secure` when enabled and not when opted out.
- [ ] **S1. Add login throttling.** High, small. **Now.**
  [main.py](../backend/app/main.py) (`login`), [auth.py](../backend/app/auth.py).
  Problem: every attempt runs a full Argon2 verification, so login is a guessing target and a CPU-exhaustion vector that also starves the shared threadpool.
  - [ ] Add a per-username attempt limit with exponential backoff, in memory (single process; see O2). This works over HTTP and does not depend on a proxy.
  - [ ] Add a per-IP limit only with the real client IP. Behind a proxy every request shares the proxy's IP, so trust `X-Forwarded-For` only from the configured proxy (see S4); until then, skip the per-IP limit or key it on the direct peer address.
  - [ ] Return the same 401 for every failure, and a 429 with `Retry-After` when throttled.
  - [ ] Log failed attempts without the password.
  - [ ] Tests: lockout after N failures, reset on success, throttling does not reveal whether a user exists.
- [ ] **S4. Harden the CSRF check.** Medium, small. **Backward compatible now; stricter at TLS.**
  `ApiAuthMiddleware` in [main.py](../backend/app/main.py).
  Problem: a mutating request with no `Origin` is allowed, and `request.base_url` is built from the `Host` header and scheme the app sees, which is wrong behind a TLS-terminating proxy.
  - [ ] **Now:** add an optional `ALLOWED_ORIGIN` setting. When unset, keep today's comparison with `request.base_url`, so the app behaves exactly as before over HTTP.
  - [ ] **At TLS:** set `ALLOWED_ORIGIN=https://<domain>` (or run uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy>`) **before** switching traffic to the proxy, or every POST returns 403.
  - [ ] **At TLS:** require `Origin`, or fall back to `Referer` or `Sec-Fetch-Site: same-origin`, on non-safe methods; consider `SameSite=Strict` (the app has no cross-site entry flows).
  - [ ] Tests: `ALLOWED_ORIGIN` set and unset, mismatched `Origin`, proxy scheme.

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

- [ ] **C1. Remove the dead `try/except` around streaming responses.** Medium, small.
  The four streaming handlers in [main.py](../backend/app/main.py) wrap `_log_response(...)` in `try/except` and map failures to a 503. The runners return generators, so nothing runs until the response is iterated, and failures arrive through the log instead.
  - [ ] Remove the dead branches and their `log.exception` calls (keep the handler for errors raised while building the request, if any).
  - [ ] Replace the tests that inject a fake raising immediately with one using a generator that raises on first iteration, to pin the real behavior.
- [ ] **C5. Return 404 JSON for unknown `/api/...` GET paths.** Low, small.
  The catch-all `frontend` route in [main.py](../backend/app/main.py) serves `200.html` for `/api/typo`.
  - [ ] Return `404 {"detail": "Not found"}` when the path starts with `api/`.
  - [ ] Test it.
- [ ] **M1. Finish de-duplicating shared rules.** Medium, small. *Partly done.*
  - [x] One version pattern and the issue-type constants now live in `service_versions.py` (done in improvements.md D2).
  - [ ] `archive_released_versions.py` still imports `create_jira_client` from `release_semantic_version`; import it from `jira_credentials`.
  - [ ] Move the shared rules out of `service_versions.py` into a neutral module such as `backend/app/jira_rules.py`, and import from there.

## Phase 3: run lifecycle and token handling (C2, S3)

- [ ] **C2. Bound waiting and document abandoned runs.** Medium, medium. *Partly done.*
  [script_runner.py](../backend/app/script_runner.py).
  - [x] The Jira client now has a `(10, 120)` second timeout (improvements.md I2).
  - [ ] Use `lock.acquire(timeout=...)` and report a clear "still busy" message when it expires, instead of waiting forever with a held thread.
  - [ ] Bound the result queue, or document why unbounded is acceptable.
  - [ ] Document, and log, that a started run completes even if the client leaves (stopping a release half-way is worse).
  - [ ] Test: two concurrent callers, the waiting message, and the timeout.
- [ ] **S3. Bind the Jira token to the session.** Medium, medium.
  `save_jira_token` and `ApiAuthMiddleware` in [main.py](../backend/app/main.py), [jira_credentials.py](../backend/app/jira_credentials.py).
  Problem: the token is a raw cookie sent on every request, outlives the server-side session, and is never checked against the signed-in user.
  - [ ] Decide: keep the token server-side in the session record and send only the session cookie (preferred), or keep the cookie and give it the session's `max_age`.
  - [ ] Verify the token with a cheap Jira call (for example `jira.myself()`) before accepting it.
  - [ ] Update the frontend token dialog and `/api/auth/me` accordingly, and the tests that read the cookie.
- [x] **C3. Release Check no longer redirects `sys.stdout` and now streams.** Done earlier; see `release_check.py`.

## Phase 4: tests for the risky paths (T1)

Add each test alongside the fix it covers.

- [ ] Login throttling (with S1).
- [ ] A streaming endpoint whose generator raises on first iteration (with C1).
- [ ] Concurrent callers on the same workflow lock and the waiting message (with C2).
- [ ] Cross-origin rejection when `Origin` is absent, and behind a proxy (with S4).
- [ ] A failed per-version archive call: one 403 is reported and the run continues (with C4).
- [x] `release_check` output isolation from other threads (covered since C3 was resolved).
- [x] Tracebacks and Jira response bodies never reach the stream (improvements.md E1).

## Phase 5: remaining low-severity fixes

- [ ] **C4. Use the public Jira API to archive.** Low, small.
  `archive_version` in [archive_released_versions.py](../backend/app/archive_released_versions.py) calls private `jira._options` and `jira._session`, and `raise_for_status()` raises `requests.HTTPError`, which `explain_exception` reports as "Unexpected error".
  - [ ] Use `version.update(archived=True)`, or wrap the HTTP error so it is explained like other Jira failures.
  - [ ] Log the explained cause per version, not `str(error)`.
  - [ ] Test a 403 on one version while the run continues.
- [ ] **C6. Build the app at startup, not import.** Low, small.
  `app = create_app()` in [main.py](../backend/app/main.py) loads `.env` and parses `AUTH_USERS_JSON` at import; a malformed value raises at import and "0 users configured" is easy to miss.
  - [ ] Log a clear startup message with the number of users configured.
  - [ ] Consider `uvicorn --factory` in the start scripts and Dockerfile so the app is built at startup.
- [ ] **M4. Validate where JQL is built.** Low, small.
  `service_versions.py` and `release_semantic_version.py` build JQL with f-strings from `project_key` and the version name. The API validates both today, so it is not exploitable.
  - [ ] Validate or escape quotes and backslashes at the point of use.
  - [ ] Unit test with a hostile value.
- [ ] **O2. Document in-memory sessions.** Low, small.
  - [ ] Note in the README that sessions are process-local and lost on restart, and that the container must keep a single worker.
  - [ ] Prune expired sessions on a timer if the user count grows (currently pruned only on login).
- [ ] **O3. Finish the Docker cleanup.** Info, small. *Partly done.*
  - [x] `CMD` uses `uv run --no-sync` (improvements.md D4; Docker not run to confirm).
  - [ ] Add a `HEALTHCHECK` that calls `/api/health`.
  - [ ] Confirm the image builds and starts as the non-root user.
- [x] **O1. `pnpm lint` passes.** Done: `.gitattributes` with `* text=auto eol=lf` and `prettier --write` (improvements.md D3).

## Phase 6: structural changes, last and behavior-neutral

- [ ] **M2. Split `release_semantic_version.py`.** Low, large.
  It mixes configuration, classification, Jira calls, blockers, comment writing and orchestration in one file, and `add_partial_release_comment` and `add_not_released_comment` are near-duplicates.
  - [ ] Do this only with the existing tests as a safety net, one behavior-neutral step at a time.
  - [ ] Split into configuration, rules (pure functions), Jira I/O and the workflow.
  - [ ] Merge the two comment builders.
- [ ] **M3. Update the project description.** Low, small.
  `CLAUDE.md` says to keep the project a small starter, but the app now ships authentication, four Jira workflows and a token dialog. The API title is still "Svelte FastAPI Starter API" and the package is `svelte-fastapi-starter`.
  - [ ] Update `CLAUDE.md`, the README and the AGENTS files to describe a release-management tool.
  - [ ] Rename the API title and the package (and the Docker image name in the docs).

## Positive notes

- Request models validate keys, versions and dates, and reject future archive dates both in the model and in the preview route.
- `explain_exception` gives actionable messages, and tracebacks and Jira response bodies no longer reach the stream.
- Auth: Argon2id parameters are checked at startup, unknown users still pay for a hash comparison, session tokens are stored only as SHA-256 hashes, cookies are HttpOnly and SameSite, and the old session is dropped on login.
- Static file serving guards against path traversal with `relative_to` on the resolved path.
- Every Jira-writing workflow has a dry-run mode and runs under a lock.
- The frontend uses runes and a shared `ScriptRun` state class, and the layout emits events for 401 and 428 so expiry is handled in one place.
