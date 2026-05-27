# Futures Trend-Following Attempt — 2026-05-27

## Motivation

최근 4개월 KOSPI200 선물 일간 변동 +25.5% / -15.3% / +25.9% / +25.1% (누적 +68%)의
**명백한 상승장**. 현 paper 운용 (`bb_reversion_15m`, `setup_a_gap_reversion`,
`setup_c_event_reaction`)은 모두 mean-reversion 계열 → 상승장에서 추세를 잡는
**추세 추종 옵션 추가**를 시도했다.

## Attempts Summary

**중요**: 초기 실험은 점수 잘못된 `point_value=10000` 으로 수행하여 절대 수치(return%, MDD%)가
5x 축소 보고되었다. 정확한 mini multiplier `point_value=50000`로 4개 최종 시나리오를 재실행한
결과를 아래에 함께 기록한다. dim-ratios(Sharpe, PF, WR)는 point_value scaling에 불변이므로
초기 보고치와 동일하다.

| Attempt | Setup | Trades | WR | PF | Sharpe | Return | MDD | Verdict |
|---------|-------|-------:|---:|---:|-------:|-------:|----:|---------|
| 1 | MACD/EMA 15m default (10K) | 230 | 21.3% | 0.52 | -4.65 | -77.3% | 78.7% | ❌ |
| 2 | MACD/EMA 15m + 4h time_cut (10K) | 200 | 24.0% | 0.57 | -4.00 | -70.0% | 72.9% | ❌ |
| 3 | MACD/EMA 15m + vol_confirm + SL -3% (10K) | 61 | 24.6% | 0.48 | -4.13 | -22.6% | 22.6% | ❌ |
| 4 | MACD/EMA **60m** (10K) | 65 | 32.3% | 0.81 | -1.28 | -11.9% | 26.3% | △ |
| **4'** | **MACD/EMA 60m (50K, correct mini)** | **65** | **32.3%** | **0.81** | **-1.28** | **-59.5%** | **84.0%** | ❌ |
| 5 | Optuna 25 trials on (4) | — | — | — | -1.006 (best) | — | — | ❌ stopped |
| 6 | `trend_pullback` (stock port) | **0** | — | — | — | — | — | ❌ stock deps |
| 7 | `momentum_breakout` (10K) | 36 | 13.9% | 0.01 | -11.0 | -47.8% | 47.9% | ❌ |
| **7'** | **`momentum_breakout` (50K)** | **36** | **13.9%** | **0.01** | **-11.0** | **-238.9%** | **239.3%** | ❌ 파산 |
| 8 | `trix_golden` (10K) | 68 | 41.2% | 0.51 | -3.31 | -19.0% | 27.4% | ❌ |
| **8'** | **`trix_golden` (50K)** | **68** | **41.2%** | **0.51** | **-3.31** | **-95.0%** | **115.7%** | ❌ |

> Bold rows are the corrected baseline with proper `point_value=50000` (KOSPI200 mini per
> `config/execution.yaml::futures_contract_spec`). Use these as the canonical record.

## Key Findings

### 1. KOSPI200 선물 인트라데이는 mean-reverting

상승장의 일간 +25% 변동에도 불구하고, **1분봉 / 15분봉 / 60분봉 모두에서 추세 추종 진입이
PF < 1**. 4개 알고리즘 × 8가지 변형 모두 음수 Sharpe. 정확한 mini multiplier(50K)로 재실행 시
모든 전략이 자본의 60%+ 손실, momentum_breakout는 자본 초과 손실(파산).

원인 추정:
- 시장 마이크로구조: 매일 09:00 KST 개장 → 15:45 KST 마감의 짧은 세션
- 일간 추세가 인트라데이 다수 진동으로 형성됨 → 진입 시점의 false signal 많음
- EOD 강제 청산이 추세 발달을 차단 (trix_golden: EOD 청산 87%)

### 2. Stock 검증 알고리즘은 futures backtest에서 직접 동작 안 함

`trend_pullback`(Stock Sharpe 3.88)과 `momentum_breakout`(Stock Sharpe 3.12)이 검증된
strategy임에도 futures에서 fail:
- **`sma_200`** indicator가 IndicatorEngine에서 계산되지 않음
- **`daily_watchlist`**, **`accumulation_score`** 등이 stock screener output에 의존
- 위 dependency가 충족 안 되면 entry가 silently skip (0 trades)

### 3. 발견된 코드 버그 (수정 완료)

`Timeframe.to_token()`은 `60 % 60 == 0` → `"1h"`로 변환하는데,
`MACDEMACrossoverEntry`가 `momentum_60m` 키로 조회 → 매번 `None` →
60m timeframe에서 0 trades. 수정 후 PF 0.81로 회복.

→ `_timeframe_token` helper로 token 변환 일관성 확보.
   향후 다른 N×60m timeframe 사용 entry도 동일 헬퍼 패턴 권장.

### 4. Optuna 12-dim joint sweep도 음수 Sharpe만 도출

진입 6 params + exit 6 params을 동시 최적화 (Sharpe metric, min_trades=50)했지만
25 trial 모두 음수. 12차원 search space에 양수 Sharpe region이 존재하지 않을 가능성.

## Decision

**Branch `feat/futures-macd-ema-trend-follow`의 코드/yaml은 default disabled로 main 머지.**

이유:
- `MACDEMACrossoverEntry` 코드와 registry 등록은 향후 **daily timeframe 시도** 시 재활용 가능
- 4개 futures yaml은 future-self가 같은 시도를 반복하지 않도록 **명시적 실패 기록 헤더** 포함
- 본 보고서가 미래의 의사결정 기록으로 남음

## What Would Likely Work Next

추세 추종이 정말 필요하다면:

1. **Daily-bar 추세 추종**: 인트라데이가 mean-reverting이라도 **일봉**은 추세 잘 잡힘.
   - 현 인프라는 1분봉 기반 → daily backtest 인프라 추가 필요 (~중간 작업)
2. **계층적 RL 부활**: deprecated 된 `rl_mppo` 자리에 LLM macro context → low-level execution
   - High-level (15분/일봉): 방향성 결정
   - Low-level (1분봉): 풀백 진입 타이밍
3. **선물이 아닌 KRX 주식**: stock에서는 추세 추종이 잘 동작 (검증된 PF 3-4)
   - `setup_a_gap_reversion` 같이 futures에 paper 운용하되, **주식 paper에 trend_pullback / momentum_breakout 추가**가 더 효율적

## Files in This PR

| File | Action | Notes |
|------|--------|-------|
| `shared/strategy/entry/macd_ema_crossover.py` | NEW | `MACDEMACrossoverEntry` 클래스 + timeframe token bug fix |
| `shared/strategy/registry.py` | MODIFIED | `macd_ema_crossover` 등록 |
| `config/strategies/futures/macd_ema_crossover_15m.yaml` | NEW | 60m timeframe (이름은 15m 유지 — branch명 일관성) |
| `config/strategies/futures/trend_pullback.yaml` | NEW | Stock-port, 0 trades 결과 명시 |
| `config/strategies/futures/momentum_breakout.yaml` | NEW | Stock-port, PF 0.01 결과 명시 |
| `config/strategies/futures/trix_golden.yaml` | NEW | Stock-port, PF 0.51 결과 명시 |
| `reports/trend_following_attempt_2026-05-27.md` | NEW | 이 문서 |
