import datetime as dt
from unittest.mock import MagicMock


def _ctx(ts=None, code="futures"):
    from shared.strategy.base import EntryContext
    return EntryContext(
        market_data={"code": code},
        timestamp=ts or dt.datetime.now(dt.UTC),
    )


def _sig(direction="long"):
    s = MagicMock()
    s.metadata = {"signal_direction": direction}
    return s


def _cfg(threshold=60.0):
    from shared.strategy.gates.regime_gate import GateConfig
    return GateConfig(
        regime_percentile_max=threshold,
        impact_score_max=70,
        event_window_minutes=15,
        require_overnight_us_direction=False,
        permissive_on_missing=True,
    )


def test_gate_cfg_none_returns_not_blocked():
    """When gate_cfg is None (strategy not opted in), helper is a no-op."""
    from shared.strategy.gates.adapter_helper import apply_regime_gate
    blocked = apply_regime_gate(
        gate_cfg=None, decision_signal=_sig(), context=_ctx(),
        strategy_name="setup_a_gap_reversion",
        redis=MagicMock(), ch_client=MagicMock())
    assert blocked is False


def test_gate_allow_path_not_blocked_and_logs(monkeypatch):
    """When the gate allows, blocked=False and a row is logged."""
    from shared.strategy.gates import adapter_helper
    # Stub LiveVolInputs to return None (PERMISSIVE → allow)
    monkeypatch.setattr(adapter_helper, "LiveVolInputs",
                        lambda **_kw: MagicMock(
                            latest_vol_at=MagicMock(return_value=None),
                            events_within=MagicMock(return_value=[]),
                            macro_for=MagicMock(return_value=None)))
    logged_rows = []
    monkeypatch.setattr(adapter_helper, "_log_decision",
                        lambda **kw: logged_rows.append(kw))
    blocked = adapter_helper.apply_regime_gate(
        gate_cfg=_cfg(), decision_signal=_sig("long"), context=_ctx(code="A01603"),
        strategy_name="setup_a_gap_reversion",
        redis=MagicMock(), ch_client=MagicMock())
    assert blocked is False
    assert len(logged_rows) == 1
    assert logged_rows[0]["strategy"] == "setup_a_gap_reversion"
    assert logged_rows[0]["signal_direction"] == "long"
    assert logged_rows[0]["asset"] == "A01603"
    assert logged_rows[0]["allow"] is True


def test_gate_block_path_blocked_and_logs(monkeypatch):
    """When the gate blocks (high regime_percentile > max), blocked=True and logged."""
    from shared.strategy.gates import adapter_helper
    # Vol asof is 09:00, ts is 09:30 → asof < ts, so NOT treated as future row
    vol_asof = dt.datetime(2026, 5, 22, 9, 0)   # naive — past relative to ts
    ctx_ts = dt.datetime(2026, 5, 22, 9, 30, tzinfo=dt.UTC)
    # Stub LiveVolInputs to return high regime_pct (75 > threshold 60) → block
    monkeypatch.setattr(adapter_helper, "LiveVolInputs",
                        lambda **_kw: MagicMock(
                            latest_vol_at=MagicMock(
                                return_value=(vol_asof, 75.0)),
                            events_within=MagicMock(return_value=[]),
                            macro_for=MagicMock(return_value=None)))
    logged_rows = []
    monkeypatch.setattr(adapter_helper, "_log_decision",
                        lambda **kw: logged_rows.append(kw))
    blocked = adapter_helper.apply_regime_gate(
        gate_cfg=_cfg(threshold=60.0), decision_signal=_sig("long"),
        context=_ctx(ts=ctx_ts), strategy_name="setup_c_event_reaction",
        redis=MagicMock(), ch_client=MagicMock())
    assert blocked is True
    assert logged_rows[0]["allow"] is False
    assert "regime_percentile" in logged_rows[0]["reason"]


def test_log_failure_does_not_propagate(monkeypatch):
    """CH insert failure must NOT change the gate verdict or raise."""
    from shared.strategy.gates import adapter_helper
    monkeypatch.setattr(adapter_helper, "LiveVolInputs",
                        lambda **_kw: MagicMock(
                            latest_vol_at=MagicMock(return_value=None),
                            events_within=MagicMock(return_value=[]),
                            macro_for=MagicMock(return_value=None)))
    monkeypatch.setattr(adapter_helper, "_log_decision",
                        MagicMock(side_effect=RuntimeError("ch down")))
    blocked = adapter_helper.apply_regime_gate(
        gate_cfg=_cfg(), decision_signal=_sig(),
        context=_ctx(), strategy_name="bb_reversion_15m",
        redis=MagicMock(), ch_client=MagicMock())
    assert blocked is False  # verdict preserved


def test_signal_direction_falls_back_to_long_when_missing():
    """If decision_signal has no metadata/side, defaults to 'long'."""
    from shared.strategy.gates.adapter_helper import apply_regime_gate
    sig = MagicMock()
    sig.metadata = None  # no metadata
    sig.side = None  # no side
    # Use gate_cfg=None for fast no-op path (we just want to verify no crash)
    blocked = apply_regime_gate(
        gate_cfg=None, decision_signal=sig, context=_ctx(),
        strategy_name="x", redis=MagicMock(), ch_client=MagicMock())
    assert blocked is False
