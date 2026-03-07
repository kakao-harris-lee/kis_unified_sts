"""Test AdaptiveModelSelector with regime-to-model mapping."""
import pytest
from datetime import datetime, timedelta

from shared.regime.model_selector import (
    AdaptiveModelSelector,
    ModelMapping,
    ModelSwitchingConfig,
)
from shared.regime.adaptive_detector import AdaptiveRegimeState
from shared.regime.models import RegimeSignal


class TestModelMapping:
    """Test ModelMapping dataclass."""

    def test_model_path_only(self):
        """Model path specified, strategy_profile None"""
        mapping = ModelMapping(model_path="models/test.zip")
        assert mapping.target == "models/test.zip"
        assert mapping.mapping_type == "model_path"

    def test_strategy_profile_only(self):
        """Strategy profile specified, model_path None"""
        mapping = ModelMapping(strategy_profile="test_profile")
        assert mapping.target == "test_profile"
        assert mapping.mapping_type == "strategy_profile"

    def test_both_specified_raises_error(self):
        """Both model_path and strategy_profile raises ValueError"""
        with pytest.raises(ValueError, match="Cannot specify both"):
            ModelMapping(model_path="test.zip", strategy_profile="test")

    def test_neither_specified_raises_error(self):
        """Neither specified raises ValueError"""
        with pytest.raises(ValueError, match="Either model_path or strategy_profile"):
            ModelMapping()


class TestAdaptiveModelSelector:
    """Test suite for AdaptiveModelSelector."""

    @pytest.fixture
    def selector(self):
        """Create selector with test configuration."""
        default = ModelMapping(strategy_profile="default")
        config = ModelSwitchingConfig(
            min_confidence=0.7,
            cooldown_minutes=60,
            min_consecutive_detections=3
        )
        return AdaptiveModelSelector(default_model=default, switching_config=config)

    # 1. Test registration

    def test_register_model_mapping(self, selector):
        """Register regime-to-model mapping"""
        mapping = ModelMapping(strategy_profile="bull_strategy")
        selector.register(AdaptiveRegimeState.TRENDING_BULL, mapping)
        assert selector.get_model(AdaptiveRegimeState.TRENDING_BULL) == mapping

    def test_register_batch(self, selector):
        """Register multiple mappings at once"""
        mappings = {
            AdaptiveRegimeState.TRENDING_BULL: ModelMapping(strategy_profile="bull"),
            AdaptiveRegimeState.TRENDING_BEAR: ModelMapping(strategy_profile="bear"),
        }
        selector.register_batch(mappings)
        assert len(selector.get_routing_table()) >= 2

    def test_get_model_not_registered(self, selector):
        """Get model for unregistered regime returns default"""
        model = selector.get_model(AdaptiveRegimeState.UNKNOWN)
        assert model == selector.default_model

    # 2. Test switching logic

    def test_switching_below_confidence_threshold(self, selector):
        """Low confidence signal → no switch"""
        signal = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BULL,
            confidence=0.5,  # Below 0.7 threshold
            timestamp=datetime.now()
        )
        result = selector.update(signal)
        assert result is None
        assert selector.consecutive_detections == 0

    def test_switching_during_cooldown(self, selector):
        """Switch during cooldown → no switch"""
        # Register mapping
        mapping = ModelMapping(strategy_profile="bull_strategy")
        selector.register(AdaptiveRegimeState.TRENDING_BULL, mapping)

        # First switch
        signal1 = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BULL,
            confidence=0.9,
            timestamp=datetime.now()
        )

        # Simulate 3 consecutive detections
        for _ in range(3):
            selector.update(signal1)

        # Try to switch before cooldown expires
        signal2 = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BEAR,
            confidence=0.9,
            timestamp=datetime.now()
        )

        # Reset consecutive counter (new regime)
        selector.update(signal2)
        selector.update(signal2)
        result = selector.update(signal2)

        # Should be blocked by cooldown
        assert result is None

    def test_switching_insufficient_consecutive(self, selector):
        """Less than min_consecutive → no switch"""
        mapping = ModelMapping(strategy_profile="bull_strategy")
        selector.register(AdaptiveRegimeState.TRENDING_BULL, mapping)

        signal = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BULL,
            confidence=0.9,
            timestamp=datetime.now()
        )

        # First detection
        result = selector.update(signal)
        assert result is None
        assert selector.consecutive_detections == 1

        # Second detection
        result = selector.update(signal)
        assert result is None
        assert selector.consecutive_detections == 2

        # Third detection should trigger switch
        result = selector.update(signal)
        assert result is not None
        assert result == mapping

    def test_switching_success(self, selector):
        """All conditions met → switch succeeds"""
        mapping = ModelMapping(strategy_profile="bull_strategy")
        selector.register(AdaptiveRegimeState.TRENDING_BULL, mapping)

        signal = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BULL,
            confidence=0.9,
            timestamp=datetime.now()
        )

        # Trigger 3 consecutive detections
        for i in range(3):
            result = selector.update(signal)
            if i == 2:
                assert result is not None
                assert result == mapping
                assert selector.current_model == mapping
                assert selector.current_regime == AdaptiveRegimeState.TRENDING_BULL

    # 3. Test fallback behavior

    def test_fallback_to_default(self, selector):
        """No model for regime → use default"""
        signal = RegimeSignal(
            state=AdaptiveRegimeState.UNKNOWN,
            confidence=0.9,
            timestamp=datetime.now()
        )

        # Trigger switch (3 consecutive detections)
        for _ in range(3):
            selector.update(signal)

        model = selector.get_model(AdaptiveRegimeState.UNKNOWN)
        assert model == selector.default_model

    def test_fallback_when_no_default(self):
        """No default model returns None for unregistered regime"""
        selector = AdaptiveModelSelector(default_model=None)

        model = selector.get_model(AdaptiveRegimeState.UNKNOWN)
        assert model is None

    # 4. Test state tracking

    def test_consecutive_detection_reset(self, selector):
        """Regime change → reset consecutive counter"""
        signal1 = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BULL,
            confidence=0.9,
            timestamp=datetime.now()
        )
        selector.update(signal1)
        selector.update(signal1)
        assert selector.consecutive_detections == 2

        # Change regime → counter resets
        signal2 = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BEAR,
            confidence=0.9,
            timestamp=datetime.now()
        )
        selector.update(signal2)

        assert selector.consecutive_detections == 1

    def test_get_status(self, selector):
        """Get selector status"""
        status = selector.get_status()
        assert "current_model" in status
        assert "current_regime" in status
        assert "consecutive_detections" in status
        assert "last_detected_regime" in status
        assert "time_since_last_switch_minutes" in status
        assert "cooldown_minutes" in status
        assert "min_confidence" in status
        assert "min_consecutive" in status
        assert "registered_regimes" in status

    def test_time_since_last_switch(self, selector):
        """Time since last switch calculated correctly"""
        # Initially no switch
        assert selector.time_since_last_switch is None

        # Trigger a switch
        mapping = ModelMapping(strategy_profile="bull_strategy")
        selector.register(AdaptiveRegimeState.TRENDING_BULL, mapping)

        signal = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BULL,
            confidence=0.9,
            timestamp=datetime.now()
        )

        # Trigger 3 consecutive detections
        for _ in range(3):
            selector.update(signal)

        # Should have time since switch
        assert selector.time_since_last_switch is not None
        assert selector.time_since_last_switch < timedelta(seconds=5)

    # 5. Test routing table

    def test_get_routing_table(self, selector):
        """Get regime to model mapping table"""
        mapping1 = ModelMapping(strategy_profile="bull")
        mapping2 = ModelMapping(model_path="models/bear.zip")

        selector.register(AdaptiveRegimeState.TRENDING_BULL, mapping1)
        selector.register(AdaptiveRegimeState.TRENDING_BEAR, mapping2)

        routing_table = selector.get_routing_table()

        assert AdaptiveRegimeState.TRENDING_BULL.value in routing_table
        assert AdaptiveRegimeState.TRENDING_BEAR.value in routing_table
        assert routing_table[AdaptiveRegimeState.TRENDING_BULL.value]["target"] == "bull"
        assert routing_table[AdaptiveRegimeState.TRENDING_BULL.value]["type"] == "strategy_profile"
        assert routing_table[AdaptiveRegimeState.TRENDING_BEAR.value]["target"] == "models/bear.zip"
        assert routing_table[AdaptiveRegimeState.TRENDING_BEAR.value]["type"] == "model_path"

    # 6. Test model change detection

    def test_no_switch_if_same_model(self, selector):
        """No switch if already using the same model"""
        mapping = ModelMapping(strategy_profile="bull_strategy")
        selector.register(AdaptiveRegimeState.TRENDING_BULL, mapping)

        signal = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BULL,
            confidence=0.9,
            timestamp=datetime.now()
        )

        # First switch
        for _ in range(3):
            selector.update(signal)

        # Reset cooldown by manipulating internal state (for testing)
        selector._last_switch_time = datetime.now() - timedelta(hours=2)

        # Try to switch to same model again
        signal2 = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BULL,
            confidence=0.9,
            timestamp=datetime.now()
        )

        # Should not trigger another switch (same model)
        result = selector.update(signal2)
        assert result is None

    # 7. Test current properties

    def test_current_model_property(self, selector):
        """current_model property works correctly"""
        assert selector.current_model is None

        # Trigger a switch
        mapping = ModelMapping(strategy_profile="bull_strategy")
        selector.register(AdaptiveRegimeState.TRENDING_BULL, mapping)

        signal = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BULL,
            confidence=0.9,
            timestamp=datetime.now()
        )

        for _ in range(3):
            selector.update(signal)

        assert selector.current_model == mapping

    def test_current_regime_property(self, selector):
        """current_regime property works correctly"""
        assert selector.current_regime is None

        # Trigger a switch
        mapping = ModelMapping(strategy_profile="bull_strategy")
        selector.register(AdaptiveRegimeState.TRENDING_BULL, mapping)

        signal = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BULL,
            confidence=0.9,
            timestamp=datetime.now()
        )

        for _ in range(3):
            selector.update(signal)

        assert selector.current_regime == AdaptiveRegimeState.TRENDING_BULL

    # 8. Test configuration

    def test_custom_switching_config(self):
        """Custom switching config is respected"""
        config = ModelSwitchingConfig(
            min_confidence=0.8,
            cooldown_minutes=120,
            min_consecutive_detections=5
        )
        selector = AdaptiveModelSelector(switching_config=config)

        assert selector.switching_config.min_confidence == 0.8
        assert selector.switching_config.cooldown_minutes == 120
        assert selector.switching_config.min_consecutive_detections == 5

    def test_default_switching_config(self):
        """Default switching config is used when not specified"""
        selector = AdaptiveModelSelector()

        assert selector.switching_config.min_confidence == 0.7
        assert selector.switching_config.cooldown_minutes == 60
        assert selector.switching_config.min_consecutive_detections == 3

    # 9. Test low confidence resets consecutive counter

    def test_low_confidence_resets_counter(self, selector):
        """Low confidence signal resets consecutive counter"""
        signal_high = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BULL,
            confidence=0.9,
            timestamp=datetime.now()
        )

        # Build up consecutive detections
        selector.update(signal_high)
        selector.update(signal_high)
        assert selector.consecutive_detections == 2

        # Low confidence signal
        signal_low = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BULL,
            confidence=0.5,  # Below threshold
            timestamp=datetime.now()
        )
        selector.update(signal_low)

        # Counter should be reset
        assert selector.consecutive_detections == 0

    # 10. Test cooldown expiration

    def test_cooldown_expiration_allows_switch(self, selector):
        """After cooldown expires, switching is allowed"""
        mapping1 = ModelMapping(strategy_profile="bull_strategy")
        mapping2 = ModelMapping(strategy_profile="bear_strategy")

        selector.register(AdaptiveRegimeState.TRENDING_BULL, mapping1)
        selector.register(AdaptiveRegimeState.TRENDING_BEAR, mapping2)

        # First switch
        signal1 = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BULL,
            confidence=0.9,
            timestamp=datetime.now()
        )

        for _ in range(3):
            selector.update(signal1)

        # Simulate cooldown expiration
        selector._last_switch_time = datetime.now() - timedelta(hours=2)

        # Try to switch after cooldown
        signal2 = RegimeSignal(
            state=AdaptiveRegimeState.TRENDING_BEAR,
            confidence=0.9,
            timestamp=datetime.now()
        )

        # Reset consecutive counter by changing regime
        selector.update(signal2)
        selector.update(signal2)
        result = selector.update(signal2)

        # Should allow switch now (cooldown expired)
        assert result is not None
        assert result == mapping2
