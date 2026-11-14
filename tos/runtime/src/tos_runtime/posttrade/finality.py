"""``SyntheticFinalityProducer`` — post-trade finality proof producer for the SYNTHETIC paper"""

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

FULL_FILL_OBLIGATION_ID_PREFIX = "synthetic-fqp-obligation"
FULL_FILL_PROOF_ID_PREFIX = "synthetic-fqp-proof"
NON_EXECUTION_OBLIGATION_ID_PREFIX = "synthetic-fqp-nonexec-obligation"
NON_EXECUTION_PROOF_ID_PREFIX = "synthetic-fqp-nonexec-proof"

_REQUIRED_LEGS: frozenset[ObligationLegDirection] = frozenset(
    {ObligationLegDirection.RECEIPT}
)

_ORDER_FQP_DOES_NOT_PROVE: tuple[str, ...] = tuple(
    dimension.value
    for dimension in FinalityDimensionKind
    if dimension is not FinalityDimensionKind.ORDER_FQP
)

_ELIGIBLE_KINDS: frozenset[EgressResultKind] = frozenset({EgressResultKind.FULL_FILL})

_NON_EXECUTION_KINDS: frozenset[EgressResultKind] = frozenset(
    {
        EgressResultKind.CANCEL_ACK,
        EgressResultKind.EXPIRED,
        EgressResultKind.REJECT,
    }
)


@dataclass(frozen=True)
class FinalityResult:
    """The obligation record + finality proof a producer issued for one result. The same shape"""

    record: EconomicObligationRecord
    proof: PostTradeFinalityProof


SyntheticFinalityResult = FinalityResult


class FinalityProducerPort(Protocol):
    """The narrow read surface :func:`~tos_runtime.engine.finality_projection.project_finality`"""

    def produce(self, payload: EgressResultPayload) -> FinalityResult | None:
        """See :meth:`SyntheticFinalityProducer.produce`'s own docstring."""
        ...


class ReleaseFinalityProducer(FinalityProducerPort, Protocol):
    """What :class:`~tos_runtime.posttrade.release_consumer.FinalityReleaseConsumer` needs off a"""

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
    """Produces a :class:`SyntheticFinalityResult` for a SYNTHETIC-transport ``FULL_FILL`` only."""

    config: FinalityConfig
    scheme: CanonicalizationScheme

    full_fill_obligation_prefix: ClassVar[str] = FULL_FILL_OBLIGATION_ID_PREFIX
    full_fill_proof_prefix: ClassVar[str] = FULL_FILL_PROOF_ID_PREFIX
    non_execution_obligation_prefix: ClassVar[str] = NON_EXECUTION_OBLIGATION_ID_PREFIX
    non_execution_proof_prefix: ClassVar[str] = NON_EXECUTION_PROOF_ID_PREFIX
    obligation_type: ClassVar[str] = "SYNTHETIC_ORDER_FQP"

    def produce(self, payload: EgressResultPayload) -> FinalityResult | None:
        """Build the obligation record + finality proof for one ``EGRESS_RESULT`` payload."""
        if payload.kind not in _ELIGIBLE_KINDS:
            return None
        filled_quantity = payload.filled_quantity
        if filled_quantity is None or filled_quantity <= 0:
            return None
        remaining_quantity = payload.remaining_quantity
        if remaining_quantity is None or remaining_quantity != 0:
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
        """Build a **non-execution** obligation record + finality proof — zero filled, zero"""
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
    """Shared ``ORDER_FQP`` artifact construction — every producer's :meth:`produce`"""
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
