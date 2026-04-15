# Known Data Gaps

## 2026-04-14 — 선물 RL 챔피언 모델 덮어쓰기 사고 (복원 완료)

- **영향 파일**: `models/futures/rl/mppo_best/best_model.zip`
- **사고 시각**: 2026-04-14 23:13 KST
- **원인**: `feat/hybrid-full-training-config` 브랜치의 실험적 hybrid 학습 run이 프로덕션 챔피언 경로를 덮어씀. 같은 종류의 사고는 2026-02-15 TFT 실험 중에도 발생한 적 있음 (MEMORY.md 참조).
- **탐지**: 2026-04-15, `scripts/analysis/rl_backtest_2026q1.py` 실행 중 MD5 불일치 감지 — 현재 `best_model.zip` (`a0db54f6...`) ≠ `mppo_best_5m_backup.zip` (`16e85532...`)
- **영향**: Task 1.3 rolling backtest에서 Sharpe/WR 수치가 신뢰할 수 없게 됨 → Task 1.3 최종 측정은 `mppo_best_5m_backup.zip`로 재수행
- **복구 (2026-04-15 18:35)**:
  1. 덮어씌워진 모델을 `models/futures/rl/mppo_best/best_model_overwritten_20260414_2313.zip`로 보존
  2. `cp models/futures/rl/mppo_best_5m_backup.zip models/futures/rl/mppo_best/best_model.zip`
  3. MD5 확인: `16e855323a5dd50e4ce6f28bf5042974` (Feb 챔피언 일치)
- **재발 방지 제안**:
  - ✅ **Implemented (2026-04-15):** `shared/ml/rl/model_paths.py::check_save_path` —
    `scripts/training/train_rl.py`는 `mppo_best/` 경로에 쓰려면 `--promote` 플래그 필수.
    실험은 `mppo_challenger/` 또는 `mppo_experiment_<tag>/` 사용.
  - `models/futures/rl/mppo_best/best_model.zip`에 파일 권한 `r--r--r--` 적용 후 의도적 promote 시에만 쓰기 권한 부여
  - PR 머지 시 모델 경로 변경 감지 hook (pre-commit) 추가

## 2026-03-11 ~ 2026-04-14 — 주식 모의투자 DB 누락

- **테이블**: `market.stock_trades` (신규 도입), 구 범주로는 `market.rl_trades`에 기록될 수 있었음
- **영향 기간**: 2026-03-11 ~ 2026-04-14 (약 1개월)
- **영향 건수**: `logs/stock_trading_*.log` 기준 74건 open / 74건 close
- **누락 원인**: `TradingOrchestrator._persist_closed_position` 필터가 `SWING_STRATEGIES ∪ rl_*` 로 설정되어 있어, 실제 활성 주식 전략인 `trend_pullback`, `momentum_breakout`이 필터에서 제외되어 DB에 적재되지 않음.
- **추가 문제 (Task 0 investigation 결과)**:
  - 이상 `profit_pct`(±수천%/±90%대) 샘플 다수. `profit_pct` 수식은 정확하지만 두 가지 근본 원인이 조합:
    1) Redis 캐시 이전 세션 가격 기반 진입 → 소형주가 당일 폭등/폭락
    2) 15:30 EOD 강제 청산 시점에 WebSocket이 이미 끊겼고 REST failover가 실패하여 `exit_price`가 stale 스냅샷 사용 (예: SK하이닉스 000660 exit=72,780 — 실제 거래된 적 없는 가격)
- **복구 정책**: **원본 로그 `profit_pct` 값 신뢰 불가**로 재적재 금지. 이 구간은 영구 데이터 공백으로 기록.
- **수정 PR**: `fix/paper-trading-db-integrity` (2026-04-14 생성)
- **후속 조치 제안**:
  - Entry price 품질 검증: Redis 캐시 TTL 단축, 또는 체결 직전 live price fetch 의무화
  - EOD 시점 데이터 검증: WebSocket staleness 감지 시 강제 청산 차단 (이번 PR Task 6로 해결)
