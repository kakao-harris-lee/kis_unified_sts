# Quant Ops Workbench UI/UX QA Evidence (2026-06-25)

**Status**: Passed with Playwright fallback verification.
**Scope**: `/risk`, `/coverage`, `/trades`, `/builder`, `/event-context`.
**Server**: local Next.js dev server at `http://127.0.0.1:3100`.

## Tooling Note

The in-app Browser execution MCP was not exposed in this Codex session, so the
visual pass used the installed Playwright CLI/runtime as the fallback browser
automation path. Chromium was installed locally with `playwright install
chromium` before the run.

## Viewports

| Name | Size |
|---|---|
| Desktop | `1440x1100` |
| Mobile | `390x844` |

## Checks Performed

- Page identity: route-specific heading visible.
- Nonblank render: body text length checked for degraded empty-state pages.
- Console health: browser console errors captured per route and viewport.
- Interaction smoke: refresh controls on `/risk`, `/coverage`, and
  `/event-context`; `History (DB)` tab on `/trades`; promotion board visibility
  on `/builder`.
- Layout sanity: visible interactive controls checked for material overlap with
  hit-test filtering so horizontally clipped mobile nav items are not treated as
  visible controls.
- Visual review: desktop/mobile screenshots inspected for readable layout,
  visible degraded-state warnings, and no obvious text/control overlap.

## Result Matrix

| Route | Desktop | Mobile | Console errors | Interaction proof |
|---|---:|---:|---:|---|
| `/risk` | pass | pass | 0 / 0 | `Refresh risk exposure` clicked |
| `/coverage` | pass | pass | 0 / 0 | `Refresh coverage` clicked |
| `/trades` | pass | pass | 0 / 0 | `History (DB)` selected |
| `/builder` | pass | pass | 0 / 0 | `Strategy Promotion Kanban` visible |
| `/event-context` | pass | pass | 0 / 0 | `Refresh event context diagnostics` clicked |

The local dashboard API was unavailable during the visual pass, so the pages
rendered their degraded empty states. That is intentional coverage for the
operator path where backend data is temporarily unavailable.

## Command Evidence

```bash
npm --prefix strategy-builder-ui run dev
curl -I --max-time 10 http://127.0.0.1:3100/trades
playwright --version
npm --prefix strategy-builder-ui test -- src/app/quant-ops-workbench.smoke.test.tsx
```

The Playwright fallback script generated these screenshots:

| Route | Desktop screenshot | Mobile screenshot |
|---|---|---|
| `/risk` | [risk-desktop.png](quant-ops-workbench-2026-06-25/risk-desktop.png) | [risk-mobile.png](quant-ops-workbench-2026-06-25/risk-mobile.png) |
| `/coverage` | [coverage-desktop.png](quant-ops-workbench-2026-06-25/coverage-desktop.png) | [coverage-mobile.png](quant-ops-workbench-2026-06-25/coverage-mobile.png) |
| `/trades` | [trades-desktop.png](quant-ops-workbench-2026-06-25/trades-desktop.png) | [trades-mobile.png](quant-ops-workbench-2026-06-25/trades-mobile.png) |
| `/builder` | [builder-desktop.png](quant-ops-workbench-2026-06-25/builder-desktop.png) | [builder-mobile.png](quant-ops-workbench-2026-06-25/builder-mobile.png) |
| `/event-context` | [event-context-desktop.png](quant-ops-workbench-2026-06-25/event-context-desktop.png) | [event-context-mobile.png](quant-ops-workbench-2026-06-25/event-context-mobile.png) |

## Notes

- The first local QA script used stale expectations for `/trades` (`DB History`)
  and `/builder` (`Promotion readiness`). Current UI/tests use `History (DB)`
  and `Strategy Promotion Kanban`.
- A naive overlap detector also flagged a horizontally clipped mobile nav item
  as overlapping settings. The final pass uses hit-testing to distinguish
  visible controls from overflow-clipped nav items.
- The screenshot directory is intentionally committed despite the repository
  `*.png` ignore rule; add these files with `git add -f` when updating this
  evidence set.
