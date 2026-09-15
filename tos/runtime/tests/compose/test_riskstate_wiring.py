"""``tos_runtime.riskstate.service.RiskStateService`` /
``tos_runtime.compose._riskstate_wiring.build_risk_state_service`` (TOS risk state service
wave, lane b; ``docs/plans/2026-09-16-tos-risk-state-service-plan.md``).

Two layers, deliberately NOT sharing fixtures across suites (mirrors
``tests/riskstate/conftest.py``'s own "cross-suite imports are forbidden" convention):

* **Unit layer** — :class:`RiskStateService` exercised directly over the SAME hermetic
  evidence/inbox/rcl-log doubles :mod:`tests.riskstate.conftest` uses (re-implemented here,
  not imported, per that module's own convention) plus the SAME
  ``aggregate_risk_policy.yaml``/``action_flow_policy.yaml`` builders from
  :mod:`tests.riskstate._documents` (plain string builders, not pytest fixtures — importing
  those is not a fixture-sharing violation). ``StageRequest``/``Proposal`` are built via
  ``model_construct`` (bypasses pydantic validation) rather than the real decision pipeline —
  a ``Proposal`` is a DRAFT-invariant ``IdDerivedArtifact`` that refuses a non-``None``
  ``proposal_id``/``canonical_digest`` unless properly ``.issue()``-d through a full capsule,
  which this suite's own attempt-identity needs are too shallow to justify building.
* **Wiring layer** — :func:`build_risk_state_service`'s five cross-checks, against a MINIMAL
  config directory this file owns alone (NOT ``tests/compose/conftest.py``'s shared
  ``config_dir`` — that fixture's own ``safety_envelope.yaml``/``safety_activation.yaml``
  serve ~400 other compose e2e tests whose HSE governed-dimension set and activation member
  count must stay exactly as they are; extending it here would risk a regression this suite
  has no way to detect until CI runs the whole compose suite).
* One ``compose_paper_runtime``-level boot-refusal test (``RiskStateConfigError``) using the
  shared ``config_dir`` fixture UNMODIFIED (it never carries the two risk-state policy files,
  so it is the correct fixture for "files absent" cases).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from tos.afg import ActionClassKind
from tos.are import AdverseScenarioKind, AdverseScenarioSet
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl.proposal import Proposal
from tos.engine.records import InstrumentKey, StageRequest
from tos.engine.vocabulary import CommitmentStep
from tos.ordering import OrderingEvent
from tos.spg import GovernedDimensionLimit, HardSafetyEnvelope
from tos.venue import ActionClass
from tos_runtime.compose._riskstate_wiring import (
    RiskPolicyScopeMismatch,
    build_risk_state_service,
)
from tos_runtime.compose._types import RiskStateConfigError
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.riskstate.flow_observation import InboxFlowReader
from tos_runtime.riskstate.policies import (
    load_action_flow_policy,
    load_aggregate_risk_policy,
)
from tos_runtime.riskstate.position import EvidencePositionReader
from tos_runtime.riskstate.service import RiskStateService
from tos_runtime.venue import PolicyNotActivated

from ..riskstate._documents import (
    action_flow_policy_yaml,
    aggregate_risk_policy_yaml,
)
from . import _fixtures as fx

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_ACCOUNT = "acct-compose"
_INSTRUMENT = "ES"
_ARE_DIM_ID = "INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL"
_AFG_DIM_ID = "afg.ORDER"


class _FixedKeyProvider:
    """Mirrors ``tests/riskstate/conftest.py``'s own re-declared double (that module's own
    docstring: cross-suite imports are forbidden)."""

    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes-riskstate-wiring-suite")

    def generations(self) -> tuple[int, ...]:
        return (1,)

    def key_for(self, generation: int) -> bytes:
        del generation
        return b"test-fixed-key-bytes-riskstate-wiring-suite"


@pytest.fixture
def evidence_store(tmp_path: Path) -> SqliteEvidenceStore:
    key_provider: KeyProvider = _FixedKeyProvider()
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=key_provider
    )
    yield instance
    instance.close()


@pytest.fixture
def inbox(tmp_path: Path) -> SqliteEventInbox:
    instance = SqliteEventInbox(tmp_path / "inbox.sqlite3", scheme=_SCHEME)
    yield instance
    instance.close()


@pytest.fixture
def rcl_log(tmp_path: Path, evidence_store: SqliteEvidenceStore) -> SqliteCommitLog:
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
    """Mirrors ``tests/riskstate/conftest.py::seed_send_sealed`` exactly (cross-suite import
    forbidden by that module's own convention)."""
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
) -> None:
    """Mirrors ``tests/riskstate/conftest.py::seed_egress_result`` exactly."""
    payload = {
        "attempt_id": attempt_id,
        "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
        "egress_result_kind": "FULL_FILL" if filled_quantity is not None else "ACK",
        "filled_quantity": filled_quantity,
        "remaining_quantity": None,
    }
    store.append(payload, kind=kind, record_class=kind)


def _stage_request(
    *, step: CommitmentStep, proposal_id: str = "prop-1", event_id: str = "root-event-1"
) -> StageRequest:
    """A ``StageRequest`` built via ``model_construct`` (module docstring) — the proposal's
    ``proposal_id`` is the only field :class:`RiskStateService` reads off it."""
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


def _hse() -> HardSafetyEnvelope:
    return HardSafetyEnvelope(
        governed_dimensions=(
            GovernedDimensionLimit(
                dimension=_ARE_DIM_ID, envelope_max=Decimal("1"), unit="CONTRACTS"
            ),
        )
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
) -> RiskStateService:
    are_path = tmp_path / "aggregate_risk_policy.yaml"
    are_path.write_text(
        aggregate_risk_policy_yaml(
            instrument_scope=f'["{_INSTRUMENT}"]', account_scope=f'["{_ACCOUNT}"]'
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
        hse_envelope=_hse(),
        scenario_set=_scenario_set(),
        required_scenario_kinds=are_policy.required_scenario_kinds,
        position_reader=position_reader,
        flow_reader=flow_reader,
        rcl_log=rcl_log,
        construction_stage_reader=lambda: None,
        effect_envelope_reader=lambda: None,
        rcl_tip_reader=lambda: 1,
        monotonic_reader=lambda: 1_000,
        max_attempts_reader=lambda: max_attempts,
        current_seq_reader=lambda: None,
        evidence_store=evidence_store,
        environment_label="riskstate-wiring-test",
        action_class=action_class,
        activated_member_digests=("are-activation-digest", "afg-activation-digest"),
    )


# ===========================================================================
# Unit layer — RiskStateService
# ===========================================================================


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
        assert (
            len(inputs.cells) == 1
        )  # one (scope, dimension) x one required scenario kind
        cell = inputs.cells[0]
        assert cell.conservative_current_usage == Decimal("0")
        assert cell.conservative_current_usage_already_committed == Decimal("0")
        assert cell.required_concurrent_overlap_effect == Decimal("0")
        assert cell.effective_limit == Decimal("1")
        assert cell.max_credible_command_effect is None  # no construction yet
        # attestation-only fields are never authored by the service:
        assert inputs.all_fields_attributed is None
        assert inputs.numerically_safe is None
        assert inputs.valuation_ok is None
        assert inputs.limit_source_is_injected_envelope is None
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

    def test_unmatched_result_counts_full_sealed_quantity_as_unknown(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """Plan §5 실증 (3): a ``RESULT_UNMATCHED`` attempt's full sealed quantity counts in
        full toward conservative usage (the position-observation boundary GRANT→DENY case).
        """
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
        assert inputs.cells[0].conservative_current_usage == Decimal("5")

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
        """Plan §5 실증 (4)'s own position-side half: a sealed send with NO terminal result
        contributes to ``required_concurrent_overlap_effect``, never
        ``conservative_current_usage`` (position.py's own ``in_flight_overlap_effect`` vs
        ``conservative_current_usage`` split)."""
        _seed_send_sealed(evidence_store, attempt_id="a1", side="BUY", quantity="2")
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None
        assert inputs.cells[0].conservative_current_usage == Decimal("0")
        assert inputs.cells[0].required_concurrent_overlap_effect == Decimal("2")

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


class TestActionFlowInputsFor:
    def test_none_rcl_tip_yields_none_inputs(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        service._rcl_tip_reader = lambda: None  # simulate a read failure
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
        assert inputs.generation_current is False  # always re-derived by the wrapper
        assert inputs.producer_self_declared_scope is False
        assert inputs.economic_ref == f"resv-{_ACCOUNT}-{_INSTRUMENT}"
        assert inputs.committed_flow_vectors == ()
        assert inputs.flow_vector is not None
        assert inputs.flow_vector.magnitude(_AFG_DIM_ID) == Decimal("1")
        assert inputs.cause is not None
        assert inputs.cause.root_cause_identity == "root-event-1"
        assert (
            inputs.cause.forked_beyond_bound is False
        )  # attempts_for_cause(1) <= max(4)
        assert inputs.snapshot is not None
        assert inputs.snapshot.snapshot_generation == 1
        # attestation-only fields are never authored by the service:
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


# ===========================================================================
# Wiring layer — build_risk_state_service cross-checks
# ===========================================================================


def _write_riskstate_wiring_config(
    tmp_path: Path,
    *,
    account: str = _ACCOUNT,
    instrument: str = _INSTRUMENT,
    action_class_map: str | None = None,
    buy_side_token: str = "BUY",
    sell_side_token: str = "SELL",
    activate_are: bool = True,
    activate_afg: bool = True,
) -> Path:
    """A minimal, self-contained config directory for
    :func:`~tos_runtime.compose._riskstate_wiring.build_risk_state_service`'s own cross-check
    tests — deliberately NOT the shared ``tests/compose/conftest.py::config_dir`` fixture
    (module docstring)."""
    directory = tmp_path / "riskstate-config"
    directory.mkdir()
    (directory / "aggregate_risk_policy.yaml").write_text(
        aggregate_risk_policy_yaml(
            instrument_scope=f'["{instrument}"]', account_scope=f'["{account}"]'
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
    are_loaded = load_aggregate_risk_policy(
        directory / "aggregate_risk_policy.yaml", scheme=_SCHEME
    )
    afg_loaded = load_action_flow_policy(
        directory / "action_flow_policy.yaml", scheme=_SCHEME
    )
    members = []
    if activate_are:
        members.append(
            {
                "kind": "AGGREGATE_RISK_POLICY",
                "member_id": are_loaded.policy.policy_id,
                "generation": are_loaded.policy.policy_generation,
                "digest": are_loaded.policy.canonical_digest,
                "resolved": True,
                "immutable": True,
            }
        )
    if activate_afg:
        members.append(
            {
                "kind": "ACTION_FLOW_POLICY",
                "member_id": afg_loaded.policy.policy_id,
                "generation": afg_loaded.policy.policy_generation,
                "digest": afg_loaded.policy.canonical_digest,
                "resolved": True,
                "immutable": True,
            }
        )
    (directory / "safety_activation.yaml").write_text(
        yaml.safe_dump({"members": members}, sort_keys=False), encoding="utf-8"
    )
    return directory


def _build_service_from_wiring_config(
    directory: Path,
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
    *,
    hse_dimension: str = _ARE_DIM_ID,
    venue_allowed_sides: frozenset[str] = frozenset({"BUY", "SELL"}),
    scenario_set: AdverseScenarioSet | None = None,
) -> RiskStateService:
    del tmp_path
    construction = fx.construction_config()
    hse = HardSafetyEnvelope(
        governed_dimensions=(
            GovernedDimensionLimit(
                dimension=hse_dimension, envelope_max=Decimal("1"), unit="CONTRACTS"
            ),
        )
    )
    return build_risk_state_service(
        config_dir=directory,
        scheme=_SCHEME,
        construction=construction,
        environment_label="riskstate-wiring-test",
        evidence_store=evidence_store,
        inbox=inbox,
        rcl_log=rcl_log,
        hse_envelope=hse,
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

    def test_hse_dimension_missing_refuses(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """Plan §5 실증 (5): a policy dimension the HSE does not declare refuses at boot."""
        directory = _write_riskstate_wiring_config(tmp_path)
        with pytest.raises(RiskPolicyScopeMismatch, match="governed_dimensions"):
            _build_service_from_wiring_config(
                directory,
                tmp_path,
                evidence_store,
                inbox,
                rcl_log,
                hse_dimension="INSTRUMENT::SOME_OTHER_DIMENSION",
            )

    def test_members_activation_missing_refuses(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """Plan §5 실증 (6): a ``members:`` mismatch (here: absent entirely) refuses at boot."""
        directory = _write_riskstate_wiring_config(tmp_path, activate_are=False)
        with pytest.raises(PolicyNotActivated):
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


# ===========================================================================
# compose_paper_runtime level — (9) run/boot rule
# ===========================================================================


def test_compose_paper_runtime_refuses_when_files_absent_and_a_provider_is_none(
    config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Plan §3 "run 차단 목록" — the shared ``config_dir`` fixture never carries
    ``aggregate_risk_policy.yaml``/``action_flow_policy.yaml``, so leaving either provider
    ``None`` must refuse at boot rather than silently admit a permanently-UNKNOWN runtime.
    """
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
    """Plan §5 실증 (8): explicit providers are still honored when the two policy files are
    absent — ``ComposedRuntime.risk_state`` stays ``None`` (the pre-existing test seam).
    """
    from tos_runtime.calendar.ports import FixedWallClockReference
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
