"""Independent-Proposal-Approval vocabulary — the approval-axis StrEnums (design #15 §2.2)."""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ApprovalResult",
    "ConsumptionStatus",
    "MaterialityVerdict",
    "ConsumptionOutcome",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #15 §2.2(1)/§4.7/M1)."""

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #15 §2.2(1)/M1)."""
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `result is ApprovalResult.APPROVE`; "
            "`status is ConsumptionStatus.ELIGIBLE`) per the truthy-sentinel seal "
            "(design #15 §2.2(1)/§4.7/M1); the denial members are non-empty strings and a "
            "bare `if result:` would fail open."
        )


class ApprovalResult(_NonTruthyStrEnum):
    """The three Independent-Approval decision results (ADR-002-023 §1 line 17 / §11 line 289 verbatim)."""

    APPROVE = "APPROVE"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class ConsumptionStatus(_NonTruthyStrEnum):
    """The single-use decision-consumption states (ADR-002-023 §12 line 302-320)."""

    ELIGIBLE = "ELIGIBLE"
    CONSUMED = "CONSUMED"


class MaterialityVerdict(_NonTruthyStrEnum):
    """Whether an approval-relevant change is material (ADR-002-023 §5.7 line 124-126 / §8 line 230)."""

    MATERIAL = "MATERIAL"
    IMMATERIAL = "IMMATERIAL"
    UNKNOWN = "UNKNOWN"


class ConsumptionOutcome(_NonTruthyStrEnum):
    """The outcome of one single-use consumption attempt (design #15 §6.2; ADR-002-023 §12 line 306-314)."""

    CONSUMED_NEW = "CONSUMED_NEW"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    REJECTED_INELIGIBLE = "REJECTED_INELIGIBLE"
    REJECTED_CONFLICT = "REJECTED_CONFLICT"
    REJECTED_REUSE = "REJECTED_REUSE"
