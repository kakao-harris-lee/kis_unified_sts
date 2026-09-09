"""§7.2-8 — env-configuration admission: every outcome-gating compare needs a capsule operand.

The design's v1.1 redefinition (design #31 §3.2 (3) / §3.5, MAJOR-2):

    an outcome-gating ``Compare`` SHALL have at least one capsule-sourced ``ref`` operand;
    a comparison whose operands are all literals or all config-sourced refs is inadmissible.

This is the engine's share of the D1↔D4 coupling. It blocks the core relabelling escape — a
market-dependent decision routed entirely through ``config`` — which RFC-008 §10:327-331 and
RFC-003 §8:236-237 forbid ("SHALL NOT relabel a value as a 'feature,' 'signal,' 'derived field,'
or 'override' to avoid Critical Input governance").

**Two honest limits are asserted rather than hidden** (design #31 §3.2 (3)/§3.5/§10.2-5):

* the seal is **partial** — an author who puts a market value in ``config`` *and* keeps a capsule
  operand alongside it still passes. Complete enforcement is D-E2 Snapshot provenance
  (RFC-004 §9:242-244), and the test below states that explicitly;
* a policy with **zero** rules has no outcome-gating comparison, so there is nothing for this
  predicate to reject. Rejecting it would be the #26 WDR MAJOR-1 over-rejection defect (check the
  applicable side before rejecting an empty).

Also covered: the escape-checker seam design #31 §3.5 deferred is now closed (design #31 §9-4,
lane D-K-3) — ``strategy_admissible`` calls ``tos.dsl.admissibility.analyze`` over every strategy's
``tos.dsl.lowering.lower_strategy``-lowered program; the dedicated escape-checker-gate test suite
lives in ``test_engine_admission_escape_checker.py``, and the AST call-site canary here is kept
(repurposed from its old negative form) to catch a future silent regression.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

import pytest
from tos.dsl import (
    ADMISSIBLE_CONTEXT_SOURCES,
    Compare,
    CompareOp,
    Decision,
    DecisionKind,
    DecisionPolicy,
    Operand,
    Rule,
    TargetKind,
    TargetSpec,
)
from tos.engine import (
    CAPSULE_CONTEXT_SOURCE,
    CONFIG_CONTEXT_SOURCE,
    AdmissionVerdict,
    RegistrationRefused,
    StrategyRegistry,
    compare_has_capsule_operand,
    iter_outcome_gating_compares,
    operand_source,
    strategy_admissible,
)

from ._engine_fixtures import (
    ACCOUNT,
    DECISION_CLASS,
    INSTRUMENT,
    authored_config,
    capsule_gated_policy,
    config_gated_policy,
    issue_strategy,
)

_CAPSULE_OPERAND = Operand(ref=("capsule", "scope", "decision_class"))
_CONFIG_OPERAND = Operand(ref=("config", "threshold"))
_CONST_OPERAND = Operand(const=DECISION_CLASS)


def _policy_with(compare: Compare) -> DecisionPolicy:
    """A one-rule policy whose single guard is ``compare``."""
    action = Decision(
        kind=DecisionKind.ACTION,
        rationale="fired",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="LONG",
            position_effect="OPEN",
            quantity_basis="RISK",
            rationale="fired",
        ),
    )
    return DecisionPolicy(
        rules=(Rule(all_of=(compare,), decision=action),),
        default=Decision(kind=DecisionKind.NO_ACTION, rationale="hold"),
    )


def test_the_named_context_sources_are_anchored_to_the_dsl_constant() -> None:
    """(§3.2 (3) drift anchor) The engine's two named sources are exactly the DSL's set."""
    assert {CAPSULE_CONTEXT_SOURCE, CONFIG_CONTEXT_SOURCE} == ADMISSIBLE_CONTEXT_SOURCES


def test_operand_source_reads_the_ref_head_and_nothing_from_a_const() -> None:
    """A ``const`` names no source; a ``ref``'s first path component is its source."""
    assert operand_source(_CAPSULE_OPERAND) == CAPSULE_CONTEXT_SOURCE
    assert operand_source(_CONFIG_OPERAND) == CONFIG_CONTEXT_SOURCE
    assert operand_source(_CONST_OPERAND) is None


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (_CAPSULE_OPERAND, _CONST_OPERAND, True),
        (_CONST_OPERAND, _CAPSULE_OPERAND, True),
        (_CAPSULE_OPERAND, _CONFIG_OPERAND, True),
        (_CONFIG_OPERAND, _CONST_OPERAND, False),
        (_CONST_OPERAND, _CONFIG_OPERAND, False),
        (_CONST_OPERAND, Operand(const="other"), False),
        (_CONFIG_OPERAND, Operand(ref=("config", "other")), False),
    ],
)
def test_the_capsule_operand_predicate_is_exhaustive_over_operand_shapes(
    left, right, expected
) -> None:
    """(§7.2-8) ≥1 capsule-sourced ``ref`` operand — every operand pairing is enumerated."""
    assert (
        compare_has_capsule_operand(Compare(left=left, op=CompareOp.EQ, right=right))
        is expected
    )


def test_a_ref_naming_an_inadmissible_source_is_not_a_capsule_read() -> None:
    """A ``ref`` outside the DSL's admissible source set is restrictive, not a capsule operand."""
    rogue = Operand(ref=("market", "last_price"))
    assert operand_source(rogue) == "market"
    assert (
        compare_has_capsule_operand(
            Compare(left=rogue, op=CompareOp.GT, right=_CONST_OPERAND)
        )
        is False
    )


def test_a_config_only_gated_strategy_is_inadmissible() -> None:
    """(§7.2-8) The core relabelling escape — a market-dependent decision via config — is refused."""
    result = strategy_admissible(issue_strategy(config_gated_policy()))
    assert result.verdict is AdmissionVerdict.INADMISSIBLE
    assert any("no capsule-sourced operand" in reason for reason in result.reasons)
    with pytest.raises(RegistrationRefused, match="INADMISSIBLE"):
        StrategyRegistry().register(
            issue_strategy(config_gated_policy()), authored_config()
        )


def test_a_literal_only_gate_is_inadmissible() -> None:
    """(§7.2-8) Two literals gate nothing about the market — inadmissible."""
    strategy = issue_strategy(
        _policy_with(
            Compare(left=_CONST_OPERAND, op=CompareOp.EQ, right=Operand(const="x"))
        )
    )
    assert strategy_admissible(strategy).verdict is AdmissionVerdict.INADMISSIBLE


def test_a_capsule_gated_strategy_is_admissible() -> None:
    """(§7.2-8) The conformant shape passes: the guard reads the Capsule."""
    result = strategy_admissible(issue_strategy(capsule_gated_policy()))
    assert result.verdict is AdmissionVerdict.ADMISSIBLE
    assert result.reasons == ()
    assert result.instrument_key is not None


def test_one_offending_compare_among_many_is_enough_to_refuse() -> None:
    """(§7.2-8) The requirement is per-comparison, not "at least one somewhere in the policy"."""
    good = Compare(left=_CAPSULE_OPERAND, op=CompareOp.EQ, right=_CONST_OPERAND)
    bad = Compare(left=_CONFIG_OPERAND, op=CompareOp.GT, right=Operand(const=0))
    action = Decision(
        kind=DecisionKind.ACTION,
        rationale="fired",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="LONG",
            position_effect="OPEN",
            quantity_basis="RISK",
            rationale="fired",
        ),
    )
    policy = DecisionPolicy(
        rules=(Rule(all_of=(good, bad), decision=action),),
        default=Decision(kind=DecisionKind.NO_ACTION, rationale="hold"),
    )
    result = strategy_admissible(issue_strategy(policy))
    assert result.verdict is AdmissionVerdict.INADMISSIBLE
    assert len([r for r in result.reasons if "capsule-sourced operand" in r]) == 1


def test_the_walk_covers_every_rule_guard_and_not_the_default() -> None:
    """(§3.5) The outcome-gating comparisons are exactly the rule guards; the default gates none."""
    policy = capsule_gated_policy()
    compares = list(iter_outcome_gating_compares(policy))
    assert len(compares) == 1
    assert compares[0] is policy.rules[0].all_of[0]
    assert policy.default.kind is DecisionKind.NO_ACTION


def test_a_rules_free_policy_has_no_gating_compare_and_is_not_over_rejected() -> None:
    """(#26 WDR MAJOR-1) ∅ gating comparisons ⇒ nothing to reject — the honest, recorded limit.

    A policy that is only its default never *gates* on anything, so this predicate has no
    applicable subject. Refusing it would be the over-rejection defect; admitting it makes no claim
    that such a policy is market-governed — that is D-E2 provenance's question.
    """
    policy = DecisionPolicy(
        rules=(),
        default=Decision(
            kind=DecisionKind.ACTION,
            rationale="unconditional",
            target=TargetSpec(
                kind=TargetKind.ACTION,
                account=ACCOUNT,
                instrument=INSTRUMENT,
                direction="LONG",
                position_effect="OPEN",
                quantity_basis="RISK",
                rationale="unconditional",
            ),
        ),
    )
    assert list(iter_outcome_gating_compares(policy)) == []
    assert (
        strategy_admissible(issue_strategy(policy)).verdict
        is AdmissionVerdict.ADMISSIBLE
    )


def test_the_seal_is_partial_and_says_so() -> None:
    """(§3.2 (3) honest limit) A capsule operand *alongside* a config operand still passes.

    This is the design's own stated boundary: engine admission is a **partial** seal and complete
    enforcement is the D-E2 Critical Input Snapshot provenance surface (RFC-004 §9:242-244). The
    test pins the limit so nobody later mistakes this predicate for a complete one.
    """
    mixed = Compare(left=_CAPSULE_OPERAND, op=CompareOp.EQ, right=_CONFIG_OPERAND)
    assert compare_has_capsule_operand(mixed) is True
    assert strategy_admissible(issue_strategy(_policy_with(mixed))).verdict is (
        AdmissionVerdict.ADMISSIBLE
    )


def test_a_draft_or_policy_less_strategy_is_inadmissible() -> None:
    """(§3.5) Only an ISSUED artifact carrying an embedded policy is an admissible input."""
    from tos.dsl import AuthoredStrategy

    draft = AuthoredStrategy(dsl_version="dsl-0", config_binding_version="cfg-0")
    result = strategy_admissible(draft)
    assert result.verdict is AdmissionVerdict.INADMISSIBLE
    assert any("no embedded DecisionPolicy" in reason for reason in result.reasons)


def test_the_escape_checker_seam_is_now_exercised_by_admission() -> None:
    """(§9-4 seam closure) admission.py DOES call the DSL escape-checker — no longer a non-claim.

    This test used to assert the opposite (``called == []``): design #31 §3.5 deferred the
    escape-checker seam because there was no ``lower_strategy`` function bridging the typed
    authoring algebra into the candidate-AST domain the checker consumes. ``tos.dsl.lowering.
    lower_strategy`` (design #31 §9-4) closes that gap, and ``strategy_admissible`` now calls
    ``analyze`` over every strategy's lowered program (:func:`tos.engine.admission._escape_checker_
    result`). The AST scan is kept (not deleted) precisely so a future regression that silently
    drops the call is caught here, the same way the old assertion caught a premature claim.
    """
    import ast
    from pathlib import Path

    engine_src = Path(__file__).resolve().parents[2] / "src" / "tos" / "engine"
    called: list[str] = []
    for path in sorted(engine_src.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute) else None
                )
                if name in {"analyze", "is_admissible", "analyze_candidate"}:
                    called.append(f"{path.name}:{node.lineno} {name}()")
    assert len(called) == 1, (
        "expected exactly one escape-checker call site in admission.py's own _escape_checker_"
        f"result helper (design #31 §9-4); found: {called}"
    )
    assert called[0].startswith("admission.py:") and called[0].endswith(
        "analyze()"
    ), called[0]
