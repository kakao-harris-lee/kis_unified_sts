"""Strategy output semantics — No-Action / Explicit Flat / Portfolio Vector (ADR-DEV-007).

Realizes the six SOS invariants as pure models + a pure transition (design §2.3):

* **SOS-INV-001** — :class:`NoActionOutcome` and an Explicit-Flat
  :class:`~tos.dsl.proposal.Proposal` are **distinct types**, both non-null,
  first-class, and recorded; they produce opposite exposure effects and are never
  conflated, never an error/null/omission. No-Action leaves exposure; a flat
  proposes a zero-position action.
* **SOS-INV-002/003** — a per-instrument target is a single Proposal; a
  :class:`PortfolioVector` is a **set** of per-instrument Proposals with **no**
  union / aggregate-authority field (that field simply does not exist).
* **SOS-INV-004** — each component is a wildcard-free Proposal binding a Capsule
  (enforced in :mod:`tos.dsl.proposal`).
* **SOS-INV-005** — every Outcome carries an all-false authority block.
* **SOS-INV-006** — a vector declares its component interdependence; absent a
  declaration it is **atomic (fail-closed)**. :func:`resolve_vector_realization`
  models the partial-approval transition: an atomic vector with any rejected
  component yields whole-vector non-realization + a recorded re-evaluation, never a
  silent naked partial. (Real approval/re-evaluation is downstream/runtime; Phase 1
  models only the transition's expressibility and the fail-closed default.)

:class:`NoActionOutcome` and :class:`PortfolioVector` are digest-bound records with
an **independent** id (design §2.3), matching the ``tos.evidence`` ledger pattern;
the component Proposals keep their own content-addressed ``IdDerivedArtifact``
identity.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design §firewall).
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import model_validator

from tos.dsl._base import (
    AllFalseAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    DecisionContextCapsuleRef,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.dsl.proposal import Proposal
from tos.dsl.vocabulary import VectorInterdependence

_NO_ACTION_ARTIFACT_TYPE = "NO_ACTION_OUTCOME"
_VECTOR_ARTIFACT_TYPE = "PORTFOLIO_VECTOR"
_SCHEMA_VERSION = "1.0-DRAFT"


class NoActionOutcome(IndependentIdArtifact):
    """A first-class No-Action Outcome (ADR-DEV-007 §5/§7; SOS-INV-001).

    Proposes nothing and leaves the current position and orders untouched. It is a
    decision, recorded with its ``rationale`` and reproducible — never an error,
    null, or omission. It is structurally **not** a Proposal (a distinct type) and
    carries no target, so it can never be mistaken for an Explicit Flat. Its
    authority block is all-false (SOS-INV-005).
    """

    _ID_FIELD: ClassVar[str] = "outcome_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "rationale",
        "decision_context_capsule.capsule_id",
        "decision_context_capsule.canonical_digest",
        "strategy_version",
        "dsl_version",
        "config_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "artifact_type",
            "schema_version",
            "rationale",
            "decision_context_capsule",
            "strategy_version",
            "dsl_version",
            "config_version",
            "authority",
        }
    )

    # ---- Layer-0 identity (independent) ----
    outcome_id: str | None = None

    # ---- Layer-1 covered content ----
    artifact_type: str = _NO_ACTION_ARTIFACT_TYPE
    schema_version: str = _SCHEMA_VERSION
    rationale: str | None = None
    decision_context_capsule: DecisionContextCapsuleRef = DecisionContextCapsuleRef()
    strategy_version: str | None = None
    dsl_version: str | None = None
    config_version: str | None = None
    authority: AllFalseAuthority = AllFalseAuthority()

    @model_validator(mode="after")
    def _rationale_non_empty(self) -> NoActionOutcome:
        """A recorded No-Action must carry a real rationale, never a vacuous "".

        ``rationale`` is a required-covered field, but the completeness guard treats
        an empty string as concrete — so ``rationale=""`` would satisfy the "record
        why" obligation vacuously (RFC-008 §7; ADR-DEV-007 §5/§7). A set-but-empty
        rationale is therefore rejected (★ vacuous satisfaction prohibition; only
        the string field, so bool/int fields are unaffected).
        """
        if self.rationale is not None and not self.rationale.strip():
            raise ArtifactIntegrityError(
                "NoActionOutcome.rationale must be non-empty — a recorded decision "
                "states why it followed from the context, not a vacuous '' "
                "(RFC-008 §7; ADR-DEV-007)"
            )
        return self


class PortfolioVector(IndependentIdArtifact):
    """A portfolio-wide target vector as a set of per-instrument Proposals (SOS-INV-002/003).

    Emitted as a **set** of single-instrument Proposals (each its own contract),
    never one multi-instrument Proposal and never an aggregated authority — there is
    no union / combined-authority field on this model (SOS-INV-003, realized by its
    absence). Components must be non-empty (★ vacuous-True prohibition), distinct
    per (account, instrument), issued, and bound to the same Capsule as the vector
    (a coherent single-evaluation unit). Component interdependence is declared;
    absent a declaration the vector is **atomic** (fail-closed, SOS-INV-006).
    """

    _ID_FIELD: ClassVar[str] = "vector_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "decision_context_capsule.capsule_id",
        "decision_context_capsule.canonical_digest",
        "dsl_version",
        "config_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "artifact_type",
            "schema_version",
            "components",
            "interdependence",
            "decision_context_capsule",
            "dsl_version",
            "config_version",
            "authority",
        }
    )

    # ---- Layer-0 identity (independent) ----
    vector_id: str | None = None

    # ---- Layer-1 covered content ----
    artifact_type: str = _VECTOR_ARTIFACT_TYPE
    schema_version: str = _SCHEMA_VERSION
    components: tuple[Proposal, ...] = ()
    #: Declared interdependence; ``None`` means undeclared → atomic (fail-closed).
    interdependence: VectorInterdependence | None = None
    decision_context_capsule: DecisionContextCapsuleRef = DecisionContextCapsuleRef()
    dsl_version: str | None = None
    config_version: str | None = None
    authority: AllFalseAuthority = AllFalseAuthority()

    @model_validator(mode="after")
    def _vector_invariants(self) -> PortfolioVector:
        """Enforce non-empty / distinct / issued / same-Capsule components (SOS-INV)."""
        if self.status == ArtifactStatus.DRAFT:
            return self
        # ★ vacuous-True prohibition: an empty vector is not a portfolio decision.
        if not self.components:
            raise ArtifactIntegrityError(
                "PortfolioVector.components must be non-empty — an empty vector is "
                "not a portfolio decision (SOS-INV fail-closed)"
            )
        seen: set[tuple[str | None, str | None]] = set()
        vector_capsule = self.decision_context_capsule.capsule_id
        for component in self.components:
            if component.status is not ArtifactStatus.ISSUED:
                raise ArtifactIntegrityError(
                    "every PortfolioVector component must be an ISSUED Proposal "
                    "(SOS-INV-004 well-formedness)"
                )
            key = (component.account, component.instrument)
            if key in seen:
                raise ArtifactIntegrityError(
                    f"duplicate per-instrument target {key} — a portfolio vector is "
                    "a set of distinct per-instrument targets (SOS-INV-002)"
                )
            seen.add(key)
            if component.decision_context_capsule.capsule_id != vector_capsule:
                raise ArtifactIntegrityError(
                    "every component must bind the same Capsule as the vector — a "
                    "vector is one coherent evaluation, not aggregated authority "
                    "(SOS-INV-003)"
                )
        return self

    def effective_interdependence(self) -> VectorInterdependence:
        """Return the interdependence, defaulting to ATOMIC when undeclared (SOS-INV-006)."""
        return self.interdependence or VectorInterdependence.ATOMIC


#: The complete set of authored outcomes (RFC-008 §6 principle 2; ADR-DEV-007).
Outcome = NoActionOutcome | Proposal | PortfolioVector


# ---------------------------------------------------------------------------
# Partial-approval transition (design §2.3; SOS-INV-006) — pure, non-authorizing.
# ---------------------------------------------------------------------------


class VectorRealization(StrEnum):
    """The realization state of a vector after per-target rejections (SOS-INV-006)."""

    #: No rejection observed — every component proceeds to its own per-target
    #: Independent Approval (approval itself is downstream/runtime; design §2.3).
    ALL_COMPONENTS_PROCEED = "ALL_COMPONENTS_PROCEED"
    #: An atomic vector with ≥1 rejection: the whole vector is not realized.
    WHOLE_VECTOR_NON_REALIZATION = "WHOLE_VECTOR_NON_REALIZATION"
    #: A declared-independent vector: non-rejected components proceed.
    NON_REJECTED_COMPONENTS_PROCEED = "NON_REJECTED_COMPONENTS_PROCEED"


class VectorResolution(FrozenModel):
    """The recorded, first-class outcome of resolving a partial approval (SOS-INV-006).

    A recorded state transition, never a silent naked partial: an atomic vector's
    partial rejection yields whole-vector non-realization plus a required strategy-
    level re-evaluation on fresh context (SOS-INV-001).
    """

    realization: VectorRealization
    reevaluation_required: bool
    proceeding_targets: tuple[tuple[str | None, str | None], ...]
    rejected_targets: tuple[tuple[str | None, str | None], ...]


def resolve_vector_realization(
    vector: PortfolioVector,
    rejected_targets: frozenset[tuple[str | None, str | None]],
) -> VectorResolution:
    """Resolve a portfolio vector under a set of per-target rejections (SOS-INV-006).

    Pure transition model (no approval, no authority): a real per-target Independent
    Approval is downstream (ADR-002-023); this models only the fail-closed authoring
    transition. Fail-closed default — an undeclared vector is atomic:

    * atomic + any rejection ⇒ ``WHOLE_VECTOR_NON_REALIZATION`` with re-evaluation
      required (never a silent naked partial);
    * independent + rejections ⇒ ``NON_REJECTED_COMPONENTS_PROCEED``;
    * no rejection ⇒ ``ALL_COMPONENTS_PROCEED``.

    Args:
        vector: The portfolio vector.
        rejected_targets: The ``(account, instrument)`` keys rejected downstream.

    Returns:
        The recorded :class:`VectorResolution`.
    """
    keys = [(c.account, c.instrument) for c in vector.components]
    rejected = tuple(k for k in keys if k in rejected_targets)
    proceeding = tuple(k for k in keys if k not in rejected_targets)

    if not rejected:
        return VectorResolution(
            realization=VectorRealization.ALL_COMPONENTS_PROCEED,
            reevaluation_required=False,
            proceeding_targets=proceeding,
            rejected_targets=(),
        )
    if vector.effective_interdependence() is VectorInterdependence.ATOMIC:
        return VectorResolution(
            realization=VectorRealization.WHOLE_VECTOR_NON_REALIZATION,
            reevaluation_required=True,
            proceeding_targets=(),
            rejected_targets=rejected,
        )
    return VectorResolution(
        realization=VectorRealization.NON_REJECTED_COMPONENTS_PROCEED,
        reevaluation_required=False,
        proceeding_targets=proceeding,
        rejected_targets=rejected,
    )
