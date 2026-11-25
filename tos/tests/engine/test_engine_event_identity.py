"""§7.1 canary extension — content-addressed event identity (Phase 3 A-K-1; design #31 §2.1(ii))."""

from __future__ import annotations

from decimal import Decimal

from tos.engine import EgressResultPayload, EngineEvent, EventKind, event_identity
from tos.engine.records import EVENT_ID_PREFIX
from tos.engine.vocabulary import EgressResultKind

from ._engine_fixtures import SCHEME, decision_tick, instrument_key, ordering


def test_the_same_event_bytes_produce_the_same_identity() -> None:
    """(§7.1) Two independently constructed, byte-identical events share one identity."""
    first = decision_tick(sequence=1)
    second = decision_tick(sequence=1)
    assert first == second, "the two events must be byte-identical by construction"
    assert event_identity(first, scheme=SCHEME) == event_identity(second, scheme=SCHEME)


def test_the_identity_is_content_addressed_through_derive_id() -> None:
    """(§2.1(ii)) The identity is ``derive_id("event", digest)`` — never a uuid4/timestamp nonce."""
    event = decision_tick(sequence=1)
    identity = event_identity(event, scheme=SCHEME)
    assert identity.startswith(f"{EVENT_ID_PREFIX}-")
    expected_digest = SCHEME.compute_digest(event.model_dump(mode="json"))
    assert identity == f"{EVENT_ID_PREFIX}-{expected_digest}"


def test_a_changed_reference_coordinate_produces_a_different_identity() -> None:
    """(§7.1) A single differing field (the reference coordinate) changes the whole identity."""
    first = decision_tick(sequence=1)
    second = decision_tick(sequence=2)
    assert event_identity(first, scheme=SCHEME) != event_identity(second, scheme=SCHEME)


def test_the_canary_also_holds_for_egress_result_events() -> None:
    """(§7.1) The same reproduce/differ canary holds for ``EGRESS_RESULT``, not only ``DECISION_TICK``."""

    def _egress(attempt_id: str) -> EngineEvent:
        return EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=instrument_key(),
                attempt_id=attempt_id,
                kind=EgressResultKind.FULL_FILL,
                filled_quantity=Decimal("1"),
                remaining_quantity=Decimal("0"),
                reference=ordering(1),
            ),
        )

    same_a = _egress("attempt-1")
    same_b = _egress("attempt-1")
    different = _egress("attempt-2")

    assert event_identity(same_a, scheme=SCHEME) == event_identity(
        same_b, scheme=SCHEME
    )
    assert event_identity(same_a, scheme=SCHEME) != event_identity(
        different, scheme=SCHEME
    )
