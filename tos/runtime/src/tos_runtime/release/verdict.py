"""The release-admission verdict: the one piece of the retired kernel ``tos.sci`` package"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "AdmissionResult",
    "ReleaseRestriction",
    "software_deployment_ok_verdict",
]


class AdmissionResult(StrEnum):
    """``ADMIT`` / ``DENY`` / ``UNKNOWN`` for one deployed artifact."""

    ADMIT = "ADMIT"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"

    def __bool__(self) -> bool:
        raise TypeError(
            "AdmissionResult is not truthy-testable — use `x is AdmissionResult.ADMIT`"
        )


@dataclass(frozen=True)
class ReleaseRestriction:
    """An active release restriction from the operator config (its presence denies)."""

    restriction_id: str
    restriction_generation: int
    trigger_class: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.restriction_id, str) or not self.restriction_id:
            raise ValueError(
                "ReleaseRestriction.restriction_id must be a non-empty str"
            )
        if isinstance(self.restriction_generation, bool) or not isinstance(
            self.restriction_generation, int
        ):
            raise ValueError("ReleaseRestriction.restriction_generation must be an int")
        if self.trigger_class is not None and not isinstance(self.trigger_class, str):
            raise ValueError("ReleaseRestriction.trigger_class must be a str or None")


def software_deployment_ok_verdict(
    admission_result: AdmissionResult | None,
    runtime_attestation_matches: bool | None,
    active_currentness_current: bool | None,
    restriction_present: bool | None,
    restriction_state_resolved: bool | None,
) -> bool:
    """``True`` only when the restriction lookup resolved, the admission is ``ADMIT``, the"""
    if restriction_state_resolved is not True:
        return False
    if admission_result is not AdmissionResult.ADMIT:
        return False
    return (
        runtime_attestation_matches is True
        and active_currentness_current is True
        and restriction_present is False
    )
