"""Typed strategy admission — the D1↔D4 coupling (design #31 §3.2 (3) / §3.5 / §9-4).

**Seam closed (design #31 §9-4).** Design #31 §3.5 originally deferred the escape-checker seam:
Slice #1 accepted only **in-process typed** :class:`~tos.dsl.AuthoredStrategy` objects, whose typed
algebra of :mod:`tos.dsl.vocabulary` is admissible *by construction* (there is no node type for an
import / clock / network / reflection effect), so the escape-checker was deliberately not called.
With :func:`tos.dsl.lowering.lower_strategy` now bridging the typed algebra into the candidate-AST
domain the checker consumes, :func:`strategy_admissible` runs **both** gates on every strategy: the
structural D1↔D4 capsule-operand walk below, and the escape-checker (:func:`tos.dsl.admissibility.
analyze`) over the strategy's lowered program. Because the typed algebra cannot express an escape,
every currently-constructible :class:`~tos.dsl.AuthoredStrategy` still passes the escape-checker
trivially — this gate closes the *seam* (design #31 §9-4's honest requirement was that the checker
actually run, not that it find anything new to reject on today's typed inputs) and is the identical
gate a :func:`tos.dsl.serialization.parse_strategy`-issued strategy goes through, since both produce
an :class:`~tos.dsl.AuthoredStrategy` and this function does not distinguish how one was built
(design #31 §1.2 "두 경로 동형").

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

#: The escape-checker mechanism version this gate records (DCE-INV-005 version facet, design #31
#: §3.5/§9-4) — an injected named constant, never left implicit. Bumping it is the seam for a future
#: checker revision. Like the sibling ``dsl_evaluation_budget_steps`` note (``tos.engine.__init__``
#: docstring), this is **not** a VERIFICATION-PROFILE-002 key; it identifies *this* module's call
#: site of the checker, not a profile-approved bound.
ESCAPE_CHECKER_ENFORCEMENT_VERSION = "esc-checker-engine-admission-0"


@dataclass(frozen=True)
class AdmissionResult:
    """The typed-admission judgement plus its reasons (design #31 §3.5/§9-4).

    ``verdict`` is the positive-identity gate (``verdict is AdmissionVerdict.ADMISSIBLE``);
    ``reasons`` records *every* failing observation so a refusal is never silent.
    ``instrument_key`` is populated only when key derivation succeeded.
    ``admissibility_result`` binds the escape-checker's own evidence record (G12: it names the exact
    ``strategy_id``/``strategy_digest`` this verdict is attributable to) whenever the checker ran —
    i.e. whenever the strategy carried a policy and was ISSUED (design #31 §9-4).
    """

    verdict: AdmissionVerdict
    reasons: tuple[str, ...] = ()
    instrument_key: InstrumentKey | None = None
    admissibility_result: AdmissibilityResult | None = None


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


def declared_target_scopes(
    strategy: AuthoredStrategy,
) -> tuple[tuple[str | None, str | None], ...]:
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


def derive_instrument_key(
    strategy: AuthoredStrategy,
) -> tuple[InstrumentKey | None, tuple[str, ...]]:
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
    operands = tuple(
        operand for compare in compares for operand in (compare.left, compare.right)
    )
    return len(rules) + len(compares) + len(operands)


def _admissibility_result_id(strategy: AuthoredStrategy) -> str:
    """The independent id an escape-checker record for ``strategy`` uses (design #31 §9-4).

    Deterministically derived from the strategy's own content-addressed identity, so re-checking
    the same strategy twice yields the same record identity — never a fresh id per call, which
    would make replay/audit unable to recognize "the same check, run again" as the same record.

    Args:
        strategy: The (ISSUED) Authored Strategy.

    Returns:
        The independent ``AdmissibilityResult.result_id`` to issue under.
    """
    return f"admres-{strategy.strategy_id}"


def _escape_checker_result(strategy: AuthoredStrategy) -> AdmissibilityResult:
    """Run the escape-checker over ``strategy``'s lowered candidate program (design #31 §9-4).

    ``lower_strategy`` -> ``analyze`` -> the bound :class:`~tos.dsl.evidence.AdmissibilityResult` —
    both the in-process typed path and a ``tos.dsl.serialization.parse_strategy``-issued strategy
    converge on this one call, since both produce an :class:`~tos.dsl.AuthoredStrategy` and this
    function does not distinguish how one was built (design #31 §1.2 "두 경로 동형"). The record
    reuses ``strategy.canonicalization_version`` (the scheme the strategy itself was issued under)
    rather than a second hard-coded version, and binds ``strategy.strategy_id`` /
    ``strategy.canonical_digest`` (G12).

    Args:
        strategy: The **ISSUED** Authored Strategy (callers verify this first — an unissued
            strategy has no ``canonicalization_version``/``canonical_digest`` to key on).

    Returns:
        The issued :class:`~tos.dsl.evidence.AdmissibilityResult`.
    """
    program = lower_strategy(strategy)
    analysis = analyze(program)
    return AdmissibilityResult.issue(  # type: ignore[return-value]
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
    """The typed admission gate (design #31 §3.5/§9-4).

    Positive checks, all of which must hold:

    1. the artifact is an **issued** Authored Strategy carrying an embedded policy (a draft or
       policy-less artifact is not an admissible authoring input);
    2. every outcome-gating comparison has at least one capsule-sourced operand — the D1↔D4
       partial seal (design #31 §3.2 (3));
    3. the strategy's lowered candidate program is ADMISSIBLE under the escape-checker
       (:func:`tos.dsl.admissibility.analyze`) — the seam design #31 §3.5 deferred, now closed
       (design #31 §9-4). Every currently-constructible typed strategy passes this trivially (the
       typed algebra cannot express an escape); the gate is real regardless, and it is the
       identical gate a serialized (``tos.dsl.serialization.parse_strategy``) strategy goes through;
    4. a single wildcard-free dispatch key derives structurally from the declared scope
       (design #31 §3.3).

    Both the in-process typed path and the parsed path reach this function as an
    :class:`~tos.dsl.AuthoredStrategy`, so they are gated identically (design #31 §1.2).

    Args:
        strategy: The Authored Strategy (in-process typed or parsed).

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
        # Only an ISSUED strategy has a real canonicalization_version/canonical_digest to key an
        # escape-checker record on; a non-ISSUED strategy is refused above regardless (the status
        # reason already forces INADMISSIBLE), so skipping the checker here avoids a
        # get_scheme(None) crash on an input that is already going to be inadmissible — fail-closed
        # via the recorded reason, never via an uncaught raise.
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
