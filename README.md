# Svelte FastAPI Starter

A local application with a SvelteKit frontend and FastAPI backend. It displays
Jira service versions that are missing a release date. The production frontend
is built as static files and served by FastAPI.

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

Create a root `.env` file with a Jira Personal Access Token:

```text
JIRA_TOKEN=your-token
JIRA_URL=https://jira.egt-digital.com
```

`.env` is ignored by Git. Open `http://127.0.0.1:8000/` for the Release Management
Tools home page, which explains the tools and links to each one; the logo always
returns to it. For the service versions report, enter a Jira project key, choose a release version status and a deployment version, then load the
report. The **List Service Versions Without a Release Date** script returns its Jira
search log in the browser, based on
`tools/list_service_versions_without_release_date.py`. The frontend sends those
values to `POST /api/service-versions`; the Jira token remains server-side. `GET
/api/health` reports backend health and whether `JIRA_TOKEN` is configured; the
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
(`GET /api/archive-released-versions/preview`), and offers quick dates such as
"End of last month". The same logic is available from the command line in
`tools/archive_released_versions_in_the_past.py`.

The script endpoints (`/api/service-versions`, `/api/release-semantic-version` and
`/api/archive-released-versions`) respond with the log as streamed plain text. The
old page addresses `/service-versions`, `/release-semantic-version` and
`/release-a-semantic-version` redirect to the current ones.

The cross-platform scripts build the frontend when needed and run the same
combined application:

```bash
./scripts/start.sh
./scripts/stop.sh
```

On Windows PowerShell, use `./scripts/start.ps1` and `./scripts/stop.ps1`.

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
- `Dockerfile`: combined frontend build and FastAPI runtime image.
