"""``tos_runtime.marketfeed.policy`` — the Critical Input Policy (CIP) loader (TOS tick-source
wave, plan ``docs/plans/2026-09-16-tos-tick-source-plan.md`` §2 decision 2).

The tick source's own governed policy, loaded with the SAME fail-closed idiom the venue / risk
policy loaders already ship (:mod:`tos_runtime.venue._venue_policy_loader`,
:mod:`tos_runtime.riskstate._aggregate_risk_policy_loader`): every leaf is named-TBD (``null`` in
the shipped ``.example.yaml``) and a still-null or missing required leaf refuses to load, naming
the offending key. Unlike those three artifacts, a Critical Input Policy is **not itself a
kernel-issued artifact type** — ``tos.capsule`` only carries a content *reference* to it
(:class:`~tos.capsule.PolicyRef`: ``policy_id`` + ``policy_generation`` + ``canonical_digest``,
``tos/src/tos/capsule/_base.py:90-99``), never the policy body. This loader therefore computes the
``canonical_digest`` itself, over the loaded document's own covered content, with the injected
:class:`~tos.canonical.CanonicalizationScheme` — the same digest algorithm the kernel artifacts use
(``scheme.compute_digest``), just without a kernel ``.issue()`` call to drive it (there is no kernel
type to issue).

**Why an empty ``fields:`` list refuses (plan §2 decision 2).** A policy that declares no
admissible field admits nothing downstream — every value a producer could ever claim would fail
:func:`tos.marketfeed.value.value_field_state`'s ∅ floor (no evaluation names the key ⇒ UNKNOWN) —
so an empty list is almost certainly a misfill, not a deliberate "admit nothing" policy (a fully
disabled CIS would simply not be wired up at all). Refusing early keeps that failure at load time,
not silently at every publish.

**Why the loader owns per-field validation** (not a nested kernel schema): the CIP's
``fields[].max_age_ms`` is a genuinely new governed value — this wave's own VER-002-adjacent
freshness bound (plan §6 operator confirmation ②) — with no kernel counterpart to defer to, unlike
the venue/risk loaders' ``_model_view``/``_runtime`` split which cross-checks against real kernel
enums (``RiskDimensionKind``, ``ActionClassKind``, ...). This loader is therefore intentionally
flatter than those three: no ``_model_view``/``_runtime`` split, no ``status: ISSUED`` template
envelope, no stored ``canonical_digest`` to tamper-check against (the shipped example carries none)
— just the flat shape the task's own contract names.

Firewall (R1, runtime scope): stdlib + ``pyyaml`` + ``tos.*`` only — no ``shared.*``, no
``os.environ``/``subprocess``/``importlib.import_module`` (``tools/tos_firewall_check.py`` scans
tests too).
"""

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

#: The runtime INSTANCE file name (distinct from an example/template file name).
CRITICAL_INPUT_POLICY_CONFIG_NAME = "critical_input_policy.yaml"

#: The top-level scalar keys, in the order the shipped example declares them.
_TOP_LEVEL_STR_KEYS: tuple[str, ...] = (
    "policy_id",
    "policy_version",
    "issuer_principal_id",
    "environment",
    "decision_class",
    "intended_use",
)

#: ``fields[]`` entry scalar-string keys (``max_age_ms`` is handled separately — it is an int).
_FIELD_STR_KEYS: tuple[str, ...] = ("field_key", "unit", "scale", "multiplier", "sign")


class CriticalInputPolicyConfigError(RuntimeError):
    """A Critical Input Policy instance YAML is missing, malformed, or carries an unfilled
    (named-TBD, i.e. still-``null``) required leaf — fail-closed at load, never a silent
    default (module docstring)."""


@dataclass(frozen=True)
class CriticalInputFieldPolicy:
    """One governed field admission rule (plan §2 decision 2, item (ii)/(iii)).

    ``unit``/``scale``/``multiplier``/``sign`` are carried as separate string attributes —
    "economically significant *distinct* safety fields" per
    ``tos/src/tos/capsule/observation.py``'s own ``Mapping`` docstring, which this policy's shape
    exists to feed (:mod:`tos_runtime.marketfeed.snapshot`) — never folded into one combined token.
    """

    field_key: str
    unit: str
    scale: str
    multiplier: str
    sign: str
    #: Freshness ceiling for this field, milliseconds (plan §2 decision 2 item (iii); plan §6
    #: operator confirmation ② — a wave-local bound, not yet a VER-002 registry key).
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
    #: ``field_key -> spec`` — the same fields, indexed for O(1) lookup by
    #: :mod:`tos_runtime.marketfeed.snapshot` (declaration order preserved in ``fields`` above for
    #: any caller that needs a deterministic "first declared" tie-break).
    fields_by_key: Mapping[str, CriticalInputFieldPolicy]
    #: Computed with the injected scheme over this document's own covered content — see module
    #: docstring for why this is computed rather than kernel-issued.
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
    """The digest preimage — every loaded field, key-sorted by the canonicalizer at digest time
    (mappings only; ``fields`` stays list-ordered, matching the document's own declaration order,
    so a reordering of otherwise-identical rules is a distinct policy)."""
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
    """Load and fail-closed-validate a Critical Input Policy INSTANCE document from ``path``.

    Args:
        path: The YAML instance file (see module docstring for the shape; every leaf is
            named-TBD in the shipped ``.example.yaml``).
        scheme: The injected canonicalization scheme, used to compute ``canonical_digest`` over
            the loaded document's own covered content (module docstring — this is not a
            kernel-issued artifact, so there is no ``.issue()`` to drive the computation).

    Returns:
        The loaded policy plus its computed ``canonical_digest``.

    Raises:
        CriticalInputPolicyConfigError: the file is missing/unreadable/not valid YAML/not a
            mapping; any top-level scalar (``policy_id``/``policy_version``/``policy_generation``/
            ``issuer_principal_id``/``environment``/``decision_class``/``intended_use``) is
            absent, ``null``, or (for the strings) blank; ``fields`` is absent, ``null``, not a
            list, or empty; a ``fields[]`` entry is not a mapping, carries a duplicate
            ``field_key``, an absent/blank/non-string ``unit``/``scale``/``multiplier``/``sign``,
            or a ``max_age_ms`` that is absent, ``null``, not an int, or not strictly positive.
    """
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
