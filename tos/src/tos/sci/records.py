"""sci digest-bound artifacts — the nine supply-chain ledger citizens (design #29 §2).

Every artifact is a **pydantic v2 frozen model** (``frozen=True, extra="forbid"`` via
:class:`~tos.sci._base.FrozenModel`): ``extra="forbid"`` is the schema-level realization of §8 line
259 ("Unknown fields, mutable references, hidden defaults, local overrides, consumer-selected
substitutions, implicit inheritance, or ``latest`` resolution are prohibited") and frozen is the
append-only realization; there is **no** update / delete / mutate / deploy / sign / admit / activate
/ transmit / arm method on any model (design #29 §0.2 — the constructive-absence canary). Field
names use the **canonical template field names verbatim** (spec terms = code terms, boundary design
#1 §2.4): the eight ``*-template.yaml`` schemas under
``tos-spec/src/part-1-foundation/verification/`` are the single source of truth, and the §6.2
anchor-drift property asserts the model ↔ template correspondence one-to-one.

**Nine id-independent artifacts (design #29 §2.1/§0.4c).** All eight canonical templates carry an
independent ``*_id`` field (``policy_id`` / ``manifest_id`` / ``attestation_id`` / ``decision_id`` /
``release_set_id``) **beside** a separate ``canonical_digest`` field — eight of eight — which is the
structural signature of :class:`~tos.sci._base.IndependentIdArtifact` (``id != f(digest)``; an
``IdDerivedArtifact`` carries no separate mutable ``*_id`` / ``*_version``). The ninth,
:class:`ReleaseRestriction`, is ADR-§5.11-derived and has no canonical template. Because identity is
orthogonal to content, a same-id / different-**covered**-bytes forged, re-issued, or replayed record
is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` (§21 line 416 "admission registry or
Release Generation conflict | fence writers; deny affected scope until one current history is
proven"), and a pre-issuance pair (digest ``None``) is ``NOT_COMPARABLE``.

**SCI is a greenfield release-admission content producer with one landed downstream consumer
(design #29 §0.4b).** ``tos.spg`` (ADR-002-014) already carries the consumption slot
``SemanticValidationInputs.software_deployment_ok`` (``tos/src/tos/spg/records.py`` line 206, gated
``is not True`` at ``tos/src/tos/spg/predicates.py`` line 467) and defers four of the seven
BundleMember items ("Release Generation, compatibility graph, runtime-attestation requirements ...
software compatibility manifests"; ``tos/src/tos/spg/vocabulary.py`` lines 185-187) to
ADR-002-029/030. SCI **produces** that verdict through
:func:`~tos.sci.predicates.software_deployment_ok_verdict` and imports ``tos.spg`` **not at all**
(sibling edge 0, design #29 §3.4) — the seam is a plain injected ``bool``.

**Malformed-model self-defence — positive-result + incomplete-binding coexistence seal (design #29
§2.3; the rlp ``ExactTrialPlan`` / egress QCC / wdr isomorph).** Three artifacts carry a
construction-time coexistence seal:

* :class:`ArtifactAdmissionDecision` — a ``result is AdmissionResult.ADMIT`` while any §15
  mandated binding is ``None`` / ``"TBD"`` / a mutable name is **unconstructable** (an ``ADMIT``
  whose exact bindings are blank cannot exist);
* :class:`AdmittedReleaseSet` — ``complete is True`` while the release-artifact-manifest set digest
  is absent is **unconstructable** (§16 line 346 "Missing artifact ... invalidates the set");
* :class:`SourceRevisionManifest` — an ``INDEPENDENT`` effective-principal verdict while the
  reviewer effective-principal set digest is absent is **unconstructable** (§9 line 267 —
  independence is never credited without the reviewer set it was evaluated over).

The ``model_construct`` escape hatch that skips validators is re-caught in the §5 predicate layer
(defence in depth, design #29 §2.3): the yolk predicates re-derive completeness structurally and
never trust a stored flag.

**Coordinate non-collapse (design #29 §2.3).** No mutable lifecycle coordinate — the decision's
``consumed`` / ``consumption_permitted`` / ``current`` (§15 step 10 single-use invalidation), the
release set's ``current`` and its injected cur-owned ``restriction_state``, the runtime
attestation's ``current`` / ``invalidated``, and the inherited ``status`` — is a covered digest
field: a lawful lifecycle transition or an injected verdict change must not change an artifact's
digest and be mis-flagged as a same-id / different-bytes ``CRITICAL_CONFLICT`` (the rcl / egress /
cur / rlp / wdr coordinate-non-collapse precedent). Every covered field is an immutable claim.
**The price of that exclusion, stated rather than implied**: because the four
non-collapsed coordinates (``AdmittedReleaseSet.current`` / ``restriction_state``,
``RuntimeArtifactAttestation.current`` / ``invalidated``) sit outside the digest, no digest-layer
comparison can detect a forged value for them — **the integrity of the channel that injects them is
load-bearing** and belongs to their owners (cur / ADR-002-024 for ``restriction_state``, the
deployment and attestation paths for the rest, §7 line 232-234). SCI reads each one fail-closed at
the predicate layer and vouches for none of them.

**Numeric bounds are outside ``_REQUIRED_COVERED`` (design #29 §2.3).** The
``age_within_approved_limit`` observations sit inside the trustworthy-time blocks whose limit keys
(``MAX_build_provenance_age_ms`` / ``MAX_artifact_admission_decision_age_ms`` /
``MAX_runtime_artifact_attestation_age_ms``) are all ``null`` with ``owner: TBD`` in Phase 1 (§8), so
requiring them would make every Phase-1 artifact unconstructable. ``_REQUIRED_COVERED`` carries
**structural identity / generation / digest** coordinates only; a missing numeric claim still fails
closed wherever it is consumed.

**Template meta fields deliberately not modelled**: ``artifact_type`` and ``schema_version`` (the tos
base carries the equivalent through ``canonicalization_version`` and the model class itself) and
``authorization_notice`` (prose restated in these docstrings). The §6.2 anchor-drift property
registers those three as the only permitted template-side exclusions.

**ADR-002-027 (``tos.sir``) incident handoff — injected opaque coordinate, edge 0 (§0.4f).** §20 line
406 routes a restriction signal into incident governance. Measured twice, honestly: ``git ls-files
tos/src/tos/sir/`` was **empty** when this package was started and the sibling **landed
mid-implementation** (``tos/src/tos/sir/records.py`` line 246
``SafetyIncidentRecord.incident_generation: int | None``), so the deferral was upgraded to a
test-only seam cross-check (``tos/tests/sci/test_seam_sir.py``). Either way the runtime treatment is
identical and unchanged: incident handoff is ADR-002-027; consumed as injected opaque generation;
SCI carries the coordinate only as ``AdmittedReleaseSet.incident_scope_binding_digest`` and
``ReleaseRestriction.trigger_class``, re-authors no incident lifecycle, and takes **no ``tos.sir``
import and no ``tos.sir`` type reference** (sibling edge 0, §3.4).

Regime tag: release-admission predicate/model substrate only; **closes no SCI-EV** — all twelve
register rows carry ``+Security`` and the organisational gate is entirely unmet; an EV-L1-complete
claim is forbidden. Effective-principal collapse, capacity arithmetic, configuration activation,
per-send egress binding, reproducibility comparison, runtime measurement, signature verification,
and restriction-floor advance are sibling / runtime / human / +Security / +Broker owned.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.sci._base``) + ``tos.sci.*`` only;
no ``shared.*``, no sibling ``tos.*`` (design #29 §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import model_validator

from tos.sci._base import (
    AllFalseSupplyChainAuthority,
    ArtifactIntegrityError,
    IndependentIdArtifact,
)
from tos.sci.state import (
    AttestationTimeBinding,
    BuildProvenanceBinding,
    DecisionTimeBinding,
    DependencyAndToolchainBinding,
    PolicyBinding,
    ReleaseArtifactBinding,
    ReleaseBinding,
    SourceRevisionManifestBinding,
    SupplyChainScope,
    VerificationProfileBinding,
)
from tos.sci.vocabulary import (
    AdmissionResult,
    IndependenceResult,
    _is_template_placeholder,
    is_mutable_name_notation,
)

__all__ = [
    "AdmittedReleaseSet",
    "ArtifactAdmissionDecision",
    "BuildProvenanceAttestation",
    "DependencyToolchainClosureManifest",
    "ReleaseArtifactManifest",
    "ReleaseRestriction",
    "RuntimeArtifactAttestation",
    "SoftwareReleasePolicy",
    "SourceRevisionManifest",
]


def _binding_absent(value: object) -> bool:
    """Whether a mandated binding coordinate is absent, placeholder, or a mutable name.

    A binding is unusable when it is ``None``, the reserved ``"TBD"`` template placeholder — matched
    **case- and padding-insensitively** through the single-sourced
    :func:`~tos.sci.vocabulary._is_template_placeholder`, so ``"tbd"`` / ``" TBD "`` / ``"Tbd"`` are
    all rejected — or, for a string, a mutable-name notation (SCI-INV-002 line 159; §1 line 19).

    The normalization is shared with :func:`~tos.sci.predicates.mutable_name_is_not_identity` on
    purpose: the §2.3 construction-time coexistence seals and the §5 predicate layer are a *two*-layer
    defence, and two layers that normalize a placeholder differently collapse into one.
    """
    if value is None or _is_template_placeholder(value):
        return True
    return isinstance(value, str) and is_mutable_name_notation(value)


class SoftwareReleasePolicy(IndependentIdArtifact):
    """The governed Software Release Policy content model (ADR-002-029 §5.1/§8; design #29 §2.4).

    §5.1 line 103: "The immutable ADR-002-014 governed policy defining source, build, dependency,
    toolchain, provenance, signing, registry, admission, compatibility, deployment, attestation,
    restriction, evidence, and recovery rules for one exact scope." §8 line 249-257 enumerates the
    nine field groups (:data:`~tos.sci.vocabulary.SOFTWARE_RELEASE_POLICY_FIELD_GROUPS`) that the
    seventeen ``*_policy_digest`` fields below realize
    (:class:`~tos.sci.state.SoftwareReleasePolicyFieldGroups` is their anchor view).

    SCI authors the policy *content* model only: its **activation is spg / ADR-002-014 governed**
    (§8 line 259 "Policy activation follows ADR-002-014 and creates neither artifact admission nor
    live permission"), carried as the injected ``policy_generation`` scalar and re-authored not at
    all (design #29 §3.5). An :class:`~tos.sci._base.IndependentIdArtifact` (``id != f(digest)``).
    Its :class:`~tos.sci._base.AllFalseSupplyChainAuthority` is all-false — a policy is governed
    content, not permission (SCI-INV-001 line 155). Every numeric bound is an injected
    Profile-INSTANCE value, all ``null`` in Phase 1 (§8; design #29 §8).
    """

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "policy_id",
        "policy_generation",
        "canonical_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "policy_version",
            "policy_generation",
            "predecessor_policy_digest",
            "scope",
            "source_review_policy_digest",
            "effective_principal_policy_digest",
            "build_recipe_policy_digest",
            "builder_identity_policy_digest",
            "build_network_policy_digest",
            "determinism_and_reproducibility_policy_digest",
            "dependency_and_toolchain_policy_digest",
            "package_source_policy_digest",
            "artifact_signing_and_key_policy_digest",
            "artifact_registry_custody_policy_digest",
            "artifact_admission_policy_digest",
            "compatibility_policy_digest",
            "deployment_promotion_policy_digest",
            "runtime_attestation_policy_digest",
            "restriction_and_incident_policy_digest",
            "recovery_and_restore_policy_digest",
            "evidence_policy_digest",
            "verification_profile_binding",
            "approved_bound_set_digest",
            "approved_limit_set_digest",
            "materiality_default",
            "missing_lineage_disposition",
            "unknown_compatibility_disposition",
            "unknown_currentness_disposition",
            "mutable_reference_permitted",
            "partial_admission_permitted",
            "consumer_local_patch_permitted",
            "release_set_union_permitted",
            "automatic_rollback_permitted",
            "automatic_rearm_permitted",
            "approved_by_effective_principal_set_digest",
            "effective_from",
            "review_due",
            "authority",
        }
    )

    policy_id: str | None = None
    policy_version: str | None = None
    #: Injected spg / ADR-002-014 governed activation generation (§8 line 259).
    policy_generation: int | None = None
    predecessor_policy_digest: str | None = None
    scope: SupplyChainScope | None = None
    source_review_policy_digest: str | None = None
    effective_principal_policy_digest: str | None = None
    build_recipe_policy_digest: str | None = None
    builder_identity_policy_digest: str | None = None
    build_network_policy_digest: str | None = None
    determinism_and_reproducibility_policy_digest: str | None = None
    dependency_and_toolchain_policy_digest: str | None = None
    package_source_policy_digest: str | None = None
    artifact_signing_and_key_policy_digest: str | None = None
    artifact_registry_custody_policy_digest: str | None = None
    artifact_admission_policy_digest: str | None = None
    compatibility_policy_digest: str | None = None
    deployment_promotion_policy_digest: str | None = None
    runtime_attestation_policy_digest: str | None = None
    restriction_and_incident_policy_digest: str | None = None
    recovery_and_restore_policy_digest: str | None = None
    evidence_policy_digest: str | None = None
    verification_profile_binding: VerificationProfileBinding | None = None
    approved_bound_set_digest: str | None = None
    approved_limit_set_digest: str | None = None
    materiality_default: str | None = None
    missing_lineage_disposition: str | None = None
    unknown_compatibility_disposition: str | None = None
    unknown_currentness_disposition: str | None = None
    #: Negative polarity — only an explicit ``is False`` is clear (§8 line 259; design #29 §5.0).
    mutable_reference_permitted: bool | None = None
    partial_admission_permitted: bool | None = None
    consumer_local_patch_permitted: bool | None = None
    release_set_union_permitted: bool | None = None
    automatic_rollback_permitted: bool | None = None
    automatic_rearm_permitted: bool | None = None
    approved_by_effective_principal_set_digest: str | None = None
    #: Injected ordering scalars, never a clock (design #29 §3.2).
    effective_from: int | None = None
    review_due: int | None = None
    #: §7 / SCI-INV-001 — a policy is governed content, not permission.
    authority: AllFalseSupplyChainAuthority = AllFalseSupplyChainAuthority()


class SourceRevisionManifest(IndependentIdArtifact):
    """The immutable Source Revision Manifest (ADR-002-029 §5.2/§9; design #29 §2.4).

    §5.2 line 107: "An immutable manifest binding one exact repository identity, source-tree digest,
    revision digest, review-policy digest, generated-source digest, submodule-closure digest,
    external-source digest, and source-history continuity identity." §9 line 265 closes the source
    side: "The closure includes generated source, submodules, vendored objects, large-file objects,
    schemas, migration source, build scripts, code generators, lock files, and safety-relevant
    documentation consumed by generation or build."

    ``repository_identity`` may legitimately be a human-readable name — it is **not** identity: §1
    line 19 "A branch, tag, package name, registry path, service label, mutable image tag,
    ``latest``, local cache, successful build, passing scan, or historical signature is not artifact
    identity". The exact identity is the three digests (``source_revision_digest`` /
    ``source_tree_digest`` / ``source_history_head_digest``) that
    :func:`~tos.sci.predicates.source_identity_exact_and_reviewed` gates through
    :func:`~tos.sci.predicates.mutable_name_is_not_identity`.

    ``effective_principal_independence_result`` is an **injected hag verdict** (ADR-002-015; design
    #29 §0.4e) — SCI credits ``INDEPENDENT`` only, and re-authors no collapse, quorum, or
    account-graph logic. §9 line 267: "Repository administration, branch protection, signed commits,
    review count, or merge status alone does not prove independence when one person controls the
    underlying accounts, recovery paths, automation, or signing identities."

    **Coexistence seal (§2.3).** An ``INDEPENDENT`` verdict while
    ``reviewer_effective_principal_set_digest`` is absent is **unconstructable**: independence is
    never credited without the reviewer set it was evaluated over.
    """

    _ID_FIELD: ClassVar[str] = "manifest_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "manifest_id",
        "repository_identity",
        "source_revision_digest",
        "source_tree_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "manifest_version",
            "source_continuity_generation",
            "policy_binding",
            "repository_identity",
            "repository_environment",
            "source_revision_digest",
            "source_tree_digest",
            "source_history_head_digest",
            "source_history_continuity_proof_digest",
            "source_review_request_digest",
            "source_review_policy_digest",
            "source_review_decision_digest",
            "source_author_effective_principal_id",
            "reviewer_effective_principal_set_digest",
            "effective_principal_independence_result",
            "generated_source_closure_digest",
            "submodule_closure_digest",
            "large_file_object_closure_digest",
            "vendored_source_closure_digest",
            "external_source_closure_digest",
            "schema_and_migration_source_digest",
            "build_script_source_digest",
            "code_generator_source_digest",
            "source_license_and_policy_result",
            "history_rewrite_detected",
            "closure_complete",
            "review_current",
            "semantic_result",
            "failure_response",
            "partial_manifest_permitted",
            "wildcard_source_permitted",
            "manifest_union_permitted",
            "consumer_patch_permitted",
            "approved_by_effective_principal_set_digest",
            "effective_from",
            "review_due",
            "authority",
        }
    )

    #: The eight §9 line 265 source-closure digests (template lines 24-31) — the §5.1 item 5 anchor.
    SOURCE_CLOSURE_DIGESTS: ClassVar[tuple[str, ...]] = (
        "generated_source_closure_digest",
        "submodule_closure_digest",
        "large_file_object_closure_digest",
        "vendored_source_closure_digest",
        "external_source_closure_digest",
        "schema_and_migration_source_digest",
        "build_script_source_digest",
        "code_generator_source_digest",
    )

    manifest_id: str | None = None
    manifest_version: str | None = None
    #: §9 line 269 — force push, history rewrite, or repository restore advances this generation.
    source_continuity_generation: int | None = None
    policy_binding: PolicyBinding | None = None
    #: A mutable repository name is **not** identity (§1 line 19) — carried, never gated on.
    repository_identity: str | None = None
    repository_environment: str | None = None
    source_revision_digest: str | None = None
    source_tree_digest: str | None = None
    source_history_head_digest: str | None = None
    source_history_continuity_proof_digest: str | None = None
    source_review_request_digest: str | None = None
    source_review_policy_digest: str | None = None
    source_review_decision_digest: str | None = None
    source_author_effective_principal_id: str | None = None
    reviewer_effective_principal_set_digest: str | None = None
    #: Injected hag (ADR-002-015) verdict — ``INDEPENDENT`` only (design #29 §0.4e).
    effective_principal_independence_result: IndependenceResult | None = None
    generated_source_closure_digest: str | None = None
    submodule_closure_digest: str | None = None
    large_file_object_closure_digest: str | None = None
    vendored_source_closure_digest: str | None = None
    external_source_closure_digest: str | None = None
    schema_and_migration_source_digest: str | None = None
    build_script_source_digest: str | None = None
    code_generator_source_digest: str | None = None
    #: Opaque injected token — **not** an admission result (§7 line 232).
    source_license_and_policy_result: str | None = None
    #: Negative polarity — only ``is False`` is clear (§9 line 269; design #29 §5.0).
    history_rewrite_detected: bool | None = None
    #: Positive polarity — only ``is True`` is a closed source lineage (SCI-INV-003).
    closure_complete: bool | None = None
    review_current: bool | None = None
    #: Opaque injected token — **not** an admission result (design #29 §2.2 MINOR-2).
    semantic_result: str | None = None
    failure_response: str | None = None
    #: Negative polarity — only an explicit ``is False`` is clear.
    partial_manifest_permitted: bool | None = None
    wildcard_source_permitted: bool | None = None
    manifest_union_permitted: bool | None = None
    consumer_patch_permitted: bool | None = None
    approved_by_effective_principal_set_digest: str | None = None
    effective_from: int | None = None
    review_due: int | None = None
    #: §7 / SCI-INV-001 — a source manifest is governed content, not permission.
    authority: AllFalseSupplyChainAuthority = AllFalseSupplyChainAuthority()

    @model_validator(mode="after")
    def _independent_requires_reviewer_set(self) -> SourceRevisionManifest:
        """An ``INDEPENDENT`` verdict without a reviewer set digest is unconstructable (§2.3)."""
        if self.effective_principal_independence_result is not (
            IndependenceResult.INDEPENDENT
        ):
            return self
        if _binding_absent(self.reviewer_effective_principal_set_digest):
            raise ArtifactIntegrityError(
                "SourceRevisionManifest cannot claim effective_principal_independence_result "
                "INDEPENDENT while reviewer_effective_principal_set_digest is absent, 'TBD', or "
                "a mutable name — independence is credited only over the exact reviewer "
                "effective-principal set it was evaluated across (ADR-002-029 §9 line 267 / "
                "SCI-INV-007 line 179; design #29 §2.3)"
            )
        return self


class DependencyToolchainClosureManifest(IndependentIdArtifact):
    """The complete Dependency and Toolchain Closure Manifest (§5.4/§11; design #29 §2.4).

    §5.4 line 115: "An immutable manifest binding the complete transitive dependency, build script,
    plugin, compiler, linker, interpreter, SDK, code generator, base image, operating-system
    package, runtime-loaded module, registry source, and resolution-policy closure by canonical
    digest." The seventeen set digests (template lines 15-30 and 34) are anchored by
    :class:`~tos.sci.state.DependencyClosureDigestSet` and consumed dimension-by-dimension by
    :func:`~tos.sci.predicates.closure_complete_or_restrictive`.

    §11 line 289: "Missing dependency, floating version, mutable package source, ambiguous platform
    selection, unknown transitive script, unavailable status source, or unresolved correction is
    restrictive. Majority registry results, previous successful install, local package cache, or
    expected compatibility cannot supply a favorable answer."

    ``floating_version_permitted`` / ``undeclared_network_resolution_permitted`` /
    ``runtime_dynamic_resolution_permitted`` are **policy permissions**, not observed states (design
    #29 §5.0 / M1): they are negative polarity and only an explicit ``is False`` is clear.
    """

    _ID_FIELD: ClassVar[str] = "manifest_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "manifest_id",
        "closure_generation",
        "resolution_policy_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "manifest_version",
            "closure_generation",
            "policy_binding",
            "source_revision_manifest_binding",
            "build_dependency_set_digest",
            "runtime_dependency_set_digest",
            "build_script_set_digest",
            "plugin_set_digest",
            "compiler_and_linker_set_digest",
            "interpreter_set_digest",
            "sdk_set_digest",
            "code_generator_set_digest",
            "base_image_set_digest",
            "operating_system_package_set_digest",
            "native_library_set_digest",
            "dynamic_module_set_digest",
            "sidecar_and_proxy_component_set_digest",
            "migration_tool_set_digest",
            "signer_component_set_digest",
            "package_source_set_digest",
            "resolution_policy_digest",
            "software_bill_of_materials_digest",
            "correction_and_revocation_state_digest",
            "compatibility_edge_set_digest",
            "common_mode_analysis_digest",
            "transitive_closure_complete",
            "all_content_digests_verified",
            "all_sources_approved",
            "all_corrections_and_revocations_current",
            "semantic_result",
            "failure_response",
            "floating_version_permitted",
            "undeclared_network_resolution_permitted",
            "runtime_dynamic_resolution_permitted",
            "closure_patch_permitted",
            "closure_union_permitted",
            "approved_by_effective_principal_set_digest",
            "effective_from",
            "review_due",
            "authority",
        }
    )

    manifest_id: str | None = None
    manifest_version: str | None = None
    closure_generation: int | None = None
    policy_binding: PolicyBinding | None = None
    source_revision_manifest_binding: SourceRevisionManifestBinding | None = None
    build_dependency_set_digest: str | None = None
    runtime_dependency_set_digest: str | None = None
    build_script_set_digest: str | None = None
    plugin_set_digest: str | None = None
    compiler_and_linker_set_digest: str | None = None
    interpreter_set_digest: str | None = None
    sdk_set_digest: str | None = None
    code_generator_set_digest: str | None = None
    base_image_set_digest: str | None = None
    operating_system_package_set_digest: str | None = None
    native_library_set_digest: str | None = None
    dynamic_module_set_digest: str | None = None
    sidecar_and_proxy_component_set_digest: str | None = None
    migration_tool_set_digest: str | None = None
    signer_component_set_digest: str | None = None
    package_source_set_digest: str | None = None
    #: §11 line 287 — the resolution policy is the source of truth for any excluded axis; its
    #: content is opaque to L1, so L1 conservatively requires **all seventeen** dimensions (§5.3).
    resolution_policy_digest: str | None = None
    software_bill_of_materials_digest: str | None = None
    correction_and_revocation_state_digest: str | None = None
    compatibility_edge_set_digest: str | None = None
    common_mode_analysis_digest: str | None = None
    #: Positive polarity — only ``is True`` is a complete transitive closure (SCI-INV-005).
    transitive_closure_complete: bool | None = None
    all_content_digests_verified: bool | None = None
    all_sources_approved: bool | None = None
    all_corrections_and_revocations_current: bool | None = None
    #: Opaque injected token — **not** an admission result (design #29 §2.2 MINOR-2).
    semantic_result: str | None = None
    failure_response: str | None = None
    #: Negative polarity **policy permission** — only ``is False`` is clear (§11 line 289).
    floating_version_permitted: bool | None = None
    undeclared_network_resolution_permitted: bool | None = None
    runtime_dynamic_resolution_permitted: bool | None = None
    closure_patch_permitted: bool | None = None
    closure_union_permitted: bool | None = None
    approved_by_effective_principal_set_digest: str | None = None
    effective_from: int | None = None
    review_due: int | None = None
    #: §7 / SCI-INV-001 — a closure manifest is governed content, not permission.
    authority: AllFalseSupplyChainAuthority = AllFalseSupplyChainAuthority()


class BuildProvenanceAttestation(IndependentIdArtifact):
    """The Build Provenance Attestation (§5.5/§10/§12; SCI-INV-004; design #29 §2.4).

    §5.5 line 119: "An authenticated **non-authorizing** statement binding one builder identity and
    epoch, source manifest, build recipe, dependency and toolchain closure, build environment,
    output artifact digest, and trustworthy-time evidence." §12 line 295: "The signer authenticates
    that statement; it does not certify safety."

    ``result`` (template line 8) is an **opaque** ``str | None``, deliberately **not** an
    :class:`~tos.sci.vocabulary.AdmissionResult` (design #29 §2.2 MINOR-2): §7 line 232 "attestation
    is a fact, not permission", and SCI-INV-004 line 167 — "Valid build provenance or a reproducible
    output does not prove semantic safety, absence of malicious source, current admission,
    compatibility, or live permission." A provenance attestation can never carry an ``ADMIT``;
    :func:`~tos.sci.predicates.provenance_is_not_admission` seals that structurally by requiring
    ``authority.proves_semantic_correctness is False`` **and**
    ``authority.creates_artifact_admission is False``.

    The actual byte comparison lives in ``reproducibility_comparison_digest`` (template line 34) and
    ``independent_build_attestation_digest`` (line 33): SCI performs **no** reproduction, no byte
    diff, and no common-mode analysis — those are +L2 / +Security (§12 line 297; design #29 §0.2).
    """

    _ID_FIELD: ClassVar[str] = "attestation_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "attestation_id",
        "builder_continuity_generation",
        "output_artifact_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "attestation_version",
            "builder_continuity_generation",
            "result",
            "policy_binding",
            "source_revision_manifest_binding",
            "dependency_and_toolchain_binding",
            "build_recipe_id",
            "build_recipe_digest",
            "builder_principal_id",
            "builder_owner_epoch",
            "builder_environment_digest",
            "builder_platform_digest",
            "builder_network_policy_digest",
            "builder_cache_state_digest",
            "declared_input_set_digest",
            "observed_input_set_digest",
            "declared_environment_digest",
            "observed_environment_digest",
            "output_artifact_digest",
            "output_platform_and_architecture_digest",
            "independent_build_attestation_digest",
            "reproducibility_comparison_digest",
            "allowed_nondeterminism_policy_digest",
            "observed_nondeterminism_digest",
            "common_mode_analysis_digest",
            "trustworthy_time_binding",
            "all_inputs_declared",
            "builder_identity_current",
            "reproducibility_requirement_satisfied",
            "provenance_complete",
            "failure_response",
            "attestation_replay_permitted",
            "favorable_output_selection_permitted",
            "attestation_union_permitted",
            "signer_identity",
            "signing_key_generation",
            "signature_digest",
            "authority",
        }
    )

    attestation_id: str | None = None
    attestation_version: str | None = None
    #: §10 line 279 — builder restart, replacement, or recovery creates a new continuity identity.
    builder_continuity_generation: int | None = None
    #: Opaque injected token — **never** an admission result (§7 line 232; SCI-INV-004).
    result: str | None = None
    policy_binding: PolicyBinding | None = None
    source_revision_manifest_binding: SourceRevisionManifestBinding | None = None
    dependency_and_toolchain_binding: DependencyAndToolchainBinding | None = None
    build_recipe_id: str | None = None
    build_recipe_digest: str | None = None
    builder_principal_id: str | None = None
    builder_owner_epoch: int | None = None
    builder_environment_digest: str | None = None
    builder_platform_digest: str | None = None
    builder_network_policy_digest: str | None = None
    builder_cache_state_digest: str | None = None
    declared_input_set_digest: str | None = None
    observed_input_set_digest: str | None = None
    declared_environment_digest: str | None = None
    observed_environment_digest: str | None = None
    output_artifact_digest: str | None = None
    output_platform_and_architecture_digest: str | None = None
    #: §12 line 297 independent-reproduction anchor — the comparison itself is +L2 / +Security.
    independent_build_attestation_digest: str | None = None
    reproducibility_comparison_digest: str | None = None
    allowed_nondeterminism_policy_digest: str | None = None
    observed_nondeterminism_digest: str | None = None
    common_mode_analysis_digest: str | None = None
    trustworthy_time_binding: AttestationTimeBinding | None = None
    #: Positive polarity — only ``is True`` is clear (§10 line 275; §12 line 299).
    all_inputs_declared: bool | None = None
    builder_identity_current: bool | None = None
    reproducibility_requirement_satisfied: bool | None = None
    provenance_complete: bool | None = None
    failure_response: str | None = None
    #: Negative polarity — only ``is False`` is clear (§12 line 299 "the release process cannot
    #: select the favorable artifact").
    attestation_replay_permitted: bool | None = None
    favorable_output_selection_permitted: bool | None = None
    attestation_union_permitted: bool | None = None
    signer_identity: str | None = None
    signing_key_generation: int | None = None
    signature_digest: str | None = None
    #: §7 / SCI-INV-004 — provenance proves no semantic correctness and creates no admission.
    authority: AllFalseSupplyChainAuthority = AllFalseSupplyChainAuthority()


class ReleaseArtifactManifest(IndependentIdArtifact):
    """The Release Artifact Manifest (§5.6/§13/§14; design #29 §2.4).

    §5.6 line 123: "An immutable manifest binding the exact release bytes, platform and
    architecture, source and build lineage, dependency closure, software bill of materials digest,
    schemas, protocols, migrations, compatibility graph, required policy/configuration identities,
    and intended deployment scope."

    ``mutable_tag_is_identity`` (template line 51) is the SCI-INV-002 seal in negative polarity —
    only an explicit ``is False`` is clear — and is consumed by
    :func:`~tos.sci.predicates.release_artifact_identity_exact` (design #29 §2.2 NEW-5). §14 line
    315: "Release artifacts SHALL be stored and retrieved by immutable content digest. Registry tags
    and paths may be discovery metadata only."

    ``signing_key_status`` (template line 44) stays an **opaque injected token**: key validity,
    rotation, and revocation are +Security (§13; SCI-INV-008), and SCI performs no signature
    verification whatsoever (design #29 §0.2).
    """

    _ID_FIELD: ClassVar[str] = "manifest_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "manifest_id",
        "artifact_content_digest",
        "platform_and_architecture_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "manifest_version",
            "artifact_generation",
            "semantic_result",
            "policy_binding",
            "source_revision_manifest_binding",
            "dependency_and_toolchain_binding",
            "build_provenance_binding",
            "artifact_identity",
            "artifact_content_digest",
            "artifact_type_and_format_digest",
            "platform_and_architecture_digest",
            "image_manifest_and_layer_closure_digest",
            "executable_and_library_set_digest",
            "plugin_and_runtime_module_set_digest",
            "sidecar_proxy_sdk_and_signer_component_set_digest",
            "software_bill_of_materials_digest",
            "schema_set_digest",
            "protocol_set_digest",
            "migration_set_digest",
            "consumer_compatibility_graph_digest",
            "required_configuration_bundle_digest",
            "required_hard_safety_envelope_digest",
            "required_broker_capability_profile_digest",
            "target_scope_digest",
            "registry_identity",
            "registry_custody_proof_digest",
            "artifact_signer_identity",
            "artifact_signing_key_generation",
            "artifact_signature_digest",
            "signing_key_status",
            "scan_and_test_evidence_set_digest",
            "unresolved_finding_set_digest",
            "lineage_complete",
            "registry_custody_current",
            "compatibility_complete",
            "failure_response",
            "mutable_tag_is_identity",
            "partial_manifest_permitted",
            "manifest_patch_permitted",
            "manifest_union_permitted",
            "authority",
        }
    )

    manifest_id: str | None = None
    manifest_version: str | None = None
    artifact_generation: int | None = None
    #: Opaque injected token — **not** an admission result (design #29 §2.2 MINOR-2).
    semantic_result: str | None = None
    policy_binding: PolicyBinding | None = None
    source_revision_manifest_binding: SourceRevisionManifestBinding | None = None
    dependency_and_toolchain_binding: DependencyAndToolchainBinding | None = None
    build_provenance_binding: BuildProvenanceBinding | None = None
    artifact_identity: str | None = None
    #: The exact release bytes' digest — an **injected opaque scalar**, not a tos model (§0.4c).
    artifact_content_digest: str | None = None
    artifact_type_and_format_digest: str | None = None
    platform_and_architecture_digest: str | None = None
    image_manifest_and_layer_closure_digest: str | None = None
    executable_and_library_set_digest: str | None = None
    plugin_and_runtime_module_set_digest: str | None = None
    sidecar_proxy_sdk_and_signer_component_set_digest: str | None = None
    software_bill_of_materials_digest: str | None = None
    schema_set_digest: str | None = None
    protocol_set_digest: str | None = None
    migration_set_digest: str | None = None
    consumer_compatibility_graph_digest: str | None = None
    #: The three §5.6 required-identity digests (template lines 35-37) — spg / brokercap owned.
    required_configuration_bundle_digest: str | None = None
    required_hard_safety_envelope_digest: str | None = None
    required_broker_capability_profile_digest: str | None = None
    target_scope_digest: str | None = None
    registry_identity: str | None = None
    registry_custody_proof_digest: str | None = None
    artifact_signer_identity: str | None = None
    artifact_signing_key_generation: int | None = None
    artifact_signature_digest: str | None = None
    #: Opaque injected +Security token (§13; SCI-INV-008) — SCI verifies no signature.
    signing_key_status: str | None = None
    scan_and_test_evidence_set_digest: str | None = None
    unresolved_finding_set_digest: str | None = None
    #: Positive polarity — only ``is True`` is clear (§5.6/§14; SCI-INV-003/011).
    lineage_complete: bool | None = None
    registry_custody_current: bool | None = None
    compatibility_complete: bool | None = None
    failure_response: str | None = None
    #: Negative polarity — only ``is False`` is clear (SCI-INV-002 line 159).
    mutable_tag_is_identity: bool | None = None
    partial_manifest_permitted: bool | None = None
    manifest_patch_permitted: bool | None = None
    manifest_union_permitted: bool | None = None
    #: §7 / SCI-INV-001 — a release-artifact manifest is governed content, not permission.
    authority: AllFalseSupplyChainAuthority = AllFalseSupplyChainAuthority()


class ArtifactAdmissionDecision(IndependentIdArtifact):
    """The single-use non-authorizing Artifact Admission Decision (§5.7/§15; design #29 §2.4).

    §5.7 line 127: "An immutable single-use non-authorizing result of ``ADMIT``, ``DENY``, or
    ``UNKNOWN`` for one exact Release Artifact Manifest, Software Release Policy, compatibility
    graph, target scope, and predecessor Release Generation." §1 line 21: "``ADMIT`` means only that
    the exact artifact is eligible to be included in one new **Admitted Release Set**."

    The nine scalar digest bindings (template lines 16-24) are §15 step 2-6's verification results
    **sealed as digests**: SCI checks their structural presence and rejects mutable names, and does
    **no** signature verification, registry retrieval, scan execution, or SBOM parse — those results
    are +Security-produced and enter through the digests (design #29 §0.2 / C1-3, which removed the
    invented ``*_verified`` booleans an earlier draft had).

    The four-field single-use block (``single_use_consumption_id`` / ``consumed`` /
    ``consumption_permitted`` / ``current``, template lines 38-41) realizes §15 step 10 "invalidate
    the single-use decision and every stale competing candidate"; the three mutable ones are
    **outside** the covered digest (coordinate non-collapse, §2.3).

    **Coexistence seal (§2.3 — this package's central seal).** A ``result is
    AdmissionResult.ADMIT`` while **any** §15 mandated binding is ``None`` / ``"TBD"`` / a mutable
    name is **unconstructable**: an ``ADMIT`` whose exact policy, artifact, lineage, closure,
    provenance, compatibility, scope, predecessor generation, or restriction floor is blank cannot
    exist (SCI-INV-006 line 175 "Missing, wildcarded, patched, unioned, mixed, or conflicting scope
    is ``UNKNOWN`` or ``DENY``"). The §5.4 predicate re-derives the same completeness structurally,
    so a ``model_construct`` bypass is caught at the second layer.
    """

    _ID_FIELD: ClassVar[str] = "decision_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "decision_id",
        "decision_version",
        "policy_binding.software_release_policy_id",
        "release_artifact_binding.release_artifact_manifest_id",
        "target_scope_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "decision_version",
            "candidate_release_generation",
            "result",
            "policy_binding",
            "release_artifact_binding",
            "source_revision_manifest_digest",
            "dependency_and_toolchain_closure_manifest_digest",
            "build_provenance_attestation_digest",
            "artifact_signature_and_key_status_digest",
            "registry_custody_proof_digest",
            "compatibility_graph_digest",
            "scan_test_and_finding_evidence_digest",
            "common_mode_analysis_digest",
            "target_scope_digest",
            "predecessor_release_generation",
            "predecessor_admitted_release_set_digest",
            "current_release_restriction_floor",
            "reviewer_effective_principal_set_digest",
            "effective_principal_independence_result",
            "decision_reason_set_digest",
            "unresolved_condition_set_digest",
            "trustworthy_time_binding",
            "single_use_consumption_id",
            "failure_response",
            "decision_patch_permitted",
            "decision_union_permitted",
            "scope_widening_permitted",
            "automatic_readmission_permitted",
            "authority",
        }
    )

    #: The §15 step 1-7 mandated bindings whose absence makes an ``ADMIT`` unconstructable (§2.3).
    #: Dotted paths resolve through the structured binding blocks.
    MANDATED_ADMIT_BINDINGS: ClassVar[tuple[str, ...]] = (
        "policy_binding.software_release_policy_id",
        "release_artifact_binding.release_artifact_manifest_id",
        "release_artifact_binding.release_artifact_manifest_digest",
        "source_revision_manifest_digest",
        "dependency_and_toolchain_closure_manifest_digest",
        "build_provenance_attestation_digest",
        "compatibility_graph_digest",
        "target_scope_digest",
        "predecessor_release_generation",
        "current_release_restriction_floor",
    )

    decision_id: str | None = None
    decision_version: str | None = None
    #: The candidate Release Generation ordering scalar (§5.8; design #29 §5.0 NEW-1).
    candidate_release_generation: int | None = None
    #: The only ``AdmissionResult``-typed field besides ``AdmittedReleaseSet.result`` (MINOR-2).
    result: AdmissionResult | None = None
    policy_binding: PolicyBinding | None = None
    release_artifact_binding: ReleaseArtifactBinding | None = None
    source_revision_manifest_digest: str | None = None
    dependency_and_toolchain_closure_manifest_digest: str | None = None
    build_provenance_attestation_digest: str | None = None
    #: §15 step 5-6 verification results sealed as +Security digests — never re-verified here.
    artifact_signature_and_key_status_digest: str | None = None
    registry_custody_proof_digest: str | None = None
    compatibility_graph_digest: str | None = None
    scan_test_and_finding_evidence_digest: str | None = None
    common_mode_analysis_digest: str | None = None
    target_scope_digest: str | None = None
    predecessor_release_generation: int | None = None
    predecessor_admitted_release_set_digest: str | None = None
    #: §15 step 7 "every current restriction floor" — an ``int`` ordering scalar (design #29 §5.0).
    current_release_restriction_floor: int | None = None
    reviewer_effective_principal_set_digest: str | None = None
    #: Injected hag (ADR-002-015) verdict — ``INDEPENDENT`` only (design #29 §0.4e).
    effective_principal_independence_result: IndependenceResult | None = None
    decision_reason_set_digest: str | None = None
    unresolved_condition_set_digest: str | None = None
    trustworthy_time_binding: DecisionTimeBinding | None = None
    single_use_consumption_id: str | None = None
    #: Mutable lifecycle coordinates — **outside** the covered digest (§2.3 non-collapse).
    #: ``consumed`` is negative polarity (only ``is False`` is clear); ``current`` is positive.
    consumed: bool | None = None
    consumption_permitted: bool | None = None
    current: bool | None = None
    failure_response: str | None = None
    #: Negative polarity — only ``is False`` is clear (§15 line 338; SCI-INV-006).
    decision_patch_permitted: bool | None = None
    decision_union_permitted: bool | None = None
    scope_widening_permitted: bool | None = None
    automatic_readmission_permitted: bool | None = None
    #: §7 — a decision "cannot deploy, activate, arm, mutate capacity, or transmit" (line 229).
    authority: AllFalseSupplyChainAuthority = AllFalseSupplyChainAuthority()

    @model_validator(mode="after")
    def _admit_requires_complete_binding(self) -> ArtifactAdmissionDecision:
        """An ``ADMIT`` with any incomplete §15 mandated binding is unconstructable (§2.3)."""
        if self.result is not AdmissionResult.ADMIT:
            return self
        missing: list[str] = []
        for path in self.MANDATED_ADMIT_BINDINGS:
            value: object = self
            for part in path.split("."):
                value = getattr(value, part, None)
                if value is None:
                    break
            if _binding_absent(value):
                missing.append(path)
        if missing:
            raise ArtifactIntegrityError(
                "ArtifactAdmissionDecision cannot carry result ADMIT while these §15 mandated "
                f"bindings are absent, 'TBD', or a mutable name: {missing} — admission binds one "
                "exact policy, artifact, lineage, compatibility graph, scope, and predecessor "
                "generation (ADR-002-029 §15 line 325-333 / SCI-INV-006 line 175; design #29 §2.3)"
            )
        return self


class AdmittedReleaseSet(IndependentIdArtifact):
    """The complete Admitted Release Set (§5.9/§16; SCI-INV-009; design #29 §2.4).

    §5.9 line 135: "The complete canonical set digest of exact Release Artifact Manifests eligible
    for deployment in one scope and Release Generation. It is a **non-authorizing negative gate**
    and cannot be patched, unioned, widened, or resolved through mutable names." §16 line 346: "The
    Admitted Release Set is complete. Missing artifact, extra artifact, mixed platform, undeclared
    sidecar, local patch, runtime plugin, consumer override, or union of narrower sets invalidates
    the set for the affected scope."

    The membership itself is a **canonical set digest** (``release_artifact_manifest_set_digest``,
    template line 24), not an enumerable tuple, so
    :func:`~tos.sci.predicates.admitted_set_no_permissive_union` takes the applicable and member
    digest sets as **injected** ``frozenset`` arguments — the model cannot perform the subset
    comparison on a digest alone (design #29 §5.5 / M1).

    ``restriction_state`` (template line 42) is an **injected cur (ADR-002-024) coordinate**: SCI
    decides only "``UNKNOWN`` or absent ⇒ deny" and invents no clear-value members — the clear set
    is a Phase-0 template INSTANCE decision (design #29 §5.0). ``release_restriction_floor`` (line
    33) is an ordering scalar whose **advance mechanism is cur's** ``fence_advances_floor``, never
    re-authored here (§3.5 M4).

    ``incident_scope_binding_digest`` (line 35) is an **injected opaque coordinate**: incident
    handoff is ADR-002-027, consumed as an injected opaque generation; that sibling
    (``tos.sir``) was **not committed at implementation start** and landed mid-implementation
    (``5aa4ade8``); either way no ``tos.sir`` type is imported
    or referenced (design #29 §0.4f).

    **Coexistence seal (§2.3).** ``complete is True`` while ``release_artifact_manifest_set_digest``
    is absent is **unconstructable** — a "complete" set with no membership digest cannot exist.
    """

    _ID_FIELD: ClassVar[str] = "release_set_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "release_set_id",
        "release_generation",
        "policy_binding.software_release_policy_id",
        "release_artifact_manifest_set_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "release_generation",
            "predecessor_release_generation",
            "predecessor_release_set_digest",
            "result",
            "policy_binding",
            "scope",
            "release_artifact_manifest_set_digest",
            "artifact_admission_decision_set_digest",
            "artifact_lineage_graph_digest",
            "consumer_compatibility_graph_digest",
            "deployment_plan_digest",
            "required_configuration_bundle_digest",
            "required_runtime_attestation_policy_digest",
            "artifact_signing_trust_bundle_generation",
            "artifact_signing_trust_bundle_digest",
            "release_restriction_floor",
            "release_restriction_set_digest",
            "incident_scope_binding_digest",
            "owner_epoch",
            "commit_record_digest",
            "committed",
            "complete",
            "compatibility_complete",
            "failure_response",
            "partial_set_permitted",
            "set_patch_permitted",
            "set_union_permitted",
            "favorable_subset_permitted",
            "historical_generation_reuse_permitted",
            "authority",
        }
    )

    release_set_id: str | None = None
    #: The committed Release Generation ordering scalar (§5.8 line 131 — never reused).
    release_generation: int | None = None
    predecessor_release_generation: int | None = None
    predecessor_release_set_digest: str | None = None
    #: The only ``AdmissionResult``-typed field besides ``ArtifactAdmissionDecision.result``.
    result: AdmissionResult | None = None
    policy_binding: PolicyBinding | None = None
    scope: SupplyChainScope | None = None
    #: The canonical **set digest** of member manifests — not an enumerable tuple (§5.5 / M1).
    release_artifact_manifest_set_digest: str | None = None
    artifact_admission_decision_set_digest: str | None = None
    artifact_lineage_graph_digest: str | None = None
    consumer_compatibility_graph_digest: str | None = None
    deployment_plan_digest: str | None = None
    required_configuration_bundle_digest: str | None = None
    required_runtime_attestation_policy_digest: str | None = None
    artifact_signing_trust_bundle_generation: int | None = None
    artifact_signing_trust_bundle_digest: str | None = None
    #: Ordering scalar; the **advance mechanism is cur's** ``fence_advances_floor`` (§3.5 M4).
    release_restriction_floor: int | None = None
    release_restriction_set_digest: str | None = None
    #: Injected opaque ADR-002-027 coordinate — sibling not committed at implementation start;
    #: landed mid-implementation (``5aa4ade8``), still consumed as an opaque scalar (edge 0).
    incident_scope_binding_digest: str | None = None
    owner_epoch: int | None = None
    commit_record_digest: str | None = None
    #: Positive polarity — only ``is True`` is clear (§16 line 344 "The committed record binds").
    committed: bool | None = None
    complete: bool | None = None
    compatibility_complete: bool | None = None
    #: Mutable lifecycle / injected coordinates — **outside** the covered digest (§2.3).
    current: bool | None = None
    #: Injected cur (ADR-002-024) token; ``UNKNOWN`` / absent ⇒ deny, clear set is Phase-0 (§5.0).
    restriction_state: str | None = None
    failure_response: str | None = None
    #: Negative polarity — only ``is False`` is clear (§16 line 346; SCI-INV-009 line 187).
    partial_set_permitted: bool | None = None
    set_patch_permitted: bool | None = None
    set_union_permitted: bool | None = None
    favorable_subset_permitted: bool | None = None
    historical_generation_reuse_permitted: bool | None = None
    #: §7 — "release-set commit creates no configuration activation or live authority" (line 230).
    authority: AllFalseSupplyChainAuthority = AllFalseSupplyChainAuthority()

    @model_validator(mode="after")
    def _complete_requires_member_set_digest(self) -> AdmittedReleaseSet:
        """A ``complete is True`` set without a member-set digest is unconstructable (§2.3)."""
        if self.complete is not True:
            return self
        if _binding_absent(self.release_artifact_manifest_set_digest):
            raise ArtifactIntegrityError(
                "AdmittedReleaseSet cannot claim complete=True while "
                "release_artifact_manifest_set_digest is absent, 'TBD', or a mutable name — the "
                "set is complete only as an exact canonical membership digest (ADR-002-029 §5.9 "
                "line 135 / §16 line 346; design #29 §2.3)"
            )
        return self


class RuntimeArtifactAttestation(IndependentIdArtifact):
    """The current Runtime Artifact Attestation (§5.10/§18; SCI-INV-010; design #29 §2.4).

    §5.10 line 139: "An authenticated current statement binding the actual loaded and executable
    artifact-set digest, runtime dependency digest, workload and deployment identities, environment,
    Safety Cell, configuration digest, attestor identity, owner epoch, receipt anchor, and Release
    Generation." §18 line 368: "Orchestrator desired state, deployment manifest, image tag, process
    command line, filesystem name, health endpoint, inventory cache, or a statement produced solely
    by the workload being evaluated is insufficient."

    ``result`` (template line 8) is an **opaque** ``str | None``, never an
    :class:`~tos.sci.vocabulary.AdmissionResult` — §7 line 232 "attestation is a fact, not
    permission" (design #29 §2.2 MINOR-2). Its ``scope`` block carries **eight** dimensions (no
    ``legal_portfolio``, template lines 17-25), a documented variation of
    :class:`~tos.sci.state.SupplyChainScope` (design #29 §4.10 / M9).

    Phase 1 authors the **shape** only: the §18 runtime-measurement predicates are not-Phase-1
    (+L2 / +Security, SCI-EV-008). The two coordinates L1 does consume are ``runtime_artifact_match``
    (line 38) and ``current`` (line 52), both read by
    :func:`~tos.sci.predicates.software_deployment_ok_verdict` (design #29 §5.6e).
    """

    _ID_FIELD: ClassVar[str] = "attestation_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "attestation_id",
        "runtime_continuity_generation",
        "observed_runtime_artifact_set_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "attestation_version",
            "runtime_continuity_generation",
            "result",
            "release_binding",
            "scope",
            "workload_identity",
            "workload_owner_epoch",
            "deployment_identity",
            "deployment_generation",
            "runtime_platform_identity",
            "actual_executable_and_image_digest",
            "actual_library_dependency_set_digest",
            "actual_plugin_and_runtime_module_set_digest",
            "actual_sidecar_proxy_sdk_and_signer_component_set_digest",
            "actual_configuration_bundle_digest",
            "expected_runtime_artifact_set_digest",
            "observed_runtime_artifact_set_digest",
            "runtime_artifact_match",
            "consumer_compatibility_result",
            "attestor_identity",
            "attestor_owner_epoch",
            "attestor_independence_result",
            "attestation_evidence_digest",
            "release_restriction_floor",
            "current_release_restriction_set_digest",
            "trustworthy_time_binding",
            "failure_response",
            "self_report_only_is_sufficient",
            "desired_state_is_actual_state",
            "attestation_patch_permitted",
            "attestation_union_permitted",
            "authority",
        }
    )

    attestation_id: str | None = None
    attestation_version: str | None = None
    runtime_continuity_generation: int | None = None
    #: Opaque injected token — **never** an admission result (§7 line 232).
    result: str | None = None
    release_binding: ReleaseBinding | None = None
    #: Eight-dimension variation — ``legal_portfolio`` is absent in this template (§4.10 M9).
    scope: SupplyChainScope | None = None
    workload_identity: str | None = None
    workload_owner_epoch: int | None = None
    deployment_identity: str | None = None
    deployment_generation: int | None = None
    runtime_platform_identity: str | None = None
    actual_executable_and_image_digest: str | None = None
    actual_library_dependency_set_digest: str | None = None
    actual_plugin_and_runtime_module_set_digest: str | None = None
    actual_sidecar_proxy_sdk_and_signer_component_set_digest: str | None = None
    actual_configuration_bundle_digest: str | None = None
    expected_runtime_artifact_set_digest: str | None = None
    observed_runtime_artifact_set_digest: str | None = None
    #: Positive polarity — only ``is True`` is a match (SCI-INV-010 line 191).
    runtime_artifact_match: bool | None = None
    #: Opaque injected token — unknown compatibility is incompatibility (SCI-INV-011).
    consumer_compatibility_result: str | None = None
    attestor_identity: str | None = None
    attestor_owner_epoch: int | None = None
    #: Injected hag (ADR-002-015) verdict — the attestor's independence (§18 line 368).
    attestor_independence_result: IndependenceResult | None = None
    attestation_evidence_digest: str | None = None
    release_restriction_floor: int | None = None
    current_release_restriction_set_digest: str | None = None
    trustworthy_time_binding: AttestationTimeBinding | None = None
    #: Mutable lifecycle coordinates — **outside** the covered digest (§2.3 non-collapse).
    #: ``current`` is positive polarity; ``invalidated`` is negative (only ``is False`` is clear).
    current: bool | None = None
    invalidated: bool | None = None
    failure_response: str | None = None
    #: Negative polarity — only ``is False`` is clear (§18 line 368-370).
    self_report_only_is_sufficient: bool | None = None
    desired_state_is_actual_state: bool | None = None
    attestation_patch_permitted: bool | None = None
    attestation_union_permitted: bool | None = None
    #: §7 line 232 — "attestation is a fact, not permission".
    authority: AllFalseSupplyChainAuthority = AllFalseSupplyChainAuthority()


class ReleaseRestriction(IndependentIdArtifact):
    """The monotonic scope-complete Release Restriction fact (§5.11/§16/§20; design #29 §2.4).

    §5.11 line 143: "A monotonic scope-complete fact that one source, build, dependency, signer,
    registry, admission, artifact, deployment, runtime, or Release Generation **cannot support
    future new-risk permission**." This is the one SCI artifact with **no canonical template** — it
    is ADR-derived (design #29 §2.1 M3, which keeps the ADR §30-1 "eight canonical schemas" count
    intact by excluding it).

    §20 line 404: "A credible authenticated restriction first reduces future authority through
    ADR-002-024. It does not wait for normal release admission, deployment, alert, evidence, or
    incident services. **Scope expands to the greatest credible dependency closure when exact impact
    is unknown.**" §20 line 406: incident declaration, stabilization, remediation, administrative
    closure, postmortem, signer recovery, registry recovery, or quiet time "does not readmit an
    artifact, **clear a release restriction**, restore production scope, or re-arm" (SCI-INV-016).

    **SCI produces the restriction FACT; cur owns the floor advance.** The monotonic floor-advance
    ordering across artifacts is ``tos.cur``'s ``fence_advances_floor`` (§20 line 404 "through
    ADR-002-024"), re-authored here **not at all** — :func:`~tos.sci.predicates.
    restriction_is_monotonic_non_revival` decides only non-revival and greatest-credible-scope
    coverage (design #29 §3.5 M4 / §5.6c).

    ``trigger_class`` is an injected opaque token drawn from the §20 line 397-402 trigger list; when
    a signal is policy-classified as an incident it enters **ADR-002-027** governance — that sibling
    was not committed at implementation start and landed mid-implementation (``5aa4ade8``); no
    ``tos.sir`` type is imported or referenced either way
    (design #29 §0.4f).
    """

    _ID_FIELD: ClassVar[str] = "restriction_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "restriction_id",
        "restriction_generation",
        "restricted_scope",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "restriction_generation",
            "restricted_scope",
            "trigger_class",
            "predecessor_restriction_digest",
            "authority",
        }
    )

    restriction_id: str | None = None
    #: Monotonic restriction ordering scalar; the cross-artifact advance is cur's (§3.5 M4).
    restriction_generation: int | None = None
    #: §20 line 404 — the greatest credible dependency closure when exact impact is unknown.
    restricted_scope: SupplyChainScope | None = None
    #: Injected opaque §20 line 397-402 trigger token (incident handoff is ADR-002-027).
    trigger_class: str | None = None
    predecessor_restriction_digest: str | None = None
    #: §7 / SCI-INV-001 — a restriction is a restrictive fact, never a permission.
    authority: AllFalseSupplyChainAuthority = AllFalseSupplyChainAuthority()
