"""``trading_date`` on egress results and their evidence (plan 2026-09-26 egress trading date, T-1).

The kernel never derives a date (it is clock-free); it carries an injected ``YYYYMMDD`` token from
the result payload to the evidence record, refuses a malformed one, and — because records of both
types were persisted before the field existed — leaves it out of the dump when unset, so every
pre-existing event identity and evidence entry stays byte-identical.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.engine import (
    EgressResultKind,
    EgressResultPayload,
    EngineEvent,
    EngineEvidenceRecord,
    EventKind,
    EvidenceKind,
)
from tos.engine.records import event_identity

from ._engine_fixtures import (
    SCHEME,
    RecordingTransmit,
    build_core,
    decision_tick,
    instrument_key,
    ordering,
)


def _sent_core():
    transmit = RecordingTransmit()
    core, sink = build_core(transmit=transmit)
    result = core.handle(decision_tick(sequence=1))
    assert result.flow is not None and result.flow.attempt is not None
    return core, sink, result.flow.attempt.attempt_id


def _fill(attempt_id: str, *, sequence: int, trading_date: str | None) -> EngineEvent:
    return EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=EgressResultPayload(
            instrument_key=instrument_key(),
            attempt_id=attempt_id,
            kind=EgressResultKind.FULL_FILL,
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("0"),
            broker_execution_id="0000003663",
            reference=ordering(sequence),
            trading_date=trading_date,
        ),
    )


def test_consumed_result_carries_the_trading_date_to_evidence() -> None:
    core, sink, attempt_id = _sent_core()
    core.handle(_fill(attempt_id, sequence=2, trading_date="20260805"))
    (record,) = [
        r for r in sink.records if r.kind is EvidenceKind.EGRESS_RESULT_CONSUMED
    ]
    assert record.trading_date == "20260805"


def test_unmatched_result_carries_the_trading_date_to_evidence() -> None:
    core, sink, attempt_id = _sent_core()
    core.handle(
        EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=instrument_key(),
                attempt_id=attempt_id,
                kind=EgressResultKind.CANCEL_ACK,
                reference=ordering(2),
            ),
        )
    )
    core.handle(_fill(attempt_id, sequence=3, trading_date="20260805"))
    (record,) = [r for r in sink.records if r.kind is EvidenceKind.RESULT_UNMATCHED]
    assert record.trading_date == "20260805"


def test_unset_trading_date_is_left_out_of_every_dump() -> None:
    """A payload without a date dumps exactly as it did before the field existed, so
    :func:`event_identity` of an already-persisted event does not change."""
    event = _fill("att-1", sequence=2, trading_date=None)
    assert event.egress_result is not None
    dumped = event.model_dump(mode="json")
    assert "trading_date" not in dumped["egress_result"]
    legacy = EngineEvent.model_validate(dumped)
    scheme = SCHEME
    assert event_identity(legacy, scheme=scheme) == event_identity(event, scheme=scheme)
    record = EngineEvidenceRecord(kind=EvidenceKind.EGRESS_RESULT_CONSUMED)
    assert "trading_date" not in record.model_dump(mode="json")


def test_set_trading_date_changes_the_identity() -> None:
    scheme = SCHEME
    undated = _fill("att-1", sequence=2, trading_date=None)
    dated = _fill("att-1", sequence=2, trading_date="20260805")
    assert event_identity(undated, scheme=scheme) != event_identity(
        dated, scheme=scheme
    )
    assert dated.model_dump(mode="json")["egress_result"]["trading_date"] == "20260805"


@pytest.mark.parametrize(
    "token", ["2026-08-05", "2026085", "202608051", "abcdefgh", ""]
)
def test_malformed_trading_date_is_refused(token: str) -> None:
    with pytest.raises(
        ValueError
    ):  # ArtifactIntegrityError, surfaced via ValidationError
        _fill("att-1", sequence=2, trading_date=token)
    with pytest.raises(
        ValueError
    ):  # ArtifactIntegrityError, surfaced via ValidationError
        EngineEvidenceRecord(
            kind=EvidenceKind.EGRESS_RESULT_CONSUMED, trading_date=token
        )


def test_trading_date_is_not_part_of_the_duplicate_signature() -> None:
    """The same broker result re-delivered with and without a date is the same result: the second
    is a duplicate, not a new fact (plan §2 decision 1)."""
    core, sink, attempt_id = _sent_core()
    core.handle(_fill(attempt_id, sequence=2, trading_date="20260805"))
    again = core.handle(_fill(attempt_id, sequence=3, trading_date=None))
    consumed = [
        r for r in sink.records if r.kind is EvidenceKind.EGRESS_RESULT_CONSUMED
    ]
    assert len(consumed) == 1
    assert again.result_disposition is not None
    assert again.result_disposition.name == "DUPLICATE"
