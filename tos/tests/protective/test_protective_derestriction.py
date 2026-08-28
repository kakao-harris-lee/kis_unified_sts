"""§8.5 de-restriction + §8.1-8.4 per-mode + §8.3.1 emergency (design #11 §6.1).

CONTAINED -> DEGRADED_PROTECTIVE is admissible only under all four conditions (not-automatic ∧
affirmative re-establishment ∧ explicit governed decision ∧ no dominating stronger
restriction); any forbidden sole basis (reconnection / elapsed time / ...) keeps CONTAINED.
It is NOT a re-arm — it invokes no liveauth re-arm workflow (design #11 §3.5). SA-EV-* /
FD-EV-* substrate — closes nothing.
"""

from __future__ import annotations

import pytest
from tos.protective import (
    ContainedEmergencyInputs,
    DeRestrictionInputs,
    ProtectiveActionOutcome,
    contained_emergency_admissible,
    derestriction_admissible,
    mode_permits_protective,
)

from ._protective_strategies import admissible_derestriction, admissible_emergency

# ---------------------------------------------------------------------------
# §8.5 de-restriction both-ways
# ---------------------------------------------------------------------------


def test_all_four_conditions_admissible() -> None:
    """(§8.5 canary b) Four conditions positive + not-automatic => admissible (positive side)."""
    assert derestriction_admissible(admissible_derestriction()) is True


_SOLE_BASIS_FLAGS = (
    "elapsed_time_only",
    "connectivity_restored_only",
    "quiet_time_only",
    "cache_agreement_only",
    "absence_of_adverse_signal_only",
)


@pytest.mark.parametrize("flag", _SOLE_BASIS_FLAGS)
def test_forbidden_sole_basis_denies(flag: str) -> None:
    """(§8.5 line 391 canary a) Any forbidden sole basis => CONTAINED retained (deny)."""
    inputs = admissible_derestriction(**{flag: True})
    assert derestriction_admissible(inputs) is False


def test_reconnection_only_does_not_auto_derestrict() -> None:
    """(§8.5 line 391) 'reconnect => auto de-restrict' is blocked."""
    assert (
        derestriction_admissible(
            admissible_derestriction(connectivity_restored_only=True)
        )
        is False
    )


@pytest.mark.parametrize(
    "field",
    [
        "reconciled_authoritative_state",
        "safety_authority_current",
        "hard_and_runtime_profile_valid",
        "critical_input_trust_restored",
        "explicit_safety_authority_decision",
    ],
)
def test_missing_affirmative_or_governed_denies(field: str) -> None:
    """(§8.5 line 402-407) Any affirmative / governed flag None => deny (fail-closed)."""
    for value in (None, False):
        inputs = admissible_derestriction(**{field: value})
        assert derestriction_admissible(inputs) is False


def test_dominating_halt_denies() -> None:
    """(§8.5 canary a) A dominating halt / incident (True or None) => deny."""
    for value in (True, None):
        inputs = admissible_derestriction(dominating_halt_or_incident=value)
        assert derestriction_admissible(inputs) is False


def test_default_derestriction_inputs_are_fail_closed() -> None:
    """(∅ fail-closed) Default (all-None affirmative) de-restriction inputs => deny."""
    assert derestriction_admissible(DeRestrictionInputs()) is False


def test_derestriction_is_not_a_rearm() -> None:
    """(§8.5 line 383-386) The predicate is a plain bool — it invokes NO liveauth re-arm."""
    # Structural: derestriction_admissible has no dual-control / quorum / re-arm parameter;
    # it consumes only the §8.5 governed inputs. A de-restriction grants no new live authority.
    import inspect

    params = set(inspect.signature(derestriction_admissible).parameters)
    assert params == {"inputs"}
    fields = set(DeRestrictionInputs.model_fields)
    for rearm_token in (
        "dual_control",
        "quorum",
        "rearm",
        "principal",
        "live_authorization",
    ):
        assert not any(
            rearm_token in f for f in fields
        ), f"{rearm_token} leaked into de-restriction"


# ---------------------------------------------------------------------------
# §8.1-8.4 mode_permits_protective
# ---------------------------------------------------------------------------


def test_mode_permits_proven_action_within_envelope() -> None:
    """(§8.1-8.4) A known mode + PROTECTIVE_PROVEN + envelope ok => permitted."""
    assert (
        mode_permits_protective(
            2, ProtectiveActionOutcome.PROTECTIVE_PROVEN, envelope_ok=True
        )
        is True
    )


def test_mode_none_denies() -> None:
    """(§8.1-8.4) An unknown mode (None rank) => deny (fail-closed)."""
    assert (
        mode_permits_protective(
            None, ProtectiveActionOutcome.PROTECTIVE_PROVEN, envelope_ok=True
        )
        is False
    )


def test_mode_denies_unproven_action() -> None:
    """(§8.1-8.4) A non-proven classification is not permitted regardless of mode."""
    for outcome in (
        ProtectiveActionOutcome.RISK_INCREASING_DENIED,
        ProtectiveActionOutcome.UNKNOWN_CONSERVATIVE,
    ):
        assert mode_permits_protective(2, outcome, envelope_ok=True) is False


def test_mode_denies_when_envelope_not_ok() -> None:
    """(§8.1-8.4 / §6.6) A None / False envelope => deny."""
    for envelope in (False, None):
        assert (
            mode_permits_protective(
                2, ProtectiveActionOutcome.PROTECTIVE_PROVEN, envelope_ok=envelope
            )
            is False
        )


# ---------------------------------------------------------------------------
# §8.3.1 contained_emergency_admissible
# ---------------------------------------------------------------------------


def test_emergency_all_conjuncts_admissible() -> None:
    """(§8.3.1) All five conjuncts positive => admissible (positive side)."""
    assert contained_emergency_admissible(admissible_emergency()) is True


def test_emergency_not_reduce_only_denies() -> None:
    """(§8.3.1 line 362 canary) reduce-only-by-construction not True => not admissible."""
    for value in (False, None):
        inputs = admissible_emergency(reduce_only_by_construction=value)
        assert contained_emergency_admissible(inputs) is False


def test_emergency_default_fail_closed() -> None:
    """(∅ fail-closed) Default (all-None) emergency inputs => not admissible."""
    assert contained_emergency_admissible(ContainedEmergencyInputs()) is False
