# verdict — 레인 B (계획 심판) · 시도 2

## 심판 메타

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED          # approve 아님 → 구현 착수 불가
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 27163c5c46bc079f4299d1fe21475bb3a4241afa84de5cf3764b1de72b440144
reviewed_version: v1.1
findings: 10                     # high 5 / medium 4 / low 1
```

실행: 모드 B (`task --fresh --effort high`, `--write` 없음 = read-only),
job `task-msp6mj59-gjdipv`, 9m 28s, companion `1.0.6`.

**모드 A 2회 연속 desync 후 전환.** 1차 `review-msp597h9-j221r0`(22m51s, 판정 없음),
2차 `review-msp69ujr-kspc0j`(7m50s, 판정 없음). 2차 desync 3중 근거: 로그 바이트
6877 고정 4분 초과 / `updatedAt` 동결 / **`pid 93480` 사망했는데 status는 `running`**.
추가로 `progressPreview`의 grep이 focus text와 무관한 코드-리뷰 레인 내용이었다 —
`sessionRuntime.mode=shared`가 다른 턴을 서빙 중이었다는 신호.

모드 B는 프롬프트 내 JSON 계약으로 스키마를 강제했다. `outputSchema` 부착 경로가
아니므로 **구조 강제가 아니라 지시 준수**에 의존한다는 한계를 기록해 둔다.

## 수용검사 (오케스트레이터 = Claude)

**10건 전건 채택. 기각 0건.**

기각 가능 사유 3가지(팬텀 `file:line` / 의도적 silenced / 비협상 규칙 배치) 중
어느 것에도 해당하는 finding이 없다. Codex 자신이 기준 6(CLAUDE.md 비협상 규칙)을
**해당 없음**으로 명시 판정했고, 비협상 규칙과 배치되는 권고도 없다.

### 직접 실측으로 확증한 3건

| Finding | 실측 명령 | 결과 |
|---|---|---|
| #1 §9.1 SAFE 부재 주장 거짓 | `sed -n '545,587p' RFC-002-Architecture.md \| grep -o 'SAFE-[0-9]\{3\}'` | **SAFE-053 × 4** (HEAD·`15d48f72^` 동일) → 확증 |
| #5 선행 프로파일 파생 구현 존재 | `sed -n '1574,1600p' tools/tos_evidence_run.py` | `_profile_null_key_census` 실재 → 확증 |
| #3 D0-1이 없는 열 참조 | 설계문서 :260-262 vs :325-328 | `stand_in`/`owner_module`/`fault_path` 부재 → 확증 |

나머지 7건은 설계 계약의 불완전성 지적으로, 문서 내부 대조로 성립을 확인했다.

## 채택한 결함의 클래스 분석

#1과 #5는 **같은 뿌리**다.

- **#1**: `15d48f72`의 결론(revert)은 옳지만 그 근거 문장("§9.1 contains no SAFE
  identifier at all")은 거짓이다. 저작자는 결론이 옳은 커밋의 **근거를 재실측 없이
  권위로 인용**했다. → 이 저장소가 **#38 §0.3에서 이미 기록한 결함 클래스**의 재발
  ("두 라운드 비평 통과분 — 결론이 옳아도 근거는 독립 재실측 대상").
- **#5**: `tos_spec_status.py`가 프로파일을 읽지 않음을 확인하고 **전역 부재로
  일반화**했다. → **anti-phantom 양방향 grep 규율 위반**(존재·부재 양방향). 한 파일의
  부재는 저장소의 부재가 아니다.

두 건 모두 저작자가 자기 문서를 재검토해서는 나오지 않는다. **독립 심판의 실증.**

`acd45c43` 자체도 같은 클래스였다("전사할 뿐"이라는 자기신고가 거짓). 따라서 이
결함 클래스는 이 트랙에서 **세 번째 발생**이다.

## 재기록: 무엇이 살아남았고 무엇이 무너졌나

| §3.0 주장 | 판정 |
|---|---|
| `acd45c43`이 12행 표 추가로 30/30 달성 | **참** (Codex 확인) |
| `15d48f72`가 phantom 할당으로 revert | **참** (인용 문자 충실, 생략부 제외) |
| 상위 계획 §6 작업 3 = stale, 재도입 지시 | **참** — 기준선 `867327e9`이 `15d48f72`의 후손임이 확인됨 |
| "§9.1에 SAFE 식별자 없음" | **거짓** (#1) |
| "30/30은 GOV-001 G6로만 가능" | **미증명** (#2) — §27 컴포넌트 할당 + §9.1의 ledger→ADR-002-002 결속 + ADR-002-002 §1 소유 모델을 잇는 파생 경로가 배제되지 않았다 |

**핵심 진단(작업 3은 stale하며 단순 전사로 수행 불가)은 살아남았다.** 무너진 것은
그 처분을 "G6 외 경로 없음"으로 **봉인**한 부분이다. 처분을 종료 조건으로 고정하지
말고 열린 판정으로 되돌려야 한다.

## next_steps (Codex 원문)

1. §3의 사실 오류와 G6-only 결론의 권한 근거를 독립적으로 판정한다.
2. 상위 계획 §1·§6의 stale 문언을 해소하기 전에는 D0 구현에 착수하지 않는다.
3. D0-1/D0-2 입력 계약, join 실패 방향, Profile 승인 predicate, D0-5 키 결속의
   검증 가능성을 확정한 뒤 재심한다.
4. 누락된 불변식 대조군과 문서·CI·rollback 결속이 모두 명시됐는지 재심에서 확인한다.

## 게이트 판정

```
레인 B 통과 조건 = adjudicator: codex AND verdict: approve AND digest 일치
현재                = codex           AND needs-attention  AND 일치
                                          ^^^^^^^^^^^^^^^ 불성립
```

**실행 착수 불가.** v1.2 개정 후 재심 필요. 재심 시 이 파일의 경로를 focus에 지목하고,
채택 10건이 실제로 해소됐는지(회피가 아니라) 1순위로 심사하게 한다.

Codex 산출물 원본:
`/private/tmp/claude-503/…/scratchpad/modeb.out` (stdout), `modeb.err` (실행 트레이스).

## 운영 메모 (판정 아님)

모드 A(`adversarial-review`)가 이 워크스페이스에서 **2회 연속 desync**했다. 원인은
shared 런타임으로 보인다. 재발하면 `outputSchema` 부착 경로를 쓸 수 없으므로 모드 B +
프롬프트 내 JSON 계약이 사실상 기본이 된다 — 이는 **게이트 적격 경로의 구조적 약화**이며,
`codex-gate` 스킬의 "게이트 적격 경로는 `adversarial-review` 하나뿐" 규정과 긴장한다.
별도 항목으로 올릴 가치가 있다.
