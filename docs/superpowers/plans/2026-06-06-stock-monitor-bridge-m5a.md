# Stock Monitor / Observability Bridge (M5a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A shadow-first, default-off observability/notification bridge daemon that consumes the decoupled stock daemon streams (`order.fill.stock.shadow`, `signal.final.stock.shadow`) and republishes dashboard-native state (positions/trades/signals/status) via the existing `TradingStatePublisher` + sends important-only Telegram alerts — keeping the React Cockpit and operator alerting working through the M5 cutover.

**Architecture:** New `services/stock_monitor/` daemon (asyncio: a two-stream consumer task + a periodic status/mark-to-market task). It pairs entry↔exit fills (by code) to build closed trades with PnL, correlates `signal.final` records (by signal_id) to enrich strategy/name, marks positions to market via a read-only `StreamConsumerFeed`, and publishes through `TradingStatePublisher` raw-dict methods. Shadow isolation reuses the built-in `TRADING_STATE_KEY_SUFFIX` (→ `trading:stock:*:shadow`). Telegram is selective (notable exit / health anomaly / daily digest), suppressed-to-log in shadow. The dashboard, `TradingStatePublisher`, and M4 daemons are **unchanged**.

**Tech Stack:** Python 3.11+, asyncio, `redis.asyncio` (streams) + sync `RedisClient` (via TradingStatePublisher), `fakeredis` (tests), pytest.

**Spec:** `docs/superpowers/specs/2026-06-06-stock-monitor-bridge-m5a-design.md`

**PR strategy:** Land as **one PR** (`feat/stock-monitor-bridge-m5a`).

**Out of scope:** the M5d cutover flag-flip / orchestrator shutdown, LLM context (M5b), daily risk reset (M5c), orchestrator reduction (M5e), fill-schema exit_reason/pnl enrichment, equity-timeline/running-totals continuity, trades order_id dedup, futures.

---

## File Structure

**Create:**
- `services/stock_monitor/__init__.py` — empty.
- `services/stock_monitor/serializers.py` — pure parse + dict-builder functions (fill/final record → typed dict; dashboard position/trade/signal dicts).
- `services/stock_monitor/alerts.py` — selective Telegram policy + `AlertSink` (send-or-log by mode).
- `services/stock_monitor/daemon.py` — `StockMonitorDaemon` (consumer + status tasks, pairing, recovery).
- `services/stock_monitor/main.py` — flag-gated entrypoint.
- `config/stock_monitor.yaml` — `stock_monitor.telegram` thresholds.
- `deploy/systemd/kis-stock-monitor-daemon.service` — disabled unit.
- `tests/unit/stock_monitor/__init__.py`, `tests/unit/stock_monitor/test_serializers.py`, `test_alerts.py`, `test_daemon.py`, `test_entrypoint.py`
- `tests/integration/test_stock_monitor_bridge.py`

**Modify:** none (M5a is purely additive — dashboard, `TradingStatePublisher`, M4 daemons untouched).

---

## Task 1: Serializers (pure parse + dict builders) + config

**Files:**
- Create: `services/stock_monitor/__init__.py` (empty), `tests/unit/stock_monitor/__init__.py` (empty)
- Create: `services/stock_monitor/serializers.py`
- Create: `config/stock_monitor.yaml`
- Test: `tests/unit/stock_monitor/test_serializers.py`

Pure functions only (no Redis) so they unit-test trivially. Build the exact dashboard dict shapes that `TradingStateReader` expects (see `shared/streaming/trading_state.py` `_serialize_position`/`_serialize_closed_position`/`publish_signal`).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_monitor/test_serializers.py`:

```python
"""Pure parse + dashboard dict builders for the stock monitor bridge."""

from __future__ import annotations

from services.stock_monitor.serializers import (
    build_position_dict,
    build_signal_dict,
    build_trade_dict,
    parse_fill,
    parse_final_signal,
)


def _enc(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


def _fill(role: str = "entry", side: str = "BUY", price: str = "71000.0") -> dict[bytes, bytes]:
    return _enc({
        "signal_id": "sig-1", "order_id": "VO-1", "symbol": "005930", "side": side,
        "order_type": "market", "requested_price": price, "filled_price": price,
        "tick_size_points": "0.0", "slippage_ticks": "0.0", "quantity": "10",
        "requested_at_ms": "1700000000000", "filled_at_ms": "1700000000000",
        "latency_ms": "0", "venue": "KRX", "trade_role": role, "broker_error_code": "",
    })


def _final() -> dict[bytes, bytes]:
    return _enc({
        "signal_id": "sig-1", "code": "005930", "name": "삼성전자", "strategy": "vr_composite",
        "direction": "long", "price": "71000.0", "quantity": "10", "confidence": "0.62",
        "generated_at_ms": "1700000000000", "metadata_json": "{}",
        "size_multiplier": "1.0", "filtered_at_ms": "1700000000000",
    })


def test_parse_fill() -> None:
    f = parse_fill(_fill(role="entry"))
    assert f["code"] == "005930" and f["trade_role"] == "entry"
    assert f["filled_price"] == 71000.0 and f["quantity"] == 10
    assert f["signal_id"] == "sig-1"


def test_parse_final_signal() -> None:
    s = parse_final_signal(_final())
    assert s["code"] == "005930" and s["strategy"] == "vr_composite"
    assert s["name"] == "삼성전자" and s["direction"] == "long"


def test_build_position_dict_enriches_from_meta() -> None:
    f = parse_fill(_fill(role="entry"))
    meta = {"strategy": "vr_composite", "name": "삼성전자"}
    p = build_position_dict(f, meta, fee_rate=0.003)
    assert p["id"] == "005930" and p["code"] == "005930"
    assert p["strategy"] == "vr_composite" and p["name"] == "삼성전자"
    assert p["side"] == "long" and p["quantity"] == 10
    assert p["entry_price"] == 71000.0 and p["current_price"] == 71000.0
    assert p["unrealized_pnl"] == 0.0 and p["state"] == "survival"
    assert p["fee_rate"] == 0.003
    assert isinstance(p["entry_time"], str) and p["entry_time"]


def test_build_position_dict_missing_meta_graceful() -> None:
    f = parse_fill(_fill(role="entry"))
    p = build_position_dict(f, {}, fee_rate=0.003)
    assert p["strategy"] == "" and p["name"] == ""  # graceful empty


def test_build_trade_dict_pnl() -> None:
    entry = {
        "code": "005930", "name": "삼성전자", "strategy": "vr_composite",
        "entry_price": 71000.0, "entry_time": "2023-11-14T22:13:20+00:00",
    }
    exit_fill = parse_fill(role="exit", side="SELL", price="73000.0")
    exit_fill = parse_fill(_fill(role="exit", side="SELL", price="73000.0"))
    # round-trip fee at 0.003: gross 2000*10=20000 - (71000+73000)*10*0.0015 = 20000-2160 = 17840
    t = build_trade_dict(entry, exit_fill, pnl=17840.0, fee_rate=0.003)
    assert t["symbol"] == "005930" and t["side"] == "long"
    assert t["entry_price"] == 71000.0 and t["exit_price"] == 73000.0
    assert t["pnl"] == 17840.0
    assert round(t["pnl_pct"], 4) == round((73000 - 71000) / 71000 * 100, 4)
    assert t["strategy"] == "vr_composite" and t["exit_reason"] == "exit"


def test_build_signal_dict() -> None:
    s = build_signal_dict(parse_final_signal(_final()))
    assert s["symbol"] == "005930" and s["strategy"] == "vr_composite"
    assert s["side"] == "long" and s["signal_type"] == "long"
    assert s["confidence"] == 0.62 and s["executed"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_monitor/test_serializers.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

Create `services/stock_monitor/__init__.py` (empty), `tests/unit/stock_monitor/__init__.py` (empty).

Create `config/stock_monitor.yaml`:

```yaml
# Stock monitor / observability bridge (M5a) — selective Telegram policy.
stock_monitor:
  telegram:
    pnl_alert_pct: 3.0            # notify only on exits with |pnl%| >= 3%
    health_stale_seconds: 600     # no fills processed for 10min during market hours -> anomaly
    health_cooldown_seconds: 1800 # min gap between repeated health alerts
    digest_time_kst: "15:40"      # one daily session digest
```

Create `services/stock_monitor/serializers.py`:

```python
"""Pure parsers + dashboard dict builders for the stock monitor bridge.

Translates the decoupled daemon stream records (order.fill.stock.* /
signal.final.stock.*) into the dashboard-native dict shapes the React Cockpit
reads via TradingStateReader (mirrors TradingStatePublisher._serialize_*).
No Redis / I/O — pure functions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _s(fields: dict[bytes, bytes], key: str) -> str:
    raw = fields.get(key.encode(), b"")
    return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)


def _ms_to_iso(ms: str) -> str:
    """Epoch-ms string -> tz-aware ISO; empty -> current UTC."""
    if not ms:
        return datetime.now(UTC).isoformat()
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=UTC).isoformat()
    except (TypeError, ValueError):
        return datetime.now(UTC).isoformat()


def parse_fill(fields: dict[bytes, bytes]) -> dict[str, Any]:
    """Parse an order.fill.stock.* record (FillLogger schema)."""
    return {
        "signal_id": _s(fields, "signal_id"),
        "order_id": _s(fields, "order_id"),
        "code": _s(fields, "symbol"),
        "side": _s(fields, "side"),
        "filled_price": float(_s(fields, "filled_price") or 0.0),
        "quantity": int(float(_s(fields, "quantity") or 0)),
        "trade_role": _s(fields, "trade_role"),
        "filled_at_ms": _s(fields, "filled_at_ms"),
    }


def parse_final_signal(fields: dict[bytes, bytes]) -> dict[str, Any]:
    """Parse a signal.final.stock.* record (M4-P candidate + M4-R fields)."""
    return {
        "signal_id": _s(fields, "signal_id"),
        "code": _s(fields, "code"),
        "name": _s(fields, "name"),
        "strategy": _s(fields, "strategy"),
        "direction": _s(fields, "direction") or "long",
        "price": float(_s(fields, "price") or 0.0),
        "confidence": float(_s(fields, "confidence") or 0.0),
        "generated_at_ms": _s(fields, "generated_at_ms"),
    }


def build_position_dict(
    fill: dict[str, Any], meta: dict[str, Any], *, fee_rate: float
) -> dict[str, Any]:
    """Dashboard open-position dict (mirrors TradingStatePublisher._serialize_position)."""
    code = fill["code"]
    entry = fill["filled_price"]
    return {
        "id": code,
        "code": code,
        "name": meta.get("name", ""),
        "side": "long",
        "quantity": fill["quantity"],
        "entry_price": entry,
        "current_price": entry,
        "unrealized_pnl": 0.0,
        "pnl_pct": 0.0,
        "entry_time": _ms_to_iso(fill["filled_at_ms"]),
        "strategy": meta.get("strategy", ""),
        "state": "survival",
        "highest_price": entry,
        "lowest_price": entry,
        "fee_rate": fee_rate,
        "stop_price": None,
        "client_order_id": fill["signal_id"],
    }


def build_trade_dict(
    entry: dict[str, Any], exit_fill: dict[str, Any], *, pnl: float, fee_rate: float
) -> dict[str, Any]:
    """Dashboard closed-trade dict (mirrors _serialize_closed_position)."""
    ep = float(entry["entry_price"])
    xp = float(exit_fill["filled_price"])
    qty = exit_fill["quantity"]
    pnl_pct = ((xp - ep) / ep * 100) if ep else 0.0
    return {
        "id": exit_fill["order_id"] or exit_fill["signal_id"],
        "symbol": entry["code"],
        "name": entry.get("name", ""),
        "side": "long",
        "quantity": qty,
        "entry_price": ep,
        "exit_price": xp,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "strategy": entry.get("strategy", ""),
        "entry_time": entry.get("entry_time", ""),
        "exit_time": _ms_to_iso(exit_fill["filled_at_ms"]),
        "exit_reason": "exit",  # fill schema carries no exit reason (spec §5.6)
    }


def build_signal_dict(sig: dict[str, Any]) -> dict[str, Any]:
    """Dashboard signal dict (mirrors TradingStatePublisher.publish_signal data)."""
    return {
        "id": sig["signal_id"],
        "symbol": sig["code"],
        "name": sig["name"],
        "side": sig["direction"],
        "signal_type": sig["direction"],
        "strategy": sig["strategy"],
        "price": sig["price"],
        "confidence": sig["confidence"],
        "timestamp": _ms_to_iso(sig["generated_at_ms"]),
        "executed": True,
        "reason": "",
        "stage": "",
    }
```

Note: the test has a duplicate `exit_fill = parse_fill(...)` line — keep the second (correct `_fill(...)` form); delete the first stray line when copying.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_monitor/test_serializers.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
.venv/bin/black services/stock_monitor tests/unit/stock_monitor
.venv/bin/ruff check --fix services/stock_monitor tests/unit/stock_monitor
.venv/bin/mypy services/stock_monitor/serializers.py
git add services/stock_monitor/__init__.py services/stock_monitor/serializers.py config/stock_monitor.yaml tests/unit/stock_monitor/
git commit -m "feat(m5a): stock monitor serializers (daemon record -> dashboard dicts) + config"
```

---

## Task 2: Selective Telegram alert policy

**Files:**
- Create: `services/stock_monitor/alerts.py`
- Test: `tests/unit/stock_monitor/test_alerts.py`

Important-only policy (spec §7): no per-fill alerts. `AlertSink` decides whether an event is alert-worthy, then either sends (live) or logs a single `would-alert` line (shadow). The session digest is accumulated and emitted on demand.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_monitor/test_alerts.py`:

```python
"""Selective Telegram policy: no per-fill spam; notable exits / health / digest only."""

from __future__ import annotations

import pytest

from services.stock_monitor.alerts import AlertSink, SessionDigest


class _FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_message(self, message: str, **kwargs: object) -> None:
        self.sent.append(message)


@pytest.mark.asyncio
async def test_entry_never_alerts() -> None:
    n = _FakeNotifier()
    sink = AlertSink(notifier=n, mode="live", pnl_alert_pct=3.0)
    await sink.on_entry(code="005930", strategy="vr", quantity=10, price=71000.0)
    assert n.sent == []  # entries are routine -> never alert


@pytest.mark.asyncio
async def test_small_exit_not_alerted_big_exit_alerted() -> None:
    n = _FakeNotifier()
    sink = AlertSink(notifier=n, mode="live", pnl_alert_pct=3.0)
    await sink.on_exit(code="005930", pnl=1000.0, pnl_pct=1.0)   # below threshold
    assert n.sent == []
    await sink.on_exit(code="005930", pnl=-50000.0, pnl_pct=-5.0)  # above threshold
    assert len(n.sent) == 1 and "005930" in n.sent[0]


@pytest.mark.asyncio
async def test_shadow_mode_suppresses_to_log(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    n = _FakeNotifier()
    sink = AlertSink(notifier=n, mode="shadow", pnl_alert_pct=3.0)
    with caplog.at_level(logging.INFO):
        await sink.on_exit(code="005930", pnl=-50000.0, pnl_pct=-5.0)
    assert n.sent == []  # shadow never sends
    assert any("would-alert" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_digest_aggregates_and_emits() -> None:
    n = _FakeNotifier()
    sink = AlertSink(notifier=n, mode="live", pnl_alert_pct=3.0)
    sink.digest.add(pnl=1000.0)
    sink.digest.add(pnl=-500.0)
    sink.digest.add(pnl=2000.0)
    await sink.emit_digest(open_count=2)
    assert len(n.sent) == 1
    msg = n.sent[0]
    assert "3" in msg  # trade count
    assert "2500" in msg or "2,500" in msg  # net pnl


def test_digest_reset() -> None:
    d = SessionDigest()
    d.add(pnl=100.0)
    d.add(pnl=-50.0)
    assert d.trades == 2 and d.realized_pnl == 50.0 and d.wins == 1
    d.reset()
    assert d.trades == 0 and d.realized_pnl == 0.0 and d.wins == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_monitor/test_alerts.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

Create `services/stock_monitor/alerts.py`:

```python
"""Selective, important-only Telegram alerting for the stock monitor bridge.

Policy (spec §7): NO per-fill alerts. Only:
  1. notable exit  — |pnl%| >= pnl_alert_pct
  2. health anomaly — emitted by the daemon (cooldown-gated) via send_health()
  3. session digest — one aggregate per day via emit_digest()

In ``shadow`` mode nothing is sent; each alert-worthy event logs one
``would-alert`` line (so even the logs are not per-fill noise). In ``live``
mode the wrapped notifier is used.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SessionDigest:
    """Accumulates one trading session's realized results for the daily digest."""

    trades: int = 0
    realized_pnl: float = 0.0
    wins: int = 0

    def add(self, *, pnl: float) -> None:
        self.trades += 1
        self.realized_pnl += pnl
        if pnl > 0:
            self.wins += 1

    def reset(self) -> None:
        self.trades = 0
        self.realized_pnl = 0.0
        self.wins = 0


class AlertSink:
    """Decides + dispatches important-only alerts (send in live, log in shadow)."""

    def __init__(
        self,
        *,
        notifier: Any | None,
        mode: str,
        pnl_alert_pct: float,
    ) -> None:
        self.notifier = notifier
        self.mode = mode
        self.pnl_alert_pct = pnl_alert_pct
        self.digest = SessionDigest()

    async def _dispatch(self, message: str) -> None:
        if self.mode == "live" and self.notifier is not None:
            try:
                await self.notifier.send_message(message)
            except Exception:
                logger.warning("telegram send failed", exc_info=True)
        else:
            logger.info("would-alert: %s", message.replace("\n", " | "))

    async def on_entry(self, **_: Any) -> None:
        """Entries are routine — never alerted (digest counts them at exit)."""
        return None

    async def on_exit(self, *, code: str, pnl: float, pnl_pct: float) -> None:
        if abs(pnl_pct) < self.pnl_alert_pct:
            return  # routine exit -> digest only
        icon = "🟢" if pnl >= 0 else "🔴"
        await self._dispatch(
            f"{icon} <b>주목 청산</b> {code}\nPnL {pnl:,.0f}원 ({pnl_pct:+.2f}%)"
        )

    async def send_health(self, message: str) -> None:
        await self._dispatch(f"⚠️ <b>헬스 이상</b>\n{message}")

    async def emit_digest(self, *, open_count: int) -> None:
        d = self.digest
        win_rate = (d.wins / d.trades * 100) if d.trades else 0.0
        await self._dispatch(
            f"📊 <b>세션 다이제스트</b>\n"
            f"거래 {d.trades}건 · 실현 {d.realized_pnl:,.0f}원 · "
            f"승률 {win_rate:.0f}% · 미청산 {open_count}건"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_monitor/test_alerts.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
.venv/bin/black services/stock_monitor tests/unit/stock_monitor
.venv/bin/ruff check --fix services/stock_monitor tests/unit/stock_monitor
.venv/bin/mypy services/stock_monitor/alerts.py
git add services/stock_monitor/alerts.py tests/unit/stock_monitor/test_alerts.py
git commit -m "feat(m5a): selective Telegram policy (notable exit / health / digest; shadow-suppress)"
```

---

## Task 3: `StockMonitorDaemon` (consumer + status + pairing + recovery)

**Files:**
- Create: `services/stock_monitor/daemon.py`
- Test: `tests/unit/stock_monitor/test_daemon.py`

The core. Consumes fill+signal streams (consumer group), pairs entry↔exit, publishes via `TradingStatePublisher` (raw-dict), marks-to-market, recovers `_open` on startup. `TradingStatePublisher` uses the sync `RedisClient` singleton via the module-level `shared.streaming.trading_state._get_redis` — tests patch that to a fakeredis sharing the async stream server.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_monitor/test_daemon.py`:

```python
"""StockMonitorDaemon: entry->position, exit->trade(pnl), signal->signals; recovery; MTM."""

from __future__ import annotations

import json

import fakeredis
import fakeredis.aioredis
import pytest

import shared.streaming.trading_state as ts
from services.stock_monitor.daemon import StockMonitorDaemon
from shared.streaming.trading_state import TradingStatePublisher, TradingStateReader


def _enc(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


def _fill(role: str, side: str, price: str, code: str = "005930") -> dict[str, str]:
    return {
        "signal_id": f"sig-{code}", "order_id": f"VO-{role}", "symbol": code, "side": side,
        "order_type": "market", "requested_price": price, "filled_price": price,
        "tick_size_points": "0.0", "slippage_ticks": "0.0", "quantity": "10",
        "requested_at_ms": "1700000000000", "filled_at_ms": "1700000000000",
        "latency_ms": "0", "venue": "KRX", "trade_role": role, "broker_error_code": "",
    }


def _final(code: str = "005930") -> dict[str, str]:
    return {
        "signal_id": f"sig-{code}", "code": code, "name": "삼성전자", "strategy": "vr_composite",
        "direction": "long", "price": "71000.0", "quantity": "10", "confidence": "0.62",
        "generated_at_ms": "1700000000000", "metadata_json": "{}",
        "size_multiplier": "1.0", "filtered_at_ms": "1700000000000",
    }


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


@pytest.fixture()
def wired(monkeypatch):
    server = fakeredis.FakeServer()
    redis = fakeredis.aioredis.FakeRedis(server=server, db=1)
    sync = fakeredis.FakeStrictRedis(server=server, db=1)
    # TradingStatePublisher/Reader use the module-level _get_redis (sync singleton).
    monkeypatch.setattr(ts, "_get_redis", lambda: sync)
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "shadow")
    daemon = StockMonitorDaemon(
        redis=redis,
        feed=_FakeFeed(),
        publisher=TradingStatePublisher(asset_class="stock"),
        alert_sink=None,
        positions_key="trading:stock:positions",
        fill_stream="order.fill.stock.shadow",
        signal_stream="signal.final.stock.shadow",
        consumer_group="stock_monitor",
        worker_id="test",
        fee_rate=0.003,
        status_interval=5.0,
    )
    return daemon, redis, TradingStateReader(asset_class="stock")


@pytest.mark.asyncio
async def test_signal_then_entry_then_exit(wired) -> None:
    daemon, redis, reader = wired

    await daemon.handle_signal(_enc(_final()))
    sigs = reader.get_signals()
    assert len(sigs) == 1 and sigs[0]["strategy"] == "vr_composite"

    await daemon.handle_fill(_enc(_fill("entry", "BUY", "71000.0")))
    positions = reader.get_positions()
    assert len(positions) == 1
    assert positions[0]["code"] == "005930" and positions[0]["strategy"] == "vr_composite"

    await daemon.handle_fill(_enc(_fill("exit", "SELL", "73000.0")))
    assert reader.get_positions() == []  # closed
    trades = reader.get_trades()
    assert len(trades) == 1
    # pnl = (73000-71000)*10 - (71000+73000)*10*0.0015 = 20000 - 2160 = 17840
    assert round(trades[0]["pnl"], 0) == 17840.0
    assert trades[0]["strategy"] == "vr_composite"


@pytest.mark.asyncio
async def test_exit_without_entry_skips_trade(wired) -> None:
    daemon, redis, reader = wired
    await daemon.handle_fill(_enc(_fill("exit", "SELL", "73000.0")))
    assert reader.get_trades() == []  # no entry paired -> no bogus pnl


@pytest.mark.asyncio
async def test_recover_open_from_positions_hash(wired) -> None:
    daemon, redis, reader = wired
    # M4-O/X working-store record (opened_at_ms signature).
    await redis.hset("trading:stock:positions", "005930", json.dumps({
        "code": "005930", "entry_price": 71000.0, "quantity": 10,
        "opened_at_ms": 1_700_000_000_000, "state": "SURVIVAL", "signal_id": "sig-005930",
    }))
    await daemon.recover_open_positions()
    # an exit fill now pairs against the recovered entry
    await daemon.handle_fill(_enc(_fill("exit", "SELL", "73000.0")))
    trades = reader.get_trades()
    assert len(trades) == 1 and trades[0]["entry_price"] == 71000.0


@pytest.mark.asyncio
async def test_mark_to_market(wired) -> None:
    daemon, redis, reader = wired
    await daemon.handle_signal(_enc(_final()))
    await daemon.handle_fill(_enc(_fill("entry", "BUY", "71000.0")))
    daemon.feed.prices["005930"] = {"close": 72000.0}
    await daemon.publish_status_and_mtm()
    pos = reader.get_positions()[0]
    assert pos["current_price"] == 72000.0
    assert pos["unrealized_pnl"] == (72000.0 - 71000.0) * 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_monitor/test_daemon.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

Create `services/stock_monitor/daemon.py`:

```python
"""Stock monitor / observability bridge daemon (M5a, shadow-first).

Consumes the decoupled stock daemon streams and republishes dashboard-native
state (positions/trades/signals/status) via TradingStatePublisher, plus
important-only alerts. Pairs entry<->exit fills (by code) for closed trades,
correlates final signals (by signal_id) for strategy/name, marks positions to
market, and recovers open state from the daemon positions hash on startup.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import OrderedDict
from typing import Any

from services.stock_exit.positions import parse_position_record
from services.stock_monitor.serializers import (
    build_position_dict,
    build_signal_dict,
    build_trade_dict,
    parse_fill,
    parse_final_signal,
)

logger = logging.getLogger(__name__)


class StockMonitorDaemon:
    """Bridge daemon: daemon streams -> dashboard keys + alerts."""

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
        fee_rate: float,
        status_interval: float,
        signal_meta_max: int = 1000,
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
        self.fee_rate = fee_rate
        self.status_interval = status_interval
        self.signal_meta_max = signal_meta_max
        self._open: dict[str, dict[str, Any]] = {}
        self._signal_meta: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._stop = asyncio.Event()

    # -- handlers --------------------------------------------------------- #

    async def handle_signal(self, fields: dict[bytes, bytes]) -> None:
        sig = parse_final_signal(fields)
        self._signal_meta[sig["signal_id"]] = {
            "strategy": sig["strategy"], "name": sig["name"], "code": sig["code"],
        }
        while len(self._signal_meta) > self.signal_meta_max:
            self._signal_meta.popitem(last=False)
        self.publisher.publish_raw_signal(build_signal_dict(sig))

    async def handle_fill(self, fields: dict[bytes, bytes]) -> None:
        fill = parse_fill(fields)
        code = fill["code"]
        if fill["trade_role"] == "entry":
            meta = self._signal_meta.get(fill["signal_id"], {})
            self.publisher.publish_raw_position(
                code, build_position_dict(fill, meta, fee_rate=self.fee_rate)
            )
            self._open[code] = {
                "code": code,
                "name": meta.get("name", ""),
                "strategy": meta.get("strategy", ""),
                "entry_price": fill["filled_price"],
                "entry_time": build_position_dict(fill, meta, fee_rate=self.fee_rate)[
                    "entry_time"
                ],
            }
            if self.alert_sink is not None:
                await self.alert_sink.on_entry(
                    code=code, strategy=meta.get("strategy", ""),
                    quantity=fill["quantity"], price=fill["filled_price"],
                )
        elif fill["trade_role"] == "exit":
            entry = self._open.pop(code, None)
            if entry is None:
                logger.warning(
                    "exit fill for %s with no open entry; skipping trade", code
                )
                self.publisher.remove_position(code)
                return
            ep, xp, qty = entry["entry_price"], fill["filled_price"], fill["quantity"]
            pnl = (xp - ep) * qty - (ep + xp) * qty * (self.fee_rate / 2)
            trade = build_trade_dict(entry, fill, pnl=pnl, fee_rate=self.fee_rate)
            self.publisher.publish_raw_trade(trade)
            self.publisher.remove_position(code)
            if self.alert_sink is not None:
                self.alert_sink.digest.add(pnl=pnl)
                await self.alert_sink.on_exit(
                    code=code, pnl=pnl, pnl_pct=trade["pnl_pct"]
                )

    # -- recovery + status ------------------------------------------------ #

    async def recover_open_positions(self) -> None:
        try:
            raw = await self.redis.hgetall(self.positions_key)
        except Exception:
            logger.warning("recover read failed; starting empty", exc_info=True)
            return
        for value in raw.values():
            rec = parse_position_record(value)
            if rec is None:
                continue  # skip foreign (orchestrator) entries
            code = str(rec["code"])
            self._open[code] = {
                "code": code,
                "name": str(rec.get("name", "")),
                "strategy": str(rec.get("strategy", "")),
                "entry_price": float(rec["entry_price"]),
                "entry_time": "",
            }
            # re-publish the dashboard open-position snapshot
            self.publisher.publish_raw_position(code, {
                "id": code, "code": code, "name": self._open[code]["name"],
                "side": "long", "quantity": int(rec["quantity"]),
                "entry_price": float(rec["entry_price"]),
                "current_price": float(rec["entry_price"]),
                "unrealized_pnl": 0.0, "pnl_pct": 0.0, "entry_time": "",
                "strategy": self._open[code]["strategy"], "state": "survival",
                "highest_price": float(rec.get("high_water", rec["entry_price"])),
                "lowest_price": float(rec.get("low_water", rec["entry_price"])),
                "fee_rate": self.fee_rate, "stop_price": None,
                "client_order_id": str(rec.get("signal_id", "")),
            })

    async def publish_status_and_mtm(self) -> None:
        for code, entry in self._open.items():
            price = await self.feed.get_current_price(code)
            close = price.get("close")
            if close is None:
                continue
            close = float(close)
            qty_pnl = (close - entry["entry_price"])
            self.publisher.publish_raw_position(code, {
                "id": code, "code": code, "name": entry["name"], "side": "long",
                "quantity": 0, "entry_price": entry["entry_price"],
                "current_price": close,
                "unrealized_pnl": qty_pnl * self._open_qty(code),
                "pnl_pct": (qty_pnl / entry["entry_price"] * 100) if entry["entry_price"] else 0.0,
                "entry_time": entry.get("entry_time", ""),
                "strategy": entry["strategy"], "state": "survival",
                "highest_price": entry["entry_price"], "lowest_price": entry["entry_price"],
                "fee_rate": self.fee_rate, "stop_price": None, "client_order_id": "",
            })
        self.publisher.publish_status({
            "open_positions": len(self._open),
            "worker_id": self.worker_id,
            "source": "stock_monitor",
        })

    def _open_qty(self, code: str) -> int:
        return int(self._open.get(code, {}).get("quantity", 0) or 0)

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
                stream_name = stream.decode() if isinstance(stream, bytes) else str(stream)
                for msg_id, data in msgs:
                    try:
                        if stream_name == self.fill_stream:
                            await self.handle_fill(data)
                        else:
                            await self.handle_signal(data)
                    except Exception:
                        logger.exception("handler error; dropping (poison-pill)")
                    await self.redis.xack(stream_name, self.consumer_group, msg_id)

    async def _status_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.publish_status_and_mtm()
            except Exception:
                logger.exception("status loop error; continuing")
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self.status_interval)
```

Note: `_open` needs `quantity` for MTM unrealized PnL. In `handle_fill` entry, also store `"quantity": fill["quantity"]` in the `_open[code]` dict, and in `recover_open_positions` store `"quantity": int(rec["quantity"])`. Add that field (the test `test_mark_to_market` asserts `unrealized_pnl == 1000*10`). Update both `_open[code] = {...}` literals to include `"quantity"`, and simplify `_open_qty` to read it. (Implementer: ensure `quantity` is in `_open` and used by MTM.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_monitor/test_daemon.py -v`
Expected: PASS (4 passed). Fix the `_open` `quantity` wiring per the note until `test_mark_to_market` passes.

- [ ] **Step 5: Commit**

```bash
.venv/bin/black services/stock_monitor tests/unit/stock_monitor
.venv/bin/ruff check --fix services/stock_monitor tests/unit/stock_monitor
.venv/bin/mypy services/stock_monitor/daemon.py
git add services/stock_monitor/daemon.py tests/unit/stock_monitor/test_daemon.py
git commit -m "feat(m5a): StockMonitorDaemon (pair fills -> dashboard state + MTM + recovery)"
```

---

## Task 4: Flag-gated entrypoint + systemd

**Files:**
- Create: `services/stock_monitor/main.py`
- Create: `deploy/systemd/kis-stock-monitor-daemon.service`
- Test: `tests/unit/stock_monitor/test_entrypoint.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_monitor/test_entrypoint.py`:

```python
"""M5a flag routing: off -> inert; stream mapping; shadow forces key-suffix; config loads."""

from __future__ import annotations

import asyncio
import os

import pytest

import services.stock_monitor.main as m


def test_resolve_mode_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STOCK_MONITOR_DAEMON", raising=False)
    assert m._resolve_mode() == "off"


def test_streams_for_shadow_and_live() -> None:
    assert m._streams_for("shadow") == ("order.fill.stock.shadow", "signal.final.stock.shadow")
    assert m._streams_for("live") == ("order.fill.stock", "signal.final.stock")


def test_off_mode_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_MONITOR_DAEMON", "off")
    assert asyncio.run(m._build_and_run()) == 0


def test_shadow_forces_key_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRADING_STATE_KEY_SUFFIX", raising=False)
    m._ensure_shadow_isolation("shadow")
    assert os.environ["TRADING_STATE_KEY_SUFFIX"] == "shadow"


def test_live_leaves_suffix_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRADING_STATE_KEY_SUFFIX", raising=False)
    m._ensure_shadow_isolation("live")
    assert os.environ.get("TRADING_STATE_KEY_SUFFIX", "") == ""


def test_config_loads() -> None:
    from shared.config.loader import ConfigLoader

    tg = ConfigLoader.load("stock_monitor.yaml").get("stock_monitor", {}).get("telegram", {})
    assert tg.get("pnl_alert_pct") == 3.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_monitor/test_entrypoint.py -v`
Expected: FAIL (AttributeError).

- [ ] **Step 3: Implement**

Create `services/stock_monitor/main.py`:

```python
"""Stock monitor bridge entrypoint (flag-gated, shadow-first, default-off).

off (default): inert. shadow: publish to trading:stock:*:shadow + suppress
Telegram-to-log. live (M5d): live keys + real Telegram.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket

logger = logging.getLogger(__name__)


def _resolve_mode() -> str:
    return os.getenv("STOCK_MONITOR_DAEMON", "off").strip().lower()


def _streams_for(mode: str) -> tuple[str, str]:
    if mode == "shadow":
        return "order.fill.stock.shadow", "signal.final.stock.shadow"
    return "order.fill.stock", "signal.final.stock"


def _ensure_shadow_isolation(mode: str) -> None:
    """Fail-safe: in shadow, force the dashboard key suffix if the operator
    forgot to set it, so M5a can never clobber the orchestrator's live keys."""
    if mode == "shadow" and not os.environ.get("TRADING_STATE_KEY_SUFFIX", "").strip():
        os.environ["TRADING_STATE_KEY_SUFFIX"] = "shadow"


async def _build_and_run() -> int:
    import signal as signal_mod

    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()
    if mode not in ("shadow", "live"):
        logger.info("STOCK_MONITOR_DAEMON=%s (off) — daemon inert, exiting", mode)
        await redis_client.aclose()
        return 0

    _ensure_shadow_isolation(mode)

    from services.stock_monitor.alerts import AlertSink
    from services.stock_monitor.daemon import StockMonitorDaemon
    from services.trading.stream_consumer_feed import StreamConsumerFeed
    from shared.config.loader import ConfigLoader
    from shared.notification.telegram import notifier_for_domain
    from shared.streaming.trading_state import TradingStatePublisher

    fill_default, signal_default = _streams_for(mode)
    fill_stream = os.environ.get("STOCK_FILL_STREAM", fill_default)
    signal_stream = os.environ.get("STOCK_FINAL_STREAM", signal_default)
    positions_key = os.environ.get("STOCK_POSITIONS_KEY", "trading:stock:positions")
    status_interval = float(os.environ.get("STOCK_MONITOR_STATUS_INTERVAL", "5"))
    tick_stream = os.environ.get("STOCK_TICK_STREAM", "market:ticks")

    fee_rate = float(
        ConfigLoader.load("stock_exit.yaml").get("stock_exit", {}).get("fee_rate", 0.003)
    )
    tg = ConfigLoader.load("stock_monitor.yaml").get("stock_monitor", {}).get("telegram", {})

    notifier = notifier_for_domain("stock") if mode == "live" else None
    alert_sink = AlertSink(
        notifier=notifier, mode=mode, pnl_alert_pct=float(tg.get("pnl_alert_pct", 3.0))
    )

    feed = StreamConsumerFeed(redis=redis_client, stream=tick_stream)
    publisher = TradingStatePublisher(asset_class="stock")

    daemon = StockMonitorDaemon(
        redis=redis_client,
        feed=feed,
        publisher=publisher,
        alert_sink=alert_sink,
        positions_key=positions_key,
        fill_stream=fill_stream,
        signal_stream=signal_stream,
        consumer_group="stock_monitor",
        worker_id=f"stock-monitor-{socket.gethostname()}-{os.getpid()}",
        fee_rate=fee_rate,
        status_interval=status_interval,
        signal_meta_max=int(os.environ.get("STOCK_MONITOR_SIGNAL_META_MAX", "1000")),
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    logger.info("stock monitor starting mode=%s suffix=%s",
                mode, os.environ.get("TRADING_STATE_KEY_SUFFIX", ""))
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

Create `deploy/systemd/kis-stock-monitor-daemon.service`:

```ini
[Unit]
Description=KIS Stock Monitor Bridge (daemon streams -> dashboard state + alerts)
After=network-online.target redis-server.service
Wants=network-online.target
Requires=redis-server.service

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/project/kis_unified_sts
EnvironmentFile=/home/deploy/project/kis_unified_sts/.env
Environment=STOCK_MONITOR_DAEMON=shadow
Environment=TRADING_STATE_KEY_SUFFIX=shadow
ExecStart=/home/deploy/project/kis_unified_sts/.venv/bin/python -m services.stock_monitor.main
Restart=on-failure
RestartSec=10s
TimeoutStopSec=30s
KillSignal=SIGTERM

# Delivered DISABLED. Enabling is an operator step (shadow validation gate).
[Install]
WantedBy=multi-user.target
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_monitor/test_entrypoint.py -v`
Expected: PASS (6 passed). The off-mode test must pass without a running redis (lazy aioredis pool).

- [ ] **Step 5: Commit**

```bash
.venv/bin/black services/stock_monitor tests/unit/stock_monitor
.venv/bin/ruff check --fix services/stock_monitor tests/unit/stock_monitor
.venv/bin/mypy services/stock_monitor/main.py
git add services/stock_monitor/main.py deploy/systemd/kis-stock-monitor-daemon.service tests/unit/stock_monitor/test_entrypoint.py
git commit -m "feat(m5a): flag-gated entrypoint (fail-safe shadow isolation) + disabled systemd unit"
```

---

## Task 5: e2e integration

**Files:**
- Test: `tests/integration/test_stock_monitor_bridge.py`

Drives the real `StockMonitorDaemon` handlers over a shared fakeredis (async streams + sync TradingStatePublisher), proving the dashboard (via `TradingStateReader`) sees the bridged state in the `:shadow` namespace.

- [ ] **Step 1: Write the test**

Create `tests/integration/test_stock_monitor_bridge.py`:

```python
"""e2e: daemon shadow streams -> StockMonitorDaemon -> dashboard :shadow keys (read-back)."""

from __future__ import annotations

import fakeredis
import fakeredis.aioredis
import pytest

import shared.streaming.trading_state as ts
from services.stock_monitor.daemon import StockMonitorDaemon
from shared.streaming.trading_state import TradingStatePublisher, TradingStateReader


def _enc(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


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
async def test_bridge_publishes_dashboard_state_in_shadow_namespace(monkeypatch) -> None:
    server = fakeredis.FakeServer()
    redis = fakeredis.aioredis.FakeRedis(server=server, db=1)
    sync = fakeredis.FakeStrictRedis(server=server, db=1)
    monkeypatch.setattr(ts, "_get_redis", lambda: sync)
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "shadow")

    daemon = StockMonitorDaemon(
        redis=redis, feed=_FakeFeed(), publisher=TradingStatePublisher(asset_class="stock"),
        alert_sink=None, positions_key="trading:stock:positions",
        fill_stream="order.fill.stock.shadow", signal_stream="signal.final.stock.shadow",
        consumer_group="stock_monitor", worker_id="e2e", fee_rate=0.003, status_interval=5.0,
    )

    def _fill(role, side, price):
        return _enc({
            "signal_id": "sig-1", "order_id": f"VO-{role}", "symbol": "005930", "side": side,
            "order_type": "market", "requested_price": price, "filled_price": price,
            "tick_size_points": "0.0", "slippage_ticks": "0.0", "quantity": "10",
            "requested_at_ms": "1700000000000", "filled_at_ms": "1700000000000",
            "latency_ms": "0", "venue": "KRX", "trade_role": role, "broker_error_code": "",
        })

    final = _enc({
        "signal_id": "sig-1", "code": "005930", "name": "삼성전자", "strategy": "vr_composite",
        "direction": "long", "price": "71000.0", "quantity": "10", "confidence": "0.62",
        "generated_at_ms": "1700000000000", "metadata_json": "{}",
        "size_multiplier": "1.0", "filtered_at_ms": "1700000000000",
    })

    await daemon.handle_signal(final)
    await daemon.handle_fill(_fill("entry", "BUY", "71000.0"))
    await daemon.handle_fill(_fill("exit", "SELL", "73000.0"))

    reader = TradingStateReader(asset_class="stock")
    # dashboard reads the bridged state from the :shadow namespace
    assert reader.get_signals()[0]["strategy"] == "vr_composite"
    assert reader.get_positions() == []  # opened then closed
    trades = reader.get_trades()
    assert len(trades) == 1 and trades[0]["symbol"] == "005930"
    assert round(trades[0]["pnl"], 0) == 17840.0

    # the live (no-suffix) keys are untouched -> orchestrator's dashboard is safe
    assert sync.exists("trading:stock:trades") == 0
    assert sync.exists("trading:stock:trades:shadow") == 1
```

- [ ] **Step 2: Run + iterate**

Run: `.venv/bin/pytest tests/integration/test_stock_monitor_bridge.py -v`
Expected: PASS (1 passed). If the `_get_redis` patch target differs, confirm `TradingStatePublisher`/`TradingStateReader` both call the module-level `shared.streaming.trading_state._get_redis` (they do — patch it once).

- [ ] **Step 3: Commit**

```bash
.venv/bin/black tests/integration/test_stock_monitor_bridge.py
.venv/bin/ruff check --fix tests/integration/test_stock_monitor_bridge.py
git add tests/integration/test_stock_monitor_bridge.py
git commit -m "test(m5a): e2e daemon streams -> dashboard :shadow keys + live keys untouched"
```

---

## Task 6: Full gate + lint + PR

- [ ] **Step 1: Lint/format/type**

```bash
.venv/bin/black services/stock_monitor tests/unit/stock_monitor tests/integration/test_stock_monitor_bridge.py
.venv/bin/ruff check services/stock_monitor tests/unit/stock_monitor tests/integration/test_stock_monitor_bridge.py
.venv/bin/mypy services/stock_monitor
```
Expected: clean (mypy may warn on the known `Redis[Any].aclose` stub gap in `main.py` — acceptable, matches every other service entrypoint).

- [ ] **Step 2: Targeted + regression**

```bash
.venv/bin/pytest tests/unit/stock_monitor tests/integration/test_stock_monitor_bridge.py -v
.venv/bin/pytest tests/ -k "trading_state or dashboard" -q
```
Expected: all PASS (the second proves the untouched dashboard/TradingState path still works).

- [ ] **Step 3: Full gate (CI parity)**

```bash
.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance && .venv/bin/pytest tests/ -m serial -q
```
Expected: green.

- [ ] **Step 4: Push + PR**

```bash
git push -u origin feat/stock-monitor-bridge-m5a
gh pr create --base main --head feat/stock-monitor-bridge-m5a \
  --title "feat(m5a): stock monitor / observability bridge (shadow-first, default off)" \
  --body "$(cat <<'EOF'
## What
The first M5 sub-project: a shadow-first, default-off bridge daemon
(`services/stock_monitor/`) that consumes the decoupled stock daemon streams
(`order.fill.stock.shadow`, `signal.final.stock.shadow`) and republishes the
dashboard-native state (positions/trades/signals/status) via the existing
`TradingStatePublisher` raw-dict methods, plus **important-only** Telegram alerts.
Keeps the React Cockpit + operator alerting working through the M5 cutover.

## Why
M4-P/R/O/X produce fills + a code-keyed positions store, but NOT the
dashboard-native `trading:stock:status/trades/signals` the orchestrator owns.
M5a aggregates them — the prerequisite "eyes" for a safe cutover. It pairs
entry↔exit fills (by code) into closed trades with PnL, correlates final signals
(by signal_id) for strategy/name, marks positions to market, and recovers open
state from the daemon positions hash on restart.

## Shadow isolation + Telegram policy
Shadow publishes to `trading:stock:*:shadow` (built-in `TRADING_STATE_KEY_SUFFIX`,
fail-safe forced in the entrypoint) — never clobbers the orchestrator's live keys,
enabling side-by-side validation. Telegram is **selective** (spec §7): NO per-fill
alerts; only notable exits (|pnl%| ≥ threshold), health anomalies, and a daily
session digest. In shadow, alerts are suppressed to a single `would-alert` log
(also important-only — no per-fill log noise).

## Scope / limitations (v1)
Shadow + live wiring; the actual cutover flag-flip is M5d. Dashboard,
`TradingStatePublisher`, and M4 daemons UNCHANGED. exit_reason absent from the
fill schema → trades carry `"exit"` (follow-up). order_id dedup deferred.

## How tested
Unit (serializers, selective Telegram policy, daemon pairing/recovery/MTM, flag
routing + fail-safe suffix), integration (streams → dashboard `:shadow` keys via
`TradingStateReader`, live keys untouched), full `tests/` gate green, ruff/black clean.

Spec: `docs/superpowers/specs/2026-06-06-stock-monitor-bridge-m5a-design.md`
Plan: `docs/superpowers/plans/2026-06-06-stock-monitor-bridge-m5a.md`

## Follow-ups
M5b (LLM context), M5c (daily reset), M5d (cutover flag-flip + runbook + rollback),
M5e (orchestrator reduction); fill exit_reason enrichment; trades order_id dedup.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Run code review** — `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:**
- §4 module + two-task daemon → Tasks 3/4. ✓
- §4.2 consume/publish mapping → Task 3 handle_fill/handle_signal/status. ✓
- §5 stateful aggregation (pairing, signal_meta, recovery, pnl parity) → Task 3. ✓
- §5.6 exit_reason gap → Task 1 build_trade_dict (`"exit"`). ✓
- §6 shadow isolation (fail-safe suffix) + stream mapping → Task 4. ✓
- §7 selective Telegram (notable exit / health / digest; shadow-suppress) → Task 2 AlertSink. ✓
- §8 flags/config/systemd → Tasks 1/4. ✓
- §9 error handling (poison-pill XACK, fire-and-forget publish, exit-without-entry skip) → Task 3. ✓
- §10 testing (unit + e2e + regression) → Tasks 1–6. ✓
- §11 acceptance (default-off, untouched dashboard/M4, shadow isolation, pnl parity) → Tasks 4/5/6. ✓

**Placeholder scan:** none — complete code in every step. (Task 1 test has a noted stray duplicate line to delete; Task 3 has a noted `quantity`-in-`_open` wiring instruction — both explicit, not placeholders.)

**Type consistency:** `parse_fill`/`parse_final_signal`/`build_position_dict(fill, meta, *, fee_rate)`/`build_trade_dict(entry, exit_fill, *, pnl, fee_rate)`/`build_signal_dict` signatures consistent across Tasks 1/3. `AlertSink(notifier, mode, pnl_alert_pct)` + `on_entry/on_exit/send_health/emit_digest/digest` consistent across Tasks 2/3/4. `StockMonitorDaemon` constructor kwargs match between Task 3 impl, Task 4 entrypoint, Task 5 e2e. `TradingStatePublisher.publish_raw_position/publish_raw_trade/publish_raw_signal/remove_position/publish_status` + `TradingStateReader.get_positions/get_trades/get_signals` match `shared/streaming/trading_state.py`. `_get_redis` patch target correct. `parse_position_record` reused from `services.stock_exit.positions`.

**Open questions resolved:** signal `executed`=True (Task 1); digest reset = daemon-internal (Task 2 `SessionDigest.reset`, emit at digest_time — wired in entrypoint/daemon, display-only); status fields = `{open_positions, worker_id, source}` (Task 3, extendable); order_id dedup deferred (out of scope).
