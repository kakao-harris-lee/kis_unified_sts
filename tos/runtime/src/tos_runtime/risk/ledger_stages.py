"""Engine ``Stage`` realizations for steps 6-10 of the ADR-002-002 §11 Normal"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from tos.afg import ActionFlowPermit
from tos.engine.records import StageRequest, StageVerdict
from tos.engine.vocabulary import CommitmentStep, StageAuthorityClass, StageOutcome
from tos.rcl import (
    AppendReceipt,
    AppendRefusal,
    AppendRefusalReason,
    CapacityReservationTransition,
    CapacityState,
    CapacityVector,
    CommandType,
    LogView,
    ReservationScope,
    TransitionCause,
    WriterEpoch,
    capacity_at_least_as_conservative,
)

from tos_runtime.rcl.log import (
    ReservationTransitionRefusal,
    SqliteCommitLog,
    StaleEpochRead,
)
from tos_runtime.rcl.projection import (
    ReservationProjectionReader,
    ScopeReservation,
    outstanding_reservations,
)
from tos_runtime.rcl.reservation_identity import reservation_id_in_scope
from tos_runtime.risk.aggregate import AggregateRiskDecisionInputs, AggregateRiskService
from tos_runtime.risk.close_fence import (
    CloseProofCommitFence,
    SyntheticCloseEntryFence,
    close_proof_fence_matches_request,
    close_proof_fence_matches_view,
    synthetic_close_fence_valid,
)
from tos_runtime.risk.flow import (
    ActionFlowDecisionInputs,
    ActionFlowGovernor,
    permit_reservation_binding,
)

__all__ = [
    "ActionFlowDecisionStage",
    "AggregateRiskDecisionStage",
    "AtomicCommitLogPort",
    "AtomicCommitStage",
    "CloseProofCommitFence",
    "CommitmentUnavailabilityStage",
    "LedgerVerificationStage",
    "SyntheticCloseEntryFence",
    "item15_fields",
    "synthetic_close_fence_valid",
    "verdict_for_scope",
]

_COMMIT_RESERVATION_KIND = CommandType.COMMIT_RESERVATION

_CAS_UNKNOWN_REASONS: frozenset[AppendRefusalReason] = frozenset(
    {
        AppendRefusalReason.STALE_EPOCH,
        AppendRefusalReason.SEQ_MISMATCH,
        AppendRefusalReason.STORE_UNAVAILABLE,
        AppendRefusalReason.PARTIAL_COMMIT_SUSPECTED,
    }
)

AggregateInputsProvider = Callable[[StageRequest], AggregateRiskDecisionInputs | None]
ActionFlowInputsProvider = Callable[[StageRequest], ActionFlowDecisionInputs | None]
PermitProvider = Callable[[StageRequest], ActionFlowPermit | None]
ReservationIdProvider = Callable[[StageRequest, ActionFlowPermit], str | None]
GenerationProvider = Callable[[StageRequest], int]
EffectEnvelopeReader = Callable[[], CapacityVector | None]
CloseProofFenceProvider = Callable[
    [StageRequest], "CloseProofCommitFence | SyntheticCloseEntryFence | None"
]


_OPEN_EFFECT = "OPEN"
_CLOSE_EFFECT = "CLOSE"


def _verdict(step: CommitmentStep, outcome: StageOutcome, reason: str) -> StageVerdict:
    """The shared verdict shape every stage below uses for a reason-only outcome."""
    return StageVerdict(
        step=step,
        outcome=outcome,
        authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
        reason=reason,
    )


def _unknown(step: CommitmentStep, reason: str) -> StageVerdict:
    """The shared restrictive ``UNKNOWN`` verdict shape every stage below uses."""
    return _verdict(step, StageOutcome.UNKNOWN, reason)


def _deny(step: CommitmentStep, reason: str) -> StageVerdict:
    """A proven denial (#966 step-8 admission table)."""
    return _verdict(step, StageOutcome.DENY, reason)


def _admit(step: CommitmentStep, reason: str) -> StageVerdict:
    """A positive admission (#966 step-8 admission table)."""
    return _verdict(step, StageOutcome.ADMIT, reason)


def _time_gate(
    time_permits_new_risk: Callable[[], bool], step: CommitmentStep
) -> StageVerdict | None:
    """Refuse to admit new risk unless the injected time gate reports ``True``."""
    if time_permits_new_risk() is not True:
        return _unknown(
            step,
            "the injected time snapshot does not report TRUSTED "
            "(tos.time.state_permits_new_normal_risk) — no new risk admitted",
        )
    return None


def _find_verdict(
    verdicts: tuple[StageVerdict, ...], step: CommitmentStep
) -> StageVerdict | None:
    """Read one prior step's verdict structurally off the flow so far (구조"""
    for verdict in verdicts:
        if verdict.step is step:
            return verdict
    return None


class AggregateRiskDecisionStage:
    """Step 6 (``AGGREGATE_RISK_DECISION``) over a real"""

    def __init__(
        self,
        service: AggregateRiskService,
        *,
        inputs_provider: AggregateInputsProvider,
        snapshot_generation_provider: GenerationProvider,
        decision_generation_provider: GenerationProvider,
        time_permits_new_risk: Callable[[], bool],
    ) -> None:
        self._service = service
        self._inputs_provider = inputs_provider
        self._snapshot_generation_provider = snapshot_generation_provider
        self._decision_generation_provider = decision_generation_provider
        self._time_permits_new_risk = time_permits_new_risk

    def __call__(self, request: StageRequest) -> StageVerdict:
        gate = _time_gate(
            self._time_permits_new_risk, CommitmentStep.AGGREGATE_RISK_DECISION
        )
        if gate is not None:
            return gate
        inputs = self._inputs_provider(request)
        if inputs is None:
            return _unknown(
                CommitmentStep.AGGREGATE_RISK_DECISION,
                "no aggregate-risk decision inputs are available for this proposal "
                "— UNKNOWN is restrictive, never an assumed grant",
            )
        try:
            decision = self._service.decide(
                request.instrument_key,
                inputs,
                snapshot_generation=self._snapshot_generation_provider(request),
                decision_generation=self._decision_generation_provider(request),
            )
        except Exception as exc:  # noqa: BLE001 - RCL projection unreachable => UNKNOWN
            return _unknown(
                CommitmentStep.AGGREGATE_RISK_DECISION,
                f"the RCL reservation projection could not be read: "
                f"{type(exc).__name__}: {exc}",
            )
        outcome = _outcome_for_result(
            decision.result.value if decision.result else None
        )
        return StageVerdict(
            step=CommitmentStep.AGGREGATE_RISK_DECISION,
            outcome=outcome,
            authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
            native_verdict_type="AggregateRiskDecision",
            native_verdict_value=(
                None if decision.result is None else decision.result.value
            ),
            bound_digest=decision.canonical_digest,
            bound_identity=decision.decision_id,
            reason=f"aggregate risk decision: {decision.result}",
        )


class ActionFlowDecisionStage:
    """Step 7 (``ACTION_FLOW_DECISION``) over a real"""

    def __init__(
        self,
        governor: ActionFlowGovernor,
        *,
        inputs_provider: ActionFlowInputsProvider,
        time_permits_new_risk: Callable[[], bool],
    ) -> None:
        self._governor = governor
        self._inputs_provider = inputs_provider
        self._time_permits_new_risk = time_permits_new_risk

    def __call__(self, request: StageRequest) -> StageVerdict:
        gate = _time_gate(
            self._time_permits_new_risk, CommitmentStep.ACTION_FLOW_DECISION
        )
        if gate is not None:
            return gate
        inputs = self._inputs_provider(request)
        if inputs is None:
            return _unknown(
                CommitmentStep.ACTION_FLOW_DECISION,
                "no action-flow decision inputs are available for this proposal "
                "— UNKNOWN is restrictive, never an assumed grant",
            )
        decision = self._governor.decide(inputs)
        outcome = _outcome_for_result(
            decision.result.value if decision.result else None
        )
        return StageVerdict(
            step=CommitmentStep.ACTION_FLOW_DECISION,
            outcome=outcome,
            authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
            native_verdict_type="ActionFlowDecision",
            native_verdict_value=(
                None if decision.result is None else decision.result.value
            ),
            bound_digest=decision.canonical_digest,
            bound_identity=decision.decision_id,
            reason=f"action flow decision: {decision.result}",
        )


def _outcome_for_result(result_value: str | None) -> StageOutcome:
    """Map a kernel ``RiskDecisionResult``/``ActionFlowResult`` (both StrEnums"""
    if result_value == "GRANT":
        return StageOutcome.ADMIT
    if result_value == "DENY":
        return StageOutcome.DENY
    return StageOutcome.UNKNOWN


class LedgerVerificationStage:
    """Step 8 (``LEDGER_VERIFICATION``) — ``read_linearizable`` + the RCL"""

    def __init__(
        self,
        log: SqliteCommitLog,
        reader: ReservationProjectionReader,
        *,
        writer_epoch: int,
        position_effect_reader: Callable[[], str | None],
    ) -> None:
        self._log = log
        self._reader = reader
        self._writer_epoch = writer_epoch
        self._position_effect_reader = position_effect_reader

    def __call__(self, request: StageRequest) -> StageVerdict:
        try:
            self._log.read_linearizable(writer_epoch=self._writer_epoch)
        except StaleEpochRead as exc:
            return _unknown(
                CommitmentStep.LEDGER_VERIFICATION, f"stale writer epoch: {exc}"
            )
        except (sqlite3.Error, OSError) as exc:
            return _unknown(
                CommitmentStep.LEDGER_VERIFICATION,
                f"RCL log unreachable: {type(exc).__name__}: {exc}",
            )
        try:
            rows = self._reader.scope_reservations(request.instrument_key)
        except (sqlite3.Error, OSError) as exc:
            return _unknown(
                CommitmentStep.LEDGER_VERIFICATION,
                f"RCL projection unreachable: {type(exc).__name__}: {exc}",
            )
        return verdict_for_scope(self._position_effect_reader(), rows)


def verdict_for_scope(
    position_effect: str | None, rows: Sequence[ScopeReservation]
) -> StageVerdict:
    """:class:`LedgerVerificationStage`'s own admission table, as a pure function."""
    outstanding = outstanding_reservations(rows)
    held = ", ".join(f"{row.reservation_id}={row.state.value}" for row in outstanding)
    if position_effect is None:
        return _deny(
            CommitmentStep.LEDGER_VERIFICATION,
            "step 2 selected no arm for this attempt, so its position effect is "
            "unknown — an unknown effect is never admitted against the ledger "
            f"(outstanding: {held or 'none'})",
        )
    if position_effect == _OPEN_EFFECT:
        if outstanding:
            return _deny(
                CommitmentStep.LEDGER_VERIFICATION,
                f"scope already holds {len(outstanding)} outstanding reservation(s) "
                f"[{held}] — an OPEN attempt needs a scope with none (no pyramiding; "
                "tos_runtime.rcl.gates.INITIAL_RESERVATION_STATES)",
            )
        return _admit(
            CommitmentStep.LEDGER_VERIFICATION,
            "RCL log reachable at the current writer epoch; scope holds no "
            "outstanding reservation, so an OPEN attempt may originate one",
        )
    if position_effect == _CLOSE_EFFECT:
        if len(outstanding) == 1 and (
            outstanding[0].state is CapacityState.POSITION_CONSUMED
        ):
            return _admit(
                CommitmentStep.LEDGER_VERIFICATION,
                f"RCL log reachable at the current writer epoch; scope holds exactly "
                f"one consumed position [{held}] for a CLOSE attempt to discharge",
            )
        return _deny(
            CommitmentStep.LEDGER_VERIFICATION,
            f"a CLOSE attempt admits only over exactly one POSITION_CONSUMED "
            f"reservation; this scope holds {len(outstanding)} outstanding "
            f"[{held or 'none'}]",
        )
    return _deny(
        CommitmentStep.LEDGER_VERIFICATION,
        f"unrecognized position effect {position_effect!r} — only "
        f"{_OPEN_EFFECT}/{_CLOSE_EFFECT} are admitted against the ledger "
        f"(outstanding: {held or 'none'})",
    )


class AtomicCommitLogPort(Protocol):
    """The narrow read/write surface :class:`AtomicCommitStage` needs off a"""

    def read_linearizable(self, *, writer_epoch: WriterEpoch) -> LogView:
        """See :meth:`~tos_runtime.rcl.log.SqliteCommitLog.read_linearizable`'s own"""
        ...

    def apply_reservation_transition(
        self,
        transition: CapacityReservationTransition,
        cause: TransitionCause,
        *,
        command_type: CommandType,
        command_id: str,
        command_digest: str | None,
        expected_seq: int,
        finality_witness: bool | None = None,
    ) -> AppendReceipt | AppendRefusal:
        """See :meth:`~tos_runtime.rcl.log.SqliteCommitLog.apply_reservation_transition`'s"""
        ...


class AtomicCommitStage:
    """Step 9 (``ATOMIC_COMMIT``) — reservation + permit in ONE"""

    def __init__(
        self,
        log: AtomicCommitLogPort,
        *,
        writer_epoch: int,
        permit_provider: PermitProvider,
        reservation_id_provider: ReservationIdProvider,
        time_permits_new_risk: Callable[[], bool],
        effect_envelope_reader: EffectEnvelopeReader,
        position_effect_reader: Callable[[], str | None] | None = None,
        close_proof_fence_reader: CloseProofFenceProvider | None = None,
    ) -> None:
        self._log = log
        self._writer_epoch = writer_epoch
        self._permit_provider = permit_provider
        self._reservation_id_provider = reservation_id_provider
        self._time_permits_new_risk = time_permits_new_risk
        self._effect_envelope_reader = effect_envelope_reader
        self._position_effect_reader = position_effect_reader
        self._close_proof_fence_reader = close_proof_fence_reader

    def _transition(
        self,
        request: StageRequest,
        reservation_id: str,
        *,
        position_effect: str | None,
    ) -> CapacityReservationTransition | StageVerdict:
        """The ``COMMITTED_UNBOUND`` transition this commit writes, carrying step 5's envelope"""
        envelope = self._effect_envelope_reader()
        if envelope is None or not envelope.components:
            return _unknown(
                CommitmentStep.ATOMIC_COMMIT,
                "no step-5 economic effect envelope to record as this reservation's "
                "committed vector — committing without one would hide its usage from ARE",
            )
        committed_vector = envelope
        if position_effect == _CLOSE_EFFECT:
            committed_vector = CapacityVector(
                components=tuple(
                    component.model_copy(
                        update={
                            "magnitude": (
                                None
                                if component.magnitude is None
                                else -component.magnitude
                            )
                        }
                    )
                    for component in envelope.components
                )
            )
        return CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=self._writer_epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.COMMITTED_UNBOUND,
            scope=ReservationScope(
                account=request.instrument_key.account,
                instrument=request.instrument_key.instrument,
            ),
            committed_vector=committed_vector,
        )

    def _expected_seq(
        self,
        request: StageRequest,
        *,
        position_effect: str | None,
        view: LogView,
    ) -> int | StageVerdict:
        """Return step 9's CAS coordinate, or a restrictive CLOSE-fence verdict."""
        expected_seq = -1 if view.last_seq is None else view.last_seq
        if position_effect != _CLOSE_EFFECT:
            return expected_seq
        if self._close_proof_fence_reader is None:
            return _unknown(
                CommitmentStep.ATOMIC_COMMIT,
                "no step-6 CLOSE proof fence provider is configured",
            )
        try:
            fence = self._close_proof_fence_reader(request)
        except Exception as exc:  # noqa: BLE001 - proof lookup cannot grant a close
            return _unknown(
                CommitmentStep.ATOMIC_COMMIT,
                f"step-6 CLOSE proof fence unavailable: {type(exc).__name__}",
            )
        if type(fence) is SyntheticCloseEntryFence:
            if not synthetic_close_fence_valid(
                fence, request, writer_epoch=self._writer_epoch, view=view
            ):
                return _unknown(
                    CommitmentStep.ATOMIC_COMMIT,
                    "step-6 synthetic CLOSE bound is not current for this exact "
                    "scope/proposal, does not fit the proven entry, or was read at "
                    "another RCL revision",
                )
            return fence.rcl_last_seq
        if type(fence) is not CloseProofCommitFence:
            return _unknown(
                CommitmentStep.ATOMIC_COMMIT,
                "step-6 CLOSE proof fence is missing or has an invalid type",
            )
        if not close_proof_fence_matches_request(fence, request):
            return _unknown(
                CommitmentStep.ATOMIC_COMMIT,
                "step-6 CLOSE proof fence is not current for this exact scope/proposal",
            )
        if not close_proof_fence_matches_view(
            fence, writer_epoch=self._writer_epoch, view=view
        ):
            return _unknown(
                CommitmentStep.ATOMIC_COMMIT,
                "RCL epoch/tip changed since the step-6 CLOSE proof was observed",
            )
        if type(fence.verified_rcl_last_seq) is not int:
            return _unknown(
                CommitmentStep.ATOMIC_COMMIT,
                "step-6 CLOSE proof has no verified current RCL tip",
            )
        return fence.verified_rcl_last_seq

    def _apply_transition(
        self,
        transition: CapacityReservationTransition,
        *,
        claim_nonce: str,
        permit_digest: str,
        permit: ActionFlowPermit,
        expected_seq: int,
    ) -> StageVerdict:
        """Write the one atomic reservation/permit entry and map its structural result."""
        try:
            result = self._log.apply_reservation_transition(
                transition,
                cause=TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
                command_type=_COMMIT_RESERVATION_KIND,
                command_id=claim_nonce,
                command_digest=permit_digest,
                expected_seq=expected_seq,
            )
        except ReservationTransitionRefusal as exc:
            return StageVerdict(
                step=CommitmentStep.ATOMIC_COMMIT,
                outcome=StageOutcome.DENY,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                reason=f"reservation lifecycle gate refused: {exc}",
            )
        except (sqlite3.Error, OSError) as exc:
            return _unknown(
                CommitmentStep.ATOMIC_COMMIT,
                f"RCL log unreachable during commit: {type(exc).__name__}: {exc}",
            )
        if isinstance(result, AppendRefusal):
            outcome = (
                StageOutcome.UNKNOWN
                if result.reason in _CAS_UNKNOWN_REASONS
                else StageOutcome.DENY
            )
            return StageVerdict(
                step=CommitmentStep.ATOMIC_COMMIT,
                outcome=outcome,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                bound_identity=permit.permit_id,
                reason=f"append refused: {result.reason}: {result.detail}",
            )
        return StageVerdict(
            step=CommitmentStep.ATOMIC_COMMIT,
            outcome=StageOutcome.ADMIT,
            authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
            native_verdict_type="AppendReceipt",
            bound_digest=permit_digest,
            bound_identity=permit.permit_id,
            reason=(
                f"reservation {transition.reservation_id!r} committed at seq={result.seq} "
                f"with bound permit {permit.permit_id!r}"
            ),
        )

    def __call__(self, request: StageRequest) -> StageVerdict:
        gate = _time_gate(self._time_permits_new_risk, CommitmentStep.ATOMIC_COMMIT)
        if gate is not None:
            return gate
        try:
            position_effect = (
                request.proposal.position_effect
                if self._position_effect_reader is None
                else self._position_effect_reader()
            )
        except (
            Exception
        ) as exc:  # noqa: BLE001 - an unknown effect cannot grant a commit
            return _unknown(
                CommitmentStep.ATOMIC_COMMIT,
                f"position effect unavailable: {type(exc).__name__}",
            )
        permit = self._permit_provider(request)
        if permit is None:
            return _unknown(
                CommitmentStep.ATOMIC_COMMIT,
                "no Action Flow Permit is available to bind this commit",
            )
        binding = permit_reservation_binding(permit)
        if binding is None:
            return _unknown(
                CommitmentStep.ATOMIC_COMMIT,
                "permit.claim_nonce/.canonical_digest absent — cannot bind the "
                "reservation commit to it",
            )
        claim_nonce, permit_digest = binding
        reservation_id = self._reservation_id_provider(request, permit)
        if reservation_id is None:
            return _unknown(
                CommitmentStep.ATOMIC_COMMIT,
                "the bound permit carries no identity — this attempt's reservation cannot "
                "be named",
            )
        transition = self._transition(
            request, reservation_id, position_effect=position_effect
        )
        if isinstance(transition, StageVerdict):
            return transition
        try:
            view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        except StaleEpochRead as exc:
            return _unknown(CommitmentStep.ATOMIC_COMMIT, f"stale writer epoch: {exc}")
        except (sqlite3.Error, OSError) as exc:
            return _unknown(
                CommitmentStep.ATOMIC_COMMIT,
                f"RCL log unreachable: {type(exc).__name__}: {exc}",
            )
        expected_seq = self._expected_seq(
            request, position_effect=position_effect, view=view
        )
        if isinstance(expected_seq, StageVerdict):
            return expected_seq
        return self._apply_transition(
            transition,
            claim_nonce=claim_nonce,
            permit_digest=permit_digest,
            permit=permit,
            expected_seq=expected_seq,
        )


class CommitmentUnavailabilityStage:
    """Step 10 (``COMMITMENT_UNAVAILABILITY``) — a genuinely independent"""

    def __init__(
        self,
        reader: ReservationProjectionReader,
        *,
        expected_state: CapacityState = CapacityState.COMMITTED_UNBOUND,
    ) -> None:
        self._reader = reader
        self._expected_state = expected_state

    def __call__(self, request: StageRequest) -> StageVerdict:
        commit_verdict = _find_verdict(
            request.prior_verdicts, CommitmentStep.ATOMIC_COMMIT
        )
        if commit_verdict is None or commit_verdict.outcome is not StageOutcome.ADMIT:
            return _unknown(
                CommitmentStep.COMMITMENT_UNAVAILABILITY,
                "no admitted step-9 commit to confirm",
            )
        reservation_id = reservation_id_in_scope(
            request.instrument_key, commit_verdict.bound_identity
        )
        if reservation_id is None:
            return _unknown(
                CommitmentStep.COMMITMENT_UNAVAILABILITY,
                "step 9's admitted verdict names no Action Flow Permit identity — the "
                "reservation it committed cannot be identified for an independent re-read",
            )
        try:
            state = self._reader.reservation_state(reservation_id)
        except (sqlite3.Error, OSError) as exc:
            return _unknown(
                CommitmentStep.COMMITMENT_UNAVAILABILITY,
                f"RCL projection unreachable: {type(exc).__name__}: {exc}",
            )
        if state is None or not capacity_at_least_as_conservative(
            state, self._expected_state
        ):
            return _unknown(
                CommitmentStep.COMMITMENT_UNAVAILABILITY,
                f"committed state of {reservation_id!r} not confirmed by independent "
                f"re-read (observed={state})",
            )
        return StageVerdict(
            step=CommitmentStep.COMMITMENT_UNAVAILABILITY,
            outcome=StageOutcome.ADMIT,
            authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
            bound_digest=commit_verdict.bound_digest,
            bound_identity=commit_verdict.bound_identity,
            reason=(
                f"commit durability of {reservation_id!r} independently confirmed: "
                f"state={state}"
            ),
        )


def item15_fields(
    permit: ActionFlowPermit | None, *, commitment_current: bool | None
) -> Mapping[str, object]:
    """The gateway ``SendBoundaryContext`` item-15 fields for one attempt."""
    return {
        "action_flow_permit_identity": None if permit is None else permit.permit_id,
        "action_flow_commitment_current": commitment_current,
    }
