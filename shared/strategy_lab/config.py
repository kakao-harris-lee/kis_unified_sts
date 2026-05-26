"""Configuration loader for Strategy Lab."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("config/strategy_lab/defaults.yaml")


@lru_cache(maxsize=1)
def load_strategy_lab_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load Strategy Lab defaults from YAML."""
    cfg_path = Path(path)
    if not cfg_path.exists():
        return {}
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    strategy_lab = data.get("strategy_lab", {})
    return strategy_lab if isinstance(strategy_lab, dict) else {}


def get_lab_ttl_seconds() -> int:
    config = load_strategy_lab_config()
    return int(config.get("ttl_seconds", 86400))


def get_lab_position_ttl_seconds() -> int:
    config = load_strategy_lab_config()
    return int(config.get("position_ttl_seconds", 172800))


def get_default_order_amount() -> float:
    config = load_strategy_lab_config()
    return float(config.get("default_order_amount", 0.0))
