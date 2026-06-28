# Stream Processor Audit Logging QA - 2026-06-28

This note captures static QA for the stream processor audit-logging pass.
Runtime log samples are intentionally deferred: this development host does not
have the paper-trading market session logs, so the final evidence check should
run on the mock/paper trading machine after the next session.

## Scope

| Area | Services | Expected evidence |
|------|----------|-------------------|
| Common stream stages | `news_scorer`, `risk_filter`, `order_router`, `stock_risk_filter`, `stock_order_router` | `event=stream_message_processed`, `event=stream_message_failed`, `event=stream_message_ack_failed` |
| Manual monitor loops | `stock-monitor`, `futures-monitor` | `event=stream_message_dropped`, rate-limited `event=monitor_stream_read_error` |
| Tick stream consumer | stock orchestrator stream-consumer path | rate-limited `event=tick_stream_read_error`; no per-tick success log |
| Signal producers | `stock-strategy`, `futures-decision-engine` | `event=signal_published` with Redis `msg_id` and generated `signal_id` |

## Static Verification

| Command | Result |
|---------|--------|
| `pytest tests/unit/streaming/test_stream_audit.py tests/unit/streaming/test_stream_stage.py tests/unit/streaming/test_multi_stream_stage.py -q` | Exit 0. |
| `pytest tests/unit/futures_monitor/test_daemon.py tests/unit/stock_monitor/test_daemon.py tests/unit/trading/test_stream_consumer_feed.py tests/unit/services/test_decision_engine_main.py tests/unit/stock_strategy/test_daemon.py -q` | Exit 0. |
| `pytest tests/unit/streaming/test_stream_audit.py tests/unit/streaming/test_stream_stage.py tests/unit/streaming/test_multi_stream_stage.py tests/unit/futures_monitor/test_daemon.py tests/unit/stock_monitor/test_daemon.py tests/unit/trading/test_stream_consumer_feed.py tests/unit/services/test_decision_engine_main.py tests/unit/stock_strategy/test_daemon.py -q` | Exit 0. |
| `ruff check shared/streaming/audit.py shared/streaming/stage.py services/futures_monitor/daemon.py services/stock_monitor/daemon.py services/trading/stream_consumer_feed.py tests/unit/streaming/test_stream_audit.py tests/unit/streaming/test_stream_stage.py tests/unit/streaming/test_multi_stream_stage.py` | Exit 0. |
| `git diff --check` | Exit 0. |

## Runtime Checklist

Run on the mock/paper trading machine after services have processed real or
paper-session stream traffic:

```bash
docker compose logs --since 24h \
  stock-strategy stock-risk-filter stock-order-router stock-monitor \
  futures-decision-engine futures-risk-filter futures-order-router futures-monitor |
  rg 'event=(signal_published|stream_message_processed|stream_message_dropped|stream_message_failed|stream_message_ack_failed|monitor_stream_read_error)'
```

For the stock stream-consumer path, include the stock trader/orchestrator
service that owns `StreamConsumerFeed` and search for:

```bash
rg 'event=tick_stream_read_error' <orchestrator-log-file>
```

Expected checks:

- `event=signal_published` has `stream`, Redis `msg_id`, generated `signal_id`,
  and core identifier fields (`symbol`/`setup_type` for futures, `code`/`strategy`
  for stock).
- Downstream `event=stream_message_processed` records can be correlated by
  `msg_id` and safe identifiers such as `signal_id`, `code`, `symbol`,
  `strategy`, or `setup_type`.
- `ack=true` appears only after successful `XACK`. If `XACK` fails, the log
  should be `event=stream_message_ack_failed` instead.
- Poison-pill monitor drops include `event=stream_message_dropped`,
  `reason=handler_exception`, `stream`, `consumer_group`, `worker_id`, `msg_id`,
  and safe identifier fields.
- Repeated Redis read errors are not emitted on every loop. After a successful
  read, a later error is visible again as a new incident.
- There are no per-tick success logs from the tick stream consumer.

## Notes

- Log values are rendered as parseable `key=value` tokens; values with spaces,
  newlines, or `=` are quoted/escaped to avoid forged tokens or multi-line log
  entries.
- The implementation adds observability only. It does not change stream payloads,
  strategy decisions, risk gates, order routing decisions, or stock/futures
  liquidation policy.
