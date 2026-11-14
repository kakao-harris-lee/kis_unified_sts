"""Proposal — the only authored output + effect-free builder (design §2.2; RFC-008 §8)."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import model_validator

from tos.dsl._base import (
    AllFalseAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    DecisionContextCapsuleRef,
    FrozenModel,
    IdDerivedArtifact,
)
from tos.dsl.candidate import WILDCARD_TOKENS
from tos.dsl.vocabulary import TargetKind

_PROPOSAL_ARTIFACT_TYPE = "STRATEGY_PROPOSAL"
_PROPOSAL_SCHEMA_VERSION = "1.0-DRAFT"
_PROPOSAL_ID_PREFIX = "prop"

FLAT_QUANTITY_BASIS = "ZERO_POSITION"


class Proposer(FrozenModel):
    """The authoring strategy identity (PROPOSAL-APPROVAL-REQUEST L8-12 anchor)."""

    strategy_id: str | None = None
    strategy_version: str | None = None


def _is_wildcard(value: str | None) -> bool:
    """Whether a scope token is a wildcard / "latest" (SOS-INV-004; ADR-002-020 §8)."""
    if value is None:
        return False
    if value in WILDCARD_TOKENS:
        return True
    return "*" in value or value.lower() == "latest"


class Proposal(IdDerivedArtifact):
    """A single per-instrument authored Proposal (RFC-008 §8; ADR-DEV-007 §8)."""

    _ID_FIELD: ClassVar[str] = "proposal_id"
    _ID_PREFIX: ClassVar[str] = _PROPOSAL_ID_PREFIX
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "proposer.strategy_id",
        "proposer.strategy_version",
        "account",
        "instrument",
        "direction",
        "position_effect",
        "quantity_basis",
        "rationale",
        "decision_context_capsule.capsule_id",
        "decision_context_capsule.canonical_digest",
        "dsl_version",
        "config_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "artifact_type",
            "schema_version",
            "proposer",
            "target_kind",
            "account",
            "instrument",
            "direction",
            "position_effect",
            "quantity_basis",
            "edge_or_confidence",
            "timing_and_execution_constraints",
            "rationale",
            "decision_context_capsule",
            "dsl_version",
            "config_version",
            "authority",
        }
    )

    proposal_id: str | None = None

    artifact_type: str = _PROPOSAL_ARTIFACT_TYPE
    schema_version: str = _PROPOSAL_SCHEMA_VERSION
    proposer: Proposer = Proposer()
    target_kind: TargetKind = TargetKind.ACTION
    account: str | None = None
    instrument: str | None = None
    direction: str | None = None
    position_effect: str | None = None
    quantity_basis: str | None = None
    edge_or_confidence: str | None = None
    timing_and_execution_constraints: tuple[str, ...] = ()
    rationale: str | None = None
    decision_context_capsule: DecisionContextCapsuleRef = DecisionContextCapsuleRef()
    dsl_version: str | None = None
    config_version: str | None = None
    authority: AllFalseAuthority = AllFalseAuthority()

    @model_validator(mode="after")
    def _proposal_invariants(self) -> Proposal:
        """Enforce wildcard-free scope + flat/action↔quantity consistency (SOS-INV-004)."""
        for name in ("account", "instrument"):
            if _is_wildcard(getattr(self, name)):
                raise ArtifactIntegrityError(
                    f"Proposal.{name} must not be a wildcard/'latest' scope "
                    "(SOS-INV-004; ADR-002-020 §8)"
                )
        if self.rationale is not None and not self.rationale.strip():
            raise ArtifactIntegrityError(
                "Proposal.rationale must be non-empty — a proposal records why the "
                "outcome followed from the context, not a vacuous '' (RFC-008 §7; "
                "ADR-DEV-007)"
            )
        if self.quantity_basis is not None:
            if self.target_kind is TargetKind.FLAT and (
                self.quantity_basis != FLAT_QUANTITY_BASIS
            ):
                raise ArtifactIntegrityError(
                    "a FLAT Proposal must use the zero-position quantity basis "
                    f"({FLAT_QUANTITY_BASIS!r}) — flat is a zero-position action "
                    "(ADR-DEV-007 §7)"
                )
            if self.target_kind is TargetKind.ACTION and (
                self.quantity_basis == FLAT_QUANTITY_BASIS
            ):
                raise ArtifactIntegrityError(
                    "an ACTION Proposal must not use the zero-position quantity "
                    "basis — that is an Explicit Flat, a distinct outcome "
                    "(ADR-DEV-007 §7; SOS-INV-001)"
                )
        return self


def build_proposal(
    *,
    scheme: Any,
    proposer: Proposer,
    account: str,
    instrument: str,
    direction: str,
    position_effect: str,
    quantity_basis: str,
    rationale: str,
    decision_context_capsule: DecisionContextCapsuleRef,
    dsl_version: str,
    config_version: str,
    edge_or_confidence: str | None = None,
    timing_and_execution_constraints: tuple[str, ...] = (),
    target_kind: TargetKind = TargetKind.ACTION,
    status: ArtifactStatus = ArtifactStatus.ISSUED,
) -> Proposal:
    """Effect-free Proposal Builder (RFC-008 §8 L256-258) — a pure constructor."""
    return Proposal.issue(
        scheme=scheme,
        status=status,
        proposer=proposer,
        target_kind=target_kind,
        account=account,
        instrument=instrument,
        direction=direction,
        position_effect=position_effect,
        quantity_basis=quantity_basis,
        edge_or_confidence=edge_or_confidence,
        timing_and_execution_constraints=timing_and_execution_constraints,
        rationale=rationale,
        decision_context_capsule=decision_context_capsule,
        dsl_version=dsl_version,
        config_version=config_version,
    )


def build_flat(
    *,
    scheme: Any,
    proposer: Proposer,
    account: str,
    instrument: str,
    direction: str,
    position_effect: str,
    rationale: str,
    decision_context_capsule: DecisionContextCapsuleRef,
    dsl_version: str,
    config_version: str,
    edge_or_confidence: str | None = None,
    timing_and_execution_constraints: tuple[str, ...] = (),
    status: ArtifactStatus = ArtifactStatus.ISSUED,
) -> Proposal:
    """Effect-free builder for an Explicit Flat (ADR-DEV-007 §7) — a zero-position action."""
    return build_proposal(
        scheme=scheme,
        proposer=proposer,
        account=account,
        instrument=instrument,
        direction=direction,
        position_effect=position_effect,
        quantity_basis=FLAT_QUANTITY_BASIS,
        rationale=rationale,
        decision_context_capsule=decision_context_capsule,
        dsl_version=dsl_version,
        config_version=config_version,
        edge_or_confidence=edge_or_confidence,
        timing_and_execution_constraints=timing_and_execution_constraints,
        target_kind=TargetKind.FLAT,
        status=status,
    )
