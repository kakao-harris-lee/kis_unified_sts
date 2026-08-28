# 설계 문서 #37 — 다심볼(multi-symbol) 확장 계약 (이연 ③ closure·provisional·닫는 EV 0건) (2026-08-06, v1.2)

> **v1.2 개정(2026-08-06)**: 독립 델타 재검증 **REVISE 유지(신규 MAJOR 2·MINOR 3)** 전건 처분 —
> v1.1이 v1.0 비평 20건 전건 해소 확인·델타 인용 off-by 0·C1 배선 "초과 충족"(재진입/중첩 무모호 코드
> 확정). 잔여 2건은 교정이 낳은 국소 결함이며 **둘 다 명시 채점 결함 클래스의 2차 재발**(전칭-반례 →
> §1.3 B3 반례·뮤테이션-표면 → fill_records 판별 단언)이라 §12에 "같은 클래스 재발 → 닫힘"으로 기록.
> RATIFY-READY 근접. 처분 전수는 §12.
>
> **v1.1 개정(2026-08-06)**: 독립 적대적 비평 **REVISE(CRITICAL 1 · MAJOR 8 · MINOR 6)** 전건 처분.
> 비평 판정 방향은 **전부 유지**: 분기 A 채택·엔진 코어 무변경·per-scope 잉여·VECTOR 미개방(§1.5 구조
> 파생 성립)·D2 기각 타당·M7 GREEN(세 불릿 문자 그대로 참·실측)·인용 정확성(phantom 0). 개정은
> 재설계가 아니라 **배선 완결(C1 단일 Transmit 슬롯 demux)·논증 교정(MJ-1 도달불가 상태·MJ-2 하이브리드·
> MJ-7 비준상태)·canary census 이행(MJ-5 M15-M20)**이다. 처분 전수는 §12. 개정 대상 배너 유지:
> 저작 → 1차 심사 → **독립 비평(완료·REVISE)** → 개정(본 v1.1) → 운영자 위임 자동 비준 → 구현 →
> 적대적 코드 리뷰. 본 산출 **provisional·닫는 EV/AC 0건**.
>
> **성격: 이연 closure 계약.** 수직 슬라이스 #1 완결(#31~#35) 시점에 비준·기록된 정직 이연 중
> ③ 다심볼(per-scope last-reference)을 닫는 계약. 스코핑 입력은
> `docs/plans/2026-08-05-tos-deferral-closure-scoping-survey.md`(이연 ③ 절 A/B/C·§D·§E·오케스트레이터
> 판정 :457 "#37 = ③ 다심볼")를 구속 입력으로 상속한다.

---

## 0. 전제·규율·경계

### 0.1 베이스라인·실측 규율 (anti-phantom)

- **베이스라인**: 서베이 실측 HEAD `5ebc61f8`(clean), 갭-closing 구현 실제 트리 `5e26f47d`.
  본 계약의 **모든 file:line 인용은 2026-08-05/06 자체 read 실측값**이다(구현 커밋 후 드리프트 가능·
  §6 REGREP).
- **부재 주장 negative-grep 병기**(존재·부재 양방향):
  1. `grep -rn "_last_reference" tos/src/tos/` → **5행**: `core.py:246`(선언·상태)·`:280`(비교)·`:301`(갱신)
     **+ `driver.py:8`·`converter.py:18`(둘 다 산문 인용)**. ⇒ **상태(state)는 코어 3행에만** 있고
     나머지 2행은 docstring 산문이다(MINOR-1 정정 — v1.0은 "3행뿐"으로 오전사).
  2. 심볼별 continuity를 배정하는 코드 → **0건**. 현행 백테스트는 `YieldOrderCounter`(driver.py:87-143)가
     **단일 continuity**(1 `source_continuity_id`)를 발행(driver.py:94·:141).
  3. `ProvisionalReservationLedger`에 `release`/`free`/`clear`/`reset` → **0건**(state.py:22·:175-176)·M13.
  4. `PortfolioVector` 접기 소비 경로 → **0건**. `pipeline.py:329-340`이 fail-closed withheld(M1).
  5. `AttemptRequest`에 instrument/scope 필드 → **0건**(records.py:347-351 실측: `attempt_id`·
     `conformance_proof_digest`·`action_flow_permit_identity`·`reference_coordinate_digest`·`authority`
     뿐). **C1의 구조적 근거**.

### 0.2 "per-scope last-reference"의 원문 근거 — 정직 서술 의무 (구속)

**"per-scope last-reference"라는 문구의 원문은 설계 5편(#31~#35) 어디에도 없다.** 서베이 전수 grep의
유일 출처는 **`docs/plans/INDEX.md:25` 한 줄**(서베이 :263-267·:436-438). #31 적대적 코드 리뷰 원
산출물은 리포에 미커밋. ⇒ **본 계약이 그 NIT의 실체를 처음 완전 서술한다.** INDEX 문구는 "per-scope가
정답"이라 규정하지 않고 "다심볼 시점에 **해소할 질문**"으로 flag했을 뿐이다. 본 계약은 그 질문을
§1에서 증거로 해소하며, 해소 결과가 "전역 유지"일 수 있음을 배제하지 않는다(서베이 :294·:388 사전 인가).

### 0.3 스코프·경계 (구속)

- **다심볼 = N-entry 레지스트리**(N개 per-instrument 전략)·**인터페이스 무변경**(#31 §3.3·registry.py:59).
  레지스트리·ledger(per-scope·state.py:137)·marketfeed resolver(`(capsule, *, instrument_key)`
  파라미터화)는 **무변경**(§2 실증).
- **VECTOR 접기는 열지 않는다.** M1(`test_engine_pipeline.py:222-236`) **GREEN 유지**. §1.5 실증.
- **발명 금지(서베이 §E 2편 (a)-(f) 전건 전사·구속)**: (a) 와일드카드 전략(#31 §3.3 (B)·RFC-003
  §9:279-283·admission.py:212-217); (b) net-position ledger/평단/multi-leg(#35 §10-2·state.py:178-182);
  (c) RCL release/capacity 해방(M13·state.py:22); (d) AMBIGUOUS→REVERSED 승격(M6); (e) 카운터
  reset/rewind(driver.py:134-135·M8); (f) VECTOR 스코프 확대.
- **canary 처분**: M1-M14는 **시작점**이며 §4가 자기 터치 표면 census(M15-M20·MJ-5)를 이행한다.
- **신규 .py 0**(M12·M18·M20). 신규 심볼은 전부 기존 backtest submodule에 배치(§3.1·§6).

### 0.4 이 계약의 심장 — 선행 판정 + 신규 load-bearing 불변식 (요약)

**선행 판정(서베이 §B·오케스트레이터 지시)**: 스트림 모델 = *단일 continuity + 단일 yield 카운터로
N심볼 인터리브* **vs** *심볼별 continuity*(하이브리드 포함). §1이 양 분기를 끝까지 설계하고 증거로
선택한다.

**결론**: **단일 continuity 채택 → 엔진 코어 `_last_reference` 전역 유지(무변경) → NIT는 채택 모델 하에서
불성립.** 기각 근거의 **최강 축은 검출력 포함관계 A ⊋ B**(§1.3): 단일 continuity는 **모든** 인접 쌍을
native로 orderable하게 만들고(cross-lane 포함), 심볼별 continuity의 어떤 변종(하이브리드 포함)도
cross-lane 인접 쌍을 `same_continuity=False`(_ordering.py:112-116)로 **AMBIGUOUS**(검출 비활성)로 둔다.

**신규 load-bearing 불변식(본 계약이 처음 명명)**: 다심볼에서 **단일 `Transmit` 슬롯의 lane demux는
`AttemptRequest` 무스코프(records.py:347-351)로 payload 파생이 불가**하므로, **코어의 동기·단일스레드
완결 보장**("one event ... to completion before the next"·core.py:1-3)에 의해 "현재 처리 중 lane"으로
demux한다(§3.2·C1). 이 완결 보장이 다심볼 배선의 **정확성 근거**임을 명기한다.

---

## 1. 선행 판정 — 스트림 모델과 last-reference 형태 (계약의 심장)

### 1.1 실측 메커니즘 (서베이 §B 정면 분석)

`ordering_admission`(core.py:160-181)은 incoming을 **단일 전역** `_last_reference`(core.py:246)에
대조하고, MONOTONE·AMBIGUOUS 모두 슬롯을 갱신한다(core.py:280·:301). `compare_order`(_ordering.py:86-139)의
백테스트 유효 우선순위는 priority 3-4(native/local-monotonic)뿐이고 **`same_continuity`일 때만**
비교된다(_ordering.py:112-127). 백테스트는 quorum/egress/causal/time을 순서에 안 쓴다(driver.py:97-99·
`test_backtest_ordering.py:90-96`). ⇒ **교차-continuity 쌍은 `AMBIGUOUS`로 떨어지고**(_ordering.py:139)
**halt 없이 수용·슬롯 덮어씀**(core.py:280-301·M6).

**심볼별 continuity 채택 시 신규 fail-open의 실물**:

| yield | 이벤트 | `compare_order` | 전역 슬롯 |
|---|---|---|---|
| 1 | A@contA | (first) MONOTONE | A@contA |
| 2 | B@contB | `same_continuity(A,B)=False` → **AMBIGUOUS** → 수용 | **B@contB (덮어씀)** |
| 3 | A@contA (논리적 A 역행) | vs B@contB: `same_continuity=False` → **AMBIGUOUS** → 수용 | A@contA |

심볼 A의 역행이 심볼 B 좌표 뒤에 숨어 잡히지 않는다(전역 슬롯의 continuity conflate). 이것이 NIT의
실체이며 다심볼 신규 fail-open이다(단일 스코프 불성립). §5-T1이 `ordering_admission` 위에서 직접 실행.

### 1.2 분기 A — 채택: 단일 continuity + 단일 yield 카운터 (전역 last-reference 유지)

**구성**: 다심볼 백테스트가 **하나의 `YieldOrderCounter`**(단일 continuity·단일 native sequence)로 N심볼
전 이벤트를 yield 순서로 스탬프. 현행 단일-심볼 드라이버(driver.py:87-143·"a single continuity"·"One
counter for the whole run")의 N심볼 확장이다.

**정합성 증명 (MJ-1 교정 — 도달 불가 상태를 논거로 쓰지 않음)**:

v1.0의 "역행이 심볼 B 좌표 뒤에서도 REVERSED로 잡힌다"는 서술은 **공허하게 참**이었다 — 분기 A에서
좌표의 유일 출처는 monotone 카운터(driver.py:130-143·reset 부재 M8)라 **"native 3 < 6" 같은 역행은
애초에 구성 불가능**하기 때문이다. NIT의 진짜 해소 논증은 **두 층**이다:

1. **역행 구성 불가 ⇒ per-scope 잉여.** 단일 카운터가 전 이벤트를 단조 스탬프하므로 엔진 게이트의
   REVERSED 경로는 backstop이고, per-scope 키잉은 그 backstop이 이미 못 만나는 상태를 위한 것 —
   추가 검출 0.
2. **심볼별 *논리적* 역행은 엔진 게이트가 아니라 입력 계약이 막는다.** 각 lane bar는 **per-lane
   `validate_bar_stream`의 strictly-increasing fail-closed**(bars.py:110-148 — `bar_index`·
   `timestamp_coordinate` 비단조면 raise)를 통과하고, **병합이 lane 내부 순서를 보존**한다(k-way merge는
   스트림 내부를 재정렬하지 않음·§3.3). ⇒ 각 lane 이벤트가 코어에 **단조 순서로 도달**한다. 이것이
   NIT의 실제 봉인이며, 엔진 코어 변경이 아니라 **입력 계약 + 병합 순서 보존**이 소유한다.

**검출력 포함관계 A ⊋ B (관측 가능·비공허)**: 분기 A는 **모든 인접 쌍이 동일 continuity**라
`compare_order`가 native로 orderable → **인접 쌍 전부 MONOTONE**(cross-lane 포함). 이는 역행 없이도
관측된다: 다심볼 trace의 전 entry `ordering_admission is MONOTONE`(선례 `test_backtest_ordering.py:251-253`
`[MONOTONE]*3`). 심볼별 continuity였다면 cross-lane 인접 쌍이 AMBIGUOUS로 나타난다(§1.3). ⇒ 분기 A의
게이트 커버리지가 **strict superset**이고, §5-T2 뮤테이션의 killing 관측이 정확히 이 MONOTONE/AMBIGUOUS
차이다.

**추가 이점**: (i) **엔진 코어 변경 0**(core.py:246/280/301 그대로·NIT 불성립·서베이 :294); (ii)
**byte-identical replay** 단일 total order(§1.6·§5-T5); (iii) **M10 정합** `source_native_sequence ==
yield_sequence`(`test_backtest_ordering.py:257-270`) 단일 카운터에서 유지; (iv) **M6 정합** — 단일
continuity는 교차-심볼 AMBIGUOUS 불발생, 서베이가 우려한 "M6이 검출 공백 통로"(:309)는 분기 A에서
**물질화하지 않음**; (v) **인터페이스 무변경(#31 §3.3) 극대 준수**.

### 1.3 분기 B — 기각: 심볼별 continuity (3변종 완전 설계·A ⊋ B가 최강 기각 축)

기각지를 **완전 설계**하여 §7 contingency로 인계한다. **세 변종**을 명기한다:

- **B1 (약변종)**: 심볼별 continuity + **심볼별 native 카운터**. native가 심볼마다 재시작.
- **B2 (하이브리드·MJ-2)**: 심볼별 continuity + **전역 단일 native 카운터**(=yield sequence). **M10
  보존**(`source_native_sequence == yield_sequence`·`test_backtest_ordering.py:267`). — v1.0이 놓친 변종.
- **엔진 측 공통**: `_last_reference`를 `OrderingEvent | None` → **`dict[str, OrderingEvent]`**, 키 =
  **`source_continuity_id`**(instrument_key 아님). `handle`(core.py:280)이 continuity로 슬롯 조회·비교·
  갱신. `None` continuity는 sentinel 슬롯·∅ 양방향.

**키 선택 논증(per-continuity vs per-instrument)**: 슬롯 키는 **`source_continuity_id`가 정답**이다 —
`compare_order`가 orderable을 산출하는 정확한 범위가 continuity이기 때문(instrument 키잉은 단일 심볼의
다중 continuity·다중 심볼의 공유 continuity를 오처리). 단일 continuity면 슬롯 1개 → 분기 A와 행동 동치.

**기각의 최강 축 — 검출력 포함관계 A ⊋ B (native-branch 변종 공통·MJ-2·MAJOR-N1 정정)**: **B1·B2
공히 cross-lane 인접 쌍이 `same_continuity=False`(_ordering.py:112-126) → AMBIGUOUS → 검출 비활성**이다.
분기 A는 전 인접 쌍 검출 활성(§1.2). ⇒ A의 게이트 커버리지가 **native-branch 변종(B1·B2)의 strict
superset**이다. **유일한 회피는 B3**(심볼별 continuity + 전역 native + **각 이벤트가 직전 yield를
`causal_predecessor_ids`로 지목**)인데, `compare_order`가 same_continuity 실패 **후** typed causal
links를 보기 때문이다(_ordering.py:128-133·필드 실재 :72·현 카운터는 비워 둠 driver.py:139-143).
**그러나 B3는 회피가 아니라 A로의 우회 수렴이다**: continuity 밖에서 단일 total order를 causal 체인으로
재구성하므로 A와 검출력 **동치**이면서 좌표를 **2벌**(per-symbol continuity + causal chain)로 유지하는
**더 비싼 구조**이고, 결함 2·4·5가 그대로 적용된다. ⇒ **어떤 B 변종도 A보다 싸게 A의 검출을 달성하지
못한다** — B2(하이브리드)는 M10을 보존하나 cross-lane 검출을 회복하지 못하고, B3는 회복하나 A로 비싸게
수렴한다.

**나머지 기각 근거(재편)**:
- **결함 2 (본질·전 변종)**: 엔진 코어 `_last_reference`를 dict로 전환 ⇒ 비준 #31 코어 권위 표면 수정·
  M7 docstring stale(lockstep)·인터페이스 무변경(#31 §3.3) 위반.
- **결함 4 (본질·전 변종)**: 분기 B는 §1.1 fail-open을 **도입한 뒤** per-scope로 봉인. 분기 A는 애초
  미도입. 방어가 필요한 상황을 자초하지 않는 편이 우월.
- **결함 5 (본질·전 변종)**: 유일 정당화 "라이브가 심볼별 continuity 강제"는 비준 안 됨(§1.4·
  broker-agnostic)·백테스트를 비준 단일-continuity 설계(driver.py:94)와 괴리. 서베이 :388 "근거 없는
  구조 변경".
- **결함 1·3 (B1 한정·비본질)**: M10 파괴(결함 1)·replay 약화(결함 3)는 **B1 약변종의 산물**이며
  **B2 하이브리드는 회피**한다. ⇒ 이 두 축은 "B1 특정 변종 한정"으로 강등한다(§8-1 정정).

⇒ **분기 A 채택. 분기 B 전 변종 기각**(최강 축 A ⊋ B). 단 §7-1이 **B2 하이브리드를 contingency 권장
형태**로 인계한다(M10/replay 보존 + per-continuity 검출 회복).

### 1.4 라이브 D-E1/D-E4 경로 함의 — 엔진 코어의 계약 (MJ-7 교정)

전역 슬롯은 **스트림이 단일 continuity일 때만** 옳다. 코어는 broker-agnostic이라 라이브 토폴로지를
가정할 수 없다. ⇒ 분기 A는 **명시적 전방 의무**를 동반한다:

- **FORWARD-OBLIGATION-MS1 (신규 전방 의무·비준물 부재·MJ-7 정직 서술)**: 다심볼 라이브 `EventSource`
  (D-E4 paper sender / 실 KIS transport·#34 §5.1 이연)는 **단일 continuity의 ingest/receive-order
  시퀀스**를 코어에 제시해야 한다. **이는 #33 §3.4의 좌표 원칙(인과 좌표 = 하네스 yield-order·단일
  continuity·driver.py:5-20)을 라이브 ingest 경계로 *처음 확장*하는 신규 전방 의무다.** #33 §3.4는
  **백테스트 드라이버 처방**이고, #31의 continuity 언급은 전부 snapshot provenance(양방향 grep 실측)이라
  **라이브 측 비준물은 존재하지 않는다.** ⇒ 이 의무는 "이미 비준된 원칙"이 아니라 **라이브 다심볼
  사이클이 게이트로 승격해야 할 신규 의무**다.
- 코어는 **이 의무 하에서 무변경으로 옳다**(교차-continuity를 spurious하게 순서짓지 않음·AMBIGUOUS·
  올바름). 유일 잠재 공백은 전역 슬롯 conflate이며 이 의무가 덮는다.
- **contingency 인계**: 미래 라이브가 이 의무를 충족 불가로 판정하면(브로커가 환원 불가능한 심볼별
  continuity 강제), **B2 하이브리드(§1.3·`source_continuity_id` per-scope + 전역 native)가 권장 봉인
  설계**로 착지한다(§7-1).

**검토·기각 — 코어에 "2번째 continuity 거부" 가드(D2)를 지금 추가**: 기각(판정 유지·MJ-7 무관). (a)
불변식을 코어에서 self-enforcing 가능하나 (b) **B2 contingency를 foreclose**하고 (c) 분기 A 백테스트에서
결코 발화 안 해 실증 불가. 불변식은 코어 하드 거부가 아니라 **ingest 경계의 전방 의무**로 두는 편이
미래-유연·비-발명. 코어는 agnostic·무변경.

### 1.5 VECTOR를 열지 않고 다심볼이 충족됨의 실증 논증 (판정 유지)

다심볼 = **N개 독립 per-instrument 전략**. 각 전략은 정확히 1스코프 선언(admission.py:206-209가 2스코프
거부·M2)·N개가 N키로 등록(registry.py:127)·각 tick은 자기 키로 dispatch(core.py:331)·그 키의 entries만
평가(`_run_entries` core.py:363-413). 스칼라 per-instrument 결정 N개 = 다심볼(레지스트리 인터페이스
무변경·registry.py:59). `PortfolioVector`(1전략 N심볼 all-or-none outcome)는 **별개 축**(OUT-5·RFC-008·
tos.dsl 기구현이나 슬라이스 미사용)이고 `pipeline.py:329-340`이 fail-closed 유지 — 사유 문자열("later
multi-symbol cycle")은 다심볼을 N-entry로 충족한 본 사이클에도 **정직**하다(VECTOR는 미착수 *다른* 축).
**M1 GREEN(FLIP 아님)**.

### 1.6 byte-identical replay가 다심볼에서 성립함 (분기 A)

성립. (1) 단일 카운터 → 단일 total order; (2) 병합이 `(timestamp_coordinate, account, instrument)`
전순서의 순수 함수(§3.3); (3) `trace_document`/`trace_digest`(results.py:94-143) 재현; (4) M10 등식 유지;
(5) **fill_records도 재현**(§3.3 정산 순서 결정론·선례 `test_backtest_replay.py:52-59`). §5-T5가
"동일 입력 2회 → 동일 `trace_digest` **및** 동일 `fill_records` 튜플"을 봉인. 공격면 "byte-identical
replay가 다심볼에서도?" 정면 처리.

---

## 2. 변경 표면 — 무엇이 바뀌고 무엇이 안 바뀌나 (실측 귀속)

| 표면 | 파일 | 처분 | 근거 |
|---|---|---|---|
| 엔진 코어 `_last_reference`·`ordering_admission`·dispatch·`_run_entries` | `engine/core.py` | **무변경** | §1.2 — 단일 continuity 전역 슬롯 정답·dispatch 이미 per-key |
| 단일 `Transmit` 슬롯(core.py:216/243/389) | `engine/core.py` | **무변경**(슬롯 자체) | C1: 드라이버가 슬롯 점유·현재 lane demux(§3.2) |
| `ProvisionalReservationLedger`(per-scope·at-most-one) | `engine/state.py:137·195-209` | **무변경** | per-scope 키잉·독립성 구조적 |
| `StrategyRegistry`(N-entry)·`derive_instrument_key`·VECTOR | `engine/registry.py`·`admission.py`·`pipeline.py:329` | **무변경** | §1.5·M2·M3·M1 |
| marketfeed resolver | `marketfeed/resolver.py` | **무변경** | 이미 `(capsule, *, instrument_key)` |
| `CausalBarConverter`·`DeterministicFillModel` | `backtest/converter.py`·`fills.py` | **무변경**(lane 단위 재사용) | §3.2 |
| 단일-심볼 `BacktestDriver` 공개 표면 | `backtest/driver.py:146-316` | **동작 무변경**(순수 리팩터로 헬퍼 추출·MJ-4) | §3.1 |
| **다심볼 드라이버**(신규 심볼·기존 파일)·병합/검증 헬퍼 | `backtest/driver.py`·`backtest/bars.py` | **신규 additive** | §3.1-3.3 |
| **다심볼 run 타입**(신규 frozen dataclass·기존 파일)·trace 변형(신규 함수) | `backtest/results.py` | **신규 additive** | §3.5·판정 |
| `WiringTrace`(단일 continuity_id·per-entry instrument_key) | `backtest/records.py` | **무변경**(재사용) | 분기 A continuity 1개 |

**요약**: 엔진·레지스트리·ledger·resolver·VECTOR·단일 `Transmit` 슬롯 **전부 무변경**. 변경은
**backtest 패키지 내부 additive 신규 심볼**에 국한. **엔진 코어 변경 0**이 헤드라인(#31 §3.3 극대 준수).

---

## 3. 구현 지정 — 다심볼 백테스트 드라이버 (분기 A)

> load-bearing 불변식 + 컴포넌트 지정. 클래스/메서드명은 제안이며 `__all__` phantom·submodule-drift·
> DRY 규율에 구속. 구현자는 추가 판단 없이 착수 가능하되 명시 불변식을 벗어나지 말 것.

### 3.1 배치·추출 규율 (MJ-4 — 추출 의무화·오케스트레이터 판정 채택)

- **신규 .py 0.** 신규 심볼은 기존 submodule: 다심볼 드라이버 → `backtest/driver.py`, 다심볼 run/trace →
  `backtest/results.py`, **병합/검증 헬퍼 → `backtest/bars.py`(판정 확정·"또는" 제거 — #35 배치-미지정
  결함류 차단)**. #35 MAJOR-1 배치 규율 동형.
- **DRY 추출 의무화(MJ-4·v1.0 "무수정" 모순 해소)**: 다심볼 드라이버는 per-lane "settlement context
  바인딩 → tick 스탬프·yield → due fill 정산" 로직을 단일-심볼 `events()`(driver.py:202-245)와 **공유
  private 헬퍼로 추출**한다. 이는 **순수 리팩터(동작 동일)**이며:
  - `BacktestDriver` **공개 표면 불변**·`test_backtest_single_core.py:143-152` 금지 목록(set_core/
    rebind/reset/…) **불변**(M17).
  - **게이트(구속·이행 판정)**: `tos/tests/backtest/` **전건 GREEN** + **기존 시나리오 digest 불변**
    (`test_backtest_replay.py:40-49` `trace_document`·`trace_digest` 2회 동일·M19). 추출이 이 digest를
    바꾸면 리팩터가 아니다 — 되돌린다.
- **`_backtest_fixtures.py` 확장은 신규 .py 규율과 무관**(테스트 fixture는 submodule-drift census
  `test_backtest_import_closure.py:562-576`의 대상이 아님 — src 디스크 목록만 감시). 다심볼 테스트
  fixture 추가는 자유.

### 3.2 lane 구성 + 단일 Transmit 슬롯 demux (C1 — CRITICAL 해소)

다심볼 드라이버는 **N개 lane**을 보유. lane = `(CausalBarConverter, DeterministicFillModel)`, instrument_key로
키잉. **단일 `YieldOrderCounter`**(1 continuity)를 전 lane이 공유.

- **lane의 `EgressResultSource`는 본 계약에서 `DeterministicFillModel`로 한정(판정)**. `GatewayResultReinjector`
  (#35 GAP-1)의 다심볼 사용은 **명시 out-of-scope**(retained 전량 drain이 심볼 귀속을 붕괴시킬 소지 —
  후속 판정 대상·§7-8).
- **단일 코어 재사용 불변**: 다심볼도 **하나의 `EngineCore`**를 전 lane·전 bar에 재사용
  (`CoreReinstantiationError`·driver.py:78-84). 드라이버는 코어를 **구성하지 않는다** — `run(core, ...)`
  인자로 주입받는다. **M18(`test_backtest_single_core.py:111-141` AST 스윕)이 이 "단일 코어 재사용"의
  실제 강제자**다(다심볼 드라이버가 `EngineCore()`/`ProvisionalReservationLedger()`/`StrategyRegistry()`를
  구성하면 loud FAIL). lane별 ledger 없음 — capacity 독립성은 코어 per-scope ledger(state.py:137)가 제공.

**단일 Transmit 슬롯 demux (C1의 핵심·신규 load-bearing 불변식)**:

`EngineCore`는 `transmit` 슬롯이 **1개**(core.py:216 param·:243 `self._transmit`·:389 `run_commitment_flow`에
전달)이고, 그 슬롯이 받는 `AttemptRequest`는 **instrument/scope를 싣지 않는다**(records.py:347-351 실측·
§0.1-5). ⇒ **attempt로 lane을 파생(demux)하는 것이 구조적으로 불가**하다. 순진한 "단일 fill model 공유"는
`DeterministicFillModel.instrument_key` 단수(fills.py:372·452)로 전 fill을 한 키로 스탬프하고 `settle_due`의
bar_index 매칭(fills.py:473-474·bar_index는 lane-지역)으로 **교차-심볼 정산 오염을 조용히 출하**한다.

**계약**: **다심볼 드라이버가 `Transmit`을 구현해 코어의 단일 슬롯을 점유**하고, **"현재 lane" 포인터로
demux**한다:
1. 병합 frontier에서 다음 `(instrument, bar)`를 뽑을 때 **현재 lane = 그 instrument의 lane**으로 설정하고,
   그 lane의 fill model에 `bind_settlement_context(bar)`(fills.py:415-421)를 호출.
2. lane의 tick을 **공유 카운터**로 스탬프·yield(driver.py:230-235 형태).
3. 코어가 tick을 **완결 처리**하며 step-14에서 `transmit(attempt)`을 호출 → 드라이버의 `Transmit`이
   **현재 lane의 fill model에 위임**(`current_lane.__call__(attempt)` — 그 lane의 `instrument_key`로
   스탬프·fills.py:452).
4. tick 후 현재 lane의 due fill 정산(`settle_due(bar)`·fills.py:462) → 각 EGRESS_RESULT를 공유 카운터로
   스탬프·yield. EGRESS_RESULT는 `payload.instrument_key`를 실으므로(core.py:424) 코어 per-scope ledger에
   정확 라우팅.

**demux 정확성의 근거 = 코어의 동기·단일스레드 완결 보장(core.py:1-3 "One event is processed to
completion before the next")**: 드라이버 제너레이터는 (2)의 yield에서 **suspend**되고 코어가 tick을
완결(단일 `transmit` 호출 포함)할 때까지 재개하지 않으므로, (3)의 `transmit` 시점에 "현재 lane"은
**모호 없이** (1)에서 바인딩한 lane이다. **이 완결 보장이 본 계약의 신규 load-bearing 불변식**이며,
`AttemptRequest` 무스코프를 처리 순서 demux로 상쇄하는 정확성의 원천이다. §5-T10이 봉인.

- **현재 lane 미설정 시 fail-closed(MINOR-N4·발명 아님)**: 드라이버 `Transmit`이 현재 lane 미설정으로
  호출되면(정상 흐름 불발생) `BacktestIntegrityError`로 fail-closed — `fills.py:441-446`("settlement
  context 미바인딩" raise) → 시퀀서 `TRANSMIT_RAISED` halt(sequencer.py:534-545) 경로 상속·신규 발명 아님.

### 3.3 결정론적 k-way 병합 (byte-identical replay의 엔진)

다심볼 `events()`는 N lane의 bar를 **결정론적으로 병합**하여 단일 카운터로 스탬프:

- **병합 키·tie-break**: `(bar.timestamp_coordinate, key.account, key.instrument)` **전순서**. 동일
  timestamp의 심볼 간 순서를 instrument_key 사전순으로 결정론적으로 깬다(byte-identical 필요조건·§1.6).
- **병합 결과 전역 순서 단언(MJ-8 (ii)·강제 가능)**: 병합 산출 스트림의 `timestamp_coordinate`가
  **non-decreasing**임을 헬퍼가 단언(비단조면 fail-closed). §5-T6.
- **per-lane 처리**: §3.2 (1)-(4) 순서로 lane별 바인딩·정산. NEXT_BAR 정산은 그 lane의 다음 bar가 병합
  순서에서 도래할 때 settle(fill model `settle_due`가 자기 lane bar로만 발화·state 독립). bar_index는
  lane별이라 두 entry(다른 심볼)가 공유 가능 — `yield_sequence`는 공유 카운터로 전역 유니크하므로 무해
  (§3.5).
- **fill_records 순서(MJ-6·MAJOR-N2 정정)**: `LocalFillRecord`에 **전역 순서 필드가 없고**(records.py:87-109)
  `settlement_bar_index`는 lane-지역이라 **lane별 `.records`의 사후 병합은 전역 정산 순서로 재구성
  불가**하다. ⇒ 다심볼 드라이버가 **정산 시점(§3.2 (4))에 순서대로 단일 run-level 누적기에 append**한다
  (끝에서 lane별 `.records`를 concat하지 않음 — concat은 lane-그룹 순서라 전역 yield 순서를 잃는다).
  누적 순서 = yield 순서(= §3.3 전순서)·§5-T5 판별 단언이 lane-concat을 KILL.

**look-ahead 무저촉(정면 처리)**: 병합 frontier는 lane당 **최대 1개 pending bar**의 순서 metadata
(`timestamp_coordinate`)만 비교. **어떤 미래 bar도 결정에 미투입** — 각 converter는 자기 lane 현재
bar로만 tick 구성·prefix-bounded 유지(converter.py:3-13). frontier는 converter 상태가 아니라
**드라이버**의 순서 metadata(드라이버는 이미 `self._yielded` 보유·driver.py:182)·크기 유계(≤N). ADR-DEV-010
**BTE-INV-004("every indicator and input SHALL be bounded by the current context timestamp"·#33 :368
원문·MINOR-2 정정: instrument-스코프 축소 서술 제거)** 무저촉.

- **검토·기각 — 병합을 caller(out-of-tree)에서**: 기각. bar 로더는 out-of-tree(bars.py:4-7)지만
  **병합 결정성은 replay 재현성의 핵심**이라 in-tree 보증이 정직. caller 병합은 byte-identical을
  tos.backtest 보증에서 caller 규율로 이전. mapping + in-tree 결정론 병합 우월.

### 3.4 continuity 배정 (단일·명명)

**하나의 `continuity_id`**(주입·명명·`YieldOrderCounter` 생성자가 공백 거부·driver.py:112-116·M9)를 전
lane·전 이벤트가 공유. **심볼별 continuity 금지**(분기 B·기각). M8(reset 불가)·M9(명명) GREEN·재사용.

### 3.5 다심볼 run 아티팩트 (MJ-6 — 전건 처분·판정 반영)

**판정: 신규 run 타입 = frozen dataclass**(기존 `BacktestRun` `@dataclass(frozen=True)`·results.py:52와
대칭). **근거**: pydantic이 아니라 dataclass여야 M15(`test_backtest_result_surface.py:92-109` — `_SEALED_MODELS`
= `FrozenModel` 서브클래스 집합 잠금)를 **건드리지 않는다**(dataclass는 FrozenModel 아님). pydantic run
타입이었다면 M15가 WIDEN으로 발화. **trace 변형 = 신규 함수 추가**(해석 A — 기존 `trace_document`·
`test_backtest_replay.py:125` JSON-native 단언 무저촉).

**`BacktestRun` 11필드(results.py:64-74) 전건 처분표(신규 run 타입)**:

| 필드 | 처분 | 근거 |
|---|---|---|
| `instrument_key: InstrumentKey` | → **`instrument_keys: tuple[InstrumentKey, ...]`**(lane 키 집합·insertion order) | 복수화(신규 타입이라 rename 아님) |
| `scenario_id: ScenarioId \| None` | **run-level 단일(carried)**·lane 공유 | 판정: ScenarioId는 run-identity(results.py:65 1/run)·per-lane 분해는 소비자·vocabulary 부재(§7-9 이연) |
| `bars_consumed: int` | **집계**(Σ lane) | — |
| `events_yielded: int` | **집계**(전 lane yield 총수) | — |
| `event_results: tuple[EventResult, ...]` | **집계**(yield/처리 순서·코어 산출 그대로) | 이미 전역 순서 |
| `trace: WiringTrace` | **carried**(단일 continuity_id + per-entry instrument_key·재사용) | 분기 A continuity 1개·`TraceEntry.instrument_key` 이미 존재 |
| `halts: tuple[HaltRecord, ...]` | **집계**(각 HaltRecord가 instrument_key 보유) | halt lane 격리(아래) |
| `fill_records: tuple[LocalFillRecord, ...]` | **집계 — 드라이버가 정산 시점 순서대로 누적**(§3.3·사후 병합 불가·records.py:87-109)·각 attempt_id/instrument_key 보유 | 결정론·판별(§5-T5) |
| `unsettled_fill_records: tuple[...]` | **집계 — EGRESS_RESULT 부재**(result_kind None·records.py:126)·순서 계약은 lane iteration(instrument_key 사전순)×intra-lane pending 순서(별도·§5-T5 주석) | — |
| `handoff_count: int` | **집계**(Σ lane) | — |
| `label: str = DEMONSTRATION_LABEL` | **carried**(상수) | — |
| `closes_no_ev`(property·비-파라미터) | **carried**(True·비-파라미터·M16) | 성과 주장 0 |

- **M16 seal 확장(MJ-5)**: 신규 run 타입은 `__post_init__`에서 `seal_performance_surface`(results.py:76-80)
  실행 + **성과-필드 census(`test_backtest_result_surface.py:70-89`)·closes_no_ev census(:112-117)에
  신규 타입 추가**(EXTEND). `instrument_keys`는 성과명 아님(GREEN).
- **dataclass 계열 집합-드리프트 canary 신설(MINOR-N3)**: M15(`_SEALED_MODELS`)는 pydantic `FrozenModel`만
  감시하고 dataclass 계열(이제 `BacktestRun`+신규 run 타입 = 2개)은 **감지기 0**이다. 신규 canary:
  `vars(tos.backtest)`에서 `dataclasses.is_dataclass` ∧ `closes_no_ev` 보유 타입 전수 == 명시 목록.
  M15 GREEN 판정은 정확하나 이 공백을 침묵 드롭하지 않는다.
- **halt의 lane 간 파급(What's Missing)**: `core.run`은 halt에 멈추지 않고 이벤트별 `EventResult`를
  산출(core.py:253-262)·드라이버가 수집(driver.py:279-302). ⇒ **심볼 A의 halt(VECTOR·capacity deny 등)는
  A 이벤트의 HaltRecord만 낳고 B의 후속 이벤트 처리를 죽이지 않는다**(이벤트 독립). §5-T4 격리에 포함.
- **다심볼 trace 변형·digest**: 신규 함수가 `instrument_keys`를 emit(oracle 스코프 여전히
  STRUCTURAL_WIRING_AGREEMENT_ONLY·results.py:116). `trace_digest`는 `BacktestRun` 타입 고정
  (results.py:127)이므로 **다심볼용 변형 함수 신규 추가**(기존 함수 무저촉·M19 JSON-native 보존). 신규
  `trace_digest` 변형은 **기존 대칭 시그니처 `(run, *, scheme)`**(results.py:127)를 유지한다.

### 3.6 다심볼 입력 계약 (∅ 양방향·comparability·MJ-8)

- **입력 = `Mapping[InstrumentKey, BarStream]`**. 각 lane 스트림은 기존 `validate_bar_stream`
  (bars.py:110-148)으로 개별 검증. `Bar`는 instrument 미탑재(bars.py:44-68)이므로 심볼 귀속은 mapping 키.
- **∅ 양방향(mapping 층위 승격·What's Missing)**: `None` mapping → **fail-closed**(missing);
  `{}` 빈 mapping → **defined empty 다심볼 run**(0 lane·0 event·`()` 스트림과 동형); lane의 `None`
  스트림 → **fail-closed**(per-lane validate); lane의 `()` 스트림 → **defined empty lane**. 단일-심볼
  ∅ 판정(bars.py:126-131)을 mapping 층위로 승격. **`{}` run도 주입 `continuity_id`를 유지**한다 —
  `WiringTrace`가 공백 continuity_id를 거부하므로(records.py:234-238) 0-lane run의 trace도 concrete
  continuity_id(드라이버 주입)를 싣는다.
- **comparability = caller 규율(MJ-8 정직 서술)**: `timestamp_coordinate`는 opaque 주입 정수
  (bars.py:9-13)라 **심볼 간 비교 가능성의 구조 술어가 없다**. 헬퍼가 **강제 가능한 것**은 (i) lane별
  strictly-increasing 재사용 + (ii) 병합 결과 non-decreasing 전역 순서(§3.3·§5-T6)뿐. **"심볼 간 단일
  비교 가능 시간 좌표계"는 caller 보증**이며 검출 불가 잔여 리스크로 §7-7에 이연 등재(§9 오약속 정정).

---

## 4. committed canary 전수 목록 + 처분 (MJ-5 census 이행 포함)

**범례**: GREEN=무영향·WIDEN=additive 확대(canary 갱신)·EXTEND=신규 심볼까지 census 확대 의무·
FLIP=의도된 loud 실패·LOCKSTEP=본문 GREEN이나 서술 갱신·REGREP=구현 재실측. **FLIP 0**.

| # | canary(file:line) | 처분 | 근거 |
|---|---|---|---|
| **M1** VECTOR 무진행·기록 | `test_engine_pipeline.py:222-236` | **GREEN**(FLIP 아님) | §1.5 |
| **M2** 전략 2스코프 거부 | `test_engine_dispatch.py:100-111` | **GREEN** | admission 무변경 |
| **M3** wildcard 스코프 거부 | `test_engine_dispatch.py:83-98` | **GREEN** | admission.py:212-217 |
| **M4** 타 instrument event/capsule 무평가 | `test_engine_dispatch.py:124-135·164-183` | **GREEN + EXTEND** | 기존 GREEN·신규 N-entry 격리(§5-T4) |
| **M5** MISSING vs EXPLICIT_EMPTY | `test_engine_dispatch.py:136-163` | **GREEN** | dispatch 무변경(MINOR-3 범위 정정) |
| **M6** AMBIGUOUS 수용·REVERSED만 거부 | `test_engine_event_vocabulary.py:207-229` | **GREEN** | §1.2 — 단일 continuity 교차-심볼 AMBIGUOUS 불발생 |
| **M7** 전역 단일 `_last_reference` 서술 | `test_backtest_ordering.py:1-18`(core.py:246/280/301 인용) | **GREEN(LOCKSTEP 불요)** | **분기 A는 core.py:246/280/301 무변경 → 세 불릿 문자 그대로 참**(아래 정직 서술) |
| **M8** 카운터 reset 불가·연속 실행 전진 | `test_backtest_ordering.py:80-87·317-332` | **GREEN** | 단일 카운터·reset 없음(§3.4·MINOR-3 정정) |
| **M9** 무명 continuity 거부 | `test_backtest_ordering.py:99-102` | **GREEN** | 단일 명명 continuity 재사용 |
| **M10** trace 좌표 순서==처리 순서·등가 좌표 unconstructable | `test_backtest_ordering.py:257-315` | **GREEN(+EXTEND)** | 단일 카운터 `native==yield` 유지·전역 유니크 좌표(§5-T5). 분기 B1였다면 FLIP/재정의(MINOR-3 정정) |
| **M11** 엔진 패키지 docstring 정직 문구 | `test_engine_package.py:87-104` | **GREEN** | 코어 무변경 |
| **M12** backtest import-closure + submodule drift + core typing-only | `test_backtest_import_closure.py:328-336·562-576·607-` | **GREEN(구속)** | 신규 .py 0·기존 submodule 배치·core typing-only 유지 |
| **M13** ledger release/free/clear/reset 부재 | `test_slice_gaps.py:480-495`·state.py:22·175-176 | **GREEN(불가침)** | 다심볼 무저촉·release 발명 금지 |
| **M14** `outstanding_consumed_magnitude` 정직 스코프=1엔트리 | state.py:178-182 | **GREEN** | 다심볼 = per-scope 독립·multi-leg 아님 |
| **M15** `_SEALED_MODELS` 집합 잠금(pydantic FrozenModel export) | `test_backtest_result_surface.py:92-109` | **GREEN(판정 산물)** | **신규 run 타입 = frozen *dataclass*라 FrozenModel 아님 → 미발화.** pydantic이었다면 WIDEN(§3.5 판정이 회피) |
| **M16** `BacktestRun` 성과-필드/closes_no_ev census | `test_backtest_result_surface.py:70-89·112-117` | **EXTEND** | 신규 run 타입을 census에 추가·`seal_performance_surface` 실행·closes_no_ev 비-파라미터 + **dataclass 계열 집합-드리프트 canary 신설**(N3·§3.5) |
| **M17** 드라이버 core-replacement 경로 부재 | `test_backtest_single_core.py:143-152` | **EXTEND** | 신규 드라이버도 set_core/rebind/reset/… 미노출(§3.1 게이트) |
| **M18** AST 스윕(EngineCore/Ledger/Registry 구성 0) | `test_backtest_single_core.py:111-141` | **GREEN(구속)** | 신규 드라이버가 코어/ledger/registry 미구성·주입만(§3.2 "단일 코어 재사용"의 실제 강제자) |
| **M19** 시나리오 digest·fill_records 재현·JSON-native | `test_backtest_replay.py:40-49·52-59·125` | **EXTEND** | 다심볼 "동일 입력 2회 → 동일 trace_document/digest/fill_records" 신규(§5-T5)·기존 무저촉(MJ-4 게이트) |
| **M20** harness vars() 스윕(engine/sibling mutation 심볼 0) | `test_backtest_import_closure.py:579-604` | **GREEN(구속)** | 신규 드라이버가 run_commitment_flow/ProvisionalReservationLedger/apply_egress_result 등 미명명 |
| **P1** `pipeline.py:16·:335` "later multi-symbol cycle" 산문 | 소스 산문(테스트 미단언) | **LOCKSTEP 불요** | **어떤 canary도 미단언(전수 grep)**·§1.5로 여전히 정직. 구현 시 산문 갱신은 REGREP(§6) |

**M7 처분의 정직 서술(구속·잠정 프레이밍과의 차이 명기·판정 유지)**: 오케스트레이터/서베이는 M7을
"docstring stale prose가 되는 lockstep 대상"으로 잠정 프레이밍했으나 그것은 **per-scope 전환(분기 B)
전제**였다. 본 계약은 분기 A 채택으로 **core.py:246/280/301을 수정하지 않으므로** M7 docstring 세
불릿("core holds **one** global `_last_reference` (core.py:246)"·"compares every incoming event
against it (core.py:280)"·"updates it for **every** non-REVERSED event (core.py:301)")이 **전부 문자
그대로 참 유지 → M7 = GREEN·LOCKSTEP 불요**. 비평이 실측 재확인(세 불릿 문자 그대로 참). 분기 B였다면
LOCKSTEP 대상이었음을 침묵 드롭 없이 명기(§1.3 결함 2).

**다심볼 capacity 서사(What's Missing·M13/M14 인접)**: `admits_new_exposure`(state.py:195-209)는
**per-scope 상한**(bound = `max_unresolved_send_per_scope`)이라, **전역 동시 노출 상한의 부재가 정본**이다
— 각 스코프가 독립적으로 자기 상한까지 허용(RFC-003 §9 atomic unit). 포트폴리오-레벨 노출 상한은 *다른*
개념(포트폴리오 리스크)이며 이연(§7-3 인접).

**터치 표면 직접 재-grep 대상(§6 게이트)**: `backtest/driver.py`·`results.py`·`records.py`·`bars.py`와
`test_backtest_*`의 committed canary 전수. M15-M20은 census 실측 완료(2026-08-06)·구현 시점 재확인.

---

## 5. 테스트 계획 + 뮤테이션 지정 (저작 증거·acceptance 아님)

닫는 EV 0 → 저작 증거(RFC-010 §6). **최소 지정(구속)**:

- **T1 — 스트림 모델 대조(문서화 테스트·순수 vocabulary·뮤테이션 프레임 제외·MJ-3)**: `ordering_admission`/
  `compare_order` 위에서 §1.1 실행. (a) 단일 continuity: A@native5 → B@native6 → A@native3 → **REVERSED**.
  (b) 심볼별 continuity: A@contA-5 → B@contB-6 → A@contA-3 → 중간 B 덮어씀 → **AMBIGUOUS**(fail-open)
  실증. **모델 대조 문서화**로 존치하되, T1은 드라이버 뮤테이션을 만나지 않으므로 뮤테이션 프레임에서
  제외한다.
- **T2 — 필수 뮤테이션(MJ-3 재지정·드라이버 표면)**:
  - **뮤턴트 A = lane별 continuity 배정** → **killing test = 다심볼 trace 전 entry `ordering_admission
    is MONOTONE`**(선례 `test_backtest_ordering.py:251-253`). 단일 continuity면 cross-lane 인접 쌍이
    MONOTONE; lane별 continuity면 AMBIGUOUS로 나타나 KILLED. **역행 없이 관측되는 A ⊋ B의 witness**(§1.2).
  - **뮤턴트 B = lane별 native 카운터** → **killing test = T5의 `source_native_sequence == yield_sequence`**
    (`test_backtest_ordering.py:267`). lane별 카운터면 등식 파괴 → KILLED.
- **T3 — per-scope at-most-one 독립성**: A·B 등록·A saturate(outstanding) → B tick 여전히 admitted.
  **뮤테이션**: ledger 키 per-scope→전역 → B deny → KILLED(state.py:137 회귀 잠금).
- **T4 — N-entry 디스패치·halt 격리(M4 확장·What's Missing)**: A-전략·B-전략 등록. A-tick → A만 평가.
  A가 halt(예: capacity deny)해도 B 후속 tick 정상 처리(halt 격리·§3.5). **뮤테이션**: 키 무관 전
  entries 실행 → KILLED.
- **T5 — 다심볼 trace 단일 total order·byte-identical(M10·M19 확장)**: N심볼 병합 실행 →
  `entry.reference.source_native_sequence == entry.yield_sequence` 전 entry·`yield_sequence` 전역
  유니크·오름차순. **동일 입력 2회 → 동일 `trace_document`/`trace_digest` *및* 동일 `fill_records` 튜플**
  (MJ-6·선례 `test_backtest_replay.py:52-59`). **뮤테이션**: 병합 tie-break 비결정(dict 순서) → 2회
  digest/fill_records 불일치 → KILLED.
  - **fill_records 순서 판별 단언(MAJOR-N2)**: `fill_records` 순서 == 동일 run `trace` 내 대응
    EGRESS_RESULT entry의 `yield_sequence` 오름차순(`LocalFillRecord.attempt_id` ↔ `TraceEntry.attempt_id`
    조인·`egress_result_kind` 보유 entry 한정). **뮤테이션 = lane-concat**(끝에서 lane별 concat) → 순서가
    lane-그룹으로 갈려 조인 불일치 → **KILLED**(2회 재현만으로는 안 잡히는 결함·v1.0 MJ-3 클래스). **조인
    스코프 한정(경계)**: 정산 완결 fill(대응 EGRESS_RESULT entry 보유)만. `unsettled_fill_records`
    (result_kind None·EGRESS_RESULT 부재·records.py:126)는 조인 밖 — 순서 계약은 lane iteration
    (instrument_key 사전순)×intra-lane pending 순서로 별도 결정(§3.5).
- **T6 — 병합 결정성·non-decreasing·look-ahead 무저촉(MJ-8 (ii))**: 동일 timestamp 두 심볼 →
  instrument_key 사전순 yield. **병합 산출 `timestamp_coordinate` non-decreasing 단언**. converter가
  자기 lane 현재 bar로만 tick 구성(prefix-bounded 회귀).
- **T10 — fill 심볼 귀속(C1·CRITICAL 봉인)**: N lane 실행 후 **전 `LocalFillRecord.instrument_key` ==
  산출 lane 키**. **뮤테이션 = 단일 공유 fill model 전환**(현재 lane demux 제거) → 교차-심볼 정산 오염
  (한 키 스탬프 + bar_index 교차 매칭) → KILLED. 이것이 §3.2 단일 Transmit 슬롯 demux의 실행 가능
  증거다.
- **T7 — VECTOR 무저촉(M1 회귀)**: 다심볼 배선 하에서도 `PortfolioVector` → `VECTOR_OUTCOME_UNSUPPORTED`.
- **T8 — additive 회귀**: 단일-심볼 `BacktestDriver`/`BacktestRun` 전 기존 테스트 GREEN·backtest
  import-closure/submodule-drift GREEN·엔진 전 테스트 GREEN(코어 무변경)·**MJ-4 추출 후 기존 시나리오
  digest 불변(M19)**.
- **T9 — 라이브 의무 관측(선택·정직)**: 코어에 두 continuity 직접 투입 → 전역 슬롯 conflate 실증(T1(b)
  동형·엔진 단위). FORWARD-OBLIGATION-MS1(§1.4)의 실체를 관측으로 남김(권장·생략 가능).

**property test 타깃**: 단일 continuity 하 임의 N심볼·임의 인터리브에 (i) 인접 admitted 쌍 항상
same-continuity·AMBIGUOUS 0, (ii) 좌표 total order = 처리 순서. hypothesis=확률 검출기이므로 결정론
회귀는 영속 canary(T2·T5·T10)로 고정.

---

## 6. REGREP 게이트 + 신규 .py 0 규율 (구현 게이트·구속)

1. **터치 표면 committed canary 전수-grep**(#35 MAJOR-1 선례). §4 M1-M20 + 아래 산문 표면을 구현 시점
   재실측·역방향 canary 사냥.
2. **신규 .py 0**: `test_backtest_import_closure.py:562-576`(drift)·M18 AST 스윕이 신규 파일/코어 구성에
   loud FAIL. 기존 submodule에만·core typing-only 유지.
3. **인용 재grep**: 설계 5편 line 인용은 구현 커밋 후 드리프트 가능. 본 계약 인용은 2026-08-05/06 기준.
4. **산문 lockstep 재grep 대상(MINOR-4·5)**: (i) `pipeline.py:16·:335` "later multi-symbol cycle"(P1·
   구현 시 산문 갱신 검토), (ii) **`converter.py:18`(전역 `_last_reference` 산문)·`:82`("single dispatch
   scope")·`driver.py:8`·:186-188("single scope")** — 다심볼 도입 시 이 산문들의 정직성 재확인(단일-심볼
   드라이버 존치 시 그대로 참·다심볼 신규 심볼은 자기 서술).
5. **필드-집합 잠금 REGREP**: `results.py`/`records.py`의 `BacktestRun`·`WiringTrace` 필드 잠금 유무
   (M16 census 외 추가 잠금)·`backtest.__all__` dedup/phantom. 잠금 충돌 시 #32/WDR 선례("구현이 더
   충실하면 canary 무력화 아닌 설계-정합") 판정.

---

## 7. not-multi-symbol / 명시 이연 (닫지 않음·접합 위치만 표기)

1. **심볼별 continuity + per-scope last-reference(분기 B)** — §1.3 완전 설계. FORWARD-OBLIGATION-MS1
   충족 불가 시 **B2 하이브리드(per-symbol continuity + 전역 native + `source_continuity_id` per-scope
   슬롯) 권장 봉인 설계**(M10/replay 보존). 접합점: `engine/core.py:246·280·301`(dict 전환).
   **B3 옵션**(causal chain 재구성·A로의 비싼 수렴)도 인계하나, 그 라이브 유용성은 **브로커가 이벤트 간
   인과 링크를 제공하는지**(= P0-2 Broker Capability Profile 소관)에 달려 있다.
2. **`PortfolioVector`/VECTOR 접기/all-or-none**(1전략 N심볼) — OUT-5·`pipeline.py:329-340`. 다심볼의
   *다른* 축·미착수.
3. **완전 net-position ledger(multi-leg·평단)·포트폴리오-레벨 노출 상한** — #35 §10-2·state.py:178-182.
   per-scope 독립 유지.
4. **실 RCL release·round-trip·reduce-only** — RFC-002 §9.1:557·M13. 무저촉.
5. **실 KIS transport·라이브 다심볼 ingest 어댑터(단일-continuity 시퀀서)** — #34 §5.1·P0-2.
   FORWARD-OBLIGATION-MS1이 그 어댑터 계약을 명세하나 구현·비준은 이연(§1.4·MJ-7).
6. **다심볼 numeric/차등 오라클** — #33 §6.2(D-E2 gated). 본 계약은 구조 배선만.
7. **다심볼 입력의 심볼 간 시간 좌표 comparability 강제(MJ-8 잔여 리스크)** — 구조 술어 부재·caller
   규율·검출 불가. 헬퍼는 lane별 단조 + 병합 non-decreasing만 강제(§3.6).
8. **`GatewayResultReinjector`(#35 GAP-1)의 다심볼 사용** — 명시 out-of-scope(retained 전량 drain이
   심볼 귀속 붕괴 소지·후속 판정). 본 계약 lane = `DeterministicFillModel` 한정(§3.2 판정).
9. **per-lane `scenario_id`** — 다심볼 `ScenarioId` vocabulary 부재·소비자 부재. run-level 단일 유지(§3.5).
10. **정식 EV-L2 PASS** — P0-1 bounds·독립 리뷰어·독립 서명. 본 산출 provisional·닫는 EV 0.

---

## 8. 리뷰어 공격 지점 (선제 반론)

1. **"단일 continuity 선택이 일거리가 적어서 아닌가·M10/replay 축이 과대."** — 반론: 최강 축은
   **검출력 포함관계 A ⊋ B**(§1.3)이며 native-branch 변종(B1·B2)은 cross-lane 인접 쌍이
   `same_continuity=False`로 AMBIGUOUS(검출 비활성)이다. **유일 회피 B3(causal chain 재구성)는 A로의
   비싼 우회 수렴**(좌표 2벌·검출 동치·결함 2·4·5 적용·MAJOR-N1). M10 파괴·replay 약화 축은 **B1 약변종
   한정**이며 B2는 회피하므로 "B 특정 변종 한정"으로 강등(MJ-2). A ⊋ B + 코어 무변경 + fail-open 미도입
   (결함 4) + 근거 견고(결함 5)가 축이다. §5-T2가 A의 우위를 MONOTONE/AMBIGUOUS로 관측(역행 없이·비공허).
2. **"라이브 함의 누락·의무 비준상태 과장."** — 반론: §1.4가 **엔진 코어 계약**으로 처리한다.
   FORWARD-OBLIGATION-MS1은 "이미 비준된 원칙"이 아니라 **#33 §3.4 좌표 원칙을 라이브 ingest 경계로
   처음 확장하는 신규 전방 의무·라이브 비준물 부재·라이브 다심볼 사이클의 게이트로 승격 필요**로 정직
   서술했다(MJ-7). #31 continuity는 전부 snapshot provenance(양방향 grep). D2 가드는 B2 contingency를
   foreclose하므로 기각(판정 유지).
3. **"M6(AMBIGUOUS 수용)과 충돌·검출 공백."** — 반론: 그 공백은 심볼별 continuity(분기 B)에서만
   (서베이 :309). 분기 A는 교차-심볼 same-continuity라 AMBIGUOUS 불발생·M6 무저촉·과잉거부(발명 (d)) 안 함.
4. **"byte-identical replay가 다심볼에서 깨진다."** — 반론: §1.6·§5-T5. 단일 카운터 total order + 병합
   `(timestamp, account, instrument)` 순수 함수 → trace_digest **및 fill_records** 재현(MJ-6). 비결정
   병합 뮤테이션 KILLED.
5. **"per-scope를 안 만들면 NIT 미closure."** — 반론: NIT는 "다심볼 시점 해소할 질문"이지 "per-scope가
   정답"이 아니다(§0.2·INDEX:25). 해소 결과는 "채택 모델 하 per-scope는 증명상 잉여"(§1.2)·서베이 :294·
   :388 사전 인가. 봉인 설계(B2)는 §1.3에 완전 보존·인계.
6. **"단일 Transmit 슬롯으로 N lane를 어떻게 구분하나(C1)."** — 반론: **못 구분한다·구분하면 안 된다** —
   `AttemptRequest` 무스코프(records.py:347-351)라 attempt demux 불가. 대신 **코어의 동기·단일스레드
   완결(core.py:1-3)**로 "현재 처리 lane"에 demux한다(§3.2). 이 완결 보장이 신규 load-bearing 불변식.
   단일 공유 fill model은 교차 정산 오염을 조용히 출하하므로 금지(§5-T10 KILLED). lane별
   `DeterministicFillModel`(각자 instrument_key·fills.py:372)이 정본.
7. **"다심볼 = N per-instrument인데 VECTOR 미개방."** — 반론: N per-instrument가 다심볼 충족(§1.5·
   registry.py:59). VECTOR(1전략 N심볼)는 OUT-5의 *다른* 축·발명 (f)·스코프 밖. `pipeline.py:335` 사유
   문자열 정직 유지.
8. **"병합 frontier가 look-ahead."** — 반론: §3.3 — frontier는 lane당 ≤1 pending bar의 순서 metadata
   (timestamp)뿐·미래 bar 결정 미투입·converter prefix-bounded 유지. BTE-INV-004(#33 :368 원문) 무저촉.
9. **"단일-심볼 드라이버를 리팩터하면 회귀 위험(MJ-4)."** — 반론: 순수 리팩터(동작 동일)·공개 표면 불변·
   게이트 = `tos/tests/backtest/` 전건 GREEN + 시나리오 digest 불변(`test_backtest_replay.py:40-49`·M19).
   digest가 바뀌면 리팩터 아님·되돌린다.

---

## 9. 미결·리스크 (구현 게이트)

- **REGREP(§6)**: `results.py`/`records.py` 필드 잠금(M16 census 외)·`backtest.__all__` phantom/dedup —
  구현 재grep. 발견 시 additive 신규 타입(§3.5)으로 우회 or 설계-정합.
- **comparability 잔여 리스크(MJ-8 정직 정정)**: v1.0 §9가 "비교 불가 좌표계 → fail-closed"를 약속했으나
  `timestamp_coordinate` opaque(bars.py:9-13)라 **구조 강제 불가**. 헬퍼는 lane별 단조 + 병합
  non-decreasing만 강제(§3.6·§5-T6). 심볼 간 단일 시간 좌표계는 **caller 규율·검출 불가 잔여 리스크**로
  §7-7 이연 등재.
- **DRY 추출과 단일-심볼 canary(MJ-4)**: §3.1 게이트(digest 불변)로 봉인·추출 후 단일-심볼 전 테스트
  GREEN 재확인.
- **FORWARD-OBLIGATION-MS1 미이행 가시성**: 라이브 어댑터 이연(§7-5)이라 현재 코드에 미강제(T9 관측만).
  실 라이브 다심볼 사이클이 게이트로 승격 필요(§1.4 계약 확정).
- **`scenario_id` run-level 판정의 미래 압력**: 다심볼 시나리오 vocabulary가 도입되면 per-lane 승격
  재검토(§7-9).

---

## 10. 명명·번호 + 오케스트레이터 판정 기재

- **문서 번호 #37** — 이연 ③ 다심볼 closure(서베이 :457). 비준 5설계 #31~#35 다심볼 확장.
- **신규 심볼(전부 기존 submodule)**: `backtest/driver.py`에 다심볼 드라이버(제안 `MultiSymbolBacktestDriver`·
  단일 공유 `YieldOrderCounter`·N lane·`Transmit` 구현·현재 lane demux); `backtest/bars.py`에 결정론적
  병합/검증 헬퍼; `backtest/results.py`에 다심볼 run 타입(제안 `MultiSymbolBacktestRun`·**frozen
  dataclass**·`instrument_keys` 복수·`closes_no_ev=True` 비-파라미터) + 다심볼 trace 변형(**신규 함수**).
  명명은 제안·`__all__` phantom/drift/dedup canary 구속(negative-grep 재확인).
- **엔진 코어 신규 심볼 0·엔진 코어 변경 0** — 헤드라인.
- **신규 패키지 0**.
- **오케스트레이터 판정 4건 기재(비평 Ambiguity 해소)**: ① 신규 run 타입 = **frozen dataclass**(BacktestRun
  대칭·M15 회피·M16 census 확대)·근거 §3.5; ② trace 변형 = **신규 함수**(해석 A·기존 무저촉·§3.5); ③
  병합/검증 헬퍼 배치 = **`backtest/bars.py` 확정**(§3.1); ④ lane `EgressResultSource` = **`DeterministicFillModel`
  한정**·`GatewayResultReinjector` 다심볼 out-of-scope(§3.2·§7-8).

---

## 11. Definition of Done (이행 판정 조건·MINOR-6)

구현 완료 = 아래 전건:
1. **신규 테스트 수 = 서베이 추정 20~35건**(:393)·**지표이지 게이트 아님**(MINOR-N5). 이행 게이트는
   DoD-2~6. §5 T1-T10 + property + ∅ 양방향 + M16/M17/M19 EXTEND 커버.
2. **§5 뮤테이션 전건 KILLED**: T2(뮤턴트 A/B)·T3·T4·T5·T10.
3. **canary GREEN**: §4 M1-M20 + P1 — FLIP 0(전건 GREEN/EXTEND/GREEN-구속). M16/M17/M19 EXTEND는 신규
   심볼까지 census 확대 완료.
4. **MJ-4 게이트**: `tos/tests/backtest/` 전건 GREEN + 기존 시나리오 `trace_digest` 불변(M19).
5. **additive 회귀(T8)**: 엔진·단일-심볼 backtest 전 기존 테스트 GREEN(파괴 0)·신규 .py 0·엔진 코어 변경 0.
6. **REGREP(§6) 이행**: 필드 잠금·산문 lockstep·인용 재grep 완료.

---

## 12. 개정 로그

### v1.2 (2026-08-06 — 독립 델타 재검증 REVISE 유지·신규 MAJOR 2·MINOR 3 전건 처분)

**코퍼스 규율 기록**: 두 신규 MAJOR는 **명시 채점 결함 클래스의 2차 재발**이다 — MAJOR-N1 = 전칭 주장
반례(§1.3 "회피 불가" → B3 반례로 교체), MAJOR-N2 = 뮤테이션-표면 부재(fill_records 명세가 어떤
관측으로도 강제 안 됨·v1.0 MJ-3 클래스 재발). **둘 다 v1.2에서 닫힘**(반례 명시형 전환·판별 단언 신설).

| finding | 처분 | 반영 위치 |
|---|---|---|
| **MAJOR-N1** §1.3/§8-1 "회피 불가" 전칭에 B3 반례 | **채택** | §1.3 A⊋B를 native-branch(B1·B2) 한정으로 정정 + B3(`causal_predecessor_ids`·_ordering.py:128-133·:72·driver.py:139-143 공백)를 "A로의 비싼 우회 수렴"으로 명시(검출 동치·좌표 2벌·결함 2·4·5); §8-1 동일; §7-1 B3 인계 옵션(라이브 유용성=브로커 인과 링크=P0-2) |
| **MAJOR-N2** fill_records "정산 순서 집계" 재구성 불가·미강제 | **채택** | §3.3/§3.5 "드라이버 정산 시점 순서 누적·사후 병합 불가(records.py:87-109 전역 순서 필드 부재·bar_index lane-지역)"로 교체; §5-T5 판별 단언 신설(fill_records 순서 ↔ EGRESS_RESULT yield_sequence·attempt_id 조인·lane-concat KILL)·조인 스코프=정산 완결 fill·unsettled 별도 순서 계약 |
| **MINOR-N3** dataclass 계열 감지기 공백 | 채택 | §3.5·§4-M16: `is_dataclass`∧`closes_no_ev` 집합-드리프트 canary 신설 |
| **MINOR-N4** 현재 lane 미설정 fail-closed 미명기 | 채택 | §3.2: `fills.py:441-446`→`TRANSMIT_RAISED`(sequencer.py:534-545) 상속·발명 아님 |
| **MINOR-N5** DoD 테스트 수를 게이트로 오독 소지 | 채택 | §11 DoD-1: 20~35=지표·게이트 아님·게이트는 DoD-2~6 |
| **기록** trace_digest 시그니처 | 기재 | §3.5: 기존 대칭 `(run, *, scheme)` 유지 |
| **기록** `{}` run continuity_id 출처 | 기재 | §3.6: `WiringTrace` 공백 거부(records.py:234-238)→주입 continuity_id |

### v1.1 (2026-08-06 — 독립 비평 REVISE 전건 처분)

| finding | 처분 | 반영 위치 |
|---|---|---|
| **C1** 단일 Transmit 슬롯 vs N lane demux 미지정 | **채택** | §3.2 — 드라이버가 Transmit 구현·현재 lane demux·근거=AttemptRequest 무스코프(records.py:347-351 실측)+동기 완결 불변식(core.py:1-3, **신규 load-bearing**); §5-T10 추가(공유 fill model→교차 정산 KILLED); §0.4·§8-6 |
| **MJ-1** §1.2-3 도달불가 상태 논거 | **채택** | §1.2 2문장 교체: 역행 구성 불가→per-scope 잉여 / 심볼별 논리 역행은 입력 계약(per-lane validate_bar_stream strictly-increasing bars.py:110-148 + 병합 순서 보존)이 봉인 |
| **MJ-2** 분기 B 최약체 기각·하이브리드 누락 | **채택** | §1.3 B2 하이브리드 3변종 명기(M10 보존 실측)·기각 최강 축을 **A ⊋ B 검출력 포함관계**로 재편·결함 1·3을 B1 한정 강등·§8-1 정정·§7-1 contingency를 B2 권장으로 재지정 |
| **MJ-3** T2 뮤테이션 자기참조 | **채택** | §5-T2 재지정: 뮤턴트 A(lane별 continuity)→killing=trace 전 entry MONOTONE(`test_backtest_ordering.py:251-253`)·뮤턴트 B(lane별 카운터)→killing=T5 native==yield; T1은 문서화 테스트로 존치·프레임 제외 |
| **MJ-4** §3.1 "무수정" vs "추출" 모순 | **채택(추출 의무화·판정)** | §3.1 순수 리팩터 추출 명문화·공개 표면/M17 불변·게이트=backtest 전건 GREEN + 시나리오 digest 불변(M19); §8-9·§11-4 |
| **MJ-5** 자기 터치 표면 canary 사냥 미이행 | **채택** | §4에 M15-M20 추가(census 실측 2026-08-06): M15 GREEN(dataclass 판정)·M16 EXTEND·M17 EXTEND·M18 GREEN구속·M19 EXTEND·M20 GREEN구속; §3.5/§9 "유무 미확인" 확정 서술로 교체 |
| **MJ-6** run 아티팩트 미지정 | **채택** | §3.5 11필드 처분표(집계/lane별/carried)·frozen dataclass·fill_records 병합 순서(§3.3)·trace 변형 신규 함수·`trace_digest` BacktestRun 고정(results.py:127); §5-T5 fill_records 재현 추가 |
| **MJ-7** FORWARD-OBLIGATION 비준상태 과장 | **채택** | §1.4·§8-2 문안 교체: "이미 비준 원칙 연장"→"#33 §3.4 좌표 원칙을 라이브 ingest 경계로 처음 확장하는 신규 전방 의무·라이브 비준물 부재·게이트 승격 필요"; D2 기각 유지 |
| **MJ-8** §9 fail-closed 약속 이행 불가 | **채택** | §3.6·§9 정직 재서술: comparability=caller 규율(검출 불가 잔여 리스크 §7-7)·헬퍼 강제 가능=lane별 단조+병합 non-decreasing(§5-T6 추가) |
| **MINOR-1** `_last_reference` grep 전사 | 채택 | §0.1-1: src 5행(driver.py:8·converter.py:18 산문 포함)·상태는 코어 3행 |
| **MINOR-2** BTE-INV-004 축소 서술 | 채택 | §3.3: instrument-스코프 축소 제거·#33 :368 원문("every indicator and input SHALL be bounded by the current context timestamp") |
| **MINOR-3** 행 범위 off-by-≤2 | 채택 | §4: M5 :136-163·M10 :257-315·M8 :80-87·317-332 정정 |
| **MINOR-4** pipeline 산문 LOCKSTEP 판정 | 채택 | §4 P1 행 추가(LOCKSTEP 불요·미단언 근거)·§6-4 REGREP |
| **MINOR-5** converter 산문 REGREP 누락 | 채택 | §6-4에 converter.py:18·:82·driver.py:8·:186-188 추가 |
| **MINOR-6** DoD 부재 | 채택 | §11 신설(테스트 20~35·뮤테이션·canary·게이트) |
| **Missing** halt lane 파급 | 채택 | §3.5·§5-T4(심볼 A halt가 B 미살해·core.py 이벤트 독립) |
| **Missing** 입력 Mapping ∅ 양방향 | 채택 | §3.6(None fail-closed·{} defined-empty·lane None/() 판정) |
| **Missing** scenario_id lane 귀속 | 채택 | §3.5 run-level 단일·§7-9 이연 |
| **Missing** 다심볼 capacity 서사 | 채택 | §4 M13/M14 인접(per-scope 상한·전역 상한 부재 정본) |
| **Missing** `_backtest_fixtures.py` vs 신규 .py 0 | 채택 | §3.1(테스트 fixture는 submodule-drift 무관) |
| **판정** run 타입=frozen dataclass·trace=신규 함수·헬퍼=bars.py·lane=DeterministicFillModel | 기재 | §3.1·§3.2·§3.5·§10 |

<!-- 저작 증거·닫는 EV 0. 비준 전 파이프라인: 1차 심사 → 독립 비평(완료·REVISE) → 개정(v1.1) →
운영자 위임 자동 비준(ADR-002 Part-2/3 연장) → 구현 → 적대적 코드 리뷰. 델타 재검증 후속. -->
