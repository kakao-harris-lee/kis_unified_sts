"""Test OFICalculator."""
import pytest


def test_ofi_calculator_creation():
    """Test OFICalculator instantiation."""
    from shared.features.ofi import OFICalculator, OFIConfig

    config = OFIConfig()
    calc = OFICalculator(config)

    assert calc.config == config


def test_ofi_calculation_buy_pressure():
    """Test OFI detects buying pressure."""
    from shared.features.ofi import OFICalculator, OFIConfig

    config = OFIConfig(lookback=5)
    calc = OFICalculator(config)

    # Simulate order book with bid depth increasing
    # OFI = sum of (bid_qty_change - ask_qty_change)
    updates = [
        # (best_bid, bid_qty, best_ask, ask_qty)
        (100.0, 100, 100.05, 100),  # Initial
        (100.0, 120, 100.05, 90),   # Bid up, ask down = buying
        (100.0, 140, 100.05, 80),
        (100.0, 160, 100.05, 70),
        (100.0, 180, 100.05, 60),
    ]

    for bid, bid_qty, ask, ask_qty in updates:
        calc.update(bid, bid_qty, ask, ask_qty)

    ofi = calc.get_ofi()

    # OFI should be positive (buying pressure)
    assert ofi > 0


def test_ofi_calculation_sell_pressure():
    """Test OFI detects selling pressure."""
    from shared.features.ofi import OFICalculator, OFIConfig

    config = OFIConfig(lookback=5)
    calc = OFICalculator(config)

    # Simulate order book with ask depth increasing
    updates = [
        (100.0, 100, 100.05, 100),  # Initial
        (100.0, 80, 100.05, 120),   # Bid down, ask up = selling
        (100.0, 60, 100.05, 140),
        (100.0, 40, 100.05, 160),
        (100.0, 20, 100.05, 180),
    ]

    for bid, bid_qty, ask, ask_qty in updates:
        calc.update(bid, bid_qty, ask, ask_qty)

    ofi = calc.get_ofi()

    # OFI should be negative (selling pressure)
    assert ofi < 0


def test_ofi_normalized():
    """Test normalized OFI (z-score)."""
    from shared.features.ofi import OFICalculator, OFIConfig

    config = OFIConfig(lookback=20, min_samples=5)
    calc = OFICalculator(config)

    # Feed small oscillating changes
    for i in range(15):
        # Small random-like changes around baseline
        bid_qty = 100 + (i % 3) * 5
        ask_qty = 100 - (i % 3) * 5
        calc.update(100.0, bid_qty, 100.05, ask_qty)

    # Then strong buy pressure (big bid increase, ask decrease)
    for i in range(5):
        calc.update(100.0, 200 + i * 20, 100.05, 50 - i * 5)

    ofi = calc.get_ofi()

    # OFI should be positive
    assert ofi > 0


def test_ofi_signal_detection():
    """Test OFI signal detection - basic buy pressure detection."""
    from shared.features.ofi import OFICalculator, OFIConfig

    config = OFIConfig(lookback=10, min_samples=5)
    calc = OFICalculator(config)

    # Feed clear buying pressure pattern
    # Bid quantity increasing, ask quantity decreasing
    for i in range(10):
        bid_qty = 100 + i * 20  # 100 -> 280
        ask_qty = 100 - i * 8   # 100 -> 28
        calc.update(100.0, bid_qty, 100.05, ask_qty)

    ofi = calc.get_ofi()

    # Should have positive OFI (buying pressure)
    assert ofi > 0


def test_ofi_liquidity_score():
    """Test liquidity scoring."""
    from shared.features.ofi import OFICalculator, OFIConfig

    config = OFIConfig()
    calc = OFICalculator(config)

    # Update with liquidity info
    calc.update(100.0, 100, 100.05, 100)

    score = calc.get_liquidity_score(
        spread=0.05,
        bid_depth=100,
        ask_depth=100,
        avg_spread=0.10,
        avg_depth=50
    )

    # Good liquidity (tight spread, deep book)
    assert score > 0.5
