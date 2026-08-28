"""venue session-phase decision + Constraint Generation order + produced seam scalars (design #19 §5.1/§3.4).

Three roles:

* **session-phase admissibility (§5.1 — the central fail-closed predicate, VTG-EV-001 yolk)** —
  :func:`session_phase_admits`. A session phase is an **injected opaque token** (``str``, not an
  enum — ADR §5.5 line 127 "Names are policy-defined", §2.2(3)); the decision is pure
  admitting-set membership: the observed phase-token must be in the policy's declared admitting
  set for the **exact** action, else the order is not admissible. An unenumerated action, an
  empty admitting set, an unknown token, or a ``None`` phase is restrictive — never a permissive
  default (§8 line 245). calendar-expectation phase is time-owned; venue produces the
  **authoritative** admissibility (§0.4c — calendar ↛ admissibility, VTG-INV-002).

* **Constraint Generation monotonic order (§3.2 ordering REUSE)** —
  :func:`constraint_generation_monotone` REUSES ``tos.ordering.compare_order`` (no re-authored
  order). venue owns the fence *meaning* (§18 invalidation / §17 egress rejection); ordering
  only carries the monotonic order (§0.4e). A wall clock never orders — venue reads no clock
  (§8).

* **produced seam scalars (§3.4)** — venue is the **producer**; downstream siblings consume
  these injected scalars (they do **not** import ``tos.venue``):

  - :func:`venue_admissibility_decision_digest_of` → the ioc ``OrderConformanceProof.
    venue_admissibility_decision_digest`` slot (``ioc/records.py:414``) and the iap
    ``ProposalApprovalRequest.venue_admissibility_decision_digest`` slot
    (``iap/records.py:257``);
  - :func:`venue_snapshot_digest_of` → the iap ``ProposalApprovalRequest.venue_snapshot_digest``
    slot (``iap/records.py:256``);
  - :func:`venue_constraint_policy_ref_coordinates` / :func:`venue_constraint_snapshot_ref_coordinates`
    / :func:`order_admissibility_decision_ref_coordinates` → the capsule
    ``VenueConstraintPolicyRef`` / ``VenueConstraintSnapshotRef`` /
    ``OrderAdmissibilityDecisionRef`` (id, generation, digest) shapes (``capsule.py:130-150``),
    carried by ``DecisionContextCapsule`` (``capsule.py:242-244``).

Every produced value has a **defining function** here (design #19 §3.4 — no produced value
without a definition, no phantom slot for a sibling field that does not exist; each cited field /
line is grep-verified).

**Truthy-sentinel discipline (design #19 §4.7).** ``OrderAdmissibilityResult`` is
truthy-untestable; :func:`session_phase_admits` returns the enum by identity (never
``if result:``). A ``SessionPhase`` token is a ``str`` and is **never** consumed by truthiness
(a non-empty token is always truthy) — only by admitting-set membership (§2.2(3)).

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.venue.*`` only; no ``shared.*``,
no other sibling ``tos.*`` (design #19 §0.3). Clock-free — no wall clock orders (§8).
"""

from __future__ import annotations

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.venue.records import (
    OrderAdmissibilityDecision,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
)
from tos.venue.vocabulary import ActionClass, OrderAdmissibilityResult

__all__ = [
    # §5.1 central fail-closed predicate
    "session_phase_admits",
    # §3.2 ordering REUSE
    "constraint_generation_monotone",
    # §3.4 produced seam scalars
    "venue_admissibility_decision_digest_of",
    "venue_snapshot_digest_of",
    "venue_constraint_policy_ref_coordinates",
    "venue_constraint_snapshot_ref_coordinates",
    "order_admissibility_decision_ref_coordinates",
]


# ===========================================================================
# §5.1 — session-phase admissibility (VTG-EV-001 substrate; the central predicate)
# ===========================================================================


def session_phase_admits(
    observed_phase: str | None,
    action: ActionClass,
    snapshot: VenueConstraintSnapshot | None,
    policy: VenueConstraintPolicy | None,
) -> OrderAdmissibilityResult:
    """Whether the observed session phase admits the exact action (§10; VTG-INV-002; VTG-AC-001).

    The central fail-closed predicate (VTG-EV-001 yolk). §10 line 273 verbatim: "An order
    approved for continuous trading cannot be reused in an opening auction, volatility auction,
    reopening auction, closing auction, after-hours session, or next trading day unless the
    policy proves identical semantics and a fresh exact decision is issued" — so admission is
    per-exact-phase and per-exact-action. VTG-INV-002 line 153: "Calendar time, quote flow,
    recent trades, connectivity, login, broker health, or absence of a restriction event never
    proves order-specific tradability", so scheduled time alone is never proof (§10 line 269).
    The session phase is an **injected opaque token** (``str`` — "Names are policy-defined",
    §5.5 line 127 / §2.2(3)); the decision is pure admitting-set membership.

    Returns:

    * ``UNKNOWN`` when ``observed_phase`` is ``None``, or the snapshot / policy is absent
      (unknown phase => restrictive, never permissive — §8 line 245);
    * ``INADMISSIBLE`` when the action is unenumerated (``admitting_phases_for`` is ``None``),
      the admitting set is **empty** (∅ admits nothing — both-ways vacuity guard, §4.7), or the
      observed token is **not** in the admitting set (an unknown / non-admitting phase);
    * ``ADMISSIBLE`` **only** when the observed token is positively in the policy's admitting
      set for the exact action.

    calendar-expectation phase is time-owned (``time.SessionContext.phase``); this predicate
    produces the **authoritative** admissibility and never treats a calendar phase as one
    (§0.4c — calendar ↛ admissibility).

    Args:
        observed_phase: The authoritatively-observed session-phase token (``None`` =>
            ``UNKNOWN``).
        action: The exact order action class.
        snapshot: The venue constraint snapshot (``None`` => ``UNKNOWN``).
        policy: The venue constraint policy declaring the admitting sets (``None`` =>
            ``UNKNOWN``).

    Returns:
        The :class:`~tos.venue.vocabulary.OrderAdmissibilityResult`.
    """
    if snapshot is None or policy is None:
        return OrderAdmissibilityResult.UNKNOWN
    if observed_phase is None:
        return (
            OrderAdmissibilityResult.UNKNOWN
        )  # unknown phase => restrictive, not permissive
    admitting = policy.admitting_phases_for(action)
    if admitting is None:
        # Unenumerated action — no admitting set declared => restrictive (§8 line 245).
        return OrderAdmissibilityResult.INADMISSIBLE
    if not admitting:
        # ∅ admitting set admits nothing (a vacuous admit is not an admit, §4.7 both-ways).
        return OrderAdmissibilityResult.INADMISSIBLE
    if observed_phase not in admitting:
        # Observed token not admitted for this exact action (§10 line 273 — no cross-phase reuse).
        return OrderAdmissibilityResult.INADMISSIBLE
    return OrderAdmissibilityResult.ADMISSIBLE


# ===========================================================================
# §3.2 — Constraint Generation monotonic order (ordering REUSE)
# ===========================================================================


def constraint_generation_monotone(
    earlier: OrderingEvent, later: OrderingEvent
) -> bool:
    """Whether ``earlier`` strictly precedes ``later`` in append-only order (§3.2 / §5.3).

    REUSES ``tos.ordering.compare_order`` (no re-authored order) to check the monotonic
    restrictive Constraint Generation order (§5.3 line 117-119 "A monotonic restrictive
    generation ... A newer halt, suspension, restriction, source discontinuity, account
    restriction, or policy generation fences older decisions"). ``True`` **only** when the order
    is unambiguously ``BEFORE``; an ``AMBIGUOUS`` / ``AFTER`` pair fails closed. venue owns the
    fence *meaning* (§18 invalidation / §17 egress rejection); ordering only carries the order
    (§0.4e). A wall clock never orders — venue reads no clock (§8).

    Args:
        earlier: The earlier ordering event.
        later: The later ordering event.

    Returns:
        ``True`` iff ``earlier`` provably precedes ``later``.
    """
    return compare_order(earlier, later) is Ordering.BEFORE


# ===========================================================================
# §3.4 — produced seam scalars (venue is the producer; siblings inject-consume)
# ===========================================================================


def venue_admissibility_decision_digest_of(
    decision: OrderAdmissibilityDecision | None,
) -> str | None:
    """Produce the Order Admissibility Decision digest for the ioc / iap seams (§3.4).

    The exact ``str`` digest the ioc ``OrderConformanceProof.venue_admissibility_decision_digest``
    slot (``ioc/records.py:414``) and the iap ``ProposalApprovalRequest.
    venue_admissibility_decision_digest`` slot (``iap/records.py:257``) carry and consume by
    injection (neither sibling imports ``tos.venue`` — sibling edge 0, §3.4). **Producing this
    is not approval**: admissibility is one input to approval, never approval itself (§30 item
    12; admissibility ≠ approval). ``None`` when the decision or its canonical digest is absent
    (fail-closed downstream).

    Args:
        decision: The order admissibility decision (``None`` => ``None``).

    Returns:
        The decision's ``canonical_digest``, or ``None``.
    """
    if decision is None:
        return None
    return decision.canonical_digest


def venue_snapshot_digest_of(snapshot: VenueConstraintSnapshot | None) -> str | None:
    """Produce the Venue Constraint Snapshot digest for the iap seam (§3.4).

    The exact ``str`` digest the iap ``ProposalApprovalRequest.venue_snapshot_digest`` slot
    (``iap/records.py:256``) carries and consumes by injection (iap does not import
    ``tos.venue``). ``None`` when the snapshot or its canonical digest is absent (fail-closed).

    Args:
        snapshot: The venue constraint snapshot (``None`` => ``None``).

    Returns:
        The snapshot's ``canonical_digest``, or ``None``.
    """
    if snapshot is None:
        return None
    return snapshot.canonical_digest


def venue_constraint_policy_ref_coordinates(
    policy: VenueConstraintPolicy | None,
) -> tuple[str | None, int | None, str | None]:
    """Produce the capsule ``VenueConstraintPolicyRef`` coordinates (§3.4).

    The (``policy_id``, ``policy_generation``, ``canonical_digest``) triple the capsule
    ``VenueConstraintPolicyRef`` (``capsule.py:130-135``) carries, filled from the venue-owned
    full artifact and injected into the capsule ``DecisionContextCapsule.venue_constraint_policy``
    slot (``capsule.py:242``; capsule does not import ``tos.venue``). capsule owns the ``*Ref``
    schema; venue owns the full artifact (§3.5).

    Args:
        policy: The venue constraint policy (``None`` => all-``None`` triple).

    Returns:
        The (policy_id, policy_generation, canonical_digest) coordinate triple.
    """
    if policy is None:
        return (None, None, None)
    return (policy.policy_id, policy.policy_generation, policy.canonical_digest)


def venue_constraint_snapshot_ref_coordinates(
    snapshot: VenueConstraintSnapshot | None,
) -> tuple[str | None, int | None, str | None]:
    """Produce the capsule ``VenueConstraintSnapshotRef`` coordinates (§3.4).

    The (``snapshot_id``, ``constraint_generation``, ``canonical_digest``) triple the capsule
    ``VenueConstraintSnapshotRef`` (``capsule.py:138-143``) carries, injected into the capsule
    ``DecisionContextCapsule.venue_constraint_snapshot`` slot (``capsule.py:243``).

    Args:
        snapshot: The venue constraint snapshot (``None`` => all-``None`` triple).

    Returns:
        The (snapshot_id, constraint_generation, canonical_digest) coordinate triple.
    """
    if snapshot is None:
        return (None, None, None)
    return (
        snapshot.snapshot_id,
        snapshot.constraint_generation,
        snapshot.canonical_digest,
    )


def order_admissibility_decision_ref_coordinates(
    decision: OrderAdmissibilityDecision | None,
) -> tuple[str | None, str | None]:
    """Produce the capsule ``OrderAdmissibilityDecisionRef`` coordinates (§3.4).

    The (``decision_id``, ``canonical_digest``) pair the capsule ``OrderAdmissibilityDecisionRef``
    (``capsule.py:146-150``) carries, injected into the capsule
    ``DecisionContextCapsule.order_admissibility_decision`` slot (``capsule.py:244``). The Ref
    carries **no** generation coordinate (unlike the policy / snapshot Refs) — this pair matches
    that shape exactly (§2.1).

    Args:
        decision: The order admissibility decision (``None`` => all-``None`` pair).

    Returns:
        The (decision_id, canonical_digest) coordinate pair.
    """
    if decision is None:
        return (None, None)
    return (decision.decision_id, decision.canonical_digest)
