# Quant Ops Workbench QA - 2026-06-27

## Scope

- `/signals` decision trace panel after selecting a signal.
- Desktop viewport: 1440x900.
- Mobile viewport: 390x844.

## Commands

- `pytest tests/unit/dashboard/test_signals.py tests/unit/dashboard/test_signals_trace.py tests/unit/dashboard/test_trades.py -q`
  - Result: 36 passed.
- `npm --prefix strategy-builder-ui test -- src/app/api/catchall-route.test.ts src/app/signals/components/DecisionTracePanel.test.tsx src/app/quant-ops-workbench.smoke.test.tsx`
  - Result: 37 passed.
- `npm --prefix strategy-builder-ui run lint`
  - Result: passed.
- `npm --prefix strategy-builder-ui run build`
  - Result: passed. Next.js reported the existing multiple-lockfile workspace-root warning.

## Render Evidence

- Desktop: `docs/testing/quant-ops-workbench-2026-06-27/signals-decision-trace-desktop.png`
- Mobile: `docs/testing/quant-ops-workbench-2026-06-27/signals-decision-trace-mobile.png`

## Browser QA Method

- In-session Browser MCP was not exposed in this Codex session, so local Playwright was used.
- Frontend dev server: `http://localhost:3100`.
- Playwright routed `/api/signals` and `/api/signals/sig-qa-1/trace` to deterministic read-only fixture responses so the UI could be verified without depending on live dashboard data.

## Findings

- Decision Trace opens from selected signal rows/cards.
- LLM context, strategy inputs, risk/orderability, lifecycle, scorecard, and evidence gaps render as read-only evidence.
- Missing sources render explicit states such as `unknown`, `not available`, `partial`, and `unscorable`.
- No browser console errors were observed during the checked flows.
- No horizontal overflow was observed in the checked desktop/mobile viewports.
- Keyboard focus reached interactive controls during the checked flow.
