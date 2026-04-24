"""Tests for ``RiskFilterLayer.from_config`` factory."""

from __future__ import annotations

from shared.risk.config import FuturesRiskConfig
from shared.risk.filters.consecutive_loss import ConsecutiveLossFilter
from shared.risk.filters.daily_mdd import DailyMDDFilter
from shared.risk.filters.daily_trade_count import DailyTradeCountFilter
from shared.risk.filters.open_position import OpenPositionFilter
from shared.risk.filters.spread import SpreadFilter
from shared.risk.filters.trading_hours import TradingHoursFilter
from shared.risk.filters.volatility import VolatilityFilter
from shared.risk.filters.weekly_mdd import WeeklyMDDFilter
from shared.risk.layer import RiskFilterLayer


def _cfg() -> FuturesRiskConfig:
    return FuturesRiskConfig(
        account_equity_krw=5_000_000,
        daily_mdd_limit_pct=0.03,
        weekly_mdd_limit_pct=0.07,
        max_position_risk_pct=0.015,
        max_daily_trades=3,
        max_position_size_contracts=2,
        consecutive_loss_soft_threshold=4,
        consecutive_loss_hard_threshold=6,
        max_spread_ticks=2,
    )


def test_from_config_builds_all_8_filters_in_spec_order() -> None:
    layer = RiskFilterLayer.from_config(
        _cfg(), trading_windows=["09:00-10:30", "14:30-15:20"]
    )
    expected_types = [
        TradingHoursFilter,
        DailyMDDFilter,
        WeeklyMDDFilter,
        ConsecutiveLossFilter,
        DailyTradeCountFilter,
        VolatilityFilter,
        SpreadFilter,
        OpenPositionFilter,
    ]
    actual_types = [type(f) for f in layer._filters]
    assert actual_types == expected_types


def test_from_config_propagates_config_values() -> None:
    cfg = _cfg()
    layer = RiskFilterLayer.from_config(cfg, trading_windows=["09:00-15:30"])

    daily_mdd = layer._filters[1]
    assert isinstance(daily_mdd, DailyMDDFilter)
    assert daily_mdd.account_equity_krw == cfg.account_equity_krw
    assert daily_mdd.daily_mdd_limit_pct == cfg.daily_mdd_limit_pct

    consec = layer._filters[3]
    assert isinstance(consec, ConsecutiveLossFilter)
    assert consec.soft_threshold == cfg.consecutive_loss_soft_threshold
    assert consec.hard_threshold == cfg.consecutive_loss_hard_threshold


def test_from_config_default_providers_never_reject() -> None:
    """Default stub providers must never cause spurious rejections so the
    backtest runs the layer exactly as if the provider-driven filters were
    permissive no-ops."""
    from datetime import UTC, datetime, timedelta

    from shared.decision.signal import Signal
    from shared.risk.state import RiskStateSnapshot

    layer = RiskFilterLayer.from_config(_cfg(), trading_windows=["00:00-23:59"])
    # Build a minimal signal squarely inside the always-valid window.
    sig = Signal(
        setup_type="A_gap_reversion",
        direction="long",
        symbol="A05603",
        entry_price=350.0,
        stop_loss=349.0,
        take_profit=352.0,
        confidence=0.7,
        reason_tags=["test"],
        valid_until=datetime.now(UTC) + timedelta(minutes=10),
        generated_at=datetime.now(UTC),
    )
    state = RiskStateSnapshot()
    result = layer.evaluate(sig, state)
    assert result.passed
    assert result.skip_reason is None


def test_from_config_custom_providers_propagate() -> None:
    cfg = _cfg()
    calls: dict[str, int] = {"atr": 0, "spread": 0, "position": 0}

    def atr() -> float:
        calls["atr"] += 1
        return 0.5

    def spread() -> float:
        calls["spread"] += 1
        return 0.5

    def has_pos(_sym: str) -> bool:
        calls["position"] += 1
        return False

    layer = RiskFilterLayer.from_config(
        cfg,
        trading_windows=["00:00-23:59"],
        current_atr_provider=atr,
        current_spread_provider=spread,
        has_open_position_provider=has_pos,
    )
    # VolatilityFilter should have the injected provider, not the stub.
    vol = layer._filters[5]
    assert vol._current_atr_provider is atr
    spr = layer._filters[6]
    assert spr._current_spread_provider is spread
    op = layer._filters[7]
    assert op._has_open_position_provider is has_pos
