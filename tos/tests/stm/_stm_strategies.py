"""Shared valid-artifact builders + strategies for the stm property tests (design #30 §7).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #30 §0.3). The builders enforce the
§7 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must be *genuinely* complete,
never a permissive shortcut):

* a **clean** coverage manifest is genuinely non-vacuous — **two** applicable obligations, one of them
  an admitted Monitored Assumption, every §9 item flag positively set, ``excluded=False``,
  ``coverage_score_present=False`` and the **full eleven-dimension** dependency closure — so a genuine
  ``critical_coverage_complete_or_gap`` is achievable without a shortcut, and so the coverage tally, the
  self-exemption gate, the dependency-closure subset and the assumption intake are each exercised
  against real structure rather than an empty tuple;
* a **clean** evaluation corpus carries **two distinct determinism keys** plus one lawful duplicate that
  agrees, so ``evaluation_is_deterministic`` is exercised on a real repeated key rather than vacuously;
* a **clean** snapshot is ``CONFORMING`` with every §12 line 324-333 binding concrete, a bound monitor
  result, a positive source-continuity fact and empty adverse sets — the only shape the §2.3 coexistence
  seal admits;
* every §6 substrate carrier is built with each polarity flag explicitly at its clearing value, so a
  test that flips exactly one flag isolates exactly one conjunct (design #30 §7.2 both-ways);
* the **polarity strategies** deliberately generate ``None`` / ``False`` / ``True`` tri-bools so the
  polarity seals (the #18/#22/#23/#25 MAJOR-2 lesson, and this contract's own C1) are exercised across
  every ``bool | None`` field.

Every generation / ordinal value is an explicit fixture int — nothing here is a *policy* number; the
real stm bounds are Verification-Profile injected and all null in Phase 1 (design #30 §8). The reserved
``"TBD"`` placeholder is excluded from required-field text. No concrete broker is named
(broker-agnostic).

Regime tag: coverage-completeness / deterministic-evaluation predicate substrate only; closes **no**
STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.stm import (
    SUPPRESSION_PRESERVED_FUNCTIONS,
    AggregateConformanceResult,
    AlertEscalationRecord,
    AlertStateVector,
    ApprovedBoundBinding,
    BoundSemanticKind,
    BrokerFinalityTokens,
    CommonModeDisclosure,
    ContinuousConformanceSnapshot,
    CoverageDimension,
    CoverageItem,
    CriticalTelemetryIdentity,
    CriticalTelemetryManifest,
    DashboardStatusToken,
    DashboardStatusView,
    MonitorCoverageManifest,
    MonitoredAssumptionIntake,
    MonitorEvaluation,
    MonitoringGapKind,
    MonitoringRecoveryInputs,
    MonitoringSuppression,
    MonitoringUnknownState,
    NumericInputState,
    RestrictiveMonitoringSignal,
    SafetyAlertRecord,
    SafetyMonitoringGap,
    SafetyMonitoringPolicy,
    SendRaceOrdering,
    SilenceObservation,
    SuppressionLifecycleState,
    TelemetryCriticality,
    TelemetrySemanticView,
)

#: The injected provisional canonicalizer (REUSE, design #30 §3.1 — no new scheme).
SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Injected ``bool | None`` flag (fail-closed on ``None`` / on the non-clearing value per polarity).
TRIBOOL = st.sampled_from([True, False, None])

#: The clean fixture's Monitor Generation (an ordering scalar, never a clock — design #30 §3.2).
CLEAN_MONITOR_GENERATION = 7

#: The clean fixture's applicable coordinates — genuinely non-vacuous on every axis.
CLEAN_OBLIGATION = "obl-hard-max"
CLEAN_ASSUMPTION_OBLIGATION = "obl-monitored-assumption"
CLEAN_APPLICABLE_OBLIGATIONS = frozenset(
    {CLEAN_OBLIGATION, CLEAN_ASSUMPTION_OBLIGATION}
)
CLEAN_SUBMITTED_ASSUMPTION_IDS = frozenset({CLEAN_ASSUMPTION_OBLIGATION})
#: All eleven §13 line 347 dimensions — a clean closure is complete, never a permissive subset.
CLEAN_APPLICABLE_DIMENSIONS: frozenset[CoverageDimension] = frozenset(CoverageDimension)

#: The clean determinism keys and bound reference (§11; design #30 §5.2).
CLEAN_BOUND_REF = "bound-binding-1"
CLEAN_KEY_A = ("evaluator-digest-a", "canonical-input-a")
CLEAN_KEY_B = ("evaluator-digest-b", "canonical-input-b")
CLEAN_REQUIRED_EVALUATION_KEYS: frozenset[tuple[str, str]] = frozenset(
    {CLEAN_KEY_A, CLEAN_KEY_B}
)
CLEAN_APPLICABLE_BOUND_REFS = frozenset({CLEAN_BOUND_REF})


# ---------------------------------------------------------------------------
# yolk 1 — §9 Monitor Coverage Manifest
# ---------------------------------------------------------------------------


def clean_coverage_item(**overrides: Any) -> CoverageItem:
    """A fully closed, positively un-excluded coverage item (§9 line 275-286)."""
    kwargs: dict[str, Any] = {
        "obligation_ref": CLEAN_OBLIGATION,
        "monitor_ref": "monitor-1",
        "scope_dimensions": CLEAN_APPLICABLE_DIMENSIONS,
        "dependency_closure_dimensions": CLEAN_APPLICABLE_DIMENSIONS,
        "restrictive_response_present": True,
        "alert_path_present": True,
        "evidence_path_present": True,
        "currentness_rule_present": True,
        "closure_1_to_12_complete": True,
        "excluded": False,
        "approved_exclusion_proof_present": None,
        "criticality": TelemetryCriticality.CRITICAL,
    }
    kwargs.update(overrides)
    return CoverageItem(**kwargs)


def clean_assumption_intake(**overrides: Any) -> MonitoredAssumptionIntake:
    """An admitted, property-invalidating Monitored Assumption (§9 line 288)."""
    kwargs: dict[str, Any] = {
        "assumption_id": CLEAN_ASSUMPTION_OBLIGATION,
        "admitted_as_coverage_item": True,
        "runtime_falsity_invalidates_property": True,
    }
    kwargs.update(overrides)
    return MonitoredAssumptionIntake(**kwargs)


def clean_coverage_manifest(**overrides: Any) -> MonitorCoverageManifest:
    """A complete, exact, unexempted, non-authorizing Monitor Coverage Manifest (§5.4/§9)."""
    kwargs: dict[str, Any] = {
        "coverage_manifest_id": "coverage-manifest-1",
        "coverage_generation": CLEAN_MONITOR_GENERATION,
        "coverage_manifest_digest": "coverage-digest-1",
        "policy_digest": "policy-digest-1",
        "coverage_items": (
            clean_coverage_item(),
            clean_coverage_item(
                obligation_ref=CLEAN_ASSUMPTION_OBLIGATION, monitor_ref="monitor-2"
            ),
        ),
        "approved_exclusions": (),
        "submitted_monitored_assumptions": (clean_assumption_intake(),),
        "is_complete": True,
        "coverage_score_present": False,
    }
    kwargs.update(overrides)
    return MonitorCoverageManifest(**kwargs)


# ---------------------------------------------------------------------------
# yolk 2 — §11 deterministic evaluation and bound semantics
# ---------------------------------------------------------------------------


def clean_evaluation(**overrides: Any) -> MonitorEvaluation:
    """One well-formed, ``CONFORMING`` monitor evaluation atom (§11 line 312/316)."""
    kwargs: dict[str, Any] = {
        "evaluator_digest": CLEAN_KEY_A[0],
        "canonical_input_digest": CLEAN_KEY_A[1],
        "result": AggregateConformanceResult.CONFORMING,
        "numeric_input_state": NumericInputState.WELL_FORMED,
        "bound_binding_digest": CLEAN_BOUND_REF,
    }
    kwargs.update(overrides)
    return MonitorEvaluation(**kwargs)


def clean_evaluation_corpus() -> tuple[MonitorEvaluation, ...]:
    """Two distinct determinism keys **plus one agreeing duplicate** — never a vacuous corpus."""
    return (
        clean_evaluation(),
        clean_evaluation(
            evaluator_digest=CLEAN_KEY_B[0], canonical_input_digest=CLEAN_KEY_B[1]
        ),
        clean_evaluation(),  # lawful duplicate: same key, same judgement
    )


def clean_bound(**overrides: Any) -> ApprovedBoundBinding:
    """A hard maximum implemented exactly as a hard maximum (§11 line 314; INV-007 line 183)."""
    kwargs: dict[str, Any] = {
        "bound_binding_digest": CLEAN_BOUND_REF,
        "approved_bound_kind": BoundSemanticKind.HARD_MAXIMUM,
        "implemented_as_kind": BoundSemanticKind.HARD_MAXIMUM,
        "units_exact": True,
        "permits_individual_exceedance": False,
        "window_inside_bound": True,
        "uncertainty_treated": True,
    }
    kwargs.update(overrides)
    return ApprovedBoundBinding(**kwargs)


# ---------------------------------------------------------------------------
# digest-bound artifacts
# ---------------------------------------------------------------------------


def clean_policy(**overrides: Any) -> SafetyMonitoringPolicy:
    """A governed, non-authorizing Safety Monitoring Policy (§5.1 line 111)."""
    kwargs: dict[str, Any] = {
        "policy_id": "policy-1",
        "policy_generation": CLEAN_MONITOR_GENERATION,
        "policy_digest": "policy-digest-1",
        "critical_telemetry_classes": ("class-a",),
        "coverage_requirements": ("requirement-a",),
        "approved_monitor_digests": ("monitor-digest-a",),
        "bound_bindings": (clean_bound(),),
        "independence_requirements": ("independence-a",),
        "suppression_rules": ("suppression-a",),
        "alert_escalation_paths": ("path-a",),
        "evidence_obligations": ("evidence-a",),
        "currentness_rules": ("currentness-a",),
        "recovery_behavior": ("recovery-a",),
        "failure_behavior": ("failure-a",),
    }
    kwargs.update(overrides)
    return SafetyMonitoringPolicy(**kwargs)


def clean_telemetry_manifest(**overrides: Any) -> CriticalTelemetryManifest:
    """A Critical Telemetry Manifest that grants no authority (§5.3 line 119)."""
    kwargs: dict[str, Any] = {
        "manifest_id": "telemetry-manifest-1",
        "manifest_generation": CLEAN_MONITOR_GENERATION,
        "manifest_digest": "telemetry-manifest-digest-1",
        "telemetry_identities": (clean_identity(),),
    }
    kwargs.update(overrides)
    return CriticalTelemetryManifest(**kwargs)


def clean_snapshot(**overrides: Any) -> ContinuousConformanceSnapshot:
    """A ``CONFORMING`` snapshot with every §12 line 324-333 binding concrete (§12 line 335)."""
    kwargs: dict[str, Any] = {
        "snapshot_id": "snapshot-1",
        "snapshot_generation": CLEAN_MONITOR_GENERATION,
        "snapshot_digest": "snapshot-digest-1",
        "monitor_generation": CLEAN_MONITOR_GENERATION,
        "policy_digest": "policy-digest-1",
        "critical_telemetry_manifest_digest": "telemetry-manifest-digest-1",
        "coverage_manifest_digest": "coverage-digest-1",
        "scope": "cell-a",
        "owner_epoch": "owner-epoch-1",
        "monitor_results": (clean_evaluation(),),
        "source_continuity_present": True,
        "active_violations": (),
        "active_unknowns": (),
        "active_gaps": (),
        "active_suppressions": (),
        "delivery_failures": (),
        "aggregate_result": AggregateConformanceResult.CONFORMING,
    }
    kwargs.update(overrides)
    return ContinuousConformanceSnapshot(**kwargs)


def clean_gap(**overrides: Any) -> SafetyMonitoringGap:
    """A classified, non-authorizing, positively-closed Safety Monitoring Gap (§5.7/§13)."""
    kwargs: dict[str, Any] = {
        "gap_id": "gap-1",
        "gap_generation": CLEAN_MONITOR_GENERATION,
        "gap_digest": "gap-digest-1",
        "monitor_generation": CLEAN_MONITOR_GENERATION,
        "gap_kind": MonitoringGapKind.MISSING,
        "exact_scope": "cell-a",
        "first_observation": "observation-1",
        "credible_start_interval": "interval-1",
        "source_evaluator_state": "state-1",
        "missing_evidence": ("evidence-a",),
        "common_modes": frozenset({"collector"}),
        "greatest_credible_impact": "impact-1",
        "required_restrictions": ("restriction-a",),
        "alert_state": "alert-state-1",
        "closure_proof_present": True,
    }
    kwargs.update(overrides)
    return SafetyMonitoringGap(**kwargs)


def clean_alert(**overrides: Any) -> SafetyAlertRecord:
    """A non-authorizing Safety Alert Record with the seven §16 line 384 bindings (§5.8)."""
    kwargs: dict[str, Any] = {
        "alert_id": "alert-1",
        "alert_generation": CLEAN_MONITOR_GENERATION,
        "alert_digest": "alert-digest-1",
        "monitor_generation": CLEAN_MONITOR_GENERATION,
        "signal_lineage": "lineage-1",
        "exact_scope": "cell-a",
        "first_known_time": "trustworthy-time-1",
        "severity_proposal": "proposal-1",
        "correlation_facts": ("fact-a",),
        "required_delivery_policy": "delivery-policy-1",
        "required_escalation_policy": "escalation-policy-1",
        "restriction_linkage": "restriction-1",
        "incident_classification_rule": "classification-rule-1",
    }
    kwargs.update(overrides)
    return SafetyAlertRecord(**kwargs)


def clean_escalation(**overrides: Any) -> AlertEscalationRecord:
    """A singly-bound, un-unioned Alert Escalation Record (§5.9 line 143)."""
    kwargs: dict[str, Any] = {
        "escalation_id": "escalation-1",
        "escalation_generation": CLEAN_MONITOR_GENERATION,
        "escalation_digest": "escalation-digest-1",
        "bound_alert_id": "alert-1",
        "policy_digest": "policy-digest-1",
        "monitor_generation": CLEAN_MONITOR_GENERATION,
        "ordered_delivery_attempts": ("attempt-1",),
        "acknowledgements": (),
        "escalation_stages": ("stage-1",),
        "failures": (),
        "alternate_paths": ("path-b",),
        "handoffs": ("handoff-1",),
        "retirement_criteria": ("criterion-1",),
        "unioned_or_substituted": False,
    }
    kwargs.update(overrides)
    return AlertEscalationRecord(**kwargs)


# ---------------------------------------------------------------------------
# §6 substrate carriers
# ---------------------------------------------------------------------------


def clean_identity(**overrides: Any) -> CriticalTelemetryIdentity:
    """An exact, un-reinterpreted Critical Telemetry identity (§8 line 253-267; §10)."""
    kwargs: dict[str, Any] = {
        "telemetry_id": "telemetry-1",
        "source_identity": "source-1",
        "units": "unit-a",
        "schema_digest": "schema-digest-1",
        "derivation_lineage_digest": "lineage-digest-1",
        "trustworthy_time_basis": "time-basis-1",
        "continuity_fact": "continuity-1",
        "criticality": TelemetryCriticality.CRITICAL,
        "semantics_reinterpreted": False,
        "hash_equality_claims_equivalence": False,
    }
    kwargs.update(overrides)
    return CriticalTelemetryIdentity(**kwargs)


def clean_semantic_view(**overrides: Any) -> TelemetrySemanticView:
    """A provenance view asserting none of the three §10 line 300-302 prohibitions."""
    kwargs: dict[str, Any] = {
        "cross_host_monotonic_subtracted": False,
        "identical_values_claim_continuity": False,
        "age_clamped_from_unbounded": False,
    }
    kwargs.update(overrides)
    return TelemetrySemanticView(**kwargs)


def clean_silence(**overrides: Any) -> SilenceObservation:
    """An honest silence observation: **every** marker set, health claim positively ``False``.

    Deliberately marker-**saturated** so the design #30 §6.2 conservative branch is exposed on its own
    (the #28 MAJOR-3 lesson): if a silence marker ever became a gate, this fixture would still pass
    while the ``treated_as_healthy=True`` fixture must still deny.
    """
    kwargs: dict[str, Any] = {
        "treated_as_healthy": False,
        "no_alert": True,
        "repeated_heartbeat": True,
        "quiet_time": True,
        "empty_query": True,
        "green_dashboard": True,
    }
    kwargs.update(overrides)
    return SilenceObservation(**kwargs)


def clean_unknown_state(**overrides: Any) -> MonitoringUnknownState:
    """A monitoring state with all seven STM-INV-005 line 175 axes positively ``False``."""
    kwargs: dict[str, Any] = dict.fromkeys(MonitoringUnknownState.UNKNOWN_FIELDS, False)
    kwargs.update(overrides)
    return MonitoringUnknownState(**kwargs)


def clean_common_mode(**overrides: Any) -> CommonModeDisclosure:
    """A disclosure with a **real** shared dependency and no independence claim (§14 line 355-359)."""
    kwargs: dict[str, Any] = {
        "shared_dependencies": frozenset({"COLLECTOR", "TIME_SOURCE"}),
        "claimed_independent": False,
        "residual_common_mode_disclosed": True,
        "self_health_as_proof": False,
        "validates_own_continuity_by_own_output": False,
    }
    kwargs.update(overrides)
    return CommonModeDisclosure(**kwargs)


def clean_suppression(**overrides: Any) -> MonitoringSuppression:
    """An ``ACTIVE`` suppression disabling none of the six and preserving all eight (§5.11/§15)."""
    kwargs: dict[str, Any] = {
        "suppression_id": "suppression-1",
        "scope": "cell-a",
        "purpose": "duplicate-notification-reduction",
        "lifecycle_state": SuppressionLifecycleState.ACTIVE,
        "preserved_functions": SUPPRESSION_PRESERVED_FUNCTIONS,
    }
    kwargs.update(dict.fromkeys(MonitoringSuppression.DISABLE_FIELDS, False))
    kwargs.update(overrides)
    return MonitoringSuppression(**kwargs)


def clean_alert_state(**overrides: Any) -> AlertStateVector:
    """An orthogonal, loss-preserving alert state vector (§16 line 388/390; INV-009/010)."""
    kwargs: dict[str, Any] = {
        "detection_state": "detected",
        "delivery_state": "delivered",
        "acknowledgement_state": "acknowledged",
        "escalation_state": "stage-1",
        "containment_state": "uncontained",
        "incident_state": "unclassified",
        "recovery_state": "not-ready",
        "economic_finality_state": "unknown",
        "ack_implies_containment": False,
        "advance_of_one_implies_another": False,
        "adverse_record_dropped": False,
        "elapsed_time_reset": False,
    }
    kwargs.update(overrides)
    return AlertStateVector(**kwargs)


def clean_broker_tokens(**overrides: Any) -> BrokerFinalityTokens:
    """Broker-finality tokens asserting none of the three §19 line 429 inferences."""
    kwargs: dict[str, Any] = {
        "missing_ack_treated_as_non_acceptance": False,
        "cancel_ack_treated_as_fqp": False,
        "unknown_effect_capacity_released": False,
    }
    kwargs.update(overrides)
    return BrokerFinalityTokens(**kwargs)


def clean_dashboard(**overrides: Any) -> DashboardStatusView:
    """An honest dashboard view: no failed render, no unknown state, no green default (§23 line 499)."""
    kwargs: dict[str, Any] = {
        "status_token": DashboardStatusToken.CURRENT_CONFORMING,
        "rendering_failed": False,
        "state_unknown": False,
        "defaulted_to_green": False,
    }
    kwargs.update(overrides)
    return DashboardStatusView(**kwargs)


def clean_recovery(**overrides: Any) -> MonitoringRecoveryInputs:
    """Recovery inputs with **every** marker recorded and all four non-revival fields ``False``.

    Marker-**saturated** on purpose (design #30 §2.4 / the #28 MAJOR-3 lesson): the non-revival gate is
    armed by the marker disjunction, so a fixture with no marker would make the four judgements
    unreachable and hide the whole conjunct.
    """
    kwargs: dict[str, Any] = dict.fromkeys(
        MonitoringRecoveryInputs.RECOVERY_MARKER_FIELDS, True
    )
    kwargs.update(dict.fromkeys(MonitoringRecoveryInputs.NON_REVIVAL_FIELDS, False))
    kwargs.update(overrides)
    return MonitoringRecoveryInputs(**kwargs)


def clean_signal(**overrides: Any) -> RestrictiveMonitoringSignal:
    """A non-authorizing restrictive monitoring signal (§5.10; §17 line 402)."""
    kwargs: dict[str, Any] = {
        "signal_id": "signal-1",
        "source_identity": "source-1",
        "scope": "cell-a",
        "monitor_generation": CLEAN_MONITOR_GENERATION,
        "confidence": "high",
        "common_modes": frozenset({"COLLECTOR"}),
    }
    kwargs.update(dict.fromkeys(RestrictiveMonitoringSignal.PROHIBITION_FIELDS, False))
    kwargs.update(overrides)
    return RestrictiveMonitoringSignal(**kwargs)


def clean_send_race(**overrides: Any) -> SendRaceOrdering:
    """The one clearing §18 line 421 shape: provable ``RESTRICT < CAPABILITY_CLAIM``, no first byte.

    "If a gap or restriction is ordered before the capability claim, the send is denied" — so the
    attempt never reached the wire and is **not** potentially live. Every other permutation (unprovable
    ordering, a recorded first byte, an equal or ``AMBIGUOUS`` comparison) is the conservative side.
    """
    from tos.ordering import OrderingEvent

    kwargs: dict[str, Any] = {
        "restrict_event": OrderingEvent(quorum_commit_index=10),
        "capability_claim_event": OrderingEvent(quorum_commit_index=20),
        "first_byte_event": None,
        "ordering_provable": True,
    }
    kwargs.update(overrides)
    return SendRaceOrdering(**kwargs)
