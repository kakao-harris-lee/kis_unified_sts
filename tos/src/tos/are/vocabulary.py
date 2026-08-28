"""Aggregate-Risk-Evaluation vocabulary — the risk-axis StrEnums (design #13 §2.2).

Spec terms = code terms (design #13 §2; boundary design #1 §2.4). The enums are authored
**verbatim** from ADR-002-021 (§1/§5.5 decision result, §10 risk dimensions / scopes, §11
adverse-scenario kinds, §13 benefit kinds). These are the **aggregate-risk** axis; they are
a distinct coordinate system from the rcl ``DimensionDescriptor`` (capacity axis,
``vector.py:39``), the spg ``EnvelopeVersion`` (safety-config axis), the brokercap
``ProfileVersion`` (broker axis), and the time snapshot (time axis). Token overlap (e.g.
"dimension", "scope", "currency") is intentional (the ADR uses the same word on several
axes), so coordinate non-collapse rests on **distinct types + non-import** (design #13 §4.4):
are imports none of those sibling axes (only ``CapacityVector`` from rcl, for the final
increment type), so a value from one can never be coerced onto another.

This module names **no** concrete broker (broker-agnostic — project memory
``tos-spec-broker-agnostic``; design #13 §0.1). The concrete per-product dimension set /
numeric limits / correlations / scenario values of any one deployment belong to a
non-normative Safety / Verification Profile INSTANCE (ADR §4 non-scope / §28), not here — a
``RiskDimensionKind`` is the structural axis, never a hardcoded numeric limit (§2.2 erratum
seal).

Pure module: stdlib only; no ``shared.*`` (design #13 §0.3).
"""

from __future__ import annotations

from enum import StrEnum


class RiskDecisionResult(StrEnum):
    """The three aggregate-risk decision results (ADR-002-021 §1 line 15 / §5.5 line 132 verbatim).

    §5.5 line 132 verbatim: an Aggregate Risk Decision is "a result of ``GRANT``, ``DENY``, or
    ``UNKNOWN``". A ``GRANT`` "authorizes only an exact RCL allocation request; it creates no
    capacity and permits no send" (§5.5 line 132; ARE-INV-009). ``UNKNOWN`` is **not**
    permissive — it "consumes conservative capacity and blocks new risk" (ARE-INV-006 line
    173), so a consumer treats it as most-restrictive, never as a soft pass. There is
    deliberately **no** "assume-grant" construction path (design #13 §4.1 — the structural
    seal against the #6 fail-open REJECT lesson).
    """

    GRANT = "GRANT"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class RiskDimensionKind(StrEnum):
    """The governed risk-dimension kinds (ADR-002-021 §10 line 270-279 verbatim).

    The **structural axes** of aggregate risk (§10); the concrete per-product / account-class
    dimension set and its numeric limits are a Phase-0 INSTANCE (§28 q2), never enumerated
    with hardcoded magnitudes here (§2.2 erratum seal). ``CONCENTRATION`` spans the §10
    instrument / underlying / issuer / sector / theme / strategy / venue / account /
    legal-portfolio / currency / global sub-axes; a cross-dimension conversion is explicit and
    a Critical Input that "cannot silently default" (§10 line 281).
    """

    GROSS_NOTIONAL = "GROSS_NOTIONAL"
    NET_NOTIONAL = "NET_NOTIONAL"
    LONG_SHORT_DELTA_DIRECTIONAL = "LONG_SHORT_DELTA_DIRECTIONAL"
    CONCENTRATION = "CONCENTRATION"
    LEVERAGE_MARGIN_COLLATERAL = "LEVERAGE_MARGIN_COLLATERAL"
    LIQUIDITY_IMPACT_SLIPPAGE_GAP = "LIQUIDITY_IMPACT_SLIPPAGE_GAP"
    BASIS_CORRELATION_HEDGE_MISMATCH = "BASIS_CORRELATION_HEDGE_MISMATCH"
    OPTION_GREEKS_EXERCISE_ASSIGNMENT = "OPTION_GREEKS_EXERCISE_ASSIGNMENT"
    SETTLEMENT_CASH_CURRENCY = "SETTLEMENT_CASH_CURRENCY"
    LOSS_DRAWDOWN_SURVIVAL = "LOSS_DRAWDOWN_SURVIVAL"
    BROKER_ACTION_RATE_PROTECTIVE_RESERVE = "BROKER_ACTION_RATE_PROTECTIVE_RESERVE"


class RiskScopeKind(StrEnum):
    """The aggregate-risk evaluation scopes (ADR-002-021 §8 line 230 / §10 verbatim).

    §10 line 283 verbatim: "no lower-dimensional projection may pass if an applicable
    higher-dimensional or cross-scope limit is unknown" — local compliance never overrides an
    unsafe aggregate state. A distinct type from the rcl / spg / brokercap scope coordinates
    (design #13 §4.4; token overlap is intentional, non-collapse rests on distinct types +
    non-import).
    """

    ENVIRONMENT = "ENVIRONMENT"
    SAFETY_CELL = "SAFETY_CELL"
    LEGAL_PORTFOLIO = "LEGAL_PORTFOLIO"
    ACCOUNT = "ACCOUNT"
    STRATEGY = "STRATEGY"
    VENUE = "VENUE"
    INSTRUMENT = "INSTRUMENT"
    UNDERLYING = "UNDERLYING"
    ISSUER = "ISSUER"
    SECTOR_THEME = "SECTOR_THEME"
    CURRENCY = "CURRENCY"
    GLOBAL = "GLOBAL"


class AdverseScenarioKind(StrEnum):
    """The credible adverse-scenario kinds (ADR-002-021 §11 line 291-299 verbatim).

    §11 line 291 verbatim: an Adverse Scenario Set "SHALL cover at least" these credible
    families. The set is a **min-coverage floor**, never a whitelist: §5.4 line 128 "Absence
    from the set is not proof that a credible adverse path can be ignored" and §11 line 301
    "Sampling, Monte Carlo count, ... historical absence ... cannot prove that an omitted
    credible tail is harmless" — an empty / under-covering set fails closed (design #13 §4.7).
    The concrete floor a given evaluation requires is **injected** (design #13 §8), never
    hardcoded; this enum is the vocabulary the floor draws from.
    """

    FILL_PREFIX_ORDERING = "FILL_PREFIX_ORDERING"
    OVERLAP_RETRY = "OVERLAP_RETRY"
    MISSING_ACK_RECEIPT_AMBIGUITY = "MISSING_ACK_RECEIPT_AMBIGUITY"
    ZERO_CROSS_REVERSAL_REDUCE_ONLY_FAIL = "ZERO_CROSS_REVERSAL_REDUCE_ONLY_FAIL"
    ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ = "ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ"
    CORRELATION_BASIS_HEDGE_VENUE = "CORRELATION_BASIS_HEDGE_VENUE"
    MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN = (
        "MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN"
    )
    EXTERNAL_TRAPPED_NONTRADE_CONCURRENT = "EXTERNAL_TRAPPED_NONTRADE_CONCURRENT"
    UNAVAILABLE_EXIT_RATELIMIT_PARTITION_RECOVERY = (
        "UNAVAILABLE_EXIT_RATELIMIT_PARTITION_RECOVERY"
    )


class BenefitKind(StrEnum):
    """The claimable risk-benefit kinds (ADR-002-021 §13 verbatim).

    Each benefit reduces adverse capacity **only when positively proven** on all seven §13
    line 336-342 premises (:func:`~tos.are.predicates.benefit_admissible`); missing / stale /
    conflicting / common-mode / unverifiable evidence yields **zero** benefit (§13 line 344;
    ARE-INV-005). A broker margin number, historical correlation, shared model output, recent
    co-movement, strategy label, or human assertion is not sufficient proof (§13 line 344).
    """

    NETTING = "NETTING"
    HEDGE = "HEDGE"
    DIVERSIFICATION = "DIVERSIFICATION"
    COLLATERAL = "COLLATERAL"
    MARGIN_OFFSET = "MARGIN_OFFSET"
    LIQUIDITY = "LIQUIDITY"
    CORRELATION = "CORRELATION"
