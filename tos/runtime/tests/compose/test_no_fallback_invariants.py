"""§2-4 of the TOS rescope plan, collected in one module: **no MOCK → REAL order"""

from __future__ import annotations

import copy
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.brokercap.routing import AuthorizationClass, OperationClass
from tos_runtime.brokercap.scopes import (
    BrokerScopeConfigError,
    BrokerScopesConfig,
    EndpointClass,
    PrincipalClass,
    load_broker_scopes,
)
from tos_runtime.compose._transport_wiring import (
    TransportKind,
    TransportWiringError,
    refuse_transport_scope_mismatch,
)

from .test_transport_wiring import _BROKER_SCOPES_EXAMPLE_PATH, _ENVIRONMENT_LABEL

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_REPO_ROOT = Path(__file__).resolve().parents[4]

_DEPLOY_ROOT = _REPO_ROOT / "config" / "tos_runtime"

_DEPLOYED_SCOPE_TABLES: tuple[Path, ...] = tuple(
    sorted(_DEPLOY_ROOT.glob("*/broker_scopes.yaml"))
)

_SCOPE_TABLES: tuple[Path, ...] = (
    _BROKER_SCOPES_EXAMPLE_PATH,
    *_DEPLOYED_SCOPE_TABLES,
)

_READ_OPERATIONS = frozenset(
    {
        OperationClass.MARKET_DATA_READ,
        OperationClass.ACCOUNT_READ,
        OperationClass.CAPABILITY_PROBE,
    }
)

_REFUSAL_BY_KIND: Mapping[TransportKind, str] = {
    TransportKind.KIS_MOCK: "MOCK-shaped under BROKER_SIMULATION",
    TransportKind.SYNTHETIC: "non-broker-reaching (reaches_broker is False)",
}

_MOCK_STOCK_ORDER_SEND: Mapping[str, str] = {
    "environment": "BROKER_SIMULATION",
    "operation_class": "ORDER_SEND",
    "economic_effect": "BROKER_RESOURCE_ONLY",
    "asset_scope": "STOCK",
    "authorization_class": "MOCK_ORDER",
}


def _table_id(path: Path) -> str:
    return path.parent.name if path.name == "broker_scopes.yaml" else path.stem


def _raw(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), path
    return raw


def _load(
    path: Path,
    tmp_path: Path,
    *,
    active_scope: str | None = None,
    mutate: Callable[[dict[str, Any]], None] | None = None,
) -> BrokerScopesConfig:
    """Load ``path`` through the REAL loader, optionally with ``active_scope`` forced and"""
    raw = copy.deepcopy(_raw(path))
    if active_scope is not None:
        raw["active_scope"] = active_scope
    if mutate is not None:
        mutate(raw)
    instance = (path.parent / str(raw["instance_path"])).resolve()
    raw["instance_path"] = os.path.relpath(instance, tmp_path)
    copied = tmp_path / f"broker_scopes_{_table_id(path)}.yaml"
    copied.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_broker_scopes(copied, environment_label=_ENVIRONMENT_LABEL)


def _scope(raw: dict[str, Any], name: str) -> dict[str, Any]:
    return next(scope for scope in raw["scopes"] if scope["name"] == name)


def _read_scope_names(path: Path) -> tuple[str, ...]:
    """The READ-class scope names in ``path``, read from the file itself (the loader is"""
    return tuple(
        str(scope["name"])
        for scope in _raw(path)["scopes"]
        if scope.get("principal_class") == PrincipalClass.READ.value
    )


def test_the_sweep_sees_every_deployed_tree() -> None:
    """**Every deployed tree contributes exactly one scope table to the clauses below.**"""
    trees = sorted(path.name for path in _DEPLOY_ROOT.iterdir() if path.is_dir())
    assert trees, f"{_DEPLOY_ROOT} holds no deployed tree — has it moved?"
    swept = sorted(path.parent.name for path in _DEPLOYED_SCOPE_TABLES)
    assert swept == trees, (
        f"the sweep covers {swept} but {_DEPLOY_ROOT} holds {trees} — "
        f"{sorted(set(trees) - set(swept))} contribute no broker_scopes.yaml, so the "
        "clauses below say nothing about them"
    )


@pytest.mark.parametrize("table", _SCOPE_TABLES, ids=_table_id)
def test_no_committed_read_scope_declares_an_order_surface(
    table: Path, tmp_path: Path
) -> None:
    """**Every committed scope table, through the real loader.**"""
    config = _load(table, tmp_path, active_scope=_read_scope_names(table)[0])
    read_scopes = [
        scope for scope in config.scopes if scope.principal_class is PrincipalClass.READ
    ]
    assert read_scopes, f"{table}: no READ-class scope — the sweep below is vacuous"
    order_principals = {
        scope.principal
        for scope in config.scopes
        if scope.principal_class is PrincipalClass.ORDER
    }
    assert order_principals, f"{table}: no ORDER-class scope to be separate FROM"
    for scope in read_scopes:
        where = f"{table}::{scope.name}"
        assert scope.endpoint_class is EndpointClass.BROKER_GET, where
        assert scope.allowed_methods == ("GET",), f"{where}: {scope.allowed_methods}"
        assert scope.principal not in order_principals, where
        for capability in scope.capability_tuples:
            assert capability.operation_class in _READ_OPERATIONS, (
                where,
                capability.operation_class,
            )
            assert (
                capability.authorization_class
                is AuthorizationClass.NON_AUTHORIZING_READ
            ), (where, capability.authorization_class)


@pytest.mark.parametrize("kind", list(TransportKind), ids=lambda k: k.value)
@pytest.mark.parametrize("table", _SCOPE_TABLES, ids=_table_id)
def test_a_read_scope_can_never_be_the_active_scope_of_either_transport(
    table: Path, kind: TransportKind, tmp_path: Path
) -> None:
    """**The order path is not composable while a read principal is active.**"""
    expected = _REFUSAL_BY_KIND.get(kind)
    assert expected is not None, f"no refusal reason pinned for transport kind {kind}"
    for name in _read_scope_names(table):
        config = _load(table, tmp_path, active_scope=name)
        with pytest.raises(TransportWiringError) as refusal:
            refuse_transport_scope_mismatch(kind, config)
        message = str(refusal.value)
        assert name in message, message
        assert expected in message, message


@pytest.mark.parametrize(
    ("capability", "refusal_says"),
    [
        pytest.param(
            _MOCK_STOCK_ORDER_SEND,
            "appears in both",
            id="mock-stock-order-send",
        ),
        pytest.param(
            {**_MOCK_STOCK_ORDER_SEND, "asset_scope": "FUTURES"},
            "is PROHIBITED",
            id="mock-futures-order-send",
        ),
        pytest.param(
            {
                **_MOCK_STOCK_ORDER_SEND,
                "environment": "BROKER_PRODUCTION",
                "authorization_class": "REAL_ORDER",
            },
            "is PROHIBITED",
            id="real-order-send",
        ),
    ],
)
def test_a_read_scope_cannot_acquire_an_order_capability(
    capability: Mapping[str, str], refusal_says: str, tmp_path: Path
) -> None:
    """**The config edit an operator reaching for a fallback would actually make.**"""

    def mutate(raw: dict[str, Any]) -> None:
        scope = _scope(raw, "REAL_READ")
        scope["endpoint_class"] = "BROKER_ORDER"
        scope["allowed_methods"] = ["SUBMIT"]
        scope["profile_evidence_ok"] = True
        scope["instance"] = {
            "environment": "MOCK_VTS",
            "degraded_since_authorization": False,
        }
        scope["profile_key"]["environment"] = "MOCK_VTS"
        scope["capability_tuples"] = [dict(capability)]

    with pytest.raises(BrokerScopeConfigError) as refusal:
        _load(
            _BROKER_SCOPES_EXAMPLE_PATH,
            tmp_path,
            active_scope="REAL_READ",
            mutate=mutate,
        )
    assert refusal_says in str(refusal.value), str(refusal.value)


def test_the_read_principal_can_never_be_the_order_principal(tmp_path: Path) -> None:
    """**The second shape of "the read-only principal reaches an order endpoint": keep"""

    def mutate(raw: dict[str, Any]) -> None:
        read_principal = _scope(raw, "REAL_READ")["principal"]
        _scope(raw, "MOCK_STOCK_ORDER")["principal"] = read_principal
        _scope(raw, "MOCK_STOCK_ORDER")["profile_evidence_ok"] = True

    with pytest.raises(BrokerScopeConfigError) as refusal:
        _load(
            _BROKER_SCOPES_EXAMPLE_PATH,
            tmp_path,
            active_scope="MOCK_STOCK_ORDER",
            mutate=mutate,
        )
    message = str(refusal.value)
    assert "share principal" in message, message
    assert "REAL_READ" in message and "MOCK_STOCK_ORDER" in message, message


_ORDER_SURFACE: Mapping[str, Any] = {
    "endpoint_class": "BROKER_ORDER",
    "allowed_methods": ["SUBMIT", "CANCEL_REPLACE"],
    "capability_tuples": [dict(_MOCK_STOCK_ORDER_SEND)],
}


def _order_shaped_read_scope(raw: dict[str, Any], **fields: Any) -> None:
    """Apply ``fields`` to ``REAL_READ`` and DELETE ``MOCK_STOCK_ORDER``."""
    raw["scopes"] = [
        scope for scope in raw["scopes"] if scope["name"] != "MOCK_STOCK_ORDER"
    ]
    scope = _scope(raw, "REAL_READ")
    scope["profile_evidence_ok"] = True
    scope["instance"] = {
        "environment": "MOCK_VTS",
        "degraded_since_authorization": False,
    }
    scope["profile_key"]["environment"] = "MOCK_VTS"
    scope.update(fields)


@pytest.mark.parametrize(
    ("fields", "offending_field"),
    [
        pytest.param(
            dict(_ORDER_SURFACE), "endpoint_class", id="review-998-order-surface"
        ),
        pytest.param(
            {"allowed_methods": ["GET", "SUBMIT"]},
            "allowed_methods",
            id="a-non-GET-method-beside-GET",
        ),
        pytest.param(
            {"capability_tuples": [dict(_MOCK_STOCK_ORDER_SEND)]},
            "capability_tuples[0].operation_class",
            id="an-order-tuple-under-a-GET-endpoint",
        ),
    ],
)
def test_the_loader_refuses_a_read_scope_that_is_not_read_only(
    fields: Mapping[str, Any], offending_field: str, tmp_path: Path
) -> None:
    """**``principal_class: READ`` means BROKER_GET, GET and read-only tuples — checked"""
    with pytest.raises(BrokerScopeConfigError) as refusal:
        _load(
            _BROKER_SCOPES_EXAMPLE_PATH,
            tmp_path,
            active_scope="REAL_READ",
            mutate=lambda raw: _order_shaped_read_scope(raw, **fields),
        )
    message = str(refusal.value)
    assert "REAL_READ" in message, message
    assert offending_field in message, message
    assert "principal_class READ" in message, message
