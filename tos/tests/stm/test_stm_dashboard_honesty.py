"""§23 dashboard honesty — 7-token drift + the no-green-default gate (design #30 §7.2).

ADR §23 line 499 verbatim: "Dashboards SHALL distinguish at minimum ``CURRENT_CONFORMING``,
``RESTRICTED``, ``NON_CONFORMING``, ``UNKNOWN``, ``STALE``, ``GAP``, and ``UNVERIFIED``. **Rendering
failures or unknown state SHALL NOT default to green.**"

Both gates are asserted independently and both ways: the marker-triggered no-green-default gate and the
negative-polarity ``defaulted_to_green`` judgement.

Regime tag: predicate substrate only; closes **no** STM-EV (STM-EV-012 substrate, ``EV-L2/3+Security``);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from tos.stm import DashboardStatusToken, evidence_and_status_honest

from ._stm_strategies import TRIBOOL, clean_dashboard


def test_the_seven_token_anchor_is_exact() -> None:
    """(§7.2 drift, appendix D) §23 line 499 names exactly seven statuses (過 0 · 不 0)."""
    assert {member.value for member in DashboardStatusToken} == {
        "CURRENT_CONFORMING",
        "RESTRICTED",
        "NON_CONFORMING",
        "UNKNOWN",
        "STALE",
        "GAP",
        "UNVERIFIED",
    }
    assert len(DashboardStatusToken) == 7


@pytest.mark.parametrize("token", sorted(DashboardStatusToken))
def test_no_token_is_truthy_testable(token: DashboardStatusToken) -> None:
    """(§4.2) ``bool(token)`` raises — ``UNVERIFIED`` can never be misread as green."""
    with pytest.raises(TypeError):
        bool(token)


def test_a_clean_view_is_honest() -> None:
    """(both-ways +) No failed render, no unknown state, no green default."""
    assert evidence_and_status_honest(clean_dashboard()) is True


@pytest.mark.parametrize("marker", ["rendering_failed", "state_unknown"])
def test_a_marker_forbids_a_green_token(marker: str) -> None:
    """(§23 line 499) A rendering failure or unknown state can never show ``CURRENT_CONFORMING``."""
    view = clean_dashboard(**{marker: True})
    assert view.status_token is DashboardStatusToken.CURRENT_CONFORMING
    assert evidence_and_status_honest(view) is False


@pytest.mark.parametrize("marker", ["rendering_failed", "state_unknown"])
@pytest.mark.parametrize(
    "token",
    [
        t
        for t in DashboardStatusToken
        if t is not DashboardStatusToken.CURRENT_CONFORMING
    ],
)
def test_a_marker_with_an_honest_token_is_admissible(
    marker: str, token: DashboardStatusToken
) -> None:
    """(both-ways +) A failed render shown as ``UNVERIFIED`` / ``STALE`` / ``GAP`` is honest."""
    assert (
        evidence_and_status_honest(
            clean_dashboard(**{marker: True}, status_token=token)
        )
        is True
    )


@pytest.mark.parametrize("value", [True, None])
def test_a_green_default_denies_on_every_token(value: bool | None) -> None:
    """(§4.3 negative polarity) ``defaulted_to_green is not False`` denies — ``None`` included."""
    for token in DashboardStatusToken:
        assert (
            evidence_and_status_honest(
                clean_dashboard(defaulted_to_green=value, status_token=token)
            )
            is False
        )


def test_an_unrendered_view_denies() -> None:
    """(fail-closed) A view with no status token is not a green one."""
    assert evidence_and_status_honest(clean_dashboard(status_token=None)) is False


def test_absent_view_denies() -> None:
    """(∅-seal) ``None`` is undecidable, therefore denied."""
    assert evidence_and_status_honest(None) is False


@given(rendering=TRIBOOL, unknown=TRIBOOL, green=TRIBOOL)
def test_the_two_gates_are_independent(
    rendering: bool | None, unknown: bool | None, green: bool | None
) -> None:
    """(property) A marker gate and the green-default gate each deny on their own."""
    view = clean_dashboard(
        rendering_failed=rendering, state_unknown=unknown, defaulted_to_green=green
    )
    marker_set = rendering is True or unknown is True
    expected = (not marker_set) and green is False
    assert evidence_and_status_honest(view) is expected
