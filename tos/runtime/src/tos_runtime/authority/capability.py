"""``capability_valid`` — the Safety Authority capability-validity runtime call"""

from __future__ import annotations

from tos.authority import CapabilityValidityInputs, SafetyAuthorityCapability
from tos.authority import permissive_capability_valid as _permissive_capability_valid

from tos_runtime.authority.epoch import SafetyAuthorityEpochService

__all__ = ["capability_valid"]


def capability_valid(
    capability: SafetyAuthorityCapability,
    *,
    epoch_service: SafetyAuthorityEpochService,
    revocation_status: str | None,
    superseded: bool | None,
    consumed: bool | None,
    issuer_key_status: str | None,
    environment_and_mode_matches: bool | None,
    dominating_restriction: bool = False,
    lease_ok: bool = False,
) -> bool:
    """Whether ``capability`` may be accepted right now (ADR-002-003 §5.2)."""
    state = epoch_service.current_state()
    witness = epoch_service.witness()
    inputs = CapabilityValidityInputs(
        currentness=witness,
        revocation_status=revocation_status,
        superseded=superseded,
        consumed=consumed,
        issuer_key_status=issuer_key_status,
        environment_and_mode_matches=environment_and_mode_matches,
        dominating_restriction=dominating_restriction,
    )
    return _permissive_capability_valid(capability, state, inputs, lease_ok)
