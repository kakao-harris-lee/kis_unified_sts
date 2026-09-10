"""``SyntheticFinalityProducer`` — post-trade finality proof producer for the SYNTHETIC paper
transport only (TOS Phase 3 Wave 2 Lane C-R; plan §2.2).

**SYNTHETIC only, quantity-only (honest disclosure).** This runtime's ``EgressResultPayload``
(``tos.engine.records``) carries an instrument key, an attempt id, a result ``kind``, and — for
a fill — ``filled_quantity``/``remaining_quantity``. It carries **no price, no amount, and no
side (buy/sell)**. This producer therefore claims exactly ONE :class:`~tos.posttrade.vocabulary
.FinalityDimensionKind`: ``ORDER_FQP`` — "broker-order final cumulative filled quantity and zero
remaining executable quantity" (ADR-002-030 §12 line 338; §1 line 23) — which is precisely what a
``FULL_FILL`` result proves and precisely what CPL-2 (ADR-002-005 §10) requires before a
reservation may reach ``RELEASED``. It never claims ``TRADE_CAPTURE``, ``SETTLEMENT``,
``CASH_AVAILABILITY``, or any of the other eight dimensions (ADR §12 line 340-345,
:data:`~tos.posttrade.vocabulary.FQP_DOES_NOT_PROVE`) — those require real broker/statement
evidence and are Phase 5 reconciliation work, never fabricated here.

The one :class:`~tos.posttrade.records.ObligationLeg` this producer ever asserts is
``RECEIPT`` with a magnitude of the exact ``filled_quantity`` — a quantity-denominated leg needs
no price. This is this producer's own declared "obligation class" (the applicable required-leg
set is caller-injected per :func:`~tos.posttrade.predicates.obligation_leg_set_complete`'s own
docstring: "the package deliberately publishes no default required set"), not a claim that a real
economic obligation record for this fill would only ever carry a ``RECEIPT`` leg — a real cash/
settlement leg is exactly the kind of claim §1 line 23 forbids ORDER_FQP from making, and this
producer never makes it.

**The release call site (TOS Phase 5 W2-R; plan §10 row ①).** This module only produces the
:class:`~tos.posttrade.records.PostTradeFinalityProof`; wiring it as a reservation's
``finality_witness`` is :mod:`tos_runtime.rcl.finality_witness`'s seam, exercised end-to-end
against the real :class:`~tos_runtime.rcl.log.SqliteCommitLog` in
``tos/runtime/tests/rcl/test_finality_witness.py``. :mod:`tos_runtime.posttrade.release_consumer`
is the ONE production call site that reaches an ``apply_reservation_transition`` call to a
``RELEASED``/``POSITION_CONSUMED`` destination — this module (:meth:`SyntheticFinalityProducer
.produce`/:meth:`~SyntheticFinalityProducer.produce_non_execution`) still only ever builds the
proof artifact, never decides whether or when to release.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``pydantic``
(transitively) + ``tos.canonical``/``tos.engine.records``/``tos.engine.vocabulary``/
``tos.posttrade`` + ``tos_runtime.posttrade.config`` only. No ``shared.*``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from tos.canonical import CanonicalizationScheme, derive_id
from tos.engine.records import EgressResultPayload
from tos.engine.vocabulary import EgressResultKind
from tos.posttrade import (
    ArtifactStatus,
    EconomicObligationRecord,
    FinalityDimensionKind,
    ObligationLeg,
    ObligationLegDirection,
    ObligationLegScope,
    PostTradeFinalityProof,
    PostTradeObligationLifecycleState,
    finality_dimensions_orthogonal,
    finality_proof_class_specific,
    obligation_leg_set_complete,
)

from tos_runtime.posttrade.config import FinalityConfig

__all__ = ["SyntheticFinalityResult", "SyntheticFinalityProducer"]

#: The one obligation leg this SYNTHETIC producer ever asserts — see module docstring.
_REQUIRED_LEGS: frozenset[ObligationLegDirection] = frozenset(
    {ObligationLegDirection.RECEIPT}
)

#: What an ``ORDER_FQP`` proof does NOT establish (ADR §12 line 340-345,
#: :data:`~tos.posttrade.vocabulary.FQP_DOES_NOT_PROVE`) — every other finality dimension, named
#: explicitly rather than left implicit so a later ``FinalityDimensionKind`` addition is picked
#: up automatically.
_ORDER_FQP_DOES_NOT_PROVE: tuple[str, ...] = tuple(
    dimension.value
    for dimension in FinalityDimensionKind
    if dimension is not FinalityDimensionKind.ORDER_FQP
)

#: Result kinds this producer ever considers. Every other kind — ``PARTIAL_FILL`` (remaining
#: quantity is by construction still live, RFC-005 §11), ``CANCEL_ACK``/``EXPIRED`` (CPL-4: a
#: cancel/expiry is not a release), ``ACK``/``REJECT``/``UNKNOWN``/``TIMEOUT`` — yields no proof.
_ELIGIBLE_KINDS: frozenset[EgressResultKind] = frozenset({EgressResultKind.FULL_FILL})

#: TOS Phase 5 W2-R (plan §10 row ①): the three kinds :meth:`SyntheticFinalityProducer
#: .produce_non_execution` ever considers — a non-execution FQP (zero filled, zero remaining) is
#: the CPL-4-honest declaration that this attempt executed nothing at all, not a release of a
#: fill (that stays :meth:`produce`'s own job). ``ACK``/``PARTIAL_FILL``/``UNKNOWN``/``TIMEOUT``
#: are never eligible: an ``ACK``/``PARTIAL_FILL`` attempt may still fill later, and
#: ``UNKNOWN``/``TIMEOUT`` carry no positive knowledge that nothing executed (RFC-005 §11
#: "timeout = UNKNOWN, never rejection") — a non-execution proof for either would assert
#: knowledge this runtime does not have.
_NON_EXECUTION_KINDS: frozenset[EgressResultKind] = frozenset(
    {
        EgressResultKind.CANCEL_ACK,
        EgressResultKind.EXPIRED,
        EgressResultKind.REJECT,
    }
)


@dataclass(frozen=True)
class SyntheticFinalityResult:
    """The obligation record + finality proof this producer issued for one ``FULL_FILL``."""

    record: EconomicObligationRecord
    proof: PostTradeFinalityProof


@dataclass(frozen=True)
class SyntheticFinalityProducer:
    """Produces a :class:`SyntheticFinalityResult` for a SYNTHETIC-transport ``FULL_FILL`` only.

    Every non-``FULL_FILL`` result — most of all a ``PARTIAL_FILL`` (remaining quantity still
    live), ``CANCEL_ACK``, or ``EXPIRED`` (CPL-4 "cancel is not release") — yields ``None``, never
    a proof. Even for a ``FULL_FILL`` a proof is issued only when the built artifacts actually
    pass the kernel's own gates (:func:`~tos.posttrade.predicates.obligation_leg_set_complete`,
    :func:`~tos.posttrade.predicates.finality_dimensions_orthogonal`,
    :func:`~tos.posttrade.predicates.finality_proof_class_specific`).

    **Independent review finding #6 (2026-09-09), corrected here.** The ``FULL_FILL``-only
    restriction used to be producer-LOCAL (the ``_ELIGIBLE_KINDS`` membership check alone) —
    none of the three kernel gates above actually assert ``payload.remaining_quantity == 0`` for
    the leg this producer's own ``ORDER_FQP`` claim asserts ("zero remaining executable
    quantity", ADR-002-030 §12 line 338). Today ``tos.engine.records.EgressResultPayload``'s own
    validator already refuses to construct a ``FULL_FILL``-kind payload with a nonzero
    ``remaining_quantity`` at all (structural derivation, RFC-005 §11), so this producer's
    ``_ELIGIBLE_KINDS`` check alone happens to be safe FOR TODAY's one-member set — but nothing
    that gate calls re-checks the magnitude, so a future edit widening ``_ELIGIBLE_KINDS`` (e.g.
    the reviewer's own mutation, adding ``PARTIAL_FILL``) would have produced a full "zero
    remaining" proof for a fill that still has quantity outstanding. :meth:`produce` now checks
    ``payload.remaining_quantity == 0`` and ``payload.filled_quantity`` present and positive
    directly against the PAYLOAD, before any kernel gate runs — this producer's own ``ORDER_FQP``
    claim is enforced structurally here too, not only inferred from ``_ELIGIBLE_KINDS``
    membership.
    """

    config: FinalityConfig
    scheme: CanonicalizationScheme

    def produce(self, payload: EgressResultPayload) -> SyntheticFinalityResult | None:
        """Build the obligation record + finality proof for one ``EGRESS_RESULT`` payload.

        Args:
            payload: The re-injected ``EGRESS_RESULT`` payload (``tos.engine.records
                .EgressResultPayload``) the driver just applied.

        Returns:
            A :class:`SyntheticFinalityResult`, or ``None`` when ``payload.kind`` is not
            ``FULL_FILL``, when ``filled_quantity`` is absent or not positive, when
            ``remaining_quantity`` is absent or nonzero (independent review finding #6 — the
            positive precondition this producer's own ``ORDER_FQP`` claim requires), or when the
            built artifacts fail any of the three kernel gates named on this class's own
            docstring.
        """
        if payload.kind not in _ELIGIBLE_KINDS:
            return None
        filled_quantity = payload.filled_quantity
        if filled_quantity is None or filled_quantity <= 0:
            return None
        remaining_quantity = payload.remaining_quantity
        if remaining_quantity is None or remaining_quantity != 0:
            # Independent review finding #6: a FULL_FILL kind alone does not prove "zero
            # remaining executable quantity" — the ORDER_FQP claim itself does, so it is
            # checked directly against the payload, not inferred from the kind.
            return None
        return self._build_synthetic_result(payload, quantity=filled_quantity)

    def produce_non_execution(
        self, payload: EgressResultPayload
    ) -> SyntheticFinalityResult | None:
        """Build a **non-execution** obligation record + finality proof — zero filled, zero
        remaining — for a ``CANCEL_ACK``/``EXPIRED``/``REJECT`` result (TOS Phase 5 W2-R; plan
        §10 row ①).

        The CPL-4-honest declaration that this attempt executed nothing at all: the ``RECEIPT``
        leg's magnitude is asserted as exactly ``Decimal("0")``, never read off the payload —
        ``EgressResultPayload``'s own validator already refuses a ``CANCEL_ACK``/``EXPIRED``/
        ``REJECT`` payload that carries any fill magnitude at all (``tos.engine.records``'
        ``_fill_shape_consistent``), so "zero executed" is this method's own structural claim
        about what these three kinds mean, not an inference from a field that cannot legally be
        present.

        **This method never decides whether zero-execution is actually TRUE for this attempt —
        it only builds the artifact.** :mod:`tos_runtime.posttrade.release_consumer`'s
        :class:`~tos_runtime.posttrade.release_consumer.FinalityReleaseConsumer` is the ONLY
        caller, and it calls this method only AFTER a three-way reconciliation report
        corroborates non-execution (plan §3 "주문 응답으로 finality 판정" is a rejected
        alternative) — a response payload alone must never produce a proof this cheaply.

        Args:
            payload: The re-injected ``EGRESS_RESULT`` payload.

        Returns:
            A :class:`SyntheticFinalityResult`, or ``None`` when ``payload.kind`` is not one of
            ``CANCEL_ACK``/``EXPIRED``/``REJECT``, or when the built artifacts fail any of the
            three kernel gates named on this class's own docstring.
        """
        if payload.kind not in _NON_EXECUTION_KINDS:
            return None
        return self._build_synthetic_result(payload, quantity=Decimal("0"))

    def _build_synthetic_result(
        self, payload: EgressResultPayload, *, quantity: Decimal
    ) -> SyntheticFinalityResult | None:
        """Shared artifact construction for :meth:`produce` (``quantity=filled_quantity``) and
        :meth:`produce_non_execution` (``quantity=Decimal("0")``) — every gate/leg/idempotency-
        key convention stays identical between the two, only the asserted magnitude differs.
        """
        account = payload.instrument_key.account
        leg_scope = ObligationLegScope(
            leg=ObligationLegDirection.RECEIPT,
            account=account,
            currency=self.config.currency,
            value_date=self.config.value_date,
            source_revision=self.config.source_revision,
            finality_class=FinalityDimensionKind.ORDER_FQP,
        )
        leg = ObligationLeg(
            direction=ObligationLegDirection.RECEIPT,
            magnitude=quantity,
            scope=leg_scope,
        )
        leg_magnitudes = {ObligationLegDirection.RECEIPT: quantity}

        if not obligation_leg_set_complete(
            required_legs=_REQUIRED_LEGS,
            present_legs=frozenset({ObligationLegDirection.RECEIPT}),
            leg_magnitudes=leg_magnitudes,
        ):
            return None

        proof_present = {FinalityDimensionKind.ORDER_FQP: True}
        if not finality_dimensions_orthogonal(
            FinalityDimensionKind.ORDER_FQP, proof_present
        ):
            return None

        obligation_id = derive_id(
            "synthetic-fqp-obligation",
            self.scheme.compute_digest(
                {"attempt_id": payload.attempt_id, "instrument_key": account}
            ),
        )
        proof_id = derive_id(
            "synthetic-fqp-proof",
            self.scheme.compute_digest({"obligation_id": obligation_id}),
        )

        record = EconomicObligationRecord.issue(
            scheme=self.scheme,
            status=ArtifactStatus.ISSUED,
            obligation_id=obligation_id,
            obligation_type="SYNTHETIC_ORDER_FQP",
            obligation_version="1",
            obligation_generation=0,
            idempotency_key=f"synthetic-fqp-obligation:{payload.attempt_id}",
            source_event_ids=(payload.attempt_id,),
            account_scope=account,
            instrument_identity=payload.instrument_key.instrument,
            quantity=quantity,
            legs=(leg,),
            leg_magnitudes=leg_magnitudes,
            lifecycle_state=PostTradeObligationLifecycleState.FINALITY_PROVEN,
            finality_proof_refs=(proof_id,),
        )
        assert isinstance(record, EconomicObligationRecord)

        proof = PostTradeFinalityProof.issue(
            scheme=self.scheme,
            status=ArtifactStatus.ISSUED,
            proof_id=proof_id,
            obligation_ref=record.obligation_id,
            obligation_version=record.obligation_version,
            leg_scope=leg_scope,
            amount=quantity,
            finality_class=FinalityDimensionKind.ORDER_FQP,
            bound_generation=record.obligation_generation,
            does_not_prove=_ORDER_FQP_DOES_NOT_PROVE,
            proof_recipe_id=self.config.proof_recipe_id,
            source_revision=self.config.source_revision,
            idempotency_key=f"synthetic-fqp-proof:{payload.attempt_id}",
        )
        assert isinstance(proof, PostTradeFinalityProof)

        if not finality_proof_class_specific(proof):
            return None

        return SyntheticFinalityResult(record=record, proof=proof)
