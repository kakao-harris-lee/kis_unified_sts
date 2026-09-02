# 레인 B 계획 «재심» — §12.3.4-R 하니스 EPIPE 수리 + sha 재핀 (head cdecb692)

```yaml
adjudicator: codex
verdict: approve
reviewed_at_head: cdecb692e18b035e24b82f4e4a4e5a2f49f6c369
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 3af54706d41ccbb230f601f29cd058d98bd4d98716a682a4f4447f25cb6ba13b
bound_set_digest: e0729ff3ccbbab41b007464742290e4e875c07846b5a87d228727abc2ae4480f
job_id: review-mtjznj44-qzsjpk
job_class: review
base: origin/main
scope: branch
prior_verdict: docs/reviews/phase0-completion-contract/20260902-174919/verdict.md
```

**findings 0 · 신규 material 0.** 이번 재심은 직전(20260902-174919)과 달리 계획 문서의
**내용이 바뀌었다**: 운영자 명시 지시(2026-09-02 «계약 §12.3.4-R 의 sha 를 재핀 진행»)로
① 계약이 verbatim 으로 담는 진입 하니스의 awk 프로그램 두 개가 `exit` 로 stdin 을 조기
종료해 gawk(GitHub ubuntu 러너 기본)에서 printf EPIPE → pipefail → HARNESS_ABORTED 를 내던
결정성 결함(mawk·macOS awk 는 통과 — «awk 구현이 판정을 결정»)을 `!done` 가드 + 플래그로
전 입력을 소비하도록 수리하고(첫 키만 채택 — 의미 보존, 708 비교 차이 0, T-81 ⑨ 보존)
② 하니스 sha 를 `1817c9ef…` → `059e13f2…` 로 회전해 계약 결속값 여섯 자리·정본 B 잡
템플릿·개발계획 두 자리·에라타(S-26 ⑥ 자기 적용 → ② 카운터 0 명시)·자기인용 좌표를
lockstep 으로 갱신했으며(C1 `8199bb38`) ③ O-6 재결속으로 OQ-11 아티팩트
`bound_set_digest` 를 `e0729ff3…` 로 갱신했다(C2 `cdecb692` · `requesting_plan_version`
v2.22 유지 · disposition/deferred_scope 불변). 심사 범위는 `git diff e46dbd88 cdecb692 --
<두 경로>` (74+/17−) 전부다.

> **2026-08-30 재심 정지 지시와의 관계**: 이 stamp 는 계약 내용 재심(#22)의 재개가 아니라,
> 운영자가 명시 지시한 sha 재핀에 U-15 R-7 이 요구하는 **재결속 심사**다. 재핀 지시가
> 계약 본문 편집을 수용했으므로 그 부속인 이 심사도 그 지시에 포함된 것으로 읽었다 —
> 심사 범위는 재핀 diff 로 한정했고 계약의 다른 내용은 재심하지 않았다.

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "approve",
  "summary": "SHIP. 하니스 펜스와 파일은 byte-identical이고 sha 059e13f2…와 O-6 digest e0729ff3…도 재계산값과 일치한다. awk 변경은 첫 키 선택을 유지하면서 전 입력만 소비하며 T-81 ⑨의 fail-closed 경로도 보존한다. 옛 sha의 살아 있는 누락, currency/좌표 불일치, §12.1·§8·O-6 규칙 위반은 발견되지 않았다.",
  "findings": [],
  "next_steps": []
}
```

원문 전체는 `.omc/review/20260902-195656/codex-raw.json`(`parseError: null` ·
`adversarial-review` 구조화 출력). 같은 focus 로 포워더가 두 잡을 완주시켰고(첫 잡
`review-mtjzg4yd-1w38uv` 도 approve·findings 0 — «708개 코퍼스 비교 차이 0 · pipefail 을
우회하지 않고 EPIPE 원인 제거» · 원문 `codex-raw-first.json`), 판정으로 채택한 것은
나중에 완료된 `review-mtjznj44-qzsjpk` 다. 두 판정은 결론·근거가 일치한다.

## 수용검사 (오케스트레이터)

- findings 0 — 기각·분리 대상 없음.
- 리비전 결속: `reviewed_scope_digest` 는 codex-gate `plan_scope_digest`(HEAD + 두 경로
  워킹트리 내용) 로 디스패치 직전 계산(`3af54706…`); 디스패치와 기록 사이 편집 0.
- 오케스트레이터 독립 실측(C2 head): 계약 검사기 PASS · self-test 145 PASS · O-6 digest
  재계산 == 아티팩트 · 새 sha 리터럴 전 결속 자리 실재(옛 sha 는 불변 transcript 와
  «회전 전» 언급만) · ubuntu gawk 컨테이너에서 하니스가 R-7 까지 도달(HARNESS_ABORTED 소멸).
- 이 verdict 착지 커밋(C3)은 bound_paths 무접촉 → R-7 `cdecb692..HEAD -- bound_paths` = ∅.
