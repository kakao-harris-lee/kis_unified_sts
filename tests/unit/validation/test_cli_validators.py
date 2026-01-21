"""Tests for CLI validators."""
import tempfile
from pathlib import Path

import pytest
import pandas as pd

from shared.validation.cli_validators import (
    validate_csv_file,
    validate_capital,
    validate_strategy_name,
    validate_symbol,
    validate_port,
    ValidationError,
)


class TestValidateCSVFile:
    """Tests for validate_csv_file function."""

    def test_valid_csv(self, tmp_path):
        """Test validation of a valid CSV file."""
        csv_file = tmp_path / "valid.csv"
        df = pd.DataFrame({
            "datetime": ["2024-01-01", "2024-01-02"],
            "open": [100, 101],
            "high": [105, 106],
            "low": [99, 100],
            "close": [104, 105],
            "volume": [1000, 1100],
        })
        df.to_csv(csv_file, index=False)

        result = validate_csv_file(str(csv_file))

        assert len(result) == 2
        assert "datetime" in result.columns
        assert result["datetime"].dtype == "datetime64[ns]"

    def test_missing_datetime_column(self, tmp_path):
        """Test validation fails when datetime column is missing."""
        csv_file = tmp_path / "no_datetime.csv"
        df = pd.DataFrame({
            "close": [100, 101],
        })
        df.to_csv(csv_file, index=False)

        with pytest.raises(ValidationError) as exc_info:
            validate_csv_file(str(csv_file))

        assert "datetime" in str(exc_info.value).lower()

    def test_missing_close_column(self, tmp_path):
        """Test validation fails when close column is missing."""
        csv_file = tmp_path / "no_close.csv"
        df = pd.DataFrame({
            "datetime": ["2024-01-01", "2024-01-02"],
        })
        df.to_csv(csv_file, index=False)

        with pytest.raises(ValidationError) as exc_info:
            validate_csv_file(str(csv_file))

        assert "close" in str(exc_info.value).lower()

    def test_file_not_found(self):
        """Test validation fails when file doesn't exist."""
        with pytest.raises(ValidationError) as exc_info:
            validate_csv_file("/nonexistent/path/file.csv")

        assert "not found" in str(exc_info.value).lower()

    def test_empty_csv(self, tmp_path):
        """Test validation fails for empty CSV."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("")

        with pytest.raises(ValidationError) as exc_info:
            validate_csv_file(str(csv_file))

        assert "empty" in str(exc_info.value).lower()

    def test_negative_price_values(self, tmp_path):
        """Test validation fails for negative price values."""
        csv_file = tmp_path / "negative.csv"
        df = pd.DataFrame({
            "datetime": ["2024-01-01"],
            "close": [-100],  # Negative price
        })
        df.to_csv(csv_file, index=False)

        with pytest.raises(ValidationError) as exc_info:
            validate_csv_file(str(csv_file))

        assert "negative" in str(exc_info.value).lower()

    def test_file_size_limit(self, tmp_path):
        """Test validation fails for oversized files."""
        csv_file = tmp_path / "large.csv"
        # Create a file > 1MB
        csv_file.write_bytes(b"x" * (2 * 1024 * 1024))

        with pytest.raises(ValidationError) as exc_info:
            validate_csv_file(str(csv_file), max_size_mb=1)

        assert "large" in str(exc_info.value).lower()


class TestValidateCapital:
    """Tests for validate_capital function."""

    def test_valid_capital(self):
        """Test validation of valid capital amounts."""
        assert validate_capital(10_000_000) == 10_000_000
        assert validate_capital(1.0) == 1.0
        assert validate_capital(999_999_999_999) == 999_999_999_999

    def test_negative_capital(self):
        """Test validation fails for negative capital."""
        with pytest.raises(ValidationError) as exc_info:
            validate_capital(-100)

        assert "positive" in str(exc_info.value).lower()

    def test_zero_capital(self):
        """Test validation fails for zero capital."""
        with pytest.raises(ValidationError) as exc_info:
            validate_capital(0)

        assert "positive" in str(exc_info.value).lower()

    def test_exceeds_maximum(self):
        """Test validation fails when exceeding maximum."""
        with pytest.raises(ValidationError) as exc_info:
            validate_capital(2_000_000_000_000)

        assert "maximum" in str(exc_info.value).lower()


class TestValidateStrategyName:
    """Tests for validate_strategy_name function."""

    def test_valid_names(self):
        """Test validation of valid strategy names."""
        assert validate_strategy_name("bb_reversion") == "bb_reversion"
        assert validate_strategy_name("Strategy1") == "Strategy1"
        assert validate_strategy_name("ofi-momentum") == "ofi-momentum"

    def test_empty_name(self):
        """Test validation fails for empty name."""
        with pytest.raises(ValidationError) as exc_info:
            validate_strategy_name("")

        assert "empty" in str(exc_info.value).lower()

    def test_invalid_characters(self):
        """Test validation fails for invalid characters."""
        with pytest.raises(ValidationError) as exc_info:
            validate_strategy_name("strategy@name")

        assert "invalid" in str(exc_info.value).lower()

    def test_too_long_name(self):
        """Test validation fails for names that are too long."""
        with pytest.raises(ValidationError) as exc_info:
            validate_strategy_name("x" * 101)

        assert "long" in str(exc_info.value).lower()


class TestValidateSymbol:
    """Tests for validate_symbol function."""

    def test_valid_symbols(self):
        """Test validation of valid symbols."""
        assert validate_symbol("005930") == "005930"
        assert validate_symbol("101S06") == "101S06"
        assert validate_symbol("aapl") == "AAPL"  # Uppercased

    def test_empty_symbol(self):
        """Test validation fails for empty symbol."""
        with pytest.raises(ValidationError):
            validate_symbol("")

    def test_invalid_symbol(self):
        """Test validation fails for invalid symbols."""
        with pytest.raises(ValidationError):
            validate_symbol("sym@bol")


class TestValidatePort:
    """Tests for validate_port function."""

    def test_valid_ports(self):
        """Test validation of valid ports."""
        assert validate_port(80) == 80
        assert validate_port(8080) == 8080
        assert validate_port(65535) == 65535

    def test_invalid_port_zero(self):
        """Test validation fails for port 0."""
        with pytest.raises(ValidationError):
            validate_port(0)

    def test_invalid_port_negative(self):
        """Test validation fails for negative ports."""
        with pytest.raises(ValidationError):
            validate_port(-1)

    def test_invalid_port_too_high(self):
        """Test validation fails for ports > 65535."""
        with pytest.raises(ValidationError):
            validate_port(65536)
