# verdict — 레인 B (계획 심판) · v1.7 · **5회 연속 완주**

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED            # 7회 연속
reviewed_scope_digest: 5f4efdfce9ebb56a5bca922722f6a92a43105321e3fb5fc419b3bee1ade8aac5
primary_doc_sha256: 37b83c0d97565a14c939db7b0496a5ea1c31f15db8803aa44f64c0b736f92517
reviewed_version: v1.7 (2309행)
findings: 10                       # high 7 / medium 3
prior_verdict: .omc/review/20260812-113604/verdict.md
```

동결 4종 지표 시작=종료 일치. 5회 연속.

## 처분 (직전 15항목)

| | |
|---|---|
| **해소 3** | T-58 자기모순 · DEF-3(§5.4 이중 기술) · #6(D0-A 전파) |
| 부분해소 7 | — |
| **회피 2** | #2(`+Security`/`+Broker`) · #7(L0 provenance) |
| **문구만 3** | UNCHK-014 과잉차단 · #4/DEF-4(`UNDECIDED`) · T-22 철회 |

## 수용검사 — 10건 전건 채택, 기각 0

### DEF-6 독립 확증 — v1.7의 핵심 수정이 무력하다

동결 중 Stop 게이트가 낸 DEF-6을 **심판이 독립 발견**했고 근거를 확장했다.

```
:493-502  G2 생성 규칙은 Evidence status 만 읽는다
상위 계획 :136-143, :376-382  G2 조건·Phase 4 종료조건에 register/blocks_gate 소비 없음
```

→ `+Security`→G2, `+Broker`→Phase 4, L0→G2 는 **어느 완료 전이도 실제로 막지 않는다.**
U-8은 "허용 값 하나를 쓰는지"만 검사한다. **"등재는 차단이 아니다"를 끝내려고 만든
기제가 같은 결함을 갖고 태어났다.**

### FWD-a-0 — 심판이 490행 전수 카운트로 양방향 개방을 보였다

```
검증 가능 floor 쌍 0개 = 278행
  현재 FWD-a 대상(PASS/READY 81행)  : STATE-EV-004 1행
  향후 READY 후보(NOT_IMPLEMENTED)   : 277행
```

그리고 **실제 쌍 P 는 아직 없는 `EVIDENCE-REQUIRED-KINDS` 의 자기선언**이며 K-2는
floor 의 **superset 을 허용**한다.

```
무관한 PACKAGE/TEST 를 추가  → FWD-a-0 통과 (우회)
추가하지 않음                → 278행이 순차적으로 차단 (도달 불가)
```

**어느 쪽도 OQ-11의 기계적 해소가 아니다.**

### 새 분류가 배타적이지 않다 — 그리고 폐기한 의미 판정을 부활시켰다

```
WORK       "닫을 수 있으나 아직 안 함"
NORMATIVE  "규범 의무인데 검사 수단이 없음"
→ '검사 수단이 아직 없는 규범 작업'은 **두 정의에 동시에 든다**
```

실제로 `+Security`는 `NORMATIVE`, RUNTIME/FAULT 정규 소스는 `WORK`로 **손기입**했다.
저작자가 `NORMATIVE`를 `WORK`로 고르면 게이트 차단이 사라진다.
U-9/T-63의 자유 산문 판정은 **v1.4에서 폐기한 U-7("구조적 이유")의 부활**이다.

### 직접 실측으로 확증한 2건

**§13.1 스키마에 신규 필드가 없다 — IC-1 클래스 재발**

```
§13.1 정식 스키마 : id / axis / reason / blocked_by / owner_track / exposed_in
§13.6 이 사용     : kind / blocks_gate / justification   ← 스키마에 부재
```

v1.3.1에서 처음 고친 IC-1("계약이 스키마에 없는 것을 참조")이 **"등재는 차단이
아니다"를 고치려고 만든 절에서 재발**했다.

**`CLAUDE.md` 인용 오류 — 저작자가 심사 지시문에까지 전파했다**

```
CLAUDE.md:104  "ClickHouse is not an active runtime …"
CLAUDE.md:106-107  "Backtests must avoid look-ahead bias. Use LookaheadGuard …"
```

v1.7이 `:104,107`로 인용했고, **재심 브리핑에도 같은 오류를 실었다.**
근거를 재실측하지 않고 옮긴 결함(§3.0.1이 기록한 클래스)의 재발.

### 나머지 채택 건

| 요지 |
|---|
| **§7.4가 여전히 "네 처분 중 하나 배정 = 완료"**를 선언 — §11만 고치고 §7.4를 놔둬 `UNDECIDED` 충돌이 이동만 함 |
| **§11에 v1.6판 U-1a 조건(`owner_track=미배정` 0)이 잔존** — 새 WORK-only 조건과 공존해 `LIMIT`인 UNCHK-014 영구 차단이 재현 |
| T-39/T-60이 전칭 주장을 **대표 샘플 1건**으로만 검사. 두 테스트가 사실상 중복 |
| **T-22가 철회 표기 뒤 산문에서 "§13의 실질 방어선"으로 능동 지정** |
| "L1 이상은 PACKAGE/TEST 포함"이라는 **합집합 규칙에서 거짓인 설명이 2곳 잔존** |
| LookaheadGuard·Phase 2~6 rollback은 **현재 계약이 아니라 향후 P-0 수정 약속**뿐 |

## 관통 패턴 — 선언층/평가층 간극, 다섯 번째

| 판 | 선언 | 미연결 |
|---|---|---|
| v1.3.8 | census 4→7 | 소비처 |
| v1.5 | D0-A 병합 | 절차표 |
| v1.6 | `UNDECIDED` 차단·U-1a | §11·대조군 |
| v1.7 | `blocks_gate`·FWD-a-0·U-9 | 게이트 술어·§11·§13.1 스키마 |

**매 판 선언층에 기제를 추가하고 평가층에 연결하지 않는다.** 그리고 새 기제가
과거에 닫은 결함 클래스를 재도입한다 — 이번엔 **IC-1(스키마 부재)과 U-7(의미 판정)
둘 다**.

## 게이트

```
통과 = codex AND approve AND digest 일치
현재 = codex AND needs-attention AND 일치     → 불성립 (7회 연속)
```

## next_steps (Codex 원문)

1. 현재 verdict로 P-0 및 모든 D0 구현 착수를 계속 차단한다.
2. `blocks_gate` 가 실제 target gate 판정을 red/NOT_MET 로 만드는 **소비 경로와
   mutation 증거** 없이는 재심 approve 불가다.
3. FWD-a-0의 **actual `required_kinds` 결속**, 278개 zero-floor 행의 도달 가능성,
   `UNDECIDED`/U-1a **단일 완료 판정**이 확인돼야 한다.
4. T-22 잔존, 거짓 L1 설명, 미정 스키마·허용 집합이 제거된 **동일 digest 결속본**으로
   재심해야 한다.
