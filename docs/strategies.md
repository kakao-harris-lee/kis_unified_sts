# Strategy Configuration Guide

전략 설정 및 커스터마이징 가이드

> **Last verified 2026-06-20 (KST).** Enabled/disabled status below reflects
> `config/strategies/stock/*.yaml` as of this date. Runtime/backtest storage is
> Parquet/DuckDB + SQLite + Redis DB 1 (ClickHouse removed 2026-06-03). For the
> live snapshot see [PROJECT_STATUS.md](PROJECT_STATUS.md) and the authoritative
> phased plan in [ROADMAP.md](ROADMAP.md).

## 개요

KIS Unified Trading Platform은 설정 기반(Configuration-Driven) 전략 시스템을 사용합니다. 모든 전략은 YAML 파일로 정의되며, 코드 수정 없이 파라미터를 조정할 수 있습니다.

## 전략 파일 구조

```
config/
├── strategies/
│   ├── stock/               # 주식 전략
│   │   ├── bb_reversion.yaml
│   │   └── v35_optimized.yaml
│   └── futures/             # 선물 전략
│       ├── ofi_momentum.yaml
│       └── pure_micro.yaml
└── risk/                    # 리스크 설정
    ├── stock.yaml
    └── futures.yaml
```

## 전략 스키마

### 기본 구조

```yaml
strategy:
  name: strategy_name        # 전략 식별자
  asset_class: stock|futures # 자산 클래스
  enabled: true              # 활성화 여부

  entry:                     # 진입 설정
    type: entry_type
    params:
      # 진입 파라미터

  exit:                      # 청산 설정
    type: exit_type
    params:
      # 청산 파라미터

  position:                  # 포지션 사이징
    type: sizing_type
    params:
      # 사이징 파라미터
```

---

## 진입 전략 (Entry Strategies)

### Trend Pullback (현재 비활성)

**상태 (2026-06-20):** `enabled: false` — 재검증 대기. 과거 검증은 합성 데이터 기반이었음.
**검증 문서 (historical, archived):** [STOCK_STRATEGY_VALIDATION_SUMMARY.md](archive/STOCK_STRATEGY_VALIDATION_SUMMARY.md)

일봉 추세 필터와 분봉 풀백 시그널을 결합한 다중 시간프레임 전략

```yaml
entry:
  type: trend_pullback
  params:
    # Daily context filter
    daily_sma_period: 20

    # Intraday entry triggers
    bb_period: 20
    bb_std: 2.0
    rsi_period: 14
    rsi_threshold: 34
    williams_period: 14
    williams_reversal_threshold: -20.0

    # Risk management
    minimum_edge_pct: 0.8
    atr_period: 14
    initial_stop_atr_multiplier: 3.5

    # Time filters
    skip_first_minutes: 30
    skip_last_minutes: 15
    signal_cooldown_seconds: 120
```

**진입 조건:**
1. 일봉 SMA(20) 위에서만 진입 (상승 추세)
2. 분봉 볼린저 밴드 하단 터치 + RSI < 34, 또는
3. Williams %R 반전 시그널 (-20 이상 반등)
4. 최소 기대 수익률 0.8% 이상
5. 장 시작 30분, 마감 15분 제외
6. 시그널 간 120초 쿨다운

### Momentum Breakout (현재 활성 — paper 관찰)

**상태 (2026-06-20):** `enabled: true` — paper 관찰용 재활성화 (#443). 재튜닝 미해결.
**검증 문서 (historical, archived):** [STOCK_STRATEGY_VALIDATION_SUMMARY.md](archive/STOCK_STRATEGY_VALIDATION_SUMMARY.md)

일봉 고가 근접과 거래량 트렌드를 활용한 모멘텀 돌파 전략

```yaml
entry:
  type: momentum_breakout
  params:
    # Breakout detection
    breakout_lookback_bars: 20
    breakout_confirmation_bars: 2

    # Volume filters
    rvol_threshold: 1.6
    accumulation_score_threshold: 40

    # Trend mode (BULL regime)
    trend_mode_enabled: true
    trend_ema_fast: 5
    trend_ema_mid: 20
    trend_ema_slow: 60
    trend_pullback_threshold_pct: 0.3

    # Risk management
    minimum_edge_pct: 1.0
    atr_period: 14
    initial_stop_atr_multiplier: 2.0

    # Time filters
    skip_first_minutes: 10
    skip_last_minutes: 10
    signal_cooldown_seconds: 120
```

**진입 조건:**
1. 가격 돌파 감지 (최근 20봉 고가 돌파)
2. RVOL > 1.6 (평균 대비 1.6배 이상 거래량)
3. 거래량 누적 점수 ≥ 40
4. **BULL regime 시:** 완화된 조건 + EMA(5/20/60) 풀백 진입
5. 최소 기대 수익률 1.0% 이상
6. 장 시작 10분, 마감 10분 제외
7. 시그널 간 120초 쿨다운

### BB Lower Reentry (레거시)

볼린저 밴드 하단 이탈 후 복귀 시 진입

```yaml
entry:
  type: bb_lower_reentry
  params:
    bb_period: 20           # 볼린저 밴드 기간
    bb_std: 2.0             # 표준편차 배수
    rsi_period: 14          # RSI 기간
    rsi_oversold: 30        # RSI 과매도 기준
    volume_confirm: true    # 거래량 확인 여부
    volume_ma_period: 20    # 거래량 MA 기간
    volume_threshold: 1.5   # 거래량 배수 기준
```

**진입 조건:**
1. 가격이 볼린저 밴드 하단 아래로 이탈
2. RSI가 과매도 구간(< 30)
3. 거래량이 평균의 1.5배 이상 (선택)
4. 가격이 볼린저 밴드 내로 복귀 시 진입

### V35 Optimized

복합 지표 기반 최적화 전략

```yaml
entry:
  type: v35_optimized
  params:
    bb_period: 20
    bb_std: 2.0
    rsi_period: 14
    rsi_oversold: 35
    macd_fast: 12
    macd_slow: 26
    macd_signal: 9
    volume_filter: true
```

**진입 조건:**
1. 볼린저 밴드 하단 근처
2. RSI < 35
3. MACD 히스토그램 상승 전환
4. 거래량 증가

### OFI Momentum

주문흐름불균형(Order Flow Imbalance) 기반 전략

```yaml
entry:
  type: ofi_momentum
  params:
    ofi_threshold: 1.5      # OFI 임계값 (표준편차)
    ofi_lookback: 20        # OFI 계산 기간
    imbalance_threshold: 0.3 # 불균형 임계값
    liquidity_min: 0.5      # 최소 유동성
```

**진입 조건:**
1. OFI가 임계값 초과 (매수 압력)
2. 호가 불균형이 매수 우위
3. 충분한 유동성 확보

### Microstructure

복합 마이크로스트럭처 전략

```yaml
entry:
  type: microstructure
  params:
    ofi_weight: 0.4
    vpin_weight: 0.3
    spread_weight: 0.3
    signal_threshold: 0.6
```

---

## 청산 전략 (Exit Strategies)

### ATR Dynamic Exit (신규)

**상태:** 활성 (trend_pullback, momentum_breakout 전용)

ATR 기반 동적 스탑로스 및 트레일링 스탑

```yaml
exit:
  type: atr_dynamic
  params:
    atr_period: 14
    initial_stop_atr_multiplier: 2.0
    trailing_activation_atr_multiplier: 2.0
    trailing_distance_atr_multiplier: 1.5
```

**동작 원리:**

```
초기 보호 (Initial Stop)
├── 진입 즉시 ATR 기반 스탑 설정
├── 예: 2.0x ATR = 진입가 - (ATR × 2.0)
└── 목표: 큰 손실 방지

트레일링 활성화 (Trailing Activation)
├── 조건: 수익이 2.0x ATR 도달
├── 동작: 트레일링 스탑 시작
└── 목표: 수익 보호하며 추세 추종

트레일링 스탑 (Trailing Stop)
├── 거리: 최고가 - (ATR × 1.5)
├── 동작: 가격 상승 시 스탑 레벨 상승
└── 목표: 수익 극대화
```

**전략별 파라미터:**

**trend_pullback:**
- Initial Stop: 3.5x ATR (보수적)
- Trailing Activation: 2.0x ATR
- Trailing Distance: 2.0x ATR

**momentum_breakout:**
- Initial Stop: 2.0x ATR (공격적)
- Trailing Activation: 2.0x ATR
- Trailing Distance: 1.5x ATR (타이트)

### Three Stage Exit

3단계 동적 청산 전략

```yaml
exit:
  type: three_stage
  params:
    # Stage 1: Survival (손실 최소화)
    hard_stop_pct: 1.5            # 무조건 손절 (%)

    # Stage 2: Breakeven (본전 확보)
    breakeven_threshold_pct: 1.5  # 본전 스탑 전환 기준 (%)
    breakeven_buffer_pct: 0.1     # 본전 스탑 버퍼 (%)

    # Stage 3: Maximize (수익 극대화)
    maximize_threshold_pct: 3.0   # 트레일링 전환 기준 (%)
    trailing_stop_pct: 2.0        # 트레일링 스탑 폭 (%)
    tight_trailing_pct: 1.0       # 타이트 트레일링 폭 (%)
    tight_trailing_trigger_pct: 10.0  # 타이트 트레일링 전환 (%)
```

**동작 원리:**

```
Stage 1: SURVIVAL (진입 직후)
├── 조건: 손익 < breakeven_threshold
├── 동작: hard_stop_pct에서 손절
└── 목표: 큰 손실 방지

Stage 2: BREAKEVEN (수익 발생 시)
├── 조건: 손익 >= breakeven_threshold
├── 동작: 스탑을 본전+buffer로 이동
└── 목표: 손실 없는 거래 확보

Stage 3: MAXIMIZE (목표 수익 도달 시)
├── 조건: 손익 >= maximize_threshold
├── 동작: 트레일링 스탑 활성화
└── 목표: 추가 수익 추구
```

### Trailing Stop

단순 트레일링 스탑

```yaml
exit:
  type: trailing_stop
  params:
    initial_stop_pct: 2.0    # 초기 스탑
    trailing_pct: 1.5        # 트레일링 폭
    activation_pct: 1.0      # 트레일링 활성화 기준
```

### Time Based Exit

시간 기반 청산

```yaml
exit:
  type: time_based
  params:
    max_hold_minutes: 60     # 최대 보유 시간
    end_of_day_exit: true    # 장 마감 청산
    exit_before_minutes: 10  # 마감 N분 전 청산
```

---

## 포지션 사이징 (Position Sizing)

### Risk Based

리스크 기반 포지션 사이징

```yaml
position:
  type: risk_based
  params:
    max_position_pct: 10.0   # 최대 포지션 비중 (%)
    max_positions: 5         # 최대 포지션 수
    risk_per_trade_pct: 1.0  # 거래당 리스크 (%)
```

### Fixed

고정 수량

```yaml
position:
  type: fixed
  params:
    quantity: 100            # 고정 수량
    max_positions: 3         # 최대 포지션 수
```

---

## 전체 전략 예시

### 주식 - BB Reversion

```yaml
# config/strategies/stock/bb_reversion.yaml
strategy:
  name: bb_reversion
  asset_class: stock
  enabled: true

  entry:
    type: bb_lower_reentry
    params:
      bb_period: 20
      bb_std: 2.0
      rsi_period: 14
      rsi_oversold: 30
      volume_confirm: true
      volume_ma_period: 20
      volume_threshold: 1.5

  exit:
    type: three_stage
    params:
      hard_stop_pct: 1.5
      breakeven_threshold_pct: 1.5
      breakeven_buffer_pct: 0.1
      maximize_threshold_pct: 3.0
      trailing_stop_pct: 2.0
      tight_trailing_pct: 1.0
      tight_trailing_trigger_pct: 10.0

  position:
    type: risk_based
    params:
      max_position_pct: 10.0
      max_positions: 5
      risk_per_trade_pct: 1.0
```

### 선물 - OFI Momentum

```yaml
# config/strategies/futures/ofi_momentum.yaml
strategy:
  name: ofi_momentum
  asset_class: futures
  enabled: true

  entry:
    type: ofi_momentum
    params:
      ofi_threshold: 1.5
      ofi_lookback: 20
      imbalance_threshold: 0.3
      liquidity_min: 0.5

  exit:
    type: time_based
    params:
      max_hold_minutes: 30
      stop_ticks: 5
      target_ticks: 10

  position:
    type: fixed
    params:
      contracts: 1
      max_contracts: 2
```

---

## 새 전략 추가하기

### 1. YAML 파일 생성

```yaml
# config/strategies/stock/my_strategy.yaml
strategy:
  name: my_strategy
  asset_class: stock
  enabled: true

  entry:
    type: existing_entry_type  # 또는 custom
    params:
      # ...

  exit:
    type: three_stage
    params:
      # ...

  position:
    type: risk_based
    params:
      # ...
```

### 2. 커스텀 진입/청산 로직 추가 (선택)

새로운 진입/청산 유형이 필요한 경우:

```python
# shared/strategy/entry/custom.py
from shared.strategy.base import EntrySignalGenerator
from shared.strategy.registry import EntryRegistry

@EntryRegistry.register("my_custom_entry")
class MyCustomEntry(EntrySignalGenerator):
    CONFIG_CLASS = MyEntryConfig

    def _validate_config(self):
        # 설정 검증
        pass

    @property
    def required_indicators(self) -> list[str]:
        return ["sma", "rsi"]

    async def generate(self, context):
        # 진입 로직
        pass
```

### 3. 테스트

```bash
# 백테스트로 검증
sts backtest run --strategy my_strategy --asset stock

# 모의투자로 실시간 테스트
sts paper start --strategy my_strategy --capital 10000000
```

---

## 최적화 (Optimization)

### CLI로 최적화

```bash
sts optimize \
  --strategy bb_reversion \
  --asset stock \
  --metric sharpe_ratio \
  --trials 100 \
  --param "entry.params.bb_period:15:25" \
  --param "entry.params.rsi_oversold:25:40" \
  --param "exit.params.hard_stop_pct:1.0:2.5"
```

### 최적 파라미터 적용

```bash
# 최적 결과 조회
sts backtest best --strategy bb_reversion --asset stock

# MLflow에서 run_id 확인 후 적용
sts backtest apply --run-id <mlflow_run_id>
```

---

## 모범 사례 (Best Practices)

### 1. 파라미터 범위

- `hard_stop_pct`: 1.0% ~ 3.0% (너무 타이트하면 잦은 손절)
- `breakeven_threshold_pct`: 하드스탑과 같거나 약간 높게
- `trailing_stop_pct`: 변동성에 따라 조정

### 2. 백테스트 기간

- 최소 1년 이상의 데이터로 테스트
- 다양한 시장 상황(상승장, 하락장, 횡보장) 포함

### 3. 과최적화 방지

- Out-of-sample 테스트 필수
- 파라미터 개수 최소화
- 단순한 전략 선호

### 4. 리스크 관리

```yaml
position:
  type: risk_based
  params:
    max_position_pct: 10.0   # 단일 종목 최대 10%
    max_positions: 5         # 동시 포지션 최대 5개
    risk_per_trade_pct: 1.0  # 거래당 자본의 1% 리스크
```

이렇게 설정하면 최대 손실이 5% (5개 x 1%)로 제한됩니다.

---

## 주식 전략 검증 현황 (Stock Strategy Validation Status)

> **Last verified 2026-06-20 (KST)** against `config/strategies/stock/*.yaml`.
> Live state lives in [PROJECT_STATUS.md](PROJECT_STATUS.md); the phased plan and
> open reactivation decisions live in [ROADMAP.md](ROADMAP.md). The 2026-03
> validation summary was synthetic-data-based and is archived
> ([archive/STOCK_STRATEGY_VALIDATION_SUMMARY.md](archive/STOCK_STRATEGY_VALIDATION_SUMMARY.md)).

### 활성 전략 (`enabled: true`)

운영 환경은 paper 전용입니다 (KIS real key로 시세 수집 + VirtualBroker 주문).
청산은 시그널 기반 three-stage이며 무조건적 EOD 청산은 없습니다.

| 전략 | 설정 파일 | 비고 |
|------|----------|------|
| momentum_breakout | `config/strategies/stock/momentum_breakout.yaml` | paper 관찰용 재활성화 (#443); 재튜닝 미해결 (최근 Sharpe -5.24). |
| pattern_pullback | `config/strategies/stock/pattern_pullback.yaml` | 활성 패턴 풀백 진입. |
| williams_r | `config/strategies/stock/williams_r.yaml` | 활성 (지표 기반 진입). |

### 비활성 전략 (`enabled: false`)

| 전략 | 설정 파일 | 사유 |
|------|----------|------|
| bb_reversion | `config/strategies/stock/bb_reversion.yaml` | 비활성. |
| opening_volume_surge (+ combo/score 변형) | `config/strategies/stock/opening_volume_surge*.yaml` | 비활성. |
| volume_accumulation | `config/strategies/stock/volume_accumulation.yaml` | 비활성. |
| trend_pullback | `config/strategies/stock/trend_pullback.yaml` | 비활성 — 재검증 대기. |
| vr_composite | `config/strategies/stock/vr_composite.yaml` | 비활성. |
| technical_consensus (+ exit 실험) | `config/strategies/stock/technical_consensus*.yaml` | 0% 승률(2026-06-02)로 비활성; 재활성화 결정 보류 ([ROADMAP.md](ROADMAP.md)). |
| trend_continuation_vwap | `config/strategies/stock/trend_continuation_vwap.yaml` | 비활성. |
| daily_pullback | `config/strategies/stock/daily_pullback.yaml` | 비활성. |
| trix_golden | `config/strategies/stock/trix_golden.yaml` | 비활성. |

**참고:** 비활성 전략 코드는 참고/실험용으로 유지되지만, 운영 환경에서는 사용되지 않습니다.
정확한 활성 여부는 항상 각 YAML의 `enabled` 플래그가 단일 진실원입니다.

---

## 관련 문서 (Related Documentation)

- [주식 전략 검증 요약 (archived, historical)](archive/STOCK_STRATEGY_VALIDATION_SUMMARY.md) - 2026-03 합성 데이터 백테스트 결과 (보관용)
- [백테스트 성능 리뷰](BACKTEST_PERFORMANCE_REVIEW.md) - 상세 백테스트 분석
- [페이퍼 트레이딩 모니터링 가이드](PAPER_TRADING_MONITORING_GUIDE.md) - 20일 검증 절차
