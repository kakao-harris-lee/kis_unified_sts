"""Unit tests for RLMPPOEntry."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pytest

from shared.strategy.base import EntryContext
from shared.strategy.entry.rl_mppo import RLMPPOConfig, RLMPPOEntry
from shared.strategy.rl_model_helpers import derive_features_from_ohlcv


def test_build_observation_has_expected_shape():
    strategy = RLMPPOEntry(RLMPPOConfig())
    strategy._get_env_config = lambda: SimpleNamespace(
        max_contracts=1,
        initial_balance=100_000_000,
        market_open="09:00",
        market_close="15:45",
    )
    context = EntryContext(
        market_data={"close": 100.0},
        indicators={},
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 0, 0),
    )
    obs = strategy._build_observation(context)
    assert obs.shape == (31,)


def test_default_config_disables_hold_override():
    assert RLMPPOConfig().enable_hold_override is False


@pytest.mark.asyncio
async def test_generate_short_signal_sets_signal_direction(monkeypatch):
    strategy = RLMPPOEntry(RLMPPOConfig(min_confidence=0.5))
    strategy._is_trading_time = lambda _ts, **_kwargs: True
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (2, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_confidence",
        lambda *_args, **_kwargs: 0.9,
    )

    context = EntryContext(
        market_data={
            "code": "A01603",
            "name": "KOSPI200 Futures",
            "close": 101.5,
        },
        indicators={},
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 5, 0),
    )

    signal = await strategy.generate(context)
    assert signal is not None
    assert signal.metadata.get("signal_direction") == "short"
    assert signal.metadata.get("direction") == "short"


@pytest.mark.asyncio
async def test_generate_skips_time_filter_in_backtest_by_default(monkeypatch):
    strategy = RLMPPOEntry(RLMPPOConfig(min_confidence=0.5))
    strategy._is_trading_time = lambda _ts, **_kwargs: False
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (0, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_confidence",
        lambda *_args, **_kwargs: 0.9,
    )

    context = EntryContext(
        market_data={"code": "A01603", "name": "KOSPI200 Futures", "close": 101.5},
        indicators={},
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 3, 0, 0),
        metadata={"is_backtest": True},
    )

    signal = await strategy.generate(context)
    assert signal is not None


@pytest.mark.asyncio
async def test_generate_applies_time_filter_when_enabled_in_backtest(monkeypatch):
    strategy = RLMPPOEntry(
        RLMPPOConfig(min_confidence=0.5, apply_time_filter_in_backtest=True)
    )
    strategy._is_trading_time = lambda _ts, **_kwargs: False
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (0, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_confidence",
        lambda *_args, **_kwargs: 0.9,
    )

    context = EntryContext(
        market_data={"code": "A01603", "name": "KOSPI200 Futures", "close": 101.5},
        indicators={},
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 3, 0, 0),
        metadata={"is_backtest": True},
    )

    signal = await strategy.generate(context)
    assert signal is None


def test_is_trading_time_with_night_session():
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            day_session_enabled=False,
            night_session_enabled=True,
            night_market_open="18:00",
            night_market_close="05:00",
            skip_market_open_minutes=5,
            skip_market_close_minutes=30,
        )
    )

    assert strategy._is_trading_time(datetime(2026, 2, 12, 18, 4, 0)) is False
    assert strategy._is_trading_time(datetime(2026, 2, 12, 18, 5, 0)) is True
    assert strategy._is_trading_time(datetime(2026, 2, 13, 4, 29, 0)) is True
    assert strategy._is_trading_time(datetime(2026, 2, 13, 4, 31, 0)) is False


def test_is_trading_time_hard_eod_block_applies_in_paper():
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            day_session_enabled=True,
            day_market_open="09:00",
            day_market_close="15:45",
            skip_market_open_minutes=0,
            skip_market_close_minutes=0,
            paper_skip_market_close_minutes=0,
            eod_hard_block_minutes=0,
            paper_eod_hard_block_minutes=10,
            night_session_enabled=False,
        )
    )

    # 11 minutes to close -> allowed
    assert (
        strategy._is_trading_time(datetime(2026, 2, 12, 15, 34, 0), is_paper=True)
        is True
    )
    # 10 minutes to close -> blocked by hard gate
    assert (
        strategy._is_trading_time(datetime(2026, 2, 12, 15, 35, 0), is_paper=True)
        is False
    )
    # live/backtest path unaffected by paper hard gate in this config
    assert (
        strategy._is_trading_time(datetime(2026, 2, 12, 15, 35, 0), is_paper=False)
        is True
    )


def test_is_trading_time_skip_close_boundary_is_exclusive_in_paper():
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            day_session_enabled=True,
            day_market_open="09:00",
            day_market_close="15:45",
            skip_market_open_minutes=0,
            skip_market_close_minutes=0,
            paper_skip_market_close_minutes=30,
            eod_hard_block_minutes=0,
            paper_eod_hard_block_minutes=0,
            night_session_enabled=False,
        )
    )

    assert (
        strategy._is_trading_time(datetime(2026, 2, 12, 15, 14, 0), is_paper=True)
        is True
    )
    assert (
        strategy._is_trading_time(datetime(2026, 2, 12, 15, 15, 0), is_paper=True)
        is False
    )


@pytest.mark.asyncio
async def test_generate_overrides_hold_to_entry_when_gap_small(monkeypatch):
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            min_confidence=0.3,
            enable_hold_override=True,
            hold_override_max_gap=0.1,
            hold_override_min_entry_prob=0.33,
        )
    )
    strategy._is_trading_time = lambda _ts, **_kwargs: True
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (4, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_probabilities",
        lambda *_args, **_kwargs: {0: 0.40, 2: 0.40, 4: 0.20},
    )

    context = EntryContext(
        market_data={
            "code": "A01603",
            "name": "KOSPI200 Futures",
            "close": 101.5,
        },
        indicators={},
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 5, 0),
    )

    signal = await strategy.generate(context)
    assert signal is not None
    assert signal.metadata.get("signal_direction") == "long"
    assert signal.metadata.get("rl_override_reason") == "hold_override"
    assert signal.confidence == pytest.approx(0.40)


@pytest.mark.asyncio
async def test_generate_hold_override_respects_paper_directional_threshold_by_default(
    monkeypatch,
):
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            min_confidence=0.3,
            paper_min_confidence=0.40,
            paper_long_min_confidence=0.42,
            paper_enable_hold_override=True,
            paper_hold_override_max_gap=0.35,
            paper_hold_override_min_entry_prob=0.20,
            paper_hold_override_min_confidence=0.25,
        )
    )
    strategy._is_trading_time = lambda _ts, **_kwargs: True
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (4, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_probabilities",
        lambda *_args, **_kwargs: {0: 0.34, 2: 0.20, 4: 0.36},
    )

    context = EntryContext(
        market_data={
            "code": "A01603",
            "name": "KOSPI200 Futures",
            "close": 101.5,
        },
        indicators={},
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 5, 0),
        metadata={"paper_trading": True},
    )

    signal = await strategy.generate(context)
    assert signal is None


@pytest.mark.asyncio
async def test_generate_hold_override_can_relax_directional_threshold_when_disabled(
    monkeypatch,
):
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            min_confidence=0.3,
            paper_min_confidence=0.40,
            paper_long_min_confidence=0.42,
            paper_enable_hold_override=True,
            paper_hold_override_max_gap=0.35,
            paper_hold_override_min_entry_prob=0.20,
            paper_hold_override_min_confidence=0.25,
            hold_override_respects_directional_thresholds=False,
        )
    )
    strategy._is_trading_time = lambda _ts, **_kwargs: True
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (4, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_probabilities",
        lambda *_args, **_kwargs: {0: 0.34, 2: 0.20, 4: 0.36},
    )

    context = EntryContext(
        market_data={
            "code": "A01603",
            "name": "KOSPI200 Futures",
            "close": 101.5,
        },
        indicators={},
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 5, 0),
        metadata={"paper_trading": True},
    )

    signal = await strategy.generate(context)
    assert signal is not None
    assert signal.metadata.get("rl_override_reason") == "hold_override"


@pytest.mark.asyncio
async def test_generate_keeps_hold_when_gap_large(monkeypatch):
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            min_confidence=0.3,
            enable_hold_override=True,
            hold_override_max_gap=0.05,
            hold_override_min_entry_prob=0.33,
        )
    )
    strategy._is_trading_time = lambda _ts, **_kwargs: True
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (4, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_probabilities",
        lambda *_args, **_kwargs: {0: 0.34, 2: 0.20, 4: 0.46},
    )

    context = EntryContext(
        market_data={
            "code": "A01603",
            "name": "KOSPI200 Futures",
            "close": 101.5,
        },
        indicators={},
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 5, 0),
    )

    signal = await strategy.generate(context)
    assert signal is None


@pytest.mark.asyncio
async def test_generate_adaptive_threshold_blocks_in_high_volatility(monkeypatch):
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            backtest_min_confidence=0.35,
            adaptive_confidence_enabled=True,
            adaptive_confidence_metric="atr_ratio",
            adaptive_confidence_trigger=0.001,
            adaptive_confidence_backtest_boost=0.10,
        )
    )
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (0, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_probabilities",
        lambda *_args, **_kwargs: {0: 0.40, 2: 0.10, 4: 0.50},
    )

    context = EntryContext(
        market_data={"code": "A01603", "name": "KOSPI200 Futures", "close": 1000.0},
        indicators={"atr": 2.0},  # atr_ratio=0.002 (high vol)
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 5, 0),
        metadata={"is_backtest": True},
    )

    signal = await strategy.generate(context)
    assert signal is None


@pytest.mark.asyncio
async def test_generate_adaptive_threshold_keeps_base_in_normal_volatility(monkeypatch):
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            backtest_min_confidence=0.35,
            adaptive_confidence_enabled=True,
            adaptive_confidence_metric="atr_ratio",
            adaptive_confidence_trigger=0.001,
            adaptive_confidence_backtest_boost=0.10,
        )
    )
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (0, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_probabilities",
        lambda *_args, **_kwargs: {0: 0.40, 2: 0.10, 4: 0.50},
    )

    context = EntryContext(
        market_data={"code": "A01603", "name": "KOSPI200 Futures", "close": 1000.0},
        indicators={"atr": 0.5},  # atr_ratio=0.0005 (normal vol)
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 5, 0),
        metadata={"is_backtest": True},
    )

    signal = await strategy.generate(context)
    assert signal is not None
    assert signal.metadata.get("rl_threshold") == pytest.approx(0.35)
    assert str(signal.metadata.get("rl_threshold_reason", "")).startswith(
        "adaptive_normal:"
    )


@pytest.mark.asyncio
async def test_generate_applies_directional_base_threshold(monkeypatch):
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            backtest_min_confidence=0.35,
            backtest_long_min_confidence=0.45,
            backtest_short_min_confidence=0.30,
        )
    )
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (0, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_probabilities",
        lambda *_args, **_kwargs: {0: 0.40, 2: 0.40, 4: 0.20},
    )

    context = EntryContext(
        market_data={"code": "A01603", "name": "KOSPI200 Futures", "close": 1000.0},
        indicators={},
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 5, 0),
        metadata={"is_backtest": True},
    )

    long_signal = await strategy.generate(context)
    assert long_signal is None

    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (2, None)
    )
    short_signal = await strategy.generate(context)
    assert short_signal is not None
    assert short_signal.metadata.get("signal_direction") == "short"
    assert short_signal.metadata.get("rl_threshold") == pytest.approx(0.30)


@pytest.mark.asyncio
async def test_generate_applies_directional_adaptive_boost(monkeypatch):
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            backtest_min_confidence=0.35,
            adaptive_confidence_enabled=True,
            adaptive_confidence_metric="atr_ratio",
            adaptive_confidence_trigger=0.001,
            adaptive_confidence_backtest_boost=0.02,
            adaptive_confidence_backtest_boost_long=0.10,
            adaptive_confidence_backtest_boost_short=0.01,
        )
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_probabilities",
        lambda *_args, **_kwargs: {0: 0.42, 2: 0.42, 4: 0.16},
    )

    context = EntryContext(
        market_data={"code": "A01603", "name": "KOSPI200 Futures", "close": 1000.0},
        indicators={"atr": 2.0},  # atr_ratio=0.002 => high-vol branch
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 5, 0),
        metadata={"is_backtest": True},
    )

    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (0, None)
    )
    long_signal = await strategy.generate(context)
    assert long_signal is None

    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (2, None)
    )
    short_signal = await strategy.generate(context)
    assert short_signal is not None
    assert short_signal.metadata.get("rl_threshold") == pytest.approx(0.36)


@pytest.mark.asyncio
async def test_generate_blocks_long_signal_in_risk_off_drop(monkeypatch):
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            min_confidence=0.3,
            risk_off_long_block_enabled=True,
            risk_off_change_threshold=-0.04,
            risk_off_regime_block_enabled=False,
        )
    )
    strategy._is_trading_time = lambda _ts, **_kwargs: True
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (0, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_probabilities",
        lambda *_args, **_kwargs: {0: 0.75, 2: 0.15, 4: 0.10},
    )

    context = EntryContext(
        market_data={
            "code": "A01603",
            "name": "KOSPI200 Futures",
            "open": 100.0,
            "close": 95.0,  # -5.0%
        },
        indicators={},
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 5, 0),
    )

    signal = await strategy.generate(context)
    assert signal is None


@pytest.mark.asyncio
async def test_generate_allows_short_signal_in_risk_off_drop(monkeypatch):
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            min_confidence=0.3,
            risk_off_long_block_enabled=True,
            risk_off_change_threshold=-0.04,
            risk_off_regime_block_enabled=False,
        )
    )
    strategy._is_trading_time = lambda _ts, **_kwargs: True
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (2, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_probabilities",
        lambda *_args, **_kwargs: {0: 0.05, 2: 0.85, 4: 0.10},
    )

    context = EntryContext(
        market_data={
            "code": "A01603",
            "name": "KOSPI200 Futures",
            "open": 100.0,
            "close": 95.0,  # -5.0%
        },
        indicators={},
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 5, 0),
    )

    signal = await strategy.generate(context)
    assert signal is not None
    assert signal.metadata.get("signal_direction") == "short"
    assert signal.metadata.get("rl_risk_off") is True
    assert "day_change:" in str(signal.metadata.get("rl_risk_off_reason", ""))


@pytest.mark.asyncio
async def test_generate_applies_risk_off_short_threshold_override(monkeypatch):
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            min_confidence=0.6,
            paper_short_min_confidence=0.48,
            risk_off_long_block_enabled=True,
            risk_off_change_threshold=-0.02,
            risk_off_regime_block_enabled=False,
            risk_off_paper_short_min_confidence=0.35,
        )
    )
    strategy._is_trading_time = lambda _ts, **_kwargs: True
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (2, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_probabilities",
        lambda *_args, **_kwargs: {0: 0.20, 2: 0.38, 4: 0.42},
    )

    context = EntryContext(
        market_data={
            "code": "A01603",
            "name": "KOSPI200 Futures",
            "open": 100.0,
            "close": 97.0,  # -3.0%
        },
        indicators={},
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 5, 0),
        metadata={"paper_trading": True},
    )

    signal = await strategy.generate(context)
    assert signal is not None
    assert signal.metadata.get("signal_direction") == "short"
    assert signal.metadata.get("rl_threshold") == pytest.approx(0.35)


@pytest.mark.asyncio
async def test_generate_flips_long_to_short_in_risk_off(monkeypatch):
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            min_confidence=0.3,
            risk_off_long_block_enabled=True,
            risk_off_change_threshold=-0.02,
            risk_off_regime_block_enabled=False,
            risk_off_flip_long_to_short_enabled=True,
            risk_off_flip_min_short_prob=0.30,
        )
    )
    strategy._is_trading_time = lambda _ts, **_kwargs: True
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (0, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_probabilities",
        lambda *_args, **_kwargs: {0: 0.58, 2: 0.36, 4: 0.06},
    )

    context = EntryContext(
        market_data={
            "code": "A01603",
            "name": "KOSPI200 Futures",
            "open": 100.0,
            "close": 97.0,
        },
        indicators={},
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 5, 0),
    )

    signal = await strategy.generate(context)
    assert signal is not None
    assert signal.metadata.get("signal_direction") == "short"
    assert signal.metadata.get("rl_override_reason") == "risk_off_flip_to_short"


@pytest.mark.asyncio
async def test_generate_blocks_long_signal_in_bear_regime(monkeypatch):
    strategy = RLMPPOEntry(
        RLMPPOConfig(
            min_confidence=0.3,
            risk_off_long_block_enabled=True,
            risk_off_change_threshold=-0.10,
            risk_off_regime_block_enabled=True,
            risk_off_regime_keywords=["BEAR"],
        )
    )
    strategy._is_trading_time = lambda _ts, **_kwargs: True
    strategy._load_model = lambda: SimpleNamespace(
        predict=lambda *_args, **_kwargs: (0, None)
    )
    strategy._build_observation = lambda _ctx: np.zeros(31, dtype=np.float32)
    monkeypatch.setattr(
        "shared.strategy.entry.rl_mppo.get_action_probabilities",
        lambda *_args, **_kwargs: {0: 0.70, 2: 0.20, 4: 0.10},
    )

    context = EntryContext(
        market_data={
            "code": "A01603",
            "name": "KOSPI200 Futures",
            "open": 100.0,
            "close": 99.8,
        },
        indicators={},
        current_positions=[],
        timestamp=datetime(2026, 2, 12, 10, 5, 0),
        metadata={"regime": "BEAR"},
    )

    signal = await strategy.generate(context)
    assert signal is None


def test_derive_features_from_ohlcv():
    bars = []
    price = 100.0
    for _ in range(150):
        price += 0.1
        bars.append(
            {
                "open": price - 0.2,
                "high": price + 0.3,
                "low": price - 0.4,
                "close": price,
                "volume": 1000,
            }
        )
    indicators = {}
    market_data = {"ohlcv": bars, "close": price}
    derived = derive_features_from_ohlcv(indicators, market_data)
    assert "rsi" in derived
    assert "macd" in derived
