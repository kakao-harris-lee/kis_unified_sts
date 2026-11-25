"""Operator-configured ``EngineConfiguration`` bounds (pre-merge fix F5,"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

__all__ = ["EngineConfig", "EngineConfigError", "load_engine_config"]

_FIELDS: tuple[str, ...] = (
    "dsl_evaluation_budget_steps",
    "max_unresolved_send_per_scope",
)


class EngineConfigError(Exception):
    """Raised when the engine config is missing, malformed, or carries an"""


@dataclass(frozen=True)
class EngineConfig:
    """The two operator-configured ``EngineConfiguration`` bounds (module"""

    dsl_evaluation_budget_steps: int
    max_unresolved_send_per_scope: int


def _require_int(raw: Any, field: str, path: Path) -> int:
    value = raw.get(field) if isinstance(raw, dict) else None
    if isinstance(value, bool) or not isinstance(value, int):
        raise EngineConfigError(
            f"{path}: {field!r} is missing, still null (named-TBD), or not "
            "an int — refusing to start until an operator supplies a "
            "concrete value"
        )
    return value


def load_engine_config(path: Path) -> EngineConfig:
    """Load + fail-closed-validate the engine bounds from ``path`` (shaped"""
    if not path.is_file():
        raise EngineConfigError(f"engine config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EngineConfigError(
            f"engine config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise EngineConfigError(
            f"engine config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise EngineConfigError(
            f"engine config file must be a top-level mapping: {path}"
        )
    values = {field: _require_int(raw, field, path) for field in _FIELDS}
    return EngineConfig(**values)
