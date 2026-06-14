# 주식 전략 실험(백테스트) 통합 개선 계획

- 작성일: 2026-06-14
- 결정: **온디맨드 + 야간 정기 배치 둘 다**, **현재 운용 레지스트리 전략을 실제 `BacktestEngine`으로 실험**(빌더 프리셋은 통합 리포트로 흡수)
- 목표: 대시보드 `/experiments`에서 현재 주식 전략들을 수집된 백테스트 데이터로 실험하고, 정식 지표(Sharpe/MDD/승률/수익률)로 비교한다.

---

## 1. 현재 상태 진단 (라이브·코드·크론 확인)

`/experiments`는 **단 하나의 일회성 실험**만 보여준다: `bullish_builder_presets_2026w23` — 11개 *빌더 프리셋*(`config/strategy_builder/kis_presets.yaml`)을 고정 종목·**일봉**으로 고정된 1주(2026-06-01~06-05)만 돌린 결과.

**연결이 끊긴 4지점:**
1. **엔진 분리** — 러너(`scripts/analysis/stock_builder_preset_experiment.py`, 932줄)는 실제 `BacktestEngine`이 아닌 **자체 페이퍼 시뮬 루프**다. `BacktestResult`의 Sharpe/MDD/`to_metrics_dict()`를 안 쓰므로 지표가 빈약(수익률·체결수만).
2. **대상 분리** — 러너는 `kis_presets`→`BuilderState`→`StrategyBuilderEvaluator`만 실행. **현재 운용 레지스트리 전략**(pattern_pullback/momentum_breakout/williams_r=enabled, vr_composite/trend_pullback 등=disabled)은 못 돌림. 레지스트리 전략은 `sts backtest run`(CLI)에서 `BacktestEngine`으로만 돌릴 수 있고 대시보드에 노출 안 됨.
3. **고정 과거 1주** — 온디맨드 재실행/새 실험 생성 불가, 대시보드에 1개 하드코딩(`GET /api/kis-builder/experiments/stock-builder-preset`).
4. **스케줄 미가동** — 호스트 크론(16:35 KST, 날짜 게이트)으로 돌던 것이 만료. 크론→compose 컷오버 미완(`deploy/scheduler.crontab`에 실험 엔트리 없음; scheduler는 profile-gated).

**"실패 케이스"의 실체:** ① status `ended_incomplete`(4/5 — 한 날 리포트 누락=크론 미스) ② 음수수익·0체결 프리셋(정상 결과인데 실패처럼 보임) ③ 윈도우 종료로 stale. **에러/no-data/단순손실을 구분하는 per-strategy 상태가 없음**이 근본 UX 문제.

**수집 데이터 (`data/market/stock/`):**
- 일봉: **421종목, 2023-06~2026-06 (3년)** — 스윙/일봉 전략(pattern_pullback, vr_composite)에 충분.
- 분봉: **45종목, 2026-03~2026-06 (3개월)** — 인트라데이 전략(momentum_breakout/williams_r/trend_pullback)은 데이터 얇음(핵심 갭).
- 로더: `shared/storage/market_data_store.py::load_market_bars_for_backtest(symbol, asset_class, timeframe, start, end)`.

---

## 2. 목표 아키텍처

**핵심 원칙: 엔진은 둘을 유지하되 리포트를 통합한다.** 레지스트리 전략 → 실제 `BacktestEngine`, 빌더 프리셋 → 기존 `StrategyBuilderEvaluator`. 둘의 출력을 **단일 통합 스키마**로 정규화.

```
실험 스펙(strategies[], symbols/universe, start/end, timeframe, capital/costs)
      │
      ▼
StockExperimentRunner  (신규, shared/backtest/experiment_runner.py)
  ├─ 각 strategy 항목:
  │    type=registry → StrategyFactory.create_from_file → (Daily|Minute)BacktestAdapter → BacktestEngine.run(df) → BacktestResult
  │    type=builder  → get_kis_preset → BuilderState → StrategyBuilderEvaluator (기존 경로 재사용)
  │  + 타임프레임 인지 데이터 로드 + 커버리지 검증 → per-strategy status(ok/skipped:no-data/error)
  ▼
통합 리포트 JSON (summaries[+sharpe/mdd/win_rate], equity_curves, trades, data_coverage, status/error)
  → reports/stock_experiment/<exp_id>_<ts>.json
      │
      ├─ (배치) compose scheduler가 야간 실행
      └─ (온디맨드) dashboard 백그라운드 잡이 실행
      ▼
백엔드 /api/experiments/* (목록/생성/상태/결과)  →  프론트 /experiments (목록 + 새 실험 폼 + 리포트 뷰)
```

**통합 리포트 스키마(기존 확장):** 현재 `summaries[]`에 `sharpe_ratio`, `max_drawdown_pct`, `win_rate_pct`(이미 일부 있음), 그리고 **`status`(ok/skipped/error)·`error`·`engine`(registry|builder)·`timeframe`** 필드를 추가. 이걸로 "실패 케이스"를 명확히 구분(에러 vs 데이터없음 vs 손실).

---

## 3. 단계별 실행 계획

### Phase 1 — 통합 실험 러너(백엔드 코어, UI 없음) ★기반
- 신규 `shared/backtest/experiment_runner.py::run_stock_experiment(spec) -> report_dict`.
  - 재사용: `StrategyFactory.create_from_file`, `DailyBacktestAdapter`/`BacktestStrategyAdapter`, `BacktestEngine`, `load_market_bars_for_backtest`, `result.to_metrics_dict()`.
  - 빌더 프리셋 경로는 기존 `stock_builder_preset_experiment.py`의 평가 로직을 함수로 추출해 재사용(중복 제거, DRY).
  - **타임프레임 인지**: 전략 YAML의 `strategy.timeframe`(minute|daily)에 맞는 데이터 로드. 커버리지 없으면 `status: skipped`로 기록(조용한 실패 금지).
  - 통합 스키마로 리포트 작성 → `reports/stock_experiment/`.
- 실험 스펙 스키마(Pydantic) + 기본 스펙 YAML(`config/experiments/stock_default.yaml`): 현재 enabled 레지스트리 전략 + 선별 빌더 프리셋, 일봉, 유니버스/워치리스트, rolling 윈도우.
- CLI: `sts experiment run --spec <yaml>` (또는 기존 `sts backtest`에 서브커맨드) — 배치/디버그용.
- 테스트: 러너 단위(레지스트리 1 + 빌더 1, no-data skip, error 캡처), 스키마.

### Phase 2 — 야간 정기 배치(compose 스케줄러)
- `deploy/scheduler.crontab`에 야간 엔트리 추가(KST native): `sts experiment run --spec config/experiments/stock_default.yaml`.
- 죽은 호스트 크론(`stock_builder_preset_experiment`) 제거, 크론→compose 컷오버 마무리(`docs/plans/2026-06-09-cron-to-compose-scheduler.md` 연계).
- rolling 윈도우(예: 최근 N개월)로 매일 갱신 → `ended_incomplete` 같은 만료 상태 소멸.

### Phase 3 — 백엔드 API 일반화 + 온디맨드 잡 러너
- `/api/experiments/*`로 일반화(기존 `/api/kis-builder/experiments/stock-builder-preset`는 호환 유지 또는 리다이렉트):
  - `GET /api/experiments` — 실험 목록(배치+온디맨드).
  - `POST /api/experiments` — 스펙 받아 백그라운드 잡 생성 → `job_id`. 상태 pending/running/done/failed.
  - `GET /api/experiments/{id}` — 상태 + 리포트.
- **잡 실행**: 백테스트는 CPU 무거움 → asyncio 백그라운드 태스크 + **동시성 1(큐)** + 진행률. 잡 상태는 Redis(DB1) 또는 경량 테이블에 영속. 인증은 기존 `X-API-Key` 패턴.
- 안전장치: 종목수×기간×전략 상한, 타임아웃, 부분 실패 격리.

### Phase 4 — 프론트 온디맨드 UI
- `/experiments`: 목록(카드) + **"새 실험" 폼** — 전략 멀티셀렉트(레지스트리+프리셋), 기간 피커, 종목/유니버스 선택, 타임프레임 → 실행 → 잡 폴링 → 상세 리포트.
- 기존 리포트 뷰(표/차트) 일반화 + **per-strategy status 뱃지**(ok/skipped/error) 표시 → "실패 케이스" 명확화.
- React Query invalidation/폴링으로 running→done 갱신.

### Phase 5 — 인트라데이 데이터 커버리지(병행)
- 분봉이 얇음(45종목/3개월). 옵션:
  - (a) 온디맨드 인트라데이 실험은 커버된 45종목·해당 기간으로 제한 + "제한적 커버리지" 안내.
  - (b) `sts stock-backfill`로 분봉 백필 확대(종목/기간) — 별도 작업.
- 러너의 커버리지 검증이 갭을 `skipped`로 표면화(은폐 금지).

---

## 4. 핵심 결정·리스크
- **엔진 통합 범위**: 엔진 자체는 통합하지 않고(레지스트리=BacktestEngine, 빌더=evaluator) **리포트 스키마만 통합**하는 게 실용적·저위험. 빌더→BacktestEngine 어댑터는 후속 선택.
- **CPU 비용**: 온디맨드 다전략×다종목×수년은 느림 → 큐+상한+진행률 필수.
- **인트라데이 데이터 갭**: 최대 제약. **KIS 분봉 히스토리는 ~30일이 하드 실링**(코드로 못 넘김) — `data/market/stock/minute`는 데일리 크론이 누적한 결과다. 일봉 전략(pattern_pullback/vr_composite)은 3년치로 충분, 분봉 전략(momentum_breakout/williams_r)은 유니버스(30종목) × 최근 ~30일만 가능. 그 밖 종목은 `skipped`로 표면화.
- **paper/live 분리 유지**: 실험은 분석용(paper 스택), 주문 경로와 무관.
- **DRY**: 기존 `stock_builder_preset_experiment.py`의 빌더 평가 로직은 재사용(삭제 아님), 통합 러너가 호출.

## 5. 권장 순서
Phase 1(코어 러너) → Phase 2(배치, 빠른 가치) → Phase 3·4(온디맨드+UI) → Phase 5(데이터, 병행). Phase 1이 모든 것의 토대.

## 6. 구현 현황 (2026-06-14)
- **Phase 1 ✅ #473** — `shared/backtest/experiment_runner.py` + `sts experiment run` (심볼별 실행+등가중 집계, finite-safe).
- **Phase 2 ✅ #475** — 야간 스케줄러 엔트리(16:40 KST) → `reports/stock_experiment/`.
- **Phase 3 ✅ #476** — `services/dashboard/routes/experiments.py` 온디맨드 잡(`asyncio.to_thread`+락) + API.
- **Phase 4 ✅ #477** — `/experiments` UI(새 실험 폼/폴링/상태 칩).
- **Phase 5 ✅** — 스케줄러 분봉 백필 `--days 30`(KIS-max 윈도우 유지) + UI 데이터 커버리지 패널 + KIS ~30일 한계 문서화. 인트라데이 전략이 커버된 유니버스 심볼에서 실제 동작 검증 완료(momentum_breakout: ok, 거래 발생).
