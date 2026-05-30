---
name: code-audit
description: "종합 코드 감사 오케스트레이터 (fan-out/fan-in). 아키텍처·보안·성능·스타일 4개 감사관을 병렬 실행하고 review-synthesizer가 단일 리포트로 통합. '종합 리뷰', '전체 감사', '코드 감사', '보안+성능+아키텍처 점검' 요청 시."
---

# Code Audit — 종합 코드 감사 오케스트레이터

코드(diff / PR / 경로)를 **4개 전문 렌즈로 병렬 감사**하고, 결과를 **하나의 우선순위 리포트로 통합**하는
fan-out/fan-in 하네스. 단일 PR 게이트 리뷰(`code-reviewer` + `/code-review` 스킬)와 달리, 이 스킬은
**여러 전문 감사관의 깊이 있는 다중 관점 감사**를 한 번에 수행한다.

## 언제 쓰나
- "종합 코드 리뷰 / 전체 감사 / 코드 감사 해줘"
- "아키텍처·보안·성능·스타일 같이 점검해줘"
- 큰 변경/릴리스 전 심층 다중 렌즈 감사
- (단순 PR 1건 게이트 리뷰는 `code-reviewer` / `/code-review` 스킬 사용)

## 팀 구성 (생성-검증 + 팬아웃/팬인)

| 에이전트 | 렌즈 | 단계 |
|---------|------|------|
| `architecture-auditor` | 레이어 경계·의존성·패턴·DRY·god-object | 병렬 감사 |
| `security-auditor` | 인젝션·시크릿·입력검증·인증·자금경로 | 병렬 감사 |
| `performance-auditor` | hot path·캐싱·쿼리·메모리·레이턴시 | 병렬 감사 |
| `style-auditor` | 포맷·타입·docstring·네이밍·매직넘버 | 병렬 감사 |
| `review-synthesizer` | 중복제거·심각도정규화·우선순위·차단판정·단일 리포트 | 통합 (fan-in) |

## 워크플로우

```
                        ┌─ architecture-auditor ─┐
[code-audit]            ├─ security-auditor ──────┤
  범위 결정  ──fan-out──┤                          ├──fan-in──→ review-synthesizer ──→ 단일 리포트
 (diff/PR/경로)         ├─ performance-auditor ───┤
                        └─ style-auditor ─────────┘
              (4개 병렬, 서로 독립 / 같은 범위 입력)        (중복제거·정렬·차단판정)
```

### Phase 1: 범위 결정
- **diff 모드**: `git diff`(working tree) 또는 staged — 진행 중 작업
- **PR 모드**: `gh pr diff <N>` — 특정 PR
- **경로 모드**: 지정 디렉토리/모듈 전체 (예: `shared/execution/`)
- 범위를 4개 감사관 모두에게 **동일하게** 전달

### Phase 2: 병렬 감사 (fan-out)
4개 감사관을 **하나의 메시지에서 동시 dispatch** (Agent 도구 병렬 호출). 각 감사관:
- 자기 렌즈에만 집중 (렌즈 간 침범 금지)
- 변경 범위 우선, 기존 부채는 pre-existing으로 표기
- 구조화 발견 목록 반환: `{severity, dimension, location, finding, recommendation, confidence}`

### Phase 3: 통합 (fan-in)
`review-synthesizer`가 4개 결과를 받아:
- 동일 위치·동일 근본원인 중복 병합 (복수 렌즈 = 신뢰도 상향)
- 심각도 정규화 (자금/주문경로·hot path·시크릿 상향)
- CRITICAL→HIGH→MEDIUM→LOW 정렬 + 차단/비차단 판정
- 단일 리포트 출력

### Phase 4: 후속 (선택)
- 차단 항목 → 담당 에이전트로 수정 위임 (`refactorer`, `execution-specialist`, `data-engineer`, `strategy-architect` 등)
- 수정 후 해당 렌즈만 재감사 (부분 재실행)

## 모델 선택 (비용/속도)
- 감사관 4종: 표준 모델(sonnet) 병렬 — 판단·코드 이해 필요
- 대규모 경로 모드: 감사관별로 하위 파일셋 분할 dispatch 후 렌즈별 1차 통합 → synthesizer 최종 통합
- synthesizer: 표준~고성능 (교차검증·우선순위 판단)

## 거짓 양성 정책 (synthesizer 강제)
- linter/typechecker/compiler가 잡을 단순 항목은 LOW로 강등 (CI가 처리)
- 변경하지 않은 라인의 기존 이슈는 pre-existing으로 분리
- 단일 렌즈·저신뢰·검증불가 → "참고"로 강등
- 의도적으로 silenced된 항목(lint ignore, 안전 주석, 테스트 픽스처)은 제외

## 품질 기준
- 모든 발견에 `파일:라인` 인용
- CRITICAL/HIGH는 영향 + 권장 조치 + 담당 제안 필수
- 차단 판정에 명확한 사유
- 리포트는 간결하게 (군더더기 없는 실행 가능 항목)

## 다른 하네스와의 경계
- **code-reviewer / `/code-review` 스킬**: 단일 PR 게이트(머지 직전 CLAUDE.md 준수 + 명백 버그). 가볍고 빠름
- **code-audit (이 스킬)**: 다중 렌즈 심층 감사 + 통합 리포트. 무겁고 포괄적
- 둘은 보완 관계 — 일상 PR은 code-reviewer, 큰 변경/릴리스/요청 시 code-audit
