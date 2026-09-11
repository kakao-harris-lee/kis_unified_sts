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
``_EgressIdentityDimensionState`` already document for their own late-bound cells).

**``DeviationService.combined_within_envelope`` carry-over (team-lead follow-up,
2026-09-11).** :class:`~tos_runtime.safety.deviation.DeviationService`'s constructor
takes only ``deviations_path`` — no injection point for
``active_set.combined_within_envelope`` (an §13 item-3 spg-injected verdict its own module
docstring already flags as "no live wiring yet"). Composing the four services here does
NOT change that: this module supplies no such injection because none exists to supply it
to — the config-file attestation stands, unmodified, as a documented, honest gap, never
silently forced through a constructor that has no parameter for it (W3.2 follow-up
candidate, per the plan's own "no honest source, do not fake" rule).

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``pathlib``,
``sqlite3``) + ``tos.cur`` (``DimensionKey``) + ``tos.egress`` (``RestrictiveLatchState``,
transitively via ``tos_runtime.safety.latch``) + ``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tos.cur import DimensionKey
from tos.engine.records import InstrumentKey

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
from tos_runtime.safety.ports import SafetyMeshService
from tos_runtime.safety.profile import SafetyProfileService
from tos_runtime.time.service import TrustworthyTimeService
from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "SAFETY_MESH_CONFIG_FILE_NAMES",
    "_InboxCell",
    "_SafetyMesh",
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

    def health_state(self) -> Any:
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
    .MonitoringService` needs (that module's own docstring, item 3 — "no public reader
    for this exists on ``SqliteEventInbox`` today ... the compose layer supplies the
    actual closure"). Reads the durable partial index
    (``tos_runtime.engine.inbox``'s own ``ON events (seq) WHERE consumed_evidence_seq IS
    NULL``) directly off the inbox's own sqlite connection — a reported shim (this
    module reaches ``SqliteEventInbox``'s private ``_conn``, mirroring
    :mod:`tos_runtime.compose.context`'s own precedent of reaching into a sibling
    module's private attribute when no public accessor exists yet).

    Returns ``0`` before the cell is filled (module docstring dead-window reasoning) —
    never a fabricated backlog count.
    """

    def _observer() -> int:
        inbox = cell.inbox
        if inbox is None:
            return 0
        row = inbox._conn.execute(  # noqa: SLF001 - reported shim, see docstring
            "SELECT COUNT(*) FROM events WHERE consumed_evidence_seq IS NULL"
        ).fetchone()
        return int(row[0]) if row is not None else 0

    return _observer


def _stm_alert_recorder_for(evidence_store: SqliteEvidenceStore) -> AlertRecorder:
    """The ``evidence_recorder`` port :class:`~tos_runtime.safety.monitoring
    .MonitoringService` needs — mirrors the ``(kind, fields) -> None`` shape that
    module's own docstring cites (:class:`~tos_runtime.transport.kis_mock.adapter
    .EvidenceRecorder`'s shape), over this composition's real evidence store."""

    def _recorder(kind: str, fields: Mapping[str, Any]) -> None:
        evidence_store.append(dict(fields), kind=kind, record_class=_STM_ALERT_KIND)

    return _recorder


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
        evidence_tip_observer=evidence_store.last_committed,
        time_health_observer=lambda: time_service.health_state.value,
        inbox_unconsumed_observer=_inbox_unconsumed_observer_for(inbox_cell),
        monotonic_ns=lambda: monotonic_source.now_ms() * _NS_PER_MS,
        evidence_recorder=_stm_alert_recorder_for(evidence_store),
    )
    services: tuple[SafetyMeshService, ...] = (
        profile_service,
        deviation_service,
        incident_service,
        monitoring_service,
    )
    dimension_readers: dict[
        DimensionKey, tuple[str, Callable[[], DimensionReport | None]]
    ] = {
        service.dimension_key: (service.identity, service.dimension_report)
        for service in services
    }

    def _deferred_fields() -> dict[str, Any]:
        return {
            "safety_profile_current": profile_service.clear().clear,
            "deviation_clear": deviation_service.clear().clear,
            "incident_clear": incident_service.clear().clear,
            "monitoring_clear": monitoring_service.clear().clear,
        }

    latch: NewRiskHaltReader = _LateBoundInboxReader(inbox_cell)
    restrictive_latch = RestrictiveLatchOwner(
        latch,
        incident_clear=lambda: incident_service.clear().clear,
        profile_clear=lambda: profile_service.clear().clear,
    )
    return _SafetyMesh(
        services=services,
        dimension_readers=dimension_readers,
        deferred_fields=_deferred_fields,
        latch=restrictive_latch,
        inbox_cell=inbox_cell,
        config_files=tuple(config_dir / name for name in SAFETY_MESH_CONFIG_FILE_NAMES),
    )
