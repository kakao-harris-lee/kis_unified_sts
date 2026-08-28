"""Brokercap value models + the append-only Broker Capability Profile (design #10 §2).

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True,
extra="forbid")`` via :class:`~tos.brokercap._base.FrozenModel`): frozen is the record-
level realization of append-only (ADR-002-004 §21 auditable / §27 replayable) — there is
**no** update / delete / mutate method on any model (design #10 §2.0). enum values / field
names use the ADR §5-§15 terms **verbatim** (spec terms = code terms, boundary design #1
§2.4; the erratum-defect-class seal, design #10 §2.2).

Numeric bounds (quantity / risk limits) use the promoted core
:data:`~tos.canonical.CanonicalDecimal` (design #10 §0.4c / §3.1) so ``1.0`` and ``1.00``
share one profile digest — never a bare ``Decimal``. Every threshold / quota / window /
horizon is otherwise an **injected** scalar carried on the predicate-input models, never
hardcoded (design #10 §8): a missing value fails closed at the consuming predicate.

The :class:`BrokerCapabilityProfile` is a digest-bound
:class:`~tos.brokercap._base.IndependentIdArtifact` with an independent,
governance-assigned ``profile_id`` (``id != f(digest)``, design #10 §3.1) so a same-id /
different-bytes forged / re-issued profile version is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT``. Each profile **version** is an immutable
record; a legitimate revalidation / supersession is a **new** version (new record, linked
by ``superseded_version_link``), never an in-place mutation (design #10 §2.3).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.brokercap._base``) +
``tos.brokercap`` only; no ``shared.*``, no other sibling ``tos.*`` (design #10 §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from tos.brokercap._base import FrozenModel, IndependentIdArtifact
from tos.brokercap.vocabulary import (
    AssuranceLevel,
    AssuranceSource,
    CapabilityDimension,
    CapabilityStatus,
    ConformanceClass,
    ProhibitedProof,
)
from tos.canonical import CanonicalDecimal

# ===========================================================================
# Value models (plain frozen) — profile-covered content
# ===========================================================================


class ProfileKey(FrozenModel):
    """The 10-coordinate profile key (ADR-002-004 §7.1 line 245-256 verbatim).

    The scope coordinates a profile version is valid for. §7.1 line 258: "Broader profiles
    are permitted only when evidence proves semantic equivalence across the broader scope"
    — Phase 1 carries the key as **coordinates only**; a broadening claim is an injected
    evidence judgment (unproven => the narrow scope; design #10 §2.2). All coordinates are
    opaque strings (broker-agnostic — a concrete ``broker_id`` value belongs to a Profile
    INSTANCE, ADR §21).
    """

    broker_id: str | None = None
    api_product: str | None = None
    api_version: str | None = None
    environment: str | None = None
    account_type: str | None = None
    market: str | None = None
    instrument_class: str | None = None
    order_type: str | None = None
    session_type: str | None = None
    credential_scope: str | None = None


class ProfileVersion(FrozenModel):
    """The 7-field profile version block (ADR-002-004 §7.2 line 264-270 verbatim).

    Dates are **injected scalars** (opaque strings), never read from a clock — brokercap
    accesses no clock (design #10 §3.5). ``profile_version`` is the immutable version
    identifier; ``superseded_version_link`` links a supersession chain whose order is
    carried by ``tos.ordering`` (design #10 §3.2). This block is covered (digest preimage),
    so a changed version / effective date / approver changes the profile digest.
    """

    profile_version: str | None = None
    effective_date: str | None = None
    evidence_package_version: str | None = None
    approver_identity: str | None = None
    expiration_or_revalidation_date: str | None = None
    superseded_version_link: str | None = None
    change_reason: str | None = None


class CapabilityDeclaration(FrozenModel):
    """One dimension's capability declaration (ADR-002-004 §5.2 / §21 Capability Matrix).

    The per-dimension record the admissibility predicate reads: a status, an assurance
    level + its sources, the evidence reference (a scalar — evidence records are referenced,
    never imported; design #10 §3.5), and — for a deficient dimension — a restriction /
    fallback reference. A ``VERIFIED_WITH_RESTRICTION`` status authorizes live behavior
    **only** when ``restriction_approved is True`` (the explicit approval of §5.3 line 146;
    ``None`` / ``False`` fails closed — design #10 §5.1). An empty ``evidence_reference``
    under a ``VERIFIED`` status is an illegal fixture (design #10 §7 clean-vs-illegal
    discipline) — the predicates never mint a status; a fixture must supply real evidence.
    """

    dimension: CapabilityDimension | None = None
    status: CapabilityStatus | None = None
    assurance_level: AssuranceLevel | None = None
    evidence_reference: str | None = None
    restriction: str | None = None
    restriction_approved: bool | None = None
    fallback_reference: str | None = None
    assurance_sources: tuple[AssuranceSource, ...] = ()


class LiveScope(FrozenModel):
    """The live-scope envelope a profile authorizes (ADR-002-004 §5.10 line 183; §21).

    The account / instrument / order-type / quantity-risk / session / action-class / mode
    coordinates the scope covers. ``quantity_risk_limit`` is a
    :data:`~tos.canonical.CanonicalDecimal` (scale-normalized). ``reduced_off_unattended_
    partition_protection`` marks that the scope has been reduced so it does **not** depend
    on unattended partition-time autonomous protection (§13.15; design #10 §6.5) — ``None``
    / ``False`` means not reduced (fail-closed at
    :func:`~tos.brokercap.predicates.partition_class_scope_ok`).
    """

    account_scope: str | None = None
    instrument_scope: str | None = None
    order_type_scope: str | None = None
    quantity_risk_limit: CanonicalDecimal | None = None
    session_scope: str | None = None
    action_classes: tuple[str, ...] = ()
    mode: str | None = None
    reduced_off_unattended_partition_protection: bool | None = None


class FinalQuantityProofRule(FrozenModel):
    """A Final Quantity Proof recipe for an order type (ADR-002-004 §15 line 843-867).

    The profile-declared recipe: which prohibited proofs the profile names (§15.3), and the
    §15.4 stronger-terminal-event markers (``no_later_change_asserted`` — the profile
    explicitly asserts "no crossing fill or correction can later change final quantity";
    ``late_event_window_defined`` — bounded correction handling is defined). At least one of
    the two §15.4 markers must be ``True`` for a proof to be acceptable (unspecified =>
    inadequate — design #10 §6.3). The required-result conjuncts (§15.2) are checked against
    an injected :class:`FinalQuantityEvidence` bundle. The numeric FQP / late-event windows
    themselves are injected scalars (Verification Profile values — design #10 §8), never
    fields here.
    """

    order_type: str | None = None
    prohibited_proofs: frozenset[ProhibitedProof] = frozenset()
    no_later_change_asserted: bool | None = None
    late_event_window_defined: bool | None = None


# ===========================================================================
# Injected predicate-input models (plain frozen)
# ===========================================================================


class RequiredCapabilitySet(FrozenModel):
    """The injected required-capability set for an action class (ADR-002-004 §11; §5.1).

    Which dimensions + assurance level an action class requires is an **injected** approved
    mapping (profile/scope specific — design #10 §5.1 / §9.2 item 9), never hardcoded. Every
    field fails closed: a ``None`` ``required_level`` or a ``minimum_live_gate_satisfied``
    that is not ``True`` makes admissibility ``PROHIBITED`` (design #10 §5.1). A deficient
    required dimension yields ``REDUCED`` **only** if it is in ``approved_fallback_dimensions``
    (an independently approved conservative fallback exists; design #10 §5.3), else
    ``PROHIBITED``.

    The ``required_dimensions`` default ``frozenset()`` is deliberately kept (uniform with
    every other tos injected-input model — liveauth ``ContinuousValidityInputs`` / recon
    ``ReleaseProofInputs`` are all-optional + fail-closed at the predicate) because it is now
    a **safe, fail-closed default**: :func:`~tos.brokercap.predicates.capability_admissible`
    treats an empty (unspecified) required set as **all 17 dimensions at the highest level**
    (§5.1 doctrine "전 차원 필요·최고 level로 취급"), so an empty set is the most-restrictive
    input, never a vacuous pass.

    Attributes:
        required_dimensions: The dimensions this action class requires. **Empty = unspecified
            => treated as all 17 dimensions at the highest level (§5.1 doctrine, fail-closed).**
        required_level: The minimum assurance level required (``None`` => fail-closed).
        minimum_live_gate_satisfied: Whether the §11 minimum-live gate is met (``None`` /
            ``False`` => the scope is CLASS-D / prohibited).
        approved_fallback_dimensions: The deficient dimensions for which an approved
            conservative fallback exists (enables ``REDUCED`` instead of ``PROHIBITED``).
    """

    required_dimensions: frozenset[CapabilityDimension] = frozenset()
    required_level: AssuranceLevel | None = None
    minimum_live_gate_satisfied: bool | None = None
    approved_fallback_dimensions: frozenset[CapabilityDimension] = frozenset()


class FallbackSpec(FrozenModel):
    """An injected fallback specification for a deficient dimension (ADR §13; §5.3).

    A fallback is admissible **only** when it is monotone-restrictive (ADR line 34
    "explicit, conservative, measurable, and tied to the affected authority and risk
    scope"; §23.9 "Unsupported Capability with No Scope Reduction ... Rejected"). Every flag
    is ``bool | None`` and fails closed: a fallback that ``widens_capability`` (adds a
    capability the broker never guaranteed), or is not ``conservative``, or is not
    ``tied_to_authority_and_risk_scope``, is not admissible (design #10 §4.2 / §5.3).
    """

    widens_capability: bool | None = None
    conservative: bool | None = None
    tied_to_authority_and_risk_scope: bool | None = None


class ObservedBehavior(FrozenModel):
    """Injected observed behavior for the drift predicate (ADR-002-004 §20.1 line 1006-1016).

    The §20.1 contradiction observations, each an injected boolean (default ``False`` =
    not-observed). Any ``True`` observation that concerns this declaration's dimension is a
    drift (design #10 §6.2). ``dimension`` gates coherence: an observation about a
    **different** dimension does not drift this declaration (fail-closed coherence guard,
    isomorphic to recon's field/confidence guard).
    """

    dimension: CapabilityDimension | None = None
    duplicate_order_despite_idempotency: bool = False
    event_before_declared_impossible: bool = False
    missing_sequence: bool = False
    late_fill_beyond_window: bool = False
    query_omission_beyond_bound: bool = False
    unexpected_rate_limit: bool = False
    session_behavior_change: bool = False
    unknown_status_code: bool = False
    unit_multiplier_mismatch: bool = False


class BrokerEvidenceRef(FrozenModel):
    """An injected scalar reference to broker evidence (design #10 §3.5).

    Broker evidence records are **referenced**, never imported (the evidence store is a
    downstream projection owned by ADR-002-016; design #10 §3.5). A concrete ``evidence_id``
    (or digest) is required for the evidence to be admissible under a profile
    (:func:`~tos.brokercap.predicates.broker_evidence_admissible_under_profile`); an empty
    reference fails closed. ``environment`` is the evidence's environment coordinate, used
    by the environment-binding check (design #10 §6.4).
    """

    evidence_id: str | None = None
    generation: int | None = None
    digest: str | None = None
    environment: str | None = None


class FinalQuantityEvidence(FrozenModel):
    """Injected observed evidence for a Final Quantity Proof (ADR-002-004 §15.2 line 843-851).

    The §15.2 required-result conjuncts as injected booleans (each ``None`` / ``False`` =>
    fails closed), plus ``sole_prohibited_basis``: the §15.3 prohibited proof that is the
    **sole** basis for the claimed final quantity, if any. When ``sole_prohibited_basis is
    not None`` the proof is inadequate regardless of the conjuncts (a proof resting solely
    on a prohibited basis; design #10 §6.3). All positive conjuncts default ``None``
    (fail-closed).

    Attributes:
        broker_order_identity_or_bounded_effect: Broker order identity established, or a
            bounded unattributed effect (§15.2).
        final_cumulative_filled_quantity: Final cumulative filled quantity established.
        zero_remaining_executable_quantity: Zero remaining executable quantity established.
        corrections_busts_late_events_handled: Corrections / busts / late events handled.
        evidence_source_provenance: Evidence source provenance recorded.
        within_valid_window: Within the valid history / query window (injected bound).
        ordering_waiting_rule_satisfied: The ordering / waiting rule is satisfied.
        sole_prohibited_basis: The prohibited proof that is the sole basis (if any).
    """

    broker_order_identity_or_bounded_effect: bool | None = None
    final_cumulative_filled_quantity: bool | None = None
    zero_remaining_executable_quantity: bool | None = None
    corrections_busts_late_events_handled: bool | None = None
    evidence_source_provenance: bool | None = None
    within_valid_window: bool | None = None
    ordering_waiting_rule_satisfied: bool | None = None
    sole_prohibited_basis: ProhibitedProof | None = None


class UncertainSendVerdict(FrozenModel):
    """The restrictive verdict for an uncertain send (ADR-002-004 §12.4 line 640-646).

    The §12.4 ladder as an all-restrictive verdict — every flag is a "no / must" so a
    permissive combination is **structurally** unrepresentable (design #10 §4.6). The
    verdict is produced by :func:`~tos.brokercap.predicates.uncertain_send_policy`; a
    timeout can never flip ``no_capacity_release`` to a release (ADR §1 line 43 "unresolved
    ambiguity remains UNKNOWN and cannot be released by timeout"; BC-INV-002/003).
    """

    no_retry: bool = True
    no_capacity_release: bool = True
    no_assume_rejection: bool = True
    no_new_conflicting_in_containment: bool = True
    start_reconciliation: bool = True
    enter_unknown_or_contained: bool = True


# ===========================================================================
# Digest-bound append-only Broker Capability Profile
# ===========================================================================


class BrokerCapabilityProfile(IndependentIdArtifact):
    """An append-only, version-immutable Broker Capability Profile (ADR-002-004 §7; §21).

    A digest-bound :class:`~tos.brokercap._base.IndependentIdArtifact` with an independent,
    governance-assigned ``profile_id`` (``id != f(digest)``, design #10 §3.1) so a same-id /
    different-bytes forged or re-issued profile version is a detectable
    ``classify_record_pair`` ``CRITICAL_CONFLICT``. A profile is **re-issued** over time
    (revalidation, supersession, EXPIRED -> revalidate); each version is an **immutable**
    record and a legitimate revalidation is a **new** version (a fresh ``profile_id``,
    linked by ``ProfileVersion.superseded_version_link``), never an in-place mutation
    (design #10 §2.3). The mutable capability facts live inside covered ``declarations``, so
    a same-id re-issuance with changed bytes is (correctly) a critical conflict — a forged
    re-publish — while a legitimate revalidation with a fresh id is ``DISTINCT``.

    ``_REQUIRED_COVERED`` lists **structural identity / scope / version / class** fields
    only (design #10 §2.3); the numeric magnitudes inside ``live_scope`` /
    ``final_quantity_proof_rules`` are excluded so a profile is ISSUED-reachable under
    Phase-1 null bounds (the recon / liveauth ``records.py`` discipline) — a missing
    magnitude fails closed at the consuming predicate. ``profile_order`` is self-excluded
    from the digest preimage (it carries the append-only ``tos.ordering`` supersession
    order, set at ledger placement — the recon ``assessment_revision`` precedent).

    This record has **no** egress / capacity-mutation / authorization-issue /
    KnowledgeState-set method — it is a non-transmitting, non-enforcing representation
    (design #10 §4.5; ADR §19/§27 defer enforcement to the runtime Broker Adapter).
    """

    _ID_FIELD: ClassVar[str] = "profile_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "profile_key",
        "profile_version",
        "conformance_class",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "profile_key",
            "profile_version",
            "declarations",
            "conformance_class",
            "live_scope",
            "final_quantity_proof_rules",
            "evidence_package_ref",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    profile_id: str | None = None

    # ---- Layer-1 covered content (ADR §7 / §8 / §10 / §15) --------------------
    profile_key: ProfileKey | None = None
    profile_version: ProfileVersion | None = None
    declarations: tuple[CapabilityDeclaration, ...] = ()
    conformance_class: ConformanceClass | None = None
    live_scope: LiveScope | None = None
    final_quantity_proof_rules: tuple[FinalQuantityProofRule, ...] = ()
    evidence_package_ref: str | None = None

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    profile_order: int | None = None

    def declaration_for(
        self, dimension: CapabilityDimension
    ) -> CapabilityDeclaration | None:
        """Return the declaration for ``dimension``, or ``None`` if **undeclared**.

        An undeclared dimension is BC-INV-001 ("treated as unavailable") — the caller
        maps a ``None`` result to most-restrictive, never to a pass (design #10 §4.1). This
        is a pure lookup over the frozen ``declarations`` tuple; it mutates nothing.

        Args:
            dimension: The capability dimension to look up.

        Returns:
            The matching :class:`CapabilityDeclaration`, or ``None`` when the dimension is
            not present in this profile's declarations.
        """
        for decl in self.declarations:
            if decl.dimension is dimension:
                return decl
        return None
