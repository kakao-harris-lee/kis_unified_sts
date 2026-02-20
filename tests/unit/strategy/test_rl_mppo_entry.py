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


@pytest.mark.asyncio
async def test_generate_short_signal_sets_signal_direction(monkeypatch):
    strategy = RLMPPOEntry(RLMPPOConfig(min_confidence=0.5))
    strategy._is_trading_time = lambda _ts: True
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
