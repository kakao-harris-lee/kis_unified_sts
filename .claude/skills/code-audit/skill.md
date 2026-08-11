---
name: code-audit
description: "종합 코드 감사 오케스트레이터 (fan-out/fan-in). 아키텍처·보안·성능·스타일 4개 감사관을 병렬 실행해 증거를 생성하고, codex-reviewer(Codex 독립 심판)가 팬인해 단일 verdict로 판정. '종합 리뷰', '전체 감사', '코드 감사', '보안+성능+아키텍처 점검', '재감사', '다시 감사', '수정 후 재심', '감사 업데이트' 요청 시."
---

# Code Audit — 종합 코드 감사 오케스트레이터

코드(diff / PR / 경로)를 **4개 전문 렌즈로 병렬 감사**해 증거를 생성하고, 그 증거를
**다른 모델 계열(Codex)의 독립 심판이 하나의 verdict로 판정**하는 fan-out/fan-in 하네스.
일상 단일 게이트 리뷰(`codex-reviewer` 단독 호출 — 서브커맨드는 동일하게 `adversarial-review`)와 달리, 이 스킬은
**여러 전문 감사관의 깊이 있는 다중 관점 감사**를 한 번에 수행한다.

**심판을 Codex가 소유하는 이유**: Claude가 만든 코드를 Claude가 승인하는 자기 승인을 막기 위해서다.
4렌즈 감사관은 **증거 생성자**이며, 심각도 정규화·차단 판정·최종 리포트는 더 이상 이들의 일이 아니다.

## 언제 쓰나
- "종합 코드 리뷰 / 전체 감사 / 코드 감사 해줘"
- "아키텍처·보안·성능·스타일 같이 점검해줘"
- 큰 변경/릴리스 전 심층 다중 렌즈 감사
- "재감사 / 다시 감사 / 수정 후 재심 / 감사 업데이트" (Phase 4 부분 재실행)
- (단순 PR 1건 게이트 리뷰는 `codex-reviewer` 단독 호출 — 렌즈 팬아웃만 생략하고 서브커맨드는 `adversarial-review` 유지)

## 팀 구성 (증거 생성 팬아웃 + 독립 심판 팬인)

| 에이전트 | 렌즈 | 단계 |
|---------|------|------|
| `architecture-auditor` | 레이어 경계·의존성·패턴·DRY·god-object | 병렬 증거 생성 |
| `security-auditor` | 인젝션·시크릿·입력검증·인증·자금경로 | 병렬 증거 생성 |
| `performance-auditor` | hot path·캐싱·쿼리·메모리·레이턴시 | 병렬 증거 생성 |
| `style-auditor` | 포맷·타입·docstring·네이밍·매직넘버 | 병렬 증거 생성 |
| `codex-reviewer` | 중복제거·심각도정규화·우선순위·차단판정·단일 verdict | 독립 심판 (fan-in) |

> `review-synthesizer`는 **폴백 전용**이다. Codex 미가용 시에만 팬인 자리를 대신한다(아래 폴백 절).

## 워크플로우

```
                        ┌─ architecture-auditor ─┐
[code-audit]            ├─ security-auditor ──────┤   각 렌즈가 파일로 기록
  범위 결정  ──fan-out──┤                          ├──→ .omc/review/{stamp}/{lens}.md
 (diff/PR/경로)         ├─ performance-auditor ───┤        (architecture|security|
  stamp=YYYYMMDD-HHMM   └─ style-auditor ─────────┘         performance|style)
                    (4개 병렬, 서로 독립 / 같은 범위 입력)
                                                                    │
                                          focus text로 디렉토리 지목 │ (Codex가 직접 읽음)
                                                                    ▼
                                        codex-reviewer (adversarial-review, 별도 프로세스)
                                                                    │
                                                                    ▼
                                            .omc/review/{stamp}/verdict.md
                                        {verdict, summary, findings[], next_steps[]}
                                                                    │
                                                                    ▼
                                              Claude 오케스트레이터 수용검사
```

### Phase 0: 워크스페이스 준비
- `stamp = YYYYMMDD-HHMM`을 정하고 `.omc/review/{stamp}/`를 만든다.
- `.omc/`는 이미 gitignore 처리되어 있으므로 산출물이 커밋을 오염시키지 않는다.

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
- **반환만 하지 말고 `.omc/review/{stamp}/{lens}.md`에 파일로 기록한다**
  (lens = `architecture` | `security` | `performance` | `style`)

> **왜 파일인가**: Codex는 별도 프로세스라 Claude 서브에이전트의 **반환값을 볼 수 없다.**
> 파일이 Codex 심판에게 증거를 전달하는 **유일한 채널**이다.
> 파일을 안 쓰면 심판은 렌즈 결과를 보지 못한 채 판정하게 된다.

각 감사관은 판정하지 않는다. **심각도는 제안값**이며 정규화·차단 판정은 심판 소관이다.

### Phase 3: 독립 심판 (fan-in)
`codex-reviewer`를 호출한다.
- 모드: **`adversarial-review`**
- **왜 `review`가 아닌가**: 네이티브 `review`는 내장 리뷰어 직결이라 플러그인이 프롬프트도 스키마도
  주입하지 못한다 — focus text 주입 불가이고 **verdict 필드도 없다**
  (`codex-companion.mjs:370-407` = `result.reviewText` free-form 렌더 / `:409-417` =
  `adversarial-review`만 `outputSchema: readOutputSchema(REVIEW_SCHEMA)` 부착).
  이 팬인 단계는 focus 지목과 단일 verdict **둘 다** 필요하므로 네이티브 경로로는 성립하지 않는다.
  플러그인 업그레이드 시 위 두 지점을 재확인한다.
- focus text로 **`.omc/review/{stamp}/`** 디렉토리를 지목한다.
  Codex는 repo-aware CLI이므로 focus text로 경로를 주면 렌즈 산출물과 대상 코드를 직접 읽는다.
  **렌즈 결과를 커맨드라인 인자로 통째로 넘기지 마라.**
- 출력은 Codex verdict 스키마:
  `{verdict: approve|needs-attention, summary, findings[{severity, title, body, file, line_start, line_end, confidence, recommendation}], next_steps[]}`
- 결과를 `.omc/review/{stamp}/verdict.md`에 저장한다.
- **Codex stdout은 verbatim 보존한다. 요약하지 마라.**
  이유: 피심판자(Claude)가 심판 결과를 요약하면 그 순간 독립성이 훼손된다.
  압축·의역·"핵심만 정리"는 전부 금지. 인용은 원문 그대로.

### Phase 3.5: 수용검사 (Claude 오케스트레이터)
**Codex verdict를 무조건 수용하지 않는다.** verbatim 보존은 유지한 채, 아래를 확인해 별도 섹션에 기록한다:

- [ ] **실재성**: 각 finding의 `file:line`이 실제로 존재하는가 (없으면 해당 항목 무효 표기)
- [ ] **의도적 silence**: lint ignore·안전 주석·테스트 픽스처처럼 **의도적으로 silenced된 항목**인가
- [ ] **비협상 규칙 배치**: 권고가 CLAUDE.md 비협상 규칙과 충돌하는가. 충돌하면 **기각하고 사유를 기록**한다.
  - 선물 long/short 대칭 훼손
  - 실계좌 증거금 관련 제안 (실 선물 계좌는 영구 미납입 — 운영자 지시)
  - EOD 일괄청산 도입 (스톡 스윙 청산은 시그널 구동)
  - ClickHouse 신규 사용
  - RL/TFT 경로 부활 (`sts rl *`, `sts tft *`, `shared/ml/rl`, `shared/ml/tft` 등)
  - 하드코딩 도입·Redis DB 1 이탈·`shared/` 우회 중복

기각 항목은 **삭제하지 말고** "기각 + 사유"로 남긴다. 심판 기록을 지우면 다음 심판이 같은 것을 다시 제기한다.

### Phase 4: 후속 (선택)
- 차단 항목 → 담당 에이전트로 수정 위임 (`refactorer`, `execution-specialist`, `data-engineer`, `strategy-architect` 등)
- 수정 후 해당 렌즈만 재감사 (부분 재실행) → **새 stamp**로 재심판 (`codex-reviewer` 재호출)

## 폴백 (Codex 미가용)
1. Codex 호출 실패 시 **1회 재시도**한다 (auth 만료·네트워크·rate limit 대부분은 일시적).
2. 재실패하면 `review-synthesizer`로 **강등**해 팬인을 수행한다 (`.omc/review/{stamp}/{lens}.md` 4개를 직접 읽음).
3. 리포트 **최상단에 아래 한 줄을 명시**한다. 조용한 폴백은 결함이다.

   ```
   [FALLBACK: 비독립 심판 — 동일 모델 계열]
   ```
4. 출력 스키마는 Codex verdict와 동일하게 유지한다 — 하류 소비 표면이 분기 없이 같아야 한다.
5. 폴백 판정은 **잠정**이다. Codex 회복 후 재심 대상으로 남긴다.
6. **판정 불능은 실패이지 통과가 아니다 (fail-closed).** Codex가 응답했더라도 출력에 `verdict`가 없거나
   `renderReviewResult`가 "Parse error + Raw final message"로 떨어졌다면 심판은 판정을 내지 못한 것이다.
   **approve로 넘기지 마라** — 판정 불능을 통과로 읽으면 게이트가 무의미해지고, 자기 승인 방지라는
   존재 이유가 소멸한다. 먼저 서브커맨드가 `adversarial-review`였는지 확인하고
   (`review`였다면 verdict 부재는 버그가 아니라 그 경로의 정상 동작이다 — Phase 3 근거 참조),
   맞게 호출했는데도 verdict가 없으면 1회 재시도 후 실패로 보고한다.

## 모델 선택 (비용/속도)
- 감사관 4종: 표준 모델(sonnet) 병렬 — 판단·코드 이해 필요
- 대규모 경로 모드: 감사관별로 하위 파일셋 분할 dispatch 후 렌즈별 1차 통합 → 렌즈 파일 1개로 기록 → Codex 최종 심판
- 심판: `codex-reviewer` (모델 계열이 다른 것 자체가 이 단계의 가치)

## 거짓 양성 정책 (Codex 심판 + Claude 수용검사가 강제)
- linter/typechecker/compiler가 잡을 단순 항목은 LOW로 강등 (CI가 처리)
- 변경하지 않은 라인의 기존 이슈는 pre-existing으로 분리
- 단일 렌즈·저신뢰·검증불가 → "참고"로 강등
- 의도적으로 silenced된 항목(lint ignore, 안전 주석, 테스트 픽스처)은 제외

## 품질 기준
- 모든 발견에 `파일:라인` 인용 (Codex 스키마의 `file` + `line_start`/`line_end`)
- CRITICAL/HIGH는 영향 + 권장 조치 필수, 담당 제안은 Claude 후속 배정에서 채운다
- 차단 판정(`needs-attention`)에 명확한 사유
- 리포트는 간결하게 (군더더기 없는 실행 가능 항목) — 단, **Codex 원문은 압축 대상이 아니다**
- 렌즈 파일과 verdict 파일이 `.omc/review/{stamp}/`에 전부 남아 재현 가능해야 한다

## 다른 하네스와의 경계
- **`code-audit` (이 스킬)**: **렌즈 팬아웃(증거 생성)**을 제공한다. 판정은 하지 않는다
- **`codex-gate` 스킬 / `codex-reviewer`**: **팬인 심판**을 소유한다 (레인 A=코드 심판, 레인 B=계획 심판)
- **일상 단일 게이트 리뷰**: `codex-reviewer` 단독 호출 (`code-reviewer`가 아니다). 서브커맨드는 `adversarial-review` — 판정을 내는 이상 규모와 무관하다
- **`code-reviewer` / `review-synthesizer`**: **폴백 전용**. Codex 미가용 시의 강등 경로일 뿐이며 평상시 진입점이 아니다
- 관계 정리 — 일상 PR은 `codex-reviewer` 단독 `adversarial-review`, 큰 변경/릴리스는 `code-audit` 팬아웃 → Codex 팬인 심판 (`adversarial-review`). 차이는 렌즈 팬아웃 유무이지 심판 경로가 아니다
