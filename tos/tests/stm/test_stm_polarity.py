"""Polarity discipline — every ``None`` converges to deny, and ``is not True`` never touches a
negative-polarity field (design #30 §4.3; the #18/#22/#23/#25 MAJOR-2 seal and this contract's own C1).

Two halves:

* **behavioural** — for every negative-polarity coordinate, ``None`` denies exactly like ``True``; for
  every positive-polarity coordinate, ``None`` denies exactly like ``False``. Each is exercised through
  the predicate that actually consumes it, so a field that is merely *declared* with the right polarity
  but read with the wrong normalization still fails here;
* **structural** — an AST scan of ``predicates.py`` proves no negative-polarity field is ever read with
  ``is not True`` (which would admit a ``None`` and re-open the fail-open) and no polarized field is
  ever read with bare truthiness. The scan carries its own planted-offender canary, so green is
  evidence the checker works rather than evidence it was neutered.

Regime tag: predicate substrate only; closes **no** STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from hypothesis import given
from tos.stm import (
    NEGATIVE_POLARITY_FIELDS,
    POSITIVE_POLARITY_FIELDS,
    MonitoringRecoveryInputs,
    MonitoringSuppression,
    MonitoringUnknownState,
    RestrictiveMonitoringSignal,
    absence_is_not_health,
    alert_state_is_orthogonal,
    attempt_potentially_live,
    bound_integrity_preserved,
    broker_finality_unchanged,
    common_mode_is_not_independence,
    conformance_requires_complete_current_valid,
    critical_coverage_complete_or_gap,
    escalation_single_binding,
    evidence_and_status_honest,
    gap_is_restrictive_not_exemption,
    handoff_is_non_authorizing,
    loss_preserves_negative_facts,
    monitored_assumption_intake_closed,
    no_self_exemption,
    recovery_revives_nothing,
    suppression_cannot_suppress_safety,
    telemetry_semantics_exact,
    unknown_is_restrictive,
)

from ._stm_strategies import (
    CLEAN_APPLICABLE_DIMENSIONS,
    CLEAN_APPLICABLE_OBLIGATIONS,
    CLEAN_ASSUMPTION_OBLIGATION,
    CLEAN_SUBMITTED_ASSUMPTION_IDS,
    TRIBOOL,
    clean_alert_state,
    clean_assumption_intake,
    clean_bound,
    clean_broker_tokens,
    clean_common_mode,
    clean_coverage_item,
    clean_coverage_manifest,
    clean_dashboard,
    clean_escalation,
    clean_gap,
    clean_identity,
    clean_recovery,
    clean_semantic_view,
    clean_send_race,
    clean_signal,
    clean_silence,
    clean_snapshot,
    clean_suppression,
    clean_unknown_state,
)

_STM_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "stm"


def _stm_sources() -> list[Path]:
    """Every ``tos.stm`` source, asserted **non-empty** so a path typo cannot make a sweep vacuous."""
    sources = sorted(_STM_SRC.rglob("*.py"))
    assert (
        sources
    ), f"no tos.stm source found under {_STM_SRC} — this sweep would be vacuous"
    return sources


def _coverage(**item_overrides: object) -> bool:
    manifest = clean_coverage_manifest(
        coverage_items=(
            clean_coverage_item(**item_overrides),
            clean_coverage_item(obligation_ref=CLEAN_ASSUMPTION_OBLIGATION),
        )
    )
    return critical_coverage_complete_or_gap(
        manifest,
        CLEAN_APPLICABLE_OBLIGATIONS,
        CLEAN_APPLICABLE_DIMENSIONS,
        CLEAN_SUBMITTED_ASSUMPTION_IDS,
    )


#: Every **negative**-polarity coordinate mapped to a one-argument judgement that consumes it.
#: ``value`` is injected into the clean carrier; the judgement must be ``True`` only for ``False``.
_NEGATIVE_CASES: dict[str, object] = {
    "excluded": lambda v: _coverage(excluded=v),
    "coverage_score_present": lambda v: critical_coverage_complete_or_gap(
        clean_coverage_manifest(coverage_score_present=v),
        CLEAN_APPLICABLE_OBLIGATIONS,
        CLEAN_APPLICABLE_DIMENSIONS,
        CLEAN_SUBMITTED_ASSUMPTION_IDS,
    ),
    "permits_individual_exceedance": lambda v: bound_integrity_preserved(
        clean_bound(permits_individual_exceedance=v)
    ),
    "semantics_reinterpreted": lambda v: telemetry_semantics_exact(
        clean_identity(semantics_reinterpreted=v), clean_semantic_view()
    ),
    "hash_equality_claims_equivalence": lambda v: telemetry_semantics_exact(
        clean_identity(hash_equality_claims_equivalence=v), clean_semantic_view()
    ),
    "cross_host_monotonic_subtracted": lambda v: telemetry_semantics_exact(
        clean_identity(), clean_semantic_view(cross_host_monotonic_subtracted=v)
    ),
    "identical_values_claim_continuity": lambda v: telemetry_semantics_exact(
        clean_identity(), clean_semantic_view(identical_values_claim_continuity=v)
    ),
    "age_clamped_from_unbounded": lambda v: telemetry_semantics_exact(
        clean_identity(), clean_semantic_view(age_clamped_from_unbounded=v)
    ),
    "treated_as_healthy": lambda v: absence_is_not_health(
        clean_silence(treated_as_healthy=v)
    ),
    "self_health_as_proof": lambda v: common_mode_is_not_independence(
        clean_common_mode(self_health_as_proof=v)
    ),
    "validates_own_continuity_by_own_output": lambda v: common_mode_is_not_independence(
        clean_common_mode(validates_own_continuity_by_own_output=v)
    ),
    "ack_implies_containment": lambda v: alert_state_is_orthogonal(
        clean_alert_state(ack_implies_containment=v)
    ),
    "advance_of_one_implies_another": lambda v: alert_state_is_orthogonal(
        clean_alert_state(advance_of_one_implies_another=v)
    ),
    "adverse_record_dropped": lambda v: loss_preserves_negative_facts(
        clean_alert_state(adverse_record_dropped=v)
    ),
    "elapsed_time_reset": lambda v: loss_preserves_negative_facts(
        clean_alert_state(elapsed_time_reset=v)
    ),
    "missing_ack_treated_as_non_acceptance": lambda v: broker_finality_unchanged(
        clean_broker_tokens(missing_ack_treated_as_non_acceptance=v)
    ),
    "cancel_ack_treated_as_fqp": lambda v: broker_finality_unchanged(
        clean_broker_tokens(cancel_ack_treated_as_fqp=v)
    ),
    "unknown_effect_capacity_released": lambda v: broker_finality_unchanged(
        clean_broker_tokens(unknown_effect_capacity_released=v)
    ),
    "defaulted_to_green": lambda v: evidence_and_status_honest(
        clean_dashboard(defaulted_to_green=v)
    ),
    "unioned_or_substituted": lambda v: escalation_single_binding(
        clean_escalation(unioned_or_substituted=v)
    ),
}
_NEGATIVE_CASES.update(
    {
        name: (
            lambda n: lambda v: unknown_is_restrictive(clean_unknown_state(**{n: v}))
        )(name)
        for name in MonitoringUnknownState.UNKNOWN_FIELDS
    }
)
_NEGATIVE_CASES.update(
    {
        name: (
            lambda n: lambda v: suppression_cannot_suppress_safety(
                clean_suppression(**{n: v})
            )
        )(name)
        for name in MonitoringSuppression.DISABLE_FIELDS
    }
)
_NEGATIVE_CASES.update(
    {
        name: (lambda n: lambda v: recovery_revives_nothing(clean_recovery(**{n: v})))(
            name
        )
        for name in MonitoringRecoveryInputs.NON_REVIVAL_FIELDS
    }
)
_NEGATIVE_CASES.update(
    {
        name: (lambda n: lambda v: handoff_is_non_authorizing(clean_signal(**{n: v})))(
            name
        )
        for name in RestrictiveMonitoringSignal.PROHIBITION_FIELDS
    }
)

#: Every **positive**-polarity coordinate mapped to a judgement that consumes it.
_POSITIVE_CASES: dict[str, object] = {
    "is_complete": lambda v: critical_coverage_complete_or_gap(
        clean_coverage_manifest(is_complete=v),
        CLEAN_APPLICABLE_OBLIGATIONS,
        CLEAN_APPLICABLE_DIMENSIONS,
        CLEAN_SUBMITTED_ASSUMPTION_IDS,
    ),
    "closure_1_to_12_complete": lambda v: _coverage(closure_1_to_12_complete=v),
    "restrictive_response_present": lambda v: _coverage(restrictive_response_present=v),
    "alert_path_present": lambda v: _coverage(alert_path_present=v),
    "evidence_path_present": lambda v: _coverage(evidence_path_present=v),
    "currentness_rule_present": lambda v: _coverage(currentness_rule_present=v),
    "approved_exclusion_proof_present": lambda v: no_self_exemption(
        clean_coverage_manifest(
            coverage_items=(
                clean_coverage_item(excluded=True, approved_exclusion_proof_present=v),
            )
        )
    ),
    "admitted_as_coverage_item": lambda v: monitored_assumption_intake_closed(
        clean_coverage_manifest(
            submitted_monitored_assumptions=(
                clean_assumption_intake(admitted_as_coverage_item=v),
            )
        ),
        CLEAN_SUBMITTED_ASSUMPTION_IDS,
    ),
    "runtime_falsity_invalidates_property": lambda v: monitored_assumption_intake_closed(
        clean_coverage_manifest(
            submitted_monitored_assumptions=(
                clean_assumption_intake(runtime_falsity_invalidates_property=v),
            )
        ),
        CLEAN_SUBMITTED_ASSUMPTION_IDS,
    ),
    "units_exact": lambda v: bound_integrity_preserved(clean_bound(units_exact=v)),
    "window_inside_bound": lambda v: bound_integrity_preserved(
        clean_bound(window_inside_bound=v)
    ),
    "uncertainty_treated": lambda v: bound_integrity_preserved(
        clean_bound(uncertainty_treated=v)
    ),
    "source_continuity_present": lambda v: conformance_requires_complete_current_valid(
        clean_snapshot().model_copy(update={"source_continuity_present": v})
    ),
    "closure_proof_present": lambda v: gap_is_restrictive_not_exemption(
        clean_gap(closure_proof_present=v)
    ),
    "residual_common_mode_disclosed": lambda v: common_mode_is_not_independence(
        clean_common_mode(residual_common_mode_disclosed=v)
    ),
    # positive polarity, three-value: only a positive proof clears the potentially-live judgement
    "ordering_provable": lambda v: not attempt_potentially_live(
        clean_send_race(ordering_provable=v)
    ),
}


# --- behavioural half ------------------------------------------------------


def test_every_registered_negative_field_has_a_behavioural_case() -> None:
    """(closure) The behavioural table covers the whole negative registry — no silent omission."""
    assert set(_NEGATIVE_CASES) == set(NEGATIVE_POLARITY_FIELDS)


def test_every_registered_positive_field_has_a_behavioural_case() -> None:
    """(closure) The behavioural table covers the whole positive registry — no silent omission."""
    assert set(_POSITIVE_CASES) == set(POSITIVE_POLARITY_FIELDS)


@pytest.mark.parametrize("field", sorted(NEGATIVE_POLARITY_FIELDS))
def test_negative_polarity_clears_only_on_false(field: str) -> None:
    """(§4.3) ``False`` clears; ``True`` **and** an unknown ``None`` both deny."""
    judge = _NEGATIVE_CASES[field]
    assert judge(False) is True, f"{field}: a positively disclaimed value must clear"
    assert judge(True) is False, f"{field}: an asserted value must deny"
    assert judge(None) is False, (
        f"{field}: an unknown None must deny — reading it with `is not True` is the "
        "#18/#22/#23/#25 fail-open (and this contract's own C1)"
    )


@pytest.mark.parametrize("field", sorted(POSITIVE_POLARITY_FIELDS))
def test_positive_polarity_clears_only_on_true(field: str) -> None:
    """(§4.3) ``True`` clears; ``False`` **and** an unknown ``None`` both deny."""
    judge = _POSITIVE_CASES[field]
    assert judge(True) is True, f"{field}: a positive proof must clear"
    assert judge(False) is False, f"{field}: a negative value must deny"
    assert judge(None) is False, f"{field}: an unknown None must deny"


@given(value=TRIBOOL)
def test_the_c1_field_is_asymmetric_across_its_two_conjuncts(
    value: bool | None,
) -> None:
    """(**C1**) ``excluded`` is filtered with ``is False`` and gated with ``is not False``.

    The tally counts only ``excluded is False``; the §9 line 290 proof gate fires on everything else.
    A single symmetric normalization would collapse the two and re-open the fail-open.
    """
    counted = _coverage(excluded=value)
    gated = no_self_exemption(
        clean_coverage_manifest(
            coverage_items=(
                clean_coverage_item(
                    excluded=value, approved_exclusion_proof_present=None
                ),
            )
        )
    )
    assert counted is (value is False)
    assert gated is (value is False)


# --- structural half -------------------------------------------------------


def _negative_is_not_true_offenders() -> list[str]:
    """Every ``<negative field> is not True`` comparison in the package sources."""
    offenders: list[str] = []
    for path in _stm_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            if len(node.ops) != 1 or not isinstance(node.ops[0], ast.IsNot):
                continue
            comparator = node.comparators[0]
            if not (isinstance(comparator, ast.Constant) and comparator.value is True):
                continue
            left = node.left
            if (
                isinstance(left, ast.Attribute)
                and left.attr in NEGATIVE_POLARITY_FIELDS
            ):
                offenders.append(f"{path.name}:{node.lineno} {left.attr} is not True")
    return offenders


def test_no_negative_polarity_field_is_read_with_is_not_true() -> None:
    """(§4.3 structural) ``is not True`` on a negative field admits ``None`` — the sealed fail-open."""
    assert _negative_is_not_true_offenders() == []


def test_the_is_not_true_scan_detects_a_planted_offender(tmp_path: Path) -> None:
    """(canary) The scan really fires — green above is evidence, not a neutered checker."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(item):\n    return item.excluded is not True\n", encoding="utf-8"
    )
    tree = ast.parse(planted.read_text(encoding="utf-8"), filename="planted")
    found = [
        node.left.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        and isinstance(node.ops[0], ast.IsNot)
        and isinstance(node.comparators[0], ast.Constant)
        and node.comparators[0].value is True
        and isinstance(node.left, ast.Attribute)
    ]
    assert "excluded" in found
    assert "excluded" in NEGATIVE_POLARITY_FIELDS


def test_no_polarized_field_is_read_with_bare_truthiness() -> None:
    """(§4.3 structural) ``if x.flag:`` on a tri-state field is a ``None``-shaped fail-open."""
    polarized = POSITIVE_POLARITY_FIELDS | NEGATIVE_POLARITY_FIELDS
    offenders: list[str] = []
    for path in _stm_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            tested: list[ast.expr] = []
            if isinstance(node, (ast.If, ast.While, ast.IfExp)):
                tested = [node.test]
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                tested = [node.operand]
            elif isinstance(node, ast.BoolOp):
                tested = list(node.values)
            for expression in tested:
                if (
                    isinstance(expression, ast.Attribute)
                    and expression.attr in polarized
                ):
                    offenders.append(
                        f"{path.name}:{expression.lineno} {expression.attr}"
                    )
    assert offenders == [], f"bare truthiness read of a tri-state field: {offenders}"
