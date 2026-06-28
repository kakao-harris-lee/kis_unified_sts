# Stream Processor Audit Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add low-noise, verifiable audit logging to trading stream processors.

**Architecture:** Add a shared streaming audit helper, integrate it at common
`StreamStage` boundaries, then patch manual monitor loops and signal producers.
The implementation must not alter trading decisions or Redis stream payloads.

**Tech Stack:** Python logging, Redis Streams, pytest, fakeredis where existing tests already use it.

---

## Task 1: Shared Audit Helper And StreamStage Integration

**Files:**
- Create: `shared/streaming/audit.py`
- Modify: `shared/streaming/stage.py`
- Test: `tests/unit/streaming/test_stream_audit.py`
- Test: `tests/unit/streaming/test_stream_stage.py`
- Test: `tests/unit/streaming/test_multi_stream_stage.py`

- [ ] **Step 1: Write failing helper tests**

Add tests proving identifier extraction, key/value rendering, and rate-limited
logging.

- [ ] **Step 2: Implement helper**

Implement `decode_stream_id`, `extract_audit_fields`, `format_audit_kv`, and
`RateLimitedLog`.

- [ ] **Step 3: Write failing StreamStage audit tests**

Add `caplog` tests proving ACK, NO-ACK, and reclaimed messages emit
`event=stream_message_processed` with `stream`, `consumer_group`, `worker_id`,
`msg_id`, `ack`, `claimed`, `duration_ms`, and `signal_id` when present.

- [ ] **Step 4: Integrate StreamStage and MultiStreamStage**

Emit one audit log per processed message and rate-limit repeated read/reclaim
errors.

- [ ] **Step 5: Verify and commit**

Run:

```bash
pytest tests/unit/streaming/test_stream_audit.py tests/unit/streaming/test_stream_stage.py tests/unit/streaming/test_multi_stream_stage.py -q
git diff --check
```

Commit:

```bash
git add shared/streaming/audit.py shared/streaming/stage.py tests/unit/streaming/test_stream_audit.py tests/unit/streaming/test_stream_stage.py tests/unit/streaming/test_multi_stream_stage.py
git commit -m "feat: add stream stage audit logging"
```

## Task 2: Manual Monitor And Tick-Consumer Log Context

**Files:**
- Modify: `services/futures_monitor/daemon.py`
- Modify: `services/stock_monitor/daemon.py`
- Modify: `services/trading/stream_consumer_feed.py`
- Test: existing relevant unit tests, or focused new tests under `tests/unit/futures_monitor/`, `tests/unit/stock_monitor/`, and `tests/unit/trading/`

- [ ] **Step 1: Write failing log-context tests**

Prove monitor handler-drop logs include `stream`, `consumer_group`,
`worker_id`, and `msg_id`. Prove repeated `StreamConsumerFeed` xread failures do
not emit an exception log on every loop.

- [ ] **Step 2: Implement monitor context logs**

Use `shared.streaming.audit.format_audit_kv` for poison-pill/handler-drop logs.

- [ ] **Step 3: Rate-limit tick-consumer xread failures**

Use `RateLimitedLog` in `StreamConsumerFeed._read_loop` without logging normal
tick success.

- [ ] **Step 4: Verify and commit**

Run:

```bash
pytest tests/unit/futures_monitor tests/unit/stock_monitor tests/unit/trading/test_stream_consumer_feed.py -q
git diff --check
```

Commit:

```bash
git add services/futures_monitor/daemon.py services/stock_monitor/daemon.py services/trading/stream_consumer_feed.py tests/unit/futures_monitor tests/unit/stock_monitor tests/unit/trading/test_stream_consumer_feed.py
git commit -m "fix: add monitor stream log context"
```

## Task 3: Signal Producer Publish Audit

**Files:**
- Modify: `services/decision_engine/main.py`
- Modify: `services/stock_strategy/daemon.py`
- Test: `tests/unit/decision_engine/`
- Test: `tests/unit/stock_strategy/test_daemon.py`

- [ ] **Step 1: Write failing publish-log tests**

Verify futures and stock signal publication logs include stream and signal ID.

- [ ] **Step 2: Implement concise publish audit logs**

Log only when a signal is emitted. Do not log idle cycles or per-tick market
data paths.

- [ ] **Step 3: Verify and commit**

Run:

```bash
pytest tests/unit/decision_engine tests/unit/stock_strategy/test_daemon.py -q
git diff --check
```

Commit:

```bash
git add services/decision_engine/main.py services/stock_strategy/daemon.py tests/unit/decision_engine tests/unit/stock_strategy/test_daemon.py
git commit -m "feat: log signal publish audit keys"
```

## Task 4: Documentation And Final Verification

**Files:**
- Modify: `docs/testing/quant-gap-execution-2026-06-28.md` or create a focused testing note if needed.
- Modify: existing PR body after push.

- [ ] **Step 1: Add runtime validation checklist**

Document that real log samples will be validated on the paper-trading machine
after the next session.

- [ ] **Step 2: Run focused verification**

Run:

```bash
pytest tests/unit/streaming/test_stream_audit.py tests/unit/streaming/test_stream_stage.py tests/unit/streaming/test_multi_stream_stage.py tests/unit/trading/test_stream_consumer_feed.py tests/unit/futures_monitor tests/unit/stock_monitor tests/unit/decision_engine tests/unit/stock_strategy/test_daemon.py -q
git diff --check
```

- [ ] **Step 3: Push and update PR**

Push the branch and update the existing draft PR with a validation note.
