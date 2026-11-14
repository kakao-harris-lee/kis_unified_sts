"""Critical Input Snapshot artifact (design §2.6)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import model_validator

from tos.capsule._base import (
    ArtifactStatus,
    CapsuleIntegrityError,
    FrozenModel,
    IdDerivedArtifact,
    PolicyRef,
    SnapshotAuthority,
)
from tos.capsule.consistency_cut import ConsistencyCut
from tos.capsule.field_evaluation import FieldEvaluation
from tos.capsule.field_state import FieldState
from tos.capsule.lineage import TransformationLineage
from tos.capsule.observation import Observation

_SNAPSHOT_ARTIFACT_TYPE = "CRITICAL_INPUT_SNAPSHOT"
_SNAPSHOT_SCHEMA_VERSION = "1.0-DRAFT"
_SNAPSHOT_ID_PREFIX = "cis"


class SnapshotScope(FrozenModel):
    """Snapshot scope (template lines 12-18) — plural account/venue/instrument."""

    environment: str | None = None
    safety_cell: str | None = None
    accounts: tuple[str, ...] = ()
    venues: tuple[str, ...] = ()
    instruments: tuple[str, ...] = ()
    decision_class: str | None = None


class TrustworthyTime(FrozenModel):
    """Trustworthy-time anchor block (template lines 33-37)."""

    snapshot_id: str | None = None
    generation: int | None = None
    consumer_receipt_anchor: str | None = None
    maximum_age_ms: int | None = None


class SnapshotValidity(FrozenModel):
    """Snapshot validity block (template lines 38-43)."""

    result: FieldState = FieldState.INVALID
    issued_at: int | None = None
    expires_at: int | None = None
    invalidation_generation: int | None = None
    invalidation_conditions: tuple[str, ...] = ()


class CorroborationPath(FrozenModel):
    """An independence-corroboration path (design §5.2 — authored element)."""

    path_id: str | None = None
    tags: tuple[str, ...] = ()


class CriticalInputSnapshot(IdDerivedArtifact):
    """Immutable Critical Input Snapshot (design §2.6)."""

    _ID_FIELD: ClassVar[str] = "snapshot_id"
    _ID_PREFIX: ClassVar[str] = _SNAPSHOT_ID_PREFIX
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "issuer_principal_id",
        "critical_input_policy.policy_id",
        "critical_input_policy.canonical_digest",
        "scope.environment",
        "scope.decision_class",
        "intended_use",
        "consistency_cut.cut_id",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "artifact_type",
            "schema_version",
            "issuer_principal_id",
            "critical_input_policy",
            "context_generation",
            "scope",
            "intended_use",
            "consistency_cut",
            "observations",
            "transformation_lineage",
            "field_evaluations",
            "corroboration_paths",
            "common_mode_dependencies",
            "residual_risks",
            "trustworthy_time",
            "validity",
            "authority",
        }
    )

    snapshot_id: str | None = None

    artifact_type: str = _SNAPSHOT_ARTIFACT_TYPE
    schema_version: str = _SNAPSHOT_SCHEMA_VERSION
    issuer_principal_id: str | None = None
    critical_input_policy: PolicyRef = PolicyRef()
    context_generation: int | None = None
    scope: SnapshotScope = SnapshotScope()
    intended_use: str | None = None
    consistency_cut: ConsistencyCut = ConsistencyCut()
    observations: tuple[Observation, ...] = ()
    transformation_lineage: tuple[TransformationLineage, ...] = ()
    field_evaluations: tuple[FieldEvaluation, ...] = ()
    corroboration_paths: tuple[CorroborationPath, ...] = ()
    common_mode_dependencies: tuple[str, ...] = ()
    residual_risks: tuple[str, ...] = ()
    trustworthy_time: TrustworthyTime = TrustworthyTime()
    validity: SnapshotValidity = SnapshotValidity()
    authority: SnapshotAuthority = SnapshotAuthority()

    @model_validator(mode="after")
    def _verify_result_conservative(self) -> CriticalInputSnapshot:
        """Reject a stored ``validity.result`` more permissive than intrinsic (§5.1)."""
        if self.status == ArtifactStatus.DRAFT:
            return self
        from tos.capsule.predicates import verify_validity_result_conservative

        if not verify_validity_result_conservative(self):
            from tos.capsule.predicates import aggregate_snapshot_validity

            intrinsic = aggregate_snapshot_validity(self, required_independent_paths=0)
            raise CapsuleIntegrityError(
                f"stored validity.result={self.validity.result} is less restrictive "
                f"than the intrinsic conservative aggregate {intrinsic} — §5.1"
            )
        return self
