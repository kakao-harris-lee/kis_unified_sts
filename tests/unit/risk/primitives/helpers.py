"""Shared factories for risk-primitive tests (real Position model)."""

from __future__ import annotations

from shared.models.position import Position, PositionSide


def make_position(
    side: PositionSide,
    entry_price: float,
    quantity: int = 1,
    *,
    highest_price: float | None = None,
    lowest_price: float | None = None,
) -> Position:
    """Build a real ``Position`` with optional raw extreme overrides."""
    position = Position(
        id="test-pos",
        code="005930",
        name="TEST",
        side=side,
        quantity=quantity,
        entry_price=entry_price,
    )
    if highest_price is not None:
        position.highest_price = highest_price
    if lowest_price is not None:
        position.lowest_price = lowest_price
    return position
