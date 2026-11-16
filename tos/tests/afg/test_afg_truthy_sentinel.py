"""Truthy-sentinel property — both axes (design #16 §2.2-1 / §7; the #13 ARE lesson)."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from tos.afg import (
    ADMISSIBILITY_ADMISSIBLE,
    ActionFlowResult,
    ActionFlowScopeKind,
    action_flow_decision,
    partition_lease_exclusive,
)

from .._truthiness_scan import package_truthiness_offenders
from ._afg_strategies import (
    ACTION_FLOW_RESULT_OR_FORGERY,
    ACTION_FLOW_RESULTS,
    SCHEME,
    TRIBOOL,
    TRUTHY_NON_BOOL,
    flow_vector,
    limit_vector,
)

_SUSPICIOUS = frozenset(
    {
        "result",
        "coverage",
        "verdict",
        "lease_admissible",
        "admissibility",
        "scope_complete",
        "lineage_complete",
        "amplification_ok",
        "envelope_ok",
        "generation_current",
    }
)


def test_every_action_flow_result_member_is_truthy() -> None:
    """(the trap itself) All three members are truthy — a bare ``if result:`` is unsafe."""
    for member in ActionFlowResult:
        assert (
            bool(member) is True
        ), f"{member} is truthy — identity gating is mandatory"


@given(coverage=ACTION_FLOW_RESULTS)
def test_only_grant_coverage_can_yield_a_grant(coverage: ActionFlowResult) -> None:
    """(axis 1) A non-``GRANT`` coverage never becomes a ``GRANT`` decision."""
    decision = action_flow_decision(
        coverage=coverage,
        scope_complete=True,
        lineage_complete=True,
        amplification_ok=True,
        envelope_ok=True,
        generation_current=True,
        applicable_action_flow_scopes=(ActionFlowScopeKind.BROKER.value,),
        decision_id="afg-dec-truthy",
        decision_generation=1,
        scheme=SCHEME,
        action_flow_vector=flow_vector(magnitude=Decimal("1")),
        decision_effective_limit=limit_vector(),
    )
    if coverage is ActionFlowResult.GRANT:
        assert decision.result is ActionFlowResult.GRANT
    else:
        assert decision.result is not ActionFlowResult.GRANT


def _decide(**overrides: object) -> ActionFlowResult:
    """Issue a decision from a fully-proven baseline with ``overrides`` applied."""
    base: dict[str, object] = {
        "coverage": ActionFlowResult.GRANT,
        "scope_complete": True,
        "lineage_complete": True,
        "amplification_ok": True,
        "envelope_ok": True,
        "generation_current": True,
        "applicable_action_flow_scopes": (ActionFlowScopeKind.BROKER.value,),
        "decision_id": "afg-dec-truthy",
        "decision_generation": 1,
        "scheme": SCHEME,
    }
    base.update(overrides)
    return action_flow_decision(**base).issued_result  # type: ignore[arg-type]


@given(coverage=ACTION_FLOW_RESULT_OR_FORGERY)
def test_only_the_grant_member_itself_can_produce_a_grant(coverage: object) -> None:
    """(C1 regression) ``GRANT`` requires the **member**, never a fall-through residue."""
    verdict = _decide(coverage=coverage)
    if coverage is ActionFlowResult.GRANT:
        assert verdict is ActionFlowResult.GRANT
    else:
        assert verdict is not ActionFlowResult.GRANT


def test_raw_result_strings_are_not_the_members() -> None:
    """(the trap itself) A ``StrEnum`` member equals its value but is not it under ``is``."""
    for member in ActionFlowResult:
        assert member == member.value
        assert member is not member.value
        assert _decide(coverage=member.value) is not ActionFlowResult.GRANT


@given(forged=st.sampled_from(TRUTHY_NON_BOOL))
def test_truthy_non_bool_premise_can_never_reach_a_grant(forged: object) -> None:
    """(M2 regression) Each of the five premises rejects a truthy non-``bool``."""
    for premise in (
        "scope_complete",
        "lineage_complete",
        "amplification_ok",
        "envelope_ok",
        "generation_current",
    ):
        verdict = _decide(**{premise: forged})
        assert (
            verdict is not ActionFlowResult.GRANT
        ), f"{premise}={forged!r} (truthy non-bool) must not reach GRANT"


@given(flag=TRIBOOL)
def test_only_positive_true_premises_reach_a_grant(flag: bool | None) -> None:
    """(M2 regression, tri-bool wiring) ``False`` / ``None`` premises never reach GRANT."""
    for premise in (
        "scope_complete",
        "lineage_complete",
        "amplification_ok",
        "envelope_ok",
        "generation_current",
    ):
        verdict = _decide(**{premise: flag})
        if flag is True:
            assert verdict is ActionFlowResult.GRANT
        else:
            assert verdict is not ActionFlowResult.GRANT


def _lease(token: object) -> bool:
    return partition_lease_exclusive(
        token,  # type: ignore[arg-type]
        3,
        "cont-1",
        reference_continuity_id="cont-1",
        new_normal_permit_during_partition=False,
        lease_refilled_remotely_or_by_wall_clock=False,
        exclusivity_retained=True,
        stale_writer_hard_fenced=True,
    )


def test_only_the_admissible_token_passes_the_lease_gate() -> None:
    """(axis 2, M2) ``TRAPPED`` / ``PROHIBITED`` are truthy but must never pass."""
    assert _lease(ADMISSIBILITY_ADMISSIBLE) is True
    for token in ("TRAPPED", "PROHIBITED"):
        assert bool(token) is True, "the trap: a non-admissible verdict is still truthy"
        assert _lease(token) is False
    assert _lease(None) is False


def test_no_afg_source_uses_bare_truthiness_on_a_result_value() -> None:
    """(source seal) No afg module tests a result-shaped value for bare truthiness."""
    offenders = package_truthiness_offenders("afg", _SUSPICIOUS)
    assert offenders == [], f"truthy-sentinel trap reachable: {offenders}"
