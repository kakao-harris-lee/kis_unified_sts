"""Possibly-live attempt reconciliation via ``tos_runtime.recon`` (TOS Phase 5 W1; team-lead
follow-up on step 5, 2026-09-10).

**Only a positively-established confidence clears a possibly-live attempt** (plan §2 decision
2). This module never authors that judgement itself: for EACH possibly-live attempt whose
``attempt_id`` can be durably established, it assembles the three
:class:`~tos_runtime.recon.service.ReconciliationService` ports — the already-landed
:class:`~tos_runtime.rcl.projection.SqliteReservationProjectionReader`,
:class:`~tos_runtime.recon.evidence_reader.SqliteEvidenceReceiptReader` (the port
``tos_runtime.recon.ports`` ships as a bare Protocol only), and
:class:`~tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness` — and calls
:meth:`~tos_runtime.recon.service.ReconciliationService.reconcile`. Every result this module
returns has :attr:`ReconciliationOutcome.cleared` ``True`` ONLY when the kernel-backed report
says ``permits_capacity_release`` AND ``permits_rearm`` AND this specific attempt's own
classification is ``MATCHED`` — never a caller-side relaxation of that conjunction.

**``event_id`` -> ``attempt_id``, the missing link.** A :class:`~tos_runtime.recovery
.possibly_live.PossiblyLiveAttempt` is identified by ``event_id`` (the admitted event's own
content-addressed identity); every ``tos_runtime.recon`` port is keyed by ``attempt_id``
instead. The durable link between the two is the ``SEND_HANDED_OFF``
:class:`~tos.engine.records.EngineEvidenceRecord` the sequencer emits (kernel
``tos/src/tos/engine/sequencer.py`` — ``run_commitment_flow``'s ``_send_and_handoff`` step,
verbatim ``EngineEvidenceRecord(kind=EvidenceKind.SEND_HANDED_OFF, attempt_id=attempt
.attempt_id, event_id=event_id, ...)``): it carries BOTH identities on the SAME row, because it
is written at the exact moment a flow instance's attempt is handed off to the send boundary.
:func:`send_handed_off_attempt_id` reads exactly that row. A possibly-live attempt with NO such
row (crash window 1 — marker only, the flow never reached the send boundary at all) has no
broker-side fate to reconcile in the first place; this module reports
:data:`NO_ATTEMPT_ID` for it rather than fabricating one or silently skipping it.

**``attempt_id`` -> ``reservation_id``, the second identity gap.** This compose root's own RCL
reservation ids are per-``(account, instrument)`` SCOPE identifiers
(``f"resv-{account}-{instrument}"`` — ``tos_runtime/compose/_engine_wiring.py``'s
``AtomicCommitStage(reservation_id_provider=...)`` / ``CapacityObligationRecorder``'s own
``reservation_id_resolver``, the SAME convention), never the per-attempt ``attempt_id``
:class:`~tos_runtime.recon.service.ReconciliationService` would otherwise pass straight into
``reservation_state``. Left unbridged, :func:`~tos_runtime.recon.service._classify_attempt`
could never see ``rcl_present=True`` for a genuine attempt id, so
:class:`~tos_runtime.recon.service.ReconciliationClass.MATCHED` — and therefore any capacity
release/re-arm — would be structurally unreachable regardless of how strong the evidence/witness
corroboration is. :class:`~tos_runtime.recon.service.ReconciliationService` now accepts an
injected ``reservation_id_for_attempt`` resolver for exactly this bridge (see its own module
docstring's "``attempt_id`` vs ``reservation_id``" section); this module supplies one that
mirrors ``CapacityObligationRecorder``'s own formula (never a new one invented here), so a
genuinely corroborated attempt (RCL reservation open, evidence-receipt + witness agreeing,
Final Quantity Proof recorded) can now actually clear.

**Freshness, honestly.** :class:`~tos.recon.FreshnessMarker`'s four fields are ``bool | None`` /
``int | None``, fail-closed on any ``None`` (that class's own docstring). This module derives
``time_confidence_held`` from the SAME positive fact
:mod:`tos_runtime.compose` end-to-end tests call ``_reach_trusted`` for
(``TrustworthyTimeService.health_state is HealthState.TRUSTED``), and ``time_generation`` /
``anchored_generation`` from the SAME live snapshot's own
``time_continuity_identity.tts_generation`` (necessarily equal to each other for a marker
anchored at the moment it is built). **Disclosed simplification**: this compose root has no
separate "is this OBSERVATION within its own approved freshness horizon" computation wired
(that is a Verification Profile bound this Phase does not yet inject) — ``fresh_within_horizon``
reuses the same ``TRUSTED`` fact as ``time_confidence_held`` rather than a genuine per-
observation age check. This is conservative, never permissive: an ``UNTRUSTED``/
``DEGRADED_HOLDOVER`` boot still fails every flag closed exactly as the all-``None`` default
would, and a ``TRUSTED`` boot can now ALSO succeed (the "resume path must supply a real marker"
requirement) rather than being structurally unable to ever clear anything.

**Scope-wide permit conservatism (accepted as-is, 2026-09-10 team-lead disposition).**
:func:`_reconcile_one` narrows ``WitnessScope.attempt_ids`` to exactly the ONE attempt under
reconciliation, but that narrowing does not reach into
:meth:`~tos_runtime.recon.evidence_reader.SqliteEvidenceReceiptReader.receipts` or
:meth:`~tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness.observe` — both readers'
own ``_in_scope`` filters only ``scope.account`` / ``scope.instrument_keys`` (their own
docstrings: "never filtered by ``attempt_id``... a receipt for an attempt outside
``scope.attempt_ids`` is the 'receipt-only' classification, not something to drop"), so every
receipt/order for the WHOLE ``(account, instrument)`` — every other attempt, every orphan order
— is still observed and folded into the SAME
:class:`~tos_runtime.recon.service.ReconciliationReport`.
:attr:`~tos_runtime.recon.service.ReconciliationReport.permits_capacity_release` /
:attr:`~tos_runtime.recon.service.ReconciliationReport.permits_rearm` are themselves a
conjunction "over every attempt and orphan order found" in that report (that class's own
docstring) — not narrowed to ``attempt_id``, unlike the ``matched`` check just above it, which
IS filtered to this one ``attempt_id``. The practical consequence: a possibly-live attempt that
is itself genuinely ``MATCHED`` can still see :attr:`ReconciliationOutcome.cleared` ``False``
if ANY other attempt or orphan order sharing its ``(account, instrument)`` fails its own
field-specific gate this same call. This is intentional, not a bug this module works around:
plan §2 decision 2's "복구는 부팅 전 장벽" is exactly "nothing in this scope may resume until
everything in this scope is resolved" — a possibly-live attempt should not clear capacity while
some unrelated position in the SAME instrument is itself unreconciled. Narrowing the permit
flags to ``attempt_id`` (so an unrelated failure could no longer block this attempt) would
change :class:`~tos_runtime.recon.service.ReconciliationService`'s own report contract
(W1-b) — out of scope for this module, and not requested; this module instead documents the
consequence honestly rather than silently relying on undocumented conservatism.

**Fail-closed on any read failure (defence in depth).** :meth:`ReconciliationService.reconcile`
guards its own ``BrokerWitness.observe`` call against
:class:`~tos_runtime.recon.ports.WitnessUnavailable` internally, but does **not** guard its
``EvidenceReceiptReader.receipts`` call the same way — and
:class:`~tos_runtime.recon.evidence_reader.SqliteEvidenceReceiptReader` raises that SAME
exception type on a genuine sqlite read failure. This module wraps BOTH the service's own
construction and each per-attempt ``.reconcile()`` call in a broad ``except Exception`` — a
boot-time barrier must resolve to a definite verdict, never propagate an unhandled exception out
of ``compose_paper_runtime`` — and treats ANY such failure exactly like an unavailable witness:
the affected attempt(s) stay HELD with :data:`RECON_UNAVAILABLE`.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``dataclasses``, ``json``)
+ ``tos.*`` + ``tos_runtime.*`` only. No ``shared.*``. Imports ``tos_runtime.recon.service`` /
``tos_runtime.recon.evidence_reader`` / ``tos_runtime.recon.witness_synthetic`` (read-only
construction, never mutates that package).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from tos.engine.records import InstrumentKey
from tos.recon import FreshnessMarker
from tos.time.domains import HealthState

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.recon.evidence_reader import SqliteEvidenceReceiptReader
from tos_runtime.recon.ports import WitnessScope
from tos_runtime.recon.service import ReconciliationClass, ReconciliationService
from tos_runtime.recon.witness_synthetic import SyntheticLedgerWitness
from tos_runtime.recovery.possibly_live import PossiblyLiveAttempt
from tos_runtime.time.service import TimeServiceNotStarted, TrustworthyTimeService

__all__ = [
    "NO_ATTEMPT_ID",
    "RECONCILED_MATCHED",
    "RECON_UNAVAILABLE",
    "ReconciliationOutcome",
    "reconcile_possibly_live_attempts",
    "send_handed_off_attempt_id",
]

#: The evidence kind carrying the durable event_id<->attempt_id link (module docstring).
_SEND_HANDED_OFF_KIND = "SEND_HANDED_OFF"

#: :attr:`ReconciliationOutcome.reason` when a possibly-live attempt has no durably-linked
#: ``attempt_id`` at all (module docstring's "the missing link").
NO_ATTEMPT_ID = "NO_ATTEMPT_ID"
#: :attr:`ReconciliationOutcome.reason` when reconciliation positively clears the attempt.
RECONCILED_MATCHED = "RECONCILED_MATCHED"
#: :attr:`ReconciliationOutcome.reason` when the service could not be built or a ``.reconcile()``
#: call itself failed (module docstring's fail-closed defence in depth).
RECON_UNAVAILABLE = "RECON_UNAVAILABLE"


@dataclass(frozen=True)
class ReconciliationOutcome:
    """One possibly-live attempt's reconciliation result.

    Attributes:
        cleared: ``True`` only when the kernel-backed report positively establishes this exact
            attempt is ``MATCHED`` across all three paths AND permits both capacity release and
            re-arm (module docstring).
        reason: :data:`RECONCILED_MATCHED` when cleared; :data:`NO_ATTEMPT_ID`,
            :data:`RECON_UNAVAILABLE`, a
            :class:`~tos_runtime.recon.service.ReconciliationReport`-supplied reason, or
            ``"NOT_CORROBORATED"`` otherwise.
    """

    cleared: bool
    reason: str


def send_handed_off_attempt_id(
    evidence_store: SqliteEvidenceStore, event_id: str
) -> str | None:
    """The ``attempt_id`` durably linked to ``event_id`` via a ``SEND_HANDED_OFF`` evidence row
    (module docstring), or ``None`` if the flow never reached the send boundary at all.
    """
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


def _build_freshness_marker(time_service: TrustworthyTimeService) -> FreshnessMarker:
    """A real (never-``None``-by-default) :class:`~tos.recon.FreshnessMarker` derived from this
    runtime's own time service (module docstring's "Freshness, honestly")."""
    try:
        snapshot = time_service.current_snapshot()
    except TimeServiceNotStarted:
        return (
            FreshnessMarker()
        )  # all-None -- fails closed, honestly, never started at all
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
) -> ReconciliationService:
    """Assemble a real :class:`~tos_runtime.recon.service.ReconciliationService`, including the
    ``reservation_id_for_attempt`` bridge (module docstring's "second identity gap") — every
    attempt id maps onto the SAME constant scope reservation id, because this compose root wires
    exactly one ``InstrumentKey`` for its whole process lifetime."""
    return ReconciliationService(
        rcl_reader=SqliteReservationProjectionReader(rcl_log),
        evidence_reader=SqliteEvidenceReceiptReader(evidence_store),
        witness=SyntheticLedgerWitness(evidence_store),
        reservation_id_for_attempt=lambda _attempt_id: f"resv-{account}-{instrument}",
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
    """One possibly-live attempt's own event_id -> attempt_id lookup PLUS reconciliation call,
    both guarded by the SAME broad ``except`` — split out of
    :func:`reconcile_possibly_live_attempts` for readability. Module docstring's "fail-closed on
    any read failure": a durable-store failure surfacing from EITHER
    :func:`send_handed_off_attempt_id` (a raw sqlite read, unguarded on its own) or
    :meth:`~tos_runtime.recon.service.ReconciliationService.reconcile` must resolve to the SAME
    :data:`RECON_UNAVAILABLE` outcome, never propagate out of a boot-time barrier call.
    """
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
    time_service: TrustworthyTimeService,
    account: str,
    instrument: str,
) -> dict[str, ReconciliationOutcome]:
    """Reconcile every possibly-live attempt via :class:`~tos_runtime.recon.service
    .ReconciliationService` (module docstring). ``attempts`` empty => ``{}`` (nothing to
    reconcile is not a failure to reconcile).

    Args:
        attempts: The possibly-live attempts to reconcile (by ``event_id``).
        rcl_log: The already-composed RCL commit log (read-only here).
        evidence_store: The already-composed evidence store (read-only here).
        inbox: The already-composed durable event inbox — accepted for a stable call shape with
            the rest of :mod:`tos_runtime.recovery.inputs`'s own durable-source parameters, not
            read directly today (:func:`send_handed_off_attempt_id` reads ``evidence_store``
            only, since ``SEND_HANDED_OFF`` is an evidence-store record, never an inbox one).
        time_service: This runtime's own :class:`~tos_runtime.time.service.TrustworthyTimeService`
            (for the freshness marker — module docstring).
        account: The single scope account this compose root's ``context_resolver`` is bound to.
        instrument: The single scope instrument this compose root's ``context_resolver`` is
            bound to.

    Returns:
        ``{event_id: ReconciliationOutcome}`` for every attempt in ``attempts``.
    """
    del inbox  # module docstring's Args note -- SEND_HANDED_OFF lives in evidence_store only
    if not attempts:
        return {}

    try:
        service = _build_reconciliation_service(
            rcl_log, evidence_store, account=account, instrument=instrument
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
