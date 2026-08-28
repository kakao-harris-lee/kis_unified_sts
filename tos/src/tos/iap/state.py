"""iap single-use consumption state machine + temporal / generation-fence predicates (§6.2/§5.6/§6.5/§6.6).

The rules that concern **state over time**: the single-use consumption state machine (§6.2 — the
EV-L1 yolk, ``state.py`` per the ioc / orthostate precedent), economic-effect continuity (§5.6 /
§16 / §19), the Trading-Approval-Generation stale-writer fence (§6.5 / §17), and non-revival
(§6.6 / §20). These are the predicate / model substrate for IAP-EV-005/010/012 (predicate-only)
and IAP-EV-011 (core §5.6) — Phase 1 authors the L1-decidable substrate and closes **no** IAP-EV
item (authoring is not evidence, VER-002-001 §5; design #15 §1).

The append-only Trading-Approval-Generation order is **not** re-authored: it REUSES
``tos.ordering`` (``Ordering`` / ``OrderingEvent`` / ``compare_order``, which depends only on
``tos.canonical``) — design #15 §3.2. A wall clock never orders (§19 line 433; iap reads no
clock). The single-use duplicate-vs-conflict classification REUSES the core
``classify_record_pair`` (design #15 §3.1) — a duplicate **identical** command is an
``IDEMPOTENT_DUP`` (same record), a same-id / different-bytes command is a ``CRITICAL_CONFLICT``
(reject).

Pure module: stdlib + ``tos.canonical`` (``classify_record_pair``) + ``tos.ordering`` +
``tos.iap.vocabulary`` only; no ``shared.*``, no sibling ``tos.*`` (design #15 §0.3 — sibling
edge 0).
"""

from __future__ import annotations

from tos.canonical import RecordPairKind, classify_record_pair
from tos.iap.vocabulary import ApprovalResult, ConsumptionOutcome, ConsumptionStatus
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "TradingApprovalGeneration",
    "consumption_transition",
    "economic_effect_outlives",
    "stale_generation_fenced",
    "recovery_revives_nothing",
]

#: The Trading Approval Generation IS the ``tos.ordering`` :class:`~tos.ordering.OrderingEvent`
#: type (design #15 §5.2 / §3.2 — "A monotonic fenced generation"): the append-only, wall-clock-
#: free generation order iap fences a stale writer against, REUSED so no self-authored order
#: exists. ``tos.ordering`` depends only on ``tos.canonical`` (core), so this is not a sibling
#: edge (§3.2 light REUSE).
TradingApprovalGeneration = OrderingEvent


def consumption_transition(
    *,
    current_status: ConsumptionStatus,
    decision_result: ApprovalResult,
    decision_current: bool | None,
    approved_intent_envelope_equivalent: bool | None,
    command_identity: str | None,
    command_digest: str | None,
    prior_command_identity: str | None = None,
    prior_command_digest: str | None = None,
) -> tuple[ConsumptionStatus, ConsumptionOutcome]:
    """The single-use consumption state machine step (§12 line 306-314 / IAP-INV-006 / IAP-AC-005).

    Models "registration -> consumption -> spent" as a pure ``(status, command) -> (status,
    outcome)`` step (state-machine exploration is the VER-002-001 EV-L1 definition — model
    checking — so it is L1-decidable). The transitions (§12 line 306-314):

    * ``ELIGIBLE`` + the decision ``is APPROVE`` + ``decision_current`` ``True`` (current /
      unexpired / unrevoked / unconsumed / compatible / in-scope, §12 line 307) + the
      approved-Intent envelope byte-for-byte / canonically equivalent (``approved_intent_envelope_equivalent``
      ``True``, §12 line 309) => ``(CONSUMED, CONSUMED_NEW)`` — one Consumption Record + one Intent
      creation request. Any missing / non-``APPROVE`` / non-current / non-equivalent input keeps it
      ``ELIGIBLE`` with ``REJECTED_INELIGIBLE`` (fail-closed — no consumption);
    * ``CONSUMED`` + a **duplicate identical** command (``classify_record_pair`` ``IDEMPOTENT_DUP``
      — same command identity + same canonical bytes) => ``(CONSUMED, IDEMPOTENT_REPLAY)`` — the
      **same** record, no new Intent (§12 line 313 "duplicate identical commands return the same
      record");
    * ``CONSUMED`` + a **conflicting** command (``CRITICAL_CONFLICT`` — same command identity,
      **different** bytes) => ``(CONSUMED, REJECTED_CONFLICT)`` (§12 line 313 "reject conflicting
      commands");
    * ``CONSUMED`` + any **distinct / not-comparable** second consumption
      (``DISTINCT`` / ``NOT_COMPARABLE`` — a different command, or an unprovable pair) =>
      ``(CONSUMED, REJECTED_REUSE)`` — single-use: at most one immutable Intent (IAP-INV-006 line
      154), and **no revival path** (a ``CONSUMED`` decision never returns to ``ELIGIBLE``; §20 /
      :func:`recovery_revives_nothing`).

    This is the **decision-consumption dimension** (iap-owned), orthogonal to the orthostate Intent
    dimension (PROPOSED->APPROVED is ``intent_transition_allowed`` ``orthostate/predicates.py:432``,
    §3.5). The runtime Intent Registry binds "consumability + Intent transition + record write" in
    one linearizable transaction; the real linearizable serialization / writer-epoch fence is
    +Security runtime (§12 line 316; IAP-EV-005) — this is the state-machine **model** only.
    Single consumption is **not** a single-send promise: every attempt still passes the
    aggregate-risk / action-flow / RCL / conformance / authority / egress gates independently (§12
    line 320; §1 line 21). Truthy-safe: only ``is`` comparisons (the enums' ``__bool__`` raises).

    Args:
        current_status: The decision's current consumption status.
        decision_result: The decision's approval result (only ``APPROVE`` is consumable).
        decision_current: Whether the decision is current / unexpired / unrevoked / in-scope
            (``None`` / ``False`` => not consumable).
        approved_intent_envelope_equivalent: Whether the approved-Intent envelope is byte-for-byte
            / canonically equivalent (``None`` / ``False`` => not consumable).
        command_identity: The incoming consumption command's identity.
        command_digest: The incoming consumption command's canonical digest.
        prior_command_identity: The already-consuming command's identity (for the ``CONSUMED``
            branch; ``None`` when first consuming).
        prior_command_digest: The already-consuming command's canonical digest.

    Returns:
        The ``(next ConsumptionStatus, ConsumptionOutcome)`` pair.
    """
    if current_status is ConsumptionStatus.ELIGIBLE:
        admissible = (
            decision_result is ApprovalResult.APPROVE
            and decision_current is True
            and approved_intent_envelope_equivalent is True
        )
        if admissible:
            return (ConsumptionStatus.CONSUMED, ConsumptionOutcome.CONSUMED_NEW)
        # Not a current APPROVE with an equivalent envelope => no consumption (fail-closed); the
        # decision stays ELIGIBLE (it was never consumed).
        return (ConsumptionStatus.ELIGIBLE, ConsumptionOutcome.REJECTED_INELIGIBLE)

    # current_status is CONSUMED: single-use is spent. Classify the incoming command against the
    # already-consuming one (classify_record_pair REUSE, §3.1).
    kind = classify_record_pair(
        prior_command_identity,
        prior_command_digest,
        command_identity,
        command_digest,
    )
    if kind is RecordPairKind.IDEMPOTENT_DUP:
        # Duplicate identical command: same record, no new Intent (§12 line 313).
        return (ConsumptionStatus.CONSUMED, ConsumptionOutcome.IDEMPOTENT_REPLAY)
    if kind is RecordPairKind.CRITICAL_CONFLICT:
        # Same command identity, different bytes: conflicting command rejected (§12 line 313).
        return (ConsumptionStatus.CONSUMED, ConsumptionOutcome.REJECTED_CONFLICT)
    # DISTINCT / NOT_COMPARABLE: a distinct (or unprovable) second consumption => single-use reuse
    # rejected (IAP-INV-006 line 154; no revival path, §20).
    return (ConsumptionStatus.CONSUMED, ConsumptionOutcome.REJECTED_REUSE)


def economic_effect_outlives(*, terminal_release_proven: bool | None) -> bool:
    """Whether the committed economic effect outlives approval expiry / invalidation (§5.6 / §16 / §19 / IAP-INV-011).

    IAP-INV-011 line 174 verbatim: "Expiry, invalidation, consumption, revocation, or loss of
    approval never proves non-acceptance, final quantity, cancellation, zero exposure, or
    releasable capacity." §16 line 397: "Approval expiry, invalidation, revocation, denial, or
    service outage does not cancel broker state or release RCL capacity. Missing ACK is not proof
    of broker non-acceptance. Cancel ACK is not Final Quantity Proof." §19 line 437: expiry
    "prevents future consumption or send. It does not expire an Intent's history, broker effect,
    order, fill, exposure, UNKNOWN state, or capacity commitment." Returns ``True`` (the effect
    outlives) **unless** a terminal release is **positively proven** (a defined downstream RCL
    transition); a ``None`` / ``False`` (missing ACK / expiry / cancel-ACK / denial / conflicting
    evidence) fails closed to persistence. The broker ACK / Final-Quantity-Proof *semantics* are
    +Broker (ADR-002-004, §3.5) — this L1 slice states only "an approval-lifecycle event is not an
    economic-state change". Isomorphic to ioc ``economic_effect_outlives`` / are
    ``non_revival_holds`` / spg ``expiry_revives_nothing``.

    Args:
        terminal_release_proven: Whether a defined downstream RCL transition positively proves
            terminal release (``None`` / ``False`` => the effect outlives).

    Returns:
        ``True`` iff the committed economic effect still outlives the approval-lifecycle event.
    """
    return terminal_release_proven is not True


def stale_generation_fenced(older: OrderingEvent, newer: OrderingEvent) -> bool:
    """Whether a newer Trading Approval Generation fences an older writer (§6.5 / §17 / IAP-INV-012).

    §17 line 405 verbatim: "Only the current fenced Intent Registry writer may consume a decision
    and create an Intent." IAP-INV-012 line 178: "Old policy, evaluator, approval, registry-writer,
    deployment, recovery, authority, and egress generations cannot decide, consume, or transmit
    after a newer applicable generation is committed." REUSES ``tos.ordering.compare_order`` (no
    re-authored order) to check that ``older`` provably precedes ``newer`` in the append-only
    Trading-Approval-Generation order. ``True`` **only** when the order is unambiguously
    ``BEFORE``; an ``AMBIGUOUS`` / ``AFTER`` pair fails closed (a wall clock never orders, §19 line
    433). The active fence **enforcement** (rejecting a stale-generation consume / transmit at
    runtime) is EV-L2/L3 +Security (§17 line 409) — this is the pure order-comparison substrate only.

    Args:
        older: The older Trading-Approval-Generation ordering event.
        newer: The newer Trading-Approval-Generation ordering event.

    Returns:
        ``True`` iff ``older`` provably precedes (is fenced by) ``newer``.
    """
    return compare_order(older, newer) is Ordering.BEFORE


def recovery_revives_nothing() -> bool:
    """Whether nothing revives a prior decision / Intent permission / authority / live state (§6.6 / §20).

    IAP-INV-014 line 186 verbatim: "Restart, replay, restore, rollback, source recovery,
    approval-service recovery, or Intent Registry recovery cannot revive a decision, Intent
    permission, authority, or live state." §20 line 447: "There is no automatic re-arm." §20 line
    445: "Restored requests, decisions, consumption records, and Intents are evidence only until
    their complete current binding and authoritative history are proven." IAP-INV-015 line 190:
    "Documents, logs, signatures, audit, replay, or successful prior decisions do not replace
    current enforcement at Intent registration and final egress." Realized as an **unconditional**
    ``True`` (isomorphic to ioc ``recovery_revives_nothing`` / are ``non_revival_holds`` / spg
    ``expiry_revives_nothing``): a lawful re-arm always requires a fresh generation + current
    artifacts + new approval + the complete ADR-002-007/015 re-arm chain, never a revival of the
    old one. The Recovery Barrier (ADR-002-017) / governed re-arm workflow enforcement is runtime.

    Returns:
        ``True`` — nothing revives a prior decision / permission / authority (unconditionally).
    """
    return True
