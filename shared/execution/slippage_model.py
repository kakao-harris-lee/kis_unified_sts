"""Slippage model for KOSPI200 mini futures execution.

Provides realistic slippage estimation based on order book depth, bid-ask spread,
order size relative to available liquidity, and time-of-day effects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SlippageModelConfig:
    """Configuration for futures slippage model.

    Attributes:
        enabled: Whether slippage model is enabled (default: False for backward compatibility)
        base_spread_bps: Base spread cost in basis points (1 bps = 0.01%)
        depth_impact_factor: Multiplier for depth-based slippage (0 = no impact, higher = more impact)
        time_of_day_multipliers: Dict mapping time window (HH:MM-HH:MM) to multiplier
        min_slippage_bps: Minimum slippage in basis points (floor)
        max_slippage_bps: Maximum slippage in basis points (cap)
    """

    enabled: bool = False
    base_spread_bps: float = 1.0
    depth_impact_factor: float = 0.5
    time_of_day_multipliers: dict[str, float] = field(default_factory=dict)
    min_slippage_bps: float = 0.5
    max_slippage_bps: float = 10.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlippageModelConfig:
        """Create config from dictionary (YAML loader).

        Args:
            data: Configuration dictionary

        Returns:
            SlippageModelConfig instance
        """
        if not isinstance(data, dict):
            # If passed non-dict (e.g., None), return disabled default
            return cls()

        # Parse time_of_day_multipliers
        time_multipliers_raw = data.get("time_of_day_multipliers", {})
        time_multipliers: dict[str, float] = {}

        if isinstance(time_multipliers_raw, dict):
            for time_window, multiplier in time_multipliers_raw.items():
                try:
                    time_multipliers[str(time_window)] = float(multiplier)
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Invalid time_of_day_multiplier '{time_window}': {multiplier}, error: {e}"
                    )

        return cls(
            enabled=_to_bool(data.get("enabled", False)),
            base_spread_bps=float(data.get("base_spread_bps", 1.0)),
            depth_impact_factor=float(data.get("depth_impact_factor", 0.5)),
            time_of_day_multipliers=time_multipliers,
            min_slippage_bps=float(data.get("min_slippage_bps", 0.5)),
            max_slippage_bps=float(data.get("max_slippage_bps", 10.0)),
        )

    def get_time_multiplier(self, current_time: time | None = None) -> float:
        """Get time-of-day multiplier for current time.

        Args:
            current_time: Current time (defaults to now)

        Returns:
            Multiplier for current time window (1.0 if no match)
        """
        if not self.time_of_day_multipliers:
            return 1.0

        if current_time is None:
            current_time = datetime.now().time()

        # Find matching time window
        for time_window, multiplier in self.time_of_day_multipliers.items():
            if _time_in_window(current_time, time_window):
                return multiplier

        return 1.0


def _to_bool(value: Any, default: bool = False) -> bool:
    """Convert value to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on", "enabled"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _time_in_window(current: time, window_str: str) -> bool:
    """Check if current time is within time window.

    Args:
        current: Current time
        window_str: Time window string (e.g., "09:00-12:00")

    Returns:
        True if current time is within window
    """
    try:
        if "-" not in window_str:
            return False

        start_str, end_str = window_str.split("-", 1)
        start = _parse_time(start_str.strip())
        end = _parse_time(end_str.strip())

        if start <= end:
            # Normal window (e.g., 09:00-12:00)
            return start <= current <= end
        else:
            # Overnight window (e.g., 23:00-01:00)
            return current >= start or current <= end

    except (ValueError, AttributeError) as e:
        logger.warning(f"Invalid time window format '{window_str}': {e}")
        return False


def _parse_time(time_str: str) -> time:
    """Parse time string in HH:MM format.

    Args:
        time_str: Time string (HH:MM)

    Returns:
        time object
    """
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {time_str}")

    hour = int(parts[0])
    minute = int(parts[1])
    return time(hour=hour, minute=minute)
