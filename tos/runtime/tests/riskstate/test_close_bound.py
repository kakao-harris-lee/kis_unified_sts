"""CLOSE quantity bounds for a SYNTHETIC transport tree, and the stock entry cap (#1011, L3).

A ``SYNTHETIC_FUTURES_ORDER`` tree has no broker to ask for a held position, so before #1011
``RiskStateService`` answered every CLOSE with ``PROVIDER_NOT_CONFIGURED`` and step 6 stayed
``UNKNOWN`` — a filled synthetic entry sealed its scope until the contract month rolled. For
that transport the durable evidence store IS the broker, so the bound here is
``close_within_entry(entry FULL_FILL, proven prior closes, q)`` read off the RCL + evidence
store, and the step-9 fence is a second, independent read of the same facts.

The stock (``kis-mock``) path keeps its broker-held proof and additionally caps the close at
what remains of the TOS entry (#1012 L3): shares held outside TOS are not TOS capacity.

Everything here is hermetic: ``tmp_path`` SQLite only, no network, no ambient env.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest
from tos.are import AdverseScenarioKind, AdverseScenarioSet
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl.proposal import Proposal
from tos.egressgw.records import CandidateConstruction, QuantityDerivation
from tos.engine.records import InstrumentKey, StageRequest
from tos.engine.vocabulary import CommitmentStep
from tos.ordering import OrderingEvent
from tos.rcl import (
    AppendRefusal,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos.spg import GovernedDimensionLimit, HardSafetyEnvelope
from tos.venue import ActionClass
from tos.workload import RuntimeIdentity
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.rcl.reservation_identity import permit_reservation_id
from tos_runtime.recon.ports import WitnessScope
from tos_runtime.risk.ledger_stages import (
    SyntheticCloseEntryFence,
    synthetic_close_fence_valid,
)
from tos_runtime.riskstate.close_bound import (
    CloseAuthoritySource,
    DurableEntryCloseBoundReader,
)
from tos_runtime.riskstate.flow_observation import InboxFlowReader
from tos_runtime.riskstate.held_position import HeldPositionProof, PositionSide, RclTip
from tos_runtime.riskstate.policies import (
    load_action_flow_policy,
    load_aggregate_risk_policy,
)
from tos_runtime.riskstate.position import EvidencePositionReader
from tos_runtime.riskstate.service import RiskStateService

from ._documents import action_flow_policy_yaml, aggregate_risk_policy_yaml

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_ACCOUNT = "88888888-01"
_INSTRUMENT = "101W09"
_KEY = InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT)
_ARE_DIM_ID = "INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL"
_ENTRY_ATTEMPT = "attempt-close-bound-entry"
_ENTRY_PERMIT = "afg-permit-close-bound-entry"
_PRIOR_CLOSE_ATTEMPT = "attempt-close-bound-prior"
_PRIOR_CLOSE_PERMIT = "afg-permit-close-bound-prior"
_PROPOSAL_ID = "prop-close-bound-1"
_TRADING_DATE = "20261030"


# ===========================================================================
# Durable seeding — the exact rows the production path writes
# ===========================================================================


def _entry_reservation_id() -> str:
    return str(permit_reservation_id(_ACCOUNT, _INSTRUMENT, _ENTRY_PERMIT))


def _prior_close_reservation_id() -> str:
    return str(permit_reservation_id(_ACCOUNT, _INSTRUMENT, _PRIOR_CLOSE_PERMIT))


def _record_join(
    store: SqliteEvidenceStore, *, attempt_id: str, permit_identity: str
) -> None:
    """The two durable rows ``tos_runtime.rcl.reservation_lookup`` joins on ``event_id``."""
    event_id = f"evt-{attempt_id}"
    store.append(
        {
            "kind": "FLOW_STEP_ADMITTED",
            "step": "ATOMIC_COMMIT",
            "event_id": event_id,
            "bound_identity": permit_identity,
        },
        kind="FLOW_STEP_ADMITTED",
        record_class="FLOW_STEP_ADMITTED",
    )
    store.append(
        {
            "kind": "ATTEMPT_REQUEST_CREATED",
            "event_id": event_id,
            "attempt_id": attempt_id,
        },
        kind="ATTEMPT_REQUEST_CREATED",
        record_class="ATTEMPT_REQUEST_CREATED",
    )


def _commit(
    rcl_log: SqliteCommitLog,
    *,
    reservation_id: str,
    from_state: CapacityState,
    to_state: CapacityState,
    command_id: str,
    command_type: CommandType,
    cause: TransitionCause,
    finality_witness: bool | None,
) -> None:
    identity = RuntimeIdentity(
        cell_id="close-bound-test-cell", process_nonce="close-bound-test-nonce"
    )
    epoch = rcl_log.current_epoch() or rcl_log.acquire_epoch(identity)
    view = rcl_log.read_linearizable(writer_epoch=epoch)
    receipt = rcl_log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=epoch,
            from_state=from_state,
            to_state=to_state,
            scope=ReservationScope(account=_ACCOUNT, instrument=_INSTRUMENT),
        ),
        cause,
        command_type=command_type,
        command_id=command_id,
        command_digest=command_id,
        expected_seq=-1 if view.last_seq is None else view.last_seq,
        finality_witness=finality_witness,
    )
    assert not isinstance(receipt, AppendRefusal), receipt


def _commit_other_scope(rcl_log: SqliteCommitLog) -> None:
    """Advance the log's tip with a reservation of a DIFFERENT scope.

    The tip is log-wide, the bound is scope-wide: this is the shape of advance that must NOT
    withdraw a fence, because nothing about this scope's proven entry changed.
    """
    identity = RuntimeIdentity(
        cell_id="close-bound-test-cell", process_nonce="close-bound-test-nonce"
    )
    epoch = rcl_log.current_epoch() or rcl_log.acquire_epoch(identity)
    view = rcl_log.read_linearizable(writer_epoch=epoch)
    receipt = rcl_log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id="resv-other-scope-close-bound",
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.POTENTIALLY_LIVE,
            scope=ReservationScope(account=_ACCOUNT, instrument="OTHER-SYMBOL"),
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id="cmd-close-bound-other-scope",
        command_digest="cmd-close-bound-other-scope",
        expected_seq=-1 if view.last_seq is None else view.last_seq,
        finality_witness=None,
    )
    assert not isinstance(receipt, AppendRefusal), receipt


def _record_full_fill(
    store: SqliteEvidenceStore, *, attempt_id: str, filled: Decimal
) -> None:
    """One terminal ``FULL_FILL`` receipt plus the finality proof that makes it provable."""
    store.append(
        {
            "attempt_id": attempt_id,
            "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
            "egress_result_kind": "FULL_FILL",
            "filled_quantity": format(filled, "f"),
            "remaining_quantity": "0",
            "broker_execution_id": f"exec-{attempt_id}",
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )
    store.append(
        {"idempotency_key": f"synthetic-fqp-proof:{attempt_id}"},
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )


def _record_release_intent(
    store: SqliteEvidenceStore, *, attempt_id: str, reservation_id: str, proof_id: str
) -> None:
    store.append(
        {
            "attempt_id": attempt_id,
            "reservation_id": reservation_id,
            "destination": CapacityState.RELEASED.value,
            "proof_id": proof_id,
        },
        kind="CAPACITY_RELEASE_INTENT",
        record_class="CAPACITY_RELEASE_INTENT",
    )


def _record_release_held(
    store: SqliteEvidenceStore, *, attempt_id: str, reservation_id: str, reason: str
) -> None:
    store.append(
        {
            "attempt_id": attempt_id,
            "reservation_id": reservation_id,
            "reason": reason,
        },
        kind="CAPACITY_RELEASE_HELD",
        record_class="CAPACITY_RELEASE_HELD",
    )


def _seed_filled_entry(
    rcl_log: SqliteCommitLog, store: SqliteEvidenceStore, *, quantity: Decimal
) -> None:
    """A filled OPEN: its reservation at ``POSITION_CONSUMED`` and its FULL_FILL on record."""
    _record_join(store, attempt_id=_ENTRY_ATTEMPT, permit_identity=_ENTRY_PERMIT)
    _commit(
        rcl_log,
        reservation_id=_entry_reservation_id(),
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=CapacityState.POSITION_CONSUMED,
        command_id="cmd-close-bound-entry",
        command_type=CommandType.RELEASE_RESERVATION,
        cause=TransitionCause.FINAL_QUANTITY_PROOF,
        finality_witness=True,
    )
    _record_full_fill(store, attempt_id=_ENTRY_ATTEMPT, filled=quantity)


def _seed_prior_close(
    rcl_log: SqliteCommitLog,
    store: SqliteEvidenceStore,
    *,
    quantity: Decimal,
    proven: bool = True,
) -> None:
    """A completed close of the seeded entry — fully proven, or deliberately not."""
    _record_join(
        store, attempt_id=_PRIOR_CLOSE_ATTEMPT, permit_identity=_PRIOR_CLOSE_PERMIT
    )
    _commit(
        rcl_log,
        reservation_id=_prior_close_reservation_id(),
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=CapacityState.POTENTIALLY_LIVE,
        command_id="cmd-close-bound-prior",
        command_type=CommandType.BIND_ATTEMPT,
        cause=TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        finality_witness=None,
    )
    _commit(
        rcl_log,
        reservation_id=_prior_close_reservation_id(),
        from_state=CapacityState.POTENTIALLY_LIVE,
        to_state=CapacityState.RELEASED,
        command_id=f"release-{_PRIOR_CLOSE_ATTEMPT}",
        command_type=CommandType.RELEASE_RESERVATION,
        cause=TransitionCause.FINAL_QUANTITY_PROOF,
        finality_witness=True,
    )
    _record_release_intent(
        store,
        attempt_id=_PRIOR_CLOSE_ATTEMPT,
        reservation_id=_prior_close_reservation_id(),
        proof_id="proof-close-bound-prior",
    )
    _record_release_held(
        store,
        attempt_id=_PRIOR_CLOSE_ATTEMPT,
        reservation_id=_entry_reservation_id(),
        reason="QUANTITY_UNPROVEN",
    )
    if proven:
        _record_full_fill(store, attempt_id=_PRIOR_CLOSE_ATTEMPT, filled=quantity)


# ===========================================================================
# Service construction
# ===========================================================================


def _hse() -> HardSafetyEnvelope:
    return HardSafetyEnvelope(
        governed_dimensions=(
            GovernedDimensionLimit(
                dimension=_ARE_DIM_ID, envelope_max=Decimal("100"), unit="CONTRACTS"
            ),
        )
    )


def _scenario_set() -> AdverseScenarioSet:
    scenario_set = AdverseScenarioSet.issue(
        scheme=_SCHEME,
        scenario_set_id="close-bound-scenario-set",
        scenario_set_generation=1,
        policy_binding_id=None,
        covered_scenario_kinds=(
            AdverseScenarioKind.ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ,
        ),
        evidence_package_ref=None,
    )
    assert isinstance(scenario_set, AdverseScenarioSet)
    return scenario_set


def _construction(quantity: Decimal) -> CandidateConstruction:
    return CandidateConstruction.model_construct(
        derivation=QuantityDerivation.model_construct(quantity=quantity)
    )


def _stage_request(
    step: CommitmentStep = CommitmentStep.AGGREGATE_RISK_DECISION,
) -> StageRequest:
    return StageRequest.model_construct(
        step=step,
        instrument_key=_KEY,
        proposal=Proposal.model_construct(proposal_id=_PROPOSAL_ID),
        reference=OrderingEvent.model_construct(
            event_id="root-event-close-bound", causal_predecessor_ids=()
        ),
        prior_verdicts=(),
        attempt=None,
        value_view=None,
        held_position_magnitude=None,
    )


def _service(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
    *,
    quantity: Decimal,
    close_authority: CloseAuthoritySource,
    held_position_proof_reader: (
        Callable[[StageRequest, str], HeldPositionProof | None] | None
    ) = None,
) -> RiskStateService:
    are_path = tmp_path / "aggregate_risk_policy.yaml"
    are_path.write_text(
        aggregate_risk_policy_yaml(
            instrument_scope=f'["{_INSTRUMENT}"]',
            account_scope=f'["{_ACCOUNT}"]',
            effective_limit_value="100",
        ),
        encoding="utf-8",
    )
    afg_path = tmp_path / "action_flow_policy.yaml"
    afg_path.write_text(
        action_flow_policy_yaml(account_scope=f'["{_ACCOUNT}"]'), encoding="utf-8"
    )
    are_policy = load_aggregate_risk_policy(are_path, scheme=_SCHEME)
    afg_policy = load_action_flow_policy(afg_path, scheme=_SCHEME)
    bound_reader = DurableEntryCloseBoundReader(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        projection=SqliteReservationProjectionReader(rcl_log),
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
    )
    return RiskStateService(
        are_policy=are_policy,
        afg_policy=afg_policy,
        scheme=_SCHEME,
        hse_envelope=_hse(),
        scenario_set=_scenario_set(),
        required_scenario_kinds=are_policy.required_scenario_kinds,
        position_reader=EvidencePositionReader(
            evidence_store,
            account=_ACCOUNT,
            instrument=_INSTRUMENT,
            buy_side_token="BUY",
            sell_side_token="SELL",
        ),
        flow_reader=InboxFlowReader(inbox, evidence_store, rcl_log, scheme=_SCHEME),
        rcl_log=rcl_log,
        construction_stage_reader=lambda: _construction(quantity),
        effect_envelope_reader=lambda: None,
        rcl_tip_reader=lambda: 1,
        monotonic_reader=lambda: 1_000,
        max_attempts_reader=lambda: 4,
        current_seq_reader=lambda: None,
        evidence_store=evidence_store,
        environment_label="close-bound-test",
        action_class=ActionClass.CLOSE,
        action_class_reader=lambda: ActionClass.CLOSE,
        attempt_arm_direction_reader=lambda: PositionSide.LONG.value,
        held_position_proof_reader=held_position_proof_reader,
        held_position_currentness_reader=None,
        close_authority=close_authority,
        entry_close_bound_reader=bound_reader.read,
        activated_member_digests=("are-digest", "afg-digest"),
    )


def _close_effect(service: RiskStateService) -> tuple[Decimal | None, dict]:
    """Step 6's derived command effect and its durable close-effect audit row."""
    inputs = service.aggregate_inputs_for(_stage_request())
    assert inputs is not None
    effects = {cell.max_credible_command_effect for cell in inputs.cells}
    assert len(effects) == 1
    row = service._evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'RISK_STATE_OBSERVED' "
        "ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    import json

    audit = json.loads(row[0])["payload"]["close_effect"]
    assert isinstance(audit, dict)
    return effects.pop(), audit


# ===========================================================================
# #1011 — SYNTHETIC transport: the durable evidence store is the broker
# ===========================================================================


def test_synthetic_close_of_a_whole_entry_passes_step6_and_the_step9_fence(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
) -> None:
    """Entry FULL_FILL 1, CLOSE 1: step 6 grants ``-1`` and step 9 rebinds the same facts."""
    _seed_filled_entry(rcl_log, evidence_store, quantity=Decimal("1"))
    service = _service(
        tmp_path,
        evidence_store,
        inbox,
        rcl_log,
        quantity=Decimal("1"),
        close_authority=CloseAuthoritySource.DURABLE_EVIDENCE,
    )
    effect, audit = _close_effect(service)
    assert effect == Decimal("-1")
    assert audit["proof_status"] == "PROOF_ACCEPTED"
    assert audit["entry_remaining"] == "1"

    request = _stage_request(step=CommitmentStep.ATOMIC_COMMIT)
    fence = service.take_close_fence(request)
    assert type(fence) is SyntheticCloseEntryFence
    assert fence.entry_quantity == Decimal("1")
    assert fence.prior_closed == Decimal("0")
    assert fence.proposed_quantity == Decimal("1")
    view = rcl_log.read_linearizable(writer_epoch=fence.rcl_writer_epoch)
    assert synthetic_close_fence_valid(
        fence, request, writer_epoch=fence.rcl_writer_epoch, view=view
    )
    # The fence is one-use: a second take has nothing left to hand step 9.
    assert service.take_close_fence(request) is None


def test_synthetic_close_over_the_entry_quantity_is_refused(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
) -> None:
    """Entry FULL_FILL 1, CLOSE 2: the proposed quantity does not fit the proven entry."""
    _seed_filled_entry(rcl_log, evidence_store, quantity=Decimal("1"))
    service = _service(
        tmp_path,
        evidence_store,
        inbox,
        rcl_log,
        quantity=Decimal("2"),
        close_authority=CloseAuthoritySource.DURABLE_EVIDENCE,
    )
    effect, audit = _close_effect(service)
    assert effect is None
    assert audit["proof_status"] == "QUANTITY_EXCEEDS_ENTRY"
    assert (
        service.take_close_fence(_stage_request(step=CommitmentStep.ATOMIC_COMMIT))
        is None
    )


def test_synthetic_split_close_admits_the_remainder_and_refuses_more(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
) -> None:
    """Entry 2 with one proven close of 1: CLOSE 1 grants, CLOSE 2 is refused."""
    _seed_filled_entry(rcl_log, evidence_store, quantity=Decimal("2"))
    _seed_prior_close(rcl_log, evidence_store, quantity=Decimal("1"))
    admitting = _service(
        tmp_path,
        evidence_store,
        inbox,
        rcl_log,
        quantity=Decimal("1"),
        close_authority=CloseAuthoritySource.DURABLE_EVIDENCE,
    )
    effect, audit = _close_effect(admitting)
    assert effect == Decimal("-1")
    assert audit["proof_status"] == "PROOF_ACCEPTED"
    assert audit["entry_remaining"] == "1"

    refusing = _service(
        tmp_path,
        evidence_store,
        inbox,
        rcl_log,
        quantity=Decimal("2"),
        close_authority=CloseAuthoritySource.DURABLE_EVIDENCE,
    )
    effect, audit = _close_effect(refusing)
    assert effect is None
    assert audit["proof_status"] == "QUANTITY_EXCEEDS_ENTRY"


def test_synthetic_close_stays_unknown_while_a_prior_close_is_unproven(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
) -> None:
    """A released prior close with no proven FULL_FILL leaves the remainder unknown."""
    _seed_filled_entry(rcl_log, evidence_store, quantity=Decimal("2"))
    _seed_prior_close(rcl_log, evidence_store, quantity=Decimal("1"), proven=False)
    service = _service(
        tmp_path,
        evidence_store,
        inbox,
        rcl_log,
        quantity=Decimal("1"),
        close_authority=CloseAuthoritySource.DURABLE_EVIDENCE,
    )
    effect, audit = _close_effect(service)
    assert effect is None
    assert audit["proof_status"] == "ENTRY_BOUND_UNPROVEN"
    assert audit["entry_bound_refusal"] == "FILL_UNPROVEN"
    assert (
        service.take_close_fence(_stage_request(step=CommitmentStep.ATOMIC_COMMIT))
        is None
    )


def test_synthetic_close_stays_unknown_without_any_consumed_entry(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
) -> None:
    """No ``POSITION_CONSUMED`` row at all: there is no entry to bound a CLOSE by."""
    service = _service(
        tmp_path,
        evidence_store,
        inbox,
        rcl_log,
        quantity=Decimal("1"),
        close_authority=CloseAuthoritySource.DURABLE_EVIDENCE,
    )
    effect, audit = _close_effect(service)
    assert effect is None
    assert audit["proof_status"] == "ENTRY_BOUND_UNPROVEN"
    assert audit["entry_bound_refusal"] == "ENTRY_NOT_SOLE_CONSUMED_POSITION"


# ===========================================================================
# #1012 L3 — the stock path caps at what remains of the TOS entry
# ===========================================================================


def _held_proof(quantity: Decimal) -> HeldPositionProof:
    return HeldPositionProof(
        scope=WitnessScope(
            account=_ACCOUNT, instrument_keys=(_KEY,), as_of_generation=7
        ),
        proposal_id=_PROPOSAL_ID,
        side=PositionSide.LONG,
        held_quantity=quantity,
        trading_date=_TRADING_DATE,
        age_origin_ms=0,
        observed_at_generation=7,
        provenance="kis-mock-stock",
        rcl_tip=RclTip(writer_epoch=1, last_seq=7),
        max_age_ms=30_000,
    )


def test_stock_close_is_capped_by_the_tos_entry_not_the_whole_holding(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
) -> None:
    """Broker holds 5 shares, the TOS entry is 1: a CLOSE of 2 is refused (#1012 L3).

    Before this cap, ``close_within_entry(held, 0, q)`` admitted any ``q <= 5``, so TOS could
    sell four shares it never bought — and the entry then refused to discharge
    (``CLOSED_OVER_ENTRY``), sealing the scope.
    """
    _seed_filled_entry(rcl_log, evidence_store, quantity=Decimal("1"))
    service = _service(
        tmp_path,
        evidence_store,
        inbox,
        rcl_log,
        quantity=Decimal("2"),
        close_authority=CloseAuthoritySource.BROKER_HELD_PROOF,
        held_position_proof_reader=lambda _request, _direction: _held_proof(
            Decimal("5")
        ),
    )
    effect, audit = _close_effect(service)
    assert effect is None
    assert audit["proof_status"] == "QUANTITY_EXCEEDS_HELD"
    assert audit["held_quantity"] == "5"
    assert audit["entry_remaining"] == "1"


def test_stock_close_within_both_the_holding_and_the_entry_is_admitted(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
) -> None:
    """The same account, a CLOSE of 1: inside the holding AND inside the TOS entry."""
    _seed_filled_entry(rcl_log, evidence_store, quantity=Decimal("1"))
    service = _service(
        tmp_path,
        evidence_store,
        inbox,
        rcl_log,
        quantity=Decimal("1"),
        close_authority=CloseAuthoritySource.BROKER_HELD_PROOF,
        held_position_proof_reader=lambda _request, _direction: _held_proof(
            Decimal("5")
        ),
    )
    effect, audit = _close_effect(service)
    assert effect == Decimal("-1")
    assert audit["proof_status"] == "PROOF_ACCEPTED"


def test_stock_close_stays_unknown_when_the_entry_bound_is_unproven(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
) -> None:
    """A valid held proof is not enough on its own — the TOS entry must be provable too."""
    service = _service(
        tmp_path,
        evidence_store,
        inbox,
        rcl_log,
        quantity=Decimal("1"),
        close_authority=CloseAuthoritySource.BROKER_HELD_PROOF,
        held_position_proof_reader=lambda _request, _direction: _held_proof(
            Decimal("5")
        ),
    )
    effect, audit = _close_effect(service)
    assert effect is None
    assert audit["proof_status"] == "QUANTITY_UNKNOWN"
    assert audit["entry_remaining"] is None


def test_synthetic_authority_never_consumes_a_broker_held_proof(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
) -> None:
    """A synthetic tree has no broker; wiring one by accident must not change the bound."""
    _seed_filled_entry(rcl_log, evidence_store, quantity=Decimal("1"))
    consumed: list[str] = []

    def _reader(_request: StageRequest, direction: str) -> HeldPositionProof:
        consumed.append(direction)
        return _held_proof(Decimal("5"))

    service = _service(
        tmp_path,
        evidence_store,
        inbox,
        rcl_log,
        quantity=Decimal("2"),
        close_authority=CloseAuthoritySource.DURABLE_EVIDENCE,
        held_position_proof_reader=_reader,
    )
    effect, audit = _close_effect(service)
    assert effect is None
    assert audit["proof_status"] == "QUANTITY_EXCEEDS_ENTRY"
    assert consumed == []


@pytest.mark.parametrize("source", list(CloseAuthoritySource))
def test_close_authority_source_is_a_closed_two_member_vocabulary(
    source: CloseAuthoritySource,
) -> None:
    """Pins the dispatch vocabulary the composition root selects by transport kind."""
    assert source.value in ("BROKER_HELD_PROOF", "DURABLE_EVIDENCE")
    assert len(CloseAuthoritySource) == 2


# ===========================================================================
# review-1015 M1/L1 — what happens to the step-6 stash between step 6 and step 9
# ===========================================================================


def _granted_close(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
) -> RiskStateService:
    """Seed entry 1, let step 6 grant a CLOSE of 1, and leave the fence stash armed."""
    _seed_filled_entry(rcl_log, evidence_store, quantity=Decimal("1"))
    service = _service(
        tmp_path,
        evidence_store,
        inbox,
        rcl_log,
        quantity=Decimal("1"),
        close_authority=CloseAuthoritySource.DURABLE_EVIDENCE,
    )
    effect, _audit = _close_effect(service)
    assert effect == Decimal("-1")
    return service


def test_a_competing_reservation_committed_after_step6_withdraws_the_fence(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
) -> None:
    """A second outstanding reservation lands between step 6 and step 9: no fence is minted.

    Concrete input: step 6 grants, then another attempt commits its own reservation into the
    same scope. The fence re-read now sees two outstanding rows, which is not the shape a
    CLOSE may be bounded in, so step 9 gets ``None`` and answers UNKNOWN. Nothing about the
    already-granted step-6 effect can resurrect it.
    """
    service = _granted_close(tmp_path, evidence_store, inbox, rcl_log)
    _record_join(
        evidence_store,
        attempt_id="attempt-close-bound-competing",
        permit_identity="afg-permit-close-bound-competing",
    )
    _commit(
        rcl_log,
        reservation_id=permit_reservation_id(
            _ACCOUNT, _INSTRUMENT, "afg-permit-close-bound-competing"
        ),
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=CapacityState.POTENTIALLY_LIVE,
        command_id="cmd-close-bound-competing",
        command_type=CommandType.BIND_ATTEMPT,
        cause=TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        finality_witness=None,
    )

    assert (
        service.take_close_fence(_stage_request(step=CommitmentStep.ATOMIC_COMMIT))
        is None
    )


def test_an_approval_only_tip_advance_still_mints_a_fence_at_the_new_tip(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
) -> None:
    """The one tolerated advance: the log moved, but the proven entry facts did not.

    This is exactly the claim the PR body makes — a tip advance is tolerated *because* the
    fence carries the RE-READ tip, which step 9 then requires to equal its own view. A commit
    that changes this scope's reservations is the previous test; this one does not.
    """
    service = _granted_close(tmp_path, evidence_store, inbox, rcl_log)
    epoch = rcl_log.current_epoch()
    assert epoch is not None
    before = rcl_log.read_linearizable(writer_epoch=epoch).last_seq
    _commit_other_scope(rcl_log)
    after = rcl_log.read_linearizable(writer_epoch=epoch).last_seq
    assert before is not None and after is not None and after > before

    fence = service.take_close_fence(_stage_request(step=CommitmentStep.ATOMIC_COMMIT))
    assert type(fence) is SyntheticCloseEntryFence
    assert fence.rcl_last_seq == after, (fence.rcl_last_seq, before, after)


def test_a_writer_epoch_change_after_step6_withdraws_the_fence(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
) -> None:
    """Another writer took the log: the step-6 reading belongs to a superseded epoch."""
    service = _granted_close(tmp_path, evidence_store, inbox, rcl_log)
    rcl_log.acquire_epoch(
        RuntimeIdentity(cell_id="close-bound-other-cell", process_nonce="other-nonce")
    )

    assert (
        service.take_close_fence(_stage_request(step=CommitmentStep.ATOMIC_COMMIT))
        is None
    )


def test_the_fence_is_minted_under_the_step6_proposal_not_the_step9_request(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
) -> None:
    """review-1015 L1 — the stash carries step 6's proposal id, so the check can fail.

    Before this binding, ``synthetic_close_fence`` copied the step-9 request's own id into the
    fence and ``synthetic_close_fence_valid`` then compared that value with itself. Here step 9
    arrives under a DIFFERENT proposal than the one step 6 credited, and gets nothing.
    """
    service = _granted_close(tmp_path, evidence_store, inbox, rcl_log)
    other = StageRequest.model_construct(
        step=CommitmentStep.ATOMIC_COMMIT,
        instrument_key=_KEY,
        proposal=Proposal.model_construct(proposal_id="prop-close-bound-OTHER"),
        reference=OrderingEvent.model_construct(
            event_id="root-event-close-bound", causal_predecessor_ids=()
        ),
        prior_verdicts=(),
        attempt=None,
        value_view=None,
        held_position_magnitude=None,
    )

    assert service.take_close_fence(other) is None
