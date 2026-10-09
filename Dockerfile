FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ ./backend/
COPY tools/ ./tools/
COPY --from=frontend-build /app/frontend/build ./frontend/build

ENV FRONTEND_BUILD_DIR=/app/frontend/build
ENV PYTHONPATH=/app

RUN useradd --create-home --shell /usr/sbin/nologin app \
  && chown -R app:app /app

USER app
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
