"""§6 predicate-only substrate — closes **no** SIR-EV (design #28 §0.4c/§6/§12).

SIR's defining discipline: **sixteen invariants over three ``EV-L1``-sliced rows**. Exactly five INV
(001 / 002 / 003 / 004 / 014) contribute to the three yolks; the other **eleven** (005 / 006 / 007 / 008
/ 009 / 010 / 011 / 012 / 013 / 015 / 016) are authored here as substrate that closes **no** SIR-EV at
all. This file exercises each §6 substrate predicate both ways and re-states, per predicate, the EV row
it does *not* close and the owner the real judgement belongs to — the over-realization boundary design
#28 §0.4c calls this contract's maximum risk.

Regime tag: predicate substrate only; SIR-EV-003 / 004 / 005 / 006 / 010 / 011 / 012 remain
NOT_IMPLEMENTED pending ``EV-L2`` / ``EV-L3`` component-fault and integration evidence plus ``+Broker``
/ ``+Security``; **EV-L1-complete claim forbidden**.
"""

from __future__ import annotations

import tos.sir as s

from ._sir_strategies import (
    clean_action,
    clean_active_set,
    clean_broker_tokens,
    clean_external_activity,
    clean_handoff,
    clean_independence_ladder,
    clean_member,
    clean_obligation,
    clean_plan,
    clean_revival_inputs,
    clean_shutdown_procedure,
    clean_unknown_state,
)

# --- §6.1 containment uses normal authority (SIR-INV-005; SIR-EV-003 L2+) ---


def test_containment_uses_normal_authority_both_ways() -> None:
    """(SIR-INV-005 line 174) Closes no SIR-EV — the real authority separation is +Security."""
    assert s.containment_uses_normal_authority(clean_plan()) is True
    assert s.containment_uses_normal_authority(None) is False


def test_action_missing_any_prerequisite_denies() -> None:
    """(§11 line 327/331) Each of the five separately owned prerequisites is individually required."""
    for field in s.ContainmentAction.PREREQUISITE_FIELDS:
        plan = clean_plan(proposed_actions=(clean_action(**{field: None}),))
        assert s.containment_uses_normal_authority(plan) is False


def test_plan_without_exact_bindings_denies() -> None:
    """(§11 line 322) A plan that binds no exact generation / set digest cannot be judged.

    ``_REQUIRED_COVERED`` already makes such a plan un-issuable, so the only way one reaches a consumer
    is the ``model_construct`` escape hatch — which the predicate layer catches (two layers, §2.3).
    """
    for blank in ("incident_generation", "active_set_digest"):
        forged = s.IncidentContainmentPlan.model_construct(
            **{
                "incident_generation": 5,
                "active_set_digest": "set-1-digest",
                "proposed_actions": (),
                "authority_effect": s.AllFalseIncidentAuthority(),
                blank: None,
            }
        )
        assert s.containment_uses_normal_authority(forged) is False


def test_action_free_plan_is_admissible_on_the_action_axis() -> None:
    """(§4.4 no over-sealing) A pure restriction / shutdown plan with no broker-directed action holds.

    The binding axis (§11 line 320-322) and the all-false axis (SIR-INV-001) still apply, so this is not
    a vacuous pass — an action-free plan with a blank binding still denies (above).
    """
    assert s.containment_uses_normal_authority(clean_plan(proposed_actions=())) is True


# --- §6.2 controlled shutdown != broker finality (INV-007; SIR-EV-004 L3+) --


def test_controlled_shutdown_not_broker_finality_both_ways() -> None:
    """(SIR-INV-007 line 182) Closes no SIR-EV — the 10-step ordering proof is L3 +Broker +Security."""
    assert s.controlled_shutdown_not_broker_finality(clean_shutdown_procedure()) is True
    assert s.controlled_shutdown_not_broker_finality(None) is False


def test_missing_any_mandated_prohibition_denies() -> None:
    """(§12 line 354-362) Each of the seven "Shutdown SHALL NOT" items is individually required."""
    assert len(s.SHUTDOWN_PROHIBITIONS) == 7
    for prohibition in s.SHUTDOWN_PROHIBITIONS:
        procedure = clean_shutdown_procedure(
            prohibited=s.SHUTDOWN_PROHIBITIONS - {prohibition}
        )
        assert s.controlled_shutdown_not_broker_finality(procedure) is False


def test_extra_prohibition_is_allowed() -> None:
    """(floor, not cap) A procedure may declare **more** prohibitions, never fewer."""
    procedure = clean_shutdown_procedure(
        prohibited=frozenset(s.SHUTDOWN_PROHIBITIONS) | {"LOCAL_EXTRA_PROHIBITION"}
    )
    assert s.controlled_shutdown_not_broker_finality(procedure) is True


def test_shutdown_step_ordering_must_be_sound() -> None:
    """(§12 line 343-352) Unknown kinds, blank ordinals and non-increasing ordinals all deny."""
    assert len(s.SHUTDOWN_STEP_KINDS) == 10
    unknown_kind = clean_shutdown_procedure(
        ordered_steps=(s.ShutdownStep(step_ordinal=1, step_kind="NOT_AN_ADR_STEP"),)
    )
    assert s.controlled_shutdown_not_broker_finality(unknown_kind) is False
    blank_ordinal = clean_shutdown_procedure(
        ordered_steps=(
            s.ShutdownStep(step_ordinal=None, step_kind=s.SHUTDOWN_STEP_KINDS[0]),
        )
    )
    assert s.controlled_shutdown_not_broker_finality(blank_ordinal) is False
    repeated = clean_shutdown_procedure(
        ordered_steps=(
            s.ShutdownStep(step_ordinal=1, step_kind=s.SHUTDOWN_STEP_KINDS[0]),
            s.ShutdownStep(step_ordinal=1, step_kind=s.SHUTDOWN_STEP_KINDS[1]),
        )
    )
    assert s.controlled_shutdown_not_broker_finality(repeated) is False


def test_step_free_procedure_still_needs_deny_before_stop() -> None:
    """(§4.4 no over-sealing) A step-free procedure is judged on its remaining axes, not waved through."""
    assert (
        s.controlled_shutdown_not_broker_finality(
            clean_shutdown_procedure(ordered_steps=())
        )
        is True
    )
    assert (
        s.controlled_shutdown_not_broker_finality(
            clean_shutdown_procedure(ordered_steps=(), deny_before_stop=None)
        )
        is False
    )


# --- §6.3 recovery revives nothing (SIR-INV-015; SIR-EV-012 L2+) -----------


def test_recovery_revives_nothing_both_ways() -> None:
    """(SIR-INV-015 line 214) Closes no SIR-EV — hard fencing / Recovery Session are sbr and +Security."""
    assert s.recovery_revives_nothing(clean_revival_inputs()) is True
    assert s.recovery_revives_nothing(None) is False
    for field in s.RecoveryRevivalInputs.REVIVAL_FIELDS:
        assert (
            s.recovery_revives_nothing(clean_revival_inputs(**{field: True})) is False
        )


def test_dominating_open_incident_is_structurally_derived() -> None:
    """(§3.6) The incident half is derived from member structure, never from a self-reported flag."""
    all_closed = clean_active_set(
        members=(
            clean_member(
                incident_id="inc-open", lifecycle_state=s.IncidentLifecycleState.CLOSED
            ),
            clean_member(
                incident_id="inc-closed",
                lifecycle_state=s.IncidentLifecycleState.CLOSED,
            ),
        )
    )
    assert s.dominating_open_incident_present(all_closed) is False
    for state in s.RESTRICTIVE_LIFECYCLE_STATES:
        one_open = clean_active_set(
            members=(
                clean_member(incident_id="inc-open", lifecycle_state=state),
                clean_member(
                    incident_id="inc-closed",
                    lifecycle_state=s.IncidentLifecycleState.CLOSED,
                ),
            )
        )
        assert s.dominating_open_incident_present(one_open) is True


# --- §6.4 obligations survive shutdown (SIR-INV-008; SIR-EV-005 L2+Broker) -


def test_obligations_survive_shutdown_both_ways() -> None:
    """(SIR-INV-008 line 186) Closes no SIR-EV — exit feasibility and late-fill analysis are +Broker."""
    assert s.obligations_survive_shutdown(clean_plan()) is True
    assert s.obligations_survive_shutdown(None) is False
    undisposed = clean_plan(
        protection_obligations=(
            clean_obligation(resolved=None, transferred_with_owner_and_evidence=None),
        )
    )
    assert s.obligations_survive_shutdown(undisposed) is False


def test_a_deliberate_transfer_is_a_lawful_disposition() -> None:
    """(§12 step 5 / §20 item 9) "preserves **or deliberately transfers**" — both paths hold."""
    transferred = clean_plan(
        protection_obligations=(
            clean_obligation(resolved=False, transferred_with_owner_and_evidence=True),
        )
    )
    assert s.obligations_survive_shutdown(transferred) is True


# --- §6.5 / §6.6 / §6.7 UNKNOWN + broker finality (SIR-EV-006 L2+Broker) ---


def test_unknown_remains_conservative_both_ways() -> None:
    """(SIR-INV-009 line 190) Closes no SIR-EV — worst-credible quantification is rcl and +Broker."""
    assert s.unknown_remains_conservative(clean_unknown_state()) is True
    assert s.unknown_remains_conservative(None) is False
    assert len(s.IncidentUnknownState.UNKNOWN_FIELDS) == 10
    for field in s.IncidentUnknownState.UNKNOWN_FIELDS:
        assert (
            s.unknown_remains_conservative(clean_unknown_state(**{field: True}))
            is False
        )


def test_broker_finality_unchanged_both_ways() -> None:
    """(SIR-INV-010 line 194) Closes no SIR-EV — broker-finality quantification is +Broker."""
    assert s.broker_finality_unchanged(clean_broker_tokens()) is True
    assert s.broker_finality_unchanged(None) is False
    assert (
        s.broker_finality_unchanged(
            clean_broker_tokens(missing_ack_treated_as_non_acceptance=True)
        )
        is False
    )
    assert (
        s.broker_finality_unchanged(
            clean_broker_tokens(cancel_ack_treated_as_final_quantity_proof=True)
        )
        is False
    )


def test_final_quantity_proof_is_not_a_conjunct_of_broker_finality_unchanged() -> None:
    """(§6.6 honesty) "the rules are unchanged" is a different claim from "this attempt is final"."""
    assert (
        s.broker_finality_unchanged(
            clean_broker_tokens(final_quantity_proof_present=True)
        )
        is True
    )
    assert (
        s.broker_finality_unchanged(
            clean_broker_tokens(final_quantity_proof_present=None)
        )
        is True
    )


# --- §6.8 / §6.9 closure (SIR-EV-010 L2+Security) --------------------------


def test_closure_independence_both_ways() -> None:
    """(SIR-INV-016 line 217-218) Closes no SIR-EV — quorum counting is hag and +Security."""
    assert (
        s.closure_independence_non_self_exemption(clean_independence_ladder()) is True
    )
    assert s.closure_independence_non_self_exemption(None) is False


def test_unresolved_role_identity_denies() -> None:
    """(SIR-INV-016 line 218) An unresolved role identity is unknown independence ⇒ deny."""
    for field in s.ClosureIndependenceLadder.ROLE_FIELDS:
        ladder = clean_independence_ladder(**{field: None})
        assert s.closure_independence_non_self_exemption(ladder) is False


def test_single_natural_person_needs_the_governed_variant() -> None:
    """(§20 item 10 / patch v0.2) Fewer than two distinct principals needs the approved variant.

    The role-string comparison is a **necessary-but-not-sufficient auxiliary hint**: two distinct role
    strings can still be one natural person behind two accounts, which is why the injected hag collapse
    verdict is ANDed and dominates (``hag/predicates.py:213-214``).
    """
    solo = dict.fromkeys(s.ClosureIndependenceLadder.ROLE_FIELDS, "person-a")
    without_variant = clean_independence_ladder(
        **solo, single_operator_variant_supplies_second=False
    )
    assert s.closure_independence_non_self_exemption(without_variant) is False
    with_variant = clean_independence_ladder(
        **solo, single_operator_variant_supplies_second=True
    )
    assert s.closure_independence_non_self_exemption(with_variant) is True
    unknown_variant = clean_independence_ladder(
        **solo, single_operator_variant_supplies_second=None
    )
    assert s.closure_independence_non_self_exemption(unknown_variant) is False


def test_the_variant_does_not_relax_the_other_obligations() -> None:
    """(SIR-INV-016 line 218) The variant "adds a satisfaction path" — it relaxes nothing else."""
    solo = dict.fromkeys(s.ClosureIndependenceLadder.ROLE_FIELDS, "person-a")
    collapsed = clean_independence_ladder(
        **solo,
        single_operator_variant_supplies_second=True,
        principals_collapsed=True,
    )
    assert s.closure_independence_non_self_exemption(collapsed) is False
    unresolved = clean_independence_ladder(
        **solo,
        single_operator_variant_supplies_second=True,
        independence_resolved=None,
    )
    assert s.closure_independence_non_self_exemption(unresolved) is False


# --- §6 recovery handoff + §6b thin models ---------------------------------


def test_recovery_handoff_requires_an_accepted_barrier() -> None:
    """(§5.9 line 142 / §21 line 511) No obligation transfers without both sbr verdicts."""
    assert s.recovery_handoff_requires_accepted_barrier(clean_handoff()) is True
    assert s.recovery_handoff_requires_accepted_barrier(None) is False
    assert (
        s.recovery_handoff_requires_accepted_barrier(
            clean_handoff(recovery_barrier_closed=None)
        )
        is False
    )


def test_external_activity_conservative_both_ways() -> None:
    """(§15 line 405-412) Closes no SIR-EV — external procedure / custody is +Broker +Security."""
    assert s.external_activity_conservative(clean_external_activity()) is True
    assert s.external_activity_conservative(None) is False
    assert (
        s.external_activity_conservative(
            clean_external_activity(retroactively_compliant_transmission=True)
        )
        is False
    )


def test_send_race_permutation_model() -> None:
    """(§16 line 431) Closes no SIR-EV — cache-free currentness and the deny latch are +Security."""
    # a provable RESTRICT < SEND with no recorded first byte is the ONLY clearing case
    assert s.attempt_potentially_live(1, 2, None, True) is False
    # ordering unprovable ⇒ potentially live even with a Final Quantity Proof
    assert s.attempt_potentially_live(None, 2, None, True) is True
    assert s.attempt_potentially_live(1, None, None, True) is True
    # SEND < RESTRICT — the §16 line 431 race ⇒ potentially live
    assert s.attempt_potentially_live(2, 1, None, True) is True
    # a recorded first broker byte contradicts the deny ⇒ potentially live (strictly conservative)
    assert s.attempt_potentially_live(1, 2, 3, True) is True
    # without the proof, nothing clears
    assert s.attempt_potentially_live(1, 2, None, False) is True


def test_equal_generation_race_is_potentially_live() -> None:
    """(§16 line 431, the AMBIGUOUS bucket) An **equal** generation is unproven, never a clearance.

    ``compare_order`` reports two equal ordering scalars as ``AMBIGUOUS``, not ``BEFORE``. A model that
    excluded the known-bad orderings instead of demanding the positive proof would fold "cannot be
    proven" into the same bucket as "restriction first" and clear the race — the exact §16 line 431
    inversion ("ordering **cannot be proven**, the attempt is potentially live").
    """
    assert s.incident_generation_advances(5, 5) is False  # AMBIGUOUS, not BEFORE
    assert s.attempt_potentially_live(5, 5, 6, True) is True
    assert s.attempt_potentially_live(5, 5, None, True) is True
    # and the "is the restriction provably first?" question answers False without clearing anything
    assert s.restriction_dominates_send(5, 5) is False


def test_step_completion_is_never_assumed() -> None:
    """(§17 line 451) An ambiguous shutdown step is treated as **not** completed."""
    kind = s.SHUTDOWN_STEP_KINDS[0]
    assert (
        s.step_completion_proven(
            s.ShutdownStep(step_ordinal=1, step_kind=kind, completed=True)
        )
        is True
    )
    for ambiguous in (False, None):
        assert (
            s.step_completion_proven(
                s.ShutdownStep(step_ordinal=1, step_kind=kind, completed=ambiguous)
            )
            is False
        )
    assert s.step_completion_proven(None) is False


def test_final_quantity_proof_absent_is_conservative() -> None:
    """(§20 item 3 / §13 line 376) No positive proof ⇒ the capacity-covered obligation stands."""
    assert s.final_quantity_proof_absent(None) is True
    assert s.final_quantity_proof_absent(clean_broker_tokens()) is True
    assert (
        s.final_quantity_proof_absent(
            clean_broker_tokens(final_quantity_proof_present=None)
        )
        is True
    )
    assert (
        s.final_quantity_proof_absent(
            clean_broker_tokens(final_quantity_proof_present=True)
        )
        is False
    )
