"""Critical Input Snapshot artifact (design §2.6).

Models ``CRITICAL-INPUT-SNAPSHOT-template.yaml`` (51 lines) 1:1 — no new *stored*
top-level field beyond the template (design §2.6). The empty template arrays
(``observations``/``transformation_lineage``/``field_evaluations``) take the
element schemas authored in §2.2-§2.4; ``consistency_cut`` takes §2.5; the
``cut_compatible`` gate is a derived predicate, not a stored field (design §2.5),
so the snapshot canonical bytes stay aligned with the template SoT.

Digest coverage (design §3.3): covered = the whole Layer-1 top-level set (every
field except the self-excluded ``snapshot_id`` / ``canonical_digest`` / ``status``
and the ``canonicalization_version`` meta field, design §3.2). Validity
aggregation (``validity.result``) is defined in :mod:`tos.capsule.predicates`
(design §5.1). The stored ``result`` is producer-supplied, but issuance enforces
that it is **never less restrictive** than the intrinsic conservative aggregate
(``verify_validity_result_conservative``): a snapshot cannot claim more validity
than its own field evaluations, cut, and common-mode analysis justify (§5.1 —
result is not an average/majority/field-ignoring vote).

``authority.*`` is forced ``false`` (design §4.4). Pure module.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import model_validator

from tos.capsule._base import (
    ArtifactStatus,
    CapsuleIntegrityError,
    DigestBoundArtifact,
    FrozenModel,
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
    """Snapshot validity block (template lines 38-43).

    ``result`` is producer-supplied; its normative conservative aggregation is
    :func:`tos.capsule.predicates.aggregate_snapshot_validity` (design §5.1).
    """

    result: FieldState = FieldState.INVALID
    issued_at: int | None = None
    expires_at: int | None = None
    invalidation_generation: int | None = None
    invalidation_conditions: tuple[str, ...] = ()


class CorroborationPath(FrozenModel):
    """An independence-corroboration path (design §5.2 — authored element).

    The template leaves ``corroboration_paths: []`` element-less; this schema is
    authored to carry the shared-resource ``tags`` (effective control / origin /
    parser / mapping / library / cache / administrator / failure-domain) that the
    common-mode collapse predicate cross-analyses (§5.2). An empty ``tags`` set
    means undetermined scope, treated as shared (conservative, ADR §22 line 522).
    """

    path_id: str | None = None
    tags: tuple[str, ...] = ()


class CriticalInputSnapshot(DigestBoundArtifact):
    """Immutable Critical Input Snapshot (design §2.6).

    A content-addressed artifact: ``snapshot_id = f(canonical_digest)`` and
    ``canonical_digest == H_ver(canonicalize(covered))`` are enforced on
    construction (design §4.1). Use :meth:`issue` to construct an issued
    snapshot; direct construction with a mismatched digest/id is rejected.
    """

    _ID_FIELD: ClassVar[str] = "snapshot_id"
    _ID_PREFIX: ClassVar[str] = _SNAPSHOT_ID_PREFIX
    # Safety-load-bearing covered fields that MUST be concrete to issue (design
    # §3.2). Derived from the ``CRITICAL-INPUT-SNAPSHOT-template.yaml`` ``TBD``
    # (must-fill) markers — issuer, policy reference, scope, intended use, and the
    # consistency-cut identity — whereas ``context_generation``/``trustworthy_time
    # .generation``/``validity.*`` left ``null`` there are optional.
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

    # ---- Layer-0 identity output (self-excluded from the digest, §3.2) ----
    # canonical_digest / status / canonicalization_version are inherited from
    # DigestBoundArtifact (shared Layer-0 + meta envelope, template-aligned §2.6).
    snapshot_id: str | None = None

    # ---- Layer-1 covered content ----
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
        """Reject a stored ``validity.result`` more permissive than intrinsic (§5.1).

        A snapshot may store a result equal to, or more restrictive than, the
        conservative aggregate of its own evaluations/cut/common-mode, but never
        less restrictive — closing the fail-open gap where a snapshot carrying a
        blocking INVALID field could still claim ``result=VALID`` (CII-INV-005).
        The predicate is imported at call time to avoid a module-load cycle
        (:mod:`tos.capsule.predicates` imports this module); it is a pure function,
        so this is not a runtime dependency cycle.
        """
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
