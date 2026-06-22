"""Per-symbol trend-strength predicate for the bear-gate override.

A symbol is "strong" (worth evaluating / exempt from blanket bear logic) when
its daily trend is confirmed-up by a multi-factor AND. Inputs are the
``system:daily_indicators:latest`` per-symbol fields. Pure + side-effect-free.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class StrengthCriteria:
    rsi_min: float = 55.0
    require_above_sma20: bool = True
    require_rsi_rising: bool = True
    require_macd_positive: bool = True


def _finite(v: object) -> float | None:
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def is_strong(daily: dict, criteria: StrengthCriteria) -> bool:
    """True iff all enabled trend conditions hold. Missing/NaN field → False."""
    close = _finite(daily.get("daily_close"))
    sma20 = _finite(daily.get("daily_sma_20"))
    rsi = _finite(daily.get("daily_rsi_14"))
    prev_rsi = _finite(daily.get("daily_prev_rsi_14"))
    macd = _finite(daily.get("daily_macd_hist"))

    if rsi is None or rsi < criteria.rsi_min:
        return False
    if criteria.require_above_sma20 and (
        close is None or sma20 is None or close <= sma20
    ):
        return False
    if criteria.require_rsi_rising and (prev_rsi is None or rsi <= prev_rsi):
        return False
    return not (criteria.require_macd_positive and (macd is None or macd <= 0))


def compute_strong_symbols(
    indicators_by_code: dict[str, dict], criteria: StrengthCriteria
) -> set[str]:
    """Return the set of codes whose daily indicators satisfy ``is_strong``."""
    return {
        code
        for code, daily in (indicators_by_code or {}).items()
        if isinstance(daily, dict) and is_strong(daily, criteria)
    }
