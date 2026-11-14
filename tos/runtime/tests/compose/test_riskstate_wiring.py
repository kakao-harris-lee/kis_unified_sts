"""``tos_runtime.riskstate.service.RiskStateService`` /"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from tos.afg import ActionClassKind
from tos.are import AdverseScenarioKind, AdverseScenarioSet
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl.proposal import Proposal
from tos.egressgw.records import CandidateConstruction, QuantityDerivation
from tos.engine.records import (
    EgressResultPayload,
    EngineEvent,
    InstrumentKey,
    StageRequest,
)
from tos.engine.vocabulary import CommitmentStep, EgressResultKind, EventKind
from tos.ioc import AxisBinding, ConformanceAxis
from tos.ordering import OrderingEvent
from tos.venue import ActionClass
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose._riskstate_wiring import (
    RiskPolicyScopeMismatch,
    build_risk_state_service,
)
from tos_runtime.compose._types import RiskStateConfigError
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.recon.ports import WitnessScope, WitnessSnapshot
from tos_runtime.risk.ledger_stages import CloseProofCommitFence
from tos_runtime.riskstate.close_bound import EntryCloseBound
from tos_runtime.riskstate.flow_observation import (
    REPLAYS_DEFINITION,
    FlowObservation,
    InboxFlowReader,
)
from tos_runtime.riskstate.held_position import (
    HeldPositionCell,
    HeldPositionConfig,
    HeldPositionCurrentness,
    HeldPositionProof,
    PositionSide,
    RclTip,
)
from tos_runtime.riskstate.policies import (
    VenuePolicyConfigError,
    load_action_flow_policy,
    load_aggregate_risk_policy,
)
from tos_runtime.riskstate.position import EvidencePositionReader, PositionObservation
from tos_runtime.riskstate.service import RiskStateService

from ..riskstate._documents import (
    action_flow_policy_yaml,
    aggregate_risk_policy_yaml,
)
from . import _fixtures as fx
from . import _symmetry_fixtures as sfx
from .conftest import (
    _RISK_STATE_ENVELOPE_MAX,
    approve_constructed_intent,
    call_wrapped_fixture,
    write_approval_file,
)
from .conftest import config_dir as _config_dir_fixture
from .conftest import config_dir_with_risk_state as _config_dir_with_risk_state_fixture
from .conftest import custody_root as _custody_root_fixture
from .conftest import data_dir as _data_dir_fixture

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_ACCOUNT = "88888888-01"
_INSTRUMENT = "ES"
_ARE_DIM_ID = "INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL"
_AFG_DIM_ID = "afg.ORDER"


class _FixedKeyProvider:
    """Mirrors ``tests/riskstate/conftest.py``'s own re-declared double (that module's own"""

    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes-riskstate-wiring-suite")

    def generations(self) -> tuple[int, ...]:
        return (1,)

    def key_for(self, generation: int) -> bytes:
        del generation
        return b"test-fixed-key-bytes-riskstate-wiring-suite"


@pytest.fixture
def evidence_store(tmp_path: Path) -> Iterator[SqliteEvidenceStore]:
    key_provider: KeyProvider = _FixedKeyProvider()
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=key_provider
    )
    yield instance
    instance.close()


@pytest.fixture
def inbox(tmp_path: Path) -> Iterator[SqliteEventInbox]:
    instance = SqliteEventInbox(tmp_path / "inbox.sqlite3", scheme=_SCHEME)
    yield instance
    instance.close()


@pytest.fixture
def rcl_log(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> Iterator[SqliteCommitLog]:
    instance = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=evidence_store)
    yield instance
    instance.close()


def _seed_send_sealed(
    store: SqliteEvidenceStore,
    *,
    attempt_id: str,
    side: str,
    quantity: str,
    event_id: str = "root-event-1",
) -> None:
    """Mirrors ``tests/riskstate/conftest.py::seed_send_sealed`` exactly (cross-suite import"""
    payload = {
        "kind": "SEND_SEALED",
        "attempt_id": attempt_id,
        "send_seal": {
            "attempt_id": attempt_id,
            "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
            "outbound_side": side,
            "outbound_quantity": quantity,
            "reference": {"event_id": event_id, "causal_predecessor_ids": []},
        },
    }
    store.append(payload, kind="SEND_SEALED", record_class="SEND_SEALED")


def _seed_egress_result(
    store: SqliteEvidenceStore,
    *,
    kind: str,
    attempt_id: str,
    filled_quantity: str | None,
    result_disposition: str | None = None,
) -> None:
    """Mirrors ``tests/riskstate/conftest.py::seed_egress_result`` exactly (including"""
    payload = {
        "attempt_id": attempt_id,
        "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
        "egress_result_kind": "FULL_FILL" if filled_quantity is not None else "ACK",
        "filled_quantity": filled_quantity,
        "remaining_quantity": None,
        "result_disposition": result_disposition,
    }
    store.append(payload, kind=kind, record_class=kind)


def _seed_recovery_marker(
    store: SqliteEvidenceStore,
    *,
    kind: str,
    event_id: str,
    handling_started_evidence_seq: int | None = None,
) -> None:
    """Mirrors ``tests/riskstate/conftest.py::seed_recovery_marker`` exactly — the"""
    payload: dict[str, object] = {"event_id": event_id}
    if handling_started_evidence_seq is not None:
        payload["handling_started_evidence_seq"] = handling_started_evidence_seq
    store.append(payload, kind=kind, record_class=kind)


def _stage_request(
    *, step: CommitmentStep, proposal_id: str = "prop-1", event_id: str = "root-event-1"
) -> StageRequest:
    """A ``StageRequest`` built via ``model_construct`` (module docstring) — the proposal's"""
    proposal = Proposal.model_construct(proposal_id=proposal_id)
    key = InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT)
    reference = OrderingEvent.model_construct(
        event_id=event_id, causal_predecessor_ids=()
    )
    return StageRequest.model_construct(
        step=step,
        instrument_key=key,
        proposal=proposal,
        reference=reference,
        prior_verdicts=(),
        attempt=None,
        value_view=None,
        held_position_magnitude=None,
    )


def _scenario_set() -> AdverseScenarioSet:
    scenario_set = AdverseScenarioSet.issue(
        scheme=_SCHEME,
        scenario_set_id="riskstate-wiring-scenario-set",
        scenario_set_generation=1,
        policy_binding_id=None,
        covered_scenario_kinds=(
            AdverseScenarioKind.ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ,
        ),
        evidence_package_ref=None,
    )
    assert isinstance(scenario_set, AdverseScenarioSet)
    return scenario_set


def _service(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
    *,
    max_attempts: int | None = 4,
    action_class: ActionClass = ActionClass.NEW_LONG,
    action_class_reader: Callable[[], ActionClass] | None = None,
    rcl_tip_reader: Callable[[], int | None] | None = None,
    envelope_max_value: str = "1",
    effective_limit_value: str = "1",
    current_seq_reader: Callable[[], int | None] | None = None,
    monotonic_reader: Callable[[], int | None] | None = None,
    construction: CandidateConstruction | None = None,
    attempt_arm_direction_reader: Callable[[], str | None] | None = None,
    held_position_proof_reader: (
        Callable[[StageRequest, str], HeldPositionProof | None] | None
    ) = None,
    held_position_currentness_reader: (
        Callable[[HeldPositionProof], HeldPositionCurrentness | None] | None
    ) = None,
    entry_close_bound_reader: Callable[[], EntryCloseBound] | None = None,
) -> RiskStateService:
    are_path = tmp_path / "aggregate_risk_policy.yaml"
    are_path.write_text(
        aggregate_risk_policy_yaml(
            instrument_scope=f'["{_INSTRUMENT}"]',
            account_scope=f'["{_ACCOUNT}"]',
            effective_limit_value=effective_limit_value,
            envelope_max_value=envelope_max_value,
        ),
        encoding="utf-8",
    )
    afg_path = tmp_path / "action_flow_policy.yaml"
    afg_path.write_text(
        action_flow_policy_yaml(account_scope=f'["{_ACCOUNT}"]'), encoding="utf-8"
    )
    are_policy = load_aggregate_risk_policy(are_path, scheme=_SCHEME)
    afg_policy = load_action_flow_policy(afg_path, scheme=_SCHEME)

    position_reader = EvidencePositionReader(
        evidence_store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    )
    flow_reader = InboxFlowReader(inbox, evidence_store, rcl_log, scheme=_SCHEME)
    return RiskStateService(
        are_policy=are_policy,
        afg_policy=afg_policy,
        scheme=_SCHEME,
        scenario_set=_scenario_set(),
        required_scenario_kinds=are_policy.required_scenario_kinds,
        position_reader=position_reader,
        flow_reader=flow_reader,
        rcl_log=rcl_log,
        construction_stage_reader=lambda: construction,
        effect_envelope_reader=lambda: None,
        rcl_tip_reader=(rcl_tip_reader if rcl_tip_reader is not None else (lambda: 1)),
        monotonic_reader=(
            monotonic_reader if monotonic_reader is not None else (lambda: 1_000)
        ),
        max_attempts_reader=lambda: max_attempts,
        current_seq_reader=(
            current_seq_reader if current_seq_reader is not None else (lambda: None)
        ),
        evidence_store=evidence_store,
        environment_label="riskstate-wiring-test",
        action_class=action_class,
        action_class_reader=action_class_reader,
        attempt_arm_direction_reader=attempt_arm_direction_reader,
        held_position_proof_reader=held_position_proof_reader,
        held_position_currentness_reader=held_position_currentness_reader,
        entry_close_bound_reader=entry_close_bound_reader,
        activated_member_digests=("are-activation-digest", "afg-activation-digest"),
    )


class TestAggregateInputsFor:
    def test_empty_evidence_yields_zero_usage_cells(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None
        assert len(inputs.cells) == 1
        cell = inputs.cells[0]
        assert cell.conservative_current_usage == Decimal("0")
        assert cell.conservative_current_usage_already_committed == Decimal("0")
        assert cell.required_concurrent_overlap_effect == Decimal("0")
        assert cell.effective_limit == Decimal("1")
        assert cell.max_credible_command_effect is None
        assert inputs.all_fields_attributed is None
        assert inputs.numerically_safe is None
        assert inputs.valuation_ok is None
        assert inputs.limit_source_is_injected_envelope is None
        assert inputs.injected_envelope_max is not None
        assert inputs.injected_envelope_max.magnitude(_ARE_DIM_ID) == Decimal("1")
        assert inputs.grant_identity == "prop-1"
        assert inputs.lineage_ref == "root-event-1"

    def test_confirmed_fill_raises_conservative_usage(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        _seed_send_sealed(evidence_store, attempt_id="a1", side="BUY", quantity="3")
        _seed_egress_result(
            evidence_store,
            kind="EGRESS_RESULT_CONSUMED",
            attempt_id="a1",
            filled_quantity="3",
        )
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None
        assert inputs.cells[0].conservative_current_usage == Decimal("3")

    def test_unmatched_result_counts_full_sealed_quantity_as_in_flight_overlap(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """Plan §5 실증 (3): a ``RESULT_UNMATCHED`` attempt's full sealed quantity counts in"""
        _seed_send_sealed(evidence_store, attempt_id="a1", side="BUY", quantity="5")
        _seed_egress_result(
            evidence_store,
            kind="RESULT_UNMATCHED",
            attempt_id="a1",
            filled_quantity=None,
        )
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None
        assert inputs.cells[0].conservative_current_usage == Decimal("0")
        assert inputs.cells[0].required_concurrent_overlap_effect == Decimal("5")

    def test_new_short_mirrors_new_long_usage_magnitude(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """Plan §5 실증 (7): NEW_SHORT mirror — position sign flips, usage magnitude equal."""
        _seed_send_sealed(evidence_store, attempt_id="a1", side="SELL", quantity="4")
        _seed_egress_result(
            evidence_store,
            kind="EGRESS_RESULT_CONSUMED",
            attempt_id="a1",
            filled_quantity="4",
        )
        service = _service(
            tmp_path, evidence_store, inbox, rcl_log, action_class=ActionClass.NEW_SHORT
        )
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None
        assert inputs.cells[0].conservative_current_usage == Decimal("4")

    def test_in_flight_sealed_send_feeds_overlap_effect_not_current_usage(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """Plan §5 실증 (4)'s own position-side half: a sealed send with NO terminal result"""
        _seed_send_sealed(evidence_store, attempt_id="a1", side="BUY", quantity="2")
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None
        assert inputs.cells[0].conservative_current_usage == Decimal("0")
        assert inputs.cells[0].required_concurrent_overlap_effect == Decimal("2")

    def test_close_without_a_broker_holding_proof_has_unknown_effect(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        construction = CandidateConstruction.model_construct(
            derivation=QuantityDerivation.model_construct(quantity=Decimal("60"))
        )
        service = _service(
            tmp_path,
            evidence_store,
            inbox,
            rcl_log,
            action_class_reader=lambda: ActionClass.CLOSE,
            construction=construction,
        )

        inputs = service.aggregate_inputs_for(
            _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        )

        assert inputs is not None
        assert inputs.cells[0].max_credible_command_effect is None

    def test_cell_proof_bounds_close_effect_to_confirmed_holding(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """Only a fresh two-view broker proof lets step 6 credit a bounded CLOSE."""

        class Clock:
            def now_ms(self) -> int:
                return 1_000

            def today(self) -> str:
                return "20261029"

        scope = WitnessScope(
            account=_ACCOUNT,
            instrument_keys=(InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT),),
            as_of_generation=9,
        )
        tip = RclTip(writer_epoch=2, last_seq=9)
        verified_tip = RclTip(writer_epoch=2, last_seq=10)
        current_tip = [tip]
        cell = HeldPositionCell(
            config=HeldPositionConfig(max_age_ms=500),
            clock=Clock(),
            rcl_tip_reader=lambda: current_tip[0],
            tip_compatible=lambda origin, current: origin == tip
            and current == verified_tip,
        )
        snapshot = WitnessSnapshot(
            observed_at_generation=9,
            orders=(),
            positions=((_INSTRUMENT, Decimal("80")),),
            positions_complete=True,
            provenance="kis-mock-stock",
            independent_of_evidence_store=True,
            order_inquiry_date="20261029",
        )
        token = cell.mark_pending(scope)
        assert cell.publish(
            scope,
            snapshot,
            confirming_snapshot=snapshot,
            age_origin_ms=900,
            confirming_age_origin_ms=950,
            trading_date="20261029",
            rcl_tip_at_start=tip,
            pending_token=token,
        )
        current_tip[0] = verified_tip

        def consume_proof(
            request: StageRequest, direction: str
        ) -> HeldPositionProof | None:
            return cell.consume(
                scope,
                PositionSide(direction),
                proposal_id=request.proposal.proposal_id,
            )

        construction = CandidateConstruction.model_construct(
            derivation=QuantityDerivation.model_construct(quantity=Decimal("60"))
        )
        entry_bound = EntryCloseBound(
            account=_ACCOUNT,
            instrument=_INSTRUMENT,
            entry_reservation_id="resv-riskstate-wiring-entry",
            entry_attempt_id="attempt-riskstate-wiring-entry",
            entry_quantity=Decimal("80"),
            prior_closed=Decimal("0"),
            rcl_writer_epoch=2,
            rcl_last_seq=9,
            refusal=None,
        )
        service = _service(
            tmp_path,
            evidence_store,
            inbox,
            rcl_log,
            action_class_reader=lambda: ActionClass.CLOSE,
            construction=construction,
            attempt_arm_direction_reader=lambda: PositionSide.LONG.value,
            held_position_proof_reader=consume_proof,
            held_position_currentness_reader=cell.validate_consumed,
            entry_close_bound_reader=lambda: entry_bound,
        )

        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)

        assert inputs is not None
        assert inputs.cells[0].max_credible_command_effect == Decimal("-60")
        fence = service.take_close_fence(request)
        assert isinstance(fence, CloseProofCommitFence)
        assert fence.proposal_id == "prop-1"
        assert fence.as_of_generation == 9
        assert fence.rcl_last_seq == 9
        assert fence.verified_rcl_last_seq == 10

    def test_records_risk_state_observed_evidence(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        service.aggregate_inputs_for(request)
        cursor = evidence_store.connection.execute(
            "SELECT kind FROM entries ORDER BY seq ASC"
        )
        kinds = [row[0] for row in cursor.fetchall()]
        assert "RISK_STATE_OBSERVED" in kinds
        assert "AGGREGATE_RISK_POLICY_BOUND" in kinds
        assert "ACTION_FLOW_POLICY_BOUND" in kinds

    def test_injected_envelope_max_is_hse_bound_not_policy_effective_limit(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """HIGH-3 (review of PR #704, 2026-09-16): every OTHER test in this suite sets the HSE"""
        service = _service(
            tmp_path,
            evidence_store,
            inbox,
            rcl_log,
            envelope_max_value="5",
            effective_limit_value="100",
        )
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None
        assert inputs.injected_envelope_max is not None
        assert inputs.injected_envelope_max.magnitude(_ARE_DIM_ID) == Decimal("5")
        assert inputs.effective_limit is not None
        assert inputs.effective_limit.magnitude(_ARE_DIM_ID) == Decimal("100")
        from tos.are.predicates import envelope_bound_not_enlarged

        assert (
            envelope_bound_not_enlarged(
                decision_effective_limit=inputs.effective_limit,
                injected_envelope_max=inputs.injected_envelope_max,
                limit_source_is_injected_envelope=True,
            )
            is False
        )


class TestActionFlowInputsFor:
    def test_none_rcl_tip_yields_none_inputs(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        service._rcl_tip_reader = lambda: None
        request = _stage_request(step=CommitmentStep.ACTION_FLOW_DECISION)
        assert service.action_flow_inputs_for(request) is None

    def test_uncovered_action_class_yields_none_inputs(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        service = _service(
            tmp_path, evidence_store, inbox, rcl_log, action_class=ActionClass.AMEND
        )
        request = _stage_request(step=CommitmentStep.ACTION_FLOW_DECISION)
        assert service.action_flow_inputs_for(request) is None

    def test_a_close_attempt_is_judged_as_an_exit_not_as_the_boot_class(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """#960 — the attempt's own action class decides step 7's kind: a CLOSE is an"""
        service = _service(
            tmp_path,
            evidence_store,
            inbox,
            rcl_log,
            action_class=ActionClass.NEW_LONG,
            action_class_reader=lambda: ActionClass.CLOSE,
        )
        request = _stage_request(step=CommitmentStep.ACTION_FLOW_DECISION)
        inputs = service.action_flow_inputs_for(request)
        assert inputs is not None
        assert inputs.action_class is ActionClassKind.ORDINARY_REDUCE_OR_EXIT

    def test_an_uncovered_attempt_class_yields_none_inputs(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """#960 fail-closed: an attempt whose class the policy does not map is UNKNOWN, never"""
        service = _service(
            tmp_path,
            evidence_store,
            inbox,
            rcl_log,
            action_class=ActionClass.NEW_LONG,
            action_class_reader=lambda: ActionClass.AMEND,
        )
        request = _stage_request(step=CommitmentStep.ACTION_FLOW_DECISION)
        assert service.action_flow_inputs_for(request) is None

    def test_happy_path_shape(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        request = _stage_request(step=CommitmentStep.ACTION_FLOW_DECISION)
        inputs = service.action_flow_inputs_for(request)
        assert inputs is not None
        assert inputs.action_class is ActionClassKind.NORMAL_NEW_RISK
        assert inputs.decision_generation == 1
        assert inputs.generation_current is False
        assert inputs.producer_self_declared_scope is False
        assert inputs.economic_ref == f"resv-{_ACCOUNT}-{_INSTRUMENT}"
        assert inputs.committed_flow_vectors == ()
        assert inputs.flow_vector is not None
        assert inputs.flow_vector.magnitude(_AFG_DIM_ID) == Decimal("1")
        assert inputs.cause is not None
        assert inputs.cause.root_cause_identity == "root-event-1"
        assert inputs.cause.forked_beyond_bound is False
        assert inputs.snapshot is not None
        assert inputs.snapshot.snapshot_generation == 1
        assert inputs.limit_source_is_injected_envelope is None
        assert inputs.economic_commitment_exclusive is None
        assert inputs.flow_commitment_exclusive is None

    def test_max_attempts_none_leaves_forked_beyond_bound_unknown(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        service = _service(tmp_path, evidence_store, inbox, rcl_log, max_attempts=None)
        request = _stage_request(step=CommitmentStep.ACTION_FLOW_DECISION)
        inputs = service.action_flow_inputs_for(request)
        assert inputs is not None
        assert inputs.cause is not None
        assert inputs.cause.forked_beyond_bound is None

    def test_decision_generation_tracks_rcl_tip_reader(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """HIGH-1 (review of PR #704, 2026-09-16): every OTHER test in this suite (and every"""
        tip_values = iter([7, 8])
        service = _service(
            tmp_path,
            evidence_store,
            inbox,
            rcl_log,
            rcl_tip_reader=lambda: next(tip_values),
        )
        request = _stage_request(step=CommitmentStep.ACTION_FLOW_DECISION)

        first = service.action_flow_inputs_for(request)
        assert first is not None
        assert first.decision_generation == 7

        second_request = _stage_request(
            step=CommitmentStep.ACTION_FLOW_DECISION, proposal_id="prop-2"
        )
        second = service.action_flow_inputs_for(second_request)
        assert second is not None
        assert second.decision_generation == 8

    def test_elapsed_monotonic_ms_consumes_real_handling_started_receipt(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """Re-review residual of HIGH-4 (review of PR #704, 2026-09-16): the earlier fix pinned"""
        payload = EgressResultPayload(
            instrument_key=InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT),
            attempt_id="prop-1",
            kind=EgressResultKind.ACK,
        )
        event = EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
        receipt = inbox.enqueue(event)
        marker = evidence_store.append(
            {"event_id": receipt.event_id},
            kind="EVENT_HANDLING_STARTED",
            record_class="EVENT_HANDLING_STARTED",
        )
        assert marker.seq is not None and marker.key_generation is not None
        inbox.mark_handling_started(
            receipt.seq, evidence_seq=marker.seq, generation=marker.key_generation
        )
        started_ns = next(
            entry.appended_at_monotonic_ns
            for entry in evidence_store.iter_entry_meta()
            if entry.seq == marker.seq
        )
        started_ms = started_ns // 1_000_000
        expected_elapsed_ms = 5_000
        service = _service(
            tmp_path,
            evidence_store,
            inbox,
            rcl_log,
            current_seq_reader=lambda: receipt.seq,
            monotonic_reader=lambda: started_ms + expected_elapsed_ms,
        )
        request = _stage_request(step=CommitmentStep.ACTION_FLOW_DECISION)
        inputs = service.action_flow_inputs_for(request)
        assert inputs is not None
        assert inputs.observed_amplification is not None
        assert inputs.observed_amplification.elapsed_monotonic == Decimal(
            expected_elapsed_ms
        )


def _read_last_observed_absent_fields(evidence_store: SqliteEvidenceStore) -> list[str]:
    """Reads the most recently appended ``RISK_STATE_OBSERVED`` row's own ``absent_fields``"""
    import json

    row = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'RISK_STATE_OBSERVED' "
        "ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "no RISK_STATE_OBSERVED row was recorded"
    payload = json.loads(row[0])["payload"]
    absent = payload["absent_fields"]
    assert isinstance(absent, list)
    return absent


def _read_last_risk_state_observed(evidence_store: SqliteEvidenceStore) -> dict:
    """Reads the most recently appended ``RISK_STATE_OBSERVED`` row's FULL payload dict —"""
    import json

    row = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'RISK_STATE_OBSERVED' "
        "ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "no RISK_STATE_OBSERVED row was recorded"
    payload = json.loads(row[0])["payload"]
    assert isinstance(payload, dict)
    return payload


class TestAbsentFieldsHonesty:
    def test_isolated_flow_absence_reports_exactly_the_one_remaining_structural_gap(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """HIGH-2, isolated form: calls the private ``_record_observation`` directly (module"""
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        flow_obs = FlowObservation(
            queue_depth=0,
            in_flight=0,
            attempts_for_cause=0,
            duplicates_rejected=0,
            replays=0,
            root_event_seq=3,
            handling_started_monotonic=123456,
            lineage_found=True,
            sources=("inbox:current_seq",),
            replays_definition=REPLAYS_DEFINITION,
        )
        position_obs = PositionObservation(
            scope_key=f"{_ACCOUNT}::{_INSTRUMENT}",
            confirmed_net=Decimal("0"),
            unknown_buy=Decimal("0"),
            unknown_sell=Decimal("0"),
            in_flight_buy=Decimal("0"),
            in_flight_sell=Decimal("0"),
            attempts_seen=0,
            sources=(),
        )
        service._record_observation(
            attempt_id="prop-isolated",
            position_obs=position_obs,
            flow_obs=flow_obs,
            committed_vectors=(),
            extra_absent=(),
        )
        absent = _read_last_observed_absent_fields(evidence_store)
        assert absent == ["committed_flow_vectors"]

    def test_real_first_attempt_absent_fields_include_only_the_one_remaining_gap(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """HIGH-2, realistic form: drives the SAME real ``aggregate_inputs_for`` path a brand"""
        payload = EgressResultPayload(
            instrument_key=InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT),
            attempt_id="prop-1",
            kind=EgressResultKind.ACK,
        )
        event = EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
        receipt = inbox.enqueue(event)
        marker = evidence_store.append(
            {"event_id": receipt.event_id},
            kind="EVENT_HANDLING_STARTED",
            record_class="EVENT_HANDLING_STARTED",
        )
        assert marker.seq is not None and marker.key_generation is not None
        inbox.mark_handling_started(
            receipt.seq, evidence_seq=marker.seq, generation=marker.key_generation
        )
        service = _service(
            tmp_path,
            evidence_store,
            inbox,
            rcl_log,
            current_seq_reader=lambda: receipt.seq,
        )
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None

        absent = set(_read_last_observed_absent_fields(evidence_store))
        assert "committed_flow_vectors" in absent
        assert "duplicates_rejected" not in absent
        assert "replays" not in absent
        assert "root_event_seq" not in absent
        assert "handling_started_monotonic" not in absent
        assert "lineage_found" not in absent


def _write_riskstate_wiring_config(
    tmp_path: Path,
    *,
    account: str = _ACCOUNT,
    instrument: str = _INSTRUMENT,
    action_class_map: str | None = None,
    buy_side_token: str = "BUY",
    sell_side_token: str = "SELL",
    omit_envelope_max: bool = False,
) -> Path:
    """A minimal, self-contained config directory for"""
    directory = tmp_path / "riskstate-config"
    directory.mkdir()
    (directory / "aggregate_risk_policy.yaml").write_text(
        aggregate_risk_policy_yaml(
            instrument_scope=f'["{instrument}"]',
            account_scope=f'["{account}"]',
            omit_envelope_max=omit_envelope_max,
        ),
        encoding="utf-8",
    )
    (directory / "action_flow_policy.yaml").write_text(
        action_flow_policy_yaml(
            account_scope=f'["{account}"]',
            action_class_map=action_class_map,
            buy_side_token=buy_side_token,
            sell_side_token=sell_side_token,
        ),
        encoding="utf-8",
    )
    return directory


def _build_service_from_wiring_config(
    directory: Path,
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
    *,
    venue_allowed_sides: frozenset[str] = frozenset({"BUY", "SELL"}),
    scenario_set: AdverseScenarioSet | None = None,
) -> RiskStateService:
    del tmp_path
    construction = fx.construction_config()
    return build_risk_state_service(
        config_dir=directory,
        scheme=_SCHEME,
        construction=construction,
        environment_label="riskstate-wiring-test",
        evidence_store=evidence_store,
        inbox=inbox,
        rcl_log=rcl_log,
        scenario_set=scenario_set if scenario_set is not None else _scenario_set(),
        required_scenario_kinds=frozenset(
            {AdverseScenarioKind.ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ}
        ),
        rcl_tip_reader=lambda: 1,
        monotonic_reader=lambda: 1_000,
        max_attempts_reader=lambda: 4,
        construction_stage_reader=lambda: None,
        effect_envelope_reader=lambda: None,
        venue_allowed_sides=venue_allowed_sides,
    )


class TestBuildRiskStateServiceCrossChecks:
    def test_happy_path_builds(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        directory = _write_riskstate_wiring_config(tmp_path)
        service = _build_service_from_wiring_config(
            directory, tmp_path, evidence_store, inbox, rcl_log
        )
        assert isinstance(service, RiskStateService)

    def test_account_mismatch_refuses(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        directory = _write_riskstate_wiring_config(
            tmp_path, account="some-other-account"
        )
        with pytest.raises(RiskPolicyScopeMismatch, match="account_scope"):
            _build_service_from_wiring_config(
                directory, tmp_path, evidence_store, inbox, rcl_log
            )

    def test_a_governed_dimension_with_no_declared_ceiling_refuses(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        'Plan S2-a: the "every ARE-governed dimension has a real envelope ceiling"'
        directory = _write_riskstate_wiring_config(tmp_path, omit_envelope_max=True)
        with pytest.raises(VenuePolicyConfigError, match="envelope_max"):
            _build_service_from_wiring_config(
                directory, tmp_path, evidence_store, inbox, rcl_log
            )

    def test_scenario_coverage_gap_refuses(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        directory = _write_riskstate_wiring_config(tmp_path)
        empty_scenario_set = AdverseScenarioSet.issue(
            scheme=_SCHEME,
            scenario_set_id="empty-scenario-set",
            scenario_set_generation=1,
            policy_binding_id=None,
            covered_scenario_kinds=(),
            evidence_package_ref=None,
        )
        assert isinstance(empty_scenario_set, AdverseScenarioSet)
        with pytest.raises(RiskPolicyScopeMismatch, match="covered_scenario_kinds"):
            _build_service_from_wiring_config(
                directory,
                tmp_path,
                evidence_store,
                inbox,
                rcl_log,
                scenario_set=empty_scenario_set,
            )

    def test_action_class_not_covered_refuses(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        directory = _write_riskstate_wiring_config(
            tmp_path, action_class_map='{"DECREASE": "ORDINARY_REDUCE_OR_EXIT"}'
        )
        with pytest.raises(RiskPolicyScopeMismatch, match="action_class_map"):
            _build_service_from_wiring_config(
                directory, tmp_path, evidence_store, inbox, rcl_log
            )

    def test_side_token_not_in_venue_allowed_sides_refuses(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        directory = _write_riskstate_wiring_config(tmp_path)
        with pytest.raises(RiskPolicyScopeMismatch, match="side_tokens"):
            _build_service_from_wiring_config(
                directory,
                tmp_path,
                evidence_store,
                inbox,
                rcl_log,
                venue_allowed_sides=frozenset({"LONG", "SHORT"}),
            )


def test_compose_paper_runtime_refuses_when_files_absent_and_a_provider_is_none(
    config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Plan §3 "run 차단 목록" — the shared ``config_dir`` fixture never carries"""
    fx.write_band_strategy_file(config_dir)
    with pytest.raises(RiskStateConfigError):
        compose_paper_runtime(
            config_dir,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=None,
            action_flow_inputs_provider=None,
        )


def test_compose_paper_runtime_with_explicit_providers_leaves_risk_state_none(
    config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Plan §5 실증 (8): explicit providers are still honored when the two policy files are"""
    from tos_runtime.risk.aggregate import AggregateRiskDecisionInputs
    from tos_runtime.risk.flow import ActionFlowDecisionInputs

    fx.write_band_strategy_file(config_dir)

    def _aggregate(request: object) -> AggregateRiskDecisionInputs | None:
        return None

    def _action_flow(request: object) -> ActionFlowDecisionInputs | None:
        return None

    runtime = compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=_aggregate,
        action_flow_inputs_provider=_action_flow,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )
    assert runtime.risk_state is None


def _fresh_risk_state_dirs(root: Path) -> tuple[Path, Path, Path]:
    """One independent ``(config_dir_with_risk_state, data_dir, custody_root)`` triple under"""
    root.mkdir(parents=True, exist_ok=True)
    config_dir = call_wrapped_fixture(_config_dir_fixture, root)
    config_dir = call_wrapped_fixture(_config_dir_with_risk_state_fixture, config_dir)
    data_dir = call_wrapped_fixture(_data_dir_fixture, root)
    custody_root = call_wrapped_fixture(_custody_root_fixture, root)
    return config_dir, data_dir, custody_root


def _drive_two_calls(runtime, custody_root: Path, event):
    """The SAME two-``run_once``-call pattern ``test_compose_root.py``'s own ADMIT tests use"""
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    approve_constructed_intent(
        runtime,
        custody_root,
        proposal_digest=proposal_digest,
    )
    results2 = runtime.run_once((event,))
    flow = results2[0].flow
    assert flow is not None
    return {v.step.value: v for v in flow.verdicts}


def _evidence_kind_counts(runtime) -> dict[str, int]:
    rows = runtime.evidence_store.connection.execute(
        "SELECT kind FROM entries ORDER BY seq ASC"
    ).fetchall()
    counts: dict[str, int] = {}
    for (kind,) in rows:
        counts[kind] = counts.get(kind, 0) + 1
    return counts


class TestComposeE2E:
    """The plan's own acceptance criterion, driven through the FULL compose stack with no"""

    def test_first_attempt_reaches_aggregate_risk_grant(
        self,
        config_dir_with_risk_state: Path,
        data_dir: Path,
        custody_root: Path,
    ) -> None:
        """Plan §5 실증 (1) — no explicit providers, the production"""
        fx.write_band_strategy_file(config_dir_with_risk_state)
        runtime = compose_paper_runtime(
            config_dir_with_risk_state,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=None,
            action_flow_inputs_provider=None,
            wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
        )
        assert runtime.risk_state is not None

        captured_action_flow_inputs = []
        original_action_flow_inputs_for = runtime.risk_state.action_flow_inputs_for

        def _spy(request):
            result = original_action_flow_inputs_for(request)
            if result is not None:
                captured_action_flow_inputs.append(result)
            return result

        runtime.risk_state.action_flow_inputs_for = _spy  # type: ignore[method-assign]

        event = fx.crossing_event()
        verdict_by_step = _drive_two_calls(runtime, custody_root, event)

        are_verdict = verdict_by_step["AGGREGATE_RISK_DECISION"]
        assert are_verdict.outcome.value == "ADMIT", are_verdict.reason
        assert are_verdict.native_verdict_value == "GRANT"

        afg_verdict = verdict_by_step["ACTION_FLOW_DECISION"]
        assert afg_verdict.outcome.value == "ADMIT", (
            "expected step 7 GRANT (module docstring's own 'Resolved' section) — got "
            f"{afg_verdict.outcome.value}: {afg_verdict.reason}"
        )
        assert afg_verdict.native_verdict_value == "GRANT"

        assert captured_action_flow_inputs, (
            "action_flow_inputs_for was never called with a non-None result — the spy "
            "captured nothing"
        )
        first_attempt_inputs = captured_action_flow_inputs[0]
        assert first_attempt_inputs.observed_amplification is not None
        assert first_attempt_inputs.observed_amplification.elapsed_monotonic is not None
        assert (
            first_attempt_inputs.observed_amplification.duplicate_redelivery_expansion
            == 0
        )
        assert (
            first_attempt_inputs.observed_amplification.failover_reconnect_replay_expansion
            == 0
        )

        counts = _evidence_kind_counts(runtime)
        assert counts.get("AGGREGATE_RISK_POLICY_BOUND") == 1
        assert counts.get("ACTION_FLOW_POLICY_BOUND") == 1
        assert counts.get("RISK_STATE_OBSERVED") == 1

        observed_row = _read_last_risk_state_observed(runtime.evidence_store)
        flow_row = observed_row["flow"]
        assert flow_row["duplicates_rejected"] == 0
        assert flow_row["replays"] == 0
        assert flow_row["replays_definition"] == REPLAYS_DEFINITION
        assert "duplicates_rejected" not in observed_row["absent_fields"]
        assert "replays" not in observed_row["absent_fields"]

    def test_seeded_prior_fill_flips_aggregate_risk_decision_to_deny(
        self,
        config_dir_with_risk_state: Path,
        data_dir: Path,
        custody_root: Path,
    ) -> None:
        """Plan §5 실증 (2) — a durable prior fill large enough to exceed the policy's own"""
        fx.write_band_strategy_file(config_dir_with_risk_state)
        runtime = compose_paper_runtime(
            config_dir_with_risk_state,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=None,
            action_flow_inputs_provider=None,
            wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
        )

        event = fx.crossing_event()
        results = runtime.run_once((event,))
        pipeline = results[0].pipeline
        assert pipeline is not None and pipeline.proposal is not None
        proposal_digest = pipeline.proposal.canonical_digest
        assert proposal_digest is not None
        construction = runtime.construction_stage.construction
        assert construction is not None and construction.intent is not None
        assert construction.intent.canonical_digest is not None
        derived_quantity = construction.derivation.quantity
        assert (
            derived_quantity is not None
        ), "no derived quantity to compute a prior fill from"
        assert derived_quantity > 0, (
            f"derived_quantity {derived_quantity} is not a sane, non-degenerate positive "
            "value — a zero or negative derivation would make the arithmetic below trivially "
            "satisfiable without the plumbing it claims to exercise actually running"
        )
        write_approval_file(
            custody_root,
            proposal_digest=proposal_digest,
            environment_label="non-live-test",
            approved_intent_envelope_digest=construction.intent.canonical_digest,
        )

        envelope_max = Decimal(_RISK_STATE_ENVELOPE_MAX)
        prior_fill = envelope_max - derived_quantity + 1
        assert prior_fill > 0, (
            f"derived_quantity {derived_quantity} leaves no room for a positive prior fill "
            f"under the {envelope_max} effective limit — the fixture's own headroom assumption "
            "no longer holds"
        )
        _seed_send_sealed(
            runtime.evidence_store,
            attempt_id="prior-fill-attempt",
            side="BUY",
            quantity=str(prior_fill),
        )
        _seed_egress_result(
            runtime.evidence_store,
            kind="EGRESS_RESULT_CONSUMED",
            attempt_id="prior-fill-attempt",
            filled_quantity=str(prior_fill),
        )

        results2 = runtime.run_once((event,))
        flow = results2[0].flow
        assert flow is not None
        verdict_by_step = {v.step.value: v for v in flow.verdicts}
        are_verdict = verdict_by_step["AGGREGATE_RISK_DECISION"]
        assert are_verdict.outcome.value == "DENY", are_verdict.reason
        assert are_verdict.native_verdict_value == "DENY"

    def test_duplicate_dispositions_beyond_envelope_flip_action_flow_decision_to_unknown(
        self,
        config_dir_with_risk_state: Path,
        data_dir: Path,
        custody_root: Path,
    ) -> None:
        """Plan §5 실증 (2), CORRECTED against the real kernel composer (finding, reported —"""
        fx.write_band_strategy_file(config_dir_with_risk_state)
        runtime = compose_paper_runtime(
            config_dir_with_risk_state,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=None,
            action_flow_inputs_provider=None,
            wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
        )
        assert runtime.risk_state is not None
        reader = runtime.risk_state._flow_reader
        original_observe = reader.observe
        seeded = {"done": False}

        def _seeding_observe(*, root_event_id, attempt_id, root_event_seq=None):
            if not seeded["done"]:
                seeded["done"] = True
                _seed_send_sealed(
                    runtime.evidence_store,
                    attempt_id="dup-attempt-1",
                    side="BUY",
                    quantity="1",
                    event_id=root_event_id,
                )
                for _ in range(3):
                    _seed_egress_result(
                        runtime.evidence_store,
                        kind="RESULT_UNMATCHED",
                        attempt_id="dup-attempt-1",
                        filled_quantity=None,
                        result_disposition="DUPLICATE",
                    )
            return original_observe(
                root_event_id=root_event_id,
                attempt_id=attempt_id,
                root_event_seq=root_event_seq,
            )

        reader.observe = _seeding_observe  # type: ignore[method-assign]

        event = fx.crossing_event()
        verdict_by_step = _drive_two_calls(runtime, custody_root, event)
        assert seeded[
            "done"
        ], "InboxFlowReader.observe was never invoked — nothing seeded"
        are_verdict = verdict_by_step["AGGREGATE_RISK_DECISION"]
        assert are_verdict.outcome.value == "ADMIT", are_verdict.reason

        afg_verdict = verdict_by_step["ACTION_FLOW_DECISION"]
        assert afg_verdict.outcome.value == "UNKNOWN", afg_verdict.reason

        observed_row = _read_last_risk_state_observed(runtime.evidence_store)
        assert observed_row["flow"]["duplicates_rejected"] == 3

    def test_recovery_markers_beyond_envelope_flip_action_flow_decision_to_unknown(
        self,
        config_dir_with_risk_state: Path,
        data_dir: Path,
        custody_root: Path,
    ) -> None:
        """Plan §5 실증 (3), CORRECTED against the real kernel composer (same finding as the"""
        fx.write_band_strategy_file(config_dir_with_risk_state)
        runtime = compose_paper_runtime(
            config_dir_with_risk_state,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=None,
            action_flow_inputs_provider=None,
            wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
        )
        assert runtime.risk_state is not None
        reader = runtime.risk_state._flow_reader
        original_observe = reader.observe
        seeded = {"done": False}

        def _seeding_observe(*, root_event_id, attempt_id, root_event_seq=None):
            if not seeded["done"]:
                seeded["done"] = True
                started = reader._resolve_handling_started(root_event_seq)
                content_event_id = None if started is None else started.content_event_id
                assert content_event_id is not None, (
                    "the root row's own content-addressed event_id could not be resolved — "
                    "nothing to seed against"
                )
                for _ in range(2):
                    _seed_recovery_marker(
                        runtime.evidence_store,
                        kind="DECISION_TICK_DROPPED_ON_RECOVERY",
                        event_id=content_event_id,
                    )
                for _ in range(2):
                    _seed_recovery_marker(
                        runtime.evidence_store,
                        kind="HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND",
                        event_id=content_event_id,
                        handling_started_evidence_seq=root_event_seq,
                    )
            return original_observe(
                root_event_id=root_event_id,
                attempt_id=attempt_id,
                root_event_seq=root_event_seq,
            )

        reader.observe = _seeding_observe  # type: ignore[method-assign]

        event = fx.crossing_event()
        verdict_by_step = _drive_two_calls(runtime, custody_root, event)
        assert seeded[
            "done"
        ], "InboxFlowReader.observe was never invoked — nothing seeded"
        are_verdict = verdict_by_step["AGGREGATE_RISK_DECISION"]
        assert are_verdict.outcome.value == "ADMIT", are_verdict.reason

        afg_verdict = verdict_by_step["ACTION_FLOW_DECISION"]
        assert afg_verdict.outcome.value == "UNKNOWN", afg_verdict.reason

        observed_row = _read_last_risk_state_observed(runtime.evidence_store)
        assert observed_row["flow"]["replays"] == 4

    def test_new_short_mirrors_new_long_at_aggregate_risk_grant(
        self, tmp_path: Path
    ) -> None:
        """Plan §5 실증 (7) — the NEW_SHORT mirror (:mod:`tests.compose._symmetry_fixtures`,"""
        config_dir, data_dir, custody_root = _fresh_risk_state_dirs(tmp_path / "short")
        sfx.write_mirrored_strategy_file(config_dir)
        runtime = compose_paper_runtime(
            config_dir,
            data_dir,
            custody_root,
            "non-live-test",
            construction=sfx.mirrored_construction_config(),
            aggregate_risk_inputs_provider=None,
            action_flow_inputs_provider=None,
            wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
        )
        assert runtime.risk_state is not None

        event = fx.crossing_event()
        verdict_by_step = _drive_two_calls(runtime, custody_root, event)
        are_verdict = verdict_by_step["AGGREGATE_RISK_DECISION"]
        assert are_verdict.outcome.value == "ADMIT", are_verdict.reason
        assert are_verdict.native_verdict_value == "GRANT"

        afg_verdict = verdict_by_step["ACTION_FLOW_DECISION"]
        assert afg_verdict.outcome.value == "ADMIT", afg_verdict.reason
        assert afg_verdict.native_verdict_value == "GRANT"

        construction = runtime.construction_stage.construction
        assert construction is not None and construction.envelope is not None
        direction_bindings = [
            b
            for b in construction.envelope.authorized_axis_bindings
            if b.axis is ConformanceAxis.DIRECTION
        ]
        assert direction_bindings == [
            AxisBinding(axis=ConformanceAxis.DIRECTION, value="SHORT")
        ], (
            "the composed envelope's own DIRECTION binding must match the NEW_SHORT action "
            "class, never the shared policy document's LONG axis left unreplaced"
        )
