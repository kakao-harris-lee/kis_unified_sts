"""Authored Strategy — a versioned Decision Policy (design §2.1; RFC-008 §5/§9).

An :class:`AuthoredStrategy` is content-addressed
(:class:`~tos.canonical.IdDerivedArtifact`, ``strategy_id = f(digest)``): its
identity *is* its version (ADR-DEV-002 ARI-INV-001 — no mutable name/tag/"latest";
a change is a Versioned Substitution = a new Artifact Identity, ADR-DEV-004
APA-INV-005). It embeds the closed typed :class:`~tos.dsl.vocabulary.DecisionPolicy`
as covered content, so the policy's identity is folded into the strategy digest
(the design §2.1 ``policy_ref`` content-addressing is realized by embedding — the
raw-source-vs-embedded question is deferred to ADR-DEV-004, design §2.1). Its
authority block is all-false (RFC-008 §11).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design §firewall).
"""

from __future__ import annotations

from typing import ClassVar

from tos.dsl._base import AllFalseAuthority, IdDerivedArtifact
from tos.dsl.vocabulary import DecisionPolicy

_STRATEGY_ARTIFACT_TYPE = "AUTHORED_STRATEGY"
_STRATEGY_SCHEMA_VERSION = "1.0-DRAFT"
_STRATEGY_ID_PREFIX = "astrat"  # design/config prefix, not a safety token (design §2.1)


class AuthoredStrategy(IdDerivedArtifact):
    """A versioned Decision Policy plus its configuration bindings (RFC-008 §5 L154-156).

    Content-addressed and immutable; embeds the admissible-by-type
    :class:`DecisionPolicy` and records the ``dsl_version`` and
    ``config_binding_version`` that evaluation stamps into decision evidence
    (RFC-008 §9 L302-306). A candidate proposer, never an authorization (RFC-008 §5).
    """

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

    # ---- Layer-0 identity (derived) ----
    strategy_id: str | None = None

    # ---- Layer-1 covered content ----
    artifact_type: str = _STRATEGY_ARTIFACT_TYPE
    schema_version: str = _STRATEGY_SCHEMA_VERSION
    dsl_version: str | None = None
    config_binding_version: str | None = None
    #: The embedded closed typed policy (admissible by construction). Required for
    #: issuance — a strategy with no policy is incomplete.
    policy: DecisionPolicy | None = None
    authority: AllFalseAuthority = AllFalseAuthority()
