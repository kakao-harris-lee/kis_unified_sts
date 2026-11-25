"""Intent-to-Order-Conformance vocabulary — the conformance-axis StrEnums (design #14 §2.2)."""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ConformanceResult",
    "ConformanceAxis",
    "PositionEffectKind",
    "OrderTypeKind",
    "QuantityUnitKind",
    "MutationClass",
]


class ConformanceResult(StrEnum):
    """The three intent-to-order conformance results (ADR-002-020 §14 line 372 verbatim)."""

    CONFORMANT = "CONFORMANT"
    NON_CONFORMANT = "NON_CONFORMANT"
    UNKNOWN = "UNKNOWN"

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #14 §2.2(1)/M1)."""
        raise TypeError(
            "ConformanceResult is not truthy-testable — use "
            "`result is ConformanceResult.CONFORMANT` (truthy-sentinel seal, "
            "design #14 §2.2(1)/§4.7/M1); NON_CONFORMANT and UNKNOWN are non-empty "
            "strings and a bare `if result:` would fail open."
        )


class ConformanceAxis(StrEnum):
    """The structural conformance axes (ADR-002-020 §10 line 274-282 / §11 line 292-299 /"""

    ENVIRONMENT = "ENVIRONMENT"
    LIVE_NONLIVE = "LIVE_NONLIVE"
    BROKER = "BROKER"
    API_PRODUCT_VERSION = "API_PRODUCT_VERSION"
    ACCOUNT = "ACCOUNT"
    SUBACCOUNT = "SUBACCOUNT"
    PORTFOLIO = "PORTFOLIO"
    CUSTODY = "CUSTODY"
    VENUE = "VENUE"
    MARKET_SEGMENT = "MARKET_SEGMENT"
    BOARD = "BOARD"
    ROUTE = "ROUTE"
    ENDPOINT = "ENDPOINT"
    SESSION_FAMILY = "SESSION_FAMILY"
    INSTRUMENT = "INSTRUMENT"
    BROKER_SYMBOL = "BROKER_SYMBOL"
    CONTRACT_MONTH = "CONTRACT_MONTH"
    OPTION_SERIES = "OPTION_SERIES"
    PRODUCT = "PRODUCT"
    SETTLEMENT = "SETTLEMENT"
    ACTION_CLASS = "ACTION_CLASS"
    DIRECTION = "DIRECTION"
    SIDE = "SIDE"
    POSITION_EFFECT = "POSITION_EFFECT"
    QUANTITY = "QUANTITY"
    UNIT = "UNIT"
    MULTIPLIER = "MULTIPLIER"
    CURRENCY = "CURRENCY"
    PRICE_SCALE = "PRICE_SCALE"
    SIGN = "SIGN"
    PRICE = "PRICE"
    TRIGGER = "TRIGGER"
    ORDER_TYPE = "ORDER_TYPE"
    TIF = "TIF"
    EXPIRATION = "EXPIRATION"
    ROUTE_FLAGS = "ROUTE_FLAGS"
    REDUCE_ONLY = "REDUCE_ONLY"
    POST_ONLY = "POST_ONLY"
    MODE = "MODE"


class PositionEffectKind(StrEnum):
    """The position-effect kinds (ADR-002-020 §11 line 294-296 verbatim)."""

    OPEN = "OPEN"
    CLOSE = "CLOSE"
    REDUCE_ONLY = "REDUCE_ONLY"


class OrderTypeKind(StrEnum):
    """The order-type kinds (ADR-002-020 §12 line 313 verbatim)."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    PEG = "PEG"
    AUCTION = "AUCTION"
    DISCRETIONARY = "DISCRETIONARY"
    CONDITIONAL = "CONDITIONAL"
    BROKER_SPECIFIC = "BROKER_SPECIFIC"


class QuantityUnitKind(StrEnum):
    """The quantity-unit kinds (ADR-002-020 §11 line 297 verbatim)."""

    SHARES = "SHARES"
    LOTS = "LOTS"
    CONTRACTS = "CONTRACTS"
    BASE_UNIT = "BASE_UNIT"
    QUOTE_UNIT = "QUOTE_UNIT"
    NOMINAL = "NOMINAL"
    NOTIONAL = "NOTIONAL"
    FACE_VALUE = "FACE_VALUE"
    FRACTIONAL = "FRACTIONAL"


class MutationClass(StrEnum):
    """The derived-command mutation classes (ADR-002-020 §16 line 427-437 anchor)."""

    NEW = "NEW"
    RETRY = "RETRY"
    CANCEL = "CANCEL"
    AMEND = "AMEND"
    REPLACE = "REPLACE"
    SPLIT_CHILD = "SPLIT_CHILD"
    AGGREGATE = "AGGREGATE"
    EXERCISE = "EXERCISE"
