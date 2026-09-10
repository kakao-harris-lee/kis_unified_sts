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

from tos.engine import EventResult
from tos.engine.records import EngineEvent
from tos.engine.vocabulary import EventKind, ResultDisposition

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.finality import SyntheticFinalityProducer
from tos_runtime.posttrade.release_consumer import FinalityReleaseConsumer
from tos_runtime.rcl.finality_witness import finality_witness_for

__all__ = [
    "ECONOMIC_OBLIGATION_KIND",
    "POSTTRADE_FINALITY_PROOF_KIND",
    "project_finality",
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


def project_finality(
    event: EngineEvent,
    result: EventResult,
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    finality_producer: SyntheticFinalityProducer,
    release_consumer: FinalityReleaseConsumer | None,
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

    **The release-trigger call site (TOS Phase 5 W2-R).** ``release_consumer.consume(payload)``
    is called for EVERY genuinely-applied ``EGRESS_RESULT`` (not only a ``FULL_FILL`` — the
    consumer itself decides, per its own module docstring, which kinds have a release
    destination at all) — after the witness row and any ``FULL_FILL`` proof/obligation evidence
    this function itself just wrote are durable, so the consumer's own re-load of those rows
    always observes THIS call's own writes, never a stale prior state.

    Args:
        event: The event the driver just handled.
        result: That event's own :class:`~tos.engine.EventResult`.
        inbox: The durable event inbox — the ``attempt_finality_witness`` side table lives here.
        evidence_store: The durable evidence store this function appends to.
        finality_producer: Produces the SYNTHETIC ``FULL_FILL`` proof.
        release_consumer: The TOS Phase 5 W2-R release consumer, or ``None`` to degrade to the
            pre-W2-R behaviour (module docstring).
    """
    if event.kind is not EventKind.EGRESS_RESULT:
        return
    if result.result_disposition is not ResultDisposition.APPLIED:
        return
    payload = event.egress_result
    assert payload is not None  # guaranteed by EngineEvent validation for EGRESS_RESULT

    produced = finality_producer.produce(payload)
    witness = finality_witness_for(None if produced is None else produced.proof)
    inbox.record_finality_witness(payload.attempt_id, witness)
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

    if release_consumer is not None:
        release_consumer.consume(payload)
