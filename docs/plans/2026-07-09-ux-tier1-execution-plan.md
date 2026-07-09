# UX Tier 1 실행계획 (2026-07-09)

> 근거 리서치: [2026-07-09-ux-improvement-research.md](2026-07-09-ux-improvement-research.md) §4 Tier 1
> 차트 결정: 위 문서 §6 — **visx 단일 추가, recharts 유지**
> 조사 기준: main `a299bb68`. 통합 지점은 아래 각 항목에 file:line으로 실측.

## 0. 범위와 원칙

Tier 1 = **데이터가 이미 존재하거나 저비용 파생 가능 + 신규 로드맵과 독립 → 즉시 착수**.
Tier 2·3(convention-parity 관측, walk-forward, divergence)은 P1/P3 로드맵에 데이터가
종속돼 별도 계획.

- **Paper-safe**: 라이브 주문 컨트롤 신규 금지. 읽기/네비게이션만.
- **기존 API 우선**: 신규 라우트는 T3(롤링 지표)에서만 불가피하게 검토.
- **차트는 visx**(신규) — 기존 recharts 4파일 무변경. 같은 SVG/React/Tailwind idiom.
- 각 항목 독립 PR. 게이트: `npm run lint && npm run build` + 해당 페이지 smoke.

## 1. 항목별 실행 계획 (실측 기반)

### T1-1. 크로스-엔티티 딥링크 (최고 레버리지, 단 실측상 재분류)

**리서치 가정**: "lineage 데이터 이미 반환 → `<Link>`만 붙이면 됨."
**실측 보정**: 데이터는 맞으나 **타깃 페이지가 id/query param을 받지 않음**.

- lineage는 이미 렌더됨: `DecisionTracePanel.tsx:428-433`
  (`trace.lineage.{signal_id,order_id,fill_id,position_id,trade_id}` — 전부 plain `<Field>`).
- `trades/page.tsx`·`positions/page.tsx`는 `useSearchParams`/param 수용 **0건**(grep 확인).

**작업**:
1. `/trades`·`/positions`에 `?highlight=<id>` 쿼리 수용 → 해당 행 스크롤+하이라이트
   (React Query 데이터에서 클라이언트 필터/스크롤; 신규 백엔드 불필요).
2. `DecisionTracePanel`의 lineage `<Field>`를 조건부 `<Link href=...>`로
   (id 존재 시만 링크, 없으면 현행 plain text 유지 — `unknown` 계약 보존).
3. 역방향: `/trades` 행 → 원 signal 트레이스 드로어 링크(선택, 2차).

**비용**: 중(리포트의 "저비용" 아님 — 타깃 페이지 param 배선 포함). **차트 무관.**
**게이트**: 딥링크 왕복(signal→trade→signal) 수동 확인 + 링크 없는 legacy 행 무크래시.

### T1-2. Underwater(수중) drawdown plot ✅ 확정 저비용

- 소스 확정: `riskApi.getEquityHistory({days}).points[].total_equity`
  (`risk/page.tsx:240-284`, `EquityCurveChart`가 이미 소비).
- underwater = `-100 * (running_max - equity) / running_max` — 프론트 파생, 신규 API 0.

**작업**: visx `@visx/shape` `AreaClosed`(y0=0, y1=drawdown%) 신규 컴포넌트
`UnderwaterChart`, `/risk` equity 곡선 하단에 배치. `/experiments` 리포트에도 재사용.
**비용**: 낮음. **visx 첫 도입 지점 → PoC 겸용.**
**게이트**: 빈 데이터/단일 포인트 empty-state + 알려진 MDD 구간과 육안 일치.

### T1-3. 롤링 리스크 지표 (rolling Sharpe/vol) — 실측상 데이터 갭 있음

**리서치 가정**: "이미 있는 일수익률로, 매우 낮음."
**실측 보정**: **일수익률 시계열 API 부재**(`src/lib/dashboard/api.ts`에 rolling/returns/
sharpe grep 0). equity 곡선만 존재.

**확정 방식 = (a) 프론트 파생** (§5 결정 1):
- `total_equity` 시계열 → 일수익률 → 롤링 창(예 20 거래일) Sharpe/vol. 신규 백엔드 0.
- 결측/휴장일은 연속 거래일 기준 창으로 처리(프론트). visx `LinePath`.
- 정확도/재사용 요구 커지면 백엔드 `/api/portfolio/rolling-stats`(b)로 승격 — 현재 액션 아님.

**비용**: 낮음~중. **리포트 "매우 낮음"은 일수익률 API가 있다는 가정이었으나 실측상 부재 →
프론트 파생 한 단계 추가.** 2차 PR, visx 재사용.

### T1-4. 명료성 수정 묶음 (소규모, 독립)

**T1-4a. `/event-context` asset_class 토글**
- 프론트 하드코딩: `event-context/page.tsx:463-467` (`asset_class:"futures"` 고정,
  queryKey도 `"futures"`).
- **서버는 이미 stock 지원**: `event_context.py:888` `asset_class` Query default futures,
  `:820` stock이면 `setup_c_not_applicable_to_stock` 블록. → 토글 추가하되 **stock은
  "Setup C 미적용" 정직 표기**(빈 화면 아님). `useAssetClass()`(다른 페이지 관례)로 배선.
- **비용**: 낮음.

**T1-4b. 색상관례 범례**
- 토큰 명확: `globals.css:11-12` `--color-profit:#ef4444`(상승=빨강)/`--color-loss:#3b82f6`(하락=파랑).
- PnL 표기 근처에 작은 범례/툴팁("빨강=상승·이익 / 파랑=하락·손실, 한국 관례"). HeaderBar
  또는 GlobalIndicators에 1회 노출.
- **비용**: 매우 낮음. **차트 무관.**

**T1-4c. 테마 토글**
- 현재 `prefers-color-scheme` 미디어쿼리만(`globals.css:57,268,320,375`), `next-themes` 부재.
- `next-themes` 도입 or CSS var + `class` 전략 + 토글 버튼(HeaderBar). 미디어쿼리를 `class`
  기반으로 전환하는 CSS 리팩터 수반.
- **비용**: 중(전역 CSS 전환). **Tier 1 중 가장 큼 — 후순위 or 분리 검토.**

## 2. 착수 순서 (의존성·리스크)

```
T1-2 underwater ──(visx 도입·PoC 겸)──▶ T1-3 rolling stats (visx 재사용)
T1-4b 색상범례 ─┐
T1-4a evt 토글 ─┼─ 독립 소규모, 병렬
T1-1 딥링크    ─┘ (백엔드 무관, 프론트 param 배선)
T1-4c 테마토글 ── 후순위 (전역 CSS, 단독 PR)
```

**권장 1차 PR 세트**: T1-2(visx 도입 겸) + T1-4b + T1-4a — 저위험·저비용·즉효.
**2차**: T1-1(딥링크, 중간 비용) + T1-3(롤링, 파생 방식 확정 후).
**분리**: T1-4c(테마) — 전역 CSS라 단독.

## 3. 리포트 대비 보정 요약 (실측으로 바뀐 것)

| 항목 | 리포트 | 실측 보정 |
|---|---|---|
| T1-1 딥링크 | "저비용, 데이터 있음" | 데이터 O, 단 **타깃 페이지 param 미수용** → 중간 비용 |
| T1-2 underwater | 저비용 | ✅ 확정 (`total_equity` 존재) |
| T1-3 롤링지표 | "매우 낮음" | **일수익률 API 부재** → 프론트 파생(a) 또는 백엔드(b) 결정 필요 |
| T1-4a evt 토글 | 커버리지 수정 | 서버 stock 지원 O, **단 Setup C는 stock N/A** 표기 필요 |
| T1-4c 테마 | 편의 수정 | 전역 CSS 미디어쿼리→class 전환 수반, Tier 1 중 최대 |

## 4. 게이트 (공통)

```bash
cd strategy-builder-ui && npm run lint && npm run build
# 신규/변경 페이지 smoke (quant-ops-workbench.smoke.test.tsx 패턴)
```
- vis?x 신규 컴포넌트는 empty/loading/degraded 상태 테스트 동반.
- 라이브 주문 컨트롤 미추가 확인(paper-safe 회귀).
- 딥링크는 link 없는 legacy 행에서 무크래시.

## 5. 결정 로그 (확정, 2026-07-09)

1. **T1-3 방식 = 프론트 파생(a)**. `total_equity` 시계열에서 일수익률→롤링창 계산,
   신규 백엔드 0. 결측/휴장일은 프론트에서 처리(연속 거래일 기준 창). 정확도/재사용
   요구가 커지면 백엔드 `/api/portfolio/rolling-stats`(b)로 승격 — 현재 액션 아님.
2. **T1-4c 테마 토글 = 별도 분리**. 전역 CSS 미디어쿼리→class 전환 리팩터가 수반돼
   Tier 1 중 비용 최대이고 성격이 달라 **단독 PR**로 분리, 1차 세트에서 제외.
3. **1차 PR 세트 = T1-2 + T1-4a + T1-4b**. underwater(visx 첫 도입 겸) + event-context
   asset 토글 + 색상관례 범례. 저위험·저비용·즉효. 딥링크(T1-1)·롤링(T1-3)은 2차.

**확정 실행 순서**:
- **1차 PR**: T1-2 + T1-4a + T1-4b (이 PR이 visx 도입을 확립 → 이후 재사용).
- **2차 PR**: T1-1 딥링크(타깃 페이지 param 배선 포함) + T1-3 롤링지표(프론트 파생, visx 재사용).
- **분리 PR**: T1-4c 테마 토글(전역 CSS class 전환, 단독).
