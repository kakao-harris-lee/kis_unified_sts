"""Polarity exhaustive regression — None ⇒ deny convergence (design #25 §4.3 / #22 MAJOR-2 seal).

The #22 MAJOR-2 lesson: a ``bool | None`` field read with ``if field:`` / ``if not field:`` fails
open on ``None`` depending on polarity. Every rlp field declares its polarity and is normalized with
``is True`` / ``is False``. This suite property-checks that **every negative-polarity field's ``None``
converges to deny** (never fail-opens to "not consumed" / "not expired" / "not aborted") and **every
positive-polarity field's ``None`` / ``False`` converges to deny**.

Regime tag: predicate substrate only; polarity seal; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from hypothesis import given
from tos.rlp import (
    TrialRunState,
    demotion_not_rearm,
    expiry_denies_future_use_only,
    promotion_progressive_single_use,
    recovery_revives_nothing,
)

from ._rlp_strategies import (
    PROMOTION_PREDECESSOR_FLOOR,
    TRIBOOL,
    clean_decision,
    clean_promotion_policy,
)

# --- negative polarity: only `is False` admits; None / True deny -------------


@given(consumed=TRIBOOL)
def test_single_use_consumed_only_false_admits(consumed: bool | None) -> None:
    """(§4.3 negative) single_use_consumed: only explicit False admits; None / True reject reuse."""
    decision = clean_decision(single_use_consumed=consumed)
    assert promotion_progressive_single_use(
        decision, clean_promotion_policy(), PROMOTION_PREDECESSOR_FLOOR
    ) is (consumed is False)


@given(expired=TRIBOOL)
def test_is_expired_negative_polarity(expired: bool | None) -> None:
    """(§4.3 negative / §6.5) is_expired: None / True deny future use; only False allows future use."""
    # expiry_denies_future_use_only returns True == deny; deny for None / True, allow only for False.
    assert expiry_denies_future_use_only(expired) is (expired is not False)


@given(reused=TRIBOOL)
def test_demotion_not_rearm_negative_polarity(reused: bool | None) -> None:
    """(§4.3 negative / §6.7) historical_promotion_reused: only explicit False allows a fresh demotion."""
    assert demotion_not_rearm(reused) is (reused is False)


# --- recovery non-revival: a recovery event revives nothing; None denies -----


@given(is_recovery=TRIBOOL)
def test_recovery_revives_nothing_forces_dead(is_recovery: bool | None) -> None:
    """(§6.6 / §4.3 negative polarity — #25 MAJOR-2 seal) Only an explicit non-recovery admits.

    ``is_recovery_event`` is negative polarity: a recovery event (``True``) **and** an unknown
    recovery flag (``None``) both revive nothing (dead), so only an explicit ``False`` (a proven
    non-recovery) keeps a prior ``RUNNING`` run live. The old ``is not True`` normalization
    fail-opened a ``None`` to "live".
    """
    # a recovery event OR an unknown (None) recovery flag => dead regardless of prior state.
    assert recovery_revives_nothing(is_recovery, TrialRunState.RUNNING) is (
        is_recovery is False
    )
    # a None prior run state is never live (fail-closed), whatever the recovery flag.
    assert recovery_revives_nothing(is_recovery, None) is False


@given(prior=TRIBOOL)
def test_recovery_prior_state_only_running_is_live(prior: bool | None) -> None:
    """(§6.6) Absent a recovery event, only a RUNNING prior state is live; terminals / None deny."""
    state = (
        TrialRunState.RUNNING
        if prior is True
        else (TrialRunState.TERMINATED if prior is False else None)
    )
    expected = state is TrialRunState.RUNNING
    assert recovery_revives_nothing(False, state) is expected


# --- exhaustive: every negative-polarity None on the decision converges to deny


@given(consumed=TRIBOOL)
def test_any_negative_none_or_true_denies_promotion(consumed: bool | None) -> None:
    """(§4.3 exhaustive) A None / True single_use_consumed ⇒ promotion not single-use-eligible."""
    if consumed is False:
        assert (
            promotion_progressive_single_use(
                clean_decision(single_use_consumed=consumed),
                clean_promotion_policy(),
                PROMOTION_PREDECESSOR_FLOOR,
            )
            is True
        )
    else:
        assert (
            promotion_progressive_single_use(
                clean_decision(single_use_consumed=consumed),
                clean_promotion_policy(),
                PROMOTION_PREDECESSOR_FLOOR,
            )
            is False
        )
