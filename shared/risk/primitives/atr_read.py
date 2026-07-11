"""ATR reading/normalization primitive (P4-a).

ATR *calculation* has a single source of truth: the P1 indicator engine
(``shared/indicators/engine`` — ``ATRCalculator`` in the reference backend).
This module does NOT recompute ATR; it only re-expresses an already-computed
reading that may arrive in normalized (ratio) form.

Legacy sites expressed here by parameterizing the detection threshold:

- ``atr_dynamic._get_atr``: threshold ``0.5``, reference ``current_price``.
- ``mean_reversion_exit._get_atr``: threshold ``0.5`` in code (the docstring
  says "< 1.0" but the implementation compares against ``0.5``), reference
  ``close``.
- ``track_a_exit._get_atr``: no normalization at all → ``normalized_below=None``.

Dict extraction / key fallbacks (``atr`` vs ``atr_14`` vs metadata
``entry_atr``) stay at the call sites; this primitive takes the raw float.
No hardcoded threshold: ``normalized_below`` is always explicit.
"""

from __future__ import annotations

__all__ = ["normalize_atr"]


def normalize_atr(
    raw_atr: float,
    reference_price: float,
    *,
    normalized_below: float | None,
) -> float:
    """Convert a possibly-normalized ATR reading to absolute price units.

    A normalized ATR is a ratio (typically ``0.001~0.05``); an absolute ATR
    for KRX instruments is ``>= 1`` price unit. When ``raw_atr`` is positive
    but below ``normalized_below`` and ``reference_price`` is positive, the
    reading is treated as a ratio and scaled by ``reference_price``;
    otherwise it passes through unchanged.

    Args:
        raw_atr: ATR reading as computed upstream (P1 engine is the
            calculation SoT).
        reference_price: Price used to de-normalize a ratio reading
            (current price / close). Ignored unless conversion applies.
        normalized_below: Detection threshold — readings strictly below this
            are considered normalized. ``None`` disables normalization
            entirely (``track_a_exit`` behavior).

    Returns:
        ATR in absolute price units; ``0.0`` when ``raw_atr <= 0``.
    """
    if raw_atr <= 0:
        return 0.0
    if (
        normalized_below is not None
        and raw_atr < normalized_below
        and reference_price > 0
    ):
        return raw_atr * reference_price
    return raw_atr
