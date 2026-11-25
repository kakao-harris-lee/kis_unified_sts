"""Serialized strategy admission — pydantic validation only (design #31 §3.5/§9-4)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl._base import ArtifactIntegrityError, FrozenModel
from tos.dsl.strategy import AuthoredStrategy
from tos.dsl.vocabulary import DecisionPolicy

__all__ = ["StrategyParseError", "parse_strategy"]


class StrategyParseError(ArtifactIntegrityError):
    """A serialized strategy mapping failed pydantic validation (design #31 §9-4)."""


class _StrategyAuthoringContent(FrozenModel):
    """The pydantic validation shape for a serialized strategy mapping (design #31 §9-4)."""

    dsl_version: str
    config_binding_version: str
    policy: DecisionPolicy
    canonicalization_version: str | None = None


def _format_validation_error(exc: ValidationError) -> str:
    """Render a pydantic :class:`ValidationError` as ``"path: message; path: message"``."""
    parts: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error["loc"]) or "<root>"
        parts.append(f"{loc}: {error['msg']}")
    return "; ".join(parts)


def parse_strategy(mapping: Mapping[str, Any]) -> AuthoredStrategy:
    """Parse + issue an Authored Strategy from a plain mapping (design #31 §9-4)."""
    try:
        content = _StrategyAuthoringContent.model_validate(dict(mapping))
    except ValidationError as exc:
        raise StrategyParseError(_format_validation_error(exc)) from exc

    scheme = get_scheme(content.canonicalization_version or EV_L1_PROVISIONAL_VERSION)
    return AuthoredStrategy.issue(
        scheme=scheme,
        dsl_version=content.dsl_version,
        config_binding_version=content.config_binding_version,
        policy=content.policy,
    )
