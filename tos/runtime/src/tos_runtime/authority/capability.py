"""``capability_valid`` — the Safety Authority capability-validity runtime call
(design #40 §5 order 4 item 2).

**This function does not judge.** It assembles a
:class:`~tos.authority.state.CapabilityValidityInputs` from the epoch
service's own log-derived state + online witness (both already fail-closed,
:mod:`tos_runtime.authority.epoch`) and the caller's opaque, injected facts
(issuer-key status, revocation status, consumed/superseded flags, environment
match, dominating restriction, lease validity) — then calls the kernel's own
``tos.authority.permissive_capability_valid`` exactly once. No comparison,
threshold, or admit/deny branch is authored here; every fail-closed judgement
already lives in the kernel predicate (``tos/src/tos/authority/predicates.py``
:199-291).
"""

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
    """Whether ``capability`` may be accepted right now (ADR-002-003 §5.2).

    Args:
        capability: The capability under test.
        epoch_service: The Safety Authority epoch service — supplies both the
            current :class:`~tos.authority.AuthorityEpochState` (via
            :meth:`~tos_runtime.authority.epoch.SafetyAuthorityEpochService.current_state`)
            and the online :class:`~tos.authority.CurrentnessWitness` (via
            :meth:`~tos_runtime.authority.epoch.SafetyAuthorityEpochService.witness`)
            this call folds into ``CapabilityValidityInputs.currentness`` —
            "cache != current" (kernel docstring): the witness is re-verified
            on every call, never reused from a prior check.
        revocation_status: Opaque injected revocation-status token (§18.2);
            this function never verifies a signature or MAC itself.
        superseded: Whether the capability has been superseded.
        consumed: Whether the capability has already been consumed.
        issuer_key_status: Opaque injected issuer-key-status token (§18.2).
        environment_and_mode_matches: Whether the live request's environment
            and mode match the capability's own claim (§18.4).
        dominating_restriction: Whether a dominating restrictive state/
            capability currently applies (§5.3).
        lease_ok: Whether §6.3 ``degraded_lease_valid`` holds — consulted by
            the kernel predicate only for a ``DEGRADED_PROTECTIVE`` capability
            type; irrelevant (and ignored) for every other type.

    Returns:
        ``True`` iff ``tos.authority.permissive_capability_valid`` holds —
        conditions 1-5 of the §1 six-part validity test (never condition 6,
        the final broker-egress independent verification, which is the
        egress gateway's job).
    """
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
