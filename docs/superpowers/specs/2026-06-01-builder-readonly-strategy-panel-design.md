# 빌더 — 운용 전략 읽기 전용 패널 (Read-only Active-Strategy Panel)

- **작성일**: 2026-06-01
- **상태**: 설계 승인됨 (구현 계획 대기)
- **관련**: `docs/superpowers/specs/2026-06-01-futures-strategy-builder-design.md` (선물 빌더), `docs/STRATEGY_BUILDER_UI.md`

---

## 1. 배경 & 목표

선물 빌더(Phase 1) 추가 후, "현재 운용 중인 선물 전략이 빌더와 동기화되어 있나?"라는 질문에서 출발했다.
조사 결과 **기존 손작성 전략(Setup A/C, williams_r, mean_reversion 등)은 빌더의 조건 모델(`BuilderState`)로
충실히 표현·편집할 수 없다** — 코드 기반 entry 클래스(regime gate, 다중-bar 상태, 외부 스크리너 의존 등)이기
때문이다. 따라서 편집형 양방향 import는 비목표다.

대신 **운용 중인 전략을 빌더 화면에 읽기 전용으로 표시**하여, 빌더로 만든 전략과 손작성 전략을 한 화면에서
볼 수 있게 한다. 특히 **빌더로 구성 불가능한 코드 전략은 읽기 전용으로 어떤 전략이 enabled(활성)인지 표시**한다.

### 핵심 사실 (조사 결과)
- `GET /api/strategies`(`services/dashboard/routes/strategies.py`)가 이미 `ConfigLoader.load_all_strategies(asset_class, enabled_only)`로 `config/strategies/{stock,futures}/`를 열거하고 `StrategyInfo`(name, asset_class, enabled, entry_type, exit_type, position_type, description)를 반환한다. `enabled_only` 파라미터 지원.
- 프론트엔드에 이미 클라이언트(`strategy-builder-ui/src/lib/dashboard/strategies.ts`, `list({asset_class, enabled_only})`)와 훅(`src/hooks/dashboard/useStrategies.ts`)이 있다.
- 빌더가 현재 보여주는 것: KIS 프리셋 템플릿(`/api/kis-builder/strategies`), 등록된 빌더 산출물(`/api/kis-builder/registered` → `config/strategies/built/`), 로컬 드래프트. **`config/strategies/{stock,futures}/`의 손작성 전략은 빌더에 표시되지 않는다.**
- `entry_type == "builder_v1"`이면 빌더 산출 전략(조건 기반), 그 외는 코드 전략.

→ **사실상 프론트엔드 표시 전용 작업**(백엔드 변경 없음 또는 최소).

---

## 2. 스코프 & 비목표

### 대상 (In Scope)
- `/builder`에 **"운용 전략" 읽기 전용 패널** 추가 — `/api/strategies`를 호출해 런타임 레지스트리 전략을 나열.
- **빌더 자산군 토글 연동**: 선물 모드 → 선물 전략, 주식 모드 → 주식 전략(`?asset=`).
- 각 항목에 **enabled 배지(● 활성 / ○ 비활성)** + entry/exit 타입.
- **빌더 전략 vs 코드 전략 구분**: `entry_type == "builder_v1"` → "빌더 전략" 배지; 그 외 → "코드 전략 · 읽기 전용" 배지.
- 코드 전략 클릭 시: 타입·파라미터 요약 등 **읽기 전용 상세**만 표시 (빌더 캔버스로 로드/편집 불가).

### 비목표 (Out of Scope)
- ❌ 코드 전략을 `BuilderState`로 변환/편집 (표현 불가 — Setup A/C·RL·다중-bar 상태·외부 스크리너 의존).
- ❌ 패널에서 전략 enable/disable 토글 (읽기 전용; 활성화는 기존 `/api/kis-builder/registered/{id}/enable` 또는 CLI/운영 경로 유지).
- ❌ 새 백엔드 엔드포인트 (기존 `/api/strategies` 재사용).
- ❌ 손작성 전략을 빌더 산출물(`built/`)로 마이그레이션.

---

## 3. 설계

### A. 데이터 흐름 (백엔드 변경 없음)
```
빌더 자산군 토글(selected: stock|futures)
  → strategiesApi.list({ asset_class: selected, enabled_only: false })
  → GET /api/strategies?asset_class=<selected>&enabled_only=false
  → StrategyInfo[] (name, asset_class, enabled, entry_type, exit_type, position_type, description)
  → 읽기 전용 패널 렌더 (React Query)
```
- `enabled_only=false`로 호출해 활성/비활성 모두 받아 상태를 구분 표시한다.
- 자산군 토글이 바뀌면 재조회(React Query key에 asset 포함).

### B. UI — `ActiveStrategiesPanel` (신규 컴포넌트)
- 위치: `/builder` 좌측 영역(프리셋·저장 전략 목록과 같은 컬럼)의 collapsible 섹션, 제목 "운용 전략".
- 각 항목 행:
  - 전략명 (+ description 툴팁/보조 텍스트)
  - **enabled 배지**: 활성(● 초록) / 비활성(○ 회색)
  - 종류 배지: "빌더 전략"(entry_type=builder_v1) 또는 "코드 전략 · 읽기 전용"
  - entry/exit 타입 (작은 모노스페이스 텍스트)
- 빈/오프라인 처리: 대시보드 API 미응답 시 조용히 빈 목록 + 안내 문구(기존 프리셋 로드 패턴과 동일).
- 정렬: enabled 우선 → 이름.

### C. 빌더 전략 vs 코드 전략
- `entry_type === "builder_v1"`:
  - "빌더 전략" 배지. (Phase 1에서는 **표시만**; 캔버스 로드/편집 연계는 별도 후속 — registered 목록이 이미 담당.)
- 그 외(코드 전략):
  - "코드 전략 · 읽기 전용" 배지. 클릭 → 읽기 전용 상세(전략명, asset_class, entry/exit/position 타입, enabled). **편집·로드 액션 없음.**
  - "빌더로 편집 불가 (코드 전략)" 안내 문구.

### D. 정직성 가드
- 코드 전략 항목에는 편집/로드 버튼을 노출하지 않는다(읽기 전용임을 UI로 강제).
- 코드 전략을 클릭해도 빌더 상태(`BuilderState`)를 변경하지 않는다.

### E. 컴포넌트 경계
- `ActiveStrategiesPanel.tsx` (신규): props로 현재 asset(`"stock"|"futures"`)을 받아 `useActiveStrategies(asset)`로 데이터 조회 → 렌더. 단일 책임(표시), 빌더 상태와 독립.
- `useActiveStrategies(asset)` 훅: 기존 `strategiesApi.list` + React Query 래핑(없으면 추가).
- `/builder` page에서 `builder.state.assetClass`를 패널에 전달.

---

## 4. 테스트
- **프론트(타입/빌드)**: `npx tsc --noEmit` + `npm run lint` + `npm run build`.
- **컴포넌트 동작(가능 시)**: 패널이 enabled/disabled 배지, "빌더 전략"/"코드 전략 · 읽기 전용" 구분, entry/exit 타입을 올바로 렌더. 코드 전략 행에 편집/로드 액션이 없음. (프론트 단위 테스트 러너가 없으면 타입체크 + 수동 스모크로 대체.)
- **백엔드**: 신규 없음. 기존 `/api/strategies`(`tests/.../test_*` ) 커버. `enabled_only=false`가 비활성 전략도 반환하는지 한 줄 확인(필요 시 기존 테스트 보강).

---

## 5. 수용 기준
- [ ] `/builder`에 "운용 전략" 읽기 전용 패널이 보인다.
- [ ] 자산군 토글에 따라 선물/주식 전략 목록이 바뀐다.
- [ ] 각 전략의 **enabled 여부가 배지로 표시**된다(활성/비활성).
- [ ] `builder_v1` 전략은 "빌더 전략", 그 외는 "코드 전략 · 읽기 전용"으로 구분된다.
- [ ] 코드 전략은 편집/로드 액션이 없고 클릭 시 읽기 전용 상세만 보인다.
- [ ] 백엔드 신규 엔드포인트 없음(기존 `/api/strategies` 재사용).
- [ ] `npm run build` 그린, 기존 기능 회귀 없음.

---

## 6. 리스크
| 리스크 | 완화 |
|--------|------|
| 코드 전략을 편집 가능한 것으로 오인 | "읽기 전용" 배지 + 편집/로드 액션 미노출 + 안내 문구 |
| `/api/strategies` 미응답(대시보드 오프라인) | 조용히 빈 목록 + 안내(기존 프리셋 로드 패턴) |
| enabled_only 기본값이 활성만 반환 | 명시적으로 `enabled_only=false` 전달 |
| 자산군 토글과 패널 비동기 | React Query key에 asset 포함하여 재조회 |
