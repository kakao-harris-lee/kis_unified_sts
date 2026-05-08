"""Unit tests for shared/strategy/llm_veto_logger.py.

Test coverage
-------------
1. ``record_veto()`` appends to the in-memory buffer.
2. ``pending_count()`` reflects the current buffer length.
3. ``flush_llm_veto_events()`` drains the buffer and calls the CH client.
4. Flush with an empty buffer returns 0 without calling CH.
5. CH insert failure → batch dropped, ``dropped_counts()`` incremented,
   flush returns 0 (best-effort semantics).
6. Buffered payload ``ts`` is preserved as tz-aware UTC.
7. ``maxlen`` bound prevents unbounded growth.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

import shared.strategy.llm_veto_logger as veto_logger

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts() -> datetime:
    """Return a fixed tz-aware UTC datetime for testing."""
    return datetime(2026, 5, 4, 1, 0, 0, tzinfo=UTC)


def _payload(
    *,
    symbol: str = "A05603",
    direction: str = "long",
    regime: str = "BEAR_STRONG",
    overall_signal: str = "STRONG_BEARISH",
    confidence: float = 0.75,
    setup: str = "setup_a_gap_reversion",
    ts: datetime | None = None,
) -> dict:
    """Build a minimal veto event payload."""
    return {
        "ts": ts or _ts(),
        "symbol": symbol,
        "direction": direction,
        "regime": regime,
        "overall_signal": overall_signal,
        "confidence": confidence,
        "setup": setup,
    }


@pytest.fixture(autouse=True)
def _reset_logger():
    """Reset global buffer and counters before each test."""
    veto_logger._pending_veto_events.clear()
    veto_logger._dropped_batch_count = 0
    veto_logger._dropped_row_count = 0
    yield
    veto_logger._pending_veto_events.clear()
    veto_logger._dropped_batch_count = 0
    veto_logger._dropped_row_count = 0


# ---------------------------------------------------------------------------
# record_veto
# ---------------------------------------------------------------------------


def test_record_veto_appends_to_buffer():
    """record_veto() adds the payload to the pending buffer."""
    assert veto_logger.pending_count() == 0
    p = _payload()
    veto_logger.record_veto(p)
    assert veto_logger.pending_count() == 1


def test_record_veto_multiple_payloads():
    """Multiple record_veto() calls accumulate correctly."""
    for i in range(5):
        veto_logger.record_veto(_payload(symbol=f"SYM{i:03d}"))
    assert veto_logger.pending_count() == 5


def test_record_veto_preserves_ts_tz_aware():
    """Buffered payload ts must remain tz-aware after record_veto."""
    ts = datetime(2026, 5, 4, 9, 30, 0, tzinfo=UTC)
    veto_logger.record_veto(_payload(ts=ts))
    stored = veto_logger._pending_veto_events[0]
    assert stored["ts"].tzinfo is not None, "ts must remain tz-aware in buffer"
    assert stored["ts"].utcoffset().total_seconds() == 0, "ts must be UTC"


# ---------------------------------------------------------------------------
# pending_count / dropped_counts
# ---------------------------------------------------------------------------


def test_pending_count_empty():
    """pending_count() returns 0 on an empty buffer."""
    assert veto_logger.pending_count() == 0


def test_dropped_counts_initial():
    """dropped_counts() returns (0, 0) at process start (after fixture reset)."""
    batches, rows = veto_logger.dropped_counts()
    assert batches == 0
    assert rows == 0


# ---------------------------------------------------------------------------
# flush_llm_veto_events — success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flush_empty_buffer_returns_zero():
    """Flush on empty buffer returns 0 without calling CH client."""
    ch = MagicMock()
    result = await veto_logger.flush_llm_veto_events(ch)
    assert result == 0
    ch.execute.assert_not_called()


@pytest.mark.asyncio
async def test_flush_success_drains_buffer():
    """Successful flush drains the buffer and calls CH execute once."""
    ch = MagicMock()
    veto_logger.record_veto(_payload())
    veto_logger.record_veto(_payload(direction="short", overall_signal="STRONG_BULLISH"))

    result = await veto_logger.flush_llm_veto_events(ch)

    assert result == 2
    assert veto_logger.pending_count() == 0
    ch.execute.assert_called_once()


@pytest.mark.asyncio
async def test_flush_success_no_drop_counters_unchanged():
    """Successful flush does not increment dropped counters."""
    ch = MagicMock()
    veto_logger.record_veto(_payload())

    await veto_logger.flush_llm_veto_events(ch)

    batches, rows = veto_logger.dropped_counts()
    assert batches == 0
    assert rows == 0


@pytest.mark.asyncio
async def test_flush_passes_correct_columns_to_ch():
    """flush_llm_veto_events passes expected column values to CH execute."""
    captured: list = []

    def _fake_execute(query: str, data: list) -> None:
        captured.extend(data)

    ch = MagicMock()
    ch.execute.side_effect = _fake_execute

    ts = _ts()
    veto_logger.record_veto(
        _payload(
            symbol="A05603",
            direction="long",
            regime="BEAR_STRONG",
            overall_signal="STRONG_BEARISH",
            confidence=0.75,
            setup="setup_a_gap_reversion",
            ts=ts,
        )
    )

    await veto_logger.flush_llm_veto_events(ch)

    assert len(captured) == 1
    row = captured[0]
    # Expected tuple layout: (ts, symbol, direction, regime, overall_signal,
    #                          confidence, setup, executed, skip_reason)
    assert row[0] == ts
    assert row[1] == "A05603"
    assert row[2] == "long"
    assert row[3] == "BEAR_STRONG"
    assert row[4] == "STRONG_BEARISH"
    assert abs(row[5] - 0.75) < 1e-9
    assert row[6] == "setup_a_gap_reversion"
    assert row[7] == 0          # executed = 0 (vetoed)
    assert row[8] == "llm_veto"  # skip_reason


# ---------------------------------------------------------------------------
# flush_llm_veto_events — failure / best-effort path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flush_ch_failure_returns_zero():
    """CH insert failure → flush returns 0 (best-effort)."""
    ch = MagicMock()
    ch.execute.side_effect = RuntimeError("CH connection refused")

    veto_logger.record_veto(_payload())
    veto_logger.record_veto(_payload())

    result = await veto_logger.flush_llm_veto_events(ch)

    assert result == 0


@pytest.mark.asyncio
async def test_flush_ch_failure_increments_dropped_counters():
    """CH insert failure increments dropped_batch_count and dropped_row_count."""
    ch = MagicMock()
    ch.execute.side_effect = RuntimeError("CH connection refused")

    n = 3
    for _ in range(n):
        veto_logger.record_veto(_payload())

    await veto_logger.flush_llm_veto_events(ch)

    batches, rows = veto_logger.dropped_counts()
    assert batches == 1
    assert rows == n


@pytest.mark.asyncio
async def test_flush_ch_failure_does_not_re_queue():
    """Failed batch is dropped, not re-queued — buffer is empty after failed flush."""
    ch = MagicMock()
    ch.execute.side_effect = RuntimeError("CH down")

    veto_logger.record_veto(_payload())

    await veto_logger.flush_llm_veto_events(ch)

    # Buffer must be empty (no re-queuing)
    assert veto_logger.pending_count() == 0


# ---------------------------------------------------------------------------
# Bounded deque / maxlen behaviour
# ---------------------------------------------------------------------------


def test_buffer_bounded_by_maxlen():
    """Buffer never grows beyond _MAX_BUFFER_SIZE (oldest rows are displaced)."""
    max_size = veto_logger._MAX_BUFFER_SIZE
    for i in range(max_size + 10):
        veto_logger.record_veto(_payload(symbol=f"SYM{i:05d}"))
    assert veto_logger.pending_count() == max_size


def test_buffer_displacement_preserves_newest_rows():
    """When buffer is full, newest rows are preserved (oldest are displaced)."""
    max_size = veto_logger._MAX_BUFFER_SIZE
    for i in range(max_size + 5):
        veto_logger.record_veto(_payload(symbol=f"SYM{i:05d}"))
    # The buffer should contain the last max_size symbols
    symbols = [e["symbol"] for e in veto_logger._pending_veto_events]
    # First symbol in buffer should be SYM00005 (index 5), not SYM00000
    assert symbols[0] == f"SYM{5:05d}"
    assert symbols[-1] == f"SYM{max_size + 4:05d}"


# ---------------------------------------------------------------------------
# Naive ts handling in _do_insert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flush_naive_ts_is_replaced_with_utc_now():
    """_do_insert replaces naive ts with datetime.now(UTC) rather than crashing."""
    ch = MagicMock()

    captured: list = []

    def _fake_execute(query: str, data: list) -> None:
        captured.extend(data)

    ch.execute.side_effect = _fake_execute

    # Inject a naive ts directly into the buffer (bypasses record_veto guard)
    naive_ts = datetime(2026, 5, 4, 9, 0, 0)  # tz-naive
    veto_logger._pending_veto_events.append(_payload(ts=naive_ts))

    result = await veto_logger.flush_llm_veto_events(ch)

    assert result == 1
    row = captured[0]
    # ts must be a datetime (replaced from naive to tz-aware)
    assert isinstance(row[0], datetime)
