"""The 19-step fail-closed Execution Coordinator sequencer (design #31 §4 — load-bearing content).

This is where the series' central lesson applies: **fail-open lives in the wiring, not inside the
predicates**. The sequencer walks the ADR-002-002 §11 Normal Commitment Flow in its normative
order (RFC-005 §7:192 — "SHALL NOT redefine, reorder, or abridge that sequence") and calls each
step through an injected ``Stage``. The rules:

1. **Positive-admit gate** (design #31 §4.2 rule 1). The *only* thing that advances the sequence is
   ``verdict.outcome is StageOutcome.ADMIT``. A negated gate (``is not DENY``) is forbidden: it
   fails open on ``None``, on an exception, and on any future member.
2. **deny / UNKNOWN / missing / absent / raised ⇒ immediate stop** (rule 2). The flow stops at that
   step, nothing is transmitted, and the halt is recorded with its reason — the sequencer-layer
   mirror of RFC-002 §10.8:761 ("reject … when any required fact is missing, stale, conflicting, or
   unverifiable").
3. **UNKNOWN is restrictive *and* special** (rule 3). It is neither a rejection nor safe-to-retry
   (RFC-005 §11:325-327). Before the attempt is handed off, an UNKNOWN simply stops the flow; once
   the attempt has left the core, an UNKNOWN keeps the reservation projection conservatively
   ``POTENTIALLY_LIVE`` and re-submits nothing (:mod:`tos.engine.state`).
4. **A degraded outcome never gets here** (rule 4). :mod:`tos.engine.pipeline` folds a
   bounded-evaluation degradation to no-action, and a no-action starts no flow — defence in depth.

**Coordinator authority: none** (design #31 §4.3). Two structural seals make that mechanical rather
than promised:

* **step 12 is not injectable.** The Coordinator's single direct action is creating the unique
  attempt request bound to the exact conformance proof and Action Flow Permit (ADR-002-002
  §11.3:599). Supplying a stage for it raises.
* **steps 15-19 are not hostable.** The Send Boundary is constitutionally D-E4 (RFC-002 §10.8);
  supplying a stage for any of them raises. D-E1 therefore makes **no** claim about final-egress
  currentness, QCC, or single-use capability, and its fail-closed guarantee is honestly scoped to
  steps 1-14 (design #31 §4.5 item-7 / §10.2-3).

**attempt-id determinism** (design #31 §4.3, MAJOR-3): the identity is content-addressed from
(conformance-proof digest, Action Flow Permit identity, reference-coordinate digest) through the
injected canonicalization scheme. No ``uuid4``, no timestamp nonce, no RNG — the same three inputs
always reproduce the same attempt identity, so replay identity survives (RFC-003 §10:360-363).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #31 §0.3). No clock, no RNG.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from tos.dsl import Proposal
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
    """One injected commitment-flow step (design #31 §4.1 / §12-2).

    A stage is ``(StageRequest) -> StageVerdict``. The sequencer does not know — and must not
    know — whether the implementation is an already-shipped pure sibling predicate, a
    non-authoritative provisional stand-in, or a D-E4 implementation; that ignorance is what makes
    backtest / paper / test-double parity possible (design #31 §4.1/§12).
    """

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Judge one step and return its positive-admit verdict."""
        ...


@runtime_checkable
class Transmit(Protocol):
    """The injected send-boundary hand-off (design #31 §4.5 / §12-3).

    ``(AttemptRequest) -> SendHandoff``, returning immediately: the core issues the request and
    does not block on the network (design #31 §2.1 D5). The *result* arrives later as an
    ``EGRESS_RESULT`` event. D-E3 injects a fill-model stand-in (no real send); D-E4 injects the
    real paper-account sender — **same sequencer, different injection** (RFC-002 §10.8:763 forbids
    exposing a general-purpose live-order method to backtest/simulation components).
    """

    def __call__(self, attempt: AttemptRequest) -> SendHandoff:
        """Hand the bound attempt to the send boundary and return at once."""
        ...


@dataclass(frozen=True)
class FlowResult:
    """The outcome of one commitment-flow run (design #31 §4).

    ``handed_off`` is ``True`` only when every step 1-14 admitted positively **and** the attempt
    was passed to the injected transmit. ``halt_step`` / ``halt_reason`` name where and why the
    flow stopped otherwise — a stop is never silent.
    """

    instrument_key: InstrumentKey
    verdicts: tuple[StageVerdict, ...] = ()
    attempt: AttemptRequest | None = None
    handed_off: bool = False
    handoff: SendHandoff | None = None
    halt_step: CommitmentStep | None = None
    halt_reason: HaltReason | None = None
    detail: str | None = None


def validate_stage_map(stages: Mapping[CommitmentStep, Stage]) -> None:
    """Reject a stage map that would breach a Coordinator structural seal (design #31 §4.3/§4.5).

    Args:
        stages: The injected step → stage mapping.

    Raises:
        ArtifactIntegrityError: If a stage is supplied for a Coordinator-realized step (1 or 12) or
            for any Send Boundary step (15-19). Both are structural seals: the Coordinator's only
            direct action is step 12, and the send boundary is D-E4's — hosting either would be the
            over-realization the design forbids.
    """
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
    """The content-addressed digest of the injected reference coordinate (design #31 §4.3).

    The event's causal-ordering coordinates are an *opaque injected* time reference (design #31
    §2.3): a bar timestamp for a backtest, an injected clock reading for paper. Digesting them
    through the same canonicalization scheme keeps the attempt identity a pure function of its
    inputs.

    Args:
        reference: The event's ordering coordinates.
        scheme: The injected canonicalization scheme.

    Returns:
        The hex digest of the canonicalized coordinates.
    """
    return scheme.compute_digest(reference.model_dump(mode="json"))


def build_attempt_request(
    *,
    conformance_proof_digest: str | None,
    action_flow_permit_identity: str | None,
    reference: OrderingEvent,
    scheme: CanonicalizationScheme,
) -> AttemptRequest:
    """Create the step-12 unique attempt request (ADR-002-002 §11.3:599; design #31 §4.3).

    The identity is **content-addressed**: ``derive_id`` over the scheme digest of
    (proof digest, permit identity, reference-coordinate digest). There is no ``uuid4``, no
    timestamp, and no RNG anywhere on this path — the §7.1 canary enforces that — so the same three
    bindings always reproduce the same attempt identity and replay identity is preserved
    (RFC-003 §10:360-363).

    Args:
        conformance_proof_digest: The exact Order Conformance Proof digest (step 11).
        action_flow_permit_identity: The exact single-use Action Flow Permit identity (step 9).
        reference: The injected reference coordinate.
        scheme: The injected canonicalization scheme.

    Returns:
        The bound :class:`~tos.engine.records.AttemptRequest`.

    Raises:
        ArtifactIntegrityError: If either binding is absent — an unbound attempt is
            unconstructable (fail-closed).
    """
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
) -> FlowResult:
    """Record a halt and return the restrictive :class:`FlowResult` (design #31 §4.2 rule 2)."""
    sink.record(
        EngineEvidenceRecord(
            kind=EvidenceKind.FLOW_HALTED,
            instrument_key=key,
            step=step,
            halt_reason=reason,
            detail=detail,
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
    """Extract the (conformance-proof digest, Action Flow Permit identity) step 12 binds.

    Read **structurally** off the recorded verdicts of step 11 and step 9 rather than from any
    caller-supplied claim (구조 파생 > 자기신고; design #31 §4.3).
    """
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
) -> FlowResult:
    """Walk ADR-002-002 §11 steps 1-14 fail-closed, then hand off to the injected transmit.

    Args:
        proposal_id: The emitted proposal's identity (bound into the reservation projection).
        proposal: The emitted per-instrument Proposal that starts the flow (step 1).
        instrument_key: The dispatch scope.
        reference: The event's injected reference/ordering coordinates.
        stages: The injected step → stage mapping for steps 2-11, 13, 14.
        transmit: The injected send-boundary hand-off; ``None`` stops the flow after step 14 with
            ``TRANSMIT_UNAVAILABLE`` (an absent send boundary is not a licence to skip it).
        ledger: The provisional, non-authoritative reservation projection.
        sink: The provisional evidence sink.
        scheme: The injected canonicalization scheme.

    Returns:
        The :class:`FlowResult`.

    Raises:
        ArtifactIntegrityError: If the stage map breaches a Coordinator structural seal.
    """
    validate_stage_map(stages)

    verdicts: tuple[StageVerdict, ...] = ()
    attempt: AttemptRequest | None = None

    for step in SEQUENCED_STEPS:
        # -- step 1: the Decision Service proposal, already realized by the pipeline ----------
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

        # -- step 12: the Coordinator's only direct action ------------------------------------
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
                return _halt(
                    sink,
                    key=instrument_key,
                    verdicts=verdicts,
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

        # -- the capacity stage: at-most-one exposure retention (design #31 §4.4, MAJOR-1) -----
        # A restrictive-only observation of the engine's OWN projection, applied *before* the
        # injected stage runs, so the seal does not depend on which stand-in was injected. It
        # creates no headroom for anyone (RFC-002 §9.1:558) and grants nothing; it only refuses to
        # start an overlapping economic effect while one is unresolved for the scope — the
        # provisional mirror of SAFE-021 At-Most-One Exposure Effect closing the between-events
        # re-entrancy window (design #31 §2.1(iv)/§4.4).
        if step is CommitmentStep.LEDGER_VERIFICATION and not ledger.admits_new_exposure(
            instrument_key
        ):
            outstanding = ledger.outstanding(instrument_key)
            return _halt(
                sink,
                key=instrument_key,
                verdicts=verdicts,
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

        # -- steps 2-11, 13, 14: injected stages ----------------------------------------------
        stage = stages.get(step)
        if stage is None:
            return _halt(
                sink,
                key=instrument_key,
                verdicts=verdicts,
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
        )
        try:
            verdict = stage(request)
        except Exception as exc:  # noqa: BLE001 - any stage failure is a restrictive stop
            return _halt(
                sink,
                key=instrument_key,
                verdicts=verdicts,
                step=step,
                reason=HaltReason.STAGE_RAISED,
                detail=f"stage for step {step_number(step)} raised {type(exc).__name__}: {exc}",
            )
        if verdict is None:
            return _halt(
                sink,
                key=instrument_key,
                verdicts=verdicts,
                step=step,
                reason=HaltReason.STAGE_VERDICT_ABSENT,
                detail=(
                    f"stage for step {step_number(step)} produced no verdict — absence is not "
                    "admission"
                ),
            )
        if verdict.step is not step:
            return _halt(
                sink,
                key=instrument_key,
                verdicts=verdicts,
                step=step,
                reason=HaltReason.STAGE_VERDICT_STEP_MISMATCH,
                detail=(
                    f"stage for step {step_number(step)} returned a verdict for {verdict.step} — "
                    "a verdict answers its own step, never another's"
                ),
            )
        verdicts += (verdict,)

        # ★ the positive-admit gate. Only an explicit ADMIT advances (design #31 §4.2 rule 1).
        if verdict.outcome is not StageOutcome.ADMIT:
            reason = (
                HaltReason.STAGE_UNKNOWN
                if verdict.outcome is StageOutcome.UNKNOWN
                else HaltReason.STAGE_DENIED
            )
            return _halt(
                sink,
                key=instrument_key,
                verdicts=verdicts,
                step=step,
                reason=reason,
                detail=verdict.reason,
            )

        sink.record(
            EngineEvidenceRecord(
                kind=EvidenceKind.FLOW_STEP_ADMITTED,
                instrument_key=instrument_key,
                step=step,
                stage_outcome=verdict.outcome,
                authority_class=verdict.authority_class,
                detail=verdict.reason,
            )
        )

        # Step 9 is where the atomic commitment is projected: the scope becomes occupied, and the
        # at-most-one retention (design #31 §4.4) applies from here on. The ledger re-checks the
        # bound itself, so a defect in the step-8 pre-check still fails closed here.
        if step is CommitmentStep.ATOMIC_COMMIT:
            try:
                ledger.commit_unbound(instrument_key, proposal_id=proposal_id)
            except ArtifactIntegrityError as exc:
                return _halt(
                    sink,
                    key=instrument_key,
                    verdicts=verdicts,
                    step=step,
                    reason=HaltReason.AT_MOST_ONE_EXPOSURE_HELD,
                    detail=str(exc),
                )

    # -- send-boundary hand-off (steps 15-19 are D-E4; design #31 §4.5) -----------------------
    if attempt is None:  # pragma: no cover - step 12 always runs or halts
        return _halt(
            sink,
            key=instrument_key,
            verdicts=verdicts,
            step=CommitmentStep.ATTEMPT_REQUEST,
            reason=HaltReason.ATTEMPT_BINDING_INCOMPLETE,
            detail="no attempt request was created",
        )
    if transmit is None:
        return _halt(
            sink,
            key=instrument_key,
            verdicts=verdicts,
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            reason=HaltReason.TRANSMIT_UNAVAILABLE,
            detail=(
                "no transmit interface is injected — the Send Boundary is D-E4's and its absence "
                "is a stop, never a skip (design #31 §4.5)"
            ),
        )

    # ADR-002-002 §11.4 step 16: the projection advances to POTENTIALLY_LIVE **before** the
    # external call, and stays there even if the hand-off fails (INV-005:168; RFC-002 §10.7:722 —
    # a missing acknowledgement is never read as a rejection).
    ledger.mark_potentially_live(instrument_key)
    try:
        handoff = transmit(attempt)
    except Exception as exc:  # noqa: BLE001 - a failed hand-off is not proof of "not sent"
        return _halt(
            sink,
            key=instrument_key,
            verdicts=verdicts,
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
