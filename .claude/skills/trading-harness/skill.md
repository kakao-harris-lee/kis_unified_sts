---
name: trading-harness
description: "KIS Unified Trading Platform 통합 오케스트레이터. 지표 전략 개발, RegimeGate 검증, 노코드 빌더, Paper→Live 승격, 코드 유지보수(테스트·리팩토링), 운영/모니터링, 빌드/테스트/CI 인프라(DevX). 전문가 풀에서 적절한 에이전트를 선택하여 라우팅한다. 리뷰·심판·차단 판정·계획 검토는 이 스킬 소관이 아니다 — `codex-gate`로 간다."
---

# Trading Harness — 통합 전문가 풀 오케스트레이터

KIS Unified Trading Platform의 전략 개발, RegimeGate 검증, 전략 승격, 코드 유지보수, 운영/모니터링을 포괄하는 전문가 팀을 조율한다.
운영 1차 방향은 **지표 기반 전략(Williams %R/RSI/MACD) + RegimeGate + Setup A/C**이며,
RL_mppo는 deprecate(2026-05-15)되어 재학습 옵션으로만 보존된다.

**심판(adjudication)은 Codex 레인이 소유한다 (2026-08-11).** Claude가 만든 산출물을 Claude가 승인하는 자기 승인을 막고
다른 모델 계열의 독립 심판을 확보하기 위해, 코드 심판과 계획 심판은 `codex-reviewer` / `codex-plan-reviewer`가 소유한다.
Claude 4렌즈 감사관은 **증거 생성**을 담당하며, 심각도 정규화·차단 판정·최종 리포트는 Codex가 낸다.
계획 *저작*은 기존 Claude 경로 그대로다 — 달라지는 건 완성된 계획이 심판 게이트를 통과해야 실행에 착수한다는 점뿐이다.
리뷰 산출물은 `.omc/review/{YYYYMMDD-HHMMSS}/`에 남긴다
(렌즈 증거 `evidence/{lens}.md`, 심판 결과 `verdict.md` — verdict는 `evidence/` 밖이며 심판 focus는 `evidence/`만 지목한다).

## 전문가 풀 (29명 — 심판 2명은 전역 `~/.claude/agents/` 소속)

### 전략 개발 팀
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `strategy-architect` | 전략 설계/구현 | 새 전략, 진입/청산 로직, YAML 설정, 레지스트리 |
| `indicator-specialist` | 지표 시그널 리서치 | 지표, Williams %R, RSI, MACD, StochRSI, consensus, RL 재학습 |
| `regime-gate-analyst` | RegimeGate 검증 | RegimeGate, 레짐, head-to-head, counterfactual, 게이트 |
| `strategy-builder` | 노코드 빌더 | builder, 빌더, builder_v1, 노코드, 빌더 UI |
| `backtest-engineer` | 백테스트/최적화 | 백테스트, Optuna, MLflow, 성과 분석, holdout |

### 전략/모델 승격 팀
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `model-evaluator` | 전략/모델 평가/비교 | 평가, 비교, A/B, 승격 판정, Sharpe |
| `model-deployer` | 배포/승격/롤백 | 배포, deploy, Paper→Live, Phase 5 게이트, 롤백 |

### 심판 팀 (Codex 독립 심판)
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `codex-reviewer` | **코드 심판 (reviewer of record)** — Codex `adversarial-review` 포워더(판정 경로), 심각도 정규화·차단 판정. 네이티브 `review`는 보조 비판정 패스 | 리뷰, 심판, 판정, 머지 게이트, 머지해도 되는지, PR 승인, 도전, 반론, adversarial |
| `codex-plan-reviewer` | **계획 심판** — 이미 저작된 계획 문서를 Codex가 도전·심사 | 계획 검토, 계획 심사, 플랜 리뷰, 착수 전 검증, 가정/롤백 점검, 범위 이탈 |

> 심판 2종은 **전역 `~/.claude/agents/` 소속이다** (프로젝트 `.claude/agents/`에 사본 없음 — 드리프트 방지).
> 이름·호출 방식은 동일하며, 이 프로젝트 고유의 비협상 대조 목록은 `codex-gate` 스킬이 공급한다.
>
> 심판 게이트는 `codex-gate` 스킬이 오케스트레이션한다 (레인 A=코드 심판, 레인 B=계획 심판).
> Codex 미가용 시에만 `code-reviewer`/`review-synthesizer`로 강등하며, 그때는 리포트 최상단에
> `[FALLBACK: 비독립 심판 — 동일 모델 계열]`을 명시한다.

### 코드 유지보수 팀
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `code-reviewer` | [FALLBACK] 코드 리뷰/컨벤션 | (평시 미사용 — Codex 미가용 시 강등 경로) |
| `test-engineer` | 테스트 작성/실행 | 테스트, pytest, 커버리지, 단위 테스트 |
| `refactorer` | 리팩토링/DRY | 중복 제거, DRY, config 추출, 정리 |

> 평시 코드 심판은 `codex-reviewer`가 소유한다. `code-reviewer`는 Codex 미가용 시에만 호출하고
> `[FALLBACK: 비독립 심판 — 동일 모델 계열]`을 리포트 최상단에 명시한다.

### 운영/모니터링 팀
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `ops-monitor` | 시스템 모니터링/성능 | 헬스체크, 상태, 성능, 모니터링, 리소스 |
| `incident-responder` | 장애 대응/복구 | 장애, 에러, 크래시, 끊김, 복구 |
| `alert-manager` | 알림/Cron 관리 | Telegram, 알림, Cron, 브리핑 전달, 알림 규칙 |

### 데이터·실행·분석 팀
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `data-engineer` | 데이터 수집/백필/품질 | 수집, 백필, backfill, 분봉, gap, 데이터 품질, warmup, screener 데이터 |
| `execution-specialist` | 주문 실행/KIS 정합/ATS | 주문 실행, 체결, 슬리피지, ATS, 라우팅, rate limit, KIS API, order_router |
| `llm-analyst` | LLM 시장분석/브리핑 콘텐츠 | LLM 분석, 브리핑 내용, 시장 분석, KRX, news, macro, 프롬프트, 스코어링 |

### 종합 코드 감사 팀 (병렬 렌즈 = 증거 생성 → Codex 심판)
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `architecture-auditor` | 아키텍처 감사 (렌즈) | 아키텍처, 레이어, 의존성, 패턴 준수, god-object |
| `security-auditor` | 보안 취약점 감사 (렌즈) | 보안, 취약점, 인젝션, 시크릿, 인증, 자금경로 |
| `performance-auditor` | 성능 병목 감사 (렌즈) | 성능, 병목, 레이턴시, 쿼리, 메모리, hot path |
| `style-auditor` | 코드 스타일 감사 (렌즈) | 스타일, 타입힌트, docstring, 네이밍, 매직넘버 |
| `review-synthesizer` | [FALLBACK] 4개 감사 결과 통합 (fan-in) | (평시 미사용 — Codex 미가용 시 강등 경로) |

> 4렌즈 감사관은 `.omc/review/{stamp}/evidence/{lens}.md`에 **증거**만 남긴다. 팬인 심판(중복제거·심각도 정규화·우선순위·차단 판정·최종 `verdict.md`)은
> `codex-reviewer`가 소유한다. `review-synthesizer`는 Codex 미가용 시에만 폴백으로 쓰고 `[FALLBACK: 비독립 심판 — 동일 모델 계열]`을 명시하며,
> **폴백은 `approve`를 내지 못한다**(`adjudicator: fallback-claude` — 품질 게이트 통과 불가).

### 프론트엔드 팀 (Next.js 단일 앱)
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `frontend-architect` | Next.js 구조/데이터페칭/디자인토큰/빌드 | 프론트 아키텍처, App Router, 디자인 토큰, 빌드, Next.js 구조 |
| `ui-engineer` | Cockpit/대시보드 컴포넌트/반응형/차트 | UI, 컴포넌트, 화면, Cockpit, 반응형, 모바일, 차트, 스타일 |
| `frontend-realtime-engineer` | WebSocket/React Query/API 배선 | 실시간, WebSocket, React Query, API 연동, 낙관적 업데이트 |

### DevOps/테스트-인프라 팀 (빌드/테스트/CI 표면)
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `container-engineer` | Docker 이미지/compose 프로파일/Dev Container/.dockerignore/Makefile | Docker, 이미지, compose, devcontainer, dockerignore, 온보딩, clone-and-go |
| `ci-pipeline-engineer` | GitHub Actions/게이팅/gha 캐싱/flaky 잡 운영 | CI, GitHub Actions, 워크플로우, 잡, 캐시, 체크, 게이팅 |
| `test-reliability-engineer` | hermetic/2-pass/fakeredis 격리/de-flaking | flaky, 테스트 깨짐, hermetic, 2-pass, serial, 시드, 결정론, conftest |

> 빌드/테스트/CI 인프라는 `devx-harness` 서브 오케스트레이터가 전담한다. 런타임 모니터링·장애·알림은 `ops-harness`(별개)가 맡는다.

## 도메인별 서브 오케스트레이터

복잡한 도메인 작업은 전용 오케스트레이터 스킬이 관리:

| 스킬 | 패턴 | 담당 에이전트 | 용도 |
|------|------|-------------|------|
| `strategy-lab` | 파이프라인 (1차) | indicator-specialist → strategy-architect → backtest-engineer → regime-gate-analyst → model-evaluator → model-deployer | 운영 전략 개발 수명주기 |
| `ops-harness` | 전문가 풀 | ops-monitor, incident-responder, alert-manager | 운영/모니터링 |
| `code-audit` | 팬아웃/팬인 | architecture/security/performance/style-auditor (병렬, 증거 생성) → codex-reviewer (심판) | 종합 다중 렌즈 코드 감사 → 단일 verdict |
| `codex-gate` | 하이브리드 팬아웃/팬인 + 게이트 | codex-reviewer (레인 A=코드 심판), codex-plan-reviewer (레인 B=계획 심판) | 코드/계획 독립 심판 (Codex 레인, reviewer of record) |
| `frontend-lab` | 파이프라인 (설계→구현) | frontend-architect → ui-engineer + frontend-realtime-engineer (병렬) | Next.js 단일 앱 화면/기능 개발 (builder 제외) |
| `devx-harness` | 전문가 풀 / 생성-검증 | container-engineer, ci-pipeline-engineer, test-reliability-engineer | 빌드/테스트/CI 인프라 (Docker·compose·devcontainer·GitHub Actions·flaky/hermetic·clone-and-go); 하위 스킬 `containerize`·`ci-workflow`·`hermetic-tests` |
| `rl-pipeline` | 파이프라인 (DEPRECATED) | indicator-specialist(보조) → model-evaluator → model-deployer | RL 재학습 전용 (운영 경로 아님) |

## 라우팅 규칙

### 1차: 도메인 판별
```
전략/지표/게이트/빌더/백테스트 관련 → 전략 개발 팀 (→ strategy-lab 스킬)
전략 평가/승격/배포 관련          → 전략/모델 승격 팀 (→ strategy-lab Phase 4-5)
단일 PR 게이트 리뷰/머지 판정      → codex-reviewer (adversarial-review) — 판정 경로는 이것뿐
접근법 자체 도전/반론 요청         → codex-reviewer (adversarial-review)
계획 검토/심사 (착수 전)           → codex-plan-reviewer (→ codex-gate 레인 B)
테스트 작성/리팩토링/정리          → 코드 유지보수 팀 (test-engineer, refactorer)
종합·다중 렌즈 코드 감사 (요청)    → code-audit 스킬 (4 감사관 병렬 = 렌즈 증거) → codex-reviewer (심판)
시스템/장애/알림 관련             → 운영/모니터링 팀 (→ ops-harness 스킬)
데이터 수집/백필/품질 관련         → data-engineer
주문 실행/체결/ATS/KIS API 관련   → execution-specialist
LLM 분석/브리핑 콘텐츠 관련        → llm-analyst
프론트엔드/대시보드/UI/Next.js 관련 → 프론트엔드 팀 (→ frontend-lab 스킬; builder 기능은 strategy-builder)
Docker/compose/devcontainer·CI/GitHub Actions·flaky/hermetic 테스트·온보딩 → DevX 팀 (→ devx-harness 스킬)
RL 재학습/복귀 검토 (명시적)      → rl-pipeline 스킬 (DEPRECATED, 예외적)
```

### 2차: 전문가 선택
키워드 매칭으로 가장 적합한 전문가 1명 또는 파이프라인 선택.

**모호어 처리 — "롤백"**: 전략/모델 되돌리기(이전 설정·배포 버전 복원)는 `model-deployer`, 장애·운영 복구(프로세스/연결/포지션 정합성 복구)는 `incident-responder`. 맥락이 불분명하면 직전 작업이 배포면 model-deployer, 장애 대응 중이면 incident-responder로 라우팅한다.

**모호어 처리 — "리뷰"**: 심판(통과/차단 판정)은 `codex-reviewer`, 렌즈 증거 생성은 4감사관(architecture/security/performance/style-auditor), 대상이 코드가 아니라 *계획 문서*면 `codex-plan-reviewer`. Codex 미가용 시에만 `code-reviewer`/`review-synthesizer` 폴백(리포트 최상단에 `[FALLBACK: 비독립 심판 — 동일 모델 계열]` 명시).

**모호어 처리 — "테스트"**: 테스트 *작성*/커버리지 보강은 `test-engineer`, flaky/hermetic/2-pass·serial·CI 결정론 등 테스트 *신뢰성·인프라*는 `test-reliability-engineer`(→ devx-harness). "테스트 깨졌어"는 신뢰성 문제일 가능성이 높으므로 test-reliability-engineer로 진단 먼저.

```
"BB 기반 새 전략 만들어줘"            → strategy-architect
"RL 대체할 지표 리서치해줘"           → indicator-specialist
"이 전략에 RegimeGate 적용해서 검증"  → regime-gate-analyst
"빌더에서 만든 전략 paper에 올려줘"    → strategy-builder
"bb_reversion 백테스트 돌려줘"        → backtest-engineer
"현재 전략이랑 새 전략 비교해줘"        → model-evaluator
"이 전략 Live로 승격해줘"             → model-deployer
"지표 전략 새로 만들고 승격까지"       → strategy-lab (풀 파이프라인)
"이 PR 리뷰해줘"                     → codex-reviewer (adversarial-review)
"머지해도 되는지 판정해줘"            → codex-reviewer (adversarial-review)
"접근법 자체를 도전해줘"              → codex-reviewer (adversarial-review)
"이 계획 괜찮은지 봐줘"               → codex-plan-reviewer
"수정했으니 재심해줘"                 → codex-gate (재심 경로)
"three_stage 테스트 작성해줘"         → test-engineer
"중복 코드 정리해줘"                  → refactorer
"시스템 상태 확인해줘"                → ops-monitor
"WebSocket 끊겼어"                   → incident-responder
"Telegram 알림 설정해줘"             → alert-manager
"전체 헬스체크"                      → ops-harness
"분봉 데이터 gap 메워줘"              → data-engineer
"백필 무결성 확인해줘"                → data-engineer
"슬리피지 모델 검증해줘"              → execution-specialist
"ATS 라우팅 규칙 손봐줘"             → execution-specialist
"장전 브리핑 분석 내용 개선해줘"       → llm-analyst
"이 PR 종합 감사해줘"                 → code-audit (4 감사관 병렬 → codex-reviewer 심판)
"보안+성능+아키텍처 같이 점검해줘"     → code-audit
"shared/execution 전체 코드 감사"      → code-audit (경로 모드)
"대시보드에 새 화면 추가해줘"          → frontend-lab (풀 파이프라인)
"Cockpit 포지션 카드 모바일 개선"      → ui-engineer
"실시간 시그널이 안 갱신돼"            → frontend-realtime-engineer
"디자인 토큰/테마 정리해줘"            → frontend-architect
"Dockerfile/compose 프로파일 손봐줘"   → container-engineer (→ devx-harness)
"CI 워크플로우/GitHub Actions 고쳐줘"  → ci-pipeline-engineer (→ devx-harness)
"이 테스트 flaky해 / CI 빨개"          → test-reliability-engineer (진단 먼저, → devx-harness)
"clone-and-go 온보딩 안 돼"            → container-engineer (+ test-reliability-engineer)
"전체 빌드/테스트/CI 인프라 감사"      → devx-harness (3 에이전트 병렬)
"RL 모델 재학습 검토" (예외)          → rl-pipeline (DEPRECATED)
```

## 복합 작업 워크플로우

### 신규 지표 전략 개발 → 승격 (strategy-lab 위임)
```
Phase 1: indicator-specialist + strategy-architect → 지표 시그널 설계/조립
Phase 2: backtest-engineer → 백테스트 + Optuna (holdout 분리)
Phase 3: regime-gate-analyst → RegimeGate head-to-head + counterfactual
Phase 4: model-evaluator → 종합 승격 판정
Phase 5: model-deployer → Phase 5 Gate 1–3 + 운영자 승인 → Paper→Live
```

### 새 전략 추가 (간이 파이프라인)
```
Phase 1: strategy-architect → 전략 설계/구현
Phase 2: test-engineer → 테스트 작성 (병렬 가능)
Phase 3: backtest-engineer → 백테스트 실행
Phase 4: codex-reviewer → 독립 심판 (approve / needs-attention)
```

### 코드 품질 개선
```
Phase 1: codex-reviewer → 이슈 식별 (독립 심판)
Phase 2: refactorer + test-engineer (병렬) → 수정 + 테스트 보강
Phase 3: codex-reviewer → 재심 (verdict 갱신)
```

### 장애 대응 (ops-harness 위임)
```
Phase 1: ops-monitor → 이상 감지
Phase 2: incident-responder → 진단 + 복구
Phase 3: alert-manager → 알림 발송
Phase 4: ops-monitor → 복구 후 재검증
```

### 병렬 실행 (팬아웃)
```
"전략 구현하고 테스트도 작성해줘"
→ strategy-architect + test-engineer (병렬)

"코드 리뷰하고 리팩토링 대상 찾아줘"
→ codex-reviewer + refactorer (병렬)

"헬스체크하고 알림 상태도 확인해줘"
→ ops-monitor + alert-manager (병렬)
```

### 종합 코드 감사 (code-audit 위임, 팬아웃→팬인)
```
범위 결정 (diff / PR #N / 경로)
    ↓ fan-out (4개 병렬, 동일 범위) — 렌즈 = 증거 생성
architecture-auditor + security-auditor + performance-auditor + style-auditor
    ↓ 각 렌즈 산출물을 .omc/review/{stamp}/evidence/{lens}.md 로 기록
    ↓ fan-in (독립 심판)
codex-reviewer (focus = .omc/review/{stamp}/evidence/) → 중복제거·심각도정규화·우선순위·차단판정
    ↓ → .omc/review/{stamp}/verdict.md  (evidence/ 밖, adjudicator: codex)
    ↓ (선택)
차단 항목 → refactorer / execution-specialist / data-engineer 등으로 수정 위임 → codex-gate 재심
```

### 프론트엔드 화면 개발 (frontend-lab 위임, 설계→구현 병렬)
```
frontend-architect → 라우트 구조 + 데이터 페칭 전략 + 디자인 토큰
    ↓ (병렬)
ui-engineer (컴포넌트/반응형/스타일) + frontend-realtime-engineer (WebSocket/React Query 배선)
    ↓
code-audit (style/architecture-auditor) + npm run build/타입체크
    ↓
codex-reviewer 심판 (approve / needs-attention)
```

### 계획 심판 게이트 (codex-gate 레인 B)
```
Phase 1: (기존 경로) Claude 측이 계획 저작 — 변경 없음
         strategy-lab / frontend-lab / devx-harness 등 기존 파이프라인이 그대로 계획을 쓴다
Phase 2: codex-plan-reviewer → 독립 심판
         (순서 · 가정 · 검증가능성 · 롤백 · 범위이탈 · CLAUDE.md 충돌)
Phase 3: needs-attention → 저작자가 계획 개정 → 재심
Phase 4: approve → 실행 착수
```

## 사용법

이 스킬은 자동으로 적용됩니다. 사용자의 요청을 분석하여:

1. **도메인 판별** → 해당 팀 식별
2. **전문가 선택** → 키워드 매칭으로 에이전트 선택
3. **단일/복합/파이프라인 판단** → 적절한 실행 방식 결정
4. **Agent 도구 호출** → `.claude/agents/{name}.md` 참조하여 위임
5. 결과를 사용자에게 보고

## 품질 게이트

모든 전략 개발 작업 완료 시:
1. `.venv/bin/pytest tests/ -v` 통과
2. `black . && ruff check .` 통과
3. CLAUDE.md 규칙 준수 (하드코딩 금지, DRY, Strategy Pattern, KST, Look-ahead 금지)
4. YAML config 존재 및 유효성
5. REMOVED/DEPRECATED 전략(`rl_mppo`, `llm_directed_indicator`) 미사용

코드 변경 완료 시:
- **`codex-reviewer`(= Codex)가 낸 새 `verdict: approve`만 이 게이트를 통과시킨다. 예외 없다.**
  - **needs-attention을 받았으면 수정 → 재심 → Codex의 새 `approve`.** "해소했으니 통과"는 없다 —
    해소되었는지 회피되었는지(테스트 무력화·조건 완화·문구만 추가)를 판정하는 것도 심판의 몫이다
    (`codex-gate` "수정 위임 (needs-attention 이후)" 절: "수정 완료 후 반드시 재심한다.
    수정만 하고 통과시키면 게이트가 아니다").
  - **기각(수용검사)은 게이트를 여는 장치가 아니다.** 기각의 용도는 둘뿐이다 —
    (a) 해당 finding이 다음 재심에서 되살아나지 않게 사유와 함께 기록하고,
    (b) 재심에 들어갈 때 Codex에게 기각 사유를 함께 제시한다.
    **finding을 전부 기각해도 게이트는 여전히 Codex의 `approve`로만 열린다.**
    피심판자가 자기 판단으로 finding을 지우고 통과할 수 있으면 심판자를 둔 의미가 소멸한다 —
    그것이 정확히 이 레인이 막으려는 자기 승인이다.
  - **판정 경로는 `adversarial-review`다.** verdict 계약을 내는 유일한 경로이므로 이 조건과 짝이 맞는다
    (`codex-companion.mjs:409-417` = 스키마 부착 / `:370-407` 네이티브 `review` = verdict 없음).
    `review` 출력에는 `verdict`가 없으므로 이 게이트를 만족시킬 수 없다
  - **폴백 산출물(`adjudicator: fallback-claude`)은 어떤 값이든 이 게이트를 통과시키지 못한다.**
    Codex 미가용 시의 강등 경로는 비독립 심판(동일 모델 계열)이라 통과 권한이 없다 —
    폴백에 통과 권한을 주면 그것이 자기 승인 우회로가 되고, 심판 레인의 존재 이유가 소멸한다.
    폴백은 애초에 `approve`를 내지 않으며(`review-synthesizer` 계약), 낸다 해도 게이트는 열리지 않는다.
  - **판정 불능도 통과가 아니다 (fail-closed).** `verdict` 필드 부재·"Parse error"는 실패로 취급한다.
  - 게이트 통과 조건을 한 줄로: **`adjudicator: codex` + `verdict: approve`.**

실행 착수 전:
- 계획이 있는 작업은 `codex-plan-reviewer` 심판 통과

**수용검사 규칙**: Codex verdict는 무조건 수용하지 않는다. 다만 **기각 가능 사유는 셋뿐이다**:

1. **팬텀 `file:line`** — 인용한 파일·라인이 실측상 부재
2. **이미 의도적으로 silenced된 항목** — lint ignore, 안전 주석, 테스트 픽스처
3. **CLAUDE.md 비협상 규칙과 배치되는 권고** — 선물 long/short 대칭, 실계좌 증거금 미투입,
   EOD 일괄청산 금지, ClickHouse 신규 사용 금지, RL/TFT 경로 부활 금지 등
   (전체 대조 목록은 `codex-gate` "비협상 규칙 대조 목록" 절)

**그 외 사유로는 기각할 수 없다** — "동의하지 않음", "우선순위 낮음", "나중에"는 기각이 아니라 **미해결**이다.
기각한 finding은 사유와 함께 기록하고 재심 때 Codex에 함께 제시한다.
Codex는 심판이지 이 repo의 비협상 규칙 위에 있지 않다. 그러나 **기각은 게이트를 열지 않는다**
(위 "코드 변경 완료 시" 절 — 게이트는 Codex의 새 `approve`로만 열린다).

전략 Paper→Live 승격 시:
1. 종합 승격 판정 PASS (model-evaluator)
2. RegimeGate head-to-head PASS + counterfactual 음수 아님 (해당 시)
3. Phase 5 Gate 1–3 통과 + 운영자 서면 승인
4. `config/futures_live.yaml::enabled` + Redis `futures:live:suspended` 절차
5. 안전장치 동작 확인 (hard stop, EOD close)
