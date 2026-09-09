"""``tos_runtime.compose`` shared dataclasses/exceptions — split out of
root.py purely for the size budget (tools/tos_size_budget.py file-level
limit); no behavioural difference from having them inline in root.py.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
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
    EngineEvent,
    EventResult,
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
from tos_runtime.brokercap import BrokerScopesConfig
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
    #: The durable event admission queue (TOS Phase 3 Wave 1 Lane A-R, plan
    #: §1.1) — its own sqlite file, separate from ``evidence_store``'s.
    inbox: SqliteEventInbox
    #: The single driver over ``core``/``gateway`` (plan §1.1) — the ONLY
    #: caller of ``core.handle``/``run`` in this composed runtime; see
    #: ``tos/runtime/tests/engine/test_no_direct_core_calls.py``.
    driver: EngineDriver
    #: The loaded Broker Scope table (TOS Phase 4 plan §2 decisions 1-2, G-4)
    #: — the SAME config :attr:`context_resolver`'s ``transport_nature`` /
    #: ``credential_route_inventory`` were derived from, exposed so a caller
    #: can inspect the active scope without re-loading the config file.
    scopes: BrokerScopesConfig

    def run_once(self, events: Iterable[EngineEvent]) -> tuple[EventResult, ...]:
        """Drive ``events`` through :attr:`driver` to completion, one at a time.

        Kept for existing call-site compatibility (every compose end-to-end test calls
        ``runtime.run_once((event,))``); the body no longer touches ``self.core`` directly —
        :attr:`driver` is now the only caller of ``core.handle``/``run`` (TOS Phase 3 Wave 1
        Lane A-R, plan §1.1: "테스트가 코어를 직접 호출하는 경로 제거").

        Args:
            events: An iterable of :class:`~tos.engine.records.EngineEvent`
                (a single synthetic tick, a short replay — never a daemon
                loop, which is Phase 5, ``cli.py``'s own module docstring).

        Returns:
            One :class:`~tos.engine.core.EventResult` per event, in order — the result for EACH
            enqueued event specifically; any re-injected follow-on ``EGRESS_RESULT`` events are
            processed too (as a side effect, durably recorded) but are not included here.
        """
        return tuple(self.driver.enqueue_and_run(event) for event in events)

    #: The evidence kind recorded by :meth:`clear_new_risk_halt` on success — a runtime-level
    #: record, not a kernel ``EvidenceKind`` member (re-review finding R3, 2026-09-09).
    _NEW_RISK_HALT_CLEARED_KIND = "NEW_RISK_HALT_CLEARED_BY_OPERATOR"
    #: The evidence kind recorded by :meth:`clear_new_risk_halt` on EVERY refusal (re-review
    #: finding RR3, 2026-09-09) — a refused clear (most of all a stale/wrong ``evidence_seq``,
    #: "the operator is looking at a violation that is not the current one") must leave a trace
    #: too, not just a silently-returned enum member a careless caller can ignore.
    _NEW_RISK_HALT_CLEAR_REFUSED_KIND = "NEW_RISK_HALT_CLEAR_REFUSED"

    def clear_new_risk_halt(
        self, *, latched_evidence_seq: int, operator_attestation: str
    ) -> NewRiskHaltClearOutcome:
        """Operator re-arm for the independent-review finding #3 new-risk halt latch
        (re-review finding R3, 2026-09-09 — see :mod:`tos_runtime.engine.inbox`'s own module
        docstring "Operator re-arm" section for why this exists now rather than in a later
        phase). THE sanctioned door — see that module's own updated docstring and
        :meth:`~tos_runtime.engine.inbox.SqliteEventInbox.clear_new_risk_halt`'s for why a direct
        call on the storage layer is refused by a mechanical pin (re-review finding RR2).

        Evidence BEFORE state change, exactly like every other halt path in this runtime
        (:func:`~tos_runtime.evidence.emergency.record_halt`'s own discipline, though this is a
        CLEAR, not a halt, so it goes through the ordinary
        :meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.append` path instead): this method
        first checks the CURRENTLY-latched halt matches ``latched_evidence_seq`` and that
        ``operator_attestation`` is non-empty, THEN durably appends one
        ``NEW_RISK_HALT_CLEARED_BY_OPERATOR`` evidence entry (the latched reason, the seq being
        cleared, and the sha256 of the attestation text — never the raw text itself, which may be
        arbitrarily long free-form operator prose), and ONLY THEN clears the latch via
        :meth:`~tos_runtime.engine.inbox.SqliteEventInbox.clear_new_risk_halt`. If that final
        clear itself refuses (a concurrent relatch changed the seq between the check above and
        the clear — a narrow, honestly-disclosed TOCTOU this single-threaded runtime does not
        currently reach, since :class:`~tos_runtime.engine.driver.EngineDriver` is itself
        single-threaded), the ``CLEARED`` evidence row still exists, recording that a clear was
        ATTEMPTED against that seq even though it did not take effect — never a silently-dropped
        attempt — and this method ALSO appends a ``NEW_RISK_HALT_CLEAR_REFUSED`` row for it
        (re-review finding RR3).

        **Every refusal is now durably recorded (re-review finding RR3, 2026-09-09).** Before this
        fix, a refused clear returned a bare ``False`` with zero evidence — a caller that ignored
        the return value, or a stale-seq clear attempt (exactly "the operator reviewed an old
        violation, not the current one"), left no trace anywhere. Every refusal path — no latch,
        empty attestation, seq mismatch, or the storage-layer TOCTOU refusal above — now appends
        one ``NEW_RISK_HALT_CLEAR_REFUSED`` entry (the typed outcome, the requested seq, the
        CURRENTLY-latched seq if any, and the attestation's sha256) before returning.

        Args:
            latched_evidence_seq: The ``evidence_seq`` of the violation the operator reviewed.
                Must equal the CURRENTLY-latched row's own seq — a stale value is refused (with a
                ``NEW_RISK_HALT_CLEAR_REFUSED`` evidence row, per RR3).
            operator_attestation: Non-empty free-text operator attestation.

        Returns:
            :class:`~tos_runtime.engine.inbox.NewRiskHaltClearOutcome` — :attr:`~tos_runtime
            .engine.inbox.NewRiskHaltClearOutcome.CLEARED` on success; ``NO_LATCH`` /
            ``EMPTY_ATTESTATION`` / ``SEQ_MISMATCH`` / ``STORAGE_REFUSED`` on refusal (the latch,
            if any, is left completely untouched in every refusal case).
        """
        current = self.inbox.new_risk_halt()
        attestation_sha256 = hashlib.sha256(
            operator_attestation.encode("utf-8")
        ).hexdigest()

        def _refuse(outcome: NewRiskHaltClearOutcome) -> NewRiskHaltClearOutcome:
            self.evidence_store.append(
                {
                    "outcome": outcome.value,
                    "requested_evidence_seq": latched_evidence_seq,
                    "current_latched_evidence_seq": (
                        current.get("evidence_seq") if current is not None else None
                    ),
                    "operator_attestation_sha256": attestation_sha256,
                },
                kind=self._NEW_RISK_HALT_CLEAR_REFUSED_KIND,
                record_class=self._NEW_RISK_HALT_CLEAR_REFUSED_KIND,
            )
            return outcome

        if current is None:
            return _refuse(NewRiskHaltClearOutcome.NO_LATCH)
        if not operator_attestation.strip():
            return _refuse(NewRiskHaltClearOutcome.EMPTY_ATTESTATION)
        if current.get("evidence_seq") != latched_evidence_seq:
            return _refuse(NewRiskHaltClearOutcome.SEQ_MISMATCH)

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
            operator_attestation=operator_attestation,
        )
        if outcome is not NewRiskHaltClearOutcome.CLEARED:
            return _refuse(NewRiskHaltClearOutcome.STORAGE_REFUSED)
        return outcome
