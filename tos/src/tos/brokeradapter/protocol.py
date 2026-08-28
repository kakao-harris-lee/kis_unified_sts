"""The Broker Adapter transport boundary (design #34 §5.1) — Protocol + outbound/result types.

RFC-002 §10.8:739 verbatim: "Broker-specific behavior SHALL remain isolated behind the Broker
Adapter boundary." This module *is* that boundary, expressed as a Protocol, and the firewall is
what makes the isolation structural rather than aspirational: ``tos/`` may not import network
stdlib (design #1 §2.3), so any **real** transport implementation is necessarily outside ``tos/``
— in a future runtime holding the credentials and the route. What lives inside ``tos/`` is the
Protocol and a synthetic, network-free implementation of it (:mod:`tos.brokeradapter.synthetic`).

**The single-shot seal (design #34 §5.4/§13).** :class:`Transport` has exactly one method, taking
one attempt and returning one result. There is no retry count, no attempt index, no idempotency
key, no "resend" flag, and no second method — so the two HIGH KIS quirks the existing operational
executor exhibits are **unrepresentable** against this contract:

* ``Q-IDEMP-1`` — ``shared/execution/executor.py:225-232`` resends an order up to three times on
  an exception path where the broker order number is unknown. Against this Protocol there is
  nothing to loop over: a resend is a *new attempt*, and a new attempt needs a new Action Flow
  Permit and a new Egress Currentness Proof, which change the content-addressed attempt identity
  and therefore run the entire 19-step flow again (RFC-005 §11:326-328 "retry is a new send under
  §11.4, not a free repeat").
* ``Q-IDEMP-2`` — ``shared/execution/executor.py:403`` wraps the order POST in a token-expiry
  retry, which cannot exclude a server that accepted the order before replying "expired".
  Authentication is a **separate concern from order transmission** in this contract: the
  Protocol takes no credential and performs no authentication, so a token refresh cannot be
  attached to a send at all. An expiry response is an ``UNKNOWN`` outcome — a missing
  acknowledgement is never a non-acceptance (RFC-005 §11:322-323).

The seam types are deliberately the **engine** ones (design #34 §0.3 — this package carries the
series' narrowest import closure): the attempt is D-E1's ``AttemptRequest``, the result is D-E1's
``EgressResultPayload``, and the egress coordinates cross as **opaque ordered scalars** the
adapter must not interpret. The typed, authoritative coordinate carriers (the egress
``EgressRequestRecord`` / ``EgressCoordinateSet``) stay on the gateway's side of the seam, where
``exact_binding_holds`` runs — the adapter never gets to decide what a coordinate means.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only, and — the load-bearing one for this package —
**no network stdlib whatsoever** (design #34 §0.3/§2.2-①). That canary is the mechanical evidence
for the design's §2 judgement: the real broker path cannot be a ``tos/`` artifact.
"""

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
    """The verified outbound one transport call carries (design #34 §5.1).

    Assembled by an adapter implementation from the scalars the gateway hands across the seam.
    It is a *record of what was asked*, never permission: it carries no credential, no route
    object, no session, and no authority block, because a transport request is data.

    ``coordinates`` are the **opaque ordered** egress coordinates. The adapter may echo them,
    record them, or map them onto a broker's wire format behind the boundary; it may not
    reinterpret their safety meaning, which stays with the gateway's ``exact_binding_holds``.
    """

    attempt: AttemptRequest
    instrument_key: InstrumentKey
    coordinates: tuple[tuple[str, str | None], ...] = ()
    quantity: CanonicalDecimal | None = None
    price: CanonicalDecimal | None = None
    side: str | None = None
    reference: OrderingEvent = OrderingEvent()

    def coordinate(self, name: str) -> str | None:
        """Return one opaque coordinate value (``None`` when absent).

        Args:
            name: The coordinate name.

        Returns:
            The coordinate's opaque value, or ``None`` when the gateway supplied none.
        """
        for key, value in self.coordinates:
            if key == name:
                return value
        return None


@runtime_checkable
class Transport(Protocol):
    """The injected step-18 transport — **one verified outbound, one result** (design #34 §5.1).

    Structurally identical to :class:`tos.egressgw.gateway.SendTransport`; the two are separate
    declarations because the firewall keeps ``tos.egressgw`` and ``tos.brokeradapter`` out of each
    other's import closures (design #34 §0.3), and a Protocol is structural by nature. The test
    suite asserts the two signatures have not drifted.

    Implementations SHALL NOT retry, SHALL NOT authenticate as part of a send, and SHALL NOT
    invent an unbound attempt (RFC-002 §9.1:565/:574). A result whose fate is unknown is reported
    as :attr:`~tos.engine.EgressResultKind.UNKNOWN` or ``TIMEOUT`` — never as a rejection.
    """

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
    ) -> EgressResultPayload:
        """Transmit the verified outbound exactly once and return the typed result.

        Args:
            attempt: The Coordinator's bound attempt request.
            instrument_key: The send's dispatch scope.
            coordinates: The opaque ordered egress coordinates.
            quantity: The authorized order quantity.
            price: The authorized order price.
            side: The authorized side token.
            reference: The event's causal-ordering coordinates.

        Returns:
            The :class:`~tos.engine.EgressResultPayload` for **this exact attempt**.
        """
        ...
