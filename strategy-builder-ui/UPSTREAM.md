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
- Next.js rewrites keep upstream `/api/*` calls intact while proxying Strategy
  Builder traffic to the STS compatibility routes under `/api/kis-builder/*`.
- Keep upstream UI changes minimal; prefer adapting in STS backend compatibility
  code so future upstream diffs remain easy to inspect.
