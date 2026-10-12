# Release Management Tools

A web application with a SvelteKit frontend and FastAPI backend for Jira release
management. After signing in and entering a personal Jira token, users can list
service versions that are missing a release date, release a deployment version,
archive released versions, and check a deployment plan for Fix Version mismatches.
The production frontend is built as static files and served by FastAPI.

## Requirements

- Python 3.12 or newer with `uv`
- Node.js 22 or newer with pnpm 10
- Docker for the container workflow

## Run Locally

Install dependencies:

```bash
uv sync
pnpm --dir frontend install
```

Build the frontend and start the combined application:

```bash
pnpm --dir frontend build
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Create a root `.env` file with the Jira URL and authentication users:

```text
JIRA_URL=https://jira.egt-digital.com
```

`.env` is ignored by Git. Open `http://127.0.0.1:8000/` for the Release Management
Tools home page, which explains the tools and links to each one; the logo always
returns to it. For the service versions report, enter a Jira project key, choose a release version status and a deployment version, then load the
report. The **List Service Versions Without a Release Date** script returns its Jira
search log in the browser, implemented in
`backend/app/service_versions.py`. The frontend sends those
values to `POST /api/service-versions`. `GET
/api/health` reports backend health and whether your Jira token cookie is present; the
home page shows a warning when it is not.

The **Release a Deployment Version** script accepts a deployment version and a Dry
Run choice. It returns its Jira workflow log in the browser. Choosing **No** for
Dry Run applies Jira changes.

Every tool streams its log to the page line by line while it runs. The log can be
searched, limited to warnings and errors, copied, or downloaded, and it is marked
out of date when the inputs change after a run. Failures are explained in plain
language, for example an expired token or an unreachable Jira. Only one run at a
time changes Jira; a second request waits and says so in its log.

Tools that change Jira are protected in two steps. A live run (Dry Run set to
**No**) is only available after a dry run with the same inputs has finished
without errors, and it asks for confirmation before it starts. After a dry run, an
**Apply These Changes** button offers the live run directly.

The **Archive Released Versions** script archives every released Jira version in a
project whose release date is on or before the date you pick (it defaults to
yesterday, and future dates are rejected). It does nothing until you click
**Archive Versions**. Dry Run defaults to **Yes**, which only lists the versions it
would archive; choosing **No** archives them in Jira. The page shows how many
versions match the chosen date before anything runs
(`GET /api/archive-released-versions/preview`). Choose the cutoff date using the
date field. Both archive methods are implemented in
`backend/app/archive_released_versions.py`.

Choose **Archive By → Version list** to paste exact Jira version names separated
by commas. This mode ignores release dates; date mode ignores the saved list.
Whitespace and duplicate names are removed. The preview lists eligible, unknown,
unreleased and already archived versions. Correct unknown names before running;
unreleased and already archived versions are skipped. Changing the method or its
input requires a fresh dry run before a live run. List preview uses
`POST /api/archive-released-versions/preview`; archiving uses the existing archive
endpoint with `archive_by: "versions"` and `version_names`, without `archive_until`.

The **Release Check** tool checks Fix Versions on the Deployment Plan's linked
issues, their parents and direct subtasks. Its read-only implementation lives in
`backend/app/release_check.py` and streams its Script Log directly from the backend.
All Jira tool implementations live in `backend/app/`.

The script endpoints (`/api/service-versions`, `/api/release-semantic-version`,
`/api/release-check` and `/api/archive-released-versions`) respond with the log as streamed plain text. The
old page addresses `/service-versions`, `/release-semantic-version` and
`/release-a-semantic-version` redirect to the current ones.

The cross-platform scripts build the frontend when needed and run the same
combined application:

```bash
./scripts/start.sh
./scripts/stop.sh
```

On Windows PowerShell, use `./scripts/start.ps1` and `./scripts/stop.ps1`.

## Authentication

Configure `AUTH_USERS_JSON` in the root `.env` or inject it from Vault. It is a
JSON array of `{"username":"email@example.com","password_hash":"<Argon2id hash>"}`
records. `python-dotenv` accepts a multiline array enclosed in single quotes.
Credentials are verified server-side; missing configuration disables login.

All Jira API routes require the HTTP-only `pm_session` cookie. Sessions last seven
days, live only in server memory, and are invalidated by logout or a server
restart. Run a single Uvicorn worker. Password changes require restarting the app.
Set `COOKIE_SECURE=true` when serving over HTTPS; leave it false for local HTTP
(browsers do not send `Secure` cookies over plain HTTP, so setting it early breaks login).

Behind a proxy that terminates HTTPS, also set `ALLOWED_ORIGIN=https://your-domain`
(scheme and host only). The app then accepts browser `POST` requests whose `Origin`
header matches it. Without it the app compares `Origin` with the address it sees
itself, which is correct for plain HTTP but rejects every `POST` behind a proxy.

Sign-in is throttled per username: after five wrong passwords in a row the username
is locked for 30 seconds, doubling with each further failure up to 15 minutes. The
count resets after a successful sign-in or 15 minutes without attempts. Unknown
usernames are throttled the same way.
The session endpoints are `/api/auth/login`, `/api/auth/me`, and `/api/auth/logout`.

After signing in, enter your Jira Personal Access Token in the modal. The server keeps
it in memory, attached to your login session, and never sends it back to the browser.
Refreshes and tool changes reuse it. It is dropped when you log out, when the session
expires, and when the server restarts (which also ends every session), and a new login
prompts for a fresh token. Jira requests require a valid login session and a saved
token. `JIRA_URL` still comes from `.env`; web tools never use `JIRA_TOKEN` from server
configuration. Older versions stored the token in a `pm_jira_token` cookie; that cookie
is now ignored and cleared at the next sign-in.

## Frontend Development

Run the Svelte development server from `frontend/`:

```bash
pnpm dev
```

For this standalone frontend server, requests to `/api/service-versions` require a
separately running backend or a development proxy. Use the combined server
workflow above to exercise the complete application.

## Verification

```bash
uv run pytest
pnpm --dir frontend check
pnpm --dir frontend lint
pnpm --dir frontend test:unit --run
pnpm --dir frontend build
```

## Docker

Build and run the combined image:

```bash
docker build -t svelte-fastapi-starter .
docker run --rm -p 8000:8000 svelte-fastapi-starter
```

Open `http://localhost:8000/`. The image builds the Svelte frontend in a Node
build stage and runs FastAPI in the final Python image.

## Project Structure

- `frontend/`: SvelteKit application and frontend tests.
- `backend/`: FastAPI application and backend tests.
- `scripts/`: cross-platform start and stop scripts.
- `utils/`: manual password-hashing utility, separate from the application runtime.
- `Dockerfile`: combined frontend build and FastAPI runtime image.

## Generate a password hash

Run the script below in PowerShell or Command Prompt

```
& "C:\Dev\Projects\pm\.venv\Scripts\python.exe" "C:\Dev\Projects\pm\utils\password-hasher.py"
```
