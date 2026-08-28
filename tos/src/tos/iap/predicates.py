"""iap request / decision / binding / closure / confinement predicates (design #15 §5/§6).

Pure, fail-closed decision rules over injected frozen models (design #15 §0.2/§4.6): iap is a
**control-plane approval kernel, not a serializer / signer / egress engine** — it authors the
complete-exact-request, deterministic-restrictive-decision, exact-binding-chain, invalidation
dependency-closure, UNKNOWN-confinement, and the predicate-only independent-validation /
no-widening / egress-currentness / conflicting-generation rules over injected policy / registry /
capability / age params. There is **no** "assume-complete" / "assume-current" / "default /
wildcard / substitute / union / widen / coerce / promote-UNKNOWN" path anywhere: an ``APPROVE`` /
``True`` comes only from positive proof, everything else is ``DENY`` / ``UNKNOWN`` / ``False``
(design #15 §4.1/§4.2 — the structural seal against the #6 fail-open REJECT lesson).

**Truthy-sentinel consume contract (design #15 §4.7, MANDATED, #14 M1 from the start):** the
``ApprovalResult`` returned by :func:`request_is_complete` / :func:`approval_decision` /
:func:`exact_binding_holds` / :func:`conflicting_evaluators_unknown` is **not** truthy-testable
(``ApprovalResult.__bool__`` raises), so a consumer MUST gate on ``result is
ApprovalResult.APPROVE``. The ``bool | None`` predicates (:func:`unknown_confines` /
:func:`no_widening_no_union` / ...) MUST be gated ``is True``.

The module authors L1-decidable substrate for IAP-EV-001/003/004/007/009 (core) and
IAP-EV-002/006/008/010 (predicate-only) but closes **no** IAP-EV item (authoring is not evidence,
VER-002-001 §5; design #15 §1) — the ``/3`` / ``+Security`` / ``+Broker`` residue remains.

Pure module: stdlib only + ``tos.iap`` records / vocabulary; no ``shared.*``, no sibling
``tos.*`` (design #15 §0.3 — sibling edge 0). iap reads no clock (§3.4/§19).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from tos.iap.records import (
    ApprovalAuthorityEffect,
    ProposalApprovalRequest,
    TradingApprovalPolicy,
)
from tos.iap.vocabulary import ApprovalResult, MaterialityVerdict

__all__ = [
    # core §5
    "request_is_complete",
    "approval_decision",
    "exact_binding_holds",
    "invalidation_closure",
    "materiality_is_material",
    "unknown_confines",
    # predicate-only §6
    "independent_validation_declared",
    "no_widening_no_union",
    "approval_grants_no_authority",
    "active_egress_currentness",
    "conflicting_evaluators_unknown",
]


# ===========================================================================
# internal scope-token classification (§9 line 253 / §4.1)
# ===========================================================================

_UNKNOWN_TOKEN = "UNKNOWN"
_LATEST_TOKEN = "latest"


def _is_wildcard(value: str) -> bool:
    """Whether a scope token is a wildcard / "latest" (§9 line 253; dsl ``proposal.py:59`` isomorph)."""
    return "*" in value or value.strip().lower() == _LATEST_TOKEN


def _scope_state(value: str | None) -> str:
    """Classify one required scalar scope field (§9 line 253 / §4.1).

    Returns ``"deny"`` for an absent / empty / wildcard value (a definite structural
    incompleteness — cannot yield ``APPROVE``), ``"unknown"`` for a present-but-``UNKNOWN`` token
    (an undetermined value — restrictive), and ``"ok"`` for a concrete non-wildcard value.
    """
    if value is None or not value.strip():
        return "deny"  # absent / empty (§9 line 253 "absent, empty ... is incomplete")
    if _is_wildcard(value):
        return "deny"  # wildcard / "latest" (never zero / unconstrained scope, §4.7)
    if value.strip().upper() == _UNKNOWN_TOKEN:
        return "unknown"  # present-but-UNKNOWN action-class / mode / fact (§9 / template L29-30)
    return "ok"


# ===========================================================================
# core §5.1 — complete exact request (IAP-EV-001 substrate, core L1 slice)
# ===========================================================================


def request_is_complete(
    request: ProposalApprovalRequest | None,
    policy: TradingApprovalPolicy | None,
) -> ApprovalResult:
    """Whether the request is one complete, immutable, exact request (§9 / IAP-INV-001 / IAP-AC-001).

    IAP-INV-001 line 134 verbatim: "Approval evaluates one complete immutable request. Omission,
    wildcard, ambiguity, hidden default, substitution, union, patch, or partial refresh is not the
    approved request." §9 line 253 verbatim: "An absent, empty, wildcard, unknown, stale,
    conflicting, or unverifiable required scope or maximum is incomplete and cannot yield
    ``APPROVE``." Returns:

    * ``DENY`` when the request is absent (``None``), when any required scalar scope / artifact-ref
      field is absent / empty / wildcard, when ``required_scope_complete`` / ``single_use`` /
      ``exact_intent_only`` is not positively ``True``, when a required generation is missing, or
      when the required-independent-facts / common-mode declarations are empty (a definite
      structural incompleteness — §9 line 249-253);
    * ``UNKNOWN`` when the ``policy`` is absent (the policy-owned required set cannot be
      determined — self-exempt is prohibited, §8 line 230), or when a present scope field is the
      ``UNKNOWN`` token (an undetermined value — never a permissive default);
    * ``APPROVE`` **only** when every §9 binding field is present, non-wildcard, non-``UNKNOWN``,
      and ``required_scope_complete`` is ``True`` (a *candidate* for approval — completeness is
      necessary, never sufficient; the decision is :func:`approval_decision`).

    A definite ``DENY`` field dominates an ``UNKNOWN`` one (a hard structural reject over an
    undecidable one); both are denial (the consume gate is ``result is ApprovalResult.APPROVE``,
    §4.7). ``policy`` presence is required to know the policy-owned materiality set (§8 line 230).

    Args:
        request: The proposal approval request (``None`` => DENY — absent, §9 line 253).
        policy: The governing spg-owned Trading Approval Policy (``None`` => UNKNOWN).

    Returns:
        The :class:`~tos.iap.vocabulary.ApprovalResult`.
    """
    if request is None:
        return ApprovalResult.DENY  # absent request cannot yield APPROVE (§9 line 253)
    if policy is None:
        # cannot determine the policy-owned required / materiality set (§8 line 230 self-exempt
        # prohibition) — restrictive, not a permissive assume-complete.
        return ApprovalResult.UNKNOWN

    required_scalars: tuple[str | None, ...] = (
        request.proposer_identity,
        request.environment,
        request.account,
        request.instrument,
        request.action_class,
        request.operating_mode,
        request.direction,
        request.position_effect,
        request.quantity_basis,
        request.proposal_id,
        request.proposal_digest,
        request.decision_context_capsule_id,
        request.decision_context_capsule_digest,
        request.critical_input_snapshot_digest,
        request.construction_envelope_id,
        request.construction_envelope_digest,
        request.canonical_broker_command_id,
        request.canonical_broker_command_digest,
        request.venue_snapshot_digest,
        request.venue_admissibility_decision_digest,
        request.broker_capability_profile_digest,
        request.trading_approval_policy_id,
        request.trading_approval_policy_digest,
    )
    saw_unknown = False
    for value in required_scalars:
        state = _scope_state(value)
        if state == "deny":
            return (
                ApprovalResult.DENY
            )  # absent / empty / wildcard dominates (§9 line 253)
        if state == "unknown":
            saw_unknown = True

    # Required non-string completeness signals — any definite structural gap is DENY (§9 line
    # 249-251): a missing generation, a not-True completeness / single-use / exact-intent flag, or
    # an empty required-independent-facts / common-mode declaration set.
    if request.request_generation is None:
        return ApprovalResult.DENY
    if request.trading_approval_policy_generation is None:
        return ApprovalResult.DENY
    if request.required_scope_complete is not True:
        return ApprovalResult.DENY  # template L17 fail-closed default (§4.1)
    if request.single_use is not True or request.exact_intent_only is not True:
        return (
            ApprovalResult.DENY
        )  # template L70-71 (single-use / exact-intent required)
    if not request.required_independent_facts:
        return ApprovalResult.DENY  # §9 line 249 required independent facts absent
    if not request.common_mode_declarations:
        return ApprovalResult.DENY  # §9 line 249 common-mode declarations absent

    if saw_unknown:
        return ApprovalResult.UNKNOWN
    return ApprovalResult.APPROVE


# ===========================================================================
# core §5.2 — deterministic restrictive decision (IAP-EV-003 substrate, core L1 slice)
# ===========================================================================


def approval_decision(
    request: ProposalApprovalRequest | None,
    policy: TradingApprovalPolicy | None,
    generation: int | None,
    *,
    independent_validation_passed: bool | None,
    all_bindings_current: bool | None,
    policy_supports_request: bool | None,
    generation_current: bool | None,
    conflicting_evaluations: bool | None = None,
    unverifiable_input: bool | None = None,
) -> ApprovalResult:
    """The deterministic, restrictive Independent Approval decision (§11 / IAP-INV-003 / IAP-AC-003).

    IAP-INV-003 line 142 verbatim: "The same complete input set under one policy and generation
    yields one deterministic result. Missing, stale, conflicting, unverifiable, unsupported, or
    unknown input yields ``DENY`` or ``UNKNOWN``, never ``APPROVE``." A **pure function**: no
    hidden clock / randomness / locale / env / mutable cache / network / "latest"-registry /
    fallback (§10 line 274), so two evaluations of the same inputs return the same result.

    Restrictive resolution (most-restrictive; ``APPROVE`` never from a negative):

    * ``DENY`` when the request is not complete-``APPROVE`` at ``DENY`` level, or when any required
      fact is a **definite negative** (``independent_validation_passed`` / ``all_bindings_current``
      / ``policy_supports_request`` / ``generation_current`` positively ``False`` — a stale /
      unsupported / broken-binding input, §11 line 289). ``DENY`` is terminal for the request
      (§11 line 296).
    * ``UNKNOWN`` when the request is ``UNKNOWN``-complete, when the generation is missing, when
      any required fact is undetermined (``None``), when evaluators conflict
      (``conflicting_evaluations`` ``True``, §17), or when an input is unverifiable — restrictive
      and requiring new evidence or a new request; it **cannot** be promoted to ``APPROVE`` by
      repeated evaluation, timeout, majority, unused capacity, human preference, prior success, or
      an expected broker rejection (§11 line 296 — there is no promotion path in this pure fn).
    * ``APPROVE`` **only** when the request is complete-``APPROVE`` and every required fact is
      positively ``True`` and the generation is present. ``APPROVE`` is a **non-authorizing
      business gate** — eligibility to be consumed once while every binding remains current; it is
      *not* ``AUTHORIZED_FOR_CAPACITY`` / capacity commitment / Live Authorization / capability
      issuance / transmission (§11 line 294; §1 line 21).

    Args:
        request: The proposal approval request.
        policy: The governing Trading Approval Policy.
        generation: The Trading Approval Generation token (``None`` => UNKNOWN — missing input).
        independent_validation_passed: Injected independent-validation result (``False`` => DENY;
            ``None`` => UNKNOWN).
        all_bindings_current: Injected all-bindings-current fact (``False`` => DENY; ``None`` =>
            UNKNOWN).
        policy_supports_request: Injected policy-supports-request fact (``False`` => DENY;
            ``None`` => UNKNOWN).
        generation_current: Injected generation-current fact (``False`` => DENY; ``None`` =>
            UNKNOWN).
        conflicting_evaluations: Injected conflicting-evaluators flag (``True`` => UNKNOWN, §17).
        unverifiable_input: Injected unverifiable-input flag (``True`` => UNKNOWN).

    Returns:
        The :class:`~tos.iap.vocabulary.ApprovalResult` (truthy-untestable; gate ``is APPROVE``).
    """
    completeness = request_is_complete(request, policy)
    if completeness is ApprovalResult.DENY:
        return ApprovalResult.DENY

    # Definite negatives => DENY (terminal): a positively-False required fact is a stale /
    # unsupported / broken-binding input (§11 line 289), never a permissive fallback.
    if (
        independent_validation_passed is False
        or all_bindings_current is False
        or policy_supports_request is False
        or generation_current is False
    ):
        return ApprovalResult.DENY

    # Undetermined / conflicting / unverifiable / UNKNOWN-complete / missing-generation => UNKNOWN
    # (restrictive; cannot be promoted — §11 line 296).
    if (
        completeness is ApprovalResult.UNKNOWN
        or generation is None
        or conflicting_evaluations is True
        or unverifiable_input is True
        or independent_validation_passed is None
        or all_bindings_current is None
        or policy_supports_request is None
        or generation_current is None
    ):
        return ApprovalResult.UNKNOWN

    # Complete-APPROVE + every required fact positively True + generation present.
    return ApprovalResult.APPROVE


# ===========================================================================
# core §5.3 — exact binding chain (IAP-EV-004 substrate, core L1 slice)
# ===========================================================================


def exact_binding_holds(
    bound_chain: Mapping[str, str | None],
    actual_chain: Mapping[str, str | None],
) -> ApprovalResult:
    """Whether the exact binding chain holds through the pipeline (§13 / IAP-INV-004 / IAP-AC-004).

    IAP-INV-004 line 146: the decision binds the exact Capsule / proposal / construction envelope
    / candidate command / venue snapshot & decision / policies / generations / scope / software /
    deployment / account / broker / route / validity. IAP-AC-004 line 585: "Account, instrument,
    direction, quantity, unit, price, Capsule, venue decision, construction, broker, route,
    environment, policy, generation, software, or deployment substitution invalidates the
    decision." Realized as a **bidirectional set comparison** (design #15 §4.3/§4.7 — the #14
    MAJOR-1 lesson): each link is a ``name -> digest`` scalar; ``bound_chain`` is what the request
    / decision bind and ``actual_chain`` is the actual artifacts' digests. Returns:

    * ``DENY`` when the chains are the ∅ case (empty — a vacuous "binds nothing" is not binding),
      when their link **names differ** (a **missing** link breaks the binding, or a **surplus** /
      substituted link is a different chain — both directions checked), or when a shared link's
      digest is a definite **mismatch** (a substitution — §13 line 585);
    * ``UNKNOWN`` when the names match but a shared link's ``bound`` or ``actual`` digest is
      undetermined (``None``) — never a permissive assume-match;
    * ``APPROVE`` **only** when the link names match exactly (both ways) and every shared link's
      digest is present and exactly equal.

    Args:
        bound_chain: The ``{link-name: digest}`` a request / decision binds (empty => DENY).
        actual_chain: The ``{link-name: digest}`` of the actual artifacts.

    Returns:
        The :class:`~tos.iap.vocabulary.ApprovalResult` (truthy-untestable; gate ``is APPROVE``).
    """
    if set(bound_chain) != set(actual_chain):
        # bidirectional: a missing link (binding broken) OR a surplus / substituted link
        # (a different chain) — both are denial (#14 MAJOR-1 bidirectional set comparison).
        return ApprovalResult.DENY
    if not bound_chain:
        # ∅ fail-closed: a vacuous "binds nothing" is not a binding proof (§4.7).
        return ApprovalResult.DENY
    saw_unknown = False
    for name, bound_digest in bound_chain.items():
        actual_digest = actual_chain[name]
        if bound_digest is None or actual_digest is None:
            saw_unknown = True  # undetermined link — never assume-match
            continue
        if bound_digest != actual_digest:
            return (
                ApprovalResult.DENY
            )  # substitution => a different chain (§13 line 585)
    if saw_unknown:
        return ApprovalResult.UNKNOWN
    return ApprovalResult.APPROVE


# ===========================================================================
# core §5.4 — invalidation dependency closure (IAP-EV-007 substrate, core L1 slice)
# ===========================================================================


def invalidation_closure(
    graph: Mapping[str, frozenset[str]],
    trigger: str,
    *,
    uncertain: Mapping[str, frozenset[str]] | None = None,
) -> frozenset[str]:
    """The complete invalidation dependency closure from a material trigger (§14 / IAP-INV-008 / IAP-AC-007).

    §14 line 361 verbatim: "The system SHALL compute the complete dependency closure across
    requests, decisions, consumption records, Intents, risk/flow decisions, commitments, proofs,
    authorities, capabilities, pending attempts, egresses, and protection." Realized as a **pure
    graph transitive-reachability** from ``trigger`` — L1-decidable (deterministic simulation).
    Fail-closed both ways (design #15 §4.4/§4.7):

    * a **partial closure is fail-open** (catastrophic): a missing dependent escapes invalidation,
      so an **uncertain / unknown edge is EXPANDED** — the ``uncertain`` adjacency is followed
      exactly like the definite ``graph`` adjacency (under-count is prohibited; the #14 MAJOR-1
      safety direction). Materiality is the entry condition: ``UNKNOWN => MATERIAL``
      (:func:`materiality_is_material`; §5.7 line 126);
    * an **empty graph** yields the minimal closure ``{trigger}`` — a "nothing to invalidate" is
      not vacuously empty; the trigger itself is always in its own closure (§4.7);
    * a **proven disconnected** node is **excluded** (the availability side — over-invalidation is
      safe but a spurious block is an availability defect; only *uncertain* edges expand).

    "An invalidation event may be evidence, but absence of the event is not proof of currentness"
    (§14 line 365) — this computes the closure of *present* dependencies; it never infers
    currentness from an absent edge (§6.4). The real material-invalidation-to-egress propagation
    latency (``B_approval_invalid_to_intent`` / ``_to_egress``) is runtime-measured (§8.1); L1 is
    the closure **completeness + expansion** discipline only.

    Args:
        graph: The definite dependency adjacency ``{node: {dependents}}``.
        trigger: The material trigger node (always in its own closure).
        uncertain: Optional uncertain-edge adjacency ``{node: {maybe-dependents}}``, followed
            (expanded) exactly like ``graph`` (fail-closed tie-break — §4.4).

    Returns:
        The frozenset of every node reachable from ``trigger`` (incl. ``trigger``).
    """
    uncertain_adj: Mapping[str, frozenset[str]] = uncertain or {}
    closure: set[str] = set()
    stack: list[str] = [trigger]
    while stack:
        node = stack.pop()
        if node in closure:
            continue
        closure.add(node)
        for dependent in graph.get(node, frozenset()):
            if dependent not in closure:
                stack.append(dependent)
        for dependent in uncertain_adj.get(node, frozenset()):
            # 불확정 edge => 확장 (treat as reachable — under-count is a fail-open, §4.4).
            if dependent not in closure:
                stack.append(dependent)
    return frozenset(closure)


def materiality_is_material(verdict: MaterialityVerdict) -> bool:
    """Whether an approval-change verdict is material — unknown materiality is material (§5.7 line 126).

    §5.7 line 126 verbatim: "Unknown materiality is material." ``True`` for ``MATERIAL`` and
    ``UNKNOWN`` (fail-closed); ``False`` **only** for a positively-``IMMATERIAL`` verdict. This is
    the entry condition for :func:`invalidation_closure` (§5.4).

    Args:
        verdict: The materiality verdict.

    Returns:
        ``True`` iff the change must be treated as material.
    """
    return verdict is not MaterialityVerdict.IMMATERIAL


# ===========================================================================
# core §5.5 — UNKNOWN confinement (IAP-EV-009 substrate, core L1 slice)
# ===========================================================================


def unknown_confines(
    *,
    any_unknown_state: bool | None,
    capacity_available: bool | None = None,
    protective_or_priority_label: bool | None = None,
    human_preference: bool | None = None,
) -> bool:
    """Whether an UNKNOWN state confines (blocks) ordinary new risk (§16 / IAP-INV-010 / IAP-AC-009).

    IAP-INV-010 line 170 verbatim: "UNKNOWN approval, input, common-mode status, consumption
    state, or invalidation state blocks ordinary new risk and cannot be offset by unused
    capacity." §16 line 391: "Available RCL capacity cannot convert uncertainty into permission."
    §16 line 393 / IAP-INV-013: a human approval, emergency priority, exit / hedge / close /
    reduce-only / protective label "do not substitute for this approval or create protective
    authority or reserve."

    The confinement is **unconditional**: ``True`` (new ordinary risk is confined / blocked) when
    ``any_unknown_state`` is ``True`` **or** undetermined (``None`` — fail-closed); ``False`` (not
    blocked *by uncertainty*) **only** when ``any_unknown_state`` is positively ``False``. The
    ``capacity_available`` / ``protective_or_priority_label`` / ``human_preference`` offset inputs
    are accepted to make the "cannot offset" contract explicit and testable — they **deliberately
    never appear in the return**, which *is* the invariant (capacity / label / priority / human
    preference can never convert uncertainty into permission). Protective classification itself is
    ADR-002-001 and a pre-authorized protective lease is ADR-002-001/002 runtime (§3.5); this L1
    slice states only that uncertainty denies the ordinary fallback (§16 line 395).

    Args:
        any_unknown_state: Whether any approval / input / common-mode / consumption / invalidation
            state is UNKNOWN (``True`` / ``None`` => confined; only ``False`` => not confined).
        capacity_available: Injected available-capacity (never offsets — accepted, unused).
        protective_or_priority_label: Injected protective / priority label (never offsets).
        human_preference: Injected human preference (never offsets — human approval is ADR-002-015).

    Returns:
        ``True`` iff ordinary new risk is confined (blocked) — the fail-closed default.
    """
    # The offset inputs are contractually irrelevant: uncertainty confinement cannot be offset by
    # capacity / label / priority / human preference (IAP-INV-010 line 170; §16 line 391/393). The
    # ``del`` makes that non-offset invariant explicit (the canonical ``_verify_id_binding`` /
    # ``del`` precedent) — they are in the signature only so the contract is testable.
    del capacity_available, protective_or_priority_label, human_preference
    return any_unknown_state is not False


# ===========================================================================
# predicate-only §6.1 — independent-validation declaration (IAP-EV-002 substrate)
# ===========================================================================


def independent_validation_declared(
    *,
    proposer_only_value: bool | None,
    shared_failure_path: bool | None,
    common_mode_declared: bool | None,
) -> bool:
    """Whether independent validation is structurally declared (§10 / IAP-INV-002 / IAP-AC-002).

    §10 line 274 verbatim: "The proposer cannot select a more favorable independent source,
    policy version, evaluator, fallback, or residual-risk disposition. Two services sharing the
    same effective failure path do not create independence. Recalculation with the same corrupted
    implementation is not validation." IAP-INV-002 line 138: approval must "not rely solely on
    proposer-produced or common-mode-corrupted facts". The **structural L1 slice only**: ``True``
    **only** when the fact is **not** proposer-only (``proposer_only_value`` positively ``False``),
    does **not** share a failure path (``shared_failure_path`` positively ``False``), and its
    common-mode declaration is present (``common_mode_declared`` positively ``True``). A ``None`` /
    ``True``-shared / ``None``-declaration fails closed. The **real** independent recompute /
    source / parser / mapping / registry / clock common-mode isolation (§10 item 6) is EV-L2
    component-fault / +Security runtime (§27 q3/q4/q9) — not closed here (sibling edge 0: no
    recompute-and-compare, which would need a shared type, §0.4c).

    Args:
        proposer_only_value: Whether the fact is proposer-produced only (``True`` / ``None`` => not
            independent).
        shared_failure_path: Whether two services share an effective failure path (``True`` /
            ``None`` => common-mode, not independent).
        common_mode_declared: Whether the common-mode declaration is present (``False`` / ``None``
            => incomplete).

    Returns:
        ``True`` iff independent validation is structurally declared complete.
    """
    return (
        proposer_only_value is False
        and shared_failure_path is False
        and common_mode_declared is True
    )


# ===========================================================================
# predicate-only §6.3 — no widening / no union + all-false authority (IAP-EV-006 substrate)
# ===========================================================================


def no_widening_no_union(
    *,
    single_exact_decision: bool | None,
    no_union_of_narrower: bool | None,
) -> bool:
    """Whether no widening / union of scope is attempted (§7/§13 / IAP-INV-007 / IAP-AC-006).

    IAP-INV-007 line 158 verbatim: "A narrower decision, multiple decisions, or a later more
    favorable fact cannot be combined to approve broader or different scope." ``True`` **only**
    when the scope is a **single exact decision** (``single_exact_decision`` positively ``True``)
    and there is **no union of narrower decisions** (``no_union_of_narrower`` positively ``True``).
    A ``None`` / ``False`` on either fails closed — a union / widen / later-favorable-fact combine
    is rejected. The credential / route confinement / bypass detection is +Security runtime (§18) —
    not closed here.

    Args:
        single_exact_decision: Whether the scope is a single exact decision (``None`` / ``False``
            => fail-closed).
        no_union_of_narrower: Whether no narrower decisions are unioned (``None`` / ``False`` =>
            fail-closed).

    Returns:
        ``True`` iff no widening / union of scope is attempted.
    """
    return single_exact_decision is True and no_union_of_narrower is True


def approval_grants_no_authority(effect: ApprovalAuthorityEffect) -> bool:
    """Whether the approval authority effect grants nothing (§7 / IAP-INV-005 line 150).

    ``True`` **only** when every authority flag is ``False``. Because
    :class:`~tos.iap.records.ApprovalAuthorityEffect` is unconstructable with any ``True`` flag, a
    constructed effect always grants nothing — this is the defining predicate that states it
    (IAP-INV-005 line 150: "Approval cannot mutate capacity, create headroom, issue authority,
    classify protection, transmit, clear HALT, or re-arm"; the +Security "no live credential
    anywhere" enforcement is IAP-EV-006). Defence in depth: a runtime re-checks it here rather
    than trust an un-validated block (the ioc ``construction_grants_no_authority`` precedent).

    Args:
        effect: The approval authority effect.

    Returns:
        ``True`` iff the effect grants no authority.
    """
    return not (
        effect.mutates_capacity
        or effect.creates_headroom
        or effect.issues_authority
        or effect.classifies_protection
        or effect.transmits
        or effect.clears_halt
        or effect.rearms
    )


# ===========================================================================
# predicate-only §6.4 — active final-egress currentness (IAP-EV-008 substrate)
# ===========================================================================


def active_egress_currentness(
    *,
    active_bounded_proof: bool | None,
    inferred_from_absence: bool | None,
    single_authoritative_consumption: bool | None,
) -> bool:
    """Whether final-egress currentness is actively proven (§15 / IAP-INV-009 / IAP-AC-008).

    §15 line 381 verbatim: "Cached ``APPROVED``, local Intent state, TTL, heartbeat, service
    health, last-known generation, prior verification, eventual consistency, or absence of an
    invalidation event is not sufficient." ``True`` **only** when currentness rests on an **active
    bounded proof** (``active_bounded_proof`` positively ``True``), is **not inferred from the
    absence** of an invalidation event (``inferred_from_absence`` positively ``False`` — §14 line
    365 / §15 line 381), and rests on a **single authoritative consumption**
    (``single_authoritative_consumption`` positively ``True``). A ``None`` fails closed ("Failure
    or ambiguity is denial", §15 line 383). The real final-egress enforcement / capability claim /
    ``SEND_STARTED`` ordering is ADR-002-013/007/024 runtime (§15 line 385) — not closed here.

    Args:
        active_bounded_proof: Whether an active, bounded currentness proof exists (``None`` /
            ``False`` => fail-closed).
        inferred_from_absence: Whether currentness is (illegitimately) inferred from an absent
            event (``True`` / ``None`` => fail-closed).
        single_authoritative_consumption: Whether a single authoritative consumption backs it
            (``None`` / ``False`` => fail-closed).

    Returns:
        ``True`` iff final-egress currentness is actively, bounded-proven.
    """
    return (
        active_bounded_proof is True
        and inferred_from_absence is False
        and single_authoritative_consumption is True
    )


# ===========================================================================
# predicate-only §6.5 — conflicting evaluators => UNKNOWN (IAP-EV-010 substrate)
# ===========================================================================


def conflicting_evaluators_unknown(
    results: Sequence[ApprovalResult],
) -> ApprovalResult:
    """The retained result of concurrent approval evaluators (§17 line 403 / IAP-INV-012 / IAP-AC-010).

    §17 line 403 verbatim: "Concurrent approval evaluators may compute decisions only under one
    exact policy and generation; conflicting results are retained and make the request
    ``UNKNOWN`` until authoritatively resolved. Majority or newest-arrival selection is not
    automatically authoritative." Returns:

    * ``UNKNOWN`` when ``results`` is **empty** (∅ fail-closed) or when the results **conflict**
      (more than one distinct value) — the conflict is retained, and **no** majority / newest
      selection is made;
    * the single agreed result when every evaluator agrees.

    The real partition / split-brain / stale-writer-fence enforcement is EV-L2/L3 +Security
    runtime (§17 line 409); the append-only generation fence is
    :func:`~tos.iap.state.stale_generation_fenced` (``tos.ordering`` REUSE, §6.5). No ``if
    result:`` is used — set membership / ``len`` are truthy-safe (the enum's ``__bool__`` raises).

    Args:
        results: The concurrent evaluators' results (empty => UNKNOWN).

    Returns:
        The retained :class:`~tos.iap.vocabulary.ApprovalResult`.
    """
    if not results:
        return ApprovalResult.UNKNOWN  # ∅ fail-closed
    distinct = set(results)
    if len(distinct) > 1:
        return (
            ApprovalResult.UNKNOWN
        )  # conflict retained; no majority / newest selection
    return next(iter(distinct))
