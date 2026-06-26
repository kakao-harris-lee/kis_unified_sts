"""Unit tests for VolatilityTargetFuturesSizer (CTA vol-target sizing).

Hermetic: synthetic Signal only. Verifies the vol-target formula, the ATR
fallback, clamping, and long/short symmetry.
"""

from __future__ import annotations

import math

import pytest

from shared.models.signal import Signal, SignalType
from shared.strategy.position.sizers import (
    VolatilityTargetFuturesConfig,
    VolatilityTargetFuturesSizer,
)
from shared.strategy.registry import SizerRegistry

POINT_VALUE = 50_000.0


def _signal(price: float, direction: str = "long", **meta) -> Signal:
    md = {"signal_direction": direction, "direction": direction}
    md.update(meta)
    return Signal(
        code="krx_kospi200f_continuous",
        signal_type=SignalType.ENTRY,
        price=price,
        strategy="cta_momentum",
        metadata=md,
    )


def _config(**kw) -> VolatilityTargetFuturesConfig:
    base = {
        "target_annual_vol": 0.15,
        "point_value_krw": POINT_VALUE,
        "max_contracts": 10,
        "min_contracts": 0,
        "trading_days_per_year": 252,
    }
    base.update(kw)
    return VolatilityTargetFuturesConfig(**base)


def test_vol_target_formula_with_explicit_annual_vol():
    sizer = VolatilityTargetFuturesSizer(_config(max_contracts=100))
    price = 300.0
    ann_vol = 0.20
    equity = 100_000_000.0
    qty = sizer.calculate(_signal(price, daily_return_vol=ann_vol), equity, [])
    # raw = (equity*target_vol) / (ann_vol * price * point_value)
    raw = (equity * 0.15) / (ann_vol * price * POINT_VALUE)
    assert qty == round(raw)


def test_higher_vol_means_fewer_contracts():
    sizer = VolatilityTargetFuturesSizer(_config(max_contracts=100))
    equity = 500_000_000.0
    low = sizer.calculate(_signal(300.0, daily_return_vol=0.10), equity, [])
    high = sizer.calculate(_signal(300.0, daily_return_vol=0.40), equity, [])
    assert low > high  # higher vol → smaller position


def test_atr_fallback_when_no_explicit_vol():
    sizer = VolatilityTargetFuturesSizer(_config(max_contracts=100))
    price = 300.0
    atr = 6.0  # daily-implied vol = 6/300 = 0.02 → annualised 0.02*sqrt(252)
    equity = 200_000_000.0
    qty = sizer.calculate(_signal(price, entry_atr=atr), equity, [])
    ann_vol = (atr / price) * math.sqrt(252)
    raw = (equity * 0.15) / (ann_vol * price * POINT_VALUE)
    assert qty == round(raw)


def test_daily_vol_metadata_is_annualised():
    sizer = VolatilityTargetFuturesSizer(_config(max_contracts=100))
    price = 300.0
    daily = 0.012
    equity = 200_000_000.0
    qty = sizer.calculate(_signal(price, daily_return_vol_daily=daily), equity, [])
    ann_vol = daily * math.sqrt(252)
    raw = (equity * 0.15) / (ann_vol * price * POINT_VALUE)
    assert qty == round(raw)


def test_clamped_to_max_contracts():
    sizer = VolatilityTargetFuturesSizer(_config(max_contracts=2))
    qty = sizer.calculate(_signal(300.0, daily_return_vol=0.05), 10_000_000_000.0, [])
    assert qty == 2


def test_min_contracts_zero_allows_no_trade():
    # Tiny equity, high vol → raw < 0.5 → rounds to 0 (min_contracts=0).
    sizer = VolatilityTargetFuturesSizer(_config(min_contracts=0, max_contracts=10))
    qty = sizer.calculate(_signal(300.0, daily_return_vol=0.50), 1_000_000.0, [])
    assert qty == 0


def test_long_short_symmetry():
    sizer = VolatilityTargetFuturesSizer(_config(max_contracts=100))
    equity = 300_000_000.0
    long_qty = sizer.calculate(_signal(300.0, "long", daily_return_vol=0.2), equity, [])
    short_qty = sizer.calculate(
        _signal(300.0, "short", daily_return_vol=0.2), equity, []
    )
    assert long_qty == short_qty and long_qty > 0


def test_zero_price_returns_zero():
    sizer = VolatilityTargetFuturesSizer(_config())
    assert sizer.calculate(_signal(0.0, daily_return_vol=0.2), 1e8, []) == 0


def test_no_vol_metadata_returns_zero():
    sizer = VolatilityTargetFuturesSizer(_config())
    assert sizer.calculate(_signal(300.0), 1e8, []) == 0  # no vol → no size


def test_registry_lookup():
    assert (
        SizerRegistry.get("volatility_target_futures") is VolatilityTargetFuturesSizer
    )


def test_config_validation():
    with pytest.raises(ValueError):
        VolatilityTargetFuturesConfig(target_annual_vol=0).validate()
    with pytest.raises(ValueError):
        VolatilityTargetFuturesConfig(min_contracts=5, max_contracts=2).validate()
