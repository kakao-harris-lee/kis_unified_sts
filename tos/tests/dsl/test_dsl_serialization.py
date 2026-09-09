"""Serialized-strategy parsing tests (design #31 §3.5/§9-4).

``parse_strategy`` realizes contract-part (i) of the design #31 §3.5 serialized
authoring seam: pydantic validation of a plain mapping into an issued, digest-bound
``AuthoredStrategy`` — no YAML import in the kernel (that is the runtime lane's job,
design #31 §1.2 lane D-R).

Coverage:

* an unknown key at the top level, and one nested inside ``policy``, is refused and
  the raised ``StrategyParseError`` names its dotted path;
* ``parse_strategy(model_dump)`` round-trips: re-parsing a strategy's own authoring
  content yields the identical digest/id (idempotent, not merely "does not raise");
* the parsed path and the in-process typed path converge on the same artifact shape
  (same digest for the same content, regardless of which path built it) — the
  design #31 §1.2 "두 경로 동형" claim, checked directly rather than only asserted.
"""

from __future__ import annotations

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl import AuthoredStrategy
from tos.dsl.serialization import StrategyParseError, parse_strategy

from ._dsl_strategies import simple_policy

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_NO_ACTION_MAPPING: dict = {
    "dsl_version": "dsl-0",
    "config_binding_version": "cfg-0",
    "policy": {"rules": (), "default": {"kind": "NO_ACTION", "rationale": "hold"}},
}


def _mapping_with(**overrides: object) -> dict:
    base = dict(_NO_ACTION_MAPPING)
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Positive parsing
# ---------------------------------------------------------------------------


def test_a_well_formed_mapping_parses_to_an_issued_strategy() -> None:
    strategy = parse_strategy(_NO_ACTION_MAPPING)
    assert isinstance(strategy, AuthoredStrategy)
    assert strategy.strategy_id is not None
    assert strategy.canonical_digest is not None
    assert strategy.policy is not None
    assert strategy.policy.rules == ()


def test_a_mapping_naming_an_explicit_canonicalization_version_uses_it() -> None:
    strategy = parse_strategy(
        _mapping_with(canonicalization_version=EV_L1_PROVISIONAL_VERSION)
    )
    assert strategy.canonicalization_version == EV_L1_PROVISIONAL_VERSION


# ---------------------------------------------------------------------------
# Unknown keys are refused with their dotted path
# ---------------------------------------------------------------------------


def test_an_unknown_top_level_key_is_refused_with_its_path() -> None:
    with pytest.raises(StrategyParseError, match="not_a_real_field"):
        parse_strategy(_mapping_with(not_a_real_field=True))


def test_an_unknown_key_nested_inside_policy_default_is_refused_with_its_path() -> None:
    mapping = _mapping_with(
        policy={
            "rules": (),
            "default": {"kind": "NO_ACTION", "rationale": "hold", "bogus": 1},
        }
    )
    with pytest.raises(StrategyParseError, match="bogus"):
        parse_strategy(mapping)


def test_an_unknown_key_nested_inside_a_rule_operand_is_refused_with_its_path() -> None:
    mapping = _mapping_with(
        policy={
            "rules": (
                {
                    "all_of": (
                        {
                            "left": {"ref": ("config", "enabled"), "extra_key": 1},
                            "op": "EQ",
                            "right": {"const": True},
                        },
                    ),
                    "decision": {"kind": "NO_ACTION", "rationale": "hold"},
                },
            ),
            "default": {"kind": "NO_ACTION", "rationale": "hold"},
        }
    )
    with pytest.raises(StrategyParseError, match="extra_key"):
        parse_strategy(mapping)


def test_a_precomputed_identity_field_is_refused_as_an_unknown_key() -> None:
    """The authoring-content shape does not accept a hand-written digest/id/status.

    Those three are *derived* by ``AuthoredStrategy.issue`` — never author-supplied
    (module docstring); ``strategy_id``/``canonical_digest``/``status`` are not
    fields of the validation wrapper, so any attempt to smuggle one in is just
    another unknown key.
    """
    with pytest.raises(StrategyParseError, match="strategy_id"):
        parse_strategy(_mapping_with(strategy_id="astrat-forged"))


# ---------------------------------------------------------------------------
# Round-trip + cross-path convergence
# ---------------------------------------------------------------------------


def test_round_trip_parse_strategy_of_its_own_dump_is_idempotent() -> None:
    """Re-parsing a parsed strategy's own authoring content yields the identical artifact."""
    first = parse_strategy(_NO_ACTION_MAPPING)
    round_tripped_mapping = {
        "dsl_version": first.dsl_version,
        "config_binding_version": first.config_binding_version,
        "policy": first.policy.model_dump(mode="json"),
    }
    second = parse_strategy(round_tripped_mapping)
    assert second.canonical_digest == first.canonical_digest
    assert second.strategy_id == first.strategy_id


def test_parsed_path_and_in_process_path_converge_on_the_same_digest() -> None:
    """The parsed mapping and the in-process typed builder agree bit-for-bit (design #31 §1.2)."""
    policy = simple_policy()
    mapping = {
        "dsl_version": "dsl-0",
        "config_binding_version": "cfg-bind-0",
        "policy": policy.model_dump(mode="json"),
    }
    parsed = parse_strategy(mapping)
    in_process = AuthoredStrategy.issue(
        scheme=_SCHEME,
        dsl_version="dsl-0",
        config_binding_version="cfg-bind-0",
        policy=policy,
    )
    assert parsed.canonical_digest == in_process.canonical_digest
    assert parsed.strategy_id == in_process.strategy_id


def test_a_structurally_invalid_rule_guard_is_refused_not_silently_dropped() -> None:
    """An empty ``all_of`` (the vacuous-True guard the typed algebra forbids) is refused."""
    mapping = _mapping_with(
        policy={
            "rules": (
                {"all_of": (), "decision": {"kind": "NO_ACTION", "rationale": "x"}},
            ),
            "default": {"kind": "NO_ACTION", "rationale": "hold"},
        }
    )
    with pytest.raises(StrategyParseError):
        parse_strategy(mapping)
