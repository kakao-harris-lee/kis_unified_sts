"""Venue / tradability / admissibility vocabulary — the venue-axis StrEnums (design #19 §2.2)."""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "OrderAdmissibilityResult",
    "TradabilityState",
    "ActionClass",
    "ConstraintClass",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #19 §2.2(1)/§4.7/M1)."""

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #19 §2.2(1)/M1)."""
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `result is OrderAdmissibilityResult.ADMISSIBLE`; "
            "`state is TradabilityState.TRADABLE`) per the truthy-sentinel seal "
            "(design #19 §2.2(1)/§4.7/M1). The denial members are non-empty strings and a "
            "bare `if result:` would fail open — and read RESTRICTED_PROTECTIVE_ONLY as "
            "full permission (§0.4d)."
        )


class OrderAdmissibilityResult(_NonTruthyStrEnum):
    """The four order-admissibility results (ADR-002-019 §5.4 line 123 verbatim)."""

    ADMISSIBLE = "ADMISSIBLE"
    RESTRICTED_PROTECTIVE_ONLY = "RESTRICTED_PROTECTIVE_ONLY"
    INADMISSIBLE = "INADMISSIBLE"
    UNKNOWN = "UNKNOWN"


class TradabilityState(_NonTruthyStrEnum):
    """The per-action tradability states (ADR-002-019 §5.6 line 131 / §11 line 283-291)."""

    TRADABLE = "TRADABLE"
    NOT_TRADABLE = "NOT_TRADABLE"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


class ActionClass(StrEnum):
    """The closed order-action taxonomy (ADR-002-019 §11 line 283-289 verbatim — v1.1 M4)."""

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
    """The venue constraint classes (ADR-002-019 §8 line 229-241 — injected classifier token)."""

    SESSION_PHASE = "SESSION_PHASE"
    INSTRUMENT_CONTRACT = "INSTRUMENT_CONTRACT"
    PRICE_TICK_LOT_QUANTITY = "PRICE_TICK_LOT_QUANTITY"
    ORDER_TYPE_TIF = "ORDER_TYPE_TIF"
    ACCOUNT_MARGIN_BORROW_SETTLEMENT = "ACCOUNT_MARGIN_BORROW_SETTLEMENT"
    BROKER_CAPABILITY = "BROKER_CAPABILITY"
    SOURCE_CONTINUITY = "SOURCE_CONTINUITY"
