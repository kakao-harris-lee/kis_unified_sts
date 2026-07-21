"""Proposal — the only authored output + effect-free builder (design §2.2; RFC-008 §8).

A :class:`Proposal` is content-addressed (``proposal_id = f(digest)``,
:class:`~tos.canonical.IdDerivedArtifact`): complete and immutable at emission, and
binding the exact Decision Context Capsule identity+digest it consumed (RFC-008 §8
L259-261). Its covered fields are aligned to the downstream Approval consumer's
vocabulary (``PROPOSAL-APPROVAL-REQUEST-template.yaml``) — an anchor, not a
redefinition of ADR-002-020 (design §2.2; ADR-002-020 field set remains
provisional/downstream, design §6.3/§8).

**Explicit Flat is a Proposal, not a No-Action** (ADR-DEV-007 §7): a flat is a
zero-position *action* (``target_kind = FLAT``, quantity basis
:data:`FLAT_QUANTITY_BASIS`), whereas No-Action leaves exposure and is a distinct
type (:class:`~tos.dsl.outcome.NoActionOutcome`). The two produce opposite exposure
effects (SOS-INV-001).

The **effect-free Proposal Builder** (:func:`build_proposal` / :func:`build_flat`)
is a pure function: it reserves no capacity, notifies no approver, reaches no owner
(RFC-008 §8 L256-258). It rejects a wildcard / "latest" account or instrument
(SOS-INV-004; ADR-002-020 §8) — such a construction is unconstructable.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design §firewall).
"""

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
_PROPOSAL_ID_PREFIX = "prop"  # design/config prefix, not a safety token (design §2.1)

#: The quantity basis that denotes a zero-position (flat) target. A FLAT proposal
#: SHALL use it; an ACTION proposal SHALL NOT — so the flat/action distinction is
#: structural, not a producer-asserted label (★ producer-optimism prohibition).
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
    """A single per-instrument authored Proposal (RFC-008 §8; ADR-DEV-007 §8).

    Content-addressed and immutable; binds the exact consumed Capsule. Carries only
    proposing-role vocabulary (RFC-008 §7): the quantity basis and edge/confidence
    are **evidence, never capacity** (RFC-008 §7 L215, §10 L341-342, §12 L435), and
    timing/execution are *requests* (RFC-005). Its authority block is all-false
    (SOS-INV-005). It is a candidate: well-formedness is necessary, never sufficient
    for authorization (RFC-008 §8 L272-274).
    """

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

    # ---- Layer-0 identity (derived) ----
    proposal_id: str | None = None

    # ---- Layer-1 covered content ----
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
        # SOS-INV-004: no wildcard / "latest" scope in any construction.
        for name in ("account", "instrument"):
            if _is_wildcard(getattr(self, name)):
                raise ArtifactIntegrityError(
                    f"Proposal.{name} must not be a wildcard/'latest' scope "
                    "(SOS-INV-004; ADR-002-020 §8)"
                )
        # A set rationale must be a real one: ``rationale`` is required-covered, but
        # the completeness guard treats "" as concrete, so an empty string would
        # satisfy the "record why" obligation vacuously (RFC-008 §7; ADR-DEV-007).
        # Only the string field is checked — bool/int fields are unaffected.
        if self.rationale is not None and not self.rationale.strip():
            raise ArtifactIntegrityError(
                "Proposal.rationale must be non-empty — a proposal records why the "
                "outcome followed from the context, not a vacuous '' (RFC-008 §7; "
                "ADR-DEV-007)"
            )
        # ★ producer-optimism: flat vs action is structural, not a claimed label.
        # Only enforced once the quantity basis is concrete (issuance requires it).
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
    """Effect-free Proposal Builder (RFC-008 §8 L256-258) — a pure constructor.

    Assembles and issues a :class:`Proposal`. It has **no side effect**: it reserves
    no capacity, notifies no approver, and reaches no owner. A wildcard / "latest"
    account or instrument is rejected (SOS-INV-004). Emission is the end — the
    returned candidate confers no authority and observes no downstream stage
    (RFC-008 §8 L268-270).

    Args:
        scheme: The canonicalization scheme to bind.
        proposer: The authoring strategy identity.
        account: The single account scope (wildcard-free).
        instrument: The single instrument scope (wildcard-free).
        direction: The intended trading direction.
        position_effect: The intended position effect.
        quantity_basis: The desired quantity basis (evidence, never capacity).
        rationale: Why the outcome followed from the context (RFC-008 §7).
        decision_context_capsule: The exact consumed Capsule bind.
        dsl_version: The DSL version.
        config_version: The configuration version.
        edge_or_confidence: An expected edge / confidence (evidence).
        timing_and_execution_constraints: Timing/execution *requests* (RFC-005).
        target_kind: ``ACTION`` (default) or ``FLAT``.
        status: The issued lifecycle status (default ``ISSUED``).

    Returns:
        The issued, digest-verified :class:`Proposal` candidate.
    """
    return Proposal.issue(  # type: ignore[return-value]
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
    """Effect-free builder for an Explicit Flat (ADR-DEV-007 §7) — a zero-position action.

    A thin specialization of :func:`build_proposal` that fixes ``target_kind=FLAT``
    and the zero-position quantity basis, so a flat is unambiguously a distinct,
    opposite-exposure action from a No-Action Outcome (SOS-INV-001).

    Args:
        scheme: The canonicalization scheme to bind.
        proposer: The authoring strategy identity.
        account: The single account scope (wildcard-free).
        instrument: The single instrument scope (wildcard-free).
        direction: The direction of the closing action.
        position_effect: The closing position effect.
        rationale: Why flat followed from the context.
        decision_context_capsule: The exact consumed Capsule bind.
        dsl_version: The DSL version.
        config_version: The configuration version.
        edge_or_confidence: An expected edge / confidence (evidence).
        timing_and_execution_constraints: Timing/execution *requests* (RFC-005).
        status: The issued lifecycle status (default ``ISSUED``).

    Returns:
        The issued Explicit-Flat :class:`Proposal`.
    """
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
