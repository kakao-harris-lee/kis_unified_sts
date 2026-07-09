# Plans Index

Last updated: 2026-07-09 (CandleChart wiring handoff added; UX Tier 1-3 shipped).

This index separates plans that still affect operational decisions from completed
implementation records. For the current runtime snapshot, start with
[../PROJECT_STATUS.md](../PROJECT_STATUS.md). **The authoritative phased roadmap
(Cross-Asset + Stock + Futures) is [../ROADMAP.md](../ROADMAP.md)** — it supersedes
the scattered plan docs for "where is each asset headed".

## Active

| Plan | Status |
|---|---|
| [2026-07-08-new-architecture-gap-analysis.md](2026-07-08-new-architecture-gap-analysis.md) | **신규 아키텍처(TA-Lib+vectorbt+선언형 YAML) Gap Analysis** — 지시서 [docs/2026-07-08_new_architencture.md](../2026-07-08_new_architencture.md) 대비 컴포넌트별 현황: TA-Lib 엔진·builder_v1·실행계층 seam은 이미 존재(채택 미완), vectorbt는 미착수, 리스크는 2세계 이중화. 6개 병렬 코드 조사 종합. |
| [2026-07-08-new-architecture-refactoring-plan.md](2026-07-08-new-architecture-refactoring-plan.md) | **신규 아키텍처 단계별 리팩토링 계획** — P0 정리 → P1 지표 TA-Lib 위임 완성 → P2 builder_v1 선언형 승격 → P3 vectorbt 백테스트(WS-A4 승격) → P4 Risk Engine 통합 → P5 Futures Context/Hedge 배선 → P6 실행계층 마감. 각 Phase parity 게이트 필수. 기존 indicator-engine 로드맵(WS-A4)과 정합. |
| [2026-07-09-di-pydantic-integration-addendum.md](2026-07-09-di-pydantic-integration-addendum.md) | **DI + Pydantic + Polars/DuckDB 통합 보강안** — 지시서에 없는 별도 추가 4종을 위 리팩토링 계획에 얹는 횡단 레인. **Pydantic**은 이미 v2 표준(65파일)이라 신규 Phase 없이 P4(risk config 통일)+P2(전략검증 수렴)+ConfigMixin 폐기 위생 레인에 흡수. **dependency-injector**는 참조 0건 신규 프레임워크 — registry/adapter 원칙과 겹쳐 **서비스 조립 루트 + KIS 데이터 파사드로 범위 한정**, order_router PoC(v2호환/lazy-import/asyncio 3대 리스크 검증) 선행 후 **후행 P6.5**로 확산. **DuckDB**는 이미 프로덕션 채택(Parquet 질의 6사이트) — 커넥션 재사용 최적화만. **Polars**는 로드맵 WS-A2/A4 배정 미도입 — P3(vectorbt)와 묶어 numpy 2.0 스윕 선행, 고아 test_data_engine.py 정리가 첫 관문, pandas 전면 대체 아님(배치/백테스트 한정). 결정 로그 포함. |
| [2026-07-09-ux-improvement-research.md](2026-07-09-ux-improvement-research.md) | **UX 개선 리서치 — 신규 로드맵 × 최신 퀀트 UX 벤치마크** — 3-갈래 병렬(현재 프론트 file:line 실측 / QuantConnect·pyfolio·IBKR·Composer·StrategyQuant X·Build Alpha 웹 벤치마크 / 신규 아키텍처 P1~P6 UX 함의 코드 실측). 워크벤치 로드맵(2026-06-22)은 P0~P2 구현 완료했으나 3대 구조 갭: **크로스-엔티티 네비 부재**(lineage 데이터 있으나 plain text), **가격 시계열 위 시각화 전무**(체결마커/regime/underwater), **과적합-방지 시각화 부재**(walk-forward/Optuna 데이터 있으나 UI 0). 교차발견: 리테일 갭(regime 오버레이·divergence·PBO)이 신규 로드맵 산출물과 겹침 → 로드맵 구현이 최신 퀀트 UX 미충족 영역을 채움. Tier 1~3 우선순위 + **차트 라이브러리 확정(§6): visx 단일 추가, recharts 유지**. 결정 축: config-driven 알고 시스템이라 차트는 매매용이 아닌 사후 진단·통계용 → 실시간 캔들 특화 lightweight-charts 제외(과설계), 통계 차트 지배적이라 visx가 히트맵·underwater·밴드 네이티브 + 캔들은 SVG 프리미티브로 직접 구현(기존 recharts/Tailwind와 동일 idiom). ECharts는 echarts-for-react React19 미해결 이슈 3건 + canvas island로 제외. |
| [2026-07-09-ux-tier1-execution-plan.md](2026-07-09-ux-tier1-execution-plan.md) | **UX Tier 1 실행계획** — 위 UX 리서치 §4 Tier 1의 착수 계획. 통합 지점을 file:line 실측해 리포트 가정 보정: 딥링크(T1-1)는 데이터 O이나 **타깃 페이지 param 미수용** → 중간 비용, underwater(T1-2)는 `total_equity` 존재로 ✅저비용, 롤링지표(T1-3)는 **일수익률 API 부재** → 프론트 파생 확정. **결정 로그 확정**: T1-3=프론트 파생, 테마토글(T1-4c)=별도 분리, 1차 PR=T1-2+T1-4a(event asset 토글)+T1-4b(색상범례). 차트는 visx(리서치 §6). **구현 완료**: Tier 1(딥링크·underwater·롤링·테마·event asset)+Tier 3(regime 오버레이·slippage/TCA·divergence·상관 히트맵·노출 추이) main 머지. |
| [2026-07-09-candlechart-wiring-handoff.md](2026-07-09-candlechart-wiring-handoff.md) | **CandleChart 배선 인계 (모의투자 서버)** — Tier-3 D의 candle+markers primitive(`CandleChart.tsx`)와 `/api/market-data/bars` 라우트는 구현·테스트 완료·머지됐으나 **로컬엔 Parquet 시장데이터(`data/market`) 부재로 실증 불가** → 데이터 있는 모의투자 서버에서 심볼-스코프 뷰에 mount하는 절차·마커 조립(fills/signals)·정렬(timestamp 해상도)·검증 게이트 기록. 권장 배선 지점=DecisionTracePanel. Tier-2 A(shadow-parity)·B(walk-forward)는 P1/P3 백엔드 종속으로 여전히 BLOCKED. |
| [2026-07-05-indicator-engine-and-stream-schema-roadmap.md](2026-07-05-indicator-engine-and-stream-schema-roadmap.md) | **Indicator calc-engine redesign + Redis stream schema standardization** — two parallel tracks. **Track A (single calc SoT):** layered stack (TA-Lib basic SoT · Polars large-scale · NumPy+Numba `@njit` custom · vectorbt vectorized backtest) under an **Indicator Cache Engine** (thousands of symbols × hundreds of indicators, dedup by `(symbol,id,params,tf)`, incremental via `talib.stream`, parallel via Polars/pool) writing a **flat panel** that collapses the runtime/backtest dual-path AND resolves the builder plumbing gaps from the §1 investigation (7 unreachable indicators sma/macd/stochastic/williams_r/cci/trix/obv, ichimoku not wired, name mismatch, cross-operator dead code). Diagnosis: ATR duplicated ×7, ~10 recent PRs all doing hand-unification/parity — hot-path `_calc_rsi` is already full-recompute (not incremental) so no reason to keep a separate hand-rolled path. pandas-ta-classic re-scoped to test-only parity oracle. **Track B:** Pydantic per-stream schema + `shared/streaming/codec.py` + `schema_version` to end dynamic-type (`payload.get("x") or payload.get("y")`) breakage in the KIS-WS→Redis→pipeline path. Sequencing WS-A0→A1→A2→A3 (builder revival), B1–B3 parallel, A4/A5 later. |
| [2026-07-04-indicator-coverage-builder-catalog-roadmap.md](2026-07-04-indicator-coverage-builder-catalog-roadmap.md) | **Indicator coverage & builder-catalog consistency roadmap** — parallelizable workstreams (WS1 StochRSI phantom-strategy fix, WS2 indicator-calc single-source-of-truth to end RSI×4/Stoch×2/ADX×2/BB×2 duplication, WS3 expose already-implemented indicators in the builder catalog, WS4 reconcile frontend `constants.ts` (80) vs backend capabilities and activate dormant badges, WS5 futures microstructure CVD + volume profile) with lanes/dependency graph and cross-cutting verification gates (backtest↔runtime parity, no-lookahead, KST, TTL, long/short symmetry, config-driven). **Status 2026-07-04:** M1 (WS3 catalog 10→18, WS4 dynamic-fetch badges, parity harness, pandas-ta decision) + M2-A (reference calculators) + StochRSI wiring (default-off) **merged to main**; value-changing fixes held on gated branches `feat/indicator-adx-wilder-gated` (regime gate) and `feat/indicator-rsi-wilder-gated` (backtest gate) — see [indicator-m2-handoff](2026-07-04-indicator-m2-handoff.md) to run the gates on a data server. |
| [2026-07-04-runtime-refactoring-roadmap.md](2026-07-04-runtime-refactoring-roadmap.md) | **Runtime refactoring and event-driven roadmap** — additive Interface/Decorator/Factory plan to reduce coupling and agent context cost; runtime large-file split priority 3 completed in `83e94681`; follow-up decomposition merged in `2140c9ed`; remaining active scope is orchestrator runtime slices, independent large-surface splits, and safe futures monolith -> F-9 event-driven transition. |
| [../superpowers/plans/2026-07-04-runtime-refactoring-next-priorities.md](../superpowers/plans/2026-07-04-runtime-refactoring-next-priorities.md) | **Runtime refactoring next-priority execution plan** — immediately actionable P1/P2/P3 backlog with branch/worktree lanes, exact files, tests, verification commands, conflict rules, and merge gates. |
| [2026-07-02-unified-investment-system-roadmap.md](2026-07-02-unified-investment-system-roadmap.md) | **Cross-asset unified investment system roadmap** — maps [통합_투자_시스템_전략_설계서.md](../통합_투자_시스템_전략_설계서.md) onto the current codebase: Market Risk Score (0–100) from futures market structure (foreign flow/OI/program/basis) + macro, unified regime engine, integrated MDD circuit breaker, hedge advisor, `/market` dashboard, Track A ledger. **Phases P0–P6 code merged 2026-07-03 (risk gates shadow-default); stays Active for the operator gates (backfill/enforce flips/drill/holdings) and open items O11–O17.** |
| [2026-06-22-quant-ops-workbench-uiux.md](2026-06-22-quant-ops-workbench-uiux.md) | Active UI/UX roadmap for Quant Ops Workbench: P0 cockpit, signal trace, risk/exposure, backtest-vs-paper comparator; structured for multi-agent implementation lanes. |
| [2026-06-02-stock-reopt-har-rv-followups.md](2026-06-02-stock-reopt-har-rv-followups.md) | Open domain follow-up recommendations: HAR-RV log-RV validation, stock strategy reactivation decisions, MLflow ops. |

## Current Decisions And Reference

| Plan | Use Today |
|---|---|
| [2026-06-03-ml-rl-removal-llm-indicator-futures.md](2026-06-03-ml-rl-removal-llm-indicator-futures.md) | Current futures decision: ML/RL/TFT runtime paths removed; futures work uses Setup A/C, LLM context, and explicit indicators/rules. |
| [2026-06-03-runtime-storage-decoupling-implementation.md](2026-06-03-runtime-storage-decoupling-implementation.md) | Current storage decision: Redis DB 1 + SQLite runtime ledger + Parquet/DuckDB market data; ClickHouse removed from active runtime paths. |
| [2026-04-20-futures-paradigm-phase5-rollout.md](2026-04-20-futures-paradigm-phase5-rollout.md) | Futures live rollout Gate 1–4 procedure (still valid) + rollback policy; RL/systemd/ClickHouse references are historical (see top note in the doc). |
| [2026-05-26-strategy-lab-extension-design.md](2026-05-26-strategy-lab-extension-design.md) | Strategy Lab product direction (active); many pieces now exist in `strategy-builder-ui/`, dashboard APIs, and experiment runner. UI is Next.js, not Vite. |

## Historical Reference

Historical plans that no longer drive current operator decisions live under
[archive/](archive/). Keep them out of default agent context unless you need
audit history for an older change.

## Archive

Completed implementation records live under [archive/](archive/). Recent moves:

| Plan | Completion Record |
|---|---|
| [archive/2026-05-28-vite-dashboard-to-nextjs-migration.md](archive/2026-05-28-vite-dashboard-to-nextjs-migration.md) | Next.js-only frontend migration completed 2026-05-31. |
| [archive/2026-06-01-improve-ux.md](archive/2026-06-01-improve-ux.md) | Original builder-funnel UX prompt, superseded by the implemented superpowers spec/plan. |
| [archive/2026-06-06-compose-pipeline-services.md](archive/2026-06-06-compose-pipeline-services.md) | Stock pipeline Compose profile migration implemented. |
| [archive/2026-06-09-cron-to-compose-scheduler.md](archive/2026-06-09-cron-to-compose-scheduler.md) | Scheduler/producers Compose migration implemented. |
| [archive/2026-06-14-stock-strategy-experiment-backtest.md](archive/2026-06-14-stock-strategy-experiment-backtest.md) | Stock experiment runner/API/UI/scheduler implemented. |
| [archive/2026-04-15-paper-trading-quality-recovery.md](archive/2026-04-15-paper-trading-quality-recovery.md) | Historical paper-quality investigation; RL/ClickHouse sections obsolete after 2026-06-03 removals. |
| [archive/2026-04-20-futures-trading-change-paradagms.md](archive/2026-04-20-futures-trading-change-paradagms.md) | Original futures paradigm brief; superseded by Setup A/C + LLM-context roadmap and current rollout gates. |
| [archive/2026-04-20-futures-paradigm-phase1-data-infra.md](archive/2026-04-20-futures-paradigm-phase1-data-infra.md) and phase 1-5 companion specs/plans | Historical futures paradigm implementation record; current futures direction is [../ROADMAP.md](../ROADMAP.md), Setup A/C, LLM context, and the F-9 runbook. |
| [archive/2026-02-20-position-recovery-design.md](archive/2026-02-20-position-recovery-design.md), [archive/2026-03-02-momentum-breakout-trend-mode-design.md](archive/2026-03-02-momentum-breakout-trend-mode-design.md), [archive/VR_Trading_Strategy_Design_Spec.md](archive/VR_Trading_Strategy_Design_Spec.md) | Older stock/recovery/VR strategy designs retained for audit history, not active roadmap steering. |
| [archive/2026-06-24-no-trade-diagnosis.md](archive/2026-06-24-no-trade-diagnosis.md) | Draft diagnostic plan superseded by later signal trace, gap research, and roadmap/status updates. |

### Historical / Archived — superseded 2026-06-20 (DO NOT REFERENCE for current work)

These plans were moved to `archive/` on 2026-06-20 with a SUPERSEDED banner.
They are kept for audit trail only. Use the replacement docs instead.

| Archived plan | Replaced by |
|---|---|
| [archive/2026-04-20-futures-paradigm-master.md](archive/2026-04-20-futures-paradigm-master.md) | [2026-06-03-ml-rl-removal-llm-indicator-futures.md](2026-06-03-ml-rl-removal-llm-indicator-futures.md) + [../ROADMAP.md](../ROADMAP.md). Phase 5 *procedure* remains live in [2026-04-20-futures-paradigm-phase5-rollout.md](2026-04-20-futures-paradigm-phase5-rollout.md). |
| [archive/2026-05-03-llm-primary-rl-minimization.md](archive/2026-05-03-llm-primary-rl-minimization.md) | [2026-06-03-ml-rl-removal-llm-indicator-futures.md](2026-06-03-ml-rl-removal-llm-indicator-futures.md). LLM-primary cutover audit trail. |
| [archive/2026-04-20-futures-paradigm-rl-repurposing.md](archive/2026-04-20-futures-paradigm-rl-repurposing.md) | RL removed 2026-06-03 → [2026-06-03-ml-rl-removal-llm-indicator-futures.md](2026-06-03-ml-rl-removal-llm-indicator-futures.md). |
| [archive/2026-04-20-futures-paradigm-rl-repurposing-v2.md](archive/2026-04-20-futures-paradigm-rl-repurposing-v2.md) | RL removed 2026-06-03 → [2026-06-03-ml-rl-removal-llm-indicator-futures.md](2026-06-03-ml-rl-removal-llm-indicator-futures.md). |
| [archive/2026-04-15-rl-retraining-data-refresh.md](archive/2026-04-15-rl-retraining-data-refresh.md) | RL removed 2026-06-03; do not resume retraining without explicit operator reversal. |
| [archive/2026-02-26-stock-strategy-redesign.md](archive/2026-02-26-stock-strategy-redesign.md) | ClickHouse-era; data layer obsolete (now Parquet/DuckDB). Current: [../ROADMAP.md](../ROADMAP.md) + [../PROJECT_STATUS.md](../PROJECT_STATUS.md). |

> The synthetic-data stock validation summary
> [`../archive/STOCK_STRATEGY_VALIDATION_SUMMARY.md`](../archive/STOCK_STRATEGY_VALIDATION_SUMMARY.md)
> was also archived 2026-06-20 (it is a top-level doc, not a plan).

Older archived plans remain in the same folder for historical context.

## Adding A Plan

1. Add new plans at `docs/plans/2026-MM-DD-<slug>.md`.
2. Put the new plan in **Active** while work is underway or operator decisions
   remain open.
3. Move completed implementation records to `archive/` once the current docs or
   code no longer need them as a top-level operational reference.
