"""§11 protective ownership + Cancellation Arbiter (design #11 §6.3).

A SAFETY_OWNED order is cancellable only under one of the three §11.1 conditions; the three
disjuncts all fail closed. A submitted-but-unconfirmed replacement gets no optimistic credit
(§11.4 line 506). An ordinary order is cancellable only when cancellation is confirmed not to
worsen aggregate risk. PR-EV-011 / X-EV-006 substrate — closes nothing.
"""

from __future__ import annotations

from tos.protective import ProtectiveOwnership, cancellation_admissible


def _safety_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "protection_no_longer_required": None,
        "within_hard_envelope": None,
        "equivalent_replacement_live": None,
        "continued_existence_worsens_aggregate": None,
        "controller_authorizes_removal": None,
        "cancellation_worsens_aggregate": None,
    }
    base.update(overrides)
    return base


def test_safety_owned_no_condition_is_not_cancellable() -> None:
    """(§11.1 canary a) SAFETY_OWNED with none of the three disjuncts => False."""
    assert (
        cancellation_admissible(ProtectiveOwnership.SAFETY_OWNED, **_safety_kwargs())
        is False
    )


def test_safety_owned_protection_no_longer_required_within_envelope() -> None:
    """(§11.1 disjunct 1) Protection no longer required ∧ within Hard Envelope => cancellable."""
    assert (
        cancellation_admissible(
            ProtectiveOwnership.SAFETY_OWNED,
            **_safety_kwargs(
                protection_no_longer_required=True, within_hard_envelope=True
            ),
        )
        is True
    )


def test_safety_owned_partial_first_disjunct_is_false() -> None:
    """(§11.1) protection-no-longer-required alone (not within envelope) => False."""
    assert (
        cancellation_admissible(
            ProtectiveOwnership.SAFETY_OWNED,
            **_safety_kwargs(protection_no_longer_required=True),
        )
        is False
    )


def test_safety_owned_equivalent_replacement_confirmed_live() -> None:
    """(§11.1 disjunct 2 canary b) A confirmed-live equivalent replacement => cancellable."""
    assert (
        cancellation_admissible(
            ProtectiveOwnership.SAFETY_OWNED,
            **_safety_kwargs(equivalent_replacement_live=True),
        )
        is True
    )


def test_safety_owned_unconfirmed_replacement_gets_no_credit() -> None:
    """(§11.4 line 506) A submitted-but-unconfirmed replacement (None / False) => no credit."""
    for value in (None, False):
        assert (
            cancellation_admissible(
                ProtectiveOwnership.SAFETY_OWNED,
                **_safety_kwargs(equivalent_replacement_live=value),
            )
            is False
        )


def test_safety_owned_worsening_with_controller_authorization() -> None:
    """(§11.1 disjunct 3) Continued existence worsens aggregate ∧ controller authorizes => cancel."""
    assert (
        cancellation_admissible(
            ProtectiveOwnership.SAFETY_OWNED,
            **_safety_kwargs(
                continued_existence_worsens_aggregate=True,
                controller_authorizes_removal=True,
            ),
        )
        is True
    )


def test_safety_owned_worsening_without_authorization_is_false() -> None:
    """(§11.1 disjunct 3) Worsening without controller authorization => False."""
    assert (
        cancellation_admissible(
            ProtectiveOwnership.SAFETY_OWNED,
            **_safety_kwargs(continued_existence_worsens_aggregate=True),
        )
        is False
    )


def test_ordinary_order_cancellable_when_not_worsening() -> None:
    """(§11.3) An ordinary order is cancellable only when cancellation does not worsen aggregate."""
    for ownership in (
        ProtectiveOwnership.STRATEGY_OWNED,
        ProtectiveOwnership.EXECUTION_OWNED,
        ProtectiveOwnership.OPERATOR_OWNED,
    ):
        assert (
            cancellation_admissible(
                ownership, **_safety_kwargs(cancellation_worsens_aggregate=False)
            )
            is True
        )


def test_ordinary_order_not_cancellable_when_worsening_or_unknown() -> None:
    """(§11.3) An ordinary cancellation that worsens aggregate (True / None) => False."""
    for value in (True, None):
        assert (
            cancellation_admissible(
                ProtectiveOwnership.STRATEGY_OWNED,
                **_safety_kwargs(cancellation_worsens_aggregate=value),
            )
            is False
        )
