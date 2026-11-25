---
name: code-audit
description: "종합 코드 감사 오케스트레이터 (fan-out/fan-in). 아키텍처·보안·성능·스타일 4개 감사관을 병렬 실행해 증거를 생성하고, review-synthesizer 가 팬인해 단일 verdict로 판정. 등급 A 에서 운영자가 범위·비용을 승인하면 codex-reviewer 가 추가 레인으로 탄다. '종합 리뷰', '전체 감사', '코드 감사', '보안+성능+아키텍처 점검', '재감사', '다시 감사', '수정 후 재심', '감사 업데이트' 요청 시."
---

# Code Audit — 종합 코드 감사 오케스트레이터

코드(diff / PR / 경로)를 **4개 전문 렌즈로 병렬 감사**해 증거를 생성하고, 그 증거를
**하나의 verdict로 판정**하는 fan-out/fan-in 하네스. 일상 단일 게이트 리뷰
(`code-reviewer` 단독 호출)와 달리, 이 스킬은 **여러 전문 감사관의 깊이 있는
다중 관점 감사**를 한 번에 수행한다.

## 레인 (CLAUDE.md R1, 2026-10-22 운영자 지시)

| 등급 | 무엇 | 팬인 심판 |
|------|------|----------|
| **A** | 실주문/브로커 송신, 자격증명·인증, 리스크 한도, 데이터 파기, DB 마이그레이션 | `review-synthesizer` 1회 **+** 운영자가 범위·비용을 승인하면 `codex-reviewer` 추가 |
| **B** | 그 밖의 모든 코드 | `review-synthesizer` 1회 — **Codex 로 가지 않는다** |
| **C** | 문서·측정 기록·증거 | 이 스킬을 쓰지 않는다. 작성자가 인용값을 대조하고 CI green 이면 머지 |

> **2026-09-04 의 «Codex 가 기본 심판» 지위는 끝났다** (2026-09-11 운영자 지시로 Codex
> 범위가 되돌리기 어려운 경로로 한정됐다). Claude 측 팬인은 폴백이 아니라 **기본 레인**이고,
> 차단 항목이 0건이면 `approve` 를 낸다. `[FALLBACK: …]` 마커는 더 이상 찍지 않는다.
>
> 자기 승인 방지는 여전히 요구된다 — **저작 패스와 리뷰 패스를 분리**해서 달성한다.
> 작성자와 같은 활성 컨텍스트에서 판정하지 마라.

## 언제 쓰나
- "종합 코드 리뷰 / 전체 감사 / 코드 감사 해줘"
- "아키텍처·보안·성능·스타일 같이 점검해줘"
- 큰 변경/릴리스 전 심층 다중 렌즈 감사
- "재감사 / 다시 감사 / 수정 후 재심 / 감사 업데이트" (Phase 4 부분 재실행)
- (단순 PR 1건 게이트 리뷰는 `code-reviewer` 단독 호출 — 렌즈 팬아웃만 생략한다)

## 팀 구성 (증거 생성 팬아웃 + 독립 심판 팬인)

| 에이전트 | 렌즈 | 단계 |
|---------|------|------|
| `architecture-auditor` | 레이어 경계·의존성·패턴·DRY·god-object | 병렬 증거 생성 |
| `security-auditor` | 인젝션·시크릿·입력검증·인증·자금경로 | 병렬 증거 생성 |
| `performance-auditor` | hot path·캐싱·쿼리·메모리·레이턴시 | 병렬 증거 생성 |
| `style-auditor` | 포맷·타입·docstring·네이밍·매직넘버 | 병렬 증거 생성 |
| `review-synthesizer` | 중복제거·심각도정규화·우선순위·차단판정·단일 verdict | 팬인 심판 (기본) |
| `codex-reviewer` | 같은 팬인을 다른 모델 계열이 한 번 더 | 등급 A + 운영자 승인 시에만 |

## 워크플로우

```
                        ┌─ architecture-auditor ─┐
[code-audit]            ├─ security-auditor ──────┤   각 렌즈가 파일로 기록
  범위 결정  ──fan-out──┤                          ├──→ .omc/review/{stamp}/evidence/{lens}.md
 (diff/PR/경로)         ├─ performance-auditor ───┤        (architecture|security|
  stamp=YYYYMMDD-HHMMSS └─ style-auditor ─────────┘         performance|style)
                    (4개 병렬, 서로 독립 / 같은 범위 입력)
                                                                    │
                                                 evidence/ 만 읽는다 │
                                                                    ▼
                               review-synthesizer (기본)  [+ codex-reviewer: 등급 A + 운영자 승인]
                                                                    │
                                                                    ▼
                                     .omc/review/{stamp}/verdict.md  ← evidence/ 밖
                     {adjudicator, reviewed_at_head, reviewed_scope_digest,
                      verdict, summary, findings[], next_steps[]}
                                                                    │
                                                                    ▼
                                              Claude 오케스트레이터 수용검사
```

### Phase 0: 워크스페이스 준비
- `stamp = YYYYMMDD-HHMMSS`(초 단위)를 정하고 `.omc/review/{stamp}/`와 `.omc/review/{stamp}/evidence/`를 만든다.
- **스탬프 디렉토리는 `mkdir -p`로 만들지 마라** — `-p`는 기존 디렉토리를 조용히 재사용해서
  이전 실행 증거와 이번 증거를 한 디렉토리에 섞는다. **충돌하면 실패하는 `mkdir`** 을 쓴다
  (생성 절차는 `codex-gate` 스킬 Phase 0이 소유).
- **렌즈 산출물은 `evidence/` 안, 심판 결과 `verdict.md`는 `evidence/` 밖**이다.
  Codex focus는 `evidence/`만 지목한다 — 심판자가 자기 이전 verdict를 증거로 되읽는 오염을
  경로 구조로 차단한다 (Phase 3 참조).
- `.omc/`는 이미 gitignore 처리되어 있으므로 산출물이 커밋을 오염시키지 않는다.
- **리비전 포착**: 심사 대상 리비전을 포착해 둔다 (`reviewed_at_head` = `git rev-parse HEAD`,
  `reviewed_scope_digest` = `review_scope_digest`). **이 스킬은 레인 A(코드)다.**
  **함수 정의·계산법·판정표는 `codex-gate` 스킬의 `## 리비전 결속` 절이 단일 소유자다** —
  여기에 복제하지 마라. 복제본은 원본과 드리프트하고, 그 순간 두 진입점이 서로 다른 것을 결속한다.
- **포착 시점은 Phase 3의 Codex 디스패치 직전**이다. Phase 0에서 미리 계산해두고 Phase 2 감사 중에
  트리가 바뀌면 digest는 심판이 실제로 본 상태를 가리키지 않는다 — 결속이 거짓이 된다.
  (Phase 0에서는 "포착한다"는 사실만 계약으로 두고, 실제 실행은 Phase 3 직전이다.)

### Phase 1: 범위 결정
- **diff 모드**: `git diff`(working tree) 또는 staged — 진행 중 작업
- **PR 모드**: `gh pr diff <N>` — 특정 PR
- **경로 모드**: 지정 디렉토리/모듈 전체 (예: `shared/execution/`)
- 범위를 4개 감사관 모두에게 **동일하게** 전달 (stamp도 함께 전달)

### Phase 2: 병렬 감사 = 증거 생성 (fan-out)
4개 감사관을 **하나의 메시지에서 동시 dispatch** (Agent 도구 병렬 호출). 각 감사관:
- 자기 렌즈에만 집중 (렌즈 간 침범 금지)
- 변경 범위 우선, 기존 부채는 pre-existing으로 표기
- 구조화 발견 목록 생성: `{severity, dimension, location, finding, recommendation, confidence}`
- **반환만 하지 말고 `.omc/review/{stamp}/evidence/{lens}.md`에 파일로 기록한다**
  (lens = `architecture` | `security` | `performance` | `style`)

> **왜 파일인가**: Codex는 별도 프로세스라 Claude 서브에이전트의 **반환값을 볼 수 없다.**
> 파일이 Codex 심판에게 증거를 전달하는 **유일한 채널**이다.
> 파일을 안 쓰면 심판은 렌즈 결과를 보지 못한 채 판정하게 된다.

각 감사관은 판정하지 않는다. **심각도는 제안값**이며 정규화·차단 판정은 심판 소관이다.

### Phase 3: 팬인 심판 (fan-in)
`review-synthesizer`를 호출한다. 등급 A 이고 운영자가 범위·비용을 승인했다면
`codex-reviewer`도 추가로 호출한다(그 경로의 절차는 `codex-gate` 스킬이 소유).
- **호출 직전에 리비전을 포착한다** (Phase 0 계약의 실행 지점):
  `reviewed_at_head` = `git rev-parse HEAD`, `reviewed_scope_digest` = `review_scope_digest`
  (레인 A). **함수 정의와 근거는 `codex-gate` 스킬 `## 리비전 결속` 절 — 복제 금지.**
- 심판에게 **`.omc/review/{stamp}/evidence/`** 디렉토리만 지목한다. **스탬프 디렉토리를
  통째로 지목하지 마라.** 통째로 주면 재실행·부분 재실행에서 심판이 **자기 이전 `verdict.md`를
  렌즈 증거로 되읽는다** — 자기 출력을 입력으로 되먹이는 오염이다.
  그래서 `verdict.md`를 `evidence/` 밖에 두고 focus는 `evidence/`만 지목한다 —
  **산문 규칙이 아니라 경로 구조로 막는 것이 요점이다.**
- 출력은 verdict 스키마:
  `{verdict: approve|needs-attention, summary, findings[{severity, title, body, file, line_start, line_end, confidence, recommendation}], next_steps[]}`
- 결과를 `.omc/review/{stamp}/verdict.md`에 저장하며, **최상위에 아래 3필드를 덧붙인다.**
  Codex 추가 레인을 탔다면 그 JSON 스키마는 플러그인 소유라 바꿀 수 없으므로 **이 필드들은
  오케스트레이터가 기록 시점에 부여한다** (Codex 출력 본문은 verbatim 유지).

  | 필드 | 값 |
  |------|-----|
  | `adjudicator` | `"claude-lane"` (Codex 추가 레인의 산출물은 `"codex"`) |
  | `reviewed_at_head` | 디스패치 직전 `git rev-parse HEAD` 출력 |
  | `reviewed_scope_digest` | 디스패치 직전 `review_scope_digest` 출력 (64자 hex) |

  **`reviewed_at_head` / `reviewed_scope_digest`의 정의·계산법·재계산 대조 절차는
  `codex-gate` 스킬 `## 리비전 결속` 절이 소유한다** — 이 스킬은 참조만 하고 복제하지 않는다.
  이 진입점이 자기 계산법을 따로 쓰면 두 진입점이 같은 이름으로 다른 것을 결속하게 된다.
- **결속 없는 verdict는 통과가 아니다 (fail-closed).** `verdict.md`에
  `reviewed_scope_digest`가 없거나 digest 계산이 실패했으면 **무엇을 승인한 것인지 알 수 없으므로**
  approve로 읽지 않는다. 대조 불능은 일치가 아니다 (`codex-gate` `## 리비전 결속`의 판정표와 동일 어휘).
  게이트 통과는 `verdict: approve` + `reviewed_scope_digest == 현재 review_scope_digest`의
  **AND**에서만 성립한다.
- **Codex 추가 레인을 탔다면 그 stdout은 verbatim 보존한다. 요약하지 마라.**
  이유: 피심판자가 심판 결과를 요약하면 그 순간 독립성이 훼손된다.
  압축·의역·"핵심만 정리"는 전부 금지. 인용은 원문 그대로.
- **R3 — 무엇이 막는가.** «이 입력 → 이 잘못된 결과» 라는 **구체적 실패 입력을 지목한
  HIGH 이상**만 차단한다. 문구·인용 줄번호·표현 정밀도는 차단하지 않는다.
  **R2 — 라운드는 최대 2회.** 2라운드 뒤 남은 지적은 이슈로 돌리고 PR 은 머지한다.

### Phase 3.5: 수용검사 (오케스트레이터)
**verdict를 무조건 수용하지 않는다.** verbatim 보존은 유지한 채, 아래를 확인해 별도 섹션에 기록한다:

- [ ] **실재성**: 각 finding의 `file:line`이 실제로 존재하는가 (없으면 해당 항목 무효 표기)
- [ ] **의도적 silence**: lint ignore·안전 주석·테스트 픽스처처럼 **의도적으로 silenced된 항목**인가
- [ ] **비협상 규칙 배치**: 권고가 CLAUDE.md 비협상 규칙과 충돌하는가. 충돌하면 **기각하고 사유를 기록**한다.
  - 선물 long/short 대칭 훼손
  - 실계좌 증거금 관련 제안 (실 선물 계좌는 영구 미납입 — 운영자 지시)
  - EOD 일괄청산 도입 (스톡 스윙 청산은 시그널 구동)
  - ClickHouse 신규 사용 (활성 런타임·compose 의존이 아니다)
  - RL/TFT 경로 부활 (`sts rl *`, `sts tft *`, `shared/ml/rl`, `shared/ml/tft` 등)
  - 하드코딩 도입·Redis DB 1 이탈·TTL 없는 새 Redis 키·`shared/` 우회 중복
  - 전략 레지스트리/팩토리 부활, `tos` 수입 방화벽 위반
  - `assert_no_live_futures_config` 인터록 우회 또는 실계좌 입금 전제

기각 항목은 **삭제하지 말고** "기각 + 사유"로 남긴다. 심판 기록을 지우면 다음 심판이 같은 것을 다시 제기한다.

### Phase 4: 후속 (선택)
- 차단 항목 → 담당 에이전트로 수정 위임 (`refactorer`, `execution-specialist`, `indicator-specialist`, `test-engineer` 등)
- 수정 후 해당 렌즈만 재감사 (부분 재실행) → **새 stamp**로 재심판 (R2: 최대 2라운드)

## 판정 불능 (fail-closed)

**판정 불능은 실패이지 통과가 아니다.** 심판이 응답했더라도 출력에 `verdict`가 없거나
파싱에 실패했다면 판정을 내지 못한 것이다. **approve로 넘기지 마라** — 판정 불능을
통과로 읽으면 게이트가 무의미해진다. 1회 재시도 후에도 verdict 가 없으면 실패로 보고한다.

결속 필드(`reviewed_at_head` · `reviewed_scope_digest`)를 포착하지 못했을 때도 같다 —
**무엇을 승인한 것인지 알 수 없으므로** approve 로 읽지 않는다. 대조 불능은 일치가 아니다.

Codex 추가 레인(등급 A + 운영자 승인)을 호출했는데 Codex 가 미가용이면, **그 사실을
`summary`에 적고** Claude 측 팬인 판정만으로 진행한다 — 등급 A 의 독립 리뷰 1회는
Claude 측 레인이 이미 수행했기 때문이다. 조용히 넘어가지 마라.

## 모델 선택 (비용/속도)
- 감사관 4종: 표준 모델(sonnet) 병렬 — 판단·코드 이해 필요
- 대규모 경로 모드: 감사관별로 하위 파일셋 분할 dispatch 후 렌즈별 1차 통합 → 렌즈 파일 1개로 기록 → Codex 최종 심판
- 팬인 심판: `review-synthesizer` (opus). 등급 A + 운영자 승인 시 `codex-reviewer` 추가 —
  모델 계열이 다른 것 자체가 그 추가 레인의 가치다

## 거짓 양성 정책 (팬인 심판 + 수용검사가 강제)
- linter/typechecker/compiler가 잡을 단순 항목은 LOW로 강등 (CI가 처리)
- 변경하지 않은 라인의 기존 이슈는 pre-existing으로 분리
- 단일 렌즈·저신뢰·검증불가 → "참고"로 강등
- 의도적으로 silenced된 항목(lint ignore, 안전 주석, 테스트 픽스처)은 제외

## 품질 기준
- 모든 발견에 `파일:라인` 인용 (`file` + `line_start`/`line_end`)
- CRITICAL/HIGH는 영향 + 권장 조치 필수, 담당 제안은 Claude 후속 배정에서 채운다
- 차단 판정(`needs-attention`)에 명확한 사유
- 리포트는 간결하게 (군더더기 없는 실행 가능 항목) — 단, **Codex 원문은 압축 대상이 아니다**
- **R7**: 측정·세션 기록은 한 표(명령·결과 숫자·로그 경로)면 충분하다
- 렌즈 파일(`.omc/review/{stamp}/evidence/{lens}.md`)과 verdict 파일(`.omc/review/{stamp}/verdict.md`)이
  전부 남아 재현 가능해야 한다 — verdict는 `evidence/` 밖이라는 배치를 지킨다
- `verdict.md`에 `adjudicator`(`claude-lane` | `codex`) + `reviewed_at_head` +
  `reviewed_scope_digest`가 기록되어 있어야 한다 — **세 필드 중 하나라도 없으면 통과 판정 불가**
  (`codex-gate` `## 리비전 결속`)

## 다른 하네스와의 경계
- **`code-audit` (이 스킬)**: 렌즈 팬아웃(증거 생성) + `review-synthesizer` 팬인 심판
- **일상 단일 게이트 리뷰**: `code-reviewer` 단독 호출 — 렌즈 팬아웃만 생략한다
- **`codex-gate` 스킬 / `codex-reviewer`**: 등급 A 에서 운영자가 범위·비용을 승인했을 때의
  **추가** 레인(레인 A=코드, 레인 B=계획). 기본 경로가 아니다
- 관계 정리 — 일상 PR은 `code-reviewer` 단독, 큰 변경/릴리스는 `code-audit` 팬아웃 →
  `review-synthesizer` 팬인. 차이는 렌즈 팬아웃 유무다
