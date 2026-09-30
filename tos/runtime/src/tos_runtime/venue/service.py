"""tos_runtime.venue.service — ``VenueConstraintService`` (snapshot + decision issuance).

TOS venue constraint service wave, plan §2 decisions 1-3, 7-8, §4.1
(``docs/plans/2026-09-15-tos-venue-constraint-service-plan.md``).

The runtime service that issues the two per-tick / per-attempt artifacts the
plan's "소유 분리" (ownership split) decision assigns to the runtime — never
to config, never to a test fixture: ``VenueConstraintSnapshot`` (issued once
per tick generation, re-issued on a session-phase change) and
``OrderAdmissibilityDecision`` (issued once per admissibility attempt). BOTH
are issued exclusively through the kernel's own ``.issue()`` constructors,
and the ``result``/``failed_predicates``/``unknown_predicates`` a decision
ever carries come EXCLUSIVELY from the kernel's own
``tos.egressgw.construction.fold_venue_admissibility`` (plus the two
sub-predicates it folds, ``session_phase_admits`` / ``order_shape_admissible``,
called here only to NAME which one failed/was unknown — never to author a
result independently). **This module authors no ``OrderAdmissibilityResult``
value itself** (plan §2 decision 1: "런타임은 어느 판정도 저작하지 않는다") —
every ``OrderAdmissibilityResult`` this module ever touches was constructed by
a kernel function, and is only ever compared with ``is``/``is not``
/ membership, never truthiness (the enum's ``__bool__`` raises,
``tos/src/tos/venue/vocabulary.py``).

**Constraint Generation / decision generation are durable monotonic**
(plan §2 decision 2/3): each is ``base + n`` where ``base`` is the count of
pre-existing ``VENUE_SNAPSHOT_ISSUED`` / ``ORDER_ADMISSIBILITY_DECISION_ISSUED``
rows already in the evidence store at CONSTRUCTION time (so a restart resumes
above whatever a prior process already committed — append-only evidence makes
this durable, never an in-memory counter that resets), and ``n`` counts issues
made by THIS process since construction.

**Snapshot caching** (plan §2 decision 2/4): :meth:`snapshot` re-reads the tick
generation on every call; within the SAME tick generation it returns the
already-issued snapshot with no new evidence row. Across a tick-generation
change it re-reads the observed session phase; if the phase is UNCHANGED from
the last issued snapshot, the cached snapshot is kept (constraint_generation
unchanged, no re-issue) — a fresh snapshot is issued only on the very first
call or when the phase actually changed.

Firewall (R1, runtime scope): stdlib + ``tos.*`` + ``tos_runtime.evidence
.store`` only — no ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Callable

from tos.canonical import CanonicalizationScheme
from tos.egressgw import fold_venue_admissibility
from tos.ioc import CanonicalBrokerCommand
from tos.venue import (
    ActionClass,
    InstrumentRouteFields,
    OrderAdmissibilityDecision,
    OrderAdmissibilityResult,
    OrderShapeFields,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
    order_shape_admissible,
    session_phase_admits,
)

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.venue.config import LoadedOrderConstructionPolicy, LoadedVenuePolicy

__all__ = [
    "VENUE_POLICY_BOUND_KIND",
    "ORDER_CONSTRUCTION_POLICY_BOUND_KIND",
    "VENUE_SNAPSHOT_ISSUED_KIND",
    "ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND",
    "VenueConstraintService",
    "record_order_construction_policy_bound",
]

#: Evidence kind string constants (runtime vocabulary — never a kernel
#: ``EvidenceKind`` member, mirroring the ``SESSION_FACTS_*`` idiom in
#: :mod:`tos_runtime.calendar.owner`).
VENUE_POLICY_BOUND_KIND = "VENUE_POLICY_BOUND"
ORDER_CONSTRUCTION_POLICY_BOUND_KIND = "ORDER_CONSTRUCTION_POLICY_BOUND"
VENUE_SNAPSHOT_ISSUED_KIND = "VENUE_SNAPSHOT_ISSUED"
ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND = "ORDER_ADMISSIBILITY_DECISION_ISSUED"

#: The three ``VenueConstraintSnapshot`` fields with no Phase-1 source — always
#: ``None`` (module docstring / plan §2 decision 2). ``action_tradability`` is
#: DELIBERATELY excluded: it is an empty tuple, not ``None`` (fold never reads
#: it, so an empty map is not itself an absent field in the same sense).
_SNAPSHOT_ABSENT_FIELD_NAMES: tuple[str, ...] = (
    "critical_input_snapshot_digest",
    "source_continuity_id",
    "max_age",
)


def record_order_construction_policy_bound(
    evidence_store: SqliteEvidenceStore,
    loaded_ocp: LoadedOrderConstructionPolicy,
    activated_member_digest: str,
) -> None:
    """Record ``ORDER_CONSTRUCTION_POLICY_BOUND`` once, at boot (plan §2
    decision 8).

    A module-level function, not a :class:`VenueConstraintService` method,
    because the Order Construction Policy is bound to step 2's construction
    stages, not to a venue service instance (lane b calls this directly at
    compose boot, alongside constructing the service for step 3).
    """
    evidence_store.append(
        {
            "policy_id": loaded_ocp.policy.policy_id,
            "policy_generation": loaded_ocp.policy.policy_generation,
            "canonical_digest": loaded_ocp.policy.canonical_digest,
            "activated_member_digest": activated_member_digest,
            "wire_codec_kind": loaded_ocp.wire_codec_kind,
        },
        kind=ORDER_CONSTRUCTION_POLICY_BOUND_KIND,
        record_class=ORDER_CONSTRUCTION_POLICY_BOUND_KIND,
    )


def _count_prior_rows(evidence_store: SqliteEvidenceStore, kind: str) -> int:
    """The durable count of pre-existing evidence rows of ``kind`` — the
    basis for a durable-monotonic generation counter surviving a restart
    (module docstring)."""
    row = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
    ).fetchone()
    return 0 if row is None else int(row[0])


class VenueConstraintService:
    """The runtime owner of ``VenueConstraintSnapshot`` /
    ``OrderAdmissibilityDecision`` issuance for one venue policy (plan §4.1).
    """

    def __init__(
        self,
        *,
        loaded_policy: LoadedVenuePolicy,
        scheme: CanonicalizationScheme,
        session_phase_reader: Callable[[], str | None],
        tick_generation_reader: Callable[[], int | None],
        evidence_store: SqliteEvidenceStore,
        environment_label: str,
        route_fields: InstrumentRouteFields,
        broker_capability_profile_version: str | None,
        broker_capability_profile_digest: str | None,
        activated_member_digest: str,
    ) -> None:
        """Construct the service and record its one boot-time
        ``VENUE_POLICY_BOUND`` evidence row (plan §2 decision 8).

        Args:
            loaded_policy: The kernel-issued policy plus its derived
                ``quantity_constraint``/``null_shape_bounds``
                (:func:`tos_runtime.venue.config.load_venue_constraint_policy`).
            scheme: The injected canonicalization scheme (issuance is
                deterministic under it — no ambient default).
            session_phase_reader: Zero-arg callable returning the current
                observed session-phase token, or ``None`` when unobservable
                (never a fabricated phase).
            tick_generation_reader: Zero-arg callable returning the current
                tick generation, or ``None`` before any tick has run.
            evidence_store: Where every evidence row this service appends is
                recorded — ALSO the source of the durable monotonic
                generation bases (module docstring).
            environment_label: Used to compose ``snapshot_id``/``decision_id``
                (``vsnap-<env>-<n>`` / ``vdec-<env>-<n>``).
            route_fields: The exact instrument/route binding a decision binds
                (``OrderAdmissibilityDecision.bound_instrument_route``).
            broker_capability_profile_version: The injected brokercap profile
                version CEILING (``None`` when the profile is still DRAFT —
                never fabricated, plan §2 decision 3).
            broker_capability_profile_digest: The injected brokercap profile
                digest CEILING (``None`` for the same reason).
            activated_member_digest: The activation-record digest this
                policy's activated ``BundleMemberRef`` carries — recorded on
                the boot-time ``VENUE_POLICY_BOUND`` row so an operator can
                see exactly which activation admitted this policy (plan §2
                decision 8's payload list; a deviation from the plan §4.1
                interface listing, since activation happens strictly BEFORE
                construction — see this lane's own report for the
                justification).

        Note:
            ``activated_member_digest`` is not listed in plan §4.1's
            constructor signature block, but plan §2 decision 8's own payload
            description names it explicitly ("activation member digest passed
            in as ``activated_member_digest: str``"). Recording
            ``VENUE_POLICY_BOUND`` at construction (as decision 8 requires)
            is impossible without it, so this constructor adds it as a
            required keyword-only parameter — the one deliberate deviation
            from the fixed §4.1 interface, reported to lane b.
        """
        self.policy: VenueConstraintPolicy = loaded_policy.policy
        self.shape_constraints: VenueShapeConstraints = (
            loaded_policy.policy.shape_constraints
        )
        self.quantity_constraint = loaded_policy.quantity_constraint
        self._scheme = scheme
        self._session_phase_reader = session_phase_reader
        self._tick_generation_reader = tick_generation_reader
        self._evidence_store = evidence_store
        self._environment_label = environment_label
        self._route_fields = route_fields
        self._broker_capability_profile_version = broker_capability_profile_version
        self._broker_capability_profile_digest = broker_capability_profile_digest

        self._snapshot_generation_base = _count_prior_rows(
            evidence_store, VENUE_SNAPSHOT_ISSUED_KIND
        )
        self._decision_generation_base = _count_prior_rows(
            evidence_store, ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND
        )
        self._snapshot_issue_count = 0
        self._decision_issue_count = 0
        self._cached_tick_generation: int | None = None

        self.last_snapshot: VenueConstraintSnapshot | None = None
        self.last_decision: OrderAdmissibilityDecision | None = None

        evidence_store.append(
            {
                "policy_id": self.policy.policy_id,
                "policy_generation": self.policy.policy_generation,
                "canonical_digest": self.policy.canonical_digest,
                "activated_member_digest": activated_member_digest,
                "null_shape_bounds": list(loaded_policy.null_shape_bounds),
            },
            kind=VENUE_POLICY_BOUND_KIND,
            record_class=VENUE_POLICY_BOUND_KIND,
        )

    def snapshot(self) -> VenueConstraintSnapshot:
        """The current tick generation's ``VenueConstraintSnapshot`` — issued
        once per tick generation, re-issued only on a session-phase change
        (module docstring)."""
        generation = self._tick_generation_reader()
        if (
            self.last_snapshot is not None
            and generation == self._cached_tick_generation
        ):
            return self.last_snapshot
        phase = self._session_phase_reader()
        if (
            self.last_snapshot is not None
            and self.last_snapshot.observed_session_phase == phase
        ):
            # Same phase, new tick generation — no material change, no re-issue.
            self._cached_tick_generation = generation
            return self.last_snapshot
        return self._issue_snapshot(phase, generation)

    def _issue_snapshot(
        self, phase: str | None, generation: int | None
    ) -> VenueConstraintSnapshot:
        self._snapshot_issue_count += 1
        constraint_generation = (
            self._snapshot_generation_base + self._snapshot_issue_count
        )
        snapshot_id = f"vsnap-{self._environment_label}-{constraint_generation}"
        snapshot = VenueConstraintSnapshot.issue(
            scheme=self._scheme,
            snapshot_id=snapshot_id,
            constraint_generation=constraint_generation,
            policy_id=self.policy.policy_id,
            policy_generation=self.policy.policy_generation,
            policy_digest=self.policy.canonical_digest,
            observed_session_phase=phase,
            action_tradability=(),
            critical_input_snapshot_digest=None,
            source_continuity_id=None,
            max_age=None,
        )
        assert isinstance(snapshot, VenueConstraintSnapshot)
        absent_fields = [
            name
            for name in _SNAPSHOT_ABSENT_FIELD_NAMES
            if getattr(snapshot, name) is None
        ]
        self._evidence_store.append(
            {
                "snapshot_id": snapshot.snapshot_id,
                "canonical_digest": snapshot.canonical_digest,
                "constraint_generation": snapshot.constraint_generation,
                "observed_session_phase": snapshot.observed_session_phase,
                "policy_digest": snapshot.policy_digest,
                "absent_fields": absent_fields,
            },
            kind=VENUE_SNAPSHOT_ISSUED_KIND,
            record_class=VENUE_SNAPSHOT_ISSUED_KIND,
        )
        self.last_snapshot = snapshot
        self._cached_tick_generation = generation
        return snapshot

    def decide(
        self,
        *,
        action_class: ActionClass,
        shape: OrderShapeFields | None,
        candidate_command: CanonicalBrokerCommand | None,
    ) -> OrderAdmissibilityDecision:
        """Issue one ``OrderAdmissibilityDecision`` for ``action_class`` /
        ``shape`` against the current snapshot (calls :meth:`snapshot` first)
        — one issuance per call, never cached across attempts (plan §2
        decision 1/3)."""
        snapshot = self.snapshot()
        phase_result = session_phase_admits(
            snapshot.observed_session_phase, action_class, snapshot, self.policy
        )
        shape_result = order_shape_admissible(shape, self.shape_constraints)
        result = fold_venue_admissibility(
            observed_session_phase=snapshot.observed_session_phase,
            action_class=action_class,
            snapshot=snapshot,
            policy=self.policy,
            shape=shape,
            constraints=self.shape_constraints,
        )
        failed_predicates, unknown_predicates = _classify_sub_results(
            session_phase_admits=phase_result, order_shape_admissible=shape_result
        )

        self._decision_issue_count += 1
        decision_generation = (
            self._decision_generation_base + self._decision_issue_count
        )
        decision_id = f"vdec-{self._environment_label}-{decision_generation}"
        candidate_command_id = (
            None if candidate_command is None else candidate_command.command_id
        )
        candidate_command_digest = (
            None if candidate_command is None else candidate_command.canonical_digest
        )

        decision = OrderAdmissibilityDecision.issue(
            scheme=self._scheme,
            decision_id=decision_id,
            decision_generation=decision_generation,
            constraint_generation=snapshot.constraint_generation,
            policy_id=self.policy.policy_id,
            policy_generation=self.policy.policy_generation,
            policy_digest=self.policy.canonical_digest,
            snapshot_id=snapshot.snapshot_id,
            snapshot_digest=snapshot.canonical_digest,
            decision_context_capsule_id=None,
            decision_context_capsule_digest=None,
            candidate_command_id=candidate_command_id,
            candidate_command_digest=candidate_command_digest,
            broker_capability_profile_version=self._broker_capability_profile_version,
            broker_capability_profile_digest=self._broker_capability_profile_digest,
            bound_instrument_route=self._route_fields,
            action_class=action_class,
            observed_session_phase=snapshot.observed_session_phase,
            result=result,
            failed_predicates=failed_predicates,
            unknown_predicates=unknown_predicates,
        )
        assert isinstance(decision, OrderAdmissibilityDecision)
        self._evidence_store.append(
            {
                "decision_id": decision.decision_id,
                "canonical_digest": decision.canonical_digest,
                "result": result.value,
                "failed_predicates": list(failed_predicates),
                "unknown_predicates": list(unknown_predicates),
                "candidate_command_digest": candidate_command_digest,
                "snapshot_id": snapshot.snapshot_id,
            },
            kind=ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND,
            record_class=ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND,
        )
        self.last_decision = decision
        return decision


def _classify_sub_results(
    *,
    session_phase_admits: OrderAdmissibilityResult,
    order_shape_admissible: OrderAdmissibilityResult,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Names of the two sub-predicates that failed / were unknown — never a
    third value, never constructed by this function (only compared by
    identity/membership against kernel-returned results, plan §2 decision 1).
    """
    failed: list[str] = []
    unknown: list[str] = []
    for name, sub_result in (
        ("session_phase_admits", session_phase_admits),
        ("order_shape_admissible", order_shape_admissible),
    ):
        if sub_result in (
            OrderAdmissibilityResult.INADMISSIBLE,
            OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY,
        ):
            failed.append(name)
        elif sub_result is OrderAdmissibilityResult.UNKNOWN:
            unknown.append(name)
    return tuple(failed), tuple(unknown)
