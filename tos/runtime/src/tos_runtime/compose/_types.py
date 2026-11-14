"""``tos_runtime.compose`` shared dataclasses/exceptions — split out of"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from tos.brokeradapter import Transport
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egressgw import (
    AdmittedPriceObservation,
    BrokerEgressGateway,
    ConformanceProofStage,
    OrderConstructionStage,
)
from tos.engine import (
    EngineCore,
    EngineEvent,
    EventResult,
    StrategyRegistry,
)
from tos.venue import ActionClass
from tos.workload import RuntimeIdentity

from tos_runtime.authority.epoch import (
    SafetyAuthorityEpochService,
)
from tos_runtime.authority.iap import (
    IntentRegistry,
)
from tos_runtime.brokercap import BrokerScopesConfig
from tos_runtime.calendar.owner import SessionFactsOwner
from tos_runtime.compose._venue_ledger_wiring import SyntheticVenueLedgerParts
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
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import NewRiskHaltClearOutcome, SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.marketfeed.scheduler import TickScheduler
from tos_runtime.posttrade.unsent_release import UnsentReleasePass
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.recovery.barrier import RecoveryVerdict
from tos_runtime.riskstate.service import RiskStateService
from tos_runtime.safety.rearm import prepare_new_risk_halt_clear
from tos_runtime.safety.shutdown import ControlledShutdown, ShutdownOutcome
from tos_runtime.time.service import TrustworthyTimeService
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSessions
from tos_runtime.venue import VenueConstraintService

if TYPE_CHECKING:
    from tos_runtime.compose._venue_wiring import VenueServiceStage
    from tos_runtime.posttrade.fill_observer import KisMockFillObserver

__all__ = [
    "ComposedRuntime",
    "ConstructionConfig",
    "OperationsFacts",
    "RecoveryBarrierHeld",
    "ReleaseAdmissionRefused",
    "RiskStateConfigError",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_TIME_CONFIG_NAME = "time.yaml"
_AUTHORITY_CONFIG_NAME = "authority.yaml"
_RISK_CONFIG_NAME = "risk.yaml"
_CURRENTNESS_CONFIG_NAME = "currentness.yaml"
_RELEASE_CONFIG_NAME = "release.yaml"

_APPROVALS_DIRNAME = "approvals"


class ReleaseAdmissionRefused(RuntimeError):
    """Raised by :func:`compose_paper_runtime` when release admission denies"""


class RiskStateConfigError(RuntimeError):
    """Raised by :func:`compose_paper_runtime` (TOS risk state service wave, plan §3 "run"""


class RecoveryBarrierHeld(RuntimeError):
    """Raised by :meth:`ComposedRuntime.run_once` when the TOS Phase 5 W1 recovery barrier"""


@dataclass(frozen=True)
class ConstructionConfig:
    """The per-strategy Order Construction facts steps 2/3/5/11 need (module"""

    account: str
    instrument: str
    price: AdmittedPriceObservation | None
    action_class: ActionClass
    instrument_class: str
    outbound_side: str
    price_field_key: str | None = None
    shape_price_field_key: str | None = None


@dataclass(frozen=True)
class OperationsFacts:
    """Read callables :func:`~tos_runtime.compose._operations_wiring.apply_operations_wiring`"""

    #: on-disk ``PRAGMA user_version`` (:func:`~tos_runtime.operations.schema_migrations
    schema_versions: Callable[[], dict[str, int | None]]
    last_backup: Callable[[], dict[str, object] | None]
    dependency_admission: Callable[[], bool | None]
    key_continuity: Callable[[], str | None]


@dataclass
class ComposedRuntime:
    """Every live composed service, plus the wired ``EngineCore``/gateway/"""

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
    venue_stage: VenueServiceStage
    proof_stage: ConformanceProofStage
    context_resolver: ComposeContextResolver
    core: EngineCore
    gateway: BrokerEgressGateway
    transport: Transport
    registry: StrategyRegistry
    release_admitted: bool
    required_scenario_kinds: frozenset
    inbox: SqliteEventInbox
    driver: EngineDriver | None
    scopes: BrokerScopesConfig
    recovery: RecoveryVerdict | None = None
    venue: VenueConstraintService | None = None
    risk_state: RiskStateService | None = None
    operations: OperationsFacts | None = None
    session_facts: SessionFactsOwner | None = None
    marketfeed: TickScheduler | None = None
    kis_credential_sessions: KisCredentialSessions | None = None
    fill_observer: KisMockFillObserver | None = None
    broker_witness_provenance: str = "synthetic-ledger"
    unsent_release: UnsentReleasePass | None = None

    venue_ledger: SyntheticVenueLedgerParts = field(
        default_factory=SyntheticVenueLedgerParts
    )

    def run_once(self, events: Iterable[EngineEvent]) -> tuple[EventResult, ...]:
        """Drive ``events`` through :attr:`driver` to completion, one at a time."""
        if self.driver is None:
            raise RecoveryBarrierHeld(
                "recovery barrier is not READY -- the engine driver is not wired "
                f"(recovery={self.recovery!r})"
            )
        return tuple(self.driver.enqueue_and_run(event) for event in events)

    def shutdown(self, *, reason: str) -> ShutdownOutcome:
        """Run the controlled-shutdown procedure once"""
        if self.fill_observer is not None:
            self.fill_observer.close()
        return ControlledShutdown(
            inbox=self.inbox,
            rcl_log=self.rcl_log,
            evidence_store=self.evidence_store,
            custody=self.custody,
            key_provider=self.key_provider,
        ).run(reason=reason)

    _NEW_RISK_HALT_CLEARED_KIND = "NEW_RISK_HALT_CLEARED_BY_OPERATOR"
    _NEW_RISK_HALT_CLEAR_REFUSED_KIND = "NEW_RISK_HALT_CLEAR_REFUSED"

    def clear_new_risk_halt(
        self, *, latched_evidence_seq: int, approvals_dir: Path
    ) -> NewRiskHaltClearOutcome:
        """Operator re-arm for the independent-review finding #3 new-risk halt latch"""
        current = self.inbox.new_risk_halt()
        decision = prepare_new_risk_halt_clear(
            current=current,
            latched_evidence_seq=latched_evidence_seq,
            approvals_dir=approvals_dir,
            evidence_store=self.evidence_store,
            inbox=self.inbox,
            environment_label=self.identity.cell_id or "",
            expected_owner_uid=os.getuid(),
            refused_kind=self._NEW_RISK_HALT_CLEAR_REFUSED_KIND,
        )
        if decision.refusal is not None:
            return decision.refusal

        assert current is not None
        attestation_text = decision.attestation_text
        assert attestation_text is not None
        attestation_sha256 = hashlib.sha256(
            attestation_text.encode("utf-8")
        ).hexdigest()
        self.evidence_store.append(
            {
                "latched_evidence_seq": latched_evidence_seq,
                "latched_reason": current.get("reason"),
                "latched_event_id": current.get("event_id"),
                "operator_attestation_sha256": attestation_sha256,
            },
            kind=self._NEW_RISK_HALT_CLEARED_KIND,
            record_class=self._NEW_RISK_HALT_CLEARED_KIND,
        )
        outcome = self.inbox.clear_new_risk_halt(
            latched_evidence_seq=latched_evidence_seq,
            operator_attestation=attestation_text,
        )
        if outcome is not NewRiskHaltClearOutcome.CLEARED:
            self.evidence_store.append(
                {
                    "outcome": NewRiskHaltClearOutcome.STORAGE_REFUSED.value,
                    "requested_evidence_seq": latched_evidence_seq,
                    "current_latched_evidence_seq": current.get("evidence_seq"),
                },
                kind=self._NEW_RISK_HALT_CLEAR_REFUSED_KIND,
                record_class=self._NEW_RISK_HALT_CLEAR_REFUSED_KIND,
            )
            return NewRiskHaltClearOutcome.STORAGE_REFUSED
        return outcome
