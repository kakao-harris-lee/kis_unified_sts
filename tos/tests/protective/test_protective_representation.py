"""representation != enforcement (design #11 §4.5; ADR §5 line 241; §11.4 line 506).

A profile / declaration / verdict is a non-transmitting, non-enforcing datum: no transmit /
egress / emit / mutate / authorize / release / mode-set / capacity-release method exists
anywhere in the protective surface. The producers return decision bools / Admissibility only —
the owning runtime (a future Protective Action Controller) enforces. (Structural-absence test,
#10-isomorphic; the ``send`` token is not banned — protective has no send concept — the
transmit / egress / emit tokens catch transmission.)
"""

from __future__ import annotations

import inspect

import pydantic
import tos.protective as pr
from tos.protective import (
    AggregateRiskComparison,
    HardEnvelopeRef,
    ProtectiveActionEnvelope,
    ProtectiveCapacityProfile,
    ProtectiveLeaseAdmissibilityScope,
    ProtectiveResourceDomainDeclaration,
)

_MODELS = (
    ProtectiveCapacityProfile,
    ProtectiveResourceDomainDeclaration,
    ProtectiveActionEnvelope,
    HardEnvelopeRef,
    ProtectiveLeaseAdmissibilityScope,
    AggregateRiskComparison,
)

#: Names that would betray egress / mutation / authorization / mode-setting. ``send`` is NOT
#: listed — protective has no send/transmit domain concept; actual transmission is caught by
#: ``transmit`` / ``egress`` / ``emit``.
_BANNED_TOKENS = (
    "transmit",
    "egress",
    "emit",
    "mutate",
    "authorize",
    "release",
    "set_state",
    "set_mode",
    "activate",
    "revive",
    "commit",
    "persist",
    "free_capacity",
)


def test_no_enforcement_methods_on_models() -> None:
    """(§4.5) No protective model exposes an egress / mutate / authorize / mode-set method."""
    inherited = set(dir(pydantic.BaseModel))
    for model in _MODELS:
        authored = [
            n for n in dir(model) if not n.startswith("_") and n not in inherited
        ]
        for name in authored:
            for token in _BANNED_TOKENS:
                assert (
                    token not in name.lower()
                ), f"{model.__name__}.{name} looks like enforcement"


def test_no_enforcement_functions_in_predicates() -> None:
    """(§4.5) No public protective function name implies egress / mutation / authorization."""
    for name, obj in vars(pr).items():
        if name.startswith("_") or not inspect.isfunction(obj):
            continue
        for token in _BANNED_TOKENS:
            assert token not in name.lower(), f"function {name} looks like enforcement"


def test_predicates_return_pure_values() -> None:
    """(§4.5) The producer bools are plain values — protective enforces nothing."""
    from ._protective_strategies import (
        approved_minimum,
        issue_profile,
        sufficient_forecast,
    )

    profile = issue_profile()
    assert isinstance(pr.domain_enumeration_complete(profile), bool)
    assert isinstance(
        pr.protective_capacity_exhausted(profile, budget_remaining=5), bool
    )
    assert isinstance(
        pr.reserve_sufficiency(
            profile,
            forecast_capacity=sufficient_forecast(),
            approved_minimum=approved_minimum(),
        ),
        bool,
    )
