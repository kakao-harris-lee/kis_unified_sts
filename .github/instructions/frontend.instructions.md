---
globs: ["**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx", "**/*.vue", "**/*.svelte"]
---

# Frontend Rules

> **Loading**: the `globs` frontmatter above **is enforced**. The OMC `rules-injector` hook supports `globs` (`src/hooks/rules-injector/types.ts:18`) and injects this file as `[Rule: …][Match: …]` when a matching path is read/written/edited (`constants.ts:45` `TRACKED_TOOLS`). Scope is structural, not advisory.
>
> This file previously lived at `.claude/rules/`, where scope was defeated — not by `globs`, but by the **location**: Claude Code loads `.claude/rules/*.md` in full into the system prompt at session start regardless of which files are open (observed directly; `.github/` has no such unconditional load). It was moved here so the declared scope is the actual scope. `.github/instructions/` requires the `.instructions.md` suffix (`finder.ts:36-41`).
>
> **One pattern per entry — no brace expansion.** `matchGlob` (`matcher.ts:17-28`) rewrites only `.`, `**`, `*`, and `?` into a regex; `{a,b}` survives as literal text, so a pattern like `**/*.{ts,tsx}` matches no real file. That form was silently dead here while `.claude/rules/` was still force-loading the file, which masked it. List each extension separately, as above.
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
