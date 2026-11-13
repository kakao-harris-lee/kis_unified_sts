"""Possibly-live attempt reconciliation via ``tos_runtime.recon`` (TOS Phase 5 W1; team-lead"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from tos.engine.records import InstrumentKey
from tos.recon import FreshnessMarker
from tos.time.domains import HealthState

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.rcl.reservation_lookup import reservation_id_for_attempt
from tos_runtime.recon.evidence_reader import SqliteEvidenceReceiptReader
from tos_runtime.recon.ports import BrokerWitness, WitnessScope
from tos_runtime.recon.service import ReconciliationClass, ReconciliationService
from tos_runtime.recon.witness_synthetic import SyntheticLedgerWitness
from tos_runtime.recovery.possibly_live import PossiblyLiveAttempt
from tos_runtime.time.service import TimeServiceNotStarted


class _ContinuityIdentityLike(Protocol):
    """The one :class:`~tos.time.TimeContinuityIdentity` field"""

    @property
    def tts_generation(self) -> int | None: ...


class _FreshnessSnapshotLike(Protocol):
    """The read surface :func:`_build_freshness_marker` needs off whatever"""

    @property
    def health_state(self) -> HealthState: ...
    @property
    def time_continuity_identity(self) -> _ContinuityIdentityLike: ...


class FreshnessTimeReader(Protocol):
    """The narrow read surface :func:`_build_freshness_marker` (and therefore"""

    def current_snapshot(self) -> _FreshnessSnapshotLike:
        """See :meth:`~tos_runtime.time.service.TrustworthyTimeService.current_snapshot`'s own"""
        ...


__all__ = [
    "NO_ATTEMPT_ID",
    "RECONCILED_MATCHED",
    "RECON_UNAVAILABLE",
    "FreshnessTimeReader",
    "ReconciliationOutcome",
    "reconcile_possibly_live_attempts",
    "send_handed_off_attempt_id",
]

_SEND_HANDED_OFF_KIND = "SEND_HANDED_OFF"

NO_ATTEMPT_ID = "NO_ATTEMPT_ID"
RECONCILED_MATCHED = "RECONCILED_MATCHED"
RECON_UNAVAILABLE = "RECON_UNAVAILABLE"


@dataclass(frozen=True)
class ReconciliationOutcome:
    """One possibly-live attempt's reconciliation result."""

    cleared: bool
    reason: str


def send_handed_off_attempt_id(
    evidence_store: SqliteEvidenceStore, event_id: str
) -> str | None:
    """The ``attempt_id`` durably linked to ``event_id`` via a ``SEND_HANDED_OFF`` evidence row"""
    cursor = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
        (_SEND_HANDED_OFF_KIND,),
    )
    for (payload_json,) in cursor.fetchall():
        payload = json.loads(payload_json).get("payload", {})
        if payload.get("event_id") == event_id:
            attempt_id = payload.get("attempt_id")
            return attempt_id if isinstance(attempt_id, str) else None
    return None


def _build_freshness_marker(time_service: FreshnessTimeReader) -> FreshnessMarker:
    """A real (never-``None``-by-default) :class:`~tos.recon.FreshnessMarker` derived from this"""
    try:
        snapshot = time_service.current_snapshot()
    except TimeServiceNotStarted:
        return FreshnessMarker()
    trusted = snapshot.health_state is HealthState.TRUSTED
    generation = snapshot.time_continuity_identity.tts_generation
    return FreshnessMarker(
        fresh_within_horizon=trusted,
        time_confidence_held=trusted,
        time_generation=generation,
        anchored_generation=generation,
    )


def _build_reconciliation_service(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    *,
    account: str,
    instrument: str,
    witness: BrokerWitness | None = None,
) -> ReconciliationService:
    """Assemble a real :class:`~tos_runtime.recon.service.ReconciliationService`, including the"""
    projection = SqliteReservationProjectionReader(rcl_log)
    return ReconciliationService(
        rcl_reader=projection,
        evidence_reader=SqliteEvidenceReceiptReader(evidence_store),
        witness=(
            SyntheticLedgerWitness(evidence_store) if witness is None else witness
        ),
        reservation_id_for_attempt=lambda attempt_id: reservation_id_for_attempt(
            evidence_store,
            projection,
            account=account,
            instrument=instrument,
            attempt_id=attempt_id,
        ),
    )


def _reconcile_one(
    *,
    event_id: str,
    service: ReconciliationService,
    evidence_store: SqliteEvidenceStore,
    account: str,
    instrument_key: InstrumentKey,
    freshness: FreshnessMarker,
) -> ReconciliationOutcome:
    """One possibly-live attempt's own event_id -> attempt_id lookup PLUS reconciliation call,"""
    try:
        attempt_id = send_handed_off_attempt_id(evidence_store, event_id)
        if attempt_id is None:
            return ReconciliationOutcome(cleared=False, reason=NO_ATTEMPT_ID)
        scope = WitnessScope(
            account=account,
            instrument_keys=(instrument_key,),
            attempt_ids=(attempt_id,),
        )
        report = service.reconcile(scope, freshness=freshness)
    except (
        Exception
    ):  # noqa: BLE001 -- module docstring's "fail-closed on any read failure"
        return ReconciliationOutcome(cleared=False, reason=RECON_UNAVAILABLE)
    matched = any(
        classification.attempt_id == attempt_id
        and classification.classification is ReconciliationClass.MATCHED
        for classification in report.classifications
    )
    if matched and report.permits_capacity_release and report.permits_rearm:
        return ReconciliationOutcome(cleared=True, reason=RECONCILED_MATCHED)
    return ReconciliationOutcome(
        cleared=False, reason=report.reason or "NOT_CORROBORATED"
    )


def reconcile_possibly_live_attempts(
    attempts: tuple[PossiblyLiveAttempt, ...],
    *,
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    time_service: FreshnessTimeReader,
    account: str,
    instrument: str,
    witness: BrokerWitness | None = None,
) -> dict[str, ReconciliationOutcome]:
    """Reconcile every possibly-live attempt via :class:`~tos_runtime.recon.service"""
    del inbox
    if not attempts:
        return {}

    try:
        service = _build_reconciliation_service(
            rcl_log,
            evidence_store,
            account=account,
            instrument=instrument,
            witness=witness,
        )
    except (
        Exception
    ):  # noqa: BLE001 -- construction failure is unavailable, fail-closed
        return {
            attempt.event_id: ReconciliationOutcome(
                cleared=False, reason=RECON_UNAVAILABLE
            )
            for attempt in attempts
        }
    freshness = _build_freshness_marker(time_service)
    instrument_key = InstrumentKey(account=account, instrument=instrument)

    return {
        attempt.event_id: _reconcile_one(
            event_id=attempt.event_id,
            service=service,
            evidence_store=evidence_store,
            account=account,
            instrument_key=instrument_key,
            freshness=freshness,
        )
        for attempt in attempts
    }
