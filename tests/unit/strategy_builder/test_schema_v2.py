"""Schema v2 (P2-a) validation tests: entry_short, exit primitives, gates,
percentile operators, capabilities exposure."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.strategy_builder.catalog import load_capabilities
from shared.strategy_builder.exit_primitives import validate_exit_primitive
from shared.strategy_builder.schema import (
    BuilderCondition,
    BuilderConditionGroup,
    BuilderGates,
    BuilderIndicator,
    BuilderMetadata,
    BuilderRegimeGate,
    BuilderState,
    ConditionOperand,
    ConditionOperator,
    ExitPrimitiveRef,
    OperandType,
)
from shared.strategy_builder.yaml_io import (
    builder_state_to_yaml,
    yaml_to_builder_state,
)


def _rsi_condition(
    operator: ConditionOperator = ConditionOperator.GREATER_THAN,
    threshold: float = 70.0,
    window: int | None = None,
) -> BuilderCondition:
    return BuilderCondition(
        left=ConditionOperand(type=OperandType.INDICATOR, indicator_alias="rsi"),
        operator=operator,
        right=ConditionOperand(type=OperandType.VALUE, value=threshold),
        window=window,
    )


def _state(**overrides) -> BuilderState:
    base = {
        "metadata": BuilderMetadata(id="schema_v2_test", name="Schema V2 Test"),
        "asset_class": "stock",
        "indicators": [BuilderIndicator(indicator_id="rsi", alias="rsi")],
        "entry": BuilderConditionGroup(
            conditions=[_rsi_condition(ConditionOperator.LESS_THAN, 30.0)]
        ),
        "exit": BuilderConditionGroup(conditions=[_rsi_condition()]),
    }
    base.update(overrides)
    return BuilderState(**base)


# --- entry_short --------------------------------------------------------


def test_entry_short_rejected_for_stock() -> None:
    with pytest.raises(ValidationError, match="futures"):
        _state(
            asset_class="stock",
            entry_short=BuilderConditionGroup(conditions=[_rsi_condition()]),
        )


def test_entry_short_accepted_for_futures() -> None:
    state = _state(
        asset_class="futures",
        entry_short=BuilderConditionGroup(conditions=[_rsi_condition()]),
    )
    assert state.entry_short is not None
    names = [name for name, _group in state.condition_groups()]
    assert names == ["entry", "entry_short", "exit"]


def test_entry_short_alias_validation_covers_short_group() -> None:
    with pytest.raises(ValidationError, match="entry_short.*unknown indicator alias"):
        _state(
            asset_class="futures",
            entry_short=BuilderConditionGroup(
                conditions=[
                    BuilderCondition(
                        left=ConditionOperand(
                            type=OperandType.INDICATOR, indicator_alias="nope"
                        ),
                        operator=ConditionOperator.GREATER_THAN,
                        right=ConditionOperand(type=OperandType.VALUE, value=1.0),
                    )
                ]
            ),
        )


def test_empty_entry_short_allowed_for_stock() -> None:
    # An empty short group carries no short entries, so stock states that
    # (de)serialize one are not rejected.
    state = _state(entry_short=BuilderConditionGroup(conditions=[]))
    assert state.entry_short is not None


# --- percentile operators -----------------------------------------------


def test_percentile_requires_window() -> None:
    with pytest.raises(ValidationError, match="requires 'window'"):
        _rsi_condition(ConditionOperator.PERCENTILE_RANK_ABOVE, 90.0, window=None)


def test_percentile_window_minimum_is_two() -> None:
    with pytest.raises(ValidationError):
        _rsi_condition(ConditionOperator.PERCENTILE_RANK_ABOVE, 90.0, window=1)


def test_percentile_rejects_value_left_operand() -> None:
    with pytest.raises(ValidationError, match="needs a series on the left"):
        BuilderCondition(
            left=ConditionOperand(type=OperandType.VALUE, value=5.0),
            operator=ConditionOperator.PERCENTILE_RANK_ABOVE,
            right=ConditionOperand(type=OperandType.VALUE, value=90.0),
            window=20,
        )


def test_percentile_rejects_non_value_right_operand() -> None:
    with pytest.raises(ValidationError, match="between 0 and 100"):
        BuilderCondition(
            left=ConditionOperand(type=OperandType.INDICATOR, indicator_alias="rsi"),
            operator=ConditionOperator.PERCENTILE_RANK_ABOVE,
            right=ConditionOperand(type=OperandType.INDICATOR, indicator_alias="rsi"),
            window=20,
        )


def test_percentile_rejects_out_of_range_threshold() -> None:
    with pytest.raises(ValidationError, match="between 0 and 100"):
        _rsi_condition(ConditionOperator.PERCENTILE_RANK_BELOW, 150.0, window=20)


def test_scalar_operators_do_not_require_window() -> None:
    condition = _rsi_condition(ConditionOperator.GREATER_THAN, 70.0)
    assert condition.window is None


def test_percentile_window_capped_at_live_candle_history() -> None:
    # The live runtime keeps at most LIVE_CANDLE_HISTORY_MAXLEN completed
    # candles; a larger window would evaluate in backtests but stay
    # permanently missing live (parity trap), so the schema rejects it.
    from shared.indicators.constants import LIVE_CANDLE_HISTORY_MAXLEN

    with pytest.raises(ValidationError, match="live candle-history"):
        _rsi_condition(
            ConditionOperator.PERCENTILE_RANK_ABOVE,
            90.0,
            window=LIVE_CANDLE_HISTORY_MAXLEN + 1,
        )


def test_percentile_window_at_cap_is_accepted() -> None:
    from shared.indicators.constants import LIVE_CANDLE_HISTORY_MAXLEN

    condition = _rsi_condition(
        ConditionOperator.PERCENTILE_RANK_ABOVE,
        90.0,
        window=LIVE_CANDLE_HISTORY_MAXLEN,
    )
    assert condition.window == LIVE_CANDLE_HISTORY_MAXLEN


def test_window_cap_single_source_matches_live_runtime_default() -> None:
    """The schema cap and the live engine's candle history depth must share
    one constant — if either side hardcodes a different number the
    backtest/live parity guarantee silently breaks."""
    import inspect

    from services.trading.indicator_engine import StreamingIndicatorEngine
    from shared.indicators.constants import LIVE_CANDLE_HISTORY_MAXLEN

    signature = inspect.signature(StreamingIndicatorEngine.__init__)
    assert signature.parameters["candle_maxlen"].default == LIVE_CANDLE_HISTORY_MAXLEN


# --- exit primitive / gates models --------------------------------------


def test_exit_primitive_ref_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        ExitPrimitiveRef(primitive="   ")


def test_gates_reject_negative_cooldown() -> None:
    with pytest.raises(ValidationError):
        BuilderGates(cooldown_seconds=-1)


def test_regime_gate_bounds_validated() -> None:
    with pytest.raises(ValidationError):
        BuilderRegimeGate(regime_percentile_max=140.0)


# --- exit primitive validation (ExitRegistry SoT) ------------------------


def test_validate_exit_primitive_none_when_absent() -> None:
    assert validate_exit_primitive(_state()) is None


def test_validate_exit_primitive_unknown_name_lists_available() -> None:
    state = _state(exit_primitive=ExitPrimitiveRef(primitive="not_a_real_exit"))
    error = validate_exit_primitive(state)
    assert error is not None
    assert "not_a_real_exit" in error
    assert "Available" in error
    assert "atr_dynamic" in error


def test_validate_exit_primitive_rejects_self_reference() -> None:
    state = _state(exit_primitive=ExitPrimitiveRef(primitive="builder_v1_exit"))
    error = validate_exit_primitive(state)
    assert error is not None
    assert "cannot be composed with itself" in error


def test_validate_exit_primitive_accepts_registered_primitive() -> None:
    state = _state(exit_primitive=ExitPrimitiveRef(primitive="atr_dynamic"))
    assert validate_exit_primitive(state) is None


def test_validate_exit_primitive_enforces_asset_class_restriction() -> None:
    # three_stage is stock-only (operational rule) — the catalog restriction
    # must block futures builder states from referencing it.
    state = _state(
        asset_class="futures",
        exit_primitive=ExitPrimitiveRef(primitive="three_stage"),
    )
    error = validate_exit_primitive(state)
    assert error is not None
    assert "three_stage" in error
    assert "asset_class" in error


def test_validate_exit_primitive_allows_three_stage_for_stock() -> None:
    state = _state(exit_primitive=ExitPrimitiveRef(primitive="three_stage"))
    assert validate_exit_primitive(state) is None


def test_validate_exit_primitive_rejects_uncataloged_registry_exit() -> None:
    # track_a_exit is a real ExitRegistry component but deliberately NOT in
    # the builder catalog (its default eod_close would violate the "no blanket
    # stock EOD liquidation" rule). The catalog is an allow-list: registered
    # but uncataloged names must be rejected with an actionable message.
    state = _state(exit_primitive=ExitPrimitiveRef(primitive="track_a_exit"))
    error = validate_exit_primitive(state)
    assert error is not None
    assert "track_a_exit" in error
    assert "not exposed to the builder" in error
    assert "catalog entry" in error


@pytest.mark.parametrize(
    ("primitive", "asset_class"),
    [
        ("three_stage", "stock"),
        ("atr_dynamic", "stock"),
        ("atr_dynamic", "futures"),
        ("chandelier_exit", "stock"),
        ("chandelier_exit", "futures"),
        ("momentum_decay", "stock"),
        ("momentum_decay", "futures"),
        ("setup_target_exit", "futures"),
    ],
)
def test_cataloged_primitives_stay_allowed(primitive: str, asset_class: str) -> None:
    state = _state(
        asset_class=asset_class,
        exit_primitive=ExitPrimitiveRef(primitive=primitive),
    )
    assert validate_exit_primitive(state) is None


def test_catalog_exit_primitives_are_registered() -> None:
    """Catalog <-> registry SoT guardrail: the allow-list must be a subset of
    the ExitRegistry (a typo'd or stale catalog entry would otherwise pass
    validation but fail at factory create)."""
    from shared.strategy.registry import ExitRegistry, register_builtin_components
    from shared.strategy_builder.catalog import exit_primitive_definitions

    register_builtin_components()
    definitions = exit_primitive_definitions()
    assert definitions, "catalog exit_primitives must not be empty"
    unregistered = sorted(
        name for name in definitions if not ExitRegistry.is_registered(name)
    )
    assert (
        not unregistered
    ), f"catalog exit_primitives not registered in ExitRegistry: {unregistered}"
    assert (
        "builder_v1_exit" not in definitions
    ), "the builder's own declarative exit must not be catalog-exposed"


# --- yaml round-trip for v2 fields ---------------------------------------


def test_yaml_roundtrip_preserves_v2_fields() -> None:
    state = _state(
        asset_class="futures",
        entry_short=BuilderConditionGroup(
            conditions=[
                _rsi_condition(ConditionOperator.PERCENTILE_RANK_ABOVE, 90.0, window=50)
            ]
        ),
        exit_primitive=ExitPrimitiveRef(
            primitive="atr_dynamic", params={"atr_period": 10}
        ),
        gates=BuilderGates(
            regime_gate=BuilderRegimeGate(enabled=True, regime_percentile_max=55.0),
            cooldown_seconds=1800,
        ),
    )
    restored = yaml_to_builder_state(builder_state_to_yaml(state))
    assert restored.entry_short is not None
    condition = restored.entry_short.conditions[0]
    assert condition.operator == ConditionOperator.PERCENTILE_RANK_ABOVE
    assert condition.window == 50
    assert restored.exit_primitive is not None
    assert restored.exit_primitive.primitive == "atr_dynamic"
    assert restored.exit_primitive.params == {"atr_period": 10}
    assert restored.gates is not None
    assert restored.gates.cooldown_seconds == 1800
    assert restored.gates.regime_gate is not None
    assert restored.gates.regime_gate.enabled is True
    assert restored.gates.regime_gate.regime_percentile_max == 55.0


def test_yaml_export_omits_v2_sections_for_legacy_states() -> None:
    yaml_text = builder_state_to_yaml(_state())
    assert "entry_short" not in yaml_text
    assert "exit_primitive" not in yaml_text
    assert "gates" not in yaml_text
    assert "window" not in yaml_text


# --- capabilities --------------------------------------------------------


def test_capabilities_expose_v2_vocabulary() -> None:
    capabilities = load_capabilities()
    assert ConditionOperator.PERCENTILE_RANK_ABOVE in capabilities.operators
    assert ConditionOperator.PERCENTILE_RANK_BELOW in capabilities.operators
    assert capabilities.directions == ["long", "short"]
    primitives = {primitive.id: primitive for primitive in capabilities.exit_primitives}
    assert "three_stage" in primitives
    assert primitives["three_stage"].asset_classes == ["stock"]
    assert "atr_dynamic" in primitives
    assert set(primitives["atr_dynamic"].asset_classes) == {"stock", "futures"}
    assert "regime_gate" in capabilities.gate_fields
    assert "cooldown_seconds" in capabilities.gate_fields
