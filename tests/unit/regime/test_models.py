"""Test regime detection models."""
from datetime import datetime


def test_regime_state_enum():
    """Test RegimeState enum."""
    from shared.regime.models import RegimeState

    assert RegimeState.BULL.value == "BULL"
    assert RegimeState.BEAR.value == "BEAR"
    assert RegimeState.SIDEWAYS.value == "SIDEWAYS"


def test_regime_signal_creation():
    """Test RegimeSignal model."""
    from shared.regime.models import RegimeSignal, RegimeState

    signal = RegimeSignal(
        state=RegimeState.BULL,
        confidence=0.85,
        timestamp=datetime.now(),
    )

    assert signal.state == RegimeState.BULL
    assert signal.confidence == 0.85
    assert signal.is_confident  # > 0.7 threshold
