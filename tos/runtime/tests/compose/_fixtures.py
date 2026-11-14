"""Compose end-to-end test fixtures (tos/runtime/tests/compose, hermetic)."""

from __future__ import annotations

import shutil
import stat
import time
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import TypedDict, Unpack

import pytest
import yaml
from tos.are import ProjectedCell
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.capsule import DecisionContextCapsule, PolicyRef
from tos.capsule.capsule import CapsuleScope, SafetyCriticalFacts, SnapshotRef
from tos.dsl import (
    VALUE_NAMESPACE,
    AuthoredStrategy,
    Compare,
    CompareOp,
    ContextValue,
    ContextValueView,
    Decision,
    DecisionContextCapsuleRef,
    DecisionKind,
    DecisionPolicy,
    EvaluationConfig,
    Operand,
    Proposer,
    Rule,
    TargetKind,
    TargetSpec,
    build_proposal,
)
from tos.egressgw import AdmittedPriceObservation, SizingBound
from tos.egressgw.vocabulary import LotRoundingPolicy
from tos.engine import (
    CAPSULE_CONTEXT_SOURCE,
    EngineConfiguration,
    EngineEvent,
    InstrumentKey,
    StrategyRegistry,
)
from tos.engine.records import DecisionTickPayload, StageRequest, TimeAdmissionInputs
from tos.engine.vocabulary import CommitmentStep, EventKind
from tos.ioc import QuantityUnitKind
from tos.ordering import OrderingEvent
from tos.rcl import CapacityComponent, CapacityVector
from tos.time import HealthState, SessionContext, UncertaintyInterval
from tos.venue import ActionClass, OrderShapeFields
from tos_runtime.compose.root import ConstructionConfig
from tos_runtime.time.sources import LocalSystemClockReader, ReferenceObservation
from tos_runtime.transport.kis_mock.codec import KIS_ORDER_CASH_WIRE_FIELDS

from ..venue._documents import ocp_yaml

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

ACCOUNT = "88888888-01"
INSTRUMENT = "ES"
DECISION_CLASS = "entry"
SIDE = "BUY"
SESSION_PHASE = "CONTINUOUS"
INSTRUMENT_CLASS = "krx-index-futures"
DEFAULT_WALL_CLOCK_UNIX_MS = 1_789_347_600_000
LAST_MINUTE_OF_DAY_UNIX_MS = 1_789_397_970_000

_ORIGINAL_LOCAL_SYSTEM_CLOCK_READ = LocalSystemClockReader.read


def pin_system_clock(
    monkeypatch: pytest.MonkeyPatch, target_unix_ms: int
) -> Callable[[], int]:
    """Shift the ONE OS wall clock a composed runtime reads onto ``target_unix_ms``."""
    real_read = _ORIGINAL_LOCAL_SYSTEM_CLOCK_READ
    offset_ms = target_unix_ms - int(time.time() * 1000)

    def _shifted_read(self: LocalSystemClockReader) -> ReferenceObservation:
        observed = real_read(self)
        if observed.wall_clock_unix_ms is None:
            return observed
        return replace(
            observed, wall_clock_unix_ms=observed.wall_clock_unix_ms + offset_ms
        )

    monkeypatch.setattr(LocalSystemClockReader, "read", _shifted_read)
    return lambda: int(time.time() * 1000) + offset_ms


LOWER_BAND = 4_500_000
UPPER_BAND = 4_520_000
CROSSING_CLOSE = 4_499_000

RISK_BUDGET = Decimal("1000")
PER_UNIT_RISK = Decimal("50")
LOT_SIZE = Decimal("2")
MIN_QUANTITY = Decimal("2")
MAX_QUANTITY = Decimal("100")
PRICE = Decimal("4200")
PRICE_FIELD_KEY = "close"


def instrument_key() -> InstrumentKey:
    return InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT)


def stage_request(
    *, step: CommitmentStep = CommitmentStep.AGGREGATE_RISK_DECISION
) -> StageRequest:
    """A minimal, valid :class:`~tos.engine.records.StageRequest` for callers that need a"""
    proposal = build_proposal(
        scheme=SCHEME,
        proposer=Proposer(strategy_id="strat-fixture", strategy_version="v1"),
        account=ACCOUNT,
        instrument=INSTRUMENT,
        direction="LONG",
        position_effect="OPEN",
        quantity_basis="RISK",
        rationale="fixture stage request — mypy stage 3 §1.2",
        decision_context_capsule=DecisionContextCapsuleRef(
            capsule_id="cap-fixture", canonical_digest="capdig-fixture"
        ),
        dsl_version="dsl-0",
        config_version="cfg-0",
    )
    return StageRequest(
        step=step,
        instrument_key=instrument_key(),
        proposal=proposal,
    )


def _value_ref(field_key: str) -> Operand:
    return Operand(ref=("capsule", VALUE_NAMESPACE, field_key))


def band_reversion_policy() -> DecisionPolicy:
    """``close < lower_band`` -> ``LONG``/``OPEN``; else hold (single rule,"""
    entry = Decision(
        kind=DecisionKind.ACTION,
        rationale="close pierced the lower band — compose e2e entry",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="LONG",
            position_effect="OPEN",
            quantity_basis="RISK",
            edge_or_confidence="compose-e2e",
            rationale="close pierced the lower band — compose e2e entry",
        ),
    )
    hold = Decision(
        kind=DecisionKind.NO_ACTION,
        rationale="close is inside the band — hold, no proposal",
    )
    return DecisionPolicy(
        rules=(
            Rule(
                all_of=(
                    Compare(
                        left=_value_ref("close"),
                        op=CompareOp.LT,
                        right=_value_ref("lower_band"),
                    ),
                ),
                decision=entry,
            ),
        ),
        default=hold,
    )


def band_reversion_strategy() -> AuthoredStrategy:
    issued = AuthoredStrategy.issue(
        scheme=SCHEME,
        dsl_version="dsl-compose",
        config_binding_version="cfg-bind-compose",
        policy=band_reversion_policy(),
    )
    assert isinstance(issued, AuthoredStrategy)
    return issued


def authored_config() -> EvaluationConfig:
    return EvaluationConfig(config_version="cfg-compose", bindings={})


def registry_with_band_strategy() -> tuple[StrategyRegistry, AuthoredStrategy]:
    registry = StrategyRegistry()
    strategy = band_reversion_strategy()
    registry.register(strategy, authored_config())
    return registry, strategy


BAND_STRATEGY_FILE_NAME = "band.strategy.yaml"


def band_reversion_strategy_mapping() -> dict[str, object]:
    """The raw-mapping equivalent of :func:`band_reversion_strategy` — same"""
    return {
        "dsl_version": "dsl-compose",
        "config_binding_version": "cfg-bind-compose",
        "policy": {
            "rules": [
                {
                    "all_of": [
                        {
                            "left": {"ref": ["capsule", VALUE_NAMESPACE, "close"]},
                            "op": "LT",
                            "right": {
                                "ref": ["capsule", VALUE_NAMESPACE, "lower_band"]
                            },
                        }
                    ],
                    "decision": {
                        "kind": "ACTION",
                        "rationale": "close pierced the lower band — compose e2e entry",
                        "target": {
                            "kind": "ACTION",
                            "account": ACCOUNT,
                            "instrument": INSTRUMENT,
                            "direction": "LONG",
                            "position_effect": "OPEN",
                            "quantity_basis": "RISK",
                            "edge_or_confidence": "compose-e2e",
                            "rationale": "close pierced the lower band — compose e2e entry",
                        },
                    },
                }
            ],
            "default": {
                "kind": "NO_ACTION",
                "rationale": "close is inside the band — hold, no proposal",
            },
        },
    }


def write_band_strategy_file(config_dir: Path) -> Path:
    """Write :func:`band_reversion_strategy_mapping` into"""
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(exist_ok=True)
    path = strategies_dir / BAND_STRATEGY_FILE_NAME
    path.write_text(
        yaml.safe_dump(band_reversion_strategy_mapping(), sort_keys=False),
        encoding="utf-8",
    )
    return path


def engine_configuration(**overrides: object) -> EngineConfiguration:
    base: dict[str, object] = {
        "dsl_evaluation_budget_steps": 64,
        "max_unresolved_send_per_scope": 1,
        "canonicalization_version": EV_L1_PROVISIONAL_VERSION,
        "enforcement_mechanism_version": "compose-e2e",
    }
    base.update(overrides)
    return EngineConfiguration.model_validate(base)


def _time_admission_inputs() -> TimeAdmissionInputs:
    return TimeAdmissionInputs(
        source_age=10,
        delay_bounds=(5,),
        max_age_bound=1000,
        future_tolerance=50,
        snapshot_age_bound=20,
        maximum_consumer_age_ms=1000,
        session_context=SessionContext(
            tz_id="tz",
            tz_db_version="tzdb-0",
            trading_calendar_version="cal-0",
            phase=SESSION_PHASE,
            is_open=True,
            tz_version_conflict=False,
            boundary_value=None,
        ),
        uncertainty_interval=UncertaintyInterval(lo=0, hi=10),
        health_state=HealthState.TRUSTED,
    )


def _capsule(seq: int) -> DecisionContextCapsule:
    issued = DecisionContextCapsule.issue(
        scheme=SCHEME,
        issuer_principal_id="iss-compose",
        critical_input_policy=PolicyRef(
            policy_id="pol-compose", canonical_digest="pd-compose"
        ),
        critical_input_snapshot=SnapshotRef(
            snapshot_id=f"snap-compose-{seq}",
            canonical_digest=f"snap-compose-digest-{seq}",
        ),
        scope=CapsuleScope(
            environment="non-live-test",
            account=ACCOUNT,
            instrument=INSTRUMENT,
            decision_class=DECISION_CLASS,
        ),
        safety_critical_facts=SafetyCriticalFacts(
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="LONG",
            quantity_basis="RISK",
            unit="contract",
        ),
    )
    assert isinstance(issued, DecisionContextCapsule)
    return issued


def _value_view(seq: int, close: int) -> ContextValueView:
    return ContextValueView(
        snapshot_id=f"snap-compose-{seq}",
        snapshot_canonical_digest=f"snap-compose-digest-{seq}",
        values=(
            ContextValue(
                field_key="close",
                value=close,
                as_of=seq,
                payload_digest=f"payload-digest-{seq}",
                observation_ref=f"raw-compose-{seq}",
            ),
            ContextValue(
                field_key="lower_band",
                value=LOWER_BAND,
                as_of=seq,
                payload_digest=f"payload-digest-{seq}",
                observation_ref=f"raw-compose-{seq}",
            ),
            ContextValue(
                field_key="upper_band",
                value=UPPER_BAND,
                as_of=seq,
                payload_digest=f"payload-digest-{seq}",
                observation_ref=f"raw-compose-{seq}",
            ),
        ),
        canonical_digest=f"view-digest-{seq}",
        canonicalization_version=EV_L1_PROVISIONAL_VERSION,
    )


def crossing_event(*, seq: int = 1, close: int = CROSSING_CLOSE) -> EngineEvent:
    """The single ``DECISION_TICK`` event this suite drives through the flow."""
    payload = DecisionTickPayload(
        instrument_key=instrument_key(),
        capsule=_capsule(seq),
        time=_time_admission_inputs(),
        reference=OrderingEvent(
            event_id=f"compose-tick-{seq}",
            source_continuity_id="compose-e2e",
            source_native_sequence=seq,
        ),
        value_view=_value_view(seq, close),
    )
    return EngineEvent(kind=EventKind.DECISION_TICK, decision_tick=payload)


def sizing_bound(**overrides: object) -> SizingBound:
    base: dict[str, object] = {
        "risk_budget": RISK_BUDGET,
        "per_unit_risk": PER_UNIT_RISK,
        "lot_size": LOT_SIZE,
        "lot_rounding": LotRoundingPolicy.FLOOR_TO_LOT,
        "min_quantity": MIN_QUANTITY,
        "max_quantity": MAX_QUANTITY,
        "quantity_unit": QuantityUnitKind.CONTRACTS,
        "admitted_quantity_bases": frozenset({"RISK"}),
    }
    base.update(overrides)
    return SizingBound.model_validate(base)


def admitted_price(**overrides: object) -> AdmittedPriceObservation:
    base: dict[str, object] = {
        "source": CAPSULE_CONTEXT_SOURCE,
        "value": PRICE,
        "snapshot_digest": "snap-compose-digest-1",
    }
    base.update(overrides)
    return AdmittedPriceObservation.model_validate(base)


def order_shape(**overrides: object) -> OrderShapeFields:
    """A hand-built :class:`~tos.venue.OrderShapeFields` literal — no longer wired anywhere on"""
    base: dict[str, object] = {
        "price": 4200,
        "quantity": 20,
        "order_type": "LIMIT",
        "tif": "DAY",
        "side": SIDE,
        "position_effect": "OPEN",
        "silently_rounded": False,
    }
    base.update(overrides)
    return OrderShapeFields.model_validate(base)


class _ConstructionConfigKwargs(TypedDict):
    """1:1 with :class:`ConstructionConfig`'s dataclass fields (plan §1.1 A-rt) — a"""

    account: str
    instrument: str
    price: AdmittedPriceObservation | None
    action_class: ActionClass
    instrument_class: str
    outbound_side: str
    price_field_key: str | None
    shape_price_field_key: str | None


class _ConstructionConfigKwargsPartial(TypedDict, total=False):
    """Same fields as :class:`_ConstructionConfigKwargs`, all optional — the override-kwargs"""

    account: str
    instrument: str
    price: AdmittedPriceObservation | None
    action_class: ActionClass
    instrument_class: str
    outbound_side: str
    price_field_key: str | None
    shape_price_field_key: str | None


def construction_config(
    **overrides: Unpack[_ConstructionConfigKwargsPartial],
) -> ConstructionConfig:
    """TOS venue constraint service wave (plan §2 decision 5): the former"""
    base: _ConstructionConfigKwargs = {
        "account": ACCOUNT,
        "instrument": INSTRUMENT,
        "price": admitted_price(),
        "action_class": ActionClass.NEW_LONG,
        "instrument_class": INSTRUMENT_CLASS,
        "outbound_side": SIDE,
        "price_field_key": PRICE_FIELD_KEY,
        "shape_price_field_key": PRICE_FIELD_KEY,
    }
    base.update(overrides)
    return ConstructionConfig(**base)


def adverse_scenario_cells() -> tuple[ProjectedCell, ...]:
    """A single fully-determinate, within-headroom"""
    from tos.are import (
        AdverseScenarioKind,
        RiskDimensionKind,
        RiskScopeKind,
    )

    return (
        ProjectedCell(
            scope=RiskScopeKind.ACCOUNT,
            dimension=RiskDimensionKind.GROSS_NOTIONAL,
            scenario=AdverseScenarioKind.ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ,
            conservative_current_usage=Decimal("0"),
            max_credible_command_effect=Decimal("100"),
            required_concurrent_overlap_effect=Decimal("0"),
            conservative_current_usage_already_committed=Decimal("0"),
            effective_limit=Decimal("1000"),
            credible_space_bounded=True,
            no_credible_intermediate_increases_exceedance=True,
            already_exceeded_regime=False,
        ),
    )


def aggregate_risk_effective_limit() -> CapacityVector:
    return CapacityVector(
        components=(
            CapacityComponent(dimension_id="notional", magnitude=Decimal("1000")),
        )
    )


def action_flow_envelope_max() -> CapacityVector:
    return CapacityVector(
        components=(
            CapacityComponent(dimension_id="afg.ORDER", magnitude=Decimal("10")),
        )
    )


def action_flow_requested_limit() -> CapacityVector:
    return CapacityVector(
        components=(
            CapacityComponent(dimension_id="afg.ORDER", magnitude=Decimal("1")),
        )
    )


KIS_MOCK_REST_BASE = "https://openapivts.koreainvestment.com:29443"

KIS_MOCK_ORDER_PRINCIPAL = "kis-mock-order-non-live-test"


class _Unset:
    """A distinguishable "no override given" sentinel — distinct from ``None`` itself, which"""


_UNSET = _Unset()


_STOCK_TREE_BROKER_FACTS = (
    Path(__file__).resolve().parents[4]
    / "config/tos_runtime/cp3-setup-d-stock-005930/broker_facts.yaml"
)
_STOCK_TREE_FILL_OBSERVER = _STOCK_TREE_BROKER_FACTS.with_name("fill_observer.yaml")


def write_kis_mock_transport_config(
    config_dir: Path,
    *,
    mode: str = "dry_run",
    endpoint_rest_base: str = KIS_MOCK_REST_BASE,
    allow_plaintext_for_tests: bool = False,
    min_send_interval_ms: int = 1100,
    wire_codec: str | None | _Unset = _UNSET,
    app_key_request_wait_budget_ms: int | None = None,
) -> Path:
    """Write a fully-valued ``kis_mock_transport.yaml`` (T2 lane C test fixture) — every"""
    path = config_dir / "kis_mock_transport.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "mode": mode,
                "endpoint_rest_base": endpoint_rest_base,
                "order_path": "/uapi/domestic-stock/v1/trading/order-cash",
                "token_path": "/oauth2/tokenP",
                "tr_id_buy": "VTTC0012U",
                "tr_id_sell": "VTTC0011U",
                "field_map": {
                    "account": "CANO",
                    "instrument": "PDNO",
                    "quantity": "ORD_QTY",
                    "price": "ORD_UNPR",
                },
                "static_body_fields": {
                    "ACNT_PRDT_CD": "01",
                    "ORD_DVSN": "00",
                    "EXCG_ID_DVSN_CD": "KRX",
                    "SLL_TYPE": "",
                    "CNDT_PRIC": "",
                },
                "price_scale": 100,
                "min_send_interval_ms": min_send_interval_ms,
                "app_key_request_wait_budget_ms": (
                    2 * min_send_interval_ms
                    if app_key_request_wait_budget_ms is None
                    else app_key_request_wait_budget_ms
                ),
                "token_reissue_min_interval_s": 60,
                "request_timeout_s": 5.0,
                "allow_plaintext_for_tests": allow_plaintext_for_tests,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    ocp_path = config_dir / "order_construction_policy.yaml"
    if ocp_path.is_file():
        if isinstance(wire_codec, _Unset):
            effective_wire_codec = (
                "{kind: kis-order-cash-v1, wire_fields: "
                f"{sorted(KIS_ORDER_CASH_WIRE_FIELDS)!r}}}"
            )
        elif wire_codec is None:
            effective_wire_codec = "null"
        else:
            effective_wire_codec = wire_codec
        ocp_path.write_text(
            ocp_yaml(
                environment="non-live-test",
                account=ACCOUNT,
                instrument=INSTRUMENT,
                wire_codec=effective_wire_codec,
            ),
            encoding="utf-8",
        )
    shutil.copyfile(_STOCK_TREE_BROKER_FACTS, config_dir / "broker_facts.yaml")
    shutil.copyfile(_STOCK_TREE_FILL_OBSERVER, config_dir / "fill_observer.yaml")
    vcp_path = config_dir / "venue_constraint_policy.yaml"
    if vcp_path.is_file():
        vcp = yaml.safe_load(vcp_path.read_text(encoding="utf-8"))
        vcp["_runtime"].setdefault("price_scale", 100)
        vcp_path.write_text(
            yaml.safe_dump(vcp, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    return path


def provision_kis_mock_custody(
    custody_root: Path, *, principal: str = KIS_MOCK_ORDER_PRINCIPAL
) -> None:
    """Add the two ``kis_mock.*`` custody scopes (T2 lane C) to an already-provisioned"""
    manifest_path = custody_root / "custody.manifest.yaml"
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    scopes = raw.setdefault("scopes", {})
    for scope_name in ("kis_mock.app_key", "kis_mock.app_secret"):
        scopes[scope_name] = {
            "file": scope_name,
            "principal": principal,
            "expected_sha256": None,
        }
        scope_path = custody_root / scope_name
        scope_path.write_bytes(f"test-secret-{scope_name}".encode())
        scope_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    manifest_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
