"""venue admissibility decision predicates (design #19 §5/§6) — pure, fail-closed.

Pure decision rules over injected frozen models (design #19 §0.2/§4.6): venue is an
**order-admissibility gate, not a conformance / capacity / approval / capability judge** —
intent-order conformance is ioc-owned, capacity mutation is rcl/are-owned, approval is
iap-owned, capability semantics are brokercap-owned, CII construction is capsule-owned, and
active currentness is ADR-002-024-owned (§3.5). venue **consumes** those injected results
(candidate command digest, brokercap ceiling scalar, capsule digest, session evidence) and
judges only venue-constraint admissibility; it re-authors none of them. There is **no**
"assume-admissible" / "infer-tradability" / "promote-capability" / "bypass-via-protective-label"
path anywhere: a positive result comes only from positive proof, everything else is
``INADMISSIBLE`` / ``UNKNOWN`` / ``False`` (design #19 §4.1 — the structural seal against the #6
fail-open lesson).

**Truthy-sentinel discipline (design #19 §4.7).** ``OrderAdmissibilityResult`` /
``TradabilityState`` are truthy-untestable ``StrEnum``s (``__bool__`` raises), so every gate
uses ``x is ENUM.SAFE_VALUE`` (e.g. ``result is OrderAdmissibilityResult.ADMISSIBLE``) — the
``RESTRICTED_PROTECTIVE_ONLY`` truthy fail-open (reading protective-only as full permission) is
the single largest risk this seal blocks (§0.4d). Injected ``bool | None`` flags are normalized
with ``is True`` / ``is not True`` (a ``None`` is UNKNOWN, never a soft pass).

**Shared reachability kernel (design #19 §5.4 / MINOR-5).** §18 material-change closure uses the
single private :func:`_reachability_closure` — the same pure transitive-reachability the iap
``invalidation_closure`` (``iap/predicates.py:347``) and sbr ``_reachability_closure``
(``sbr/predicates.py:81``) author, **re-authored locally** (import of ``tos.iap`` / ``tos.sbr``
is forbidden — sibling edge 0; the DRY is preserved at the property-test-contract level, not by
code sharing, design #19 §0.4d). Its axioms: ``trigger`` is always in its own closure; monotone
(adding uncertain edges only widens); a cycle terminates (visited set); an uncertain / unproven
edge is **expanded** (under-count is a fail-open); an empty graph yields the minimal closure
``{trigger}``.

Pure module: ``pydantic`` + stdlib + ``tos.venue.*`` (records / vocabulary) only; no
``shared.*``, no other sibling ``tos.*`` (design #19 §0.3).
"""

from __future__ import annotations

from collections.abc import Mapping

from tos.venue.records import (
    AccountMarginFacts,
    BindingChain,
    InstrumentRouteFields,
    OrderAdmissibilityDecision,
    OrderShapeFields,
    PolicyResolution,
    SourceContinuity,
    SourceObservation,
    VenueGateAuthorityEffect,
    VenueShapeConstraints,
)
from tos.venue.vocabulary import (
    ActionClass,
    OrderAdmissibilityResult,
    TradabilityState,
)

__all__ = [
    # core §5 (VTG-EV-003/004/006 substrate)
    "exact_instrument_route_bound",
    "order_shape_admissible",
    "decision_binding_exact",
    "no_decision_union",
    "material_change_closure",
    # predicate-only §6 (VTG-EV-002/005/007/008/009/010/011/012 substrate)
    "tradability_conflict_unknown",
    "account_constraint_conservative",
    "egress_currentness_active",
    "stale_decision_rejected_at_egress",
    "exit_not_assumed_admissible",
    "protective_label_no_bypass",
    "common_mode_reduces_scope",
    "unknown_continuity_invalidates",
    "gate_authority_separated",
    "reopen_revives_nothing",
]

#: The exact-match scalar routing fields of :class:`~tos.venue.records.InstrumentRouteFields`
#: (the alias set is compared separately for set equality, §5.2).
_ROUTE_SCALAR_FIELDS: tuple[str, ...] = (
    "canonical_instrument_id",
    "venue_listing",
    "market_segment",
    "contract_month",
    "product_type",
    "currency",
    "multiplier",
    "expiration",
    "settlement_method",
    "account_mapping",
    "environment",
    "broker",
    "route",
)

#: The exit-class actions independently constrained (§6.4; VTG-INV-003 line 157). An exit /
#: reduce-only / cancel / replacement / protective action's admissibility is never assumed from
#: an entry's — it must be positively proven.
_EXIT_ACTION_CLASSES: frozenset[ActionClass] = frozenset(
    {
        ActionClass.DECREASE,
        ActionClass.CLOSE,
        ActionClass.REVERSAL,
        ActionClass.CANCEL,
        ActionClass.AMEND,
        ActionClass.REPLACE,
        ActionClass.REDUCE_ONLY,
        ActionClass.PROTECTIVE,
        ActionClass.EMERGENCY,
    }
)


# ===========================================================================
# Shared reachability kernel (design #19 §5.4 / MINOR-5)
# ===========================================================================


def _reachability_closure(
    graph: Mapping[str, frozenset[str]],
    trigger: str,
    *,
    unproven: Mapping[str, frozenset[str]] | None = None,
) -> frozenset[str]:
    """The transitive-reachability closure from ``trigger`` (design #19 §5.4 / §0.4d).

    The single kernel behind :func:`material_change_closure` (§18 invalidation) — isomorphic to
    the iap ``invalidation_closure`` (``iap/predicates.py:347``) and sbr ``_reachability_closure``
    (``sbr/predicates.py:81``), re-authored locally (sibling edge 0). Axioms (regressed by the
    §7 shared-closure property contract, incl. the ``test_seam_iap`` / ``test_seam_sbr``
    cross-checks):

    * ``trigger`` is always in its own closure (an empty graph yields ``{trigger}`` — a
      "nothing reachable" is not a vacuous empty set, design #19 §4.7);
    * an **uncertain / unproven** edge is followed exactly like a definite edge — an under-count
      would let a dependent escape invalidation (a fail-open; §18 line 412 "Failure to prove
      complete propagation expands containment"; §5.8 "Unknown materiality is material");
    * a **proven-disconnected** node (absent from both adjacencies) is excluded (the
      availability side — over-expansion is safe, a spurious block is an availability defect);
    * a cycle terminates (visited set) and includes the cycle.

    Args:
        graph: The definite dependency adjacency ``{node: {dependents}}``.
        trigger: The trigger node (always in its own closure).
        unproven: Optional uncertain-edge adjacency ``{node: {maybe-dependents}}``, followed
            (expanded) exactly like ``graph`` (fail-closed tie-break — under-count is
            prohibited, design #19 §4.7).

    Returns:
        The frozenset of every node reachable from ``trigger`` (incl. ``trigger``).
    """
    unproven_adj: Mapping[str, frozenset[str]] = unproven or {}
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
        for dependent in unproven_adj.get(node, frozenset()):
            # 불확정 edge => 확장 (treat as reachable — under-count is a fail-open, §18 line 412).
            if dependent not in closure:
                stack.append(dependent)
    return frozenset(closure)


# ===========================================================================
# core §5.2 — exact instrument / contract / account / route binding (VTG-EV-003, +Security)
# ===========================================================================


def exact_instrument_route_bound(
    decision: OrderAdmissibilityDecision | None,
    candidate_fields: InstrumentRouteFields | None,
) -> bool:
    """Whether the decision binds the candidate's exact instrument / route (§11; VTG-INV-004).

    §11 line 281: an admissible decision binds the canonical instrument identity plus **every**
    routing-relevant alias / venue listing / market segment / contract month / product /
    currency / multiplier / expiration / settlement / account / environment / broker / route.
    §27 AC-003 line 613 verbatim: "Substitute symbol alias, market segment, contract month,
    account, environment, or broker route. Every mismatch must be rejected through final
    egress." Returns ``True`` **only** when every scalar routing field of the decision's bound
    identity is concrete and **exactly equal** to the candidate's, and the routing-alias sets
    are **exactly equal** (both-ways: a missing routing field OR a spurious alias substitution
    fails, design #19 §4.7). A ``None`` decision / candidate, any ``None`` / mismatched scalar,
    or any alias-set difference is rejected. Candidate command construction is ioc-owned (§3.5);
    this predicate only checks the decision binds it exactly.

    Args:
        decision: The order admissibility decision (``None`` => ``False``).
        candidate_fields: The candidate command's instrument / route fields (``None`` =>
            ``False``).

    Returns:
        ``True`` iff the decision's bound identity exactly matches the candidate's.
    """
    if decision is None or candidate_fields is None:
        return False
    bound = decision.bound_instrument_route
    for name in _ROUTE_SCALAR_FIELDS:
        bound_value = getattr(bound, name)
        candidate_value = getattr(candidate_fields, name)
        if bound_value is None or candidate_value is None:
            return False  # missing routing field => not bound (fail-closed)
        if bound_value != candidate_value:
            return False  # substitution => rejected (§11 AC-003 line 613)
    # Alias set exact equality — both-ways (a missing alias under-counts, a spurious alias
    # substitutes; either is a mismatch, §4.7).
    return bound.routing_relevant_aliases == candidate_fields.routing_relevant_aliases


# ===========================================================================
# core §5.3 — order-shape venue-admissibility (VTG-EV-004, +Broker)
# ===========================================================================


def order_shape_admissible(
    shape: OrderShapeFields | None,
    constraints: VenueShapeConstraints | None,
) -> OrderAdmissibilityResult:
    """Whether the exact order shape is venue-admissible (§12; VTG-INV-004).

    §12 line 299: price band / tick / lot / quantity / order-type / TIF are checked **without
    permissive rounding or substitution**; §12 line 309: "Rounding that changes price,
    quantity, direction, risk, or authorized economic effect creates a new broker-request shape
    and requires a new exact decision." So a silently-rounded shape is ``INADMISSIBLE``
    (VTG-AC-004 line 617 "Silent normalization or widening must fail"). Every numeric bound is
    **injected policy content** (§8.0 — nothing hardcoded); a missing band / tick / lot / qty
    or an invalid (zero) tick / lot is ``UNKNOWN`` (never a permissive default, §8 line 245).

    This is the **venue-admissibility** judgement only (band / tick / lot violation); the
    **intent-conformance** judgement (does the command match the approved Intent) is ioc-owned
    — the same fields, a different decision (§3.5 핵심 판정 (a); §12 line 311 "Broker-side
    validation is defense in depth"). Returns ``ADMISSIBLE`` **only** when the shape passes
    every declared constraint positively; any violation is ``INADMISSIBLE``; any missing /
    invalid injected bound is ``UNKNOWN``.

    Args:
        shape: The exact order shape (``None`` => ``UNKNOWN``).
        constraints: The injected venue shape constraints (``None`` / missing bound =>
            ``UNKNOWN``).

    Returns:
        The :class:`~tos.venue.vocabulary.OrderAdmissibilityResult`.
    """
    if shape is None or constraints is None:
        return OrderAdmissibilityResult.UNKNOWN
    # A silently-rounded / normalized shape is a NEW shape — never admissible here (§12 line 309).
    if shape.silently_rounded is not False:
        return OrderAdmissibilityResult.INADMISSIBLE
    # Required injected numeric bounds must be present + valid, else UNKNOWN (fail-closed, §8.0).
    if (
        shape.price is None
        or constraints.price_min is None
        or constraints.price_max is None
        or constraints.tick_size is None
        or shape.quantity is None
        or constraints.lot_size is None
        or constraints.min_quantity is None
        or constraints.max_quantity is None
    ):
        return OrderAdmissibilityResult.UNKNOWN
    if constraints.tick_size == 0 or constraints.lot_size == 0:
        return (
            OrderAdmissibilityResult.UNKNOWN
        )  # invalid injected constraint, not a divisor
    # Required policy-declared enum sets must be non-empty (empty => nothing admitted => UNKNOWN).
    if (
        not constraints.allowed_order_types
        or not constraints.allowed_tifs
        or not constraints.allowed_sides
        or not constraints.allowed_position_effects
    ):
        return OrderAdmissibilityResult.UNKNOWN
    # Price band + tick (no permissive rounding — the injected tick divides exactly).
    if shape.price < constraints.price_min or shape.price > constraints.price_max:
        return OrderAdmissibilityResult.INADMISSIBLE
    if (shape.price - constraints.price_min) % constraints.tick_size != 0:
        return OrderAdmissibilityResult.INADMISSIBLE
    # Quantity min/max + lot (odd-lot => inadmissible).
    if (
        shape.quantity < constraints.min_quantity
        or shape.quantity > constraints.max_quantity
    ):
        return OrderAdmissibilityResult.INADMISSIBLE
    if shape.quantity % constraints.lot_size != 0:
        return OrderAdmissibilityResult.INADMISSIBLE
    # Order-type / TIF / side / position-effect membership.
    if shape.order_type not in constraints.allowed_order_types:
        return OrderAdmissibilityResult.INADMISSIBLE
    if shape.tif not in constraints.allowed_tifs:
        return OrderAdmissibilityResult.INADMISSIBLE
    if shape.side not in constraints.allowed_sides:
        return OrderAdmissibilityResult.INADMISSIBLE
    if shape.position_effect not in constraints.allowed_position_effects:
        return OrderAdmissibilityResult.INADMISSIBLE
    return OrderAdmissibilityResult.ADMISSIBLE


# ===========================================================================
# core §5.4 — exact decision binding + no union + material-change closure (VTG-EV-006, +Security)
# ===========================================================================


def decision_binding_exact(chain: BindingChain | None) -> bool:
    """Whether the decision binds every downstream stage with the exact identity (§16; VTG-INV-004).

    §16 line 363-373: the decision id/digest binds proposal / approval / intent / candidate
    command / capacity / authority / capability / commit-proof / egress with the **same**
    identity; §16 line 377: a consumer rejects a missing / mismatched / stale / wrong-scope /
    superseded / invalidated / unverifiable binding. §14 line 343: "Decisions cannot be patched,
    partially refreshed, unioned, widened, or silently recomputed." Returns ``True`` **only**
    when the chain exists, its ``decision_id`` and ``decision_digest`` are concrete, the stage
    set is **non-empty** (an empty chain is not "exact binding" — fail-closed, §4.7), and
    **every** stage binds exactly that id and digest. Any mismatch fails closed.

    Args:
        chain: The decision binding chain (``None`` / empty / any mismatch => ``False``).

    Returns:
        ``True`` iff every stage binds the exact decision identity.
    """
    if chain is None:
        return False
    if chain.decision_id is None or chain.decision_digest is None:
        return False
    if not chain.stage_bindings:
        return False  # ∅ — no bound stage is not exact binding (§4.7)
    for binding in chain.stage_bindings:
        if binding.bound_decision_id != chain.decision_id:
            return False
        if binding.bound_decision_digest != chain.decision_digest:
            return False
    return True


def no_decision_union(decision_digests: frozenset[str]) -> bool:
    """Whether the shape maps to exactly one decision (no union / widen) (§14; VTG-INV-004).

    §14 line 343 verbatim: "Decisions cannot be patched, partially refreshed, **unioned,
    widened**, or silently recomputed. Any material field change creates a new Snapshot or
    decision and repeats every affected downstream gate." An exact broker-request shape has
    **exactly one** Order Admissibility Decision — there is no path that unions multiple
    decisions into one permission. Returns ``True`` **only** when there is exactly one distinct
    decision digest; an empty set (nothing bound) and a multi-digest set (a union / widen
    attempt) both fail closed (design #19 §4.7).

    Args:
        decision_digests: The distinct decision digests bound for one exact shape.

    Returns:
        ``True`` iff exactly one decision is bound (no union / widen).
    """
    return len(decision_digests) == 1


def material_change_closure(
    dep_graph: Mapping[str, frozenset[str]],
    change_triggers: frozenset[str],
    *,
    unproven: Mapping[str, frozenset[str]] | None = None,
) -> frozenset[str]:
    """The dependencies invalidated by a material constraint change (§18 line 404-412; VTG-INV-008).

    §18 line 404-410: any material change (unscheduled closure / halt / suspension, listing /
    contract / tick / lot / band change, account / borrow / margin / settlement change,
    broker-capability degradation, source correction / discontinuity) fences the affected
    unconsumed decisions and downstream permission "before future new-risk send" (VTG-INV-008
    line 177). §18 line 412: "Invalidation SHALL reach approval, authority issuance, unconsumed
    capabilities, and every final egress ... Failure to prove complete propagation expands
    containment to the complete possibly affected scope." Realized as the union, over every
    material change trigger, of the shared :func:`_reachability_closure` — the same
    iap-/sbr-isomorphic closure discipline (design #19 §0.4d): an ``unproven`` edge is
    **expanded** (an affected dependency must not escape — the under-count fail-open; §5.8
    "Unknown materiality is material"). Each trigger is always in its own closure, so a single
    material change with no graph edges still invalidates itself. An **empty** ``change_triggers``
    yields the empty set — no change, nothing invalidated (the availability side; a valid
    decision within max age is not spuriously invalidated, §18 canary b). The real
    invalidation-to-egress latency is runtime-measured (§8.1); L1 is the closure-completeness
    discipline only.

    Args:
        dep_graph: The constraint dependency adjacency ``{node: {dependents}}``.
        change_triggers: The material change trigger nodes (empty => empty invalidation set).
        unproven: The uncertain-edge adjacency, expanded (an affected dependency must not
            escape, design #19 §4.7).

    Returns:
        The frozenset of every decision / dependency invalidated by the changes.
    """
    invalidated: set[str] = set()
    for trigger in change_triggers:
        invalidated |= _reachability_closure(dep_graph, trigger, unproven=unproven)
    return frozenset(invalidated)


# ===========================================================================
# predicate-only §6.1 — tradability conflict => UNKNOWN (VTG-EV-002, +Broker)
# ===========================================================================


def tradability_conflict_unknown(
    observations: frozenset[SourceObservation],
    resolution: PolicyResolution | None,
) -> OrderAdmissibilityResult:
    """Whether conflicting tradability observations resolve — only via policy (§10; VTG-INV-005).

    §10 line 275 verbatim: conflicting venue / broker / quote / calendar observations stay
    ``UNKNOWN`` until a policy-defined resolution — "majority or newest-arrival selection is not
    automatically authoritative." §25.2 line 531: "Market data can continue while order entry is
    halted, restricted, stale, or account-ineligible", so quote flow never proves tradability —
    a source observation is an **input, not permission**. Returns ``UNKNOWN`` when observations
    are empty (nothing proves tradability), or when they conflict with **no** policy resolution;
    only a policy-defined ``resolved_result`` yields a non-``UNKNOWN`` result. The real conflict
    resolution / broker probe is +Broker runtime (§3.5); L1 is the "conflict => UNKNOWN, majority
    forbidden, observation ↛ permission" predicate only.

    Args:
        observations: The source observations (empty => ``UNKNOWN``).
        resolution: The policy-defined resolution (``None`` / no result => ``UNKNOWN``).

    Returns:
        The policy-resolved :class:`~tos.venue.vocabulary.OrderAdmissibilityResult`, else
        ``UNKNOWN``.
    """
    if not observations:
        return OrderAdmissibilityResult.UNKNOWN
    states = {obs.state for obs in observations}
    if len(states) > 1:
        # Conflict — only a policy-defined resolution decides (majority/newest not automatic).
        if resolution is not None and resolution.resolved_result is not None:
            return resolution.resolved_result
        return OrderAdmissibilityResult.UNKNOWN
    # A single consistent observation is still only an input — a policy resolution may elevate
    # it, otherwise it remains UNKNOWN (observation ↛ permission, §10 line 275).
    if resolution is not None and resolution.resolved_result is not None:
        return resolution.resolved_result
    return OrderAdmissibilityResult.UNKNOWN


# ===========================================================================
# predicate-only §6.2 — account/margin/borrow conservatism (VTG-EV-005, +Broker)
# ===========================================================================


def account_constraint_conservative(
    facts: AccountMarginFacts | None,
    prior: AccountMarginFacts | None,
) -> bool:
    """Whether account / margin / borrow headroom is conservatively established (§13; VTG-INV-005).

    §13 line 319 verbatim: "Margin, buying power, borrow availability, or account eligibility is
    **not inferred** from a stale balance, a previous successful order, or the absence of a
    broker error." Returns ``True`` (**conservative — headroom positively established**) **only**
    when the facts exist, are positively ``fresh`` **and** ``corroborated``, and **none** of the
    forbidden optimistic bases (stale balance / prior order / absence-of-error) is used. Any
    inference basis positively ``True``, or a non-positive ``fresh`` / ``corroborated``, fails
    closed. ``prior`` is accepted and **discarded** — a previous fact set never manufactures
    current headroom (§13 line 319; the accept-and-discard seal). Per-field confidence is
    recon-owned and post-trade finality is ADR-002-030 (§3.5; broker-agnostic — no concrete
    broker named); L1 is the "stale ↛ headroom" conservatism predicate only.

    Args:
        facts: The current account / margin facts (``None`` => ``False``).
        prior: The prior facts (accepted and discarded — never a headroom basis).

    Returns:
        ``True`` iff headroom rests on fresh, corroborated, non-inferred facts.
    """
    del prior  # §13 line 319 — a prior fact set never manufactures current headroom.
    if facts is None:
        return False
    if facts.inferred_from_stale_balance is True:
        return False
    if facts.inferred_from_prior_order is True:
        return False
    if facts.inferred_from_absence_of_error is True:
        return False
    if facts.fresh is not True:
        return False
    return facts.corroborated is True


# ===========================================================================
# predicate-only §6.3 — active final-egress currentness (VTG-EV-007, +Security)
# ===========================================================================


def egress_currentness_active(
    current_actively_established: bool | None,
    request_generation: int | None,
    current_generation: int | None,
) -> bool:
    """Whether final-egress currentness is actively established (§17; VTG-INV-010).

    §17 line 394 verbatim: "Cached permissive state, TTL, schedule, heartbeat, service health,
    broker connectivity, last-known generation, eventual consistency, or absence of a halt /
    restriction event SHALL NOT establish currentness." So currentness must be **actively**
    established (``current_actively_established is True``); a cache / heartbeat / absence
    (``None`` / ``False``) fails closed. Returns ``True`` (**admit**) **only** when currentness
    is actively established **and** both generations are verifiable **and** the request
    references **exactly** the current Constraint Generation — an **older** generation is stale
    and a **newer** one is an unrecognized future generation (the §4.3 coordinate non-collapse:
    substituting another coordinate's value never matches). The active-currentness protocol is
    ADR-002-024 runtime (+Security, §6.3); L1 is the order-comparison + active-establish
    predicate only (the monotonic order is REUSED from ``tos.ordering`` — see
    :func:`~tos.venue.state.constraint_generation_monotone`).

    Args:
        current_actively_established: Whether currentness is actively established (``None`` /
            ``False`` => not current).
        request_generation: The request's referenced generation (``None`` => not current).
        current_generation: The current Constraint Generation (``None`` => not current).

    Returns:
        ``True`` iff egress currentness is actively established for exactly this generation.
    """
    if current_actively_established is not True:
        return False
    if request_generation is None or current_generation is None:
        return False
    return request_generation == current_generation


def stale_decision_rejected_at_egress(
    current_actively_established: bool | None,
    request_generation: int | None,
    current_generation: int | None,
) -> bool:
    """Whether a new-risk egress request must be rejected on currentness grounds (§17; VTG-INV-010).

    The reject-framed complement of :func:`egress_currentness_active`: §17 line 383-394 requires
    final egress to reject any new-risk request when currentness cannot be **actively**
    established, either generation is unverifiable, or the request references a
    non-current generation (older = stale; newer = unrecognized future gen, §4.3 non-collapse).
    §17 line 396: a race between final currentness and the first broker byte that cannot be
    proven leaves the effect potentially-live (blind retry forbidden — runtime, +Security).
    Returns ``True`` (**reject**) whenever currentness is not actively established for exactly
    the current generation.

    Args:
        current_actively_established: Whether currentness is actively established.
        request_generation: The request's referenced generation.
        current_generation: The current Constraint Generation.

    Returns:
        ``True`` iff the request must be rejected at egress.
    """
    return not egress_currentness_active(
        current_actively_established, request_generation, current_generation
    )


# ===========================================================================
# predicate-only §6.4 — exit not assumed admissible (VTG-EV-008, +Broker)
# ===========================================================================


def exit_not_assumed_admissible(
    action: ActionClass,
    tradability: TradabilityState,
) -> bool:
    """Whether an exit-class action's admissibility is positively proven, not assumed (§11/§19; VTG-INV-003).

    VTG-INV-003 line 157 verbatim: "Exit, reduce-only, cancel, replacement, and protective
    actions are independently constrained and may be ``INADMISSIBLE`` or ``UNKNOWN``." §11 line
    285 / §25.4 line 539: reduce-only / exit actions "can be unsupported, reverse exposure,
    cross zero, violate account/venue rules, or fail while protection is removed", so an exit is
    **never** assumed executable from an entry's admissibility. Returns ``True`` (**admissible —
    positively proven**) **only** when ``action`` is an exit-class action (decrease / close /
    reversal / cancel / amend / replace / reduce-only / protective / emergency) **and** its
    per-action ``tradability`` is positively :attr:`~tos.venue.vocabulary.TradabilityState.TRADABLE`
    (explicit identity — never ``if tradability:``). A non-exit action returns ``False`` (this
    predicate clears only exit-class actions), and any non-``TRADABLE`` tradability fails closed.
    Final Quantity Proof / broker semantics are ADR-002-004 (+Broker, §3.5); no blind retry
    (§25.8 line 555). L1 is the "exit ↛ assumed-admissible" predicate only.

    Args:
        action: The exit-class action under evaluation (non-exit => ``False``).
        tradability: The exact per-action tradability (non-``TRADABLE`` => ``False``).

    Returns:
        ``True`` iff an exit-class action's admissibility is positively proven.
    """
    if action not in _EXIT_ACTION_CLASSES:
        return False  # not an exit-class action — this predicate does not clear it
    return tradability is TradabilityState.TRADABLE


# ===========================================================================
# predicate-only §6.5 — protective label grants no bypass (VTG-EV-009, +Broker)
# ===========================================================================


def protective_label_no_bypass(
    label_is_protective: bool | None,
    exact_admissibility: OrderAdmissibilityResult,
    separate_protective_authority: bool | None,
    intermediate_effects_capacity_covered: bool | None,
) -> bool:
    """Whether a protective action may proceed — never on a label alone (§19; VTG-INV-007).

    VTG-INV-007 line 173-175 verbatim: "Protective or containment use requires exact current
    admissibility, separate protective classification and authority, and conservative capacity
    for every credible intermediate effect." §1 line 29 / §19 line 426: "only a separately
    authorized exact action whose current restrictive-path constraints are positively proven may
    proceed." So a protective label **never** bypasses a constraint. Returns ``True`` (**the
    RESTRICTED_PROTECTIVE_ONLY path may proceed**) **only** when all three hold: (i) the action
    is positively labelled protective (``label_is_protective is True``); (ii) its exact current
    admissibility is positively :attr:`~tos.venue.vocabulary.OrderAdmissibilityResult.ADMISSIBLE`
    or :attr:`~tos.venue.vocabulary.OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY`
    (explicit identity — never ``if exact_admissibility:``, which would read the truthy denial /
    protective-only strings as permission, §0.4d); (iii) a **separate** protective authority is
    positively present; and (iv) every credible intermediate / reversal effect is
    capacity-covered ("Priority is not reserved protective capacity", §19 line 426). Any missing
    condition fails closed. Classification / replacement is protective-owned and capacity is
    rcl-owned (§3.5); L1 is the "label ↛ bypass, 3-condition" predicate only.

    Args:
        label_is_protective: Whether the action is positively classified protective (``None`` /
            ``False`` => ``False``).
        exact_admissibility: The action's exact current admissibility result.
        separate_protective_authority: Whether a separate protective authority is present
            (``None`` / ``False`` => ``False``).
        intermediate_effects_capacity_covered: Whether every credible intermediate effect is
            capacity-covered (``None`` / ``False`` => ``False``).

    Returns:
        ``True`` iff the protective action may proceed on all four positive conditions.
    """
    if label_is_protective is not True:
        return False
    if exact_admissibility not in (
        OrderAdmissibilityResult.ADMISSIBLE,
        OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY,
    ):
        return False
    if separate_protective_authority is not True:
        return False
    return intermediate_effects_capacity_covered is True


# ===========================================================================
# predicate-only §6.6 — common-mode + unknown continuity (VTG-EV-010, +Security)
# ===========================================================================


def common_mode_reduces_scope(
    shared_dependencies: frozenset[str],
    independent_corroboration: bool | None,
) -> bool:
    """Whether a common-mode dependency reduces the corroboration scope (§15; VTG-INV-005/006).

    §15 line 353 verbatim: "Two services that consume the same corrupted dependency do not
    provide independent corroboration." A shared venue feed / broker endpoint / calendar /
    mapping / margin library / cache / parser / credential / network / region / deployment /
    rule-engine is common-mode, so independence is not established and scope must reduce
    (SAFE-034, §15 line 355). Returns ``True`` (**scope must reduce — independence not
    established**) whenever there are any shared dependencies, or when independent corroboration
    is not positively established (``independent_corroboration is not True`` — an absent
    corroboration reduces scope, fail-closed). Returns ``False`` (**no reduction**) **only**
    when there are no shared dependencies **and** independence is positively corroborated. The
    real failure-domain / security boundary is +Security runtime (§27 q10, §3.5); L1 is the
    "shared ↛ independent" predicate only.

    Args:
        shared_dependencies: The shared (common-mode) dependencies (non-empty => reduce).
        independent_corroboration: Whether independence is positively corroborated (``None`` /
            ``False`` => reduce).

    Returns:
        ``True`` iff the corroboration scope must be reduced.
    """
    if shared_dependencies:
        return True
    return independent_corroboration is not True


def unknown_continuity_invalidates(continuity: SourceContinuity | None) -> bool:
    """Whether an unknown / unverifiable source continuity invalidates future decisions (§9; VTG-INV-005).

    §9 line 263 verbatim: restart / reconnect / endpoint-or-credential substitution / sequence
    reset / rollback / failover / missed-page / stale-cache / unverifiable continuity requires a
    new continuity identity or an explicit gap; **unknown continuity invalidates** affected
    future decisions. Returns ``True`` (**invalidate — continuity is not positively
    established**) when the continuity is ``None``, has no identity, is not positively
    ``verifiable``, or any gap flag (restart / reconnect / sequence-reset / rollback /
    failover) is positively ``True``. Returns ``False`` (**continuity holds**) **only** when a
    concrete continuity identity is positively verifiable with no gap. The real failure-domain /
    security boundary is +Security runtime (§3.5); L1 is the "unknown continuity => invalidate"
    predicate only.

    Args:
        continuity: The source continuity facts (``None`` => invalidate).

    Returns:
        ``True`` iff the continuity is unknown / unverifiable and must invalidate.
    """
    if continuity is None:
        return True
    if continuity.continuity_id is None:
        return True
    if continuity.verifiable is not True:
        return True
    return (
        continuity.restarted is True
        or continuity.reconnected is True
        or continuity.sequence_reset is True
        or continuity.rolled_back is True
        or continuity.failed_over is True
    )


# ===========================================================================
# predicate-only §6.7 — gate authority separation (VTG-EV-011, +Security, broker-cap N/A)
# ===========================================================================


def gate_authority_separated(
    effect: VenueGateAuthorityEffect | None,
    holds_live_credential: bool | None,
) -> bool:
    """Whether the venue gate grants no authority and holds no live credential (§7; VTG-INV-011).

    VTG-INV-011 line 189-191 verbatim: "Constraint evaluation cannot approve, mutate capacity,
    issue authority, classify protection, transmit, clear HALT, or re-arm." §7 line 223: "The
    Venue Constraint Gate SHALL NOT hold a usable live broker credential, signer, session, or
    broker-order route merely because it queries broker or venue constraints." Returns ``True``
    (**authority is separated**) **only** when the effect exists, no live credential is held
    (``holds_live_credential is False`` — a ``True`` / ``None`` rejects), and every authority
    flag is ``False``. Because :class:`~tos.venue._base.VenueGateAuthorityEffect` is
    unconstructable with any ``True`` flag, a *validated* effect always separates authority —
    this is the defining predicate that states it, and the defence-in-depth re-check for a block
    that reached the consumer via an unvalidated ``model_construct`` path. The real SoD /
    bypass-path / common-effective-control proof is +Security runtime (§7 line 220, §3.5).

    Args:
        effect: The venue-gate authority effect (``None`` => ``False``).
        holds_live_credential: Whether a live credential is held (``True`` / ``None`` =>
            ``False``).

    Returns:
        ``True`` iff the gate grants no authority and holds no live credential.
    """
    if effect is None:
        return False
    if holds_live_credential is not False:
        return False
    return not (
        effect.approves
        or effect.mutates_capacity
        or effect.issues_authority
        or effect.classifies_protection
        or effect.transmits
        or effect.clears_halt
        or effect.rearms
    )


# ===========================================================================
# predicate-only §6.8 — reopen revives nothing (VTG-EV-012, +Security)
# ===========================================================================


def reopen_revives_nothing(
    *,
    venue_reopened: bool | None = None,
    halt_released: bool | None = None,
    reconnected: bool | None = None,
    restarted: bool | None = None,
    failed_over: bool | None = None,
    clock_recovered: bool | None = None,
    constraint_service_recovered: bool | None = None,
    prior_decision: object | None = None,
) -> bool:
    """Whether a venue reopen / recovery revives a prior decision — never (§22; VTG-INV-013).

    VTG-INV-013 line 197-199 verbatim: "Venue reopen, halt release, account restoration,
    reconnect, restart, failover, clock recovery, or constraint-service recovery cannot revive a
    previous decision or authority." §22 line 471: "A fresh decision and the complete governed
    authorization chain are required. No automatic re-arm is permitted." Realized as an
    **unconditional** ``True`` with every revival input **accepted and discarded** (isomorphic
    to the sbr ``recovery_completion_revives_nothing`` ``predicates.py:484`` / authority
    ``recovery_generation_revives_nothing`` replica pattern, design #19 §0.4d): no revival input
    can influence the answer because the answer never reads them — the model provides **no**
    reopen → prior-decision-restoration operation at all, and this predicate documents and fixes
    that absence. A lawful re-arm always requires a fresh decision plus a governed ADR-002-007/015
    re-arm workflow (§22 handoff), never a revival of the old one; that workflow is runtime
    (§3.5).

    Returns:
        ``True`` — nothing revives a prior decision (unconditionally).
    """
    del venue_reopened, halt_released, reconnected, restarted
    del failed_over, clock_recovered, constraint_service_recovered, prior_decision
    return True
