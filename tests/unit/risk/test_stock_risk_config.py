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


def test_stock_risk_config_loads_leverage_block():
    """Phase 4-g stock leverage cap ships ENABLED + enforce with cap 1.0 (cash
    account — no leverage; multiplier 1) after the operator flip (2026-07-12):
    P4-g gate + P5-3 stock_risk_filter provider wiring complete. Pinning the
    shipped values fails the build on an accidental revert to shadow/disabled, a
    cap typo, or a mis-nested block. The filter stays fail-open on missing/
    no-provider data — only gross_leverage > 1.0 rejects a new entry."""
    lev = StockRiskConfig.from_yaml().leverage
    assert lev.enabled is True
    assert lev.mode == "enforce"
    assert lev.max_gross_leverage == 1.0
    assert lev.stale_max_age_seconds is None


def test_stock_risk_config_loads_core_correlation_block():
    """Phase 5B Track A/B correlation knobs come from risk.yaml risk_stock."""
    cfg = StockRiskConfig.from_yaml()
    cc = cfg.core_correlation
    assert cc.overlap_enabled is True
    assert cc.reload_interval_seconds == 60
    assert cc.sector_cap.enabled is True
    assert cc.sector_cap.sector_key == "semiconductor_equipment"
    assert cc.sector_cap.cap == 0.40
    assert cc.sector_cap.skip_reason == "sector_cap_semiconductor"
    assert cc.sector_cap.classification_source == "core_holdings"
