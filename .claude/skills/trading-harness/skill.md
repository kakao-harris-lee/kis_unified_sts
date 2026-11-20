---
name: trading-harness
description: "KIS Unified STS 통합 오케스트레이터. 지표/선언형 필드 카탈로그, KIS 전송·브로커 프로브, 코드 유지보수(테스트·리팩토링), 운영/장애, 프론트엔드, 빌드/테스트/CI 인프라(DevX), 종합 코드 감사. 전문가 풀에서 적절한 에이전트를 선택해 라우팅한다. tos 커널·런타임 작업은 `tos/CLAUDE.md` 에서 시작한다."
---

# Trading Harness — 통합 전문가 풀 오케스트레이터

이 저장소에서 실제로 돌아가는 것은 **TOS 커널 + CP-3 tenant 세션**과 **읽기 전용
운영자 표면**이다. 레거시 주식/선물 런타임, 전략 레지스트리, RL/TFT, 노코드 빌더,
Telegram 알림, ClickHouse 피드는 2026-11 L1–L7 에서 삭제됐다
(`docs/plans/2026-11-07-legacy-removal-plan.md`). 없는 것을 되살리려 하지 마라.

**tos 작업은 이 스킬이 아니라 `tos/CLAUDE.md` 에서 시작한다.** `tos/`, `tools/tos_*`,
`tests/tools/test_tos_*`, `docs/plans/*tos*` 가 그 working set 이고, 비대칭 수입
방화벽이 CI 로 강제된다.

## 전문가 풀 (18명 — 전원 이 repo `.claude/agents/` 소속)

### 도메인 팀
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `indicator-specialist` | 지표 엔진·선언형 필드 카탈로그 | 지표, 필드, `fields.yaml`, 카탈로그, 웜업, 표본 게이팅, look-ahead |
| `execution-specialist` | KIS 전송·브로커 프로브·인증 | 프로브, KIS API, 토큰, 페이싱, EGW00201, TR id, 계약 명세 |
| `frontend-architect` | Next.js 단일 앱 (`/tos` 페이지·프록시·빌드) | 프론트, UI, 화면, Next.js, 프록시, 디자인 토큰, vitest |

### 코드 유지보수 팀
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `test-engineer` | 테스트 작성/실행/커버리지 | 테스트, pytest, 커버리지, 단위 테스트 |
| `refactorer` | 리팩토링/DRY | 중복 제거, DRY, config 추출, 정리 |

### 운영/장애 팀 (→ `ops-harness`)
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `ops-monitor` | 상태 확인 (읽기 전용) | 헬스체크, 상태, 모니터링, 리소스, 오늘 뭐 돌았나 |
| `incident-responder` | 장애 진단·복구 | 장애, 크래시, 부팅 거부, 끊김, 복구 |

### DevOps/테스트-인프라 팀 (→ `devx-harness`)
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `container-engineer` | Docker 이미지·compose 프로파일·Dev Container·`.dockerignore`·Makefile | Docker, 이미지, compose, devcontainer, 온보딩 |
| `ci-pipeline-engineer` | GitHub Actions 7개 워크플로우·필수 체크·게이팅·캐싱 | CI, GitHub Actions, 워크플로우, 잡, 캐시, 체크 |
| `test-reliability-engineer` | hermetic·2-pass·fakeredis 격리·de-flaking | flaky, 테스트 깨짐, hermetic, 2-pass, serial, 시드, 결정론 |

### 종합 코드 감사 팀 (→ `code-audit`)
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `architecture-auditor` | 아키텍처 렌즈 — tos 방화벽·레이어·의존성·DRY | 아키텍처, 경계, 의존성, 방화벽, god-object |
| `security-auditor` | 보안 렌즈 — 시크릿·인증·실주문 인터록 | 보안, 취약점, 시크릿, 인증, 자금경로 |
| `performance-auditor` | 성능 렌즈 — 바당 hot path·캐싱·페이싱 예산 | 성능, 병목, 레이턴시, 메모리, hot path |
| `style-auditor` | 스타일 렌즈 — 타입·docstring·매직넘버·`# SAFETY:` | 스타일, 타입힌트, 네이밍, 매직넘버 |

### 리뷰 레인 (CLAUDE.md R1)
| 에이전트 | 전문 영역 | 언제 |
|---------|----------|------|
| `code-reviewer` | 단일 PR 리뷰 — **기본 레인** | 등급 B 의 유일한 레인, 등급 A 의 독립 리뷰 1회 |
| `review-synthesizer` | 4렌즈 팬인 심판 — **기본 레인** | `code-audit` 의 마지막 단계 |
| `codex-reviewer` | Codex 코드 심판 — **추가 레인** | 등급 A + 운영자가 범위·비용 승인 시에만 |
| `codex-plan-reviewer` | Codex 계획 심판 — **추가 레인** | 운영자가 계획 비평을 명시 요청했을 때만 |

> **R1 등급.** A = 실주문/브로커 송신 · 자격증명/인증 · 리스크 한도 · 데이터 파기 ·
> DB 마이그레이션. B = 그 밖의 모든 코드와, 운영자 결정의 근거가 되는 사실을 적은 문서.
> C = 그 밖의 문서·측정 기록·증거 PR — **리뷰 레인 없이** 작성자가 인용값을 대조하고
> CI green 이면 머지한다. PR 본문에 등급과 한 줄 이유를 적는다.
>
> **R2** 라운드 최대 2회. **R3** «이 입력 → 이 잘못된 결과» 를 지목한 HIGH 이상만 차단.
> **R4** 새 계획 문서는 300줄 이하. 계획은 리뷰 레인으로 보내지 않는다 — 운영자가 읽고 승인한다.
>
> **자기 승인 금지**: 저작 패스와 리뷰 패스를 분리한다. 작성자와 같은 활성 컨텍스트에서
> 승인하지 마라.

## 도메인별 서브 오케스트레이터

| 스킬 | 패턴 | 담당 에이전트 | 용도 |
|------|------|-------------|------|
| `ops-harness` | 전문가 풀 | ops-monitor, incident-responder | 운영 상태·장애 진단/복구 |
| `code-audit` | 팬아웃/팬인 | 4개 감사관(병렬, 증거) → review-synthesizer (심판) | 종합 다중 렌즈 코드 감사 → 단일 verdict |
| `devx-harness` | 전문가 풀 | container-engineer, ci-pipeline-engineer, test-reliability-engineer | 빌드/테스트/CI 인프라. 하위 스킬 `containerize`·`ci-workflow`·`hermetic-tests` |
| `codex-gate` | 게이트 | codex-reviewer (레인 A), codex-plan-reviewer (레인 B) | **추가** Codex 레인 — 등급 A + 운영자 승인 시에만 |

## 라우팅 규칙

### 1차: 도메인 판별
```
tos 커널 / tos_runtime / tools/tos_* 작업        → tos/CLAUDE.md 에서 시작 (이 스킬 아님)
지표·필드 카탈로그·fields.yaml 관련               → indicator-specialist
KIS 프로브·토큰·페이싱·TR id 관련                 → execution-specialist
프론트엔드/`/tos` 페이지/프록시/UI 빌드           → frontend-architect
테스트 작성·리팩토링·정리                         → test-engineer, refactorer
운영 상태·장애·복구                               → ops-harness (ops-monitor / incident-responder)
Docker·compose·devcontainer·CI·flaky·온보딩       → devx-harness
단일 PR 리뷰 / 머지 판정                          → code-reviewer
종합·다중 렌즈 코드 감사                          → code-audit
등급 A + 운영자 승인된 Codex 심판                 → codex-gate
```

### 2차: 모호어 처리
- **"리뷰"**: 단일 PR 판정은 `code-reviewer`, 렌즈 증거 생성은 4감사관,
  팬인 심판은 `review-synthesizer`. Codex 는 등급 A + 운영자 승인 시에만 추가로 탄다.
- **"테스트"**: *작성*/커버리지는 `test-engineer`, flaky/hermetic/2-pass/CI 결정론 등
  *신뢰성·인프라* 는 `test-reliability-engineer`. "테스트 깨졌어" 는 신뢰성 쪽을 먼저 의심한다.
- **"복구"**: 운영 세션·연결·프로세스 복구는 `incident-responder`.
  이미지/compose/env 파일 문제면 `container-engineer`.

```
"필드 카탈로그에 연산 추가해줘"        → indicator-specialist
"프로브 페이싱이 이상해"               → execution-specialist
"/tos 페이지에 패널 추가해줘"          → frontend-architect
"이 테스트 flaky해 / CI 빨개"          → test-reliability-engineer (진단 먼저)
"CI 워크플로우 고쳐줘"                 → ci-pipeline-engineer
"Dockerfile/compose 손봐줘"            → container-engineer
"오늘 세션 뭐 돌았어"                  → ops-monitor
"세션이 안 떴어 / 부팅 거부"           → incident-responder
"이 PR 리뷰해줘"                       → code-reviewer
"이 PR 종합 감사해줘"                  → code-audit
"중복 코드 정리해줘"                   → refactorer
```

## 비협상 규칙 (어떤 라우팅도 이것을 우회하지 않는다)

CLAUDE.md «Non-Negotiable Rules» 가 정본이다. 요약:

- **설정 기반**: 임계값·심볼·리스크 값·포트·Redis DB·스케줄·게이트는 YAML/env/config 에.
- **DRY**: 공유 동작은 `shared/`.
- **Redis DB 1** 전용, 새 키에는 TTL (기본 24h, 누적 스냅샷 48h). 예외는 YAML 값 옆에
  이유를 적고, 그 키의 신선도 검사가 **같은 설정값**을 읽어야 한다.
- **KST 네이티브**: 세션 로직·cron. 한국 장 시간과 비교하기 **전에** 변환.
- **시크릿 비커밋**: `${VAR}` 참조. `.kis_token_*`·채워진 `.env` 금지.
- **주식 스윙 청산은 시그널 구동** — 일괄 EOD 청산을 넣지 않는다.
- **선물 long/short 대칭** — 방향은 `signal_direction` 을 따른다.
- **실전 선물 계좌는 절대 입금하지 않는다.** 실주문 경로(P-R5 stage 2 포함)는 **정책상
  영구 차단**이다. 미입금 preflight ABORT 는 «입금 대기» 가 아니라 **종결 판정**이다.
  실계좌 GET 읽기는 괜찮고, 체결이 필요한 측정은 모의 계좌 유도 상한을 쓴다.
- **tos 수입 방화벽**: `tos/` 밖에서 `tos`/`tos_runtime` import 금지. `tos/` 는 비준된
  6개 pure-commons 만.
- **되살리지 말 것**: 전략 레지스트리/팩토리, `sts rl *`·`sts tft *`, `shared/ml/{rl,tft}`,
  `services/api`/호스트 `:8000`, 직접 ClickHouse 사용.
- **`# SAFETY:`**: 지워지면 안 되는 «왜» 는 한 줄 `# SAFETY:` 주석으로 적는다
  (`tools/strip_prose.py` 의 KEEP_MARKERS 가 보존한다).
- **동결 경로**: `shared/decision/setups/vwap_reversion.py` 와 그 의존성은
  `TOS_PAPER_READY` 까지 바이트 동일이다.
- **가짜 완료 금지**: TODO 플레이스홀더·`test.skip`/`.only`·스텁 테스트·미구현 분기는
  증거가 아니라 차단 사유다.

## 작업 전 확인

- **브랜치 먼저**: `main` 에 직접 커밋하지 않는다. `git switch -c <type>/<slug>`.
- **워크트리 격리**: 병렬 에이전트는 각자 워크트리에서. `git stash` 금지 (저장소 전역이다).
- **무거운 빌드는 호스트 전체에서 1개**: `free -m`·`pgrep -af GradleWrapperMain`·
  `ps -eo pid,rss,args --sort=-rss` 를 **별도 턴으로 먼저** 확인한다.
- **프로브는 분리 워크트리에서만** 실행한다.
