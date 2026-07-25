"""Environment binding + credential scope (design #10 §6.4; BC-EV-020/015; BC-INV-009).

Cross-environment (sandbox/paper) evidence SHALL NOT establish live capability; same,
non-inherited environment => bound; a requested credential scope must be within the declared
scope.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.brokercap import credential_scope_declared_ok, environment_binding_ok

from ._brokercap_strategies import issue_profile, profile_key

# ---------------------------------------------------------------------------
# environment_binding_ok both-ways (BC-INV-009)
# ---------------------------------------------------------------------------


def test_same_environment_not_inherited_ok() -> None:
    """(§6.4 canary b) Same environment ∧ not inherited => True."""
    assert (
        environment_binding_ok(
            evidence_environment="live", scope_environment="live", inherited=False
        )
        is True
    )


def test_cross_environment_evidence_denied() -> None:
    """(BC-INV-009 canary a) Sandbox evidence for a live scope => False (no auto-establish)."""
    assert (
        environment_binding_ok(
            evidence_environment="sandbox", scope_environment="live", inherited=False
        )
        is False
    )


def test_inherited_capability_denied() -> None:
    """(§13.14) inherited True => False (do not inherit capability across environments)."""
    assert (
        environment_binding_ok(
            evidence_environment="live", scope_environment="live", inherited=True
        )
        is False
    )


def test_none_environment_or_inherited_fails_closed() -> None:
    """(§6.4) Any None environment / inherited => False."""
    assert not environment_binding_ok(None, "live", False)
    assert not environment_binding_ok("live", None, False)
    assert not environment_binding_ok("live", "live", None)


@given(
    ev_env=st.none() | st.sampled_from(["live", "sandbox", "paper"]),
    scope_env=st.none() | st.sampled_from(["live", "sandbox", "paper"]),
    inherited=st.sampled_from([True, False, None]),
)
def test_environment_binding_definition(
    ev_env: str | None, scope_env: str | None, inherited: bool | None
) -> None:
    """environment_binding_ok iff both concrete + equal + not inherited."""
    expected = (
        ev_env is not None
        and scope_env is not None
        and ev_env == scope_env
        and inherited is False
    )
    assert environment_binding_ok(ev_env, scope_env, inherited) == expected


# ---------------------------------------------------------------------------
# credential_scope_declared_ok
# ---------------------------------------------------------------------------


def test_matching_credential_scope_ok() -> None:
    """(§6.4) A requested scope matching the declared credential scope => True."""
    profile = issue_profile(profile_key=profile_key(credential_scope="trade"))
    assert credential_scope_declared_ok(profile, "trade") is True


def test_mismatched_credential_scope_denied() -> None:
    """(§6.4) A requested scope not matching the declared scope => False."""
    profile = issue_profile(profile_key=profile_key(credential_scope="read"))
    assert credential_scope_declared_ok(profile, "trade") is False


def test_undeclared_or_none_credential_scope_fails_closed() -> None:
    """(§6.4) An undeclared scope or a None request => False."""
    profile_no_scope = issue_profile(profile_key=profile_key(credential_scope=None))
    assert credential_scope_declared_ok(profile_no_scope, "trade") is False
    profile = issue_profile(profile_key=profile_key(credential_scope="trade"))
    assert credential_scope_declared_ok(profile, None) is False
    assert credential_scope_declared_ok(None, "trade") is False
