# Quant Ops Workbench UI/UX Plan

- **작성일**: 2026-06-22 KST
- **상태**: P0/P1/P2 diagnostics implemented; automated smoke QA and
  desktop/mobile screenshot evidence committed
- **범위**: `strategy-builder-ui/` + `services/dashboard/routes/*` + existing
  runtime/experiment data sources
- **목표**: Strategy Lab을 단순 builder가 아니라 운영 의사결정이 가능한
  Quant Ops Workbench로 확장한다.

## Source Of Truth

Current project state:

- Runtime roadmap: [../ROADMAP.md](../ROADMAP.md)
- Project status: [../PROJECT_STATUS.md](../PROJECT_STATUS.md)
- Strategy Lab design: [2026-05-26-strategy-lab-extension-design.md](2026-05-26-strategy-lab-extension-design.md)
- Stock cutover runbook: [../runbooks/stock-pipeline-cutover-m5d.md](../runbooks/stock-pipeline-cutover-m5d.md)
- Futures cutover runbook: [../runbooks/futures-pipeline-cutover-f9.md](../runbooks/futures-pipeline-cutover-f9.md)

External product references:

- QuantConnect Algorithm Framework:
  `Universe Selection -> Alpha/Signal -> Portfolio Construction -> Execution -> Risk Management`
  (<https://www.quantconnect.com/docs/v1/algorithm-framework/overview>)
- QuantConnect live results: equity curve, holdings, trades/orders, logs,
  server statistics, errors
  (<https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/results>)
- QuantConnect backtest report: returns, drawdown, rolling stats, exposure
  (<https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/report>)
- TradingView Strategy Tester: overview, performance summary, trade list,
  properties (<https://www.tradingview.com/pine-script-docs/concepts/strategies/>)
- IBKR Risk Navigator: portfolio-level risk with drill-down views
  (<https://www.ibkrguides.com/traderworkstation/risk-navigator.htm>)

## Product Thesis

The operator needs a workflow, not more isolated tables.

```text
Universe / data quality
  -> Signal decision trace
  -> Portfolio and risk impact
  -> Order/fill lifecycle
  -> Backtest-vs-paper evidence
  -> Promotion gate decision
```

The current UI already has Cockpit, positions, signals, trades, experiments,
builder, and execute pages. The missing layer is the operator decision model:
why the system is allowed to trade, why a signal happened or was blocked, how
risk changed, and whether paper evidence matches backtest expectations.

## Non-Negotiable Constraints

- Paper-safe by default. Do not add live order controls.
- Do not bypass `config/futures_live.yaml::enabled` or
  `futures:live:suspended`.
- Preserve stock swing behavior: no blanket EOD liquidation.
- Preserve futures long/short symmetry and `signal_direction` semantics.
- Use Redis DB 1 and TTLs for any new ephemeral UI state.
- Prefer existing dashboard APIs before adding routes.
- New UI must stay behind Caddy on `DASHBOARD_HOST_PORT` and use existing
  Next.js `strategy-builder-ui/`.
- Keep Strategy Lab generated/paper actions clearly labeled as paper.

## Current Surface Inventory

Frontend pages:

| Page | Current role | Gap |
|---|---|---|
| `/` | Cockpit: positions, compact signals/fills, equity/cash, quick actions | Needs health/data freshness/scheduler/forecast/F9/kill-switch merged into one ops state |
| `/signals` | Signal table with filters | Needs reason tree, reject reason, risk/LLM veto, orderability, linked lifecycle |
| `/positions` | Open positions | Needs exposure drill-down and risk budget usage |
| `/trades` | Live/history trades, PnL charts | Needs signal/order/fill lineage and backtest-vs-paper comparison |
| `/experiments` | Stock experiment reports and on-demand jobs | Needs comparator against paper windows and promotion gate evidence |
| `/builder` | Visual strategy builder and paper registration | Needs lifecycle/promotion state and evidence artifacts |
| `/execute` | Upstream-compatible paper signal/order flow | Needs tighter integration with Strategy Lab lifecycle or eventual de-emphasis |

Relevant backend routes already exist:

- `services/dashboard/routes/health.py`
- `services/dashboard/routes/signals.py`
- `services/dashboard/routes/trades.py`
- `services/dashboard/routes/trading.py`
- `services/dashboard/routes/experiments.py`
- `services/dashboard/routes/strategy_lab.py`
- `services/dashboard/routes/kis_builder.py`

## Target Information Architecture

Primary nav should remain compact, but the concepts should be clear:

| Area | User question |
|---|---|
| Ops Cockpit | Is it safe and meaningful to trade now? |
| Signals | Why did this signal happen or get rejected? |
| Risk | What is the current exposure and failure mode? |
| Experiments | Does backtest evidence support this strategy? |
| Paper Review | Did paper behavior match the expected backtest profile? |
| Strategy Lab | How do I change, test, and promote a strategy? |

## Multi-Agent Implementation Model

Work should be split by contract boundaries. Each agent owns one lane and
publishes a small, typed interface or page slice. Agents should not make broad
cross-lane refactors.

### Agent Lanes

| Lane | Owner role | Primary files | Output |
|---|---|---|---|
| A0 Product Contract | product/tech lead | this plan, `docs/ROADMAP.md`, route/type docs | Shared schemas, terminology, acceptance gates |
| A1 Backend Observability | backend agent | `services/dashboard/routes/health.py`, `metrics.py`, `trading.py` | Ops summary DTO for cockpit |
| A2 Signal Trace | backend+frontend agent | `signals.py`, `trades.py`, `strategy_lab.py`, `/signals` | Signal detail DTO + signal trace drawer |
| A3 Risk & Exposure | backend+frontend agent | `trading.py`, `health.py`, position components | Risk/exposure board and drill-down |
| A4 Experiment Comparator | backend+frontend agent | `experiments.py`, `trades.py`, `/experiments` | Backtest-vs-paper comparator |
| A5 Lifecycle Blotter | backend+frontend agent | `signals.py`, `trades.py`, Strategy Lab store | Signal -> ticket -> order -> fill timeline |
| A6 Promotion Kanban | frontend+config agent | `/builder`, `/experiments`, registered strategies APIs | Evidence-based promotion board |
| A7 UX QA | QA/accessibility agent | Playwright/screenshots, component tests | Responsive, accessible, non-overlapping UI |

### Coordination Rules

- A0 defines DTO names first. Other agents may add optional fields but must not
  rename shared fields without updating every consumer.
- Backend lanes ship fixture JSON in tests before frontend consumes it.
- Frontend lanes use mock/fixture data for layout tests before backend routes
  are complete.
- Each lane owns focused tests and one screenshot checklist.
- No lane changes live trading behavior. If a lane discovers missing runtime
  data, expose it as `unknown` / `not_available`, not as a blocking exception.

## Shared DTO Contracts

Use these as first-pass contracts. Fields can be optional when data is absent.

### `OpsSummary`

```yaml
asset_class: stock | futures | all
as_of: ISO-8601
mode:
  trading_mode: paper | live | unknown
  real_trading: boolean
health:
  dashboard: ok | degraded | error
  redis: ok | degraded | error
  runtime_ledger: ok | degraded | error
  scheduler: ok | stale | unknown
  producers: ok | stale | unknown
data_freshness:
  ticks_age_seconds: number | null
  daily_indicators_age_seconds: number | null
  universe_age_seconds: number | null
forecasting:
  har_rv_age_seconds: number | null
  stale: boolean
kill_switch:
  enabled: boolean
  active_conditions: list
pipeline:
  stock_pipeline_mode: live | shadow | off | unknown
  futures_f9_state: dormant | shadow | gate2 | cutover | unknown
pnl:
  today_pnl_krw: number
  realized_pnl_krw: number | null
  unrealized_pnl_krw: number | null
```

### `SignalTrace`

```yaml
signal_id: string
asset_class: stock | futures
strategy: string
symbol: string
side: BUY | SELL | HOLD
timestamp: ISO-8601
status: generated | blocked | order_ticket_created | submitted | filled | rejected | expired
reason: string
confidence: number | null
price: number | null
decision_inputs:
  indicators: map
  regime: string | null
  llm_context: map | null
  setup: string | null
reject:
  stage: strategy | risk | order_router | exit | unknown | null
  reason: string | null
orderability:
  state: paper_orderable | blocked | stale_data | position_conflict | insufficient_cash | not_supported
  details: string | null
links:
  order_id: string | null
  fill_id: string | null
  position_id: string | null
  trade_id: string | null
```

### `RiskExposure`

```yaml
asset_class: stock | futures | all
as_of: ISO-8601
portfolio:
  equity_krw: number | null
  cash_krw: number | null
  gross_exposure_krw: number
  net_exposure_krw: number
  daily_loss_krw: number
  max_drawdown_pct: number | null
by_strategy:
  - strategy: string
    positions: number
    exposure_krw: number
    unrealized_pnl_krw: number
    realized_pnl_krw: number | null
    max_position_usage_pct: number | null
by_symbol:
  - symbol: string
    strategy: string
    side: long | short
    exposure_krw: number
    pnl_pct: number
```

### `BacktestPaperComparison`

```yaml
strategy: string
asset_class: stock | futures
window:
  start: date
  end: date
backtest:
  total_return_pct: number | null
  sharpe: number | null
  max_drawdown_pct: number | null
  win_rate_pct: number | null
  trades_per_day: number | null
paper:
  total_return_pct: number | null
  sharpe_proxy: number | null
  max_drawdown_pct: number | null
  win_rate_pct: number | null
  trades_per_day: number | null
  rejected_orders: number
divergence:
  status: aligned | watch | fail | insufficient_data
  reasons: list[string]
gate:
  recommendation: hold_disabled | shadow | small_paper | promote_candidate
  missing_evidence: list[string]
```

## Phased Plan

### P0.1 Ops Cockpit 2.0

Status: Initial implementation complete via enriched `/api/health/summary`.

Goal: one scan-friendly page for "can the system trade now?"

Backend tasks:

- Add or extend a single `/api/health/summary` response to satisfy `OpsSummary`.
- Include scheduler/producers freshness from Redis keys or known service status.
- Include HAR-RV freshness and stale model state from existing forecasting
  endpoint.
- Include F9 state as `dormant` until a reliable source exists.

Frontend tasks:

- Add Cockpit status bands: System, Data, Forecast, Pipeline, Risk.
- Preserve dense layout; avoid marketing-style cards.
- Each degraded state links to the relevant runbook or page.

Acceptance:

- Operator can see Redis, RuntimeLedger, data freshness, forecast stale, kill
  switch, stock pipeline, and futures F9 state without leaving `/`.
- Unknown data is explicit and does not render as healthy.

### P0.2 Signal Decision Trace

Status: Initial implementation complete via enriched `/api/signals` rows and
`/signals` trace detail panel.

Goal: every signal tells its story.

Backend tasks:

- Extend `/api/signals` rows with optional trace summary fields.
- Add `/api/signals/{id}` detail if the existing model is too compact.
- Normalize reject reasons from strategy/risk/order-router streams where
  available.

Frontend tasks:

- Add a signal detail drawer on `/signals`.
- Show reason, indicator values, regime, LLM/veto/risk state, reject stage,
  orderability, and linked order/fill/position.
- Add filters for `blocked`, `paper_orderable`, `filled`, `rejected`.

Acceptance:

- A `technical_consensus`, `momentum_breakout`, Setup A, or Setup C signal can be
  inspected without reading logs.
- Rejected signals show the blocking stage when known.

### P0.3 Risk & Exposure Board

Status: Initial implementation complete via `/api/trading/risk-exposure` and
`/risk`.

Goal: portfolio-level risk with drill-down.

Backend tasks:

- Build `RiskExposure` from positions, trading status, RuntimeLedger trades, and
  configured limits where available.
- Do not invent missing limits; expose `null` and a warning.

Frontend tasks:

- Add `/risk` or a Cockpit tab/section.
- Show portfolio totals, by-strategy exposure, by-symbol exposure, daily loss,
  max-position usage, kill-switch active conditions.

Acceptance:

- Futures long/short exposure is represented symmetrically.
- Stock swing positions are shown without implying forced EOD liquidation.

### P0.4 Backtest-vs-Paper Comparator

Status: Initial implementation complete via
`/api/kis-builder/experiments/latest/compare-paper` and `/experiments`.

Goal: strategy reactivation and promotion decisions have evidence in the UI.

Backend tasks:

- Add comparison endpoint using stock experiment reports plus RuntimeLedger
  trades for matching strategy/window.
- Start with stock strategies; design schema to support futures later.

Frontend tasks:

- Extend `/experiments` with "Compare to paper" per strategy.
- Show aligned/watch/fail/insufficient-data status and missing evidence.

Acceptance:

- `technical_consensus` reactivation and `momentum_breakout` observation can be
  reviewed from one panel.
- Missing paper window or insufficient trades is explicit.

### P1.1 Lifecycle Blotter

Status: Initial implementation complete via `/api/trades/lifecycle` and
`/trades` timeline panels.

Goal: trace execution from signal to closed trade.

Tasks:

- Add lifecycle timeline component reusable from `/signals`, `/trades`, and
  Strategy Lab.
- Link signal id, ticket id, order id, fill id, position id, trade id when
  available.
- For legacy rows without full lineage, show partial timeline with gaps.

Acceptance:

- A filled or rejected paper action can be debugged without cross-checking three
  pages and logs.

### P1.2 Strategy Promotion Kanban

Status: Initial implementation complete via read-only `/builder` promotion
board.

Goal: visible gate state for each strategy/draft.

Columns:

```text
Draft -> Validated -> Backtested -> Swept -> Paper Enabled -> Paper Observed -> Live Gated
```

Tasks:

- Use existing registered strategy APIs and experiment reports first.
- Attach evidence artifacts: validation result, latest backtest, latest paper
  comparison, risk notes, operator gate.
- Live-gated column is display-only until explicit live approval workflow exists.

Acceptance:

- No strategy appears "promotable" without evidence links.
- Paper/live distinction is obvious.

### P1.3 Universe & Data Coverage Explorer

Status: Initial implementation complete via `/api/coverage` and `/coverage`.

Goal: explain why strategies do or do not have candidates.

Tasks:

- Show screener universe, trade targets, daily indicators, missing symbols,
  minute/daily data coverage, KIS 30-day minute-data limit, and stale keys.
- Link strategy experiment coverage gaps to the same explorer.

Acceptance:

- A no-signal day can be triaged as data/universe issue vs strategy selectivity.

### P2 Setup C / Event Context Diagnostics

Goal: make Setup C no-signal root cause visible.

Status: implemented via `/api/event-context/diagnostics` and `/event-context`.

Tasks:

- Add event-score freshness/sparsity panel.
- Show news/macro source timeline and scoring status.
- Add Setup C candidate count, blocked reason distribution, and missing event
  source warnings.

Acceptance:

- Operator can distinguish "Setup C is selective" from "event sourcing is empty."

### P2.1 Workbench UI/UX QA Pass

Status: complete.
Automated smoke coverage exercises `/risk`, `/coverage`, `/trades`, `/builder`,
and `/event-context` loading, empty, degraded, tab, and read-only states.
Playwright desktop/mobile checks remain the required visual gate when these
routes change.

Closure evidence (2026-06-25 KST): Vitest smoke coverage is committed in
`strategy-builder-ui/src/app/quant-ops-workbench.smoke.test.tsx`. Playwright
fallback desktop/mobile screenshots and interaction checks are retained in
[../testing/quant-ops-workbench-2026-06-25.md](../testing/quant-ops-workbench-2026-06-25.md).
The earlier static audit that found the missing screenshot gap is preserved at
[../investigations/2026-06-25-roadmap-codebase-consistency.md](../investigations/2026-06-25-roadmap-codebase-consistency.md).

Goal: verify the new operator workflows render cleanly and remain paper-safe
across desktop/mobile states.

Tasks:

- [x] Add automated smoke coverage for loading, empty, and degraded states using
  the existing Vitest/Testing Library stack.
- [x] Run desktop/mobile visual checks for `/risk`, `/coverage`, `/trades`,
  `/builder`, and `/event-context`.
- [x] Check interactive controls for accessible names and confirm no new surface can
  submit live orders.

Acceptance:

- Key Quant Ops Workbench pages render without runtime crashes under mocked or
  degraded data.
- Navigation, refresh buttons, tables, timelines, evidence boards, and warning
  states remain scan-friendly on desktop and mobile widths.
- Live-trading controls are not introduced by the QA pass.

## Test Plan

Per lane:

- Backend: unit tests for DTO builders with full, partial, and unavailable data.
- Frontend: component tests for degraded/empty/loading states.
- Integration: mocked API fixture page render for desktop and mobile widths.
- Manual QA: browser screenshot pass for `/`, `/signals`, `/experiments`,
  `/risk`, `/coverage`, `/trades`, `/builder`, and `/event-context`.
- Safety: verify no new UI control can submit live orders.

Global checks:

```bash
cd strategy-builder-ui
npm run lint
npm run build

pytest tests/unit/dashboard tests/unit/strategy_lab -q
```

## Multi-Agent Handoff Checklist

Historical checklist, completed by the 2026-06-22 Workbench implementation.

Before parallel implementation:

- [x] A0 publishes final DTO names and first fixture JSON under a test fixture
      path.
- [x] A1-A5 agree on `asset_class` filter behavior (`stock`, `futures`, `all`).
- [x] A7 defines desktop/mobile screenshot viewport list.
- [x] Backend lanes add route-level tests before frontend binds to routes.
- [x] Frontend lanes use feature flags or graceful empty states until all routes
      are present.

During implementation:

- [x] Keep PRs lane-scoped.
- [x] Do not rename existing public routes unless all callers are updated in the
      same PR.
- [x] Add docs for any new route in [../api.md](../api.md) only after route
      behavior is stable.
- [x] Update [../ROADMAP.md](../ROADMAP.md) phase status only after merged work
      and verification.

## Open Questions

- Should P0 surfaces be new pages (`/risk`, `/paper-review`) or Cockpit tabs?
  Default: start as Cockpit sections/drawers, split pages only if density
  becomes hard to scan.
- Where should long-lived paper comparison artifacts be stored? Default:
  recompute from RuntimeLedger + experiment reports first; persist only if slow.
- Should `/execute` remain separate after Strategy Lab paper tickets mature?
  Default: keep compatibility route but make Strategy Lab the primary workflow.
