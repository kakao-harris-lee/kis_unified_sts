"""Config model for the futures contract / roll-state publisher.

Loads config/futures_contract.yaml::futures_contract. All roll-window and Redis
values are config-driven (no magic numbers) — see the YAML for the roll policy.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field, model_validator

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigNotFoundError


class ContractRollConfig(BaseModel):
    """Roll-window thresholds (calendar days to front expiry)."""

    pre_roll_days: int = Field(default=5, ge=0)
    block_front_new_entries_days: int = Field(default=2, ge=0)
    require_roll_on_expiry_day: bool = Field(default=True)
    liquidity_flip_enabled: bool = Field(default=False)

    @model_validator(mode="after")
    def _validate_window(self) -> ContractRollConfig:
        if self.block_front_new_entries_days > self.pre_roll_days:
            raise ValueError(
                "block_front_new_entries_days must be <= pre_roll_days "
                f"(got {self.block_front_new_entries_days} > {self.pre_roll_days})"
            )
        return self


class ContractNightMasterConfig(BaseModel):
    """Night-session code resolution + manual override."""

    enabled: bool = Field(default=True)
    stale_after_days: int = Field(default=20, gt=0)
    manual_override_allowed: bool = Field(default=True)
    night_front_symbol: str = Field(default="")
    night_next_symbol: str = Field(default="")


class ContractRedisConfig(BaseModel):
    """Redis publication contract (latest hash + stream + TTLs)."""

    latest_key: str = Field(default="futures:contract:latest")
    latest_ttl_seconds: int = Field(default=86400, gt=0)
    latest_ttl_fallback_seconds: int = Field(default=172800, gt=0)
    stream_key: str = Field(default="stream:futures.contract")
    stream_maxlen: int = Field(default=5000, gt=0)
    stream_ttl_seconds: int = Field(default=86400, gt=0)


class FuturesContractConfig(ServiceConfigBase):
    """Top-level config from ``config/futures_contract.yaml``."""

    _default_config_file: ClassVar[str] = "futures_contract.yaml"
    _default_section: ClassVar[str] = "futures_contract"

    enabled: bool = Field(default=True)
    product: str = Field(default="mini")
    roll: ContractRollConfig = Field(default_factory=ContractRollConfig)
    night_master: ContractNightMasterConfig = Field(
        default_factory=ContractNightMasterConfig
    )
    redis: ContractRedisConfig = Field(default_factory=ContractRedisConfig)

    @model_validator(mode="after")
    def _validate_product(self) -> FuturesContractConfig:
        if self.product not in {"mini", "kospi200"}:
            raise ValueError(
                f"product must be 'mini' or 'kospi200', got {self.product!r}"
            )
        return self

    @classmethod
    def load_or_default(cls, path: str | None = None) -> FuturesContractConfig:
        """Load from YAML when available, otherwise validated defaults."""
        try:
            return cls.from_yaml(path)
        except ConfigNotFoundError:
            return cls()
