"""LLM Veto Logger

Buffer for LLM veto-authority event payloads (Phase 1.2).  When a Setup A or
Setup C candidate entry signal is blocked by the LLM veto (high confidence in
an opposing overall_signal), the event is recorded here instead of being silently
discarded.  Buffered rows can be flushed to ClickHouse table
``kospi.signals_all`` (with ``executed=0, skip_reason='llm_veto'``) by the
orchestrator or any caller via ``flush_llm_veto_events()``.

Design notes:
    - **Mirrors rl_shadow_logger**: same bounded-deque pattern, same best-effort
      delivery semantics, same ``dropped_counts()`` API for Prometheus alerting.
    - **Non-blocking**: ``record_veto()`` appends to an in-memory deque and
      returns immediately — no I/O on the hot path.
    - **Thread-safe deque**: Python's ``collections.deque`` append/popleft are
      GIL-protected and safe for concurrent producer/consumer access.
    - **Bounded buffer**: ``maxlen=10_000`` prevents unbounded growth if the
      orchestrator flush is delayed.
    - **Counterfactual analysis**: persisted rows let operators compare
      counterfactual PnL of vetoed signals vs. signals that were allowed through
      (Phase 1 paper validation §6 of the LLM-primary RL-minimization plan).
    - **Orchestrator wiring**: ``TradingOrchestrator._shadow_loggers_flush_loop``
      drains this buffer every ``flush_interval_seconds`` (default 60s, see
      ``config/shadow_loggers.yaml``).  A final drain runs in
      ``_shadow_loggers_final_flush`` on shutdown when
      ``final_flush_on_stop: true`` (default).  Each logger's flush is wrapped
      in its own try/except so a failure here does not skip the rl_shadow
      flush on the same tick (and vice versa).
      Tests: ``tests/unit/trading/test_shadow_loggers_flush.py``.

Required payload keys for the ClickHouse flush:
    ``ts``              (datetime, tz-aware UTC)
    ``symbol``          (str)
    ``direction``       (str: "long" | "short")
    ``regime``          (str)
    ``overall_signal``  (str — the opposing overall_signal that triggered veto)
    ``confidence``      (float — LLM context confidence at veto time)
    ``setup``           (str — e.g. "setup_a_gap_reversion")

Example:

    .. code-block:: python

        # In SetupAEntryAdapter.generate() when veto fires:
        from shared.strategy.llm_veto_logger import record_veto
        record_veto(payload)
        return None  # no Signal emitted

        # Direct flush (e.g. tests, ad-hoc operator scripts):
        from shared.strategy.llm_veto_logger import flush_llm_veto_events
        await flush_llm_veto_events(ch_client)
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level pending buffer (bounded to avoid unbounded memory growth)
# ---------------------------------------------------------------------------
_MAX_BUFFER_SIZE: int = 10_000
_pending_veto_events: deque[dict[str, Any]] = deque(maxlen=_MAX_BUFFER_SIZE)

# Counters for batches dropped due to ClickHouse insert failures.  Veto data
# is best-effort by design (see flush_llm_veto_events docstring); these metrics
# let operators detect persistent CH issues without silently losing the
# counterfactual dataset.
_dropped_batch_count: int = 0
_dropped_row_count: int = 0


def record_veto(payload: dict[str, Any]) -> None:
    """Append an LLM veto event payload to the in-memory buffer.

    This function is intentionally non-blocking.  The caller must not await
    any I/O here; the ClickHouse write happens later via
    ``flush_llm_veto_events()``.

    Args:
        payload: Dict containing at minimum ``ts`` (tz-aware UTC datetime),
            ``symbol``, ``direction``, ``regime``, ``overall_signal``,
            ``confidence``, and ``setup``.  Extra keys are preserved and
            forwarded to the ClickHouse flush unchanged.
    """
    _pending_veto_events.append(payload)
    logger.debug(
        "llm_veto: buffered veto symbol=%s direction=%s regime=%s "
        "overall_signal=%s confidence=%.3f setup=%s (buffer_size=%d)",
        payload.get("symbol", ""),
        payload.get("direction", ""),
        payload.get("regime", ""),
        payload.get("overall_signal", ""),
        float(payload.get("confidence", 0.0)),
        payload.get("setup", ""),
        len(_pending_veto_events),
    )


def pending_count() -> int:
    """Return the number of veto events currently waiting to be flushed."""
    return len(_pending_veto_events)


def dropped_counts() -> tuple[int, int]:
    """Return ``(dropped_batches, dropped_rows)`` since process start.

    Operators / Prometheus exporters use these to detect persistent ClickHouse
    insert failures.  Non-zero values mean veto events were lost; zero on a
    long-running process means flush has been reliable.
    """
    return _dropped_batch_count, _dropped_row_count


async def flush_llm_veto_events(ch_client: Any) -> int:
    """Drain the buffer and insert rows into ``kospi.signals_all``.

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

    Re-queueing the failed batch (via ``appendleft``) was rejected for the
    same reason as in ``rl_shadow_logger``: the bounded deque means concurrent
    producer rows arriving during the failed insert window would be displaced
    — silently corrupting the counterfactual dataset.  Use
    :func:`dropped_counts` (and Prometheus alerting on a non-zero rate) to
    catch persistent CH issues.
    """
    import asyncio

    global _dropped_batch_count, _dropped_row_count

    if not _pending_veto_events:
        return 0

    # Drain current buffer (popleft is GIL-protected; concurrent producers may
    # append during this loop and will be picked up on the next flush call).
    rows: list[dict[str, Any]] = []
    while _pending_veto_events:
        rows.append(_pending_veto_events.popleft())

    if not rows:
        return 0

    try:
        await asyncio.to_thread(_do_insert, ch_client, rows)
        logger.info("llm_veto: flushed %d rows to kospi.signals_all", len(rows))
        return len(rows)
    except Exception as exc:
        # Best-effort: drop the batch + record the loss.  Re-queueing would
        # corrupt newer producer rows under bounded-deque semantics (see
        # docstring).  Operators detect persistent issues via dropped_counts().
        _dropped_batch_count += 1
        _dropped_row_count += len(rows)
        logger.error(
            "llm_veto: flush failed (%s); dropping batch of %d rows "
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

    Inserts vetoed-signal rows into ``kospi.signals_all`` with
    ``executed=0`` and ``skip_reason='llm_veto'`` so counterfactual analysis
    can compare PnL of blocked vs. unblocked signals.

    Args:
        ch_client: ClickHouse client with an ``execute(query, data)`` method.
        rows: List of payload dicts to insert.
    """
    data: list[tuple[Any, ...]] = []
    for row in rows:
        ts = row.get("ts")
        if not isinstance(ts, datetime):
            ts = datetime.now(UTC)

        data.append(
            (
                ts,
                str(row.get("symbol", "")),
                str(row.get("direction", "")),
                str(row.get("regime", "")),
                str(row.get("overall_signal", "")),
                float(row.get("confidence", 0.0)),
                str(row.get("setup", "")),
                0,           # executed = 0 (vetoed)
                "llm_veto",  # skip_reason
            )
        )

    query = """
        INSERT INTO kospi.signals_all (
            ts, symbol, direction, regime, overall_signal,
            confidence, setup, executed, skip_reason
        ) VALUES
    """
    ch_client.execute(query, data)
