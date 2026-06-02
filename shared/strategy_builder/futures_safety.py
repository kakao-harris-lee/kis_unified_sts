"""Auto-enforced safety guards for builder-generated futures strategies."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time as dt_time
from functools import lru_cache
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path("config/strategy_builder/futures_safety.yaml")


@dataclass(frozen=True)
class FuturesSafety:
    """Hard limits that builder futures strategies cannot disable."""

    hard_stop_pct: float
    eod_close_time: dt_time


@lru_cache(maxsize=1)
def load_futures_safety(path: str | Path = DEFAULT_CONFIG_PATH) -> FuturesSafety:
    """Load the futures safety guards (cached via ``lru_cache``).

    Falls back to safe defaults (hard_stop_pct=3.0, eod_close_time=15:15) when
    the file or individual keys are missing. Malformed values raise a clear
    ``ValueError``.
    """
    cfg_path = Path(path)
    data: dict = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        data = raw.get("futures_safety", {}) or {}

    raw_hard_stop = data.get("hard_stop_pct", 3.0)
    try:
        hard_stop = float(raw_hard_stop)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"futures_safety.yaml: invalid hard_stop_pct {raw_hard_stop!r} "
            "(expected a number)"
        ) from exc

    raw_time = str(data.get("eod_close_time", "15:15"))
    try:
        hh, mm = (int(part) for part in raw_time.split(":")[:2])
        eod_close_time = dt_time(hh, mm)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"futures_safety.yaml: invalid eod_close_time {raw_time!r} "
            "(expected HH:MM)"
        ) from exc

    return FuturesSafety(hard_stop_pct=hard_stop, eod_close_time=eod_close_time)
