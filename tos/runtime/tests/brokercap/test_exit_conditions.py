"""TOS Phase 4 plan §4 exit-condition battery (EC-1..EC-5) —
``docs/plans/2026-09-09-tos-phase4-scopes-and-verify-realization-plan.md``.

Hermetic: real config under ``tmp_path``, the real byte-immutable KIS draft
INSTANCE file (read-only), and (EC-2/EC-5) a real composed runtime driven
through one crossing event — never a mock of the gateway's own verify list.
"""

from __future__ import annotations

import ast
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

from ..compose import _fixtures as fx
from ..compose.conftest import config_dir as config_dir  # noqa: F401
from ..compose.conftest import custody_root as custody_root  # noqa: F401
from ..compose.conftest import data_dir as data_dir  # noqa: F401
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


def _load_example(tmp_path: Path, **overrides: str | bool) -> BrokerScopesConfig:
    raw = yaml.safe_load(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["active_scope"] = overrides.pop("active_scope", "SYNTHETIC_FUTURES_ORDER")
    raw["instance_path"] = str(_DRAFT_PATH)
    if overrides.pop("mock_evidence_ok", False):
        for scope in raw["scopes"]:
            if scope["name"] == "MOCK_STOCK_ORDER":
                scope["profile_evidence_ok"] = True
    path = tmp_path / "broker_scopes.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_broker_scopes(path, environment_label="paper-env-7")


# ===========================================================================
# EC-1 — MOCK -> REAL fallback mutation never admitted; no rewriting
# ===========================================================================


class TestEC1NoFallbackRewriting:
    """Plan §4 EC-1: a requested tuple with no exact scope match denies —
    :func:`resolve_scope` never widens across environments (already pinned
    exhaustively by lane A's own mutation evidence M-A,
    ``tos/runtime/tests/brokercap/test_scopes.py::
    test_mutation_evidence_m_a_shipped_resolver_never_widens_environment`` —
    not duplicated here)."""

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
        """AST-based negative-grep (plan §4 EC-1): ``.endpoint_class`` is
        read off a :class:`~tos_runtime.brokercap.scopes.BrokerScope` (a
        PROHIBITED scope included) ONLY inside the allowlisted trio —
        ``brokercap/scopes.py`` (loader + G-4 derivation),
        ``brokercap/derive.py`` (items 6/12), and ``compose/_wiring.py``
        (none currently, reserved for G-4 wiring). ``.principal`` is NOT
        scanned the same way: the attribute name alone is ambiguous in this
        codebase (``ComposeContextResolver.principal`` and
        ``FileCustody``'s own credential principal are unrelated concepts
        sharing the name) — a blanket scan would false-positive on today's
        correct code. A PROHIBITED scope's own principal never reaching a
        transport is instead guaranteed structurally: ``active_scope`` can
        never BE a PROHIBITED scope (boot refusal,
        ``test_active_scope_prohibited_refuses_to_load``), and G-4's own
        readers (``transport_nature``/``credential_route_inventory``, both
        allowlisted) never special-case admissibility when reading a
        principal for inventory visibility.
        """
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


# ===========================================================================
# EC-2 — read-only principal can never reach an order endpoint
# ===========================================================================


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
        # The READ principal DOES carry a usable credential/route (it reaches
        # a broker for reads) — the point is no ORDER-class scope shares it.
        assert by_principal[read_scope.principal].usable_credential is True

    def test_composing_with_active_principal_equal_to_read_principal_refuses_at_boot(
        self,
        config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        tmp_path: Path,
    ) -> None:
        # REAL_READ's principal after {environment_label} substitution
        # ("non-live-test", the environment_label _compose() always uses).
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
        """Kernel-level check: even if a transport LIES that the READ
        principal is synthetic/non-broker (a forged self-report),
        :func:`resolve_broker_applicability` refuses to accept it, because
        the injected credential-route inventory (built from the scope
        table) shows that exact principal DOES carry a usable credential
        and a broker route — corroboration always wins over self-report
        (design #34 §4.2 item 2)."""
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


# ===========================================================================
# EC-3 — futures REAL order capability never created by config/env alone
# ===========================================================================


class TestEC3ConfigAloneNeverCreatesFuturesRealOrder:
    """Plan §4 EC-3 (kernel rule 4). The load-refusal itself is lane A's own
    ``test_broker_production_futures_order_in_config_refuses_to_load_naming_scope``
    (``test_scopes.py``) — referenced, not duplicated. This class adds the
    M-B mutation evidence the plan asks for."""

    def test_illegal_axis_combination_refuses_naming_the_scope(
        self, tmp_path: Path
    ) -> None:
        raw = {
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
        """M-B: a loader rewritten to use ``model_construct``/``model_copy
        (update=`` would bypass the validated-construction seal (kernel rule
        4) — demonstrated directly against the kernel type, never against
        this loader (which the shipped source pins by negative-grep,
        ``test_scopes.py::test_no_model_construct_or_model_copy_update_in_
        brokercap_package``, extended to cover this file's new
        ``derive.py`` too via the same directory glob)."""
        illegal = CapabilityTuple.model_construct(
            environment=BrokerEnvironment.BROKER_PRODUCTION,
            operation_class=OperationClass.ORDER_SEND,
            economic_effect=EconomicEffect.POSITION_OR_CASH,
            asset_scope=AssetScope.FUTURES,
            authorization_class=AuthorizationClass.REAL_ORDER,
        )
        # The bypass succeeds at construction (no validator ran) — this IS
        # the mutation going red, which is exactly why the negative-grep
        # over the shipped loader source (never using model_construct) is
        # the real seal, not a runtime type check here.
        assert illegal.asset_scope is AssetScope.FUTURES
        with pytest.raises(ValidationError):
            CapabilityTuple(
                environment=BrokerEnvironment.BROKER_PRODUCTION,
                operation_class=OperationClass.ORDER_SEND,
                economic_effect=EconomicEffect.POSITION_OR_CASH,
                asset_scope=AssetScope.FUTURES,
                authorization_class=AuthorizationClass.REAL_ORDER,
            )


# ===========================================================================
# EC-4 — MOCK-unsupported conditions still measurable via evidence-bearing
# reads/probes
# ===========================================================================


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
        assert scope.admissibility is Admissibility.PROHIBITED  # null evidence


# ===========================================================================
# EC-5 — honesty test (NOT a pass): broker-reaching mock e2e denies honestly
# ===========================================================================


def _ec5_config_dir(config_dir: Path) -> Path:
    """Rewrite the standard fixture's ``broker_scopes.yaml`` to activate
    MOCK_STOCK_ORDER (REDUCED, real evidence flag) bound to the REAL MOCK_VTS
    INSTANCE document — every other config file is left as the standard
    fixture wrote it."""
    raw = yaml.safe_load(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    raw["active_scope"] = "MOCK_STOCK_ORDER"
    raw["instance_path"] = str(_DRAFT_PATH)
    for scope in raw["scopes"]:
        if scope["name"] == "MOCK_STOCK_ORDER":
            scope["profile_evidence_ok"] = True
    (config_dir / "broker_scopes.yaml").write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )
    return config_dir


class TestEC5HonestyNotAPass:
    """Plan §4 EC-5 — deliberately NOT satisfied (§7 운영자 확인 지점 1): this
    class pins the HONEST denial a broker-reaching mock scope produces
    today, never a fabricated pass."""

    def test_broker_reaching_mock_scope_never_even_reaches_the_gateway(
        self,
        config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        tmp_path: Path,
    ) -> None:
        """A REAL, EARLIER honest denial layer this compose root already
        has (TOS Phase 3 Wave 2 Lane B-R, ``tos_runtime.compose.
        _preconditions.RuntimeCoordinatorPreconditions.live_scope_authorized``):
        a broker-reaching transport (``reaches_broker is True``, G-4-derived
        from the active MOCK_STOCK_ORDER scope) is structurally refused
        under the ONLY supported governance posture (``NOT_AUTHORIZED``) —
        the tick halts at ``LIVE_SCOPE_NOT_AUTHORIZED`` BEFORE step 1, no
        pipeline, no gateway verification, no ledger mutation. Zero
        transport calls holds trivially here; item 6/12 honesty is proven
        at the gateway/kernel level directly below
        (:meth:`test_kernel_level_item6_item12_deny_honestly_for_the_broker_reaching_scope`),
        since this e2e path cannot reach the gateway at all for a
        broker-reaching scope."""
        _ec5_config_dir(config_dir)
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        results = runtime.run_once((event,))

        assert results[0].pipeline is None
        assert results[0].halt_reason is not None
        assert results[0].halt_reason.value == "LIVE_SCOPE_NOT_AUTHORIZED"
        assert runtime.transport.requests == ()
        assert runtime.gateway.verifications == ()

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_kernel_level_item6_item12_deny_honestly_for_the_broker_reaching_scope(
        self, tmp_path: Path
    ) -> None:
        """The plan §4 EC-5 honesty proof, driven directly against the
        kernel gateway (``tos.egressgw.verify_send_boundary``) with the
        SAME derived fields :mod:`tos_runtime.compose.context` would feed
        it — bypassing the earlier Coordinator-preconditions halt (previous
        test) purely to exercise items 6/12/deferred in isolation, exactly
        as the plan asks: item 6 DENIED naming brokercap's PROHIBITED
        verdict, item 12 UNKNOWN (DRAFT ⇒ not current), every deferred item
        (4/5/7/8/9/10) UNKNOWN — never NOT_APPLICABLE (that would claim
        this send was synthetic, which a broker-reaching scope never is)."""
        from tos.egress import RestrictiveLatchState
        from tos.egressgw import verify_send_boundary
        from tos.engine import AttemptRequest
        from tos_runtime.brokercap.scopes import transport_nature

        config = _load_example(
            tmp_path, active_scope="MOCK_STOCK_ORDER", mock_evidence_ok=True
        )
        scope = next(s for s in config.scopes if s.name == "MOCK_STOCK_ORDER")
        instance = load_instance_document(config.instance_path, environment="MOCK_VTS")
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
            venue_session_account_facts_current=True,
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
        assert item12.outcome is VerifyOutcome.UNKNOWN

        deferred_items = (
            SendVerifyItem.CURRENT_SAFETY_AUTHORITY_EPOCH,
            SendVerifyItem.VALID_LIVE_SCOPE,
            SendVerifyItem.HARD_SAFETY_ENVELOPE_VERSIONS,
            SendVerifyItem.SAFETY_DEVIATION,
            SendVerifyItem.SAFETY_INCIDENT,
            SendVerifyItem.SAFETY_MONITORING,
        )
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
        """The unchanged existing e2e hand-off count (module docstring) —
        items 6/12 SATISFIED for the SYNTHETIC default scope, now derived
        rather than attested."""
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


# ===========================================================================
# M-C — mutation evidence: a stubbed derive_item6_item12 would falsely pass
# ===========================================================================


class TestMutationEvidenceMC:
    """A ``derive_item6_item12`` stub that always returns ``True``/current
    would make EC-5's honesty assertions fail — demonstrating the shipped
    derivation is load-bearing, not decorative."""

    def test_constant_true_stub_would_break_the_ec5_prohibited_assertion(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config = _load_example(
            tmp_path, active_scope="MOCK_STOCK_ORDER", mock_evidence_ok=True
        )
        scope = next(s for s in config.scopes if s.name == "MOCK_STOCK_ORDER")
        instance = load_instance_document(config.instance_path, environment="MOCK_VTS")

        shipped = derive_item6_item12(scope, config, instance)
        assert shipped.account_instrument_action_allowed is False  # honest, PROHIBITED

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
        assert mutated.account_instrument_action_allowed is True  # the mutation, red

        with pytest.raises(AssertionError):
            assert mutated.account_instrument_action_allowed is False
