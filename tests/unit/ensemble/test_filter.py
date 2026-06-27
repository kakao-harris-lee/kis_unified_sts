"""Test EnsembleFilter."""
import pytest


def test_filter_creation():
    """Test EnsembleFilter instantiation."""
    from shared.ensemble.config import EnsembleConfig
    from shared.ensemble.filter import EnsembleFilter

    config = EnsembleConfig()
    filter = EnsembleFilter(config)

    assert filter.config == config


def test_check_long_entry():
    """Test long entry conditions."""
    from shared.ensemble.config import EnsembleConfig
    from shared.ensemble.filter import EnsembleFilter
    from shared.trend.models import TechnicalData

    config = EnsembleConfig(dl_threshold=0.6, min_confidence=0.5)
    filter = EnsembleFilter(config)

    # Bullish technical data
    tech_data = TechnicalData(
        timestamp=1705300800.0,
        close=331.50,     # Price above cloud
        ma_short=331.0,   # Short MA above long MA = bullish
        ma_long=329.0,
        ichimoku_tenkan=331.0,
        ichimoku_kijun=330.0,
        ichimoku_senkou_a=330.5,  # Cloud top = 330.5
        ichimoku_senkou_b=329.5,
        atr=1.5,
    )

    result = filter.check_long(
        dl_probability=0.8,
        technical_data=tech_data,
        volume_ratio=1.5,  # Above average volume
    )

    assert result.direction == "LONG"
    assert result.ma_aligned is True
    assert result.ichimoku_aligned is True
    assert result.is_valid()


def test_check_short_entry():
    """Test short entry conditions."""
    from shared.ensemble.config import EnsembleConfig
    from shared.ensemble.filter import EnsembleFilter
    from shared.trend.models import TechnicalData

    config = EnsembleConfig(dl_threshold=0.6, min_confidence=0.5)
    filter = EnsembleFilter(config)

    # Bearish technical data
    tech_data = TechnicalData(
        timestamp=1705300800.0,
        close=327.50,     # Price below cloud
        ma_short=328.0,   # Short MA below long MA = bearish
        ma_long=330.0,
        ichimoku_tenkan=328.0,
        ichimoku_kijun=329.0,
        ichimoku_senkou_a=328.5,  # Cloud bottom = 328.5
        ichimoku_senkou_b=329.5,
        atr=1.5,
    )

    result = filter.check_short(
        dl_probability=0.75,
        technical_data=tech_data,
        volume_ratio=1.2,
    )

    assert result.direction == "SHORT"
    assert result.ma_aligned is True
    assert result.ichimoku_aligned is True


def test_filter_rejects_misaligned():
    """Test filter rejects when MA not aligned."""
    from shared.ensemble.config import EnsembleConfig
    from shared.ensemble.filter import EnsembleFilter
    from shared.trend.models import TechnicalData

    config = EnsembleConfig()
    filter = EnsembleFilter(config)

    # MA bearish but trying to go long
    tech_data = TechnicalData(
        timestamp=1705300800.0,
        close=330.50,
        ma_short=328.0,   # Short MA BELOW long MA = bearish
        ma_long=332.0,
        ichimoku_tenkan=331.0,
        ichimoku_kijun=330.0,
        ichimoku_senkou_a=330.5,
        ichimoku_senkou_b=329.5,
        atr=1.5,
    )

    result = filter.check_long(
        dl_probability=0.8,
        technical_data=tech_data,
        volume_ratio=1.5,
    )

    assert result.ma_aligned is False
    assert not result.is_valid()


def test_multi_horizon_confirmation():
    """Test multi-horizon confirmation logic."""
    from shared.ensemble.config import EnsembleConfig
    from shared.ensemble.filter import EnsembleFilter
    from shared.ensemble.models import HorizonResult

    config = EnsembleConfig(
        horizons=["1m", "5m", "15m"],
        min_horizons_confirmed=2
    )
    filter = EnsembleFilter(config)

    # All horizons confirm
    horizon_results = [
        HorizonResult(horizon="1m", probability=0.8, direction="LONG", confirmed=True),
        HorizonResult(horizon="5m", probability=0.75, direction="LONG", confirmed=True),
        HorizonResult(horizon="15m", probability=0.7, direction="LONG", confirmed=True),
    ]

    confirmed, confidence = filter.check_multi_horizon(horizon_results, "LONG")
    assert confirmed is True
    assert confidence > 0.7


def test_multi_horizon_fails_without_consensus():
    """Test multi-horizon fails without consensus."""
    from shared.ensemble.config import EnsembleConfig
    from shared.ensemble.filter import EnsembleFilter
    from shared.ensemble.models import HorizonResult

    config = EnsembleConfig(
        horizons=["1m", "5m", "15m"],
        min_horizons_confirmed=2
    )
    filter = EnsembleFilter(config)

    # Only 1 horizon confirms
    horizon_results = [
        HorizonResult(horizon="1m", probability=0.8, direction="LONG", confirmed=True),
        HorizonResult(horizon="5m", probability=0.4, direction="SHORT", confirmed=False),
        HorizonResult(horizon="15m", probability=0.45, direction="SHORT", confirmed=False),
    ]

    confirmed, confidence = filter.check_multi_horizon(horizon_results, "LONG")
    assert confirmed is False


def test_generate_signal():
    """Test signal generation with stop/target calculation."""
    from shared.ensemble.config import EnsembleConfig
    from shared.ensemble.filter import EnsembleFilter
    from shared.trend.models import TechnicalData

    config = EnsembleConfig(
        atr_stop_multiplier=2.0,
        atr_target_multiplier=3.0,
        default_position_size=5.0
    )
    filter = EnsembleFilter(config)

    tech_data = TechnicalData(
        timestamp=1705300800.0,
        close=330.50,
        ma_short=331.0,
        ma_long=329.0,
        ichimoku_tenkan=331.0,
        ichimoku_kijun=330.0,
        ichimoku_senkou_a=330.5,
        ichimoku_senkou_b=329.5,
        atr=1.0,
    )

    signal = filter.generate_signal(
        direction="LONG",
        dl_probability=0.8,
        technical_data=tech_data,
        current_price=330.50,
    )

    assert signal is not None
    assert signal.direction == "LONG"
    assert signal.entry_price == 330.50
    assert signal.stop_loss == pytest.approx(328.50)  # 330.50 - 2*1.0
    assert signal.take_profit == pytest.approx(333.50)  # 330.50 + 3*1.0
    assert signal.position_size == 5.0
