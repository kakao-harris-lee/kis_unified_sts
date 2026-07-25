"""Profile version enforcement (design #10 §6.1; BC-EV-021; BC-INV-008).

stale / mismatched / expired / degraded => deny; matching, unexpired, undegraded => True.
This produced bool is the upstream of liveauth ``broker_capability_current``.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.brokercap import active_profile_version, profile_version_current

from ._brokercap_strategies import issue_profile, profile_version

# ---------------------------------------------------------------------------
# profile_version_current both-ways
# ---------------------------------------------------------------------------


def test_current_version_positive() -> None:
    """(§6.1 canary b) Matching ∧ unexpired ∧ undegraded => True."""
    assert (
        profile_version_current(
            active_version="v1",
            presented_version="v1",
            not_expired=True,
            degraded_since_authorization=False,
        )
        is True
    )


def test_mismatched_version_denies() -> None:
    """(§22 / §7.4 canary a) A stale / mismatched presented version => deny."""
    assert (
        profile_version_current(
            active_version="v2",
            presented_version="v1",
            not_expired=True,
            degraded_since_authorization=False,
        )
        is False
    )


def test_expired_version_denies() -> None:
    """(§20.3) not_expired None / False => deny (EXPIRED until revalidated)."""
    assert not profile_version_current("v1", "v1", None, False)
    assert not profile_version_current("v1", "v1", False, False)


def test_degraded_since_authorization_denies() -> None:
    """(§19 line 996 / BC-INV-008) degraded True / None => deny."""
    assert not profile_version_current("v1", "v1", True, True)
    assert not profile_version_current("v1", "v1", True, None)


def test_none_version_denies() -> None:
    """(§6.1) A None active or presented version => deny."""
    assert not profile_version_current(None, "v1", True, False)
    assert not profile_version_current("v1", None, True, False)


@given(
    active=st.none() | st.text(min_size=1, max_size=4),
    presented=st.none() | st.text(min_size=1, max_size=4),
    not_expired=st.sampled_from([True, False, None]),
    degraded=st.sampled_from([True, False, None]),
)
def test_version_current_definition(
    active: str | None,
    presented: str | None,
    not_expired: bool | None,
    degraded: bool | None,
) -> None:
    """profile_version_current is True iff all positive conditions hold."""
    expected = (
        active is not None
        and presented is not None
        and active == presented
        and not_expired is True
        and degraded is False
    )
    assert profile_version_current(active, presented, not_expired, degraded) == expected


# ---------------------------------------------------------------------------
# active_profile_version scalar producer
# ---------------------------------------------------------------------------


def test_active_profile_version_scalar() -> None:
    """(§3.4) active_profile_version returns the immutable version string (liveauth scalar)."""
    profile = issue_profile(profile_version=profile_version(profile_version="v7"))
    assert active_profile_version(profile) == "v7"


def test_active_profile_version_none() -> None:
    """A None profile => None scalar (fail-closed downstream)."""
    assert active_profile_version(None) is None
