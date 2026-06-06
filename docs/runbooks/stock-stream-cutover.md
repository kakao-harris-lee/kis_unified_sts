# Runbook — Stock Market-Data Stream Cutover (M1c)

Switch the stock orchestrator from owning the KIS WebSocket feed to consuming
the Redis tick stream published by the `kis-market-ingest-stock` daemon (M1a).
Flag: `STOCK_MARKET_DATA_SOURCE` (`websocket` default | `stream`). Stock only —
futures stays `websocket` (the tick stream carries no orderbook, which the
futures slippage controller requires).

## Preconditions

1. `stock-market-ingest` (M1a) running and healthy:
   - `docker compose --env-file .env.paper --profile stock-ingest ps stock-market-ingest`
   - Redis: `redis-cli -n 1 XLEN market:ticks` rising during market hours.
2. No second WebSocket consumer for the same KIS stock account (the ingest
   daemon owns the WS connection; the orchestrator must NOT also connect).

## Activate

1. Set the flag for the stock orchestrator process/unit env:
   `STOCK_MARKET_DATA_SOURCE=stream`
   (also ensure `REDIS_URL` points at the right DB — paper `…/1` on 6381,
   live `…/1` on 6382, per the paper/live separation runbook).
2. Start the ingest daemon through compose:
   `docker compose --env-file .env.paper --profile stock-ingest up -d stock-market-ingest`.
3. Restart the stock orchestrator.
4. Confirm in logs: `Stock data source = STREAM (market:ticks); KIS WebSocket feed skipped`
   and `Stock stream-consumer feed started (N symbols)`.

## Validate the SLO

The goal is ingest latency independent of downstream compute load. Check:

- `market_data_staleness` p99 flat/improved vs the websocket baseline and not
  rising when indicator/strategy/LLM load spikes.
- tick→XADD latency (ingest side) stable.
- `trading_signal_latency_ms` unchanged or better.
- Positions/signals/fills appear normal vs the websocket baseline; paper PnL
  marks update per tick (paper_broker observations preserved).

## Rollback

1. Set `STOCK_MARKET_DATA_SOURCE=websocket` (or unset).
2. Restart the stock orchestrator. It rebuilds the KIS WebSocket feed; the
   stream feed and its async redis client are torn down on stop.

No data migration is involved — the flag flip is the whole switch.

## Notes

- If the ingest daemon dies/lags while `stream` is active, the orchestrator's
  `MarketDataProvider` failover degrades to KIS REST polling (the `_kis_client`
  is retained) rather than going dark.
- Futures cutover is a separate increment (needs an orderbook transport).
