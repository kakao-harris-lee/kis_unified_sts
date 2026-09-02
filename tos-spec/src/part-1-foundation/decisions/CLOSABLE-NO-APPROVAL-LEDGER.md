# Closable-NO Approval Ledger — U-16 전이 승인 원장

> **Document class**: 추적 원장 (append-only). `U-12` 원장(`OQ-11-RAISE-LEDGER.md`)
> 과 **별도 파일**이다 — 한 원장의 부재가 다른 원장의 부재를 함의하면 안 된다
> (U-16-b). 이 원장의 스키마·간선 대응·소비 규칙(g1~g6·h)·상태 전순서의 유일
> 소스는 `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`
> §13.6.5 (`U-16`)이며, 여기서 재기술하지 않는다 (S-14).

## 규율 (전부 §13.6.5 인용 — 이 파일은 규칙을 신설하지 않는다)

- **append-only**: 행의 수정·삭제는 위반이며, g5 가 도입 시점 blob 과 현행을
  대조해 `APPROVAL_ROW_MUTATED` 로 차단한다.
- 행이 간선을 «덮는가»는 전부 **구조 파생**(transition 일치 · `c_APP` 진 조상 ·
  digest 대조)으로 결정된다 — 자기신고 순번(`edge_seq`)은 스키마에 존재하지
  않는다 (U-16-b #2, v2.15 마감).
- 승인 행의 도입 커밋 `c_APP` 는 구조 집합으로 파생되며 `|c_APP|=1` 이어야 한다
  (U-16-c).

## 행 스키마 (U-16-b «#2» 블록 인용)

`row_id | transition | row_content_digest | approved_at_head | reviewer_ref | rationale_ref`

## 승인 행

| row_id | transition | row_content_digest | approved_at_head | reviewer_ref | rationale_ref |
|---|---|---|---|---|---|
| UNCHK-014 | ABSENT->NO | f5b8616419142924783eca9fdf8630e0e4412f686cf4e80562dc669bea31f87f | fb263a6ef689b22390bacb8671362792fd50db9e | docs/reviews/phase0-completion-contract/20260901-223154/UNCHK-014-NO-ROW-REVIEW.md | docs/plans/2026-08-12-tos-phase0-completion-contract-design.md §13.5 |

## 탄생 시점 기록 (2026-09-01 · 관측만)

- 이 원장은 §12.1 트리·U-16-c 의 요구대로 **레지스터 CSV(②) 도입 커밋보다
  먼저** 착지한다 — 시드의 `closable=NO` 1행(`UNCHK-014`, 출생-NO)이 그
  대상이며, ② 착지 시 그 간선(`ABSENT->NO`)을 위 행이 덮는다.
- `approved_at_head` = ⓪ 커밋(제안 + 독립 리뷰, Codex adversarial-review
  `b4nl6nxuv` · approve · findings 0). ⓪ ⊰ ①(이 파일의 도입 커밋)이며 동일
  커밋이 아니다 — g6 이 소비한다.
- `row_content_digest` 의 대상은 ② 에 도입될 레지스터 행이고 보유처는 이
  원장이다 — 자기참조가 아니다 (U-16-f).
