# Architecture Hardening Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove two concrete stream-pipeline architecture gaps: futures instrument selection drift and lack of a shared multi-input Redis stream stage.

**Architecture:** Add one shared futures instrument resolver and make all current futures entrypoints read the same product/symbol contract. Add a `MultiStreamStage` sibling to `StreamStage` so services that consume multiple streams can share consumer-group creation, pending reclaim, retry, and stream-specific ACK behavior.

**Tech Stack:** Python 3, pytest, fakeredis, Redis Streams consumer groups, existing `shared.collector.historical.futures.get_front_month_code`.

---

## File Structure

- Create `shared/execution/futures_instrument.py`
  - Owns normalized futures product selection and env-driven symbol resolution.
- Modify `services/trading/orchestrator.py`
  - Replace local `FUTURES_TRADING_PRODUCT` branch in `TradingConfig._get_futures_default_symbols`.
- Modify `services/decision_engine/main.py`
  - Use the shared resolver instead of requiring `FUTURES_STRATEGY_SYMBOL`.
- Modify `services/market_ingest/main.py`
  - Use the shared resolver for futures tick symbols.
- Modify `services/futures_monitor/main.py`
  - Use the shared resolver for monitor feed/spec symbol.
- Modify `services/order_router/main.py`
  - Use the shared resolver for order-router feed/spec symbol.
- Create `tests/unit/execution/test_futures_instrument_config.py`
  - Resolver unit tests.
- Modify `tests/unit/trading/test_futures_product_selection.py`
  - Keep orchestrator compatibility tests green through the shared resolver.
- Modify `shared/streaming/stage.py`
  - Add `MultiStreamStage` without changing the existing `StreamStage` public contract.
- Create `tests/unit/streaming/test_multi_stream_stage.py`
  - Multi-stream group creation, read, reclaim, and ACK tests.

Workers must not edit files outside their assigned ownership unless the controller explicitly reassigns scope. The controller owns final integration, verification, commit, and push.

---

### Task 1: Shared Futures Instrument Resolver

**Owner:** FuturesInstrumentConfig worker.

**Files:**
- Create: `shared/execution/futures_instrument.py`
- Create: `tests/unit/execution/test_futures_instrument_config.py`
- Modify: `services/trading/orchestrator.py`
- Modify: `services/decision_engine/main.py`
- Modify: `services/market_ingest/main.py`
- Modify: `services/futures_monitor/main.py`
- Modify: `services/order_router/main.py`
- Modify: `tests/unit/trading/test_futures_product_selection.py` only if needed to keep its assertions current.

- [ ] **Step 1: Write the failing resolver tests**

Add `tests/unit/execution/test_futures_instrument_config.py`:

```python
"""Tests for shared futures instrument selection."""

from __future__ import annotations

from datetime import date

from shared.execution.futures_instrument import (
    DEFAULT_FUTURES_PRODUCT,
    FuturesInstrumentConfig,
    normalize_futures_product,
    resolve_futures_instrument_from_env,
)


def test_default_product_is_mini_front_month(monkeypatch):
    monkeypatch.delenv("FUTURES_TRADING_PRODUCT", raising=False)
    monkeypatch.delenv("FUTURES_STRATEGY_SYMBOL", raising=False)

    instrument = resolve_futures_instrument_from_env(
        target_date=date(2026, 3, 1)
    )

    assert instrument == FuturesInstrumentConfig(
        symbol="A05603",
        product=DEFAULT_FUTURES_PRODUCT,
        source="FUTURES_TRADING_PRODUCT",
    )


def test_kospi200_product_selects_full_size_front_month(monkeypatch):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "KOSPI200")
    monkeypatch.delenv("FUTURES_STRATEGY_SYMBOL", raising=False)

    instrument = resolve_futures_instrument_from_env(
        target_date=date(2026, 3, 1)
    )

    assert instrument.symbol == "A01603"
    assert instrument.product == "kospi200"
    assert instrument.source == "FUTURES_TRADING_PRODUCT"


def test_invalid_product_falls_back_to_mini(monkeypatch):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "nikkei")
    monkeypatch.delenv("FUTURES_STRATEGY_SYMBOL", raising=False)

    instrument = resolve_futures_instrument_from_env(
        target_date=date(2026, 3, 1)
    )

    assert instrument.symbol == "A05603"
    assert instrument.product == "mini"


def test_explicit_strategy_symbol_overrides_front_month(monkeypatch):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "mini")
    monkeypatch.setenv("FUTURES_STRATEGY_SYMBOL", "A01603")

    instrument = resolve_futures_instrument_from_env(
        target_date=date(2026, 3, 1)
    )

    assert instrument.symbol == "A01603"
    assert instrument.product == "mini"
    assert instrument.source == "FUTURES_STRATEGY_SYMBOL"


def test_normalize_futures_product_is_case_insensitive():
    assert normalize_futures_product(" KOSPI200 ") == "kospi200"
    assert normalize_futures_product(" mini ") == "mini"
    assert normalize_futures_product("") == "mini"
    assert normalize_futures_product(None) == "mini"
```

- [ ] **Step 2: Run the resolver test and verify RED**

Run:

```bash
pytest tests/unit/execution/test_futures_instrument_config.py -q
```

Expected: fail during import because `shared.execution.futures_instrument` does not exist.

- [ ] **Step 3: Implement the shared resolver**

Create `shared/execution/futures_instrument.py`:

```python
"""Shared futures instrument selection.

All futures daemons should resolve their active contract through this module so
paper/live/shadow services do not drift on product or symbol selection.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from shared.collector.historical.futures import get_front_month_code

DEFAULT_FUTURES_PRODUCT = "mini"
SUPPORTED_FUTURES_PRODUCTS = frozenset({"mini", "kospi200"})


@dataclass(frozen=True)
class FuturesInstrumentConfig:
    """Resolved futures instrument metadata."""

    symbol: str
    product: str
    source: str


def normalize_futures_product(value: str | None) -> str:
    """Normalize FUTURES_TRADING_PRODUCT with mini as the safe runtime default."""
    product = (value or DEFAULT_FUTURES_PRODUCT).strip().lower()
    if product not in SUPPORTED_FUTURES_PRODUCTS:
        return DEFAULT_FUTURES_PRODUCT
    return product


def resolve_futures_instrument_from_env(
    *,
    environ: Mapping[str, str] | None = None,
    target_date: date | None = None,
) -> FuturesInstrumentConfig:
    """Resolve the futures contract from env with an explicit symbol override."""
    env = os.environ if environ is None else environ
    product = normalize_futures_product(env.get("FUTURES_TRADING_PRODUCT"))
    explicit_symbol = (env.get("FUTURES_STRATEGY_SYMBOL") or "").strip()
    if explicit_symbol:
        return FuturesInstrumentConfig(
            symbol=explicit_symbol,
            product=product,
            source="FUTURES_STRATEGY_SYMBOL",
        )
    return FuturesInstrumentConfig(
        symbol=get_front_month_code(product=product, target_date=target_date),
        product=product,
        source="FUTURES_TRADING_PRODUCT",
    )
```

- [ ] **Step 4: Run resolver tests and verify GREEN**

Run:

```bash
pytest tests/unit/execution/test_futures_instrument_config.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Wire orchestrator through the resolver**

In `services/trading/orchestrator.py`, replace `TradingConfig._get_futures_default_symbols` local product logic with:

```python
        from shared.execution.futures_instrument import (
            resolve_futures_instrument_from_env,
        )

        instrument = resolve_futures_instrument_from_env()
        logger.info(
            "Futures default symbol (resolved): %s (product=%s source=%s)",
            instrument.symbol,
            instrument.product,
            instrument.source,
        )
        return [instrument.symbol]
```

- [ ] **Step 6: Wire decoupled futures services through the resolver**

Use this import in each service function where the current symbol is resolved:

```python
from shared.execution.futures_instrument import resolve_futures_instrument_from_env
```

Apply the service-specific replacements:

`services/decision_engine/main.py`:

```python
    instrument = resolve_futures_instrument_from_env()
    symbol = instrument.symbol
```

This replaces the direct `FUTURES_STRATEGY_SYMBOL` lookup and removes the runtime error that forces shadow/live mode to use a different source of truth.

`services/market_ingest/main.py` futures branch:

```python
        async def symbol_provider() -> list[str]:
            return [resolve_futures_instrument_from_env().symbol]
```

`services/futures_monitor/main.py`:

```python
    instrument = resolve_futures_instrument_from_env()
    symbol = instrument.symbol
```

`services/order_router/main.py`:

```python
    instrument = resolve_futures_instrument_from_env()
    symbol = instrument.symbol
```

Remove now-unused `get_front_month_code` imports and local `FUTURES_TRADING_PRODUCT` branches from those functions.

- [ ] **Step 7: Run focused futures instrument tests**

Run:

```bash
pytest tests/unit/execution/test_futures_instrument_config.py tests/unit/trading/test_futures_product_selection.py -q
```

Expected: both files pass.

- [ ] **Step 8: Run ruff on the touched Python files**

Run:

```bash
ruff check shared/execution/futures_instrument.py services/trading/orchestrator.py services/decision_engine/main.py services/market_ingest/main.py services/futures_monitor/main.py services/order_router/main.py tests/unit/execution/test_futures_instrument_config.py tests/unit/trading/test_futures_product_selection.py
```

Expected: no lint errors.

---

### Task 2: Shared MultiStreamStage

**Owner:** MultiStreamStage worker.

**Files:**
- Modify: `shared/streaming/stage.py`
- Create: `tests/unit/streaming/test_multi_stream_stage.py`
- Modify: `shared/streaming/__init__.py` only if exporting `MultiStreamStage` is needed by tests or existing import patterns.

- [ ] **Step 1: Write the failing multi-stream tests**

Add `tests/unit/streaming/test_multi_stream_stage.py`:

```python
"""Unit tests for shared.streaming.stage.MultiStreamStage."""

from __future__ import annotations

import asyncio

import pytest

from shared.streaming.stage import MultiStreamStage


class FakeRedis:
    def __init__(
        self,
        batches: list[tuple[str, list[tuple[bytes, dict[bytes, bytes]]]]],
        claimed: dict[str, list[list[tuple[bytes, dict[bytes, bytes]]]]] | None = None,
    ) -> None:
        self._batches = list(batches)
        self._claimed = {key: list(value) for key, value in (claimed or {}).items()}
        self.created: list[tuple[str, str, str, bool]] = []
        self.acked: list[tuple[str, bytes]] = []
        self.xreadgroup_calls = 0
        self.xautoclaim_calls: list[str] = []

    async def xgroup_create(self, stream, group, id="0", mkstream=False):
        self.created.append((stream, group, id, mkstream))

    async def xreadgroup(self, *, streams, **_kwargs):
        self.xreadgroup_calls += 1
        if self._batches:
            stream, messages = self._batches.pop(0)
            assert stream in streams
            return [(stream, messages)]
        await asyncio.sleep(0)
        return []

    async def xautoclaim(
        self, stream, _group, _worker, _idle_ms, _start_id, *, count
    ):
        self.xautoclaim_calls.append(stream)
        batches = self._claimed.get(stream, [])
        if batches:
            return ["0-0", batches.pop(0)[:count], []]
        return ["0-0", [], []]

    async def xack(self, stream, _group, msg_id):
        self.acked.append((stream, msg_id))


class RecordingMultiStage(MultiStreamStage):
    def __init__(self, *, ack_result=True, gate_result=True, **kwargs):
        super().__init__(**kwargs)
        self.ack_result = ack_result
        self.gate_result = gate_result
        self.handled: list[tuple[str, bytes]] = []
        self.post_poll_counts: list[int] = []
        self.shutdown_calls = 0

    async def handle_message(self, stream, msg_id, _fields):
        self.handled.append((stream, msg_id))
        return self.ack_result

    async def pre_iteration_gate(self):
        return self.gate_result

    async def post_poll(self, message_count):
        self.post_poll_counts.append(message_count)

    async def on_shutdown(self):
        self.shutdown_calls += 1


def _stage(redis, **kwargs):
    params = {
        "redis": redis,
        "input_streams": ["s:a", "s:b"],
        "consumer_group": "g",
        "worker_id": "w",
        "xread_block_ms": 5,
        "batch_size": 10,
    }
    params.update(kwargs)
    return RecordingMultiStage(**params)


async def _run_briefly(stage, seconds=0.05):
    task = asyncio.create_task(stage.run())
    await asyncio.sleep(seconds)
    await stage.stop()
    await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_creates_consumer_group_for_each_stream():
    redis = FakeRedis([])
    stage = _stage(redis)

    await _run_briefly(stage)

    assert redis.created == [
        ("s:a", "g", "0", True),
        ("s:b", "g", "0", True),
    ]


@pytest.mark.asyncio
async def test_processes_and_acks_each_message_on_its_source_stream():
    redis = FakeRedis(
        [
            ("s:a", [(b"1-0", {b"k": b"a"})]),
            ("s:b", [(b"2-0", {b"k": b"b"})]),
        ]
    )
    stage = _stage(redis)

    await _run_briefly(stage)

    assert stage.handled == [("s:a", b"1-0"), ("s:b", b"2-0")]
    assert redis.acked == [("s:a", b"1-0"), ("s:b", b"2-0")]


@pytest.mark.asyncio
async def test_no_ack_when_handle_returns_false():
    redis = FakeRedis([("s:a", [(b"1-0", {})])])
    stage = _stage(redis, ack_result=False)

    await _run_briefly(stage)

    assert stage.handled == [("s:a", b"1-0")]
    assert redis.acked == []


@pytest.mark.asyncio
async def test_reclaims_idle_pending_per_stream_before_new_reads():
    redis = FakeRedis(
        batches=[("s:b", [(b"2-0", {})])],
        claimed={"s:a": [[(b"1-0", {})]], "s:b": []},
    )
    stage = _stage(redis, pending_retry_idle_ms=0)

    await _run_briefly(stage)

    assert stage.handled[:2] == [("s:a", b"1-0"), ("s:b", b"2-0")]
    assert redis.acked[:2] == [("s:a", b"1-0"), ("s:b", b"2-0")]
    assert "s:a" in redis.xautoclaim_calls
    assert "s:b" in redis.xautoclaim_calls


@pytest.mark.asyncio
async def test_pre_iteration_gate_false_stops_before_read_and_runs_shutdown():
    redis = FakeRedis([("s:a", [(b"1-0", {})])])
    stage = _stage(redis, gate_result=False)

    await _run_briefly(stage)

    assert redis.xreadgroup_calls == 0
    assert stage.handled == []
    assert stage.shutdown_calls == 1
```

- [ ] **Step 2: Run the multi-stream test and verify RED**

Run:

```bash
pytest tests/unit/streaming/test_multi_stream_stage.py -q
```

Expected: fail during import because `MultiStreamStage` is not defined.

- [ ] **Step 3: Add `MultiStreamStage` beside `StreamStage`**

In `shared/streaming/stage.py`, add `MultiStreamStage` after `StreamStage`. Its public contract is:

```python
class MultiStreamStage(ABC):
    def __init__(
        self,
        *,
        redis: Any,
        input_streams: list[str],
        consumer_group: str,
        worker_id: str,
        xread_block_ms: int,
        batch_size: int,
        xreadgroup_error_sleep_seconds: float = 0.5,
        pending_retry_idle_ms: int = 60_000,
    ) -> None:
        ...

    @abstractmethod
    async def handle_message(
        self,
        stream: str | bytes,
        msg_id: bytes,
        fields: dict[bytes, bytes],
    ) -> bool:
        ...
```

Behavior must match `StreamStage` except stream-aware:

- Validate `input_streams` is non-empty and store a list copy.
- Create the same consumer group for every input stream with `mkstream=True`.
- Reclaim pending messages per input stream using `XAUTOCLAIM`.
- Read with `streams={stream: ">" for stream in self.input_streams}`.
- Call `handle_message(stream, msg_id, fields)` for every message.
- ACK with `xack(stream, consumer_group, msg_id)` using the message's source stream.
- Keep optional hooks named `on_startup`, `pre_iteration_gate`, `post_poll`, `on_shutdown`.
- Keep `stop()` as an async method that sets an internal `asyncio.Event`.
- Preserve the existing `StreamStage` implementation and tests unchanged.

- [ ] **Step 4: Run multi-stream tests and existing stream-stage tests**

Run:

```bash
pytest tests/unit/streaming/test_multi_stream_stage.py tests/unit/streaming/test_stream_stage.py -q
```

Expected: both test files pass.

- [ ] **Step 5: Run ruff on streaming files**

Run:

```bash
ruff check shared/streaming/stage.py tests/unit/streaming/test_multi_stream_stage.py tests/unit/streaming/test_stream_stage.py
```

Expected: no lint errors.

---

## Controller Integration

- [ ] **Step 1: Review worker summaries**

Confirm each worker reports:

```text
Status: DONE
Files changed: ...
Tests run: ...
Concerns: ...
```

- [ ] **Step 2: Check combined diff**

Run:

```bash
git diff --stat
git diff -- shared/execution/futures_instrument.py shared/streaming/stage.py
```

Expected: futures changes and streaming changes are independent.

- [ ] **Step 3: Run combined focused tests**

Run:

```bash
pytest tests/unit/execution/test_futures_instrument_config.py tests/unit/trading/test_futures_product_selection.py tests/unit/streaming/test_multi_stream_stage.py tests/unit/streaming/test_stream_stage.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run ruff on all touched Python files**

Run:

```bash
ruff check shared/execution/futures_instrument.py shared/streaming/stage.py services/trading/orchestrator.py services/decision_engine/main.py services/market_ingest/main.py services/futures_monitor/main.py services/order_router/main.py tests/unit/execution/test_futures_instrument_config.py tests/unit/trading/test_futures_product_selection.py tests/unit/streaming/test_multi_stream_stage.py tests/unit/streaming/test_stream_stage.py
```

Expected: no lint errors.

- [ ] **Step 5: Commit and push only after verification**

Run:

```bash
git status --short
git add docs/superpowers/plans/2026-06-27-architecture-audit-parallel-plan.md docs/superpowers/plans/2026-06-27-architecture-hardening-phase1.md shared/execution/futures_instrument.py shared/streaming/stage.py services/trading/orchestrator.py services/decision_engine/main.py services/market_ingest/main.py services/futures_monitor/main.py services/order_router/main.py tests/unit/execution/test_futures_instrument_config.py tests/unit/trading/test_futures_product_selection.py tests/unit/streaming/test_multi_stream_stage.py tests/unit/streaming/test_stream_stage.py
git commit -m "Harden futures instrument and stream stage architecture"
git push origin architecture-hardening-phase1
```

Expected: remote branch is pushed for review or follow-up merge.
