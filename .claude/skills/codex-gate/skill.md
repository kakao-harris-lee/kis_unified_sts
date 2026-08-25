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

**Codex를 디스패치하기 직전에 심사 대상 리비전을 포착한다** (아래 "리비전 결속" 절):

```bash
git rev-parse HEAD                    # → verdict.md 의 reviewed_at_head (두 레인 공통)
review_scope_digest                   # 레인 A(코드): 작업 트리 전체
plan_scope_digest <계획 문서 경로들>   # 레인 B(계획): 그 문서들만 + reviewed_plan_paths 기록
```

**레인에 따라 결속 범위가 다르다** — 함수 정의와 방향 선택 근거는 아래 "리비전 결속" 절 한 곳에 있다.

포착 시점은 **Codex가 트리(레인 B는 계획 문서)를 읽는 시점과 같아야 한다.** 먼저 계산해두고
그 사이에 편집이 들어가면 digest는 심판이 실제로 본 상태가 아닌 것을 가리킨다 — 결속이 거짓이 된다.

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
                       필수 필드: adjudicator / reviewed_at_head / reviewed_scope_digest
                       (레인 B는 + reviewed_plan_paths)
                       ("리비전 결속" 절 — 이것들이 없으면 통과 판정 불가)
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
    ↓ (디스패치 직전 리비전 포착: reviewed_at_head / reviewed_plan_paths / reviewed_scope_digest)
    ↓ → .omc/review/{stamp}/verdict.md
    ↓ needs-attention → 저작자가 계획 개정 → 재심 (저작자 ≠ 심판 유지)
    ↓ approve
    ↓ 실행 착수 직전 plan_scope_digest 재계산·대조
    ↓   불일치 = 승인 후 계획이 개정됨 → approve 무효, 재심 (Phase 0 복귀)
    ↓   기록 없음 · 계산 불가 · 경로 소실 = 착수 불가 (fail-closed)
실행 착수
```

**개정은 저작자가 한다.** 심판이 계획을 고치면 심판이 저자가 되고, 다음 심사는 자기 승인이 된다.

**레인 B도 리비전에 결속된다.** 결속하지 않으면 레인 A와 같은 결함 클래스가 남는다 —
계획이 approve를 받은 뒤 개정되면 **그 개정본이 심사를 우회한다.** 필드명·판정 어휘는 레인 A와
동일하고 **결속 범위만 계획 문서로 좁다.** 규칙은 아래 "리비전 결속" 절 **한 곳**에 두 레인이
나란히 적혀 있다 (여기서 되풀이하지 않는다 — 중복 저작은 드리프트를 만든다).

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

**기각 가능 사유는 위 3가지뿐이다** — 팬텀 `file:line`(실측 부재) / 의도적으로 silenced된 항목 /
비협상 규칙 배치. **그 외 사유로는 기각할 수 없다.** "동의하지 않음", "우선순위 낮음", "나중에"는
기각이 아니라 **미해결**이다 (네 번째 행 pre-existing 분리는 기각이 아니라 비차단 분류다).

**수용검사는 게이트를 여는 장치가 아니다.** finding을 전부 기각해도 게이트는 여전히
**Codex가 낸 새 `verdict: approve`로만** 열린다. 기각의 용도는 둘뿐이다 —
(a) 해당 finding이 다음 재심에서 되살아나지 않게 사유와 함께 기록하고,
(b) 재심에 들어갈 때 Codex에게 기각 사유를 함께 제시한다(판단은 심판이 한다).
피심판자가 자기 판단으로 finding을 지우고 통과할 수 있으면 심판자를 둔 의미가 소멸한다 —
그것이 정확히 이 게이트가 막으려는 자기 승인이다.

### 심판 에이전트는 이 프로젝트 소속, 대조 목록은 이 스킬 소유

심판 에이전트 2종(`codex-reviewer`, `codex-plan-reviewer`)은 **이 repo의
`.claude/agents/`에 있다.** 전역 `~/.claude/agents/`에는 두지 않는다 — 전역에 두면
심판 레인이 없는 모든 프로젝트까지 codex 리뷰가 새어 들어간다(운영자 지시, 2026-08-20).
사본은 여전히 한 벌뿐이므로 드리프트는 생기지 않는다.

codex 심판 레인을 쓰는 프로젝트는 `kis_unified_sts` / `bid-vector` / `easy-doc` 셋뿐이며,
`bid-vector`는 `scripts/codex-review-kotlin.sh`, `easy-doc`은 자체
`.claude/agents/codex-reviewer.md`로 각자 레인을 소유한다. 이 두 벌은 이 파일의 사본이 아니다.

**⚠ 이 프로젝트에서는 stop-time 게이트를 모든 워크트리에서 꺼 둔다.** codex 플러그인은
`git rev-parse --show-toplevel` 결과를 workspace 키로 쓰므로 **워크트리는 각각 별개 workspace다**
(`plugins/data/codex-openai-codex/state/<basename>-<hash>/state.json::config.stopReviewGate`).
기존 워크트리에서 켜져 있으면 `/codex:setup --disable-review-gate`로 끄고,
새 워크트리에서도 `/codex:setup --enable-review-gate`를 실행하지 않는다. 현재 플러그인의 Stop 훅은
매 종료 시도마다 게이트 적격 `adversarial-review`가 아닌 새 generic `task`를 만들며, 이미 명시적 리뷰가
실행 중이어도 중복 실행할 수 있다. 코드 변경 전용 프롬프트라 계획 심사도 대신하지 못한다.

계층은 이렇게 갈린다:

| 층 | 소유 |
|----|------|
| **심판 절차** (Codex 호출 규약·모드 선택·verbatim·에러 핸들링) | 이 repo의 심판 에이전트 |
| **이 repo의 비협상 대조 목록** (아래 8항목) | **이 스킬** |

심판 에이전트는 "그 repo의 `CLAUDE.md`(없으면 `AGENTS.md`)를 먼저 읽으라"는 일반 지시만 갖고 있다.
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

기각은 판정 뒤집기도, 게이트 통과도 아니다. **verbatim 원문은 그대로 보존**하고, 수용검사 결과를
**별도 섹션**으로 덧붙인다. 재심을 호출할 때는 기각 사유를 focus text에 함께 제시해
같은 finding이 되살아나는지를 **심판이** 판단하게 한다.

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

## 리비전 결속 — approve는 심사한 그 내용에 대한 진술이다 (레인 A·B 공통)

**승인은 시각에 대한 진술이 아니라 심사한 내용에 대한 진술이다** (레인 A = 코드 상태,
레인 B = 계획 내용). Codex가 승인한 것은 "이 repo"나 "그 문서"가 아니라
**심사 시점의 그 내용**이다. 내용이 바뀌면 진술의 대상이 사라지고,
남은 `approve`는 더 이상 아무것도 승인하지 않는다.

이 결속이 없으면 게이트에 다음 우회로가 열린다:

```
Codex가 상태 X를 승인 → Claude가 계속 수정 → 상태 Y가 "승인됨"으로 통과
```

**승인 이후의 편집이 심사를 통째로 우회한다.** 게이트를 아무리 단일 조건으로 좁혀도
이 구멍이 있으면 나머지 규칙 전부가 무의미해진다 — 자기 승인을 막아도
"심사받지 않은 코드의 통과"는 그대로 남기 때문이다.

**이 규율은 이 repo에 이미 있다.** 증거 하네스의 `harness_at_commit`(= git blob id),
EV 실행의 baseline staleness 게이트(`NO_PRIOR_EV_L1_RUN_AT_THIS_BASELINE`), lineage digest 결속 —
전부 "이 산출물이 **어떤 상태를** 측정한 것인가"를 구조로 못박는다.
**심판 레인만 이 규율이 빠져 있었다.** 같은 규율을 여기에 적용한다.

### `verdict.md` 필수 필드 (레인 A 3종 / 레인 B 4종)

| 필드 | 값 | 용도 |
|------|-----|------|
| `adjudicator` | `codex` \| `fallback-claude` | 심판자 식별 (위 절) |
| `reviewed_at_head` | `git rev-parse HEAD` 출력 | 심사 시점의 커밋 (두 레인 공통) |
| `reviewed_scope_digest` | 아래 스니펫 출력 (64자 hex) | 심사한 **내용**의 지문 (레인별 범위 다름) |
| `reviewed_plan_paths` | 심사한 계획 문서 경로 목록 | **레인 B 전용** — 결속 범위 자체의 명시 기록 |

`reviewed_at_head`만으로는 부족하다 — 이 게이트는 대부분 **미커밋 작업 트리**(레인 B는 방금 쓰여
아직 커밋되지 않은 계획 문서)를 심사하므로 HEAD가 그대로여도 내용은 얼마든지 바뀐다.
커밋 해시는 필요조건이지 충분조건이 아니다.

### 범위 digest 계산 (레인 A — 코드 작업 트리)

```bash
review_scope_digest() {
  set -o pipefail
  {
    git rev-parse HEAD                                  || return 1
    git diff HEAD                                       || return 1  # 추적 파일 내용 (staged+unstaged)
    git status --porcelain=v1 --untracked-files=all     || return 1  # 파일 단위 상태 (미추적 이름 포함)
    git ls-files --others --exclude-standard -z \
      | sort -z | xargs -0 -r shasum -a 256             || return 1  # 미추적 파일 *내용*
  } | shasum -a 256 | cut -d' ' -f1
}
```

**네 번째 줄이 핵심이다.** `git diff HEAD`는 추적 파일만 덮고, `git status --porcelain`은
미추적 파일의 **이름만** 싣는다. 그 둘만 쓰면 신규 파일을 만들어 심사받은 뒤
**같은 이름으로 내용을 갈아끼워도 digest가 변하지 않는다** — 신규 파일이 심사를 우회하는 경로가
그대로 남는다. `git ls-files --others`로 미추적 파일의 **내용**까지 넣어야 그 구멍이 닫힌다
(`sort -z`는 디렉토리 순회 순서에 따른 digest 흔들림을 막는다).

**`.omc/`는 digest에 들어가지 않는다** — `.gitignore` 처리되어 있어 `--exclude-standard`와
`--porcelain`이 둘 다 제외한다. 이것은 우연이 아니라 **요구되는 성질**이다:
`verdict.md`를 쓰는 행위가 digest를 바꾸면 **기록하는 순간 자기 자신을 무효화한다.**
측정이 스스로를 무효화해서는 안 된다.

### 레인 B — 계획 문서로 좁혀 결속한다

**필드명·판정 어휘는 레인 A와 같다. 다른 것은 결속 범위 하나뿐이다.**

| 필드 | 레인 A (코드) | 레인 B (계획) |
|------|--------------|--------------|
| `adjudicator` | `codex` \| `fallback-claude` | 동일 |
| `reviewed_at_head` | `git rev-parse HEAD` | 동일 |
| `reviewed_plan_paths` | — | **심사한 계획 문서 경로 목록** (repo 루트 기준 상대경로) |
| `reviewed_scope_digest` | `review_scope_digest` (작업 트리 전체) | `plan_scope_digest <경로들>` (그 문서들만) |

```bash
plan_scope_digest() {                                  # 인자: 심사한 계획 문서 경로들
  set -o pipefail
  [ "$#" -gt 0 ] || return 1                           # 대상 0건 = 범위 미확정 → 실패
  for p in "$@"; do [ -f "$p" ] || return 1; done      # 경로 소실 → 실패 (fail-closed)
  {
    git rev-parse HEAD                          || return 1
    printf '%s\0' "$@" | LC_ALL=C sort -z -u \
      | xargs -0 -r shasum -a 256               || return 1   # 경로 + 워킹트리 실제 내용
  } | shasum -a 256 | cut -d' ' -f1
}
```

**워킹트리 내용을 해싱한다.** 계획 문서는 커밋된 것·미커밋인 것·커밋 후 수정중인 것이 섞인다.
커밋본만 다루면 `git hash-object <path>`(blob id)로 충분하지만 그것은 **커밋 상태만** 가리켜
커밋 후 편집을 놓친다. 워킹트리 해싱은 세 경우를 **한 방식으로** 덮으므로 분기 자체가 없어진다.

**경로도 digest에 들어간다** — `shasum` 출력이 `<hash>  <경로>` 형태라 경로가 입력에 그대로 실린다.
**파일 목록이 바뀌는 것도 범위 변경이다**: 문서를 추가·제거·개명하면 digest가 달라져야 한다.
`sort -z -u`는 인자 순서 차이로 인한 **거짓 불일치**를 막는다 (같은 집합이면 같은 digest).
경로는 **repo 루트 기준 상대경로로 통일**한다 — 같은 파일이라도 표기가 바뀌면 digest가 달라진다.

#### 과잉 무효화 방향 — 레인 B는 반대로 좁힌다 (명시적 선택)

레인 A는 작업 트리 전체를 결속해 **과잉 무효화 쪽**으로 붙였다 (아래 절). 레인 B는 계획 문서만
결속하므로 **무관한 코드 변경이 계획 approve를 무효화하지 않는다.** 전체 트리 digest를 쓰면
계획과 무관한 코드 한 줄 수정마다 계획 재심이 걸려 게이트가 실효를 잃기 때문이다.

**대가**: 계획이 전제한 코드가 바뀌어도 계획 approve는 살아남는다 —
**그 경우 재심을 요청할 책임은 저작자에게 있다.**

방향이 갈리는 근거: 레인 A가 막는 것은 "심사받지 않은 **코드**의 통과"이고, 레인 B가 막는 것은
"심사받지 않은 **계획**의 착수"다. 각 레인은 자기 심사 대상에 결속한다. 계획 문서 자체의 변경에
대해서는 레인 B도 레인 A와 똑같이 기계적이다 — **digest가 다르면 무효.**

### 게이트 통과 시점에 재계산·대조 (필수)

승인을 인용하는 시점 — 레인 A는 머지·승격 인용 시점, **레인 B는 실행 착수 시점** — 에
digest를 **다시 계산해서** `verdict.md`에 기록된 값과 대조한다.
레인 A는 `review_scope_digest`, 레인 B는 `plan_scope_digest`에 기록된 `reviewed_plan_paths`를
**그대로** 넣어 재계산한다 (경로 목록을 임의로 바꾸면 대조 자체가 다른 범위를 재는 것이 된다).

| 관측 | 판정 |
|------|------|
| 재계산 digest == 기록된 `reviewed_scope_digest` | 리비전 결속 성립 — 나머지 게이트 조건 평가로 진행 |
| 재계산 digest != 기록된 값 | **approve 무효.** 승인 이후 코드(레인 B는 계획)가 바뀌었다 → **재심 대상** (Phase 0 복귀) |
| `verdict.md`에 `reviewed_scope_digest` 없음 (레인 B는 `reviewed_plan_paths`도) | **통과 아님 (fail-closed)** — 무엇을 승인한 것인지 알 수 없다 |
| digest 계산 실패 (git 실패 · 빈 출력 · 64자 hex 아님 · **레인 B: 계획 경로 소실 · 대상 0건**) | **통과 아님 (fail-closed)** — 대조 불능은 일치가 아니다 |

**승인 이후의 어떤 변경이든 `approve`를 무효화한다.** 변경이 사소한지, 무관한 파일인지,
"지적과 상관없는 오타 수정"인지는 **피심판자가 판단할 사항이 아니다** — 그 판단을 허용하는 순간
피심판자가 심사 범위를 스스로 정하게 되고, 그것이 정확히 이 레인이 막으려는 자기 승인이다.
무효화 판정은 기계적이다: **digest가 다르면 무효.**

**레인 A의 digest는 repo 전체 범위이므로 과잉 무효화가 일어난다** (심사 범위 밖 파일을 고쳐도 무효).
이것은 결함이 아니라 **선택된 방향**이다 — 과잉 무효화의 비용은 재심 1회이고,
과소 무효화의 비용은 **심사받지 않은 코드의 통과**다. fail-closed 쪽으로 붙인다.
**레인 B는 반대 방향을 선택했고 그 대가까지 위 절에 명기되어 있다** — 조용히 좁힌 것이 아니다.

### 게이트 통과 조건 (최종형)

```
레인 A: adjudicator: codex + verdict: approve + reviewed_scope_digest == 현재 review_scope_digest
레인 B: adjudicator: codex + verdict: approve + reviewed_scope_digest == 현재 plan_scope_digest(reviewed_plan_paths)
```

세 조건은 **AND**다. 어느 하나라도 불성립·확인 불능이면 통과가 아니다.
레인 B에서 "통과 아님"은 **실행 착수 불가**를 뜻한다.

## Stop 리뷰 게이트와의 구분

이 프로젝트에서는 `/codex:setup --disable-review-gate` 상태를 유지한다. Codex 플러그인은 활성화한 채
리뷰가 필요한 체크포인트에서만 명시적으로 호출한다.

| | Stop 리뷰 게이트 | codex-gate (이 스킬) |
|---|---|---|
| 상태/발동 | **비활성 유지** (턴 종료마다 generic task를 만들지 않음) | 명시적 호출 |
| 단위 | 턴 단위 변경 | 범위 단위 (diff/PR/경로/계획) |
| 산출 | ALLOW / BLOCK | verdict + findings + next_steps + `verdict.md` |
| 렌즈 증거 | 없음 | 4렌즈 팬아웃 동반 가능 |
| 계획 심사 | 불가 | 레인 B |

일반 코드 관점이 필요하면 `/codex:review --background --scope working-tree`, 판정이나 설계 도전이
필요하면 이 스킬의 `adversarial-review` 경로를 사용한다. 계획은 반드시 레인 B로 심사한다.
Stop 훅을 이 스킬의 자동 안전망으로 다시 켜지 않는다.

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
| **digest 계산 실패 / `reviewed_scope_digest` 기록 없음** (레인 B: `reviewed_plan_paths` 없음 · **계획 경로 소실** · 대상 0건) | **게이트 실패 (fail-closed)**. 대조 불능은 일치가 아니다 ("리비전 결속" 절). 레인 B는 **착수 불가** |
| **재계산 digest가 기록값과 불일치** | approve **무효** — 승인 후 편집됨(레인 B는 계획이 개정됨). 재심 (Phase 0 복귀) |

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

**품질 게이트 통과는 `adjudicator: "codex"` + `verdict: approve` + `reviewed_scope_digest == 현재 digest`의
조합에서만 성립한다** (아래 "리비전 결속" 절).
폴백 산출물(`adjudicator: "fallback-claude"`)은 어떤 값이든 게이트를 통과시키지 못한다
(위 fail-closed 규칙과 같은 성질이다 — 판정 불능도, 비독립 판정도, 리비전 미결속 판정도 통과가 아니다).

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
7. verdict.md 기록 — adjudicator: "codex" + reviewed_at_head + reviewed_scope_digest
   + verbatim 원문 + 수용검사 섹션
   (evidence/ 밖에 쓴다 — 다음 심판의 입력 표면에 들어가지 않게)
8. finding#1 → execution-specialist, #3 → test-engineer 위임
9. 수정 완료 → Phase 0 복귀 (재심: 새 스탬프 + 직전 .omc/review/20260811-143052/verdict.md 파일 1건 지목)
기대: 채택 2건 해소 확인 + 기각 1건이 재심에서 되살아나지 않음
```

### 시나리오 4 — 승인 후 편집 (리비전 결속이 잡아내는 경우)

```
1. 재심에서 Codex가 verdict: approve 반환
2. verdict.md 기록 — adjudicator: codex, reviewed_at_head: d4c6485f...,
   reviewed_scope_digest: a91f...(64자 hex)
3. 그 뒤 "사소한 오타 하나만" 수정이 들어옴 (심사 지적과 무관한 파일)
4. 게이트 통과를 인용하려는 시점에 review_scope_digest 재계산 → 7c02... (불일치)
5. approve 무효 판정 → Phase 0 복귀, 재심
기대: "무관한 사소 변경"이라는 피심판자의 자기 판단이 게이트를 열지 못한다.
      무효화는 기계적(digest 불일치)이며 변경의 성격을 논하지 않는다.
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
- 기각한 finding은 **기각 사유를 반드시 기록** (조용히 버리지 않는다) — 기각 사유는 **3가지로 한정**되고, **기각은 게이트를 열지 않는다**
- `verdict.md`에 **`adjudicator`(`codex` | `fallback-claude`) 기록** — 하류가 구조로 심판자를 식별
- `verdict.md`에 **`reviewed_at_head` + `reviewed_scope_digest` 기록** (**레인 B는 + `reviewed_plan_paths`**),
  게이트 통과 시점(레인 B = **실행 착수 시점**)에 **digest 재계산·대조** — 기록 없음·계산 불가·경로 소실·불일치는
  전부 **통과 아님**(fail-closed). 승인 이후의 어떤 변경이든 `approve`를 무효화한다
  (레인 A는 작업 트리 전체, 레인 B는 심사한 계획 문서만 결속 — 방향 선택과 대가는 "리비전 결속" 절)
- 폴백 시 `[FALLBACK: 비독립 심판 — 동일 모델 계열]` **최상단 명시** + **`approve` 금지**
- 렌즈 산출물은 `evidence/` 안, `verdict.md`는 `evidence/` **밖** — focus 지목은 `evidence/`만
- needs-attention 후 수정했으면 **반드시 재심** — 수정만으로 통과시키지 않는다
