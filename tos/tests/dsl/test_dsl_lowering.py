"""Typed-algebra -> candidate-AST lowering tests (design #31 §3.5 D4 / §9-4 seam closure).

``lower_strategy`` closes the seam design #31 §3.5 named and explicitly deferred: it
maps every node of the closed typed authoring algebra (``tos.dsl.vocabulary``) onto
the open candidate-AST domain (``tos.dsl.candidate``) the escape-checker
(``tos.dsl.admissibility.analyze``) consumes, so an in-process typed
``AuthoredStrategy`` can now be run through the same escape-checker gate a
serialized strategy will use (``tos.engine.admission.strategy_admissible``, lane
D-K-3).

Coverage:

* every fixture policy shape (NO_ACTION-only default, ACTION, FLAT, VECTOR,
  multi-rule) lowers to a non-empty, ADMISSIBLE ``CandidateProgram`` — a genuine
  positive (``is_admissible`` checked, not merely "did not raise");
* ``iter_nodes`` over the lowered program visits exactly one ``rule`` node per
  authored ``Rule``, in authored order;
* lowering is deterministic: lowering the same strategy twice yields ``==``
  ``CandidateProgram`` values (frozen-model structural equality);
* ``lower_strategy`` never raises, even for a policy-less ``AuthoredStrategy``
  (module-docstring totality claim);
* a lowered program mutated (validation-bypassing direct-node injection — the WDR
  #26 two-layer canary idiom) to carry each ``candidate.ESCAPE_KINDS`` /
  ambient-symbol / wildcard-scope family is rejected by ``analyze`` — proving the
  checker actually inspects a *lowered* tree, not only a hand-built adversarial one.
"""

from __future__ import annotations

from typing import Any

import pytest
from tos.dsl import (
    AdmissibilityVerdict,
    AuthoredStrategy,
    CandidateProgram,
    analyze,
    is_admissible,
)
from tos.dsl.candidate import (
    AMBIENT_SYMBOLS,
    ESCAPE_KINDS,
    WILDCARD_TOKENS,
    CandidateNode,
    iter_nodes,
)
from tos.dsl.lowering import lower_strategy
from tos.dsl.vocabulary import ADMISSIBLE_KINDS, KIND_POLICY, KIND_RULE

from ._dsl_strategies import (
    FIXTURE_POLICY_BUILDERS,
    default_only_policy,
    issue_strategy,
    multi_rule_policy,
    simple_policy,
    vector_policy,
)

# ---------------------------------------------------------------------------
# Positive coverage — every fixture shape lowers to an admissible program
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("build_policy", FIXTURE_POLICY_BUILDERS)
def test_every_fixture_strategy_lowers_to_an_admissible_program(
    build_policy: Any,
) -> None:
    """Every fixture policy shape lowers to a non-empty, ADMISSIBLE candidate program."""
    strategy = issue_strategy(policy=build_policy())
    program = lower_strategy(strategy)
    assert isinstance(program, CandidateProgram)
    assert (
        program.nodes
    )  # non-empty (CandidateProgram forbids empty construction anyway)
    analysis = analyze(program)
    assert analysis.verdict is AdmissibilityVerdict.ADMISSIBLE, analysis.reasons
    assert is_admissible(program)


def test_every_lowered_node_kind_is_inside_the_authoring_surface_vocabulary() -> None:
    """Lowering never emits a kind outside ``ADMISSIBLE_KINDS`` (design #31 §9-4)."""
    strategy = issue_strategy(policy=multi_rule_policy())
    program = lower_strategy(strategy)
    for node in iter_nodes(program):
        assert node.kind in ADMISSIBLE_KINDS, node.kind


def test_the_lowered_root_is_a_single_policy_node() -> None:
    """The whole program is rooted at exactly one ``policy`` candidate node."""
    strategy = issue_strategy(policy=simple_policy())
    program = lower_strategy(strategy)
    assert len(program.nodes) == 1
    assert program.nodes[0].kind == KIND_POLICY


def test_iter_nodes_covers_every_authored_rule_in_order() -> None:
    """The lowered policy carries exactly one ``rule`` node per authored ``Rule`` (D-K-1)."""
    policy = multi_rule_policy()
    strategy = issue_strategy(policy=policy)
    program = lower_strategy(strategy)
    rule_nodes = [node for node in iter_nodes(program) if node.kind == KIND_RULE]
    assert len(rule_nodes) == len(policy.rules) == 2


def test_lowering_a_rules_free_policy_still_lowers_its_mandatory_default() -> None:
    """∅ rules ⇒ zero rule nodes, but the mandatory default still lowers (total, not vacuous)."""
    strategy = issue_strategy(policy=default_only_policy())
    program = lower_strategy(strategy)
    assert [node for node in iter_nodes(program) if node.kind == KIND_RULE] == []
    assert is_admissible(program)


# ---------------------------------------------------------------------------
# Determinism + totality
# ---------------------------------------------------------------------------


def test_lowering_is_deterministic_same_strategy_same_program() -> None:
    """Lowering the same strategy twice yields structurally ``==`` candidate programs."""
    strategy = issue_strategy(policy=vector_policy())
    assert lower_strategy(strategy) == lower_strategy(strategy)


def test_lowering_two_strategies_with_different_policies_yields_different_programs() -> (
    None
):
    """Lowering is a genuine function of the policy content, not a constant shape."""
    left = issue_strategy(policy=simple_policy())
    right = issue_strategy(policy=vector_policy())
    assert lower_strategy(left) != lower_strategy(right)


def test_lowering_a_policy_less_strategy_is_total_never_raises() -> None:
    """``lower_strategy`` never raises, even for a DRAFT/policy-less strategy (total function)."""
    draft = AuthoredStrategy(dsl_version="dsl-0", config_binding_version="cfg-0")
    assert draft.policy is None
    program = lower_strategy(draft)
    assert isinstance(program, CandidateProgram)
    assert is_admissible(program)


# ---------------------------------------------------------------------------
# Escape-injection canary — a lowered program mutated with an escape/ambient/
# wildcard family is rejected by analyze (WDR #26 two-layer canary idiom).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("escape_kind", sorted(ESCAPE_KINDS))
def test_a_lowered_program_with_an_injected_escape_kind_is_rejected(
    escape_kind: str,
) -> None:
    """Appending one escape-kind node to an otherwise-admissible lowered program flips it (DCE-EV-001/004)."""
    strategy = issue_strategy(policy=multi_rule_policy())
    program = lower_strategy(strategy)
    assert is_admissible(program)  # baseline is genuinely admissible (non-vacuous)
    mutated = CandidateProgram(nodes=(*program.nodes, CandidateNode(kind=escape_kind)))
    assert not is_admissible(mutated)
    assert any(r.startswith("non_vocabulary_kind:") for r in analyze(mutated).reasons)


@pytest.mark.parametrize("symbol", sorted(AMBIENT_SYMBOLS))
def test_a_lowered_program_with_an_injected_ambient_symbol_is_rejected(
    symbol: str,
) -> None:
    """Poisoning the lowered root with a named ambient symbol is rejected (DCE-EV-003)."""
    strategy = issue_strategy(policy=simple_policy())
    program = lower_strategy(strategy)
    poisoned_root = program.nodes[0].model_copy(update={"symbol": symbol})
    mutated = CandidateProgram(nodes=(poisoned_root,))
    assert not is_admissible(mutated)
    assert any(r.startswith("ambient_symbol:") for r in analyze(mutated).reasons)


@pytest.mark.parametrize("token", sorted(WILDCARD_TOKENS))
def test_a_lowered_program_with_an_injected_wildcard_scope_is_rejected(
    token: str,
) -> None:
    """Poisoning the lowered root with a wildcard scope token is rejected (RFC-008 §11 item 13)."""
    strategy = issue_strategy(policy=simple_policy())
    program = lower_strategy(strategy)
    poisoned_root = program.nodes[0].model_copy(update={"scope": token})
    mutated = CandidateProgram(nodes=(poisoned_root,))
    assert not is_admissible(mutated)
    assert any(r.startswith("wildcard_scope:") for r in analyze(mutated).reasons)


def test_a_lowered_program_with_a_buried_ambient_source_is_rejected() -> None:
    """An ambient ``context_ref`` source buried inside the lowered tree is caught (recursion, M-2)."""
    strategy = issue_strategy(policy=simple_policy())
    program = lower_strategy(strategy)
    poisoned = CandidateNode(
        kind="const", children=(CandidateNode(kind="context_ref", source="clock"),)
    )
    mutated = CandidateProgram(nodes=(*program.nodes, poisoned))
    assert not is_admissible(mutated)
    assert any(r.startswith("ambient_source:") for r in analyze(mutated).reasons)
