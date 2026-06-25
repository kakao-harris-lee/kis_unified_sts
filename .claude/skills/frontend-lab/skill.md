---
name: frontend-lab
description: "프론트엔드 개발 오케스트레이터. 단일 Next.js 앱(strategy-builder-ui) 화면/기능 개발: 아키텍처·디자인토큰 → 컴포넌트 구현 + 실시간 데이터 배선. '대시보드 화면', 'UI 추가', 'Cockpit', '프론트', 'Next.js 페이지' 요청 시. builder 기능은 strategy-builder 소유."
---

# Frontend Lab — 프론트엔드 개발 오케스트레이터

KIS Unified Trading Platform의 **단일 Next.js 16 앱(`strategy-builder-ui/`)** 개발을 조율하는 스킬.
Cockpit·트레이딩 대시보드 화면을 설계→구현→실시간 배선까지 일관되게 개발한다.
(`/builder`·`/execute` 노코드 빌더 기능은 `strategy-builder` 에이전트 소유 — 이 스킬은 구조/토큰만 공유)

## 언제 쓰나
- "대시보드 화면 추가/수정", "Cockpit UI 손봐줘", "새 Next.js 페이지", "프론트 컴포넌트"
- 실시간 데이터 표시/갱신, WebSocket 연동, React Query 캐시 이슈
- 디자인 토큰/반응형/모바일 패턴 작업
- (백엔드 API/데이터는 execution-specialist·data-engineer, 빌더 기능은 strategy-builder)

## 전문가 구성 (생성-검증 + 파이프라인)

| 에이전트 | 역할 | 단계 |
|---------|------|------|
| `frontend-architect` | App Router 구조·데이터 페칭 전략·디자인 토큰·빌드/배포 | Phase 1 (설계) |
| `ui-engineer` | Cockpit/대시보드 컴포넌트·반응형/모바일·스타일·차트 | Phase 2 (구현, 병렬) |
| `frontend-realtime-engineer` | WebSocket·React Query·API 클라이언트·액션/낙관적 업데이트 | Phase 2 (배선, 병렬) |

## 워크플로우

```
Phase 1: 설계                  Phase 2: 구현 (병렬)              Phase 3: 검증
┌─────────────────┐          ┌──────────────────────────┐    ┌──────────────────┐
│ frontend-architect│   ───→  │ ui-engineer              │    │ code-audit       │
│ - 라우트/구조     │         │  - 컴포넌트/스타일/반응형 │ →  │ (style/arch      │
│ - 데이터 페칭 전략│         ├──────────────────────────┤    │  auditor) +      │
│ - 디자인 토큰     │         │ frontend-realtime-engineer│    │ 빌드/타입체크    │
│ - 빌드/배포 영향  │         │  - WebSocket/RQ/API 배선  │    │                  │
└─────────────────┘          └──────────────────────────┘    └──────────────────┘
```

## 시나리오별 워크플로우

### 1. 신규 대시보드 화면 (풀 파이프라인)
```
frontend-architect: 라우트 구조 + RSC/CSR 판단 + 토큰 + 데이터 흐름 설계
    ↓
ui-engineer + frontend-realtime-engineer (병렬):
  - ui-engineer: 컴포넌트/반응형/스타일 구현
  - frontend-realtime-engineer: hook/WebSocket/React Query 배선
    ↓
code-audit (style/architecture-auditor): 프론트 감사 + npm run build/타입체크
```

### 2. 기존 화면 UI 수정
```
ui-engineer 단독 (필요 시 frontend-architect 토큰 확인)
```

### 3. 실시간 데이터/상태 이슈
```
frontend-realtime-engineer: WebSocket/React Query invalidation 진단·수정
    ↓ (백엔드 계약 변경 필요 시)
execution-specialist / data-engineer: API/채널 정합
```

### 4. 디자인 시스템/토큰 변경
```
frontend-architect: 토큰 정의 변경
    ↓
ui-engineer: 영향 컴포넌트 일괄 반영
```

## 품질 게이트 (공통)
- **단일 앱 유지**: 모든 UI는 `strategy-builder-ui/`. 새 SPA 분기 금지 (Next.js 통합 완료 상태)
- **토큰 우선**: 색상/간격/타이포는 `globals.css` 토큰. 하드코딩 금지. 한국 관습(상승=빨강/하락=파랑) 준수
- **포트 규약**: 외부 `DASHBOARD_HOST_PORT`(paper/local 5081) → Caddy 내부 5080 → Next 3100, FastAPI 8001 API-only. host 3000 사용 금지(별도 프로젝트)
- **실시간 단일 채널**: `/ws` WebSocket → React Query invalidation. SSE/폴링 추가 금지
- **표현/로직 분리**: 컴포넌트는 hook 소비, 비즈니스 로직은 백엔드
- **파괴적 액션 안전**: 킬스위치/stop은 확인 플로우(모바일 slide-to-confirm) 뒤에서만
- **빌드 검증**: `npm run build`(next build) 통과, 타입체크 통과, `--legacy-peer-deps` 인지

## 다른 하네스와의 경계
- **strategy-builder**: `/builder`·`/execute` + `components/builder/` + 빌더 hooks/인증 소유. frontend-lab은 구조/토큰만 공유, 빌더 기능 침범 금지
- **code-audit**: 프론트 구조/스타일은 architecture/style-auditor가 감사 (frontend-lab이 호출)
- **백엔드(execution-specialist/data-engineer)**: 프론트가 소비하는 API/실시간 데이터 계약 소유
- **글로벌 `frontend-design` 스킬**: 비주얼 디자인 품질이 필요할 때 보조 활용 가능 (프로젝트 토큰·관습 우선)
