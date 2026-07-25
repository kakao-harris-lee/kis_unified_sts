"""Shared valid-artifact builders + strategies for the spg property tests.

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #12 §0.3). The builders
enforce the §7 clean-vs-illegal fixture discipline (the #8 REJECT lesson):

* an envelope built here declares a real governed dimension with a concrete
  ``envelope_max`` + unit; a profile declares the same dimension with a concrete
  ``profile_value`` <= the envelope max + the **same** unit — so the "clean" fixtures are
  genuinely within-envelope / unit-compatible, never a permissive shortcut;
* an **over-envelope** fixture carries a real value strictly greater than the envelope max;
* a **VALID** semantic-validation input tuple has every fold step positively ``True`` +
  ``change_direction=RESTRICTIVE``; an INVALID one flips one exact step;
* a **mixed-generation** fixture carries a genuine generation mismatch.

The reserved ``"TBD"`` placeholder is excluded from required-field text.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.spg import (
    ActivationInputs,
    ActivationRecord,
    BundleMemberKind,
    BundleMemberRef,
    ChangeDirection,
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
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved ``"TBD"``).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")

#: Injected ``bool | None`` flag (fail-closed on ``None`` / ``False``).
TRIBOOL = st.sampled_from([True, False, None])
#: A non-negative generation integer (+ ``None`` for the fail-closed direction; §8).
OPT_GENERATION = st.none() | st.integers(min_value=0, max_value=1000)
#: Distinct enum strategies.
CHANGE_DIRECTIONS = st.sampled_from(list(ChangeDirection))
MEMBER_KINDS = st.sampled_from(list(BundleMemberKind))


# ---------------------------------------------------------------------------
# Value builders
# ---------------------------------------------------------------------------


def envelope_version(**overrides: Any) -> EnvelopeVersion:
    """A concrete immutable envelope version block."""
    base: dict[str, Any] = {
        "version": "e1",
        "effective_date": "2026-07-25",
        "approver_identity": "approver-1",
    }
    base.update(overrides)
    return EnvelopeVersion(**base)


def profile_version(**overrides: Any) -> ProfileVersion:
    """A concrete immutable profile version block."""
    base: dict[str, Any] = {
        "version": "p1",
        "effective_date": "2026-07-25",
        "approver_identity": "approver-1",
    }
    base.update(overrides)
    return ProfileVersion(**base)


def envelope_dimension(
    dimension: str = "qty",
    envelope_max: Decimal | None = Decimal("10"),
    unit: str = "sh",
    **overrides: Any,
) -> GovernedDimensionLimit:
    """An envelope governed dimension (carries the maximum + unit metadata)."""
    base: dict[str, Any] = {
        "dimension": dimension,
        "envelope_max": envelope_max,
        "unit": unit,
    }
    base.update(overrides)
    return GovernedDimensionLimit(**base)


def profile_dimension(
    dimension: str = "qty",
    profile_value: Decimal | None = Decimal("5"),
    unit: str = "sh",
    **overrides: Any,
) -> GovernedDimensionLimit:
    """A profile governed dimension (carries the operating value + the same unit)."""
    base: dict[str, Any] = {
        "dimension": dimension,
        "profile_value": profile_value,
        "unit": unit,
    }
    base.update(overrides)
    return GovernedDimensionLimit(**base)


# ---------------------------------------------------------------------------
# Digest-bound artifact builders
# ---------------------------------------------------------------------------


def envelope_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Envelope issuance kwargs with every required covered field concrete + one dimension."""
    base: dict[str, Any] = {
        "envelope_id": "env-1",
        "envelope_generation": 1,
        "envelope_version": envelope_version(),
        "governed_dimensions": (envelope_dimension(),),
        "permitted_scope": ("acct-1",),
    }
    base.update(overrides)
    return base


def issue_envelope(**overrides: Any) -> HardSafetyEnvelope:
    """Issue a valid :class:`HardSafetyEnvelope` (all required covered fields concrete)."""
    return HardSafetyEnvelope.issue(
        scheme=SCHEME, **envelope_required_kwargs(**overrides)
    )


def profile_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Profile issuance kwargs pinning ``env-1`` gen 1 with a within-envelope dimension."""
    base: dict[str, Any] = {
        "profile_id": "prof-1",
        "profile_generation": 1,
        "profile_version": profile_version(),
        "target_envelope_id": "env-1",
        "target_envelope_generation": 1,
        "governed_dimensions": (profile_dimension(),),
        "scope": ("acct-1",),
    }
    base.update(overrides)
    return base


def issue_profile(**overrides: Any) -> RuntimeSafetyProfile:
    """Issue a valid :class:`RuntimeSafetyProfile` within the ``env-1`` envelope."""
    return RuntimeSafetyProfile.issue(
        scheme=SCHEME, **profile_required_kwargs(**overrides)
    )


def over_envelope_profile(**overrides: Any) -> RuntimeSafetyProfile:
    """A profile whose ``qty`` value (50) strictly exceeds the envelope max (10) — real breach."""
    base: dict[str, Any] = {
        "profile_id": "prof-over",
        "governed_dimensions": (profile_dimension(profile_value=Decimal("50")),),
    }
    base.update(overrides)
    return issue_profile(**base)


def all_members(**overrides: Any) -> tuple[BundleMemberRef, ...]:
    """A complete tuple of all 29 modeled members, each resolved + immutable (clean fixture)."""
    return tuple(
        BundleMemberRef(
            kind=kind,
            member_id=f"m-{kind.value}",
            generation=1,
            digest=f"d-{kind.value}",
            resolved=True,
            immutable=True,
        )
        for kind in BundleMemberKind
    )


def issue_bundle(**overrides: Any) -> SafetyConfigurationBundle:
    """Issue a bundle nesting a valid envelope + within-envelope profile."""
    base: dict[str, Any] = {
        "bundle_id": "b-1",
        "bundle_generation": 1,
        "envelope": issue_envelope(),
        "profile": issue_profile(),
    }
    base.update(overrides)
    return SafetyConfigurationBundle.issue(scheme=SCHEME, **base)


def issue_complete_bundle(**overrides: Any) -> SafetyConfigurationBundle:
    """Issue a bundle whose ``members`` tuple has all 29 modeled members (complete)."""
    return issue_bundle(members=all_members(), **overrides)


def issue_activation(**overrides: Any) -> ActivationRecord:
    """Issue a valid :class:`ActivationRecord` (profile gen 1, predecessor gen 0)."""
    base: dict[str, Any] = {
        "activation_id": "act-1",
        "profile_generation": 1,
        "predecessor_generation": 0,
    }
    base.update(overrides)
    return ActivationRecord.issue(scheme=SCHEME, **base)


def issue_manifest(**overrides: Any) -> ConsumerCompatibilityManifest:
    """Issue a manifest declaring a concrete schema + field surface (non-empty)."""
    base: dict[str, Any] = {
        "manifest_id": "man-1",
        "consumer_identity": "consumer-1",
        "declared_schemas": ("s1",),
        "declared_fields": ("f1",),
        "declared_units": ("sh",),
    }
    base.update(overrides)
    return ConsumerCompatibilityManifest.issue(scheme=SCHEME, **base)


# ---------------------------------------------------------------------------
# Injected-input builders
# ---------------------------------------------------------------------------


def valid_semantic_inputs(**overrides: Any) -> SemanticValidationInputs:
    """Fold-step inputs that (with a within-envelope bundle) make semantic_validation VALID."""
    base: dict[str, Any] = {
        "signature_and_revocation_ok": True,
        "canonical_reproducible": True,
        "cross_field_consistent": True,
        "aggregate_effect_within": True,
        "software_deployment_ok": True,
        "bundle_member_digests_match": True,
        "time_validity_ok": True,
        "change_direction": ChangeDirection.RESTRICTIVE,
    }
    base.update(overrides)
    return SemanticValidationInputs(**base)


def committable_activation_inputs(**overrides: Any) -> ActivationInputs:
    """Activation inputs that fold to COMMITTABLE (all four positive + staging/attestation)."""
    base: dict[str, Any] = {
        "version_fully_active": True,
        "mixed_versions_present": False,
        "units_compatible": True,
        "envelope_bounded": True,
        "staging_complete": True,
        "attestation_complete": True,
    }
    base.update(overrides)
    return ActivationInputs(**base)


def restrictive_direction_inputs(**overrides: Any) -> ChangeDirectionInputs:
    """Change-direction observations that classify a pure tightening as RESTRICTIVE."""
    base: dict[str, Any] = {
        "previously_denied_now_permitted": False,
        "all_dimensions_ordered_conservative": True,
        "semantics_changed": False,
        "any_dimension_widened": False,
        "all_narrowing_or_equal": True,
    }
    base.update(overrides)
    return ChangeDirectionInputs(**base)


def all_preserved_override_inputs(**overrides: Any) -> RestrictiveOverrideInputs:
    """Restrictive-override preservation flags all positively True."""
    base: dict[str, Any] = {
        "no_auto_revert": True,
        "capacity_preserved": True,
        "orders_preserved": True,
        "exposure_preserved": True,
        "unknown_preserved": True,
        "protective_preserved": True,
    }
    base.update(overrides)
    return RestrictiveOverrideInputs(**base)


def lawful_rollback_inputs(**overrides: Any) -> RollbackInputs:
    """Rollback preconditions all positively True (a lawful new proposal)."""
    base: dict[str, Any] = {
        "new_generation_issued": True,
        "current_schema_valid": True,
        "current_approval": True,
        "break_before_make": True,
        "fresh_rearm": True,
    }
    base.update(overrides)
    return RollbackInputs(**base)


def compat_query(**overrides: Any) -> CompatibilityQuery:
    """A compatibility query the :func:`issue_manifest` manifest covers."""
    base: dict[str, Any] = {
        "required_schemas": ("s1",),
        "required_fields": ("f1",),
    }
    base.update(overrides)
    return CompatibilityQuery(**base)
