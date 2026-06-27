# tests/unit/decision/test_signal.py
from datetime import UTC, datetime, timedelta

import pytest

from shared.decision.signal import Signal


def _kwargs(**overrides):
    base = {
        "setup_type": "A_gap_reversion",
        "direction": "long",
        "symbol": "A05603",
        "entry_price": 350.25,
        "stop_loss": 349.25,
        "take_profit": 352.00,
        "confidence": 0.7,
        "reason_tags": ["sp500_gap_+1.20%"],
        "valid_until": datetime.now(UTC) + timedelta(minutes=10),
        "generated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return base


def test_signal_valid_construction():
    s = Signal(**_kwargs())
    assert s.setup_type == "A_gap_reversion"
    assert s.direction == "long"


@pytest.mark.parametrize("direction", ["up", "buy", "", None])
def test_signal_rejects_bad_direction(direction):
    with pytest.raises(ValueError):
        Signal(**_kwargs(direction=direction))


def test_signal_to_stream_dict_roundtrip():
    s = Signal(**_kwargs())
    fields = s.to_stream_dict()
    assert fields["setup_type"] == "A_gap_reversion"
    assert fields["direction"] == "long"
    # reason_tags serialized as JSON
    import json

    assert json.loads(fields["reason_tags_json"]) == ["sp500_gap_+1.20%"]


def test_signal_risk_reward_ratio():
    s = Signal(**_kwargs(entry_price=100.0, stop_loss=99.0, take_profit=102.0))
    assert s.risk_reward_ratio() == pytest.approx(2.0)
