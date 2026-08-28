# verdict — 레인 B (계획 심판) · v2.8 재심

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: cb6979f81476881af4513dd90b054142e0e2c381
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: f34756f36bdb7f090d281e1f9dacec8c6778d1869da43362680c9c382218b716
reviewed_version: v2.8 (5,268행) — 동결 03262ef7 · 실행 증거 ed11f68d · 6e‴ 재결속 cb6979f8 이후 심사
findings: 2                        # high 2
prior_verdict: .omc/review/20260814-110807/verdict.md   # v2.7 재심 (NOT_PASSED)
mode: A (adversarial-review, --scope working-tree), write=false
lane: B (계획) — plan_scope_digest 로 계획 문서 2건에만 결속
job: review-msslr7qi-52zbvn / thread 019fff16-cbea-7b33-b571-46e934b9be04
     # detached(nohup) 실행 · 정상 종료 635s · 좀비 잡 없음
```

리비전 결속: 디스패치 직전 = 심사 종료 후 재계산 **3값 전부 불변**(HEAD·plan_scope_digest·
아티팩트 content digest `2e965b11…`). 두 계획 문서 정지·작업 트리 13항목 전후 동일 —
Codex 쓰기 흔적 없음. Codex 도 동결→증거→재결속 순서·digest 일치를 독립 확인했다.

## 처분

**직전 3건: #1 부분해소 · #2 해소됨 · #3 부분해소.**
**#2(U-12 merge-DAG 유일화)는 이 아크의 잔여-우회 사슬에서 최초의 "해소됨" 판정**이다 —
경계 집합 + (author date, commit id) 전순서가 merge DAG 에서도 유일값을 준다고 심판이
확인했다(author date 위조·비단조성은 유일성을 깨지 않는 UNCHK-023 이연 한계로 정리).
`CLAUDE.md` 비협상 규칙 직접 충돌 **없음**. findings 3→2. **심판이 레시피를 현행
HEAD 에서 독립 재실행**해 `recipe_rc=0`·상태값 미산출을 실측했다 — 증거 문화의 교차 적용.

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

NO-SHIP. 독립 확인 결과 동결 `03262ef7` → 증거 `ed11f68d` → 재결속/현행 HEAD `cb6979f8` 순서, 결속 문서 정지 상태, digest `2e965b11…` 일치는 성립한다. 직전 findings: #1 `부분해소`—U-15 명령·변이 증거는 실재하지만 진입 거부 소비자는 없다. #2 `해소됨`—U-12의 경계 집합과 `(author date, commit id)` 전순서는 merge DAG에서도 유일값을 준다. author date 위조·비단조성은 유일성을 깨지는 않지만 `UNCHK-023`으로 이연된 신뢰 한계다. #3 `부분해소`—행 내용 digest는 추가됐지만 reviewer 아티팩트의 시점별 blob 결속이 없다. U-15-e (1)~(4)는 기록 형식상 충족하고 동결 블록 SHA와 변이 커밋도 독립 재파생됐지만, 상태값은 프로그램 산출이 아니라 사람이 붙인 해석이다. 7항목: ① needs-attention—pre-D0-A 강제 순서 미완; ② needs-attention—수동 절차 비우회와 reviewer 시점 결속을 가정; ③ needs-attention—실제 거부 및 U-16 사후변조 증명 부재; ④ 해당 없음—커밋별 rollback/revert 경로가 명시됨; ⑤ 해당 없음—추가 표면은 직전 high 대응 범위; ⑥ 해당 없음—CLAUDE.md:21-36,85-105의 설정·Redis·KST·EOD·선물 대칭/실주문·RL/TFT·ClickHouse 규칙과 직접 충돌 없음; ⑦ needs-attention—실제 진입 소비자와 reviewer/원장 사후변조 대조군 누락. 설정·마이그레이션·일반 테스트·문서·배포 표면은 계획에 포함돼 있다.

Findings:
- [high] U-15 레시피는 stale 상태를 출력할 뿐 D0-A 진입을 거부하지 않는다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:4148-4156)
  계획은 모든 항의 기대값 불일치나 명령 오류가 진입 거부를 일으킨다고 선언하지만, 레시피에는 비교·분기·비정상 종료 또는 진입 명령과의 결속이 없다. transcript도 `bash recipe.sh`와 T-81 스크립트가 모두 exit 0이었다고 기록한다(U15-ENTRY-CHECK.md:76,195,242). 현행 `cb6979f8`에서 독립 재실행해도 `verdict: needs-attention`과 R-7 비공집합(`03262ef7`)을 출력한 뒤 `recipe_rc=0`으로 끝났고 `d0a_entry_state`조차 산출하지 않았다. 따라서 `bfa4844d` 변이는 stale 검출의 실질적 증거지만 실제 진입 거부 증거는 아니다. 문서도 transcript를 생략한 진입을 1단이 막지 못한다고 인정한다(:4272-4274,4371-4376). stale 또는 미승인 계획으로 D0-A가 시작될 수 있어 직전 #1은 부분해소에 그친다.
  Recommendation: 실제 pre-D0-A 진입 소비자가 stale·미승인 입력에서 비정상 종료하거나 진입을 차단한 실행 결과가 나오기 전까지 #1과 Lane B를 통과로 계산하지 않는다.
- [high] U-16은 reviewer의 역사적 blob을 결속하지 않아 승인 후 digest 삽입이 통과할 수 있다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5098-5117)
  U-16-g3는 `approved_at_head`에서 `reviewer_ref` 경로가 존재했는지만 확인하고, U-16-h의 digest 리터럴 검사는 어느 커밋의 파일 본문을 읽는지 지정하지 않는다. 예컨대 H0에 digest 없는 무관 리뷰가 존재하고, H1에서 그 경로를 가리키는 승인 행을 선커밋하고, H2에서 `NO` 전이를 한 뒤, H3에서 기존 리뷰에 digest를 삽입하면 문언상 g3·h·g2와 `c_APP < c_NO`가 모두 성립할 수 있다. 즉 리터럴 존재는 선이미지 저항만 제공할 뿐 시간 순서를 함의하지 않는다. 원장을 append-only라고 부르지만 승인 행 변경을 검출하는 소비 규칙도 없다(:5071-5073). T-82 ⑧은 digest가 없는 기존 리뷰만, ⑩은 레지스터 행 변경만 다루며 reviewer/원장 사후변조를 시험하지 않는다(:2797). 이 우회는 `NO_ROWS_CLEAR`를 허위로 만들어 owner 의무와 Phase 0 차단을 제거할 수 있으므로 직전 #3은 부분해소다.
  Recommendation: `approved_at_head`의 정확한 reviewer blob 및 승인 행 불변성이 소비되고, `c_NO` 이후 reviewer·원장 변경 변이가 fail-closed라는 증거가 나오기 전까지 #3을 해소로 판정하지 않는다.

Next steps:
- Lane B와 P-0/D0 착수를 NOT_PASSED로 유지한다.
- U-15 transcript는 검출 증거로만 인정하고 실제 진입 소비자의 거부 결과를 확인한다.
- U-16에서 전이 후 reviewer 아티팩트 변경과 승인 원장 행 변경 변이를 검증한다.
```

---

# 수용검사 (오케스트레이터) — **채택 2 / 기각 0**

기각 사유 3가지(팬텀 file:line / 의도적 silenced / 비협상 배치) 중 해당 없음. 전건 실측.

| # | sev | 실측 | 처분 |
|---|---|---|---|
| 1 | high | `:4148-4156` 실재 — "하나라도 어긋나거나 명령이 오류로 끝나면 진입 거부"는 **산문 판정**이고 레시피 명령 블록에 비교·분기·비정상 종료 부재. transcript `:76`·`:242` "exit=0 — 판정은 출력 대조로 한다" 실재 — 상태값이 사람의 해석임을 자인 | 채택 |
| 2 | high | `:5098-5117` 실재 — g3 = `git cat-file -e`(**경로 존재만**, 내용 아님)·h 의 리터럴 검사는 읽는 blob 의 커밋 미지정 → H0~H3 사후 삽입 시나리오 문언상 통과. `:5071-5073` append-only 선언에 소비 규칙 부재 | 채택 |

## 관측 (finding 아님)

- **수렴 가속**: findings 6→3→3→**2**, **최초 "해소됨" 1건**(#2 merge-DAG). 잔여 2건은
  둘 다 "계약이 선언한 것을 실행/검증 가능하게 만들라"는 동일 방향 — #1 은 판정의
  기계화(비정상 종료), #3 은 결속의 시점화(역사적 blob).
- #1 해소 경로: 레시피에 **판정 하니스 형태**(대조·분기·`exit 1`)를 계약 전문으로
  저작하면 검사기 없이도 실행 가능한 거부가 성립한다 — 실행해 rc≠0 거부 증거를
  남길 수 있다(현행 상태가 이미 차단 상태라 음성 증거 즉시 생산 가능).
- #3 해소 경로: g3 를 존재 검사에서 **시점 blob 내용 소비**(`git show
  <approved_at_head>:<reviewer_ref>` 에 digest 리터럴 등장)로 강화 + 승인 행
  불변성 소비 규칙 + T-82 사후변조 변이(⑫ 전이 후 reviewer 편집·⑬ 원장 행 편집).

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND plan_scope_digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립
```

**레인 B NOT_PASSED 유지. P-0/D0 착수 불가.**
