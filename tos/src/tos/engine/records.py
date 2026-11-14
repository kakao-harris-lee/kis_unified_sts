"""Engine models — events, injected coordinates, stage verdicts, the attempt request, evidence."""

from __future__ import annotations

import re

from pydantic import Field, model_validator

from tos.capsule import DecisionContextCapsule
from tos.dsl import (
    WILDCARD_TOKENS,
    AuthoredStrategy,
    ContextValueView,
    EvaluationConfig,
    Proposal,
)
from tos.engine._base import (
    AllFalseCoordinatorAuthority,
    ArtifactIntegrityError,
    CanonicalDecimal,
    CanonicalizationScheme,
    FrozenModel,
    derive_id,
)
from tos.engine.vocabulary import (
    FILL_RESULT_KINDS,
    CommitmentStep,
    EgressKnowledge,
    EgressResultKind,
    EventKind,
    EvidenceKind,
    HaltReason,
    ResultDisposition,
    StageAuthorityClass,
    StageOutcome,
    UnsentDiscardReason,
)
from tos.ordering import OrderingEvent
from tos.rcl import CapacityState
from tos.time import HealthState, SessionContext, UncertaintyInterval

__all__ = [
    "ATTEMPT_ID_PREFIX",
    "EVENT_ID_PREFIX",
    "AttemptRequest",
    "DecisionTickPayload",
    "EgressResultOutcome",
    "EgressResultPayload",
    "EngineConfiguration",
    "EngineEvent",
    "EngineEvidenceRecord",
    "InstrumentKey",
    "ProvisionalReservation",
    "RegisteredStrategy",
    "SendHandoff",
    "StageRequest",
    "StageVerdict",
    "TimeAdmissionInputs",
    "UnsentDiscardRef",
    "egress_result_outcome_digest",
    "event_identity",
]

ATTEMPT_ID_PREFIX = "attempt"

EVENT_ID_PREFIX = "event"


def _is_wildcard_scope(value: str) -> bool:
    """Whether a scope token is a wildcard / "latest" (RFC-003 §9:279-283 dispatch mirror)."""
    if value in WILDCARD_TOKENS:
        return True
    return "*" in value or value.lower() == "latest"


class InstrumentKey(FrozenModel):
    """The structurally derived (account, instrument) dispatch key (design #31 §3.3 / D2)."""

    account: str
    instrument: str

    @model_validator(mode="after")
    def _scope_is_concrete_and_wildcard_free(self) -> InstrumentKey:
        """Reject an empty or wildcard scope component (fail-closed key derivation)."""
        for name in ("account", "instrument"):
            value: str = getattr(self, name)
            if not value.strip():
                raise ArtifactIntegrityError(
                    f"InstrumentKey.{name} must be a concrete non-empty scope — an unkeyable "
                    "strategy is not dispatchable (design #31 §3.3)"
                )
            if _is_wildcard_scope(value):
                raise ArtifactIntegrityError(
                    f"InstrumentKey.{name} must not be a wildcard/'latest' scope "
                    "(RFC-003 §9:279-283 dispatch-layer mirror; design #31 §3.3)"
                )
        return self


class TimeAdmissionInputs(FrozenModel):
    """The injected time coordinates the §2.3 freshness gate consumes — never a clock read."""

    source_age: int | None = None
    delay_bounds: tuple[int | None, ...] = ()
    max_age_bound: int | None = None
    future_tolerance: int | None = None
    snapshot_age_bound: int | None = None
    maximum_consumer_age_ms: int | None = None
    session_context: SessionContext | None = None
    uncertainty_interval: UncertaintyInterval | None = None
    health_state: HealthState | None = None


class DecisionTickPayload(FrozenModel):
    """A ``DECISION_TICK`` payload (design #31 §2.2)."""

    instrument_key: InstrumentKey
    capsule: DecisionContextCapsule
    time: TimeAdmissionInputs = TimeAdmissionInputs()
    reference: OrderingEvent = OrderingEvent()
    value_view: ContextValueView | None = None


def _omit_when_none(value: object) -> bool:
    """``exclude_if`` predicate for fields added after records of their type were already"""
    return value is None


_TRADING_DATE_SHAPE = re.compile(r"[0-9]{8}")


def _check_trading_date(value: str | None, owner: str) -> None:
    """An injected KST trading-date token is ``YYYYMMDD`` digits or ``None`` — the kernel is"""
    if value is not None and _TRADING_DATE_SHAPE.fullmatch(value) is None:
        raise ArtifactIntegrityError(
            f"{owner}.trading_date must be YYYYMMDD digits or None, got {value!r}"
        )


class EgressResultPayload(FrozenModel):
    """An ``EGRESS_RESULT`` payload re-injected from the D-E4 send boundary (design #31 §2.2)."""

    instrument_key: InstrumentKey
    attempt_id: str
    kind: EgressResultKind
    filled_quantity: CanonicalDecimal | None = None
    remaining_quantity: CanonicalDecimal | None = None
    broker_execution_id: str | None = None
    resolution_generation: int | None = None
    reference: OrderingEvent = OrderingEvent()
    trading_date: str | None = Field(default=None, exclude_if=_omit_when_none)

    @model_validator(mode="after")
    def _fill_shape_consistent(self) -> EgressResultPayload:
        """Enforce magnitude/kind consistency — partial stays partial (RFC-005 §11:338-339)."""
        _check_trading_date(self.trading_date, "EgressResultPayload")
        if not self.attempt_id.strip():
            raise ArtifactIntegrityError(
                "EgressResultPayload.attempt_id must be concrete — a result with no attempt "
                "identity cannot be applied to any reservation (design #31 §2.1(ii))"
            )
        if self.kind not in FILL_RESULT_KINDS:
            if self.filled_quantity is not None or self.remaining_quantity is not None:
                raise ArtifactIntegrityError(
                    f"EgressResultPayload kind={self.kind} must carry no fill magnitude — only "
                    f"{sorted(FILL_RESULT_KINDS)} do (design #31 §2.2)"
                )
            return self
        if self.filled_quantity is None or self.remaining_quantity is None:
            raise ArtifactIntegrityError(
                f"EgressResultPayload kind={self.kind} requires both filled_quantity and "
                "remaining_quantity — an unquantified fill is not a fill (RFC-005 §11:338-339)"
            )
        if self.filled_quantity <= 0:
            raise ArtifactIntegrityError(
                f"EgressResultPayload kind={self.kind} requires a positive filled_quantity"
            )
        if self.remaining_quantity < 0:
            raise ArtifactIntegrityError(
                "EgressResultPayload.remaining_quantity must not be negative"
            )
        partial_by_magnitude = self.remaining_quantity > 0
        declared_partial = self.kind is EgressResultKind.PARTIAL_FILL
        if partial_by_magnitude != declared_partial:
            raise ArtifactIntegrityError(
                "declared fill kind contradicts the magnitudes — a remaining quantity > 0 is a "
                "PARTIAL_FILL and must not be recorded as a FULL_FILL (RFC-005 §11:338-339; "
                "구조 파생 > 자기신고)"
            )
        return self


class EngineEvent(FrozenModel):
    """One event of the closed vocabulary (design #31 §2.2)."""

    kind: EventKind
    decision_tick: DecisionTickPayload | None = None
    egress_result: EgressResultPayload | None = None
    corporate_action: None = None

    @model_validator(mode="after")
    def _payload_matches_kind(self) -> EngineEvent:
        """Reject an event whose payload does not match its kind (fail-closed)."""
        fields = ("decision_tick", "egress_result", "corporate_action")
        expected = {
            EventKind.DECISION_TICK: "decision_tick",
            EventKind.EGRESS_RESULT: "egress_result",
        }[self.kind]
        if getattr(self, expected) is None:
            raise ArtifactIntegrityError(
                f"EngineEvent kind={self.kind} requires a {expected} payload"
            )
        for other in fields:
            if other == expected:
                continue
            if getattr(self, other) is not None:
                raise ArtifactIntegrityError(
                    f"EngineEvent kind={self.kind} must not carry a {other} payload"
                )
        return self

    def payload(
        self,
    ) -> DecisionTickPayload | EgressResultPayload:
        """Return the single payload ``_payload_matches_kind`` guarantees is present."""
        if self.decision_tick is not None:
            return self.decision_tick
        if self.egress_result is not None:
            return self.egress_result
        raise ArtifactIntegrityError("EngineEvent carries no payload (fail-closed)")

    def reference(self) -> OrderingEvent:
        """Return the event's causal-ordering coordinates (design #31 §2.1(ii))."""
        return self.payload().reference

    def instrument_key(self) -> InstrumentKey:
        """Return the event's bound instrument key."""
        return self.payload().instrument_key


def event_identity(event: EngineEvent, *, scheme: CanonicalizationScheme) -> str:
    """The content-addressed identity of one engine event (Phase 3 A-K-1; design #31 §2.1(ii))."""
    return derive_id(
        EVENT_ID_PREFIX, scheme.compute_digest(event.model_dump(mode="json"))
    )


class StageVerdict(FrozenModel):
    """A stage's native verdict wrapped as a positive-admit judgement (design #31 §4.1)."""

    step: CommitmentStep
    outcome: StageOutcome
    authority_class: StageAuthorityClass
    native_verdict_type: str | None = None
    native_verdict_value: str | None = None
    bound_digest: str | None = None
    bound_identity: str | None = None
    reason: str | None = None
    authority: AllFalseCoordinatorAuthority = AllFalseCoordinatorAuthority()


class AttemptRequest(FrozenModel):
    """The Coordinator's step-12 unique attempt request (ADR-002-002 §11.3:599; design #31 §4.3)."""

    attempt_id: str
    conformance_proof_digest: str
    action_flow_permit_identity: str
    reference_coordinate_digest: str
    authority: AllFalseCoordinatorAuthority = AllFalseCoordinatorAuthority()

    @model_validator(mode="after")
    def _bindings_concrete(self) -> AttemptRequest:
        """Every binding must be concrete — an unbound attempt is unconstructable."""
        for name in (
            "attempt_id",
            "conformance_proof_digest",
            "action_flow_permit_identity",
            "reference_coordinate_digest",
        ):
            value: str = getattr(self, name)
            if not value.strip():
                raise ArtifactIntegrityError(
                    f"AttemptRequest.{name} must be concrete — a transmission attempt is bound to "
                    "the exact proof and permit (ADR-002-002 §11.3:599)"
                )
        return self


class StageRequest(FrozenModel):
    """The input one injected stage receives (design #31 §4.1 / §12-2)."""

    step: CommitmentStep
    instrument_key: InstrumentKey
    proposal: Proposal
    reference: OrderingEvent = OrderingEvent()
    prior_verdicts: tuple[StageVerdict, ...] = ()
    attempt: AttemptRequest | None = None
    value_view: ContextValueView | None = None
    held_position_magnitude: CanonicalDecimal | None = None


class SendHandoff(FrozenModel):
    """The immediate return of the injected ``Transmit`` interface (design #31 §4.5)."""

    accepted_for_transmission: bool | None = None
    handoff_reference: str | None = None


class ProvisionalReservation(FrozenModel):
    """The engine's **non-authoritative** reservation projection (design #31 §2.4/§4.4)."""

    instrument_key: InstrumentKey
    capacity_state: CapacityState
    knowledge: EgressKnowledge
    proposal_id: str | None = None
    attempt_id: str | None = None
    filled_quantity: CanonicalDecimal | None = None
    remaining_quantity: CanonicalDecimal | None = None
    pre_quarantine_capacity: CapacityState | None = None
    authority: AllFalseCoordinatorAuthority = AllFalseCoordinatorAuthority()


class UnsentDiscardRef(FrozenModel):
    """The typed token gating :meth:`~tos.engine.state.ProvisionalReservationLedger"""

    proposal_id: str
    reason: UnsentDiscardReason


class EgressResultOutcome(FrozenModel):
    """The covered content of one applied ``EGRESS_RESULT`` outcome (Phase 3 wave 3 KW3-RD)."""

    disposition: ResultDisposition
    capacity_state: CapacityState | None = None
    knowledge: EgressKnowledge | None = None
    filled_quantity: CanonicalDecimal | None = None
    remaining_quantity: CanonicalDecimal | None = None
    pre_quarantine_capacity: CapacityState | None = None


def egress_result_outcome_digest(
    disposition: ResultDisposition,
    projection: ProvisionalReservation | None,
    *,
    scheme: CanonicalizationScheme,
) -> str:
    """The content-addressed digest of one applied ``EGRESS_RESULT`` outcome (Phase 3 KW3-RD)."""
    outcome = EgressResultOutcome(
        disposition=disposition,
        capacity_state=None if projection is None else projection.capacity_state,
        knowledge=None if projection is None else projection.knowledge,
        filled_quantity=None if projection is None else projection.filled_quantity,
        remaining_quantity=(
            None if projection is None else projection.remaining_quantity
        ),
        pre_quarantine_capacity=(
            None if projection is None else projection.pre_quarantine_capacity
        ),
    )
    return scheme.compute_digest(outcome.model_dump(mode="json"))


class RegisteredStrategy(FrozenModel):
    """One admitted Authored Strategy plus its authored configuration (design #31 §3.3/§3.5)."""

    strategy: AuthoredStrategy
    config: EvaluationConfig
    instrument_key: InstrumentKey


class EngineConfiguration(FrozenModel):
    """Every injected scalar the engine consumes (design #31 §8 — hardcoded numbers: 0)."""

    dsl_evaluation_budget_steps: int
    max_unresolved_send_per_scope: int
    canonicalization_version: str
    enforcement_mechanism_version: str

    @model_validator(mode="after")
    def _bounds_non_negative(self) -> EngineConfiguration:
        """Reject a negative injected bound — an ill-formed bound is not a bound."""
        for name in ("dsl_evaluation_budget_steps", "max_unresolved_send_per_scope"):
            value: int = getattr(self, name)
            if value < 0:
                raise ArtifactIntegrityError(
                    f"EngineConfiguration.{name} must be non-negative (got {value})"
                )
        for name in ("canonicalization_version", "enforcement_mechanism_version"):
            token: str = getattr(self, name)
            if not token.strip():
                raise ArtifactIntegrityError(
                    f"EngineConfiguration.{name} must be a concrete injected version"
                )
        return self


class EngineEvidenceRecord(FrozenModel):
    """One provisional evidence record (design #31 §5.1/§12-5)."""

    kind: EvidenceKind
    instrument_key: InstrumentKey | None = None
    step: CommitmentStep | None = None
    event_id: str | None = None
    halt_reason: HaltReason | None = None
    stage_outcome: StageOutcome | None = None
    authority_class: StageAuthorityClass | None = None
    bound_identity: str | None = None
    bound_digest: str | None = None
    egress_result_kind: EgressResultKind | None = None
    result_disposition: ResultDisposition | None = None
    nontrade_disposition: None = None
    capacity_state: CapacityState | None = None
    knowledge: EgressKnowledge | None = None
    filled_quantity: CanonicalDecimal | None = None
    remaining_quantity: CanonicalDecimal | None = None
    broker_execution_id: str | None = None
    trading_date: str | None = Field(default=None, exclude_if=_omit_when_none)
    outcome_type: str | None = None
    outcome_digest: str | None = None
    capsule_id: str | None = None
    capsule_digest: str | None = None
    strategy_version: str | None = None
    config_version: str | None = None
    attempt_id: str | None = None
    detail: str | None = None
    authority: AllFalseCoordinatorAuthority = AllFalseCoordinatorAuthority()

    @model_validator(mode="after")
    def _trading_date_shape(self) -> EngineEvidenceRecord:
        """Refuse a malformed injected trading-date token (:func:`_check_trading_date`)."""
        _check_trading_date(self.trading_date, "EngineEvidenceRecord")
        return self
