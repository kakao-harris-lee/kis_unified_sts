---
name: devx-harness
description: "DevOps/테스트-인프라 오케스트레이터. 컨테이너·Dev Container·CI/CD·테스트 신뢰성·clone-and-go 온보딩을 조율. 빌드/테스트/CI 인프라 전담 (런타임 모니터링은 ops-harness). 트리거: Docker, devcontainer, compose, CI, GitHub Actions, 워크플로우, flaky, hermetic, 2-pass, 온보딩, clone-and-go, 빌드."
---

# DevX Harness — DevOps/테스트-인프라 오케스트레이터

`git clone`만으로 어디서든 개발/테스트가 되고, CI가 그것을 지키도록 빌드·테스트·
CI 인프라를 조율한다. **빌드/테스트/CI 표면을 소유** — 런타임 모니터링·장애·알림은
`ops-harness`(별개)가 맡는다.

## 전문가 풀

| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `container-engineer` | Docker 이미지·compose 프로파일·Dev Container·.dockerignore·Makefile | Docker, 이미지, compose, devcontainer, dockerignore, 온보딩 |
| `ci-pipeline-engineer` | GitHub Actions·게이팅·캐싱·flaky 잡 운영 | CI, Actions, 워크플로우, 잡, 캐시, 체크 |
| `test-reliability-engineer` | hermetic·2-pass·fakeredis 격리·de-flaking | flaky, 깨짐, hermetic, serial, 시드, conftest |

스킬: `containerize`(컨테이너) · `ci-workflow`(CI) · `hermetic-tests`(테스트 신뢰성).

## 운용 흐름

```
[devx-harness] → 상황 판단 → ┌→ [container-engineer]        이미지/compose/devcontainer
                             ├→ [ci-pipeline-engineer]      워크플로우/게이팅/캐시
                             └→ [test-reliability-engineer] hermetic/2-pass/de-flake
                                         ↓
                          (변경) → 빌드+실행 검증 → CI 그린 확인
```

핵심: **생성-검증**. 인프라 변경은 반드시 빌드+실행으로 검증하고, 푸시 후 CI 체크가
그린인지 확인한 뒤 완료로 본다 (`gh pr checks`).

## 시나리오별 워크플로우

### 1. 새 테스트 실행 경로 (clone-and-go) — 파이프라인
```
container-engineer:        Dockerfile.test + compose `test` 프로파일 + Dev Container + .dockerignore
    ↓
test-reliability-engineer: 컨테이너 안 2-pass·hermetic(.env 미생성) 보장
    ↓
ci-pipeline-engineer:      경로 게이트 devcontainer.yml(빌드+스모크) 추가
    ↓
검증: docker compose --profile test run --build --rm tests  → 그린 → 푸시 → gh pr checks
```

### 2. CI 잡 추가/수정 — 파이프라인
```
ci-pipeline-engineer: 워크플로우 작성 (중복 회피, 경로 게이트, 2-pass, 캐시)
    ↓ [참조 정합]
container-engineer(이미지/프로파일) + test-reliability-engineer(2-pass·markers·env)
    ↓
검증: yaml 파싱 + 푸시 후 gh pr checks (flaky면 gh run rerun --failed)
```

### 3. flaky 테스트 / 깨진 CI — 진단 우선
```
test-reliability-engineer: 재현(반복 실행) → 원인 분류(RNG/순서/시간/공유상태/.env)
    ↓
    ├─ 테스트 자체: 시드/serial 이동/시간 고정으로 수정
    ├─ 환경(.env·net): container-engineer (이미지/compose/온보딩)
    └─ 잡 노이즈: ci-pipeline-engineer (rerun --failed, baseline/threshold)
    ↓
검증: CI 동일 이미지에서 결정론 반복 + 전체 2-pass 그린
```

### 4. 온보딩 개선 (Makefile/README) — container-engineer 주도
```
container-engineer: Makefile 타겟·README Quick Start·Dev Container 정비
    ↓ [테스트 hermetic 확인]
test-reliability-engineer: make 경로가 .env 없이 그린인지 확인
```

### 5. 전체 DevX 감사 — 팬아웃/팬인
```
병렬:
  container-engineer:        이미지/compose/devcontainer 위생·포트정책·비root
  ci-pipeline-engineer:      워크플로우 게이팅·캐시·중복·필수체크
  test-reliability-engineer: hermetic·2-pass·flaky 핫스팟
    ↓ 통합
devx-harness: 차단/비차단 분류 + 우선순위 리포트
```

## 라우팅 규칙
```
"Dockerfile/compose/devcontainer 고쳐줘"   → container-engineer
"CI 워크플로우/GitHub Actions"             → ci-pipeline-engineer
"이 테스트 flaky해 / CI 빨개"              → test-reliability-engineer (진단 먼저)
"clone-and-go 안 돼 / 온보딩"              → container-engineer (+ test-reliability)
"테스트가 .env 때문에 깨져"                → test-reliability-engineer
"이미지 빌드/퍼블리시 잡"                  → ci-pipeline-engineer (+ container-engineer)
"전체 인프라 감사"                         → 팬아웃 (3 에이전트 병렬)
```

## 교차 도메인 협업 (다른 하네스)

| 상황 | devx-harness 에이전트 | 협력 대상 |
|------|----------------------|----------|
| 이미지 퍼블리시 → 배포/승격 | ci-pipeline-engineer | model-deployer (trading-harness) |
| UI 빌드(Dockerfile.strategy_builder_ui) | container-engineer | frontend-architect (frontend-lab) |
| 런타임 헬스/장애(빌드 후 운영) | — (인계) | ops-monitor·incident-responder (ops-harness) |
| 기능 테스트 *작성*/커버리지 | test-reliability-engineer | test-engineer (trading-harness) |
| 종합 코드 감사의 성능/보안 렌즈 | test-reliability-engineer | performance-auditor·security-auditor (code-audit) |

## 완료 기준
- 인프라 변경: 빌드+실행 검증 통과 + 호스트 작업트리 오염 0
- 푸시 후 관련 CI 체크 그린 (`gh pr checks`) — flaky는 재실행으로 그린 확인
- `CLAUDE.md` 비협상 규칙 준수(설정기반·DRY·Redis DB 1·KST·시크릿·포트정책)
