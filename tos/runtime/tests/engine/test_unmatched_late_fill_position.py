"""A fill refused after ``CANCEL_ACK`` stays visible to the position reader even when a later
``EXPIRED`` is applied — driven through the real engine, not hand-seeded rows."""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.engine import EngineEvent, EventKind
from tos.engine.records import EgressResultPayload
from tos.engine.vocabulary import EgressResultKind, ResultDisposition
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.riskstate.position import EvidencePositionReader

from . import _fixtures as fx
from . import _parity_fixtures as pfx


def _result(
    attempt_id: str,
    kind: EgressResultKind,
    filled: str | None = None,
    remaining: str | None = None,
) -> EngineEvent:
    return EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=EgressResultPayload(
            instrument_key=fx.instrument_key(),
            attempt_id=attempt_id,
            kind=kind,
            filled_quantity=Decimal(filled) if filled is not None else None,
            remaining_quantity=Decimal(remaining) if remaining is not None else None,
        ),
    )


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_expired_after_refused_late_fill_leaves_the_fill_in_flight(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source: object,
    side: str,
) -> None:
    gateway = fx.FakeGateway(auto_ack=False)
    driver, _core = pfx.build_engine_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
        transmit=gateway,
        sink=pfx.durable_engine_sink(evidence_store),
    )
    driver.bind_gateway(gateway)
    tick = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick.flow is not None and tick.flow.handed_off is True
    attempt_id = tick.flow.attempt.attempt_id  # type: ignore[union-attr]
    evidence_store.append(
        {
            "kind": "SEND_SEALED",
            "attempt_id": attempt_id,
            "send_seal": {
                "attempt_id": attempt_id,
                "instrument_key": {
                    "account": fx.ACCOUNT,
                    "instrument": fx.INSTRUMENT,
                },
                "outbound_side": side,
                "outbound_quantity": "10",
            },
        },
        kind="SEND_SEALED",
        record_class="SEND_SEALED",
    )

    cancel = driver.enqueue_and_run(_result(attempt_id, EgressResultKind.CANCEL_ACK))
    late_fill = driver.enqueue_and_run(
        _result(attempt_id, EgressResultKind.FULL_FILL, filled="10", remaining="0")
    )
    expired = driver.enqueue_and_run(_result(attempt_id, EgressResultKind.EXPIRED))
    assert [
        cancel.result_disposition,
        late_fill.result_disposition,
        expired.result_disposition,
    ] == [
        ResultDisposition.APPLIED,
        ResultDisposition.NON_MONOTONIC_PROJECTION,
        ResultDisposition.APPLIED,
    ]

    obs = EvidencePositionReader(
        evidence_store,
        account=fx.ACCOUNT,
        instrument=fx.INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    ).observe()
    toward, against = (
        (obs.in_flight_buy, obs.in_flight_sell)
        if side == "BUY"
        else (obs.in_flight_sell, obs.in_flight_buy)
    )
    assert obs.confirmed_net == Decimal(0)
    assert toward == Decimal(10)
    assert against == Decimal(0)
    assert (obs.unknown_buy, obs.unknown_sell) == (Decimal(0), Decimal(0))
