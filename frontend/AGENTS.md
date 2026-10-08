# Svelte Frontend

Use SvelteKit for this frontend. Keep work scoped to the current request.

## Principles

- State material assumptions and ask when an unresolved ambiguity would
  materially change the implementation.
- Implement only what the request requires. Prefer the smallest clear solution.
- Read relevant code before editing. Preserve existing style and user changes;
  avoid unrelated refactors or cleanup.
- Remove artifacts made unused by a change.
- Define concrete success criteria, run proportionate checks, and report results
  and limitations accurately.

## Stack And Structure

- Use SvelteKit 2, Svelte 5, strict TypeScript, and Tailwind CSS.
- Work in `frontend/`. Keep pages and layouts in `src/routes/` and shared code
  in `src/lib/`.
- Use `@sveltejs/adapter-static`; FastAPI serves `build/` in production.
- Keep prerendering enabled and access browser APIs in browser-only lifecycle
  code, typically `onMount`.
- Use runes for reactive state. Prefer DOM event properties such as `onclick`
  over legacy event directives.

## Accessibility And Data

- Prefer semantic HTML, native controls, visible focus, and descriptive labels.
- Keep browser requests same-origin through `/api`.
- Keep secrets and privileged code out of the frontend. Validate API data before
  displaying it and never render external strings with `{@html}`.
- Show loading and error states for requests.

## Verification

Run relevant checks from `frontend/`:

```bash
pnpm check
pnpm lint
pnpm test:unit --run
pnpm build
pnpm test:e2e
```
