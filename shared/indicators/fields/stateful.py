"""The gated (stateful) catalog ops — ONE base class, three invariants.

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


__all__ = [
    "GatedLag",
    "GatedMax",
    "GatedMin",
    "GatedPercentile",
    "GatedWindowOp",
]
