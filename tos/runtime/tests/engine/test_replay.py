"""Hermetic tests for :func:`tos_runtime.engine.replay.replay_engine` (TOS Phase 3 Wave 1
Lane A-R; plan §1.1 "재생 digest 동일").

Most scenarios here use ``transmit=None`` for BOTH the original run and the replay's
``build_core`` factory — the fully side-effect-free scope :mod:`tos_runtime.engine.replay`'s own
module docstring documents (see "Side-effect scope, reported precisely"). A scenario that drives
a REAL hand-off live (CR5, 2026-09-09 — kernel lane KW3-RD gave ``EGRESS_RESULT`` events a real
``outcome_digest``, exposing a replay-fidelity gap at the send boundary) uses
:class:`~tos_runtime.engine.replay_transmit.RecordedTransmit` for the REPLAY side instead of a
bare ``None`` — still fully side-effect-free (no transport, no new attempt — see that class's own
module docstring), reproducing the live run's own recorded ``SEND_HANDED_OFF`` evidence rather
than a real send.
"""

from __future__ import annotations

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.orthostate_projection import (
    NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
)
from tos_runtime.engine.replay import replay_engine
from tos_runtime.engine.replay_transmit import (
    RecordedTransmit,
    ReplayTransmitEvidenceMissing,
    any_recorded_hand_off,
)
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.sinks import EngineEvidenceSinkAdapter
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.nontrade.latch import latch_restrictive

from . import _fixtures as fx
from .conftest import FakeMonotonicSource

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: Independent review finding #14: ``max_send_result_wait_ms`` is a concrete positive int now,
#: never ``None`` — a caller that wants "timeout injection never fires within this test" passes a
#: bound far larger than anything the test advances its ``FakeMonotonicSource`` by.
_NO_TIMEOUT_WITHIN_TEST = 10**12


def _driver(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> EngineDriver:
    driver = EngineDriver(
        core=fx.build_core(transmit=None),
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="replay-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    # This suite's CORPORATE_ACTION replay scenarios (added kernel round #3 K-4) reach a
    # restrictive disposition by default (fx.corporate_action_event's honestly-empty payload) —
    # TOS runtime operations wiring plan §2 decision 3 made an un-bound latch on a restrictive
    # result a loud EngineDriverInvariantError rather than a silent skip, so every driver this
    # suite builds needs the real shared latch bound, exactly like a real compose root.
    driver.bind_nontrade_latch(latch_restrictive)
    return driver


def test_identical_replay_matches_for_every_event(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    driver = _driver(inbox, evidence_store, emergency_log)
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    driver.enqueue_and_run(fx.decision_tick_event(seq=3))

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.total_compared == 3
    assert verdict.diverged == ()


def test_window_events_limits_the_replay_to_the_most_recent_n(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """A windowed replay is only sound when the events outside the window carry no ledger state
    into the ones inside it — here every tick is a defined no-action (never proposes, never
    touches the reservation ledger), so each event's outcome is independent of the others and a
    1-event window genuinely matches (see :func:`tos_runtime.engine.replay.replay_engine`'s own
    module docstring for the path-dependency caveat this test is deliberately avoiding).
    """
    registry = fx.registry_with(fx.never_fires_policy())
    driver = EngineDriver(
        core=fx.build_core(registry=registry, transmit=None),
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="replay-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    driver.enqueue_and_run(fx.decision_tick_event(seq=3))

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(registry=registry, transmit=None),
        scheme=SCHEME,
        window_events=1,
    )
    assert verdict.ok
    assert verdict.total_compared == 1


def test_zero_or_negative_window_is_rejected(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    with pytest.raises(ValueError, match="positive int or None"):
        replay_engine(
            inbox,
            evidence_store,
            emergency_log,
            lambda: fx.build_core(transmit=None),
            scheme=SCHEME,
            window_events=0,
        )


def test_mutated_recorded_outcome_digest_is_detected_as_a_divergence(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Mutation test (plan §1.1 "재생 비교 제거 red" companion): tamper with the recorded
    ``outcome_digest`` a real ``EVENT_CONSUMED`` receipt carries — replay must catch it, not
    silently agree."""
    driver = _driver(inbox, evidence_store, emergency_log)
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))

    # Test-only tamper of the durably recorded digest (never how production code writes evidence
    # — evidence.sqlite3's entries table is append/no-update by trigger; this bypasses that
    # trigger deliberately, as a test double for "the recorded baseline was corrupted").
    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        "REPLACE(payload_json, '\"outcome_digest\":', '\"outcome_digest_untouched\":') "
        "WHERE kind = 'EVENT_CONSUMED'"
    )

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),
        scheme=SCHEME,
        window_events=None,
    )
    assert not verdict.ok
    assert len(verdict.diverged) == 1

    halts = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'REPLAY_DIVERGED'"
    ).fetchone()[0]
    assert halts == 1


def test_mutated_recorded_egress_result_outcome_digest_is_detected_as_a_divergence(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5 (2026-09-09), companion to the DECISION_TICK mutation test above, extended to an
    ``EGRESS_RESULT`` receipt now that kernel lane KW3-RD (``783fadf0``) gives it a real,
    non-``None`` ``outcome_digest``. Tamper with the recorded digest on the ``EVENT_CONSUMED``
    receipt for the re-injected result event specifically (not the ``DECISION_TICK``) — replay,
    using :class:`RecordedTransmit` to correctly reproduce the live hand-off, must still catch
    the tamper rather than silently agreeing (or, worse, silently treating it as ``uncompared``
    the way an unfixed replay would have before ``RecordedTransmit`` existed)."""
    gateway = fx.FakeGateway()
    driver = EngineDriver(
        core=fx.build_core(
            transmit=gateway, sink=EngineEvidenceSinkAdapter(evidence_store)
        ),
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="replay-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    driver.bind_gateway(gateway)
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True
    assert inbox.count == 2  # the tick + the re-injected ACK result
    assert any_recorded_hand_off(evidence_store)

    # Tamper ONLY the SECOND EVENT_CONSUMED receipt (the EGRESS_RESULT's own outcome_digest) —
    # the DECISION_TICK's own receipt is left untouched.
    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        "REPLACE(payload_json, '\"outcome_digest\":', '\"outcome_digest_untouched\":') "
        "WHERE kind = 'EVENT_CONSUMED' AND seq = "
        "(SELECT MAX(seq) FROM entries WHERE kind = 'EVENT_CONSUMED')"
    )

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=RecordedTransmit(evidence_store)),
        scheme=SCHEME,
        window_events=None,
    )
    assert not verdict.ok
    assert len(verdict.diverged) == 1

    halts = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'REPLAY_DIVERGED'"
    ).fetchone()[0]
    assert halts == 1


def test_replay_never_calls_the_live_runs_transport(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5 (2026-09-09) — behavioral companion to
    ``test_no_transport_during_replay.py``'s structural (AST-import) pin: the SAME transport
    instance the live run handed a real attempt to must receive ZERO further calls once replay
    runs, no matter how many events replay compares. :class:`RecordedTransmit` (the transmit
    replay installs instead) reproduces the LOCAL ledger effect purely by reading durable
    ``SEND_HANDED_OFF`` evidence back out of the SAME evidence store — it never holds, wraps, or
    forwards to the live run's own transport object.
    """
    gateway = fx.FakeGateway()
    driver = EngineDriver(
        core=fx.build_core(
            transmit=gateway, sink=EngineEvidenceSinkAdapter(evidence_store)
        ),
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="replay-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    driver.bind_gateway(gateway)
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True
    assert len(gateway.attempts) == 1  # the live send actually happened

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=RecordedTransmit(evidence_store)),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert (
        len(gateway.attempts) == 1
    )  # unchanged — replay never touched the live transport


def test_events_outside_the_recorded_baseline_are_skipped_not_diverged(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """An admitted-but-not-yet-consumed row (no ``EVENT_CONSUMED`` receipt to compare against)
    must not be reported as a divergence — there is nothing to diverge FROM."""
    inbox.enqueue(fx.decision_tick_event(seq=1))  # enqueued directly, never processed

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.total_compared == 0


def test_recorded_transmit_refuses_to_guess_a_hand_off_the_evidence_does_not_corroborate(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """CR5 (2026-09-09) unit test for the fail-closed guard the dispatch's own disposition
    requires: "If the evidence for an attempt is missing/ambiguous, the stand-in must NOT
    guess — return the refusal path and let the divergence surface." An evidence store with no
    ``SEND_HANDED_OFF`` row for a given ``attempt_id`` (e.g. an evidence-loss edge case, or an
    attempt this store never actually processed) must raise
    :class:`ReplayTransmitEvidenceMissing`, never silently fabricate a
    :class:`~tos.engine.records.SendHandoff`.
    """
    from tos.engine.records import AttemptRequest

    stand_in = RecordedTransmit(evidence_store)
    attempt = AttemptRequest(
        attempt_id="attempt-never-recorded",
        conformance_proof_digest="digest-proof",
        action_flow_permit_identity="permit-identity",
        reference_coordinate_digest="digest-reference",
    )
    with pytest.raises(ReplayTransmitEvidenceMissing):
        stand_in(attempt)


def test_egress_result_outcome_digest_is_compared_and_matches(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5 (2026-09-09), RED before the fix — renamed from ``test_egress_result_none_outcome_
    digest_is_uncompared_not_diverged`` (independent review finding #1, 2026-09-09), whose own
    premise kernel lane KW3-RD (``783fadf0``) retired: ``EventResult.outcome_digest`` is no
    longer honestly ``None`` for an ``EGRESS_RESULT`` event — it is now a real digest derived
    from the applied disposition/capacity/knowledge/quantities (``tos.engine.records
    .EgressResultOutcome``). The old assumption ("both sides are None, so there is nothing to
    compare") is retired; the new one is "both sides must be REAL and EQUAL".

    Root cause this fix addresses (K-W2b, confirmed against the real driver): replay used to
    compose its core with ``transmit=None``. ``tos.engine.sequencer.run_commitment_flow`` treats
    an absent transmit as an unconditional ``TRANSMIT_UNAVAILABLE`` stop, reached BEFORE
    ``ledger.mark_potentially_live`` ever runs — so replay's reservation projection stayed
    ``ATTEMPT_BOUND`` while the LIVE run (a real hand-off) had already advanced it to
    ``POTENTIALLY_LIVE``. Replaying the identical ``EGRESS_RESULT`` against the two different
    prior projections computed two different ``EgressResultOutcome`` digests for the same event.
    :class:`~tos_runtime.engine.replay_transmit.RecordedTransmit` fixes this: it reproduces the
    live run's own recorded ``SEND_HANDED_OFF`` evidence for the exact attempt being replayed,
    letting ``mark_potentially_live`` run during replay exactly as it did live.
    """
    gateway = fx.FakeGateway()
    driver = EngineDriver(
        core=fx.build_core(
            transmit=gateway, sink=EngineEvidenceSinkAdapter(evidence_store)
        ),
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="replay-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    driver.bind_gateway(gateway)
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True
    assert inbox.count == 2  # the tick + the re-injected ACK result
    assert any_recorded_hand_off(evidence_store)

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=RecordedTransmit(evidence_store)),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.diverged == ()
    # Both the DECISION_TICK and the EGRESS_RESULT now carry a real, comparable digest.
    assert verdict.total_compared == 2
    assert verdict.uncompared == 0


def test_installing_the_standin_when_the_live_run_never_had_a_send_boundary_diverges(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """CR5 (2026-09-09) — the negative the dispatch asked for ("the stand-in returning the wrong
    local effect"), constructed from a measured fact rather than assumed.

    **Measured (see :mod:`tos_runtime.engine.replay_transmit`'s own module docstring): making
    :class:`RecordedTransmit` RAISE for a specific attempt, instead of returning a
    ``SendHandoff``, does NOT by itself change the reservation's ledger state** —
    ``tos.engine.sequencer.run_commitment_flow`` calls ``ledger.mark_potentially_live`` BEFORE
    the ``try``/``except`` around ``transmit(attempt)``, so a raise and a return are
    ledger-equivalent (a direct probe against the real driver confirms both leave the identical
    ``POTENTIALLY_LIVE``/``SENT_UNCONFIRMED`` reservation). A per-attempt "wrong return value"
    mutation of the stand-in therefore CANNOT be observed as a digest divergence via this
    mechanism — so this test exercises the genuinely observable failure mode instead: installing
    :class:`RecordedTransmit` (or ANY non-``None`` transmit) for a replay window whose LIVE run
    never had a send boundary configured at all. ``mark_potentially_live`` requires only that
    ``transmit is not None`` — merely installing a stand-in, regardless of what it later does,
    wrongly advances the reservation to ``POTENTIALLY_LIVE`` when the live run's own
    ``TRANSMIT_UNAVAILABLE`` halt never did. This is exactly why
    :func:`~tos_runtime.engine.replay_transmit.any_recorded_hand_off` exists: a caller MUST use
    it to decide between ``RecordedTransmit`` and ``transmit=None`` — it must never install the
    stand-in unconditionally.
    """
    from tos.engine.records import EgressResultPayload, EngineEvent
    from tos.engine.vocabulary import EgressResultKind, EventKind

    driver = EngineDriver(
        core=fx.build_core(
            transmit=None, sink=EngineEvidenceSinkAdapter(evidence_store)
        ),
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="replay-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.halt_reason is not None
    assert tick_result.halt_reason.value == "TRANSMIT_UNAVAILABLE"
    assert tick_result.reservation is not None
    attempt_id = tick_result.reservation.attempt_id
    assert attempt_id is not None
    assert not any_recorded_hand_off(evidence_store)  # genuinely never handed off

    # A late, out-of-band result for the SAME attempt (kernel's own APPLIED/duplicate rules do
    # not require a hand-off to have happened — see ADR-002-002 §15.2 "absence is not proof").
    # ``ACK`` (not a fill kind) is deliberately chosen: its capacity target in
    # ``tos.engine.state._RESULT_TRANSITIONS`` is ``None`` — "leave capacity where it is" — which
    # is exactly why it is starting-state-SENSITIVE (unlike ``FULL_FILL``'s fixed
    # ``POSITION_CONSUMED`` target, which converges to the identical digest regardless of
    # starting capacity and was measured NOT to diverge here). Replaying this ``ACK`` against a
    # wrongly-``POTENTIALLY_LIVE``-advanced ledger (this test's misuse) leaves capacity at
    # ``POTENTIALLY_LIVE``; the live run's own correctly-``ATTEMPT_BOUND`` ledger leaves capacity
    # at ``ATTEMPT_BOUND`` — two different final capacity states, therefore two different
    # ``EgressResultOutcome`` digests for the byte-identical event.
    late_result = EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=EgressResultPayload(
            instrument_key=fx.instrument_key(),
            attempt_id=attempt_id,
            kind=EgressResultKind.ACK,
        ),
    )
    result_event = driver.enqueue_and_run(late_result)
    assert result_event.result_disposition is not None

    # MISUSE: install RecordedTransmit unconditionally, ignoring any_recorded_hand_off's own
    # run-wide gate — exactly the mistake a caller must not make.
    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=RecordedTransmit(evidence_store)),
        scheme=SCHEME,
        window_events=None,
    )
    assert not verdict.ok
    assert len(verdict.diverged) >= 1


class _AlwaysRefusedPreconditions:
    """A ``False``/``False`` ``CoordinatorPreconditions`` double — every ``DECISION_TICK`` this
    core ever sees is refused before step 1 (``HaltReason.AUTHORITY_NOT_CURRENT``)."""

    def authority_epoch_current(self) -> bool | None:
        return False

    def live_scope_authorized(self, _transport_nature: object) -> bool | None:
        return False


def test_coordinator_gate_refusal_receipt_is_uncompared_not_diverged(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Independent review finding #1, wave 2 (2026-09-09), RED before the fix.

    A DIFFERENT half of finding #1 from the EGRESS_RESULT case above: here the LIVE run's own
    ``EVENT_CONSUMED`` receipt carries a genuine Coordinator-gate refusal
    (``HaltReason.AUTHORITY_NOT_CURRENT``), not an honest EGRESS_RESULT ``None``. The driver here
    is built with ``_AlwaysRefusedPreconditions`` (refused live), but ``replay_engine``'s
    ``build_core`` factory below uses the DEFAULT ``_AlwaysPermissivePreconditions`` (mirroring
    ``_ReplayPreconditions``'s own unconditional True/True design in the real compose wiring) —
    so, before the fix, replay would run the FULL pipeline for this refused tick and manufacture
    a real digest, an asymmetric None-recorded/non-None-replayed pair the old comparison logic
    reported as a divergence.
    """
    driver = EngineDriver(
        core=fx.build_core(transmit=None, preconditions=_AlwaysRefusedPreconditions()),
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="replay-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.halt_reason is not None
    assert tick_result.halt_reason.value == "AUTHORITY_NOT_CURRENT"
    assert tick_result.outcome_digest is None

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),  # default: _AlwaysPermissivePreconditions
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.diverged == ()
    assert verdict.total_compared == 0
    assert verdict.uncompared == 1
    assert len(verdict.uncompared_halt_reasons) == 1
    event_id, halt_reason = verdict.uncompared_halt_reasons[0]
    assert halt_reason == "AUTHORITY_NOT_CURRENT"


def test_new_risk_halt_latch_receipt_is_uncompared_not_diverged(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Re-review finding R1 (2026-09-09), RED before the fix.

    The independent-review finding #3 new-risk latch's own reason
    (``NEW_RISK_HALTED_BY_COUPLING_VIOLATION``) is a RUNTIME halt reason, not a kernel
    ``HaltReason`` member — it was absent from the closed pre-pipeline set, so a
    latch-refused ``DECISION_TICK``'s receipt (``outcome_digest=None``, ``core.handle`` never
    called) reached the normal comparison. Replay has no knowledge of the runtime-level latch, so
    it ran the FULL pipeline for the tick and manufactured a real digest — the exact
    ``None``-recorded / non-``None``-replayed asymmetry finding #1 was fixed to eliminate,
    reopened verbatim by the latch reason's own absence from the closed set.
    """
    driver = EngineDriver(
        core=fx.build_core(transmit=None),
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="replay-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    inbox.record_new_risk_halt(
        reason=NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
        event_id="attempt:test-r1",
        evidence_seq=None,
    )
    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.pipeline is None
    assert tick_result.outcome_digest is None

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.diverged == ()
    assert verdict.total_compared == 0
    assert verdict.uncompared == 1
    assert len(verdict.uncompared_halt_reasons) == 1
    event_id, halt_reason = verdict.uncompared_halt_reasons[0]
    assert halt_reason == NEW_RISK_HALTED_BY_COUPLING_VIOLATION


# ===========================================================================
# CORPORATE_ACTION replay comparison (kernel round #3 §2 결정 3)
# ===========================================================================


def test_corporate_action_replay_matches(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """A CORPORATE_ACTION event replays identically: same outcome_digest, same
    nontrade_disposition — never uncompared, never diverged."""
    driver = _driver(inbox, evidence_store, emergency_log)
    driver.enqueue_and_run(fx.corporate_action_event(seq=1))

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.ok
    assert verdict.total_compared == 1
    assert verdict.diverged == ()


def test_mutated_recorded_nontrade_disposition_is_detected_as_a_divergence(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Mutation guard (kernel round #3 §2 결정 3): tamper ONLY the recorded
    ``nontrade_disposition`` string (the ``outcome_digest`` stays byte-identical) — replay must
    still catch it as a divergence, proving the disposition is compared as its own independent
    signal, not folded silently into the digest comparison alone."""
    driver = _driver(inbox, evidence_store, emergency_log)
    driver.enqueue_and_run(fx.corporate_action_event(seq=1))

    evidence_store.connection.execute("DROP TRIGGER IF EXISTS entries_no_update")
    evidence_store.connection.execute(
        "UPDATE entries SET payload_json = "
        'REPLACE(payload_json, \'"nontrade_disposition":"NONTRADE_TRAPPED"\', '
        '\'"nontrade_disposition":"NONTRADE_BLOCK_NEW_RISK"\') '
        "WHERE kind = 'EVENT_CONSUMED'"
    )

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: fx.build_core(transmit=None),
        scheme=SCHEME,
        window_events=None,
    )
    assert not verdict.ok
    assert len(verdict.diverged) == 1

    halts = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'REPLAY_DIVERGED'"
    ).fetchone()[0]
    assert halts == 1
