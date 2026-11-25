"""The bar the evaluator consumes, and the three window values defined elsewhere.

``session.vwap_typical``, ``atr`` and ``session.minutes_since_open`` are NOT new
definitions. They are the three values ``MarketContextReplay`` hands the legacy
Setup D on every bar (``shared/backtest/market_context_replay.py`` — the B3
witness, byte-frozen), and the declarative producer has to agree with them to the
last float bit (P2-b compares bar × field byte-identically).

Why they are implemented here rather than imported
--------------------------------------------------
``shared/indicators/`` is one of the six pure-commons packages ``tos`` may
import; ``shared.backtest`` is on the firewall's forbidden list
(``.importlinter``, design §2.3), so this module cannot import the witness. What
it does instead, per value:

* ``atr`` — the witness delegates to the indicator engine's ``atr_partial``
  (``shared.indicators.engine.backtest_backend``), which IS in the pure set. But
  that backend is a whole-window function (``atr[i] = tr[max(0, i-p+1):i+1].mean()``
  over a precomputed frame) and this evaluator is a bar-by-bar stream, so calling
  it per bar would be quadratic in Python. :class:`AtrWindow` is the same
  recurrence held incrementally: a ``deque(maxlen=period)`` of true ranges holds
  exactly ``tr[max(0, i-period+1) : i+1]`` after bar ``i``, and the mean is taken
  with numpy over that same contiguous ordering. Bit-equality with the engine op
  — and so with the witness — is PINNED by
  ``tests/unit/indicators/fields/test_replay_parity.py``.
* ``session.vwap_typical`` — the witness computes it inline inside
  ``iter_contexts``; there is no helper to call, and extracting one would edit a
  byte-frozen file. :class:`SessionVwapTypical` repeats the same operation
  sequence (full-session slice, elementwise typical price, ``.sum()`` of the
  whole slice — NOT a running accumulator, which would round differently) and
  the same ``total_volume <= 0 -> close`` fallback, pinned by the same test.
* ``session.minutes_since_open`` — the witness's value comes from
  ``MarketContext.minutes_since_open`` in ``shared.decision``, which is not in
  the pure set either. The expression is repeated verbatim and pinned by the same
  test.

The session boundary itself IS reused: ``shared.determinism.replay.session_date``
(a ratified commons package) is the witness's own session predicate.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from shared.determinism.replay import KST, ensure_kst, session_date
from shared.indicators.fields.errors import FieldEvalError


@dataclass(frozen=True)
class FieldBar:
    """One minute bar, timestamped in KST.

    Attributes:
        ts_kst: Bar LABEL timestamp, tz-aware KST. The label, not label+60s —
            the session fields are computed on the label
            (``tools/tos_cp3/produce_fields.py::derive_as_of_ms``).
        open: Bar open.
        high: Bar high.
        low: Bar low.
        close: Bar close.
        volume: Bar volume.
    """

    ts_kst: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def create(
        cls,
        timestamp: Any,
        *,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> FieldBar:
        """Build a bar, normalizing *timestamp* to KST.

        A naive timestamp is treated as KST and an aware one is converted, which
        is :func:`shared.determinism.replay.ensure_kst` — the same normalization
        the witness applies to every replayed bar.
        """
        ts = ensure_kst(pd.Timestamp(timestamp)).to_pydatetime()
        values = {"open": open, "high": high, "low": low, "close": close}
        for name, value in (*values.items(), ("volume", volume)):
            if not np.isfinite(value):
                raise FieldEvalError(
                    f"{ts.isoformat()}: non-finite bar {name}={value!r} — the "
                    "input bar stream is corrupt"
                )
        return cls(
            ts_kst=ts,
            open=float(open),
            high=float(high),
            low=float(low),
            close=float(close),
            volume=float(volume),
        )

    @property
    def session(self) -> date:
        """The bar's trading-session date (KST calendar date)."""
        return session_date(pd.Timestamp(self.ts_kst))

    @property
    def session_token(self) -> str:
        """Opaque session identifier: the session date, ISO-8601.

        Futures is day-only and the stock tenants are single-session too, so the
        KST date IS the session — the same token
        ``tools/tos_cp3/produce_fields.py`` publishes.
        """
        return self.session.isoformat()


def minutes_since_open(bar: FieldBar, *, open_hour: int, open_minute: int) -> float:
    """Elapsed minutes from the configured KST session open to *bar*.

    Verbatim ``shared/decision/context.py::MarketContext.minutes_since_open``
    (over ``market_open_time()``): the open anchor is taken on the bar's OWN
    calendar date, so a bar before the open yields a negative value rather than
    wrapping to the previous day.

    Args:
        bar: The bar being evaluated.
        open_hour: Configured regular-session open hour, KST.
        open_minute: Configured regular-session open minute, KST.
    """
    open_at = datetime(
        bar.ts_kst.year,
        bar.ts_kst.month,
        bar.ts_kst.day,
        open_hour,
        open_minute,
        tzinfo=KST,
    )
    return (bar.ts_kst - open_at).total_seconds() / 60


class SessionVwapTypical:
    """Session typical-price VWAP, reset on the KST date boundary.

    ``sum(((h+l+c)/3) * v) / sum(v)`` over the session's bars up to and including
    the current one — the witness's ``iter_contexts`` VWAP. The sums are taken
    over the WHOLE session slice on every bar (numpy pairwise summation), not
    carried in a running accumulator: a sequential accumulator rounds
    differently, and this value has to match byte for byte.
    """

    def __init__(self) -> None:
        self._session: date | None = None
        self._high: list[float] = []
        self._low: list[float] = []
        self._close: list[float] = []
        self._volume: list[float] = []

    def update(self, bar: FieldBar) -> float:
        """Append *bar* to the current session and return the VWAP through it."""
        session = bar.session
        if session != self._session:
            self._session = session
            self._high.clear()
            self._low.clear()
            self._close.clear()
            self._volume.clear()
        self._high.append(bar.high)
        self._low.append(bar.low)
        self._close.append(bar.close)
        self._volume.append(bar.volume)

        high = np.asarray(self._high, dtype=float)
        low = np.asarray(self._low, dtype=float)
        close = np.asarray(self._close, dtype=float)
        volume = np.asarray(self._volume, dtype=float)
        typical_price = (high + low + close) / 3.0
        total_vol = volume.sum()
        if total_vol > 0:
            return float((typical_price * volume).sum() / total_vol)
        return float(close[-1])


class AtrWindow:
    """Partial-window ATR over the whole bar stream (the replay convention).

    Equivalent to the indicator engine's ``atr_partial``
    (``shared.indicators.engine.backtest_backend``) held incrementally:

    * true range at the first bar is ``high - low`` (no previous close to use);
    * afterwards ``max(h-l, |h-prev_close|, |l-prev_close|)``;
    * the value at bar ``i`` is the mean of the trailing ``min(i+1, period)``
      true ranges.

    The window is NOT reset per session — the witness computes ATR over the whole
    frame, so the first bar of a session uses the previous session's last close.
    That is what makes a stitched seed advance ATR
    (``tools/tos_cp3/produce_fields.py``, ``emit_days``).
    """

    def __init__(self, period: int) -> None:
        if period < 1:
            raise FieldEvalError(f"atr period must be >= 1, got {period}")
        self._period = period
        self._true_ranges: deque[float] = deque(maxlen=period)
        self._prev_close: float | None = None

    def update(self, bar: FieldBar) -> float:
        """Append *bar*'s true range and return the ATR at this bar."""
        if self._prev_close is None:
            true_range = bar.high - bar.low
        else:
            true_range = max(
                bar.high - bar.low,
                abs(bar.high - self._prev_close),
                abs(bar.low - self._prev_close),
            )
        self._true_ranges.append(true_range)
        self._prev_close = bar.close
        return float(np.asarray(self._true_ranges, dtype=float).mean())


__all__ = [
    "AtrWindow",
    "FieldBar",
    "SessionVwapTypical",
    "minutes_since_open",
]
