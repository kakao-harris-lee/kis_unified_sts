"""Position codec: M4-O record -> Position, opened_at_ms guard, high_water round-trip."""

from __future__ import annotations

import json

from services.stock_exit.positions import (
    parse_position_record,
    position_from_record,
    record_with_high_water,
)
from shared.models.position import PositionSide, PositionState


def _m4o_record(code: str = "005930") -> dict[str, object]:
    return {
        "code": code,
        "entry_price": 71000.0,
        "quantity": 10,
        "opened_at_ms": 1_700_000_000_000,
        "state": "survival",
        "signal_id": "sig-1",
    }


def test_parse_accepts_m4o_record() -> None:
    rec = parse_position_record(json.dumps(_m4o_record()).encode())
    assert rec is not None
    assert rec["code"] == "005930"


def test_parse_skips_foreign_record_without_opened_at_ms() -> None:
    foreign = {
        "id": "uuid",
        "code": "005930",
        "entry_price": 71000.0,
        "quantity": 10,
        "entry_time": "2026-06-06T00:00:00+00:00",
    }
    assert parse_position_record(json.dumps(foreign)) is None


def test_parse_skips_garbage() -> None:
    assert parse_position_record(b"not-json") is None


def test_position_from_record_builds_long_position() -> None:
    pos = position_from_record(_m4o_record(), fee_rate=0.003)
    assert pos.code == "005930"
    assert pos.side == PositionSide.LONG
    assert pos.quantity == 10
    assert pos.entry_price == 71000.0
    assert pos.state == PositionState.SURVIVAL
    assert pos.entry_time.tzinfo is not None
    assert pos.highest_price == 71000.0
    assert pos.lowest_price == 71000.0
    assert pos.fee_rate == 0.003


def test_high_water_round_trip() -> None:
    rec = _m4o_record()
    pos = position_from_record(rec, fee_rate=0.003)
    pos.update_price(73000.0)  # new high
    raw = record_with_high_water(rec, pos)
    rec2 = parse_position_record(raw)
    assert rec2 is not None
    restored = position_from_record(rec2, fee_rate=0.003)
    assert restored.highest_price == 73000.0  # trailing survives restart
    assert restored.entry_price == 71000.0
    assert restored.quantity == 10
