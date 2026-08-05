"""shared.risk.atr_percentile — the one ATR-percentile calculation.

Two things are pinned here:

1. **Backtest parity.** The live volatility-reference publisher and the
   backtest replay reference must agree on what "the 90th percentile of this
   ATR series" means.  Before this module the only implementation lived inside
   ``MarketContextReplay._precompute``; the tests below pin that the promoted
   helper reproduces that expression exactly, and that the replay itself still
   produces the value it always did.

2. **Never 0.0.** A ``0.0`` threshold is the precise historical defect: every
   live ATR exceeds it, so the filter would reject every entry and halt all
   trading.  The helper returns ``None`` for every degenerate case instead, so
   "unknown threshold" and "threshold of zero" cannot be confused.
"""

from __future__ import annotations

import numpy as np
import pytest

from shared.risk.atr_percentile import DEFAULT_ATR_PERCENTILE, atr_percentile


# The exact expression that used to live in MarketContextReplay._precompute.
# Deliberately re-spelled here rather than imported: an independent anchor
# cannot drift in lockstep with the code it pins.
def _legacy_replay_percentile(series) -> float:
    return float(np.nanpercentile(series, 90))


# ---------------------------------------------------------------------------
# Parity with the pre-promotion backtest expression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "series",
    [
        [1.0, 2.0, 3.0, 4.0, 5.0],
        [0.5, 0.5, 0.5, 0.5],
        list(np.linspace(0.1, 12.5, 137)),
        [3.0, np.nan, 4.0, np.nan, 5.0, 6.0],
        list(np.random.default_rng(20260805).uniform(0.2, 9.0, 500)),
    ],
)
def test_matches_legacy_replay_expression(series) -> None:
    """Same input, same number as the expression the backtest used to inline."""
    assert atr_percentile(series, 90.0) == pytest.approx(
        _legacy_replay_percentile(series)
    )


def test_default_percentile_is_the_90th() -> None:
    """The default matches the historical ``atr_90th_percentile`` naming."""
    assert DEFAULT_ATR_PERCENTILE == 90.0
    series = [1.0, 2.0, 3.0, 9.0]
    assert atr_percentile(series) == pytest.approx(atr_percentile(series, 90.0))


def test_replay_reference_is_unchanged_by_the_promotion() -> None:
    """The backtest replay still computes what it always did, via the helper.

    Pins the DRY promotion end to end: the replay no longer owns the
    arithmetic, and its published ``atr_90th_percentile`` is still the
    full-series 90th percentile of its own ATR series.
    """
    pd = pytest.importorskip("pandas")
    from shared.backtest.market_context_replay import MarketContextReplay

    rng = np.random.default_rng(4242)
    n = 400
    closes = 350.0 + np.cumsum(rng.normal(0.0, 0.35, n))
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-03-02 09:00", periods=n, freq="1min"),
            "open": closes,
            "high": closes + 0.6,
            "low": closes - 0.6,
            "close": closes,
            "volume": np.full(n, 100.0),
        }
    )
    replay = MarketContextReplay(
        df=frame,
        symbol="A05603",
        macro_snapshot=None,
        scheduled_events=[],
        contract_spec=None,
    )

    assert replay._atr_90th == pytest.approx(
        _legacy_replay_percentile(replay._atr_series)
    )
    assert replay._atr_90th > 0.0


# ---------------------------------------------------------------------------
# The "never 0.0" contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("series", "label"),
    [
        ([], "empty"),
        ([np.nan, np.nan], "all-NaN"),
        ([0.0, 0.0, 0.0], "all-zero"),
        ([-1.0, -2.0], "negative"),
    ],
)
def test_undefined_percentile_is_none_not_zero(series, label) -> None:
    """A degenerate series yields None — never a 0.0 threshold.

    ``0.0`` would satisfy ``current_atr > threshold`` for every live reading,
    rejecting every entry.  ``None`` means "no threshold known" and makes the
    filter skip loudly instead.
    """
    assert atr_percentile(series, 90.0) is None, label


def test_all_nan_input_does_not_warn() -> None:
    """The all-NaN branch is taken before numpy can emit its RuntimeWarning."""
    with np.errstate(all="raise"):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert atr_percentile([np.nan, np.nan, np.nan], 90.0) is None


def test_positive_percentile_is_returned_verbatim() -> None:
    assert atr_percentile([1.0, 2.0, 3.0, 4.0], 50.0) == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# Misconfiguration fails loudly, not silently
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("percentile", [-1.0, 100.1, 900.0])
def test_out_of_range_percentile_raises(percentile) -> None:
    """A mis-configured percentile must not silently produce a nonsense bound."""
    with pytest.raises(ValueError, match="within"):
        atr_percentile([1.0, 2.0, 3.0], percentile)


def test_accepts_numpy_array_and_nested_shape() -> None:
    assert atr_percentile(np.array([[1.0, 2.0], [3.0, 4.0]]), 50.0) == pytest.approx(
        2.5
    )
