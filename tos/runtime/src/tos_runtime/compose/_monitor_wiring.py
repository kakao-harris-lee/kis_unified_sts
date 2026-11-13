"""``tos_runtime.compose._monitor_wiring`` — the slim monitor and the item-16 latch owner.

What is left of the Phase 5 W3 safety-mesh construction after plan S2-a
(``docs/plans/2026-11-13-tos-code-halving-plan.md``) deleted the four mesh services, the
Coordinator's third question and the egress deferred items 7/8/9/10. Two owners remain and
both still need building exactly once per boot:

* :class:`~tos_runtime.safety.monitoring.MonitoringService` — the MONITORING currentness
  dimension's owner (evidence-tip stall + inbox backlog);
* :class:`~tos_runtime.safety.latch.RestrictiveLatchOwner` — the egress item-16
  ``restrictive_latch_state`` owner over the durable new-risk-halt latch.

**The late-bound inbox cell.** Both owners read the durable
:class:`~tos_runtime.engine.inbox.SqliteEventInbox`, which does not exist until
:func:`~tos_runtime.compose._engine_wiring.wire_engine_and_driver` builds it — well AFTER
this module's construction point in ``_boot_services``. Both close over the SAME
:class:`_InboxCell` mutable cell instead, which
:func:`~tos_runtime.compose.root.compose_paper_runtime` fills in once the inbox exists,
strictly before handing the composed runtime to any caller that could drive an attempt.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``pathlib``) +
``tos.cur`` (``DimensionKey``) + ``tos.engine.records`` (``InstrumentKey``) +
``tos_runtime.*`` only. No ``shared.*``. This module never imports ``sqlite3`` directly —
the evidence-tip/inbox-backlog observers go through
``SqliteEvidenceStore.last_committed_excluding`` / ``SqliteEventInbox.unconsumed_count``.
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
from tos_runtime.safety.latch import (
    CapacityOwner,
    NewRiskHaltReader,
    RestrictiveLatchOwner,
)
from tos_runtime.safety.monitoring import AlertRecorder, MonitoringService
from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "MONITOR_CONFIG_FILE_NAMES",
    "_InboxCell",
    "_MonitorOwners",
    "build_capacity_owner",
    "build_monitor_owners",
]

_MONITOR_COVERAGE_CONFIG_NAME = "monitor_coverage.yaml"

#: Every policy-document file name this module loads under a compose ``config_dir`` — used
#: both to load them and to fold their digests into ``OPERATOR_ATTESTED_INPUTS``
#: (``_wiring.py``'s own ``extra_config_files`` seam).
MONITOR_CONFIG_FILE_NAMES: tuple[str, ...] = (_MONITOR_COVERAGE_CONFIG_NAME,)

#: ``STM_ALERT`` — the one evidence kind
#: :class:`~tos_runtime.safety.monitoring.MonitoringService` emits.
_STM_ALERT_KIND = "STM_ALERT"

#: Nanoseconds per millisecond — :class:`~tos_runtime.time.sources.MonotonicSource` reports
#: milliseconds, the monitor's stall detector wants nanoseconds.
_NS_PER_MS = 1_000_000


@dataclass
class _InboxCell:
    """The late-bound cell the latch owner's inbox reader and the monitor's
    ``inbox_unconsumed_observer`` both close over (module docstring)."""

    inbox: SqliteEventInbox | None = None


class _LateBoundInboxReader:
    """Satisfies :class:`~tos_runtime.safety.latch.NewRiskHaltReader` over an
    :class:`_InboxCell` that starts empty. Before the cell is filled, ``new_risk_halt()``
    reports ``None`` (no latch observed) — never reachable in practice, since no attempt is
    ever driven before ``compose_paper_runtime`` fills the cell in."""

    def __init__(self, cell: _InboxCell) -> None:
        self._cell = cell

    def new_risk_halt(self) -> Mapping[str, object] | None:
        """The currently-latched row, or ``None`` (no latch / cell not yet filled)."""
        if self._cell.inbox is None:
            return None
        return self._cell.inbox.new_risk_halt()


def _inbox_unconsumed_observer_for(cell: _InboxCell) -> Callable[[], int]:
    """The ``inbox_unconsumed_observer`` port the monitor needs. Returns ``0`` before the
    cell is filled (module docstring dead-window reasoning) — never a fabricated backlog.
    """

    def _observer() -> int:
        inbox = cell.inbox
        if inbox is None:
            return 0
        return inbox.unconsumed_count

    return _observer


def _stm_alert_recorder_for(evidence_store: SqliteEvidenceStore) -> AlertRecorder:
    """The ``evidence_recorder`` port the monitor needs, over this composition's real
    evidence store."""

    def _recorder(kind: str, fields: Mapping[str, Any]) -> None:
        evidence_store.append(dict(fields), kind=kind, record_class=_STM_ALERT_KIND)

    return _recorder


def _evidence_tip_observer_excluding_own_alerts(
    evidence_store: SqliteEvidenceStore,
) -> Callable[[], tuple[int | None, str, int | None]]:
    """The ``evidence_tip_observer`` port the monitor needs.

    **Self-perturbation, and why this seam exists.** The SAME evidence store also receives
    the monitor's own ``STM_ALERT`` writes (:func:`_stm_alert_recorder_for`). Wiring the
    plain :meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.last_committed` here would
    let a genuine, continuing stall flap: the very ``STM_ALERT`` the monitor emits advances
    the tip the NEXT call reads, which that call would then honestly (but wrongly) read as
    "the tip advanced" and reset the stall clock. Reads ``last_committed_excluding``
    instead — the SAME store, with the monitor's own kind excluded.
    """
    excluded = frozenset({_STM_ALERT_KIND})

    def _observer() -> tuple[int | None, str, int | None]:
        return evidence_store.last_committed_excluding(excluded)

    return _observer


@dataclass
class _MonitorOwners:
    """Everything :func:`build_monitor_owners` assembles — handed to
    :mod:`tos_runtime.compose._currentness_wiring` (the MONITORING dimension reader) and
    :mod:`tos_runtime.compose.context` (the item-16 latch)."""

    monitoring: MonitoringService
    #: ``DimensionKey -> (owner_identity, reader)`` — ready to fold into
    #: ``CurrentnessAssembler``'s own reader map.
    dimension_readers: dict[
        DimensionKey, tuple[str, Callable[[], DimensionReport | None]]
    ]
    #: The item-16 restrictive-latch owner — still needs :attr:`inbox_cell` filled in
    #: before ``compose_paper_runtime`` returns.
    latch: RestrictiveLatchOwner
    #: The late-bound cell both :attr:`latch` and the monitor close over.
    inbox_cell: _InboxCell
    #: Every policy-document path this call loaded — for ``OPERATOR_ATTESTED_INPUTS``.
    config_files: tuple[Path, ...] = field(default_factory=tuple)


def build_capacity_owner(
    projection: ReservationProjectionReader, scope: InstrumentKey
) -> CapacityOwner:
    """Build the item-16 ``worst_credible_capacity`` owner — a thin, stateless wrapper (no
    config, no late-bound cell needed), so ``_wiring.py``'s ``_build_context_resolver``
    constructs it directly once ``instrument_key`` is known."""
    return CapacityOwner(projection, scope)


def build_monitor_owners(
    config_dir: Path,
    *,
    evidence_store: SqliteEvidenceStore,
    monotonic_source: MonotonicSource,
) -> _MonitorOwners:
    """Construct the slim monitor and the item-16 latch owner — the ONE call
    :func:`~tos_runtime.compose._wiring._boot_services` makes into this module.

    Args:
        config_dir: The SAME compose config directory every other ``tos_runtime.*.config``
            loader reads from.
        evidence_store: This composition's real evidence store — the monitor's
            ``STM_ALERT`` sink and its evidence-tip observation source.
        monotonic_source: This composition's real monotonic clock — the monitor's
            stall-detector clock.

    Raises:
        tos_runtime.safety.monitoring.MonitoringConfigError: ``monitor_coverage.yaml`` is
            missing, malformed, or still carries an unfilled (named-TBD) field —
            fail-closed at construction.
    """
    inbox_cell = _InboxCell()
    monitoring = MonitoringService(
        config_path=config_dir / _MONITOR_COVERAGE_CONFIG_NAME,
        evidence_tip_observer=_evidence_tip_observer_excluding_own_alerts(
            evidence_store
        ),
        inbox_unconsumed_observer=_inbox_unconsumed_observer_for(inbox_cell),
        monotonic_ns=lambda: monotonic_source.now_ms() * _NS_PER_MS,
        evidence_recorder=_stm_alert_recorder_for(evidence_store),
    )
    # Boot-time warm-up (never a fabricated verdict): the monitor's own honest contract
    # reports the evidence tip UNKNOWN on the VERY FIRST observation any instance makes,
    # since there is no prior advance timestamp to compare against. Discharging that one
    # unavoidable "no baseline yet" observation here, at boot, before any attempt is ever
    # driven, is what a production system does before trusting a stall detector.
    monitoring.healthy()
    latch_reader: NewRiskHaltReader = _LateBoundInboxReader(inbox_cell)
    return _MonitorOwners(
        monitoring=monitoring,
        dimension_readers={
            monitoring.dimension_key: (
                monitoring.identity,
                monitoring.dimension_report,
            )
        },
        latch=RestrictiveLatchOwner(latch_reader),
        inbox_cell=inbox_cell,
        config_files=(config_dir / _MONITOR_COVERAGE_CONFIG_NAME,),
    )
