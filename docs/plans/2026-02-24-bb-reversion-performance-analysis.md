# bb_reversion 전략 성과 분석 및 개선 방향

**Date**: 2026-02-24
**Status**: Analysis Complete

## 1. 분석 배경

bb_reversion 전략의 paper trading 성과가 저조하여 원인 파악 및 개선 방향 도출을 위해 체계적 분석 수행.

### 분석 인프라 구축
- ClickHouse `market.minute_candles`: 30종목, ~3개월 분봉 데이터 (2025-11 ~ 2026-02)
- `sts backtest run --tier all`: 30종목 일괄 백테스트 CLI
- `scripts/optimize_bb_reversion.py`: Optuna TPE 기반 파라미터 최적화

### V35 레거시 정리
- bb_reversion 파라미터는 구 `quant_moment_sts` 프로젝트의 V35OptimizedStrategy에서 유래
- V35 Sharpe 2.62 (2019-2024)는 **인트라데이** 청산 조건으로 달성 (stop -1.5%, time_cut 20min, EOD 15:15)
- 현재는 **스윙** 청산 조건 (stop -3%, time_cut 없음, EOD 없음) → V35 성과와 직접 비교 불가
- YAML에서 V35 관련 주석 제거 완료

---

## 2. 현재 성과 (30종목, 2025-11 ~ 2026-02)

### Tier별 집계

| Tier | 종목 수 | 거래 수 | 평균 수익률 | 평균 승률 | 평균 Sharpe |
|------|---------|---------|-----------|---------|------------|
| Top (대형주) | 10 | 582 | -0.82% | 38% | **-1.58** |
| Mid (중형주) | 10 | 637 | -0.25% | 46% | **-0.33** |
| Bottom (소형주) | 10 | 663 | -0.84% | 44% | **-1.23** |
| **Overall** | **30** | **1,882** | **-0.63%** | **43%** | **-1.05** |

### 수익 종목 (Sharpe > 0): 9/30

| 종목 | Tier | 거래 수 | 수익률 | 승률 | Sharpe |
|------|------|---------|--------|------|--------|
| 삼성전기 | bottom | 65 | +1.33% | 57% | **2.53** |
| SK | mid | 74 | +0.78% | 53% | 1.32 |
| 기아 | top | 68 | +0.89% | 46% | 1.29 |
| 현대모비스 | mid | 64 | +0.53% | 52% | 1.21 |
| 삼성물산 | mid | 63 | +0.40% | 49% | 0.95 |
| 삼성생명 | mid | 65 | +0.10% | 52% | 0.46 |
| KT&G | bottom | 51 | -0.03% | 57% | 0.35 |
| 삼성전자 | top | 66 | -0.10% | 42% | 0.08 |
| 삼성SDI | mid | 69 | -0.09% | 41% | 0.07 |

### 최악 종목 (Sharpe < -2)

| 종목 | Tier | 거래 수 | 수익률 | 승률 | Sharpe |
|------|------|---------|--------|------|--------|
| NAVER | top | 58 | -1.83% | 41% | -4.71 |
| 카카오 | top | 62 | -2.05% | 34% | -4.14 |
| 신한지주 | mid | 62 | -1.56% | 37% | -3.27 |
| 엔씨소프트 | bottom | 67 | -1.84% | 34% | -2.89 |
| 알테오젠 | bottom | 73 | -2.06% | 34% | -2.90 |
| LG화학 | top | 68 | -1.59% | 43% | -2.50 |
| LG에너지솔루션 | bottom | 62 | -1.23% | 42% | -2.49 |

---

## 3. 파라미터 최적화 결과

### 실험 설정
- **도구**: Optuna TPE Sampler, 100 trials
- **대상**: 9종목 대표 (tier별 3종목)
- **목표**: 평균 Sharpe ratio 최대화

### 탐색 공간

| Parameter | Range | Best |
|-----------|-------|------|
| bb_period | 10-30 | 19 |
| bb_std | 1.5-3.0 | 2.3 |
| bb_touch_buffer | 1.00-1.03 | 1.01 |
| rsi_period | 7-21 | 16 |
| rsi_oversold | 25-45 | 41 |
| exit_stop_loss_pct | -5% ~ -1% | -4.5% |
| exit_breakeven_threshold_pct | 1% ~ 4% | 2% |
| exit_maximize_threshold_pct | 2% ~ 8% | 7% |
| exit_trailing_stop_pct | -5% ~ -1% | -2.5% |

### 파라미터 중요도

| Parameter | Importance | 설명 |
|-----------|------------|------|
| rsi_oversold | **35.6%** | 가장 중요. 38→41 완화 시 진입 기회 증가 |
| bb_touch_buffer | **31.3%** | 1.01 유지 최적 |
| exit_stop_loss_pct | **16.2%** | -3%→-4.5% 확대로 조기 손절 방지 |
| exit_breakeven_threshold_pct | 7.6% | 2% 유지 |
| exit_maximize_threshold_pct | 6.1% | 3%→7% 상향 |
| 나머지 | <2% | 미미한 영향 |

### 결과

| Metric | 현재 (9종목) | 최적화 (9종목) | 최적화 (30종목) |
|--------|-------------|---------------|----------------|
| Avg Sharpe | 0.05 | **0.33** | **-1.05** |

**결론: 9종목 subset에서 6.6x 개선 달성하나, 30종목 전체에 일반화 실패.**

---

## 4. 원인 분석

### 4.1 시장 구조 문제 (Primary)
- 2025-11 ~ 2026-02 구간은 약세/하락 추세장
- Mean Reversion 전략은 **횡보장(SIDEWAYS)**에서 가장 효과적
- BB 하단 터치 후 반등 없이 계속 하락하는 종목 다수 → 손절 연발

### 4.2 종목 특성 불일치
- **대형주 tech (NAVER, 카카오, LG화학)**: 강한 하락 추세 → Mean Reversion 최악
- **금융/가치주 (삼성생명, KB금융, KT&G)**: 상대적 안정 → Sharpe 양호
- **소형 고변동 (에코프로, 알테오젠)**: 변동성 과다 → 손절 반복

### 4.3 전략 구조 한계
1. **진입 조건 단순**: BB lower touch + RSI < threshold만으로는 추세 하락 vs 일시 조정 구분 불가
2. **market_state_filter 미작동**: 백테스트에서 MFI/ADX 데이터 없어 비활성화 → BEAR에서도 진입
3. **스윙 청산의 양면성**: 넓은 손절(-3%)은 수익 구간에서 유리하나, 하락장에서 손실 확대

### 4.4 파라미터 과적합
- 100 trials 최적화가 9종목 noise에 맞춰진 파라미터 도출
- 30종목으로 확장 시 성과 악화 → overfitting 확인

---

## 5. 개선 방향 (향후 작업)

### 5.1 시장 상태 필터 실전 적용 (High Priority)
**현재 문제**: `market_state_filter`가 config에 있지만 백테스트에서 MFI/ADX 없어 비활성화

**개선안**:
- ClickHouse 분봉에서 MFI/ADX 지표 사전 계산
- 백테스트에서도 market_state_filter 활성화
- BEAR/BEAR_STRONG 상태에서 진입 차단
- 예상 효과: 손실 거래 30-50% 감소

### 5.2 종목 필터 강화 (High Priority)
**현재 문제**: 30종목 일괄 적용, 전략에 맞지 않는 종목 포함

**개선안**:
- **Tier 필터**: Mid-cap 위주 운용 (Sharpe -0.33 vs Top -1.58)
- **변동성 필터**: 과도한 변동성(MDD > 2.5%) 종목 제외
- **추세 필터**: ADX > 25 (강한 추세) 종목은 Mean Reversion 부적합 → 제외
- **Screener 연동**: dip_candidates 중 추세 하락 종목 필터링

### 5.3 진입 조건 보강 (Medium Priority)
**현재 문제**: BB + RSI 이진 조건만으로 진입 판단

**개선안**:
- **MACD 확인**: MACD histogram 상승 전환 확인 (V35에 있었으나 현재 미사용)
- **거래량 확인**: 하단 터치 시 거래량 급증 → 반전 신호
- **캔들 패턴**: 하단 터치 후 양봉 확인 (1-bar delay)
- **복수 시간프레임**: 5분봉 BB + 1분봉 RSI 조합

### 5.4 청산 전략 개선 (Medium Priority)
**현재 문제**: 3-Stage Exit의 고정 임계값

**개선안**:
- **ATR 기반 동적 손절**: 고정 -3% 대신 ATR × 2 사용
- **시간 기반 손절**: N일 경과 후 수익 없으면 청산 (스윙이라도 무한 보유 방지)
- **부분 청산**: BREAKEVEN 단계에서 50% 익절, 나머지 MAXIMIZE

### 5.5 데이터 확장 (Low Priority, 장기)
**현재 제약**: 3개월 데이터만 보유 → 다양한 시장 구간 검증 불가

**개선안**:
- 6개월+ 백필 완료 (이미 CLI 준비됨: `sts stock-backfill run --days 180`)
- 상승장/횡보장/하락장 각 구간별 성과 분리 분석
- Walk-forward 검증으로 과적합 방지

### 5.6 전략 앙상블 (Low Priority, 장기)
- bb_reversion + opening_volume_surge + volume_accumulation 조합
- 시장 상태별 전략 가중치 동적 조절
- 포트폴리오 레벨 리스크 관리

---

## 6. 인프라 변경 사항 (이번 세션에서 구현)

| 파일 | 변경 | 상태 |
|------|------|------|
| `shared/collector/historical/stock.py` | 30일 하드캡→180일, resume 상태 추적, CH 로더 | Uncommitted |
| `cli/main.py` | `--symbol`, `--tier` 옵션, `_run_tier_backtest()` | Uncommitted |
| `scripts/optimize_bb_reversion.py` | Optuna TPE 최적화 스크립트 (신규) | Uncommitted |
| `config/strategies/stock/bb_reversion.yaml` | V35 주석 제거, 백테스트 결과 갱신 | Uncommitted |

---

## 7. 관련 파일

- 최적화 스크립트: `scripts/optimize_bb_reversion.py`
- 전략 설정: `config/strategies/stock/bb_reversion.yaml`
- 백테스트 엔진: `shared/backtest/engine.py`
- 어댑터: `shared/backtest/adapter.py`
- 진입 전략: `shared/strategy/entry/mean_reversion.py`
- 청산 전략: `shared/strategy/exit/three_stage.py`
- 데이터 수집: `shared/collector/historical/stock.py`
- CLI: `cli/main.py`
