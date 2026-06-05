"""LLM Veto Logger

Buffer for LLM veto-authority event payloads.  When a Setup A or Setup C
candidate entry signal is blocked by the LLM veto, the event is recorded here
instead of being silently discarded.  The historical external flush target was
removed with the Parquet/RuntimeLedger storage migration; flush now drains the
bounded buffer without external I/O until a replacement archive is added.

Design notes:
    - **Best-effort delivery**: bounded-deque buffering with a
      ``dropped_counts()`` API for Prometheus alerting.
    - **Non-blocking**: ``record_veto()`` appends to an in-memory deque and
      returns immediately — no I/O on the hot path.
    - **Thread-safe deque**: Python's ``collections.deque`` append/popleft are
      GIL-protected and safe for concurrent producer/consumer access.
    - **Bounded buffer**: ``maxlen=10_000`` prevents unbounded growth if the
      orchestrator flush is delayed.
    - **Orchestrator wiring**: ``TradingOrchestrator._shadow_loggers_flush_loop``
      drains this buffer every ``flush_interval_seconds`` (default 60s, see
      ``config/shadow_loggers.yaml``).  A final drain runs in
      ``_shadow_loggers_final_flush`` on shutdown when
      ``final_flush_on_stop: true`` (default).

Required payload keys:
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
        await flush_llm_veto_events()
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level pending buffer (bounded to avoid unbounded memory growth)
# ---------------------------------------------------------------------------
_MAX_BUFFER_SIZE: int = 10_000
_pending_veto_events: deque[dict[str, Any]] = deque(maxlen=_MAX_BUFFER_SIZE)

# Counters for batches drained without a durable archive. Veto data is
# best-effort by design until a Parquet/RuntimeLedger archive is introduced.
_dropped_batch_count: int = 0
_dropped_row_count: int = 0


def record_veto(payload: dict[str, Any]) -> None:
    """Append an LLM veto event payload to the in-memory buffer.

    This function is intentionally non-blocking.  The caller must not await
    any I/O here; flushing happens later via ``flush_llm_veto_events()``.

    Args:
        payload: Dict containing at minimum ``ts`` (tz-aware UTC datetime),
            ``symbol``, ``direction``, ``regime``, ``overall_signal``,
            ``confidence``, and ``setup``.  Extra keys are preserved and
            forwarded to the archive flush unchanged.
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

    Operators / Prometheus exporters use these to detect that veto events were
    drained before a durable replacement archive exists.
    """
    return _dropped_batch_count, _dropped_row_count


async def flush_llm_veto_events(_storage_client: Any | None = None) -> int:
    """Drain the buffer without external I/O.

    Returns:
        Number of durable rows written. This is always 0 until the logger gets a
        Parquet or RuntimeLedger archive target.
    """
    global _dropped_batch_count, _dropped_row_count
    _ = _storage_client

    if not _pending_veto_events:
        return 0

    # Drain current buffer (popleft is GIL-protected; concurrent producers may
    # append during this loop and will be picked up on the next flush call).
    rows: list[dict[str, Any]] = []
    while _pending_veto_events:
        rows.append(_pending_veto_events.popleft())

    if not rows:
        return 0

    _dropped_batch_count += 1
    _dropped_row_count += len(rows)
    logger.info(
        "llm_veto: drained %d rows without durable archive "
        "(total drained batches=%d rows=%d)",
        len(rows),
        _dropped_batch_count,
        _dropped_row_count,
    )
    return 0
