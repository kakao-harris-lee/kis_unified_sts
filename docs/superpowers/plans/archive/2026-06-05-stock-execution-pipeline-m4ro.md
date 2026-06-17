# Stock Execution Pipeline (M4-R + M4-O) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the stock entry-execution tail of the decoupled stream pipeline — two shadow-first, default-off daemons that consume `signal.candidate.stock.shadow` (M4-P output) → risk filter → `signal.final.stock.shadow` → paper execution → `order.fill.stock.shadow`.

**Architecture:** Two new per-asset daemon modules (`services/stock_risk_filter/`, `services/stock_order_router/`) reuse `StreamStage`, `RiskFilterLayer`, `RuntimeRiskState`, `VirtualBroker`, `FillLogger`, `RuntimeLedger` unchanged. A thin stock codec adapts the M4-P stock candidate schema (no stop/target) into the duck-typed object the 8 risk filters read (they only touch `signal.symbol` and `signal.generated_at`). The merged futures `services/risk_filter` / `services/order_router` daemons are **not touched** (zero regression to the live futures path). M4-X (exit) is a separate spec.

**Tech Stack:** Python 3.11+, asyncio, `redis.asyncio` (DB 1), `fakeredis.aioredis` (tests), Pydantic `ServiceConfigBase`, pytest.

**Spec:** `docs/superpowers/specs/2026-06-05-stock-execution-pipeline-m4ro-design.md`

**PR strategy:** R+O form one testable unit (the e2e test in Task 7 spans both). Land as **one PR**. Tasks 1–4 = M4-R, Tasks 5–6 = M4-O, Task 7 = e2e, Task 8 = gate+PR.

**Out of scope (do not implement):** M4-X exit / ThreeStageExit producer / position close, ATS `VenueRouter`, real KIS stock orders + stock live guard, stock short entry, futures stream `.futures` rename, `signals_all` audit for stock (futures-only Phase 3 audit; stock shadow defers it), the `shared/streaming/daemon_entrypoint.py` DRY extraction (separate chore).

---

## File Structure

**Create:**
- `services/stock_risk_filter/__init__.py` — empty package marker.
- `services/stock_risk_filter/codec.py` — `StockRiskSignal` dataclass + `stock_signal_from_stream_fields()` (inverse of M4-P `candidate.py`). Shared by both daemons.
- `services/stock_risk_filter/main.py` — `StockRiskFilterDaemon(StreamStage)` + flag-gated entrypoint.
- `services/stock_order_router/__init__.py` — empty package marker.
- `services/stock_order_router/main.py` — `StockOrderRouterDaemon(StreamStage)` + flag-gated entrypoint.
- `deploy/systemd/kis-stock-risk-filter.service` — disabled unit.
- `deploy/systemd/kis-stock-order-router.service` — disabled unit.
- `tests/unit/stock_risk_filter/__init__.py`, `tests/unit/stock_risk_filter/test_codec.py`, `test_daemon.py`, `test_entrypoint.py`
- `tests/unit/stock_order_router/__init__.py`, `tests/unit/stock_order_router/test_daemon.py`, `test_entrypoint.py`
- `tests/integration/test_stock_execution_pipeline.py`

**Modify:**
- `shared/risk/config.py` — add `StockRiskConfig` + `load_stock_trading_windows()`.
- `config/risk.yaml` — add `risk_stock:` section + `trading_windows_stock:` list.

---

## Task 1: Stock risk config + trading windows

**Files:**
- Modify: `config/risk.yaml`
- Modify: `shared/risk/config.py` (append after `load_trading_windows`, near line 594+)
- Test: `tests/unit/stock_risk_filter/__init__.py` (create empty), `tests/unit/stock_risk_filter/test_codec.py` will come in Task 2 — for this task create `tests/unit/risk/test_stock_risk_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/risk/test_stock_risk_config.py`:

```python
"""StockRiskConfig loads the risk_stock section; stock trading windows load separately."""

from __future__ import annotations

from shared.risk.config import StockRiskConfig, load_stock_trading_windows


def test_stock_risk_config_loads_risk_stock_section():
    cfg = StockRiskConfig.from_yaml()
    # Stock equity differs from futures; section is risk_stock, not risk.
    assert cfg.account_equity_krw > 0
    assert cfg.max_daily_trades >= 1
    # Field set is inherited from FuturesRiskConfig (asset-neutral params).
    assert hasattr(cfg, "consecutive_loss_soft_threshold")
    assert hasattr(cfg, "max_spread_ticks")


def test_stock_trading_windows_are_korean_equity_session():
    windows = load_stock_trading_windows()
    assert isinstance(windows, list)
    assert windows, "stock trading windows must be non-empty"
    # Korean equity session is 09:00-15:30 KST; first window starts at 09:00.
    assert windows[0].startswith("09:00")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/risk/test_stock_risk_config.py -v`
Expected: FAIL with `ImportError: cannot import name 'StockRiskConfig'`.

- [ ] **Step 3: Implement**

In `config/risk.yaml`, add a top-level `risk_stock:` section and a `trading_windows_stock:` list (siblings of the existing `risk:` and `trading_windows:`). Use the existing `risk:`/`trading_windows:` blocks as the shape reference:

```yaml
# Stock intraday risk parameters (Phase M4-R — StockRiskFilterDaemon).
# Same field set as `risk:` (FuturesRiskConfig is asset-neutral); stock values.
risk_stock:
  account_equity_krw: 10000000      # stock paper account equity
  daily_mdd_limit_pct: 0.03
  weekly_mdd_limit_pct: 0.07
  max_position_risk_pct: 0.02
  max_daily_trades: 10              # stock portfolio trades more symbols than futures
  max_position_size_contracts: 1000 # shares cap (not contracts) — high; sizing is share-based
  consecutive_loss_soft_threshold: 4
  consecutive_loss_hard_threshold: 6
  max_spread_ticks: 5

# Korean equity regular session, KST. Half-open [start, end).
trading_windows_stock:
  - "09:00-15:30"
```

In `shared/risk/config.py`, append after `load_trading_windows` (the function near line 594) and after the `FuturesRiskConfig` class:

```python
class StockRiskConfig(FuturesRiskConfig):
    """Stock intraday risk parameters for the M4-R StockRiskFilterDaemon.

    FuturesRiskConfig's fields are asset-neutral (equity, MDD, consecutive-loss,
    trade-count, spread); only the YAML section and env prefix differ. Loaded
    from ``config/risk.yaml`` under the ``risk_stock:`` section.
    """

    _default_config_file: ClassVar[str] = "risk.yaml"
    _default_section: ClassVar[str] = "risk_stock"
    _env_prefix: ClassVar[str] = "STOCK_RISK_"


def load_stock_trading_windows(path: str | None = None) -> list[str]:
    """Load the ``trading_windows_stock`` list from ``config/risk.yaml``.

    Mirrors :func:`load_trading_windows` but reads the stock session key.
    Returns ``[]`` if the key is absent.
    """
    from shared.config.loader import ConfigLoader

    if path is None:
        env_config_dir = os.environ.get("KIS_CONFIG_DIR")
        if env_config_dir and Path(env_config_dir) != ConfigLoader.get_config_dir():
            ConfigLoader.set_config_dir(env_config_dir)
        raw_data = ConfigLoader.load("risk.yaml")
    else:
        import yaml

        if os.path.isabs(str(path)) and not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            raw_data = yaml.safe_load(f) or {}

    windows = raw_data.get("trading_windows_stock", [])
    return list(windows) if isinstance(windows, list) else []
```

Note: `ClassVar` is already imported in `shared/risk/config.py` (used by `FuturesRiskConfig`). If a lint error says otherwise, add `from typing import ClassVar`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/risk/test_stock_risk_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add config/risk.yaml shared/risk/config.py tests/unit/risk/test_stock_risk_config.py
git commit -m "feat(m4-r): StockRiskConfig + stock trading windows (risk_stock section)"
```

---

## Task 2: Stock codec — `StockRiskSignal` + parser

**Files:**
- Create: `services/stock_risk_filter/__init__.py` (empty)
- Create: `services/stock_risk_filter/codec.py`
- Create: `tests/unit/stock_risk_filter/__init__.py` (empty)
- Test: `tests/unit/stock_risk_filter/test_codec.py`

The 8 risk filters read only `signal.symbol` and `signal.generated_at` (verified across `shared/risk/filters/*.py`). The futures `Signal.__post_init__` forbids `stop_loss <= 0`, so the stock candidate (no stop) cannot construct a futures `Signal`. We define a minimal duck-typed `StockRiskSignal` instead. The parser is the inverse of M4-P's `services/stock_strategy/candidate.py::stock_signal_to_stream_dict`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_risk_filter/test_codec.py`:

```python
"""Round-trip: M4-P stock_signal_to_stream_dict -> stock_signal_from_stream_fields."""

from __future__ import annotations

from datetime import UTC, datetime

from services.stock_risk_filter.codec import (
    StockRiskSignal,
    stock_signal_from_stream_fields,
)


def _encode(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


def test_parses_m4p_candidate_fields():
    raw = {
        "signal_id": "abc123",
        "code": "005930",
        "name": "삼성전자",
        "strategy": "vr_composite",
        "direction": "long",
        "price": "71000.0",
        "quantity": "10",
        "confidence": "0.62",
        "generated_at_ms": str(int(datetime(2026, 6, 5, 4, 0, tzinfo=UTC).timestamp() * 1000)),
        "metadata_json": "{}",
    }
    signal_id, sig = stock_signal_from_stream_fields(_encode(raw))
    assert signal_id == "abc123"
    assert isinstance(sig, StockRiskSignal)
    # Filters read .symbol and .generated_at — both must be populated.
    assert sig.symbol == "005930"
    assert sig.code == "005930"
    assert sig.generated_at is not None
    assert sig.generated_at.tzinfo is not None
    assert sig.direction == "long"
    assert sig.price == 71000.0
    assert sig.quantity == 10
    assert sig.confidence == 0.62


def test_missing_direction_defaults_long():
    raw = {
        "signal_id": "x",
        "code": "000660",
        "name": "",
        "strategy": "s",
        "direction": "",
        "price": "50000",
        "quantity": "1",
        "confidence": "0.5",
        "generated_at_ms": "",
        "metadata_json": "{}",
    }
    _id, sig = stock_signal_from_stream_fields(_encode(raw))
    assert sig.direction == "long"
    assert sig.generated_at is None  # empty ms -> None (TradingHours rejects None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_risk_filter/test_codec.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.stock_risk_filter.codec'`.

- [ ] **Step 3: Implement**

Create `services/stock_risk_filter/__init__.py` (empty) and `tests/unit/stock_risk_filter/__init__.py` (empty).

Create `services/stock_risk_filter/codec.py`:

```python
"""Stock candidate codec — inverse of services.stock_strategy.candidate.

The 8 RiskFilterLayer filters read only ``signal.symbol`` and
``signal.generated_at`` (see shared/risk/filters/*.py), so a minimal duck-typed
object suffices. The futures Signal cannot be reused: its __post_init__ forbids
stop_loss <= 0 and the stock candidate has no stop/target.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class StockRiskSignal:
    """Minimal stock signal consumed by RiskFilterLayer + carried to final.

    ``symbol`` (== code) and ``generated_at`` are what the filters read; the
    remaining fields are carried through for the final-stream re-emit and for
    M4-O execution.
    """

    symbol: str
    code: str
    name: str
    strategy: str
    direction: str
    price: float
    quantity: int
    confidence: float
    generated_at: datetime | None


def stock_signal_from_stream_fields(
    fields: dict[bytes, bytes],
) -> tuple[str, StockRiskSignal]:
    """Parse Redis stream fields (M4-P candidate schema) into a StockRiskSignal."""

    def _s(key: str) -> str:
        raw = fields.get(key.encode(), b"")
        return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)

    def _ms_to_dt(ms: str) -> datetime | None:
        if not ms:
            return None
        return datetime.fromtimestamp(int(ms) / 1000, tz=UTC)

    code = _s("code")
    signal = StockRiskSignal(
        symbol=code,
        code=code,
        name=_s("name"),
        strategy=_s("strategy"),
        direction=_s("direction") or "long",
        price=float(_s("price") or 0.0),
        quantity=int(float(_s("quantity") or 0)),
        confidence=float(_s("confidence") or 0.0),
        generated_at=_ms_to_dt(_s("generated_at_ms")),
    )
    return _s("signal_id"), signal


def decode_fields(fields: dict[bytes, bytes]) -> dict[str, str]:
    """Decode a raw Redis field dict to ``{str: str}`` for re-emit."""
    out: dict[str, str] = {}
    for k, v in fields.items():
        key = k.decode("utf-8", errors="replace") if isinstance(k, bytes) else str(k)
        val = v.decode("utf-8", errors="replace") if isinstance(v, bytes) else str(v)
        out[key] = val
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_risk_filter/test_codec.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add services/stock_risk_filter/__init__.py services/stock_risk_filter/codec.py tests/unit/stock_risk_filter/
git commit -m "feat(m4-r): stock candidate codec (StockRiskSignal + parser)"
```

---

## Task 3: `StockRiskFilterDaemon`

**Files:**
- Create: `services/stock_risk_filter/main.py` (daemon class only this task; entrypoint in Task 4)
- Test: `tests/unit/stock_risk_filter/test_daemon.py`

Mirrors `services/risk_filter/main.py::RiskFilterDaemon` but with the stock codec, no `signals_all` writer (deferred), and passthrough re-emit of all candidate fields + `size_multiplier` + `filtered_at_ms`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_risk_filter/test_daemon.py`:

```python
"""StockRiskFilterDaemon.handle_message: pass -> final XADD; reject -> no XADD; poison-pill drop."""

from __future__ import annotations

from datetime import UTC, datetime

import fakeredis.aioredis
import pytest

from services.stock_risk_filter.main import StockRiskFilterDaemon
from shared.risk.layer import RiskFilterLayer
from shared.risk.runtime_state import RuntimeRiskState


def _encode(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


def _candidate(code: str = "005930", generated_at_ms: str | None = None) -> dict[str, str]:
    if generated_at_ms is None:
        # 09:30 KST = 00:30 UTC — inside the 09:00-15:30 stock window.
        generated_at_ms = str(int(datetime(2026, 6, 5, 0, 30, tzinfo=UTC).timestamp() * 1000))
    return {
        "signal_id": "sig-1",
        "code": code,
        "name": "n",
        "strategy": "vr_composite",
        "direction": "long",
        "price": "71000.0",
        "quantity": "10",
        "confidence": "0.62",
        "generated_at_ms": generated_at_ms,
        "metadata_json": "{}",
    }


def _build_daemon(redis) -> StockRiskFilterDaemon:
    # Stock session window; no open-position provider (always-False stub).
    layer = RiskFilterLayer.from_config(
        config=__import__("shared.risk.config", fromlist=["StockRiskConfig"]).StockRiskConfig(),
        trading_windows=["09:00-15:30"],
    )
    return StockRiskFilterDaemon(
        redis=redis,
        layer=layer,
        runtime_state=RuntimeRiskState(redis=redis, asset_class="stock"),
        candidate_stream="signal.candidate.stock.shadow",
        final_stream="signal.final.stock.shadow",
        consumer_group="stock_risk_filter",
        worker_id="test-worker",
        final_maxlen=1000,
        xread_block_ms=100,
        batch_size=10,
    )


@pytest.mark.asyncio
async def test_passing_candidate_emits_final_with_size_multiplier():
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    ack = await daemon.handle_message(b"1-0", _encode(_candidate()))
    assert ack is True
    entries = await redis.xrange("signal.final.stock.shadow")
    assert len(entries) == 1
    _id, fields = entries[0]
    assert fields[b"code"] == b"005930"
    assert b"size_multiplier" in fields
    assert b"filtered_at_ms" in fields


@pytest.mark.asyncio
async def test_outside_session_rejected_no_final():
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    # 20:00 KST = 11:00 UTC — outside 09:00-15:30.
    off = str(int(datetime(2026, 6, 5, 11, 0, tzinfo=UTC).timestamp() * 1000))
    ack = await daemon.handle_message(b"1-0", _encode(_candidate(generated_at_ms=off)))
    assert ack is True  # rejected is audit-only consume
    entries = await redis.xrange("signal.final.stock.shadow")
    assert entries == []


@pytest.mark.asyncio
async def test_unparseable_is_poison_pill_drop():
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    ack = await daemon.handle_message(b"1-0", {b"price": b"not-a-float", b"code": b"x"})
    assert ack is True  # consumed, not retried
    assert await redis.xrange("signal.final.stock.shadow") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_risk_filter/test_daemon.py -v`
Expected: FAIL with `ImportError: cannot import name 'StockRiskFilterDaemon'`.

- [ ] **Step 3: Implement**

Create `services/stock_risk_filter/main.py` (daemon class + imports; the entrypoint `_build_and_run`/`main` is added in Task 4):

```python
"""Stock risk-filter consumer-group daemon (M4-R, flag-gated, shadow-first).

Reads stock candidates from ``signal.candidate.stock.shadow`` (M4-P output),
runs the 8-filter RiskFilterLayer with stock config + session windows, and on
pass re-emits all candidate fields + size_multiplier + filtered_at_ms to
``signal.final.stock.shadow``.

Error taxonomy (mirrors services.risk_filter.main):
- Parse error            -> XACK (poison-pill drop)
- Filter eval raises     -> NO XACK (leave pending)
- final XADD raises      -> NO XACK
"""

from __future__ import annotations

import logging
import time
from typing import Any

from services.stock_risk_filter.codec import (
    decode_fields,
    stock_signal_from_stream_fields,
)
from shared.risk.layer import RiskFilterLayer
from shared.risk.runtime_state import RuntimeRiskState
from shared.streaming.stage import StreamStage

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400


class StockRiskFilterDaemon(StreamStage):
    """Apply the 8-filter RiskFilterLayer to every stock candidate."""

    def __init__(
        self,
        *,
        redis: Any,
        layer: RiskFilterLayer,
        runtime_state: RuntimeRiskState,
        candidate_stream: str,
        final_stream: str,
        consumer_group: str,
        worker_id: str,
        final_maxlen: int,
        xread_block_ms: int,
        batch_size: int,
    ) -> None:
        super().__init__(
            redis=redis,
            input_stream=candidate_stream,
            consumer_group=consumer_group,
            worker_id=worker_id,
            xread_block_ms=xread_block_ms,
            batch_size=batch_size,
            xreadgroup_error_sleep_seconds=0.5,
        )
        self.layer = layer
        self.runtime_state = runtime_state
        self.final_stream = final_stream
        self.final_maxlen = final_maxlen

    async def handle_message(
        self, msg_id: bytes, fields: dict[bytes, bytes]  # noqa: ARG002
    ) -> bool:
        try:
            signal_id, signal = stock_signal_from_stream_fields(fields)
            passthrough = decode_fields(fields)
        except Exception:
            logger.exception("Unparseable stock candidate; ACKing as poison-pill")
            return True  # poison-pill: consume

        try:
            snapshot = await self.runtime_state.snapshot()
            result = self.layer.evaluate(signal, snapshot)
        except Exception:
            logger.exception(
                "Stock filter eval failed signal_id=%s; leaving pending", signal_id
            )
            return False

        if not result.passed:
            logger.info(
                "Stock candidate rejected signal_id=%s reason=%s",
                signal_id,
                result.skip_reason,
            )
            return True  # rejected: consume (no final)

        try:
            fields_out = dict(passthrough)
            fields_out["size_multiplier"] = str(result.size_multiplier)
            fields_out["filtered_at_ms"] = str(int(time.time() * 1000))
            await self.redis.xadd(
                self.final_stream,
                fields_out,
                maxlen=self.final_maxlen,
                approximate=True,
            )
            await self.redis.expire(self.final_stream, _STREAM_TTL_SECONDS)
        except Exception:
            logger.exception(
                "Stock final XADD failed signal_id=%s; leaving pending", signal_id
            )
            return False

        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_risk_filter/test_daemon.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add services/stock_risk_filter/main.py tests/unit/stock_risk_filter/test_daemon.py
git commit -m "feat(m4-r): StockRiskFilterDaemon (candidate -> filter -> final.stock.shadow)"
```

---

## Task 4: M4-R flag-gated entrypoint + open-position provider + systemd

**Files:**
- Modify: `services/stock_risk_filter/main.py` (append `_resolve_mode`, `_streams_for`, `_build_and_run`, `main`)
- Create: `deploy/systemd/kis-stock-risk-filter.service`
- Test: `tests/unit/stock_risk_filter/test_entrypoint.py`

Mirrors `services/stock_strategy/main.py` flag gating. The open-position provider uses a **sync** Redis client (the layer's `evaluate` is synchronous), mirroring how `stock_strategy/main.py` uses `RedisClient.get_client()` for watchlist reads. It checks `HEXISTS trading:stock:positions <code>` — the hash M4-O writes on fill.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_risk_filter/test_entrypoint.py`:

```python
"""M4-R flag routing: off -> inert (no daemon constructed); stream-name mapping."""

from __future__ import annotations

import services.stock_risk_filter.main as m


def test_resolve_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("STOCK_RISK_FILTER", raising=False)
    assert m._resolve_mode() == "off"


def test_streams_for_shadow():
    candidate, final = m._streams_for("shadow")
    assert candidate == "signal.candidate.stock.shadow"
    assert final == "signal.final.stock.shadow"


def test_off_mode_is_inert(monkeypatch):
    import asyncio

    monkeypatch.setenv("STOCK_RISK_FILTER", "off")
    # off path must return 0 without constructing a daemon or touching a real redis.
    rc = asyncio.run(m._build_and_run())
    assert rc == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_risk_filter/test_entrypoint.py -v`
Expected: FAIL with `AttributeError: module ... has no attribute '_resolve_mode'`.

- [ ] **Step 3: Implement**

Append to `services/stock_risk_filter/main.py`:

```python
# ---------------------------------------------------------------------------
# Flag-gated entrypoint (shadow-first, default-off)
# ---------------------------------------------------------------------------


def _resolve_mode() -> str:
    import os

    return os.getenv("STOCK_RISK_FILTER", "off").strip().lower()


def _streams_for(mode: str) -> tuple[str, str]:
    """Return ``(candidate_stream, final_stream)`` for the mode.

    shadow -> (signal.candidate.stock.shadow, signal.final.stock.shadow).
    The else branch reserves the live (unsuffixed) names for a future cutover.
    """
    if mode == "shadow":
        return "signal.candidate.stock.shadow", "signal.final.stock.shadow"
    return "signal.candidate.stock", "signal.final.stock"


async def _build_and_run() -> int:
    import asyncio
    import os
    import signal as signal_mod
    import socket

    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()
    if mode != "shadow":
        logger.info("STOCK_RISK_FILTER=%s (off) — daemon inert, exiting", mode)
        await redis_client.aclose()
        return 0

    from shared.risk.config import StockRiskConfig, load_stock_trading_windows
    from shared.streaming.client import RedisClient

    candidate_stream, final_stream = _streams_for(mode)
    candidate_stream = os.environ.get("STOCK_CANDIDATE_STREAM", candidate_stream)
    final_stream = os.environ.get("STOCK_FINAL_STREAM", final_stream)

    config = StockRiskConfig.from_yaml()
    windows = load_stock_trading_windows()

    # Sync redis for the open-position provider (layer.evaluate is sync).
    sync_redis = RedisClient.get_client()
    positions_key = os.environ.get("STOCK_POSITIONS_KEY", "trading:stock:positions")

    def _has_open_position(code: str) -> bool:
        try:
            return bool(sync_redis.hexists(positions_key, code))
        except Exception:
            return False  # fail-open

    layer = RiskFilterLayer.from_config(
        config=config,
        trading_windows=windows,
        has_open_position_provider=_has_open_position,
    )
    runtime_state = RuntimeRiskState(redis=redis_client, asset_class="stock")

    worker_id = f"stock-risk-filter-{socket.gethostname()}-{os.getpid()}"
    daemon = StockRiskFilterDaemon(
        redis=redis_client,
        layer=layer,
        runtime_state=runtime_state,
        candidate_stream=candidate_stream,
        final_stream=final_stream,
        consumer_group="stock_risk_filter",
        worker_id=worker_id,
        final_maxlen=10_000,
        xread_block_ms=2000,
        batch_size=10,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        await redis_client.aclose()
    return 0


def main() -> int:
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
```

Create `deploy/systemd/kis-stock-risk-filter.service`:

```ini
[Unit]
Description=KIS Stock Risk Filter (signal.candidate.stock.shadow -> RiskFilterLayer -> signal.final.stock.shadow)
After=network-online.target redis-server.service
Wants=network-online.target
Requires=redis-server.service

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/project/kis_unified_sts
EnvironmentFile=/home/deploy/project/kis_unified_sts/.env
Environment=STOCK_RISK_FILTER=shadow
ExecStart=/home/deploy/project/kis_unified_sts/.venv/bin/python -m services.stock_risk_filter.main
Restart=on-failure
RestartSec=10s
TimeoutStopSec=30s
KillSignal=SIGTERM

# Delivered DISABLED. Enabling is an operator step (shadow validation gate).
[Install]
WantedBy=multi-user.target
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_risk_filter/test_entrypoint.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add services/stock_risk_filter/main.py deploy/systemd/kis-stock-risk-filter.service tests/unit/stock_risk_filter/test_entrypoint.py
git commit -m "feat(m4-r): flag-gated entrypoint + open-position provider + disabled systemd unit"
```

---

## Task 5: `StockOrderRouterDaemon` (paper execution + position record)

**Files:**
- Create: `services/stock_order_router/__init__.py` (empty)
- Create: `services/stock_order_router/main.py` (daemon class this task; entrypoint Task 6)
- Create: `tests/unit/stock_order_router/__init__.py` (empty)
- Test: `tests/unit/stock_order_router/test_daemon.py`

Consumes `signal.final.stock.shadow`, scales quantity by `size_multiplier`, paper-executes via `VirtualBroker` (slippage modeled), logs the fill via `FillLogger(asset_class="stock", venue="KRX")`, and records the open position to the `trading:stock:positions` hash (read by M4-R's open-position provider; consumed later by M4-X).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_order_router/test_daemon.py`:

```python
"""StockOrderRouterDaemon.handle_message: final -> paper fill -> fill stream + position record."""

from __future__ import annotations

import json

import fakeredis.aioredis
import pytest

from services.stock_order_router.main import StockOrderRouterDaemon
from shared.execution.fill_logger import FillLogger
from shared.paper.broker import VirtualBroker


def _encode(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


def _final(code: str = "005930", size_multiplier: str = "1.0", qty: str = "10") -> dict[str, str]:
    return {
        "signal_id": "sig-1",
        "code": code,
        "name": "n",
        "strategy": "vr_composite",
        "direction": "long",
        "price": "71000.0",
        "quantity": qty,
        "confidence": "0.62",
        "generated_at_ms": "1000",
        "metadata_json": "{}",
        "size_multiplier": size_multiplier,
        "filtered_at_ms": "2000",
    }


def _build_daemon(redis) -> StockOrderRouterDaemon:
    fill_logger = FillLogger(
        redis=redis,
        stream="order.fill.stock.shadow",
        maxlen=1000,
        asset_class="stock",
    )
    return StockOrderRouterDaemon(
        redis=redis,
        broker=VirtualBroker(slippage_rate=0.001),
        fill_logger=fill_logger,
        final_stream="signal.final.stock.shadow",
        consumer_group="stock_order_router",
        worker_id="test-worker",
        positions_key="trading:stock:positions",
        xread_block_ms=100,
        batch_size=10,
    )


@pytest.mark.asyncio
async def test_fill_published_and_position_recorded():
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    ack = await daemon.handle_message(b"1-0", _encode(_final()))
    assert ack is True

    fills = await redis.xrange("order.fill.stock.shadow")
    assert len(fills) == 1
    _id, f = fills[0]
    assert f[b"symbol"] == b"005930"
    assert f[b"side"] == b"BUY"
    assert f[b"venue"] == b"KRX"
    assert f[b"trade_role"] == b"entry"
    assert int(f[b"quantity"]) == 10

    raw = await redis.hget("trading:stock:positions", "005930")
    assert raw is not None
    pos = json.loads(raw)
    assert pos["quantity"] == 10
    assert pos["entry_price"] > 0
    assert pos["state"] == "SURVIVAL"


@pytest.mark.asyncio
async def test_size_multiplier_scales_quantity_floored_at_one():
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    # 10 shares * 0.5 = 5
    await daemon.handle_message(b"1-0", _encode(_final(size_multiplier="0.5", qty="10")))
    fills = await redis.xrange("order.fill.stock.shadow")
    assert int(fills[0][1][b"quantity"]) == 5


@pytest.mark.asyncio
async def test_unparseable_is_poison_pill_drop():
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    ack = await daemon.handle_message(b"1-0", {b"price": b"NaNaN", b"code": b"x"})
    assert ack is True
    assert await redis.xrange("order.fill.stock.shadow") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_order_router/test_daemon.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.stock_order_router.main'`.

- [ ] **Step 3: Implement**

Create `services/stock_order_router/__init__.py` (empty) and `tests/unit/stock_order_router/__init__.py` (empty).

Create `services/stock_order_router/main.py` (daemon class; entrypoint in Task 6):

```python
"""Stock order-router consumer-group daemon (M4-O, flag-gated, shadow-first).

Reads filtered stock signals from ``signal.final.stock.shadow``, paper-executes
via VirtualBroker (slippage modeled), logs the fill to ``order.fill.stock.shadow``
+ RuntimeLedger, and records the open position to the ``trading:stock:positions``
hash (read by M4-R OpenPositionFilter; consumed later by M4-X exit).

KRX-only (no ATS this increment); share-based sizing (no ContractSpec); no
PseudoOCO bracket (stock has no entry-time stop/target — M4-X owns exit).

Error taxonomy:
- Parse error        -> XACK (poison-pill drop)
- Broker raises      -> NO XACK (retry)
- Fill logging raises-> NO XACK
"""

from __future__ import annotations

import json
import logging
import math
import time
from typing import Any

from services.stock_risk_filter.codec import stock_signal_from_stream_fields
from shared.execution.fill_logger import FillLogger
from shared.paper.broker import VirtualBroker
from shared.paper.models import OrderSide, OrderType
from shared.streaming.stage import StreamStage

logger = logging.getLogger(__name__)


def _resolve_quantity(*, base_quantity: int, size_multiplier: float) -> int:
    """Scale base share quantity by size_multiplier; floor at 1 (never zero)."""
    scaled = int(math.floor(base_quantity * size_multiplier))
    return max(scaled, 1)


class StockOrderRouterDaemon(StreamStage):
    """Paper-execute stock entries and record open positions."""

    def __init__(
        self,
        *,
        redis: Any,
        broker: VirtualBroker,
        fill_logger: FillLogger,
        final_stream: str,
        consumer_group: str,
        worker_id: str,
        positions_key: str,
        xread_block_ms: int,
        batch_size: int,
    ) -> None:
        super().__init__(
            redis=redis,
            input_stream=final_stream,
            consumer_group=consumer_group,
            worker_id=worker_id,
            xread_block_ms=xread_block_ms,
            batch_size=batch_size,
            xreadgroup_error_sleep_seconds=0.5,
        )
        self.broker = broker
        self.fill_logger = fill_logger
        self.positions_key = positions_key

    async def handle_message(
        self, msg_id: bytes, fields: dict[bytes, bytes]  # noqa: ARG002
    ) -> bool:
        try:
            signal_id, signal = stock_signal_from_stream_fields(fields)
            size_multiplier = float(
                fields.get(b"size_multiplier", b"1.0").decode(errors="replace") or 1.0
            )
        except Exception:
            logger.exception("Unparseable stock final signal; ACK as poison-pill")
            return True  # poison-pill: consume

        quantity = _resolve_quantity(
            base_quantity=signal.quantity, size_multiplier=size_multiplier
        )

        try:
            order = await self.broker.submit_order(
                symbol=signal.code,
                side=OrderSide.BUY,
                quantity=quantity,
                price=signal.price,
                order_type=OrderType.MARKET,
                market_price=signal.price,
            )
        except Exception:
            logger.exception(
                "broker raised signal_id=%s; leaving pending", signal_id
            )
            return False

        if not order.filled:
            logger.info(
                "stock paper order not filled signal_id=%s reason=%s",
                signal_id,
                order.rejection_reason,
            )
            return True  # final state, consumed

        filled_price = float(order.fill_price or signal.price)
        now_ms = int(time.time() * 1000)
        slippage = abs(filled_price - signal.price)

        try:
            await self.fill_logger.log_fill(
                signal_id=signal_id,
                order_id=order.order_id,
                symbol=signal.code,
                side="BUY",
                order_type="market",
                requested_price=signal.price,
                filled_price=filled_price,
                tick_size_points=0.0,
                slippage_ticks=slippage,
                quantity=quantity,
                requested_at_ms=now_ms,
                filled_at_ms=now_ms,
                venue="KRX",
                trade_role="entry",
            )
        except Exception:
            logger.exception(
                "fill logging failed signal_id=%s; leaving pending", signal_id
            )
            return False

        # Record open position (read by M4-R OpenPositionFilter; M4-X consumes).
        try:
            await self.redis.hset(
                self.positions_key,
                signal.code,
                json.dumps(
                    {
                        "code": signal.code,
                        "entry_price": filled_price,
                        "quantity": quantity,
                        "opened_at_ms": now_ms,
                        "state": "SURVIVAL",
                        "signal_id": signal_id,
                    }
                ),
            )
        except Exception:
            # Best-effort: the fill is already published; do not retry the order.
            logger.exception(
                "position record failed signal_id=%s code=%s", signal_id, signal.code
            )

        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_order_router/test_daemon.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add services/stock_order_router/__init__.py services/stock_order_router/main.py tests/unit/stock_order_router/
git commit -m "feat(m4-o): StockOrderRouterDaemon (final -> paper fill -> fill.stock.shadow + position)"
```

---

## Task 6: M4-O flag-gated entrypoint + systemd

**Files:**
- Modify: `services/stock_order_router/main.py` (append entrypoint)
- Create: `deploy/systemd/kis-stock-order-router.service`
- Test: `tests/unit/stock_order_router/test_entrypoint.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_order_router/test_entrypoint.py`:

```python
"""M4-O flag routing: off -> inert; stream-name mapping."""

from __future__ import annotations

import services.stock_order_router.main as m


def test_resolve_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("STOCK_ORDER_ROUTER", raising=False)
    assert m._resolve_mode() == "off"


def test_final_stream_for_shadow():
    assert m._final_stream_for("shadow") == "signal.final.stock.shadow"
    assert m._fill_stream_for("shadow") == "order.fill.stock.shadow"


def test_off_mode_is_inert(monkeypatch):
    import asyncio

    monkeypatch.setenv("STOCK_ORDER_ROUTER", "off")
    assert asyncio.run(m._build_and_run()) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_order_router/test_entrypoint.py -v`
Expected: FAIL with `AttributeError: ... '_resolve_mode'`.

- [ ] **Step 3: Implement**

Append to `services/stock_order_router/main.py`:

```python
# ---------------------------------------------------------------------------
# Flag-gated entrypoint (shadow-first, default-off)
# ---------------------------------------------------------------------------


def _resolve_mode() -> str:
    import os

    return os.getenv("STOCK_ORDER_ROUTER", "off").strip().lower()


def _final_stream_for(mode: str) -> str:
    return "signal.final.stock.shadow" if mode == "shadow" else "signal.final.stock"


def _fill_stream_for(mode: str) -> str:
    return "order.fill.stock.shadow" if mode == "shadow" else "order.fill.stock"


async def _build_and_run() -> int:
    import asyncio
    import os
    import signal as signal_mod
    import socket

    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()
    if mode != "shadow":
        logger.info("STOCK_ORDER_ROUTER=%s (off) — daemon inert, exiting", mode)
        await redis_client.aclose()
        return 0

    from shared.storage import SQLiteRuntimeLedger
    from shared.storage.config import StorageConfig

    final_stream = os.environ.get("STOCK_FINAL_STREAM", _final_stream_for(mode))
    fill_stream = os.environ.get("STOCK_FILL_STREAM", _fill_stream_for(mode))
    positions_key = os.environ.get("STOCK_POSITIONS_KEY", "trading:stock:positions")

    runtime_ledger = None
    storage_config = StorageConfig.load_or_default()
    if storage_config.runtime_storage.backend == "sqlite":
        runtime_ledger = SQLiteRuntimeLedger(storage_config.runtime_storage.sqlite)

    fill_logger = FillLogger(
        redis=redis_client,
        archive_client=None,
        stream=fill_stream,
        maxlen=10_000,
        runtime_ledger=runtime_ledger,
        asset_class="stock",
    )

    # Paper broker with modeled slippage (CLAUDE.md: 슬리피지 반영 필수).
    slippage_rate = float(os.environ.get("STOCK_PAPER_SLIPPAGE_RATE", "0.001"))
    broker = VirtualBroker(slippage_rate=slippage_rate)

    worker_id = f"stock-order-router-{socket.gethostname()}-{os.getpid()}"
    daemon = StockOrderRouterDaemon(
        redis=redis_client,
        broker=broker,
        fill_logger=fill_logger,
        final_stream=final_stream,
        consumer_group="stock_order_router",
        worker_id=worker_id,
        positions_key=positions_key,
        xread_block_ms=2000,
        batch_size=10,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        await fill_logger.flush()
        await redis_client.aclose()
        if runtime_ledger is not None:
            runtime_ledger.close()
    return 0


def main() -> int:
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
```

Note: confirm `FillLogger.flush` exists (it is called by the futures order_router at `services/order_router/main.py:406`). If `SQLiteRuntimeLedger` import path differs, match `services/order_router/main.py:325` (`from shared.storage import SQLiteRuntimeLedger`).

Create `deploy/systemd/kis-stock-order-router.service`:

```ini
[Unit]
Description=KIS Stock Order Router (signal.final.stock.shadow -> paper fill -> order.fill.stock.shadow)
After=network-online.target redis-server.service
Wants=network-online.target
Requires=redis-server.service

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/project/kis_unified_sts
EnvironmentFile=/home/deploy/project/kis_unified_sts/.env
Environment=STOCK_ORDER_ROUTER=shadow
ExecStart=/home/deploy/project/kis_unified_sts/.venv/bin/python -m services.stock_order_router.main
Restart=on-failure
RestartSec=10s
TimeoutStopSec=30s
KillSignal=SIGTERM

# Delivered DISABLED. Enabling is an operator step (shadow validation gate).
[Install]
WantedBy=multi-user.target
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_order_router/test_entrypoint.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add services/stock_order_router/main.py deploy/systemd/kis-stock-order-router.service tests/unit/stock_order_router/test_entrypoint.py
git commit -m "feat(m4-o): flag-gated entrypoint + disabled systemd unit"
```

---

## Task 7: e2e integration — candidate → risk → final → order → fill + re-entry block

**Files:**
- Test: `tests/integration/test_stock_execution_pipeline.py`

Drives both daemons over a shared fakeredis: a stock candidate flows to a fill, the position is recorded, and a second candidate for the same code is blocked by `OpenPositionFilter` (no second fill).

- [ ] **Step 1: Write the test**

Create `tests/integration/test_stock_execution_pipeline.py`:

```python
"""e2e: candidate.stock.shadow -> M4-R -> final.stock.shadow -> M4-O -> fill + position.

Also asserts OpenPositionFilter blocks re-entry once M4-O has recorded a position.
"""

from __future__ import annotations

from datetime import UTC, datetime

import fakeredis
import fakeredis.aioredis
import pytest

from services.stock_order_router.main import StockOrderRouterDaemon
from services.stock_risk_filter.main import StockRiskFilterDaemon
from shared.execution.fill_logger import FillLogger
from shared.paper.broker import VirtualBroker
from shared.risk.config import StockRiskConfig
from shared.risk.layer import RiskFilterLayer
from shared.risk.runtime_state import RuntimeRiskState


def _encode(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


def _candidate(code: str) -> dict[str, str]:
    # 09:30 KST -> inside 09:00-15:30 stock window.
    gen = str(int(datetime(2026, 6, 5, 0, 30, tzinfo=UTC).timestamp() * 1000))
    return {
        "signal_id": f"sig-{code}",
        "code": code,
        "name": "n",
        "strategy": "vr_composite",
        "direction": "long",
        "price": "71000.0",
        "quantity": "10",
        "confidence": "0.62",
        "generated_at_ms": gen,
        "metadata_json": "{}",
    }


@pytest.mark.asyncio
async def test_candidate_to_fill_and_reentry_blocked():
    redis = fakeredis.aioredis.FakeRedis()
    positions_key = "trading:stock:positions"

    # Sync fakeredis sharing the same server as the async client so the
    # open-position provider sees what M4-O writes.
    sync_redis = fakeredis.FakeStrictRedis(server=redis.connection_pool.connection_kwargs["server"])

    def _has_open_position(code: str) -> bool:
        return bool(sync_redis.hexists(positions_key, code))

    risk = StockRiskFilterDaemon(
        redis=redis,
        layer=RiskFilterLayer.from_config(
            config=StockRiskConfig(),
            trading_windows=["09:00-15:30"],
            has_open_position_provider=_has_open_position,
        ),
        runtime_state=RuntimeRiskState(redis=redis, asset_class="stock"),
        candidate_stream="signal.candidate.stock.shadow",
        final_stream="signal.final.stock.shadow",
        consumer_group="stock_risk_filter",
        worker_id="risk-w",
        final_maxlen=1000,
        xread_block_ms=100,
        batch_size=10,
    )
    order = StockOrderRouterDaemon(
        redis=redis,
        broker=VirtualBroker(slippage_rate=0.001),
        fill_logger=FillLogger(
            redis=redis, stream="order.fill.stock.shadow", maxlen=1000, asset_class="stock"
        ),
        final_stream="signal.final.stock.shadow",
        consumer_group="stock_order_router",
        worker_id="order-w",
        positions_key=positions_key,
        xread_block_ms=100,
        batch_size=10,
    )

    # 1st candidate -> passes risk -> final -> fill -> position recorded.
    assert await risk.handle_message(b"c1", _encode(_candidate("005930"))) is True
    final_entries = await redis.xrange("signal.final.stock.shadow")
    assert len(final_entries) == 1
    assert await order.handle_message(final_entries[0][0], final_entries[0][1]) is True

    fills = await redis.xrange("order.fill.stock.shadow")
    assert len(fills) == 1
    assert await redis.hexists(positions_key, "005930")

    # 2nd candidate, same code -> OpenPositionFilter rejects -> no new final.
    assert await risk.handle_message(b"c2", _encode(_candidate("005930"))) is True
    final_after = await redis.xrange("signal.final.stock.shadow")
    assert len(final_after) == 1  # unchanged — re-entry blocked
```

- [ ] **Step 2: Run + iterate**

Run: `.venv/bin/pytest tests/integration/test_stock_execution_pipeline.py -v`
Expected: PASS (1 passed).

If the `fakeredis.FakeStrictRedis(server=...)` shared-server wiring fails (API differs by fakeredis version), fall back to a single shared `fakeredis` server object:

```python
import fakeredis
server = fakeredis.FakeServer()
redis = fakeredis.aioredis.FakeRedis(server=server)
sync_redis = fakeredis.FakeStrictRedis(server=server)
```

Use whichever the installed `fakeredis` supports (check `.venv/bin/python -c "import fakeredis; print(fakeredis.__version__)"`).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_stock_execution_pipeline.py
git commit -m "test(m4-ro): e2e candidate.stock -> risk -> final -> order -> fill + re-entry block"
```

---

## Task 8: Full gate + lint + PR

- [ ] **Step 1: Lint/format/type**

```bash
.venv/bin/black services/stock_risk_filter services/stock_order_router tests/unit/stock_risk_filter tests/unit/stock_order_router tests/integration/test_stock_execution_pipeline.py shared/risk/config.py
.venv/bin/ruff check --fix services/stock_risk_filter services/stock_order_router tests/unit/stock_risk_filter tests/unit/stock_order_router
.venv/bin/mypy services/stock_risk_filter services/stock_order_router
```
Expected: no errors (mypy may warn on `Any` redis — acceptable, matches existing daemons).

- [ ] **Step 2: Targeted suite**

```bash
.venv/bin/pytest tests/unit/stock_risk_filter tests/unit/stock_order_router tests/unit/risk/test_stock_risk_config.py tests/integration/test_stock_execution_pipeline.py -v
```
Expected: all PASS.

- [ ] **Step 3: Regression — futures daemons untouched**

```bash
.venv/bin/pytest tests/unit/risk tests/unit -k "risk_filter or order_router" -q
```
Expected: all PASS (proves zero regression to the merged futures path — we added new modules, modified only `shared/risk/config.py` additively and `config/risk.yaml` additively).

- [ ] **Step 4: Full gate (CI parity)**

```bash
.venv/bin/pytest tests/ -m "not serial" -q && .venv/bin/pytest tests/ -m serial -q
```
Expected: green. (Mirrors the CI 2-pass parallel+serial split.)

- [ ] **Step 5: Push + PR**

```bash
git push -u origin docs/stock-execution-pipeline-m4ro-spec
gh pr create --base main --head docs/stock-execution-pipeline-m4ro-spec \
  --title "feat(m4-ro): stock execution pipeline (risk_filter + order_router, shadow-first, default off)" \
  --body "$(cat <<'EOF'
## What
The stock entry-execution tail of the decoupled stream pipeline: two shadow-first,
default-off daemons consuming M4-P's `signal.candidate.stock.shadow` →
`StockRiskFilterDaemon` (RiskFilterLayer, stock session windows + open-position
re-entry block) → `signal.final.stock.shadow` → `StockOrderRouterDaemon`
(VirtualBroker paper fill with slippage, FillLogger, position record) →
`order.fill.stock.shadow`. Flags `STOCK_RISK_FILTER`/`STOCK_ORDER_ROUTER` default
off; systemd units disabled.

## Why
M4-R/O — the stock generalization of the futures risk_filter/order_router tail.
M4-P built the producer but its candidates had no consumer. Reuses StreamStage /
RiskFilterLayer / RuntimeRiskState / VirtualBroker / FillLogger / RuntimeLedger
unchanged; merged futures daemons untouched (zero regression). Merge is inert
(default off).

## Scope / limitations (validate in shadow before cutover)
Entry execution only — M4-X (ThreeStageExit producer + position close) is a
separate spec. PnL-dependent risk filters (MDD/consecutive-loss) are inert until
M4-X feeds realized PnL; active filters are TradingHours / DailyTradeCount /
OpenPosition. KRX-only (ATS deferred behind flag). No `signals_all` audit for
stock yet. See spec §5.4.

## How tested
Unit (codec round-trip, daemon pass/reject/poison-pill, size-multiplier scaling,
position record, flag routing), integration (candidate→risk→final→order→fill +
OpenPositionFilter re-entry block), full `tests/` gate green, ruff/black/mypy clean.

Spec: `docs/superpowers/specs/2026-06-05-stock-execution-pipeline-m4ro-design.md`
Plan: `docs/superpowers/plans/archive/2026-06-05-stock-execution-pipeline-m4ro.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 6: Run code review**

Run `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:**
- §4.1 topology (candidate.stock.shadow → final.stock.shadow → fill.stock.shadow) → Tasks 3/5/7. ✓
- §4.2 schemas (final += size_multiplier/filtered_at_ms; fill via FillLogger) → Task 3 (final), Task 5 (fill). ✓
- §4.3 stock codec (filters read symbol+generated_at) → Task 2. ✓
- §5 M4-R (StreamStage reuse, RuntimeRiskState asset=stock, StockRiskConfig, 8 filters, OpenPosition provider) → Tasks 1/3/4. ✓
- §5.4 PnL-filter limitation documented → spec + PR body. ✓
- §6 M4-O (VirtualBroker paper, FillLogger asset=stock/venue=KRX, position record, no ContractSpec/PseudoOCO/locked_symbol) → Tasks 5/6. ✓
- §6.4 position open record (trading:stock:positions) → Task 5; read by M4-R provider → Task 4; e2e → Task 7. ✓
- §7 flags/systemd → Tasks 4/6; DRY reuse → all tasks. ✓
- §8 error taxonomy (poison-pill/no-xack/best-effort) → Tasks 3/5. ✓
- §9 tests (unit + e2e + regression) → Tasks 2–8. ✓
- §10 acceptance (default-off, futures untouched, no ClickHouse) → Task 8 step 3. ✓

**Placeholder scan:** none — every step has complete code/commands.

**Type consistency:** `StockRiskSignal` fields (symbol/code/name/strategy/direction/price/quantity/confidence/generated_at) used identically in Tasks 2/3/5. `stock_signal_from_stream_fields` returns `(str, StockRiskSignal)` consistently. `FillLogger.log_fill` kwargs match `shared/execution/fill_logger.py:56-74`. `VirtualBroker.submit_order` kwargs + `.filled`/`.fill_price`/`.order_id`/`.rejection_reason` match `shared/paper/broker.py` + `models.py`. `RiskFilterLayer.from_config(config, trading_windows, has_open_position_provider=...)` matches `shared/risk/layer.py:84`. `RuntimeRiskState(redis=, asset_class=)` + `snapshot()` match `shared/risk/runtime_state.py:32`.

**Deferred-to-plan open questions resolved:** PR split → one PR (header). daemon_entrypoint DRY → deferred (out-of-scope note). StockRiskConfig defaults → Task 1 YAML. positions key format → Task 5 (`trading:stock:positions` hash, JSON value with state=SURVIVAL for M4-X forward-compat).
