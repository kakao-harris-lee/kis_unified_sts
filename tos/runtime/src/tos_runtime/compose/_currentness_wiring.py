"""``tos_runtime.compose`` currentness/risk phase-wiring helpers — split out"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tos.afg import ActionAmplificationEnvelope
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.cur import CurrentnessPolicy, DimensionKey

from tos_runtime.authority.epoch import SafetyAuthorityEpochService
from tos_runtime.compose._dimension_readers import (
    _build_dimension_readers,
    _EnvironmentScopeDimensionState,
    _PostTradeDimensionState,
    _RecoveryDimensionState,
    _ReleaseDimensionState,
)
from tos_runtime.compose._monitor_wiring import _MonitorOwners
from tos_runtime.compose._risk_attestations import (
    RiskAttestations,
    load_risk_attestations,
)
from tos_runtime.compose.context import (
    RecordingActionFlowGovernor,
    RecordingAggregateRiskService,
)
from tos_runtime.currentness.config import load_currentness_config
from tos_runtime.currentness.proof import EgressCurrentnessProofIssuer
from tos_runtime.currentness.vector import CurrentnessAssembler
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.risk.aggregate import (
    load_adverse_scenario_set,
    load_required_scenario_kinds,
)
from tos_runtime.time.service import TrustworthyTimeService

__all__ = [
    "_RiskAndCurrentness",
    "_build_risk_and_currentness",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_RISK_CONFIG_NAME = "risk.yaml"
_CURRENTNESS_CONFIG_NAME = "currentness.yaml"
_RISK_ATTESTATIONS_CONFIG_NAME = "risk_attestations.yaml"


@dataclass
class _RiskAndCurrentness:
    projection: SqliteReservationProjectionReader
    risk_service: RecordingAggregateRiskService
    flow_governor: RecordingActionFlowGovernor
    required_scenario_kinds: frozenset
    currentness_assembler: CurrentnessAssembler
    proof_issuer: EgressCurrentnessProofIssuer
    risk_attestations: RiskAttestations
    recovery_dimension_state: _RecoveryDimensionState
    environment_scope_dimension_state: _EnvironmentScopeDimensionState
    monitor_owners: _MonitorOwners
    post_trade_dimension_state: _PostTradeDimensionState
    release_dimension_state: _ReleaseDimensionState


def _load_action_flow_envelope(path: Path) -> ActionAmplificationEnvelope:
    """Build the Action Flow Governor's ``ActionAmplificationEnvelope`` from"""
    import yaml

    from tos_runtime.risk.aggregate import AggregateRiskConfigError

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AggregateRiskConfigError(f"cannot read {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise AggregateRiskConfigError(f"{path} must be a top-level mapping")
    fields = (
        "max_fan_out",
        "max_depth",
        "max_attempts",
        "max_mutations",
        "max_queries",
        "max_queue_depth",
        "max_in_flight",
        "max_elapsed_monotonic",
        "max_duplicate_redelivery_expansion",
        "max_failover_reconnect_replay_expansion",
        "max_amplification_per_cause",
    )
    missing = [name for name in fields if raw.get(name) is None]
    if missing:
        raise AggregateRiskConfigError(
            f"{path}: ActionAmplificationEnvelope axes still null (named-TBD): "
            f"{missing} — refusing to start"
        )
    return ActionAmplificationEnvelope(**{name: raw[name] for name in fields})


def _build_flow_governor(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    envelope: ActionAmplificationEnvelope,
    *,
    writer_epoch: int,
) -> RecordingActionFlowGovernor:
    """Step 7's Action Flow Governor — split out of"""
    return RecordingActionFlowGovernor(
        rcl_log,
        evidence_store,
        envelope,
        writer_epoch=writer_epoch,
    )


def _build_currentness_policy(config_dir: Path) -> CurrentnessPolicy:
    """The governing ``CurrentnessPolicy`` — split out of"""
    currentness_config = load_currentness_config(config_dir / _CURRENTNESS_CONFIG_NAME)
    currentness_policy = CurrentnessPolicy.issue(
        scheme=_SCHEME,
        policy_id="compose-currentness-policy",
        policy_generation=1,
        required_dimensions=currentness_config.required_dimensions,
    )
    assert isinstance(currentness_policy, CurrentnessPolicy)
    return currentness_policy


def _build_risk_and_currentness(
    config_dir: Path,
    rcl_log: SqliteCommitLog,
    writer_epoch: int,
    evidence_store: SqliteEvidenceStore,
    time_service: TrustworthyTimeService,
    authority_epoch_service: SafetyAuthorityEpochService,
    environment_label: str,
    monitor_owners: _MonitorOwners,
) -> _RiskAndCurrentness:
    """Aggregate Risk Authority + Action Flow Governor (order 5), currentness assembler +"""
    projection = SqliteReservationProjectionReader(rcl_log)
    scenario_set = load_adverse_scenario_set(config_dir / _RISK_CONFIG_NAME)
    required_scenario_kinds = load_required_scenario_kinds(
        config_dir / _RISK_CONFIG_NAME
    )
    risk_service = RecordingAggregateRiskService(
        projection, scenario_set, evidence_store
    )
    envelope = _load_action_flow_envelope(config_dir / _RISK_CONFIG_NAME)
    flow_governor = _build_flow_governor(
        rcl_log,
        evidence_store,
        envelope,
        writer_epoch=writer_epoch,
    )

    currentness_policy = _build_currentness_policy(config_dir)

    dimension_readers, dimension_states = _build_dimension_readers(
        authority_epoch_service=authority_epoch_service,
        currentness_policy=currentness_policy,
        environment_label=environment_label,
        monitor_owners=monitor_owners,
    )
    currentness_assembler = CurrentnessAssembler(
        rcl_log,
        time_service,
        writer_epoch=writer_epoch,
        policy=currentness_policy,
        mandated=frozenset({DimensionKey.COMMIT_LOG, DimensionKey.TRUSTWORTHY_TIME}),
        dimension_readers=dimension_readers,
    )
    proof_issuer = EgressCurrentnessProofIssuer(
        rcl_log,
        writer_epoch=writer_epoch,
        is_complete=currentness_assembler.is_complete,
    )
    risk_attestations = load_risk_attestations(
        config_dir / _RISK_ATTESTATIONS_CONFIG_NAME
    )

    return _RiskAndCurrentness(
        projection=projection,
        risk_service=risk_service,
        flow_governor=flow_governor,
        required_scenario_kinds=required_scenario_kinds,
        currentness_assembler=currentness_assembler,
        risk_attestations=risk_attestations,
        recovery_dimension_state=dimension_states.recovery,
        environment_scope_dimension_state=dimension_states.environment_scope,
        post_trade_dimension_state=dimension_states.post_trade,
        release_dimension_state=dimension_states.release,
        monitor_owners=monitor_owners,
        proof_issuer=proof_issuer,
    )
