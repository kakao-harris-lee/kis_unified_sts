"""``tos_runtime.compose._safety_wiring`` — Phase 5 W3 safety-mesh construction (plan
``docs/plans/2026-09-11-tos-phase5-w3-safety-mesh-plan.md`` §2 decision 8).

The ONE call site that builds the four W3-a1/a2 safety-mesh services
(:class:`~tos_runtime.safety.profile.SafetyProfileService`,
:class:`~tos_runtime.safety.deviation.DeviationService`,
:class:`~tos_runtime.safety.incident.IncidentService`,
:class:`~tos_runtime.safety.monitoring.MonitoringService`) and the item-16 latch/capacity
owners (:mod:`tos_runtime.safety.latch`, W3-c), and bundles everything three consumers
need generically (plan §2 decision 1 — the shared :class:`~tos_runtime.safety.ports
.SafetyMeshService` shape):

(i)   the currentness owner seam — :func:`build_safety_mesh` returns one
      ``dimension_readers`` map entry per service, ready to fold into
      :mod:`tos_runtime.currentness.vector`'s own reader map;
(ii)  the egress deferred-item input — :attr:`_SafetyMesh.deferred_fields` supplies items
      7/8/9/10 for :mod:`tos_runtime.compose.context`'s own ``_deferred_mesh_fields``;
(iii) the Coordinator's third question — :attr:`_SafetyMesh.services` is the
      ``safety_mesh: Sequence[SafetyMeshService]`` :class:`~tos_runtime.compose
      ._preconditions.RuntimeCoordinatorPreconditions` ANDs together.

**The late-bound inbox cell.** :class:`~tos_runtime.safety.latch.RestrictiveLatchOwner`
needs a :class:`~tos_runtime.safety.latch.NewRiskHaltReader` and
:class:`~tos_runtime.safety.monitoring.MonitoringService` needs an
``inbox_unconsumed_observer`` — both over the durable
:class:`~tos_runtime.engine.inbox.SqliteEventInbox`, which does not exist until
:func:`~tos_runtime.compose._engine_wiring.wire_engine_and_driver` builds it (inside
``_finalize``, well AFTER this module's own construction point in ``_boot_services``,
design #40 §5 order 5-6). Both close over the SAME :class:`_InboxCell` mutable cell
instead — :func:`~tos_runtime.compose.root.compose_paper_runtime` fills it in once the
inbox exists, strictly before handing the composed runtime to any caller that could
drive an attempt (the identical "구성 순서" discipline
:mod:`tos_runtime.compose._currentness_wiring`'s own ``_RecoveryDimensionState`` /
``_EnvironmentScopeDimensionState`` already document for their own late-bound cells).

**``DeviationService.combined_within_envelope`` carry-over (team-lead follow-up,
2026-09-11).** :class:`~tos_runtime.safety.deviation.DeviationService`'s constructor
takes only ``deviations_path`` — no injection point for
``active_set.combined_within_envelope`` (an §13 item-3 spg-injected verdict its own module
docstring already flags as "no live wiring yet"). Composing the four services here does
NOT change that: this module supplies no such injection because none exists to supply it
to — the config-file attestation stands, unmodified, as a documented, honest gap, never
silently forced through a constructor that has no parameter for it (W3.2 follow-up
candidate, per the plan's own "no honest source, do not fake" rule).

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``pathlib``)
+ ``tos.cur`` (``DimensionKey``) + ``tos.egress`` (``RestrictiveLatchState``,
transitively via ``tos_runtime.safety.latch``) + ``tos_runtime.*`` only. No ``shared.*``.
LOW-7 (W3.1 independent review): this module never imports ``sqlite3`` directly — the
evidence-tip/inbox-backlog observers go through ``SqliteEvidenceStore.last_committed_
excluding``/``SqliteEventInbox.unconsumed_count``'s own public APIs (both
``tos_runtime.*``, already covered above).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tos.cur import DimensionKey
from tos.engine.records import InstrumentKey
from tos.time import HealthState

from tos_runtime.currentness.vector import DimensionReport
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.projection import ReservationProjectionReader
from tos_runtime.safety.deviation import DeviationService
from tos_runtime.safety.incident import IncidentService
from tos_runtime.safety.latch import (
    CapacityOwner,
    NewRiskHaltReader,
    RestrictiveLatchOwner,
)
from tos_runtime.safety.monitoring import AlertRecorder, MonitoringService
from tos_runtime.safety.ports import MeshClearance, SafetyMeshService
from tos_runtime.safety.profile import SafetyProfileService
from tos_runtime.time.service import TrustworthyTimeService
from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "SAFETY_MESH_CONFIG_FILE_NAMES",
    "SafetyMeshSnapshot",
    "_InboxCell",
    "_SafetyMesh",
    "_SafetyMeshTickCell",
    "build_capacity_owner",
    "build_safety_mesh",
]

_SAFETY_ENVELOPE_CONFIG_NAME = "safety_envelope.yaml"
_SAFETY_PROFILE_CONFIG_NAME = "safety_profile.yaml"
_SAFETY_ACTIVATION_CONFIG_NAME = "safety_activation.yaml"
_SAFETY_DEVIATIONS_CONFIG_NAME = "safety_deviations.yaml"
_SAFETY_INCIDENTS_CONFIG_NAME = "safety_incidents.yaml"
_MONITOR_COVERAGE_CONFIG_NAME = "monitor_coverage.yaml"

#: Every safety-mesh policy-document file name under a compose ``config_dir`` (plan §2
#: decision 8) — used both to load them (below) and to fold their digests into
#: ``OPERATOR_ATTESTED_INPUTS`` (``_wiring.py``'s own ``extra_config_files`` seam).
SAFETY_MESH_CONFIG_FILE_NAMES: tuple[str, ...] = (
    _SAFETY_ENVELOPE_CONFIG_NAME,
    _SAFETY_PROFILE_CONFIG_NAME,
    _SAFETY_ACTIVATION_CONFIG_NAME,
    _SAFETY_DEVIATIONS_CONFIG_NAME,
    _SAFETY_INCIDENTS_CONFIG_NAME,
    _MONITOR_COVERAGE_CONFIG_NAME,
)

#: ``STM_ALERT`` — the one evidence kind :class:`~tos_runtime.safety.monitoring.MonitoringService`
#: emits through its injected ``evidence_recorder`` (plan §2 decision 8; that module's own
#: docstring: "this runtime knows no delivery channel for the alert itself").
_STM_ALERT_KIND = "STM_ALERT"

#: Nanoseconds per millisecond — :class:`~tos_runtime.time.sources.MonotonicSource` reports
#: milliseconds, :class:`~tos_runtime.safety.monitoring.MonitoringService`'s stall detector
#: wants nanoseconds (module docstring item 1).
_NS_PER_MS = 1_000_000


class _TimeHealthAdapter:
    """Adapts :class:`~tos_runtime.time.service.TrustworthyTimeService` (a ``health_state``
    PROPERTY) to :class:`~tos_runtime.safety.profile.SafetyProfileService`'s own
    ``TimeHealthSource`` Protocol (a ``health_state()`` METHOD) — a reported shim, not a
    second time service."""

    def __init__(self, time_service: TrustworthyTimeService) -> None:
        self._time_service = time_service

    def health_state(self) -> HealthState:
        return self._time_service.health_state


@dataclass
class _InboxCell:
    """The late-bound cell :class:`~tos_runtime.safety.latch.RestrictiveLatchOwner`'s
    inbox reader and :class:`~tos_runtime.safety.monitoring.MonitoringService`'s
    ``inbox_unconsumed_observer`` both close over (module docstring)."""

    inbox: SqliteEventInbox | None = None


class _LateBoundInboxReader:
    """Satisfies :class:`~tos_runtime.safety.latch.NewRiskHaltReader` over an
    :class:`_InboxCell` that starts empty (module docstring). Before the cell is filled,
    ``new_risk_halt()`` reports ``None`` (no latch observed) — never reachable in
    practice, since no attempt is ever driven before ``compose_paper_runtime`` fills the
    cell in (the same dead-pre-fill-window reasoning ``_RecoveryDimensionState``'s own
    docstring already documents)."""

    def __init__(self, cell: _InboxCell) -> None:
        self._cell = cell

    def new_risk_halt(self) -> Mapping[str, object] | None:
        if self._cell.inbox is None:
            return None
        return self._cell.inbox.new_risk_halt()


def _inbox_unconsumed_observer_for(cell: _InboxCell) -> Callable[[], int]:
    """The ``inbox_unconsumed_observer`` port :class:`~tos_runtime.safety.monitoring
    .MonitoringService` needs (that module's own docstring, item 3). Reads
    :attr:`~tos_runtime.engine.inbox.SqliteEventInbox.unconsumed_count` — the public
    property that owns this observation (added alongside this wiring specifically so
    this module never has to reach into the inbox's private connection).

    Returns ``0`` before the cell is filled (module docstring dead-window reasoning) —
    never a fabricated backlog count.
    """

    def _observer() -> int:
        inbox = cell.inbox
        if inbox is None:
            return 0
        return inbox.unconsumed_count

    return _observer


def _stm_alert_recorder_for(evidence_store: SqliteEvidenceStore) -> AlertRecorder:
    """The ``evidence_recorder`` port :class:`~tos_runtime.safety.monitoring
    .MonitoringService` needs — mirrors the ``(kind, fields) -> None`` shape that
    module's own docstring cites (:class:`~tos_runtime.transport.kis_mock.adapter
    .EvidenceRecorder`'s shape), over this composition's real evidence store."""

    def _recorder(kind: str, fields: Mapping[str, Any]) -> None:
        evidence_store.append(dict(fields), kind=kind, record_class=_STM_ALERT_KIND)

    return _recorder


def _evidence_tip_observer_excluding_own_alerts(
    evidence_store: SqliteEvidenceStore,
) -> Callable[[], tuple[int | None, str, int | None]]:
    """The ``evidence_tip_observer`` port :class:`~tos_runtime.safety.monitoring
    .MonitoringService` needs (W3.1 independent review HIGH-1).

    **Self-perturbation, and why this seam exists.** The SAME evidence store also
    receives this service's own ``STM_ALERT`` writes
    (:func:`_stm_alert_recorder_for`, above). Wiring the plain
    :meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.last_committed` here would
    let a genuine, continuing stall flap deny/clear/clear: the very ``STM_ALERT`` this
    service emits on a non-``True`` :meth:`~tos_runtime.safety.monitoring.MonitoringService.clear`
    advances the tip the NEXT call reads, which that call would then honestly (but
    wrongly) read as "the tip advanced" and reset the stall clock. Reads
    :meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.last_committed_excluding`
    instead — the SAME store, with its own ``STM_ALERT`` kind excluded from
    consideration — so the observation is independent of this service's own writes
    (the module docstring's own "Wiring contract").
    """
    excluded = frozenset({_STM_ALERT_KIND})

    def _observer() -> tuple[int | None, str, int | None]:
        return evidence_store.last_committed_excluding(excluded)

    return _observer


@dataclass(frozen=True)
class SafetyMeshSnapshot:
    """One consistent, per-tick evaluation of every safety-mesh service (team-lead
    disposition following the HIGH-1/HIGH-2 fixes: :meth:`~tos_runtime.safety.ports
    .SafetyMeshService.clear` is now STATEFUL for at least one service — MONITORING's
    continuity tracking advances on every call — so 3+ independent call sites within
    the SAME tick could each see a DIFFERENT answer, not merely a wasted extra call).

    Computed exactly once per tick via :func:`_refresh_tick_snapshot` (the
    Coordinator's third question calls this UNCONDITIONALLY, at the top of every
    ``live_scope_authorized`` call — kernel diff 0, this is purely a runtime-side
    coordination point) and read — never independently recomputed — by every LATER
    consumer in that same tick via :func:`_current_tick_snapshot` (the currentness
    dimension readers, the deferred-mesh-fields supply, and the item-16 latch
    owner's ``incident_clear``/``profile_clear`` closures).

    **``tick_generation`` (W3.1 independent review MEDIUM-8, latent: M17 survives).**
    A snapshot carries no signal of ITS OWN staleness without this: if the Coordinator's
    refresh is skipped for a whole tick (the kernel's own ``authority_epoch_current()``
    gate — design #31 §9-10 — already refuses BEFORE ``live_scope_authorized`` is ever
    reached, per ``tos.engine.core``'s own gate-①-then-② sequencing), a LATER same-tick
    (or several-ticks-later) consumer reading the cell would see a snapshot from
    whenever the Coordinator last actually ran, with no way to tell it apart from a
    genuinely current one. ``tick_generation`` is stamped from the durable
    :class:`~tos_runtime.engine.inbox.SqliteEventInbox`'s own ``count`` (how many events
    this runtime has EVER admitted — already shared via :class:`_InboxCell`, and already
    monotonic and externally observable independent of whether the Coordinator gate ever
    ran) — ``None`` only in the dead pre-``_finalize`` window before the inbox exists.
    """

    clearances: Mapping[str, MeshClearance]
    reports: Mapping[str, DimensionReport | None]
    tick_generation: int | None

    def clear_for(self, identity: str) -> MeshClearance | None:
        """This service's clearance from THIS snapshot, or ``None`` if ``identity``
        was not one of the services this snapshot was taken over."""
        return self.clearances.get(identity)

    def report_for(self, identity: str) -> DimensionReport | None:
        """This service's currentness dimension report from THIS snapshot — ``None``
        both when ``identity`` is unknown and when the service itself reported no
        dimension (the two cases are indistinguishable here, and both are honestly
        absent either way)."""
        return self.reports.get(identity)

    @staticmethod
    def take(
        services: Sequence[SafetyMeshService], *, tick_generation: int | None
    ) -> SafetyMeshSnapshot:
        """Evaluate every service's :meth:`~tos_runtime.safety.ports.SafetyMeshService
        .clear` and :meth:`~tos_runtime.safety.ports.SafetyMeshService.dimension_report`
        exactly once each, in the order given, and stamp the result with
        ``tick_generation`` (the class docstring's own MEDIUM-8 rationale)."""
        clearances: dict[str, MeshClearance] = {}
        reports: dict[str, DimensionReport | None] = {}
        for service in services:
            clearances[service.identity] = service.clear()
            reports[service.identity] = service.dimension_report()
        return SafetyMeshSnapshot(
            clearances=clearances, reports=reports, tick_generation=tick_generation
        )


@dataclass
class _SafetyMeshTickCell:
    """The mutable holder :func:`_refresh_tick_snapshot`/:func:`_current_tick_snapshot`
    share — starts empty every boot, and is overwritten (never merged, never
    incrementally updated) on every tick by the Coordinator's own unconditional
    refresh."""

    snapshot: SafetyMeshSnapshot | None = None


def _current_tick_generation(inbox_cell: _InboxCell) -> int | None:
    """The honest per-tick identity :class:`SafetyMeshSnapshot`'s own docstring
    documents (MEDIUM-8) — ``None`` only before ``_finalize`` binds the durable inbox
    (the dead pre-boot-completion window, mirrors every other late-bound cell's own
    "absent until filled" discipline)."""
    inbox = inbox_cell.inbox
    return inbox.count if inbox is not None else None


def _refresh_tick_snapshot(
    services: Sequence[SafetyMeshService],
    cell: _SafetyMeshTickCell,
    inbox_cell: _InboxCell,
) -> SafetyMeshSnapshot:
    """Take a FRESH :class:`SafetyMeshSnapshot`, unconditionally, and store it into
    ``cell`` — the Coordinator's own call, made once per tick regardless of which
    branch ``live_scope_authorized`` ultimately takes (so the cell holds a genuinely
    current snapshot before ANY later same-tick consumer runs, synthetic transport
    included — plan §2 decision 5's own "synthetic e2e 불변" is unaffected, since this
    call authors no admission judgement of its own)."""
    snapshot = SafetyMeshSnapshot.take(
        services, tick_generation=_current_tick_generation(inbox_cell)
    )
    cell.snapshot = snapshot
    return snapshot


def _current_tick_snapshot(
    services: Sequence[SafetyMeshService],
    cell: _SafetyMeshTickCell,
    inbox_cell: _InboxCell,
) -> SafetyMeshSnapshot:
    """Reuse THIS tick's already-taken snapshot when one exists AND its
    ``tick_generation`` still matches the inbox's current count (the normal live path —
    the Coordinator always refreshes first, in the SAME tick, before this ever runs);
    otherwise take a fresh one now (MEDIUM-8: a generation MISMATCH means the
    Coordinator's own refresh was skipped for one or more ticks — e.g. the kernel's
    ``authority_epoch_current()`` gate refused before ``live_scope_authorized`` was ever
    reached — so the cell's snapshot is honestly stale and this consumer self-heals
    rather than silently trusting it; an EMPTY cell, e.g. a unit test exercising a
    reader with no Coordinator call in front of it, is just the ``None == None``
    instance of the same comparison — never a crash either way)."""
    current_generation = _current_tick_generation(inbox_cell)
    if (
        cell.snapshot is not None
        and cell.snapshot.tick_generation == current_generation
    ):
        return cell.snapshot
    return _refresh_tick_snapshot(services, cell, inbox_cell)


@dataclass
class _SafetyMesh:
    """Everything :func:`build_safety_mesh` assembles — handed to
    :mod:`tos_runtime.compose._currentness_wiring` (dimension readers),
    :mod:`tos_runtime.compose.context` (deferred fields + latch), and
    :mod:`tos_runtime.compose._engine_wiring` (Coordinator ``safety_mesh``)."""

    #: The four services, in currentness-item order (7, 8, 9, 10) — this exact tuple is
    #: the Coordinator's own ``safety_mesh: Sequence[SafetyMeshService]``.
    services: tuple[SafetyMeshService, ...]
    #: ``DimensionKey -> (owner_identity, reader)`` — ready to fold into
    #: ``CurrentnessAssembler``'s own reader map.
    dimension_readers: dict[
        DimensionKey, tuple[str, Callable[[], DimensionReport | None]]
    ]
    #: Items 7/8/9/10's deferred egress-mesh fields, evaluated fresh on every call — never
    #: cached across ticks (mirrors ``ComposeContextResolver._deferred_mesh_fields``'s own
    #: item-4 discipline).
    deferred_fields: Callable[[], dict[str, Any]]
    #: The item-16 restrictive-latch owner (W3-c) — still needs :attr:`inbox_cell` filled
    #: in before ``compose_paper_runtime`` returns.
    latch: RestrictiveLatchOwner
    #: The late-bound cell both :attr:`latch` and the MONITORING dimension/deferred-field
    #: reader close over — ``compose_paper_runtime`` fills in ``.inbox`` once
    #: ``_finalize`` builds the durable inbox.
    inbox_cell: _InboxCell
    #: The Coordinator's own per-tick refresh (:func:`_refresh_tick_snapshot`, bound over
    #: :attr:`services` and the shared tick cell) — called UNCONDITIONALLY, once per
    #: tick, by :class:`~tos_runtime.compose._preconditions.RuntimeCoordinatorPreconditions`.
    refresh_tick_snapshot: Callable[[], SafetyMeshSnapshot]
    #: Every safety-mesh policy-document path this call loaded — for
    #: ``OPERATOR_ATTESTED_INPUTS`` (``extra_config_files``).
    config_files: tuple[Path, ...] = field(default_factory=tuple)


def build_capacity_owner(
    projection: ReservationProjectionReader, scope: InstrumentKey
) -> CapacityOwner:
    """Build the item-16 ``worst_credible_capacity`` owner (plan §2 decision 6) — a thin,
    stateless wrapper (no config, no late-bound cell needed), so
    :mod:`tos_runtime.compose._wiring`'s ``_build_context_resolver`` constructs it
    directly once ``instrument_key`` is known, rather than threading it through this
    module's own early construction window."""
    return CapacityOwner(projection, scope)


def _clear_value(snapshot: SafetyMeshSnapshot, identity: str) -> bool | None:
    """The tri-state ``clear`` value for ``identity`` from ``snapshot`` — ``None`` both
    when the service reported ``None`` (unestablished) and when ``identity`` is
    somehow absent from the snapshot (never reachable in production wiring — every
    identity here comes from the SAME ``services`` tuple the snapshot was taken over —
    but never a crash on a caller's typo either)."""
    clearance = snapshot.clear_for(identity)
    return None if clearance is None else clearance.clear


def _mesh_dimension_reader_for(
    identity: str,
    services: Sequence[SafetyMeshService],
    cell: _SafetyMeshTickCell,
    inbox_cell: _InboxCell,
) -> Callable[[], DimensionReport | None]:
    """One safety-mesh service's currentness dimension reader, sourced from the SAME
    per-tick :class:`SafetyMeshSnapshot` the other two consumers read (never a second,
    independent ``service.dimension_report()`` call — see that class's own docstring).
    """

    def _reader() -> DimensionReport | None:
        return _current_tick_snapshot(services, cell, inbox_cell).report_for(identity)

    return _reader


def build_safety_mesh(
    config_dir: Path,
    *,
    evidence_store: SqliteEvidenceStore,
    time_service: TrustworthyTimeService,
    monotonic_source: MonotonicSource,
) -> _SafetyMesh:
    """Load + construct the four W3-a1/a2 safety-mesh services and the item-16
    restrictive-latch owner (module docstring) — the ONE call
    :func:`~tos_runtime.compose._wiring._boot_services` makes into this module (plan §2
    decision 8, "``_wiring.py``는 1호출+import만").

    Args:
        config_dir: The SAME compose config directory every other ``tos_runtime.*.config``
            loader reads from.
        evidence_store: This composition's real evidence store — the MONITORING service's
            ``STM_ALERT`` sink.
        time_service: This composition's real Trustworthy Time service — the
            SAFETY_ENVELOPE_PROFILE service's time-verifiability port (via
            :class:`_TimeHealthAdapter`) and the MONITORING service's own health
            observation.
        monotonic_source: This composition's real monotonic clock — the MONITORING
            service's stall-detector clock.

    Raises:
        SafetyProfileConfigError / DeviationConfigError / IncidentConfigError /
        MonitoringConfigError: Any of the six policy documents is missing, malformed, or
            still carries an unfilled (named-TBD) field — fail-closed at construction,
            never a partially-built mesh.
    """
    profile_service = SafetyProfileService(
        envelope_path=config_dir / _SAFETY_ENVELOPE_CONFIG_NAME,
        profile_path=config_dir / _SAFETY_PROFILE_CONFIG_NAME,
        activation_path=config_dir / _SAFETY_ACTIVATION_CONFIG_NAME,
        time_source=_TimeHealthAdapter(time_service),
    )
    deviation_service = DeviationService(
        deviations_path=config_dir / _SAFETY_DEVIATIONS_CONFIG_NAME
    )
    incident_service = IncidentService(
        config_path=config_dir / _SAFETY_INCIDENTS_CONFIG_NAME
    )
    inbox_cell = _InboxCell()
    monitoring_service = MonitoringService(
        config_path=config_dir / _MONITOR_COVERAGE_CONFIG_NAME,
        evidence_tip_observer=_evidence_tip_observer_excluding_own_alerts(
            evidence_store
        ),
        time_health_observer=lambda: time_service.health_state.value,
        inbox_unconsumed_observer=_inbox_unconsumed_observer_for(inbox_cell),
        monotonic_ns=lambda: monotonic_source.now_ms() * _NS_PER_MS,
        evidence_recorder=_stm_alert_recorder_for(evidence_store),
    )
    # Boot-time warm-up (never a fabricated verdict): MonitoringService's own honest
    # continuity contract reports source_continuity_present=None (UNKNOWN) on the VERY
    # FIRST observation it ever makes, on ANY instance, since there is no prior
    # (seq, chain_digest) to compare against yet (monitoring.py's own "Honest-source
    # table"). Left unaddressed, the FIRST real DECISION_TICK after boot would see the
    # Coordinator's third question -- the first call this instance ever makes -- read
    # UNKNOWN and refuse, even on an otherwise healthy runtime. Discharging that one
    # unavoidable "no baseline yet" observation here, at boot (before any attempt is
    # ever driven), is what a production system does before trusting a stall detector
    # -- an honest warm-up read, never a second judgement authored by this module
    # (mesh services still author none; this call only primes internal state a real
    # kernel-predicate call already governs on every LATER call).
    monitoring_service.clear()
    services: tuple[SafetyMeshService, ...] = (
        profile_service,
        deviation_service,
        incident_service,
        monitoring_service,
    )
    # Team-lead disposition (post-HIGH-1/HIGH-2): clear() is now STATEFUL for at least
    # one service (MONITORING's continuity tracking), so the three per-tick consumers
    # below (dimension readers, deferred fields, the latch's incident/profile closures)
    # all read from ONE SafetyMeshSnapshot per tick instead of each calling .clear()/
    # .dimension_report() independently — see SafetyMeshSnapshot's own docstring.
    tick_cell = _SafetyMeshTickCell()
    dimension_readers: dict[
        DimensionKey, tuple[str, Callable[[], DimensionReport | None]]
    ] = {
        service.dimension_key: (
            service.identity,
            _mesh_dimension_reader_for(
                service.identity, services, tick_cell, inbox_cell
            ),
        )
        for service in services
    }

    def _deferred_fields() -> dict[str, Any]:
        snapshot = _current_tick_snapshot(services, tick_cell, inbox_cell)
        return {
            "safety_profile_current": _clear_value(snapshot, profile_service.identity),
            "deviation_clear": _clear_value(snapshot, deviation_service.identity),
            "incident_clear": _clear_value(snapshot, incident_service.identity),
            "monitoring_clear": _clear_value(snapshot, monitoring_service.identity),
        }

    latch: NewRiskHaltReader = _LateBoundInboxReader(inbox_cell)
    restrictive_latch = RestrictiveLatchOwner(
        latch,
        incident_clear=lambda: _clear_value(
            _current_tick_snapshot(services, tick_cell, inbox_cell),
            incident_service.identity,
        ),
        profile_clear=lambda: _clear_value(
            _current_tick_snapshot(services, tick_cell, inbox_cell),
            profile_service.identity,
        ),
    )
    return _SafetyMesh(
        services=services,
        dimension_readers=dimension_readers,
        deferred_fields=_deferred_fields,
        latch=restrictive_latch,
        inbox_cell=inbox_cell,
        refresh_tick_snapshot=lambda: _refresh_tick_snapshot(
            services, tick_cell, inbox_cell
        ),
        config_files=tuple(config_dir / name for name in SAFETY_MESH_CONFIG_FILE_NAMES),
    )
