# UX 개선 리서치 — 신규 로드맵 × 최신 퀀트 UX 벤치마크 (2026-07-09)

> 상위 계획: [2026-07-08-new-architecture-refactoring-plan.md](2026-07-08-new-architecture-refactoring-plan.md)
> 보강안: [2026-07-09-di-pydantic-integration-addendum.md](2026-07-09-di-pydantic-integration-addendum.md)
> 기존 UI/UX 로드맵: [2026-06-22-quant-ops-workbench-uiux.md](2026-06-22-quant-ops-workbench-uiux.md)
> 조사 기준: main `ed8a95aa` (2026-07-09). 3-갈래 병렬 리서치: (A) 현재 프론트 실측,
> (B) 최신 퀀트 UX 벤치마크(웹), (C) 신규 로드맵 UX 함의(코드 실측).

## 0. 결론 요약

기존 Quant Ops Workbench 로드맵(2026-06-22)은 P0~P2를 **이미 구현 완료**했다
(14 페이지 + 34 대시보드 라우트, cockpit/signals/risk/coverage/evidence/event-context
등). 그 로드맵은 "운영 의사결정 워크플로우"를 목표로 했고 그건 달성됐다.

**이번 리서치의 새로움은 두 축이다:**
1. **신규 아키텍처(P1~P6)가 만들어내는 새 UX 요구** — 기존 워크벤치 로드맵에 없던 것.
   지표 convention-gate/shadow-parity 관측, vectorbt 기반 walk-forward/민감도 시각화,
   선언형 빌더 P2-a 확장, risk 통합 후 노출 필드.
2. **최신 퀀트 플랫폼 대비 구조적 갭** — 벤치마크로 확인된, 홈메이드 시스템이
   놓치기 쉬운 패턴(가격차트+체결마커, underwater plot, 백테스트-라이브 divergence 등).

**한 줄 판정**: 워크벤치는 "표(table) 워크플로우"로는 성숙했으나 **(a) 크로스-엔티티
네비게이션 부재, (b) 가격 시계열 위 시각화(마커/regime/체결) 전무, (c) 실험 통계의
과적합-방지 시각화 부재** 세 구조적 갭이 있고, 이 셋은 각각 이미 존재하는 데이터·신규
로드맵 산출물·저비용 차트로 메울 수 있다. 아래 §4에 우선순위.

## 1. 현재 프론트엔드 실측 (갈래 A)

14 페이지, Next.js App Router + Tailwind v4(무 컴포넌트라이브러리, hand-rolled) +
recharts + React Query(폴링 4-tier) + `/ws` 브리지(캐시 invalidation 전용). 상세 근거:

### 1.1 확정된 상위 갭 (file:line)

| # | 갭 | 근거 | 성격 |
|---|---|---|---|
| A1 | **크로스-엔티티 네비게이션 전무** — 백엔드는 signal→order→fill→position→trade lineage를 반환하나 UI는 전부 plain text, 클릭 이동 불가 | `signals/components/DecisionTracePanel.tsx:428-432`. `<Link>`은 `Navigation.tsx`와 `GlobalIndicators.tsx:30-40` 두 곳에만 존재 | **데이터 이미 있음 → 최고 레버리지** |
| A2 | **`/builder`·`/execute`가 시각적으로 고아** — `HeaderBar`/asset-tabs 미렌더, 별도 UI 언어 | `builder/page.tsx:328`, `execute/page.tsx:202` (둘 다 `HeaderBar` import 0) | 일관성 |
| A3 | **가격차트+진입/청산 마커가 어디에도 없음** — recharts로 6+ line/bar 있으나 심볼 가격 시계열에 시그널/체결 오버레이 0개 | Signals/Trades/Positions 전부 부재 | **차트 idiom 부재** |
| A4 | 13-항목 flat 네비, 그룹핑 없음, 모바일 아이콘-only | `Navigation.tsx:29-43,81-105` | 정보구조 |
| A5 | 테마 토글 부재 (dark는 `prefers-color-scheme`만) | `globals.css:59-70`, `setTheme` grep 0 | 편의 |
| A6 | 한국식 색상관례(빨강=상승/이익) 범례·툴팁 없음 → 서구 직관 사용자 오독 | `globals.css:16-17` (`--color-profit:#ef4444`) | 접근성/명료성 |
| A7 | `/event-context` `asset_class:"futures"` 하드코딩 → 주식 사용자 무용 | `event-context/page.tsx:463-467` | 커버리지 |
| A8 | 프로모션 칸반이 "Live Gated"에서 막다른 길 — 실제 승격 액션·다음 단계 안내 없음 | `StrategyPromotionBoard.tsx:129,597-598` | 워크플로우 |
| A9 | `/experiments` job 진행이 이진(running/done) — % 없음, 취소 없음 | `experiments/page.tsx:357-360,448` | 피드백 |
| A10 | `/trades` Live(Redis) vs History(DB) 2소스가 분리 탭 — 마이그레이션 시점·통합 카운트 없음 | `trades/components/TradesTabList.tsx` | 명료성 |

### 1.2 잘 되어 있는 것 (유지)

- 접근성 우수: `role=tab/tablist`, `aria-selected/current`, `sr-only` 캡션, 키보드 네비.
- 킬스위치 모바일 UX: `SlideToConfirm.tsx`(90% 드래그+reduced-motion 폴백) + `MobileKillSwitchBar`.
- 카드-vs-테이블 반응형 일관성, `/signals` DecisionTracePanel 드릴다운 깊이.
- 명시적 `unknown/not_available/unavailable` 상태 어휘 (건강하지 않은 것을 건강하게 안 보임).

## 2. 최신 퀀트 UX 벤치마크 (갈래 B, 웹 리서치)

QuantConnect / TradingView / Composer.trade / IBKR Risk Navigator / Portfolio Visualizer
/ pyfolio·QuantStats / Freqtrade / Hummingbot / Alpaca / OpenAlgo 등 실측. 핵심 패턴:

### 2.1 즉시 채택 가치 높은 패턴 (operator value ÷ build cost 상위)

| 패턴 | 예시 플랫폼 | 운영자 결정 | 빌드 |
|---|---|---|---|
| **Underwater(수중) drawdown plot** | pyfolio `plot_drawdown_underwater`, QuantStats | 현재 낙폭이 역사적 정상 범위인지 새 손실 국면인지 | **낮음** (equity 시계열의 파생 area chart) — 최고 가성비 |
| **가격차트 위 체결/시그널 마커** | QuantConnect live(제출=회색원/체결=색화살표 at fill price), Hummingbot(entry→exit 색선), 3Commas | "나쁜 체결이었나"를 벤치마크(당시 시가)와 같은 프레임에서 즉시 판단 | 중간 (candlestick+마커; recharts는 캔들 없음→경량 라이브러리 검토) |
| **롤링 리스크 지표 시계열** (rolling Sharpe/vol/Sortino) | pyfolio, QuantStats, Local Maestro | "롤링 샤프가 3주째 음수" → regime 분류기 없이도 실행 가능 | **매우 낮음** (rolling window + line) |
| **백테스트-라이브 divergence 추적** | QuantConnect Live Reconciliation (OOS 백테스트 곡선 오버레이 + DTW 일평균%오차 스칼라) | 라이브가 백테스트 프로파일에서 이탈하는지 상시 감시 | 중간 — **리테일 유일 best-in-class, 차별화 지점** |
| **파라미터 민감도 히트맵 + 과적합 경고** | Build Alpha, StrategyQuant, PBO/deflated Sharpe 문헌 | "이 파라미터가 봉우리 하나에만 얹혀있나(과적합)" | 중간 (Optuna 데이터 이미 산출됨) |
| **Monte Carlo 트레이드-셔플 신뢰밴드** | Portfolio Visualizer (fan chart + 종말분포 히스토그램) | 단일 백테스트를 결과 분포로 — 꼬리위험 포함 | 중간 |
| **상관 히트맵 (특히 drawdown-conditional)** | QuantConnect Research, Local Maestro | 거짓 분산투자 방지 — 폭락 시 동시 하락하는 전략 탐지 | 낮음~중간 |
| **노출 시계열 (net long/short, 섹터 틸트)** | Composer Historical Allocation, Local Maestro | 시간에 걸친 집중위험 누적 | 낮음 (포지션 스냅샷 stacked-area) |

### 2.2 확인된 "리테일 갭" = 차별화 기회

벤치마크가 **홈메이드가 오히려 앞설 수 있다**고 확인한 영역:
- **equity/price 곡선 위 regime 컬러 오버레이** — 어떤 상용 리테일 플랫폼도 shipped 기능
  없음(블로그/튜토리얼 수준만). 이 repo는 RegimeGate/HAR-RV 분류기가 이미 있어
  **분류 비용이 매몰됨 → 거의 순수 프론트 작업**.
- **per-fill TCA (체결 vs arrival price)** — 리테일 브로커는 분기 PDF(605/606)만 제공.
  per-fill slippage 시각화는 어떤 리테일 도구보다 우위.
- **주문 latency 분해(스테이지별)** — OpenAlgo 등 1인 오픈소스에만 존재, 상용 부재.
- **backtest-vs-live divergence 상시 지표** — QuantConnect만 유일. 최고 레버리지 차별화.

### 2.3 백테스트/전략개발 앵글 심화 — walk-forward & 과적합 시각화 (15패턴)

전용 리서치(StrategyQuant X / Build Alpha / QuantConnect / vectorbt / pyfolio /
QuantStats / TradingView / Composer / Numerai)에서 도출한 과적합-방지 시각화 패턴.
**P3(vectorbt) + Optuna 스윕이 만드는 데이터와 정확히 맞물린다.**

| 패턴 | 예시 | 운영자 결정 | 비고 |
|---|---|---|---|
| **Walk-Forward Matrix** (IS/OOS 색상 그리드) | StrategyQuant X(run×OOS% 셀, 초록/빨강 pass-fail, "stable zone"), Build Alpha(5×5, 파랑=IS/초록=OOS) | 과적합을 단일 숫자 아닌 **공간 패턴**으로 — 고립 초록 셀 vs 견고한 초록 블록 | P3 walk-forward의 1급 시각화 |
| **최적화 히트맵 / 3D 파라미터 표면** | QuantConnect(2-param 히트맵, 3-param 회전 3D, "일관된 색상"=안정존), vectorbt(`.vbt.heatmap()` + 3D `go.Volume`) | 파라미터 봉우리가 넓은 안정존인지 뾰족한 스파이크(과적합)인지 | Optuna 데이터 이미 산출 |
| **WF 3D 안정성 표면** (smooth vs spiky) | StrategyQuant X(NetProfit/DD/Stability 표면), Build Alpha NTO(노이즈 주입 51 series) | 매끄러움=견고, 뾰족함=과적합 | Tier 3 |
| **Monte Carlo fan chart** (신뢰밴드+bust/goal 임계선) | QuantStats `plot_montecarlo`(spaghetti+95%밴드+중앙값+실제경로+임계선), Build Alpha(5th/95th equity fan + drawdown CDF) | 단일 백테스트를 결과 분포로 — "95% 신뢰수준 낙폭 ≤30%" | QuantStats가 가장 완성된 청사진 |
| **Bayesian cone / posterior** | pyfolio `create_bayesian_tear_sheet`(Sharpe/vol posterior + OOS cone) | 통계적으로 가장 정교 | pymc3 필요, 유지보수 중단 fork — 참고만 |
| **월별 수익률 히트맵** | QuantStats `monthly_heatmap`(year×month, RdYlGn diverging) | 계절성·특정월 취약 | 저비용 |

**⭐ 가장 citable한 갭 — Deflated Sharpe / PBO는 리테일 GUI에 사실상 전무:**
QuantConnect·QuantStats조차 **PSR(Probabilistic Sharpe)만** 구현, DSR/PBO 미구현.
QC 스태프 명시: "DSR은 비결정적이라 PSR을 선택". 완전한 PBO/CSCV 구현은 연구 스크립트
`pypbo`(~136★, matplotlib 3-panel)에만 존재, StrategyQuant X·Build Alpha 문서엔 "PBO/DSR"
언급 0. **학술적으로 엄밀한 다중검정 보정이 2025-26 리테일에 침투 0** — 홈메이드가
`shared/backtest`에 DSR/PBO를 계산·시각화하면 명확한 차별화(단, 계산 신설 필요 = Tier 3).

**노코드 빌더 floor 비교**: Composer.trade는 3-블록 선형 편집기(Weighting/Conditional/
Filter-Sort-Select)이고 **walk-forward/Monte Carlo/OOS-split UI가 전무** — 이 repo의
builder_v1 + P3 시각화가 이를 상회할 여지.

## 3. 신규 로드맵이 만드는 새 UX 요구 (갈래 C, 코드 실측)

기존 워크벤치 로드맵에 **없던**, 신규 아키텍처(P1~P6)·보강안이 새로 요구하는 표면:

| 로드맵 산출물 | 새 UX 요구 | 현재 상태 (실측) |
|---|---|---|
| **P1 지표 TA-Lib 위임 + convention flip** (`STS_INDICATOR_CONVENTION`) | 지표별 safe/gated 분류, parity delta %, flip 준비도 관측 화면 — flip이 "운영자 게이트"라 UI 필수 | **부재.** shadow-parity는 `shared/indicators/engine/shadow.py`+테스트에만. health.py의 "shadow"는 선물 계약/증거금 read-model(무관) |
| **P3 vectorbt 백테스트** (walk-forward/민감도 가속) | walk-forward OOS fold 시각화, 파라미터 민감도 히트맵, Optuna param importance/history | **부재(UI).** `scripts/walk_forward_{bootstrap,phase3,paper_foldin,sensitivity}.py` 4종 + `optimizer.py`(matplotlib `plot_*`)만. 대시보드/라우트 노출 0 |
| **P2 선언형 빌더 승격 + P2-a 어휘 확장** | signal_direction(선물 대칭), exit 프리미티브 참조, regime/LLM 게이트 훅을 카탈로그·UI에 노출 | `/capabilities` 엔드포인트 존재(`strategy_builder.py:82`), builder 펀넬 존재. 단 P2-a 신규 어휘 미반영 |
| **P4 Risk Engine 통합** (레버리지/증거금 신설, 프리미티브) | 통합 후 단일 RiskExposure에 레버리지 사용률·증거금 게이트·프리미티브 상태 노출 | `/risk` + `RiskExposure` DTO 존재. 신설 필드(레버리지·증거금) 미노출 |
| **P5 Futures Context/Hedge 배선** | basis/OI/외인/롤/증거금 regime read-model, hedge advisory 노출 | `/market`에 부분 노출(`market_risk.py`, `portfolio.py` hedge, `health_futures_contract.py`). 조합 서비스 dormant라 자주 빈 화면 |
| **P6 KIS 데이터 파사드 + 체결모델 정렬** | 체결모델 3벌(백테스트 다음바±0.3틱 vs 라이브 passive vs 페이퍼) 괴리를 slippage 캘리브레이션 리포트로 | **부재.** §2.2 per-fill TCA 갭과 정확히 일치 |

**교차 관찰**: 갈래 B의 "리테일 갭 = 차별화"와 갈래 C의 "신규 로드맵 산출물"이
정확히 겹친다 — regime 오버레이(P5 분류기), divergence 추적(P3 parity + P6 체결),
민감도 히트맵(P3 vectorbt). **즉 신규 로드맵을 구현하면 그 데이터가 마침 최신 퀀트
UX의 미충족 영역을 채운다.** UX 작업을 로드맵에 얹으면 한계비용이 낮다.

## 4. 우선순위화된 개선 포인트

**우선순위 = (운영자 가치 × 로드맵 정합) ÷ 빌드비용.** 3-갈래 교차 검증된 항목 우선.

### Tier 1 — 데이터 이미 존재, 저비용, 즉시 착수 가능

1. **크로스-엔티티 딥링크** (A1). lineage 데이터는 이미 반환됨 — signal/order/fill/
   position/trade ID를 `<Link>`로. 최고 레버리지. **기존 워크벤치 P1.1 blotter의 완성.**
2. **Underwater drawdown plot** (B). equity 시계열 파생 area chart — `/risk`·`/experiments`
   에 추가. 최고 가성비.
3. **롤링 리스크 지표 시계열** (B). rolling Sharpe/vol — 이미 있는 일수익률로. 저비용.
4. **`/event-context` asset_class 토글** (A7), **색상관례 범례**(A6), **테마 토글**(A5) —
   소규모 명료성 수정 묶음.

### Tier 2 — 신규 로드맵과 동반 구현 (로드맵이 데이터를 만듦)

5. **지표 convention-gate/shadow-parity 관측 화면** (C/P1). flip이 운영자 게이트라
   **UI 없이는 위험** — safe/gated 분류·parity delta·flip 준비도. P1과 동반 필수.
6. **walk-forward / 파라미터 민감도 시각화** (C/P3 + B). 스크립트 4종·Optuna 데이터가
   이미 산출됨 → 라우트+히트맵/OOS fold 차트. P3 vectorbt가 스윕을 가속하면 필수.
7. **백테스트-vs-라이브 divergence 추적** (B/C P3·P6). QuantConnect Reconciliation 벤치마크.
   **리테일 유일 best-in-class = 최대 차별화.** 기존 `/experiments` compare-paper의 상시화.
8. **가격차트 + 시그널/체결 마커** (A3/B). **lightweight-charts로 결정(§6)** — 캔들+
   `createSeriesMarkers`. Signals/Trades에서 "왜 이 시점에 진입" 직관.

### Tier 3 — 차별화·후행 (분류기·배선 선행 필요)

9. **regime 컬러 오버레이** (B/C P5). 분류기 이미 존재 → 거의 순수 프론트. 상용 부재 차별화.
10. **per-fill slippage / TCA** (B/C P6). 체결모델 정렬 이후. 리테일 우위 영역.
11. **상관 히트맵(drawdown-conditional) + 노출 시계열** (B). 다전략 성숙 후.
12. **프로모션 칸반 live 단계 명료화**(A8), **experiments 진행률**(A9), **trades 2소스 통합**(A10).

## 5. 제약 (기존 워크벤치 로드맵 계승)

- **Paper-safe 기본.** 라이브 주문 컨트롤 신규 추가 금지. `futures_live.enabled`/
  `futures:live:suspended` 우회 금지 (§ 워크벤치 Non-Negotiable).
- 주식 EOD 일괄청산 금지, 선물 long/short 대칭 유지, KST-only, Redis DB1+TTL.
- 신규 라우트보다 기존 대시보드 API 우선. Caddy `DASHBOARD_HOST_PORT` 뒤 단일 Next.js 앱.
- 신규 UI 상태는 `unknown/not_available`로 노출 (블로킹 예외 금지).
- **차트 라이브러리**: recharts는 캔들스틱/히트맵 부재 → Tier 2·3용 추가 필요. 상세 결정 §6.

## 6. 차트 라이브러리 결정 (리서치 완료)

Tier 2·3의 가격차트+마커·히트맵·underwater/밴드는 현 recharts로 불가. 후보를
**실제 스택(Next 16.1.6 / React 19.2.3 / TS5 / Tailwind v4)**에 대해 실측 비교.

### 6.1 비교 요약

| 라이브러리 | 캔들+마커 | 히트맵 | 밴드/underwater | React19/Next16 | 번들(min+gz) | 라이선스 | 유지보수 |
|---|---|---|---|---|---|---|---|
| **lightweight-charts v5** | **네이티브** (`createSeriesMarkers`) | ✗ | 부분(Area/Baseline) | ✓ React 결합 0, `use client`+`useEffect` | **61KB** | Apache-2.0 | v5.2.0(2026-04), 16.5k★ |
| **visx** (Airbnb) | ✗(프리미티브) | ✓ `@visx/heatmap` | ✓ `@visx/shape` Area y0/y1 | ✓ v4 peer `^18‖^19` 명시 | 모듈당 ~10-20KB | MIT | v4, 20.9k★ 활발 |
| ECharts | ✓ candlestick+markPoint | ✓ 네이티브 | ✓ markArea | ⚠ `echarts-for-react` 래퍼 **React19 미해결 이슈 3건**(#617/#628/#619) | ~360KB | Apache-2.0 | v6, 66.7k★ |
| Plotly.js | ✓ | ✓ | ✓ | ✓ react-plotly v4 `^19` | **1.33MB** (최대) | MIT | 활발, 무거움 |
| uPlot | 데모 플러그인 | 데모 플러그인 | 데모 플러그인 | 공식 React 래퍼 부재 | **21KB**(최소) | MIT | 10.3k★ |
| Nivo | ✗ | ✓ | 부분 | 미확인 | ~196KB | MIT | 느린 cadence |

(KLineChart도 검토 — 캔들 전용 40KB, 단 히트맵 부재·커뮤니티 얕음 → lightweight-charts 대체 이점 없음.)

### 6.2 결정: **lightweight-charts v5 + visx 2종 추가, recharts 유지**

**근거:**
- **요구 #1(캔들+체결마커, 최우선·TradingView 룩)은 lightweight-charts가 압도** —
  TradingView 자체 엔진, `createSeriesMarkers`가 가격+시점 체결마커 전용 API,
  React 결합 0(→ React 19.2.3 peer-dep 노출 없음), 61KB, 미해결 호환 이슈 없음, DX ~10-15줄.
- **단일 라이브러리 해법은 ECharts뿐이나 부적합** — 3요구를 한 패키지로 커버하지만
  `echarts-for-react` 래퍼에 **React 19 미해결 이슈 3건**(2026 현재 open) + 360KB +
  비-TradingView 스타일링 부담 → 두 번째 경량 lib 추가가 더 나은 트레이드오프.
- **visx가 히트맵(`@visx/heatmap`: 민감도/상관 그리드) + 밴드/underwater(`@visx/shape`
  Area y0/y1: Monte Carlo fan, regime 밴드) 갭을 채움** — React 18/19 peer 명시 해결,
  MIT, 모듈당 ~10-20KB.
- **recharts는 무변경** — 3.8.1 peer가 이미 React 19 지원 선언, 3종 공존 충돌 없음.
  기존 4개 단순차트 마이그레이션 ROI 없음.

### 6.3 통합 노트

- 설치: `npm i lightweight-charts` + `npm i @visx/heatmap @visx/shape @visx/scale @visx/group @visx/axis @visx/tooltip` (쓰는 서브모듈만).
- **lightweight-charts**: 래핑 컴포넌트 `"use client"`, `useEffect`에서 `createChart` →
  series → `createSeriesMarkers`. `window`/canvas를 마운트 후에만 만지므로 `next/dynamic
  {ssr:false}`는 **정합성엔 불필요**(useEffect가 이미 SSR-safe) — 단 61KB를 라우트 청크로
  분리하려면 `dynamic()` 래핑이 선택적으로 유용.
- **visx**: 순수 React/SVG, SSR-safe. 툴팁 hover 상호작용 필요한 곳만 `"use client"`.
- **코드 스플리팅**: 각 lib import를 해당 차트 컴포넌트/라우트에만 국한(공유 layout import
  금지) → shared 번들 팽창 방지, recharts-only 페이지 무영향.
- **미래 통합 옵션**: 훗날 recharts까지 흡수하려면 ECharts를 `echarts-for-react` 래퍼 없이
  직접 사용하는 길만 충분히 넓음 — 단 현재 액션 아님.

## 7. 다음 단계 (제안, 미실행)

- 이 리서치를 근거로 **워크벤치 로드맵 v2 섹션** 또는 별도 실행계획 작성 여부 결정.
- Tier 1은 신규 로드맵과 독립 → 즉시 착수 가능. Tier 2는 P1/P3에 동반 배치.
- 차트 라이브러리 스파이크: lightweight-charts 캔들+체결마커 PoC 1건 + visx underwater/
  히트맵 PoC 1건으로 Tier 2·3 실현성 검증.

---

> 근거 출처: 갈래 A는 `strategy-builder-ui/src` 실측(file:line 인용). 갈래 B는 웹 리서치
> (QuantConnect/pyfolio/QuantStats/IBKR/Portfolio Visualizer/Composer/Freqtrade/Hummingbot/
> OpenAlgo/StrategyQuant X/Build Alpha/vectorbt/pypbo 등, URL은 리서치 세션 기록). 갈래 C는
> `services/dashboard/routes/`·`scripts/`·`shared/indicators/engine/` 실측. §6 차트
> 라이브러리는 후보별 React19/Next16 호환·번들·유지보수 웹 실측 + package.json 스택 대조.
