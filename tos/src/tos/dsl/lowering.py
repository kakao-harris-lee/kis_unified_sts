"""Typed-algebra -> candidate-AST lowering (design #31 §3.5 D4 / §9-4 seam closure).

Design #31 §3.5 named this seam and deliberately deferred it: Slice #1's in-process
typed :class:`~tos.dsl.strategy.AuthoredStrategy` never reaches the escape-checker
(:func:`tos.dsl.admissibility.analyze`) because there was no function turning the
closed typed authoring algebra (:mod:`tos.dsl.vocabulary`) into the open
candidate-AST domain (:mod:`tos.dsl.candidate`) the checker consumes (the DSL spike
memo's G11 gap, ``docs/plans/2026-07-29-tos-dsl-spike-findings.md``). This module
closes that seam: :func:`lower_strategy` is the missing conversion function, so both
the in-process typed path and a future serialized (:mod:`tos.dsl.serialization`)
authoring path can be run through the identical escape-checker gate
(:mod:`tos.engine.admission`, design #31 §9-4).

**Direction is one-way.** Lowering only ever walks the typed algebra *down* into
candidate nodes; there is no function that raises a candidate program back into a
typed :class:`~tos.dsl.vocabulary.DecisionPolicy` (design #31 §9-4 "역방향은 만들지
않는다") — a candidate is the adversarial input domain (design §3.2), never an
authoring output.

**Totality.** :func:`lower_strategy` never raises. Every :class:`~tos.dsl.vocabulary.
Rule`, :class:`~tos.dsl.vocabulary.Compare`, :class:`~tos.dsl.vocabulary.Operand`, and
:class:`~tos.dsl.vocabulary.TargetSpec` the typed algebra can construct has exactly one
lowering, and every lowered :class:`~tos.dsl.candidate.CandidateNode` carries a
``kind`` drawn from :data:`tos.dsl.vocabulary.ADMISSIBLE_KINDS` — the typed algebra's
*node* shapes cannot express an escape by construction, so nothing they can construct
lowers to an escape/wildcard/unknown node (design §3.5 "구성상 admissible"). The
*ambient-source* case is separate and, until Phase 3 K2-p3-#10, was **not** actually
closed here: :class:`~tos.dsl.vocabulary.Operand`'s constructor did not check ``ref[0]``
against :data:`~tos.dsl.vocabulary.ADMISSIBLE_CONTEXT_SOURCES`, so an
``Operand(ref=("ambient", "now"))`` was constructible and lowered straight to an
ambient ``context_ref`` node. That constructor gate now makes the claim true again by
construction — but the escape-checker (:func:`tos.dsl.admissibility.analyze`) is the
load-bearing, independent check for the `ref`-source case regardless, not a formality
run over an already-closed seam. A policy-less
:class:`~tos.dsl.strategy.AuthoredStrategy` (``policy is None``) is not itself an
authoring input with any content to walk; it lowers to the same single ``NO_ACTION``
shape the typed evaluator's own totality discipline uses for "nothing to decide"
(:func:`tos.dsl.vocabulary.evaluate_policy`'s mandatory ``default``) rather than
raising. This branch is never reached on the admission path in practice —
:func:`tos.engine.admission.strategy_admissible` refuses a policy-less strategy
before ever calling this function — it exists purely so ``lower_strategy`` is
total over the whole :class:`~tos.dsl.strategy.AuthoredStrategy` type, not only over
the sub-case that already carries a policy.

**Determinism.** Every source model is an immutable, tuple-ordered
:class:`~tos.dsl._base.FrozenModel`; lowering never consults a ``dict``/``set``
iteration order or any ambient input, so lowering the same strategy twice yields
structurally ``==`` :class:`~tos.dsl.candidate.CandidateProgram` values.

**Payload is intentionally structural, not literal.** A :class:`~tos.dsl.candidate.
CandidateNode` carries no scalar-value field, so a lowered ``const`` operand does not
carry the literal it held, and a lowered ``target`` does not carry its account/
instrument. This matches what the escape-checker actually inspects (design §3.3):
node *kind*, ``context_ref`` *source*, a named ambient *symbol*, and a wildcard
*scope* — never a literal payload. A ``ref`` operand's source (the one structural
fact the checker cares about) is preserved via :attr:`~tos.dsl.candidate.
CandidateNode.source`.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design §firewall).
"""

from __future__ import annotations

from tos.dsl.candidate import CandidateNode, CandidateProgram
from tos.dsl.strategy import AuthoredStrategy
from tos.dsl.vocabulary import (
    KIND_COMPARE,
    KIND_CONST,
    KIND_CONTEXT_REF,
    KIND_NO_ACTION,
    KIND_POLICY,
    KIND_PROPOSE_ACTION,
    KIND_PROPOSE_FLAT,
    KIND_PROPOSE_VECTOR,
    KIND_RULE,
    KIND_TARGET,
    Compare,
    Decision,
    DecisionKind,
    DecisionPolicy,
    Operand,
    Rule,
    TargetSpec,
)

__all__ = ["lower_strategy"]


def _lower_operand(operand: Operand) -> CandidateNode:
    """Lower one authored :class:`Operand` (design §3.5).

    A ``ref`` lowers to a ``context_ref`` candidate node carrying its source (the
    first path component — :func:`tos.engine.admission.operand_source` reads the
    same component); a ``const`` lowers to a bare ``const`` node (its literal is not
    structural — see module docstring).
    """
    if operand.ref is not None:
        return CandidateNode(kind=KIND_CONTEXT_REF, source=operand.ref[0])
    return CandidateNode(kind=KIND_CONST)


def _lower_compare(compare: Compare) -> CandidateNode:
    """Lower one :class:`Compare` to a ``compare`` node over its two lowered operands."""
    return CandidateNode(
        kind=KIND_COMPARE,
        children=(_lower_operand(compare.left), _lower_operand(compare.right)),
    )


def _lower_target(target: TargetSpec) -> CandidateNode:
    """Lower one :class:`TargetSpec` to a bare ``target`` node (structural only)."""
    del target  # the checker inspects node shape, never a TargetSpec's payload
    return CandidateNode(kind=KIND_TARGET)


def _lower_decision(decision: Decision) -> CandidateNode:
    """Lower one :class:`Decision` to its ``propose_*`` / ``no_action`` node (design §3.5).

    :class:`Decision`'s own ``_shape_consistent`` validator guarantees ``target`` is
    set for ``ACTION``/``FLAT`` and ``vector`` is non-empty for ``VECTOR`` (design
    §3.1 ``vocabulary.py``), so the ``None``/empty branches below are unreachable for
    any pydantic-constructed ``Decision`` — they exist only so this function type-
    checks as total without a bare ``assert`` (never raising, per module docstring).
    """
    if decision.kind is DecisionKind.NO_ACTION:
        return CandidateNode(kind=KIND_NO_ACTION)
    if decision.kind is DecisionKind.ACTION:
        target = decision.target
        if (
            target is None
        ):  # pragma: no cover - Decision._shape_consistent guarantees this
            return CandidateNode(kind=KIND_NO_ACTION)
        return CandidateNode(
            kind=KIND_PROPOSE_ACTION, children=(_lower_target(target),)
        )
    if decision.kind is DecisionKind.FLAT:
        target = decision.target
        if (
            target is None
        ):  # pragma: no cover - Decision._shape_consistent guarantees this
            return CandidateNode(kind=KIND_NO_ACTION)
        return CandidateNode(kind=KIND_PROPOSE_FLAT, children=(_lower_target(target),))
    # DecisionKind.VECTOR
    return CandidateNode(
        kind=KIND_PROPOSE_VECTOR,
        children=tuple(_lower_target(target) for target in decision.vector),
    )


def _lower_rule(rule: Rule) -> CandidateNode:
    """Lower one :class:`Rule` to a ``rule`` node over its guard compares + its decision."""
    children = tuple(_lower_compare(compare) for compare in rule.all_of) + (
        _lower_decision(rule.decision),
    )
    return CandidateNode(kind=KIND_RULE, children=children)


def _lower_policy(policy: DecisionPolicy) -> CandidateNode:
    """Lower a whole :class:`DecisionPolicy` to a ``policy`` node (design #31 §9-4).

    Children are every lowered ``rule`` (authored order preserved) plus the lowered
    mandatory ``default`` — so :func:`tos.dsl.candidate.iter_nodes` over the result
    visits exactly one ``rule`` node per authored ``Rule`` (D-K-1 coverage
    requirement), never fewer, never a duplicate.
    """
    children = tuple(_lower_rule(rule) for rule in policy.rules) + (
        _lower_decision(policy.default),
    )
    return CandidateNode(kind=KIND_POLICY, children=children)


def lower_strategy(strategy: AuthoredStrategy) -> CandidateProgram:
    """Lower an Authored Strategy's embedded policy to a candidate program (design #31 §9-4).

    A total function over the typed algebra (module docstring): every
    :class:`DecisionPolicy` this strategy embeds becomes a single-rooted
    :class:`~tos.dsl.candidate.CandidateProgram` whose one root node is the lowered
    ``policy`` node, so :func:`tos.dsl.admissibility.analyze` can run the same
    escape-checker gate over it that a genuinely adversarial candidate would face.

    Args:
        strategy: The Authored Strategy to lower (in-process typed or issued via
            :func:`tos.dsl.serialization.parse_strategy` — both converge on this one
            function, design #31 §1.2 "두 경로 동형").

    Returns:
        The lowered, non-empty :class:`~tos.dsl.candidate.CandidateProgram`.
    """
    if strategy.policy is None:
        # Total over the full AuthoredStrategy type (module docstring); never
        # reached on the admission path in practice (strategy_admissible refuses a
        # policy-less strategy first).
        return CandidateProgram(nodes=(CandidateNode(kind=KIND_NO_ACTION),))
    return CandidateProgram(nodes=(_lower_policy(strategy.policy),))
