import datetime as dt
from unittest.mock import MagicMock

from shared.backtest.engine import BacktestEngine, SignalType


def _bar(ts):
    return {"datetime": ts, "open": 100, "high": 101, "low": 99,
            "close": 100, "volume": 1000, "code": "X", "name": "X"}


def _make_cfg():
    cfg = MagicMock()
    cfg.cost = MagicMock(commission_rate=0.0, slippage_rate=0.0, tax_rate=0.0)
    cfg.initial_capital = 10_000_000
    cfg.position_size_pct = 100.0
    cfg.max_positions = 1
    cfg.point_value = 50_000
    cfg.lookahead_guard_mode = "off"
    cfg.ats_enabled = False        # short-circuits __init__'s ATS branch
    cfg.ats_simulator = None
    cfg.risk = MagicMock(close_on_day_change=False, max_daily_trades=0)
    return cfg


def _make_strat(signal):
    strat = MagicMock()
    strat.on_bar.return_value = signal
    strat.required_indicators = ()
    strat.check_exit.return_value = (False, None)
    return strat


def test_no_gate_passthrough_buy_opens_position():
    strat = _make_strat(SignalType.BUY)
    eng = BacktestEngine(strat, _make_cfg())  # gate=None, backward-compatible
    eng._open_position = MagicMock()
    eng._process_bar(_bar(dt.datetime(2026, 3, 1, 9, 0)))
    eng._open_position.assert_called_once()


def test_gate_block_forces_hold_no_open():
    strat = _make_strat(SignalType.BUY)
    gate = MagicMock()
    gate.allow.return_value = (False, "regime_high", 92.5)
    eng = BacktestEngine(strat, _make_cfg(), gate=gate)
    eng._open_position = MagicMock()
    eng._process_bar(_bar(dt.datetime(2026, 3, 1, 9, 0)))
    eng._open_position.assert_not_called()
    gate.allow.assert_called_once()


def test_gate_allow_buy_still_opens():
    strat = _make_strat(SignalType.BUY)
    gate = MagicMock()
    gate.allow.return_value = (True, "regime_ok", 50.0)
    eng = BacktestEngine(strat, _make_cfg(), gate=gate)
    eng._open_position = MagicMock()
    eng._process_bar(_bar(dt.datetime(2026, 3, 1, 9, 0)))
    eng._open_position.assert_called_once()
