"""Authoring Surface Vocabulary = closed typed AST algebra (design §3.1, DCE-INV-001).

This module is the **constructive** realization of DCE-INV-001 (ADR-DEV-001 §6
L140-144): the authoring surface is *exactly* the RFC-008 §7 permitted
expressions, and every prohibited effect is **absent from the type**, not
blocklisted on a reachable host. There is no node type for ``import``,
``network``, ``clock``, ``FFI``, ``reflection``, ``dynamic-eval``, or a wildcard
scope — so those effects are unexpressible by construction (RFC-008 §11 items
12/13/17). "default-deny = absent-from-surface, not blocklisted" is realized here
as *the type system itself*.

The algebra is deliberately less than a general-purpose language (RFC-008 §7):

* value operands: a literal :class:`Const` or a read-only :class:`Operand` ``ref``
  into the Decision Context (no ambient clock/rand/net/fs — those cannot be named);
* :class:`Compare` (a total, pure comparison) combined into a :class:`Rule` guard
  (``all_of`` — a non-empty conjunction, so a rule never fires vacuously);
* :class:`Decision` nodes — the only outputs a strategy may name: propose an
  action, propose an explicit flat, propose a portfolio vector, or no-action
  (RFC-008 §6 principle 2, §7);
* :class:`DecisionPolicy` — an ordered rule list plus a mandatory default
  Decision, so evaluation is total and deterministic (RFC-008 §9).

The algebra is **family-independent** (design §3.1): it reads equally as the
grammar of a standalone constrained language or the admissible-node set of an
embedded subset, so it does not pre-empt RFC-008 §14 Q1 (ADR-DEV-001 §7 — the
family choice is approved design/config, deferred; design §0).

The pure evaluator (:func:`evaluate_policy`) is a function of the policy and an
environment derived solely from the Capsule + configuration (design §4). It reads
ambient nothing: there is no clock/rand/net/fs parameter to read (RFC-008 §9).
Mapping the chosen :class:`Decision` to a concrete Outcome artifact lives in
:mod:`tos.dsl.determinism` (kept out of this module to keep the vocabulary free of
any Proposal/Outcome dependency).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design §firewall).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import model_validator

from tos.dsl._base import ArtifactIntegrityError, FrozenModel

# ---------------------------------------------------------------------------
# Authoring Surface Vocabulary — the admissible node-kind names (design §3.1)
# ---------------------------------------------------------------------------
# These strings name every construct the surface provides. They are the
# membership set the static admissibility predicate (:mod:`tos.dsl.admissibility`)
# tests a candidate against: default-deny means a node whose kind is not in this
# frozenset is *absent from the surface* and therefore inadmissible. Nothing here
# names an ambient/escape effect — that is DCE-INV-001 realized as data.

KIND_CONST = "const"
KIND_CONTEXT_REF = "context_ref"
KIND_COMPARE = "compare"
KIND_RULE = "rule"
KIND_POLICY = "policy"
KIND_TARGET = "target"
KIND_PROPOSE_ACTION = "propose_action"
KIND_PROPOSE_FLAT = "propose_flat"
KIND_PROPOSE_VECTOR = "propose_vector"
KIND_NO_ACTION = "no_action"

#: The complete Authoring Surface Vocabulary (DCE-INV-001). Anything outside it is
#: inadmissible by default-deny membership, not by a blocklist.
ADMISSIBLE_KINDS: frozenset[str] = frozenset(
    {
        KIND_CONST,
        KIND_CONTEXT_REF,
        KIND_COMPARE,
        KIND_RULE,
        KIND_POLICY,
        KIND_TARGET,
        KIND_PROPOSE_ACTION,
        KIND_PROPOSE_FLAT,
        KIND_PROPOSE_VECTOR,
        KIND_NO_ACTION,
    }
)

#: The only Decision Context read sources a ``context_ref`` may name (design §4).
#: A read from any other named source (clock/rand/net/fs/global/builtin) is an
#: ambient reach and is inadmissible (RFC-008 §11 item 12; DCE-INV-003).
ADMISSIBLE_CONTEXT_SOURCES: frozenset[str] = frozenset({"capsule", "config"})


#: A DSL scalar value. Booleans are kept distinct from numbers by the comparison
#: rules below (a bool is never treated as an orderable magnitude).
ScalarValue = bool | int | float | str


class _Unknown:
    """Singleton sentinel for an unresolved / non-scalar context read (design §4).

    Missing, non-scalar, or absent context resolves to ``UNKNOWN`` and any
    comparison against it is ``False`` — "UNKNOWN is restrictive" (RFC-008 §10):
    an unresolved read never satisfies a guard, so it can only *narrow* the action
    set, never widen it.
    """

    _instance: _Unknown | None = None

    def __new__(cls) -> _Unknown:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "UNKNOWN"


UNKNOWN = _Unknown()


class CompareOp(StrEnum):
    """The total set of comparison operators a strategy may express (RFC-008 §7)."""

    EQ = "EQ"
    NE = "NE"
    LT = "LT"
    LE = "LE"
    GT = "GT"
    GE = "GE"


class TargetKind(StrEnum):
    """Whether a target proposes an action or an explicit flat (ADR-DEV-007 §7)."""

    ACTION = "ACTION"
    FLAT = "FLAT"


class DecisionKind(StrEnum):
    """The exhaustive set of authored outcomes (RFC-008 §6 principle 2; ADR-DEV-007)."""

    NO_ACTION = "NO_ACTION"
    ACTION = "ACTION"
    FLAT = "FLAT"
    VECTOR = "VECTOR"


class VectorInterdependence(StrEnum):
    """Portfolio-vector component interdependence (ADR-DEV-007 §5, SOS-INV-006).

    ``ATOMIC`` = all-or-none; ``INDEPENDENT`` = mutual independence. Absence of a
    declaration is treated as ``ATOMIC`` (fail-closed) by the consuming models.
    """

    ATOMIC = "ATOMIC"
    INDEPENDENT = "INDEPENDENT"


class Operand(FrozenModel):
    """A value operand: exactly one of a literal ``const`` or a context ``ref``.

    ``ref`` is a read-only path into the Decision Context environment (design §4);
    its first component names the source and SHALL be an
    :data:`ADMISSIBLE_CONTEXT_SOURCES` member — there is no way to name an ambient
    source here (DCE-INV-003). ``const`` carries an injected literal (thresholds
    are configuration, never hard-coded — design §7).
    """

    const: ScalarValue | None = None
    ref: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> Operand:
        """Exactly one of ``const`` / ``ref`` is set, and ``ref`` is non-empty."""
        has_const = self.const is not None
        has_ref = self.ref is not None
        if has_const == has_ref:
            raise ArtifactIntegrityError(
                "Operand must set exactly one of const / ref "
                f"(const={self.const!r}, ref={self.ref!r})"
            )
        if has_ref and not self.ref:
            raise ArtifactIntegrityError("Operand.ref must be a non-empty path")
        return self


class Compare(FrozenModel):
    """A pure, total comparison of two operands (RFC-008 §7)."""

    left: Operand
    op: CompareOp
    right: Operand


class TargetSpec(FrozenModel):
    """A single per-instrument authored target (ADR-DEV-007 §8; ADR-002-020 §8 anchor).

    Carries only the proposing-role vocabulary (RFC-008 §7): account, instrument,
    direction, position effect, and — as *evidence*, never capacity — a quantity
    basis and an edge/confidence. Timing/execution are *requests* (RFC-005), not
    commands. Well-formedness (wildcard-free, flat-vs-action consistency) is
    enforced when this is assembled into a :class:`~tos.dsl.proposal.Proposal`.
    """

    kind: TargetKind
    account: str | None = None
    instrument: str | None = None
    direction: str | None = None
    position_effect: str | None = None
    quantity_basis: str | None = None
    edge_or_confidence: str | None = None
    timing_and_execution_constraints: tuple[str, ...] = ()
    rationale: str | None = None


class Decision(FrozenModel):
    """A terminal authored outcome node (RFC-008 §6 principle 2; ADR-DEV-007).

    Exactly one of four shapes, discriminated by :class:`DecisionKind`:

    * ``NO_ACTION`` — propose nothing, leave exposure (a first-class outcome);
    * ``ACTION`` / ``FLAT`` — a single :class:`TargetSpec` (flat = zero-position);
    * ``VECTOR`` — a non-empty set of per-instrument targets with a declared
      :class:`VectorInterdependence` (undeclared ⇒ atomic, fail-closed).

    ``rationale`` is mandatory: an outcome must record why it followed from the
    context (RFC-008 §7). Shape consistency is enforced at construction.
    """

    kind: DecisionKind
    rationale: str
    target: TargetSpec | None = None
    vector: tuple[TargetSpec, ...] = ()
    interdependence: VectorInterdependence | None = None

    @model_validator(mode="after")
    def _shape_consistent(self) -> Decision:
        """Reject a Decision whose payload does not match its kind (fail-closed)."""
        if not self.rationale:
            raise ArtifactIntegrityError("Decision.rationale must be non-empty")
        if self.kind in (DecisionKind.ACTION, DecisionKind.FLAT):
            if self.target is None:
                raise ArtifactIntegrityError(
                    f"Decision kind={self.kind} requires a single target"
                )
            if self.vector:
                raise ArtifactIntegrityError(
                    f"Decision kind={self.kind} must not carry a vector"
                )
            expected = (
                TargetKind.ACTION
                if self.kind is DecisionKind.ACTION
                else TargetKind.FLAT
            )
            if self.target.kind is not expected:
                raise ArtifactIntegrityError(
                    f"Decision kind={self.kind} requires target.kind={expected}"
                )
        elif self.kind is DecisionKind.VECTOR:
            if not self.vector:
                raise ArtifactIntegrityError(
                    "Decision kind=VECTOR requires a non-empty target set "
                    "(an empty vector is not a decision — SOS-INV fail-closed)"
                )
            if self.target is not None:
                raise ArtifactIntegrityError(
                    "Decision kind=VECTOR must not carry a single target"
                )
        else:  # NO_ACTION
            if self.target is not None or self.vector:
                raise ArtifactIntegrityError(
                    "Decision kind=NO_ACTION must carry no target/vector"
                )
        return self


class Rule(FrozenModel):
    """A guarded rule: a non-empty conjunction of comparisons and a Decision.

    ``all_of`` SHALL be non-empty: an empty conjunction would fire *vacuously*
    (``all([]) is True``), which the design forbids (★ vacuous-True prohibition).
    The always-applicable case is expressed by :class:`DecisionPolicy` ``default``,
    never by an empty guard.
    """

    all_of: tuple[Compare, ...]
    decision: Decision

    @model_validator(mode="after")
    def _guard_non_empty(self) -> Rule:
        """Reject an empty guard so a rule can never fire vacuously (★3)."""
        if not self.all_of:
            raise ArtifactIntegrityError(
                "Rule.all_of must be non-empty — an empty guard would fire "
                "vacuously; use DecisionPolicy.default for the unconditional case"
            )
        return self


class DecisionPolicy(FrozenModel):
    """An ordered rule list plus a mandatory default Decision (RFC-008 §9).

    Evaluation is total (there is always a ``default``) and deterministic (rules
    are tried in order, first match wins), so a strategy evaluation over a fixed
    context is a pure function (RFC-008 §9). ``rules`` may be empty — a
    policy that is *only* its default is a valid, always-same-outcome policy.
    """

    rules: tuple[Rule, ...] = ()
    default: Decision


# ---------------------------------------------------------------------------
# Pure evaluator (design §4) — a function of (policy, environment) only.
# ---------------------------------------------------------------------------


def resolve_operand(operand: Operand, env: dict[str, Any]) -> ScalarValue | _Unknown:
    """Resolve an operand to a scalar, or :data:`UNKNOWN` (design §4).

    A ``const`` resolves to its literal. A ``ref`` walks ``env`` by its path; any
    missing component, or a non-scalar leaf, resolves to :data:`UNKNOWN`. The read
    reaches nothing outside ``env`` — no ambient source is reachable (DCE-INV-003).

    Args:
        operand: The operand to resolve.
        env: The Decision Context environment (namespaced Capsule + config view).

    Returns:
        The resolved :data:`ScalarValue`, or :data:`UNKNOWN`.
    """
    if operand.const is not None:
        return operand.const
    value: Any = env
    for part in operand.ref or ():
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return UNKNOWN
    if isinstance(value, bool | int | float | str):
        return value
    return UNKNOWN


def eval_compare(compare: Compare, env: dict[str, Any]) -> bool:
    """Evaluate one comparison; :data:`UNKNOWN` operands make it ``False`` (design §4).

    ``EQ``/``NE`` apply to any scalar pair. Ordering comparisons apply only to
    numbers (a ``bool`` is never an orderable magnitude, and a str/number mismatch
    never orders); an inapplicable comparison is ``False`` (restrictive).

    Args:
        compare: The comparison node.
        env: The Decision Context environment.

    Returns:
        The boolean result (``False`` on any :data:`UNKNOWN` or type mismatch).
    """
    left = resolve_operand(compare.left, env)
    right = resolve_operand(compare.right, env)
    if isinstance(left, _Unknown) or isinstance(right, _Unknown):
        return False
    if compare.op is CompareOp.EQ:
        return type(left) is type(right) and left == right
    if compare.op is CompareOp.NE:
        return not (type(left) is type(right) and left == right)
    # Ordering: numeric-only, bool excluded.
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    if not isinstance(left, int | float) or not isinstance(right, int | float):
        return False
    if compare.op is CompareOp.LT:
        return left < right
    if compare.op is CompareOp.LE:
        return left <= right
    if compare.op is CompareOp.GT:
        return left > right
    return left >= right  # CompareOp.GE


def rule_fires(rule: Rule, env: dict[str, Any]) -> bool:
    """Whether every comparison in a rule's (non-empty) guard holds (design §4)."""
    return all(eval_compare(compare, env) for compare in rule.all_of)


def evaluate_policy(policy: DecisionPolicy, env: dict[str, Any]) -> Decision:
    """Evaluate a policy to its chosen Decision (pure, deterministic; RFC-008 §9).

    Rules are tried in order; the first whose guard fires selects its Decision.
    If none fires, the mandatory ``default`` is chosen — so the result is total
    and depends only on ``(policy, env)`` (referential transparency; design §4).

    Args:
        policy: The authored decision policy.
        env: The Decision Context environment (Capsule + config view).

    Returns:
        The chosen :class:`Decision`.
    """
    for rule in policy.rules:
        if rule_fires(rule, env):
            return rule.decision
    return policy.default
