"""Phase 3 wave 3 KW3-RD — ``EGRESS_RESULT`` outcome digests (design #31 §7.1 replay identity).

Wave 3 lane F-R's survey finding: ``EventResult.outcome_digest`` was unconditionally ``None`` for
every ``EGRESS_RESULT`` — ``core.py::_handle_egress_result`` never set ``pipeline``, and the
property only ever read through it. That made both the backtest=paper parity comparison and the
runtime replay comparison vacuous for result events: ``None == None`` reports
``tos.evidence.ReplayResultState.INCONCLUSIVE`` ("uncompared"), not a verified match. The design
#31 §5 exit condition ("같은 Capsule/정책/seed replay digest 동일") was therefore only half-measured.

This file proves the fix's required properties over the real ``EngineCore`` +
``ProvisionalReservationLedger`` (never a hand-built composite):

* an ``APPLIED`` result now carries a real digest, not ``None``;
* the same result replayed against the same starting ledger state reproduces the digest
  (RFC-003 §10:345-348 reproducibility);
* a different disposition for the byte-identical payload (``APPLIED`` vs ``DUPLICATE``) changes
  the digest, even though the resulting projection state is otherwise identical;
* a Coordinator-gate refusal — which never reaches the ``EGRESS_RESULT`` handler at all — still
  reports ``None``; the fix only ever *adds* a digest, it never invents one where the core
  genuinely produced no outcome.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

from decimal import Decimal

from tos.engine import (
    EgressResultKind,
    EgressResultOutcome,
    EgressResultPayload,
    EngineEvent,
    EventKind,
    HaltReason,
    ResultDisposition,
    egress_result_outcome_digest,
)

from ._engine_fixtures import (
    SCHEME,
    AllTruePreconditions,
    RecordingTransmit,
    build_core,
    decision_tick,
    instrument_key,
    ordering,
)


def _sent_core():
    """A core that has completed one flow, so a reservation is projected POTENTIALLY_LIVE."""
    core, sink = build_core(transmit=RecordingTransmit())
    result = core.handle(decision_tick(sequence=1))
    assert result.flow is not None and result.flow.attempt is not None
    return core, sink, result.flow.attempt.attempt_id


def _egress_event(
    kind: EgressResultKind, attempt_id: str, *, sequence: int = 2, **fills
):
    """Build an ``EGRESS_RESULT`` event for the projected attempt."""
    return EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=EgressResultPayload(
            instrument_key=instrument_key(),
            attempt_id=attempt_id,
            kind=kind,
            reference=ordering(sequence),
            **fills,
        ),
    )


def test_an_applied_egress_result_has_a_real_outcome_digest() -> None:
    """([KW3-RD]) An APPLIED ACK now carries a real digest, not ``None``."""
    core, _, attempt_id = _sent_core()
    result = core.handle(_egress_event(EgressResultKind.ACK, attempt_id))

    assert result.result_disposition is ResultDisposition.APPLIED
    assert result.pipeline is None
    assert result.outcome_digest is not None
    assert result.outcome_digest == result.result_outcome_digest


def test_the_same_result_against_the_same_ledger_state_reproduces_the_digest() -> None:
    """([KW3-RD]; design #31 §7.1) Two independently wired cores, the same tick and then the same
    ``EGRESS_RESULT`` on each, reproduce the same outcome digest — the reproducibility property a
    replay comparison depends on.
    """
    first_core, _, first_attempt = _sent_core()
    second_core, _, second_attempt = _sent_core()

    first = first_core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            first_attempt,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    second = second_core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            second_attempt,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )

    assert first.outcome_digest is not None
    assert first.outcome_digest == second.outcome_digest


def test_applied_and_duplicate_dispositions_produce_different_digests() -> None:
    """([KW3-RD]) The byte-identical payload applied twice: the first is ``APPLIED``, the second
    is ``DUPLICATE`` — different dispositions must digest differently even though the resulting
    (unchanged, on the second call) projection state is otherwise the same.
    """
    core, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert second.result_disposition is ResultDisposition.DUPLICATE

    assert first.outcome_digest is not None
    assert second.outcome_digest is not None
    assert first.outcome_digest != second.outcome_digest


def test_a_coordinator_gate_refusal_still_reports_no_outcome_digest() -> None:
    """([KW3-RD]) A ``DECISION_TICK`` refused before step 1 never reaches the ``EGRESS_RESULT``
    handler at all — ``result_outcome_digest`` stays unset, and ``outcome_digest`` stays ``None``,
    exactly as before this fix. The fix only ever adds a digest where the core produced a real
    outcome; it invents none where the core genuinely produced nothing.
    """
    core, _ = build_core(
        transmit=RecordingTransmit(),
        preconditions=AllTruePreconditions(authority=False),
    )
    result = core.handle(decision_tick(sequence=1))

    assert result.halt_reason is HaltReason.AUTHORITY_NOT_CURRENT
    assert result.pipeline is None
    assert result.result_outcome_digest is None
    assert result.outcome_digest is None


def test_egress_result_outcome_digest_is_a_pure_function_of_disposition_and_projection() -> (
    None
):
    """([KW3-RD]) The helper is a pure function over exactly its two declared inputs plus the
    scheme — recomputing it from the caller's own already-computed disposition/reservation
    reproduces the exact digest ``core.handle`` recorded, with no hidden state.
    """
    core, _, attempt_id = _sent_core()
    result = core.handle(_egress_event(EgressResultKind.ACK, attempt_id))
    assert result.reservation is not None

    recomputed = egress_result_outcome_digest(
        result.result_disposition, result.reservation, scheme=SCHEME
    )
    assert recomputed == result.result_outcome_digest


def test_orphan_no_reservation_still_yields_a_deterministic_digest() -> None:
    """([KW3-RD]) ``ORPHAN_NO_RESERVATION`` carries no projection at all (``projection=None``),
    yet the digest is still real and deterministic — the same orphaned payload against the same
    (empty) scope redigests to the same value, an absent observation rather than a crash or a
    missing digest.
    """
    core, _ = build_core(transmit=RecordingTransmit())
    result = core.handle(
        _egress_event(EgressResultKind.ACK, "attempt-unknown", sequence=1)
    )

    assert result.result_disposition is ResultDisposition.ORPHAN_NO_RESERVATION
    assert result.reservation is None
    assert result.outcome_digest is not None
    assert result.outcome_digest == egress_result_outcome_digest(
        ResultDisposition.ORPHAN_NO_RESERVATION, None, scheme=SCHEME
    )


def test_egress_result_outcome_covers_the_disposition_field() -> None:
    """([KW3-RD]; mutation guard) Two otherwise-identical outcomes differing only in disposition
    must digest differently — the guard against a future edit that drops ``disposition`` from the
    digest's covered content (:data:`EgressResultOutcome._COVERED_FIELDS`-equivalent: every field
    declared on the model, since it is dumped whole)."""
    applied = EgressResultOutcome(disposition=ResultDisposition.APPLIED)
    duplicate = EgressResultOutcome(disposition=ResultDisposition.DUPLICATE)

    assert SCHEME.compute_digest(
        applied.model_dump(mode="json")
    ) != SCHEME.compute_digest(duplicate.model_dump(mode="json"))
