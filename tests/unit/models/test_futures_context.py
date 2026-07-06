"""Unit tests for shared.models.futures_context (Phase C structured context).

Deterministic / I/O-free: injected upstream hashes. Covers basis/foreign-flow
regime labels, carry pressure, per-input degrade with missing_components, the
LLM-vs-composite naming separation, and the Redis field contract.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from shared.models.futures_context import (
    FUTURES_CONTEXT_SCHEMA_VERSION,
    BasisRegimeThresholds,
    ForeignFlowThresholds,
    build_futures_context,
    carry_pressure,
    classify_basis_regime,
    classify_foreign_flow_regime,
    context_to_fields,
)

_NOW = datetime(2026, 7, 1, 10, 0)
_BASIS_TH = BasisRegimeThresholds(fair_band_points=0.25, deep_band_points=1.0)
_FLOW_TH = ForeignFlowThresholds(neutral_qty=2000, strong_qty=8000)


@pytest.mark.parametrize(
    ("dev", "expected"),
    [
        (0.0, "fair"),
        (0.1, "fair"),
        (-0.1, "fair"),
        (0.5, "contango"),
        (1.5, "deep_contango"),
        (-0.5, "backwardation"),
        (-1.5, "deep_backwardation"),
        (None, None),
    ],
)
def test_classify_basis_regime(dev, expected):
    assert classify_basis_regime(dev, _BASIS_TH) == expected


@pytest.mark.parametrize(
    ("qty", "expected"),
    [
        (0, "neutral"),
        (1500, "neutral"),
        (3000, "buy"),
        (9000, "strong_buy"),
        (-3000, "sell"),
        (-9000, "strong_sell"),
        (None, None),
    ],
)
def test_classify_foreign_flow_regime(qty, expected):
    assert classify_foreign_flow_regime(qty, _FLOW_TH) == expected


def test_carry_pressure_amplifies_near_expiry():
    # Same dev, fewer days → stronger carry pull.
    far = carry_pressure(0.5, 20)
    near = carry_pressure(0.5, 2)
    assert near > far > 0.5
    assert carry_pressure(None, 5) is None
    assert carry_pressure(0.5, None) is None


def test_carry_pressure_expiry_day_uses_strongest_scale():
    # dte <= 0 clamps to 1 (no division blowup).
    assert carry_pressure(0.5, 0) == pytest.approx(0.5 * 2.0)


def _full_inputs():
    contract = {
        "front_symbol": "A05607",
        "days_to_expiry": "8",
        "roll_state": "normal",
        "new_entry_front_allowed": "true",
    }
    structure = {
        "basis": "1.20",
        "basis_dev": "0.50",
        "basis_dev_ma5": "0.40",
        "fut_oi_qty": "250000",
        "fut_oi_change": "1200",
        "oi_price_signal": "new_longs",
        "fut_foreign_net_qty": "3000",
        "fut_foreign_net_qty_cum20": "12000",
    }
    risk = {"score": "62.5", "band": "ELEVATED", "regime": "risk_off"}
    margin = {
        "margin_usage_pct": "0.32",
        "liquidation_buffer_ticks": "480.0",
        "risk_level": "ok",
    }
    return contract, structure, risk, margin


def test_build_full_context_composes_all_groups():
    contract, structure, risk, margin = _full_inputs()
    ctx = build_futures_context(
        product="mini",
        contract=contract,
        structure=structure,
        risk=risk,
        margin=margin,
        tick_value_krw=1000.0,
        basis_thresholds=_BASIS_TH,
        foreign_thresholds=_FLOW_TH,
        asof_ts=_NOW,
    )
    assert ctx.front_symbol == "A05607"
    assert ctx.days_to_expiry == 8
    assert ctx.roll_state == "normal"
    assert ctx.new_entry_front_allowed is True
    assert ctx.basis_regime == "contango"
    assert ctx.carry_pressure == pytest.approx(0.5 * (1 + 1 / 8))
    assert ctx.foreign_flow_regime == "buy"
    # Composite Market Risk Score — distinct name from the LLM risk_score.
    assert ctx.market_risk_score == pytest.approx(62.5)
    assert ctx.market_risk_band == "ELEVATED"
    assert ctx.margin_risk_level == "ok"
    assert ctx.tick_value_krw == 1000.0
    # Only slippage_snapshot missing (no published read-model yet).
    assert ctx.missing_components == ("slippage_snapshot",)
    assert ctx.degraded is True  # slippage snapshot always missing today


def test_no_llm_risk_score_field_collision():
    # The composite score maps to market_risk_score; there is no bare
    # `risk_score` attribute that could be confused with the LLM MarketContext.
    _, _, risk, _ = _full_inputs()
    ctx = build_futures_context(
        product="mini",
        contract={},
        structure={},
        risk=risk,
        margin={},
        tick_value_krw=1000.0,
        basis_thresholds=_BASIS_TH,
        foreign_thresholds=_FLOW_TH,
        asof_ts=_NOW,
    )
    assert not hasattr(ctx, "risk_score")
    assert ctx.market_risk_score == pytest.approx(62.5)


@pytest.mark.parametrize("drop", ["contract", "structure", "risk", "margin"])
def test_missing_single_input_still_publishes_with_component(drop):
    contract, structure, risk, margin = _full_inputs()
    inputs = {
        "contract": contract,
        "structure": structure,
        "risk": risk,
        "margin": margin,
    }
    inputs[drop] = {}
    ctx = build_futures_context(
        product="mini",
        contract=inputs["contract"],
        structure=inputs["structure"],
        risk=inputs["risk"],
        margin=inputs["margin"],
        tick_value_krw=1000.0,
        basis_thresholds=_BASIS_TH,
        foreign_thresholds=_FLOW_TH,
        asof_ts=_NOW,
    )
    assert drop in ctx.missing_components
    assert ctx.degraded is True


def test_missing_tick_value_recorded():
    contract, structure, risk, margin = _full_inputs()
    ctx = build_futures_context(
        product="mini",
        contract=contract,
        structure=structure,
        risk=risk,
        margin=margin,
        tick_value_krw=None,
        basis_thresholds=_BASIS_TH,
        foreign_thresholds=_FLOW_TH,
        asof_ts=_NOW,
    )
    assert "tick_value" in ctx.missing_components
    assert ctx.tick_value_krw is None


def test_fields_contract_all_strings_with_null_markers():
    ctx = build_futures_context(
        product="mini",
        contract={},
        structure={},
        risk={},
        margin={},
        tick_value_krw=None,
        basis_thresholds=_BASIS_TH,
        foreign_thresholds=_FLOW_TH,
        asof_ts=_NOW,
    )
    fields = context_to_fields(ctx)
    assert fields["schema_version"] == str(FUTURES_CONTEXT_SCHEMA_VERSION)
    assert fields["product"] == "mini"
    assert fields["front_symbol"] == ""
    assert fields["basis_regime"] == ""
    assert fields["market_risk_score"] == ""
    assert fields["new_entry_front_allowed"] == ""  # None → "" (tri-state)
    assert all(isinstance(v, str) for v in fields.values())
