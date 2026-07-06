"""Config model for the futures margin-risk publisher.

Loads config/futures_margin.yaml::futures_margin. Margin rates / thresholds /
Redis values are config-driven; multiplier + tick come from
config/execution.yaml::futures_contract_spec at build time (single source of
contract constants — never duplicated here).
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field, model_validator

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigNotFoundError


class MarginProductDefault(BaseModel):
    """Per-product margin rates + overnight gap shock + symbol prefixes."""

    initial_margin_rate: float = Field(default=0.08, gt=0, le=1)
    maintenance_margin_rate: float = Field(default=0.06, gt=0, le=1)
    stress_gap_points: float = Field(default=5.0, ge=0)
    symbol_prefixes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self) -> MarginProductDefault:
        if self.maintenance_margin_rate > self.initial_margin_rate:
            raise ValueError(
                "maintenance_margin_rate must be <= initial_margin_rate "
                f"({self.maintenance_margin_rate} > {self.initial_margin_rate})"
            )
        cleaned = [str(p).strip() for p in self.symbol_prefixes if str(p).strip()]
        if not cleaned:
            raise ValueError("symbol_prefixes must not be empty")
        self.symbol_prefixes = cleaned
        return self


class MarginThresholdsConfig(BaseModel):
    """Margin-usage + liquidation-buffer escalation thresholds."""

    watch_margin_usage_pct: float = Field(default=0.45, gt=0, le=1)
    reduce_only_margin_usage_pct: float = Field(default=0.65, gt=0, le=1)
    block_new_entries_margin_usage_pct: float = Field(default=0.80, gt=0, le=1)
    critical_margin_usage_pct: float = Field(default=0.90, gt=0, le=1)
    watch_liquidation_buffer_ticks: float = Field(default=80, ge=0)
    critical_liquidation_buffer_ticks: float = Field(default=40, ge=0)

    @model_validator(mode="after")
    def _validate_order(self) -> MarginThresholdsConfig:
        usages = [
            self.watch_margin_usage_pct,
            self.reduce_only_margin_usage_pct,
            self.block_new_entries_margin_usage_pct,
            self.critical_margin_usage_pct,
        ]
        if usages != sorted(usages):
            raise ValueError("margin usage thresholds must be strictly ascending")
        if self.critical_liquidation_buffer_ticks > self.watch_liquidation_buffer_ticks:
            raise ValueError(
                "critical_liquidation_buffer_ticks must be <= watch buffer ticks"
            )
        return self


class MarginRedisConfig(BaseModel):
    """Redis publication contract (latest hash + stream + short TTLs)."""

    latest_key: str = Field(default="futures:risk:latest")
    latest_ttl_seconds: int = Field(default=900, gt=0)
    stream_key: str = Field(default="stream:futures.risk")
    stream_maxlen: int = Field(default=5000, gt=0)
    stream_ttl_seconds: int = Field(default=900, gt=0)


class MarginAlertsConfig(BaseModel):
    """Telegram advisory on risk-level escalation."""

    enabled: bool = Field(default=True)
    domain: str = Field(default="briefing")


class FuturesMarginConfig(ServiceConfigBase):
    """Top-level config from ``config/futures_margin.yaml``."""

    _default_config_file: ClassVar[str] = "futures_margin.yaml"
    _default_section: ClassVar[str] = "futures_margin"

    enabled: bool = Field(default=True)
    account_snapshot_max_age_seconds: int = Field(default=300, gt=0)
    price_max_age_seconds: int = Field(default=30, gt=0)
    fallback_account_equity_krw: float = Field(default=50_000_000, gt=0)
    product: str = Field(default="mini")
    product_defaults: dict[str, MarginProductDefault] = Field(default_factory=dict)
    thresholds: MarginThresholdsConfig = Field(default_factory=MarginThresholdsConfig)
    redis: MarginRedisConfig = Field(default_factory=MarginRedisConfig)
    alerts: MarginAlertsConfig = Field(default_factory=MarginAlertsConfig)

    #: product arg → execution-spec key / margin product_defaults key.
    _PRODUCT_SPEC_KEYS: ClassVar[dict[str, str]] = {
        "mini": "kospi200_mini",
        "kospi200": "kospi200_full",
    }

    @model_validator(mode="after")
    def _validate_product(self) -> FuturesMarginConfig:
        if self.product not in self._PRODUCT_SPEC_KEYS:
            raise ValueError(
                f"product must be 'mini' or 'kospi200', got {self.product!r}"
            )
        return self

    @property
    def reference_spec_key(self) -> str:
        """Execution-spec / product_defaults key for the reference product."""
        return self._PRODUCT_SPEC_KEYS[self.product]

    @classmethod
    def load_or_default(cls, path: str | None = None) -> FuturesMarginConfig:
        """Load from YAML when available, otherwise validated defaults."""
        try:
            return cls.from_yaml(path)
        except ConfigNotFoundError:
            return cls()
