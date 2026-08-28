# verdict — 레인 B (계획 심판) · v2.1 · **9회 연속 완주**

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED            # 11회 연속
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: e947ae15f267a1efc849394e17531d4bd856ab50b11549cbfb9070644ce1ad23
primary_doc_sha256: 08d5b048ac8eb4b283ded1dfd6b28d7fc65e7cc658adff340465757432da66ea
reviewed_version: v2.1 (3170행)
findings: 5                        # critical 1 / high 4
non_negotiable_violations: 1       # ← 3회 연속 "위반 0" 기록 중단
prior_verdict: .omc/review/20260812-171720/verdict.md
mode: A (adversarial-review, --scope working-tree), job review-mspyt9lg-wckwto, 8m10s, write=false
```

동결 4종 지표 시작=종료 일치(9회 연속). 심사 중 개정 0.
Codex 가 스파이크 2종을 직접 실행하고 **"exit 0 은 controls 가 돌았다는 뜻이지 후보
출력이 깨끗하다는 뜻이 아니다"** 라고 명시 — 3회 연속 같은 판정.

## 처분

**v2.0 직전 4건**: 해소 0 / **부분해소 3**(critical·F-B·F-C) / **문구만 1**(F-D).
T-22·T-52 dangling 참조는 저작자 자체 스윕이 찾아 교정(심판 확인).

findings 추이: v1.8 **11** → v1.9 **6** → v2.0 **4** → v2.1 **5**.

## 수용검사 — 5건 전건 채택, 기각 0

인용 전건 실측(별도 조사). **팬텀 0.** 기각 사유 3종 어느 것에도 해당 없음.

### ⚠ 비협상 규칙 위반 1건 (저작자 유발)

```
CLAUDE.md:20-22  "thresholds ... belong in YAML/env/config files,
                  not hardcoded branches"
D:3107           `0 ≤ n < m ≤ 7 **AND m − n ≤ 3**`      ← 리터럴 임계값
```

**F-B 를 고치려고 넣은 폭 상한이 비협상 조항을 위반한다.** 3회 연속 유지되던
"위반 0" 이 저작자가 도입한 리터럴에서 끊겼다.

### ⚠ CRITICAL — `OQ-11` 이 차단인데 **그것을 산출하는 단계가 없다**

```
§5.2.4 :1551-1557   OQ-11 미해소면 STATE-EV-004 가 FWD-a 불충족
§9     :2372        OQ-11 = 차단
§11    :2437        "OQ-11 판정 취득" = 종료조건
§12.3  :2563-2575   ← **취득·기록·검증 단계 없음** (실측 확인)
```

세 절은 서로 일관되게 고쳐졌으나 **절차표가 그 산출물을 만들지 못한다.**
계획 DAG 가 자기 필수 종료 아티팩트를 생산할 수 없다 — **IC-5 영구 차단 클래스의
재현이며, v2.1 이 만든 것이다.** `UNCHK-004`·`UNCHK-005`(강등) 도 배정 행위가
절차에 없는 채로 차단 중이다.

> **선언층/평가층 간극의 새 형태**: 지금까지는 "선언하고 소비처를 안 붙였다"였는데,
> 이번엔 **필수 산출물을 선언하고 생산 단계를 안 붙였다.**

### 나머지 채택 4건

| 요지 | 실측 |
|---|---|
| **폭 상한이 데이터에 맞춘 미검증 리터럴** — T-62 음성 대조군 4종에 **폭 초과(`Phase 0-7`)가 없다**. T-72 는 유효 범위형의 비차단·계수만 본다 ⇒ **상한을 강제하는 대조군이 없다** | 확인. §13.6.4 예시 목록엔 `Phase 0-7` 을 넣고 **T-62 에는 넣지 않았다** |
| **INV-C3 를 강제한다고 주장하면서 11술어 중 10을 미검증** — §4.3(:719-725)이 "각 항목은 §8 대조군을 갖는다"고 **전칭 주장**하고 §11(:2411)이 T-2 통과를 완료 증거로 쓴다. UNCHK-022 는 기록만 할 뿐 아무것도 소비하지 않는다 | 확인. 전칭 주장 원문 실재 |
| **T-76·S-19·S-9 확장이 소비처 없음** — §11 은 T-75·T-72 를 결속했으나 **`T-76` 은 §11 에 0건**. T-76 이 약속한 "레벨 분포 앵커"도 §5.2.8 에 그 형태로 존재하지 않는다(:972-973 은 고유값 26, :1035-1050 은 **floor 집합** 분포로 다른 것) | 확인. `T-76` 은 §8·§5.2.4·변경이력 3곳뿐 |
| **U-9 는 문구만 바뀌었다** — 인용의 적절성 미검사를 저작자가 자인. `closable=NO` 전환 + 무관한 실재 절 인용으로 소유자·게이트 의무를 여전히 제거할 수 있다 | 확인 |

## 관통 패턴 — **교정이 결함을 생성하는 국면**

| 판 | 닫은 것 | 새로 만든 것 |
|---|---|---|
| v1.9 | critical(T-61) 등 6 | 문법→대조군 미갱신 · 지표 3중 1결속 · 병합 미전파 |
| v2.0 | F3·F4 | **`전사` 용어로 완료 금지** · **F5→OQ-11 영구 차단** |
| **v2.1** | dangling 참조 3건 | **하드코딩 임계값(비협상 위반)** · **OQ-11 종료조건에 생산 단계 부재** |

**두 판 연속 교정이 새 결함을 생성했고, 이번엔 비협상 위반까지 나왔다.**

## 게이트

```
통과 = codex AND approve AND digest 일치
현재 = codex AND needs-attention AND 일치     → 불성립 (11회 연속)
```

**P-0 및 모든 D0 구현 착수 차단 유지.**

## next_steps (Codex 원문)

1. Keep P-0 and all D0 implementation blocked; v2.1 does not pass Lane B.
2. **Any re-review must show executable evidence for these defects; additional prose,
   labels, or unconsumed UNCHK/OQ entries are insufficient.**

## 오케스트레이터 관측 (판정 아님)

next_steps 2 는 **산문 개정으로는 통과하지 못한다**는 진술이다. 이번 회차까지의 실측이
그것을 뒷받침한다 — 종이에서 잡힌 결함은 심판이 잡았고, 저작자 도구가 잡은 것(S-16
자기오염·분류 재기입 우회·dangling 2건·지표 오산 3회)은 **전부 실행에서 나왔다.**

계약이 검증 불가능한 근본 이유는 변하지 않았다: **이 문서는 아직 존재하지 않는
기계(검사기·게이트 평가기·레지스터)의 완료 계약을 쓰고 있다.** 계약의 참·거짓은
그 기계를 돌려야 결정되는데 기계는 게이트에 막혀 있고, 게이트는 계약이 검증되지
않아 열리지 않는다.
