# RegimeGate Paper Observation Runbook (P2-③)

Spec: `docs/superpowers/specs/archive/2026-05-22-p2-approach3-setup-ac-regime-gate-design.md`
Plan: `docs/superpowers/plans/archive/2026-05-22-p2-approach3-setup-ac-regime-gate.md`

## Activation (per strategy)

1. Pick the strategy to activate (start with `setup_a_gap_reversion` — fires most frequently in paper).
2. Edit its YAML at `config/strategies/futures/<name>.yaml` and flip `entry.params.regime_gate.enabled: false → true`. Commit the edit (auditable git history).
3. Restart the paper-trading orchestrator so the new config loads:
   ```bash
   sudo systemctl restart kis-trading-paper-futures  # or your paper unit
   ```
4. Confirm the gate is wired by tailing the orchestrator log for `RegimeGate` / `apply_regime_gate` entries on the next entry-signal cycle.
5. Verify the live forecasting service is running and writing `kospi.vol_forecasts`:
   ```bash
   /home/deploy/project/kis_unified_sts/scripts/cron/forecasting.sh status
   ```
6. Verify Redis key freshness:
   ```bash
   redis-cli -n 1 --no-raw GET forecast:vol:current
   # asof field should be within the last ~60s during market hours
   ```

## Weekly review

A cron entry should call the digest every Sunday 18:00 KST:
```
0 9 * * 0  cd /home/deploy/project/kis_unified_sts && set -a; source .env; set +a && .venv/bin/python scripts/analysis/regime_gate_counterfactual.py >> $KIS_LOG_DIR/regime_gate_weekly_$(date +\%Y\%m\%d).log 2>&1
```
(`0 9 * * 0` is 09:00 UTC = 18:00 KST.)

The digest posts to the futures Telegram channel. Read each per-strategy block:

- **`allowed_mean_pnl_pct > blocked_mean_pnl_pct` AND block-rate in 5-30% range** → gate is adding value; keep enabled.
- **block-rate < 5%** → threshold too loose (gate rarely fires); consider tightening `regime_percentile_max` (e.g. 60 → 55).
- **block-rate > 30%** → threshold too tight (gate over-blocks); loosen.
- **`allowed_mean_pnl_pct ≤ blocked_mean_pnl_pct`** → gate is not helping; review decisions in `regime_gate_decisions` + paper P&L logs; consider tightening threshold OR disabling.

After ≥2 weeks per activated strategy, decide:

- Keep enabled (gate adds value)
- Re-tune threshold (separate small follow-up)
- Disable (gate doesn't help on this strategy)

## Rollback

To disable the gate on a strategy without removing the wiring:
1. Edit YAML, set `entry.params.regime_gate.enabled: false`.
2. Commit + restart the paper orchestrator.

The gate code remains in place; only the per-strategy opt-in is rescinded.

To remove the entire wiring (rare): revert PR 2026-05-22 P2-③ — orchestrator's adapters fall back to `gate_cfg=None` no-op path.

## Manual digest run (operator-on-demand)

```bash
cd /home/deploy/project/kis_unified_sts
source .env
.venv/bin/python scripts/analysis/regime_gate_counterfactual.py \
    --start-date 2026-05-15 --end-date 2026-05-21 \
    --no-telegram                     # console only; skip Telegram
```

## Known limitations

- **Setup C will show 0/0 signals most weeks** until a separate event-sourcing fix populates `kospi.event_scores` / `config/scheduled_events.yaml`. This is expected, not a defect (spec §6 / §13 correction).
- **Threshold transferability untested** — `regime_percentile_max=60` was tuned on `bb_reversion_15m` backtest (PR e6cfa35 PASS Δ=+3.26). Per-strategy revalidation needed after ≥2 weeks of paper data per activated strategy.
- **`forecast_pct` calibration is suspect (~3× too high)** — does NOT affect this gate's CDF-position semantics (regime_percentile is rank-based), but Setup C's `forecast_atr_equivalent` consumption may be miscalibrated. Separate concern, tracked under master plan v4.11.
- **No live trading affected** — `config/futures_live.yaml::enabled` stays `false` and Redis `futures:live:suspended` flag remains set; this whole feature is paper-only.
- **`A01603` contract roll**: `scripts/analysis/regime_gate_counterfactual.py:85` hardcodes `WHERE code = 'A01603'` (the KOSPI200 connected-near futures contract used in PR #329's HAR-RV training data). After each quarterly roll (~March / June / September / December), this code expires and the script will return empty rows → all cohort P&L estimates become 0.0. **Operator must update the constant in the script after each roll** (or, future PR: parameterize via `--futures-code` CLI flag defaulting to the current near-month). Next expected roll: **2026-06-12**.

## On-call escalation

- Gate hook raises (logs show stack trace from `apply_regime_gate` or `LiveVolInputs`): degrade procedure is automatic (PERMISSIVE), but file an incident — the hook's `except Exception` paths shouldn't fire in normal operation.
- `kospi.regime_gate_decisions` table missing or write rate-limited: check `shared/db/client.py::insert_regime_gate_decisions` log entries; the gate verdict is preserved even when logging fails (spec §6 C2).
- Telegram digest not received Sunday: check cron, check log archive at `$KIS_LOG_DIR/regime_gate_weekly_*.log`; the script archives the message even when Telegram send fails.
