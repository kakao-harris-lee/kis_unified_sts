"""``derive_item6_item12`` under option (a) "K" (operator decision 2026-10-23).

The MOCK_STOCK_ORDER scope (REDUCED, real MOCK_VTS INSTANCE draft) passes item 6 and takes
item 12 from the injected mock-account freshness. Every mutation of its tuples toward real money
— production environment, position/cash effect, real-order authorization, an unknown axis —
falls back to the ordinary rule: REDUCED fails item 6, and item 12 reads the profile approval
the draft does not have, whatever the mock source says.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import yaml
from tos.brokercap import (
    AuthorizationClass,
    BrokerEnvironment,
    CapabilityTuple,
    EconomicEffect,
)
from tos_runtime.brokercap import (
    BrokerScopesConfig,
    derive_item6_item12,
    load_active_instance_document,
    load_broker_scopes,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DRAFT = _REPO_ROOT / "docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
_EXAMPLE = Path(__file__).resolve().parents[2] / "config/broker_scopes.example.yaml"


def _mock_scopes(tmp_path: Path) -> BrokerScopesConfig:
    raw = yaml.safe_load(_EXAMPLE.read_text(encoding="utf-8"))
    raw["active_scope"] = "MOCK_STOCK_ORDER"
    raw["instance_path"] = str(_DRAFT)
    for scope in raw["scopes"]:
        if scope["name"] == "MOCK_STOCK_ORDER":
            scope["profile_evidence_ok"] = True
    path = tmp_path / "broker_scopes.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_broker_scopes(path, environment_label="non-live-test")


def _with_tuples(
    config: BrokerScopesConfig, tuples: tuple[CapabilityTuple, ...]
) -> BrokerScopesConfig:
    scope = dataclasses.replace(config.active_scope, capability_tuples=tuples)
    return dataclasses.replace(
        config,
        active_scope=scope,
        scopes=tuple(scope if s.name == scope.name else s for s in config.scopes),
    )


def _derive(config: BrokerScopesConfig, generation: bool | None):
    return derive_item6_item12(
        config.active_scope,
        config,
        load_active_instance_document(config),
        mock_generation_current=generation,
    )


def test_the_mock_scope_passes_item_6_and_takes_item_12_from_the_mock_source(
    tmp_path: Path,
) -> None:
    config = _mock_scopes(tmp_path)
    fields = _derive(config, True)
    assert fields.account_instrument_action_allowed is True
    assert fields.broker_constraint_generation_current is True
    assert "mock-account GET freshness" in fields.reason


@pytest.mark.parametrize("generation", [None, False])
def test_a_stale_or_absent_mock_source_fails_item_12(
    tmp_path: Path, generation: bool | None
) -> None:
    fields = _derive(_mock_scopes(tmp_path), generation)
    assert fields.broker_constraint_generation_current is False
    # item 6 is about the scope, not the account read
    assert fields.account_instrument_action_allowed is True


def _mutations(base: CapabilityTuple) -> list[CapabilityTuple]:
    return [
        base.model_copy(update={"environment": BrokerEnvironment.BROKER_PRODUCTION}),
        base.model_copy(update={"economic_effect": EconomicEffect.POSITION_OR_CASH}),
        base.model_copy(update={"authorization_class": AuthorizationClass.REAL_ORDER}),
        CapabilityTuple.model_construct(**{**base.model_dump(), "environment": None}),
        CapabilityTuple.model_construct(
            **{**base.model_dump(), "economic_effect": None}
        ),
    ]


@pytest.mark.parametrize("index", range(5))
def test_each_mutation_toward_real_money_is_refused_on_both_items(
    tmp_path: Path, index: int
) -> None:
    config = _mock_scopes(tmp_path)
    original = config.active_scope.capability_tuples
    mutated = _mutations(original[0])[index]
    fields = _derive(_with_tuples(config, (mutated, *original[1:])), True)
    # REDUCED without the mock class: item 6 refused, as before option (a)
    assert fields.account_instrument_action_allowed is False
    # item 12 ignores the mock source and reads the profile (no approvers -> False)
    assert fields.broker_constraint_generation_current is False
