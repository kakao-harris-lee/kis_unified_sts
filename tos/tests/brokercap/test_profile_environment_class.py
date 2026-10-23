"""``BrokerCapabilityProfile.environment_class`` (#932 Codex r2).

The egress gateway's option (a) item-6 relaxation reads exactly this field, so it is the
profile's OWN declaration (from its INSTANCE document, never a send-time context), it is
digest-covered, and a profile cannot claim the simulation class while describing live trading.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.brokercap import BrokerEnvironment

from ._brokercap_strategies import issue_profile, live_scope

_NON_LIVE = live_scope(mode="NON_LIVE", action_classes=())


def test_a_simulation_profile_with_a_non_live_scope_constructs() -> None:
    profile = issue_profile(
        live_scope=_NON_LIVE, environment_class=BrokerEnvironment.BROKER_SIMULATION
    )
    assert profile.environment_class is BrokerEnvironment.BROKER_SIMULATION


@pytest.mark.parametrize(
    "scope",
    [
        live_scope(mode="LIVE", action_classes=()),  # a live mode
        live_scope(mode="NON_LIVE", action_classes=("entry",)),  # live action classes
        live_scope(mode=None, action_classes=()),  # undeclared mode
        None,  # no scope at all
    ],
)
def test_a_profile_cannot_claim_simulation_while_describing_live_trading(
    scope: object,
) -> None:
    with pytest.raises(ValidationError, match="BROKER_SIMULATION requires"):
        issue_profile(
            live_scope=scope, environment_class=BrokerEnvironment.BROKER_SIMULATION
        )


def test_a_production_profile_may_describe_live_trading() -> None:
    profile = issue_profile(environment_class=BrokerEnvironment.BROKER_PRODUCTION)
    assert profile.environment_class is BrokerEnvironment.BROKER_PRODUCTION


def test_the_class_is_digest_covered() -> None:
    """An issued profile commits to its class: relabelling it changes the digest."""
    sim = issue_profile(
        live_scope=_NON_LIVE, environment_class=BrokerEnvironment.BROKER_SIMULATION
    )
    prod = issue_profile(
        live_scope=_NON_LIVE, environment_class=BrokerEnvironment.BROKER_PRODUCTION
    )
    assert sim.canonical_digest != prod.canonical_digest
    assert "environment_class" in sim.covered_content()
