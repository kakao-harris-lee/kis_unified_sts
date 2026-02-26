"""Unit tests for WebSocket parsing functions."""
import time
from shared.kis.websocket import (
    ORDERBOOK_FIELDS,
    ORDERBOOK_MIN_FIELDS,
    parse_futures_orderbook,
    parse_futures_trade,
    _safe_float,
)


class TestSafeFloat:
    """Tests for _safe_float helper function."""

    def test_valid_float(self):
        """Test extraction of valid float value."""
        fields = ["", "123.45", ""]
        result = _safe_float(fields, 1)
        assert result == 123.45

    def test_empty_field_returns_default(self):
        """Test empty field returns default value."""
        fields = ["", "", ""]
        result = _safe_float(fields, 1, default=0.0)
        assert result == 0.0

    def test_empty_field_returns_none(self):
        """Test empty field returns None when no default."""
        fields = ["", "", ""]
        result = _safe_float(fields, 1)
        assert result is None

    def test_index_out_of_range(self):
        """Test index out of range returns default."""
        fields = ["1", "2"]
        result = _safe_float(fields, 10, default=99.0)
        assert result == 99.0

    def test_invalid_float_returns_default(self):
        """Test invalid float string returns default."""
        fields = ["", "not_a_number", ""]
        result = _safe_float(fields, 1, default=0.0)
        assert result == 0.0

    def test_value_exceeds_max_bound(self):
        """Test value exceeding max bound returns default."""
        fields = ["", "1e10", ""]  # Exceeds MAX_PRICE (1e9)
        result = _safe_float(fields, 1, default=0.0)
        assert result == 0.0

    def test_value_below_min_bound(self):
        """Test value below min bound returns default."""
        fields = ["", "-1e10", ""]  # Below MIN_PRICE (-1e9)
        result = _safe_float(fields, 1, default=0.0)
        assert result == 0.0

    def test_negative_valid_value(self):
        """Test valid negative value is accepted."""
        fields = ["", "-500.0", ""]
        result = _safe_float(fields, 1)
        assert result == -500.0


class TestParseFuturesOrderbook:
    """Tests for parse_futures_orderbook function."""

    def test_valid_orderbook(self, sample_orderbook_data):
        """Test parsing valid orderbook data."""
        result = parse_futures_orderbook("101V01", sample_orderbook_data, time.time())

        assert result is not None
        assert result.symbol == "101V01"

        # Check bid prices
        assert result.bid_price_1 == 330.45
        assert result.bid_price_2 == 330.40
        assert result.bid_price_3 == 330.35

        # Check ask prices
        assert result.ask_price_1 == 330.50
        assert result.ask_price_2 == 330.55
        assert result.ask_price_3 == 330.60

        # Check quantities
        assert result.bid_qty_1 == 120
        assert result.ask_qty_1 == 100

    def test_short_fields_returns_none(self):
        """Test insufficient fields returns None."""
        data = "^".join([""] * 10)  # Only 10 fields, need ORDERBOOK_MIN_FIELDS
        result = parse_futures_orderbook("101V01", data, time.time())
        assert result is None

    def test_empty_fields(self):
        """Test all empty fields."""
        data = "^".join([""] * ORDERBOOK_MIN_FIELDS)
        result = parse_futures_orderbook("101V01", data, time.time())

        assert result is not None
        # Default values for required fields
        assert result.bid_price_1 == 0.0
        assert result.ask_price_1 == 0.0

    def test_invalid_float_in_field(self):
        """Test handling of invalid float in field."""
        fields = [""] * ORDERBOOK_MIN_FIELDS
        fields[ORDERBOOK_FIELDS["bid_price"][0]] = "invalid_price"  # bid_price_1
        data = "^".join(fields)

        result = parse_futures_orderbook("101V01", data, time.time())
        # Should still parse, using default for invalid field
        assert result is not None

    def test_timestamp_preserved(self):
        """Test timestamp is preserved in result."""
        ts = 1234567890.123
        result = parse_futures_orderbook("101V01", "^".join([""] * ORDERBOOK_MIN_FIELDS), ts)
        assert result.timestamp == ts


class TestParseFuturesTrade:
    """Tests for parse_futures_trade function."""

    def test_valid_trade(self, sample_trade_data):
        """Test parsing valid trade data."""
        result = parse_futures_trade("101V01", sample_trade_data, time.time())

        assert result is not None
        assert result.symbol == "101V01"
        assert result.current_price == 330.25
        assert result.open_price == 329.50
        assert result.high_price == 331.00
        assert result.low_price == 329.00
        assert result.tick_volume == 5
        assert result.cumulative_volume == 15000
        assert result.open_interest == 25000

    def test_short_fields_returns_none(self):
        """Test insufficient fields returns None."""
        data = "^".join([""] * 5)  # Only 5 fields, need 19
        result = parse_futures_trade("101V01", data, time.time())
        assert result is None

    def test_empty_ohlc_fields(self):
        """Test empty OHLC fields are None."""
        data = "^".join([""] * 19)
        result = parse_futures_trade("101V01", data, time.time())

        assert result is not None
        assert result.current_price is None
        assert result.open_price is None
        assert result.high_price is None
        assert result.low_price is None

    def test_partial_data(self):
        """Test parsing with only some fields populated."""
        fields = [""] * 19
        fields[5] = "330.00"  # Only current price
        data = "^".join(fields)

        result = parse_futures_trade("101V01", data, time.time())

        assert result is not None
        assert result.current_price == 330.00
        assert result.open_price is None
        assert result.tick_volume is None


class TestEdgeCases:
    """Edge case tests for parsing functions."""

    def test_exact_minimum_fields_orderbook(self):
        """Test exactly minimum required fields for orderbook."""
        data = "^".join(["1"] * ORDERBOOK_MIN_FIELDS)
        result = parse_futures_orderbook("101V01", data, time.time())
        assert result is not None

    def test_37_fields_orderbook_is_valid(self):
        """Current parser should accept 37-field messages (uses up to index 36)."""
        data = "^".join(["1"] * 37)
        result = parse_futures_orderbook("101V01", data, time.time())
        assert result is not None

    def test_exact_minimum_fields_trade(self):
        """Test exactly 19 fields for trade."""
        data = "^".join(["1"] * 19)
        result = parse_futures_trade("101V01", data, time.time())
        assert result is not None

    def test_extra_fields_ignored(self):
        """Test extra fields are ignored."""
        # More than required fields
        data = "^".join(["1"] * 100)
        result = parse_futures_orderbook("101V01", data, time.time())
        assert result is not None

    def test_scientific_notation(self):
        """Test scientific notation is handled."""
        fields = [""] * ORDERBOOK_MIN_FIELDS
        fields[ORDERBOOK_FIELDS["bid_price"][0]] = "3.3045e2"  # 330.45 in scientific notation
        data = "^".join(fields)

        result = parse_futures_orderbook("101V01", data, time.time())
        assert result is not None
        assert abs(result.bid_price_1 - 330.45) < 0.01

    def test_zero_values(self):
        """Test zero values are handled correctly."""
        fields = [""] * 19
        fields[5] = "0"  # current_price = 0
        fields[9] = "0"  # tick_volume = 0
        data = "^".join(fields)

        result = parse_futures_trade("101V01", data, time.time())
        assert result is not None
        assert result.current_price == 0.0
        assert result.tick_volume == 0.0
