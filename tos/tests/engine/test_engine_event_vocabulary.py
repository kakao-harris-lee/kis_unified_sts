"""§7.2-7 — the event vocabulary is closed and an unknown kind is a fail-closed error (§2.2).

The design's target: *"미지 event kind → fail-closed 오류(silent drop 아님)"*. Silently dropping an
unrecognised event is the archetypal wiring fail-open: the system keeps running while a whole class
of event disappears.

This module also covers the vocabulary's two neighbours:

* **partial fills stay partial** (design #31 §2.2 MINOR-3; RFC-005 §11:338-339, §6:176-178). The
  fill/partial distinction is derived from the magnitudes, so a producer cannot label a partial as
  a full fill, and the already-filled quantity is never re-requested;
* **causal order** (§2.1(ii)). A positively-established reversal is refused; an *ambiguous* pair is
  recorded and admitted, because "cannot order" is not "proven backwards" — over-rejecting it would
  be the #26 WDR MAJOR-1 defect, and the risk it might carry is separately sealed by the
  at-most-one retention and the positive attempt-identity match.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError
from tos.engine import (
    ADMISSIBLE_EVENT_KINDS,
    EgressResultKind,
    EgressResultPayload,
    EngineEvent,
    EventKind,
    HaltReason,
    OrderingAdmission,
    UnknownEventKindError,
    admit_kind,
    ordering_admission,
)
from tos.ordering import OrderingEvent

from ._engine_fixtures import (
    RecordingTransmit,
    build_core,
    corporate_action_event,
    decision_tick,
    instrument_key,
    issue_capsule,
    ordering,
)


class _BogusEvent:
    """An object shaped like an event but carrying a kind outside the closed vocabulary.

    ``"CORPORATE_ACTION"`` is now a REAL :class:`EventKind` member's value (kernel round #3 §2
    결정 1) — but this bare **string** is still not admitted, because :func:`admit_kind` checks
    positive membership of the exact enum object, never string equality (the SAME distinction
    :func:`test_a_string_that_merely_matches_a_member_value_is_not_admitted` locks for
    ``"DECISION_TICK"``, now parametrized here too). Admitting this string would require the
    caller to have actually constructed ``EventKind.CORPORATE_ACTION``, not merely a lookalike
    string — this fixture proves that boundary still holds even once the member is real.
    """

    kind = "CORPORATE_ACTION"


def test_the_vocabulary_is_exactly_the_three_declared_kinds() -> None:
    """(§2.2; kernel round #3 §2 결정 1) The closed set and the enum agree — no member is
    admissible-but-unlisted. This test used to pin exactly two kinds; that pin is now false —
    round #3 added ``CORPORATE_ACTION`` as the enum-addition-only extension design #31 §2.2
    itself anticipated (the dispatcher interface did not change: :func:`admit_kind` and the
    handler signature are exactly as before)."""
    assert frozenset(EventKind) == ADMISSIBLE_EVENT_KINDS
    assert sorted(k.value for k in ADMISSIBLE_EVENT_KINDS) == [
        "CORPORATE_ACTION",
        "DECISION_TICK",
        "EGRESS_RESULT",
    ]


@pytest.mark.parametrize(
    "bogus",
    ["CORPORATE_ACTION", "CANCEL", "", None, 0, object(), _BogusEvent()],
)
def test_an_unknown_kind_is_a_fail_closed_error(bogus) -> None:
    """(§7.2-7) Anything outside the closed vocabulary raises — it is never dropped silently.

    ``"CORPORATE_ACTION"`` stays in this list even though it is now a real member's *value*
    (kernel round #3 §2 결정 1) — see :class:`_BogusEvent`'s own docstring for why the bare
    string is still refused."""
    with pytest.raises(UnknownEventKindError):
        admit_kind(bogus)


@pytest.mark.parametrize(
    "value", ["DECISION_TICK", "EGRESS_RESULT", "CORPORATE_ACTION"]
)
def test_a_string_that_merely_matches_a_member_value_is_not_admitted(value) -> None:
    """(§2.2) Admission is positive **membership**, not string equality — no coercion path.

    Parametrized over all three real member values (kernel round #3 §2 결정 1 added the third) —
    a bare string identical to any of them is still refused."""
    with pytest.raises(UnknownEventKindError):
        admit_kind(value)


def test_the_core_refuses_an_event_whose_kind_is_outside_the_vocabulary() -> None:
    """(§7.2-7) The dispatcher itself raises rather than returning a benign "nothing happened"."""
    core, _ = build_core(transmit=RecordingTransmit())
    with pytest.raises(UnknownEventKindError):
        core.handle(_BogusEvent())  # type: ignore[arg-type]


def test_every_admissible_kind_is_actually_handled() -> None:
    """(§2.2; kernel round #3 §2 결정 1) Every vocabulary member has a handler — an unhandled
    member is not a no-op. This test used to name only two kinds; round #3's third
    (``CORPORATE_ACTION``) reaches its own handler too, never an ``UnknownEventKindError``.
    """
    core, _ = build_core(transmit=RecordingTransmit())
    for kind in ADMISSIBLE_EVENT_KINDS:
        assert admit_kind(kind) is kind
    assert core.handle(decision_tick(sequence=1)).kind is EventKind.DECISION_TICK
    ca_result = core.handle(corporate_action_event(sequence=2))
    assert ca_result.kind is EventKind.CORPORATE_ACTION
    assert ca_result.nontrade_outcome is not None


def test_an_event_payload_must_match_its_kind() -> None:
    """(§2.2; kernel round #3 §2 결정 1) The closed-vocabulary discipline reaches the payload
    shape too — now over all three kinds, not two."""
    with pytest.raises(ValidationError, match="requires a decision_tick payload"):
        EngineEvent(kind=EventKind.DECISION_TICK)
    with pytest.raises(ValidationError, match="requires a egress_result payload"):
        EngineEvent(kind=EventKind.EGRESS_RESULT)
    with pytest.raises(ValidationError, match="requires a corporate_action payload"):
        EngineEvent(kind=EventKind.CORPORATE_ACTION)


def test_an_event_may_not_carry_the_other_kinds_payload() -> None:
    """(§2.2; kernel round #3 §2 결정 1) Two payloads on one event is an ambiguous event —
    unconstructable. Covers all three O(n²) same-event pairings the three-kind vocabulary now
    admits, not just the original two-kind pair."""
    tick = decision_tick(sequence=1)
    ca = corporate_action_event(sequence=1)
    with pytest.raises(ValidationError, match="must not carry"):
        EngineEvent(
            kind=EventKind.DECISION_TICK,
            decision_tick=tick.decision_tick,
            egress_result=EgressResultPayload(
                instrument_key=instrument_key(),
                attempt_id="a",
                kind=EgressResultKind.ACK,
            ),
        )
    with pytest.raises(ValidationError, match="must not carry"):
        EngineEvent(
            kind=EventKind.DECISION_TICK,
            decision_tick=tick.decision_tick,
            corporate_action=ca.corporate_action,
        )
    with pytest.raises(ValidationError, match="must not carry"):
        EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=instrument_key(),
                attempt_id="a",
                kind=EgressResultKind.ACK,
            ),
            corporate_action=ca.corporate_action,
        )


# ---------------------------------------------------------------------------
# partial fills stay partial (§2.2 MINOR-3)
# ---------------------------------------------------------------------------


def test_a_partial_fill_carries_both_magnitudes() -> None:
    """(RFC-005 §11:338-339) A partial is represented as a partial, with filled + remaining."""
    payload = EgressResultPayload(
        instrument_key=instrument_key(),
        attempt_id="attempt-1",
        kind=EgressResultKind.PARTIAL_FILL,
        filled_quantity=Decimal("3"),
        remaining_quantity=Decimal("7"),
    )
    assert payload.filled_quantity == Decimal("3")
    assert payload.remaining_quantity == Decimal("7")


def test_a_partial_may_not_be_relabelled_as_a_full_fill() -> None:
    """(구조 파생 > 자기신고) The magnitudes decide, not the declared kind."""
    with pytest.raises(ValidationError, match="contradicts the magnitudes"):
        EgressResultPayload(
            instrument_key=instrument_key(),
            attempt_id="attempt-1",
            kind=EgressResultKind.FULL_FILL,
            filled_quantity=Decimal("3"),
            remaining_quantity=Decimal("7"),
        )


def test_a_full_fill_may_not_be_relabelled_as_a_partial() -> None:
    """(구조 파생 > 자기신고) The check is symmetric — a zero remainder is not a partial."""
    with pytest.raises(ValidationError, match="contradicts the magnitudes"):
        EgressResultPayload(
            instrument_key=instrument_key(),
            attempt_id="attempt-1",
            kind=EgressResultKind.PARTIAL_FILL,
            filled_quantity=Decimal("3"),
            remaining_quantity=Decimal("0"),
        )


@pytest.mark.parametrize(
    "kind",
    [
        EgressResultKind.ACK,
        EgressResultKind.REJECT,
        EgressResultKind.UNKNOWN,
        EgressResultKind.TIMEOUT,
    ],
)
def test_a_non_fill_result_may_not_carry_fill_magnitudes(kind) -> None:
    """(§2.2) Only the two fill kinds carry magnitudes — an acknowledged fill is unconstructable."""
    with pytest.raises(ValidationError, match="must carry no fill magnitude"):
        EgressResultPayload(
            instrument_key=instrument_key(),
            attempt_id="attempt-1",
            kind=kind,
            filled_quantity=Decimal("1"),
        )


def test_a_fill_without_magnitudes_is_unconstructable() -> None:
    """(§2.2) An unquantified fill is not a fill."""
    with pytest.raises(ValidationError, match="requires both"):
        EgressResultPayload(
            instrument_key=instrument_key(),
            attempt_id="attempt-1",
            kind=EgressResultKind.FULL_FILL,
        )


def test_an_egress_result_without_an_attempt_identity_is_unconstructable() -> None:
    """(§2.1(ii)) A result with no attempt identity could not be applied to anything."""
    with pytest.raises(ValidationError, match="attempt_id must be concrete"):
        EgressResultPayload(
            instrument_key=instrument_key(), attempt_id="  ", kind=EgressResultKind.ACK
        )


# ---------------------------------------------------------------------------
# causal order (§2.1(ii))
# ---------------------------------------------------------------------------


def test_the_first_event_is_monotone_by_definition() -> None:
    """(§2.1(ii)) With no predecessor there is nothing to reverse."""
    assert ordering_admission(None, ordering(1)) is OrderingAdmission.MONOTONE


def test_a_proven_reversal_is_refused() -> None:
    """(§2.1(ii)) An event positively preceding the last consumed one is fail-closed."""
    assert ordering_admission(ordering(5), ordering(2)) is OrderingAdmission.REVERSED

    core, sink = build_core(transmit=RecordingTransmit())
    core.handle(decision_tick(sequence=5))
    result = core.handle(decision_tick(sequence=2, capsule=issue_capsule()))
    assert result.ordering is OrderingAdmission.REVERSED
    assert result.halt_reason is HaltReason.EVENT_ORDER_REVERSED
    assert result.pipeline is None


def test_an_ambiguous_pair_is_recorded_and_admitted_not_over_rejected() -> None:
    """(§2.1(ii); #26 WDR MAJOR-1) "cannot order" is not "proven backwards"."""
    bare = OrderingEvent(event_id="bare")
    assert ordering_admission(bare, OrderingEvent(event_id="other")) is (
        OrderingAdmission.AMBIGUOUS
    )


def test_a_forward_event_is_monotone() -> None:
    """(§2.1(ii)) The ordinary case advances."""
    assert ordering_admission(ordering(1), ordering(2)) is OrderingAdmission.MONOTONE
