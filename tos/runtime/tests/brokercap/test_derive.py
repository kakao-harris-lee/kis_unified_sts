"""``tos_runtime.brokercap.derive`` tests (TOS Phase 4 plan §2 decision 4,"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from tos.brokercap import Admissibility, AssetScope
from tos_runtime.brokercap import derive as derive_module
from tos_runtime.brokercap.derive import (
    derive_item6_item12,
    load_active_instance_document,
)
from tos_runtime.brokercap.instance import load_instance_document
from tos_runtime.brokercap.scopes import BrokerScopesConfig, load_broker_scopes

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DRAFT_PATH = (
    _REPO_ROOT / "docs" / "broker-profiles" / "KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
)
_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "broker_scopes.example.yaml"
)


def _load_config(
    tmp_path: Path, *, active_scope: str, mock_evidence_ok: bool = False
) -> BrokerScopesConfig:
    raw = yaml.safe_load(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["active_scope"] = active_scope
    raw["instance_path"] = os.path.relpath(_DRAFT_PATH, tmp_path)
    if mock_evidence_ok:
        for scope in raw["scopes"]:
            if scope["name"] == "MOCK_STOCK_ORDER":
                scope["profile_evidence_ok"] = True
    path = tmp_path / "broker_scopes.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_broker_scopes(path, environment_label="paper-env-7")


def _scope(config: BrokerScopesConfig, name: str):
    return next(s for s in config.scopes if s.name == name)


def _instance_path(config: BrokerScopesConfig) -> Path:
    """``config.instance_path``, asserted present — every call site below"""
    path = config.instance_path
    assert path is not None
    return path


def test_synthetic_scope_item6_true_item12_true_no_instance_needed(
    tmp_path: Path,
) -> None:
    config = _load_config(tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER")
    scope = _scope(config, "SYNTHETIC_FUTURES_ORDER")
    assert scope.instance is None

    fields = derive_item6_item12(scope, config, instance=None)

    assert fields.account_instrument_action_allowed is True
    assert fields.broker_constraint_generation_current is True
    assert fields.broker_capability_profile is None
    assert fields.required_capability_set is None
    assert fields.broker_profile_version_current is None


def test_load_active_instance_document_is_none_for_synthetic_default(
    tmp_path: Path,
) -> None:
    config = _load_config(tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER")
    assert load_active_instance_document(config) is None


def test_synthetic_scope_binds_via_its_own_asset_binding_override(
    tmp_path: Path,
) -> None:
    """Independent-review finding F4: the SYNTHETIC scope declares its OWN"""
    config = _load_config(tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER")
    scope = _scope(config, "SYNTHETIC_FUTURES_ORDER")

    assert scope.asset_binding[AssetScope.FUTURES] == "SYNTHETIC_FUTURES"
    assert (
        config.asset_binding[AssetScope.FUTURES] == "DOMESTIC_STOCK_AND_INDEX_FUTURES"
    )
    assert scope.asset_binding != config.asset_binding


def test_synthetic_scope_asset_binding_override_is_load_bearing_mutation_m5(
    tmp_path: Path,
) -> None:
    """Mutation M5: corrupting ONLY the SYNTHETIC scope's own asset_binding"""
    raw = yaml.safe_load(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["active_scope"] = "SYNTHETIC_FUTURES_ORDER"
    raw["instance_path"] = os.path.relpath(_DRAFT_PATH, tmp_path)
    for scope_raw in raw["scopes"]:
        if scope_raw["name"] == "SYNTHETIC_FUTURES_ORDER":
            scope_raw["asset_binding"]["FUTURES"] = "MISMATCHED_INSTRUMENT_CLASS"
    path = tmp_path / "broker_scopes.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    config = load_broker_scopes(path, environment_label="paper-env-7")
    scope = _scope(config, "SYNTHETIC_FUTURES_ORDER")

    fields = derive_item6_item12(scope, config, instance=None)
    assert fields.account_instrument_action_allowed is False


def test_real_read_item6_true_structurally_admissible_and_bound(
    tmp_path: Path,
) -> None:
    config = _load_config(tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER")
    scope = _scope(config, "REAL_READ")
    assert scope.admissibility is Admissibility.ADMISSIBLE

    instance = load_instance_document(_instance_path(config), environment="REAL_PROD")
    fields = derive_item6_item12(scope, config, instance)

    assert fields.account_instrument_action_allowed is True
    assert fields.broker_constraint_generation_current is False
    assert fields.broker_capability_profile is instance.profile
    assert fields.broker_profile_version_current is False
    assert "instance=present" in fields.reason
    assert "-> False" in fields.reason


def test_real_read_instance_binds_to_the_real_prod_document(
    tmp_path: Path,
) -> None:
    """2026-09-10 instance-authoring act: the real draft's REAL_PROD document"""
    config = _load_config(tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER")
    scope = _scope(config, "REAL_READ")
    assert scope.instance is not None
    instance = load_instance_document(
        _instance_path(config), environment=scope.instance.environment
    )
    assert instance.environment == "REAL_PROD"
    assert instance.status == "DRAFT"
    assert instance.approvers == ()
    assert instance.verified_dimensions == frozenset()


def test_mock_stock_order_item6_false_when_evidence_not_positive(
    tmp_path: Path,
) -> None:
    config = _load_config(tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER")
    scope = _scope(config, "MOCK_STOCK_ORDER")
    assert scope.admissibility is Admissibility.PROHIBITED

    instance = load_instance_document(_instance_path(config), environment="MOCK_VTS")
    fields = derive_item6_item12(scope, config, instance)

    assert fields.account_instrument_action_allowed is False
    assert fields.broker_capability_profile is instance.profile
    assert fields.required_capability_set is scope.required_capability_set
    assert fields.required_capability_set is not None
    assert fields.broker_constraint_generation_current is False
    assert fields.broker_profile_version_current is False


def test_mock_stock_order_item6_true_for_the_reduced_mock_class(
    tmp_path: Path,
) -> None:
    """``profile_evidence_ok: true`` makes the SCOPE's own admissibility REDUCED (not"""
    config = _load_config(
        tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER", mock_evidence_ok=True
    )
    scope = _scope(config, "MOCK_STOCK_ORDER")
    assert scope.admissibility is Admissibility.REDUCED

    instance = load_instance_document(_instance_path(config), environment="MOCK_VTS")
    fields = derive_item6_item12(scope, config, instance)
    assert fields.account_instrument_action_allowed is True


def test_derive_item6_item12_threads_scopes_own_degraded_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Independent-review finding F5: ``derive_item6_item12`` must feed the"""
    config = _load_config(
        tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER", mock_evidence_ok=True
    )
    scope = _scope(config, "MOCK_STOCK_ORDER")
    assert scope.instance is not None
    assert scope.instance.degraded_since_authorization is None
    instance = load_instance_document(_instance_path(config), environment="MOCK_VTS")

    captured: dict[str, object] = {}
    original = derive_module.instance_version_current

    def _capturing(document, *, degraded_since_authorization):
        captured["degraded_since_authorization"] = degraded_since_authorization
        return original(
            document, degraded_since_authorization=degraded_since_authorization
        )

    monkeypatch.setattr(derive_module, "instance_version_current", _capturing)
    derive_item6_item12(scope, config, instance)
    assert captured["degraded_since_authorization"] is None


def test_real_order_item6_false_always_prohibited(tmp_path: Path) -> None:
    config = _load_config(tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER")
    scope = _scope(config, "REAL_ORDER")
    assert scope.admissibility is Admissibility.PROHIBITED

    fields = derive_item6_item12(scope, config, instance=None)

    assert fields.account_instrument_action_allowed is False
    assert fields.broker_constraint_generation_current is False
    assert fields.required_capability_set is not None


def test_load_active_instance_document_loads_mock_vts_for_active_mock_scope(
    tmp_path: Path,
) -> None:
    config = _load_config(
        tmp_path, active_scope="MOCK_STOCK_ORDER", mock_evidence_ok=True
    )
    document = load_active_instance_document(config)
    assert document is not None
    assert document.environment == "MOCK_VTS"
    assert document.artifact_id == "KIS-BCP-MOCK-VTS-DRAFT-0001"
    assert len(document.declared_dimensions) == 17
    assert document.verified_dimensions == frozenset()
