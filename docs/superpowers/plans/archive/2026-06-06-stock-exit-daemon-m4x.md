# Stock Exit Daemon (M4-X) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A shadow-first, default-off stock exit daemon that scans open positions (written by M4-O), runs `ThreeStageExit`, paper-sells, closes positions, and feeds realized PnL back to `RuntimeRiskState` — activating M4-R's currently-inert PnL-dependent filters.

**Architecture:** A self-contained timer-loop daemon (`services/stock_exit/`, mirroring M4-P's structure — NOT a `StreamStage`). Per cycle it reconstructs `Position` objects from the `trading:stock:positions` hash, tracks/persists each running high, runs the reused `ThreeStageExit` (with one new additive `eod_exempt_maximize` config flag honoring the no-flatten policy), then for each exit signal: `VirtualBroker` SELL → `FillLogger` exit fill → HDEL close → `RuntimeRiskState.record_trade`. Heavy logic is reused unchanged except the one backward-compatible `ThreeStageExitConfig` flag.

**Tech Stack:** Python 3.11+, asyncio, `redis.asyncio` (DB 1), `fakeredis.aioredis` (tests), pytest.

**Spec:** `docs/superpowers/specs/2026-06-06-stock-exit-daemon-m4x-design.md`

**PR strategy:** Land as **one PR** (`feat/stock-exit-daemon-m4x`). The e2e test (Task 5) spans the daemon + the M4-R re-entry seam.

**Out of scope (do not implement):** BEAR_EXIT / regime / `market_state` wiring (v1 `enable_bear_exit=false`, pass `market_state=None`), per-strategy exit configs (v1 single config), partial exits (full-close only), real KIS sell + stock live guard, stock short exit, `FillLogger` exit_reason/pnl fields, orchestrator adopting `eod_exempt_maximize`, the `shared/streaming/daemon_entrypoint.py` DRY extraction.

---

## File Structure

**Create:**
- `services/stock_exit/__init__.py` — empty package marker.
- `services/stock_exit/positions.py` — `parse_position_record`, `position_from_record`, `record_with_high_water` (codec: M4-O hash record ⇄ `Position`, with the `opened_at_ms` guard).
- `services/stock_exit/daemon.py` — `StockExitDaemon` (run_cycle + execute + run loop).
- `services/stock_exit/main.py` — flag-gated entrypoint.
- `config/stock_exit.yaml` — `stock_exit:` section (ThreeStageExitConfig values, `eod_exempt_maximize: true`, `enable_bear_exit: false`).
- `deploy/systemd/kis-stock-exit-daemon.service` — disabled unit.
- `tests/unit/strategy/exit/test_three_stage_eod_exempt.py`
- `tests/unit/stock_exit/__init__.py`, `tests/unit/stock_exit/test_positions.py`, `test_daemon.py`, `test_entrypoint.py`
- `tests/integration/test_stock_exit_pipeline.py`

**Modify:**
- `shared/strategy/exit/three_stage.py` — add `eod_exempt_maximize` field to `ThreeStageExitConfig` (+ `from_dict`/`to_dict`/docstring) and one condition in `_check_position`.

---

## Task 1: `eod_exempt_maximize` flag on ThreeStageExit (no-flatten for MAXIMIZE)

**Files:**
- Modify: `shared/strategy/exit/three_stage.py`
- Test: `tests/unit/strategy/exit/test_three_stage_eod_exempt.py`

This is the only shared-code change: a backward-compatible flag (default `False` = current behavior). When `True`, MAXIMIZE-stage positions are exempt from the unconditional EOD_CLOSE.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/strategy/exit/test_three_stage_eod_exempt.py`:

```python
"""eod_exempt_maximize: MAXIMIZE positions skip EOD_CLOSE; others still close."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason
from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig

# 15:30 KST = 06:30 UTC (after the 15:15 eod_close_time).
_EOD_NOW = datetime(2026, 6, 9, 6, 30, tzinfo=UTC)


def _pos(entry: float = 10000.0) -> Position:
    return Position(
        id="p1", code="005930", name="", side=PositionSide.LONG,
        quantity=10, entry_price=entry,
    )


@pytest.mark.asyncio
async def test_maximize_exempt_from_eod_when_flag_set() -> None:
    strat = ThreeStageExit(
        ThreeStageExitConfig(eod_exempt_maximize=True, enable_bear_exit=False)
    )
    # +5% -> MAXIMIZE; price at the high so trailing stop is NOT hit.
    md = {"005930": {"close": 10500.0}}
    with patch("shared.strategy.exit.three_stage.is_trading_day_kst", return_value=True):
        sig = await strat._check_position(
            position=_pos(), market_data=md, market_state=None, now=_EOD_NOW
        )
    # MAXIMIZE exempt -> no EOD_CLOSE; at-high -> no trailing -> held (None).
    assert sig is None or sig.reason != ExitReason.EOD_CLOSE


@pytest.mark.asyncio
async def test_survival_still_eod_closed_with_flag() -> None:
    strat = ThreeStageExit(
        ThreeStageExitConfig(eod_exempt_maximize=True, enable_bear_exit=False)
    )
    md = {"005930": {"close": 10050.0}}  # +0.5% -> SURVIVAL
    with patch("shared.strategy.exit.three_stage.is_trading_day_kst", return_value=True):
        sig = await strat._check_position(
            position=_pos(), market_data=md, market_state=None, now=_EOD_NOW
        )
    assert sig is not None and sig.reason == ExitReason.EOD_CLOSE


@pytest.mark.asyncio
async def test_maximize_eod_closed_when_flag_default_false() -> None:
    # Backward-compat: default False -> MAXIMIZE is still force-closed at EOD.
    strat = ThreeStageExit(ThreeStageExitConfig(enable_bear_exit=False))
    md = {"005930": {"close": 10500.0}}  # +5% -> MAXIMIZE
    with patch("shared.strategy.exit.three_stage.is_trading_day_kst", return_value=True):
        sig = await strat._check_position(
            position=_pos(), market_data=md, market_state=None, now=_EOD_NOW
        )
    assert sig is not None and sig.reason == ExitReason.EOD_CLOSE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/strategy/exit/test_three_stage_eod_exempt.py -v`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'eod_exempt_maximize'`.

- [ ] **Step 3: Implement**

In `shared/strategy/exit/three_stage.py`, in the `ThreeStageExitConfig` dataclass, add the field after `enable_bear_exit` (around line 115):

```python
    # BEAR 시장 청산
    enable_bear_exit: bool = True

    # EOD 면제: True면 MAXIMIZE stage 포지션은 EOD_CLOSE 면제(추세 종목 overnight 보유).
    # 기본 False = 기존 동작(전 stage 강제청산) 보존.
    eod_exempt_maximize: bool = False
```

In `ThreeStageExitConfig.from_dict` (around line 158-170), add to the returned `cls(...)`:

```python
            enable_bear_exit=data.get("enable_bear_exit", True),
            eod_exempt_maximize=data.get("eod_exempt_maximize", False),
        )
```

In `ThreeStageExitConfig.to_dict` (around line 172-190), add the key (place it next to the other keys, before the closing brace):

```python
            "enable_bear_exit": self.enable_bear_exit,
            "eod_exempt_maximize": self.eod_exempt_maximize,
        }
```
(Read the actual `to_dict` body first; append the `eod_exempt_maximize` entry consistently with the existing keys — `enable_bear_exit` may or may not already be in `to_dict`; if `enable_bear_exit` is absent from `to_dict`, add both for completeness.)

In `_check_position`, find the EOD block (around line 388-401). The `stage` variable is already computed just above (line 386: `stage = self._determine_stage(position, profit_pct)`). Change the EOD condition to exempt MAXIMIZE when the flag is set:

```python
        # 1. EOD 체크 (최우선) — eod_exempt_maximize 시 MAXIMIZE는 면제(no-flatten)
        close_time = effective_close_time(self.config.eod_close_time)
        eod_due = is_trading_day_kst(now) and to_kst(now).time() >= close_time
        maximize_exempt = (
            self.config.eod_exempt_maximize and stage == PositionState.MAXIMIZE
        )
        if eod_due and not maximize_exempt:
            return self._create_exit_signal(
                position=position,
                current_price=current_price,
                profit_pct=profit_pct,
                profit_amount=profit_amount,
                reason=ExitReason.EOD_CLOSE,
                priority=1,
                stage=stage,
                high_since_entry=high_since_entry,
                holding_minutes=holding_minutes,
            )
```
(`PositionState` is already imported at line 40.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/strategy/exit/test_three_stage_eod_exempt.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Regression — existing three_stage tests unaffected**

Run: `.venv/bin/pytest tests/ -k three_stage -q`
Expected: all PASS (default `False` preserves current behavior).

- [ ] **Step 6: Commit**

```bash
.venv/bin/black shared/strategy/exit/three_stage.py tests/unit/strategy/exit/test_three_stage_eod_exempt.py
.venv/bin/ruff check --fix shared/strategy/exit/three_stage.py tests/unit/strategy/exit/test_three_stage_eod_exempt.py
git add shared/strategy/exit/three_stage.py tests/unit/strategy/exit/test_three_stage_eod_exempt.py
git commit -m "feat(m4-x): eod_exempt_maximize flag — MAXIMIZE positions skip EOD_CLOSE (no-flatten)"
```

---

## Task 2: Position codec — reconstruct from M4-O record + opened_at_ms guard + high_water

**Files:**
- Create: `services/stock_exit/__init__.py` (empty), `tests/unit/stock_exit/__init__.py` (empty)
- Create: `services/stock_exit/positions.py`
- Test: `tests/unit/stock_exit/test_positions.py`

M4-O writes `trading:stock:positions` hash, field=code, value JSON `{code, entry_price, quantity, opened_at_ms, state, signal_id}`. M4-X reconstructs a `Position`, restores the running high (`high_water`/`low_water`) it persists, and skips foreign records (orchestrator entries lack `opened_at_ms`).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_exit/test_positions.py`:

```python
"""Position codec: M4-O record -> Position, opened_at_ms guard, high_water round-trip."""

from __future__ import annotations

import json

from shared.models.position import PositionSide, PositionState
from services.stock_exit.positions import (
    parse_position_record,
    position_from_record,
    record_with_high_water,
)


def _m4o_record(code: str = "005930") -> dict[str, object]:
    return {
        "code": code,
        "entry_price": 71000.0,
        "quantity": 10,
        "opened_at_ms": 1_700_000_000_000,
        "state": "survival",
        "signal_id": "sig-1",
    }


def test_parse_accepts_m4o_record() -> None:
    rec = parse_position_record(json.dumps(_m4o_record()).encode())
    assert rec is not None
    assert rec["code"] == "005930"


def test_parse_skips_foreign_record_without_opened_at_ms() -> None:
    # An orchestrator PositionTracker entry uses entry_time, not opened_at_ms.
    foreign = {"id": "uuid", "code": "005930", "entry_price": 71000.0,
               "quantity": 10, "entry_time": "2026-06-06T00:00:00+00:00"}
    assert parse_position_record(json.dumps(foreign)) is None


def test_parse_skips_garbage() -> None:
    assert parse_position_record(b"not-json") is None


def test_position_from_record_builds_long_position() -> None:
    pos = position_from_record(_m4o_record(), fee_rate=0.003)
    assert pos.code == "005930"
    assert pos.side == PositionSide.LONG
    assert pos.quantity == 10
    assert pos.entry_price == 71000.0
    assert pos.state == PositionState.SURVIVAL
    assert pos.entry_time.tzinfo is not None
    # No persisted high_water -> __post_init__ seeds high/low to entry.
    assert pos.highest_price == 71000.0
    assert pos.lowest_price == 71000.0
    assert pos.fee_rate == 0.003


def test_high_water_round_trip() -> None:
    rec = _m4o_record()
    pos = position_from_record(rec, fee_rate=0.003)
    pos.update_price(73000.0)  # new high
    raw = record_with_high_water(rec, pos)
    rec2 = parse_position_record(raw)
    assert rec2 is not None
    restored = position_from_record(rec2, fee_rate=0.003)
    assert restored.highest_price == 73000.0  # trailing survives restart
    # Original M4-O fields preserved.
    assert restored.entry_price == 71000.0
    assert restored.quantity == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_exit/test_positions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.stock_exit.positions'`.

- [ ] **Step 3: Implement**

Create `services/stock_exit/__init__.py` (empty), `tests/unit/stock_exit/__init__.py` (empty), and `services/stock_exit/positions.py`:

```python
"""Codec between the M4-O position hash record and a `Position`.

M4-O (services/stock_order_router) writes ``trading:stock:positions`` hash:
field = code, value = JSON ``{code, entry_price, quantity, opened_at_ms, state,
signal_id}``. M4-X reconstructs a `Position`, restores the running extremes
(``high_water``/``low_water``) it persists each cycle, and skips foreign records
(the orchestrator's PositionTracker uses ``entry_time``, not ``opened_at_ms``).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from shared.models.position import Position, PositionSide, PositionState

_STATE_BY_VALUE = {s.value: s for s in PositionState}


def parse_position_record(value: Any) -> dict[str, Any] | None:
    """Decode a hash value to a dict, or None for unusable/foreign records.

    Returns None unless the record carries the M4-O signature field
    ``opened_at_ms`` (and ``code``) — this skips the orchestrator's
    ``entry_time``-keyed entries that may share the same hash during the
    strangler period.
    """
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="replace")
    try:
        rec = json.loads(value)
    except (TypeError, ValueError):
        return None
    if not isinstance(rec, dict) or "opened_at_ms" not in rec or "code" not in rec:
        return None
    return rec


def position_from_record(rec: dict[str, Any], *, fee_rate: float) -> Position:
    """Build a LONG `Position` from an M4-O record (+ persisted high/low if present)."""
    opened_ms = int(rec["opened_at_ms"])
    entry_time = datetime.fromtimestamp(opened_ms / 1000, tz=UTC)
    state = _STATE_BY_VALUE.get(
        str(rec.get("state", "survival")).lower(), PositionState.SURVIVAL
    )
    pos = Position(
        id=str(rec.get("signal_id") or rec["code"]),
        code=str(rec["code"]),
        name=str(rec.get("name", "")),
        side=PositionSide.LONG,
        quantity=int(rec["quantity"]),
        entry_price=float(rec["entry_price"]),
        entry_time=entry_time,
        state=state,
        fee_rate=fee_rate,
    )
    # __post_init__ seeds high/low to entry; restore persisted extremes if any.
    if rec.get("high_water") is not None:
        pos.highest_price = float(rec["high_water"])
    if rec.get("low_water") is not None:
        pos.lowest_price = float(rec["low_water"])
    return pos


def record_with_high_water(rec: dict[str, Any], pos: Position) -> str:
    """Re-serialize the record with the position's running extremes (restart recovery)."""
    return json.dumps(
        {**rec, "high_water": pos.highest_price, "low_water": pos.lowest_price}
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_exit/test_positions.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
.venv/bin/black services/stock_exit tests/unit/stock_exit
.venv/bin/ruff check --fix services/stock_exit tests/unit/stock_exit
git add services/stock_exit/__init__.py services/stock_exit/positions.py tests/unit/stock_exit/
git commit -m "feat(m4-x): position codec (M4-O record <-> Position, opened_at_ms guard, high_water)"
```

---

## Task 3: `StockExitDaemon` (scan cycle + execute + run loop)

**Files:**
- Create: `services/stock_exit/daemon.py`
- Test: `tests/unit/stock_exit/test_daemon.py`

The daemon class. `run_cycle()` is stateless across cycles (high_water is persisted to and restored from the hash each cycle). `_execute_exit` does SELL → HDEL → record_trade/win/loss → log_fill.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_exit/test_daemon.py`:

```python
"""StockExitDaemon: stop-loss -> SELL + HDEL + record_loss + exit fill; not-filled -> no close."""

from __future__ import annotations

import json

import fakeredis.aioredis
import pytest

from services.stock_exit.daemon import StockExitDaemon
from shared.execution.fill_logger import FillLogger
from shared.paper.broker import VirtualBroker
from shared.risk.runtime_state import RuntimeRiskState
from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig


def _seed_record(code: str = "005930", entry: float = 71000.0) -> dict[str, object]:
    return {
        "code": code,
        "entry_price": entry,
        "quantity": 10,
        "opened_at_ms": 1_700_000_000_000,
        "state": "survival",
        "signal_id": f"sig-{code}",
    }


def _build_daemon(redis, *, broker=None, fill_logger=None) -> StockExitDaemon:
    exit_strategy = ThreeStageExit(
        ThreeStageExitConfig(enable_bear_exit=False, eod_exempt_maximize=True)
    )
    return StockExitDaemon(
        redis=redis,
        feed=_FakeFeed(),
        exit_strategy=exit_strategy,
        broker=broker or VirtualBroker(slippage_rate=0.0001),
        fill_logger=fill_logger
        or FillLogger(
            redis=redis, stream="order.fill.stock.shadow", maxlen=1000, asset_class="stock"
        ),
        runtime_state=RuntimeRiskState(redis=redis, asset_class="stock"),
        positions_key="trading:stock:positions",
        interval_seconds=1.0,
    )


class _FakeFeed:
    """Minimal StreamConsumerFeed stand-in: a settable price cache."""

    def __init__(self) -> None:
        self.prices: dict[str, dict[str, float]] = {}

    def update_symbols(self, symbols: list[str]) -> None:  # noqa: D401
        pass

    async def get_current_price(self, symbol: str) -> dict[str, float]:
        return dict(self.prices.get(symbol, {}))

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


@pytest.mark.asyncio
async def test_stop_loss_sells_closes_and_records_loss() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    # -2% from 71000 = 69580 < stop_loss_pct (-1.5%) -> STOP_LOSS.
    daemon.feed.prices["005930"] = {"close": 69580.0}

    await daemon.run_cycle()

    # Position closed (HDEL).
    assert not await redis.hexists("trading:stock:positions", "005930")
    # Exit fill published with trade_role=exit, side=SELL.
    fills = await redis.xrange("order.fill.stock.shadow")
    assert len(fills) == 1
    assert fills[0][1][b"side"] == b"SELL"
    assert fills[0][1][b"trade_role"] == b"exit"
    # Realized loss fed to risk state.
    snap = await daemon.runtime_state.snapshot()
    assert snap.daily_pnl_krw < 0
    assert snap.consecutive_losses == 1


@pytest.mark.asyncio
async def test_no_price_no_action() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    # No price in feed -> no exit, position stays.
    await daemon.run_cycle()
    assert await redis.hexists("trading:stock:positions", "005930")
    assert await redis.xrange("order.fill.stock.shadow") == []


@pytest.mark.asyncio
async def test_unfilled_sell_does_not_close() -> None:
    redis = fakeredis.aioredis.FakeRedis()

    class _UnfilledBroker:
        async def submit_order(self, **kwargs):
            class _O:
                filled = False
                rejection_reason = "no_fill"
                fill_price = None
                order_id = ""
            return _O()

    daemon = _build_daemon(redis, broker=_UnfilledBroker())
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 69580.0}  # would trigger stop
    await daemon.run_cycle()
    # SELL not filled -> position NOT closed, retry next cycle.
    assert await redis.hexists("trading:stock:positions", "005930")
    assert await redis.xrange("order.fill.stock.shadow") == []


@pytest.mark.asyncio
async def test_high_water_persisted() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 72000.0}  # +1.4% -> SURVIVAL, no exit
    await daemon.run_cycle()
    raw = await redis.hget("trading:stock:positions", "005930")
    rec = json.loads(raw)
    assert rec["high_water"] == 72000.0  # running high persisted for restart
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_exit/test_daemon.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.stock_exit.daemon'`.

- [ ] **Step 3: Implement**

Create `services/stock_exit/daemon.py`:

```python
"""Stock exit daemon (M4-X, timer-loop, shadow-first).

Scans open stock positions from ``trading:stock:positions`` (written by M4-O),
tracks each running high, runs ThreeStageExit, paper-sells exits, closes
positions (HDEL), and feeds realized PnL to RuntimeRiskState — activating M4-R's
PnL-dependent filters. Not a StreamStage (no upstream exit-candidate stream);
a decision-cadence loop like the M4-P StockStrategyDaemon.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import Any

from services.stock_exit.positions import (
    parse_position_record,
    position_from_record,
    record_with_high_water,
)
from shared.paper.models import OrderSide, OrderType

logger = logging.getLogger(__name__)


class StockExitDaemon:
    """Decision-cadence loop that exits open stock positions via ThreeStageExit."""

    def __init__(
        self,
        *,
        redis: Any,
        feed: Any,
        exit_strategy: Any,
        broker: Any,
        fill_logger: Any,
        runtime_state: Any,
        positions_key: str,
        interval_seconds: float,
        now_fn: Any = lambda: datetime.now(UTC),
    ) -> None:
        self.redis = redis
        self.feed = feed
        self.exit_strategy = exit_strategy
        self.broker = broker
        self.fill_logger = fill_logger
        self.runtime_state = runtime_state
        self.positions_key = positions_key
        self.interval_seconds = interval_seconds
        self.now_fn = now_fn
        self.fee_rate = float(getattr(exit_strategy.config, "fee_rate", 0.003))
        self._stop = asyncio.Event()

    async def run(self) -> None:
        await self.feed.start()
        try:
            while not self._stop.is_set():
                try:
                    await self.run_cycle()
                except Exception:
                    logger.exception("stock exit cycle failed; continuing")
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.interval_seconds
                    )
        finally:
            await self.feed.stop()

    async def stop(self) -> None:
        self._stop.set()

    async def run_cycle(self) -> None:
        raw = await self.redis.hgetall(self.positions_key)
        positions = []
        recs: dict[str, dict[str, Any]] = {}
        for value in raw.values():
            rec = parse_position_record(value)
            if rec is None:
                continue  # skip foreign/orchestrator entries (no opened_at_ms)
            pos = position_from_record(rec, fee_rate=self.fee_rate)
            recs[pos.code] = rec
            positions.append(pos)

        if not positions:
            return

        self.feed.update_symbols([p.code for p in positions])

        market_data: dict[str, dict[str, Any]] = {}
        for pos in positions:
            price = await self.feed.get_current_price(pos.code)
            close = price.get("close")
            if close is None:
                continue
            pos.update_price(float(close))  # raises high/low
            await self.redis.hset(
                self.positions_key,
                pos.code,
                record_with_high_water(recs[pos.code], pos),
            )
            market_data[pos.code] = {"close": float(close)}

        signals = await self.exit_strategy.scan_positions(
            positions, market_data, market_state=None
        )
        pos_by_code = {p.code: p for p in positions}
        for sig in signals:
            await self._execute_exit(sig, pos_by_code.get(sig.code))

    async def _execute_exit(self, sig: Any, pos: Any) -> None:
        if pos is None:
            return
        qty = int(sig.quantity) if getattr(sig, "quantity", 0) else pos.quantity
        current = float(sig.current_price) if sig.current_price > 0 else pos.current_price

        order = await self.broker.submit_order(
            symbol=sig.code,
            side=OrderSide.SELL,
            quantity=qty,
            price=current,
            order_type=OrderType.MARKET,
            market_price=current,
        )
        if not order.filled:
            logger.info(
                "stock exit not filled code=%s reason=%s", sig.code, order.rejection_reason
            )
            return  # leave position open, retry next cycle

        filled = float(order.fill_price or current)
        gross = (filled - pos.entry_price) * qty
        round_trip_fee = (pos.entry_price + filled) * qty * (pos.fee_rate / 2)
        pnl = gross - round_trip_fee

        # HDEL first (authoritative close — prevents re-sell / double PnL on retry).
        await self.redis.hdel(self.positions_key, sig.code)
        await self.runtime_state.record_trade(pnl_krw=pnl)
        if pnl > 0:
            await self.runtime_state.record_win()
        else:
            await self.runtime_state.record_loss()

        now_ms = int(self.now_fn().timestamp() * 1000)
        reason = getattr(sig.reason, "value", str(sig.reason))
        try:
            await self.fill_logger.log_fill(
                signal_id=pos.id,
                order_id=order.order_id or "",
                symbol=sig.code,
                side="SELL",
                order_type="market",
                requested_price=current,
                filled_price=filled,
                tick_size_points=0.0,
                slippage_ticks=abs(filled - current),
                quantity=qty,
                requested_at_ms=now_ms,
                filled_at_ms=now_ms,
                venue="KRX",
                trade_role="exit",
            )
        except Exception:
            logger.warning(
                "exit fill log failed code=%s (position already closed)",
                sig.code,
                exc_info=True,
            )
        logger.info("stock exit code=%s reason=%s pnl=%.0f", sig.code, reason, pnl)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_exit/test_daemon.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
.venv/bin/black services/stock_exit tests/unit/stock_exit
.venv/bin/ruff check --fix services/stock_exit tests/unit/stock_exit
.venv/bin/mypy services/stock_exit/daemon.py services/stock_exit/positions.py
git add services/stock_exit/daemon.py tests/unit/stock_exit/test_daemon.py
git commit -m "feat(m4-x): StockExitDaemon (scan -> SELL -> HDEL close -> RuntimeRiskState PnL)"
```

---

## Task 4: Flag-gated entrypoint + config + systemd

**Files:**
- Create: `services/stock_exit/main.py`
- Create: `config/stock_exit.yaml`
- Create: `deploy/systemd/kis-stock-exit-daemon.service`
- Test: `tests/unit/stock_exit/test_entrypoint.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_exit/test_entrypoint.py`:

```python
"""M4-X flag routing: off -> inert; fill-stream mapping; config loads."""

from __future__ import annotations

import asyncio

import pytest

import services.stock_exit.main as m


def test_resolve_mode_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STOCK_EXIT_DAEMON", raising=False)
    assert m._resolve_mode() == "off"


def test_fill_stream_for() -> None:
    assert m._fill_stream_for("shadow") == "order.fill.stock.shadow"
    assert m._fill_stream_for("off") == "order.fill.stock"


def test_off_mode_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_EXIT_DAEMON", "off")
    assert asyncio.run(m._build_and_run()) == 0


def test_stock_exit_config_loads() -> None:
    from shared.config.loader import ConfigLoader
    from shared.strategy.exit.three_stage import ThreeStageExitConfig

    raw = ConfigLoader.load("stock_exit.yaml").get("stock_exit", {})
    cfg = ThreeStageExitConfig.from_dict(raw)
    assert cfg.eod_exempt_maximize is True
    assert cfg.enable_bear_exit is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_exit/test_entrypoint.py -v`
Expected: FAIL — `AttributeError: ... '_resolve_mode'`.

- [ ] **Step 3: Implement**

Create `config/stock_exit.yaml`:

```yaml
# Stock exit (M4-X — StockExitDaemon) ThreeStageExit config.
# Single config for all stock positions (v1; per-strategy is a follow-up).
stock_exit:
  stop_loss_pct: -0.015
  breakeven_threshold_pct: 0.015
  maximize_threshold_pct: 0.03
  trailing_stop_pct: -0.03
  overshoot_threshold_pct: 0.07
  overshoot_trailing_pct: -0.015
  time_cut_minutes: 20
  eod_close_hour: 15
  eod_close_minute: 15
  eod_exempt_maximize: true     # MAXIMIZE positions ride overnight (no-flatten)
  enable_bear_exit: false       # v1: no regime wiring
  fee_rate: 0.003
```

Create `services/stock_exit/main.py`:

```python
"""Stock exit daemon entrypoint (flag-gated, shadow-first, default-off).

off (default): inert — log + close redis + return 0, constructing nothing.
shadow:        full wiring to order.fill.stock.shadow.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket

logger = logging.getLogger(__name__)


def _resolve_mode() -> str:
    """Return the daemon mode from the env var (default 'off')."""
    return os.getenv("STOCK_EXIT_DAEMON", "off").strip().lower()


def _fill_stream_for(mode: str) -> str:
    """shadow -> suffixed exit-fill stream; else reserved live (unsuffixed)."""
    return "order.fill.stock.shadow" if mode == "shadow" else "order.fill.stock"


async def _build_and_run() -> int:
    import signal as signal_mod

    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()
    if mode != "shadow":
        logger.info("STOCK_EXIT_DAEMON=%s (off) — daemon inert, exiting", mode)
        await redis_client.aclose()
        return 0

    from services.stock_exit.daemon import StockExitDaemon
    from services.trading.stream_consumer_feed import StreamConsumerFeed
    from shared.config.loader import ConfigLoader
    from shared.execution.fill_logger import FillLogger
    from shared.paper.broker import VirtualBroker
    from shared.risk.runtime_state import RuntimeRiskState
    from shared.storage import SQLiteRuntimeLedger
    from shared.storage.config import StorageConfig
    from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig

    raw = ConfigLoader.load("stock_exit.yaml").get("stock_exit", {})
    exit_strategy = ThreeStageExit(ThreeStageExitConfig.from_dict(raw))

    tick_stream = os.environ.get("STOCK_TICK_STREAM", "market:ticks")
    feed = StreamConsumerFeed(redis=redis_client, stream=tick_stream)

    fill_stream = os.environ.get("STOCK_FILL_STREAM", _fill_stream_for(mode))
    positions_key = os.environ.get("STOCK_POSITIONS_KEY", "trading:stock:positions")
    interval = float(os.environ.get("STOCK_EXIT_INTERVAL", "5"))

    runtime_ledger = None
    storage_config = StorageConfig.load_or_default()
    if storage_config.runtime_storage.backend == "sqlite":
        runtime_ledger = SQLiteRuntimeLedger(storage_config.runtime_storage.sqlite)

    fill_logger = FillLogger(
        redis=redis_client,
        archive_client=None,
        stream=fill_stream,
        maxlen=10_000,
        batch_size=10,
        runtime_ledger=runtime_ledger,
        asset_class="stock",
    )
    slippage_rate = float(os.environ.get("STOCK_PAPER_SLIPPAGE_RATE", "0.0001"))
    broker = VirtualBroker(slippage_rate=slippage_rate)
    runtime_state = RuntimeRiskState(redis=redis_client, asset_class="stock")

    daemon = StockExitDaemon(
        redis=redis_client,
        feed=feed,
        exit_strategy=exit_strategy,
        broker=broker,
        fill_logger=fill_logger,
        runtime_state=runtime_state,
        positions_key=positions_key,
        interval_seconds=interval,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    worker = f"stock-exit-{socket.gethostname()}-{os.getpid()}"
    logger.info("stock exit daemon starting worker=%s interval=%.1fs", worker, interval)
    try:
        await daemon.run()
    finally:
        await fill_logger.flush()
        await redis_client.aclose()
        if runtime_ledger is not None:
            runtime_ledger.close()
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
```

Create `deploy/systemd/kis-stock-exit-daemon.service`:

```ini
[Unit]
Description=KIS Stock Exit Daemon (trading:stock:positions -> ThreeStageExit -> paper SELL + close + PnL feedback)
After=network-online.target redis-server.service
Wants=network-online.target
Requires=redis-server.service

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/project/kis_unified_sts
EnvironmentFile=/home/deploy/project/kis_unified_sts/.env
Environment=STOCK_EXIT_DAEMON=shadow
ExecStart=/home/deploy/project/kis_unified_sts/.venv/bin/python -m services.stock_exit.main
Restart=on-failure
RestartSec=10s
TimeoutStopSec=30s
KillSignal=SIGTERM

# Delivered DISABLED. Enabling is an operator step (shadow validation gate).
[Install]
WantedBy=multi-user.target
```

Note: confirm `ConfigLoader.load("stock_exit.yaml")` resolves the new top-level `config/stock_exit.yaml` (the loader resolves filenames against the config dir, as risk_filter/order_router do with `risk.yaml`/`execution.yaml`). If it cannot find it, place the file where `ConfigLoader` looks and adjust the filename argument — do NOT hardcode a path.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_exit/test_entrypoint.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
.venv/bin/black services/stock_exit tests/unit/stock_exit
.venv/bin/ruff check --fix services/stock_exit tests/unit/stock_exit
.venv/bin/mypy services/stock_exit/main.py
git add services/stock_exit/main.py config/stock_exit.yaml deploy/systemd/kis-stock-exit-daemon.service tests/unit/stock_exit/test_entrypoint.py
git commit -m "feat(m4-x): flag-gated entrypoint + stock_exit config + disabled systemd unit"
```

---

## Task 5: e2e integration — M4-O open → M4-X exit → M4-R re-entry + PnL feedback

**Files:**
- Test: `tests/integration/test_stock_exit_pipeline.py`

Proves the lifecycle loop: a position opened (as M4-O would) is exited by M4-X (fill + HDEL + PnL feedback), and afterward M4-R's `OpenPositionFilter` sees the code as free (re-entry re-enabled), while `RuntimeRiskState` reflects the realized loss (M4-R MDD/consecutive-loss now have data).

- [ ] **Step 1: Write the test**

Create `tests/integration/test_stock_exit_pipeline.py`:

```python
"""e2e: M4-O-style open position -> M4-X exit -> close + PnL feedback + re-entry freed."""

from __future__ import annotations

import json

import fakeredis
import fakeredis.aioredis
import pytest

from services.stock_exit.daemon import StockExitDaemon
from shared.execution.fill_logger import FillLogger
from shared.paper.broker import VirtualBroker
from shared.risk.runtime_state import RuntimeRiskState
from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig


class _FakeFeed:
    def __init__(self) -> None:
        self.prices: dict[str, dict[str, float]] = {}

    def update_symbols(self, symbols: list[str]) -> None:
        pass

    async def get_current_price(self, symbol: str) -> dict[str, float]:
        return dict(self.prices.get(symbol, {}))

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


@pytest.mark.asyncio
async def test_open_exit_close_and_reentry_freed() -> None:
    server = fakeredis.FakeServer()
    redis = fakeredis.aioredis.FakeRedis(server=server, db=1)
    sync_redis = fakeredis.FakeStrictRedis(server=server, db=1)
    positions_key = "trading:stock:positions"

    # M4-O opened position (its exact record schema).
    await redis.hset(
        positions_key,
        "005930",
        json.dumps({
            "code": "005930", "entry_price": 71000.0, "quantity": 10,
            "opened_at_ms": 1_700_000_000_000, "state": "survival", "signal_id": "sig-1",
        }),
    )

    # M4-R OpenPositionFilter provider sees the open position (re-entry blocked).
    def _has_open_position(code: str) -> bool:
        return bool(sync_redis.hexists(positions_key, code))

    assert _has_open_position("005930") is True

    feed = _FakeFeed()
    feed.prices["005930"] = {"close": 69580.0}  # -2% -> STOP_LOSS

    daemon = StockExitDaemon(
        redis=redis,
        feed=feed,
        exit_strategy=ThreeStageExit(
            ThreeStageExitConfig(enable_bear_exit=False, eod_exempt_maximize=True)
        ),
        broker=VirtualBroker(slippage_rate=0.0001),
        fill_logger=FillLogger(
            redis=redis, stream="order.fill.stock.shadow", maxlen=1000, asset_class="stock"
        ),
        runtime_state=RuntimeRiskState(redis=redis, asset_class="stock"),
        positions_key=positions_key,
        interval_seconds=1.0,
    )

    await daemon.run_cycle()

    # Exit fill published.
    fills = await redis.xrange("order.fill.stock.shadow")
    assert len(fills) == 1 and fills[0][1][b"trade_role"] == b"exit"
    # Position closed -> re-entry freed (M4-R provider now returns False).
    assert _has_open_position("005930") is False
    # Realized loss fed to the shared risk state M4-R reads.
    snap = await RuntimeRiskState(redis=redis, asset_class="stock").snapshot()
    assert snap.daily_pnl_krw < 0
    assert snap.consecutive_losses == 1
```

- [ ] **Step 2: Run + iterate**

Run: `.venv/bin/pytest tests/integration/test_stock_exit_pipeline.py -v`
Expected: PASS (1 passed). If the sync/async fakeredis server sharing API differs by version, mirror the working pattern from `tests/integration/test_stock_execution_pipeline.py` (the M4-R/O e2e uses the same `FakeServer()` + `db=1` approach).

- [ ] **Step 3: Commit**

```bash
.venv/bin/black tests/integration/test_stock_exit_pipeline.py
.venv/bin/ruff check --fix tests/integration/test_stock_exit_pipeline.py
git add tests/integration/test_stock_exit_pipeline.py
git commit -m "test(m4-x): e2e open -> exit -> close + PnL feedback + re-entry freed"
```

---

## Task 6: Full gate + lint + PR

- [ ] **Step 1: Lint/format/type**

```bash
.venv/bin/black services/stock_exit tests/unit/stock_exit tests/integration/test_stock_exit_pipeline.py shared/strategy/exit/three_stage.py tests/unit/strategy/exit/test_three_stage_eod_exempt.py
.venv/bin/ruff check services/stock_exit tests/unit/stock_exit tests/integration/test_stock_exit_pipeline.py
.venv/bin/mypy services/stock_exit
```
Expected: clean (mypy may warn on the known `Redis[Any].aclose` stub gap in `main.py` — acceptable, matches every other service entrypoint).

- [ ] **Step 2: Targeted + regression**

```bash
.venv/bin/pytest tests/unit/stock_exit tests/unit/strategy/exit/test_three_stage_eod_exempt.py tests/integration/test_stock_exit_pipeline.py -v
.venv/bin/pytest tests/ -k three_stage -q
```
Expected: all PASS (incl. three_stage regression — `eod_exempt_maximize` default False preserves behavior).

- [ ] **Step 3: Full gate (CI parity)**

```bash
.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance && .venv/bin/pytest tests/ -m serial -q
```
Expected: green.

- [ ] **Step 4: Push + PR**

```bash
git push -u origin feat/stock-exit-daemon-m4x
gh pr create --base main --head feat/stock-exit-daemon-m4x \
  --title "feat(m4-x): stock exit daemon (ThreeStageExit, shadow-first, default off)" \
  --body "$(cat <<'EOF'
## What
The stock EXIT half of the decoupled pipeline (M4-O open ↔ M4-X close symmetry):
a shadow-first, default-off timer-loop daemon that scans `trading:stock:positions`,
runs `ThreeStageExit` (stop/breakeven/trailing/time_cut/EOD), paper-sells exits via
`VirtualBroker`, closes positions (HDEL), and feeds realized PnL to `RuntimeRiskState`
— activating M4-R's previously-inert MDD/consecutive-loss filters. Flag
`STOCK_EXIT_DAEMON` default off; systemd unit disabled.

## Why
M4-R/O built entry-only execution; positions accumulated with no exit. M4-X closes
the lifecycle and closes the risk loop (realized PnL → M4-R filters). Implements the
documented no-flatten policy via a new backward-compatible `eod_exempt_maximize`
config flag (MAXIMIZE positions ride overnight; default False preserves orchestrator
behavior — zero regression).

## Scope / limitations (v1)
BEAR_EXIT / regime deferred (`enable_bear_exit=false`). Single stock exit config
(per-strategy needs M4-O to persist `strategy` — follow-up). Full-close only.
Paper-only. Long-only. Exit fills carry `trade_role=exit` (reason/pnl in logs +
risk state, not the fill schema). See spec §1.

## How tested
Unit (eod_exempt_maximize flag incl. backward-compat, position codec + opened_at_ms
guard + high_water round-trip, daemon stop-loss/no-price/unfilled/high-persist),
integration (open → exit → close + PnL feedback + re-entry freed), three_stage
regression green, full `tests/` gate green, ruff/black clean.

Spec: `docs/superpowers/specs/2026-06-06-stock-exit-daemon-m4x-design.md`
Plan: `docs/superpowers/plans/archive/2026-06-06-stock-exit-daemon-m4x.md`

## Follow-ups
Per-strategy exit configs (needs M4-O `strategy` persistence); BEAR_EXIT/regime
wiring; M5 monolithic-orchestrator cutover.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Run code review** — `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:**
- §2 EOD no-flatten (`eod_exempt_maximize`) → Task 1. ✓
- §2 BEAR deferred (`enable_bear_exit=false`) → Task 4 config + daemon passes `market_state=None`. ✓
- §4.1 module structure → Tasks 2/3/4. ✓
- §4.2 cycle flow (read → high persist → scan → execute) → Task 3 `run_cycle`. ✓
- §4.3 Position reconstruction → Task 2 `position_from_record`. ✓
- §4.4 ThreeStageExit reuse + flag → Task 1. ✓
- §4.5 single config → Task 4 `config/stock_exit.yaml`. ✓
- §4.6 opened_at_ms guard → Task 2 `parse_position_record`. ✓
- §5 execution (SELL → HDEL → record_trade/win/loss → log_fill best-effort) → Task 3 `_execute_exit`. ✓
- §5 PnL = gross − round-trip fee → Task 3. ✓
- §6 flags/systemd/env overrides → Task 4. ✓
- §7 error handling (skip foreign, no-price skip, unfilled no-close, cycle resilience) → Tasks 2/3 + tests. ✓
- §8 testing (unit + e2e + regression) → Tasks 1–6. ✓
- §9 acceptance (default-off, no-regression, PnL feedback activates M4-R, ClickHouse-free) → Tasks 4/5/6. ✓

**Placeholder scan:** none — complete code in every step.

**Type consistency:** `parse_position_record` / `position_from_record(rec, *, fee_rate)` / `record_with_high_water(rec, pos)` signatures consistent across Tasks 2/3. `StockExitDaemon` constructor kwargs match between Task 3 impl, Task 4 entrypoint, and Task 5 e2e. `OrderSide.SELL`/`OrderType.MARKET` from `shared.paper.models`. `RuntimeRiskState.record_trade(*, pnl_krw=)` / `record_win()` / `record_loss()` / `snapshot()` match `shared/risk/runtime_state.py`. `FillLogger.log_fill(...)` kwargs match the M4-O usage. `feed.get_current_price` is async returning a dict (matches `StreamConsumerFeed`). `ThreeStageExit.scan_positions(positions, market_data, market_state=None)` + `_check_position(position=, market_data=, market_state=, now=)` match `three_stage.py`.

**Open questions resolved:** cadence default = 5s (`STOCK_EXIT_INTERVAL`, Task 4); loop-activation integration test included (Task 5); fee = explicit gross−round-trip (Task 3, VirtualBroker commission ignored cross-process); `eod_exempt_maximize` inlined reusing the already-computed `stage` (Task 1).
