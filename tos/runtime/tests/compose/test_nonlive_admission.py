"""``tos_runtime.compose._nonlive_admission`` tests (TOS KIS MOCK transport
plan T2 lane B; plan §2 decision 7 / §7 operator disposition row 1,
``docs/plans/2026-09-10-tos-kis-mock-transport-plan.md``).

Hermetic (D1.4) — every write stays under ``tmp_path``; the Broker
Capability Profile INSTANCE document is loaded READ-ONLY from
``docs/broker-profiles/`` (never written), the same pattern
``tos/runtime/tests/brokercap/test_instance.py`` already uses (reads are
never restricted by the write guard).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
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
from tos.egressgw import TransportNature
from tos_runtime.brokercap.instance import InstanceDocument, load_instance_document
from tos_runtime.brokercap.scopes import (
    BrokerScope,
    EndpointClass,
    PrincipalClass,
    ScopeInstanceBinding,
    load_broker_scopes,
)
from tos_runtime.brokercap.scopes import transport_nature as scope_transport_nature
from tos_runtime.compose._nonlive_admission import (
    NonLiveAdmissionVerdict,
    nonlive_broker_consuming_admitted,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

# tos/runtime/tests/compose/test_nonlive_admission.py -> repo root is 4 parents up
# (same depth as tos/runtime/tests/brokercap/test_instance.py's own _REPO_ROOT).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DRAFT_PATH = (
    _REPO_ROOT / "docs" / "broker-profiles" / "KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
)
_BROKER_SCOPES_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "broker_scopes.example.yaml"
)


@pytest.fixture(scope="module")
def mock_vts_document() -> InstanceDocument:
    return load_instance_document(_DRAFT_PATH, environment="MOCK_VTS")


@pytest.fixture(scope="module")
def real_prod_document() -> InstanceDocument:
    return load_instance_document(_DRAFT_PATH, environment="REAL_PROD")


# ============================================================================
# Fixtures — a minimal MOCK_STOCK_ORDER-shaped scope + capability tuples
# ============================================================================


def _mock_capability_tuple() -> CapabilityTuple:
    return CapabilityTuple(
        environment=BrokerEnvironment.BROKER_SIMULATION,
        operation_class=OperationClass.ORDER_SEND,
        economic_effect=EconomicEffect.BROKER_RESOURCE_ONLY,
        asset_scope=AssetScope.STOCK,
        authorization_class=AuthorizationClass.MOCK_ORDER,
    )


def _read_capability_tuple_broker_simulation() -> CapabilityTuple:
    """The OTHER admitted authorization_class (condition 3) — NON_AUTHORIZING_READ,
    still inside BROKER_SIMULATION."""
    return CapabilityTuple(
        environment=BrokerEnvironment.BROKER_SIMULATION,
        operation_class=OperationClass.MARKET_DATA_READ,
        economic_effect=EconomicEffect.NONE,
        asset_scope=AssetScope.STOCK,
        authorization_class=AuthorizationClass.NON_AUTHORIZING_READ,
    )


def _real_capability_tuple() -> CapabilityTuple:
    return CapabilityTuple(
        environment=BrokerEnvironment.BROKER_PRODUCTION,
        operation_class=OperationClass.ORDER_SEND,
        economic_effect=EconomicEffect.POSITION_OR_CASH,
        asset_scope=AssetScope.STOCK,
        authorization_class=AuthorizationClass.REAL_ORDER,
    )


def _mock_scope(
    *,
    admissibility: Admissibility = Admissibility.ADMISSIBLE,
    capability_tuples: tuple[CapabilityTuple, ...] | None = None,
    instance: ScopeInstanceBinding | None = ScopeInstanceBinding(
        environment="MOCK_VTS"
    ),
) -> BrokerScope:
    return BrokerScope(
        name="MOCK_STOCK_ORDER_TEST",
        capability_tuples=(
            capability_tuples
            if capability_tuples is not None
            else (_mock_capability_tuple(),)
        ),
        profile_key=ProfileKey(),
        principal_class=PrincipalClass.ORDER,
        principal="kis-mock-order-test",
        endpoint_class=EndpointClass.BROKER_ORDER,
        allowed_methods=("SUBMIT",),
        admissibility=admissibility,
        provenance=(),
        inside_boundary=True,
        environment_binding={},
        asset_binding={},
        instance=instance,
    )


_RISK_FALSE = TransportNature(risk_relevant_live=False)
_RISK_TRUE = TransportNature(risk_relevant_live=True)
_RISK_NONE = TransportNature()  # every field None, including risk_relevant_live


def _positive_kwargs(mock_vts_document: InstanceDocument) -> dict:
    """All five conditions positively satisfied."""
    return {
        "posture_admitted": True,
        "transport_nature": _RISK_FALSE,
        "active_scope": _mock_scope(),
        "instance_document": mock_vts_document,
    }


# ============================================================================
# All five positive -> admitted; each negated alone -> refused with the
# matching reason (team-lead spec)
# ============================================================================


def test_all_five_positive_admits(mock_vts_document: InstanceDocument) -> None:
    verdict = nonlive_broker_consuming_admitted(**_positive_kwargs(mock_vts_document))
    assert verdict.admitted is True
    assert verdict.reasons == ()


def test_verdict_is_the_documented_dataclass(
    mock_vts_document: InstanceDocument,
) -> None:
    verdict = nonlive_broker_consuming_admitted(**_positive_kwargs(mock_vts_document))
    assert isinstance(verdict, NonLiveAdmissionVerdict)
    assert verdict.admitted is True


def test_condition1_posture_false_refuses(mock_vts_document: InstanceDocument) -> None:
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["posture_admitted"] = False
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is False
    assert "posture_not_admitted" in verdict.reasons


def test_condition1_posture_none_refuses(mock_vts_document: InstanceDocument) -> None:
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["posture_admitted"] = None
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is False
    assert "posture_not_admitted" in verdict.reasons


def test_condition2_scope_prohibited_refuses(
    mock_vts_document: InstanceDocument,
) -> None:
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["active_scope"] = _mock_scope(admissibility=Admissibility.PROHIBITED)
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is False
    assert "scope_admissibility_not_admissible_or_reduced" in verdict.reasons


def test_condition2_scope_reduced_is_the_other_positive_value(
    mock_vts_document: InstanceDocument,
) -> None:
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["active_scope"] = _mock_scope(admissibility=Admissibility.REDUCED)
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is True


def test_condition2_active_scope_none_refuses(
    mock_vts_document: InstanceDocument,
) -> None:
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["active_scope"] = None
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is False
    assert "scope_admissibility_not_admissible_or_reduced" in verdict.reasons


def test_condition3_real_order_tuple_refuses(
    mock_vts_document: InstanceDocument,
) -> None:
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["active_scope"] = _mock_scope(capability_tuples=(_real_capability_tuple(),))
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is False
    assert "capability_tuples_not_mock_simulation" in verdict.reasons


def test_condition3_one_real_tuple_among_mock_tuples_still_refuses(
    mock_vts_document: InstanceDocument,
) -> None:
    """EVERY tuple must qualify — one REAL tuple alongside a MOCK one refuses."""
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["active_scope"] = _mock_scope(
        capability_tuples=(_mock_capability_tuple(), _real_capability_tuple())
    )
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is False
    assert "capability_tuples_not_mock_simulation" in verdict.reasons


def test_condition3_empty_capability_tuples_refuses(
    mock_vts_document: InstanceDocument,
) -> None:
    """An empty tuple set is never vacuously admitted by ``all()`` over nothing."""
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["active_scope"] = _mock_scope(capability_tuples=())
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is False
    assert "capability_tuples_not_mock_simulation" in verdict.reasons


def test_condition3_non_authorizing_read_in_broker_simulation_admits(
    mock_vts_document: InstanceDocument,
) -> None:
    """NON_AUTHORIZING_READ is the OTHER admitted authorization_class, not just
    MOCK_ORDER — still requires BROKER_SIMULATION."""
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["active_scope"] = _mock_scope(
        capability_tuples=(_read_capability_tuple_broker_simulation(),)
    )
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is True


def test_condition4_risk_relevant_live_true_refuses(
    mock_vts_document: InstanceDocument,
) -> None:
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["transport_nature"] = _RISK_TRUE
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is False
    assert "risk_relevant_live_not_false" in verdict.reasons


def test_condition4_risk_relevant_live_none_refuses(
    mock_vts_document: InstanceDocument,
) -> None:
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["transport_nature"] = _RISK_NONE
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is False
    assert "risk_relevant_live_not_false" in verdict.reasons


def test_condition4_transport_nature_none_refuses(
    mock_vts_document: InstanceDocument,
) -> None:
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["transport_nature"] = None
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is False
    assert "risk_relevant_live_not_false" in verdict.reasons


class _ReachesBrokerOnly:
    """A minimal duck type satisfying the KERNEL's own ``TransportNatureLike`` Protocol
    (``tos.engine.core`` — declares only ``reaches_broker``) but genuinely lacking
    ``risk_relevant_live``. Independent review MEDIUM-3: the caller-side ``typing.cast`` in
    ``RuntimeCoordinatorPreconditions.live_scope_authorized`` is a static-typing-only widening —
    at runtime, nothing stops a Protocol-conforming object shaped exactly like this from reaching
    condition 4."""

    reaches_broker = True


def test_condition4_a_reaches_broker_only_duck_type_refuses_rather_than_raises(
    mock_vts_document: InstanceDocument,
) -> None:
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["transport_nature"] = _ReachesBrokerOnly()
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is False
    assert "risk_relevant_live_not_false" in verdict.reasons


def test_condition5_instance_environment_mismatch_refuses(
    mock_vts_document: InstanceDocument,
) -> None:
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["active_scope"] = _mock_scope(
        instance=ScopeInstanceBinding(environment="REAL_PROD")
    )
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is False
    assert "instance_environment_mismatch" in verdict.reasons


def test_condition5_scope_with_no_instance_block_refuses(
    mock_vts_document: InstanceDocument,
) -> None:
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["active_scope"] = _mock_scope(instance=None)
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is False
    assert "instance_environment_mismatch" in verdict.reasons


def test_condition5_instance_document_none_refuses(
    mock_vts_document: InstanceDocument,
) -> None:
    kwargs = _positive_kwargs(mock_vts_document)
    kwargs["instance_document"] = None
    verdict = nonlive_broker_consuming_admitted(**kwargs)
    assert verdict.admitted is False
    assert "instance_environment_mismatch" in verdict.reasons


def test_every_argument_none_refuses_with_all_five_reasons() -> None:
    verdict = nonlive_broker_consuming_admitted(
        posture_admitted=None,
        transport_nature=None,
        active_scope=None,
        instance_document=None,
    )
    assert verdict.admitted is False
    assert len(verdict.reasons) == 5


# ============================================================================
# Full sweep — every scope in the real broker_scopes.example.yaml, every
# posture, with risk_relevant_live derived from the scope itself (not
# independently toggled) — only a MOCK_STOCK_ORDER-shaped scope with a
# positive posture ever admits; every REAL_* scope refuses for BOTH posture
# values, naming condition 3 among the reasons.
# ============================================================================


def _load_example_scopes_with_mock_stock_order_evidence() -> dict:
    """The shipped example, with MOCK_STOCK_ORDER's ``profile_evidence_ok``
    patched positive (mirrors ``tos/runtime/tests/brokercap/test_scopes.py``
    ``test_resolve_scope_reduced``) so its stamped admissibility is REDUCED
    rather than the shipped example's honest PROHIBITED (no P0-2 evidence
    yet — a scopes-loader fact this sweep does not re-litigate; it exercises
    this module's own condition boundaries instead)."""
    raw = yaml.safe_load(_BROKER_SCOPES_EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["active_scope"] = "SYNTHETIC_FUTURES_ORDER"
    for scope in raw["scopes"]:
        if scope["name"] == "MOCK_STOCK_ORDER":
            scope["profile_evidence_ok"] = True
    return raw


def test_full_sweep_only_mock_stock_order_shaped_scope_ever_admits(
    tmp_path: Path,
    mock_vts_document: InstanceDocument,
    real_prod_document: InstanceDocument,
) -> None:
    raw = _load_example_scopes_with_mock_stock_order_evidence()
    path = tmp_path / "broker_scopes.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    config = load_broker_scopes(path, environment_label="sweep-env")

    documents_by_environment = {
        "MOCK_VTS": mock_vts_document,
        "REAL_PROD": real_prod_document,
    }

    swept_a_mock_admission = False
    for scope in config.scopes:
        nature = scope_transport_nature(scope)
        instance_document = (
            documents_by_environment.get(scope.instance.environment)
            if scope.instance is not None
            else None
        )
        for posture in (True, False):
            verdict = nonlive_broker_consuming_admitted(
                posture_admitted=posture,
                transport_nature=nature,
                active_scope=scope,
                instance_document=instance_document,
            )
            if scope.name == "MOCK_STOCK_ORDER" and posture is True:
                assert verdict.admitted is True, (scope.name, posture, verdict.reasons)
                swept_a_mock_admission = True
            else:
                assert verdict.admitted is False, (scope.name, posture, verdict.reasons)
            if scope.name in ("REAL_READ", "REAL_ORDER"):
                assert "capability_tuples_not_mock_simulation" in verdict.reasons

    assert swept_a_mock_admission, "the sweep never exercised the one admitting case"
