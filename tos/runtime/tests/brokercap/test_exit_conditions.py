"""TOS Phase 4 plan §4 exit-condition battery (EC-1..EC-5) —"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError
from tos.brokercap import (
    Admissibility,
    AssetScope,
    AuthorizationClass,
    BrokerEnvironment,
    CapabilityTuple,
    ClaimKind,
    EconomicEffect,
    OperationClass,
    ProvenanceClass,
    provenance_admits_claim,
)
from tos.egressgw import (
    BrokerApplicability,
    SendBoundaryContext,
    TransportNature,
    resolve_broker_applicability,
)
from tos.egressgw.vocabulary import SendVerifyItem, VerifyOutcome
from tos_runtime.brokercap import derive as derive_module
from tos_runtime.brokercap.derive import Item6Item12Fields, derive_item6_item12
from tos_runtime.brokercap.instance import load_instance_document
from tos_runtime.brokercap.scopes import (
    BrokerScopeConfigError,
    BrokerScopesConfig,
    ScopeDisposition,
    credential_route_inventory,
    load_broker_scopes,
    resolve_scope,
)
from tos_runtime.compose._transport_wiring import TransportKind

from ..compose import _fixtures as fx
from ..compose.conftest import write_approval_file
from ..compose.test_compose_root import _compose, _reach_trusted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DRAFT_PATH = (
    _REPO_ROOT / "docs" / "broker-profiles" / "KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
)
_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "broker_scopes.example.yaml"
)
_RUNTIME_SRC = Path(__file__).resolve().parents[2] / "src" / "tos_runtime"


def _instance_path(config: BrokerScopesConfig) -> Path:
    """``config.instance_path``, asserted present — every call site below"""
    path = config.instance_path
    assert path is not None
    return path


def _load_example(tmp_path: Path, **overrides: str | bool) -> BrokerScopesConfig:
    raw = yaml.safe_load(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["active_scope"] = overrides.pop("active_scope", "SYNTHETIC_FUTURES_ORDER")
    raw["instance_path"] = os.path.relpath(_DRAFT_PATH, tmp_path)
    if overrides.pop("mock_evidence_ok", False):
        for scope in raw["scopes"]:
            if scope["name"] == "MOCK_STOCK_ORDER":
                scope["profile_evidence_ok"] = True
    path = tmp_path / "broker_scopes.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_broker_scopes(path, environment_label="paper-env-7")


class TestEC1NoFallbackRewriting:
    """Plan §4 EC-1: a requested tuple with no exact scope match denies —"""

    def test_broker_simulation_futures_mock_order_has_no_scope_unsupported_deny(
        self, tmp_path: Path
    ) -> None:
        config = _load_example(tmp_path)
        requested = CapabilityTuple(
            environment=BrokerEnvironment.BROKER_SIMULATION,
            operation_class=OperationClass.ORDER_SEND,
            economic_effect=EconomicEffect.BROKER_RESOURCE_ONLY,
            asset_scope=AssetScope.FUTURES,
            authorization_class=AuthorizationClass.MOCK_ORDER,
        )
        resolution = resolve_scope(config, requested)
        assert resolution.disposition is ScopeDisposition.UNSUPPORTED_DENY
        assert resolution.scope is None

    def test_no_consumer_of_endpoint_class_outside_the_allowlist(self) -> None:
        """AST-based negative-grep (plan §4 EC-1): ``.endpoint_class`` is"""
        allowlist = {"scopes.py", "derive.py", "_wiring.py"}
        offenders = []
        for path in _RUNTIME_SRC.rglob("*.py"):
            if path.name in allowlist:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr == "endpoint_class":
                    offenders.append(f"{path}:{node.lineno}")
        assert offenders == []


class TestEC2ReadPrincipalCannotReachOrder:
    """Plan §4 EC-2."""

    def test_credential_route_inventory_read_principal_shares_no_order_scope(
        self, tmp_path: Path
    ) -> None:
        config = _load_example(tmp_path)
        read_scope = next(s for s in config.scopes if s.name == "REAL_READ")
        order_scopes = [
            s
            for s in config.scopes
            if s.principal_class.value == "ORDER"
            and s.principal == read_scope.principal
        ]
        assert order_scopes == []

        inventory = credential_route_inventory(
            config, active_principal="egressgw-paper-env-7"
        )
        by_principal = {entry.principal: entry for entry in inventory}
        assert by_principal[read_scope.principal].usable_credential is True

    def test_composing_with_active_principal_equal_to_read_principal_refuses_at_boot(
        self,
        config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        tmp_path: Path,
    ) -> None:
        raw = yaml.safe_load((config_dir / "egress_coordinates.yaml").read_text())
        raw["active_principal"] = {"value": "kis-read-non-live-test"}
        (config_dir / "egress_coordinates.yaml").write_text(
            yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
        )
        with pytest.raises(BrokerScopeConfigError, match="REAL_READ"):
            _compose(tmp_path, config_dir, data_dir, custody_root)

    def test_read_principal_self_declared_synthetic_is_rejected_by_the_inventory(
        self, tmp_path: Path
    ) -> None:
        """Kernel-level check: even if a transport LIES that the READ"""
        config = _load_example(tmp_path)
        read_scope = next(s for s in config.scopes if s.name == "REAL_READ")
        inventory = credential_route_inventory(
            config, active_principal="some-other-gateway-principal"
        )
        forged_nature = TransportNature(
            principal=read_scope.principal,
            reaches_broker=False,
            credential_bearing=False,
            route_bearing=False,
            risk_relevant_live=False,
        )
        context = SendBoundaryContext(
            credential_route_inventory=inventory,
            non_live_test_environment_token="paper-env-7",
            scope_environment="paper-env-7",
            evidence_environment="paper-env-7",
            environment_inherited=False,
        )
        applicability = resolve_broker_applicability(forged_nature, context)
        assert applicability is BrokerApplicability.BROKER_RESOURCE_CONSUMING


class TestEC3ConfigAloneNeverCreatesFuturesRealOrder:
    """Plan §4 EC-3 (kernel rule 4). The load-refusal itself is lane A's own"""

    def test_illegal_axis_combination_refuses_naming_the_scope(
        self, tmp_path: Path
    ) -> None:
        raw: dict[str, Any] = {
            "active_scope": None,
            "environment_binding": {
                "SYNTHETIC": "SYNTHETIC",
                "BROKER_SIMULATION": "MOCK_VTS",
                "BROKER_PRODUCTION": "REAL_PROD",
            },
            "asset_binding": {
                "STOCK": "DOMESTIC_STOCK_AND_INDEX_FUTURES",
                "FUTURES": "DOMESTIC_STOCK_AND_INDEX_FUTURES",
            },
            "scopes": [
                {
                    "name": "ILLEGAL_SCOPE_EC3",
                    "principal_class": "ORDER",
                    "principal": "illegal-ec3",
                    "endpoint_class": "BROKER_ORDER",
                    "allowed_methods": ["SUBMIT"],
                    "profile_evidence_ok": None,
                    "profile_key": {},
                    "capability_tuples": [
                        {
                            "environment": "BROKER_PRODUCTION",
                            "operation_class": "ORDER_SEND",
                            "economic_effect": "POSITION_OR_CASH",
                            "asset_scope": "FUTURES",
                            "authorization_class": "REAL_ORDER",
                        }
                    ],
                    "provenance": [],
                }
            ],
        }
        path = tmp_path / "broker_scopes.yaml"
        path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        with pytest.raises(BrokerScopeConfigError, match="ILLEGAL_SCOPE_EC3"):
            load_broker_scopes(path, environment_label="paper-env-7")

    def test_os_environ_negative_grep_over_brokercap(self) -> None:
        package_dir = _RUNTIME_SRC / "brokercap"
        for path in package_dir.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "os.environ" not in source, f"{path}: os.environ found"
            assert "getenv(" not in source, f"{path}: getenv( found"

    def test_mutation_evidence_m_b_model_construct_would_bypass_the_seal(self) -> None:
        """M-B: a loader rewritten to use ``model_construct``/``model_copy"""
        illegal = CapabilityTuple.model_construct(
            environment=BrokerEnvironment.BROKER_PRODUCTION,
            operation_class=OperationClass.ORDER_SEND,
            economic_effect=EconomicEffect.POSITION_OR_CASH,
            asset_scope=AssetScope.FUTURES,
            authorization_class=AuthorizationClass.REAL_ORDER,
        )
        assert illegal.asset_scope is AssetScope.FUTURES
        with pytest.raises(ValidationError):
            CapabilityTuple(
                environment=BrokerEnvironment.BROKER_PRODUCTION,
                operation_class=OperationClass.ORDER_SEND,
                economic_effect=EconomicEffect.POSITION_OR_CASH,
                asset_scope=AssetScope.FUTURES,
                authorization_class=AuthorizationClass.REAL_ORDER,
            )


class TestEC4MockUnsupportedStillMeasurable:
    """Plan §4 EC-4."""

    def test_real_read_provenance_admits_measurement_never_real_order(
        self, tmp_path: Path
    ) -> None:
        config = _load_example(tmp_path)
        read_scope = next(s for s in config.scopes if s.name == "REAL_READ")
        assert read_scope.provenance, "expected at least one provenance entry"
        probe = read_scope.provenance[0]
        assert probe.provenance_class is ProvenanceClass.CONTROLLED_GET_PROBE
        assert probe.probe_manifest is not None
        assert probe.probe_manifest.emits_orders is False

        assert provenance_admits_claim(probe, ClaimKind.MEASURED_BOUND) is True
        assert provenance_admits_claim(probe, ClaimKind.REAL_ORDER_CAPABILITY) is False

    def test_mock_vts_instance_provenance_never_admits_real_order_capability(
        self,
    ) -> None:
        document = load_instance_document(_DRAFT_PATH, environment="MOCK_VTS")
        assert document.provenance, "expected produced provenance"
        for provenance in document.provenance:
            assert (
                provenance_admits_claim(provenance, ClaimKind.REAL_ORDER_CAPABILITY)
                is False
            )

    def test_mock_stock_order_reduced_only_with_positive_evidence(
        self, tmp_path: Path
    ) -> None:
        config = _load_example(tmp_path)
        scope = next(s for s in config.scopes if s.name == "MOCK_STOCK_ORDER")
        assert scope.admissibility is Admissibility.PROHIBITED


def _ec5_config_dir(config_dir: Path) -> Path:
    """Rewrite the standard fixture's ``broker_scopes.yaml`` to activate"""
    raw = yaml.safe_load(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["active_scope"] = "MOCK_STOCK_ORDER"
    raw["instance_path"] = os.path.relpath(_DRAFT_PATH, config_dir)
    for scope in raw["scopes"]:
        if scope["name"] == "MOCK_STOCK_ORDER":
            scope["profile_evidence_ok"] = True
    (config_dir / "broker_scopes.yaml").write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )
    return config_dir


class TestEC5HonestyNotAPass:
    """Plan §4 EC-5 — deliberately NOT satisfied (§7 운영자 확인 지점 1): this"""

    def test_broker_reaching_mock_scope_never_even_reaches_the_gateway(
        self,
        config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        tmp_path: Path,
    ) -> None:
        """A REAL, EARLIER honest denial layer this compose root already"""
        _ec5_config_dir(config_dir)
        fx.write_kis_mock_transport_config(config_dir)
        fx.provision_kis_mock_custody(custody_root)
        runtime = _compose(
            tmp_path,
            config_dir,
            data_dir,
            custody_root,
            transport_kind=TransportKind.KIS_MOCK,
        )
        _reach_trusted(runtime)
        event = fx.crossing_event()
        results = runtime.run_once((event,))

        assert results[0].pipeline is None
        assert results[0].halt_reason is not None
        assert results[0].halt_reason.value == "LIVE_SCOPE_NOT_AUTHORIZED"
        transport_evidence_rows = runtime.evidence_store.connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind LIKE 'TRANSPORT_%'"
        ).fetchone()[0]
        assert transport_evidence_rows == 0
        assert runtime.gateway.verifications == ()

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_kernel_level_item6_item12_deny_honestly_for_the_broker_reaching_scope(
        self, tmp_path: Path
    ) -> None:
        """The plan §4 EC-5 honesty proof, driven directly against the"""
        from tos.egress import RestrictiveLatchState
        from tos.egressgw import verify_send_boundary
        from tos.engine import AttemptRequest
        from tos_runtime.brokercap.scopes import transport_nature

        config = _load_example(
            tmp_path, active_scope="MOCK_STOCK_ORDER", mock_evidence_ok=True
        )
        scope = next(s for s in config.scopes if s.name == "MOCK_STOCK_ORDER")
        instance = load_instance_document(
            _instance_path(config), environment="MOCK_VTS"
        )
        derived = derive_item6_item12(scope, config, instance)
        nature = transport_nature(scope)
        assert nature.reaches_broker is True

        attempt = AttemptRequest(
            attempt_id="ec5-attempt",
            conformance_proof_digest="ec5-proof-digest",
            action_flow_permit_identity="ec5-permit",
            reference_coordinate_digest="ec5-reference",
        )
        context = SendBoundaryContext(
            transport_nature=nature,
            account_instrument_action_allowed=derived.account_instrument_action_allowed,
            broker_capability_profile=derived.broker_capability_profile,
            required_capability_set=derived.required_capability_set,
            broker_profile_version_current=derived.broker_profile_version_current,
            session_facts_current=True,
            tradability_facts_current=True,
            account_facts_current=True,
            broker_constraint_generation_current=(
                derived.broker_constraint_generation_current
            ),
            restrictive_latch_state=RestrictiveLatchState.CLEAR,
        )
        verification = verify_send_boundary(attempt=attempt, context=context)

        assert (
            verification.applicability is BrokerApplicability.BROKER_RESOURCE_CONSUMING
        )
        by_item = {v.item: v for v in verification.verdicts}

        item6 = by_item[
            SendVerifyItem.ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY
        ]
        assert item6.outcome is VerifyOutcome.DENIED
        assert "PROHIBITED" in (item6.reason or "")

        item12 = by_item[
            SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION
        ]
        assert item12.outcome is VerifyOutcome.DENIED
        assert "broker-constraint generation" in (item12.reason or "")

        deferred_items = (SendVerifyItem.VALID_LIVE_SCOPE,)
        for item in deferred_items:
            assert by_item[item].outcome is VerifyOutcome.UNKNOWN
            assert by_item[item].outcome is not VerifyOutcome.NOT_APPLICABLE
        assert not any(
            v.outcome is VerifyOutcome.NOT_APPLICABLE for v in verification.verdicts
        )

    def test_synthetic_default_still_gets_items_6_and_12_satisfied_derived(
        self,
        config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        tmp_path: Path,
    ) -> None:
        """The unchanged existing e2e hand-off count (module docstring) —"""
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        results = runtime.run_once((event,))
        proposal_digest = results[0].pipeline.proposal.canonical_digest
        construction = runtime.construction_stage.construction
        assert construction is not None and construction.intent is not None
        write_approval_file(
            custody_root,
            proposal_digest=proposal_digest,
            environment_label="non-live-test",
            approved_intent_envelope_digest=construction.intent.canonical_digest,
        )
        runtime.run_once((event,))

        assert len(runtime.transport.requests) == 1
        verification = runtime.gateway.verifications[-1]
        by_item = {v.item: v for v in verification.verdicts}
        assert (
            by_item[
                SendVerifyItem.ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY
            ].outcome
            is VerifyOutcome.SATISFIED
        )
        assert (
            by_item[
                SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION
            ].outcome
            is VerifyOutcome.SATISFIED
        )

        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestMutationEvidenceMC:
    """A ``derive_item6_item12`` stub that always returns ``True``/current"""

    def test_constant_true_stub_would_break_the_ec5_prohibited_assertion(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config = _load_example(
            tmp_path, active_scope="MOCK_STOCK_ORDER", mock_evidence_ok=True
        )
        scope = next(s for s in config.scopes if s.name == "MOCK_STOCK_ORDER")
        instance = load_instance_document(
            _instance_path(config), environment="MOCK_VTS"
        )

        shipped = derive_item6_item12(scope, config, instance)
        assert shipped.broker_constraint_generation_current is False

        def _stub_always_true(*_args: object, **_kwargs: object) -> Item6Item12Fields:
            return Item6Item12Fields(
                account_instrument_action_allowed=True,
                broker_constraint_generation_current=True,
                broker_capability_profile=instance.profile,
                required_capability_set=scope.required_capability_set,
                broker_profile_version_current=True,
                reason="mutation stub — always True",
            )

        monkeypatch.setattr(derive_module, "derive_item6_item12", _stub_always_true)
        mutated = derive_module.derive_item6_item12(scope, config, instance)
        assert mutated.broker_constraint_generation_current is True

        with pytest.raises(AssertionError):
            assert mutated.broker_constraint_generation_current is False


class TestF9SingleInstanceLoadPerBoot:
    """Independent-review finding F9: ``_wiring.py`` used to load the active"""

    def test_load_instance_document_called_at_most_once_per_boot(
        self,
        config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _ec5_config_dir(config_dir)
        fx.write_kis_mock_transport_config(config_dir)
        fx.provision_kis_mock_custody(custody_root)
        calls: list[int] = []
        original = derive_module.load_instance_document

        def _counting(*args: Any, **kwargs: Any) -> object:
            calls.append(1)
            return original(*args, **kwargs)

        monkeypatch.setattr(derive_module, "load_instance_document", _counting)
        runtime = _compose(
            tmp_path,
            config_dir,
            data_dir,
            custody_root,
            transport_kind=TransportKind.KIS_MOCK,
        )

        assert len(calls) == 1

        runtime.rcl_log.close()
        runtime.evidence_store.close()
