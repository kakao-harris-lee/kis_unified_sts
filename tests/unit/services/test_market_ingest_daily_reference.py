"""market-ingest keeps the futures prev_close read-model published every trade day.

After the F-9 cutover retires the orchestrator, this daemon is the only futures
process left holding KIS credentials. The decision-engine only accepts a
reference stamped with today's KST date, so a publish at boot alone would leave
Setup A blind from the second day on — and a single boot failure would leave it
blind for the container's life. These tests drive the poll with an injected
clock; loop-level tests wait on events with a deadline, never a fixed sleep.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, time

import fakeredis
import pytest

from services.market_ingest.main import (
    MarketIngestDaemon,
    _build_daily_reference_prefetch,
)
from shared.strategy.market_time import KST
from shared.streaming.daily_reference import (
    DailyReferenceSchedule,
    load_daily_reference_config,
    read_futures_daily_reference,
)

SYMBOL = "A05609"
NEXT_SYMBOL = "A05612"
# 2026-09-14 (Mon) and 2026-09-15 (Tue) are KRX trading days; 09-12 is a Saturday.
MONDAY_0900 = datetime(2026, 9, 14, 9, 0, tzinfo=KST)
TUESDAY_0900 = datetime(2026, 9, 15, 9, 0, tzinfo=KST)
SCHEDULE = DailyReferenceSchedule(poll_seconds=60, publish_from=time(8, 45))
DEADLINE_S = 2.0


class _Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class _KISClient:
    def __init__(self, prev_close=411.25):
        self.prev_close = prev_close
        self.calls: list[str] = []

    async def _get_futures_price(self, symbol):
        self.calls.append(symbol)
        return {"price": 412.0, "prev_close": self.prev_close}


class _Feed:
    def __init__(self):
        self.callback = None

    def set_tick_callback(self, cb):
        self.callback = cb

    def update_symbols(self, symbols, *args, **kwargs):  # noqa: ARG002
        pass

    async def start(self):
        pass

    async def stop(self):
        pass

    def is_healthy(self) -> bool:
        return True


class _Publisher:
    def publish(self, asset, symbol, payload):
        pass

    def close(self, timeout: float = 2.0):  # noqa: ARG002
        pass


class _RecordingPrefetch:
    """Prefetch double: scripted outcomes, records every call."""

    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or [])
        self.calls: list[tuple[list[str], datetime]] = []
        self.succeeded = asyncio.Event()

    async def __call__(self, symbols, asof):
        self.calls.append((list(symbols), asof))
        outcome = self.outcomes.pop(0) if self.outcomes else True
        if isinstance(outcome, Exception):
            raise outcome
        if outcome:
            self.succeeded.set()
        return outcome


async def _static_provider() -> list[str]:
    return [SYMBOL]


def _daemon(
    prefetch, *, clock=None, schedule=SCHEDULE, refresh_interval_seconds=3600.0
) -> MarketIngestDaemon:
    daemon = MarketIngestDaemon(
        asset="futures",
        feed=_Feed(),
        publisher=_Publisher(),
        symbol_provider=_static_provider,
        refresh_interval_seconds=refresh_interval_seconds,
        daily_reference_prefetch=prefetch,
        daily_reference_schedule=schedule,
        now_fn=clock or _Clock(MONDAY_0900),
    )
    daemon._symbols = [SYMBOL]
    return daemon


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def _no_freshness_writes(monkeypatch):
    monkeypatch.setenv("INGEST_DATA_FRESHNESS_ENABLED", "false")


# ---------------------------------------------------------------------------
# prefetch builder — delegation to the shared helper
# ---------------------------------------------------------------------------


async def test_prefetch_publishes_through_the_shared_helper(redis_client):
    kis = _KISClient(prev_close=411.25)
    prefetch = _build_daily_reference_prefetch(kis, redis_client)

    assert await prefetch([SYMBOL], MONDAY_0900) is True

    payload = read_futures_daily_reference(redis_client, SYMBOL)
    assert payload is not None
    assert payload["prev_close"] == 411.25
    assert payload["source"] == "kis_rest"
    assert payload["producer"] == "market-ingest"
    assert payload["asof_ts"] == "2026-09-14T09:00:00+09:00"
    assert kis.calls == [SYMBOL]


async def test_prefetch_reports_a_partial_publish_as_failure(redis_client):
    """A False return is what makes the daemon retry on the next poll."""
    prefetch = _build_daily_reference_prefetch(_KISClient(prev_close=0), redis_client)

    assert await prefetch([SYMBOL], MONDAY_0900) is False
    assert read_futures_daily_reference(redis_client, SYMBOL) is None


# ---------------------------------------------------------------------------
# one poll, injected clock
# ---------------------------------------------------------------------------


async def test_republishes_on_the_next_trade_day_with_that_days_asof(redis_client):
    """R1 regression: the boot-only publish went stale on day two."""
    clock = _Clock(MONDAY_0900)
    kis = _KISClient()
    daemon = _daemon(_build_daily_reference_prefetch(kis, redis_client), clock=clock)

    assert await daemon._publish_daily_reference_if_due() is True
    assert read_futures_daily_reference(redis_client, SYMBOL)["asof_ts"] == (
        "2026-09-14T09:00:00+09:00"
    )

    clock.now = datetime(2026, 9, 14, 14, 0, tzinfo=KST)
    assert await daemon._publish_daily_reference_if_due() is False
    assert kis.calls == [SYMBOL], "one REST call per trade day"

    clock.now = TUESDAY_0900
    assert await daemon._publish_daily_reference_if_due() is True
    assert read_futures_daily_reference(redis_client, SYMBOL)["asof_ts"] == (
        "2026-09-15T09:00:00+09:00"
    )
    assert kis.calls == [SYMBOL, SYMBOL]


async def test_does_not_publish_before_the_window_opens():
    clock = _Clock(datetime(2026, 9, 15, 8, 44, tzinfo=KST))
    prefetch = _RecordingPrefetch()
    daemon = _daemon(prefetch, clock=clock)

    assert await daemon._publish_daily_reference_if_due() is False
    assert prefetch.calls == []

    clock.now = datetime(2026, 9, 15, 8, 45, tzinfo=KST)
    assert await daemon._publish_daily_reference_if_due() is True
    assert prefetch.calls == [([SYMBOL], clock.now)]


async def test_does_not_publish_on_a_non_trading_day():
    prefetch = _RecordingPrefetch()
    daemon = _daemon(prefetch, clock=_Clock(datetime(2026, 9, 12, 10, 0, tzinfo=KST)))

    assert await daemon._publish_daily_reference_if_due() is False
    assert prefetch.calls == []


async def test_a_raising_prefetch_is_retried_on_the_next_poll(caplog):
    prefetch = _RecordingPrefetch([ConnectionError("tokenP EGW00133"), True])
    daemon = _daemon(prefetch)

    with caplog.at_level("WARNING"):
        assert await daemon._publish_daily_reference_if_due() is False
    assert "daily_reference prefetch failed for A05609" in caplog.text

    assert await daemon._publish_daily_reference_if_due() is True
    assert len(prefetch.calls) == 2
    assert await daemon._publish_daily_reference_if_due() is False
    assert len(prefetch.calls) == 2, "success latches the day"


async def test_a_partial_publish_is_retried_on_the_next_poll():
    prefetch = _RecordingPrefetch([False, True])
    daemon = _daemon(prefetch)

    assert await daemon._publish_daily_reference_if_due() is False
    assert await daemon._publish_daily_reference_if_due() is True
    assert len(prefetch.calls) == 2


async def test_a_rollover_republishes_the_new_contract_the_same_day():
    prefetch = _RecordingPrefetch()
    daemon = _daemon(prefetch)
    assert await daemon._publish_daily_reference_if_due() is True

    await daemon._apply_symbols([NEXT_SYMBOL])

    assert await daemon._publish_daily_reference_if_due() is True
    assert [symbols for symbols, _ in prefetch.calls] == [[SYMBOL], [NEXT_SYMBOL]]


async def test_apply_symbols_never_waits_on_the_prefetch():
    """R1: the inline await on a symbol change blocked the refresh loop."""
    never = asyncio.Event()

    async def _blocked(_symbols, _asof):
        await never.wait()
        return True

    daemon = _daemon(_blocked)
    await asyncio.wait_for(daemon._apply_symbols([NEXT_SYMBOL]), timeout=DEADLINE_S)
    assert daemon._symbols == [NEXT_SYMBOL]


async def test_stock_ingest_has_no_daily_reference_loop():
    """Stock has no prev_close read-model — the loop exits immediately."""
    daemon = MarketIngestDaemon(
        asset="stock",
        feed=_Feed(),
        publisher=_Publisher(),
        symbol_provider=_static_provider,
        refresh_interval_seconds=3600.0,
    )
    assert daemon.daily_reference_prefetch is None
    await asyncio.wait_for(daemon._daily_reference_loop(), timeout=DEADLINE_S)
    assert await daemon._publish_daily_reference_if_due() is False


def test_the_schedule_defaults_to_the_yaml_config():
    daemon = MarketIngestDaemon(
        asset="futures",
        feed=_Feed(),
        publisher=_Publisher(),
        symbol_provider=_static_provider,
        refresh_interval_seconds=3600.0,
        daily_reference_prefetch=_RecordingPrefetch(),
    )
    assert daemon._daily_reference_schedule is not None
    assert (
        daemon._daily_reference_schedule.poll_seconds
        == load_daily_reference_config().poll_seconds
    )


# ---------------------------------------------------------------------------
# run() wiring — background task, deadline-bounded waits
# ---------------------------------------------------------------------------


async def test_run_starts_the_freshness_loop_while_the_prefetch_is_blocked():
    """R1: the boot prefetch was awaited inline before freshness_task existed,
    and delayed SIGTERM handling for as long as KIS took."""
    entered = asyncio.Event()
    release = asyncio.Event()

    async def _blocked(_symbols, _asof):
        entered.set()
        await release.wait()
        return True

    daemon = _daemon(_blocked)
    freshness_started = asyncio.Event()

    async def _freshness_probe():
        freshness_started.set()

    daemon._freshness_loop = _freshness_probe
    task = asyncio.create_task(daemon.run())

    await asyncio.wait_for(entered.wait(), timeout=DEADLINE_S)
    await asyncio.wait_for(freshness_started.wait(), timeout=DEADLINE_S)
    assert not release.is_set(), "the prefetch is still blocked"

    await daemon.stop()
    await asyncio.wait_for(task, timeout=DEADLINE_S)


async def test_run_retries_a_failed_boot_publish_on_the_poll_interval():
    prefetch = _RecordingPrefetch([ConnectionError("KIS unreachable"), True])
    daemon = _daemon(
        prefetch, schedule=DailyReferenceSchedule(0.01, publish_from=time(8, 45))
    )

    task = asyncio.create_task(daemon.run())
    await asyncio.wait_for(prefetch.succeeded.wait(), timeout=DEADLINE_S)
    await daemon.stop()
    await asyncio.wait_for(task, timeout=DEADLINE_S)

    assert len(prefetch.calls) == 2


async def test_a_daily_reference_loop_crash_is_logged_and_ingest_keeps_running(
    caplog,
):
    feed = _Feed()
    daemon = _daemon(_RecordingPrefetch())
    daemon.feed = feed
    crashed = asyncio.Event()

    async def _crash():
        crashed.set()
        raise RuntimeError("loop exploded")

    daemon._daily_reference_loop = _crash

    with caplog.at_level("ERROR"):
        task = asyncio.create_task(daemon.run())
        await asyncio.wait_for(crashed.wait(), timeout=DEADLINE_S)
        await daemon.stop()
        await asyncio.wait_for(task, timeout=DEADLINE_S)

    assert feed.callback is not None, "the daemon kept running and wired its feed"
    assert "daily_reference loop crashed" in caplog.text
