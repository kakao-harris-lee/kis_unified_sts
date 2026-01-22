"""Shared utilities."""
from .math import safe_divide, safe_pct_change
from .calc import (
    calc_profit_rate,
    calc_profit_pct,
    calc_unrealized_pnl,
    calc_realized_pnl,
    calc_drop_from_high,
    calc_order_quantity,
    calc_position_value,
    calc_weight,
    validate_price,
    normalize_side,
)

__all__ = [
    # Math utilities
    "safe_divide",
    "safe_pct_change",
    # Calc utilities
    "calc_profit_rate",
    "calc_profit_pct",
    "calc_unrealized_pnl",
    "calc_realized_pnl",
    "calc_drop_from_high",
    "calc_order_quantity",
    "calc_position_value",
    "calc_weight",
    "validate_price",
    "normalize_side",
]
