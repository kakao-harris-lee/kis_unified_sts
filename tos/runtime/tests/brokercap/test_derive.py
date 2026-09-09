"""``tos_runtime.brokercap.derive`` tests (TOS Phase 4 plan §2 decision 4,
``docs/plans/2026-09-09-tos-phase4-scopes-and-verify-realization-plan.md``).
Hermetic — real config + the real, byte-immutable KIS draft INSTANCE file
under a repo-relative path (D1.4 read-only exception), never a mock.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tos.brokercap import Admissibility
from tos_runtime.brokercap.derive import (
    derive_item6_item12,
    load_active_instance_document,
)
from tos_runtime.brokercap.instance import (
    BrokerInstanceConfigError,
    load_instance_document,
)
from tos_runtime.brokercap.scopes import BrokerScopesConfig, load_broker_scopes

# tos/runtime/tests/brokercap/test_derive.py -> repo root is 4 parents up.
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
    raw["instance_path"] = str(_DRAFT_PATH)
    if mock_evidence_ok:
        for scope in raw["scopes"]:
            if scope["name"] == "MOCK_STOCK_ORDER":
                scope["profile_evidence_ok"] = True
    path = tmp_path / "broker_scopes.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_broker_scopes(path, environment_label="paper-env-7")


def _scope(config: BrokerScopesConfig, name: str):
    return next(s for s in config.scopes if s.name == name)


# ===========================================================================
# SYNTHETIC_FUTURES_ORDER — no instance block, endpoint_class SYNTHETIC
# ===========================================================================


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


# ===========================================================================
# REAL_READ — broker-reaching (BROKER_GET), instance environment REAL_PROD
# (which fails to load — the real draft's known REAL_PROD gap)
# ===========================================================================


def test_real_read_item6_true_structurally_admissible_and_bound(
    tmp_path: Path,
) -> None:
    config = _load_config(tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER")
    scope = _scope(config, "REAL_READ")
    assert scope.admissibility is Admissibility.ADMISSIBLE

    fields = derive_item6_item12(scope, config, instance=None)

    assert fields.account_instrument_action_allowed is True
    # item 12: broker-reaching + no loadable instance -> honestly not current.
    assert fields.broker_constraint_generation_current is False
    assert fields.broker_capability_profile is None
    assert fields.broker_profile_version_current is False


def test_real_read_instance_binding_fails_to_load_the_known_real_prod_gap(
    tmp_path: Path,
) -> None:
    """Wave-1 fact: the real draft's REAL_PROD document lacks both
    ``profile_identity._model_view`` and ``live_scope._model_view`` — the
    loader honestly refuses rather than inventing them."""
    config = _load_config(tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER")
    scope = _scope(config, "REAL_READ")
    assert scope.instance is not None
    with pytest.raises(BrokerInstanceConfigError, match="profile_identity"):
        load_instance_document(
            config.instance_path, environment=scope.instance.environment
        )


# ===========================================================================
# MOCK_STOCK_ORDER — broker-reaching (BROKER_ORDER), instance MOCK_VTS loads
# ===========================================================================


def test_mock_stock_order_item6_false_when_evidence_not_positive(
    tmp_path: Path,
) -> None:
    config = _load_config(tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER")
    scope = _scope(config, "MOCK_STOCK_ORDER")
    assert scope.admissibility is Admissibility.PROHIBITED  # profile_evidence_ok: null

    instance = load_instance_document(config.instance_path, environment="MOCK_VTS")
    fields = derive_item6_item12(scope, config, instance)

    assert fields.account_instrument_action_allowed is False
    assert fields.broker_capability_profile is instance.profile
    assert fields.required_capability_set is scope.required_capability_set
    assert fields.required_capability_set is not None
    # item 12: DRAFT + approvers=[] -> never current, regardless of item 6.
    assert fields.broker_constraint_generation_current is False
    assert fields.broker_profile_version_current is False


def test_mock_stock_order_item6_true_when_evidence_positive_but_reduced_scope(
    tmp_path: Path,
) -> None:
    """``profile_evidence_ok: true`` makes the SCOPE's own admissibility
    REDUCED (not ADMISSIBLE) — item 6's ``admissibility is ADMISSIBLE`` gate
    is therefore still False for a REDUCED scope, by design (plan §2
    decision 4 names ``ADMISSIBLE`` specifically, never ``REDUCED``)."""
    config = _load_config(
        tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER", mock_evidence_ok=True
    )
    scope = _scope(config, "MOCK_STOCK_ORDER")
    assert scope.admissibility is Admissibility.REDUCED

    instance = load_instance_document(config.instance_path, environment="MOCK_VTS")
    fields = derive_item6_item12(scope, config, instance)
    assert fields.account_instrument_action_allowed is False


# ===========================================================================
# REAL_ORDER — always PROHIBITED, broker-reaching, instance REAL_PROD (fails)
# ===========================================================================


def test_real_order_item6_false_always_prohibited(tmp_path: Path) -> None:
    config = _load_config(tmp_path, active_scope="SYNTHETIC_FUTURES_ORDER")
    scope = _scope(config, "REAL_ORDER")
    assert scope.admissibility is Admissibility.PROHIBITED

    fields = derive_item6_item12(scope, config, instance=None)

    assert fields.account_instrument_action_allowed is False
    assert fields.broker_constraint_generation_current is False
    # required_capability_set is still carried (visibility, module
    # docstring) even though this scope can never send.
    assert fields.required_capability_set is not None


# ===========================================================================
# load_active_instance_document — active-scope-only loading
# ===========================================================================


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
