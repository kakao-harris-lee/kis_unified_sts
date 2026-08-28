"""Venue / tradability / admissibility vocabulary — the venue-axis StrEnums (design #19 §2.2).

Spec terms = code terms (design #19 §2; boundary design #1 §2.4). The decision enums are
authored **verbatim** from ADR-002-019 (§5.4 admissibility result, §5.6 tradability state).
These are the **venue-admissibility** axis; they are a distinct coordinate system from the
static-DSL ``dsl.AdmissibilityResult`` / ``dsl.AdmissibilityVerdict``
(``dsl/evidence.py:58`` — ADR-DEV-001 static-program admission, a **homonym** in a different
domain), the ioc ``ConformanceResult`` (intent-to-order conformance axis —
``ioc/vocabulary.py:40``), and the brokercap ``Admissibility`` (capability-ceiling axis). The
non-collapse rests on **distinct types + non-import** (venue imports none of those sibling
axes, sibling edge 0 — design #19 §0.3/§0.4c/§0.4d).

**Truthy-sentinel structural seal (design #19 §2.2(1)/§4.7 — the critical seal, #14 M1
adopted from the start).** Every admissibility / tradability member is a non-empty ``StrEnum``
string, so ``if result:`` / ``bool(result)`` would read a denial value (``INADMISSIBLE`` /
``UNKNOWN`` / ``NOT_TRADABLE``) — and, catastrophically, ``RESTRICTED_PROTECTIVE_ONLY`` — as
**truthy**, a silent fail-open that reads *protective-only* as *full permission* (§0.4d — this
is the single largest risk in this package, strictly worse than the ioc 3-value seal). Every
such enum subclasses :class:`_NonTruthyStrEnum`, whose :meth:`~_NonTruthyStrEnum.__bool__`
**raises** ``TypeError``, making them *truthy-untestable*: the misuse surfaces as an immediate
runtime error, never a silent pass. The mandated consume gate is the explicit positive-identity
comparison (``result is OrderAdmissibilityResult.ADMISSIBLE`` /
``state is TradabilityState.TRADABLE``) — everything else is denial;
``RESTRICTED_PROTECTIVE_ONLY`` proceeds only through the separate protective gate
(:func:`~tos.venue.predicates.protective_label_no_bypass`, §6.5). Isomorphic to the ioc
``ConformanceResult`` seal (``ioc/vocabulary.py:63``); authored locally-fresh here (sibling
edge 0 — no ioc import).

``SessionPhase`` is deliberately **not** an enum here: ADR §5.5 line 127 "Names are
policy-defined and never imply permission by themselves", so a hardcoded closed enum would
violate both "names are policy-defined" and the no-hardcoding rule (design #19 §2.2(3)). A
session phase is an **injected opaque token** (``str``) judged only by admitting-set membership
(:func:`~tos.venue.state.session_phase_admits`), never by truthiness. ``ActionClass``, by
contrast, is a **closed** ``StrEnum`` (ADR §11 line 283-289 fixed taxonomy — v1.1 M4).

This module names **no** concrete broker (broker-agnostic — project memory
``tos-spec-broker-agnostic``; design #19 §0.1) and hardcodes **no** numeric tick / lot / band
bound (ADR §4 non-scope line 103): every bound is an injected policy-content value (design #19
§8). An enum member is a structural label, never a limit or a permission.

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #19 §0.3).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "OrderAdmissibilityResult",
    "TradabilityState",
    "ActionClass",
    "ConstraintClass",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #19 §2.2(1)/§4.7/M1).

    Every member is a non-empty string, so a bare ``if result:`` / ``bool(result)`` would
    read a denial member (``INADMISSIBLE`` / ``UNKNOWN`` / ``NOT_TRADABLE``) — or, worst of
    all, ``RESTRICTED_PROTECTIVE_ONLY`` — as truthy, a catastrophic silent fail-open that
    reads protective-only as full permission. :meth:`__bool__` therefore raises ``TypeError``
    on every member, so the misuse surfaces as a loud runtime error rather than a silent pass.
    Consumers MUST use the explicit positive-identity gate (``x is ENUM.SAFE_VALUE``).
    Isomorphic to the ioc ``ConformanceResult`` seal (``ioc/vocabulary.py:63``); authored
    locally-fresh here (sibling edge 0, no ioc import — design #19 §0.4d). ``is`` identity,
    ``.value``, hashing, set membership, and ``model_dump`` are all unaffected (none calls
    ``__bool__``).
    """

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #19 §2.2(1)/M1).

        Raises:
            TypeError: always — the enum is not truthy-testable. Use the explicit positive
                identity gate (e.g. ``result is OrderAdmissibilityResult.ADMISSIBLE``;
                ``state is TradabilityState.TRADABLE``); a bare ``if result:`` /
                ``bool(result)`` would fail open on the truthy denial strings — and read
                ``RESTRICTED_PROTECTIVE_ONLY`` as full permission (§0.4d).
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `result is OrderAdmissibilityResult.ADMISSIBLE`; "
            "`state is TradabilityState.TRADABLE`) per the truthy-sentinel seal "
            "(design #19 §2.2(1)/§4.7/M1). The denial members are non-empty strings and a "
            "bare `if result:` would fail open — and read RESTRICTED_PROTECTIVE_ONLY as "
            "full permission (§0.4d)."
        )


class OrderAdmissibilityResult(_NonTruthyStrEnum):
    """The four order-admissibility results (ADR-002-019 §5.4 line 123 verbatim).

    §5.4 line 123 verbatim: ``ADMISSIBLE`` / ``RESTRICTED_PROTECTIVE_ONLY`` / ``INADMISSIBLE``
    / ``UNKNOWN``. ADR §1 line 23 verbatim: "``ADMISSIBLE`` means **only** that the exact order
    shape passed the declared constraint checks at the decision point. It does not mean the
    order is economically safe, approved, capacity-covered, currently authorized, accepted by
    the broker, filled, or capable of reducing exposure." So **only** ``ADMISSIBLE`` is an
    ordinary pass. ``RESTRICTED_PROTECTIVE_ONLY`` (§1 line 29 / §19 line 426) permits
    **no ordinary new risk** — only a separately authorized protective action whose current
    restrictive-path constraints are positively proven may proceed; ``INADMISSIBLE`` and
    ``UNKNOWN`` are denial.

    **Truthy-sentinel seal (design #19 §2.2(1)/§4.7 — #14 M1 from the start, more critical
    here):** all four members are non-empty ``StrEnum`` strings, so ``if result:`` /
    ``bool(result)`` would read ``INADMISSIBLE`` / ``UNKNOWN`` **and**
    ``RESTRICTED_PROTECTIVE_ONLY`` as truthy — a catastrophic silent fail-open reading
    protective-only as full permission (worse than the ioc 3-value case). Truthy-untestable
    (``__bool__`` raises). The mandated consume gate is ``result is
    OrderAdmissibilityResult.ADMISSIBLE`` for ordinary new risk; ``RESTRICTED_PROTECTIVE_ONLY``
    proceeds only through :func:`~tos.venue.predicates.protective_label_no_bypass` (§6.5).
    """

    ADMISSIBLE = "ADMISSIBLE"
    RESTRICTED_PROTECTIVE_ONLY = "RESTRICTED_PROTECTIVE_ONLY"
    INADMISSIBLE = "INADMISSIBLE"
    UNKNOWN = "UNKNOWN"


class TradabilityState(_NonTruthyStrEnum):
    """The per-action tradability states (ADR-002-019 §5.6 line 131 / §11 line 283-291).

    §5.6 line 131 verbatim: "``TRADABLE`` is not a global instrument boolean." §11 line 283-291
    requires an exact-action tradability, so this is a **per-action** verdict dimension (new
    long/short, increase/decrease/close/reversal, cancel/amend/replace/reduce-only,
    protective/emergency, routing alternative — §11 line 285-289). §11 line 291 verbatim: "An
    instrument may be quoteable but not orderable, sellable but not shortable, cancellable but
    not replaceable ... A global ``tradable=true`` field is insufficient." The value set is at
    minimum ``TRADABLE`` / ``NOT_TRADABLE`` / ``RESTRICTED`` / ``UNKNOWN`` (the exact
    enumeration is policy-bound, §5.2). Only ``TRADABLE`` is a pass. Truthy-untestable
    (``__bool__`` raises); the mandated consume gate is ``state is TradabilityState.TRADABLE``
    — a single global ``bool`` is forbidden (§11 line 291).
    """

    TRADABLE = "TRADABLE"
    NOT_TRADABLE = "NOT_TRADABLE"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


class ActionClass(StrEnum):
    """The closed order-action taxonomy (ADR-002-019 §11 line 283-289 verbatim — v1.1 M4).

    Unlike :class:`~tos.venue.vocabulary` ``SessionPhase`` (an injected policy-open token, §2.2(3)),
    the action classes are a **fixed, closed** taxonomy: ADR §11 line 283-289 "At minimum ...
    SHALL distinguish" enumerates them, so a closed ``StrEnum`` is correct here (v1.1 M4). A
    **plain** ``StrEnum``: it is an input taxonomy token consumed by identity / set membership
    (:func:`~tos.venue.state.session_phase_admits` / :func:`~tos.venue.predicates.exit_not_assumed_admissible`),
    never a gate result read with ``if action:``, so it does not need the truthy seal (unlike
    the two decision enums above). Per-action tradability is judged separately
    (:class:`TradabilityState`); this enum is only the action label.
    """

    NEW_LONG = "NEW_LONG"
    NEW_SHORT = "NEW_SHORT"
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    CLOSE = "CLOSE"
    REVERSAL = "REVERSAL"
    CANCEL = "CANCEL"
    AMEND = "AMEND"
    REPLACE = "REPLACE"
    REDUCE_ONLY = "REDUCE_ONLY"
    PROTECTIVE = "PROTECTIVE"
    EMERGENCY = "EMERGENCY"
    ROUTING_ALTERNATIVE = "ROUTING_ALTERNATIVE"


class ConstraintClass(StrEnum):
    """The venue constraint classes (ADR-002-019 §8 line 229-241 — injected classifier token).

    §8 line 229-241 groups the constraint domains a Venue Constraint Policy declares:
    session-phase, instrument/contract, price/tick/lot/quantity, order-type/TIF,
    account/margin/borrow/settlement, broker-capability, source-continuity. The policy — not a
    proposer or consumer — determines materiality and precedence (§14 line 345); the concrete
    classifier / precedence is a Phase-0 INSTANCE (§27 q2). A **plain** ``StrEnum`` input
    taxonomy token: venue consumes the classification, it does not re-classify. Compared by
    identity / set membership, never truthiness.
    """

    SESSION_PHASE = "SESSION_PHASE"
    INSTRUMENT_CONTRACT = "INSTRUMENT_CONTRACT"
    PRICE_TICK_LOT_QUANTITY = "PRICE_TICK_LOT_QUANTITY"
    ORDER_TYPE_TIF = "ORDER_TYPE_TIF"
    ACCOUNT_MARGIN_BORROW_SETTLEMENT = "ACCOUNT_MARGIN_BORROW_SETTLEMENT"
    BROKER_CAPABILITY = "BROKER_CAPABILITY"
    SOURCE_CONTINUITY = "SOURCE_CONTINUITY"
