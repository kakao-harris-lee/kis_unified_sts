# Grafana Dashboards — Archived

**Status (as of 2026-05-12)**: All operational dashboards are archived.

The React Cockpit at `http://localhost:8001/` is now the single operational pane for stock + futures monitoring. See `docs/superpowers/specs/2026-05-12-dashboard-redesign-design.md` and `docs/superpowers/plans/2026-05-12-dashboard-redesign.md` for the redesign rationale.

## Active

(empty — all moved to `archive/`)

## Archived (`archive/`)

| File | Reason |
|------|--------|
| `futures-paradigm-overview.json` | Replaced by Cockpit `/` |
| `futures-paradigm-risk.json` | Risk indicators absorbed into Cockpit `GlobalIndicators` + kill-switch state |
| `futures-trade-history.json` | Replaced by `/trades` drill-down |
| `llm-primary-phase2-monitoring.json` | Phase 2 cutover counterfactual still tracked via cron/Telegram; no live dashboard needed |
| `signal-monitoring.json` | Replaced by `/signals` drill-down + Cockpit `SignalsListCompact` |
| `trading-overview.json` | Replaced by Cockpit `/` |
| `stream-realtime.json` | Replaced by Cockpit `GlobalIndicators` data-freshness indicator |
| `system-health.json` | Replaced by Cockpit `GlobalIndicators` process indicator |
| `futures-paradigm-live-ladder.json` | Pre-Gate 3 only; restore when live ladder opens |
| `rl-paper-matrix-realtime.json` | Matrix profile comparison unused — single production profile |

## Restoration (raw debugging)

To re-enable any archived dashboard temporarily for raw ClickHouse / Prometheus debugging:

```bash
git mv monitoring/grafana/dashboards/archive/<name>.json monitoring/grafana/dashboards/<name>.json
# Grafana provisioning auto-reloads
```

To make permanent, commit the move and revert when no longer needed.

## Data sources (unchanged)

- ClickHouse (`uid: clickhouse`) — `kospi.rl_trades`, `kospi.swing_positions`, `kospi.signals_all`, `kospi.order_fills`, `kospi.rl_shadow_predictions`
- Prometheus (`uid: prometheus`) — `risk_state_*`, `kill_switch_condition_value`, `kill_switch_triggered_total`, `trading_errors_total`, `trading_signals_total`, `shadow_logger_*`

## Edits

Treat dashboard JSON as code. `allowUiUpdates: true` is set in `dashboard.yaml` so on-the-fly Grafana UI edits persist *until* the next file change — then the JSON on disk wins.

Spec: `docs/superpowers/specs/2026-05-12-dashboard-redesign-design.md`
