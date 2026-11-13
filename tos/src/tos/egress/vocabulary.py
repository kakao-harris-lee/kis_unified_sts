"""Egress-boundary vocabulary — the EGRESS-axis StrEnums (design #22 §2.2)."""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "EgressAdmission",
    "CommitProofValidity",
    "RestrictiveLatchState",
    "SignerRole",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #22 §2.2/§4.7/M1)."""

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #22 §2.2/§4.7/M1)."""
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `admission is EgressAdmission.ADMIT`; "
            "`validity is CommitProofValidity.VALID`; `state is RestrictiveLatchState.CLEAR`) "
            "per the truthy-sentinel seal (design #22 §2.2/§4.7/M1). The denial members are "
            "non-empty strings and a bare `if admission:` would fail open — reading DENY / "
            "INVALID / UNKNOWN / DENY_LATCHED as an admission."
        )


class EgressAdmission(_NonTruthyStrEnum):
    """The final egress admission verdict (ADR-002-013 §1/§11.2, non-truthy — critical seal)."""

    ADMIT = "ADMIT"
    DENY = "DENY"


class CommitProofValidity(_NonTruthyStrEnum):
    """The Quorum Commit Certificate validity verdict (ADR-002-013 §11.2, non-truthy)."""

    VALID = "VALID"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class RestrictiveLatchState(_NonTruthyStrEnum):
    """The local restrictive deny-latch state (ADR-002-013 §13/§11.2 step 14, non-truthy)."""

    CLEAR = "CLEAR"
    DENY_LATCHED = "DENY_LATCHED"


class SignerRole(StrEnum):
    """The quorum signer role taxonomy (ADR-002-013 §11.1, closed — leader-vs-quorum axis)."""

    QUORUM_MEMBER = "QUORUM_MEMBER"
    LEADER = "LEADER"
