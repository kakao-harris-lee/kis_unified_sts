"""Currentness runtime config loader (design #40 §5 order 6, lane R).

Loads ``tos/runtime/config/currentness.example.yaml`` (or an
operator-approved copy). The one VER-002 profile key this lane consumes is
``B_capability_claim_to_send`` (`tos-spec/src/part-1-foundation/verification/
VERIFICATION-PROFILE-002.yaml` line 301 — approved ``value_ms: 500``, but
marked "RECHECK: APPROVE after the fenced egress journal and broker
transport are implemented"). Phase 2 does not implement that measurement
path (no real broker transport exists yet), so — matching
``tos_runtime.time.config``'s own discipline of keeping a key ``null`` at its
own consumption site even where an upstream VER-002 entry already carries an
approved number — this loader keeps the key ``null`` (named-TBD) until an
operator explicitly approves it for *this* consumption site, and fails
closed at load time until then.

Also loads ``required_dimensions`` (Phase 5 W3-b, W3.1 independent review MEDIUM-3) —
the operator-declared CURRENTNESS_POLICY dimension set, a non-empty list of valid
``tos.cur.DimensionKey`` names, fail-closed on missing/``null``/empty/unknown/
duplicate entries; see :data:`_REQUIRED_DIMENSIONS_KEY`'s own docstring for why this
must be a genuine, independently-editable declaration rather than one this module
re-derives from the kernel's own mandated floor.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from tos.cur import DimensionKey

__all__ = ["CurrentnessConfig", "CurrentnessConfigError", "load_currentness_config"]


class CurrentnessConfigError(Exception):
    """Raised when the currentness config is missing, malformed, or carries
    an unfilled (missing/null) required key — fail-closed at load."""


#: The one VER-002 profile key this lane consumes, named verbatim (module
#: docstring). ``None`` (named-TBD) is refused until a Bounds-Approver
#: decision fills it for this consumption site.
_BOUND_KEY = "B_capability_claim_to_send"

#: The operator-declared CURRENTNESS_POLICY dimension set (Phase 5 W3-b, plan §2
#: decision 3; W3.1 independent review MEDIUM-3). Read verbatim into
#: ``CurrentnessPolicy.required_dimensions`` by ``_currentness_wiring.py`` — never
#: fabricated FROM ``tos.cur.MANDATED_DIMENSION_FLOOR`` at construction time (the
#: original bug: a policy built by copying the kernel's own floor trivially "covers"
#: that same floor, so the CURRENTNESS_POLICY dimension reader's
#: ``policy_covers_mandated_dimensions`` check was asking whether the floor it had just
#: issued covers the floor — a tautology no operator YAML value could ever change).
#: This key is the genuine, independently-editable declaration that check now compares
#: against the kernel's floor.
_REQUIRED_DIMENSIONS_KEY = "required_dimensions"


@dataclass(frozen=True)
class CurrentnessConfig:
    """Fully-valued currentness runtime configuration.

    ``max_claim_to_send_bound_ms`` feeds
    :meth:`~tos_runtime.currentness.proof.EgressCurrentnessProofIssuer.issue`'s
    ``max_claim_to_send_bound_ms`` argument, matching the field name
    ``tos.cur.EgressCurrentnessProof.max_claim_to_send_bound_ms`` itself
    carries (a Profile-INSTANCE bound, ADR-002-024 §8).

    ``required_dimensions`` is the operator-declared CURRENTNESS_POLICY dimension set
    (module docstring, MEDIUM-3) — fed straight into
    ``CurrentnessPolicy.required_dimensions`` by ``_currentness_wiring.py``'s
    ``_build_risk_and_currentness``, never re-derived from
    :data:`~tos.cur.MANDATED_DIMENSION_FLOOR` at construction time.
    """

    max_claim_to_send_bound_ms: int
    required_dimensions: tuple[DimensionKey, ...]


def load_currentness_config(path: Path) -> CurrentnessConfig:
    """Load + validate the currentness config file, fail-closed.

    Args:
        path: Path to a YAML file shaped like
            ``tos/runtime/config/currentness.example.yaml``.

    Returns:
        A fully-valued :class:`CurrentnessConfig`.

    Raises:
        CurrentnessConfigError: The file is missing/unreadable/not valid
            YAML/not a mapping, the required key is missing or still
            ``null`` (named-TBD), or its value fails its type/sign check.
    """
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
    """Load + fail-closed-validate ``required_dimensions`` (MEDIUM-3, module
    docstring) — a non-empty list of valid, non-duplicate ``DimensionKey`` names, never
    missing/``null``/empty/malformed."""
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
            dimensions.append(DimensionKey(entry))
        except ValueError as exc:
            raise CurrentnessConfigError(
                f"currentness config key {_REQUIRED_DIMENSIONS_KEY!r} names an unknown "
                f"DimensionKey: {entry!r} in {path}"
            ) from exc
    if len(set(dimensions)) != len(dimensions):
        raise CurrentnessConfigError(
            f"currentness config key {_REQUIRED_DIMENSIONS_KEY!r} carries a duplicate "
            f"DimensionKey entry in {path}"
        )
    return tuple(dimensions)
