# Futures Monitor Daemon (F-5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A shadow-first `services/futures_monitor/` that bridges the decoupled futures chain's streams to dashboard state (`trading:futures:*[:shadow]`) + Telegram alerts — full mirror of the stock monitor, with a monitor-owned positions hash, side-aware multiplier PnL, and the F-6 exit `trade_role`s.

**Architecture:** Mirror `services/stock_monitor/` (main.py + daemon.py + serializers.py). REUSE by import the asset-agnostic `AlertSink`/`SessionDigest` (`services.stock_monitor.alerts`), `TradingStatePublisher`, `StreamConsumerFeed`, `notifier_for_domain("futures")`, contract-spec helpers. New futures code: serializers (futures signal schema + side+multiplier builders), `calc_futures_realized_pnl` (parity with `PseudoOCO._record_pnl`), `positions.py` codec, `FuturesMonitorDaemon` (owns `futures:monitor:positions`).

**Tech Stack:** Python 3.11+ asyncio, Redis streams + hashes (fakeredis in tests), pytest. Reference (read, don't modify): `services/stock_monitor/{main,daemon,serializers,alerts}.py`, `tests/unit/stock_monitor/`.

**Spec:** `docs/superpowers/specs/2026-06-07-futures-monitor-f5-design.md`

**Worktree:** Implement in `/tmp/f5-impl` (branch `feat/futures-monitor-f5`). Run venv tools from `cd /tmp/f5-impl` using `/home/deploy/project/kis_unified_sts/.venv/bin/{pytest,black,ruff,mypy}`.

**GIT HYGIENE (critical):** NEVER run `git stash`/`pop`/`apply`/`drop` — repo-global across worktrees, corrupts the operator's stash. Use `git add <explicit paths>` + `git commit` only. Do not touch `/home/deploy/project/kis_unified_sts`, and do NOT modify `services/stock_monitor/` (reuse-by-import only).

**Key invariants:** PnL = `(exit−entry)·sign·qty·multiplier` (sign +1 long / −1 short, NO fee) — must match F-6 `PseudoOCO._record_pnl`. Monitor never writes `risk:state:futures*`. Shadow keys (`trading:futures:*:shadow`) never collide with the orchestrator's live keys. off = inert default.

**Out of scope:** order_router bracket durability, enabling the daemon (systemd delivered DISABLED), dashboard changes, F-4.

---

## File Structure

**Create:**
- `shared/utils/calc.py` (MODIFY — add `calc_futures_realized_pnl`)
- `services/futures_monitor/__init__.py`
- `services/futures_monitor/serializers.py`
- `services/futures_monitor/positions.py`
- `services/futures_monitor/daemon.py`
- `services/futures_monitor/main.py`
- `config/futures_monitor.yaml`
- `deploy/systemd/kis-futures-monitor-daemon.service`
- `tests/unit/futures_monitor/{__init__,test_serializers,test_positions,test_daemon,test_entrypoint}.py`

---

## Task 1: `calc_futures_realized_pnl` (parity helper)

**Files:** Modify `shared/utils/calc.py`; Test `tests/unit/utils/test_calc_futures_pnl.py` (create).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/utils/test_calc_futures_pnl.py`:
```python
"""F-5: futures realized PnL — parity with PseudoOCO._record_pnl (no fee)."""

from __future__ import annotations

import pytest

from shared.utils.calc import calc_futures_realized_pnl

MULT = 50_000.0


def test_long_win() -> None:
    # (333.00-331.20)*1*1*50000 = 90000
    assert calc_futures_realized_pnl(331.20, 333.00, 1, "long", multiplier_krw_per_point=MULT) == pytest.approx(90_000.0)


def test_long_loss() -> None:
    assert calc_futures_realized_pnl(331.20, 330.00, 1, "long", multiplier_krw_per_point=MULT) == pytest.approx(-60_000.0)


def test_short_win() -> None:
    # short: (329.40-331.20)*(-1)*1*50000 = 90000
    assert calc_futures_realized_pnl(331.20, 329.40, 1, "short", multiplier_krw_per_point=MULT) == pytest.approx(90_000.0)


def test_short_loss() -> None:
    assert calc_futures_realized_pnl(331.20, 332.40, 1, "short", multiplier_krw_per_point=MULT) == pytest.approx(-60_000.0)


def test_quantity_scales() -> None:
    assert calc_futures_realized_pnl(331.20, 333.20, 3, "long", multiplier_krw_per_point=MULT) == pytest.approx(300_000.0)
```

- [ ] **Step 2: Run to verify it fails** — `cd /tmp/f5-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/utils/test_calc_futures_pnl.py -q` → FAIL (ImportError).

- [ ] **Step 3: Implement** — append to `shared/utils/calc.py`:
```python
def calc_futures_realized_pnl(
    entry_price: float,
    exit_price: float,
    quantity: int,
    side: str,
    *,
    multiplier_krw_per_point: float,
) -> float:
    """Futures realized PnL in KRW. Matches PseudoOCO._record_pnl (F-6), no fee.

    sign = +1 for long, -1 for short → (exit-entry)*sign*qty*multiplier. Used by
    the futures monitor for dashboard PnL parity with the risk-state writer.
    """
    sign = 1.0 if side == "long" else -1.0
    return (exit_price - entry_price) * sign * quantity * multiplier_krw_per_point
```

- [ ] **Step 4: Run to verify it passes** — same pytest cmd → PASS (5 passed).

- [ ] **Step 5: Format + mypy + commit**
```bash
cd /tmp/f5-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black shared/utils/calc.py tests/unit/utils/test_calc_futures_pnl.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix shared/utils/calc.py tests/unit/utils/test_calc_futures_pnl.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy shared/utils/calc.py 2>&1 | tail -3
git add shared/utils/calc.py tests/unit/utils/test_calc_futures_pnl.py
git commit -m "feat(f-5): calc_futures_realized_pnl (parity with PseudoOCO._record_pnl)"
git rev-parse HEAD
```
(If `tests/unit/utils/` lacks `__init__.py`, the dir is a namespace pkg — fine; create the test file regardless. mypy: no new errors in calc.py.)

---

## Task 2: futures serializers

**Files:** Create `services/futures_monitor/__init__.py` (empty), `services/futures_monitor/serializers.py`; Test `tests/unit/futures_monitor/__init__.py` (empty) + `tests/unit/futures_monitor/test_serializers.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/futures_monitor/test_serializers.py`:
```python
"""F-5 futures monitor serializers — futures schema, side+multiplier."""

from __future__ import annotations

from services.futures_monitor.serializers import (
    build_position_dict,
    build_signal_dict,
    build_trade_dict,
    parse_fill,
    parse_final_signal,
)

MULT = 50_000.0


def _fill_fields(side: str = "long", role: str = "entry") -> dict[bytes, bytes]:
    return {
        b"signal_id": b"s1",
        b"order_id": b"O1",
        b"symbol": b"A05603",
        b"side": side.encode(),
        b"filled_price": b"331.20",
        b"quantity": b"1",
        b"trade_role": role.encode(),
        b"filled_at_ms": b"1700000000000",
    }


def test_parse_fill_reads_futures_fields() -> None:
    f = parse_fill(_fill_fields(side="short", role="stop_loss"))
    assert f["symbol"] == "A05603"
    assert f["side"] == "short"
    assert f["filled_price"] == 331.20
    assert f["quantity"] == 1
    assert f["trade_role"] == "stop_loss"
    assert f["signal_id"] == "s1"


def test_parse_final_signal_futures_schema() -> None:
    fields = {
        b"signal_id": b"s1",
        b"symbol": b"A05603",
        b"setup_type": b"A_gap_reversion",
        b"direction": b"short",
        b"entry_price": b"331.20",
        b"confidence": b"0.85",
        b"generated_at_ms": b"1700000000000",
    }
    sig = parse_final_signal(fields)
    assert sig["symbol"] == "A05603"
    assert sig["setup_type"] == "A_gap_reversion"
    assert sig["direction"] == "short"
    assert sig["entry_price"] == 331.20
    assert sig["confidence"] == 0.85


def test_build_position_dict_carries_side() -> None:
    fill = parse_fill(_fill_fields(side="short"))
    meta = {"setup_type": "A_gap_reversion", "direction": "short"}
    pos = build_position_dict(fill, meta, multiplier=MULT)
    assert pos["code"] == "A05603"
    assert pos["side"] == "short"
    assert pos["entry_price"] == 331.20
    assert pos["strategy"] == "A_gap_reversion"
    assert pos["unrealized_pnl"] == 0.0


def test_build_trade_dict_long_pnl_pct_and_reason() -> None:
    entry = {"symbol": "A05603", "side": "long", "entry_price": 331.20,
             "entry_time": "t0", "setup_type": "A_gap_reversion"}
    exit_fill = parse_fill(_fill_fields(role="take_profit"))
    exit_fill["filled_price"] = 333.00
    trade = build_trade_dict(entry, exit_fill, pnl=90_000.0)
    assert trade["side"] == "long"
    assert trade["exit_reason"] == "take_profit"
    assert trade["pnl"] == 90_000.0
    assert trade["pnl_pct"] == round((333.00 - 331.20) / 331.20 * 100, 10) or trade["pnl_pct"] > 0


def test_build_trade_dict_short_pnl_pct() -> None:
    entry = {"symbol": "A05603", "side": "short", "entry_price": 331.20,
             "entry_time": "t0", "setup_type": "A"}
    exit_fill = parse_fill(_fill_fields(side="long", role="stop_loss"))
    exit_fill["filled_price"] = 332.40
    trade = build_trade_dict(entry, exit_fill, pnl=-60_000.0)
    assert trade["side"] == "short"
    # short pnl_pct = (ep - xp)/ep*100 = (331.20-332.40)/331.20*100 < 0
    assert trade["pnl_pct"] < 0


def test_build_signal_dict_futures() -> None:
    sig = {"signal_id": "s1", "symbol": "A05603", "setup_type": "A_gap_reversion",
           "direction": "long", "entry_price": 331.20, "confidence": 0.85,
           "generated_at_ms": "1700000000000"}
    d = build_signal_dict(sig)
    assert d["symbol"] == "A05603"
    assert d["strategy"] == "A_gap_reversion"
    assert d["price"] == 331.20
    assert d["side"] == "entry"
```

- [ ] **Step 2: Run to verify it fails** — `cd /tmp/f5-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/futures_monitor/test_serializers.py -q` → FAIL.

- [ ] **Step 3: Implement**

Create `services/futures_monitor/__init__.py` (empty) and `tests/unit/futures_monitor/__init__.py` (empty).

Create `services/futures_monitor/serializers.py`:
```python
"""Pure parsers + dashboard dict builders for the futures monitor bridge.

Translates decoupled daemon stream records (order.fill.futures.* /
signal.final.futures.*) into the dashboard-native dict shapes the React Cockpit
reads via TradingStateReader. Side-aware, contract-multiplier PnL. No I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _s(fields: dict[bytes, bytes], key: str) -> str:
    raw = fields.get(key.encode(), b"")
    return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)


def _ms_to_iso(ms: str) -> str:
    """Epoch-ms string -> tz-aware ISO; empty/invalid -> current UTC.

    The empty/invalid -> ``datetime.now(UTC)`` fallback intentionally matches
    ``_tz_aware_iso(None)`` in ``shared/streaming/trading_state.py``.
    """
    if not ms:
        return datetime.now(UTC).isoformat()
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=UTC).isoformat()
    except (TypeError, ValueError):
        return datetime.now(UTC).isoformat()


def parse_fill(fields: dict[bytes, bytes]) -> dict[str, Any]:
    """Parse an order.fill.futures.* record (FillLogger schema)."""
    return {
        "signal_id": _s(fields, "signal_id"),
        "order_id": _s(fields, "order_id"),
        "symbol": _s(fields, "symbol"),
        "side": _s(fields, "side") or "long",
        "filled_price": float(_s(fields, "filled_price") or 0.0),
        "quantity": int(float(_s(fields, "quantity") or 0)),
        "trade_role": _s(fields, "trade_role"),
        "filled_at_ms": _s(fields, "filled_at_ms"),
    }


def parse_final_signal(fields: dict[bytes, bytes]) -> dict[str, Any]:
    """Parse a signal.final.futures.* record (Signal.to_stream_dict schema)."""
    return {
        "signal_id": _s(fields, "signal_id"),
        "symbol": _s(fields, "symbol"),
        "setup_type": _s(fields, "setup_type"),
        "direction": _s(fields, "direction") or "long",
        "entry_price": float(_s(fields, "entry_price") or 0.0),
        "confidence": float(_s(fields, "confidence") or 0.0),
        "generated_at_ms": _s(fields, "generated_at_ms"),
    }


def build_position_dict(
    fill: dict[str, Any], meta: dict[str, Any], *, multiplier: float
) -> dict[str, Any]:
    """Dashboard open-position dict (mirrors _serialize_position), side-aware."""
    symbol = fill["symbol"]
    entry = fill["filled_price"]
    return {
        "id": symbol,
        "code": symbol,
        "name": "",
        "side": fill["side"],
        "quantity": fill["quantity"],
        "entry_price": entry,
        "current_price": entry,
        "unrealized_pnl": 0.0,
        "pnl_pct": 0.0,
        "entry_time": _ms_to_iso(fill["filled_at_ms"]),
        "strategy": meta.get("setup_type", ""),
        "state": "survival",
        "highest_price": entry,
        "lowest_price": entry,
        "fee_rate": 0.0,
        "stop_price": None,
        "client_order_id": fill["signal_id"],
    }


def build_trade_dict(
    entry: dict[str, Any], exit_fill: dict[str, Any], *, pnl: float
) -> dict[str, Any]:
    """Dashboard closed-trade dict (mirrors _serialize_closed_position), side-aware."""
    ep = float(entry["entry_price"])
    xp = float(exit_fill["filled_price"])
    qty = exit_fill["quantity"]
    side = entry.get("side", "long")
    if not ep:
        pnl_pct = 0.0
    elif side == "long":
        pnl_pct = (xp - ep) / ep * 100
    else:
        pnl_pct = (ep - xp) / ep * 100
    return {
        "id": exit_fill["order_id"] or exit_fill["signal_id"],
        "symbol": entry["symbol"],
        "name": entry.get("name", ""),
        "side": side,
        "quantity": qty,
        "entry_price": ep,
        "exit_price": xp,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "strategy": entry.get("setup_type", ""),
        "entry_time": entry.get("entry_time", ""),
        "exit_time": _ms_to_iso(exit_fill["filled_at_ms"]),
        "exit_reason": exit_fill["trade_role"],
    }


def build_signal_dict(sig: dict[str, Any]) -> dict[str, Any]:
    """Dashboard signal dict (mirrors orchestrator convention)."""
    return {
        "id": sig["signal_id"],
        "symbol": sig["symbol"],
        "name": "",
        "side": "entry",
        "signal_type": "entry",
        "strategy": sig["setup_type"],
        "price": sig["entry_price"],
        "confidence": sig["confidence"],
        "timestamp": _ms_to_iso(sig["generated_at_ms"]),
        "executed": True,
        "reason": "",
        "stage": "",
    }
```

- [ ] **Step 4: Run to verify it passes** — pytest → PASS.

- [ ] **Step 5: Format + commit**
```bash
cd /tmp/f5-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black services/futures_monitor/ tests/unit/futures_monitor/
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix services/futures_monitor/ tests/unit/futures_monitor/
git add services/futures_monitor/__init__.py services/futures_monitor/serializers.py tests/unit/futures_monitor/__init__.py tests/unit/futures_monitor/test_serializers.py
git commit -m "feat(f-5): futures monitor serializers (futures schema, side+multiplier)"
git rev-parse HEAD
```

---

## Task 3: futures positions codec

**Files:** Create `services/futures_monitor/positions.py`; Test `tests/unit/futures_monitor/test_positions.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/futures_monitor/test_positions.py`:
```python
"""F-5 futures monitor positions hash codec."""

from __future__ import annotations

from services.futures_monitor.positions import (
    build_position_record,
    parse_futures_position_record,
)


def test_round_trip() -> None:
    state = {
        "symbol": "A05603", "side": "short", "entry_price": 331.20,
        "quantity": 2, "opened_at_ms": 1700000000000, "setup_type": "A",
        "signal_id": "s1", "high_water": 332.0, "low_water": 330.0,
    }
    raw = build_position_record(state)
    rec = parse_futures_position_record(raw.encode())
    assert rec is not None
    assert rec["symbol"] == "A05603"
    assert rec["side"] == "short"
    assert rec["entry_price"] == 331.20
    assert rec["quantity"] == 2


def test_foreign_record_skipped_missing_opened_at() -> None:
    # orchestrator-style record (no opened_at_ms) → None
    assert parse_futures_position_record(b'{"symbol": "A05603", "entry_time": "x"}') is None


def test_missing_symbol_skipped() -> None:
    assert parse_futures_position_record(b'{"opened_at_ms": 1}') is None


def test_invalid_json_returns_none() -> None:
    assert parse_futures_position_record(b"not json") is None
```

- [ ] **Step 2: Run to verify it fails** — pytest → FAIL.

- [ ] **Step 3: Implement** — create `services/futures_monitor/positions.py`:
```python
"""Futures monitor's private positions hash codec (F-5).

The decoupled futures chain has no positions hash, so the futures monitor owns
``futures:monitor:positions`` (field=symbol) for restart recovery: HSET on
entry, update high/low on MTM, HDEL on exit, recover on startup. Records require
``opened_at_ms`` + ``symbol`` so foreign (orchestrator) records are skipped.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_position_record(state: dict[str, Any]) -> str:
    """JSON-encode an open-position state dict for HSET."""
    return json.dumps(
        {
            "symbol": state["symbol"],
            "side": state["side"],
            "entry_price": float(state["entry_price"]),
            "quantity": int(state["quantity"]),
            "opened_at_ms": int(state.get("opened_at_ms", 0) or 0),
            "setup_type": state.get("setup_type", ""),
            "signal_id": state.get("signal_id", ""),
            "high_water": float(state.get("high_water", state["entry_price"])),
            "low_water": float(state.get("low_water", state["entry_price"])),
        }
    )


def parse_futures_position_record(value: bytes | str) -> dict[str, Any] | None:
    """Decode a hash value; return None for foreign/invalid records.

    Requires both ``opened_at_ms`` and ``symbol`` (skips orchestrator-style
    records that lack ``opened_at_ms``).
    """
    try:
        raw = value.decode() if isinstance(value, bytes) else value
        rec = json.loads(raw)
    except (ValueError, AttributeError):
        return None
    if not isinstance(rec, dict):
        return None
    if "opened_at_ms" not in rec or "symbol" not in rec:
        return None
    return rec
```

- [ ] **Step 4: Run to verify it passes** — pytest → PASS.

- [ ] **Step 5: Format + commit**
```bash
cd /tmp/f5-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black services/futures_monitor/positions.py tests/unit/futures_monitor/test_positions.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix services/futures_monitor/positions.py tests/unit/futures_monitor/test_positions.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy services/futures_monitor/positions.py 2>&1 | tail -3
git add services/futures_monitor/positions.py tests/unit/futures_monitor/test_positions.py
git commit -m "feat(f-5): futures monitor positions hash codec"
git rev-parse HEAD
```

---

## Task 4: FuturesMonitorDaemon

**Files:** Create `services/futures_monitor/daemon.py`; Test `tests/unit/futures_monitor/test_daemon.py`.

**Reference:** `services/stock_monitor/daemon.py` (the run/stop/_consume_loop/_status_loop/_check_health_and_digest scaffolding is structurally identical — adapt the handlers for futures: 3 exit roles, side-aware multiplier PnL, monitor-owned hash writes, recover from the futures hash).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/futures_monitor/test_daemon.py`:
```python
"""F-5 FuturesMonitorDaemon — entry/exit pairing, multiplier PnL, hash writes."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import fakeredis.aioredis
import pytest

from services.futures_monitor.daemon import FuturesMonitorDaemon

MULT = 50_000.0
POS_KEY = "futures:monitor:positions"


class _FakeFeed:
    def __init__(self, close: float = 331.20) -> None:
        self._close = close

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def get_current_price(self, symbol: str) -> dict:
        return {"close": self._close}

    def get_staleness_seconds(self) -> float | None:
        return 0.0


def _fill(side: str, role: str, price: float, qty: int = 1) -> dict[bytes, bytes]:
    return {
        b"signal_id": b"s1", b"order_id": b"O1", b"symbol": b"A05603",
        b"side": side.encode(), b"filled_price": str(price).encode(),
        b"quantity": str(qty).encode(), b"trade_role": role.encode(),
        b"filled_at_ms": b"1700000000000",
    }


def _make_daemon(redis: Any) -> FuturesMonitorDaemon:
    return FuturesMonitorDaemon(
        redis=redis,
        feed=_FakeFeed(),
        publisher=MagicMock(),
        alert_sink=None,
        positions_key=POS_KEY,
        fill_stream="order.fill.futures.shadow",
        signal_stream="signal.final.futures.shadow",
        consumer_group="futures_monitor",
        worker_id="w1",
        multiplier=MULT,
        status_interval=0.01,
    )


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(db=1)


@pytest.mark.asyncio
async def test_entry_opens_position_and_writes_hash(redis):
    d = _make_daemon(redis)
    await d.handle_fill(_fill("long", "entry", 331.20))
    assert "A05603" in d._open
    assert d._open["A05603"]["side"] == "long"
    assert await redis.hexists(POS_KEY, "A05603")
    d.publisher.publish_raw_position.assert_called_once()


@pytest.mark.asyncio
async def test_long_take_profit_pnl_and_hdel(redis):
    d = _make_daemon(redis)
    await d.handle_fill(_fill("long", "entry", 331.20))
    await d.handle_fill(_fill("short", "take_profit", 333.00))
    assert "A05603" not in d._open
    assert not await redis.hexists(POS_KEY, "A05603")
    trade = d.publisher.publish_raw_trade.call_args.args[0]
    assert trade["pnl"] == pytest.approx(90_000.0)  # (333.00-331.20)*1*50000
    assert trade["exit_reason"] == "take_profit"
    assert trade["side"] == "long"


@pytest.mark.asyncio
async def test_short_stop_loss_pnl_sign(redis):
    d = _make_daemon(redis)
    await d.handle_fill(_fill("short", "entry", 331.20))
    await d.handle_fill(_fill("long", "stop_loss", 332.40))
    trade = d.publisher.publish_raw_trade.call_args.args[0]
    assert trade["pnl"] == pytest.approx(-60_000.0)  # (332.40-331.20)*(-1)*50000
    assert trade["side"] == "short"


@pytest.mark.asyncio
async def test_orphan_exit_removes_position(redis):
    d = _make_daemon(redis)
    await d.handle_fill(_fill("long", "stop_loss", 330.0))  # no open entry
    d.publisher.remove_position.assert_called_once_with("A05603")
    d.publisher.publish_raw_trade.assert_not_called()


@pytest.mark.asyncio
async def test_recover_from_hash(redis):
    await redis.hset(POS_KEY, "A05603", json.dumps({
        "symbol": "A05603", "side": "short", "entry_price": 331.20, "quantity": 1,
        "opened_at_ms": 1700000000000, "setup_type": "A", "signal_id": "s1",
        "high_water": 332.0, "low_water": 330.0,
    }))
    d = _make_daemon(redis)
    await d.recover_open_positions()
    assert d._open["A05603"]["side"] == "short"
    assert d._open["A05603"]["entry_price"] == 331.20


@pytest.mark.asyncio
async def test_mtm_side_aware_unrealized(redis):
    d = _make_daemon(redis)
    await d.handle_fill(_fill("short", "entry", 331.20))
    d.feed._close = 330.20  # short profits when price falls
    await d.publish_status_and_mtm()
    pos = d.publisher.publish_raw_position.call_args.args[1]
    # short unrealized = (330.20-331.20)*(-1)*1*50000 = +50000
    assert pos["unrealized_pnl"] == pytest.approx(50_000.0)


@pytest.mark.asyncio
async def test_signal_published(redis):
    d = _make_daemon(redis)
    await d.handle_signal({
        b"signal_id": b"s1", b"symbol": b"A05603", b"setup_type": b"A_gap_reversion",
        b"direction": b"long", b"entry_price": b"331.20", b"confidence": b"0.85",
        b"generated_at_ms": b"1700000000000",
    })
    d.publisher.publish_raw_signal.assert_called_once()
```

- [ ] **Step 2: Run to verify it fails** — pytest → FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement** — create `services/futures_monitor/daemon.py`:
```python
"""Futures monitor / observability bridge daemon (F-5, shadow-first).

Consumes the decoupled futures daemon streams and republishes dashboard-native
state (positions/trades/signals/status) via TradingStatePublisher + important-
only alerts. Pairs entry<->exit fills (by symbol) for closed trades, side-aware
contract-multiplier PnL (parity with PseudoOCO._record_pnl), marks positions to
market, owns the futures positions hash for restart recovery.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from services.futures_monitor.positions import (
    build_position_record,
    parse_futures_position_record,
)
from services.futures_monitor.serializers import (
    _ms_to_iso,
    build_position_dict,
    build_signal_dict,
    build_trade_dict,
    parse_fill,
    parse_final_signal,
)
from shared.utils.calc import calc_futures_realized_pnl

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_EXIT_ROLES = ("stop_loss", "take_profit", "force_close")


class FuturesMonitorDaemon:
    """Bridge daemon: futures daemon streams -> dashboard keys + alerts."""

    def __init__(
        self,
        *,
        redis: Any,
        feed: Any,
        publisher: Any,
        alert_sink: Any | None,
        positions_key: str,
        fill_stream: str,
        signal_stream: str,
        consumer_group: str,
        worker_id: str,
        multiplier: float,
        status_interval: float,
        signal_meta_max: int = 1000,
        now_fn: Callable[[], datetime] = lambda: datetime.now(UTC),
        health_stale_seconds: float = 600.0,
        health_cooldown_seconds: float = 1800.0,
        digest_time_kst: str = "15:40",
    ) -> None:
        self.redis = redis
        self.feed = feed
        self.publisher = publisher
        self.alert_sink = alert_sink
        self.positions_key = positions_key
        self.fill_stream = fill_stream
        self.signal_stream = signal_stream
        self.consumer_group = consumer_group
        self.worker_id = worker_id
        self.multiplier = multiplier
        self.status_interval = status_interval
        self.signal_meta_max = signal_meta_max
        self.now_fn = now_fn
        self.health_stale_seconds = health_stale_seconds
        self.health_cooldown_seconds = health_cooldown_seconds
        self.digest_time_kst = digest_time_kst
        self._open: dict[str, dict[str, Any]] = {}
        self._signal_meta: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._stop = asyncio.Event()
        self._last_health_alert_ts: float = 0.0
        self._digest_emitted_date: str = ""
        self._digest_reset_date: str = ""

    # -- handlers --------------------------------------------------------- #

    async def handle_signal(self, fields: dict[bytes, bytes]) -> None:
        sig = parse_final_signal(fields)
        self._signal_meta[sig["signal_id"]] = {
            "setup_type": sig["setup_type"],
            "direction": sig["direction"],
            "symbol": sig["symbol"],
        }
        while len(self._signal_meta) > self.signal_meta_max:
            self._signal_meta.popitem(last=False)
        self.publisher.publish_raw_signal(build_signal_dict(sig))

    async def _persist_open(self, symbol: str) -> None:
        with contextlib.suppress(Exception):
            await self.redis.hset(
                self.positions_key, symbol, build_position_record(self._open[symbol])
            )

    async def handle_fill(self, fields: dict[bytes, bytes]) -> None:
        fill = parse_fill(fields)
        symbol = fill["symbol"]
        role = fill["trade_role"]
        if role == "entry":
            meta = self._signal_meta.get(fill["signal_id"], {})
            pos_dict = build_position_dict(fill, meta, multiplier=self.multiplier)
            self.publisher.publish_raw_position(symbol, pos_dict)
            entry_price = fill["filled_price"]
            self._open[symbol] = {
                "symbol": symbol,
                "side": fill["side"],
                "setup_type": meta.get("setup_type", ""),
                "signal_id": fill["signal_id"],
                "entry_price": entry_price,
                "quantity": fill["quantity"],
                "entry_time": pos_dict["entry_time"],
                "opened_at_ms": int(float(fill["filled_at_ms"] or 0)),
                "high_water": entry_price,
                "low_water": entry_price,
            }
            await self._persist_open(symbol)
            if self.alert_sink is not None:
                await self.alert_sink.on_entry(
                    code=symbol, strategy=meta.get("setup_type", ""),
                    quantity=fill["quantity"], price=entry_price,
                )
        elif role in _EXIT_ROLES:
            entry = self._open.pop(symbol, None)
            if entry is None:
                logger.warning("exit fill for %s with no open entry; skipping", symbol)
                self.publisher.remove_position(symbol)
                with contextlib.suppress(Exception):
                    await self.redis.hdel(self.positions_key, symbol)
                return
            ep, xp, qty = entry["entry_price"], fill["filled_price"], fill["quantity"]
            side = entry["side"]
            pnl = calc_futures_realized_pnl(
                ep, xp, qty, side, multiplier_krw_per_point=self.multiplier
            )
            trade = build_trade_dict(entry, fill, pnl=pnl)
            self.publisher.publish_raw_trade(trade)
            self.publisher.remove_position(symbol)
            with contextlib.suppress(Exception):
                await self.redis.hdel(self.positions_key, symbol)
            if self.alert_sink is not None:
                await self.alert_sink.on_exit(
                    code=symbol, pnl=pnl, pnl_pct=trade["pnl_pct"]
                )
        else:
            logger.warning("unknown trade_role %r for %s; dropping", role, symbol)

    # -- recovery + status ------------------------------------------------ #

    async def recover_open_positions(self) -> None:
        try:
            raw = await self.redis.hgetall(self.positions_key)
        except Exception:
            logger.warning("recover read failed; starting empty", exc_info=True)
            return
        for value in raw.values():
            rec = parse_futures_position_record(value)
            if rec is None:
                continue
            symbol = str(rec["symbol"])
            entry_price = float(rec["entry_price"])
            self._open[symbol] = {
                "symbol": symbol,
                "side": str(rec.get("side", "long")),
                "setup_type": str(rec.get("setup_type", "")),
                "signal_id": str(rec.get("signal_id", "")),
                "entry_price": entry_price,
                "quantity": int(rec["quantity"]),
                "entry_time": _ms_to_iso(str(rec.get("opened_at_ms", ""))),
                "opened_at_ms": int(rec.get("opened_at_ms", 0) or 0),
                "high_water": float(rec.get("high_water", entry_price)),
                "low_water": float(rec.get("low_water", entry_price)),
            }
            self._publish_position(symbol, entry_price)

    def _publish_position(self, symbol: str, close: float) -> None:
        entry = self._open[symbol]
        ep = entry["entry_price"]
        qty = int(entry.get("quantity", 0) or 0)
        sign = 1.0 if entry["side"] == "long" else -1.0
        self.publisher.publish_raw_position(
            symbol,
            {
                "id": symbol,
                "code": symbol,
                "name": "",
                "side": entry["side"],
                "quantity": qty,
                "entry_price": ep,
                "current_price": close,
                "unrealized_pnl": (close - ep) * sign * qty * self.multiplier,
                "pnl_pct": (((close - ep) * sign) / ep * 100) if ep else 0.0,
                "entry_time": entry.get("entry_time", ""),
                "strategy": entry.get("setup_type", ""),
                "state": "survival",
                "highest_price": entry["high_water"],
                "lowest_price": entry["low_water"],
                "fee_rate": 0.0,
                "stop_price": None,
                "client_order_id": entry.get("signal_id", ""),
            },
        )

    async def publish_status_and_mtm(self) -> None:
        for symbol, entry in list(self._open.items()):
            price = await self.feed.get_current_price(symbol)
            close = price.get("close")
            if close is None:
                continue
            close = float(close)
            entry["high_water"] = max(float(entry.get("high_water", close)), close)
            entry["low_water"] = min(float(entry.get("low_water", close)), close)
            self._publish_position(symbol, close)
            await self._persist_open(symbol)
        self.publisher.publish_status(
            {
                "open_positions": len(self._open),
                "worker_id": self.worker_id,
                "source": "futures_monitor",
            }
        )

    async def _check_health_and_digest(self) -> None:
        if self.alert_sink is None:
            return
        now_kst = self.now_fn().astimezone(_KST)
        today = now_kst.date().isoformat()
        hhmm = now_kst.strftime("%H:%M")
        in_market = time(9, 0) <= now_kst.time() <= time(15, 30)
        if now_kst.time() >= time(9, 0) and self._digest_reset_date != today:
            self.alert_sink.digest.reset()
            self._digest_reset_date = today
        if hhmm >= self.digest_time_kst and self._digest_emitted_date != today:
            if self.alert_sink.digest.trades > 0:
                await self.alert_sink.emit_digest(open_count=len(self._open))
            self._digest_emitted_date = today
        if in_market:
            staleness = self.feed.get_staleness_seconds()
            if staleness is not None and staleness > self.health_stale_seconds:
                now_ts = self.now_fn().timestamp()
                if now_ts - self._last_health_alert_ts > self.health_cooldown_seconds:
                    await self.alert_sink.send_health(
                        f"market data stale {staleness:.0f}s (feed)"
                    )
                    self._last_health_alert_ts = now_ts

    # -- loops ------------------------------------------------------------ #

    async def run(self) -> None:
        await self.feed.start()
        for stream in (self.fill_stream, self.signal_stream):
            with contextlib.suppress(Exception):
                await self.redis.xgroup_create(
                    stream, self.consumer_group, id="0", mkstream=True
                )
        await self.recover_open_positions()
        consumer = asyncio.create_task(self._consume_loop())
        status = asyncio.create_task(self._status_loop())
        try:
            await self._stop.wait()
        finally:
            consumer.cancel()
            status.cancel()
            for t in (consumer, status):
                with contextlib.suppress(asyncio.CancelledError):
                    await t
            await self.feed.stop()

    async def stop(self) -> None:
        self._stop.set()

    async def _consume_loop(self) -> None:
        while not self._stop.is_set():
            try:
                messages = await self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.worker_id,
                    streams={self.fill_stream: ">", self.signal_stream: ">"},
                    count=50,
                    block=2000,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("xreadgroup error; sleeping 0.5s")
                await asyncio.sleep(0.5)
                continue
            if not messages:
                continue
            for stream, msgs in messages:
                name = stream.decode() if isinstance(stream, bytes) else str(stream)
                for msg_id, data in msgs:
                    try:
                        if name == self.fill_stream:
                            await self.handle_fill(data)
                        elif name == self.signal_stream:
                            await self.handle_signal(data)
                        else:
                            logger.warning("unexpected stream %s", name)
                    except Exception:
                        logger.exception("handler error; dropping (poison-pill)")
                    await self.redis.xack(name, self.consumer_group, msg_id)

    async def _status_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.publish_status_and_mtm()
                await self._check_health_and_digest()
            except Exception:
                logger.exception("status loop error; continuing")
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self.status_interval)
```

- [ ] **Step 4: Run to verify it passes** — pytest → PASS (all daemon tests).

- [ ] **Step 5: Format + mypy + commit**
```bash
cd /tmp/f5-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black services/futures_monitor/daemon.py tests/unit/futures_monitor/test_daemon.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix services/futures_monitor/daemon.py tests/unit/futures_monitor/test_daemon.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy services/futures_monitor/daemon.py 2>&1 | tail -5
git add services/futures_monitor/daemon.py tests/unit/futures_monitor/test_daemon.py
git commit -m "feat(f-5): FuturesMonitorDaemon (pairing, multiplier PnL, owned positions hash)"
git rev-parse HEAD
```
(`_ms_to_iso` is imported from serializers — if ruff flags the private import, it's intentional reuse; keep it. If ruff/mypy flags an unused import, remove only the genuinely unused.)

---

## Task 5: entrypoint + config + systemd

**Files:** Create `services/futures_monitor/main.py`, `config/futures_monitor.yaml`, `deploy/systemd/kis-futures-monitor-daemon.service`; Test `tests/unit/futures_monitor/test_entrypoint.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/futures_monitor/test_entrypoint.py`:
```python
"""F-5 futures monitor entrypoint flag routing."""

from __future__ import annotations

import services.futures_monitor.main as m


def test_resolve_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("FUTURES_MONITOR_DAEMON", raising=False)
    assert m._resolve_mode() == "off"


def test_streams_for_shadow():
    assert m._streams_for("shadow") == (
        "order.fill.futures.shadow",
        "signal.final.futures.shadow",
    )


def test_streams_for_live():
    assert m._streams_for("live") == ("order.fill.futures", "signal.final.futures")


def test_shadow_forces_suffix(monkeypatch):
    monkeypatch.delenv("TRADING_STATE_KEY_SUFFIX", raising=False)
    m._ensure_shadow_isolation("shadow")
    import os
    assert os.environ.get("TRADING_STATE_KEY_SUFFIX") == "shadow"


def test_live_clears_suffix(monkeypatch):
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "shadow")
    m._ensure_shadow_isolation("live")
    import os
    assert os.environ.get("TRADING_STATE_KEY_SUFFIX") == ""


def test_config_loads():
    from shared.config.loader import ConfigLoader

    cfg = ConfigLoader.load("futures_monitor.yaml").get("futures_monitor", {})
    assert "telegram" in cfg
```

- [ ] **Step 2: Run to verify it fails** — pytest → FAIL.

- [ ] **Step 3: Implement**

Create `config/futures_monitor.yaml`:
```yaml
# Futures monitor / observability bridge (F-5) — selective Telegram policy.
futures_monitor:
  telegram:
    pnl_alert_pct: 3.0            # notify only on exits with |pnl%| >= 3%
    health_stale_seconds: 600     # no market data for 10min during market hours -> anomaly
    health_cooldown_seconds: 1800 # min gap between repeated health alerts
    digest_time_kst: "15:40"      # one daily session digest
```

Create `services/futures_monitor/main.py`:
```python
"""Futures monitor bridge entrypoint (flag-gated, shadow-first, default-off).

off (default): inert. shadow: publish to trading:futures:*:shadow + suppress
Telegram-to-log. live: live keys + real futures Telegram (Phase-5-gated).

Consumes order.fill.futures[.shadow] and signal.final.futures[.shadow].
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket

logger = logging.getLogger(__name__)


def _resolve_mode() -> str:
    return os.getenv("FUTURES_MONITOR_DAEMON", "off").strip().lower()


def _streams_for(mode: str) -> tuple[str, str]:
    if mode == "shadow":
        return "order.fill.futures.shadow", "signal.final.futures.shadow"
    return "order.fill.futures", "signal.final.futures"


def _ensure_shadow_isolation(mode: str) -> None:
    if mode == "shadow" and not os.environ.get("TRADING_STATE_KEY_SUFFIX", "").strip():
        os.environ["TRADING_STATE_KEY_SUFFIX"] = "shadow"
    if mode == "live" and os.environ.get("TRADING_STATE_KEY_SUFFIX", "").strip():
        logger.warning("clearing TRADING_STATE_KEY_SUFFIX for live futures monitor")
        os.environ["TRADING_STATE_KEY_SUFFIX"] = ""


async def _build_and_run() -> int:
    import signal as signal_mod

    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()
    if mode not in ("shadow", "live"):
        logger.info("FUTURES_MONITOR_DAEMON=%s (off) — daemon inert, exiting", mode)
        await redis_client.aclose()
        return 0

    _ensure_shadow_isolation(mode)

    from services.futures_monitor.daemon import FuturesMonitorDaemon
    from services.stock_monitor.alerts import AlertSink
    from services.trading.stream_consumer_feed import StreamConsumerFeed
    from shared.collector.historical.futures import get_front_month_code
    from shared.config.loader import ConfigLoader
    from shared.execution.contract_spec import (
        ContractSpecRegistry,
        resolve_contract_spec,
    )
    from shared.notification.telegram import notifier_for_domain
    from shared.streaming.trading_state import TradingStatePublisher

    fill_default, signal_default = _streams_for(mode)
    fill_stream = os.environ.get("FUTURES_FILL_STREAM", fill_default)
    signal_stream = os.environ.get("FUTURES_FINAL_STREAM", signal_default)
    positions_key = os.environ.get(
        "FUTURES_MONITOR_POSITIONS_KEY", "futures:monitor:positions"
    )
    status_interval = float(os.environ.get("FUTURES_MONITOR_STATUS_INTERVAL", "5"))
    tick_stream = os.environ.get("FUTURES_TICK_STREAM", "raw_data")

    specs = ContractSpecRegistry.from_yaml("config/execution.yaml")
    symbol = get_front_month_code(product="mini")
    spec = resolve_contract_spec(symbol, specs)

    tg = (
        ConfigLoader.load("futures_monitor.yaml")
        .get("futures_monitor", {})
        .get("telegram", {})
    )
    notifier = notifier_for_domain("futures") if mode == "live" else None
    alert_sink = AlertSink(
        notifier=notifier, mode=mode, pnl_alert_pct=float(tg.get("pnl_alert_pct", 3.0))
    )

    feed = StreamConsumerFeed(redis=redis_client, stream=tick_stream)
    feed.update_symbols([symbol])
    publisher = TradingStatePublisher(asset_class="futures")

    worker_id = f"futures-monitor-{socket.gethostname()}-{os.getpid()}"
    daemon = FuturesMonitorDaemon(
        redis=redis_client,
        feed=feed,
        publisher=publisher,
        alert_sink=alert_sink,
        positions_key=positions_key,
        fill_stream=fill_stream,
        signal_stream=signal_stream,
        consumer_group="futures_monitor",
        worker_id=worker_id,
        multiplier=spec.multiplier_krw_per_point,
        status_interval=status_interval,
        signal_meta_max=int(os.environ.get("FUTURES_MONITOR_SIGNAL_META_MAX", "1000")),
        health_stale_seconds=float(tg.get("health_stale_seconds", 600)),
        health_cooldown_seconds=float(tg.get("health_cooldown_seconds", 1800)),
        digest_time_kst=str(tg.get("digest_time_kst", "15:40")),
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    logger.info(
        "futures monitor starting worker=%s mode=%s symbol=%s suffix=%s",
        worker_id, mode, symbol, os.environ.get("TRADING_STATE_KEY_SUFFIX", ""),
    )
    try:
        await daemon.run()
    finally:
        await redis_client.aclose()
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
```

Verify `StreamConsumerFeed` has `update_symbols` (the stock monitor's feed didn't call it — futures needs the symbol for `get_current_price`). Inspect `services/trading/stream_consumer_feed.py`; if it has no `update_symbols`, drop that line (the feed reads the tick stream and `get_current_price(symbol)` filters by symbol internally) — adjust to whatever the feed API actually provides. Do NOT invent an API.

Create `deploy/systemd/kis-futures-monitor-daemon.service` (mirror the stock unit, delivered DISABLED — no mode env so it is off-inert; read `deploy/systemd/kis-stock-monitor-daemon.service` for the exact template and adapt names/ExecStart to `services.futures_monitor.main`). Do NOT set `FUTURES_MONITOR_DAEMON` (stays off).

- [ ] **Step 4: Run to verify it passes**
```bash
cd /tmp/f5-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/futures_monitor/ -q
FUTURES_MONITOR_DAEMON=off /home/deploy/project/kis_unified_sts/.venv/bin/python -c "import services.futures_monitor.main as m; print('off ->', m._resolve_mode())"
```
Expected: PASS; prints `off -> off`.

- [ ] **Step 5: Format + commit**
```bash
cd /tmp/f5-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black services/futures_monitor/main.py tests/unit/futures_monitor/test_entrypoint.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix services/futures_monitor/main.py tests/unit/futures_monitor/test_entrypoint.py
git add services/futures_monitor/main.py config/futures_monitor.yaml deploy/systemd/kis-futures-monitor-daemon.service tests/unit/futures_monitor/test_entrypoint.py
git commit -m "feat(f-5): futures monitor entrypoint + config + (disabled) systemd unit"
git rev-parse HEAD
```

---

## Task 6: full gate + PR

- [ ] **Step 1: Targeted + regression**
```bash
cd /tmp/f5-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/futures_monitor/ tests/unit/utils/test_calc_futures_pnl.py tests/unit/stock_monitor/ -q
```
Expected: all PASS (stock_monitor untouched → still green; futures new green).

- [ ] **Step 2: Full gate (CI parity) + mypy**
```bash
cd /tmp/f5-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance -p no:randomly 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -15
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m serial -q 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -8
/home/deploy/project/kis_unified_sts/.venv/bin/mypy shared/utils/calc.py services/futures_monitor/ 2>&1 | tail -6
```
Expected: green; mypy no new errors in the futures files. (A local xdist flake on `test_mixins_properties.py`/`test_handles_arbitrary_dicts` is a known pre-existing `ConfigLoader`-singleton artifact — confirm any failure is NOT a futures_monitor/calc test; CI is the merge gate.)

- [ ] **Step 3: Push + PR**
```bash
cd /tmp/f5-impl
git push -u origin feat/futures-monitor-f5
gh pr create --base main --head feat/futures-monitor-f5 \
  --title "feat(f-5): futures monitor daemon (dashboard bridge + Telegram, shadow-first)" \
  --body "$(cat <<'EOF'
## What
A shadow-first `services/futures_monitor/` that bridges the decoupled futures chain's streams
(`order.fill.futures[.shadow]` + `signal.final.futures[.shadow]`) to dashboard state
(`trading:futures:*[:shadow]`) + selective Telegram alerts — a full mirror of the stock monitor,
adapted for futures.

## Why
F-6 made the decoupled chain enter AND exit, but a shadow run was invisible (no Cockpit
positions/trades/signals, no alerts). The stock chain has `stock_monitor` (M5a); futures had none.

## Design
- **Modes:** off (default, inert) / shadow (`trading:futures:*:shadow` + Telegram→log) / live
  (unsuffixed + real futures Telegram; Phase-5-gated, systemd unit delivered DISABLED).
- **Reuse-by-import** (DRY): `AlertSink`/`SessionDigest` (asset-agnostic), `TradingStatePublisher`,
  `StreamConsumerFeed`, `notifier_for_domain("futures")`, contract-spec helpers. **stock_monitor untouched.**
- **Futures-specific:** serializers (futures signal schema, side-aware + multiplier `build_*`),
  `calc_futures_realized_pnl` (parity with F-6 `PseudoOCO._record_pnl`), a monitor-owned positions
  hash `futures:monitor:positions` (HSET entry / update MTM / HDEL exit / recover on startup),
  `FuturesMonitorDaemon` pairing `entry`→`{stop_loss,take_profit,force_close}` by symbol, side-aware
  multiplier PnL, MTM via the `raw_data` feed.

## Safety
- **PnL parity:** dashboard PnL == risk-state PnL — `(exit−entry)·sign·qty·multiplier`, no fee, same
  formula as the F-6 risk writer. The monitor never writes `risk:state:futures*`.
- **Collision isolation:** shadow keys `trading:futures:*:shadow` are disjoint from the orchestrator's
  live `trading:futures:*` (suffix via `_key`; dashboard reader suffix-blind → shadow invisible until a
  cutover). The private `futures:monitor:positions` hash is disjoint from `trading:futures:positions`.
- **off-inert** default; poison-pill drop; orphan-exit safe; loop-resilient.

## Scope / limitations
Monitor restart is now durable (its hash); an **order_router** restart still orphans in-memory
brackets (pre-existing, out of scope). Dashboard already renders futures `side` → no frontend change.

## How tested
calc parity (long/short); serializers (futures schema, side+multiplier, long+short trade pnl_pct);
positions codec (round-trip + foreign-skip); daemon (entry→exit lifecycle long+short PnL, orphan
exit, recover-from-hash, side-aware MTM, hash HSET/HDEL, signal publish). Full gate green;
mypy/ruff/black clean; stock_monitor suite still green (reuse-by-import only).

> CI note: a local `-n auto` run may flake on the unrelated `test_handles_arbitrary_dicts` (known
> pre-existing `ConfigLoader`-singleton xdist artifact). CI `test` gate is the arbiter.

Spec: `docs/superpowers/specs/2026-06-07-futures-monitor-f5-design.md`
Plan: `docs/superpowers/plans/archive/2026-06-07-futures-monitor-f5.md`

## Follow-ups
F-4 (MarketContext builder unification — last Phase B item), F-8/F-9 cutover. Hoisting AlertSink to
`shared/` is a future DRY refactor.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Run code review** — `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:** §4.2 modes/streams/shadow → Task 5; §4.3 serializers → Task 2; §4.4 calc parity → Task 1; §4.5 positions hash → Task 3; §4.6 daemon → Task 4; §4.7 AlertSink reuse → Task 5 (import); §4.8 entrypoint+config+systemd → Task 5; §7 testing → Tasks 1-6. ✓

**Placeholder scan:** none — complete code in every step, except the two explicitly-flagged verify-against-reality points (StreamConsumerFeed.update_symbols existence; systemd unit template) which instruct reading the actual file, not guessing.

**Type consistency:** `calc_futures_realized_pnl(entry, exit, qty, side, *, multiplier_krw_per_point)`; serializers `build_position_dict(fill, meta, *, multiplier)` / `build_trade_dict(entry, exit_fill, *, pnl)`; `parse_futures_position_record(value) -> dict|None` / `build_position_record(state) -> str`; `FuturesMonitorDaemon(*, redis, feed, publisher, alert_sink, positions_key, fill_stream, signal_stream, consumer_group, worker_id, multiplier, status_interval, ...)`; main `_resolve_mode`/`_streams_for`/`_ensure_shadow_isolation`. PnL sign +1 long/−1 short consistent across calc + daemon MTM + serializers pnl_pct. Exit roles `{stop_loss,take_profit,force_close}` consistent with F-6. `setup_type` used as the strategy field throughout (futures has no `strategy`/`name`).

**Open questions resolved:** AlertSink reused by import (not rewritten); positions hash key `futures:monitor:positions` (monitor-owned); PnL no-fee parity with PseudoOCO; tick feed `raw_data`; systemd delivered disabled; `_ms_to_iso`/`_s` duplicated in futures serializers (self-contained, stock untouched).
