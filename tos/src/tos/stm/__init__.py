"""Safety Telemetry Integrity, Continuous Conformance Monitoring, and Alert Escalation Governance
(ADR-002-028 — "STM") pure models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-028 part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design
contract ``docs/plans/2026-07-28-tos-safety-telemetry-design.md`` (v1.1, operator-delegated
auto-ratified 2026-07-28). It authors the **coverage-completeness / deterministic-evaluation structural
substrate** — the complete-and-exact Critical coverage judgement with no self-exemption (STM-EV-001)
and the deterministic evaluation with intact approved-bound semantics (STM-EV-005) — over seven
digest-bound artifacts plus injected value models (design #30 §2).

**This is the series' safety-telemetry governance *greenfield content owner*, with NO inbound deferee
but the richest committed forward seam yet — four clades (design #30 §0.1/§0.4b, the key architecture
decision).** No landed sibling defers telemetry *content* to ``tos.stm``. What is different from SIR is
that the coordinates this package will produce are **already consumed** by four committed siblings:

1. ``cur/vocabulary.py:144`` — cur's currentness dimension-key enum has a ``MONITORING`` member,
   and it is inside cur's mandated dimension floor
   (``cur/vocabulary.py:172``). **cur owns that currentness dimension's completeness judgement**; stm
   produces the dimension's *value* (a Monitor Generation and a Continuous Conformance Snapshot digest)
   and re-authors none of cur's judgement. Claiming "cur does not own MONITORING" would be the #28 C1
   defect repeated, so it is asserted the other way here and locked by a seam test.
2. ``spg/vocabulary.py:217-219`` ``SAFETY_MONITORING_POLICY`` / ``CRITICAL_TELEMETRY_MANIFEST`` /
   ``MONITOR_COVERAGE_MANIFEST`` — governed-artifact-**kind** string tokens naming the *kind of artifact
   ADR-002-014 governs*, not these artifact models.
3. ``rlp/predicates.py:774-780`` ``monitoring_not_preventive`` plus its own docstring witness: "an
   EV-L6 monitor is **detective**, non-authorizing ... The monitoring generation is an **injected -028
   (STM) coordinate, not landed**."
4. ``sir/predicates.py:15`` / ``sir/state.py:46`` — "the **-028** / -029 handoff and
   compromise coordinates are ... injected opaque coordinates."

Every one of those consumptions is an **anonymous** dimension name, string token, ``bool | None`` or
opaque generation, and none references a ``tos.stm`` type — so the seam is **forward** and the **sibling
edge is 0**; stm is the producer of those coordinates' *values*, artifacts and structural judgements,
not a deferee. The name ``tos.stm`` is fixed only by four firewall *exclusion*-list comments
(``wdr/__init__.py:47`` / ``rlp/__init__.py:39`` / ``cur/__init__.py:51`` / ``sir/__init__.py:67``
enumerate the then-future sibling ``tos.stm`` as auto-excluded), so **naming is weak soft load-bearing** — a
different name would orphan no functional reference, only make those list comments imprecise (design #30
§0.4a).

Four same-name / different-proposition collisions are sealed explicitly (design #30 §0.5): cur's
``MONITORING`` currentness dimension key (``cur/vocabulary.py:144``); the spg
governed-artifact-**kind** tokens; ioc's
``ConformanceResult`` {CONFORMANT / NON_CONFORMANT / UNKNOWN} for *intent-to-order command* conformance
(``ioc/vocabulary.py:40-72``, whose ``__bool__`` seal is the reused *pattern* and nothing more); and the
string-only "monitoring" of ``wdr/vocabulary.py:268`` ``CompensatingControlKind.MONITORING`` and
``brokercap/vocabulary.py:110`` ``AssuranceLevel.LEVEL_4_CONTINUOUSLY_MONITORED``. That list is
**representative, not exhaustive**, which is why the anchor-resolution property re-fixes each collision
mechanically rather than by memory.

**The maximum risk here is over-realization (design #30 §0.4c).** STM-INV-001..016 is sixteen invariants
over only **two** ``EV-L1``-sliced rows — the fewest of the governance sextet: exactly five (001 / 002 /
003 / 004 / 007) contribute to the L1 yolks and the other eleven (005 / 006 / 008-016) are authored as
**predicate-only substrate that closes no STM-EV at all**. The telemetry collector and monitor evaluator
runtimes, the requirement/hazard/control registry and conservative coverage compiler, the Monitor
Generation registry and owner fence, the alert delivery / acknowledgement / escalation protocol, the
per-send final-egress currentness transaction, the worst-credible-effect computation and the §22
security controls are **all runtime / vendor / +Security / +Broker / sibling-owned**, never L1. The
second risk is duplication: the cur Active Currentness Vector **and MONITORING dimension completeness**,
spg policy activation + Hard Safety Envelope, rlp EV-L6 demotion, sir Incident Generation + incident
classification, egress final-egress enforcement + credential/route confinement, evidence custody,
authority Safety Authority / HALT, liveauth Live Authorization, rcl capacity mutation + worst-credible
effect, protective classification, time Trustworthy Time, hag Effective Principal and wdr's Non-Waivable
Boundary are **all injected-consumed**, re-authored not at all (design #30 §3.5).

This package is **pure, non-transmitting, non-collecting, non-mutating, and clock-free** (design #30
§0.2/§4.1): it has **no** send / transmit / emit / scrape / collect / publish / deliver / escalate /
page / suppress / mutate / reserve / release / clear-halt function — the structural absence of such a
function is this package's identity (§4.1 constructive-absence canary; the void-canary tests assert it,
including the absence of cur's dimension-key enum, its vector-completeness predicate and its mandated
dimension floor by name, so stm can never quietly usurp cur's judgement). It **cannot** create
capacity, approve an action, create headroom, mark a requirement ``PASS``, satisfy a preventive control,
establish broker finality, activate configuration, issue authority, permit transmission, close an
incident, establish recovery readiness, restore scope, re-arm, or classify an action protective
(all-false :class:`~tos.stm._base.AllFalseMonitoringAuthority`, STM-INV-001) — and that holds for a
``CONFORMING`` snapshot too (§1 line 25). A positive result comes only from positive proof, everything
else is denial (design #30 §4.3 — the polarity seal, with **negative-polarity fields never read with
``is not True``**; §4.4 — the reconcile seal and the two opposite-polarity empty sets).

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``classify_record_pair`` + ``EVL1ProvisionalCanonicalizer``, on whose tested
determinism yolk 2's key rests) + ``tos.ordering`` (Monitor Generation order). It imports **no**
sibling — every real sibling and any future one is excluded by the §7.1 **allowlist** closure test
(``tos.*`` closure ⊆ {``tos.canonical``, ``tos.ordering``, ``tos.stm``}) — **sibling edge 0** (design
#30 §0.3/§3.4). **rcl edge 0** in particular: stm does no capacity arithmetic (the worst credible
economic effect is an injected opaque coordinate, never a ``CapacityVector``), which is what ADR §7 line
235 demands — "Risk Capacity Ledger | **monitoring never writes capacity**". **PROMOTE 0** — the digest /
ordering substrate is already core.

Identity is **independent, not** ``f(digest)`` for all seven artifacts (design #30 §2.1/§3.1): each is
an immutable issued record; a same-id / different-**covered**-bytes forgery, re-issue or replay is a
detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` — the structural defence ADR §22 line 474
demands for "raw and derived telemetry integrity and continuity".

**Completion discipline (design #30 §1).** ``STM-EV-001..012`` are all NOT_IMPLEMENTED. Only **two** rows
carry an ``EV-L1`` slice (core), and — uniquely among the governance sextet — **both carry ``+Security``,
so there is no clean ``EV-L1/3`` row at all**: 001 Complete Critical Coverage (``EV-L1/3+Security``) and
005 Deterministic Evaluation and Bound Integrity (``EV-L1/3+Security``). Eight rows are predicate-only
(≥ ``EV-L2``): 002 / 003 / 004 / 006 / 007 / 008 / 010 / 012, of which 003 is the single untagged row
and 010 is the single ``+Broker`` row. Two rows are not-Phase-1 at an ``EV-L3`` floor — 009 Active
Currentness and Send Race and 011 Compromise, Fencing, and Failure Domains. ``+Security`` covers **ten of
twelve** rows, the highest density of the sextet. Phase 1 authors the L1-decidable structural substrate
and closes **no** STM-EV. Authoring is not evidence (VER-002-001 §5; ADR §27 line 594 "Written cases
define obligations only. They are not completed evidence."; §30 line 698 "Authorship ... does not satisfy
these gates."). Tag for any claim: "coverage-completeness / deterministic-evaluation predicate substrate
only; STM-EV-001..012 remain NOT_IMPLEMENTED pending EV-L2/L3 integration, adversarial, +Security and
+Broker evidence; **EV-L1-complete claim forbidden**; the telemetry collector / monitor evaluator runtime
/ coverage compiler / Monitor Generation registry and writer fence / alert delivery and escalation /
per-send egress currentness / worst-credible-effect computation are re-authored / runtime / vendor /
+Security / +Broker / sibling-owned; L1 is coverage / determinism / bound structural judgement only."

Regime tag: coverage-completeness / deterministic-evaluation predicate substrate only; closes
**no** STM-EV; ``STM-EV-001..012`` all remain NOT_IMPLEMENTED; **EV-L1-complete claim forbidden.**

Public surface groups by module:

* :mod:`tos.stm.vocabulary` — the eight truthy-untestable STM StrEnums
  (``AggregateConformanceResult`` / ``DashboardStatusToken`` / ``MonitoringGapKind`` /
  ``NumericInputState`` / ``BoundSemanticKind`` / ``TelemetryCriticality`` /
  ``SuppressionLifecycleState`` / ``CoverageDimension``) + the transcribed ADR anchors.
* :mod:`tos.stm.records` — the seven digest-bound artifacts + the all-false
  ``AllFalseMonitoringAuthority``.
* :mod:`tos.stm.state` — the sixteen injected value / input models + the ``tos.ordering`` generation
  REUSE.
* :mod:`tos.stm.predicates` — the two yolk predicates + supporting + the predicate-only §6 substrate +
  the not-Phase-1 §6b thin send-race / stale-writer models + the §4.3 polarity registry.
"""

from __future__ import annotations

from tos.stm._base import (
    AllFalseMonitoringAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    EVL1ProvisionalCanonicalizer,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)
from tos.stm.predicates import (
    MARKER_FIELDS,
    NEGATIVE_POLARITY_FIELDS,
    POSITIVE_POLARITY_FIELDS,
    absence_is_not_health,
    alert_state_is_orthogonal,
    all_false_monitoring_authority,
    attempt_potentially_live,
    bound_integrity_preserved,
    broker_finality_unchanged,
    common_mode_is_not_independence,
    conformance_requires_complete_current_valid,
    coverage_grants_no_authority,
    critical_coverage_complete_or_gap,
    deterministic_evaluation_bound_integrity,
    economic_effect_outlives_monitor_state,
    escalation_single_binding,
    evaluation_is_deterministic,
    evidence_and_status_honest,
    gap_is_restrictive_not_exemption,
    handoff_is_non_authorizing,
    loss_preserves_negative_facts,
    monitored_assumption_intake_closed,
    no_self_exemption,
    numeric_result_not_conforming_by_default,
    recovery_revives_nothing,
    restriction_ordered_before_capability_claim,
    stale_writer_fenced,
    suppression_cannot_suppress_safety,
    telemetry_semantics_exact,
    unknown_is_restrictive,
)
from tos.stm.records import (
    AlertEscalationRecord,
    ContinuousConformanceSnapshot,
    CriticalTelemetryManifest,
    MonitorCoverageManifest,
    SafetyAlertRecord,
    SafetyMonitoringGap,
    SafetyMonitoringPolicy,
)
from tos.stm.state import (
    AlertStateVector,
    ApprovedBoundBinding,
    BrokerFinalityTokens,
    CommonModeDisclosure,
    CoverageItem,
    CriticalTelemetryIdentity,
    DashboardStatusView,
    MonitoredAssumptionIntake,
    MonitorEvaluation,
    MonitoringRecoveryInputs,
    MonitoringSuppression,
    MonitoringUnknownState,
    RestrictiveMonitoringSignal,
    SendRaceOrdering,
    SilenceObservation,
    TelemetrySemanticView,
    max_monitor_generation,
    monitor_generation_advances,
)
from tos.stm.vocabulary import (
    ALL_FALSE_AUTHORITY_VERBS,
    COVERAGE_CLOSURE_ITEM_COUNT,
    COVERAGE_CLOSURE_ITEMS,
    CRITICAL_TELEMETRY_BINDING_GROUPS,
    DENYING_AGGREGATE_RESULTS,
    FINAL_EGRESS_CURRENTNESS_FACTS,
    HARD_BOUND_KINDS,
    IN_FORCE_SUPPRESSION_STATES,
    MALFORMED_NUMERIC_STATES,
    MONITORING_SUPPRESSION_PROHIBITIONS,
    NEUTRAL_BOUND_KINDS,
    PARTITION_FAILURE_MODES,
    RESTRICTIVE_SIGNAL_PROHIBITIONS,
    RESTRICTIVE_SUPPRESSION_STATES,
    SHARED_DEPENDENCY_ANCHOR,
    SUPPRESSION_PRESERVED_FUNCTIONS,
    WEAK_BOUND_KINDS,
    AggregateConformanceResult,
    BoundSemanticKind,
    CoverageDimension,
    DashboardStatusToken,
    MonitoringGapKind,
    NumericInputState,
    SuppressionLifecycleState,
    TelemetryCriticality,
)

__all__ = [
    # base (reused core + stm-local all-false authority)
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "EVL1ProvisionalCanonicalizer",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
    "AllFalseMonitoringAuthority",
    # vocabulary — the eight truthy-untestable enums
    "AggregateConformanceResult",
    "DashboardStatusToken",
    "MonitoringGapKind",
    "NumericInputState",
    "BoundSemanticKind",
    "TelemetryCriticality",
    "SuppressionLifecycleState",
    "CoverageDimension",
    # vocabulary — derived membership sets + transcribed ADR anchors
    "HARD_BOUND_KINDS",
    "NEUTRAL_BOUND_KINDS",
    "WEAK_BOUND_KINDS",
    "MALFORMED_NUMERIC_STATES",
    "DENYING_AGGREGATE_RESULTS",
    "RESTRICTIVE_SUPPRESSION_STATES",
    "IN_FORCE_SUPPRESSION_STATES",
    "COVERAGE_CLOSURE_ITEMS",
    "COVERAGE_CLOSURE_ITEM_COUNT",
    "FINAL_EGRESS_CURRENTNESS_FACTS",
    "SUPPRESSION_PRESERVED_FUNCTIONS",
    "PARTITION_FAILURE_MODES",
    "CRITICAL_TELEMETRY_BINDING_GROUPS",
    "SHARED_DEPENDENCY_ANCHOR",
    "ALL_FALSE_AUTHORITY_VERBS",
    "MONITORING_SUPPRESSION_PROHIBITIONS",
    "RESTRICTIVE_SIGNAL_PROHIBITIONS",
    # records — the seven digest-bound artifacts
    "SafetyMonitoringPolicy",
    "CriticalTelemetryManifest",
    "MonitorCoverageManifest",
    "ContinuousConformanceSnapshot",
    "SafetyMonitoringGap",
    "SafetyAlertRecord",
    "AlertEscalationRecord",
    # state — injected value / input models + ordering REUSE
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
    # polarity registry (design #30 §4.3 / §7.2 (a))
    "POSITIVE_POLARITY_FIELDS",
    "NEGATIVE_POLARITY_FIELDS",
    "MARKER_FIELDS",
    # core §5 predicates — the two yolks + supporting
    "all_false_monitoring_authority",
    "critical_coverage_complete_or_gap",
    "coverage_grants_no_authority",
    "no_self_exemption",
    "monitored_assumption_intake_closed",
    "deterministic_evaluation_bound_integrity",
    "evaluation_is_deterministic",
    "bound_integrity_preserved",
    "numeric_result_not_conforming_by_default",
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
