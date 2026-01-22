"""PnL and trading calculation utilities.

Centralized calculation functions for profit/loss, position sizing, and
trading metrics. All calculations are extracted here to avoid duplication.

Usage:
    from shared.utils.calc import calc_profit_rate, calc_unrealized_pnl

    # Calculate profit rate
    rate = calc_profit_rate(
        entry_price=100.0,
        current_price=105.0,
        side="long",
    )  # Returns 0.05 (5%)

    # Calculate unrealized PnL
    pnl = calc_unrealized_pnl(
        entry_price=100.0,
        current_price=105.0,
        quantity=10,
        side="long",
    )  # Returns 50.0
"""

from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

# Type alias for position side
PositionSideType = Literal["long", "short", "LONG", "SHORT", "BUY", "SELL"]


def normalize_side(side: PositionSideType | str) -> str:
    """Normalize position side to 'long' or 'short'.

    Args:
        side: Position side string (case-insensitive)

    Returns:
        Normalized side ('long' or 'short')

    Raises:
        ValueError: If side is not recognized
    """
    side_lower = str(side).lower()

    if side_lower in ("long", "buy"):
        return "long"
    elif side_lower in ("short", "sell"):
        return "short"
    else:
        raise ValueError(f"Invalid side: {side}. Expected: long/short/buy/sell")


def calc_profit_rate(
    entry_price: float,
    current_price: float,
    side: PositionSideType | str = "long",
) -> float:
    """Calculate profit rate (as decimal).

    Args:
        entry_price: Entry price of position
        current_price: Current market price
        side: Position side ('long' or 'short')

    Returns:
        Profit rate as decimal (e.g., 0.05 for 5%)

    Example:
        >>> calc_profit_rate(100.0, 105.0, "long")
        0.05
        >>> calc_profit_rate(100.0, 95.0, "short")
        0.05
    """
    if entry_price <= 0:
        logger.warning(f"Invalid entry_price: {entry_price}")
        return 0.0

    if current_price < 0:
        logger.warning(f"Invalid current_price: {current_price}")
        return 0.0

    normalized_side = normalize_side(side)

    if normalized_side == "long":
        return (current_price - entry_price) / entry_price
    else:  # short
        return (entry_price - current_price) / entry_price


def calc_profit_pct(
    entry_price: float,
    current_price: float,
    side: PositionSideType | str = "long",
) -> float:
    """Calculate profit percentage.

    Args:
        entry_price: Entry price of position
        current_price: Current market price
        side: Position side ('long' or 'short')

    Returns:
        Profit as percentage (e.g., 5.0 for 5%)

    Example:
        >>> calc_profit_pct(100.0, 105.0, "long")
        5.0
    """
    return calc_profit_rate(entry_price, current_price, side) * 100


def calc_unrealized_pnl(
    entry_price: float,
    current_price: float,
    quantity: int,
    side: PositionSideType | str = "long",
) -> float:
    """Calculate unrealized profit/loss in currency.

    Args:
        entry_price: Entry price of position
        current_price: Current market price
        quantity: Position quantity
        side: Position side ('long' or 'short')

    Returns:
        Unrealized PnL in currency

    Example:
        >>> calc_unrealized_pnl(100.0, 105.0, 10, "long")
        50.0
    """
    if quantity <= 0:
        return 0.0

    normalized_side = normalize_side(side)

    if normalized_side == "long":
        return (current_price - entry_price) * quantity
    else:  # short
        return (entry_price - current_price) * quantity


def calc_realized_pnl(
    entry_price: float,
    exit_price: float,
    quantity: int,
    side: PositionSideType | str = "long",
    fee_rate: float = 0.0,
) -> float:
    """Calculate realized profit/loss including fees.

    Args:
        entry_price: Entry price of position
        exit_price: Exit price of position
        quantity: Position quantity
        side: Position side ('long' or 'short')
        fee_rate: Total fee rate (e.g., 0.003 for 0.3%)

    Returns:
        Realized PnL after fees

    Example:
        >>> calc_realized_pnl(100.0, 105.0, 10, "long", 0.003)
        46.925  # 50 - (100*10*0.0015 + 105*10*0.0015)
        # Note: fee_rate is the total round-trip fee, split evenly between entry and exit
    """
    gross_pnl = calc_unrealized_pnl(entry_price, exit_price, quantity, side)

    if fee_rate > 0:
        # Fees on both entry and exit
        entry_fee = entry_price * quantity * (fee_rate / 2)
        exit_fee = exit_price * quantity * (fee_rate / 2)
        return gross_pnl - entry_fee - exit_fee

    return gross_pnl


def calc_drop_from_high(
    current_price: float,
    highest_price: float,
) -> float:
    """Calculate percentage drop from highest price.

    Args:
        current_price: Current market price
        highest_price: Highest price since entry

    Returns:
        Drop percentage (e.g., 3.0 for 3% drop)

    Example:
        >>> calc_drop_from_high(97.0, 100.0)
        3.0
    """
    if highest_price <= 0:
        return 0.0

    if current_price >= highest_price:
        return 0.0

    return (highest_price - current_price) / highest_price * 100


def calc_order_quantity(
    order_amount: float,
    price: float,
    max_quantity: int = 1_000_000,
) -> int:
    """Calculate order quantity from order amount.

    Args:
        order_amount: Total order amount in currency
        price: Unit price
        max_quantity: Maximum allowed quantity (safety limit)

    Returns:
        Order quantity (integer, capped at max_quantity)

    Example:
        >>> calc_order_quantity(1_000_000, 50000)
        20
    """
    if price <= 0 or order_amount <= 0:
        return 0

    quantity = int(order_amount / price)

    # Safety cap to prevent integer overflow or excessive orders
    return min(quantity, max_quantity)


def calc_position_value(
    price: float,
    quantity: int,
) -> float:
    """Calculate position value.

    Args:
        price: Unit price
        quantity: Position quantity

    Returns:
        Position value in currency
    """
    return price * quantity


def calc_weight(
    position_value: float,
    total_capital: float,
) -> float:
    """Calculate position weight in portfolio.

    Args:
        position_value: Value of position
        total_capital: Total portfolio capital

    Returns:
        Weight as decimal (e.g., 0.1 for 10%)
    """
    if total_capital <= 0:
        return 0.0

    return position_value / total_capital


def validate_price(
    price: float,
    min_price: float = 0.0,
    max_price: float = float("inf"),
) -> bool:
    """Validate price is within acceptable range.

    Args:
        price: Price to validate
        min_price: Minimum acceptable price
        max_price: Maximum acceptable price

    Returns:
        True if valid, False otherwise
    """
    if price is None:
        return False

    try:
        price_float = float(price)
    except (TypeError, ValueError):
        return False

    return min_price < price_float < max_price
