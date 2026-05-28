"""Compatibility tests for the imported KIS Strategy Builder UI."""

import pytest

from shared.strategy_builder.evaluator import StrategyBuilderEvaluator
from shared.strategy_builder.kis_compat import (
    apply_kis_preset_params,
    build_sample_series_for_state,
    get_kis_preset,
    kis_state_to_builder_state,
    list_kis_strategy_infos,
)
from shared.strategy_builder.schema import SignalSide


def test_kis_presets_include_readme_strategy_set():
    strategy_ids = {strategy["id"] for strategy in list_kis_strategy_infos()}

    assert {
        "golden_cross",
        "momentum",
        "trend_filter",
        "week52_high",
        "consecutive",
        "disparity",
        "breakout_fail",
        "strong_close",
        "volatility",
        "mean_reversion",
        "rsi_reversal",
        "williams_r_reversal",
        "macd_signal_cross",
        "bollinger_rsi_reversion",
        "vwap_reclaim",
        "stochastic_reversal",
        "trend_pullback",
        "donchian_breakout",
        "adx_trend_continuation",
        "trix_golden",
        "cci_reversal",
        "mfi_reversal",
        "obv_accumulation",
        "ichimoku_cloud_breakout",
        "supertrend_follow",
        "keltner_breakout",
        "engulfing_rsi_reversal",
    } <= strategy_ids


def test_kis_builder_states_convert_and_generate_sample_buy_signals():
    evaluator = StrategyBuilderEvaluator()

    for preset_info in list_kis_strategy_infos():
        preset = get_kis_preset(preset_info["id"])
        assert preset is not None
        state = kis_state_to_builder_state(preset["builder_state"])
        series = build_sample_series_for_state(state, symbol="005930")

        signal = evaluator.generate_signals(state, [series])[0]

        assert state.metadata.id == preset_info["id"]
        assert signal.side == SignalSide.BUY, preset_info["id"]
        assert signal.orderability == "paper_orderable", preset_info["id"]


def test_kis_preset_execute_params_update_builder_state_values():
    preset = get_kis_preset("golden_cross")
    assert preset is not None

    state = apply_kis_preset_params(
        preset,
        {"short_period": 7, "long_period": 35},
    )

    assert state["indicators"][0]["params"]["period"] == 7
    assert state["indicators"][1]["params"]["period"] == 35


def test_kis_preset_execute_params_update_derived_thresholds():
    preset = get_kis_preset("mean_reversion")
    assert preset is not None

    state = apply_kis_preset_params(
        preset,
        {"buy_threshold": -5, "sell_threshold": 5},
    )

    assert state["entry"]["conditions"][0]["right"]["value"] == 95
    assert state["exit"]["conditions"][0]["right"]["value"] == 105


def test_kis_preset_execute_params_keep_fractional_values():
    preset = get_kis_preset("vwap_reclaim")
    assert preset is not None

    state = apply_kis_preset_params(
        preset,
        {"change_threshold": 0.5},
    )

    assert state["entry"]["conditions"][1]["right"]["value"] == 0.5


def test_kis_preset_execute_params_update_breakout_margin():
    preset = get_kis_preset("week52_high")
    assert preset is not None

    state = apply_kis_preset_params(
        preset,
        {"breakout_margin": 0.5},
    )

    assert state["entry"]["conditions"][1]["right"]["value"] == 0.5
    assert state["exit"]["conditions"][1]["right"]["value"] == 0.5


def test_candlestick_builder_condition_preserves_signal_direction():
    state = kis_state_to_builder_state(
        {
            "metadata": {
                "id": "candle_test",
                "name": "Candle Test",
                "category": "candlestick",
            },
            "indicators": [
                {
                    "id": "engulfing_1",
                    "indicatorId": "engulfing",
                    "alias": "engulfing_1",
                    "params": {},
                    "output": "value",
                }
            ],
            "entry": {
                "logic": "AND",
                "conditions": [
                    {
                        "id": "entry_1",
                        "isCandlestick": True,
                        "candlestickAlias": "engulfing_1",
                        "candlestickSignal": "bullish",
                        "left": {"type": "indicator", "indicatorAlias": "engulfing_1"},
                        "operator": "greater_than",
                        "right": {"type": "value", "value": 0},
                    }
                ],
            },
            "exit": {
                "logic": "OR",
                "conditions": [
                    {
                        "id": "exit_1",
                        "isCandlestick": True,
                        "candlestickAlias": "engulfing_1",
                        "candlestickSignal": "bearish",
                        "left": {"type": "indicator", "indicatorAlias": "engulfing_1"},
                        "operator": "greater_than",
                        "right": {"type": "value", "value": 0},
                    }
                ],
            },
        }
    )

    assert state.entry.conditions[0].operator.value == "greater_than"
    assert state.exit.conditions[0].operator.value == "less_than"


@pytest.mark.asyncio
async def test_kis_builder_compat_routes_execute_paper_signal():
    from services.dashboard.routes import kis_builder

    listed = await kis_builder.list_strategies()
    assert listed["total"] >= 27

    response = await kis_builder.execute_strategy(
        kis_builder.ExecuteStrategyRequest(
            strategy_id="donchian_breakout",
            stocks=["005930"],
        )
    )

    assert response["status"] == "success"
    assert response["results"][0]["action"] == "BUY"
