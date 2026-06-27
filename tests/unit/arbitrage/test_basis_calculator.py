"""Test BasisCalculator."""
import pytest


def test_fair_value_calculation():
    """Test fair value formula."""
    from shared.arbitrage.basis_calculator import BasisCalculator
    from shared.arbitrage.config import ArbitrageConfig

    config = ArbitrageConfig(risk_free_rate=0.035)
    calc = BasisCalculator(config)

    # spot * (1 + r * T/365)
    # 330 * (1 + 0.035 * 30/365) = 330 * 1.00288 = 330.95
    fair_value = calc.calculate_fair_value(330.0, days_to_expiry=30)

    assert fair_value == pytest.approx(330.95, rel=0.01)


def test_basis_update():
    """Test basis calculation update."""
    from shared.arbitrage.basis_calculator import BasisCalculator
    from shared.arbitrage.config import ArbitrageConfig

    config = ArbitrageConfig()
    calc = BasisCalculator(config)

    # Update with sample data
    data = calc.update(
        spot_index=330.0,
        futures_price=331.5,
        days_to_expiry=30,
        timestamp=1705300800.0
    )

    assert data.spot_index == 330.0
    assert data.futures_price == 331.5
    assert data.basis > 0  # Futures above fair value


def test_zscore_after_warmup():
    """Test z-score calculation after warmup."""
    import random

    from shared.arbitrage.basis_calculator import BasisCalculator
    from shared.arbitrage.config import ArbitrageConfig

    config = ArbitrageConfig(min_samples=10)
    calc = BasisCalculator(config)

    # Warmup with 20 samples
    for i in range(20):
        calc.update(
            spot_index=330.0 + random.random() * 0.1,
            futures_price=331.0 + random.random() * 0.1,
            days_to_expiry=30,
            timestamp=1705300800.0 + i
        )

    assert calc.is_ready()

    # Add extreme value
    data = calc.update(
        spot_index=330.0,
        futures_price=335.0,  # Big deviation
        days_to_expiry=30
    )

    assert abs(data.basis_zscore) > 1.0  # Should be significant
