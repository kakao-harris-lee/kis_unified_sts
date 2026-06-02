# Strategy Builder UI

The upstream KIS Strategy Builder frontend is imported in `strategy-builder-ui/`.

- Upstream source: `koreainvestment/open-trading-api/strategy_builder/frontend`
- User-facing URL: `http://localhost:5080`
- Internal container port: `strategy-builder-ui:3100`
- Backend compatibility API: `services/dashboard/routes/kis_builder.py`

Run with Docker Compose:

```bash
docker compose up -d strategy-builder-ui
```

Run locally:

```bash
cd strategy-builder-ui
npm install
KIS_BUILDER_API_BASE=http://localhost:5080 npm run dev
```

The UI keeps upstream `/builder` and `/execute` routes. In this repository the
execution and order surfaces are paper-only compatibility endpoints; they do
not submit live KIS orders.

API routing:

- Browser calls stay same-origin under `/api/*`.
- `strategy-builder-ui/src/app/api/[...path]/route.ts` proxies those calls to
  `${KIS_BUILDER_API_BASE}/api/kis-builder/*`.
- In Docker, Caddy is the only host-published web entry on port `5080`; the
  Next.js `3100` port and dashboard `8001` port are internal only.
- If dashboard API auth is enabled, set `KIS_BUILDER_API_KEY` to the same value
  as `DASHBOARD_API_KEY`; Docker Compose wires this automatically.

Preset strategy coverage:

- The upstream README advertises 10 default strategies and 80 technical
  indicators.
- This repository exposes the 10 upstream defaults plus a curated major set of
  indicator-combination presets through `/api/kis-builder/strategies`.
- Current preset count: 27.
- Added major families include RSI/Williams %R/CCI/MFI reversals, MACD/TRIX
  momentum, Bollinger/VWAP/Donchian/Keltner breakouts, ADX/Ichimoku/SuperTrend
  trend following, OBV accumulation, and one candlestick + RSI reversal.
