"""Test FeatureProcessor."""


def test_processor_creation():
    """Test FeatureProcessor instantiation."""
    from shared.features.processor import FeatureProcessor, ProcessorConfig

    config = ProcessorConfig()
    processor = FeatureProcessor(config)

    assert processor.config == config


def test_process_trade():
    """Test processing a trade event."""
    from shared.features.processor import FeatureProcessor, ProcessorConfig

    config = ProcessorConfig()
    processor = FeatureProcessor(config)

    # Process trade
    result = processor.process_trade(
        price=330.50,
        size=10,
        side="BUY",
        timestamp=1705300800.0,
    )

    assert result is not None
    assert "vwap" in result
    assert "trade_count" in result


def test_process_orderbook():
    """Test processing orderbook update."""
    from shared.features.processor import FeatureProcessor, ProcessorConfig

    config = ProcessorConfig()
    processor = FeatureProcessor(config)

    # Process orderbook
    result = processor.process_orderbook(
        best_bid=330.45,
        bid_qty=100,
        best_ask=330.50,
        ask_qty=100,
        timestamp=1705300800.0,
    )

    assert result is not None
    assert "spread" in result
    assert "mid_price" in result
    assert "ofi" in result


def test_get_features():
    """Test getting feature snapshot."""
    from shared.features.processor import FeatureProcessor, ProcessorConfig

    config = ProcessorConfig()
    processor = FeatureProcessor(config)

    # Process some data
    for i in range(10):
        processor.process_trade(
            price=330.0 + i * 0.1,
            size=10 + i,
            side="BUY" if i % 2 == 0 else "SELL",
            timestamp=1705300800.0 + i,
        )
        processor.process_orderbook(
            best_bid=330.0 + i * 0.1 - 0.025,
            bid_qty=100 + i,
            best_ask=330.0 + i * 0.1 + 0.025,
            ask_qty=100 - i,
            timestamp=1705300800.0 + i,
        )

    features = processor.get_features()

    assert features is not None
    assert "vwap" in features
    assert "ofi" in features
    assert "spread" in features
    assert "liquidity_score" in features


def test_trade_imbalance():
    """Test buy/sell trade imbalance calculation."""
    from shared.features.processor import FeatureProcessor, ProcessorConfig

    config = ProcessorConfig()
    processor = FeatureProcessor(config)

    # More buys than sells
    for i in range(10):
        processor.process_trade(price=330.0, size=10, side="BUY")

    for i in range(5):
        processor.process_trade(price=330.0, size=10, side="SELL")

    imbalance = processor.get_trade_imbalance()

    # Should be positive (more buys)
    assert imbalance > 0


def test_processor_reset():
    """Test processor reset."""
    from shared.features.processor import FeatureProcessor, ProcessorConfig

    config = ProcessorConfig()
    processor = FeatureProcessor(config)

    # Process data
    processor.process_trade(price=330.0, size=10, side="BUY")

    processor.reset()

    features = processor.get_features()
    assert features["trade_count"] == 0
