"""Closed egressgw vocabulary — the verify items, their dispositions, and the outcome enums."""

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
    """A ``StrEnum`` that refuses truthiness testing (truthy-sentinel seal, #14 M1 precedent)."""

    def __bool__(self) -> bool:
        """Reject truthiness outright."""
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive-identity "
            "gate (e.g. `outcome is VerifyOutcome.SATISFIED`); a bare `if value:` would read a "
            "denial as a pass (design #34 §7)"
        )


class SendVerifyItem(StrEnum):
    """The things the Broker Egress Gateway verifies before a send (RFC-002 §10.8:741-759)."""

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
    """How honestly each verify item is realized in slice #1 (design #34 §4.1 表)."""

    REALIZED_STRUCTURAL = "REALIZED_STRUCTURAL"
    PROVISIONAL_STAND_IN = "PROVISIONAL_STAND_IN"
    DEFERRED_APPLICABILITY = "DEFERRED_APPLICABILITY"


REALIZED_ITEMS: frozenset[SendVerifyItem] = frozenset(
    {
        SendVerifyItem.VALID_UNUSED_TRANSMISSION_CAPABILITY,
        SendVerifyItem.ORDER_CONSTRUCTION,
        SendVerifyItem.CURRENTNESS,
        SendVerifyItem.ACTUAL_OUTBOUND_CONFORMANCE,
    }
)

PROVISIONAL_ITEMS: frozenset[SendVerifyItem] = frozenset(
    {
        SendVerifyItem.ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY,
        SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION,
    }
)

DEFERRED_ITEMS: frozenset[SendVerifyItem] = frozenset(
    {
        SendVerifyItem.VALID_LIVE_SCOPE,
    }
)


class VerifyOutcome(_NonTruthyStrEnum):
    """One verify item's judgement (design #34 §4.2)."""

    SATISFIED = "SATISFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"
    DENIED = "DENIED"


ADMITTING_VERIFY_OUTCOMES: frozenset[VerifyOutcome] = frozenset(
    {VerifyOutcome.SATISFIED, VerifyOutcome.NOT_APPLICABLE}
)


class BrokerApplicability(_NonTruthyStrEnum):
    """Whether this send consumes a broker resource (design #34 §2.2 / §4.2 — the axis)."""

    BROKER_RESOURCE_CONSUMING = "BROKER_RESOURCE_CONSUMING"
    NON_BROKER_SYNTHETIC = "NON_BROKER_SYNTHETIC"
    UNKNOWN = "UNKNOWN"


class SendHaltReason(StrEnum):
    """Why the send boundary stopped (design #34 §4.2 "중단 사유 기록")."""

    CONTEXT_MISSING = "CONTEXT_MISSING"
    ATTEMPT_ALREADY_CONSUMED = "ATTEMPT_ALREADY_CONSUMED"
    OUTBOUND_NOT_BOUND_TO_CONSTRUCTION = "OUTBOUND_NOT_BOUND_TO_CONSTRUCTION"
    VERIFY_ITEM_DENIED = "VERIFY_ITEM_DENIED"
    VERIFY_ITEM_UNKNOWN = "VERIFY_ITEM_UNKNOWN"
    VERIFY_LIST_INCOMPLETE = "VERIFY_LIST_INCOMPLETE"
    BROKER_APPLICABILITY_UNRESOLVED = "BROKER_APPLICABILITY_UNRESOLVED"
    SINGLE_USE_CLAIM_REFUSED = "SINGLE_USE_CLAIM_REFUSED"
    TRANSPORT_UNAVAILABLE = "TRANSPORT_UNAVAILABLE"
    TRANSPORT_RAISED = "TRANSPORT_RAISED"
    OUTBOUND_COORDINATE_DERIVATION_RAISED = "OUTBOUND_COORDINATE_DERIVATION_RAISED"
    SEND_SEAL_UNCONSTRUCTABLE = "SEND_SEAL_UNCONSTRUCTABLE"
    RESULT_UNREADABLE = "RESULT_UNREADABLE"
    RESULT_ATTEMPT_IDENTITY_MISMATCH = "RESULT_ATTEMPT_IDENTITY_MISMATCH"


class DerivationOutcome(_NonTruthyStrEnum):
    """Whether the G5 quantity / price derivation produced a value (design #34 §3.1)."""

    DERIVED = "DERIVED"
    DENIED = "DENIED"


class LotRoundingPolicy(StrEnum):
    """The **authored, explicit** lot policy the derivation must follow (design #34 §3.1)."""

    EXACT_MULTIPLE_REQUIRED = "EXACT_MULTIPLE_REQUIRED"
    FLOOR_TO_LOT = "FLOOR_TO_LOT"


class EffectBasis(StrEnum):
    """How one Economic Effect Envelope dimension's magnitude is derived (design #34 §3.2 step 5)."""

    QUANTITY = "QUANTITY"
    NOTIONAL = "NOTIONAL"


_ITEM_NUMBERS: dict[SendVerifyItem, int] = {
    item: number for number, item in enumerate(SEND_VERIFY_ITEMS, start=1)
}


def verify_item_number(item: SendVerifyItem) -> int:
    """Return this gateway's 1-based verify-list number for ``item``."""
    number = _ITEM_NUMBERS.get(item)
    if number is None:
        raise ArtifactIntegrityError(
            f"{item!r} is not one of the RFC-002 §10.8:741-759 verify-list items this "
            "gateway carries"
        )
    return number


def _verify_disposition_partition_anchor() -> None:
    """Prove the three disposition sets **partition** the verify items (drift anchor)."""
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
