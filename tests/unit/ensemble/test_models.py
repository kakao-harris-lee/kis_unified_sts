"""Test ensemble filter models."""


def test_filter_result_creation():
    """Test FilterResult dataclass."""
    from shared.ensemble.models import FilterResult

    result = FilterResult(
        timestamp=1705300800.0,
        direction="LONG",
        confidence=0.85,
        dl_probability=0.9,
        ma_aligned=True,
        ichimoku_aligned=True,
        volume_confirmed=True,
    )

    assert result.direction == "LONG"
    assert result.confidence == 0.85
    assert result.is_valid()


def test_filter_result_invalid_without_alignment():
    """Test FilterResult invalid when filters not aligned."""
    from shared.ensemble.models import FilterResult

    result = FilterResult(
        timestamp=1705300800.0,
        direction="LONG",
        confidence=0.7,
        dl_probability=0.8,
        ma_aligned=False,  # Not aligned
        ichimoku_aligned=True,
        volume_confirmed=True,
    )

    assert not result.is_valid()


def test_ensemble_signal_creation():
    """Test EnsembleSignal dataclass."""
    from shared.ensemble.models import EnsembleSignal, FilterResult

    filter_result = FilterResult(
        timestamp=1705300800.0,
        direction="LONG",
        confidence=0.85,
        dl_probability=0.9,
        ma_aligned=True,
        ichimoku_aligned=True,
        volume_confirmed=True,
    )

    signal = EnsembleSignal(
        timestamp=1705300800.0,
        direction="LONG",
        entry_price=330.50,
        stop_loss=328.00,
        take_profit=335.00,
        position_size=5.0,
        filter_result=filter_result,
    )

    assert signal.direction == "LONG"
    assert signal.entry_price == 330.50


def test_horizon_result_creation():
    """Test HorizonResult for multi-horizon confirmation."""
    from shared.ensemble.models import HorizonResult

    result = HorizonResult(
        horizon="5m",
        probability=0.75,
        direction="LONG",
        confirmed=True,
    )

    assert result.horizon == "5m"
    assert result.confirmed is True
