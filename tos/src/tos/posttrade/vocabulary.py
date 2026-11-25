"""Post-trade vocabulary — the nine posttrade-axis StrEnums (design #24 §2.2)."""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "EventObligationLegKind",
    "FinalityDimensionKind",
    "ObligationLegDirection",
    "PostTradeObligationLifecycleState",
]


class PostTradeObligationLifecycleState(StrEnum):
    """The 8 + 4 obligation lifecycle states (ADR §10 line 287-301 verbatim; count = 12)."""

    POTENTIAL = "POTENTIAL"
    RECOGNIZED = "RECOGNIZED"
    DUE = "DUE"
    IN_FLIGHT = "IN_FLIGHT"
    PARTIALLY_SATISFIED = "PARTIALLY_SATISFIED"
    SATISFIED_PENDING_FINALITY = "SATISFIED_PENDING_FINALITY"
    FINALITY_PROVEN = "FINALITY_PROVEN"
    CLOSED = "CLOSED"
    BREAK_OPEN = "BREAK_OPEN"
    CORRECTION_PENDING = "CORRECTION_PENDING"
    FAILED_OR_TRAPPED = "FAILED_OR_TRAPPED"
    SUPERSEDED = "SUPERSEDED"


class FinalityDimensionKind(StrEnum):
    """The 10 orthogonal finality dimensions (ADR §6 PTF-INV-002 line 156; count = 10)."""

    ORDER_FQP = "ORDER_FQP"
    TRADE_CAPTURE = "TRADE_CAPTURE"
    INSTRUCTION_ACCEPTANCE = "INSTRUCTION_ACCEPTANCE"
    SETTLEMENT = "SETTLEMENT"
    CASH_AVAILABILITY = "CASH_AVAILABILITY"
    COLLATERAL_ELIGIBILITY = "COLLATERAL_ELIGIBILITY"
    CUSTODY_TITLE = "CUSTODY_TITLE"
    FEE_FINALITY = "FEE_FINALITY"
    BORROW_DISCHARGE = "BORROW_DISCHARGE"
    CORPORATE_ACTION_FINALITY = "CORPORATE_ACTION_FINALITY"


class ObligationLegDirection(StrEnum):
    """The 8 obligation-leg directions (ADR §5.3 line 116 / §9 line 273; count = 8)."""

    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
    DELIVERY = "DELIVERY"
    RECEIPT = "RECEIPT"
    ENCUMBRANCE = "ENCUMBRANCE"
    RELEASE = "RELEASE"
    RETURN = "RETURN"
    CONTINGENT = "CONTINGENT"


class EventObligationLegKind(StrEnum):
    """The 9 event-obligation leg kinds (ADR §17 line 416 verbatim; count = 9)."""

    ASSET = "ASSET"
    CASH = "CASH"
    FEE = "FEE"
    TAX = "TAX"
    FINANCING = "FINANCING"
    MARGIN = "MARGIN"
    BORROW = "BORROW"
    CUSTODY = "CUSTODY"
    DELIVERY = "DELIVERY"
