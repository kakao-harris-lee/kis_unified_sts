"""지표 계산 경로 parity/특성화(characterization) 테스트 하네스.

목적
----
지표 계산 로직이 최소 5개 경로에 분산되어 중복 구현되어 있고, 그 결과 같은
지표라도 경로마다 값(algorithm)과 키 이름(schema)이 갈린다:

    * RSI        : 런타임(rolling-SMA) vs shared(Wilder EMA)  -> 값이 다름
    * Stochastic : 런타임 ``stoch_k``/``stoch_d`` vs shared ``sto_k``/``sto_d``
                   -> 키 이름이 다름 (같은 파일 안에서도 두 규약이 공존)
    * ADX        : 런타임(full Wilder-smoothed ADX) vs regime detector(단일 DX)
                   -> 알고리즘 자체가 다름
    * Bollinger  : 런타임(sample std, ddof=1) vs core polars(rolling_std, ddof=1)
                   -> 동일해야 하는 쌍 (tolerance 비교)

이 파일은 "정답"을 규정하는 테스트가 아니라, **현재 동작을 스냅샷으로 고정하는
안전망**이다. 향후 통합(Single-Source-of-Truth) 리팩토링 시 값/키가 바뀌면 이
테스트가 시끄럽게 실패하여 델타를 드러낸다. 실패하면 통합을 수행한 사람이
스냅샷 상수를 의식적으로 갱신하면 된다.

설계 원칙
--------
* 정확한 float 동치 assert 금지. 대신
  (a) 구조 불변식(키 존재/범위/단조성),
  (b) "일치해야 하는 쌍"은 tolerance 비교,
  (c) "알려진 divergence"는 문서화된 expected 상수 + 델타 floor 로 스냅샷.
* 입력 OHLCV 는 RNG 없이 순수 수식으로 생성한다. numpy/pandas 의 RNG 버전
  정책과 무관하게 완전히 결정론적이므로 스냅샷 상수가 영원히 안정적이다.

주의: 이 파일은 대상 구현 모듈을 절대 수정하지 않는다(읽기/임포트 전용).
"""

import math

import numpy as np
import pandas as pd
import pytest

# 대상 구현 (읽기/임포트 전용 — 수정 금지)
from services.trading.indicator_calculations import IndicatorCalculationMixin
from services.trading.indicator_candles import Candle
from shared.indicators.momentum import RSICalculator, StochasticCalculator
from shared.regime.adaptive_detector import AdaptiveRegimeDetector

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 결정론적 OHLCV 샘플 (RNG 미사용 — 순수 수식)
# ---------------------------------------------------------------------------

_N_BARS = 64  # BB(20)/RSI(14)/ADX(14*2)/Stoch(14) 모두 충분히 채우는 길이


def _build_ohlcv() -> dict[str, list[float]]:
    """결정론적 OHLCV 딕셔너리 생성.

    상승 드리프트 위에 두 개의 서로소 주기 사인/코사인을 겹쳐, 상승/하락
    구간이 골고루 섞이도록 만든다(지표가 극단값으로 포화되지 않게 함).
    RNG 를 쓰지 않으므로 numpy/python 버전과 무관하게 값이 고정된다.
    """
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
        # OHLC 정합성 보장 (high >= max(o,c), low <= min(o,c))
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
    """함수 스코프 DataFrame.

    shared 계산기는 입력 df 에 컬럼을 추가(mutate)하므로, 매 테스트마다 새
    DataFrame 을 제공하여 테스트 간 오염을 막는다.
    """
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
    """Mixin 의 인스턴스 메서드(``_calc_rsi``/``_calc_bb``)를 호출하기 위한 최소 host.

    Mixin 은 ``self.bb_period``/``self.bb_std``/``self.rsi_period`` 를 참조하므로,
    프로덕션 기본값과 동일하게 세팅한 껍데기 클래스를 둔다.
    """

    def __init__(self) -> None:
        self.bb_period = 20
        self.bb_std = 2.0
        self.rsi_period = 14


@pytest.fixture
def runtime_host() -> _RuntimeIndicatorHost:
    return _RuntimeIndicatorHost()


# ---------------------------------------------------------------------------
# 스냅샷 상수 (현재 동작 특성화 — 통합 시 갱신 대상)
# ---------------------------------------------------------------------------
# 아래 값들은 _build_ohlcv() 로 만든 고정 입력에 대해 현재 각 구현이 산출하는
# 실제 값이다. 알고리즘/스키마가 바뀌면 이 상수와 어긋나 테스트가 실패한다.

# RSI: rolling-SMA(런타임) vs Wilder EMA(shared)
_RSI_RUNTIME_SMA = 60.198576
_RSI_SHARED_WILDER = 47.099143
_RSI_KNOWN_DELTA = 13.099432  # 두 알고리즘 사이의 현재 델타(문서화용)

# Stochastic 값 스냅샷 (키 이름은 별도 테스트에서 특성화)
_STOCH_K_RUNTIME = 32.771277
_STOCH_D_RUNTIME = 49.647273
_STOCH_K_SHARED = 56.017756
_STOCH_D_SHARED = 77.266641

# ADX: full Wilder-smoothed ADX(런타임) vs 단일-bar DX(regime detector)
_ADX_RUNTIME_WILDER = 31.719136
_ADX_DETECTOR_DX = 15.873272
_ADX_KNOWN_DELTA = 15.845864

# Bollinger (런타임 ddof=1 sample std)
_BB_LOWER = 99.902454
_BB_MID = 107.210789
_BB_UPPER = 114.519124

# 스냅샷 값 비교용 절대 허용오차. float 라이브러리 버전 드리프트(<1e-6)는
# 흡수하되, 실제 알고리즘 교체(수 단위 변화)는 반드시 잡아내는 크기.
_SNAPSHOT_ABS_TOL = 5e-3


# ---------------------------------------------------------------------------
# 1) RSI 두 경로 대조
# ---------------------------------------------------------------------------


def test_rsi_range_invariant_both_paths(
    runtime_host: _RuntimeIndicatorHost, frame: pd.DataFrame
) -> None:
    """RSI 는 두 경로 모두 [0, 100] 범위 불변식을 지킨다."""
    rsi_runtime = runtime_host._calc_rsi(frame["close"].tolist())
    rsi_shared = float(RSICalculator(period=14).calculate(frame)["rsi"].iloc[-1])

    assert 0.0 <= rsi_runtime <= 100.0
    assert 0.0 <= rsi_shared <= 100.0


def test_rsi_runtime_uses_rolling_sma_smoothing(
    runtime_host: _RuntimeIndicatorHost, frame: pd.DataFrame
) -> None:
    """런타임 RSI 는 gains/losses 의 단순이동평균(SMA) 방식임을 스냅샷으로 고정.

    ``services.trading.indicator_calculations._calc_rsi`` 는 최근 rsi_period 개
    delta 의 평균(SMA)으로 RS 를 계산한다(core polars RSI 와 동일 규약).
    """
    rsi_runtime = runtime_host._calc_rsi(frame["close"].tolist())
    assert rsi_runtime == pytest.approx(_RSI_RUNTIME_SMA, abs=_SNAPSHOT_ABS_TOL)


def test_rsi_shared_uses_wilder_ema_smoothing(frame: pd.DataFrame) -> None:
    """shared RSI 는 Wilder EMA(alpha=1/period) 방식임을 스냅샷으로 고정.

    ``shared.indicators.momentum.RSICalculator`` 는 ewm(alpha=1/period) 로
    gains/losses 를 스무딩한다. 초기 rsi_period 구간을 지수적으로 누적하므로
    런타임 SMA 방식과 값이 갈린다.
    """
    rsi_shared = float(RSICalculator(period=14).calculate(frame)["rsi"].iloc[-1])
    assert rsi_shared == pytest.approx(_RSI_SHARED_WILDER, abs=_SNAPSHOT_ABS_TOL)


def test_rsi_two_paths_diverge_materially(
    runtime_host: _RuntimeIndicatorHost, frame: pd.DataFrame
) -> None:
    """두 RSI 경로가 "다르다는 사실" 자체를 안전망으로 고정.

    왜 다른가: 런타임은 rolling-SMA, shared 는 Wilder-EMA 스무딩이라
    같은 close 시계열에서도 서로 다른 RS 를 낸다. 통합으로 둘이 같아지면
    아래 델타 floor 가 무너져 이 테스트가 실패 -> 의도적 갱신을 유도한다.
    """
    rsi_runtime = runtime_host._calc_rsi(frame["close"].tolist())
    rsi_shared = float(RSICalculator(period=14).calculate(frame)["rsi"].iloc[-1])
    delta = abs(rsi_runtime - rsi_shared)

    # (a) 현재 델타 스냅샷
    assert delta == pytest.approx(_RSI_KNOWN_DELTA, abs=_SNAPSHOT_ABS_TOL)
    # (b) "재현적으로 다르다"는 구조 불변식 (통합 시 무너져 실패로 드러남)
    assert delta > 5.0, "RSI 두 경로가 수렴함 — SoT 통합 발생? 스냅샷 갱신 필요"


# ---------------------------------------------------------------------------
# 2) Stochastic 키 이름 불일치 특성화
# ---------------------------------------------------------------------------


def test_stochastic_key_schemas_coexist(
    candles: list[Candle], frame: pd.DataFrame
) -> None:
    """런타임 ``stoch_k``/``stoch_d`` 와 shared ``sto_k``/``sto_d`` 가 공존함을 명시.

    왜 다른가: 두 구현이 독립적으로 작성되며 서로 다른 키 규약을 채택했다.
    실제로 ``services/trading/indicator_queries.py`` 는 한 파일 안에서
    ``stoch_k``/``stoch_d`` (런타임 계산 경로)와 ``sto_k``/``sto_d`` (shared
    momentum 경로)를 **둘 다** 사용한다 — SoT 통합의 핵심 리스크 포인트.
    """
    # 런타임 경로: 튜플 반환 -> 호출부(indicator_queries)가 stoch_k/stoch_d 로 매핑
    stoch_k, stoch_d = IndicatorCalculationMixin._calc_stochastic(candles)
    runtime_result = {"stoch_k": stoch_k, "stoch_d": stoch_d}

    # shared 경로: DataFrame 컬럼 sto_k/sto_d 로 산출
    shared_df = StochasticCalculator().calculate(frame)

    runtime_keys = set(runtime_result.keys())
    shared_keys = {"sto_k", "sto_d"}

    # 런타임 키 규약
    assert runtime_keys == {"stoch_k", "stoch_d"}
    # shared 키 규약
    assert "sto_k" in shared_df.columns
    assert "sto_d" in shared_df.columns
    # 두 키 체계는 서로소 — 한쪽 키로 다른 쪽 값을 읽으면 KeyError/누락
    assert runtime_keys.isdisjoint(shared_keys)


def test_stochastic_values_in_range_and_snapshotted(
    candles: list[Candle], frame: pd.DataFrame
) -> None:
    """두 Stochastic 값 모두 [0, 100] 범위 + 현재 값 스냅샷.

    값도 다르다: 런타임은 period=14 raw %K 와 마지막 smooth=3 SMA(%D),
    shared 는 fastk=12 slow-stochastic(slowk=5, slowd=5) 이라 스무딩 구조가
    달라 %D 가 특히 크게 갈린다.
    """
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


# ---------------------------------------------------------------------------
# 3) ADX 두 구현 대조
# ---------------------------------------------------------------------------


def test_adx_range_invariant_both_paths(
    candles: list[Candle], ohlcv: dict[str, list[float]]
) -> None:
    """ADX/DX 는 두 구현 모두 [0, 100] 범위 불변식을 지킨다."""
    adx_runtime = IndicatorCalculationMixin._calc_adx(candles, period=14)
    detector = AdaptiveRegimeDetector()
    adx_detector = detector._calc_adx(
        np.asarray(ohlcv["high"]),
        np.asarray(ohlcv["low"]),
        np.asarray(ohlcv["close"]),
        period=14,
    )

    assert adx_runtime is not None
    assert 0.0 <= adx_runtime <= 100.0
    assert 0.0 <= float(adx_detector) <= 100.0


def test_adx_two_implementations_diverge(
    candles: list[Candle], ohlcv: dict[str, list[float]]
) -> None:
    """두 ADX 구현의 알고리즘 차이를 tolerance 비교 + 델타 스냅샷으로 특성화.

    왜 다른가:
      * 런타임 ``_calc_adx`` 는 정통 ADX — DX 를 다시 Wilder 스무딩한 최종값.
      * regime detector ``_calc_adx`` 는 이름만 ADX 이고 실제로는 마지막 바의
        **단일 DX** 를 rolling-mean(단순평균) 기반으로 산출한다(스무딩 없음).
    따라서 같은 OHLC 에서도 값이 크게 벌어진다. 통합 시 둘을 하나로 합치면
    아래 스냅샷/델타 floor 가 무너져 실패로 드러난다.
    """
    adx_runtime = IndicatorCalculationMixin._calc_adx(candles, period=14)
    detector = AdaptiveRegimeDetector()
    adx_detector = float(
        detector._calc_adx(
            np.asarray(ohlcv["high"]),
            np.asarray(ohlcv["low"]),
            np.asarray(ohlcv["close"]),
            period=14,
        )
    )

    assert adx_runtime is not None
    assert adx_runtime == pytest.approx(_ADX_RUNTIME_WILDER, abs=_SNAPSHOT_ABS_TOL)
    assert adx_detector == pytest.approx(_ADX_DETECTOR_DX, abs=_SNAPSHOT_ABS_TOL)

    delta = abs(adx_runtime - adx_detector)
    assert delta == pytest.approx(_ADX_KNOWN_DELTA, abs=_SNAPSHOT_ABS_TOL)
    assert delta > 5.0, "ADX 두 구현이 수렴함 — SoT 통합 발생? 스냅샷 갱신 필요"


# ---------------------------------------------------------------------------
# 4) Bollinger 두 구현 대조
# ---------------------------------------------------------------------------


def test_bollinger_runtime_uses_sample_std_ddof1(
    runtime_host: _RuntimeIndicatorHost, ohlcv: dict[str, list[float]]
) -> None:
    """런타임 BB 는 sample std(ddof=1) 를 쓰며 구조 불변식을 만족.

    ``_calc_bb`` 는 Polars ``rolling_std`` 기본값(ddof=1)에 맞추기 위해
    표본분산(ddof=1)을 쓴다. 여기서는
      (a) lower < mid < upper 단조성,
      (b) mid == 윈도우 평균,
      (c) std 가 ddof=1(표본) 이며 ddof=0(모집단) 과는 다름
    을 특성화한다.
    """
    closes = ohlcv["close"]
    lower, mid, upper = runtime_host._calc_bb(closes)

    window = np.asarray(closes[-runtime_host.bb_period :])
    sample_std = float(window.std(ddof=1))  # Polars rolling_std 기본
    population_std = float(window.std(ddof=0))

    # (a) 단조성
    assert lower < mid < upper
    # (b) 중앙선 == 단순평균
    assert mid == pytest.approx(float(window.mean()), abs=1e-9)
    # (c) ddof=1 사용 확인: sample std 와 일치, population std 와는 불일치
    expected_upper_sample = float(window.mean()) + runtime_host.bb_std * sample_std
    expected_upper_pop = float(window.mean()) + runtime_host.bb_std * population_std
    assert upper == pytest.approx(expected_upper_sample, abs=1e-9)
    assert upper != pytest.approx(expected_upper_pop, abs=1e-6)

    # 값 스냅샷
    assert lower == pytest.approx(_BB_LOWER, abs=_SNAPSHOT_ABS_TOL)
    assert mid == pytest.approx(_BB_MID, abs=_SNAPSHOT_ABS_TOL)
    assert upper == pytest.approx(_BB_UPPER, abs=_SNAPSHOT_ABS_TOL)


def test_bollinger_runtime_matches_core_polars_when_available(
    runtime_host: _RuntimeIndicatorHost, ohlcv: dict[str, list[float]]
) -> None:
    """런타임 BB 와 core.indicator_engine 의 polars BB 가 일치해야 하는 쌍.

    둘 다 period=20, std=2.0, ddof=1 을 쓰므로 값이 근사적으로 같아야 한다
    (이것은 "알려진 divergence" 가 아니라 "일치해야 하는 쌍" 이므로 tolerance
    비교). polars 미설치 환경에서는 skip 한다.
    """
    pl = pytest.importorskip("polars")
    from core.indicator_engine import IndicatorEngine

    df = pl.DataFrame({"close": ohlcv["close"]})
    enriched = IndicatorEngine().add_v35_indicators(df)
    assert enriched is not None, "샘플이 min_rows 를 충족해야 함"

    polars_lower = float(enriched["bb_lower"][-1])
    polars_upper = float(enriched["bb_upper"][-1])

    lower, _mid, upper = runtime_host._calc_bb(ohlcv["close"])

    # 동일해야 하는 쌍 — 넉넉하되 알고리즘 차이는 잡는 tolerance
    assert lower == pytest.approx(polars_lower, abs=1e-6)
    assert upper == pytest.approx(polars_upper, abs=1e-6)
