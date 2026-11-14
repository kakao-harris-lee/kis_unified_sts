"""tos.position pure records — the position-observation value substrate (kernel round #4 K-2)."""

from __future__ import annotations

from decimal import Decimal

from tos.canonical import FrozenModel

__all__ = [
    "ConsumedResult",
    "PositionObservation",
    "SealedSend",
]


class PositionObservation(FrozenModel):
    """One (account, instrument) scope's conservative position observation (DR-0003 §2.2 /"""

    scope_key: str
    confirmed_net: Decimal
    unknown_buy: Decimal
    unknown_sell: Decimal
    in_flight_buy: Decimal
    in_flight_sell: Decimal
    attempts_seen: int
    sources: tuple[str, ...] = ()


class SealedSend(FrozenModel):
    """One durably-sealed send's ``(attempt_id, side, quantity)`` (runtime docstring's"""

    attempt_id: str
    side: str | None = None
    quantity: Decimal | None = None


class ConsumedResult(FrozenModel):
    """The LATEST applied (``EGRESS_RESULT_CONSUMED``) result for one attempt — the per-attempt"""

    result_kind: str | None = None
    filled_quantity: Decimal | None = None
    remaining_quantity: Decimal | None = None
