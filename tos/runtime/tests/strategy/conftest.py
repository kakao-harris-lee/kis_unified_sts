"""``tos_runtime.strategy.loader`` test fixtures (hermetic, ``tmp_path`` only).

Builds its own tiny strategy fixtures directly against kernel PRODUCTION
packages (``tos.canonical``/``tos.dsl``/``tos.engine.admission``) — mirrors
``tos/runtime/tests/compose/_fixtures.py``'s own "runtime tests build their
own fixtures too" discipline (that module's docstring); this suite does not
import the compose fixtures.

``shim_parse_strategy`` stands in for the not-yet-landed kernel
``tos.dsl.serialization.parse_strategy`` (D-K lane, design #31 §9-4 / plan
§1.2): it builds+issues an :class:`~tos.dsl.AuthoredStrategy` directly from
the raw mapping via pydantic construction (nested dict -> submodel
validation is automatic in pydantic v2), so this suite exercises
``load_strategies`` against the SAME mapping shape the eventual kernel
parser will accept — only the parsing mechanism differs, never the shape.
An unrecognized top-level key in the ``policy``/nested mappings surfaces as
a ``pydantic.ValidationError`` here (every DSL model is
``extra="forbid"`` — ``tos.canonical._base.FrozenModel``), which
``load_strategies`` catches and re-raises as ``StrategyLoadError`` — the
same behavior the eventual kernel ``StrategyParseError`` path will have.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl import AuthoredStrategy
from tos.dsl.vocabulary import DecisionPolicy
from tos.engine.admission import strategy_admissible

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

ACCOUNT = "acct-strategy-loader"
INSTRUMENT = "ES"


def shim_parse_strategy(mapping: dict[str, Any]) -> AuthoredStrategy:
    """Test-only stand-in for the not-yet-landed kernel
    ``tos.dsl.serialization.parse_strategy`` — see this module's docstring."""
    policy = DecisionPolicy(**mapping["policy"])
    issued = AuthoredStrategy.issue(
        scheme=SCHEME,
        dsl_version=mapping["dsl_version"],
        config_binding_version=mapping["config_binding_version"],
        policy=policy,
    )
    assert isinstance(issued, AuthoredStrategy)
    return issued


def admissible_strategy_mapping(**overrides: Any) -> dict[str, Any]:
    """A raw mapping that ``shim_parse_strategy`` + ``strategy_admissible``
    both accept positively — the happy-path fixture."""
    base: dict[str, Any] = {
        "dsl_version": "dsl-loader-test",
        "config_binding_version": "cfg-bind-loader-test",
        "policy": {
            "rules": [
                {
                    "all_of": [
                        {
                            "left": {"ref": ["capsule", "resolved_values", "close"]},
                            "op": "LT",
                            "right": {
                                "ref": ["capsule", "resolved_values", "lower_band"]
                            },
                        }
                    ],
                    "decision": {
                        "kind": "ACTION",
                        "rationale": "close pierced the lower band",
                        "target": {
                            "kind": "ACTION",
                            "account": ACCOUNT,
                            "instrument": INSTRUMENT,
                            "direction": "LONG",
                            "position_effect": "OPEN",
                            "quantity_basis": "RISK",
                            "edge_or_confidence": "loader-test",
                        },
                    },
                }
            ],
            "default": {"kind": "NO_ACTION", "rationale": "hold, no proposal"},
        },
    }
    base.update(overrides)
    return base


def inadmissible_strategy_mapping() -> dict[str, Any]:
    """A mapping that parses cleanly but is INADMISSIBLE: its only outcome-
    gating Compare has no capsule-sourced operand (both sides are literal
    ``const`` values) — the D1<->D4 partial seal
    (``tos.engine.admission.compare_has_capsule_operand``) rejects this."""
    mapping = admissible_strategy_mapping()
    mapping["policy"]["rules"][0]["all_of"][0] = {
        "left": {"const": 1},
        "op": "LT",
        "right": {"const": 2},
    }
    return mapping


def write_strategy_yaml(directory: Path, name: str, mapping: dict[str, Any]) -> Path:
    path = directory / name
    path.write_text(yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture()
def strategies_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "strategies"
    directory.mkdir()
    return directory


@pytest.fixture()
def parse():
    return shim_parse_strategy


@pytest.fixture()
def admit():
    return strategy_admissible
