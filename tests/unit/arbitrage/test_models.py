"""Test arbitrage models."""
import pytest


def test_basis_data_creation():
    """Test BasisData dataclass."""
    from shared.arbitrage.models import BasisData

    data = BasisData(
        timestamp=1705300800.0,
        spot_index=330.50,
        futures_price=331.00,
        fair_value=330.75,
        basis=0.25,
        basis_zscore=1.5,
        days_to_expiry=30,
        rolling_mean=0.10,
        rolling_std=0.15,
    )

    assert data.spot_index == 330.50
    assert data.basis_zscore == 1.5


def test_arbitrage_signal_creation():
    """Test ArbitrageSignal dataclass."""
    from shared.arbitrage.models import ArbitrageSignal, BasisData

    basis_data = BasisData(
        timestamp=1705300800.0,
        spot_index=330.50,
        futures_price=331.00,
        fair_value=330.75,
        basis=0.25,
        basis_zscore=2.8,
        days_to_expiry=30,
        rolling_mean=0.10,
        rolling_std=0.15,
    )

    signal = ArbitrageSignal(
        timestamp=1705300800.0,
        direction="SELL",  # Basis too high, sell futures
        basis_zscore=2.8,
        entry_price=331.00,
        order_size=5.0,
        basis_data=basis_data,
    )

    assert signal.direction == "SELL"
    assert signal.basis_zscore > 2.5
