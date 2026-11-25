"""``rsi`` and ``williams_r`` against TA-Lib, to the last bit."""

from __future__ import annotations

import numpy as np
import pytest

from shared.indicators.fields import (
    FieldBar,
    FieldEvaluator,
    WilderRsi,
    WilliamsR,
)

from .conftest import bar, parsed

CLOSES: tuple[float, ...] = (
    44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
    45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64,
    46.21, 46.25, 45.71, 46.45, 45.78, 45.35, 44.03, 44.18, 44.22, 44.57,
)  # fmt: skip


def _bars() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A fixed high/low/close frame: the closes above, with a 0.6/0.7 range."""
    close = np.asarray(CLOSES, dtype=float)
    return close + 0.6, close - 0.7, close


def _random_bars(count: int = 4000) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A longer frame from a FIXED seed — many bars, still reproducible."""
    rng = np.random.default_rng(20261120)
    base = 40000.0 + np.cumsum(rng.normal(0.0, 25.0, count))
    high = base + np.abs(rng.normal(0.0, 12.0, count))
    low = base - np.abs(rng.normal(0.0, 12.0, count))
    close = np.clip(base + rng.normal(0.0, 8.0, count), low, high)
    return high, low, close


def _assert_matches(ours: list[float | None], reference: np.ndarray) -> None:
    """Every bar: a missing value exactly where TA-Lib has NaN, else ``==``."""
    assert len(ours) == len(reference)
    compared = 0
    for index, (mine, theirs) in enumerate(zip(ours, reference, strict=True)):
        if mine is None:
            assert np.isnan(theirs), f"bar {index}: we have no value, TA-Lib {theirs!r}"
            continue
        assert not np.isnan(theirs), f"bar {index}: TA-Lib has no value, we {mine!r}"
        assert mine == float(theirs), f"bar {index}: {mine!r} != {float(theirs)!r}"
        compared += 1
    assert compared > 0, "the series produced no comparable bars"


class TestRsiAgainstTalib:
    @pytest.mark.parametrize("period", [2, 3, 5, 14, 20])
    def test_every_bar_equals_talib_rsi(self, period: int) -> None:
        talib = pytest.importorskip("talib")
        _, _, close = _bars()
        op = WilderRsi(period=period, field="rsi")
        ours = [op.update(float(value)) for value in close]
        _assert_matches(ours, talib.RSI(close, timeperiod=period))

    @pytest.mark.parametrize("period", [2, 5, 14, 20])
    def test_four_thousand_bars_equal_talib_rsi(self, period: int) -> None:
        """Long enough that the Wilder recurrence's drift would show."""
        talib = pytest.importorskip("talib")
        _, _, close = _random_bars()
        op = WilderRsi(period=period, field="rsi")
        ours = [op.update(float(value)) for value in close]
        _assert_matches(ours, talib.RSI(close, timeperiod=period))

    def test_warmup_is_talibs_lookback(self) -> None:
        """``period`` changes need ``period + 1`` closes: lookback = period."""
        talib = pytest.importorskip("talib")
        _, _, close = _bars()
        reference = talib.RSI(close, timeperiod=14)
        assert int(np.argmax(~np.isnan(reference))) == 14
        op = WilderRsi(period=14, field="rsi")
        ours = [op.update(float(value)) for value in close]
        assert ours[:14] == [None] * 14
        assert ours[14] is not None


class TestWilliamsRAgainstTalib:
    @pytest.mark.parametrize("period", [2, 3, 5, 14, 20])
    def test_every_bar_equals_talib_willr(self, period: int) -> None:
        talib = pytest.importorskip("talib")
        high, low, close = _bars()
        op = WilliamsR(period=period, field="wr")
        ours = [
            op.update(high=float(h), low=float(low_), close=float(c))
            for h, low_, c in zip(high, low, close, strict=True)
        ]
        _assert_matches(ours, talib.WILLR(high, low, close, timeperiod=period))

    @pytest.mark.parametrize("period", [2, 5, 14, 30, 120])
    def test_four_thousand_bars_equal_talib_willr(self, period: int) -> None:
        """The test that pins the arithmetic ORDER."""
        talib = pytest.importorskip("talib")
        high, low, close = _random_bars()
        op = WilliamsR(period=period, field="wr")
        ours = [
            op.update(high=float(h), low=float(low_), close=float(c))
            for h, low_, c in zip(high, low, close, strict=True)
        ]
        _assert_matches(ours, talib.WILLR(high, low, close, timeperiod=period))

    def test_naive_arithmetic_order_would_not_match(self) -> None:
        """The measurement behind decision 1 of ``stateful.py``'s docstring."""
        talib = pytest.importorskip("talib")
        high, low, close = _random_bars()
        reference = talib.WILLR(high, low, close, timeperiod=14)
        naive_mismatches = 0
        for index in range(13, len(close)):
            window = slice(index - 13, index + 1)
            highest = max(float(value) for value in high[window])
            lowest = min(float(value) for value in low[window])
            naive = -100.0 * ((highest - float(close[index])) / (highest - lowest))
            naive_mismatches += naive != float(reference[index])
        assert naive_mismatches > 0, (
            "the naive order no longer diverges — if TA-Lib changed its "
            "arithmetic, WilliamsR must follow it, not the other way round"
        )

    def test_warmup_is_talibs_lookback(self) -> None:
        """The current bar is in the window: lookback = period - 1."""
        talib = pytest.importorskip("talib")
        high, low, close = _bars()
        reference = talib.WILLR(high, low, close, timeperiod=14)
        assert int(np.argmax(~np.isnan(reference))) == 13
        op = WilliamsR(period=14, field="wr")
        ours = [
            op.update(high=float(h), low=float(low_), close=float(c))
            for h, low_, c in zip(high, low, close, strict=True)
        ]
        assert ours[:13] == [None] * 13
        assert ours[13] is not None


class TestDeclaredDivergenceOnADegenerateWindow:
    """Where a window carries no information, measured on both sides."""

    def test_talib_rsi_on_a_flat_series_is_zero(self) -> None:
        talib = pytest.importorskip("talib")
        flat = np.full(40, 100.0)
        assert float(talib.RSI(flat, timeperiod=14)[-1]) == 0.0

    def test_our_rsi_on_a_flat_series_has_no_value(self) -> None:
        """Only this case — a series with no movement anywhere — is ``None``."""
        op = WilderRsi(period=14, field="rsi")
        assert [op.update(100.0) for _ in range(40)] == [None] * 40

    def test_talib_willr_on_a_flat_window_is_zero(self) -> None:
        talib = pytest.importorskip("talib")
        flat = np.full(40, 100.0)
        assert float(talib.WILLR(flat, flat, flat, timeperiod=14)[-1]) == 0.0

    def test_our_willr_on_a_flat_window_has_no_value(self) -> None:
        op = WilliamsR(period=14, field="wr")
        values = [op.update(high=100.0, low=100.0, close=100.0) for _ in range(40)]
        assert values == [None] * 40

    def test_a_lock_after_movement_holds_the_pre_lock_rsi(self) -> None:
        """NOT ``None``: Wilder's averages decay toward 0 without reaching it."""
        closes = [100.0 + (index % 3) for index in range(30)] + [130.0] * 400
        op = WilderRsi(period=2, field="rsi")
        values = [op.update(close) for close in closes]
        locked = values[30:]
        assert all(value is not None for value in locked)
        assert len(set(locked)) == 1
        assert locked[0] == pytest.approx(99.01960785040595)

    def test_talib_flips_that_same_lock_to_zero(self) -> None:
        """TA-Lib's ``TA_IS_ZERO`` epsilon (1e-8) crosses at bar 81 here."""
        talib = pytest.importorskip("talib")
        closes = np.asarray(
            [100.0 + (index % 3) for index in range(30)] + [130.0] * 400, dtype=float
        )
        reference = talib.RSI(closes, timeperiod=2)
        assert float(reference[80]) == pytest.approx(99.01960785040595)
        assert float(reference[-1]) == 0.0
        first_zero = next(
            index
            for index, value in enumerate(reference)
            if not np.isnan(value) and float(value) == 0.0
        )
        assert 30 < first_zero < 200

    def test_williams_r_does_go_missing_on_that_same_lock(self) -> None:
        """The op whose window is finite: after ``period`` locked bars, no value."""
        op = WilliamsR(period=3, field="wr")
        moving = [(102.0, 98.0, 100.0), (103.0, 99.0, 101.0)]
        for high, low, close in moving:
            op.update(high=high, low=low, close=close)
        locked = [op.update(high=110.0, low=110.0, close=110.0) for _ in range(5)]
        assert locked[-1] is None
        assert locked[-2] is None

    def test_rsi_recovers_once_the_series_moves_again(self) -> None:
        """A flat stretch is a gap in the field, not a permanent death."""
        op = WilderRsi(period=3, field="rsi")
        for _ in range(10):
            assert op.update(100.0) is None
        assert op.update(101.0) == 100.0

    def test_williams_r_recovers_once_the_window_moves_again(self) -> None:
        op = WilliamsR(period=3, field="wr")
        for _ in range(10):
            assert op.update(high=100.0, low=100.0, close=100.0) is None
        assert op.update(high=110.0, low=100.0, close=105.0) is not None


def test_a_declared_field_carries_the_same_values_as_the_class() -> None:
    """The evaluator path and the class agree — no rounding enters the wiring."""
    high, low, close = _bars()
    bars: list[FieldBar] = [
        bar(index, high=float(h), low=float(low_), close=float(c))
        for index, (h, low_, c) in enumerate(zip(high, low, close, strict=True))
    ]
    document = parsed(
        [
            {"name": "rsi14", "op": "rsi", "params": {"period": 14}},
            {"name": "wr14", "op": "williams_r", "params": {"period": 14}},
            {"name": "raw", "op": "gt", "inputs": ["rsi14"], "params": {"const": 0}},
            {"name": "probe", "op": "permissive", "inputs": ["raw"]},
        ]
    )
    records = FieldEvaluator(document).run(bars)

    rsi_op = WilderRsi(period=14, field="rsi14")
    wr_op = WilliamsR(period=14, field="wr14")
    frame = zip(high, low, close, strict=True)
    for record, (h, low_, c) in zip(records, frame, strict=True):
        assert record.values["rsi14"] == rsi_op.update(float(c))
        assert record.values["wr14"] == wr_op.update(
            high=float(h), low=float(low_), close=float(c)
        )
