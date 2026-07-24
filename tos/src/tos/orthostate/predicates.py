"""Pure orthostate predicates (design #8 §5, §6; ADR-002-005 §10-§13).

The EV-L1 *functions* whose contract the property tests verify. None is a stored field;
all are computed on demand over **injected** state (design #8 §0.2: no clock reads, no
egress, no persistence, no runtime coupling enforcement — those are EV-L2/L3). Every
predicate is conservative / **fail-closed**: an empty set, a missing / ``None``
coordinate or side-flag, an unproven proof, or an unknown state can never become a
coupling pass, a permitted conservatism reduction, an ownership grant, or a
less-conservative restart (ADR-002-005 §11; §10 line 164 "An invariant violation is a
Critical incident and an immediate new-risk halt condition").

Contents (design section -> ADR / STATE-EV substrate; **no STATE-EV is closed**, §1):

* §5.2/§5.3 : ``coupling_violations`` / ``no_coupling_violation`` — CPL-1..7 static
  detect-and-flag over a composite; **never** normalizes (STATE-EV-003 L1 slice).
* §6.1 : ``conservative_direction_ok`` — weak-basis can't reduce conservatism, increase
  never blocked; Capacity delegates to ``rcl.transition_allowed`` (STATE-EV-002 substrate).
* §5.4/§6 : ``intent_transition_allowed`` / ``attempt_transition_allowed`` /
  ``knowledge_transition_allowed`` — the ADR §5/§6/§8 arrow tables + positive-proof
  guards (Broker Order is a state set, no arrow predicate).
* §6.2 : ``may_transition`` — the §12 ownership table; non-owner / None => False
  (STATE-EV-005 substrate).
* §6.3 : ``reconstruct_conservative`` — the §13 conservative restart projection;
  Knowledge codomain structurally excludes ``RECONCILED`` (STATE-EV-004 substrate).

Capacity is REUSED from ``tos.rcl`` (design #8 §3.4): ``CapacityState``, the
``capacity_at_least_as_conservative`` comparator, and ``transition_allowed``. The
capacity conservatism lattice / rank is **never** re-derived here (DRY / no drift —
design #8 decision #3).

Pure module: ``pydantic`` + stdlib + ``tos.rcl`` / ``tos.orthostate`` only; no real
clock, no ``shared.*``, no ``tos.evidence`` / ``tos.capsule`` / ``tos.time`` /
``tos.authority`` / ``tos.liveauth`` / ``tos.dsl`` (design #8 §0.3/§3.5).
"""

from __future__ import annotations

from tos.orthostate.records import CompositeState
from tos.orthostate.state import CouplingSideConditions
from tos.orthostate.vocabulary import (
    WEAK_BASES,
    BrokerOrderState,
    ConservatismBasis,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransitionAuthority,
    TransmissionAttemptState,
)
from tos.rcl import (
    CapacityState,
    TransitionCause,
    capacity_at_least_as_conservative,
    transition_allowed,
)

# ===========================================================================
# §5.2 / §5.3 — cross-dimension coupling invariants (CPL-1..7, static)
# ===========================================================================

#: Attempt states that assert a potentially-live send effect (CPL-1 antecedent).
_ATTEMPT_POTENTIALLY_LIVE: frozenset[TransmissionAttemptState] = frozenset(
    {TransmissionAttemptState.SEND_STARTED, TransmissionAttemptState.SENT_UNCONFIRMED}
)

#: Broker states permitting a proven release under CPL-2 (with proof where required).
_CPL2_RELEASE_BROKER_STATES: frozenset[BrokerOrderState] = frozenset(
    {
        BrokerOrderState.CANCELLED,
        BrokerOrderState.REJECTED,
        BrokerOrderState.EXPIRED,
        BrokerOrderState.FILLED,
    }
)

#: Knowledge states that force ``QUARANTINED_UNKNOWN`` under CPL-5.
_CPL5_KNOWLEDGE_STATES: frozenset[KnowledgeState] = frozenset(
    {KnowledgeState.CONFLICTED, KnowledgeState.QUARANTINED}
)

#: Attempt states that imply the write-ahead ``SEND_STARTED`` boundary was crossed
#: (CPL-6 antecedent — every state reachable from ``SEND_STARTED`` onward).
_ATTEMPT_SEND_STARTED_AND_BEYOND: frozenset[TransmissionAttemptState] = frozenset(
    {
        TransmissionAttemptState.SEND_STARTED,
        TransmissionAttemptState.SENT_UNCONFIRMED,
        TransmissionAttemptState.ACK_OBSERVED,
        TransmissionAttemptState.SEND_FAILED_PROVEN,
        TransmissionAttemptState.SUPERSEDED,
    }
)


def coupling_violations(
    composite: CompositeState,
    side: CouplingSideConditions | None = None,
) -> frozenset[str]:
    """The set of violated cross-dimension coupling invariants (design #8 §5; §10).

    A pure **static detect-and-flag** predicate over a well-formed composite: it returns
    the ids of the CPL invariants (ADR-002-005 §10 line 156-162) that the composite
    violates, and **never** normalizes / repairs the composite (design #8 §5.5; §10 line
    164 — a violation is a Critical incident to hold, not silently fix). An empty set
    means "no violation detected", **not** "certified fully legal" — the CPL invariants
    are necessary conditions, not a sufficient enumeration (design #8 §5.4, over-claim
    ban).

    Every CPL is fail-closed on its injected side-condition: a ``None`` proof / epoch /
    trapped flag is treated as *not proven* and can raise a violation (design #8 §5.2).
    Overlapping exact-value obligations (e.g. CPL-5 ``QUARANTINED_UNKNOWN`` ∧ CPL-7
    ``TRAPPED_CONSUMED``) cannot both be satisfied and so both surface — the composite is
    illegal for every capacity value, and **no CPL is dropped** to "resolve" it (design
    #8 §5.3b — dropping either loses the quarantine / trapped signal, a fail-open).

    Args:
        composite: The five-dimension observation under test (all coordinates present
            by construction — design #8 §4.4 completeness).
        side: The injected proof / epoch / trapped side-conditions; ``None`` uses the
            all-``None`` (fail-closed) default.

    Returns:
        The frozenset of violated CPL ids (empty iff none detected).
    """
    if side is None:
        side = CouplingSideConditions()

    attempt = composite.transmission_attempt_state
    broker = composite.broker_order_state
    knowledge = composite.knowledge_state
    cap = composite.capacity_state

    violations: set[str] = set()

    # CPL-1 (potential effect => capacity): Attempt in {SEND_STARTED, SENT_UNCONFIRMED}
    # or Broker=UNKNOWN => Capacity at least as conservative as POTENTIALLY_LIVE (§10
    # line 156). Uses the rcl comparator (design #8 §3.4b) — no local rank re-derivation.
    if attempt in _ATTEMPT_POTENTIALLY_LIVE or broker is BrokerOrderState.UNKNOWN:
        if not capacity_at_least_as_conservative(cap, CapacityState.POTENTIALLY_LIVE):
            violations.add("CPL-1")

    # CPL-2 (no release without proof): Capacity=RELEASED requires Knowledge=RECONCILED
    # (or CONSISTENT under the applicable proof rule) AND Broker in {CANCELLED, REJECTED,
    # EXPIRED, FILLED} AND Final Quantity Proof where required (§10 line 157). Any None
    # flag => not proven => violation.
    if cap is CapacityState.RELEASED:
        knowledge_proven = knowledge is KnowledgeState.RECONCILED or (
            knowledge is KnowledgeState.CONSISTENT
            and side.consistent_release_proof_rule is True
        )
        broker_terminal = broker in _CPL2_RELEASE_BROKER_STATES
        fqp_proven = side.final_quantity_proof is True
        if not (knowledge_proven and broker_terminal and fqp_proven):
            violations.add("CPL-2")

    # CPL-3 (fill transfer, static consistency): Broker=FILLED => Capacity=POSITION_
    # CONSUMED; Broker=PARTIALLY_FILLED => Capacity=PARTIALLY_CONSUMED (§10 line 158;
    # ADR-002-002 §15.1). The atomic per-quantity transfer + remaining-split is runtime
    # (/3); this is the static aggregate-state consistency slice (design #8 §5.2 Gap).
    if broker is BrokerOrderState.FILLED and cap is not CapacityState.POSITION_CONSUMED:
        violations.add("CPL-3")
    if (
        broker is BrokerOrderState.PARTIALLY_FILLED
        and cap is not CapacityState.PARTIALLY_CONSUMED
    ):
        violations.add("CPL-3")

    # CPL-4 (cancel is not release): Broker=CANCEL_PENDING or a bare cancel-ACK
    # (Broker=CANCELLED with no Final Quantity Proof) => Capacity != RELEASED (§10 line
    # 159; ADR-002-002 §16.2). In the static view CPL-2 already forbids RELEASED for
    # both cases (design #8 §5.2 m2 subsumption); CPL-4's own "at most RELEASE_PENDING_
    # PROOF" content is transitional (/3). A proven CANCELLED + release is allowed by
    # CPL-2 and so is NOT a bare cancel-ACK.
    bare_cancel_ack = (
        broker is BrokerOrderState.CANCELLED and side.final_quantity_proof is None
    )
    if broker is BrokerOrderState.CANCEL_PENDING or bare_cancel_ack:
        if cap is CapacityState.RELEASED:
            violations.add("CPL-4")

    # CPL-5 (unknown quarantine): Broker=UNKNOWN or Knowledge in {CONFLICTED,
    # QUARANTINED} => Capacity = QUARANTINED_UNKNOWN exactly (§10 line 160; §7 line 122).
    # In a satisfiable overlap with CPL-1 (Broker=UNKNOWN) the more-conservative exact
    # value dominates (design #8 §5.3a): only QUARANTINED_UNKNOWN satisfies both.
    if broker is BrokerOrderState.UNKNOWN or knowledge in _CPL5_KNOWLEDGE_STATES:
        if cap is not CapacityState.QUARANTINED_UNKNOWN:
            violations.add("CPL-5")

    # CPL-6 (authority gate on transmission): an attempt that reached SEND_STARTED+
    # requires a current authority epoch verifiable at final egress; a stale / unknown
    # epoch fails closed (§10 line 161; ADR-002-003). The actual egress check is
    # deferred (/3); Phase 1 realizes only the injected binding premise.
    if attempt in _ATTEMPT_SEND_STARTED_AND_BEYOND:
        if side.authority_epoch_current is not True:
            violations.add("CPL-6")

    # CPL-7 (trapped exposure): confirmed non-reducible exposure => Capacity =
    # TRAPPED_CONSUMED exactly, regardless of any pending exit Intent / Attempt (§10
    # line 162; ADR-002-002 §24). Only a True flag asserts exposure.
    if side.non_reducible_exposure is True:
        if cap is not CapacityState.TRAPPED_CONSUMED:
            violations.add("CPL-7")

    return frozenset(violations)


def no_coupling_violation(
    composite: CompositeState,
    side: CouplingSideConditions | None = None,
) -> bool:
    """Whether no CPL invariant violation is detected (design #8 §5.1).

    ``True`` iff :func:`coupling_violations` is empty. This asserts only "no violation
    **detected**" — never "certified fully legal" (design #8 §5.4, necessary-not-
    sufficient discipline).

    Args:
        composite: The composite under test.
        side: The injected side-conditions (``None`` => fail-closed default).

    Returns:
        ``True`` iff the violation set is empty.
    """
    return not coupling_violations(composite, side)


# ===========================================================================
# §6.1 — conservative-direction rule (weak basis can't reduce; increase free)
# ===========================================================================

#: Per-dimension conservatism rank for the four LOCAL dimensions (higher = more
#: conservative = more uncertainty / assumed exposure / less authority — ADR-002-005
#: §11 line 170). Capacity is NOT here — it delegates to ``rcl.transition_allowed``
#: (design #8 §3.4/§6.1b). These ranks encode the §11 conservative direction; the full
#: per-dimension total-order ratification (notably the Intent lifecycle) is reserved for
#: Phase-0 (design #8 §6.1c) — undetermined reductions still fail closed here.
_INTENT_CONSERVATISM_RANK: dict[IntentState, int] = {
    # Terminal resolved (no exposure remains, entered only under proof) — least conservative.
    IntentState.CLOSED: 0,
    IntentState.WITHDRAWN: 0,
    # Authority axis: more authority granted = less conservative (advancing it reduces
    # conservatism and needs the approval / aggregate-risk decision, §5 line 67/75).
    IntentState.ACTIVE: 1,
    IntentState.AUTHORIZED_FOR_CAPACITY: 2,
    IntentState.APPROVED: 3,
    IntentState.PROPOSED: 4,
    # Denied: no authority ever, a halt outcome — most conservative.
    IntentState.DENIED: 5,
}

#: Attempt conservatism rank: potentially-live states (must assume live) are most
#: conservative; SEND_FAILED_PROVEN (proven not live, entered only under positive proof,
#: §6 line 97) is least conservative.
_ATTEMPT_CONSERVATISM_RANK: dict[TransmissionAttemptState, int] = {
    TransmissionAttemptState.SEND_FAILED_PROVEN: 0,
    TransmissionAttemptState.NONE: 1,
    TransmissionAttemptState.PREPARED: 2,
    TransmissionAttemptState.CAPABILITY_ISSUED: 3,
    TransmissionAttemptState.SUPERSEDED: 4,
    TransmissionAttemptState.ACK_OBSERVED: 5,
    TransmissionAttemptState.SENT_UNCONFIRMED: 6,
    TransmissionAttemptState.SEND_STARTED: 7,
}

#: Broker conservatism rank: UNKNOWN (forces quarantine, §7 line 122) is most
#: conservative; NONE_OBSERVED (asserts no order) is least. Collapsing UNKNOWN to a
#: less-conservative value under a weak basis is forbidden (§11 line 173).
_BROKER_CONSERVATISM_RANK: dict[BrokerOrderState, int] = {
    BrokerOrderState.NONE_OBSERVED: 0,
    BrokerOrderState.CANCELLED: 1,
    BrokerOrderState.REJECTED: 1,
    BrokerOrderState.EXPIRED: 1,
    BrokerOrderState.WORKING: 2,
    BrokerOrderState.CANCEL_PENDING: 3,
    BrokerOrderState.PARTIALLY_FILLED: 4,
    BrokerOrderState.FILLED: 5,
    BrokerOrderState.UNKNOWN: 6,
}

#: Knowledge conservatism rank: RECONCILED (fully corroborated) is least conservative;
#: QUARANTINED (stable conservative, exit needs evidence, §8 line 142) is most. A fresh
#: conflict re-opening RECONCILED -> CONFLICTED is a conservatism increase and is always
#: permitted (§11 line 177).
_KNOWLEDGE_CONSERVATISM_RANK: dict[KnowledgeState, int] = {
    KnowledgeState.RECONCILED: 0,
    KnowledgeState.CONSISTENT: 1,
    KnowledgeState.RECONCILING: 2,
    KnowledgeState.UNOBSERVED: 3,
    KnowledgeState.STALE: 4,
    KnowledgeState.CONFLICTED: 5,
    KnowledgeState.QUARANTINED: 6,
}

#: The four local dimensions' conservatism ranks by dimension (Capacity excluded).
_LOCAL_CONSERVATISM_RANK: dict[StateDimension, dict] = {
    StateDimension.INTENT: _INTENT_CONSERVATISM_RANK,
    StateDimension.TRANSMISSION_ATTEMPT: _ATTEMPT_CONSERVATISM_RANK,
    StateDimension.BROKER_ORDER: _BROKER_CONSERVATISM_RANK,
    StateDimension.KNOWLEDGE: _KNOWLEDGE_CONSERVATISM_RANK,
}


def conservative_direction_ok(
    dimension: StateDimension,
    from_state: object,
    to_state: object,
    basis: ConservatismBasis | TransitionCause | None,
) -> bool:
    """Whether a per-dimension transition respects the conservative-direction rule (§6.1).

    ADR-002-005 §11: increasing (or holding) conservatism is **always permitted and
    never blocked** (line 177); reducing conservatism requires the specific positive
    proof for that transition — a **weak** basis (timeout / absence / local cache /
    operator assertion / recovery-reconnect, :data:`WEAK_BASES`) may only *increase*
    conservatism (line 172-175), and a ``None`` basis fails closed (treated as weak).

    * **Capacity** delegates to ``tos.rcl.transition_allowed`` (design #8 §3.4/§6.1b) —
      the capacity lattice is never re-derived here; ``basis`` must be a
      ``tos.rcl.TransitionCause`` and ``from_state`` / ``to_state`` must be
      ``CapacityState`` (else fail-closed ``False``).
    * The **four local dimensions** use their §11 conservatism rank
      (:data:`_LOCAL_CONSERVATISM_RANK`): ``to`` at least as conservative as ``from`` =>
      allowed under any basis (including ``None``); a reduction => allowed only under a
      strong (non-weak, non-``None``) :class:`ConservatismBasis`. An off-dimension or
      unranked coordinate fails closed.

    Args:
        dimension: The dimension being transitioned.
        from_state: The current state (dimension-typed; ``CapacityState`` for Capacity).
        to_state: The proposed next state.
        basis: The transition basis — a ``TransitionCause`` for Capacity, a
            ``ConservatismBasis`` for the local dimensions, or ``None`` (fail-closed).

    Returns:
        ``True`` iff the transition respects the conservative direction.
    """
    if dimension is StateDimension.CAPACITY:
        if not isinstance(from_state, CapacityState) or not isinstance(
            to_state, CapacityState
        ):
            return False
        if not isinstance(basis, TransitionCause):
            # Capacity conservatism uses rcl's TransitionCause vocabulary (design #8
            # §6.1b); anything else (incl. None or a ConservatismBasis) fails closed.
            return False
        return transition_allowed(from_state, to_state, basis)

    rank = _LOCAL_CONSERVATISM_RANK.get(dimension)
    if rank is None:
        return False
    if from_state not in rank or to_state not in rank:
        return False  # off-dimension / unknown coordinate => fail-closed
    if rank[to_state] >= rank[from_state]:
        return True  # increase or hold conservatism — never blocked (§11 line 177)
    # A reduction in conservatism requires a strong (non-weak, non-None) basis.
    return isinstance(basis, ConservatismBasis) and basis not in WEAK_BASES


# ===========================================================================
# §5.4 / §6 — per-dimension transition legality (arrow tables + proof guards)
# ===========================================================================

#: Intent arrows (ADR-002-005 §5 line 69-73). PROPOSED -> DENIED is deliberately
#: ABSENT: DENIED branches from APPROVED (line 71 column-22 + line 75), design #8 §2.2.
_INTENT_TRANSITIONS: frozenset[tuple[IntentState, IntentState]] = frozenset(
    {
        (IntentState.PROPOSED, IntentState.APPROVED),
        (IntentState.APPROVED, IntentState.AUTHORIZED_FOR_CAPACITY),
        (IntentState.APPROVED, IntentState.DENIED),
        (IntentState.AUTHORIZED_FOR_CAPACITY, IntentState.ACTIVE),
        (IntentState.ACTIVE, IntentState.CLOSED),
        (IntentState.ACTIVE, IntentState.WITHDRAWN),
    }
)

#: Intent states whose entry requires proof of no potentially-live effect (§5 line 77).
_INTENT_PROOF_REQUIRED: frozenset[IntentState] = frozenset(
    {IntentState.CLOSED, IntentState.WITHDRAWN}
)

#: Transmission Attempt arrows (ADR-002-005 §6 line 85-92).
_ATTEMPT_TRANSITIONS: frozenset[
    tuple[TransmissionAttemptState, TransmissionAttemptState]
] = frozenset(
    {
        (TransmissionAttemptState.NONE, TransmissionAttemptState.PREPARED),
        (
            TransmissionAttemptState.PREPARED,
            TransmissionAttemptState.CAPABILITY_ISSUED,
        ),
        (
            TransmissionAttemptState.CAPABILITY_ISSUED,
            TransmissionAttemptState.SEND_STARTED,
        ),
        (
            TransmissionAttemptState.SEND_STARTED,
            TransmissionAttemptState.SENT_UNCONFIRMED,
        ),
        (
            TransmissionAttemptState.SENT_UNCONFIRMED,
            TransmissionAttemptState.ACK_OBSERVED,
        ),
        (
            TransmissionAttemptState.SENT_UNCONFIRMED,
            TransmissionAttemptState.SEND_FAILED_PROVEN,
        ),
        (
            TransmissionAttemptState.SENT_UNCONFIRMED,
            TransmissionAttemptState.SUPERSEDED,
        ),
    }
)

#: Knowledge arrows (ADR-002-005 §8 line 130-136) + the §11 line 177 conservatism-
#: increasing re-open (RECONCILED -> CONFLICTED), the STALE freshness-loss arrows, and
#: the QUARANTINED evidence-gated exit (§8 line 142).
_KNOWLEDGE_TRANSITIONS: frozenset[tuple[KnowledgeState, KnowledgeState]] = frozenset(
    {
        (KnowledgeState.UNOBSERVED, KnowledgeState.CONSISTENT),
        (KnowledgeState.UNOBSERVED, KnowledgeState.CONFLICTED),
        (KnowledgeState.CONSISTENT, KnowledgeState.CONFLICTED),
        (KnowledgeState.RECONCILED, KnowledgeState.CONFLICTED),
        (KnowledgeState.CONFLICTED, KnowledgeState.RECONCILING),
        (KnowledgeState.RECONCILING, KnowledgeState.RECONCILED),
        (KnowledgeState.RECONCILING, KnowledgeState.QUARANTINED),
        (KnowledgeState.QUARANTINED, KnowledgeState.RECONCILING),
        (KnowledgeState.CONSISTENT, KnowledgeState.STALE),
        (KnowledgeState.RECONCILED, KnowledgeState.STALE),
    }
)


def intent_transition_allowed(
    from_state: IntentState | None,
    to_state: IntentState | None,
    *,
    no_potentially_live_proof: bool | None = None,
) -> bool:
    """Whether an Intent transition is legal (design #8 §6; ADR-002-005 §5).

    ``True`` only for the exact §5 arrows (:data:`_INTENT_TRANSITIONS`). ``PROPOSED ->
    DENIED`` is NOT allowed (DENIED branches from APPROVED, §2.2). Entry to ``CLOSED`` /
    ``WITHDRAWN`` additionally requires proof that no potentially-live effect remains
    (§5 line 77): ``no_potentially_live_proof`` must be ``True`` — ``None`` / ``False``
    fails closed. Terminal states (``CLOSED`` / ``DENIED`` / ``WITHDRAWN``) have no
    outgoing arrow. ``None`` on either side fails closed.

    Args:
        from_state: The current Intent state (or ``None``).
        to_state: The proposed next Intent state (or ``None``).
        no_potentially_live_proof: Proof that Capacity + Knowledge show no
            potentially-live effect (required to enter ``CLOSED`` / ``WITHDRAWN``).

    Returns:
        ``True`` iff the transition is legal.
    """
    if from_state is None or to_state is None:
        return False
    if (from_state, to_state) not in _INTENT_TRANSITIONS:
        return False
    if to_state in _INTENT_PROOF_REQUIRED:
        return no_potentially_live_proof is True
    return True


def attempt_transition_allowed(
    from_state: TransmissionAttemptState | None,
    to_state: TransmissionAttemptState | None,
    *,
    positive_send_failure_evidence: bool | None = None,
) -> bool:
    """Whether a Transmission-Attempt transition is legal (design #8 §6; ADR-002-005 §6).

    ``True`` only for the exact §6 arrows (:data:`_ATTEMPT_TRANSITIONS`). Entry to
    ``SEND_FAILED_PROVEN`` additionally requires **positive evidence** the broker did
    not and cannot accept the attempt (§6 line 97): ``positive_send_failure_evidence``
    must be ``True`` — timeout / absence / reset / restart (``None`` / ``False``) can
    **never** reach ``SEND_FAILED_PROVEN`` (fail-closed). ``None`` on either side fails
    closed.

    Args:
        from_state: The current Attempt state (or ``None``).
        to_state: The proposed next Attempt state (or ``None``).
        positive_send_failure_evidence: Positive proof of non-acceptance (required to
            enter ``SEND_FAILED_PROVEN``).

    Returns:
        ``True`` iff the transition is legal.
    """
    if from_state is None or to_state is None:
        return False
    if (from_state, to_state) not in _ATTEMPT_TRANSITIONS:
        return False
    if to_state is TransmissionAttemptState.SEND_FAILED_PROVEN:
        return positive_send_failure_evidence is True
    return True


def knowledge_transition_allowed(
    from_state: KnowledgeState | None,
    to_state: KnowledgeState | None,
    *,
    corroboration: bool | None = None,
    final_quantity_proof_where_broker_involved: bool | None = None,
    freshness_lost: bool | None = None,
    quarantine_exit_evidence: bool | None = None,
) -> bool:
    """Whether a Knowledge transition is legal (design #8 §6; ADR-002-005 §8).

    ``True`` only for the §8 arrows (:data:`_KNOWLEDGE_TRANSITIONS`), each with its
    positive-proof guard (all ``None`` / ``False`` fail closed):

    * Entry to ``RECONCILED`` requires ``corroboration`` **and**
      ``final_quantity_proof_where_broker_involved`` both ``True`` (§8 line 140 —
      positive corroborating evidence + Final Quantity Proof where a broker order is
      involved; never inferred from a single source or silence).
    * Entry to ``STALE`` requires ``freshness_lost`` ``True`` (§8 line 141).
    * Exit from ``QUARANTINED`` requires ``quarantine_exit_evidence`` ``True`` (§8 line
      142 — escaping quarantine requires evidence, never assertion).

    ``None`` on either side fails closed.

    Args:
        from_state: The current Knowledge state (or ``None``).
        to_state: The proposed next Knowledge state (or ``None``).
        corroboration: Positive corroborating evidence (required for ``RECONCILED``).
        final_quantity_proof_where_broker_involved: Final Quantity Proof is satisfied
            (or not needed) where a broker order is involved (required for ``RECONCILED``).
        freshness_lost: Freshness bound exceeded (required for ``STALE``).
        quarantine_exit_evidence: Evidence sufficient to leave ``QUARANTINED``.

    Returns:
        ``True`` iff the transition is legal.
    """
    if from_state is None or to_state is None:
        return False
    if (from_state, to_state) not in _KNOWLEDGE_TRANSITIONS:
        return False
    if to_state is KnowledgeState.RECONCILED:
        return (
            corroboration is True and final_quantity_proof_where_broker_involved is True
        )
    if to_state is KnowledgeState.STALE:
        return freshness_lost is True
    if from_state is KnowledgeState.QUARANTINED:
        return quarantine_exit_evidence is True
    return True


# ===========================================================================
# §6.2 — transition ownership (§12 table; non-owner / None => False)
# ===========================================================================

#: The §12 exclusive transition authorities for the four SINGLE-OWNER dimensions
#: (ADR-002-005 line 185/187-189). The Transmission Attempt dimension is deliberately
#: NOT here: it is region-split by ``to_state`` (see below), so a single owner set would
#: over-grant (a send-boundary write to the preparation owner, or vice versa).
_DIMENSION_OWNERS: dict[StateDimension, frozenset[TransitionAuthority]] = {
    StateDimension.INTENT: frozenset({TransitionAuthority.INTENT_REGISTRY}),
    StateDimension.BROKER_ORDER: frozenset(
        {TransitionAuthority.BROKER_ADAPTER_EVIDENCE}
    ),
    StateDimension.KNOWLEDGE: frozenset({TransitionAuthority.RECONCILIATION_SERVICE}),
    StateDimension.CAPACITY: frozenset({TransitionAuthority.RISK_CAPACITY_LEDGER}),
}

#: Transmission Attempt PREPARATION region — owned by the Execution Coordinator alone
#: (ADR-002-005 §6 line 82 "Execution Coordinator for preparation"; §12 line 186). The
#: region is gated by the transition's ``to_state``: entry into PREPARED / CAPABILITY_ISSUED.
_ATTEMPT_PREP_REGION: frozenset[TransmissionAttemptState] = frozenset(
    {
        TransmissionAttemptState.PREPARED,
        TransmissionAttemptState.CAPABILITY_ISSUED,
    }
)

#: Transmission Attempt SEND-BOUNDARY region — owned by the Broker Adapter / Egress
#: Gateway alone (ADR-002-005 §6 line 82 "Broker Adapter / Egress Gateway for the send
#: boundary"; §12 line 186). Gated by ``to_state``: the write-ahead entry INTO
#: SEND_STARTED (§6 line 89 "durably recorded BEFORE the network call; write-ahead
#: boundary") and every state beyond it. Because gating is by ``to_state``, the
#: CAPABILITY_ISSUED -> SEND_STARTED cell lands here (the Egress Gateway owns the entry
#: into SEND_STARTED) — design #8 §6.2.
_ATTEMPT_SEND_BOUNDARY_REGION: frozenset[TransmissionAttemptState] = frozenset(
    {
        TransmissionAttemptState.SEND_STARTED,
        TransmissionAttemptState.SENT_UNCONFIRMED,
        TransmissionAttemptState.ACK_OBSERVED,
        TransmissionAttemptState.SEND_FAILED_PROVEN,
        TransmissionAttemptState.SUPERSEDED,
    }
)


def may_transition(
    actor: TransitionAuthority | None,
    dimension: StateDimension,
    from_state: object,
    to_state: object,
) -> bool:
    """Whether ``actor`` owns the authority for this dimension transition (§6.2; §12).

    ``True`` iff ``actor`` is the exclusive owner of this transition (ADR-002-005 §12
    line 191 "No component SHALL write a dimension it does not own"). The argument order
    follows design #8 §6.2 exactly: ``(actor, dimension, from_state, to_state)``.

    The **Transmission Attempt** dimension is **region-split by ``to_state``** (design #8
    §6.2; ADR-002-005 §6 line 82 + line 89; §12 line 186): the preparation region (entry
    into ``PREPARED`` / ``CAPABILITY_ISSUED``) is owned by the ``EXECUTION_COORDINATOR``
    **alone**, and the send-boundary region (the write-ahead entry into ``SEND_STARTED``
    and every state beyond it) is owned by the ``BROKER_ADAPTER_EGRESS`` **alone**. So the
    Execution Coordinator may NOT perform a send-boundary transition and the Egress
    Gateway may NOT perform a preparation transition. An Attempt transition with a
    ``None`` ``from_state`` / ``to_state``, or an off-region ``to_state`` (e.g. into the
    genesis ``NONE``), fails closed.

    The other four dimensions have a single exclusive owner each (Intent Registry /
    Broker-evidence adapter / Reconciliation Service / Risk Capacity Ledger), so they are
    **actor-only** — ``from_state`` / ``to_state`` are accepted for signature uniformity
    but not region-gated (there is no sub-region to distinguish). A ``None`` actor, a
    ``None`` / unknown dimension, or any non-owner fails closed.

    Actor authentication and the rejection-evidencing of a non-owner write are EV-L2/L3 +
    Security (STATE-EV-005 minimum level) and are out of scope; Phase 1 realizes only the
    role-coordinate ownership predicate.

    Args:
        actor: The transition authority attempting the write (or ``None``).
        dimension: The dimension whose ownership is queried.
        from_state: The transition's current state (its ``None``-ness fails an Attempt
            transition closed; ignored for the single-owner dimensions).
        to_state: The transition's next state (gates the Attempt region; ignored for the
            single-owner dimensions).

    Returns:
        ``True`` iff ``actor`` may perform this transition on ``dimension``.
    """
    if actor is None:
        return False
    if dimension is StateDimension.TRANSMISSION_ATTEMPT:
        if from_state is None or to_state is None:
            return False  # an Attempt transition needs both endpoints (fail-closed)
        if to_state in _ATTEMPT_PREP_REGION:
            return actor is TransitionAuthority.EXECUTION_COORDINATOR
        if to_state in _ATTEMPT_SEND_BOUNDARY_REGION:
            return actor is TransitionAuthority.BROKER_ADAPTER_EGRESS
        return False  # off-region to_state (e.g. genesis NONE) => fail-closed
    owners = _DIMENSION_OWNERS.get(dimension)
    if owners is None:
        return False
    return actor in owners


# ===========================================================================
# §6.3 — conservative restart reconstruction (Knowledge never RECONCILED)
# ===========================================================================

#: Attempt states that, on restart, imply the send may be live (§13 line 198): reached
#: SEND_STARTED and not proven-terminal (SEND_FAILED_PROVEN is the only proven-not-live).
_ATTEMPT_POTENTIALLY_LIVE_AFTER_RESTART: frozenset[TransmissionAttemptState] = (
    frozenset(
        {
            TransmissionAttemptState.SEND_STARTED,
            TransmissionAttemptState.SENT_UNCONFIRMED,
            TransmissionAttemptState.ACK_OBSERVED,
            TransmissionAttemptState.SUPERSEDED,
        }
    )
)

#: Broker states that are structurally terminal and so preserved across restart (§13
#: line 198); every other non-UNKNOWN broker state is reconstructed as UNKNOWN.
_BROKER_STRUCTURALLY_TERMINAL: frozenset[BrokerOrderState] = frozenset(
    {
        BrokerOrderState.FILLED,
        BrokerOrderState.CANCELLED,
        BrokerOrderState.REJECTED,
        BrokerOrderState.EXPIRED,
    }
)

#: Positive-knowledge states that must NOT survive a restart (§13 line 199 — re-derive,
#: never carry positive knowledge across a restart; §11 line 175 recovery != knowledge).
_KNOWLEDGE_DOWNGRADE_ON_RESTART: frozenset[KnowledgeState] = frozenset(
    {KnowledgeState.RECONCILED, KnowledgeState.CONSISTENT}
)


def reconstruct_conservative(pre: CompositeState) -> CompositeState:
    """Project a pre-restart composite to a conservative post-restart one (§6.3; §13).

    A pure projection realizing ADR-002-005 §13 line 195-200 (the substrate only —
    actual durable reload / crash recovery / Recovery Barrier are EV-L3, design #8 §6.3):

    * If the Attempt reached ``SEND_STARTED`` and is not proven-terminal, Capacity is
      raised to at least ``POTENTIALLY_LIVE`` (preserved if already more conservative —
      via the rcl comparator, no rank re-derivation) (line 198).
    * A Broker Order that is not structurally terminal is reconstructed as ``UNKNOWN``;
      terminal / already-``UNKNOWN`` states are preserved (line 198).
    * Knowledge is re-derived: the positive-knowledge states (``RECONCILED`` /
      ``CONSISTENT``) are downgraded to ``CONFLICTED`` — the codomain **structurally
      excludes** ``RECONCILED`` (never re-arrived at), so "restart as knowledge of a
      specific state" is unrepresentable (line 199; §11 line 175). Intent and Attempt
      are preserved.

    The result is a fresh DRAFT observation (no digest / id yet) whose dimensions are
    never less conservative than ``pre``'s.

    Args:
        pre: The pre-restart composite observation.

    Returns:
        A new conservative :class:`CompositeState` (DRAFT).
    """
    post_capacity = pre.capacity_state
    if pre.transmission_attempt_state in _ATTEMPT_POTENTIALLY_LIVE_AFTER_RESTART:
        if not capacity_at_least_as_conservative(
            pre.capacity_state, CapacityState.POTENTIALLY_LIVE
        ):
            post_capacity = CapacityState.POTENTIALLY_LIVE

    if (
        pre.broker_order_state in _BROKER_STRUCTURALLY_TERMINAL
        or pre.broker_order_state is BrokerOrderState.UNKNOWN
    ):
        post_broker = pre.broker_order_state
    else:
        post_broker = BrokerOrderState.UNKNOWN

    if pre.knowledge_state in _KNOWLEDGE_DOWNGRADE_ON_RESTART:
        post_knowledge = KnowledgeState.CONFLICTED
    else:
        post_knowledge = pre.knowledge_state

    return CompositeState(
        intent_identity=pre.intent_identity,
        intent_state=pre.intent_state,
        transmission_attempt_state=pre.transmission_attempt_state,
        broker_order_state=post_broker,
        knowledge_state=post_knowledge,
        capacity_state=post_capacity,
        state_model_version=pre.state_model_version,
    )
