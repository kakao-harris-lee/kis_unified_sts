"""Test AnomalyDetector."""
from datetime import datetime, timedelta


def test_detect_price_outlier():
    """Test detection of price outliers."""
    from shared.monitoring.anomaly import AnomalyDetector, AnomalyConfig

    # Use smaller min_samples and window for testing
    config = AnomalyConfig(min_samples=5, outlier_std_threshold=2.0)
    detector = AnomalyDetector(config)

    # Create stable prices followed by an outlier
    # 25 normal values (100-102 range), then spike at index 25
    prices = [100 + (i % 3) for i in range(25)] + [500]  # 500 is outlier

    anomalies = detector.detect_outliers(prices, window=10)

    assert len(anomalies) == 1
    assert anomalies[0]["index"] == 25
    assert anomalies[0]["value"] == 500


def test_detect_data_gap():
    """Test detection of data gaps."""
    from shared.monitoring.anomaly import AnomalyDetector

    detector = AnomalyDetector()

    # Timestamps with a gap
    now = datetime.now()
    timestamps = [
        now - timedelta(minutes=5),
        now - timedelta(minutes=4),
        now - timedelta(minutes=3),
        # Gap here (missing minute 2)
        now - timedelta(minutes=0),
    ]

    gaps = detector.detect_gaps(timestamps, expected_interval_seconds=60)

    assert len(gaps) >= 1
