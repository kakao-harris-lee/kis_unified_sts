"""Pure tick/field arithmetic shared by probe modules. STDLIB ONLY."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol


class TickLike(Protocol):
    """Anything carrying an exact price increment."""

    size: Decimal


def decimal_field(container: Any, key: str) -> Decimal | None:
    """A numeric broker field as an exact Decimal, or ``None`` if unestablished."""
    if not isinstance(container, dict):
        return None
    raw = container.get(key)
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "")
    if not text:
        return None
    try:
        value = Decimal(text)
    except ArithmeticError:
        return None
    if not value.is_finite():
        return None
    return value


def corroborate_tick(
    quote_output: dict[str, Any], tick: TickLike, fields: tuple[str, ...]
) -> dict[str, Any]:
    """Check the broker's own quoted prices are multiples of the configured tick."""
    observed: dict[str, Any] = {}
    offenders: list[str] = []
    for name in fields:
        value = decimal_field(quote_output, name)
        observed[name] = str(value) if value is not None else None
        if value is not None and value > 0 and value % tick.size != 0:
            offenders.append(f"{name}={value}")
    return {
        "tick_size_points": str(tick.size),
        "broker_quoted_values": observed,
        "non_multiples": offenders,
        "corroborated": not offenders,
        "meaning": (
            "Every positive broker-quoted price above is expected to be an exact "
            "multiple of the registered tick. A non-multiple contradicts the "
            "registry and the resting price must not be snapped to it."
        ),
    }
