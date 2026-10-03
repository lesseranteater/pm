# Kanban Frontend

Use SvelteKit for this frontend. Keep work scoped to the current request and
the MVP below. Apply these instructions proportionately to the task.

## Part 1: Reusable Agent Principles

This section is technology-neutral and can be reused independently of Part 2.

### Think Before Changing Code

- State material assumptions and explain uncertainty. Ask when an unresolved
  ambiguity would materially change the implementation.
- Surface meaningful tradeoffs and suggest a simpler approach when it meets
  the requirement.

### Keep It Simple

- Implement only what the request requires. Avoid speculative features,
  abstractions, configuration, and handling for impossible scenarios.
- Prefer the smallest clear solution. Reconsider implementations substantially
  more complex than the problem requires.

### Make Surgical Changes

- Read relevant code before editing. Preserve existing style and user changes;
  avoid unrelated refactors, formatting, or cleanup.
- Remove artifacts made unused by your changes. Report unrelated issues
  without fixing them unless requested.

### Work Toward Verifiable Outcomes

- Define concrete success criteria. For multi-step work, make a short plan
  with verification for each important step.
- Reproduce bugs and establish the root cause before fixing them. Add focused
  regression tests when practical; test behavior rather than implementation.
- Run relevant checks and report results and limitations accurately. Keep
  verification proportionate: document review for documentation edits, focused
  tests and relevant build checks for behavior changes.

### Completion Standard

Every change should be traceable to the request, proportionate to the task,
and verified to an appropriate level of confidence.

## Part 2: Kanban And SvelteKit Guidance

### MVP Business Requirements

These requirements define the app's functional acceptance criteria. Preserve
them during refactoring and simplification; technical choices must support
them, not silently change or reduce them. Change scope only when explicitly
requested, and verify every required user workflow before MVP handoff.

- Build an MVP Kanban-style project-management web app in `frontend/` using
  SvelteKit. Users manage their work visually on a single board.
- Provide exactly one board with five fixed columns. Allow users to rename
  columns, but not add or remove them.
- Cards contain only a title and details as user-editable content.
- Allow users to add a card to a chosen column, edit its title and details,
  and delete an existing card.
- Support drag and drop to move cards between columns.
- Populate the board with dummy data on first load so the app is immediately
  usable without setup.
- Keep board changes in memory only: no database, browser-storage persistence,
  or user management for this MVP. Reloading starts a fresh demo board.
- Do not add archiving, search, filtering, or features beyond this scope unless
  explicitly requested.
- Prioritize a slick, professional, polished UI/UX that is responsive and
  accessible. Keep functionality and implementation simple; use established
  libraries where they reduce effort without adding unnecessary complexity.

### MVP Delivery Criteria

- Before implementation, write a phased plan with checkable success criteria,
  including scaffolding, a `.gitignore`, and meaningful unit tests.
- Execute the plan and verify each success criterion. Exercise the complete
  MVP through Playwright integration/end-to-end tests and fix defects found.
- For the MVP implementation handoff, finish and test all required features,
  leave the development server running and ready for the user, and report its
  URL and verification results. If blocked, report the blocker rather than
  claiming completion. Documentation-only tasks do not require starting a server.

### Stack And Tooling

- SvelteKit 2, Svelte 5, strict TypeScript, and a compatible stable Vite version.
- Tailwind CSS 4 through `@tailwindcss/vite`; Lucide Svelte for icons.
- pnpm with a committed `pnpm-lock.yaml`. Record Node and pnpm versions; ignore
  dependencies, generated output, and local secrets in version control.
- ESLint with `eslint-plugin-svelte` and `typescript-eslint`, plus Prettier.
- Vitest with a Playwright browser provider for component tests; Playwright for
  end-to-end tests.
- Use stable, compatible dependencies within the selected majors. Respect the
  lockfile and make major upgrades explicit. Consult version-matched docs;
  current online examples may target a newer SvelteKit major.

### Structure And Configuration

- Work in `frontend/`. Keep pages and layouts in `src/routes/`, route-specific
  components beside their route, and shared components in `src/lib/components/`.
- Use `$lib/...` for shared imports and `src/lib/components/ui/` for UI primitives.
  Create helpers and directories only as needed.
- Use `@sveltejs/adapter-node` for Node deployment and the `sveltekit()` Vite
  plugin. Follow the selected SvelteKit version's configuration conventions.
- Extend `.svelte-kit/tsconfig.json` with `strict: true`. Do not edit generated
  configuration or suppress type, lint, or accessibility checks to hide errors.
- Keep SSR enabled by default; isolate browser-only dependencies and access
  browser APIs in browser-only lifecycle code, typically `onMount`.

### Svelte Conventions

- Use `<script lang="ts">` when a component needs a script. Type its `$props()`
  and use snippets with `{@render ...}` for composable content.
- Use runes for reactive application state. Prefer `$derived` for computed
  values; reserve `$effect` for external side effects and clean up resources.
  Ordinary nonreactive `let` variables are fine.
- Use DOM event properties such as `onclick`, and typed callback props for
  component events. Avoid legacy `$:` reactivity and `on:click` directives.
- Keep board state in its owning page or a per-board context. Prefer callbacks
  for child updates; use `$bindable` only for deliberate two-way bindings.
  Never share per-user mutable state through server module globals.
- Use stable card/column IDs and keyed `{#each}` blocks. Keep initial render
  data deterministic so server and client output agree during hydration.

### UI Components And Styling

- Prefer semantic HTML and native controls. Use Bits UI, directly or through
  wrappers, for complex controls; preserve its keyboard and focus behavior.
- [shadcn-svelte](https://www.shadcn-svelte.com/) may be used when a hand-rolled
  control would be more costly than a sourced one. Add a component only when
  the screen needs it; do not install the whole registry in advance.
- Keep sourced-component changes targeted. Reuse existing primitives and visual
  variants; use a `cn()` helper with `clsx` and `tailwind-merge` when needed to
  compose conditional or caller-supplied classes.
- Import global CSS once in the root layout. Use mobile-first Tailwind styles
  and shared tokens:
  - Yellow `#ecad0a`: accents and highlights.
  - Blue `#209dd7`: links and key sections.
  - Purple `#753991`: primary actions.
  - Navy `#032147`: headings.
  - Gray `#888888`: supporting text, subject to contrast requirements.
- Keep project documentation concise. Do not use emojis.

### Accessibility And Interaction

- Use labels, semantic headings, visible focus, explicit button types, and
  accessible names for icon-only buttons. Associate errors with their fields.
- Provide a keyboard- and touch-operable move control alongside dragging.
  Announce moves appropriately and manage focus after dialogs and deletions.
- Check narrow screens, zoom, and reduced-motion preferences. Do not convey
  status through color alone.
- Verify foreground/background contrast: at least 4.5:1 for normal text and
  3:1 for large text. Adjust brand-token variants when needed; `#888888` on
  white fails the normal-text threshold.
- Show empty, loading, saving, and error states where applicable. Preserve
  unsaved input on failure; reconcile or roll back failed optimistic updates.

### Data Boundaries

- Keep the demo local. Introduce API clients and server integration only when
  requested; do not scaffold speculative backend layers.
- When needed, use server `load` functions for private data and page form
  actions for suitable mutations. Actions belong in `+page.server.ts`, not
  `+layout.server.ts`; use the supplied `fetch` in loads and generated route types.
- Use `use:enhance` for SvelteKit action forms, not arbitrary API endpoints.
  Centralize repeated browser requests in a small typed client when necessary;
  handle unsuccessful responses explicitly without imposing an error framework.
- Keep secrets and privileged code in `src/lib/server/` or server-only files.
  Never import private environment modules into client code or return secrets
  in page data. Validate external data at the boundary; types alone do not do so.
- Render card content as text, not raw `{@html}`.
- If a separate backend is introduced, choose one same-origin routing solution.
  Development proxy settings alone do not provide production routing.

### Verification

After scaffolding, keep these scripts aligned with `package.json`. Run relevant
checks from `frontend/`; do not claim unavailable checks passed:

```bash
pnpm check
pnpm lint
pnpm test:unit --run
pnpm build
pnpm test:e2e
```

- Keep component tests in the Vitest browser project and non-component tests in
  the Node project, with non-overlapping include/exclude patterns.
- Cover card creation, editing, deletion, movement, column renaming, empty
  columns, and keyboard interactions. Check narrow-screen and touch behavior.
- Test end-to-end journeys against a production build. For deployment changes,
  also smoke-test the Node adapter output; preview is not the production server.
- Keep tests deterministic. Mock external services unless a test explicitly
  provisions them; cover failure states when API integration is added.
- Use `pnpm dev` for development and `pnpm preview` to inspect a build.

### References

Use documentation matching the selected major versions:
[Svelte](https://svelte.dev/docs/svelte/overview),
[SvelteKit](https://svelte.dev/docs/kit/introduction), and
[shadcn-svelte](https://www.shadcn-svelte.com/docs).
