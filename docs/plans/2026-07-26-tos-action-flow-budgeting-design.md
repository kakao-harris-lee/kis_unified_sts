# 설계 문서 #16 — Action-Flow Budgeting·Retry-Storm Containment·Protective-Traffic Preservation 계약 (2026-07-26, v1.2)

> **문서 번호 규약 각주(v1.1 개번)**: 본 문서는 v1.0에서 "#15"였으나 세션 A가 #15를 ADR-002-023 IAP 설계에 선점
> (비준 커밋 `ff5a708e`)하여 v1.1에서 **#16**으로 개번했다. 시리즈 순번은 착수 순서가 아니라 비준·선점 순서를 따른다.

- **대상 ADR**: ADR-002-022 — Action-Flow Budgeting, Retry-Storm Containment, and Protective-Traffic
  Preservation ("AFG"). 693줄. Status **Proposed**.
- **자체 시리즈(실측·앵커)**: **AFG-INV-001..014**(§6 line 155–209, 14종 — grep `^### AFG-INV-` = 14)·
  **AFG-AC-001..012**(§27 line 583–631, 12종 — grep `^### AFG-AC-` = 12)·**AFG-EV-001..012**(EVIDENCE-REGISTER-002
  line 288–299, 12행; VER-002-001 §266–277 line 2239–2321). **새 시리즈 창작 금지**.
- **Depends On(ADR line 9)**: RFC-000 constitutional safe state; RFC-001 SAFE-003/004/010–015/020/021/024/025/
  030–035/040–044/046/048/050–052; **ADR-002-001 through ADR-002-021**(전부 비준·구현 완료).
- **시리즈 선례(동형 유지)**: 설계 #13(Aggregate Risk Projection, `tos.are`, v1.1)·#12(Safety Profile Governance,
  `tos.spg`, v1.1)·#11(Degraded-Mode Protective Capacity, `tos.protective`, v1.1). 본 계약은 **#13 ARE와 구조적으로
  가장 가깝다**(양자 모두 rcl `GrantDecisionRef`·`CapacityVector` 소비, produced-scalar decision seam, 5/7 EV
  분할).
- **비준 상태**: **2026-07-26 운영자 비준(v1.1) — 효력 발생**(v1.2 에라타 반영 후에도 **비준 효력 유지** — 아래
  §10.1 v1.2 항목 참조: ADR 원문 전사 누락 1건의 보수 방향 정정이며 계약 의미 변경·재비준 불요)("비준 진행" 명시 지시; 자동 비준 위임 경로 아님).
  경위: v1.0 → 오케스트레이터 1차 심사 통과 → 독립 비평 리뷰 **REVISE**(CRITICAL 1[C1 §10:276 방향 반전 전사]·
  MAJOR 9·MINOR 10·Gap 9, ~122 인용 전수 검증) → v1.1 전량 반영(저작자 1차 소스 재실측, 처방 반론 0) →
  오케스트레이터 스팟체크 통과(+잔존 인용 오귀속 1건 직접 정정). **§10.3 판단 지점 4건 승인**: ① decision/reserve
  seam decoupled + `ActionFlowVector`=rcl `CapacityVector` REUSE(afg→rcl, 시리즈 6번째 sibling edge) ②
  `ActionFlowPermit` afg-local 스키마 ③ spg action-flow 전용 step 불요·이연 ④ VP-002 bounds는 Bounds-Approver
  Phase-0 이관. 효력: `tos/src/tos/afg/` Phase 1(EV-L1) 순수·비전송·fail-closed 모델 + property test 착수 승인.
  본 문서는 여전히 어떤 AFG-EV·ADR acceptance·restricted-live·production도 승인하지 않는다(§0.2).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-022 조항별 **Phase 1(EV-L1) 도달성 경계**(§1). **core(L1 슬라이스) / predicate-only / not-Phase-1
   (형제 소유·런타임 이연) 3분류.** **결정적 사실(register 실측·정정)**: `AFG-EV` 12행 중 **5행(001·002·004·007·
   008)이 register 최소 레벨에 `EV-L1` 슬라이스 보유**(#11/#13형 core tier). **orchestrator 사전 카운트 "L1
   슬라이스 6행"은 실측 결과 "5행"으로 정정**한다(EVIDENCE-REGISTER-002 `.md` line 288–299(=`.csv` line 257–268) 전수: 003·005·006·009·010·
   011·012는 최소 `EV-L2` — §1 표; VER-002-001 line 2255/2269/2276/2297/2304/2311/2318 재확인). **닫는 AFG-EV =
   0건**(L1 슬라이스 저작 ≠ EV closure: `/3`·`+Security`·`+Broker` 잔여). "**EV-L1-complete 주장 금지**". 이 정정은
   #13 ARE(사전 6→실측 5)와 **동일 패턴**이며 우연이 아니라 register가 storm-containment/broker-common-mode/
   security-bypass 계열을 최소 `EV-L2/L3`로 고정하기 때문이다.
2. **5-아티팩트 + value 데이터 모델**(§2, **core**): digest-bound `IndependentIdArtifact`인
   `ActionFlowPolicy`(§5.1/§8; **spg Safety Config Bundle member `ACTION_FLOW_POLICY` 실측** `spg/vocabulary.py:209`)·
   `ActionFlowStateSnapshot`(§5.3/§10; grants no permission)·`ActionFlowDecision`(§5.4/§13; GRANT/DENY/UNKNOWN·
   forward-only decision ref 생산)·`ActionFlowPermit`(§5.5/§13; single-use RCL commitment record — **NOT a
   Transmission Capability**) + value 모델 `ActionFlowVector`(§5.6, **rcl `CapacityVector` REUSE**)·`ActionCause`
   (§5.7 lineage)·`ActionAmplificationEnvelope`(§5.8)·`ProtectiveFlowReserveClaim`(§5.9, protective 분류 소비)·
   all-false `ActionFlowGovernorEffect`(§7/AFG-INV-011). 어휘: `ActionFlowResult`(GRANT/DENY/UNKNOWN — §1 line 15·
   §5.4 line 125 verbatim)·`ActionClassKind`(§9 line 258–266 9종 verbatim)·`ActionFlowScopeKind`(§10 line 274
   verbatim)·`ActionFlowDimensionKind`(§5.6 line 133 verbatim). Generation은 `tos.ordering` 좌표(§3.2, 별도 heavy
   아티팩트 아님 — ARE Aggregate Risk Generation 동형).
3. **complete-scope / no-local-headroom 중앙 불변식**(§4.1/§5.1, AFG-EV-001 substrate — ADR §10·AFG-INV-001):
   `scope_graph_complete(...) -> bool`. **모든 applicable shared scope 포함**(global..action-class, §10 line 274)
   ∧ **local counter·separate process·scheduler priority가 distributed headroom을 만들지 못함**(§10 line 278;
   rcl `producer_local_counter`/`scheduler_priority` "create **no** headroom" `records.py:127–128` 실측 동형).
   **두 보수 규칙 분리(C1 — 방향 반전 정정)**: (i) **unknown dependency/limit scope ⇒ smallest conservative
   containing scope로 확장**(§1 line 25 "expands to the smallest conservative containing scope"); (ii) **broker가
   documented scope를 incomplete/contradictory/stale/unverified하게 노출 ⇒ limit을 largest credible containing
   scope에 걸쳐 shared로 취급**(§10 line 276 "treated as shared across the largest credible containing scope" — 공유
   범위를 넓게 = 보수적). 두 규칙 모두 new normal risk 차단. `shared_limit_conservative` 술어로 실현(§5.1). 빈
   scope set ⇒ 보수적 UNKNOWN(§4.7 양방향).
4. **bounded-amplification / cause-lineage 중앙 불변식**(§4.2/§5.2, AFG-EV-002 substrate — ADR §11·AFG-INV-002):
   `amplification_bounded(...) -> bool` ∧ `cause_lineage_complete(...) -> bool`. **root cause + complete parent
   lineage 필수**; fan-out·depth·attempt·mutation·queue·elapsed-time·duplicate/redelivery/failover/reconnect/replay
   expansion 전부 유한 bound(§11 line 284–292); **duplicate event는 새 allowance 창조 안 함**(§11 line 294);
   **동일 cause의 concurrent consumer는 하나의 envelope 공유**(§11 line 294); **changed command = 새 action**(§11
   line 294). lineage missing/cyclic/forked-beyond-bound/inconsistent ⇒ `UNKNOWN`·contain(§11 line 296). 빈 lineage
   ⇒ UNKNOWN(§4.7).
5. **exact-binding / permit single-use 중앙 불변식**(§4.3/§5.3, AFG-EV-007 substrate — ADR §13·AFG-INV-003/004/005):
   `permit_single_use(...) -> bool` ∧ `atomic_economic_flow_coverage(...) -> ActionFlowResult`. **one decision·
   permit = one exact action identity/command/cause/lineage/scope/generation/vector** — patch/union/widen/transplant/
   replay 불가(AFG-INV-003 line 165); permit exact·single-use·consumed-or-quarantined(§13 line 342); **경제 vector와
   action-flow vector 둘 다 exclusive commit되거나 neither**(AFG-INV-005 line 173; §13 line 330 "commit both in one
   deterministic transaction or ... cannot leave a live-send-capable partial state"). None/missing/불완비 ⇒ no
   permit(§13 line 330). 원자 commit 실행 자체는 rcl 런타임(§13; 이연). 빈 vector ⇒ restrictive(§4.7).
6. **refill-not-manufactured / counter-integrity 중앙 불변식**(§4.4/§5.4, AFG-EV-008 substrate — ADR §18·**AFG-INV-
   004**(RCL-Only Budget Mutation, line 169 "replenishes")·**AFG-INV-007**(UNKNOWN Is Restrictive, line 181) 앵커
   — **INV-013는 "Stale Generations Are Fenced"(generation fencing, line 205)이지 refill 아님**, M6 정정; INV-013는
   별도 `generation_fenced` 술어(§5.4)): `refill_conservative(...) -> ActionFlowResult|bool`. **approved trustworthy-time + RCL committed history
   만이 replenish**(§18 line 404); wall-clock/clock-recovery/restart/broker-timestamp/newly-healthy-source가 headroom
   제조 못 함(§18 line 405); **negative age·future issue time·uncertainty·discontinuity·unknown continuity ⇒ clamp
   toward restriction, never refill**(§18 line 405); **cross-host/process monotonic 직접 subtract 금지**(§18 line
   403; time `MonotonicReading` "continuity subtraction is never performed" `elements.py:112` 실측 동형). time
   recovery ⇒ new Time Health Generation·revive 없음(§18 line 407). 빈 window/미확립 continuity ⇒ restrictive(§4.7).
7. **no-blind-retry 불변식**(§4.5/§6.1, AFG-EV-003 substrate — ADR §14·AFG-INV-008): `no_blind_retry(...) -> bool`.
   **missing ACK·timeout·reset·proxy fail·SDK exception·redirect·rate-limit response는 non-acceptance 증명 아님**
   (§14 line 350); attempt는 **potentially live 유지**; retry count·elapsed·backoff·repeated response가 UNKNOWN을
   known rejection으로 변환 못 함(§14 line 352); blind failover(session/endpoint/route/credential/broker/client-order-id)
   금지(§14 line 352). orthostate `TransmissionAttemptState.SENT_UNCONFIRMED`(`vocabulary.py:86`)를 좌표 소비하고,
   attempt-축의 positive 대응물은 `SEND_FAILED_PROVEN`(`:88`)이다(m4 정정: `no_potentially_live_proof is True`
   `predicates.py:461`은 `intent_transition_allowed`의 **Intent-축** 파라미터이므로 attempt-축 근거가 아니라 "`is
   True` 정규화 선례"로만 인용). 최소 `EV-L2/3+Broker`(broker idempotency 증명 잔여).
8. **cancel-ACK-not-FQP / oscillation-bounded 불변식**(§4.5/§6.2, AFG-EV-004 substrate — ADR §15·AFG-INV-009):
   `cancel_ack_not_final_quantity_proof(...) -> bool` ∧ `oscillation_bounded(...) -> bool`. **cancel ACK ≠ Final
   Quantity Proof**(§15 line 358; capacity release·replacement reuse·retry 정당화 안 함); original+replacement은
   worst credible overlap/late-fill/reversal/protection-gap 대비 covered(§15 line 358); cancel↔submit 무한 진동
   금지·budget reset 목적 새 cause 생성 금지(§15 line 360); reserve 부재 시 trapped exposure 기록·contain(§15 line
   362). orthostate `BrokerOrderState.{CANCELLED,UNKNOWN}` 좌표 소비. 최소 `EV-L1/3+Broker`(core L1 슬라이스이나
   broker 통합 잔여).
9. **AFG ↔ rcl/protective/spg/orthostate/brokercap/time/recon/are 경계(중심 아키텍처)**: AFG는 **sibling edge 1건
   (afg→rcl, `CapacityVector`+`aggregate_usage`/`effective_limit` REUSE만)**을 유지한다(§0.4c/§3.4; #8 orthostate→rcl·
   #13 are→rcl 선례 동형). AFG는 (i) rcl `GrantDecisionRef`(`authority.py:39–40` "Aggregate Risk / **Action Flow**
   decision reference" 실측)·all-false authority block·최종 action-flow `CapacityVector`를 **생산/REUSE**하고,
   (ii) protective `is_reserved_guarantee`(`predicates.py:129`)·`partition_lease_admissible`(`:460`)·bounded-retry
   `budget_remaining`(`:590–615`)의 **결과 bool/scalar를 주입 소비**하며, (iii) spg 활성 `ACTION_FLOW_POLICY`
   generation(`vocabulary.py:209`)·orthostate attempt/broker-order state·brokercap idempotency/rate-limit
   evidence·time validity·recon `ConservativeBound`를 **주입 소비**한다. **rcl `CapacityVector`만 import하고
   canonical/ordering/rcl 외 모든 현재·미래 tos 형제(현재 13개: protective/spg/orthostate/brokercap/time/recon/are/
   liveauth/authority/capsule/evidence/dsl + **ioc/iap 신규**, M9)는 미import** — produced-scalar/bool·주입 좌표로만
   참조. `tos.afg`는 `tos.canonical`·`tos.ordering`·`tos.rcl`(CapacityVector)만 import한다(§0.3). **PROMOTE 0건.
   sibling edge 1건(afg→rcl, rcl↛afg 실측 acyclic; **ioc→rcl 5번째 edge 실측** → afg→rcl은 6번째 후보).**
10. **fail-closed 규율 + named both-ways canary**(§4): unknown scope ⇒ 확장·차단; missing lineage ⇒ UNKNOWN;
    duplicate event ⇒ no new allowance; missing ACK ⇒ potentially live; cancel ACK ⇒ not FQP; expiry ⇒ future만
    제한(경제 effect 불변); recovery/reconnect/refill ⇒ non-revival·no auto re-arm; priority ⇒ not reserve;
    **빈 scope set·빈 dimension set·빈 required-scope·빈 amplification envelope·빈 lineage ⇒ 보수적 UNKNOWN/DENY**
    (∅-공허, §4.7 — **양방향** 명시). 각 가드에 both-ways canary. **truthy-sentinel 정규화**: `ActionFlowResult`
    소비 게이트는 `result is ActionFlowResult.GRANT`(identity)로만 통과 — `if result:`(StrEnum truthy 관통) 금지
    (#13 ARE UNKNOWN-truthy 교훈; orthostate `is True` 정규화 `predicates.py:461` 선례).
11. **property-test 하네스 타깃**(§7, §1 분류 정렬) + import-closure 검증(§7.1) + run manifest 7항목(§7.2) +
    fixture clean-vs-illegal 정합(#8 교훈) + seam cross-check(test-only, §3.4).
12. **bounds 주입 계약 + Phase-0 이관**(§8): AFG decision 구조에는 numeric bound 부재(전부 enum·boolean·집합 논리·
    주입 `CanonicalDecimal`); ADR이 요하는 수치(invalidation-to-RCL·invalidation-to-egress·violation-to-containment·
    snapshot/decision/permit age·amplification-per-cause)는 **VERIFICATION-PROFILE-002에 8키 전부 실재**(null/TBD/
    MEASURE — §8.1 실측)이며 **candidate 신규 키 0건**(#10/#13형 "0 누락"). per-broker rate/burst/queue/refill 수치는
    **Broker Capability Profile INSTANCE**(brokercap; VP-002 키 아님·이연). 값 승인은 Bounds-Approver 게이트.

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR §30 line 677 "ADR-002-022
  remains `Proposed` until all of the following are true"·line 693 "This ADR authorizes architecture and
  implementation-planning work only. It authorizes no live trading. Written acceptance cases and registered
  evidence are not completed evidence. No automatic re-arm is permitted." **닫는 AFG-EV = 0건.**
- **capacity 산술(commit/consume/quarantine/release·serialize·transfer·atomic economic+flow transaction)을 저작하지
  않는다.** 그것은 **rcl(#5, ADR-002-002/012)이 이미 소유·구현**했다 — `CommittedReservation`·`transition_allowed`
  (`predicates.py:463`)·`grant_authorizes_exact_request`(`predicates.py:575`)·`aggregate_usage`/`effective_limit`
  (`vector.py:103/139`). ADR §1 line 19 verbatim "The Risk Capacity Ledger is the sole serialization and mutation
  authority for every governed action-flow capacity dimension"·AFG-INV-004 line 169. AFG는 action-flow decision
  scalar·`ActionFlowVector`(=`CapacityVector`)를 **생산**하고 rcl이 binding·serialize·원자 commit(§13 line 330).
  §29 q2 "Which bounded protocol atomically commits economic and action-flow coverage"은 명시적 런타임 OQ다.
- **final egress·Live Authorization·Transmission Capability·Commit Proof·active final-egress currentness enforcement을
  저작하지 않는다.** ADR §17 line 380–397(final-egress active currentness)·§4 non-scope line 103(credential/route/
  Commit Proof/hard-fence = ADR-002-013)은 **런타임**이다. ADR §1 line 21 "The Broker Adapter / Egress Gateway
  remains the final transmission enforcement point"·§5.5 line 129 "The permit ... is **not** Live Authorization, a
  Transmission Capability, broker permission." AFG permit은 mandatory precondition이지 전송 권한이 아니다. AFG는
  결정 bool/scalar·permit 레코드만 반환하며 **전송·capability 발급·claim 실행을 하지 않는다**(§4.6; AFG-INV-011).
- **exact broker-command construction을 침범하지 않는다.** ADR §4 non-scope line 99 verbatim "exact broker-command
  construction, which remains ADR-002-020." **ADR-002-020 IOC는 이제 비준·구현 완료다(세션 A, `tos/src/tos/ioc/`;
  ioc→rcl 5번째 sibling edge — `EconomicEffectEnvelope = CapacityVector` `ioc/records.py:69` 실측).** 그럼에도
  **AFG는 IOC에 의존하지 않는다** — command **identity/digest**(scalar)만 binding하고 command **bytes 구성**은 하지
  않는다. 소유권 경계 단절 유지(v1.0의 "미비준·다른 세션 진행 중" 서술은 v1.1에서 "비준·구현 완료·무의존"으로
  갱신; 필요 시 `tos/src/tos/ioc/` 실측으로 boundary 보강 가능하나 현행 scalar-주입·무의존이 최소 접점이다).
- **Protective Flow Reserve 분류·guarantee-level·protective lease admissibility·bounded-retry budget·max-action-rate를
  재저작하지 않는다.** 그것은 **protective(#11, ADR-002-001)가 이미 소유·구현**했다 — `GuaranteeLevel`(**M1 정정 —
  `ReserveGuaranteeLevel`은 phantom·코드 부재**; PHYSICALLY/LOGICALLY_RESERVED/PRIORITIZED_ONLY/BEST_EFFORT/
  UNAVAILABLE, `vocabulary.py:32`)·`is_reserved_guarantee`(`bool`, `predicates.py:129`)·`partition_lease_admissible`
  (**`Admissibility` StrEnum 반환** ADMISSIBLE/TRAPPED/PROHIBITED, `vocabulary.py:118/137` — **M2 정정, bool|None
  아님**; `predicates.py:460`)·bounded-retry `budget_remaining None/<=0 ⇒ no retry`(`:590–615`)·`max_action_rate`
  (`records.py:87/107`). ADR §16 line 368 "under ADR-002-001/004"·§20 line 427(protective lease). AFG는 그 분류/
  budget/lease의 **결과를 주입 소비**하고 action-flow **vector·dimension**을
  생산한다(§3.4; **이것이 protective가 이미 노출한 bounded-retry·reserve 표면을 AFG action-flow 축과 접합하는
  지점**).
- **Broker Capability Profile(rate limit·idempotency·shared-scope·reconnect·throttle 증거)를 재저작하지 않는다.**
  그것은 **brokercap(ADR-002-004)이 이미 소유·구현**했다 — `SUBMISSION_IDEMPOTENCY`/`RATE_LIMITS`(`vocabulary.py:
  71/82`)·`duplicate_order_despite_idempotency`/`unexpected_rate_limit`/`no_retry`(`records.py:222/227/292`). ADR
  §21 line 447 "Broker documentation ... are evidence inputs, not permission"·brokercap `_base.py:19` "creates no
  action-flow [capacity]" 실측. AFG는 broker 증거를 **주입 소비**하고 broker capability를 판정하지 않는다.
- **transmission-attempt / broker-order / knowledge 상태기계를 재저작하지 않는다.** 그것은 **orthostate(ADR-002-005)
  가 이미 소유·구현**했다 — `TransmissionAttemptState`(8상태 NONE..SUPERSEDED, `vocabulary.py:61`; `SENT_UNCONFIRMED`
  `:86`·`SEND_FAILED_PROVEN` `:88`)·`BrokerOrderState`(9상태, **`:92`** — m1 정정; `CANCELLED` `:115`·`UNKNOWN`
  `:118`)·`attempt_transition_allowed`(`predicates.py:465`). AFG-INV-008(no blind retry)·AFG-INV-009(cancel ACK not
  FQP)는 orthostate 상태를 **좌표 소비**한다(SENT_UNCONFIRMED ⇒ potentially live; CANCELLED+later-fill ⇒ not FQP).
  AFG는 attempt 상태를 set하지 않는다.
- **trustworthy-time·refill 시간모델·consistency-cut snapshot 조립·독립 verifier·common-mode 분리 런타임을 구현하지
  않는다.** ADR §18(trustworthy-time = ADR-002-008)·§10 snapshot 조립·§24 security common-mode·§29 q3/q4/q7은
  **런타임 EV-L2/L3**이다. AFG는 time validity·monotonic continuity·recon `ConservativeBound`를 **주입 소비**하고
  순수 동등/순서 검사만 한다.
- **Restrictive Fence Record·Local Restrictive Latch·per-send generation 순서를 저작하지 않는다(Gap-6).** ADR §1
  line 23 "ADR-002-024 orders the Action Flow Generation ... in one per-send proof. A stale permit, local limiter,
  queue priority, or previous proof cannot cross a Restrictive Fence Record or a Local Restrictive Latch in
  `DENY_LATCHED` or `UNKNOWN` state." ⇒ fence record·latch·per-send ordering **메커니즘**은 **ADR-002-024** 소관
  (런타임)이다. AFG는 stale permit/decision이 fence를 못 넘음을 `generation_fenced`(§5.4)로 순수 판정하되 fence/
  latch 자체를 구현하지 않는다.
- **numeric rate·burst·queue·age·amplification·propagation bound를 승인하지 않는다.** ADR §4 non-scope line 105
  "numeric rates, bursts, ages, queue sizes, or propagation bounds, which require an approved Verification Profile
  and Broker Capability Profile"·§29 q12. 전부 주입 파라미터/`CanonicalDecimal`로 담고 **어떤 숫자도 하드코딩하지
  않는다**(CLAUDE.md). 값 부재 ⇒ fail-closed. 값 승인은 Bounds-Approver 게이트(§8·§9.2).

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

`tos.afg` 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml`도 import하지
  않는다** — action-flow 결정 규칙은 StrEnum·boolean·집합 논리이고 수치는 `CanonicalDecimal` 산술(비교·`is_finite`·
  scale-normalize)뿐이며, 모든 rate·burst·queue·amplification bound·broker limit·reserve 값은 주입 파라미터이고
  YAML 파싱은 하네스(설계 #3) 소관이다(closure 최소화 — #5–#13 §0.3 동형).
- tos 자기 자신: `tos.canonical`(`FrozenModel`·`DigestBoundArtifact`·**이미 core인 `IndependentIdArtifact`**·
  **이미 core인 `classify_record_pair`**·`RecordPairKind`·`ArtifactStatus`·**이미 core인 `CanonicalDecimal`**),
  `tos.ordering`(Action Flow Generation·decision·permit·snapshot append-only 순서 — §3.2), **`tos.rcl`(action-flow
  `CapacityVector` 타입 + `aggregate_usage`/`effective_limit` REUSE만 — §0.4c; 실측: rcl closure = canonical+
  ordering+self, 타 형제 미포함이라 afg→rcl은 clean edge)**, `tos.afg.*`. **canonical/ordering/rcl 외 모든 현재·
  미래 tos 형제를 import하지 않는다**(M9 — default-deny 규칙; 고정 "12 형제" 열거는 세션 A의 ioc/iap 추가로 이미
  stale이므로 규칙을 열거가 아닌 "canonical·ordering·rcl 외 전부 금지"로 서술; 현재 13개 = protective/spg/orthostate/
  brokercap/time/recon/are/liveauth/authority/capsule/evidence/dsl/ioc/iap)(produced-scalar/bool·주입 좌표로만 참조
  — §3.4/§3.5). **PROMOTE 0건. sibling edge 1건(afg→rcl).**
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이 `shared.config.secrets`
  (→ `os.environ`)를 무조건 전이 import한다. `tos.afg`는 어떤 `shared.*`도 필요로 하지 않는 순수 커널이다.
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`, `shared.llm`, `shared.storage`,
  `shared.backtest`, `services.*`, `cli.*`(`.importlinter` forbidden set).
- **firewall 구조 확인(실측)**: `.importlinter`는 `[importlinter:contract:tos-operational-firewall]` type=forbidden·
  source_modules=`tos` 단일 계약이며 `layered`가 아니다 — intra-tos sibling→sibling edge는 구조적으로 금지되지 않고
  설계 #1 §3.2 "자기 자신 `tos.*`" 허용 조항이 커버한다. **신규 패키지 `tos.afg`는 firewall 도구 무수정 자동
  포섭**된다(forbidden 계약이 source=tos 전체를 덮으므로). **afg→rcl(`CapacityVector` REUSE) edge는 firewall
  위반이 아니다**(#8 orthostate→rcl `orthostate/records.py:36`·#13 are→rcl 동형 — 이미 존재). 그 외 decision/
  magnitude/reserve seam은 produced-scalar/bool 주입(edge 0)으로 유지하는 것을 **설계 규율**로 삼는다(§0.4b).
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(**allowlist 형식** — `import tos.afg` 후
  `sys.modules`의 top-level `tos.*` ⊆ {`tos.canonical`,`tos.ordering`,`tos.rcl`,`tos.afg`} assert + `shared.config`·
  `os.environ`·numpy/pandas/yaml 부재 assert; **M9: denylist 열거가 아니라 allowlist라 ioc/iap 등 미래 형제 추가에
  자동 견고**). required check(`tos-firewall`)와 함께 green이어야 성립.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 위치·명명 = `tos/src/tos/afg/`.** register domain(EVIDENCE-REGISTER-002 line 288) "**Action Flow
Governance**"·prefix `AFG`(`AFG-EV`/`AFG-AC`/`AFG-INV`)를 직접 명명. 명명 대안 비교(#13 §0.4a 형식):

- **`tos.budget`(action-flow budgeting)(기각·좁음)**: ADR 제목의 첫 토큰만 명명해 **지나치게 좁다** — AFG는
  budgeting뿐 아니라 **amplification containment(§11)·retry/cancel storm(§14–15)·protective reserve(§16)·final-
  egress currentness(§17)·recovery(§22)**를 포함한다(#11이 `tos.degraded`를, #12가 `tos.envelope`를, #13이
  `tos.riskproj`를 "좁다"로 기각한 것과 동형). register prefix `AFG`(Governance)와도 어긋남.
- **`tos.flow`/`tos.rate`(기각·collision·좁음)**: `tos.flow`는 도처의 "flow"/dataflow 토큰과 의미 충돌·지나치게
  generic; `tos.rate`는 rate가 action-flow vector의 **한 dimension**일 뿐이라 좁다. 하드 기각.
- **`tos.governor`/`tos.actionflow`(기각·혼동/비관행)**: `tos.governor`는 **Action Flow Governor**(§7의 한
  컴포넌트, 평가자)와 충돌 — 패키지는 governor+RCL-permit+egress-currentness+recovery 전체라 컴포넌트명보다 넓다;
  `tos.actionflow`는 verbose하고 terse 명명 관행(canonical/capsule/rcl/recon/liveauth/dsl/brokercap/spg/are)과
  어긋남.
- **선택 `tos.afg`**: **register domain "Action Flow Governance"·prefix `AFG`**를 직접 명명, terse, ADR 전체(Action
  Flow **G**overnance)를 포섭. 의미 있는 두문자로 `tos.rcl`(Risk Capacity Ledger)·`tos.spg`(Safety Profile
  Governance)·`tos.dsl`·`tos.are` 동형. **naming은 load-bearing이 아니다**(설계 #1 line 164) — 운영자 치환 가능;
  **load-bearing은 layering**(afg → canonical·ordering·**rcl(CapacityVector REUSE)** 한 방향; protective·spg·
  orthostate·brokercap·time·recon·are와 형제/상하류, **produced-scalar/bool seam·edge 0**; rcl만 1 edge). 실측:
  `tos/src/tos/afg` 부재·`tos.afg`/`ActionFlowPermit`/`ActionFlowVector`/`ActionFlowGovernor` 토큰 tos 내 0건(grep
  실측·충돌 없음). 내부 module(`_base.py`·`vocabulary.py`·`records.py`·`predicates.py`·`state.py`)은 rcl/are/spg/
  protective 선례 동형.

**(b) afg = produced-scalar/bool producer, sibling edge 1건(afg→rcl `CapacityVector`만) (중심 결정, 코드 실측).**
AFG는 **rcl 1개 소비자의 상류**(action-flow decision scalar·vector 생산)이면서 **protective·spg·orthostate·
brokercap·time·recon 6개 생산자의 하류**(reserve bool·정책 generation·attempt 상태·broker 증거·time validity·recon
bound 주입 소비)다. produced-value seam은 전부 produced-scalar/bool 주입(edge 0)이고, **유일한 package edge는
action-flow `CapacityVector` 타입 + 산술 REUSE를 위한 afg→rcl edge**다. seam 대안 비교(#13 §0.4b 형식):

- **대안 A — afg가 소비자(rcl)를 import해 decision을 직접 참조**: 이미 rcl `GrantDecisionRef`가 "Action Flow
  decision reference"를 **주입 슬롯**으로 봉인해 두었으므로(`authority.py:40` 실측) afg→rcl decision seam은 이미
  produced-scalar(str|None) 주입이다. decision-ref만을 위한 별도 import는 불요.
- **대안 B — 소비자가 afg를 import**: rcl이 afg를 직접 호출. **기각**: rcl은 **이미 비준·구현**됐고 action-flow
  decision을 주입 슬롯(`GrantDecisionRef.decision_id/generation/canonical_decision_digest` `authority.py:53–55`)으로
  봉인했다. rcl↛afg 실측(rcl authority ref는 `str|None` 주입 — grep). ratified 패키지를 afg 의존으로 바꾸면
  침습이며 rcl↛afg acyclic이 깨진다.
- **선택 — decision/reserve seam은 plain-scalar/bool 주입(edge 0), action-flow vector 타입·산술만 afg→rcl REUSE
  (1 edge)**: afg는 자신의 어휘·5-아티팩트 모델·결정 술어를 저작하고, decision/reserve 출력은 plain `str`/`int`/
  `bool`/`CanonicalDecimal`로 rcl/protective가 이미 선언한 주입 signature와 타입 일치; **action-flow `CapacityVector`
  (§5.6)와 `aggregate_usage`/`effective_limit`(headroom 검사)만 rcl에서 REUSE한다**(afg→rcl 1 edge, §0.4c). 근거:
  (i) #11/#13의 produced-bool/scalar 봉인과 정합. (ii) **acyclic**: afg→rcl 단일 edge(rcl↛afg 실측)·afg↛{protective,
  spg,orthostate,brokercap,time,recon,are} ∧ 그들↛afg. (iii) **compose seam-sealing**: 타입 일치 + fail-closed
  정합으로 seam 조립, **test-only** 모듈이 afg·(각 소비자)를 둘 다 import해 polarity·fail-closed를 대조(테스트
  import는 §7.1 package closure 불계상). **운영자 판단 지점(§10.3)**: decision/reserve seam decoupled(권장) + action-
  flow vector afg→rcl REUSE(권장·§0.4c).

**(c) REUSE + PROMOTE 0건 + `CapacityVector` REUSE 결정 (핵심 아키텍처, #13 MAJOR-1 동형).** 5-아티팩트는
`tos.canonical.IndependentIdArtifact`(id⊥digest)·`DigestBoundArtifact`(digest 검증)를 REUSE한다. rate·burst·queue·
in-flight·amplification magnitude·limit·headroom은 **이미 core인 `CanonicalDecimal`** REUSE(NaN/infinity 구성-거부·
`1.0` vs `1.00` digest drift 차단; bare `Decimal`/float 금지). **핵심 결정 — `ActionFlowVector`는 rcl
`CapacityVector`(`vector.py:74`, ADR-002-002 §6)를 REUSE한다(afg→rcl 1 edge)**:
- **근거 1(타입 소유·좌표 붕괴 방지 — M3 재앵커)**: ADR §1 line 19 verbatim "The Risk Capacity Ledger is the sole
  serialization and mutation authority ... atomically commit the exact risk-capacity vector **and action-flow
  vector**"·**AFG-INV-004 line 169**·**§30 item 2 line 680** "The RCL action-flow vector and deterministic atomic
  economic/flow commitment protocol are implemented" — action-flow capacity의 vector schema 소유자는 RCL(ADR-002-002)
  이다. (**M3 정정**: §29 q1은 Open Questions Register 항목 — ADR line 671 "Unresolved questions reduce authority
  ... never relax an invariant" — 이므로 REUSE 정당화의 **1차 근거로 인용 불가**; q1이 미해결이라 rcl vector schema
  확정 전까지 REUSE는 **잠정 결정**이고 §10.3-1 판단 지점으로 남는다. q1은 근거가 아니라 미해결 표시로만 언급.) `CapacityVector`는 `dimension_id: str`로 **generic**하다(`vector.py:
  74–100` 실측: "Used both as an adverse-increment / usage vector and ... an Effective Limit vector") — 경제 축이
  아니라 임의 named-dimension 축이므로 action-flow dimension(broker-request/order-mutation/cancel/query/session/
  queue/in-flight/cause-amplification)을 담을 수 있다. afg가 별도 vector를 재정의하면 소유 타입 중복 + rcl commit
  값(`LedgerCommandRecord.proposed_adverse_increment` `records.py:185`)과의 좌표 붕괴 위험.
- **근거 2(산술 REUSE)**: §13 item 6 "sufficient ordinary or protective action-flow capacity in every dimension"의
  headroom 검사(usage ≤ effective_limit, 차원별)는 rcl `aggregate_usage`(`vector.py:103`)·`effective_limit`
  (`:139`)를 그대로 REUSE한다 — 두 함수 모두 **None ⇒ UNKNOWN 전파(fail-closed)** 이미 구현(`:132`·`:164`). afg가
  재구현하면 fail-closed 방향 재검증 부담·drift 위험(#5 produced-bool under-realization 교훈).
- ⇒ 최종 per-(scope,dimension) action-flow increment/usage/limit은 `CapacityVector`를 REUSE(타입 수준 정합 —
  rcl이 commit하는 그 타입), **중간 per-(scope,dimension,cause) 표현이 필요하면 afg-local value 모델**로 richer하게
  둔다. **acyclic 실증**: rcl은 afg를 import하지 않으므로(rcl authority ref는 주입 `str|None`) afg→rcl은 단일 방향
  edge, cycle 아님. 선례: #8 orthostate→rcl(`from tos.rcl import CapacityState`, `records.py:36`)·#13 are→rcl.
- **기각 대안**: (b) **자체 vector** — Phase-1 참조 축약/정합 property를 afg가 별도 명세해야 하고 rcl commit 타입과
  좌표 붕괴 위험(#13 MAJOR-1이 동일 이유로 자체 vector 기각). (c) **canonical PROMOTE** — 무거움(현재 rcl+are+afg만
  필요), 기각. **운영자 판단 지점(§10.3)**: (a) REUSE(권장·채택) vs (b) 자체 vector.

**(d) `ActionFlowPermit` = afg-local 스키마 (schema-ownership vs production-ownership 분리).** ADR §1 line 19 "It
[RCL] SHALL produce an ... Action Flow Permit." rcl이 **인스턴스를 produce**하나(런타임), **permit 스키마 계약**(§5.5·
§13 line 332–342 필드)은 본 ADR-002-022가 정의한다. rcl(#5)은 `TransmissionCapability`(`records.py:249`, single-use
nonce)·`CommitReservation`을 갖지만 **`ActionFlowPermit`은 부재**(grep 실측 — rcl에 "permit" 토큰은 docstring/
vacuous-permit 논의뿐). ADR §5.5 line 129이 permit ≠ Transmission Capability를 명시하므로 **별개 아티팩트**다. ⇒
`ActionFlowPermit`은 **afg-local digest-bound 모델**(ARE가 `AggregateRiskDecision` 스키마를 소유하되 rcl이 consume한
것과 동형); permit의 **single-use 불변식**(nonce·`single_use: bool`, `TransmissionCapability` `records.py:295–296`
동형 패턴)은 EV-L1 decidable; **consume/quarantine 원자 전이**는 rcl/egress 런타임(EV-L2/L3, 이연). **운영자 판단
지점(§10.3)**: permit 스키마를 afg-local로 둘지(권장) rcl로 PROMOTE할지 — afg-local 권장(afg 고유 evidence·rcl
ledger 내부 불요; afg가 REUSE한 `CapacityVector`로 flow vector 담아 좌표 정합).

**(e) `id=f(digest)` 미채택 (canonical REUSE).** Policy·Snapshot·Decision·Permit은 **거버넌스/평가/commitment
identity**(policy version/signer/approval §8; snapshot consistency-cut identity §10; decision issuer §13; permit
consumer/claim-nonce/single-use §13 line 339)를 가지며, same-id/diff-bytes(위조·재발행·contradictory decision·
double-spend permit) 탐지에 `classify_record_pair`(`RecordPairKind.CRITICAL_CONFLICT`)를 쓰려면 id⊥digest여야 한다
(#4–#13 §3.1 동형). ⇒ `IndependentIdArtifact` 채택, `IdDerivedArtifact`(capsule content-addressed) 미채택.
**결정적 코드 증거**: rcl `GrantDecisionRef`가 `decision_id`(53)와 `canonical_decision_digest`(55)를 **별개 필드**로
담아 decision은 id⊥digest임을 소비 측이 이미 전제. 각 Generation은 immutable append-only 레코드이며 정당한
revalidation/supersession은 **새 generation**이지 in-place mutation이 아니다(§22 recovery→new generation). **`tos.afg.
_base`**: canonical 원시타입(`FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`CanonicalDecimal`)의 thin
re-export이되, **all-false `ActionFlowGovernorEffect`의 베이스(all-false authority 계약)는 canonical에 없으므로
`tos.afg._base`에서 로컬 fresh 정의**한다(rcl `_base.py` `AllFalseAuthority`·are `_base` 동형 — afg→rcl edge가 있어도
이 계약은 재사용하지 않고 로컬 저작해 edge 목적을 `CapacityVector` 단일 용도로 유지). `CapacityVector` 자체는
rcl에서 REUSE(§0.4c).

**(f) 앵커 규약 — AFG-INV/AC/EV 앵커, 새 시리즈 창작 금지.** **실측**: ADR-002-022는 자체 시리즈 `AFG-INV-001..014`
(§6 line 155–209, 14종)·`AFG-AC-001..012`(§27 line 583–631, 12종)·`AFG-EV-001..012`(register line 288–299, 12행)를
정의한다. ⇒ 본 계약은 모델 불변식·술어를 **`AFG-INV-###` / `AFG-AC-###` / `AFG-EV-###` / §-clause / `SAFE-###`
(§28 traceability line 637–652)**에 앵커하고 **새 INV/AC/EV 시리즈를 창작하지 않는다**. #6/#8/#10/#12/#13 동형.

**(g) AFG-EV = #11/#13형 core tier(5행) but 닫는 AFG-EV = 0건.** register 실측: **5행(001·002·004·007·008)이 최소
레벨에 `EV-L1` 슬라이스 보유**(§1 표), 7행(003·005·006·009·010·011·012)은 최소 `EV-L2`. ⇒ §1 분류는 **core(L1
슬라이스 5) / predicate-only(7) / not-Phase-1 3분류**. **그러나 닫는 AFG-EV = 0건** — L1 슬라이스 저작은 EV closure가
아니다(`/3`·`+Security`·`+Broker` 통합·독립 리뷰 잔여). §1·§4·§5·§7 전체에 **일관**해야 하며 finishing 전 self-
consistency pass에서 대조한다(#8 lesson 선제 봉합).

---

## 1. 범위 매핑 — ADR-002-022 조항별 EV-L1 도달성 (닫는 AFG-EV 0건)

EV-level 정의(VER-002-001 line 142–164): **EV-L1 = Model and Property Verification**(state-machine exploration,
model checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integrated System Fault Test**, **+Broker = Broker Capability Profile evidence**, **+Security = independent
security-boundary assessment**. Phase 1은 EV-L1만이다. 합성표기(line 166–172): `EV-Ln/Lm`은 staged scope —
EV-Ln이 **earliest non-live stage**, EV-Lm이 통합/broker/production 수용 전 추가 요구. `+X`는 EV-Ln을 대체·인하하지
않는다.

> **결정적 사실 1 — AFG-EV ↔ AFG-AC 1:1, 최소 레벨 실측(사전 카운트 정정)**: `AFG-EV-001..012`(register line
> 288–299)는 ADR §27 `AFG-AC-001..012`(line 583–631)와 제목·번호가 **1:1**(§27 line 631 "Each case SHALL have a
> dedicated `AFG-EV-*` Evidence Register item"). register 최소 레벨 실측(EVIDENCE-REGISTER-002 + VER-002-001 이중
> 확인):
> **`EV-L1` 슬라이스 보유(5행)** = 001(`EV-L1/3` line 288)·002(`EV-L1/3` 289)·004(`EV-L1/3+Broker` 291)·007
> (`EV-L1/3+Security` 294)·008(`EV-L1/3` 295); **`EV-L1` 슬라이스 부재(7행, 최소 ≥ L2)** = 003(`EV-L2/3+Broker`
> 290)·005(`EV-L2/3+Broker` 292)·006(`EV-L2/3+Broker+Security` 293)·009(`EV-L2/3+Security` 296)·010(`EV-L2/3+
> Security` 297)·011(`EV-L2/3+Security` 298)·012(`EV-L2/3+Security` 299). ⇒ **core tier 5행**(#11/#13형;
> orchestrator 사전 "L1 슬라이스 6행"은 **5로 정정** — storm/reconnect(003)·complete-classification(005)·reserve-
> exclusivity(006)·invalidation-currentness(009)·partition(010)·authority-bypass(011)·recovery(012)가 최소 `EV-L2`
> 이므로), predicate-only substrate 7행.
>
> **결정적 사실 2 — authoring ≠ acceptance(닫는 AFG-EV = 0건)**: Phase 1은 각 AFG-EV의 **L1-decidable predicate/
> model substrate**를 저작하나 **어떤 AFG-EV도 닫지 않는다.** (a) core 5행조차 `/3`·`+Security`·`+Broker` 잔여
> (fault injection·adversarial·security·broker 통합), (b) 7행은 최소 ≥ L2, (c) VER-002-001 §5 "Registration is not
> execution"·ADR §27 line 631 "Writing or registering the case does not satisfy it"·§30 line 693 item 10. ⇒
> **"EV-L1-complete 주장 금지"**. Owner/Reviewer는 register상 TBD.

**규율 태그(모든 주장에 부착)**: "**predicate/coordinate substrate only; AFG-EV-001..012 전부 NOT_IMPLEMENTED —
core 5행은 `/3`·`+Security`·`+Broker` 통합·독립 리뷰 대기, predicate-only 7행은 EV-L2/L3 fault injection·adversarial·
+Security·+Broker evidence 대기. EV-L1-complete 주장 금지.**"

**ADR-002-022 조항 → Phase-1 분류(core / predicate-only / not-Phase-1[형제 소유·런타임 이연])**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | AFG-EV |
|---|---|---|---|---|
| **§10** (line 274–278) | Scope Graph·Shared Limits·no local headroom | **core (L1 슬라이스)** | `scope_graph_complete`·unknown⇒확장(§5.1) — AFG-INV-001. 실제 broker-global aggregation은 런타임(주입 소비). `/3` 잔여. | **001** |
| **§11** (line 284–296) | Action Amplification·Causal Lineage | **core (L1 슬라이스)** | `amplification_bounded`·`cause_lineage_complete`(§5.2) — AFG-INV-002. duplicate⇒no allowance. fan-out **값**은 주입. `/3` 잔여. | **002** |
| **§15** (line 358–362) | Cancel/Amend/Replace Storm·cancel ACK≠FQP | **core (L1 슬라이스)** | `cancel_ack_not_final_quantity_proof`·`oscillation_bounded`(§6.2) — AFG-INV-009. orthostate 상태 좌표. broker 통합 `+Broker` 잔여. | **004** |
| **§13** (line 319–342) | RCL Commitment·Permit·atomic economic+flow | **core (L1 슬라이스)** | `permit_single_use`·`atomic_economic_flow_coverage`(§5.3) — AFG-INV-003/004/005. 원자 commit은 rcl 런타임. `+Security` 잔여. | **007** |
| **§12** (line 300–313) | Rate/Burst/Queue/In-Flight·queue≠validity·backlog≠authority | **core (L1 슬라이스, M8 신설)** | `queue_does_not_extend_validity`·`permit_not_merged`·`backlog_is_not_authority`(§5.3) — §12 line 311/313 L1-decidable. 6-state 구분(line 304–309)은 snapshot 축(§2.1 Gap-8). rate/burst 수치는 주입. `/3` 잔여. | **002/007** |
| **§18** (line 403–407) | Time·Windows·Refill·no manufactured headroom | **core (L1 슬라이스)** | `refill_conservative`·counter-integrity·`generation_fenced`(§5.4) — **AFG-INV-004(replenishes)+INV-007(UNKNOWN)**(M6; INV-013=generation fencing≠refill). cross-host non-subtraction·clamp-to-restriction. time 모델은 주입. `/3` 잔여. | **008** |
| **§14** (line 348–352) | Retry·Timeout·Missing ACK | **predicate-only** | `no_blind_retry`(§6.1) — AFG-INV-008. broker idempotency 증명은 brokercap+런타임. 최소 `EV-L2/3+Broker`. | **003** |
| **§9** (line 254–268) | Complete Action·Resource Classification | **predicate-only** | `action_class_conservative`(§6.3) — most conservative class. common-mode resource 소진은 EV-L2·+Broker. 최소 `EV-L2/3+Broker`. | **005** |
| **§16** (line 368–374) | Protective Flow Reserve·exclusivity | **predicate-only** | `reserve_exclusive`·`priority_is_not_reserve`(§6.4) — AFG-INV-006. protective 분류 소비. common-mode·+Security는 런타임. 최소 `EV-L2/3+Broker+Security`. | **006** |
| **§17/§19** (line 380–419) | Invalidation·Active Final-Egress Currentness | **predicate-only** | `currentness_invalidation`(§6.5) — AFG-INV-010. cache≠currentness. active RCL/egress currentness는 런타임(profile bound). 최소 `EV-L2/3+Security`. | **009** |
| **§20** (line 425–431) | Partition·Failover·Stale Writer·Protective Lease | **predicate-only** | `partition_lease_exclusive`(§6.6) — protective lease 소비. quorum/fence enforce는 런타임. 최소 `EV-L2/3+Security`. | **010** |
| **§7/§24** (line 215–229·489–500) | Authority Separation·Bypass | **predicate-only** | `ActionFlowGovernorEffect` all-false·`governor_grants_no_authority`(§6.7) — AFG-INV-011. governor↛live route·egress bypass는 +Security 런타임. 최소 `EV-L2/3+Security`. | **011** |
| **§22** (line 455–465) | Recovery·Economic Continuity·Non-Revival | **predicate-only** | `non_revival_holds`·`economic_effect_persists`(§6.8) — AFG-INV-012/014. Recovery Barrier(ADR-002-017)·re-arm 런타임. 최소 `EV-L2/3+Security`. | **012** |
| **§5/§8** (line 111–149·233–248) | Definitions·Action Flow Policy Contract | **core substrate(분산)** | 5-아티팩트 모델·`ActionFlowResult` 어휘(§2). policy는 spg Bundle member(§5.1·`ACTION_FLOW_POLICY` 실측). policy **값**은 주입. | 001–012 공통 |
| **§10 broker-global aggregation·§17 egress enforce·§24 verifier** | shared-limit 실측 조립·final-egress enforce·독립 verifier·common-mode 런타임 | **not-Phase-1 (런타임 EV-L2/L3)** | consistency-cut(§29 q3)·egress currentness(§29 q4)·common-mode(§24·§29 q8). afg는 순수 동등/순서 검사만. | 001/009/011 (런타임) |
| **§17 egress·Transmission Capability·Commit Proof** | final egress·Live Auth·capability·claim 실행 | **not-Phase-1 (ADR-002-007/013)** | afg는 결정 bool·permit 레코드만. 전송·capability·claim은 런타임(§0.2). | 007/009 (런타임) |
| **§14 broker idempotency·§21 broker capability** | broker-side idempotency 증명·shared-scope 증거 | **not-Phase-1 (ADR-002-004 brokercap·+Broker)** | brokercap INSTANCE·broker 통합(§0.2). 전부 주입. | 003/004/005 (broker) |
| **§4 non-scope** (line 105) | numeric rate/burst/queue/age/propagation bounds | **not-Phase-1 (Phase-0/INSTANCE)** | 수치 선택은 §9.2 Phase-0. 전부 주입. | — |

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True, extra="forbid")`,
`tos.canonical.FrozenModel` REUSE)로 저작한다. `extra="forbid"`는 **§8 line 248 "Omitted or unknown fields are
restrictive"·§9 line 254 "governed even when it is believed not to create economic exposure"의 스키마 수준 실현**
이다(unknown/silent-drop 차단). 모든 rate·burst·queue·amplification magnitude·limit·headroom은 **주입
`CanonicalDecimal|None`**(하드코딩 수치 0).

### 2.0 소유권 골격 — afg는 canonical의 하류, rcl의 상류(decision)·6개 형제의 하류(주입 소비)

`tos.afg`는 `tos.canonical`·`tos.ordering`(둘 다 core) + `tos.rcl`(`CapacityVector` REUSE)만 import한다. dataflow상
afg는 **rcl의 상류**(action-flow decision scalar·`ActionFlowVector` 생산)이자 **protective·spg·orthostate·brokercap·
time·recon의 하류**(reserve bool·정책 generation·attempt 상태·broker 증거·time validity·recon bound 주입 소비)다.
decision/reserve seam은 **produced-scalar/bool 주입(edge 0)**으로 실현되고, **유일 package edge는 action-flow
`CapacityVector` 타입 + `aggregate_usage`/`effective_limit` REUSE를 위한 afg→rcl edge**다(§0.4c; rcl↛afg acyclic).

### 2.1 digest-bound / plain-frozen / value / reference 분류 (총괄)

| 모델 | 분류 | 근거 |
|---|---|---|
| `ActionFlowPolicy`(§5.1/§8) | **digest-bound `IndependentIdArtifact`** | §5.1 line 113 "immutable, authenticated, content-addressed"·§8 line 233; id⊥digest(governance identity·같은-id/diff-bytes 탐지). **spg Safety Config Bundle member `ACTION_FLOW_POLICY`**(`spg/vocabulary.py:209` 실측). |
| `ActionFlowStateSnapshot`(§5.3/§10) | **digest-bound `IndependentIdArtifact`** | §5.3 line 119 "immutable consistency-cut artifact"·"grants no permission"(line 121); consistency-cut identity ⊥ digest. |
| `ActionFlowDecision`(§5.4/§13) | **digest-bound `IndependentIdArtifact`** | §5.4 line 123 "immutable non-authorizing result"; **decision_id ⊥ canonical_decision_digest**(rcl `GrantDecisionRef` `authority.py:53/55` 별개 필드 실측). forward-only(§13). |
| `ActionFlowPermit`(§5.5/§13) | **digest-bound `IndependentIdArtifact` (afg-local, §0.4d)** | §5.5 line 127 "immutable, exact, single-use RCL commitment record"; **NOT Transmission Capability**(line 129). single_use·claim_nonce(rcl `TransmissionCapability` `records.py:295–296` 패턴 동형). |
| `ActionFlowVector`(§5.6) | **REUSE rcl `CapacityVector`** | §5.6 line 131–133 multi-dim resource. ADR §29 q1 "RCL vector schema"·generic dimension_id(`vector.py:74`)(§0.4c; afg→rcl edge). |
| `ActionCause`(§5.7) | **plain-frozen value** | §5.7 line 135–137 root + parent lineage. rcl `causation_identity`(`records.py:151`)·`attempt_identity`(`:153`) 좌표 정합. |
| `ActionAmplificationEnvelope`(§5.8) | **plain-frozen value(주입 bound)** | §5.8 line 139–141 max count/rate/fan-out/depth/time/queue/broker-resource. unknown/unbounded ⇒ denial(line 141). 값은 주입(`MAX_action_amplification_per_cause`). |
| `ProtectiveFlowReserveClaim`(§5.9/§16) | **plain-frozen value(protective 분류 소비)** | §5.9 line 143–145 exclusive RCL pre-commitment. guarantee level·`is_reserved_guarantee` 결과 주입(protective 소유, §3.4). |
| `ActionFlowGovernorEffect`(§7/AFG-INV-011) | **plain-frozen all-false** | rcl `RclAuthorityEffect`(`authority.py:19–36`) 동형; 어떤 True도 unconstructable(§1 line 17 "A `GRANT` is not capacity or permission to send"). |
| `ActionFlowResult`/`ActionClassKind`/`ActionFlowScopeKind`/`ActionFlowDimensionKind` | **StrEnum(어휘)** | §2.2 verbatim. |

**§12 6-state 분류 disposition (Gap-8·M8)**: ADR §12 line 304–309은 action-flow 상태를 6구분한다 — (1) allocations
committed but not yet claimed, (2) claims made but no broker byte proven, (3) broker-directed writes started,
(4) acknowledged/unacknowledged, (5) queued/in-flight/throttled/rejected/timed-out/ambiguous, (6) usage reserved
exclusively for protection. **판정**: 이 6구분은 **`ActionFlowStateSnapshot`의 per-dimension 축 필드**(§5.3)로 담되,
(2)(3)(4)의 transmission-attempt 세부는 **orthostate `TransmissionAttemptState` 좌표 주입**(§3.4; CAPABILITY_ISSUED/
SEND_STARTED/SENT_UNCONFIRMED/ACK_OBSERVED)이고 (6) protective reserve는 protective `GuaranteeLevel` 주입이다. rcl
`CapacityState`(예: `TRAPPED_CONSUMED`)와의 접점은 주입 소비(afg는 capacity state를 set하지 않음) — Gap-8 판정:
6구분을 **snapshot 모델의 구조적 field**로만 저작하고 상태 전이 실행은 rcl/orthostate 런타임. **partition lease
admissibility는 protective `Admissibility` StrEnum 주입 소비**(M2; §6.6).

### 2.2 어휘 (verbatim 전사 — 에라타 defect class 주의)

**(1) `ActionFlowResult`** — ADR §1 line 15·§5.4 line 125 verbatim "`GRANT`, `DENY`, or `UNKNOWN`". 3종:
`GRANT`("A `GRANT` is not capacity or permission to send"·"authorizes only an exact RCL allocation request", §1
line 17·§5.4 line 125)·`DENY`·`UNKNOWN`. **UNKNOWN은 permissive 아님** — "consumes conservative capacity and
blocks new normal risk"(AFG-INV-007 line 181). **truthy-sentinel 봉합(양축)**: (i) `ActionFlowResult`는 StrEnum이라
truthy — 소비 게이트는 `result is ActionFlowResult.GRANT`(identity)로만 통과, `if result:`(DENY/UNKNOWN 관통) 금지;
(ii) **protective `Admissibility` StrEnum(ADMISSIBLE/TRAPPED/PROHIBITED, `vocabulary.py:118`) 소비 게이트도 `verdict
is Admissibility.ADMISSIBLE`로만 통과**(TRAPPED/PROHIBITED/None 관통 금지 — M2); (iii) bool|None 안전 술어는 `is
True`/`is not True` 정규화(#13 ARE UNKNOWN-truthy 교훈; orthostate `is True` `predicates.py:461` 선례).

**(2) `ActionClassKind`** — §9 line 258–266 verbatim 9종: `NORMAL_NEW_RISK`·`ORDINARY_REDUCE_OR_EXIT`·
`SAFETY_PROTECTIVE`·`CANCEL_OR_REPLACE`·`RECONCILIATION_QUERY`·`SESSION_OR_CONNECTION_CONTROL`·`HALT_SUPPORT`·
`RECOVERY_NON_LIVE`·`ADMINISTRATIVE_NON_LIVE`. **classification은 admissibility/risk capacity/protective capacity/
authority/broker permission을 창조하지 않는다**(§9 line 268). **the more conservative applicable class and vector
govern when classification conflicts**(§9 line 268 — 진동/reduce가 risk를 올릴 수 있음: exit이 zero-cross/reversal/
overlap, cancel이 protection 제거, query/reconnect가 shared resource 소진). **주의(에라타 봉합)**: 이 9종은 ADR §9의
**구조적 축**이며 label이 더 permissive class를 만들지 못한다(§7 line 218 "Producer label cannot create a more
permissive class").

**(3) `ActionFlowScopeKind`** — §10 line 274 verbatim 17종: `GLOBAL`·`ENVIRONMENT`·`SAFETY_CELL`·`BROKER`·
`LEGAL_PORTFOLIO`·`ACCOUNT`·`CREDENTIAL`·`SESSION`·`CONNECTION_POOL`·`ROUTE`·`ENDPOINT`·`VENUE`·`INSTRUMENT`·
`STRATEGY`·`INTENT`·`CAUSE`·`ACTION_CLASS`. (§1 line 25는 부분집합; §10이 fuller list. **m7: §10 line 274 `cause`
≡ §1 line 25 "originating event"** — 동일 scope의 두 표기이며 별개 멤버 아님, `CAUSE`로 단일화.) **두 보수 규칙
(C1)**: unknown dependency/limit scope ⇒ **smallest** conservative containing scope(§1 line 25); broker documented
scope incomplete/contradictory/stale/unverified ⇒ **largest** credible containing scope에 shared(§10 line 276).
**separate processes/nodes/regions/local counters ≠ independent capacity**(§10 line 278; independence는 allocation/
refill/broker enforcement/**credential·session state**/failure-domain/final-route **6축** 분리 증거 필요 — v1.2
에라타로 credential/session state 축 복원).

**(4) `ActionFlowDimensionKind`** — **§5.6 line 133**(Action Flow Vector 정의 축)에서 명명: `BROKER_REQUEST`·
`ORDER`·`ORDER_MUTATION`·`CANCEL_AMEND_REPLACE`·`QUERY`·`SESSION`·`CONNECTION`·`CREDENTIAL`·`ROUTE`·`ENDPOINT`·
`QUEUE`·`IN_FLIGHT`·`CAUSE_AMPLIFICATION`(13종). **M5 정정**: v1.0의 "§8 line 238 verbatim"은 오귀속 — §5.6:133
(vector 정의, "order mutation" 단일)과 §8:238("mutations, **orders**, cancels" 분리) + §21:439("connection")은
**목록이 다르다**. §8:238은 "including..."의 **비폐쇄 예시**이고(§8 line 248 "Omitted or unknown fields are
restrictive") 따라서 `ActionFlowDimensionKind`는 §5.6 정의에 §8:238 `orders`(→`ORDER`, submission ≠ mutation)와
§21:439 `connection`(→`CONNECTION`, ≠ session)을 **합집합**한 **명명된 최소 집합**이며 폐쇄 우주가 아니다. 미열거
dimension_id는 `CapacityVector.dimension_id: str`(자유 문자열)로 표현 가능하고 **소비 술어에서 fail-closed**(unknown
⇒ UNKNOWN, §4.1). 각 dimension은 exact unit/scope/measurement-point/aggregation/window-or-refill/burst/max-debt/
failure-response 보유(§12 line 302). **counting은 submit뿐 아니라 cancel/amend/replace/query/session/reconnect/
SDK-retry 전부**(§9 line 254·rejected alt §25.6 line 526). 이 값들이 `ActionFlowVector`(=`CapacityVector`)의
`dimension_id`가 된다(§7 Gap-1 disjointness property로 경제 dimension-id와 ∩=∅ 강제).

**(5) 좌표 어휘(비붕괴 — 본 절 §2.2-5가 좌표-비붕괴 canonical 위치; m8: 문서 내 dangling "§4.4 좌표 비붕괴"
참조는 전부 여기 §2.2-5로 정정)**: afg `ActionFlowDimensionKind`(action-flow 자원 축) ≠ rcl `DimensionDescriptor`
(경제 capacity 축, `vector.py:39`) ≠ are `RiskDimensionKind`(aggregate-risk 축; **are `BROKER_ACTION_RATE_PROTECTIVE_
RESERVE`** `are/vocabulary.py:67`는 action-rate의 **경제적 view**이지 afg 자원 view가 아님) ≠ protective
`GuaranteeLevel`(reserve 분류 축, `vocabulary.py:32` — **M1: `ReserveGuaranteeLevel` 아님**) ≠ spg
`ConfigArtifactKind`(bundle-member 축). 토큰 겹칠 수 있으나 **별개 타입**. **Gap-1(전역 관점 — disjointness 자기정합
조건)**: `CapacityVector.dimension_id`는 자유 문자열이고 `aggregate_usage`/`effective_limit`은 문자열 일치로만
동작하므로 REUSE 정당화("좌표 붕괴 방지")의 자기정합 조건은 **afg action-flow dimension-id 집합 ∩ 경제 dimension-id
집합 = ∅**이다. `CapacityVector` REUSE 소비자가 **rcl(경제)·are(AdverseIncrement)·ioc(`EconomicEffectEnvelope`
`ioc/records.py:69`)·afg(ActionFlowVector) 4곳**이므로 disjointness는 afg-로컬이 아닌 **전역 dimension-id namespace**
문제다 — 본 계약은 afg 몫(afg dimension-id = `ActionFlowDimensionKind` 값, 전부 action-flow 자원 토큰)만 확정하고
전역 namespace 조정(경제/risk/flow 접두사 규약)은 **Phase-0/후속 판단 지점**(§10.3)으로 남긴다. disjointness는 §7
core 필수 property. **핵심**: are의 action-rate risk dimension(경제)과 afg의 action-flow vector(자원)는 **다른 축**이며 AFG-INV-
005 atomic coverage는 둘 **다** commit을 요구(both, not either — §4.7 양방향).

### 2.3 아티팩트 covered + self-exclusion (설계 #4 §3.3 상속)

covered(digest preimage) = 각 아티팩트의 구조적 identity/scope/version/generation/class + (Decision) command
identity·cause·lineage·policy/generation/snapshot digest·vector·amplification envelope·scope·protective classification
digest scalar + (Permit) permit/RCL-commitment/writer-epoch/revision/command identity·policy/generation/snapshot/
decision/cause/lineage digest·resource vector·ordinary-or-protective dimension mark·protective-lease/reserve proof·
consumer/claim-nonce/single-use/issue-anchor/max-age/invalidation-generation·economic-capacity commitment ref(§13
line 332–340 verbatim). preimage 제외: `*_id`·`canonical_digest`·`canonicalization_version`·`status`(ArtifactStatus)·
`*_order`(ledger placement)·파생 역참조. **`_REQUIRED_COVERED`는 structural identity/scope/version/class만**(numeric
magnitude 제외 — Phase-1 null bound에서 ISSUED 도달 가능; missing magnitude는 consuming 술어에서 fail-closed, #13
§2.3 규율 상속).

> **핵심 설계 결정 — 5-아티팩트는 immutable generation별 append-only(#10/#12/#13 상속)**: Policy/Snapshot/Decision/
> Permit은 시간에 따라 **재발행**된다(§5.2 Action Flow Generation·§22 recovery→new artifacts). 하나의 stable id에
> mutable 내용을 담으면 정당한 revalidation이 same-id/diff-bytes `CRITICAL_CONFLICT`로 **오탐**된다. ⇒ **각
> generation은 fresh id를 가진 immutable 레코드**다. same identity + diff canonical digest ⇒ `CRITICAL_CONFLICT`
> (위조·재발행 위조·contradictory decision·double-spend permit만); 정당한 개정 ⇒ **새 generation**. **Decision·
> Permit은 특히 forward-only**: 미래 Capacity Commitment identity를 covered에 담지 않는다(non-cyclic; §29 q2가
> economic/flow atomic commit이 Order Conformance Proof·Transmission Capability issuance와 cyclic dependency를
> 만들지 않을 것을 명시적으로 요구).

---

## 3. canonical / ordering / rcl REUSE + 6-생산자 주입 seam + 형제 경계

### 3.1 canonical REUSE + `id=f(digest)` 미채택

5-아티팩트는 `tos.canonical.IndependentIdArtifact`·`DigestBoundArtifact`를 REUSE한다. canonicalizer는
`tos.canonical` registry + `EVL1ProvisionalCanonicalizer`(`ev-l1-provisional-0`) REUSE, **신규 canonicalizer 없음**
(프로덕션 canonical semantic form은 Phase-0 §9.2 — ADR §30 item 1). magnitude·limit·headroom은 **이미 core인
`CanonicalDecimal`** REUSE(NaN/infinity 구성-거부). **`id=f(digest)` 미채택**(§0.4e 근거·rcl `GrantDecisionRef` 별개
필드 실측). **PROMOTE = 0건**.

### 3.2 ordering REUSE (Action Flow Generation / decision / permit / snapshot append-only 순서)

Action Flow Generation(§5.2 line 117 "A monotonic generation")·decision·permit·snapshot의 append-only 순서는 신규
저작하지 않고 `tos.ordering`(`Ordering`·`OrderingEvent`·`compare_order`, `tos.canonical`만 의존)를 REUSE한다. **wall
clock은 순서를 만들지 않는다**(§17 line 391 "last-known generation ... is not proof"·§18 line 405 "Wall-clock
movement ... cannot manufacture headroom"와 정확히 정합) — afg는 clock을 읽지 않는다(§3.5; time validity·monotonic
continuity는 주입 flag). Generation은 별도 heavy 아티팩트가 아니라 각 아티팩트의 `*_generation: int` 좌표 + ordering
비교로 실현(#13 Aggregate Risk Generation 동형). light REUSE(core 의존, 신규 edge 아님).

### 3.3 REUSE 요약 표

| substrate | 결정 | 근거 |
|---|---|---|
| `FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`ArtifactStatus` | **REUSE(core `tos.canonical`)** | §3.1; 신규 없음 |
| `classify_record_pair`·`RecordPairKind` | **REUSE(core)** | §3.1; same-id/diff-bytes·contradictory decision·double-spend permit |
| `CanonicalDecimal` | **REUSE(core, #9 PROMOTE됨)** | §3.1/§4.4; magnitude·limit·NaN 구성-거부·PROMOTE 불필요 |
| `Ordering`·`OrderingEvent`·`compare_order` | **REUSE(core `tos.ordering`)** | §3.2; generation/decision/permit/snapshot 순서 |
| rcl `CapacityVector`·`aggregate_usage`·`effective_limit` | **REUSE(afg→rcl 1 edge; `ActionFlowVector`·headroom)** | §0.4c; ADR §29 q1 RCL vector schema·rcl↛afg acyclic·#8/#13 선례 |
| 5-아티팩트·`ActionCause`·`ActionAmplificationEnvelope`·`ProtectiveFlowReserveClaim`·술어·어휘 | **로컬 저작** | §0.4a/§2; ADR §5–§22 verbatim·decision-side |
| rcl decision-ref scalar·all-false authority·protective reserve bool·spg policy generation·orthostate 상태·brokercap 증거·time validity·recon bound | **미소유 — produced-scalar/bool·주입 좌표로만 참조** | §3.4; 1-소비자 + 6-생산자 seam |
| capacity 산술(원자 commit)·envelope 거버넌스·protective classify·broker capability·attempt 상태기계·trustworthy-time·final egress·numeric bound | **미소유 — rcl/spg/protective/brokercap/orthostate/time/런타임/INSTANCE 이연** | §3.5 |
| PROMOTE | **0건** | §3.1 |
| sibling edge | **1건(afg→rcl, `CapacityVector`+산술)** | §3.4; #8/#13 선례 동형 |

### 3.4 rcl / protective / spg / orthostate / brokercap / time / recon 경계 — produced-scalar seam(edge 0) + afg→rcl 1 edge (중심, 코드 실측)

**(a) afg = produced-scalar/bool producer(§0.4b).** afg는 형제를 **import하지 않고**(rcl 예외), 그들이 소비할
plain scalar/bool을 생산하거나 그들이 생산한 값을 주입 소비한다. **코드 실측 seam**(sibling 서사 아님 — #10
MAJOR-1 교훈; 전 인용 grep 실측):

| afg 산출 / 소비 (§5/§6) | 타입 | 상대 (이미 비준·구현) | signature(실측 file:line) |
|---|---|---|---|
| **[생산]** decision content ref 3종 | `str\|None`·`int\|None` | rcl `grant_authorizes_exact_request` | afg → rcl `GrantDecisionRef.{decision_id, decision_generation, canonical_decision_digest}`(`rcl/authority.py:53–55`, "**Action Flow** decision reference" `:40`); rcl이 `bound_reservation_*` post-commit 충전(`:56–58`) |
| **[생산]** all-false authority block | (all-false) | rcl `RclAuthorityEffect` 동형 | afg `ActionFlowGovernorEffect`(로컬 fresh, `_base` `AllFalseAuthority`; 어떤 True도 unconstructable — rcl `authority.py:25` 동형) |
| **[생산/REUSE]** 최종 action-flow vector | `CapacityVector` | rcl commit·`aggregate_usage`/`effective_limit` | afg `ActionFlowVector`=`CapacityVector` REUSE(`rcl/vector.py:74`); headroom = `effective_limit`(`:139`)·`aggregate_usage`(`:103`) REUSE(None⇒UNKNOWN 전파 `:132/164`) |
| **[소비]** reserve guarantee | `bool` | protective `is_reserved_guarantee`(→ `GuaranteeLevel`) | afg `reserve_exclusive` 주입 소비(`protective/predicates.py:129`; PHYSICALLY/LOGICALLY만 reserved, `GuaranteeLevel` `vocabulary.py:32` — M1; `is not True⇒not reserved`) |
| **[소비]** partition lease admissibility | **`Admissibility` StrEnum** | protective `partition_lease_admissible` | afg `partition_lease_exclusive` 주입 소비(`protective/predicates.py:460` → **`Admissibility`** ADMISSIBLE/TRAPPED/PROHIBITED `vocabulary.py:118/137` — **M2, bool 아님**; `is Admissibility.ADMISSIBLE`로만 통과) |
| **[소비]** bounded-retry budget | `int\|None` | protective bounded-retry | afg `no_blind_retry` 보조 주입(`protective/predicates.py:590–615`; `budget_remaining None/<=0 ⇒ no retry`) |
| **[소비]** attempt / broker-order 상태 | StrEnum | orthostate 상태기계 | afg `no_blind_retry`/`cancel_ack_not_final_quantity_proof` 좌표 소비(`orthostate/vocabulary.py:61`(attempt)·**`:92`**(broker-order) — m1; `SENT_UNCONFIRMED`:86·`SEND_FAILED_PROVEN`:88·`CANCELLED`:115·`UNKNOWN`:118) |
| **[소비]** same-order retry / rate admission (**전용 술어**, M7) | `bool` | brokercap `same_order_retry_allowed`·`rate_admission_ok` | afg `no_blind_retry`(idempotency)·`shared_limit_conservative`(rate) 주입 소비(`brokercap/predicates.py:377`·`:437`; capability 축 `SUBMISSION_IDEMPOTENCY`/`RATE_LIMITS` `vocabulary.py:71/82`; "creates no action-flow" `_base.py:19`) |
| **[소비]** 활성 정책 generation | `int\|None`·`str\|None` | spg `ACTION_FLOW_POLICY` bundle member | afg 활성 policy generation 주입 소비(`spg/vocabulary.py:209`; spg가 bundle activate·generation 부여) |
| **[소비]** elapsed-within-continuity / snapshot-age / recovery-non-revival (**전용 술어**, M7) | `int\|None`·`bool` | time `elapsed_within_continuity`·`snapshot_age_admissible`·`recovery_generation_revives_nothing` | afg `refill_conservative`(§5.4)·`non_revival_holds`(§6.8) 주입 소비(`time/predicates.py:73`·`:287`·`:499`; `MonotonicReading` "continuity subtraction is never performed" `elements.py:112`; cross-host 비교 금지 `LOCAL_MONOTONIC`/`MONOTONIC_DISCONTINUITY` `domains.py:22/87`) |
| **[소비]** recon `ConservativeBound` | value | recon reconciliation | afg 복구/currentness 주입 소비(`recon/records.py:28`; `FieldReconciliationAssessment` `:119`) |

**(b) 정직 공개 — 전용 술어 실재 vs 좌표-의존 구분 (under-realization 봉합 #7/#11; M7 정정)**: 전용 술어가 **실재**
하는 상대(주입 결과를 정의된 afg 술어로 소비): rcl(`grant_authorizes_exact_request`·decision-ref)·protective
(`is_reserved_guarantee`·`partition_lease_admissible`·bounded-retry)·**brokercap(`same_order_retry_allowed`·
`rate_admission_ok`)**·**time(`elapsed_within_continuity`·`snapshot_age_admissible`·`recovery_generation_revives_
nothing`)** — 이들은 §3.4 표에서 **produced-bool 전용 슬롯**으로 소비되고 §7에 전용 seam 테스트(`test_seam_brokercap`·
`test_seam_time` 포함)를 둔다(M7: v1.0의 "rcl·protective만 전용 술어" 서술 정정). 반면 아래 seam은 **전용 afg-bool
슬롯이 부재한 좌표-의존**이라 정직 이연:
- **orthostate**: attempt/broker-order 상태는 afg 술어가 **좌표 소비**(주입 StrEnum)하나 orthostate records에 전용
  afg-bool 필드는 **부재**(#13 are-orthostate 동형 정직 이연). afg `no_blind_retry`는 정의 술어(§6.1)를 갖고
  orthostate 상태를 입력으로 받는다.
- **spg**: `ACTION_FLOW_POLICY`는 bundle member(실측)이나 **spg `SemanticValidationInputs`에 `action_flow_effect_
  within` 같은 전용 step 필드는 부재**(실측: `spg/records.py:205`는 `aggregate_effect_within`[ARE step 7]만 보유;
  grep `action_flow|effect_within` in spg/records.py = aggregate만). AFG 정책 narrowing은 spg **generic step-6
  envelope 검사**(`profile_within_envelope`, spg-owned·任意 dimension)로 검증되므로 **afg는 spg step을 생산하지
  않는다(phantom 금지)**. **운영자 판단 지점(§10.3)**: 미래에 action-flow 전용 spg step이 필요한지 — 현 판정은
  불요·이연.
- **brokercap/time/recon**: 전부 주입 opaque flag/bound. afg는 이들을 판정하지 않는다.

**(c) afg는 mutate/transmit/issue/claim/activate하지 않는다(§1 line 17/21·§17 런타임·AFG-INV-011).** afg는 결정
scalar/bool·permit 레코드만 생산하고 capacity mutation·egress transmit·capability/permit-consume·claim 실행·live-
scope set 메서드가 **부재**하다(§4.6). 소비 authority(rcl serialize/원자 commit·final egress·protective classify)가
실제 action을 gate한다.

**(d) seam cross-check = MANDATED(test-only).** Phase 1은 **test-only** 모듈(`tos/tests/afg/test_seam_rcl.py`·
`test_seam_protective.py`·`test_seam_orthostate.py`)에서 afg·(각 상대)를 **둘 다 import**해 (i) afg decision ref ↔
rcl `grant_authorizes_exact_request`, (ii) afg `ActionFlowVector` 좌표 ↔ rcl commit 타입·`effective_limit` 정합,
(iii) afg reserve 소비 ↔ protective `is_reserved_guarantee`(`is not True⇒not reserved`), (iv) afg `no_blind_retry` ↔
orthostate `SENT_UNCONFIRMED` polarity를 assert한다. **이 테스트는 package edge가 아니다** — 테스트 import는 §7.1
package-closure에 계상되지 않는다(#11/#13 동형). **acyclic**: afg→rcl 단일 edge(rcl↛afg 실측)·afg↛{나머지 11 형제}
∧ 그들↛afg.

### 3.5 소유권 분할표 — afg가 소유 / 형제에서 소비·생산 (본 문서 최대 함정 지대, #11/#12/#13 §3.5 상속)

> **소유권 분할 명시(#8·#11·#13 교훈 — cross-section 혼동 선제 봉합)**: ADR-002-022는 **broker-directed action flow의
> budgeting·amplification·retry-storm·protective-reserve·final-egress currentness 결정 프로토콜**만 결정하며(§4
> line 85–95) capacity serialization/원자 commit(rcl)·envelope governance(spg)·protective classification/reserve/
> lease(protective)·broker capability(brokercap)·attempt 상태기계(orthostate)·trustworthy-time(time)·broker-command
> construction(ADR-002-020)·final egress(ADR-002-013)를 **소유하지 않는다**. 함정: afg가 protective의
> `is_reserved_guarantee`·rcl의 `transition_allowed`·brokercap의 idempotency·orthostate의 attempt 상태를 재저작하면
> 권위 중복(#8 lesson). 아래 표가 경계를 코드 실측으로 고정한다.

| ADR 조항/개념 | afg 소유 (Phase 1) | 형제 소유 (재저작 금지) | seam 방향(실측) |
|---|---|---|---|
| §10 scope graph·shared limit | `scope_graph_complete`·`ActionFlowScopeKind`·no-local-headroom(§5.1) | rcl 경제 vector 산술·broker-global 실측 조립(런타임) | afg가 scope 완전성 판정 → rcl `CapacityVector`로 usage/limit 담음(`aggregate_usage`/`effective_limit` REUSE) |
| §13 RCL commit·permit | decision ref·permit 스키마·`ActionFlowVector`·all-false(§5.3/§0.4d) | rcl 원자 commit·serialize·`grant_authorizes_exact_request`·`transition_allowed`(`predicates.py:575/463`) | afg `decision_id/gen/digest` 생산 → rcl `GrantDecisionRef` 소비(`authority.py:53–55`); reservation 좌표·원자 commit은 rcl(non-cyclic·§29 q2) |
| §16 protective reserve | `reserve_exclusive`·`priority_is_not_reserve`·`ProtectiveFlowReserveClaim`(§6.4) | protective `GuaranteeLevel`(M1)·`is_reserved_guarantee`·reserve minimum(`vocabulary.py:32`·`predicates.py:129`) | protective reserve bool → afg 주입 소비; afg는 reserve **분류**를 하지 않음(**protective bounded-retry·reserve 표면 접합 지점**) |
| §14 retry/idempotency | `no_blind_retry`(§6.1) | orthostate attempt 상태기계·brokercap idempotency·protective retry budget(`orthostate/predicates.py:465`·`brokercap/records.py:222`·`protective/predicates.py:590`) | orthostate 상태·brokercap 증거·protective budget → afg 주입 소비; afg는 상태를 set·capability 판정 안 함 |
| §15 cancel/replace | `cancel_ack_not_final_quantity_proof`·`oscillation_bounded`(§6.2) | orthostate `BrokerOrderState`(CANCELLED+later-fill)·rcl Final Quantity Proof 규칙(`orthostate/vocabulary.py:92`) | orthostate broker-order 상태 → afg 주입 소비; FQP 규칙은 orthostate/rcl(ADR-002-002/011) |
| §8 policy·envelope | policy 모델(bundle member)·`ActionAmplificationEnvelope`(§5.8) | spg bundle activation·envelope narrow-only·`profile_within_envelope`(spg 소유·`vocabulary.py:209`) | spg 활성 generation → afg 주입 소비; afg는 spg step 생산 안 함(§3.4 (b) phantom 금지) |
| §18 time·refill | `refill_conservative`·counter-integrity(§5.4) | time trustworthy-time·monotonic non-subtraction(`time/elements.py:112`) | time validity·monotonic continuity → afg 주입 소비; afg는 clock 안 읽음 |
| §17 currentness | `currentness_invalidation` 술어(§6.5) | authority invalidation·final-egress active currentness enforce(런타임·ADR-002-013/024) | afg 순수 술어; enforcement 런타임(profile bound) |
| §22 non-revival | `non_revival_holds`·`economic_effect_persists`(§6.8) | ADR-002-017 Recovery Barrier·re-arm workflow(런타임)·recon `ConservativeBound`(`recon/records.py:28`) | afg 술어; barrier enforce 런타임; recon bound 주입 소비 |
| §7 authority separation | `ActionFlowGovernorEffect` all-false·`governor_grants_no_authority`(§6.7) | rcl `RclAuthorityEffect`·final egress confinement(ADR-002-013) | afg all-false 생산; egress confinement 런타임 |
| §9 broker-command | command **identity/digest**(scalar) binding | **ADR-002-020 IOC** exact command bytes 구성(미비준·본 계약 미의존) | afg는 identity/digest scalar만; command 구성 침범 금지(§0.2·§4 line 99) |

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **앵커는 AFG-INV-001..014(§6)·AFG-AC-
001..012(§27)·§-clause·SAFE-###**이며 **새 시리즈를 창작하지 않는다**(§0.4f). **fail-closed discipline**: 미증명/
초과/None/stale/expired/label에 대한 술어는 절대 vacuous permissive/작은 vector가 되지 않으며, live 허용은 *양성
증명*을 요구하고, 각 가드에 **both-ways canary**(가드가 실제로 발화함)를 붙인다.

### 4.1 complete-scope / no-local-headroom 중앙 불변식 (중앙 — ADR §10 line 274–278; AFG-INV-001; §1 line 25)

**중앙 결정**: "Action flow SHALL be bounded over every applicable shared scope ... A component may not select a
narrower scope merely because it cannot observe another producer or because a broker documents limits
incompletely. Unknown dependency or limit scope expands to the smallest conservative containing scope and blocks
new normal risk"(§1 line 25). 실현(구조적):

1. **`scope_graph_complete`에 permissive 기본값 부재**: 오직 모든 applicable `ActionFlowScopeKind`(§10 line 274,
   17종)가 snapshot에 포함될 때만 `True`. 하나라도 누락/unknown-applicability ⇒ **smallest conservative containing
   scope로 확장·`False`**(§10 line 276). "account-local success ≠ credential/session/IP/route/broker-global 독립"
   (§10 line 276).
2. **local counter·process·priority ≠ headroom**(§10 line 278): separate process/node/region/local counter가
   distributed capacity를 확립하지 못함 — rcl `producer_local_counter`/`scheduler_priority` "create **no** headroom;
   the reducer never reads them for capacity"(`records.py:127–128` 실측 동형). independence는 allocation/refill/
   broker-enforcement/**credential·session state**/failure-domain/final-route **6축** 분리 **증거** 필요(v1.2
   에라타 — §10 line 278 원문 6축).
3. **headroom 방향(부등호 검산 #6)**: admission = `aggregate_usage(committed) ≤ effective_limit(hard, runtime)`
   차원별. `effective_limit`(`vector.py:139`)이 `min(hard, runtime)`·None⇒None(fail-closed)을 이미 구현 —
   **usage > limit ⇒ DENY**(진리표: usage=None⇒UNKNOWN·limit=None⇒UNKNOWN·usage≤limit⇒pass·usage>limit⇒DENY).
   REUSE로 방향 전치 위험 제거.

**canary(both-ways)**: (a) 한 credential/session/route/broker-global scope 누락, 또는 local-counter-only 근거 ⇒
`False`/확장(가드 발화; §27 AFG-AC-001); 빈 scope set ⇒ `UNKNOWN`(§4.7); (b) 전 applicable scope 포함 + independence
증거 ⇒ `True`(양성 side — 정당한 admission을 막지 않음).

### 4.2 bounded-amplification / cause-lineage 중앙 불변식 (ADR §11 line 284–296; AFG-INV-002; AFG-EV-002)

- **모든 root cause 유한 bound**(AFG-INV-002 line 161): `amplification_bounded(envelope, observed) -> bool`는
  fan-out·depth·attempt·mutation·queue·elapsed-time·duplicate/redelivery/failover/reconnect/replay expansion이 전부
  주입 envelope bound **이하**일 때만 `True`. **unknown or unbounded amplification is denial**(§5.8 line 141).
- **cause lineage 완전성**(§11 line 284): `cause_lineage_complete(cause) -> bool`는 immutable root-cause identity +
  complete parent lineage 보유 시에만 `True`. missing/cyclic/forked-beyond-bound/inconsistent ⇒ `False`·`UNKNOWN`·
  contain(§11 line 296).
- **duplicate ≠ new allowance**(§11 line 294): "A duplicate event does not create another allowance. Concurrent
  consumers of the same cause share one envelope." ⇒ 동일 root cause의 관측 반복이 envelope를 리셋하지 못함.
- **changed command = 새 action**(§11 line 294): quantity/price/route/account/instrument/action-class/effect/
  session/credential/broker identity 변경 ⇒ 새 action·fresh construction/risk/flow/authority/capability 요구(§27
  AFG-AC-002).
- **canary(both-ways)**: (a) fan-out/depth/attempt가 bound 초과, 또는 lineage missing/cyclic, 또는 duplicate가 새
  allowance 시도 ⇒ `False`/`UNKNOWN`(가드 발화); 빈 lineage/빈 envelope ⇒ `UNKNOWN`(§4.7); (b) 전 count ≤ bound +
  lineage 완비 ⇒ `True`.

### 4.3 exact-binding / permit single-use / atomic coverage 중앙 불변식 (ADR §13 line 319–342; AFG-INV-003/004/005)

- **one exact binding**(AFG-INV-003 line 165): decision·permit는 one exact action identity/command/operation/cause/
  lineage/scope/generation/resource-vector를 binding하고 "cannot be patched, unioned, widened, transplanted, or
  replayed." digest 정합(재계산 일치) 시에만 `True`.
- **permit single-use**(§13 line 342): `permit_single_use(permit) -> bool`는 permit이 exact·single-use(nonce·
  `single_use: bool=True`)이고 claimed/ambiguous/lost/conflicting이 아닐 때만 consumable — rcl `TransmissionCapability`
  `nonce`/`single_use`(`records.py:295–296`) 패턴 동형. unused permit 해제는 "never claimed and cannot reach any
  broker path" 증명 시에만(§13 line 342); claimed/ambiguous ⇒ consumed/quarantined 유지.
- **atomic economic+flow coverage**(AFG-INV-005 line 173·§13 line 330): `atomic_economic_flow_coverage(economic_ref,
  flow_vector) -> ActionFlowResult`는 **경제 vector와 action-flow vector 둘 다 exclusively committed**일 때만
  `GRANT`; 하나라도 None/미commit ⇒ no permit(§13 line 330 "commit both ... or ... cannot leave a live-send-capable
  partial state"). 원자 transaction 실행은 rcl 런타임(§29 q2). **release 비대칭**(§13 line 342): "Releasing
  action-flow capacity never releases economic capacity without its separate Final Quantity Proof rules."
- **canary(both-ways)**: (a) permit 재사용/replay, 또는 경제 present·flow None(또는 역), 또는 decision patch/union ⇒
  `False`/no-`GRANT`(가드 발화; §27 AFG-AC-007); 빈 flow vector ⇒ restrictive(§4.7); (b) 단일 정합 binding + 양
  coverage 증명 ⇒ consumable·`GRANT` 가능.

### 4.4 refill-not-manufactured / counter-integrity 중앙 불변식 (ADR §18 line 403–407; AFG-INV-004 line 169 "replenishes" + AFG-INV-007 line 181; AFG-EV-008) — M6: INV-013(Stale Generations Fenced, line 205)은 refill 아님, §5.4 `generation_fenced`로 분리

- **approved time + RCL history만 refill**(§18 line 404): `refill_conservative(...) -> ActionFlowResult|bool`는
  trustworthy-time(ADR-002-008) + RCL committed history로만 replenish. wall-clock/clock-recovery/restart/broker-
  timestamp/newly-healthy-source ⇒ headroom 제조 **불가**(§18 line 405).
- **cross-host non-subtraction**(§18 line 403): "Monotonic values from different hosts or processes SHALL NOT be
  directly subtracted." consumer-local elapsed는 local monotonic basis만 — time `MonotonicReading` "continuity
  subtraction is never performed"(`elements.py:112`)·`monotonic_anchor_value` required injected(`:82`) 소비.
- **clamp toward restriction**(§18 line 405): negative age·future issue time·uncertainty·discontinuity·unknown
  continuity ⇒ restriction 방향 clamp, never refill. `CanonicalDecimal` finite REUSE(NaN/infinity 구성-거부).
- **time recovery ≠ revival**(§18 line 407): time recovery ⇒ new Time Health Generation·permits/decisions/leases/
  live-authority revive 없음.
- **canary(both-ways)**: (a) wall-clock jump·monotonic discontinuity·cross-host subtract·restart·stale refill·
  window-boundary race·counter divergence ⇒ restriction(가드 발화; §27 AFG-AC-008 "No event may manufacture
  headroom"); 미확립 continuity ⇒ restrictive(§4.7); (b) approved time + RCL history ∧ finite age ⇒ refill 가능.

### 4.5 no-blind-retry / cancel-ACK-not-FQP 불변식 (ADR §14/§15; AFG-INV-008/009)

- **missing ACK = potentially live**(AFG-INV-008 line 185·§14 line 350): `no_blind_retry(...) -> bool`는 missing
  ACK·timeout·reset·proxy-fail·SDK-exception·redirect·rate-limit-response가 non-acceptance를 증명하지 못함을 강제 —
  attempt는 potentially live 유지; retry count/elapsed/backoff/repeated-response가 UNKNOWN을 known rejection으로
  변환 못 함. orthostate `SENT_UNCONFIRMED`(`vocabulary.py:86`) 좌표 소비; attempt-축 positive 대응물은
  `SEND_FAILED_PROVEN`(`:88`)이다(m4: `no_potentially_live_proof is True` `predicates.py:461`은
  `intent_transition_allowed`의 **Intent-축** 파라미터이므로 attempt-축 근거가 아니라 "`is True` 정규화 선례"로만
  인용). blind failover(session/endpoint/route/credential/broker/client-order-id) 금지(§14 line 352).
- **cancel ACK ≠ FQP**(AFG-INV-009 line 189·§15 line 358): `cancel_ack_not_final_quantity_proof(...) -> bool`는
  cancel acknowledgement이 capacity release·replacement reuse·retry를 정당화하지 못함을 강제; original+replacement은
  worst overlap/late-fill/reversal/protection-gap 대비 covered. orthostate `BrokerOrderState.CANCELLED` + "a later
  valid fill SHALL be accepted even after a locally observed CANCELLED"(`vocabulary.py` 실측) 좌표 소비.
- **truthy-sentinel 봉합**: orthostate 상태(StrEnum)·`no_potentially_live_proof`(bool|None) 소비 시 `is True`/
  identity 비교만(non-bool truthy 관통 금지).
- **canary(both-ways)**: (a) missing-ACK 후 retry 시도, 또는 cancel-ACK로 capacity release 시도, 또는 cancel↔submit
  무한 진동 ⇒ `False`(가드 발화; §27 AFG-AC-003/004); (b) POSITIVE_SEND_FAILURE_PROOF(orthostate `SEND_FAILED_
  PROVEN`) + 완전 evidence/capability/coverage/authority ⇒ governed retry 가능(양성 side, §14 line 350).

### 4.6 representation ≠ enforcement (ADR §1 line 17/21; §17; AFG-INV-011)

`ActionFlowDecision`·`GRANT`·permit·admissibility bool은 **비전송·비-enforcing representation**이다 — "GRANT" 기록이
order를 전송하거나 capacity를 commit하거나 permit을 claim하거나 Live Authorization을 발급하지 않는다. §1 line 17
verbatim "A `GRANT` is not capacity or permission to send"·§1 line 19 "The permit is a mandatory precondition, not
transmission authority"·§5.5 line 129 "not ... a Transmission Capability." §23 line 483 "Logs, metrics, dashboards,
replay, and post-hoc alerts are evidence. They do not authorize, serialize, reserve, prevent, transmit, release
capacity, or re-arm." ⇒ afg에 **egress transmit·capacity mutate·permit-consume/claim·capability issue·live-scope
set 메서드가 부재**(구성적 부재). `ActionFlowGovernorEffect` all-false가 이를 타입 수준으로 봉인(§6.7).

### 4.7 ∅-공허 fail-closed (양방향 명시 — #10/#12/#13 code-review MAJOR 교훈)

빈 입력의 **모든 방향**을 명문화한다(#12 교훈: 표의 방향이 하나뿐이면 불변식의 전 금지 동사와 대조해 커버리지
명시). AFG 금지 동사(§1·AFG-INV; **Gap-4 확장**): **narrower-scope-select**(§1 line 25)·**patch/union/widen/
transplant/replay**(AFG-INV-003 line 165)·**borrow/consume/relabel reserve**(AFG-INV-006 line 177)·**blind-retry**
(AFG-INV-008)·**release**(AFG-INV-012 line 201)·**revive/auto-re-arm**(AFG-INV-014 line 209)·**create protective
authority**(§9 line 268)·**enlarge Hard Safety Envelope**(§8 line 248)·**merge-permits / regenerate-command /
backlog→authority**(§12 line 313)·**repay-reserve-later**(§16 line 370)·**delegate materiality/scope/reserve to
producer**(§8 line 248)·**assume-zero-counter on restart**(§22 line 463)·**recalculate-favorable-vector /
invent-cause / change-action-class at egress**(§17 line 397).

| 빈 입력 | 금지 방향(vacuous permissive 차단) | 허용 방향(양성 side) | 근거 |
|---|---|---|---|
| **빈 scope set** | 평가 scope 부재 ⇒ "no shared limit" 아님 ⇒ AFG-INV-001 완전성 증명 불가 ⇒ `UNKNOWN`(smallest containing scope 확장 — §1 line 25 unknown-dependency 규칙) | 적용 가능한 전 scope(global..action-class) 포함 + independence 증거 ⇒ 평가 가능 | §1 line 25; §10 line 274; AFG-INV-001 line 157 |
| **빈 dimension set** | 빈 governed dimension ⇒ "no resource use" 아님 ⇒ shared limit 증명 불가 ⇒ `UNKNOWN`/`DENY` | policy·broker·action이 요하는 전 dimension 완비 ⇒ 평가 가능 | §8 line 238·§9 line 254 (uncounted class 금지) |
| **빈 required-scope(consumer 미지정)** | required 빈 ⇒ 공허 ADMISSIBLE 금지 ⇒ restrictive | consumer가 요구 scope 명시 + 전부 covered ⇒ 통과 | §8 line 248 (omitted fields restrictive); #10 빈-required 공허 ADMISSIBLE 재발 방지 |
| **빈 amplification envelope** | bound 미제시 ⇒ "unbounded" ⇒ denial(§5.8 line 141) | 전 bound(fan-out/depth/attempt/…) 주입 ⇒ 평가 가능 | §5.8 line 141·§11 line 290 |
| **빈 lineage** | root/parent 부재 ⇒ `UNKNOWN`·contain(§11 line 296) | root + complete parent lineage ⇒ 평가 가능 | §11 line 284/296 |
| **None magnitude/limit** | None ⇒ `UNKNOWN`/`DENY`(§4.1·rcl `aggregate_usage` None⇒None `vector.py:132`) | finite magnitude + finite limit ⇒ 비교 가능 | §12; AFG-INV-007 line 181 |
| **빈 flow vector**(m10) | flow vector 미제시 ⇒ atomic coverage 증명 불가 ⇒ `atomic_economic_flow_coverage` no-`GRANT` | 경제 ref + 전 dimension covered flow vector ⇒ `GRANT` 가능 | §13 line 330; AFG-INV-005 |
| **빈 permits**(m10·M8) | permit 부재/merge 대상 없음 ⇒ `permit_not_merged`/`queue_does_not_extend_validity` restrictive | 단일 유효 permit ⇒ reorder 통과 | §12 line 313 |
| **빈 credible_containing_scopes**(m10·C1) | containing scope 후보 부재 ⇒ `shared_limit_conservative` `UNKNOWN`(largest 확립 불가) | credible containing scope 집합 present ⇒ largest 반환 | §10 line 276 |

**양방향 규율**: 각 빈-입력 가드는 (a) 금지 방향(가드 발화 canary)과 (b) 허용 방향(정당 통과 canary)을 **둘 다**
property로 검증한다(§7). vacuous-grant도 vacuous-block(정당 admission 차단)도 결함이다 — 전자는 안전 위반, 후자는
가용성 위반(#12 both-ways 교훈). **동사별 전용 canary 커버리지(Gap-4 확장)**: narrower-scope-select(§5.1)·patch/
union/replay(§5.3)·borrow/repay-reserve(§6.4)·blind-retry(§6.1)·release(§6.8)·revive/assume-zero-counter(§6.8)·
create-protective-authority(§6.7)·enlarge-envelope(§5.1)·**merge-permits/regenerate-command/backlog→authority**
(§5.3, M8)·**delegate-to-producer**(§5.1 policy 계약)·**recalculate-favorable/invent-cause/change-class-at-egress**
(§6.5 — final egress는 decision을 widen 못 함, §17 line 397)가 각 절에 전용 named canary를 갖는다.

---

## 5. core 술어 — scope·amplification·permit·refill·cancel (AFG-EV-001/002/004/007/008 substrate)

**핵심 난제**: distributed action-flow의 보수성·유한 amplification·permit 정확성·refill 무제조를 **순수 함수**로
저작하되, (i) rate·burst·queue·fan-out·broker limit을 **주입 파라미터**로 두어 하드코딩 수치·broker 판정을 배제하고
(§8), (ii) **fail-closed(§4)를 구조로** 지키며(permissive 기본·vacuous 부재), (iii) unknown scope·missing lineage·
missing ACK·cancel ACK·changed command를 **most-restrictive**로 처리한다.

### 5.1 scope graph 완전성 + no-local-headroom (§10; AFG-EV-001 substrate, core L1 슬라이스)

`scope_graph_complete(snapshot: ActionFlowStateSnapshot|None, required_scopes: frozenset[ActionFlowScopeKind],
inputs) -> bool`:

- `True` **only** when snapshot 존재 ∧ 모든 applicable `ActionFlowScopeKind`(§10 line 274, 17종) 포함 ∧ 각 scope가
  allocation/refill/broker-enforcement/**credential·session state**/failure-domain/final-route **6축**
  independence 증거 보유(§10 line 278 원문 verbatim: "allocation, refill, broker enforcement, credential/session
  state, failure domain, and final route" — v1.2 에라타로 credential/session state 축 복원).
- **narrower-scope-select 거부**(§1 line 25): component가 다른 producer 미관측·broker 불완전 문서화를 이유로 좁은
  scope 선택 불가 ⇒ unknown ⇒ smallest conservative containing scope 확장·`False`.
- **local-headroom 거부**(§10 line 278): local counter·separate process·scheduler priority가 distributed headroom
  아님(rcl `records.py:127–128` 동형). headroom = `aggregate_usage ≤ effective_limit`(rcl REUSE, §4.1 부등호 검산).
- **enlarge-envelope 전용 canary(§4.7)**: admission이 주입 Hard Safety Envelope max 초과 시 DENY(§8 line 248
  "Runtime configuration may narrow ... but cannot enlarge"); envelope 출처가 runtime/broker/model이면 거부.
- **`shared_limit_conservative` 술어(C1 정식 정의 — v1.0은 §3.4에 이름만 존재)**: `shared_limit_conservative(
  documented_scope_status: str|None, claimed_scope: ActionFlowScopeKind|None, credible_containing_scopes:
  frozenset[ActionFlowScopeKind], independence_evidence: bool|None) -> ActionFlowScopeKind|UNKNOWN` — **두 보수
  규칙(C1)**: (i) `documented_scope_status`가 incomplete/contradictory/stale/unverified/None ⇒ **largest credible
  containing scope 반환**(§10 line 276 "shared across the largest credible containing scope"); (ii)
  `independence_evidence is not True` ⇒ claimed_scope 불신·containing scope로 확장(§10 line 278). documented 완비·
  검증 + independence 증거일 때만 claimed_scope 유지. 빈 `credible_containing_scopes` ⇒ `UNKNOWN`(§4.7). **canary
  (both-ways, M8/C1)**: (a) documented 불완전 + claimed=ACCOUNT ⇒ BROKER/GLOBAL(largest credible) 승격(가드 발화);
  (b) documented 완비 + independence 증거 ⇒ claimed=ACCOUNT 유지(양성 side — 정당한 좁은 scope 유지).
- **delegate-to-producer 거부(Gap-4)**: policy는 materiality/scope/reserve classification을 producer에 위임 못 함
  (§8 line 248) — producer가 scope/class를 self-declare하면 거부.
- **canary(AFG-AC-001, both-ways)**: (a) 한 scope 누락·local-counter-only·envelope enlarge 시도·producer self-scope
  ⇒ `False`/확장(가드 발화); 빈 scope ⇒ `UNKNOWN`(§4.7); (b) 전 required scope + independence 증거 + envelope 이하
  ⇒ `True`.

### 5.2 amplification + cause lineage (§11; AFG-EV-002 substrate, core L1 슬라이스)

`amplification_bounded(envelope: ActionAmplificationEnvelope, observed, inputs) -> bool` ∧ `cause_lineage_complete(
cause: ActionCause|None) -> bool`:

- **유한 bound**(§11 line 284–292): fan-out·depth·attempt·mutation·query·queue·in-flight·elapsed-monotonic·
  duplicate/redelivery/failover/reconnect/replay expansion ≤ 주입 envelope bound(각 `CanonicalDecimal`/int). unknown/
  unbounded ⇒ denial(§5.8 line 141).
- **lineage 완전성**(§11 line 284/296): immutable root + complete parent lineage; missing/cyclic/forked-beyond-bound/
  inconsistent ⇒ `False`·`UNKNOWN`·contain.
- **duplicate/concurrent 공유**(§11 line 294): 동일 root cause 관측 반복·concurrent consumer가 하나의 envelope 공유
  (budget reset 불가). changed command ⇒ 새 cause·fresh artifacts(§11 line 294).
- **canary(AFG-AC-002, both-ways)**: (a) bound 초과·lineage cyclic/missing·duplicate가 allowance 시도 ⇒ `False`/
  `UNKNOWN`(가드 발화); 빈 envelope/lineage ⇒ `UNKNOWN`(§4.7); (b) 전 count ≤ bound + lineage 완비 ⇒ `True`.

### 5.3 exact binding + permit single-use + atomic coverage (§13; AFG-EV-007 substrate, core L1 슬라이스)

`permit_single_use(permit: ActionFlowPermit|None) -> bool` ∧ `atomic_economic_flow_coverage(economic_ref: str|None,
flow_vector: CapacityVector|None, inputs) -> ActionFlowResult` ∧ decision content ref 생산:

- **exact binding**(AFG-INV-003 line 165): decision·permit가 one exact action identity/command/cause/lineage/scope/
  generation/vector binding; patch/union/widen/transplant/replay ⇒ `False`. digest 정합 시에만.
- **permit single-use**(§13 line 342): nonce·`single_use: bool` + not claimed/ambiguous/lost/conflicting ⇒
  consumable. unused 해제는 "never claimed and cannot reach any broker path" 증명 시에만.
- **atomic coverage**(AFG-INV-005 line 173·§13 line 330): 경제 ref present ∧ flow vector 전 dimension covered
  (`aggregate_usage ≤ effective_limit`, rcl REUSE) ⇒ `GRANT` 가능; 하나라도 None ⇒ no `GRANT`. **원자 transaction은
  rcl 런타임**(§29 q2 — cyclic dependency 회피는 런타임 프로토콜).
- **decision content ref 생산(rcl seam)**: `decision_id`·`decision_generation`·`canonical_decision_digest`(§3.4) →
  rcl `GrantDecisionRef` 상류. **forward-only**: reservation 좌표·미래 commitment identity 미포함(non-cyclic).
- **§12 queue/permit/backlog 술어(M8 신설 — §12 전면 매핑)**: `queue_does_not_extend_validity(queued_item,
  prereq_generation, current_generation) -> bool`(§12 line 311 "Queueing does not extend permit, authority,
  context, constraint, decision, capability, or policy validity. Work whose prerequisites expire in queue is
  denied and cannot be silently refreshed" — queue 내 prereq 만료 ⇒ denied·silent-refresh 불가) ∧
  `permit_not_merged(permits) -> bool`(§12 line 313 "cannot merge permits") ∧ `backlog_is_not_authority(
  scheduler_reorder, independent_prereqs_valid: bool|None) -> bool`(§12 line 313 "cannot ... regenerate a command,
  or turn backlog into current authority"; scheduler는 independent prereq이 valid한 action만 reorder,
  `independent_prereqs_valid is not True ⇒ False`). **canary(both-ways)**: (a) queue 내 만료 prereq silent-refresh·
  두 permit merge·backlog→authority 승격·command regenerate ⇒ `False`(가드 발화); 빈 permits ⇒ restrictive(§4.7);
  (b) prereq 유효한 단일 permit reorder ⇒ 통과.
- **canary(AFG-AC-007, both-ways)**: (a) permit 재사용/replay·경제-only 또는 flow-only·decision patch ⇒ `False`/
  no-`GRANT`(가드 발화); 빈 vector ⇒ restrictive(§4.7); (b) 단일 정합 binding + 양 coverage ⇒ consumable·`GRANT` 가능.

### 5.4 time / refill / counter integrity (§18; AFG-EV-008 substrate, core L1 슬라이스)

`refill_conservative(time_valid: bool|None, monotonic_continuity_id: str|None, age, inputs) -> ActionFlowResult|
bool`:

- **approved time + RCL history**(§18 line 404): trustworthy-time(주입 validity flag) + RCL committed history로만
  refill. wall-clock/recovery/restart/broker-timestamp ⇒ 제조 불가(§18 line 405).
- **cross-host non-subtraction**(§18 line 403): monotonic 값은 same-continuity 내에서만 비교 — time
  `elapsed_within_continuity`(`predicates.py:73`, 전용 술어 M7; 다른 continuity ⇒ None)·`elements.py:112`
  "continuity subtraction is never performed" 주입 소비; `monotonic_continuity_id` 불일치 ⇒ subtract 금지·
  restrictive. snapshot age는 time `snapshot_age_admissible`(`:287`) 주입.
- **clamp toward restriction**(§18 line 405): negative age·future issue·uncertainty·discontinuity·unknown continuity
  ⇒ restriction clamp(`CanonicalDecimal` finite 검사; time_valid `is not True` ⇒ restrictive).
- **`generation_fenced` 술어(M6 — INV-013 분리)**: `generation_fenced(artifact_generation: int|None,
  current_generation: int|None) -> bool`(AFG-INV-013 line 205 "Stale policy, flow, writer, recovery, authority,
  capability, credential, session, route, and egress generations cannot allocate, consume, or transmit";
  `tos.ordering.compare_order`로 L1-decidable — `artifact_generation < current_generation` 또는 어느 쪽 None ⇒
  fenced `False`). **§18 refill과 별개 축**(refill=INV-004/007, generation fence=INV-013). time
  `recovery_generation_revives_nothing`(`time/predicates.py:499`) 주입 소비(§3.4). AFG-EV-007/009 대상. **canary
  (both-ways)**: (a) stale/None generation ⇒ `False`(fenced, 가드 발화); (b) current generation 일치 ⇒ 통과.
- **canary(AFG-AC-008, both-ways)**: (a) wall-clock jump·cross-host subtract·counter divergence·stale refill ⇒
  restriction(가드 발화; §27 AFG-AC-008); 미확립 continuity ⇒ restrictive(§4.7); (b) approved time + same continuity
  + finite age ⇒ refill 가능.

### 5.5 evidence 재구성 substrate (§23; AFG-EV-001/002/004/007/008 공통)

- **frozen digest-bound 레코드**: `ActionFlowPolicy`/`ActionFlowStateSnapshot`/`ActionFlowDecision`/`ActionFlowPermit`
  각 결정을 durable evidence에서 재구성 가능케 함(§23 line 471–479 exact policy/generation/snapshot/decision/permit/
  cause/lineage/amplification/scope/vector/limit/reserve + queue/in-flight/claim/SEND_STARTED/first-byte/ACK/fill/
  cancel/reconciliation transitions). **replay ENGINE 자체는 ADR-002-016**(not-Phase-1). **Evidence Is Not
  Authority**(§23 line 483; §4.6). evidence 참조는 scalar(id/gen/digest).
- **canary**: id⊥digest이므로 same-id/diff-bytes decision·double-spend permit ⇒ `classify_record_pair`
  `CRITICAL_CONFLICT`(위조·contradictory decision·permit reuse 탐지·양쪽 보존, no last-write-wins).

---

## 6. predicate-only 술어 — retry·classification·reserve·currentness·partition·authority·recovery (AFG-EV-003/005/006/009/010/011/012 substrate, 최소 ≥ L2·닫지 않음)

각각 **L1-decidable substrate**를 저작하나 **어떤 AFG-EV도 닫지 않는다**(최소 ≥ L2·+Security/+Broker 잔여).
**(+ AFG-EV-004 core L1 슬라이스는 §6.2에 배치 — register상 `EV-L1/3+Broker`이므로 §5/§7 core로 상호참조; m3.)**

### 6.1 no-blind-retry (§14; AFG-EV-003 substrate, predicate-only)

`no_blind_retry(attempt_state, broker_order_state, idempotency_proven: bool|None, budget_remaining: int|None,
inputs) -> bool` — §4.5 중앙 불변식. missing-ACK/timeout/reset ⇒ potentially live(orthostate `SENT_UNCONFIRMED`
좌표); retry는 broker-side idempotency 양성 증명(brokercap `SUBMISSION_IDEMPOTENCY` 주입) + 완전 evidence/capability/
coverage/authority + budget(protective `budget_remaining>0`) 시에만 governed. blind failover 금지. **broker
idempotency 증명·SDK/reconnect 통합은 not-Phase-1**(brokercap INSTANCE·+Broker). **∅/None canary(Gap-5)**:
`no_blind_retry`의 attempt_state/broker_order_state/idempotency_proven/budget_remaining이 **전부 None ⇒ `False`**
(미증명 ⇒ no retry, 가드 발화); positive 4-tuple(`SEND_FAILED_PROVEN` + idempotency `is True` + budget>0 + 완전
authority) ⇒ 통과. 최소 `EV-L2/3+Broker`.

### 6.2 cancel-ACK-not-FQP / oscillation-bounded (§15; AFG-EV-004 substrate, **core L1 슬라이스이나 broker 통합 잔여**)

`cancel_ack_not_final_quantity_proof(broker_order_state, inputs) -> bool` ∧ `oscillation_bounded(cause, envelope) ->
bool` — §4.5. cancel ACK ≠ capacity release/replacement reuse/retry(orthostate `CANCELLED`+later-fill 좌표);
original+replacement covered for overlap/late-fill/reversal/protection-gap; cancel↔submit 무한 진동 금지·budget
reset용 새 cause 금지(oscillation은 §5.2 amplification envelope 공유). reserve 부재 ⇒ trapped exposure·contain(§15
line 362). **AFG-EV-004는 register상 `EV-L1/3+Broker`**(core L1 슬라이스) — L1 substrate는 여기, **+Broker 통합은
이연**.

### 6.3 complete action / resource classification (§9; AFG-EV-005 substrate, predicate-only)

`action_class_conservative(claimed_class, applicable_classes, vector) -> ActionClassKind` — most conservative
applicable class·vector가 conflict 시 govern(§9 line 268); label이 더 permissive class 창조 못 함(§7 line 218);
submit뿐 아니라 cancel/amend/replace/query/session/reconnect/SDK 전부 counted(§9 line 254). **common-mode resource
소진·broker 통합은 EV-L2·+Broker**. 최소 `EV-L2/3+Broker`.

### 6.4 protective flow reserve exclusivity (§16; AFG-EV-006 substrate, predicate-only)

`reserve_exclusive(claim: ProtectiveFlowReserveClaim, is_reserved: bool|None, inputs) -> bool` ∧
`priority_is_not_reserve(...) -> bool` — normal traffic이 minimum reserve를 borrow/consume/relabel 불가(AFG-INV-006
line 177). **protective `is_reserved_guarantee` 결과(bool) 주입 소비**(`predicates.py:129`; PHYSICALLY/LOGICALLY_
RESERVED만 guaranteed — **`GuaranteeLevel` `vocabulary.py:32`, M1: `ReserveGuaranteeLevel` 아님**; **`is_reserved is
not True ⇒ not reserved`** — truthy-sentinel 봉합). **priority alone ≠ reservation**(§16 line 372 "A high-priority
queue without exclusive capacity is `PRIORITIZED_ONLY`"). inseparable common-mode limit ⇒ normal admission을 reserve
보존 수준 이하로 축소 또는 protective 하향(§16 line 374). **∅/None canary(Gap-5)**: is_reserved=None ⇒ `False`(미증명
reserve ⇒ borrow 불가, 가드 발화); PHYSICALLY_RESERVED(bool True) ⇒ 통과. **common-mode 독립·+Security는 런타임**.
최소 `EV-L2/3+Broker+Security`.

### 6.5 currentness / invalidation (§17/§19; AFG-EV-009 substrate, predicate-only)

`currentness_invalidation(triggers, decision, permit) -> bool` — material change(§19 line 413: policy/broker-limit/
constraint/session/credential/route/endpoint/scope-graph/time-health/queue-in-flight/cause-lineage/RCL/protective-
reserve/capability/consumer-compatibility) ⇒ affected unclaimed decision·permit invalidate. **cache/TTL/heartbeat/
service-health/broker-connection/prior-success/queue-position/absence-of-invalidation ≠ currentness**(§17 line 391).
race ⇒ potentially-live·permit consumed/quarantined·economically covered·blind-retry 금지(§17 line 395).
**materiality 기본값(Gap-7·§5.10 line 149 verbatim "Unknown materiality is material")**: `is_material(change,
materiality_known: bool|None) -> bool`에서 **materiality 미상(None)/미선언 ⇒ material=`True`**(invalidate; §2.1
extra="forbid"·§4.7 fail-closed 정합). **recalculate-favorable/invent-cause/change-class at egress 금지(Gap-4)**:
final egress는 decision을 widen/favorable-recalculate/invent-cause/change-class 못 함(§17 line 397) — currentness
술어가 egress override를 `False`로 차단. **active RCL/final-egress currentness enforcement은 런타임**(profile bound
`B_action_flow_invalid_to_rcl/egress`). 최소 `EV-L2/3+Security`.

### 6.6 partition / stale-writer / protective lease (§20; AFG-EV-010 substrate, predicate-only)

`partition_lease_exclusive(lease_admissible: Admissibility|None, remaining_budget: int|None, monotonic_continuity_id,
inputs) -> bool` — control-plane partition 중 no new normal permit(§20 line 425); exclusive pre-issued scope-limited
lease + monotonic local sub-budget만 소비(§20 line 427); lease가 remote/wall-clock refill 불가; loss of exclusivity/
continuity/remaining-budget ⇒ deny. **protective `partition_lease_admissible` 결과 주입 소비**(**`Admissibility`
StrEnum 반환 ADMISSIBLE/TRAPPED/PROHIBITED, `predicates.py:460`·`vocabulary.py:118/137` — M2, bool|None 아님**;
**`lease_admissible is Admissibility.ADMISSIBLE`로만 통과** — TRAPPED/PROHIBITED/None ⇒ deny). stale writer(old RCL/
governor/scheduler/egress)는 hard-fence 전까지 potentially active(§20 line 429). **∅/None canary(Gap-5)**:
lease_admissible=None/TRAPPED/PROHIBITED 또는 remaining_budget None/<=0 ⇒ `False`(가드 발화); ADMISSIBLE + budget>0 +
same continuity ⇒ 통과. **quorum/fence enforce는 런타임**. 최소 `EV-L2/3+Security`.

### 6.7 authority separation / all-false (§7/§24; AFG-EV-011 substrate, predicate-only)

`ActionFlowGovernorEffect` all-false(§4.6·AFG-INV-011: rcl `RclAuthorityEffect` 동형·어떤 True도 unconstructable) +
`governor_grants_no_authority(effect) -> bool`. §7 line 220 "Governor SHALL NOT mutate a budget, issue authority, or
transmit"·§7 line 229 "The Action Flow Governor SHALL NOT hold a live broker credential, signer, session, route, or
endpoint capability." **governor↛live route·egress bypass·common-mode privilege는 +Security 런타임**(§24 line 500).
최소 `EV-L2/3+Security`.

### 6.8 non-revival + economic continuity (§19/§22; AFG-EV-012 substrate, predicate-only)

`non_revival_holds(...) -> bool`(무조건 True — restart/rollback/restore/failover/reconnect/backoff-expiry/queue-drain/
counter-refill/broker-throttle-recovery/matching-replay/improved-health가 old decision/permit/capability/budget/
authority/live-scope를 **revive 못 함**, §22 line 465·AFG-INV-014 line 209; "No automatic re-arm is permitted") ∧
`economic_effect_persists(...) -> bool`(permit/decision/policy/authority/retry-window/queue-item expiry가 possible
broker/economic effect를 expire 못 함, AFG-INV-012 line 201·§19 line 419; missing ACK potentially live·cancel ACK
insufficient). **Recovery Barrier(ADR-002-017)·governed re-arm enforce는 런타임**(§22 line 465). recon
`ConservativeBound` 주입 소비(conflicting evidence ⇒ conservative 확대). time `recovery_generation_revives_nothing`
(`time/predicates.py:499`) 주입 소비(§3.4·M7). **∅/None canary(Gap-5)**: `non_revival_holds`는 무조건 True(recovery
입력이 무엇이든 old artifact revive 안 함); `economic_effect_persists`는 permit/decision expiry·missing/None ACK ⇒
`True`(effect 지속·release 불가, 가드 발화); positive Final Quantity Proof ⇒ release 가능(양성 side; orthostate/rcl
FQP 규칙). **assume-zero-counter on restart 금지(Gap-4·§22 line 463)**: restart/restore 시 counter=0·empty queue·
unused permit 가정 ⇒ 거부. 최소 `EV-L2/3+Security`.

---

## 7. property-test 하네스 타깃

§1 분류에 정렬한다. **닫는 AFG-EV = 0건** — 어떤 test-target도 AFG-EV closure·acceptance를 주장하지 않는다(규율
태그 부착). 각 술어에 **both-ways canary**(§4·§5·§6)와 **fixture clean-vs-illegal 정합**(#8 교훈)을 건다.

- **core(L1 슬라이스, AFG-EV-001/002/004/007/008 substrate)**: `scope_graph_complete`+`shared_limit_conservative`
  (C1)+no-local-headroom+enlarge canary(§5.1); `amplification_bounded`+`cause_lineage_complete`(§5.2);
  `permit_single_use`+`atomic_economic_flow_coverage`+`queue_does_not_extend_validity`+`permit_not_merged`+
  `backlog_is_not_authority`(M8)+decision content ref(§5.3); `refill_conservative`+counter-integrity+
  `generation_fenced`(M6)+`CanonicalDecimal` finite(§5.4); `cancel_ack_not_final_quantity_proof`+`oscillation_
  bounded`(§6.2, core L1); frozen digest-bound 레코드 재구성·`classify_record_pair` CRITICAL_CONFLICT(§5.5).
  hypothesis property: policy/snapshot/decision/permit/vector/cause/envelope/scope를 무작위 생성해 scope-완전성·
  **shared-limit-방향(C1 largest-vs-smallest 두 규칙)**·amplification-bound·permit-single-use·atomic-coverage·
  **queue≠validity/backlog≠authority(M8)**·refill-integrity·**generation-fence(M6)**·cancel-ACK 불변식을 검사.
  **dimension-id disjointness property(Gap-1)**: afg `ActionFlowDimensionKind` 값 집합 ∩ 경제 dimension-id 집합 = ∅
  회귀(전역 namespace 자기정합·rcl/are/ioc/afg 4소비자). **truthy-sentinel property(양축, M2)**: `ActionFlowResult`
  소비 게이트가 `is GRANT`로만·protective `Admissibility` 게이트가 `is ADMISSIBLE`로만 통과(DENY/UNKNOWN·TRAPPED/
  PROHIBITED 관통 시 실패).
- **predicate-only(AFG-EV-003/005/006/009/010/011/012 substrate, EV 미주장)**: `no_blind_retry`(§6.1);
  `action_class_conservative`(§6.3); `reserve_exclusive`+`priority_is_not_reserve`(§6.4); `currentness_invalidation`
  (§6.5); `partition_lease_exclusive`(§6.6); `governor_grants_no_authority`+all-false(§6.7); `non_revival_holds`+
  `economic_effect_persists`(§6.8).
- **seam cross-check(test-only, MANDATED §3.4)**: `test_seam_rcl`(afg decision ref ↔ rcl `grant_authorizes_exact_
  request`·`ActionFlowVector` 좌표 ↔ `effective_limit`/`aggregate_usage`·all-false ↔ `RclAuthorityEffect`)·
  `test_seam_protective`(afg reserve 소비 ↔ `is_reserved_guarantee` `is not True⇒not reserved`·lease ↔ `partition_
  lease_admissible` **3값(ADMISSIBLE/TRAPPED/PROHIBITED)+None 전수 polarity — `is ADMISSIBLE`만 통과, M2**·budget ↔
  bounded-retry)·`test_seam_orthostate`(afg `no_blind_retry` ↔ `SENT_UNCONFIRMED` polarity·cancel-ACK ↔ `CANCELLED`+
  later-fill)·**`test_seam_brokercap`(M7 — afg `no_blind_retry`/`shared_limit_conservative` ↔ `same_order_retry_
  allowed` `:377`/`rate_admission_ok` `:437`)**·**`test_seam_time`(M7 — afg `refill_conservative`/`non_revival_holds`
  ↔ `elapsed_within_continuity` `:73`/`snapshot_age_admissible` `:287`/`recovery_generation_revives_nothing` `:499`)**.
  테스트 import는 package closure에 불계상(§7.1).
- **∅-공허 회귀(양방향, §4.7 표와 행 1:1 대응 — m10)**: 빈 scope set ⇒ `scope_graph_complete` `UNKNOWN`(non-
  vacuous); 빈 dimension set ⇒ restrictive; 빈 required-scope ⇒ restrictive(#10 봉합); 빈 amplification envelope ⇒
  `amplification_bounded` denial; 빈 lineage ⇒ `cause_lineage_complete` `UNKNOWN`; 빈 flow vector ⇒
  `atomic_economic_flow_coverage` restrictive; **None magnitude/limit ⇒ `UNKNOWN`/`DENY`**(rcl `aggregate_usage`
  None⇒None `vector.py:132`); 빈 permits ⇒ `permit_not_merged`/`queue_does_not_extend_validity` restrictive(M8);
  빈 credible_containing_scopes ⇒ `shared_limit_conservative` `UNKNOWN`(C1). **§4.7 표 9행 ↔ 본 §7 목록 1:1 대응
  (m10)**; **동시에** 각 완비 입력의 정당 통과 canary.

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#5..#13 §7.1 상속)

**allowlist 형식(M9 — denylist 열거 금지)**: `import tos.afg` 후 `{m for m in sys.modules if m.startswith("tos.")}`
의 top-level 패키지 ⊆ **{`tos.canonical`, `tos.ordering`, `tos.rcl`, `tos.afg`}** assert(그 외 모든 tos 형제 —
protective/spg/orthostate/brokercap/time/recon/are/liveauth/authority/capsule/evidence/dsl/**ioc/iap** 및 미래 형제
— 등장 시 실패) + `shared.config`·`os.environ` 흔적·`numpy`/`pandas`/`yaml` 부재 assert. **고정 "12 형제" 열거는
세션 A의 ioc/iap 추가로 stale이었으므로 allowlist가 미래-견고**(M9). required check(`tos-firewall`,
`tools/tos_firewall_check.py` layer-① AST + `.importlinter` layer-② 전이)와 함께 green이어야 §0.3 선언이 능동 성립.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

(1) 목적: afg Phase-1(EV-L1) 순수 모델+property test. (2) 명령: `pytest tos/tests/afg/ -v`. (3) 격리:
hermetic(`.env` 비주입·clock 미접근·네트워크 없음). (4) 결정론: hypothesis 시드 고정·`CanonicalDecimal` scale-
normalize·NaN/infinity 구성-거부. (5) 산출물: property test 결과(EV closure 아님 — 규율 태그). (6) 게이트:
`tos-firewall` required green. (7) 비-acceptance: 어떤 AFG-EV도 닫지 않음(§0.2·VER-002-001 §5).

---

## 8. bounds 주입 + Phase-0

**§8.0 afg decision 구조에 numeric bound 부재**: 전부 enum(`ActionFlowResult`/`ActionClassKind`/`ActionFlowScopeKind`/
`ActionFlowDimensionKind`)·boolean·집합 논리·주입 `CanonicalDecimal`(rate·burst·queue·amplification magnitude·limit·
headroom). ADR §4 non-scope line 105 "numeric rates, bursts, ages, queue sizes, or propagation bounds"는 수치를
**명시 배제**한다 — 전부 **Safety/Verification Profile INSTANCE 측정값**이며 주입 opaque param으로만 담는다. 값 부재
⇒ fail-closed(§4). 값 승인은 Bounds-Approver 게이트(§9.2).

**§8.1 Verification-Profile 키 실측(`measurement_source` 전수 확인)**: ADR-002-022가 요하는 수치 분류 및
VERIFICATION-PROFILE-002.yaml 키 상태(전수 grep):
- **정책 scope pin**: `action_flow_policy_id`(line 64, TBD)·`action_flow_policy_generation`(line 65, null)·
  `action_flow_policy_digest`(line 66, TBD) — 아티팩트 test-harness pin.
- **invalidation-to-RCL(§13/§19)**: `B_action_flow_invalid_to_rcl`(line 282, `value_ms: null` MEASURE,
  `measurement_source: action_flow_generation_decision_permit_and_rcl_admission_trace`) — **이미 존재**.
- **invalidation-to-egress(§17)**: `B_action_flow_invalid_to_egress`(line 289, `null` MEASURE, source
  `action_flow_generation_invalidation_and_egress_boundary_trace`) — **이미 존재**.
- **violation-to-containment(§19)**: `B_action_flow_violation_to_containment`(line 296, `null` MEASURE, "rate/
  amplification/queue/reserve containment") — **이미 존재**.
- **snapshot age(§10)**: `MAX_action_flow_state_snapshot_age_ms`(line 717, `null` — "unknown age denies allocation
  and send") — **이미 존재**.
- **decision age(§13/§17)**: `MAX_action_flow_decision_age_ms`(line 718, `null` — "expiry never expires possible
  broker or economic effect") — **이미 존재**.
- **permit age(§13/§17)**: `MAX_action_flow_permit_age_ms`(line 719, `null` — "stale permit denies send and cannot
  release economic capacity") — **이미 존재**(ARE에는 없던 permit-특유 키).
- **amplification per cause(§11)**: `MAX_action_amplification_per_cause`(line 720, `null` — "unknown or exceeded
  amplification invokes containment") — **이미 존재**(AFG-특유 키).
- **결론(M4 정정 — §30 item 9 전문 대조·절단 인용 제거)**: ADR §30 item 9 line 687 verbatim은 **9카테고리** —
  "Verification Profile **rate, burst, amplification, queue, age, invalidation, containment, refill, and
  protective-reserve** bounds are approved and measured under fault injection." v1.0이 이를 4개(invalidation/
  containment/age/amplification)로 재진술한 것은 절단 인용이었다. **9카테고리 개별 귀속**: (1) **invalidation** →
  `B_action_flow_invalid_to_rcl/egress`(VP-002 실재·null); (2) **containment** → `B_action_flow_violation_to_
  containment`(VP-002 실재·null); (3) **age** → `MAX_action_flow_state_snapshot/decision/permit_age_ms`(VP-002
  실재·null); (4) **amplification** → `MAX_action_amplification_per_cause`(VP-002 실재·null); (5) **rate**·(6)
  **burst**·(7) **queue**·(8) **refill**·(9) **protective-reserve** → **VP-002 키 부재**이나 결함이 아니라 **Broker
  Capability Profile INSTANCE 귀속**: ADR §4 line 105 "numeric rates, bursts, ages, queue sizes ... require an
  approved Verification Profile **and Broker Capability Profile**"·§21 line 437–445(broker별 request/mutation/order/
  cancel/query/session/connection 한도·burst·window·reserve guarantee는 Broker Capability Profile 소관)이므로 이
  5류의 **per-broker 수치**는 broker profile에서 측정·승인되고 afg는 주입 소비한다. ⇒ **VP-002 candidate 신규 키 =
  0건**(timing/age/amplification 4류는 전부 실재·null; rate/burst/queue/refill/protective-reserve는 brokercap
  INSTANCE — under-claim도 over-claim도 아닌 레이어 정합, M4). afg는 전 수치를 신뢰하지 않으며(VP status PROPOSED·
  unapproved bound ≠ approved, VER-002-001 §6) fail-closed 처리(§4).

**§8.2 self-referential 주의(경미)**: afg `ActionFlowPolicy`는 spg Safety Configuration Bundle member(`ACTION_FLOW_
POLICY` `spg/vocabulary.py:209` 실측)이며 VP scope 블록이 policy id/generation/digest를 pin한다. #12(spg)가 다룬
self-reference paradox와 달리 afg는 **Bundle의 member 하나**일 뿐(governance 주체 아님)이라 layering이 단순하다 —
afg는 VP를 import·파싱하지 않고(YAML은 하네스 #3), policy 좌표를 주입 scalar로만 담는다. VP status PROPOSED ⇒ 전
수치 불신.

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

1. `tos/src/tos/afg/` 5-module 저작(`_base.py` shim + all-false `ActionFlowGovernorEffect`·`vocabulary.py`·
   `records.py`·`predicates.py`·`state.py`[permit single-use lifecycle]) + `tos/tests/afg/` property test(§7) +
   seam cross-check(§3.4) + import-closure(§7.1).
2. core 술어(§5): `scope_graph_complete`·`shared_limit_conservative`(C1)·`amplification_bounded`·`cause_lineage_
   complete`·`permit_single_use`·`atomic_economic_flow_coverage`·`queue_does_not_extend_validity`·`permit_not_merged`·
   `backlog_is_not_authority`(M8)·`refill_conservative`·`generation_fenced`(M6)·`cancel_ack_not_final_quantity_proof`·
   `oscillation_bounded` + predicate-only 술어 7종(§6, `is_material` Gap-7 포함) + 5-아티팩트·`ActionCause`·
   `ActionAmplificationEnvelope`·`ProtectiveFlowReserveClaim`·all-false authority(§2) 구현 + `ActionClassKind`/
   `ActionFlowScopeKind`/`ActionFlowDimensionKind`(13종, M5) frozenset + `ActionFlowVector`=`CapacityVector` REUSE +
   dimension-id disjointness property(Gap-1).
3. 미래 caller 런타임(Action Flow Governor / Snapshot Assembly / RCL-admission / Final Egress)이 afg 산출 decision
   scalar·`ActionFlowVector`(`CapacityVector`)·all-false authority를 소비자(rcl commit·`GrantDecisionRef` 주입 슬롯)로
   배선(§3.4; Phase 1 밖·EV-L3). **`ActionFlowVector`는 `CapacityVector` REUSE라 축약 reducer 불요**(§0.4c; #13
   MAJOR-1 동형).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

ADR §29 Open Implementation Questions(12항)·§30 Approval Gate(13조건)에서 Phase-1 밖으로 이연:
1. **RCL vector schema + deterministic transition model**(§29 q1) — multi-scope rate/burst/queue/in-flight/cause-
   amplification/protective-reserve capacity의 rcl 표현(afg는 `CapacityVector` REUSE·rcl이 산술 소유).
2. **atomic economic+flow commit protocol without cyclic dependency**(§29 q2) — Order Conformance Proof·Transmission
   Capability issuance와의 비순환 원자 commit(런타임; **ADR-002-020 IOC 비준·구현 완료 — 본 계약은 command
   identity/digest scalar만 참조·무의존, M9**). LedgerCommandRecord가 경제 vector 1 slot(`proposed_adverse_increment`
   `records.py:185`)만 가지므로 action-flow vector 2번째 slot 추가 vs 동일 vector fold는 미해결 rcl 확장(§10.4-2).
3. **scope graph broker-global/credential/IP/route/session/account/endpoint/venue/action-class/environment 표현**
   (§29 q3) — 실측 shared-limit 조립 런타임.
4. **active RCL/final-egress currentness protocol without permissive cache/circular dependency**(§29 q4·§17) — 런타임.
5. **claim/SEND_STARTED/first-byte/permit-consumption/ambiguous-send ordering + durable evidence**(§29 q5) — orthostate
   attempt 상태 + rcl claim 런타임.
6. **broker SDK retry/redirect/connection-pool/proxy/signer/queue/reconnect/session-manager 최종-claim-boundary 봉쇄**
   (§29 q6) — 런타임 confinement(ADR-002-013).
7. **cause lineage/amplification counter 완전성 across fan-out/replay/failover/redelivery, no self-reset**(§29 q7) —
   런타임(afg는 순수 완전성 술어만).
8. **broker scope별 `PHYSICALLY_RESERVED`/`LOGICALLY_RESERVED` vs `PRIORITIZED_ONLY`/`BEST_EFFORT`/`UNAVAILABLE`**
   (§29 q8) — protective 분류 + brokercap 증거 INSTANCE(afg는 결과 주입 소비).
9. **protective sub-ledger lease overlap/refill prevention + conservative rejoin**(§29 q9·§20) — rcl/protective 런타임.
10. **trustworthy-time 모델(distributed refill·consumer receipt age, no cross-host subtract)**(§29 q10·§18) — time
    런타임(afg는 validity 주입 소비).
11. **cancellation/query/session/reconnect/administrative traffic의 normal vs protective 자원 공유/격리**(§29 q11) —
    런타임 배선.
12. **numeric rate/burst/amplification/age/queue/in-flight/invalidation/containment/recovery bounds 승인**(§29 q12·
    §30 item 9) — VP-002 8키(§8.1 전부 실재·null)의 Bounds-Approver 승인 + fault-injection 측정; per-broker rate/
    burst/queue는 Broker Capability Profile INSTANCE. **candidate 신규 VP-002 키 0건.**
13. **ADR-002-023 IAP approval/consumption/Intent lineage binding**(§30 item 13) — approval/Intent Registry가
    action-flow capacity를 창조하지 않도록 binding(별도 ADR·EV family; IAP는 다음 설계 예정).
14. **ADR-002-016 Evidence Integrity·Replay Capsule**(§23·§29) — replay ENGINE(§5.5 레코드 substrate만 Phase-1).
15. **ARCHITECTURE-GATE-STATUS 명시 acceptance 결정**(§30 item 12) — 실행된 AFG-EV-001..012 + cross-system evidence
    + 독립 리뷰(Independent-Safety-Reviewer 하드 배제, IMPLEMENTATION-PLAN-002 §3).

---

## 10. 개정 로그 + 비준 체크리스트 + 판단 지점

### 10.1 개정 로그

- **v1.2 (2026-07-26) — 에라타 1건(ADR 원문 전사 누락 정정). 비준 효력 유지·재비준 불요.** 구현 단계의 적대적
  코드 리뷰가 **MAJOR-4**로 적발: 본 계약이 §10 line 278의 independence 축을 **5축**으로 전사했으나 ADR-002-022
  §10 line 278 원문은 **6축**이다 — verbatim "Independence requires evidence that allocation, refill, broker
  enforcement, **credential/session state**, failure domain, and final route are genuinely separate"
  (1차 소스 실측: `tos-spec/src/part-1-foundation/ADR-002-022-Action-Flow-Budgeting-Retry-Storm-Containment-and-
  Protective-Traffic-Preservation.md:278`). **credential/session state 축**이 누락되어 있었다.
  - **정정 개소(3)**: §2.2-3(line 455 인근)·§4.1 item 2(line 640 인근)·§5.1(line 776 인근) — 전부 6축으로 복원.
  - **성질**: **전사 누락의 복원**이며 계약 의미 변경이 아니다. 축 추가는 `scope_graph_complete`의 통과 조건을
    **좁히기만** 하므로(추가 양성 증거 요구) 방향이 **보수 강화**다 — fail-open을 만들지 않고 기존 결정을 뒤집지
    않는다. 따라서 §10.2 비준 체크리스트 재수행·재비준은 불요하고 **v1.1 비준 효력이 그대로 유지**된다.
  - **구현 반영**: `tos/src/tos/afg/records.py` `ScopeIndependenceEvidence`에 `credential_session_state_separated`
    필드 추가 + `_SEPARATION_AXES`(6축 ClassVar) 도입 + `is_independent()` 합취 포함; 회귀 canary
    `test_every_adr_separation_axis_is_load_bearing`(6축 각각 개별 fail-closed 실증)·
    `test_credential_session_state_axis_is_required_for_independence` 신설.
  - 형식 선례: 설계 #7 liveauth v1.2 에라타.
- **v1.1 (2026-07-26) — 독립 비평 리뷰 REVISE(CRITICAL 1·MAJOR 9·MINOR 10·Gap 9) 반영, 운영자 비준 대기.** 전
  1차 소스 재실측(받아쓰기 금지·phantom 재발 0). 문서 번호 **#15→#16** 개번(세션 A #15 IAP 선점 `ff5a708e`).
  - **C1 (fail-open 방향 반전)**: §10:276을 "smallest"로 오전사한 다개소(§0.1 item3·§2.2-3·§3.5·§4.7·§5.1)를 **두-규칙
    분리**로 정정 — unknown dependency scope⇒smallest(§1:25) / broker documented incomplete⇒**largest** credible
    containing scope(§10:276, 공유 넓게). `shared_limit_conservative` §5.1 정식 정의 + both-ways canary + §7/§9.1 등재.
  - **M1 (phantom)**: `ReserveGuaranteeLevel`(코드 부재)→실명 `GuaranteeLevel`(`protective/vocabulary.py:32`) 정정
    (§0.2·§2.2-5·§6.4·§3.4).
  - **M2 (seam 타입 오선언)**: `partition_lease_admissible` 반환 `bool|None`→**`Admissibility` StrEnum**(ADMISSIBLE/
    TRAPPED/PROHIBITED `vocabulary.py:118/137`)·`is Admissibility.ADMISSIBLE` identity 게이트(§0.2·§3.4·§6.6)·truthy
    규율 Admissibility 축(§2.2-1)·§7 seam 3값+None 전수 canary.
  - **M3 (§29 q1 over-claim)**: REUSE 근거를 §29 q1(Open Questions·미해결)→**§1:19 + AFG-INV-004:169 + §30 item2:680**
    재앵커; q1 미해결이라 REUSE 잠정(§0.4c·§10.3-1).
  - **M4 (§30 item9 절단 인용)**: 4개→**9카테고리 전문** 개별 귀속 — timing/age/amplification 4류=VP-002 실재·null,
    rate/burst/queue/refill/protective-reserve 5류=brokercap INSTANCE(§8.1·§9.2·§10.2-11).
  - **M5 (dimension 오귀속)**: "§8:238 verbatim" 삭제(§5.6:133≠§8:238≠§21:439); `ActionFlowDimensionKind`에 `ORDER`·
    `CONNECTION` 추가(13종)·비폐쇄 명시(§2.2-4).
  - **M6 (INV-013 오배정)**: §18 refill 앵커 INV-013→**INV-004(replenishes)+INV-007**; INV-013(Stale Generations
    Fenced)은 `generation_fenced` §5.4 신설(§4.4·§1 표·§7·§9.1).
  - **M7 (brokercap/time under-realization)**: 전용 술어 5종(brokercap `same_order_retry_allowed`:377·`rate_admission_
    ok`:437; time `elapsed_within_continuity`:73·`snapshot_age_admissible`:287·`recovery_generation_revives_nothing`:499)
    §3.4 produced-bool 전용 슬롯 승격·§3.4(b) 정정·§7 `test_seam_brokercap`/`test_seam_time` 레인.
  - **M8 (§12 미매핑)**: §1 표 §12 행 신설·`queue_does_not_extend_validity`/`permit_not_merged`/`backlog_is_not_
    authority` §5.3·§4.7 금지 동사·§12 6분류 §2.1 disposition(Gap-8).
  - **M9 (denylist→allowlist)**: 세션 A `tos/src/tos/ioc/`(비준·구현)·`iap/` 추가로 "12 형제" stale — §0.3/§7.1
    allowlist(⊆{canonical,ordering,rcl,afg}) 전환·IOC "미비준"→"비준·구현 완료·무의존"(§0.2·§9.2)·sibling edge 선례
    ioc→rcl 5번째(afg→rcl 6번째 후보).
  - **Gap-1 disjointness**(§2.2-5·§7)·**Gap-4 금지 동사 확장**(§4.7)·**Gap-5 predicate-only ∅/None canary**(§6)·
    **Gap-6 Fence/Latch=ADR-002-024 이연**(§0.2)·**Gap-7 "Unknown materiality is material"**(§6.5)·**Gap-8 §12 6분류**
    (§2.1)·Gap-9=M5 흡수. **MINOR m1–m10**: orthostate `:100`→`:92`·멤버 라인; permit→`ActionFlowPermit` 부재; §6 헤더
    004 병기; `no_potentially_live_proof`=intent-축(§4.5·§6.1); 694→693; register .md288–299(=.csv257–268); CAUSE≡
    originating event(§2.2-3); dangling §4.4→§2.2-5; §4.7↔§7 행 대응(m10). **리뷰 처방 전건 정확·반론 0.**
- **v1.0 (2026-07-26) — 초안, 독립 비평 리뷰 대기.** ADR-002-022를 Phase 1(EV-L1) 설계 계약으로 실현. 패키지
  `tos.afg`(Action Flow Governance; 대안 `tos.budget`[좁음]·`tos.flow`/`tos.rate`[collision/좁음]·`tos.governor`/
  `tos.actionflow`[혼동/비관행] 기각, §0.4a). 5-아티팩트(`ActionFlowPolicy`·`ActionFlowStateSnapshot`·
  `ActionFlowDecision`·`ActionFlowPermit`, 전부 IndependentIdArtifact·digest-bound·generation-immutable append-only)
  + value 모델(`ActionFlowVector`=rcl `CapacityVector` REUSE·`ActionCause`·`ActionAmplificationEnvelope`·
  `ProtectiveFlowReserveClaim`·all-false `ActionFlowGovernorEffect`)(§2). EV 분류: **core 5행(AFG-EV-001·002·004·
  007·008, #11/#13형 core tier) / predicate-only 7행(003·005·006·009·010·011·012) / not-Phase-1 — 닫는 AFG-EV = 0건**
  (§1). **실측-원천 정정**: orchestrator 사전 카운트 "L1 슬라이스 6행" → register 실측 **5행**(003·005·006·009·010·
  011·012는 최소 EV-L2, §1 결정적 사실 1; #13 ARE와 동일 정정 패턴). seam: **rcl 1-소비자 produced-scalar/bool
  producer + protective/spg/orthostate/brokercap/time/recon 6-생산자 주입 소비, sibling edge 1건(afg→rcl `CapacityVector`
  +`aggregate_usage`/`effective_limit` REUSE), PROMOTE 0**(코드 실측 [v1.1 라인 정정]: rcl `authority.py:40/53–55`·
  `vector.py:74/103/139`, protective `predicates.py:129/460/590–615`·`GuaranteeLevel vocabulary.py:32`·`Admissibility
  vocabulary.py:118`, orthostate `vocabulary.py:61/92`·`predicates.py:461`, spg `vocabulary.py:209`, brokercap
  `same_order_retry_allowed/rate_admission_ok predicates.py:377/437`·`vocabulary.py:71/82`·`_base.py:19`, time
  `elapsed_within_continuity/snapshot_age_admissible/recovery_generation_revives_nothing predicates.py:73/287/499`·
  `elements.py:112`, recon `records.py:28`). **핵심 아키텍처 판정**: (i) `ActionFlowVector`=rcl `CapacityVector`
  REUSE(afg→rcl 1 edge; [v1.1 M3: 근거 §1:19/AFG-INV-004:169/§30 item2:680 재앵커·§29 q1은 미해결 표시] generic
  dimension_id·rcl↛afg acyclic·#8/#13 선례) — 자체 vector(기각·좌표 붕괴)·PROMOTE(기각·무거움); (ii) `ActionFlowPermit` afg-local 스키마
  (schema-ownership vs rcl production-ownership 분리·permit ≠ Transmission Capability §5.5); (iii) protective
  reserve/bounded-retry/lease는 **결과 bool/scalar 주입 소비**(재분류 금지 — protective 소유); (iv) spg `ACTION_FLOW_
  POLICY` bundle member 실측이나 **전용 semantic-validation step 필드 부재**(phantom 금지 — afg는 spg step 생산 안
  함, §3.4 (b)). 중심 fail-closed 술어: `scope_graph_complete`(no-local-headroom)·`amplification_bounded`(unbounded⇒
  denial)·`permit_single_use`+`atomic_economic_flow_coverage`(both-or-neither)·`refill_conservative`(no manufactured
  headroom)·`no_blind_retry`·`cancel_ack_not_final_quantity_proof`·`non_revival_holds`(§5/§6). **∅-공허 양방향**(빈
  scope/dimension/required-scope/amplification/lineage/vector — 금지 방향+허용 방향 둘 다, §4.7). **truthy-sentinel
  정규화**(`ActionFlowResult is GRANT`·reserve `is not True`; orthostate `is True` 선례). 앵커: AFG-INV-001..014·
  AFG-AC-001..012·AFG-EV-001..012(§0.4f). **bounds 실측**: VP-002 8키(pin 3 + timing/amplification 5) 전부 실재·null
  (candidate 신규 키 0건, §8.1; per-broker rate/burst는 brokercap INSTANCE). 선제 봉합: fail-open(§4)·∅-공허 양방향
  (§4.7)·truthy-sentinel(§2.2)·under-realization(rcl/protective 전용 슬롯엔 정의 술어·orthostate/spg는 정직 좌표-
  의존/phantom-금지 이연 §3.4 (b))·phantom 0(전 인용 grep 실측)·부등호 검산(§4.1 headroom·rcl `effective_limit`
  REUSE)·좌표 비붕괴(§2.2-5). **어떤 EV도 닫지 않음·acceptance 미선언·[v1.1] ADR-002-020 IOC 비준·구현 완료이나 무의존.**

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

1. **패키지 명명** `tos.afg`(Action Flow Governance) 승인 — 또는 대안(§0.4a `budget`/`flow`/`rate`/`governor`/
   `actionflow` 기각 근거 검토; naming은 load-bearing 아님).
2. **seam 결정**: decision/reserve seam produced-scalar/bool 주입(edge 0) + `ActionFlowVector` afg→rcl `CapacityVector`
   REUSE(1 edge) — §3.4/§0.4b/§0.4c. **[운영자 판단 지점]**. rcl/protective 슬롯이 실재함을 코드로 재확인(리뷰어:
   `rcl/authority.py:40/53–55`·`rcl/vector.py:74/103/139`·`protective/predicates.py:129/460/590` 인용 라인 검증 —
   sibling 서사 아님).
3. **`ActionFlowVector` = `CapacityVector` REUSE 결정**: afg→rcl 1 edge(rcl↛afg 실측 acyclic·#8 orthostate→rcl·#13
   are→rcl 선례; ADR §29 q1 "RCL vector schema" 타입 소유) — 자체 vector(기각·좌표 붕괴)·PROMOTE(기각·무거움) 근거
   검토(§0.4c). **[운영자 판단 지점]**: REUSE(채택) 승인 여부. `aggregate_usage`/`effective_limit` REUSE로 headroom
   fail-closed(None⇒UNKNOWN)·부등호 방향(usage≤limit) 재확인.
4. **`ActionFlowPermit` 스키마 소유**: afg-local(권장·schema-ownership) vs rcl PROMOTE(§0.4d). **[운영자 판단
   지점]**. permit ≠ Transmission Capability(§5.5 line 129) 재확인·single-use 불변식이 rcl `TransmissionCapability`
   `records.py:295–296` 패턴 동형인지.
5. **spg step 부재(phantom 금지)**: spg `ACTION_FLOW_POLICY` bundle member 실측(`vocabulary.py:209`)이나 **전용
   `action_flow_effect_within` step 필드 부재**(spg `records.py:205` = `aggregate_effect_within`만)를 재확인 — afg가
   spg step을 생산하지 않고 generic step-6 envelope 검증에 위임하는 판정이 정확한지. **[운영자 판단 지점]**: 미래
   action-flow 전용 spg step 필요 여부(현 판정 불요·이연).
6. **EV 분류·실측 정정**: core 5 / predicate-only 7 / not-Phase-1 판정과 **닫는 AFG-EV = 0건** 규율 확인. 특히
   **사전 카운트 "6"→실측 "5"** 정정(003·005·006·009·010·011·012가 최소 EV-L2임을 register line 290–299로 재확인)이
   §1·§5·§6·§7에 일관한지·"EV-L1-complete 주장 금지" 부착 self-consistency pass.
7. **소유권 분할(§3.5)**: afg가 rcl 원자 commit(`transition_allowed`)·protective reserve 분류(`is_reserved_guarantee`)·
   brokercap capability·orthostate attempt 상태기계·trustworthy-time·broker-command 구성(ADR-002-020)·final egress를
   **재저작하지 않음** 확인(#8·#11·#13 권위 중복 교훈). **ADR-002-020 IOC 미의존** 재확인(command identity/digest
   scalar만·bytes 구성 침범 금지).
8. **fail-closed·∅-공허 양방향(§4.7)**: 빈 scope⇒`UNKNOWN`·빈 dimension⇒restrictive·빈 required-scope⇒restrictive·
   빈 amplification⇒denial·빈 lineage⇒`UNKNOWN`·빈 permits⇒restrictive·None magnitude⇒UNKNOWN/DENY, **각각 금지+허용
   canary 둘 다** 확인(#6 fail-open·#10/#12 ∅-void 교훈; §4.7 표 9행↔§7 목록 1:1 m10). 금지 동사(narrower-scope/patch/
   union/borrow-reserve/blind-retry/release/revive/create-protective-authority/enlarge-envelope + **Gap-4: merge-
   permits/regenerate-command/backlog→authority/repay-reserve/delegate-to-producer/assume-zero-counter/recalculate-
   favorable/invent-cause/change-class**) 커버리지 대조.
9. **truthy-sentinel(§2.2, 양축 M2)**: `ActionFlowResult` 소비 게이트 `is GRANT`·**protective `Admissibility` 게이트
   `is ADMISSIBLE`(M2)**·reserve `is not True`·time `is not True` 정규화(orthostate `is True` `predicates.py:461`
   선례) — StrEnum/bool|None truthy 관통 0건 확인(#13 ARE UNKNOWN-truthy 교훈).
10. **실측-원천·phantom 0**: 전 인용 타입/필드(`GrantDecisionRef`·"Action Flow decision reference"·`CapacityVector`·
    `aggregate_usage`/`effective_limit`·`is_reserved_guarantee`·**`GuaranteeLevel`(M1)**·**`Admissibility`(M2)**·
    `partition_lease_admissible`·bounded-retry `budget_remaining`·**brokercap `same_order_retry_allowed`/`rate_
    admission_ok`(M7)**·**time `elapsed_within_continuity`/`snapshot_age_admissible`/`recovery_generation_revives_
    nothing`(M7)**·`TransmissionAttemptState`·`BrokerOrderState`·`ACTION_FLOW_POLICY`·`SUBMISSION_IDEMPOTENCY`/
    `RATE_LIMITS`·`MonotonicReading`·`ConservativeBound`·**ioc `EconomicEffectEnvelope`(Gap-1)**)이 실코드에 존재함을
    grep 재확인(#10 MAJOR phantom 교훈; **`ReserveGuaranteeLevel`은 phantom으로 제거**). AFG-INV(14)·AFG-AC(12)·
    AFG-EV(12) 수·seam 라인이 원문/코드와 일치.
11. **bounds 실측(§8.1)**: VP-002 8키(`action_flow_policy_*` pin 3·`B_action_flow_invalid_to_rcl/egress`·`B_action_
    flow_violation_to_containment`·`MAX_action_flow_state_snapshot/decision/permit_age_ms`·`MAX_action_amplification_
    per_cause`)가 **전부 실재·null/TBD**(candidate 신규 키 0건)임을 `measurement_source` 전수 확인. per-broker rate/
    burst/queue가 brokercap INSTANCE(VP-002 키 아님)임을 재확인(over-claim/under-claim 양쪽 봉합).
12. **broker-agnostic·숫자 하드코딩 0·firewall(§0.3)·verbatim 전사(§2.2)** 확인.
13. **비-acceptance**: 어떤 AFG-EV/ADR acceptance·restricted-live·production도 선언 안 함(§0.2)·Independent-Safety-
    Reviewer 하드 배제 확인·비준 기록 = "v1.1 개정 완료 — 운영자 비준 대기".

### 10.3 운영자 판단 지점 (요약)

1. **decision/reserve seam decoupled(권장) + `ActionFlowVector` afg→rcl `CapacityVector` REUSE(1 edge, 권장)** vs
   대안(자체 vector) — §3.4/§0.4c. #8/#13 sibling-edge 선례 대비 수용 가능성.
2. **`ActionFlowPermit` 스키마 소유** afg-local(권장) vs rcl PROMOTE — §0.4d.
3. **spg action-flow 전용 semantic-validation step 필요 여부** — 현 판정 불요(generic step-6 위임)·이연(§3.4 (b)/
   §10.2 item 5).
4. **VP-002 bounds Bounds-Approver 승인** — 8키 전부 null·per-broker 수치는 brokercap INSTANCE(§8.1·§9.2 item 12).
5. **ioc 정식 형제화 후 command identity/digest edge 필요 가능성(OQ5)** — ADR-002-020 IOC 비준·구현 완료(`tos/src/
   tos/ioc/`)로 정식 형제다. 현행 판정은 **afg가 command identity/digest scalar만 주입 참조·afg↛ioc 무의존** 유지
   (§0.2; command bytes 구성은 IOC 소유)이나, 미래 IOC↔AFG per-send binding(§29 q5 claim ordering)이 edge를 요구할지
   재검토. 현 권장: 무의존 유지(scalar 주입이 최소 접점).
6. **dimension-id 전역 namespace 조정(Gap-1)** — CapacityVector 4소비자(rcl/are/ioc/afg) 간 dimension-id disjointness
   전역 규약(접두사 등)은 Phase-0/후속(afg 몫만 본 계약 확정).

### 10.4 리뷰 이력 + 독립 리뷰어 공격 지점 (open questions)

**리뷰 이력**: v1.0 독립 비평 리뷰 **REVISE**(CRITICAL 1·MAJOR 9·MINOR 10·Gap 9). v1.1이 전 항목 반영(§10.1) — C1
fail-open 방향 반전·M1 phantom·M2 seam 타입·M3 over-claim·M4 절단 인용·M5 dimension·M6 INV 오배정·M7 under-
realization·M8 §12 미매핑·M9 denylist→allowlist + Gap 9건 + MINOR 10건. 오케스트레이터가 C1·M1·M2·M8을 1차 소스
재실측 확정, 저작자가 전 항목을 1차 소스 재확인 후 적용(phantom 재발 0). **리뷰 처방 전건 정확 판정(반론 0).**

1. **`ActionFlowVector`=`CapacityVector` REUSE**가 afg→rcl 단일 edge로 strict edge-0 규율 대비 수용 가능한지(#8/#13
   선례로 정합 판단이나 운영자 확인 필요) — 특히 action-flow dimension(자원 축)이 rcl 경제 dimension과 같은
   `CapacityVector` 컨테이너를 쓰되 좌표 비붕괴(§2.2-5)가 유지되는지(dimension_id namespace 분리·Gap-1).
2. **atomic economic+flow coverage(§5.3/AFG-INV-005)**를 afg가 "양 coverage present ⇒ GRANT 가능"의 순수 술어로만
   저작하고 원자 transaction을 rcl 런타임(§29 q2)에 이연한 경계가 정확한지 — LedgerCommandRecord가 현재 경제 vector
   (`proposed_adverse_increment`) 1개 slot만 가지므로(records.py:185) action-flow vector를 두 번째 slot으로 추가하는
   것은 미래 rcl 확장(EV-L3)인지, 아니면 동일 `CapacityVector`에 action-flow dimension을 fold하는지 — **미해결 런타임
   설계 지점**(Phase-1은 afg-local vector 생산까지만).
3. **`ActionFlowPermit` afg-local 스키마 vs rcl production-ownership** 분리가 under-realization인지 정확인지(rcl이
   permit을 produce하나 스키마는 afg가 소유 — ARE decision 동형).
4. **spg step 부재를 phantom-금지로 정직 이연**한 판정(§3.4 (b))이 정확인지 vs spg에 action-flow 전용 step을
   신설해야 하는지(#10 MAJOR-1 phantom 교훈 반대편 — 없는 것을 만들지 않음).
5. **orthostate attempt 상태 좌표-의존**(전용 afg-bool slot 부재)이 under-realization인지 정직 이연인지(#13 are-
   orthostate 동형 — `no_blind_retry`는 정의 술어를 갖고 상태를 입력 소비).
6. **AFG-EV-004(cancel storm)가 register상 `EV-L1/3+Broker`(core L1 슬라이스)** 인데 §6.2(predicate-only 절)에 배치한
   것이 모순 아닌지 — 판정: L1 substrate(`cancel_ack_not_final_quantity_proof`·`oscillation_bounded`)는 core로
   §7 core 목록에 포함하되, **+Broker 통합 잔여** 때문에 술어 정의를 §6.2에 두고 §5/§7 core에서 상호참조(003 no-blind-
   retry와 동거하는 storm-containment 계열이라 배치 편의). core/predicate 이중 성격의 정직 표기.
7. **core 5행이 실제로 전부 L1-decidable substrate를 갖는지**(특히 AFG-EV-001 `/3`·002 `/3`·004 `+Broker`·007
   `+Security`·008 `/3`의 L1 부분과 overlay 부분 분리가 정확한지).

---

**규율 태그(문서 전체 적용)**: predicate/coordinate substrate only; AFG-EV-001..012 전부 NOT_IMPLEMENTED — core
5행(001·002·004·007·008)은 `/3`·`+Security`·`+Broker` 통합·독립 리뷰 대기, predicate-only 7행(003·005·006·009·010·
011·012)은 EV-L2/L3 fault injection·adversarial·+Security·+Broker evidence 대기. **EV-L1-complete 주장 금지. 닫는
AFG-EV = 0건. ADR-002-020 IOC 비준·구현 완료이나 본 계약 무의존(command identity/digest scalar만). 어떤 ADR
acceptance·restricted-live·production도 미승인.**
