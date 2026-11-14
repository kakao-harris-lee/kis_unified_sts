"""Mirrored long/short compose fixtures for the W5 §2 decision 8 symmetry suite (lane f4)."""

from __future__ import annotations

from pathlib import Path

import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl import (
    VALUE_NAMESPACE,
    AuthoredStrategy,
    Compare,
    CompareOp,
    Decision,
    DecisionKind,
    DecisionPolicy,
    Operand,
    Rule,
    TargetKind,
    TargetSpec,
)
from tos.venue import ActionClass
from tos_runtime.compose.root import ConstructionConfig

from . import _fixtures as fx

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def _value_ref(field_key: str) -> Operand:
    """Re-derived locally rather than reaching into ``fx``'s underscore-private helper (same"""
    return Operand(ref=("capsule", VALUE_NAMESPACE, field_key))


def mirrored_policy() -> DecisionPolicy:
    """``close < lower_band`` -> ``SHORT``/``OPEN`` — the exact same trigger"""
    entry = Decision(
        kind=DecisionKind.ACTION,
        rationale="close pierced the lower band — compose e2e SHORT mirror",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=fx.ACCOUNT,
            instrument=fx.INSTRUMENT,
            direction="SHORT",
            position_effect="OPEN",
            quantity_basis="RISK",
            edge_or_confidence="compose-e2e-short",
            rationale="close pierced the lower band — compose e2e SHORT mirror",
        ),
    )
    hold = Decision(
        kind=DecisionKind.NO_ACTION,
        rationale="close is inside the band — hold, no proposal",
    )
    return DecisionPolicy(
        rules=(
            Rule(
                all_of=(
                    Compare(
                        left=_value_ref("close"),
                        op=CompareOp.LT,
                        right=_value_ref("lower_band"),
                    ),
                ),
                decision=entry,
            ),
        ),
        default=hold,
    )


def mirrored_strategy() -> AuthoredStrategy:
    issued = AuthoredStrategy.issue(
        scheme=SCHEME,
        dsl_version="dsl-compose",
        config_binding_version="cfg-bind-compose",
        policy=mirrored_policy(),
    )
    assert isinstance(issued, AuthoredStrategy)
    return issued


def mirrored_strategy_mapping() -> dict[str, object]:
    """The raw-mapping equivalent of :func:`mirrored_strategy`, mirroring"""
    return {
        "dsl_version": "dsl-compose",
        "config_binding_version": "cfg-bind-compose",
        "policy": {
            "rules": [
                {
                    "all_of": [
                        {
                            "left": {"ref": ["capsule", VALUE_NAMESPACE, "close"]},
                            "op": "LT",
                            "right": {
                                "ref": ["capsule", VALUE_NAMESPACE, "lower_band"]
                            },
                        }
                    ],
                    "decision": {
                        "kind": "ACTION",
                        "rationale": "close pierced the lower band — compose e2e SHORT mirror",
                        "target": {
                            "kind": "ACTION",
                            "account": fx.ACCOUNT,
                            "instrument": fx.INSTRUMENT,
                            "direction": "SHORT",
                            "position_effect": "OPEN",
                            "quantity_basis": "RISK",
                            "edge_or_confidence": "compose-e2e-short",
                            "rationale": "close pierced the lower band — compose e2e SHORT mirror",
                        },
                    },
                }
            ],
            "default": {
                "kind": "NO_ACTION",
                "rationale": "close is inside the band — hold, no proposal",
            },
        },
    }


MIRRORED_STRATEGY_FILE_NAME = "band-short.strategy.yaml"


def write_mirrored_strategy_file(config_dir: Path) -> Path:
    """Write :func:`mirrored_strategy_mapping` — the SHORT-side counterpart of"""
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(exist_ok=True)
    path = strategies_dir / MIRRORED_STRATEGY_FILE_NAME
    path.write_text(
        yaml.safe_dump(mirrored_strategy_mapping(), sort_keys=False),
        encoding="utf-8",
    )
    return path


def mirrored_construction_config() -> ConstructionConfig:
    """:func:`~._fixtures.construction_config`, mirrored (plan §2 decision 8: "픽스처"""
    return ConstructionConfig(
        account=fx.ACCOUNT,
        instrument=fx.INSTRUMENT,
        price=fx.admitted_price(),
        action_class=ActionClass.NEW_SHORT,
        instrument_class=fx.INSTRUMENT_CLASS,
        outbound_side="SELL",
        price_field_key=fx.PRICE_FIELD_KEY,
        shape_price_field_key=fx.PRICE_FIELD_KEY,
    )
