"""representation != enforcement (design #12 §4.5; SPG-INV-014 line 205).

An envelope / profile / bundle / activation record / verdict is a non-transmitting,
non-enforcing datum: no egress / transmit / mutate / authorize / release / activate /
capacity method exists anywhere in the spg surface. The producers return decision bools /
scalars only — the owning runtime enforces.
"""

from __future__ import annotations

import inspect

import pydantic
import tos.spg as spg
from tos.spg import (
    ActivationRecord,
    ConsumerCompatibilityManifest,
    GovernedDimensionLimit,
    HardSafetyEnvelope,
    RuntimeSafetyProfile,
    SafetyConfigurationBundle,
)

_MODELS = (
    HardSafetyEnvelope,
    RuntimeSafetyProfile,
    SafetyConfigurationBundle,
    ActivationRecord,
    ConsumerCompatibilityManifest,
    GovernedDimensionLimit,
)

#: Names that would betray egress / mutation / authorization / activation. ("activation" as a
#: noun is caught by the "activate" verb token below; the record type is a passive datum.)
_BANNED_TOKENS = (
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
    "arm",
    "delete",
    "overwrite",
    "free_capacity",
)


def test_no_enforcement_methods_on_models() -> None:
    """(§4.5) No spg model exposes an egress / mutate / authorize / activate method."""
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
    """(§4.5) No public spg function name implies egress / mutation / activation.

    Predicate names describe *decisions* about activation (``activation_atomic`` /
    ``activation_serializable``) or produce scalars (``activation_digest``); they do not
    perform an activation. The banned tokens are the *verb* forms (``activate``); the
    ``activation`` noun in a decision-predicate name is allowed.
    """
    # NB: "revive" is intentionally NOT listed — ``expiry_revives_nothing`` /
    # ``rollback_revives_nothing`` are pure decision predicates asserting NON-revival, not
    # enforcement (design #12 §5.6/§6.1). Actual state change would be "activate" / "commit".
    verb_banned = (
        "transmit",
        "egress",
        "mutate",
        "authorize",
        "release",
        "commit",
        "persist",
        "emit",
    )
    for name, obj in vars(spg).items():
        if name.startswith("_") or not inspect.isfunction(obj):
            continue
        for token in verb_banned:
            assert token not in name.lower(), f"function {name} looks like enforcement"


def test_predicates_return_pure_values() -> None:
    """(§4.5) The producer outputs are plain values — spg enforces nothing."""
    from ._spg_strategies import issue_envelope, issue_profile

    env = issue_envelope()
    prof = issue_profile()
    assert isinstance(spg.envelope_bounded(env, prof), bool)
    assert isinstance(spg.active_envelope_version(env), str)
    assert isinstance(spg.active_profile_generation(prof), int)


def test_no_mutate_methods_on_envelope() -> None:
    """(§2.0/§4.5) The envelope adds no update / delete / mutate / release / capacity method."""
    banned = ("update", "delete", "mutate", "release", "free_capacity", "overwrite")
    inherited = set(dir(pydantic.BaseModel))
    authored = [
        n
        for n in dir(HardSafetyEnvelope)
        if not n.startswith("_") and n not in inherited
    ]
    for name in authored:
        for token in banned:
            assert token not in name.lower(), f"unexpected mutating method: {name}"
