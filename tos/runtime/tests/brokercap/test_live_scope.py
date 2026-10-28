"""Item 5 — ``live_scope_valid`` (PR-3 option (a), operator decision 2026-10-22).

Each rule of :mod:`tos_runtime.brokercap.live_scope` has its own failing input below; the
valid case is the MOCK_STOCK_ORDER scope bound to the real MOCK_VTS INSTANCE draft, sealed to
the kis-mock transport's own endpoint.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path

import pytest
import yaml
from tos.brokercap import Admissibility
from tos.egress.state import EgressCoordinateSet
from tos_runtime.brokercap import (
    BrokerScopesConfig,
    credential_route_inventory,
    load_active_instance_document,
    load_broker_scopes,
)
from tos_runtime.brokercap.live_scope import live_scope_failures, live_scope_valid

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DRAFT = _REPO_ROOT / "docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
_EXAMPLE = Path(__file__).resolve().parents[2] / "config/broker_scopes.example.yaml"
_ENV = "non-live-test"
_GATEWAY = f"egressgw-{_ENV}"
_ENDPOINT = (
    "https://mock.example.invalid:29443/uapi/domestic-stock/v1/trading/order-cash"
)


def _scopes(
    tmp_path: Path, active: str, *, evidence_ok: bool = True
) -> BrokerScopesConfig:
    raw = yaml.safe_load(_EXAMPLE.read_text(encoding="utf-8"))
    raw["active_scope"] = active
    raw["instance_path"] = os.path.relpath(
        _DRAFT, tmp_path
    )  # relative, as committed trees (#958)
    for scope in raw["scopes"]:
        if scope["name"] == "MOCK_STOCK_ORDER":
            scope["profile_evidence_ok"] = evidence_ok
    path = tmp_path / "broker_scopes.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_broker_scopes(path, environment_label=_ENV)


def _sealed(**overrides: object) -> EgressCoordinateSet:
    values: dict[str, object] = {
        "endpoint": _ENDPOINT,
        "account": "12345678",
        "environment": _ENV,
        "action": "NEW_ORDER",
        "method": "SUBMIT",
        "route_identity": "kis-mock-route",
        "credential_generation": 0,
        "broker_session_generation": 0,
        "egress_generation": 1,
        "active_principal": _GATEWAY,
    }
    values.update(overrides)
    return EgressCoordinateSet(**values)  # type: ignore[arg-type]


def _judge(config: BrokerScopesConfig, **overrides: object) -> tuple[str, ...]:
    kwargs: dict[str, object] = {
        "sealed": _sealed(),
        "gateway_principal": _GATEWAY,
        "inventory": credential_route_inventory(config, active_principal=_GATEWAY),
        "transport_endpoint": _ENDPOINT,
        "environment_label": _ENV,
    }
    instance = overrides.pop("instance", load_active_instance_document(config))
    kwargs.update(overrides)
    return live_scope_failures(config, instance, **kwargs)  # type: ignore[arg-type]


def test_the_mock_stock_order_scope_sealed_to_its_own_endpoint_is_valid(
    tmp_path: Path,
) -> None:
    config = _scopes(tmp_path, "MOCK_STOCK_ORDER")
    assert _judge(config) == ()
    assert (
        live_scope_valid(
            config,
            load_active_instance_document(config),
            sealed=_sealed(),
            gateway_principal=_GATEWAY,
            inventory=credential_route_inventory(config, active_principal=_GATEWAY),
            transport_endpoint=_ENDPOINT,
            environment_label=_ENV,
        )
        is True
    )


def test_a_non_broker_scope_is_not_judged(tmp_path: Path) -> None:
    """The synthetic paper posture is unchanged: item 5 stays ``None`` (not consulted)."""
    config = _scopes(tmp_path, "SYNTHETIC_FUTURES_ORDER")
    assert (
        live_scope_valid(
            config,
            None,
            sealed=_sealed(endpoint="synthetic://paper/order"),
            gateway_principal=_GATEWAY,
            inventory=(),
            transport_endpoint=None,
            environment_label=_ENV,
        )
        is None
    )


def test_a_scope_that_no_longer_resolves_is_invalid(tmp_path: Path) -> None:
    """The boot loader refuses a PROHIBITED active scope; item 5 is the per-attempt check that
    the same scope, as judged now, still resolves to itself and not to PROHIBITED."""
    config = _scopes(tmp_path, "MOCK_STOCK_ORDER")
    prohibited = dataclasses.replace(
        config.active_scope, admissibility=Admissibility.PROHIBITED
    )
    mutated = dataclasses.replace(
        config,
        active_scope=prohibited,
        scopes=tuple(
            prohibited if s.name == prohibited.name else s for s in config.scopes
        ),
    )
    assert "resolve:PROHIBITED" in _judge(mutated)


def test_an_active_scope_absent_from_the_table_is_invalid(tmp_path: Path) -> None:
    config = _scopes(tmp_path, "MOCK_STOCK_ORDER")
    mutated = dataclasses.replace(
        config,
        scopes=tuple(s for s in config.scopes if s.name != config.active_scope.name),
    )
    assert "resolve:UNSUPPORTED_DENY" in _judge(mutated)


@pytest.mark.parametrize(
    ("overrides", "failure"),
    [
        ({"instance": None}, "instance:absent"),
        ({"sealed": _sealed(active_principal="egressgw-other")}, "principal:sealed"),
        ({"gateway_principal": "egressgw-other"}, "principal:sealed"),
        ({"inventory": ()}, "principal:not_a_broker_route"),
        ({"transport_endpoint": None}, "endpoint"),
        ({"sealed": _sealed(endpoint="synthetic://paper/order")}, "endpoint"),
        (
            {"transport_endpoint": _ENDPOINT.replace("mock.example", "real.example")},
            "endpoint",
        ),
        ({"sealed": _sealed(environment="live")}, "environment"),
        ({"environment_label": "live"}, "environment"),
    ],
)
def test_each_mismatch_with_the_sealed_tuple_is_invalid(
    tmp_path: Path, overrides: dict, failure: str
) -> None:
    config = _scopes(tmp_path, "MOCK_STOCK_ORDER")
    assert failure in _judge(config, **overrides)


def test_an_instance_for_another_environment_is_invalid(tmp_path: Path) -> None:
    config = _scopes(tmp_path, "MOCK_STOCK_ORDER")
    instance = load_active_instance_document(config)
    assert instance is not None
    wrong = dataclasses.replace(instance, environment="REAL_PROD")
    assert "instance:environment" in _judge(config, instance=wrong)


def test_a_principal_that_is_only_a_read_route_is_invalid(tmp_path: Path) -> None:
    """The MOCK order principal listed WITHOUT a broker route (as a read-only entry would be)."""
    config = _scopes(tmp_path, "MOCK_STOCK_ORDER")
    inventory = tuple(
        (
            e.model_copy(update={"broker_route": False})
            if e.principal == config.active_scope.principal
            else e
        )
        for e in credential_route_inventory(config, active_principal=_GATEWAY)
    )
    assert "principal:not_a_broker_route" in _judge(config, inventory=inventory)
