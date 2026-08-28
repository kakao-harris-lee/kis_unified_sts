"""stm pure predicates — the two §5 yolks, the §6 substrate and the §6b thin models (design #30 §5/§6).

Every function here is **pure**: no I/O, no clock, no network, no mutation, no transmission, no
collection. Each answers one structural question about injected, immutable coordinates and returns
``True`` **only** on positive proof — everything else is denial (design #30 §4.3 fail-closed default).

**Polarity discipline (design #30 §4.3 — the #18/#22/#23/#25 MAJOR-2 seal).** Every ``bool | None``
coordinate declares a polarity in :data:`POSITIVE_POLARITY_FIELDS` / :data:`NEGATIVE_POLARITY_FIELDS`
(or, for a non-judgement observation record, :data:`MARKER_FIELDS`) and is normalized with ``is True`` /
``is False``. A **negative-polarity field is never read with ``is not True``** — that admits a ``None``
and re-opens the fail-open; its clear is ``is False`` and its deny normalization is ``is not False``. A
positive-polarity field clears on ``is True`` and denies on ``is not True``. A ``None`` is UNKNOWN and
converges to **deny** on both polarities (STM-INV-005 line 175). The polarity expectations are read off
the design #30 §4.3 table, never back-derived from this code.

**The C1 lesson is here, in yolk 1.** The design's own v1.0 broke its own rule: the coverage tally
filtered items with ``excluded is not True``, which counted an ``excluded=None`` (unknown-exclusion) item
as covered without any proof — precisely what STM-INV-002 line 163 forbids ("Missing or **unknown**
coverage is a gap, not an exemption"). The ratified v1.1 shape is asymmetric on purpose: the tally
filter is ``excluded is False`` (a positively-disclaimed exclusion) and the approved-exclusion gate fires
on ``excluded is not False`` (``True`` **or** ``None``). Both directions are separately mandated
fixtures.

**Two empty sets with opposite polarity (design #30 §4.4 — this contract's signature ∅ rule).** The same
``()`` means opposite things depending on the *kind* of predicate:

* a **completeness** predicate's ∅ must be checked against the *applicable* side first — an empty
  coverage manifest with a non-empty applicable obligation set **denies** (a gap), while an empty
  manifest with an empty applicable set is a **valid explicit-empty** (rejecting it would be the #26
  MAJOR-1 over-sealing defect), and a non-empty manifest with an empty applicable set denies as surplus;
* a **relational-consistency** predicate's ∅ is **valid ``True``** — no pair, no contradiction. That
  ``True`` asserts *only* the absence of a determinism violation and asserts **nothing** about
  existence; existence is owned by yolk 2's separate presence gate, which denies an empty corpus against
  a non-empty required-key set (STM-INV-004 line 171 "empty query ... proves safety" is the self-yolk
  violation that gate seals).

**Structural derivation over self-report (design #30 §2.4/§4.3).** The recovery non-revival gate is
armed by the **disjunction of the nine recorded recovery-event markers**, never by a self-reported
"recovery happened" flag; the coverage tally is derived from the item structure, never from a stored
score (``coverage_score_present is not False`` ⇒ deny, §9 line 292).

**Group reconcile discipline (design #30 §4.4 — the #22 MAJOR-1 seal).** Coverage judgement reconciles
**all** items conservatively, never the first: the completeness check is both-ways and order-independent,
"a favorable union of narrow manifests cannot create broader coverage" (§9 line 292), and a group's
reconciled generation fence is the **newest** (:func:`~tos.stm.state.max_monitor_generation`), never the
first.

**Three-value discipline (design #30 §4.3 — the #28 MAJOR-2 seal).** "Proven denial", "proven safe" and
"unprovable" are never folded into one boolean: the §18 send race is answered by two independent
predicates, and :class:`~tos.stm.vocabulary.AggregateConformanceResult` keeps ``CONFORMING`` (positive
proof) distinct from ``UNKNOWN`` (unprovable) and ``NON_CONFORMING`` (proven negative) — which is why
``if result:`` is structurally impossible (``__bool__`` raises).

**Forward-seam discipline (design #30 §3.6/§4.1).** stm produces the MONITORING dimension's **value** (a
Monitor Generation and a Continuous Conformance Snapshot digest); the dimension's **completeness
judgement is cur-owned** (``cur/vocabulary.py:144`` inside cur's mandated floor at ``:172``) and is
neither re-authored nor assigned here — a §4.1 canary asserts that cur's dimension-key enum, its
vector-completeness predicate and its mandated dimension floor are absent **by name** from every stm
source. Likewise the
§17 restrictive signal is *produced*; ADR-002-027 keeps materiality, severity, greatest-credible incident
scope, Incident Generation, containment and closure (§17 line 400), which sir already anticipates as an
injected opaque coordinate (``sir/predicates.py:15``).

Pure module: ``pydantic`` + stdlib + ``tos.stm.*`` (records / state / vocabulary / _base) only; no
``shared.*``, no sibling ``tos.*`` (design #30 §0.3). Clock-free.

Regime tag: **coverage-completeness / deterministic-evaluation predicate substrate only; closes no
STM-EV; STM-EV-001..012 all remain NOT_IMPLEMENTED** — the two core rows 001 / 005 are both ``EV-L1/3+Security`` and await ``/3``
integration **and** the whole ``+Security`` coverage-forgery / evaluator-differential axis (there is
**no** clean ``EV-L1/3`` row at all, the lowest of the governance sextet); the eight predicate-only rows
await component-fault ``EV-L2`` plus ``+Broker`` / ``+Security``; the two not-Phase-1 rows (009 / 011)
are ``EV-L3`` runtime. **EV-L1-complete claim forbidden.**
"""

from __future__ import annotations

from tos.ordering import Ordering, compare_order
from tos.stm._base import AllFalseMonitoringAuthority
from tos.stm.records import (
    AlertEscalationRecord,
    ContinuousConformanceSnapshot,
    MonitorCoverageManifest,
    SafetyMonitoringGap,
)
from tos.stm.state import (
    AlertStateVector,
    ApprovedBoundBinding,
    BrokerFinalityTokens,
    CommonModeDisclosure,
    CriticalTelemetryIdentity,
    DashboardStatusView,
    MonitorEvaluation,
    MonitoringRecoveryInputs,
    MonitoringSuppression,
    MonitoringUnknownState,
    RestrictiveMonitoringSignal,
    SendRaceOrdering,
    SilenceObservation,
    TelemetrySemanticView,
    monitor_generation_advances,
)
from tos.stm.vocabulary import (
    HARD_BOUND_KINDS,
    IN_FORCE_SUPPRESSION_STATES,
    NEUTRAL_BOUND_KINDS,
    SUPPRESSION_PRESERVED_FUNCTIONS,
    WEAK_BOUND_KINDS,
    AggregateConformanceResult,
    CoverageDimension,
    DashboardStatusToken,
    NumericInputState,
    TelemetryCriticality,
)

__all__ = [
    # polarity registry (design #30 §4.3 / §7.2 (a))
    "POSITIVE_POLARITY_FIELDS",
    "NEGATIVE_POLARITY_FIELDS",
    "MARKER_FIELDS",
    # all-false authority (STM-INV-001)
    "all_false_monitoring_authority",
    # core §5.1 — yolk 1 + supporting
    "critical_coverage_complete_or_gap",
    "coverage_grants_no_authority",
    "no_self_exemption",
    "monitored_assumption_intake_closed",
    # core §5.2 — yolk 2 (four parts)
    "deterministic_evaluation_bound_integrity",
    "evaluation_is_deterministic",
    "bound_integrity_preserved",
    "numeric_result_not_conforming_by_default",
    # supporting
    "conformance_requires_complete_current_valid",
    "gap_is_restrictive_not_exemption",
    "escalation_single_binding",
    # predicate-only §6 substrate (closes NO STM-EV)
    "telemetry_semantics_exact",
    "absence_is_not_health",
    "unknown_is_restrictive",
    "common_mode_is_not_independence",
    "suppression_cannot_suppress_safety",
    "alert_state_is_orthogonal",
    "loss_preserves_negative_facts",
    "handoff_is_non_authorizing",
    "broker_finality_unchanged",
    "economic_effect_outlives_monitor_state",
    "evidence_and_status_honest",
    "recovery_revives_nothing",
    # not-Phase-1 thin models §6b
    "restriction_ordered_before_capability_claim",
    "attempt_potentially_live",
    "stale_writer_fenced",
]


# ===========================================================================
# polarity registry (design #30 §4.3 — transcribed from the contract's table)
# ===========================================================================

#: Every **positive**-polarity ``bool | None`` coordinate: it clears on ``is True`` and denies on ``is
#: not True`` (``False`` **and** an unknown ``None`` both deny). Transcribed from the design #30 §4.3
#: judgement table plus the §2.4 field skeletons; the §7.2 (a) field-closure property asserts all three
#: directions (every registered name is a declared model field, every declared ``bool | None`` model
#: field is registered, and every registered judgement field is really **read** by a predicate).
POSITIVE_POLARITY_FIELDS: frozenset[str] = frozenset(
    {
        "is_complete",
        "closure_1_to_12_complete",
        "restrictive_response_present",
        "alert_path_present",
        "evidence_path_present",
        "currentness_rule_present",
        "approved_exclusion_proof_present",
        "admitted_as_coverage_item",
        "runtime_falsity_invalidates_property",
        "units_exact",
        "window_inside_bound",
        "uncertainty_treated",
        "source_continuity_present",
        "closure_proof_present",
        "ordering_provable",
        "residual_common_mode_disclosed",
    }
)

#: Every **negative**-polarity ``bool | None`` coordinate: it clears **only** on ``is False`` and denies
#: on ``is not False`` (``True`` **and** an unknown ``None`` both deny). ``is not True`` is **never**
#: used on any of these — that is the exact #18/#22/#23/#25 fail-open the design #30 §4.3 rule seals
#: (and the one the contract's own v1.0 committed on ``excluded``, C1), and the §7.2 polarity regression
#: greps this module to prove it.
NEGATIVE_POLARITY_FIELDS: frozenset[str] = frozenset(
    {
        "excluded",
        "coverage_score_present",
        "permits_individual_exceedance",
        "semantics_reinterpreted",
        "hash_equality_claims_equivalence",
        "cross_host_monotonic_subtracted",
        "identical_values_claim_continuity",
        "age_clamped_from_unbounded",
        "treated_as_healthy",
        "telemetry_missing",
        "state_stale",
        "state_conflicting",
        "state_ambiguous",
        "state_discontinuous",
        "generation_mixed",
        "state_unverifiable",
        "disables_collection",
        "disables_evaluation",
        "disables_restrictive_signaling",
        "disables_evidence",
        "disables_generation_advancement",
        "disables_final_egress_denial",
        "self_health_as_proof",
        "validates_own_continuity_by_own_output",
        "ack_implies_containment",
        "advance_of_one_implies_another",
        "adverse_record_dropped",
        "elapsed_time_reset",
        "missing_ack_treated_as_non_acceptance",
        "cancel_ack_treated_as_fqp",
        "unknown_effect_capacity_released",
        "defaulted_to_green",
        "revived_prior_authority",
        "resumed_trial",
        "restored_production_scope",
        "auto_re_armed",
        "downgrades_existing_fence",
        "selects_narrower_scope",
        "clears_local_latch",
        "publishes_no_incident",
        "unioned_or_substituted",
    }
)

#: The **non-judgement observation markers** (design #30 §4.3 marker list, OQ1). A marker records *what
#: was observed*; it is never itself cleared or denied, so it carries no polarity. Two dispositions:
#:
#: * **structurally consumed** — the nine :data:`~tos.stm.state.MonitoringRecoveryInputs`
#:   ``RECOVERY_MARKER_FIELDS`` whose *disjunction* arms the §24 line 511 non-revival gate,
#:   ``CommonModeDisclosure.claimed_independent`` (read only together with a non-empty
#:   ``shared_dependencies``), and ``DashboardStatusView.rendering_failed`` / ``state_unknown`` (which
#:   trigger the §23 line 499 no-green-default gate);
#: * **explicitly deferred** — the five :data:`~tos.stm.state.SilenceObservation`
#:   ``SILENCE_MARKER_FIELDS``, which record *which* silence was observed and take **no** part in the L1
#:   judgement, because :func:`absence_is_not_health` consumes ``treated_as_healthy``
#:   **unconditionally** (design #30 MINOR-2). They exist for the §22 forgery / runtime-audit axis.
#:
#: ``quiet_time`` is declared on **both** models: it is a deferred silence marker on
#: :class:`~tos.stm.state.SilenceObservation` **and** a consumed recovery marker on
#: :class:`~tos.stm.state.MonitoringRecoveryInputs` (§24 line 507 "or operator return"; §1 line 23
#: "elapsed quiet time"). Because consumption is detected by field *name*, it registers as consumed.
MARKER_FIELDS: frozenset[str] = frozenset(
    {
        # SilenceObservation — explicitly deferred (§4 / §1 line 23)
        "no_alert",
        "repeated_heartbeat",
        "quiet_time",
        "empty_query",
        "green_dashboard",
        # MonitoringRecoveryInputs — structurally consumed as a disjunction (§24 line 507)
        "restart",
        "reconnect",
        "failover",
        "restore",
        "queue_drain",
        "alert_ack",
        "replay",
        "operator_return",
        # CommonModeDisclosure — read only in combination (§14 line 355)
        "claimed_independent",
        # DashboardStatusView — gate triggers (§23 line 499)
        "rendering_failed",
        "state_unknown",
    }
)


#: Normalized placeholder texts that are **not** a concrete reference. Compared after ``strip()`` +
#: ``casefold()`` so ``" TBD "`` / ``"tbd"`` / ``"N/A"`` cannot smuggle a binding past the gate (the #25
#: RLP ``is_wildcard_value`` precedent). **Honestly non-exhaustive**: no denylist of texts can be
#: complete, and it is not asked to be — it catches the canonical template markers this codebase and the
#: spec templates actually emit (``"TBD"`` is the canonical §3.2 must-fill marker). A reference that is
#: merely *wrong* rather than *blank* is a governance fact no string check can decide.
_PLACEHOLDER_REFERENCES: frozenset[str] = frozenset(
    {"", "tbd", "n/a", "na", "none", "null", "-", "?", "unknown", "todo"}
)


def _is_placeholder_reference(value: str | None) -> bool:
    """Whether an external reference is absent, blank or a template placeholder (fail-closed)."""
    if value is None:
        return True
    return value.strip().casefold() in _PLACEHOLDER_REFERENCES


# ===========================================================================
# all-false authority (STM-INV-001; design #30 §2.4/§5.1 conjunct 2)
# ===========================================================================


def all_false_monitoring_authority(
    authority: AllFalseMonitoringAuthority | None,
) -> bool:
    """Whether a monitoring artifact's authority block is genuinely all-false (STM-INV-001; §1 line 25).

    STM-INV-001 line 159 verbatim: "No policy, manifest, snapshot, gap, alert, acknowledgement, page,
    dashboard, or monitoring workflow creates capacity, approval, live authority, transmission
    permission, incident closure, readiness, or re-arm." §1 line 25 says the same for the best possible
    result: even a ``CONFORMING`` snapshot "does not approve an action, create headroom, mark an RFC
    requirement ``PASS``, satisfy preventive control, establish broker finality, activate configuration,
    issue authority, permit transmission, close an incident, establish recovery readiness, restore
    scope, or re-arm." §7 line 236 adds "alert severity is not protective classification."

    The construction validator already rejects a ``True`` flag, so this predicate is the **second
    layer** that re-derives the fact for a ``model_construct`` bypass (defence in depth, design #30
    §2.3): every declared flag must be positively ``False``, and an absent block denies.

    Args:
        authority: The artifact's authority block (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every declared authority flag is positively ``False``.
    """
    if authority is None:
        return False
    return all(
        getattr(authority, name) is False for name in type(authority).model_fields
    )


# ===========================================================================
# core §5.1 — complete Critical coverage (STM-EV-001 yolk, +Security residue)
# ===========================================================================


def coverage_grants_no_authority(manifest: MonitorCoverageManifest | None) -> bool:
    """Whether a Monitor Coverage Manifest grants nothing (STM-INV-001; design #30 §5.1 conjunct 2).

    A manifest is the *mapping* from obligations to monitors; it creates no capacity, approval, live
    authority, transmission permission, incident closure, readiness, re-arm or protective
    classification (STM-INV-001 line 159; §7 line 236).

    Args:
        manifest: The coverage manifest (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the manifest's authority block is genuinely all-false.
    """
    if manifest is None:
        return False
    return all_false_monitoring_authority(manifest.authority_effect)


def no_self_exemption(manifest: MonitorCoverageManifest | None) -> bool:
    """Whether every exclusion claim is proven and no unknown materiality is excluded (§8; §9 line 290).

    §1 line 21 verbatim: "A component SHALL NOT **self-exempt** a safety obligation because a metric is
    inconvenient, unavailable, noisy, or common-mode." §9 line 290: "An exclusion is valid **only when
    independent policy governance proves** that telemetry corruption or omission cannot affect a safety
    decision, delay containment, weaken evidence, or falsely preserve live eligibility. **Unknown scope
    or impact is included.**" §8 line 249: "**Unknown materiality is Critical.**"

    **The C1 asymmetry (design #30 §4.3/§5.1 conjunct 4).** The gate fires on ``excluded is not
    False`` — i.e. on a claimed exclusion (``True``) **and on an unknown one (``None``)** alike. Reading
    it as ``is not True`` would let an ``excluded=None`` item slip past the proof requirement entirely,
    which is exactly the fail-open STM-INV-002 line 163 names: "Missing or **unknown** coverage is a
    gap, not an exemption."

    An item whose criticality is ``UNKNOWN_MATERIALITY`` folds to ``CRITICAL`` and cannot be excluded at
    all — **no proof rescues it** (§8 line 249). Both the ``coverage_items`` and the declared
    ``approved_exclusions`` are checked, and **all** items are reconciled, never the first (design #30
    §4.4).

    Args:
        manifest: The coverage manifest (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no item is excluded without an approved-exclusion proof and no unknown-materiality
        item is excluded at all.
    """
    if manifest is None:
        return False
    for item in tuple(manifest.coverage_items) + tuple(manifest.approved_exclusions):
        if item.excluded is False:
            continue  # positively disclaimed exclusion — nothing to prove
        # `excluded` is True *or* an unknown None: the §9 line 290 gate fires on both (C1).
        # An **undeclared** criticality is treated exactly like a declared `UNKNOWN_MATERIALITY`:
        # §8 line 249 "Unknown materiality is Critical" is about the *state of knowledge*, not about
        # the act of declaring it. Admitting `None` here would invert the incentive — an honest
        # `UNKNOWN_MATERIALITY` report would be penalised while simply omitting the field bought an
        # exclusion. Both are Critical and neither is excludable.
        if (
            item.criticality is None
            or item.criticality is TelemetryCriticality.UNKNOWN_MATERIALITY
        ):
            return (
                False  # §8 line 249 — unknown materiality is Critical, never excludable
            )
        if item.approved_exclusion_proof_present is not True:
            return False
    return True


def monitored_assumption_intake_closed(
    manifest: MonitorCoverageManifest | None,
    submitted_assumption_ids: frozenset[str],
) -> bool:
    """Whether every Monitored Assumption entered through the manifest (§9 line 288; ADR-DEV-011).

    §9 line 288 verbatim (the v0.2 patch): "Each submitted Monitored Assumption is a manifest item
    subject to the same 1-12 closure above or an approved exclusion, admitted through the
    coverage-completeness discipline (STM-INV-002) and **never as an out-of-band addition.**"

    Three layers, all required (design #30 §5.1 conjunct 7):

    1. every submitted id is an intake the manifest actually carries **and** an obligation the manifest
       actually covers — an id with no intake, or an intake whose id is not a coverage item, is the
       out-of-band addition §9 line 288 forbids;
    2. every carried intake is ``admitted_as_coverage_item is True`` (positive polarity);
    3. every carried intake is ``runtime_falsity_invalidates_property is True`` (positive polarity) —
       the property that makes it a *Monitored* Assumption at all rather than a silently trusted
       condition.

    **Deliberately stricter than the ADR's alternative branch (design #30 §5.1 conjunct 7).** §9 line
    288 allows "the same 1-12 closure above **or an approved exclusion**"; the ratified contract requires
    the closure branch positively. That is the fail-closed direction: an assumption admitted by exclusion
    would still have to clear :func:`no_self_exemption`, and requiring positive admission here can only
    deny more, never permit more.

    Args:
        manifest: The coverage manifest (``None`` ⇒ ``False``).
        submitted_assumption_ids: The ids of the Monitored Assumptions submitted to this manifest.

    Returns:
        ``True`` iff every submitted assumption is admitted as a coverage item with an
        invalidating-runtime-falsity declaration.
    """
    if manifest is None:
        return False
    obligation_refs = {
        item.obligation_ref
        for item in manifest.coverage_items
        if item.obligation_ref is not None
    }
    intake_ids = {
        intake.assumption_id
        for intake in manifest.submitted_monitored_assumptions
        if intake.assumption_id is not None
    }
    if not submitted_assumption_ids <= intake_ids:
        return False  # a submitted assumption with no intake — out-of-band addition
    for intake in manifest.submitted_monitored_assumptions:
        if intake.assumption_id is None or intake.assumption_id not in obligation_refs:
            return False  # not a manifest item — out-of-band addition (§9 line 288)
        if intake.admitted_as_coverage_item is not True:
            return False
        if intake.runtime_falsity_invalidates_property is not True:
            return False
    return True


def critical_coverage_complete_or_gap(
    manifest: MonitorCoverageManifest | None,
    applicable_obligations: frozenset[str],
    applicable_dimensions: frozenset[CoverageDimension],
    submitted_assumption_ids: frozenset[str],
) -> bool:
    """Whether Critical coverage is complete and exact (STM-EV-001 **yolk 1**; §9; §8; STM-INV-002).

    §5.4 line 123: the manifest is "The immutable mapping from **every** applicable Critical
    requirement, hazard, accepted control, bound, live prerequisite, and failure mode to its exact
    telemetry, evaluator, dependency closure, restrictive response, alert path, evidence path, and
    currentness rule." STM-INV-002 line 163: "Every applicable Critical obligation has a policy-owned
    monitor mapping over the greatest credible dependency scope. **Missing or unknown coverage is a gap,
    not an exemption.**"

    ``True`` means coverage is complete, exact and non-authorizing. ``False`` means incomplete /
    gapped / inconsistent / undecidable — and a missing obligation is a **gap**, which §13 makes
    restrictive; it is never an exemption. The whole judgement is fail-closed and every conjunct is
    ANDed:

    1. **∅ both-ways (design #30 §4.4/§5.1 conjunct 1).** ``manifest is None`` denies. An **explicit
       empty** manifest (no items) against an **empty** applicable set is *valid* — a no-obligation
       scope is a real state and rejecting it would be the #26 MAJOR-1 over-sealing defect — but only
       with ``is_complete`` positively ``True``. No items against a **non-empty** applicable set denies
       (the missing coverage is a gap). Items against an **empty** applicable set denies as surplus /
       phantom coverage. The applicable side is always checked **before** the ∅ is rejected.
    2. **All-false authority** (:func:`coverage_grants_no_authority`, STM-INV-001 line 159).
    3. **Completeness, both ways (§9; STM-INV-002 line 163).** Every applicable obligation must appear
       among the items whose ``excluded is False`` — the **C1** filter: an ``excluded=None``
       unknown-exclusion is *not* counted here and is routed to conjunct 4 instead. Each mapped item
       must satisfy its item-level closure: the whole §9 line 275-286 1-12 closure plus the four
       separately named items 7 / 8 / 9 / 11.
    4. **No self-exemption** (:func:`no_self_exemption`, §8 line 249 / §9 line 290).
    5. **Item-level closure, no favorable union (§9 line 292).** ``coverage_score_present`` is negative
       polarity: "Coverage percentages, monitor counts, or dashboard completeness scores cannot replace
       item-level closure. A favorable union of narrow manifests cannot create broader coverage."
    6. **Dependency-closure completeness (§9 item 2).** Every applicable dimension must be represented
       in each mapped item's dependency closure — **inclusion only**: a *wider* closure is harmless and
       rejecting it would over-seal (design #30 MINOR-3), while an unrepresented dimension is an
       incompleteness that must deny (the cur ``CONTEXT`` vacuous-pass lesson).
    7. **Monitored-Assumption intake** (:func:`monitored_assumption_intake_closed`, §9 line 288).

    **Closes no STM-EV.** STM-EV-001 is ``EV-L1/3+Security``: the ``/3`` integration axis and the whole
    ``+Security`` coverage / manifest-forgery and suppression-resistance axis (§22 line 472-479) remain,
    and the conservative coverage compiler and requirement/hazard registry are runtime and independently
    reviewed (§30 gate 2). Authoring is not evidence (ADR §27 line 594).

    Args:
        manifest: The Monitor Coverage Manifest (``None`` ⇒ ``False``).
        applicable_obligations: Every applicable Critical obligation reference for this scope.
        applicable_dimensions: Every dependency-closure dimension applicable to this scope.
        submitted_assumption_ids: The ids of the Monitored Assumptions submitted to this manifest.

    Returns:
        ``True`` iff coverage is complete, exact, unexempted and non-authorizing.
    """
    if manifest is None:
        return False

    # --- conjunct 1: ∅ both-ways, applicable side checked first (design #30 §4.4) ---
    # NOTE (deliberate redundancy): this first arm is *provably equivalent* to the conjunct-3 subset
    # check below — on the only inputs it fires for (no items, non-empty applicable set) the coverage
    # tally is empty, so `applicable_obligations <= covered` already denies. It is kept because §4.4
    # requires the applicable side to be inspected **before** an empty manifest is rejected, and
    # stating that ordering explicitly is what stops a future refactor from turning the ∅ case into a
    # blanket denial (the #26 MAJOR-1 over-sealing defect) or a blanket pass.
    if not manifest.coverage_items and applicable_obligations:
        return (
            False  # missing coverage is a gap, not an exemption (STM-INV-002 line 163)
        )
    if manifest.coverage_items and not applicable_obligations:
        return False  # surplus / phantom coverage — both ways

    # --- conjunct 2: all-false authority (STM-INV-001 line 159) ---
    if not coverage_grants_no_authority(manifest):
        return False

    # --- the §9 "complete and exact" claim itself (positive polarity) ---
    if manifest.is_complete is not True:
        return False

    # --- conjunct 5: item-level closure, never a score (§9 line 292, negative polarity) ---
    if manifest.coverage_score_present is not False:
        return False

    # --- conjunct 3: completeness both ways, with the C1 tally filter ---
    covered: dict[str, list] = {}
    for item in manifest.coverage_items:
        # C1: ONLY a positively disclaimed exclusion counts as covered. `is not True` here would
        # count an unknown `excluded=None` item and bypass the conjunct-4 proof gate entirely.
        if item.excluded is False and item.obligation_ref is not None:
            covered.setdefault(item.obligation_ref, []).append(item)
    if not applicable_obligations <= frozenset(covered):
        return False
    for obligation in applicable_obligations:
        for item in covered[obligation]:
            if item.closure_1_to_12_complete is not True:
                return False
            if item.restrictive_response_present is not True:
                return False  # §9 item 7
            if item.alert_path_present is not True:
                return False  # §9 item 8
            if item.evidence_path_present is not True:
                return False  # §9 item 9
            if item.currentness_rule_present is not True:
                return False  # §9 item 11
            # --- conjunct 6: dependency-closure completeness, inclusion-only (§9 item 2) ---
            if not applicable_dimensions <= item.dependency_closure_dimensions:
                return False

    # --- conjunct 4: no self-exemption (§8 line 249; §9 line 290) ---
    if not no_self_exemption(manifest):
        return False

    # --- conjunct 7: Monitored-Assumption intake (§9 line 288 patch) ---
    return monitored_assumption_intake_closed(manifest, submitted_assumption_ids)


# ===========================================================================
# core §5.2 — deterministic evaluation and bound integrity (STM-EV-005 yolk 2)
# ===========================================================================


def evaluation_is_deterministic(evaluations: tuple[MonitorEvaluation, ...]) -> bool:
    """Whether a monitor-evaluation corpus is internally deterministic (§11 line 312; **yolk 2 (a)**).

    §11 line 312 verbatim: "Monitor logic SHALL be immutable, versioned, canonical, **deterministic for
    identical inputs**, and independently testable." §11 line 316: "evaluator disagreement yields
    ``UNKNOWN`` or a restrictive result."

    stm does **not run** an evaluator (that is runtime, design #30 §0.2), so the L1-decidable form of
    determinism is a **relation over the evaluation record corpus**: any two records sharing the
    determinism key ``(evaluator_digest, canonical_input_digest)`` must agree on both ``result`` and
    ``numeric_input_state``. A single disagreement is a determinism violation and denies. This is the
    direct realization of VER-002-001's EV-L1 definition ("property-based testing, and deterministic
    simulation").

    The key's own determinism is **delegated, not re-authored**: ``canonical_input_digest`` is an
    :class:`~tos.stm._base.EVL1ProvisionalCanonicalizer` digest, so "identical inputs ⇒ identical
    digest" is already a tested core property (design #30 §3.1).

    **The ∅ here is valid ``True`` — and asserts nothing about existence (design #30 §4.4/§5.2, C2).**
    An empty or singleton corpus contains no conflicting pair, so there is no determinism violation:
    the vacuous ``True`` of a safety property is sound. It does **not** claim that any evaluation
    exists. Existence is the separate concern of the composite yolk's presence gate, which denies an
    empty corpus against a non-empty required-key set — so calling this relation alone can never produce
    a vacuous overall pass. This is the contract's signature ∅ rule: the same ``()`` is valid here and
    denying in the completeness predicate :func:`critical_coverage_complete_or_gap`, because the two are
    different *kinds* of predicate (design #30 §4.4).

    Args:
        evaluations: The monitor-evaluation corpus (``()`` / singleton ⇒ ``True``, vacuously).

    Returns:
        ``True`` iff no two records share a determinism key while disagreeing on the judgement.
    """
    if len(evaluations) <= 1:
        return True
    seen: dict[tuple[str | None, str | None], MonitorEvaluation] = {}
    for evaluation in evaluations:
        key = (evaluation.evaluator_digest, evaluation.canonical_input_digest)
        prior = seen.get(key)
        if prior is None:
            seen[key] = evaluation
            continue
        if evaluation.result is not prior.result:
            return False
        if evaluation.numeric_input_state is not prior.numeric_input_state:
            return False
    return True


def bound_integrity_preserved(bound: ApprovedBoundBinding | None) -> bool:
    """Whether an approved bound's semantics survived implementation (§11 line 314; **yolk 2 (b)**).

    §11 line 314 verbatim: "An approved **hard maximum cannot be implemented as a percentile, average,
    best-effort target, or window that permits an individual exceedance.** Debounce, grace, hysteresis,
    and confirmation windows **count inside the applicable detection or containment bound** unless the
    approved Verification Profile explicitly defines otherwise." STM-INV-007 line 183: hard maxima and
    their semantics "cannot be replaced by a percentile, average, **local threshold, hidden grace
    period, or favorable sampling rule**."

    **Whitelist, not denylist (design #30 §5.2 (b), M3 — the #25 RLP MAJOR-1 isomorph).** A denylist of
    ``{PERCENTILE, AVERAGE, BEST_EFFORT_TARGET}`` leaks the moment a new weak form is declared — exactly
    what happened between §11 line 314 and STM-INV-007 line 183. This gate instead admits only an
    implemented kind that is **identical to the approved kind and inside a declared partition** of
    :class:`~tos.stm.vocabulary.BoundSemanticKind`; a future member nobody has classified auto-denies in
    either role. The partition is **membership, not a strength order** — no ranking is invented (design
    #30 §4.3).

    The remaining conjuncts are the §11 line 312-314 bindings: ``permits_individual_exceedance`` is
    **negative** polarity (clears only on ``is False``), while ``units_exact`` / ``window_inside_bound``
    / ``uncertainty_treated`` are **positive** (clear only on ``is True``); an unknown ``None`` denies on
    both sides.

    **Closes no STM-EV** (STM-EV-005 substrate; the evaluator differential, parser-drift and
    threshold-weakening rejection is §30 gate 4, ``+Security`` runtime).

    Args:
        bound: The approved bound binding (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the implemented semantics exactly preserve the approved bound.
    """
    if bound is None:
        return False
    approved = bound.approved_bound_kind
    implemented = bound.implemented_as_kind
    if approved is None or implemented is None:
        return False
    if approved in HARD_BOUND_KINDS:
        # §11 line 314 — a hard bound survives only as the *same* hard bound.
        if implemented not in HARD_BOUND_KINDS or implemented is not approved:
            return False
    elif approved in WEAK_BOUND_KINDS or approved in NEUTRAL_BOUND_KINDS:
        # A classified non-hard bound still has to survive exactly; reinterpreting a PERCENTILE as a
        # RANGE is a semantics change too (§11 line 312 "the policy binds ... units, states").
        if implemented is not approved:
            return False
    else:
        # Whitelist residue: an unclassified (future) member is never admitted.
        return False
    if bound.permits_individual_exceedance is not False:
        return False
    if bound.units_exact is not True:
        return False
    if bound.window_inside_bound is not True:
        return False
    return bound.uncertainty_treated is True


def numeric_result_not_conforming_by_default(
    evaluation: MonitorEvaluation | None,
) -> bool:
    """Whether a malformed numeric input was kept out of ``CONFORMING`` (§11 line 316; **yolk 2 (c)**).

    §11 line 316 verbatim: "**Unknown numeric input, NaN, infinity, overflow, underflow,
    non-convergence, unit mismatch, parser differential, missing sample, insufficient history, or
    evaluator disagreement yields ``UNKNOWN`` or a restrictive result. It never yields ``CONFORMING`` by
    default.**"

    The contrapositive is the gate: a ``CONFORMING`` result requires
    :attr:`~tos.stm.vocabulary.NumericInputState.WELL_FORMED`. Any of the eleven malformed states
    (:data:`~tos.stm.vocabulary.MALFORMED_NUMERIC_STATES`) coexisting with ``CONFORMING`` denies; a
    malformed input must land on ``RESTRICTED`` / ``NON_CONFORMING`` / ``UNKNOWN``.

    An evaluation with **no** result or **no** numeric state denies outright: an unjudgeable record is
    not a passing one (fail-closed, design #30 §4.2). Comparisons are explicit ``is`` identity —
    ``if evaluation.result:`` is structurally impossible here anyway (``__bool__`` raises).

    **Closes no STM-EV** (STM-EV-005 substrate; the differential test that *detects* a parser drift is
    §30 gate 4, ``+Security`` runtime).

    Args:
        evaluation: The monitor evaluation (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the evaluation does not claim ``CONFORMING`` on a non-well-formed numeric input.
    """
    if evaluation is None:
        return False
    if evaluation.result is None or evaluation.numeric_input_state is None:
        return False
    if evaluation.result is AggregateConformanceResult.CONFORMING:
        return evaluation.numeric_input_state is NumericInputState.WELL_FORMED
    return True


def deterministic_evaluation_bound_integrity(
    evaluations: tuple[MonitorEvaluation, ...],
    bounds: tuple[ApprovedBoundBinding, ...],
    required_evaluation_keys: frozenset[tuple[str, str]],
    applicable_bound_refs: frozenset[str],
) -> bool:
    """Whether evaluation is deterministic and bound semantics intact (STM-EV-005 **yolk 2**; §11; §12).

    The four-part composite (design #30 §5.2): **(0)** presence and ∅ both-ways, **(a)**
    :func:`evaluation_is_deterministic`, **(b)** :func:`bound_integrity_preserved` for every submitted
    bound, **(c)** :func:`numeric_result_not_conforming_by_default` for every evaluation.

    **(0) is the C2 seal.** Without it the composite would return a vacuous ``True`` on a
    completely-empty input — an "empty query proves safety" fail-open that STM-INV-004 line 171 names
    explicitly, and that would have been a self-violation of this very contract's yolk. The gate is
    both-ways:

    * ``required_evaluation_keys`` empty **and** corpus empty ⇒ a valid explicit-empty (no required
      monitor for this scope); rejecting it would over-seal (design #26 MAJOR-1 lesson);
    * ``required_evaluation_keys`` non-empty **and** corpus empty ⇒ **deny**;
    * ``required_evaluation_keys`` empty **and** corpus non-empty ⇒ **deny** as surplus;
    * every required key must actually be present in the corpus.

    It also carries the **M4 binding closure**: every ``bound_binding_digest`` an evaluation references
    must be among the **submitted** bounds, and every applicable bound reference must be submitted too.
    Without it an evaluator could be judged under a bound it never disclosed — the favorable-subset
    bypass (§9 line 292's no-favorable-union rule applied to bounds, the #22 isomorph). A submitted bound
    nothing references is harmless surplus.

    Any evaluation or bound missing its identifying digests denies: an unattributable record cannot
    establish determinism (fail-closed).

    **Closes no STM-EV.** STM-EV-005 is ``EV-L1/3+Security``: the ``/3`` integration axis plus the whole
    ``+Security`` evaluator-differential / parser-drift / threshold-weakening resistance axis remain
    (§30 gate 4). Authoring is not evidence (ADR §27 line 594).

    Args:
        evaluations: The monitor-evaluation corpus.
        bounds: The submitted approved bound bindings.
        required_evaluation_keys: The ``(evaluator_digest, canonical_input_digest)`` pairs policy
            requires for this scope (``frozenset()`` ⇒ no required monitor).
        applicable_bound_refs: The ``bound_binding_digest`` values applicable to this scope.

    Returns:
        ``True`` iff presence, determinism, bound integrity and numeric fail-closure all hold.
    """
    # --- (0) presence + ∅ both-ways (design #30 §5.2 (0), C2) ---
    # NOTE (deliberate redundancy): this first arm is *provably equivalent* to the required-key subset
    # check below — on the only inputs it fires for (non-empty required set, empty corpus) the observed
    # key set is empty, so `required_evaluation_keys <= observed_keys` already denies. It is kept
    # because it is the C2 seal's plain statement of "an empty query proves nothing" (STM-INV-004 line
    # 171) at the top of the gate, where a reader looking for the ∅ behaviour will find it.
    if required_evaluation_keys and not evaluations:
        return False  # "an empty query proves safety" — STM-INV-004 line 171
    if evaluations and not required_evaluation_keys:
        return False  # surplus corpus against no requirement — both ways
    observed_keys: set[tuple[str, str]] = set()
    for evaluation in evaluations:
        if (
            evaluation.evaluator_digest is None
            or evaluation.canonical_input_digest is None
            or evaluation.bound_binding_digest is None
        ):
            return False  # unattributable record — fail-closed
        observed_keys.add(
            (evaluation.evaluator_digest, evaluation.canonical_input_digest)
        )
    if not required_evaluation_keys <= observed_keys:
        return False
    submitted_bound_refs: set[str] = set()
    for bound in bounds:
        if bound.bound_binding_digest is None:
            return False  # unattributable bound — fail-closed
        submitted_bound_refs.add(bound.bound_binding_digest)
    if not applicable_bound_refs <= submitted_bound_refs:
        return False
    referenced = {
        evaluation.bound_binding_digest
        for evaluation in evaluations
        if evaluation.bound_binding_digest is not None
    }
    if not referenced <= submitted_bound_refs:
        return False  # judged under an undisclosed bound — the favorable-subset bypass

    # --- (a) relational determinism ---
    if not evaluation_is_deterministic(evaluations):
        return False
    # --- (c) per-evaluation numeric fail-closure ---
    for evaluation in evaluations:
        if not numeric_result_not_conforming_by_default(evaluation):
            return False
    # --- (b) per-bound integrity ---
    return all(bound_integrity_preserved(bound) for bound in bounds)


# ===========================================================================
# supporting §5 predicates
# ===========================================================================


def conformance_requires_complete_current_valid(
    snapshot: ContinuousConformanceSnapshot | None,
) -> bool:
    """Whether a ``CONFORMING`` snapshot really is complete, current and valid (§12 line 335).

    §12 line 335 verbatim: "``CONFORMING`` requires **every** required item to be current, complete, and
    independently valid under policy. ``RESTRICTED``, ``NON_CONFORMING``, or ``UNKNOWN`` denies dependent
    new risk for the affected scope."

    The construction validator already makes a malformed ``CONFORMING`` snapshot unconstructable; this
    is the **second layer** that re-derives the fact for a ``model_construct`` bypass (design #30 §2.3,
    the #20 lesson). A non-``CONFORMING`` snapshot passes this predicate as long as it is
    non-authorizing — the predicate judges the *honesty of a CONFORMING claim*, not the desirability of
    the result.

    **Even a ``CONFORMING`` result grants nothing** (§1 line 25; all-false authority), which is asserted
    here for every snapshot regardless of result.

    Args:
        snapshot: The Continuous Conformance Snapshot (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the snapshot is non-authorizing and any ``CONFORMING`` claim is structurally backed.
    """
    if snapshot is None:
        return False
    if not all_false_monitoring_authority(snapshot.authority_effect):
        return False
    if snapshot.aggregate_result is None:
        return False  # an unjudged snapshot proves nothing (fail-closed)
    if snapshot.aggregate_result is not AggregateConformanceResult.CONFORMING:
        return True
    for name in (
        "snapshot_id",
        "snapshot_generation",
        "monitor_generation",
        "policy_digest",
        "critical_telemetry_manifest_digest",
        "coverage_manifest_digest",
        "scope",
        "owner_epoch",
    ):
        if getattr(snapshot, name) is None:
            return False
    if not snapshot.monitor_results:
        return False  # §12 line 329 binds "every required monitor and result"
    if snapshot.source_continuity_present is not True:
        return False  # §12 line 330, positive polarity
    if snapshot.active_violations or snapshot.active_unknowns:
        return False
    return not (snapshot.active_gaps or snapshot.delivery_failures)


def gap_is_restrictive_not_exemption(gap: SafetyMonitoringGap | None) -> bool:
    """Whether a Monitoring Gap is classified, non-authorizing and closed only by proof (§13 line 349).

    STM-INV-002 line 163: "Missing or unknown coverage is a **gap, not an exemption**." §13 line 349:
    "**Monitoring recovery does not close the gap by itself.** Closure requires continuity re-established
    under a new or current fenced generation, loss interval bounded, missed violations conservatively
    reconstructed, dependent state re-evaluated, evidence gaps resolved or explicitly restrictive, and
    every required owner handoff accepted."

    **Read the return value carefully.** ``True`` means the gap is a well-formed, classified,
    non-authorizing record **whose closure is positively proven**. ``False`` is the conservative side and
    covers three distinct situations that all keep the gap open and restrictive: an absent record, an
    unclassified gap kind (nothing in the §5.7 line 135 ten-kind taxonomy), an authority-bearing record,
    and — the ordinary case — a gap with no closure proof. ``closure_proof_present`` is positive polarity,
    so an unknown ``None`` keeps the gap open; there is no other clearing path, which is exactly what §13
    line 349 demands.

    **Closes no STM-EV** (STM-EV-001 / STM-EV-008 substrate; the gap-to-restriction runtime and the
    ``B_monitoring_gap_to_authority_restrict`` bound are §8 Phase-0 and ``+Security`` runtime).

    Args:
        gap: The Safety Monitoring Gap record (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the gap is classified, non-authorizing and positively proven closed.
    """
    if gap is None:
        return False
    if gap.gap_kind is None:
        return False  # unclassified — outside the §5.7 line 135 ten-kind taxonomy
    if not all_false_monitoring_authority(gap.authority_effect):
        return False
    return gap.closure_proof_present is True


def escalation_single_binding(record: AlertEscalationRecord | None) -> bool:
    """Whether an escalation record keeps its single alert binding (§5.9 line 143).

    §5.9 line 143 verbatim: an Alert Escalation Record is "bound to **exactly one** Safety Alert Record
    and one policy and Monitor Generation ... One alert may have multiple records for independent paths
    or successive escalation generations, but **records cannot be unioned, substituted, or used to narrow
    the alert scope or reset its first-observed time.**"

    Two conjuncts: the binding must be a **concrete** reference (:func:`_is_placeholder_reference`
    rejects an absent, blank or template id — an unbound record could be attached to any alert), and
    ``unioned_or_substituted`` must be positively ``False``. That second conjunct is **negative**
    polarity: ``is not False`` denies, so an unknown ``None`` denies too. The consumption *shape* is
    reused, never imported, from the iap single-use gate (``iap/predicates.py:176`` ``single_use is not
    True`` ⇒ deny) — sibling edge 0.

    **Closes no STM-EV** (STM-EV-007 substrate; ``EV-L2/3+Security`` — the delivery and escalation
    runtime is §30 gate 6).

    Args:
        record: The Alert Escalation Record (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the record is bound to exactly one alert and claims no union or substitution.
    """
    if record is None:
        return False
    if _is_placeholder_reference(record.bound_alert_id):
        return False
    return record.unioned_or_substituted is False


# ===========================================================================
# §6 predicate-only substrate — closes NO STM-EV (design #30 §6/§0.4c)
# ===========================================================================


def telemetry_semantics_exact(
    identity: CriticalTelemetryIdentity | None,
    view: TelemetrySemanticView | None,
) -> bool:
    """Whether telemetry semantics stayed exact (§10; §8 line 267; STM-INV-003 line 167; §6.1).

    STM-INV-003 line 167 verbatim: "Identity, scope, source, units, schema, meaning, derivation,
    continuity, and time basis are immutable and verified. **A consumer cannot reinterpret or silently
    default them.**" §8 line 267: "**Hash equality**, metric name, topic, label, dashboard panel, or
    source health **alone does not establish semantic equivalence.**" §10 line 300: "**Identical values
    before and after a discontinuity do not prove continuity.**" §10 line 302: "**Cross-host monotonic
    values SHALL NOT be directly subtracted** ... **Future, negative, unknown, or unbounded age cannot be
    clamped into freshness.**"

    All five coordinates are **negative** polarity and clear only on ``is False``; an unknown ``None``
    denies on every one of them.

    **Closes no STM-EV** (STM-EV-002 substrate; ``EV-L2/3+Security`` — the source-continuity, unit and
    derivation runtime is §30 gate 3).

    Args:
        identity: The telemetry semantic identity (``None`` ⇒ ``False``).
        view: The consumer's provenance / continuity view (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no reinterpretation, hash-equality claim, cross-host subtraction, false continuity
        claim or age clamping is asserted.
    """
    if identity is None or view is None:
        return False
    if identity.semantics_reinterpreted is not False:
        return False
    if identity.hash_equality_claims_equivalence is not False:
        return False
    if view.cross_host_monotonic_subtracted is not False:
        return False
    if view.identical_values_claim_continuity is not False:
        return False
    return view.age_clamped_from_unbounded is False


def absence_is_not_health(obs: SilenceObservation | None) -> bool:
    """Whether observed silence was kept out of a health claim (§1 line 23; STM-INV-004 line 171; §6.2).

    STM-INV-004 line 171 verbatim: "**No alert, repeated health heartbeat, quiet time, successful scrape,
    empty query, or green dashboard proves safety, completeness, currentness, or containment.**" §1 line
    23: "Dashboard labels, aggregate scores, heartbeats, service health, cached green state, elapsed
    quiet time, page acknowledgement, or absence of a new alert are **not proof** that the monitored fact
    is safe or current."

    **Unconditional (design #30 MINOR-2).** The gate is ``treated_as_healthy is False`` regardless of
    which — or whether any — silence marker is set. The invariant is about the *inference*, not about the
    kind of silence, so making the gate conditional on a marker would create a branch in which no silence
    is recorded and the health claim goes unchecked. The five markers therefore take no part in the
    judgement (they are explicitly deferred, :data:`MARKER_FIELDS`).

    ``treated_as_healthy`` is **negative** polarity: ``is not False`` denies, so both an asserted health
    claim (``True``) and an unknown one (``None``) deny.

    **Closes no STM-EV** (STM-EV-003 substrate; ``EV-L2/3`` — the runtime silence judgement is
    component-fault level).

    Args:
        obs: The silence observation (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the observation positively asserts the silence was not treated as health.
    """
    if obs is None:
        return False
    return obs.treated_as_healthy is False


def unknown_is_restrictive(state: MonitoringUnknownState | None) -> bool:
    """Whether every UNKNOWN monitoring axis is clear (§13; STM-INV-005 line 175; §6.3).

    STM-INV-005 line 175 verbatim: "**Missing, stale, conflicting, ambiguous, discontinuous,
    mixed-generation, or unverifiable monitoring state blocks dependent new risk and expands to the
    greatest credible scope.**"

    All seven axes are **negative** polarity and are consumed as a group through
    :data:`~tos.stm.state.MonitoringUnknownState.UNKNOWN_FIELDS`: a single axis that is ``is not False``
    — asserted (``True``) **or unknown (``None``)** — denies. The greatest-credible scope expansion
    itself is an injected coordinate (§13 line 347 is cur / egress / sir-owned, design #30 §3.5).

    **Closes no STM-EV** (STM-EV-003 substrate; ``EV-L2/3``).

    Args:
        state: The UNKNOWN monitoring state (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every one of the seven STM-INV-005 axes is positively ``False``.
    """
    if state is None:
        return False
    return all(
        getattr(state, name) is False for name in MonitoringUnknownState.UNKNOWN_FIELDS
    )


def common_mode_is_not_independence(disc: CommonModeDisclosure | None) -> bool:
    """Whether a common mode was kept out of an independence claim (§14; STM-INV-006 line 179; §6.4).

    STM-INV-006 line 179 verbatim: "**Shared sources, collectors, parsers, clocks, datastores, networks,
    administrators, identities, deployments, notification routes, or vendors do not count as independent
    paths.**" §14 line 355 names the seventeen shared dependencies
    (:data:`~tos.stm.vocabulary.SHARED_DEPENDENCY_ANCHOR`). §14 line 359: "A monitor SHALL NOT approve
    its own omission, **validate its own source continuity using only its output**, or **treat its own
    health endpoint as proof** of semantic correctness." §14 line 357: "remaining common mode is
    **recorded as residual risk**".

    ``claimed_independent`` is a **marker** read only in combination: a non-empty ``shared_dependencies``
    together with an independence claim denies. The two §14 line 359 self-proof coordinates are
    **negative** polarity and the §14 line 357 disclosure is **positive**.

    The effective-control analysis proper — whether two nominally distinct paths really are independent —
    is hag-owned and ``+Security``; this predicate judges only the disclosure structure.

    **Closes no STM-EV** (STM-EV-004 substrate; ``EV-L2/3+Security``).

    Args:
        disc: The common-mode disclosure (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no independence is claimed over a shared dependency and no self-proof is asserted.
    """
    if disc is None:
        return False
    if disc.shared_dependencies and disc.claimed_independent is True:
        return False
    if disc.self_health_as_proof is not False:
        return False
    if disc.validates_own_continuity_by_own_output is not False:
        return False
    return disc.residual_common_mode_disclosed is True


def suppression_cannot_suppress_safety(sup: MonitoringSuppression | None) -> bool:
    """Whether a suppression left safety intact (§5.11 line 151; §15; STM-INV-008 line 187; §6.5).

    §5.11 line 151 verbatim: a Monitoring Suppression "**SHALL NOT disable source collection, invariant
    evaluation, restrictive signaling, evidence, generation advancement, or final-egress denial** for a
    Critical condition" — six prohibitions, consumed as a group through
    :data:`~tos.stm.state.MonitoringSuppression.DISABLE_FIELDS`, all **negative** polarity. STM-INV-008
    line 187: "Maintenance, inhibition, mute, deduplication, test, or operator acknowledgement cannot
    disable a required restrictive path, hide an unresolved Critical state, or create permission."

    A second, independent axis is the §15 line 367-376 eight preserved-active functions
    (:data:`~tos.stm.vocabulary.SUPPRESSION_PRESERVED_FUNCTIONS`), which the suppression's declared
    ``preserved_functions`` is **floored** against — it may preserve more, never fewer. Monitoring Gap
    creation lives on that axis, not among the six prohibitions.

    Finally, §15 line 365 / §21 line 458 make ``EXPIRED`` and ``UNKNOWN`` automatically restrictive and
    unsuppressed, so a suppression in either state — or with no state at all — denies here. **The gate
    is written as a positive whitelist** (:data:`~tos.stm.vocabulary.IN_FORCE_SUPPRESSION_STATES`)
    rather than as the contract's §6.5 denylist phrasing: on today's four-member enum the two are
    exactly equivalent, and the whitelist additionally auto-denies a future lifecycle member nobody has
    classified — a conservative strengthening inside the contract, never a change of verdict on any
    input the contract specifies (the #25 RLP MAJOR-1 denylist-leak lesson).

    A suppression approval "is **not** a Safety Deviation Decision unless ADR-002-026 separately
    authorizes" (§15 line 365); that deviation verdict is a wdr-owned injected coordinate, re-authored
    not at all (design #30 §3.5).

    **Closes no STM-EV** (STM-EV-006 substrate; ``EV-L2/3+Security`` — approval and expiry are runtime,
    §30 gate 6).

    Args:
        sup: The Monitoring Suppression (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the suppression disables none of the six, preserves all eight, and is in force.
    """
    if sup is None:
        return False
    for name in MonitoringSuppression.DISABLE_FIELDS:
        if getattr(sup, name) is not False:
            return False
    if not sup.preserved_functions >= SUPPRESSION_PRESERVED_FUNCTIONS:
        return False
    return sup.lifecycle_state in IN_FORCE_SUPPRESSION_STATES


def alert_state_is_orthogonal(vec: AlertStateVector | None) -> bool:
    """Whether the eight alert-state axes stayed independent (§16 line 388; STM-INV-009 line 191; §6.6).

    STM-INV-009 line 191 verbatim: "Detection, delivery, acknowledgement, escalation, containment,
    incident lifecycle, recovery, and economic finality are **independent states. Advancement of one
    never implies another.**" §16 line 388: "Recipient acknowledgement means only that the exact alert
    was received by an authenticated effective person or approved automated endpoint. **It is not
    containment, remediation, broker finality, incident closure, recovery readiness, or re-arm.**"

    Both coordinates are **negative** polarity and clear only on ``is False``.

    **Note the name.** This predicate is a *judgement about* alert state, not an alerting action: stm
    creates, delivers, acknowledges and escalates nothing (design #30 §4.1 — the void-canary asserts no
    executable ``deliver`` / ``escalate`` / ``page`` function exists anywhere in the package).

    **Closes no STM-EV** (STM-EV-007 substrate; ``EV-L2/3+Security``).

    Args:
        vec: The alert state vector (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff neither an acknowledgement-implies-containment nor a cross-axis implication is
        asserted.
    """
    if vec is None:
        return False
    if vec.ack_implies_containment is not False:
        return False
    return vec.advance_of_one_implies_another is False


def loss_preserves_negative_facts(vec: AlertStateVector | None) -> bool:
    """Whether loss and backpressure preserved adverse facts (§16 line 390; STM-INV-010 line 195; §6.6).

    STM-INV-010 line 195 verbatim: "**Overflow, queue pressure, retry, correlation, deduplication, or
    delivery failure cannot preferentially discard adverse state or reset elapsed detection and
    escalation time.**" §21 line 455: "queue overflow or backpressure -> **preserve adverse records;
    restrict; never sample them away**." §16 line 390: a failure "**preserves the original deadline**".

    Both coordinates are **negative** polarity and clear only on ``is False``; an unknown ``None`` denies.

    **Closes no STM-EV** (STM-EV-007 substrate; ``EV-L2/3+Security`` — the backpressure runtime is §30
    gate 6).

    Args:
        vec: The alert state vector (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no adverse record was dropped and no elapsed time was reset.
    """
    if vec is None:
        return False
    if vec.adverse_record_dropped is not False:
        return False
    return vec.elapsed_time_reset is False


def handoff_is_non_authorizing(signal: RestrictiveMonitoringSignal | None) -> bool:
    """Whether a restrictive monitoring signal stays non-authorizing (§17 line 402; STM-INV-011; §6.7).

    §17 line 402 verbatim: "**No monitor or alert may downgrade an existing fence or incident, select a
    narrower scope, clear a local latch, or publish ``NO_INCIDENT``.** Conflicting monitoring and
    incident state resolves to the more restrictive state." §5.10 line 147: a Restrictive Monitoring
    Signal "can only preserve or reduce future authority ... **It cannot clear a restriction or create
    permission.**" STM-INV-011 line 199: "Monitoring may request restriction and incident evaluation
    **only**."

    The four §17 line 402 prohibitions are consumed as a group through
    :data:`~tos.stm.state.RestrictiveMonitoringSignal.PROHIBITION_FIELDS`, all **negative** polarity,
    alongside the all-false authority block.

    **``publishes_no_incident`` is a prohibition flag, not a token** (the #28 SIR phantom lesson): §17
    line 402 forbids publishing ``NO_INCIDENT``; it does not give stm a ``NO_INCIDENT`` vocabulary
    member. §17 line 400 keeps materiality, severity, greatest-credible incident scope, Incident
    Generation, the active incident set, containment, shutdown, handoff and closure with ADR-002-027 —
    re-authored here not at all. This is the **forward seam** sir already anticipates as an injected
    opaque coordinate (``sir/predicates.py:15``; ``sir/state.py:46``).

    **Closes no STM-EV** (STM-EV-008 substrate; ``EV-L2/3+Security`` — the restrictive ingress and
    incident classification are sir-owned and §30 gate 8).

    Args:
        signal: The restrictive monitoring signal (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the signal grants nothing and asserts none of the four §17 line 402 prohibitions.
    """
    if signal is None:
        return False
    if not all_false_monitoring_authority(signal.authority_effect):
        return False
    return all(
        getattr(signal, name) is False
        for name in RestrictiveMonitoringSignal.PROHIBITION_FIELDS
    )


def broker_finality_unchanged(tokens: BrokerFinalityTokens | None) -> bool:
    """Whether monitoring left broker finality untouched (§19 line 429; STM-INV-013 line 207; §6.8).

    §19 line 429 verbatim: "**Missing broker ACK remains possible acceptance. Cancel ACK is not Final
    Quantity Proof.** A lost or failed monitor covering broker evidence expands UNKNOWN and **preserves
    the worst credible economic effect in RCL capacity.** Capacity availability cannot turn unknown
    monitoring state into permission." §19 line 427: a monitor result "cannot set an order to rejected, a
    position to zero, an obligation to settled, or a capacity commitment to released."

    All three coordinates are **negative** polarity and clear only on ``is False``.

    The worst-credible-effect *computation* is rcl-owned and ``+Broker`` — stm does no capacity
    arithmetic, which is why the **rcl edge is 0** (design #30 §3.5/§10.2-⑥).

    **Closes no STM-EV** (STM-EV-010 substrate; ``EV-L2/3+Broker``).

    Args:
        tokens: The broker-finality tokens (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no missing-ACK inference, Cancel-ACK-as-FQP claim or capacity release is asserted.
    """
    if tokens is None:
        return False
    if tokens.missing_ack_treated_as_non_acceptance is not False:
        return False
    if tokens.cancel_ack_treated_as_fqp is not False:
        return False
    return tokens.unknown_effect_capacity_released is False


def economic_effect_outlives_monitor_state(
    authority: AllFalseMonitoringAuthority | None,
) -> bool:
    """Whether expiry left economic effect intact (§19 line 431; STM-INV-013 line 207; §6.8).

    §19 line 431 verbatim: "Policy, telemetry, snapshot, alert, acknowledgement, suppression, page,
    incident, workflow, credential, or session expiry **only restricts future authority. It never
    expires existing economic effect, protective obligation, external activity, or capacity
    commitment.**"

    **Consumed as an authority *shape*, never as an expiry flag (design #30 §6.8 — the #26 WDR v1.2
    lesson).** An earlier design generation read an ``is_expired`` field directly and treated its
    ``False`` as a clear, which inverts the invariant: expiry is not the thing being cleared. The
    correct L1 realization is that whatever the monitoring state's expiry, the artifact still creates no
    capacity and establishes no broker finality — so the two authority flags that *would* be the vehicle
    for erasing an economic effect are the ones asserted false.

    **Closes no STM-EV** (STM-EV-010 substrate; ``EV-L2/3+Broker`` — quantifying broker finality is
    ``+Broker``).

    Args:
        authority: The monitoring artifact's authority block (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the artifact creates no capacity and establishes no broker finality.
    """
    if authority is None:
        return False
    if authority.creates_capacity is not False:
        return False
    return authority.establishes_broker_finality is False


def evidence_and_status_honest(dash: DashboardStatusView | None) -> bool:
    """Whether a dashboard status stayed honest (§23 line 499; STM-INV-014 line 211; §6.9).

    §23 line 499 verbatim: "Dashboards SHALL distinguish at minimum ``CURRENT_CONFORMING``,
    ``RESTRICTED``, ``NON_CONFORMING``, ``UNKNOWN``, ``STALE``, ``GAP``, and ``UNVERIFIED``. **Rendering
    failures or unknown state SHALL NOT default to green.**" STM-INV-014 line 211: "Metrics, logs,
    alerts, dashboards, pages, audit, replay, reports, and postmortems **cannot replace a preventive or
    restrictive enforcement point**."

    Two independent gates. First, the no-green-default gate: a rendering failure **or** an unknown state
    (either **marker** asserted ``True``) coexisting with a ``CURRENT_CONFORMING`` token denies. Second,
    the negative-polarity judgement ``defaulted_to_green is False``, which denies on an unknown ``None``
    too. A missing status token denies — an unrendered view is not a green one.

    The evidence-is-not-prevention half of STM-INV-014 is carried structurally instead, by
    :attr:`~tos.stm._base.AllFalseMonitoringAuthority.satisfies_preventive_control`: no monitoring
    artifact can mark a preventive control satisfied (design #30 §12 INV-014 row).

    **Closes no STM-EV** (STM-EV-012 substrate; ``EV-L2/3+Security`` — evidence custody is
    ADR-002-016-owned).

    Args:
        dash: The dashboard status view (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no failed / unknown render is shown as ``CURRENT_CONFORMING`` and no green default
        is asserted.
    """
    if dash is None:
        return False
    if dash.status_token is None:
        return False
    if (dash.rendering_failed is True or dash.state_unknown is True) and (
        dash.status_token is DashboardStatusToken.CURRENT_CONFORMING
    ):
        return False
    return dash.defaulted_to_green is False


def recovery_revives_nothing(inputs: MonitoringRecoveryInputs | None) -> bool:
    """Whether monitoring recovery revived nothing (§24 line 511; STM-INV-015 line 215; §6.9).

    §24 line 511 verbatim: "Prior ``CONFORMING`` snapshots, alert acknowledgements, suppressions, trial
    state, production scope, authority, capabilities, or pages **are not reusable. Recovery readiness is
    non-authorizing and a fresh ADR-002-007/015 governed re-arm chain remains mandatory.**"
    STM-INV-015 line 215: "**Restart, reconnect, failover, restore, replay, backlog drain, source
    recovery, alert delivery, operator return, or quiet time cannot restore prior authority or
    automatically re-arm.**"

    **Structurally derived gate (design #30 §2.4, OQ1).** The nine recorded recovery-event markers
    (:data:`~tos.stm.state.MonitoringRecoveryInputs.RECOVERY_MARKER_FIELDS`) are read as a
    **disjunction**: once *any* recovery event is recorded, all four
    :data:`~tos.stm.state.MonitoringRecoveryInputs.NON_REVIVAL_FIELDS` — every one **negative** polarity
    — must be positively ``False``. The gate is armed by the observed structure, never by a
    self-reported "a recovery happened" flag.

    **The disjunction arms on ``is not False``, not on ``is True``.** Disarming requires every one of
    the nine markers to be a **positive disclaimer** (``is False``); a marker that is unknown (``None``)
    arms the gate exactly like a recorded event. Reading the markers with ``is True`` would mean a
    record that simply reports no markers at all — the default shape — bypasses the gate entirely, so a
    record whose four revival self-reports were all ``True`` would pass: the marker-drop fail-open, the
    #20 HAG isomorph. Only a fully disclaimed marker set means "nothing to revive", which is what
    STM-INV-005 line 175 ("Missing ... monitoring state blocks dependent new risk") requires.

    The Recovery Barrier itself is ADR-002-017 / sbr-owned and the fresh re-arm chain is
    ADR-002-007/015 / liveauth / hag-owned; both are injected, re-authored not at all (design #30 §3.5).

    **Closes no STM-EV** (STM-EV-012 substrate; ``EV-L2/3+Security``).

    Args:
        inputs: The monitoring recovery inputs (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no recorded recovery event coexists with a revival, resumption, scope restoration
        or automatic re-arm.
    """
    if inputs is None:
        return False
    # A marker that is `True` **or unknown (`None`)** arms the gate: a record whose nine markers are all
    # unreported says nothing about whether a recovery happened, and reading that silence as "no
    # recovery" would let a record whose four revival self-reports are all `True` pass untouched
    # (the #20 HAG malformed-drop isomorph). Only a positively disclaimed marker set — every one
    # `is False` — means "nothing to revive"; STM-INV-005 line 175 makes the unknown restrictive.
    recovery_observed = any(
        getattr(inputs, name) is not False
        for name in MonitoringRecoveryInputs.RECOVERY_MARKER_FIELDS
    )
    if not recovery_observed:
        return True
    return all(
        getattr(inputs, name) is False
        for name in MonitoringRecoveryInputs.NON_REVIVAL_FIELDS
    )


# ===========================================================================
# §6b not-Phase-1 thin models — closes NO STM-EV (STM-EV-009 / STM-EV-011)
# ===========================================================================


def restriction_ordered_before_capability_claim(
    ordering: SendRaceOrdering | None,
) -> bool:
    """Whether a gap or restriction provably precedes the capability claim (§18 line 421).

    §18 line 421 verbatim: "**If a gap or restriction is ordered before the capability claim, the send
    is denied.**" REUSES ``tos.ordering.compare_order`` (no re-authored order): ``True`` means the
    restriction **provably** precedes the claim and the send is denied.

    **This predicate answers one question only — "is the restriction provably first?" — and its
    ``False`` is not a clearance (design #30 §4.3 three-value discipline, the #28 MAJOR-2 lesson).** An
    unknown, equal or ambiguous ordering returns ``False`` here because nothing was *proven*, **not**
    because the send is admissible; the ordering-unprovable case is answered separately and
    conservatively by :func:`attempt_potentially_live`, which returns ``True`` on exactly those inputs. A
    consumer reading this ``False`` as "the send may proceed" would invert §18 line 421. Send
    admissibility belongs to the egress final-egress decision (design #30 §3.5), never here.

    §18 line 419: "Cached green state, TTL, heartbeat, dashboard reachability, alert acknowledgement,
    last-known generation, eventual consistency, or absence of a negative event **is not proof**." The
    cache-free currentness protocol, the ``B_monitoring_gap_to_egress_deny`` bound and the deny-first
    latch are ``+Security`` runtime and egress-owned (design #30 §6b).

    **Closes no STM-EV** (STM-EV-009 substrate; ``EV-L3+Security``).

    Args:
        ordering: The §18 send-race ordering permutation (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the restriction provably precedes the capability claim.
    """
    if ordering is None:
        return False
    if ordering.restrict_event is None or ordering.capability_claim_event is None:
        return False
    return (
        compare_order(ordering.restrict_event, ordering.capability_claim_event)
        is Ordering.BEFORE
    )


def attempt_potentially_live(ordering: SendRaceOrdering | None) -> bool:
    """Whether an attempt racing a monitoring invalidation stays potentially live (§18 line 421).

    §18 line 421 verbatim: "**If ordering between a material monitoring invalidation and first
    broker-directed byte cannot be proven, the attempt remains potentially live, capacity-covered, and
    ineligible for blind retry.** Monitoring success never overrides another denial or creates a
    Transmission Capability."

    ``True`` means the attempt remains potentially live and capacity-covered. **The model demands a
    positive proof to clear and treats every unproven ordering as a race** — three distinct states, never
    folded into one (design #30 §4.3):

    * an absent record is potentially live outright — nothing was proven about anything;
    * **a recorded first broker-directed byte** is potentially live outright, whatever the ordering: if
      a byte reached the wire at all, the deny cannot have taken effect before it, and §19 line 429
      keeps "Missing broker ACK remains possible acceptance". This is a strictly conservative addition —
      it only ever adds a denial, never clears one the ordering rule would have kept live;
    * an ``ordering_provable`` that is not positively ``True`` is potentially live — positive polarity,
      so an unknown ``None`` lands here, which is the literal §18 line 421 trigger "ordering ... cannot
      be proven";
    * the residual clearing case is a provable ``RESTRICT < CAPABILITY_CLAIM`` — the send was denied
      before it happened (:func:`restriction_ordered_before_capability_claim`).

    Requiring the positive proof rather than excluding the known-bad orderings is what keeps an
    equal-generation race (which ``compare_order`` reports as ``AMBIGUOUS``, i.e. not ``BEFORE``) on the
    conservative side. The worst-credible capacity coverage is rcl-owned and ``+Broker`` (**rcl edge
    0**); the no-blind-retry enforcement is egress / action-flow owned (design #30 §6b).

    **Closes no STM-EV** (STM-EV-009 substrate; ``EV-L3+Security``).

    Args:
        ordering: The §18 send-race ordering permutation (``None`` ⇒ ``True``, conservatively).

    Returns:
        ``True`` iff the attempt must be treated as potentially live and capacity-covered.
    """
    if ordering is None:
        return True
    if ordering.first_byte_event is not None:
        return True  # bytes on the wire ⇒ possible acceptance (§19 line 429)
    if ordering.ordering_provable is not True:
        return True
    return not restriction_ordered_before_capability_claim(ordering)


def stale_writer_fenced(
    current_generation: int | None, writer_generation: int | None
) -> bool:
    """Whether a writer's Monitor Generation is provably superseded (§12 line 337; STM-INV-016 line 219).

    STM-INV-016 line 219 verbatim: "**Superseded monitor publishers, evaluators, manifests, dashboards,
    and consumers cannot publish or accept a prior Monitor Generation after replacement, rollback, or
    restore.**" §12 line 337: "**A stale owner is treated as potentially active until hard fencing is
    proven.**" §5.5 line 127: "Restore, rollback, failover, replacement, or policy change cannot reuse a
    superseded generation."

    REUSES ``tos.ordering.compare_order`` through
    :func:`~tos.stm.state.monitor_generation_advances`: ``True`` means the writer's generation is
    **provably** older than the current one, i.e. it is a stale writer whose output must be fenced. An
    unknown, equal or ambiguous pair returns ``False`` — **which is not a clearance**: §12 line 337 keeps
    a stale owner "potentially active **until hard fencing is proven**", so an unproven pair means the
    fence has not been established and the conservative consumer must keep treating the writer as
    possibly active. The hard fence itself is authority / egress runtime and ``+Security``.

    **Closes no STM-EV** (STM-EV-011 substrate; ``EV-L3+Security`` — compromise expansion, the partition
    matrix and failure-domain isolation are integration / adversarial L3, failuredomain / egress-owned).

    Args:
        current_generation: The current Monitor Generation ordering scalar (``None`` ⇒ ``False``).
        writer_generation: The writer's Monitor Generation ordering scalar (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the writer's generation is provably superseded by the current one.
    """
    return monitor_generation_advances(writer_generation, current_generation)
