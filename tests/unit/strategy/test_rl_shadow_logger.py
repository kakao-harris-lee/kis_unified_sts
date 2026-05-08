"""Unit tests for shared/strategy/rl_shadow_logger.py.

Mirrors the structure of ``test_llm_veto_logger.py`` since both loggers
share the same bounded-deque + best-effort-flush pattern.

Test coverage
-------------
1. ``record_shadow_prediction()`` appends to the buffer.
2. ``pending_count()`` reflects current buffer length.
3. ``flush_rl_shadow_predictions()`` drains the buffer and calls the CH client.
4. Flush with empty buffer returns 0 without calling CH.
5. CH insert failure → batch dropped, ``dropped_counts()`` incremented,
   flush returns 0 (best-effort semantics).
6. Insert tuple shape matches the V5 schema column order.
7. ``ts`` is coerced to a tz-aware UTC datetime when missing/invalid.
8. ``action_probs`` keys are stringified, values floated.
9. ``action_masks`` are coerced to ints (0/1).
10. ``maxlen`` bound prevents unbounded growth.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

import shared.strategy.rl_shadow_logger as shadow_logger

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# V5 schema column order — keep in sync with infra/clickhouse/migrations/V5__rl_shadow_predictions.sql
_V5_COLS: tuple[str, ...] = (
    "ts",
    "symbol",
    "action",
    "confidence",
    "action_probs",
    "regime",
    "risk_mode",
    "risk_score",
    "action_masks",
    "executed_setup_id",
)


def _ts() -> datetime:
    return datetime(2026, 5, 8, 1, 0, 0, tzinfo=UTC)


def _payload(
    *,
    ts: datetime | None = None,
    symbol: str = "A05603",
    action: int = 0,
    confidence: float = 0.75,
    action_probs: dict | None = None,
    regime: str = "BULL",
    risk_mode: str = "NEUTRAL",
    risk_score: float = 0.2,
    action_masks: list | None = None,
    executed_setup_id: str = "",
) -> dict:
    return {
        "ts": ts if ts is not None else _ts(),
        "symbol": symbol,
        "action": action,
        "confidence": confidence,
        "action_probs": action_probs or {0: 0.6, 1: 0.1, 2: 0.1, 3: 0.1, 4: 0.1},
        "regime": regime,
        "risk_mode": risk_mode,
        "risk_score": risk_score,
        "action_masks": action_masks or [1, 1, 1, 1, 1],
        "executed_setup_id": executed_setup_id,
    }


@pytest.fixture(autouse=True)
def _reset_logger():
    shadow_logger._pending_shadow_predictions.clear()
    shadow_logger._dropped_batch_count = 0
    shadow_logger._dropped_row_count = 0
    yield
    shadow_logger._pending_shadow_predictions.clear()
    shadow_logger._dropped_batch_count = 0
    shadow_logger._dropped_row_count = 0


# ---------------------------------------------------------------------------
# record_shadow_prediction / pending_count
# ---------------------------------------------------------------------------


def test_record_appends_to_buffer():
    assert shadow_logger.pending_count() == 0
    shadow_logger.record_shadow_prediction(_payload())
    assert shadow_logger.pending_count() == 1


def test_pending_count_tracks_multiple_records():
    for _ in range(5):
        shadow_logger.record_shadow_prediction(_payload())
    assert shadow_logger.pending_count() == 5


# ---------------------------------------------------------------------------
# flush — happy path
# ---------------------------------------------------------------------------


def test_flush_empty_buffer_returns_zero():
    ch = MagicMock()
    n = asyncio.run(shadow_logger.flush_rl_shadow_predictions(ch))
    assert n == 0
    ch.execute.assert_not_called()


def test_flush_drains_buffer_and_calls_ch():
    ch = MagicMock()
    shadow_logger.record_shadow_prediction(_payload(symbol="A05603"))
    shadow_logger.record_shadow_prediction(_payload(symbol="101S6000"))

    n = asyncio.run(shadow_logger.flush_rl_shadow_predictions(ch))

    assert n == 2
    assert shadow_logger.pending_count() == 0
    ch.execute.assert_called_once()
    # Inspect the data tuple passed
    call_args = ch.execute.call_args
    query, data = call_args.args[0], call_args.args[1]
    assert "INSERT INTO kospi.rl_shadow_predictions" in query
    assert isinstance(data, list)
    assert len(data) == 2


# ---------------------------------------------------------------------------
# Schema mapping — verify tuple shape matches V5 columns
# ---------------------------------------------------------------------------


def test_insert_tuple_matches_v5_column_count():
    """The insert tuple length must match the V5 schema column count.

    Regression: if a future column is added to V5 but not to ``_do_insert``,
    ClickHouse rejects the batch silently → all shadow data lost.
    """
    ch = MagicMock()
    shadow_logger.record_shadow_prediction(_payload())
    asyncio.run(shadow_logger.flush_rl_shadow_predictions(ch))

    data = ch.execute.call_args.args[1]
    assert len(data) == 1
    row_tuple = data[0]
    assert len(row_tuple) == len(_V5_COLS), (
        f"Insert tuple has {len(row_tuple)} fields, "
        f"V5 schema has {len(_V5_COLS)} columns: {_V5_COLS}"
    )


def test_insert_column_order_matches_v5():
    """Verify positional argument types match V5 column types."""
    ch = MagicMock()
    shadow_logger.record_shadow_prediction(
        _payload(
            ts=_ts(),
            symbol="A05603",
            action=2,
            confidence=0.83,
            regime="BEAR",
            risk_mode="DEFENSIVE",
            risk_score=0.91,
            executed_setup_id="setup_a_2026_05_08_001",
        )
    )
    asyncio.run(shadow_logger.flush_rl_shadow_predictions(ch))

    row = ch.execute.call_args.args[1][0]
    # Positional unpacking — order MUST match V5 schema:
    ts, symbol, action, confidence, action_probs, regime, risk_mode, risk_score, action_masks, executed_setup_id = row

    assert ts == _ts()
    assert symbol == "A05603"
    assert action == 2
    assert confidence == pytest.approx(0.83)
    assert isinstance(action_probs, dict)
    assert regime == "BEAR"
    assert risk_mode == "DEFENSIVE"
    assert risk_score == pytest.approx(0.91)
    assert isinstance(action_masks, list)
    assert executed_setup_id == "setup_a_2026_05_08_001"


# ---------------------------------------------------------------------------
# Coercion — ts / probs / masks
# ---------------------------------------------------------------------------


def test_missing_ts_falls_back_to_now_utc():
    """When ts is missing or not a datetime, _do_insert falls back to now(UTC)."""
    ch = MagicMock()
    payload = _payload()
    del payload["ts"]
    shadow_logger.record_shadow_prediction(payload)

    before = datetime.now(UTC)
    asyncio.run(shadow_logger.flush_rl_shadow_predictions(ch))
    after = datetime.now(UTC)

    inserted_ts = ch.execute.call_args.args[1][0][0]
    assert isinstance(inserted_ts, datetime)
    assert inserted_ts.tzinfo is UTC
    assert before <= inserted_ts <= after


def test_action_probs_keys_stringified():
    """V5 schema is Map(String, Float32) — int keys must be coerced to str."""
    ch = MagicMock()
    shadow_logger.record_shadow_prediction(
        _payload(action_probs={0: 0.5, 1: 0.3, 2: 0.2})
    )
    asyncio.run(shadow_logger.flush_rl_shadow_predictions(ch))

    inserted_probs = ch.execute.call_args.args[1][0][4]
    assert isinstance(inserted_probs, dict)
    assert all(isinstance(k, str) for k in inserted_probs)
    assert all(isinstance(v, float) for v in inserted_probs.values())
    assert inserted_probs == {"0": 0.5, "1": 0.3, "2": 0.2}


def test_action_masks_coerced_to_ints():
    """V5 schema is Array(UInt8) — bools/numpy must be coerced to plain int."""
    ch = MagicMock()
    shadow_logger.record_shadow_prediction(
        _payload(action_masks=[True, False, True, True, False])
    )
    asyncio.run(shadow_logger.flush_rl_shadow_predictions(ch))

    inserted_masks = ch.execute.call_args.args[1][0][8]
    assert inserted_masks == [1, 0, 1, 1, 0]
    assert all(isinstance(m, int) and not isinstance(m, bool) for m in inserted_masks)


# ---------------------------------------------------------------------------
# Best-effort failure semantics
# ---------------------------------------------------------------------------


def test_flush_failure_drops_batch_and_increments_counters():
    """If CH insert raises, the drained batch is dropped — not re-queued.

    Re-queueing would corrupt newer producer rows under bounded-deque
    semantics (see flush_rl_shadow_predictions docstring).
    """
    ch = MagicMock()
    ch.execute.side_effect = RuntimeError("ClickHouse down")
    shadow_logger.record_shadow_prediction(_payload())
    shadow_logger.record_shadow_prediction(_payload())

    n = asyncio.run(shadow_logger.flush_rl_shadow_predictions(ch))

    assert n == 0
    assert shadow_logger.pending_count() == 0  # drained, not re-queued
    batches, rows = shadow_logger.dropped_counts()
    assert batches == 1
    assert rows == 2


def test_dropped_counts_accumulate_across_failures():
    ch = MagicMock()
    ch.execute.side_effect = RuntimeError("CH down")

    for batch_size in (3, 5, 1):
        for _ in range(batch_size):
            shadow_logger.record_shadow_prediction(_payload())
        asyncio.run(shadow_logger.flush_rl_shadow_predictions(ch))

    batches, rows = shadow_logger.dropped_counts()
    assert batches == 3
    assert rows == 9  # 3 + 5 + 1


# ---------------------------------------------------------------------------
# Bounded buffer
# ---------------------------------------------------------------------------


def test_buffer_is_bounded_at_maxlen():
    """deque(maxlen=10_000) enforces an upper bound — older rows are dropped."""
    cap = shadow_logger._MAX_BUFFER_SIZE
    for i in range(cap + 50):
        shadow_logger.record_shadow_prediction(_payload(symbol=f"S{i:05d}"))
    assert shadow_logger.pending_count() == cap
