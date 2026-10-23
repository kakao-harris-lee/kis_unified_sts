"""``project_finality`` — the driver's post-trade finality-projection hook (TOS Phase 5 W2-R;
plan §10 row ②).

**A pure move, plus one new call.** This module's body is
:class:`~tos_runtime.engine.driver.EngineDriver`'s own ``_project_finality`` method, moved here
verbatim to recover the driver's own module-size headroom (``config/tos_size_budget.yaml``) —
same behaviour, same evidence kinds, same placement in the driver's own event loop
(:meth:`~tos_runtime.engine.driver.EngineDriver._process_next` calls it unconditionally, right
after that event's own ``EVENT_CONSUMED`` receipt is durable, mirroring
:meth:`~tos_runtime.engine.driver.EngineDriver._track_timeouts`'s own placement — see that
method's own module docstring for the full "team-lead CR-4, plan §2.2" history this move
inherits unchanged). The ONE addition (team-lead dispatch, plan §10 row ②): after the durable
witness row + (for a ``FULL_FILL``) the proof/obligation evidence are committed, this function
calls :meth:`~tos_runtime.posttrade.release_consumer.FinalityReleaseConsumer.consume` — the W2-R
release consumer :mod:`tos_runtime.posttrade.release_consumer`'s own module docstring names as
the ONE production call site that ever reaches a ``RELEASED``/``POSITION_CONSUMED`` RCL
destination.

``release_consumer`` is ``| None`` by design (mirrors
:class:`~tos_runtime.engine.driver.EngineDriver`'s own ``recovery_composite_writer`` optional
pattern): a driver constructed without one — every existing test-suite driver construction that
predates this wave, and any future driver that genuinely wants no release path — degrades to
exactly the pre-W2-R behaviour (proof + witness recorded, never consumed), never a silent
behaviour change for a caller that has not opted in.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.engine`` +
``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tos.engine import EventResult
from tos.engine.records import EgressResultPayload, EngineEvent
from tos.engine.state import FinalityProofRef, ProvisionalReservationLedger
from tos.engine.vocabulary import EgressResultKind, EventKind, ResultDisposition

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.finality import (
    FinalityProducerPort,
    ReleaseFinalityProducer,
)
from tos_runtime.rcl.finality_witness import finality_witness_for

if TYPE_CHECKING:
    # TOS Phase 5 W2-R re-review finding NEW-1 (2026-09-10): a runtime import here forms a
    # cycle -- `release_consumer` imports `tos_runtime.engine.inbox`, which triggers
    # `tos_runtime/engine/__init__.py`, which imports `driver`, which imports THIS module,
    # which would (at runtime) import `release_consumer` right back, mid-initialization. This
    # module only ever uses `FinalityConsumerPort` as a type annotation
    # (`project_finality`'s own `release_consumer` parameter) -- both this module and
    # `tos_runtime.posttrade.release_consumer` already carry `from __future__ import
    # annotations`, so the annotation is never evaluated at runtime and this import is safe to
    # defer to type-checking time only. See `engine/driver.py`'s own matching fix (the other
    # half of the SAME cycle) and `tests/posttrade/test_release_consumer.py`'s fresh-subprocess
    # import test, which pins the cycle closed. (mypy stage 3 §1.3 rule 3: narrowed from the
    # concrete `FinalityReleaseConsumer` to the `FinalityConsumerPort` it actually calls
    # `.consume()` through — a test double no longer needs to BE a `FinalityReleaseConsumer`.)
    from tos_runtime.posttrade.release_consumer import FinalityConsumerPort

__all__ = [
    "ECONOMIC_OBLIGATION_KIND",
    "ENGINE_PROJECTION_RELEASED_KIND",
    "ENGINE_PROJECTION_RELEASE_SKIPPED_KIND",
    "FINALITY_REPROJECTED_KIND",
    "POSTTRADE_FINALITY_PROOF_KIND",
    "project_finality",
    "project_recovered_finality",
]

#: Evidence kinds this hook appends when :class:`~tos_runtime.posttrade.finality
#: .SyntheticFinalityProducer` produces a proof for a genuinely-``APPLIED`` ``EGRESS_RESULT``
#: (team-lead CR-4 dispatch, plan §2.2). Not kernel ``EvidenceKind`` members — this is
#: runtime-level evidence about a SYNTHETIC-transport artifact the kernel's own posttrade
#: package never emits itself (``tos_runtime.posttrade.finality``'s own module docstring). The
#: SAME literals :mod:`tos_runtime.posttrade.release_consumer` reuses for its own non-execution
#: proof path — single source of truth for the kind strings lives here.
ECONOMIC_OBLIGATION_KIND = "ECONOMIC_OBLIGATION"
POSTTRADE_FINALITY_PROOF_KIND = "POSTTRADE_FINALITY_PROOF"
#: Runtime-local evidence kind (kernel round #3 §2 decision 5 W2-K wiring) appended whenever the
#: kernel's in-memory :class:`~tos.engine.state.ProvisionalReservationLedger` was NOT released
#: this call — either because ``release_consumer.consume`` did not itself commit an RCL release
#: (held, or no release destination for this result kind), or because it did but the kernel's own
#: ``release()`` refused (idempotent repeat, unmatched attempt, or not yet a terminal knowledge
#: state locally). Never a kernel ``EvidenceKind`` member (mirrors this module's own
#: ``ECONOMIC_OBLIGATION_KIND``/``POSTTRADE_FINALITY_PROOF_KIND`` precedent).
ENGINE_PROJECTION_RELEASE_SKIPPED_KIND = "ENGINE_PROJECTION_RELEASE_SKIPPED"
#: Recorded when the kernel projection DID release (PR-3b r2 claim 2) — the durable fact the boot
#: replay re-applies, at the same point in the event order, so replay equals live.
ENGINE_PROJECTION_RELEASED_KIND = "ENGINE_PROJECTION_RELEASED"
#: Recorded by :func:`project_recovered_finality` (PR-3b) for every pass it makes, with why.
FINALITY_REPROJECTED_KIND = "FINALITY_REPROJECTED"
#: The kinds :func:`project_recovered_finality` ever hands the release consumer.
_RECOVERABLE_KINDS = frozenset(
    {
        EgressResultKind.FULL_FILL,
        EgressResultKind.CANCEL_ACK,
        EgressResultKind.EXPIRED,
        EgressResultKind.REJECT,
    }
)


def project_finality(
    event: EngineEvent,
    result: EventResult,
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    finality_producer: FinalityProducerPort,
    release_consumer: FinalityConsumerPort | None,
    ledger: ProvisionalReservationLedger,
) -> None:
    """For a genuinely-applied ``FULL_FILL``, produce a SYNTHETIC post-trade finality proof, then
    (TOS Phase 5 W2-R) hand the payload to ``release_consumer``.

    Called unconditionally, right after every freshly-handled event's own ``EVENT_CONSUMED``
    receipt is durable (never on a crash-window recovery path, which never calls
    ``core.handle`` at all and so has no fresh ``EventResult`` to project) — exactly the same
    placement as :meth:`~tos_runtime.engine.driver.EngineDriver._track_timeouts`, which this
    mirrors. The ``FULL_FILL``-only finality-proof gate below is this function's own (mirroring
    ``_track_timeouts``'s own APPLIED-only gate for the SAME reason: a non-``APPLIED`` result's
    ``EgressResultPayload`` still carries an attempt id and a ``FULL_FILL`` kind by construction,
    but was never actually accepted onto THIS attempt's reservation — producing a proof from it
    would assert finality for a fill the kernel itself refused).

    The durable ``attempt_finality_witness`` row is written for every genuinely-applied
    ``EGRESS_RESULT`` (not only a ``FULL_FILL``) so a later, non-proof-bearing result for the
    same attempt (e.g. a ``TIMEOUT``) does not leave a stale prior witness readable —
    :func:`~tos_runtime.rcl.finality_witness.finality_witness_for` itself always returns the
    correct value (``True`` only for THIS producer call's own proof, ``None`` otherwise), so
    writing it unconditionally on every applied result can only ever record the CURRENT truth,
    never a stale one.

    **The release-trigger call site (TOS Phase 5 W2-R; kernel round #3 §2 decision 5 W2-K).**
    Delegated to :func:`_project_release` (size-budget discipline) — see that function's own
    docstring for the full ``release_consumer.consume`` / kernel ``ledger.release`` chain.

    Args:
        event: The event the driver just handled.
        result: That event's own :class:`~tos.engine.EventResult`.
        inbox: The durable event inbox — the ``attempt_finality_witness`` side table lives here.
        evidence_store: The durable evidence store this function appends to.
        finality_producer: Produces the SYNTHETIC ``FULL_FILL`` proof.
        release_consumer: The TOS Phase 5 W2-R release consumer, or ``None`` to degrade to the
            pre-W2-R behaviour (module docstring).
        ledger: The SAME :class:`~tos.engine.state.ProvisionalReservationLedger`
            :attr:`~tos.engine.core.EngineCore.ledger` the driver's own core owns — never a
            second, independently-constructed ledger.
    """
    if event.kind is not EventKind.EGRESS_RESULT:
        return
    if result.result_disposition is not ResultDisposition.APPLIED:
        return
    payload = event.egress_result
    assert payload is not None  # guaranteed by EngineEvent validation for EGRESS_RESULT

    _record_fill_proof(
        payload,
        inbox=inbox,
        evidence_store=evidence_store,
        finality_producer=finality_producer,
    )
    _project_release(
        payload,
        evidence_store=evidence_store,
        release_consumer=release_consumer,
        ledger=ledger,
    )


def _project_release(
    payload: EgressResultPayload,
    *,
    evidence_store: SqliteEvidenceStore,
    release_consumer: FinalityConsumerPort | None,
    ledger: ProvisionalReservationLedger,
) -> bool:
    """The release-trigger call site (TOS Phase 5 W2-R; kernel round #3 §2 decision 5 W2-K),
    factored out of :func:`project_finality` (size-budget discipline).

    ``release_consumer.consume(payload)`` is called for EVERY genuinely-applied ``EGRESS_RESULT``
    (not only a ``FULL_FILL`` — the consumer itself decides, per its own module docstring, which
    kinds have a release destination at all) — after the witness row and any ``FULL_FILL``
    proof/obligation evidence :func:`project_finality` itself just wrote are durable, so the
    consumer's own re-load of those rows always observes THAT call's own writes, never a stale
    prior state.

    Only AFTER ``release_consumer.consume`` reports a committed RCL release
    (:class:`~tos_runtime.posttrade.release_consumer.ReleaseOutcome.released` is ``True``, with
    every one of ``proof_digest``/``evidence_seq``/``resolution_generation`` present) does this
    function build a kernel :class:`~tos.engine.state.FinalityProofRef` — using the
    ``CAPACITY_RELEASE_INTENT`` evidence row's own ``seq`` and the witness generation the
    consumer's own gate 4 validated the proof against — and call ``ledger.release(ref)``. Any
    other outcome (the consumer held, or the kernel's own ``release()`` itself refused) is
    recorded as :data:`ENGINE_PROJECTION_RELEASE_SKIPPED_KIND` evidence, never silently dropped
    and never raised — this module's own "never a crash" discipline, matching the kernel ledger's
    own "conservative recorded outcome" one. ``release_consumer is None`` (module docstring's
    pre-W2-R degrade path) records nothing at all — there was no consumer to have attempted
    anything with, never a behaviour change for a caller that has not opted in.

    Args:
        payload: The genuinely-applied ``EGRESS_RESULT`` payload.
        evidence_store: Where :data:`ENGINE_PROJECTION_RELEASE_SKIPPED_KIND` is appended.
        release_consumer: The TOS Phase 5 W2-R release consumer, or ``None`` to degrade to the
            pre-W2-R no-op (module docstring).
        ledger: The engine core's own :class:`~tos.engine.state.ProvisionalReservationLedger`.
    """
    if release_consumer is None:
        return False
    outcome = release_consumer.consume(payload)
    released_locally = False
    if (
        outcome.released
        and outcome.proof_digest is not None
        and outcome.evidence_seq is not None
        and outcome.resolution_generation is not None
    ):
        ref = FinalityProofRef(
            attempt_id=outcome.attempt_id,
            proof_digest=outcome.proof_digest,
            evidence_seq=outcome.evidence_seq,
            resolution_generation=outcome.resolution_generation,
        )
        released_locally = ledger.release(ref)
        if released_locally:
            # PR-3b r2 claim 2: the boot replay re-applies this exact release at this exact point
            # (engine/replay.py) so the replayed projection equals the live one.
            evidence_store.append(
                {
                    "attempt_id": ref.attempt_id,
                    "proof_digest": ref.proof_digest,
                    "evidence_seq": ref.evidence_seq,
                    "resolution_generation": ref.resolution_generation,
                },
                kind=ENGINE_PROJECTION_RELEASED_KIND,
                record_class=ENGINE_PROJECTION_RELEASED_KIND,
            )
    if not released_locally:
        evidence_store.append(
            {"attempt_id": outcome.attempt_id, "rcl_released": outcome.released},
            kind=ENGINE_PROJECTION_RELEASE_SKIPPED_KIND,
            record_class=ENGINE_PROJECTION_RELEASE_SKIPPED_KIND,
        )
    return outcome.released


def _record_fill_proof(
    payload: EgressResultPayload,
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    finality_producer: FinalityProducerPort,
) -> None:
    """The durable witness row, plus the obligation/proof evidence when the producer issued one
    (shared by :func:`project_finality` and :func:`project_recovered_finality`)."""
    produced = finality_producer.produce(payload)
    if produced is not None:
        evidence_store.append(
            produced.record.model_dump(mode="json"),
            kind=ECONOMIC_OBLIGATION_KIND,
            record_class=ECONOMIC_OBLIGATION_KIND,
        )
        evidence_store.append(
            produced.proof.model_dump(mode="json"),
            kind=POSTTRADE_FINALITY_PROOF_KIND,
            record_class=POSTTRADE_FINALITY_PROOF_KIND,
        )
    # Witness LAST (PR-3b r2 claim 1): a "True" witness row only ever follows a durable proof, so
    # an interruption between the writes leaves "no witness", never "witness without proof".
    witness = finality_witness_for(None if produced is None else produced.proof)
    inbox.record_finality_witness(payload.attempt_id, witness)


def project_recovered_finality(
    payload: EgressResultPayload,
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    finality_producer: ReleaseFinalityProducer,
    release_consumer: FinalityConsumerPort,
    ledger: ProvisionalReservationLedger,
    reason: str,
) -> bool | None:
    """Re-run finality for a terminal result the engine recorded whose release has not committed
    (PR-3b review HIGH 1): the process died after the engine consumed the result but before
    :func:`project_finality` ran, or reconciliation / the RCL CAS held the release last time. The
    fill observer calls this from its retry loop. The engine is never re-fed the result: finality
    is projected from the already-recorded one, so the inbox — and every later boot's replay —
    is untouched.

    * The ``FULL_FILL`` proof is written only if this attempt has no finality witness yet, so a
      retry never mints a second proof row.
    * Release goes through :func:`_project_release` — the release consumer's every gate
      (witness, re-loaded proof, reconciliation against the boot's broker witness, the RCL's own
      state/CAS check) and, when the RCL commits, the kernel projection's own ``release`` too
      (a no-op, recorded as skipped, when the engine holds no such reservation).

    **No double release.** A reservation already ``POSITION_CONSUMED``/``RELEASED`` is refused by
    the RCL; the observer stops retrying once the release command is committed.

    Args:
        reason: Why this pass runs (today always ``release_not_committed``) — recorded.

    Returns:
        Whether the RCL transition committed, or ``None`` when ``payload.kind`` has no release
        destination (``ACK``/``PARTIAL_FILL``/``UNKNOWN``/``TIMEOUT``) and nothing was done.
    """
    if payload.kind not in _RECOVERABLE_KINDS:
        return None
    if payload.kind is EgressResultKind.FULL_FILL:
        # r2 claim 1: decide by the proof ROWS, not the witness flag — an interrupted write can
        # leave either one without the other. Rows present: only the witness may be missing.
        if _fill_proof_durable(evidence_store, finality_producer, payload.attempt_id):
            if inbox.finality_witness(payload.attempt_id) is not True:
                inbox.record_finality_witness(payload.attempt_id, True)
        else:
            _record_fill_proof(
                payload,
                inbox=inbox,
                evidence_store=evidence_store,
                finality_producer=finality_producer,
            )
    released = _project_release(
        payload,
        evidence_store=evidence_store,
        release_consumer=release_consumer,
        ledger=ledger,
    )
    evidence_store.append(
        {
            "attempt_id": payload.attempt_id,
            "egress_result_kind": payload.kind.value,
            "broker_execution_id": payload.broker_execution_id,
            "reason": reason,
            "rcl_released": released,
        },
        kind=FINALITY_REPROJECTED_KIND,
        record_class=FINALITY_REPROJECTED_KIND,
    )
    return released


def _fill_proof_durable(
    evidence_store: SqliteEvidenceStore,
    producer: ReleaseFinalityProducer,
    attempt_id: str,
) -> bool:
    """Both the obligation and the proof row of ``attempt_id``'s fill are durable (the release
    consumer re-loads exactly these two by these idempotency keys)."""
    wanted = {
        ECONOMIC_OBLIGATION_KIND: f"{producer.full_fill_obligation_prefix}:{attempt_id}",
        POSTTRADE_FINALITY_PROOF_KIND: f"{producer.full_fill_proof_prefix}:{attempt_id}",
    }
    for kind, key in wanted.items():
        rows = evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?", (kind,)
        ).fetchall()
        if not any(
            json.loads(row[0]).get("payload", {}).get("idempotency_key") == key
            for row in rows
        ):
            return False
    return True
