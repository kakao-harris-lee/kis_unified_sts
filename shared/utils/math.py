"""Math utilities with safety checks."""
import logging
from typing import Union

logger = logging.getLogger(__name__)

Number = Union[int, float]


def safe_divide(
    numerator: Number,
    denominator: Number,
    default: Number = 0.0,
    warn: bool = False,
) -> float:
    """Safely divide two numbers, returning default if denominator is zero.

    Args:
        numerator: The number to divide
        denominator: The number to divide by
        default: Value to return if denominator is zero (default: 0.0)
        warn: Whether to log a warning on division by zero

    Returns:
        Result of division or default value
    """
    if denominator == 0:
        if warn:
            logger.warning(f"Division by zero avoided: {numerator}/{denominator}")
        return float(default)
    return float(numerator) / float(denominator)


def safe_pct_change(
    old_value: Number,
    new_value: Number,
    default: Number = 0.0,
) -> float:
    """Calculate percentage change safely.

    Args:
        old_value: The original value
        new_value: The new value
        default: Value to return if old_value is zero

    Returns:
        Percentage change (e.g., 0.05 for 5% increase)
    """
    if old_value == 0:
        return float(default)
    return (float(new_value) - float(old_value)) / float(old_value)
