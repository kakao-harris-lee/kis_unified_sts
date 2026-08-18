# verdict — 레인 B (계획 심판) · v2.13 재심

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: b259669cabb294c9cd0a663801d60784403e1ec3
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 3254f437fe0ae6c9ea311ad542d233e7b61481316bf822fb03e8ee62310de678
reviewed_version: v2.13 (6,226행) — 동결 8a25c3c0 · 증거 3134a87b · 재결속 b259669c
findings: 3                        # high 2 / medium 1 — 직전 3건 전부 "부분해소"
prior_verdict: .omc/review/20260815-144959/verdict.md   # v2.12 재심
mode: A (adversarial-review, --scope working-tree, --wait), write=false
lane: B (계획) — plan_scope_digest 로 계획 문서 2건에만 결속
job: review-msypyvsn-uiqr7t / codex thread 01a01522-9d24-7583-bcbc-60bfbde24354
     # 1회 디스패치 정상 완료(6m 28s) — 재시도 불요. companion 1.0.6 foreground 출력엔
     # "Codex session ID" 트레일러 줄이 없어 threadId/turnId 로 기재(포워더 실측)
```

리비전 결속: 디스패치 직전 = 심사 종료 후 재계산 **불변**(HEAD·plan_scope_digest·
내용-only digest `796ca1e0…` == 아티팩트 보유값 `OQ-11-DISPOSITION.md:10`). Codex 도
결속 일치와 `8a25c3c0→3134a87b→b259669c` 순서를 독립 확인.

## 처분

**직전 3건: #1 부분해소 · #2 부분해소 · #3 부분해소** — 이번 판에서 신규 해소 0
(아크 누적 해소 4건 유지: U-12 merge-DAG · U-16 시점-blob · U-16 전칭 통일 ·
K-14/T-83). `CLAUDE.md` 비협상 직접 충돌 **없음**(9판 연속). 회피 판정 0.
잔여 3건은 전부 **"저작은 옳은 방향이나 소비 규칙이 아직 우회를 남기고, 실행 증거가
실제 소비자에서 나오지 않았다"** 는 한 클래스:
① CORR(d) 는 transcript 의 **생성 순서·d 동일성**을 검사하지 않아 사후 세탁 가능
(비가드 d → parent(d) 에서 하니스 재실행 → d′≠d 의 ENTRY_OK transcript 가 유일
CORR 항) + 손 실행기가 형식 미검증·파일당 1건 접기 + **§11 행이 CORR 의 ENTRY_OK
조건을 누락**(S-22 클래스) ② g6 의 `c_R` = **경로 최초 도입 커밋**이라 기존 경로에
digest 를 넣는 수정 B∥승인 A 변종을 못 잡음 ③ edge_seq 병렬 충돌의 **재부여 append
복구가 자기 MALFORMED 규칙과 모순**(중복 키가 남아 영구 차단).

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

출하 불가. 직전 #1·#2·#3은 모두 부분해소이며, 해소됨이나 회피로 판정하지 않는다. HEAD b259669c, plan_scope_digest 3254f437…, bound_set_digest 796ca1e0…, 8a25c3c0→3134a87b→b259669c 순서는 확인됐고 쿼터 소진 기록은 결함이 아니다. 심사 기준 (1)(2)(3)(4)(7)은 미충족이고, 범위 이탈 및 CLAUDE.md 비협상 충돌은 발견하지 못했다.

Findings:
- [high] 직전 #1 — 부분해소: CORR은 사후 생성 transcript로 비가드 착수를 세탁할 수 있다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:4775-4783)
  부모 결속과 ENTRY_OK 조건은 실질 보강이지만, CORR(d)는 transcript가 d보다 먼저 생성됐는지 또는 transcript에 기록된 가드의 D0A-FIRST 커밋이 실제 d인지 검사하지 않는다. 따라서 비가드 d를 먼저 만든 뒤 parent(d)에서 하니스를 재실행해 별도 D0A-FIRST d′와 ENTRY_OK transcript를 만들면 d′≠d여도 유일한 CORR 항으로 통과할 수 있다. 실행 증거의 ⑮는 직전 우회와 같은 parent 구성이지만, 실제 방출값은 보조 스크립트의 `|CORR(d)| = 0`뿐이고 `TRANSCRIPT_MISSING`/red는 산문 판정이다(U15-ENTRY-CHECK.md:525-574). 그 보조 스크립트는 U-15-e 형식 검증도 하지 않고 다중-run 파일을 파일당 1건으로 접어 |CORR|>1도 우회한다(:578-624). 실제 소비자는 아직 리뷰 표면이라고 문서가 인정한다(:4817-4821). 또한 §11은 CORR의 ENTRY_OK 조건을 누락한 채 존재·부모 일치 두 조건만 적고 `NOT_STARTED`만 비차단이라고 주장해, ENTRY_PROVENANCE_CLEAR도 비차단인 상태 집합과 충돌한다(:3361). 예방이 UNCHK-008 Phase 1로 남은 점까지 포함하면 #1은 부분해소다.
  Recommendation: 실제 status 소비자가 사후 생성된 d′ transcript, 동일 파일 내 복수 매치, 차단 transcript를 각각 거부하고 선언된 상태값과 비정상 rc를 직접 방출하는 증거가 나오기 전까지 #1을 미통과로 유지한다.
- [high] 직전 #2 — 부분해소: g6은 리뷰 내용이 아니라 경로 최초 도입만 순서화한다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5971-5991)
  strict 조상 극성과 merge-base 판정 자체는 결정적이며 단순 R∥A는 닫는다. 그러나 c_R은 reviewer_ref 경로의 최초 도입 커밋일 뿐, 승인된 digest를 담은 blob의 도입 커밋이 아니다. 공통 조상 H0에서 빈/기존 reviewer 경로를 만든 뒤, 브랜치 B에서 digest를 삽입하고 형제 브랜치 A에서 approved_at_head=B인 승인 행을 만들고, 두 브랜치를 NO 전이 M에서 merge하면 c_R=H0은 c_APP=A의 진 조상이라 g6가 통과한다. 동시에 B는 M의 조상이고 B 시점 blob에는 digest가 있어 g3·h도 통과하지만, 실제 리뷰 내용 B는 승인 A의 조상이 아니다. T-82 ⑮는 새 reviewer 아티팩트 R과 A의 병렬 도입만 기술해 이 기존-경로 변종을 덮지 않으며 실행 증거도 없다(:2894, :4256). 따라서 산문 순서의 일부만 소비 규칙으로 옮겨졌다.
  Recommendation: 기존 reviewer 경로의 digest-bearing 수정 B와 승인 A가 병렬인 merge-DAG가 실제 소비자에서 APPROVAL_ORDER_INVALID로 red가 되는 증거 전에는 #2를 해소로 계수하지 않는다.
- [medium] 직전 #3 — 부분해소: append-only 재부여 절차로 병렬 edge_seq 충돌을 복구할 수 없다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5913-5926)
  (row_id, edge_seq)는 선형 ABSENT→NO→YES→NO 반복을 결정적으로 표현하므로 문구만 추가한 것은 아니다. 하지만 문서는 병렬 브랜치가 같은 seq를 부여하면 MALFORMED라고 한 뒤, 머지 후 재계산한 행을 append하면 복구된다고 주장한다. 바로 다음 규칙은 기존 행을 남기면서 동일 (row_id, edge_seq)가 둘 이상이면 항상 APPROVAL_MALFORMED라고 한다. 새 번호 행을 append해도 기존 중복 키는 남으므로 NO_ROWS_CLEAR에 도달할 수 없고, 기존 행 수정·삭제는 append-only 및 g5 불변성에 걸린다. T-82 ⑯은 선형 반복 양성만 다루고 이 병렬 충돌·복구 경로는 실행되지 않았다(:2894, :4257). 정상 병렬 작업이 영구 차단되는 실패/롤백 결함이 남는다.
  Recommendation: 기존 승인 행의 삭제·변조·이력 재작성 없이 병렬 seq 충돌 상태에서 실제 소비자가 NO_ROWS_CLEAR로 복구되는 양성 증거가 확인될 때까지 #3을 미통과로 유지한다.

Next steps:
- 레인 B를 NOT_PASSED로 유지하고 P-0/D0-A 착수를 차단한다.
- 재심 증거는 실제 status 소비자에서 사후 transcript 세탁, 기존 reviewer 경로의 B∥A, 병렬 edge_seq 충돌 복구를 직접 실행해야 한다.
- 대상 두 계획 문서가 변경되면 현재 plan_scope_digest 승인을 무효화하고 다시 결속한다.
```

---

# 수용검사 (오케스트레이터) — **채택 3 / 기각 0**

기각 사유 3가지(팬텀 file:line / 의도적 silenced / 비협상 배치) 중 해당 없음. 전건 실측.

| # | sev | 실측 | 처분 |
|---|---|---|---|
| 1 | high | `:4775-4783` 실재 — CORR(d) 3조건에 transcript 생성 순서·d 동일성 조건 부재 확인. `:4817-4821` "그 전까지는 리뷰 표면" 자인 실재. `:3361` §11 행 = "① 대응 transcript 존재 ② parent == R-0 head **둘 다**" — **ENTRY_OK 조건 미전파 확인**(S-22 클래스, U-15-g-3 재저작이 §11 행에 안 미침) + "NOT_STARTED 가 유일한 비차단 값" 문구가 같은 행의 `{ENTRY_PROVENANCE_CLEAR, NOT_STARTED}` 집합과 자기모순 확인. transcript `:525-574` 실재 — 프로그램 방출값은 `\|CORR(d)\| = 0` 뿐, `TRANSCRIPT_MISSING` 은 산문 판정 확인. `:578-624` 실재 — corr-exec.sh 는 `found=1` 로 파일당 1건 접기(|CORR|>1 은 파일 단위로 붕괴)·(4c) 형식 검증 없음 확인 | 채택 |
| 2 | high | `:5971-5991` 실재 — `c_R` = "`reviewer_ref` 아티팩트를 **도입한** 커밋"(경로 최초 도입). 기존 경로의 digest-bearing 수정 커밋 B 와 분리되는 정의 확인. H0(빈 경로)→B(digest 삽입)∥A(approved_at_head=B)→M 구성에서 g6(H0 ⊰ A)·g3(B,A 각각 M 조상)·h(`git show B:` 에 digest) 전부 통과·B ⋠ A 성립 — 검산 일치. `:2894`/`:4256` T-82 ⑮ = "병렬 R∥A" 신규 아티팩트 도입 변형만 | 채택 |
| 3 | medium | `:5913-5926` 실재 — "해소는 재부여 커밋 … append(기존 행은 남고)" 직후 "같은 `(row_id, edge_seq)` 가 둘 이상 = `APPROVAL_MALFORMED`" — append 로 기존 중복 키가 소거되지 않아 MALFORMED 영구. 계약 내 자기모순 확인. `:4257` ⑯ 은 선형 반복 양성만 | 채택 |

## 관측 (finding 아님)

- **판정의 성격 변화**: 8판까지는 "미해소/신규 결함"이 섞였으나 이번은 **전건
  부분해소·회피 0·신규 결함 클래스 0** — 잔여는 세 축 전부 "**소비 규칙의 정밀도**
  + **실제 소비자에서의 실행 증거**"다. Codex 의 next_steps 가 세 실행 증거를
  명시했다: (i) 사후 transcript 세탁 거부 (ii) 기존 reviewer 경로 B∥A red
  (iii) 병렬 edge_seq 충돌 복구 양성.
- #1 저작 경로: CORR(d) 에 **d 동일성 조건** 추가 — transcript 가 기록한 도입
  커밋(하니스는 `&&` 우변 결과를 모르므로 **transcript 가 아니라 d 측에서
  transcript 를 가리키는 결속**이 자연스러움: D0A-FIRST 커밋 메시지/트레일러에
  transcript 경로+sha256 리터럴 → CORR 조건 (4) "d 가 t 를 인용" — 순환 없음:
  t 는 d 이전에 존재, d 가 t 를 가리킴) + 다중-run 파일의 **쌍 단위 계수**
  (파일당 접기 금지) + (4c) 형식 검증 소비 + §11 행 ENTRY_OK 전파(S-22) +
  "NOT_STARTED 유일 비차단" 문구 정정. 실행 증거: 실제 소비자(`--check`) 는 D0-A
  이후라 리뷰 표면 한계는 정직 잔존 — 손 실행기를 **선언 상태값+rc 방출**로 승격.
- #2 저작 경로: `c_R` 을 **digest-bearing blob 도입 커밋**으로 재정의
  (`git log --diff-filter=AM -S<row_content_digest> -- <reviewer_ref>` 의 최초
  커밋) — "경로 도입"이 아니라 "**내용 도입**" ⊰ c_APP. T-82 ⑰ 기존-경로 B∥A.
- #3 저작 경로: 병렬 충돌 복구를 **append 로 표현 가능**하게 — 예: 재부여 행이
  `supersedes: [(row_id, edge_seq)…]` 를 명시하고 MALFORMED 판정은 "supersede
  되지 않은 중복"에만 적용(g5 는 각 행 도입 시점 내용 불변 유지) — 또는 병렬
  seq 충돌을 MALFORMED 가 아니라 **머지 커밋 기준 전순서 재계산으로 결정적 재번호**
  (append 없이 소비자가 계산). 두 안 중 저작자 판단. T-82 ⑱ 병렬 충돌 복구 양성.

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND plan_scope_digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립
```

**레인 B NOT_PASSED 유지. P-0/D0 착수 불가.**
