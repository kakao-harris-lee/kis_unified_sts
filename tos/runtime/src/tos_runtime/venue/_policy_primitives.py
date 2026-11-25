"""tos_runtime.venue._policy_primitives — shared YAML-loading primitives and"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from tos.canonical import ArtifactStatus
from tos.venue import ActionClass

__all__ = [
    "VenuePolicyConfigError",
    "TBD_DIGEST",
    "TBD_STR",
    "ACCEPTED_SCHEMA_VERSION",
    "TEMPLATE_MAPPING_KEYS",
]


class VenuePolicyConfigError(RuntimeError):
    """A venue / order-construction policy instance YAML is missing,"""


ACCEPTED_SCHEMA_VERSION = "1.0-DRAFT"

TBD_DIGEST = "TBD"

TBD_STR = "TBD"

TEMPLATE_MAPPING_KEYS: tuple[str, ...] = ("authority", "evidence")


def load_mapping(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise VenuePolicyConfigError(f"{label} config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VenuePolicyConfigError(
            f"{label} config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise VenuePolicyConfigError(
            f"{label} config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise VenuePolicyConfigError(
            f"{path}: {label} config must be a top-level mapping"
        )
    return raw


def require_str(raw: dict[str, Any], key: str, path: Path, ctx: str) -> str:
    if key not in raw:
        raise VenuePolicyConfigError(f"{path}: {ctx} missing required key {key!r}")
    value = raw[key]
    if not isinstance(value, str) or not value:
        raise VenuePolicyConfigError(
            f"{path}: {ctx} {key!r} is still null (named-TBD) or not a non-empty string"
        )
    return value


def require_filled_str(raw: dict[str, Any], key: str, path: Path, ctx: str) -> str:
    """Like :func:`require_str`, but ALSO refuses the template's own"""
    value = require_str(raw, key, path, ctx)
    if value == TBD_STR:
        raise VenuePolicyConfigError(
            f"{path}: {ctx} {key!r} is still the template placeholder {TBD_STR!r}"
        )
    return value


def require_int(raw: dict[str, Any], key: str, path: Path, ctx: str) -> int:
    if key not in raw:
        raise VenuePolicyConfigError(f"{path}: {ctx} missing required key {key!r}")
    value = raw[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise VenuePolicyConfigError(
            f"{path}: {ctx} {key!r} is still null (named-TBD) or not an int"
        )
    return value


def optional_int(raw: dict[str, Any], key: str, path: Path, ctx: str) -> int | None:
    if key not in raw:
        raise VenuePolicyConfigError(f"{path}: {ctx} missing required key {key!r}")
    value = raw[key]
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise VenuePolicyConfigError(f"{path}: {ctx} {key!r} must be an int or null")
    return value


def optional_str(raw: dict[str, Any], key: str, path: Path, ctx: str) -> str | None:
    """Like :func:`optional_int`, for a nullable string key (kernel round #4 K-3 —"""
    if key not in raw:
        raise VenuePolicyConfigError(f"{path}: {ctx} missing required key {key!r}")
    value = raw[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise VenuePolicyConfigError(f"{path}: {ctx} {key!r} must be a string or null")
    if value == TBD_STR:
        raise VenuePolicyConfigError(
            f"{path}: {ctx} {key!r} is still the template placeholder {TBD_STR!r}"
        )
    return value


def require_list(raw: dict[str, Any], key: str, path: Path, ctx: str) -> list[Any]:
    if key not in raw or raw[key] is None:
        raise VenuePolicyConfigError(
            f"{path}: {ctx} {key!r} must be an explicit list ([] accepted; "
            "a missing key or null is a named-TBD gap)"
        )
    value = raw[key]
    if not isinstance(value, list):
        raise VenuePolicyConfigError(f"{path}: {ctx} {key!r} must be a list")
    return value


def require_mapping_key(raw: dict[str, Any], key: str, path: Path) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise VenuePolicyConfigError(f"{path}: {key!r} must be an explicit mapping")
    return value


def require_nullable_str_key_present(
    raw: dict[str, Any], key: str, path: Path, ctx: str
) -> None:
    """Require ``key`` to be PRESENT (DR-0002 §2.1 "every template key is"""
    if key not in raw:
        raise VenuePolicyConfigError(f"{path}: {ctx} missing required key {key!r}")
    value = raw[key]
    if value is not None and not isinstance(value, str):
        raise VenuePolicyConfigError(f"{path}: {ctx} {key!r} must be a string or null")


def require_str_list(entries: list[Any], path: Path, ctx: str) -> tuple[str, ...]:
    for entry in entries:
        if not isinstance(entry, str):
            raise VenuePolicyConfigError(f"{path}: {ctx} entries must be strings")
    return tuple(entries)


def require_exact_str(
    raw: dict[str, Any], key: str, expected: str, path: Path, ctx: str
) -> None:
    value = raw.get(key)
    if value != expected:
        raise VenuePolicyConfigError(
            f"{path}: {ctx} {key!r} must equal {expected!r} (got {value!r})"
        )


def require_issued_status(raw: dict[str, Any], path: Path) -> None:
    status = raw.get("status")
    if status != ArtifactStatus.ISSUED.value:
        raise VenuePolicyConfigError(
            f"{path}: 'status' must be {ArtifactStatus.ISSUED.value!r} — a "
            f"DRAFT (or any other non-ISSUED) policy cannot be activated "
            f"(got {status!r})"
        )


def check_canonical_digest(
    raw: dict[str, Any], path: Path, computed_digest: str | None, ctx: str
) -> None:
    """Cross-check the document's own ``canonical_digest`` against the"""
    value = raw.get("canonical_digest")
    if value == TBD_DIGEST:
        return
    if not isinstance(value, str):
        raise VenuePolicyConfigError(
            f"{path}: {ctx} canonical_digest must be a string or "
            f"{TBD_DIGEST!r} (got {value!r})"
        )
    if value != computed_digest:
        raise VenuePolicyConfigError(
            f"{path}: {ctx} canonical_digest {value!r} != the freshly "
            f"computed digest {computed_digest!r} — refusing (tamper/stale "
            "detection)"
        )


def require_template_shape(
    raw: dict[str, Any],
    path: Path,
    *,
    list_keys: tuple[str, ...],
    mapping_keys: tuple[str, ...],
) -> None:
    """Presence/shape-only fidelity check over every template rule-list /"""
    for key in list_keys:
        require_list(raw, key, path, "policy")
    for key in mapping_keys:
        require_mapping_key(raw, key, path)


def parse_action_classes(
    scope_raw: dict[str, Any], path: Path, ctx: str
) -> frozenset[ActionClass]:
    entries = require_list(scope_raw, "action_classes", path, ctx)
    classes: set[ActionClass] = set()
    for token in entries:
        if not isinstance(token, str):
            raise VenuePolicyConfigError(
                f"{path}: {ctx}.action_classes entries must be strings"
            )
        try:
            classes.add(ActionClass(token))
        except ValueError as exc:
            raise VenuePolicyConfigError(
                f"{path}: {ctx}.action_classes {token!r} is not a known ActionClass"
            ) from exc
    return frozenset(classes)


def require_singleton_list_str(
    scope_raw: dict[str, Any], key: str, path: Path, ctx: str
) -> str:
    entries = require_list(scope_raw, key, path, ctx)
    values = require_str_list(entries, path, f"{ctx}.{key}")
    if len(values) != 1:
        raise VenuePolicyConfigError(
            f"{path}: {ctx}.{key} must be a list of EXACTLY one string for a "
            f"single live scope (v1) — got {len(values)}"
        )
    if values[0] == TBD_STR or not values[0].strip():
        raise VenuePolicyConfigError(
            f"{path}: {ctx}.{key} is still {TBD_STR!r}/empty (named-TBD) — fill the "
            "deployment coordinate before activation"
        )
    return values[0]
