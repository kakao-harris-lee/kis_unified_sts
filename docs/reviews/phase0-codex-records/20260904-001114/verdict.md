---
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 2e5edb4adeb54756b2d20887886c2663adb16d37
reviewed_scope_digest: b05927447416c4d14735807222019e90b58b05a891f9103947d99a60811971e9
job_id: review-mtlo6mst-93vt2j
subcommand: adversarial-review (--wait · setsid · base 28475ca1^ · scope branch · attempt3 via retry loop — attempt1/2 는 OpenAI 장애 backend 404)
captured_at_utc: 2026-09-03T15:15:12Z
verdict_recovered_at_utc: 2026-09-03T15:22Z
recorded_at_utc: 2026-09-04T00:35Z (후속 세션 — 직전 세션은 verdict 회수 직후 컨텍스트 압축으로 중단)
lane: A (코드) — Phase 0 완료 계약 §12.3 절차표 9행 «codex-reviewer 적대적 코드 리뷰» · 재심 #1
prior_verdict: .omc/review/20260903-165133/verdict.md (needs-attention · 채택 3/3)
scope: git diff 28475ca1^ HEAD -- . ':!docs/plans' ':!docs/reviews'  (D0 구현 블록 + 수정 커밋 067ecb2e · 2e5edb4a)
evidence: .omc/review/20260904-001114/evidence/{architecture,security,performance,style}.md (1차 스탬프 사본 + 출처 헤더)
verbatim_sources: codex-result.json (구조화 출력) · codex-wait.out (렌더 스트림)
---

# Codex verdict — verbatim (structured output, 무편집)

```json
{"verdict":"needs-attention","summary":"출하 차단. 직전 finding #1(파일 부재 fail-open), #2(UNBOUND 산문 자기신고), #3(git 실패 시 walk 폴백)는 모두 해소됐다. 구 구현으로 되돌리면 각각 새 missing-site/prose/git-failure 대조군이 실패하며, `/definitely-not-a-repo`도 7/7 UNDECIDED·fail-closed를 반환한다. 선언 오류·본문 부재·미선언 인용·NONE 모순은 UNDECIDED로 접히고, 권위 tos_spec_status 경로는 git만 사용하며 StatusError가 rc 1로 전파된다. 그러나 D0-5는 계약에 없는 NONE 및 다중 키 우선순위로 MET를 만들고, 렌더러의 ‘정확히 7개’ 조건도 실제로는 6/6 같은 축소 우주를 허용한다. 또한 요구된 docs/plans 무편집 검사가 0파일이 아니라 4파일(+88/-17)이다. 현재 생성물의 7행 basis는 직접 파생 결과와 일치하고 d0a_entry_state=ENTRY_OK이며 tos_spec_status --check와 하니스는 rc 0이었다. tos_completion_status --check 및 pytest는 실행 환경에 사용 가능한 임시 디렉터리가 없어 각각 rc 2/수집 전 실패하여 재검증되지 않았다. 2e5edb4a의 7사이트 변경은 docstring-only이고 import firewall 실행 코드에는 영향이 없다. UNCHK-012·008·023 경로는 이번 수정으로 새로 열리거나 넓어지지 않았다.","findings":[{"severity":"high","title":"D0-5가 계약에 없는 NONE·다중 키 접기 규칙으로 완료를 선언한다","body":"§7.4는 저작자가 의존 키 K를 공급하고, 키 미공급은 UNDECIDED로 완료를 차단한다고 규정한다. 하지만 구현은 다중 키를 UNBOUND>BLOCKED>VALUED로 접고, NONE 선언은 소스 토큰 스캔에서 우주 키가 안 보이면 UNBOUND로 만든다. marketfeed는 실제로 NONE 경로로 UNBOUND가 되고 resolver는 6 VALUED+1 UNBOUND를 UNBOUND 하나로 접어 현재 D0-5 MET에 기여한다. 에라타 후보도 두 규칙이 계약에 없음을 정직하게 인정하므로 은폐는 아니지만, 운영자 채택 전에는 frozen 계약의 완료 판정 근거가 아니다. 특히 NONE은 ‘키를 공급하지 못함’을 저작자 선언 하나로 UNBOUND로 바꾸는 새 우회로다.","file":"tools/tos_completion_status.py","line_start":3679,"line_end":3814,"confidence":0.98,"recommendation":"이를 계약 에라타 대상으로 유지하고 운영자 처분 전에는 NONE 및 혼합 처분 사이트를 UNDECIDED로 처리해 D0-5 MET를 막아라. 이 레인에서 frozen 계약 본문을 편집하지 마라."},{"severity":"high","title":"검토 기준점 이후 frozen 계획·계약 diff가 0이 아니다","body":"요구된 `git diff 28475ca1^ HEAD --stat -- docs/plans`는 4파일, +88/-17을 반환했고 Phase-0 계약 자체가 +72/-15다. 변경은 15b65212와 8199bb38에서 유입되어 이번 두 수정 커밋보다 선행하지만, 전체 D0 블록의 지정 기준점에는 포함된다. 따라서 ‘계약 편집 0파일’ 전제가 거짓이며, 계약 밖 에라타 메모가 주장하는 무편집 상태도 이 리뷰 범위 전체에는 적용되지 않는다. 이는 산문 내용 재심이 아니라 frozen/blob-bound 입력이 목표 diff에서 바뀌었다는 기계적 범위 위반이다.","file":"docs/plans/2026-08-12-tos-phase0-completion-contract-design.md","line_start":8007,"line_end":8011,"confidence":1,"recommendation":"계약을 고치지 말고, 계획 변경 커밋이 제외되는 올바른 기준점으로 심사 범위를 다시 결속하거나 해당 변경을 별도 레인 B 산출물로 분리한 뒤 docs/plans stat이 0임을 재확인하라."},{"severity":"medium","title":"렌더러의 정확히 7사이트 조건이 축소된 D1_SITES를 기준으로 재정의된다","body":"MET 계산은 고정된 계약상 7개 이름과 비교하지 않고 현재 `D1_SITES`에서 기대 집합을 다시 만든다. 따라서 D1_SITES에서 한 항목을 제거하면 compute 결과와 기대 집합이 함께 6개로 줄어 `d1_missing=[]`, `d1_undecided=[]`가 되어 6/6으로 MET가 된다. 여분 disposition이나 허용 어휘 밖 값도 명시적으로 거부하지 않는다. 현 테스트의 하드코딩된 실사이트 기대는 일부 변이를 잡지만, 렌더러 자체의 주장인 ‘정확 일치 AND 전부 허용 처분’은 구현되지 않았다.","file":"tools/tos_completion_status.py","line_start":4167,"line_end":4179,"confidence":0.97,"recommendation":"계약상 고정 7개 이름과 `set(d1_dispositions)`의 완전 동등성, D1_SITES의 길이·이름 불변식, 모든 처분이 VALUED/BLOCKED/UNBOUND 중 하나임을 각각 검사하라. 한 사이트 삭제, 여분 사이트, 잘못된 처분을 주입하면 MET가 실패하는 렌더러 대조군을 추가하라."}],"next_steps":["NONE·혼합 키 규칙에 대한 운영자 계약 에라타 처분 전 D0-5 MET를 차단한다.","렌더러를 고정 7개 이름 및 허용 처분 집합에 대해 fail-closed로 고친다.","docs/plans diff가 0이 되는 기준점 또는 분리된 레인 B 범위로 리뷰 결속을 바로잡는다.","쓰기 가능한 임시 디렉터리가 있는 환경에서 focused pytest와 `tos_completion_status.py --check`를 재실행한다."]}
```

# 직전 finding 3건의 해소 확인 (Codex summary 발췌 · 재심 1순위 항목)

Codex 는 1차 finding F1(파일 부재 fail-open)·F2(UNBOUND 산문 자기신고)·F3(git 실패 walk 폴백) 을 **모두 해소** 로
판정했다 — 「구 구현으로 되돌리면 각각 새 대조군이 실패」「`/definitely-not-a-repo` 도 7/7 UNDECIDED」「권위 경로는
git 만 사용하며 StatusError 가 rc 1 로 전파」「7사이트 변경은 docstring-only」「UNCHK-012·008·023 경로는 넓어지지 않음」.
회피(테스트 무력화·조건 완화·문구만 추가) 지적 0.

# 수용검사 (오케스트레이터 = Claude · 판정이 아니라 대조)

기각 가능 사유는 셋뿐이다(팬텀 file:line · 의도적 silenced · 비협상 규칙 배치). 이 표는 기각 여부와 pre-existing
분류만 정한다 — 게이트는 Codex 의 새 approve 로만 열린다.

| # | sev | file:line 실재 | in-range(28475ca1^..HEAD) | 의도적 silenced | 비협상 규칙 배치 | 처분 |
|---|---|---|---|---|---|---|
| 1 | high | 실재 — `tools/tos_completion_status.py:3679-3814` `_derive_d1_disposition` 이 NONE(스캔 0건→UNBOUND) 과 `_d1_fold_key_dispositions`(UNBOUND>BLOCKED>VALUED) 로 처분을 만든다. HEAD 실측: marketfeed = NONE 경로 UNBOUND · resolver = 6 VALUED + 1 UNBOUND → 접기 UNBOUND | in-range(2e5edb4a) | 아니오 — 두 규칙은 코드 주석과 `D1-DERIVATION-ERRATUM-CANDIDATE.md` 가 «계약 조항 아님(설계 규칙)» 으로 자인한 항목이다. 자인은 silenced 근거가 아니라 오히려 Codex 독법을 뒷받침한다: frozen 계약 §7.4 :2682-2823 의 어휘는 단일 K 에 대한 VALUED/BLOCKED/UNBOUND 와 K 미공급 UNDECIDED 뿐이며, 운영자 에라타 채택 전에는 그 밖의 규칙이 완료값을 만들 수 없다 | 없음(계약 무편집 권고) | **채택** — 운영자 에라타 처분 전까지 NONE 사이트·혼합 처분 사이트를 UNDECIDED 로. 결과 D0-5 는 MET → NOT_MET(5/7) 로 정직 노출된다 (§11 상태 변화 = 운영자 보고 항목) |
| 2 | high | 실재 — `git diff 28475ca1^ HEAD --stat -- docs/plans` = 4 files · +88/−17 (계약 +72/−15) 재실측 일치. 출처 커밋 `15b65212`(FWD-a 5차 · 설계 에라타 앵커) · `8199bb38`(§12.3.4-R 하니스 EPIPE 수리 · sha 재핀) | in-range 이나 **이 레인의 수정 커밋보다 선행** (pre-existing) | 아니오 | 없음 | **채택(범위 결함 · 코드 결함 아님)** — 원인은 focus.txt 의 «docs/plans stat 은 0 파일» 이라는 오케스트레이터의 허위 전제. 두 커밋은 레인 B(계약) 산출물로 각각 별도 Codex 심판 기록을 가진다(아래 처분). 다음 focus 는 사실대로 4 파일·출처·레인 B 판정 경로를 제시하고, 레인 A 심사 범위에서 `docs/plans`·`docs/reviews` 를 제외함을 명시한다 |
| 3 | medium | 실재 — `tools/tos_completion_status.py:4167-4179` 렌더러가 기대 집합을 `D1_SITES` 에서 재파생 → 사이트 1개 제거 시 6/6 MET. 여분 사이트·허용 어휘 밖 처분 명시 거부 없음 | in-range(2e5edb4a) | 아니오 | 없음 | **채택** — 계약상 고정 7 이름 상수와 완전 동등 + D1_SITES 불변식 + 처분 어휘 검사 + 렌더러 red 대조군 3종 |

기각 0 · pre-existing 분리 0(finding 2 는 채택하되 코드 결함이 아닌 범위 결함으로 분류) · 채택 3/3.

## 계약 대조 메모(수용검사 근거 · 계약 무편집)

- §7.4 :2682-2823 — 처분 어휘는 「VALUED / BLOCKED / UNBOUND」(공급된 K 와 VER-002 우주의 관계)와 「UNDECIDED = K 미공급」뿐.
  «의존 키가 없다(NONE)» 는 선언과 «여러 K 의 처분을 하나로 접는다» 는 규칙은 계약 어휘 밖이다 → finding 1 채택.
  구현이 계약보다 «더 충실» 하다는 논증은 에라타 채택 뒤에나 유효하다(운영자 소관).
  - 부수 실측: UNCHK-024 처분(PR #640)은 resolver 의 `max_age_bound` 를 UNBOUND 로 등재했으나 이는 레지스터 등재이지
    §7.4 처분 규칙의 확장이 아니다 — 에라타 채택 근거 자료로 에라타 후보 문서에 기재만 한다.
- 완료 기준(v1.8) — 「7개 사이트 전부가 VALUED/BLOCKED/UNBOUND 중 하나」 → finding 3 의 «축소 우주 6/6 MET» 는 계약이
  고정한 7 이름을 검사기 가변 상수로 대체한 것 → 채택.
- 레인 A 범위 정의(1차 verdict.md `scope:`) 는 `':!docs/plans' ':!docs/reviews'` 를 제외했으나 Codex 에 넘긴 `--scope branch`
  는 경로 제외를 모른다. 제외는 산문이었고 «0 파일» 단언은 거짓이었다 → finding 2 채택.

## 수정 위임 (오케스트레이터는 직접 고치지 않는다)

| finding | 담당 레인 | 산출 |
|---|---|---|
| 1 + 3 | 실행 에이전트(Sonnet) — `tools/tos_completion_status.py` · `tests/tools/test_tos_completion_status.py` · `tos-spec/src/TOS-COMPLETION-STATUS.md` 재생성 · `D1-DERIVATION-ERRATUM-CANDIDATE.md` 갱신(계약 밖) | NONE → UNDECIDED(스캔 결과는 basis 로 보존) · 혼합 처분 → UNDECIDED(키별 내역 basis) · 균일 처분만 사이트 처분으로 · 렌더러 고정 7 이름 상수 + 불변식 + 어휘 검사 + red 대조군 |
| 2 | 오케스트레이터(범위 결속) — 다음 스탬프 focus.txt | «docs/plans 4 파일» 사실 기재 + 출처 커밋 2건 + 각각의 레인 B 심판 기록 경로 + 레인 A 제외 경로 명시. 기준점은 D0 블록 시작(`28475ca1^`)을 유지한다 — 두 계획 커밋은 블록 중간에 있어 기준점 이동으로 제외할 수 없고, 제외하면 D0 구현 커밋도 함께 빠진다 |
| next_steps 4 | 오케스트레이터 — focused pytest · `--check` 를 쓰기 가능한 환경에서 재실행하고 로그를 `evidence/` 에 첨부 | Codex 샌드박스가 못 돌린 검증의 대체 증거(자기 승인 아님 — 실행 로그 제공) |

수정 후 **재심 필수** — 새 스탬프 + 이 파일(`.omc/review/20260904-001114/verdict.md`)을 Codex 에 지목해 해소 vs 회피를
1순위로 심사시킨다. 이 needs-attention 은 §12.3 9행의 기록 심판이며, Phase 0 완료 판정(§11)은 이 레인의 approve 이전에는
인용할 수 없다. finding 1 채택으로 D0-5 가 NOT_MET 로 돌아가는 것은 이 레인의 결정이 아니라 frozen 계약의 정직한 독법이며,
MET 복원은 운영자의 에라타 처분(NONE 어휘 도입 · 다중 키 처분 규칙)으로만 가능하다.
