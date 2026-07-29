"""The synthetic paper transport (design #34 §5.2) — network 0, credentials 0, route 0.

This is what the slice actually executes. Design #34 §2 makes it the honest send boundary for
slice #1, on the **broker-reached / synthetic** axis rather than the live / non-live one:

* ① the firewall forbids network stdlib inside ``tos/``, so a real broker transport is
  necessarily located outside ``tos/`` — the firewall bounds *where* it can live;
* ② a real paper-account API call is a **broker-resource-consuming** transmission (it creates a
  mock order on a broker's server), so RFC-002 §10.8:741 triggers the full verify list for it,
  and the deferred safety-governance mesh plus the P0-2-blocked profile make the required facts
  unverifiable ⇒ §10.8:761 rejection. That is what actually stops the real-paper option from
  executing, and the gateway enforces it rather than this module asserting it.

A synthetic transport is the **other side** of that axis, not a way around it: it consumes no
broker resource, holds no credential, and reaches no route, so the gateway's broker-applicability
gate can positively establish it — with structural corroboration from the credential-route
inventory, never from this class's say-so.

**Deterministic by construction.** The fill band is a pure function of the injected
:class:`SyntheticFillPolicy` and the authorized quantity: no clock, no RNG, no ambient state. Two
runs over the same inputs produce byte-identical results, which is what makes the transport usable
as the D-E3 backtest fill model's structural twin (design #34 §5.2 — same Protocol, different
injection).

**Structurally derived outcome.** The fill / partial distinction follows the **magnitudes**, not a
declared label (구조 파생 > 자기신고), mirroring D-E1's own ``EgressResultPayload`` shape validator
(``engine/records.py:221-229``): a remaining quantity above zero is a ``PARTIAL_FILL`` and cannot
be recorded as a ``FULL_FILL``. The already-filled part is never re-requested (RFC-005 §11:338-339,
§6:176-178).

⚠ **NON-AUTHORITATIVE.** A result from this transport is not evidence that any broker accepted
anything, because no broker was contacted. It closes no EV and it establishes no currentness,
capability, or capacity fact (design #34 §1.1/§2.4).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only; **no network stdlib, no clock, no RNG**.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from pydantic import model_validator

from tos.brokeradapter.protocol import OutboundSendRequest
from tos.canonical import ArtifactIntegrityError, CanonicalDecimal, FrozenModel
from tos.engine import (
    AttemptRequest,
    EgressResultKind,
    EgressResultPayload,
    InstrumentKey,
)
from tos.ordering import OrderingEvent

__all__ = [
    "NON_FILL_DECLARABLE_KINDS",
    "SyntheticFillPolicy",
    "SyntheticPaperTransport",
    "synthetic_transport_nature_fields",
]


#: The outcomes an injected policy may declare outright, because they are *not* derived from a
#: fill magnitude: an acknowledgement with no fill, a broker rejection, and the two genuinely
#: unknown fates. ``FULL_FILL`` / ``PARTIAL_FILL`` are deliberately **absent** — those two are
#: derived from the magnitudes and can never be declared (구조 파생 > 자기신고).
#: The **pinned** arithmetic context the fill band runs under (adversarial review NIT-1), the
#: symmetric twin of ``tos.egressgw.construction.DERIVATION_CONTEXT``. ``decimal`` arithmetic
#: reads an ambient per-thread context; a fresh :class:`~decimal.Context` makes the band a pure
#: function of its declared arguments, which is what lets this transport stand in for the D-E3
#: fill model (design #34 §5.2).
FILL_CONTEXT: Context = Context(prec=28, rounding=ROUND_HALF_EVEN)

NON_FILL_DECLARABLE_KINDS: frozenset[EgressResultKind] = frozenset(
    {
        EgressResultKind.ACK,
        EgressResultKind.REJECT,
        EgressResultKind.UNKNOWN,
        EgressResultKind.TIMEOUT,
    }
)


class SyntheticFillPolicy(FrozenModel):
    """The injected, deterministic paper fill band (design #34 §5.2).

    Exactly one of two modes, and the validator forbids both at once:

    * a **declared non-fill outcome** (``declared_kind`` in :data:`NON_FILL_DECLARABLE_KINDS`) —
      how a scenario asks for an acknowledgement, a rejection, or one of the two unknown fates;
    * a **fill band** (``fill_numerator`` / ``fill_denominator`` over the authorized quantity,
      floored to ``lot_size``) — from which the kind is *derived*, never declared.

    The band is expressed as an exact integer ratio rather than a float so the arithmetic is
    exact and reproducible across processes (no binary-float variation — ADR-002-020 §11:301).

    ⚠ This band models nothing about real market microstructure. Cost realism, queue position,
    and the differential oracle are **D-E3's** (design #34 §5.2/§8.3); this exists so the send
    boundary has a deterministic counterparty, not so anyone can estimate a fill.
    """

    declared_kind: EgressResultKind | None = None
    fill_numerator: int | None = None
    fill_denominator: int | None = None
    lot_size: CanonicalDecimal | None = None

    @model_validator(mode="after")
    def _exactly_one_mode(self) -> SyntheticFillPolicy:
        """Reject a policy that declares both modes, neither, or a derivable kind."""
        has_band = self.fill_numerator is not None or self.fill_denominator is not None
        if self.declared_kind is not None:
            if self.declared_kind not in NON_FILL_DECLARABLE_KINDS:
                raise ArtifactIntegrityError(
                    f"SyntheticFillPolicy.declared_kind={self.declared_kind.value} is a fill "
                    "kind — a fill / partial-fill outcome is DERIVED from the magnitudes and "
                    "may never be declared (구조 파생 > 자기신고; RFC-005 §11:338-339)"
                )
            if has_band:
                raise ArtifactIntegrityError(
                    "SyntheticFillPolicy declares both an outcome and a fill band — a policy "
                    "with two modes has no single deterministic answer"
                )
            return self
        if self.fill_numerator is None or self.fill_denominator is None:
            raise ArtifactIntegrityError(
                "SyntheticFillPolicy declares neither an outcome nor a complete fill band — an "
                "undetermined transport is not a transport (fail-closed)"
            )
        if self.fill_denominator <= 0:
            raise ArtifactIntegrityError(
                "SyntheticFillPolicy.fill_denominator must be positive"
            )
        if self.fill_numerator < 0 or self.fill_numerator > self.fill_denominator:
            raise ArtifactIntegrityError(
                "SyntheticFillPolicy.fill_numerator must lie in [0, fill_denominator]"
            )
        if self.lot_size is None or self.lot_size <= 0:
            raise ArtifactIntegrityError(
                "SyntheticFillPolicy.lot_size must be a positive injected lot — a fill is "
                "floored to whole lots, never silently rounded"
            )
        return self


def synthetic_transport_nature_fields() -> dict[str, bool]:
    """The three negative-polarity nature flags a synthetic transport can honestly declare.

    Returned as a plain mapping (not a ``TransportNature``) because
    :class:`~tos.egressgw.records.TransportNature` lives in ``tos.egressgw``, which this package
    does not import (design #34 §0.3 closure). A caller wires these into the gateway's context
    together with the **principal** — and the gateway still refuses to take the declaration at
    face value: it requires structural corroboration from the credential-route inventory
    (design #34 §4.2).

    Returns:
        ``reaches_broker`` / ``credential_bearing`` / ``route_bearing``, each ``False``.
    """
    return {
        "reaches_broker": False,
        "credential_bearing": False,
        "route_bearing": False,
    }


class SyntheticPaperTransport:
    """A deterministic, network-free paper transport (design #34 §5.2).

    Holds **no** credential, **no** session, **no** route, and opens **no** socket: the class has
    no such attribute to hold one in, which is the same constructive-absence discipline the
    sibling kernels use for "there is no transmit method". Its only method is the single-shot
    :meth:`send_once`, so a retry loop cannot be written against it.

    ``requests`` retains what was asked, in order, so a test can assert that exactly one call was
    made for one attempt — the mechanical form of "no blind resubmission".
    """

    def __init__(self, policy: SyntheticFillPolicy) -> None:
        """Configure the transport with its injected deterministic fill policy.

        Args:
            policy: The injected :class:`SyntheticFillPolicy`.
        """
        self._policy = policy
        self.requests: tuple[OutboundSendRequest, ...] = ()

    @property
    def policy(self) -> SyntheticFillPolicy:
        """The injected fill policy."""
        return self._policy

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
        """Produce the deterministic result for exactly one verified outbound.

        The result's ``attempt_id`` is **always** the attempt's own: a transport can never
        transition a reservation other than the one it was handed (design #31 §2.1(ii)).

        Args:
            attempt: The Coordinator's bound attempt request.
            instrument_key: The send's dispatch scope.
            coordinates: The opaque ordered egress coordinates.
            quantity: The authorized order quantity.
            price: The authorized order price.
            side: The authorized side token.
            reference: The event's causal-ordering coordinates.

        Returns:
            The :class:`~tos.engine.EgressResultPayload` for this exact attempt.
        """
        request = OutboundSendRequest(
            attempt=attempt,
            instrument_key=instrument_key,
            coordinates=coordinates,
            quantity=quantity,
            price=price,
            side=side,
            reference=reference,
        )
        self.requests += (request,)
        if self._policy.declared_kind is not None:
            return EgressResultPayload(
                instrument_key=instrument_key,
                attempt_id=attempt.attempt_id,
                kind=self._policy.declared_kind,
                reference=reference,
            )
        if quantity is None or not quantity.is_finite() or quantity <= 0:
            # No authorized magnitude to fill against. This is not a rejection — nothing was
            # established about a broker's disposition — so the honest report is UNKNOWN
            # (RFC-005 §11:322-323 missing acknowledgement != not accepted).
            return EgressResultPayload(
                instrument_key=instrument_key,
                attempt_id=attempt.attempt_id,
                kind=EgressResultKind.UNKNOWN,
                reference=reference,
            )
        filled = self._filled_quantity(quantity)
        remaining = quantity - filled
        if filled <= 0:
            return EgressResultPayload(
                instrument_key=instrument_key,
                attempt_id=attempt.attempt_id,
                kind=EgressResultKind.ACK,
                reference=reference,
            )
        # ★ structural derivation: the kind follows the magnitudes, never a label.
        kind = (
            EgressResultKind.PARTIAL_FILL
            if remaining > 0
            else EgressResultKind.FULL_FILL
        )
        return EgressResultPayload(
            instrument_key=instrument_key,
            attempt_id=attempt.attempt_id,
            kind=kind,
            filled_quantity=filled,
            remaining_quantity=remaining,
            reference=reference,
        )

    def _filled_quantity(self, quantity: Decimal) -> Decimal:
        """The exact, lot-floored filled magnitude for ``quantity`` (pure integer ratio math)."""
        numerator = self._policy.fill_numerator
        denominator = self._policy.fill_denominator
        lot = self._policy.lot_size
        assert numerator is not None  # narrowed by the policy validator
        assert denominator is not None
        assert lot is not None
        with localcontext(FILL_CONTEXT):
            raw = (quantity * Decimal(numerator)) / Decimal(denominator)
            return (raw // lot) * lot
