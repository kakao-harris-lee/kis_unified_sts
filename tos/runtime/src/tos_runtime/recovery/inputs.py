"""``RecoveryInputs`` — the boot-time recovery-barrier inputs, assembled from durable sources
ONLY (TOS Phase 5 W1; plan §2 decision 2: "전부 구조 파생, 운영자 «정상» 선언 입력 0").

:func:`assemble_recovery_inputs` has no operator/attestation/override parameter anywhere — every
field is read straight off a durable store this runtime already owns:

* RCL log tip/generation/open reservations — :class:`~tos_runtime.rcl.log.SqliteCommitLog`.
* Evidence tip + the already-recorded replay-window facts —
  :class:`~tos_runtime.evidence.store.SqliteEvidenceStore` (:mod:`tos_runtime.recovery
  .legacy_receipts`).
* The durable inbox's unconsumed count and possibly-live attempt set —
  :class:`~tos_runtime.engine.inbox.SqliteEventInbox` (:mod:`tos_runtime.recovery
  .possibly_live`).
* The kernel ``tos.staterestore`` on-disk composite-state substrate, keyed by each possibly-live
  attempt's own event id (there is no other durable identity to key a restart-time composite
  reload on at this boot-time layer). **Disclosed limitation**: nothing in this runtime shell
  writes to that store yet (measured directly: zero ``tos.staterestore`` references anywhere
  under ``tos_runtime`` before this module) — :func:`tos.staterestore.reload_conservative` is
  called for real, but for every attempt it re-derives from an EMPTY store, so it deterministically
  raises :class:`~tos.staterestore.IncompleteStoreError` (no durable Intent marker) today. That
  is treated as the fail-closed "composite state not restorable" fact, not swallowed — it is
  exactly the conservative reading design #39 argues for an absent store, and it means every
  possibly-live attempt is ALSO flagged incomplete here until a future wave wires the driver's own
  write path into this store (out of this lane's owned files — see this module's own
  ``composite_state_incomplete_attempt_ids`` field docstring).
* The D4 custody manifest's own identity — :class:`~tos_runtime.custody.file_custody
  .CustodyManifest` (re-loaded independently, read-only, the same file
  :class:`~tos_runtime.custody.file_custody.FileCustody` already validated at boot).

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``hashlib``, ``pathlib``) +
``tos.*`` + ``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from tos.canonical import CanonicalizationScheme
from tos.rcl import CapacityState
from tos.staterestore import IncompleteStoreError, reload_conservative

from tos_runtime.custody.file_custody import MANIFEST_FILENAME, CustodyManifest
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.recovery.legacy_receipts import (
    LegacyReceiptFacts,
    legacy_receipts_in_window,
)
from tos_runtime.recovery.possibly_live import (
    PossiblyLiveAttempt,
    reconstruct_possibly_live_attempts,
)

__all__ = ["OpenReservation", "RecoveryInputs", "assemble_recovery_inputs"]

#: Reservation states :func:`tos_runtime.rcl.log.SqliteCommitLog.reservation_rows` may report
#: that are structurally CLOSED (no longer economically open) — only ``RELEASED``
#: (``tos/src/tos/rcl/vocabulary.py``'s ``CapacityState``). Every other member (including
#: ``QUARANTINED_UNKNOWN``/``RELEASE_PENDING_PROOF``) still holds capacity and counts as open.
_CLOSED_RESERVATION_STATES = frozenset({CapacityState.RELEASED})


@dataclass(frozen=True)
class OpenReservation:
    """One RCL reservation still holding capacity (not :data:`CapacityState.RELEASED`).

    Attributes:
        reservation_id: The reservation's own id.
        state: Its current :class:`~tos.rcl.CapacityState`.
        last_seq: The RCL log ``seq`` of its most recent transition.
        scope_account: The reservation's scope account.
        scope_instrument: The reservation's scope instrument.
    """

    reservation_id: str
    state: CapacityState
    last_seq: int
    scope_account: str
    scope_instrument: str


@dataclass(frozen=True)
class RecoveryInputs:
    """Every durable fact :mod:`tos_runtime.recovery.barrier` folds into a verdict.

    See the module docstring for exactly which durable store backs each field. No field is ever
    populated from an operator attestation, an environment variable, or a caller-supplied
    override — the whole point of this dataclass (plan §2 decision 2's "전부 구조 파생").
    """

    #: :meth:`~tos_runtime.rcl.log.SqliteCommitLog.current_epoch` — the RCL log's own Writer
    #: Epoch, acquired fresh on THIS boot (never equated with ``rcl_runtime_generation`` — design
    #: #40 v1.1 note ②, "두 epoch 를 증명 없이 결합하지 않는다").
    rcl_writer_epoch: int
    #: :meth:`~tos_runtime.rcl.log.SqliteCommitLog.latest_runtime_generation` — the D4 workload
    #: generation recorded on the most recent ``epochs`` row, or ``None`` if this process never
    #: recorded one (a fresh/first boot).
    rcl_runtime_generation: int | None
    #: Every RCL reservation not yet :data:`~tos.rcl.CapacityState.RELEASED`.
    open_reservations: tuple[OpenReservation, ...]
    #: :meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.last_committed`'s own ``last_seq``
    #: — ``None`` for a genuinely empty evidence store.
    evidence_tip_seq: int | None
    #: The signing-key generation of that same tip entry (``None`` alongside ``evidence_tip_seq``
    #: for an empty store).
    evidence_tip_key_generation: int | None
    #: The ⓑ legacy-receipt facts for the current replay window (:mod:`tos_runtime.recovery
    #: .legacy_receipts`).
    legacy_receipts: LegacyReceiptFacts
    #: How many inbox rows are admitted but not yet consumed (possibly-live attempts included —
    #: this is the BROADER count; use :attr:`possibly_live_attempts` for the narrower crash-window
    #: subset).
    inbox_unconsumed_count: int
    #: The ⓗ possibly-live attempt set (:mod:`tos_runtime.recovery.possibly_live`).
    possibly_live_attempts: tuple[PossiblyLiveAttempt, ...]
    #: Possibly-live attempts whose ``tos.staterestore`` composite reload was NOT cleanly
    #: reconstructable (today: every one of them — see module docstring's disclosed limitation).
    #: Empty when :attr:`possibly_live_attempts` is empty (nothing to restore is not a failure to
    #: restore).
    composite_state_incomplete_attempt_ids: tuple[str, ...]
    #: The D4 custody manifest's own ``environment_label`` (``None`` if the manifest file is
    #: absent — should not happen post-boot, since :class:`~tos_runtime.custody.file_custody
    #: .FileCustody` already required it, but this module never assumes that without checking).
    custody_environment_label: str | None
    #: sha256 of the custody manifest file's raw bytes — the manifest's own content identity.
    custody_manifest_digest: str | None


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
    composite_state_store_path: Path,
) -> tuple[str, ...]:
    incomplete: list[str] = []
    for attempt in possibly_live_attempts:
        try:
            reload_conservative(composite_state_store_path, attempt.event_id)
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
) -> RecoveryInputs:
    """Assemble :class:`RecoveryInputs` purely from durable sources (module docstring).

    Args:
        rcl_log: The already-composed RCL commit log (read-only here).
        evidence_store: The already-composed evidence store (read-only here).
        inbox: The already-composed durable event inbox (read-only here).
        scheme: The canonicalization scheme this runtime composed with.
        window_events: The SAME ``engine_driver.yaml`` ``replay_window_events`` bound the boot-
            time replay check already used.
        custody_root: The D4 custody directory (for the manifest identity read).
        composite_state_store_path: Where a ``tos.staterestore`` composite-state store for this
            data directory would live (module docstring's disclosed limitation: nothing writes
            here yet, so every reload is conservatively incomplete).

    Returns:
        The fully assembled :class:`RecoveryInputs`.
    """
    possibly_live_attempts = reconstruct_possibly_live_attempts(inbox, scheme=scheme)
    last_seq, _digest, last_key_generation = evidence_store.last_committed()
    unconsumed_count = sum(
        1 for seq, _event in inbox.replay() if not inbox.is_consumed(seq)
    )
    environment_label, manifest_digest = _custody_identity(custody_root)

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
            possibly_live_attempts, composite_state_store_path
        ),
        custody_environment_label=environment_label,
        custody_manifest_digest=manifest_digest,
    )
