# 동결 중 이연된 지적 — v1.5 재심 판정 후 처분

```yaml
frozen_version: v1.5
plan_scope_digest: a5212589ad14f0b04cfe86085355bec8a4091720dc7275732b84643edb4c8e04
freeze_verified_at_deferral: a5212589ad14f0b04cfe86085355bec8a4091720dc7275732b84643edb4c8e04  # 일치
review_in_flight: true
```

**문서 미편집.** 재심 in-flight이며 편집하면 결속이 깨진다. 운영자 지시("무한 루프 금지")에
따라 판정 수령 후 일괄 처분한다.

Stop 게이트 원문: **"v1.5 still contains mutually incompatible completion contracts."**

---

## DEF-3 (확증) — §5.4의 상태별 규칙이 §5.2.4의 v1.5 FWD-a와 상충한다

### 실측

```
:1130  §5.4  | `PASS` (2행)  | 실제 표면 필수. `existence=PRESENT` 아니면 오류 |
:1131  §5.4  | `READY` (79행)| 실제 표면 필수. `STAND_IN` 허용, 단 명시 |

§5.2.4 (v1.5)  적용 대상 = 검증 가능 kind({PACKAGE, TEST, REVIEWER})의 쌍뿐.
               검증 불가 kind({RUNTIME, FAULT})의 쌍은 존재는 필수이나 충족 판정 대상 아님
               → existence = UNVERIFIABLE
§5.2.8 floor   L2 이상 387행에 FAULT, L3 이상 374행에 RUNTIME 강제
```

### 귀결

`PASS`/`READY` 81행 중 L2 이상인 행은 floor에 의해 `FAULT`(및 `RUNTIME`) 쌍을 갖고,
그 쌍의 `existence`는 `UNVERIFIABLE`이다.

- **§5.4는 그것을 오류라고 한다** (PRESENT 아니면 오류 / 실제 표면 필수)
- **§5.2.4는 그것을 정상이라고 한다** (충족 판정 대상 아님)

**같은 행·같은 쌍에 대해 두 계약이 반대 판정을 낸다.**

### 결함 클래스 — 세 번째 재발

이 정확한 쌍(§5.4 상태별 규칙 ↔ FWD-a)이 어긋난 것이 **세 번째**다.

| 판 | 형태 |
|---|---|
| v1.3.4 | FWD-a가 81행에 단일 규칙 → §5.4의 `PASS`=`PRESENT`만 규칙과 충돌. 상태별 분기로 정합화 |
| v1.4 | (정합 유지) |
| **v1.5** | floor 도입으로 `UNVERIFIABLE` 쌍 발생 → FWD-a는 갱신했으나 **§5.4는 갱신하지 않음** |

**근본 원인은 같은 사실을 두 곳에 독립 기술한 것이다.** §5.4의 상태별 채움 규칙과
§5.2.4의 FWD-a 상태별 판정은 동일 계약의 두 표현이고, 한쪽만 고치면 반드시 갈라진다.
S-9(단일 소스)가 **값**에 대해 세운 원칙을 **규칙**에는 적용하지 않았다.

### 처분 방향 (판정 후 확정)

문구를 맞추는 것으로 끝내면 네 번째 재발이 예약된다. **구조적 처분**:

- §5.4는 상태별 규칙을 **재기술하지 않고 §5.2.4를 참조**한다 (단일 소스)
- 또는 두 절을 병합한다
- 어느 쪽이든 "PASS는 PRESENT" 같은 문장이 문서에 **한 번만** 나타나야 한다

S-14 후보: **동일 계약을 두 절이 각자 기술하지 않는다. 한 곳이 정의하고 다른 곳은
참조한다.** (S-9의 규칙 버전)

---

## 기각 — `Profile-dependent` 3행의 K-13 차단은 상충이 아니다

상충 후보로 검토했으나 **실측 결과 문제 없음**:

```
BC-EV-003    status=NOT_IMPLEMENTED   level=Profile-dependent
ECO-EV-012   status=NOT_IMPLEMENTED   level=Profile-dependent
IOM-EV-008   status=NOT_IMPLEMENTED   level=Profile-dependent
```

3행 전부 `NOT_IMPLEMENTED`이므로 **FWD-b(비차단 지표) 소속**이고 FWD-a에 들어가지
않는다. K-13이 이들을 차단해도 Phase 0 종료조건이 도달 불가가 되지 않는다 —
"승인된 Verification Profile이 해소하기 전에는 `READY`로 이동할 수 없다"는 규범
요구와 정확히 일치한다.

**추측하지 않고 실측해 기각한다.**
