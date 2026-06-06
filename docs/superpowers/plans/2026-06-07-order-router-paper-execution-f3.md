# Order Router Paper Execution (F-3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `PaperKISFuturesAdapter` + a `FUTURES_ORDER_ROUTER` mode flag so the decoupled futures order_router can run in PAPER mode — real WS orderbook in, faithful passive-limit fills simulated locally, recorded to FillLogger, with ZERO real KIS orders.

**Architecture:** `PassiveMaker` is already decoupled via a duck-typed `kis_client` interface. F-3 adds a paper implementation of that interface (real orderbook via the live feed + a tick-watch fill model + synthetic order ids) and wires the order_router to select paper vs live vs off. `PassiveMaker`, `PseudoOCO`, `OrderRouterDaemon`, and `FillLogger` are unchanged.

**Tech Stack:** Python 3.11+ asyncio, `KISFuturesPriceFeed` (real WS), pytest. Tests use a fake feed + the existing `Signal`/`ContractSpec`/`PassiveMaker` patterns (`tests/unit/execution/test_passive_maker.py`).

**Spec:** `docs/superpowers/specs/2026-06-07-order-router-paper-execution-f3-design.md`

**Worktree:** Implement in `/tmp/f3-impl` (branch `feat/order-router-paper-execution`). Run venv tools from `cd /tmp/f3-impl` using `/home/deploy/project/kis_unified_sts/.venv/bin/{pytest,black,ruff,mypy}`.

**GIT HYGIENE (critical):** NEVER run `git stash`/`pop`/`apply`/`drop` (repo-global; corrupts the operator's stash). Use `git add <paths>` + `git commit` only. No mypy-baseline-via-stash.

**PR strategy:** One PR (`feat/order-router-paper-execution`).

**Out of scope:** orderbook streaming transport (order_router uses its own real WS); F-1 stream-naming (full-chain shadow validation needs it separately); PseudoOCO live-close semantics (fill_logger-only, unchanged); the live execution path (real adapter + LiveModeGuard, unchanged).

---

## File Structure

**Create:**
- `shared/execution/paper_kis_futures_adapter.py` — `PaperKISFuturesAdapter` + `_passive_filled` (pure).
- `tests/unit/execution/test_paper_kis_futures_adapter.py` — adapter + fill-model unit tests.
- `tests/integration/test_order_router_paper_execution.py` — PassiveMaker + paper adapter end-to-end (fill + miss).

**Modify:**
- `services/order_router/main.py` — `_resolve_mode()`, off-inert, feed `is_real=True`, order_executor gated to live, adapter branch (paper/live), daemon `live_mode_guard` branch.

**Verified facts:** `KISFuturesAdapter(*, order_executor, futures_price_feed)` with `get_futures_orderbook(symbol)->SimpleNamespace(bid=[.price],ask=[.price])`, `place_futures_order(*, symbol, side, quantity, order_type, price)->str`, `await_fill(order_id, timeout_seconds)->Fill|None`, `cancel_order(order_id)->bool`. `Fill(order_id, price, quantity, filled_at_ms)` from `shared.execution.passive_maker`. `feed.get_orderbook_snapshot(symbol)->dict` (sync; keys `bid_price_1`/`ask_price_1`, `{}` if none). `feed.get_current_price(symbol)->dict` (async; `close`=last trade, `{}` if none). order_router build at `services/order_router/main.py:356-397` inside `async def _build_and_run()` (294); `live_guard`/`fill_logger`/`spec`/`symbol`/`phase4_config`/`kill_config`/`runtime_ledger`/`redis_client` defined before 356. `PassiveMaker.place_passive_limit_futures` posts limit=best_bid(long)/best_ask(short), calls place→await_fill→(miss)cancel; result has `.is_filled`/`.filled_price`.

---

## Task 1: PaperKISFuturesAdapter + fill model + unit tests

**Files:**
- Create: `shared/execution/paper_kis_futures_adapter.py`
- Test: `tests/unit/execution/test_paper_kis_futures_adapter.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/execution/test_paper_kis_futures_adapter.py`:

```python
"""F-3: PaperKISFuturesAdapter — real orderbook, simulated passive fills, no real orders."""

from __future__ import annotations

import pytest

from shared.execution.paper_kis_futures_adapter import (
    PaperKISFuturesAdapter,
    _passive_filled,
)
from shared.execution.passive_maker import Fill


class _FakeFeed:
    def __init__(self, snapshot: dict, price: dict) -> None:
        self._snap = snapshot
        self._price = price

    async def get_current_price(self, symbol: str) -> dict:
        return dict(self._price)

    def get_orderbook_snapshot(self, symbol: str) -> dict:
        return dict(self._snap)


# ---- _passive_filled (pure) ----

def test_passive_filled_long() -> None:
    # long limit at 100: fills when a trade prints <= 100 OR ask crosses <= 100
    assert _passive_filled("long", 100.0, 99.0, 100.0, 100.5) is True   # trade <= limit
    assert _passive_filled("long", 100.0, 101.0, 100.0, 100.0) is True  # ask <= limit
    assert _passive_filled("long", 100.0, 101.0, 100.0, 100.5) is False  # neither


def test_passive_filled_short() -> None:
    # short limit at 100: fills when trade >= 100 OR bid crosses >= 100
    assert _passive_filled("short", 100.0, 101.0, 99.5, 100.0) is True   # trade >= limit
    assert _passive_filled("short", 100.0, 99.0, 100.0, 100.0) is True   # bid >= limit
    assert _passive_filled("short", 100.0, 99.0, 99.5, 100.0) is False   # neither


def test_passive_filled_none_inputs() -> None:
    assert _passive_filled("long", 100.0, None, None, None) is False


# ---- adapter ----

@pytest.mark.asyncio
async def test_get_futures_orderbook_delegates_to_feed() -> None:
    feed = _FakeFeed({"bid_price_1": 331.20, "ask_price_1": 331.22}, {"close": 331.21})
    adapter = PaperKISFuturesAdapter(futures_price_feed=feed)
    book = await adapter.get_futures_orderbook("A05603")
    assert book.bid[0].price == 331.20
    assert book.ask[0].price == 331.22


@pytest.mark.asyncio
async def test_get_futures_orderbook_empty_raises() -> None:
    adapter = PaperKISFuturesAdapter(futures_price_feed=_FakeFeed({}, {}))
    with pytest.raises(RuntimeError):
        await adapter.get_futures_orderbook("A05603")


@pytest.mark.asyncio
async def test_place_order_synthetic_id_no_real_call() -> None:
    adapter = PaperKISFuturesAdapter(
        futures_price_feed=_FakeFeed({"bid_price_1": 100.0, "ask_price_1": 100.5}, {})
    )
    oid = await adapter.place_futures_order(
        symbol="A05603", side="long", quantity=2, order_type="limit", price=100.0
    )
    assert oid.startswith("PAPER-")
    assert adapter._pending[oid].limit == 100.0
    assert adapter._pending[oid].quantity == 2


@pytest.mark.asyncio
async def test_await_fill_fills_at_limit_when_market_reaches() -> None:
    # long limit 100; market last trade 99 (<= 100) -> fills at the posted limit
    feed = _FakeFeed({"bid_price_1": 100.0, "ask_price_1": 100.5}, {"close": 99.0})
    adapter = PaperKISFuturesAdapter(futures_price_feed=feed, poll_interval=0.01)
    oid = await adapter.place_futures_order(
        symbol="A05603", side="long", quantity=1, order_type="limit", price=100.0
    )
    fill = await adapter.await_fill(oid, timeout_seconds=1)
    assert isinstance(fill, Fill)
    assert fill.price == 100.0  # passive fill at posted limit (slippage 0)
    assert fill.quantity == 1


@pytest.mark.asyncio
async def test_await_fill_misses_on_timeout() -> None:
    # long limit 100; market stays above (trade 101, ask 100.5) -> never fills
    feed = _FakeFeed({"bid_price_1": 100.0, "ask_price_1": 100.5}, {"close": 101.0})
    adapter = PaperKISFuturesAdapter(futures_price_feed=feed, poll_interval=0.01)
    oid = await adapter.place_futures_order(
        symbol="A05603", side="long", quantity=1, order_type="limit", price=100.0
    )
    fill = await adapter.await_fill(oid, timeout_seconds=0.05)
    assert fill is None


@pytest.mark.asyncio
async def test_cancel_order_is_noop_true() -> None:
    adapter = PaperKISFuturesAdapter(
        futures_price_feed=_FakeFeed({"bid_price_1": 100.0, "ask_price_1": 100.5}, {})
    )
    oid = await adapter.place_futures_order(
        symbol="A05603", side="long", quantity=1, order_type="limit", price=100.0
    )
    assert await adapter.cancel_order(oid) is True
    assert oid not in adapter._pending
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /tmp/f3-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/execution/test_paper_kis_futures_adapter.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

Create `shared/execution/paper_kis_futures_adapter.py`:

```python
"""Paper (simulated) KIS futures adapter for the order_router (F-3).

A drop-in for the duck-typed ``kis_client`` interface PassiveMaker uses
(``get_futures_orderbook`` / ``place_futures_order`` / ``await_fill`` /
``cancel_order``). Reads the REAL orderbook from the live futures feed but
simulates passive-limit fills locally — NO real KIS order is ever placed.
Enables paper validation of the decoupled futures execution path with real
market data (KIS 모의투자 does not serve a futures realtime feed).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from shared.execution.passive_maker import Fill

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _PaperOrder:
    symbol: str
    side: str
    limit: float
    quantity: int


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _passive_filled(
    side: str,
    limit: float,
    last_trade: float | None,
    best_bid: float | None,
    best_ask: float | None,
) -> bool:
    """True if a passive limit at ``limit`` would fill given the market state.

    long (resting at best bid): fills when the market trades down to the bid
    (a trade prints <= limit) or the ask crosses to <= limit. short (resting at
    best ask): fills when a trade prints >= limit or the bid crosses >= limit.
    """
    if side == "long":
        return (last_trade is not None and last_trade <= limit) or (
            best_ask is not None and best_ask <= limit
        )
    return (last_trade is not None and last_trade >= limit) or (
        best_bid is not None and best_bid >= limit
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


class PaperKISFuturesAdapter:
    """Simulated futures kis_client: real orderbook in, simulated fills, no orders."""

    def __init__(self, *, futures_price_feed: Any, poll_interval: float = 0.2) -> None:
        self.feed = futures_price_feed
        self._poll_interval = poll_interval
        self._pending: dict[str, _PaperOrder] = {}

    async def get_futures_orderbook(self, symbol: str) -> Any:
        snap = self.feed.get_orderbook_snapshot(symbol)
        if not snap:
            raise RuntimeError(f"no orderbook snapshot for {symbol}")
        return SimpleNamespace(
            bid=[SimpleNamespace(price=float(snap["bid_price_1"]))],
            ask=[SimpleNamespace(price=float(snap["ask_price_1"]))],
        )

    async def place_futures_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        price: float | None,
    ) -> str:
        order_id = f"PAPER-{uuid4().hex[:12]}"
        self._pending[order_id] = _PaperOrder(
            symbol=symbol,
            side=side,
            limit=float(price or 0.0),
            quantity=int(quantity),
        )
        return order_id

    async def await_fill(self, order_id: str, timeout_seconds: int) -> Fill | None:
        order = self._pending.get(order_id)
        if order is None:
            logger.warning("paper await_fill: no pending order %s", order_id)
            return None
        deadline = time.monotonic() + float(timeout_seconds)
        while time.monotonic() < deadline:
            price = await self.feed.get_current_price(order.symbol)
            snap = self.feed.get_orderbook_snapshot(order.symbol) or {}
            last_trade = _to_float((price or {}).get("close"))
            best_bid = _to_float(snap.get("bid_price_1"))
            best_ask = _to_float(snap.get("ask_price_1"))
            if _passive_filled(order.side, order.limit, last_trade, best_bid, best_ask):
                return Fill(
                    order_id=order_id,
                    price=order.limit,
                    quantity=order.quantity,
                    filled_at_ms=_now_ms(),
                )
            await asyncio.sleep(self._poll_interval)
        logger.info("paper await_fill: %s timed out (passive miss)", order_id)
        return None

    async def cancel_order(self, order_id: str) -> bool:
        self._pending.pop(order_id, None)
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /tmp/f3-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/execution/test_paper_kis_futures_adapter.py -v`
Expected: PASS (9 passed).

- [ ] **Step 5: Format + mypy + commit**

```bash
cd /tmp/f3-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black shared/execution/paper_kis_futures_adapter.py tests/unit/execution/test_paper_kis_futures_adapter.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix shared/execution/paper_kis_futures_adapter.py tests/unit/execution/test_paper_kis_futures_adapter.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy shared/execution/paper_kis_futures_adapter.py
git add shared/execution/paper_kis_futures_adapter.py tests/unit/execution/test_paper_kis_futures_adapter.py
git commit -m "feat(f-3): PaperKISFuturesAdapter — real orderbook, simulated passive fills, no real orders"
```
Note: confirm NO mypy errors attributable to the new file (`shared/` is in the type-check gate scope — this file must be clean).

---

## Task 2: order_router mode wiring + integration test

**Files:**
- Modify: `services/order_router/main.py`
- Test: `tests/integration/test_order_router_paper_execution.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/test_order_router_paper_execution.py`:

```python
"""F-3 e2e: PassiveMaker over PaperKISFuturesAdapter — fills/misses, no real orders."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.decision.signal import Signal
from shared.execution.contract_spec import ContractSpec
from shared.execution.paper_kis_futures_adapter import PaperKISFuturesAdapter
from shared.execution.passive_maker import PassiveMaker


class _FakeFeed:
    def __init__(self, snapshot: dict, price: dict) -> None:
        self._snap = snapshot
        self._price = price

    async def get_current_price(self, symbol: str) -> dict:
        return dict(self._price)

    def get_orderbook_snapshot(self, symbol: str) -> dict:
        return dict(self._snap)


def _spec() -> ContractSpec:
    return ContractSpec(
        name="kospi200_mini",
        multiplier_krw_per_point=50_000,
        tick_size_points=0.02,
        tick_value_krw=1_000,
        commission_rate=0.0,
        symbol_prefix="A05",
    )


def _signal(direction: str = "long") -> Signal:
    return Signal(
        setup_type="A_gap_reversion",
        direction=direction,
        symbol="A05603",
        entry_price=331.20,
        stop_loss=330.50,
        take_profit=332.50,
        confidence=0.85,
        valid_until=datetime(2026, 6, 8, 6, 0, tzinfo=UTC),
        generated_at=datetime(2026, 6, 8, 5, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_paper_passive_entry_fills_at_bid_and_logs() -> None:
    # long: limit posted at best_bid 331.20; last trade 331.18 (<= bid) -> fills
    feed = _FakeFeed(
        {"bid_price_1": 331.20, "ask_price_1": 331.22}, {"close": 331.18}
    )
    adapter = PaperKISFuturesAdapter(futures_price_feed=feed, poll_interval=0.01)
    fill_logger = MagicMock()
    fill_logger.log_fill = AsyncMock()
    pm = PassiveMaker(kis_client=adapter, fill_logger=fill_logger)

    result = await pm.place_passive_limit_futures(
        signal=_signal("long"), signal_id="s1", quantity=1, spec=_spec(),
        timeout_seconds=1,
    )

    assert result.is_filled
    assert result.filled_price == 331.20  # passive fill at posted bid
    fill_logger.log_fill.assert_awaited_once()
    # paper: only synthetic order ids ever existed (no real KIS order)
    assert all(oid.startswith("PAPER-") for oid in adapter._pending) or not adapter._pending


@pytest.mark.asyncio
async def test_paper_passive_entry_misses_when_market_away() -> None:
    # long: limit 331.20; market stays above (trade 331.30, ask 331.22) -> miss
    feed = _FakeFeed(
        {"bid_price_1": 331.20, "ask_price_1": 331.22}, {"close": 331.30}
    )
    adapter = PaperKISFuturesAdapter(futures_price_feed=feed, poll_interval=0.01)
    fill_logger = MagicMock()
    fill_logger.log_fill = AsyncMock()
    pm = PassiveMaker(kis_client=adapter, fill_logger=fill_logger)

    result = await pm.place_passive_limit_futures(
        signal=_signal("long"), signal_id="s2", quantity=1, spec=_spec(),
        timeout_seconds=0.05,
    )

    assert not result.is_filled
    fill_logger.log_fill.assert_not_awaited()  # no fill logged on a miss
```

- [ ] **Step 2: Run + iterate**

Run: `cd /tmp/f3-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/integration/test_order_router_paper_execution.py -v`
Expected: PASS (2 passed). If `result.filled_price`/`is_filled` attribute names differ, inspect `shared/execution/order_result.py::OrderResult` and adjust the assertions to the actual fields (do NOT change production code). If `place_passive_limit_futures` rounds the bid to a tick differently, the fill price is `round(331.20, tick 0.02) == 331.20` — unchanged.

- [ ] **Step 3: Wire the mode flag into `services/order_router/main.py`**

Add a module-level helper (near the other module helpers, above `_build_and_run`):
```python
def _resolve_mode() -> str:
    """order_router execution mode: off (default) | paper | live."""
    return os.getenv("FUTURES_ORDER_ROUTER", "off").strip().lower()
```

In `_build_and_run`, immediately after `redis_client` is created (~line 328, after `redis_url = ...`/`redis_client = ...`), add the off-inert gate:
```python
    mode = _resolve_mode()
    if mode not in ("paper", "live"):
        logger.info("FUTURES_ORDER_ROUTER=%s (off) — order_router inert, exiting", mode)
        await redis_client.aclose()
        return 0
```

Replace the build block (currently lines 356-397: `# ExecutionConfig ...` through the `OrderRouterDaemon(...)` close `)`) with the mode-aware version:
```python
    # Feed is ALWAYS real: KIS 모의투자 serves no futures realtime feed, so the
    # real WS is the only orderbook source (paper mode simulates execution, not data).
    kis_auth = KISAuthConfig(
        app_key=os.environ.get("KIS_FUTURES_APP_KEY", ""),
        app_secret=os.environ.get("KIS_FUTURES_APP_SECRET", ""),
        is_real=True,
    )
    futures_feed = KISFuturesPriceFeed(config=kis_auth)
    futures_feed.update_symbols([symbol])
    await futures_feed.start()

    if mode == "paper":
        from shared.execution.paper_kis_futures_adapter import PaperKISFuturesAdapter

        kis_adapter: Any = PaperKISFuturesAdapter(futures_price_feed=futures_feed)
        guard_for_daemon = None  # paper places no real orders
        logger.info("order_router PAPER mode — real orderbook, simulated fills, no real orders")
    else:  # live
        execution_section = ConfigLoader.load("execution.yaml").get("execution", {})
        order_executor = OrderExecutor(ExecutionConfig(**execution_section))
        await order_executor.initialize()
        kis_adapter = KISFuturesAdapter(
            order_executor=order_executor,
            futures_price_feed=futures_feed,
        )
        guard_for_daemon = live_guard

    passive_maker = PassiveMaker(kis_client=kis_adapter, fill_logger=fill_logger)
    pseudo_oco = PseudoOCO(fill_logger=fill_logger)

    worker_id = f"order-router-{socket.gethostname()}-{os.getpid()}"
    daemon = OrderRouterDaemon(
        redis=redis_client,
        passive_maker=passive_maker,
        pseudo_oco=pseudo_oco,
        contract_spec=spec,
        final_stream="stream:signal.final",
        consumer_group="order_router",
        worker_id=worker_id,
        xread_block_ms=phase4_config.xread_block_ms,
        batch_size=phase4_config.xread_batch_size,
        passive_timeout_seconds=phase4_config.passive_timeout_seconds,
        base_quantity=phase4_config.base_quantity,
        kill_switch_sentinel_path=kill_config.sentinel_path,
        live_mode_guard=guard_for_daemon,
        locked_symbol=symbol,
    )
```
(Ensure `from typing import Any` is imported at module top — it is used elsewhere in the file; if not, add it. The `OrderExecutor`/`ExecutionConfig`/`ConfigLoader`/`KISFuturesAdapter`/`KISAuthConfig`/`KISFuturesPriceFeed`/`PassiveMaker`/`PseudoOCO`/`OrderRouterDaemon` imports already exist at the top — keep them.)

- [ ] **Step 4: Verify the mode wiring (no regression to live; off-inert; paper selects paper adapter)**

Run: `cd /tmp/f3-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/integration/test_order_router_paper_execution.py tests/unit/execution/ -q`
Then a focused import + off-inert smoke check:
```bash
cd /tmp/f3-impl && FUTURES_ORDER_ROUTER=off /home/deploy/project/kis_unified_sts/.venv/bin/python -c "
import asyncio, services.order_router.main as m
print('resolve off ->', m._resolve_mode())
"
```
Expected: tests PASS; `_resolve_mode()` returns `off`. (Full off-inert `_build_and_run` returns 0 without building the feed — but it builds redis first; the smoke check above just confirms the helper. A deeper off-inert test is optional given the early `return 0`.)

- [ ] **Step 5: black + ruff + commit**

```bash
cd /tmp/f3-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black services/order_router/main.py tests/integration/test_order_router_paper_execution.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix services/order_router/main.py tests/integration/test_order_router_paper_execution.py
git add services/order_router/main.py tests/integration/test_order_router_paper_execution.py
git commit -m "feat(f-3): order_router FUTURES_ORDER_ROUTER mode (off/paper/live); feed always real"
```

---

## Task 3: Full gate + PR

- [ ] **Step 1: Targeted + regression**

```bash
cd /tmp/f3-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/execution/ tests/integration/test_order_router_paper_execution.py -q
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -k "passive_maker or order_router or kis_futures_adapter" -q
```
Expected: all PASS (the second proves unchanged `PassiveMaker`/`KISFuturesAdapter`/order_router daemon still green).

- [ ] **Step 2: Full gate (CI parity)**

```bash
cd /tmp/f3-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m serial -q
```
Expected: green.

- [ ] **Step 3: mypy (gate scope = shared/)**

```bash
cd /tmp/f3-impl
/home/deploy/project/kis_unified_sts/.venv/bin/mypy shared/execution/paper_kis_futures_adapter.py
```
Expected: clean (new `shared/` file must pass the type-check gate).

- [ ] **Step 4: Push + PR**

```bash
cd /tmp/f3-impl
git push -u origin feat/order-router-paper-execution
gh pr create --base main --head feat/order-router-paper-execution \
  --title "feat(f-3): order_router paper execution (real orderbook, simulated passive fills)" \
  --body "$(cat <<'EOF'
## What
A `PaperKISFuturesAdapter` + a `FUTURES_ORDER_ROUTER` mode flag (off/paper/live) so
the decoupled futures order_router can run in PAPER mode — real WS orderbook in,
faithful passive-limit fills simulated locally, recorded to FillLogger, with ZERO
real KIS orders.

## Why
The order_router was real-execution-only and, run against KIS 모의투자
(`KIS_FUTURES_MARKET=mock`), connected to a mock WS that serves no futures realtime
feed → empty orderbook → every signal failed (the "orderbook problem"). KIS 모의투자
does not support the futures realtime WS (`H0IFCNT0`/`H0IFASP0` are real-account-only),
so faithful validation needs **real data + local simulated execution** — exactly what
F-3 provides.

## Approach — paper kis_client, real feed, no real orders
`PassiveMaker` is already decoupled via a duck-typed `kis_client` interface. F-3 adds
a paper implementation: `get_futures_orderbook` reads the real feed; `place_futures_order`
returns a synthetic `PAPER-…` id (no KIS call); `await_fill` runs a faithful tick-watch
model (`_passive_filled`: long fills when a trade prints ≤ limit or the ask crosses;
short symmetric) and fills at the posted limit (slippage 0) or returns None on timeout
(passive miss); `cancel_order` is a no-op. The feed is **always `is_real=True`** (real
orderbook — the only source); only execution is paper/live. `PassiveMaker`, `PseudoOCO`
(fill_logger-only, already paper-compatible), `OrderRouterDaemon`, and `FillLogger` are
UNCHANGED — only the injected `kis_client` + the mode wiring differ. The live path (real
adapter + `LiveModeGuard`) is unchanged.

## Scope
F-3 = the paper-execution capability + unit/integration validation. End-to-end chain
validation (decision_engine → risk_filter → order_router-paper → fill) also needs F-1
(stream-naming coherence). Orderbook streaming transport is deferred (order_router uses
its own real WS, like the orchestrator).

## How tested
Unit (`test_paper_kis_futures_adapter.py`): `_passive_filled` matrix (long/short ×
trade/cross/none), synthetic-id place (no real call), await_fill fill-at-limit + miss-
on-timeout, get_orderbook delegation + empty→RuntimeError, no-op cancel. Integration
(`test_order_router_paper_execution.py`): PassiveMaker over the paper adapter fills at
the bid + logs, and misses when the market stays away (no fill logged). Full `tests/`
gate green; mypy clean on the new `shared/` file.

Spec: `docs/superpowers/specs/2026-06-07-order-router-paper-execution-f3-design.md`
Plan: `docs/superpowers/plans/2026-06-07-order-router-paper-execution-f3.md`

## Follow-ups
F-1 (stream-naming coherence — enables end-to-end shadow), F-2 (decision_engine live
producer), F-4/F-5/F-6, F-8/F-9 cutover. Orderbook streaming transport if dual-WS
becomes a constraint.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Run code review** — `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:**
- §4.1 PaperKISFuturesAdapter (4 methods, synthetic id, real-feed orderbook) → Task 1. ✓
- §4.2 order_router mode wiring (off/paper/live, feed always real, order_executor gated to live, daemon guard branch) → Task 2 Step 3. ✓
- §4.3 unchanged PassiveMaker/PseudoOCO/daemon/FillLogger → only injected client + wiring; integration test uses real PassiveMaker. ✓
- §5 faithful fill model (`_passive_filled`, fill@limit, timeout→miss, poll injectable) → Task 1 Step 3 + tests. ✓
- §6 error handling (no real orders structurally; staleness→miss; off→inert) → adapter (local-only) + `_resolve_mode` off gate. ✓
- §7 testing (`_passive_filled` matrix, adapter, PassiveMaker integration, regression) → Tasks 1-3. ✓
- §8 acceptance → Tasks 1-3. ✓

**Placeholder scan:** none — complete code in every step.

**Type consistency:** `PaperKISFuturesAdapter(*, futures_price_feed, poll_interval=0.2)`, `_passive_filled(side, limit, last_trade, best_bid, best_ask) -> bool`, `Fill(order_id, price, quantity, filled_at_ms)`, `get_futures_orderbook -> SimpleNamespace(bid=[.price], ask=[.price])`, `place_futures_order(*, symbol, side, quantity, order_type, price) -> str`, `await_fill(order_id, timeout_seconds) -> Fill|None`, `cancel_order -> bool` — all consistent between adapter, tests, and the PassiveMaker interface it mirrors (`KISFuturesAdapter`). Feed methods: `get_current_price` (async) / `get_orderbook_snapshot` (sync, `bid_price_1`/`ask_price_1`) match `KISFuturesPriceFeed`. `_resolve_mode` returns off/paper/live; the build branch matches. The integration test's `Signal`/`ContractSpec` match `tests/unit/execution/test_passive_maker.py`; `result.is_filled`/`.filled_price` match the daemon's usage (`order_router/main.py:262`).

**Open questions resolved:** fill price = posted limit (passive); no partial-fill modeling (all/miss, YAGNI); mode flag `FUTURES_ORDER_ROUTER`; feed always real (execution-only paper/live split); test locations `tests/unit/execution/` + `tests/integration/`.
