# Upstream Strategy Builder UI

Source: https://github.com/koreainvestment/open-trading-api/tree/main/strategy_builder/frontend

Imported from upstream commit:

```text
33e0e1e65cd1c8c8b639531483ec0b327087bab1
```

Local integration notes:

- Runs on internal container port `3100`; host access goes through Caddy on
  `DASHBOARD_HOST_PORT` (paper/local `5081`) so the existing `3000` owner on
  this host stays separate.
- Only the `/tos` operator page, the `/` redirect to it and the `/api/[...path]`
  proxy remain. Every upstream Strategy Builder page, and the
  `/api/kis-builder/*` compatibility routes they called, were deleted by the
  legacy removal (`docs/plans/2026-11-07-legacy-removal-plan.md`, L4/L5). The
  proxy now resolves `/api/tos/projection` against `KIS_BUILDER_API_BASE`; the
  env var keeps its upstream name.
- There is no upstream diff to keep inspectable any more: what is left is
  STS-authored. Treat this file as provenance for the scaffold
  (Next.js/Tailwind/test setup), not as a merge contract.
