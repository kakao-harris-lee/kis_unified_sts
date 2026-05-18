from shared.config.loader import ConfigLoader
from shared.strategy.registry import (
    StrategyFactory,
    register_builtin_components,
)


def test_bb_reversion_15m_entry_declares_mtf_base_15m():
    register_builtin_components()
    cfg = ConfigLoader.load_strategy("futures", "bb_reversion_15m")
    strat = StrategyFactory.create(cfg)
    assert "mtf_base_15m" in strat.entry.required_indicators
