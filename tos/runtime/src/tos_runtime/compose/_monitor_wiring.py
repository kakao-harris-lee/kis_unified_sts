"""``tos_runtime.compose._monitor_wiring`` — the slim monitor and the item-16 latch owner."""

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

MONITOR_CONFIG_FILE_NAMES: tuple[str, ...] = (_MONITOR_COVERAGE_CONFIG_NAME,)

_STM_ALERT_KIND = "STM_ALERT"

_NS_PER_MS = 1_000_000


@dataclass
class _InboxCell:
    """The late-bound cell the latch owner's inbox reader and the monitor's"""

    inbox: SqliteEventInbox | None = None


class _LateBoundInboxReader:
    """Satisfies :class:`~tos_runtime.safety.latch.NewRiskHaltReader` over an"""

    def __init__(self, cell: _InboxCell) -> None:
        self._cell = cell

    def new_risk_halt(self) -> Mapping[str, object] | None:
        """The currently-latched row, or ``None`` (no latch / cell not yet filled)."""
        if self._cell.inbox is None:
            return None
        return self._cell.inbox.new_risk_halt()


def _inbox_unconsumed_observer_for(cell: _InboxCell) -> Callable[[], int]:
    """The ``inbox_unconsumed_observer`` port the monitor needs. Returns ``0`` before the"""

    def _observer() -> int:
        inbox = cell.inbox
        if inbox is None:
            return 0
        return inbox.unconsumed_count

    return _observer


def _stm_alert_recorder_for(evidence_store: SqliteEvidenceStore) -> AlertRecorder:
    """The ``evidence_recorder`` port the monitor needs, over this composition's real"""

    def _recorder(kind: str, fields: Mapping[str, Any]) -> None:
        evidence_store.append(dict(fields), kind=kind, record_class=_STM_ALERT_KIND)

    return _recorder


def _evidence_tip_observer_excluding_own_alerts(
    evidence_store: SqliteEvidenceStore,
) -> Callable[[], tuple[int | None, str, int | None]]:
    """The ``evidence_tip_observer`` port the monitor needs."""
    excluded = frozenset({_STM_ALERT_KIND})

    def _observer() -> tuple[int | None, str, int | None]:
        return evidence_store.last_committed_excluding(excluded)

    return _observer


@dataclass
class _MonitorOwners:
    """Everything :func:`build_monitor_owners` assembles — handed to"""

    monitoring: MonitoringService
    dimension_readers: dict[
        DimensionKey, tuple[str, Callable[[], DimensionReport | None]]
    ]
    latch: RestrictiveLatchOwner
    inbox_cell: _InboxCell
    config_files: tuple[Path, ...] = field(default_factory=tuple)


def build_capacity_owner(
    projection: ReservationProjectionReader, scope: InstrumentKey
) -> CapacityOwner:
    """Build the item-16 ``worst_credible_capacity`` owner — a thin, stateless wrapper (no"""
    return CapacityOwner(projection, scope)


def build_monitor_owners(
    config_dir: Path,
    *,
    evidence_store: SqliteEvidenceStore,
    monotonic_source: MonotonicSource,
) -> _MonitorOwners:
    """Construct the slim monitor and the item-16 latch owner — the ONE call"""
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
