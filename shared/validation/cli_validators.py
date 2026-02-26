"""Input validators for CLI commands.

Provides validation for user inputs to prevent:
- Malicious CSV files (size limits, schema validation)
- Invalid parameter values (negative capital, etc.)
- Path traversal attacks
"""
import logging
from pathlib import Path
from typing import Set, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Validation constants
ALLOWED_CSV_COLUMNS = {"datetime", "open", "high", "low", "close", "volume"}
REQUIRED_CSV_COLUMNS = {"datetime", "close"}
MAX_CSV_SIZE_MB = 100
MAX_CSV_ROWS = 10_000_000  # 10 million rows
MAX_CAPITAL = 1_000_000_000_000  # 1 trillion KRW


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


def validate_csv_file(
    path: str,
    max_size_mb: float = MAX_CSV_SIZE_MB,
    max_rows: int = MAX_CSV_ROWS,
    reject_duplicate_datetime: bool = False,
    require_monotonic_datetime: bool = False,
    max_zero_volume_ratio: float | None = None,
    max_zero_volume_price_move_ratio: float | None = None,
) -> pd.DataFrame:
    """Validate CSV file before processing.

    Performs the following checks:
    1. File exists and is accessible
    2. File size is within limits
    3. Required columns exist
    4. Datetime column can be parsed
    5. Numeric columns are valid

    Args:
        path: Path to CSV file
        max_size_mb: Maximum allowed file size in MB
        max_rows: Maximum allowed number of rows

    Returns:
        Validated DataFrame with parsed datetime

    Raises:
        ValidationError: If validation fails
    """
    file_path = Path(path)

    # Check file exists
    if not file_path.exists():
        raise ValidationError(f"File not found: {path}")

    if not file_path.is_file():
        raise ValidationError(f"Not a file: {path}")

    # Size check
    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValidationError(
            f"CSV file too large: {size_mb:.1f}MB > {max_size_mb}MB limit"
        )

    # Load with row limit check
    try:
        df = pd.read_csv(path, nrows=max_rows + 1)
    except pd.errors.EmptyDataError:
        raise ValidationError("CSV file is empty")
    except pd.errors.ParserError as e:
        raise ValidationError(f"Failed to parse CSV: {e}")

    if len(df) > max_rows:
        raise ValidationError(f"CSV has too many rows: >{max_rows:,}")

    # Required columns
    missing_columns = REQUIRED_CSV_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValidationError(
            f"CSV missing required columns: {missing_columns}. "
            f"Required: {REQUIRED_CSV_COLUMNS}"
        )

    # Parse dates
    try:
        df["datetime"] = pd.to_datetime(df["datetime"])
    except Exception as e:
        raise ValidationError(f"Failed to parse 'datetime' column: {e}")

    # Datetime integrity checks
    if reject_duplicate_datetime:
        duplicate_count = int(df["datetime"].duplicated().sum())
        if duplicate_count > 0:
            raise ValidationError(
                f"'datetime' contains duplicated rows: {duplicate_count}"
            )

    if require_monotonic_datetime and not df["datetime"].is_monotonic_increasing:
        raise ValidationError("'datetime' must be strictly monotonic increasing")

    # Validate numeric columns
    numeric_columns = ["open", "high", "low", "close", "volume"]
    for col in numeric_columns:
        if col in df.columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                # Try to convert
                try:
                    df[col] = pd.to_numeric(df[col])
                except ValueError:
                    raise ValidationError(f"Column '{col}' must be numeric")

    # Check for negative prices
    price_columns = ["open", "high", "low", "close"]
    for col in price_columns:
        if col in df.columns:
            if (df[col] < 0).any():
                raise ValidationError(f"Column '{col}' contains negative values")

    # Optional volume quality gate (useful for futures RL datasets)
    if max_zero_volume_ratio is not None and "volume" in df.columns:
        if not 0.0 <= max_zero_volume_ratio <= 1.0:
            raise ValidationError(
                f"max_zero_volume_ratio must be in [0,1], got {max_zero_volume_ratio}"
            )
        zero_volume_ratio = float((df["volume"] == 0).mean())
        if zero_volume_ratio > max_zero_volume_ratio:
            raise ValidationError(
                f"Zero-volume ratio too high: {zero_volume_ratio:.4f} > "
                f"{max_zero_volume_ratio:.4f}"
            )

    # Optional phantom-bar gate:
    # bars with zero volume while close price still changes.
    if (
        max_zero_volume_price_move_ratio is not None
        and "volume" in df.columns
        and "close" in df.columns
    ):
        if not 0.0 <= max_zero_volume_price_move_ratio <= 1.0:
            raise ValidationError(
                "max_zero_volume_price_move_ratio must be in [0,1], "
                f"got {max_zero_volume_price_move_ratio}"
            )
        close_diff = df["close"].diff().abs().fillna(0)
        phantom_ratio = float(((df["volume"] == 0) & (close_diff > 0)).mean())
        if phantom_ratio > max_zero_volume_price_move_ratio:
            raise ValidationError(
                "Zero-volume moving-price ratio too high: "
                f"{phantom_ratio:.4f} > {max_zero_volume_price_move_ratio:.4f}"
            )

    logger.info(f"CSV validated: {len(df)} rows, {len(df.columns)} columns")
    return df


def validate_capital(value: float, max_value: float = MAX_CAPITAL) -> float:
    """Validate capital amount.

    Args:
        value: Capital amount
        max_value: Maximum allowed capital

    Returns:
        Validated capital amount

    Raises:
        ValidationError: If validation fails
    """
    if value <= 0:
        raise ValidationError(f"Capital must be positive, got: {value}")

    if value > max_value:
        raise ValidationError(
            f"Capital exceeds maximum limit: {value:,.0f} > {max_value:,.0f}"
        )

    return value


def validate_strategy_name(name: str, allowed_chars: Optional[Set[str]] = None) -> str:
    """Validate strategy name.

    Args:
        name: Strategy name
        allowed_chars: Set of allowed characters (default: alphanumeric + underscore)

    Returns:
        Validated strategy name

    Raises:
        ValidationError: If validation fails
    """
    if not name:
        raise ValidationError("Strategy name cannot be empty")

    if len(name) > 100:
        raise ValidationError("Strategy name too long (max 100 characters)")

    # Default allowed characters
    if allowed_chars is None:
        import string

        allowed_chars = set(string.ascii_letters + string.digits + "_-")

    invalid_chars = set(name) - allowed_chars
    if invalid_chars:
        raise ValidationError(
            f"Strategy name contains invalid characters: {invalid_chars}"
        )

    return name


def validate_symbol(symbol: str) -> str:
    """Validate stock/futures symbol.

    Args:
        symbol: Trading symbol (e.g., '005930', '101S06')

    Returns:
        Validated symbol

    Raises:
        ValidationError: If validation fails
    """
    if not symbol:
        raise ValidationError("Symbol cannot be empty")

    # Symbol should be alphanumeric
    if not symbol.replace("-", "").replace(".", "").isalnum():
        raise ValidationError(f"Invalid symbol format: {symbol}")

    if len(symbol) > 20:
        raise ValidationError("Symbol too long (max 20 characters)")

    return symbol.upper()


def validate_port(port: int) -> int:
    """Validate port number.

    Args:
        port: Port number

    Returns:
        Validated port number

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(port, int):
        raise ValidationError(f"Port must be an integer, got: {type(port)}")

    if port < 1 or port > 65535:
        raise ValidationError(f"Port must be between 1 and 65535, got: {port}")

    return port
