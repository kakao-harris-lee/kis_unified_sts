# Runbook: Paper Trading Cutover — host-cron → Docker Compose

> **ARCHIVED 2026-06-22:** Historical 2026-06-08 cutover runbook. It predates
> the cron-to-Compose scheduler migration and the current stock decoupled
> runtime. Use [stock-pipeline-cutover-m5d.md](../../runbooks/stock-pipeline-cutover-m5d.md),
> [futures-pipeline-cutover-f9.md](../../runbooks/futures-pipeline-cutover-f9.md),
> and [cron-to-compose-cutover.md](../../runbooks/cron-to-compose-cutover.md)
> for current operation.

Migrate the **currently-running** paper system from host crontab + host
`redis-server` (6379) to the Docker Compose stack, for stock + futures paper
verification. One runtime only — the two **cannot** coexist (same KIS app keys →
WebSocket session collision + double trades).

## Locked decisions (2026-06-08)

| Item | Choice |
|------|--------|
| Runtime | **Full cutover to Docker Compose.** Host-cron *trading* disabled. |
| Stock path | **Decoupled M4 pipeline** (`stock-ingest` + `stock-pipeline` profiles), `STOCK_PIPELINE_MODE=live`. |
| Futures path | **`trader-futures`** orchestrator daemon (`trading` profile). |
| Redis | **Single host `redis-server` on 6379** (password-less). Containers reach it via `host.docker.internal:6379`; the Compose `redis` service is **not** started (`--no-deps`). |
| Watchlist producers | **Stay on host cron** (screener / fusion / daily_scanner / indicator) — they only *produce* `system:*:latest` keys into 6379, no WS, no trades. |
| Diagnosis focus | signal quality·PnL / feed·system stability / data integrity. |

> Why `STOCK_PIPELINE_MODE=live` and not `paper`: the decoupled daemons accept only
> `shadow` | `live` (any other value → inert). **Both fill via `VirtualBroker`** — the
> stock order-router has *no* real-KIS order path in code. `live` = the
> *unsuffixed* (primary) keyspace; `shadow` = isolated `.shadow` logging only.
> `paper` is invalid and silently disables every daemon.

## Current state (verified 2026-06-08)

- No `kis-*` containers running. Paper runs via host crontab + host redis 6379.
- 6379 db1: 5491 keys; `system:trade_targets:latest` + `system:daily_watchlist:latest`
  present and fresh; password-less; bound `0.0.0.0` (container-reachable).
- Host-cron trading entries (to disable): `stock_trading.sh start|stop|watchdog`,
  `setup_ac_paper` futures + watchdog.

---

## .env.paper — create and apply the single-Redis overrides

```bash
cp .env.paper.example .env.paper      # gitignored (PR #437); fill every CHANGE_ME_*
```

Then set these (override the `.env.paper.example` defaults):

```dotenv
# --- Single host Redis (no separate compose redis) ---
REDIS_HOST=host.docker.internal
REDIS_PORT=6379
REDIS_URL=redis://host.docker.internal:6379/1
REDIS_PASSWORD=
REDIS_HOST_PORT=6381            # parked; the compose redis is NOT started

# --- Stock: decoupled pipeline, actively trading (paper fills via VirtualBroker) ---
STOCK_PIPELINE_MODE=live        # shadow = isolated logging only; paper = INVALID (inert)
STOCK_ORCHESTRATOR_ENABLED=false  # block monolithic stock (anti double-trade)
KIS_STOCK_MARKET=mock

# --- Futures: orchestrator daemon, real WS data + VirtualBroker fills ---
FUTURES_ORCHESTRATOR_ENABLED=true
FUTURES_TRADING_STRATEGY=       # blank = registry default (Setup A/C)
KIS_FUTURES_MARKET=real
TRADING_MODE=paper
KIS_REAL_TRADING=false
```

Fill the real secrets (`KIS_STOCK_*`, `KIS_FUTURES_*`, `TELEGRAM_*`, `API_KEY`,
`DASHBOARD_API_KEY`). `REDIS_PASSWORD` stays empty because host 6379 is password-less.

---

## Cutover (run before 08:55 KST, off-hours)

### 1. Disable host-cron trading (keep producers)

```bash
crontab -l > ~/crontab.backup.$(date +%Y%m%d)   # backup first
crontab -e
```

Comment out (prefix `#`) **only** these — leave screener / fusion / daily_scanner /
indicator untouched:

```
# 55 8  * * 1-5 .../scripts/cron/stock_trading.sh start
# 0  16 * * 1-5 .../scripts/cron/stock_trading.sh stop
# 2-52/5 9-15 * * 1-5 .../scripts/cron/stock_trading.sh start   (watchdog)
# 55 8  * * 1-5 ... cli.main trade start --asset futures --paper --single
# 2-57/5 9-15 * * 1-5 ... cli.main trade start --asset futures --paper --single  (watchdog)
```

### 2. Stop running host trading + clean disposable paper state

```bash
# stop any live host orchestrator loops
pkill -f 'cli.main trade start' || true
bash scripts/cron/stock_trading.sh stop || true

# (optional) flatten, then clear paper position keys on 6379
python scripts/trading/flatten_all.py --asset stock || true
redis-cli -p 6379 -n 1 del stock:daemon:positions trading:stock:positions \
  trading:futures:positions
```

### 3. Stock daily risk reset (so `stock_cutover_verify --mode live` CRITICAL passes)

```bash
REDIS_URL=redis://localhost:6379/1 .venv/bin/python -m scripts.maintenance.daily_risk_reset
```

### 4. Build + launch (all `--no-deps`; compose redis stays down)

```bash
docker compose --env-file .env.paper build

# infra (dashboard/ui/caddy/exporter) — connect out to host redis
docker compose --env-file .env.paper up -d --no-deps \
  dashboard strategy-builder-ui caddy stream-exporter

# stock decoupled pipeline + tick ingest
docker compose --env-file .env.paper --profile stock-ingest --profile stock-pipeline \
  up -d --no-deps stock-market-ingest stock-strategy stock-risk-filter \
  stock-order-router stock-exit stock-monitor

# futures orchestrator daemon
docker compose --env-file .env.paper --profile trading up -d --no-deps trader-futures
```

> `--no-deps` is required: it stops Compose from auto-starting its own `redis`
> service, which would collide on host port 6379. The containers reach the host
> redis via `host.docker.internal` (wired through `extra_hosts: host-gateway`).

### 5. Verify (after 09:00 KST, feed live)

```bash
docker compose --env-file .env.paper ps
python -m scripts.ops.stock_cutover_verify --mode live          # expect PASS

# redis reachability from inside a container
docker compose --env-file .env.paper exec -T stock-strategy \
  python -c "import os,redis; print(redis.from_url(os.environ['REDIS_URL']).ping())"

# tick freshness + decoupled streams
redis-cli -p 6379 -n 1 xlen market:ticks
redis-cli -p 6379 -n 1 xlen signal.candidate.stock signal.final.stock order.fill.stock
redis-cli -p 6379 -n 1 hlen stock:daemon:positions

docker compose --env-file .env.paper logs --tail=50 trader-futures   # "asset=futures mode=paper"
```

Dashboard: `http://<host>:5081` (caddy). Confirm positions/signals/fills populate.

---

## Diagnosis setup (what to watch)

| Axis | Where | Signal |
|------|-------|--------|
| Signal quality·PnL | dashboard `/signals` `/trades`, RuntimeLedger SQLite | entry/exit cadence, win-rate, per-strategy PnL, hold time |
| Feed·system stability | Prometheus (`:9091`) / dashboard `/metrics` | `trading_ws_{disconnect,reconnect}_total{feed}`, `trading_rate_limit_penalty_total`, `trading_pipeline_stage_latency_ms{stage}`, `trading_errors_total`, restart loops (`docker compose ps`) |
| Data integrity | redis + parquet | `market:ticks` freshness, gap warnings, pre-market warmup, watchlist key TTL |

Two log lines to grep on the trading services: pipeline **slow-stage WARN** and
**rate-limit recovery INFO**. Everything else is metrics-only.

---

## Rollback (back to host-cron paper)

```bash
docker compose --env-file .env.paper down                # stop the whole stack
crontab ~/crontab.backup.YYYYMMDD                        # re-enable host-cron trading
# host redis 6379 was never touched; watchlist producers kept running throughout.
```

Rollback triggers: container restart-loop, market data stale during hours, fills
stop while final signals present, unbounded stream backlog, or WS feed flapping.

## Notes / open items

- **Self-contained variant (future hardening):** run the Compose `redis` as the
  single store and repoint the producer crons to it (passworded). Heavier (cron
  env + password alignment); deferred until paper is stable on the host-redis path.
- `risk:state:stock:meta` must be refreshed daily (step 3). Consider a paper cron
  `59 8 * * 1-5 ... daily_risk_reset` once the stack is stable.
- M5b LLM market-context is **optional** for the decoupled chain (no risk filter
  gates on it); enable later if a strategy needs it.
