"""ioc temporal / lifecycle predicates — non-revival, economic continuity, generation fence (§6.6/§5.7).

The decision rules that concern **state over time**: non-revival (§6.6 / §21), economic-effect
continuity (§6.6 / §18 / §20), and the Construction-Generation fence (§5.7 / §3.2). These are the
predicate-only IOC-EV-012 substrate — the L1-decidable rules; the Recovery Barrier (ADR-002-017),
the governed re-arm workflow, and the active generation-fence enforcement are all EV-L2/L3 runtime
(design #14 §6.6; §28).

The append-only Construction-Generation order is **not** re-authored: it REUSES ``tos.ordering``
(``Ordering`` / ``OrderingEvent`` / ``compare_order``, which depends only on ``tos.canonical``) —
design #14 §3.2. A wall clock never orders (§9 line 268 / §17 line 459; ioc reads no clock).

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` only; no ``shared.*``, no other sibling
``tos.*`` (design #14 §0.3).
"""

from __future__ import annotations

from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "recovery_revives_nothing",
    "economic_effect_outlives",
    "construction_generation_fences",
]


def recovery_revives_nothing() -> bool:
    """Whether nothing revives a prior proof / capability / command permission / live scope (§6.6 / §21).

    IOC-INV-013 / §21 line 515 verbatim: "Compiler, serializer, SDK, cache, signer, route, or
    service recovery cannot revive a prior proof, capability, command permission, or live scope."
    Identical recompilation, replay equivalence, passing regression tests, broker reconnect, or a
    cache restore "cannot revive an old proof or authority" and "No automatic re-arm is
    permitted" (§21 line 515 / §1 line 41). Realized as an **unconditional** ``True`` (isomorphic
    to are ``non_revival_holds`` / spg ``expiry_revives_nothing`` / rcl
    ``recovery_generation_revives_nothing``): a lawful re-arm always requires a fresh artifact +
    governed decision, never a revival of the old one.

    Returns:
        ``True`` — nothing revives a prior proof / authority (unconditionally).
    """
    return True


def economic_effect_outlives(*, terminal_release_proven: bool | None) -> bool:
    """Whether the committed economic effect outlives artifact expiry (§6.6 / §18 / IOC-INV-012).

    IOC-INV-012 line 201 verbatim: intent / policy / command / proof / capability expiry or
    invalidation "never expires orders, attempts, fills, exposure, UNKNOWN, or capacity
    commitments already capable of effect". A newly ``NON_CONFORMANT`` / invalidated proof cannot
    retroactively prove a broker rejection or a zero quantity (§18 line 475). Returns ``True``
    (the effect outlives the expiry) unless a terminal release is **positively proven** (a defined
    RCL transition); a ``None`` / ``False`` (missing ACK / expiry / conflicting evidence) fails
    closed to persistence.

    Args:
        terminal_release_proven: Whether a defined RCL transition positively proves terminal
            release (``None`` / ``False`` => the effect outlives).

    Returns:
        ``True`` iff the committed economic effect still outlives the expiry.
    """
    return terminal_release_proven is not True


def construction_generation_fences(older: OrderingEvent, newer: OrderingEvent) -> bool:
    """Whether a newer restrictive Construction Generation fences an older one (§5.7 / §3.2).

    §5.7 line 141 verbatim: "A monotonic restrictive generation ... A newer restrictive
    generation fences older unconsumed proofs." REUSES ``tos.ordering.compare_order`` (no
    re-authored order) to check that ``older`` provably precedes ``newer`` in the append-only
    Construction-Generation order. ``True`` **only** when the order is unambiguously ``BEFORE``;
    an ``AMBIGUOUS`` / ``AFTER`` pair fails closed (a wall clock never orders, §9 line 268). The
    active fence **enforcement** (rejecting a proof issued under an older generation at egress) is
    runtime (§3.2) — this is the pure order-comparison substrate only.

    Args:
        older: The older Construction-Generation ordering event.
        newer: The newer Construction-Generation ordering event.

    Returns:
        ``True`` iff ``older`` provably precedes (is fenced by) ``newer``.
    """
    return compare_order(older, newer) is Ordering.BEFORE
