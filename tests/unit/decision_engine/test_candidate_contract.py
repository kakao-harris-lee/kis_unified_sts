"""A provider-built context -> setup -> candidate must parse in risk_filter."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from services.risk_filter.main import _signal_from_stream_fields
from shared.decision.context import MarketContext
from shared.decision.setups.gap_reversion import SetupAGapReversion
from shared.decision.setups.vwap_reversion import SetupDVWAPReversion

_KST = ZoneInfo("Asia/Seoul")


class _Macro:
    sp500_change_pct = 1.0


def test_setup_a_candidate_roundtrips_through_risk_filter_parser():
    # Build a context that makes Setup A fire (gap up + retrace in band).
    # now is KST 09:30 → minutes_since_open=45 (08:45 open) ∈ [10,120].
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


def test_setup_d_candidate_roundtrips_through_risk_filter_parser():
    """Setup D's candidate must survive the same stream encode/parse as Setup A.

    Setup D joined the decoupled roster in the F-9 port; it emits a different
    ``setup_type`` and always fills stop AND target (the risk_filter parser
    requires both), so the round trip is pinned here rather than assumed from
    the Setup A case.
    """
    # vwap=100, atr=2 → z = (104-100)/2 = 2.0 >= extreme_atr_mult 1.8 → short.
    # 11:00 KST = 135 min after the 08:45 open → inside the session window.
    ctx = MarketContext(
        now=datetime(2026, 6, 5, 11, 0, tzinfo=_KST),
        symbol="A05",
        current_price=104.0,
        prev_close=100.0,
        today_open=100.0,
        vwap=100.0,
        atr_14=2.0,
        atr_90th_percentile=2.0,
        last_15min_high=104.0,
        last_15min_low=104.0,
        current_spread_ticks=1.0,
        macro_overnight=None,
        scheduled_events=[],
    )
    sig = SetupDVWAPReversion().check(ctx)
    assert (
        sig is not None
    ), "Setup D did not fire — check the VWAP-stretch math against SetupDConfig defaults"
    fields = sig.to_stream_dict()
    fields["signal_id"] = "cafebabe"
    encoded = {k.encode(): str(v).encode() for k, v in fields.items()}
    signal_id, parsed = _signal_from_stream_fields(encoded)
    assert signal_id == "cafebabe"
    assert parsed.setup_type == "D_vwap_reversion"
    assert parsed.direction == sig.direction == "short"
    assert parsed.entry_price == sig.entry_price
    assert parsed.stop_loss == sig.stop_loss
    assert parsed.take_profit == sig.take_profit
