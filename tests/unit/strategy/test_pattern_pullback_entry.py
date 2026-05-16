"""Unit tests for PatternPullbackEntry."""

from __future__ import annotations

from datetime import datetime

import pytest

from shared.strategy.base import EntryContext
from shared.strategy.entry.pattern_pullback import (
    PatternPullbackConfig,
    PatternPullbackEntry,
)


def _context(
    *,
    close: float = 70_000.0,
    sma_200: float = 65_000.0,
    sma_20: float = 71_000.0,
    sma_60: float = 68_000.0,
    sma_60_prev: float = 67_000.0,
    rsi_5: float = 35.0,
    atr: float = 1_800.0,
    volume_ratio: float = 1.6,
    highest_high: float = 72_000.0,
    daily_closes: list[float] | None = None,
) -> EntryContext:
    if daily_closes is None:
        daily_closes = [65_000.0] * 61 + [close]
    return EntryContext(
        market_data={"code": "005930", "name": "삼성전자", "close": close},
        indicators={
            "sma_200": sma_200,
            "sma_20": sma_20,
            "sma_60": sma_60,
            "sma_60_prev": sma_60_prev,
            "rsi_5": rsi_5,
            "atr": atr,
            "volume_ratio": volume_ratio,
            "highest_high": highest_high,
            "daily_closes": daily_closes,
        },
        timestamp=datetime(2026, 5, 15),
    )


def _entry(patterns: list[dict]) -> PatternPullbackEntry:
    return PatternPullbackEntry(
        PatternPullbackConfig(
            signal_cooldown_days=0,
            entry_sort="rsi5_asc",
            patterns=patterns,
        )
    )


@pytest.mark.asyncio
async def test_pullback_reversal_emits_ranked_signal() -> None:
    entry = _entry(
        [
            {
                "name": "pullback_reversal",
                "rsi5_max": 45,
                "min_atr_pct": 0.02,
                "min_highest_high_gap_pct": -0.05,
                "require_mid_trend": True,
            }
        ]
    )

    signal = await entry.generate(_context())

    assert signal is not None
    assert signal.strategy == "pattern_pullback"
    assert signal.metadata["signal_direction"] == "long"
    assert signal.metadata["pattern_name"] == "pullback_reversal"
    assert signal.metadata["entry_priority"] == pytest.approx(35.0)
    assert signal.metadata["atr_pct"] == pytest.approx(1_800 / 70_000)


@pytest.mark.asyncio
async def test_volume_pullback_requires_volume_and_return_gate() -> None:
    entry = _entry(
        [
            {
                "name": "volume_pullback",
                "rsi5_max": 50,
                "min_volume_ratio": 1.5,
                "max_return_60d": 0.05,
                "min_atr_pct": 0.03,
            }
        ]
    )
    accepted_closes = [69_000.0] * 61 + [70_000.0]
    rejected_closes = [60_000.0] * 61 + [70_000.0]

    assert (
        await entry.generate(
            _context(atr=2_200.0, volume_ratio=1.6, daily_closes=accepted_closes)
        )
    ) is not None
    assert (
        await entry.generate(
            _context(atr=2_200.0, volume_ratio=1.4, daily_closes=accepted_closes)
        )
    ) is None
    assert (
        await entry.generate(
            _context(atr=2_200.0, volume_ratio=1.6, daily_closes=rejected_closes)
        )
    ) is None


@pytest.mark.asyncio
async def test_common_trend_gates_block_invalid_pullbacks() -> None:
    entry = _entry(
        [
            {
                "name": "pullback_reversal",
                "rsi5_max": 45,
                "min_atr_pct": 0.02,
                "require_mid_trend": True,
            }
        ]
    )

    assert await entry.generate(_context(close=64_000.0, sma_200=65_000.0)) is None
    assert await entry.generate(_context(close=72_000.0, sma_20=71_000.0)) is None


@pytest.mark.asyncio
async def test_mid_trend_filter_is_pattern_specific() -> None:
    volume_entry = _entry(
        [
            {
                "name": "volume_pullback",
                "rsi5_max": 50,
                "min_volume_ratio": 1.5,
                "min_atr_pct": 0.03,
            }
        ]
    )
    reversal_entry = _entry(
        [
            {
                "name": "pullback_reversal",
                "rsi5_max": 45,
                "min_atr_pct": 0.02,
                "require_mid_trend": True,
            }
        ]
    )
    context = _context(
        atr=2_200.0,
        volume_ratio=1.6,
        sma_60=67_000.0,
        sma_60_prev=68_000.0,
    )

    assert await volume_entry.generate(context) is not None
    assert await reversal_entry.generate(context) is None


@pytest.mark.asyncio
async def test_config_from_dict_accepts_nested_patterns_and_aliases() -> None:
    config = PatternPullbackConfig.from_dict(
        {
            "entry_sort": "atr_pct_desc",
            "patterns": [
                {
                    "name": "scan_alias",
                    "rsi5_max": 40,
                    "atr_pct_min": 0.02,
                    "highest_high_gap_min": -0.05,
                    "sma60_rising": True,
                }
            ],
            "unknown_field": "ignored",
        }
    )
    entry = PatternPullbackEntry(config)

    signal = await entry.generate(_context(rsi_5=38.0))

    assert config.entry_sort == "atr_pct_desc"
    assert config.patterns[0]["name"] == "scan_alias"
    assert signal is not None
    assert signal.metadata["entry_priority"] == pytest.approx(-(1_800 / 70_000))


def test_registry_and_factory_create_pattern_pullback() -> None:
    from shared.strategy.registry import (
        EntryRegistry,
        ExitRegistry,
        SizerRegistry,
        StrategyFactory,
        register_builtin_components,
    )

    saved_entries = dict(EntryRegistry._components)
    saved_exits = dict(ExitRegistry._components)
    saved_sizers = dict(SizerRegistry._components)
    EntryRegistry.clear()
    ExitRegistry.clear()
    SizerRegistry.clear()
    try:
        register_builtin_components()
        assert EntryRegistry.is_registered("pattern_pullback")
        strategy = StrategyFactory.create_from_file("stock", "pattern_pullback")
        assert strategy.name == "pattern_pullback"
        assert strategy.entry.name == "pattern_pullback"
        assert strategy.exit.name == "chandelier_exit"
    finally:
        EntryRegistry._components.clear()
        EntryRegistry._components.update(saved_entries)
        ExitRegistry._components.clear()
        ExitRegistry._components.update(saved_exits)
        SizerRegistry._components.clear()
        SizerRegistry._components.update(saved_sizers)
