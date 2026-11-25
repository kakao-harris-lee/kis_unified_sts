"""CP-3 bar-frame helpers shared by the live producer and B1a."""

from __future__ import annotations

import pandas as pd

from tools.tos_cp3.produce_fields import OpenAnchor, StrategyInputs

COLUMNS = ["code", "timestamp", "open", "high", "low", "close", "volume"]

__all__ = ["COLUMNS", "frame", "seed_capacity"]


def frame(rows: list[tuple]) -> pd.DataFrame:
    return (
        pd.DataFrame(rows, columns=COLUMNS)
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


def seed_capacity(
    df: pd.DataFrame, strategy: StrategyInputs, anchor: OpenAnchor
) -> int:
    """First session cannot advance check's window without a previous close."""
    if df.empty:
        return 0
    dates = sorted(set(df.timestamp.dt.date))
    minutes = (
        df.timestamp.dt.hour * 60
        + df.timestamp.dt.minute
        - (anchor.hour * 60 + anchor.minute)
    )
    cfg = strategy.entry_config
    return int(
        (
            (df.timestamp.dt.date != dates[0])
            & (minutes >= cfg.valid_minutes_min)
            & (minutes <= cfg.no_entry_after_minutes_since_open)
        ).sum()
    )
