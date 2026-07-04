# 전략 빌더 흐름 세로 깔때기 재구성 — Design Spec

- **작성일**: 2026-06-02
- **대상**: `strategy-builder-ui` `/builder` 페이지
- **출처 아이디어**: `docs/plans/archive/2026-06-01-improve-ux.md` (Method A — 수직 피드형 깔때기 파이프라인). 본 스펙은 그 아이디어를 현 아키텍처에 맞게 재정의한 것이다.
- **상태**: 승인됨 (브레인스토밍 합의 완료)

---

## 1. 배경 & 목적

현 `/builder`는 우측 패널의 **5단계 가로 스텝퍼**(지표 → 진입 → 청산 → 리스크 → 정보)로 전략을 조립한다. 페이퍼 등록은 좌측 "내 전략" 리스트의 3-dot 메뉴에 분리돼 있고, 등록 피드백은 native `alert()`이며, 등록 후 다음 단계(활성화·모니터링) 안내가 없다.

원본 지시서(`2026-06-01-improve-ux.md`)는 "수직 피드형 깔때기" UX를 제안하지만, 백엔드 가정(Next.js Route Handler가 `python3 backtest.py` spawn, Redis `backtest:status`, SSE)은 현 아키텍처(FastAPI + `sts` CLI + WebSocket `/ws`, 비동기 job queue 없음)와 맞지 않는다.

**목적**: 지시서의 *UX 아이디어*(전체 파이프라인을 한눈에 보는 세로 깔때기 흐름, 명확한 실행/피드백)만 취해, 현 아키텍처·정책 안에서 빌더 흐름을 재구성한다.

### 통증점 (현행)

1. 가로 스텝퍼가 한 번에 한 단계만 노출 → 전체 파이프라인을 한눈에 못 본다.
2. 등록이 "저장 → 좌측 리스트에서 찾기 → 3-dot 메뉴"로 분절·매몰된다.
3. 등록 피드백이 `alert()` (toast 아님).
4. 등록 후 enable → 모니터링 경로 안내가 없다.
5. 작성 중인 draft를 바로 등록할 수 없다(먼저 localStorage 저장 필요).

---

## 2. 범위 (Scope)

**프론트엔드 전용 재구성.** 백엔드·API·런타임·전략 엔진 변경 없음.

### 그대로 재사용 (변경 없음)

- 엔드포인트: `register-paper`, `registered` (GET), `preview-code`, 프리셋/지표 카탈로그 (`registered/{id}/enable`은 존재하나 본 스펙에서 호출하지 않음 — §5.4)
- 상태/훅: `useStrategyBuilder` 리듀서, `useLocalStrategies`
- 컴포넌트: `IndicatorSelector`, `ConditionBuilder`, `RiskManager`, `MetadataEditor`, `PreviewPanel`, `ActiveStrategiesPanel`, `FileDropZone`
- API 클라이언트: `registerPaperStrategy`, `listRegisteredStrategies`, `listKisBuilderPresets`, `previewCodeFromState`

### 변경

- `strategy-builder-ui/src/app/builder/page.tsx` — 가로 스텝퍼 + 다음/이전 네비 제거, 세로 깔때기 피드로 재구성
- `strategy-builder-ui/src/components/builder/CustomStrategyList.tsx` — `alert()` → toast 교체 (액션바와 동일한 등록 피드백 경로 공유)
- `strategy-builder-ui/src/components/builder/index.ts` — 신규 컴포넌트 export 추가
- **테스트 인프라 추가**: `strategy-builder-ui`에 테스트 러너가 없으므로 vitest + React Testing Library + jsdom를 스캐폴딩한다(`package.json` test 스크립트, `vitest.config.ts`, `vitest.setup.ts`). 프론트엔드 dev-tooling 한정 변경.

### 신규 컴포넌트 (3개)

- `FunnelStage` — 스테이지 래퍼 카드
- `StageRail` — 좌측 세로 미니레일(진행 인디케이터 + 스크롤 점프)
- `BuilderActionBar` — 하단 스티키 액션 바(저장 + 페이퍼 등록)

---

## 3. 레이아웃

데스크탑 3-컬럼 그리드(`grid lg:grid-cols-3`)를 유지하되 중앙을 스텝퍼 대신 세로 피드로 바꾼다.

```
┌──────────────────────────────────────────────────────────┐
│  전략 빌더            [주식/선물]         [● 프리뷰 토글]   │
├────────┬──────────────────────────────────┬──────────────┤
│ 좌 패널 │  중앙: 세로 깔때기 피드            │  우: 프리뷰    │
│ (기존)  │                                  │  (스티키)     │
│ ·기본  │  [StageRail]│ ▼ 1 전략 정보  ✓   │  YAML/Python │
│  전략  │   ① 정보    │ ──── 커넥터 ────    │  미리보기     │
│ ·내 전략│   ② 지표 ✓  │ ▼ 2 지표       ✓   │  (PreviewPanel│
│ ·Active│   ③ 진입 ⚠  │ ──────────         │   재사용)     │
│  전략  │   ④ 청산 ✓  │ ▼ 3 진입 조건  ⚠   │              │
│        │   ⑤ 리스크✓ │ ▼ 4 청산 조건  ✓   │              │
│        │             │ ▼ 5 리스크 관리 ✓  │              │
├────────┴─────────────┴────────────────────┴──────────────┤
│  [저장]                      [페이퍼로 등록 →]            │  ← BuilderActionBar (스티키)
└──────────────────────────────────────────────────────────┘
```

- **모바일**: 좌 패널은 상단/하단으로 흐르고, 프리뷰는 기존 토글 패턴(`showPreview`) 유지. 피드는 자연 세로 스크롤. `StageRail`은 모바일에서 숨김(`hidden lg:block`) — 스크롤이 곧 네비.
- **스테이지 순서**: 정보 → 지표 → 진입 → 청산 → 리스크. (실제 데이터 흐름 방향: 정의 → 빌딩블록 → 진입 시그널 → 청산 시그널 → 리스크 게이트.)

---

## 4. 컴포넌트 설계

### 4.1 `FunnelStage` (신규)

스테이지 하나를 감싸는 래퍼 카드.

- **Props**: `id`(anchor용), `stepNum`, `title`, `status: "complete" | "warning" | "empty"`, `children`, `showConnector?: boolean`
- **렌더**: 제목 행(스텝 번호 + 라벨 + status chip) + `children`(기존 섹션 컴포넌트) + 하단 깔때기 커넥터(`showConnector`면 좁아지는 시각 요소)
- **status chip**: ✓완료(emerald) / ⚠경고(amber) / 비어있음(slate) — 현 `getStepStatus` 색상·아이콘 규칙 재사용
- **anchor**: `id={`stage-${id}`}` + `scroll-mt`(스티키 헤더 보정)으로 `StageRail` 점프 타겟

### 4.2 `StageRail` (신규)

좌측 세로 미니레일. 현 가로 `<nav role="tablist">` + 다음/이전 버튼 + Alt+화살표 키내비를 대체.

- **Props**: `stages: { id, stepNum, shortLabel, status }[]`, `activeId`, `onJump(id)`
- **동작**: chip 클릭 → 해당 `FunnelStage`로 `scrollIntoView({ behavior: "smooth", block: "start" })`
- **active 추적**: `IntersectionObserver`로 현재 뷰포트 상단 스테이지를 active로 하이라이트 (선택적; 단순 클릭 점프만으로도 1차 충족 가능)
- **접근성**: `<nav aria-label="전략 빌더 단계">`, 각 chip은 `<a href="#stage-...">` 또는 버튼 + `aria-current`

### 4.3 `BuilderActionBar` (신규)

하단 스티키 액션 바. 현행 스텝 네비 푸터(다음/이전/저장하기)와 좌측 리스트의 등록 액션을 하나로 통합.

- **Props**: `isValid`, `validationErrors: string[]`, `assetClass`, `onSave()`, `onRegister()`, `registering: boolean`, `lastRegistered?: { name } | null`
- **버튼**:
  - `[저장]` (secondary) → `onSave` = `localStrategies.save(builder.state)` + 성공 toast
  - `[페이퍼로 등록 →]` (primary) → `onRegister` = `registerPaperStrategy({ builder_state: builder.state })`
  - 두 버튼 모두 `!isValid` 시 disabled + 사유 툴팁(`validationErrors`)
- **등록 후**: dismissible 안내 카드(§5) 표시

---

## 5. 데이터 흐름 & 등록 UX (핵심 개선)

`useStrategyBuilder` 상태는 불변. 액션바에서 두 갈래로 분기한다.

### 5.1 저장 (localStorage)

기존과 동일: `localStrategies.save(builder.state)` → 좌측 "내 전략" 리스트에 반영.

### 5.2 페이퍼 등록 (현재 draft 직접 등록)

- `registerPaperStrategy({ builder_state: builder.state })` 호출 — **저장 → 리스트에서 찾기 단계를 우회**해 작성 중 draft를 바로 등록
- 성공 시 `listRegisteredStrategies()` 재조회 → 좌측 "등록됨" 배지 동기화
- 백엔드는 `config/strategies/built/<id>.yaml`을 `enabled: false`로 생성 (현행 그대로)

### 5.3 등록 피드백 (alert → toast + 안내)

- `CustomStrategyList`와 `BuilderActionBar` 모두 `useToast` 사용, `alert()` 제거
- **성공 toast + dismissible 안내 카드**(액션바 위)에 3단계 다음 행동 명시:
  1. `'X' 전략이 페이퍼에 등록되었습니다 (비활성 상태)`
  2. `활성화는 운영자 작업입니다 — orchestrator 재적용 후 반영됩니다`
  3. `체결·포지션은 대시보드(/)에서 모니터링하세요`
- 실패 시 `toast.error(메시지)`

### 5.4 enable 토글은 범위 외

Phase 1 paper-only + 수동 enable 정책을 준수한다. UI는 "안내"만 제공하고 in-UI 활성화 버튼은 추가하지 않는다. (`registered/{id}/enable` 엔드포인트는 존재하나, 활성화는 운영자 판단 + orchestrator 재적용이 필요하므로 빌더 화면에서 토글하지 않는다.)

---

## 6. 검증 & 에러 처리

- **스테이지별 status chip**: 현 `getStepStatus` 로직 유지 (metadata.name, indicators>0, entry/exit conditions>0, risk 토글 중 하나).
- **액션바 게이트**: `builder.isValid`(이름 + 진입 ≥1 + 청산 ≥1)가 false면 저장·등록 버튼 disabled.
- **검증 실패 피드백**: 등록/저장 시 누락 항목을 toast로 표시하고, 첫 미충족 스테이지로 자동 스크롤(`StageRail.onJump`).
- **stale 요청 가드**: 등록 중 중복 클릭 방지(`registering` 플래그), 기존 `pythonRequestRef` 패턴과 동일한 사상.

---

## 7. 테스트 & 검증

테스트 러너로 **vitest + React Testing Library + jsdom**를 신규 도입한다(§2). TDD로 작성:

- `computeStageStatuses` / `firstIncompleteStageId` (순수 함수): status 매핑, 첫 미충족 스테이지.
- `FunnelStage`: status별 chip 렌더, 커넥터 표시, anchor id.
- `StageRail`: stages → chip 매핑, `onJump` 호출.
- `BuilderActionBar`: invalid → 버튼 disabled, `onSave`/`onRegister` 호출, 등록 중 disabled, 안내 카드 렌더.
- `CustomStrategyList`: `registerPaperStrategy` mock 성공/실패 → `alert()` 대신 toast 호출.

**페이지 통합(`page.tsx`)**은 RTL 풀 통합 대신 `tsc --noEmit` + `eslint` + `next build` + 수동 브라우저 확인으로 검증한다(API/Provider 모킹 비용 대비 실익 낮음).

---

## 8. 범위 외 (Out of Scope)

- 백테스트 실행 버튼 (Phase 5: 백테스트 CLI 전용)
- SSE / 실시간 `● Process` 인디케이터 (비동기 job queue 없음)
- 신규 백엔드 엔드포인트 / Route Handler에서 Python spawn
- LLM Screener 스테이지 추가 (현 빌더는 지표 조건 조립 도구 — 추상화 레벨 불변)
- in-UI enable 토글 (§5.4)

---

## 9. 수용 기준 (Acceptance Criteria)

- [ ] `/builder` 중앙이 세로 깔때기 피드로 렌더되고, 5개 스테이지가 한 화면 스크롤로 모두 접근 가능하다.
- [ ] 좌측 `StageRail` chip 클릭 시 해당 스테이지로 스무스 스크롤되고 status가 색상으로 표시된다.
- [ ] 하단 스티키 액션바에서 작성 중 draft를 **저장 없이 바로** 페이퍼 등록할 수 있다.
- [ ] 등록 성공/실패가 toast로 표시되고(`alert()` 제거), 성공 시 등록→활성화→모니터링 3단계 안내가 노출된다.
- [ ] `isValid`가 false면 저장·등록 버튼이 비활성이고 사유가 안내된다.
- [ ] 프리뷰(YAML/Python), import/export, 프리셋/내 전략/Active 패널이 기존대로 동작한다.
- [ ] 모바일에서 프리뷰 토글이 유지되고 피드가 세로 스크롤된다.
- [ ] `npm run build` / lint / 신규·회귀 테스트 통과.
