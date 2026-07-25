"""representation != enforcement (design #10 §4.5; ADR §19/§27; §17.5 line 947).

A profile / declaration / verdict is a non-transmitting, non-enforcing datum: no egress /
transmit / mutate / authorize / release / KnowledgeState-set method exists anywhere in the
brokercap surface. The producers return decision bools only — the owning runtime enforces.
"""

from __future__ import annotations

import inspect

import pydantic
import tos.brokercap as bc
from tos.brokercap import (
    BrokerCapabilityProfile,
    CapabilityDeclaration,
    FinalQuantityProofRule,
    LiveScope,
    ProfileKey,
    ProfileVersion,
    UncertainSendVerdict,
)

_MODELS = (
    BrokerCapabilityProfile,
    CapabilityDeclaration,
    ProfileKey,
    ProfileVersion,
    LiveScope,
    FinalQuantityProofRule,
    UncertainSendVerdict,
)

#: Names that would betray egress / mutation / authorization / state-setting. ("send" is
#: intentionally NOT listed: ``uncertain_send_policy`` is a pure decision producer named for
#: the ADR §12.4 "uncertain send" domain concept — actual transmission is caught by
#: "transmit" / "egress".)
_BANNED_MODEL_TOKENS = (
    "transmit",
    "egress",
    "mutate",
    "authorize",
    "release",
    "set_state",
    "set_knowledge",
    "activate",
    "revive",
    "commit",
    "persist",
    "emit",
)


def test_no_enforcement_methods_on_models() -> None:
    """(§4.5) No brokercap model exposes an egress / mutate / authorize / state-set method."""
    inherited = set(dir(pydantic.BaseModel))
    for model in _MODELS:
        authored = [
            n for n in dir(model) if not n.startswith("_") and n not in inherited
        ]
        for name in authored:
            for token in _BANNED_MODEL_TOKENS:
                assert (
                    token not in name.lower()
                ), f"{model.__name__}.{name} looks like enforcement"


def test_no_enforcement_functions_in_predicates() -> None:
    """(§4.5) No public brokercap function name implies egress / mutation / authorization."""
    for name, obj in vars(bc).items():
        if name.startswith("_") or not inspect.isfunction(obj):
            continue
        for token in _BANNED_MODEL_TOKENS:
            assert token not in name.lower(), f"function {name} looks like enforcement"


def test_predicates_return_pure_values() -> None:
    """(§4.5) The producer bools are plain values — brokercap enforces nothing."""
    from ._brokercap_strategies import issue_profile, required_set

    profile = issue_profile()
    assert isinstance(
        bc.broker_capability_sufficient(profile, required_set(), version_current=True),
        bool,
    )
    assert isinstance(bc.active_profile_version(profile), str)
    assert isinstance(bc.active_conformance_class(profile), str)
