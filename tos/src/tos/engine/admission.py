"""Typed strategy admission — the D1↔D4 coupling (design #31 §3.2 (3) / §3.5).

Slice #1 accepts **in-process typed** :class:`~tos.dsl.AuthoredStrategy` objects only. The typed
algebra of :mod:`tos.dsl.vocabulary` is admissible *by construction* (there is no node type for an
import / clock / network / reflection effect), so the escape-checker — which exists for candidates
arriving from **outside** the type system — is deliberately **not** called here, and this slice
therefore makes **no** claim about the escape-safety of a serialized authoring path (design #31
§3.5 "정직 한계"; the serialization lowering + checking + strategy↔verdict binding seam is reserved
for a later cycle, design #31 §9-4).

What admission *does* own is the engine's share of the D1 env-configuration contract
(design #31 §3.2 (3), v1.1 MAJOR-2 redefinition):

    an outcome-gating ``Compare`` SHALL have at least one capsule-sourced ``ref`` operand;
    a comparison whose operands are all literals or all config-sourced refs is inadmissible.

That is a pure AST walk over ``DecisionPolicy.rules -> Rule.all_of -> Compare.left/right ->
Operand.const/ref`` — no DSL change, no escape-checker involvement.

**Honest scope (partial sealing).** This blocks the core case — a market-dependent decision routed
entirely through ``config`` — but it cannot stop a dishonest author who puts a market value in
``config`` *and* keeps a capsule operand alongside it. Complete enforcement belongs to the D-E2
Critical Input Snapshot provenance surface (RFC-004 §9:242-244 "source identity, continuity, and
provenance … never by unattributed fetch or side channel"). Claiming more here would be
over-claiming (design #31 §3.2 (3)/§3.5/§10.2-5).

**∅ discipline.** A policy with zero rules has *no* outcome-gating comparison, so there is nothing
for this predicate to reject; it is admissible with respect to *this* rule, and that is recorded
honestly rather than papered over with an over-rejection (the #26 WDR MAJOR-1 lesson: check the
applicable side before rejecting an empty).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #31 §0.3).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from tos.dsl import (
    ADMISSIBLE_CONTEXT_SOURCES,
    AuthoredStrategy,
    Compare,
    Decision,
    DecisionPolicy,
    Operand,
    TargetSpec,
)
from tos.engine._base import ArtifactStatus
from tos.engine.records import InstrumentKey
from tos.engine.vocabulary import CAPSULE_CONTEXT_SOURCE, AdmissionVerdict

__all__ = [
    "AdmissionResult",
    "compare_has_capsule_operand",
    "declared_target_scopes",
    "derive_instrument_key",
    "iter_outcome_gating_compares",
    "operand_source",
    "policy_work_steps",
    "strategy_admissible",
]


@dataclass(frozen=True)
class AdmissionResult:
    """The typed-admission judgement plus its reasons (design #31 §3.5).

    ``verdict`` is the positive-identity gate (``verdict is AdmissionVerdict.ADMISSIBLE``);
    ``reasons`` records *every* failing observation so a refusal is never silent.
    ``instrument_key`` is populated only when key derivation succeeded.
    """

    verdict: AdmissionVerdict
    reasons: tuple[str, ...] = ()
    instrument_key: InstrumentKey | None = None


def operand_source(operand: Operand) -> str | None:
    """Return the Decision Context source a ``ref`` operand names, else ``None``.

    A ``const`` operand names no source (it is an authored literal). A ``ref`` operand's first
    path component is its source (``tos.dsl.vocabulary.Operand`` docstring; ``resolve_operand``
    walks the namespaced environment).

    Args:
        operand: The operand to inspect.

    Returns:
        The source token for a ``ref`` operand, else ``None``.
    """
    if operand.ref is None or not operand.ref:
        return None
    return operand.ref[0]


def iter_outcome_gating_compares(policy: DecisionPolicy) -> Iterator[Compare]:
    """Yield every comparison that gates which outcome the policy selects (design #31 §3.5).

    The outcome-gating comparisons are exactly the guards of the ordered rule list: the mandatory
    ``default`` is reached when no guard fires and is gated by nothing, so it contributes no
    comparison.

    Args:
        policy: The authored decision policy.

    Yields:
        Each :class:`~tos.dsl.Compare` in each rule's non-empty conjunction, in authored order.
    """
    for rule in policy.rules:
        yield from rule.all_of


def compare_has_capsule_operand(compare: Compare) -> bool:
    """Whether an outcome-gating comparison reads at least one capsule-sourced operand.

    The D1↔D4 predicate (design #31 §3.2 (3)). ``True`` **only** when at least one operand is a
    ``ref`` whose source is positively :data:`~tos.engine.vocabulary.CAPSULE_CONTEXT_SOURCE`; a
    comparison of two literals, or of config-sourced refs alone, is the config-relabelling escape
    this seals (RFC-008 §10:327-331; RFC-003 §8:236-237).

    A ``ref`` naming a source outside :data:`tos.dsl.ADMISSIBLE_CONTEXT_SOURCES` is not a capsule
    read either — it is an inadmissible source, handled the same restrictive way.

    Args:
        compare: The comparison node.

    Returns:
        ``True`` iff at least one operand is a capsule-sourced ``ref``.
    """
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


def declared_target_scopes(strategy: AuthoredStrategy) -> tuple[tuple[str | None, str | None], ...]:
    """Return the distinct (account, instrument) scopes the strategy's own targets declare.

    The **structural** source of the dispatch key (design #31 §3.3): the scopes are read out of
    the strategy's embedded policy, never from a registrant's assertion. ``TargetSpec.account`` /
    ``.instrument`` are ``str | None`` (``tos.dsl.vocabulary`` lines 204-205), so a ``None`` shows
    up here verbatim and is rejected downstream — it is not silently skipped.

    Args:
        strategy: The Authored Strategy.

    Returns:
        The distinct declared scopes, in first-seen order (empty when the policy declares none).
    """
    if strategy.policy is None:
        return ()
    scopes: list[tuple[str | None, str | None]] = []
    for target in _iter_targets(strategy.policy):
        scope = (target.account, target.instrument)
        if scope not in scopes:
            scopes.append(scope)
    return tuple(scopes)


def derive_instrument_key(strategy: AuthoredStrategy) -> tuple[InstrumentKey | None, tuple[str, ...]]:
    """Derive the dispatch key structurally from the strategy's declared scope (design #31 §3.3).

    Fail-closed in three ways, each a named refusal rather than a default:

    * **no declared target** — nothing to key on (a policy of pure no-actions is undispatchable);
    * **more than one distinct scope** — slice #1 is per-instrument (RFC-003 §9:327-339 atomic
      unit; multi-symbol vectors are deferred), so a strategy declaring two scopes has no single
      key;
    * **a ``None`` (wildcard) account or instrument** — key derivation is impossible, the
      dispatch-layer mirror of the RFC-003 §9:279-283 Proposal wildcard prohibition (design #31
      §3.3 MINOR-1).

    Args:
        strategy: The Authored Strategy.

    Returns:
        ``(key, reasons)``: the derived key with an empty reason tuple, or ``(None, reasons)``.
    """
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
    except ValueError as exc:  # ArtifactIntegrityError subclasses ValueError
        return None, (f"declared scope is not a usable dispatch key: {exc}",)


def policy_work_steps(policy: DecisionPolicy) -> int:
    """The **static** structural complexity count of a policy (design #31 §3.4, MINOR-2).

    :func:`tos.dsl.resolve_bound` is a pure integer comparison; it does **not** interrupt
    :func:`tos.dsl.evaluate` mid-run, and ``evaluate`` reports no step count. The engine therefore
    derives the work count *before* calling ``evaluate``, by walking the policy structure — rules,
    their comparisons, and those comparisons' operands. The result is a symbolic count compared
    against the injected ``budget_steps``; it is not a wall-time or CPU measurement, and real
    metering + enforcement remains layer-3 runtime (``tos.dsl.bounds`` module docstring).

    Args:
        policy: The authored decision policy.

    Returns:
        The symbolic work-step count (``>= 0``).
    """
    rules = policy.rules
    compares = tuple(compare for rule in rules for compare in rule.all_of)
    operands = tuple(operand for compare in compares for operand in (compare.left, compare.right))
    return len(rules) + len(compares) + len(operands)


def strategy_admissible(strategy: AuthoredStrategy) -> AdmissionResult:
    """The typed in-process admission gate (design #31 §3.5).

    Positive checks, all of which must hold:

    1. the artifact is an **issued** Authored Strategy carrying an embedded policy (a draft or
       policy-less artifact is not an admissible authoring input);
    2. every outcome-gating comparison has at least one capsule-sourced operand — the D1↔D4
       partial seal (design #31 §3.2 (3));
    3. a single wildcard-free dispatch key derives structurally from the declared scope
       (design #31 §3.3).

    Args:
        strategy: The in-process typed Authored Strategy.

    Returns:
        The :class:`AdmissionResult` — ``ADMISSIBLE`` only when every check passes positively.
    """
    reasons: list[str] = []
    if strategy.status is not ArtifactStatus.ISSUED:
        reasons.append(
            f"strategy status is {strategy.status} — only an ISSUED Authored Strategy is an "
            "admissible authoring input (design #31 §3.5)"
        )
    policy = strategy.policy
    if policy is None:
        reasons.append("strategy carries no embedded DecisionPolicy (design #31 §3.5)")
        return AdmissionResult(verdict=AdmissionVerdict.INADMISSIBLE, reasons=tuple(reasons))

    for index, compare in enumerate(iter_outcome_gating_compares(policy)):
        if not compare_has_capsule_operand(compare):
            reasons.append(
                f"outcome-gating compare #{index} has no capsule-sourced operand "
                f"(left={compare.left!r}, right={compare.right!r}) — a market-dependent decision "
                "may not be routed through config or literals (RFC-008 §10:327-331; RFC-003 "
                "§8:236-237; design #31 §3.2 (3))"
            )

    key, key_reasons = derive_instrument_key(strategy)
    reasons.extend(key_reasons)

    if reasons:
        return AdmissionResult(verdict=AdmissionVerdict.INADMISSIBLE, reasons=tuple(reasons))
    return AdmissionResult(verdict=AdmissionVerdict.ADMISSIBLE, instrument_key=key)
