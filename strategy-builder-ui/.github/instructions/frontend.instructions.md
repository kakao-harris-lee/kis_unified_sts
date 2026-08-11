---
globs: ["**/*.js", "*.js", "**/*.jsx", "*.jsx", "**/*.ts", "*.ts", "**/*.tsx", "*.tsx", "**/*.vue", "*.vue", "**/*.svelte", "*.svelte"]
---

# Frontend Rules

> **Loading**: the `globs` frontmatter above **is enforced**. The OMC `rules-injector` hook supports `globs` (`src/hooks/rules-injector/types.ts:18`) and injects this file as `[Rule: …][Match: …]` when a matching path is read/written/edited (`constants.ts:45` `TRACKED_TOOLS`). Scope is structural, not advisory.
>
> This file previously lived at `.claude/rules/`, where scope was defeated — not by `globs`, but by the **location**: Claude Code loads `.claude/rules/*.md` in full into the system prompt at session start regardless of which files are open (observed directly; `.github/` has no such unconditional load). It was moved to `.github/instructions/` so the declared scope is the actual scope. That directory requires the `.instructions.md` suffix (`finder.ts:36-41`).
>
> **Why this file sits under `strategy-builder-ui/` and not the repo root.** `findProjectRoot` (`finder.ts:57-63`) walks up from the edited file and returns at the **first** `PROJECT_MARKERS` hit; `package.json` is one of those markers (`constants.ts:17-24`) and `strategy-builder-ui/package.json` exists. So for any file under `strategy-builder-ui/**` the project root is **`strategy-builder-ui/`**, the upward rule scan stops there, and a copy at the repo root is **never reached**. It lives beside the project it governs. (`shared/**` has no marker of its own, so it walks to the repo root's `.git` — which is why `python-backend.instructions.md` stays there and works.)
>
> ⚠ **This recurs if another subproject grows its own marker.** Drop a `package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod` / `.venv` into any directory and every file below it stops seeing repo-root rules. A new subproject needs its own `.github/instructions/`.
>
> **Globs are matched against the path relative to that project root** (`matcher.ts:52-57`), i.e. `src/app/layout.tsx`, not `strategy-builder-ui/src/app/layout.tsx`.
>
> **List both `**/*.x` and `*.x` for every extension.** `matchGlob` (`matcher.ts:17-28`) turns `**/*.tsx` into `^.*/[^/]*\.tsx$` — the literal `/` is required, so files sitting **directly at the project root** (`next.config.ts`, `vitest.config.ts`) never match. The bare `*.x` form covers them.
>
> **One pattern per entry — no brace expansion.** The same rewriter handles only `.`, `**`, `*`, and `?`; `{a,b}` survives as literal text, so a pattern like `**/*.{ts,tsx}` matches no real file. That form was silently dead here while `.claude/rules/` was still force-loading the file, which masked it. List each extension separately, as above.
>
> Each rule has a "why" so you can override it intentionally.

## Components
- Functional components only (no class components) — *hooks API is the supported path since React 16.8 (2019); class lifecycle methods are not first-class with Suspense / concurrent rendering*
- One component per file — *grep-by-filename works; circular-import risk drops*
- Reusable components in `components/`, page components in `pages/` or `views/` — *next.js / nuxt convention; routing tools depend on it*
- Props interface/type defined at top of file (TS) or `propTypes` defined at bottom (JS) — *contract is visible without scrolling; LSP autocomplete works for consumers*

## State Management
- Local state for component-specific data (`useState`, `useReducer`) — *keep blast radius small; don't pollute global store with form input state*
- Global store (Zustand / Redux / Pinia) for shared application state only — *anything passed through more than 2 prop layers is a candidate; below that, prop drilling is fine*
- API calls through a dedicated service layer (`services/` or `api/`), not inside components — *one place to swap fetch for axios, add retries, mock in tests*
- Loading and error states for all async operations — *the "spinner-then-blank" UX is a regression magnet; always render `if (error) ... if (loading) ... return data`*

## Styling
- Follow the project's existing convention (CSS modules / Tailwind / styled-components / vanilla-extract) — *do not introduce a second styling system; the bundle size and cognitive cost is real*
- Responsive design — mobile-first (`min-width` queries, not `max-width`) — *progressive enhancement; default styles work on the smallest target*
- No inline styles beyond trivial cases (one-off `style={{ width: dynamicPx }}`) — *inline styles bypass the design system, can't be themed, and hurt CSP*

## Error Handling
- Error boundaries for user-facing component trees — *uncaught render errors otherwise unmount the entire React tree (white screen)*
- User-friendly error messages, no raw `error.toString()` — *expose stack traces only in dev; production users see a sentence and a retry button*
- Graceful degradation when API is unavailable — *show cached data + "offline" indicator rather than a hard error*

## Testing
- Unit tests for utility functions (Vitest / Jest) — *fastest feedback loop; pure functions deserve 100% coverage*
- Component tests for user interactions (Testing Library: `getByRole`, `userEvent.click`) — *test the user contract, not implementation details; avoid `getByTestId` unless nothing semantic exists*
- Mock API responses in tests (MSW preferred over `jest.mock`) — *MSW intercepts at the network layer, so the same mocks work in Storybook and Playwright*
- Test accessibility (semantic HTML, ARIA labels, `getByRole` queries) — *if Testing Library can find your button, so can a screen reader*
