"""Core EV-L1 supply-chain predicates — five yolk + five cross-cutting + three supporting (§5).

Every predicate is **pure, total, and fail-closed**: it reads only its arguments, touches no clock,
no environment, no network, and no sibling package, and returns ``True`` **only** on positive proof.
A ``None`` denies on both polarities; a negative-polarity ``bool | None`` is cleared **only** by an
explicit ``is False`` (never ``is not True``, which reads ``None`` as clear — the #18/#22 MAJOR-2
fail-open lesson, design #29 §0.5-5); a positive-polarity flag is cleared only by ``is True``; and
the two tri-state enums are consumed by **positive identity** (``is AdmissionResult.ADMIT`` /
``is IndependenceResult.INDEPENDENT``), never by a fall-through over a residual space (the AFG C1
lesson, §0.5-4).

**What these predicates do NOT do (design #29 §0.2 — the EGRESS #22 over-realization boundary).**
No signature verification, no reproducibility byte comparison, no scan or test execution, no SBOM
parse, no registry retrieval, no runtime measurement, no effective-principal collapse, no capacity
arithmetic, no configuration activation, no per-send currentness transaction, no incident lifecycle,
no production promotion, no evidence custody, no recovery or re-arm, and **no restriction-floor
advance** (that is cur ``fence_advances_floor``, §20 line 404 "through ADR-002-024"). Those results
enter as **injected verdicts, generations, and digests** produced by the owning sibling, runtime,
human, +Security, or +Broker path (§7 line 221-241). L1 decides only the structural completeness,
positive-``ADMIT``, closure completeness, mutable-name rejection, generation monotonicity,
restriction non-revival, negative-gate discipline, and all-false authority of the protocol.

Regime tag: release-admission predicate/model substrate only; **closes no SCI-EV** — SCI-EV-001
through SCI-EV-012 are all ``NOT_IMPLEMENTED``, the four core rows (001 / 002 / 003 / 006) still
await ``/3`` and ``+Security`` (002 and 003 additionally ``/2``), and **all twelve register rows
carry ``+Security``** so the organisational security-boundary gate is entirely unmet. An
EV-L1-complete claim is forbidden (design #29 §1).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.sci._base``) + ``tos.ordering``
(via ``tos.sci.state``) + ``tos.sci.*`` only; no ``shared.*``, no sibling ``tos.*`` (design #29 §0.3).
"""

from __future__ import annotations

from tos.sci._base import AllFalseSupplyChainAuthority
from tos.sci.records import (
    AdmittedReleaseSet,
    ArtifactAdmissionDecision,
    BuildProvenanceAttestation,
    DependencyToolchainClosureManifest,
    ReleaseArtifactManifest,
    ReleaseRestriction,
    SourceRevisionManifest,
)
from tos.sci.state import (
    AdmissionBindingSet,
    DependencyClosureDigestSet,
    SupplyChainScope,
    generation_strictly_advances,
    restriction_floor_not_behind,
)
from tos.sci.vocabulary import (
    UNKNOWN_RESTRICTION_STATE,
    AdmissionResult,
    IndependenceResult,
    _is_template_placeholder,
    is_mutable_name_notation,
)

__all__ = [
    "active_currentness_is_negative_gate",
    "admission_admits_only_positive",
    "admitted_set_no_permissive_union",
    "closure_complete_or_restrictive",
    "independence_unproven_is_common_mode",
    "mutable_name_is_not_identity",
    "provenance_is_not_admission",
    "release_artifact_identity_exact",
    "release_generation_monotonic",
    "restriction_is_monotonic_non_revival",
    "rollback_is_new_generation",
    "software_deployment_ok_verdict",
    "source_identity_exact_and_reviewed",
    "supply_chain_artifact_not_authority",
]

# --------------------------------------------------------------------------------------------
# Supporting predicates (design #29 §0.1-4 / §5.1 / §5.4 — the three named supporting predicates)
# --------------------------------------------------------------------------------------------


def mutable_name_is_not_identity(value: str | None) -> bool:
    """Whether a coordinate is a usable **exact** identity (SCI-INV-002 line 159; §1 line 19).

    ``True`` **only** when the value is present, is not the reserved ``"TBD"`` template placeholder
    (matched **case- and padding-insensitively**, so ``"tbd"`` / ``" TBD "`` / ``"Tbd"`` are all
    rejected — an exact comparison would let a lower-cased placeholder satisfy every mandated
    binding at once), and is not a detectable mutable-name notation
    (:func:`~tos.sci.vocabulary.is_mutable_name_notation`). SCI-INV-002 line 159: "Safety-relevant
    identity uses exact canonical content digests. Tags, branches, package names, registry paths,
    service names, deployment labels, timestamps, ``latest``, and local cache state are not identity
    or currentness proof."

    **Best-effort, non-exhaustive (design #29 §0.5-8).** The detectable set is the catalogued
    sentinels plus the glob / tag / path / registry metacharacters; novel mutable notations,
    manifest-list resolution, mirror divergence, and local cache substitution (§14) are owned by
    +Security and the runtime. A ``True`` here is *necessary*, never *sufficient*, for exactness.

    Args:
        value: The candidate identity coordinate.

    Returns:
        ``True`` iff the coordinate is present, concrete, and not a detectable mutable name.
    """
    if value is None or _is_template_placeholder(value):
        return False
    return not is_mutable_name_notation(value)


def independence_unproven_is_common_mode(result: IndependenceResult | None) -> bool:
    """Whether effective-principal independence is **positively proven** (SCI-INV-007 line 179).

    ``True`` **only** for ``result is IndependenceResult.INDEPENDENT``. ``COMMON_MODE``,
    ``UNKNOWN``, and ``None`` are all restrictive — unproven independence *is* common mode. §9 line
    267: "Repository administration, branch protection, signed commits, review count, or merge
    status alone does not prove independence when one person controls the underlying accounts,
    recovery paths, automation, or signing identities."

    The verdict is **hag-owned** (ADR-002-015; design #29 §0.4e): SCI is an instance consumer and
    re-authors no effective-principal collapse, quorum, or account-graph logic. The real "one person,
    several accounts" resistance is hag plus +Security; this predicate only refuses to credit
    anything short of a positive ``INDEPENDENT``.

    Args:
        result: The injected independence verdict.

    Returns:
        ``True`` iff independence is positively proven.
    """
    return result is IndependenceResult.INDEPENDENT


def release_artifact_identity_exact(manifest: ReleaseArtifactManifest | None) -> bool:
    """Whether a release artifact's identity is exact and its custody current (§5.6/§14).

    ``True`` **only** when the manifest is present and all four template claims hold:
    ``mutable_tag_is_identity is False`` (negative polarity — SCI-INV-002 line 159, the
    ``mutable_tag_is_identity`` template line 51 consumer), ``lineage_complete is True``
    (SCI-INV-003), ``registry_custody_current is True`` (§14 line 319 "If registry history, digest
    closure, current restriction state, or retrieved bytes cannot be proven, the artifact is
    quarantined"), and ``compatibility_complete is True`` (SCI-INV-011 line 195).

    Consumed as item 11 of :func:`admission_admits_only_positive`: the decision carries only the
    manifest's id and digest, so the manifest itself is injected to complete the identity check
    (design #29 §5.4 MINOR-1).

    Args:
        manifest: The release artifact manifest the decision binds.

    Returns:
        ``True`` iff the artifact identity is exact, lineage closed, custody current, and
        compatibility complete.
    """
    if manifest is None:
        return False
    return (
        manifest.mutable_tag_is_identity is False
        and manifest.lineage_complete is True
        and manifest.registry_custody_current is True
        and manifest.compatibility_complete is True
    )


# --------------------------------------------------------------------------------------------
# Yolk 1 — SCI-EV-001 source identity and review integrity (§9 / §15 step 2)
# --------------------------------------------------------------------------------------------


def source_identity_exact_and_reviewed(manifest: SourceRevisionManifest | None) -> bool:
    """Whether a source revision is exactly identified, independently reviewed, and closed (§9).

    All of the following must hold (fail-closed conjunction; design #29 §5.1):

    1. **∅-seal** — a ``None`` manifest denies.
    2. **Exact digest identity** — ``source_revision_digest``, ``source_tree_digest``, and
       ``source_history_head_digest`` are each present, concrete, and **not** a mutable-name
       notation (:func:`mutable_name_is_not_identity`), so a ``source_revision_digest="latest"``
       is rejected outright. ``repository_identity`` may be a human-readable name and is
       deliberately **not** an identity gate — §1 line 19: "A branch, tag, package name, registry
       path, service label, mutable image tag, ``latest``, local cache, successful build, passing
       scan, or historical signature is not artifact identity."
    3. **Effective-principal independence** — the injected hag verdict is positively
       ``INDEPENDENT`` (:func:`independence_unproven_is_common_mode`); ``COMMON_MODE`` /
       ``UNKNOWN`` / ``None`` deny (SCI-INV-007 line 179).
    4. **History continuity** — ``history_rewrite_detected is False`` (negative polarity: a ``True``
       *or* a ``None`` denies), the ``source_history_continuity_proof_digest`` is present and
       concrete, and ``review_current is True``. §9 line 269: "Force push, history rewrite, deleted
       branch, moved tag, mirror divergence, submodule retarget, regenerated source, or repository
       restore advances source continuity and invalidates affected unconsumed admission decisions."
    5. **Source closure** — ``closure_complete is True`` and all eight §9 line 265 closure digests
       (generated / submodule / large-file / vendored / external / schema-and-migration /
       build-script / code-generator) are present and concrete (SCI-INV-003 line 163 "Unknown or
       omitted input is restrictive").

    **Closes no SCI-EV.** SCI-EV-001 is ``EV-L1/3+Security``: the real "same effective person
    behind several accounts" resistance (SCI-AC-001 line 554) is hag plus an independent
    security-boundary assessment, not this structural predicate.

    Args:
        manifest: The source revision manifest under evaluation.

    Returns:
        ``True`` iff every clause holds.
    """
    if manifest is None:
        return False

    exact_identity = (
        mutable_name_is_not_identity(manifest.source_revision_digest)
        and mutable_name_is_not_identity(manifest.source_tree_digest)
        and mutable_name_is_not_identity(manifest.source_history_head_digest)
    )
    if not exact_identity:
        return False

    if not independence_unproven_is_common_mode(
        manifest.effective_principal_independence_result
    ):
        return False

    continuity = (
        manifest.history_rewrite_detected is False
        and mutable_name_is_not_identity(
            manifest.source_history_continuity_proof_digest
        )
        and manifest.review_current is True
    )
    if not continuity:
        return False

    if manifest.closure_complete is not True:
        return False
    return all(
        mutable_name_is_not_identity(getattr(manifest, name, None))
        for name in SourceRevisionManifest.SOURCE_CLOSURE_DIGESTS
    )


# --------------------------------------------------------------------------------------------
# Yolk 2 — SCI-EV-002 provenance is not admission (§10 / §12 / SCI-INV-004)
# --------------------------------------------------------------------------------------------


def provenance_is_not_admission(
    attestation: BuildProvenanceAttestation | None,
) -> bool:
    """Whether build provenance is complete **and structurally non-authorizing** (§12/SCI-INV-004).

    Provenance validity is a *necessary* input to §15 step 4, never an admission or a correctness
    proof. SCI-INV-004 line 167: "Valid build provenance or a reproducible output does not prove
    semantic safety, absence of malicious source, current admission, compatibility, or live
    permission." All of the following must hold (design #29 §5.2):

    1. **∅-seal** — a ``None`` attestation denies.
    2. **Builder continuity** — ``builder_identity_current is True`` and ``all_inputs_declared is
       True``. §10 line 275: "Inputs not present in the Source Revision Manifest or Dependency and
       Toolchain Closure Manifest are denied"; line 279: "Builder restart, replacement, rollback,
       image change, cache restore, credential rotation, or runner recovery creates a new builder
       continuity identity."
    3. **Reproduction requirement** — ``reproducibility_requirement_satisfied is True`` and
       ``favorable_output_selection_permitted is False`` (negative polarity). §12 line 299: "Output
       disagreement is ``UNKNOWN`` or ``DENY``; **the release process cannot select the favorable
       artifact**." The actual byte comparison sits in ``reproducibility_comparison_digest`` and is
       injected +L2 / +Security work — SCI compares nothing.
    4. **Structural non-authorization** — ``authority.proves_semantic_correctness is False`` **and**
       ``authority.creates_artifact_admission is False``, and ``provenance_complete is True``. The
       second authority flag is what makes this argument non-vacuous (design #29 §2.4 M2): a
       complete provenance that could itself create admission would collapse §15 step 4 into step 8.

    **Closes no SCI-EV.** SCI-EV-002 is ``EV-L1/2/3+Security``: hermetic build isolation, independent
    reproduction, and common-mode analysis (SCI-AC-002 line 558) are +L2 / +Security.

    Args:
        attestation: The build provenance attestation under evaluation.

    Returns:
        ``True`` iff provenance is complete and provably grants nothing.
    """
    if attestation is None:
        return False
    if not (
        attestation.builder_identity_current is True
        and attestation.all_inputs_declared is True
    ):
        return False
    if not (
        attestation.reproducibility_requirement_satisfied is True
        and attestation.favorable_output_selection_permitted is False
    ):
        return False
    authority = attestation.authority
    if authority is None:
        return False
    return (
        authority.proves_semantic_correctness is False
        and authority.creates_artifact_admission is False
        and attestation.provenance_complete is True
    )


# --------------------------------------------------------------------------------------------
# Yolk 3 — SCI-EV-003 dependency and toolchain closure (§11 / SCI-INV-003 / SCI-INV-005)
# --------------------------------------------------------------------------------------------


def closure_complete_or_restrictive(
    manifest: DependencyToolchainClosureManifest | None,
) -> bool:
    """Whether the dependency and toolchain closure is complete, else restrictive (§11).

    All of the following must hold (design #29 §5.3):

    1. **∅-seal** — a ``None`` manifest denies, and an **empty closure** (every one of the seventeen
       set digests absent) denies through clause 2. §1 line 17: "Missing, stale, conflicting,
       ambiguous, incompletely closed, unapproved, or unverifiable supply-chain state grants zero
       eligibility for dependent new risk." The ADR nowhere sanctions an explicitly-empty closure,
       so ∅ is denial and not a vacuous pass (design #29 §0.5-2 / C2).
    2. **Seventeen dimensions plus correction state** — ``resolution_policy_digest`` is present and
       concrete, **all seventeen** §11 closure set digests
       (:class:`~tos.sci.state.DependencyClosureDigestSet`) are present and concrete, and
       ``correction_and_revocation_state_digest`` is present. The resolution policy is the source of
       truth for any axis it excludes (§11 line 287), but that exclusion set lives **inside** the
       policy digest and is opaque at L1 — so L1 conservatively requires every axis (design #29
       §5.3 NEW-7; the fail-closed direction).
    3. **Completeness and verification** — ``transitive_closure_complete is True``,
       ``all_content_digests_verified is True``, ``all_sources_approved is True``, and
       ``all_corrections_and_revocations_current is True`` (§11 line 289 "unresolved correction is
       restrictive").
    4. **No floating or dynamic resolution** — ``floating_version_permitted is False``,
       ``undeclared_network_resolution_permitted is False``, and
       ``runtime_dynamic_resolution_permitted is False``. These are **policy permissions** in
       negative polarity, so a ``None`` denies. §11 line 289: "Missing dependency, floating version,
       mutable package source, ambiguous platform selection, unknown transitive script, unavailable
       status source, or unresolved correction is restrictive."

    **Closes no SCI-EV.** SCI-EV-003 is ``EV-L1/2/3+Security``: transitive resolution proof and
    common-mode package-source analysis (SCI-AC-003 line 562) are +L2 / +Security. The
    mutable-source detection is best-effort and non-exhaustive (design #29 §0.5-8).

    Args:
        manifest: The dependency and toolchain closure manifest under evaluation.

    Returns:
        ``True`` iff the closure is complete, verified, corrected, and non-floating.
    """
    if manifest is None:
        return False
    if not mutable_name_is_not_identity(manifest.resolution_policy_digest):
        return False
    if not all(
        mutable_name_is_not_identity(getattr(manifest, name, None))
        for name in DependencyClosureDigestSet.model_fields
    ):
        return False
    if not mutable_name_is_not_identity(
        manifest.correction_and_revocation_state_digest
    ):
        return False
    if not (
        manifest.transitive_closure_complete is True
        and manifest.all_content_digests_verified is True
        and manifest.all_sources_approved is True
        and manifest.all_corrections_and_revocations_current is True
    ):
        return False
    return (
        manifest.floating_version_permitted is False
        and manifest.undeclared_network_resolution_permitted is False
        and manifest.runtime_dynamic_resolution_permitted is False
    )


# --------------------------------------------------------------------------------------------
# Yolk 4 — SCI-EV-006 admission admits only positive (§15 / SCI-INV-006)
# --------------------------------------------------------------------------------------------


def admission_admits_only_positive(
    decision: ArtifactAdmissionDecision | None,
    active_restriction_floor: int | None,
    restriction_floor_resolved: bool | None,
    target_scope: SupplyChainScope | None,
    scope_resolved: bool | None,
    release_artifact_manifest: ReleaseArtifactManifest | None,
    manifest_resolved: bool | None,
    *,
    require_manifest_digest_match: bool = False,
) -> bool:
    """Whether an admission decision is a genuine, exactly-bound, positive ``ADMIT`` (§15).

    Eleven clauses, all required (design #29 §5.4):

    1. **∅-seal and resolution gates** — a ``None`` decision denies; a lookup that did not resolve
       (``restriction_floor_resolved`` / ``scope_resolved`` / ``manifest_resolved`` not ``True``)
       denies conservatively.
    2. **``ADMIT`` positive identity** — ``decision.result is AdmissionResult.ADMIT``. ``ADMIT`` is
       never reached as a residual space by excluding ``DENY`` (the AFG C1 lesson, §0.5-4).
    3. **Exact binding completeness** — the two structured bindings (``policy_binding``
       ``software_release_policy_id`` / ``release_artifact_binding`` id and digest) and all nine
       scalar digest bindings (:class:`~tos.sci.state.AdmissionBindingSet` — source revision,
       closure, provenance, **signature and key status, registry custody, compatibility graph, scan
       / test / finding evidence**, common-mode analysis, target scope) are present, concrete, and
       not mutable names. §15 steps 1-6. The **verification results are sealed inside those
       digests** by +Security: SCI verifies no signature, retrieves no artifact, and runs no scan
       (design #29 §0.2 / C1).
    4. **Restriction floor** — ``current_release_restriction_floor`` is present and
       :func:`~tos.sci.state.restriction_floor_not_behind` proves it is at or ahead of the active
       floor. ``Ordering.AFTER`` (behind) and ``Ordering.AMBIGUOUS`` both deny. §15 step 7: "verify
       predecessor Release Generation and **every current restriction floor**."
    5. **Independence** — ``effective_principal_independence_result`` is positively ``INDEPENDENT``
       (§15 step 2; SCI-INV-007).
    6. **Scope completeness** — the decision's ``target_scope_digest`` is present and concrete and
       the injected :class:`~tos.sci.state.SupplyChainScope` has ``scope_complete is True``
       (SCI-INV-006 line 175 "Missing, wildcarded, patched, unioned, mixed, or conflicting scope is
       ``UNKNOWN`` or ``DENY``").
    7. **No patch / union / widen / readmit** — ``decision_patch_permitted``,
       ``decision_union_permitted``, ``scope_widening_permitted``, and
       ``automatic_readmission_permitted`` are each ``is False``. §15 line 338: "Decisions cannot be
       patched, unioned, replayed, widened, or silently re-evaluated with newer favorable inputs."
    8. **Predecessor generation** — ``predecessor_release_generation`` and
       ``predecessor_admitted_release_set_digest`` are present and
       :func:`~tos.sci.state.generation_strictly_advances` proves the candidate generation strictly
       follows the predecessor. An **equal** generation is a reuse and denies (§5.8 line 131).
    9. **Single use** — ``consumed is False`` (negative polarity: a consumed or unknown decision
       cannot admit again; §15 step 10).
    10. **Decision currentness** — ``current is True`` (a non-current decision is not an admission
        basis).
    11. **Release-artifact identity, coupled to the binding** — the injected manifest must be
        **the one the decision points at**, not merely *a* well-formed manifest:
        ``release_artifact_manifest.manifest_id`` must equal
        ``release_artifact_binding.release_artifact_manifest_id``, and when the manifest carries a
        concrete ``canonical_digest`` (i.e. it is issued rather than pre-issuance) that digest must
        equal ``release_artifact_binding.release_artifact_manifest_digest``. Only then does
        :func:`release_artifact_identity_exact` decide. Without the coupling, a *different* clean
        manifest would satisfy item 11 for any decision — a cross-decision substitution that §5.7
        line 127 forbids ("for **one exact** Release Artifact Manifest") and that §14 line 315-317
        names directly ("Registry tags and paths may be discovery metadata only; every consumer
        verifies the complete manifest ... after retrieval and before use").

    **Coupling limits, stated rather than implied.** ``target_scope`` (item 6) is **not** coupled to
    ``target_scope_digest``: :class:`~tos.sci.state.SupplyChainScope` is a value model with no
    digest field, so the scope object and the decision's scope digest cannot be tied together at
    L1 — the binding is a Phase-0 / +Security responsibility and is deferred explicitly here rather
    than faked. The manifest digest comparison is likewise skipped for a pre-issuance (``DRAFT``)
    manifest whose ``canonical_digest`` is ``None``; pass ``require_manifest_digest_match=True`` to
    demand a concrete, non-placeholder digest as well (a backward-compatible opt-in strengthening,
    the PTF #24 kwargs precedent).

    **Compatibility boundary (design #29 §5.4 NEW-4d).** This predicate checks only that
    ``compatibility_graph_digest`` is *bound*; the compatibility **verdict** is
    :func:`admitted_set_no_permissive_union`'s (§17 line 358 "Unknown compatibility denies the
    affected scope"; SCI-INV-011) — the two never double-judge.

    **Closes no SCI-EV.** SCI-EV-006 is ``EV-L1/3+Security``: common-mode review and self-approval
    resistance (SCI-AC-006 line 574) are +Security.

    Args:
        decision: The admission decision under evaluation.
        active_restriction_floor: The injected currently active restriction floor ordering scalar.
        restriction_floor_resolved: Whether the active-floor lookup resolved (positive polarity).
        target_scope: The injected exact target scope the decision binds.
        scope_resolved: Whether the target-scope lookup resolved (positive polarity).
        release_artifact_manifest: The injected manifest the decision's binding points at.
        manifest_resolved: Whether the manifest lookup resolved (positive polarity).
        require_manifest_digest_match: Opt-in strengthening — additionally demand that the manifest
            carry a concrete, non-placeholder ``canonical_digest`` (default ``False`` so a
            pre-issuance manifest stays admissible; the id coupling is enforced either way).

    Returns:
        ``True`` iff every clause holds.
    """
    if decision is None:
        return False
    if restriction_floor_resolved is not True:
        return False
    if scope_resolved is not True:
        return False
    if manifest_resolved is not True:
        return False

    if decision.result is not AdmissionResult.ADMIT:
        return False

    policy_binding = decision.policy_binding
    artifact_binding = decision.release_artifact_binding
    if policy_binding is None or artifact_binding is None:
        return False
    if not mutable_name_is_not_identity(policy_binding.software_release_policy_id):
        return False
    if not (
        mutable_name_is_not_identity(artifact_binding.release_artifact_manifest_id)
        and mutable_name_is_not_identity(
            artifact_binding.release_artifact_manifest_digest
        )
    ):
        return False
    if not all(
        mutable_name_is_not_identity(getattr(decision, name, None))
        for name in AdmissionBindingSet.model_fields
    ):
        return False

    if decision.current_release_restriction_floor is None:
        return False
    if not restriction_floor_not_behind(
        decision.current_release_restriction_floor, active_restriction_floor
    ):
        return False

    if not independence_unproven_is_common_mode(
        decision.effective_principal_independence_result
    ):
        return False

    if target_scope is None or target_scope.scope_complete is not True:
        return False

    if not (
        decision.decision_patch_permitted is False
        and decision.decision_union_permitted is False
        and decision.scope_widening_permitted is False
        and decision.automatic_readmission_permitted is False
    ):
        return False

    if not mutable_name_is_not_identity(
        decision.predecessor_admitted_release_set_digest
    ):
        return False
    if not generation_strictly_advances(
        decision.predecessor_release_generation, decision.candidate_release_generation
    ):
        return False

    if decision.consumed is not False:
        return False
    if decision.current is not True:
        return False

    if release_artifact_manifest is None:
        return False
    if (
        release_artifact_manifest.manifest_id
        != artifact_binding.release_artifact_manifest_id
    ):
        return False
    manifest_digest = release_artifact_manifest.canonical_digest
    if require_manifest_digest_match and not mutable_name_is_not_identity(
        manifest_digest
    ):
        return False
    if manifest_digest is not None and (
        manifest_digest != artifact_binding.release_artifact_manifest_digest
    ):
        return False
    return release_artifact_identity_exact(release_artifact_manifest)


# --------------------------------------------------------------------------------------------
# Yolk 5 — SCI-EV-006 admitted set: complete, no permissive union (§16 / SCI-INV-009)
# --------------------------------------------------------------------------------------------


def admitted_set_no_permissive_union(
    release_set: AdmittedReleaseSet | None,
    applicable_manifest_digests: frozenset[str] | None,
    member_manifest_digests: frozenset[str],
    applicable_set_resolved: bool | None,
) -> bool:
    """Whether one complete current Admitted Release Set governs the scope (§16/SCI-INV-009).

    Five clauses, all required (design #29 §5.5):

    1. **∅-seal and resolution gate** — a ``None`` set denies; ``applicable_set_resolved`` not
       ``True`` denies; a ``None`` applicable set denies; and an **empty applicable set together
       with an empty membership denies**. The ADR nowhere sanctions an explicitly-empty Admitted
       Release Set (design #29 §0.5-2 / C2 — the negative grep over §5.9 / §11 / §16 found none),
       and §1 line 17 says missing or incompletely closed state "grants zero eligibility", while
       §16 line 346 says "Missing artifact, extra artifact, mixed platform, undeclared sidecar,
       local patch, runtime plugin, consumer override, or union of narrower sets **invalidates the
       set for the affected scope**". Reversing this would require an ADR §16 erratum.
    2. **Completeness both ways** — the applicable digests and the member digests are **equal**: a
       missing artifact (applicable ⊄ member) and an extra artifact (member ⊄ applicable) both deny.
    3. **No permissive union** — ``partial_set_permitted``, ``set_union_permitted``, and
       ``favorable_subset_permitted`` are each ``is False``. SCI-INV-009 line 187: "Partial
       deployment and favorable subsets cannot form a permissive union."
    4. **Committed, complete, current, compatible, restriction-resolved** — ``complete is True``,
       ``committed is True``, ``current is True``, ``compatibility_complete is True`` (a bound
       compatibility digest is **not** enough — SCI-INV-011 line 195 / §17 line 358 "Unknown
       compatibility denies the affected scope"), and ``restriction_state`` is **positively
       resolved**: absent or ``UNKNOWN`` (case-insensitively) denies. The clear-value set is a
       Phase-0 template INSTANCE decision, so no member is invented here (design #29 §5.0).
    5. **Generation coherence** — ``historical_generation_reuse_permitted is False`` and
       :func:`~tos.sci.state.generation_strictly_advances` proves the committed
       ``release_generation`` strictly follows ``predecessor_release_generation``. §5.8 line 131: a
       generation "cannot be reused after rejection, revocation, rollback, restore, compromise, or
       supersession."

    **Closes no SCI-EV.**

    Args:
        release_set: The admitted release set under evaluation.
        applicable_manifest_digests: The injected set of manifest digests applicable to the scope.
        member_manifest_digests: The injected set of manifest digests the set actually contains
            (the model carries only their canonical set digest, so membership is injected).
        applicable_set_resolved: Whether the applicable-set lookup resolved (positive polarity).

    Returns:
        ``True`` iff exactly one complete, current, committed, compatible, non-union set governs.
    """
    if release_set is None:
        return False
    if applicable_set_resolved is not True:
        return False
    if applicable_manifest_digests is None:
        return False
    if not applicable_manifest_digests and not member_manifest_digests:
        return False
    if applicable_manifest_digests != member_manifest_digests:
        return False

    if not (
        release_set.partial_set_permitted is False
        and release_set.set_union_permitted is False
        and release_set.favorable_subset_permitted is False
    ):
        return False

    if not (
        release_set.complete is True
        and release_set.committed is True
        and release_set.current is True
        and release_set.compatibility_complete is True
    ):
        return False
    if not _restriction_state_positively_resolved(release_set.restriction_state):
        return False

    if release_set.historical_generation_reuse_permitted is not False:
        return False
    return generation_strictly_advances(
        release_set.predecessor_release_generation, release_set.release_generation
    )


def _restriction_state_positively_resolved(state: str | None) -> bool:
    """Whether an injected cur restriction-state token is positively resolved (§16; §5.0).

    ``False`` for ``None``, for a blank token, and for the ``UNKNOWN`` placeholder matched
    **case-insensitively** after a ``strip().casefold()`` normalization (the RLP #25 denylist
    normalization lesson — a ``"Unknown"`` variant must not slip through). The **clear**-value set
    is a Phase-0 template INSTANCE decision, so no clear member is invented here: SCI decides only
    "``UNKNOWN`` or absent ⇒ deny" (design #29 §5.0).
    """
    if state is None:
        return False
    normalized = state.strip().casefold()
    if not normalized:
        return False
    return normalized != UNKNOWN_RESTRICTION_STATE.strip().casefold()


# --------------------------------------------------------------------------------------------
# Cross-cutting structural predicates (design #29 §5.6)
# --------------------------------------------------------------------------------------------


def supply_chain_artifact_not_authority(
    authority: AllFalseSupplyChainAuthority | None,
) -> bool:
    """Whether a supply-chain artifact's authority block grants nothing (SCI-INV-001 line 155).

    ``True`` **only** when the block is present and **every** one of its twenty declared flags is
    ``False``. A ``None`` block denies (an absent authority claim is not a proof of harmlessness).
    Construction already rejects any ``True`` flag
    (:class:`~tos.sci._base.AllFalseSupplyChainAuthority`); this predicate is the second layer that
    re-derives the property from the values, so a ``model_construct`` bypass is still caught
    (design #29 §2.3).

    SCI-INV-001 line 155: "No policy, manifest, provenance attestation, signature, admission
    decision, release set, deployment record, runtime attestation, scan, test, or evidence artifact
    creates capacity, approval, protection, live authority, broker permission, incident closure,
    readiness, scope restoration, or re-arm."

    Args:
        authority: The artifact's authority block.

    Returns:
        ``True`` iff the block is present and entirely false.
    """
    if authority is None:
        return False
    return all(
        getattr(authority, name, None) is False
        for name in AllFalseSupplyChainAuthority.model_fields
    )


def release_generation_monotonic(
    predecessor: int | None, successor: int | None
) -> bool:
    """Whether a Release Generation strictly advances, never regressing or reusing (§5.8/SCI-INV-012).

    §5.8 line 131: a Release Generation "cannot be reused after rejection, revocation, rollback,
    restore, compromise, or supersession." ``True`` **only** when
    :func:`~tos.sci.state.generation_strictly_advances` proves ``successor`` strictly follows
    ``predecessor``; an equal (reuse), regressing, ambiguous, or absent pair denies. The ordering
    itself is ``tos.ordering``'s (REUSE, PROMOTE 0) and is reached only through the §5.0 helper —
    never by calling ``compare_order`` directly with a raw scalar, which would leave
    ``Ordering.AMBIGUOUS`` unmapped (design #29 §5.0 NEW-1).

    Args:
        predecessor: The predecessor Release Generation ordering scalar.
        successor: The successor Release Generation ordering scalar.

    Returns:
        ``True`` iff the generation strictly advances.
    """
    return generation_strictly_advances(predecessor, successor)


def rollback_is_new_generation(
    predecessor_generation: int | None,
    rollback_generation: int | None,
    historical_generation_reuse_permitted: bool | None,
) -> bool:
    """Whether a rollback / restore / hotfix takes a **new** generation (§22/SCI-INV-012).

    §22 line 433: "Rollback is a new release proposal, admission decision, Admitted Release Set, and
    Release Generation. Historical acceptance does not prove present compatibility, key status,
    dependency status, current Hard Safety Envelope compliance, or runtime suitability."
    SCI-INV-012 line 199: "Rollback, restore, rebuild, re-sign, hotfix, registry recovery, or
    **identical bytes** require a new Release Generation and fresh governed admission. No
    predecessor admission or authority revives."

    ``True`` **only** when the rollback generation strictly advances the predecessor **and**
    ``historical_generation_reuse_permitted is False`` (negative polarity: a ``True`` or a ``None``
    denies). Reusing the historical generation — the exact revival §5.8 forbids — can therefore
    never pass.

    Args:
        predecessor_generation: The superseded Release Generation ordering scalar.
        rollback_generation: The rollback / restore / hotfix Release Generation ordering scalar.
        historical_generation_reuse_permitted: The set's negative-polarity reuse permission.

    Returns:
        ``True`` iff the rollback takes a strictly new, non-reused generation.
    """
    if historical_generation_reuse_permitted is not False:
        return False
    return generation_strictly_advances(predecessor_generation, rollback_generation)


def restriction_is_monotonic_non_revival(
    restriction: ReleaseRestriction | None,
    credible_scope_dimensions: frozenset[str] | None,
    scope_resolved: bool | None,
    revival_claimed: bool | None,
) -> bool:
    """Whether a Release Restriction is scope-complete and cannot be revived (§20/SCI-INV-016).

    Four clauses, all required (design #29 §5.6c):

    1. **∅-seal and resolution gate** — a ``None`` restriction denies; ``scope_resolved`` not
       ``True`` denies; a ``None`` or **empty** credible-closure set denies (∅ both ways, §0.5-2).
       The emptiness test runs on the closure with ``scope_complete`` **subtracted**, so a
       **near-∅** closure such as ``frozenset({"scope_complete"})`` — which names a completeness
       flag but no scope axis — denies exactly as ∅ does instead of passing vacuously.
    2. **Scope completeness** — the restriction's ``restricted_scope`` is present with
       ``scope_complete is True``.
    3. **Greatest credible closure coverage** — **every** dimension named in
       ``credible_scope_dimensions`` is explicitly and concretely bound on the restricted scope.
       §20 line 404: "Scope expands to the **greatest credible dependency closure** when exact
       impact is unknown." An omitted dimension is an unknown axis, and unknown scope is denial
       (SCI-INV-006 line 175) — so any-broaden-wins, and a silently narrower restriction cannot
       pass. The *value-level* union arithmetic (which concrete value is broader) is **not**
       L1-decidable and stays with cur / +Security.
    4. **Non-revival** — ``revival_claimed is False`` (negative polarity: a claim to readmit or
       clear, and an unknown, both deny). §20 line 406: incident declaration, stabilization,
       remediation, administrative closure, postmortem, signer recovery, registry recovery, or quiet
       time "does not readmit an artifact, **clear a release restriction**, restore production scope,
       or re-arm."

    **This is not the floor-advance mechanism.** The cross-artifact monotonic restriction-floor
    advance is ``tos.cur``'s ``fence_advances_floor`` (§20 line 404 "reduces future authority
    **through ADR-002-024**"); SCI produces the restriction *fact* and re-authors that mechanism not
    at all (design #29 §3.5 M4).

    Args:
        restriction: The release restriction under evaluation.
        credible_scope_dimensions: The injected greatest-credible-closure dimension names.
        scope_resolved: Whether the credible-closure lookup resolved (positive polarity).
        revival_claimed: Whether anything claims to clear or readmit (negative polarity).

    Returns:
        ``True`` iff the restriction is scope-complete, covers the credible closure, and is
        un-revivable.
    """
    if restriction is None:
        return False
    if scope_resolved is not True:
        return False
    if credible_scope_dimensions is None:
        return False
    # ``scope_complete`` is a completeness *flag*, not a scope axis: a closure consisting only of
    # it names no coordinate at all, so it is a **near-∅** closure and denies exactly as ∅ does.
    # Subtracting it before the emptiness test is what stops ``frozenset({"scope_complete"})``
    # from walking the loop, hitting the ``continue``, and passing vacuously (design #29 §0.5-2).
    substantive_dimensions = frozenset(credible_scope_dimensions) - {"scope_complete"}
    if not substantive_dimensions:
        return False
    scope = restriction.restricted_scope
    if scope is None or scope.scope_complete is not True:
        return False
    for dimension in substantive_dimensions:
        if dimension not in SupplyChainScope.SCOPE_DIMENSIONS:
            return False
        if not mutable_name_is_not_identity(getattr(scope, dimension, None)):
            return False
    return revival_claimed is False


def active_currentness_is_negative_gate(
    currentness_current: bool | None,
    supplies_capacity: bool | None,
    supplies_authority: bool | None,
    supplies_protection: bool | None,
    supplies_approval: bool | None,
    supplies_admissibility: bool | None,
    supplies_permission: bool | None,
) -> bool:
    """Whether a currentness pass is consumed as a **negative gate only** (SCI-INV-013; §1 line 27).

    §1 line 27 verbatim: "A successful check is only a negative gate. **It cannot supply capacity,
    authority, protection, approval, admissibility, or permission that another owner has not
    independently granted.**" SCI-INV-013 line 203: "Cache, TTL, heartbeat, health, deployment
    status, and absence of revocation are not currentness proof."

    ``True`` **only** when the currentness verdict is positively current *and* every one of the six
    §1 line 27 supply claims is explicitly ``False`` (negative polarity: a ``True`` means the gate is
    being read as a grant, and a ``None`` is an unknown — both deny). A non-current verdict denies
    outright.

    The per-send ordered currentness **transaction** is cur's (ADR-002-024 §19) and final egress is
    ADR-002-013's; this predicate is the structural discipline SCI owns, and the two propositions
    are not the same (design #29 §3.5 / §5.6d). Note the citation: the negative-gate sentence is
    §1 line 27; §19 line 389 ("Final egress verifies exact facts and conformance ...") is a separate
    sentence about egress.

    Args:
        currentness_current: The injected cur currentness verdict (positive polarity).
        supplies_capacity: Whether the pass is claimed to supply capacity (negative polarity).
        supplies_authority: Whether it is claimed to supply authority (negative polarity).
        supplies_protection: Whether it is claimed to supply protection (negative polarity).
        supplies_approval: Whether it is claimed to supply approval (negative polarity).
        supplies_admissibility: Whether it is claimed to supply admissibility (negative polarity).
        supplies_permission: Whether it is claimed to supply permission (negative polarity).

    Returns:
        ``True`` iff currentness is current and supplies none of the six.
    """
    if currentness_current is not True:
        return False
    return (
        supplies_capacity is False
        and supplies_authority is False
        and supplies_protection is False
        and supplies_approval is False
        and supplies_admissibility is False
        and supplies_permission is False
    )


def software_deployment_ok_verdict(
    admission_result: AdmissionResult | None,
    runtime_attestation_matches: bool | None,
    active_currentness_current: bool | None,
    restriction_present: bool | None,
    restriction_state_resolved: bool | None,
) -> bool:
    """Produce the ``software_deployment_ok`` verdict spg consumes (§18/§1; design #29 §5.6e).

    This is SCI's one **produced-value seam**: ``tos.spg`` (ADR-002-014) carries the consumption slot
    ``SemanticValidationInputs.software_deployment_ok`` (``tos/src/tos/spg/records.py`` line 206) and
    gates it ``is not True`` (``tos/src/tos/spg/predicates.py`` line 467) as step 8 of its semantic
    validation fold. The seam is a plain ``bool`` — **no import edge in either direction** (sibling
    edge 0, design #29 §3.4).

    ``True`` **only** when all of the following hold:

    * ``restriction_state_resolved is True`` — an unresolved restriction lookup denies
      conservatively (§21 line 427 "No retry, mirror, cache, alternate registry, previous artifact,
      emergency signer, manual copy, or operator assertion may select a more permissive state when
      provenance, ordering, currentness, or scope is unknown");
    * ``admission_result is AdmissionResult.ADMIT`` — positive identity, never a fall-through;
    * ``runtime_attestation_matches is True`` — the ``runtime_artifact_match`` observation
      (RUNTIME-ARTIFACT-ATTESTATION line 38); SCI-INV-010 line 191 "Desired state and process health
      are insufficient";
    * ``active_currentness_current is True`` — the injected cur (ADR-002-024) currentness verdict;
    * ``restriction_present is False`` — negative polarity, so a present *or unknown* restriction
      denies (SCI-INV-014; §16 line 348).

    Even a ``True`` here is only a **negative gate**: §1 line 27 — it supplies no capacity,
    authority, protection, approval, admissibility, or permission.

    Args:
        admission_result: The exact admission decision result for the deployed artifact.
        runtime_attestation_matches: The runtime artifact-set match observation.
        active_currentness_current: The injected cur active-currentness verdict.
        restriction_present: Whether any release restriction applies (negative polarity).
        restriction_state_resolved: Whether the restriction lookup resolved (positive polarity).

    Returns:
        ``True`` iff every clause holds.
    """
    if restriction_state_resolved is not True:
        return False
    if admission_result is not AdmissionResult.ADMIT:
        return False
    return (
        runtime_attestation_matches is True
        and active_currentness_current is True
        and restriction_present is False
    )
