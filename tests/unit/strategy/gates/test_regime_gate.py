import datetime as dt

from shared.strategy.gates.regime_gate import GateConfig, RegimeGate


def _cfg(**kw):
    base = {
        "regime_percentile_max": 80.0,
        "impact_score_max": 70,
        "event_window_minutes": 15,
        "require_overnight_us_direction": False,
        "permissive_on_missing": True,
    }
    base.update(kw)
    return GateConfig(**base)


class _StubInputs:
    def __init__(self, vol=None, events=(), macro_sp500_pct=None):
        self.vol = vol
        self.events = list(events)
        self.macro_sp500_pct = macro_sp500_pct

    def latest_vol_at(self, _ts):
        return self.vol  # tuple(asof, regime_percentile) or None

    def events_within(self, _ts, _window_min):
        return self.events  # list of (asof, impact_score)

    def macro_for(self, _date):
        return self.macro_sp500_pct  # float or None


def test_allow_when_regime_low_no_events():
    g = RegimeGate(_cfg(), _StubInputs(
        vol=(dt.datetime(2026, 3, 1, 9, 0), 50.0), events=()))
    allow, reason, regime_pct = g.allow(
        dt.datetime(2026, 3, 1, 9, 0), "futures",
        signal_direction="long")
    assert allow is True
    assert reason == "regime_ok"
    assert regime_pct == 50.0


def test_block_when_regime_high():
    g = RegimeGate(_cfg(), _StubInputs(
        vol=(dt.datetime(2026, 3, 1, 9, 0), 92.5), events=()))
    allow, reason, regime_pct = g.allow(
        dt.datetime(2026, 3, 1, 9, 0), "futures", signal_direction="long")
    assert allow is False
    assert "regime_percentile" in reason
    assert regime_pct == 92.5


def test_block_when_recent_high_impact_event():
    g = RegimeGate(_cfg(), _StubInputs(
        vol=(dt.datetime(2026, 3, 1, 9, 0), 50.0),
        events=[(dt.datetime(2026, 3, 1, 9, 5), 85)]))
    allow, reason, regime_pct = g.allow(
        dt.datetime(2026, 3, 1, 9, 10), "futures", signal_direction="long")
    assert allow is False
    assert "impact_score" in reason
    assert regime_pct == 50.0


def test_overnight_us_direction_alignment_blocks_opposite():
    g = RegimeGate(_cfg(require_overnight_us_direction=True),
        _StubInputs(vol=(dt.datetime(2026, 3, 1, 9, 0), 50.0),
                    macro_sp500_pct=-1.2))  # US down
    allow, reason, regime_pct = g.allow(
        dt.datetime(2026, 3, 1, 9, 0), "futures", signal_direction="long")
    assert allow is False
    assert "overnight" in reason
    assert regime_pct == 50.0


def test_permissive_on_missing_vol_allows():
    g = RegimeGate(_cfg(), _StubInputs(vol=None, events=()))
    allow, reason, regime_pct = g.allow(
        dt.datetime(2026, 3, 1, 9, 0), "futures", signal_direction="long")
    assert allow is True
    assert reason == "permissive_missing_vol"
    assert regime_pct == 0.0


def test_allow_returns_3_tuple_with_regime_pct():
    """Refactor regression: gate.allow returns (allow, reason, regime_pct)
    instead of (allow, reason) + string-parsing regime_pct from reason."""
    g = RegimeGate(_cfg(), _StubInputs(
        vol=(dt.datetime(2026, 3, 1, 9, 0), 75.5), events=()))
    result = g.allow(
        dt.datetime(2026, 3, 1, 9, 0), "futures", signal_direction="long")
    assert len(result) == 3
    allow, reason, regime_pct = result
    assert allow is True
    assert reason == "regime_ok"
    assert regime_pct == 75.5


def test_lookahead_guard_rejects_future_vol():
    # vol asof is AFTER the decision ts — must NOT be used
    g = RegimeGate(_cfg(), _StubInputs(
        vol=(dt.datetime(2026, 3, 1, 9, 5), 92.5), events=()))
    allow, reason, regime_pct = g.allow(
        dt.datetime(2026, 3, 1, 9, 0), "futures", signal_direction="long")
    # Future row treated as MISSING (permissive)
    assert allow is True
    assert reason == "permissive_missing_vol"
    assert regime_pct == 0.0
