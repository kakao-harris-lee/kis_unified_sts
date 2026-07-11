# VectorbtRunner Parity Report (P3-b/P3-c / WS-A4 gate evidence)

- 생성: 2026-07-11 19:36 KST, `scripts/vbt_parity_report.py`
- vectorbt 1.0.0 / legacy `shared/backtest/engine.py` BacktestEngine
- Plan: `docs/plans/2026-07-08-new-architecture-refactoring-plan.md` §5, `docs/plans/2026-07-05-indicator-engine-and-stream-schema-roadmap.md` §WS-A4
- 러너: `shared/backtest/vbt_runner.py` (opt-in `strategy.backtest.engine: vectorbt`; 기본값 legacy)
- 시나리오·전략·완화설정은 머지 게이트 테스트 모듈에서 직접 import — 리포트와 게이트가 항상 같은 매트릭스를 돌린다.
- CI: 게이트 잡(`test`)은 vectorbt 미설치라 vectorbt-의존 parity 케이스를 skip 하고 마스킹/게이트/seam 계층만 강제한다. parity 스위트 전체는 advisory `backtest-extra` 레인과 이 스크립트(배포 호스트)에서 돈다 — **운영자 flip 전 재실행 필수** (exit code 가 실데이터 포함 전 셀 판정).

## 허용오차 정책

| 항목 | 정책 |
|---|---|
| 트레이드 시퀀스 (시각/가격/수량/pnl/사유) | **완전 일치** (`to_dict()` 동등) |
| final capital / Sharpe / Sortino / exit_reasons | **bit-동일** (resolver 가 legacy 연산 순서 유지) |
| 자산곡선 / MDD | vectorbt cash·assets 시프트 재구성 — 부동소수 결합순서 ulp 잔차만 허용 (합성 `atol=1e-6` KRW / 실데이터 1e8 자본 스케일 `atol=1e-4` KRW; 이번 실행 관측치: 합성 ≤1.5e-08, 실데이터 ≤0.0e+00) |
| `result.to_dict()` (라운딩 후) | **완전 일치** |

초과 드리프트는 `tests/unit/backtest/test_vbt_runner.py` parity 스위트가 실패시킨다 (머지 게이트).

## 합성 시나리오 × 리스크 매트릭스 (P3-b, 합성 진입+청산 전략)

| 케이스 | trades | trade seq | Δreturn(%p) | ΔSharpe | ΔMDD(%p) | Δfinal(KRW) | equity maxΔ(KRW) | reasons | to_dict |
|---|---|---|---|---|---|---|---|---|---|
| trend_up × default | 8 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| trend_up × tight_sl_tp | 10 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.86e-14 | 0.00e+00 | 3.73e-09 | ✅ | ✅ |
| trend_up × trailing | 8 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| trend_up × max_hold_bars | 8 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| trend_up × force_close_time | 8 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| trend_up × max_daily_trades | 4 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| trend_up × close_on_day_change | 8 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 1.86e-09 | ✅ | ✅ |
| trend_down × default | 18 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.87e-14 | 0.00e+00 | 3.73e-09 | ✅ | ✅ |
| trend_down × tight_sl_tp | 89 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.11e-13 | 0.00e+00 | 1.30e-08 | ✅ | ✅ |
| trend_down × trailing | 19 | ✅ exact | 0.00e+00 | 0.00e+00 | 3.77e-14 | 0.00e+00 | 3.73e-09 | ✅ | ✅ |
| trend_down × max_hold_bars | 45 | ✅ exact | 0.00e+00 | 0.00e+00 | 5.55e-14 | 0.00e+00 | 7.45e-09 | ✅ | ✅ |
| trend_down × force_close_time | 88 | ✅ exact | 0.00e+00 | 0.00e+00 | 9.33e-14 | 0.00e+00 | 1.49e-08 | ✅ | ✅ |
| trend_down × max_daily_trades | 4 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| trend_down × close_on_day_change | 19 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 3.73e-09 | ✅ | ✅ |
| chop × default | 11 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| chop × tight_sl_tp | 63 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.49e-13 | 0.00e+00 | 1.49e-08 | ✅ | ✅ |
| chop × trailing | 11 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| chop × max_hold_bars | 21 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.89e-14 | 0.00e+00 | 1.86e-09 | ✅ | ✅ |
| chop × force_close_time | 43 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 3.73e-09 | ✅ | ✅ |
| chop × max_daily_trades | 3 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| chop × close_on_day_change | 12 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| gap_days × default | 15 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| gap_days × tight_sl_tp | 28 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.87e-14 | 0.00e+00 | 3.73e-09 | ✅ | ✅ |
| gap_days × trailing | 15 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| gap_days × max_hold_bars | 23 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| gap_days × force_close_time | 25 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| gap_days × max_daily_trades | 4 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| gap_days × close_on_day_change | 15 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 1.86e-09 | ✅ | ✅ |
| random_walk × default | 14 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| random_walk × tight_sl_tp | 39 | ✅ exact | 0.00e+00 | 0.00e+00 | 3.73e-14 | 0.00e+00 | 7.45e-09 | ✅ | ✅ |
| random_walk × trailing | 14 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| random_walk × max_hold_bars | 27 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| random_walk × force_close_time | 30 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 1.86e-09 | ✅ | ✅ |
| random_walk × max_daily_trades | 4 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | ✅ | ✅ |
| random_walk × close_on_day_change | 14 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 1.86e-09 | ✅ | ✅ |
| same_bar_reentry × default | 15 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.87e-14 | 0.00e+00 | 1.86e-09 | ✅ | ✅ |

## 실 exit 생성기 매트릭스 (P3-c 허용목록 증거)

실제 exit 클래스 인스턴스(ATRDynamicExit / ChandelierExit — `atr_dynamic_decay` 는 배포 momentum_breakout 의 exit 설정 그대로)를 TestRealExitParity 와 동일한 픽스처로 이중 구동. 트레이드 시퀀스는 가격 포함 **완전 일치** 기준이다(러너가 트레이드 가격을 resolver 이벤트의 bar 종가 원본에서 채움).

| 케이스 | trades | trade seq | Δreturn(%p) | ΔSharpe | ΔMDD(%p) | Δfinal(KRW) | equity maxΔ(KRW) | reasons | to_dict |
|---|---|---|---|---|---|---|---|---|---|
| atr_dynamic × trend_up × default | 7 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.83e-14 | 0.00e+00 | 3.73e-09 | ✅ | ✅ |
| atr_dynamic × trend_up × tight_sl_tp | 17 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.86e-14 | 0.00e+00 | 1.86e-09 | ✅ | ✅ |
| atr_dynamic × trend_down × default | 33 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.87e-14 | 0.00e+00 | 3.73e-09 | ✅ | ✅ |
| atr_dynamic × trend_down × tight_sl_tp | 101 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 7.45e-09 | ✅ | ✅ |
| atr_dynamic × chop × default | 21 | ✅ exact | 0.00e+00 | 0.00e+00 | 3.72e-14 | 0.00e+00 | 3.73e-09 | ✅ | ✅ |
| atr_dynamic × chop × tight_sl_tp | 64 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.12e-13 | 0.00e+00 | 1.30e-08 | ✅ | ✅ |
| atr_dynamic_decay × trend_up × default | 15 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.84e-14 | 0.00e+00 | 3.73e-09 | ✅ | ✅ |
| atr_dynamic_decay × trend_up × tight_sl_tp | 18 | ✅ exact | 0.00e+00 | 0.00e+00 | 3.72e-14 | 0.00e+00 | 5.59e-09 | ✅ | ✅ |
| atr_dynamic_decay × trend_down × default | 74 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.49e-13 | 0.00e+00 | 1.49e-08 | ✅ | ✅ |
| atr_dynamic_decay × trend_down × tight_sl_tp | 109 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 7.45e-09 | ✅ | ✅ |
| atr_dynamic_decay × chop × default | 40 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.84e-14 | 0.00e+00 | 5.59e-09 | ✅ | ✅ |
| atr_dynamic_decay × chop × tight_sl_tp | 64 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.12e-13 | 0.00e+00 | 1.30e-08 | ✅ | ✅ |
| chandelier_exit × trend_up × default | 6 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.83e-14 | 0.00e+00 | 3.73e-09 | ✅ | ✅ |
| chandelier_exit × trend_up × tight_sl_tp | 17 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.86e-14 | 0.00e+00 | 1.86e-09 | ✅ | ✅ |
| chandelier_exit × trend_down × default | 29 | ✅ exact | 0.00e+00 | 0.00e+00 | 3.77e-14 | 0.00e+00 | 7.45e-09 | ✅ | ✅ |
| chandelier_exit × trend_down × tight_sl_tp | 101 | ✅ exact | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 7.45e-09 | ✅ | ✅ |
| chandelier_exit × chop × default | 13 | ✅ exact | 0.00e+00 | 0.00e+00 | 3.72e-14 | 0.00e+00 | 3.73e-09 | ✅ | ✅ |
| chandelier_exit × chop × tight_sl_tp | 64 | ✅ exact | 0.00e+00 | 0.00e+00 | 1.12e-13 | 0.00e+00 | 1.30e-08 | ✅ | ✅ |

## 선물 harness 매트릭스 (P3-d — resolver 원장 ↔ from_orders 원장)

`shared/backtest/vbt_harness_runner.py::VbtHarnessRunner` 는 선물 harness의 **컴포지션 래퍼**다 — `BacktestDecisionHarness` 가 여전히 SoT(결과 무변형 반환)이고, 이 섹션은 그 harness 트레이드 레코드로 세운 `vbt.Portfolio.from_orders` 원장이 harness 의 tick 회계를 재현하는지를 검증한다. **주의**: 위 주식 섹션과 달리 이것은 legacy-vs-vbt 두 독립 엔진 비교가 아니라 **harness resolver 원장 ↔ from_orders 원장 구성** 대조다(harness 가 유일 엔진). 멀티바 트레이드(`exit_bar > fill_bar`)만 컬럼당 1개로 `from_orders` 에 태우고, 같은-bar 트레이드(`==`, EOD-on-fill/last-bar)는 표현 불가라 종가 일치 확인 + tick P&L 을 fill/exit 가격에서 **해석적으로 재계산**해 검증한다(헤드라인 tick 합은 same-bar 에 대해 대수적으로 공허하므로 이 재계산이 실제 tick 회계 검증이다). 픽스처는 게이트 `tests/unit/backtest/test_vbt_harness_runner.py` 를 그대로 import.

| 케이스 | trades | multibar | samebar | parity |
|---|---|---|---|---|
| symmetric_mix | 8 | 7 | 1 | ✅ |
| long_only | 3 | 3 | 0 | ✅ |
| short_only | 2 | 2 | 0 | ✅ |
| sizer_scaled | 1 | 1 | 0 | ✅ |
| zero_signal | 0 | 0 | 0 | ✅ |
| gap_past_stop | 0 | 0 | 0 | ✅ |
| no_next_bar | 0 | 0 | 0 | ✅ |

## 실데이터 — williams_r (활성 주식 전략, 레지스트리 경로)

- 데이터: `005930` 실 분봉 parquet 3397 bars, 2026-06-01 ~ 2026-06-12 (KST)
- 경로: `StrategyFactory` → `BacktestStrategyAdapter` → 양 엔진 (fresh adapter 각각)
- 엔트리 게이트 완화: `market_state_filter/trend_filter/volume_confirm` off, cooldown 1800s — 해당 필터는 이 윈도우에서 신호를 전부 차단(backtest 경로는 일봉 미시딩 → trend_filter 상시 False). parity 는 *동일 신호에 대한 체결/포트폴리오 계층* 검증이므로 유효하며, 완화는 양 엔진에 동일 적용됐다 (설정 소스: test_vbt_runner_realdata._load_config).

| 항목 | 값 |
|---|---|
| trades | 11 ({'indicator_exit': 4, 'time_cut': 2, 'stop_loss': 5}) |
| trade seq | ✅ exact |
| Δreturn / ΔSharpe / ΔMDD | 0.00e+00 / 0.00e+00 / 0.00e+00 |
| Δfinal capital | 0.00e+00 KRW |
| equity maxΔ | 0.00e+00 KRW |
| to_dict 일치 | ✅ |
| 실행 시간 | legacy 14.1s / vectorbt 13.9s |

## 속도 — Optuna-style 스윕 (비게이트, 참고용)

- 합성 800 bars × 20 param evals, JIT warmup 제외
- 경량 합성 전략: legacy 0.13s / vectorbt runner 0.47s → **vectorbt 가 3.50× 느림** (eval 당 vbt Portfolio 구성 고정 오버헤드 ~17ms)
- 실전략(williams_r, 3397 bars): legacy 14.1s / vectorbt 13.9s → **0.99×** — 시그널 생성(어댑터/지표)이 지배해 오버헤드가 상쇄됨

**정직한 결론**: 현 단계 러너는 시그널 생성을 legacy 와 동일한 어댑터 순차 패스로 수행하므로(신호 parity 를 구조적으로 보장하기 위한 설계) 스윕 가속은 아직 없다 — 트리비얼 전략에선 오히려 vbt 고정비만큼 느리고, 실전략에선 동률이다. 본격적 벡터화 가속은 P1/P2(선언형 조건 → boolean 배열 사전계산)가 어댑터 순차 패스를 대체할 때 실현된다 — plan §5 P3-a 첫 항목. 이 PR 의 가치는 속도가 아니라 **계약 이전**(BacktestResult 를 vectorbt Portfolio 원장으로 채우는 검증된 경로 + parity 게이트)이다.

## Fill-model 매핑 노트 (요약)

`shared/backtest/vbt_runner.py` 모듈 docstring 이 정본. 요점:

1. 체결 시점: legacy 는 시그널 bar 의 **종가**에 즉시 체결 — `Portfolio.from_orders(price=close)` 로 재현. look-ahead 없음 (진입이 legacy 보다 이른 bar 에 체결될 수 없음).
2. 한국 비용 모델(매도세 비대칭)은 vbt `fees`(양측 비율)로 표현 불가 → 주문별 절대 `fixed_fees` 로 정확 매핑 (현금 흐름 잔차 0).
3. legacy `BacktestTrade.pnl` 은 진입비 제외 규약 → vbt 트레이드 pnl + entry_fees 로 보정 (cross-check 로 강제).
4. Sharpe/Sortino 는 legacy 자체 정의(일별 실현 PnL KRW) 재현 — vbt 네이티브 통계 전환은 legacy 제거 시 별도 결정.
5. 동일 bar 청산→재진입: 2컬럼 cash-sharing 그룹 + per-bar `call_seq` 로 매핑 (매도 정산 후 매수 순서 보존).
6. 미지원(→`NotImplementedError`, legacy 폴백): vectorbt 미설치 환경, 선물, ATS, 멀티심볼 프레임, 공매도 진입, regime gate 경로, DailyBacktestAdapter(일봉 어댑터) 경로(parity 미검증 — daily 전략은 exit 가 허용목록에 있어도 legacy), 허용목록 밖 exit 생성기(허용목록 = williams_r_exit / atr_dynamic / chandelier_exit — P3-c 확장; three_stage 는 부분청산이라 구조적 표현 불가로 영구 제외), 마지막 bar 진입+동일 bar END_OF_DATA 청산. 상태머신 exit 강제 전략은 `backtest.legacy_exit: true` 로 legacy 를 명시 강제할 수 있다(P3-c escape hatch). 러너 내부 cross-check 불일치(`VectorbtParityError`)도 seam 에서 legacy 폴백된다(심볼 드랍 아님, 조사용 경고).

## 판정

**PASS** — 주식(합성 + 실 exit 생성기 + 실데이터) 트레이드 시퀀스/지표 일치 **및** 선물 harness resolver 원장 ↔ from_orders 원장 tick 회계 일치 (허용오차 내).

운영자 flip(experiment 경로 `backtest.engine: vectorbt`) 은 본 증거 + paper 관찰을 근거로 별도 게이트에서 결정한다. 이 PR 은 기본값을 변경하지 않는다.
