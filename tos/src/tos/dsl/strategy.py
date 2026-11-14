"""Authored Strategy — a versioned Decision Policy (design §2.1; RFC-008 §5/§9)."""

from __future__ import annotations

from typing import ClassVar

from tos.dsl._base import AllFalseAuthority, IdDerivedArtifact
from tos.dsl.vocabulary import DecisionPolicy

_STRATEGY_ARTIFACT_TYPE = "AUTHORED_STRATEGY"
_STRATEGY_SCHEMA_VERSION = "1.0-DRAFT"
_STRATEGY_ID_PREFIX = "astrat"


class AuthoredStrategy(IdDerivedArtifact):
    """A versioned Decision Policy plus its configuration bindings (RFC-008 §5 L154-156)."""

    _ID_FIELD: ClassVar[str] = "strategy_id"
    _ID_PREFIX: ClassVar[str] = _STRATEGY_ID_PREFIX
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "dsl_version",
        "config_binding_version",
        "policy",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "artifact_type",
            "schema_version",
            "dsl_version",
            "config_binding_version",
            "policy",
            "authority",
        }
    )

    strategy_id: str | None = None

    artifact_type: str = _STRATEGY_ARTIFACT_TYPE
    schema_version: str = _STRATEGY_SCHEMA_VERSION
    dsl_version: str | None = None
    config_binding_version: str | None = None
    policy: DecisionPolicy | None = None
    authority: AllFalseAuthority = AllFalseAuthority()
