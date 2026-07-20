"""Deterministic replay primitives shared across replay/backtest harnesses.

Pure, dependency-light mechanisms for deterministic historical replay of bar
data: timezone normalization to KST, trading-session segmentation, and
prior-session close lookup. These primitives are the mechanical core reused by
higher-level context assembly (which stays in the backtest package because it
depends on heavier data models).

The module depends only on stdlib plus ``pandas`` (an approved commons
dependency). It carries no dependency on execution, storage, streaming, LLM, or
backtest orchestration packages, and has no import side effects beyond loading
``pandas``, so it is safe to reuse from any deterministic harness.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

#: Korea Standard Time — the native timezone of KRX trading sessions.
KST = ZoneInfo("Asia/Seoul")

#: Default number of leading bars reserved for indicator warmup (ATR/VWAP).
DEFAULT_WARMUP_BARS: int = 60


def ensure_kst(ts: pd.Timestamp) -> pd.Timestamp:
    """Return ``ts`` as a KST-aware timestamp.

    Naive timestamps are localized to KST; already-aware timestamps are
    converted to KST.

    Args:
        ts: A pandas Timestamp, tz-aware or naive.

    Returns:
        The timestamp expressed in the ``Asia/Seoul`` timezone.
    """
    if ts.tzinfo is None:
        return ts.tz_localize(KST)
    return ts.tz_convert(KST)


def session_date(ts: pd.Timestamp) -> date:
    """Return the trading-session date (KST calendar date) of ``ts``.

    Args:
        ts: A KST-aware (or naive-KST) timestamp.

    Returns:
        The calendar date of the bar in KST.
    """
    return ts.date()


@dataclass(frozen=True)
class SessionIndex:
    """Deterministic per-bar trading-session segmentation.

    Both lists are aligned bar-for-bar with the timestamp sequence they were
    built from.

    Attributes:
        session_dates: Session (KST calendar) date for each bar, in order.
        session_start_idx: Index of the first bar of the session each bar
            belongs to.
    """

    session_dates: list[date]
    session_start_idx: list[int]

    def __len__(self) -> int:
        """Return the number of indexed bars."""
        return len(self.session_dates)


def build_session_index(timestamps: Sequence[Any]) -> SessionIndex:
    """Segment an ordered timestamp sequence into trading sessions.

    Walks ``timestamps`` in order, normalizing each to KST, and records the
    session date plus the index at which the current session began. The result
    is fully deterministic in the input order — a new session starts whenever
    the KST calendar date changes.

    Args:
        timestamps: Ordered raw timestamps (anything ``pd.Timestamp`` accepts).

    Returns:
        A :class:`SessionIndex` aligned bar-for-bar with ``timestamps``.
    """
    session_dates: list[date] = []
    session_start_idx: list[int] = []
    current_date: date | None = None
    current_start: int = 0
    for i, ts_raw in enumerate(timestamps):
        ts_kst = ensure_kst(pd.Timestamp(ts_raw))
        d = session_date(ts_kst)
        if d != current_date:
            current_date = d
            current_start = i
        session_dates.append(d)
        session_start_idx.append(current_start)
    return SessionIndex(
        session_dates=session_dates,
        session_start_idx=session_start_idx,
    )


def build_prev_session_close(
    session_dates: Sequence[date],
    closes: Sequence[float],
) -> dict[date, float]:
    """Map each session date to the last close of the previous session.

    Args:
        session_dates: Per-bar session dates (see :func:`build_session_index`),
            expected to be contiguous per session.
        closes: Per-bar close prices, aligned with ``session_dates``.

    Returns:
        A dict from session date to the previous session's final close. The
        first session is absent from the mapping (it has no prior session).
    """
    date_to_last_close: dict[date, float] = {}
    last_d: date | None = None
    last_close: float | None = None
    for d, close in zip(session_dates, closes):
        if last_d is not None and d != last_d:
            date_to_last_close[d] = last_close  # type: ignore[assignment]
        last_d = d
        last_close = close
    return date_to_last_close
