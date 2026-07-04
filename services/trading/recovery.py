"""Position recovery helpers for trading runtime startup."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from shared.models.position import Position, PositionSide, PositionState


@dataclass(frozen=True)
class RecoveryFreshness:
    """Freshness decision for a recovered open position."""

    recoverable: bool
    is_swing: bool
    age_days: int


def parse_recovery_entry_time(pos_data: Mapping[str, Any]) -> datetime:
    """Parse the persisted entry timestamp for a recoverable position."""
    entry_time_str = pos_data.get("entry_time", "")
    if not isinstance(entry_time_str, str) or not entry_time_str:
        raise ValueError("missing entry_time")
    try:
        return datetime.fromisoformat(entry_time_str)
    except ValueError as exc:
        raise ValueError("invalid entry_time") from exc


def evaluate_position_freshness(
    *,
    strategy: str,
    entry_time: datetime,
    today: date,
    swing_strategies: Collection[str],
    max_swing_age_days: int,
) -> RecoveryFreshness:
    """Evaluate Redis position freshness using swing/intraday recovery policy."""
    age_days = (today - entry_time.date()).days
    is_swing = strategy in swing_strategies
    if is_swing:
        recoverable = age_days <= max_swing_age_days
    else:
        recoverable = entry_time.date() == today
    return RecoveryFreshness(
        recoverable=recoverable,
        is_swing=is_swing,
        age_days=age_days,
    )


def reconstruct_recovered_position(
    pos_data: Mapping[str, Any],
    *,
    entry_time: datetime,
    symbol_names: Mapping[str, str],
) -> Position:
    """Reconstruct a Position from persisted recovery data."""
    side = PositionSide(pos_data.get("side", "long"))
    entry_price = float(pos_data["entry_price"])
    current_price = float(pos_data.get("current_price", entry_price))

    pos_code = str(pos_data["code"])
    position = Position(
        id=str(pos_data.get("id", "")),
        code=pos_code,
        name=str(pos_data.get("name", "") or symbol_names.get(pos_code, pos_code)),
        side=side,
        quantity=int(pos_data["quantity"]),
        entry_price=entry_price,
        entry_time=entry_time,
        current_price=current_price,
        highest_price=float(
            pos_data.get("highest_price", max(entry_price, current_price))
        ),
        lowest_price=float(
            pos_data.get("lowest_price", min(entry_price, current_price))
        ),
        state=_position_state_from_recovery_data(pos_data),
        strategy=str(pos_data.get("strategy", "")),
        fee_rate=float(pos_data.get("fee_rate", 0.003)),
    )

    recovered_coid = str(pos_data.get("client_order_id") or "").strip()
    if recovered_coid:
        position.metadata["client_order_id"] = recovered_coid

    stop_price = pos_data.get("stop_price")
    if stop_price is not None:
        position.stop_price = float(stop_price)

    return position


def _position_state_from_recovery_data(
    pos_data: Mapping[str, Any],
) -> PositionState:
    state = pos_data.get("state", PositionState.SURVIVAL.value)
    if isinstance(state, PositionState):
        return state
    return PositionState(str(state).lower())
