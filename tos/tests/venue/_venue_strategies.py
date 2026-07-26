"""Shared valid-artifact builders + strategies for the venue property tests (design #19 §7).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #19 §0.3). The builders
enforce the §7 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must be
*genuinely* admissible, never a permissive shortcut):

* a **clean** policy declares a non-empty admitting-phase set for the exact action, a non-empty
  required-constraint-class set, and genuine injected shape constraints;
* a **clean** instrument route + candidate match on every scalar field and alias set;
* a **clean** order shape is genuinely inside every injected band / tick / lot / enum set and
  positively not silently-rounded;
* a **clean** binding chain binds the exact decision identity on every stage;
* the **∅ strategies** deliberately generate empty sets / graphs so the ∅-void guards are
  actually exercised (the #10 lesson — a strategy that never emits ∅ leaves the ∅ branch
  untested).

Every band / tick / lot value is an explicit fixture int — nothing here is a *policy* number;
the real venue bounds are Verification-Profile injected and all null / TBD in Phase 1 (design
#19 §8.1). The reserved ``"TBD"`` placeholder is excluded from required-field text.
"""

from __future__ import annotations

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.venue import (
    AccountMarginFacts,
    ActionClass,
    ActionPhaseAdmission,
    ActionTradability,
    BindingChain,
    ConstraintClass,
    ConstraintDependencyClosure,
    InstrumentRouteFields,
    OrderAdmissibilityDecision,
    OrderAdmissibilityResult,
    OrderShapeFields,
    SourceContinuity,
    StageBinding,
    TradabilityState,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
)

#: The injected provisional canonicalizer (REUSE, design #19 §3.1 — no new scheme).
SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved ``"TBD"``).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")
#: Injected ``bool | None`` flag (fail-closed on ``None`` / ``False``).
TRIBOOL = st.sampled_from([True, False, None])
#: The four admissibility results.
ADMISSIBILITY_RESULTS = st.sampled_from(list(OrderAdmissibilityResult))
#: The tradability states.
TRADABILITY_STATES = st.sampled_from(list(TradabilityState))
#: The closed action taxonomy.
ACTION_CLASSES = st.sampled_from(list(ActionClass))

#: A representative session-phase-token universe (§5.5 line 127 — policy-defined tokens).
PHASE_TOKENS: frozenset[str] = frozenset(
    {
        "closed",
        "pre_open",
        "opening_auction",
        "continuous_trading",
        "volatility_interruption",
        "halt",
        "reopening_auction",
        "closing_auction",
        "post_close",
        "after_hours",
    }
)


# ---------------------------------------------------------------------------
# Clean builders (genuinely admissible — the #8 lesson)
# ---------------------------------------------------------------------------


def clean_instrument_route() -> InstrumentRouteFields:
    """A fully-concrete instrument / route binding (every scalar + alias set present)."""
    return InstrumentRouteFields(
        canonical_instrument_id="INST-1",
        venue_listing="VEN-1",
        market_segment="SEG-1",
        contract_month="2026-09",
        product_type="FUT",
        currency="KRW",
        multiplier="1",
        expiration="2026-09-14",
        settlement_method="CASH",
        account_mapping="ACCT-1",
        environment="paper",
        broker="BRK-1",
        route="ROUTE-1",
        routing_relevant_aliases=frozenset({"ALIAS-A", "ALIAS-B"}),
    )


def clean_shape_constraints() -> VenueShapeConstraints:
    """Genuine injected venue shape constraints (all bounds concrete — fixture ints, §8.1)."""
    return VenueShapeConstraints(
        price_min=100,
        price_max=200,
        tick_size=5,
        lot_size=10,
        min_quantity=10,
        max_quantity=100,
        allowed_order_types=frozenset({"LIMIT", "MARKET"}),
        allowed_tifs=frozenset({"DAY", "IOC"}),
        allowed_sides=frozenset({"BUY", "SELL"}),
        allowed_position_effects=frozenset({"OPEN", "CLOSE"}),
    )


def clean_shape() -> OrderShapeFields:
    """A genuinely venue-admissible order shape (inside every band / tick / lot / enum set)."""
    return OrderShapeFields(
        price=105,  # 100 + 1 tick
        quantity=20,  # 2 lots, within [10, 100]
        order_type="LIMIT",
        tif="DAY",
        side="BUY",
        position_effect="OPEN",
        silently_rounded=False,
    )


def clean_policy(
    *,
    action: ActionClass = ActionClass.NEW_LONG,
    admitting_phases: frozenset[str] = frozenset({"continuous_trading"}),
) -> VenueConstraintPolicy:
    """A policy declaring a non-empty admitting-phase set + required constraint classes (§5.1)."""
    return VenueConstraintPolicy.issue(
        scheme=SCHEME,
        policy_id="venue-policy-1",
        policy_generation=3,
        scope="paper/BRK-1/ACCT-1",
        admitting_phase_rules=(
            ActionPhaseAdmission(action=action, admitting_phases=admitting_phases),
        ),
        required_constraint_classes=frozenset(
            {ConstraintClass.SESSION_PHASE, ConstraintClass.PRICE_TICK_LOT_QUANTITY}
        ),
        shape_constraints=clean_shape_constraints(),
        dependency_closure=ConstraintDependencyClosure(),
    )


def clean_snapshot(
    *,
    observed_session_phase: str = "continuous_trading",
    action: ActionClass = ActionClass.NEW_LONG,
    state: TradabilityState = TradabilityState.TRADABLE,
) -> VenueConstraintSnapshot:
    """A digest-verified snapshot (id ⊥ digest) with a per-action tradability entry."""
    return VenueConstraintSnapshot.issue(
        scheme=SCHEME,
        snapshot_id="venue-snap-1",
        constraint_generation=4,
        policy_id="venue-policy-1",
        policy_generation=3,
        policy_digest="venue-policy-digest",
        observed_session_phase=observed_session_phase,
        action_tradability=(ActionTradability(action=action, state=state),),
        critical_input_snapshot_digest="cii-digest",
        source_continuity_id="cont-1",
    )


def clean_decision(
    *,
    result: OrderAdmissibilityResult = OrderAdmissibilityResult.ADMISSIBLE,
    decision_id: str = "venue-dec-1",
    route: InstrumentRouteFields | None = None,
    action: ActionClass = ActionClass.NEW_LONG,
) -> OrderAdmissibilityDecision:
    """A digest-verified order admissibility decision (id ⊥ digest, all-false authority)."""
    return OrderAdmissibilityDecision.issue(
        scheme=SCHEME,
        decision_id=decision_id,
        decision_generation=5,
        constraint_generation=4,
        policy_id="venue-policy-1",
        policy_generation=3,
        policy_digest="venue-policy-digest",
        snapshot_id="venue-snap-1",
        snapshot_digest="venue-snap-digest",
        candidate_command_id="ioc-cmd-1",
        candidate_command_digest="ioc-cmd-digest",
        broker_capability_profile_version="bc-v1",
        broker_capability_profile_digest="bc-digest",
        bound_instrument_route=route if route is not None else clean_instrument_route(),
        action_class=action,
        observed_session_phase="continuous_trading",
        result=result,
    )


def clean_binding_chain(
    *,
    decision_id: str = "venue-dec-1",
    decision_digest: str = "venue-dec-digest",
) -> BindingChain:
    """A binding chain that binds the exact decision identity on every stage (§5.4 positive)."""
    return BindingChain(
        decision_id=decision_id,
        decision_digest=decision_digest,
        stage_bindings=(
            StageBinding(
                stage="approval",
                bound_decision_id=decision_id,
                bound_decision_digest=decision_digest,
            ),
            StageBinding(
                stage="egress",
                bound_decision_id=decision_id,
                bound_decision_digest=decision_digest,
            ),
        ),
    )


def clean_account_facts() -> AccountMarginFacts:
    """Fresh, corroborated, non-inferred account/margin facts (§6.2 positive side)."""
    return AccountMarginFacts(
        fresh=True,
        corroborated=True,
        inferred_from_stale_balance=False,
        inferred_from_prior_order=False,
        inferred_from_absence_of_error=False,
    )


def clean_continuity() -> SourceContinuity:
    """A verifiable source continuity with no gap (§6.6 positive side)."""
    return SourceContinuity(
        continuity_id="cont-1",
        verifiable=True,
        restarted=False,
        reconnected=False,
        sequence_reset=False,
        rolled_back=False,
        failed_over=False,
    )


# ---------------------------------------------------------------------------
# Hypothesis strategies (∅ deliberately reachable — the #10 lesson)
# ---------------------------------------------------------------------------


@st.composite
def graph_and_trigger(
    draw: st.DrawFn,
) -> tuple[dict[str, frozenset[str]], str]:
    """A random dependency graph + a trigger node drawn from it (∅ graph reachable)."""
    nodes = draw(
        st.lists(st.text(min_size=1, max_size=3), min_size=1, max_size=6, unique=True)
    )
    graph: dict[str, frozenset[str]] = {}
    for node in nodes:
        deps = draw(st.sets(st.sampled_from(nodes), max_size=len(nodes)))
        graph[node] = frozenset(deps)
    trigger = draw(st.sampled_from(nodes))
    return graph, trigger
