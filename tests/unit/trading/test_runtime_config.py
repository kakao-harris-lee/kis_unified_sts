"""Runtime configuration ownership and facade compatibility tests."""

from __future__ import annotations

import pytest


def test_runtime_config_owner_matches_orchestrator_facade() -> None:
    from services.trading import orchestrator, runtime_config

    assert runtime_config.TradingConfig is orchestrator.TradingConfig
    assert (
        runtime_config.EntryReentryGuardConfig is orchestrator.EntryReentryGuardConfig
    )
    for name in (
        "MIN_INITIAL_CAPITAL",
        "MAX_INITIAL_CAPITAL",
        "MIN_ORDER_AMOUNT",
        "MAX_ORDER_AMOUNT",
        "REENTRY_GUARD_SCOPES",
    ):
        assert getattr(runtime_config, name) == getattr(orchestrator, name)


def test_stock_factory_preserves_env_driven_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services.trading.runtime_config import TradingConfig

    monkeypatch.setenv("STOCK_REQUIRE_DAILY_INDICATORS_FOR_DYNAMIC_UNIVERSE", "false")
    monkeypatch.setenv("STOCK_INCLUDE_DAILY_WATCHLIST_IN_DYNAMIC_UNIVERSE", "0")
    monkeypatch.setenv("STOCK_REGIME_EXCLUDE_DIP_CANDIDATES", "false")
    monkeypatch.setenv("STOCK_REGIME_MIN_MFI_SYMBOLS", "4")
    monkeypatch.setenv("STOCK_REGIME_MIN_MFI_COVERAGE_RATIO", "0.25")
    monkeypatch.setenv("STOCK_REGIME_LOW_CONFIDENCE_BEAR_FALLBACK", "SIDEWAYS_FLAT")

    config = TradingConfig.stock(strategy_name="opening_volume_surge")

    assert config.asset_class == "stock"
    assert config.strategy_name == "opening_volume_surge"
    assert config.symbols == []
    assert config.market_data_refresh_seconds == 2.0
    assert config.require_daily_indicators_for_dynamic_universe is False
    assert config.include_daily_watchlist_in_dynamic_universe is False
    assert config.regime_exclude_dip_candidates is False
    assert config.regime_min_mfi_symbols == 4
    assert config.regime_min_mfi_coverage_ratio == 0.25
    assert config.regime_low_confidence_bear_fallback == "SIDEWAYS_FLAT"


def test_futures_factory_preserves_explicit_symbols_and_alert_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services.trading.runtime_config import TradingConfig

    monkeypatch.setenv("TELEGRAM_FUTURES_BOT_TOKEN", "futures-token")
    monkeypatch.setenv("TELEGRAM_FUTURES_CHAT_ID", "futures-chat")

    config = TradingConfig.futures(
        strategy_name="setup_c_event_reaction",
        initial_capital=50_000_000,
        order_amount=2_000_000,
        symbols=["A05TEST"],
    )

    assert config.asset_class == "futures"
    assert config.strategy_name == "setup_c_event_reaction"
    assert config.initial_capital == 50_000_000
    assert config.order_amount_per_trade == 2_000_000
    assert config.symbols == ["A05TEST"]
    assert config.telegram_token == "futures-token"
    assert config.telegram_chat_id == "futures-chat"


def test_entry_reentry_guard_config_preserves_reason_normalization() -> None:
    from services.trading.runtime_config import EntryReentryGuardConfig

    config = EntryReentryGuardConfig.from_dict(
        {
            "enabled": True,
            "scope": "symbol",
            "default_cooldown_seconds": 120,
            "reason_cooldown_seconds": {"STOP_LOSS": 600},
        }
    )

    assert config.enabled is True
    assert config.scope == "symbol"
    assert config.cooldown_for("stop_loss") == 600
    assert config.cooldown_for("momentum_decay") == 120


def test_runtime_config_validation_boundaries_are_preserved() -> None:
    from services.trading.runtime_config import (
        MAX_ORDER_AMOUNT,
        MIN_INITIAL_CAPITAL,
        TradingConfig,
    )

    with pytest.raises(ValueError, match="initial_capital must be between"):
        TradingConfig(initial_capital=MIN_INITIAL_CAPITAL - 1)

    with pytest.raises(ValueError, match="order_amount_per_trade must be between"):
        TradingConfig(order_amount_per_trade=MAX_ORDER_AMOUNT + 1)
