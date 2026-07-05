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
    _interpretation_lines,
    _json_safe,
    _LegacyShim,
)
from services.trading.indicator_candles import Candle  # noqa: E402
from shared.indicators.engine import (  # noqa: E402
    IndicatorSpec,
    default_engine,
)
from shared.indicators.engine.adapters import window_from_bars  # noqa: E402
from shared.indicators.engine.spec import OHLCVWindow  # noqa: E402


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


def test_interpretation_membership_derives_from_results() -> None:
    """The prose safe/gate lists must come from the measured classification, so
    the report can never assert 'delegate-safe' for a gate-required row."""
    results = [
        {
            "asset": "stock",
            "indicators": {
                "rsi": {"classification": "delegate-safe"},
                "atr": {"classification": "gate-required"},
                "bb_width": {"classification": "gate-required"},
            },
        }
    ]
    text = "\n".join(_interpretation_lines(results))
    # safe row appears in the delegate-safe sentence, gate rows under gate-required
    assert "`rsi`" in text
    assert "`atr`" in text and "`bb_width`" in text
    # a row that flipped to gate-required must NOT be advertised as delegate-safe:
    flipped = [
        {
            "asset": "stock",
            "indicators": {"rsi": {"classification": "gate-required"}},
        }
    ]
    flipped_text = "\n".join(_interpretation_lines(flipped))
    safe_line = next(
        line for line in flipped_text.splitlines() if line.startswith("**Delegate-safe")
    )
    assert "`rsi`" not in safe_line


def test_rsi_diverges_short_window_but_converges_long() -> None:
    """The warmup finding: TA-Lib RSI (SMA-seed) and legacy _calc_rsi (first-delta
    seed) diverge sharply on short windows and only reach bit-parity at ~200+ bars.
    This is why RSI is NOT drop-in delegate-safe despite the 240-bar harness."""
    import numpy as np

    shim = _LegacyShim()
    rng = np.random.default_rng(3)
    closes = (100 + np.cumsum(rng.normal(0, 0.7, 300))).tolist()

    def engine_rsi(cs: list[float]) -> float:
        w = OHLCVWindow.from_sequences(
            open=cs, high=cs, low=cs, close=cs, volume=[0.0] * len(cs)
        )
        return (
            default_engine()
            .compute(IndicatorSpec.create("rsi", {"period": 14}), w)
            .flat_latest()["rsi"]
        )

    short_diff = abs(engine_rsi(closes[:20]) - shim._calc_rsi(closes[:20]))
    long_diff = abs(engine_rsi(closes) - shim._calc_rsi(closes))
    assert short_diff > 1.0  # materially different early in a session
    assert long_diff < 1e-6  # bit-parity once Wilder warmup washes out the seed
    assert short_diff > long_diff + 5.0


def test_rvol_is_bit_identical_to_legacy(candles) -> None:
    """rvol is the one indicator that is truly drop-in: engine == legacy at any
    window length (both = short-mean / long-mean of volume)."""
    shim = _LegacyShim()
    for wlen in (20, 60, len(candles)):
        win = candles[-wlen:]
        eng = (
            default_engine()
            .compute(
                IndicatorSpec.create("rvol", {"short_window": 5, "long_window": 20}),
                window_from_bars(win),
            )
            .flat_latest()["rvol"]
        )
        assert eng == pytest.approx(shim._calc_rvol(win), abs=1e-9)


def test_interpretation_flags_warmup_sensitive_as_not_drop_in() -> None:
    """An indicator delegate-safe at the long window but gate-required at the short
    window must NOT be listed as drop-in; it goes under the warmup-sensitive warning."""
    results = [
        {
            "asset": "stock",
            "window": 240,
            "indicators": {
                "rsi": {"classification": "delegate-safe"},
                "rvol": {"classification": "delegate-safe"},
            },
        },
        {
            "asset": "stock",
            "window": 30,
            "indicators": {
                "rsi": {"classification": "gate-required"},
                "rvol": {"classification": "delegate-safe"},
            },
        },
    ]
    text = "\n".join(_interpretation_lines(results))
    drop_in_line = next(
        line for line in text.splitlines() if line.startswith("**Delegate-safe")
    )
    assert "`rvol`" in drop_in_line
    assert "`rsi`" not in drop_in_line  # safe only at long window -> not drop-in
    assert "Warmup-sensitive" in text
    warm_line = next(line for line in text.splitlines() if "Warmup-sensitive" in line)
    assert "`rsi`" in warm_line


def test_json_safe_replaces_nonfinite() -> None:
    payload = {"a": float("nan"), "b": [float("inf"), 1.5], "c": {"d": -float("inf")}}
    safe = _json_safe(payload)
    assert safe == {"a": None, "b": [None, 1.5], "c": {"d": None}}
    # and it round-trips through strict JSON
    import json

    json.dumps(safe, allow_nan=False)
