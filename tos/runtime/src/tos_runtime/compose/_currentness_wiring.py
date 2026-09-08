"""``tos_runtime.compose`` currentness/risk phase-wiring helpers — split out
of ``_wiring.py`` purely for the size budget (tools/tos_size_budget.py file-
level limit); no behavioural difference from having them inline there.
:func:`~tos_runtime.compose._wiring._boot_services` calls
:func:`_build_risk_and_currentness`, in the design #40 §5 order 5-6.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tos.afg import ActionAmplificationEnvelope
from tos.authority import currentness_admissible
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.cur import MANDATED_DIMENSION_FLOOR, CurrentnessPolicy, DimensionKey
from tos.engine.vocabulary import StageOutcome

from tos_runtime.authority.epoch import SafetyAuthorityEpochService
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
from tos_runtime.compose.context import (
    RecordingActionFlowGovernor,
    RecordingAggregateRiskService,
    VerdictRecorder,
)
from tos_runtime.currentness.config import load_currentness_config
from tos_runtime.currentness.proof import EgressCurrentnessProofIssuer
from tos_runtime.currentness.vector import CurrentnessAssembler, DimensionReport
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.risk.aggregate import (
    load_adverse_scenario_set,
    load_required_scenario_kinds,
)
from tos_runtime.time.service import TrustworthyTimeService

__all__ = [
    "_ActionFlowDimensionState",
    "_RiskAndCurrentness",
    "_action_flow_dimension_reader_for",
    "_authority_dimension_reader_for",
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


def _authority_dimension_reader_for(
    authority_epoch_service: SafetyAuthorityEpochService,
) -> Callable[[], DimensionReport | None]:
    def _reader() -> DimensionReport | None:
        state = authority_epoch_service.current_state()
        if state.current_epoch_floor is None:
            return None
        witness = authority_epoch_service.witness()
        return DimensionReport(
            bound_generation=state.current_epoch_floor,
            positively_established=currentness_admissible(witness),
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _ActionFlowDimensionState:
    """A late-bound cell for the ACTION_FLOW dimension reader (below).

    ``CurrentnessAssembler`` is constructed before ``_build_realized_stages``
    creates step 9's ``VerdictRecorder`` (the currentness/risk wiring order,
    design #40 §5, runs before the engine Stage wiring) — so the reader
    closes over this mutable cell, and :func:`compose_paper_runtime` fills
    in ``step9_recorder`` right after ``_build_realized_stages`` returns.
    """

    step9_recorder: VerdictRecorder | None = None


def _action_flow_dimension_reader_for(
    rcl_log: SqliteCommitLog,
    writer_epoch: int,
    state: _ActionFlowDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The ACTION_FLOW currentness dimension, derived from step 9's own
    ``AtomicCommitStage`` outcome (team-lead follow-up guidance, 2026-09-08:
    "derive it from AtomicCommitStage's own AppendReceipt seq, not from Q's
    standalone issue_permit").

    ``ActionFlowPermit.rcl_commitment_ref`` itself stays ``None``
    (``tos_runtime.risk.flow.ActionFlowGovernor.build_permit``'s own
    docstring — the durable commit lives in step 9's single
    ``apply_reservation_transition`` entry instead), so this reader does
    NOT read that field; it independently re-reads the RCL log's own
    CURRENT tip (never step 9's self-reported claim) and reports
    ``positively_established`` only when step 9 itself last recorded
    ``ADMIT`` — the same "구조 파생, never a caller-supplied claim"
    discipline every other reader in this module already follows.
    """

    def _reader() -> DimensionReport | None:
        verdict = state.step9_recorder.last_verdict if state.step9_recorder else None
        if verdict is None or verdict.outcome is not StageOutcome.ADMIT:
            return None
        view = rcl_log.read_linearizable(writer_epoch=writer_epoch)
        if view.last_seq is None:
            return None
        return DimensionReport(
            bound_generation=view.last_seq,
            positively_established=True,
            restrictive_floor=0,
        )

    return _reader


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


def _build_risk_and_currentness(
    config_dir: Path,
    rcl_log: SqliteCommitLog,
    writer_epoch: int,
    evidence_store: SqliteEvidenceStore,
    time_service: TrustworthyTimeService,
    authority_epoch_service: SafetyAuthorityEpochService,
) -> _RiskAndCurrentness:
    """Aggregate Risk Authority + Action Flow Governor (order 5), currentness
    assembler + Egress Currentness Proof issuer (order 6)."""
    projection = SqliteReservationProjectionReader(rcl_log)
    scenario_set = load_adverse_scenario_set(config_dir / _RISK_CONFIG_NAME)
    required_scenario_kinds = load_required_scenario_kinds(
        config_dir / _RISK_CONFIG_NAME
    )
    risk_service = RecordingAggregateRiskService(
        projection, scenario_set, evidence_store
    )
    envelope = _load_action_flow_envelope(config_dir / _RISK_CONFIG_NAME)
    flow_governor = RecordingActionFlowGovernor(
        rcl_log, evidence_store, envelope, writer_epoch=writer_epoch
    )

    # Loaded (and thereby fail-closed validated at startup) even though this
    # slice's proof issuance path does not yet consume
    # `max_claim_to_send_bound_ms` directly.
    load_currentness_config(config_dir / _CURRENTNESS_CONFIG_NAME)
    # Narrowed to exactly MANDATED_DIMENSION_FLOOR (the 21 non-conditional
    # DimensionKey members) — never the full 22-member enum, which would
    # also require the conditional RESTRICTED_LIVE_TRIAL dimension this
    # composition has no basis to attest at all (§9:258, RLP-deferred,
    # out of Phase 2 scope). "A policy may require more, never fewer"
    # (tos.cur.predicates.vector_complete's own §5.1 rule) — this IS the
    # floor, not a narrowing below it.
    currentness_policy = CurrentnessPolicy.issue(
        scheme=_SCHEME,
        policy_id="compose-currentness-policy",
        policy_generation=1,
        required_dimensions=tuple(
            sorted(MANDATED_DIMENSION_FLOOR, key=lambda k: k.value)
        ),
    )
    assert isinstance(currentness_policy, CurrentnessPolicy)

    action_flow_dimension_state = _ActionFlowDimensionState()
    currentness_assembler = CurrentnessAssembler(
        rcl_log,
        time_service,
        writer_epoch=writer_epoch,
        policy=currentness_policy,
        mandated=frozenset({DimensionKey.COMMIT_LOG, DimensionKey.TRUSTWORTHY_TIME}),
        authority_dimension_reader=_authority_dimension_reader_for(
            authority_epoch_service
        ),
        action_flow_dimension_reader=_action_flow_dimension_reader_for(
            rcl_log, writer_epoch, action_flow_dimension_state
        ),
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
        action_flow_dimension_state=action_flow_dimension_state,
        proof_issuer=proof_issuer,
    )
