"""RL Shadow Mode Logger

Buffer for RL shadow-mode prediction payloads.  When ``RLMPPOEntry`` runs in
``shadow_mode=True`` the inference result is recorded here instead of emitting
a live Signal.  Buffered rows are flushed to ClickHouse table
``kospi.rl_shadow_predictions`` by the orchestrator (or any caller) via
``flush_rl_shadow_predictions()``.

Design notes:
    - **Non-blocking**: ``record_shadow_prediction()`` appends to an in-memory
      deque and returns immediately.  The ClickHouse write happens only on an
      explicit ``flush_rl_shadow_predictions()`` call.
    - **Thread-safe deque**: Python's ``collections.deque`` append/popleft are
      GIL-protected and safe for concurrent producer/consumer access without
      an explicit lock.
    - **Bounded buffer**: ``maxlen=10_000`` prevents unbounded growth if the
      orchestrator flush is delayed.
    - **Orchestrator wiring**: ``TradingOrchestrator._shadow_loggers_flush_loop``
      drains this buffer every ``flush_interval_seconds`` (default 60s, see
      ``config/shadow_loggers.yaml``).  A final drain runs in
      ``_shadow_loggers_final_flush`` on shutdown when
      ``final_flush_on_stop: true`` (default).  Each logger's flush is wrapped
      in its own try/except so a failure in one does not skip the other.
      Tests: ``tests/unit/trading/test_shadow_loggers_flush.py``.

Example:

    .. code-block:: python

        # In RLMPPOEntry.generate() when shadow_mode=True:
        from shared.strategy.rl_shadow_logger import record_shadow_prediction
        record_shadow_prediction(payload)
        return None  # no Signal emitted

        # Direct flush (e.g. tests, ad-hoc operator scripts):
        from shared.strategy.rl_shadow_logger import flush_rl_shadow_predictions
        await flush_rl_shadow_predictions(ch_client)
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level pending buffer (bounded to avoid unbounded memory growth)
# ---------------------------------------------------------------------------
_MAX_BUFFER_SIZE: int = 10_000
_pending_shadow_predictions: deque[dict[str, Any]] = deque(maxlen=_MAX_BUFFER_SIZE)

# Counters for batches dropped due to ClickHouse insert failures. Shadow data
# is best-effort by design (see flush_rl_shadow_predictions docstring); these
# metrics let operators detect persistent CH issues without silently corrupting
# the counterfactual dataset.
_dropped_batch_count: int = 0
_dropped_row_count: int = 0


def record_shadow_prediction(payload: dict[str, Any]) -> None:
    """Append a shadow-mode prediction payload to the in-memory buffer.

    This function is intentionally non-blocking.  The caller (``RLMPPOEntry``)
    must not await any I/O here; the ClickHouse write happens later via
    ``flush_rl_shadow_predictions()``.

    Args:
        payload: Dict containing at minimum ``ts``, ``symbol``, ``action``,
            ``confidence``, ``action_probs``, ``regime``, ``risk_mode``,
            ``risk_score``, ``action_masks``, ``executed_setup_id``.
            Extra keys are silently ignored during flush.
    """
    _pending_shadow_predictions.append(payload)
    logger.debug(
        "rl_shadow: buffered prediction symbol=%s action=%s confidence=%.3f "
        "(buffer_size=%d)",
        payload.get("symbol", ""),
        payload.get("action"),
        payload.get("confidence", 0.0),
        len(_pending_shadow_predictions),
    )


def pending_count() -> int:
    """Return the number of predictions currently waiting to be flushed."""
    return len(_pending_shadow_predictions)


def dropped_counts() -> tuple[int, int]:
    """Return ``(dropped_batches, dropped_rows)`` since process start.

    Operators / Prometheus exporters use these to detect persistent ClickHouse
    insert failures.  Non-zero values mean shadow predictions were lost; zero
    on a long-running process means flush has been reliable.
    """
    return _dropped_batch_count, _dropped_row_count


async def flush_rl_shadow_predictions(ch_client: Any) -> int:
    """Drain the buffer and insert rows into ``kospi.rl_shadow_predictions``.

    This is an **async** function so it can be awaited inside the
    ``TradingOrchestrator`` event loop without blocking the trading cycle.
    The underlying ClickHouse client call is run synchronously inside an
    ``asyncio.to_thread`` wrapper to keep the event loop non-blocking.

    Args:
        ch_client: A ClickHouse client instance (e.g. ``shared.db.client``
            wrapping ``clickhouse_driver.Client``).  Must expose an
            ``execute(query, data)`` method.

    Returns:
        Number of rows flushed (0 if buffer was empty or insert failed).

    Delivery semantics: **best-effort**.  If the ClickHouse insert raises, the
    drained batch is dropped and ``_dropped_batch_count`` /
    ``_dropped_row_count`` are incremented (read via :func:`dropped_counts`).

    Re-queueing the failed batch (via ``appendleft``) was rejected because the
    buffer is bounded by ``maxlen=10_000``.  During the ``asyncio.to_thread``
    insert window, concurrent producers append new rows to the deque.  On
    failure, ``appendleft``-ing 10_000 old rows would push those newly-arrived
    rows off the right end of the bounded deque — silently corrupting the
    counterfactual dataset.  Shadow data is for offline analysis where
    occasional batch loss is acceptable provided it is **observable**.  Use
    :func:`dropped_counts` (and Prometheus alerting on a non-zero rate) to
    catch persistent CH issues.
    """
    import asyncio

    global _dropped_batch_count, _dropped_row_count

    if not _pending_shadow_predictions:
        return 0

    # Drain current buffer (popleft is GIL-protected; concurrent producers may
    # append during this loop and will be picked up on the next flush call).
    rows: list[dict[str, Any]] = []
    while _pending_shadow_predictions:
        rows.append(_pending_shadow_predictions.popleft())

    if not rows:
        return 0

    try:
        await asyncio.to_thread(_do_insert, ch_client, rows)
        logger.info("rl_shadow: flushed %d rows to kospi.rl_shadow_predictions", len(rows))
        return len(rows)
    except Exception as exc:
        # Best-effort: drop the batch + record the loss.  Re-queueing would
        # corrupt newer producer rows under bounded-deque semantics (see
        # docstring).  Operators detect persistent issues via dropped_counts().
        _dropped_batch_count += 1
        _dropped_row_count += len(rows)
        logger.error(
            "rl_shadow: flush failed (%s); dropping batch of %d rows "
            "(total dropped batches=%d rows=%d)",
            exc,
            len(rows),
            _dropped_batch_count,
            _dropped_row_count,
            exc_info=True,
        )
        return 0


def _do_insert(ch_client: Any, rows: list[dict[str, Any]]) -> None:
    """Synchronous ClickHouse insert (runs inside asyncio.to_thread).

    Args:
        ch_client: ClickHouse client with an ``execute(query, data)`` method.
        rows: List of payload dicts to insert.
    """
    data: list[tuple[Any, ...]] = []
    for row in rows:
        ts = row.get("ts")
        # Ensure ts is a datetime (tz-aware UTC preferred by ClickHouse DateTime64)
        if not isinstance(ts, datetime):
            from datetime import UTC

            ts = datetime.now(UTC)

        action_probs: dict[str, float] = {
            str(k): float(v) for k, v in (row.get("action_probs") or {}).items()
        }
        action_masks_raw = row.get("action_masks") or []
        action_masks: list[int] = [int(bool(m)) for m in action_masks_raw]

        data.append(
            (
                ts,
                str(row.get("symbol", "")),
                int(row.get("action", 0)),
                float(row.get("confidence", 0.0)),
                action_probs,
                str(row.get("regime", "")),
                str(row.get("risk_mode", "")),
                float(row.get("risk_score", 0.0)),
                action_masks,
                str(row.get("executed_setup_id", "")),
            )
        )

    query = """
        INSERT INTO kospi.rl_shadow_predictions (
            ts, symbol, action, confidence,
            action_probs, regime, risk_mode, risk_score,
            action_masks, executed_setup_id
        ) VALUES
    """
    ch_client.execute(query, data)
