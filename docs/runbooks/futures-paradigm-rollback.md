# Futures Paradigm — Rollback Runbook

Manual rollback procedure for Phase 5 futures paradigm. Mirrors spec
`docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md` §6.2 step-for-step,
formatted as an executable checklist with command blocks.

## When to roll back

- Gate 3 monitoring shows MDD breach, runaway slippage, or kill-switch trip with non-trivial cause
- Anomalous behaviour the operator cannot diagnose within ~10 minutes
- Any time the operator concludes the new pipeline is doing something it shouldn't

When in doubt, **roll back**. The cost of an unnecessary rollback (one
session of paper-only trading) is ~negligible compared to a session of
live trading under unknown failure mode.

## Step-by-step

### 1. Flatten every open futures position via market

```bash
# Dry-run first to confirm the position list looks right
python -m scripts.trading.flatten_all

# Then issue the actual close orders
python -m scripts.trading.flatten_all --confirm --reason "<incident-id>"
```

- [ ] CONFIRMED summary printed; FAILED count = 0
- [ ] `clickhouse-client --query "SELECT count() FROM kospi.swing_positions WHERE asset_class='futures' AND status='open'"` returns 0

### 2. Stop all new-system systemd units

```bash
sudo systemctl stop kis-news-collector kis-news-scorer \
                    kis-decision-engine kis-risk-filter \
                    kis-order-router kis-kill-switch
```

- [ ] `systemctl is-active <unit>` = `inactive` for all 6

### 3. Disable Decision Engine in config (defence-in-depth against systemd auto-restart)

Edit `config/decision_engine.yaml` → `enabled: false`. Commit so it sticks.

- [ ] `grep "^enabled:" config/decision_engine.yaml` → `enabled: false`

### 4. Verify standard orchestrators continue running

```bash
systemctl is-active kis-futures-trading kis-stock-trading
ps aux | grep -E "sts trade start|services.trading" | grep -v grep
```

- [ ] Phase 4/5 stack stopped; standard stock/futures trading path remains available

### 5. Collect logs (incident bundle)

```bash
TS=$(date +%Y%m%d_%H%M%S)
mkdir -p reports/incidents/$TS
cd reports/incidents/$TS

# systemd logs
journalctl -u kis-decision-engine -u kis-risk-filter \
           -u kis-order-router -u kis-kill-switch \
           --since "2 hours ago" > systemd.log

# ClickHouse: most-recent fills + signals
clickhouse-client --query \
  "SELECT * FROM kospi.order_fills WHERE filled_at >= now() - INTERVAL 4 HOUR FORMAT JSONEachRow" \
  > order_fills.jsonl
clickhouse-client --query \
  "SELECT * FROM kospi.rl_signals WHERE generated_at >= now() - INTERVAL 4 HOUR FORMAT JSONEachRow" \
  > rl_signals.jsonl

# Redis stream snapshots
redis-cli -n 1 XLEN stream:signal.candidate stream:signal.scored stream:signal.final \
  > redis_lengths.txt
```

- [ ] Bundle directory present at `reports/incidents/<timestamp>/`
- [ ] Bundle committed (or sent to operator's incident channel)

### 6. 24-hour cooldown — no resumption without RCA

- [ ] No restart attempt within 24 hours of trip
- [ ] Root-cause identified, fix authored as PR, fix merged
- [ ] Telegram briefing posted to incident channel summarizing cause + fix

### 7. Resume — paper-only re-validation

Before turning the live order_router back on:

- [ ] Run for **at least 3 days in paper mode** (Phase 4 paper account)
- [ ] Weekly Edge Review covering the 3-day window shows no `pause`/`retune` actions
- [ ] Operator sign-off (written ack) before flipping `futures_live.enabled: true`

```bash
# Re-enable systemd units AFTER RCA + paper re-validation
sudo systemctl start kis-decision-engine kis-risk-filter kis-order-router kis-kill-switch
sudo systemctl start kis-news-collector kis-news-scorer
# Re-enable in config
sed -i 's/^enabled: false$/enabled: true/' config/decision_engine.yaml
# Lift live-mode pause when ready
redis-cli -n 1 del futures:live:suspended
```

## Drill cadence — TWICE A YEAR

Per spec §6.3: weekend rollback drill on a non-trading Saturday.

- [ ] Quarterly calendar reminder set (operations runbook)
- [ ] Drill output saved to `reports/drills/rollback_YYYYMMDD.txt` with step durations
- [ ] Any step taking > 2× expected time → investigate before next live cycle

See `scripts/drills/rollback_drill.sh` (Phase 5 Task 8) for the
automated dry-run drill.

## Notes

- **kill_switch sentinel ≠ rollback**. The kill_switch trip is a
  *partial* halt: it prevents new orders but does not flatten positions
  on its own. Step 1 (flatten) is mandatory regardless.
- **Don't `--no-verify` past pre-commit hooks** when committing config
  rollback edits — pre-commit catches accidental syntax breakage that
  would silently revive the disabled service on next reload.

Spec: `docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md` §6.2.
