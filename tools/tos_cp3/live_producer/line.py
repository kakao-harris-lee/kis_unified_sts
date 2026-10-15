"""The pure half of ③: a frozen frame in, at most one journal row out.

Split out of :mod:`~tools.tos_cp3.live_producer.producer` with
:mod:`~tools.tos_cp3.live_producer.halt_policy` and
:mod:`~tools.tos_cp3.live_producer.seed_lineage` (PR #904 review round 1 item
A.5): that module sits at ``config/tos_size_budget.yaml``'s 1,000-line cap and
the right answer to "no room left" is a seam, not shorter lines.

The seam is one that module's own first line already named — "the pure
``build_line`` and the thin outer loop around it". This is the pure half: it
reads no clock, opens no socket and touches no file, so the only thing a
caller can change about its answer is the frame it hands in. The identity the
row carries lives here too, because this function is the only writer of it
into a row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from tools.tos_cp3 import TOS_CP3_VERSION
from tools.tos_cp3.produce_fields import OpenAnchor, StrategyInputs, produce_bars

#: The allowlist prefix added to ``bootproof_guard`` in PR-2, and the full
#: ``source_id`` every line carries. The delimiter rule there means the prefix
#: matches ``tos-cp3-live`` exactly or ``tos-cp3-live/`` + anything.
SOURCE_PREFIX = "tos-cp3-live"
SOURCE_ID = f"{SOURCE_PREFIX}/{TOS_CP3_VERSION}"


@dataclass(frozen=True)
class LineOutcome:
    """One attempt at a journal row: the row, or the reason there is none."""

    row: dict[str, Any] | None = None
    reason: str | None = None
    raw_event_id: str | None = None


def build_line(
    frame: Any,
    *,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: Any,
    anchor: OpenAnchor,
    bar_minute: datetime,
    received_ms: int,
) -> LineOutcome:
    """The pure half: a frozen frame in, at most one journal row out.

    ``raw_event_id`` and the fifteen ``FIELD_ORDER`` values come from B1a's own
    ``produce_bars``, so the same bar's real-time and offline lines join in B3.
    Two keys differ from B1a here (plan §1): ``source_id`` names this producer
    and ``received_ms`` records when the REST response arrived.

    **The row carries no ``as_of_ms``** (review B1). This function runs
    ``produce_bars`` — measured at ~0.44 s late in a session — so a stamp taken
    here would already have spent more than the tenant's whole 800 ms budget by
    the time the line is written. :meth:`~tools.tos_cp3.live_producer.sinks
    .ObservationJournal.append` takes it immediately before the replace, and
    refuses a row that arrives with one.

    A last record that is not *bar_minute* is not a defect: ``produce_bars``
    omits a bar whose ATR/VWAP inputs cannot carry their published meaning, and
    B1a omits the same bar, so B3 does not diverge (plan §3.1). It is reported
    as ``omitted_unusable``.
    """
    import pandas as pd

    produced = produce_bars(
        frame,
        symbol=symbol,
        strategy=strategy,
        contract_spec=contract_spec,
        anchor=anchor,
    )
    last = produced.records[-1]
    # ``MarketContextReplay`` yields KST-AWARE stamps while the frozen frame and
    # ``parse_ohlcv`` carry naive KST wall time. Compared as-is, an aware and a
    # naive Timestamp for the same minute are never equal, so every line would
    # read as ``omitted_unusable`` and the producer would publish nothing at
    # all. Dropped the same way B1a's own ``_bar_lookup`` drops it.
    if pd.Timestamp(last.bar_kst).tz_localize(None) != pd.Timestamp(bar_minute):
        return LineOutcome(reason="omitted_unusable", raw_event_id=last.raw_event_id)
    return LineOutcome(
        row={
            "raw_event_id": last.raw_event_id,
            "source_id": SOURCE_ID,
            "instrument": last.instrument,
            "received_ms": received_ms,
            "fields": last.fields,
        },
        raw_event_id=last.raw_event_id,
    )
