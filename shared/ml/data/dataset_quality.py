"""Dataset quality checks for synthetic, transfer, and hybrid OHLCV data."""

from __future__ import annotations

from typing import Any

import pandas as pd


REQUIRED_OHLCV_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]


def validate_ohlcv_quality(
    df: pd.DataFrame,
    *,
    symbol: str,
    table: str,
    max_zero_volume_ratio: float = 0.95,
    max_zero_volume_price_move_ratio: float = 0.20,
    reject_duplicate_datetime: bool = True,
    require_monotonic_datetime: bool = True,
) -> dict[str, Any]:
    """Validate OHLCV integrity and return a concise summary."""
    if df.empty:
        raise ValueError(f"Empty dataset: {table} ({symbol})")

    missing = [col for col in REQUIRED_OHLCV_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns for {table}/{symbol}: {missing}")

    checked = df.copy()
    checked["datetime"] = pd.to_datetime(checked["datetime"])

    if reject_duplicate_datetime:
        duplicate_count = int(checked["datetime"].duplicated().sum())
        if duplicate_count > 0:
            raise ValueError(
                f"Data quality check failed ({table}/{symbol}): duplicated datetime rows={duplicate_count}"
            )

    if require_monotonic_datetime and not checked["datetime"].is_monotonic_increasing:
        raise ValueError(
            f"Data quality check failed ({table}/{symbol}): datetime is not monotonic increasing"
        )

    if checked[["open", "high", "low", "close"]].isna().any().any():
        raise ValueError(f"Data quality check failed ({table}/{symbol}): NaN prices detected")

    if (checked[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError(f"Data quality check failed ({table}/{symbol}): non-positive prices detected")

    if (checked["high"] < checked[["open", "close"]].max(axis=1)).any():
        raise ValueError(f"Data quality check failed ({table}/{symbol}): high below open/close")
    if (checked["low"] > checked[["open", "close"]].min(axis=1)).any():
        raise ValueError(f"Data quality check failed ({table}/{symbol}): low above open/close")

    if checked["volume"].isna().any():
        raise ValueError(f"Data quality check failed ({table}/{symbol}): NaN volume detected")
    if (checked["volume"] < 0).any():
        raise ValueError(f"Data quality check failed ({table}/{symbol}): negative volume detected")

    zero_volume_ratio = float((checked["volume"] == 0).mean())
    if zero_volume_ratio > max_zero_volume_ratio:
        raise ValueError(
            f"Data quality check failed ({table}/{symbol}): zero-volume ratio={zero_volume_ratio:.4f} > {max_zero_volume_ratio:.4f}"
        )

    close_diff = checked["close"].diff().abs().fillna(0)
    phantom_ratio = float(((checked["volume"] == 0) & (close_diff > 0)).mean())
    if phantom_ratio > max_zero_volume_price_move_ratio:
        raise ValueError(
            f"Data quality check failed ({table}/{symbol}): zero-volume moving-price ratio={phantom_ratio:.4f} > {max_zero_volume_price_move_ratio:.4f}"
        )

    return {
        "rows": int(len(checked)),
        "start": checked["datetime"].min().isoformat(),
        "end": checked["datetime"].max().isoformat(),
        "zero_volume_ratio": round(zero_volume_ratio, 6),
        "zero_volume_price_move_ratio": round(phantom_ratio, 6),
    }
