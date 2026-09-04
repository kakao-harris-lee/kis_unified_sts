---
adjudicator: codex
verdict: needs-attention
lane: B (plan) — 계약 v2.22 에라타 52차(§7.4 D-3/D-4/D-5) + O-6 재결속 · 재심 #1
reviewed_at_head: 091b0fad8e5396f3c15fa97196d385c500d3b908
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: de021febceb91e8e88aa3fea313e841b117108e07200fb7f67b46389ba63d46d
digest_kind: plan_scope_digest
bound_set_digest: 961135fd91c80b27d6f2822d80411a5212c94ca90442b96d76d53f1be382c41e
base: 26db89c92fedef044ddbfb1c7dc93545a6187033 (에라타 직전 HEAD)
commits: C1 76a4e42333fafb0d28af6e64b08a285b77798fb1 (에라타+lockstep) · C2 091b0fad8e5396f3c15fa97196d385c500d3b908 (O-6 재결속)
captured_at_utc: 2026-09-04T02:21:56Z
prior_verdict: docs/reviews/phase0-completion-contract/20260902-195656/verdict.md
job_id: review-mtmbw5f3-xpo98b
subcommand: adversarial-review (--wait · setsid · base 26db89c9 · scope branch · focus 로 두 결속 경로 diff 로 한정)
verdict_recovered_at_utc: 2026-09-04T02:28:11.167Z
verbatim_sources: codex-result.json · codex-wait.out · evidence/scope-diff.patch · evidence/lockstep-diff.patch
---

# Codex verdict — verbatim (structured output, 무편집)

```json
{"verdict":"needs-attention","summary":"출하 차단. O-6의 두 digest, C1 decided_at_head, blob/행수는 일치했고 계약 검사와 145개 self-test는 rc 0이었다. 그러나 D-4는 NONE을 구조적으로 검증하지 못해 저작자가 UNBOUND 또는 간접 의존을 NO_DEPENDENCY로 바꿀 수 있다. 또한 요청된 `tos_contract_index.py --check` 직접 실행은 `--out` 부재로 rc 2였다.","findings":[{"severity":"high","title":"D-4가 NONE 자기신고를 막지 못해 UNBOUND 의존을 숨길 수 있다","body":"D-4는 `NONE` 선언을 검증할 때 현재 VER-002 우주 키의 로컬 토큰 참조만 찾는다. 따라서 우주 밖 의존 키(정의상 D-3에서는 UNBOUND여야 함)는 같은 스캔 범위에 리터럴로 존재해도 검출 대상이 아니어서, 저작자가 그 키를 선언하는 대신 NONE을 쓰면 NO_DEPENDENCY와 §13 면제를 얻는다. 실제 resolver의 `max_age_bound`가 바로 이런 우주 밖 키 클래스다. 또한 module은 패키지 재귀, class/method는 파일 하나만 보므로 외부 helper가 실제 키를 읽고 사이트가 그 결과를 소비하는 경우도 0건으로 접힌다. 계약은 별칭·간접 참조를 못 본다고 인정하지만, 그러면서도 0건을 완료 처분으로 사용하므로 UNDECIDED 차단을 다시 연다. `토큰 리터럴 참조`도 식별자·문자열·주석 중 무엇을 세는지 정의하지 않아 C4 구현이 여러 비동치 해석으로 갈릴 수 있다.","file":"docs/plans/2026-08-12-tos-phase0-completion-contract-design.md","line_start":2829,"line_end":2841,"confidence":0.99,"recommendation":"NONE 검증의 후보 우주와 의존 경계를 닫아라. 최소한 우주 밖 의존 후보도 UNBOUND로 포착하고, 외부 호출을 통한 전이 의존의 귀속 규칙 및 토큰화·주석/문자열 처리 규칙을 명시해 미확정 사례는 UNDECIDED로 차단해야 한다. 계약 본문 추가 편집이므로 S-26 ⑥에 따라 ② 카운터가 다시 0으로 리셋되고 O-6 재결속·레인 B 재심 비용이 발생함을 함께 기록하라."}],"next_steps":["D-4의 우주 밖 키 및 스캔 범위 밖 간접 의존 대조군을 추가하고, 둘 다 NO_DEPENDENCY가 아닌 UNDECIDED 또는 UNBOUND로 귀속되는지 검증한다.","계약 수정 후 plan_scope_digest와 bound_set_digest를 다시 계산하고 O-6를 재결속한 뒤 레인 B 재심을 반복한다.","색인 검증은 실제 생성 산출물 경로를 `--out`으로 지정해 다시 실행한다. 현재 요청에 적힌 `python tools/tos_contract_index.py --check` 그대로는 rc 2다."]}
```

# 수용검사 (오케스트레이터 = Claude)

| # | sev | file:line 실재 | silenced | 비협상 배치 | 처분 |
|---|---|---|---|---|---|
| 1 | high | 실재 — 계약 :2829-2841 D-4 본문(52차 · C1 76a4e423). 스캔 후보 = VER-002 우주 키만 → 우주 밖 의존 키(D-3 에서 UNBOUND · §13 등재 의무)를 선언 대신 `NONE` 으로 적으면 스캔이 잡지 못하고 NO_DEPENDENCY(§13 면제)를 얻는다. resolver 의 `max_age_bound` 가 실재하는 그 클래스. 또 «토큰 리터럴 참조» 의 토큰화(식별자·문자열·주석)와 전이 의존 귀속 규칙이 미정의 | 아니오 — 52차 «정직 경계» 문단이 별칭·간접 참조를 못 본다고 자인했으나, 자인은 0건을 완료값으로 쓰는 것을 정당화하지 않는다(v1.6 「막아야 닫힌다」) | 없음(계약 편집 비용을 함께 기록하라는 권고 — 수용) | **채택** → 53차 에라타 |

기각 0 · 채택 1/1. Codex 가 확인한 것: O-6 두 digest · decided_at_head=C1 · blob/행수 일치 · tos_contract_check + self-test 145 rc 0. next_steps 3(색인 `--check` 는 `--out` 산출물이 필요)은 focus 의 오기 — 이 저장소에 색인 산출물 파일은 없고 `--locate` 만 쓴다. 다음 focus 에서 그 요구를 제거한다.

## 처분 (53차 에라타 설계 — 저작은 Opus 레인 · 심판은 Codex)

1. **의존의 정의를 D-1 로 환원**: 사이트의 «의존 키» 는 D-1 이 정의한 대로 docstring 이 리터럴로 인용하는 키다. 외부 helper 가 키를 읽어 파생값을 넘기는 전이 소비는 그 helper 의 의존이지 이 docstring 사이트의 의존 키가 아니며(§7.1 이 사이트 7곳을 고정), 스캔은 그 정의 위의 «추가 가드» 다.
2. **NONE 스캔의 후보 우주를 닫는다**: VER-002 우주 키 ∪ §7.1 전 사이트가 선언한 키 전부(D-5 의 VER-002-KEYS 및 CONTRAST — 기계 파생 가능한 닫힌 집합). 후보 중 하나라도 사이트 범위에 리터럴로 있으면 UNDECIDED(선언 누락 의심 — 그 키를 선언하면 D-3 으로 UNBOUND/VALUED/BLOCKED 가 된다). resolver 의 `max_age_bound` 류가 이 집합에 들어가 Codex 가 든 사례가 닫힌다.
3. **토큰화 규칙 명시**: 범위 안 모든 `*.py` 의 원문 전 행(코드·문자열·주석·docstring 구분 없이) 에 대해 단어 경계 정규식 `(?<![A-Za-z0-9_])KEY(?![A-Za-z0-9_])` — 상위집합(보수적) 이라 주석 안의 언급도 UNDECIDED 를 만든다(정직: 과잉 차단 방향).
4. **정직 경계 재진술**: 후보 우주 «밖» 의 이름(어느 사이트도 선언하지 않은 새 의존)은 여전히 못 본다 — UNCHK-015 의 거울상 그대로. 이것은 UNBOUND 의 K 적절성과 같은 한계이지 NONE 고유의 구멍이 아니다.
5. 비용 기록: 계약 편집이므로 S-26 ⑥ 재적용(② 카운터 0 유지) · O-6 재결속 · 레인 B 재심 반복.
