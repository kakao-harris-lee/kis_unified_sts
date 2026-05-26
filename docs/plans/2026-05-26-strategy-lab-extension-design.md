# Strategy Lab Redesign

**Date**: 2026-05-26
**Status**: Design proposal
**Goal**: Make `kis_unified_sts` a visual strategy workstation where an
operator designs a trading strategy in the UI, sees generated BUY/SELL/HOLD
signals, and can execute paper buy/sell orders directly from those signals.
Backtesting and sweeps support the loop, but the signal-to-order workflow is
the center of the product.

This repo currently operates with backtesting and paper trading only. There is
no live-order runtime to protect in the current scope, so the design should
optimize for strategy iteration speed, backtest depth, and paper-trading
feedback loops. Live trading, if introduced later, must be a new promotion tier
with separate controls.

---

## References

Primary reference repository: <https://github.com/koreainvestment/open-trading-api>

Reference areas:

- `strategy_builder/README.md`: visual builder, YAML import/export, signal
  generation, order execution flow.
- `strategy_builder/strategy_core/dsl/`: builder-state to DSL parsing and
  generated Python strategy code.
- `strategy_builder/strategy_core/executor.py`: unified execution routes for
  preset, builder-state, local, and custom strategies.
- `backtester/README.md`: strategy selection, `.kis.yaml` import, parameter
  controls, results UI, MCP job model.
- `backtester/kis_backtest/core/schema.py`: unified strategy schema and
  operator normalization.
- `backtester/kis_mcp/tools/backtest.py`: async backtest jobs, file-backed job
  state, polling, retry.

Current repo anchors:

- Strategy runtime: `shared/strategy/base.py`, `shared/strategy/registry.py`,
  `services/trading/strategy_manager.py`.
- Strategy config: `config/strategies/{stock,futures}/*.yaml`.
- Backtest runtime: `shared/backtest/{engine,adapter,daily_adapter,config}.py`,
  `cli/main.py sts backtest run`.
- Paper runtime: `services/trading/orchestrator.py`.
- Dashboard: `services/dashboard/routes/*`, `dashboard-frontend/src`.

---

## Product Direction

Build a first-class **Strategy Lab** inside the existing dashboard.

The core user path is:

```text
Visual Builder
  -> Generate Signals
  -> Inspect Signal Cards
  -> Create Paper Order Ticket
  -> Execute Paper Buy/Sell
  -> Track Fill / Position / PnL
  -> Revise Strategy
```

The lab should let an operator:

1. Design a strategy visually.
2. Generate executable BUY/SELL/HOLD signals for selected symbols.
3. See each generated signal as a first-class UI object with reason,
   confidence, price context, risk, and orderability status.
4. Convert a signal into a paper order ticket.
5. Execute paper buy/sell from the ticket.
6. Track the resulting paper fill, position, and PnL back to the originating
   strategy draft and signal.
7. Run single-symbol and portfolio backtests.
8. Compare parameter sweeps.
9. Promote a validated draft into automated paper trading.
10. Iterate from observed signal/order failures back into the builder.

The reference project separates Strategy Builder and Backtester into separate
apps. This repo should integrate them into one loop because it already has a
dashboard, paper runtime, strategy registry, and backtest engine.

---

## Design Stance

Borrow aggressively:

- Visual indicator/rule/risk builder.
- Signal generation and signal result UI.
- Signal-driven paper buy/sell execution.
- `.kis.yaml` compatible import and export.
- Generated Python preview.
- Dynamic generated strategy execution for backtest and paper mode.
- Async backtest jobs with polling and retry.
- Multi-stock result dashboards.
- Preset strategy catalog plus local/generated strategies.
- Optional AI/MCP-facing backtest API.

Adapt to this repo:

- Use the existing ClickHouse data loaders, Redis state, paper orchestrator, and
  strategy registry.
- Keep generated strategies under an explicit `lab` namespace.
- Support both compiled in-memory execution and generated file execution.
- Make manual signal-to-paper-order execution and automated paper execution
  first-class endpoints, not only offline export steps.

Keep out of scope for now:

- Live/cash trading controls.
- Broker-side real order execution.
- Separate Next.js/FastAPI apps.

---

## Target Architecture

```text
dashboard /strategy-lab
  |
  | builder state / YAML / generated code
  v
services/dashboard/routes/strategy_lab.py
  |
  | validate, compile, generate signals, order ticket, paper order,
  | backtest, sweep, paper-run, promote
  v
shared/strategy_lab/
  schema.py          StrategySpec v1, .kis.yaml compatibility
  capabilities.py    indicators, operators, timeframes, risk fields
  dsl.py             builder state <-> DSL <-> StrategySpec
  codegen.py         StrategySpec -> Python strategy module
  sandbox.py         generated-module load and validation
  compiler.py        StrategySpec -> TradingStrategy / YAML config
  evaluator.py       current-data and historical signal execution
  signal_store.py    signal lifecycle and traceability
  order_bridge.py    signal -> paper order ticket/execution
  backtest_jobs.py   async jobs, retries, artifacts, Redis state
  paper_jobs.py      paper strategy registration and paper-run lifecycle
  reports.py         result JSON, markdown, chart payloads
  yaml_io.py         .sts.yaml and .kis.yaml import/export
  |
  +--> shared/strategy/registry.py
  +--> shared/backtest/engine.py
  +--> services/trading/orchestrator.py
  +--> shared/execution / paper broker path
  +--> services/dashboard/routes/{signals,trades,trading}.py
```

The core change is that Strategy Lab owns a strategy draft lifecycle. Existing
runtime components become execution targets.

Signals are not a secondary artifact. A generated signal must have an ID,
visible card, reason, confidence, source draft, source code hash, latest market
inputs, and an orderability state.

---

## Strategy Lifecycle

```text
DRAFT
  -> validated
  -> backtested
  -> swept
  -> paper_enabled
  -> paper_observed
  -> revised
```

Each stage stores artifacts:

- `draft`: normalized `StrategySpec`.
- `validated`: schema result, warnings, required data.
- `backtested`: result JSON, equity curve, trade list, summary metrics.
- `swept`: parameter grid/random search results.
- `paper_enabled`: generated YAML/module plus paper runtime registration.
- `paper_observed`: signal/fill/PnL snapshots linked to the lab strategy ID.

Signal lifecycle:

```text
generated
  -> displayed
  -> order_ticket_created
  -> paper_order_submitted
  -> paper_filled | paper_rejected | expired | dismissed
```

Every signal stores:

- `signal_id`
- `draft_id`
- `strategy_name`
- `code` / `name`
- `side`: BUY, SELL, HOLD
- `confidence`
- `strength`
- `reason`
- `reference_price`
- `risk_snapshot`
- `generated_at`
- `source`: preview, backtest, paper_run
- `orderability`: actionable, blocked, expired, position_conflict,
  insufficient_cash, stale_data
- optional `paper_order_id`, `fill_id`, and `position_id`

Redis keys use DB 1 and TTLs:

- `strategy_lab:draft:{draft_id}`: 48h TTL.
- `strategy_lab:job:{job_id}`: 24h TTL.
- `strategy_lab:paper:{run_id}`: 24h TTL after stop.
- `strategy_lab:signal:{signal_id}`: 24h TTL after final state.

Durable artifacts:

- `reports/strategy_lab/{date}/{job_id}.json`
- `reports/strategy_lab/{date}/{job_id}.md`
- `reports/strategy_lab/{date}/{job_id}.html` optional
- generated strategies under `var/strategy_lab/generated/` for runtime loading,
  with YAML exports optionally copied into `config/strategies/*/generated/`.

Generated runtime files should not be enabled by default in git-tracked config.
The lab can still load them directly for paper mode.

---

## StrategySpec V1

Use a Pydantic schema under `shared/strategy_lab/schema.py`. The schema should
normalize reference repo `.kis.yaml` fields and native `.sts.yaml` fields into
one internal representation.

```yaml
version: "sts.strategy.v1"

metadata:
  id: "lab_sma_rsi_pullback"
  name: "SMA + RSI Pullback"
  description: "Generated in Strategy Lab"
  author: "operator"
  tags: ["stock", "daily", "pullback"]

strategy:
  asset_class: "stock"
  timeframe: "daily"
  category: "custom"

  indicators:
    - id: "sma"
      alias: "sma_fast"
      params: { period: 20 }
    - id: "sma"
      alias: "sma_slow"
      params: { period: 60 }
    - id: "rsi"
      alias: "rsi5"
      params: { period: 5 }

  entry:
    logic: "AND"
    conditions:
      - left: { indicator: "sma_fast" }
        operator: "greater_than"
        right: { indicator: "sma_slow" }
      - left: { indicator: "rsi5" }
        operator: "less_equal"
        right: { value: 45 }

  exit:
    logic: "OR"
    conditions:
      - left: { indicator: "sma_fast" }
        operator: "less_than"
        right: { indicator: "sma_slow" }

risk:
  stop_loss_pct: 7.0
  take_profit_pct: 0.0
  trailing_stop_pct: 3.0
  max_hold_bars: 10

position:
  type: "fixed"
  params:
    order_amount_per_stock: 10000000
    max_positions: 3

paper:
  enabled: false
  universe:
    symbols: ["005930", "000660"]
  budget:
    capital: 100000000
```

V1 should support:

- `stock` daily and minute strategies first.
- `futures` only after stock path proves stable.
- Operator aliases from `.kis.yaml`: `crosses_above`, `cross_above`, `>`,
  `gte`, etc.
- Simple arithmetic operands: `indicator * scalar`, `indicator + scalar`.
- Nested condition groups.
- Parameter definitions for sweeps:

```yaml
params:
  rsi_limit:
    default: 45
    min: 25
    max: 55
    step: 5
```

---

## Execution Model

Use two execution paths from day one.

### 1. Rule Engine Path

Implement generic components:

- `shared/strategy/entry/rule_based.py`
- `shared/strategy/exit/rule_based.py`

This path evaluates `StrategySpec` directly against `EntryContext`,
`ExitContext`, and `BacktestStrategyAdapter` inputs. It is stable, easy to test,
and good for most builder strategies.

### 2. Generated Python Path

Implement code generation:

- `shared/strategy_lab/codegen.py`
- `shared/strategy_lab/sandbox.py`

Generated modules can run in backtest and paper mode. This copies the useful
part of `strategy_builder/strategy_core/dsl/codegen.py` without creating a
separate app.

Guardrails:

- Generated modules import only allowlisted repo modules.
- No filesystem writes from generated strategy code.
- No network calls from generated strategy code.
- Generated class must implement the same adapter interface as existing
  backtest strategies.
- Module load must happen through `strategy_lab.sandbox`, never arbitrary
  `importlib` in routes.
- Generated code is stored with content hash and linked to `draft_id`.

Because current scope is backtest and paper trading only, dynamic strategy
execution is acceptable and useful. If live trading is added later, generated
code must pass a separate promotion gate or compile to static reviewed YAML.

---

## Backtest Engine Strategy

Run current in-repo engine as the primary engine.

```text
StrategySpec
  -> validate
  -> choose rule_engine or generated_python
  -> load ClickHouse data
  -> DailyBacktestAdapter or BacktestStrategyAdapter
  -> BacktestEngine.run()
  -> persist result
```

Add a secondary optional backend later:

- `backend = "native"`: existing `shared/backtest` engine.
- `backend = "lean"`: optional independent verification inspired by
  `open-trading-api/backtester`.

Lean should not block the first implementation. The native engine gives faster
iteration and matches paper runtime more closely.

---

## Signal-To-Order Integration

The visual builder must produce actionable signals, not just YAML.

Signal generation modes:

1. **Preview Signal**
   - Runs the draft strategy against current market data for selected symbols.
   - Produces BUY/SELL/HOLD cards immediately.
   - Best for interactive strategy design.

2. **Backtest Signals**
   - Shows historical generated signals over the chart and trade table.
   - Used to understand whether a rule triggers for the right reason.

3. **Paper Run Signals**
   - Runs continuously while a paper run is active.
   - Signals can be auto-executed or manually executed depending on run mode.

Signal card requirements:

- Side badge: BUY, SELL, HOLD.
- Confidence/strength.
- Current or backtest reference price.
- Matched rule explanations.
- Required indicators and latest values.
- Risk preview: stop, target, max position, estimated order amount.
- Action buttons:
  - `Create Buy Ticket` for BUY.
  - `Create Sell Ticket` for SELL when a matching paper position exists.
  - `Dismiss` for HOLD or rejected signals.

Order ticket requirements:

- Paper-only label.
- Symbol, side, quantity, order amount, estimated price.
- Source signal and strategy draft.
- Position impact preview.
- Cash/position validation.
- Submit button for paper buy/sell.

Execution path:

```text
SignalCard
  -> OrderTicket
  -> strategy_lab.order_bridge
  -> existing paper broker / orchestrator execution path
  -> fill / reject
  -> dashboard position + trade state
```

Manual signal execution is required for the first implementation. Automated
paper execution can be enabled per paper run after the manual path works.

---

## Paper Trading Integration

Paper mode should be a core Strategy Lab feature.

Add:

- `POST /api/strategy-lab/paper-runs`
- `GET /api/strategy-lab/paper-runs/{run_id}`
- `POST /api/strategy-lab/paper-runs/{run_id}/stop`

Paper run behavior:

- Compile the draft to `lab_{draft_id}` strategy.
- Register generated/rule strategy in memory for the paper orchestrator.
- Start paper trading with a scoped strategy list and scoped symbol universe.
- Publish all signals/fills/trades with `lab_draft_id` and `paper_run_id`.
- Support manual execution from signal cards.
- Support optional auto-execution for BUY/SELL signals when `auto_execute`
  is enabled for the paper run.
- Reuse existing `services/trading/orchestrator.py`, `PositionTracker`, and
  dashboard signal/trade routes.

Paper run boundaries:

- Capital is paper-only.
- Universe is explicit and visible in the UI.
- Runtime can be stopped from Strategy Lab.
- Results are linked back into the same draft.
- Manual order tickets remain available even when automated paper execution is
  disabled.

This is more useful than export-only promotion because it closes the loop from
design to observed paper behavior.

---

## Dashboard UX

Add `/strategy-lab` to the existing Vite dashboard.

Views:

1. Builder
   - Indicator palette.
   - Rule blocks with AND/OR/nested groups.
   - Risk and position controls.
   - YAML preview.
   - Generated Python preview.
   - Validation warnings.

2. Signals
   - Symbol/watchlist selector.
   - `Generate Signals` command.
   - Signal cards grouped by BUY, SELL, HOLD.
   - Rule explanation and indicator values per signal.
   - Orderability badge per signal.
   - `Create Buy Ticket` / `Create Sell Ticket` actions.
   - Paper order ticket drawer.
   - Submit paper order, fill/reject status, and linked position.

3. Backtest
   - Single symbol, multi-symbol, and watchlist inputs.
   - Date range and capital controls.
   - Native backend selector.
   - Parameter sweep controls.
   - Job status and retry.

4. Results
   - Equity curve.
   - Drawdown curve.
   - Per-symbol trade table.
   - Historical signal markers and reasons.
   - Strategy-vs-benchmark summary.
   - Metrics: total return, monthly expected, CAGR, MDD, Sharpe, win rate,
     profit factor, average win/loss, trade count, exposure.
   - Warnings: no trades, low trade count, high open-position contribution,
     warmup-heavy Sharpe, stale/missing data.

5. Paper
   - Start/stop paper run.
   - Live paper signals.
   - Manual/auto execution mode selector.
   - Paper positions/fills.
   - PnL and drawdown since paper run start.
   - Failure log: validation errors, missing indicators, stale data, order
     rejects, rate-limit waits.

6. Compare
   - Compare drafts and sweeps side by side.
   - Promote best parameter set back into builder.

Unlike the earlier conservative design, the UI may include paper BUY/SELL
execution state because the current system is paper-only. The UI must still
label actions as paper.

---

## API Surface

Add `services/dashboard/routes/strategy_lab.py`.

Endpoints:

- `GET /api/strategy-lab/capabilities`
  - Supported indicators, outputs, operators, timeframes, data requirements.

- `POST /api/strategy-lab/drafts`
  - Save or normalize a draft.

- `POST /api/strategy-lab/validate`
  - Validate `StrategySpec`, `.kis.yaml`, or builder state.

- `POST /api/strategy-lab/preview-code`
  - Return generated Python and generated YAML.

- `POST /api/strategy-lab/preview-signal`
  - Run current-data signal preview for selected symbols.

- `GET /api/strategy-lab/signals/{signal_id}`
  - Return signal details, matched rules, latest indicator values,
    orderability status, and linked paper order/fill.

- `POST /api/strategy-lab/signals/{signal_id}/order-ticket`
  - Build a paper order ticket from an actionable BUY/SELL signal.
  - Validate paper cash, existing position, max positions, and stale data.

- `POST /api/strategy-lab/orders/paper`
  - Submit a paper buy/sell order created from a signal ticket.
  - Returns submitted/rejected/filled status and linked trade identifiers.

- `POST /api/strategy-lab/backtests`
  - Submit async native backtest job.

- `POST /api/strategy-lab/backtests/sweep`
  - Submit parameter sweep job.

- `GET /api/strategy-lab/backtests/{job_id}`
  - Poll job status and results.

- `POST /api/strategy-lab/backtests/{job_id}/retry`
  - Retry failed job with same spec/data request.

- `POST /api/strategy-lab/paper-runs`
  - Start paper execution for a validated draft.
  - Supports `execution_mode=manual|auto`.

- `GET /api/strategy-lab/paper-runs/{run_id}`
  - Paper run status and linked signals/trades.

- `POST /api/strategy-lab/paper-runs/{run_id}/stop`
  - Stop the paper run.

- `POST /api/strategy-lab/export`
  - Export `.sts.yaml`, `.kis.yaml`, or generated Python.

---

## Promotion Model

Replace the previous "promote disabled YAML only" model with a staged model:

1. **Lab Draft**
   - Stored in Redis/artifacts.
   - Editable in UI.

2. **Backtest Candidate**
   - Has completed validation and at least one backtest.

3. **Paper Candidate**
   - Can start a paper run directly from Strategy Lab.
   - No git commit required.

4. **Repo Strategy**
   - Exported into `config/strategies/{asset}/generated/`.
   - Default may be `enabled: false`, but paper-only operators can choose
     `enabled: true` when explicitly exporting a paper profile.

5. **Live Candidate**
   - Future-only tier.
   - Requires a new design and stricter review.

This matches the current operating reality: paper trading is the proving ground,
not a risky deployment target.

---

## Implementation Plan

### Phase 1: Core Schema, YAML, and Capabilities

- Add `shared/strategy_lab/schema.py`.
- Add `shared/strategy_lab/capabilities.py`.
- Add `.kis.yaml` import compatibility and native `.sts.yaml`.
- Add builder-state to `StrategySpec` conversion.
- Add unit tests for aliases, nested conditions, unsupported indicators, risk
  bounds, and param definitions.

### Phase 2: Rule Engine and Generated Code

- Add `rule_based` entry/exit components.
- Add `codegen.py` and generated Python preview.
- Add `sandbox.py` loader for generated modules.
- Add deterministic tests for:
  - direct rule evaluation;
  - generated Python execution;
  - generated YAML instantiation through `StrategyFactory`.

### Phase 3: Native Backtest Jobs

- Add validate/backtest/result/retry endpoints.
- Use Redis DB 1 job state with TTL.
- Persist result JSON/markdown under `reports/strategy_lab/`.
- Add single-symbol and multi-symbol tests with fixture data.
- Add parameter sweep jobs.

### Phase 4: Dashboard Strategy Lab

- Add `/strategy-lab` route.
- Add `strategyLabApi`.
- Build Builder, Signals, Backtest, Results, Compare views.
- Include YAML and Python previews.
- Add signal cards and paper order ticket drawer.
- Add result charts and trade tables.

### Phase 5: Signal-Driven Paper Orders

- Add signal store and signal lifecycle states.
- Add order ticket API.
- Add paper order execution API from signal ticket.
- Link signal -> paper order -> fill -> position/trade.
- Add UI actions for paper buy/sell from signal cards.

### Phase 6: Paper Run Integration

- Add paper run API.
- Add lab strategy runtime registration.
- Add `lab_draft_id` and `paper_run_id` metadata to signals/trades.
- Add Paper view with live signals, positions, fills, and PnL.
- Add start/stop controls scoped to paper-only runs.
- Add `manual` and `auto` paper execution modes.

### Phase 7: Repo Export and Optional MCP

- Export generated strategies to repo config.
- Add CLI:

```bash
sts strategy-lab validate path/to/spec.sts.yaml
sts strategy-lab backtest path/to/spec.sts.yaml --symbol 005930 --start 2025-01-01 --end 2025-12-31
sts strategy-lab paper path/to/spec.sts.yaml --symbols 005930,000660 --capital 100000000
```

- Add MCP-like tools only after the API is stable:
  - list capabilities;
  - validate spec;
  - run backtest;
  - get result;
  - start/stop paper run.

---

## Risks And Controls

- Strategy semantics drift between builder, backtest, and paper.
  - Control: both rule engine and generated Python must run through the same
    adapters used by `BacktestEngine` and paper orchestrator.

- Generated code becomes opaque.
  - Control: always show generated Python preview, persist content hash, and
    link it to result artifacts.

- Bad strategies can churn paper runtime.
  - Control: explicit paper universe, paper capital cap, paper run stop button,
    and per-run metadata.

- Indicator mismatch.
  - Control: capabilities endpoint comes from real resolver/indicator contracts,
    not a hand-maintained UI list.

- Redis accumulation.
  - Control: all lab keys use DB 1 and TTL.

- Future live trading pressure.
  - Control: live is a separate lifecycle tier and not silently unlocked by any
    paper/backtest feature.

---

## First Aggressive Slice

Build this first, not a document-only shell:

1. `StrategySpec` Pydantic schema.
2. `.kis.yaml` import and `.sts.yaml` export.
3. Rule-based entry/exit components.
4. Generated Python preview and sandboxed generated execution.
5. Signal generation API for selected symbols.
6. Dashboard builder page with YAML/Python preview.
7. Signal cards with BUY/SELL/HOLD and rule explanations.
8. Paper order ticket from a generated BUY/SELL signal.
9. Paper buy/sell execution from that ticket.

The first slice is complete only when this works:

```bash
sts strategy-lab signal examples/strategy_lab/sma_rsi_pullback.sts.yaml \
  --symbols 005930,000660
```

and the UI can take a BUY/SELL signal from that output and submit a paper order.

The next slice is backtest:

```bash
sts strategy-lab backtest examples/strategy_lab/sma_rsi_pullback.sts.yaml \
  --symbol 005930 \
  --start 2025-01-01 \
  --end 2025-12-31
```

Then continuous paper:

```bash
sts strategy-lab paper examples/strategy_lab/sma_rsi_pullback.sts.yaml \
  --symbols 005930,000660 \
  --capital 100000000
```
