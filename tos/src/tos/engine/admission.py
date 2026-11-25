"""Typed strategy admission — the D1↔D4 coupling (design #31 §3.2 (3) / §3.5 / §9-4)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from tos.canonical import get_scheme
from tos.dsl import (
    ADMISSIBLE_CONTEXT_SOURCES,
    AdmissibilityResult,
    AdmissibilityVerdict,
    AuthoredStrategy,
    Compare,
    Decision,
    DecisionPolicy,
    Operand,
    TargetSpec,
    analyze,
)
from tos.dsl.lowering import lower_strategy
from tos.engine._base import ArtifactStatus
from tos.engine.records import InstrumentKey
from tos.engine.vocabulary import CAPSULE_CONTEXT_SOURCE, AdmissionVerdict

__all__ = [
    "ESCAPE_CHECKER_ENFORCEMENT_VERSION",
    "AdmissionResult",
    "compare_has_capsule_operand",
    "declared_target_scopes",
    "derive_instrument_key",
    "iter_outcome_gating_compares",
    "operand_source",
    "policy_work_steps",
    "strategy_admissible",
]

ESCAPE_CHECKER_ENFORCEMENT_VERSION = "esc-checker-engine-admission-0"


@dataclass(frozen=True)
class AdmissionResult:
    """The typed-admission judgement plus its reasons (design #31 §3.5/§9-4)."""

    verdict: AdmissionVerdict
    reasons: tuple[str, ...] = ()
    instrument_key: InstrumentKey | None = None
    admissibility_result: AdmissibilityResult | None = None


def operand_source(operand: Operand) -> str | None:
    """Return the Decision Context source a ``ref`` operand names, else ``None``."""
    if operand.ref is None or not operand.ref:
        return None
    return operand.ref[0]


def iter_outcome_gating_compares(policy: DecisionPolicy) -> Iterator[Compare]:
    """Yield every comparison that gates which outcome the policy selects (design #31 §3.5)."""
    for rule in policy.rules:
        yield from rule.all_of


def compare_has_capsule_operand(compare: Compare) -> bool:
    """Whether an outcome-gating comparison reads at least one capsule-sourced operand."""
    for operand in (compare.left, compare.right):
        source = operand_source(operand)
        if source is None:
            continue
        if source not in ADMISSIBLE_CONTEXT_SOURCES:
            continue
        if source == CAPSULE_CONTEXT_SOURCE:
            return True
    return False


def _iter_decisions(policy: DecisionPolicy) -> Iterator[Decision]:
    """Yield every Decision node a policy can select (each rule's, plus the default)."""
    for rule in policy.rules:
        yield rule.decision
    yield policy.default


def _iter_targets(policy: DecisionPolicy) -> Iterator[TargetSpec]:
    """Yield every :class:`~tos.dsl.TargetSpec` the policy declares, in authored order."""
    for decision in _iter_decisions(policy):
        if decision.target is not None:
            yield decision.target
        yield from decision.vector


def declared_target_scopes(
    strategy: AuthoredStrategy,
) -> tuple[tuple[str | None, str | None], ...]:
    """Return the distinct (account, instrument) scopes the strategy's own targets declare."""
    if strategy.policy is None:
        return ()
    scopes: list[tuple[str | None, str | None]] = []
    for target in _iter_targets(strategy.policy):
        scope = (target.account, target.instrument)
        if scope not in scopes:
            scopes.append(scope)
    return tuple(scopes)


def derive_instrument_key(
    strategy: AuthoredStrategy,
) -> tuple[InstrumentKey | None, tuple[str, ...]]:
    """Derive the dispatch key structurally from the strategy's declared scope (design #31 §3.3)."""
    scopes = declared_target_scopes(strategy)
    if not scopes:
        return None, (
            "strategy declares no TargetSpec scope — the dispatch key cannot be derived "
            "structurally (design #31 §3.3)",
        )
    if len(scopes) > 1:
        return None, (
            f"strategy declares {len(scopes)} distinct (account, instrument) scopes {scopes} — "
            "slice #1 dispatch is per-instrument (design #31 §3.1/§3.3)",
        )
    account, instrument = scopes[0]
    if account is None or instrument is None:
        return None, (
            f"strategy declares a wildcard (None) scope (account={account!r}, "
            f"instrument={instrument!r}) — registration is refused, mirroring the RFC-003 "
            "§9:279-283 Proposal wildcard prohibition (design #31 §3.3)",
        )
    try:
        return InstrumentKey(account=account, instrument=instrument), ()
    except ValueError as exc:
        return None, (f"declared scope is not a usable dispatch key: {exc}",)


def policy_work_steps(policy: DecisionPolicy) -> int:
    """The **static** structural complexity count of a policy (design #31 §3.4, MINOR-2)."""
    rules = policy.rules
    compares = tuple(compare for rule in rules for compare in rule.all_of)
    operands = tuple(
        operand for compare in compares for operand in (compare.left, compare.right)
    )
    return len(rules) + len(compares) + len(operands)


def _admissibility_result_id(strategy: AuthoredStrategy) -> str:
    """The independent id an escape-checker record for ``strategy`` uses (design #31 §9-4)."""
    return f"admres-{strategy.strategy_id}"


def _escape_checker_result(strategy: AuthoredStrategy) -> AdmissibilityResult:
    """Run the escape-checker over ``strategy``'s lowered candidate program (design #31 §9-4)."""
    program = lower_strategy(strategy)
    analysis = analyze(program)
    return AdmissibilityResult.issue(
        scheme=get_scheme(strategy.canonicalization_version),
        result_id=_admissibility_result_id(strategy),
        candidate=program,
        verdict=analysis.verdict,
        reasons=analysis.reasons,
        enforcement_mechanism_version=ESCAPE_CHECKER_ENFORCEMENT_VERSION,
        dsl_version=strategy.dsl_version,
        strategy_id=strategy.strategy_id,
        strategy_digest=strategy.canonical_digest,
    )


def strategy_admissible(strategy: AuthoredStrategy) -> AdmissionResult:
    """The typed admission gate (design #31 §3.5/§9-4)."""
    reasons: list[str] = []
    if strategy.status is not ArtifactStatus.ISSUED:
        reasons.append(
            f"strategy status is {strategy.status} — only an ISSUED Authored Strategy is an "
            "admissible authoring input (design #31 §3.5)"
        )
    policy = strategy.policy
    if policy is None:
        reasons.append("strategy carries no embedded DecisionPolicy (design #31 §3.5)")
        return AdmissionResult(
            verdict=AdmissionVerdict.INADMISSIBLE, reasons=tuple(reasons)
        )

    for index, compare in enumerate(iter_outcome_gating_compares(policy)):
        if not compare_has_capsule_operand(compare):
            reasons.append(
                f"outcome-gating compare #{index} has no capsule-sourced operand "
                f"(left={compare.left!r}, right={compare.right!r}) — a market-dependent decision "
                "may not be routed through config or literals (RFC-008 §10:327-331; RFC-003 "
                "§8:236-237; design #31 §3.2 (3))"
            )

    admissibility_result: AdmissibilityResult | None = None
    if strategy.status is ArtifactStatus.ISSUED:
        admissibility_result = _escape_checker_result(strategy)
        if admissibility_result.verdict is AdmissibilityVerdict.INADMISSIBLE:
            reasons.extend(
                f"escape-checker: {reason}" for reason in admissibility_result.reasons
            )

    key, key_reasons = derive_instrument_key(strategy)
    reasons.extend(key_reasons)

    if reasons:
        return AdmissionResult(
            verdict=AdmissionVerdict.INADMISSIBLE,
            reasons=tuple(reasons),
            admissibility_result=admissibility_result,
        )
    return AdmissionResult(
        verdict=AdmissionVerdict.ADMISSIBLE,
        instrument_key=key,
        admissibility_result=admissibility_result,
    )
