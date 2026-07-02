"""Shared config + frame helpers for the Market Risk Score validation CLIs.

Read-only analysis lane (unified roadmap §4.4): these helpers consume the
``market_structure_daily`` Parquet score columns written by the Phase 1a
hindcast CLI. They intentionally do NOT import the score engine
(``shared/risk/market_risk_score.py``) — the Parquet contract
(``risk_score``, ``risk_score_ema3``, ``risk_band``, ``unified_regime``,
``degraded``, ``risk_coverage_ratio``) is the only coupling point. Note the
bare ``coverage_ratio`` close-row column is the collector's data-collection
coverage, not the engine's weighted score coverage.
"""

from __future__ import annotations

import math
import sys
from datetime import date
from pathlib import Path
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

# Direct-invocation support (``python scripts/validation/<tool>.py``).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigNotFoundError

KST = ZoneInfo("Asia/Seoul")


class ValidationSettings(BaseModel):
    """Hindsight-report knobs (§4.4-2 discrimination + O7 flapping)."""

    score_columns: list[str] = Field(
        default_factory=lambda: ["risk_score_ema3", "risk_score"]
    )
    band_column: str = "risk_band"
    regime_column: str = "unified_regime"
    degraded_column: str = "degraded"
    coverage_column: str = "risk_coverage_ratio"
    price_columns: list[str] = Field(
        default_factory=lambda: ["kospi_close", "k200_close"]
    )
    thresholds: list[float] = Field(default_factory=lambda: [70.0, 85.0])
    horizons_days: list[int] = Field(default_factory=lambda: [5, 20])
    lower_quantiles: list[float] = Field(default_factory=lambda: [0.10, 0.25])
    exclude_degraded: bool = True
    permutation_iterations: int = Field(default=5000, ge=1)
    permutation_seed: int = 20260702
    flapping_round_trip_pairs: list[list[str]] = Field(
        default_factory=lambda: [["ELEVATED", "HIGH"]]
    )
    episodes: list[str] = Field(default_factory=lambda: ["2026-07-02"])
    report_dir: str = "reports/market-risk"


class CounterfactualSettings(BaseModel):
    """Retroactive long-block gate knobs (§4.4-3, §4.2 HIGH-band rule)."""

    block_threshold: float = 70.0
    block_sides: list[str] = Field(default_factory=lambda: ["long"])
    asset_classes: list[str] = Field(default_factory=list)
    score_columns: list[str] = Field(
        default_factory=lambda: ["risk_score_ema3", "risk_score"]
    )
    exclude_degraded: bool = True
    prefer_premarket: bool = True
    assume_naive_entry_tz: str = "Asia/Seoul"
    report_dir: str = "reports/market-risk"


class MarketRiskValidationConfig(ServiceConfigBase):
    """Top-level config loaded from ``config/market_risk_validation.yaml``."""

    _default_config_file: ClassVar[str] = "market_risk_validation.yaml"

    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    counterfactual: CounterfactualSettings = Field(
        default_factory=CounterfactualSettings
    )

    @classmethod
    def load_or_default(cls, path: str | None = None) -> MarketRiskValidationConfig:
        """Load from YAML when available, otherwise return validated defaults."""
        try:
            return cls.from_yaml(path)
        except ConfigNotFoundError:
            return cls()


def is_missing(value: Any) -> bool:
    """True for None/NaN — mirrors the collector's presence semantics."""
    if value is None:
        return True
    return isinstance(value, float) and math.isnan(value)


def first_present_column(frame: Any, candidates: list[str]) -> str | None:
    """First candidate column that exists and has at least one present value."""
    for name in candidates:
        if name in frame.columns and any(
            not is_missing(value) for value in frame[name]
        ):
            return name
    return None


def load_snapshot_frame(
    store: Any,
    snapshot: str,
    start: date | None = None,
    end: date | None = None,
) -> Any:
    """Load one snapshot's rows sorted by trade_date (may be empty)."""
    frame = store.read_range(start, end, snapshot=snapshot)
    if frame is None or getattr(frame, "empty", True):
        return frame
    return frame.sort_values("trade_date").reset_index(drop=True)


def build_store(parquet_root: str | None) -> Any:
    """Market-structure store from an explicit root or repo storage config."""
    from shared.storage.market_structure_store import (
        MarketStructureConfig,
        ParquetMarketStructureStore,
        create_market_structure_store,
    )

    if parquet_root:
        return ParquetMarketStructureStore(
            parquet_root, config=MarketStructureConfig.load_or_default()
        )
    return create_market_structure_store()
