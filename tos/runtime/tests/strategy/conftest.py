"""``tos_runtime.strategy.loader``/``resolve`` test fixtures (hermetic,
``tmp_path`` only).

Builds its own tiny strategy fixtures directly against kernel PRODUCTION
packages (``tos.canonical``/``tos.dsl``/``tos.dsl.serialization``/
``tos.engine.admission``) — mirrors ``tos/runtime/tests/compose/
_fixtures.py``'s own "runtime tests build their own fixtures too"
discipline (that module's docstring); this suite does not import the
compose fixtures.

``parse`` is wired to the REAL kernel :func:`tos.dsl.serialization.
parse_strategy` (D-K lane, landed at ``[D-K-done]`` 2026-09-09) — no local
shim remains, since the kernel function this suite was standing in for now
exists.
"""

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
    """A raw mapping that :func:`tos.dsl.serialization.parse_strategy` +
    :func:`tos.engine.admission.strategy_admissible` both accept positively
    — the happy-path fixture. Shape matches ``tos.dsl.serialization.
    _StrategyAuthoringContent`` exactly: ``dsl_version``,
    ``config_binding_version``, ``policy`` (no ``canonicalization_version``
    — optional, defaults to the provisional scheme)."""
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
    """The IN-PROCESS TYPED equivalent of :func:`admissible_strategy_mapping`'s
    default shape — built directly via :meth:`~tos.dsl.AuthoredStrategy.issue`,
    never through ``parse_strategy``. Used by the cross-check test to prove
    the two authoring paths converge (design #31 §1.2 "두 경로 동형")."""
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
    return parse_strategy


@pytest.fixture()
def admit():
    return strategy_admissible
