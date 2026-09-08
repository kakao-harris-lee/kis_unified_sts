"""Engine ``Stage`` realizations for steps 6-10 of the ADR-002-002 §11 Normal
Commitment Flow (design #40 §5 order 5 item 3; slice plan §2 item 3),
replacing ``tos.engine.standins.ProvisionalStandIn`` for those five steps —
the ``tos_runtime.authority.stages.IndependentApprovalStage`` precedent (step
4, lane P): every stage here routes a :class:`~tos.engine.records.StageRequest`
into a real kernel judgement call and wraps the result as a
:class:`~tos.engine.records.StageVerdict`; none of them judges itself, and
none ever emits
:data:`~tos.engine.vocabulary.StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL`.

Steps realized here:

* **6** :class:`AggregateRiskDecisionStage` — routes into
  :meth:`tos_runtime.risk.aggregate.AggregateRiskService.decide`.
* **7** :class:`ActionFlowDecisionStage` — routes into
  :meth:`tos_runtime.risk.flow.ActionFlowGovernor.decide`.
* **8** :class:`LedgerVerificationStage` — ``read_linearizable`` (writer-epoch
  fencing) + the RCL reservation projection, verifying the instrument scope is
  a *fresh* scope eligible to originate a ``COMMITTED_UNBOUND`` reservation
  (:data:`tos_runtime.rcl.gates.INITIAL_RESERVATION_STATES` — a real,
  independent re-check of the ledger, never a self-comparison against this
  stage's own prior output or the engine's separate provisional projection).
* **9** :class:`AtomicCommitStage` — commits the reservation transition AND
  binds the Action Flow Permit's single-use commitment coordinate in ONE
  ``apply_reservation_transition`` call (see this module's own "atomicity"
  section below, and ``tos_runtime.risk.flow``'s module docstring for why a
  literal single-entry full-content merge is not achievable without editing
  ``tos_runtime/rcl/log.py``, out of this lane's write surface).
* **10** :class:`CommitmentUnavailabilityStage` — positively re-confirms step
  9's commit is durable/reachable; never assumes durability from step 9's own
  ADMIT (a genuinely independent re-read).

**Atomicity (step 9, AFG-INV-005 / §13 line 330).** ``AtomicCommitStage`` calls
``SqliteCommitLog.apply_reservation_transition`` exactly ONCE, with
``command_id = permit.claim_nonce`` and ``command_digest = permit.canonical_digest``
(:func:`tos_runtime.risk.flow.permit_reservation_binding`) — the SAME
``BEGIN IMMEDIATE`` ... ``COMMIT`` transaction that commits the reservation
transition ALSO durably claims the permit's single-use nonce (the log's own
``entries.command_id`` ``UNIQUE`` constraint) and fixes its exact digest.
There is **no** second ``append_cas``/transaction for the permit in this
stage — never split into two transactions, per the design directive. The
tradeoff, reported precisely (not silently papered over): the permit's full
field content is NOT itself inside this entry's ``payload_json`` (that shape
is fixed by ``apply_reservation_transition``, out of this lane's write
surface) — it lives in the evidence store instead
(``ActionFlowGovernor.build_permit`` callers are expected to evidence the
built permit separately, e.g. via a caller-side ``evidence.append`` before
invoking this stage, or via ``ActionFlowGovernor.issue_permit``'s own
STANDALONE evidencing when that path is used instead of this fold). What
genuinely IS atomic with the reservation commit — the exclusive claim of the
nonce and the binding digest — is, in the literal sense of "one transaction,
never two".

**Reported ``CommandType`` choice (step 9).** :data:`~tos.rcl.CommandType.COMMIT_RESERVATION`
is an exact match for "commit a reservation" (ADR-002-012 §10 line 294-311) —
no gap to report for this one, unlike ``tos_runtime.risk.flow``'s STANDALONE
permit-issuance path.

**Fault contract (slice plan §2 item 3 "장애 계약"):**

=======================================  ====================================
Contract                                  How this module satisfies it
=======================================  ====================================
RCL log file inaccessible                 Steps 8, 9, 10 catch ``sqlite3.Error``
                                           / ``OSError`` around every log call
                                           and return ``UNKNOWN`` — never a
                                           denial by omission.
stale writer epoch                        Steps 8/9 catch
                                           ``tos_runtime.rcl.log.StaleEpochRead``
                                           (step 8: ``UNKNOWN``; step 9: the
                                           commit itself is refused —
                                           ``UNKNOWN``, the log is unreachable
                                           at the fenced epoch, not a proven
                                           denial).
scenario config null                      Refused at ``AggregateRiskService``
                                           construction time
                                           (``tos_runtime.risk.aggregate.load_adverse_scenario_set``),
                                           before any stage runs.
permit claimed twice                      Step 9's ``apply_reservation_transition``
                                           returns ``AppendRefusal`` with
                                           ``DUPLICATE_COMMAND_ID`` /
                                           ``COMMAND_BYTES_MISMATCH`` for a
                                           reused ``claim_nonce`` (the log's own
                                           ``command_id`` ``UNIQUE`` constraint)
                                           — mapped to ``DENY`` here (§13 line
                                           342 "single-use": even an idempotent-
                                           shaped replay of the SAME permit is
                                           refused, never silently re-admitted).
permit state after restart                Only via replay: step 8/10 read
                                           EXCLUSIVELY through
                                           ``ReservationProjectionReader``/
                                           ``read_linearizable`` — no
                                           in-process cache anywhere in this
                                           module.
=======================================  ====================================

**Time gate.** Steps 6, 7, and 9 (the three steps that would admit *new* risk)
each take an injected ``time_permits_new_risk: Callable[[], bool]`` and refuse
with ``UNKNOWN`` when it is not ``True`` — the composition root wires this to
``tos.time.state_permits_new_normal_risk(time_service.current_snapshot().health_state)``
(never computed in this module — a pure routing concern, per every other
stage's own "the stage does not judge" discipline). Steps 8 and 10 are
verification-only (they admit or refuse an ALREADY-decided commitment, never a
*new* risk) and do not take this gate.

Firewall: stdlib (``sqlite3``) + ``pydantic`` (transitively) + ``tos.engine``
(``records``/``vocabulary`` only) + ``tos.rcl`` + ``tos_runtime.evidence`` +
``tos_runtime.rcl`` (``log``/``gates``/``projection``) +
``tos_runtime.risk`` (self — ``aggregate``/``flow`` siblings) only (R1
allowlist). No ``tos_runtime.authority`` / ``tos_runtime.currentness`` /
``tos_runtime.release`` import (slice plan §5 cross-lane isolation) — any
cross-lane fact this module needs (e.g. the time gate) is received as an
injected callable.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping

from tos.afg import ActionFlowPermit
from tos.engine.records import StageRequest, StageVerdict
from tos.engine.vocabulary import CommitmentStep, StageAuthorityClass, StageOutcome
from tos.rcl import (
    AppendRefusal,
    AppendRefusalReason,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
    capacity_at_least_as_conservative,
)

from tos_runtime.rcl.log import (
    ReservationTransitionRefusal,
    SqliteCommitLog,
    StaleEpochRead,
)
from tos_runtime.rcl.projection import ReservationProjectionReader
from tos_runtime.risk.aggregate import AggregateRiskDecisionInputs, AggregateRiskService
from tos_runtime.risk.flow import (
    ActionFlowDecisionInputs,
    ActionFlowGovernor,
    permit_reservation_binding,
)

__all__ = [
    "ActionFlowDecisionStage",
    "AggregateRiskDecisionStage",
    "AtomicCommitStage",
    "CommitmentUnavailabilityStage",
    "LedgerVerificationStage",
    "item15_fields",
]

#: Step 9's exact ``CommandType`` match (module docstring — no gap).
_COMMIT_RESERVATION_KIND = CommandType.COMMIT_RESERVATION

#: Refusal reasons that mean "the log itself could not be reached/fenced at
#: this moment" — mapped to ``UNKNOWN`` (never a proven denial). Everything
#: else (``DUPLICATE_COMMAND_ID`` / ``COMMAND_BYTES_MISMATCH`` /
#: ``INTEGRITY_VIOLATION``) is a structural refusal of THIS specific attempt —
#: mapped to ``DENY``.
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
ReservationIdProvider = Callable[[StageRequest], str]
GenerationProvider = Callable[[StageRequest], int]


def _unknown(step: CommitmentStep, reason: str) -> StageVerdict:
    """The shared restrictive ``UNKNOWN`` verdict shape every stage below uses."""
    return StageVerdict(
        step=step,
        outcome=StageOutcome.UNKNOWN,
        authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
        reason=reason,
    )


def _time_gate(
    time_permits_new_risk: Callable[[], bool], step: CommitmentStep
) -> StageVerdict | None:
    """Refuse to admit new risk unless the injected time gate reports ``True``.

    Returns:
        A restrictive ``UNKNOWN`` verdict if the gate is not ``True``, else
        ``None`` to let the caller proceed.
    """
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
    """Read one prior step's verdict structurally off the flow so far (구조
    파생 > 자기신고 — the ``tos.engine.sequencer._bindings_from`` precedent)."""
    for verdict in verdicts:
        if verdict.step is step:
            return verdict
    return None


class AggregateRiskDecisionStage:
    """Step 6 (``AGGREGATE_RISK_DECISION``) over a real
    :class:`~tos_runtime.risk.aggregate.AggregateRiskService`."""

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
    """Step 7 (``ACTION_FLOW_DECISION``) over a real
    :class:`~tos_runtime.risk.flow.ActionFlowGovernor`."""

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
    """Map a kernel ``RiskDecisionResult``/``ActionFlowResult`` (both StrEnums
    sharing the same ``GRANT``/``DENY``/``UNKNOWN`` member names) to a
    :class:`~tos.engine.vocabulary.StageOutcome` — by exact string identity,
    never a bare truthiness check (both kernel enums are truthy StrEnums)."""
    if result_value == "GRANT":
        return StageOutcome.ADMIT
    if result_value == "DENY":
        return StageOutcome.DENY
    return StageOutcome.UNKNOWN


class LedgerVerificationStage:
    """Step 8 (``LEDGER_VERIFICATION``) — ``read_linearizable`` + the RCL
    reservation projection (module docstring)."""

    def __init__(
        self,
        log: SqliteCommitLog,
        reader: ReservationProjectionReader,
        *,
        writer_epoch: int,
    ) -> None:
        self._log = log
        self._reader = reader
        self._writer_epoch = writer_epoch

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
            existing_state = self._reader.instrument_state(request.instrument_key)
        except (sqlite3.Error, OSError) as exc:
            return _unknown(
                CommitmentStep.LEDGER_VERIFICATION,
                f"RCL projection unreachable: {type(exc).__name__}: {exc}",
            )
        if existing_state is not None:
            return StageVerdict(
                step=CommitmentStep.LEDGER_VERIFICATION,
                outcome=StageOutcome.DENY,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                reason=(
                    f"scope already holds a committed reservation at "
                    f"{existing_state} — not a fresh scope eligible to "
                    "originate COMMITTED_UNBOUND "
                    "(tos_runtime.rcl.gates.INITIAL_RESERVATION_STATES)"
                ),
            )
        return StageVerdict(
            step=CommitmentStep.LEDGER_VERIFICATION,
            outcome=StageOutcome.ADMIT,
            authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
            reason=(
                "RCL log reachable at the current writer epoch; scope has no "
                "committed reservation"
            ),
        )


class AtomicCommitStage:
    """Step 9 (``ATOMIC_COMMIT``) — reservation + permit in ONE
    ``apply_reservation_transition`` transaction (module docstring's
    atomicity section)."""

    def __init__(
        self,
        log: SqliteCommitLog,
        *,
        writer_epoch: int,
        permit_provider: PermitProvider,
        reservation_id_provider: ReservationIdProvider,
        time_permits_new_risk: Callable[[], bool],
    ) -> None:
        self._log = log
        self._writer_epoch = writer_epoch
        self._permit_provider = permit_provider
        self._reservation_id_provider = reservation_id_provider
        self._time_permits_new_risk = time_permits_new_risk

    def __call__(self, request: StageRequest) -> StageVerdict:
        gate = _time_gate(self._time_permits_new_risk, CommitmentStep.ATOMIC_COMMIT)
        if gate is not None:
            return gate
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
        reservation_id = self._reservation_id_provider(request)
        transition = CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=self._writer_epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.COMMITTED_UNBOUND,
            scope=ReservationScope(
                account=request.instrument_key.account,
                instrument=request.instrument_key.instrument,
            ),
        )
        try:
            view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        except StaleEpochRead as exc:
            return _unknown(CommitmentStep.ATOMIC_COMMIT, f"stale writer epoch: {exc}")
        except (sqlite3.Error, OSError) as exc:
            return _unknown(
                CommitmentStep.ATOMIC_COMMIT,
                f"RCL log unreachable: {type(exc).__name__}: {exc}",
            )
        expected_seq = -1 if view.last_seq is None else view.last_seq
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
                f"reservation {reservation_id!r} committed at seq={result.seq} "
                f"with bound permit {permit.permit_id!r}"
            ),
        )


class CommitmentUnavailabilityStage:
    """Step 10 (``COMMITMENT_UNAVAILABILITY``) — a genuinely independent
    re-read confirming step 9's commit is durable/reachable (module
    docstring); never a self-comparison against step 9's own verdict alone."""

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
        try:
            state = self._reader.instrument_state(request.instrument_key)
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
                f"committed state not confirmed by independent re-read "
                f"(observed={state})",
            )
        return StageVerdict(
            step=CommitmentStep.COMMITMENT_UNAVAILABILITY,
            outcome=StageOutcome.ADMIT,
            authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
            bound_digest=commit_verdict.bound_digest,
            bound_identity=commit_verdict.bound_identity,
            reason=f"commit durability independently confirmed: state={state}",
        )


def item15_fields(
    permit: ActionFlowPermit | None, *, commitment_current: bool | None
) -> Mapping[str, object]:
    """The gateway ``SendBoundaryContext`` item-15 fields for one attempt.

    Args:
        permit: The permit bound to this attempt, or ``None`` if none was
            issued/admitted.
        commitment_current: Whether the permit's RCL commitment is currently
            confirmed (``None`` when genuinely unknown — never coerced to
            ``False``).

    Returns:
        A mapping with exactly ``action_flow_permit_identity`` and
        ``action_flow_commitment_current`` (``tos/src/tos/egressgw/records.py``
        item-15 field names).
    """
    return {
        "action_flow_permit_identity": None if permit is None else permit.permit_id,
        "action_flow_commitment_current": commitment_current,
    }
