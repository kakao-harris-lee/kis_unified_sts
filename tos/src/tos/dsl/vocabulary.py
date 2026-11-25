"""Authoring Surface Vocabulary = closed typed AST algebra (design §3.1, DCE-INV-001)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import model_validator

from tos.dsl._base import ArtifactIntegrityError, FrozenModel

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

ADMISSIBLE_CONTEXT_SOURCES: frozenset[str] = frozenset({"capsule", "config"})


ScalarValue = bool | int | float | str


class _Unknown:
    """Singleton sentinel for an unresolved / non-scalar context read (design §4)."""

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
    """Portfolio-vector component interdependence (ADR-DEV-007 §5, SOS-INV-006)."""

    ATOMIC = "ATOMIC"
    INDEPENDENT = "INDEPENDENT"


class Operand(FrozenModel):
    """A value operand: exactly one of a literal ``const`` or a context ``ref``."""

    const: ScalarValue | None = None
    ref: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> Operand:
        """Exactly one of ``const`` / ``ref`` is set, ``ref`` is non-empty, and its source admissible."""
        has_const = self.const is not None
        has_ref = self.ref is not None
        if has_const == has_ref:
            raise ArtifactIntegrityError(
                "Operand must set exactly one of const / ref "
                f"(const={self.const!r}, ref={self.ref!r})"
            )
        if has_ref and not self.ref:
            raise ArtifactIntegrityError("Operand.ref must be a non-empty path")
        if self.ref and self.ref[0] not in ADMISSIBLE_CONTEXT_SOURCES:
            raise ArtifactIntegrityError(
                f"Operand.ref names a source outside ADMISSIBLE_CONTEXT_SOURCES "
                f"(source={self.ref[0]!r}, admissible={sorted(ADMISSIBLE_CONTEXT_SOURCES)}) — "
                "there is no way to name an ambient source here (DCE-INV-003)"
            )
        return self


class Compare(FrozenModel):
    """A pure, total comparison of two operands (RFC-008 §7)."""

    left: Operand
    op: CompareOp
    right: Operand


class TargetSpec(FrozenModel):
    """A single per-instrument authored target (ADR-DEV-007 §8; ADR-002-020 §8 anchor)."""

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
    """A terminal authored outcome node (RFC-008 §6 principle 2; ADR-DEV-007)."""

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
        else:
            if self.target is not None or self.vector:
                raise ArtifactIntegrityError(
                    "Decision kind=NO_ACTION must carry no target/vector"
                )
        return self


class Rule(FrozenModel):
    """A guarded rule: a non-empty conjunction of comparisons and a Decision."""

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
    """An ordered rule list plus a mandatory default Decision (RFC-008 §9)."""

    rules: tuple[Rule, ...] = ()
    default: Decision


def resolve_operand(operand: Operand, env: dict[str, Any]) -> ScalarValue | _Unknown:
    """Resolve an operand to a scalar, or :data:`UNKNOWN` (design §4)."""
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
    """Evaluate one comparison; :data:`UNKNOWN` operands make it ``False`` (design §4)."""
    left = resolve_operand(compare.left, env)
    right = resolve_operand(compare.right, env)
    if isinstance(left, _Unknown) or isinstance(right, _Unknown):
        return False
    if compare.op is CompareOp.EQ:
        return type(left) is type(right) and left == right
    if compare.op is CompareOp.NE:
        return not (type(left) is type(right) and left == right)
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
    return left >= right


def rule_fires(rule: Rule, env: dict[str, Any]) -> bool:
    """Whether every comparison in a rule's (non-empty) guard holds (design §4)."""
    return all(eval_compare(compare, env) for compare in rule.all_of)


def evaluate_policy(policy: DecisionPolicy, env: dict[str, Any]) -> Decision:
    """Evaluate a policy to its chosen Decision (pure, deterministic; RFC-008 §9)."""
    for rule in policy.rules:
        if rule_fires(rule, env):
            return rule.decision
    return policy.default
