"""Quality guards for stock daily candles."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import Field

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigError

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)


class DailyCandleQualityConfig(ServiceConfigBase):
    """Configurable guards for daily OHLCV inputs."""

    _default_config_file = "daily_data_quality.yaml"

    fetch_multiplier: int = Field(
        default=3,
        ge=1,
        description="Raw rows to fetch per requested clean row",
    )
    repeated_ohlcv_run_min: int = Field(
        default=5,
        ge=2,
        description="Minimum consecutive repeated OHLCV run to reject",
    )
    reject_nonpositive_volume: bool = Field(
        default=True,
        description="Reject rows where volume is zero or negative",
    )


def load_daily_quality_config() -> DailyCandleQualityConfig:
    """Load quality config, falling back to defaults if the YAML is unavailable."""
    try:
        return DailyCandleQualityConfig.from_yaml()
    except ConfigError as exc:
        logger.warning("Daily quality config unavailable, using defaults: %s", exc)
        return DailyCandleQualityConfig()


def quality_fetch_limit(limit: int, config: DailyCandleQualityConfig) -> int:
    """Return raw row limit needed before quality filtering."""
    requested = max(1, int(limit))
    return requested * max(1, int(config.fetch_multiplier))


def clean_daily_candle_frame(
    df: pd.DataFrame,
    *,
    config: DailyCandleQualityConfig,
    limit: int | None = None,
) -> pd.DataFrame:
    """Deduplicate and remove placeholder-like daily candles.

    The input and output are oldest-to-newest after cleaning.  Placeholder rows
    are detected as a consecutive run where the full OHLCV tuple is repeated
    for ``repeated_ohlcv_run_min`` or more rows.
    """
    if df.empty:
        return df

    required = {"date", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"daily candle frame missing columns: {sorted(missing)}")

    cleaned = df.copy()
    cleaned["date"] = _to_date_series(cleaned["date"])
    cleaned = cleaned.sort_values("date").drop_duplicates("date", keep="last")

    for col in ("open", "high", "low", "close", "volume"):
        cleaned[col] = cleaned[col].astype(float)

    if config.reject_nonpositive_volume:
        cleaned = cleaned[cleaned["volume"] > 0]

    signature = (
        cleaned["open"].astype(str)
        + "|"
        + cleaned["high"].astype(str)
        + "|"
        + cleaned["low"].astype(str)
        + "|"
        + cleaned["close"].astype(str)
        + "|"
        + cleaned["volume"].astype(str)
    )
    run_id = signature.ne(signature.shift()).cumsum()
    run_size = run_id.map(run_id.value_counts())
    reject_repeated_run = run_size >= config.repeated_ohlcv_run_min
    if reject_repeated_run.any():
        logger.warning(
            "Dropping %d suspicious repeated daily candles",
            int(reject_repeated_run.sum()),
        )
        cleaned = cleaned[~reject_repeated_run]

    cleaned = cleaned.sort_values("date").reset_index(drop=True)
    if limit is not None and limit > 0 and len(cleaned) > limit:
        cleaned = cleaned.tail(limit).reset_index(drop=True)

    return cleaned


def _to_date_series(series: pd.Series) -> pd.Series:
    import pandas as pd

    converted = pd.to_datetime(series)
    return converted.dt.date
