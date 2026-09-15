"""Shared YAML-policy loading helpers for the W3-a1 safety-mesh services
(:mod:`tos_runtime.safety.profile`, :mod:`tos_runtime.safety.deviation`).

Both services load an operator policy document and fail closed at
construction — never a lazily-discovered ``None`` deep inside ``clear()`` —
mirroring the "null == named-TBD ⇒ boot refusal" discipline every
``tos_runtime.*.config`` loader in this codebase already applies
(:mod:`tos_runtime.posttrade.config`, :mod:`tos_runtime.compose
._egress_attestations`). This module is a **private** helper: it holds no
policy-specific field name, so it stays reusable across the two lane files
without becoming a shared cross-lane surface (plan §4 file-ownership rule —
this file belongs to W3-a1 alone).

Pure module: stdlib + ``yaml`` only; no ``shared.*``, no ``tos.*`` import (a
generic mapping/scalar reader has no reason to know a kernel record shape).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

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
    """Raised by a caller when a loaded document is missing, malformed, or
    still carries an unfilled (named-TBD ``null``) required field. Each
    service module raises its own subclass so a test / operator can tell
    ``SafetyProfileService`` config errors from ``DeviationService`` ones by
    type; this base class exists only so shared helper functions below have
    one signature to raise via a caller-supplied subclass."""


def load_yaml_document(path: Path, error_cls: type[Exception]) -> dict[str, Any]:
    """Read + parse ``path`` as a top-level YAML mapping, fail-closed.

    Args:
        path: Path to a YAML file.
        error_cls: The caller's own error type to raise on any failure (so
            each service's boot-refusal exception type is preserved).

    Returns:
        The parsed top-level mapping.

    Raises:
        error_cls: The file is missing, unreadable, not valid YAML, or its
            top-level value is not a mapping.
    """
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
    return value


def require_list_field(
    raw: dict[str, Any], key: str, path: Path, error_cls: type[Exception]
) -> list[Any]:
    """Return ``raw[key]`` as an explicit (possibly empty) ``list``.

    ``null`` refuses to load — an *explicit empty list* (``[]``) is the only
    spelling of "nothing here" a policy document may use (plan §2 decisions
    2/3: "명시적 빈 리스트 허용" for the deviation / incident active sets).
    """
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
