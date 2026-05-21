import datetime as dt
from unittest.mock import MagicMock

from shared.backtest.engine import BacktestEngine, SignalType


def _bar(ts):
    return {"datetime": ts, "open": 100, "high": 101, "low": 99,
            "close": 100, "volume": 1000, "code": "X", "name": "X"}


def test_no_gate_passthrough_buy_opens_position():
    strat = MagicMock()
    strat.on_bar.return_value = SignalType.BUY
    strat.required_indicators = ()
    cfg = MagicMock()
    cfg.cost = MagicMock(commission_rate=0.0, slippage_rate=0.0, tax_rate=0.0)
    cfg.initial_capital = 10_000_000
    cfg.position_size_pct = 100.0
    cfg.max_positions = 1
    cfg.point_value = 50_000
    cfg.lookahead_guard_mode = "off"
    eng = BacktestEngine(strat, cfg)  # no gate → backward-compatible
    eng._open_position = MagicMock()
    eng.on_bar(_bar(dt.datetime(2026, 3, 1, 9, 0)))
    eng._open_position.assert_called_once()


def test_gate_block_forces_hold_no_open():
    strat = MagicMock()
    strat.on_bar.return_value = SignalType.BUY
    strat.required_indicators = ()
    cfg = MagicMock()
    cfg.cost = MagicMock(commission_rate=0.0, slippage_rate=0.0, tax_rate=0.0)
    cfg.initial_capital = 10_000_000
    cfg.position_size_pct = 100.0
    cfg.max_positions = 1
    cfg.point_value = 50_000
    cfg.lookahead_guard_mode = "off"
    gate = MagicMock()
    gate.allow.return_value = (False, "regime_high")
    eng = BacktestEngine(strat, cfg, gate=gate)
    eng._open_position = MagicMock()
    eng.on_bar(_bar(dt.datetime(2026, 3, 1, 9, 0)))
    eng._open_position.assert_not_called()
    gate.allow.assert_called_once()


def test_gate_allow_buy_still_opens():
    strat = MagicMock()
    strat.on_bar.return_value = SignalType.BUY
    strat.required_indicators = ()
    cfg = MagicMock()
    cfg.cost = MagicMock(commission_rate=0.0, slippage_rate=0.0, tax_rate=0.0)
    cfg.initial_capital = 10_000_000
    cfg.position_size_pct = 100.0
    cfg.max_positions = 1
    cfg.point_value = 50_000
    cfg.lookahead_guard_mode = "off"
    gate = MagicMock()
    gate.allow.return_value = (True, "regime_ok")
    eng = BacktestEngine(strat, cfg, gate=gate)
    eng._open_position = MagicMock()
    eng.on_bar(_bar(dt.datetime(2026, 3, 1, 9, 0)))
    eng._open_position.assert_called_once()
