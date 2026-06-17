# Futures WS Auto-Reconnect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `KISFuturesPriceFeed` automatic WebSocket reconnect (exponential backoff + re-subscribe + `record_ws_reconnect("futures")` metric) at parity with the stock feed, confined to the futures-feed wrapper.

**Architecture:** A supervisor thread replaces the bare `adapter.subscribe` worker in `start()`. It runs the initial subscribe loop, then on drop retries with backoff using a *fresh* `KISWebSocketAdapter` per attempt. A deliberate `stop()` (which sets `_running=False` before `disconnect()`) never triggers reconnect. Backoff knobs come from `config/streaming.yaml::futures_feed`.

**Tech Stack:** Python 3.11, `threading`, `pytest` (run via `.venv/bin/pytest`), Prometheus collector (`services.monitoring.metrics`).

**Reference (proven pattern):** `shared/kis/stock_feed.py` — `_record_ws_metric` (45-57), `_reconnect` (469-515), `_on_close` reconnect spawn (454-467), config reads (197-199).

**Spec:** `docs/superpowers/specs/2026-06-07-futures-ws-auto-reconnect-design.md`

---

### Task 1: Config knobs for reconnect backoff

**Files:**
- Modify: `config/streaming.yaml` (futures_feed section, after `orderbook_missing_warn_interval_seconds`)
- Modify: `shared/kis/futures_feed.py:64-74` (`__init__` config reads)
- Test: `tests/unit/kis/test_futures_feed_reconnect.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/kis/test_futures_feed_reconnect.py`:

```python
"""Futures WS auto-reconnect: config knobs, metric helper, supervisor backoff."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import shared.kis.futures_feed as ff
from shared.kis.auth import KISAuthConfig
from shared.kis.futures_feed import KISFuturesPriceFeed


def _make_feed() -> KISFuturesPriceFeed:
    return KISFuturesPriceFeed(
        config=KISAuthConfig(app_key="k", app_secret="s", is_real=True)
    )


class TestReconnectConfigKnobs:
    def test_reads_reconnect_delays_from_config(self):
        feed = _make_feed()
        # streaming.yaml::futures_feed provides 1.0 / 60.0
        assert feed._reconnect_initial_delay == 1.0
        assert feed._reconnect_max_delay == 60.0

    def test_defaults_when_keys_absent(self):
        cfg = {
            "max_symbols": 10,
            "subscription_delay": 0.05,
            "connection_timeout": 10.0,
            "shutdown_timeout": 5.0,
        }
        with patch.object(ff, "_load_futures_feed_config", return_value=cfg):
            feed = _make_feed()
        assert feed._reconnect_initial_delay == 1.0
        assert feed._reconnect_max_delay == 60.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/kis/test_futures_feed_reconnect.py::TestReconnectConfigKnobs -v`
Expected: FAIL with `AttributeError: '_reconnect_initial_delay'`

- [ ] **Step 3: Add config knobs to streaming.yaml**

In `config/streaming.yaml`, under `futures_feed:`, after the
`orderbook_missing_warn_interval_seconds: 30.0` line, add:

```yaml
  reconnect_initial_delay: 1.0   # 재접속 초기 대기 (초)
  reconnect_max_delay: 60.0      # 재접속 최대 대기 (초)
```

- [ ] **Step 4: Read knobs in `__init__`**

In `shared/kis/futures_feed.py`, immediately after the
`self._orderbook_missing_warn_interval = float(...)` block (currently ends at
line 74), add:

```python
        self._reconnect_initial_delay = float(
            feed_cfg.get("reconnect_initial_delay", 1.0)
        )
        self._reconnect_max_delay = float(
            feed_cfg.get("reconnect_max_delay", 60.0)
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/kis/test_futures_feed_reconnect.py::TestReconnectConfigKnobs -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add config/streaming.yaml shared/kis/futures_feed.py tests/unit/kis/test_futures_feed_reconnect.py
git commit -m "feat(futures-feed): reconnect backoff config knobs"
```

---

### Task 2: Best-effort `_record_ws_reconnect` helper

**Files:**
- Modify: `shared/kis/futures_feed.py` (module level, after the imports / before `_load_futures_feed_config`, around line 24)
- Test: `tests/unit/kis/test_futures_feed_reconnect.py` (append class)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/kis/test_futures_feed_reconnect.py`:

```python
class TestRecordWsReconnectHelper:
    def test_calls_collector(self):
        fake = MagicMock()
        with patch(
            "services.monitoring.metrics.get_metrics_collector",
            return_value=fake,
        ):
            ff._record_ws_reconnect("futures")
        fake.record_ws_reconnect.assert_called_once_with("futures")

    def test_swallows_collector_construction_failure(self):
        with patch(
            "services.monitoring.metrics.get_metrics_collector",
            side_effect=RuntimeError("boom"),
        ):
            ff._record_ws_reconnect("futures")  # must not raise

    def test_swallows_method_failure(self):
        fake = MagicMock()
        fake.record_ws_reconnect.side_effect = RuntimeError("boom")
        with patch(
            "services.monitoring.metrics.get_metrics_collector",
            return_value=fake,
        ):
            ff._record_ws_reconnect("futures")  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/kis/test_futures_feed_reconnect.py::TestRecordWsReconnectHelper -v`
Expected: FAIL with `AttributeError: module 'shared.kis.futures_feed' has no attribute '_record_ws_reconnect'`

- [ ] **Step 3: Add the helper**

In `shared/kis/futures_feed.py`, after `logger = logging.getLogger(__name__)`
(line 23) and before `def _load_futures_feed_config`, add:

```python
def _record_ws_reconnect(feed: str) -> None:
    """Best-effort WS reconnect counter.

    Lazy guarded import so a missing/failing collector never breaks the
    WebSocket supervisor thread.
    """
    try:
        from services.monitoring.metrics import get_metrics_collector

        get_metrics_collector().record_ws_reconnect(feed)
    except Exception:  # noqa: BLE001 — observability must never break the WS thread
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/kis/test_futures_feed_reconnect.py::TestRecordWsReconnectHelper -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add shared/kis/futures_feed.py tests/unit/kis/test_futures_feed_reconnect.py
git commit -m "feat(futures-feed): best-effort _record_ws_reconnect helper"
```

---

### Task 3: Reconnect supervisor + `start()` hook

**Files:**
- Modify: `shared/kis/futures_feed.py` — `start()` (200-205 thread target) + new `_run_with_reconnect` method (insert after `start()`, before `stop()`)
- Test: `tests/unit/kis/test_futures_feed_reconnect.py` (append classes)

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/kis/test_futures_feed_reconnect.py`:

```python
class TestStartUsesSupervisor:
    @pytest.mark.asyncio
    async def test_start_thread_targets_supervisor(self):
        feed = _make_feed()
        feed._adapter = MagicMock()  # connect() is a no-op mock
        feed.update_symbols(["A05603"])
        captured = {}

        class FakeThread:
            def __init__(self, *a, **kw):
                captured.update(kw)

            def start(self):
                pass  # mocked: nothing runs

        with patch.object(ff.threading, "Thread", FakeThread):
            await feed.start()

        assert captured["target"] == feed._run_with_reconnect


class TestSupervisorNoReconnectAfterStop:
    def test_no_reconnect_when_not_running(self):
        feed = _make_feed()
        feed._symbols = ["A05603"]
        feed._running = False  # deliberate stop state
        initial_adapter = MagicMock()
        feed._adapter = initial_adapter

        with (
            patch.object(ff, "KISWebSocketAdapter") as ctor,
            patch.object(ff, "_record_ws_reconnect") as rec,
            patch.object(ff.time, "sleep") as sleep,
        ):
            feed._run_with_reconnect()

        initial_adapter.subscribe.assert_called_once()  # initial loop only
        ctor.assert_not_called()  # no fresh adapter
        rec.assert_not_called()
        sleep.assert_not_called()


class TestSupervisorBackoff:
    def test_reconnects_and_records_metric(self):
        feed = _make_feed()
        feed._symbols = ["A05603"]
        feed._running = True
        feed._reconnect_initial_delay = 1.0
        feed._reconnect_max_delay = 60.0
        feed._adapter = MagicMock()  # initial subscribe returns immediately

        sleeps: list[float] = []

        def fake_sleep(d):
            sleeps.append(d)
            if len(sleeps) >= 2:
                feed._running = False  # stop after second loop entry

        fresh = MagicMock()  # connect ok, subscribe returns immediately

        with (
            patch.object(ff, "KISWebSocketAdapter", return_value=fresh) as ctor,
            patch.object(ff, "_record_ws_reconnect") as rec,
            patch.object(ff.time, "sleep", side_effect=fake_sleep),
        ):
            feed._run_with_reconnect()

        ctor.assert_called_once_with(feed._config)
        fresh.connect.assert_called_once()
        rec.assert_called_once_with("futures")
        assert sleeps[0] == 1.0  # initial delay used

    def test_backoff_escalates_and_caps_on_connect_failure(self):
        feed = _make_feed()
        feed._symbols = ["A05603"]
        feed._running = True
        feed._reconnect_initial_delay = 1.0
        feed._reconnect_max_delay = 3.0  # low cap to prove min()
        feed._adapter = MagicMock()

        sleeps: list[float] = []

        def fake_sleep(d):
            sleeps.append(d)
            if len(sleeps) >= 4:
                feed._running = False

        failing = MagicMock()
        failing.connect.side_effect = RuntimeError("server down")

        with (
            patch.object(ff, "KISWebSocketAdapter", return_value=failing),
            patch.object(ff, "_record_ws_reconnect") as rec,
            patch.object(ff.time, "sleep", side_effect=fake_sleep),
        ):
            feed._run_with_reconnect()

        # 1.0 -> 2.0 -> min(4.0,3.0)=3.0 -> capped 3.0
        assert sleeps == [1.0, 2.0, 3.0, 3.0]
        rec.assert_not_called()  # connect never succeeded

    def test_resets_backoff_after_successful_reconnect(self):
        feed = _make_feed()
        feed._symbols = ["A05603"]
        feed._running = True
        feed._reconnect_initial_delay = 1.0
        feed._reconnect_max_delay = 60.0
        feed._adapter = MagicMock()

        sleeps: list[float] = []

        def fake_sleep(d):
            sleeps.append(d)
            if len(sleeps) >= 2:
                feed._running = False

        fresh = MagicMock()  # both reconnects succeed, subscribe returns

        with (
            patch.object(ff, "KISWebSocketAdapter", return_value=fresh),
            patch.object(ff, "_record_ws_reconnect"),
            patch.object(ff.time, "sleep", side_effect=fake_sleep),
        ):
            feed._run_with_reconnect()

        # success resets delay, so both sleeps are the initial delay
        assert sleeps == [1.0, 1.0]
```

Note: only `test_start_thread_targets_supervisor` is async — decorate it with
`@pytest.mark.asyncio` (matching `tests/unit/kis/test_futures_feed.py`, which uses
the same explicit marker). Ensure `import pytest` is present at the top of the file
(add it in Task 1's test file if missing).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/kis/test_futures_feed_reconnect.py -v`
Expected: FAIL — `_run_with_reconnect` does not exist; `start()` targets `self._adapter.subscribe` not `self._run_with_reconnect`.

- [ ] **Step 3: Change `start()` thread target**

In `shared/kis/futures_feed.py`, in `start()`, change the thread construction
(currently lines 200-205) from:

```python
        self._thread = threading.Thread(
            target=self._adapter.subscribe,
            args=(self._symbols, self._on_tick),
            daemon=True,
            name="FuturesPriceFeed",
        )
```

to:

```python
        self._thread = threading.Thread(
            target=self._run_with_reconnect,
            daemon=True,
            name="FuturesPriceFeed",
        )
```

- [ ] **Step 4: Add the `_run_with_reconnect` supervisor**

In `shared/kis/futures_feed.py`, insert this method between `start()` and
`stop()` (after the `start()` method's final `logger.info(...)` return, before
`async def stop`):

```python
    def _run_with_reconnect(self) -> None:
        """Worker thread: run the subscribe loop, reconnect on drop.

        Runs the initial ``subscribe`` (the adapter is already connected by
        ``start()``); it blocks until the WebSocket drops or ``stop()`` is
        called. On an *unexpected* drop (``_running`` still True), retries with
        exponential backoff using a fresh adapter per attempt, re-subscribes,
        and records ``record_ws_reconnect("futures")``. A deliberate ``stop()``
        (which sets ``_running=False`` before ``disconnect()``) ends the loop
        without reconnecting. Mirrors ``KISStockPriceFeed._reconnect``.
        """
        try:
            self._adapter.subscribe(self._symbols, self._on_tick)
        except Exception as e:  # noqa: BLE001 — log and fall through to reconnect
            logger.error(f"[FuturesPriceFeed] Subscribe loop error: {e}")

        delay = self._reconnect_initial_delay
        while self._running:
            time.sleep(delay)
            if not self._running:
                break
            try:
                # The previous adapter is spent (is_running permanently False);
                # build a fresh one for the new connection.
                self._adapter = KISWebSocketAdapter(self._config)
                self._adapter.connect()
                logger.info("[FuturesPriceFeed] Reconnected to futures WS feed")
                _record_ws_reconnect("futures")
                delay = self._reconnect_initial_delay  # reset backoff on success
                self._adapter.subscribe(self._symbols, self._on_tick)
                # subscribe() returned: WS dropped again (or stop()).
                # Loop re-checks _running at the top.
            except Exception as e:  # noqa: BLE001 — backoff and retry
                logger.error(f"[FuturesPriceFeed] Reconnect attempt failed: {e}")
                delay = min(delay * 2, self._reconnect_max_delay)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/kis/test_futures_feed_reconnect.py -v`
Expected: PASS (all classes)

- [ ] **Step 6: Run the existing futures-feed tests (no regression)**

Run: `.venv/bin/pytest tests/unit/kis/test_futures_feed.py tests/unit/kis/test_ws_observability.py -v`
Expected: PASS (unchanged behavior; disconnect metric still recorded by adapter)

- [ ] **Step 7: Commit**

```bash
git add shared/kis/futures_feed.py tests/unit/kis/test_futures_feed_reconnect.py
git commit -m "feat(futures-feed): WS auto-reconnect supervisor (exponential backoff + re-subscribe)"
```

---

## Self-Review (already applied)

- **Spec coverage:** config knobs (Task 1) ✓, metric helper (Task 2) ✓, supervisor + start() hook + stop-distinction + backoff/cap/reset (Task 3) ✓.
- **Type consistency:** `_run_with_reconnect` (one name throughout), `_record_ws_reconnect` (matches `websocket._record_ws_disconnect` style), `_reconnect_initial_delay` / `_reconnect_max_delay` (match stock feed `_reconnect_delay` semantics but named for clarity).
- **No placeholders:** every step has full code.
