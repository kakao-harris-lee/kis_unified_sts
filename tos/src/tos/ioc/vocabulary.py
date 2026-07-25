"""Intent-to-Order-Conformance vocabulary — the conformance-axis StrEnums (design #14 §2.2).

NOT Immediate-Or-Cancel — ``tos.ioc`` is Intent-to-Order Conformance (ADR-002-020); the ``ioc``
token is a module path, never an order-type value (design #14 §0.4a).

Spec terms = code terms (design #14 §2; boundary design #1 §2.4). The enums are authored
**verbatim** from ADR-002-020 (§14 line 372 decision result, §10-§12 conformance axes,
§11 position effect / quantity units, §12 order types, §16 mutation classes). These are the
**conformance** axis; they are a distinct coordinate system from the rcl ``DimensionDescriptor``
(capacity axis, ``vector.py:39``), the are ``RiskDimensionKind`` (risk axis), the brokercap
``CapabilityDimension`` (broker axis), and the orthostate ``StateDimension`` (state axis). Token
overlap (e.g. "instrument", "account", "venue") is intentional (the ADR uses the same word on
several axes), so coordinate non-collapse rests on **distinct types + non-import** (design #14
§2.3): ioc imports none of those sibling axes (only ``CapacityVector`` from rcl, for the
``EconomicEffectEnvelope`` type), so a value from one can never be coerced onto another.

This module names **no** concrete broker (broker-agnostic — project memory
``tos-spec-broker-agnostic``; design #14 §0.1). The concrete per-broker registry values /
mappings of any one deployment belong to a Phase-0 INSTANCE (ADR §4 non-scope / §28 q3), not
here — a :class:`ConformanceAxis` is the structural axis, never a hardcoded registry value
(§2.2 erratum seal).

Pure module: stdlib only; no ``shared.*`` (design #14 §0.3).
"""

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
    """The three intent-to-order conformance results (ADR-002-020 §14 line 372 verbatim).

    §14 line 372 verbatim: the "final result ``CONFORMANT`` or ``NON_CONFORMANT`` / ``UNKNOWN``".
    ``CONFORMANT`` "grants no approval or authority ... usable only as one current input" (§14
    line 376); ``NON_CONFORMANT`` and ``UNKNOWN`` are **both** denial (§14 line 374 "makes the
    proof ``UNKNOWN`` or ``NON_CONFORMANT`` and blocks authority issuance and transmission").
    Only ``CONFORMANT`` is the safe pass value.

    **Truthy-sentinel structural seal (v1.1 M1, design #14 §2.2(1)/§4.7):** all three members are
    non-empty ``StrEnum`` strings, so ``if result:`` / ``bool(result)`` would read ``NON_CONFORMANT``
    and ``UNKNOWN`` as **truthy** — a catastrophic silent fail-open. :meth:`__bool__` therefore
    **raises** ``TypeError`` on every member, making this a *truthy-untestable* type: a future
    consumer's ``if result:`` misuse surfaces as an immediate runtime error, never a silent pass
    (the only structural defence available in the producer, an upgrade of the #13 prose lesson).
    The mandated consume gate is the explicit positive identity
    ``result is ConformanceResult.CONFORMANT`` — everything else is denial.
    """

    CONFORMANT = "CONFORMANT"
    NON_CONFORMANT = "NON_CONFORMANT"
    UNKNOWN = "UNKNOWN"

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #14 §2.2(1)/M1).

        Raises:
            TypeError: always — ``ConformanceResult`` is not truthy-testable. Use the explicit
                ``result is ConformanceResult.CONFORMANT`` positive-identity gate (§4.7); a bare
                ``if result:`` / ``bool(result)`` would fail open on the truthy ``NON_CONFORMANT``
                / ``UNKNOWN`` strings.
        """
        raise TypeError(
            "ConformanceResult is not truthy-testable — use "
            "`result is ConformanceResult.CONFORMANT` (truthy-sentinel seal, "
            "design #14 §2.2(1)/§4.7/M1); NON_CONFORMANT and UNKNOWN are non-empty "
            "strings and a bare `if result:` would fail open."
        )


class ConformanceAxis(StrEnum):
    """The structural conformance axes (ADR-002-020 §10 line 274-282 / §11 line 292-299 /
    §12 line 311-317 verbatim).

    The **structural axes** conformance is checked over; the concrete per-broker registry values
    / mappings (account / instrument / route / tick / lot / multiplier) are a Phase-0 INSTANCE
    (§28 q3), never enumerated with hardcoded values here (§2.2 erratum seal). A cross-axis
    transformation (currency / multiplier / tick) must be explicit and policy-bound and produce
    one unambiguous mapping (§10 line 284 / §11 line 301) — this enum is only the axis label.
    """

    # §10 identity axes (line 274-282)
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
    # §11 direction / quantity axes (line 292-299)
    DIRECTION = "DIRECTION"
    SIDE = "SIDE"
    POSITION_EFFECT = "POSITION_EFFECT"
    QUANTITY = "QUANTITY"
    UNIT = "UNIT"
    MULTIPLIER = "MULTIPLIER"
    CURRENCY = "CURRENCY"
    PRICE_SCALE = "PRICE_SCALE"
    SIGN = "SIGN"
    # §12 price / order-type / mode axes (line 311-317)
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
    """The position-effect kinds (ADR-002-020 §11 line 294-296 verbatim).

    §11 line 301: "Signed quantity alone is insufficient when broker side and position effect
    are separate fields. A negative value cannot silently flip a side" — so direction / side /
    position effect are **independent** conformance axes (design #14 §5.1 canary).
    """

    OPEN = "OPEN"
    CLOSE = "CLOSE"
    REDUCE_ONLY = "REDUCE_ONLY"


class OrderTypeKind(StrEnum):
    """The order-type kinds (ADR-002-020 §12 line 313 verbatim).

    §12 line 313 verbatim: "market, limit, stop, stop-limit, peg, auction, discretionary,
    conditional, and broker-specific order type". A price improvement / more aggressive price /
    longer expiration / broader route is a **material change** (§12 line 321 "'More likely to
    fill' is not a safety justification").
    """

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
    """The quantity-unit kinds (ADR-002-020 §11 line 297 verbatim).

    §11 line 297 verbatim: "shares, lots, contracts, base/quote units, nominal/notional, face
    value, and fractional units". ``abs`` / clamp / cast / truncation / binary-float /
    scientific-notation / unitless transport is prohibited unless policy-approved (§11 line 301).
    """

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
    """The derived-command mutation classes (ADR-002-020 §16 line 427-437 anchor).

    §16 line 429: "Every broker mutation has its own command identity and proof." Aggregation is
    default-denied (§16 line 437). ``NEW`` and ``SPLIT_CHILD`` are design-derived (not a §16
    "verbatim" token, design #14 §2.2(6) m1); the exercise-family classes anchor to IOC-INV-008
    and the ADR §16 mutation enumeration.
    """

    NEW = "NEW"
    RETRY = "RETRY"
    CANCEL = "CANCEL"
    AMEND = "AMEND"
    REPLACE = "REPLACE"
    SPLIT_CHILD = "SPLIT_CHILD"
    AGGREGATE = "AGGREGATE"
    EXERCISE = "EXERCISE"
