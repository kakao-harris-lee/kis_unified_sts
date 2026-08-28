# verdict — 레인 B (계획 심판) · v2.12 재심 (쿼터 복구 후 재개)

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: d409ffd9ffd744b7fad302c6444af5d19891fcfc
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: d9419d21f948238dd48996d8df7d932ba4eabb3279acd9ad66cc306408598b1f
reviewed_version: v2.12 (6,040행) — 동결 cf9b0295 · 증거 69d28002 · 재결속 a191910e · 판정불능 기록 d409ffd9 이후 재개 심사
findings: 3                        # high 2 / medium 1
prior_verdict: .omc/review/20260815-092111/verdict.md   # v2.11 재심 (직전 실판정 — 20260815-102037 은 판정 불능 기록)
mode: A (adversarial-review, --scope working-tree), write=false
lane: B (계획) — plan_scope_digest 로 계획 문서 2건에만 결속
job: review-mstylikg-xrqhd5 / codex session 01a003fa-8d52-77a0-a5bf-236ab2511690
     # 크레딧 충전 후 1회 디스패치 정상 완료(8m 2s) — 재시도 불요
```

리비전 결속: 디스패치 직전 = 심사 종료 후 재계산 **불변**(HEAD·plan_scope_digest·
내용-only digest `934516a6…` == 아티팩트 보유값). Codex 도 결속 일치와
`cf9b0295→69d28002→a191910e→d409ffd9` 순서를 독립 확인. **쿼터 소진 기록은
결함으로 세지 않았다**(판정문 명시).

## 처분

**직전 3건: #1 부분해소 · #2 해소됨 · #3 해소됨** — 아크 누적 해소 **4건**
(U-12 merge-DAG · U-16 시점-blob · U-16 전칭 통일 · K-14/T-83).
`CLAUDE.md` 비협상 직접 충돌 **없음**(8판 연속). 신규 3건:
① #1 잔여 심화 — 비가드 착수 상존 + **신규 동시성 축**(하니스 통과와 D0A-FIRST
커밋 사이 HEAD 불변성을 잠그지 않음) ② **reviewer→승인 조상 순서 미강제** —
g3 는 각각이 전이 커밋의 조상이기만 요구해, 병렬 브랜치의 R∥A 를 merge 하면
산문의 ⓪→① 순서 주장이 소비 규칙보다 약한 fail-open ③ 원장 스키마의 간선
결정성 부재 — 반복 이력(ABSENT→NO→YES→NO)에서 단일 transition 행이 두 간선을
못 덮고, 복수 행은 g5 추출 모호/MALFORMED — 정상 반복 이력이 NO_ROWS_CLEAR 에
도달하는 양성 사례 부재.

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

출하 불가. 직전 판정별 결과는 ① 부분해소—transcript는 실제 D0A-FIRST의 직렬 가드 경로를 입증했지만 비가드 착수를 차단하지 않음, ② 해소됨—활성 U-16 본체·통과 상태·§11이 간선 전칭을 소비하며 단수 술어 잔존을 확인하지 못함, ③ 해소됨—T-83이 문법-유효·미매핑 음성과 매핑 내 양성을 분리함. bound_set_digest 934516a6… 일치 및 cf9b0295→69d28002→a191910e→d409ffd9 순서를 확인했고, 쿼터 소진 기록은 결함으로 세지 않았다. 기준별 판정: (1) needs-attention—U-15/U-16 순서 의존성이 실제 강제 조건과 불일치, (2) needs-attention—가드 준수와 단일 행에 대한 복수 승인 표현 가능성을 가정, (3) needs-attention—비가드·동시성·복수 전이 대조군 부재, (4) 해당 없음—새 비가역 선행 단계나 롤백 결함 없음, (5) 해당 없음—중대한 범위 이탈 없음, (6) 해당 없음—CLAUDE.md:21-36,85-87,104-107의 비협상 규칙과 직접 충돌 없음, (7) needs-attention—merge 승인 순서와 반복 전이 인접 영향 검증 누락.

Findings:
- [high] 직전 finding 1은 부분해소: 실제 경로를 사용했지만 가드 생략은 여전히 착수를 허용한다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:4687-4702)
  U-15-f는 규정 형식의 `&&` 우변 억제만 보장하고, 다른 착수 형식은 기계적으로 막지 않는다고 명시한다. transcript의 음성·양성 결과는 이 직렬 규정 경로와 일치하지만, 호출자가 하니스를 생략해 `config/tos_completion.yaml`을 직접 커밋하면 stale 승인 아래 D0-A가 이미 시작된 뒤 transcript 부재로만 사후 발견된다. 또한 하니스 성공과 D0A-FIRST 커밋 사이 HEAD 불변성을 잠그거나 재검사하지 않아, 그 사이 결속 경로가 변경되는 동시성 변이도 증명하지 못한다.
  Recommendation: 비가드 호출과 하니스 통과 직후 HEAD 변경 변이에서 파일 및 `--diff-filter=A` 도입 커밋이 모두 남지 않는 실제 진입 표면의 거부 증거가 확인될 때까지 해소로 계수하지 않는다.
- [high] U-16이 선언한 reviewer→승인 조상 순서를 실제 소비 규칙이 강제하지 않는다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5794-5803)
  g3은 `approved_at_head`와 `c_APP`가 각각 전이 커밋 `c`의 조상이기만 요구한다. 그러나 문서는 별도로 `approved_at_head ≤ c_APP`와 reviewer 아티팩트 ⓪가 승인 ①의 조상이어야 한다고 주장한다(5833행, 5990-5995행). 리뷰 R과 승인 A를 공통 기저의 병렬 브랜치에 만들고, A가 R의 hash와 digest를 참조한 뒤 둘을 전이 커밋 M에서 merge하면 R·A 모두 M의 조상이어서 g3·h·U-16-c를 통과하지만 R은 A의 조상이 아니다. T-82 ⑭의 병렬 `c_APP` 변이는 승인과 전이 간선 관계만 검사해 이 순서 위반을 잡지 못한다. 독립 리뷰 provenance 순서가 산문보다 약한 fail-open 계약이다.
  Recommendation: 리뷰와 승인 커밋이 병렬인 merge-DAG가 현재 소비자에서 반드시 red가 되는 대조군 증거 없이는 U-16의 독립 승인 순서 계약을 완료로 인정하지 않는다.
- [medium] 간선 전칭을 승인 원장 스키마가 결정적으로 표현하지 못한다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5744-5772)
  U-16-a2는 모든 →NO 간선마다 승인 행을 요구하지만 원장 행에는 `row_id`와 단일 `transition`만 있고 승인 또는 간선 식별자가 없다. 같은 행이 `ABSENT→NO`를 거친 뒤 YES로 돌아갔다가 다시 `YES→NO`가 되면 한 승인 행은 g1상 두 간선을 모두 덮을 수 없다. 복수 행을 두면 g5의 "그 row_id 행" 추출이 모호하고, 상태 정의는 중복 행을 MALFORMED로 분류한다(5807-5810행, 5864행). T-82에는 이 정상 반복 이력이 `NO_ROWS_CLEAR`에 도달하는 양성 사례가 없어 구현에 따라 영구 차단 또는 임의 행 선택이 발생한다.
  Recommendation: 서로 다른 transition을 가진 복수 →NO 간선을 한 현재 NO 행에 구성하고, 어떤 간선도 무시하지 않으면서 결정적으로 `NO_ROWS_CLEAR`에 도달하는 계약·대조군이 확인될 때까지 차단한다.

Next steps:
- 레인 B를 NOT_PASSED로 유지하고 P-0/D0-A 착수를 계속 차단한다.
- 재심에서는 U-15 비가드·HEAD 변경 억제, U-16 reviewer→승인 조상성, 동일 row의 이종 복수 간선 도달성을 실제 소비자 대조군으로 확인한다.

Codex session ID: 01a003fa-8d52-77a0-a5bf-236ab2511690
Resume in Codex: codex resume 01a003fa-8d52-77a0-a5bf-236ab2511690
```

---

# 수용검사 (오케스트레이터) — **채택 3 / 기각 0**

기각 사유 3가지(팬텀 file:line / 의도적 silenced / 비협상 배치) 중 해당 없음. 전건 실측.

| # | sev | 실측 | 처분 |
|---|---|---|---|
| 1 | high | `:4687-4702` 실재 — 가드 형태 정의에 하니스 통과↔커밋 사이 HEAD 불변 조항 부재 확인. 비가드 한계는 문서 자인 | 채택 |
| 2 | high | `:5794-5803` 실재 — g3 는 "간선 c 의 조상"만 요구. reviewer 커밋 ⊰ 승인 커밋 순서를 소비하는 규칙 부재 확인(산문 주장과 괴리) | 채택 |
| 3 | medium | `:5744-5756` 실재 — a2 전칭 ∃ 승인 행 + 원장 행 = row_id·단일 transition. 반복 이력의 복수 간선 표현·추출 규칙 부재 확인 | 채택 |

## 관측 (finding 아님)

- **해소 가속**: 직전 3건 중 2건 해소 — 누적 4건(U-12 DAG·U-16 시점-blob·U-16
  전칭 통일·K-14/T-83). findings 6→3→3→2→2→3→3 이나 실질 잔여 축은
  **U-15 착수 강제**와 **U-16 원장 정밀화** 둘로 수렴.
- #1 의 두 갈래: (a) 동시성(HEAD 잠금) — 저작 가능: D0A-FIRST 커밋의 **부모가
  하니스가 평가한 HEAD 와 동일**해야 한다는 결속(transcript 의 R-0 HEAD 소비)
  + T-81 변이 (b) 비가드 착수 — 진입 표면 거부는 브랜치 보호(UNCHK-008,
  Phase 1) 소관과 정면 접촉. 사후 관측 소비 계약(부모-transcript 대조로 위반
  기계 파생) + UNCHK-008 결속의 정직 저작이 경로.
- #2 저작 경로: g6 신설(reviewer 아티팩트 도입 커밋 ⊰ c_APP — 조상성 소비) +
  T-82 병렬 R∥A merge 변이.
- #3 저작 경로: 원장 행에 간선 식별(전이 커밋 결속) 추가·(row_id, 간선) 단위
  승인·g5 추출 재정의·정상 반복 이력의 NO_ROWS_CLEAR 도달 양성 대조군.

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND plan_scope_digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립
```

**레인 B NOT_PASSED 유지. P-0/D0 착수 불가.**
