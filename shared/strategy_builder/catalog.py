"""Strategy Builder capability catalog."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from shared.strategy_builder.schema import (
    BuilderCapabilities,
    ConditionOperator,
    ExitPrimitiveDefinition,
    IndicatorDefinition,
)

DEFAULT_CONFIG_PATH = Path("config/strategy_builder/indicators.yaml")


@lru_cache(maxsize=1)
def load_strategy_builder_config(
    path: str | Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        return {}
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    config = data.get("strategy_builder", {})
    return config if isinstance(config, dict) else {}


def load_capabilities() -> BuilderCapabilities:
    config = load_strategy_builder_config()
    indicators = [
        IndicatorDefinition.model_validate(item)
        for item in config.get("indicators", [])
        if isinstance(item, dict)
    ]
    operators = [
        ConditionOperator(operator) for operator in config.get("operators", [])
    ]
    return BuilderCapabilities(
        indicators=indicators,
        operators=operators,
        price_fields=list(
            config.get("price_fields", ["close", "open", "high", "low", "volume"])
        ),
        risk_fields=dict(config.get("risk_fields", {})),
        default_order_amount=float(config.get("default_order_amount", 1_000_000)),
        ttl_seconds=int(config.get("ttl_seconds", 86400)),
        directions=list(config.get("directions", ["long"])),
        exit_primitives=[
            ExitPrimitiveDefinition.model_validate(item)
            for item in config.get("exit_primitives", [])
            if isinstance(item, dict)
        ],
        gate_fields=dict(config.get("gate_fields", {})),
    )


def indicator_by_id() -> dict[str, IndicatorDefinition]:
    return {indicator.id: indicator for indicator in load_capabilities().indicators}


def exit_primitive_definitions() -> dict[str, ExitPrimitiveDefinition]:
    """Catalog exit-primitive metadata keyed by ExitRegistry name."""
    return {
        primitive.id: primitive for primitive in load_capabilities().exit_primitives
    }


def get_builder_ttl_seconds() -> int:
    return int(load_strategy_builder_config().get("ttl_seconds", 86400))


def get_builder_position_ttl_seconds() -> int:
    return int(load_strategy_builder_config().get("position_ttl_seconds", 172800))
