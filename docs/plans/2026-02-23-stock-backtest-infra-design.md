# Stock Backtest Infrastructure & Performance Analysis Design

**Date**: 2026-02-23
**Status**: Approved

## Problem Statement

bb_reversion 전략의 paper trading과 백테스트 성과가 모두 저조함. 원인 파악과 지속적인 백테스트를 위해 장기 분봉 데이터 수집/관리 인프라가 필요.

### Current State

- ClickHouse `market.minute_candles`: 33종목, 238K bars, 2025-12-23 ~ 2026-02-23 (약 2개월)
- `backfill_stock_minute()`에 `days = min(days, 30)` 하드캡
- 백테스트 CLI(`sts backtest run`)는 CSV 파일만 지원 (ClickHouse 직접 읽기 불가)
- KIS API `FHKST03010230`은 날짜 파라미터로 6개월+ 과거 분봉 조회 가능

## Design

### Section 1: 6개월 분봉 대량 수집 + ClickHouse 직접 백테스트

#### A. 데이터 수집 확장 (`shared/collector/historical/stock.py`)

1. **30일 하드캡 제거**: `days = min(days, 30)` → `days = min(days, 180)`
2. **Rate limit 안전 수집**:
   - 기존 10종목 동시 요청 (semaphore) 유지
   - 날짜별 배치 간 1초 sleep
   - 30종목 × 180일 = 5,400 API 호출, ~90분 예상
   - API 에러 시 exponential backoff 강화
3. **진행 상태 추적**: state file에 (code, date) 단위 기록 → 중단 후 이어서 수집
4. **CLI**:
   ```bash
   sts stock-backfill run --days 180
   sts stock-backfill run --days 180 --codes 005930,000660
   sts stock-backfill status  # 종목별 수집 현황
   ```

#### B. 백테스트 CLI ClickHouse 직접 읽기 (`cli/main.py`)

새 옵션 추가:
```bash
# 종목 지정 → ClickHouse에서 자동 로드
sts backtest run -s bb_reversion -a stock --symbol 005930

# 티어별 순회 (top/mid/bottom/all)
sts backtest run -s bb_reversion -a stock --tier all

# 날짜 범위 (선택)
sts backtest run -s bb_reversion -a stock --symbol 005930 \
  --start 2025-09-01 --end 2026-02-23
```

- `--symbol` 또는 `--tier` → ClickHouse `market.minute_candles` 쿼리
- `--data` CSV 옵션 기존 유지 (하위 호환)
- `--tier` 사용 시 → 종목별 결과 + tier별 집계 요약 테이블 출력

### Section 2: bb_reversion 성과 저하 원인 분석

별도 스크립트 없이 기존 인프라 활용:

**1단계: 현상 파악** (즉시 실행 가능)
```bash
sts backtest run -s bb_reversion -a stock --tier all
```
- 종목별 Sharpe, 승률, 거래 수 테이블
- 대형/중형/소형주 tier별 집계

**2단계: 시그널 진단**
- 진입 vs 청산 문제 분리
- market_state_filter 차단 비율 확인
- BB lower touch + RSI < 38 조건의 적절성

**3단계: 파라미터 민감도**
```bash
sts optimize -s bb_reversion -a stock --symbol 005930 --trials 50
```
- V35 파라미터가 현재 시장에 맞는지 확인
- 최적 파라미터 탐색

### Section 3: 매일 자동 수집 cron 강화

**기존 유지**: `stock_backfill.sh` (15:50) — 당일 분봉 수집

**추가**: 최초 1회 6개월 대량 백필 (수동 실행)
```bash
sts stock-backfill run --days 180  # ~90분
```

**데이터 무결성**: `sts stock-backfill status` 강화
- 종목별 수집 기간 (earliest ~ latest)
- 누락 거래일 탐지
- 총 데이터 행 수

## Files to Modify

| File | Change |
|------|--------|
| `shared/collector/historical/stock.py` | 30일 하드캡 제거, 상태 추적 강화 |
| `cli/main.py` | `--symbol`, `--tier` 옵션 추가, ClickHouse 로더 |
| `shared/backtest/engine.py` | (변경 없음 — DataFrame 입력은 동일) |

## Non-Goals

- 새 분석 스크립트 작성 (기존 백테스트 엔진 활용)
- 멀티 심볼 동시 시뮬레이션 (종목별 순회)
- 외부 데이터 소스 (KIS API만 사용)
- 종목 유니버스 확대 (현재 30종목 유지)
