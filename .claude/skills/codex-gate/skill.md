---
name: codex-gate
description: "심판 게이트 오케스트레이터. 코드와 계획의 최종 심사를 Codex(다른 모델 계열)에 위임해 자기 승인을 차단한다. 리뷰, 코드 리뷰, PR 리뷰, 머지 전 점검, 머지해도 되나, 차단 판정, 심판, 적대적 리뷰, 감사 통합, 계획 검토, 계획 리뷰, 이 계획 괜찮은지, 착수 전 점검, 릴리스 전 점검, 승격 게이트 요청 시 사용. 후속 요청 — 재리뷰, 다시 리뷰, 재심, 수정 후 재심, 지적사항 고쳤어, 계획 재검토, 리뷰 업데이트 — 에도 반드시 이 스킬로 다시 들어온다. 계획 저작은 이 스킬 소관이 아니다."
---

# Codex Gate — 심판 게이트 오케스트레이터

코드와 계획의 **최종 심사(judgment)** 를 Codex에 위임하는 게이트.
Claude는 저작하고, Codex는 심판한다.

## 왜 Codex가 심판인가

저자와 심판이 같은 모델 계열이면 리뷰는 독립 증거가 아니라 **자기 확인**이다.
이 프로젝트는 "독립 비평"과 "동일 계열 한계(same-family limitation)"를 중대하게 취급한다.
그래서 심판을 Claude 밖으로 내보낸다 — **자기 승인 방지가 이 게이트의 존재 이유다.**

## 경계 선언 (먼저 못박는다)

| 항목 | 소유 |
|------|------|
| 계획 **저작** | **이 스킬 아님** — 기존 경로 유지 (`planner`, `strategy-lab`, `frontend-lab`, `devx-harness`, `architect`) |
| 코드 **저작·수정** | **이 스킬 아님** — 구현 에이전트 소관 |
| 렌즈 감사 팬아웃 | `code-audit`이 제공 |
| **심판(팬인·판정)** | **이 스킬** |
| 수용검사·비협상 규칙 대조 | **이 스킬** (오케스트레이터) |

이 스킬은 **심판만** 소유한다. 저작 경로는 건드리지 않는다.

## 실행 모드: 하이브리드 (팀 아님)

**서브 에이전트 팬아웃/팬인으로 실행한다. `/team` 통신 모드를 쓰지 않는다.**

이유: Codex 에이전트(`codex-reviewer`, `codex-plan-reviewer`)는 stdout을 **verbatim으로 반환하는 얇은 포워더**다.
자체 판단으로 대화하지 않으므로 팀 통신(SendMessage)에 의미 있게 참여할 수 없다.
메시지를 주고받게 만들면 포워더가 요약을 시작하고 — 그 순간 verbatim이 깨지고 독립성이 소멸한다.
따라서 **팬아웃(렌즈 병렬) → 팬인(Codex 단일 심판)** 구조가 옳다.

## Phase 0 — 컨텍스트 확인 (항상 먼저)

```bash
ls -1dt .omc/review/*/ 2>/dev/null | head -5
git status --short --untracked-files=all
```

| 관측 | 판별 | 행동 |
|------|------|------|
| `.omc/review/` 없음 | **초기 실행** | 새 스탬프 생성 후 전체 레인 실행 |
| 직전 스탬프 있음 + 그 이후 코드/계획 수정됨 | **부분 재실행 (재심)** | 새 스탬프 생성 + **직전 `verdict.md` 파일 1건의 명시 경로**를 Codex에 지목해 해소 여부부터 심사 |
| 직전 스탬프 있음 + 범위가 완전히 다름 | **새 실행** | 새 스탬프, 직전 verdict 미지목 |

스탬프 생성:

```bash
command mkdir -p .omc/review                                 # 컨테이너만 -p (스탬프 아님)
STAMP="$(date +%Y%m%d-%H%M%S)"
until command mkdir ".omc/review/$STAMP" 2>/dev/null; do     # -p 아님 — 이미 있으면 실패한다
  STAMP="$(date +%Y%m%d-%H%M%S)-$RANDOM"
done
command mkdir ".omc/review/$STAMP/evidence"
echo "$STAMP"
```

`command` 를 붙이는 이유: 대화형 셸에 `alias mkdir='mkdir -pv'` 같은 별칭이 있으면
`-p`가 몰래 붙어 **충돌해도 실패하지 않는다** — 그 순간 이 가드가 통째로 무력화된다
(이 환경에서 실제로 그 별칭이 관측됐다). 별칭을 우회해야 "실패하면 새 스탬프" 계약이 성립한다.

**스탬프 디렉토리를 `mkdir -p`로 만들지 마라.** `-p`는 기존 디렉토리를 **조용히 재사용**한다.
재심은 지적 수정 직후에 일어나므로 1분 내 재실행이 드물지 않고, 분 단위 스탬프 + `-p`면
같은 디렉토리에 들어간다. 새 렌즈가 일부만 덮어쓰면 **이전 실행 증거와 이번 증거가 한 디렉토리에 섞인다.**
그래서 초 단위로 올리고, **충돌하면 실패하는 `mkdir`** 로 새 디렉토리임을 보장한다
(같은 초에 충돌하면 `-$RANDOM` 접미사로 재시도).

`.omc/`는 이미 `.gitignore` 처리되어 있다 — 산출물이 커밋을 오염시키지 않는다.

**재심에서 가장 중요한 것**: 지적이 실제로 해소되었는지 vs 회피되었는지(테스트 무력화, 조건 완화,
문구만 추가) 구별. 이걸 Codex에게 1순위로 지시한다.

## 워크스페이스 프로토콜

```
.omc/review/{YYYYMMDD-HHMMSS}/
├── evidence/          ← 렌즈 산출물만. Codex focus는 여기만 지목한다
│   ├── architecture.md
│   ├── security.md
│   ├── performance.md
│   └── style.md
└── verdict.md         ← Codex 심판 결과 (verbatim + 수용검사 기록). evidence/ 밖
```

**증거와 판정은 물리적으로 분리한다.** focus text가 지목하는 것은 항상
**`.omc/review/{stamp}/evidence/`** 이고, `verdict.md`는 그 밖에 둔다.

이유: 심판자가 읽는 표면에 **심판자의 이전 출력이 절대 들어가지 않아야** 자기 되먹임이
구조적으로 불가능해진다. 스탬프 디렉토리를 통째로 지목하면 재실행·부분 재실행에서
Codex가 자기 이전 `verdict.md`를 "렌즈 증거"로 읽는다 — 자기 출력을 입력으로 되먹이는 오염이고,
독립 심판의 전제가 깨진다. **산문 규칙이 아니라 경로 구조로 막는 것이 요점이다.**

**렌즈 결과 본문을 Codex 커맨드라인 인자로 통째로 넘기지 마라.**
Codex는 repo-aware CLI다 — focus text로 `.omc/review/{stamp}/evidence/` 경로를 지목하면 직접 읽는다.
본문을 붙이면 인자 길이가 폭발하고 잘린다.

## 레인 A — 코드 심판

```
범위 결정 (diff / PR #N / 경로)
    ↓ fan-out (Claude 4렌즈 병렬 — 한 메시지에서 동시 dispatch)
architecture-auditor + security-auditor + performance-auditor + style-auditor
    ↓ 각 렌즈가 .omc/review/{stamp}/evidence/{lens}.md 로 산출
    ↓ fan-in
codex-reviewer  (adversarial-review, focus = .omc/review/{stamp}/evidence/)
    ↓
verdict(approve | needs-attention) + findings + next_steps
    ↓ → .omc/review/{stamp}/verdict.md  (evidence/ 밖 — 심판 입력 표면에서 제외)
    ↓ 수용검사 (오케스트레이터 = Claude)
    ↓ needs-attention → 담당 에이전트로 수정 위임 → 재심 (Phase 0으로 복귀)
    ↓ approve → 게이트 통과
```

### 경량 경로 (렌즈 팬아웃 생략)

단일 소규모 변경(1~2파일, 명확한 범위)은 **렌즈 팬아웃 없이 `codex-reviewer` 단독**으로 간다.
**경량화되는 것은 렌즈 4종 생략이지 심판 경로 교체가 아니다** — 호출은 여전히 `adversarial-review`다.
판정을 내야 하는 이상 규모와 무관하게 게이트 적격 경로를 쓴다 (아래 "게이트 적격 경로" 절).

| 변경 규모 | 경로 |
|-----------|------|
| 1~2파일, 명확 | `codex-reviewer` 단독 `adversarial-review` (foreground) — 렌즈 팬아웃만 생략 |
| 그 외 / 큰 변경 / 릴리스 전 / 승격 게이트 | 4렌즈 팬아웃 → `codex-reviewer` `adversarial-review` (background) |

### 게이트 적격 경로 (판정을 낼 수 있는 경로는 하나뿐이다)

| 서브커맨드 | 출력 | 게이트 적격 |
|-----------|------|------------|
| `adversarial-review` | `{verdict, summary, findings[], next_steps[]}` 구조화 출력 | **적격 — 유일** |
| `review` (네이티브 내장 리뷰어) | free-form 텍스트, **`verdict` 필드 없음** | **부적격 — 보조 패스** |

근거 (플러그인 업그레이드 시 **이 두 지점을 재확인**한다):

- `codex-companion.mjs:370-407` — 네이티브 `review`는 `result.reviewText`를 그대로 렌더한다.
  `outputSchema` 미부착, `parseStructuredOutput` 미호출 → **verdict가 존재하지 않는다**
- `codex-companion.mjs:409-417` — `adversarial-review`만 `outputSchema: readOutputSchema(REVIEW_SCHEMA)`를
  부착하고 `:418`에서 `parseStructuredOutput`으로 구조화 파싱한다
- `scripts/lib/render.mjs:24-40` `validateReviewResultShape`는 `verdict`/`summary`/`findings`/`next_steps`를
  요구하며, 없으면 `renderReviewResult`(`:211-250`)가 "Parse error + Raw final message"로 떨어진다

**`review` 출력으로는 approve / needs-attention을 선언할 수 없다.** 그 출력은 사람이 읽을
추가 관점일 뿐이며, 게이트 통과 근거로 인용하는 것 자체가 결함이다.

### 수정 위임 (needs-attention 이후)

finding별로 담당을 배정한다 — **오케스트레이터가 직접 고치지 않는다.**

| finding 영역 | 담당 |
|-------------|------|
| 중복·구조 정리 | `refactorer` |
| 주문 실행·KIS 정합 | `execution-specialist` |
| 데이터 수집·품질 | `data-engineer` |
| 전략 로직·YAML | `strategy-architect` |
| 테스트 보강 | `test-engineer` |
| 프론트엔드 | `ui-engineer` / `frontend-realtime-engineer` |
| CI·컨테이너·flaky | `ci-pipeline-engineer` / `container-engineer` / `test-reliability-engineer` |

수정 완료 후 **반드시 재심**한다. 수정만 하고 통과시키면 게이트가 아니다.

## 레인 B — 계획 심판

```
Claude 측이 계획 저작 (기존 경로 — strategy-lab / frontend-lab / devx-harness / planner / architect)
    ↓
codex-plan-reviewer 심판
    ↓ needs-attention → 저작자가 계획 개정 → 재심 (저작자 ≠ 심판 유지)
    ↓ approve
실행 착수
```

**개정은 저작자가 한다.** 심판이 계획을 고치면 심판이 저자가 되고, 다음 심사는 자기 승인이 된다.

### 계획 심사 기준 (`codex-plan-reviewer`에 전부 주입)

1. 단계 순서·의존성이 실제로 성립하는가 (선행 없이 착수하는 단계)
2. 숨은 가정 — 무엇이 참이어야 하는가, 검증되었는가
3. 검증 가능성 — **증명 수단 없는 단계는 결함이다**
4. 실패·롤백 경로
5. 범위 이탈·과잉 설계·불필요한 신규 표면
6. `CLAUDE.md` 비협상 규칙 충돌 (**Codex에게 CLAUDE.md를 먼저 읽으라고 명시**)
7. 누락 — 설정·마이그레이션·테스트·문서·운영

## 수용검사 (Claude 몫 — 반드시 수행)

**Codex verdict를 그대로 통과시키지 마라.** 오케스트레이터가 아래를 확인한다.

| 검사 | 방법 | 불합격 시 |
|------|------|----------|
| `file:line`이 실재하는가 | 해당 파일·라인 실측 | 팬텀 finding — 기각, 사유 기록 |
| 이미 의도적으로 silenced인가 | lint ignore, 안전 주석, 테스트 픽스처 확인 | 기각, 사유 기록 |
| CLAUDE.md 비협상 규칙과 배치되는 권고인가 | 아래 목록 대조 | **기각, 사유 기록** |
| 변경 범위 밖 기존 부채인가 | diff 대조 | pre-existing으로 분리 (비차단) |

### 심판 에이전트는 전역, 대조 목록은 이 스킬 소유

심판 에이전트 2종(`codex-reviewer`, `codex-plan-reviewer`)은 **전역 `~/.claude/agents/`에 있다.**
프로젝트 `.claude/agents/`에는 사본을 두지 않는다 — 두 벌을 유지하면 드리프트가 생긴다.

계층은 이렇게 갈린다:

| 층 | 소유 |
|----|------|
| **심판 절차** (Codex 호출 규약·모드 선택·verbatim·에러 핸들링) | 전역 에이전트 |
| **이 repo의 비협상 대조 목록** (아래 8항목) | **이 스킬** |

전역 에이전트는 "그 repo의 `CLAUDE.md`(없으면 `AGENTS.md`)를 먼저 읽으라"는 일반 지시만 갖고 있다.
**이 스킬이 있을 때는 아래 목록이 그보다 구체적이므로 이쪽이 우선한다** — 오케스트레이터가
focus text에 주입하고, 수용검사도 이 목록으로 한다.

### 비협상 규칙 대조 목록 (배치되면 즉시 기각)

- 선물 **long/short 대칭** 훼손을 요구하는 권고
- **실계좌 증거금** 입금·실물 선물 주문 경로를 전제하는 제안 (운영자 지시로 영구 차단)
- 주식 **EOD 일괄청산** 도입 (스윙 청산은 시그널 구동)
- **ClickHouse 신규 사용** 추가
- **RL/TFT 경로 부활** (`sts rl *`, `sts tft *`, `shared/ml/rl`, `shared/ml/tft`)
- 임계값·심볼·포트·Redis DB·스케줄의 **하드코딩** 권고 (설정 구동만 허용)
- Redis **DB 1 이탈**, TTL 없는 신규 키
- KST가 아닌 타임존으로 세션 로직 판정

> **Codex는 심판이지, 이 repo의 비협상 규칙 위에 있지 않다.**
> 기각한 finding은 `verdict.md`에 **기각 사유와 함께 기록**한다 — 조용히 버리면 다음 재심에서 되살아난다.

기각은 판정 뒤집기가 아니다. **verbatim 원문은 그대로 보존**하고, 수용검사 결과를 **별도 섹션**으로 덧붙인다.

## 호출 규약 (Codex companion CLI)

`${CLAUDE_PLUGIN_ROOT}`는 codex 플러그인 자체 커맨드/에이전트에서만 설정된다.
**이 프로젝트 에이전트에서는 설정되지 않는다.** 매 호출마다 해석한다:

```bash
CODEX="$(ls -d "$HOME"/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)"
[ -n "$CODEX" ] || { echo "CODEX_UNAVAILABLE"; exit 1; }
node "$CODEX" <subcommand> ...
```

**버전 하드코딩 금지** — 플러그인 업그레이드 시 조용히 깨진다 (CLAUDE.md "하드코딩 금지"와 같은 규칙).

```
review             [--wait|--background] [--base <ref>] [--scope auto|working-tree|branch]
adversarial-review [--wait|--background] [--base <ref>] [--scope auto|working-tree|branch] [focus text]
task               [--background] [--write] [--resume-last|--fresh] [--model <m>]
                   [--effort none|minimal|low|medium|high|xhigh] [prompt]
status [job-id] [--all] [--json]
result [job-id] [--json]
cancel [job-id] [--json]
```

### 불변 규칙

| 규칙 | 이유 |
|------|------|
| **슬래시 커맨드 호출 불가** (`/codex:review`, `/codex:adversarial-review`) | `disable-model-invocation: true` — 에이전트가 부를 수 없다. companion을 Bash로 직접 실행 |
| **`--write` 절대 금지** | 심판이 수정하면 피심판자가 된다. `task`도 `--write` 없이 read-only |
| **`review`는 focus text도 verdict도 없다** | 내장 리뷰어 직결 = 플러그인이 프롬프트도 스키마도 주입 못 함 (`codex-companion.mjs:370-407`). focus가 필요하거나 **판정이 필요하면 반드시 `adversarial-review`** (`:409-417`) |
| **verbatim 반환** | 피심판자가 요약하면 severity가 눌리고 불편한 finding이 탈락한다 — 독립 심사의 의미가 소멸 |
| **untracked 포함** | `git status --short --untracked-files=all`로 확인. 신규 파일은 `--scope working-tree` 필요 |

### 출력 스키마 (플러그인이 `adversarial-review`에만 강제)

```
{ verdict: "approve" | "needs-attention",
  summary: string,
  findings: [{ severity: critical|high|medium|low, title, body,
               file, line_start, line_end, confidence(0..1), recommendation }],
  next_steps: [string] }
```

### 심판자 식별 필드 (`adjudicator`) — 오케스트레이터가 부여

`verdict.md`에 기록할 때 **최상위에 `adjudicator` 필드를 반드시 넣는다.**

| 값 | 언제 |
|----|------|
| `"codex"` | Codex `adversarial-review`가 낸 판정 |
| `"fallback-claude"` | 폴백(`review-synthesizer` / `code-reviewer` / `critic`)이 낸 판정 |

**이 필드는 오케스트레이터가 부여한다.** Codex의 JSON 스키마 자체는 플러그인 소유라 바꿀 수 없다 —
따라서 Codex 출력 본문은 verbatim으로 두고, `verdict.md`로 기록하는 시점에 이 필드를 덧붙인다.

이유: 하류가 **산문이 아니라 구조로** 심판자를 구별할 수 있어야 한다.
"[FALLBACK] 이 판정은 잠정" 같은 배너 문구는 기계적 구별자가 아니다.

## Stop 리뷰 게이트와의 구분

`/codex:setup --enable-review-gate`로 **Stop 훅**이 활성화되어 있다.
Claude 턴이 코드 변경을 만들면 자동으로 Codex 심사가 돌고 ALLOW/BLOCK을 낸다.

| | Stop 리뷰 게이트 | codex-gate (이 스킬) |
|---|---|---|
| 발동 | 자동 (턴 종료 시) | 명시적 호출 |
| 단위 | 턴 단위 변경 | 범위 단위 (diff/PR/경로/계획) |
| 산출 | ALLOW / BLOCK | verdict + findings + next_steps + `verdict.md` |
| 렌즈 증거 | 없음 | 4렌즈 팬아웃 동반 가능 |
| 계획 심사 | 불가 | 레인 B |

**서로 대체 관계가 아니다.** Stop 훅은 턴 단위 자동 안전망이고, 이 스킬은 명시적 게이트다.
Stop 훅이 ALLOW를 냈다는 것이 이 게이트를 통과했다는 뜻이 아니다.

## 에러 핸들링

```
1회 재시도 (범위 축소 — 파일 수/경로 좁히기)
    ↓ 재실패
폴백 강등 + [FALLBACK] 명시 (필수)
```

| 증상 | 대응 |
|------|------|
| companion 미발견 / auth 만료 / 네트워크 / rate limit / 비인증 | 1회 재시도 → 폴백 |
| 백그라운드 잡이 매달림 | `node "$CODEX" cancel <job-id> --json` → 범위 축소 재시도 |
| "변경 없음" 판정 | 범위 지정 실수 우선 의심 → `--scope working-tree`로 재시도 |
| verdict가 스키마를 벗어남 | 원문 그대로 보존 + 스키마 이탈 사실 명기 |
| **출력에 `verdict`가 없음 / "Parse error"로 떨어짐** | **그 자체를 게이트 실패로 취급 (fail-closed)**. approve로 넘기지 않는다 |

**판정 불능 = 실패이지 통과가 아니다 (fail-closed).** `verdict` 필드가 없거나
`renderReviewResult`가 "Parse error + Raw final message"로 떨어졌다면 심판은 **판정을 내지 못한 것**이다.
이것을 통과로 읽으면 게이트가 무의미해진다 — 판정 없는 통과는 심판 없는 승인과 같고,
그 순간 자기 승인 방지라는 이 게이트의 존재 이유가 소멸한다.
먼저 **서브커맨드가 `adversarial-review`였는지 확인**하라 (`review`를 썼다면 verdict 부재는
버그가 아니라 그 경로의 정상 동작이다 — 위 "게이트 적격 경로" 절). 맞게 호출했는데도
verdict가 없으면 1회 재시도 후 실패로 보고한다.

### 폴백 정책

**Codex 미가용일 때만** Claude 측 `code-reviewer` / `review-synthesizer`(코드) 또는
`critic`(계획)으로 강등한다. 강등 리포트 **최상단에 반드시**:

```
[FALLBACK: 비독립 심판 — 동일 모델 계열]
```

**폴백을 조용히 수행하는 것은 결함이다.** 이 프로젝트는 "독립 비평"과 "동일 계열 한계"를
중대하게 취급한다 — 표시 없는 폴백은 비독립 심판을 독립 심판으로 위장시킨다.
Codex가 복구되면 **폴백 판정은 잠정이며 재심 대상**임을 명기한다.

#### 폴백은 `approve`를 낼 수 없다

**발견이 0건이어도 폴백 판정은 `needs-attention`이다.** `next_steps`에
"Codex 복구 후 `codex-reviewer` 재심 필수"를 넣고, `verdict.md`에 `adjudicator: "fallback-claude"`를 기록한다.

이유: 폴백이 낼 수 있는 **가장 강한 주장은 "내가 본 범위에선 차단 사유를 못 찾았다"이지 "통과"가 아니다.**
비독립 심판자에게 통과 권한을 주면 폴백이 게이트 우회로가 된다 — Codex를 잠깐 못 쓰는 것만으로
Claude가 Claude의 작업을 승인한 결과물이 정상 통과와 **구별 불가능한 형태로** 나온다.
배너 문구는 산문일 뿐 기계적 구별자가 아니므로, 값 자체를 막는다.

**품질 게이트 통과는 `adjudicator: "codex"` + `verdict: approve`의 조합에서만 성립한다.**
폴백 산출물(`adjudicator: "fallback-claude"`)은 어떤 값이든 게이트를 통과시키지 못한다
(위 fail-closed 규칙과 같은 성질이다 — 판정 불능도, 비독립 판정도 통과가 아니다).

## 다른 하네스와의 경계

| 하네스 | 역할 | 관계 |
|--------|------|------|
| `code-audit` | 4렌즈 팬아웃(증거 생산) | **팬인 심판은 이 스킬이 소유** |
| `codex-reviewer` | 코드 심판 (Codex 포워더) | 이 스킬이 호출 |
| `codex-plan-reviewer` | 계획 심판 (Codex 포워더) | 이 스킬이 호출 |
| `code-reviewer` / `review-synthesizer` | **폴백 전용으로 격하** | Codex 미가용 시에만 |
| `critic` / `momus` | 계획 리뷰 — **폴백 전용으로 격하** | Codex 미가용 시에만 |
| Claude 저작 경로 (`planner`, `strategy-lab`, `frontend-lab`, `devx-harness`) | 계획·코드 저작 | **변경 없음 — 그대로 유지** |

## 테스트 시나리오

### 시나리오 1 — 정상 흐름 (코드 심판, 큰 변경)

```
입력: "shared/execution 변경 리뷰해줘"
1. Phase 0: .omc/review/ 없음 → 초기 실행. STAMP=20260811-143052 생성 (충돌 시 실패하는 mkdir)
2. git status --untracked-files=all → 변경 6파일 + 신규 2 (untracked) 확인
3. fan-out: 4렌즈 병렬 dispatch
   → .omc/review/20260811-143052/evidence/{architecture,security,performance,style}.md
4. fan-in: codex-reviewer 호출
   node "$CODEX" adversarial-review --background --scope working-tree \
     "4렌즈 증거가 .omc/review/20260811-143052/evidence/ 에 있다. 먼저 읽고 독립 검증하라. CLAUDE.md도 읽어라."
   → job-id 반환
5. status → result 회수 → verdict: needs-attention, findings 3건
6. 수용검사: finding#2가 "EOD 일괄청산 추가" 권고 → 비협상 규칙 배치 → 기각, 사유 기록
   finding#1, #3은 file:line 실재 확인 → 채택
7. verdict.md 기록 — adjudicator: "codex" + verbatim 원문 + 수용검사 섹션
   (evidence/ 밖에 쓴다 — 다음 심판의 입력 표면에 들어가지 않게)
8. finding#1 → execution-specialist, #3 → test-engineer 위임
9. 수정 완료 → Phase 0 복귀 (재심: 새 스탬프 + 직전 .omc/review/20260811-143052/verdict.md 파일 1건 지목)
기대: 채택 2건 해소 확인 + 기각 1건이 재심에서 되살아나지 않음
```

### 시나리오 2 — 에러 흐름 (Codex 인증 만료)

```
입력: "이 PR 머지해도 되나"
1. Phase 0 정상, STAMP 생성
2. codex-reviewer 호출 → stderr "401 unauthorized"
   → 에이전트가 CODEX_UNAVAILABLE: 인증 만료 반환 (성공한 척하지 않음)
3. 1회 재시도 (범위 축소) → 동일 실패
4. 폴백 강등: code-reviewer + review-synthesizer 호출
5. 리포트 최상단에 [FALLBACK: 비독립 심판 — 동일 모델 계열] 명시
6. 폴백은 차단 항목 0건이어도 verdict: needs-attention (approve 불가)
7. verdict.md에 adjudicator: "fallback-claude" + 폴백 사유 + next_steps "Codex 복구 후 재심 필수" 기록
기대: 폴백 표시 누락 없음. adjudicator 필드만으로 하류가 비독립 판정임을 구조로 식별.
      이 판정으로 승격 게이트를 통과시키지 않음
```

### 시나리오 3 — 에러 흐름 (백그라운드 잡 매달림)

```
1. adversarial-review --background → job-id 획득
2. status 반복 확인 → 진행 없음
3. node "$CODEX" cancel <job-id> --json
4. 범위 축소 (경로를 shared/execution/ 하위 1개 모듈로) 후 재시도
5. 여전히 실패 → 폴백 정책 진입 ([FALLBACK] 명시)
기대: job이 유실되지 않고 취소 기록이 남음
```

## 품질 기준

- 모든 finding에 `파일:라인` 인용 — **실재 여부는 오케스트레이터가 검증**
- verdict 원문은 **verbatim 보존**. 수용검사는 별도 섹션으로 덧붙임
- 기각한 finding은 **기각 사유를 반드시 기록** (조용히 버리지 않는다)
- `verdict.md`에 **`adjudicator`(`codex` | `fallback-claude`) 기록** — 하류가 구조로 심판자를 식별
- 폴백 시 `[FALLBACK: 비독립 심판 — 동일 모델 계열]` **최상단 명시** + **`approve` 금지**
- 렌즈 산출물은 `evidence/` 안, `verdict.md`는 `evidence/` **밖** — focus 지목은 `evidence/`만
- needs-attention 후 수정했으면 **반드시 재심** — 수정만으로 통과시키지 않는다
