"""Safety Profile Governance pure data models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-014 (Hard Safety Envelope and Runtime Safety Profile Governance) part
of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design contract
``docs/plans/2026-07-25-tos-safety-profile-governance-design.md`` (v1.1). It models Safety
Configuration as a **권위 boundary** (ADR line 63) through an immutable, authenticated,
content-addressed **dual artifact** — a maximum-authority ``HardSafetyEnvelope`` and one
exact live-scope ``RuntimeSafetyProfile`` operating at or below it — and authors the
envelope-dominance / semantic-validation / atomic-activation / stale-base / restrictive-
precedence / expiry-non-revival / decision-replay predicates on top.

This package is **pure, non-transmitting, non-enforcing, and clock-free** (design #12
§0.2/§4.5): frozen pydantic models over injected state + conservative fail-closed
predicates. It **cannot** transmit / activate / mutate capacity / issue authorization / re-arm
— it produces decision **bools** / scalars; the owning runtime (a future Safety Profile
Validator / Configuration Distribution / Live-Authorization service, ADR §1/§13/§16) enforces
them. There is no "assume-within" / "assume-committable" path anywhere: ``valid`` /
``COMMITTABLE`` / ``True`` comes only from positive proof, everything else is restrictive
(design #12 §4.1 — the structural seal against the #6 fail-open REJECT lesson).

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``classify_record_pair`` + the already-core ``CanonicalDecimal``,
design #12 §0.4c) + ``tos.ordering`` (append-only generation / activation order) — no
``numpy`` / ``pandas`` / ``yaml``, no ``shared.*``, and — as the decision-side **upstream**
of seven consumers — **none** of ``tos.liveauth`` / ``tos.authority`` / ``tos.rcl`` /
``tos.time`` / ``tos.capsule`` / ``tos.evidence`` / ``tos.protective`` / ``tos.brokercap`` /
``tos.orthostate`` / ``tos.recon`` / ``tos.dsl`` (design #12 §0.3/§3.4/§3.5 — **sibling edge
0**; the seven consumers already declared injected ``bool | None`` / ``str | None`` /
``int | None`` seams). Actively verified by the §7.1 import-closure test in
``tos/tests/spg``. **PROMOTE 0건** — ``CanonicalDecimal`` is already core (design #9 §0.4c).

Identity is **independent, not** ``f(digest)`` (design #12 §3.1): each envelope / profile /
bundle / activation / manifest generation is an immutable record; a legitimate revalidation /
supersession is a new independent id, a same-id / different-bytes re-issuance is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT``.

**Completion discipline (design #12 §1):** ``SPG-EV-001..012`` are all predicate /
coordinate substrate (8 rows carry an EV-L1 slice — the series' largest core tier — but the
other 4 are EV-L2+, and even the 8 have ``/2`` / ``/3`` / ``+Security`` residue) — Phase 1
authors the L1-decidable substrate and closes **no** SPG-EV item (authoring is not evidence,
VER-002-001 §5). Tag for any claim: "predicate / coordinate substrate only; SPG-EV-001..012
remain NOT_IMPLEMENTED pending EV-L2/L3 fault injection, adversarial, and +Security evidence;
EV-L1-complete claim forbidden."

Public surface groups by module:

* :mod:`tos.spg.vocabulary` — the governance-CLASS StrEnums.
* :mod:`tos.spg.records` — the dual digest-bound artifacts + value / injected-input models.
* :mod:`tos.spg.predicates` — envelope-dominance / semantic-validation / atomic-activation /
  stale-base / restrictive / expiry / rollback / break-glass / compat / bundle predicates +
  the produced seam bools / scalars.
"""

from __future__ import annotations

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.spg._base import (
    ArtifactIntegrityError,
    ArtifactStatus,
    IndependentIdArtifact,
)
from tos.spg.predicates import (
    activation_atomic,
    activation_digest,
    activation_serializable,
    active_envelope_generation,
    active_envelope_version,
    active_profile_generation,
    active_profile_version,
    break_glass_confined,
    bundle_complete,
    change_direction,
    compatibility_manifest_matches,
    envelope_bounded,
    envelope_expansion_enlarges_nothing,
    envelope_incompatible,
    envelope_limit_operand,
    envelope_not_expanded,
    envelope_profile_covers_enlarged,
    envelope_transition_allowed,
    expiry_revives_nothing,
    expiry_suspends_new_risk,
    hard_and_runtime_versions_match,
    missing_config_denies,
    profile_limit_operand,
    profile_transition_allowed,
    profile_within_envelope,
    restrictive_override_admissible,
    rollback_requires_new_generation,
    rollback_revives_nothing,
    semantic_validation,
    units_compatible,
)
from tos.spg.records import (
    ActivationInputs,
    ActivationRecord,
    BundleMemberRef,
    ChangeDirectionInputs,
    CompatibilityQuery,
    ConsumerCompatibilityManifest,
    EnvelopeVersion,
    GovernedDimensionLimit,
    HardSafetyEnvelope,
    ProfileVersion,
    RestrictiveOverrideInputs,
    RollbackInputs,
    RuntimeSafetyProfile,
    SafetyConfigurationBundle,
    SemanticValidationInputs,
    SemanticValidationResult,
)
from tos.spg.vocabulary import (
    BREAK_GLASS_ALLOWED_ACTIONS,
    MODELED_BUNDLE_MEMBERS,
    ActivationVerdict,
    BreakGlassAction,
    BundleMemberKind,
    ChangeDirection,
    EnvelopeState,
    ProfileState,
    ValidationReason,
)

__all__ = [
    # base (reused core)
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "IndependentIdArtifact",
    # ordering (reused core — append-only generation / activation order)
    "Ordering",
    "OrderingEvent",
    "compare_order",
    # vocabulary
    "BREAK_GLASS_ALLOWED_ACTIONS",
    "MODELED_BUNDLE_MEMBERS",
    "ActivationVerdict",
    "BreakGlassAction",
    "BundleMemberKind",
    "ChangeDirection",
    "EnvelopeState",
    "ProfileState",
    "ValidationReason",
    # records
    "ActivationInputs",
    "ActivationRecord",
    "BundleMemberRef",
    "ChangeDirectionInputs",
    "CompatibilityQuery",
    "ConsumerCompatibilityManifest",
    "EnvelopeVersion",
    "GovernedDimensionLimit",
    "HardSafetyEnvelope",
    "ProfileVersion",
    "RestrictiveOverrideInputs",
    "RollbackInputs",
    "RuntimeSafetyProfile",
    "SafetyConfigurationBundle",
    "SemanticValidationInputs",
    "SemanticValidationResult",
    # predicates
    "activation_atomic",
    "activation_digest",
    "activation_serializable",
    "active_envelope_generation",
    "active_envelope_version",
    "active_profile_generation",
    "active_profile_version",
    "break_glass_confined",
    "bundle_complete",
    "change_direction",
    "compatibility_manifest_matches",
    "envelope_bounded",
    "envelope_expansion_enlarges_nothing",
    "envelope_incompatible",
    "envelope_limit_operand",
    "envelope_not_expanded",
    "envelope_profile_covers_enlarged",
    "envelope_transition_allowed",
    "expiry_revives_nothing",
    "expiry_suspends_new_risk",
    "hard_and_runtime_versions_match",
    "missing_config_denies",
    "profile_limit_operand",
    "profile_transition_allowed",
    "profile_within_envelope",
    "restrictive_override_admissible",
    "rollback_requires_new_generation",
    "rollback_revives_nothing",
    "semantic_validation",
    "units_compatible",
]
