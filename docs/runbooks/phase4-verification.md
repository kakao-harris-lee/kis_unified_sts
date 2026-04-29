# Phase 4 Verification Runbook

Two-week paper-uptime gate per `docs/plans/2026-04-20-futures-paradigm-phase4-execution.md` §9.

## Pre-flight

- [ ] Phase 3 has at minimum **conditional provisional sign-off** per
      `docs/runbooks/phase3-verification.md` § "Phase 3 status determination".
      The original "≥12 months clean data + OOS gate" requirement was
      replaced by the three-pronged path (bootstrap + sensitivity + paper
      fold-in). As of 2026-04-29 the bootstrap gate fails on backtest
      alone — paper deployment is therefore the **primary** evidence
      source for final sign-off.
- [ ] **Conservative ladder enforced** — `phase4_execution.base_quantity`
      in `config/execution.yaml` must be **1** (one contract). Do NOT
      raise this until Phase 3 final sign-off via
      `scripts/walk_forward_paper_foldin.py` passes. Phase 5's 1→2→5
      ladder explicitly gates on this.
- [ ] `rl_mppo` paper account & keys are SEPARATE from Phase 4 paper account (avoid double-entry on the same KOSPI200 mini contract)
- [ ] `KIS_FUTURES_*` credentials configured for Phase 4 paper account
- [ ] `TELEGRAM_FUTURES_*` configured for kill-switch alerts
- [ ] V3 migration applied: `clickhouse-client --query "DESC kospi.order_fills"` shows 16 columns
- [ ] V1 + V2 already applied (signals_all + news_scored)

## Install

```bash
sudo bash deploy/systemd/install_phase4.sh
sudo systemctl enable --now kis-decision-engine
sudo systemctl enable --now kis-risk-filter
sudo systemctl enable --now kis-order-router
sudo systemctl enable --now kis-kill-switch
```

Add Weekly Edge Review to crontab:
```cron
0 5 * * 1 /home/deploy/project/kis_unified_sts/.venv/bin/python -m jobs.weekly_edge_review >> /home/deploy/project/kis_unified_sts/logs/weekly_edge_review/$(date +\%Y\%m\%d).log 2>&1
```

## Weekly checks

### Week 1 endpoint

- [ ] `systemctl show kis-decision-engine kis-risk-filter kis-order-router kis-kill-switch -p NRestarts` returns 0 for all
- [ ] `clickhouse-client --query "SELECT count() FROM kospi.order_fills WHERE filled_at >= now() - INTERVAL 7 DAY"` ≥ 10
- [ ] `clickhouse-client --query "SELECT avg(slippage_ticks) FROM kospi.order_fills WHERE filled_at >= now() - INTERVAL 7 DAY"` ≤ 0.5 (warn) / ≤ 0.4 (gate)
- [ ] `redis-cli -n 1 XLEN stream:signal.candidate` reasonable (no runaway growth)
- [ ] `rl_mppo` Grafana dashboard shows zero regression vs pre-Phase-4 baseline (independent paper account)
- [ ] Weekly Edge Review Telegram delivered Mon 05:00 KST with no negative-EV alerts on either Setup A or C

### Week 2 endpoint (gate decision)

All Week-1 checks plus:
- [ ] `count() FROM kospi.order_fills WHERE filled_at >= now() - INTERVAL 14 DAY` ≥ 20
- [ ] `avg(slippage_ticks)` ≤ 0.4 (gate)
- [ ] Kill switch drill executed at least once: trigger one of the 6 conditions in a controlled window, verify (a) `stream:risk.event` (when wired) emits, (b) `kis-order-router` logs "Kill switch sentinel ... refusing", (c) Telegram alert delivered, (d) systemd shows kis-kill-switch as inactive
- [ ] Backtest vs paper PnL divergence < 20% on the same signals (compare `kospi.signals_all` × `kospi.order_fills` for the period vs the harness replay)

## Kill switch recovery

If the kill switch trips:

1. Investigate root cause via `journalctl -u kis-kill-switch -n 200`
2. Telegram message has the trigger reason + condition details
3. Operator review with risk owner — do **not** clear without approval
4. Run `scripts/kill_switch_clear.sh` (see Task 19 failure-mode doc) — removes the sentinel after confirming PnL state and any open positions
5. `sudo systemctl start kis-order-router kis-kill-switch`

## Rollback

To disable Phase 4 daemons without code changes:

```bash
sudo systemctl stop kis-order-router kis-risk-filter kis-decision-engine kis-kill-switch
sudo systemctl disable kis-order-router kis-risk-filter kis-decision-engine kis-kill-switch
```

`rl_mppo` paper continues unaffected (separate orchestrator path).

## Gate go/no-go

Pass if all checkboxes above are checked. Phase 5 (paper → live ladder)
gate ladder is documented in
`docs/plans/2026-04-20-futures-paradigm-phase5-implementation-plan.md`.
