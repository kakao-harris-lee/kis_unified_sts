"""The 19-step fail-closed Execution Coordinator sequencer (design #31 §4 — load-bearing content)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from tos.dsl import ContextValueView, Proposal
from tos.engine._base import (
    ArtifactIntegrityError,
    CanonicalizationScheme,
    derive_id,
)
from tos.engine.records import (
    ATTEMPT_ID_PREFIX,
    AttemptRequest,
    EngineEvidenceRecord,
    InstrumentKey,
    SendHandoff,
    StageRequest,
    StageVerdict,
)
from tos.engine.sink import EvidenceSink
from tos.engine.state import ProvisionalReservationLedger
from tos.engine.vocabulary import (
    COORDINATOR_REALIZED_STEPS,
    SEND_BOUNDARY_STEPS,
    SEQUENCED_STEPS,
    CommitmentStep,
    EvidenceKind,
    HaltReason,
    StageAuthorityClass,
    StageOutcome,
    step_number,
)
from tos.ordering import OrderingEvent

__all__ = [
    "FlowResult",
    "Stage",
    "Transmit",
    "build_attempt_request",
    "reference_coordinate_digest",
    "run_commitment_flow",
    "validate_stage_map",
]


@runtime_checkable
class Stage(Protocol):
    """One injected commitment-flow step (design #31 §4.1 / §12-2)."""

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Judge one step and return its positive-admit verdict."""
        ...


@runtime_checkable
class Transmit(Protocol):
    """The injected send-boundary hand-off (design #31 §4.5 / §12-3)."""

    def __call__(self, attempt: AttemptRequest) -> SendHandoff:
        """Hand the bound attempt to the send boundary and return at once."""
        ...


@dataclass(frozen=True)
class FlowResult:
    """The outcome of one commitment-flow run (design #31 §4)."""

    instrument_key: InstrumentKey
    verdicts: tuple[StageVerdict, ...] = ()
    attempt: AttemptRequest | None = None
    handed_off: bool = False
    handoff: SendHandoff | None = None
    halt_step: CommitmentStep | None = None
    halt_reason: HaltReason | None = None
    detail: str | None = None


def validate_stage_map(stages: Mapping[CommitmentStep, Stage]) -> None:
    """Reject a stage map that would breach a Coordinator structural seal (design #31 §4.3/§4.5)."""
    for step in stages:
        if step in COORDINATOR_REALIZED_STEPS:
            raise ArtifactIntegrityError(
                f"step {step_number(step)} ({step}) is realized directly by the Execution "
                "Coordinator and is not injectable — supplying a stage for it would move the "
                "Coordinator's own action (or the Decision Service's proposal) outside it "
                "(ADR-002-002 §11.3:599; design #31 §4.3)"
            )
        if step in SEND_BOUNDARY_STEPS:
            raise ArtifactIntegrityError(
                f"step {step_number(step)} ({step}) is a Send Boundary step — constitutionally "
                "D-E4 (RFC-002 §10.8:741-759). This sequencer does not host it and makes no claim "
                "about final-egress currentness / QCC / single-use (design #31 §4.5 item-7)"
            )


def reference_coordinate_digest(
    reference: OrderingEvent, *, scheme: CanonicalizationScheme
) -> str:
    """The content-addressed digest of the injected reference coordinate (design #31 §4.3)."""
    return scheme.compute_digest(reference.model_dump(mode="json"))


def build_attempt_request(
    *,
    conformance_proof_digest: str | None,
    action_flow_permit_identity: str | None,
    reference: OrderingEvent,
    scheme: CanonicalizationScheme,
) -> AttemptRequest:
    """Create the step-12 unique attempt request (ADR-002-002 §11.3:599; design #31 §4.3)."""
    if not conformance_proof_digest or not action_flow_permit_identity:
        raise ArtifactIntegrityError(
            "an attempt request binds the exact conformance proof and Action Flow Permit "
            f"(proof_digest={conformance_proof_digest!r}, "
            f"permit={action_flow_permit_identity!r}) — ADR-002-002 §11.3:599"
        )
    coordinate_digest = reference_coordinate_digest(reference, scheme=scheme)
    preimage = {
        "conformance_proof_digest": conformance_proof_digest,
        "action_flow_permit_identity": action_flow_permit_identity,
        "reference_coordinate_digest": coordinate_digest,
    }
    return AttemptRequest(
        attempt_id=derive_id(ATTEMPT_ID_PREFIX, scheme.compute_digest(preimage)),
        conformance_proof_digest=conformance_proof_digest,
        action_flow_permit_identity=action_flow_permit_identity,
        reference_coordinate_digest=coordinate_digest,
    )


def _halt(
    sink: EvidenceSink,
    *,
    key: InstrumentKey,
    verdicts: tuple[StageVerdict, ...],
    step: CommitmentStep,
    reason: HaltReason,
    detail: str | None,
    event_id: str | None = None,
) -> FlowResult:
    """Record a halt and return the restrictive :class:`FlowResult` (design #31 §4.2 rule 2)."""
    sink.record(
        EngineEvidenceRecord(
            kind=EvidenceKind.FLOW_HALTED,
            instrument_key=key,
            step=step,
            halt_reason=reason,
            detail=detail,
            event_id=event_id,
        )
    )
    return FlowResult(
        instrument_key=key,
        verdicts=verdicts,
        halt_step=step,
        halt_reason=reason,
        detail=detail,
    )


def _bindings_from(verdicts: tuple[StageVerdict, ...]) -> tuple[str | None, str | None]:
    """Extract the (conformance-proof digest, Action Flow Permit identity) step 12 binds."""
    proof_digest: str | None = None
    permit_identity: str | None = None
    for verdict in verdicts:
        if verdict.step is CommitmentStep.ORDER_CONFORMANCE_PROOF:
            proof_digest = verdict.bound_digest
        elif verdict.step is CommitmentStep.ATOMIC_COMMIT:
            permit_identity = verdict.bound_identity
    return proof_digest, permit_identity


def run_commitment_flow(
    *,
    proposal_id: str | None,
    proposal: Proposal,
    instrument_key: InstrumentKey,
    reference: OrderingEvent,
    stages: Mapping[CommitmentStep, Stage],
    transmit: Transmit | None,
    ledger: ProvisionalReservationLedger,
    sink: EvidenceSink,
    scheme: CanonicalizationScheme,
    value_view: ContextValueView | None = None,
    event_id: str | None = None,
) -> FlowResult:
    """Walk ADR-002-002 §11 steps 1-14 fail-closed, then hand off to the injected transmit."""
    validate_stage_map(stages)

    verdicts: tuple[StageVerdict, ...] = ()
    attempt: AttemptRequest | None = None

    def _stop(
        *, step: CommitmentStep, reason: HaltReason, detail: str | None
    ) -> FlowResult:
        """Record a halt for this flow — binds ``sink``/``verdicts``/``event_id`` from the"""
        return _halt(
            sink,
            key=instrument_key,
            verdicts=verdicts,
            step=step,
            reason=reason,
            detail=detail,
            event_id=event_id,
        )

    for step in SEQUENCED_STEPS:
        if step is CommitmentStep.DECISION_PROPOSAL:
            verdicts += (
                StageVerdict(
                    step=step,
                    outcome=StageOutcome.ADMIT,
                    authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                    native_verdict_type=type(proposal).__name__,
                    bound_digest=proposal.canonical_digest,
                    bound_identity=proposal_id,
                    reason="immutable Intent proposal emitted by the decision pipeline",
                ),
            )
            continue

        if step is CommitmentStep.ATTEMPT_REQUEST:
            proof_digest, permit_identity = _bindings_from(verdicts)
            try:
                attempt = build_attempt_request(
                    conformance_proof_digest=proof_digest,
                    action_flow_permit_identity=permit_identity,
                    reference=reference,
                    scheme=scheme,
                )
            except ArtifactIntegrityError as exc:
                return _stop(
                    step=step,
                    reason=HaltReason.ATTEMPT_BINDING_INCOMPLETE,
                    detail=str(exc),
                )
            ledger.bind_attempt(instrument_key, attempt_id=attempt.attempt_id)
            sink.record(
                EngineEvidenceRecord(
                    kind=EvidenceKind.ATTEMPT_REQUEST_CREATED,
                    instrument_key=instrument_key,
                    step=step,
                    attempt_id=attempt.attempt_id,
                    event_id=event_id,
                    detail=(
                        "content-addressed from (proof digest, permit identity, reference "
                        "coordinate) — no RNG, no timestamp nonce (RFC-003 §10:360-363)"
                    ),
                )
            )
            verdicts += (
                StageVerdict(
                    step=step,
                    outcome=StageOutcome.ADMIT,
                    authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                    native_verdict_type=type(attempt).__name__,
                    bound_identity=attempt.attempt_id,
                    reason="unique attempt request bound to the exact proof and permit",
                ),
            )
            continue

        if (
            step is CommitmentStep.LEDGER_VERIFICATION
            and not ledger.admits_new_exposure(instrument_key)
        ):
            outstanding = ledger.outstanding(instrument_key)
            return _stop(
                step=step,
                reason=HaltReason.AT_MOST_ONE_EXPOSURE_HELD,
                detail=(
                    "an unresolved reservation is projected for this scope "
                    f"(capacity_state="
                    f"{None if outstanding is None else outstanding.capacity_state.value}, "
                    f"knowledge={None if outstanding is None else outstanding.knowledge.value}, "
                    f"attempt_id={None if outstanding is None else outstanding.attempt_id!r}) — "
                    "an overlapping economic effect is denied at the capacity stage "
                    "(MAX_unresolved_send_per_scope; RFC-005 §11:319-343, §12 item 7 :364-365)"
                ),
            )

        stage = stages.get(step)
        if stage is None:
            return _stop(
                step=step,
                reason=HaltReason.STAGE_MISSING,
                detail=(
                    f"no stage is injected for step {step_number(step)} ({step}) — a missing "
                    "required step is a stop, never a skip (RFC-002 §10.8:761)"
                ),
            )
        request = StageRequest(
            step=step,
            instrument_key=instrument_key,
            proposal=proposal,
            reference=reference,
            prior_verdicts=verdicts,
            attempt=attempt,
            value_view=value_view,
            held_position_magnitude=ledger.outstanding_consumed_magnitude(
                instrument_key
            ),
        )
        try:
            verdict = stage(request)
        except (
            Exception
        ) as exc:  # noqa: BLE001 - any stage failure is a restrictive stop
            return _stop(
                step=step,
                reason=HaltReason.STAGE_RAISED,
                detail=f"stage for step {step_number(step)} raised {type(exc).__name__}: {exc}",
            )
        if verdict is None:
            return _stop(
                step=step,
                reason=HaltReason.STAGE_VERDICT_ABSENT,
                detail=(
                    f"stage for step {step_number(step)} produced no verdict — absence is not "
                    "admission"
                ),
            )
        if verdict.step is not step:
            return _stop(
                step=step,
                reason=HaltReason.STAGE_VERDICT_STEP_MISMATCH,
                detail=(
                    f"stage for step {step_number(step)} returned a verdict for {verdict.step} — "
                    "a verdict answers its own step, never another's"
                ),
            )
        verdicts += (verdict,)

        if verdict.outcome is not StageOutcome.ADMIT:
            reason = (
                HaltReason.STAGE_UNKNOWN
                if verdict.outcome is StageOutcome.UNKNOWN
                else HaltReason.STAGE_DENIED
            )
            return _stop(step=step, reason=reason, detail=verdict.reason)

        sink.record(
            EngineEvidenceRecord(
                kind=EvidenceKind.FLOW_STEP_ADMITTED,
                instrument_key=instrument_key,
                step=step,
                stage_outcome=verdict.outcome,
                authority_class=verdict.authority_class,
                event_id=event_id,
                bound_identity=verdict.bound_identity,
                bound_digest=verdict.bound_digest,
                detail=verdict.reason,
            )
        )

        if step is CommitmentStep.ATOMIC_COMMIT:
            try:
                ledger.commit_unbound(instrument_key, proposal_id=proposal_id)
            except ArtifactIntegrityError as exc:
                return _stop(
                    step=step,
                    reason=HaltReason.AT_MOST_ONE_EXPOSURE_HELD,
                    detail=str(exc),
                )

    if attempt is None:  # pragma: no cover - step 12 always runs or halts
        return _stop(
            step=CommitmentStep.ATTEMPT_REQUEST,
            reason=HaltReason.ATTEMPT_BINDING_INCOMPLETE,
            detail="no attempt request was created",
        )
    if transmit is None:
        return _stop(
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            reason=HaltReason.TRANSMIT_UNAVAILABLE,
            detail=(
                "no transmit interface is injected — the Send Boundary is D-E4's and its absence "
                "is a stop, never a skip (design #31 §4.5)"
            ),
        )

    ledger.mark_potentially_live(instrument_key)
    try:
        handoff = transmit(attempt)
    except (
        Exception
    ) as exc:  # noqa: BLE001 - a failed hand-off is not proof of "not sent"
        return _stop(
            step=CommitmentStep.NETWORK_CALL,
            reason=HaltReason.TRANSMIT_RAISED,
            detail=(
                f"transmit raised {type(exc).__name__}: {exc} — the reservation projection stays "
                "POTENTIALLY_LIVE and nothing is resubmitted (ADR-002-002 INV-005:168)"
            ),
        )
    sink.record(
        EngineEvidenceRecord(
            kind=EvidenceKind.SEND_HANDED_OFF,
            instrument_key=instrument_key,
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id=attempt.attempt_id,
            event_id=event_id,
            detail=(
                "attempt handed to the injected send boundary; steps 15-19 (final-egress "
                "currentness, QCC, single-use capability, actual-outbound comparison) are D-E4's "
                "and are not claimed here (design #31 §4.5 item-7)"
            ),
        )
    )
    return FlowResult(
        instrument_key=instrument_key,
        verdicts=verdicts,
        attempt=attempt,
        handed_off=True,
        handoff=handoff,
    )
