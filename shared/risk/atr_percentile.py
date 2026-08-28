"""ATR percentile — one calculation shared by the backtest and the live writer.

Before this module the only ATR-percentile computation in the repo lived inside
:meth:`shared.backtest.market_context_replay.MarketContextReplay._precompute`
(``float(np.nanpercentile(atr_series, 90))``) and was reachable only from a
backtest.  The production ``VolatilityFilter`` threshold therefore had no
writer at all.  Promoting the arithmetic here lets the replay reference and the
live :mod:`shared.risk.volatility_reference` publisher share ONE implementation
instead of growing a second, subtly different one.

Only the *percentile* is shared.  The ATR series itself is produced differently
on each side and deliberately so:

* backtest — the full ATR series computed from a historical bar DataFrame by
  the backtest-convention indicator engine (``atr_partial``);
* live — a causal rolling window of ATR readings sampled from the running
  :class:`StreamingIndicatorEngine`, persisted between samples in Redis.

Both are sequences of ATR values in absolute price units, so the percentile
math is identical and is pinned as such by
``tests/unit/risk/test_atr_percentile.py``.

Undefined-result policy
-----------------------
:func:`atr_percentile` returns ``None`` — never ``0.0`` — whenever the
percentile cannot be established (empty input, all-NaN input, non-finite or
non-positive result).  This is load-bearing rather than cosmetic: a ``0.0``
threshold is exactly the historical defect this whole change closes, because
``current_atr > 0.0`` is true for every live reading and would reject every
signal.  ``None`` propagates as "no threshold known" and makes the filter skip
loudly instead of halting all trading silently.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

__all__ = ["DEFAULT_ATR_PERCENTILE", "atr_percentile"]

#: Upper-tail percentile used for the volatility reference.  Matches the
#: historical ``atr_90th_percentile`` naming and the backtest replay's fixed
#: 90th-percentile reference.
DEFAULT_ATR_PERCENTILE: float = 90.0


def atr_percentile(
    values: Sequence[float] | np.ndarray,
    percentile: float = DEFAULT_ATR_PERCENTILE,
) -> float | None:
    """Return the *percentile*-th ATR of *values*, or ``None`` when undefined.

    NaNs are ignored (``np.nanpercentile`` semantics), matching the backtest
    replay's historical behaviour bit for bit on the same input.

    Args:
        values: ATR readings in absolute price units.  Order is irrelevant.
        percentile: Percentile to take, in ``[0, 100]``.  Defaults to
            :data:`DEFAULT_ATR_PERCENTILE`.

    Returns:
        The percentile as a ``float``, or ``None`` when it cannot be
        established — empty/all-NaN input, or a non-finite or non-positive
        result.  See the module docstring for why ``None`` rather than ``0.0``.

    Raises:
        ValueError: If *percentile* is outside ``[0, 100]``.  A caller that
            mis-configures the percentile must fail loudly at wiring time
            rather than silently produce a nonsense threshold.
    """
    if not 0.0 <= percentile <= 100.0:
        raise ValueError(
            f"percentile must be within [0, 100], got {percentile!r}",
        )

    array = np.asarray(values, dtype=float).ravel()
    if array.size == 0:
        return None
    if bool(np.isnan(array).all()):
        # np.nanpercentile would emit a RuntimeWarning and return NaN here.
        return None

    result = float(np.nanpercentile(array, percentile))
    if not np.isfinite(result) or result <= 0.0:
        return None
    return result
