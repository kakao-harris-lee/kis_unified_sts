# Phase 2 Startup Runbook

**Status**: Active for the first Phase 2 trading day (2026-05-11 Mon).
**Predecessor plan**: `docs/plans/2026-05-03-llm-primary-rl-minimization.md` (v3.7).
**Related runbooks**:
- `docs/runbooks/futures-paradigm-operations.md` — daily ops checklist (post-Phase-2).
- `docs/runbooks/futures-paradigm-rollback.md` — emergency rollback.
- `docs/runbooks/phase5-verification.md` — Gate 1–4 verification gates.

---

## Purpose

This runbook covers the first trading-day cutover from pre-Phase-2 (`rl_mppo`
primary, no Setup A/C, no shadow logging) to **Phase 2 paper validation**:

- `rl_mppo` demoted to `shadow_mode: true` — RL still infers but emits no Signal.
- Setup A (gap reversion) and Setup C (event reaction) become primary entries
  via `services/trading/strategy_manager.py` adapters.
- All counterfactual / observability infrastructure is wired and runs
  automatically (see § "What runs automatically" below).

The cutover is **a process restart**, not a code deployment — the code has been
on `main` since 2026-05-08.  The cron and Prometheus assets have been registered
and active since the same day.

## What runs automatically (no operator action needed)

| Component | Schedule | Result |
|-----------|----------|--------|
| `kospi.rl_shadow_predictions` flush | every 60s during process lifetime | rows accumulate for counterfactual analysis |
| Shadow-loggers Prometheus gauges | every 60s | 5 gauges, 4 alerts armed |
| `kospi.signals_all` Setup A/C insert | per signal | Setup detail + LLM tuning audit |
| `kospi.rl_trades` | shadow_mode → 0 inserts | invariant verified by daily check |
| Counterfactual weekly report | Mon 07:00 KST | Telegram briefing channel |
| Phase 2 daily verification | Mon-Fri 16:00 KST | Telegram PASS/FAIL |

## Pre-flight check (Friday EOD before the Monday cutover)

**One-command shortcut**: `bash scripts/cron/phase2_preflight_check.sh`
runs all 9 checks below (5 from this section + crontab + Prometheus +
Telegram credentials + **strategies_loadable_futures runtime check** —
PR #216 regression guard for the 2026-05-11 cutover blocker where YAML
said `enabled: true` but the orchestrator silently loaded only
`rl_mppo`).  Exit code 0 if every critical check passes.
JSON output: `python -m scripts.analysis.phase2_preflight_check --json`.

Or run the individual checks below if you prefer to inspect each
manually.

```bash
cd /home/deploy/project/kis_unified_sts

# 1. ClickHouse migrations applied (V1-V5)
clickhouse-client --user "${CLICKHOUSE_USER:-default}" --password "$CLICKHOUSE_PASSWORD" \
  -q "SELECT version FROM kospi.schema_migrations ORDER BY version FORMAT TabSeparated"
# Expected: V1, V2, V3, V4, V5 (one per line)

# 2. shadow_mode flag set to true
grep "shadow_mode:" config/strategies/futures/rl_mppo.yaml
# Expected: shadow_mode: true

# 3. Setup A/C strategy.enabled true (paper-only since futures_live.enabled=false)
grep -A 1 "^strategy:" config/strategies/futures/setup_a_gap_reversion.yaml | grep enabled
grep -A 1 "^strategy:" config/strategies/futures/setup_c_event_reaction.yaml | grep enabled
# Expected: enabled: true (both)

# 4. futures_live.enabled remains false (paper mode)
grep "^enabled:" config/futures_live.yaml
# Expected: enabled: false

# 5. Crontab has both Phase 2 entries
crontab -l | grep -E "counterfactual_weekly|phase2_daily_verification"
# Expected:
#   0 7 * * 1 .../counterfactual_weekly.sh
#   0 16 * * 1-5 .../phase2_daily_verification.sh
```

If any of these is wrong, **STOP** and consult `docs/plans/2026-05-03-llm-primary-rl-minimization.md`
or `git log` for the relevant PR before restarting the orchestrator.

## Day-of (Mon 08:55 KST)

The orchestrator restart is handled by `scripts/cron/rl_paper.sh start`
(triggered by the existing `2-37/5 9-15 * * 1-5` watchdog cron).  No manual
intervention is required.  But the operator should verify:

1. **Process lifecycle** — by 09:05 KST:
   ```bash
   pgrep -af "sts rl paper" | head -3
   # Expected: one PID with process up < 10 min
   ```

2. **Shadow logger flush task started** — check log for the line:
   ```bash
   grep "shadow_loggers flush loop started" logs/rl_paper_$(date +%Y%m%d).log
   # Expected: ONE line with "interval=60.0s"
   ```

3. **No tz-aware errors** (regression guard for PR #161/#162):
   ```bash
   grep -cE "offset-naive|offset-aware|TypeError" logs/rl_paper_$(date +%Y%m%d).log
   # Expected: 0
   ```

4. **First RL shadow row written by 09:30 KST**:
   ```bash
   clickhouse-client --user "${CLICKHOUSE_USER:-default}" --password "$CLICKHOUSE_PASSWORD" -q \
     "SELECT count() FROM kospi.rl_shadow_predictions WHERE ts >= today()"
   # Expected: > 0 by 09:30
   ```

5. **First Setup A signal logged by 12:00 KST** (Setup A fires on the
   first morning gap):
   ```bash
   clickhouse-client --user "${CLICKHOUSE_USER:-default}" --password "$CLICKHOUSE_PASSWORD" -q \
     "SELECT count() FROM kospi.signals_all WHERE setup_type='A' AND generated_at >= today()"
   # Expected: >= 1 by 12:00
   ```

If steps 4 or 5 fail, see § "Troubleshooting" below.

## Day-of (Mon 16:00 KST)

The daily-verification cron fires automatically and posts a Telegram digest
to the briefing channel:

- ✅ ALL PASS — proceed to normal weekday cadence.
- ❌ FAIL — at least one of the four critical gates failed.  Read the
  per-gate `actual` vs `expected` lines in the Telegram message and
  open `reports/daily_verification/$(date +%Y-%m-%d).json` for the full
  payload.  Common patterns:

| Failed gate | Likely cause | Action |
|-------------|--------------|--------|
| `rl_shadow_predictions_today=0` | RL inference loop dead, or process never restarted | Check `pgrep`; restart `scripts/cron/rl_paper.sh start` |
| `rl_trades_today_is_zero ≠ 0` | `shadow_mode: false` accidentally deployed | Revert `config/strategies/futures/rl_mppo.yaml` to `shadow_mode: true` and restart |
| `setup_a_signals_today < 1` | Setup A adapter not registered, or `strategy.enabled: false` | `grep enabled config/strategies/futures/setup_a_gap_reversion.yaml`; restart if config OK |
| `shadow_logger_dropped_batches > 0` | ClickHouse insert failure | Check `kospi.rl_shadow_predictions` write path; may need V5 schema verify |

## Day-of (Mon 16:30 KST) — manual cross-checks (only first day)

After the daily-verification Telegram, manually inspect:

1. **Daily verification report**:
   `reports/daily_verification/$(date +%Y-%m-%d).json` should show non-zero
   Setup A/C and RL shadow logger activity for today.

2. **Prometheus alerts** — confirm none of the 4 shadow-loggers alerts fired
   (browser → http://localhost:9090/alerts → all should be `inactive`):
   - `ShadowLoggerBatchesDropped`
   - `ShadowLoggerFlushStale`
   - `ShadowLoggerBufferFillingUp`
   - `ShadowLoggerBufferNearOverflow`

3. **Counterfactual archive** — the 2026-05-08 dry-run is in
   `reports/counterfactual/2026-W19.json`; the **first real** weekly archive
   from Phase 2 data appears 2026-05-18 (next Mon) covering 2026-05-11 –
   2026-05-17.

## Subsequent days (Tue–Fri week 1)

No manual checks required.  Trust the automation:

- **Telegram daily 16:00 KST** PASS report = green-light next day.
- **React Dashboard + Prometheus alerts** daily spot-check as needed.
- **Telegram weekly 07:00 KST Mon** = first counterfactual report on
  2026-05-18 covering Mon–Fri week 1.

If you see ANY ❌ FAIL Telegram or any Prometheus alert (warning or critical):

1. Open the daily-verification JSON: `reports/daily_verification/$(date +%Y-%m-%d).json`.
2. Check Prometheus directly: `curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts'`.
3. Use the failure-modes table in this runbook + `futures-paradigm-failure-modes.md`.
4. **Escalation**: if a critical alert remains active for > 1h during market hours,
   stop accepting new orders via the live-mode guard:
   ```bash
   redis-cli -n 1 set futures:live:suspended 1
   ```
   This sets the kill-switch sentinel; subsequent signals are XACK-skipped.

## Troubleshooting

### "First RL shadow row never appeared" (step 4 of Day-of)

Sequence to investigate:

```bash
# Did the process restart at all today?
pgrep -af "sts rl paper" | xargs ps -o pid,etime,command

# Is the shadow logger task wired?
grep "shadow_loggers flush loop" logs/rl_paper_$(date +%Y%m%d).log | head -3

# Did flush attempt? Look for INFO lines
grep "shadow_loggers flush" logs/rl_paper_$(date +%Y%m%d).log | tail -10

# Is RLMPPOEntry actually in shadow_mode?
python3 -c "
from shared.config.loader import ConfigLoader
cfg = ConfigLoader.load_strategy('futures', 'rl_mppo')
print('shadow_mode:', cfg['strategy']['entry']['params'].get('shadow_mode'))
"
# Expected: True
```

If everything looks right but rows are still zero, manually verify the V5 table:

```bash
clickhouse-client --user "${CLICKHOUSE_USER:-default}" --password "$CLICKHOUSE_PASSWORD" -q \
  "DESCRIBE kospi.rl_shadow_predictions"
# Expected: 10 columns including ts, symbol, action, action_probs, ...
```

### "Setup A signal never generated" (step 5 of Day-of)

```bash
# Confirm adapter registration
python3 -c "
from shared.strategy.registry import EntryRegistry, register_builtin_components
register_builtin_components()
names = list(EntryRegistry.list_all())
print('setup_a_gap_reversion:', 'setup_a_gap_reversion' in names)
print('setup_c_event_reaction:', 'setup_c_event_reaction' in names)
"
# Expected: True, True

# Confirm config gates
yq '.strategy.enabled' config/strategies/futures/setup_a_gap_reversion.yaml
yq '.strategy.enabled' config/strategies/futures/setup_c_event_reaction.yaml
# Expected: true, true
```

If both checks pass but signals never come, the morning gap may simply not
have triggered Setup A's threshold — this is normal.  Setup A signals are
**not guaranteed** every day; the daily target is `>= 1` because operator §7
agreed Setup A *should* fire on most opening gaps but plain market days
without a gap will produce zero signals.  Wait until end-of-week (5 days)
before declaring this a real failure.

## Rollback

If Phase 2 must be reverted to pre-Phase-2 (`rl_mppo` primary):

1. Set `shadow_mode: false` in `config/strategies/futures/rl_mppo.yaml`.
2. Set `strategy.enabled: false` in both Setup A and Setup C configs.
3. Restart orchestrator: `scripts/cron/rl_paper.sh start`.
4. The cron entries for counterfactual_weekly and phase2_daily_verification
   can stay — they will simply report empty windows until Phase 2 is
   re-enabled, no harm done.

If a more aggressive rollback is needed (revert plan to pre-Phase-2 entirely),
follow `docs/runbooks/futures-paradigm-rollback.md`.

## End-of-week 1 review (2026-05-15 Fri after 16:00 KST)

The operator should confirm before week 2 begins:

- 5 daily-verification reports stored in `reports/daily_verification/2026-05-1{1..5}.json`.
- All five reports show `all_passed: true` (or have explainable single-day failures).
- Cumulative counters in week-1 reports:
  - Setup A executed: target ≥ 1/day average → ≥ 5 by EOW.
  - RL shadow predictions: target ≥ 200/day average → ≥ 1000 by EOW (matches Phase 4 gate).
- Telegram weekly report appears at 07:00 KST Mon 2026-05-18 covering the full week.

If all cumulative targets met and zero ❌ FAILs, Phase 2 is operationally stable
and Phase 3 Track A (operator gates — see plan §10.1) can be scheduled.
