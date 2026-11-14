"""Shared YAML-policy loading helpers for the W3-a1 safety-mesh services"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tos_runtime._named_tbd import reject_named_tbd

__all__ = [
    "PolicyLoadError",
    "load_yaml_document",
    "require_mapping_field",
    "require_bool_field",
    "require_int_field",
    "require_str_field",
    "require_list_field",
]


class PolicyLoadError(Exception):
    """Raised by a caller when a loaded document is missing, malformed, or"""


def load_yaml_document(path: Path, error_cls: type[Exception]) -> dict[str, Any]:
    """Read + parse ``path`` as a top-level YAML mapping, fail-closed."""
    if not path.is_file():
        raise error_cls(f"policy config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise error_cls(f"policy config file could not be read: {path}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise error_cls(f"policy config file is not valid YAML: {path}") from exc
    if not isinstance(raw, dict):
        raise error_cls(
            f"policy config file must be a top-level mapping: {path} (got {type(raw)!r})"
        )
    return raw


def require_mapping_field(
    raw: dict[str, Any], key: str, path: Path, error_cls: type[Exception]
) -> dict[str, Any]:
    """Return ``raw[key]`` as a non-null mapping, or raise ``error_cls``."""
    if key not in raw:
        raise error_cls(f"{path}: missing required mapping key {key!r}")
    value = raw[key]
    if value is None:
        raise error_cls(
            f"{path}: {key!r} is still null (named-TBD) — refusing to start "
            "until an operator fills it"
        )
    if not isinstance(value, dict):
        raise error_cls(f"{path}: {key!r} must be a mapping (got {type(value)!r})")
    return value


def require_bool_field(
    raw: dict[str, Any], key: str, path: Path, error_cls: type[Exception]
) -> bool:
    """Return ``raw[key]`` as a non-null ``bool``, or raise ``error_cls``."""
    if key not in raw:
        raise error_cls(f"{path}: missing required bool key {key!r}")
    value = raw[key]
    if value is None:
        raise error_cls(
            f"{path}: {key!r} is still null (named-TBD) — refusing to start "
            "until an operator fills it"
        )
    if not isinstance(value, bool):
        raise error_cls(f"{path}: {key!r} must be a bool (got {type(value)!r})")
    return value


def require_int_field(
    raw: dict[str, Any], key: str, path: Path, error_cls: type[Exception]
) -> int:
    """Return ``raw[key]`` as a non-null ``int``, or raise ``error_cls``."""
    if key not in raw:
        raise error_cls(f"{path}: missing required int key {key!r}")
    value = raw[key]
    if value is None:
        raise error_cls(
            f"{path}: {key!r} is still null (named-TBD) — refusing to start "
            "until an operator fills it"
        )
    if isinstance(value, bool) or not isinstance(value, int):
        raise error_cls(f"{path}: {key!r} must be an int (got {value!r})")
    return value


def require_str_field(
    raw: dict[str, Any], key: str, path: Path, error_cls: type[Exception]
) -> str:
    """Return ``raw[key]`` as a non-null, non-blank ``str``, or raise ``error_cls``."""
    if key not in raw:
        raise error_cls(f"{path}: missing required str key {key!r}")
    value = raw[key]
    if value is None:
        raise error_cls(
            f"{path}: {key!r} is still null (named-TBD) — refusing to start "
            "until an operator fills it"
        )
    if not isinstance(value, str) or not value.strip():
        raise error_cls(f"{path}: {key!r} must be a non-blank string (got {value!r})")
    reject_named_tbd(value, field=key, context=str(path), error_cls=error_cls)
    return value


def require_list_field(
    raw: dict[str, Any], key: str, path: Path, error_cls: type[Exception]
) -> list[Any]:
    """Return ``raw[key]`` as an explicit (possibly empty) ``list``."""
    if key not in raw:
        raise error_cls(f"{path}: missing required list key {key!r}")
    value = raw[key]
    if value is None:
        raise error_cls(
            f"{path}: {key!r} is null — an explicit empty list ([]) is required "
            "to state 'none', not a bare null"
        )
    if not isinstance(value, list):
        raise error_cls(f"{path}: {key!r} must be a list (got {type(value)!r})")
    return value
