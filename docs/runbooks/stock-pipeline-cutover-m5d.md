# Runbook: Stock Pipeline Cutover (M5d, Compose)

Flip stock **paper** trading from the monolithic compose `trader` loop to the
decoupled M4 pipeline (M4-P -> M4-R -> M4-O -> M4-X) + M5a monitor + M5b LLM
context job + M5c daily risk reset. Paper->paper: M4-O still uses `VirtualBroker`.
The operational risks are silent stop, double trading, and stale market data.

Spec: `docs/superpowers/specs/2026-06-06-stock-stream-cutover-m5d-design.md`
Compose plan: `docs/plans/archive/2026-06-06-compose-pipeline-services.md`

## Compose Profiles

- `trading`: legacy monolithic `trader` service (`sts trade start`).
- `stock-pipeline`: `stock-strategy`, `stock-risk-filter`, `stock-order-router`,
  `stock-exit`, `stock-monitor`.
- `stock-ingest`: `stock-market-ingest`, the KIS stock WebSocket owner and
  `market:ticks` producer.

`stock-market-ingest` is separate on purpose. Do not run it while the monolithic
stock trader still owns the KIS stock WebSocket feed.

## Gate 0 - Prerequisites

- Copy `.env.paper.example` to `.env.paper` and fill secrets.
- `docker compose --env-file .env.paper up -d redis dashboard strategy-builder-ui caddy stream-exporter`
- Monolithic stock trader is running normally:
  `docker compose --env-file .env.paper --profile trading up -d trader`.
- `STOCK_PIPELINE_MODE=shadow` in `.env.paper`, or unset so compose defaults to shadow.
- M5b LLM context runs in shadow via an operator cron or one-shot compose command.
- M5c daily risk reset is installed for the paper environment.

## Gate 1 - Shadow Validation (>= 3-5 Trading Days)

Start the decoupled stock consumers without the ingest daemon:

```bash
docker compose --env-file .env.paper --profile stock-pipeline up -d \
  stock-strategy stock-risk-filter stock-order-router stock-exit stock-monitor
```

Each trading day:

- `python -m scripts.ops.stock_cutover_verify --mode shadow` -> PASS.
- `docker compose --env-file .env.paper ps stock-strategy stock-risk-filter stock-order-router stock-exit stock-monitor` shows the services up.
- M5a dashboard `:shadow` keys show decoupled signals/fills/positions.
- No unbounded stream backlog and no restart loop.
- Optional sanity check: compare shadow decisions with monolithic paper trades for direction, not exact fill parity.

## Gate 2 - Operator Approval

Record the date and a one-line shadow validation summary before proceeding.

## Cutover Sequence (Run Off-Hours)

1. Flatten and clear disposable paper state:

   ```bash
   python scripts/trading/flatten_all.py --asset stock        # optional
   docker compose --env-file .env.paper --profile trading stop trader
   docker compose --env-file .env.paper exec -T redis sh -c \
     'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli -n 1 del stock:daemon:positions trading:stock:positions'
   ```

2. Start the decoupled live stock pipeline and the stock ingest daemon:

   ```bash
   STOCK_PIPELINE_MODE=live \
     docker compose --env-file .env.paper \
       --profile stock-ingest --profile stock-pipeline up -d \
       stock-market-ingest stock-strategy stock-risk-filter stock-order-router \
       stock-exit stock-monitor
   ```

3. Move M5b to live context publishing:

   - If cron-managed: change `STOCK_LLM_CONTEXT=shadow` to `STOCK_LLM_CONTEXT=live`.
   - Disable the monolithic orchestrator LLM publisher in `config/llm.yaml`
     (`market_context_publisher.enabled: false`) before restarting any monolithic trader.
   - M5c daily risk reset is mode-agnostic.

4. Post-cutover verification:

   ```bash
   python -m scripts.ops.stock_cutover_verify --mode live
   docker compose --env-file .env.paper ps \
     stock-market-ingest stock-strategy stock-risk-filter stock-order-router \
     stock-exit stock-monitor
   ```

5. First 09:00 KST session observation:

   - `market:ticks` is fresh.
   - live dashboard keys show positions/fills/signals.
   - no restart loop or backlog growth.

6. Permanently block accidental stock monolith restart after successful cutover:

   ```bash
   # in .env.paper
   STOCK_ORCHESTRATOR_ENABLED=false
   ```

## Rollback Triggers

Roll back if any of these happen: live verify fails, market data goes stale during
market hours, fills stop while final signals are present, stream backlog grows
without bound, or a compose service restart-loops.

## Rollback

```bash
COMPOSE_ENV_FILE=/home/deploy/project/kis_unified_sts/.env.paper \
  bash scripts/ops/stock_cutover_rollback.sh --dry-run
COMPOSE_ENV_FILE=/home/deploy/project/kis_unified_sts/.env.paper \
  bash scripts/ops/stock_cutover_rollback.sh
```

Then re-enable `config/llm.yaml::market_context_publisher.enabled: true`, revert
the M5b cron to `STOCK_LLM_CONTEXT=shadow`, and confirm the monolithic trader is
up:

```bash
docker compose --env-file .env.paper --profile trading ps trader
python -m scripts.ops.stock_cutover_verify --mode shadow
```

## Notes

- `stock:daemon:positions` is the M4-R/O/X/monitor working store.
- `trading:stock:positions[:shadow]` is the dashboard-native key owned by
  `TradingStatePublisher`.
- Residual positions in the KIS mock account from the monolithic trader remain a
  documented follow-up cleanup.
- The paper-grade halt for the decoupled stock pipeline is:

  ```bash
  docker compose --env-file .env.paper stop \
    stock-market-ingest stock-strategy stock-risk-filter stock-order-router \
    stock-exit stock-monitor
  ```
