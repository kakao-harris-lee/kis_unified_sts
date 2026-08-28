"""Malformed-model self-defence — the coexistence seals and their predicate second layer (§2.3).

Three construction-time seals, each about a **missing structure** rather than a flag's value (design
#30 §2.3, the #20 lesson):

* ``ContinuousConformanceSnapshot`` — a ``CONFORMING`` result coexisting with an absent §12 line
  324-333 binding, no bound monitor result, an unknown source-continuity fact, or a recorded active
  violation / unknown / gap / delivery failure;
* ``MonitorCoverageManifest`` — an ``is_complete`` claim coexisting with an absent identity /
  generation / policy binding, a coverage item with no obligation reference, or a submitted Monitored
  Assumption with no id;
* ``AlertEscalationRecord`` — delivery attempts / escalation stages / handoffs coexisting with no
  ``bound_alert_id`` (§5.9 line 143 "bound to **exactly one** Safety Alert Record").

Each is then re-caught in the predicate layer for a ``model_construct`` bypass (defence in depth) —
which is the whole point of the second layer, since ``model_construct`` skips every validator.

Regime tag: predicate substrate only; closes **no** STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
from tos.stm import (
    AggregateConformanceResult,
    AlertEscalationRecord,
    ArtifactIntegrityError,
    ContinuousConformanceSnapshot,
    MonitorCoverageManifest,
    conformance_requires_complete_current_valid,
    critical_coverage_complete_or_gap,
    escalation_single_binding,
)

from ._stm_strategies import (
    CLEAN_APPLICABLE_DIMENSIONS,
    CLEAN_APPLICABLE_OBLIGATIONS,
    CLEAN_SUBMITTED_ASSUMPTION_IDS,
    clean_assumption_intake,
    clean_coverage_item,
    clean_coverage_manifest,
    clean_escalation,
    clean_evaluation,
    clean_snapshot,
)

_SNAPSHOT_BINDINGS = (
    "snapshot_id",
    "snapshot_generation",
    "monitor_generation",
    "policy_digest",
    "critical_telemetry_manifest_digest",
    "coverage_manifest_digest",
    "scope",
    "owner_epoch",
)


# --- ContinuousConformanceSnapshot ----------------------------------------


@pytest.mark.parametrize("binding", _SNAPSHOT_BINDINGS)
def test_conforming_with_a_missing_binding_is_unconstructable(binding: str) -> None:
    """(§2.3; §12 line 335) A ``CONFORMING`` claim with a blank §12 binding cannot exist."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_snapshot(**{binding: None})


def test_conforming_with_no_monitor_result_is_unconstructable() -> None:
    """(§12 line 329) "every required monitor and result" — an empty query proves nothing."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_snapshot(monitor_results=())


def test_conforming_with_unknown_source_continuity_is_unconstructable() -> None:
    """(§12 line 330) UNKNOWN is restrictive (STM-INV-005 line 175) — it cannot back a CONFORMING."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_snapshot(source_continuity_present=None)


@pytest.mark.parametrize(
    "adverse",
    ["active_violations", "active_unknowns", "active_gaps", "delivery_failures"],
)
def test_conforming_with_an_adverse_record_is_unconstructable(adverse: str) -> None:
    """(§12 line 335) ``CONFORMING`` requires **every** required item current, complete and valid."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_snapshot(**{adverse: ("adverse-1",)})


def test_a_false_source_continuity_stays_constructable() -> None:
    """(§2.3) The seal is about *missing structure*, never a flag's value — the gate stays testable."""
    snapshot = clean_snapshot(
        aggregate_result=AggregateConformanceResult.RESTRICTED,
        source_continuity_present=False,
    )
    assert snapshot.source_continuity_present is False


def test_active_suppressions_do_not_block_a_conforming_snapshot() -> None:
    """(§15) A governed suppression that disables nothing is compatible with ``CONFORMING``."""
    snapshot = clean_snapshot(active_suppressions=("suppression-1",))
    assert conformance_requires_complete_current_valid(snapshot) is True


@pytest.mark.parametrize("binding", _SNAPSHOT_BINDINGS)
def test_the_predicate_catches_a_model_construct_snapshot(binding: str) -> None:
    """(second layer, §2.3) ``model_construct`` skips the validator — the predicate does not."""
    forged = ContinuousConformanceSnapshot.model_construct(
        **{
            **dict.fromkeys(_SNAPSHOT_BINDINGS, "x"),
            "monitor_results": (clean_evaluation(),),
            "source_continuity_present": True,
            "active_violations": (),
            "active_unknowns": (),
            "active_gaps": (),
            "delivery_failures": (),
            "aggregate_result": AggregateConformanceResult.CONFORMING,
            binding: None,
        }
    )
    assert conformance_requires_complete_current_valid(forged) is False


def test_the_predicate_catches_a_model_construct_empty_result_set() -> None:
    """(second layer) A forged ``CONFORMING`` snapshot with no monitor result still denies."""
    forged = clean_snapshot().model_copy(update={"monitor_results": ()})
    assert forged.aggregate_result is AggregateConformanceResult.CONFORMING
    assert conformance_requires_complete_current_valid(forged) is False


@pytest.mark.parametrize(
    "adverse",
    ["active_violations", "active_unknowns", "active_gaps", "delivery_failures"],
)
def test_the_predicate_catches_a_model_copy_adverse_record(adverse: str) -> None:
    """(second layer) ``model_copy`` also bypasses the validator; the predicate re-derives the fact."""
    forged = clean_snapshot().model_copy(update={adverse: ("adverse-1",)})
    assert conformance_requires_complete_current_valid(forged) is False


# --- MonitorCoverageManifest ----------------------------------------------


@pytest.mark.parametrize(
    "binding", ["coverage_manifest_id", "coverage_generation", "policy_digest"]
)
def test_complete_claim_with_a_missing_binding_is_unconstructable(binding: str) -> None:
    """(§2.3; §5.4 line 123) A "complete and exact" mapping needs its exact identity binding."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_coverage_manifest(**{binding: None})


def test_complete_claim_with_an_unreferenced_item_is_unconstructable() -> None:
    """(§5.4 line 123) A complete mapping cannot contain an item that maps no obligation."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_coverage_manifest(
            coverage_items=(clean_coverage_item(obligation_ref=None),)
        )


def test_complete_claim_with_an_unidentified_assumption_is_unconstructable() -> None:
    """(§9 line 288) An intake with no id would be the out-of-band addition the patch forbids."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_coverage_manifest(
            submitted_monitored_assumptions=(
                clean_assumption_intake(assumption_id=None),
            )
        )


def test_an_incomplete_manifest_may_carry_anything() -> None:
    """(§2.3) With no completeness claim there is no coexistence to seal — the gate stays testable."""
    manifest = clean_coverage_manifest(
        is_complete=False,
        coverage_items=(clean_coverage_item(obligation_ref=None),),
    )
    assert manifest.is_complete is False


def test_the_predicate_catches_a_model_construct_manifest() -> None:
    """(second layer, §2.3) A forged complete manifest with a blank item still denies."""
    forged = MonitorCoverageManifest.model_construct(
        coverage_manifest_id="coverage-manifest-1",
        coverage_generation=7,
        policy_digest="policy-digest-1",
        coverage_items=(clean_coverage_item(obligation_ref=None),),
        approved_exclusions=(),
        submitted_monitored_assumptions=(),
        is_complete=True,
        coverage_score_present=False,
    )
    assert (
        critical_coverage_complete_or_gap(
            forged,
            CLEAN_APPLICABLE_OBLIGATIONS,
            CLEAN_APPLICABLE_DIMENSIONS,
            CLEAN_SUBMITTED_ASSUMPTION_IDS,
        )
        is False
    )


# --- AlertEscalationRecord -------------------------------------------------


@pytest.mark.parametrize(
    "content", ["ordered_delivery_attempts", "escalation_stages", "handoffs"]
)
def test_unbound_escalation_content_is_unconstructable(content: str) -> None:
    """(§5.9 line 143) An escalation record bound to no alert could be unioned across alerts."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        AlertEscalationRecord(
            escalation_id="escalation-1",
            escalation_generation=7,
            bound_alert_id=None,
            **{content: ("value-1",)},
        )


def test_an_empty_unbound_escalation_is_constructable_but_denies() -> None:
    """(§2.3) The seal covers *content*; the predicate covers the binding claim itself."""
    empty = AlertEscalationRecord(escalation_id="escalation-1", escalation_generation=7)
    assert empty.bound_alert_id is None
    assert escalation_single_binding(empty) is False


@pytest.mark.parametrize("placeholder", [None, "", "TBD"])
def test_a_placeholder_binding_denies(placeholder: str | None) -> None:
    """(§5.9 line 143) A blank or template binding is not "exactly one Safety Alert Record"."""
    forged = clean_escalation().model_copy(update={"bound_alert_id": placeholder})
    assert escalation_single_binding(forged) is False


@pytest.mark.parametrize("value", [True, None])
def test_a_unioned_or_substituted_record_denies(value: bool | None) -> None:
    """(§5.9 line 143, negative polarity) ``is not False`` denies — ``None`` included."""
    assert (
        escalation_single_binding(clean_escalation(unioned_or_substituted=value))
        is False
    )


def test_absent_escalation_denies() -> None:
    """(∅-seal) ``None`` is undecidable, therefore denied."""
    assert escalation_single_binding(None) is False


@pytest.mark.parametrize(
    "placeholder",
    [
        "",
        "   ",
        "TBD",
        "tbd",
        " Tbd ",
        "N/A",
        "n/a",
        "na",
        "None",
        "null",
        "-",
        "?",
        "UNKNOWN",
        "todo",
    ],
)
def test_a_normalized_placeholder_binding_denies(placeholder: str) -> None:
    """(MINOR-1) The template-placeholder check normalizes case and whitespace before comparing.

    A raw ``in ("", "TBD")`` membership test let ``"  "`` / ``"tbd"`` / ``"N/A"`` through as if they
    were concrete alert ids (the #25 RLP ``is_wildcard_value`` lesson). The denylist is **honestly
    non-exhaustive** — no list of texts can be complete — but it catches every canonical template
    marker this codebase and the spec templates emit.
    """
    forged = clean_escalation().model_copy(update={"bound_alert_id": placeholder})
    assert escalation_single_binding(forged) is False


def test_a_concrete_binding_that_merely_contains_a_placeholder_word_still_clears() -> (
    None
):
    """(MINOR-1, both ways) The check is exact-after-normalization, never a substring match."""
    for concrete in ("alert-tbd-7", "TBD-1", "unknown-source-alert", "alert-1"):
        forged = clean_escalation().model_copy(update={"bound_alert_id": concrete})
        assert escalation_single_binding(forged) is True
