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

**The declared band source** (CP-3 band 원천 웨이브,
``docs/plans/2026-10-08-tos-cp3-band-source-wave-plan.md`` §4.3). When the
active policy declares a ``_runtime.band_source``, this service is handed a
``band_reader`` and a ``trading_date_reader`` and folds the observed broker
price band into the EFFECTIVE shape constraints
(:attr:`VenueConstraintService.shape_constraints`, now a property). Four
statements govern it, and each one is a test in plan §8:

* **Both readers ``None`` ⇒ byte-identical behaviour to before this wave.**
  Every new evidence key is gated on the POLICY declaring a band source, not
  on a reader being present, so a tree with no declaration (today: the
  resident ``paper`` tree and both CP-3 tenant trees, plan §5) emits exactly
  the rows it emitted yesterday.
* **The declared read instants, and only those** — the first snapshot is
  ``"boot"`` and every later phase change is ``"phase_change"``, and a read
  happens only when ``band_source.read_on`` names that token. A policy
  declaring ``["boot"]`` therefore reads exactly once for the life of the
  process. (Independent review M2: ``read_on`` used to be validated by the
  loader and then ignored, so every declaration behaved like both tokens.)
  The 모의 quote rate limit is 1.0 rps
  (``config/tos_runtime/paper/marketfeed.yaml:101-103``, probe P-13), and plan
  §2 shows a same-day band can only WIDEN, so reading once at boot is the
  conservative direction, not a shortcut.
* **The trading-date bond runs BEFORE the tick-generation cache early
  return** (plan §4.4a). Behind that early return the check would be skipped
  for as long as the tick generation did not move — which is exactly the
  overnight state the bond exists for.
* **Re-issue only on a state TRANSITION** (plan §4.3's review L3). A band
  change is a material change under ADR-002-019 §18 and takes a new
  Constraint Generation — but the only same-phase band transition this
  runtime can actually produce is the trading-date bond DROPPING a stale
  band, because every read coincides with a phase change, which already
  re-issues. A band that is ALREADY ``None`` staying ``None`` is not a
  transition and must not inflate the counter. (Independent review M3: the
  value/continuity comparison that used to sit beside this was measured to
  decide nothing and was deleted — see :meth:`VenueConstraintService
  ._read_band`.)

**The three snapshot fields are a STAND-IN** (plan §4.3's review M3). The
kernel defines ``critical_input_snapshot_digest`` as "CII provenance binding
(capsule-owned; venue binds the digest, §3.5)"
(``tos/src/tos/venue/records.py:489-490``). What this service puts there is
the digest of a RUNTIME :class:`~tos_runtime.venue.band_source
.BandObservation`, not of a kernel ``CriticalInputSnapshot``
(``tos/src/tos/capsule/snapshot.py``). Mechanically the kernel is unchanged
(this field's only consumer is the record itself); semantically the runtime
has overlaid a meaning, so every evidence row this service writes says
``"stand-in"`` in the same idiom ``egress_coordinates.yaml::
capsule_terminus_fields`` uses, and "promote the band observation to a real
``CriticalInputSnapshot``" is registered as a GOV-001 candidate (plan §6 (B)).

Firewall (R1, runtime scope): stdlib + ``tos.*`` + ``tos_runtime.*`` only —
no ``shared.*``.
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
from tos_runtime.venue.band_source import BandObservation, BandReader
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


def _policy_bound_payload(
    loaded_policy: LoadedVenuePolicy, activated_member_digest: str
) -> dict[str, object]:
    """The one boot-time ``VENUE_POLICY_BOUND`` row (plan §2 decision 8).

    The two band-source keys appear ONLY when the policy declares a source (plan §4.5's
    review L2 — a tree that declares none must emit a row byte-identical to yesterday's).
    They exist because activation compares the kernel ``canonical_digest``, which covers
    ``_model_view`` only: a ``_runtime.band_source`` declaration is OUTSIDE it. The
    operator's 2026-10-08 disposition on plan §6 (B) was to fill that gap with evidence and
    register the covered-field promotion as a GOV-001 candidate — never to extend the kernel
    record here.
    """
    payload: dict[str, object] = {
        "policy_id": loaded_policy.policy.policy_id,
        "policy_generation": loaded_policy.policy.policy_generation,
        "canonical_digest": loaded_policy.policy.canonical_digest,
        "activated_member_digest": activated_member_digest,
        "null_shape_bounds": list(loaded_policy.null_shape_bounds),
    }
    if loaded_policy.band_source is not None:
        payload["band_source_digest"] = loaded_policy.band_source_digest
        payload["price_scale"] = loaded_policy.price_scale
    return payload


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
        band_reader: BandReader | None = None,
        trading_date_reader: Callable[[], str | None] | None = None,
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
            band_reader: see :meth:`_adopt_band_source`.
            trading_date_reader: see :meth:`_adopt_band_source`.

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
        self.quantity_constraint = loaded_policy.quantity_constraint
        self._adopt_band_source(loaded_policy, band_reader, trading_date_reader)
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
            _policy_bound_payload(loaded_policy, activated_member_digest),
            kind=VENUE_POLICY_BOUND_KIND,
            record_class=VENUE_POLICY_BOUND_KIND,
        )

    def _adopt_band_source(
        self,
        loaded_policy: LoadedVenuePolicy,
        band_reader: BandReader | None,
        trading_date_reader: Callable[[], str | None] | None,
    ) -> None:
        """Set up this service's band state (module docstring's "the declared band source").

        Args:
            loaded_policy: Its ``band_source`` is the SINGLE source for "does this deployment
                have a band source", and therefore for whether any of this wave's evidence
                keys appear at all (plan §4.5's review L2: a tree that declares none must emit
                rows byte-identical to yesterday's).
            band_reader: The declared source's reader, or ``None`` — the shipped state of
                every tree today (plan §5), in which case this service behaves exactly as it
                did before this wave.
            trading_date_reader: The calendar owner's KST trading-date reading, used ONLY for
                the §4.4a bond. ``None`` makes that bond drop any held band on its next
                evaluation — fail-closed: a band whose date cannot be compared cannot be shown
                to still be today's.
        """
        #: The policy's own shape constraints, untouched. The EFFECTIVE constraints every
        #: consumer reads are :attr:`shape_constraints` (a property since the band-source
        #: wave) — identical to this object whenever no band is held.
        self._policy_shape_constraints: VenueShapeConstraints = (
            loaded_policy.policy.shape_constraints
        )
        #: The effective constraints, recomputed ONLY when the band transitions — so step 3's
        #: decision and the gateway's item 11 re-fold read the SAME object between re-issues
        #: (plan §4.3), never two equal-but-distinct ``model_copy`` results.
        self._effective_shape_constraints: VenueShapeConstraints = (
            self._policy_shape_constraints
        )
        self._band_source_declared = loaded_policy.band_source is not None
        #: The policy's own ``band_source.read_on`` — the instants this service may read at
        #: (independent review M2: it used to be validated by the loader and then ignored).
        #: Empty when no source is declared, which makes the read unreachable either way.
        self._band_read_on: tuple[str, ...] = (
            ()
            if loaded_policy.band_source is None
            else loaded_policy.band_source.read_on
        )
        self._band_reader = band_reader
        self._trading_date_reader = trading_date_reader
        self._band: BandObservation | None = None

    @property
    def shape_constraints(self) -> VenueShapeConstraints:
        """The EFFECTIVE shape constraints — the policy's own, with ``price_min``/``price_max``
        replaced by the held band when there is one (module docstring's "the declared band
        source"; plan §4.3).

        A property rather than the plain attribute it used to be, so the three existing
        consumers (step 3's decision, the venue stage's two folds, the gateway's item 11
        context) see a band appear or disappear without any of them changing what they read.
        """
        return self._effective_shape_constraints

    def snapshot(self) -> VenueConstraintSnapshot:
        """The current tick generation's ``VenueConstraintSnapshot`` — issued
        once per tick generation, re-issued on a session-phase change or a band
        transition (module docstring)."""
        generation = self._tick_generation_reader()
        # (plan §4.4a) The trading-date bond is evaluated BEFORE the tick-generation cache
        # early return below. Behind it, a band held from a previous trading date would
        # survive for as long as the tick generation did not move.
        band_transition = self._enforce_trading_date_bond()
        if (
            not band_transition
            and self.last_snapshot is not None
            and generation == self._cached_tick_generation
        ):
            return self.last_snapshot
        phase = self._session_phase_reader()
        phase_changed = (
            self.last_snapshot is None
            or self.last_snapshot.observed_session_phase != phase
        )
        if phase_changed:
            # `band_source.read_on` is CONSULTED, not merely validated (independent review
            # M2): the very first snapshot is the "boot" instant and every later phase change
            # is a "phase_change" one, and a token the policy did not declare means no read.
            self._read_band("boot" if self.last_snapshot is None else "phase_change")
        if not band_transition and not phase_changed:
            # Same phase, new tick generation, band unchanged — no material change, no
            # re-issue. `last_snapshot` is non-None here (phase_changed is True when it is).
            assert self.last_snapshot is not None
            self._cached_tick_generation = generation
            return self.last_snapshot
        return self._issue_snapshot(phase, generation)

    def _enforce_trading_date_bond(self) -> bool:
        """Drop a held band whose trading date is not the current one (plan §4.4a).

        Returns:
            ``True`` only when this call actually dropped a band — a state TRANSITION (plan
            §4.3's review L3). An already-``None`` band is not re-dropped, so an out-of-session
            process calling :meth:`snapshot` N times does not advance the Constraint Generation
            N times.
        """
        if self._band is None:
            return False
        current = (
            None if self._trading_date_reader is None else self._trading_date_reader()
        )
        if current is not None and current == self._band.trading_date:
            return False
        self._set_band(None)
        return True

    def _read_band(self, instant: str) -> None:
        """Read the declared band source once, if ``instant`` is one the policy declared.

        **Returns nothing on purpose** (independent review M3). An earlier cut returned "did
        the band change" and folded that into the re-issue condition — and the fold decided
        NOTHING: a read only ever happens when the phase changed, and a phase change already
        forces a re-issue, so mutating the comparison to "always changed" AND deleting the fold
        outright both left every test green (measured). Dead logic that looks like a guard is
        exactly what #838 is about, so it is gone rather than left in place. The one same-phase
        band transition that IS reachable — the trading-date bond dropping a stale band — keeps
        its own return value and its own red proof (:meth:`_enforce_trading_date_bond`).
        """
        if self._band_reader is None or instant not in self._band_read_on:
            return
        self._set_band(self._band_reader())

    def _set_band(self, band: BandObservation | None) -> None:
        self._band = band
        self._effective_shape_constraints = (
            self._policy_shape_constraints
            if band is None
            else self._policy_shape_constraints.model_copy(
                update={"price_min": band.price_min, "price_max": band.price_max}
            )
        )

    def _issue_snapshot(
        self, phase: str | None, generation: int | None
    ) -> VenueConstraintSnapshot:
        self._snapshot_issue_count += 1
        constraint_generation = (
            self._snapshot_generation_base + self._snapshot_issue_count
        )
        snapshot_id = f"vsnap-{self._environment_label}-{constraint_generation}"
        band = self._band
        snapshot = VenueConstraintSnapshot.issue(
            scheme=self._scheme,
            snapshot_id=snapshot_id,
            constraint_generation=constraint_generation,
            policy_id=self.policy.policy_id,
            policy_generation=self.policy.policy_generation,
            policy_digest=self.policy.canonical_digest,
            observed_session_phase=phase,
            action_tradability=(),
            # The three fields plan §4.3 binds the band observation into. STAND-IN semantics
            # (module docstring's own section) — kernel record fields added: 0.
            critical_input_snapshot_digest=(
                None if band is None else band.record_digest
            ),
            source_continuity_id=(None if band is None else band.source_continuity_id),
            max_age=(None if band is None else f"trading_date_kst:{band.trading_date}"),
        )
        assert isinstance(snapshot, VenueConstraintSnapshot)
        absent_fields = [
            name
            for name in _SNAPSHOT_ABSENT_FIELD_NAMES
            if getattr(snapshot, name) is None
        ]
        payload: dict[str, object] = {
            "snapshot_id": snapshot.snapshot_id,
            "canonical_digest": snapshot.canonical_digest,
            "constraint_generation": snapshot.constraint_generation,
            "observed_session_phase": snapshot.observed_session_phase,
            "policy_digest": snapshot.policy_digest,
            "absent_fields": absent_fields,
        }
        if self._band_source_declared:
            payload["band_digest"] = None if band is None else band.record_digest
            payload["critical_input_snapshot_digest_role"] = "stand-in"
        self._evidence_store.append(
            payload,
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
