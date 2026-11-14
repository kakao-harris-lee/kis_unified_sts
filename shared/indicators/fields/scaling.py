"""Integer scaling for published field values — ONE definition.

The TOS kernel compares only ``bool``/``int``/``str``: a float Critical Input is
dropped at the border (``tos/src/tos/marketfeed/value.py``). So every numeric
field a producer publishes is a scaled integer, and *how* it is rounded is part
of the field's meaning.

These two functions were moved here VERBATIM from
``tools/tos_cp3/produce_fields.py`` (CP-3 B1a) when the declarative field
evaluator needed the same rounding: a second copy is exactly how the legacy-driven
producer and the declarative producer would come to disagree about a bar whose
value lands on a half. ``produce_fields`` re-exports them from this module, so
its published bytes are unchanged — the CP-3 journal rounding is pinned by
``tests/tools/test_cp3_produce_fields.py`` and by the parity test in
``tests/unit/indicators/fields/test_scaling.py``.

Pure: stdlib ``math`` only.
"""

from __future__ import annotations

import math


def scaled_int_half_up(value: float, scale: int) -> int:
    """Scale a MAGNITUDE by *scale* and round half-up to an ``int``.

    Used for prices and ATR, where the nearest representable value is what is
    wanted and no threshold comparison is made on the published integer.
    Half-up is monotone, so the OHLC relations a ``tos.backtest.Bar`` validates
    (``high >= low``, ``open``/``close`` inside the range) survive the scaling.

    Half-up rather than :func:`round` because ``round`` is banker's rounding,
    whose result depends on the parity of the neighbouring integer —
    deterministic, but not reproducible by a reader who reimplements the scale
    from the sidecar.
    """
    return int(math.floor(value * scale + 0.5))


def scaled_int_toward_zero(value: float, scale: int) -> int:
    """Scale a SIGNED, threshold-compared value and truncate toward zero.

    Used for ``z_x1000``. Two properties half-up does not have:

    * **Symmetric** — ``+1.7995`` and ``-1.7995`` become ``+1799`` and
      ``-1799``, whereas half-up maps them to ``1800`` and ``-1799``.
    * **Conservative at the trigger** — truncation toward zero means
      ``abs(z_x1000) >= scaled_int_toward_zero(extreme_atr_mult, 1000)`` holds
      only when ``abs(z) >= extreme_atr_mult`` really does, so a policy written
      on the integer **never fires where the legacy setup did not**. The price
      is that the published integer understates ``abs(z)`` by up to one unit
      (0.001 ATR); see declared difference D8.
    """
    return int(math.trunc(value * scale))


#: Rounding mode name -> implementation. The ``round:`` key of a ``publish``
#: entry's ``scale`` mapping names one of these; an unknown name is refused by
#: the loader (``schema.py``) rather than silently defaulted, because the two
#: modes disagree on exactly the values a threshold is written against.
ROUNDING_MODES = {
    "half_up": scaled_int_half_up,
    "toward_zero": scaled_int_toward_zero,
}


__all__ = ["ROUNDING_MODES", "scaled_int_half_up", "scaled_int_toward_zero"]
