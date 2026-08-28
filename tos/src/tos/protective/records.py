"""Protective value models + the append-only Protective Capacity Profile (design #11 §2).

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True, extra="forbid")``
via :class:`~tos.protective._base.FrozenModel`): frozen is the record-level realization of
append-only (ADR-002-001 §18 audit; §21 evidence) — there is **no** update / delete / mutate
method on any model (design #11 §2.0). enum values / field names use the ADR §3.1 / §4.6 / §6
/ §7 / §11 terms **verbatim** (spec terms = code terms, boundary design #1 §2.4; the
erratum-defect-class seal, design #11 §2.2).

Numeric magnitudes (quantity / notional / margin / reserve bounds) use the already-core
:data:`~tos.canonical.CanonicalDecimal` (design #11 §0.4c / §3.1) so ``1.0`` and ``1.00``
share one profile digest — never a bare ``Decimal``. Every threshold / bound / window is
otherwise an **injected** scalar carried on the predicate-input models, never hardcoded
(design #11 §8): a missing value fails closed at the consuming predicate.

The :class:`ProtectiveCapacityProfile` is a digest-bound
:class:`~tos.protective._base.IndependentIdArtifact` with an independent, governance-assigned
``profile_id`` (``id != f(digest)``, design #11 §3.1) so a same-id / different-bytes forged /
re-issued profile version is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``. Each
profile **version** is an immutable record; a legitimate revalidation / supersession is a
**new** version (a fresh ``profile_id``), never an in-place mutation (design #11 §2.3).

The injected predicate-input models (``AggregateRiskComparison`` / ``IntermediateState
Witness`` / ``DeRestrictionInputs`` / ``ContainedEmergencyInputs``) carry **only** conservative
aggregate-risk comparisons and injected verdicts — never a ``strategy_flag`` / ``sell_
direction`` / ``exit_name`` / ``reduce_intent`` / ``operator_description`` (ADR §6 line 249
"non-authoritative"; classification purity, design #11 §4.3).

Pure module: ``pydantic`` + stdlib + ``tos.protective._base`` (-> ``tos.canonical``) only; no
``shared.*``, no other sibling ``tos.*`` (design #11 §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from tos.canonical import CanonicalDecimal
from tos.protective._base import FrozenModel, IndependentIdArtifact
from tos.protective.vocabulary import GuaranteeLevel, ProtectiveResourceDomain

# ===========================================================================
# Value models (plain frozen) — profile-covered content
# ===========================================================================


class ProtectiveResourceDomainDeclaration(FrozenModel):
    """One domain's guarantee declaration (ADR-002-001 §4.6 / §12.4; design #11 §2.1).

    The per-domain record :func:`~tos.protective.predicates.guarantee_level_resolved` /
    :func:`~tos.protective.predicates.is_reserved_guarantee` read: the domain, its assigned
    :class:`~tos.protective.vocabulary.GuaranteeLevel`, and the evidence flags that ADR §4.6
    line 217 ("SHALL NOT be described as guaranteed unless its reservation mechanism and
    failure independence have been demonstrated") requires before a level counts as reserved.
    A ``PHYSICALLY_RESERVED`` declaration with ``failure_independence_evidenced`` not ``True``
    is an illegal fixture (design #11 §7 clean-vs-illegal discipline) — the predicate never
    mints reserved status; a fixture must supply real evidence. ``evidence_reference`` is a
    scalar (evidence records are referenced, never imported; design #11 §3.5).
    """

    domain: ProtectiveResourceDomain | None = None
    guarantee_level: GuaranteeLevel | None = None
    reservation_mechanism_evidenced: bool | None = None
    failure_independence_evidenced: bool | None = None
    evidence_reference: str | None = None
    common_mode_note: str | None = None


class ProtectiveActionEnvelope(FrozenModel):
    """The protective action envelope a profile declares (ADR-002-001 §7 line 300-315).

    §7 line 315 verbatim: "The Protective Action Envelope SHALL remain subordinate to the Hard
    Safety Envelope." The per-axis magnitudes are the already-core
    :data:`~tos.canonical.CanonicalDecimal` (scale-normalized); each is ``None`` until an
    ADR-002-014 Safety Profile INSTANCE supplies it (design #11 §8), and a ``None`` axis fails
    the §6.6 :func:`~tos.protective.predicates.envelope_subordinate` check closed. The
    permitted sets / evidence-requirement / escalation markers are representation only — this
    is a non-enforcing datum (design #11 §4.5).
    """

    permitted_accounts: tuple[str, ...] = ()
    permitted_instruments: tuple[str, ...] = ()
    permitted_action_classes: tuple[str, ...] = ()
    max_quantity: CanonicalDecimal | None = None
    max_notional: CanonicalDecimal | None = None
    max_gross_increase: CanonicalDecimal | None = None
    max_margin: CanonicalDecimal | None = None
    max_action_rate: CanonicalDecimal | None = None
    max_duration: CanonicalDecimal | None = None
    venue_or_order_constraint: str | None = None
    evidence_requirement: str | None = None
    escalation_on_breach: bool | None = None


class HardEnvelopeRef(FrozenModel):
    """The Hard Safety Envelope bounds the protective envelope is subordinate to (§7).

    An injected reference to the ADR-002-014 Hard Safety Envelope's per-axis maxima (design
    #11 §6.6); each is ``None`` until the Safety Profile INSTANCE supplies it and fails the
    subordination check closed. The axes mirror :class:`ProtectiveActionEnvelope` so
    :func:`~tos.protective.predicates.envelope_subordinate` can compare them axis-for-axis.
    """

    max_quantity: CanonicalDecimal | None = None
    max_notional: CanonicalDecimal | None = None
    max_gross_increase: CanonicalDecimal | None = None
    max_margin: CanonicalDecimal | None = None
    max_action_rate: CanonicalDecimal | None = None
    max_duration: CanonicalDecimal | None = None


class ProtectiveLeaseAdmissibilityScope(FrozenModel):
    """A pre-proven partition-time lease-admissibility scope marker (ADR §9; design #11 §2.1).

    The pre-proven venue / session / account / instrument / order-shape space a Degraded
    Protective Lease was proven admissible for, plus the injected ``staleness_tolerance``
    scalar (an ADR-002-019 Order Admissibility Decision reference; design #11 §8). The actual
    in-scope / staleness verdicts are injected booleans on
    :func:`~tos.protective.predicates.partition_lease_admissible` (rcl / ADR-002-019 owns the
    arithmetic; protective consumes the verdicts — design #11 §3.5). This marker is carried
    for representation; a ``None`` marker never widens admissibility.
    """

    pre_proven_venues: tuple[str, ...] = ()
    pre_proven_sessions: tuple[str, ...] = ()
    pre_proven_accounts: tuple[str, ...] = ()
    pre_proven_instruments: tuple[str, ...] = ()
    pre_proven_order_shapes: tuple[str, ...] = ()
    staleness_tolerance: str | None = None


# ===========================================================================
# Injected predicate-input models (plain frozen) — classification purity §4.3
# ===========================================================================


class AggregateRiskComparison(FrozenModel):
    """Injected conservative aggregate-risk comparison for §6.1 (ADR §6.1 line 255-263).

    The §6.1 final-state comparison values — supplied by ARE (ADR-002-021, an unimplemented
    tos package; design #11 §0.2) as scaled :data:`~tos.canonical.CanonicalDecimal` — plus the
    already-exceeded-regime marker (ADR-002-002 §23.2). protective compares, it does **not**
    compute the numbers (design #11 §3.5). It carries **no** ``strategy_flag`` / ``sell_
    direction`` / ``exit_name`` / ``reduce_intent`` / ``operator_description`` / ``correlation``
    field — a strategy label is non-authoritative (ADR §6 line 249; classification purity,
    design #11 §4.3). Any ``None`` magnitude fails the classifier closed to ``RISK_INCREASING_
    DENIED`` (design #11 §5.3).
    """

    final_conservative_risk: CanonicalDecimal | None = None
    current_conservative_risk: CanonicalDecimal | None = None
    no_action_risk: CanonicalDecimal | None = None
    already_exceeded_regime: bool | None = None


class IntermediateStateWitness(FrozenModel):
    """Injected §6.2 intermediate-state witness (ADR §6.2 line 265-279).

    The worst credible partial-fill / ordering / leg-failure / late-fill / basis / liquidity /
    margin intermediate risk (compared against ``AggregateRiskComparison.no_action_risk``),
    plus the credible-state-space bound (RFC-002 §3.1.17; injected flag — a **None** / unbounded
    space => ``UNKNOWN_CONSERVATIVE``, never silently excluded, ADR §6.2 line 277) and the
    no-exceedance-increase witness. Like :class:`AggregateRiskComparison` it carries **no**
    strategy label (classification purity, design #11 §4.3).
    """

    worst_intermediate_risk: CanonicalDecimal | None = None
    credible_space_bounded: bool | None = None
    no_credible_intermediate_increases_exceedance: bool | None = None


class DeRestrictionInputs(FrozenModel):
    """Injected §8.5 ``CONTAINED`` -> ``DEGRADED_PROTECTIVE`` de-restriction inputs (ADR §8.5).

    The v0.7 U1 de-restriction predicate folds these (design #11 §6.1). The five
    ``*_only`` flags are the §8.5 line 391 forbidden **sole** bases ("Elapsed time,
    connectivity or session restoration, broker reconnection, quiet time, cache agreement, or
    the mere absence of new adverse signals SHALL NOT cause or contribute to this
    transition") — each defaults ``False`` (not-the-sole-basis) and **any** ``True`` denies.
    The four affirmative-re-establishment flags + the governed-decision flag are ``bool |
    None`` and load-bearing (all must be positively ``True``; ``None`` / ``False`` fails
    closed, §8.5 line 402-407), and ``dominating_halt_or_incident`` must be positively
    ``False`` (a dominating stronger restriction denies; ADR-002-027 / SIR-INV-015 injected
    verdict). All affirmative inputs are injected verdicts (orthostate ``RECONCILED`` /
    authority current / profile valid / ADR-002-018 trust) — protective owns the roll-up, not
    the arithmetic (design #11 §3.5).
    """

    # (i) not automatic — the forbidden sole bases (§8.5 line 391; default not-sole-basis).
    elapsed_time_only: bool = False
    connectivity_restored_only: bool = False
    quiet_time_only: bool = False
    cache_agreement_only: bool = False
    absence_of_adverse_signal_only: bool = False
    # (ii) affirmative re-establishment (§8.5 line 402; cached / last-known-good insufficient).
    reconciled_authoritative_state: bool | None = None
    safety_authority_current: bool | None = None
    hard_and_runtime_profile_valid: bool | None = None
    critical_input_trust_restored: bool | None = None
    # (iii) explicit governed decision (§8.5 line 403-407).
    explicit_safety_authority_decision: bool | None = None
    # (iv) no dominating stronger restriction (§8.5; ADR-002-027 / 015 injected verdict).
    dominating_halt_or_incident: bool | None = None


class ContainedEmergencyInputs(FrozenModel):
    """Injected §8.3.1 ``CONTAINED`` emergency-action inputs (ADR §8.3.1 line 362-367).

    The §8.3.1 reduce-only-by-construction emergency-action conjuncts (design #11 §6.1); each
    is ``bool | None`` and load-bearing (all must be positively ``True``; ``None`` / ``False``
    => not admissible => trapped / escalate). ``reduce_only_by_construction`` is the §8.3.1
    line 362 "reduce-only across every governed dimension relative to the current reconciled
    position" witness; ``independently_authorized`` is the Safety-Authority / operator-
    emergency-path authorization (§23.2 — operator authorization does not make an unproven
    action protective, line 364); ``potentially_live_final_quantity_rule_preserved`` is the
    §14.1-4 rcl rule (injected — protective does not re-author it, design #11 §3.5).
    """

    in_preapproved_bounded_set: bool | None = None
    reduce_only_by_construction: bool | None = None
    within_bounded_emergency_envelope: bool | None = None
    independently_authorized: bool | None = None
    potentially_live_final_quantity_rule_preserved: bool | None = None


# ===========================================================================
# Digest-bound append-only Protective Capacity Profile
# ===========================================================================


class ProtectiveCapacityProfile(IndependentIdArtifact):
    """An append-only, version-immutable Protective Capacity Profile (ADR §4.6 / §12.4; §7).

    A digest-bound :class:`~tos.protective._base.IndependentIdArtifact` with an independent,
    governance-assigned ``profile_id`` (``id != f(digest)``, design #11 §3.1) so a same-id /
    different-bytes forged or re-issued profile version is a detectable ``classify_record_pair``
    ``CRITICAL_CONFLICT``. A profile is **re-issued** over time (revalidation, supersession,
    guarantee-level up/downgrade); each version is an **immutable** record and a legitimate
    revalidation is a **new** version (a fresh ``profile_id``), never an in-place mutation
    (design #11 §2.3). The mutable domain / guarantee facts live inside covered
    ``declarations``, so a same-id re-issuance with changed bytes is (correctly) a critical
    conflict — a forged re-publish — while a legitimate revalidation with a fresh id is
    ``DISTINCT``.

    ``_REQUIRED_COVERED`` lists **structural identity / version** fields only (design #11
    §2.3); the numeric magnitudes inside ``action_envelope`` are excluded so a profile is
    ISSUED-reachable under Phase-1 null bounds (the recon / liveauth / brokercap ``records.py``
    discipline) — a missing magnitude fails closed at the consuming predicate. ``profile_order``
    is self-excluded from the digest preimage (it carries the append-only ``tos.ordering``
    supersession order, set at ledger placement — the brokercap ``profile_order`` precedent).

    This record has **no** egress / capacity-mutation / authorization-issue / mode-set /
    capacity-release method — it is a non-transmitting, non-enforcing representation (design
    #11 §4.5; ADR §5 line 241 defers enforcement to the runtime Protective Action Controller).
    """

    _ID_FIELD: ClassVar[str] = "profile_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "profile_version",
        "approver_identity",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "profile_version",
            "approver_identity",
            "declarations",
            "action_envelope",
            "lease_admissibility_scope",
            "reserve_minimum_ref",
            "evidence_package_ref",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    profile_id: str | None = None

    # ---- Layer-1 covered content (ADR §4.6 / §7 / §12) ------------------------
    profile_version: str | None = None
    approver_identity: str | None = None
    declarations: tuple[ProtectiveResourceDomainDeclaration, ...] = ()
    action_envelope: ProtectiveActionEnvelope | None = None
    lease_admissibility_scope: ProtectiveLeaseAdmissibilityScope | None = None
    reserve_minimum_ref: str | None = None
    evidence_package_ref: str | None = None

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    profile_order: int | None = None

    def declaration_for(
        self, domain: ProtectiveResourceDomain
    ) -> ProtectiveResourceDomainDeclaration | None:
        """Return the declaration for ``domain``, or ``None`` if **undeclared**.

        An undeclared domain is treated as ``UNAVAILABLE`` (ADR §4.1 line 158) — the caller
        maps a ``None`` result to most-restrictive, never to a pass (design #11 §4.1). This is
        a pure lookup over the frozen ``declarations`` tuple; it mutates nothing.

        Args:
            domain: The protective resource domain to look up.

        Returns:
            The matching :class:`ProtectiveResourceDomainDeclaration`, or ``None`` when the
            domain is not present in this profile's declarations.
        """
        for decl in self.declarations:
            if decl.domain is domain:
                return decl
        return None
