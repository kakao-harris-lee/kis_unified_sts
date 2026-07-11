"""Tests for ``RiskFilterLayer.from_config`` factory."""

from __future__ import annotations

from shared.risk.config import FuturesRiskConfig, StockRiskConfig
from shared.risk.filters.concurrent_positions import ConcurrentPositionsFilter
from shared.risk.filters.consecutive_loss import ConsecutiveLossFilter
from shared.risk.filters.core_correlation import (
    CoreSectorCapFilter,
    TrackAOverlapFilter,
)
from shared.risk.filters.daily_mdd import DailyMDDFilter
from shared.risk.filters.daily_trade_count import DailyTradeCountFilter
from shared.risk.filters.open_position import OpenPositionFilter
from shared.risk.filters.portfolio_mdd import PortfolioMddFilter
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


def test_from_config_builds_all_9_filters_in_spec_order() -> None:
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
        # Phase 3B: unified portfolio-MDD gate (fail-open; shadow-mode no-op).
        PortfolioMddFilter,
    ]
    actual_types = [type(f) for f in layer._filters]
    assert actual_types == expected_types


def test_futures_config_never_grows_core_correlation_filters() -> None:
    """FuturesRiskConfig has no core_correlation attribute → futures chain
    stays untouched by the Phase 5B stock-only rules."""
    layer = RiskFilterLayer.from_config(_cfg(), trading_windows=["09:00-15:30"])
    assert not any(
        isinstance(f, TrackAOverlapFilter | CoreSectorCapFilter) for f in layer._filters
    )


def test_stock_config_appends_core_correlation_filters_last() -> None:
    layer = RiskFilterLayer.from_config(
        StockRiskConfig(),
        trading_windows=["09:00-15:30"],
        core_holdings_provider=lambda: None,  # hermetic: no file loader built
        stock_positions_provider=lambda: None,
    )
    assert [type(f) for f in layer._filters[-3:]] == [
        PortfolioMddFilter,
        TrackAOverlapFilter,
        CoreSectorCapFilter,
    ]


def test_stock_config_core_correlation_flags_disable_each_filter() -> None:
    cfg = StockRiskConfig()
    cfg.core_correlation.overlap_enabled = False
    layer = RiskFilterLayer.from_config(
        cfg,
        trading_windows=["09:00-15:30"],
        core_holdings_provider=lambda: None,
    )
    assert not any(isinstance(f, TrackAOverlapFilter) for f in layer._filters)
    assert any(isinstance(f, CoreSectorCapFilter) for f in layer._filters)

    cfg.core_correlation.sector_cap.enabled = False
    layer = RiskFilterLayer.from_config(
        cfg,
        trading_windows=["09:00-15:30"],
        core_holdings_provider=lambda: None,
    )
    assert not any(
        isinstance(f, TrackAOverlapFilter | CoreSectorCapFilter) for f in layer._filters
    )


def test_stock_config_core_correlation_values_propagate() -> None:
    cfg = StockRiskConfig()

    def _ledger() -> None:
        return None

    def _positions() -> None:
        return None

    layer = RiskFilterLayer.from_config(
        cfg,
        trading_windows=["09:00-15:30"],
        core_holdings_provider=_ledger,
        stock_positions_provider=_positions,
    )
    overlap = layer._filters[-2]
    assert isinstance(overlap, TrackAOverlapFilter)
    assert overlap._core_holdings_provider is _ledger

    cap = layer._filters[-1]
    assert isinstance(cap, CoreSectorCapFilter)
    assert cap._core_holdings_provider is _ledger
    assert cap._positions_provider is _positions
    assert cap.sector_key == cfg.core_correlation.sector_cap.sector_key
    assert cap.cap == cfg.core_correlation.sector_cap.cap
    assert cap.skip_reason == cfg.core_correlation.sector_cap.skip_reason


def test_from_config_portfolio_mdd_disabled_by_config() -> None:
    cfg = _cfg()
    cfg.portfolio_mdd.enabled = False
    layer = RiskFilterLayer.from_config(cfg, trading_windows=["09:00-15:30"])
    assert not any(isinstance(f, PortfolioMddFilter) for f in layer._filters)


# ---------------------------------------------------------------------------
# Phase 4-e: ConcurrentPositionsFilter — default-inert + opt-in wiring
# ---------------------------------------------------------------------------


def test_concurrent_positions_absent_by_default() -> None:
    """Default config (enabled=False) never builds the concurrency filter, so
    the existing chain is structurally unchanged."""
    futures = RiskFilterLayer.from_config(_cfg(), trading_windows=["09:00-15:30"])
    assert not any(isinstance(f, ConcurrentPositionsFilter) for f in futures._filters)
    stock = RiskFilterLayer.from_config(
        StockRiskConfig(),
        trading_windows=["09:00-15:30"],
        core_holdings_provider=lambda: None,
        stock_positions_provider=lambda: None,
    )
    assert not any(isinstance(f, ConcurrentPositionsFilter) for f in stock._filters)


def test_concurrent_positions_appended_when_enabled() -> None:
    cfg = _cfg()
    cfg.concurrent_positions.enabled = True
    cfg.concurrent_positions.max_total_positions = 20
    cfg.concurrent_positions.max_positions_per_asset = 5

    def _count() -> dict[str, int]:
        return {}

    layer = RiskFilterLayer.from_config(
        cfg,
        trading_windows=["09:00-15:30"],
        open_positions_count_provider=_count,
    )
    matches = [f for f in layer._filters if isinstance(f, ConcurrentPositionsFilter)]
    assert len(matches) == 1
    filt = matches[0]
    assert filt.asset_class == "futures"  # FuturesRiskConfig._asset_class
    assert filt.max_total_positions == 20
    assert filt.max_positions_per_asset == 5
    assert filt._count_provider is _count


def test_concurrent_positions_binds_stock_asset_class() -> None:
    cfg = StockRiskConfig()
    cfg.concurrent_positions.enabled = True
    cfg.concurrent_positions.max_positions_per_asset = 15
    layer = RiskFilterLayer.from_config(
        cfg,
        trading_windows=["09:00-15:30"],
        core_holdings_provider=lambda: None,
        stock_positions_provider=lambda: None,
    )
    filt = next(f for f in layer._filters if isinstance(f, ConcurrentPositionsFilter))
    assert filt.asset_class == "stock"  # StockRiskConfig._asset_class
    assert filt.max_positions_per_asset == 15


def test_concurrent_positions_warns_when_enabled_but_unwired(caplog) -> None:
    """F5: enabling the filter without a count provider must emit exactly one
    build-time warning so operators can tell 'inert (unwired)' from
    'active + passing'."""
    import logging

    cfg = _cfg()
    cfg.concurrent_positions.enabled = True
    with caplog.at_level(logging.WARNING, logger="shared.risk.layer"):
        RiskFilterLayer.from_config(cfg, trading_windows=["09:00-15:30"])
    warnings = [r.getMessage() for r in caplog.records if r.name == "shared.risk.layer"]
    assert sum("no count provider wired" in m for m in warnings) == 1


def test_concurrent_positions_no_warning_when_disabled(caplog) -> None:
    """Default (disabled) config must not emit the unwired warning at all."""
    import logging

    with caplog.at_level(logging.WARNING, logger="shared.risk.layer"):
        RiskFilterLayer.from_config(_cfg(), trading_windows=["09:00-15:30"])
    assert not any("count provider wired" in r.getMessage() for r in caplog.records)


def test_concurrent_positions_no_warning_when_wired(caplog) -> None:
    """Enabled + wired must not emit the unwired warning (it is active, not inert)."""
    import logging

    cfg = _cfg()
    cfg.concurrent_positions.enabled = True
    with caplog.at_level(logging.WARNING, logger="shared.risk.layer"):
        RiskFilterLayer.from_config(
            cfg,
            trading_windows=["09:00-15:30"],
            open_positions_count_provider=lambda: {},
        )
    assert not any("no count provider wired" in r.getMessage() for r in caplog.records)


def test_concurrent_positions_noop_equivalence() -> None:
    """Inert proof: a layer WITH the enabled filter but NO count provider
    yields the identical LayerResult as a layer WITHOUT the filter."""
    from datetime import UTC, datetime, timedelta

    from shared.decision.signal import Signal
    from shared.risk.state import RiskStateSnapshot

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

    baseline_cfg = _cfg()  # concurrent_positions disabled
    baseline = RiskFilterLayer.from_config(
        baseline_cfg,
        trading_windows=["00:00-23:59"],
        portfolio_snapshot_provider=lambda: None,
    )

    enabled_cfg = _cfg()
    enabled_cfg.concurrent_positions.enabled = True
    enabled_cfg.concurrent_positions.max_total_positions = 1
    enabled_cfg.concurrent_positions.max_positions_per_asset = 1
    with_filter = RiskFilterLayer.from_config(
        enabled_cfg,
        trading_windows=["00:00-23:59"],
        portfolio_snapshot_provider=lambda: None,
        # No count provider injected → the enabled filter fails open.
    )
    assert any(isinstance(f, ConcurrentPositionsFilter) for f in with_filter._filters)

    r_base = baseline.evaluate(sig, state)
    r_with = with_filter.evaluate(sig, state)
    assert r_with.passed == r_base.passed is True
    assert r_with.skip_reason == r_base.skip_reason
    assert r_with.size_multiplier == r_base.size_multiplier


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

    layer = RiskFilterLayer.from_config(
        _cfg(),
        trading_windows=["00:00-23:59"],
        # Hermetic: never let the portfolio filter build a real Redis client.
        portfolio_snapshot_provider=lambda: None,
    )
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
