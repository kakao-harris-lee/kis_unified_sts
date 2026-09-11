"""``tos_runtime.compose`` currentness/risk phase-wiring helpers — split out
of ``_wiring.py`` purely for the size budget (tools/tos_size_budget.py file-
level limit); no behavioural difference from having them inline there.
:func:`~tos_runtime.compose._wiring._boot_services` calls
:func:`_build_risk_and_currentness`, in the design #40 §5 order 5-6.

The individual dimension-reader factories + their late-bound state cells live in
:mod:`tos_runtime.compose._dimension_readers` (moved there for the size budget,
2026-09-12) — this module keeps only the assembly point
(:func:`_build_risk_and_currentness`), the risk/currentness services it
constructs, and the :class:`_RiskAndCurrentness` bundle it returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tos.afg import ActionAmplificationEnvelope
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.cur import CurrentnessPolicy, DimensionKey

from tos_runtime.authority.epoch import SafetyAuthorityEpochService
from tos_runtime.compose._dimension_readers import (
    _ActionFlowDimensionState,
    _build_dimension_readers,
    _ConstraintDimensionState,
    _ConstructionDimensionState,
    _DecisionProofIntentDimensionState,
    _EnvironmentScopeDimensionState,
    _PostTradeDimensionState,
    _RecoveryDimensionState,
    _ReleaseDimensionState,
    _TradingApprovalDimensionState,
)
from tos_runtime.compose._egress_attestations import (
    EgressAttestations,
    load_egress_attestations,
)
from tos_runtime.compose._pending_dimensions import (
    PendingDimensionSpec,
    load_pending_currentness_dimensions,
)
from tos_runtime.compose._risk_attestations import (
    RiskAttestations,
    load_risk_attestations,
)
from tos_runtime.compose._safety_wiring import _SafetyMesh
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

#: Same config file name ``_wiring.py`` uses for the risk/currentness configs
#: (``tos/runtime/config/risk.example.yaml`` / ``currentness.example.yaml``
#: / ``currentness_dimensions.example.yaml``).
_RISK_CONFIG_NAME = "risk.yaml"
_CURRENTNESS_CONFIG_NAME = "currentness.yaml"
_CURRENTNESS_DIMENSIONS_CONFIG_NAME = "currentness_dimensions.yaml"
_EGRESS_ATTESTATIONS_CONFIG_NAME = "egress_attestations.yaml"
_RISK_ATTESTATIONS_CONFIG_NAME = "risk_attestations.yaml"


@dataclass
class _RiskAndCurrentness:
    projection: SqliteReservationProjectionReader
    risk_service: RecordingAggregateRiskService
    flow_governor: RecordingActionFlowGovernor
    required_scenario_kinds: frozenset
    currentness_assembler: CurrentnessAssembler
    proof_issuer: EgressCurrentnessProofIssuer
    #: The 17 operator-attested pending currentness dimensions (team-lead
    #: follow-up guidance) — see
    #: :mod:`tos_runtime.compose._pending_dimensions`'s own module docstring.
    pending_dimension_specs: tuple[PendingDimensionSpec, ...]
    #: The 5 operator-attested egress-gate stand-ins (items 6/12/16 — team-lead
    #: follow-up guidance) — see
    #: :mod:`tos_runtime.compose._egress_attestations`'s own module docstring.
    egress_attestations: EgressAttestations
    #: The 6 operator-attested step 6/7 admission witnesses (re-review
    #: finding F4) — see
    #: :mod:`tos_runtime.compose._risk_attestations`'s own module docstring.
    risk_attestations: RiskAttestations
    #: The late-bound cell the ACTION_FLOW dimension reader closes over —
    #: filled in with step 9's ``VerdictRecorder`` once
    #: ``_build_realized_stages`` creates it (see
    #: ``_ActionFlowDimensionState``'s own docstring for why).
    action_flow_dimension_state: _ActionFlowDimensionState
    #: Late-bound cell the RECOVERY dimension reader closes over — filled in with the
    #: W1 recovery barrier's own verdict once ``apply_recovery_barrier`` runs (see
    #: ``_RecoveryDimensionState``'s own docstring for why).
    recovery_dimension_state: _RecoveryDimensionState
    #: Late-bound cell the TRADING_APPROVAL dimension reader closes over — filled in
    #: with step 4's own ``VerdictRecorder`` once ``_build_realized_stages`` creates it
    #: (see ``_TradingApprovalDimensionState``'s own docstring for why).
    trading_approval_dimension_state: _TradingApprovalDimensionState
    #: Late-bound cell the ENVIRONMENT_SCOPE dimension reader closes over — filled in
    #: with the resolved active :class:`~tos_runtime.brokercap.scopes.BrokerScope` once
    #: ``_resolve_strategies_and_attested_inputs`` returns (see
    #: ``_EnvironmentScopeDimensionState``'s own docstring for why).
    environment_scope_dimension_state: _EnvironmentScopeDimensionState
    #: The four W3-a1/a2 safety-mesh services + item-16 latch owner (Phase 5 W3-b, plan §2
    #: decision 8) — see :mod:`tos_runtime.compose._safety_wiring`'s own module docstring.
    safety_mesh: _SafetyMesh
    #: Phase 5 W3.2's five late-bound cells (plan §2 decisions 2-6; AGGREGATE_RISK needs
    #: none — its reader closes over :attr:`risk_service` directly, already constructed
    #: by the time :func:`_build_dimension_readers` runs) — see each cell's own docstring
    #: in :mod:`tos_runtime.compose._dimension_readers`.
    construction_dimension_state: _ConstructionDimensionState
    constraint_dimension_state: _ConstraintDimensionState
    decision_proof_intent_dimension_state: _DecisionProofIntentDimensionState
    post_trade_dimension_state: _PostTradeDimensionState
    release_dimension_state: _ReleaseDimensionState


def _load_action_flow_envelope(path: Path) -> ActionAmplificationEnvelope:
    """Build the Action Flow Governor's ``ActionAmplificationEnvelope`` from
    the ``risk.yaml`` block (``tos_runtime.risk`` has no dedicated loader for
    this — see ``tos/runtime/config/risk.example.yaml``'s own comment: "is
    constructed directly by the composition root")."""
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
    safety_mesh: _SafetyMesh,
) -> RecordingActionFlowGovernor:
    """Step 7's Action Flow Governor — split out of
    :func:`_build_risk_and_currentness` purely for the size budget.

    Phase 5 W3.2 plan §2 decision 8 (lane d2 follow-up): wires
    ``safety_mesh.protective_action.protective_classification_digest`` (a bound
    method, ``Callable[[], str | None]``) as the real fact
    ``ActionFlowDecisionInputs.protective_classification_digest`` supplies,
    replacing the ``None`` default that otherwise left it permanently unfed
    (``risk/flow.py``'s own construction-site follow-up note).
    """
    return RecordingActionFlowGovernor(
        rcl_log,
        evidence_store,
        envelope,
        writer_epoch=writer_epoch,
        protective_classification_digest_provider=(
            safety_mesh.protective_action.protective_classification_digest
        ),
    )


def _build_currentness_policy(config_dir: Path) -> CurrentnessPolicy:
    """The governing ``CurrentnessPolicy`` — split out of
    :func:`_build_risk_and_currentness` purely for the size budget.

    W3.1 independent review MEDIUM-3: ``required_dimensions`` used to be built by
    sorting ``MANDATED_DIMENSION_FLOOR`` itself, at construction — which made the
    CURRENTNESS_POLICY dimension reader's own ``policy_covers_mandated_dimensions``
    check a tautology (a policy built FROM the floor trivially "covers" that same
    floor; no operator config value could ever change the answer). Now genuinely
    read from the operator-declared ``required_dimensions`` key
    (``tos_runtime.currentness.config``'s own module docstring) — an independently-
    editable declaration the reader compares against the kernel's own floor, never a
    copy of it.
    """
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
    safety_mesh: _SafetyMesh,
) -> _RiskAndCurrentness:
    """Aggregate Risk Authority + Action Flow Governor (order 5), currentness assembler +
    Egress Currentness Proof issuer (order 6); forwards to
    :func:`~tos_runtime.compose._dimension_readers._build_dimension_readers`."""
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
        safety_mesh=safety_mesh,
    )

    currentness_policy = _build_currentness_policy(config_dir)

    dimension_readers, dimension_states = _build_dimension_readers(
        rcl_log=rcl_log,
        writer_epoch=writer_epoch,
        authority_epoch_service=authority_epoch_service,
        currentness_policy=currentness_policy,
        environment_label=environment_label,
        safety_mesh=safety_mesh,
        risk_service=risk_service,
    )
    currentness_assembler = CurrentnessAssembler(
        rcl_log,
        time_service,
        writer_epoch=writer_epoch,
        policy=currentness_policy,
        mandated=frozenset({DimensionKey.COMMIT_LOG, DimensionKey.TRUSTWORTHY_TIME}),
        dimension_readers=dimension_readers,
    )
    # `is_complete` is the SAME currentness_assembler.is_complete callable
    # every other consumer uses (== tos.cur.predicates.vector_complete,
    # never re-derived) — the issuer derives `result` from it per issuance,
    # never from a caller-supplied claim.
    proof_issuer = EgressCurrentnessProofIssuer(
        rcl_log,
        writer_epoch=writer_epoch,
        is_complete=currentness_assembler.is_complete,
    )
    pending_dimension_specs = load_pending_currentness_dimensions(
        config_dir / _CURRENTNESS_DIMENSIONS_CONFIG_NAME
    )
    egress_attestations = load_egress_attestations(
        config_dir / _EGRESS_ATTESTATIONS_CONFIG_NAME
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
        pending_dimension_specs=pending_dimension_specs,
        egress_attestations=egress_attestations,
        risk_attestations=risk_attestations,
        action_flow_dimension_state=dimension_states.action_flow,
        recovery_dimension_state=dimension_states.recovery,
        trading_approval_dimension_state=dimension_states.trading_approval,
        environment_scope_dimension_state=dimension_states.environment_scope,
        construction_dimension_state=dimension_states.construction,
        constraint_dimension_state=dimension_states.constraint,
        decision_proof_intent_dimension_state=dimension_states.decision_proof_intent,
        post_trade_dimension_state=dimension_states.post_trade,
        release_dimension_state=dimension_states.release,
        safety_mesh=safety_mesh,
        proof_issuer=proof_issuer,
    )
