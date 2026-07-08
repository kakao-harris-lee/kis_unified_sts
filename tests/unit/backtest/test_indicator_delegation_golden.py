"""Golden regression pins for backtest-adapter indicator math (P1-b1).

These tests freeze the exact hand-rolled indicator math that
``shared/backtest/daily_adapter.py`` (SMA / RSI / ATR / highest-high /
volume-ratio prescan), ``shared/backtest/adapter.py`` (``_MarketDataEnricher``
high_N / rvol / VWAP / volume velocity+acceleration) and
``shared/backtest/market_context_replay.py`` (ATR-14 partial-window mean)
carried BEFORE delegation to the indicator package, and assert that the
production paths reproduce those numbers BIT-IDENTICALLY — exact float
equality with NaN positions preserved (``np.testing.assert_array_equal``).

Any numeric drift introduced by the delegation refactor fails here. A handful
of hard-coded literal spot pins additionally protect against BOTH sides
drifting together (e.g. a frozen copy being "fixed" alongside production).

Do NOT edit the ``_frozen_*`` reference implementations: they are verbatim
pre-refactor copies (the golden).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd

from shared.backtest.adapter import _MarketDataEnricher
from shared.backtest.daily_adapter import DailyBacktestAdapter
from shared.backtest.market_context_replay import MarketContextReplay
from shared.execution.contract_spec import ContractSpec

# ---------------------------------------------------------------------------
# Deterministic synthetic OHLCV builders
# ---------------------------------------------------------------------------


def _daily_frame(n: int = 320) -> pd.DataFrame:
    """Seeded synthetic daily OHLCV with edge-case stretches.

    - bars 0..29: monotonic up-run (exercises the zero-loss RSI branch, where
      the hand-rolled convention yields NaN, not 100);
    - bars 200..209: flat closes (zero-gain/zero-loss RSI denominator);
    - bars 220..222: zero volume (volume-ratio ``avg > 0`` guard).
    """
    rng = np.random.RandomState(42)
    steps = np.concatenate(
        [np.abs(rng.normal(0.6, 0.3, 30)), rng.normal(0.0, 1.2, n - 30)]
    )
    close = 100.0 + np.cumsum(steps)
    close[200:210] = close[200]
    high = close + np.abs(rng.normal(0.6, 0.25, n))
    low = close - np.abs(rng.normal(0.6, 0.25, n))
    open_ = low + (high - low) * rng.uniform(0.2, 0.8, n)
    volume = rng.randint(1_000, 50_000, n).astype(np.int64)
    volume[220:223] = 0
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def _minute_bars(sessions: int = 7, bars_per_session: int = 30) -> list[dict]:
    """Seeded synthetic 1-minute bars across several sessions (one symbol).

    Integer volumes (incl. a few zeros) so the enricher's running sums hit its
    ``vwap_v > 0`` / ``avg_bar_vol > 0`` guards.
    """
    rng = np.random.RandomState(7)
    bars: list[dict] = []
    price = 50_000.0
    for day in range(sessions):
        day_ts = datetime(2026, 3, 2 + day, 9, 0, 0)
        for i in range(bars_per_session):
            price += float(rng.normal(0.0, 30.0))
            high = price + float(abs(rng.normal(10.0, 5.0)))
            low = price - float(abs(rng.normal(10.0, 5.0)))
            volume = int(rng.randint(0, 5_000))
            if day == 0 and i < 2:
                volume = 0  # zero-volume open (vwap fallback branch)
            bars.append(
                {
                    "code": "005930",
                    "datetime": day_ts + timedelta(minutes=i),
                    "open": float(price - 5.0),
                    "high": float(high),
                    "low": float(low),
                    "close": float(price),
                    "volume": volume,
                }
            )
    return bars


def _replay_frame(sessions: int = 2, bars_per_session: int = 100) -> pd.DataFrame:
    """Seeded synthetic futures 1-minute OHLCV for MarketContextReplay."""
    rng = np.random.RandomState(11)
    rows = []
    price = 350.0
    for day in range(sessions):
        day_ts = datetime(2026, 4, 6 + day, 9, 0, 0)
        for i in range(bars_per_session):
            price += float(rng.normal(0.0, 0.15))
            high = price + float(abs(rng.normal(0.1, 0.05)))
            low = price - float(abs(rng.normal(0.1, 0.05)))
            rows.append(
                {
                    "timestamp": day_ts + timedelta(minutes=i),
                    "open": price - 0.05,
                    "high": high,
                    "low": low,
                    "close": price,
                    "volume": int(rng.randint(50, 500)),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Frozen pre-refactor reference implementations (verbatim copies — DO NOT EDIT)
# ---------------------------------------------------------------------------


def _frozen_rsi(series: pd.Series, period: int) -> pd.Series:
    """Verbatim pre-refactor ``DailyBacktestAdapter._compute_rsi``."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def _frozen_daily_prescan(data: pd.DataFrame) -> pd.DataFrame:
    """Verbatim pre-refactor hand-rolled block of ``prescan_data`` (defaults:
    sma 200/20/60, mid_trend_lookback 5, rsi 5, volume_lookback 20, atr 22,
    lookback 22). The momentum block (rsi/williams_r/macd) already delegated
    to ``calculate_all_momentum`` pre-refactor and is not part of this golden.
    """
    df = data.copy()

    df["sma_200"] = df["close"].rolling(window=200, min_periods=200).mean()
    df["sma_20"] = df["close"].rolling(window=20, min_periods=20).mean()
    df["sma_60"] = df["close"].rolling(window=60, min_periods=60).mean()
    df["sma_60_prev"] = df["sma_60"].shift(5)

    df["rsi_5"] = _frozen_rsi(df["close"], 5)

    df["ma20"] = df["close"].rolling(window=20, min_periods=1).mean()
    volume_avg = df["volume"].shift(1).rolling(window=20, min_periods=1).mean()
    df["volume_ratio"] = np.where(volume_avg > 0, df["volume"] / volume_avg, 1.0)

    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr"] = tr.rolling(window=22, min_periods=22).mean()

    df["highest_high"] = df["high"].rolling(window=22, min_periods=1).max()
    return df


class _FrozenEnricher:
    """Verbatim pre-refactor ``_MarketDataEnricher`` derived-field math
    (single-symbol tracking state + ``enrich``; prescan map not exercised)."""

    def __init__(self, breakout_period: int = 5, rvol_avg_days: int = 5):
        from collections import defaultdict, deque

        self._breakout_period = breakout_period
        self._rvol_avg_days = rvol_avg_days
        self._prev_day_volume_map: dict[str, dict[str, float]] = {}
        self._current_date: dict[str, str] = {}
        self._daily_volume: dict[str, float] = {}
        self._prev_day_volume: dict[str, float] = {}
        self._prev_day_close: dict[str, float] = {}
        self._change_ref_close: dict[str, float] = {}
        self._daily_closes: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
        self._daily_highs: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
        self._daily_volumes: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
        self._vwap_pv_sum: dict[str, float] = {}
        self._vwap_v_sum: dict[str, float] = {}
        self._recent_volumes: dict[str, deque] = defaultdict(lambda: deque(maxlen=5))
        self._all_bar_volumes: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=500)
        )

    def enrich(self, bar: dict, timestamp: datetime) -> dict:
        code = str(bar.get("code", "BACKTEST") or "BACKTEST")
        date_str = timestamp.strftime("%Y-%m-%d")
        close = float(bar.get("close", 0) or 0)
        high = float(bar.get("high", 0) or 0)
        volume = float(bar.get("volume", 0) or 0)
        typical_price = (
            float(bar.get("high", close) or close)
            + float(bar.get("low", close) or close)
            + close
        ) / 3.0

        prev_date = self._current_date.get(code)
        if prev_date != date_str:
            if prev_date is not None:
                self._prev_day_volume[code] = self._daily_volume.get(code, 0)
                self._change_ref_close[code] = self._prev_day_close.get(code, 0)
                day_vol = self._daily_volume.get(code, 0)
                if day_vol > 0:
                    self._daily_volumes[code].append(day_vol)
            self._daily_volume[code] = 0.0
            self._vwap_pv_sum[code] = 0.0
            self._vwap_v_sum[code] = 0.0
            self._current_date[code] = date_str

        if not self._daily_closes[code] or prev_date != date_str:
            self._daily_closes[code].append(close)
            self._daily_highs[code].append(high)
        else:
            self._daily_closes[code][-1] = close
            if high > self._daily_highs[code][-1]:
                self._daily_highs[code][-1] = high

        self._daily_volume[code] = self._daily_volume.get(code, 0) + volume

        if code not in self._prev_day_close and prev_date is None:
            self._prev_day_close[code] = float(bar.get("open", close) or close)
            self._change_ref_close[code] = self._prev_day_close[code]

        pdv = self._prev_day_volume.get(code, 0)
        if pdv == 0 and self._prev_day_volume_map:
            pdv = self._prev_day_volume_map.get(code, {}).get(date_str, 0)
        bar["prev_day_volume"] = int(pdv)

        bar["volume"] = int(self._daily_volume[code])

        ref_close = self._change_ref_close.get(code, 0)
        if ref_close > 0:
            bar["change_pct"] = (close - ref_close) / ref_close * 100.0
        else:
            bar["change_pct"] = 0.0

        period = self._breakout_period
        highs = list(self._daily_highs[code])
        if len(highs) >= period + 1:
            bar[f"high_{period}"] = max(highs[-(period + 1) : -1])
        elif len(highs) >= 2:
            bar[f"high_{period}"] = max(highs[:-1])
        else:
            bar[f"high_{period}"] = high

        self._all_bar_volumes[code].append(volume)
        bar_vols = list(self._all_bar_volumes[code])
        if len(bar_vols) >= 20:
            avg_bar_vol = sum(bar_vols[:-1]) / (len(bar_vols) - 1)
            bar["rvol"] = volume / avg_bar_vol if avg_bar_vol > 0 else 1.0
        else:
            bar["rvol"] = 1.0

        self._vwap_pv_sum[code] = self._vwap_pv_sum.get(code, 0) + typical_price * volume
        self._vwap_v_sum[code] = self._vwap_v_sum.get(code, 0) + volume
        vwap_v = self._vwap_v_sum[code]
        bar["vwap"] = self._vwap_pv_sum[code] / vwap_v if vwap_v > 0 else close

        self._recent_volumes[code].append(volume)
        vols = list(self._recent_volumes[code])
        if len(vols) >= 2:
            bar["volume_velocity"] = vols[-1] - vols[-2]
        else:
            bar["volume_velocity"] = 0.0
        if len(vols) >= 3:
            v1 = vols[-1] - vols[-2]
            v0 = vols[-2] - vols[-3]
            bar["volume_acceleration"] = v1 - v0
        else:
            bar["volume_acceleration"] = 0.0

        self._prev_day_close[code] = close

        return bar


def _frozen_compute_atr(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray
) -> np.ndarray:
    """Verbatim pre-refactor ``market_context_replay._compute_atr`` (ATR-14,
    TR with bar-0 = H-L, partial-window numpy slice means from bar 0)."""
    _ATR_PERIOD = 14
    n = len(closes)
    tr = np.empty(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    atr = np.empty(n)
    for i in range(n):
        start = max(0, i - _ATR_PERIOD + 1)
        atr[i] = tr[start : i + 1].mean()
    return atr


# ---------------------------------------------------------------------------
# Goldens
# ---------------------------------------------------------------------------

_DAILY_COLS = [
    "sma_200",
    "sma_20",
    "sma_60",
    "sma_60_prev",
    "rsi_5",
    "ma20",
    "volume_ratio",
    "atr",
    "highest_high",
]

_ENRICH_KEYS = [
    "prev_day_volume",
    "volume",
    "change_pct",
    "high_5",
    "rvol",
    "vwap",
    "volume_velocity",
    "volume_acceleration",
]


def _records_col(records: list[dict], key: str) -> np.ndarray:
    return np.array([rec[key] for rec in records], dtype=np.float64)


class TestDailyAdapterPrescanGolden:
    def test_prescan_bit_identical_to_frozen(self):
        df = _daily_frame()
        expected = _frozen_daily_prescan(df)

        adapter = DailyBacktestAdapter(
            SimpleNamespace(name="golden"),  # type: ignore[arg-type]
            {},
        )
        adapter.prescan_data(df)

        assert len(adapter._precomputed) == len(df)
        for col in _DAILY_COLS:
            np.testing.assert_array_equal(
                _records_col(adapter._precomputed, col),
                expected[col].to_numpy(dtype=np.float64),
                err_msg=f"numeric drift in daily prescan column '{col}'",
            )

    def test_prescan_spot_pins(self):
        """Hard literal pins (full float repr) against both-sides drift."""
        df = _daily_frame()
        adapter = DailyBacktestAdapter(
            SimpleNamespace(name="golden"),  # type: ignore[arg-type]
            {},
        )
        adapter.prescan_data(df)
        rec_last = adapter._precomputed[-1]
        rec_100 = adapter._precomputed[100]

        assert rec_last["sma_200"] == SPOT_SMA200_LAST
        assert rec_last["rsi_5"] == SPOT_RSI5_LAST
        assert rec_last["atr"] == SPOT_ATR_LAST
        assert rec_last["volume_ratio"] == SPOT_VR_LAST
        assert rec_100["highest_high"] == SPOT_HH_100
        # zero-loss up-run start: hand-rolled RSI convention is NaN (not 100)
        assert np.isnan(rec_100["sma_200"])
        assert np.isnan(adapter._precomputed[10]["rsi_5"])
        # zero-volume bars fall back to ratio 1.0 only when avg is 0 — here the
        # trailing average is > 0, so the ratio is exactly 0.0
        assert adapter._precomputed[221]["volume_ratio"] == 0.0


class TestEnricherGolden:
    def test_enrich_bit_identical_to_frozen(self):
        bars = _minute_bars()
        prod = _MarketDataEnricher(breakout_period=5)
        frozen = _FrozenEnricher(breakout_period=5)

        for bar in bars:
            ts = bar["datetime"]
            got = prod.enrich(dict(bar), ts)
            want = frozen.enrich(dict(bar), ts)
            for key in _ENRICH_KEYS:
                assert got[key] == want[key], (
                    f"numeric drift in enricher field '{key}' at {ts}: "
                    f"{got[key]!r} != {want[key]!r}"
                )
                assert type(got[key]) is type(want[key]), (
                    f"type drift in enricher field '{key}' at {ts}"
                )

    def test_enrich_spot_pins(self):
        bars = _minute_bars()
        prod = _MarketDataEnricher(breakout_period=5)
        last: dict = {}
        for bar in bars:
            last = prod.enrich(dict(bar), bar["datetime"])
        assert last["rvol"] == SPOT_ENRICH_RVOL_LAST
        assert last["vwap"] == SPOT_ENRICH_VWAP_LAST
        assert last["high_5"] == SPOT_ENRICH_HIGH5_LAST
        assert last["volume_acceleration"] == SPOT_ENRICH_ACCEL_LAST


class TestReplayAtrGolden:
    def _replay(self, df: pd.DataFrame) -> MarketContextReplay:
        spec = ContractSpec(
            name="golden",
            multiplier_krw_per_point=250_000,
            tick_size_points=0.05,
            tick_value_krw=12_500,
            commission_rate=0.00003,
            symbol_prefix="101",
        )
        return MarketContextReplay(
            df=df,
            symbol="101S6000",
            macro_snapshot=None,
            scheduled_events=[],
            contract_spec=spec,
        )

    def test_atr_series_bit_identical_to_frozen(self):
        df = _replay_frame()
        replay = self._replay(df)
        expected = _frozen_compute_atr(
            df["high"].to_numpy(dtype=float),
            df["low"].to_numpy(dtype=float),
            df["close"].to_numpy(dtype=float),
        )
        np.testing.assert_array_equal(
            replay._atr_series,
            expected,
            err_msg="numeric drift in replay ATR-14 series",
        )
        assert replay._atr_90th == float(np.nanpercentile(expected, 90))

    def test_atr_context_spot_pins(self):
        df = _replay_frame()
        replay = self._replay(df)
        assert replay._atr_series is not None
        assert float(replay._atr_series[-1]) == SPOT_REPLAY_ATR_LAST
        assert replay._atr_90th == SPOT_REPLAY_ATR_90TH
        ctx = next(iter(replay.iter_contexts()))
        assert ctx.atr_14 == SPOT_REPLAY_CTX_ATR


# Literal spot pins (full repr, generated from the pre-refactor code paths).
SPOT_SMA200_LAST = 117.51518099425
SPOT_RSI5_LAST = 79.95075380853305
SPOT_ATR_LAST = 1.4687443186324425
SPOT_VR_LAST = 0.9015321478436096
SPOT_HH_100 = 114.00638734080042
SPOT_ENRICH_RVOL_LAST = 0.23824652846854733
SPOT_ENRICH_VWAP_LAST = 49400.35368428992
SPOT_ENRICH_HIGH5_LAST = 49974.73564396955
SPOT_ENRICH_ACCEL_LAST = -4613.0
SPOT_REPLAY_ATR_LAST = 0.2438318145813493
SPOT_REPLAY_ATR_90TH = 0.2763946369876343
SPOT_REPLAY_CTX_ATR = 0.2317447600618274
