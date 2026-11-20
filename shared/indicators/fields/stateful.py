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
2. **A degenerate window has no value — but "degenerate" means different things
   to the two ops, and only one of them meets it on a lock.** The two cases,
   measured rather than assumed:

   * ``williams_r`` has a FINITE window, so ``period`` bars of a Korean stock
     sitting on its daily limit (상한가/하한가) make ``highest == lowest``
     exactly. TA-Lib returns ``0.0`` there, which reads as "the close is at the
     top of the range" — an entry trigger manufactured out of a window with no
     information. This op returns ``None`` instead, and the tenant's own
     ``permissive`` decides what that means for its gate.
   * ``rsi`` has an INFINITE one (Wilder smoothing never forgets), so its
     ``None`` is rarer than it looks: ``avg_gain + avg_loss`` is exactly ``0``
     only when the series has not moved AT ALL since the first bar. After any
     earlier movement a lock decays both averages toward zero without ever
     reaching it, so this op keeps returning the PRE-LOCK ratio for as long as
     the lock lasts (measured: ``period=2``, 30 moving bars then 400 locked
     ones — 99.0196 on every one of the 400). TA-Lib diverges in the opposite
     direction: it prints exactly ``0.0`` once the sum falls under its
     ``TA_IS_ZERO`` epsilon (1e-8, a C-level constant, so the crossing bar is
     build-dependent) — bar 81 of that same series.

   Neither value is informative during a lock. A tenant that must not act
   through one gates on something that notices it (a range or volume field),
   not on RSI. All four behaviours above are pinned in
   ``test_talib_reference.py``, and the parity tests exclude the degenerate
   tail rather than pretending the two agree there.

Part 3 — what their state does NOT do: reset on a session boundary.
-------------------------------------------------------------------
Neither op is session-aware. ``rsi`` carries its averages and ``williams_r`` its
window across the overnight gap, so the first bar of a session is one more
change / one more bar, and an opening gap enters RSI as a single large one. That
is ``atr``'s behaviour (``bar.py``: "the window is NOT reset per session"), not
``session.vwap_typical``'s. It is also what a whole-frame TA-Lib pass over a
stitched series computes, which is the point: the reference and this stream have
to agree bar for bar. A tenant that wants a session-local reading cannot get it
by declaring these ops — that would be a new op.

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
    the first ``period`` bars (TA-Lib's ``TA_RSI_Lookback``). ``period < 2`` is
    refused, as TA-Lib refuses it (``TA_BAD_PARAM``): accepting it would put a
    value outside the reference's own domain into a published field.

    **This op has unbounded memory.** Wilder smoothing weights every past bar,
    so the value on a given bar depends on where the stream STARTED, and two
    runs over the same bars from different starts converge only slowly —
    measured on 7000 bars, to the last bit after roughly ``35 * period`` bars
    (period 2: 55; 14: 470; 50: 1758; period 200 had not converged within
    7000). The catalog bounds ``period`` for that reason; see the note beside
    the op in :mod:`shared.indicators.fields.catalog`.

    Args:
        period: Wilder lookback, in bars.
        field: Declared field name, for refusal messages.
    """

    def __init__(self, *, period: int, field: str) -> None:
        if period < 2:
            raise FieldEvalError(
                f"{field}: rsi period must be >= 2, got {period} "
                "(TA-Lib refuses a shorter one)"
            )
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
    docstring, decision 2. ``period < 2`` is refused because TA-Lib refuses it.

    Unlike :class:`WilderRsi` this op forgets: the window holds exactly
    ``period`` bars, so its value never depends on where the stream started.

    Args:
        period: Window length, in bars.
        field: Declared field name, for refusal messages.
    """

    def __init__(self, *, period: int, field: str) -> None:
        if period < 2:
            raise FieldEvalError(
                f"{field}: williams_r period must be >= 2, got {period} "
                "(TA-Lib refuses a shorter one)"
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
