"""Compose e2e tests for :mod:`tos_runtime.compose._venue_wiring` (TOS venue constraint"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egressgw import fold_venue_admissibility
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose._venue_wiring import VenuePolicyScopeMismatch
from tos_runtime.compose.root import compose_paper_runtime

if TYPE_CHECKING:
    from tos_runtime.compose._venue_wiring import VenueServiceStage

from ..venue._documents import ocp_yaml, venue_policy_yaml
from . import _fixtures as fx
from .conftest import (
    _VENUE_POLICY_ACCOUNT,
    _VENUE_POLICY_ADMITTING_PHASE,
    _VENUE_POLICY_ENVIRONMENT,
    _VENUE_POLICY_INSTRUMENT,
    _VENUE_POLICY_INSTRUMENT_CLASS,
    call_wrapped_fixture,
)
from .conftest import config_dir as _config_dir_fixture
from .conftest import custody_root as _custody_root_fixture
from .conftest import data_dir as _data_dir_fixture
from .test_compose_root import (
    _action_flow_inputs,
    _action_flow_inputs_for,
    _aggregate_inputs,
    _compose,
    _LiveRuntimeFacts,
    _reach_trusted,
)
from .test_transport_wiring import _activate_mock_stock_order

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def _fresh_compose_dirs(root: Path) -> tuple[Path, Path, Path]:
    """Mirrors ``test_symmetry.py``'s own helper — one independent"""
    root.mkdir(parents=True, exist_ok=True)
    config_dir = call_wrapped_fixture(_config_dir_fixture, root)
    data_dir = call_wrapped_fixture(_data_dir_fixture, root)
    custody_root = call_wrapped_fixture(_custody_root_fixture, root)
    return config_dir, data_dir, custody_root


def _compose_with_construction(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    construction,
):
    """Mirrors ``test_compose_root.py``'s own ``_compose`` but takes a caller-supplied"""
    fx.write_band_strategy_file(config_dir)
    facts = _LiveRuntimeFacts()
    runtime = compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=construction,
        aggregate_risk_inputs_provider=_aggregate_inputs,
        action_flow_inputs_provider=_action_flow_inputs_for(facts),
        transport_kind=TransportKind.SYNTHETIC,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )
    facts.runtime = runtime
    return runtime


def _kind_count(runtime, kind: str) -> int:
    row = runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
    ).fetchone()
    count = row[0]
    assert isinstance(count, int), f"COUNT(*) returned {type(count).__name__}"
    return count


def _rows(runtime, kind: str) -> list[dict]:
    cursor = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
    )
    return [json.loads(row[0])["payload"] for row in cursor.fetchall()]


class TestVenueServiceE2E:
    def test_boot_binds_the_policies_once_and_step3_admits_with_the_real_decision(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        assert _kind_count(runtime, "VENUE_POLICY_BOUND") == 1
        assert _kind_count(runtime, "ORDER_CONSTRUCTION_POLICY_BOUND") == 1

        results = runtime.run_once((fx.crossing_event(),))
        assert results[0].flow is not None
        verdicts = {v.step: v for v in results[0].flow.verdicts}
        step3 = verdicts[CommitmentStep.VENUE_ADMISSIBILITY_DECISION]
        assert step3.outcome is StageOutcome.ADMIT

        decision = runtime.venue.last_decision
        assert decision is not None
        snapshot = runtime.venue.last_snapshot
        assert snapshot is not None
        fold = fold_venue_admissibility(
            observed_session_phase=snapshot.observed_session_phase,
            action_class=fx.ActionClass.NEW_LONG,
            snapshot=snapshot,
            policy=runtime.venue.policy,
            shape=runtime.venue_stage.resolved_shape,
            constraints=runtime.venue.shape_constraints,
        )
        assert decision.result is fold

        assert step3.bound_digest is not None
        assert step3.bound_digest == decision.canonical_digest
        assert step3.bound_identity == decision.decision_id

        assert runtime.context_resolver.instance_document is None
        assert decision.broker_capability_profile_version is None
        assert decision.broker_capability_profile_digest is None

        construction = runtime.construction_stage.construction
        assert construction is not None and construction.command is not None
        assert (
            decision.candidate_command_digest == construction.command.canonical_digest
        )

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_two_attempts_same_tick_issue_one_snapshot_and_two_decisions(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        event = fx.crossing_event()
        runtime.run_once((event,))
        runtime.run_once((event,))

        assert _kind_count(runtime, "VENUE_SNAPSHOT_ISSUED") == 1
        assert _kind_count(runtime, "ORDER_ADMISSIBILITY_DECISION_ISSUED") == 2
        snapshot_ids = {
            row["snapshot_id"]
            for row in _rows(runtime, "ORDER_ADMISSIBILITY_DECISION_ISSUED")
        }
        assert len(snapshot_ids) == 1

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_closed_phase_instant_denies_step3(
        self, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        (config_dir / "calendar.yaml").write_text(
            yaml.safe_dump(
                {
                    "calendar_version": "cal-compose-0",
                    "tz_id": "Asia/Seoul",
                    "holidays": [],
                    "sessions": {
                        fx.INSTRUMENT_CLASS: [
                            {
                                "phase": _VENUE_POLICY_ADMITTING_PHASE,
                                "start": "09:00",
                                "end": "15:30",
                                "days": ["MON", "TUE", "WED", "THU", "FRI"],
                                "crosses_midnight": False,
                            }
                        ]
                    },
                    "closed_phase": "CLOSED",
                    "futures_expiry": {},
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        saturday_kst = 1_789_779_600_000
        fx.write_band_strategy_file(config_dir)
        facts = _LiveRuntimeFacts()
        runtime = compose_paper_runtime(
            config_dir,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=_aggregate_inputs,
            action_flow_inputs_provider=_action_flow_inputs_for(facts),
            transport_kind=TransportKind.SYNTHETIC,
            wall_clock=FixedWallClockReference(saturday_kst),
        )
        facts.runtime = runtime
        _reach_trusted(runtime)

        results = runtime.run_once((fx.crossing_event(),))
        assert results[0].flow is not None
        verdicts = {v.step: v for v in results[0].flow.verdicts}
        step3 = verdicts[CommitmentStep.VENUE_ADMISSIBILITY_DECISION]
        assert step3.outcome is not StageOutcome.ADMIT
        assert runtime.venue is not None
        last_snapshot = runtime.venue.last_snapshot
        assert last_snapshot is not None
        assert last_snapshot.observed_session_phase == "CLOSED"

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_recompose_over_the_same_data_dir_strictly_increases_constraint_generation(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        runtime.run_once((fx.crossing_event(),))
        first_generation = runtime.venue.last_snapshot.constraint_generation
        runtime.rcl_log.close()
        runtime.evidence_store.close()

        runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime2)
        runtime2.run_once((fx.crossing_event(),))
        second_generation = runtime2.venue.last_snapshot.constraint_generation
        assert second_generation > first_generation

        runtime2.rcl_log.close()
        runtime2.evidence_store.close()

    def test_print_policy_digests_matches_the_venue_policy_bound_payload_digest(
        self,
        config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from tos_runtime.compose import cli

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        bound_digest = _rows(runtime, "VENUE_POLICY_BOUND")[0]["canonical_digest"]
        runtime.rcl_log.close()
        runtime.evidence_store.close()

        args = cli.parse_args(["print-policy-digests", "--config-dir", str(config_dir)])
        assert isinstance(args, cli.PrintPolicyDigestsArgs)
        exit_code = cli._dispatch_print_policy_digests(args)
        assert exit_code == 0
        out = capsys.readouterr().out
        match = re.search(r"VENUE_CONSTRAINT_POLICY \S+ \S+ (\S+)", out)
        assert match is not None
        assert match.group(1) == bound_digest


def test_the_retired_ocp_literals_do_not_appear_under_tos_runtime_src() -> None:
    """M4: the old ``policy_id="compose-ocp"``/``policy_version="ocp-v1"`` literals must never"""
    src_root = Path(__file__).resolve().parents[2] / "src" / "tos_runtime"
    offenders = []
    for path in src_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "compose-ocp" in text or '"ocp-v1"' in text:
            offenders.append(str(path))
    assert offenders == []


def test_compose_context_resolver_has_no_venue_decision_field() -> None:
    """M9: ``ComposeContextResolver`` must carry no ``venue_decision``/``venue_policy``/"""
    context_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "tos_runtime"
        / "compose"
        / "context.py"
    )
    tree = ast.parse(context_path.read_text(encoding="utf-8"))
    resolver = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "ComposeContextResolver"
    )
    field_names = {
        stmt.target.id
        for stmt in resolver.body
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
    }
    assert "venue_decision" not in field_names
    assert "venue_policy" not in field_names
    assert "venue_snapshot" not in field_names


def test_broker_capability_profile_facts_stay_none_for_a_real_draft_instance_document() -> (
    None
):
    """Loads the REAL, repo-tracked KIS draft INSTANCE document (the same file"""
    from tos_runtime.brokercap.instance import load_instance_document
    from tos_runtime.compose._venue_wiring import _broker_capability_profile_facts

    path = (
        Path(__file__).resolve().parents[4]
        / "docs"
        / "broker-profiles"
        / "KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
    )
    document = load_instance_document(path, environment="MOCK_VTS")
    assert document.status == "DRAFT"
    assert document.profile.canonical_digest is None

    version, digest = _broker_capability_profile_facts(document)
    assert digest is None
    profile_version = document.profile.profile_version
    assert profile_version is not None
    assert version == profile_version.profile_version
    assert version is not None


class TestVenueBootRefusals:
    def test_admitting_phase_token_not_in_calendar_refuses_to_boot(
        self, tmp_path: Path
    ) -> None:
        config_dir, data_dir, custody_root = _fresh_compose_dirs(tmp_path / "case")
        (config_dir / "venue_constraint_policy.yaml").write_text(
            venue_policy_yaml(
                environment=_VENUE_POLICY_ENVIRONMENT,
                account=_VENUE_POLICY_ACCOUNT,
                instrument=_VENUE_POLICY_INSTRUMENT,
                instrument_class=_VENUE_POLICY_INSTRUMENT_CLASS,
                price_min="1000",
                price_max="9000000",
                tick_size="500",
                lot_size="2",
                min_quantity="2",
                max_quantity="100",
                admitting_phases='["OPEN_X"]',
                admitting_phases_short='["OPEN_X"]',
            ),
            encoding="utf-8",
        )
        fx.write_band_strategy_file(config_dir)
        with pytest.raises(VenuePolicyScopeMismatch):
            compose_paper_runtime(
                config_dir,
                data_dir,
                custody_root,
                "non-live-test",
                construction=fx.construction_config(),
                aggregate_risk_inputs_provider=_aggregate_inputs,
                action_flow_inputs_provider=_action_flow_inputs,
                transport_kind=TransportKind.SYNTHETIC,
            )

    def test_instrument_class_mismatch_refuses_to_boot(
        self, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """(a′) wave lane D — mutation proof for plan §4.2's "``instrument_class``: literal"""
        fx.write_band_strategy_file(config_dir)
        with pytest.raises(VenuePolicyScopeMismatch, match="instrument_class"):
            compose_paper_runtime(
                config_dir,
                data_dir,
                custody_root,
                "non-live-test",
                construction=fx.construction_config(
                    instrument_class="not-the-real-class"
                ),
                aggregate_risk_inputs_provider=_aggregate_inputs,
                action_flow_inputs_provider=_action_flow_inputs,
                transport_kind=TransportKind.SYNTHETIC,
            )

    def test_kis_mock_wire_codec_null_refuses_at_compose_level(
        self, tmp_path: Path
    ) -> None:
        """MEDIUM (team-lead review, 2026-09-15): ``write_kis_mock_transport_config`` used to"""
        config_dir, data_dir, custody_root = _fresh_compose_dirs(tmp_path / "case")
        _activate_mock_stock_order(config_dir)
        fx.write_kis_mock_transport_config(config_dir, wire_codec=None)
        fx.provision_kis_mock_custody(custody_root)
        fx.write_band_strategy_file(config_dir)
        with pytest.raises(VenuePolicyScopeMismatch):
            compose_paper_runtime(
                config_dir,
                data_dir,
                custody_root,
                "non-live-test",
                construction=fx.construction_config(),
                aggregate_risk_inputs_provider=_aggregate_inputs,
                action_flow_inputs_provider=_action_flow_inputs,
                transport_kind=TransportKind.KIS_MOCK,
            )

    def test_synthetic_wire_codec_non_null_refuses_at_compose_level(
        self, tmp_path: Path
    ) -> None:
        """MEDIUM inverse (team-lead review, 2026-09-15): a ``synthetic`` transport boot with a"""
        config_dir, data_dir, custody_root = _fresh_compose_dirs(tmp_path / "case")
        (config_dir / "order_construction_policy.yaml").write_text(
            ocp_yaml(
                environment=_VENUE_POLICY_ENVIRONMENT,
                account=_VENUE_POLICY_ACCOUNT,
                instrument=_VENUE_POLICY_INSTRUMENT,
                wire_codec='{kind: kis-order-cash-v1, wire_fields: ["CANO"]}',
            ),
            encoding="utf-8",
        )
        fx.write_band_strategy_file(config_dir)
        with pytest.raises(VenuePolicyScopeMismatch):
            compose_paper_runtime(
                config_dir,
                data_dir,
                custody_root,
                "non-live-test",
                construction=fx.construction_config(),
                aggregate_risk_inputs_provider=_aggregate_inputs,
                action_flow_inputs_provider=_action_flow_inputs,
                transport_kind=TransportKind.SYNTHETIC,
            )

    def test_instrument_scope_mismatch_refuses_to_boot(self, tmp_path: Path) -> None:
        config_dir, data_dir, custody_root = _fresh_compose_dirs(tmp_path / "case")
        (config_dir / "venue_constraint_policy.yaml").write_text(
            venue_policy_yaml(
                environment=_VENUE_POLICY_ENVIRONMENT,
                account=_VENUE_POLICY_ACCOUNT,
                instrument="NOT-" + _VENUE_POLICY_INSTRUMENT,
                instrument_class=_VENUE_POLICY_INSTRUMENT_CLASS,
                price_min="1000",
                price_max="9000000",
                tick_size="500",
                lot_size="2",
                min_quantity="2",
                max_quantity="100",
                admitting_phases=f'["{_VENUE_POLICY_ADMITTING_PHASE}"]',
                admitting_phases_short=f'["{_VENUE_POLICY_ADMITTING_PHASE}"]',
            ),
            encoding="utf-8",
        )
        fx.write_band_strategy_file(config_dir)
        with pytest.raises(VenuePolicyScopeMismatch):
            compose_paper_runtime(
                config_dir,
                data_dir,
                custody_root,
                "non-live-test",
                construction=fx.construction_config(),
                aggregate_risk_inputs_provider=_aggregate_inputs,
                action_flow_inputs_provider=_action_flow_inputs,
                transport_kind=TransportKind.SYNTHETIC,
            )


class TestWireCodecCrossCheck:
    """M11, at the unit level: a full kis-mock e2e boot needs a whole scope/custody dance"""

    def test_null_wire_codec_with_kis_mock_transport_refuses(
        self, tmp_path: Path
    ) -> None:
        from tos_runtime.compose import _venue_wiring
        from tos_runtime.venue import load_order_construction_policy

        path = tmp_path / "order_construction_policy.yaml"
        path.write_text(ocp_yaml(wire_codec="null"), encoding="utf-8")
        loaded = load_order_construction_policy(path, scheme=_SCHEME)
        with pytest.raises(VenuePolicyScopeMismatch):
            _venue_wiring._cross_check_wire_codec(
                loaded, transport_kind=TransportKind.KIS_MOCK
            )

    def test_non_null_wire_codec_with_synthetic_transport_refuses(
        self, tmp_path: Path
    ) -> None:
        from tos_runtime.compose import _venue_wiring
        from tos_runtime.venue import load_order_construction_policy

        path = tmp_path / "order_construction_policy.yaml"
        path.write_text(
            ocp_yaml(wire_codec='{kind: kis-order-cash-v1, wire_fields: ["CANO"]}'),
            encoding="utf-8",
        )
        loaded = load_order_construction_policy(path, scheme=_SCHEME)
        with pytest.raises(VenuePolicyScopeMismatch):
            _venue_wiring._cross_check_wire_codec(
                loaded, transport_kind=TransportKind.SYNTHETIC
            )

    def test_exact_kis_order_cash_wire_codec_with_kis_mock_transport_admits(
        self, tmp_path: Path
    ) -> None:
        from tos_runtime.compose import _venue_wiring
        from tos_runtime.transport.kis_mock.codec import KIS_ORDER_CASH_WIRE_FIELDS
        from tos_runtime.venue import load_order_construction_policy

        path = tmp_path / "order_construction_policy.yaml"
        path.write_text(
            ocp_yaml(
                wire_codec=(
                    "{kind: kis-order-cash-v1, wire_fields: "
                    f"{sorted(KIS_ORDER_CASH_WIRE_FIELDS)!r}}}"
                )
            ),
            encoding="utf-8",
        )
        loaded = load_order_construction_policy(path, scheme=_SCHEME)
        _venue_wiring._cross_check_wire_codec(
            loaded, transport_kind=TransportKind.KIS_MOCK
        )

    def test_null_wire_codec_with_synthetic_transport_admits(
        self, tmp_path: Path
    ) -> None:
        from tos_runtime.compose import _venue_wiring
        from tos_runtime.venue import load_order_construction_policy

        path = tmp_path / "order_construction_policy.yaml"
        path.write_text(ocp_yaml(wire_codec="null"), encoding="utf-8")
        loaded = load_order_construction_policy(path, scheme=_SCHEME)
        _venue_wiring._cross_check_wire_codec(
            loaded, transport_kind=TransportKind.SYNTHETIC
        )


class TestDerivedQuantityReachesVenueGate:
    """decision 2: ``order_shape.quantity`` is judged from the derivation"""

    def test_derived_quantity_reaches_the_fold_not_the_literal(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        construction = fx.construction_config()
        runtime = _compose_with_construction(
            tmp_path, config_dir, data_dir, custody_root, construction
        )
        _reach_trusted(runtime)

        results = runtime.run_once((fx.crossing_event(),))
        verdicts = {v.step: v for v in results[0].flow.verdicts}
        step3 = verdicts[CommitmentStep.VENUE_ADMISSIBILITY_DECISION]

        construction_result = runtime.construction_stage.construction
        assert (
            construction_result is not None and construction_result.command is not None
        )
        from decimal import Decimal

        from tos.ioc import ConformanceAxis

        bound_quantity = construction_result.command.axis_value(
            ConformanceAxis.QUANTITY
        )
        assert bound_quantity is not None and Decimal(bound_quantity) == 10

        assert runtime.venue_stage.resolved_shape is not None
        assert runtime.venue_stage.resolved_shape.quantity == 10
        assert step3.outcome is StageOutcome.ADMIT

        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestSourcedShapeNonIntegralQuantityNeverFallsBackToTheLiteral:
    """MEDIUM (team-lead review, PR #718): pins ``VenueServiceStage._sourced_shape`` ITSELF —"""

    @staticmethod
    def _stage(shape) -> VenueServiceStage:
        from tos.egressgw import CandidateConstruction
        from tos.venue import ActionClass
        from tos_runtime.compose._venue_wiring import VenueServiceStage
        from tos_runtime.venue import VenueConstraintService

        class _StubService(VenueConstraintService):
            """Only ``VenueServiceStage._sourced_shape`` — never ``__call__`` — is exercised"""

            def __init__(
                self,
            ) -> None:
                pass

        class _StubConstructionStage:
            construction: CandidateConstruction | None = None

        return VenueServiceStage(
            _StubService(),
            _StubConstructionStage(),
            ActionClass.NEW_LONG,
            None,
            shape=shape,
        )

    def test_non_integral_axis_value_leaves_quantity_none_not_the_literal(self) -> None:
        from tos.ioc import AxisBinding, CanonicalBrokerCommand, ConformanceAxis
        from tos.venue import OrderShapeFields

        literal_quantity = 20
        resolved = OrderShapeFields(
            price=4500,
            quantity=literal_quantity,
            order_type="LIMIT",
            tif="DAY",
            side="BUY",
            position_effect="OPEN",
            silently_rounded=False,
        )
        command = CanonicalBrokerCommand(
            command_id="cmd-test",
            command_generation=1,
            axis_bindings=(AxisBinding(axis=ConformanceAxis.QUANTITY, value="10.5"),),
        )

        sourced = self._stage(resolved)._sourced_shape(resolved, command)

        assert sourced is not None
        assert sourced.quantity is None
        assert sourced.quantity != literal_quantity


class TestSourcedShapeIgnoresPolicyViolatingLiteralQuantity:
    """(a′) wave lane D: pins the same property"""

    @staticmethod
    def _stage(shape) -> VenueServiceStage:
        from tos.egressgw import CandidateConstruction
        from tos.venue import ActionClass
        from tos_runtime.compose._venue_wiring import VenueServiceStage
        from tos_runtime.venue import VenueConstraintService

        class _StubService(VenueConstraintService):
            """Only ``VenueServiceStage._sourced_shape`` — never ``__call__`` — is exercised"""

            def __init__(
                self,
            ) -> None:
                pass

        class _StubConstructionStage:
            construction: CandidateConstruction | None = None

        return VenueServiceStage(
            _StubService(),
            _StubConstructionStage(),
            ActionClass.NEW_LONG,
            None,
            shape=shape,
        )

    def test_policy_violating_literal_quantity_never_reaches_the_judged_shape(
        self,
    ) -> None:
        from tos.ioc import AxisBinding, CanonicalBrokerCommand, ConformanceAxis

        literal_quantity = 999
        shape = fx.order_shape(quantity=literal_quantity)
        command = CanonicalBrokerCommand(
            command_id="cmd-test",
            command_generation=1,
            axis_bindings=(AxisBinding(axis=ConformanceAxis.QUANTITY, value="10"),),
        )

        sourced = self._stage(shape)._sourced_shape(shape, command)

        assert sourced is not None
        assert sourced.quantity == 10
        assert sourced.quantity != literal_quantity


class TestSilentlyRoundedIsNeverIntroduced:
    """(a′) wave lane C, HIGH round 3 (team-lead re-review, PR #718, 2026-09-16):"""

    def test_sourced_quantity_equals_the_derivations_own_output_on_the_happy_path(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        from tos.egressgw import DerivationOutcome

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        runtime.run_once((fx.crossing_event(),))

        construction = runtime.construction_stage.construction
        assert construction is not None
        assert construction.derivation.outcome is DerivationOutcome.DERIVED
        assert runtime.venue_stage.resolved_shape is not None
        assert runtime.venue_stage.resolved_shape.quantity == int(
            construction.derivation.quantity
        )
        assert runtime.venue_stage.resolved_shape.silently_rounded is False

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_sourced_quantity_equals_the_derivations_own_output_when_floor_to_lot_actually_rounds(
        self, tmp_path: Path
    ) -> None:
        """FLOOR_TO_LOT check (team-lead brief, 2026-09-16). ``risk_budget=1030`` /"""
        from decimal import Decimal

        from tos.egressgw import DerivationOutcome

        config_dir, data_dir, custody_root = _fresh_compose_dirs(tmp_path / "case")
        (config_dir / "order_construction_policy.yaml").write_text(
            ocp_yaml(
                environment=_VENUE_POLICY_ENVIRONMENT,
                account=_VENUE_POLICY_ACCOUNT,
                instrument=_VENUE_POLICY_INSTRUMENT,
                wire_codec="null",
                construction=(
                    "  construction:\n"
                    "    sizing:\n"
                    "      max_quantity: 100\n"
                    "      min_quantity: 2\n"
                    "      lot_size: 2\n"
                    '      lot_rounding: "FLOOR_TO_LOT"\n'
                    "      risk_budget: 1030\n"
                    "      per_unit_risk: 50\n"
                    "      max_notional: null\n"
                    '      admitted_quantity_bases: ["RISK"]\n'
                    "    axes:\n"
                    '      - axis: "TIF"\n'
                    '        value: "DAY"\n'
                    '      - axis: "DIRECTION"\n'
                    '        value: "LONG"\n'
                    "    action_class_shape:\n"
                    "      NEW_LONG:\n"
                    '        LONG: {side: "BUY", position_effect: "OPEN"}\n'
                    "      NEW_SHORT:\n"
                    '        SHORT: {side: "SELL", position_effect: "OPEN"}\n'
                    "    effect_dimensions:\n"
                    '      - dimension_id: "INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL"\n'
                    '        basis: "QUANTITY"\n'
                    '        unit: "CONTRACTS"\n'
                    '        scale: "1"\n'
                ),
            ),
            encoding="utf-8",
        )
        construction = fx.construction_config()
        runtime = _compose_with_construction(
            tmp_path, config_dir, data_dir, custody_root, construction
        )
        _reach_trusted(runtime)
        runtime.run_once((fx.crossing_event(),))

        construction_result = runtime.construction_stage.construction
        assert construction_result is not None
        assert construction_result.derivation.outcome is DerivationOutcome.DERIVED
        assert construction_result.derivation.quantity == Decimal("20")

        assert runtime.venue_stage.resolved_shape is not None
        assert runtime.venue_stage.resolved_shape.quantity == int(
            construction_result.derivation.quantity
        )
        assert runtime.venue_stage.resolved_shape.silently_rounded is False

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_missing_price_still_reaches_unknown_not_the_hardcoded_false_blocking_it(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """A structurally-unprojectable step-3 price — ``_shape_for``'s own documented"""
        construction = fx.construction_config(
            shape_price_field_key="not-a-real-field-key"
        )
        runtime = _compose_with_construction(
            tmp_path, config_dir, data_dir, custody_root, construction
        )
        _reach_trusted(runtime)

        results = runtime.run_once((fx.crossing_event(),))
        verdicts = {v.step: v for v in results[0].flow.verdicts}
        step3 = verdicts[CommitmentStep.VENUE_ADMISSIBILITY_DECISION]

        assert runtime.venue_stage.resolved_shape is not None
        assert runtime.venue_stage.resolved_shape.price is None
        assert runtime.venue_stage.resolved_shape.silently_rounded is False
        assert step3.outcome is StageOutcome.UNKNOWN

        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestDerivedShapeQuantityUnit:
    """decision 2: pure unit coverage for :func:`_derived_shape_quantity`'s fail-closed"""

    def test_absent_candidate_command_is_none(self) -> None:
        from tos_runtime.compose._venue_wiring import _derived_shape_quantity

        assert _derived_shape_quantity(None) is None

    def test_absent_quantity_axis_is_none(self) -> None:
        from tos.ioc import CanonicalBrokerCommand
        from tos_runtime.compose._venue_wiring import _derived_shape_quantity

        command = CanonicalBrokerCommand(command_id="cmd-test", command_generation=1)
        assert _derived_shape_quantity(command) is None

    def test_fractional_axis_value_is_none_not_a_guess(self) -> None:
        from tos.ioc import AxisBinding, CanonicalBrokerCommand, ConformanceAxis
        from tos_runtime.compose._venue_wiring import _derived_shape_quantity

        command = CanonicalBrokerCommand(
            command_id="cmd-test",
            command_generation=1,
            axis_bindings=(AxisBinding(axis=ConformanceAxis.QUANTITY, value="1.5"),),
        )
        assert _derived_shape_quantity(command) is None

    def test_whole_number_axis_value_parses_to_int(self) -> None:
        from tos.ioc import AxisBinding, CanonicalBrokerCommand, ConformanceAxis
        from tos_runtime.compose._venue_wiring import _derived_shape_quantity

        command = CanonicalBrokerCommand(
            command_id="cmd-test",
            command_generation=1,
            axis_bindings=(AxisBinding(axis=ConformanceAxis.QUANTITY, value="20"),),
        )
        assert _derived_shape_quantity(command) == 20


class TestConstructionRulesShapeSourcingUnit:
    """decisions 2/3: pure unit coverage for the ``ConstructionRules``-driven sourcing"""

    def test_side_and_position_effect_come_from_the_mapping(self) -> None:
        from tos.ioc import AxisBinding, ConformanceAxis
        from tos.venue import ActionClass
        from tos_runtime.compose._venue_wiring import _shape_side_and_position_effect
        from tos_runtime.venue.construction_rules import (
            ActionClassShape,
            ConstructionRules,
        )

        long_rules = ConstructionRules(
            sizing_bound=fx.sizing_bound(),
            admitted_quantity_bases=frozenset({"RISK"}),
            authorized_axes=(
                AxisBinding(axis=ConformanceAxis.DIRECTION, value="LONG"),
            ),
            action_class_shape={
                (ActionClass.NEW_LONG, "LONG"): ActionClassShape(
                    side="BUY", position_effect="OPEN"
                ),
                (ActionClass.CLOSE, "LONG"): ActionClassShape(
                    side="SELL", position_effect="CLOSE"
                ),
            },
            effect_dimensions=(),
        )
        assert _shape_side_and_position_effect(long_rules, ActionClass.NEW_LONG) == (
            "BUY",
            "OPEN",
        )
        assert _shape_side_and_position_effect(long_rules, ActionClass.CLOSE) == (
            "SELL",
            "CLOSE",
        )

        short_rules = ConstructionRules(
            sizing_bound=fx.sizing_bound(),
            admitted_quantity_bases=frozenset({"RISK"}),
            authorized_axes=(
                AxisBinding(axis=ConformanceAxis.DIRECTION, value="SHORT"),
            ),
            action_class_shape={
                (ActionClass.NEW_SHORT, "SHORT"): ActionClassShape(
                    side="SELL", position_effect="OPEN"
                ),
                (ActionClass.CLOSE, "SHORT"): ActionClassShape(
                    side="BUY", position_effect="CLOSE"
                ),
            },
            effect_dimensions=(),
        )
        assert _shape_side_and_position_effect(short_rules, ActionClass.NEW_SHORT) == (
            "SELL",
            "OPEN",
        )
        assert _shape_side_and_position_effect(short_rules, ActionClass.CLOSE) == (
            "BUY",
            "CLOSE",
        )

    def test_action_class_absent_from_the_mapping_is_a_refusal(self) -> None:
        from tos.ioc import AxisBinding, ConformanceAxis
        from tos.venue import ActionClass
        from tos_runtime.compose._venue_wiring import _shape_side_and_position_effect
        from tos_runtime.venue.construction_rules import (
            ActionClassShape,
            ConstructionRules,
        )

        rules = ConstructionRules(
            sizing_bound=fx.sizing_bound(),
            admitted_quantity_bases=frozenset({"RISK"}),
            authorized_axes=(
                AxisBinding(axis=ConformanceAxis.DIRECTION, value="LONG"),
            ),
            action_class_shape={
                (ActionClass.NEW_LONG, "LONG"): ActionClassShape(
                    side="BUY", position_effect="OPEN"
                ),
            },
            effect_dimensions=(),
        )

        assert _shape_side_and_position_effect(rules, ActionClass.NEW_SHORT) == (
            None,
            None,
        )
        assert _shape_side_and_position_effect(rules, ActionClass.CLOSE) == (None, None)
        assert _shape_side_and_position_effect(rules, None) == (None, None)

    def test_no_direction_binding_is_a_refusal(self) -> None:
        """No ``DIRECTION`` axis binding at all is the SAME refusal as an absent mapping"""
        from tos.venue import ActionClass
        from tos_runtime.compose._venue_wiring import _shape_side_and_position_effect
        from tos_runtime.venue.construction_rules import (
            ActionClassShape,
            ConstructionRules,
        )

        rules = ConstructionRules(
            sizing_bound=fx.sizing_bound(),
            admitted_quantity_bases=frozenset({"RISK"}),
            authorized_axes=(),
            action_class_shape={
                (ActionClass.CLOSE, "LONG"): ActionClassShape(
                    side="SELL", position_effect="CLOSE"
                ),
            },
            effect_dimensions=(),
        )

        assert _shape_side_and_position_effect(rules, ActionClass.CLOSE) == (
            None,
            None,
        )

    def test_order_type_and_tif_come_from_authorized_axes(self) -> None:
        from tos.ioc import AxisBinding, ConformanceAxis
        from tos_runtime.compose._venue_wiring import _shape_order_type_and_tif
        from tos_runtime.venue.construction_rules import ConstructionRules

        rules = ConstructionRules(
            sizing_bound=fx.sizing_bound(),
            admitted_quantity_bases=frozenset({"RISK"}),
            authorized_axes=(
                AxisBinding(axis=ConformanceAxis.ORDER_TYPE, value="LIMIT"),
                AxisBinding(axis=ConformanceAxis.TIF, value="DAY"),
                AxisBinding(axis=ConformanceAxis.ACCOUNT, value=fx.ACCOUNT),
            ),
            action_class_shape={},
            effect_dimensions=(),
        )

        assert _shape_order_type_and_tif(rules) == ("LIMIT", "DAY")

    def test_order_type_and_tif_absent_from_authorized_axes_is_none(self) -> None:
        from tos_runtime.compose._venue_wiring import _shape_order_type_and_tif
        from tos_runtime.venue.construction_rules import ConstructionRules

        rules = ConstructionRules(
            sizing_bound=fx.sizing_bound(),
            admitted_quantity_bases=frozenset({"RISK"}),
            authorized_axes=(),
            action_class_shape={},
            effect_dimensions=(),
        )

        assert _shape_order_type_and_tif(rules) == (None, None)
