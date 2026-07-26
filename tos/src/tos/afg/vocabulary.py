"""Action-Flow-Governance vocabulary — the action-flow-axis StrEnums (design #16 §2.2).

Spec terms = code terms (design #16 §2; boundary design #1 §2.4). The enums are authored
**verbatim** from ADR-002-022 (§1/§5.4 decision result, §9 action classes, §10 scopes,
§5.6 vector dimensions, §19 material-change kinds). These are the **action-flow resource**
axis; they are a distinct coordinate system from the rcl ``DimensionDescriptor`` (economic
capacity axis, ``vector.py:39``), the are ``RiskDimensionKind`` (aggregate-risk axis —
``BROKER_ACTION_RATE_PROTECTIVE_RESERVE`` there is the *economic view* of action rate, not
the afg resource view), the protective ``GuaranteeLevel`` (reserve-classification axis),
and the spg ``ConfigArtifactKind`` (bundle-member axis). Token overlap is intentional (the
ADR uses the same word on several axes), so coordinate non-collapse rests on **distinct
types + non-import** (design #16 §2.2-5): afg imports none of those sibling axes (only
``CapacityVector`` from rcl, for the final action-flow vector), so a value from one can
never be coerced onto another.

Gap-1 (dimension-id disjointness). ``CapacityVector.dimension_id`` is a free string and
``aggregate_usage`` / ``effective_limit`` match on string equality, so the self-consistency
condition of the REUSE justification ("no coordinate collapse") is that the **afg
action-flow dimension-id set is disjoint from the economic dimension-id set**. This module
fixes the afg half of that contract: an afg dimension id **is** an
:class:`ActionFlowDimensionKind` value (:data:`ACTION_FLOW_DIMENSION_IDS`), every token of
which names an action-flow *resource*, never an economic magnitude. The global namespace
convention across the four ``CapacityVector`` consumers (rcl / are / ioc / afg) is a
Phase-0 follow-up (design #16 §2.2-5 / §10.3-6); the disjointness itself is a §7 core
property test.

This module names **no** concrete broker (broker-agnostic — project memory
``tos-spec-broker-agnostic``; design #16 §0.1) and hardcodes **no** numeric rate, burst,
queue size, age, or amplification bound (ADR §4 non-scope line 105): every such value is
an injected ``CanonicalDecimal`` / ``int`` parameter (design #16 §8). A dimension kind is
the structural axis, never a limit.

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #16 §0.3).
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

__all__ = [
    "ActionFlowResult",
    "ActionClassKind",
    "ActionFlowScopeKind",
    "ActionFlowDimensionKind",
    "DocumentedScopeStatus",
    "MaterialChangeKind",
    "ACTION_CLASS_CONSERVATISM_ORDER",
    "ACTION_FLOW_SCOPE_BREADTH_ORDER",
    "ACTION_FLOW_DIMENSION_IDS",
    "MATERIAL_CHANGE_KINDS",
    "RESERVED_GUARANTEE_TOKENS",
    "ADMISSIBILITY_ADMISSIBLE",
    "ATTEMPT_STATE_SENT_UNCONFIRMED",
    "ATTEMPT_STATE_SEND_FAILED_PROVEN",
    "BROKER_ORDER_STATE_CANCELLED",
    "BROKER_ORDER_STATE_UNKNOWN",
    "action_flow_dimension_id",
    "is_action_flow_dimension_id",
    "broadest_scope",
    "narrowest_scope",
    "most_conservative_action_class",
]


class ActionFlowResult(StrEnum):
    """The three action-flow decision results (ADR-002-022 §1 line 15 / §5.4 line 125).

    §5.4 line 125 verbatim: an Action Flow Decision carries a result of ``GRANT``,
    ``DENY``, or ``UNKNOWN``. A ``GRANT`` "is not capacity or permission to send" and
    "authorizes only an exact RCL allocation request" (§1 line 17; AFG-INV-011).
    ``UNKNOWN`` is **not** permissive — it "consumes conservative capacity and blocks new
    normal risk" (AFG-INV-007 line 181), so a consumer treats it as most-restrictive,
    never as a soft pass. There is deliberately **no** "assume-grant" construction path
    (design #16 §4.1 — the structural seal against the #6 fail-open lesson).

    **Truthy-sentinel seal (design #16 §2.2-1).** ``ActionFlowResult`` is a ``StrEnum``,
    so **every** member — including ``DENY`` and ``UNKNOWN`` — is *truthy*. A consuming
    gate SHALL therefore test ``result is ActionFlowResult.GRANT`` (identity); a bare
    ``if result:`` would let ``DENY`` / ``UNKNOWN`` through (the #13 ARE UNKNOWN-truthy
    lesson; the orthostate ``is True`` normalization ``predicates.py:461`` precedent).
    """

    GRANT = "GRANT"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class ActionClassKind(StrEnum):
    """The 9 governed action classes (ADR-002-022 §9 line 258-266 verbatim).

    §9 line 268: classification "creates no admissibility, risk capacity, protective
    capacity, authority, or broker permission", and "the more conservative applicable
    class and vector govern when classification conflicts" — an exit can zero-cross /
    reverse / overlap, a cancel can remove protection, and a query / reconnect can exhaust
    a shared resource, so a *less* risky-sounding label never buys a more permissive
    class (§7 line 218 "Producer label cannot create a more permissive class").

    Counting spans **every** class, not just submissions: cancel / amend / replace /
    query / session / reconnect / SDK retry are all counted (§9 line 254; rejected
    alternative §25.6 line 526).
    """

    NORMAL_NEW_RISK = "NORMAL_NEW_RISK"
    ORDINARY_REDUCE_OR_EXIT = "ORDINARY_REDUCE_OR_EXIT"
    SAFETY_PROTECTIVE = "SAFETY_PROTECTIVE"
    CANCEL_OR_REPLACE = "CANCEL_OR_REPLACE"
    RECONCILIATION_QUERY = "RECONCILIATION_QUERY"
    SESSION_OR_CONNECTION_CONTROL = "SESSION_OR_CONNECTION_CONTROL"
    HALT_SUPPORT = "HALT_SUPPORT"
    RECOVERY_NON_LIVE = "RECOVERY_NON_LIVE"
    ADMINISTRATIVE_NON_LIVE = "ADMINISTRATIVE_NON_LIVE"


#: §9 declaration order read as **most-conservative first** (design #16 §6.3). A
#: structural convention, never a numeric weight: ``NORMAL_NEW_RISK`` is the
#: hardest-governed class (it creates new normal risk, §1 line 25), and the tail classes
#: are progressively less risk-creating. When several classes apply, the *earliest* member
#: of this tuple governs (§9 line 268 "the more conservative applicable class ... govern").
ACTION_CLASS_CONSERVATISM_ORDER: tuple[ActionClassKind, ...] = tuple(ActionClassKind)


class ActionFlowScopeKind(StrEnum):
    """The 17 action-flow limit scopes (ADR-002-022 §10 line 274 verbatim).

    §10 line 274 gives the fuller list (§1 line 25 is a subset). ``CAUSE`` is the §10
    ``cause`` scope, which is the same scope §1 line 25 calls "originating event" — one
    scope under two spellings, unified here (design #16 §2.2-3, m7), not two members.

    **Two conservative rules (design #16 C1 — the fail-open direction seal).** They point
    in opposite directions and must not be conflated:

    1. *Unknown dependency or limit scope* expands to the **smallest** conservative
       containing scope and blocks new normal risk (§1 line 25).
    2. *Broker-documented scope that is incomplete / contradictory / stale / unverified*
       makes the limit "treated as shared across the **largest** credible containing
       scope" (§10 line 276) — sharing the limit as widely as credible is the
       conservative direction there.

    §10 line 278: separate processes / nodes / regions / local counters are **not**
    independent capacity; independence needs allocation / refill / broker-enforcement /
    failure-domain / final-route separation *evidence*.

    A distinct type from the rcl / are / protective / spg scope coordinates (design #16
    §2.2-5); non-collapse rests on distinct types + non-import.
    """

    GLOBAL = "GLOBAL"
    ENVIRONMENT = "ENVIRONMENT"
    SAFETY_CELL = "SAFETY_CELL"
    BROKER = "BROKER"
    LEGAL_PORTFOLIO = "LEGAL_PORTFOLIO"
    ACCOUNT = "ACCOUNT"
    CREDENTIAL = "CREDENTIAL"
    SESSION = "SESSION"
    CONNECTION_POOL = "CONNECTION_POOL"
    ROUTE = "ROUTE"
    ENDPOINT = "ENDPOINT"
    VENUE = "VENUE"
    INSTRUMENT = "INSTRUMENT"
    STRATEGY = "STRATEGY"
    INTENT = "INTENT"
    CAUSE = "CAUSE"
    ACTION_CLASS = "ACTION_CLASS"


#: §10 line 274 declaration order read as **broadest containing scope first** (design #16
#: §5.1 C1). A structural containment convention, never a numeric weight: ``GLOBAL``
#: contains everything, ``ACTION_CLASS`` is the narrowest named scope. The C1 rules pick
#: the **first** member (largest) for an incomplete broker document and the **last**
#: member (smallest) for an unknown dependency scope.
ACTION_FLOW_SCOPE_BREADTH_ORDER: tuple[ActionFlowScopeKind, ...] = tuple(
    ActionFlowScopeKind
)


class ActionFlowDimensionKind(StrEnum):
    """The named action-flow vector dimensions (ADR-002-022 §5.6 line 133; design §2.2-4).

    The Action Flow Vector is multi-dimensional over broker request / order / mutation /
    cancel / query / session / connection / credential / route / endpoint / queue /
    in-flight / cause-amplification resources. The member set is the §5.6 line 133
    definition **unioned** with §8 line 238 ``orders`` (submission is not mutation) and
    §21 line 439 ``connection`` (a connection is not a session) — v1.0's "§8 line 238
    verbatim" attribution was corrected in v1.1 (M5): those three lists differ and §8:238
    is an open "including ..." example, not a closed universe.

    **This enum is therefore a named minimum set, not a closed universe.** An unenumerated
    dimension is representable as a free ``CapacityVector.dimension_id`` string, and the
    consuming afg predicates fail **closed** on it (unknown dimension => ``UNKNOWN``,
    design #16 §4.1/§2.2-4) — see :func:`is_action_flow_dimension_id`.

    Each dimension carries an exact unit / scope / measurement point / aggregation /
    window-or-refill / burst / max-debt / failure-response (§12 line 302); every one of
    those values is **injected** (design #16 §8), none is hardcoded here.
    """

    BROKER_REQUEST = "BROKER_REQUEST"
    ORDER = "ORDER"
    ORDER_MUTATION = "ORDER_MUTATION"
    CANCEL_AMEND_REPLACE = "CANCEL_AMEND_REPLACE"
    QUERY = "QUERY"
    SESSION = "SESSION"
    CONNECTION = "CONNECTION"
    CREDENTIAL = "CREDENTIAL"
    ROUTE = "ROUTE"
    ENDPOINT = "ENDPOINT"
    QUEUE = "QUEUE"
    IN_FLIGHT = "IN_FLIGHT"
    CAUSE_AMPLIFICATION = "CAUSE_AMPLIFICATION"


#: The afg half of the Gap-1 dimension-id namespace contract (design #16 §2.2-5): an afg
#: action-flow dimension id **is** an :class:`ActionFlowDimensionKind` value. Every token
#: names an action-flow *resource*, so the set is disjoint from the economic / aggregate-
#: risk dimension-id sets carried on the same ``CapacityVector`` container by rcl / are /
#: ioc. The disjointness is asserted as a §7 core property (afg cannot import those
#: siblings, so the assertion lives in the test lane).
ACTION_FLOW_DIMENSION_IDS: frozenset[str] = frozenset(
    kind.value for kind in ActionFlowDimensionKind
)


class DocumentedScopeStatus(StrEnum):
    """Status of a broker's *documented* limit scope (ADR-002-022 §10 line 276).

    §10 line 276: when a broker documents limits "incompletely" or the documentation is
    contradictory / stale / unverified, the limit is "treated as shared across the largest
    credible containing scope". Only :attr:`VERIFIED_COMPLETE` is a positive status; every
    other member — and ``None``, and any unrecognized token — is non-credible and triggers
    the C1 largest-containing-scope widening (fail-closed, design #16 §5.1).
    """

    VERIFIED_COMPLETE = "VERIFIED_COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    CONTRADICTORY = "CONTRADICTORY"
    STALE = "STALE"
    UNVERIFIED = "UNVERIFIED"


class MaterialChangeKind(StrEnum):
    """The material-change kinds that invalidate a decision / permit (§19 line 413).

    §19 line 413 enumerates the changes that invalidate every affected unclaimed decision
    and permit. §5.10 line 149 verbatim: "Unknown materiality is material" — so an
    unknown / undeclared materiality is treated as material (Gap-7,
    :func:`~tos.afg.state.is_material`), and §17 line 391: a cache / TTL / heartbeat /
    service health / broker connection / prior success / queue position / absence of
    invalidation is **not** a currentness proof.
    """

    POLICY = "POLICY"
    BROKER_LIMIT = "BROKER_LIMIT"
    CONSTRAINT = "CONSTRAINT"
    SESSION = "SESSION"
    CREDENTIAL = "CREDENTIAL"
    ROUTE = "ROUTE"
    ENDPOINT = "ENDPOINT"
    SCOPE_GRAPH = "SCOPE_GRAPH"
    TIME_HEALTH = "TIME_HEALTH"
    QUEUE_IN_FLIGHT = "QUEUE_IN_FLIGHT"
    CAUSE_LINEAGE = "CAUSE_LINEAGE"
    RCL = "RCL"
    PROTECTIVE_RESERVE = "PROTECTIVE_RESERVE"
    CAPABILITY = "CAPABILITY"
    CONSUMER_COMPATIBILITY = "CONSUMER_COMPATIBILITY"


#: The §19 line 413 material-change token set (string form, for injected tokens).
MATERIAL_CHANGE_KINDS: frozenset[str] = frozenset(
    kind.value for kind in MaterialChangeKind
)

# ===========================================================================
# Injected sibling coordinate tokens (design #16 §3.4 — afg imports no sibling)
# ===========================================================================
#
# afg consumes protective / orthostate verdicts as **injected produced values**; it does
# NOT import ``tos.protective`` / ``tos.orthostate`` (§0.3 allowlist = canonical +
# ordering + rcl + self). The tokens below are therefore afg-local *coordinate constants*
# that name the sibling's enum member. Drift between them and the sibling enum is locked
# by the MANDATED test-only seam checks (``test_seam_protective`` / ``test_seam_orthostate``,
# design #16 §3.4(d)/§7), which import the real enums and assert both value equality and
# the full-polarity behaviour (``is Admissibility.ADMISSIBLE`` only; TRAPPED / PROHIBITED /
# ``None`` all deny).

#: protective ``Admissibility.ADMISSIBLE`` (``protective/vocabulary.py:118/137``). The
#: **only** admissible verdict: ``TRAPPED`` / ``PROHIBITED`` / ``None`` all deny (design
#: #16 M2 — the verdict is a 3-token StrEnum, never ``bool | None``, and every member is
#: truthy, so a bare truthiness test would pass ``TRAPPED``).
ADMISSIBILITY_ADMISSIBLE: str = "ADMISSIBLE"

#: protective ``GuaranteeLevel`` members that positively establish a *reservation*
#: (``protective/vocabulary.py:32``; ``is_reserved_guarantee`` ``predicates.py:129``).
#: ``PRIORITIZED_ONLY`` / ``BEST_EFFORT`` / ``UNAVAILABLE`` are **never** reserved (§3.1.4
#: line 144 "A prioritized resource is not a reserved resource"; ADR-002-022 §16 line 372).
RESERVED_GUARANTEE_TOKENS: frozenset[str] = frozenset(
    {"PHYSICALLY_RESERVED", "LOGICALLY_RESERVED"}
)

#: orthostate ``TransmissionAttemptState.SENT_UNCONFIRMED`` (``vocabulary.py:86``) — the
#: attempt stays **potentially live**; a missing ACK / timeout / reset / proxy failure /
#: SDK exception / redirect / rate-limit response never proves non-acceptance (§14 line
#: 350; AFG-INV-008).
ATTEMPT_STATE_SENT_UNCONFIRMED: str = "SENT_UNCONFIRMED"

#: orthostate ``TransmissionAttemptState.SEND_FAILED_PROVEN`` (``vocabulary.py:88``) — the
#: attempt-axis **positive** counterpart: positive evidence the broker did not and cannot
#: accept. The only attempt state from which a governed retry may proceed (§14 line 350).
ATTEMPT_STATE_SEND_FAILED_PROVEN: str = "SEND_FAILED_PROVEN"

#: orthostate ``BrokerOrderState.CANCELLED`` (``vocabulary.py:115``) — a locally observed
#: cancellation. A later valid fill SHALL still be accepted, so a cancel ACK is **not** a
#: Final Quantity Proof (§15 line 358; AFG-INV-009).
BROKER_ORDER_STATE_CANCELLED: str = "CANCELLED"

#: orthostate ``BrokerOrderState.UNKNOWN`` (``vocabulary.py:118``) — first-class, capacity
#: consuming, and never "rejected / cancelled / unfilled / safe-to-retry".
BROKER_ORDER_STATE_UNKNOWN: str = "UNKNOWN"


# ===========================================================================
# Pure vocabulary helpers (no numbers, no clock, no broker)
# ===========================================================================


def action_flow_dimension_id(kind: ActionFlowDimensionKind) -> str:
    """The afg ``CapacityVector.dimension_id`` for ``kind`` (Gap-1 convention).

    The afg dimension-id convention is the identity map onto the
    :class:`ActionFlowDimensionKind` value (design #16 §2.2-5): the token that lands in
    ``CapacityVector.dimension_id`` is exactly the enum value, so the afg id set is
    :data:`ACTION_FLOW_DIMENSION_IDS` and stays disjoint from the economic id sets.

    Args:
        kind: The action-flow dimension kind.

    Returns:
        The dimension-id string to use on an ``ActionFlowVector`` component.
    """
    return kind.value


def is_action_flow_dimension_id(dimension_id: str | None) -> bool:
    """Whether ``dimension_id`` is a governed afg action-flow dimension (§2.2-4).

    ``True`` **only** for a token in :data:`ACTION_FLOW_DIMENSION_IDS`. A ``None`` or an
    unenumerated free string is **not** recognized — the enum is a named minimum set, not
    a closed universe, so an unenumerated dimension is representable but the consuming
    predicate fails **closed** on it (unknown => ``UNKNOWN``, design #16 §4.1/§2.2-4).

    Args:
        dimension_id: The ``CapacityVector`` dimension id (``None`` => ``False``).

    Returns:
        ``True`` iff the id names a governed action-flow dimension.
    """
    if dimension_id is None:
        return False
    return dimension_id in ACTION_FLOW_DIMENSION_IDS


def broadest_scope(scopes: Iterable[ActionFlowScopeKind]) -> ActionFlowScopeKind | None:
    """The **largest** credible containing scope in ``scopes`` (§10 line 276; C1 rule 2).

    Returns the earliest member of :data:`ACTION_FLOW_SCOPE_BREADTH_ORDER` present in
    ``scopes`` — the widest sharing, which is the conservative direction when a broker
    documents its limit scope incompletely / contradictorily / stale / unverified. An
    **empty** set yields ``None`` (no containing scope can be established — fail-closed,
    design #16 §4.7).

    Args:
        scopes: The credible containing scopes (empty => ``None``).

    Returns:
        The broadest scope, or ``None`` when none is credible.
    """
    present = frozenset(scopes)
    for scope in ACTION_FLOW_SCOPE_BREADTH_ORDER:
        if scope in present:
            return scope
    return None


def narrowest_scope(
    scopes: Iterable[ActionFlowScopeKind],
) -> ActionFlowScopeKind | None:
    """The **smallest** conservative containing scope in ``scopes`` (§1 line 25; C1 rule 1).

    Returns the latest member of :data:`ACTION_FLOW_SCOPE_BREADTH_ORDER` present in
    ``scopes`` — the smallest containing scope an unknown dependency / limit scope expands
    to (§1 line 25 "expands to the smallest conservative containing scope and blocks new
    normal risk"). An **empty** set yields ``None`` (fail-closed, design #16 §4.7).

    Args:
        scopes: The credible containing scopes (empty => ``None``).

    Returns:
        The narrowest scope, or ``None`` when none is credible.
    """
    present = frozenset(scopes)
    for scope in reversed(ACTION_FLOW_SCOPE_BREADTH_ORDER):
        if scope in present:
            return scope
    return None


def most_conservative_action_class(
    classes: Iterable[ActionClassKind],
) -> ActionClassKind | None:
    """The most conservative class in ``classes`` (§9 line 268 conflict rule).

    Returns the earliest member of :data:`ACTION_CLASS_CONSERVATISM_ORDER` present in
    ``classes``. An **empty** set yields ``None`` (a vacuous "classified over nothing" is
    not a classification — fail-closed, design #16 §4.7).

    Args:
        classes: The applicable action classes (empty => ``None``).

    Returns:
        The governing (most conservative) class, or ``None`` when none applies.
    """
    present = frozenset(classes)
    for action_class in ACTION_CLASS_CONSERVATISM_ORDER:
        if action_class in present:
            return action_class
    return None
