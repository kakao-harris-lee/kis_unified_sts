"""``tos_runtime.brokercap.scopes`` tests (TOS Phase 4 plan §2 decisions 1-2,
``docs/plans/2026-09-09-tos-phase4-scopes-and-verify-realization-plan.md``,
lane A wave 1). Hermetic — real config files under ``tmp_path`` only (D1.4).
"""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from tos.brokercap import (
    Admissibility,
    AssetScope,
    AuthorizationClass,
    BrokerEnvironment,
    CapabilityTuple,
    EconomicEffect,
    OperationClass,
    ProfileKey,
)
from tos_runtime.brokercap.scopes import (
    BrokerScope,
    BrokerScopeConfigError,
    BrokerScopesConfig,
    EndpointClass,
    PrincipalClass,
    ScopeDisposition,
    credential_route_inventory,
    load_broker_scopes,
    refuse_principal_collision,
    resolve_scope,
    transport_nature,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "broker_scopes.example.yaml"
)
_SCOPE_NAMES = (
    "SYNTHETIC_FUTURES_ORDER",
    "REAL_READ",
    "MOCK_STOCK_ORDER",
    "REAL_ORDER",
)


def _load_example_dict() -> dict:
    raw = yaml.safe_load(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["active_scope"] = "SYNTHETIC_FUTURES_ORDER"
    return raw


def _write(path: Path, content: dict) -> None:
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


def _scope_by_name(raw: dict, name: str) -> dict:
    for scope in raw["scopes"]:
        if scope["name"] == name:
            return scope
    raise KeyError(name)


def _minimal_scope(
    *,
    name: str = "SOME_SCOPE",
    principal_class: str = "SYNTHETIC",
    principal: str = "principal-{environment_label}",
    endpoint_class: str = "SYNTHETIC",
    allowed_methods: list | None = None,
    profile_evidence_ok: bool | None = None,
    inside_boundary: bool | None = True,
) -> dict:
    return {
        "name": name,
        "principal_class": principal_class,
        "principal": principal,
        "endpoint_class": endpoint_class,
        "allowed_methods": (
            allowed_methods if allowed_methods is not None else ["SUBMIT"]
        ),
        "profile_evidence_ok": profile_evidence_ok,
        "inside_boundary": inside_boundary,
        "profile_key": {},
        "capability_tuples": [
            {
                "environment": "SYNTHETIC",
                "operation_class": "ORDER_SEND",
                "economic_effect": "NONE",
                "asset_scope": "FUTURES",
                "authorization_class": "SYNTHETIC_ORDER",
            }
        ],
        "provenance": [],
    }


def _minimal_config(scopes: list[dict], *, active_scope: str | None) -> dict:
    return {
        "active_scope": active_scope,
        "environment_binding": {
            "SYNTHETIC": "SYNTHETIC",
            "BROKER_SIMULATION": "MOCK_VTS",
            "BROKER_PRODUCTION": "REAL_PROD",
        },
        "asset_binding": {
            "STOCK": "DOMESTIC_STOCK_AND_INDEX_FUTURES",
            "FUTURES": "DOMESTIC_STOCK_AND_INDEX_FUTURES",
        },
        "scopes": scopes,
    }


# ============================================================================
# Loader happy path — the shipped example config
# ============================================================================


def test_example_config_loads_with_active_scope_filled(tmp_path: Path) -> None:
    raw = _load_example_dict()
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    config = load_broker_scopes(path, environment_label="paper-env-7")

    assert {s.name for s in config.scopes} == set(_SCOPE_NAMES)
    assert config.active_scope.name == "SYNTHETIC_FUTURES_ORDER"

    by_name = {s.name: s for s in config.scopes}
    assert by_name["SYNTHETIC_FUTURES_ORDER"].admissibility is Admissibility.ADMISSIBLE
    assert by_name["REAL_READ"].admissibility is Admissibility.ADMISSIBLE
    # MOCK_STOCK_ORDER maps to the kernel's REDUCED-ceiling rule, but the
    # shipped example honestly leaves profile_evidence_ok null (no P0-2
    # evidence yet — task 4, operator lane) — the kernel fails that closed
    # to PROHIBITED (None/False both fail closed, never REDUCED); see
    # test_resolve_scope_reduced below for the positive-evidence case.
    assert by_name["MOCK_STOCK_ORDER"].admissibility is Admissibility.PROHIBITED
    assert by_name["REAL_ORDER"].admissibility is Admissibility.PROHIBITED

    assert (
        by_name["SYNTHETIC_FUTURES_ORDER"].principal_class is PrincipalClass.SYNTHETIC
    )
    assert by_name["REAL_READ"].principal_class is PrincipalClass.READ
    assert by_name["MOCK_STOCK_ORDER"].principal_class is PrincipalClass.ORDER
    assert by_name["REAL_ORDER"].principal_class is PrincipalClass.ORDER

    assert by_name["SYNTHETIC_FUTURES_ORDER"].endpoint_class is EndpointClass.SYNTHETIC
    assert by_name["REAL_READ"].endpoint_class is EndpointClass.BROKER_GET
    assert by_name["MOCK_STOCK_ORDER"].endpoint_class is EndpointClass.BROKER_ORDER
    assert by_name["REAL_ORDER"].endpoint_class is EndpointClass.BROKER_ORDER


def test_environment_label_substitution(tmp_path: Path) -> None:
    raw = _load_example_dict()
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    config = load_broker_scopes(path, environment_label="paper-env-7")
    by_name = {s.name: s for s in config.scopes}

    assert by_name["SYNTHETIC_FUTURES_ORDER"].principal == "synthetic-paper-paper-env-7"
    assert by_name["REAL_READ"].principal == "kis-read-paper-env-7"
    assert by_name["MOCK_STOCK_ORDER"].principal == "kis-mock-order-paper-env-7"
    assert by_name["REAL_ORDER"].principal == "kis-real-order-paper-env-7"


def test_principal_without_the_token_passes_through_unchanged(tmp_path: Path) -> None:
    raw = _minimal_config(
        [_minimal_scope(principal="fixed-principal-no-templating")],
        active_scope="SOME_SCOPE",
    )
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    config = load_broker_scopes(path, environment_label="paper-env-7")

    assert config.active_scope.principal == "fixed-principal-no-templating"


# ============================================================================
# Named-TBD null -> refuse to load
# ============================================================================


@pytest.mark.parametrize(
    "field",
    [
        "name",
        "principal_class",
        "principal",
        "endpoint_class",
        "allowed_methods",
        "inside_boundary",
    ],
)
def test_a_still_null_scope_field_refuses_to_load(tmp_path: Path, field: str) -> None:
    scope = _minimal_scope()
    scope[field] = None
    raw = _minimal_config(
        [scope], active_scope="SOME_SCOPE" if field != "name" else None
    )
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="named-TBD"):
        load_broker_scopes(path, environment_label="paper-env-7")


def test_non_boolean_inside_boundary_refuses_to_load(tmp_path: Path) -> None:
    scope = _minimal_scope(inside_boundary="yes")  # type: ignore[arg-type]
    raw = _minimal_config([scope], active_scope="SOME_SCOPE")
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="inside_boundary"):
        load_broker_scopes(path, environment_label="paper-env-7")


def test_null_active_scope_refuses_to_load(tmp_path: Path) -> None:
    raw = _minimal_config([_minimal_scope()], active_scope=None)
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="active_scope"):
        load_broker_scopes(path, environment_label="paper-env-7")


def test_active_scope_naming_unknown_scope_refuses_to_load(tmp_path: Path) -> None:
    raw = _minimal_config([_minimal_scope()], active_scope="NOT_A_REAL_SCOPE")
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="NOT_A_REAL_SCOPE"):
        load_broker_scopes(path, environment_label="paper-env-7")


def test_active_scope_prohibited_refuses_to_load(tmp_path: Path) -> None:
    raw = _load_example_dict()
    raw["active_scope"] = "REAL_ORDER"
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="PROHIBITED"):
        load_broker_scopes(path, environment_label="paper-env-7")


def test_empty_capability_tuples_refuses_to_load(tmp_path: Path) -> None:
    scope = _minimal_scope()
    scope["capability_tuples"] = []
    raw = _minimal_config([scope], active_scope="SOME_SCOPE")
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError):
        load_broker_scopes(path, environment_label="paper-env-7")


def test_null_environment_binding_entry_refuses_to_load(tmp_path: Path) -> None:
    raw = _minimal_config([_minimal_scope()], active_scope="SOME_SCOPE")
    raw["environment_binding"]["SYNTHETIC"] = None
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="environment_binding"):
        load_broker_scopes(path, environment_label="paper-env-7")


def test_unknown_environment_binding_key_refuses_to_load(tmp_path: Path) -> None:
    raw = _minimal_config([_minimal_scope()], active_scope="SOME_SCOPE")
    raw["environment_binding"]["NOT_AN_ENVIRONMENT"] = "SOMETHING"
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError):
        load_broker_scopes(path, environment_label="paper-env-7")


def test_null_asset_binding_entry_refuses_to_load(tmp_path: Path) -> None:
    raw = _minimal_config([_minimal_scope()], active_scope="SOME_SCOPE")
    raw["asset_binding"]["STOCK"] = None
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="asset_binding"):
        load_broker_scopes(path, environment_label="paper-env-7")


def test_missing_file_refuses_to_load(tmp_path: Path) -> None:
    with pytest.raises(BrokerScopeConfigError):
        load_broker_scopes(
            tmp_path / "does-not-exist.yaml", environment_label="paper-env-7"
        )


def test_not_a_mapping_refuses_to_load(tmp_path: Path) -> None:
    path = tmp_path / "broker_scopes.yaml"
    path.write_text(yaml.safe_dump(["not", "a", "mapping"]), encoding="utf-8")
    with pytest.raises(BrokerScopeConfigError):
        load_broker_scopes(path, environment_label="paper-env-7")


# ============================================================================
# Instance cross-check uses the scope's OWN resolved environment_binding
# (re-review finding: _check_instance_bindings used to validate against the
# config-wide table even for a scope carrying its own F4 override)
# ============================================================================


def test_instance_cross_check_uses_the_scopes_own_environment_binding(
    tmp_path: Path,
) -> None:
    """A scope declaring its own ``environment_binding`` override must have
    ``instance.environment`` cross-checked against THAT map, not the
    config-wide default — otherwise a scope could carry an override that
    silently disagrees with its own declared INSTANCE binding while the
    cross-check keeps passing against a table the scope no longer actually
    binds through (one-source-of-truth violation)."""
    raw = _load_example_dict()
    _scope_by_name(raw, "REAL_READ")["environment_binding"] = {
        "BROKER_PRODUCTION": "SYNTHETIC"
    }
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="REAL_READ"):
        load_broker_scopes(path, environment_label="paper-env-7")


def test_instance_cross_check_passes_when_the_override_agrees_with_instance(
    tmp_path: Path,
) -> None:
    """Positive companion: an override that maps BROKER_PRODUCTION to the
    SAME string the scope's ``instance.environment`` already names still
    loads cleanly — the cross-check is against the scope's own resolved
    map, not a blanket refusal of overrides."""
    raw = _load_example_dict()
    _scope_by_name(raw, "REAL_READ")["environment_binding"] = {
        "BROKER_PRODUCTION": "REAL_PROD"
    }
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    config = load_broker_scopes(path, environment_label="paper-env-7")
    real_read = next(s for s in config.scopes if s.name == "REAL_READ")
    assert real_read.environment_binding[BrokerEnvironment.BROKER_PRODUCTION] == (
        "REAL_PROD"
    )


# ============================================================================
# EC-3 — config alone can never create a futures REAL order capability
# ============================================================================


def test_broker_production_futures_order_in_config_refuses_to_load_naming_scope(
    tmp_path: Path,
) -> None:
    scope = _minimal_scope(
        name="ILLEGAL_SCOPE", principal_class="ORDER", endpoint_class="BROKER_ORDER"
    )
    scope["capability_tuples"] = [
        {
            "environment": "BROKER_PRODUCTION",
            "operation_class": "ORDER_SEND",
            "economic_effect": "POSITION_OR_CASH",
            "asset_scope": "FUTURES",
            "authorization_class": "REAL_ORDER",
        }
    ]
    raw = _minimal_config([scope], active_scope=None)
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="ILLEGAL_SCOPE"):
        load_broker_scopes(path, environment_label="paper-env-7")


def test_null_capability_tuple_axis_refuses_to_load(tmp_path: Path) -> None:
    scope = _minimal_scope()
    scope["capability_tuples"][0]["environment"] = None
    raw = _minimal_config([scope], active_scope=None)
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="SOME_SCOPE"):
        load_broker_scopes(path, environment_label="paper-env-7")


# ============================================================================
# Principal separation
# ============================================================================


def test_read_and_order_scopes_sharing_a_principal_refuses_to_load(
    tmp_path: Path,
) -> None:
    raw = _load_example_dict()
    _scope_by_name(raw, "MOCK_STOCK_ORDER")["principal"] = _scope_by_name(
        raw, "REAL_READ"
    )["principal"]
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="REAL_READ"):
        load_broker_scopes(path, environment_label="paper-env-7")


def test_synthetic_and_read_scopes_sharing_a_principal_refuses_to_load(
    tmp_path: Path,
) -> None:
    raw = _load_example_dict()
    _scope_by_name(raw, "REAL_READ")["principal"] = _scope_by_name(
        raw, "SYNTHETIC_FUTURES_ORDER"
    )["principal"]
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="SYNTHETIC_FUTURES_ORDER"):
        load_broker_scopes(path, environment_label="paper-env-7")


def test_same_class_scopes_sharing_a_principal_refuses_to_load(tmp_path: Path) -> None:
    """Independent-review finding F2: principal separation used to be
    enforced only ACROSS ``principal_class`` values — two scopes of the
    SAME class (e.g. two ``ORDER`` scopes) sharing a principal loaded
    without complaint. The generalized rule refuses ANY two distinct
    scopes sharing a principal, naming both."""
    scope_a = _minimal_scope(
        name="ORDER_A", principal_class="ORDER", principal="same-order"
    )
    scope_b = _minimal_scope(
        name="ORDER_B", principal_class="ORDER", principal="same-order"
    )
    scope_b["capability_tuples"][0]["operation_class"] = "CANCEL_REPLACE"
    raw = _minimal_config([scope_a, scope_b], active_scope="ORDER_A")
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="ORDER_A") as exc_info:
        load_broker_scopes(path, environment_label="paper-env-7")
    assert "ORDER_B" in str(exc_info.value)


def test_different_class_scopes_with_distinct_principals_still_load(
    tmp_path: Path,
) -> None:
    """Sanity companion to the F2 refusal above — two scopes with genuinely
    DISTINCT principals still load cleanly."""
    scope_a = _minimal_scope(
        name="ORDER_A", principal_class="ORDER", principal="order-a-principal"
    )
    scope_b = _minimal_scope(
        name="ORDER_B", principal_class="ORDER", principal="order-b-principal"
    )
    scope_b["capability_tuples"][0]["operation_class"] = "CANCEL_REPLACE"
    raw = _minimal_config([scope_a, scope_b], active_scope="ORDER_A")
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    config = load_broker_scopes(path, environment_label="paper-env-7")

    assert config.active_scope.name == "ORDER_A"


# ============================================================================
# Duplicate tuples across scopes — independent-review finding F3
# ============================================================================


def test_duplicate_capability_tuple_across_two_scopes_refuses_to_load(
    tmp_path: Path,
) -> None:
    """The SAME capability tuple listed in two different scopes must refuse
    at load — without this, ``resolve_scope`` would silently pick whichever
    scope appears FIRST in the YAML list, letting an earlier (more
    permissive) scope shadow a later (more restrictive) one for the exact
    same request."""
    scope_a = _minimal_scope(name="DUP_A", principal="dup-a-principal")
    scope_b = _minimal_scope(name="DUP_B", principal="dup-b-principal")
    # Both scopes carry the IDENTICAL default capability tuple.
    raw = _minimal_config([scope_a, scope_b], active_scope="DUP_A")
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="DUP_A") as exc_info:
        load_broker_scopes(path, environment_label="paper-env-7")
    assert "DUP_B" in str(exc_info.value)


def test_non_duplicate_tuples_across_scopes_load_cleanly(tmp_path: Path) -> None:
    scope_a = _minimal_scope(name="NODUP_A", principal="nodup-a-principal")
    scope_b = _minimal_scope(name="NODUP_B", principal="nodup-b-principal")
    scope_b["capability_tuples"][0]["operation_class"] = "CANCEL_REPLACE"
    raw = _minimal_config([scope_a, scope_b], active_scope="NODUP_A")
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    config = load_broker_scopes(path, environment_label="paper-env-7")
    assert {s.name for s in config.scopes} == {"NODUP_A", "NODUP_B"}


# ============================================================================
# Non-string values — independent-review finding F6
# ============================================================================


def test_non_string_principal_refuses_to_load_never_attributeerror(
    tmp_path: Path,
) -> None:
    scope = _minimal_scope()
    scope["principal"] = 12345
    raw = _minimal_config([scope], active_scope="SOME_SCOPE")
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="principal"):
        load_broker_scopes(path, environment_label="paper-env-7")


def test_non_string_binding_value_refuses_to_load(tmp_path: Path) -> None:
    raw = _minimal_config([_minimal_scope()], active_scope="SOME_SCOPE")
    raw["environment_binding"]["SYNTHETIC"] = 123
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)

    with pytest.raises(BrokerScopeConfigError, match="environment_binding"):
        load_broker_scopes(path, environment_label="paper-env-7")


# ============================================================================
# resolve_scope — EC-1, all four dispositions, never rewrites
# ============================================================================


@pytest.fixture()
def loaded_config(tmp_path: Path) -> BrokerScopesConfig:
    raw = _load_example_dict()
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)
    return load_broker_scopes(path, environment_label="paper-env-7")


def test_resolve_scope_admitted(loaded_config: BrokerScopesConfig) -> None:
    requested = CapabilityTuple(
        environment=BrokerEnvironment.SYNTHETIC,
        operation_class=OperationClass.ORDER_SEND,
        economic_effect=EconomicEffect.NONE,
        asset_scope=AssetScope.FUTURES,
        authorization_class=AuthorizationClass.SYNTHETIC_ORDER,
    )
    resolution = resolve_scope(loaded_config, requested)
    assert resolution.disposition is ScopeDisposition.ADMITTED
    assert (
        resolution.scope is not None
        and resolution.scope.name == "SYNTHETIC_FUTURES_ORDER"
    )


def test_resolve_scope_reduced(tmp_path: Path) -> None:
    """The kernel's REDUCED-ceiling rule fires only when ``profile_evidence_ok``
    is positively ``true`` — the shipped example config (loaded_config
    fixture) honestly leaves it ``null`` (no P0-2 evidence yet), which fails
    closed to PROHIBITED, so this test builds its own config with the
    evidence flag positively set to exercise the REDUCED path."""
    raw = _load_example_dict()
    _scope_by_name(raw, "MOCK_STOCK_ORDER")["profile_evidence_ok"] = True
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)
    config = load_broker_scopes(path, environment_label="paper-env-7")

    requested = CapabilityTuple(
        environment=BrokerEnvironment.BROKER_SIMULATION,
        operation_class=OperationClass.ORDER_SEND,
        economic_effect=EconomicEffect.BROKER_RESOURCE_ONLY,
        asset_scope=AssetScope.STOCK,
        authorization_class=AuthorizationClass.MOCK_ORDER,
    )
    resolution = resolve_scope(config, requested)
    assert resolution.disposition is ScopeDisposition.REDUCED
    assert resolution.scope is not None and resolution.scope.name == "MOCK_STOCK_ORDER"


def test_resolve_scope_mock_stock_order_prohibited_when_evidence_not_positive(
    loaded_config: BrokerScopesConfig,
) -> None:
    """The shipped example's honest ``profile_evidence_ok: null`` fails
    closed to PROHIBITED, never REDUCED (None/False both fail closed —
    kernel ``routing_admissibility`` docstring)."""
    requested = CapabilityTuple(
        environment=BrokerEnvironment.BROKER_SIMULATION,
        operation_class=OperationClass.ORDER_SEND,
        economic_effect=EconomicEffect.BROKER_RESOURCE_ONLY,
        asset_scope=AssetScope.STOCK,
        authorization_class=AuthorizationClass.MOCK_ORDER,
    )
    resolution = resolve_scope(loaded_config, requested)
    assert resolution.disposition is ScopeDisposition.PROHIBITED
    assert resolution.scope is not None and resolution.scope.name == "MOCK_STOCK_ORDER"


def test_resolve_scope_prohibited(loaded_config: BrokerScopesConfig) -> None:
    requested = CapabilityTuple(
        environment=BrokerEnvironment.BROKER_PRODUCTION,
        operation_class=OperationClass.ORDER_SEND,
        economic_effect=EconomicEffect.POSITION_OR_CASH,
        asset_scope=AssetScope.STOCK,
        authorization_class=AuthorizationClass.REAL_ORDER,
    )
    resolution = resolve_scope(loaded_config, requested)
    assert resolution.disposition is ScopeDisposition.PROHIBITED
    assert resolution.scope is not None and resolution.scope.name == "REAL_ORDER"


def test_resolve_scope_unsupported_deny_mock_futures_order_never_rewritten(
    loaded_config: BrokerScopesConfig,
) -> None:
    """A MOCK futures order has no scope at all (the upstream plan has no
    such row) — it must DENY, never fall back to a different, wider scope."""
    requested = CapabilityTuple(
        environment=BrokerEnvironment.BROKER_SIMULATION,
        operation_class=OperationClass.ORDER_SEND,
        economic_effect=EconomicEffect.BROKER_RESOURCE_ONLY,
        asset_scope=AssetScope.FUTURES,
        authorization_class=AuthorizationClass.MOCK_ORDER,
    )
    resolution = resolve_scope(loaded_config, requested)
    assert resolution.disposition is ScopeDisposition.UNSUPPORTED_DENY
    assert resolution.scope is None


# ============================================================================
# transport_nature — structural derivation per endpoint class
# ============================================================================


def _scope(
    endpoint_class: EndpointClass,
    *,
    principal: str = "p",
    authorization_class: AuthorizationClass = AuthorizationClass.SYNTHETIC_ORDER,
    inside_boundary: bool = True,
) -> BrokerScope:
    tup_kwargs = {
        "environment": BrokerEnvironment.SYNTHETIC,
        "operation_class": OperationClass.ORDER_SEND,
        "economic_effect": EconomicEffect.NONE,
        "asset_scope": AssetScope.FUTURES,
        "authorization_class": authorization_class,
    }
    if authorization_class is AuthorizationClass.REAL_ORDER:
        tup_kwargs.update(
            environment=BrokerEnvironment.BROKER_PRODUCTION,
            economic_effect=EconomicEffect.POSITION_OR_CASH,
            asset_scope=AssetScope.STOCK,
        )
    elif authorization_class is AuthorizationClass.NON_AUTHORIZING_READ:
        tup_kwargs.update(
            environment=BrokerEnvironment.BROKER_PRODUCTION,
            operation_class=OperationClass.MARKET_DATA_READ,
        )
    tup = CapabilityTuple(**tup_kwargs)
    return BrokerScope(
        name="TEST_SCOPE",
        capability_tuples=(tup,),
        profile_key=ProfileKey(),
        principal_class=PrincipalClass.SYNTHETIC,
        principal=principal,
        endpoint_class=endpoint_class,
        allowed_methods=("SUBMIT",),
        admissibility=Admissibility.ADMISSIBLE,
        provenance=(),
        inside_boundary=inside_boundary,
        environment_binding={BrokerEnvironment.SYNTHETIC: "SYNTHETIC"},
        asset_binding={AssetScope.FUTURES: "SYNTHETIC_FUTURES"},
    )


def test_transport_nature_synthetic_all_false() -> None:
    nature = transport_nature(_scope(EndpointClass.SYNTHETIC))
    assert nature.reaches_broker is False
    assert nature.credential_bearing is False
    assert nature.route_bearing is False
    assert nature.risk_relevant_live is False


def test_transport_nature_none_all_false() -> None:
    nature = transport_nature(_scope(EndpointClass.NONE))
    assert nature.reaches_broker is False
    assert nature.credential_bearing is False
    assert nature.route_bearing is False


def test_transport_nature_broker_get_all_true_reach() -> None:
    nature = transport_nature(
        _scope(
            EndpointClass.BROKER_GET,
            authorization_class=AuthorizationClass.NON_AUTHORIZING_READ,
        )
    )
    assert nature.reaches_broker is True
    assert nature.credential_bearing is True
    assert nature.route_bearing is True
    assert nature.risk_relevant_live is False


def test_transport_nature_broker_order_all_true_reach() -> None:
    nature = transport_nature(_scope(EndpointClass.BROKER_ORDER))
    assert nature.reaches_broker is True
    assert nature.credential_bearing is True
    assert nature.route_bearing is True


def test_transport_nature_risk_relevant_live_true_only_for_real_order() -> None:
    nature = transport_nature(
        _scope(
            EndpointClass.BROKER_ORDER,
            authorization_class=AuthorizationClass.REAL_ORDER,
        )
    )
    assert nature.risk_relevant_live is True
    assert nature.principal == "p"


# ============================================================================
# credential_route_inventory
# ============================================================================


def test_credential_route_inventory_shape(loaded_config: BrokerScopesConfig) -> None:
    inventory = credential_route_inventory(
        loaded_config, active_principal="egressgw-paper-env-7"
    )
    by_principal = {entry.principal: entry for entry in inventory}

    assert len(inventory) == len(loaded_config.scopes) + 1
    assert by_principal["egressgw-paper-env-7"].usable_credential is False
    assert by_principal["egressgw-paper-env-7"].broker_route is False
    assert by_principal["egressgw-paper-env-7"].inside_boundary is True

    synthetic_entry = by_principal["synthetic-paper-paper-env-7"]
    assert synthetic_entry.usable_credential is False
    assert synthetic_entry.broker_route is False

    real_read_entry = by_principal["kis-read-paper-env-7"]
    assert real_read_entry.usable_credential is True
    assert real_read_entry.broker_route is True

    mock_order_entry = by_principal["kis-mock-order-paper-env-7"]
    assert mock_order_entry.usable_credential is True
    assert mock_order_entry.broker_route is True

    for entry in inventory:
        assert entry.inside_boundary is True


def test_credential_route_inventory_inside_boundary_is_scope_derived_not_hardcoded(
    tmp_path: Path,
) -> None:
    """Independent-review finding F1: a scope declared ``inside_boundary:
    false`` must produce an inventory entry with ``inside_boundary=False`` —
    never the old hardcoded ``True`` literal — and that flag must be
    LOAD-BEARING against the kernel's own boundary-disjointness predicate
    (``tos.egress.predicates.credential_route_authority_disjoint``): a
    broker-reaching (``usable_credential=True``, ``broker_route=True``)
    scope OUTSIDE the boundary is exactly the bypass condition
    EGRESS-INV-002 forbids."""
    from tos.egress.predicates import credential_route_authority_disjoint

    raw = _load_example_dict()
    _scope_by_name(raw, "REAL_READ")["inside_boundary"] = False
    path = tmp_path / "broker_scopes.yaml"
    _write(path, raw)
    config = load_broker_scopes(path, environment_label="paper-env-7")

    inventory = credential_route_inventory(
        config, active_principal="egressgw-paper-env-7"
    )
    by_principal = {entry.principal: entry for entry in inventory}
    real_read_entry = by_principal["kis-read-paper-env-7"]
    assert real_read_entry.inside_boundary is False
    assert real_read_entry.usable_credential is True
    assert real_read_entry.broker_route is True

    # Load-bearing: an outside-boundary principal with a usable credential
    # AND a broker route is exactly the bypass condition the kernel
    # predicate must catch — it does, honestly, once derived from config.
    assert credential_route_authority_disjoint(inventory) is False

    # Contrast: the SAME inventory shape but with every entry honestly
    # inside the boundary (the shipped example, unmodified) passes —
    # proving the flag (not something else) is what flips the verdict.
    baseline_raw = _load_example_dict()
    baseline_path = tmp_path / "broker_scopes_baseline.yaml"
    _write(baseline_path, baseline_raw)
    baseline_config = load_broker_scopes(baseline_path, environment_label="paper-env-7")
    baseline_inventory = credential_route_inventory(
        baseline_config, active_principal="egressgw-paper-env-7"
    )
    assert credential_route_authority_disjoint(baseline_inventory) is True


# ============================================================================
# refuse_principal_collision — G-4 generalization of R2
# ============================================================================


def test_refuse_principal_collision_raises_when_active_principal_matches_a_scope(
    loaded_config: BrokerScopesConfig,
) -> None:
    with pytest.raises(BrokerScopeConfigError, match="SYNTHETIC_FUTURES_ORDER"):
        refuse_principal_collision(
            loaded_config, active_principal="synthetic-paper-paper-env-7"
        )


def test_refuse_principal_collision_passes_for_a_distinct_principal(
    loaded_config: BrokerScopesConfig,
) -> None:
    refuse_principal_collision(loaded_config, active_principal="egressgw-paper-env-7")


# ============================================================================
# Negative-grep — no ambient env, no kernel-bypassing construction
# ============================================================================


def test_no_os_environ_or_getenv_in_brokercap_package() -> None:
    package_dir = (
        Path(__file__).resolve().parents[2] / "src" / "tos_runtime" / "brokercap"
    )
    for path in package_dir.glob("*.py"):
        if path.name == "instance.py":
            continue  # lane C's module — out of lane A's scope
        source = path.read_text(encoding="utf-8")
        assert "os.environ" not in source, f"{path}: os.environ found"
        assert "getenv(" not in source, f"{path}: getenv( found"


def test_no_model_construct_or_model_copy_update_in_brokercap_package() -> None:
    package_dir = (
        Path(__file__).resolve().parents[2] / "src" / "tos_runtime" / "brokercap"
    )
    for path in package_dir.glob("*.py"):
        if path.name == "instance.py":
            continue  # lane C's module — out of lane A's scope
        source = path.read_text(encoding="utf-8")
        assert "model_construct(" not in source, f"{path}: model_construct( found"
        assert "model_copy(update=" not in source, f"{path}: model_copy(update= found"


def test_no_consumer_of_a_prohibited_scopes_endpoint_class_outside_this_module() -> (
    None
):
    """EC-1: a PROHIBITED scope (REAL_ORDER) is listed for visibility only —
    no OTHER module in this runtime reads ``.endpoint_class`` to route a
    call. This module itself legitimately reads it (transport_nature /
    credential_route_inventory), so it is excluded from the scan."""
    runtime_src = Path(__file__).resolve().parents[2] / "src" / "tos_runtime"
    offenders = []
    for path in runtime_src.rglob("*.py"):
        if path.parent.name == "brokercap":
            continue
        source = path.read_text(encoding="utf-8")
        if ".endpoint_class" in source:
            offenders.append(path)
    assert offenders == []


# ============================================================================
# Mutation evidence M-A (EC-1) — a widening resolver would go red
# ============================================================================


def test_mutation_evidence_m_a_shipped_resolver_never_widens_environment(
    loaded_config: BrokerScopesConfig,
) -> None:
    """Demonstrates the discriminating power of EC-1's "never widen" rule.

    A SYNTHETIC market-data read has no scope in this config (only
    ``REAL_READ`` — ``BROKER_PRODUCTION`` only — covers reads) — the shipped
    :func:`resolve_scope` correctly denies it. A MUTATED resolver that
    retries with ``environment=BROKER_PRODUCTION`` on ``UNSUPPORTED_DENY``
    would incorrectly ADMIT it (silently promoting a synthetic read to a
    real-broker read) — this test proves that mutation goes red against the
    same assertion the shipped code satisfies.
    """
    requested = CapabilityTuple(
        environment=BrokerEnvironment.SYNTHETIC,
        operation_class=OperationClass.MARKET_DATA_READ,
        economic_effect=EconomicEffect.NONE,
        asset_scope=AssetScope.STOCK,
        authorization_class=AuthorizationClass.NON_AUTHORIZING_READ,
    )

    shipped_result = resolve_scope(loaded_config, requested)
    assert shipped_result.disposition is ScopeDisposition.UNSUPPORTED_DENY
    assert shipped_result.scope is None

    def _mutated_resolve(config: BrokerScopesConfig, requested: CapabilityTuple):
        result = resolve_scope(config, requested)
        if (
            result.disposition is ScopeDisposition.UNSUPPORTED_DENY
            and requested.environment is not BrokerEnvironment.BROKER_PRODUCTION
        ):
            widened = requested.model_copy(
                update={"environment": BrokerEnvironment.BROKER_PRODUCTION}
            )
            return resolve_scope(config, widened)
        return result

    mutated_result = _mutated_resolve(loaded_config, requested)
    assert (
        mutated_result.disposition is ScopeDisposition.ADMITTED
    )  # the bug, illustrated

    # The EC-1 guard itself: this is the assertion the shipped resolver
    # satisfies and the mutated one does NOT — proving the mutation is
    # caught (red) by the very check the shipped code passes (green).
    with pytest.raises(AssertionError):
        assert resolve_scope(loaded_config, requested).disposition is (
            ScopeDisposition.ADMITTED
        )


def test_mutation_evidence_m_a_exhaustive_sweep_never_admits_a_different_environment(
    loaded_config: BrokerScopesConfig,
) -> None:
    """Exhaustive sweep (5 enums, all constructible tuples): whenever
    :func:`resolve_scope` returns a scope, that scope must contain a tuple
    EXACTLY equal to what was requested — in particular sharing the same
    ``environment`` — never a different one reached by a widening retry."""
    axes = (
        BrokerEnvironment,
        OperationClass,
        EconomicEffect,
        AssetScope,
        AuthorizationClass,
    )
    checked = 0
    for environment, operation, economic, asset, authorization in itertools.product(
        *axes
    ):
        try:
            tup = CapabilityTuple(
                environment=environment,
                operation_class=operation,
                economic_effect=economic,
                asset_scope=asset,
                authorization_class=authorization,
            )
        except ValidationError:
            continue
        checked += 1
        resolution = resolve_scope(loaded_config, tup)
        if resolution.scope is not None:
            assert tup in resolution.scope.capability_tuples
            assert any(t.environment == tup.environment for t in (tup,))
        else:
            assert resolution.disposition is ScopeDisposition.UNSUPPORTED_DENY
    assert checked > 0
