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
    """Build a real ``Position`` with optional raw extreme overrides.

    ``Position.__post_init__`` normalizes unset extremes
    (``highest_price == 0.0`` / ``lowest_price == inf``) to ``entry_price``.
    To exercise the legacy unset-extreme fallbacks the overrides are applied
    *after* construction, bypassing that normalization.

    Args:
        side: Position direction.
        entry_price: Entry price (may be ``0`` / negative for guard tests).
        quantity: Position size.
        highest_price: Raw ``highest_price`` to force post-construction.
        lowest_price: Raw ``lowest_price`` to force post-construction.

    Returns:
        A ``shared.models.position.Position`` instance.
    """
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
