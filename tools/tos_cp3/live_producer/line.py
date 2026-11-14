"""The pure half of ③: a frozen frame in, at most one journal row out."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from tools.tos_cp3 import TOS_CP3_VERSION
from tools.tos_cp3.produce_fields import OpenAnchor, StrategyInputs, produce_bars

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
    """The pure half: a frozen frame in, at most one journal row out."""
    import pandas as pd

    produced = produce_bars(
        frame,
        symbol=symbol,
        strategy=strategy,
        contract_spec=contract_spec,
        anchor=anchor,
    )
    last = produced.records[-1]
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
