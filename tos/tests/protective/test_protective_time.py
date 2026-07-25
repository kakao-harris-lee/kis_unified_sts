"""§10 time-untrusted protective behavior (design #11 §6.5).

When time cannot be trusted, time-dependent authorization is invalid: a new protective order
is admissible only under a non-time-dependent emergency rule; a cancellation of a confirmed
risk-increasing order MAY be admissible when not itself risk-increasing. protective consumes
the ``time_trusted`` bool (tos.time owns the arithmetic). SA-EV-011 / TIME-EV-* substrate —
closes nothing.
"""

from __future__ import annotations

from tos.protective import (
    Admissibility,
    ProtectiveActionKind,
    time_untrusted_protective_admissible,
)

_NEW = ProtectiveActionKind.NEW_PROTECTIVE_ORDER
_CANCEL = ProtectiveActionKind.CANCELLATION_OF_RISK_INCREASING


def test_untrusted_new_order_without_emergency_rule_prohibited() -> None:
    """(§10 line 459 canary a) Untrusted time + new protective order without rule => PROHIBITED."""
    for trusted in (False, None):
        verdict = time_untrusted_protective_admissible(
            _NEW,
            time_trusted=trusted,
            nontime_dependent_emergency_rule=None,
            cancellation_not_risk_increasing=None,
        )
        assert verdict is Admissibility.PROHIBITED


def test_untrusted_new_order_with_emergency_rule_admissible() -> None:
    """(§10 line 459) Untrusted time + a non-time-dependent emergency rule => ADMISSIBLE."""
    verdict = time_untrusted_protective_admissible(
        _NEW,
        time_trusted=False,
        nontime_dependent_emergency_rule=True,
        cancellation_not_risk_increasing=None,
    )
    assert verdict is Admissibility.ADMISSIBLE


def test_untrusted_cancellation_not_risk_increasing_may_be_admissible() -> None:
    """(§10 line 460 canary b) Untrusted time + non-risk-increasing cancellation => MAY ADMISSIBLE."""
    verdict = time_untrusted_protective_admissible(
        _CANCEL,
        time_trusted=False,
        nontime_dependent_emergency_rule=None,
        cancellation_not_risk_increasing=True,
    )
    assert verdict is Admissibility.ADMISSIBLE


def test_untrusted_cancellation_risk_increasing_prohibited() -> None:
    """(§10 line 460) Untrusted time + a risk-increasing cancellation (None / False) => PROHIBITED."""
    for value in (None, False):
        verdict = time_untrusted_protective_admissible(
            _CANCEL,
            time_trusted=False,
            nontime_dependent_emergency_rule=None,
            cancellation_not_risk_increasing=value,
        )
        assert verdict is Admissibility.PROHIBITED


def test_trusted_time_delegates_admissible() -> None:
    """(§10) Trusted time => normal path (not blocked on the time axis) => ADMISSIBLE."""
    verdict = time_untrusted_protective_admissible(
        _NEW,
        time_trusted=True,
        nontime_dependent_emergency_rule=None,
        cancellation_not_risk_increasing=None,
    )
    assert verdict is Admissibility.ADMISSIBLE


def test_untrusted_unrelated_kind_prohibited() -> None:
    """(§10) Untrusted time + a kind that is neither new-order nor cancellation => PROHIBITED."""
    verdict = time_untrusted_protective_admissible(
        ProtectiveActionKind.OVERLAP_FIRST_ADD_ONLY,
        time_trusted=None,
        nontime_dependent_emergency_rule=True,
        cancellation_not_risk_increasing=True,
    )
    assert verdict is Admissibility.PROHIBITED
