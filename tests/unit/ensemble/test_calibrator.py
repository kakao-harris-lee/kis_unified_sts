"""Test ProbabilityCalibrator."""


def test_calibrator_creation():
    """Test ProbabilityCalibrator instantiation."""
    from shared.ensemble.calibrator import ProbabilityCalibrator
    from shared.ensemble.config import EnsembleConfig

    config = EnsembleConfig()
    calibrator = ProbabilityCalibrator(config)

    assert calibrator.config == config


def test_calibrator_zscore_normalization():
    """Test z-score based probability normalization."""
    from shared.ensemble.calibrator import ProbabilityCalibrator
    from shared.ensemble.config import EnsembleConfig

    config = EnsembleConfig()
    calibrator = ProbabilityCalibrator(config)

    # Feed historical probabilities (mean ~0.5, std ~0.1)
    for _ in range(50):
        calibrator.update(0.5)
    for _ in range(25):
        calibrator.update(0.4)
    for _ in range(25):
        calibrator.update(0.6)

    # Extreme probability should have high z-score
    z_score = calibrator.get_zscore(0.8)
    assert z_score > 2.0  # More than 2 std from mean

    # Normal probability should have low z-score
    z_score = calibrator.get_zscore(0.5)
    assert abs(z_score) < 0.5


def test_calibrator_calibrated_probability():
    """Test calibrated probability output."""
    import random

    from shared.ensemble.calibrator import ProbabilityCalibrator
    from shared.ensemble.config import EnsembleConfig

    config = EnsembleConfig(calibration_lookback=100)
    calibrator = ProbabilityCalibrator(config)

    # Warmup with varied data (mean ~0.5, std ~0.1)
    random.seed(42)
    for _ in range(100):
        calibrator.update(0.5 + random.gauss(0, 0.1))

    # High raw probability should calibrate higher (above 0.5)
    calibrated = calibrator.calibrate(0.8)
    assert calibrated > 0.5

    # Low raw probability should calibrate lower (below 0.5)
    calibrated = calibrator.calibrate(0.2)
    assert calibrated < 0.5


def test_calibrator_not_ready():
    """Test calibrator before warmup."""
    import random

    from shared.ensemble.calibrator import ProbabilityCalibrator
    from shared.ensemble.config import EnsembleConfig

    config = EnsembleConfig(calibration_lookback=100)
    calibrator = ProbabilityCalibrator(config)

    # Not ready yet
    assert not calibrator.is_ready()

    # Feed some data
    random.seed(42)
    for _ in range(50):
        calibrator.update(0.5 + random.gauss(0, 0.1))

    assert not calibrator.is_ready()

    # Complete warmup
    for _ in range(50):
        calibrator.update(0.5 + random.gauss(0, 0.1))

    assert calibrator.is_ready()
