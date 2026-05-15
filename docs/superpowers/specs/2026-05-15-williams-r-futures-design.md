# Williams %R 선물 변형 — Design

**Date**: 2026-05-15
**Author**: 운영 결정 (RL_mppo deprecate v4.10 후속)
**Status**: Design → 구현 (enabled=false로 시작, 백테스트 검증 후 활성화)

## 배경

RL_mppo deprecate (master plan v4.10, 2026-05-15) 이후 선물 시그널 layer를
명시적 기술 지표 기반으로 재구성한다. 첫 번째 변형은 **Williams %R** —
주식에 이미 등록된 `williams_r` entry/exit 컴포넌트를 선물 양방향으로 확장한다.

기존 자산:
- `shared/strategy/entry/williams_r.py` — `WilliamsREntry` (레지스트리 등록 완료)
- `shared/strategy/exit/williams_r_exit.py` — `WilliamsRExit` (레지스트리 등록 완료)
- `config/strategies/stock/williams_r.yaml` — stock, `enabled: false`

## 기존 코드의 stock-only 제약

### Entry (`williams_r.py`)
1. `generate()`는 **LONG 시그널만 생성** — 과매도 반전(`prev_wr < oversold`
   AND `current_wr >= reversal`) → `signal_direction: "long"`.
2. `allow_short: bool = False` config 필드는 **존재하지만 generate()에서
   미사용** (dead config).
3. 시간 필터 default: `market_close_hour: 15, market_close_minute: 15`
   (주식 EOD 15:15). 선물은 15:45.

### Exit (`williams_r_exit.py`)
1. P&L 계산(`_calc_profit_pct/_amount`, `_get_extreme_since_entry`)은
   **이미 SHORT 지원** — `PositionSide.SHORT` 분기 있음.
2. 그러나 indicator exit(#4)은 **LONG 전용** — `williams_r >=
   overbought_threshold`만 검사. SHORT 포지션은 hard-stop/EOD/time-cut으로만
   청산되고 지표 기반 청산이 안 됨 (비대칭).
3. 시간 필터 default: `eod_close_hour: 15, eod_close_minute: 15` (주식).

## 설계 결정

### 1. 후방 호환 — 주식 동작 불변
주식 `williams_r.yaml`은 `allow_short: false`. 모든 변경은 `allow_short`
게이팅 또는 SHORT 포지션 한정 분기로, `allow_short=false` 경로의 동작을
바꾸지 않는다.

### 2. Entry — 양방향 추가 (`allow_short=True`일 때만)
대칭 로직 추가:
- **LONG** (기존): `prev_wr < oversold_threshold` AND
  `current_wr >= reversal_threshold` → `signal_direction: "long"`
- **SHORT** (신규, `allow_short=True`): `prev_wr > overbought_threshold`
  AND `current_wr <= overbought_reversal_threshold` →
  `signal_direction: "short"`

신규 config 필드:
- `overbought_threshold: float = -20.0` (과매수 진입선)
- `overbought_reversal_threshold: float = -20.0` (반전 확인선)

confidence는 LONG의 `_calculate_confidence`를 대칭화 (reversal depth는
`abs(prev_wr - overbought_threshold)`, trend score는 `close < bb_middle`
거리). trend_filter도 SHORT일 때 `close < bb_middle`로 반전.

### 3. Exit — SHORT 포지션 indicator exit 대칭화
`_check_position()` #4를 포지션 방향에 따라 분기:
- **LONG 포지션**: `williams_r >= overbought_threshold` → exit (기존)
- **SHORT 포지션**: `williams_r <= oversold_exit_threshold` → exit (신규)

신규 config 필드:
- `oversold_exit_threshold: float = -80.0` (SHORT 청산용 과매도선)

hard-stop/EOD/time-cut은 방향 무관 (이미 SHORT P&L 지원).

### 4. 선물 config 신규 작성
`config/strategies/futures/williams_r_15m.yaml`:
- `asset_class: futures`
- `enabled: false` — **백테스트(101S6000) + Optuna 검증 전까지 비활성**
- `allow_short: true`
- entry/exit 시간 필터: `market_close_hour: 15, market_close_minute: 45`,
  `eod_close_hour: 15, eod_close_minute: 45` (선물 EOD)
- position sizer: `fixed` (계약 단위는 execution.yaml::futures_contract_spec)

## 비목표 (이번 PR 범위 밖)

- 백테스트 실행 / Optuna 파라미터 최적화 → 별도 후속 (운영자 + backtest-engineer)
- 선물 production 활성화 (`enabled: true`) → 백테스트 Sharpe 검증 후 별도 PR
- 다른 지표 전략(RSI/MACD) 선물 변형 → 별도 design + PR

## 검증 계획

- 단위 테스트: LONG 진입(기존 회귀), SHORT 진입(신규, `allow_short=true`),
  `allow_short=false`일 때 SHORT 미생성(후방호환), SHORT 포지션 oversold exit,
  LONG 포지션 overbought exit(기존 회귀), 선물 EOD 15:45.
- `StrategyFactory.create_from_file("futures", "williams_r_15m")` 로딩 확인.
- 기존 stock williams_r 테스트 회귀 없음.
