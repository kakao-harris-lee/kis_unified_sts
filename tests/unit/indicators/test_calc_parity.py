"""지표 계산 경로 parity/특성화(characterization) 테스트 하네스."""

import math

import numpy as np
import pandas as pd
import pytest

from shared.indicators.momentum import RSICalculator, StochasticCalculator
from shared.indicators.streaming.calculations import IndicatorCalculationMixin
from shared.indicators.streaming.candles import Candle

pytestmark = pytest.mark.unit


_N_BARS = 64


def _build_ohlcv() -> dict[str, list[float]]:
    """결정론적 OHLCV 딕셔너리 생성."""
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    volumes: list[float] = []
    for i in range(_N_BARS):
        close = 100.0 + 0.12 * i + 4.0 * math.sin(i / 4.0) + 1.5 * math.cos(i / 2.3)
        span = 0.8 + 0.5 * abs(math.sin(i / 3.0))
        high = close + span
        low = close - span * (0.7 + 0.3 * abs(math.cos(i / 5.0)))
        open_ = close - 0.4 * math.sin(i / 2.0)
        high = max(high, open_, close)
        low = min(low, open_, close)
        volume = 2000.0 + 900.0 * abs(math.sin(i / 2.5)) + 15.0 * i
        opens.append(open_)
        highs.append(high)
        lows.append(low)
        closes.append(close)
        volumes.append(volume)
    return {
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    }


@pytest.fixture(scope="module")
def ohlcv() -> dict[str, list[float]]:
    """모듈 스코프 결정론적 OHLCV (읽기 전용으로만 사용)."""
    return _build_ohlcv()


@pytest.fixture
def frame(ohlcv: dict[str, list[float]]) -> pd.DataFrame:
    """함수 스코프 DataFrame."""
    return pd.DataFrame(ohlcv)


@pytest.fixture
def candles(ohlcv: dict[str, list[float]]) -> list[Candle]:
    """런타임 Candle 리스트."""
    return [
        Candle(
            open=ohlcv["open"][i],
            high=ohlcv["high"][i],
            low=ohlcv["low"][i],
            close=ohlcv["close"][i],
            volume=ohlcv["volume"][i],
            minute=930 + i,
        )
        for i in range(_N_BARS)
    ]


class _RuntimeIndicatorHost(IndicatorCalculationMixin):
    """Mixin 의 인스턴스 메서드(``_calc_rsi``/``_calc_bb``)를 호출하기 위한 최소 host."""

    def __init__(self) -> None:
        self.bb_period = 20
        self.bb_std = 2.0
        self.rsi_period = 14


@pytest.fixture
def runtime_host() -> _RuntimeIndicatorHost:
    return _RuntimeIndicatorHost()


_RSI_SHARED_WILDER = 47.099143
_RSI_RUNTIME_WILDER = 47.099143
_RSI_CONVERGENCE_TOL = 1e-6

_STOCH_K_RUNTIME = 32.771277
_STOCH_D_RUNTIME = 49.647273
_STOCH_K_SHARED = 56.017756
_STOCH_D_SHARED = 77.266641

_ADX_RUNTIME_WILDER = 31.719136

_BB_LOWER = 99.902454
_BB_MID = 107.210789
_BB_UPPER = 114.519124

_SNAPSHOT_ABS_TOL = 5e-3


def test_rsi_range_invariant_both_paths(
    runtime_host: _RuntimeIndicatorHost, frame: pd.DataFrame
) -> None:
    """RSI 는 두 경로 모두 [0, 100] 범위 불변식을 지킨다."""
    rsi_runtime = runtime_host._calc_rsi(frame["close"].tolist())
    rsi_shared = float(RSICalculator(period=14).calculate(frame)["rsi"].iloc[-1])

    assert 0.0 <= rsi_runtime <= 100.0
    assert 0.0 <= rsi_shared <= 100.0


def test_rsi_runtime_uses_wilder_smoothing(
    runtime_host: _RuntimeIndicatorHost, frame: pd.DataFrame
) -> None:
    """런타임 RSI 가 Wilder EMA(shared 표준)로 수렴했음을 스냅샷으로 고정 (M2)."""
    rsi_runtime = runtime_host._calc_rsi(frame["close"].tolist())
    assert rsi_runtime == pytest.approx(_RSI_RUNTIME_WILDER, abs=_SNAPSHOT_ABS_TOL)


def test_rsi_shared_uses_wilder_ema_smoothing(frame: pd.DataFrame) -> None:
    """shared RSI 는 Wilder EMA(alpha=1/period) 방식임을 스냅샷으로 고정."""
    rsi_shared = float(RSICalculator(period=14).calculate(frame)["rsi"].iloc[-1])
    assert rsi_shared == pytest.approx(_RSI_SHARED_WILDER, abs=_SNAPSHOT_ABS_TOL)


def test_rsi_two_paths_converge(
    runtime_host: _RuntimeIndicatorHost, frame: pd.DataFrame
) -> None:
    """두 RSI 경로가 이제 **동일**함을 안전망으로 고정 (M2, 2026-07-04)."""
    rsi_runtime = runtime_host._calc_rsi(frame["close"].tolist())
    rsi_shared = float(RSICalculator(period=14).calculate(frame)["rsi"].iloc[-1])
    delta = abs(rsi_runtime - rsi_shared)

    assert (
        delta < _RSI_CONVERGENCE_TOL
    ), "RSI 런타임/shared 경로가 다시 벌어짐 — 런타임이 Wilder 표준에서 이탈?"
    assert rsi_runtime == pytest.approx(_RSI_SHARED_WILDER, abs=_SNAPSHOT_ABS_TOL)


def test_stochastic_key_schemas_coexist(
    candles: list[Candle], frame: pd.DataFrame
) -> None:
    """런타임 ``stoch_k``/``stoch_d`` 와 shared ``sto_k``/``sto_d`` 가 공존함을 명시."""
    stoch_k, stoch_d = IndicatorCalculationMixin._calc_stochastic(candles)
    runtime_result = {"stoch_k": stoch_k, "stoch_d": stoch_d}

    shared_df = StochasticCalculator().calculate(frame)

    runtime_keys = set(runtime_result.keys())
    shared_keys = {"sto_k", "sto_d"}

    assert runtime_keys == {"stoch_k", "stoch_d"}
    assert "sto_k" in shared_df.columns
    assert "sto_d" in shared_df.columns
    assert runtime_keys.isdisjoint(shared_keys)


def test_stochastic_values_in_range_and_snapshotted(
    candles: list[Candle], frame: pd.DataFrame
) -> None:
    """두 Stochastic 값 모두 [0, 100] 범위 + 현재 값 스냅샷."""
    stoch_k, stoch_d = IndicatorCalculationMixin._calc_stochastic(candles)
    shared_df = StochasticCalculator().calculate(frame)
    sto_k = float(shared_df["sto_k"].iloc[-1])
    sto_d = float(shared_df["sto_d"].iloc[-1])

    for value in (stoch_k, stoch_d, sto_k, sto_d):
        assert 0.0 <= value <= 100.0

    assert stoch_k == pytest.approx(_STOCH_K_RUNTIME, abs=_SNAPSHOT_ABS_TOL)
    assert stoch_d == pytest.approx(_STOCH_D_RUNTIME, abs=_SNAPSHOT_ABS_TOL)
    assert sto_k == pytest.approx(_STOCH_K_SHARED, abs=_SNAPSHOT_ABS_TOL)
    assert sto_d == pytest.approx(_STOCH_D_SHARED, abs=_SNAPSHOT_ABS_TOL)


def test_adx_range_invariant_runtime_path(candles: list[Candle]) -> None:
    """ADX/DX 는 [0, 100] 범위 불변식을 지킨다."""
    adx_runtime = IndicatorCalculationMixin._calc_adx(candles, period=14)

    assert adx_runtime is not None
    assert 0.0 <= adx_runtime <= 100.0


def test_adx_runtime_snapshot(candles: list[Candle]) -> None:
    """런타임 ADX 값 스냅샷 (canonical Wilder ADX)."""
    adx_runtime = IndicatorCalculationMixin._calc_adx(candles, period=14)

    assert adx_runtime is not None
    assert adx_runtime == pytest.approx(_ADX_RUNTIME_WILDER, abs=_SNAPSHOT_ABS_TOL)


def test_bollinger_runtime_uses_sample_std_ddof1(
    runtime_host: _RuntimeIndicatorHost, ohlcv: dict[str, list[float]]
) -> None:
    """런타임 BB 는 sample std(ddof=1) 를 쓰며 구조 불변식을 만족."""
    closes = ohlcv["close"]
    lower, mid, upper = runtime_host._calc_bb(closes)

    window = np.asarray(closes[-runtime_host.bb_period :])
    sample_std = float(window.std(ddof=1))
    population_std = float(window.std(ddof=0))

    assert lower < mid < upper
    assert mid == pytest.approx(float(window.mean()), abs=1e-9)
    expected_upper_sample = float(window.mean()) + runtime_host.bb_std * sample_std
    expected_upper_pop = float(window.mean()) + runtime_host.bb_std * population_std
    assert upper == pytest.approx(expected_upper_sample, abs=1e-9)
    assert upper != pytest.approx(expected_upper_pop, abs=1e-6)

    assert lower == pytest.approx(_BB_LOWER, abs=_SNAPSHOT_ABS_TOL)
    assert mid == pytest.approx(_BB_MID, abs=_SNAPSHOT_ABS_TOL)
    assert upper == pytest.approx(_BB_UPPER, abs=_SNAPSHOT_ABS_TOL)
