"""``tos_runtime.compose`` shared dataclasses/exceptions — split out of
root.py purely for the size budget (tools/tos_size_budget.py file-level
limit); no behavioural difference from having them inline in root.py.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from tos.brokeradapter import Transport
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
from tos_runtime.recovery.barrier import RecoveryVerdict
from tos_runtime.safety.rearm import prepare_new_risk_halt_clear
from tos_runtime.safety.shutdown import ControlledShutdown, ShutdownOutcome
from tos_runtime.time.service import TrustworthyTimeService

__all__ = [
    "ComposedRuntime",
    "ConstructionConfig",
    "OperationsFacts",
    "RecoveryBarrierHeld",
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


class RecoveryBarrierHeld(RuntimeError):
    """Raised by :meth:`ComposedRuntime.run_once` when the TOS Phase 5 W1 recovery barrier
    (:mod:`tos_runtime.recovery.barrier`, wired by :mod:`tos_runtime.compose._recovery_wiring`)
    did not resolve to :attr:`~tos.sbr.vocabulary.ReadinessVerdict.READY`.

    A typed refusal, never a silent no-op (plan §2 decision 2): a caller that tries to drive an
    event through a held runtime learns exactly why, via :attr:`ComposedRuntime.recovery`,
    rather than getting an ``AttributeError`` on a ``None`` driver or — worse — a call that
    quietly does nothing.
    """


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


@dataclass(frozen=True)
class OperationsFacts:
    """Read callables :func:`~tos_runtime.compose._operations_wiring.apply_operations_wiring`
    exposes on :attr:`ComposedRuntime.operations` (TOS Phase 5 W4 plan §2 decision 11) — the
    ``operations`` field group of the operator projection (plan §2.7). Defined here, not in
    ``_operations_wiring.py``, purely to avoid that module importing THIS one for
    :class:`ComposedRuntime`'s own type while this one imports it back for the field's type (a
    two-file cycle) — the same "shared dataclass lives in ``_types.py``" placement
    :class:`ConstructionConfig` already uses.

    Every field is a zero-argument read callable, never a stored value — the SAME "read
    callable, not a snapshot" discipline :mod:`tos_runtime.operator.projection` requires of its
    own constructor arguments, so ``apply_operations_wiring`` can hand these straight through.
    """

    #: ``{"evidence": int | None, "rcl": int | None, "inbox": int | None}`` — each store's own
    #: on-disk ``PRAGMA user_version`` (:func:`~tos_runtime.operations.schema_migrations
    #: .schema_version`), read fresh on every call (never cached — a ``migrate`` CLI run between
    #: two projection exports must be visible on the very next one).
    schema_versions: Callable[[], dict[str, int | None]]
    #: ``{"generation": int, "age_monotonic_ns": None, "manifest_digest": str}`` for the highest
    #: ``gen*`` manifest under the composed ``backup_root``, or ``None`` when no ``backup_root``
    #: was given or no manifest exists yet. ``age_monotonic_ns`` is always ``None`` — a backup
    #: manifest's ``created_at_monotonic_ns`` was stamped by a DIFFERENT process's monotonic
    #: clock, and monotonic clocks are not comparable across processes (module docstring of
    #: ``_operations_wiring.py`` has the full reasoning); no trusted wall-clock source exists
    #: either (plan §2.7's own "벽시계 값 비노출" decision), so this fact stays honestly absent
    #: until a cross-process-comparable time source exists.
    last_backup: Callable[[], dict[str, object] | None]
    #: The STAGE B dependency-admission verdict (``composed.release_admitted`` — the SAME fact
    #: :attr:`~ComposedRuntime.release_admitted` already carries; plan §2 decision 5).
    dependency_admission: Callable[[], bool | None]
    #: Placeholder — TOS Phase 5 W4 lane e3 (``operations/key_rotation.py``) has not landed at
    #: the time this wiring was authored; returns ``None`` unconditionally (never a fabricated
    #: verdict) until a follow-up threads the real
    #: :class:`~tos_runtime.operations.key_rotation.KeyContinuityVerdict` through here.
    key_continuity: Callable[[], str | None]


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
    #: T2 lane C — widened from ``SyntheticPaperTransport`` to the kernel's own ``Transport``
    #: Protocol: either the synthetic transport or a fully-wired ``KisMockTransport`` satisfies
    #: it structurally.
    transport: Transport
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
    #: ``tos/runtime/tests/engine/test_no_direct_core_calls.py``. ``None`` iff the TOS Phase 5
    #: W1 recovery barrier (:attr:`recovery`) did not resolve to ``READY`` — see
    #: :meth:`run_once`'s own ``RecoveryBarrierHeld`` refusal.
    driver: EngineDriver | None
    #: The loaded Broker Scope table (TOS Phase 4 plan §2 decisions 1-2, G-4)
    #: — the SAME config :attr:`context_resolver`'s ``transport_nature`` /
    #: ``credential_route_inventory`` were derived from, exposed so a caller
    #: can inspect the active scope without re-loading the config file.
    scopes: BrokerScopesConfig
    #: The TOS Phase 5 W1 recovery-barrier verdict (:mod:`tos_runtime.recovery.barrier`),
    #: stamped by :func:`tos_runtime.compose._recovery_wiring.apply_recovery_barrier`
    #: immediately after this runtime is otherwise fully composed. ``None`` only transiently,
    #: before that wiring runs inside :func:`~tos_runtime.compose.root.compose_paper_runtime` —
    #: never observable on a runtime a caller actually receives.
    recovery: RecoveryVerdict | None = None
    #: TOS Phase 5 W4 §2 decision 11 — set by
    #: :func:`~tos_runtime.compose._operations_wiring.apply_operations_wiring` (called from
    #: :func:`~tos_runtime.compose.root.compose_paper_runtime`, right after
    #: ``apply_recovery_barrier``). ``None`` only transiently before that wiring runs — never
    #: observable on a runtime a caller actually receives (mirrors :attr:`recovery`'s own
    #: docstring).
    operations: OperationsFacts | None = None

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

        Raises:
            RecoveryBarrierHeld: If :attr:`driver` is ``None`` (the TOS Phase 5 W1 recovery
                barrier did not resolve to ``READY``) — a typed refusal, never a silent no-op.
        """
        if self.driver is None:
            raise RecoveryBarrierHeld(
                "recovery barrier is not READY -- the engine driver is not wired "
                f"(recovery={self.recovery!r})"
            )
        return tuple(self.driver.enqueue_and_run(event) for event in events)

    def shutdown(self, *, reason: str) -> ShutdownOutcome:
        """Run the TOS Phase 5 W3.2 controlled-shutdown procedure once (lane d3;
        :mod:`tos_runtime.safety.shutdown`'s own module docstring has the full honesty
        discipline — what each step proves, what it deliberately does not, and why).

        A thin sequencing wrapper ONLY: the actual step bodies, the kernel-predicate calls,
        and the recovery-handoff package construction all live in
        :class:`~tos_runtime.safety.shutdown.ControlledShutdown`, kept out of this dataclass
        purely for the ``tools/tos_size_budget.py`` function-length budget (no behavioural
        difference from inlining it here).

        Args:
            reason: A free-text operator/runtime reason for the shutdown — recorded on the
                ``CONTROLLED_SHUTDOWN_STARTED`` evidence row and as the new-risk-halt
                latch's own reason.

        Returns:
            The :class:`~tos_runtime.safety.shutdown.ShutdownOutcome`. Closes
            :attr:`inbox`, :attr:`rcl_log`, and :attr:`evidence_store` as part of the
            procedure — this runtime is not usable for further calls afterward.
        """
        return ControlledShutdown(
            inbox=self.inbox,
            rcl_log=self.rcl_log,
            evidence_store=self.evidence_store,
            custody=self.custody,
            key_provider=self.key_provider,
        ).run(reason=reason)

    #: The evidence kind recorded by :meth:`clear_new_risk_halt` on success — a runtime-level
    #: record, not a kernel ``EvidenceKind`` member (re-review finding R3, 2026-09-09).
    _NEW_RISK_HALT_CLEARED_KIND = "NEW_RISK_HALT_CLEARED_BY_OPERATOR"
    #: The evidence kind recorded by :meth:`clear_new_risk_halt` on EVERY refusal (re-review
    #: finding RR3, 2026-09-09) — a refused clear (most of all a stale/wrong ``evidence_seq``,
    #: "the operator is looking at a violation that is not the current one") must leave a trace
    #: too, not just a silently-returned enum member a careless caller can ignore.
    _NEW_RISK_HALT_CLEAR_REFUSED_KIND = "NEW_RISK_HALT_CLEAR_REFUSED"

    def clear_new_risk_halt(
        self, *, latched_evidence_seq: int, approvals_dir: Path
    ) -> NewRiskHaltClearOutcome:
        """Operator re-arm for the independent-review finding #3 new-risk halt latch
        (re-review finding R3, 2026-09-09 — see :mod:`tos_runtime.engine.inbox`'s own module
        docstring "Operator re-arm" section for why this exists now rather than in a later
        phase). THE sanctioned door — see that module's own updated docstring and
        :meth:`~tos_runtime.engine.inbox.SqliteEventInbox.clear_new_risk_halt`'s for why a direct
        call on the storage layer is refused by a mechanical pin (re-review finding RR2).

        **TOS Phase 5 W3 plan §2 decision 7.** The single free-text operator attestation this
        method used to accept is replaced by a HAG two-person quorum, evaluated by
        :func:`~tos_runtime.safety.rearm.prepare_new_risk_halt_clear` (which owns the
        NO_LATCH/SEQ_MISMATCH pre-checks plus the
        :class:`~tos_runtime.safety.rearm.ReArmWorkflow` quorum evaluation, including its own
        ``REARM_APPROVED``/``REARM_REFUSED`` evidence — split out purely for the
        ``tools/tos_size_budget.py`` function-length budget, no behavioural change). THIS method
        still owns the actual storage-layer clear call — the machine pin
        ``tests/engine/test_no_direct_latch_clear.py`` allows only this file to call
        :meth:`~tos_runtime.engine.inbox.SqliteEventInbox.clear_new_risk_halt` — plus the
        ``NEW_RISK_HALT_CLEARED_BY_OPERATOR`` evidence (BEFORE that call) and the
        ``NEW_RISK_HALT_CLEAR_REFUSED`` row for the one refusal only IT can observe: the
        storage-layer TOCTOU (a concurrent relatch changing the seq between the pre-check and the
        clear — a narrow, honestly-disclosed window this single-threaded runtime does not
        currently reach, since :class:`~tos_runtime.engine.driver.EngineDriver` is itself
        single-threaded).

        Args:
            latched_evidence_seq: The ``evidence_seq`` of the violation the operator reviewed.
                Must equal the CURRENTLY-latched row's own seq — a stale value is refused (with a
                ``NEW_RISK_HALT_CLEAR_REFUSED`` evidence row, per RR3).
            approvals_dir: The directory
                ``approvals_dir/rearm/<latched_evidence_seq>.yaml`` is resolved under (the same
                root :mod:`tos_runtime.authority.iap` uses for
                ``approvals/<proposal_digest>.yaml``).

        Returns:
            :class:`~tos_runtime.engine.inbox.NewRiskHaltClearOutcome` — :attr:`~tos_runtime
            .engine.inbox.NewRiskHaltClearOutcome.CLEARED` on success; ``NO_LATCH`` /
            ``SEQ_MISMATCH`` / ``QUORUM_REFUSED`` / ``STORAGE_REFUSED`` on refusal (the latch,
            if any, is left completely untouched in every refusal case).
        """
        current = self.inbox.new_risk_halt()
        decision = prepare_new_risk_halt_clear(
            current=current,
            latched_evidence_seq=latched_evidence_seq,
            approvals_dir=approvals_dir,
            evidence_store=self.evidence_store,
            inbox=self.inbox,
            time_service=self.time_service,
            environment_label=self.identity.cell_id or "",
            expected_owner_uid=os.getuid(),
            refused_kind=self._NEW_RISK_HALT_CLEAR_REFUSED_KIND,
        )
        if decision.refusal is not None:
            return decision.refusal

        assert (
            current is not None
        )  # decision.refusal is None only past the NO_LATCH check
        attestation_text = decision.attestation_text
        assert attestation_text is not None  # non-None exactly when refusal is None
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
