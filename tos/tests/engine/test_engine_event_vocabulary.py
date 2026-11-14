"""§7.2-7 — the event vocabulary is closed and an unknown kind is a fail-closed error (§2.2)."""

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
    decision_tick,
    instrument_key,
    issue_capsule,
    ordering,
)


class _BogusEvent:
    """An object shaped like an event but carrying a kind outside the closed vocabulary."""

    kind = "CANCEL"


def test_the_vocabulary_is_exactly_the_two_declared_kinds() -> None:
    """(§2.2) The closed set and the enum agree — no member is admissible-but-unlisted."""
    assert frozenset(EventKind) == ADMISSIBLE_EVENT_KINDS
    assert sorted(k.value for k in ADMISSIBLE_EVENT_KINDS) == [
        "DECISION_TICK",
        "EGRESS_RESULT",
    ]


@pytest.mark.parametrize(
    "bogus",
    ["CORPORATE_ACTION", "CANCEL", "", None, 0, object(), _BogusEvent()],
)
def test_an_unknown_kind_is_a_fail_closed_error(bogus) -> None:
    """(§7.2-7) Anything outside the closed vocabulary raises — it is never dropped silently."""
    with pytest.raises(UnknownEventKindError):
        admit_kind(bogus)


@pytest.mark.parametrize("value", ["DECISION_TICK", "EGRESS_RESULT"])
def test_a_string_that_merely_matches_a_member_value_is_not_admitted(value) -> None:
    """(§2.2) Admission is positive **membership**, not string equality — no coercion path."""
    with pytest.raises(UnknownEventKindError):
        admit_kind(value)


def test_the_core_refuses_an_event_whose_kind_is_outside_the_vocabulary() -> None:
    """(§7.2-7) The dispatcher itself raises rather than returning a benign "nothing happened"."""
    core, _ = build_core(transmit=RecordingTransmit())
    with pytest.raises(UnknownEventKindError):
        core.handle(_BogusEvent())  # type: ignore[arg-type]


def test_every_admissible_kind_is_actually_handled() -> None:
    """(§2.2) Every vocabulary member has a handler — an unhandled member is not a no-op."""
    core, _ = build_core(transmit=RecordingTransmit())
    for kind in ADMISSIBLE_EVENT_KINDS:
        assert admit_kind(kind) is kind
    assert core.handle(decision_tick(sequence=1)).kind is EventKind.DECISION_TICK


def test_an_event_payload_must_match_its_kind() -> None:
    """(§2.2) The closed-vocabulary discipline reaches the payload shape too."""
    with pytest.raises(ValidationError, match="requires a decision_tick payload"):
        EngineEvent(kind=EventKind.DECISION_TICK)
    with pytest.raises(ValidationError, match="requires a egress_result payload"):
        EngineEvent(kind=EventKind.EGRESS_RESULT)


def test_an_event_may_not_carry_the_other_kinds_payload() -> None:
    """(§2.2) Two payloads on one event is an ambiguous event — unconstructable."""
    tick = decision_tick(sequence=1)
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
