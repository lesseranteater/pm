#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.starter-server.pid"
LOG_FILE="$ROOT_DIR/.starter-server.log"

if [[ -f "$PID_FILE" ]] && kill -0 "$(<"$PID_FILE")" 2>/dev/null; then
  printf 'Server is already running with PID %s\n' "$(<"$PID_FILE")"
  exit 0
fi

if [[ ! -f "$ROOT_DIR/frontend/build/index.html" ]]; then
  pnpm --dir "$ROOT_DIR/frontend" build
fi

cd "$ROOT_DIR"
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port "${PORT:-8000}" >"$LOG_FILE" 2>&1 &
printf '%s\n' "$!" >"$PID_FILE"
printf 'Server started at http://127.0.0.1:%s\n' "${PORT:-8000}"
