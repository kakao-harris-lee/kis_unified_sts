"""``tos_runtime.riskstate._riskstate_primitives`` — the SHARED YAML-parsing helpers both
Aggregate Risk Policy and Action Flow Policy INSTANCE loaders use (team-lead disposition
2026-09-16, review of PR #704 item T1: split ``policies.py`` the same way
``tos_runtime/venue/config.py`` was split — ``_policy_primitives.py``'s own shared-helper
role, mirrored here).

Nothing here is copied from :mod:`tos_runtime.venue._policy_primitives` — that module's own
fail-closed YAML primitives (``load_mapping``, ``require_*``, ``check_canonical_digest``,
``require_template_shape``, ``VenuePolicyConfigError``) are imported and reused by BOTH
sibling loader modules directly; this module holds only the handful of helpers genuinely
shared BETWEEN the two riskstate loaders themselves (a decimal-magnitude parser and an
explicit-string-list parser, both used by the ARE and AFG loaders identically) plus the one
top-level mapping-key tuple both templates share (the ``hard_safety_envelope``/
``runtime_safety_profile`` presence-only block, plan §2.1's own "both templates carry" note).

Firewall (R1, runtime scope): stdlib + ``tos_runtime.venue._policy_primitives`` only.
"""

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

#: Both templates carry a ``hard_safety_envelope``/``runtime_safety_profile`` top-level
#: mapping block (``{envelope_id|profile_id, generation, canonical_digest}``, all null/TBD in
#: the template) alongside ``authority``/``evidence`` — same presence-only discipline (neither
#: loader interprets their content; the actual HSE cross-check is a lane b wiring-time
#: concern, :mod:`tos_runtime.compose._riskstate_wiring`).
RISK_TEMPLATE_MAPPING_KEYS: tuple[str, ...] = (
    *TEMPLATE_MAPPING_KEYS,
    "hard_safety_envelope",
    "runtime_safety_profile",
)


def require_explicit_list_str(
    raw: Mapping[str, Any], key: str, path: Path, ctx: str
) -> tuple[str, ...]:
    """An explicit-list-of-strings top-level policy key (``[]`` accepted) — shared by every
    ARE/AFG scope-array key that is NOT the ARE singleton pair (that one needs an
    exactly-one-entry check the ARE loader owns alone)."""
    entries = require_list(dict(raw), key, path, ctx)
    return require_str_list(entries, path, f"{ctx}.{key}")


def require_nonnegative_decimal(value: Any, path: Path, ctx: str) -> Decimal:
    """A decimal-shaped, non-negative magnitude — shared by ARE's ``effective_limits`` and
    AFG's ``limits`` (both ``_runtime`` mappings of ``dimension_id -> magnitude``)."""
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
