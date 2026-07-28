"""Injected supply-chain value models + the two ordering helpers (design #29 §2.1/§5.0).

The frozen, id-less value models every SCI artifact embeds (``SupplyChainScope``, the binding
blocks, the trustworthy-time blocks) plus the three **field-name anchor views** the §4 verbatim
transcription mandates (``SoftwareReleasePolicyFieldGroups`` — §8's seventeen ``*_policy_digest``
fields plus the two approved-set digests, §4.3; ``DependencyClosureDigestSet`` — §11's seventeen
closure set digests, §4.9; ``AdmissionBindingSet`` — the §15 step 1-7 scalar digest bindings, §4.4).
The three anchors are **consumed by the predicates**, not decorative: the §11 closure completeness
(§5.3 item 2) and the §15 binding completeness (§5.4 item 3) iterate their field names over the
corresponding artifact, so a dropped dimension is a real behavioural regression and not only a
drift-test failure (the WDR MAJOR-1 field-group defect class, design #29 §6.2).

**Two ordering helpers, deliberately not one (design #29 §5.0 NEW-1 / v1.3 UPHOLD).**
``tos.ordering.compare_order`` takes ``OrderingEvent`` values (never a ``str``) and returns
``Ordering.AMBIGUOUS`` for an unmapped pair, so a raw call is a fail-open surface. Both helpers wrap
their ``int`` ordering scalar in ``OrderingEvent(quorum_commit_index=...)`` and treat
``Ordering.AMBIGUOUS`` as **deny**. They realize two **different** propositions and must not be
merged:

* :func:`restriction_floor_not_behind` — *at-or-ahead*: a decision whose restriction floor **equals**
  the active floor has observed the current restriction and is admissible (§15 step 7). The
  ``equal ⇒ True`` short-circuit sits **before** the ``compare_order`` call by construction: an equal
  pair yields ``_cmp`` ``None`` and therefore ``Ordering.AMBIGUOUS``
  (``tos/src/tos/ordering/_ordering.py`` lines 77-83), so moving the short-circuit after the call
  would deny every legitimate equal-floor decision — a false-negative regression the §6.3 (i) canary
  pins.
* :func:`generation_strictly_advances` — *strictly ahead*: §5.8 line 131, a Release Generation
  "cannot be reused after rejection, revocation, rollback, restore, compromise, or supersession", so
  an **equal** generation is a reuse and must deny. Using the floor helper here would let reuse pass
  — the §6.3 (j) canary pins that too.

Both are a **local re-expression** of the cur ``floor_strictly_advances``
(``tos/src/tos/cur/state.py`` line 190) *shape*, **not an import** (sibling edge 0, design #29
§3.4). They are also **not** the cur restriction-floor *advance mechanism*: cur
``fence_advances_floor`` (``tos/src/tos/cur/predicates.py`` line 415) owns the cross-artifact
monotonic floor advance (§20 line 404 "reduces future authority **through ADR-002-024**"); SCI only
asks whether an admission decision is behind the active floor, and whether one generation strictly
follows another (design #29 §3.5 M4 — proposition separation, re-authoring zero).

Every generation / floor coordinate is an ``int | None`` **ordering scalar, never a clock** (design
#29 §3.2 — the ten wall-clock ``MAX_*_ms`` keys are secondary, +Security, and injected, §8).

Regime tag: release-admission predicate/model substrate only; **closes no SCI-EV**; all 12 register
rows carry ``+Security``; an EV-L1-complete claim is forbidden.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.sci._base``) + ``tos.ordering``
only; no ``shared.*``, no sibling ``tos.*`` (design #29 §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.sci._base import FrozenModel

__all__ = [
    "AdmissionBindingSet",
    "AttestationTimeBinding",
    "BuildProvenanceBinding",
    "DecisionTimeBinding",
    "DependencyAndToolchainBinding",
    "DependencyClosureDigestSet",
    "PolicyBinding",
    "ReleaseArtifactBinding",
    "ReleaseBinding",
    "SoftwareReleasePolicyFieldGroups",
    "SourceRevisionManifestBinding",
    "SupplyChainScope",
    "VerificationProfileBinding",
    "generation_strictly_advances",
    "restriction_floor_not_behind",
]


class SupplyChainScope(FrozenModel):
    """The exact target scope of a release fact (ADR §16 line 344; design #29 §4.10).

    The nine ``scope:`` dimensions transcribed verbatim from the SOFTWARE-RELEASE-POLICY (template
    lines 9-18) and ADMITTED-RELEASE-SET (template lines 14-23) blocks. §5.9 line 135: the Admitted
    Release Set "is a non-authorizing negative gate and cannot be patched, unioned, widened, or
    resolved through mutable names", and §6 SCI-INV-006 line 175: "Missing, wildcarded, patched,
    unioned, mixed, or conflicting scope is ``UNKNOWN`` or ``DENY``".

    ``scope_complete`` is **positive polarity**: only an explicit ``True`` is a complete scope; a
    ``False`` or a ``None`` denies (design #29 §5.0).

    **Documented template variation (design #29 §4.10 / M9).** The RUNTIME-ARTIFACT-ATTESTATION
    ``scope:`` block (template lines 17-25) carries **eight** dimensions — it has no
    ``legal_portfolio``. The same model is reused for it with ``legal_portfolio`` left ``None``
    (absent), and :data:`RUNTIME_SCOPE_DIMENSIONS` records the eight-name anchor so the §6.2
    drift property checks the runtime template against eight, not nine.
    """

    #: The nine SOFTWARE-RELEASE-POLICY / ADMITTED-RELEASE-SET scope dimensions (§4.10 anchor).
    SCOPE_DIMENSIONS: ClassVar[tuple[str, ...]] = (
        "environment",
        "safety_cell",
        "capacity_domain",
        "legal_portfolio",
        "account_scope_digest",
        "broker_scope_digest",
        "component_scope_digest",
        "dependency_closure_digest",
        "scope_complete",
    )
    #: The eight RUNTIME-ARTIFACT-ATTESTATION scope dimensions — no ``legal_portfolio`` (§4.10 M9).
    RUNTIME_SCOPE_DIMENSIONS: ClassVar[tuple[str, ...]] = (
        "environment",
        "safety_cell",
        "capacity_domain",
        "account_scope_digest",
        "broker_scope_digest",
        "component_scope_digest",
        "dependency_closure_digest",
        "scope_complete",
    )

    environment: str | None = None
    safety_cell: str | None = None
    capacity_domain: str | None = None
    legal_portfolio: str | None = None
    account_scope_digest: str | None = None
    broker_scope_digest: str | None = None
    component_scope_digest: str | None = None
    dependency_closure_digest: str | None = None
    #: Positive polarity — only ``is True`` is a complete scope (§5.4 item 6).
    scope_complete: bool | None = None


class PolicyBinding(FrozenModel):
    """The ``policy_binding:`` block every dependent artifact carries (template lines 9-12).

    §15 step 1: "bind one exact current Software Release Policy and target scope". The policy's own
    activation is **ADR-002-014 governed** (§8 line 259 "Policy activation follows ADR-002-014 and
    creates neither artifact admission nor live permission") — the generation and digest are injected
    coordinates, re-authored not at all (design #29 §3.5).
    """

    software_release_policy_id: str | None = None
    policy_generation: int | None = None
    policy_digest: str | None = None


class ReleaseArtifactBinding(FrozenModel):
    """The ``release_artifact_binding:`` block of an admission decision (template lines 13-15).

    §5.7 line 127: an Artifact Admission Decision is issued "for one exact Release Artifact
    Manifest". The decision carries the manifest's **id and digest**, not the manifest object — so
    :func:`~tos.sci.predicates.admission_admits_only_positive` takes the manifest as a separate
    injected argument to complete the identity check (design #29 §5.4 item 11 / MINOR-1).
    """

    release_artifact_manifest_id: str | None = None
    release_artifact_manifest_digest: str | None = None


class SourceRevisionManifestBinding(FrozenModel):
    """The ``source_revision_manifest_binding:`` block (template lines 12-14 / 13-15)."""

    source_revision_manifest_id: str | None = None
    source_revision_manifest_digest: str | None = None


class DependencyAndToolchainBinding(FrozenModel):
    """The ``dependency_and_toolchain_binding:`` block (template lines 16-18)."""

    closure_manifest_id: str | None = None
    closure_manifest_digest: str | None = None


class BuildProvenanceBinding(FrozenModel):
    """The ``build_provenance_binding:`` block (RELEASE-ARTIFACT-MANIFEST lines 19-21)."""

    build_provenance_attestation_id: str | None = None
    build_provenance_attestation_digest: str | None = None


class ReleaseBinding(FrozenModel):
    """The ``release_binding:`` block of a runtime attestation (template lines 9-16).

    §18 line 366: the runtime-attestation path binds the actual loaded artifact set to, among
    others, the "Release Generation". Every coordinate is an injected scalar.
    """

    software_release_policy_id: str | None = None
    software_release_policy_generation: int | None = None
    software_release_policy_digest: str | None = None
    release_set_id: str | None = None
    release_generation: int | None = None
    admitted_release_set_digest: str | None = None
    release_artifact_manifest_digest: str | None = None


class VerificationProfileBinding(FrozenModel):
    """The ``verification_profile_binding:`` block of a policy (template lines 36-39).

    The ten VERIFICATION-PROFILE-002 keys ADR §29 item 12 names are **all** ``null`` with
    ``owner: TBD`` today (design #29 §8): the profile binding carries the identity of the profile
    whose values a Phase-0 Bounds-Approver will set. **SCI authors zero new profile keys and
    hardcodes zero numbers.**
    """

    verification_profile_id: str | None = None
    verification_profile_version: str | None = None
    verification_profile_digest: str | None = None


class DecisionTimeBinding(FrozenModel):
    """The admission decision's ``trustworthy_time_binding:`` block (template lines 32-37).

    ``age_within_approved_limit`` is a **numeric-bound INSTANCE** observation whose limit key
    (``MAX_artifact_admission_decision_age_ms``) is ``null`` in Phase 1, so it is deliberately
    **outside** the artifact's ``_REQUIRED_COVERED`` set (design #29 §2.3): requiring it would make
    every Phase-1 artifact unconstructable. A missing or ``False`` numeric claim still fails closed
    wherever it is consumed.
    """

    time_health_generation: int | None = None
    receipt_anchor: str | None = None
    decided_at: int | None = None
    maximum_age_key: str | None = None
    #: Positive polarity — only ``is True`` is within the (injected, Phase-1 null) limit.
    age_within_approved_limit: bool | None = None


class AttestationTimeBinding(FrozenModel):
    """The attestation ``trustworthy_time_binding:`` block (provenance lines 38-43; runtime 46-51).

    Same numeric-bound INSTANCE discipline as :class:`DecisionTimeBinding`; the limit keys are
    ``MAX_build_provenance_age_ms`` and ``MAX_runtime_artifact_attestation_age_ms``, both ``null``
    pending Phase-0 approval (design #29 §8).
    """

    time_health_generation: int | None = None
    receipt_anchor: str | None = None
    attested_at: int | None = None
    maximum_age_key: str | None = None
    #: Positive polarity — only ``is True`` is within the (injected, Phase-1 null) limit.
    age_within_approved_limit: bool | None = None


class SoftwareReleasePolicyFieldGroups(FrozenModel):
    """§8 field-group anchor view — the seventeen ``*_policy_digest`` fields + two set digests.

    ADR §8 line 249-257 enumerates nine prose field groups
    (:data:`~tos.sci.vocabulary.SOFTWARE_RELEASE_POLICY_FIELD_GROUPS`); the SOFTWARE-RELEASE-POLICY
    template realizes them as seventeen ``*_policy_digest`` fields (lines 19-35) plus
    ``approved_bound_set_digest`` (line 40) and ``approved_limit_set_digest`` (line 41) — design #29
    §4.3. This model is the **manually-transcribed anchor** for that set: the §6.2 drift property
    asserts its field names equal the template's and are all present on
    :class:`~tos.sci.records.SoftwareReleasePolicy`, so a whole field group cannot be silently
    dropped (the WDR MAJOR-1 defect class).

    §8 line 259: "Unknown fields, mutable references, hidden defaults, local overrides,
    consumer-selected substitutions, implicit inheritance, or ``latest`` resolution are prohibited."
    """

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
    approved_bound_set_digest: str | None = None
    approved_limit_set_digest: str | None = None


class DependencyClosureDigestSet(FrozenModel):
    """§11 closure anchor view — the seventeen dependency/toolchain set digests (§4.9).

    ADR §11 line 285: the closure manifest "SHALL cover all transitive build-time and runtime
    dependencies, package sources, plugins, compilers, linkers, interpreters, SDKs, code generators,
    base images, operating-system packages, native libraries, dynamically loaded modules, sidecars,
    proxies, migration tools, and signer components that can change safety-relevant behavior or
    broker-directed bytes." The DEPENDENCY-AND-TOOLCHAIN-CLOSURE-MANIFEST template realizes that as
    sixteen ``*_set_digest`` fields (lines 15-30) plus ``compatibility_edge_set_digest`` (line 34) —
    seventeen dimensions in total (design #29 §4.9).

    **Consumed, not decorative**: :func:`~tos.sci.predicates.closure_complete_or_restrictive`
    iterates these seventeen field names over the manifest, so an omitted dimension is a real
    admission denial and a dropped field is a behavioural regression, not just a drift-test failure.
    """

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
    compatibility_edge_set_digest: str | None = None


class AdmissionBindingSet(FrozenModel):
    """§15 step 1-7 binding anchor view — the nine scalar digest bindings (§4.4).

    The ARTIFACT-ADMISSION-DECISION template lines 16-24 carry the nine scalar digests the §15
    step 2-6 verifications bind, plus ``target_scope_digest``. **The verification *results* are
    sealed inside those digests by +Security** — SCI checks that each binding is present, concrete,
    and not a mutable name, and performs **no** signature verification, byte comparison, scan, SBOM
    parse, or registry retrieval (design #29 §0.2 over-realization boundary; the C1-3 "invented bool
    verdict" removal).

    **Consumed, not decorative**: :func:`~tos.sci.predicates.admission_admits_only_positive`
    iterates these nine field names over the decision (§5.4 item 3). The two *structured* bindings —
    ``policy_binding`` (:class:`PolicyBinding`) and ``release_artifact_binding``
    (:class:`ReleaseArtifactBinding`) — are checked through their own models in the same item, and
    the two ordering scalars (``predecessor_release_generation``,
    ``current_release_restriction_floor``) through the §5.0 ordering helpers in items 4 and 8.
    """

    source_revision_manifest_digest: str | None = None
    dependency_and_toolchain_closure_manifest_digest: str | None = None
    build_provenance_attestation_digest: str | None = None
    artifact_signature_and_key_status_digest: str | None = None
    registry_custody_proof_digest: str | None = None
    compatibility_graph_digest: str | None = None
    scan_test_and_finding_evidence_digest: str | None = None
    common_mode_analysis_digest: str | None = None
    target_scope_digest: str | None = None


def restriction_floor_not_behind(
    decision_floor: int | None, active_floor: int | None
) -> bool:
    """Whether an admission decision's restriction floor is at or ahead of the active one (§15-7).

    ADR §15 step 7: admission "verify[s] predecessor Release Generation and **every current
    restriction floor**". A decision that observed an *older* floor than the one currently in force
    has not seen the newest restrictive fact and cannot admit (§16 line 348 "New restrictive facts
    advance the release restriction floor without waiting for a replacement permissive set").

    ``True`` **only** when both floors are present and the decision floor is **at or ahead of** the
    active floor. An **equal** pair is at-or-ahead and returns ``True`` through a short-circuit that
    sits **before** the ``compare_order`` call by construction: ``compare_order`` maps an equal pair
    to ``Ordering.AMBIGUOUS`` (``tos/src/tos/ordering/_ordering.py`` lines 77-83), so evaluating the
    comparison first would deny every legitimate equal-floor decision (the §6.3 (i) false-negative
    canary). ``Ordering.AFTER`` (the decision is behind) and ``Ordering.AMBIGUOUS`` both deny, and a
    ``None`` on either side denies (design #29 §5.0).

    This is **not** the cur restriction-floor advance mechanism: cur ``fence_advances_floor`` owns
    the cross-artifact monotonic advance (§20 line 404 "through ADR-002-024"); this helper answers
    only the admission-time not-behind question (design #29 §3.5 M4 / §5.6c).

    Args:
        decision_floor: The decision's ``current_release_restriction_floor`` ordering scalar.
        active_floor: The currently active restriction floor ordering scalar (injected).

    Returns:
        ``True`` iff both floors are present and the decision floor is at or ahead of the active one.
    """
    if decision_floor is None or active_floor is None:
        return False
    if decision_floor == active_floor:
        return True
    return (
        compare_order(
            OrderingEvent(quorum_commit_index=active_floor),
            OrderingEvent(quorum_commit_index=decision_floor),
        )
        is Ordering.BEFORE
    )


def generation_strictly_advances(
    predecessor: int | None, successor: int | None
) -> bool:
    """Whether ``successor`` strictly follows ``predecessor`` in Release Generation order (§5.8).

    ADR §5.8 line 131: a Release Generation "is a monotonic restrictive generation ... It **cannot
    be reused** after rejection, revocation, rollback, restore, compromise, or supersession." §22
    line 433: "Rollback is a new release proposal, admission decision, Admitted Release Set, and
    Release Generation." An **equal** pair is therefore a *reuse* and denies — the difference from
    :func:`restriction_floor_not_behind`, which allows equality because a floor is an at-or-ahead
    proposition. Using the floor helper here would let a reused generation pass (the §6.3 (j)
    fail-open canary).

    ``True`` **only** when both scalars are present and ``compare_order`` proves
    ``Ordering.BEFORE``; equal (which maps to ``Ordering.AMBIGUOUS``), ``Ordering.AMBIGUOUS``, and
    ``Ordering.AFTER`` all deny, as does a ``None`` on either side. Same polarity as the cur
    ``floor_strictly_advances`` shape it re-expresses locally (import zero, design #29 §3.4).

    Args:
        predecessor: The predecessor Release Generation ordering scalar.
        successor: The candidate / committed Release Generation ordering scalar.

    Returns:
        ``True`` iff ``successor`` provably strictly follows ``predecessor``.
    """
    if predecessor is None or successor is None:
        return False
    return (
        compare_order(
            OrderingEvent(quorum_commit_index=predecessor),
            OrderingEvent(quorum_commit_index=successor),
        )
        is Ordering.BEFORE
    )
