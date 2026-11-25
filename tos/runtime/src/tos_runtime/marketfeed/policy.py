"""``tos_runtime.marketfeed.policy`` — the Critical Input Policy (CIP) loader (TOS tick-source"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from tos.canonical import CanonicalizationScheme

__all__ = [
    "CRITICAL_INPUT_POLICY_CONFIG_NAME",
    "CriticalInputFieldPolicy",
    "CriticalInputPolicyConfigError",
    "LoadedCriticalInputPolicy",
    "load_critical_input_policy",
]

CRITICAL_INPUT_POLICY_CONFIG_NAME = "critical_input_policy.yaml"

_TOP_LEVEL_STR_KEYS: tuple[str, ...] = (
    "policy_id",
    "policy_version",
    "issuer_principal_id",
    "environment",
    "decision_class",
    "intended_use",
)

_FIELD_STR_KEYS: tuple[str, ...] = ("field_key", "unit", "scale", "multiplier", "sign")

_TBD_STR = "TBD"


class CriticalInputPolicyConfigError(RuntimeError):
    """A Critical Input Policy instance YAML is missing, malformed, or carries an unfilled"""


@dataclass(frozen=True)
class CriticalInputFieldPolicy:
    """One governed field admission rule (plan §2 decision 2, item (ii)/(iii))."""

    field_key: str
    unit: str
    scale: str
    multiplier: str
    sign: str
    max_age_ms: int


@dataclass(frozen=True)
class LoadedCriticalInputPolicy:
    """A loaded, digest-computed Critical Input Policy (module docstring)."""

    policy_id: str
    policy_version: str
    policy_generation: int
    issuer_principal_id: str
    environment: str
    decision_class: str
    intended_use: str
    fields: tuple[CriticalInputFieldPolicy, ...]
    fields_by_key: Mapping[str, CriticalInputFieldPolicy]
    canonical_digest: str


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CriticalInputPolicyConfigError(
            f"critical input policy config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CriticalInputPolicyConfigError(
            f"critical input policy config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CriticalInputPolicyConfigError(
            f"critical input policy config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise CriticalInputPolicyConfigError(
            f"{path}: critical input policy config must be a top-level mapping"
        )
    return raw


def _require_str(raw: Mapping[str, Any], key: str, path: Path, ctx: str) -> str:
    if key not in raw:
        raise CriticalInputPolicyConfigError(
            f"{path}: {ctx} missing required key {key!r}"
        )
    value = raw[key]
    if not isinstance(value, str) or not value.strip():
        raise CriticalInputPolicyConfigError(
            f"{path}: {ctx}.{key} is still null (named-TBD) or not a non-empty string"
        )
    if value == _TBD_STR:
        raise CriticalInputPolicyConfigError(
            f"{path}: {ctx}.{key} is still the template placeholder {_TBD_STR!r} — "
            "operator-fill before activation"
        )
    return value


def _require_int(raw: Mapping[str, Any], key: str, path: Path, ctx: str) -> int:
    if key not in raw:
        raise CriticalInputPolicyConfigError(
            f"{path}: {ctx} missing required key {key!r}"
        )
    value = raw[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise CriticalInputPolicyConfigError(
            f"{path}: {ctx}.{key} is still null (named-TBD) or not an int"
        )
    return value


def _parse_field_entry(
    entry: Any, index: int, path: Path, *, seen_keys: set[str]
) -> CriticalInputFieldPolicy:
    ctx = f"policy.fields[{index}]"
    if not isinstance(entry, dict):
        raise CriticalInputPolicyConfigError(f"{path}: {ctx} must be a mapping")
    values: dict[str, str] = {
        key: _require_str(entry, key, path, ctx) for key in _FIELD_STR_KEYS
    }
    field_key = values["field_key"]
    if field_key in seen_keys:
        raise CriticalInputPolicyConfigError(
            f"{path}: {ctx}.field_key {field_key!r} is a duplicate of an earlier entry — two "
            "rules for one field have no single admissible reading"
        )
    seen_keys.add(field_key)
    max_age_ms = _require_int(entry, "max_age_ms", path, ctx)
    if max_age_ms <= 0:
        raise CriticalInputPolicyConfigError(
            f"{path}: {ctx}.max_age_ms must be a positive int (got {max_age_ms!r}) — a "
            "non-positive freshness ceiling would admit nothing or everything, never a bound"
        )
    return CriticalInputFieldPolicy(
        field_key=field_key,
        unit=values["unit"],
        scale=values["scale"],
        multiplier=values["multiplier"],
        sign=values["sign"],
        max_age_ms=max_age_ms,
    )


def _parse_fields(
    raw: Mapping[str, Any], path: Path
) -> tuple[CriticalInputFieldPolicy, ...]:
    if "fields" not in raw or raw["fields"] is None:
        raise CriticalInputPolicyConfigError(
            f"{path}: policy.fields must be an explicit list (a missing key or null is a "
            "named-TBD gap)"
        )
    entries = raw["fields"]
    if not isinstance(entries, list):
        raise CriticalInputPolicyConfigError(f"{path}: policy.fields must be a list")
    if not entries:
        raise CriticalInputPolicyConfigError(
            f"{path}: policy.fields is empty — a policy that declares no admissible field "
            "admits nothing (module docstring); this is almost certainly a misfill, not a "
            "deliberate deny-all (a disabled CIS should not be wired up at all)"
        )
    seen_keys: set[str] = set()
    return tuple(
        _parse_field_entry(entry, i, path, seen_keys=seen_keys)
        for i, entry in enumerate(entries)
    )


def _covered_content(
    *,
    policy_id: str,
    policy_version: str,
    policy_generation: int,
    issuer_principal_id: str,
    environment: str,
    decision_class: str,
    intended_use: str,
    fields: tuple[CriticalInputFieldPolicy, ...],
) -> dict[str, Any]:
    """The digest preimage — every loaded field, key-sorted by the canonicalizer at digest time"""
    return {
        "policy_id": policy_id,
        "policy_version": policy_version,
        "policy_generation": policy_generation,
        "issuer_principal_id": issuer_principal_id,
        "environment": environment,
        "decision_class": decision_class,
        "intended_use": intended_use,
        "fields": [
            {
                "field_key": f.field_key,
                "unit": f.unit,
                "scale": f.scale,
                "multiplier": f.multiplier,
                "sign": f.sign,
                "max_age_ms": f.max_age_ms,
            }
            for f in fields
        ],
    }


def load_critical_input_policy(
    path: Path, *, scheme: CanonicalizationScheme
) -> LoadedCriticalInputPolicy:
    """Load and fail-closed-validate a Critical Input Policy INSTANCE document from ``path``."""
    raw = _load_mapping(path)
    (
        policy_id,
        policy_version,
        issuer_principal_id,
        environment,
        decision_class,
        intended_use,
    ) = (_require_str(raw, key, path, "policy") for key in _TOP_LEVEL_STR_KEYS)
    policy_generation = _require_int(raw, "policy_generation", path, "policy")
    fields = _parse_fields(raw, path)

    canonical_digest = scheme.compute_digest(
        _covered_content(
            policy_id=policy_id,
            policy_version=policy_version,
            policy_generation=policy_generation,
            issuer_principal_id=issuer_principal_id,
            environment=environment,
            decision_class=decision_class,
            intended_use=intended_use,
            fields=fields,
        )
    )

    return LoadedCriticalInputPolicy(
        policy_id=policy_id,
        policy_version=policy_version,
        policy_generation=policy_generation,
        issuer_principal_id=issuer_principal_id,
        environment=environment,
        decision_class=decision_class,
        intended_use=intended_use,
        fields=fields,
        fields_by_key={f.field_key: f for f in fields},
        canonical_digest=canonical_digest,
    )
