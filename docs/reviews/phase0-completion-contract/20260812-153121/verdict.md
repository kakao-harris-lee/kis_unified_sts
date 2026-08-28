# verdict — 레인 B (계획 심판) · v1.9 · **7회 연속 완주**

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED            # 9회 연속
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: d95dba461ce9dc66b556fe5f4a61eedb6d37abb6a02806f3603aa4f6abcfafba
primary_doc_sha256: cae1e8a4ed6c4288606393c8d87164cc96a0525904adcc09a431a6968ddba29f
reviewed_version: v1.9 (2921행)
findings: 6                        # critical 0 / high 6 / medium 0
prior_verdict: .omc/review/20260812-134502/verdict.md
mode: A (adversarial-review, --scope working-tree), job review-msprmck1-qgwtzj, 12m48s, write=false
```

동결 4종 지표 시작=종료 일치(7회 연속). 심사 중 개정 0.

**실행 이력 주의**: 최초 디스패치는 foreground 타임아웃의 SIGTERM 전파로 21초 만에 죽었으나
status 가 51분간 `running` 으로 stale 했다. PID 소멸 + `updatedAt` 정지로 판별해 cancel 후
`nohup`/`disown` 으로 재디스패치했다. 위 판정은 **재디스패치된 완주 job** 의 것이다.

## 처분

**v1.8 직전 11건**: 해소 6 / 부분해소 5 / **미해소 0 · 문구만 0 · 회피 0**
→ **critical(T-61 이 자기 계약을 검증하지 않음) 해소됨.**

**v1.9 자체 처분 12건**: 해소 5 (①T-61 재작성 ②고아 target ⑧구 U-1a 정의부
⑨폐기 어휘 ⑩거짓 L1) / 부분해소 7.

## 수용검사 — 6건 전건 채택, 기각 0

인용 전량 실측: 계획 문서 11개 위치·`CLAUDE.md` 8조항 **팬텀 0건.**
비협상 8조항 `file:line` 개별 대조 → **위반 0 (2회 연속).**

기각 사유 3종(팬텀 / 의도적 silenced / 비협상 배치) 어느 것에도 해당 없음.

### F1 (high) — T-69 는 자기가 시험한다는 뮤테이션을 검출하지 못한다

**오케스트레이터 독립 재계산으로 확증:**

```
      규칙준수   부분→MET 뮤테이션   뒤집힘
G1    False     False              없음
G2    False     False              없음
G3    False     False              없음
```

`부분`만 `MET` 으로 바꿔도 **다른 술어(NMC·false CHECKABLE)가 가려서** 게이트가
뒤집히지 않는다. T-69 는 게이트 뒤집힘을 관측하므로 **결합 규칙을 틀리게 구현해도 green.**

> **이 문서 자신이 §4.2.2 에서 유도한 원리의 위반이다** — "verdict 가 상수이므로
> 사유 집합이 유일한 관측 표면"이라고 U-8a 근거로 써 놓고, **같은 절의 대조군 T-69 를
> verdict 관측으로 작성했다.** 원리를 도출한 판에서 그 원리를 위반했다.

### F2 (high) — T-62 의 "문법 밖" 대조군이 v1.9 문법에서 **유효 입력**이 됐다

```
:1952  T-62 … `owner_track`을 문법 밖 문자열(`Phase 2-5` 등 구 표기)로 → …
:2886  범위  `Phase <n>-<m>`  (0 ≤ n < m ≤ 7)   ← [v1.9 추가]
        2 < 5, 둘 다 0..7  ⇒ `Phase 2-5` 는 이제 **유효**
```

**문법을 데이터에 맞춰 넓히고 음성 테스트를 갱신하지 않았다.** §13.2.1 ③ 이
"거짓 정밀도"를 피하려고 범위형을 넣었는데, 그 확장이 **기존 부정확 데이터를 통과시키는
방향**이었고 대조군만 옛 값을 가리킨 채 남았다.

### F3 (high) — U-10 은 지표 3개를 요구하는데 대조군·종료조건은 1개뿐

```
:2536-2538  U-10 = superset_declared_pairs · imprecise_owner_track · blank_normative_ref_rows
:1955       T-67  → required_kinds 뮤테이션, superset_declared_pairs 만 관측
:2229       §11   → superset_declared_pairs 만 종료조건
```

나머지 둘은 **누락·하드코딩·stale 이어도 red 전이가 없다.**

### F4 (high) — T-39/T-60 병합이 활성 계약·종료조건에 미전파

```
:1963       T-60 철회
:2242       종료조건 대체 문구가 여전히 `(K-10·T-60)` 인용  ← dangling
:2589-2591  U-2b 가 여전히 "임의의 계약 하나" 표본 정의 — T-39 전수화와 충돌
```

또한 종료조건이 "**선언된** 모든 계약이 호출됨"을 주장하는데 T-39 의 우주는
**등록된** 키뿐이다(UNCHK-019 가 인정한 갭) — **종료조건이 과대주장.**

### F5 (high) — DEF-7 은 여전히 우회 가능

무관한 기존 `PACKAGE`/`TEST` 표면을 얹으면 FWD-a-0 불충족이 통과로 바뀌고,
지표 값과 무관하게 Phase 0 조건은 전부 성립한다. T-67 은 **관측 가능성**을 증명하지
**저항력**을 증명하지 않는다.

### F6 (high) — `closable=NO` 가 여전히 무료 면제

T-63 은 `reason` 이 비었는지만 본다. 저작자가 `YES`→`NO` 로 바꾸고 소유자를 비우고
아무 산문이나 적으면, `normative_ref` 공란과 결합해 **어느 게이트에도 기여하지 않는다.**
v1.9 는 `normative_ref` 재량을 UNCHK-020 으로 등재하면서 **같은 쌍의 `closable` 재량은
등재하지 않았다** — 직교 2필드를 비대칭 처리했다.

## 관통 패턴 — 선언층/평가층 간극, **여덟 번째이자 3건 동시**

| 판 | 형태 |
|---|---|
| v1.3.8 ~ v1.7 | 선언 추가 → 소비처 미연결 (5회) |
| v1.8 | 양방향 동시 (정의부만 폐기 / 소비처만 철회) |
| **v1.9** | **F2 문법 확장 → 대조군 미갱신 · F3 지표 3개 선언 → 1개만 결속 · F4 테스트 병합 → 계약·종료조건 미전파** |

**세 건 전부 v1.9 가 새로 도입한 것에서 일어났다.** S-9(단일 소스)·S-10(의도 표시는
수행 아님)·S-16(계약↔대조군 필드 대조)을 이 판에서 강화했는데도 같은 클래스가 재발했다.

**F1 은 한 단계 더 나쁘다** — 규칙 위반이 아니라 **자기가 방금 유도한 원리의 위반**이다.

## 게이트

```
통과 = codex AND approve AND digest 일치
현재 = codex AND needs-attention AND 일치     → 불성립 (9회 연속)
```

**P-0 및 모든 D0 구현 착수 차단 유지.**

## next_steps (Codex 원문)

1. Keep P-0 and all D0 implementation blocked under the current needs-attention verdict.
2. Obtain red-producing evidence for the six cited paths, especially isolated PARTIAL
   folding, valid/invalid owner ranges, all U-10 metrics, and closable YES-to-NO transitions.
3. Re-review a frozen, identical digest after active T-60 consumers and the
   registered-versus-declared contract scope are reconciled.
