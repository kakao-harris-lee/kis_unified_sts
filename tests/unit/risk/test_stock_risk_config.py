"""StockRiskConfig loads the risk_stock section; stock trading windows load separately."""

from __future__ import annotations

from shared.risk.config import StockRiskConfig, load_stock_trading_windows


def test_stock_risk_config_loads_risk_stock_section():
    cfg = StockRiskConfig.from_yaml()
    assert cfg.account_equity_krw > 0
    assert cfg.max_daily_trades >= 1
    assert hasattr(cfg, "consecutive_loss_soft_threshold")
    assert hasattr(cfg, "max_spread_ticks")


def test_stock_trading_windows_are_korean_equity_session():
    windows = load_stock_trading_windows()
    assert isinstance(windows, list)
    assert windows, "stock trading windows must be non-empty"
    assert windows[0].startswith("09:00")
