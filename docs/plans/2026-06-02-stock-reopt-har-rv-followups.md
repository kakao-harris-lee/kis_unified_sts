# Phase 2 / Stock Verification FAIL — Follow-up Recommendations

- **작성일**: 2026-06-02
- **맥락**: 2026-06-02 Phase 2 Daily Verification + Stock Paper Verification 텔레그램 FAIL 조사.
- **상태**: 핵심 수정 5건 main 머지 완료. 본 문서는 남은 도메인 follow-up 권고안 (운영 결정 대기).

## 머지 완료 (main)

| PR | 내용 |
|----|------|
| #390 | chandelier 테스트 수정 (main `test` CI green 복구) |
| #389 | phase2 `har_rv` 게이트 `created_at` 기준 + orchestrator→`signals_all` 영속화(B2) |
| #391 | HAR-RV refit 계약 해상도 유동성 가드 (`HAVING bars>=30`, 5d 윈도우) |
| #392 | 0% 승률 주식 전략 3개 비활성 (technical_consensus / trend_continuation_vwap / momentum_breakout) |
| #393 | paper reconciliation: broker-absent break-even 청산 방지 + 실 P&L + 초기 stop 영속화 |

운영 조치: HAR-RV refit 재실행, A01606 06-01 분봉 백필(0→102).

## #2 — 전략 재튜닝 결과 (Optuna, 2026-06-02)

> 결과는 MLflow 서버(localhost:5000) 다운으로 stdout 로그에서 회수. 라이브 paper 재활성은 미적용(운영 결정).

| 전략 | 윈도우 | best Sharpe | win% | 수익 | equity | 권고 |
|------|--------|-------------|------|------|--------|------|
| **momentum_breakout** | 89d(분봉) | -5.24 | 32.3 | -0.75% | ↓ | **비활성 유지** — 재튜닝으로도 손실. 전략 로직/레짐 적합성 재설계 필요(strategy-architect), 단순 튜닝 불가 |
| **technical_consensus** | 1093d(일봉) | +6.53 | 55.6 | +14.8% | ↑ | **재활성 후보** — 아래 파라미터. 단 3년 백테스트 통과일 뿐 최근 3주 라이브는 손실 → **현 레짐 검증 후** 소액 재활성 권장 |
| **trend_continuation_vwap** | — | — | — | — | — | **미최적화** — `optimize_strategies.py` 미지원. generic 경로(sts optimize / param definer 추가)로 재튜닝 필요 |

**technical_consensus 재튜닝 best params** (현재 대비 진입필터 강화):
```
min_entry_core_votes=2, rsi_oversold=30, rsi_recovery=40,
williams_oversold=-75, williams_reversal=-65, min_volume_ratio=2.0,
signal_cooldown_days=1, stop_loss_pct=4.5, exit_hard_stop_pct=-0.05
```
재활성 시: 위 params 적용 + `enabled: true` + 소액/모니터링. **monthly_expected 0.284%**는 검증의 10% 목표에 크게 미달(목표 자체가 비현실적), win-rate·equity는 통과.

## #1 — HAR-RV refit OOS 실패 (forecasting)

**근본 원인**: OOS R² -3.189는 대부분 **메트릭 아티팩트** — `ss_tot`이 holdout 자체 분산(oracle mean)이라, train(고변동)→holdout(저변동 4× 차이) 레짐 시프트에서 음수 폭발. 모델은 train-mean 기준 R² **+0.586**으로 실제로는 유용. 추가로 garbage-tick RV 아웃라이어(03-04 ≈ 414% 연율) + `daily_rv_series` 야간세션 일경계 버그.

**권고 (검증 후 적용)**:
1. HAR-RV 타깃을 **log-RV**로 전환 (Corsi 표준, 분산안정화) + 로그정규 bias-corrected 역변환 → OOS R² -3.19→**-0.06**, holdout 무관하게 안정. `shared/forecasting/volatility_har_rv.py`.
2. `daily_rv_series` 야간세션 일경계 수정 (`realized_variance.py`).
3. **`min_r2_oos` 게이트 완화 금지** (나쁜 예측 수용).
- **블라스트 반경**: log-RV 역변환이 `forecast_pct`/`forecast_atr_equivalent`/`regime_percentile` 크기를 바꿔 Setup A/C 임계값 + RegimeGate에 영향 → **백테스트 + 1주 shadow 검증 후 cutover**. 미검증 ship 금지.
- 현 상태: 05-31 stale 모델로 forecast 발행 중 (합리적, 긴급 위험 없음). log-RV 적용 전까지 refit 매일 실패.

## #3 부수 — 추가 권고 (PR #393에서 일부만 처리)

- runtime-only stop 전략(bb_reversion/three_stage 등)은 signal에 절대 stop_loss price가 없어 여전히 `stop_loss_price=0` 영속 → 하드스톱 영속 원하면 signal이 절대가 emit해야 함.
- `high_since_entry` 청산가 proxy는 round-trip 포지션을 과대평가 → 정확히 하려면 open row에 `current_price` 스냅샷 컬럼 추가.
- `MOCK_MIRROR_ENABLED` 신뢰성: paper 회계가 VirtualBroker에 있는데 mock 미러가 KIS mock에 실주문→빈번 실패. 미러 필요성 재검토.

## 데이터/운영

- A01606 등 근월물 분봉 ingestion 안정성 (06-01 갭은 일회성, 백필 완료). refit이 ingestion 완료 후 돌도록 보장.
- MLflow 서버(localhost:5000) 다운 — 재튜닝 추적 유실. 재기동 필요.
