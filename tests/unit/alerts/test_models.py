"""Test alert models."""
from datetime import datetime


def test_alert_level_enum():
    """Test AlertLevel enum."""
    from shared.alerts.models import AlertLevel

    assert AlertLevel.INFO.value == "INFO"
    assert AlertLevel.WARNING.value == "WARNING"
    assert AlertLevel.CRITICAL.value == "CRITICAL"


def test_alert_creation():
    """Test Alert model."""
    from shared.alerts.models import Alert, AlertLevel

    alert = Alert(
        level=AlertLevel.WARNING,
        title="High Drawdown",
        message="Portfolio drawdown exceeded 5%",
        timestamp=datetime.now(),
    )

    assert alert.level == AlertLevel.WARNING
    assert "Drawdown" in alert.title
