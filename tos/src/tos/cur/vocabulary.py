"""Currentness-axis vocabulary — the CUR StrEnums (design #23 §2.2)."""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ProofResult",
    "CurrentnessAdmission",
    "DimensionKey",
    "CONDITIONAL_DIMENSION_KEYS",
    "MANDATED_DIMENSION_FLOOR",
    "RETIRED_DIMENSION_KEYS",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #23 §2.2/§4.2)."""

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #23 §2.2/§4.2)."""
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `result is ProofResult.CURRENT`; "
            "`admission is CurrentnessAdmission.ADMIT`) per the truthy-sentinel seal "
            "(design #23 §2.2/§4.2/M1). The denial members are non-empty strings and a bare "
            "`if result:` would fail open — reading RESTRICTED / UNKNOWN / DENY as an admission."
        )


class ProofResult(_NonTruthyStrEnum):
    """The Egress Currentness Proof conformance result (ADR-002-024 §12, non-truthy — critical seal)."""

    CURRENT = "CURRENT"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


class CurrentnessAdmission(_NonTruthyStrEnum):
    """The final currentness admission verdict (ADR-002-024 §13, non-truthy)."""

    ADMIT = "ADMIT"
    DENY = "DENY"


class DimensionKey(StrEnum):
    """The Safety Currentness Vector dimension catalogue (ADR-002-024 §9, closed structural token)."""

    ENVIRONMENT_SCOPE = "ENVIRONMENT_SCOPE"
    CURRENTNESS_POLICY = "CURRENTNESS_POLICY"
    COMMIT_LOG = "COMMIT_LOG"
    SAFETY_AUTHORITY = "SAFETY_AUTHORITY"
    MONITORING = "MONITORING"
    RELEASE = "RELEASE"
    POST_TRADE = "POST_TRADE"
    TRUSTWORTHY_TIME = "TRUSTWORTHY_TIME"
    RECOVERY = "RECOVERY"
    CRITICAL_INPUT = "CRITICAL_INPUT"
    CONTEXT = "CONTEXT"
    CONSTRAINT = "CONSTRAINT"
    CONSTRUCTION = "CONSTRUCTION"
    TRADING_APPROVAL = "TRADING_APPROVAL"
    AGGREGATE_RISK = "AGGREGATE_RISK"
    ACTION_FLOW = "ACTION_FLOW"
    DECISION_PROOF_INTENT = "DECISION_PROOF_INTENT"
    EGRESS_IDENTITY = "EGRESS_IDENTITY"
    RESTRICTED_LIVE_TRIAL = "RESTRICTED_LIVE_TRIAL"


CONDITIONAL_DIMENSION_KEYS: frozenset[DimensionKey] = frozenset(
    {DimensionKey.RESTRICTED_LIVE_TRIAL}
)

RETIRED_DIMENSION_KEYS: frozenset[DimensionKey] = frozenset(
    {
        DimensionKey.CONSTRUCTION,
        DimensionKey.CONSTRAINT,
        DimensionKey.TRADING_APPROVAL,
        DimensionKey.AGGREGATE_RISK,
        DimensionKey.ACTION_FLOW,
        DimensionKey.DECISION_PROOF_INTENT,
        DimensionKey.CONTEXT,
        DimensionKey.CRITICAL_INPUT,
        DimensionKey.EGRESS_IDENTITY,
    }
)

MANDATED_DIMENSION_FLOOR: frozenset[DimensionKey] = (
    frozenset(DimensionKey) - CONDITIONAL_DIMENSION_KEYS - RETIRED_DIMENSION_KEYS
)
