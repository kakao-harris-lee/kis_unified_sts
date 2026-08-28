"""are temporal / lifecycle predicates — concurrency, currentness, non-revival (§6.3/§6.4/§6.6).

The decision rules that concern **state over time**: non-cyclic forward-only binding and
concurrency (§6.3 / §18), currentness / invalidation (§6.4 / §17), and non-revival + economic
continuity (§6.6 / §20 / §21). These are the predicate-only ARE-EV-008/009/012 substrate — the
L1-decidable rules; the RCL serialization / generation-fence enforcement, the active
final-egress currentness enforcement, and the Recovery Barrier / governed re-arm workflow are
all EV-L2/L3 runtime (design #13 §6; §28).

The append-only Aggregate Risk Generation / decision / snapshot order is **not** re-authored:
it REUSES ``tos.ordering`` (``Ordering`` / ``OrderingEvent`` / ``compare_order``, which depends
only on ``tos.canonical``) — design #13 §3.2. A wall clock never orders (§17 line 440 / §18
line 454; are reads no clock).

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.canonical`` (via the records)
only; no ``shared.*``, no other sibling ``tos.*`` (design #13 §0.3).
"""

from __future__ import annotations

from tos.are.records import AggregateRiskDecision
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "non_cyclic_binding",
    "concurrent_not_reservation",
    "decision_generation_monotone",
    "currentness_invalidation",
    "non_revival_holds",
    "economic_effect_persists",
]

#: Reservation-binding coordinates a forward-only decision must NOT carry (§16 line 413):
#: rcl charges ``bound_reservation_*`` post-commit, so their presence on a decision would make
#: the pipeline cyclic (design #13 §5.6). A structural, not numeric, contract.
_FORWARD_ONLY_FORBIDDEN_FIELDS: frozenset[str] = frozenset(
    {
        "bound_reservation_revision",
        "bound_reservation_digest",
        "bound_generation",
        "reservation_id",
    }
)


def non_cyclic_binding(decision: AggregateRiskDecision) -> bool:
    """Whether the decision is forward-only and binds no future commitment (§6.3 / §4.6 / §16).

    ARE-INV-002 line 158 / §16 line 413: an Aggregate Risk Decision "does not bind a future
    Capacity Commitment identity" — it produces only forward-only content
    (``decision_id`` / ``decision_generation`` / ``canonical_decision_digest``); rcl charges the
    reservation coordinate post-commit (the non-cyclic code realization, design #13 §5.6).
    ``True`` **only** when the decision model carries **none** of the reservation-binding fields
    (a structural check — a subclass that reintroduces one is a cyclic-binding canary and fails).

    Args:
        decision: The aggregate risk decision.

    Returns:
        ``True`` iff the decision carries no forward reservation-binding coordinate.
    """
    return _FORWARD_ONLY_FORBIDDEN_FIELDS.isdisjoint(type(decision).model_fields)


def concurrent_not_reservation(
    *,
    headroom_observed: bool | None,
    rcl_serialization_committed: bool | None,
) -> bool:
    """Whether an exclusive commitment exists (only RCL serialization creates one) (§6.3 / §18).

    §18 line 448 verbatim: "Concurrent evaluations may observe the same headroom but cannot
    reserve it. Only RCL serialization creates exclusive commitment." ``True`` **only** when
    ``rcl_serialization_committed is True`` — merely observing headroom
    (``headroom_observed``) is **never** a reservation, and a blind retry against observed
    headroom fails closed (§17 line 442). The ``headroom_observed`` argument is accepted to make
    the "observation != reservation" canary explicit; it never grants exclusivity.

    Args:
        headroom_observed: Whether headroom was observed (never a reservation).
        rcl_serialization_committed: Whether RCL serialization committed the reservation.

    Returns:
        ``True`` iff an exclusive commitment exists via RCL serialization.
    """
    del headroom_observed  # observation is never a reservation (§18 line 448)
    return rcl_serialization_committed is True


def decision_generation_monotone(earlier: OrderingEvent, later: OrderingEvent) -> bool:
    """Whether ``earlier`` strictly precedes ``later`` in append-only order (§3.2 / §5.2).

    REUSES ``tos.ordering.compare_order`` (no re-authored order) to check the monotonic
    Aggregate Risk Generation order (§5.2 line 120 "A monotonic generation"). ``True`` **only**
    when the order is unambiguously ``BEFORE``; an ``AMBIGUOUS`` / ``AFTER`` pair fails closed (a
    wall clock never orders, §17 line 440).

    Args:
        earlier: The earlier ordering event.
        later: The later ordering event.

    Returns:
        ``True`` iff ``earlier`` provably precedes ``later``.
    """
    return compare_order(earlier, later) is Ordering.BEFORE


def currentness_invalidation(
    *,
    material_change_present: bool | None,
    cache_ttl_or_heartbeat_only: bool | None,
) -> bool:
    """Whether an unconsumed decision must be invalidated (§6.4 / §17).

    §17: a material change (position / order / fill / commitment / external / effect / command /
    approval / venue / context / broker / price / vol / liquidity / margin / envelope / policy /
    scenario / model / schema / source / recovery / epoch / security) invalidates every affected
    unconsumed decision. §17 line 440: a cached GRANT / TTL / heartbeat / health /
    last-known-generation / eventual-consistency / absence-of-invalidation is **not** a
    currentness proof. Returns ``True`` (must invalidate) when a material change is present or
    unknown (fail-closed), or when currentness rests only on a cache / TTL / heartbeat; ``False``
    (stays current) **only** when there is positively no material change and currentness does not
    rest on a cache alone.

    Args:
        material_change_present: Whether a material change occurred (``True`` / ``None`` =>
            invalidate).
        cache_ttl_or_heartbeat_only: Whether currentness rests only on a cache / TTL / heartbeat
            (``True`` => invalidate; not a currentness proof).

    Returns:
        ``True`` iff the decision must be invalidated.
    """
    if material_change_present is not False:
        return True
    return cache_ttl_or_heartbeat_only is True


def non_revival_holds() -> bool:
    """Whether nothing revives a prior decision / grant / authority / live scope (§6.6 / §21).

    ARE-INV-013 / §21 line 488-500 verbatim: no restart, restore, failover, recovery,
    reconciliation, replay, or improved input revives a prior decision, grant, authority, or
    live scope; "No automatic re-arm is permitted" (§1 line 41 / §21 line 500). Realized as an
    **unconditional** ``True`` (isomorphic to spg ``expiry_revives_nothing`` / rcl
    ``recovery_generation_revives_nothing``): a lawful re-arm always requires a fresh artifact +
    governed decision, never a revival of the old one.

    Returns:
        ``True`` — nothing revives a prior decision (unconditionally).
    """
    return True


def economic_effect_persists(*, terminal_release_proven: bool | None) -> bool:
    """Whether the committed economic effect persists (§6.6 / §20 / ARE-INV-011 line 193).

    §20 line 480 / ARE-INV-011 line 193: a missing ACK, timeout, cancel, withdrawal,
    decision-expiry, policy-expiry, or evaluator-failure does **not** release committed /
    potentially-consumed capacity. Reconciliation may request a **defined** RCL transition but
    cannot rewrite a decision, erase an UNKNOWN, or free capacity (§20 line 482). Returns
    ``True`` (the effect persists) unless a terminal release is **positively proven** (a defined
    RCL transition); a ``None`` / ``False`` (missing ACK / expiry / conflicting evidence) fails
    closed to persistence.

    Args:
        terminal_release_proven: Whether a defined RCL transition positively proves terminal
            release (``None`` / ``False`` => the effect persists).

    Returns:
        ``True`` iff the economic effect still persists.
    """
    return terminal_release_proven is not True
