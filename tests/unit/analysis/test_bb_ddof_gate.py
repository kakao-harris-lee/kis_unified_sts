"""Hermetic guards for the Bollinger ddof gate's core transform.

The gate (``scripts/analysis/bb_ddof_gate.py``) runs bb_reversion twice, swapping
``_calc_bb`` from sample std (ddof=1) to population std (ddof=0). These tests pin
that the swap is *exactly* the ddof change and nothing else — the only thing that
makes the A/B a faithful measurement of the delegation.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

from scripts.analysis.bb_ddof_gate import (
    _calc_bb_population,
    _delta,
    _verdict_lines,
)
from services.trading.indicator_calculations import IndicatorCalculationMixin


def test_population_std_is_exactly_ddof0() -> None:
    closes = [100.0 + (i % 7) - 3.0 * (i % 3) for i in range(40)]
    shim = SimpleNamespace(bb_period=20, bb_std=2.0)
    lower, mid, upper = _calc_bb_population(shim, closes)

    window = closes[-20:]
    mean = sum(window) / len(window)
    pop_std = math.sqrt(sum((x - mean) ** 2 for x in window) / len(window))
    assert mid == mean
    assert upper == mean + 2.0 * pop_std
    assert lower == mean - 2.0 * pop_std


def test_population_bands_are_2p53pct_narrower_than_legacy() -> None:
    """Half-width shrinks by exactly 1 - sqrt((n-1)/n) vs the legacy ddof=1 band."""
    closes = [100.0 + math.sin(i / 3.0) * 5.0 for i in range(60)]
    legacy = IndicatorCalculationMixin()
    legacy.bb_period = 20  # type: ignore[attr-defined]
    legacy.bb_std = 2.0  # type: ignore[attr-defined]
    shim = SimpleNamespace(bb_period=20, bb_std=2.0)

    l1, m1, u1 = legacy._calc_bb(closes)
    l0, m0, u0 = _calc_bb_population(shim, closes)

    assert m0 == m1  # middle band identical (both 20-SMA)
    hw_sample = u1 - m1  # ddof=1 half-width
    hw_pop = u0 - m0  # ddof=0 half-width
    expected_ratio = math.sqrt(19.0 / 20.0)  # pop/sample std ratio at n=20
    assert math.isclose(hw_pop / hw_sample, expected_ratio, rel_tol=1e-12)
    # narrower by ~2.53%
    assert abs((1 - hw_pop / hw_sample) - 0.02532) < 1e-4


def test_delta_helper_handles_none() -> None:
    assert _delta(1.0, 3.0) == 2.0
    assert _delta(None, 3.0) is None
    assert _delta(1.0, None) is None


def test_verdict_refuses_to_decide_on_failed_run() -> None:
    """A skipped/error arm (empty summary) must NOT read as delegate-safe."""
    base = {"status": "skipped", "error": "no_data", "summary": {}}
    pop = {"status": "skipped", "error": "no_data", "summary": {}}
    text = "\n".join(_verdict_lines(base, pop))
    assert "Cannot decide" in text
    assert "delegate-safe" not in text.lower()


def test_verdict_gates_on_structural_trade_collapse() -> None:
    """One arm collapsing to 0 trades gates even when the return delta is tiny."""
    base = {"status": "ok", "summary": {"closed_trades": 120, "total_return_pct": 0.0}}
    pop = {"status": "ok", "summary": {"closed_trades": 0, "total_return_pct": 0.0}}
    text = "\n".join(_verdict_lines(base, pop))
    assert "GATE" in text and "PASS" not in text


def test_verdict_passes_on_neutral_deltas() -> None:
    """Small return/Sharpe deltas + modest trade move → delegate-safe PASS."""
    base = {
        "status": "ok",
        "summary": {
            "closed_trades": 137,
            "total_return_pct": -0.321,
            "sharpe_ratio": -4.298,
            "win_rate_pct": 44.5,
        },
    }
    pop = {
        "status": "ok",
        "summary": {
            "closed_trades": 149,
            "total_return_pct": -0.322,
            "sharpe_ratio": -4.268,
            "win_rate_pct": 44.97,
        },
    }
    text = "\n".join(_verdict_lines(base, pop))
    assert "PASS — delegate-safe" in text
