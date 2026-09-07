"""Shared fixtures for ``tos_runtime.risk`` tests (design #40 §5 order 5;
slice plan §2)."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.afg import (
    ActionAmplificationEnvelope,
    ActionCause,
    ActionFlowScopeKind,
    ActionFlowStateSnapshot,
    ObservedAmplification,
    ScopeIndependenceEvidence,
)
from tos.are import (
    AdverseScenarioKind,
    AdverseScenarioSet,
    ProjectedCell,
    RiskDimensionKind,
    RiskScopeKind,
)
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import InstrumentKey
from tos.evidence import EvidenceAppendReceipt
from tos.rcl import CapacityComponent, CapacityVector
from tos.workload import RuntimeIdentity
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.risk.aggregate import (
    AggregateRiskDecisionInputs,
    AggregateRiskService,
    load_adverse_scenario_set,
    load_required_scenario_kinds,
)
from tos_runtime.risk.flow import ActionFlowDecisionInputs, ActionFlowGovernor

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: The (scope, dimension) key ``tos.are.predicates.adverse_increment`` groups
#: cells under (``f"{scope.value}::{dimension.value}"``) — used to keep the
#: GRANT-shaped fixtures below consistent with that internal key shape.
_ARE_DIM_KEY = (
    f"{RiskScopeKind.ACCOUNT.value}::{RiskDimensionKind.GROSS_NOTIONAL.value}"
)

#: A governed afg dimension id (the namespace-prefixed value, afg §2.2-4).
_AFG_DIM_ID = "afg.ORDER"


class FakeEvidenceAppendPort:
    """An in-memory :class:`~tos_runtime.evidence.ports.EvidenceAppendPort` double."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, object], str, str]] = []
        self._raise_next: Exception | None = None

    def fail_next_append(self, exc: Exception) -> None:
        self._raise_next = exc

    def append(
        self, payload: Mapping[str, object], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:
        if self._raise_next is not None:
            pending = self._raise_next
            self._raise_next = None
            raise pending
        self.calls.append((dict(payload), kind, record_class))
        return EvidenceAppendReceipt(
            segment_id=None,
            seq=len(self.calls) - 1,
            chain_digest="fake",
            key_generation=1,
        )

    def kinds(self) -> list[str]:
        return [kind for _payload, kind, _record_class in self.calls]


@pytest.fixture
def evidence_port() -> FakeEvidenceAppendPort:
    return FakeEvidenceAppendPort()


@pytest.fixture
def identity() -> RuntimeIdentity:
    return RuntimeIdentity(cell_id="test-cell", process_nonce="test-nonce-1")


@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    return tmp_path / "rcl.sqlite3"


@pytest.fixture
def log(log_path: Path, evidence_port: FakeEvidenceAppendPort) -> SqliteCommitLog:
    instance = SqliteCommitLog(log_path, evidence_port=evidence_port)
    yield instance
    instance.close()


@pytest.fixture
def writer_epoch(log: SqliteCommitLog, identity: RuntimeIdentity) -> int:
    return log.acquire_epoch(identity)


@pytest.fixture
def projection_reader(log: SqliteCommitLog) -> SqliteReservationProjectionReader:
    return SqliteReservationProjectionReader(log)


@pytest.fixture
def instrument_key() -> InstrumentKey:
    return InstrumentKey(account="acct-1", instrument="101S06")


def write_risk_config(path: Path, **overrides: Any) -> Path:
    """Write one fully-filled ``risk.example.yaml``-shaped config file."""
    base: dict[str, Any] = {
        "scenario_set_id": "scenario-set-1",
        "scenario_set_generation": 1,
        "policy_binding_id": None,
        "covered_scenario_kinds": ["FILL_PREFIX_ORDERING"],
        "required_scenario_kinds": ["FILL_PREFIX_ORDERING"],
        "evidence_package_ref": None,
        "max_fan_out": 10,
        "max_depth": 10,
        "max_attempts": 5,
        "max_mutations": 5,
        "max_queries": 5,
        "max_queue_depth": 100,
        "max_in_flight": 10,
        "max_elapsed_monotonic": "1000",
        "max_duplicate_redelivery_expansion": 3,
        "max_failover_reconnect_replay_expansion": 3,
        "max_amplification_per_cause": "100",
    }
    base.update(overrides)
    path.write_text(yaml.safe_dump(base))
    return path


@pytest.fixture
def risk_config_path(tmp_path: Path) -> Path:
    return write_risk_config(tmp_path / "risk.yaml")


@pytest.fixture
def scenario_set(risk_config_path: Path) -> AdverseScenarioSet:
    return load_adverse_scenario_set(risk_config_path)


@pytest.fixture
def required_scenario_kinds(
    risk_config_path: Path,
) -> frozenset[AdverseScenarioKind]:
    return load_required_scenario_kinds(risk_config_path)


@pytest.fixture
def envelope() -> ActionAmplificationEnvelope:
    return ActionAmplificationEnvelope(
        max_fan_out=10,
        max_depth=10,
        max_attempts=5,
        max_mutations=5,
        max_queries=5,
        max_queue_depth=100,
        max_in_flight=10,
        max_elapsed_monotonic=Decimal("1000"),
        max_duplicate_redelivery_expansion=3,
        max_failover_reconnect_replay_expansion=3,
        max_amplification_per_cause=Decimal("100"),
    )


@pytest.fixture
def ara_service(
    projection_reader: SqliteReservationProjectionReader,
    scenario_set: AdverseScenarioSet,
    evidence_port: FakeEvidenceAppendPort,
) -> AggregateRiskService:
    return AggregateRiskService(projection_reader, scenario_set, evidence_port)


@pytest.fixture
def afg_governor(
    log: SqliteCommitLog,
    evidence_port: FakeEvidenceAppendPort,
    envelope: ActionAmplificationEnvelope,
    writer_epoch: int,
) -> ActionFlowGovernor:
    return ActionFlowGovernor(log, evidence_port, envelope, writer_epoch=writer_epoch)


def grant_shaped_are_inputs(
    required_scenario_kinds: frozenset[AdverseScenarioKind],
) -> AggregateRiskDecisionInputs:
    """An :class:`AggregateRiskDecisionInputs` bundle that drives
    ``tos.are.risk_decision`` to ``GRANT`` (every premise positively proven)."""
    cell = ProjectedCell(
        scope=RiskScopeKind.ACCOUNT,
        dimension=RiskDimensionKind.GROSS_NOTIONAL,
        scenario=AdverseScenarioKind.FILL_PREFIX_ORDERING,
        conservative_current_usage=Decimal("0"),
        max_credible_command_effect=Decimal("10"),
        required_concurrent_overlap_effect=Decimal("0"),
        conservative_current_usage_already_committed=Decimal("0"),
        effective_limit=Decimal("100"),
    )
    effective_limit_vector = CapacityVector(
        components=(
            CapacityComponent(dimension_id=_ARE_DIM_KEY, magnitude=Decimal("50")),
        )
    )
    envelope_max = CapacityVector(
        components=(
            CapacityComponent(dimension_id=_ARE_DIM_KEY, magnitude=Decimal("100")),
        )
    )
    return AggregateRiskDecisionInputs(
        cells=(cell,),
        required_scenario_kinds=required_scenario_kinds,
        applicable_risk_scopes=("ACCOUNT",),
        all_fields_attributed=True,
        required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
        numerically_safe=True,
        valuation_ok=True,
        injected_envelope_max=envelope_max,
        limit_source_is_injected_envelope=True,
        effective_limit=effective_limit_vector,
    )


def grant_shaped_afg_inputs() -> ActionFlowDecisionInputs:
    """An :class:`ActionFlowDecisionInputs` bundle that drives
    ``tos.afg.action_flow_decision`` to ``GRANT``."""
    cause = ActionCause(
        root_cause_identity="cause-1",
        parent_lineage=("root-1",),
        lineage_attested=True,
        cyclic=False,
        forked_beyond_bound=False,
        inconsistent=False,
        command_identity="cmd-1",
        command_digest="cmd-digest-1",
    )
    independence = ScopeIndependenceEvidence(
        scope=ActionFlowScopeKind.ACCOUNT,
        allocation_separated=True,
        refill_separated=True,
        broker_enforcement_separated=True,
        credential_session_state_separated=True,
        failure_domain_separated=True,
        final_route_separated=True,
        basis_is_local_counter_only=False,
        basis_is_scheduler_priority_only=False,
    )
    snapshot = ActionFlowStateSnapshot.issue(
        scheme=_SCHEME,
        snapshot_id="afg-snapshot-1",
        snapshot_generation=1,
        consistency_cut_identity="cut-1",
        covered_scopes=(ActionFlowScopeKind.ACCOUNT,),
        scope_independence=(independence,),
    )
    observed = ObservedAmplification(
        fan_out=1,
        depth=1,
        attempts=1,
        mutations=1,
        queries=1,
        queue_depth=1,
        in_flight=1,
        elapsed_monotonic=Decimal("1"),
        duplicate_redelivery_expansion=0,
        failover_reconnect_replay_expansion=0,
        amplification_per_cause=Decimal("1"),
        duplicate_event_created_new_allowance=False,
        envelope_reset_on_duplicate=False,
        concurrent_consumers_share_one_envelope=True,
    )
    requested_limit = CapacityVector(
        components=(
            CapacityComponent(dimension_id=_AFG_DIM_ID, magnitude=Decimal("1")),
        )
    )
    envelope_max = CapacityVector(
        components=(
            CapacityComponent(dimension_id=_AFG_DIM_ID, magnitude=Decimal("10")),
        )
    )
    flow_vector = CapacityVector(
        components=(
            CapacityComponent(dimension_id=_AFG_DIM_ID, magnitude=Decimal("1")),
        )
    )
    hard_limit = CapacityVector(
        components=(
            CapacityComponent(dimension_id=_AFG_DIM_ID, magnitude=Decimal("10")),
        )
    )
    runtime_limit = CapacityVector(
        components=(
            CapacityComponent(dimension_id=_AFG_DIM_ID, magnitude=Decimal("10")),
        )
    )
    return ActionFlowDecisionInputs(
        cause=cause,
        snapshot=snapshot,
        required_scopes=frozenset({ActionFlowScopeKind.ACCOUNT}),
        producer_self_declared_scope=False,
        observed_amplification=observed,
        requested_limit=requested_limit,
        injected_envelope_max=envelope_max,
        limit_source_is_injected_envelope=True,
        economic_ref="economic-ref-1",
        flow_vector=flow_vector,
        committed_flow_vectors=(),
        hard_limit=hard_limit,
        runtime_limit=runtime_limit,
        economic_commitment_exclusive=True,
        flow_commitment_exclusive=True,
        generation_current=True,
        applicable_action_flow_scopes=("ACCOUNT",),
        decision_generation=1,
        cause_digest="cause-digest-1",
        command_identity="cmd-1",
        command_digest="cmd-digest-1",
    )
