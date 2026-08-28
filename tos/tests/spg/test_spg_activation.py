"""Atomic activation + stale-base serialization (design #12 §5.3/§5.4; SPG-EV-004/005).

Both-ways canaries + the ∅/None fail-closed regressions. spg's internal activation_atomic
folds the four seam bools to an ActivationVerdict; the four bools also feed liveauth's fold
(the seam test locks that alignment separately).
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.spg import (
    ActivationVerdict,
    activation_atomic,
    activation_serializable,
)

from ._spg_strategies import (
    committable_activation_inputs,
    issue_activation,
)

# ---------------------------------------------------------------------------
# activation_atomic — both-ways + DEFERRED
# ---------------------------------------------------------------------------


def test_committable_positive_side() -> None:
    """(canary +) All four bools positive + staging/attestation => COMMITTABLE."""
    assert (
        activation_atomic(committable_activation_inputs())
        is ActivationVerdict.COMMITTABLE
    )


def test_mixed_versions_denied() -> None:
    """(canary - SPG-INV-005) mixed_versions_present True => DENIED (no permissive union)."""
    assert (
        activation_atomic(committable_activation_inputs(mixed_versions_present=True))
        is ActivationVerdict.DENIED
    )


def test_each_missing_positive_condition_denies() -> None:
    """(fail-closed) Any of the four bools set to None / unsafe => DENIED."""
    for override in (
        {"version_fully_active": None},
        {"version_fully_active": False},
        {"units_compatible": None},
        {"envelope_bounded": None},
        {"mixed_versions_present": None},
    ):
        assert (
            activation_atomic(committable_activation_inputs(**override))
            is ActivationVerdict.DENIED
        )


def test_incomplete_staging_defers() -> None:
    """(§13 line 383) Incomplete staging / attestation => DEFERRED (not-live, not committed)."""
    assert (
        activation_atomic(committable_activation_inputs(staging_complete=None))
        is ActivationVerdict.DEFERRED
    )
    assert (
        activation_atomic(committable_activation_inputs(attestation_complete=False))
        is ActivationVerdict.DEFERRED
    )


def test_default_activation_inputs_defer() -> None:
    """(fail-closed) A bare ActivationInputs (all None) defers (staging unproven)."""
    from tos.spg import ActivationInputs

    assert activation_atomic(ActivationInputs()) is ActivationVerdict.DEFERRED


def test_activation_atomic_never_vacuously_committable() -> None:
    """(∅-seal) There is no input combination where an unproven bool yields COMMITTABLE."""
    from tos.spg import ActivationInputs

    # A single missing positive proof can never be COMMITTABLE.
    assert (
        activation_atomic(
            ActivationInputs(
                version_fully_active=True,
                mixed_versions_present=False,
                units_compatible=True,
                envelope_bounded=None,  # unproven
                staging_complete=True,
                attestation_complete=True,
            )
        )
        is ActivationVerdict.DENIED
    )


# ---------------------------------------------------------------------------
# activation_serializable — stale-base both-ways
# ---------------------------------------------------------------------------


def test_serializable_positive_side() -> None:
    """(canary + §15) predecessor == current active generation => serializable."""
    candidate = issue_activation(predecessor_generation=4)
    assert activation_serializable(candidate, 4) is True


def test_stale_base_rejected() -> None:
    """(canary - SPG-INV-003) A stale predecessor (!= current) => not serializable."""
    candidate = issue_activation(predecessor_generation=3)
    assert activation_serializable(candidate, 4) is False


def test_serializable_none_fails_closed() -> None:
    """(fail-closed line 161) A None predecessor / None current (latest/cache) fails closed."""
    assert activation_serializable(None, 4) is False
    assert (
        activation_serializable(issue_activation(predecessor_generation=None), 4)
        is False
    )
    assert (
        activation_serializable(issue_activation(predecessor_generation=4), None)
        is False
    )


@given(
    predecessor=st.integers(min_value=0, max_value=5),
    current=st.integers(min_value=0, max_value=5),
)
def test_serializable_iff_predecessor_equals_current(
    predecessor: int, current: int
) -> None:
    """(property) serializable is True IFF predecessor == current (no last-write-wins)."""
    candidate = issue_activation(predecessor_generation=predecessor)
    assert activation_serializable(candidate, current) is (predecessor == current)
