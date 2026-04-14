# Known Data Gaps

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
