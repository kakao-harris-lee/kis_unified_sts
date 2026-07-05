"""Hermetic guards for the real-data shadow-parity harness.

The harness (``scripts/analysis/shadow_parity_realdata.py``) needs deploy-host
Parquet to run in full, but its *wiring* — the engine↔legacy Comparison table and
the p95 classification — must not rot. These tests exercise that wiring on a
synthetic series (no Parquet), asserting every ``expected="safe"`` row is
near-parity and every ``expected="gate"`` row diverges, so a wrong flat key or
param in any row fails loudly in CI.
"""

from __future__ import annotations

import numpy as np
import pytest

talib = pytest.importorskip("talib")

from scripts.analysis.shadow_parity_realdata import (  # noqa: E402
    _comparisons,
    _LegacyShim,
)
from services.trading.indicator_candles import Candle  # noqa: E402
from shared.indicators.engine import IndicatorSpec, default_engine  # noqa: E402
from shared.indicators.engine.adapters import window_from_bars  # noqa: E402


@pytest.fixture(scope="module")
def candles() -> list[Candle]:
    rng = np.random.default_rng(11)
    n = 260
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.7, n))
    high = close + rng.uniform(0.05, 1.0, n)
    low = close - rng.uniform(0.05, 1.0, n)
    open_ = close + rng.normal(0.0, 0.3, n)
    vol = rng.uniform(1_000.0, 5_000.0, n)
    return [
        Candle(
            open=float(open_[i]),
            high=float(high[i]),
            low=float(low[i]),
            close=float(close[i]),
            volume=float(vol[i]),
            minute=900 + i,
        )
        for i in range(n)
    ]


@pytest.mark.parametrize("comp", _comparisons(), ids=lambda c: c.label)
def test_comparison_row_matches_its_expected_direction(comp, candles) -> None:
    """Each 'safe' row is near-parity; each 'gate' row diverges — over a
    distribution of endpoints, mirroring the harness's robust classification
    (a single endpoint is fragile: e.g. fast/slow %K can momentarily coincide)."""
    engine = default_engine()
    shim = _LegacyShim()
    window = 120
    rels: list[float] = []
    for end in range(window, len(candles) + 1, 10):
        win = candles[end - window : end]
        flat = engine.compute(
            IndicatorSpec.create(comp.engine_id, comp.engine_params),
            window_from_bars(win),
        ).flat_latest()
        new = comp.engine_value(flat)
        old = comp.legacy(shim, win)
        if new is None or old is None or not np.isfinite(new) or not np.isfinite(old):
            continue
        if abs(old) > 1e-12:
            rels.append(abs(new - old) / abs(old))
    assert rels, f"{comp.label}: no finite comparisons produced"
    median_rel = float(np.median(rels))
    if comp.expected == "safe":
        assert median_rel <= 0.01, f"{comp.label} expected parity, median={median_rel}"
    else:
        assert (
            median_rel > 0.01
        ), f"{comp.label} expected divergence, median={median_rel}"


def test_bb_width_isolates_ddof_shift(candles) -> None:
    """bb_width comparison must recover the exact 1-sqrt((n-1)/n) ddof factor."""
    comps = {c.label: c for c in _comparisons()}
    bb = comps["bb_width"]
    engine = default_engine()
    shim = _LegacyShim()
    flat = engine.compute(
        IndicatorSpec.create(bb.engine_id, bb.engine_params),
        window_from_bars(candles),
    ).flat_latest()
    new = bb.engine_value(flat)  # population-std half-width
    old = bb.legacy(shim, candles)  # sample-std half-width
    # legacy (ddof=1) is wider by sqrt(n/(n-1)); rel gap = 1 - sqrt((n-1)/n).
    expected = 1.0 - (19.0 / 20.0) ** 0.5
    assert abs(new - old) / old == pytest.approx(expected, rel=1e-6)


def test_all_labels_unique() -> None:
    labels = [c.label for c in _comparisons()]
    assert len(labels) == len(set(labels))
