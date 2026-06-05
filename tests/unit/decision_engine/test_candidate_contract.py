"""A provider-built context -> setup -> candidate must parse in risk_filter."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from services.risk_filter.main import _signal_from_stream_fields
from shared.decision.context import MarketContext
from shared.decision.setups.gap_reversion import SetupAGapReversion

_KST = ZoneInfo("Asia/Seoul")


class _Macro:
    sp500_change_pct = 1.0


def test_setup_a_candidate_roundtrips_through_risk_filter_parser():
    # Build a context that makes Setup A fire (gap up + retrace in band).
    # now must be KST 09:30 so minutes_since_open=30 ∈ [10,120].
    # prev_close=100, today_open=105 (+5% gap), current_price=103
    # retrace = (105-103)/5 = 0.4 ∈ [0.20, 0.70] → fires.
    ctx = MarketContext(
        now=datetime(2026, 6, 5, 9, 30, tzinfo=_KST),
        symbol="A05",
        current_price=103.0,
        prev_close=100.0,
        today_open=105.0,  # +5% gap up
        vwap=0.0,
        atr_14=1.0,
        atr_90th_percentile=0.0,
        last_15min_high=0.0,
        last_15min_low=0.0,
        current_spread_ticks=0.0,
        macro_overnight=_Macro(),
        scheduled_events=[],
    )
    sig = SetupAGapReversion().check(ctx)
    assert (
        sig is not None
    ), "Setup A did not fire — check gap/retrace/macro math against SetupAConfig defaults"
    fields = sig.to_stream_dict()
    fields["signal_id"] = "deadbeef"
    # encode like Redis (bytes keys/values) then parse back
    encoded = {k.encode(): str(v).encode() for k, v in fields.items()}
    signal_id, parsed = _signal_from_stream_fields(encoded)
    assert signal_id == "deadbeef"
    assert parsed.setup_type == "A_gap_reversion"
    assert parsed.direction == sig.direction
    assert parsed.entry_price == sig.entry_price
