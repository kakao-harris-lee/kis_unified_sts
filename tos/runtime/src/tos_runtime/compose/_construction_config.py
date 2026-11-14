"""``tos_runtime.compose._construction_config`` — the ``construction.yaml`` loader (TOS ``run``"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from tos.venue import ActionClass

from tos_runtime.compose._types import ConstructionConfig

__all__ = [
    "CONSTRUCTION_CONFIG_NAME",
    "ConstructionConfigError",
    "load_construction_config",
]

CONSTRUCTION_CONFIG_NAME = "construction.yaml"

_TBD_STR = "TBD"

_KNOWN_KEYS: frozenset[str] = frozenset(
    {
        "account",
        "instrument",
        "action_class",
        "instrument_class",
        "outbound_side",
        "price_field_key",
        "shape_price_field_key",
    }
)

_STR_FIELDS: tuple[str, ...] = (
    "account",
    "instrument",
    "instrument_class",
    "outbound_side",
    "price_field_key",
    "shape_price_field_key",
)


class ConstructionConfigError(Exception):
    """Raised when ``construction.yaml`` is missing, malformed, carries an unrecognized"""


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConstructionConfigError(f"construction config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConstructionConfigError(
            f"construction config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConstructionConfigError(
            f"construction config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise ConstructionConfigError(
            f"{path}: construction config must be a top-level mapping"
        )
    unknown = set(raw) - _KNOWN_KEYS
    if unknown:
        raise ConstructionConfigError(
            f"{path}: unrecognized key(s) {sorted(unknown)!r} — known keys are "
            f"{sorted(_KNOWN_KEYS)!r}"
        )
    return raw


def _require_str(raw: dict[str, Any], key: str, path: Path) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConstructionConfigError(
            f"{path}: {key!r} is missing, still null (named-TBD), or not a non-empty string"
        )
    if value == _TBD_STR:
        raise ConstructionConfigError(
            f"{path}: {key!r} is still the template placeholder {_TBD_STR!r} — "
            "operator-fill before this deployment can boot"
        )
    return value


def _require_action_class(raw: dict[str, Any], path: Path) -> ActionClass:
    value = raw.get("action_class")
    if not isinstance(value, str) or not value.strip():
        raise ConstructionConfigError(
            f"{path}: 'action_class' is missing, still null (named-TBD), or not a "
            "non-empty string"
        )
    if value == _TBD_STR:
        raise ConstructionConfigError(
            f"{path}: 'action_class' is still the template placeholder {_TBD_STR!r} — "
            "operator-fill before this deployment can boot"
        )
    try:
        return ActionClass(value)
    except ValueError as exc:
        valid = [member.value for member in ActionClass]
        raise ConstructionConfigError(
            f"{path}: 'action_class'={value!r} is not a valid tos.venue.ActionClass "
            f"member ({valid}): {exc}"
        ) from exc


def load_construction_config(path: Path) -> ConstructionConfig:
    """Load + fail-closed-validate ``construction.yaml`` from ``path`` (shaped like"""
    raw = _load_mapping(path)
    action_class = _require_action_class(raw, path)
    str_values = {field: _require_str(raw, field, path) for field in _STR_FIELDS}
    return ConstructionConfig(
        account=str_values["account"],
        instrument=str_values["instrument"],
        price=None,
        action_class=action_class,
        instrument_class=str_values["instrument_class"],
        outbound_side=str_values["outbound_side"],
        price_field_key=str_values["price_field_key"],
        shape_price_field_key=str_values["shape_price_field_key"],
    )
