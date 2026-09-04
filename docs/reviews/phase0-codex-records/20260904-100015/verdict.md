---
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 26db89c92fedef044ddbfb1c7dc93545a6187033
reviewed_scope_digest: e29542e10517207db24c12d7c392fc06539ee92febae5e4d7423a42bb92a5e06
job_id: review-mtm957x1-fzj64e
subcommand: adversarial-review (--wait · setsid pid 6793 · base 28475ca1^ · scope branch · 재심 #2)
captured_at_utc: 2026-09-04T01:00:15Z
verdict_recovered_at_utc: 2026-09-04T01:09:37.401Z
lane: A (코드) — Phase 0 완료 계약 §12.3 절차표 9행 «codex-reviewer 적대적 코드 리뷰» · 재심 #2
prior_verdict: .omc/review/20260904-001114/verdict.md (needs-attention · 채택 3/3)
scope: git diff 28475ca1^ HEAD -- . ':!docs/plans' ':!docs/reviews'  (D0 구현 블록 + 수정 커밋 067ecb2e · 2e5edb4a · 26db89c9)
evidence: .omc/review/20260904-100015/evidence/{architecture,security,performance,style}.md (1차 사본) + verification-run.md (오케스트레이터 실행 로그)
verbatim_sources: codex-result.json (구조화 출력) · codex-wait.out (렌더 스트림)
---

# Codex verdict — verbatim (structured output, 무편집)

```json
{"verdict":"needs-attention","summary":"출하 차단. 재심 #1 finding 1은 해소됐다: NONE은 항상 UNDECIDED이고, 혼합 키도 UNDECIDED이며, 균일 다중 키는 우선순위 없이 어느 K를 택해도 동일한 처분이므로 접기 규칙 재도입이 아니다. UNCHK-026은 U-6의 개별 등재이며 D0-5는 계속 NOT_MET라 완료 우회가 아니다(정확한 U-6 문언은 §7.4:2802-2807이고, 지목된 §13.6.6은 존재하지 않는다). 합성 코퍼스의 우주 밖 단일 키 배선도 전용 NONE·혼합·실코퍼스 대조군을 보존한다. 같은 입력의 세 기대가 반전됐고 2e5edb4a 구현은 실제로 UNBOUND/BLOCKED를 반환하므로 새 테스트에 실패한다. 재심 #1 finding 3도 해소됐다: 고정 7이름은 D1_SITES 비파생 리터럴이고, 사이트 삭제·여분·어휘 밖 값이 모두 차단된다. 생성물은 검사기 결과(D0-5 UNDECIDED 2, ENTRY_OK)와 일치한다. 제공된 쓰기 가능 환경 로그는 pytest 209/209, --check, ruff/black/mypy rc 0이며, 이번 샌드박스의 직접 --check는 임시 디렉터리 부재로 rc 2였다. 에라타 (e)는 사실과 필요한 운영자 처분만 기록한다. 다만 finding 2는 부분 해소다: Lane A의 docs/plans 제외는 명확해졌지만, 제외된 네 파일 중 15b65212의 July 설계 문서 두 개는 인용된 Lane B 승인 범위에 없다. 1차에서 해소된 파일부재·산문 자기신고·git-failure 축은 이번 수정으로 회귀하지 않았고, UNCHK-012·008·023도 새로 열리거나 넓어지지 않았다(pre-existing).","findings":[{"severity":"high","title":"제외된 July 계획 문서 두 개에 별도 Lane B 심판 결속이 없다","body":"재심 #1 finding 2의 허위 ‘docs/plans=0’ 전제는 정정됐지만, 대체 결속은 불완전하다. 15b65212가 이 파일과 safety-profile 설계 문서에 각각 7줄을 추가했으나, 근거로 제시된 20260902-174919 승인 기록의 reviewed_plan_paths는 Phase-0 completion contract와 completion development plan 두 개뿐이다. 그 기록도 두 파일만 byte-identical하다고 명시하므로, PR merge HEAD를 승인했다는 사실만으로 범위 밖 두 문서의 내용 심판이 되지 않는다. 결과적으로 Lane A에서 제외된 네 plan 파일 중 두 개는 어느 제시된 Lane B 승인에도 결속되지 않은 채 D0 전체 블록 승인을 요구한다. 이는 26db89c9 이전부터 존재한 범위 결함이지만 이번 범위 정정으로 해소되지 않았다.","file":"docs/plans/2026-07-25-tos-intent-order-conformance-design.md","line_start":1201,"line_end":1206,"confidence":0.99,"recommendation":"계약 본문을 편집하지 말고, 15b65212가 변경한 두 July 설계 문서의 정확한 diff/path를 reviewed_plan_paths와 digest에 결속한 별도 Lane B Codex 판정을 제시하라. 이미 그런 판정이 있다면 해당 기록의 정확한 경로와 범위 필드를 제공하라."}],"next_steps":["15b65212의 두 July 설계 문서를 명시적으로 포함하는 Lane B 승인 기록을 취득하거나 기존의 정확한 결속 기록을 제시한다.","그 기록을 반영한 뒤 동일한 Lane A 범위로 재심한다. finding 1과 3은 추가 코드 수정이 필요 없다."]}
```

# 재심 #1 finding 3건의 처분 (Codex summary 발췌)

- finding 1(NONE·혼합 키): **해소** — 「NONE 은 항상 UNDECIDED, 혼합 키도 UNDECIDED, 균일 다중 키는 어느 K 를 택해도 동일한 처분이므로 접기 규칙
  재도입이 아니다. UNCHK-026 은 U-6 의 개별 등재이며 D0-5 는 계속 NOT_MET 라 완료 우회가 아니다」. 부수 정정: U-6 의 계약 문언은
  §7.4 :2802-2807 이며 focus 가 적은 «§13.6.6» 은 존재하지 않는다(오케스트레이터 focus 의 팬텀 인용 — 코드 docstring 의 같은 표기는
  후속 정정 대상).
- finding 3(렌더러 고정 7 이름): **해소** — 「고정 7 이름은 D1_SITES 비파생 리터럴이고 사이트 삭제·여분·어휘 밖 값이 모두 차단된다」.
- finding 2(docs/plans 범위): **부분 해소** — 레인 A 의 docs/plans 제외는 명확해졌으나, 제외된 4 파일 중 `15b65212` 의 7월 설계 문서 2건은
  제시된 레인 B 승인(20260902-174919 · reviewed_plan_paths = 계약·개발계획 2건)의 범위 밖 → 이번 유일 finding.
- 1차 finding 3건(파일 부재·산문 자기신고·git-failure)은 회귀 없음. UNCHK-012·008·023 확장 없음(pre-existing).

# 수용검사 (오케스트레이터 = Claude · 판정이 아니라 대조)

| # | sev | file:line 실재 | in-range(28475ca1^..HEAD) | 의도적 silenced | 비협상 규칙 배치 | 처분 |
|---|---|---|---|---|---|---|
| 1 | high | 실재 — `docs/plans/2026-07-25-tos-intent-order-conformance-design.md:1201-1206` = `15b65212` 가 append 한 «에라타 (2026-09-02) — evidence-id 리터럴 앵커» 절(+7) · 같은 커밋이 `2026-07-25-tos-safety-profile-governance-design.md:1318-1324` 에도 +7. 두 문서는 이후 무변경(`git diff 15b65212 HEAD` 0). `.omc/review/*/verdict.md`·`docs/reviews/` 전수 grep 결과 이 두 변경을 reviewed_plan_paths 로 결속한 Codex 판정은 없다(20260812-* 스탬프 10건은 두 문서의 원 저작 심판이지 이 에라타 절이 아니다) | in-range(pre-existing · 이 레인 수정 커밋보다 선행) | 아니오 | 없음(계약 무편집 권고) | **채택(범위 결속 결함 · 코드 결함 아님)** — 두 문서의 해당 diff 를 `reviewed_plan_paths` + `plan_scope_digest` 로 결속한 별도 레인 B Codex 판정을 취득한 뒤 동일 레인 A 범위로 재심 #3 |

기각 0 · 채택 1/1. 코드 수정 불요(next_steps 2 「finding 1 과 3 은 추가 코드 수정이 필요 없다」).

## 처분 계획

1. 레인 B 심판(별도 스탬프 · `codex-plan-reviewer` 경로 = adversarial-review · 범위 = `git diff 15b65212^ 15b65212 -- <두 문서>` · reviewed_plan_paths 두 문서 ·
   plan_scope_digest = 두 문서 현재 내용) → verdict.md 는 `.omc/review/<stamp>/` 에 둔다. **`docs/reviews/phase0-completion-contract/` 에 두지
   않는다** — R-3 선택자가 사전순 마지막 스탬프를 고르고 R-5 가 reviewed_plan_paths 에 계약 2건을 요구하므로 ENTRY 가 깨진다(아카이브 함정 ·
   보존 위치는 운영자 결정).
2. 레인 A 재심 #3: 같은 범위·같은 HEAD(코드 무변경이면 digest 동일) · focus 에 레인 B 기록 경로와 범위 필드 제시.
