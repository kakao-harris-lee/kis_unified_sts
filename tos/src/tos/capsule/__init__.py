"""Decision Context Capsule + Critical Input Snapshot pure data models (Phase 1).

Realizes IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1) of ADR-002-018, per the
ratified design contract
``docs/plans/2026-07-20-tos-decision-context-capsule-snapshot-design.md`` (v2).

This package is **pure, non-transmitting, and authority-free** (design §0.2,
§4.4): frozen pydantic models, injectable canonicalization, and conservative
derived predicates. It imports only ``pydantic`` + stdlib — no ``numpy``/
``pandas``, no ``shared.*`` operational packages, no network / process / env
access (design §0.3 firewall closure, actively verified by the import-closure
test in ``tos/tests``).

Public surface groups by module:

* :mod:`tos.capsule.field_state` — five-valued lattice + aggregation.
* :mod:`tos.capsule.canonicalization` — injectable scheme + provisional EV-L1
  canonicalizer + registry.
* :mod:`tos.capsule.observation`, ``lineage``, ``field_evaluation``,
  ``consistency_cut`` — element schemas.
* :mod:`tos.capsule.snapshot`, ``capsule`` — the two digest-bound artifacts.
* :mod:`tos.capsule.context_generation` — generation ordering predicate.
* :mod:`tos.capsule.predicates` — derived predicates and conservative
  aggregations.
"""

from __future__ import annotations

from tos.capsule._base import (
    ArtifactStatus,
    CapsuleAuthority,
    CapsuleIntegrityError,
    DigestBoundArtifact,
    FrozenModel,
    PolicyRef,
    SnapshotAuthority,
    derive_id,
)
from tos.capsule.canonicalization import (
    EV_L1_PROVISIONAL_VERSION,
    CanonicalizationScheme,
    EVL1ProvisionalCanonicalizer,
    get_scheme,
    register_scheme,
)
from tos.capsule.capsule import DecisionContextCapsule
from tos.capsule.consistency_cut import ConsistencyCut
from tos.capsule.context_generation import generation_can_authorize
from tos.capsule.field_evaluation import FieldEvaluation
from tos.capsule.field_state import FieldState, more_restrictive, restrictiveness, worst
from tos.capsule.lineage import TransformationLineage
from tos.capsule.observation import AdmissionResult, Observation
from tos.capsule.snapshot import CriticalInputSnapshot

__all__ = [
    # base
    "ArtifactStatus",
    "CapsuleAuthority",
    "CapsuleIntegrityError",
    "DigestBoundArtifact",
    "FrozenModel",
    "PolicyRef",
    "SnapshotAuthority",
    "derive_id",
    # canonicalization
    "EV_L1_PROVISIONAL_VERSION",
    "CanonicalizationScheme",
    "EVL1ProvisionalCanonicalizer",
    "get_scheme",
    "register_scheme",
    # artifacts + elements
    "DecisionContextCapsule",
    "CriticalInputSnapshot",
    "ConsistencyCut",
    "FieldEvaluation",
    "TransformationLineage",
    "Observation",
    "AdmissionResult",
    # field state + predicates
    "FieldState",
    "more_restrictive",
    "restrictiveness",
    "worst",
    "generation_can_authorize",
]
