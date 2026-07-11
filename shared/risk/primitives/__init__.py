"""Risk primitives library (P4-a): pure, stateless PnL / extreme / stop / ATR math.

Single source for the side-aware risk math copy-pasted across exit
generators. Landed as a zero-consumer library (P4-a); exit generators are
rewired to these primitives in P4-b.

Modules:
    pnl: Side-aware profit ratio/amount (``_calc_profit_pct`` /
        ``_calc_profit_amount`` unification).
    extremes: Favorable extreme since entry (``_get_extreme_since_entry``
        unification, ``Position``-sourced).
    stops: Stateless stop / trailing-stop decisions (HWM passed in).
    atr_read: Normalized-ATR re-expression (calculation SoT stays in the
        P1 indicator engine).
"""

from shared.risk.primitives.atr_read import normalize_atr
from shared.risk.primitives.extremes import extreme_since_entry
from shared.risk.primitives.pnl import profit_amount, profit_pct
from shared.risk.primitives.stops import (
    abs_stop_hit,
    atr_stop_level,
    pct_stop_hit,
    pct_trailing_stop_level,
    trailing_stop_hit,
)

__all__ = [
    "abs_stop_hit",
    "atr_stop_level",
    "extreme_since_entry",
    "normalize_atr",
    "pct_stop_hit",
    "pct_trailing_stop_level",
    "profit_amount",
    "profit_pct",
    "trailing_stop_hit",
]
