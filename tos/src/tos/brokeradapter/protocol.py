"""The Broker Adapter transport boundary (design #34 §5.1) — Protocol + outbound/result types."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from tos.canonical import CanonicalDecimal, FrozenModel
from tos.engine import (
    AttemptRequest,
    EgressResultPayload,
    InstrumentKey,
)
from tos.ordering import OrderingEvent

__all__ = [
    "OutboundSendRequest",
    "Transport",
]


class OutboundSendRequest(FrozenModel):
    """The verified outbound one transport call carries (design #34 §5.1)."""

    attempt: AttemptRequest
    instrument_key: InstrumentKey
    coordinates: tuple[tuple[str, str | None], ...] = ()
    quantity: CanonicalDecimal | None = None
    price: CanonicalDecimal | None = None
    side: str | None = None
    reference: OrderingEvent = OrderingEvent()
    seal_digest: str | None = None

    def coordinate(self, name: str) -> str | None:
        """Return one opaque coordinate value (``None`` when absent)."""
        for key, value in self.coordinates:
            if key == name:
                return value
        return None


@runtime_checkable
class Transport(Protocol):
    """The injected step-18 transport — **one verified outbound, one result** (design #34 §5.1)."""

    def send_once(
        self,
        attempt: AttemptRequest,
        *,
        instrument_key: InstrumentKey,
        coordinates: tuple[tuple[str, str | None], ...],
        quantity: CanonicalDecimal | None = None,
        price: CanonicalDecimal | None = None,
        side: str | None = None,
        reference: OrderingEvent = OrderingEvent(),
        seal_digest: str | None = None,
    ) -> EgressResultPayload:
        """Transmit the verified outbound exactly once and return the typed result."""
        ...
