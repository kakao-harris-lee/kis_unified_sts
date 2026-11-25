"""``tos_runtime.strategy.loader``/``resolve`` test fixtures (hermetic,"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl.serialization import parse_strategy
from tos.dsl.strategy import AuthoredStrategy
from tos.dsl.vocabulary import DecisionPolicy
from tos.engine.admission import strategy_admissible

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

ACCOUNT = "acct-strategy-loader"
INSTRUMENT = "ES"


def admissible_strategy_mapping(**overrides: Any) -> dict[str, Any]:
    """A raw mapping that :func:`tos.dsl.serialization.parse_strategy` +"""
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


def in_process_typed_strategy() -> AuthoredStrategy:
    """The IN-PROCESS TYPED equivalent of :func:`admissible_strategy_mapping`'s"""
    mapping = admissible_strategy_mapping()
    policy = DecisionPolicy(**mapping["policy"])
    issued = AuthoredStrategy.issue(
        scheme=SCHEME,
        dsl_version=mapping["dsl_version"],
        config_binding_version=mapping["config_binding_version"],
        policy=policy,
    )
    assert isinstance(issued, AuthoredStrategy)
    return issued


def inadmissible_strategy_mapping() -> dict[str, Any]:
    """A mapping that parses cleanly but is INADMISSIBLE: its only outcome-"""
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
    return parse_strategy


@pytest.fixture()
def admit():
    return strategy_admissible
