# Kanban Frontend

SvelteKit frontend for the Kanban MVP. The board currently uses in-memory state
and resets to dummy data when the page is reloaded. Production builds use
`@sveltejs/adapter-static` and are intended to be served by FastAPI.

## Requirements

- Node.js 22 or newer
- pnpm 10

## Install

From the `frontend/` directory:

```bash
pnpm install
```

## Start Development

```bash
pnpm dev
```

Open `http://localhost:5173/`.

To expose the development server to other devices on the local network:

```bash
pnpm dev --host 0.0.0.0
```

Stop the server with `Ctrl+C`.

## Verify Changes

```bash
pnpm check
pnpm lint
pnpm test:unit --run
pnpm test:e2e
pnpm build
```

Playwright may require browser installation on a new machine:

```bash
pnpm exec playwright install chromium
```

## Preview A Production Build

```bash
pnpm build
pnpm preview
```

Open the URL printed by the preview server, usually `http://localhost:4173/`.
The generated static files are written to `build/` for the FastAPI container.

## Project Layout

- `src/routes/+page.svelte`: Kanban board UI and interactions.
- `src/lib/board.ts`: board and card types plus demo data.
- `src/app.css`: global styles and design tokens.
- `src/lib/*.test.ts`: unit tests.
- `e2e/`: Playwright end-to-end tests.
- `AGENTS.md`: implementation requirements and working conventions.

Keep the MVP local and simple. Do not add persistence, authentication, AI
features, or backend integration unless explicitly requested. When backend
integration is added, browser requests should use same-origin `/api` routes
served by FastAPI.
