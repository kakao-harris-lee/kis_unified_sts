"""Truthy-sentinel property — both axes (design #16 §2.2-1 / §7; the #13 ARE lesson).

Two StrEnums cross the afg surface and **every** member of each is *truthy*:

1. :class:`~tos.afg.vocabulary.ActionFlowResult` (``GRANT`` / ``DENY`` / ``UNKNOWN``) — a
   bare ``if result:`` would let ``DENY`` and ``UNKNOWN`` through, so every consuming gate
   must use ``result is ActionFlowResult.GRANT``;
2. the injected protective ``Admissibility`` verdict (``ADMISSIBLE`` / ``TRAPPED`` /
   ``PROHIBITED``, design #16 M2 — **not** ``bool | None``) — only the ``ADMISSIBLE`` token
   may pass.

``bool | None`` flags are normalized with ``is True`` / ``is not True`` (the orthostate
``predicates.py:461`` precedent): a ``None`` is UNKNOWN, never a soft pass.

The properties here are **behavioural**: they drive the real predicates with every truthy
member and assert the non-``GRANT`` / non-``ADMISSIBLE`` members never produce a permissive
outcome. A source-level scan additionally proves no afg module contains a bare truthiness
test on a result value.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from tos.afg import (
    ADMISSIBILITY_ADMISSIBLE,
    ActionFlowResult,
    ActionFlowScopeKind,
    action_flow_decision,
    partition_lease_exclusive,
)

from ._afg_strategies import (
    ACTION_FLOW_RESULT_OR_FORGERY,
    ACTION_FLOW_RESULTS,
    SCHEME,
    TRIBOOL,
    TRUTHY_NON_BOOL,
    flow_vector,
    limit_vector,
)

_AFG_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "afg"


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
    return action_flow_decision(**base).result  # type: ignore[arg-type]


@given(coverage=ACTION_FLOW_RESULT_OR_FORGERY)
def test_only_the_grant_member_itself_can_produce_a_grant(coverage: object) -> None:
    """(C1 regression) ``GRANT`` requires the **member**, never a fall-through residue.

    A gate that only tests for the ``UNKNOWN`` / ``DENY`` members and lets everything else
    fall through makes ``GRANT`` the *residual* outcome: a raw ``"GRANT"`` / ``"BANANA"``
    string, ``None``, ``0``, ``""``, or ``[1]`` would all be granted. Only the singleton
    member may pass.
    """
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
    """(M2 regression) Each of the five premises rejects a truthy non-``bool``.

    The premises are ``bool``-annotated only; Python enforces nothing at runtime. A
    ``if not X:`` gate would pass ``"UNKNOWN"``, ``1``, ``[1]``, even the string
    ``"False"`` — so every premise must be gated with ``is not True``.
    """
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


def test_lease_gate_matches_the_real_protective_enum_polarity() -> None:
    """(axis 2, seam parity) Driven with the **real** ``Admissibility`` members, 3 + None."""
    from tos.protective import Admissibility

    assert _lease(Admissibility.ADMISSIBLE) is True
    assert _lease(Admissibility.TRAPPED) is False
    assert _lease(Admissibility.PROHIBITED) is False
    assert _lease(None) is False


def _bare_truthiness_offenders(path: Path) -> list[str]:
    """Return ``if <name>:`` / ``if not <name>:`` uses of a result-shaped local (AST)."""
    # Result-shaped values AND the five ``bool``-annotated decision premises: all of them
    # must be gated by identity / ``is not True``, never by bare truthiness (NIT-1).
    suspicious = {
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
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            test = test.operand
        if isinstance(test, ast.Name) and test.id in suspicious:
            offenders.append(f"{path.name}:{node.lineno} bare truthiness on {test.id}")
    return offenders


def test_no_afg_source_uses_bare_truthiness_on_a_result_value() -> None:
    """(source seal) No afg module tests a result-shaped value for bare truthiness."""
    sources = sorted(_AFG_SRC.rglob("*.py"))
    assert sources, f"no tos.afg source files found under {_AFG_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_bare_truthiness_offenders(path))
    assert offenders == [], f"truthy-sentinel trap reachable: {offenders}"


def test_bare_truthiness_scan_detects_a_planted_offender(tmp_path: Path) -> None:
    """(canary) The AST scan actually catches a planted ``if result:`` (not vacuous)."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(result):\n    if result:\n        return 1\n    return 0\n",
        encoding="utf-8",
    )
    assert _bare_truthiness_offenders(planted) != []
