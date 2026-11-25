"""``RecoveryInputs`` — the boot-time recovery-barrier inputs, assembled from durable sources"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError
from tos.canonical import CanonicalizationScheme
from tos.rcl import CapacityState
from tos.staterestore import IncompleteStoreError, reload_conservative

from tos_runtime.custody.file_custody import MANIFEST_FILENAME, CustodyManifest
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.recon.ports import BrokerWitness
from tos_runtime.recovery.legacy_receipts import (
    LegacyReceiptFacts,
    legacy_receipts_in_window,
)
from tos_runtime.recovery.possibly_live import (
    PossiblyLiveAttempt,
    reconstruct_possibly_live_attempts,
)
from tos_runtime.recovery.reconciliation import (
    FreshnessTimeReader,
    ReconciliationOutcome,
    reconcile_possibly_live_attempts,
    send_handed_off_attempt_id,
)

__all__ = ["OpenReservation", "RecoveryInputs", "assemble_recovery_inputs"]

_CLOSED_RESERVATION_STATES = frozenset({CapacityState.RELEASED})

_REPLAY_VERDICT_IDENTICAL_KIND = "REPLAY_VERDICT_IDENTICAL"
_REPLAY_DIVERGED_KIND = "REPLAY_DIVERGED"


def _replay_verdict_ok(evidence_store: SqliteEvidenceStore) -> bool:
    """Obligation 1 (independent-review finding F5): a durable ``REPLAY_VERDICT_IDENTICAL`` row"""
    (identical_count,) = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?",
        (_REPLAY_VERDICT_IDENTICAL_KIND,),
    ).fetchone()
    if identical_count == 0:
        return False
    (diverged_count,) = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (_REPLAY_DIVERGED_KIND,)
    ).fetchone()
    return bool(diverged_count == 0)


def _inbox_events_parseable(inbox: SqliteEventInbox) -> bool:
    """Obligation 5 (independent-review finding F5, 2026-09-10): every unconsumed inbox row"""
    try:
        for _seq, _event in inbox.replay():
            pass
    except ValidationError:
        return False
    return True


@dataclass(frozen=True)
class OpenReservation:
    """One RCL reservation still holding capacity (not :data:`CapacityState.RELEASED`)."""

    reservation_id: str
    state: CapacityState
    last_seq: int
    scope_account: str
    scope_instrument: str


@dataclass(frozen=True)
class RecoveryInputs:
    """Every durable fact :mod:`tos_runtime.recovery.barrier` folds into a verdict."""

    rcl_writer_epoch: int
    rcl_runtime_generation: int | None
    open_reservations: tuple[OpenReservation, ...]
    evidence_tip_seq: int | None
    evidence_tip_key_generation: int | None
    legacy_receipts: LegacyReceiptFacts
    inbox_unconsumed_count: int
    possibly_live_attempts: tuple[PossiblyLiveAttempt, ...]
    composite_state_incomplete_attempt_ids: tuple[str, ...]
    custody_environment_label: str | None
    custody_manifest_digest: str | None
    possibly_live_reconciliation: dict[str, ReconciliationOutcome] = field(
        default_factory=dict
    )
    replay_verdict_ok: bool = True
    inbox_events_parseable: bool = True


def _open_reservations(rcl_log: SqliteCommitLog) -> tuple[OpenReservation, ...]:
    return tuple(
        OpenReservation(
            reservation_id=reservation_id,
            state=state,
            last_seq=last_seq,
            scope_account=scope.account,
            scope_instrument=scope.instrument,
        )
        for reservation_id, state, last_seq, scope in rcl_log.reservation_rows()
        if state not in _CLOSED_RESERVATION_STATES
    )


def _composite_state_incomplete_ids(
    possibly_live_attempts: tuple[PossiblyLiveAttempt, ...],
    evidence_store: SqliteEvidenceStore,
    composite_state_store_path: Path,
) -> tuple[str, ...]:
    """Which possibly-live attempts (named by their own ``event_id``) have NO cleanly"""
    incomplete: list[str] = []
    for attempt in possibly_live_attempts:
        attempt_id = send_handed_off_attempt_id(evidence_store, attempt.event_id)
        if attempt_id is None:
            incomplete.append(attempt.event_id)
            continue
        try:
            reload_conservative(composite_state_store_path, attempt_id)
        except IncompleteStoreError:
            incomplete.append(attempt.event_id)
    return tuple(incomplete)


def _custody_identity(custody_root: Path) -> tuple[str | None, str | None]:
    manifest_path = custody_root / MANIFEST_FILENAME
    if not manifest_path.is_file():
        return None, None
    raw = manifest_path.read_bytes()
    manifest = CustodyManifest.load(manifest_path)
    return manifest.environment_label, hashlib.sha256(raw).hexdigest()


def assemble_recovery_inputs(
    *,
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    scheme: CanonicalizationScheme,
    window_events: int | None,
    custody_root: Path,
    composite_state_store_path: Path,
    time_service: FreshnessTimeReader,
    account: str,
    instrument: str,
    witness: BrokerWitness | None = None,
) -> RecoveryInputs:
    """Assemble :class:`RecoveryInputs` purely from durable sources (module docstring)."""
    last_seq, _digest, last_key_generation = evidence_store.last_committed()
    environment_label, manifest_digest = _custody_identity(custody_root)
    if not _inbox_events_parseable(inbox):
        return RecoveryInputs(
            rcl_writer_epoch=rcl_log.current_epoch(),
            rcl_runtime_generation=rcl_log.latest_runtime_generation(),
            open_reservations=_open_reservations(rcl_log),
            evidence_tip_seq=last_seq,
            evidence_tip_key_generation=last_key_generation,
            legacy_receipts=LegacyReceiptFacts(count=0, event_ids=()),
            inbox_unconsumed_count=0,
            possibly_live_attempts=(),
            composite_state_incomplete_attempt_ids=(),
            custody_environment_label=environment_label,
            custody_manifest_digest=manifest_digest,
            replay_verdict_ok=_replay_verdict_ok(evidence_store),
            inbox_events_parseable=False,
        )

    possibly_live_attempts = reconstruct_possibly_live_attempts(inbox, scheme=scheme)
    unconsumed_count = sum(
        1 for seq, _event in inbox.replay() if not inbox.is_consumed(seq)
    )
    reconciliation = reconcile_possibly_live_attempts(
        possibly_live_attempts,
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        time_service=time_service,
        account=account,
        instrument=instrument,
        witness=witness,
    )

    return RecoveryInputs(
        rcl_writer_epoch=rcl_log.current_epoch(),
        rcl_runtime_generation=rcl_log.latest_runtime_generation(),
        open_reservations=_open_reservations(rcl_log),
        evidence_tip_seq=last_seq,
        evidence_tip_key_generation=last_key_generation,
        legacy_receipts=legacy_receipts_in_window(
            inbox, evidence_store, scheme=scheme, window_events=window_events
        ),
        inbox_unconsumed_count=unconsumed_count,
        possibly_live_attempts=possibly_live_attempts,
        composite_state_incomplete_attempt_ids=_composite_state_incomplete_ids(
            possibly_live_attempts, evidence_store, composite_state_store_path
        ),
        custody_environment_label=environment_label,
        custody_manifest_digest=manifest_digest,
        possibly_live_reconciliation=reconciliation,
        replay_verdict_ok=_replay_verdict_ok(evidence_store),
        inbox_events_parseable=True,
    )
