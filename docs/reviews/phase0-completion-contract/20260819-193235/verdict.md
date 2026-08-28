# verdict — 레인 B (계획 심판) · v2.20 재심

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: c00d808ec262d088820dc977b466d9b44e9796a2
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: f64d9fb23d5ee08f0527e72992bda4b719a13fa1c83e68530e91a8a05f4524c6
reviewed_version: v2.20 (계약 7,494행 에라타 재동결 ae842cce · 개발계획 579행 (D) 개정 적용 3d17ea66) — 동결 3d17ea66 · 증거 d101eb63 · 에라타 ae842cce · addendum 29baafcc · 재결속 c00d808e
findings: 2                        # high 1 / medium 1 — 직전 #1 회피 · #2 해소됨 · #3 해소됨 · #4 해소됨 · #5/#6 부분해소 · 신규 클래스 0
prior_verdict: .omc/review/20260819-135916/verdict.md   # v2.19 재심
mode: A (adversarial-review, --scope working-tree, --wait), write=false
lane: B (계획) — plan_scope_digest 로 계획 문서 2건에만 결속
job: review-mszyg7j6-owwgt5 / codex thread 01a01996-9eab-7c40-9a33-442bb009e401 (turn 01a01996-a008-73f0-b73d-0bae30a24602)
     # 1회 디스패치 정상 완료(9m 59s) — 재시도 불요 · parseError null · companion 1.0.6
```

리비전 결속: 디스패치 직전 = 심사 종료 후 재계산 **불변**(HEAD·plan_scope_digest·
내용-only digest `9cf4ec74…` == 아티팩트 보유값 `OQ-11-DISPOSITION.md:10`). Codex 도
결속 HEAD·두 digest·커밋 순서를 독립 확인. 재결속은 **두 문서 모두 개정된** 내용
(계약 에라타 `ae842cce`·개발계획 (D) 적용 `3d17ea66`)에 대해 1회(`c00d808e`).

## 처분

**직전 5건: #1 회피 · #2 해소됨 · #3 해소됨 · #4 해소됨 · #5/#6 부분해소** — **아크
누적 해소 11**(a2 g6·격리 스냅샷·⑯ = 9·10·11번째). `CLAUDE.md` 비협상 직접 충돌
**없음**(13판 연속). 신규 결함 클래스 0·S-20 종수 불일치 0. **회피 1**(#1): 구조
파서+서버 스텝 대조는 «토큰 존재»와 «이름·conclusion»만 인증 — 계약 자신이 :5470-5476
에서 `|| true`·`set +e` 런타임 무효화가 blob·서버 대조를 통과한다고 적고 증거가 그것을
ACTIVE 기대값으로 고정했으며, `false && bash tools/tos_entry_harness.sh || true` 처럼
하니스를 «실행하지 않는» 명령열도 경로가 실행 위치에 있어 통과 → 승인된 하니스를
실행하거나 digest 불일치를 실패로 전파하지 않아도 PREVENTION_ACTIVE. 부분 표면 검사를
해소로 제시한 형태라 «회피». #5/#6 부분: 개발계획 :270-308 과 계약 (D) 는 맞춰졌으나
활성 UNCHK-008(:6191)의 `owner_track` 이 여전히 `Phase 1`(계약 :6274-6275 «owner_track
= 축을 닫을 트랙»)·U-17 하니스 경로가 «D0-A 산출물»(:5462)로 표기 → Phase 0 가
PREVENTION_ACTIVE 를 소비하기 전에 그 축·하니스를 누가 산출·폐쇄하는지 단일 비순환
순서 부재 — (D) verbatim 적용이 두 단계 문구만 맞추고 활성 형제 소비처에 미전파(S-22).

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

NO-SHIP. 결속 HEAD·두 digest·커밋 순서는 확인됐지만 의미 결함이 남았다. 직전 5건 처분: #1 회피 — 비활성 문자열은 잡지만 실행·실패 전파를 인증하지 않는 부분 표면 검사다(계약:5452-5476, 증거:3190-3191). #2 해소됨 — U-16-g 전 항과 g6 대조가 결속됐다(:6812-6829, :2935). #3 해소됨 — 격리 clone, 진입 HEAD detach, 내부 canary로 기존 graft TOCTOU가 닫혔다(:7099-7131; U16 증거:81-129; U17 증거:67-89). #4 해소됨 — ⑯·⑱ 모두 edge_seq 미기재 현행 스키마를 소비한다(:6838-6897, :2935). #5/#6 부분해소 — 개발계획 :270-308과 계약 (D) :4437-4488은 맞춰졌지만 활성 UNCHK 표면이 Phase 1을 유지한다. 기준별 판정: (1) 단계 순서·의존성 BLOCK(#5), (2) 숨은 가정 BLOCK(#1), (3) 검증 가능성 BLOCK(#1), (4) 실패 처리 BLOCK(#1), 별도 rollback 결함은 해당 없음, (5) 범위 이탈·과잉 설계 해당 없음, (6) CLAUDE.md 비협상 충돌 해당 없음, (7) 누락 BLOCK(#1·#5). S-20 종수 불일치는 새로 발견되지 않았고 S-22 전파 누락은 #5에 남았다.

Findings:
- [high] [#1 회피] 실패하지 않는 검증 스텝도 PREVENTION_ACTIVE가 된다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5457-5476)
  구조 파서는 하니스 경로와 SHA 대조 명령의 토큰 존재만 확인한다. 이 절은 `shasum … | grep <sha> || true`와 `set +e`가 blob·서버 대조를 모두 통과한다고 명시하며, 실행 증거도 이를 PREVENTION_ACTIVE 기대값으로 고정한다. 같은 이유로 `false && bash tools/tos_entry_harness.sh || true`처럼 하니스를 실행하지 않는 명령열도 단순 명령 목록에서 경로를 발견한다. 서버 확인은 작성자 지정 이름과 conclusion만 보므로 인과관계를 복구하지 못한다. 결과적으로 승인된 하니스를 실행하거나 digest 불일치를 실패로 전파하지 않아도 D0-A 예방 조건이 green이 된다.
  Recommendation: 도달 불가능한 하니스 호출과 `|| true`·`set +e`로 중화된 digest 불일치가 권위 U-17 소비자에서 비-0 및 non-ACTIVE가 되기 전까지 #1 해소와 출하를 인정하지 않는다.
- [medium] [#5/#6 부분해소] 같은 예방 통제의 활성 소유 시점이 여전히 Phase 1이다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:6191)
  개발계획은 tos-gate와 branch protection을 D0-A 전제로 옮겼지만, 활성 UNCHK-008은 동일한 외부 required-check·branch-protection 예방 축의 `owner_track`을 여전히 Phase 1로 둔다. 계약 자체가 owner_track을 축을 닫는 트랙이라고 정의한다(:6274-6275). 또한 U-17의 필수 하니스 경로를 `D0-A 산출물`이라고 표기한다(:5461-5462). 따라서 Phase 0가 PREVENTION_ACTIVE를 소비하기 전에 그 축과 하니스를 누가 산출·폐쇄하는지 단일한 비순환 순서가 없다. (D)의 verbatim 적용은 두 눈에 띄는 단계 문구만 맞췄고 활성 형제 소비처에는 전파되지 않았다.
  Recommendation: UNCHK-008, U-17 하니스 소유, 개발계획 선행조건이 동일한 pre-D0-A 생산 주체와 시점을 가리키고 D0-A·Phase 1 산출물 없이 PREVENTION_ACTIVE에 도달함이 증명되기 전까지 #5를 미해소 상태로 유지한다.

Next steps:
- 두 차단 사유가 현재 결속 문서와 권위 소비자에서 반증될 때까지 구현 착수 및 출하를 보류한다.
```

### 구조화 JSON 원문 (`result review-mszyg7j6-owwgt5 --json` · `confidence` 포함 · verbatim)

```json
{
  "verdict": "needs-attention",
  "summary": "NO-SHIP. 결속 HEAD·두 digest·커밋 순서는 확인됐지만 의미 결함이 남았다. 직전 5건 처분: #1 회피 — 비활성 문자열은 잡지만 실행·실패 전파를 인증하지 않는 부분 표면 검사다(계약:5452-5476, 증거:3190-3191). #2 해소됨 — U-16-g 전 항과 g6 대조가 결속됐다(:6812-6829, :2935). #3 해소됨 — 격리 clone, 진입 HEAD detach, 내부 canary로 기존 graft TOCTOU가 닫혔다(:7099-7131; U16 증거:81-129; U17 증거:67-89). #4 해소됨 — ⑯·⑱ 모두 edge_seq 미기재 현행 스키마를 소비한다(:6838-6897, :2935). #5/#6 부분해소 — 개발계획 :270-308과 계약 (D) :4437-4488은 맞춰졌지만 활성 UNCHK 표면이 Phase 1을 유지한다. 기준별 판정: (1) 단계 순서·의존성 BLOCK(#5), (2) 숨은 가정 BLOCK(#1), (3) 검증 가능성 BLOCK(#1), (4) 실패 처리 BLOCK(#1), 별도 rollback 결함은 해당 없음, (5) 범위 이탈·과잉 설계 해당 없음, (6) CLAUDE.md 비협상 충돌 해당 없음, (7) 누락 BLOCK(#1·#5). S-20 종수 불일치는 새로 발견되지 않았고 S-22 전파 누락은 #5에 남았다.",
  "findings": [
    {"severity": "high", "title": "[#1 회피] 실패하지 않는 검증 스텝도 PREVENTION_ACTIVE가 된다", "body": "구조 파서는 하니스 경로와 SHA 대조 명령의 토큰 존재만 확인한다. 이 절은 `shasum … | grep <sha> || true`와 `set +e`가 blob·서버 대조를 모두 통과한다고 명시하며, 실행 증거도 이를 PREVENTION_ACTIVE 기대값으로 고정한다. 같은 이유로 `false && bash tools/tos_entry_harness.sh || true`처럼 하니스를 실행하지 않는 명령열도 단순 명령 목록에서 경로를 발견한다. 서버 확인은 작성자 지정 이름과 conclusion만 보므로 인과관계를 복구하지 못한다. 결과적으로 승인된 하니스를 실행하거나 digest 불일치를 실패로 전파하지 않아도 D0-A 예방 조건이 green이 된다.", "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md", "line_start": 5457, "line_end": 5476, "confidence": 0.99, "recommendation": "도달 불가능한 하니스 호출과 `|| true`·`set +e`로 중화된 digest 불일치가 권위 U-17 소비자에서 비-0 및 non-ACTIVE가 되기 전까지 #1 해소와 출하를 인정하지 않는다."},
    {"severity": "medium", "title": "[#5/#6 부분해소] 같은 예방 통제의 활성 소유 시점이 여전히 Phase 1이다", "body": "개발계획은 tos-gate와 branch protection을 D0-A 전제로 옮겼지만, 활성 UNCHK-008은 동일한 외부 required-check·branch-protection 예방 축의 `owner_track`을 여전히 Phase 1로 둔다. 계약 자체가 owner_track을 축을 닫는 트랙이라고 정의한다(:6274-6275). 또한 U-17의 필수 하니스 경로를 `D0-A 산출물`이라고 표기한다(:5461-5462). 따라서 Phase 0가 PREVENTION_ACTIVE를 소비하기 전에 그 축과 하니스를 누가 산출·폐쇄하는지 단일한 비순환 순서가 없다. (D)의 verbatim 적용은 두 눈에 띄는 단계 문구만 맞췄고 활성 형제 소비처에는 전파되지 않았다.", "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md", "line_start": 6191, "line_end": 6191, "confidence": 0.97, "recommendation": "UNCHK-008, U-17 하니스 소유, 개발계획 선행조건이 동일한 pre-D0-A 생산 주체와 시점을 가리키고 D0-A·Phase 1 산출물 없이 PREVENTION_ACTIVE에 도달함이 증명되기 전까지 #5를 미해소 상태로 유지한다."}
  ],
  "next_steps": [
    "두 차단 사유가 현재 결속 문서와 권위 소비자에서 반증될 때까지 구현 착수 및 출하를 보류한다.",
    ""
  ]
}
```

> 포워더 전달: parseError null·codex.status 0·stderr ""·target working-tree explicit·write false·재시도 0. `next_steps[1]` 빈 문자열은 산출 잔여물(내용 손실 없음). Codex 가 두 문서·직전 verdict·증거 2건·CLAUDE.md 를 직접 통독.

---

# 수용검사 (오케스트레이터) — **채택 2 / 기각 0**

기각 사유 3가지(팬텀 file:line / 의도적 silenced / 비협상 배치) 중 해당 없음. 전건 실측.

| # | sev | 실측 | 처분 |
|---|---|---|---|
| 1 | high (#1 회피) | `:5457-5476` (b)③ (1) 구조 파싱 문단 실재 — (i) 실행 위치 술어·(ii) 대조 «능동» 요구·불충족 4종·**정직 경계 문단 :5470-5476 «`shasum … \| grep 957… \|\| true`·`set +e` 로 exit-code 무효화 … 스텝이 `success` 라 blob 파싱을 통과 … 서버 스텝 대조도 이름·conclusion 만»** 리터럴 확인. `false && bash tools/tos_entry_harness.sh \|\| true` 는 토큰열에 경로가 «실행 위치»(인터프리터 첫 비-옵션 인자)로 실재하므로 (i) 통과 — 도달 불가 호출을 구별하는 술어 없음 확인. 증거 `U17-PREVENTION-CHECK-V220.md` ⑬c 가 ACTIVE/0 을 «계약대로» 기대값으로 고정. 심판 계수 «회피»(부분 표면 검사의 green 을 해소로 제시)는 정당 — 계약 자신이 미검출을 자인했더라도 «실행·실패 전파 미인증»이 #1(비활성 문자열 인증)의 본질과 같은 클래스 | 채택 |
| 2 | medium (#5/#6 부분) | `:6191` UNCHK-008 행의 `owner_track` 셀 = `Phase 1` 리터럴 확인 · `:6274-6275` «`owner_track` = 축을 닫을 트랙» 정의 확인 · `:5462` «(경로 리터럴은 계약이 정한다·D0-A 산출물)» 확인. 개발계획 (D) 적용은 Phase 0 «선행 조건» 으로 옮겼으나 계약 §13 레지스터 UNCHK-008 owner_track·U-17 하니스 경로의 «D0-A 산출물» 표기가 미전파(S-22 — 형제 소비처) → «D0-A 착수 전에 PREVENTION_ACTIVE» 인데 그 전제(하니스 파일·required check 축)를 D0-A/Phase 1 이 산출하는 순환 | 채택 |

비협상 대조: 선물 대칭·실계좌 증거금·EOD 청산·ClickHouse·RL/TFT·하드코딩·Redis DB/TTL·비KST — 2건 어느 것도 배치 권고 아님.

## 관측 (finding 아님)

- **해소 3(a2 g6·격리 스냅샷·⑯) = 아크 누적 11** — 격리 스냅샷 기층(#3)을 심판이 «구조로 닫혔다»로 인정(판정 요약 — 계약은 «잔여 종류 이동»으로 정직 표기 유지).
- **#1 저작 경로**: (b)③ 에 «실행 도달성·실패 전파» 구조 요건 추가 — `run:` 은 `set -euo pipefail`(또는 `shell: bash -euo pipefail {0}` / `defaults.run.shell`)로 시작·하니스 호출은 **조건 연산자(`&&`/`||`/`if`/`case`) 의 피연산자가 아닌 최상위 단순 명령**·대조 명령은 파이프라인의 마지막이며 뒤에 `|| true`/`|| :`/`; true`/`set +e`/`exit 0` 류 «무효화 토큰» 부재·`continue-on-error`/`if: always()` 부재 — 구문 단위로 결정적 검사(여전히 «런타임 실행을 증명하지 않는다»는 정직 경계 유지하되 ⑬c 를 «검출»로 전환) + 서버 잡의 `steps[].conclusion` 외에 **실패 전파 증거**로 대조 스텝의 `number`·`started_at/completed_at` 만 추가 가능(의미론은 여전히 불가 — 정직). T-84 ⑬c→검출·⑬d(도달 불가 호출 `false && bash …`)·⑬e(`continue-on-error`).
- **#2 저작 경로**: UNCHK-008 `owner_track` → `Phase 0`(D0-A 선행조건 — 운영자/인프라 행위·D0-A 산출물 아님)·`blocked_by` 정합, U-17 «하니스 경로 = D0-A 산출물» → «pre-D0-A 산출(§12.3.4-R 블록의 파일 실체화 — D0-A 착수 «전» 운영자/선행 단계가 둔다; 내용은 계약 §12.3.4-R 결속값)», 개발계획 Phase 0 선행 조건에 «하니스 파일 `tools/tos_entry_harness.sh` 실체화(sha 957bf49d…)»를 같은 선행조건으로 명시(두 문서 같은 주체·시점). S-22: 형제 소비처(UNCHK-008 행·U-15/U-17 «D0-A 산출물» 표기·개발계획 §3 G1/§6) 전수.

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND plan_scope_digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립
```

**레인 B NOT_PASSED 유지. P-0/D0 착수 불가.**
