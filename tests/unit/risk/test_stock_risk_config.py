"""StockRiskConfig loads the risk_stock section; stock trading windows load separately."""

from __future__ import annotations

from shared.risk.config import StockRiskConfig, load_stock_trading_windows


def test_stock_risk_config_loads_risk_stock_section():
    cfg = StockRiskConfig.from_yaml()
    # Exact values from the `risk_stock:` section — distinct from the `risk:`
    # futures defaults (equity 5_000_000, max_daily_trades 3, max_spread_ticks 2).
    assert cfg.account_equity_krw == 10_000_000
    assert cfg.max_daily_trades == 10
    assert cfg.max_spread_ticks == 5


def test_stock_trading_windows_are_korean_equity_session():
    assert load_stock_trading_windows() == ["09:00-15:30"]
