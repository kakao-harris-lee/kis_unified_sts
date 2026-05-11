# Phase 5 Futures Paradigm — Grafana Dashboards

Dashboards auto-loaded by the existing provisioning at
`monitoring/grafana/provisioning/dashboards/dashboard.yaml`
(no YAML changes required).

## Active

| File | UID | Purpose |
|------|-----|---------|
| `futures-paradigm-overview.json` | `futures-paradigm-overview` | Today PnL / open positions / signal & fill counts (24h) / open-position table |
| `futures-paradigm-risk.json` | `futures-paradigm-risk` | Daily/weekly MDD gauges, consecutive-loss counter, six kill-switch condition gauges, kill-switch trip timeline |
| `llm-primary-phase2-monitoring.json` | `llm-primary-phase2-monitoring` | Phase 2 cutover — RL shadow vs Setup A/C counterfactual, LLM veto rate, kill-switch state |
| `trading-overview.json` | — | Cross-asset trading overview (stock + futures) |
| `signal-monitoring.json` | — | Live signal feed (entry/exit) across strategies |
| `stream-realtime.json` | — | WebSocket stream health & freshness |
| `system-health.json` | — | Process / Redis / ClickHouse / API liveness |
| `futures-trade-history.json` | — | Historical futures trade tape |

## Archived (`archive/`)

| File | Reason |
|------|--------|
| `futures-paradigm-live-ladder.json` | Pre-Gate 3 only; Phase 5 has not entered live ladder (`futures_live.enabled: false`). Restore from archive when Gate 3 opens. |
| `rl-paper-matrix-realtime.json` | Matrix profile comparison no longer used — single production profile. |

## Data sources

- ClickHouse (`uid: clickhouse`) — `kospi.rl_trades`, `kospi.swing_positions`, `kospi.signals_all`, `kospi.order_fills`, `kospi.rl_shadow_predictions`
- Prometheus (`uid: prometheus`) — `risk_state_*`, `kill_switch_condition_value{name="..."}`, `kill_switch_triggered_total`, `trading_errors_total`, `trading_signals_total`, `shadow_logger_*`

Note: `kospi.rl_signals` was deprecated; queries use `kospi.signals_all` filtered by `setup_type IN ('A','C')` for the Phase 2 LLM-primary paradigm.

## When to consult which

- **Operations (intraday)**: `overview` for "what's happening right now"; `risk` for "are we within limits"
- **Phase 2 cutover monitoring**: `llm-primary-phase2-monitoring`
- **Post-incident review**: `risk` (kill-switch panels) + `system-health`
- **Gate 3 progression** (when activated): restore `live-ladder` from archive

## Edits

`allowUiUpdates: true` is set in `dashboard.yaml`, so on-the-fly edits in
the Grafana UI persist *until* the next file change — then the JSON on
disk wins. Treat dashboard JSON as code: edit, commit, deploy.

Spec: `docs/plans/2026-04-20-futures-paradigm-phase5-implementation-plan.md` Task 6.
