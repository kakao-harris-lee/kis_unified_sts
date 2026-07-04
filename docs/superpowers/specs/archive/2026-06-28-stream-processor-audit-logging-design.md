# Stream Processor Audit Logging Design

Date: 2026-06-28

## Goal

Make the trading stream processors leave enough low-noise evidence to answer,
after a paper/live session, which stream message was processed, acknowledged,
retried, skipped, or dropped.

## Scope

This is code-side observability only. The development server has no live trading
log sample, so runtime validation is deferred to the next paper-trading session.
This change must not alter trading decisions, stream payloads, Redis DB
selection, order placement, or position management.

## Requirements

- Every `StreamStage` and `MultiStreamStage` processed message emits one audit
  log with stable key/value fields:
  `event=stream_message_processed`, `stream`, `consumer_group`, `worker_id`,
  `msg_id`, `ack`, `claimed`, `duration_ms`, and any available
  `signal_id`, `symbol`/`code`, `strategy`, `setup_type`.
- Poison-pill and handler-drop logs in monitor loops include `stream`,
  `consumer_group`, `worker_id`, and `msg_id`.
- Repeated Redis read/reclaim errors are rate-limited so a sustained outage does
  not print a traceback every 0.5 seconds. First failure should still include a
  traceback; later failures should be summarized until the cooldown expires.
- Signal producers emit a concise publish audit only when a signal is emitted,
  not on idle ticks or per-market-tick paths.
- Raw tick publish/consume success remains quiet. Existing tick publisher stats
  stay the primary high-volume observability surface.

## Design

Add `shared.streaming.audit` as a small helper module:

- `decode_stream_id(value)` normalizes `bytes`/`str` stream IDs for logs.
- `extract_audit_fields(fields)` extracts non-sensitive identifiers from Redis
  fields.
- `format_audit_kv(**items)` renders stable key/value log text without requiring
  a repo-wide logging formatter migration.
- `RateLimitedLog` tracks last emission, suppressed count, and emits either a
  full first traceback or a summary message.

Integrate the helper at framework boundaries first:

- `StreamStage._process_messages` logs one audit line after each
  `handle_message` return and before/after the ACK decision is known.
- `MultiStreamStage._process_messages` does the same while preserving source
  stream names.
- Reclaim/read errors in the shared loop use `RateLimitedLog`.

Then cover manual loops and producers:

- `futures_monitor` and `stock_monitor` add stream/message context to handler
  drop logs and rate-limit Redis read errors.
- `StreamConsumerFeed` rate-limits repeated `xread` failures; it does not log
  every successful tick.
- `DecisionEngineDaemon._publish` and `StockStrategyDaemon._publish` log one
  signal-published audit line with stream, signal ID, symbol/code, strategy or
  setup where available.

## Testing

Unit tests should verify:

- Audit helper extraction and rate-limit behavior.
- `StreamStage` emits ACK and NO-ACK audit records with message IDs and
  extracted signal IDs.
- `MultiStreamStage` emits source stream names and `claimed=true` for reclaimed
  pending messages.
- Monitor poison-pill logs include stream/message context.
- Signal producers log only on publish.

Runtime validation after paper trading:

1. Capture service logs for stock and futures stream daemons.
2. Search for `event=stream_message_processed`.
3. For a sampled `signal_id`, verify the path can be followed through candidate,
   risk, final, order/fill, and monitor logs or streams.
4. During an injected Redis read outage, verify logs are rate-limited and include
   suppressed counts.
