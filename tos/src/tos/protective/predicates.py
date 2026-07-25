"""Pure protective-decision predicates (design #11 §5, §6).

The EV-L1 *functions* the property tests verify — none is a stored field; all are computed on
demand over **injected** state (design #11 §0.2: no clock, no egress, no persistence, no
capacity mutation — those are runtime EV-L2/L3). Every predicate is conservative /
**fail-closed** (design #11 §4.1): a missing / undeclared / unassigned / unproven / ``None``
input never becomes ``ADMISSIBLE`` / ``True`` — live admission requires **positive proof**,
and there is deliberately no "assume-admissible" path anywhere. The central completeness
predicates (:func:`domain_enumeration_complete`, :func:`guarantee_assignment_complete`) treat
an empty / unspecified required set as the full 7-domain floor, so a zero-iteration loop can
never yield a vacuous pass (the fail-open seal, design #11 §4.1 / §5.1).

Produced-value seam (design #11 §3.4): protective imports **none** of its consumers /
siblings (``tos.authority`` / ``tos.liveauth`` / ``tos.rcl`` / ``tos.orthostate`` / ...) — it
produces plain ``bool`` outputs their already-ratified predicates consume as injected
``bool | None`` flags. The five produced bools + their consuming slots:

* :func:`protective_classification_present` ``True`` (``PROTECTIVE_PROVEN``) fills authority
  ``degraded_lease_valid``'s ``protective_classification_present`` (``authority/predicates.py:
  513``); ``False`` fails it closed.
* :func:`protective_capacity_exhausted` ``True`` fills authority ``degraded_lease_invalidated``'s
  ``protective_capacity_exhausted`` (``authority/predicates.py:639``); ``True`` / ``None``
  invalidates.
* :func:`protective_leases_reconciled` fills authority ``state.py:129`` +
  liveauth re-arm variant prereq (``liveauth/predicates.py:135``).
* :func:`reserve_sufficiency` (== the produced ``protective_coverage_valid``) fills liveauth
  ``ContinuousValidityInputs.protective_coverage_valid`` (``liveauth/state.py:138``).
* :func:`protective_coverage_added` fills liveauth ``InPlaceExpansionInputs.protective_coverage_
  added`` (``liveauth/state.py:204``).

protective returns ``bool``; the consuming signatures are ``bool | None`` (``None`` fails
closed), so a protective ``False`` and a caller-supplied ``None`` are both safe. Runtime
wiring is the caller's (future Protective Action Controller / Live-Authorization /
Reconciliation Service) concern; the MANDATED test-only cross-checks (``test_seam_authority`` /
``test_seam_liveauth``) lock this alignment without making the seam a package edge (design #11
§3.4/§7.1).

Numbers are never hardcoded: every bound / budget / threshold / horizon is an injected
parameter, and a ``None`` bound fails closed (design #11 §8). Broker-agnostic: no predicate
names a concrete broker (design #11 §0.1).

Pure module: ``pydantic`` + stdlib + ``tos.protective`` only; no ``shared.*``, no sibling
``tos.*`` beyond ``tos.canonical`` (design #11 §0.3).
"""

from __future__ import annotations

from collections.abc import Mapping

from tos.canonical import CanonicalDecimal
from tos.protective.records import (
    AggregateRiskComparison,
    ContainedEmergencyInputs,
    DeRestrictionInputs,
    HardEnvelopeRef,
    IntermediateStateWitness,
    ProtectiveActionEnvelope,
    ProtectiveCapacityProfile,
    ProtectiveLeaseAdmissibilityScope,
    ProtectiveResourceDomainDeclaration,
)
from tos.protective.vocabulary import (
    REQUIRED_PROTECTIVE_DOMAINS,
    Admissibility,
    GuaranteeLevel,
    ProtectiveActionKind,
    ProtectiveActionOutcome,
    ProtectiveOwnership,
    ProtectiveResourceDomain,
)

# ===========================================================================
# §5.1 — domain enumeration completeness (PRD-EV-001 substrate; core L1 slice)
# ===========================================================================


def _resolve_required(
    required: frozenset[ProtectiveResourceDomain] | None,
) -> frozenset[ProtectiveResourceDomain]:
    """Return the required-domain set, substituting the 7-domain floor for None / empty.

    An unspecified (``None``) or **empty** required set is treated as the full
    :data:`~tos.protective.vocabulary.REQUIRED_PROTECTIVE_DOMAINS` floor — the most
    restrictive interpretation, so a zero-iteration loop never yields a vacuous pass (design
    #11 §4.1 / §5.1; the brokercap empty-required fail-closed lesson).
    """
    if not required:
        return REQUIRED_PROTECTIVE_DOMAINS
    return required


def domain_enumeration_complete(
    profile: ProtectiveCapacityProfile | None,
    required: frozenset[ProtectiveResourceDomain] | None = None,
) -> bool:
    """Whether every required protective resource domain is enumerated (ADR §4 line 158; §4.6).

    ADR §4 line 158 verbatim: "Protective capacity SHALL be defined across **all resources
    whose exhaustion could prevent containment**." Returns ``True`` **only** when every domain
    in the required set is present in ``profile.declarations`` — a required domain that is
    **not** enumerated is treated as ``UNAVAILABLE`` (design #11 §4.1 / §4.2), and there is
    **no** "assume-present" path. The required set is **injected + floored**: a ``None`` /
    **empty** required set is the full 7-domain floor (design #11 §5.1), and broker/venue
    domains only widen it (the ``+Broker`` slice). PRD-EV-001 substrate — **not** closed
    (``+Broker`` / integration ``/3`` remain; design #11 §1).

    Args:
        profile: The Protective Capacity Profile under test (``None`` => ``False``).
        required: The required protective resource domains (``None`` / empty => the 7-domain
            floor, fail-closed).

    Returns:
        ``True`` iff every required domain is declared.
    """
    if profile is None:
        return False
    required_set = _resolve_required(required)
    declared = frozenset(
        decl.domain for decl in profile.declarations if decl.domain is not None
    )
    return required_set <= declared


# ===========================================================================
# §5.2 — guarantee-level assignment completeness (PRD-EV-002 substrate; core L1 slice)
# ===========================================================================


def is_reserved_guarantee(
    declaration: ProtectiveResourceDomainDeclaration | None,
) -> bool:
    """Whether a declaration positively establishes a reserved guarantee (ADR §4.6 line 217).

    ADR §4.6 line 217 verbatim: "A resource SHALL NOT be described as **guaranteed** unless its
    reservation mechanism and failure independence have been demonstrated. Priority is not
    reservation." Returns ``True`` **only** from positive evidence:

    * ``PHYSICALLY_RESERVED`` — ``reservation_mechanism_evidenced is True`` AND
      ``failure_independence_evidenced is True`` (both demonstrated, line 217; §4.2 item 2).
    * ``LOGICALLY_RESERVED`` — ``reservation_mechanism_evidenced is True`` AND a
      ``common_mode_note`` is present (the shared lower-level dependency documented honestly;
      §12.4 line 547).
    * ``PRIORITIZED_ONLY`` / ``BEST_EFFORT`` / ``UNAVAILABLE`` / ``None`` — **never** reserved
      (§3.1.4 line 144 "A prioritized resource is not a reserved resource"; design #11 §4.2).

    Any missing evidence flag fails closed (not reserved). [SAFE-003; SAFE-015; SAFE-040]

    Args:
        declaration: The domain declaration (``None`` => ``False``).

    Returns:
        ``True`` iff the declaration demonstrably establishes a reserved guarantee.
    """
    if declaration is None or declaration.guarantee_level is None:
        return False
    level = declaration.guarantee_level
    if level is GuaranteeLevel.PHYSICALLY_RESERVED:
        return (
            declaration.reservation_mechanism_evidenced is True
            and declaration.failure_independence_evidenced is True
        )
    if level is GuaranteeLevel.LOGICALLY_RESERVED:
        return (
            declaration.reservation_mechanism_evidenced is True
            and declaration.common_mode_note is not None
        )
    return False


def guarantee_level_resolved(
    domain: ProtectiveResourceDomain,
    profile: ProtectiveCapacityProfile | None,
) -> GuaranteeLevel:
    """Resolve a domain's effective guarantee level, fail-closed (ADR §4.6 line 215/217; §12.4).

    Returns the assigned :class:`~tos.protective.vocabulary.GuaranteeLevel`, with two
    fail-closed rules (design #11 §4.2):

    * an **undeclared** domain, or a declaration with a ``None`` level, resolves to
      ``UNAVAILABLE`` (the lowest — ADR line 217; there is no "assume-present" promotion);
    * a declaration claiming ``PHYSICALLY_RESERVED`` / ``LOGICALLY_RESERVED`` **without** the
      demonstrated evidence (:func:`is_reserved_guarantee` ``False``) is **downgraded** to
      ``PRIORITIZED_ONLY`` (ADR line 217 "SHALL NOT be described as guaranteed unless
      demonstrated") — a claim is never trusted over its evidence.

    PRD-EV-002 substrate — **not** closed (integration ``/3`` remains; design #11 §1).

    Args:
        domain: The protective resource domain to resolve.
        profile: The Protective Capacity Profile (``None`` => ``UNAVAILABLE``).

    Returns:
        The effective guarantee level (``UNAVAILABLE`` when unassigned / undemonstrated).
    """
    if profile is None:
        return GuaranteeLevel.UNAVAILABLE
    declaration = profile.declaration_for(domain)
    if declaration is None or declaration.guarantee_level is None:
        return GuaranteeLevel.UNAVAILABLE
    level = declaration.guarantee_level
    if level in (
        GuaranteeLevel.PHYSICALLY_RESERVED,
        GuaranteeLevel.LOGICALLY_RESERVED,
    ) and not is_reserved_guarantee(declaration):
        return GuaranteeLevel.PRIORITIZED_ONLY
    return level


def guarantee_assignment_complete(
    profile: ProtectiveCapacityProfile | None,
    required: frozenset[ProtectiveResourceDomain] | None = None,
) -> bool:
    """Whether every required domain has an assigned guarantee level (ADR §4.6; design #11 §5.2).

    Returns ``True`` **only** when :func:`domain_enumeration_complete` holds AND every required
    domain has an **explicitly assigned** guarantee level (an explicit ``UNAVAILABLE`` counts
    as an evidenced assignment; an *undeclared* domain or a ``None`` level is an **implicit**
    ``UNAVAILABLE` => incomplete). A missing / unassigned domain fails closed (design #11
    §4.2). PRD-EV-002 substrate — **not** closed.

    Args:
        profile: The Protective Capacity Profile (``None`` => ``False``).
        required: The required protective resource domains (``None`` / empty => the 7-domain
            floor, fail-closed).

    Returns:
        ``True`` iff enumeration is complete and every required domain carries an explicit
        guarantee level.
    """
    if not domain_enumeration_complete(profile, required):
        return False
    assert profile is not None  # domain_enumeration_complete rejected None
    required_set = _resolve_required(required)
    for domain in required_set:
        declaration = profile.declaration_for(domain)
        if declaration is None or declaration.guarantee_level is None:
            return False
    return True


# ===========================================================================
# §5.3 — protective action classification (produces protective_classification_present)
# ===========================================================================


def protective_classification(
    comparison: AggregateRiskComparison,
    intermediate: IntermediateStateWitness,
    *,
    envelope_within_hard: bool | None,
) -> ProtectiveActionOutcome:
    """Classify an action by conservative aggregate-risk analysis (ADR §6.1/§6.2 line 251-279).

    Realizes the §6.1 final-state test ∧ §6.2 intermediate-state test over **injected**
    conservative aggregate-risk comparisons — never a strategy label (ADR §6 line 249;
    classification purity, design #11 §4.3). Returns:

    * ``UNKNOWN_CONSERVATIVE`` when the credible state space is **unbounded** (``credible_
      space_bounded`` not ``True``) — treated conservatively as UNKNOWN, never silently
      excluded (§6.2 line 277);
    * ``RISK_INCREASING_DENIED`` when protectiveness cannot be **positively** proven — any
      ``None`` magnitude, a worst intermediate above no-action, a credible intermediate that
      increases hard-limit exceedance, or (normal regime) a final not below current / outside
      the Hard Safety Envelope (§6.2 line 279 "classified as risk increasing and denied");
    * ``PROTECTIVE_PROVEN`` only from positive proof: worst-intermediate <= no-action ∧ no
      credible exceedance increase, AND either the normal regime (``final < current`` within
      the Hard Safety Envelope) or the already-exceeded regime (``final <= current`` return-
      toward-envelope trajectory with no exceedance increase — a single action need not
      restore the full envelope, §6.1 line 263).

    The aggregate-risk magnitudes are injected (ARE / ADR-002-021; protective compares only,
    design #11 §0.2). [SAFE-004 hard envelope; SAFE-013 aggregate risk; SAFE-021; SAFE-025]

    Args:
        comparison: The injected §6.1 aggregate-risk comparison.
        intermediate: The injected §6.2 intermediate-state witness.
        envelope_within_hard: Whether the final state is within the Hard Safety Envelope
            (normal regime; ``None`` / ``False`` => denied unless already-exceeded regime).

    Returns:
        The classification outcome.
    """
    if intermediate.credible_space_bounded is not True:
        return ProtectiveActionOutcome.UNKNOWN_CONSERVATIVE
    final = comparison.final_conservative_risk
    current = comparison.current_conservative_risk
    no_action = comparison.no_action_risk
    worst = intermediate.worst_intermediate_risk
    if final is None or current is None or no_action is None or worst is None:
        return ProtectiveActionOutcome.RISK_INCREASING_DENIED
    # §6.2 intermediate-state test: no credible intermediate worse than no-action, and none
    # increases hard-limit exceedance (both must be positively established).
    if not (
        worst <= no_action
        and intermediate.no_credible_intermediate_increases_exceedance is True
    ):
        return ProtectiveActionOutcome.RISK_INCREASING_DENIED
    if comparison.already_exceeded_regime is True:
        # §6.1 line 263 relaxation: return-toward-envelope trajectory + no exceedance increase.
        if final <= current:
            return ProtectiveActionOutcome.PROTECTIVE_PROVEN
        return ProtectiveActionOutcome.RISK_INCREASING_DENIED
    # §6.1 normal regime: strict final < current within the Hard Safety Envelope.
    if envelope_within_hard is True and final < current:
        return ProtectiveActionOutcome.PROTECTIVE_PROVEN
    return ProtectiveActionOutcome.RISK_INCREASING_DENIED


def protective_classification_present(
    comparison: AggregateRiskComparison,
    intermediate: IntermediateStateWitness,
    *,
    envelope_within_hard: bool | None,
) -> bool:
    """Whether the action is proven protective (produced bool; design #11 §3.4).

    ``True`` **only** when :func:`protective_classification` is ``PROTECTIVE_PROVEN`` — a
    ``RISK_INCREASING_DENIED`` / ``UNKNOWN_CONSERVATIVE`` outcome fails closed. This produced
    bool fills authority ``degraded_lease_valid``'s injected ``protective_classification_
    present`` condition (``authority/predicates.py:513``; ``None`` / ``False`` => the lease is
    invalid). A strategy label can never flip it (classification purity, design #11 §4.3).

    Args:
        comparison: The injected §6.1 aggregate-risk comparison.
        intermediate: The injected §6.2 intermediate-state witness.
        envelope_within_hard: Whether the final state is within the Hard Safety Envelope.

    Returns:
        ``True`` iff the action is classified ``PROTECTIVE_PROVEN``.
    """
    return (
        protective_classification(
            comparison, intermediate, envelope_within_hard=envelope_within_hard
        )
        is ProtectiveActionOutcome.PROTECTIVE_PROVEN
    )


# ===========================================================================
# §6.1 — degraded-mode: §8.5 de-restriction / §8.1-8.4 per-mode / §8.3.1 emergency
# ===========================================================================


def derestriction_admissible(inputs: DeRestrictionInputs) -> bool:
    """Whether ``CONTAINED`` -> ``DEGRADED_PROTECTIVE`` de-restriction is admissible (ADR §8.5).

    The v0.7 U1 governed de-restriction (design #11 §6.1). Returns ``True`` **only** when
    **all four** conditions hold, else ``False`` (``CONTAINED`` is retained — fail-closed,
    §8.5 line 389):

    1. **not automatic** — none of the §8.5 line 391 forbidden sole bases (elapsed time /
       connectivity restoration / reconnection / quiet time / cache agreement / mere absence
       of adverse signal) is the trigger;
    2. **affirmative re-establishment** — reconciled authoritative state ∧ current Safety
       Authority ∧ valid hard-and-runtime profile ∧ restored critical-input trust (cached /
       last-known-good insufficient, line 402);
    3. **explicit governed decision** — an explicit Safety-Authority decision (not strategy /
       ordinary-execution / operator-convenience / readiness inference, line 403-407);
    4. **no dominating stronger restriction** — ``dominating_halt_or_incident`` positively
       ``False`` (ADR-002-027 / 015 injected verdict).

    This is **not a re-arm** (§8.5 line 383-386): it grants no new risk / live authority, so it
    does **not** invoke the ADR-002-007 re-arm workflow — protective authors it as a separate
    predicate and never touches liveauth re-arm (design #11 §3.5). Every governed input is an
    injected verdict; the arithmetic is authority's / orthostate's (design #11 §3.5).
    [SAFE-003; SAFE-041; SAFE-044 no automatic re-arm]

    Args:
        inputs: The injected §8.5 de-restriction inputs.

    Returns:
        ``True`` iff the governed de-restriction is admissible.
    """
    # (i) not automatic — any forbidden sole basis denies (§8.5 line 391).
    if (
        inputs.elapsed_time_only
        or inputs.connectivity_restored_only
        or inputs.quiet_time_only
        or inputs.cache_agreement_only
        or inputs.absence_of_adverse_signal_only
    ):
        return False
    # (ii) affirmative re-establishment — all four positively True (§8.5 line 402).
    if not (
        inputs.reconciled_authoritative_state is True
        and inputs.safety_authority_current is True
        and inputs.hard_and_runtime_profile_valid is True
        and inputs.critical_input_trust_restored is True
    ):
        return False
    # (iii) explicit governed decision (§8.5 line 403-407).
    if inputs.explicit_safety_authority_decision is not True:
        return False
    # (iv) no dominating stronger restriction (positively False required).
    return inputs.dominating_halt_or_incident is False


def mode_permits_protective(
    mode_rank: int | None,
    action: ProtectiveActionOutcome,
    envelope_ok: bool | None,
) -> bool:
    """Whether the current mode permits a protective action (ADR §8.1-8.4; design #11 §6.1).

    Composes the injected authority precedence coordinate (``mode_rank`` — the authority
    ``PRECEDENCE_RANK`` verdict, whose per-mode ordering / thresholds are **owned by
    authority**, design #11 §3.5; not re-derived here) with the §5.3 classification and §6.6
    envelope subordination. Returns ``True`` **only** when the mode is known (``mode_rank`` not
    ``None``), the action is ``PROTECTIVE_PROVEN`` (§5.3), and it stays within its envelope
    (``envelope_ok is True``). A ``None`` mode / envelope, or an unproven action, fails closed
    (deny) — the mode enum is **not** re-declared (authority-duplication excluded, §0.4e).

    Args:
        mode_rank: The injected authority precedence rank (``None`` => deny).
        action: The §5.3 classification outcome.
        envelope_ok: Whether the action is envelope-subordinate (``None`` / ``False`` => deny).

    Returns:
        ``True`` iff the mode is known, the action is proven protective, and it is within
        envelope.
    """
    if mode_rank is None:
        return False
    if envelope_ok is not True:
        return False
    return action is ProtectiveActionOutcome.PROTECTIVE_PROVEN


def contained_emergency_admissible(inputs: ContainedEmergencyInputs) -> bool:
    """Whether a ``CONTAINED`` emergency action is admissible (ADR §8.3.1 line 362-367).

    Returns ``True`` **only** when **all five** §8.3.1 conjuncts are positively ``True``
    (design #11 §6.1) — in a pre-approved bounded set, reduce-only-by-construction across every
    governed dimension relative to the current reconciled position, within the bounded
    emergency envelope, independently authorized (Safety Authority / operator emergency path),
    and preserving the §14.1-4 Potentially-Live / Final-Quantity rule (injected rcl verdict).
    Any ``None`` / ``False`` => not admissible => trapped / escalate (§15 / §13 line 367).
    Operator authorization does **not** make an unproven action protective (line 364).

    Args:
        inputs: The injected §8.3.1 emergency-action inputs.

    Returns:
        ``True`` iff every §8.3.1 conjunct holds positively.
    """
    return (
        inputs.in_preapproved_bounded_set is True
        and inputs.reduce_only_by_construction is True
        and inputs.within_bounded_emergency_envelope is True
        and inputs.independently_authorized is True
        and inputs.potentially_live_final_quantity_rule_preserved is True
    )


# ===========================================================================
# §6.2 — partition-time lease-admissibility (ADR §9 line 448 "ADR-002-001 owns")
# ===========================================================================


def partition_lease_admissible(
    action_kind: ProtectiveActionKind,
    scope: ProtectiveLeaseAdmissibilityScope | None,
    *,
    within_pre_proven_scope: bool | None,
    staleness_ok: bool | None,
    lease_valid_for_new_transmission: bool | None,
    partition_new_commitment_denied: bool | None,
) -> Admissibility:
    """Partition-time lease-admissibility verdict (ADR §9 line 426/448; design #11 §6.2).

    ADR line 448: "ADR-002-001 owns this partition-time lease-admissibility rule." Returns:

    * ``PROHIBITED`` when no valid lease exists (``lease_valid_for_new_transmission`` not
      ``True``) — the action cannot proceed under any lease;
    * ``TRAPPED`` when the rcl partition verdict is unknown (``partition_new_commitment_denied
      is None``), or the action is cancel-first / removal / weakening, or an add-only action
      is outside the pre-proven scope or past staleness — current admissibility cannot be
      established, so the exposure stays "conservatively covered and trapped (§15) rather than
      transmitted on stale admissibility" (§9 line 448);
    * ``ADMISSIBLE`` **only** for an overlap-first / add-only action that consumes an
      already-valid lease within the pre-proven scope and within staleness (§9 line 448 "the
      lease MAY support overlap-first / add-only protective action") — new Aggregate Protective
      Commitment stays denied to rcl's ``partition_verdict`` (injected; design #11 §3.5).

    The rcl ``partition_verdict`` / lease-validity and the pre-proven scope / staleness are all
    injected coordinates (protective consumes, never re-authors, design #11 §3.5). [SAFE-024;
    SAFE-035; SAFE-048]

    Args:
        action_kind: The protective action kind (overlap-first add-only vs cancel-first).
        scope: The pre-proven lease-admissibility scope marker (representation; ``None`` never
            widens admissibility).
        within_pre_proven_scope: Whether the action is within the pre-proven scope.
        staleness_ok: Whether the lease is within staleness tolerance.
        lease_valid_for_new_transmission: Whether a valid lease exists (``None`` / ``False`` =>
            ``PROHIBITED``).
        partition_new_commitment_denied: The rcl ``partition_verdict`` new-commitment-denied
            flag (``None`` => ``TRAPPED``, conservative).

    Returns:
        The admissibility verdict.
    """
    del scope  # representation only; the verdicts are injected (design #11 §3.5)
    if lease_valid_for_new_transmission is not True:
        return Admissibility.PROHIBITED
    if partition_new_commitment_denied is None:
        return Admissibility.TRAPPED
    if (
        action_kind is ProtectiveActionKind.OVERLAP_FIRST_ADD_ONLY
        and within_pre_proven_scope is True
        and staleness_ok is True
    ):
        return Admissibility.ADMISSIBLE
    # cancel-first / removal / weakening, or out-of-scope / stale add-only => trapped.
    return Admissibility.TRAPPED


# ===========================================================================
# §6.3 — protective ownership + Cancellation Arbiter (ADR §11.1-11.3)
# ===========================================================================


def cancellation_admissible(
    ownership: ProtectiveOwnership,
    *,
    protection_no_longer_required: bool | None,
    within_hard_envelope: bool | None,
    equivalent_replacement_live: bool | None,
    continued_existence_worsens_aggregate: bool | None,
    controller_authorizes_removal: bool | None,
    cancellation_worsens_aggregate: bool | None,
) -> bool:
    """Whether an order may be cancelled (ADR §11.1-11.3; design #11 §6.3).

    For a ``SAFETY_OWNED`` order (§11.1 line 475-479) returns ``True`` **only** under one of
    the three conditions, else ``False`` (strategy / ordinary-execution cleanup can never
    cancel it):

    * protection is no longer required AND the position is within the Hard Safety Envelope; or
    * an equivalent / stronger replacement is **authoritatively confirmed live** (``equivalent_
      replacement_live is True``) — a submitted / transmitted / acknowledged replacement gets
      **no** optimistic protection credit (§11.4 line 506; the caller sets this ``True`` only
      when confirmed); or
    * continued existence worsens conservative aggregate risk AND the Protective Action
      Controller authorizes removal.

    For any other ownership (ordinary risk-increasing order, §11.3) returns ``True`` **only**
    when ``cancellation_worsens_aggregate is False`` — cancelling is confirmed not to worsen
    aggregate risk (protective evaluation precedes ordinary cancellation, §11.2 line 487; the
    ordering is the caller's). Any ``None`` fails closed. order-state (orthostate ``BrokerOrder
    State`` / ``KnowledgeState``) is an injected coordinate (design #11 §3.5). [SAFE-002;
    SAFE-021]

    Args:
        ownership: The order's protective ownership class.
        protection_no_longer_required: Whether protection is no longer required.
        within_hard_envelope: Whether the position is within the Hard Safety Envelope.
        equivalent_replacement_live: Whether an equivalent replacement is confirmed live (no
            optimistic credit — ``None`` / ``False`` => no credit).
        continued_existence_worsens_aggregate: Whether continued existence worsens aggregate
            risk.
        controller_authorizes_removal: Whether the Protective Action Controller authorizes
            removal.
        cancellation_worsens_aggregate: Whether cancelling worsens aggregate risk (ordinary
            orders; only a positive ``False`` permits).

    Returns:
        ``True`` iff the cancellation is admissible.
    """
    if ownership is ProtectiveOwnership.SAFETY_OWNED:
        return (
            (protection_no_longer_required is True and within_hard_envelope is True)
            or (equivalent_replacement_live is True)
            or (
                continued_existence_worsens_aggregate is True
                and controller_authorizes_removal is True
            )
        )
    # ordinary risk-increasing order (§11.3): cancel only if confirmed not to worsen aggregate.
    return cancellation_worsens_aggregate is False


# ===========================================================================
# §6.4 — bounded retry + exhaustion (produces protective_capacity_exhausted)
# ===========================================================================


def retry_admissible(
    *,
    budget_remaining: int | None,
    duplicate_economic_effect_possible: bool | None,
    unknown_outcome: bool | None,
    dedup_proven: bool | None,
) -> bool:
    """Whether a bounded protective retry is admissible (ADR §13 line 583-594; §14.4 line 639).

    Returns ``True`` **only** when: a positive budget remains (``budget_remaining`` is concrete
    and ``> 0``); a duplicate economic effect is impossible (``duplicate_economic_effect_
    possible is False``, §13.3 "retry cannot create duplicate economic effect"); and the
    outcome is not an unproven UNKNOWN (``unknown_outcome`` ``True`` with ``dedup_proven`` not
    ``True`` => no retry — "blind resubmission is prohibited", §14.4 line 639). Any ``None`` /
    exhausted budget fails closed. [SAFE-014 bounded action rate; SAFE-021]

    Args:
        budget_remaining: The injected retry budget remaining (``None`` / ``<= 0`` => no
            retry).
        duplicate_economic_effect_possible: Whether a duplicate economic effect is possible
            (only a positive ``False`` permits).
        unknown_outcome: Whether the prior outcome is UNKNOWN.
        dedup_proven: Whether deduplication is proven (required when the outcome is UNKNOWN).

    Returns:
        ``True`` iff a bounded, non-duplicating retry is admissible.
    """
    if budget_remaining is None or budget_remaining <= 0:
        return False
    if duplicate_economic_effect_possible is not False:
        return False
    # UNKNOWN outcome without proven dedup => blind resubmission prohibited (§14.4 line 639).
    return not (unknown_outcome is True and dedup_proven is not True)


def protective_capacity_exhausted(
    profile: ProtectiveCapacityProfile | None,
    required: frozenset[ProtectiveResourceDomain] | None = None,
    *,
    budget_remaining: int | None,
) -> bool:
    """Whether protective capacity is exhausted (ADR §13 line 578-594; produces a bool; §3.4).

    Returns ``True`` (**exhausted** — the restrictive, containment-triggering direction) when
    any required protective resource domain is ``UNAVAILABLE`` / unverifiable (§13 line 578-579
    "risk capacity, margin, broker quota or session, worker or queue, network path, trustworthy
    time, current Protective Lease, or reconciliation capability") **or** the retry budget is
    exhausted (``budget_remaining`` ``None`` / ``<= 0``). Retry-budget exhaustion is itself a
    containment trigger and Critical operational event (§13 line 594). Fail-closed: a ``None``
    profile / budget => exhausted.

    This produced bool fills authority ``degraded_lease_invalidated``'s ``protective_capacity_
    exhausted`` (``authority/predicates.py:639``; ``True`` / ``None`` invalidates the lease —
    the polarity is aligned). The preserve / Potentially-Live arithmetic is rcl's (INV-005/012;
    design #11 §3.5). [SAFE-014; SAFE-021]

    Args:
        profile: The Protective Capacity Profile (``None`` => exhausted).
        required: The required protective resource domains (``None`` / empty => the 7-domain
            floor).
        budget_remaining: The injected retry budget remaining (``None`` / ``<= 0`` =>
            exhausted).

    Returns:
        ``True`` iff protective capacity is exhausted.
    """
    if budget_remaining is None or budget_remaining <= 0:
        return True
    if profile is None:
        return True
    required_set = _resolve_required(required)
    for domain in required_set:
        if guarantee_level_resolved(domain, profile) is GuaranteeLevel.UNAVAILABLE:
            return True
    return False


# ===========================================================================
# §6.5 — time-untrusted protective behavior (ADR §10 line 455-463)
# ===========================================================================


def time_untrusted_protective_admissible(
    action_kind: ProtectiveActionKind,
    *,
    time_trusted: bool | None,
    nontime_dependent_emergency_rule: bool | None,
    cancellation_not_risk_increasing: bool | None,
) -> Admissibility:
    """Protective behavior when time cannot be trusted (ADR §10 line 455-463; design #11 §6.5).

    When ``time_trusted is True`` the normal path applies (delegated to the other predicates)
    and this returns ``ADMISSIBLE`` (not blocked on the time axis). When time is **not** trusted
    (``False`` / ``None``), time-dependent live / protective authorization is invalid (§10 line
    456-457), so:

    * a ``NEW_PROTECTIVE_ORDER`` is ``ADMISSIBLE`` **only** under a non-time-dependent emergency
      rule (``nontime_dependent_emergency_rule is True``; §10 line 459), else ``PROHIBITED``;
    * a ``CANCELLATION_OF_RISK_INCREASING`` order MAY be ``ADMISSIBLE`` when it is not itself
      risk-increasing (``cancellation_not_risk_increasing is True``; §10 line 460), else
      ``PROHIBITED``;
    * any other kind is ``PROHIBITED``.

    An unverified protective authorization is **not** permanently valid (§10 line 463) — the
    model provides no "authorization persists after time-untrust" operation (structural
    absence). Time freshness / holdover is ``tos.time``'s; protective consumes the
    ``time_trusted`` bool (design #11 §0.4e). [SAFE-035 trustworthy time basis]

    Args:
        action_kind: The protective action kind.
        time_trusted: Whether time is trusted (``True`` => normal path; ``False`` / ``None`` =>
            time-untrusted rules).
        nontime_dependent_emergency_rule: Whether a non-time-dependent emergency rule applies
            (for a new protective order).
        cancellation_not_risk_increasing: Whether a cancellation is not itself risk-increasing.

    Returns:
        The admissibility verdict.
    """
    if time_trusted is True:
        return Admissibility.ADMISSIBLE
    if action_kind is ProtectiveActionKind.NEW_PROTECTIVE_ORDER:
        return (
            Admissibility.ADMISSIBLE
            if nontime_dependent_emergency_rule is True
            else Admissibility.PROHIBITED
        )
    if action_kind is ProtectiveActionKind.CANCELLATION_OF_RISK_INCREASING:
        return (
            Admissibility.ADMISSIBLE
            if cancellation_not_risk_increasing is True
            else Admissibility.PROHIBITED
        )
    return Admissibility.PROHIBITED


# ===========================================================================
# §6.6 — protective action envelope subordination (ADR §7 line 315)
# ===========================================================================

#: The per-axis magnitude fields compared for envelope subordination (§7). Each axis of the
#: protective envelope must be <= the Hard Safety Envelope's corresponding axis.
_ENVELOPE_AXES: tuple[str, ...] = (
    "max_quantity",
    "max_notional",
    "max_gross_increase",
    "max_margin",
    "max_action_rate",
    "max_duration",
)


def envelope_subordinate(
    protective: ProtectiveActionEnvelope | None,
    *,
    hard_envelope_bounds: HardEnvelopeRef | None,
) -> bool:
    """Whether the protective envelope is subordinate to the Hard Safety Envelope (ADR §7).

    §7 line 315 verbatim: "The Protective Action Envelope SHALL remain subordinate to the Hard
    Safety Envelope." Returns ``True`` **only** when every axis (max quantity / notional /
    gross-increase / margin / action-rate / duration) of ``protective`` is present and ``<=``
    the corresponding Hard Safety Envelope axis. A missing axis on either side (``None``) fails
    closed — subordination cannot be proven (design #11 §6.6). The magnitudes are injected
    :data:`~tos.canonical.CanonicalDecimal` (ADR-002-014 Safety Profile; never hardcoded,
    design #11 §8). [SAFE-004 hard envelope; SAFE-050]

    Args:
        protective: The protective action envelope (``None`` => ``False``).
        hard_envelope_bounds: The injected Hard Safety Envelope bounds (``None`` => ``False``).

    Returns:
        ``True`` iff every protective axis is present and within the hard bound.
    """
    if protective is None or hard_envelope_bounds is None:
        return False
    for axis in _ENVELOPE_AXES:
        protective_value: CanonicalDecimal | None = getattr(protective, axis)
        hard_value: CanonicalDecimal | None = getattr(hard_envelope_bounds, axis)
        if protective_value is None or hard_value is None:
            return False
        if protective_value > hard_value:
            return False
    return True


# ===========================================================================
# §6.7 — dynamic reserve sufficiency + protective-lease reconciliation
#         (produces protective_coverage_valid / protective_leases_reconciled /
#          protective_coverage_added)
# ===========================================================================


def reserve_sufficiency(
    profile: ProtectiveCapacityProfile | None,
    *,
    forecast_capacity: Mapping[ProtectiveResourceDomain, CanonicalDecimal | None],
    approved_minimum: Mapping[ProtectiveResourceDomain, CanonicalDecimal | None],
    required: frozenset[ProtectiveResourceDomain] | None = None,
) -> bool:
    """Whether dynamic reserve is sufficient (ADR §12.5 line 549-561; produces coverage_valid).

    Returns ``True`` **only** when, for **every** required protective resource domain, the
    forecast capacity is present and ``>=`` the approved minimum. A ``None`` forecast or minimum
    (or a domain missing from either map) fails closed (insufficient) — the §12.5 sufficiency
    ladder (``LIVE_RESTRICTED -> DEGRADED_PROTECTIVE -> CONTAINED -> HALTED``, line 555-559) is
    **authority mode**'s to drive; protective produces only the sufficiency bool (design #11
    §3.5). An empty required set is the 7-domain floor (never a vacuous pass, design #11 §4.1).

    This produced bool is the ``protective_coverage_valid`` that fills liveauth
    ``ContinuousValidityInputs.protective_coverage_valid`` (``liveauth/state.py:138``; ``None`` /
    ``False`` => invalid). The thresholds / forecasts are injected (Safety Profile / rcl; never
    hardcoded, design #11 §8). [SAFE-040 protective control in degraded; SAFE-015]

    Args:
        profile: The Protective Capacity Profile (``None`` => ``False``).
        forecast_capacity: The injected per-domain forecast capacity (``None`` value =>
            insufficient).
        approved_minimum: The injected per-domain approved minimum (``None`` value =>
            insufficient).
        required: The required protective resource domains (``None`` / empty => the 7-domain
            floor).

    Returns:
        ``True`` iff every required domain's forecast meets its approved minimum.
    """
    if profile is None:
        return False
    required_set = _resolve_required(required)
    for domain in required_set:
        forecast = forecast_capacity.get(domain)
        minimum = approved_minimum.get(domain)
        if forecast is None or minimum is None:
            return False
        if forecast < minimum:
            return False
    return True


def protective_leases_reconciled(
    *,
    all_protective_leases_accounted: bool | None,
    reconciliation_evidence_current: bool | None,
    no_unresolved_protective_lease_conflicts: bool | None,
) -> bool:
    """Whether protective leases are reconciled (ADR §5/§16; produces a bool; design #11 §6.7).

    MAJOR-1 definition — isomorphic to the other four producers: returns ``True`` **only** when
    all three injected verdicts are positively ``True`` (``all_protective_leases_accounted and
    reconciliation_evidence_current and no_unresolved_protective_lease_conflicts``), else
    ``False`` (any ``None`` / ``False`` fails closed). The three inputs are injected verdicts
    (protective owns the roll-up, not the arithmetic — design #11 §3.5): all-leases-accounted
    is rcl's ``ProtectiveLease`` aggregation (ADR §5 line 238 / §16 line 675); reconciliation-
    evidence-current is recon's freshness (§12.3 / §9 line 450); no-unresolved-conflict is
    authority's ``lease_scope_exclusive`` verdict (§12.3 Loss of Exclusivity).

    ADR basis (§5 line 229-241): the Protective Action Controller SHALL verify current
    protective capacity and may consume only pre-committed capacity under a **valid Protective
    Lease**, and §16 line 675 makes "protective-capacity accounting is reconciled" a degraded-
    exit precondition — so the protective-side roll-up is an ADR-assigned duty. This produced
    bool fills authority ``state.py:129`` + liveauth re-arm variant prereq (``liveauth/
    predicates.py:135``). [SAFE-044 no automatic re-arm; SAFE-024]

    Args:
        all_protective_leases_accounted: Whether every protective lease is accounted (rcl
            verdict).
        reconciliation_evidence_current: Whether the reconciliation evidence is current (recon
            verdict).
        no_unresolved_protective_lease_conflicts: Whether there is no unresolved / overlapping
            protective-lease conflict (authority exclusivity verdict).

    Returns:
        ``True`` iff all three verdicts are positively ``True``.
    """
    return (
        all_protective_leases_accounted is True
        and reconciliation_evidence_current is True
        and no_unresolved_protective_lease_conflicts is True
    )


def protective_coverage_added(
    profile: ProtectiveCapacityProfile | None,
    *,
    envelope_not_expanded: bool | None,
    forecast_capacity: Mapping[ProtectiveResourceDomain, CanonicalDecimal | None],
    approved_minimum: Mapping[ProtectiveResourceDomain, CanonicalDecimal | None],
    delta_required: frozenset[ProtectiveResourceDomain] | None = None,
) -> bool:
    """Whether an enlarged (delta) scope stays sufficiently covered (ADR §14.1; produces a bool).

    For a §14.1 in-place expansion: returns ``True`` **only** when the delta does **not** expand
    the envelope (``envelope_not_expanded is True``) AND the delta scope's required domains are
    all reserve-sufficient (:func:`reserve_sufficiency`). Fail-closed: an unproven
    envelope-not-expanded, an insufficient delta, or a ``None`` profile => ``False``. This
    produced bool fills liveauth ``InPlaceExpansionInputs.protective_coverage_added``
    (``liveauth/state.py:204``; ``None`` / ``False`` => not admissible). [SAFE-040; SAFE-015]

    Args:
        profile: The Protective Capacity Profile (``None`` => ``False``).
        envelope_not_expanded: Whether the delta stays within the existing envelope (``None`` /
            ``False`` => ``False``).
        forecast_capacity: The injected per-domain forecast capacity.
        approved_minimum: The injected per-domain approved minimum.
        delta_required: The delta scope's required protective resource domains (``None`` /
            empty => the 7-domain floor).

    Returns:
        ``True`` iff the delta stays within the envelope and is reserve-sufficient.
    """
    if envelope_not_expanded is not True:
        return False
    return reserve_sufficiency(
        profile,
        forecast_capacity=forecast_capacity,
        approved_minimum=approved_minimum,
        required=delta_required,
    )


# ===========================================================================
# §6.8 — multi-account minimum allocation (ADR §12.6 line 565-574)
# ===========================================================================


def account_minimum_preserved(
    *,
    per_account_minimum: Mapping[str, CanonicalDecimal | None],
    global_emergency_pool: CanonicalDecimal | None,
    no_account_encroaches_other_minimum: bool | None,
    trapped_and_protectable_separated: bool | None,
) -> bool:
    """Whether multi-account minimum allocation is preserved (ADR §12.6 line 565-574).

    Returns ``True`` **only** when: a concrete global emergency pool is present; every account
    carries a concrete minimum (an empty map or a ``None`` minimum fails closed — no vacuous
    pass); no account's consumption encroaches on another account's minimum protected
    allocation (``no_account_encroaches_other_minimum is True``, line 571); and already-trapped
    accounts are separated from still-protectable ones (``trapped_and_protectable_separated is
    True``, line 573). The actual vector arithmetic is rcl's — protective produces only the
    minimum-preservation judgment over injected survivability-based arbitration markers (design
    #11 §3.5). Any ``None`` fails closed. [SAFE-015 exclusive commitment]

    Args:
        per_account_minimum: The injected per-account minimum protected allocation (empty /
            ``None`` value => ``False``).
        global_emergency_pool: The injected global emergency pool (``None`` => ``False``).
        no_account_encroaches_other_minimum: Whether no account encroaches on another's minimum
            (injected verdict).
        trapped_and_protectable_separated: Whether trapped / still-protectable accounts are
            separated (injected verdict).

    Returns:
        ``True`` iff multi-account minimum allocation is preserved.
    """
    if global_emergency_pool is None:
        return False
    if not per_account_minimum:
        return False
    for minimum in per_account_minimum.values():
        if minimum is None:
            return False
    return (
        no_account_encroaches_other_minimum is True
        and trapped_and_protectable_separated is True
    )
