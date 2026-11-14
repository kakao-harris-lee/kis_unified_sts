"""``tos_runtime.riskstate._riskstate_primitives`` — the SHARED YAML-parsing helpers both"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from tos_runtime.venue._policy_primitives import (
    TEMPLATE_MAPPING_KEYS,
    VenuePolicyConfigError,
    require_list,
    require_str_list,
)

__all__ = [
    "RISK_TEMPLATE_MAPPING_KEYS",
    "require_explicit_list_str",
    "require_nonnegative_decimal",
]

RISK_TEMPLATE_MAPPING_KEYS: tuple[str, ...] = (
    *TEMPLATE_MAPPING_KEYS,
    "hard_safety_envelope",
    "runtime_safety_profile",
)


def require_explicit_list_str(
    raw: Mapping[str, Any], key: str, path: Path, ctx: str
) -> tuple[str, ...]:
    """An explicit-list-of-strings top-level policy key (``[]`` accepted) — shared by every"""
    entries = require_list(dict(raw), key, path, ctx)
    return require_str_list(entries, path, f"{ctx}.{key}")


def require_nonnegative_decimal(value: Any, path: Path, ctx: str) -> Decimal:
    """A decimal-shaped, non-negative magnitude — shared by ARE's ``effective_limits`` and"""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise VenuePolicyConfigError(
            f"{path}: {ctx} must be a decimal-shaped string or int"
        )
    try:
        magnitude = Decimal(str(value))
    except InvalidOperation as exc:
        raise VenuePolicyConfigError(f"{path}: {ctx} is not a valid decimal") from exc
    if magnitude < 0:
        raise VenuePolicyConfigError(
            f"{path}: {ctx} must be non-negative (got {magnitude})"
        )
    return magnitude
