"""Shared valid-artifact builders + strategies for the sir property tests (design #28 §7).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #28 §0.3). The builders enforce the
§7 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must be *genuinely* complete,
never a permissive shortcut):

* a **clean** dependency closure presents **all 22** §5.6 dimensions with an explicit affected-id entry
  for each, ``closure_unknown=False`` and a positive completeness proof, so a genuine
  ``dependency_closure_complete`` is achievable (not a shortcut);
* a **clean** active set is genuinely non-vacuous — two members, one still open and one ``CLOSED``, a
  declared shared dependency, ``is_complete``/``is_current`` positively ``True`` and both generations
  concrete — so each ``no_favorable_subset`` derivation is exercised against real structure rather than
  an empty tuple;
* a **clean** incident record carries an exact un-exempted scope, an admissible classification, and
  every polarity flag explicitly set to its clearing value;
* a **clean** closure decision is ``CLOSE_ADMINISTRATIVELY`` with all twelve §20 contract slots at their
  declared polarity, ``single_use_consumed=False`` and an all-false authority;
* a **clean** containment plan carries a fully-referenced action, a resolved protection obligation and
  the three §14 protective coordinates at their clearing values;
* the **polarity strategies** deliberately generate ``None`` / ``False`` / ``True`` tri-bools so the
  polarity seals (the #18/#22/#23/#25 MAJOR-2 lesson) are exercised across every ``bool | None`` field.

Every generation / ordinal value is an explicit fixture int — nothing here is a *policy* number; the
real sir bounds are Verification-Profile injected and all null in Phase 1 (design #28 §8). The reserved
``"TBD"`` placeholder is excluded from required-field text. No concrete broker is named
(broker-agnostic).
"""

from __future__ import annotations

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.sir import (
    CLOSURE_CONTRACT_ITEM_POLARITY,
    SHUTDOWN_PROHIBITIONS,
    SHUTDOWN_STEP_KINDS,
    ActiveSafetyIncidentSet,
    ActiveSetMember,
    AnalysisClaim,
    BrokerFinalityTokens,
    ClosureDecisionResult,
    ClosureDimension,
    ClosureIndependenceLadder,
    CommunicationAssertionKind,
    CommunicationHonestyLadder,
    ContainmentAction,
    ControlledShutdownProcedure,
    ExternalActivityClaim,
    IncidentClassificationInput,
    IncidentClosureDecision,
    IncidentContainmentPlan,
    IncidentDependencyClosure,
    IncidentLifecycleState,
    IncidentRecordState,
    IncidentRecoveryHandoffPackage,
    IncidentScope,
    IncidentUnknownState,
    OngoingSafetyObligation,
    RecoveryRevivalInputs,
    SafetyIncidentPolicy,
    SafetyIncidentRecord,
    SafetySignal,
    ShutdownStep,
    SignalClassificationClass,
)

#: The injected provisional canonicalizer (REUSE, design #28 §3.1 — no new scheme).
SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Injected ``bool | None`` flag (fail-closed on ``None`` / on the non-clearing value per polarity).
TRIBOOL = st.sampled_from([True, False, None])

#: The clean fixture's Incident Generation (an ordering scalar, never a clock — design #28 §3.2).
CLEAN_INCIDENT_GENERATION = 5

#: The clean fixture's applicable coordinates.
CLEAN_APPLICABLE_INCIDENTS = frozenset({"inc-open", "inc-closed"})
CLEAN_APPLICABLE_SHARED_CAUSES = frozenset({"dep-shared"})
CLEAN_APPLICABLE_DIMENSIONS: frozenset[ClosureDimension] = frozenset()


def clean_signal(**overrides: object) -> SafetySignal:
    """A material, authenticated Safety Signal with a positively establishable scope (§5.2)."""
    kwargs: dict[str, object] = {
        "signal_id": "sig-1",
        "source_identity": "src-1",
        "trustworthy_time_basis": "time-gen-1",
        "classification": SignalClassificationClass.HARD_ENVELOPE_VIOLATION,
        "is_material": True,
        "is_authenticated": True,
        "scope_establishable": True,
    }
    kwargs.update(overrides)
    return SafetySignal(**kwargs)


def clean_classification(**overrides: object) -> IncidentClassificationInput:
    """A §8 classification input with a positive policy match and a positively established scope."""
    kwargs: dict[str, object] = {
        "classification": SignalClassificationClass.HARD_ENVELOPE_VIOLATION,
        "policy_class_match": True,
        "severity": "severity-major",
        "unestablished": False,
    }
    kwargs.update(overrides)
    return IncidentClassificationInput(**kwargs)


def clean_scope(**overrides: object) -> IncidentScope:
    """An exact scope covering every §5.6 dimension, neither self-exempted nor narrowed (§10:303)."""
    kwargs: dict[str, object] = {
        "scope_by_dimension": {
            dimension: frozenset({f"{dimension.value.lower()}-1"})
            for dimension in ClosureDimension
        },
        "self_exempted": False,
        "wildcard_or_narrowed": False,
    }
    kwargs.update(overrides)
    return IncidentScope(**kwargs)


def clean_dependency_closure(**overrides: object) -> IncidentDependencyClosure:
    """A §5.6 closure presenting all 22 dimensions with an explicit affected-id entry for each."""
    kwargs: dict[str, object] = {
        "present_dimensions": frozenset(ClosureDimension),
        "affected_ids_by_dimension": {
            dimension: frozenset({f"{dimension.value.lower()}-1"})
            for dimension in ClosureDimension
        },
        "closure_unknown": False,
        "dependency_closure_complete": True,
    }
    kwargs.update(overrides)
    return IncidentDependencyClosure(**kwargs)


def clean_obligation(**overrides: object) -> OngoingSafetyObligation:
    """A §5.11 ongoing obligation that is positively resolved and positively transferred."""
    kwargs: dict[str, object] = {
        "obligation_id": "obl-1",
        "kind": "protection-duty",
        "resolved": True,
        "transferred_with_owner_and_evidence": True,
    }
    kwargs.update(overrides)
    return OngoingSafetyObligation(**kwargs)


def clean_action(**overrides: object) -> ContainmentAction:
    """A §11 containment action carrying all five separately-owned prerequisite references."""
    kwargs: dict[str, object] = {
        "action_kind": "reconciliation",
        "classifier_ref": "protective-classifier-1",
        "authority_ref": "authority-gen-1",
        "capacity_ref": "rcl-commitment-1",
        "currentness_ref": "currentness-vector-1",
        "egress_ref": "egress-validation-1",
        "assumed_executable": False,
    }
    kwargs.update(overrides)
    return ContainmentAction(**kwargs)


def clean_shutdown_procedure(**overrides: object) -> ControlledShutdownProcedure:
    """A §5.8 procedure that denies before stopping and declares every §12 prohibition."""
    kwargs: dict[str, object] = {
        "ordered_steps": tuple(
            ShutdownStep(step_ordinal=index, step_kind=kind, completed=False)
            for index, kind in enumerate(SHUTDOWN_STEP_KINDS, start=1)
        ),
        "deny_before_stop": True,
        "preserved_functions": ("halt", "egress-latch", "reconciliation"),
        "hard_fenced_paths": ("path-1",),
        "prohibited": SHUTDOWN_PROHIBITIONS,
    }
    kwargs.update(overrides)
    return ControlledShutdownProcedure(**kwargs)


def clean_member(
    *,
    incident_id: str = "inc-open",
    lifecycle_state: IncidentLifecycleState | None = IncidentLifecycleState.SUSPECTED,
    **overrides: object,
) -> ActiveSetMember:
    """One structural Active Safety Incident Set member (§5.5/§10)."""
    kwargs: dict[str, object] = {
        "incident_id": incident_id,
        "incident_digest": f"{incident_id}-digest",
        "lifecycle_state": lifecycle_state,
        "parent_id": None,
        "shared_cause_ids": frozenset(),
        "resolved": True,
    }
    kwargs.update(overrides)
    return ActiveSetMember(**kwargs)


def clean_members() -> tuple[ActiveSetMember, ...]:
    """The genuinely non-vacuous clean member tuple: one open incident and one ``CLOSED`` one.

    Deliberately **not** empty: an empty tuple would make every ``no_favorable_subset`` derivation
    vacuously ``False`` and the clean fixture would prove nothing (the #8 lesson). One member declares a
    shared cause (exercising the shared-cause derivation against real data) and the other is ``CLOSED``
    (so the two-open-member common-mode derivation is genuinely evaluated and genuinely ``False``).
    """
    return (
        clean_member(
            incident_id="inc-open",
            lifecycle_state=IncidentLifecycleState.SUSPECTED,
            shared_cause_ids=frozenset({"dep-shared"}),
            resolved=True,
        ),
        clean_member(
            incident_id="inc-closed",
            lifecycle_state=IncidentLifecycleState.CLOSED,
            shared_cause_ids=frozenset(),
            resolved=True,
        ),
    )


def clean_active_set(**overrides: object) -> ActiveSafetyIncidentSet:
    """A digest-verified canonical Active Safety Incident Set (§5.5; injected coordinates uncovered)."""
    kwargs: dict[str, object] = {
        "active_set_id": "set-1",
        "active_set_generation": 1,
        "active_set_digest": "set-1-digest",
        "incident_generation": CLEAN_INCIDENT_GENERATION,
        "safety_cell": "cell-1",
        "members": clean_members(),
        "shared_dependencies": ("dep-shared",),
        "is_complete": True,
        "is_current": True,
        "state": IncidentLifecycleState.CONTAINING,
    }
    kwargs.update(overrides)
    return ActiveSafetyIncidentSet.issue(scheme=SCHEME, **kwargs)


def empty_active_set(**overrides: object) -> ActiveSafetyIncidentSet:
    """The §4.4 **valid explicit-empty** set — the canonical no-incident bundle (§5.5:126; §16:423)."""
    kwargs: dict[str, object] = {
        "members": (),
        "shared_dependencies": (),
        "state": None,
    }
    kwargs.update(overrides)
    return clean_active_set(**kwargs)


def clean_record(**overrides: object) -> SafetyIncidentRecord:
    """A digest-verified, genuinely coherent restrictive Safety Incident Record (§5.3)."""
    kwargs: dict[str, object] = {
        "incident_id": "inc-open",
        "record_version": 1,
        "record_digest": "rec-1-digest",
        "predecessor_record_id": None,
        "incident_generation": CLEAN_INCIDENT_GENERATION,
        "signals": (clean_signal(),),
        "severity": "severity-major",
        "incident_scope": clean_scope(),
        "dependency_closure": clean_dependency_closure(),
        "restrictions": ("halt-request",),
        "actions": ("fence-1",),
        "ongoing_obligations": (clean_obligation(),),
        "evidence_gaps": (),
        "external_activity": (),
        "owners": ("owner-1",),
        "lifecycle_state": IncidentLifecycleState.SUSPECTED,
        "record_state": IncidentRecordState.ACTIVE,
        "classification": clean_classification(),
        "greatest_credible_scope_computed": True,
        "restriction_workflow_gated": False,
        "severity_label_narrows_scope": False,
    }
    kwargs.update(overrides)
    return SafetyIncidentRecord.issue(scheme=SCHEME, **kwargs)


def clean_policy(**overrides: object) -> SafetyIncidentPolicy:
    """A digest-verified governed Safety Incident Policy (§5.1; spg/014 activation injected)."""
    kwargs: dict[str, object] = {
        "policy_id": "pol-1",
        "policy_generation": 3,
        "policy_digest": "pol-1-digest",
        "authoritative_signal_classes": frozenset(SignalClassificationClass),
        "severity_rules": ("rule-severity",),
        "scope_closure_rules": ("rule-closure",),
        "required_restrictions": ("rule-restriction",),
        "escalation_paths": ("path-1",),
        "controlled_shutdown_rules": ("rule-shutdown",),
        "evidence_obligations": ("rule-evidence",),
        "independence_requirements": ("rule-independence",),
        "closure_conditions": ("rule-closure-condition",),
        "failure_behavior": ("fail-closed",),
    }
    kwargs.update(overrides)
    return SafetyIncidentPolicy.issue(scheme=SCHEME, **kwargs)


def clean_plan(**overrides: object) -> IncidentContainmentPlan:
    """A digest-verified non-authorizing Incident Containment Plan (§5.7/§11)."""
    kwargs: dict[str, object] = {
        "plan_id": "plan-1",
        "plan_generation": 1,
        "plan_digest": "plan-1-digest",
        "incident_id": "inc-open",
        "active_set_digest": "set-1-digest",
        "incident_generation": CLEAN_INCIDENT_GENERATION,
        "scope": clean_scope(),
        "severity": "severity-major",
        "signals": (clean_signal(),),
        "hazards": ("hazard-1",),
        "dependency_closure": clean_dependency_closure(),
        "committed_restrictions": ("deny-new-risk",),
        "hard_fences": ("fence-1",),
        "stale_owner_disposition": ("owner-1-fenced",),
        "positions": ("pos-1",),
        "orders": ("ord-1",),
        "potentially_live_quantity": ("plq-1",),
        "external_activity": (),
        "rcl_commitments": ("commitment-1",),
        "protection_obligations": (clean_obligation(),),
        "proposed_actions": (clean_action(),),
        "controlled_shutdown": clean_shutdown_procedure(),
        "evidence": ("evidence-1",),
        "notification": ("notify-1",),
        "handoff": ("handoff-1",),
        "escalation": ("escalate-1",),
        "failure_behavior": ("fail-closed",),
        "recovery_barrier_trigger": "barrier-trigger-1",
        "protection_blindly_cancelled": False,
        "cancellation_arbiter_approved": True,
        "exposure_reported_safely_closed": False,
    }
    kwargs.update(overrides)
    return IncidentContainmentPlan.issue(scheme=SCHEME, **kwargs)


def clean_handoff(**overrides: object) -> IncidentRecoveryHandoffPackage:
    """A digest-verified non-authorizing Recovery Handoff Package (§5.9; sbr verdicts injected)."""
    kwargs: dict[str, object] = {
        "handoff_id": "handoff-1",
        "handoff_generation": 1,
        "handoff_digest": "handoff-1-digest",
        "incident_id": "inc-open",
        "active_set_generation": 1,
        "unresolved_obligations": (clean_obligation(resolved=False),),
        "recovery_barrier_closed": True,
        "accepted_by_recovery_session": True,
    }
    kwargs.update(overrides)
    return IncidentRecoveryHandoffPackage.issue(scheme=SCHEME, **kwargs)


def clean_contract_items() -> tuple[bool | None, ...]:
    """The twelve §20 contract slots, each at its declared :data:`CLOSURE_CONTRACT_ITEM_POLARITY`."""
    return tuple(bool(positive) for positive in CLOSURE_CONTRACT_ITEM_POLARITY)


def clean_closure_decision(**overrides: object) -> IncidentClosureDecision:
    """A digest-verified administrative, contract-complete, unconsumed Closure Decision (§5.10/§20)."""
    kwargs: dict[str, object] = {
        "closure_id": "clo-1",
        "closure_generation": 1,
        "closure_digest": "clo-1-digest",
        "incident_id": "inc-open",
        "active_set_digest": "set-1-digest",
        "incident_generation": CLEAN_INCIDENT_GENERATION,
        "result": ClosureDecisionResult.CLOSE_ADMINISTRATIVELY,
        "closure_contract_items": clean_contract_items(),
        "effective_principal_verdict": True,
        "single_use_consumed": False,
        "consumed_by_live_authority": False,
    }
    kwargs.update(overrides)
    return IncidentClosureDecision.issue(scheme=SCHEME, **kwargs)


def clean_communication_ladder(**overrides: object) -> CommunicationHonestyLadder:
    """A §18:472 honesty view whose label matches its kind and claims no enforcement ack."""
    kwargs: dict[str, object] = {
        "assertion_kind": CommunicationAssertionKind.OBSERVED_FACT,
        "claimed_as": CommunicationAssertionKind.OBSERVED_FACT,
        "is_message_ack": False,
        "treated_as_enforcement_ack": False,
    }
    kwargs.update(overrides)
    return CommunicationHonestyLadder(**kwargs)


def clean_analysis_claim(**overrides: object) -> AnalysisClaim:
    """A §18:474 analysis claim that substitutes nothing and authorizes nothing."""
    kwargs: dict[str, object] = {
        "analysis_kind": "root-cause",
        "substitutes_prevention": False,
        "authorizes_past_effect": False,
    }
    kwargs.update(overrides)
    return AnalysisClaim(**kwargs)


def clean_independence_ladder(**overrides: object) -> ClosureIndependenceLadder:
    """A §20 item 10 ladder with six distinct role identities and no collapse (hag verdict injected)."""
    kwargs: dict[str, object] = {
        "detector": "person-a",
        "affected_owner": "person-b",
        "response_implementer": "person-c",
        "evidence_producer": "person-d",
        "performance_beneficiary": "person-e",
        "live_armer": "person-f",
        "principals_collapsed": False,
        "independence_resolved": True,
        "single_operator_variant_supplies_second": False,
    }
    kwargs.update(overrides)
    return ClosureIndependenceLadder(**kwargs)


def clean_unknown_state(**overrides: object) -> IncidentUnknownState:
    """A §13/§16 UNKNOWN carrier with every axis positively ``False`` (SIR-INV-009)."""
    kwargs: dict[str, object] = dict.fromkeys(
        IncidentUnknownState.UNKNOWN_FIELDS, False
    )
    kwargs.update(overrides)
    return IncidentUnknownState(**kwargs)


def clean_broker_tokens(**overrides: object) -> BrokerFinalityTokens:
    """A §13 broker-finality carrier taking no shortcut (SIR-INV-010); broker-agnostic."""
    kwargs: dict[str, object] = {
        "missing_ack_treated_as_non_acceptance": False,
        "cancel_ack_treated_as_final_quantity_proof": False,
        "query_omission_treated_as_absence_proof": False,
        "blind_retry_authorized": False,
        "premature_release_authorized": False,
        "optimistic_reconciliation_authorized": False,
        "final_quantity_proof_present": False,
    }
    kwargs.update(overrides)
    return BrokerFinalityTokens(**kwargs)


def clean_revival_inputs(**overrides: object) -> RecoveryRevivalInputs:
    """A §21 non-revival carrier with every axis positively ``False`` (SIR-INV-015)."""
    kwargs: dict[str, object] = dict.fromkeys(
        RecoveryRevivalInputs.REVIVAL_FIELDS, False
    )
    kwargs.update(overrides)
    return RecoveryRevivalInputs(**kwargs)


def clean_external_activity(**overrides: object) -> ExternalActivityClaim:
    """A §15 external-activity claim that claims nothing and expands reconciliation."""
    kwargs: dict[str, object] = {
        "retroactively_compliant_transmission": False,
        "proves_execution_or_final_quantity": False,
        "releases_capacity_by_operator_statement": False,
        "clears_halt_or_closes_incident": False,
        "re_arms": False,
        "expands_reconciliation_and_closure": True,
    }
    kwargs.update(overrides)
    return ExternalActivityClaim(**kwargs)
