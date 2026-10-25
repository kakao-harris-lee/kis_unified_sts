"""``SyntheticFinalityProducer`` — post-trade finality proof producer for the SYNTHETIC paper
transport only (TOS Phase 3 Wave 2 Lane C-R; plan §2.2).

**Not the producer for a broker fill (PR-3b).** A ``FULL_FILL`` the KIS 모의투자 fill observer read
off the broker gets its proof from :class:`~tos_runtime.posttrade.broker_finality
.BrokerFinalityProducer` instead — same ``ORDER_FQP`` construction (:func:`build_order_fqp_result`,
shared), different ``obligation_type`` and id/idempotency prefixes, so no broker-sourced artifact
is ever labelled ``SYNTHETIC``. Which one a boot uses is decided once in compose
(:mod:`tos_runtime.compose._broker_posttrade_wiring`).

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
from typing import ClassVar, Protocol

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

__all__ = [
    "FULL_FILL_OBLIGATION_ID_PREFIX",
    "FULL_FILL_PROOF_ID_PREFIX",
    "NON_EXECUTION_OBLIGATION_ID_PREFIX",
    "NON_EXECUTION_PROOF_ID_PREFIX",
    "FinalityProducerPort",
    "FinalityResult",
    "ReleaseFinalityProducer",
    "SyntheticFinalityResult",
    "SyntheticFinalityProducer",
    "build_order_fqp_result",
]

#: Idempotency-key / :func:`~tos.canonical.derive_id` namespace prefixes (TOS Phase 5 W2-R
#: independent-review M4 fix, 2026-09-10). :meth:`SyntheticFinalityProducer.produce` and
#: :meth:`~SyntheticFinalityProducer.produce_non_execution` used to share ONE prefix each
#: (``"synthetic-fqp-obligation"``/``"synthetic-fqp-proof"``), so an attempt that legitimately
#: produced BOTH a ``FULL_FILL`` proof (via :meth:`produce`) and a later non-execution proof
#: (via :meth:`produce_non_execution`) would mint COLLIDING ``obligation_id``/``proof_id``
#: content-addressed identities AND collide on ``idempotency_key`` — the later row would
#: silently shadow the earlier one in every idempotency-key-keyed reload
#: (:mod:`tos_runtime.posttrade.release_consumer`'s own ``_reload_proof``/``_reload_obligation``,
#: and :mod:`tos_runtime.recon.evidence_reader`'s ``_attempts_with_finality_proof``). Distinct
#: prefixes make the two artifact families non-collidable by construction; the ``FULL_FILL``
#: prefixes are UNCHANGED literal values (so
#: :mod:`tos_runtime.recon.evidence_reader`'s own already-shipped, disclosed-coupling prefix
#: match keeps working unmodified — it correctly never recognizes a non-execution proof as a
#: Final Quantity Proof for a fill, which it structurally is not).
FULL_FILL_OBLIGATION_ID_PREFIX = "synthetic-fqp-obligation"
FULL_FILL_PROOF_ID_PREFIX = "synthetic-fqp-proof"
NON_EXECUTION_OBLIGATION_ID_PREFIX = "synthetic-fqp-nonexec-obligation"
NON_EXECUTION_PROOF_ID_PREFIX = "synthetic-fqp-nonexec-proof"

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
class FinalityResult:
    """The obligation record + finality proof a producer issued for one result. The same shape
    for the SYNTHETIC producer here and the broker-sourced one
    (:mod:`tos_runtime.posttrade.broker_finality`) — what each one claims is in the artifact
    itself (``obligation_type`` and the id/idempotency prefixes), never in this container.
    """

    record: EconomicObligationRecord
    proof: PostTradeFinalityProof


#: The pre-PR-3b name, kept so existing imports keep working.
SyntheticFinalityResult = FinalityResult


class FinalityProducerPort(Protocol):
    """The narrow read surface :func:`~tos_runtime.engine.finality_projection.project_finality`
    needs off a :class:`SyntheticFinalityProducer` (mypy stage 3 §1.3 rule 3 port
    introduction) — only :meth:`~SyntheticFinalityProducer.produce`, never
    :meth:`~SyntheticFinalityProducer.produce_non_execution` or the producer's own
    config/scheme state."""

    def produce(self, payload: EgressResultPayload) -> FinalityResult | None:
        """See :meth:`SyntheticFinalityProducer.produce`'s own docstring."""
        ...


class ReleaseFinalityProducer(FinalityProducerPort, Protocol):
    """What :class:`~tos_runtime.posttrade.release_consumer.FinalityReleaseConsumer` needs off a
    producer (PR-3b): the non-execution proof, the scope config gate 4 compares against, and the
    four idempotency-key prefixes it re-loads that producer's own rows by. Satisfied by
    :class:`SyntheticFinalityProducer` and by
    :class:`~tos_runtime.posttrade.broker_finality.BrokerFinalityProducer` — the consumer reloads
    exactly the family the producer it was wired with writes, never the other one's."""

    @property
    def config(self) -> FinalityConfig: ...

    full_fill_obligation_prefix: ClassVar[str]
    full_fill_proof_prefix: ClassVar[str]
    non_execution_obligation_prefix: ClassVar[str]
    non_execution_proof_prefix: ClassVar[str]

    def produce_non_execution(
        self, payload: EgressResultPayload
    ) -> FinalityResult | None:
        """See :meth:`SyntheticFinalityProducer.produce_non_execution`."""
        ...


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

    full_fill_obligation_prefix: ClassVar[str] = FULL_FILL_OBLIGATION_ID_PREFIX
    full_fill_proof_prefix: ClassVar[str] = FULL_FILL_PROOF_ID_PREFIX
    non_execution_obligation_prefix: ClassVar[str] = NON_EXECUTION_OBLIGATION_ID_PREFIX
    non_execution_proof_prefix: ClassVar[str] = NON_EXECUTION_PROOF_ID_PREFIX
    #: The ``EconomicObligationRecord.obligation_type`` every artifact of this producer carries.
    obligation_type: ClassVar[str] = "SYNTHETIC_ORDER_FQP"

    def produce(self, payload: EgressResultPayload) -> FinalityResult | None:
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
        return build_order_fqp_result(
            payload,
            config=self.config,
            scheme=self.scheme,
            quantity=filled_quantity,
            obligation_id_prefix=self.full_fill_obligation_prefix,
            proof_id_prefix=self.full_fill_proof_prefix,
            obligation_type=self.obligation_type,
        )

    def produce_non_execution(
        self, payload: EgressResultPayload
    ) -> FinalityResult | None:
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
        return build_order_fqp_result(
            payload,
            config=self.config,
            scheme=self.scheme,
            quantity=Decimal("0"),
            obligation_id_prefix=self.non_execution_obligation_prefix,
            proof_id_prefix=self.non_execution_proof_prefix,
            obligation_type=self.obligation_type,
        )


def build_order_fqp_result(
    payload: EgressResultPayload,
    *,
    config: FinalityConfig,
    scheme: CanonicalizationScheme,
    quantity: Decimal,
    obligation_id_prefix: str,
    proof_id_prefix: str,
    obligation_type: str,
) -> FinalityResult | None:
    """Shared ``ORDER_FQP`` artifact construction — every producer's :meth:`produce`
    (``quantity=filled_quantity``) and ``produce_non_execution`` (``quantity=Decimal("0")``).
    Every gate/leg convention is identical across callers; only the asserted magnitude, the
    id/idempotency-key namespace (module docstring's M4 fix — distinct prefixes so artifact
    families never collide) and the declared ``obligation_type`` differ.
    """
    account = payload.instrument_key.account
    leg_scope = ObligationLegScope(
        leg=ObligationLegDirection.RECEIPT,
        account=account,
        currency=config.currency,
        value_date=config.value_date,
        source_revision=config.source_revision,
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
        obligation_id_prefix,
        scheme.compute_digest(
            {"attempt_id": payload.attempt_id, "instrument_key": account}
        ),
    )
    proof_id = derive_id(
        proof_id_prefix,
        scheme.compute_digest({"obligation_id": obligation_id}),
    )

    record = EconomicObligationRecord.issue(
        scheme=scheme,
        status=ArtifactStatus.ISSUED,
        obligation_id=obligation_id,
        obligation_type=obligation_type,
        obligation_version="1",
        obligation_generation=0,
        idempotency_key=f"{obligation_id_prefix}:{payload.attempt_id}",
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
        scheme=scheme,
        status=ArtifactStatus.ISSUED,
        proof_id=proof_id,
        obligation_ref=record.obligation_id,
        obligation_version=record.obligation_version,
        leg_scope=leg_scope,
        amount=quantity,
        finality_class=FinalityDimensionKind.ORDER_FQP,
        bound_generation=record.obligation_generation,
        does_not_prove=_ORDER_FQP_DOES_NOT_PROVE,
        proof_recipe_id=config.proof_recipe_id,
        source_revision=config.source_revision,
        idempotency_key=f"{proof_id_prefix}:{payload.attempt_id}",
    )
    assert isinstance(proof, PostTradeFinalityProof)

    if not finality_proof_class_specific(proof):
        return None

    return FinalityResult(record=record, proof=proof)
