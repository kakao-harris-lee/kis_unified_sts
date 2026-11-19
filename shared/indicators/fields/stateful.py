"""The stateful catalog ops: the gated windows, and the momentum indicators.

Part 1 — the gated ops: ONE base class, three invariants.

``gated_percentile``, ``gated_max``, ``gated_min`` and ``gated_lag`` differ only
in how they reduce their window. Everything that can go subtly wrong about them
is identical, so it is enforced once, here, rather than four times:

1. **Read before append (strictly causal).** The value returned on bar *i* is a
   function of samples from bars strictly before *i*. The current bar's value
   enters the window only after the read. This is
   ``shared/decision/setups/vwap_reversion.py::_vol_reference`` /
   ``_self_range`` ("Append AFTER reading (strictly causal: reference excludes
   this bar)") expressed once.
2. **Sample only when gated.** The legacy windows advance only on bars where the
   early-return chain reached them — in-window bars with usable inputs. A
   declarative field is evaluated on *every* bar, so the window advance is moved
   to an explicit ``sample_when`` boolean field: a bar where it is false is read
   but contributes no sample. Get this wrong and ``hi_vol`` differs from the
   warmup onward (plan §6, risk 1).
3. **``None`` during warmup.** Fewer than ``warmup`` samples means "no value
   yet", never ``0`` and never ``False``. The consumer makes the gate permissive
   with an explicit ``permissive`` op.

The reduction itself is deliberately the legacy's own call: ``np.percentile`` with
its default (linear) interpolation on the sample window, and the builtins ``max``
/ ``min`` — not their numpy counterparts — so no float-order difference can enter
through the reduction (plan §6, risk 2).

Part 2 — ``rsi`` and ``williams_r``: general indicators, TA-Lib's arithmetic.
----------------------------------------------------------------------------
These two share none of the above: they take no ``sample_when`` (every bar is a
sample, which is what the textbook definition says), and the current bar IS part
of their value. What they do share with the gated ops is the warmup rule — no
value until the lookback is covered, ``None`` and never a neutral 50 or 0.

Two decisions a reader will want the reason for:

1. **The reference is TA-Lib, reproduced operation by operation** — including
   ``williams_r``'s odd-looking ``(highest - close) / ((highest - lowest) /
   -100.0)``, which is ``ta_WILLR.c``'s own order. "Simplifying" it to
   ``-100 * (highest - close) / (highest - lowest)`` changes the last bit on
   roughly a third of bars (measured: 1329 of 3987 at ``period=14`` on 4000
   random bars), and a threshold written on the published integer can flip on
   exactly those. The parity is pinned to the last bit by
   ``tests/unit/indicators/fields/test_talib_reference.py``.
2. **A degenerate window has no value, where TA-Lib returns 0.0.** TA-Lib's RSI
   on a flat series is ``0.0`` and its %R on a flat window is ``0.0`` — read as
   indicator values those are "maximally oversold" and "at the top of the
   range", i.e. two entry triggers manufactured out of a window that contains no
   information. A Korean stock sitting on its daily limit (상한가/하한가)
   produces exactly that window, so this is a real input, not a hypothetical
   one. Both ops return ``None`` there: the field has no value, and the tenant's
   own ``permissive`` decides what that means for its gate. The divergence is
   declared, and pinned against TA-Lib by the same test.

These are not imported from ``shared.indicators.engine`` for the reason
:mod:`shared.indicators.fields.bar` gives for ``atr``: those backends are
whole-window pandas/numpy functions and this evaluator is a bar-by-bar stream,
so calling one per bar is quadratic. They also compute a different thing —
``momentum_backend._rsi`` seeds Wilder's average with an ``ewm`` rather than the
mean of the first ``period`` changes, and ``momentum_backend._williams_r`` uses
``min_periods=1`` (a partial window instead of a warmup) and returns ``-50.0``
on a flat one. Those conventions are the legacy strategy path's and are frozen
there; the catalog's are the reference ones.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from typing import Final

import numpy as np

from shared.indicators.fields.errors import FieldEvalError

#: ``gated_lag`` is the one-sample case of the same machinery.
_LAG_WINDOW: Final[int] = 1


class GatedWindowOp(ABC):
    """Base class of every stateful catalog op. See the module docstring.

    Args:
        window: Maximum number of samples retained (the trailing window).
        warmup: Minimum number of samples before a value is produced.
        field: Declared field name, for refusal messages.
    """

    def __init__(self, *, window: int, warmup: int, field: str) -> None:
        if window < 1:
            raise FieldEvalError(f"{field}: window must be >= 1, got {window}")
        if warmup < 1:
            raise FieldEvalError(f"{field}: warmup must be >= 1, got {warmup}")
        if warmup > window:
            # The legacy's own footgun note (``trend_warmup_bars``): a warmup
            # above the window cap means the window never reaches warmup and the
            # field is permanently None — a silently dead gate.
            raise FieldEvalError(
                f"{field}: warmup={warmup} exceeds window={window}, so the "
                "window can never reach warmup and the field would be "
                "permanently None (a silently dead gate)"
            )
        self._field = field
        self._warmup = warmup
        self._samples: deque[float] = deque(maxlen=window)

    @property
    def sample_count(self) -> int:
        """Number of samples currently held (for tests and diagnostics)."""
        return len(self._samples)

    def step(self, value: float | None, *, sample: bool) -> float | None:
        """Read the window, then append *value* when *sample* is true.

        Args:
            value: The current bar's input value. May be ``None`` only on a bar
                that does not sample — a sampled ``None`` is a declaration bug.
            sample: The ``sample_when`` field's value on this bar.

        Returns:
            The reduced window value, or ``None`` while shorter than ``warmup``.
        """
        reduced = (
            self._reduce() if len(self._samples) >= self._warmup else None
        )  # read BEFORE append — invariant 1
        if sample:
            if value is None:
                raise FieldEvalError(
                    f"{self._field}: the input has no value on a bar its "
                    "sample_when gate admits — a missing value cannot enter a "
                    "causal window"
                )
            self._samples.append(float(value))
        return reduced

    @abstractmethod
    def _reduce(self) -> float:
        """Reduce the current sample window to one value."""


class GatedPercentile(GatedWindowOp):
    """``gated_percentile`` — the q-th percentile of the sample window.

    ``np.percentile`` with its default interpolation, called on the sample deque
    exactly as ``_vol_reference`` calls it.
    """

    def __init__(self, *, q: float, window: int, warmup: int, field: str) -> None:
        super().__init__(window=window, warmup=warmup, field=field)
        if not 0.0 <= q <= 100.0:
            raise FieldEvalError(f"{field}: q must be in [0, 100], got {q}")
        self._q = q

    def _reduce(self) -> float:
        return float(np.percentile(self._samples, self._q))


class GatedMax(GatedWindowOp):
    """``gated_max`` — the maximum of the sample window (builtin ``max``)."""

    def _reduce(self) -> float:
        return max(self._samples)


class GatedMin(GatedWindowOp):
    """``gated_min`` — the minimum of the sample window (builtin ``min``)."""

    def _reduce(self) -> float:
        return min(self._samples)


class GatedLag(GatedWindowOp):
    """``gated_lag`` — the last sample taken before this bar.

    The one-sample case: ``prev_close = self._close_window[-1] if
    self._close_window else None`` in ``vwap_reversion.py::check``, read before
    the same bar's close is appended.
    """

    def __init__(self, *, field: str) -> None:
        super().__init__(window=_LAG_WINDOW, warmup=_LAG_WINDOW, field=field)

    def _reduce(self) -> float:
        return self._samples[-1]


class WilderRsi:
    """``rsi`` — Wilder's RSI of the close, in TA-Lib's arithmetic.

    The definition, in the order ``ta_RSI.c`` performs it:

    * the first ``period`` changes seed the averages as plain sums divided by
      ``period`` (NOT an ``ewm``);
    * every later bar smooths: ``avg = (avg * (period - 1) + change) / period``,
      with the multiply, the add and the divide in that order;
    * the value is ``100 * avg_gain / (avg_gain + avg_loss)``, which is Wilder's
      ``100 - 100 / (1 + RS)`` without forming ``RS`` — so a zero ``avg_loss``
      gives exactly ``100.0`` instead of dividing by zero.

    ``period`` changes need ``period + 1`` closes, so the value is ``None`` on
    the first ``period`` bars (TA-Lib's ``TA_RSI_Lookback``). TA-Lib refuses
    ``period < 2``; this op accepts ``period = 1`` (the loader's floor for every
    count), where the formula degenerates to 0 or 100 on each bar.

    Args:
        period: Wilder lookback, in bars.
        field: Declared field name, for refusal messages.
    """

    def __init__(self, *, period: int, field: str) -> None:
        if period < 1:
            raise FieldEvalError(f"{field}: rsi period must be >= 1, got {period}")
        self._period = period
        self._changes = 0
        self._prev_close: float | None = None
        self._avg_gain = 0.0
        self._avg_loss = 0.0

    @property
    def change_count(self) -> int:
        """Number of close-to-close changes seen (for tests and diagnostics)."""
        return self._changes

    def update(self, close: float) -> float | None:
        """Advance by one bar and return the RSI at it, or ``None`` in warmup."""
        previous = self._prev_close
        self._prev_close = close
        if previous is None:
            return None

        change = close - previous
        self._changes += 1
        if self._changes <= self._period:
            # Seed: the sum of the first `period` changes, divided once.
            if change < 0:
                self._avg_loss -= change
            else:
                self._avg_gain += change
            if self._changes < self._period:
                return None
            self._avg_gain /= self._period
            self._avg_loss /= self._period
        else:
            self._avg_gain *= self._period - 1
            self._avg_loss *= self._period - 1
            if change < 0:
                self._avg_loss -= change
            else:
                self._avg_gain += change
            self._avg_gain /= self._period
            self._avg_loss /= self._period

        total = self._avg_gain + self._avg_loss
        if total == 0.0:
            # No movement at all in the smoothed history: RSI is undefined, and
            # TA-Lib's 0.0 would read as "maximally oversold". See the module
            # docstring, decision 2.
            return None
        return 100.0 * (self._avg_gain / total)


class WilliamsR:
    """``williams_r`` — Williams %R over the trailing ``period`` bars.

    ``(highest_high - close) / ((highest_high - lowest_low) / -100)`` over the
    last ``period`` bars INCLUDING this one — ``ta_WILLR.c``'s own arithmetic
    order, which is not interchangeable with the algebraically equal
    ``-100 * (hh - close) / (hh - ll)`` (module docstring, decision 1). The
    range is ``-100`` (close at the window low) to ``0`` (close at its high).

    The value is ``None`` on the first ``period - 1`` bars (TA-Lib's
    ``TA_WILLR_Lookback``), and on a bar whose window is flat — see the module
    docstring, decision 2.

    Args:
        period: Window length, in bars.
        field: Declared field name, for refusal messages.
    """

    def __init__(self, *, period: int, field: str) -> None:
        if period < 1:
            raise FieldEvalError(
                f"{field}: williams_r period must be >= 1, got {period}"
            )
        self._period = period
        self._highs: deque[float] = deque(maxlen=period)
        self._lows: deque[float] = deque(maxlen=period)

    @property
    def sample_count(self) -> int:
        """Number of bars currently in the window (for tests and diagnostics)."""
        return len(self._highs)

    def update(self, *, high: float, low: float, close: float) -> float | None:
        """Advance by one bar and return %R at it, or ``None`` in warmup."""
        self._highs.append(high)
        self._lows.append(low)
        if len(self._highs) < self._period:
            return None
        highest = max(self._highs)
        lowest = min(self._lows)
        divisor = (highest - lowest) / -100.0
        if divisor == 0.0:  # a flat window — also true of `-0.0`, as in TA-Lib
            return None
        return (highest - close) / divisor


__all__ = [
    "GatedLag",
    "GatedMax",
    "GatedMin",
    "GatedPercentile",
    "GatedWindowOp",
    "WilderRsi",
    "WilliamsR",
]
