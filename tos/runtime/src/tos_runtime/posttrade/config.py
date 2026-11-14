"""SYNTHETIC post-trade finality runtime config loader (TOS Phase 3 Wave 2 Lane C-R; plan §2.2)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from tos_runtime._named_tbd import reject_named_tbd

__all__ = [
    "FinalityConfig",
    "FinalityConfigError",
    "PostTradeWitnessKind",
    "WITNESS_CONFIG_KEY",
    "load_finality_config",
]

WITNESS_CONFIG_KEY = "witness"


class PostTradeWitnessKind(StrEnum):
    """The closed vocabulary ``finality.yaml::witness`` accepts (module docstring)."""

    SYNTHETIC_VENUE_LEDGER = "synthetic_venue_ledger"


class FinalityConfigError(Exception):
    """Raised when the finality config is missing, malformed, or carries an unfilled"""


@dataclass(frozen=True)
class FinalityConfig:
    """Fully-valued SYNTHETIC post-trade finality runtime configuration."""

    currency: str
    value_date: str
    source_revision: str
    proof_recipe_id: str
    release_proof_wait_ms: int
    witness: PostTradeWitnessKind | None = None


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
    reject_named_tbd(
        value, field=key, context="finality config", error_cls=FinalityConfigError
    )
    return value


def _require_positive_int(raw: dict[str, Any], key: str) -> int:
    if key not in raw:
        raise FinalityConfigError(f"finality config missing required key: {key!r}")
    value = raw[key]
    if value is None:
        raise FinalityConfigError(
            "finality config has an unfilled (named-TBD) key — fail-closed at startup "
            f"until an operator fills it: {key!r}"
        )
    if isinstance(value, bool) or not isinstance(value, int):
        raise FinalityConfigError(
            f"finality config key {key!r} must be an int (got {value!r})"
        )
    if value <= 0:
        raise FinalityConfigError(
            f"finality config key {key!r} must be a positive int (got {value!r}) — a "
            "zero/negative wait bound is not a smaller bound, it is a silently-disabled one"
        )
    return value


def _optional_witness(raw: dict[str, Any]) -> PostTradeWitnessKind | None:
    """``witness``, or ``None`` when the key is absent (module docstring's "witness" section)."""
    if WITNESS_CONFIG_KEY not in raw:
        return None
    value = raw[WITNESS_CONFIG_KEY]
    try:
        return PostTradeWitnessKind(value)
    except ValueError as exc:
        known = ", ".join(repr(kind.value) for kind in PostTradeWitnessKind)
        raise FinalityConfigError(
            f"finality config key {WITNESS_CONFIG_KEY!r} is {value!r}, which names no known "
            f"witness (known: {known}) — remove the key to keep the default store-derived "
            "witness, never leave it misspelled"
        ) from exc


def load_finality_config(path: Path) -> FinalityConfig:
    """Load + validate the SYNTHETIC finality config file, fail-closed."""
    raw = _require_mapping(path)
    return FinalityConfig(
        currency=_require_str(raw, "currency"),
        value_date=_require_str(raw, "value_date"),
        source_revision=_require_str(raw, "source_revision"),
        proof_recipe_id=_require_str(raw, "proof_recipe_id"),
        release_proof_wait_ms=_require_positive_int(raw, "release_proof_wait_ms"),
        witness=_optional_witness(raw),
    )
