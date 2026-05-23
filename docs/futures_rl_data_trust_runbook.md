# Futures RL Data Trust Runbook

KOSPI 200 선물 RL 학습/백테스트에서 데이터 신뢰 구간을 관리하기 위한 운영 문서.

## 1) 현재 운영 결정 (2026-02-27)

- `mppo_final`(clean retrain candidate)은 **비활성(disable)**.
- 실험/운영 기준 모델은 `mppo_best` 유지.
- 이유:
  - 동일 클린 구간 백테스트에서 `mppo_best`는 양호 성능.
  - 동일 구간에서 `mppo_final`은 성능 열화가 확인됨.

주의: `mppo_best`가 과거 오염 가능성이 있는 기간을 포함해 학습되었더라도,
현재 **클린 검증 구간에서의 실측 성능**이 더 우수하므로 baseline으로 유지한다.

## 2) RL 데이터 정책

- 학습/평가 데이터 고정:
  - table: `kospi.kospi200f_1m`
  - symbol: `101S6000`
- 실거래(종목)는 mini front-month(`A05xxx`)를 사용하되,
  RL 학습/백테스트 데이터는 `101S6000` 기준을 유지한다.

## 3) 신뢰 구간(Trusted Window) 정의

하루(거래일)를 신뢰 대상으로 인정하려면 아래 조건을 모두 만족해야 한다.

1. `datetime` 중복 0건
2. `datetime` 단조 증가
3. 비정상 초단위 바(`toSecond(datetime) != 0`) 0건
4. `volume == 0` 이면서 가격 변동이 있는 phantom bar 비율 0%
5. 일별 바 수가 최소 기준(`min_bars_per_day`, 기본 300) 이상

연속된 신뢰 거래일만 백테스트/학습의 신뢰 구간으로 사용한다.

## 4) 현재 신뢰 구간 (잠정)

- 잠정 신뢰 구간: `2026-02-09` ~ `2026-02-26`
- 근거:
  - 오염 구간 삭제 후 재검증 PASS
  - archive/ClickHouse 무결성 점검 통과

이 구간은 고정값이 아니라, 백필/재검증 결과에 따라 확장 또는 축소한다.

## 5) 재학습 전 필수 게이트 (Go/No-Go)

아래를 모두 통과할 때만 재학습을 수행한다.

1. 데이터 무결성 점검 PASS
2. 신뢰 구간 산출 및 문서 업데이트 완료
3. baseline(`mppo_best`) 고정 백테스트 결과 저장
4. candidate 모델이 동일 구간에서 baseline 대비 열화가 없음을 확인

권장 명령:

```bash
# 1) 데이터 품질 점검
.venv/bin/python scripts/analysis/audit_rl_futures_data.py \
  --clickhouse --database kospi --table kospi200f_1m --symbol 101S6000

# 2) 백필 무결성 점검(예시 날짜)
.venv/bin/python scripts/analysis/check_futures_backfill_integrity.py \
  --date 2026-02-26

# 3) baseline 백테스트 (항상 동일 조건 유지)
FUTURES_CANDLE_TABLE=kospi200f_1m .venv/bin/sts backtest run \
  -s rl_mppo -a futures --symbol 101S6000 \
  --start 2026-02-09 --end 2026-02-26 --no-track
```

## 6) 모델 교체 기준 (Promotion)

candidate를 `mppo_best`로 교체하려면 최소 조건:

1. 동일 신뢰 구간 백테스트에서 총수익률/Sharpe가 baseline 이상
2. 거래 수 급증(과매매) 없이 MDD 악화 없음
3. 최소 2개 이상 추가 구간(walk-forward)에서도 재현

하나라도 미충족 시 baseline 유지.

## 7) 운영 체크리스트

- [ ] `RL_MPPO_MODEL_PATH`가 의도한 모델을 가리키는지 확인
- [ ] `config/ml/rl_*.yaml`의 `data.start_date/end_date` 적용 여부 확인
- [ ] `sts backtest run`이 futures 로더 경로를 타는지 확인
- [ ] 백테스트 결과와 평가 결과의 기간/조건이 동일한지 확인

## 8) 상승장 Paper 파라미터 매트릭스 (Pre-clean 프로파일 비교)

데이터 정리 이전에 쓰던 파라미터군(`rl_mppo`, `rl_mppo_tune_*`, `rl_mppo_profile_*`)을
동일 모델(`mppo_best`)에서 paper로 회전 실행해, 장중 체결 가능성과 손익을 함께 비교한다.

### 8.1 전일/장전 후보 생성 (캐시 리플레이)

```bash
.venv/bin/python scripts/analysis/tune_rl_preopen.py \
  --asset futures \
  --mode long_bias \
  --evaluation-mode paper \
  --tune-target paper \
  --write-profiles \
  --profile-prefix rl_mppo_tune
```

- `evaluation-mode paper`: paper threshold 경로(`paper_*`) 기준으로 리플레이 평가
- `tune-target paper`: `paper_hold_override_*` 필드에 직접 반영

### 8.2 장중 프로파일 라운드로빈 실행/집계

```bash
.venv/bin/python scripts/analysis/rl_paper_profile_matrix.py \
  --profiles rl_mppo,rl_mppo_profile_asym_long_strict,rl_mppo_profile_uptrend_spike_guard,rl_mppo_tune_a,rl_mppo_tune_b \
  --duration-minutes 30 \
  --model mppo_best
```

- 출력: `output/paper_matrix/<timestamp>/`
  - 개별 로그: `<nn>_<profile>.log`
  - 요약: `paper_profile_matrix_summary_*.csv/json`
- 핵심 비교 지표:
  - `entry_fill_rate` (진입 실행률)
  - `blocks_wide_spread`, `blocks_insufficient_depth` (차단 원인)
  - `win_rate`, `total_pnl_pct`, `avg_slippage_ticks_abs`
  - `uptrend_score` (상승장 우선 가중 점수)

### 8.3 Cron 연동 (월요일 장 시작 자동 실행)

`scripts/cron/rl_paper.sh start`가 기본적으로 matrix 모드를 실행한다.

- 기본 프로파일:
  - `rl_mppo,rl_mppo_profile_asym_long_strict,rl_mppo_profile_uptrend_spike_guard,rl_mppo_tune_a,rl_mppo_tune_b`
- 세션 출력 디렉토리:
  - `output/paper_matrix/YYYYMMDD_session/`
- `stop` 시점(장 종료 후) 자동 동작:
  - 세션 로그를 재집계해 `paper_profile_matrix_summary_*.csv/json` 생성

환경변수 오버라이드:

- `RL_PAPER_MATRIX_ENABLED` (기본 `1`)
- `RL_PAPER_MATRIX_MODEL` (기본 `mppo_best`)
- `RL_PAPER_MATRIX_PROFILES` (콤마 구분 프로파일 목록)
- `RL_PAPER_MATRIX_DURATION_MINUTES` (프로파일별 분할 실행 시간, 미지정 시 장 종료 시각 기준 자동 계산)
- `RL_PAPER_MATRIX_COOLDOWN_SECONDS` (프로파일 사이 휴지시간, 기본 `8`)

### 8.4 장중 모니터링

레거시 대시보드는 제거되었으며, 장중 확인은 React Dashboard와
Prometheus/ClickHouse 쿼리로 수행한다.

핵심 확인 항목:

- Entry/Rejected 신호 수
- Signal Acceptance Rate
- Strategy별 signal flow
- Entry Blocks by Reason (`trading_entry_blocks_total`)
- RL action probability(long/short/hold)

참고:

- `trading_signals_total{type=\"rejected\"}`는 실행 가드 차단 시 증가한다.
- 차단 사유는 `trading_entry_blocks_total{reason=...}`로 분해되어 확인 가능하다.
