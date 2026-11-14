"""Currentness runtime config loader (design #40 §5 order 6, lane R)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from tos.cur import RETIRED_DIMENSION_KEYS, DimensionKey

__all__ = ["CurrentnessConfig", "CurrentnessConfigError", "load_currentness_config"]


class CurrentnessConfigError(Exception):
    """Raised when the currentness config is missing, malformed, or carries"""


_BOUND_KEY = "B_capability_claim_to_send"

_REQUIRED_DIMENSIONS_KEY = "required_dimensions"


@dataclass(frozen=True)
class CurrentnessConfig:
    """Fully-valued currentness runtime configuration."""

    max_claim_to_send_bound_ms: int
    required_dimensions: tuple[DimensionKey, ...]


def load_currentness_config(path: Path) -> CurrentnessConfig:
    """Load + validate the currentness config file, fail-closed."""
    if not path.is_file():
        raise CurrentnessConfigError(f"currentness config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CurrentnessConfigError(
            f"currentness config file could not be read: {path}"
        ) from exc
    try:
        raw: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CurrentnessConfigError(
            f"currentness config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise CurrentnessConfigError(
            f"currentness config file must be a top-level mapping: {path} "
            f"(got {type(raw)!r})"
        )
    if _BOUND_KEY not in raw:
        raise CurrentnessConfigError(
            f"currentness config missing required key: {_BOUND_KEY!r}"
        )
    value = raw[_BOUND_KEY]
    if value is None:
        raise CurrentnessConfigError(
            "currentness config has an unfilled (named-TBD) key — fail-closed "
            f"at startup until a Bounds-Approver decision fills it: {_BOUND_KEY!r}"
        )
    if isinstance(value, bool) or not isinstance(value, int):
        raise CurrentnessConfigError(
            f"currentness config key {_BOUND_KEY!r} must be a non-negative int "
            f"(got {value!r})"
        )
    if value < 0:
        raise CurrentnessConfigError(
            f"currentness config key {_BOUND_KEY!r} must be non-negative "
            f"(got {value!r})"
        )
    required_dimensions = _load_required_dimensions(raw, path)
    return CurrentnessConfig(
        max_claim_to_send_bound_ms=value, required_dimensions=required_dimensions
    )


def _load_required_dimensions(
    raw: dict[str, Any], path: Path
) -> tuple[DimensionKey, ...]:
    """Load + fail-closed-validate ``required_dimensions`` (MEDIUM-3, module"""
    if _REQUIRED_DIMENSIONS_KEY not in raw:
        raise CurrentnessConfigError(
            f"currentness config missing required key: {_REQUIRED_DIMENSIONS_KEY!r}"
        )
    raw_dimensions = raw[_REQUIRED_DIMENSIONS_KEY]
    if raw_dimensions is None:
        raise CurrentnessConfigError(
            "currentness config has an unfilled (named-TBD) key — fail-closed at "
            f"startup until an operator declares it: {_REQUIRED_DIMENSIONS_KEY!r}"
        )
    if not isinstance(raw_dimensions, list) or not raw_dimensions:
        raise CurrentnessConfigError(
            f"currentness config key {_REQUIRED_DIMENSIONS_KEY!r} must be a "
            f"non-empty list (got {raw_dimensions!r})"
        )
    dimensions: list[DimensionKey] = []
    for entry in raw_dimensions:
        if not isinstance(entry, str):
            raise CurrentnessConfigError(
                f"currentness config key {_REQUIRED_DIMENSIONS_KEY!r} entry must be a "
                f"string DimensionKey name (got {entry!r}) in {path}"
            )
        try:
            key = DimensionKey(entry)
        except ValueError as exc:
            raise CurrentnessConfigError(
                f"currentness config key {_REQUIRED_DIMENSIONS_KEY!r} names an unknown "
                f"DimensionKey: {entry!r} in {path}"
            ) from exc
        if key in RETIRED_DIMENSION_KEYS:
            raise CurrentnessConfigError(
                f"currentness config key {_REQUIRED_DIMENSIONS_KEY!r} names a retired "
                f"DimensionKey (plan S2-b): {entry!r} in {path} — remove it"
            )
        dimensions.append(key)
    if len(set(dimensions)) != len(dimensions):
        raise CurrentnessConfigError(
            f"currentness config key {_REQUIRED_DIMENSIONS_KEY!r} carries a duplicate "
            f"DimensionKey entry in {path}"
        )
    return tuple(dimensions)
