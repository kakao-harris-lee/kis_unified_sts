# verdict — 레인 B (계획 심판) · 시도 3 (v1.2 재심)

## 심판 메타

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED          # 2회 연속 — 구현 착수 계속 차단
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: cb6ddb8af4e6f86ff8be219780216712829526196e82d1e2824ed19ba925ff87
reviewed_version: v1.2
findings: 8                      # high 4 / medium 4
prior_verdict: .omc/review/20260812-065727/verdict.md
```

실행: 모드 B (`task --background --fresh --effort high`, `write: false` 실측 확인),
job `task-msp7m8lj-eyedyy`, 450s, desync 0. digest 심사 전후 동일 — mid-review 개정 없음.

## 직전 10건 처리 판정

| # | 판정 | 근거 |
|---|---|---|
| F-1 | **해소** | §3.0.1의 SAFE-053 재실측이 RFC-002 실제 내용과 일치 |
| F-2 | **회피** | 문구는 철회했으나 OQ-8을 비차단으로 두고 상위 30/30을 29/30으로 낮춤. checker는 여전히 G6-only를 선언 |
| F-3 | **해소** | D0-1이 실제 정의된 열만 참조 |
| F-4 | 부분해소 | K-2 매핑 함수·K-3 정규 소스 부재로 실행 불가 |
| F-5 | 부분해소 | `approved` predicate 여전히 없음, OQ-9가 종료를 차단하지 않음 |
| F-6 | 부분해소 | 무제한 `UNDECIDED`로 완료 가능 |
| F-7 | 부분해소 | T-7/T-13이 정의 부재로 실행 불가, T-3c 범위가 §3.3과 모순 |
| F-8 | 부분해소 | D0-3 독립 표기가 실제 D0-4 의존과 불일치, P-0 범위가 §8 누락 |
| F-9 | 부분해소 | CI가 Phase 1로 이연, rollback 범위가 실제 수정 파일 미포괄 |
| F-10 | **해소** | 헤더와 §12.3 정합 |

**해소 3 / 회피 1 / 부분해소 6.** 신규 high 1건(G1~G3 술어 누락) 추가.

## 수용검사 — 8건 전건 채택, 기각 0

기각 사유 3가지 중 어느 것에도 해당 없음. Codex가 기준 6(CLAUDE.md 비협상)을
**해당 없음**으로 명시 판정했고, `CLAUDE.md:36`(실선물 주문 영구 차단)을 계획 §10이
보존함을 확인했다.

### 직접 실측으로 확증한 3건

**① T-3c의 대상 집합이 비어 있다 (가장 치명적)**

```bash
sed -n '719,812p' tools/tos_spec_status.py | grep -c "29/30"
# 0
```

v1.2 §8.1은 T-3c 범위를 "`_COUNT_TRANSCRIPTIONS`가 관리하는 앵커 집합"으로 좁혔다.
**그 11개 앵커에는 `29/30` 전사가 하나도 없다.** 즉 T-3c는 공집합을 검사한다 —
언제나 green이고 아무것도 검출하지 않는다.

이것은 §3.3이 약속한 "숫자만 있는 전사는 실패로 처리"의 **완전한 무력화**다.
v1.2는 실행 불가능한 전역 규칙을 실행 가능한 공집합 규칙으로 바꿨을 뿐이다.
**범위 축소가 곧 회피인 전형.**

**② K-2가 파생 규칙이 아니라 이름뿐이다**

```bash
cut -d, -f5 EVIDENCE-REGISTER-002.csv | grep -c Critical   # 338 (+ 34 = 인용부호 내 콤마 파싱 잡음)
cut -d, -f5 EVIDENCE-REGISTER-DEV.csv  | grep -c Critical   # 118 / 118
```

`criticality`는 사실상 전 행이 `Critical`이다 — **판별력 0**. 따라서
"criticality와 minimum_evidence_level에서 필수 kind 집합을 파생한다"는 규칙은
결정적이지 않다. K-3의 "선언된 서비스 목록"·"fault 시나리오 레지스터"도 파일·스키마·
소유자가 지정되지 않았고 저장소에 해당 정규 레지스터가 확인되지 않았다.

> 위 census 자체가 naive CSV cut이라 인용부호 내 콤마로 오염됐다("register CSV naive
> grep 금지" 교훈). 오염분은 다른 값이 아니라 파싱 잡음이므로 **"criticality 비판별"**
> 이라는 결론은 유지되지만, 구현 시 census는 CSV 파서로 다시 해야 한다.

**③ §7.5가 F-1과 같은 클래스의 오류를 새 위치에 남겼다**

```bash
grep "^BTE-EV-00[1-7]," EVIDENCE-REGISTER-DEV.csv | cut -d, -f10
# 전 7행: ai-review(decorrelated)+operator-countersign  — 배정 완료
```

v1.2 §7.5는 DEV 20개 named-TBD를 근거로 backtest docstring의 "DEV 스코프에서는 P0-3
incomplete가 참"이라고 일반화했다. **BTE-EV-001..007의 reviewer는 전부 배정돼 있다.**
§9 OQ-2가 여전히 "미판정"이라고 적어 §7.5의 부분완료 주장과도 모순된다.

**§3.0.1에서 "이 클래스가 세 번 발생했다"고 자기비판한 문서가, 같은 커밋에서 네 번째를
저질렀다.** 자기비판의 존재가 재발을 막지 못한다는 실증.

### 신규 high — D0-1 술어가 상위 완료 정의를 누락

v1.2 §4.2는 G1 3술어 / G2 2술어 / G3 2술어만 둔다. 상위 계획 `:128-149`가 요구하는
durable state owner 결속, 세 transport의 동일 검증 경계, root 없는 독립 실행,
독립 Evidence review, synthetic/VirtualBroker E2E·restart·partition·clock·partial-fill·
unknown-finality·replay, migration/rollback protocol 동결이 **누락**됐고
`NOT_MACHINE_CHECKABLE`로도 표시되지 않았다. → 생성기가 상위 정의 미충족 상태를
`MET`으로 만들 수 있다. **INV-C3(fail-closed)의 취지를 술어 집합 자체가 배신한다.**

## 심판 자기신고 한계 (수용 시 감안)

Codex가 밝힘: **집중 pytest를 실행하지 못했다** (read-only 실행환경에 임시 디렉터리
없음). 따라서 T-1~T-20 관련 판정은 **전부 정적 대조 근거**이며 테스트 실행 기반
주장은 이번 심사에 없다. 위 ①~③은 오케스트레이터가 직접 실행해 확증했다.

## 게이트 판정

```
레인 B 통과 = adjudicator: codex AND verdict: approve AND digest 일치
현재        = codex           AND needs-attention  AND 일치
                                  ^^^^^^^^^^^^^^^ 2회 연속 불성립
```

**P-0 및 D0 구현 착수 계속 차단.**

## 구조적 관찰 — 두 사이클의 패턴

v1.1→v1.2에서 **해소 3건은 전부 "사실을 고치는" 유형**이었고(F-1 오인용, F-3 열 불일치,
F-10 버전 표기), **회피/부분해소 7건은 전부 "계약을 정의해야 하는" 유형**이었다.

이는 우연이 아니다. 저작자는 지적받은 곳에 **문장을 추가**해 대응했고, 그 문장이
사실 교정일 때는 해소됐지만 **정의를 요구하는 곳에서는 이름만 붙고 규칙은 비었다**
(K-2, `approved`, `UNDECIDED` 상한, T-3c 범위). §3.3의 전역 약속이 §8.1의 공집합으로
축소된 것이 그 극단이다.

**다음 개정은 문장 추가가 아니라 결정을 요구한다.** 결정 없이 한 사이클 더 돌리면
같은 패턴이 반복될 가능성이 높다 — 이 판단은 오케스트레이터의 것이며 심판 소관이 아니다.

## next_steps (Codex 원문)

1. 현재 verdict가 needs-attention이므로 P-0 및 D0 구현 착수를 계속 차단한다.
2. F-2, F-4, F-5, F-6, F-7, F-8, F-9의 잔여 계약 결함과 신규 G1~G3 술어 누락을
   직접 근거로 다시 심사한다.
3. 재심에서는 상위 Phase 0 네 종료 조건의 약화 여부와 OQ-8/OQ-9/UNDECIDED의
   차단 효과를 fail-closed로 판정한다.
