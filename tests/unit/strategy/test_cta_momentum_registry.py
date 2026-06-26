"""Registry + factory integration for the CTA daily momentum strategy.

Confirms the entry/exit/sizer register through ``register_builtin_components``
and that ``StrategyFactory`` builds the full strategy from the shipped YAML with
no phantom indicator requirements (the daily-cadence footgun).
"""

from __future__ import annotations

from shared.strategy.entry.cta_momentum import CTAMomentumEntry
from shared.strategy.exit.cta_momentum_exit import CTAMomentumExit
from shared.strategy.position.sizers import VolatilityTargetFuturesSizer
from shared.strategy.registry import (
    EntryRegistry,
    ExitRegistry,
    SizerRegistry,
    StrategyFactory,
    register_builtin_components,
)


def test_builtin_registration():
    register_builtin_components()
    assert EntryRegistry.get("cta_momentum") is CTAMomentumEntry
    assert ExitRegistry.get("cta_momentum_exit") is CTAMomentumExit
    assert (
        SizerRegistry.get("volatility_target_futures") is VolatilityTargetFuturesSizer
    )


def test_factory_builds_full_strategy():
    register_builtin_components()
    config = {
        "strategy": {
            "name": "cta_momentum",
            "entry": {"type": "cta_momentum", "params": {"momentum_lookback": 60}},
            "exit": {"type": "cta_momentum_exit", "params": {"max_holding_days": 60}},
            "position": {
                "type": "volatility_target_futures",
                "params": {"target_annual_vol": 0.15, "point_value_krw": 50000},
            },
        }
    }
    strat = StrategyFactory.create(config)
    assert strat.entry.name == "cta_momentum"
    assert strat.exit.name == "cta_momentum_exit"
    assert isinstance(strat.position_sizer, VolatilityTargetFuturesSizer)
    # Daily-cadence strategy must request no indicator packs.
    assert strat.required_indicators == []
