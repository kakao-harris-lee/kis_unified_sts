"""stm injected value / input models + the ``tos.ordering`` Monitor Generation REUSE (design #30 §2.4).

Every model here is an **immutable value** (``frozen=True, extra="forbid"`` via
:class:`~tos.stm._base.FrozenModel`) with **no** independent id and **no** digest: these are the
coordinates a runtime injects into the §5 / §6 predicates, not ledger citizens (the ledger citizens are
in :mod:`tos.stm.records`). Field names use the ADR §5-§24 terms **verbatim** (spec terms = code terms,
boundary design #1 §2.4).

**Tri-state judgement coordinates (design #30 §4.3).** Every judgement coordinate is ``bool | None``,
never a bare ``bool``: a bare ``bool`` cannot express UNKNOWN, and UNKNOWN is exactly what STM-INV-005
line 175 requires to be restrictive. Each coordinate declares a polarity in
:data:`~tos.stm.predicates.POSITIVE_POLARITY_FIELDS` /
:data:`~tos.stm.predicates.NEGATIVE_POLARITY_FIELDS` (or, for a non-judgement observation record,
:data:`~tos.stm.predicates.MARKER_FIELDS`) and is normalized with ``is True`` / ``is False``. A
**negative-polarity field is never read with ``is not True``** — that admits a ``None`` and re-opens the
#18/#22/#23/#25 fail-open; its clear is ``is False``.

**Monitor Generation ordering REUSE (design #30 §3.2).** :func:`monitor_generation_advances` and
:func:`max_monitor_generation` REUSE ``tos.ordering.compare_order`` (no re-authored order) for the §5.5
monotonic Monitor Generation fence — "Restore, rollback, failover, replacement, or policy change cannot
reuse a superseded generation" — and the §12 line 337 stale-writer rule, "A stale owner is treated as
potentially active until hard fencing is proven" (STM-INV-016 line 219). stm owns the fence *meaning*;
ordering only carries the monotonic order. **A wall clock never orders — stm reads no clock**: a Monitor
Generation is an ordering identity, not wall-clock (design #30 §3.2/§8), so this package is clock-free
(the ``MAX_*_age_ms`` wall-clock ages are **injected** secondary +Security / INSTANCE bounds, design #30
§8/§10.3-4).

**Numeric-bound freedom (design #30 §8; ADR §29 OQ 12 line 674).** stm carries no numeric size /
duration / threshold constant: ``B_safety_telemetry_loss_detect`` /
``B_monitoring_gap_to_authority_restrict`` / ``B_monitoring_gap_to_egress_deny`` /
``B_critical_alert_delivery`` / ``B_alert_escalation`` / ``B_monitoring_generation_fence`` /
``MAX_critical_telemetry_age_ms`` / ``MAX_continuous_conformance_snapshot_age_ms`` /
``MAX_safety_alert_age_ms`` / ``MAX_monitoring_suppression_duration_ms`` /
``MAX_alert_acknowledgement_age_ms`` are all **injected** opaque Profile-INSTANCE scalars, null in Phase
1 and fail-closed at the consuming predicate.

**Injected-verdict discipline (design #30 §3.5 duplication boundary).** Every sibling
owner's produced verdict / generation / digest is an **injected** coordinate: stm does **not** re-decide
any owner's business content (cur Active Currentness Vector **and the MONITORING dimension's
completeness judgement**, spg Safety Monitoring Policy activation + Hard Safety Envelope, rlp EV-L6
demotion, sir Incident Generation + incident classification, egress final-egress enforcement + credential
/ route confinement, evidence custody / causal chain / gap, authority Safety Authority / HALT, liveauth
Live Authorization, rcl capacity mutation + worst-credible effect, protective Protective Action
Controller, time Trustworthy Time, hag Effective Principal, wdr Non-Waivable Boundary, and the sibling-owned
-029 release-lineage / compromise coordinates) — it consumes the produced fact and judges only the
coverage / determinism / bound / honesty structure.

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.stm.*`` (``_base`` / ``vocabulary``) only;
no ``shared.*``, no sibling ``tos.*`` (design #30 §0.3). Clock-free.

Regime tag: coverage-completeness / deterministic-evaluation predicate substrate only; closes **no**
STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from typing import ClassVar

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.stm._base import AllFalseMonitoringAuthority, FrozenModel
from tos.stm.vocabulary import (
    AggregateConformanceResult,
    BoundSemanticKind,
    CoverageDimension,
    DashboardStatusToken,
    NumericInputState,
    SuppressionLifecycleState,
    TelemetryCriticality,
)

__all__ = [
    "MonitorEvaluation",
    "ApprovedBoundBinding",
    "CoverageItem",
    "MonitoredAssumptionIntake",
    "CriticalTelemetryIdentity",
    "TelemetrySemanticView",
    "SilenceObservation",
    "MonitoringUnknownState",
    "CommonModeDisclosure",
    "MonitoringSuppression",
    "AlertStateVector",
    "BrokerFinalityTokens",
    "DashboardStatusView",
    "MonitoringRecoveryInputs",
    "RestrictiveMonitoringSignal",
    "SendRaceOrdering",
    "monitor_generation_advances",
    "max_monitor_generation",
]


# ===========================================================================
# yolk 2 carriers — §11 deterministic evaluation and bound semantics
# ===========================================================================


class MonitorEvaluation(FrozenModel):
    """One evaluator's judgement of one canonical input (§11; design #30 §2.4 — yolk 2 atom).

    §11 line 312 verbatim: "Monitor logic SHALL be immutable, versioned, canonical, **deterministic for
    identical inputs**, and independently testable. The policy binds the evaluator digest, exact
    inputs, units, states, thresholds, hysteresis, debounce, aggregation, windowing, uncertainty, and
    failure response."

    The **determinism key** is ``(evaluator_digest, canonical_input_digest)``; two records sharing that
    key but disagreeing on ``result`` or ``numeric_input_state`` are a non-determinism violation
    (:func:`~tos.stm.predicates.evaluation_is_deterministic`, fail-closed). The key's *own*
    determinism is delegated, not re-authored: ``canonical_input_digest`` is a
    :class:`~tos.stm._base.EVL1ProvisionalCanonicalizer` digest, so "identical inputs ⇒ identical
    digest" is already a tested core property (design #30 §3.1/§5.2).

    **Structure over parallel tuples** (design #30 §2.3): carrying the evaluation as one atom removes
    the whole defect class of parallel ``evaluator_digests`` / ``results`` tuples drifting in length or
    order.

    ``bound_binding_digest`` binds this evaluation to the :class:`ApprovedBoundBinding` it was judged
    under; yolk 2's presence gate requires every referenced binding to be **submitted**, so a favorable
    subset (judge under a bound you never disclose) cannot pass (design #30 §5.2 (0)-2, the #22
    no-favorable-union isomorph).
    """

    evaluator_digest: str | None = None
    canonical_input_digest: str | None = None
    result: AggregateConformanceResult | None = None
    numeric_input_state: NumericInputState | None = None
    bound_binding_digest: str | None = None


class ApprovedBoundBinding(FrozenModel):
    """The semantics an approved bound was implemented with (§11 line 314; STM-INV-007 line 183).

    §11 line 314 verbatim: "An approved hard maximum cannot be implemented as a percentile, average,
    best-effort target, or **window that permits an individual exceedance**. Debounce, grace,
    hysteresis, and confirmation windows **count inside the applicable detection or containment bound**
    unless the approved Verification Profile explicitly defines otherwise." STM-INV-007 line 183 adds
    "local threshold, hidden grace period, or favorable sampling rule" to the weak forms.

    Judged by :func:`~tos.stm.predicates.bound_integrity_preserved` under a **whitelist**: the
    implemented kind must be identical to the approved kind and inside a declared partition of
    :class:`~tos.stm.vocabulary.BoundSemanticKind`, so an unclassified future member auto-denies
    (design #30 §5.2 (b), M3 — the #25 RLP MAJOR-1 isomorph).

    Polarities (design #30 §4.3): ``permits_individual_exceedance`` is **negative** (clears only on
    ``is False``); ``units_exact`` / ``window_inside_bound`` / ``uncertainty_treated`` are **positive**
    (clear only on ``is True``).
    """

    bound_binding_digest: str | None = None
    approved_bound_kind: BoundSemanticKind | None = None
    implemented_as_kind: BoundSemanticKind | None = None
    #: Positive — §11 line 312 the policy binds exact units.
    units_exact: bool | None = None
    #: Negative — §11 line 314 "window that permits an individual exceedance".
    permits_individual_exceedance: bool | None = None
    #: Positive — §11 line 314 debounce / grace / hysteresis count **inside** the bound.
    window_inside_bound: bool | None = None
    #: Positive — §11 line 312 uncertainty is part of the binding.
    uncertainty_treated: bool | None = None


# ===========================================================================
# yolk 1 carriers — §9 Monitor Coverage Manifest elements
# ===========================================================================


class CoverageItem(FrozenModel):
    """One applicable obligation's coverage mapping (§9 line 275-286; design #30 §2.4 — yolk 1 element).

    The §9 line 275-286 twelve-item closure (transcribed as
    :data:`~tos.stm.vocabulary.COVERAGE_CLOSURE_ITEMS`) is carried by ``closure_1_to_12_complete``
    together with the four separately named item flags the §4.3 polarity table enumerates — item 7
    (``restrictive_response_present``), item 8 (``alert_path_present``), item 9
    (``evidence_path_present``) and item 11 (``currentness_rule_present``).

    **No self-exemption (design #30 §5.1 conjunct 3/4, C1).** ``excluded`` is a **negative**-polarity
    exclusion *claim*: the coverage tally admits only ``excluded is False`` (a positively-disclaimed
    exclusion), and any item whose ``excluded is not False`` — ``True`` **or an unknown ``None``** — is
    routed to the §9 line 290 approved-exclusion gate and denies without
    ``approved_exclusion_proof_present is True``. Reading the tally filter as ``is not True`` would let
    an ``excluded=None`` item be counted as covered without any proof, which is exactly what
    STM-INV-002 line 163 forbids: "Missing or **unknown** coverage is a gap, not an exemption."

    An item whose ``criticality`` is
    :attr:`~tos.stm.vocabulary.TelemetryCriticality.UNKNOWN_MATERIALITY` folds to ``CRITICAL`` and can
    never be excluded at all, with or without a proof (§8 line 249 "Unknown materiality is Critical").
    """

    obligation_ref: str | None = None
    monitor_ref: str | None = None
    scope_dimensions: frozenset[CoverageDimension] = frozenset()
    dependency_closure_dimensions: frozenset[CoverageDimension] = frozenset()
    #: Positive — §9 item 7 required restrictive action and containment owner.
    restrictive_response_present: bool | None = None
    #: Positive — §9 item 8 alert delivery and escalation stages.
    alert_path_present: bool | None = None
    #: Positive — §9 item 9 evidence and independent-review obligations.
    evidence_path_present: bool | None = None
    #: Positive — §9 item 11 final-egress or recovery currentness dependency.
    currentness_rule_present: bool | None = None
    #: Positive — the whole §9 line 275-286 1-12 closure for this item.
    closure_1_to_12_complete: bool | None = None
    #: **Negative** — the exclusion claim. Clears only on ``is False`` (design #30 §4.3 / C1).
    excluded: bool | None = None
    #: Positive — §9 line 290 independent-governance proof for an exclusion.
    approved_exclusion_proof_present: bool | None = None
    criticality: TelemetryCriticality | None = None


class MonitoredAssumptionIntake(FrozenModel):
    """An assumption-derived monitoring obligation (§9 line 288 patch; ADR-DEV-011 TAB-INV-006).

    §9 line 288 verbatim: the manifest "SHALL additionally enumerate assumption-derived monitoring
    obligations submitted to it — in particular each Monitored Assumption (ADR-DEV-011 TAB-INV-006): a
    recorded pre-deployment Test Assumption whose **runtime falsity would invalidate a property
    demonstrated under it**. Each submitted Monitored Assumption is a manifest item subject to the same
    1-12 closure above or an approved exclusion, admitted through the coverage-completeness discipline
    (STM-INV-002) and **never as an out-of-band addition**."

    Both flags are **positive** polarity and both are really consumed by
    :func:`~tos.stm.predicates.critical_coverage_complete_or_gap` conjunct 7's three layers: the id must
    be inside the manifest's coverage items (no out-of-band addition), the assumption must be admitted
    as a coverage item, and its runtime falsity must be declared property-invalidating — which is what
    makes it a Monitored Assumption at all rather than a silently trusted condition.

    **ADR-DEV-011's TAB-INV-001..007 is a separate invariant series** from STM-INV-001..016; the single
    crossing point is this manifest intake (design #30 §10.2-⑬). The patch that introduced it is
    explicitly EV-neutral: "no new EV ID is introduced; the Evidence Register count is unchanged".
    """

    assumption_id: str | None = None
    #: Positive — §9 line 288 "a manifest item ... never as an out-of-band addition".
    admitted_as_coverage_item: bool | None = None
    #: Positive — ADR-DEV-011 Monitored Assumption definition (§9 line 288).
    runtime_falsity_invalidates_property: bool | None = None


# ===========================================================================
# §6 predicate-only substrate carriers
# ===========================================================================


class CriticalTelemetryIdentity(FrozenModel):
    """One telemetry item's semantic identity (§8 line 256-265; §10; STM-INV-003 line 167).

    The §8 **line 256-265** ten semantic-identity groups are the ones this model carries; the two
    preceding groups at §8 line 253-254 (the ADR-002-029 release-lineage and ADR-002-030 post-trade
    bindings) are **injected opaque coordinates** owned by those ADRs and are deliberately not fields
    here (design #30 §0.4f / §3.5). All twelve are transcribed together as
    :data:`~tos.stm.vocabulary.CRITICAL_TELEMETRY_BINDING_GROUPS`, whose §7.2 (c) property re-parses the
    full §8 line 253-265 bullet list — the anchor stays complete even though the model carries the
    stm-owned subset that participates in the L1-decidable §6.1 judgement.

    Both judgement flags are **negative** polarity: STM-INV-003 line 167 "Identity, scope, source,
    units, schema, meaning, derivation, continuity, and time basis are immutable and verified. A
    consumer **cannot reinterpret or silently default them**"; §8 line 267 "Hash equality, metric name,
    topic, label, dashboard panel, or source health alone **does not establish semantic equivalence**."
    """

    telemetry_id: str | None = None
    source_identity: str | None = None
    units: str | None = None
    schema_digest: str | None = None
    derivation_lineage_digest: str | None = None
    #: Injected ADR-002-008 trustworthy-time basis (time-owned; stm reads no clock).
    trustworthy_time_basis: str | None = None
    continuity_fact: str | None = None
    criticality: TelemetryCriticality | None = None
    #: **Negative** — §10 line 302 / STM-INV-003 line 167 no reinterpretation or silent defaulting.
    semantics_reinterpreted: bool | None = None
    #: **Negative** — §8 line 267 hash equality alone is not semantic equivalence.
    hash_equality_claims_equivalence: bool | None = None


class TelemetrySemanticView(FrozenModel):
    """A consumer's provenance / continuity view of telemetry (§10 line 300-302; STM-INV-003).

    All three flags are **negative** polarity, each transcribing one §10 prohibition verbatim:

    * §10 line 302 "**Cross-host monotonic values SHALL NOT be directly subtracted.**"
    * §10 line 300 "**Identical values before and after a discontinuity do not prove continuity.**"
    * §10 line 302 "**Future, negative, unknown, or unbounded age cannot be clamped into freshness.**"
    """

    #: **Negative** — §10 line 302 cross-host monotonic non-subtraction.
    cross_host_monotonic_subtracted: bool | None = None
    #: **Negative** — §10 line 300 identical values do not prove continuity.
    identical_values_claim_continuity: bool | None = None
    #: **Negative** — §10 line 302 unbounded age cannot be clamped into freshness.
    age_clamped_from_unbounded: bool | None = None


class SilenceObservation(FrozenModel):
    """An observation of monitoring silence (§1 line 23; STM-INV-004 line 171; §6.2 carrier).

    STM-INV-004 line 171 verbatim: "**No alert, repeated health heartbeat, quiet time, successful
    scrape, empty query, or green dashboard proves safety**, completeness, currentness, or containment."

    **One judgement field, five deliberate markers (design #30 §2.4 / §4.3 marker list, OQ1).**
    ``treated_as_healthy`` is the **sole** judgement coordinate and is **negative** polarity:
    :func:`~tos.stm.predicates.absence_is_not_health` requires ``is False`` **unconditionally**,
    regardless of which silence markers are set (design #30 MINOR-2). The five marker fields —
    ``no_alert`` / ``repeated_heartbeat`` / ``quiet_time`` / ``empty_query`` / ``green_dashboard`` —
    record *which* silence a runtime observed; they are **explicitly deferred** and take no part in the
    L1 judgement (they exist for the §22 forgery / runtime-audit axis). That deferral is registered in
    :data:`~tos.stm.predicates.MARKER_FIELDS` and asserted by the §7.2 (a) field-closure property, so it
    can never be mistaken for a forgotten consumption.
    """

    #: The §7.2 (a) marker group: recorded silence observations, **not** judgement inputs (OQ1).
    SILENCE_MARKER_FIELDS: ClassVar[tuple[str, ...]] = (
        "no_alert",
        "repeated_heartbeat",
        "quiet_time",
        "empty_query",
        "green_dashboard",
    )

    #: **Negative** judgement field — §1 line 23 / STM-INV-004 line 171. The only one consumed.
    treated_as_healthy: bool | None = None
    no_alert: bool | None = None
    repeated_heartbeat: bool | None = None
    quiet_time: bool | None = None
    empty_query: bool | None = None
    green_dashboard: bool | None = None


class MonitoringUnknownState(FrozenModel):
    """The UNKNOWN monitoring-state axes (§13; STM-INV-005 line 175; §6.3 carrier).

    STM-INV-005 line 175 verbatim: "**Missing, stale, conflicting, ambiguous, discontinuous,
    mixed-generation, or unverifiable** monitoring state blocks dependent new risk and expands to the
    greatest credible scope."

    All seven fields are **negative** polarity and are consumed as a group through
    :data:`UNKNOWN_FIELDS`: a single one that is ``is not False`` — ``True`` **or an unknown ``None``**
    — denies and expands to the greatest credible scope (the scope expansion itself is an injected
    opaque coordinate; §13 line 347 is cur / egress / sir-owned).
    """

    #: The seven STM-INV-005 line 175 axes, consumed as a group by ``unknown_is_restrictive``.
    UNKNOWN_FIELDS: ClassVar[tuple[str, ...]] = (
        "telemetry_missing",
        "state_stale",
        "state_conflicting",
        "state_ambiguous",
        "state_discontinuous",
        "generation_mixed",
        "state_unverifiable",
    )

    telemetry_missing: bool | None = None
    state_stale: bool | None = None
    state_conflicting: bool | None = None
    state_ambiguous: bool | None = None
    state_discontinuous: bool | None = None
    generation_mixed: bool | None = None
    state_unverifiable: bool | None = None


class CommonModeDisclosure(FrozenModel):
    """A monitoring path's shared-dependency disclosure (§14; STM-INV-006 line 179; §6.4 carrier).

    §14 line 355 verbatim: "Shared source, collector, exporter, parser, schema registry, library, time
    source, message bus, datastore, network, region, credential, administrator, CI pipeline, deployment,
    notification provider, or policy owner **is a disclosed common mode**" (seventeen items, transcribed
    as :data:`~tos.stm.vocabulary.SHARED_DEPENDENCY_ANCHOR`). §14 line 359: "A monitor SHALL NOT approve
    its own omission, **validate its own source continuity using only its output**, or **treat its own
    health endpoint as proof** of semantic correctness."

    ``shared_dependencies`` stays an **open** ``frozenset[str]`` on purpose: §14 line 357 keeps
    "remaining common mode ... recorded as residual risk" open-ended, so the closed seventeen-item
    transcription is an honesty anchor rather than a closed enum (design #30 appendix M / OQ2).

    ``claimed_independent`` is a **marker**: it is never read alone, only in combination — a non-empty
    ``shared_dependencies`` together with ``claimed_independent is True`` denies (STM-INV-006 line 179
    "Shared sources ... **do not count as independent paths**"). The effective-control analysis proper is
    hag-owned and +Security.
    """

    shared_dependencies: frozenset[str] = frozenset()
    #: Marker — read only in combination with a non-empty ``shared_dependencies`` (§6.4).
    claimed_independent: bool | None = None
    #: Positive — §14 line 357 residual common mode is recorded.
    residual_common_mode_disclosed: bool | None = None
    #: **Negative** — §14 line 359 own health endpoint is not proof.
    self_health_as_proof: bool | None = None
    #: **Negative** — §14 line 359 own output cannot validate own continuity.
    validates_own_continuity_by_own_output: bool | None = None


class MonitoringSuppression(FrozenModel):
    """A governed Monitoring Suppression (§5.11 line 151; §15; STM-INV-008 line 187; §6.5 carrier).

    §5.11 line 151 verbatim: a suppression "is a governed temporary change to presentation or duplicate
    notification behavior. **It SHALL NOT disable source collection, invariant evaluation, restrictive
    signaling, evidence, generation advancement, or final-egress denial** for a Critical condition" —
    six prohibitions, transcribed as
    :data:`~tos.stm.vocabulary.MONITORING_SUPPRESSION_PROHIBITIONS` and carried 1:1 by the six
    **negative**-polarity ``disables_*`` fields consumed through :data:`DISABLE_FIELDS`.

    A separate axis is the §15 line 367-376 eight preserved-active functions
    (:data:`~tos.stm.vocabulary.SUPPRESSION_PRESERVED_FUNCTIONS`), which
    :func:`~tos.stm.predicates.suppression_cannot_suppress_safety` floors ``preserved_functions``
    against — a suppression may preserve *more*, **never fewer**. Monitoring Gap creation lives on that
    axis, not among the six prohibitions.

    ``lifecycle_state`` is :class:`~tos.stm.vocabulary.SuppressionLifecycleState`: ``EXPIRED`` and
    ``UNKNOWN`` are automatically restrictive and unsuppressed (§15 line 365; §21 line 458). A
    suppression approval "is not a Safety Deviation Decision unless ADR-002-026 separately authorizes"
    (§15 line 365) — that deviation verdict is a wdr-owned injected coordinate, re-authored not at all.
    """

    #: The six §5.11 line 151 prohibitions, consumed as a group by ``suppression_cannot_suppress_safety``.
    DISABLE_FIELDS: ClassVar[tuple[str, ...]] = (
        "disables_collection",
        "disables_evaluation",
        "disables_restrictive_signaling",
        "disables_evidence",
        "disables_generation_advancement",
        "disables_final_egress_denial",
    )

    suppression_id: str | None = None
    scope: str | None = None
    purpose: str | None = None
    lifecycle_state: SuppressionLifecycleState | None = None
    #: The §15 line 367-376 functions this suppression declares still active (floored, never capped).
    preserved_functions: frozenset[str] = frozenset()
    disables_collection: bool | None = None
    disables_evaluation: bool | None = None
    disables_restrictive_signaling: bool | None = None
    disables_evidence: bool | None = None
    disables_generation_advancement: bool | None = None
    disables_final_egress_denial: bool | None = None


class AlertStateVector(FrozenModel):
    """The orthogonal alert-state axes (§16; STM-INV-009 line 191 / STM-INV-010 line 195; §6.6).

    STM-INV-009 line 191 verbatim: "Detection, delivery, acknowledgement, escalation, containment,
    incident lifecycle, recovery, and economic finality are **independent states. Advancement of one
    never implies another.**" §16 line 388: recipient acknowledgement "is not containment, remediation,
    broker finality, incident closure, recovery readiness, or re-arm." STM-INV-010 line 195: "Overflow,
    queue pressure, retry, correlation, deduplication, or delivery failure **cannot preferentially
    discard adverse state or reset elapsed detection and escalation time**."

    The eight ``*_state`` strings are opaque injected labels for the eight orthogonal axes; the four
    ``bool | None`` fields are all **negative** polarity and carry the two judgements.
    """

    detection_state: str | None = None
    delivery_state: str | None = None
    acknowledgement_state: str | None = None
    escalation_state: str | None = None
    containment_state: str | None = None
    incident_state: str | None = None
    recovery_state: str | None = None
    economic_finality_state: str | None = None
    #: **Negative** — §16 line 388 acknowledgement is not containment.
    ack_implies_containment: bool | None = None
    #: **Negative** — STM-INV-009 line 191 advancement of one never implies another.
    advance_of_one_implies_another: bool | None = None
    #: **Negative** — STM-INV-010 line 195 adverse records are never preferentially discarded.
    adverse_record_dropped: bool | None = None
    #: **Negative** — STM-INV-010 line 195 elapsed detection / escalation time is never reset.
    elapsed_time_reset: bool | None = None


class BrokerFinalityTokens(FrozenModel):
    """The broker-finality invariance axes (§19 line 429; STM-INV-013 line 207; §6.8 carrier).

    §19 line 429 verbatim: "**Missing broker ACK remains possible acceptance. Cancel ACK is not Final
    Quantity Proof.** A lost or failed monitor covering broker evidence expands UNKNOWN and **preserves
    the worst credible economic effect in RCL capacity.** Capacity availability cannot turn unknown
    monitoring state into permission."

    All three fields are **negative** polarity. The worst-credible-effect *computation* is rcl-owned and
    +Broker — stm does no capacity arithmetic, which is why the **rcl edge is 0** (design #30 §3.5).

    **Same-name / different-package note**: ``sir/state.py`` declares a ``BrokerFinalityTokens`` of its
    own for the ADR-002-027 axis. The two are independent local models on different ADRs; neither
    imports the other (sibling edge 0).
    """

    #: **Negative** — §19 line 429 missing ACK is not proof of non-acceptance.
    missing_ack_treated_as_non_acceptance: bool | None = None
    #: **Negative** — §19 line 429 Cancel ACK is not Final Quantity Proof.
    cancel_ack_treated_as_fqp: bool | None = None
    #: **Negative** — §19 line 429 UNKNOWN effect stays capacity-consuming.
    unknown_effect_capacity_released: bool | None = None


class DashboardStatusView(FrozenModel):
    """A rendered dashboard status view (§23 line 499; STM-INV-014 line 211; §6.9 carrier).

    §23 line 499 verbatim: "Dashboards SHALL distinguish at minimum ``CURRENT_CONFORMING``,
    ``RESTRICTED``, ``NON_CONFORMING``, ``UNKNOWN``, ``STALE``, ``GAP``, and ``UNVERIFIED``. **Rendering
    failures or unknown state SHALL NOT default to green.**"

    ``rendering_failed`` and ``state_unknown`` are **markers**: they trigger the no-green-default gate
    rather than being judged themselves. ``defaulted_to_green`` is the **negative**-polarity judgement
    field. :func:`~tos.stm.predicates.evidence_and_status_honest` denies whenever a marker is set while
    the token is ``CURRENT_CONFORMING``, and independently requires ``defaulted_to_green is False``.
    """

    status_token: DashboardStatusToken | None = None
    #: Marker — triggers the §23 line 499 no-green-default gate.
    rendering_failed: bool | None = None
    #: Marker — triggers the §23 line 499 no-green-default gate.
    state_unknown: bool | None = None
    #: **Negative** — §23 line 499 rendering failures / unknown state never default to green.
    defaulted_to_green: bool | None = None


class MonitoringRecoveryInputs(FrozenModel):
    """Monitoring-recovery events and their non-revival judgement (§24 line 511; STM-INV-015 line 215).

    §24 line 507 verbatim: "**Startup, restart, reconnect, failover, restore, policy activation, monitor
    deployment, source recovery, queue drain, alert acknowledgement, replay, or operator return** occurs
    behind the ADR-002-017 Recovery Barrier for the affected dependency scope." §24 line 511: "Prior
    ``CONFORMING`` snapshots, alert acknowledgements, suppressions, trial state, production scope,
    authority, capabilities, or pages are **not reusable**. Recovery readiness is non-authorizing and a
    **fresh ADR-002-007/015 governed re-arm chain remains mandatory**."

    **Nine markers structurally derive the gate, four negative fields carry the judgement (design #30
    §2.4 / OQ1).** The nine :data:`RECOVERY_MARKER_FIELDS` record *which* recovery event occurred; their
    **disjunction** is what arms the non-revival gate in
    :func:`~tos.stm.predicates.recovery_revives_nothing` — so they are genuinely consumed (structural
    derivation, not self-report), while the four :data:`NON_REVIVAL_FIELDS` are the **negative**-polarity
    judgements that must each be positively ``False`` once any marker is present.
    """

    #: The nine §24 line 507 recovery-event markers whose disjunction arms the non-revival gate.
    RECOVERY_MARKER_FIELDS: ClassVar[tuple[str, ...]] = (
        "restart",
        "reconnect",
        "failover",
        "restore",
        "queue_drain",
        "alert_ack",
        "replay",
        "operator_return",
        "quiet_time",
    )
    #: The four §24 line 511 non-revival judgement fields (all negative polarity).
    NON_REVIVAL_FIELDS: ClassVar[tuple[str, ...]] = (
        "revived_prior_authority",
        "resumed_trial",
        "restored_production_scope",
        "auto_re_armed",
    )

    restart: bool | None = None
    reconnect: bool | None = None
    failover: bool | None = None
    restore: bool | None = None
    queue_drain: bool | None = None
    alert_ack: bool | None = None
    replay: bool | None = None
    operator_return: bool | None = None
    quiet_time: bool | None = None
    #: **Negative** — §24 line 511 prior authority is not revived.
    revived_prior_authority: bool | None = None
    #: **Negative** — §24 line 511 trial state is not reusable.
    resumed_trial: bool | None = None
    #: **Negative** — §24 line 511 production scope is not restored.
    restored_production_scope: bool | None = None
    #: **Negative** — §24 line 511 a fresh governed re-arm chain remains mandatory.
    auto_re_armed: bool | None = None


class RestrictiveMonitoringSignal(FrozenModel):
    """The non-authorizing signal monitoring proposes (§5.10; §17 line 402; STM-INV-011 line 199).

    §5.10 line 147 verbatim: "An authenticated request or fact that can only **preserve or reduce**
    future authority through the separately owned ADR-002-024/027 path. **It cannot clear a restriction
    or create permission.**" §17 line 402 verbatim: "**No monitor or alert may downgrade an existing
    fence or incident, select a narrower scope, clear a local latch, or publish ``NO_INCIDENT``.**"

    The four §17 line 402 prohibitions (transcribed as
    :data:`~tos.stm.vocabulary.RESTRICTIVE_SIGNAL_PROHIBITIONS`) are carried 1:1 by the four
    **negative**-polarity fields consumed through :data:`PROHIBITION_FIELDS`, alongside the all-false
    authority block.

    **``publishes_no_incident`` is a prohibition flag, not a token** (design #30 §6.7, the #28 SIR
    phantom lesson): ADR §17 line 402 forbids publishing ``NO_INCIDENT``; it does not give stm ownership
    of a ``NO_INCIDENT`` vocabulary member. Incident materiality, severity, greatest-credible scope,
    Incident Generation, containment and closure all remain ADR-002-027-owned (§17 line 400) and are
    re-authored not at all. This is the **forward seam** sir already anticipates as an injected opaque
    coordinate (``sir/predicates.py:15``; ``sir/state.py:46``).
    """

    #: The four §17 line 402 prohibitions, consumed as a group by ``handoff_is_non_authorizing``.
    PROHIBITION_FIELDS: ClassVar[tuple[str, ...]] = (
        "downgrades_existing_fence",
        "selects_narrower_scope",
        "clears_local_latch",
        "publishes_no_incident",
    )

    signal_id: str | None = None
    source_identity: str | None = None
    scope: str | None = None
    #: The §5.5 Monitor Generation ordering scalar (an ordering identity, never a clock).
    monitor_generation: int | None = None
    confidence: str | None = None
    common_modes: frozenset[str] = frozenset()
    downgrades_existing_fence: bool | None = None
    selects_narrower_scope: bool | None = None
    clears_local_latch: bool | None = None
    publishes_no_incident: bool | None = None
    #: §5.10 / STM-INV-011 — a proposed signal is non-authorizing (all-false).
    authority_effect: AllFalseMonitoringAuthority = AllFalseMonitoringAuthority()


class SendRaceOrdering(FrozenModel):
    """The §18 line 421 invalidation-versus-send ordering permutation (not-Phase-1 §6b thin model).

    §18 line 421 verbatim: "**If a gap or restriction is ordered before the capability claim, the send
    is denied. If ordering between a material monitoring invalidation and first broker-directed byte
    cannot be proven, the attempt remains potentially live, capacity-covered, and ineligible for blind
    retry.** Monitoring success never overrides another denial or creates a Transmission Capability."

    **Three-value discipline (design #30 §4.3, the #28 MAJOR-2 lesson).** "Proven denial", "proven
    safe" and "unprovable" are three distinct states and are never folded into one boolean:
    :func:`~tos.stm.predicates.restriction_ordered_before_capability_claim` answers only "is the
    restriction *provably* first?", and :func:`~tos.stm.predicates.attempt_potentially_live` answers the
    conservative residue independently. ``ordering_provable`` is **positive** polarity — an unknown
    ``None`` lands on the potentially-live side.

    The three ordering coordinates are ``tos.ordering.OrderingEvent`` values (REUSE, no re-authored
    order). The cache-free currentness protocol, the ``B_monitoring_gap_to_egress_deny`` bound and the
    deny-first latch are +Security runtime and egress-owned (STM-EV-009, ``EV-L3+Security``).
    """

    #: The ordered gap / restriction event (§18 line 421 "a gap or restriction is ordered before").
    restrict_event: OrderingEvent | None = None
    #: The capability-claim event (§18 line 421 "the capability claim").
    capability_claim_event: OrderingEvent | None = None
    #: The first broker-directed byte, when one was recorded at all (``None`` ⇒ none recorded).
    first_byte_event: OrderingEvent | None = None
    #: Positive — §18 line 421 ordering must be *provable*; ``None`` ⇒ potentially live.
    ordering_provable: bool | None = None


# ===========================================================================
# Monitor Generation ordering REUSE (design #30 §3.2 — §5.5 / §12 line 337)
# ===========================================================================


def monitor_generation_advances(predecessor: int | None, candidate: int | None) -> bool:
    """Whether ``candidate`` strictly advances ``predecessor`` in Monitor Generation order (§5.5).

    REUSES ``tos.ordering.compare_order`` (no re-authored order) for the §5.5 Monitor Generation
    monotonic fence — "A **monotonic** generation identifying the current Safety Monitoring Policy,
    manifests, approved monitor logic, owners, and active restrictive state for one exact scope.
    **Restore, rollback, failover, replacement, or policy change cannot reuse a superseded
    generation**" — and the §12 line 337 rule that "any material policy, manifest, monitor, dependency,
    scope, source, evaluator, bound, suppression, failure-domain, or owner change advances the
    generation and invalidates affected snapshots." The two generations are wrapped as ordering
    coordinates (an ordering scalar, **not** a clock — design #30 §3.2) and the result is ``True``
    **only** when ``predecessor`` provably precedes ``candidate`` (``BEFORE``); an equal, ambiguous or
    regressing pair fails closed. stm owns the fence *meaning*; ordering only carries the order.

    Args:
        predecessor: The predecessor Monitor Generation ordering scalar (``None`` ⇒ ``False``).
        candidate: The candidate Monitor Generation ordering scalar (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff ``candidate`` provably strictly exceeds ``predecessor``.
    """
    if predecessor is None or candidate is None:
        return False
    return (
        compare_order(
            OrderingEvent(quorum_commit_index=predecessor),
            OrderingEvent(quorum_commit_index=candidate),
        )
        is Ordering.BEFORE
    )


def max_monitor_generation(generations: tuple[int | None, ...]) -> int | None:
    """The newest (MAX) Monitor Generation of a group, or ``None`` if any is unknown (§4.4; §12).

    The design #30 §4.4 group-reconcile rule: when several entries carry a Monitor Generation the
    reconciled fence is the **newest**, never the first (§5.5 monotonic; §12 line 337 "A stale owner is
    treated as potentially active until hard fencing is proven"; STM-INV-016 line 219). Order-independent
    by construction. A single ``None`` makes the group's newest generation **unprovable**, so the whole
    group fails closed to ``None`` rather than silently maximising over the known subset.

    Args:
        generations: The group's Monitor Generation ordering scalars.

    Returns:
        The newest generation, or ``None`` when the group is empty or any member is unknown.
    """
    if not generations:
        return None
    newest: int | None = None
    for generation in generations:
        if generation is None:
            return None
        if newest is None or monitor_generation_advances(newest, generation):
            newest = generation
    return newest
