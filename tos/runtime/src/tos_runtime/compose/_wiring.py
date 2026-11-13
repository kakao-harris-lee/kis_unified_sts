"""``tos_runtime.compose`` phase-wiring helpers — split out of root.py"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tos.authority import AuthorityTransitionReason
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egress import EgressCoordinateSet
from tos.egressgw import (
    ConformanceProofStage,
    EconomicEffectStage,
    OrderConstructionStage,
)
from tos.engine import (
    CommitmentStep,
    StageRequest,
    StrategyRegistry,
)
from tos.engine.records import InstrumentKey
from tos.iap import ApprovalResult, IndependentApprovalDecision, exact_binding_holds
from tos.time import HealthState
from tos.workload import RuntimeIdentity

from tos_runtime.authority.epoch import (
    AuthorityRuntimeConfig,
    SafetyAuthorityEpochService,
    load_authority_config,
)
from tos_runtime.authority.iap import (
    IntentRegistry,
    LoadedApproval,
    OperatorApprovalFileError,
    load_operator_approval_with_receipt,
)
from tos_runtime.authority.stages import IndependentApprovalStage
from tos_runtime.authority.standing import (
    StandingApprovalSource,
    StandingRecordingStage,
    chain_decision_providers,
)
from tos_runtime.brokercap import (
    BrokerScopesConfig,
    InstanceDocument,
    credential_route_inventory,
    load_active_instance_document,
    load_broker_scopes,
    refuse_principal_collision,
    transport_nature,
)
from tos_runtime.compose._attempt_arm import (
    attempt_reader,
    attempt_side,
)
from tos_runtime.compose._attempt_shape import (
    ProposalShapedConstructionStage,
    build_attempt_arms,
)
from tos_runtime.compose._boot_integrity import (
    record_operator_attested_inputs,
    verify_rcl_log_or_halt,
)
from tos_runtime.compose._currentness_wiring import (
    _build_risk_and_currentness,
    _RiskAndCurrentness,
)
from tos_runtime.compose._egress_coordinates import (
    EgressCoordinatesConfig,
    load_egress_coordinates,
)
from tos_runtime.compose._envelope_wiring import build_construction_inputs
from tos_runtime.compose._ledger_wiring import _build_ledger_stages
from tos_runtime.compose._monitor_wiring import (
    _MonitorOwners,
    build_capacity_owner,
    build_monitor_owners,
)
from tos_runtime.compose._request_digest import (
    RequestBytesDigestSource,
    default_request_bytes_digest_source,
)
from tos_runtime.compose._risk_attestations import (
    wrap_action_flow_inputs_provider,
    wrap_aggregate_risk_inputs_provider,
)
from tos_runtime.compose._transport_wiring import TransportKind, resolve_transport_boot
from tos_runtime.compose._types import (
    ConstructionConfig,
    ReleaseAdmissionRefused,
)
from tos_runtime.compose._venue_wiring import VenueServiceStage
from tos_runtime.compose.context import (
    ComposeContextResolver,
    RecordingActionFlowGovernor,
    VerdictRecorder,
    record_egress_identity_observation,
)
from tos_runtime.currentness.proof import EgressCurrentnessProofIssuer
from tos_runtime.currentness.stages import (
    AttemptBindVerificationStage,
    TransmissionCapabilityContext,
    TransmissionCapabilityStage,
)
from tos_runtime.currentness.vector import CurrentnessAssembler
from tos_runtime.custody.file_custody import FileCustody
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.ports import EvidenceAppendPort
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.operations.dependency_admission import observe_runtime_artifact
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.rcl.reservation_identity import (
    attempt_request_reservation_id,
)
from tos_runtime.release.admission import ReleaseAdmissionService
from tos_runtime.release.config import load_release_config
from tos_runtime.risk.aggregate import (
    AggregateRiskDecisionInputs,
)
from tos_runtime.risk.flow import ActionFlowDecisionInputs
from tos_runtime.risk.ledger_stages import (
    ActionFlowDecisionStage,
    AggregateRiskDecisionStage,
    CloseProofCommitFence,
    CommitmentUnavailabilityStage,
    LedgerVerificationStage,
    SyntheticCloseEntryFence,
)
from tos_runtime.riskstate.close_bound import EntryCloseBound
from tos_runtime.strategy.resolve import (
    ResolvedStrategyRegistry,
    resolve_strategy_registry,
)
from tos_runtime.time.config import TrustworthyTimeConfig, load_time_config
from tos_runtime.time.generation import seed_from
from tos_runtime.time.service import (
    TimeServiceNotStarted,
    TimeSnapshotReader,
    TrustworthyTimeService,
)
from tos_runtime.time.sources import (
    LocalSystemClockReader,
    MonotonicSource,
    ProcessMonotonicSource,
)
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig
from tos_runtime.venue import LoadedOrderConstructionPolicy, VenueConstraintService

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_TIME_CONFIG_NAME = "time.yaml"
_AUTHORITY_CONFIG_NAME = "authority.yaml"
_RISK_CONFIG_NAME = "risk.yaml"
_CURRENTNESS_CONFIG_NAME = "currentness.yaml"
_RELEASE_CONFIG_NAME = "release.yaml"
_EGRESS_COORDINATES_CONFIG_NAME = "egress_coordinates.yaml"
_BROKER_SCOPES_CONFIG_NAME = "broker_scopes.yaml"

_APPROVALS_DIRNAME = "approvals"


def _time_permits_new_risk(time_service: TimeSnapshotReader) -> Callable[[], bool]:
    """Re-review addendum B (2026-09-08): the catch below is narrowed to"""

    def _check() -> bool:
        try:
            snapshot = time_service.current_snapshot()
        except TimeServiceNotStarted:
            return False
        from tos.time import state_permits_new_normal_risk

        return state_permits_new_normal_risk(snapshot.health_state) is True

    return _check


def _rcl_tip_generation_provider(
    rcl_log: SqliteCommitLog, writer_epoch: int
) -> Callable[[StageRequest], int]:
    """A ``GenerationProvider`` (snapshot/decision generation, step 6; also"""

    def _provider(_request: StageRequest) -> int:
        view = rcl_log.read_linearizable(writer_epoch=writer_epoch)
        return 0 if view.last_seq is None else view.last_seq

    return _provider


def _decision_provider(
    custody_root: Path,
    environment_label: str,
    uid: int,
    time_service: TimeSnapshotReader,
    time_config: TrustworthyTimeConfig,
    evidence: EvidenceAppendPort,
) -> Callable[[StageRequest], LoadedApproval | None]:
    """Lazily loads the operator approval file bound to a proposal's own"""
    approvals_dir = custody_root / _APPROVALS_DIRNAME

    def _provider(request: StageRequest) -> LoadedApproval | None:
        proposal = request.proposal
        digest = getattr(proposal, "canonical_digest", None)
        if digest is None:
            return None
        path = approvals_dir / f"{digest}.yaml"
        if not path.is_file():
            return None
        try:
            return load_operator_approval_with_receipt(
                path,
                time=time_service,
                time_config=time_config,
                expected_owner_uid=uid,
                environment_label=environment_label,
            )
        except OperatorApprovalFileError as exc:
            evidence.append(
                {"path": str(path), "error": str(exc)},
                kind="IAP_APPROVAL_FILE_REFUSED",
                record_class="IAP_APPROVAL_FILE_REFUSED",
            )
            return None

    return _provider


def _build_identity(environment_label: str, code_digest: str) -> RuntimeIdentity:
    """This process's :class:`~tos.workload.RuntimeIdentity` — creates no"""
    return RuntimeIdentity(
        cell_id=environment_label,
        runtime_generation=0,
        process_nonce=secrets.token_hex(8),
        code_digest=code_digest,
    )


def _stage_a_release_probe(
    release_service: ReleaseAdmissionService,
    release_config: object,
    identity: RuntimeIdentity,
) -> None:
    """STAGE A release-admission probe (reported deviation from the plan's"""
    stage_a_admitted = release_service.decide(identity, currentness_current=True)
    if not stage_a_admitted:
        raise ReleaseAdmissionRefused(
            "compose_paper_runtime: release admission denied at the "
            f"pre-I/O STAGE A probe ({release_config!r}) — refusing to "
            "construct any custody/evidence/RCL/engine/gateway service "
            "(slice plan §4 item 1 fail-closed boot refusal)"
        )


@dataclass
class _Infra:
    custody: FileCustody
    key_provider: FileKeyProvider
    evidence_store: SqliteEvidenceStore
    emergency_log: EmergencyAppendLog
    time_service: TrustworthyTimeService
    time_config: TrustworthyTimeConfig
    monotonic_source: MonotonicSource


def _build_custody_evidence_time(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    environment_label: str,
    identity: RuntimeIdentity,
    uid: int,
    monotonic_source: MonotonicSource | None,
) -> _Infra:
    """custody / evidence store (``FileKeyProvider``) / emergency log /"""
    resolved_monotonic_source = (
        monotonic_source if monotonic_source is not None else ProcessMonotonicSource()
    )
    key_provider = FileKeyProvider(custody_root, expected_owner_uid=uid)
    evidence_store = SqliteEvidenceStore(
        data_dir / "evidence.sqlite3", key_provider=key_provider
    )
    custody = FileCustody(
        custody_root,
        environment_label=environment_label,
        expected_owner_uid=uid,
        evidence=evidence_store,
    )
    emergency_log = EmergencyAppendLog(data_dir / "emergency.jsonl")

    time_config = load_time_config(config_dir / _TIME_CONFIG_NAME)
    time_service = TrustworthyTimeService(
        monotonic=resolved_monotonic_source,
        references=(LocalSystemClockReader(),),
        config=time_config,
        identity=identity,
        evidence=evidence_store,
    )
    time_service.start()
    time_service.evaluate()
    time_service.evaluate()

    return _Infra(
        custody=custody,
        key_provider=key_provider,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        time_service=time_service,
        time_config=time_config,
        monotonic_source=resolved_monotonic_source,
    )


@dataclass
class _RclAndAuthority:
    rcl_log: SqliteCommitLog
    writer_epoch: int
    authority_epoch_service: SafetyAuthorityEpochService
    intent_registry: IntentRegistry


def _build_rcl_and_authority(
    data_dir: Path,
    config_dir: Path,
    identity: RuntimeIdentity,
    evidence_store: SqliteEvidenceStore,
    time_service: TrustworthyTimeService,
    time_config: TrustworthyTimeConfig,
    authority_domain: str,
) -> _RclAndAuthority:
    """RCL log (``acquire_epoch`` + generation seed) + Safety Authority epoch"""
    rcl_log = SqliteCommitLog(data_dir / "rcl.sqlite3", evidence_port=evidence_store)
    writer_epoch = rcl_log.acquire_epoch(identity, runtime_generation=0)
    seed_from(rcl_log)

    authority_config: AuthorityRuntimeConfig = load_authority_config(
        config_dir / _AUTHORITY_CONFIG_NAME
    )
    authority_epoch_service = SafetyAuthorityEpochService(
        rcl_log,
        time_service,
        evidence_store,
        authority_domain=authority_domain,
        writer_epoch=writer_epoch,
        config=authority_config,
    )
    authority_epoch_service.transition(
        leader_identity=identity.process_nonce or "compose-root",
        transition_reason=AuthorityTransitionReason.EXPLICIT_ADMINISTRATIVE_REVOCATION,
    )
    policy_generation = authority_config.trading_approval_policy_generation
    assert policy_generation is not None
    intent_registry = IntentRegistry(
        rcl_log,
        evidence_store,
        writer_epoch=writer_epoch,
        trading_approval_policy_generation=policy_generation,
        time=time_service,
        time_config=time_config,
    )

    return _RclAndAuthority(
        rcl_log=rcl_log,
        writer_epoch=writer_epoch,
        authority_epoch_service=authority_epoch_service,
        intent_registry=intent_registry,
    )


def _stage_b_release_probe(
    release_service: ReleaseAdmissionService,
    identity: RuntimeIdentity,
    time_service: TrustworthyTimeService,
    rcl_log: SqliteCommitLog,
) -> bool:
    """STAGE B release admission — the real, honestly-derived boot-time"""
    boot_currentness_current = (
        time_service.health_state is HealthState.TRUSTED and rcl_log.current_epoch() > 0
    )
    release_admitted = release_service.decide(
        identity, currentness_current=boot_currentness_current
    )
    if not release_admitted:
        raise ReleaseAdmissionRefused(
            "compose_paper_runtime: release admission denied at STAGE B "
            f"(boot_currentness_current={boot_currentness_current!r}) — "
            "refusing to construct any engine/gateway service (slice plan "
            "§4 item 1 fail-closed boot refusal)"
        )
    return release_admitted


@dataclass
class _ConstructionStages:
    construction_stage: OrderConstructionStage
    venue_stage: VenueServiceStage
    venue_recorder: VerdictRecorder
    economic_stage: EconomicEffectStage
    proof_stage: ConformanceProofStage


def _build_construction_stages(
    construction: ConstructionConfig,
    *,
    venue_service: VenueConstraintService,
    loaded_ocp: LoadedOrderConstructionPolicy,
    entry_close_bound_reader: Callable[[], EntryCloseBound] | None = None,
) -> _ConstructionStages:
    """Steps 2/3/5/11 (design #34 §3.2). Step 2's OCP coordinates come from ``build_venue_service``"""
    inputs = build_construction_inputs(
        construction, venue_service=venue_service, loaded_ocp=loaded_ocp, scheme=_SCHEME
    )
    construction_stage = ProposalShapedConstructionStage(
        arms=build_attempt_arms(
            loaded_ocp,
            boot_action_class=construction.action_class,
            venue_service=venue_service,
        ),
        loaded_ocp=loaded_ocp,
        entry_close_bound_reader=entry_close_bound_reader,
        price=construction.price,
        venue_constraint=venue_service.quantity_constraint,
        scheme=_SCHEME,
        intent_id=inputs.identities.intent_id,
        intent_version=inputs.identities.intent_version,
        envelope_id=inputs.identities.envelope_id,
        policy_id=inputs.policy_id,
        policy_version=inputs.policy_version,
        policy_generation=inputs.policy_generation,
        command_id=inputs.identities.command_id,
        generation=inputs.identities.generation,
        price_field_key=construction.price_field_key,
    )
    venue_stage = VenueServiceStage(
        venue_service,
        construction_stage,
        construction.action_class,
        construction.shape_price_field_key,
        construction_rules=loaded_ocp.construction_rules,
        attempt_reader=attempt_reader(construction_stage),
    )
    economic_stage = EconomicEffectStage(construction_stage=construction_stage)
    proof_stage = ConformanceProofStage(
        construction_stage=construction_stage,
        scheme=_SCHEME,
        proof_id=inputs.identities.proof_id,
        proof_generation=inputs.identities.generation,
        required_authority_scope=(f"scope-{construction.instrument}",),
    )
    return _ConstructionStages(
        construction_stage=construction_stage,
        venue_stage=venue_stage,
        venue_recorder=VerdictRecorder(venue_stage),
        economic_stage=economic_stage,
        proof_stage=proof_stage,
    )


@dataclass
class _RealizedStages:
    step4_recorder: VerdictRecorder
    step6_stage: AggregateRiskDecisionStage
    step7_stage: ActionFlowDecisionStage
    step8_stage: LedgerVerificationStage
    step9_recorder: VerdictRecorder
    step10_stage: CommitmentUnavailabilityStage
    step13_recorder: VerdictRecorder
    step14_stage: TransmissionCapabilityStage


def _build_step4_recorder(
    intent_registry: IntentRegistry,
    construction_stage: OrderConstructionStage,
    custody_root: Path,
    environment_label: str,
    uid: int,
    infra: _Infra,
    standing: StandingApprovalSource | None = None,
) -> VerdictRecorder:
    """Step 4 (``IndependentApprovalStage``), wrapped for verdict recording. ``standing``"""

    def _consuming_command_identity(request: StageRequest, decision: object) -> str:
        artifact = construction_stage.construction
        if artifact is not None and artifact.command is not None:
            return artifact.command.command_id or ""
        return getattr(request.proposal, "canonical_digest", None) or ""

    def _consuming_command_digest(request: StageRequest, decision: object) -> str:
        artifact = construction_stage.construction
        if artifact is not None and artifact.command is not None:
            return artifact.command.canonical_digest or ""
        return ""

    def _envelope_equivalent_provider(
        _request: StageRequest, decision: IndependentApprovalDecision
    ) -> bool | None:
        """Structural derivation (team-lead follow-up guidance, 2026-09-08):"""
        artifact = construction_stage.construction
        if artifact is None or artifact.intent is None:
            return None
        binding = exact_binding_holds(
            {"approved_intent_envelope": decision.approved_intent_envelope_digest},
            {"approved_intent_envelope": artifact.intent.canonical_digest},
        )
        if binding is ApprovalResult.APPROVE:
            return True
        if binding is ApprovalResult.DENY:
            return False
        return None

    decision_provider = _decision_provider(
        custody_root,
        environment_label,
        uid,
        infra.time_service,
        infra.time_config,
        infra.evidence_store,
    )
    if standing is not None:
        decision_provider = chain_decision_providers(decision_provider, standing)
    stage = IndependentApprovalStage(
        intent_registry,
        decision_provider=decision_provider,
        command_identity_provider=_consuming_command_identity,
        command_digest_provider=_consuming_command_digest,
        envelope_equivalent_provider=_envelope_equivalent_provider,
    )
    if standing is None:
        return VerdictRecorder(stage)
    return VerdictRecorder(StandingRecordingStage(stage, standing))


def _build_realized_stages(
    *,
    infra: _Infra,
    rcl: _RclAndAuthority,
    risk: _RiskAndCurrentness,
    construction_stages: _ConstructionStages,
    construction: ConstructionConfig,
    aggregate_risk_inputs_provider: Callable[
        [StageRequest], AggregateRiskDecisionInputs | None
    ],
    action_flow_inputs_provider: Callable[
        [StageRequest], ActionFlowDecisionInputs | None
    ],
    close_proof_fence_reader: Callable[
        [StageRequest], CloseProofCommitFence | SyntheticCloseEntryFence | None
    ],
    custody_root: Path,
    environment_label: str,
    uid: int,
    standing: StandingApprovalSource | None = None,
) -> _RealizedStages:
    """Steps 4, 6-10, 13, 14 — the real runtime Stages (never stand-ins)."""
    rcl_log, writer_epoch = rcl.rcl_log, rcl.writer_epoch
    intent_registry = rcl.intent_registry
    risk_service, flow_governor = risk.risk_service, risk.flow_governor
    projection = risk.projection
    construction_stage = construction_stages.construction_stage
    step4_recorder = _build_step4_recorder(
        intent_registry,
        construction_stage,
        custody_root,
        environment_label,
        uid,
        infra,
        standing,
    )
    time_gate = _time_permits_new_risk(infra.time_service)
    generation_provider = _rcl_tip_generation_provider(rcl_log, writer_epoch)

    step6_stage = AggregateRiskDecisionStage(
        risk_service,
        inputs_provider=wrap_aggregate_risk_inputs_provider(
            aggregate_risk_inputs_provider, risk.risk_attestations
        ),
        snapshot_generation_provider=generation_provider,
        decision_generation_provider=generation_provider,
        time_permits_new_risk=time_gate,
    )
    step7_stage = ActionFlowDecisionStage(
        flow_governor,
        inputs_provider=wrap_action_flow_inputs_provider(
            action_flow_inputs_provider,
            risk.risk_attestations,
            generation_provider,
        ),
        time_permits_new_risk=time_gate,
    )
    step8_stage, step9_recorder, step10_stage = _build_ledger_stages(
        rcl_log=rcl_log,
        projection=projection,
        writer_epoch=writer_epoch,
        flow_governor=flow_governor,
        construction_stage=construction_stage,
        economic_stage=construction_stages.economic_stage,
        generation_provider=generation_provider,
        time_gate=time_gate,
        close_proof_fence_reader=close_proof_fence_reader,
    )
    step13_recorder, step14_stage = _build_currentness_stages(
        rcl_log=rcl_log,
        writer_epoch=writer_epoch,
        construction_stages=construction_stages,
        flow_governor=flow_governor,
        step4_recorder=step4_recorder,
        construction=construction,
    )
    return _RealizedStages(
        step4_recorder=step4_recorder,
        step6_stage=step6_stage,
        step7_stage=step7_stage,
        step8_stage=step8_stage,
        step9_recorder=step9_recorder,
        step10_stage=step10_stage,
        step13_recorder=step13_recorder,
        step14_stage=step14_stage,
    )


def _build_currentness_stages(
    *,
    rcl_log: SqliteCommitLog,
    writer_epoch: int,
    construction_stages: _ConstructionStages,
    flow_governor: RecordingActionFlowGovernor,
    step4_recorder: VerdictRecorder,
    construction: ConstructionConfig,
) -> tuple[VerdictRecorder, TransmissionCapabilityStage]:
    """Steps 13 (Attempt Bind Verification) + 14 (Transmission Capability) —"""
    proof_stage = construction_stages.proof_stage
    construction_stage = construction_stages.construction_stage
    step13_stage = AttemptBindVerificationStage(
        reservation_digest_reader=lambda _attempt: (
            None if proof_stage.proof is None else proof_stage.proof.canonical_digest
        ),
        permit_digest_reader=lambda _attempt: (
            None
            if flow_governor.last_permit is None
            else flow_governor.last_permit.permit_id
        ),
        approval_digest_reader=lambda _attempt: (
            None
            if step4_recorder.last_verdict is None
            else step4_recorder.last_verdict.bound_digest
        ),
    )
    step14_stage = TransmissionCapabilityStage(
        rcl_log,
        writer_epoch=writer_epoch,
        context_reader=lambda request: TransmissionCapabilityContext(
            reservation_identity=attempt_request_reservation_id(
                request.instrument_key, request.attempt
            ),
            account_scope=request.instrument_key.account,
            instrument_scope=request.instrument_key.instrument,
            side_action_scope=attempt_side(
                construction_stage, construction.outbound_side
            ),
        ),
    )
    return VerdictRecorder(step13_stage), step14_stage


def _build_context_resolver(
    *,
    construction_stages: _ConstructionStages,
    realized: _RealizedStages,
    flow_governor: RecordingActionFlowGovernor,
    currentness_assembler: CurrentnessAssembler,
    proof_issuer: EgressCurrentnessProofIssuer,
    session_facts_current_reader: Callable[[], bool | None],
    tradability_facts_current_reader: Callable[[], bool | None],
    account_facts_current_reader: Callable[[], bool | None],
    mock_generation_reader: Callable[[], bool | None],
    observed_session_phase_reader: Callable[[], str | None],
    egress_coordinates: EgressCoordinatesConfig,
    broker_scopes: BrokerScopesConfig,
    instance_document: InstanceDocument | None,
    construction: ConstructionConfig,
    environment_label: str,
    continuity_id: str,
    authority_epoch_service: SafetyAuthorityEpochService,
    monitor_owners: _MonitorOwners,
    projection: SqliteReservationProjectionReader,
    evidence_store: SqliteEvidenceStore,
    transport_config: KisMockTransportConfig | None,
    request_bytes_digest_source: RequestBytesDigestSource | None = None,
) -> ComposeContextResolver:
    """The gateway's lazy ``SendBoundaryContext`` resolver (design #35 §3.1 (3)) — transport"""
    refuse_principal_collision(
        broker_scopes, active_principal=egress_coordinates.active_principal
    )
    instrument_key = InstrumentKey(
        account=construction.account, instrument=construction.instrument
    )
    resolved_credential_route_inventory = credential_route_inventory(
        broker_scopes, active_principal=egress_coordinates.active_principal
    )
    record_egress_identity_observation(
        evidence_store, resolved_credential_route_inventory
    )
    return ComposeContextResolver(
        construction_stage=construction_stages.construction_stage,
        proof_stage=construction_stages.proof_stage,
        venue_stage=construction_stages.venue_stage,
        step4_recorder=realized.step4_recorder,
        step9_recorder=realized.step9_recorder,
        step14_stage=realized.step14_stage,
        flow_governor=flow_governor,
        currentness_assembler=currentness_assembler,
        proof_issuer=proof_issuer,
        session_facts_current_reader=session_facts_current_reader,
        tradability_facts_current_reader=tradability_facts_current_reader,
        account_facts_current_reader=account_facts_current_reader,
        mock_generation_reader=mock_generation_reader,
        broker_scopes=broker_scopes,
        instance_document=instance_document,
        authority_epoch_service=authority_epoch_service,
        latch=monitor_owners.latch,
        capacity=build_capacity_owner(projection, instrument_key),
        transport_nature=transport_nature(broker_scopes.active_scope),
        environment_label=environment_label,
        principal=egress_coordinates.active_principal,
        credential_route_inventory=resolved_credential_route_inventory,
        authorized_coordinates=EgressCoordinateSet(
            endpoint=egress_coordinates.endpoint,
            account=construction.account,
            environment=environment_label,
            action=egress_coordinates.action,
            method=egress_coordinates.method,
            route_identity=egress_coordinates.route_identity,
            credential_generation=egress_coordinates.credential_generation,
            broker_session_generation=egress_coordinates.broker_session_generation,
            egress_generation=egress_coordinates.egress_generation,
            active_principal=egress_coordinates.active_principal,
        ),
        transport_endpoint=(
            None
            if transport_config is None
            else transport_config.endpoint_rest_base + transport_config.order_path
        ),
        request_bytes_digest_source=(
            request_bytes_digest_source
            if request_bytes_digest_source is not None
            else default_request_bytes_digest_source(
                construction, egress_coordinates.capsule_terminus_fields
            )
        ),
        outbound_side=construction.outbound_side,
        action_class=construction.action_class,
        observed_session_phase_reader=observed_session_phase_reader,
        continuity_id=continuity_id,
        instrument_key=instrument_key,
    )


def _resolve_strategies_and_attested_inputs(
    config_dir: Path,
    environment_label: str,
    identity: RuntimeIdentity,
    infra: _Infra,
    risk: _RiskAndCurrentness,
    registry: StrategyRegistry | None,
    allow_no_strategies: bool,
    transport_kind: TransportKind,
) -> tuple[
    EgressCoordinatesConfig,
    BrokerScopesConfig,
    ResolvedStrategyRegistry,
    InstanceDocument | None,
    KisMockTransportConfig | None,
]:
    """Load ``egress_coordinates.yaml`` + ``broker_scopes.yaml`` (TOS Phase 4"""
    egress_coordinates = load_egress_coordinates(
        config_dir / _EGRESS_COORDINATES_CONFIG_NAME,
        environment_label=environment_label,
    )
    broker_scopes = load_broker_scopes(
        config_dir / _BROKER_SCOPES_CONFIG_NAME,
        environment_label=environment_label,
    )
    instance_document = load_active_instance_document(broker_scopes)
    transport_boot = resolve_transport_boot(
        transport_kind, config_dir, broker_scopes, infra.custody
    )
    resolved_strategies = resolve_strategy_registry(
        config_dir,
        injected_registry=registry,
        evidence_store=infra.evidence_store,
        emergency_log=infra.emergency_log,
        identity=identity,
        allow_no_strategies=allow_no_strategies,
    )
    record_operator_attested_inputs(
        config_dir,
        infra.evidence_store,
        identity,
        risk.risk_attestations,
        egress_coordinates,
        resolved_strategies.loaded,
        resolved_strategies.loaded_bindings,
        broker_scopes=broker_scopes,
        instance_document=instance_document,
        extra_config_files=(
            transport_boot.extra_config_files + risk.monitor_owners.config_files
        ),
    )
    return (
        egress_coordinates,
        broker_scopes,
        resolved_strategies,
        instance_document,
        transport_boot.transport_config,
    )


@dataclass
class _BootResult:
    """:func:`_boot_services`'s return value — named fields instead of a"""

    identity: RuntimeIdentity
    infra: _Infra
    rcl: _RclAndAuthority
    risk: _RiskAndCurrentness
    release_admitted: bool
    egress_coordinates: EgressCoordinatesConfig
    broker_scopes: BrokerScopesConfig
    instance_document: InstanceDocument | None
    registry: StrategyRegistry
    transport_config: KisMockTransportConfig | None


def _boot_services(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    environment_label: str,
    uid: int,
    authority_domain: str,
    monotonic_source: MonotonicSource | None,
    registry: StrategyRegistry | None,
    allow_no_strategies: bool,
    transport_kind: TransportKind,
) -> _BootResult:
    """Identity + STAGE A release probe + custody/evidence/time + RCL/authority + STAGE"""
    observation = observe_runtime_artifact()
    identity = _build_identity(environment_label, observation.source_tree_digest)
    release_config = load_release_config(config_dir / _RELEASE_CONFIG_NAME)
    release_service = ReleaseAdmissionService(release_config, observation)
    _stage_a_release_probe(release_service, release_config, identity)

    infra = _build_custody_evidence_time(
        config_dir,
        data_dir,
        custody_root,
        environment_label,
        identity,
        uid,
        monotonic_source,
    )
    rcl = _build_rcl_and_authority(
        data_dir,
        config_dir,
        identity,
        infra.evidence_store,
        infra.time_service,
        infra.time_config,
        authority_domain,
    )
    verify_rcl_log_or_halt(
        rcl.rcl_log, infra.evidence_store, infra.emergency_log, identity
    )
    release_admitted = _stage_b_release_probe(
        release_service, identity, infra.time_service, rcl.rcl_log
    )
    monitor_owners = build_monitor_owners(
        config_dir,
        evidence_store=infra.evidence_store,
        monotonic_source=infra.monotonic_source,
    )
    risk = _build_risk_and_currentness(
        config_dir,
        rcl.rcl_log,
        rcl.writer_epoch,
        infra.evidence_store,
        infra.time_service,
        rcl.authority_epoch_service,
        environment_label,
        monitor_owners,
    )
    (
        egress_coordinates,
        broker_scopes,
        resolved_strategies,
        instance_document,
        transport_config,
    ) = _resolve_strategies_and_attested_inputs(
        config_dir,
        environment_label,
        identity,
        infra,
        risk,
        registry,
        allow_no_strategies,
        transport_kind,
    )
    return _BootResult(
        identity=identity,
        infra=infra,
        rcl=rcl,
        risk=risk,
        release_admitted=release_admitted,
        egress_coordinates=egress_coordinates,
        broker_scopes=broker_scopes,
        instance_document=instance_document,
        registry=resolved_strategies.registry,
        transport_config=transport_config,
    )


def _build_stage_map(
    construction_stages: _ConstructionStages, realized: _RealizedStages
) -> dict:
    """The ``CommitmentStep`` -> ``Stage`` map ``EngineCore`` is wired with —"""
    return {
        CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION: construction_stages.construction_stage,
        CommitmentStep.VENUE_ADMISSIBILITY_DECISION: construction_stages.venue_recorder,
        CommitmentStep.INDEPENDENT_APPROVAL: realized.step4_recorder,
        CommitmentStep.ECONOMIC_EFFECT_ENVELOPE: construction_stages.economic_stage,
        CommitmentStep.AGGREGATE_RISK_DECISION: realized.step6_stage,
        CommitmentStep.ACTION_FLOW_DECISION: realized.step7_stage,
        CommitmentStep.LEDGER_VERIFICATION: realized.step8_stage,
        CommitmentStep.ATOMIC_COMMIT: realized.step9_recorder,
        CommitmentStep.COMMITMENT_UNAVAILABILITY: realized.step10_stage,
        CommitmentStep.ORDER_CONFORMANCE_PROOF: construction_stages.proof_stage,
        CommitmentStep.ATTEMPT_BIND_VERIFICATION: realized.step13_recorder,
        CommitmentStep.TRANSMISSION_CAPABILITY: realized.step14_stage,
    }
