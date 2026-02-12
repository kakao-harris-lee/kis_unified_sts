"""Test ArbitrageEngine."""


def test_engine_creation():
    """Test ArbitrageEngine instantiation."""
    from shared.arbitrage.engine import ArbitrageEngine
    from shared.arbitrage.config import ArbitrageConfig

    config = ArbitrageConfig()
    engine = ArbitrageEngine(config)

    assert engine.config == config
    assert engine.basis_calculator is not None


def test_engine_spread_filter():
    """Test spread filter rejects wide spreads."""
    from shared.arbitrage.engine import ArbitrageEngine
    from shared.arbitrage.config import ArbitrageConfig

    config = ArbitrageConfig(max_spread_ticks=2)
    engine = ArbitrageEngine(config)

    # 3 ticks spread (0.15) should be rejected
    can_enter, signal, reason = engine.check_spread(
        best_bid=330.45,
        best_ask=330.60  # 0.15 spread = 3 ticks
    )

    assert can_enter is False
    assert "spread" in reason.lower()


def test_engine_depth_filter():
    """Test depth filter requires sufficient liquidity."""
    from shared.arbitrage.engine import ArbitrageEngine
    from shared.arbitrage.config import ArbitrageConfig

    config = ArbitrageConfig(order_size=5.0, depth_multiplier=5.0)
    engine = ArbitrageEngine(config)

    # Need 25 contracts depth, only have 20
    can_enter = engine.check_depth(
        bid_qty=20,
        ask_qty=20
    )

    assert can_enter is False


def test_engine_full_entry_check():
    """Test full entry check flow."""
    from shared.arbitrage.engine import ArbitrageEngine
    from shared.arbitrage.config import ArbitrageConfig

    config = ArbitrageConfig(
        min_samples=5,
        basis_threshold=2.0,
        max_spread_ticks=2,
        depth_multiplier=2.0,
        order_size=5.0
    )
    engine = ArbitrageEngine(config)

    # Warmup the basis calculator
    for i in range(10):
        engine.check_entry(
            spot_index=330.0,
            futures_price=330.95,  # Near fair value
            days_to_expiry=30,
            best_bid=330.90,
            best_ask=331.00,
            bid_qty=50,
            ask_qty=50,
            timestamp=1705300800.0 + i
        )

    # Now check with extreme basis
    can_enter, signal, reason = engine.check_entry(
        spot_index=330.0,
        futures_price=335.0,  # Big deviation
        days_to_expiry=30,
        best_bid=334.95,
        best_ask=335.05,  # 2 ticks spread
        bid_qty=50,
        ask_qty=50,
        timestamp=1705300810.0
    )

    # Should generate a signal (basis too high = SELL)
    assert can_enter is True
    assert signal is not None
    assert signal.direction == "SELL"
