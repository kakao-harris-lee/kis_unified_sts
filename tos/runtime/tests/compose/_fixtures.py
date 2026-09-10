"""Compose end-to-end test fixtures (tos/runtime/tests/compose, hermetic).

**Not a copy of ``tos/tests/slice/_slice_fixtures.py`` and does not import
it** (runtime tests may not import kernel test modules — coordinator's task
brief). This module authors its own, much smaller, single-crossing-bar
strategy directly against kernel PRODUCTION packages
(``tos.dsl``/``tos.capsule``/``tos.engine``/``tos.egressgw``/``tos.venue``)
— the same public APIs the kernel test module uses, re-derived locally for
this suite (mirrors that file's own "cross-suite imports are forbidden, each
package's fixtures stay in its own suite" discipline, extended here to mean
"runtime tests build their own fixtures too").

One event, one instrument, one strategy: ``close < lower_band`` -> a single
``LONG``/``OPEN`` proposal. No :mod:`tos.backtest`/:mod:`tos.marketfeed`
driver is used — the compose end-to-end tests build the
:class:`~tos.engine.records.EngineEvent` directly (a
:class:`~tos.engine.records.DecisionTickPayload` needs only a Capsule + a
:class:`~tos.dsl.ContextValueView`, both constructed directly here), since
compose's own ``run_once(events)`` takes a plain iterable of events — no
bar-replay driver is part of this composition.
"""

from __future__ import annotations

import stat
from decimal import Decimal
from pathlib import Path

import yaml
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
    DecisionKind,
    DecisionPolicy,
    EvaluationConfig,
    Operand,
    Rule,
    TargetKind,
    TargetSpec,
)
from tos.egressgw import (
    AdmittedPriceObservation,
    EffectDimensionSpec,
    ProposedConstructionEnvelope,
)
from tos.egressgw.vocabulary import EffectBasis, LotRoundingPolicy
from tos.engine import (
    CAPSULE_CONTEXT_SOURCE,
    EngineConfiguration,
    EngineEvent,
    InstrumentKey,
    StrategyRegistry,
)
from tos.engine.records import DecisionTickPayload, TimeAdmissionInputs
from tos.engine.vocabulary import EventKind
from tos.ioc import AxisBinding, ConformanceAxis, QuantityUnitKind
from tos.ordering import OrderingEvent
from tos.rcl import CapacityComponent, CapacityVector
from tos.time import HealthState, SessionContext, UncertaintyInterval
from tos.venue import (
    ActionClass,
    ActionPhaseAdmission,
    OrderAdmissibilityDecision,
    OrderShapeFields,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
)
from tos_runtime.compose.root import ConstructionConfig

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

ACCOUNT = "acct-compose"
INSTRUMENT = "ES"
DECISION_CLASS = "entry"
SIDE = "BUY"
SESSION_PHASE = "CONTINUOUS"

LOWER_BAND = 4_500_000
UPPER_BAND = 4_520_000
#: The single crossing close this suite drives through the whole flow.
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


def _value_ref(field_key: str) -> Operand:
    return Operand(ref=("capsule", VALUE_NAMESPACE, field_key))


def band_reversion_policy() -> DecisionPolicy:
    """``close < lower_band`` -> ``LONG``/``OPEN``; else hold (single rule,
    single-direction — this suite only ever drives the crossing branch)."""
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


#: The strategy file name :func:`write_band_strategy_file` writes — matches
#: this suite's own ``*.strategy.yaml`` naming convention
#: (``tos/runtime/config/strategies/example.strategy.yaml``).
BAND_STRATEGY_FILE_NAME = "band.strategy.yaml"


def band_reversion_strategy_mapping() -> dict[str, object]:
    """The raw-mapping equivalent of :func:`band_reversion_strategy` — same
    ``dsl_version``/``config_binding_version``/policy content, shaped for
    :func:`tos.dsl.serialization.parse_strategy` (the file-source authoring
    path) rather than in-process typed construction. Both converge on the
    IDENTICAL :class:`~tos.dsl.AuthoredStrategy` digest+id
    (design #31 §1.2 "두 경로 동형") — ``parse_strategy`` issues via the
    same :meth:`~tos.dsl.AuthoredStrategy.issue` call either way."""
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
    """Write :func:`band_reversion_strategy_mapping` into
    ``config_dir / "strategies" / "band.strategy.yaml"`` (creating the
    ``strategies`` directory if absent) — the file-source counterpart to
    :func:`registry_with_band_strategy`'s injected-registry path
    (TOS Phase 3 슬라이스 D-R ``[D-R-2]``)."""
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
    return EngineConfiguration(**base)


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


def sizing_bound(**overrides: object) -> object:
    from tos.egressgw import SizingBound

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
    return SizingBound(**base)


def proposed_envelope(**overrides: object) -> ProposedConstructionEnvelope:
    base: dict[str, object] = {
        "envelope_generation": 1,
        "policy_binding_id": "ocp-compose",
        "authorized_axis_bindings": (
            AxisBinding(axis=ConformanceAxis.ACCOUNT, value=ACCOUNT),
            AxisBinding(axis=ConformanceAxis.INSTRUMENT, value=INSTRUMENT),
            AxisBinding(axis=ConformanceAxis.DIRECTION, value="LONG"),
            AxisBinding(axis=ConformanceAxis.SIDE, value=SIDE),
            AxisBinding(axis=ConformanceAxis.ORDER_TYPE, value="LIMIT"),
            AxisBinding(axis=ConformanceAxis.TIF, value="DAY"),
            AxisBinding(axis=ConformanceAxis.ENVIRONMENT, value="non-live-test"),
        ),
        "sizing_bound": sizing_bound(),
        "effect_dimensions": (
            EffectDimensionSpec(
                dimension_id="notional",
                basis=EffectBasis.NOTIONAL,
                unit="KRW",
                scale="1",
            ),
            EffectDimensionSpec(
                dimension_id="units",
                basis=EffectBasis.QUANTITY,
                unit="contract",
                scale="1",
            ),
        ),
    }
    base.update(overrides)
    return ProposedConstructionEnvelope(**base)


def admitted_price(**overrides: object) -> AdmittedPriceObservation:
    base: dict[str, object] = {
        "source": CAPSULE_CONTEXT_SOURCE,
        "value": PRICE,
        "snapshot_digest": "snap-compose-digest-1",
    }
    base.update(overrides)
    return AdmittedPriceObservation(**base)


def venue_quantity_constraint() -> object:
    from tos.egressgw import VenueQuantityConstraint

    return VenueQuantityConstraint(
        lot_size=LOT_SIZE,
        min_quantity=MIN_QUANTITY,
        max_quantity=MAX_QUANTITY,
        quantity_unit=QuantityUnitKind.CONTRACTS,
    )


def venue_policy() -> VenueConstraintPolicy:
    issued = VenueConstraintPolicy.issue(
        scheme=SCHEME,
        policy_id="vpol-compose",
        policy_generation=1,
        scope="scope-compose",
        admitting_phase_rules=(
            ActionPhaseAdmission(
                action=ActionClass.NEW_LONG, admitting_phases=frozenset({SESSION_PHASE})
            ),
        ),
    )
    assert isinstance(issued, VenueConstraintPolicy)
    return issued


def venue_snapshot() -> VenueConstraintSnapshot:
    issued = VenueConstraintSnapshot.issue(
        scheme=SCHEME,
        snapshot_id="vsnap-compose",
        constraint_generation=1,
        policy_id="vpol-compose",
        policy_generation=1,
        observed_session_phase=SESSION_PHASE,
    )
    assert isinstance(issued, VenueConstraintSnapshot)
    return issued


def venue_admissible_decision() -> OrderAdmissibilityDecision:
    from tos.venue import OrderAdmissibilityResult

    issued = OrderAdmissibilityDecision.issue(
        scheme=SCHEME,
        decision_id="vdec-compose",
        decision_generation=1,
        result=OrderAdmissibilityResult.ADMISSIBLE,
    )
    assert isinstance(issued, OrderAdmissibilityDecision)
    return issued


def order_shape() -> OrderShapeFields:
    return OrderShapeFields(
        price=4200,
        quantity=20,
        order_type="LIMIT",
        tif="DAY",
        side=SIDE,
        position_effect="OPEN",
        silently_rounded=False,
    )


def venue_shape_constraints() -> VenueShapeConstraints:
    return VenueShapeConstraints(
        price_min=1000,
        price_max=9_000_000,
        tick_size=500,
        lot_size=2,
        min_quantity=2,
        max_quantity=100,
        allowed_order_types=frozenset({"LIMIT"}),
        allowed_tifs=frozenset({"DAY"}),
        allowed_sides=frozenset({SIDE}),
        allowed_position_effects=frozenset({"OPEN"}),
    )


def construction_config() -> ConstructionConfig:
    return ConstructionConfig(
        account=ACCOUNT,
        instrument=INSTRUMENT,
        envelope=proposed_envelope(),
        price=admitted_price(),
        venue_constraint=venue_quantity_constraint(),
        venue_snapshot=venue_snapshot(),
        venue_policy=venue_policy(),
        venue_decision=venue_admissible_decision(),
        order_shape=order_shape(),
        venue_shape_constraints=venue_shape_constraints(),
        action_class=ActionClass.NEW_LONG,
        observed_session_phase=SESSION_PHASE,
        outbound_side=SIDE,
        price_field_key=PRICE_FIELD_KEY,
        shape_price_field_key=PRICE_FIELD_KEY,
    )


def adverse_scenario_cells() -> tuple[object, ...]:
    """A single fully-determinate, within-headroom
    :class:`~tos.are.ProjectedCell` — enough for ``adverse_increment`` to
    reach ``GRANT`` at the projection level."""
    from tos.are import (
        AdverseScenarioKind,
        ProjectedCell,
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


# ===========================================================================
# TOS KIS MOCK transport plan T2 lane C — kis-mock compose test fixtures
# ===========================================================================

#: The real INSTANCE MOCK_VTS document's own ``rest_base`` (docs/broker-profiles/
#: KIS-BROKER-CAPABILITY-PROFILE-draft.yaml) — this suite's config never invents its own host.
KIS_MOCK_REST_BASE = "https://openapivts.koreainvestment.com:29443"

#: ``MOCK_STOCK_ORDER.principal`` in ``broker_scopes.example.yaml``, substituted for the SAME
#: ``environment_label`` (``"non-live-test"``) every compose e2e test in this suite composes
#: with (:func:`_compose` in ``test_compose_root.py``) — the custody-principal consistency
#: check (:func:`~tos_runtime.compose._transport_wiring.refuse_custody_principal_mismatch`)
#: requires byte-exact equality with this value.
KIS_MOCK_ORDER_PRINCIPAL = "kis-mock-order-non-live-test"


def write_kis_mock_transport_config(
    config_dir: Path,
    *,
    mode: str = "dry_run",
    endpoint_rest_base: str = KIS_MOCK_REST_BASE,
    allow_plaintext_for_tests: bool = False,
    min_send_interval_ms: int = 1100,
) -> Path:
    """Write a fully-valued ``kis_mock_transport.yaml`` (T2 lane C test fixture) — every
    named-TBD field of the shipped example filled with a concrete, schema-valid value.

    ``endpoint_rest_base``/``allow_plaintext_for_tests``/``min_send_interval_ms`` default to
    the real-host, TLS-only, T2-lane-C shape every existing caller relies on; T3's own
    hermetic-fake-KIS-server counterfactual (``test_kis_mock_e2e_honesty.py``) is the only
    caller that overrides them, to point this config at the fake server's own ``127.0.0.1``
    ``http://`` base instead of inventing a second, duplicated config-writer.
    """
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
                "min_send_interval_ms": min_send_interval_ms,
                "token_reissue_min_interval_s": 60,
                "request_timeout_s": 5.0,
                "allow_plaintext_for_tests": allow_plaintext_for_tests,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def provision_kis_mock_custody(
    custody_root: Path, *, principal: str = KIS_MOCK_ORDER_PRINCIPAL
) -> None:
    """Add the two ``kis_mock.*`` custody scopes (T2 lane C) to an already-provisioned
    ``custody_root`` (``tos/runtime/tests/compose/conftest.py``'s own ``custody_root`` fixture) —
    manifest rows + 0600 secret files, both principals equal to ``principal`` (defaults to the
    SAME value :data:`KIS_MOCK_ORDER_PRINCIPAL` names)."""
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
