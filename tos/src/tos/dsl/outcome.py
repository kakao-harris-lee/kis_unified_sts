"""Strategy output semantics — No-Action / Explicit Flat / Portfolio Vector (ADR-DEV-007)."""

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
    """A first-class No-Action Outcome (ADR-DEV-007 §5/§7; SOS-INV-001)."""

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

    outcome_id: str | None = None

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
        """A recorded No-Action must carry a real rationale, never a vacuous ""."""
        if self.rationale is not None and not self.rationale.strip():
            raise ArtifactIntegrityError(
                "NoActionOutcome.rationale must be non-empty — a recorded decision "
                "states why it followed from the context, not a vacuous '' "
                "(RFC-008 §7; ADR-DEV-007)"
            )
        return self


class PortfolioVector(IndependentIdArtifact):
    """A portfolio-wide target vector as a set of per-instrument Proposals (SOS-INV-002/003)."""

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

    vector_id: str | None = None

    artifact_type: str = _VECTOR_ARTIFACT_TYPE
    schema_version: str = _SCHEMA_VERSION
    components: tuple[Proposal, ...] = ()
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


Outcome = NoActionOutcome | Proposal | PortfolioVector


class VectorRealization(StrEnum):
    """The realization state of a vector after per-target rejections (SOS-INV-006)."""

    ALL_COMPONENTS_PROCEED = "ALL_COMPONENTS_PROCEED"
    WHOLE_VECTOR_NON_REALIZATION = "WHOLE_VECTOR_NON_REALIZATION"
    NON_REJECTED_COMPONENTS_PROCEED = "NON_REJECTED_COMPONENTS_PROCEED"


class VectorResolution(FrozenModel):
    """The recorded, first-class outcome of resolving a partial approval (SOS-INV-006)."""

    realization: VectorRealization
    reevaluation_required: bool
    proceeding_targets: tuple[tuple[str | None, str | None], ...]
    rejected_targets: tuple[tuple[str | None, str | None], ...]


def resolve_vector_realization(
    vector: PortfolioVector,
    rejected_targets: frozenset[tuple[str | None, str | None]],
) -> VectorResolution:
    """Resolve a portfolio vector under a set of per-target rejections (SOS-INV-006)."""
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
