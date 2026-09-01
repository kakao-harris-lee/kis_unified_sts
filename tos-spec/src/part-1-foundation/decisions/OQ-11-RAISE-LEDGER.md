# OQ-11 Raise Ledger — U-12 durable `raised_at` 입력원

> **Document class**: 추적 원장 (append-only). 판정 아티팩트가 아니다 — OQ-11 의
> 판정은 `OQ-11-DISPOSITION.md`(같은 디렉터리·별도 파일)가 담고, 상태 파생은
> D0-A 검사기가 담당한다. **판정 부재가 원장 부재를 함의하면 안 되므로 별도
> 파일이다.** 이 원장의 스키마·파생·소비 규칙의 유일 소스는
> `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md` §12.3.1
> (`U-12` — 특히 ①-b·②·③)이며, 여기서 재기술하지 않는다 (S-14).

## 규율 (전부 §12.3.1 인용 — 이 파일은 규칙을 신설하지 않는다)

- **append-only**: 기존 행의 수정·삭제는 위반이며 git 이력에 남는다 (U-12 ② 보존 규칙).
- 생성물(`TOS-COMPLETION-STATUS`)은 이 원장을 **읽어 노출할 뿐 기입하지 않는다** —
  재생성이 시계를 되돌리지 못한다 (U-12 ②).
- `closed_by` 가 빈 행 = **열린 에피소드** (U-12 ②).
- `raised_at` 기재값은 그대로 소비되지 않는다 — 소비값은 `raised_at_effective`
  (min 3항 파생, U-12 ②)다.
- `trigger_at_head` 기재값은 대조 대상이다 — ①-b ③ 이 재파생한 `trigger_commit`
  과 다르면 `RAISE_MALFORMED` (U-12 ②).

## 행 스키마 (U-12 ② 인용)

`episode_id | raised_at (UTC ISO-8601) | trigger_at_head | closed_by`

## 에피소드

| episode_id | raised_at | trigger_at_head | closed_by |
|---|---|---|---|

## 탄생 시점 실측 (2026-09-01 · 표제 아래에는 관측만 둔다)

원장은 **행 0개로 태어난다.** 근거 — U-12 ① 트리거 4항을 커밋 `55872545`
시점 내용으로 실측:

```text
(i)   아티팩트 존재       tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md — 실재
(ii)  disposition          RESOLVED_MAPPING_APPROVED ∈ 판정 어휘 4종
(iii) bound_paths          계약 §12.3.1 요구 집합(2경로)과 일치 — 더도 덜도 아님
(iv)  digest 재계산        daaba47b1c4b2b31717c098c8d761d9fd2b0cd1eb7e0d55b48d46a4e059f1c3b
                           == 아티팩트 보유값 (일치)
⇒ oq11_rebinding_required = False
```

트리거가 불성립이므로 열린 에피소드가 없는 것이 정확한 상태다 — 빈 원장은
`RAISE_MISSING`(트리거 성립 ∧ 열린 에피소드 부재)에 해당하지 않는다.

**이 실측은 탄생 시점 기록이며 현재 시제 주장이 아니다.** 이후의 상태는 검사기
(`tools/tos_completion_status.py --check` — U-12 ⑤ 강제 지점)가 매 실행
재파생하며, 이 절의 값은 그 판정의 입력이 아니다.
