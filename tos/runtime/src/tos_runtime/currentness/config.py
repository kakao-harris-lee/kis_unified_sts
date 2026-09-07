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
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

__all__ = ["CurrentnessConfig", "CurrentnessConfigError", "load_currentness_config"]


class CurrentnessConfigError(Exception):
    """Raised when the currentness config is missing, malformed, or carries
    an unfilled (missing/null) required key — fail-closed at load."""


#: The one VER-002 profile key this lane consumes, named verbatim (module
#: docstring). ``None`` (named-TBD) is refused until a Bounds-Approver
#: decision fills it for this consumption site.
_BOUND_KEY = "B_capability_claim_to_send"


@dataclass(frozen=True)
class CurrentnessConfig:
    """Fully-valued currentness runtime configuration.

    ``max_claim_to_send_bound_ms`` feeds
    :meth:`~tos_runtime.currentness.proof.EgressCurrentnessProofIssuer.issue`'s
    ``max_claim_to_send_bound_ms`` argument, matching the field name
    ``tos.cur.EgressCurrentnessProof.max_claim_to_send_bound_ms`` itself
    carries (a Profile-INSTANCE bound, ADR-002-024 §8).
    """

    max_claim_to_send_bound_ms: int


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
    return CurrentnessConfig(max_claim_to_send_bound_ms=value)
