"""``tos_runtime.compose`` shared dataclasses/exceptions — split out of
root.py purely for the size budget (tools/tos_size_budget.py file-level
limit); no behavioural difference from having them inline in root.py.
"""

from __future__ import annotations

from dataclasses import dataclass

from tos.brokeradapter import SyntheticPaperTransport
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egressgw import (
    AdmittedPriceObservation,
    BrokerEgressGateway,
    ConformanceProofStage,
    OrderConstructionStage,
    ProposedConstructionEnvelope,
    VenueConstraintStage,
    VenueQuantityConstraint,
)
from tos.engine import (
    EngineCore,
    StrategyRegistry,
)
from tos.venue import (
    ActionClass,
    OrderAdmissibilityDecision,
    OrderShapeFields,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
)
from tos.workload import RuntimeIdentity

from tos_runtime.authority.epoch import (
    SafetyAuthorityEpochService,
)
from tos_runtime.authority.iap import (
    IntentRegistry,
)
from tos_runtime.compose.context import (
    ComposeContextResolver,
    RecordingActionFlowGovernor,
    RecordingAggregateRiskService,
    VerdictRecorder,
)
from tos_runtime.currentness.proof import EgressCurrentnessProofIssuer
from tos_runtime.currentness.stages import (
    TransmissionCapabilityStage,
)
from tos_runtime.currentness.vector import CurrentnessAssembler
from tos_runtime.custody.file_custody import FileCustody
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.time.service import TrustworthyTimeService

__all__ = [
    "ComposedRuntime",
    "ConstructionConfig",
    "ReleaseAdmissionRefused",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Config file names expected directly under ``config_dir`` (each shaped like
#: its ``tos/runtime/config/*.example.yaml`` counterpart).
_TIME_CONFIG_NAME = "time.yaml"
_AUTHORITY_CONFIG_NAME = "authority.yaml"
_RISK_CONFIG_NAME = "risk.yaml"
_CURRENTNESS_CONFIG_NAME = "currentness.yaml"
_RELEASE_CONFIG_NAME = "release.yaml"

#: Where operator-authored Independent Approval decisions live, keyed by
#: proposal digest (``tos_runtime.authority.iap`` module docstring:
#: "approvals/<proposal_digest>.yaml").
_APPROVALS_DIRNAME = "approvals"


class ReleaseAdmissionRefused(RuntimeError):
    """Raised by :func:`compose_paper_runtime` when release admission denies
    (slice plan §4 item 1: "release admission(거부 시 기동 중단)") — nothing
    past custody/evidence/RCL is constructed when this is raised."""


@dataclass(frozen=True)
class ConstructionConfig:
    """The per-strategy Order Construction facts steps 2/3/5/11 need (module
    docstring). Every field mirrors ``tests/slice/_slice_fixtures.py``'s own
    injected constants — genuine per-deployment configuration, not a bound
    this compose root could derive itself.
    """

    account: str
    instrument: str
    envelope: ProposedConstructionEnvelope
    price: AdmittedPriceObservation | None
    venue_constraint: VenueQuantityConstraint | None
    venue_snapshot: VenueConstraintSnapshot
    venue_policy: VenueConstraintPolicy
    venue_decision: OrderAdmissibilityDecision
    order_shape: OrderShapeFields
    venue_shape_constraints: VenueShapeConstraints
    action_class: ActionClass
    observed_session_phase: str
    outbound_side: str
    price_field_key: str | None = None
    shape_price_field_key: str | None = None


@dataclass
class ComposedRuntime:
    """Every live composed service, plus the wired ``EngineCore``/gateway/
    transport (slice plan §4 item 1's own ordered list)."""

    custody: FileCustody
    key_provider: FileKeyProvider
    evidence_store: SqliteEvidenceStore
    emergency_log: EmergencyAppendLog
    time_service: TrustworthyTimeService
    rcl_log: SqliteCommitLog
    writer_epoch: int
    identity: RuntimeIdentity
    authority_epoch_service: SafetyAuthorityEpochService
    intent_registry: IntentRegistry
    risk_service: RecordingAggregateRiskService
    flow_governor: RecordingActionFlowGovernor
    currentness_assembler: CurrentnessAssembler
    proof_issuer: EgressCurrentnessProofIssuer
    step4_recorder: VerdictRecorder
    step9_recorder: VerdictRecorder
    step14_stage: TransmissionCapabilityStage
    construction_stage: OrderConstructionStage
    venue_stage: VenueConstraintStage
    proof_stage: ConformanceProofStage
    context_resolver: ComposeContextResolver
    core: EngineCore
    gateway: BrokerEgressGateway
    transport: SyntheticPaperTransport
    registry: StrategyRegistry
    release_admitted: bool
    #: The loaded coverage floor (``risk.yaml``'s ``required_scenario_kinds``)
    #: — exposed so a caller building ``AggregateRiskDecisionInputs`` reuses
    #: the SAME floor the config declared, never a re-typed duplicate.
    required_scenario_kinds: frozenset

    def run_once(self, events: object) -> tuple:
        """Drive the composed ``EngineCore`` over ``events`` to completion.

        Args:
            events: An iterable of :class:`~tos.engine.records.EngineEvent`
                (a single synthetic tick, a short replay — never a daemon
                loop, which is Phase 5, ``cli.py``'s own module docstring).

        Returns:
            One :class:`~tos.engine.core.EventResult` per event, in order.
        """
        return self.core.run(events)  # type: ignore[arg-type]
