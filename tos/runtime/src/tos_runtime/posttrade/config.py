"""SYNTHETIC post-trade finality runtime config loader (TOS Phase 3 Wave 2 Lane C-R; plan §2.2).

Loads ``tos/runtime/config/finality.example.yaml`` (or an operator-approved copy). The four
values here are the scope-tuple components :class:`~tos.posttrade.records.ObligationLegScope`
needs that this runtime cannot honestly derive from an ``EgressResultPayload`` alone
(``currency``/``value_date``/``source_revision``) plus the approved proof-recipe identity
(``proof_recipe_id``, ADR-002-030 §29 Q3) — every one of them is an OPERATOR-APPROVED STATIC
value, never computed here (mirrors :mod:`tos_runtime.release.config`'s own "null=named-TBD ⇒
refuse to start" discipline). What IS derived from the result at hand — the account, the
instrument, the exact filled quantity — is never duplicated into this config; see
:mod:`tos_runtime.posttrade.finality`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

__all__ = ["FinalityConfig", "FinalityConfigError", "load_finality_config"]


class FinalityConfigError(Exception):
    """Raised when the finality config is missing, malformed, or carries an unfilled
    (missing/null) required key — fail-closed at load."""


@dataclass(frozen=True)
class FinalityConfig:
    """Fully-valued SYNTHETIC post-trade finality runtime configuration.

    Attributes:
        currency: The exact settlement currency this SYNTHETIC transport's obligations are
            denominated in (``ObligationLegScope.currency``, ADR §11 line 328).
        value_date: The exact value-date token this transport's obligations bind
            (``ObligationLegScope.value_date`` — an opaque injected token; this package is
            clock-free and reads no time source).
        source_revision: The exact source revision the finality proof is taken against
            (``ObligationLegScope.source_revision`` / :attr:`~tos.posttrade.records
            .PostTradeFinalityProof.source_revision`).
        proof_recipe_id: The Phase-0-approved proof recipe identity (ADR §29 Q3) this SYNTHETIC
            producer issues every proof under.
    """

    currency: str
    value_date: str
    source_revision: str
    proof_recipe_id: str


def _require_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FinalityConfigError(f"finality config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FinalityConfigError(
            f"finality config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise FinalityConfigError(
            f"finality config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise FinalityConfigError(
            f"finality config file must be a top-level mapping: {path} (got {type(raw)!r})"
        )
    return raw


def _require_str(raw: dict[str, Any], key: str) -> str:
    if key not in raw:
        raise FinalityConfigError(f"finality config missing required key: {key!r}")
    value = raw[key]
    if value is None:
        raise FinalityConfigError(
            "finality config has an unfilled (named-TBD) key — fail-closed at startup "
            f"until an operator fills it: {key!r}"
        )
    if not isinstance(value, str) or not value.strip():
        raise FinalityConfigError(
            f"finality config key {key!r} must be a non-blank string (got {value!r})"
        )
    return value


def load_finality_config(path: Path) -> FinalityConfig:
    """Load + validate the SYNTHETIC finality config file, fail-closed.

    Args:
        path: Path to a YAML file shaped like ``tos/runtime/config/finality.example.yaml``.

    Returns:
        A fully-valued :class:`FinalityConfig`.

    Raises:
        FinalityConfigError: The file is missing/unreadable/not valid YAML/not a mapping, or a
            required key is missing or still ``null`` (named-TBD).
    """
    raw = _require_mapping(path)
    return FinalityConfig(
        currency=_require_str(raw, "currency"),
        value_date=_require_str(raw, "value_date"),
        source_revision=_require_str(raw, "source_revision"),
        proof_recipe_id=_require_str(raw, "proof_recipe_id"),
    )
