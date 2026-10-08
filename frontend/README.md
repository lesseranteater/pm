# Svelte Frontend

The static SvelteKit frontend fetches `GET /api/message` and displays the
returned message. FastAPI serves the production `build/` output.

## Development

```bash
pnpm install
pnpm dev
```

The standalone development server does not run the Python API. Use the root
combined-server instructions to test the frontend against FastAPI.

## Checks

```bash
pnpm check
pnpm lint
pnpm test:unit --run
pnpm build
pnpm test:e2e
```
