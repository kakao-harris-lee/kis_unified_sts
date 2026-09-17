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

from typing import TYPE_CHECKING

from tos.engine import EventResult
from tos.engine.records import EgressResultPayload, EngineEvent
from tos.engine.state import FinalityProofRef, ProvisionalReservationLedger
from tos.engine.vocabulary import EventKind, ResultDisposition

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.finality import SyntheticFinalityProducer
from tos_runtime.rcl.finality_witness import finality_witness_for

if TYPE_CHECKING:
    # TOS Phase 5 W2-R re-review finding NEW-1 (2026-09-10): a runtime import here forms a
    # cycle -- `release_consumer` imports `tos_runtime.engine.inbox`, which triggers
    # `tos_runtime/engine/__init__.py`, which imports `driver`, which imports THIS module,
    # which would (at runtime) import `release_consumer` right back, mid-initialization. This
    # module only ever uses `FinalityReleaseConsumer` as a type annotation
    # (`project_finality`'s own `release_consumer` parameter) -- both this module and
    # `tos_runtime.posttrade.release_consumer` already carry `from __future__ import
    # annotations`, so the annotation is never evaluated at runtime and this import is safe to
    # defer to type-checking time only. See `engine/driver.py`'s own matching fix (the other
    # half of the SAME cycle) and `tests/posttrade/test_release_consumer.py`'s fresh-subprocess
    # import test, which pins the cycle closed.
    from tos_runtime.posttrade.release_consumer import FinalityReleaseConsumer

__all__ = [
    "ECONOMIC_OBLIGATION_KIND",
    "ENGINE_PROJECTION_RELEASE_SKIPPED_KIND",
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
#: Runtime-local evidence kind (kernel round #3 §2 decision 5 W2-K wiring) appended whenever the
#: kernel's in-memory :class:`~tos.engine.state.ProvisionalReservationLedger` was NOT released
#: this call — either because ``release_consumer.consume`` did not itself commit an RCL release
#: (held, or no release destination for this result kind), or because it did but the kernel's own
#: ``release()`` refused (idempotent repeat, unmatched attempt, or not yet a terminal knowledge
#: state locally). Never a kernel ``EvidenceKind`` member (mirrors this module's own
#: ``ECONOMIC_OBLIGATION_KIND``/``POSTTRADE_FINALITY_PROOF_KIND`` precedent).
ENGINE_PROJECTION_RELEASE_SKIPPED_KIND = "ENGINE_PROJECTION_RELEASE_SKIPPED"


def project_finality(
    event: EngineEvent,
    result: EventResult,
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    finality_producer: SyntheticFinalityProducer,
    release_consumer: FinalityReleaseConsumer | None,
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
    release_consumer: FinalityReleaseConsumer | None,
    ledger: ProvisionalReservationLedger,
) -> None:
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
        return
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
    if not released_locally:
        evidence_store.append(
            {"attempt_id": outcome.attempt_id, "rcl_released": outcome.released},
            kind=ENGINE_PROJECTION_RELEASE_SKIPPED_KIND,
            record_class=ENGINE_PROJECTION_RELEASE_SKIPPED_KIND,
        )
