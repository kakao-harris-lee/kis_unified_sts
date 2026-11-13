"""Closed egressgw vocabulary — the verify items, their dispositions, and the outcome enums.

Everything the Order Construction seam and the Broker Egress Gateway dispatch on is a **closed
enumeration** here, inheriting the series' truthy-sentinel discipline (#14 M1 / #19 / #23 / D-E1
``vocabulary.py:59-77``): every verdict-shaped ``StrEnum`` has non-empty string members, so a
bare ``if verdict:`` would read a denial as a pass. :meth:`_NonTruthyStrEnum.__bool__` therefore
**raises**, and every progress gate is an explicit positive identity or a positive membership in
a named closed set — never ``is not DENY`` (design #34 §7).

Three seals live in this module:

1. **The verify list is the contract** (:data:`SEND_VERIFY_ITEMS`, taken from
   RFC-002 §10.8:741-759 in the ADR's own order, less the four plan-S2-a removals and the six
   plan-S2-b folds — :class:`SendVerifyItem`, :data:`FOLDED_VERIFY_ITEMS`). Its per-item
   disposition (:data:`REALIZED_ITEMS` / :data:`PROVISIONAL_ITEMS` / :data:`DEFERRED_ITEMS`) is
   the design §4.1 table, and an import-time anchor proves the three sets **partition** it
   exactly — 4 + 2 + 1 = 7, disjoint, exhaustive. A future item that lands in no set, or in two,
   is an immediate :class:`~tos.canonical.ArtifactIntegrityError` rather than a silently skipped
   verify item (the #23 CUR enum-drift-anchor lesson applied to a verify list).
2. **Admission is a positive closed set, not a negation** (:data:`ADMITTING_VERIFY_OUTCOMES`).
   ``NOT_APPLICABLE`` is a *recorded positive judgement* reachable only under a positively
   established non-broker applicability (design #34 §4.2), never a silent skip — so the two
   admitting members are enumerated explicitly rather than derived from "not DENIED".
3. **No permissive default anywhere.** :class:`BrokerApplicability` carries ``UNKNOWN`` as an
   explicit member that is *not* in the non-broker gate, and :class:`LotRoundingPolicy` has no
   "default" member: an unstated lot policy is a denial, never a silent round (design #34 §3.1).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #34 §0.3).
"""

from __future__ import annotations

from enum import StrEnum

from tos.canonical import ArtifactIntegrityError

__all__ = [
    "ADMITTING_VERIFY_OUTCOMES",
    "DEFERRED_ITEMS",
    "FOLDED_VERIFY_ITEMS",
    "PROVISIONAL_ITEMS",
    "REALIZED_ITEMS",
    "SEND_VERIFY_ITEMS",
    "BrokerApplicability",
    "DerivationOutcome",
    "EffectBasis",
    "LotRoundingPolicy",
    "SendHaltReason",
    "SendVerifyItem",
    "VerifyDisposition",
    "VerifyOutcome",
    "verify_item_number",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that refuses truthiness testing (truthy-sentinel seal, #14 M1 precedent).

    Every member is a non-empty string, so ``if value:`` / ``bool(value)`` would read a *denial*
    as a *pass*. Raising here makes that misuse an immediate ``TypeError`` instead of a silent
    fail-open; consumers must use an explicit positive-identity gate.
    """

    def __bool__(self) -> bool:
        """Reject truthiness outright.

        Raises:
            TypeError: always — use the explicit positive-identity gate instead.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive-identity "
            "gate (e.g. `outcome is VerifyOutcome.SATISFIED`); a bare `if value:` would read a "
            "denial as a pass (design #34 §7)"
        )


class SendVerifyItem(StrEnum):
    """The things the Broker Egress Gateway verifies before a send (RFC-002 §10.8:741-759).

    The RFC's list is 17 items; this enum carries 13 of them, and the gateway judges seven
    (:data:`SEND_VERIFY_ITEMS`; the six plan-S2-b folds are :data:`FOLDED_VERIFY_ITEMS`). Items 7/8/9/10 (Hard Safety
    Envelope versions, safety deviation, safety incident, safety monitoring) went with plan
    S2-a: the safety-mesh services that supplied their flags were removed because their inputs
    were constant in every shipped tenant tree, and monitoring is carried by the MONITORING
    currentness dimension instead.

    **Removal condition for a member of this enum, measured before the S2-a cut.** A
    ``VERIFY_ITEM`` evidence row stores its item as a plain string inside the payload
    JSON; nothing re-validates that string back into this enum (grepped: no
    ``SendVerifyItem(...)``/``VerifyItemVerdict.model_validate`` over stored data), and
    no replay comparison re-derives a verify list. So removing a member leaves every
    already-recorded row's bytes and digest untouched — measured on copies of the four
    live leaves: 128,001/128,001 evidence payloads digest-identical, 2,989/2,989 inbox
    events identical in ``event_id`` and bytes. Note that
    :func:`verify_item_number` renumbers from this tuple, so NEW rows after a removal
    carry different numbers for the items that follow it; old rows keep theirs.

    Named after the RFC's own item text. :data:`SEND_VERIFY_ITEMS` fixes the order and
    :func:`verify_item_number` derives the 1-based number **structurally** from that tuple, so a
    number is never a re-assigned label (the D-E1 ``step_number`` precedent).

    §10.8:741 makes the trigger "before any risk-relevant **or broker-resource-consuming**
    transmission" — the trigger is *not* live/non-live (design #34 §2.2 MAJOR-1), which is why
    the deferred items are gated on :class:`BrokerApplicability` rather than on a live flag.
    """

    VALID_UNUSED_TRANSMISSION_CAPABILITY = "VALID_UNUSED_TRANSMISSION_CAPABILITY"
    MATCHING_INTENT_AND_RESERVATION_IDENTITIES = (
        "MATCHING_INTENT_AND_RESERVATION_IDENTITIES"
    )
    CURRENT_COMMITMENT_EPOCH = "CURRENT_COMMITMENT_EPOCH"
    CURRENT_SAFETY_AUTHORITY_EPOCH = "CURRENT_SAFETY_AUTHORITY_EPOCH"
    VALID_LIVE_SCOPE = "VALID_LIVE_SCOPE"
    ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY = (
        "ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY"
    )
    VENUE_SNAPSHOT_AND_ADMISSIBILITY_DECISION = (
        "VENUE_SNAPSHOT_AND_ADMISSIBILITY_DECISION"
    )
    VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION = (
        "VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION"
    )
    ORDER_CONSTRUCTION = "ORDER_CONSTRUCTION"
    TRADING_APPROVAL = "TRADING_APPROVAL"
    ACTION_FLOW = "ACTION_FLOW"
    CURRENTNESS = "CURRENTNESS"
    ACTUAL_OUTBOUND_CONFORMANCE = "ACTUAL_OUTBOUND_CONFORMANCE"


#: **Plan S2-b folds** — members kept (a ``VERIFY_ITEM`` evidence row carries its item as a
#: plain string, and the persisted-bytes rule keeps every enum member a stored row may name),
#: but no longer judged at the send boundary, because the earlier stage named beside each one
#: already stops the same input in the same synchronous flow (and no verify item ever denied in
#: the 3.45M evidence rows measured on 2026-11-13). Removal condition: none — keep them.
#:
#: * ``MATCHING_INTENT_AND_RESERVATION_IDENTITIES`` — constant: :func:`~tos.egressgw.records.
#:   send_boundary_context` (the only ``SendBoundaryContext`` builder) copies the three
#:   ``reservation_*`` fields from the attempt they were compared against.
#: * ``CURRENT_COMMITMENT_EPOCH`` — currentness: a fenced writer epoch makes the RCL
#:   ``read_linearizable`` the proof issuer runs raise (or the vector absent), so the send stops
#:   at proof issuance / item CURRENTNESS before this item could read it.
#: * ``CURRENT_SAFETY_AUTHORITY_EPOCH`` — the Coordinator precondition (same predicate over the
#:   same epoch service, refusing the tick before step 1) and the SAFETY_AUTHORITY currentness
#:   dimension re-read per send.
#: * ``VENUE_SNAPSHOT_AND_ADMISSIBILITY_DECISION`` — step 3, which folded the same retained
#:   snapshot / decision and halts on anything but ADMISSIBLE.
#: * ``TRADING_APPROVAL`` — step 4 (independent approval): the consumed flag *is* step 4's ADMIT,
#:   and the intent-binding digest is copied from the same construction it was compared to.
#: * ``ACTION_FLOW`` — step 9 (atomic commit): the commitment flag *is* step 9's ADMIT, and the
#:   permit identity the attempt binds is step 9's own ``bound_identity``.
FOLDED_VERIFY_ITEMS: frozenset[SendVerifyItem] = frozenset(
    {
        SendVerifyItem.MATCHING_INTENT_AND_RESERVATION_IDENTITIES,
        SendVerifyItem.CURRENT_COMMITMENT_EPOCH,
        SendVerifyItem.CURRENT_SAFETY_AUTHORITY_EPOCH,
        SendVerifyItem.VENUE_SNAPSHOT_AND_ADMISSIBILITY_DECISION,
        SendVerifyItem.TRADING_APPROVAL,
        SendVerifyItem.ACTION_FLOW,
    }
)

#: The normative item order (RFC-002 §10.8:741-759, less the four plan-S2-a removals and the
#: six plan-S2-b folds). Tuple order **is** the contract.
SEND_VERIFY_ITEMS: tuple[SendVerifyItem, ...] = (
    SendVerifyItem.VALID_UNUSED_TRANSMISSION_CAPABILITY,
    SendVerifyItem.VALID_LIVE_SCOPE,
    SendVerifyItem.ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY,
    SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION,
    SendVerifyItem.ORDER_CONSTRUCTION,
    SendVerifyItem.CURRENTNESS,
    SendVerifyItem.ACTUAL_OUTBOUND_CONFORMANCE,
)


class VerifyDisposition(StrEnum):
    """How honestly each verify item is realized in slice #1 (design #34 §4.1 表).

    There is deliberately no ``COMPLETE`` member: slice #1 realizes **structure and
    coordinates**, and the design's whole §1.1 declaration is that no currentness / QCC /
    single-use / credential-isolation acceptance is claimed. A disposition label that could read
    as "done" does not exist, so it cannot be claimed.
    """

    #: Verified in slice #1 by a shipped pure sibling predicate over structure / coordinates.
    REALIZED_STRUCTURAL = "REALIZED_STRUCTURAL"
    #: A non-authoritative stand-in for an owning runtime that does not exist yet.
    PROVISIONAL_STAND_IN = "PROVISIONAL_STAND_IN"
    #: Runtime not landed; **broker-applicability conditional** (design #34 §4.2) — required and
    #: therefore UNKNOWN-denying for a broker-reaching / risk-relevant-live send, and explicitly
    #: ``NOT_APPLICABLE`` only for a positively established synthetic non-broker send.
    DEFERRED_APPLICABILITY = "DEFERRED_APPLICABILITY"


#: Design §4.1 — the items verified with real shipped predicates.
REALIZED_ITEMS: frozenset[SendVerifyItem] = frozenset(
    {
        SendVerifyItem.VALID_UNUSED_TRANSMISSION_CAPABILITY,
        SendVerifyItem.ORDER_CONSTRUCTION,
        SendVerifyItem.CURRENTNESS,
        SendVerifyItem.ACTUAL_OUTBOUND_CONFORMANCE,
    }
)

#: Design §4.1 — the items answered by an injected owner-supplied flag.
PROVISIONAL_ITEMS: frozenset[SendVerifyItem] = frozenset(
    {
        SendVerifyItem.ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY,
        SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION,
    }
)

#: Design §4.1 — the broker-applicability-conditional item (N/A only for a synthetic send).
DEFERRED_ITEMS: frozenset[SendVerifyItem] = frozenset(
    {
        SendVerifyItem.VALID_LIVE_SCOPE,
    }
)


class VerifyOutcome(_NonTruthyStrEnum):
    """One verify item's judgement (design #34 §4.2).

    ``SATISFIED`` is the ordinary positive pass. ``NOT_APPLICABLE`` is **also** a positive,
    recorded judgement — the design's §4.2 broker-applicability gate makes an explicit N/A the
    opposite of a silent skip — but it is reachable only for a
    :data:`VerifyDisposition.DEFERRED_APPLICABILITY` item under a positively established
    :attr:`BrokerApplicability.NON_BROKER_SYNTHETIC` send. ``UNKNOWN`` is restrictive and stays
    distinguishable from ``DENIED`` in the recorded evidence (RFC-005 §11:325-327).
    """

    SATISFIED = "SATISFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"
    DENIED = "DENIED"


#: The **positive closed set** of admitting outcomes (design #34 §4.2 / §7). The gate is
#: ``outcome in ADMITTING_VERIFY_OUTCOMES`` — a positive membership, never ``is not DENIED``,
#: which would fail open on ``None`` and on any future member.
ADMITTING_VERIFY_OUTCOMES: frozenset[VerifyOutcome] = frozenset(
    {VerifyOutcome.SATISFIED, VerifyOutcome.NOT_APPLICABLE}
)


class BrokerApplicability(_NonTruthyStrEnum):
    """Whether this send consumes a broker resource (design #34 §2.2 / §4.2 — the axis).

    RFC-002 §10.8:741 triggers the verify list on a "risk-relevant **or**
    broker-resource-consuming" transmission, so the axis that decides whether the deferred
    safety-governance mesh is *required* is **broker-reached / synthetic**, not live / non-live
    (design #34 MAJOR-1: a real paper-account API call is non-live and still broker-consuming).

    ``UNKNOWN`` is an explicit member and is **not** in the non-broker gate: an unestablished
    transport nature is conservatively treated as broker-consuming (fail-closed, §4.2).
    """

    BROKER_RESOURCE_CONSUMING = "BROKER_RESOURCE_CONSUMING"
    NON_BROKER_SYNTHETIC = "NON_BROKER_SYNTHETIC"
    UNKNOWN = "UNKNOWN"


class SendHaltReason(StrEnum):
    """Why the send boundary stopped (design #34 §4.2 "중단 사유 기록").

    A halt is always recorded **with** its reason: a restrictive termination without a recorded
    reason is a silent stop, not a fail-closed one (the D-E1 ``HaltReason`` discipline).
    """

    CONTEXT_MISSING = "CONTEXT_MISSING"
    ATTEMPT_ALREADY_CONSUMED = "ATTEMPT_ALREADY_CONSUMED"
    #: The scalars about to cross the transport seam are not the ones step 2 derived, or the
    #: outbound request does not carry the exact compiled command digest (design #34 §4.4 /
    #: RFC-005 §7:213).
    OUTBOUND_NOT_BOUND_TO_CONSTRUCTION = "OUTBOUND_NOT_BOUND_TO_CONSTRUCTION"
    VERIFY_ITEM_DENIED = "VERIFY_ITEM_DENIED"
    VERIFY_ITEM_UNKNOWN = "VERIFY_ITEM_UNKNOWN"
    VERIFY_LIST_INCOMPLETE = "VERIFY_LIST_INCOMPLETE"
    BROKER_APPLICABILITY_UNRESOLVED = "BROKER_APPLICABILITY_UNRESOLVED"
    SINGLE_USE_CLAIM_REFUSED = "SINGLE_USE_CLAIM_REFUSED"
    TRANSPORT_UNAVAILABLE = "TRANSPORT_UNAVAILABLE"
    TRANSPORT_RAISED = "TRANSPORT_RAISED"
    #: Reserved for decoding existing evidence. New coordinate failures occur while building the
    #: pre-claim seal and use :attr:`SEND_SEAL_UNCONSTRUCTABLE` instead.
    OUTBOUND_COORDINATE_DERIVATION_RAISED = "OUTBOUND_COORDINATE_DERIVATION_RAISED"
    #: The pre-``SEND_STARTED`` :class:`~tos.egressgw.seal.SendSeal` could not be built — a
    #: required fact was absent from the send-boundary context, or the assembled seal failed its
    #: own construction-time validation (coordinate mismatch, diverging claim/active principal).
    #: Recorded **before** the step-16 claim, so nothing is consumed.
    SEND_SEAL_UNCONSTRUCTABLE = "SEND_SEAL_UNCONSTRUCTABLE"
    #: The transport call itself succeeded (``send_once`` returned), but the result object it
    #: returned could not be read — an attribute access on ``result`` (identity, kind, fill
    #: magnitudes) raised. Handled the same way ``TRANSPORT_RAISED`` is: the send already
    #: happened and is never repeated, and the reservation stays POTENTIALLY_LIVE
    #: (UNKNOWN-restrictive, §4.2 "unknown preserves capacity, deny").
    RESULT_UNREADABLE = "RESULT_UNREADABLE"
    RESULT_ATTEMPT_IDENTITY_MISMATCH = "RESULT_ATTEMPT_IDENTITY_MISMATCH"


class DerivationOutcome(_NonTruthyStrEnum):
    """Whether the G5 quantity / price derivation produced a value (design #34 §3.1).

    There are exactly two members and **no** "defaulted" / "repaired" / "best effort" member:
    RFC-005 §7:211-213 forbids inventing, defaulting, normalizing, rounding, or repairing any
    broker-command field, so a derivation that cannot compute an exact bounded value is
    ``DENIED`` — the outcome vocabulary makes a silent fallback unrepresentable (the Q-MIC-3
    seal, design #34 §13).
    """

    DERIVED = "DERIVED"
    DENIED = "DENIED"


class LotRoundingPolicy(StrEnum):
    """The **authored, explicit** lot policy the derivation must follow (design #34 §3.1).

    There is no default member. RFC-005 §7:211 forbids rounding a broker-command field, so the
    only admissible rounding is one an authored policy states outright:

    * ``EXACT_MULTIPLE_REQUIRED`` — the raw derived size must already be an exact multiple of the
      lot; anything else is a denial (never a silent adjustment);
    * ``FLOOR_TO_LOT`` — the authored, risk-reducing floor to the next lower whole lot, stated in
      policy and therefore not "silent".

    An absent policy (``None`` at the call site) is a denial, not a fallback to either member.
    """

    EXACT_MULTIPLE_REQUIRED = "EXACT_MULTIPLE_REQUIRED"
    FLOOR_TO_LOT = "FLOOR_TO_LOT"


class EffectBasis(StrEnum):
    """How one Economic Effect Envelope dimension's magnitude is derived (design #34 §3.2 step 5).

    The basis is **declared per dimension by injected policy** and the magnitude is then computed
    from the derived order size — never self-reported by the proposal (구조 파생 > 자기신고).
    """

    QUANTITY = "QUANTITY"
    NOTIONAL = "NOTIONAL"


#: The 1-based RFC-002 §10.8 item numbers, derived structurally from :data:`SEND_VERIFY_ITEMS`.
_ITEM_NUMBERS: dict[SendVerifyItem, int] = {
    item: number for number, item in enumerate(SEND_VERIFY_ITEMS, start=1)
}


def verify_item_number(item: SendVerifyItem) -> int:
    """Return this gateway's 1-based verify-list number for ``item``.

    Derived structurally from :data:`SEND_VERIFY_ITEMS`, so it renumbers with the tuple (plan
    S2-a removed four items and S2-b folded six; old rows keep the numbers they were written
    with).

    Args:
        item: The verify item.

    Returns:
        The 1-based normative item number.

    Raises:
        ArtifactIntegrityError: If ``item`` is not a member of the normative list — an item
            outside the closed set is not a verify item (fail-closed, design #34 §4.1).
    """
    number = _ITEM_NUMBERS.get(item)
    if number is None:
        raise ArtifactIntegrityError(
            f"{item!r} is not one of the RFC-002 §10.8:741-759 verify-list items this "
            "gateway carries"
        )
    return number


def _verify_disposition_partition_anchor() -> None:
    """Prove the three disposition sets **partition** the verify items (drift anchor).

    The #23 CUR enum-drift-anchor lesson applied to a verify list: an item that belongs to no
    disposition set would be silently skipped by the gateway loop (a fail-open), and an item in
    two sets would be judged twice under contradictory rules. Both are import-time errors here,
    so the design §4.1 table and the code cannot drift apart unnoticed.

    Raises:
        ArtifactIntegrityError: If the sets are not disjoint, not exhaustive, or the wrong sizes.
    """
    declared = set(SEND_VERIFY_ITEMS)
    if declared != set(SendVerifyItem) - FOLDED_VERIFY_ITEMS:
        raise ArtifactIntegrityError(
            "SEND_VERIFY_ITEMS is not exactly the unfolded SendVerifyItem membership — the "
            "normative order must enumerate every item exactly once (RFC-002 §10.8:741-759)"
        )
    if len(SEND_VERIFY_ITEMS) != len(declared):
        raise ArtifactIntegrityError("SEND_VERIFY_ITEMS repeats an item")
    overlaps = (
        (REALIZED_ITEMS & PROVISIONAL_ITEMS)
        | (REALIZED_ITEMS & DEFERRED_ITEMS)
        | (PROVISIONAL_ITEMS & DEFERRED_ITEMS)
    )
    if overlaps:
        raise ArtifactIntegrityError(
            f"verify-item dispositions overlap for {sorted(overlaps)} — one item, one disposition"
        )
    union = REALIZED_ITEMS | PROVISIONAL_ITEMS | DEFERRED_ITEMS
    missing = declared - union
    if missing:
        raise ArtifactIntegrityError(
            f"verify items {sorted(missing)} carry no disposition — an undisposed verify item "
            "would be skipped by the gateway loop (design #34 §4.1)"
        )
    sizes = (len(REALIZED_ITEMS), len(PROVISIONAL_ITEMS), len(DEFERRED_ITEMS))
    if sizes != (4, 2, 1):
        raise ArtifactIntegrityError(
            f"verify-item disposition counts drifted from the design §4.1 table 4/2/1: {sizes}"
        )


_verify_disposition_partition_anchor()
