"""Unit tests for shared.risk.futures_margin (Phase B pure margin math).

Deterministic / I/O-free: injected positions, specs, equity, price, ATR. Covers
long/short symmetry, mini-vs-full tick value, the fail-open/fail-closed matrix,
stress-loss escalation, ATR-coverage degrade, max-additional sizing, and the
Redis field contract.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from shared.risk.futures_margin import (
    MARGIN_RISK_SCHEMA_VERSION,
    MarginProductSpec,
    MarginThresholds,
    compute_margin_risk,
    margin_state_to_fields,
)

_NOW = datetime(2026, 7, 1, 10, 0)

_MINI = MarginProductSpec(
    multiplier_krw_per_point=50_000,
    tick_size_points=0.02,
    initial_margin_rate=0.08,
    maintenance_margin_rate=0.06,
    stress_gap_points=5.0,
    symbol_prefixes=("A05", "105"),
)
_FULL = MarginProductSpec(
    multiplier_krw_per_point=250_000,
    tick_size_points=0.05,
    initial_margin_rate=0.08,
    maintenance_margin_rate=0.06,
    stress_gap_points=5.0,
    symbol_prefixes=("A01", "101"),
)
_SPECS = {"kospi200_mini": _MINI, "kospi200_full": _FULL}
_TH = MarginThresholds(
    watch_margin_usage_pct=0.45,
    reduce_only_margin_usage_pct=0.65,
    block_new_entries_margin_usage_pct=0.80,
    critical_margin_usage_pct=0.90,
    watch_liquidation_buffer_ticks=80,
    critical_liquidation_buffer_ticks=40,
)


def _compute(
    positions,
    *,
    equity=50_000_000,
    atr=None,
    price=400.0,
    product="kospi200_mini",
    snapshot_ok=True,
    fail_closed=False,
):
    return compute_margin_risk(
        positions=positions,
        product_specs=_SPECS,
        reference_product=product,
        account_equity_krw=equity,
        cash_available_krw=None,
        reference_price=price,
        atr_by_symbol=atr if atr is not None else {"A05607": 5.0},
        thresholds=_TH,
        snapshot_ok=snapshot_ok,
        fail_closed=fail_closed,
        asof_ts=_NOW,
    )


def test_long_mini_margin_and_buffers():
    s = _compute(
        [{"code": "A05607", "side": "long", "quantity": 1, "current_price": 400.0}]
    )
    # notional = 1 * 400 * 50,000 = 20,000,000
    assert s.initial_margin_required_krw == pytest.approx(20_000_000 * 0.08)
    assert s.maintenance_margin_required_krw == pytest.approx(20_000_000 * 0.06)
    assert s.margin_usage_pct == pytest.approx(1_600_000 / 50_000_000)
    # maintenance buffer / (|qty| * multiplier) = 48,800,000 / 50,000 = 976 pts
    assert s.liquidation_buffer_points == pytest.approx(976.0)
    assert s.liquidation_buffer_ticks == pytest.approx(976.0 / 0.02)
    # stress = |qty| * multiplier * atr = 50,000 * 5 = 250,000
    assert s.stress_loss_1atr_krw == pytest.approx(250_000)
    assert s.stress_loss_2atr_krw == pytest.approx(500_000)
    assert s.stress_loss_gap_krw == pytest.approx(50_000 * 5.0)
    assert s.risk_level == "ok"


def test_long_short_symmetry():
    long_s = _compute(
        [{"code": "A05607", "side": "long", "quantity": 2, "current_price": 400.0}]
    )
    short_s = _compute(
        [{"code": "A05607", "side": "short", "quantity": 2, "current_price": 400.0}]
    )
    assert short_s.initial_margin_required_krw == long_s.initial_margin_required_krw
    assert (
        short_s.maintenance_margin_required_krw
        == long_s.maintenance_margin_required_krw
    )
    assert short_s.liquidation_buffer_ticks == long_s.liquidation_buffer_ticks
    assert short_s.stress_loss_1atr_krw == long_s.stress_loss_1atr_krw
    assert short_s.stress_loss_gap_krw == long_s.stress_loss_gap_krw


def test_full_product_tick_value_differs_from_mini():
    mini = _compute(
        [{"code": "A05607", "side": "long", "quantity": 1, "current_price": 400.0}]
    )
    full = compute_margin_risk(
        positions=[
            {"code": "A01609", "side": "long", "quantity": 1, "current_price": 400.0}
        ],
        product_specs=_SPECS,
        reference_product="kospi200_full",
        account_equity_krw=50_000_000,
        cash_available_krw=None,
        reference_price=400.0,
        atr_by_symbol={"A01609": 5.0},
        thresholds=_TH,
        snapshot_ok=True,
        fail_closed=False,
        asof_ts=_NOW,
    )
    # full multiplier 250,000 = 5x mini → 5x margin + stress.
    assert full.initial_margin_required_krw == pytest.approx(
        mini.initial_margin_required_krw * 5
    )
    assert full.stress_loss_1atr_krw == pytest.approx(mini.stress_loss_1atr_krw * 5)


def test_stale_account_live_is_critical():
    s = _compute(
        [{"code": "A05607", "side": "long", "quantity": 1, "current_price": 400.0}],
        snapshot_ok=False,
        fail_closed=True,
    )
    assert s.risk_level == "critical"
    assert s.degraded is True
    assert "account_snapshot_stale" in s.missing_components


def test_stale_account_paper_is_degraded_not_critical():
    s = _compute(
        [{"code": "A05607", "side": "long", "quantity": 1, "current_price": 400.0}],
        snapshot_ok=False,
        fail_closed=False,
    )
    assert s.risk_level != "critical"
    assert s.degraded is True


def test_stress_loss_exceeding_buffer_forces_reduce_only():
    # Low usage (< watch) but a huge ATR breaches the maintenance buffer.
    s = _compute(
        [{"code": "A05607", "side": "long", "quantity": 1, "current_price": 400.0}],
        equity=6_000_000,
        atr={"A05607": 100.0},
    )
    assert s.margin_usage_pct < _TH.watch_margin_usage_pct
    assert s.stress_loss_1atr_krw > s.maintenance_buffer_krw
    assert s.risk_level == "reduce_only"


def test_missing_atr_marks_degraded_and_drops_stress():
    s = _compute(
        [{"code": "A05607", "side": "long", "quantity": 1, "current_price": 400.0}],
        atr={},
    )
    assert s.stress_loss_1atr_krw is None
    assert s.stress_loss_2atr_krw is None
    # Gap stress does not need ATR.
    assert s.stress_loss_gap_krw > 0
    assert s.degraded is True
    assert "atr:A05607" in s.missing_components


def test_no_positions_is_ok():
    s = _compute([], atr={})
    assert s.risk_level == "ok"
    assert s.initial_margin_required_krw == 0.0
    assert s.liquidation_buffer_ticks is None
    assert s.max_additional_contracts is not None  # headroom on empty book


def test_max_additional_contracts_sizing():
    # Empty book, equity 50M, block threshold 0.80 → headroom 40M.
    # per-contract initial = 400 * 50,000 * 0.08 = 1,600,000 → floor(40M/1.6M)=25.
    s = _compute([], atr={})
    assert s.max_additional_contracts == 25


def test_missing_reference_price_drops_max_additional():
    s = _compute(
        [{"code": "A05607", "side": "long", "quantity": 1, "current_price": 400.0}],
        price=None,
    )
    assert s.max_additional_contracts is None
    assert s.per_contract_initial_margin_krw is None
    assert "reference_price" in s.missing_components


def test_per_contract_initial_margin_published_for_hedge_lane():
    # 400pt × 50,000/pt × 0.08 = 1,600,000 (reference product = mini).
    s = _compute([], atr={})
    assert s.per_contract_initial_margin_krw == pytest.approx(1_600_000)


def test_unknown_symbol_prefix_recorded_missing():
    s = _compute(
        [{"code": "ZZZ999", "side": "long", "quantity": 1, "current_price": 400.0}]
    )
    assert any(m.startswith("margin_product:") for m in s.missing_components)
    # No resolvable position → treated as an empty book.
    assert s.initial_margin_required_krw == 0.0


def test_fields_contract_is_all_strings_with_null_markers():
    s = _compute(
        [{"code": "A05607", "side": "long", "quantity": 1, "current_price": 400.0}],
        atr={},
    )
    fields = margin_state_to_fields(s)
    assert fields["schema_version"] == str(MARGIN_RISK_SCHEMA_VERSION)
    assert fields["risk_level"] == s.risk_level
    assert fields["stress_loss_1atr_krw"] == ""  # None → "" marker
    assert fields["cash_available_krw"] == ""
    assert all(isinstance(v, str) for v in fields.values())
