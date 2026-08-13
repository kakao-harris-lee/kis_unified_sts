# verdict — 레인 B (계획 심판) · v1.4 · **2회 연속 완주**

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
reviewed_scope_digest: f706f5df5410ade9070418a6fc5770121525d07bde7b8baec437ab263a9a48e7
primary_doc_sha256: 82b5bd11a4829bacb59b9ac08659759a5ad17e31efed8b0dfbf6f1b6ac9263cf
reviewed_version: v1.4 (1868행)
findings: 6                        # high 4 / medium 2
prior_verdict: .omc/review/20260812-101107/verdict.md
```

실행: 모드 B, job `task-mspf9i58-8zff5g`, 8m 47s, 완주.
**동결 유지**: digest·doc SHA·행수·HEAD 4종 전부 시작=종료 일치.
부수 확증: 결속 범위가 **2문서**임이 실측으로 확정(주 문서 단독은 `239083ba…`).

## 직전 6건 처분 — 회피 0 / 문구만 0

| # | 판정 |
|---|---|
| #4 (과잉 CHECKABLE) | **해소** — UNCHK-011~013 강등이 거짓 주장을 제거, INV-C4로 MET 미기여 |
| #6 (K-11 범위) | **해소** — 전 490행 확대 + T-54 |
| #1 (U-2 우주) | 부분해소 |
| #2 (종료조건 약화) | 부분해소 |
| #3 (floor) | 부분해소 |
| #5 (VALUED) | 부분해소 |

**직전 회차(회피 1 + 문구만 2)에서 실질 진전.** 4건이 부분해소로 올라왔고 퇴행 0.

## 수용검사 — 6건 전건 채택, 기각 0

기준 6(`CLAUDE.md` 비협상)은 **직접 충돌 없음**. Codex가 조항별로 대조했다
(설정구동/DRY `:21-25`, Redis DB1·TTL `:26-28`, KST `:29-30`, secrets `:31-32`,
선물 무입금·REAL_ORDER 영구차단 `:36`, 독립 심판 `:143-158`).

### 직접 실측으로 확증 — 규범 텍스트가 심판보다 더 결정적

**#3 — `floor(e)`가 파싱은 되지만 규범 의미에서 파생되지 않는다**

`VER-002-001` §5 원문:

```
EV-L0 — Design Inspection
  Static architecture and requirement review.
  Every EV-L0 review SHALL record the reviewer's provenance …
EV-L2 — Component Fault Test
  A component is tested with controlled failure injection and authoritative state inspection.
```

- **EV-L2가 이미 fault test다.** v1.4의 floor는 `FAULT`를 L3 이상에만 붙였다 →
  **L2를 포함하되 L3가 없는 13행에서 `FAULT` 누락.**
- **EV-L0는 정적 설계 검토다.** 전 행에 `PACKAGE`·`TEST`를 요구할 근거가 없다.
  반면 EV-L0는 reviewer provenance를 **SHALL**로 요구 → `REVIEWER`의 근거는 여기 있다.
- **`+Security`는 독립 축이다** — "requires an independent security-boundary assessment
  covering identity, credential, authorization, fencing, and bypass paths".
  **157행이 이를 가지는데 `surface_kind`에 `SECURITY`가 없다.**
- `+Broker → RUNTIME`은 규범 문언에서 도출된 등치가 아니다.
- **`Profile-dependent`**: "Missing resolution **is a blocker** and SHALL NOT default to
  the lowest level" → v1.4는 UNCHK-010(완료조건 제외)로 처리했으나 **규범은 차단**을
  요구한다. **처분 방향이 규범과 반대다.**

→ 저작자의 floor는 **문법에서 파생됐고 의미에서 파생되지 않았다.** `{PACKAGE}` 단독
선언은 막지만, 무엇을 반드시 요구해야 하는지를 의미적으로 축소하는 경로는 남는다.

**S-13 자기 위반** — §13.4가 `NOT_MACHINE_CHECKABLE 6건`이라 쓰는데 레지스터는
**실제 14행**. 자기참조 카운트 금지 규칙을 만든 문서가 그 규칙을 위반한다.

**T-25 자기모순** — §7.4에서 U-7의 "미조사 vs 구조적 판정 불가" 의미 판정을 **제거**
했는데, T-25는 여전히 사유가 "미조사"면 실패하라고 요구한다. **제거한 판정을 테스트가
계속 요구한다.**

**순서 모순** — K-10이 모든 `K-*`의 강제 지점을 `tos_completion_status.py --check`로
고정하는데, 구현 순서는 D0-2(계약 생성) → D0-1(검사기 생성)이다. **D0-2는 완료 시점에
자기 계약을 실행할 강제 지점이 없다.**

## 이연 지적과의 관계

`DEFERRED-FINDINGS.md`의 DEF-1(floor→FAULT→UNVERIFIABLE→FWD-a 도달 불가)을
**심판은 독립 발견하지 못했다.** 이연 기록이 보완한다. 다만 #3이 확정되면 DEF-1의
전제(어느 레벨에 FAULT가 붙는가)가 바뀌므로 **함께 재설계해야 한다.**

DEF-2(UNDECIDED 탈출구)는 심판 #5가 같은 축을 독립 지적했다 — **입력 재량으로 이동**.
추가로 심판은 **무관한 non-null 키를 공급하면 기계적으로 `VALUED`가 파생된다**는
더 나쁜 경로를 찾았다(키의 사이트 관련성 검증 부재).

## 범위 판정 — 신규 표면 자체에 대한 경고

> "5. 범위·과잉 설계: **미통과** — 비규범 Markdown 계획을 CI 계약 데이터베이스처럼
> 파싱하는 새 표면이 생겼지만 안정된 문법·입력 결속이 없다."

**#1의 해법(`PHASE0-CONTRACT-INDEX`)이 그 자체로 과잉 설계 판정을 받았다.**
구체 근거: 선언 형식 불일치(G1~G3는 중복 키 표 행, FWD 계열은 bare `FWD`/`FWD2`/
`REV`/`REV2`가 `FWD-*` 어휘 밖), 산문 오탐(`FWD-a를 통과한다`), 대체된 U-7이 여전히
선언 형식, **입력 문서가 untracked라 fresh CI에서 재생성 불가**.

→ 다음 개정은 이 방향을 **더 정교하게 만들 것이 아니라 재검토**해야 한다.

## 게이트

```
통과 = codex AND approve AND digest 일치
현재 = codex AND needs-attention AND 일치     → 불성립 (4회 연속)
```

**P-0 및 D0 착수 계속 차단.**

## next_steps (Codex 원문)

1. 현재 verdict로 P-0과 D0 구현 착수를 계속 차단한다.
2. 재심에서는 부분해소로 판정한 #1·#2·#3·#5와 단계 순서·자기 규율 finding을 우선 재검증한다.
3. #4와 #6은 관련 문언이 다시 변경되지 않는 한 해소 판정을 유지할 수 있다.

## 구조적 관찰

동결 도입 후 **2회 연속 완주**했고 판정 품질이 올라갔다 — 이번 심판은 규범 문서
(`VER-002-001` §5)를 직접 읽어 저작자의 floor 규칙이 **문법 파생이지 의미 파생이
아님**을 보였다. 위생 왕복과 달리 이것은 외부 근거에 결속된 지적이다.

동시에 경고 신호도 있다: 각 수정이 새 기제를 낳고, 새 기제가 자기 강제 지점을 필요로
하며, 문서는 1,868행에 자체 절차 S-1~S-13을 갖췄는데 **그 절차를 자기 개정에 적용한
증거가 없다**(finding 6). 다음 개정은 기제 추가가 아니라 **축소 방향**이어야 한다.
