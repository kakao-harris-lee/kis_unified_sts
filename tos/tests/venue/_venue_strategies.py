"""Shared valid-artifact builders + strategies for the venue property tests (design #19 §7)."""

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
    PriceBandTick,
    SourceContinuity,
    StageBinding,
    TradabilityState,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
)

MEASURED_KRX_PRICE_BAND_ROW = PriceBandTick(
    band_min=200_000, band_max=300_000, tick=500
)
MEASURED_KRX_PRICE = 232_500

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")
TRIBOOL = st.sampled_from([True, False, None])
ADMISSIBILITY_RESULTS = st.sampled_from(list(OrderAdmissibilityResult))
TRADABILITY_STATES = st.sampled_from(list(TradabilityState))
ACTION_CLASSES = st.sampled_from(list(ActionClass))

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


def price_band_table_constraints() -> VenueShapeConstraints:
    """Shape constraints with a declared price-band tick table (kernel round #4 K-1)."""
    return VenueShapeConstraints(
        price_min=100_000,
        price_max=500_000,
        tick_size=7,
        price_band_ticks=(MEASURED_KRX_PRICE_BAND_ROW,),
        lot_size=10,
        min_quantity=10,
        max_quantity=1_000_000,
        allowed_order_types=frozenset({"LIMIT", "MARKET"}),
        allowed_tifs=frozenset({"DAY", "IOC"}),
        allowed_sides=frozenset({"BUY", "SELL"}),
        allowed_position_effects=frozenset({"OPEN", "CLOSE"}),
    )


def price_band_table_shape() -> OrderShapeFields:
    """A shape priced at the one measured KRX price-band datapoint (232,500원, tick 500)."""
    return OrderShapeFields(
        price=MEASURED_KRX_PRICE,
        quantity=20,
        order_type="LIMIT",
        tif="DAY",
        side="BUY",
        position_effect="OPEN",
        silently_rounded=False,
    )


def clean_shape() -> OrderShapeFields:
    """A genuinely venue-admissible order shape (inside every band / tick / lot / enum set)."""
    return OrderShapeFields(
        price=105,
        quantity=20,
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
