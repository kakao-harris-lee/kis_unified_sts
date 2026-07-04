"""Pydantic config for the market-structure collector.

Loaded from the ``collector`` section of ``config/market_structure.yaml``
(the storage/snapshot sections of the same file are owned by
``shared/storage/market_structure_store.py``). All thresholds, Redis keys,
TTLs, and KIS TR parameters live here — no hardcoded branches in the
collector code.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from shared.config.base import ServiceConfigBase

# Coverage components tracked by the collector. Every component may be
# missing (recorded in ``missing_components``); values are never synthesized.
DEFAULT_COMPONENTS: tuple[str, ...] = (
    "foreign_futures",
    "program",
    "oi",
    "k200",
    "basis",
    "stock_investor",
    "fx",
    "overseas",
)


class MarketStructureRedisSettings(BaseModel):
    """Redis DB 1 publication keys and TTLs (project policy: keys need TTLs)."""

    latest_key: str = Field(default="market:structure:latest")
    latest_ttl_seconds: int = Field(default=86400, gt=0)
    stream_key: str = Field(default="stream:market.structure")
    stream_maxlen: int = Field(default=5000, gt=0)
    stream_ttl_seconds: int = Field(default=86400, gt=0)
    cum20_key: str = Field(default="market:structure:cum20:foreign_futures")
    cum20_ttl_seconds: int = Field(default=172800, gt=0)
    night_close_key: str = Field(default="market:structure:night_close")
    macro_stream_key: str = Field(default="stream:macro.overnight")


class MarketStructureKISSettings(BaseModel):
    """KIS TR parameters (REAL-investment only TRs; see roadmap Phase 0)."""

    foreign_futures_market_code: str = Field(default="K2I")
    foreign_futures_product_code: str = Field(default="F001")
    program_market_div: str = Field(default="J")
    program_market_cls: str = Field(default="K")
    futures_symbol: str = Field(default="101S6000")
    index_market_div: str = Field(default="U")
    index_code: str = Field(default="2001")


class MarketStructureBasisSettings(BaseModel):
    """Theoretical fair-value inputs (shared/arbitrage/basis_calculator.py)."""

    risk_free_rate: float = Field(default=0.035, ge=0.0)


class MarketStructureDerivedSettings(BaseModel):
    """Windows for the derived columns stored alongside raw components."""

    foreign_cum_window_days: int = Field(default=20, gt=0)
    basis_dev_ma_days: int = Field(default=5, gt=0)
    usdkrw_ret_days: int = Field(default=5, gt=0)
    k200_ma_windows: list[int] = Field(default_factory=lambda: [5, 20, 60])
    k200_ret_days: int = Field(default=20, gt=0)
    history_lookback_days: int = Field(default=120, gt=0)


class MarketStructureHealthSettings(BaseModel):
    """Freshness thresholds surfaced via /api/health/summary."""

    stale_after_seconds: int = Field(default=50400, gt=0)


class MarketStructureCollectorConfig(ServiceConfigBase):
    """Top-level collector config (``config/market_structure.yaml::collector``)."""

    _default_config_file: ClassVar[str] = "market_structure.yaml"
    _default_section: ClassVar[str] = "collector"

    redis: MarketStructureRedisSettings = Field(
        default_factory=MarketStructureRedisSettings
    )
    kis: MarketStructureKISSettings = Field(default_factory=MarketStructureKISSettings)
    basis: MarketStructureBasisSettings = Field(
        default_factory=MarketStructureBasisSettings
    )
    derived: MarketStructureDerivedSettings = Field(
        default_factory=MarketStructureDerivedSettings
    )
    components: list[str] = Field(default_factory=lambda: list(DEFAULT_COMPONENTS))
    health: MarketStructureHealthSettings = Field(
        default_factory=MarketStructureHealthSettings
    )
