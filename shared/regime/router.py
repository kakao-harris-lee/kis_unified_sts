"""Strategy router based on market regime."""
import logging

from .models import RegimeSignal, RegimeState

logger = logging.getLogger(__name__)


class StrategyRouter:
    """Route to appropriate strategy based on market regime.

    Features:
    - Map regimes to strategies
    - Default strategy fallback
    - Strategy activation tracking
    """

    def __init__(self, default_strategy: str | None = None):
        self.default_strategy = default_strategy
        self._regime_map: dict[RegimeState, str] = {}
        self._current_strategy: str | None = None

    def register(self, strategy_name: str, regimes: list[RegimeState]) -> None:
        """Register strategy for given regimes."""
        for regime in regimes:
            self._regime_map[regime] = strategy_name
            logger.debug(f"Registered {strategy_name} for {regime.value}")

    def get_strategy(self, state: RegimeState) -> str | None:
        """Get strategy for given regime state."""
        strategy = self._regime_map.get(state, self.default_strategy)
        return strategy

    def update(self, signal: RegimeSignal) -> str | None:
        """Update router with new regime signal.

        Returns:
            New strategy name if changed, None otherwise
        """
        if not signal.is_confident:
            # Keep current strategy if signal not confident
            return None

        new_strategy = self.get_strategy(signal.state)

        if new_strategy != self._current_strategy:
            old_strategy = self._current_strategy
            self._current_strategy = new_strategy
            logger.info(
                f"Strategy switch: {old_strategy} -> {new_strategy} "
                f"(regime: {signal.state.value}, confidence: {signal.confidence:.2f})"
            )
            return new_strategy

        return None

    @property
    def current_strategy(self) -> str | None:
        """Get current active strategy."""
        return self._current_strategy

    def get_routing_table(self) -> dict[str, str]:
        """Get regime to strategy mapping."""
        return {k.value: v for k, v in self._regime_map.items()}
