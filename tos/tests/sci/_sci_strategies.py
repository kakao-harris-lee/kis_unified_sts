"""Shared valid-artifact builders + strategies for the sci property tests (design #29 §6).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #29 §0.3). The builders enforce
the clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must be *genuinely*
complete, never a permissive shortcut):

* a **clean** scope binds every one of the nine §4.10 dimensions to an exact concrete value and sets
  ``scope_complete=True``, so a genuine :func:`~tos.sci.predicates.admission_admits_only_positive`
  item 6 is achievable rather than short-circuited;
* a **clean** source manifest carries three exact non-mutable identity digests, an ``INDEPENDENT``
  hag verdict with its reviewer set, ``history_rewrite_detected=False``, ``review_current=True``,
  ``closure_complete=True``, and **all eight** §9 line 265 closure digests;
* a **clean** closure manifest carries **all seventeen** §11 set digests plus the resolution policy
  and correction state, all four completeness flags ``True``, and all three floating / dynamic
  permissions explicit ``False``;
* a **clean** decision is a genuine ``ADMIT`` with **all nine** scalar digest bindings, both
  structured bindings, a strictly advancing candidate generation, an equal-or-ahead restriction
  floor, ``consumed=False``, and ``current=True``;
* a **clean** admitted release set is complete / committed / current / compatibility-complete with a
  positively-resolved restriction state and a strictly advancing generation;
* the **polarity strategies** deliberately generate ``None`` / ``False`` / ``True`` tri-bools so the
  polarity seals (the #18/#22 MAJOR-2 lesson) are exercised across every ``bool | None`` field.

Every digest fixture is metacharacter-free and is not a catalogued mutable-name sentinel, so
:func:`~tos.sci.predicates.mutable_name_is_not_identity` accepts it; the reserved ``"TBD"``
placeholder never appears in a clean value. Every generation / floor value is an explicit fixture
``int`` ordering scalar — nothing here is a *policy* number; the real sci bounds are the ten
VERIFICATION-PROFILE-002 keys, all ``null`` in Phase 1 (design #29 §8).
"""

from __future__ import annotations

from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.sci import (
    AdmissionBindingSet,
    AdmissionResult,
    AdmittedReleaseSet,
    ArtifactAdmissionDecision,
    AttestationTimeBinding,
    BuildProvenanceAttestation,
    BuildProvenanceBinding,
    DecisionTimeBinding,
    DependencyAndToolchainBinding,
    DependencyClosureDigestSet,
    DependencyToolchainClosureManifest,
    IndependenceResult,
    PolicyBinding,
    ReleaseArtifactBinding,
    ReleaseArtifactManifest,
    ReleaseBinding,
    ReleaseRestriction,
    RuntimeArtifactAttestation,
    SoftwareReleasePolicy,
    SourceRevisionManifest,
    SupplyChainScope,
    VerificationProfileBinding,
)

#: The injected provisional canonicalizer (REUSE, design #29 §3.1 — no new scheme).
SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Injected ``bool | None`` flag (fail-closed on ``None`` / the wrong polarity).
TRIBOOL = st.sampled_from([True, False, None])

#: Injected tri-state admission result including the absent case.
ADMISSION_RESULTS = st.sampled_from([*list(AdmissionResult), None])

#: Injected tri-state independence verdict including the absent case.
INDEPENDENCE_RESULTS = st.sampled_from([*list(IndependenceResult), None])

#: Fixture ordering scalars — a predecessor and a strictly advancing successor.
PREDECESSOR_GENERATION = 41
CANDIDATE_GENERATION = 42
ACTIVE_RESTRICTION_FLOOR = 7


def clean_scope(**overrides: Any) -> SupplyChainScope:
    """A scope with every §4.10 dimension bound to an exact value and ``scope_complete=True``."""
    kwargs: dict[str, Any] = {
        name: f"d-{name}"
        for name in SupplyChainScope.SCOPE_DIMENSIONS
        if name != "scope_complete"
    }
    kwargs["scope_complete"] = True
    kwargs.update(overrides)
    return SupplyChainScope(**kwargs)


def clean_policy_binding(**overrides: Any) -> PolicyBinding:
    """An exact policy binding (§15 step 1)."""
    kwargs: dict[str, Any] = {
        "software_release_policy_id": "pol-1",
        "policy_generation": 3,
        "policy_digest": "d-policy",
    }
    kwargs.update(overrides)
    return PolicyBinding(**kwargs)


def clean_release_artifact_binding(**overrides: Any) -> ReleaseArtifactBinding:
    """An exact release-artifact binding (id + digest, never the manifest object)."""
    kwargs: dict[str, Any] = {
        "release_artifact_manifest_id": "ram-1",
        "release_artifact_manifest_digest": "d-release-artifact-manifest",
    }
    kwargs.update(overrides)
    return ReleaseArtifactBinding(**kwargs)


def clean_policy(**overrides: Any) -> SoftwareReleasePolicy:
    """A Software Release Policy with every §8 field group bound (§4.3)."""
    kwargs: dict[str, Any] = {
        "policy_id": "pol-1",
        "policy_version": "v1",
        "policy_generation": 3,
        "predecessor_policy_digest": "d-predecessor-policy",
        "scope": clean_scope(),
        "verification_profile_binding": VerificationProfileBinding(
            verification_profile_id="vp-002",
            verification_profile_version="v1",
            verification_profile_digest="d-vp",
        ),
        "approved_bound_set_digest": "d-approved-bounds",
        "approved_limit_set_digest": "d-approved-limits",
        "materiality_default": "CRITICAL",
        "missing_lineage_disposition": "DENY_AND_RESTRICT",
        "unknown_compatibility_disposition": "DENY",
        "unknown_currentness_disposition": "DENY_SEND",
        "mutable_reference_permitted": False,
        "partial_admission_permitted": False,
        "consumer_local_patch_permitted": False,
        "release_set_union_permitted": False,
        "automatic_rollback_permitted": False,
        "automatic_rearm_permitted": False,
        "approved_by_effective_principal_set_digest": "d-approvers",
    }
    for name in SoftwareReleasePolicy.model_fields:
        if name.endswith("_policy_digest") and name not in kwargs:
            kwargs[name] = f"d-{name}"
    kwargs.update(overrides)
    return SoftwareReleasePolicy(**kwargs)


def clean_source_manifest(**overrides: Any) -> SourceRevisionManifest:
    """A source manifest that genuinely satisfies ``source_identity_exact_and_reviewed``."""
    kwargs: dict[str, Any] = {
        "manifest_id": "srm-1",
        "manifest_version": "v1",
        "source_continuity_generation": 5,
        "policy_binding": clean_policy_binding(),
        "repository_identity": "core-repo",
        "repository_environment": "governed",
        "source_revision_digest": "d-source-revision",
        "source_tree_digest": "d-source-tree",
        "source_history_head_digest": "d-source-history-head",
        "source_history_continuity_proof_digest": "d-source-history-continuity",
        "source_review_request_digest": "d-review-request",
        "source_review_policy_digest": "d-review-policy",
        "source_review_decision_digest": "d-review-decision",
        "source_author_effective_principal_id": "principal-author",
        "reviewer_effective_principal_set_digest": "d-reviewer-set",
        "effective_principal_independence_result": IndependenceResult.INDEPENDENT,
        "source_license_and_policy_result": "REVIEWED",
        "history_rewrite_detected": False,
        "closure_complete": True,
        "review_current": True,
        "semantic_result": "REVIEWED",
        "failure_response": "QUARANTINE_AND_DENY",
        "partial_manifest_permitted": False,
        "wildcard_source_permitted": False,
        "manifest_union_permitted": False,
        "consumer_patch_permitted": False,
        "approved_by_effective_principal_set_digest": "d-approvers",
    }
    for name in SourceRevisionManifest.SOURCE_CLOSURE_DIGESTS:
        kwargs[name] = f"d-{name}"
    kwargs.update(overrides)
    return SourceRevisionManifest(**kwargs)


def clean_provenance(**overrides: Any) -> BuildProvenanceAttestation:
    """An attestation that genuinely satisfies ``provenance_is_not_admission``."""
    kwargs: dict[str, Any] = {
        "attestation_id": "bpa-1",
        "attestation_version": "v1",
        "builder_continuity_generation": 9,
        "result": "ATTESTED",
        "policy_binding": clean_policy_binding(),
        "source_revision_manifest_binding": None,
        "dependency_and_toolchain_binding": DependencyAndToolchainBinding(
            closure_manifest_id="dtc-1", closure_manifest_digest="d-closure-manifest"
        ),
        "build_recipe_id": "recipe-1",
        "build_recipe_digest": "d-build-recipe",
        "builder_principal_id": "builder-1",
        "builder_owner_epoch": 2,
        "builder_environment_digest": "d-builder-environment",
        "builder_platform_digest": "d-builder-platform",
        "builder_network_policy_digest": "d-builder-network",
        "builder_cache_state_digest": "d-builder-cache",
        "declared_input_set_digest": "d-declared-inputs",
        "observed_input_set_digest": "d-observed-inputs",
        "declared_environment_digest": "d-declared-environment",
        "observed_environment_digest": "d-observed-environment",
        "output_artifact_digest": "d-output-artifact",
        "output_platform_and_architecture_digest": "d-output-platform",
        "independent_build_attestation_digest": "d-independent-build",
        "reproducibility_comparison_digest": "d-reproducibility-comparison",
        "allowed_nondeterminism_policy_digest": "d-allowed-nondeterminism",
        "observed_nondeterminism_digest": "d-observed-nondeterminism",
        "common_mode_analysis_digest": "d-common-mode",
        "trustworthy_time_binding": AttestationTimeBinding(
            time_health_generation=1,
            receipt_anchor="anchor-1",
            attested_at=100,
            maximum_age_key="MAX_build_provenance_age_ms",
            age_within_approved_limit=True,
        ),
        "all_inputs_declared": True,
        "builder_identity_current": True,
        "reproducibility_requirement_satisfied": True,
        "provenance_complete": True,
        "failure_response": "QUARANTINE_AND_DENY",
        "attestation_replay_permitted": False,
        "favorable_output_selection_permitted": False,
        "attestation_union_permitted": False,
        "signer_identity": "signer-1",
        "signing_key_generation": 4,
        "signature_digest": "d-signature",
    }
    kwargs["source_revision_manifest_binding"] = None
    kwargs.update(overrides)
    return BuildProvenanceAttestation(**kwargs)


def clean_closure_manifest(**overrides: Any) -> DependencyToolchainClosureManifest:
    """A closure manifest that genuinely satisfies ``closure_complete_or_restrictive``."""
    kwargs: dict[str, Any] = {
        "manifest_id": "dtc-1",
        "manifest_version": "v1",
        "closure_generation": 6,
        "policy_binding": clean_policy_binding(),
        "resolution_policy_digest": "d-resolution-policy",
        "software_bill_of_materials_digest": "d-sbom",
        "correction_and_revocation_state_digest": "d-correction-state",
        "common_mode_analysis_digest": "d-common-mode",
        "transitive_closure_complete": True,
        "all_content_digests_verified": True,
        "all_sources_approved": True,
        "all_corrections_and_revocations_current": True,
        "semantic_result": "CLOSED",
        "failure_response": "QUARANTINE_AND_DENY",
        "floating_version_permitted": False,
        "undeclared_network_resolution_permitted": False,
        "runtime_dynamic_resolution_permitted": False,
        "closure_patch_permitted": False,
        "closure_union_permitted": False,
        "approved_by_effective_principal_set_digest": "d-approvers",
    }
    for name in DependencyClosureDigestSet.model_fields:
        kwargs[name] = f"d-{name}"
    kwargs.update(overrides)
    return DependencyToolchainClosureManifest(**kwargs)


def clean_release_artifact_manifest(**overrides: Any) -> ReleaseArtifactManifest:
    """A manifest that genuinely satisfies ``release_artifact_identity_exact``."""
    kwargs: dict[str, Any] = {
        "manifest_id": "ram-1",
        "manifest_version": "v1",
        "artifact_generation": 8,
        "semantic_result": "REVIEWED",
        "policy_binding": clean_policy_binding(),
        "dependency_and_toolchain_binding": DependencyAndToolchainBinding(
            closure_manifest_id="dtc-1", closure_manifest_digest="d-closure-manifest"
        ),
        "build_provenance_binding": BuildProvenanceBinding(
            build_provenance_attestation_id="bpa-1",
            build_provenance_attestation_digest="d-provenance",
        ),
        "artifact_identity": "artifact-1",
        "artifact_content_digest": "d-artifact-content",
        "artifact_type_and_format_digest": "d-artifact-format",
        "platform_and_architecture_digest": "d-platform",
        "image_manifest_and_layer_closure_digest": "d-layer-closure",
        "executable_and_library_set_digest": "d-executables",
        "plugin_and_runtime_module_set_digest": "d-plugins",
        "sidecar_proxy_sdk_and_signer_component_set_digest": "d-sidecars",
        "software_bill_of_materials_digest": "d-sbom",
        "schema_set_digest": "d-schemas",
        "protocol_set_digest": "d-protocols",
        "migration_set_digest": "d-migrations",
        "consumer_compatibility_graph_digest": "d-compatibility-graph",
        "required_configuration_bundle_digest": "d-config-bundle",
        "required_hard_safety_envelope_digest": "d-envelope",
        "required_broker_capability_profile_digest": "d-broker-capability",
        "target_scope_digest": "d-target-scope",
        "registry_identity": "registry-1",
        "registry_custody_proof_digest": "d-custody",
        "artifact_signer_identity": "signer-1",
        "artifact_signing_key_generation": 4,
        "artifact_signature_digest": "d-signature",
        "signing_key_status": "VALID",
        "scan_and_test_evidence_set_digest": "d-scan-evidence",
        "unresolved_finding_set_digest": "d-findings",
        "lineage_complete": True,
        "registry_custody_current": True,
        "compatibility_complete": True,
        "failure_response": "QUARANTINE_AND_DENY",
        "mutable_tag_is_identity": False,
        "partial_manifest_permitted": False,
        "manifest_patch_permitted": False,
        "manifest_union_permitted": False,
    }
    kwargs.update(overrides)
    return ReleaseArtifactManifest(**kwargs)


def clean_decision(**overrides: Any) -> ArtifactAdmissionDecision:
    """A genuine ``ADMIT`` decision with every §15 step 1-7 binding present and exact."""
    kwargs: dict[str, Any] = {
        "decision_id": "aad-1",
        "decision_version": "v1",
        "candidate_release_generation": CANDIDATE_GENERATION,
        "result": AdmissionResult.ADMIT,
        "policy_binding": clean_policy_binding(),
        "release_artifact_binding": clean_release_artifact_binding(),
        "predecessor_release_generation": PREDECESSOR_GENERATION,
        "predecessor_admitted_release_set_digest": "d-predecessor-set",
        "current_release_restriction_floor": ACTIVE_RESTRICTION_FLOOR,
        "reviewer_effective_principal_set_digest": "d-reviewer-set",
        "effective_principal_independence_result": IndependenceResult.INDEPENDENT,
        "decision_reason_set_digest": "d-reasons",
        "unresolved_condition_set_digest": "d-conditions",
        "trustworthy_time_binding": DecisionTimeBinding(
            time_health_generation=1,
            receipt_anchor="anchor-1",
            decided_at=100,
            maximum_age_key="MAX_artifact_admission_decision_age_ms",
            age_within_approved_limit=True,
        ),
        "single_use_consumption_id": "consume-1",
        "consumed": False,
        "consumption_permitted": True,
        "current": True,
        "failure_response": "DENY_AND_RESTRICT",
        "decision_patch_permitted": False,
        "decision_union_permitted": False,
        "scope_widening_permitted": False,
        "automatic_readmission_permitted": False,
    }
    for name in AdmissionBindingSet.model_fields:
        kwargs[name] = f"d-{name}"
    kwargs.update(overrides)
    return ArtifactAdmissionDecision(**kwargs)


def clean_release_set(**overrides: Any) -> AdmittedReleaseSet:
    """A complete, committed, current, compatible admitted release set."""
    kwargs: dict[str, Any] = {
        "release_set_id": "ars-1",
        "release_generation": CANDIDATE_GENERATION,
        "predecessor_release_generation": PREDECESSOR_GENERATION,
        "predecessor_release_set_digest": "d-predecessor-set",
        "result": AdmissionResult.ADMIT,
        "policy_binding": clean_policy_binding(),
        "scope": clean_scope(),
        "release_artifact_manifest_set_digest": "d-manifest-set",
        "artifact_admission_decision_set_digest": "d-decision-set",
        "artifact_lineage_graph_digest": "d-lineage-graph",
        "consumer_compatibility_graph_digest": "d-compatibility-graph",
        "deployment_plan_digest": "d-deployment-plan",
        "required_configuration_bundle_digest": "d-config-bundle",
        "required_runtime_attestation_policy_digest": "d-attestation-policy",
        "artifact_signing_trust_bundle_generation": 2,
        "artifact_signing_trust_bundle_digest": "d-trust-bundle",
        "release_restriction_floor": ACTIVE_RESTRICTION_FLOOR,
        "release_restriction_set_digest": "d-restriction-set",
        "incident_scope_binding_digest": "d-incident-scope",
        "owner_epoch": 3,
        "commit_record_digest": "d-commit-record",
        "committed": True,
        "complete": True,
        "current": True,
        "compatibility_complete": True,
        "restriction_state": "NO_RESTRICTION",
        "failure_response": "DENY_DEPENDENT_NEW_RISK",
        "partial_set_permitted": False,
        "set_patch_permitted": False,
        "set_union_permitted": False,
        "favorable_subset_permitted": False,
        "historical_generation_reuse_permitted": False,
    }
    kwargs.update(overrides)
    return AdmittedReleaseSet(**kwargs)


def clean_runtime_attestation(**overrides: Any) -> RuntimeArtifactAttestation:
    """A runtime attestation whose actual bytes match the admitted set (§18 shape only)."""
    kwargs: dict[str, Any] = {
        "attestation_id": "raa-1",
        "attestation_version": "v1",
        "runtime_continuity_generation": 4,
        "result": "ATTESTED",
        "release_binding": ReleaseBinding(
            software_release_policy_id="pol-1",
            software_release_policy_generation=3,
            software_release_policy_digest="d-policy",
            release_set_id="ars-1",
            release_generation=CANDIDATE_GENERATION,
            admitted_release_set_digest="d-admitted-set",
            release_artifact_manifest_digest="d-release-artifact-manifest",
        ),
        "scope": clean_scope(legal_portfolio=None),
        "workload_identity": "workload-1",
        "workload_owner_epoch": 2,
        "deployment_identity": "deployment-1",
        "deployment_generation": 5,
        "runtime_platform_identity": "platform-1",
        "actual_executable_and_image_digest": "d-actual-image",
        "actual_library_dependency_set_digest": "d-actual-libraries",
        "actual_plugin_and_runtime_module_set_digest": "d-actual-plugins",
        "actual_sidecar_proxy_sdk_and_signer_component_set_digest": "d-actual-sidecars",
        "actual_configuration_bundle_digest": "d-actual-config",
        "expected_runtime_artifact_set_digest": "d-expected-runtime-set",
        "observed_runtime_artifact_set_digest": "d-observed-runtime-set",
        "runtime_artifact_match": True,
        "consumer_compatibility_result": "COMPATIBLE",
        "attestor_identity": "attestor-1",
        "attestor_owner_epoch": 1,
        "attestor_independence_result": IndependenceResult.INDEPENDENT,
        "attestation_evidence_digest": "d-attestation-evidence",
        "release_restriction_floor": ACTIVE_RESTRICTION_FLOOR,
        "current_release_restriction_set_digest": "d-restriction-set",
        "trustworthy_time_binding": AttestationTimeBinding(
            time_health_generation=1,
            receipt_anchor="anchor-1",
            attested_at=100,
            maximum_age_key="MAX_runtime_artifact_attestation_age_ms",
            age_within_approved_limit=True,
        ),
        "current": True,
        "invalidated": False,
        "failure_response": "DENY_SEND_AND_RESTRICT",
        "self_report_only_is_sufficient": False,
        "desired_state_is_actual_state": False,
        "attestation_patch_permitted": False,
        "attestation_union_permitted": False,
    }
    kwargs.update(overrides)
    return RuntimeArtifactAttestation(**kwargs)


def clean_restriction(**overrides: Any) -> ReleaseRestriction:
    """A scope-complete Release Restriction fact covering the greatest credible closure."""
    kwargs: dict[str, Any] = {
        "restriction_id": "rr-1",
        "restriction_generation": 11,
        "restricted_scope": clean_scope(),
        "trigger_class": "SIGNER_COMPROMISE_SUSPECTED",
        "predecessor_restriction_digest": "d-predecessor-restriction",
    }
    kwargs.update(overrides)
    return ReleaseRestriction(**kwargs)


#: The dimension names a greatest-credible-closure lookup injects (§20 line 404).
CREDIBLE_SCOPE_DIMENSIONS = frozenset(
    name for name in SupplyChainScope.SCOPE_DIMENSIONS if name != "scope_complete"
)


def admit_args(**overrides: Any) -> dict[str, Any]:
    """The clean injected argument set for ``admission_admits_only_positive``."""
    kwargs: dict[str, Any] = {
        "decision": clean_decision(),
        "active_restriction_floor": ACTIVE_RESTRICTION_FLOOR,
        "restriction_floor_resolved": True,
        "target_scope": clean_scope(),
        "scope_resolved": True,
        "release_artifact_manifest": clean_release_artifact_manifest(),
        "manifest_resolved": True,
    }
    kwargs.update(overrides)
    return kwargs


def admitted_set_args(**overrides: Any) -> dict[str, Any]:
    """The clean injected argument set for ``admitted_set_no_permissive_union``."""
    members = frozenset({"d-manifest-a", "d-manifest-b"})
    kwargs: dict[str, Any] = {
        "release_set": clean_release_set(),
        "applicable_manifest_digests": members,
        "member_manifest_digests": members,
        "applicable_set_resolved": True,
    }
    kwargs.update(overrides)
    return kwargs
