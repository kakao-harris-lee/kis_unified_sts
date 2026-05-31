# Market-Open Pipeline Verification Runbook

End-to-end verification of the **WebSocket → strategy → aggregation/reporting**
pipeline with **LIVE market data**, run on the **next trading day**.

This is the verification that **cannot be done on a holiday** — there is no live
tick flow when the market is closed. It exists to answer three operator concerns
after the feed-observability work landed on branch
`feat/pipeline-observability-gaps`:

1. **Concern 1** — Stock **and** futures data actually arrive over WebSocket (live).
2. **Concern 2** — Stock and futures strategies run **in parallel** without a
   bottleneck (separate OS processes, within-asset concurrency, p99 well under
   the 60s 1-minute-bar budget).
3. **Concern 3** — Strategy results are correctly **aggregated / processed /
   reported** across all three channels (Dashboard, Telegram, Prometheus).

Run the sections **in order**. Each has a fenced, copy-pasteable command block
and an *Expected* note. Tick every `- [ ]` box. If any box fails, jump to the
**Failure triage** table before continuing.

> Korean market hours: **09:00–15:30 KST = 00:00–06:30 UTC**.
> The operations crontab declares `CRON_TZ=Asia/Seoul`, so all cron times are KST.
> Stock trading cron: start `55 8 * * 1-5` (08:55 KST), stop `0 16 * * 1-5`.
> Pre-market ClickHouse warmup runs **before 09:00**.
> Futures trading is started by `scripts/cron/futures_trading.sh start` (08:55 KST,
> Setup A/C + `bb_reversion_15m`) — same wrapper pattern as stock. The Phase-5
> systemd paradigm (decision_engine / risk_filter / order_router / kill_switch) is
> a separate path; see `futures-paradigm-operations.md`.

---

## Conventions used below

| Token | Meaning |
|-------|---------|
| `:5080` | Caddy front door (dashboard API + `/ws`) |
| `:8001` | Dashboard container, direct (bypasses Caddy) |
| `:9090` | Prometheus (host) |
| `redis-cli -n 1` | Redis **DB 1 only** (DB 0 belongs to another project) |
| `clickhouse-client` | ClickHouse native, port **9000** |
| `$TELEGRAM_*` | env-provided Telegram credentials (`TELEGRAM_{STOCK,FUTURES,BRIEFING}_*`) |

Replace `localhost` with the actual host if you run these from a workstation.

---

## 0. Prerequisites (any time before 08:55 KST)

- [ ] **Today is a trading day.** Confirm against the holiday cache — if today is
      a holiday there is no live data and this runbook does not apply:
      ```bash
      clickhouse-client --query \
        "SELECT today() AS d,
                toDayOfWeek(today()) AS dow  -- 6=Sat,7=Sun => non-trading"
      # Cross-check the in-process holiday cache (services/trading/holiday_cache.py)
      # via the dashboard freshness endpoint, which 200s only on trading days.
      ```
- [ ] **`.env` credentials present** for both assets:
      `KIS_STOCK_APP_KEY/SECRET/ACCOUNT_NO`, `KIS_FUTURES_APP_KEY/SECRET/ACCOUNT_NO`,
      and `KIS_STOCK_MARKET` / `KIS_FUTURES_MARKET` set as intended (`real`/`mock`).
- [ ] **Stack is up on :5080.** See §1.

---

## 1. T-1 pre-open (before 08:55 KST)

### 1.1 Stack health

- [ ] Containers up:
      ```bash
      docker compose ps
      ```
      *Expected*: dashboard, caddy, redis, clickhouse, prometheus all `Up`.

- [ ] Caddy front door answers:
      ```bash
      curl -fsS http://localhost:5080/ -o /dev/null -w 'caddy_root=%{http_code}\n'
      ```
      *Expected*: `caddy_root=200`.

- [ ] Dashboard direct health (bypassing Caddy, to isolate Caddy vs app):
      ```bash
      curl -fsS http://localhost:8001/health -w '\n' || \
      curl -fsS http://localhost:8001/ -o /dev/null -w 'dash_root=%{http_code}\n'
      ```
      *Expected*: 200 / healthy JSON.

### 1.2 Infra reachable

- [ ] Redis DB 1:
      ```bash
      redis-cli -n 1 ping
      ```
      *Expected*: `PONG`.

- [ ] ClickHouse native (9000):
      ```bash
      clickhouse-client --query "SELECT 1"
      ```
      *Expected*: `1`.

### 1.3 Warmup data present (so 09:00 indicator warmup does not miss)

Warmup reads **stock `market.minute_candles`** and **futures `kospi.kospi_mini_1m`**.
Confirm yesterday's bars exist so warmup returns ≥ `warmup_min_candles` (20):

- [ ] Stock warmup source has recent bars:
      ```bash
      clickhouse-client --query "
        SELECT count() AS bars, max(timestamp) AS last_bar
        FROM market.minute_candles
        WHERE timestamp >= today() - 1"
      ```
      *Expected*: `bars` >> 20 across the watchlist; `last_bar` is yesterday's
      session (or today's pre-market warmup load).

- [ ] Futures warmup source (connected futures continuous, plus the live
      near-month) has recent bars:
      ```bash
      clickhouse-client --query "
        SELECT count() AS bars, max(timestamp) AS last_bar
        FROM kospi.kospi_mini_1m
        WHERE timestamp >= today() - 1"
      ```
      *Expected*: `bars` >> 20; `last_bar` is yesterday's session.

- [ ] If either is thin/empty, **backfill before open** and re-check:
      ```bash
      sts backfill today          # futures + index minute backfill
      sts stock-backfill run      # stock minute backfill
      ```

---

## 2. Concern 1 — WebSocket live data, BOTH assets (after 09:00 KST)

Goal: prove **stock** ticks (`H0STCNT0`) **and** **futures** ticks
(`H0IFCNT0` + orderbook `H0IFASP0`) are actually arriving over WebSocket.

### 2.1 Both orchestrator processes are running

Each asset is a **separate OS process** (`sts trade start --asset stock|futures`),
its own event loop and GIL. The stock process is launched by the cron wrapper:

```bash
# Stock (cron-managed):
bash scripts/cron/stock_trading.sh start     # idempotent; safe if already running
# Futures (cron-managed, separate process):
bash scripts/cron/futures_trading.sh start   # idempotent; safe if already running
```

- [ ] Both processes exist with **distinct PIDs**:
      ```bash
      ps -ef | grep -i "[s]ts trade"
      pgrep -af "asset stock"
      pgrep -af "asset futures"
      ```
      *Expected*: at least one PID for `asset stock` and a different PID for
      `asset futures`. Two distinct PIDs = process-level parallelism (Concern 2
      foundation).

### 2.2 Feed health — first tick, no drops, not stale

Both feeds expose `get_health_status()`; the orchestrator surfaces the rolled-up
counters via `get_status()` and logs WARNINGs on new drops / staleness.

- [ ] **Logs show first tick and no drop/stale warnings** for each asset:
      ```bash
      # Stock orchestrator logs (KISStockPriceFeed):
      journalctl -u kis-trade-stock -f --since "09:00 today" 2>/dev/null || \
        tail -f logs/trade-stock.log
      # Look for: feed connected, first tick received, NO "feed drops" / "stale" WARNING

      # Futures orchestrator logs (KISWebSocketAdapter):
      journalctl -u kis-trade-futures -f --since "09:00 today" 2>/dev/null || \
        tail -f logs/trade-futures.log
      ```
      *Expected*: each feed logs connection + first tick within ~10s of 09:00;
      **no** `feed drops` or `staleness > stale_warn_threshold_seconds` (60s)
      WARNING lines.

  Feed health keys to recognise in the logs:
  - **Stock** (`shared/kis/stock_feed.py`): `running`, `dropped_count`, ...
  - **Futures** (`shared/kis/websocket.py` adapter): `connected`,
    `messages_received`, `messages_dropped`, `parse_errors`, `queue_depth`,
    `last_message_age_s`.

### 2.3 Ticks are landing (Redis updating)

- [ ] Redis system/state keys advance for both assets (run twice ~10s apart;
      values/timestamps must change):
      ```bash
      redis-cli -n 1 --scan --pattern 'system:stock:*'
      redis-cli -n 1 --scan --pattern 'system:futures:*'
      # Spot-check a couple of values across two reads:
      redis-cli -n 1 get system:stock:last_tick_ts 2>/dev/null
      redis-cli -n 1 get system:futures:last_tick_ts 2>/dev/null
      ```
      *Expected*: timestamps move forward between the two reads.

### 2.4 Data freshness endpoint (per asset)

- [ ] Dashboard freshness is fresh for **both** assets:
      ```bash
      curl -fsS "http://localhost:5080/api/health/data-freshness?asset_class=stock"   | jq .
      curl -fsS "http://localhost:5080/api/health/data-freshness?asset_class=futures" | jq .
      ```
      *Expected*: each reports a small age (seconds), not stale.

### 2.5 Prometheus staleness gauges low

- [ ] Both staleness series are low (well under the 60s warn threshold). The
      Prometheus gauge is `trading_websocket_staleness_seconds` with a `feed`
      label (`stock` / `futures`):
      ```bash
      curl -fsS http://localhost:9090/api/v1/query \
        --data-urlencode 'query=trading_websocket_staleness_seconds' \
        | jq '.data.result[] | {feed: .metric.feed, value: .value[1]}'
      ```
      *Expected*: both `feed="stock"` and `feed="futures"` present and small
      (single-digit to low-tens of seconds during active trading). The same
      values appear in the dashboard health JSON as
      `websocket_staleness_seconds.{stock,futures}`.

**Concern 1 PASS criteria**: distinct stock + futures PIDs; both feeds logged
first tick with no drop/stale warnings; Redis advancing for both; both freshness
endpoints fresh; both staleness gauges < 60s.

---

## 3. Concern 2 — Parallel, no bottleneck

Goal: prove the two assets run concurrently and that each asset's signal cycle
finishes **well under** the 60s 1-minute-bar budget (p99 < 60s).

### 3.1 Process-level parallelism (already confirmed in §2.1)

- [ ] Stock and futures run as **separate processes** (distinct PIDs from §2.1).
      Separate event loop + separate GIL → true cross-asset parallelism; one
      asset cannot block the other.

### 3.2 60s "Signal cycle" summary per asset

`strategy_manager.py` logs a throttled **"Signal cycle"** summary every 60s.

- [ ] Each asset emits a Signal-cycle line roughly once per minute, with a cycle
      duration far below 60s:
      ```bash
      # Stock:
      journalctl -u kis-trade-stock --since "09:00 today" 2>/dev/null \
        | grep -i "signal cycle" | tail -5
      # Futures:
      journalctl -u kis-trade-futures --since "09:00 today" 2>/dev/null \
        | grep -i "signal cycle" | tail -5
      ```
      *Expected*: a line ~every 60s for each asset; reported cycle/elapsed time
      comfortably under the 60s bar budget (target p99 < 60s).

### 3.3 Market-data fetch diagnostics latency

The market-data loop logs fetch diagnostics every ~30 ticks.

- [ ] Fetch latency is small (sub-second to a few seconds), nowhere near 60s:
      ```bash
      journalctl -u kis-trade-stock --since "09:00 today" 2>/dev/null \
        | grep -iE "fetch|market.?data" | tail -5
      journalctl -u kis-trade-futures --since "09:00 today" 2>/dev/null \
        | grep -iE "fetch|market.?data" | tail -5
      ```
      *Expected*: fetch diagnostics show low latency; no growth/backlog trend.

### 3.4 No queue backpressure (drops stay at 0)

- [ ] `trading_feed_drops_total` is **0** for both feeds (rising drops = the
      internal queue is filling faster than it drains = backpressure bottleneck):
      ```bash
      curl -fsS http://localhost:9090/api/v1/query \
        --data-urlencode 'query=trading_feed_drops_total' | jq '.data.result'
      ```
      *Expected*: every `{feed=...}` series reads `0` (or flat, not climbing).

### 3.5 Warmup misses are 0

- [ ] `trading_warmup_misses_total` is **0** (a miss means warmup returned fewer
      than `warmup_min_candles` (20) bars for a symbol → indicator cold-start):
      ```bash
      curl -fsS http://localhost:9090/api/v1/query \
        --data-urlencode 'query=trading_warmup_misses_total' | jq '.data.result'
      ```
      *Expected*: `0`. If > 0, see triage (backfill the warmup source).

### 3.6 Within-asset concurrency (note, not a separate command)

- [ ] Within each asset, strategies run via `asyncio.gather`
      (`parallel_entries` / `parallel_exits` default `true`), and the indicator
      cache is **shared per-symbol** (no N× recompute across strategies). The
      sub-60s Signal-cycle times in §3.2 are the live evidence of this.

**Concern 2 PASS criteria**: distinct PIDs; each asset's Signal cycle < 60s
(p99 budget); fetch latency low and flat; `trading_feed_drops_total` == 0;
`trading_warmup_misses_total` == 0.

---

## 4. Concern 3 — Aggregation / processing / reporting

Goal: trace one signal through the whole reporting chain, and confirm stock vs
futures stay **separated** end-to-end. Wait until at least one signal has fired
(stock signals typically appear within the first ~hour; futures per setup).

### 4.1 Signal → Dashboard `/api/signals`

- [ ] Signals show on the dashboard per asset:
      ```bash
      curl -fsS "http://localhost:5080/api/signals?asset_class=stock"   | jq '.[0:3]'
      curl -fsS "http://localhost:5080/api/signals?asset_class=futures" | jq '.[0:3]'
      ```
      *Expected*: recent signals listed (or an empty list with HTTP 200 if no
      signal has fired yet — a 200 is still a pass for plumbing).

- [ ] Same signals present in Redis (DB 1), per asset:
      ```bash
      redis-cli -n 1 lrange trading:stock:signals 0 4
      redis-cli -n 1 lrange trading:futures:signals 0 4
      ```

### 4.2 Position → `/api/trading/positions` + Redis hash

- [ ] Open positions report per asset, and match Redis:
      ```bash
      curl -fsS "http://localhost:5080/api/trading/positions?asset_class=stock"   | jq .
      curl -fsS "http://localhost:5080/api/trading/positions?asset_class=futures" | jq .
      redis-cli -n 1 hgetall trading:stock:positions
      redis-cli -n 1 hgetall trading:futures:positions
      ```
      *Expected*: the dashboard position set equals the Redis hash for each asset.

### 4.3 Status endpoint surfaces the new feed stats

- [ ] `get_status()` stats (now including `feed_drops` and `warmup_misses`) are
      exposed per asset:
      ```bash
      curl -fsS "http://localhost:5080/api/trading/status?asset_class=stock"   | jq .
      curl -fsS "http://localhost:5080/api/trading/status?asset_class=futures" | jq .
      ```
      *Expected*: each returns running state plus `feed_drops: 0` and
      `warmup_misses: 0`.

### 4.4 On close → trade persisted in ClickHouse + `/api/trades`

Stock closed trades land in **`market.stock_trades`**; futures land in
**`kospi.rl_trades`** (has an `asset_class` column).

- [ ] Today's closed trades persist per asset:
      ```bash
      clickhouse-client --query "
        SELECT count() AS n, max(toDateTime(*)) AS last_ts
        FROM market.stock_trades
        WHERE toDate(timestamp) = today()" 2>/dev/null

      clickhouse-client --query "
        SELECT asset_class, count() AS n
        FROM kospi.rl_trades
        WHERE toDate(timestamp) = today()
        GROUP BY asset_class"
      ```
      *Expected*: counts grow as positions close; futures rows carry
      `asset_class='futures'`.

- [ ] Same trades visible on the dashboard per asset:
      ```bash
      curl -fsS "http://localhost:5080/api/trades?asset_class=stock"   | jq '.[0:3]'
      curl -fsS "http://localhost:5080/api/trades?asset_class=futures" | jq '.[0:3]'
      ```

### 4.5 Telegram alert in the correct channel

- [ ] When a stock signal/fill fires, the alert lands in the **STOCK** channel;
      futures alerts land in the **FUTURES** channel; daily briefing in
      **BRIEFING**. (3 channels: `TELEGRAM_{STOCK,FUTURES,BRIEFING}_*`.)
      *Expected*: no cross-channel leakage (stock event must not appear in the
      futures channel and vice-versa).

### 4.6 Prometheus per-asset metrics

- [ ] Per-asset trade/PnL metrics tick over with the asset label:
      ```bash
      curl -fsS http://localhost:9090/api/v1/query \
        --data-urlencode 'query={__name__=~"trading_.*",asset=~"stock|futures"}' \
        | jq '.data.result[] | {metric: .metric, value: .value[1]}'
      ```
      *Expected*: both `asset="stock"` and `asset="futures"` series present.

### 4.7 Live push over `/ws` (routed through Caddy after PR #380)

- [ ] The dashboard WebSocket pushes live updates **through Caddy**:
      ```bash
      # Quick handshake probe (expects HTTP 101 Switching Protocols):
      curl -fsS -i -N \
        -H "Connection: Upgrade" -H "Upgrade: websocket" \
        -H "Sec-WebSocket-Version: 13" \
        -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
        "http://localhost:5080/ws" | head -1
      ```
      *Expected*: `HTTP/1.1 101 Switching Protocols`. If this times out, Caddy
      likely was not reloaded after PR #380 (see triage).

**Concern 3 PASS criteria**: signal visible on `/api/signals` + Redis;
position consistent across `/api/trading/positions` + Redis hash; closed trade in
`stock_trades`/`rl_trades` + `/api/trades`; correct Telegram channel; per-asset
Prometheus series; `/ws` upgrades through :5080; stock and futures remain
separated (distinct Redis keys, `asset_class` tag, dashboard asset tabs).

---

## 5. Failure triage

| Symptom | Where to look | Likely cause / action |
|---------|---------------|------------------------|
| `feed drops` WARNING in logs / `trading_feed_drops_total` climbing | Orchestrator logs; Prometheus | **Queue backpressure** — consumer slower than producer. Check `queue_depth`/`last_message_age_s` in futures health; CPU; downstream stall. |
| `trading_warmup_misses_total` > 0 / warmup WARNING (< 20 bars) | Orchestrator startup logs | Gap in warmup source. Backfill: `sts backfill today` (futures `kospi.kospi_mini_1m`) / `sts stock-backfill run` (stock `market.minute_candles`), then restart the asset. |
| Staleness gauge high / `data-freshness` stale | `trading_websocket_staleness_seconds{feed=...}`; feed logs | WS dropped or slow. Feed auto-reconnects (initial 1s → max 60s); failover to REST after 3 consecutive unhealthy (`failover.staleness_threshold_seconds=30`). If it doesn't recover, restart the asset process. |
| Only ONE asset has ticks | `pgrep -af "asset ..."`; that asset's logs | The other orchestrator isn't running or auth failed. Verify the missing process; check that asset's `KIS_*` creds and `KIS_*_MARKET`. |
| Both processes share one PID / only one PID | `ps -ef \| grep "sts trade"` | Not running as separate processes → no cross-asset parallelism. Start the missing `sts trade start --asset ...` (stock via `scripts/cron/stock_trading.sh start`). |
| Signal cycle ≥ 60s or rising | "Signal cycle" log line; fetch diagnostics | Per-bar budget breach. Check fetch latency, indicator recompute, ClickHouse/Redis latency. Confirm `parallel_entries/parallel_exits` true and shared indicator cache. |
| `/ws` times out / no live push, but REST endpoints work | Caddy config/logs | Caddy not reloaded after PR #380 `/ws` routing. Reload Caddy (`docker compose restart caddy` or `caddy reload`). |
| Signal on dashboard but no trade row | `stock_trades` / `rl_trades`; insert error logs | ClickHouse insert failing — check `kill_switch:metrics:clickhouse_insert_fail_rate` (Redis DB 1) and ClickHouse reachability. |
| Telegram alert in wrong channel | `TELEGRAM_{STOCK,FUTURES,BRIEFING}_*` env | Channel routing/env mixup. Verify per-asset chat IDs/tokens. |
| Stock & futures data mixed together | Redis keys; `asset_class` column; dashboard tabs | Asset separation broken. Confirm distinct `trading:stock:*` vs `trading:futures:*` keys and `asset_class='futures'` on `rl_trades`. |

---

## 6. Sign-off checklist

Operator: ____________________   Trading date (KST): ____________________

**Concern 1 — live WebSocket data, both assets**
- [ ] Distinct stock and futures orchestrator PIDs (separate processes)
- [ ] Both feeds logged first tick; no drop/stale WARNINGs
- [ ] Redis advancing for both; both `data-freshness` endpoints fresh
- [ ] `trading_websocket_staleness_seconds{feed="stock"|"futures"}` both < 60s

**Concern 2 — parallel, no bottleneck**
- [ ] Each asset's "Signal cycle" completes < 60s (p99 budget held)
- [ ] Market-data fetch latency low and flat (nowhere near 60s)
- [ ] `trading_feed_drops_total` == 0 (no backpressure)
- [ ] `trading_warmup_misses_total` == 0
- [ ] Within-asset gather concurrency + shared indicator cache confirmed

**Concern 3 — aggregation / processing / reporting**
- [ ] Signal traced to `/api/signals` + Redis (per asset)
- [ ] Position consistent across `/api/trading/positions` + Redis hash
- [ ] `feed_drops` / `warmup_misses` surfaced in `/api/trading/status`
- [ ] Closed trade persisted (`stock_trades` / `rl_trades`) + `/api/trades`
- [ ] Telegram alert in the correct channel (no cross-leak)
- [ ] Per-asset Prometheus series present (`asset="stock"` and `"futures"`)
- [ ] `/ws` upgrades through Caddy :5080 (PR #380)
- [ ] Stock vs futures separated throughout (keys, `asset_class`, tabs)

**Overall result**: ☐ PASS   ☐ FAIL (see notes) ____________________________

---

## References

- `docs/runbooks/futures-paradigm-operations.md` — futures daily operations
- `docs/runbooks/phase5-verification.md` — Phase 5 gate verification
- `config/streaming.yaml` — `feed_observability:` thresholds
  (`drop_warn_threshold`, `stale_warn_threshold_seconds`, `warmup_min_candles`)
- `services/trading/orchestrator.py` — feed health rollup, `get_status()`
  (`feed_drops`, `warmup_misses`)
- `services/trading/strategy_manager.py` — 60s "Signal cycle" summary
- `shared/kis/stock_feed.py`, `shared/kis/futures_feed.py`,
  `shared/kis/websocket.py` — feeds + `get_health_status()`
