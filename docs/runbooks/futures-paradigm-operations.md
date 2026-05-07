# Futures Paradigm — Daily Operations Runbook

Day-to-day operating checklist for the Phase 5 futures paradigm system
(Setup A/C + Phase 4 stack: decision_engine, risk_filter, order_router,
kill_switch). Use alongside `futures-paradigm-failure-modes.md` (Phase 4)
and the Grafana dashboards in `monitoring/grafana/dashboards/`.

## 09:00 — Status check (mandatory before market open at 09:00 KST)

- [ ] All 4 systemd units running: `systemctl is-active kis-decision-engine kis-risk-filter kis-order-router kis-kill-switch` → all `active`
- [ ] No kill-switch sentinel: `! test -f /var/run/kis_kill_switch.tripped`
- [ ] No position-recovery sentinel: `! test -f /var/run/kis_position_recovery.tripped`
- [ ] Live-mode guard state matches intent: `redis-cli -n 1 get futures:live:suspended` returns `(nil)` for "live runs", or `1` for "paused"
- [ ] Daily-trade counter from prior session expired (or absent): `redis-cli -n 1 get "order_router:daily_trades:$(TZ=Asia/Seoul date +%Y-%m-%d)"` returns `(nil)` at session start
- [ ] Grafana **Futures Paradigm — Risk** dashboard: all 6 condition tiles green
- [ ] Last 1h fills count sane on **Futures Paradigm — Overview** (no runaway order rate)

## Noon — Signal review

- [ ] **Futures Paradigm — Overview** signal-by-setup count is non-zero by 12:00 (zero by noon = signal pipeline likely broken)
- [ ] Open-positions table shows ≤ `futures_live.max_position_size_contracts` (currently 1)

## 15:30 — EOD flat verification

- [ ] All futures positions closed by 15:15 (EOD close logic — `eod_close_hour=15, eod_close_minute=15` in exit configs, executed before futures market close at 15:45). Check: `clickhouse-client --query "SELECT count() FROM kospi.swing_positions WHERE asset_class='futures' AND status='open'"` → 0
- [ ] If non-zero: investigate before next session. Manual close: `python -m scripts.trading.flatten_all --confirm --reason eod_manual`
- [ ] Today PnL recorded: see **Overview → Today PnL**

## Overnight — Macro readiness (if running 24h pipelines)

- [ ] News collector → scorer pipeline lag < 300s (kill_switch threshold)
- [ ] ClickHouse insert error rate < 10% (kill_switch threshold)

## Weekly cadence

| Day/Time | Action |
|----------|--------|
| Mon 06:00 KST | Review Telegram-delivered Weekly Edge Review (`scripts/analysis/weekly_edge_review.py`). Look for ACTIONS sections — they only appear when something is actionable. |
| Mon 09:00 KST | If Weekly Edge Review flagged a setup as `pause` or `retune`, follow the runbook section in the report. |
| Twice-yearly (Apr + Oct, last Sat) | Run rollback drill: `bash scripts/drills/rollback_drill.sh`. Output to `reports/drills/rollback_YYYYMMDD.txt`. See `futures-paradigm-rollback.md` § Drill cadence. |

## Common operator commands

```bash
# Pause live trading without restarting (runtime kill via Redis flag)
redis-cli -n 1 set futures:live:suspended 1

# Resume live trading
redis-cli -n 1 del futures:live:suspended

# Emergency flatten (dry-run first, then --confirm)
python -m scripts.trading.flatten_all
python -m scripts.trading.flatten_all --confirm --reason "<reason>"

# Recover from kill_switch trip (after operator review of cause)
bash scripts/kill_switch_clear.sh

# Recover from position-recovery sentinel (after manual reconciliation)
bash scripts/recover_positions_clear.sh

# Tail order_router logs
journalctl -u kis-order-router -f --since "1h ago"

# Inspect today's Gate-3 daily-trade counter (KST date)
redis-cli -n 1 get "order_router:daily_trades:$(TZ=Asia/Seoul date +%Y-%m-%d)"

# Reset counter mid-day (use only with explicit reason — burns the audit
# trail of how many orders we've placed today)
redis-cli -n 1 del "order_router:daily_trades:$(TZ=Asia/Seoul date +%Y-%m-%d)"
```

## Escalation

- **Telegram alerts (`is_critical=True`)**: drop everything, check Grafana Risk dashboard, identify which condition tripped (`kill_switch_condition_value{name="..."}`), then follow `futures-paradigm-failure-modes.md` matrix.
- **Sentinel files present at startup**: refuse to clear without RCA. The sentinel exists *because* the prior session detected something the daemon refuses to silently absorb.

Spec: `docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md` §6.1 / §7.1.
