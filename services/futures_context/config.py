"""Config model for the futures structured-context v2 publisher.

Loads config/futures_context.yaml::futures_context. Upstream input keys,
regime bands, and Redis publication values are config-driven.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field, model_validator

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigNotFoundError
from shared.instruments.futures import PRODUCT_ARG_TO_SPEC_KEY


class ContextInputsConfig(BaseModel):
    """Upstream read-model keys (read-only inputs)."""

    contract_latest_key: str = Field(default="futures:contract:latest")
    structure_latest_key: str = Field(default="market:structure:latest")
    risk_latest_key: str = Field(default="market:risk:latest")
    margin_latest_key: str = Field(default="futures:risk:latest")


class BasisRegimeConfig(BaseModel):
    """basis_regime classification bands (index points)."""

    fair_band_points: float = Field(default=0.25, gt=0)
    deep_band_points: float = Field(default=1.0, gt=0)

    @model_validator(mode="after")
    def _validate(self) -> BasisRegimeConfig:
        if self.deep_band_points <= self.fair_band_points:
            raise ValueError("deep_band_points must be > fair_band_points")
        return self


class ForeignFlowRegimeConfig(BaseModel):
    """foreign_flow_regime classification bands (net contracts)."""

    neutral_qty: float = Field(default=2000, gt=0)
    strong_qty: float = Field(default=8000, gt=0)

    @model_validator(mode="after")
    def _validate(self) -> ForeignFlowRegimeConfig:
        if self.strong_qty <= self.neutral_qty:
            raise ValueError("strong_qty must be > neutral_qty")
        return self


class ContextRedisConfig(BaseModel):
    """Redis publication contract (latest hash + stream + TTLs)."""

    latest_key: str = Field(default="futures:context:latest")
    latest_ttl_seconds: int = Field(default=86400, gt=0)
    stream_key: str = Field(default="stream:futures.context")
    stream_maxlen: int = Field(default=5000, gt=0)
    stream_ttl_seconds: int = Field(default=86400, gt=0)


class FuturesContextConfig(ServiceConfigBase):
    """Top-level config from ``config/futures_context.yaml``."""

    _default_config_file: ClassVar[str] = "futures_context.yaml"
    _default_section: ClassVar[str] = "futures_context"

    enabled: bool = Field(default=True)
    product: str = Field(default="mini")
    inputs: ContextInputsConfig = Field(default_factory=ContextInputsConfig)
    basis_regime: BasisRegimeConfig = Field(default_factory=BasisRegimeConfig)
    foreign_flow_regime: ForeignFlowRegimeConfig = Field(
        default_factory=ForeignFlowRegimeConfig
    )
    redis: ContextRedisConfig = Field(default_factory=ContextRedisConfig)

    @model_validator(mode="after")
    def _validate_product(self) -> FuturesContextConfig:
        if self.product not in PRODUCT_ARG_TO_SPEC_KEY:
            raise ValueError(
                f"product must be one of {sorted(PRODUCT_ARG_TO_SPEC_KEY)}, "
                f"got {self.product!r}"
            )
        return self

    @property
    def reference_spec_key(self) -> str:
        """Execution-spec key for the reference product's tick value."""
        return PRODUCT_ARG_TO_SPEC_KEY[self.product]

    @classmethod
    def load_or_default(cls, path: str | None = None) -> FuturesContextConfig:
        """Load from YAML when available, otherwise validated defaults."""
        try:
            return cls.from_yaml(path)
        except ConfigNotFoundError:
            return cls()
