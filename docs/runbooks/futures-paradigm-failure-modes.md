# Futures Paradigm — Phase 4 Failure Modes

Spec §9 deliverable. Each entry is a known failure surface, the symptom an
operator sees, and the recovery path.

---

## 1. ClickHouse outage during fill logging

**Symptom**: `kis-order-router` and `kis-news-scorer` logs show
`signals_all flush failed; N rows pending redelivery` or
`order_fills flush failed`. `journalctl -u kis-order-router | grep CH`
shows repeated re-tries.

**Cause**: ClickHouse native port 9000 unreachable, or query fails (eg.
schema drift after a manual ALTER).

**Impact**: The `FillLogger` and `SignalsAllWriter` re-raise on failure
(Phase 2 invariant from PR #126). Consumer-group XACK is skipped, so the
source signal is left pending. On CH recovery the message is redelivered
and the row eventually lands. **Note**: rows already drained from the
in-memory buffer at the moment of the failed `execute()` are lost
(documented trade-off — duplicate-fill prevention takes precedence over
audit completeness).

**Recovery**:
1. `systemctl status clickhouse` — confirm CH is back
2. `clickhouse-client --query "SELECT 1"`
3. The router daemon will pick up its pending list automatically.
4. If the buffered rows mattered, replay from the upstream Redis stream
   via `redis-cli -n 1 XRANGE stream:signal.final - + COUNT 1000`.

---

## 2. KIS WebSocket disconnect during passive fill wait

**Symptom**: `passive_maker raised signal_id=X; leaving pending` in
order_router logs. Open position on the exchange but no `kospi.order_fills`
row.

**Cause**: KIS WebSocket dropped between `place_futures_order` and the
fill confirmation. The order is still live on the exchange.

**Impact**: PR #134 review note flagged this as a non-idempotency bug —
on retry, `PassiveMaker.place_passive_limit_futures` would place a SECOND
order. Mitigation deferred to Tasks 16-17 wiring; for now, follow recovery.

**Recovery**:
1. Check KIS web/app for live orders matching the signal_id timestamp
2. Cancel the orphan order manually if redelivery hasn't already done so
3. `redis-cli -n 1 XACK stream:signal.final order_router <message-id>`
   to prevent retry. (Use this judiciously — only after confirming the
   exchange state.)

---

## 3. Kill switch trips

**Symptom**: Telegram alert "KILL SWITCH TRIPPED: <reason>". `kis-kill-switch`
service inactive; sentinel file at `/var/run/kis_kill_switch.tripped`.

**Cause**: One of 6 conditions in `config/kill_switch.yaml` exceeded:
daily_loss / weekly_loss / consecutive_losses / api_error_rate /
news_pipeline_lag / clickhouse_insert_fail_rate.

**Impact**: `kis-order-router` refuses to consume new messages on next
loop iteration (sentinel check). Pre-trip messages already in
`stream:signal.final` will sit unACKed until the sentinel is cleared.

**Recovery** — REQUIRES OPERATOR APPROVAL:
1. `journalctl -u kis-kill-switch -n 200` — confirm reason + details
2. Review PnL state: `redis-cli -n 1 HGETALL risk:state:futures`
3. Manually flatten any open positions if `force_close_callback` failed
   (check `kospi.order_fills WHERE trade_role='force_close' AND filled_at >= NOW() - INTERVAL 1 HOUR`)
4. `scripts/kill_switch_clear.sh` (operator-only — removes the sentinel)
5. `sudo systemctl start kis-kill-switch kis-order-router`
6. Document the trip in the incident log

---

## 4. Decision engine context provider stalls

**Symptom**: `redis-cli -n 1 XLEN stream:signal.candidate` is flat;
`risk_filter` and `order_router` idle.

**Cause**: The `LiveMarketContextBuilder` (Task 17 wiring) cannot fetch
fresh bars — KIS REST 5xx, ClickHouse warmup query failing, etc. The
daemon's `context_provider() returns None` no-op path keeps it alive but
silent.

**Recovery**:
1. `journalctl -u kis-decision-engine -n 100` — look for context_provider
   exception traces
2. `clickhouse-client --query "SELECT max(ts) FROM kospi.kospi200f_1m"` —
   verify the warmup path has data
3. `redis-cli -n 1 GET system:trade_targets:latest` — verify upstream
   universe data fresh (if the live builder reads it)
4. Restart the daemon: `sudo systemctl restart kis-decision-engine`

---

## 5. PseudoOCO bracket leaks

**Symptom**: `PseudoOCO.active_handles` growing unboundedly during paper
operation. Memory creep on `kis-order-router` over hours/days.

**Cause**: Brackets are registered on entry fill but never fired (no
`on_tick` calls — the live price feed wiring is in Tasks 16-17) or
`check_expiry` not running.

**Recovery**:
1. Restart the daemon to drop the in-memory state. **Note**: this loses
   bracket references. Reconcile open positions with KIS web/app.
2. Until the live price-feed loop is wired, use shorter `signal.valid_until`
   windows (config in Setup configs) so brackets self-expire faster.

---

## 6. Redis stream backlog

**Symptom**: `redis-cli -n 1 XLEN stream:signal.candidate` > 10000;
`xpending stream:signal.candidate risk_filter` shows large pending count.

**Cause**: `risk_filter` daemon crashed or stalled; backlog accumulating
from `decision_engine`.

**Recovery**:
1. `systemctl status kis-risk-filter` — restart if crashed
2. If the backlog is too large to drain reasonably (e.g. days of stale
   signals), `XTRIM stream:signal.candidate MAXLEN 100` and document the
   data loss. Stale signals would not fire trades anyway because Setup
   A/C have validity windows.

---

## 7. Migration drift

**Symptom**: `INSERT INTO kospi.order_fills` fails with
`Cannot read all data` or column-type mismatch.

**Cause**: V3 migration partially applied or schema manually altered.

**Recovery**:
1. `clickhouse-client --query "SELECT * FROM kospi.schema_migrations"` —
   confirm V1, V2, V3 all applied
2. `DESC kospi.order_fills` — compare against
   `infra/clickhouse/migrations/V3__create_order_fills.sql`
3. If schema differs, `DROP TABLE kospi.order_fills` (after backup) and
   re-run `python scripts/migrations/apply_clickhouse_migrations.py`. The
   migration runner uses `IF NOT EXISTS` so re-running is safe once V3 is
   removed from the tracking table.

---

## 8. Telegram bot down / rate-limited

**Symptom**: Kill switch trips but no Telegram alert; weekly edge review
runs but no message.

**Cause**: HTTP 429 on the Telegram bot, or the bot token revoked.

**Impact**: Operational blindness, but no trading impact. The kill switch
still trips and writes the sentinel; the daemon still exits cleanly.

**Recovery**:
1. Re-check `TELEGRAM_FUTURES_BOT_TOKEN` / `TELEGRAM_FUTURES_CHAT_ID` in
   `.env`.
2. If the bot is rate-limited, wait for the cooldown window (typically
   60s); kill-switch path logs the failure but does not retry.

---

## 9. Sentinel file orphaned by stale process

**Symptom**: `kis-order-router` refuses to start after a normal restart.
`/var/run/kis_kill_switch.tripped` exists with old reason.

**Cause**: Previous kill switch trip wasn't cleared.

**Recovery**: Operator review + `scripts/kill_switch_clear.sh` (see #3).

---

## 10. KOSPI200 mini front-month rollover

**Symptom**: Around 2nd Thursday of each month, signals reference an
expired contract code (e.g. A05603 after the March 2026 expiry).

**Cause**: The contract spec resolver doesn't auto-update; `decision_engine`
keeps using the previous month's symbol.

**Recovery**: Phase 4 daemons inherit symbol selection from the
`TradingOrchestrator` rollover convention (CLAUDE.md §RL Symbol Policy:
"sts rl paper" path). Restart the daemons after expiry (cron-driven daily
restart pattern from Phase 1/2 already covers this).
