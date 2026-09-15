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
* The kernel ``tos.staterestore`` on-disk composite-state substrate, keyed by ``attempt_id``
  (:class:`~tos_runtime.recovery.composite_state_writer.CompositeStateWriter` writes there now —
  see that module's own module docstring for why ``attempt_id``, not a possibly-live attempt's
  own ``event_id``). This module resolves ``event_id`` -> ``attempt_id`` via the SAME durable
  ``SEND_HANDED_OFF`` link :func:`~tos_runtime.recovery.reconciliation.send_handed_off_attempt_id`
  bridges for reconciliation before ever calling :func:`tos.staterestore.reload_conservative`
  (independent-review finding F3, 2026-09-10 — see :func:`_composite_state_incomplete_ids`'s own
  docstring). A possibly-live attempt with no ``SEND_HANDED_OFF`` row at all (the flow never
  reached the send boundary) has no attempt id to reload a composite for, and is reported
  incomplete for exactly that reason, never silently treated as satisfied.
* The D4 custody manifest's own identity — :class:`~tos_runtime.custody.file_custody
  .CustodyManifest` (re-loaded independently, read-only, the same file
  :class:`~tos_runtime.custody.file_custody.FileCustody` already validated at boot).
* Every possibly-live attempt's reconciliation outcome — :mod:`tos_runtime.recovery
  .reconciliation`, run PER-ATTEMPT against a real
  :class:`~tos_runtime.recon.service.ReconciliationService` that module assembles itself (three
  durable ports: the RCL reservation projection, the evidence-receipt reader, and the broker
  witness — see that module's own module docstring for the ``event_id`` -> ``attempt_id`` ->
  ``reservation_id`` identity bridges it closes), plus a freshness marker derived from this
  runtime's own time service. Only a positively-established confidence clears an attempt (plan
  §2 decision 2).

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``hashlib``, ``pathlib``) +
``tos.*`` + ``tos_runtime.*`` only. No ``shared.*``.
"""

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
from tos_runtime.recovery.legacy_receipts import (
    LegacyReceiptFacts,
    legacy_receipts_in_window,
)
from tos_runtime.recovery.possibly_live import (
    PossiblyLiveAttempt,
    reconstruct_possibly_live_attempts,
)
from tos_runtime.recovery.reconciliation import (
    ReconciliationOutcome,
    reconcile_possibly_live_attempts,
    send_handed_off_attempt_id,
)
from tos_runtime.time.service import TrustworthyTimeService

__all__ = ["OpenReservation", "RecoveryInputs", "assemble_recovery_inputs"]

#: Reservation states :func:`tos_runtime.rcl.log.SqliteCommitLog.reservation_rows` may report
#: that are structurally CLOSED (no longer economically open) — only ``RELEASED``
#: (``tos/src/tos/rcl/vocabulary.py``'s ``CapacityState``). Every other member (including
#: ``QUARANTINED_UNKNOWN``/``RELEASE_PENDING_PROOF``) still holds capacity and counts as open.
_CLOSED_RESERVATION_STATES = frozenset({CapacityState.RELEASED})

#: Independent-review finding F5 (2026-09-10): the evidence kind
#: ``tos_runtime.compose._engine_wiring.REPLAY_VERDICT_IDENTICAL_KIND`` records for a genuinely
#: clean replay — replicated here as a citation, not a re-derivation (this module's own
#: established convention for evidence-kind literals shared across packages; avoids a
#: ``tos_runtime.recovery -> tos_runtime.compose`` import edge running backwards against this
#: runtime's own composition-root layering). ``tos_runtime.engine.replay``'s own
#: ``_REPLAY_DIVERGED_KIND`` cited the same way.
_REPLAY_VERDICT_IDENTICAL_KIND = "REPLAY_VERDICT_IDENTICAL"
_REPLAY_DIVERGED_KIND = "REPLAY_DIVERGED"


def _replay_verdict_ok(evidence_store: SqliteEvidenceStore) -> bool:
    """Obligation 1 (independent-review finding F5): a durable ``REPLAY_VERDICT_IDENTICAL`` row
    exists in this evidence store AND no ``REPLAY_DIVERGED`` row exists at all — never a bare
    ``ok=True`` constant. A genesis boot with an empty evidence store (no replay ever ran, no
    ``EVENT_CONSUMED`` baseline to compare against) has neither row and correctly fails this
    check; :func:`RecoveryBarrier.verdict`'s own genesis-consistency obligation (4) is the one
    that recognizes a genuinely empty store as legitimate, not this one.
    """
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
    """Obligation 5 (independent-review finding F5, 2026-09-10): every unconsumed inbox row
    parses through the kernel ``EngineEvent`` model. ``SqliteEventInbox.replay()`` already
    validates via ``EngineEvent.model_validate`` internally — this converts a malformed row's
    ``pydantic.ValidationError`` into a graceful ``False`` (FAILED obligation) instead of an
    unhandled exception escaping :func:`assemble_recovery_inputs`.
    """
    try:
        for _seq, _event in inbox.replay():
            pass
    except ValidationError:
        return False
    return True


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
    #: reconstructable — either no ``SEND_HANDED_OFF`` row exists to resolve an ``attempt_id``
    #: at all, or a resolved ``attempt_id``'s own composite reload came back genuinely
    #: incomplete (:func:`_composite_state_incomplete_ids`; module docstring's ``event_id`` ->
    #: ``attempt_id`` bridge). Empty when :attr:`possibly_live_attempts` is empty (nothing to
    #: restore is not a failure to restore).
    composite_state_incomplete_attempt_ids: tuple[str, ...]
    #: The D4 custody manifest's own ``environment_label`` (``None`` if the manifest file is
    #: absent — should not happen post-boot, since :class:`~tos_runtime.custody.file_custody
    #: .FileCustody` already required it, but this module never assumes that without checking).
    custody_environment_label: str | None
    #: sha256 of the custody manifest file's raw bytes — the manifest's own content identity.
    custody_manifest_digest: str | None
    #: ``{event_id: ReconciliationOutcome}`` for every entry in :attr:`possibly_live_attempts`
    #: (:mod:`tos_runtime.recovery.reconciliation`). Defaults to empty for hand-constructed test
    #: inputs that never called reconciliation — :mod:`tos_runtime.recovery.barrier` treats a
    #: missing entry as unreconciled (fail-closed), never as vacuously cleared.
    possibly_live_reconciliation: dict[str, ReconciliationOutcome] = field(
        default_factory=dict
    )
    #: Obligation 1 (independent-review finding F5, 2026-09-10): whether a durable
    #: ``REPLAY_VERDICT_IDENTICAL`` row exists in the evidence store AND no ``REPLAY_DIVERGED``
    #: row exists at all (:func:`_replay_verdict_ok`) — never a bare ``True`` constant. Defaults
    #: to ``True`` here ONLY for hand-constructed test inputs isolating a different obligation
    #: (mirrors :attr:`possibly_live_reconciliation`'s own default-for-tests convention);
    #: :func:`assemble_recovery_inputs` always computes the real value.
    replay_verdict_ok: bool = True
    #: Obligation 5 (independent-review finding F5, 2026-09-10): whether every unconsumed inbox
    #: row parses through the kernel ``EngineEvent`` model (:func:`_inbox_events_parseable`) —
    #: ``SqliteEventInbox.replay()`` already validates internally, so a malformed row would
    #: otherwise raise an unhandled exception out of a boot-time barrier call instead of a
    #: graceful FAILED obligation. Defaults to ``True`` here ONLY for hand-constructed test
    #: inputs (mirrors :attr:`replay_verdict_ok`'s own convention).
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
    """Which possibly-live attempts (named by their own ``event_id``) have NO cleanly
    reconstructable ``tos.staterestore`` composite (obligation 6).

    Independent-review finding F3 (2026-09-10): the staterestore write is keyed by
    ``attempt_id`` (:mod:`tos_runtime.recovery.composite_state_writer`'s own module docstring),
    never by a possibly-live attempt's own ``event_id`` — so this read side must resolve
    ``event_id`` -> ``attempt_id`` via the SAME durable ``SEND_HANDED_OFF`` link
    :func:`~tos_runtime.recovery.reconciliation.send_handed_off_attempt_id` already bridges for
    reconciliation, before ever calling :func:`tos.staterestore.reload_conservative`. A possibly-
    live attempt with no such row at all (crash window 1 — marker only, the flow never reached
    the send boundary) has no attempt id to reload a composite for in the first place, so it is
    ALSO reported incomplete here, never silently treated as satisfied.
    """
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
    time_service: TrustworthyTimeService,
    account: str,
    instrument: str,
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
        composite_state_store_path: Where the ``tos.staterestore`` composite-state store for
            this data directory lives — :class:`~tos_runtime.recovery.composite_state_writer
            .CompositeStateWriter` writes here (keyed by ``attempt_id``, independent-review
            finding F3), and :func:`_composite_state_incomplete_ids` reloads from it after
            resolving each possibly-live attempt's ``event_id`` onto that SAME ``attempt_id``.
        time_service: This runtime's own :class:`~tos_runtime.time.service
            .TrustworthyTimeService` (forwarded to :mod:`tos_runtime.recovery.reconciliation`
            for the freshness marker).
        account: The single scope account this compose root's ``context_resolver`` is bound to
            (forwarded to reconciliation).
        instrument: The single scope instrument this compose root's ``context_resolver`` is
            bound to (forwarded to reconciliation).

    Returns:
        The fully assembled :class:`RecoveryInputs`.
    """
    last_seq, _digest, last_key_generation = evidence_store.last_committed()
    environment_label, manifest_digest = _custody_identity(custody_root)
    if not _inbox_events_parseable(inbox):
        # Obligation 5 (independent-review finding F5): a malformed row makes
        # SqliteEventInbox.replay() itself raise a kernel EngineEvent ValidationError --
        # every OTHER inbox-derived computation below would raise too, so this returns a
        # conservative, fully-populated RecoveryInputs with inbox_events_parseable=False
        # (obligation 5 FAILED) rather than letting the exception escape the boot-time
        # barrier ungracefully.
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
