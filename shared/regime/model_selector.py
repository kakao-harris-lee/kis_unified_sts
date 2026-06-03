"""Adaptive model selector based on market regime.

Maps detected regimes to optimal RL models or strategy profiles,
with cooldown logic to prevent thrashing.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Union

from .adaptive_detector import AdaptiveRegimeState
from .models import RegimeSignal, RegimeState

logger = logging.getLogger(__name__)


@dataclass
class ModelSwitchingConfig:
    """Configuration for model switching behavior.

    Prevents thrashing by requiring:
    1. Minimum confidence threshold
    2. Time-based cooldown between switches
    3. Consecutive regime detections before switching
    """
    min_confidence: float = 0.7
    cooldown_minutes: int = 60
    min_consecutive_detections: int = 3


@dataclass
class ModelMapping:
    """Model mapping entry supporting both direct paths and strategy profiles.

    Attributes:
        model_path: Direct path to model file (e.g., 'models/futures/rl/mppo_best.zip')
        strategy_profile: Strategy profile name (e.g., 'rl_mppo_profile_balanced')

    Note: Exactly one of model_path or strategy_profile must be specified.
    """
    model_path: Optional[str] = None
    strategy_profile: Optional[str] = None

    def __post_init__(self):
        """Validate that exactly one mapping type is specified."""
        if not self.model_path and not self.strategy_profile:
            raise ValueError("Either model_path or strategy_profile must be specified")
        if self.model_path and self.strategy_profile:
            raise ValueError("Cannot specify both model_path and strategy_profile")

    @property
    def target(self) -> str:
        """Get the target model or profile."""
        return self.model_path or self.strategy_profile or ""

    @property
    def mapping_type(self) -> str:
        """Get the mapping type (model_path or strategy_profile)."""
        return "model_path" if self.model_path else "strategy_profile"


class AdaptiveModelSelector:
    """Select optimal model/profile based on detected market regime.

    Features:
    - Map regimes to models or strategy profiles
    - Switching cooldown to prevent thrashing
    - Consecutive detection requirement
    - Confidence threshold filtering
    - Default model fallback

    Usage:
        selector = AdaptiveModelSelector(
            default_model=ModelMapping(strategy_profile='rl_mppo_profile_balanced'),
            switching_config=ModelSwitchingConfig(cooldown_minutes=60)
        )

        # Register regime-to-model mappings
        selector.register(
            AdaptiveRegimeState.TRENDING_BULL,
            ModelMapping(strategy_profile='rl_mppo_profile_balanced')
        )
        selector.register(
            AdaptiveRegimeState.TRENDING_BEAR,
            ModelMapping(strategy_profile='rl_mppo_profile_pnl')
        )

        # Update with new regime signal
        signal = detector.detect(df)
        new_model = selector.update(signal)

        if new_model:
            print(f"Switching to: {new_model.target} ({new_model.mapping_type})")
    """

    def __init__(
        self,
        default_model: Optional[ModelMapping] = None,
        switching_config: Optional[ModelSwitchingConfig] = None,
    ):
        """Initialize model selector.

        Args:
            default_model: Fallback model when regime is UNKNOWN or low confidence
            switching_config: Switching behavior configuration
        """
        self.default_model = default_model
        self.switching_config = switching_config or ModelSwitchingConfig()

        self._regime_map: Dict[Union[RegimeState, AdaptiveRegimeState], ModelMapping] = {}
        self._current_model: Optional[ModelMapping] = None
        self._current_regime: Optional[Union[RegimeState, AdaptiveRegimeState]] = None

        # Switching cooldown tracking
        self._last_switch_time: Optional[datetime] = None
        self._consecutive_detections: int = 0
        self._last_detected_regime: Optional[Union[RegimeState, AdaptiveRegimeState]] = None

    def register(
        self,
        regime: Union[RegimeState, AdaptiveRegimeState],
        model: ModelMapping,
    ) -> None:
        """Register model for given regime.

        Args:
            regime: Regime state (basic or adaptive)
            model: Model mapping (path or profile)
        """
        self._regime_map[regime] = model
        logger.debug(
            f"Registered {model.target} ({model.mapping_type}) for {regime.value}"
        )

    def register_batch(
        self,
        mappings: Dict[Union[RegimeState, AdaptiveRegimeState], ModelMapping],
    ) -> None:
        """Register multiple regime-to-model mappings.

        Args:
            mappings: Dictionary of regime to model mappings
        """
        for regime, model in mappings.items():
            self.register(regime, model)

    def get_model(
        self,
        regime: Union[RegimeState, AdaptiveRegimeState],
    ) -> Optional[ModelMapping]:
        """Get model for given regime.

        Args:
            regime: Regime state

        Returns:
            Model mapping or default model if not found
        """
        return self._regime_map.get(regime, self.default_model)

    def update(self, signal: RegimeSignal) -> Optional[ModelMapping]:
        """Update selector with new regime signal.

        Implements switching logic:
        1. Check confidence threshold
        2. Check cooldown period
        3. Check consecutive detections
        4. Switch model if all conditions met

        Args:
            signal: Regime detection signal

        Returns:
            New model mapping if switched, None otherwise
        """
        # 1. Check confidence threshold
        if signal.confidence < self.switching_config.min_confidence:
            logger.debug(
                f"Regime signal confidence too low: {signal.confidence:.2f} < "
                f"{self.switching_config.min_confidence}"
            )
            # Reset consecutive counter on low confidence
            self._consecutive_detections = 0
            self._last_detected_regime = None
            return None

        # 2. Check cooldown period
        if self._last_switch_time:
            cooldown = timedelta(minutes=self.switching_config.cooldown_minutes)
            time_since_switch = datetime.now() - self._last_switch_time

            if time_since_switch < cooldown:
                remaining = (cooldown - time_since_switch).total_seconds() / 60
                logger.debug(
                    f"Model switching in cooldown: {remaining:.1f} minutes remaining"
                )
                return None

        # 3. Track consecutive detections
        if signal.state == self._last_detected_regime:
            self._consecutive_detections += 1
        else:
            self._consecutive_detections = 1
            self._last_detected_regime = signal.state

        # 4. Check consecutive detection requirement
        if self._consecutive_detections < self.switching_config.min_consecutive_detections:
            logger.debug(
                f"Regime {signal.state.value} detected {self._consecutive_detections}/"
                f"{self.switching_config.min_consecutive_detections} times "
                f"(confidence: {signal.confidence:.2f})"
            )
            return None

        # 5. Get model for detected regime
        new_model = self.get_model(signal.state)

        if not new_model:
            logger.warning(
                f"No model registered for regime {signal.state.value}, "
                f"using default: {self.default_model.target if self.default_model else 'None'}"
            )
            new_model = self.default_model

        # 6. Check if model changed
        if new_model and new_model != self._current_model:
            old_model = self._current_model
            old_regime = self._current_regime

            self._current_model = new_model
            self._current_regime = signal.state
            self._last_switch_time = datetime.now()

            logger.info(
                f"Model switch: "
                f"{old_model.target if old_model else 'None'} "
                f"({old_model.mapping_type if old_model else 'N/A'}) -> "
                f"{new_model.target} ({new_model.mapping_type}) | "
                f"Regime: {old_regime.value if old_regime else 'None'} -> "
                f"{signal.state.value} | "
                f"Confidence: {signal.confidence:.2f} | "
                f"Consecutive: {self._consecutive_detections}"
            )

            return new_model

        return None

    @property
    def current_model(self) -> Optional[ModelMapping]:
        """Get current active model mapping."""
        return self._current_model

    @property
    def current_regime(self) -> Optional[Union[RegimeState, AdaptiveRegimeState]]:
        """Get current regime state."""
        return self._current_regime

    @property
    def consecutive_detections(self) -> int:
        """Get consecutive detection count for current regime."""
        return self._consecutive_detections

    @property
    def time_since_last_switch(self) -> Optional[timedelta]:
        """Get time elapsed since last model switch."""
        if not self._last_switch_time:
            return None
        return datetime.now() - self._last_switch_time

    def get_routing_table(self) -> Dict[str, Dict[str, str]]:
        """Get regime to model mapping table.

        Returns:
            Dictionary mapping regime values to model info
        """
        return {
            regime.value: {
                "target": model.target,
                "type": model.mapping_type,
            }
            for regime, model in self._regime_map.items()
        }

    def get_status(self) -> Dict[str, any]:
        """Get current selector status.

        Returns:
            Status dictionary with current state
        """
        return {
            "current_regime": self._current_regime.value if self._current_regime else None,
            "current_model": self._current_model.target if self._current_model else None,
            "current_model_type": self._current_model.mapping_type if self._current_model else None,
            "consecutive_detections": self._consecutive_detections,
            "last_detected_regime": self._last_detected_regime.value if self._last_detected_regime else None,
            "time_since_last_switch_minutes": (
                self.time_since_last_switch.total_seconds() / 60
                if self.time_since_last_switch else None
            ),
            "cooldown_minutes": self.switching_config.cooldown_minutes,
            "min_confidence": self.switching_config.min_confidence,
            "min_consecutive": self.switching_config.min_consecutive_detections,
            "registered_regimes": list(self._regime_map.keys()),
        }
