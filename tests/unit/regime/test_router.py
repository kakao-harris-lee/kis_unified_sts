"""Test StrategyRouter."""


def test_router_strategy_selection():
    """Test regime-based strategy selection."""
    from shared.regime.router import StrategyRouter
    from shared.regime.models import RegimeState

    router = StrategyRouter()

    # Register strategies for regimes
    router.register("aggressive", [RegimeState.BULL])
    router.register("defensive", [RegimeState.BEAR])
    router.register("range_bound", [RegimeState.SIDEWAYS])

    assert router.get_strategy(RegimeState.BULL) == "aggressive"
    assert router.get_strategy(RegimeState.BEAR) == "defensive"
    assert router.get_strategy(RegimeState.SIDEWAYS) == "range_bound"


def test_router_default_strategy():
    """Test default strategy fallback."""
    from shared.regime.router import StrategyRouter
    from shared.regime.models import RegimeState

    router = StrategyRouter(default_strategy="balanced")

    # No strategies registered
    assert router.get_strategy(RegimeState.BULL) == "balanced"
