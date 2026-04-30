# Phase 5 Futures Paradigm — Grafana Dashboards

Three new dashboards added by Phase 5 Task 6. Auto-loaded by the existing
provisioning at `monitoring/grafana/provisioning/dashboards/dashboard.yaml`
(no YAML changes required).

| File | UID | Purpose |
|------|-----|---------|
| `futures-paradigm-overview.json` | `futures-paradigm-overview` | Today PnL / open positions / signal & fill counts (24h) / open-position table |
| `futures-paradigm-risk.json` | `futures-paradigm-risk` | Daily/weekly MDD gauges, consecutive-loss counter, six kill-switch condition gauges, kill-switch trip timeline |
| `futures-paradigm-live-ladder.json` | `futures-paradigm-live-ladder` | Gate 3 ladder progress: current contract size, days completed (of 14), cumulative net PnL, slippage trend, API error rate |

## Data sources

- ClickHouse (`uid: clickhouse`) — `kospi.rl_trades`, `kospi.swing_positions`, `kospi.rl_signals`, `kospi.order_fills`
- Prometheus (`uid: prometheus`) — `risk_state_*`, `kill_switch_condition_value{name="..."}`, `kill_switch_triggered_total`, `trading_errors_total`, `trading_signals_total`

## When to consult which

- **Operations** (intraday): `overview` for "what's happening right now"; `risk` for "are we within limits"
- **Gate 3 progression** (1→2→5 contracts): `live-ladder` is the source of truth
- **Post-incident review**: `risk` (kill-switch panels) + `live-ladder` (slippage/error rate)

## Edits

`allowUiUpdates: true` is set in `dashboard.yaml`, so on-the-fly edits
in the Grafana UI persist *until* the next file change — then the JSON
on disk wins. Treat dashboard JSON as code: edit, commit, deploy.

Spec: `docs/plans/2026-04-20-futures-paradigm-phase5-implementation-plan.md` Task 6.
