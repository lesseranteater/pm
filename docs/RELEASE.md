# Release Verification

The application is released as one container. The final image contains the
compiled SvelteKit frontend and FastAPI backend; runtime SQLite data is kept in
the `/app/data` volume.

## Build And Run

```bash
docker build -t project-management-mvp .
docker run --rm --name project-management-mvp \
  --env-file .env \
  -p 8000:8000 \
  -v pm_data:/app/data \
  project-management-mvp
```

The `.env` file is excluded from the Docker build context. Pass secrets at
runtime with `--env-file` or explicit environment flags; never add them to the

## Verified Workflows

- Clean `docker build --no-cache` completed successfully.
- `/api/health` and the compiled frontend were served by the same container.
- Login and authenticated board reads succeeded.
- Card creation persisted after stopping and restarting the container with the
  same named volume.
- Backend AI contract tests cover mocked upstream success and failures without
  requiring a live key.
- Root `scripts/start.sh` and `scripts/stop.sh` completed a local start/stop
  cycle on Linux.
- Container logs contained no credentials or model response secrets.

## Local Script Workflow

```bash
PORT=8000 ./scripts/start.sh
./scripts/stop.sh
```

Windows users should use the PowerShell or Command Prompt wrappers documented
in the root README. The Windows scripts were reviewed but not executed in the
Linux verification environment.
