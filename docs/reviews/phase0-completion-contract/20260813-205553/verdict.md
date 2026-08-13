# verdict — 레인 B (계획 심판) · v2.5

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: d52fd1584eac7ffc4af3db620f69e8bfd6e202f800ca7156c7011df6c9c70945
reviewed_version: v2.5 (3825행)
findings: 6                        # high 5 / medium 1
prior_verdict: .omc/review/20260812-231234/verdict.md   # v2.3 (레인 A·B 공통 기원)
mode: A (adversarial-review, --scope working-tree), write=false
lane: B (계획) — plan_scope_digest 로 계획 문서 2건에만 결속
```

리비전 결속: 디스패치 직전 = 심사 종료 후 = 오케스트레이터 제시값 **3자 일치.**
산출물 해시가 레인 A 산출물 8건 전부와 상이(오염 0).
**스트리밍 트랩**: 중간 preview 3회 **전부 `needs-attention`** — 레인 A 에서 4회 재현된
approve→needs-attention 뒤집힘이 **이번엔 발생하지 않았다.**

## 처분

**F4 부분해소 · F5 부분해소 · IND-1 미해소 · F7 회피(범위축소) 유지 · IND-2 해소.**
`CLAUDE.md` 비협상 규칙 직접 충돌 **없음.**
그리고 **v2.5 편집 자체가 OQ-11 승인 결속을 무효화했다** (신규 high).

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

No-ship. 처분은 F4 부분해소, F5 부분해소, IND-1 미해소, F7 회피(범위축소), IND-2 해소로 판정한다. v2.5 편집이 OQ-11 승인 결속도 무효화했다. CLAUDE.md 비협상 규칙과의 직접 충돌은 발견하지 못했다.

Findings:
- [high] v2.5 편집이 OQ-11 승인의 결속을 이미 무효화했다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:3076-3078)
  현재 두 bound_paths를 아티팩트의 명령으로 재계산한 값은 `676450757571556e40ab58dc7a8783fb872365ed74a30571c39b094679447f51`이지만, 판정문은 v2.4의 `ac8d74ba…`를 보유한다. 판정문 자체가 불일치는 현 내용의 승인이 아니라고 규정하고 계획도 1365-1366행에서 이를 인정한다. 그런데 이 행과 3176-3189행은 여전히 6e 완료·APPROVED·잔여 게이트가 review 하나뿐이라고 주장한다. 활성 서술도 실제 `bound_set_digest`를 `plan_scope_digest`로 잘못 부른다. 따라서 F5와 IND-1의 현재 상태 전제가 승인 없는 상태에 서 있다.
  Recommendation: v2.5 내용을 먼저 동결한 뒤 최종 두 문서 digest에 결속된 운영자 판정을 새로 취득하고, 실제 승인 전에는 6e·현재 상태를 미충족으로 표시하라. digest 값만 복사해 갱신하지 말고 `bound_set_digest` 명칭도 활성 소비처 전부에 전파하라.
- [high] IND-1은 영구 대기를 `raised_at` 이전으로 이동시켰다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:3147-3174)
  계약은 운영자가 `raised_at`을 기입해야만 시계를 시작하고, 누락이면 명시적으로 '6e 미착수이지 무응답이 아니다'라고 한다. 제기 의무의 발생 조건이나 제기 자체의 기한이 없어 운영자 무행위는 영원히 NO_RESPONSE가 되지 않는다. 더구나 `raised_at`의 권위 입력·불변성·재생성 시 보존 규칙 없이 생성물인 TOS-COMPLETION-STATUS에 직접 기입하며, deadline 미정 차단과 만료 전이는 §11 종료조건·계약 ID·대조군 어디에도 결속되지 않았다. named-TBD를 fail-closed라고 부른 것은 현재로서는 실행 가능한 계약이 아니라 산문이다.
  Recommendation: 재판정 요구가 발생하는 객관적 트리거와 durable `raised_at` 입력원을 정의하고, 누락·형식 오류·deadline 미정을 명시적 차단 상태로 만들라. 해당 상태 전이를 §11과 실제 `--check` 소비처에 결속하고 누락, 미만료, 만료, 재생성·시계 리셋 대조군을 추가하라.
- [high] DEFERRED_WITH_SCOPE는 여전히 범위를 표현하거나 검증할 스키마가 없다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:3116-3130)
  산출 계약의 필수 내용은 질문 ①~③뿐이며 `DEFERRED_WITH_SCOPE`의 범위 필드, 행 ID 문법, 닫힌 행 우주, 나머지 매핑 승인 결속을 정의하지 않는다. 그럼에도 3130행은 그 미정의 범위가 전역인지 부분집합인지에 따라 차단 또는 FWD-a 제외를 선택한다. 따라서 판정값만 DEFERRED_WITH_SCOPE로 쓰고 범위를 누락하거나 자유 산문으로 적어도 계약상 거부할 수 없으며, 생성기도 어느 분기를 택할지 검증할 수 없다. 팬텀 5번째 지표의 철회 자체는 보호를 줄이지 않으므로 F7과 같지 않지만, F5 전체는 부분해소에 그친다.
  Recommendation: 기계 판독 가능한 deferred-scope 필드와 전역/부분집합 문법, canonical evidence-id 집합, 잔여 매핑 승인 결속, 제외 목록 생성 규칙을 산출 계약에 추가하고 누락·고아·전역 오분류·stale 제외 목록 대조군을 실제 종료 소비처에 걸라.
- [high] F7은 보호를 복원하지 않고 비차단 레지스터로 옮겼다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:2919)
  계획은 YES→NO 전이가 U-1a의 소유자 의무와 게이트 기여를 제거하며, 남는 `closable_no_rows`도 앵커 동시 수정 시 침묵한다고 직접 인정한다. UNCHK-021은 `blocks_gate`가 없고 Phase 0에서 차단하지 않으므로 이 경로의 등재는 가시성 보강일 뿐 완화가 아니다. 이는 활성 보호를 철회한 뒤 표면만 이동한 것으로 직전 판정의 '회피(범위축소)'가 유지된다. 같은 UNCHK 행 안에서도 blocked_by는 Phase 1 이연이라고 쓰지만 owner_track은 Phase 2-5라 소유 시점까지 어긋난다.
  Recommendation: F7을 해소로 세지 말고 명시적 미해소 또는 수용 위험으로 분류하라. YES→NO 전이에 독립 리뷰 provenance와 결속된 승인 소비처를 두거나 전이 가드를 유지하고, UNCHK-021의 실제 owner_track을 한 값으로 확정하라.
- [high] F4의 config-스냅샷 정합은 검증 절차 없는 선언이다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:2968-2974)
  거짓 유일소스 문구와 rollback 목록은 정정됐지만, 새 핵심 계약인 'config와 문서 스냅샷 기계 대조'에는 문서 값을 추출하는 정본 규칙, 계약 ID, enforcement registry 소비처, 종료조건, 음성 대조군이 없다. §8의 T-71·T-76은 분류·레지스터 입력 뮤테이션만 기술하며 문서 스냅샷 단독 변경, config 값 불일치, config 파일·키·형 부재를 검증한다고 명시하지 않는다. 검사기가 config를 무시하거나 문서 리터럴만 drift해도 새 F4 계약이 green인지 red인지 증명할 수 없다.
  Recommendation: 문서 스냅샷과 config 사이의 canonical 결속 방식을 정의하고 강제 지점 레지스트리와 §11에 연결하라. 스냅샷 단독 변경, config 불일치, 파일 부재, 키 누락, 형 오류 각각이 실제 `tos_completion_status --check`를 red로 만드는 대조군을 명시하라.
- [medium] L-PROTO-STALE은 등재가 아니라 추적 불가능한 라벨이다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:232-253)
  문서는 §0.3의 다수 서술이 stale임을 인정하면서 `L-PROTO-STALE`로 등재했다고 하지만, 이 식별자는 문서에서 요약·변경 이력·이 문단 세 곳에만 있고 스키마·레지스터·종료 기준이 없다. 지목한 정본 `.omc/review/20260813-180752/verdict.md`도 `.gitignore` 대상이어서 clean checkout과 다른 운영자에게 전달되지 않는다. 따라서 현재 문서는 알려진 stale 증거를 유지하면서 검증 가능한 정본이나 실제 소유 기록을 제공하지 않는다.
  Recommendation: 코드 레인을 재개하지 말고, 종결 요약과 L-PROTO-STALE의 owner·해소 기준을 추적되는 문서 또는 정식 limitation register에 보존하라. 그렇지 않으면 stale 활성 서술을 현재 계획에서 제거하거나 정확한 내용으로 갱신하라.

Next steps:
- Lane B와 P-0/D0 착수를 NOT_PASSED로 유지한다.
- OQ-11 재결속 후 F4·F5·IND-1의 계약과 대조군을 종료 소비처에 연결하고, F7은 해소가 아닌 잔여 위험으로 재분류한다.
- 최종 편집을 동결한 뒤 `bound_set_digest`와 계획 심사 digest를 다시 계산해 현행 버전 전체를 재심한다.
```

---

# 수용검사 (오케스트레이터) — **채택 6 / 기각 0**

기각 사유 3가지 중 해당 없음. 4건을 직접 실측했다.

| # | sev | 실측 | 처분 |
|---|---|---|---|
| 1 | high | `OQ-11-DISPOSITION.md:10 bound_set_digest: ac8d74ba…` · 문서 `:1365` 가 "digest 가 다르면 그 승인은 이 내용에 대한 승인이 아니다" 를 규정 — **v2.5 편집으로 불일치 확정** | 채택 |
| 2 | high | `raised_at` 기입 전에는 시계가 시작되지 않고, **제기 자체의 기한이 없다** | 채택 |
| 3 | high | 산출 계약 필수 내용이 ①~③뿐 — 범위 필드·행 ID 문법 부재 | 채택 |
| 4 | high | `UNCHK-021` 행: `owner_track` 열 = **`Phase 2-5`**, 본문 = **"Phase 1 이연"** — 실측 불일치 | 채택 |
| 5 | high | 정합 대조가 계약 ID·레지스트리 소비처·대조군 없이 선언만 | 채택 |
| 6 | medium | `git check-ignore` → `.gitignore:5:.omc/` — **판정 기록이 clean checkout 에 전달되지 않는다** | 채택 |

## ⚠ 오케스트레이터 실패 (finding #1)

**이것은 저작 실패가 아니라 오케스트레이션 실패다.** v2.4 변경 이력이 이 교훈을 이미 기록했다:

> Stop 게이트 적발 — 아티팩트가 **결속 규칙을 써 넣고 곧바로 위반했다**(계획 편집으로 digest
> 변경) → **결속은 대상 확정 후에 한다**는 순서 규칙을 아티팩트에 기록

오케스트레이터가 그 기록을 읽고도 **동결 없이 개정을 지시**해 같은 함정을 두 판 연속 밟았다.
올바른 순서는 **개정 → 동결 → 재결속(운영자 판정) → 심사**였다.

## ⚠ 세션 전체에 걸친 구조적 문제 (finding #6)

`.omc/` 는 `.gitignore` 대상이다. 따라서 **이 세션이 생성한 판정 기록 전부**
(레인 A 9회차분 + 레인 B) **가 clean checkout 과 다른 운영자에게 전달되지 않는다.**
코드 레인 종결 기록(`.omc/review/20260813-180752/verdict.md`)도 마찬가지이며,
v2.5 가 그것을 "정본" 으로 지목한 것은 **추적 불가능한 포인터**다.

이는 개별 finding 이 아니라 **기록 보존 방식의 결함**이며 운영자 처분이 필요하다.

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND plan_scope_digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립
```

**레인 B 통과 = 실행 착수 가능을 뜻한다. 현재 착수 불가.**
