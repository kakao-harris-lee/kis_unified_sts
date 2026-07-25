"""approval_decision — deterministic restrictive decision (design #15 §5.2; IAP-EV-003 substrate, core L1 slice).

determinism property (§4.2): same complete input set + policy + generation + facts => same result
(a pure function, no hidden clock / randomness / registry). restrictive (§11 line 289): missing /
stale / conflicting / unverifiable / unsupported / unknown => DENY / UNKNOWN, never APPROVE.
UNKNOWN cannot be promoted (§11 line 296). both-ways: complete + all-True => APPROVE.

Regime tag: predicate / model substrate only; IAP-EV-003 NOT_IMPLEMENTED (`/3` residue);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.iap import ApprovalResult, approval_decision

from ._iap_strategies import (
    APPROVE_FACTS,
    TRIBOOL,
    complete_request,
    issue_policy,
)


def test_complete_all_true_approves() -> None:
    """(positive side, §11 line 294) Complete request + every fact True + generation => APPROVE."""
    result = approval_decision(complete_request(), issue_policy(), 7, **APPROVE_FACTS)
    assert result is ApprovalResult.APPROVE


@given(
    independent_validation_passed=TRIBOOL,
    all_bindings_current=TRIBOOL,
    policy_supports_request=TRIBOOL,
    generation_current=TRIBOOL,
    conflicting_evaluations=TRIBOOL,
    unverifiable_input=TRIBOOL,
    generation=st.one_of(st.none(), st.integers(min_value=0, max_value=99)),
)
def test_decision_never_approves_on_a_negative(
    independent_validation_passed: bool | None,
    all_bindings_current: bool | None,
    policy_supports_request: bool | None,
    generation_current: bool | None,
    conflicting_evaluations: bool | None,
    unverifiable_input: bool | None,
    generation: int | None,
) -> None:
    """(§11 line 289 restrictive) APPROVE only when every fact is True + generation present — never on a negative."""
    result = approval_decision(
        complete_request(),
        issue_policy(),
        generation,
        independent_validation_passed=independent_validation_passed,
        all_bindings_current=all_bindings_current,
        policy_supports_request=policy_supports_request,
        generation_current=generation_current,
        conflicting_evaluations=conflicting_evaluations,
        unverifiable_input=unverifiable_input,
    )
    all_positive = (
        independent_validation_passed is True
        and all_bindings_current is True
        and policy_supports_request is True
        and generation_current is True
        and conflicting_evaluations is not True
        and unverifiable_input is not True
        and generation is not None
    )
    if result is ApprovalResult.APPROVE:
        assert all_positive, "APPROVE leaked on a missing / stale / conflicting input"
    else:
        # Every non-APPROVE is a denial (DENY or UNKNOWN) — never a permissive fallback.
        assert result in (ApprovalResult.DENY, ApprovalResult.UNKNOWN)


@given(
    independent_validation_passed=TRIBOOL,
    all_bindings_current=TRIBOOL,
    policy_supports_request=TRIBOOL,
    generation_current=TRIBOOL,
    generation=st.one_of(st.none(), st.integers(min_value=0, max_value=99)),
)
def test_decision_is_deterministic(
    independent_validation_passed: bool | None,
    all_bindings_current: bool | None,
    policy_supports_request: bool | None,
    generation_current: bool | None,
    generation: int | None,
) -> None:
    """(§4.2 determinism) The same inputs evaluated twice yield the identical result (pure function)."""
    request, policy = complete_request(), issue_policy()
    kwargs = {
        "independent_validation_passed": independent_validation_passed,
        "all_bindings_current": all_bindings_current,
        "policy_supports_request": policy_supports_request,
        "generation_current": generation_current,
    }
    first = approval_decision(request, policy, generation, **kwargs)
    second = approval_decision(request, policy, generation, **kwargs)
    assert first is second


def test_definite_false_binding_denies() -> None:
    """(§11 line 289) A positively-False binding-current fact is a stale input => DENY (terminal)."""
    result = approval_decision(
        complete_request(),
        issue_policy(),
        7,
        **{**APPROVE_FACTS, "all_bindings_current": False},
    )
    assert result is ApprovalResult.DENY


def test_none_fact_is_unknown() -> None:
    """(§11 line 289) An undetermined (None) fact => UNKNOWN — never a permissive default."""
    result = approval_decision(
        complete_request(),
        issue_policy(),
        7,
        **{**APPROVE_FACTS, "policy_supports_request": None},
    )
    assert result is ApprovalResult.UNKNOWN


def test_missing_generation_is_unknown() -> None:
    """(§11 line 289) A missing generation => UNKNOWN (missing input, never APPROVE)."""
    result = approval_decision(
        complete_request(), issue_policy(), None, **APPROVE_FACTS
    )
    assert result is ApprovalResult.UNKNOWN


def test_conflicting_evaluations_is_unknown() -> None:
    """(§17) Conflicting evaluators => UNKNOWN (retained, no majority selection)."""
    result = approval_decision(
        complete_request(),
        issue_policy(),
        7,
        **{**APPROVE_FACTS, "conflicting_evaluations": True},
    )
    assert result is ApprovalResult.UNKNOWN


def test_unknown_cannot_be_promoted_by_re_evaluation() -> None:
    """(§11 line 296) Repeated evaluation of an UNKNOWN input never promotes it to APPROVE."""
    request, policy = complete_request(), issue_policy()
    facts = {**APPROVE_FACTS, "policy_supports_request": None}
    for _ in range(
        5
    ):  # repeated evaluation / timeout / retry cannot promote (§11 line 296)
        assert approval_decision(request, policy, 7, **facts) is ApprovalResult.UNKNOWN


def test_incomplete_request_denies_decision() -> None:
    """(§5.1 -> §5.2) A DENY-incomplete request denies the decision regardless of positive facts."""
    result = approval_decision(
        complete_request(account="*"), issue_policy(), 7, **APPROVE_FACTS
    )
    assert result is ApprovalResult.DENY
