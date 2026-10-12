# Code Review

- **Date:** 2026-10-12
- **Branch:** `barebones` (includes uncommitted auth work: `backend/app/auth.py`, `main.py`, `frontend/src/routes/+layout.svelte`, related tests)
- **Scope:** FastAPI backend (`backend/app`), SvelteKit frontend (`frontend/src`), `tools/`, Dockerfile and start scripts.
- **Method:** Manual read of the backend, the auth and streaming paths, and the frontend layout and API helpers. I read about two thirds of `release_semantic_version.py` (1,154 lines) in detail and did not trace its Jira business rules line by line. I did not read the Svelte route pages or the e2e specs, and I did not run the Playwright e2e tests.

## Verification

| Check | Result |
| --- | --- |
| `uv run pytest` | 93 passed |
| `pnpm check` | 0 errors, 0 warnings |
| `pnpm test:unit --run` | 44 passed |
| `pnpm lint` | **Fails**: Prettier reports style issues in 30 files (I did not diagnose the cause; line endings are a likely candidate on Windows) |

## Summary

The app is well structured and well tested. Inputs are validated at the API boundary, and the Jira error messages are safe. Argon2id with a dummy hash on unknown users is a good choice, and so are hashed session tokens and HttpOnly cookies.

The main risks are in the new authentication layer and in how long-running Jira scripts are run:

1. Login has no brute-force protection.
2. The user's Jira token is stored in a plain cookie that is not bound to the session.
3. `COOKIE_SECURE` defaults to off while the Docker image listens on `0.0.0.0`.
4. A queued run can wait forever on a lock, and a disconnected client does not stop a run.
5. The Release Check stream is not a real stream, and it redirects `stdout` for the whole process.

Findings are ordered by severity. Each has an ID so it can be referenced in follow-up work.

| ID | Severity | Area | Title |
| --- | --- | --- | --- |
| S1 | High | Security | No rate limiting or lockout on login |
| S2 | High | Security | Secure cookie flag is off by default; image binds to `0.0.0.0` |
| S3 | Medium | Security | Jira token kept in a client-side cookie, not bound to the session |
| S4 | Medium | Security | CSRF check trusts a missing `Origin` header and `base_url` behind proxies |
| C1 | Medium | Correctness | `try/except` around streaming responses can never fire |
| C2 | Medium | Correctness | Queued runs wait on the lock with no timeout; abandoned runs keep going |
| C3 | Medium | Correctness | Release Check redirects `sys.stdout` process-wide and does not stream |
| C4 | Low | Correctness | Archive treats an HTTP error from Jira differently from `JIRAError` and uses private client internals |
| C5 | Low | Correctness | Unknown `/api/...` GET paths return the SPA HTML with status 200 |
| C6 | Low | Correctness | `app = create_app()` runs at import time and can fail on bad config |
| M1 | Medium | Maintainability | Business rules and patterns are duplicated across modules |
| M2 | Low | Maintainability | `release_semantic_version.py` is a 1,154-line module |
| M3 | Low | Maintainability | Scope has drifted from the "small starter" described in `CLAUDE.md` |
| M4 | Low | Maintainability | Defense-in-depth gaps in JQL construction |
| O1 | Low | Operations | Lint fails; Prettier is not clean |
| O2 | Low | Operations | Sessions are in memory and process-local |
| O3 | Info | Operations | Docker image has no healthcheck; start script and image differ in bind address |
| T1 | Low | Tests | Gaps in test coverage for the risky paths |

---

## Security

### S1. No rate limiting or lockout on login — High

- **Where:** [main.py:166-179](../backend/app/main.py#L166-L179), [auth.py:47-53](../backend/app/auth.py#L47-L53)
- **Problem:** `/api/auth/login` can be called without limit. Each attempt runs a full Argon2 verification, so it is both a password-guessing target and a CPU-exhaustion vector. Verification runs in the shared threadpool, so a flood of attempts also starves the streaming endpoints.
- **Recommendation:** Add a per-username and per-IP attempt limit with exponential backoff, kept in memory (the app is single-process; see O2). Return the same 401 for every failure. Log failed attempts without logging the password.
- **Effort:** Small.

### S2. Secure cookie flag is off by default; image binds to `0.0.0.0` — High

- **Where:** [main.py:134](../backend/app/main.py#L134), [Dockerfile](../Dockerfile), commit `c628cca`
- **Problem:** `COOKIE_SECURE` defaults to `false`, and the container (and, per the latest commit, the server host) listens on all interfaces. A deployment that forgets the variable sends the session cookie and the Jira token cookie in clear text. The default fails open.
- **Recommendation:** Default to secure cookies and add an explicit `COOKIE_SECURE=false` opt-out for local HTTP development (or derive it from the request scheme and `X-Forwarded-Proto` when behind a trusted proxy). Document the TLS requirement in the README.
- **Effort:** Small.

### S3. Jira token kept in a client-side cookie, not bound to the session — Medium

- **Where:** [main.py:188-194](../backend/app/main.py#L188-L194), [main.py:136-164](../backend/app/main.py#L136-L164)
- **Problem:**
  - The user's personal Jira access token is stored as a raw cookie value. It is sent on every request, including static asset requests, and it survives in the browser until it is deleted.
  - It is not tied to the login session: the cookie is cleared on login and logout, but the session expiring server-side (7 days) leaves the token cookie behind. The middleware does ignore it without a valid session, so this is hygiene, not a bypass.
  - A user can run Jira write operations (release, archive) with any token pasted in, and nothing checks that the token belongs to the signed-in user.
- **Recommendation:** Keep the token server-side in the session record (in memory, next to the session) and send only the session cookie. If the cookie approach stays, give it the same `max_age` as the session and verify the token with a cheap Jira call (for example `jira.myself()`) before accepting it.
- **Effort:** Medium.

### S4. CSRF check trusts a missing `Origin` and `base_url` behind proxies — Medium

- **Where:** [main.py:141-144](../backend/app/main.py#L141-L144)
- **Problem:**
  - A mutating request with no `Origin` header is allowed. `SameSite=Lax` covers most browser cases, but the rule that stops cross-site POSTs should not depend on a header being present.
  - `request.base_url` is built from the `Host` header and scheme the app sees. Behind a TLS-terminating proxy the scheme is `http`, so legitimate `https://` origins would be rejected, and a permissive `Host` handling would weaken the check.
- **Recommendation:** Require `Origin` (or fall back to `Referer`, or `Sec-Fetch-Site: same-origin`) on non-safe methods, and compare against a configured `ALLOWED_ORIGIN` setting instead of the request's own `Host`. Alternatively use `SameSite=Strict`, because the app has no cross-site entry flows.
- **Effort:** Small.

---

## Correctness

### C1. `try/except` around streaming responses can never fire — Medium

- **Where:** [main.py:207-288](../backend/app/main.py#L207-L288) (the four streaming endpoints)
- **Problem:** The handlers wrap `_log_response(...)` in `try/except Exception` and map failures to a 503. The reporters and releasers return generators, so nothing runs until the response is iterated, after the `try` has exited. The 503 branches and `log.exception(...)` calls are effectively dead code for real runs. The unit tests pass because they inject fakes that raise immediately.
- **Impact:** Anything that fails inside the run is reported through the script log (which `stream_script_log` handles). The dead branches suggest the opposite and could mislead later maintainers.
- **Recommendation:** Remove the dead `try/except` blocks, or document that failures arrive through the log. Keep one test with a generator that raises on first iteration, to pin the real behavior.
- **Effort:** Small.

### C2. Queued runs wait on the lock with no timeout; abandoned runs keep going — Medium

- **Where:** [script_runner.py:41-76](../backend/app/script_runner.py#L41-L76)
- **Problem:**
  - A second caller blocks in `lock.acquire()` with no timeout. If the first run hangs on Jira (the Jira client has no explicit timeout set), every later caller queues behind it forever and each holds a worker thread.
  - Starlette iterates the sync generator in the threadpool, so each waiting request occupies a threadpool slot as well as its own worker thread. A handful of stuck requests can exhaust the default pool.
  - If the browser disconnects, the generator is closed but the worker thread keeps running (and keeps writing to Jira for a release or archive run). That may be intended for safety, since stopping a release half-way is worse, but it is undocumented and the output is silently lost.
  - The result queue is unbounded; a stalled client with a chatty run grows memory.
- **Recommendation:**
  - Use `lock.acquire(timeout=...)` and report a clear "still busy" message when it expires.
  - Pass a request timeout to the `JIRA(...)` client (see `jira_credentials.py`).
  - Document that a started run completes even if the client leaves, and log that fact.
- **Effort:** Medium.

### C3. Release Check redirects `sys.stdout` process-wide and does not stream — Medium

- **Where:** [release_check.py:33-40](../backend/app/release_check.py#L33-L40)
- **Problem:**
  - `contextlib.redirect_stdout` swaps `sys.stdout` for the whole process, not just the worker thread. Any other thread that prints during the run (another tool, a library, uvicorn) has its output swallowed into the report, and the reverse can happen too.
  - The report is only sent to the log after the script finishes, so the user sees nothing until the end. The other tools stream line by line.
  - The script module is re-executed from disk on every call (`exec_module`), so a failure to import shows up only at run time.
- **Recommendation:** Change `tools/release_check.py` so its functions log through a logger or accept an output callback, as the other tools do, and drop the redirect. If the redirect must stay, hold a lock around it and document that it is process-global.
- **Effort:** Medium.

### C4. Archive error handling and private client internals — Low

- **Where:** [archive_released_versions.py:77-87](../backend/app/archive_released_versions.py#L77-L87)
- **Problem:** `archive_version` calls the private `jira._options` and `jira._session` attributes, which can change in any `jira` release (the dependency range is `>=3.10,<4`). `response.raise_for_status()` raises `requests.HTTPError`, not `JIRAError`, so the user-facing explanation helper (`explain_exception`) reports it as an "Unexpected error". The per-version loop also swallows the cause and logs only `str(error)`.
- **Recommendation:** Use the public API (`version.update(archived=True)` is supported by the library) or wrap the HTTP error so it is explained like other Jira failures. Add a test that a 403 on one version is reported and the run continues.
- **Effort:** Small.

### C5. Unknown `/api/...` GET paths return the SPA HTML — Low

- **Where:** [main.py:290-307](../backend/app/main.py#L290-L307)
- **Problem:** The catch-all route serves `200.html` for any unknown GET, including `/api/typo`. Callers get a 200 with HTML instead of a 404 JSON error, which hides client bugs.
- **Recommendation:** In the catch-all, return a 404 JSON response when the path starts with `api/`.
- **Effort:** Small.

### C6. `app = create_app()` runs at import time — Low

- **Where:** [main.py:312](../backend/app/main.py#L312), [auth.py:21-36](../backend/app/auth.py#L21-L36)
- **Problem:** Importing `backend.app.main` loads `.env` and parses `AUTH_USERS_JSON`. A malformed value raises `RuntimeError` at import, which gives an unhelpful traceback under uvicorn and makes any tooling that imports the module (tests, docs generation) fail. When there are no users configured, the app starts normally and every login returns 503, which is easy to miss.
- **Recommendation:** Keep the strict validation but log a clear startup message (for example "0 users configured"). Consider uvicorn's `--factory` option so the app is built at startup, not import.
- **Effort:** Small.

---

## Maintainability

### M1. Business rules and patterns are duplicated — Medium

- **Where:** `SEMANTIC_VERSION_PATTERN` in [service_versions.py:11-19](../backend/app/service_versions.py#L11-L19) and [release_semantic_version.py](../backend/app/release_semantic_version.py) (this copy additionally allows `UNKNOWN`); `PARENT_ISSUE_TYPES` and `RELEASABLE_SUBTASK_TYPES` in both modules; the team list is hard-coded in both regexes; `archive_released_versions.py` imports `create_jira_client` from `release_semantic_version` instead of `jira_credentials`.
- **Problem:** The two regexes will drift: adding a team to one and not the other changes which versions the tools accept, with no error.
- **Recommendation:** Move the shared constants and the one version pattern into a single module (for example `backend/app/jira_rules.py`), derive the `UNKNOWN` variant from it, and import it everywhere.
- **Effort:** Small.

### M2. `release_semantic_version.py` is a 1,154-line module — Low

- **Problem:** Configuration, classification, Jira calls, blockers, comment writing and orchestration all live in one file. `add_partial_release_comment` and `add_not_released_comment` are near-duplicates, and `evaluate_parent` is a long function with many branches. This makes the riskiest workflow (it writes to Jira) the hardest to review.
- **Recommendation:** Split into configuration, rules (pure functions), Jira I/O, and the workflow, and merge the two comment builders. Do this only with the existing tests as a safety net, and keep each step behavior-neutral.
- **Effort:** Large.

### M3. Scope has drifted from the "small starter" — Low

- **Where:** `CLAUDE.md` says to keep the project a small SvelteKit and FastAPI starter unless scope is explicitly expanded; the FastAPI title is still "Svelte FastAPI Starter API", the package is `svelte-fastapi-starter`, and the app now ships authentication, four Jira workflows and a token dialog.
- **Recommendation:** Update the project instructions and README to describe the app as it is (a release-management tool), and rename the API title and package. This avoids contradictory guidance for future contributors and agents.
- **Effort:** Small.

### M4. Defense-in-depth gaps in JQL construction — Low

- **Where:** [service_versions.py:48-54](../backend/app/service_versions.py#L48-L54), [release_semantic_version.py:982](../backend/app/release_semantic_version.py#L982)
- **Problem:** JQL is built with f-strings from `project_key` and the version name. Today the API validates both with strict patterns, so this is not exploitable. The safety lives in the request models, not at the point of use, so a later caller that skips validation would introduce injection.
- **Recommendation:** Validate (or escape double quotes and backslashes) at the point where the JQL is built, and add a unit test with a hostile value.
- **Effort:** Small.

---

## Operations

### O1. Lint fails — Low

- **Problem:** `pnpm lint` exits non-zero because Prettier flags 30 files. The cause is not diagnosed; I did not check whether it is line endings (`core.autocrlf`) or real formatting drift. The project's own checklist lists `pnpm lint` as a required step.
- **Recommendation:** Run `pnpm exec prettier --write .` once, or add a `.gitattributes` with `* text=auto eol=lf` if it is line endings, and keep lint in CI.

### O2. Sessions are in memory and process-local — Low

- **Where:** [auth.py:39-45](../backend/app/auth.py#L39-L45)
- **Problem:** Sessions disappear on restart, and running more than one uvicorn worker or container would make users appear randomly signed out. Expired sessions are only pruned when someone logs in.
- **Recommendation:** Acceptable for a single-instance tool. Document it, and make sure the Docker command keeps a single worker. Prune on a timer if the user count grows.

### O3. Docker and start scripts — Info

- **Problem:** The Docker `CMD` binds `0.0.0.0` (needed in a container) while `scripts/start.sh` binds `127.0.0.1`; the container has no `HEALTHCHECK` even though `/api/health` exists, and `uv run` at startup may attempt an environment sync as the non-root user.
- **Recommendation:** Add a `HEALTHCHECK` that calls `/api/health`, and run `uvicorn` from the synced environment directly (`.venv/bin/uvicorn`) so startup does not depend on `uv` behavior.

---

## Tests

### T1. Coverage gaps on the riskiest paths — Low

The suite is broad (93 backend and 44 frontend unit tests), but these behaviors have no test that I could find:

- Login throttling (S1) is untested because it does not exist.
- A streaming endpoint whose generator raises on first iteration (C1).
- Concurrent callers on the same workflow lock and the waiting message (C2).
- `release_check` output isolation from other threads (C3).
- The cross-origin rejection when `Origin` is absent, and behind a proxy (S4).
- A failed per-version archive call (C4).

---

## Positive notes

- Request models validate keys, versions and dates, and reject future archive dates both in the model and in the preview route.
- `explain_exception` gives actionable messages without leaking tokens, URLs or tracebacks.
- Auth: Argon2id parameters are checked at startup, unknown users still pay for a hash comparison, session tokens are stored only as SHA-256 hashes, cookies are HttpOnly and SameSite, and the old session is dropped on login.
- Frontend static file serving guards against path traversal with `relative_to` on the resolved path.
- Every Jira-writing workflow has a dry-run mode and runs under a lock.
- The frontend uses runes and a shared `ScriptRun` state class, and the layout emits events for 401 and 428 so expiry is handled in one place.

## Suggested order of work

1. S2, S1, S4: small changes that close the largest security gaps.
2. C1, C5, M1: small cleanups that remove misleading code and duplication.
3. C2, C3, S3: medium changes to the run lifecycle and token handling.
4. O1, T1: restore a clean lint run and add the missing tests alongside each fix.
5. M2 and M3 last, as separate behavior-neutral changes.
