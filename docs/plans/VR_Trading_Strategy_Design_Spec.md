# VR(Volume Ratio) 기반 트레이딩 전략 시스템 설계서

> **문서 목적**: Claude Code가 이 설계서를 기반으로 VR 지표 기반 매매 신호 시스템을 구현할 수 있도록 모든 요구사항을 구체적으로 정의한다.
> **작성일**: 2026-02-26
> **대상 환경**: Python 3.10+

---

## 1. 시스템 개요

### 1.1 목표
일봉(Daily) 차트 데이터를 기반으로 VR(Volume Ratio, 거래량 비율) 지표를 계산하고, 이동평균선(MA) 및 RSI와 결합하여 **매수/매도 신호를 생성**하는 분석 시스템을 구현한다.

### 1.2 핵심 원리
VR은 일정 기간 동안 **주가 상승일의 거래량 합계**를 **하락일의 거래량 합계**와 비교하여, 시장의 과열 또는 침체 상태를 수치로 나타내는 기술적 지표이다.

### 1.3 시스템 구성 요소

```
[데이터 수집 모듈] → [지표 계산 엔진] → [신호 생성 엔진] → [결과 출력 모듈]
     │                    │                    │                    │
  주가/거래량         VR, MA, RSI          복합 신호 판단        리포트/차트
  일봉 데이터          계산                 매수/매도/관망         시각화
```

---

## 2. 데이터 요구사항

### 2.1 입력 데이터 스키마

| 필드명 | 타입 | 필수 | 설명 |
|--------|------|------|------|
| `date` | `datetime` | ✅ | 거래일 (일봉 기준) |
| `open` | `float` | ✅ | 시가 |
| `high` | `float` | ✅ | 고가 |
| `low` | `float` | ✅ | 저가 |
| `close` | `float` | ✅ | 종가 |
| `volume` | `int` | ✅ | 거래량 |
| `ticker` | `str` | ✅ | 종목 코드 |

### 2.2 데이터 소스 우선순위

1. **1순위**: `pykrx` 라이브러리 (한국 주식 - KRX)
2. **2순위**: `yfinance` 라이브러리 (해외 주식)
3. **3순위**: CSV 파일 직접 로드 (사용자 제공 데이터)

### 2.3 데이터 수집 인터페이스

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class StockData:
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    ticker: str

class DataFetcher:
    """데이터 수집 추상 클래스"""

    def fetch(
        self,
        ticker: str,
        start_date: str,    # "YYYY-MM-DD"
        end_date: str,      # "YYYY-MM-DD"
        market: str = "KRX"  # "KRX" | "US" | "CSV"
    ) -> list[StockData]:
        ...
```

### 2.4 데이터 전처리 규칙

- 거래량이 0인 날(휴장일 등)은 **제외**한다.
- 결측치(NaN)가 있는 행은 **제거**하고 로그를 남긴다.
- 최소 데이터 요구량: VR 계산 기간(기본 20일) + 보조지표 warm-up 기간(RSI 14일, MA 최대값) → **최소 60 거래일** 이상의 데이터를 확보해야 한다.
- 데이터는 반드시 **일봉(Daily)** 기준이어야 한다. (VR 지표의 신뢰도가 가장 높은 시간 프레임)

---

## 3. 지표 계산 엔진

### 3.1 VR (Volume Ratio) 계산

#### 3.1.1 수식 정의

```
VR(%) = (상승일 거래량 합 + 보합일 거래량 합 × 0.5) / (하락일 거래량 합 + 보합일 거래량 합 × 0.5) × 100
```

#### 3.1.2 일별 분류 기준

| 분류 | 조건 | 설명 |
|------|------|------|
| 상승일 (Up Day) | `close[t] > close[t-1]` | 전일 대비 종가 상승 |
| 하락일 (Down Day) | `close[t] < close[t-1]` | 전일 대비 종가 하락 |
| 보합일 (Unchanged Day) | `close[t] == close[t-1]` | 전일 대비 종가 동일 |

#### 3.1.3 파라미터

| 파라미터 | 기본값 | 범위 | 설명 |
|----------|--------|------|------|
| `vr_period` | 20 | 5 ~ 60 | VR 계산 기간 (거래일 수) |

#### 3.1.4 구현 의사 코드

```python
def calculate_vr(closes: list[float], volumes: list[int], period: int = 20) -> list[Optional[float]]:
    """
    VR(Volume Ratio) 계산

    Args:
        closes: 종가 리스트 (시간순 정렬)
        volumes: 거래량 리스트 (시간순 정렬)
        period: VR 산출 기간 (기본 20일)

    Returns:
        VR 값 리스트 (%). 계산 불가능한 초기 구간은 None.
        예: 150.0 → 150%, 300.0 → 300%

    Edge Cases:
        - 하락일 거래량 합이 0이면 → VR = None (division by zero 방지)
        - 보합일 거래량은 상승/하락 양쪽에 절반씩 배분
    """
    vr_values = []

    for i in range(len(closes)):
        if i < period:
            vr_values.append(None)
            continue

        up_volume = 0.0
        down_volume = 0.0
        unchanged_volume = 0.0

        for j in range(i - period + 1, i + 1):
            if closes[j] > closes[j - 1]:
                up_volume += volumes[j]
            elif closes[j] < closes[j - 1]:
                down_volume += volumes[j]
            else:
                unchanged_volume += volumes[j]

        denominator = down_volume + unchanged_volume * 0.5
        if denominator == 0:
            vr_values.append(None)
        else:
            numerator = up_volume + unchanged_volume * 0.5
            vr_values.append((numerator / denominator) * 100)

    return vr_values
```

#### 3.1.5 VR 해석 기준 (상수 정의)

```python
# VR 구간 상수 정의
VR_ZONES = {
    "EXTREME_OVERHEAT": {"min": 400, "max": float("inf"), "label": "극단적 과열", "signal": "STRONG_SELL"},
    "OVERHEAT":         {"min": 300, "max": 400,          "label": "과열권",       "signal": "SELL"},
    "MODERATE_HIGH":    {"min": 150, "max": 300,          "label": "보통~과열",    "signal": "NEUTRAL"},
    "NORMAL":           {"min": 100, "max": 150,          "label": "보통",         "signal": "NEUTRAL"},
    "MODERATE_LOW":     {"min": 75,  "max": 100,          "label": "보통~침체",    "signal": "NEUTRAL"},
    "DEPRESSION":       {"min": 60,  "max": 75,           "label": "침체권",       "signal": "BUY"},
    "BOTTOM":           {"min": 40,  "max": 60,           "label": "바닥권",       "signal": "STRONG_BUY"},
    "EXTREME_BOTTOM":   {"min": 0,   "max": 40,           "label": "극단적 바닥",  "signal": "STRONG_BUY"},
}
```

---

### 3.2 보조 지표 계산

VR은 단독 사용보다 다른 기술적 지표와 병행할 때 승률이 높아지므로, 아래 보조 지표를 반드시 함께 계산한다.

#### 3.2.1 이동평균선 (Moving Average)

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `ma_short` | 5 | 단기 이동평균 기간 |
| `ma_mid` | 20 | 중기 이동평균 기간 |
| `ma_long` | 60 | 장기 이동평균 기간 |

```python
def calculate_ma(closes: list[float], period: int) -> list[Optional[float]]:
    """단순 이동평균(SMA) 계산"""
    # period 미만 구간은 None 반환
    # SMA = 최근 period일 종가의 산술평균
    ...
```

**MA 기반 추세 판단 로직:**

```python
def get_ma_trend(close: float, ma5: float, ma20: float, ma60: float) -> str:
    """
    Returns:
        "STRONG_UPTREND"  : close > ma5 > ma20 > ma60 (정배열)
        "UPTREND"         : close > ma20 and ma20 > ma60
        "DOWNTREND"       : close < ma20 and ma20 < ma60
        "STRONG_DOWNTREND": close < ma5 < ma20 < ma60 (역배열)
        "SIDEWAYS"        : 그 외
    """
    ...
```

#### 3.2.2 RSI (Relative Strength Index)

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `rsi_period` | 14 | RSI 계산 기간 |

```python
def calculate_rsi(closes: list[float], period: int = 14) -> list[Optional[float]]:
    """
    Wilder's smoothing 방식 RSI 계산
    Returns: 0 ~ 100 범위의 RSI 값 리스트
    """
    ...
```

**RSI 해석 기준:**

```python
RSI_ZONES = {
    "OVERBOUGHT":  {"min": 70, "max": 100, "label": "과매수", "signal": "SELL"},
    "NEUTRAL":     {"min": 30, "max": 70,  "label": "중립",   "signal": "NEUTRAL"},
    "OVERSOLD":    {"min": 0,  "max": 30,  "label": "과매도", "signal": "BUY"},
}
```

---

## 4. 복합 신호 생성 엔진

### 4.1 신호 등급 체계

```python
from enum import Enum

class SignalType(Enum):
    STRONG_BUY  = "적극 매수"   # 확신도 높은 매수 신호
    BUY         = "매수"        # 일반 매수 신호
    NEUTRAL     = "관망"        # 관망 (신호 없음)
    SELL        = "매도"        # 일반 매도 신호
    STRONG_SELL = "적극 매도"   # 확신도 높은 매도 신호

@dataclass
class TradeSignal:
    date: datetime
    ticker: str
    signal: SignalType
    confidence: float          # 0.0 ~ 1.0 (신뢰도)
    vr_value: float            # VR 값 (%)
    vr_zone: str               # VR 구간명
    rsi_value: float           # RSI 값
    ma_trend: str              # MA 추세
    price: float               # 현재가 (종가)
    reasons: list[str]         # 신호 발생 사유 리스트
```

### 4.2 복합 신호 판단 로직 (핵심 규칙 테이블)

#### 4.2.1 매수 신호 조건

| 우선순위 | VR 조건 | RSI 조건 | MA 추세 조건 | 결과 신호 | 신뢰도 |
|----------|---------|----------|-------------|-----------|--------|
| 1 | VR ≤ 60 (바닥권) | RSI ≤ 30 (과매도) | 하락추세 둔화 또는 횡보 | **STRONG_BUY** | 0.85 |
| 2 | VR ≤ 75 (침체권) | RSI ≤ 30 (과매도) | 무관 | **STRONG_BUY** | 0.80 |
| 3 | VR ≤ 60 (바닥권) | RSI ≤ 40 | close > MA5 (단기 반등) | **BUY** | 0.75 |
| 4 | VR ≤ 75 (침체권) | RSI ≤ 40 | close > MA20 | **BUY** | 0.70 |
| 5 | VR ≤ 75 (침체권) | 30 < RSI ≤ 50 | 상승추세 또는 횡보 | **BUY** | 0.60 |

#### 4.2.2 매도 신호 조건

| 우선순위 | VR 조건 | RSI 조건 | MA 추세 조건 | 결과 신호 | 신뢰도 |
|----------|---------|----------|-------------|-----------|--------|
| 1 | VR ≥ 400 (극단적 과열) | RSI ≥ 70 (과매수) | 무관 | **STRONG_SELL** | 0.85 |
| 2 | VR ≥ 300 (과열권) | RSI ≥ 70 (과매수) | 무관 | **STRONG_SELL** | 0.80 |
| 3 | VR ≥ 300 (과열권) | RSI ≥ 60 | close < MA5 (단기 하락) | **SELL** | 0.75 |
| 4 | VR ≥ 300 (과열권) | 50 < RSI < 70 | 하락추세 전환 | **SELL** | 0.65 |

#### 4.2.3 관망 조건

- 위 매수/매도 조건에 **모두 해당하지 않는** 경우 → `NEUTRAL` (신뢰도 0.0)
- VR이 100~150% 범위이고 RSI가 40~60 범위인 경우 → 명확한 `NEUTRAL`

### 4.3 주의사항 로직 (경고 플래그)

아래 조건에 해당하면 신호에 **경고 메시지**를 추가한다.

```python
WARNINGS = {
    "VR_OVERHEAT_BUT_MOMENTUM": {
        "condition": "VR >= 300 AND ma_trend == STRONG_UPTREND",
        "message": "⚠️ VR 과열이나 강한 상승 모멘텀 유지 중. 추가 상승 가능성 있음. 분할 매도 권장."
    },
    "VR_BOTTOM_BUT_FALLING": {
        "condition": "VR <= 60 AND ma_trend == STRONG_DOWNTREND",
        "message": "⚠️ VR 바닥권이나 강한 하락 추세. 추가 하락 가능성 있음. 분할 매수 또는 추세 반전 확인 후 진입 권장."
    },
    "DIVERGENCE_VR_RSI": {
        "condition": "VR signals BUY AND RSI signals SELL (또는 반대)",
        "message": "⚠️ VR과 RSI 신호 불일치. 신호 신뢰도 하락. 추가 확인 필요."
    },
    "LOW_VOLUME": {
        "condition": "최근 5일 평균 거래량 < 20일 평균 거래량의 50%",
        "message": "⚠️ 거래량 급감. VR 신뢰도 저하 가능성."
    }
}
```

### 4.4 신호 생성 함수 시그니처

```python
def generate_signal(
    date: datetime,
    ticker: str,
    close: float,
    vr: float,
    rsi: float,
    ma5: float,
    ma20: float,
    ma60: float,
    recent_volumes: list[int]  # 최근 20일 거래량 (경고 판단용)
) -> TradeSignal:
    """
    복합 지표를 종합하여 최종 트레이딩 신호를 생성한다.

    판단 순서:
    1. VR 구간 판별
    2. RSI 구간 판별
    3. MA 추세 판별
    4. 매수 조건 테이블 순회 (우선순위순)
    5. 매도 조건 테이블 순회 (우선순위순)
    6. 해당 없으면 NEUTRAL
    7. 경고 플래그 체크 및 추가
    """
    ...
```

---

## 5. 결과 출력 모듈

### 5.1 콘솔 리포트 (텍스트)

```
================================================================================
📊 VR 분석 리포트 | 삼성전자 (005930) | 2026-02-26
================================================================================

[현재 상태]
  종가: 72,500원
  VR (20일): 68.5% → 침체권 🔵
  RSI (14일): 28.3 → 과매도 🔵
  MA 추세: 하락추세 둔화 (종가 > MA5)

[매매 신호]
  🟢 적극 매수 (STRONG_BUY) | 신뢰도: 85%
  사유:
    - VR 68.5%: 침체권 진입 (75% 이하)
    - RSI 28.3: 과매도 구간 (30 이하)
    - 단기 반등 시그널: 종가가 5일 이동평균 상회

[경고]
  ⚠️ VR 바닥권이나 강한 하락 추세. 분할 매수 권장.

[지표 상세]
  MA5: 71,800원 | MA20: 73,200원 | MA60: 75,100원
  20일 상승일 거래량: 12,345,678
  20일 하락일 거래량: 18,023,456
================================================================================
```

### 5.2 차트 시각화 (matplotlib)

하나의 Figure에 **4개 서브플롯**을 상하로 배치한다.

```
┌─────────────────────────────────────────┐
│ [1] 주가 캔들차트 + MA(5, 20, 60)       │
│     - 매수 신호: 🔺 (녹색 삼각형)        │
│     - 매도 신호: 🔻 (빨간색 역삼각형)     │
├─────────────────────────────────────────┤
│ [2] 거래량 막대 차트                     │
│     - 상승일: 빨간색 | 하락일: 파란색     │
├─────────────────────────────────────────┤
│ [3] VR 차트                             │
│     - 300% 수평선 (과열 기준, 빨간 점선)  │
│     - 150% 수평선 (보통 기준, 회색 점선)  │
│     - 75% 수평선 (침체 기준, 파란 점선)   │
│     - 60% 수평선 (바닥 기준, 녹색 점선)   │
│     - 바닥/침체 영역 하이라이트 (반투명)   │
├─────────────────────────────────────────┤
│ [4] RSI 차트                            │
│     - 70 수평선 (과매수, 빨간 점선)       │
│     - 30 수평선 (과매도, 파란 점선)       │
└─────────────────────────────────────────┘
```

**차트 구현 요구사항:**

```python
def plot_analysis(
    data: list[StockData],
    vr_values: list[float],
    rsi_values: list[float],
    ma5: list[float],
    ma20: list[float],
    ma60: list[float],
    signals: list[TradeSignal],
    ticker: str,
    save_path: Optional[str] = None  # None이면 화면 표시
) -> None:
    """
    4-패널 분석 차트를 생성한다.

    구현 세부:
    - figsize: (16, 12)
    - 서브플롯 높이 비율: [3, 1, 1.5, 1] (주가:거래량:VR:RSI)
    - 한글 폰트: 'NanumGothic' 또는 시스템 기본 한글 폰트
    - mplfinance 사용 권장 (캔들차트)
    - 매수/매도 신호는 주가 차트에 마커로 표시
    - X축은 모든 서브플롯이 공유 (sharex=True)
    - VR/RSI 구간은 axhspan으로 배경 하이라이트
    """
    ...
```

### 5.3 데이터 내보내기

```python
def export_results(
    signals: list[TradeSignal],
    format: str = "csv"  # "csv" | "json" | "xlsx"
) -> str:
    """분석 결과를 파일로 내보낸다. 반환값: 저장된 파일 경로."""
    ...
```

**CSV 출력 컬럼:**

```
date,ticker,close,vr,vr_zone,rsi,rsi_zone,ma_trend,signal,confidence,reasons,warnings
```

---

## 6. 프로젝트 구조

```
vr_trading_strategy/
├── README.md                  # 프로젝트 설명 및 사용법
├── requirements.txt           # 의존성 패키지
├── config.py                  # 전역 설정 (파라미터 기본값, 상수)
├── main.py                    # CLI 엔트리포인트
│
├── data/
│   ├── __init__.py
│   ├── fetcher.py             # 데이터 수집 (pykrx, yfinance, CSV)
│   └── preprocessor.py        # 데이터 전처리 및 검증
│
├── indicators/
│   ├── __init__.py
│   ├── vr.py                  # VR 계산
│   ├── moving_average.py      # 이동평균선 계산
│   └── rsi.py                 # RSI 계산
│
├── strategy/
│   ├── __init__.py
│   ├── signal_generator.py    # 복합 신호 생성 엔진
│   ├── signal_rules.py        # 매수/매도 규칙 정의
│   └── warnings.py            # 경고 플래그 로직
│
├── output/
│   ├── __init__.py
│   ├── console_report.py      # 콘솔 텍스트 리포트
│   ├── chart.py               # matplotlib 차트 시각화
│   └── exporter.py            # CSV/JSON/XLSX 내보내기
│
└── tests/
    ├── test_vr.py             # VR 계산 단위 테스트
    ├── test_rsi.py            # RSI 계산 단위 테스트
    ├── test_signals.py        # 신호 생성 통합 테스트
    └── test_data/
        └── sample_data.csv    # 테스트용 샘플 데이터
```

---

## 7. CLI 인터페이스

```bash
# 기본 사용법: 한국 주식 분석
python main.py --ticker 005930 --market KRX --period 120

# 해외 주식 분석
python main.py --ticker AAPL --market US --period 180

# CSV 데이터 사용
python main.py --csv ./data/my_stock.csv --period 120

# 파라미터 커스터마이징
python main.py --ticker 005930 --market KRX \
    --vr-period 20 \
    --rsi-period 14 \
    --ma-short 5 --ma-mid 20 --ma-long 60

# 결과 내보내기
python main.py --ticker 005930 --market KRX --export csv --output ./results/

# 차트 저장
python main.py --ticker 005930 --market KRX --chart --save-chart ./charts/
```

**CLI 인자 정의:**

| 인자 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `--ticker` | str | (필수*) | 종목 코드 |
| `--market` | str | `KRX` | 시장 (`KRX`, `US`) |
| `--csv` | str | None | CSV 파일 경로 (--ticker 대신 사용) |
| `--period` | int | 120 | 조회 기간 (거래일 수) |
| `--vr-period` | int | 20 | VR 계산 기간 |
| `--rsi-period` | int | 14 | RSI 계산 기간 |
| `--ma-short` | int | 5 | 단기 MA 기간 |
| `--ma-mid` | int | 20 | 중기 MA 기간 |
| `--ma-long` | int | 60 | 장기 MA 기간 |
| `--chart` | flag | False | 차트 표시 |
| `--save-chart` | str | None | 차트 저장 경로 |
| `--export` | str | None | 내보내기 형식 (`csv`, `json`, `xlsx`) |
| `--output` | str | `./output/` | 결과 파일 저장 디렉토리 |

---

## 8. 의존성 패키지

```
# requirements.txt
pandas>=2.0.0
numpy>=1.24.0
matplotlib>=3.7.0
mplfinance>=0.12.10b0
pykrx>=1.0.45
yfinance>=0.2.28
openpyxl>=3.1.0       # xlsx 내보내기용
argparse               # CLI (표준 라이브러리)
```

---

## 9. 테스트 요구사항

### 9.1 단위 테스트

#### VR 계산 테스트 케이스

```python
def test_vr_basic():
    """기본 VR 계산: 상승 10일, 하락 10일 → 거래량 비율 확인"""
    closes = [100, 102, 101, 103, 100, 104, 99, 105, 98, 106,
              97, 107, 96, 108, 95, 109, 94, 110, 93, 111, 92]
    volumes = [1000] * 21
    result = calculate_vr(closes, volumes, period=20)
    # 상승 10일 × 1000 = 10000, 하락 10일 × 1000 = 10000
    # VR = 10000/10000 × 100 = 100%
    assert result[-1] == pytest.approx(100.0, rel=0.01)

def test_vr_all_up():
    """모든 날이 상승 → 하락 거래량 0 → VR = None (division by zero)"""
    closes = list(range(100, 122))  # 계속 상승
    volumes = [1000] * 22
    result = calculate_vr(closes, volumes, period=20)
    assert result[-1] is None

def test_vr_depression():
    """하락 우세 → VR < 75% (침체권)"""
    # 상승 5일(거래량 500), 하락 15일(거래량 1500) 시나리오 구성
    ...

def test_vr_overheat():
    """상승 우세 → VR > 300% (과열권)"""
    ...
```

#### 신호 생성 테스트 케이스

```python
def test_strong_buy_signal():
    """VR ≤ 60 + RSI ≤ 30 → STRONG_BUY"""
    signal = generate_signal(
        date=datetime(2026, 2, 26),
        ticker="005930",
        close=72500,
        vr=55.0,       # 바닥권
        rsi=25.0,       # 과매도
        ma5=71800, ma20=73200, ma60=75100,
        recent_volumes=[10000] * 20
    )
    assert signal.signal == SignalType.STRONG_BUY
    assert signal.confidence >= 0.80

def test_strong_sell_signal():
    """VR ≥ 300 + RSI ≥ 70 → STRONG_SELL"""
    ...

def test_neutral_signal():
    """VR 100~150 + RSI 40~60 → NEUTRAL"""
    ...

def test_warning_divergence():
    """VR BUY + RSI SELL → 경고 플래그 포함"""
    ...
```

### 9.2 통합 테스트

- 실제 종목 데이터를 사용한 End-to-End 테스트
- 데이터 수집 → 지표 계산 → 신호 생성 → 차트 출력 전체 파이프라인 검증
- 최소 3개 종목에 대해 실행하여 에러 없음을 확인

---

## 10. 구현 우선순위 및 단계

### Phase 1: 핵심 엔진 (MVP)
1. `config.py` - 상수 및 기본 파라미터 정의
2. `indicators/vr.py` - VR 계산
3. `indicators/rsi.py` - RSI 계산
4. `indicators/moving_average.py` - MA 계산
5. `strategy/signal_generator.py` - 복합 신호 생성
6. `tests/` - 단위 테스트

### Phase 2: 데이터 연동
7. `data/fetcher.py` - pykrx, yfinance 연동
8. `data/preprocessor.py` - 데이터 전처리
9. `main.py` - CLI 엔트리포인트

### Phase 3: 출력 및 시각화
10. `output/console_report.py` - 텍스트 리포트
11. `output/chart.py` - 4-패널 차트
12. `output/exporter.py` - 파일 내보내기

### Phase 4: 품질 강화
13. 통합 테스트 추가
14. 에러 핸들링 강화
15. 로깅 시스템 추가
16. README.md 문서화

---

## 11. 핵심 설계 원칙 (Claude Code 참고)

1. **일봉 전용**: VR의 신뢰도가 가장 높은 시간 프레임은 일봉이다. 분봉/주봉은 지원하지 않는다.
2. **맹신 금지 반영**: 모든 신호에 신뢰도(confidence)와 경고(warnings)를 포함하여, 사용자가 맹목적으로 따르지 않도록 설계한다.
3. **복합 판단 우선**: VR 단독 신호보다 RSI·MA와의 복합 판단을 항상 우선한다. VR 단독으로는 `NEUTRAL`만 반환한다.
4. **분할 매매 권장**: 과열/바닥 극단 구간에서는 일괄이 아닌 분할 매매를 권장하는 메시지를 포함한다.
5. **방어적 코딩**: division by zero, None 값, 데이터 부족 등 엣지 케이스를 모두 처리한다.
6. **한글 지원**: 리포트, 차트 라벨, 에러 메시지 모두 한글로 출력한다.
