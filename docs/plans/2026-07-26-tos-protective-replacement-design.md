# 설계 문서 #18 — Protective Replacement·Protection-Gap Control 계약 (2026-07-26, v1.2 에라타)

> **문서 번호 규약 각주(#18 확정, Q5)**: v1.0은 "잠정 #18"이었으나(세션 A #17 선점 우려), **오케스트레이터
> 판정으로 v1.1에서 #18 확정** — 세션 A가 #17 SBR(Startup/Recovery, 커밋 `9eb13bba`)을 완결하고 다음 VTG를
> #19로 메모리 조율했다. #17=SBR·#18=본 PR·#19=VTG(예정). 시리즈 순번은 착수 순서가 아니라 비준·선점 순서를
> 따른다(#16 AFG v1.0 "#15"→v1.1 "#16" 개번 선례). naming/번호는 load-bearing이 아니다.
>
> **대상 ADR**: ADR-002-011 — Protective Replacement and Protection-Gap Control ("PR"). 549줄. Status
> **Proposed**, Version 0.3(Last Updated 2026-07-17). Decision Type: Safety-Critical Architecture Decision.
> **Amends**: RFC-002 §13.3 Cancel/Replace Semantics·§21 Protective Control·§10/§15/§19 capacity·reconciliation
> prerequisites(ADR line 10). **Depends On**(ADR line 11): RFC-000 constitutional safe state; RFC-001
> SAFE-002/004/011/013/015/020/021/022/023/025/032/040/041/043/048/051/052; ADR-002-001 through ADR-002-009.
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며 스펙 텍스트
> (RFC/ADR/템플릿/프로파일)를 **변경하지 않는다**. **broker-agnostic 원칙(project memory
> `tos-spec-broker-agnostic`)**: 본 문서의 규범 텍스트는 **어떤 구체 broker(KIS 포함)도 명명하지 않는다.**
> replacement mode·protection gap/overlap·credible-intermediate-outcome·FQP 불변식은 전부 broker-agnostic이며,
> 브로커 제약은 capability class(Broker Capability Profile, #10)로만 표현한다.
>
> **자체 시리즈(실측·앵커)**: ADR-002-011은 **자체 `PR-INV` 번호 시리즈를 정의하지 않는다**(grep 실측: `PR-INV`
> 0건; §19에 `PR-AC-001..012` 12종만, line 420–431). 매핑 대상 EV: `verification/EVIDENCE-REGISTER-002.csv`의
> **`PR-EV-001..012` 12행**(domain "Protective Replacement", primary_adr ADR-002-011). ⇒ 본 계약은 모델 불변식·
> 술어를 **`PR-EV-001..012` · `PR-AC-001..012`(§19) · §-clause · `SAFE-###`(§22 traceability line 488–500)**에
> 앵커하고 **새 INV/AC/EV 시리즈를 창작하지 않는다**(§0.4f). #11 protective(ADR-002-001 자체 INV 부재)·#9(ADR-002-006
> 자체 INV 부재) 동형이며, #6(`SA-INV`)·#10(`BC-INV`)·#16(`AFG-INV`)이 자체 INV에 앵커한 것과는 상황이 다르다.
>
> **선행 문서(의존·형제)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   본 계약의 모든 모델은 전용 top-level 패키지에 놓이고 §3.2 허용목록 안에서만 의존한다(§0.3). line 164
>   "naming은 load-bearing이 아니다 — 내부 세분화는 후속 설계 문서가 정의한다"에 따라 본 문서가 신규 패키지
>   내부를 정의한다.
> - [설계 #11 — Degraded-Mode Protective Capacity 계약 (v1.2, 비준·구현)](2026-07-25-tos-degraded-mode-protective-capacity-design.md)
>   + 코드 `tos/src/tos/protective/`. **본 문서의 최인접 상류이자 최대 소유권 인접 지대다.** protective는
>   ADR-002-001 §9(partition-time lease-admissibility)·§11(Cancellation Arbiter)·§13(bounded-retry/exhaustion)·
>   §6.1/§6.2(protective classification)를 **이미 소유·구현**한다: `cancellation_admissible`(`predicates.py:523`,
>   §11.4 line 506 "no optimistic credit for submitted/acked replacement" 포함)·`partition_lease_admissible`
>   (`predicates.py:460`, → `Admissibility` StrEnum)·`retry_admissible`(`predicates.py:588`)·
>   `protective_capacity_exhausted`(`predicates.py:623`)·`protective_classification`(`predicates.py:246`)·
>   `ProtectiveActionKind`(`vocabulary.py:180`: `OVERLAP_FIRST_ADD_ONLY`·`CANCEL_FIRST_OR_REMOVAL`)·`Admissibility`
>   (`vocabulary.py:118`)·`ProtectiveOwnership`(`vocabulary.py:60`). **결정적 실측**: protective의 §3.5 소유권
>   분할표(설계 #11 line 726)는 "**§11.4 protection gap / non-atomic replacement | ADR-002-011 (PR-EV) |
>   protective 미소유(partition-lease-admissibility만 §9)**"라고 명시해 본 ADR로 gap/overlap/replacement를 **이연**
>   해 두었다. 본 계약은 그 이연분을 실현하고 protective 술어를 **주입 소비**한다(§3.4/§3.5). **`tos.protective`는
>   import하지 않는다**(형제; produced-bool/주입 좌표로만).
> - [설계 #5 — Risk Capacity Ledger 계약 (v1.1, 비준)](2026-07-21-tos-risk-capacity-ledger-design.md) + 코드
>   `tos/src/tos/rcl/`. **두 번째 소유권 인접 지대다.** rcl은 §9(Risk Capacity Accounting)·§14 capacity 산술을
>   **이미 소유·구현**한다: `CapacityVector`(`vector.py:74`, generic `dimension_id: str`)·`aggregate_usage`/
>   `effective_limit`(headroom, None⇒UNKNOWN 전파)·`transition_allowed(...,FINAL_QUANTITY_PROOF)`(`predicates.py:438`;
>   `TransitionCause.FINAL_QUANTITY_PROOF` `vocabulary.py:94`)·`partition_verdict`(`predicates.py:711`)·
>   `ProtectivePool`/`ProtectiveLease`(`records.py:315/348`)·`CapacityState`(`vocabulary.py:15`, `TRAPPED_CONSUMED`·
>   `QUARANTINED_UNKNOWN`)·`LedgerCommandRecord.proposed_adverse_increment: CapacityVector`(`records.py:185`)·
>   `GrantDecisionRef`(`authority.py:39`). **rcl `GrantDecisionRef`는 "Aggregate Risk / Action Flow decision"
>   전용**(`authority.py:40` 실측)이며 replacement decision slot이 **아니다** — 이것이 PR을 produced-bool 커널
>   (edge-0)로 확정하는 결정적 코드 증거다(§0.4b/§0.4c). **`tos.rcl`은 import하지 않는다**(형제; 주입 좌표로만 —
>   §0.4c에서 대안 검토).
> - [설계 #8 — Orthogonal Trading State 계약 (비준·구현)](2026-07-25-tos-orthogonal-state-design.md) + 코드
>   `tos/src/tos/orthostate/`. §5 orthogonal-state의 order/transmission/knowledge 축은 orthostate 소관이다:
>   `BrokerOrderState`(`vocabulary.py:92`; `CANCELLED` `:115`·`UNKNOWN` `:118`; **"a later valid fill SHALL be
>   accepted even after a locally observed CANCELLED" `:103–104` 실측**)·`TransmissionAttemptState`
>   (`vocabulary.py:61`; `SENT_UNCONFIRMED` `:86`·`SEND_FAILED_PROVEN` `:88`). PR은 order/attempt 상태를 **주입
>   좌표**로 소비하고 replacement-workflow 좌표(§5)를 **별개 축**으로 소유한다(좌표 비붕괴 §2.2-5). **`tos.orthostate`
>   는 import하지 않는다**(형제).
> - [설계 #16 (잠정) — Action-Flow Budgeting·Retry-Storm Containment 계약 (v1.2, 비준·구현)](2026-07-26-tos-action-flow-budgeting-design.md)
>   + 코드 `tos/src/tos/afg/`. **cancel-ACK≠FQP·missing-ACK·oscillation의 L1 술어를 이미 소유·구현**한다:
>   `cancel_ack_not_final_quantity_proof`(`predicates.py:794`)·`no_blind_retry`(`predicates.py:713`)·
>   `oscillation_bounded`(`predicates.py:841`)·`economic_effect_persists`(`state.py`, `predicates.py:519` 참조).
>   **핵심 소유권 판정(§3.5·§4.6)**: PR-EV-004 "Cancel ACK Is Not Final Quantity Proof"와 afg 동명 술어는 **같은
>   금지 규칙의 다른 EV 좌표**다(ADR 원문 대조 — 후술). **`tos.afg`는 import하지 않는다**(형제).
> - [설계 #10 — Broker Capability 계약 (v1.1, 비준)](2026-07-25-tos-broker-capability-design.md) + 코드
>   `tos/src/tos/brokercap/`. §6.1 atomic-replace semantics·§10/§11 FQP·idempotency·rate는 brokercap 소관이다:
>   `fqp_adequate`(`predicates.py:595`)·`same_order_retry_allowed`(`predicates.py:377`)·`rate_admission_ok`
>   (`predicates.py:437`)·**"the 5 replace/amend semantics (ADR-002-004 §8.8)" `vocabulary.py:203`**·
>   `final_quantity_proof_rules`(`records.py:359`). PR은 이 결과를 **주입 소비**하고 broker capability를 판정하지
>   않는다(broker-agnostic). **`tos.brokercap`은 import하지 않는다**(형제).
> - [설계 #6 Safety Authority (비준)](2026-07-23-tos-safety-authority-design.md)·[설계 #9 Reconciliation
>   Confidence (비준)]·[설계 #13 (잠정) Aggregate Risk Projection (비준·구현)](2026-07-25-tos-aggregate-risk-projection-design.md).
>   §8 HALT precedence는 authority(`AuthorityState.HALTED`·`PRECEDENCE_RANK`·`restrictive_dominates`) 소관, §16
>   recovery는 recon(`ConservativeBound`) 소관, §9 credible-state-space aggregate risk는 are(ADR-002-021) 소관이며
>   PR은 전부 **주입 소비**한다. **미import**(형제).
>
> **v1.2 에라타 고지(2026-07-26, 비준 효력 유지)**: 본 개정은 **의미 변경이 아니라 실측-정합 에라타**다(#16 v1.2
> [6축 전사 누락] 선례 동형). 발견 경로 = **적대적 코드 리뷰 MAJOR-1**. 내용: v1.1이 `leg_admissibility` 생산자
> (ADR-002-019)를 "세션 A WIP·코드 부재"로 보고 `bool|None` 주입 슬롯으로만 서술했으나, **실 producer가 `tos.venue`로
> 착지**(`OrderAdmissibilityResult` — 4토큰 truthy-untestable StrEnum)했으므로 §3.4 행을 **실측 signature + 접기
> 규칙 + venue `protective_label_no_bypass` 경유**로 정정하고 §7 MANDATED seam 목록의 `test_seam_vtg`를 "작성됨"으로
> 갱신한다. **접기 규칙은 보수 방향**(4토큰 중 `ADMISSIBLE` 1개만 True; 나머지 3토큰·None ⇒ fail-closed)이므로 어떤
> 허용도 넓히지 않으며 v1.1 비준 효력·PR-EV 비-acceptance(§0.2)는 **그대로 유지**된다. 에라타 승인 = 오케스트레이터
> 위임 비준(2026-07-25 표준지시).
>
> **비준 상태**: **2026-07-26 운영자 위임 자동 비준(v1.1) — 효력 발생**(표준지시 2026-07-25 + 본 세션 운영자
> "PR 사이클도 적대적 코드 리뷰·커밋까지 끝까지 진행" 지시). 경위: v1.0 → 오케스트레이터 1차 심사 통과(앵커
> 14/14·PR-AC 12·§-row 전조항 커버) → 독립 비평 리뷰 **REVISE**(CRITICAL 2[C1 netting 극성 3중 모순·C2
> sufficiency 조달원 범주 오류 — 둘 다 old-취소 경로 fail-open]·MAJOR 6·MINOR 8·Gap 8; 인용 33/33 정확·어휘
> 5종 verbatim clean·소유권 3판정 독립 확증) → v1.1 전량 반영(저작자 1차 소스 재실측, 반론 0; no-netting을
> 주입 flag에서 **구조적 magnitude 파생**으로 전환·`overlap_first_sequencing_valid` 4-입력 conjunction·
> `leg_admissibility` 슬롯 3술어 착륙·§4.6a 신규 불변식) → 오케스트레이터 스팟체크 통과(구파라미터 0·음극성
> `is not True` 0[개정 로그 서술 제외]·§4.6a 실재). **§10.3 판단 지점 전건 승인** — 핵심: edge 0 유지 +
> no-netting 구조적 파생(리뷰 처방 (b))·`tos.replacement` 패키지·#18 확정. 효력: `tos/src/tos/replacement/`
> Phase 1(EV-L1) 순수·비전송·fail-closed 모델 + property test 착수 승인. 본 문서는 여전히 어떤 PR-EV·ADR
> acceptance·restricted-live·production도 승인하지 않는다(§0.2). ADR acceptance는 오직 *실행된* evidence로만
> 온다(project memory `tos-spec-rfc-authoring-track`; ADR §18 line 410·§24 line 517–531; VER-002-001 §5
> "Registration is not execution").
>
> **리뷰 이력(선제 봉합 defect class)**: 시리즈 축적 REJECT/REVISE — #6 v1.0 REJECT(fail-open seam: exclusivity
> `≤1⇒True` vacuous-True)·#8 v1.0 REJECT(cross-section 혼동)·#10 v1.0 REVISE(seam 실측 오명명 — 코드 부재 함수
> 인용)·#13 ARE(사전 6→실측 5 core 정정)·#16 AFG v1.0 REVISE(CRITICAL 1[C1 방향 반전]·MAJOR 9·MINOR 10·Gap 9;
> v1.2 에라타[6축 전사 누락]). **#16 신규 교훈**: GRANT류 결과는 잔여 공간(fall-through)이 아니라 **양성 identity
> 증명으로만 도달**(코드 리뷰 CRITICAL). 본 문서가 **선제 봉합**한 defect class: (a) §1 core-tier 판정(PR-EV 2행
> L1 슬라이스 보유·닫는 PR-EV 0). (b) 소유권 중복 구조적 배제(§3.5 코드 실측 소유권 분할표). (c) fail-open seam
> 방지(중앙 술어 본질적 fail-closed·양성 identity 증명·both-ways canary). (d) fixture clean-vs-illegal 정합.
> (e) cross-section self-consistency pass(§1↔§4/§5/§6↔§7). (f) verbatim 전사 + ADR line 병기(에라타 방지). (g)
> 실측-원천 결함 방지(모든 seam을 코드 실측 signature+라인; 인용 전 grep). (h) **방향 극성 검산**(overlap-first↔
> cancel-first 반대 방향 진리표 §4.5). (i) **전사 완전성**(§9 9항·§12 6항·§15 8항·§5 10항·§7 12항·§10 9항·§11
> 7항·§16 9항·§18 10항 원문 항목 수 전수 대조 — v1.1 M3 확장). (j) **truthy-sentinel 극성 분기(v1.1 C1 신규
> 교훈)**: 양극성 bool|None(안전값=True)은 `is True`, **음극성 bool|None(안전값=False)은 `is False`만**(음극성에
> `is not True` 사용 금지 — None 통과=fail-open); StrEnum은 identity(`is ADMISSIBLE`/`is REPLACEMENT_ADMISSIBLE`);
> **GRANT/complete류는 양성 conjunction identity로만 도달**(fall-through 금지 #16 CRITICAL). (k) **∅-공허 양방향**
> (금지+허용 canary 둘 다).
>
> **시리즈 규율 개선 4건(v1.1 신규 — 다음 문서 상속용, §10.1 참조)**: (1) **truthy-sentinel 극성 분기**(위 (j) —
> 음극성 필드에 `is False` 강제); (2) **카운트 대조 전수화**(위 (i)); (3) **§3.4 seam 표에 "형제 술어 docstring
> 명제 ↔ ADR 조항 명제 동일성" 열 추가** — 명제가 다르면 좌표-의존 이연으로 강등(C2 category-error 구조적 재발
> 방지); (4) **§-row 매핑을 normative 문장 단위로**(§5:139이 한 줄에 3규범을 담은 사례 — M1).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-011 조항별 **Phase 1(EV-L1) 도달성 경계**(§1). **core(L1 슬라이스) / predicate-only / not-Phase-1
   (형제 소유·런타임 이연) 3분류.** **결정적 사실(register 실측·오케스트레이터 사전 카운트 확인)**: `PR-EV` 12행
   중 **2행(001·005)이 register 최소 레벨에 `EV-L1` 슬라이스 보유**(#11 protective형 core tier — protective도
   정확히 2 core row였다). **오케스트레이터 사전 카운트 "L1 슬라이스 2행 = 001·005"는 실측 결과 정확**하다
   (정정 없음; CSV-aware 파싱 — 제목 필드 쉼표 포함, EVIDENCE-REGISTER-002.csv 전수). 나머지 10행: **003·004·006
   = `EV-L3+Broker`, 007·012 = `EV-L3/5`, 002·008 = `EV-L2/3`, 009·010·011 = `EV-L3`**(전부 L1 슬라이스 부재).
   **닫는 PR-EV = 0건**(L1 슬라이스 저작 ≠ EV closure: `/3`·`+Broker` 잔여). "**EV-L1-complete 주장 금지**".
2. **replacement 5-어휘 + 워크플로 데이터 모델**(§2, **core substrate**): `ReplacementMode`(§6, 4종:
   `BROKER_PROVEN_ATOMIC`·`OVERLAP_FIRST`·`CANCEL_FIRST`·`NO_SAFE_MODE`)·`ReplacementWorkflowState`(§5, 7+2종
   PLANNED..COMPLETED + FAILED_CONTAINED/RECOVERY_REQUIRED)·`CredibleIntermediateOutcomeKind`(§9, 9종 verbatim)·
   `ReevaluationTargetKind`(§12, 6종 verbatim)·`ReplacementOutcome`(로컬 결과) 어휘 + digest-bound
   `ReplacementAuthorization`(§7 IndependentIdArtifact)·`ReplacementWorkflowRecord`(§5 orthogonal, digest-bound)·
   `ProtectionObligation`(§4.1 value) + 주입 value(`AggregateRiskComparison`류·`OverlapReservationClaim`). Generation은
   `tos.ordering` 좌표(§3.2, 별도 heavy 아티팩트 아님 — #13 ARE·#16 AFG 동형).
3. **overlap-first reservation completeness + no-netting 중앙 불변식**(§4.1/§5.1, **PR-EV-001 core L1 슬라이스** —
   ADR §6.2·§9·PR-AC-001): `overlap_first_reservation_complete(...) -> bool`. **모든 credible intermediate outcome
   (§9 line 234–243, 9종)이 reservation에 포함**되고 **old와 new가 둘 다 계상(netting 부재)**될 때만 True.
   이것이 "원본+대체 주문 동시 커버"와 rcl capacity **이중 계상**의 정합 지점이다(§0.4d 핵심 판정).
4. **overlap-first sequencing 불변식**(§4.1/§5.1, **PR-EV-001 core L1**): `overlap_first_sequencing_valid(...) ->
   bool`. **old는 new Protection Sufficiency Proof가 current이고 Cancellation Arbiter가 removal이 required
   protection을 줄이지 않음을 판정할 때까지 취소 불가**(§6.2 line 159). protective `protective_classification`·
   `cancellation_admissible` 결과를 **주입 소비**(§3.4).
5. **partial-fill re-evaluation completeness 중앙 불변식**(§4.2/§5.2, **PR-EV-005 core L1 슬라이스** — ADR §12·
   PR-AC-005): `partial_fill_reevaluation_complete(...) -> bool`. **모든 fill/recognized exposure change가 6종
   re-evaluation(§12 line 292–298 verbatim)을 원자적으로 유발**할 때만 True + **no-hiding-clamp**(§12 line 302
   "SHALL NOT be rounded or clamped in a way that hides uncovered or reversing quantity") + **risk-increasing ⇒
   egress deny/contain**(§12 line 300).
6. **cancel-first admission gate 술어**(§4.3/§6.1, **PR-EV-002 predicate-only** — ADR §6.3): `cancel_first_admission_
   gate(...) -> bool`. **8 전제조건(§6.3 line 166–174 verbatim) 전부 양성 증명**일 때만 True; 하나라도 unknown ⇒
   denied(§6.3 line 176). protective `cancellation_admissible`·brokercap resource·time-trust 주입 소비. **최소
   `EV-L2/3` — 닫지 않음.**
7. **replacement-authorization currentness 술어**(§4.4/§6.2, **PR-EV-008 predicate-only** — ADR §7):
   `replacement_authorization_current(...) -> bool`. **material change(§7 line 201) ⇒ 무효** + **expiry는 future
   transmission만 차단, 이미 전송된 old/new의 economic effect는 불변**(§7 line 203). afg `economic_effect_persists`
   (`tos.afg.state`) 주입 소비. **최소 `EV-L2/3` — 닫지 않음.**
8. **replacement workflow label-grants-nothing 불변식**(§4.4/§5.3, core substrate — ADR §5 line 137): "No lifecycle
   label by itself authorizes capacity release or removal of protection." all-false `ReplacementAuthorityEffect` +
   orthogonality 규율(§5 line 107 "SHALL NOT collapse order state, transmission state, knowledge confidence,
   capacity state, and protection state into one enum").
9. **PR ↔ protective/rcl/orthostate/afg/brokercap/authority/recon/are 경계(중심 아키텍처)**: PR은 **sibling edge
   0건**을 유지한다(§0.4b/§3.4; **권장 — protective #11 동형**). PR은 (i) overlap-first/partial-fill/cancel-first/
   authorization completeness·sequencing·gate **bool을 생산**하고 미래 Protective Action Controller/rcl-admission/
   final-egress 런타임이 소비하며, (ii) protective `cancellation_admissible`/`partition_lease_admissible`(→
   `Admissibility`)/`protective_classification`/`retry_admissible`·afg `cancel_ack_not_final_quantity_proof`/
   `no_blind_retry`/`economic_effect_persists`·brokercap `fqp_adequate`/replace-amend-semantics/`same_order_retry_
   allowed`·orthostate `BrokerOrderState`/`TransmissionAttemptState`·rcl `CapacityState`/`partition_verdict`/
   `aggregate_usage`(주입)·authority HALT precedence·recon `ConservativeBound`·are aggregate-risk 수치를 **주입
   좌표/produced-bool로 소비**한다. **`tos.canonical`·`tos.ordering`(둘 다 core)만 import**한다(§0.3). **PROMOTE
   0건. sibling edge 0건(권장) — `CapacityVector` REUSE(edge-1, pr→rcl)는 §0.4c/§0.4d에서 대안 검토 후 기각·판단
   지점.**
10. **fail-closed 규율 + named both-ways canary**(§4): 미포함 outcome ⇒ incomplete; **netting 미증명(구조적 no-netting
    부재) ⇒ False**; new **Protection Sufficiency Proof**(§10 per-field) 미current ⇒ old 취소 불가; missing re-eval
    target ⇒ incomplete; clamp가 quantity 은닉 ⇒ False; 8-조건 중 하나라도 unknown ⇒ cancel-first denied; **leg
    admissibility(-019) 미current ⇒ leg proceed 불가·trapped**; expiry ⇒ future만 제한(economic effect 불변);
    bound 초과 ⇒ containment(authority 확장·capacity widen·complete 선언 금지); **빈 outcome set·빈 re-eval target
    set·빈 required-condition·None magnitude ⇒ 보수적 UNKNOWN/DENY/TRAPPED**(∅-공허, §4.7 — **양방향** 명시). 각
    가드에 both-ways canary. **truthy-sentinel 극성 분기(v1.1 C1)**: protective `Admissibility` 게이트는 `verdict
    is Admissibility.ADMISSIBLE`(identity)로만(TRAPPED/PROHIBITED/None 관통 금지); `ReplacementOutcome`은 identity;
    **양극성 bool|None(안전값=True: `within_hard_envelope`·`new_protection_sufficiency_current`·`cancellation_
    admissible`·`leg_admissibility`)은 `is True`**; **음극성 bool|None(안전값=False: `hides_uncovered_or_reversing`·
    `material_change`·`became_risk_increasing`)은 `is False`만**(음극성에 `is not True` 금지 — None 통과=fail-open);
    **완료/허용 결과는 잔여 fall-through가 아니라 양성 conjunction identity 증명으로만 도달**(#16 CRITICAL 교훈). 단
    **no-netting은 flag 극성이 아니라 구조적 magnitude 파생**으로 증명한다(v1.1 M6 처방(b) — §0.4d).
11. **property-test 하네스 타깃**(§7, §1 분류 정렬) + import-closure 검증(§7.1, **allowlist 형식**) + run manifest
    7항목(§7.2) + fixture clean-vs-illegal 정합(#8 교훈) + seam cross-check(test-only, §3.4) + **hypothesis
    전략에 forgery/∅ 케이스 명시 포함**(§7).
12. **bounds 주입 계약 + Phase-0 이관**(§8): PR decision 구조에는 numeric bound 부재(전부 enum·boolean·집합 논리·
    주입 `CanonicalDecimal`); ADR §15가 요하는 8 timing bound는 **VP-002에 4 PR-전용 키 실재·null**(`B_protection_gap`
    line 625·`B_protection_overlap` 632·`B_protective_replacement_contain` 639·`B_final_quantity_proof` 569 —
    §8.1 실측)이며 **confirmed candidate 신규 키 0건**(#10/#13/#16형); per-broker gap/overlap 수치는 Broker
    Capability Profile INSTANCE(§15 line 353·VP 주석 "APPROVE per broker/order/replacement profile"). 값 승인은
    Bounds-Approver 게이트.

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR §24 line 519 "This ADR
  SHALL remain **Proposed** until all of the following are complete"·line 531 "Authorship of this ADR does not
  prove safe replacement and does not authorize restricted-live or production operation"·§18 line 410 "Written
  cases and logs are not completed evidence. Acceptance requires registered, executed, retained, and independently
  reviewed evidence under VER-002-001." **닫는 PR-EV = 0건.**
- **capacity 산술(commit/consume/release·aggregate envelope·partition consumption·원자 replacement 예약 commit)을
  저작하지 않는다.** 그것은 **rcl(#5, ADR-002-002/012)이 이미 소유·구현**했다 — `CapacityVector`·`aggregate_usage`/
  `effective_limit`·`transition_allowed`·`partition_verdict`·`ProtectivePool`/`ProtectiveLease`·`CapacityState`.
  ADR §9 line 231 verbatim "the Risk Capacity Ledger SHALL atomically commit capacity for the maximum aggregate
  risk over all credible intermediate outcomes"·§1 line 21 "The Risk Capacity Ledger is the sole authority that
  reserves, commits, remaps, and releases capacity." PR은 credible-intermediate-outcome **완전성**을 판정하고 rcl이
  vector를 원자 commit한다(§0.4d). §9 line 245 "Capacity MAY be reduced only after evidence proves that the
  relevant risk can no longer occur"의 실행(전이)은 rcl 런타임.
- **Cancellation Arbiter admissibility·partition-time lease-admissibility·protective classification/sufficiency·
  bounded-retry/exhaustion을 재저작하지 않는다.** 그것은 **protective(#11, ADR-002-001)가 이미 소유·구현**했다 —
  `cancellation_admissible`(`predicates.py:523`, §11.4 "no optimistic credit for submitted/acked replacement"
  포함)·`partition_lease_admissible`(`predicates.py:460`)·`protective_classification`(`predicates.py:246`)·
  `retry_admissible`(`predicates.py:588`). ADR §8(Cancellation Arbiter Rules)·§10(Protection Sufficiency Proof)·
  §13(bounded retry)는 protective 술어를 **주입 소비**하고 재저작하지 않는다(CLAUDE.md DRY 비협상). **PR의 §8 처리:
  overlap-first sequencing(§5.1)·cancel-first gate(§6.1)가 protective `cancellation_admissible`를 **한 입력으로
  소비**하는 상위 술어일 뿐 arbiter를 재구현하지 않는다**(§3.5).
- **cancel-ACK≠FQP·missing-ACK·oscillation의 L1 술어를 재저작하지 않는다.** 그것은 **afg(#16, ADR-002-022)가 이미
  소유·구현**했다 — `cancel_ack_not_final_quantity_proof`(`predicates.py:794`)·`no_blind_retry`(`predicates.py:713`)·
  `oscillation_bounded`(`predicates.py:841`)·`economic_effect_persists`(`state.py`). **핵심 판정(§4.6)**: PR-EV-004
  "Cancel ACK Is Not Final Quantity Proof"(`EV-L3+Broker`)와 afg `cancel_ack_not_final_quantity_proof`
  (`EV-L1/3+Broker`, AFG-EV-004 core L1)는 **같은 금지 규칙의 다른 EV 좌표**다 — **L1-decidable 술어 소유 = afg**,
  PR-EV-004는 **broker-evidenced L3 통합 좌표**(broker가 cancel ACK 후 late fill을 보내는 실증)라 **L1 슬라이스
  부재·본 Phase-1 미저작·afg+brokercap+orthostate 좌표 주입 소비**다(§3.5).
- **FQP 규칙·atomic-replace semantics·idempotency·rate를 재저작하지 않는다.** 그것은 **brokercap(#10, ADR-002-004)
  + evidence(ADR-002-006)가 이미 소유**했다 — `fqp_adequate`(`predicates.py:595`)·**"the 5 replace/amend semantics
  (ADR-002-004 §8.8)" `vocabulary.py:203`**·`same_order_retry_allowed`(`predicates.py:377`)·`rate_admission_ok`
  (`predicates.py:437`). ADR §4.6 line 99 "The evidence required by ADR-002-004 and ADR-002-006 to establish the
  final executable or filled quantity"·§6.1 line 147 "the active Broker Capability Profile specifies exact
  semantics." PR은 broker 증거를 **주입 소비**하고 broker capability를 판정하지 않는다(broker-agnostic).
- **order/transmission/knowledge 상태기계를 재저작하지 않는다.** 그것은 **orthostate(#8, ADR-002-005)가 이미
  소유**했다 — `BrokerOrderState`(`vocabulary.py:92`; CANCELLED+later-fill `:103–104`)·`TransmissionAttemptState`
  (`vocabulary.py:61`). PR의 replacement-workflow 좌표(§5 lifecycle)는 **별개 축**이며 order/attempt 상태를 **주입
  좌표**로 소비한다(좌표 비붕괴 §2.2-5). PR은 attempt/order 상태를 set하지 않는다.
- **final egress·Live Authorization·Transmission Capability·Protective Action Controller 런타임·containment 실행을
  저작하지 않는다.** ADR §1 line 21 "The Broker Adapter/Egress Gateway is the final transmission enforcement
  point"·§17(Failure Containment)·§16(Recovery)은 **런타임 EV-L2/L3**이다. PR은 결정 bool·완전성 판정·workflow
  레코드만 반환하며 **전송·capacity mutate·capability 발급·containment 실행을 하지 않는다**(§4.4; label-grants-nothing).
- **aggregate risk 수치·Adverse Scenario Set·HALT precedence·recovery reconciliation·trustworthy-time을 산출하지
  않는다.** §9 credible-state-space aggregate risk = **are(ADR-002-021)**, §8 HALT precedence = **authority
  (ADR-002-003)**, §16 recovery = **recon/rcl/liveauth**, §15 time = **time(ADR-002-008)**. PR은 전부 주입 소비하고
  비교/완전성 술어만 적용한다.
- **numeric gap/overlap/timing bound를 승인하지 않는다.** ADR §15 line 353 "Numeric values remain unapproved until
  human approval and executed evidence are recorded." 전부 주입 `CanonicalDecimal`로 담고 **어떤 숫자도 하드코딩하지
  않는다**(CLAUDE.md). 값 부재 ⇒ fail-closed. 값 승인은 Bounds-Approver 게이트(§8·§9.2).

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

신규 PR 패키지 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml`도 import하지
  않는다** — replacement 결정 규칙은 StrEnum·boolean·집합 논리이고 수치는 `CanonicalDecimal` 산술(비교·`is_finite`·
  scale-normalize)뿐이며, 모든 gap/overlap/timing bound·broker limit·aggregate-risk 값은 주입 파라미터이고 YAML
  파싱은 하네스(설계 #3) 소관이다(closure 최소화 — #5–#16 §0.3 동형).
- tos 자기 자신: `tos.canonical`(`FrozenModel`·`DigestBoundArtifact`·**이미 core인 `IndependentIdArtifact`**·
  **이미 core인 `classify_record_pair`**·`RecordPairKind`·`ArtifactStatus`·**이미 core인 `CanonicalDecimal`**),
  `tos.ordering`(replacement generation·authorization·workflow append-only 순서 — §3.2), 자기 자신 모듈.
  **canonical/ordering 외 모든 현재·미래 tos 형제(현재 19개 committed: canonical·capsule·evidence·time·ordering·
  dsl·rcl·authority·liveauth·orthostate·recon·brokercap·spg·protective·are·ioc·iap·afg·**sbr**[커밋 `9eb13bba` —
  v1.1 m5: 18→19]) 를 import하지 않는다**(default-deny — 규칙을 열거가 아닌 "canonical·ordering 외 전부 금지"로
  서술; produced-bool·주입 좌표로만 참조 — §3.4/§3.5). **PROMOTE 0건. sibling edge 0건(권장).**
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이 `shared.config.secrets`
  (→ `os.environ`)를 무조건 전이 import한다. PR 패키지는 어떤 `shared.*`도 필요로 하지 않는 순수 커널이다.
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`, `shared.llm`, `shared.storage`,
  `shared.backtest`, `services.*`, `cli.*`(`.importlinter` forbidden set).
- **firewall 구조 확인(실측 — #11/#16 §0.3 상속)**: `.importlinter`는 `[importlinter:contract:tos-operational-
  firewall]` type=forbidden·source_modules=`tos` 단일 계약이며 `layered`가 아니다 — intra-tos sibling→sibling edge는
  구조적으로 금지되지 않고 설계 #1 §3.2 "자기 자신 `tos.*`" 허용 조항이 커버한다. **신규 PR 패키지는 firewall
  도구 무수정 자동 포섭**된다(forbidden 계약이 source=tos 전체를 덮으므로). 본 문서는 그럼에도 **sibling edge
  0건**을 **설계 규율**로 유지한다(§0.4b) — protective #11 동형.
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(**allowlist 형식** — `import` 후 `sys.modules`의
  top-level `tos.*` ⊆ {`tos.canonical`, `tos.ordering`, 자기 자신} assert + `shared.config`·`os.environ`·numpy/
  pandas/yaml 부재 assert). required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST +
  `.importlinter` layer-② 전이)와 함께 green이어야 §0.3 선언이 능동 성립.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 위치·명명 = `tos/src/tos/replacement/`.** register domain(EVIDENCE-REGISTER-002 "**Protective
Replacement**")·prefix `PR`(`PR-EV`/`PR-AC`)를 명명 근거로 삼되, 상류 형제 `tos.protective`(#11, ADR-002-001)가
"protective" 토큰을 이미 점유하므로 **본 ADR의 변별 토큰 "Replacement"**를 직접 명명한다. 명명 대안 비교(#11
§0.4a·#16 §0.4a 형식):

- **`tos.pr`(register prefix 직결)(기각·cryptic)**: `PR-EV` prefix와 일치하나 `pr`은 **의미 있는 두문자가 아니다**
  (pull request / public relations 통용) — protective #11이 `tos.prd`를 정확히 같은 이유("cryptic")로 기각한 선례
  동형. 명명 원칙(#16 §0.4a "의미 있는 두문자") 미달.
- **`tos.protrepl`/`tos.protreplace`(기각·cryptic/verbose)**: register domain "Protective Replacement" 직결이나
  `protrepl`은 cryptic, `protreplace`는 verbose하고 terse 명명 관행(canonical/capsule/rcl/recon/spg/are/afg)과
  어긋남.
- **`tos.gap`(기각·좁음)**: ADR 제목의 "Protection-Gap Control"만 명명해 지나치게 좁다 — 본 ADR은 gap뿐 아니라
  overlap(§4.5)·replacement mode(§6)·FQP-gated retirement(§11)·partial-fill(§12)·authorization(§7)를 포함한다.
- **`tos.replace`(기각·collision/좁음)**: `str.replace`/generic "replace"와 의미 충돌·동사형.
- **선택 `tos.replacement`**: **ADR 변별 토큰 "Replacement" 직접 명명**, terse, 명사형(#11 `tos.protective`가
  형용사형을 명사형으로 정착시킨 것과 대칭). gap/overlap은 **replacement-scoped 상태**(§4.4 Protection Gap·§4.5
  Protection Overlap이 replacement 맥락에서 정의됨)이므로 `tos.replacement`가 포섭. **경계 명시(중복 방지)**:
  protective(#11)도 `ProtectiveActionKind.{OVERLAP_FIRST_ADD_ONLY, CANCEL_FIRST_OR_REMOVAL}`를 갖지만 그것은
  **partition-time lease-admissibility 전용**(§9)이고, `tos.replacement`는 그 위의 **일반 replacement-DECISION
  layer**(mode 선택·overlap-first reservation 완전성·cancel-first gate·gap/overlap 상태·workflow lifecycle·FQP-gated
  retirement)를 소유하며 partition-lease-admissibility·capacity 산술·arbiter admissibility를 **소유하지 않는다**
  (§3.5). **naming은 load-bearing이 아니다**(설계 #1 line 164) — 운영자 치환 가능. 실측: `tos/src/tos/replacement`·
  `tos/src/tos/pr` 부재(grep — 충돌 없음). 내부 module(`_base.py`·`vocabulary.py`·`records.py`·`predicates.py`·
  `state.py`)은 protective/rcl/are/afg 선례 동형.

**(b) replacement = produced-bool producer, sibling edge 0건 (중심 결정·권장 — protective #11 동형, 코드 실측).**
PR은 미래 소비자(Protective Action Controller·rcl-admission·final-egress·Reconciliation Service 런타임)의 **상류**다
— overlap-first/partial-fill/cancel-first/authorization completeness·sequencing·gate **bool을 생산**하고, 상류
형제(protective·afg·brokercap·orthostate·rcl·authority·recon·are)가 생산한 값을 **주입 소비**한다. seam 대안 비교
(#11 §0.4b·#16 §0.4b 형식):

- **대안 A — PR이 소비자(rcl)를 import해 decision을 직접 참조**: rcl `GrantDecisionRef`(`authority.py:39`)는
  **"Aggregate Risk / Action Flow decision reference" 전용**(`:40` 실측)이며 **replacement decision slot이 아니다**.
  are/afg는 GRANT/DENY **decision을 생산**해 이 slot으로 흐르지만, **PR은 replacement "decision"을 rcl에 흘리지
  않는다** — PR 산출물은 completeness/sequencing/gate **bool**이며 Cancellation Arbiter/Protective Action
  Controller가 소비한다(protective classification/exhaustion bool이 authority/liveauth로 흐른 것과 동형). ⇒ decision-
  ref import 불요.
- **대안 B — 소비자가 PR을 import**: rcl/protective가 PR을 직접 호출. **기각**: rcl·protective는 **이미 비준·구현**
  됐고 replacement 조건을 주입 슬롯(protective `cancellation_admissible`의 `equivalent_replacement_live` 인자 등)으로
  이미 봉인했다. ratified 패키지를 PR 의존으로 바꾸면 침습이며 acyclic이 깨진다.
- **선택 — decoupled, plain-bool producer(edge 0건)**: PR은 자신의 어휘·워크플로 모델·결정 술어를 저작하고, 출력은
  plain `bool`/StrEnum(`ReplacementOutcome`)으로 미래 소비자 signature와 타입 일치; 소비 방향도 protective/afg/
  brokercap/orthostate/rcl 산출을 **주입 `bool|None`/StrEnum/`CanonicalDecimal`**로 소비하고 형제를 import하지 않는다.
  근거: (i) **최인접 상류 protective #11이 정확히 이 형태**(produced-bool·edge 0·2 core row)이며 본 ADR과 소유권이
  가장 인접하다 — 일관성. (ii) rcl `GrantDecisionRef`가 replacement를 커버하지 않음(대안 A 실측) — PR은 decision-
  producer 가문(are/afg)이 아니라 completeness/admissibility 가문(protective)이다. (iii) edge 0·cycle 원천 차단.
  (iv) **compose seam-sealing**: 타입 일치 + fail-closed 정합, **test-only** 모듈이 PR·(각 상대)를 둘 다 import해
  polarity·fail-closed 대조(테스트 import는 §7.1 package closure 불계상). **운영자 판단 지점(§10.3)**: produced-bool
  decoupled(권장) vs `CapacityVector` REUSE(§0.4c/§0.4d에서 검토·기각).

**(c) `CapacityVector` REUSE(edge-1) 검토 후 기각 — edge 0 권장 (핵심 아키텍처, 사전 브리핑 "이중 계상" 핵심
지점 응답).** overlap-first reservation(§9)이 rcl `CapacityVector`(`vector.py:74`)를 REUSE(pr→rcl edge, are→rcl·
afg→rcl·ioc→rcl 선례)해야 하는지 검토:

- **REUSE 찬성 근거**: ADR §9 line 231 "the Risk Capacity Ledger SHALL atomically commit capacity for the maximum
  aggregate risk over all credible intermediate outcomes" — rcl이 replacement reservation vector를 commit하므로
  are(`AdverseIncrement`)·afg(`ActionFlowVector`)처럼 **PR도 vector를 생산해 rcl이 commit**한다고 볼 수 있다.
- **정정(v1.1 M6 — 실측 재확인)**: v1.0 기각 근거 (i)이 "aggregate-risk vector 산출은 are 소유"라 서술했으나
  **부정확**하다. are `records.py:19–25/61` 실측 verbatim: "are **REUSES the type only** — capacity commit /
  serialize / benefit [reducer not needed]"·"the increment ... uses the rcl `CapacityVector` type (`vector.py:74`,
  ADR-002-002 §6 — **the type owner**) via the single are→rcl sibling edge." 즉 **타입 소유자는 rcl**이고 **산술
  (commit/serialize) 소유자도 rcl**이며, **are는 타입을 REUSE할 뿐 산술을 소유하지 않는다**. "type REUSE ≠
  arithmetic ownership." 따라서 "are가 vector를 소유하므로 PR이 못 쓴다"는 논거는 성립하지 않는다.
- **기각 근거(edge 0 권장 — 재작성)**: (i) **PR의 L1-decidable 핵심은 vector 산술이 아니다** — completeness(9종
  set 포함, set 논리)·**no-netting(구조적 magnitude 파생, 아래 §0.4d·M6 처방(b))**·sequencing(주입 bool)이며,
  vector 합산·headroom(`aggregate_usage ≤ effective_limit`)은 rcl 소유이고 PR은 그 verdict를 **주입 소비**한다
  (§5.1). L1 결정에 rcl `CapacityVector` **타입 자체가 불필요**하다. (ii) **are는 credible-set/risk AXIS를 소유**
  한다 — are `RiskDimensionKind` + scenario 축(`ProjectedCell` are-local, `records.py:61` "carries a scenario axis
  rcl `CapacityVector` does not") — PR은 그 aggregate-risk 값을 **주입 소비**(§9 line 231이 credible set을
  ADR-002-021=are에 bind). PR이 `CapacityVector`를 REUSE하면 **자체 replacement dimension 축을 정의**해야 하고
  are/rcl dimension namespace와 좌표 충돌(§2.2-5). (iii) **최인접 상류 protective #11이 edge 0**(reserve sufficiency·
  partition을 다루면서도 `CapacityVector` 미REUSE, rcl `partition_verdict`/`CapacityState` 주입 좌표 소비) — PR도
  동형. (iv) rcl `GrantDecisionRef`가 replacement 미커버(§0.4b 대안 A) — PR은 decision+vector 생산 가문(are/afg)이
  아니다. ⇒ **edge 0 권장·PROMOTE 0·sibling edge 0**. **운영자 판단 지점(§10.3-1)**: (a) `CapacityVector` REUSE
  (edge-1, pr→rcl 7번째 후보) vs **(b) 구조적 magnitude 파생 no-netting(edge-0, 채택·리뷰어·오케스트레이터 권장)** —
  §0.4d. 미래 런타임에서 PR이 vector를 직접 조립해야 하면 (a)로 승격 가능하나 Phase-1은 (b)로 충분하다.

**(d) overlap-first "원본+대체 동시 커버" ↔ rcl capacity 이중 계상 정합 (핵심 설계 판정).** 사전 브리핑이 지목한
핵심 지점. 판정:

- **이중 계상은 결함이 아니라 보수적 요구다.** overlap-first에서 old protective order와 new protective order는
  동시에 live·fillable하며(§6.2 line 155), worst credible intermediate state는 **둘 다 체결**을 포함한다(§1 line
  25·§9 line 238 "simultaneous old and new fills"). 순진한 replacement 회계는 old를 new로 **netting**(상쇄)하지만,
  overlap-first에서는 **netting 금지** — 둘 다 체결 시 over-close/reversal이 발생하기 때문이다(§20.2 line 443
  "Simultaneous fills can over-close or reverse exposure").
- **정합 메커니즘 — no-netting을 구조적 magnitude로 파생(v1.1 M6 처방(b), edge-0 유지)**: `OverlapReservationClaim`은
  outcome별 **주입 `CanonicalDecimal|None` magnitude**를 담는다(`old_order_remaining`·`new_order_remaining`·
  `simultaneous_fills` 등 9 outcome). **no-netting은 flag가 아니라 파생 성질**이다: `netting_absent`는 **old_order_
  remaining·new_order_remaining·simultaneous_fills가 셋 다 present(not None)·비음수**일 때만 True — netting을 적용
  하면 old를 new로 상쇄해 둘 중 하나가 소거/감액되므로, 둘이 **별개 비음수 magnitude로 병존**하면 netting은 구조적
  으로 불가능하다(caller가 flag로 위조 불가 — v1.0 injected-flag 대비 강건). 하나라도 None/음수 ⇒ netting 의심/
  incomplete ⇒ fail-closed. **PR의 소유**: (i) reservation이 **9종 credible outcome 전부 포함**(`overlap_first_
  reservation_complete` — set 완전성, protective `domain_enumeration_complete` 동형), (ii) **구조적 no-netting 파생**
  (old+new+simultaneous magnitude 병존·비음수). **PR이 소유하지 않는 것**: 합산 산술·hard-envelope 비교(rcl
  `aggregate_usage` `vector.py:103`/`effective_limit` `vector.py:139` — rcl이 dimension별 usage 합산, netting 아님)·
  aggregate-risk 투영(are). "prevents unbounded reversal"(PR-AC-001)은 **구조적으로 이중 계상된(netting-불가)
  reservation이 hard envelope 이하로 유지됨**(rcl `within_hard_envelope` verdict 주입 소비)을 의미한다 — PR은
  completeness+구조적-no-netting을 강제하고 rcl이 합산·bound를 강제한다. **좌표: PR outcome magnitude(replacement
  intermediate 축) → rcl이 dimension별 합산·commit·are가 risk 투영** (§0.4c 좌표 충돌 회피로 PR은 `CapacityVector`
  타입 미REUSE — magnitude는 outcome_kind→CanonicalDecimal 매핑 value로 로컬 표현).
- **좌표 비붕괴**: PR `CredibleIntermediateOutcomeKind`(replacement intermediate 축) ≠ are `RiskDimensionKind`
  (aggregate-risk 축) ≠ rcl `CapacityVector.dimension_id`(경제 capacity 축). 토큰 겹칠 수 있으나 별개 타입(§2.2-5).

**(e) `id=f(digest)` 미채택 (canonical REUSE).** `ReplacementAuthorization`·`ReplacementWorkflowRecord`는
**거버넌스/워크플로 identity**(authorization id·writer epoch·authority epoch·workflow generation §7 line 196)를
가지며, same-id/diff-bytes(위조·재발행·contradictory authorization·double-commit workflow) 탐지에
`classify_record_pair`(`RecordPairKind.CRITICAL_CONFLICT`)를 쓰려면 id⊥digest여야 한다(#4–#16 §3.1 동형). ⇒
`IndependentIdArtifact` 채택, `IdDerivedArtifact`(capsule content-addressed) 미채택. 각 generation은 immutable
append-only이며 정당한 재발행(§7 line 201 material change ⇒ re-evaluation)은 **새 generation**이지 in-place
mutation이 아니다. **`tos.replacement._base`**: canonical 원시타입(`FrozenModel`·`DigestBoundArtifact`·
`IndependentIdArtifact`·`CanonicalDecimal`)의 thin re-export + all-false `ReplacementAuthorityEffect`(label-grants-
nothing §4.4)의 로컬 fresh 정의(rcl `AllFalseAuthority`·are/afg `_base` 동형).

**(f) 앵커 규약 — PR-EV/PR-AC/§-clause/SAFE 앵커, 새 시리즈 창작 금지.** **실측**: ADR-002-011은 `PR-AC-001..012`
(§19 line 420–431, 12종)·`PR-EV-001..012`(register 12행)만 정의하고 **자체 `PR-INV` 시리즈가 없다**(grep 0건). ⇒
본 계약은 모델 불변식·술어를 **`PR-EV-###` / `PR-AC-###` / §-clause / `SAFE-###`(§22)**에 앵커하고 **새 INV/AC/EV
시리즈를 창작하지 않는다**. #9/#11 동형.

**(g) PR-EV = #11 protective형 core tier(2행) but 닫는 PR-EV = 0건.** register 실측: **2행(001·005)이 최소 레벨에
`EV-L1` 슬라이스 보유**(`EV-L1/3`·`EV-L1/3`), 10행은 최소 `EV-L2`+. ⇒ §1 분류는 **core(L1 슬라이스 2) / predicate-
only(2: 002·008) / not-Phase-1(8) 3분류**. **그러나 닫는 PR-EV = 0건** — L1 슬라이스 저작은 EV closure가 아니다
(`/3`·`+Broker` 통합·독립 리뷰 잔여). §1·§4·§5·§7 전체에 **일관**해야 하며 finishing 전 self-consistency pass에서
대조한다(#8 lesson 선제 봉합). **최인접 상류 protective #11과 동일 shape**(2 core row·닫는 EV 0)라 우연이 아니라
register가 replacement의 broker-integration 계열(003·004·006·012 +Broker, 007 L3/5)과 recovery/partition/HALT
계열(009·010·011 L3)을 최소 `EV-L2`+로 고정하기 때문이다.

---

## 1. 범위 매핑 — ADR-002-011 조항별 EV-L1 도달성 (닫는 PR-EV 0건)

EV-level 정의(VER-002-001 line 142–164): **EV-L1 = Model and Property Verification**(state-machine exploration,
model checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integrated System Fault Test**, **+Broker = Broker Capability Profile evidence**, **+Security = independent
security-boundary assessment**. Phase 1은 EV-L1만이다. 합성표기(line 166–172): `EV-Ln/Lm`은 staged scope —
EV-Ln이 **earliest non-live stage**, EV-Lm이 통합/broker 수용 전 추가 요구. `+X`는 EV-Ln을 대체·인하하지 않는다.

> **결정적 사실 1 — PR-EV ↔ PR-AC 1:1, 최소 레벨 실측(오케스트레이터 사전 카운트 확인)**: `PR-EV-001..012`(register)는
> ADR §19 `PR-AC-001..012`(line 420–431)와 제목·번호가 **1:1**. register 최소 레벨 실측(EVIDENCE-REGISTER-002.csv
> **CSV-aware 파싱 — title 필드 쉼표 포함, naive grep/awk 금지**; 12행 전수):
> **`EV-L1` 슬라이스 보유(2행)** = 001(`EV-L1/3`, "Overlap-First Replacement")·005(`EV-L1/3`, "Partial-Fill
> Interleavings"); **`EV-L1` 슬라이스 부재(10행)** = 002(`EV-L2/3` "Cancel-First Admission Gate")·003(`EV-L3+Broker`
> "Missing ACK Replacement Ambiguity")·004(`EV-L3+Broker` "Cancel ACK Is Not Final Quantity Proof")·006
> (`EV-L3+Broker` "New Protection Sufficiency Proof")·007(`EV-L3/5` "Protective Broker-Resource Exhaustion")·008
> (`EV-L2/3` "Replacement Authority Expiry")·009(`EV-L3` "Replacement Crash and Failover")·010(`EV-L3` "Replacement
> Partition")·011(`EV-L3` "HALT and Replacement Precedence")·012(`EV-L3/5` "Broker-Proven Atomic Replace Scope").
> ⇒ **core tier 2행**(#11 protective형 — PRD-EV도 정확히 2행이었다), predicate-only substrate 2행(002·008 —
> L1-decidable이나 register 최소 `EV-L2`), not-Phase-1 8행. **오케스트레이터 사전 실측("L1 슬라이스 2행 = 001·005")과
> 일치 — 정정 없음.**
>
> **결정적 사실 2 — authoring ≠ acceptance(닫는 PR-EV = 0건)**: Phase 1은 core 2행의 **L1-decidable predicate/model
> substrate**를 저작하나 **어떤 PR-EV도 닫지 않는다.** (a) core 2행조차 `/3` 잔여(integration fault·adversarial
> interleaving), (b) 10행은 최소 ≥ L2(+Broker/+L3/+L5), (c) VER-002-001 §5 "Registration is not execution"·ADR §18
> line 410·§24 line 519–531. ⇒ **"EV-L1-complete 주장 금지"**. Owner/Reviewer는 register상 TBD.

**규율 태그(모든 주장에 부착)**: "**predicate/coordinate substrate only; PR-EV-001..012 전부 NOT_IMPLEMENTED —
core 2행(001·005)은 `/3` 통합·독립 리뷰 대기, 나머지 10행은 EV-L2/L3 fault injection·adversarial·+Broker evidence
대기. EV-L1-complete 주장 금지. 닫는 PR-EV = 0건.**"

**ADR-002-011 조항 → Phase-1 분류(core / predicate-only / not-Phase-1[형제 소유·런타임 이연])** — **전 조항 §1–§25
매핑(§-row 완전성 #16 M8 교훈)**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | PR-EV |
|---|---|---|---|---|
| **§6.2** (line 153–159) | Overlap-First Replacement | **core (L1 슬라이스)** | `overlap_first_reservation_complete`+`overlap_first_sequencing_valid`(§5.1) — 9종 credible outcome 완전성·no-netting·new-sufficiency-first. `/3` 잔여. | **001** |
| **§9** (line 229–248) | Risk Capacity Accounting (credible intermediate outcomes) | **core (L1 슬라이스, 001 substrate)** | `CredibleIntermediateOutcomeKind` 9종(§2.2)+completeness(§5.1). 합산 산술은 rcl·aggregate-risk는 are 주입(§0.4d). `/3` 잔여. | **001** |
| **§12** (line 289–302) | Partial Fills and Exposure Changes | **core (L1 슬라이스)** | `partial_fill_reevaluation_complete`(§5.2) — 6종 re-eval 완전성·no-hiding-clamp·risk-increasing⇒deny. `/3` 잔여. | **005** |
| **§6.3** (line 161–176) | Cancel-First Replacement (admission gate) | **predicate-only** | `cancel_first_admission_gate`(§6.1) — 8 전제 verbatim. protective `cancellation_admissible`·brokercap resource·time 주입. 최소 `EV-L2/3`. | **002** |
| **§7** (line 184–204) | Replacement Authorization (expiry) | **predicate-only** | `replacement_authorization_current`(§6.2) — material-change 무효·expiry≠economic-effect(afg `economic_effect_persists` 주입). 최소 `EV-L2/3`. | **008** |
| **§14** (line 324–332) | Missing ACK, Retry, Idempotency | **not-Phase-1** | afg `no_blind_retry`(L1)·brokercap `same_order_retry_allowed` 주입 소비. 최소 `EV-L3+Broker`. | **003** |
| **§11** (line 271–285) | Final Quantity Proof + Old-Order Retirement | **not-Phase-1** | afg `cancel_ack_not_final_quantity_proof`(L1)·brokercap `fqp_adequate`·orthostate CANCELLED+later-fill 주입(§4.6). 최소 `EV-L3+Broker`. | **004** |
| **§10** (line 251–267) | Protection Sufficiency Proof | **not-Phase-1** | protective `protective_classification`·brokercap field-level proof 주입. 최소 `EV-L3+Broker`. | **006** |
| **§13** (line 306–320) | Broker and Market Resource Failure | **not-Phase-1** | protective `retry_admissible`/`protective_capacity_exhausted`·brokercap `rate_admission_ok` 주입. 최소 `EV-L3/5`. | **007** |
| **§16** (line 357–373, crash) | Crash + Failover recovery | **not-Phase-1** | recon `ConservativeBound`·rcl recovery·fence 런타임 주입. 최소 `EV-L3`. | **009** |
| **§5** line 139 (B) — per-leg -019 admissibility | 전 leg가 current exact ADR-002-019 Order Admissibility Decision 바인딩; missing/unknown ⇒ conservative gap/overlap/trapped | **predicate-only (주입 슬롯)** | `leg_admissibility: bool\|None` 주입 슬롯(§5.1/§6.1/§5.3; 양성 증명만 통과, mode 합성점=전 leg frozenset 양성). -019 producer(VTG)는 Phase-1 밖·주입 소비(§3.4 9번째 생산자). trapped ⇒ `ReplacementOutcome.REPLACEMENT_TRAPPED`(§2.2·Q1). 최소 `EV-L2/3`(VTG). | 001/002 (leg-slot) |
| **§5** line 139 (C)·**§16** (partition) | Control-plane/broker Partition (protective 소유) | **not-Phase-1 (protective 소유)** | protective `partition_lease_admissible`(→`Admissibility`) 주입(§4.6; ADR line 139 "ADR-002-001 owns this rule"). 최소 `EV-L3`. | **010** |
| **§8** (line 225) | HALT and Replacement Precedence | **not-Phase-1** | authority `AuthorityState.HALTED`·`PRECEDENCE_RANK`·`restrictive_dominates` 주입. 최소 `EV-L3`. | **011** |
| **§6.1** (line 145–151) | Broker-Proven Atomic Replace Scope | **not-Phase-1** | brokercap "5 replace/amend semantics"(`vocabulary.py:203`) 주입. 최소 `EV-L3/5`. | **012** |
| **§1** (line 15–36) | Decision (central) | **core substrate(분산)** | 워크플로 안전성·worst-credible-state·cancel-ACK≠FQP·new-order≠effective-by-ACK·fail-closed 원칙 → §2 어휘·§4 불변식 전반. | 001–012 공통 |
| **§4.1–4.6** (line 73–101) | Definitions (Obligation/Workflow/Sufficiency/Gap/Overlap/FQP) | **core substrate(분산)** | `ProtectionObligation`·gap/overlap value·`ReplacementMode`·FQP 어휘(§2). FQP는 brokercap/evidence 소유(§4.6 line 99). | 001–012 공통 |
| **§5** line 105–137·line 139 (A) | Orthogonal State (workflow lifecycle) + label≠executable | **core substrate(분산)** | `ReplacementWorkflowState`(7+2, line 124–135)·no-collapse 규율(line 107)·label-grants-nothing(line 137·139 (A) "No lifecycle label ... proves ... executable")(§4.4·§5.3). order/attempt/knowledge는 orthostate·capacity는 rcl(주입). | 001–012 공통 |
| **§6.4** (line 178–181) | No Safe Replacement Mode | **core substrate(분산)** | `ReplacementMode.NO_SAFE_MODE`·`replacement_mode_admissible`(§5.3) — 안전 모드 부재 ⇒ 최안전 protection 유지·containment. | 001–012 공통 |
| **§2** (line 40–56) | Context (non-atomic replace·overlap/gap dual risk) | **narrative** | §2 line 44–54 non-atomic 관측 behavior 9종·line 56 "control both the protection gap and the overlap state" → §4.5 mode 진리표·§6 modes 근거. | — |
| **§3** (line 60–70) | Decision Drivers (8) | **narrative/SAFE 앵커** | Driver 1–8(line 62–69). **Driver 6 line 67 "Protective priority must not be represented as reserved protective capacity"** → priority≠capacity(아래 §9:247 행). | — |
| **§9** line 247·**§20.5** (line 453–455) | Priority ≠ reserved capacity | **not-Phase-1 (protective/rcl 소유)** | §9 line 247 "Priority classification affects scheduling only. It does not create capacity or reserve broker resources"·§20.5 "Priority is not reserved risk capacity or broker capacity" → **protective `GuaranteeLevel.PRIORITIZED_ONLY`≠reserved**(설계 #11 §4.2)·rcl reserve 소유. PR 미소유(주입 소비). | 007 (consumed) |
| **§8** (line 207–226, arbiter) | Cancellation Arbiter Rules | **not-Phase-1 (protective 소유)** | protective `cancellation_admissible`(`predicates.py:523`) 소유·재저작 금지. PR sequencing/gate가 **주입 소비**(§3.5·§0.2). | 004/011 (consumed) |
| **§15** (line 336–353) | Gap and Overlap Bounds + bound-exceed 3 SHALL NOT | **predicate-only(3 SHALL NOT) + not-Phase-1(수치)** | 8 timing bound 수치는 Phase-0/VP-002 4키 실재·null(§8.1)·per-broker INSTANCE. **line 351 3 SHALL NOT**(bound 초과 시 authority 확장·capacity widen·complete 선언 금지) → `bound_exceeded ⇒ REPLACEMENT_CONTAINED` canary(§5.3·§4.7 M5). | 001/002/005 (bound canary) |
| **§17** (line 377–389) | Failure Containment | **not-Phase-1 (런타임)** | containment 실행(deny new risk·preserve capacity·escalate)은 authority/egress/rcl 런타임. PR은 워크플로 상태만. | 009/011 (런타임) |
| **§18** (line 393–410) | Evidence and Observability | **core substrate (재구성)** | frozen digest-bound 레코드 재구성(§5.4). replay ENGINE=ADR-002-016(런타임). Evidence Is Not Authority. | 001–012 공통 |
| **§19** (line 414–431) | Acceptance Cases (PR-AC-001..012) | **앵커** | §0.4f — PR-AC ↔ PR-EV 1:1 앵커. Registration ≠ execution. | 001–012 |
| **§20** (line 435–465) | Rejected Alternatives (7) | **narrative** | §20.1 cancel-then-submit≠ordinary·§20.2 "simultaneous fills over-close/reverse"(§0.4d 이중 계상)·§20.3 "cancel ACK ≠ gone"(§4.6)·§20.4 no-ACK-retry-new-id(§6.3 003)·**§20.5 priority≠capacity**(위 §9:247 행)·§20.6 gap-후-복원 불가·§20.7 recovery-clear-restart 불가(§4.7 clear-workflow-and-restart 금지동사). | — |
| **§21/§22** (line 467–500) | Consequences / Traceability | **narrative/SAFE 앵커** | SAFE-002/004/013(hard envelope·gap/overlap)·011(cancellation non-bypass)·015(RCL-only)·020/021(lineage)·048(partition)·051/052(evidence). | — |
| **§23/§24/§25** (line 504–548) | Open Questions / Approval Gate / History | **Phase-0/non-acceptance** | §23 6 OQ → §9.2. §24 approval gate → §0.2 비-acceptance. | — |
| **§9 rcl commit·§10 field-proof·§16 fence 런타임** | 원자 commit·field-level broker proof·hard fence enforce | **not-Phase-1 (런타임 EV-L2/L3)** | rcl 원자 commit(§9 line 231)·brokercap+broker(§10)·recon/rcl fence(§16). PR은 완전성/비교 술어만. | 001/006/009 (런타임) |

**Phase-1 분류 요약**: **core(L1 슬라이스)** = {§6.2/§9 overlap-first [PR-EV-001], §12 partial-fill [PR-EV-005]} —
**2 PR-EV의 L1 슬라이스뿐, 닫는 PR-EV = 0건.** **predicate-only(EV 주장 금지)** = {§6.3 cancel-first gate
[PR-EV-002], §7 authorization expiry [PR-EV-008], **§5:139 (B) per-leg -019 admissibility 주입 슬롯**(001/002 내),
**§15 bound-exceed 3 SHALL NOT canary**}. **not-Phase-1(형제 소유·런타임 이연)** = {§14→afg/brokercap [003],
§11→afg/brokercap/orthostate [004], §10→protective/brokercap [006], §13→protective/brokercap·priority≠capacity
[007], §16 crash→recon/rcl [009], §5:139 (C)/§16 partition→protective [010], §8 HALT→authority [011], §6.1
atomic→brokercap [012], §8 arbiter→protective, §17 containment→런타임, §15 수치→Phase-0}. (self-consistency: core 2
+ predicate-only 2 PR-EV(+leg-slot·bound-canary substrate) + not-Phase-1 8 + substrate 분산 — §3.5 소유권 분할과
정합.)

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True, extra="forbid")`,
`tos.canonical.FrozenModel` REUSE)로 저작한다. `extra="forbid"`는 **§7 line 201 "Any material change invalidates
the authorization"·§12 line 302 "SHALL NOT be rounded or clamped in a way that hides uncovered quantity"의 스키마
수준 실현**(unknown/silent-drop 차단)이다. frozen은 append-only(§18 evidence·§16 durable recovery)의 레코드 수준
실현이며 모델에 update/delete 연산이 없다. 모든 gap/overlap/timing/aggregate-risk 값은 **주입 `CanonicalDecimal|None`**
(하드코딩 수치 0).

### 2.0 소유권 골격 — replacement는 canonical의 하류, 9개 형제의 하류(주입 소비)·미래 런타임의 상류(produced-bool)

`tos.replacement`는 `tos.canonical`·`tos.ordering`(둘 다 core)만 import한다. dataflow상 replacement는 **미래
소비자(Protective Action Controller·rcl-admission·final-egress) 상류**(completeness·sequencing·gate bool 생산)이자
**protective·afg·brokercap·orthostate·rcl·authority·recon·are·evidence 9개 형제의 하류**(arbiter/classification/FQP/
attempt-state/capacity/HALT/recovery/aggregate-risk/**per-field Protection Sufficiency Proof** 주입 소비 — v1.1 C2:
evidence(ADR-002-006)가 §10 field-proof 생산자)다. 모든 seam은 **produced-bool/StrEnum·주입 좌표(edge 0)**로
실현한다(§0.4b/§0.4c; protective #11 동형). replacement가 **소유·저작하는 것**: replacement 어휘(`ReplacementMode`·
`ReplacementWorkflowState`·`CredibleIntermediateOutcomeKind`·`ReevaluationTargetKind`·`ReplacementOutcome`) +
`ReplacementAuthorization`·`ReplacementWorkflowRecord` digest-bound 레코드 + `ProtectionObligation`·
`OverlapReservationClaim` value + overlap-first/partial-fill/cancel-first/authorization/mode **술어**. **소유하지
않는 것**: capacity 산술(rcl)·Cancellation Arbiter/partition-lease/classification/retry(protective)·cancel-ACK-FQP/
missing-ACK/oscillation L1(afg)·FQP/atomic-replace/idempotency(brokercap)·order/attempt state(orthostate)·HALT
precedence(authority)·recovery(recon)·aggregate-risk 수치(are). §3.5가 상술.

### 2.1 digest-bound / plain-frozen / value / reference 분류 (총괄)

| 모델 | 분류 | 근거 |
|---|---|---|
| `ReplacementAuthorization`(§7) | **digest-bound `IndependentIdArtifact`** | §7 line 188–199 "Every replacement authorization SHALL bind…" **12항 전수(v1.1 M4 복원)**: (1)authorization/workflow id·(2)**scope tuple: Safety Cell/account/portfolio/strategy/broker/environment**(line 189)·(3)old/new intent id+lineage·(4)obligation+**current exposure version**(line 191)·(5)mode·(6)max overlap/gap·(7)capacity id+upper bounds·(8)broker capability/session·(9)writer/authority epoch·revocation generation·egress identity·(10)time-health·(11)profile version·(12)**completion/failure/containment conditions**(line 199 — §15:351 pre-authorized containment digest 고정 근거); id⊥digest(거버넌스 identity·same-id/diff-bytes 위조·contradictory authorization 탐지). |
| `ReplacementWorkflowRecord`(§5) | **digest-bound `IndependentIdArtifact`** | §5 line 110–120 "SHALL retain independently" **10항**(old/new intent id·attempt id·broker order lineage·knowledge confidence·rcl reservation id·obligation version·cancellation authz id·overlap/gap assessment·exposure basis·workflow generation/owner epoch); orthogonal 축을 **별개 필드**로 보존(no-collapse §5 line 107). |
| `ProtectionObligation`(§4.1) | **plain-frozen value** | §4.1 line 77 "versioned requirement"(scope·side·protected quantity·trigger/price·duration·venue·max gap·max overlap·ownership·policy identity). obligation version은 좌표 scalar. **소비처(v1.1 m8/G6)**: `partial_fill_reevaluation_complete`의 `REMAINING_PROTECTIVE_OBLIGATION` target(§5.2·§12 line 293) — 재평가가 obligation version을 갱신; `overlap_first_sequencing_valid`가 max-overlap/max-gap 좌표 참조(§5.1). |
| `OverlapReservationClaim`(§9) | **plain-frozen value(주입)** | §9 line 234–243 credible outcome별 예약 + `reserved_outcome_kinds: frozenset[CredibleIntermediateOutcomeKind]` + **per-outcome `magnitudes: Mapping[CredibleIntermediateOutcomeKind, CanonicalDecimal\|None]`**(v1.1 M6 처방(b) — `old_order_remaining`·`new_order_remaining`·`simultaneous_fills` 별개 비음수 magnitude로 **no-netting을 구조 파생**; injected flag 아님) + 주입 aggregate-risk 비교값(`CanonicalDecimal`) + `within_hard_envelope: bool\|None`(rcl verdict 주입). |
| classification/cancellation/partition 입력 value | **plain-frozen value(주입)** | protective `Admissibility`·`cancellation_admissible` bool·are aggregate-risk·rcl `partition_verdict`·orthostate order-state·afg cancel-ACK bool·brokercap FQP/replace-semantics·time-trust (전부 `bool\|None`/StrEnum/scalar). |
| `ReplacementAuthorityEffect`(§5/§4.4) | **plain-frozen all-false** | rcl `AllFalseAuthority`·afg `ActionFlowGovernorEffect` 동형; 어떤 True도 unconstructable(§5 line 137 "No lifecycle label by itself authorizes capacity release or removal of protection"). |
| `ReplacementMode`/`ReplacementWorkflowState`/`CredibleIntermediateOutcomeKind`/`ReevaluationTargetKind`/`ReplacementOutcome` | **StrEnum(어휘)** | §2.2 verbatim. |
| `CanonicalDecimal`(gap/overlap/exposure/risk 값) | **REUSE core `tos.canonical`**(이미 존재) | §3.1 — PROMOTE 불필요. |

> **핵심 설계 결정 — 레코드는 immutable generation별 append-only(#10/#11/#16 상속)**: `ReplacementAuthorization`·
> `ReplacementWorkflowRecord`는 시간에 따라 **재발행**된다(§7 line 201 material change ⇒ re-evaluation·§16 recovery ⇒
> new authority). 하나의 stable id에 mutable 내용을 담으면 정당한 재발행이 same-id/diff-bytes `CRITICAL_CONFLICT`로
> **오탐**된다. ⇒ **각 generation은 fresh id를 가진 immutable 레코드**다. same identity + diff canonical digest ⇒
> `CRITICAL_CONFLICT`(위조·재발행 위조·contradictory authorization·double-commit workflow만); 정당한 개정 ⇒ **새
> generation**. generation 순서는 `tos.ordering`(§3.2).

### 2.2 어휘 (verbatim 전사 — 에라타 defect class 주의·항목 수 대조 #16 M4)

> **전사 규율**: enum 값·순서는 ADR 원문에서 **verbatim**이며(스펙 토큰=코드 토큰), 각 블록에 ADR line·항목 수를
> 병기한다(#16 M4 절단 인용·항목 수 누락 교훈). **미열거 값은 fail-closed**(§4.7).

**(1) `ReplacementMode`(StrEnum) — ADR §6 (line 143–181), 4종:**

```text
BROKER_PROVEN_ATOMIC   (§6.1 line 145 — active Broker Capability Profile이 exact semantics를 증거로 증명한 경우만)
OVERLAP_FIRST          (§6.2 line 153 — new protection이 old 제거 전 확립; preferred)
CANCEL_FIRST           (§6.3 line 161 — old protection이 new 확립 전 제거; Protection Gap 생성·8조건 gate)
NO_SAFE_MODE           (§6.4 line 178 — 셋 다 unsafe ⇒ replacement 미가용, 최안전 protection 유지·containment)
```

**방향 극성 주의(§4.5 진리표)**: `OVERLAP_FIRST`(new→old, gap 없음·overlap 위험)와 `CANCEL_FIRST`(old→new, gap
위험·overlap 없음)는 **반대 방향 규칙**이다 — 혼동 금지. **경계 명시(좌표 비붕괴 §2.2-5)**: 이 `ReplacementMode`는
**일반 replacement 워크플로 모드**이며 protective `ProtectiveActionKind.{OVERLAP_FIRST_ADD_ONLY, CANCEL_FIRST_OR_
REMOVAL}`(`vocabulary.py:180`, **partition-time lease-admissibility 전용**)와 **별개 타입**이다. 토큰이 겹치나(둘 다
overlap-first/cancel-first 개념) 스코프가 다르다 — partition 중에는 PR `ReplacementMode`가 protective `ProtectiveAction
Kind`로 매핑되어 `partition_lease_admissible` verdict를 소비한다(§3.4 seam).

**(2) `ReplacementWorkflowState`(StrEnum) — ADR §5 (line 124–135), 7 + 2종 verbatim:**

```text
PLANNED  ->  CAPACITY_COMMITTED  ->  FIRST_LEG_SENT  ->  INTERMEDIATE_STATE
         ->  NEW_PROTECTION_PROVEN  ->  OLD_FINALITY_PENDING  ->  COMPLETED
Any state          ->  FAILED_CONTAINED
Any uncertain state ->  RECOVERY_REQUIRED
```

**주의(§5 line 137 verbatim)**: "**No lifecycle label by itself authorizes capacity release or removal of
protection.**"·line 139 "No lifecycle label or 'protective' classification proves that cancel, amend, replace,
reduce-only, or new protection is executable." ⇒ 워크플로 상태는 **비권위 좌표**이며 `ReplacementAuthorityEffect`
all-false로 label-grants-nothing을 타입 수준 봉인(§4.4). **이 워크플로 축은 orthostate order/attempt/knowledge 축과
별개**(§5 line 107 no-collapse; 좌표 비붕괴 §2.2-5).

**(3) `CredibleIntermediateOutcomeKind`(StrEnum) — ADR §9 (line 234–243), 9종 verbatim(항목 수 대조 = 9):**

```text
CURRENT_EXPOSURE_UNPROTECTED     (§9 "current exposure without sufficient protection")
OLD_ORDER_REMAINING_EXECUTABLE   (§9 "old-order remaining executable quantity")
NEW_ORDER_REMAINING_EXECUTABLE   (§9 "new-order remaining executable quantity")
SIMULTANEOUS_OLD_AND_NEW_FILLS   (§9 "simultaneous old and new fills")
PARTIAL_FILLS_EVERY_ORDERING     (§9 "partial fills in every relevant ordering")
OVER_CLOSE_AND_REVERSAL          (§9 "over-close and reversal exposure")
TEMPORARY_LOSS_OF_PROTECTION     (§9 "temporary loss of trigger, price, or venue protection")
COMMISSION_MARGIN_MARKET_BOUNDS  (§9 "commissions, margin, multiplier, currency, and market-movement bounds")
BROKER_SCARCITY_PREVENTS_PROTECTION (§9 "broker order-count, cancel, and rate-limit scarcity where it can prevent protection")
```

**required 집합 = 9종**(overlap-first reservation completeness의 최소 우주 §5.1). 미열거 outcome ⇒ reservation
incomplete(§4.1). **이 9종은 §9의 구조적 축**이며 aggregate-risk 수치 자체는 are 주입(§0.2·§0.4d).

**(4) `ReevaluationTargetKind`(StrEnum) — ADR §12 (line 292–298), 6종 verbatim(항목 수 대조 = 6):**

```text
REMAINING_PROTECTIVE_OBLIGATION  (§12 "the remaining protective obligation")
OLD_AND_NEW_EXECUTABLE_QUANTITIES (§12 "old and new executable quantities")
OVERLAP_AND_GAP_RISK             (§12 "overlap and gap risk")
CAPACITY_COMMITMENTS             (§12 "capacity commitments")
CANCELLATION_AUTHORIZATION       (§12 "cancellation authorization")
PENDING_TRANSMISSION_CONFORMANCE (§12 "whether any pending transmission remains conformant")
```

**required 집합 = 6종**(partial-fill re-evaluation completeness의 최소 우주 §5.2). 미재평가 target ⇒ incomplete
(§4.2). §12 line 291 "Every fill or recognized exposure change invalidates stale quantity calculations and triggers
atomic re-evaluation of" — 원자적 6종 전부.

**(5) `ReplacementOutcome`(StrEnum, 로컬 결과) — 술어 산출:**

```text
REPLACEMENT_ADMISSIBLE   (overlap-first 완전·sequencing 유효, 또는 cancel-first 8조건 충족)
REPLACEMENT_DENIED       (§6.3 line 176 "cancel-first replacement is denied"·§12 line 300 risk-increasing deny)
REPLACEMENT_CONTAINED    (§6.4 line 180·§17 — 안전 모드 부재·deviation·bound 초과 ⇒ 최안전 protection 유지·containment)
REPLACEMENT_TRAPPED      (§5 line 139 (B) leg admissibility 부재·partition scope 밖 ⇒ 전송 불가·보수적 "trapped-exposure treatment" 유지; v1.1 M1-⑤/Q1)
REPLACEMENT_UNKNOWN      (credible-state-space 미경계·∅ 입력 ⇒ conservatively UNKNOWN, §9 line 231·§4.7)
```

`ReplacementOutcome`에는 **"assume-admissible" 기본 생성 경로가 없다**(§4 fail-open 봉합) — ADMISSIBLE는 양성
conjunction identity로만 도달(#16 CRITICAL 교훈). 소비 게이트는 `outcome is ReplacementOutcome.REPLACEMENT_ADMISSIBLE`
identity로만(truthy 관통 금지 §4.7). **`REPLACEMENT_TRAPPED` 판정(v1.1 M1-⑤/Q1 해소)**: leg admissibility(-019) 부재·
partition scope 밖으로 exposure가 전송 불가하나 보수적으로 커버되는 상태를 **5번째 값으로 명시**한다 — 이는
protective `Admissibility.TRAPPED`(`vocabulary.py:138`)·rcl `CapacityState.TRAPPED_CONSUMED`(`vocabulary.py:30`)와
**별개 좌표**(replacement outcome 축; §2.2-5 비붕괴)이며 그 둘을 재저작하지 않고 좌표 소비한다. `REPLACEMENT_CONTAINED`
(능동 containment action)와 구분: TRAPPED = exposure 커버·전송 불가·추가 action 부재.

**(6) 좌표 어휘(비붕괴 — 본 절 §2.2-5가 좌표-비붕괴 canonical 위치)**: replacement `ReplacementMode`(워크플로 모드
축) ≠ protective `ProtectiveActionKind`(partition-lease 축, `vocabulary.py:180`) ≠ orthostate `BrokerOrderState`/
`TransmissionAttemptState`(order/attempt 축) ≠ rcl `CapacityState`(capacity 축, `vocabulary.py:15`)·`CapacityVector.
dimension_id`(경제 dimension 축) ≠ are `RiskDimensionKind`(aggregate-risk 축) ≠ replacement `CredibleIntermediate
OutcomeKind`(replacement intermediate 축). 토큰 겹칠 수 있으나(overlap-first·cancel·trapped·reversal 등) **별개
타입**. **핵심**: overlap-first의 old+new 동시 커버는 replacement intermediate 축(9종)의 completeness이고, are
aggregate-risk(경제)와 rcl capacity(경제)는 그 위 산술 축이다 — PR은 intermediate 축의 완전성만 판정한다(§0.4d).

### 2.3 아티팩트 covered + self-exclusion (설계 #4 §3.3 상속)

covered(digest preimage) = 각 레코드의 구조적 identity/scope/version/generation + (`ReplacementAuthorization`, **§7
line 188–199 12항 전수 v1.1 M4**) authorization/workflow id·**Safety Cell/account/portfolio/strategy/broker/
environment scope tuple**(189)·old/new intent id+lineage·obligation+**current exposure version**(191)·mode·max
overlap/gap 참조·capacity commitment id+upper bounds·broker-capability/session profile 참조·writer/authority epoch·
revocation generation·egress identity·time-health generation·artifact/config/Safety-Profile/Verification-Profile
version·**completion/failure/containment conditions**(199) + (`ReplacementWorkflowRecord`) old/new intent·attempt·
broker-order lineage·knowledge/evidence confidence 참조·rcl reservation/commitment id·obligation version·cancellation
authz id·overlap/gap assessment·exposure basis·workflow generation/owner epoch(§5 line 110–120 verbatim). preimage 제외:
`*_id`·`canonical_digest`·`canonicalization_version`·`status`(ArtifactStatus)·`*_generation`(ledger placement)·파생
역참조. **`_REQUIRED_COVERED`는 structural identity/scope/version만**(numeric magnitude·gap/overlap 값 제외 — Phase-1
null bound에서 ISSUED 도달 가능; missing magnitude는 consuming 술어에서 fail-closed, #13/#16 §2.3 규율 상속).
`ReplacementAuthorization`·`ReplacementWorkflowRecord`는 특히 **forward-only**: 미래 Capacity Commitment identity를
covered에 담지 않는다(non-cyclic; rcl이 원자 commit — §9·§0.4b).

---

## 3. canonical / ordering REUSE + 9-생산자 주입 seam + 형제 경계

### 3.1 canonical REUSE + `id=f(digest)` 미채택

`ReplacementAuthorization`·`ReplacementWorkflowRecord`는 `tos.canonical.IndependentIdArtifact`·`DigestBoundArtifact`를
REUSE한다. canonicalizer는 `tos.canonical` registry + `EVL1ProvisionalCanonicalizer`(`ev-l1-provisional-0`) REUSE,
**신규 canonicalizer 없음**(프로덕션 canonical form은 Phase-0 §9.2). gap/overlap/exposure/risk magnitude는 **이미
core인 `CanonicalDecimal`** REUSE(NaN/infinity 구성-거부·`1.0` vs `1.00` digest drift 차단; bare `Decimal`/float
금지). **`id=f(digest)` 미채택**(§0.4e 근거·거버넌스/워크플로 identity + same-id/diff-bytes 위조 탐지). **PROMOTE =
0건**(IndependentIdArtifact·classify_record_pair·CanonicalDecimal 전부 이미 core — #6/#9가 PROMOTE 완료, 본 문서는
후속으로서 PROMOTE 부담 없음).

### 3.2 ordering REUSE (replacement generation / authorization / workflow append-only 순서)

replacement generation·authorization 재발행·workflow 전이의 append-only 순서는 신규 저작하지 않고 `tos.ordering`
(`Ordering`·`OrderingEvent`·`compare_order`, `tos.canonical`만 의존)를 REUSE한다. **wall clock은 순서를 만들지
않는다**(§15 line 349 "Every measured duration SHALL use ADR-002-008 trustworthy time"·§7 line 203 "Authorization
expiry ... does not expire the economic effect"와 정합) — replacement는 clock을 읽지 않는다(§3.5; time-health
generation·validity는 주입 flag). Generation은 별도 heavy 아티팩트가 아니라 각 레코드의 `*_generation: int` 좌표 +
ordering 비교로 실현(#13/#16 동형). light REUSE(core 의존, 신규 edge 아님).

### 3.3 REUSE 요약 표

| substrate | 결정 | 근거 |
|---|---|---|
| `FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`ArtifactStatus` | **REUSE(core `tos.canonical`)** | §3.1; 신규 없음 |
| `classify_record_pair`·`RecordPairKind` | **REUSE(core)** | §3.1; same-id/diff-bytes·contradictory authorization·double-commit workflow |
| `CanonicalDecimal` | **REUSE(core, #9 PROMOTE됨)** | §3.1/§0.4e; gap/overlap/risk magnitude·NaN 구성-거부·PROMOTE 불필요 |
| `Ordering`·`OrderingEvent`·`compare_order` | **REUSE(core `tos.ordering`)** | §3.2; generation/authorization/workflow 순서 |
| replacement 어휘·2 digest-bound 레코드·`ProtectionObligation`·`OverlapReservationClaim`·all-false authority·술어 | **로컬 저작** | §0.4a/§2; ADR §5–§18 verbatim·decision-side |
| protective `cancellation_admissible`/`partition_lease_admissible`/`protective_classification`/`retry_admissible` · afg `cancel_ack_not_final_quantity_proof`/`no_blind_retry`/`economic_effect_persists` · brokercap `fqp_adequate`/replace-semantics/`same_order_retry_allowed`/`rate_admission_ok` · orthostate `BrokerOrderState`/`TransmissionAttemptState` · rcl `CapacityState`/`partition_verdict`/`aggregate_usage` · authority HALT precedence · recon `ConservativeBound` · are aggregate-risk | **미소유 — 주입 좌표/produced-bool로만 소비** | §3.4; 9-생산자 seam |
| capacity 산술(원자 commit)·arbiter admissibility·FQP·atomic-replace·attempt 상태기계·HALT·recovery·aggregate-risk 수치 | **미소유 — rcl/protective/brokercap/orthostate/authority/recon/are/런타임/INSTANCE 이연** | §3.5 |
| PROMOTE | **0건** | §3.1 |
| sibling edge | **0건(권장)** | §3.4; protective #11 동형 (`CapacityVector` REUSE=edge-1은 §0.4c 기각·판단 지점) |

### 3.4 9-생산자 주입 seam(edge 0) — produced-bool/좌표 소비 (중심, 코드 실측)

**(a) replacement = 주입 소비자 + produced-bool 생산자(§0.4b).** replacement는 형제를 **import하지 않고**, 그들이
생산한 bool/StrEnum/scalar를 주입 소비하며 미래 소비자가 소비할 completeness/gate bool을 생산한다. **코드 실측
seam**(sibling 서사 아님 — #10 MAJOR-1·#8 line 791 교훈; 전 인용 grep 실측):

| replacement 소비/생산 (§4/§5/§6) | 타입 | 상대 (이미 비준·구현) | signature(실측 file:line) |
|---|---|---|---|
| **[소비]** cancellation admissibility | `bool` | protective `cancellation_admissible` | replacement `overlap_first_sequencing_valid`/`cancel_first_admission_gate`가 주입 소비(`protective/predicates.py:523`; `equivalent_replacement_live`로 "no optimistic credit for submitted/acked replacement" §11.4 line 506 이미 처리; `is not True⇒not admissible`) |
| **[소비]** partition-time lease admissibility | **`Admissibility` StrEnum** | protective `partition_lease_admissible` | replacement partition 처리(PR-EV-010)가 주입 소비(`protective/predicates.py:460`→ ADMISSIBLE/TRAPPED/PROHIBITED `vocabulary.py:118`; **`verdict is Admissibility.ADMISSIBLE`로만 통과** — TRAPPED/PROHIBITED/None ⇒ deny; PR `ReplacementMode.OVERLAP_FIRST`→protective `ProtectiveActionKind.OVERLAP_FIRST_ADD_ONLY` 매핑) |
| **[소비]** protective classification present (**aggregate-risk 축, C2 정정**) | `bool` | protective `protective_classification`/`protective_classification_present` | replacement `overlap_first_sequencing_valid`의 **별개 입력** 주입 소비(`protective/predicates.py:246/309`; docstring 명제 = "**True only when PROTECTIVE_PROVEN via conservative aggregate-risk analysis**" — **§10 per-field sufficiency와 다른 축**, v1.1 C2; `is True`만 통과) |
| **[소비]** **new Protection Sufficiency Proof current (§10 per-field, C2 신규 9번째 생산자)** | `bool` | **evidence(ADR-002-006) per-field proof + brokercap `broker_capability_sufficient`** | replacement `overlap_first_sequencing_valid`의 `new_protection_sufficiency_current` 주입 소비(§10 line 254–263 9-field; `broker_capability_sufficient` `brokercap/predicates.py:206`; §1 line 34 "ACK alone ≠ effective protection"; **PR-EV-006 좌표·+Broker 이연**; `is True`만) |
| **[소비]** **per-leg -019 Order Admissibility (M1 신규; v1.2 에라타 정정)** | **`OrderAdmissibilityResult` 4토큰 → caller 접기 → `bool`** | **venue `OrderAdmissibilityResult`**(`venue/vocabulary.py:91`) + **venue `protective_label_no_bypass`**(`venue/predicates.py:599`) | **v1.1 서술("VTG producer는 Phase-1 밖·코드 부재")은 실측 부정합 — producer가 `tos.venue`로 착지**(설계 #19). 실 producer는 **4토큰**(`ADMISSIBLE`/`RESTRICTED_PROTECTIVE_ONLY`/`INADMISSIBLE`/`UNKNOWN`) **truthy-untestable StrEnum**(`__bool__` ⇒ `TypeError` 봉인)이고 replacement 슬롯은 `bool\|None`이다. **접기 규칙(비준)**: caller-side에서 **`result is OrderAdmissibilityResult.ADMISSIBLE`일 때만 `True`**; 나머지 3토큰·`None` ⇒ not-True ⇒ fail-closed. **`RESTRICTED_PROTECTIVE_ONLY`은 직접 접기에서 `False`**(ADR-002-019 §1:29/§19:426 — ordinary new risk 불허). 그 하에서 protective-라벨 leg의 세부 허용은 **venue 소유 `protective_label_no_bypass`**(실측 signature: `(label_is_protective, exact_admissibility, separate_protective_authority, intermediate_effects_capacity_covered) -> bool`)를 caller가 조합해 산출한 bool로만 슬롯에 착륙 — **replacement는 재결정하지 않는다**(§3.5 권위 중복 배제). 소비처: `overlap_first_sequencing_valid`/`cancel_first_admission_gate`/`replacement_mode_admissible`(§5 line 139 (B); missing/unknown ⇒ `REPLACEMENT_TRAPPED`; `is True`만). seam 테스트 `test_seam_vtg` **작성됨**(§7). |
| **[소비]** retry admissibility / exhaustion | `bool` | protective `retry_admissible`/`protective_capacity_exhausted` | replacement PR-EV-007 주입 소비(`protective/predicates.py:588/623`) |
| **[소비]** cancel-ACK≠FQP / missing-ACK / economic-effect-persists | `bool` | afg `cancel_ack_not_final_quantity_proof`/`no_blind_retry`/`economic_effect_persists` | replacement PR-EV-004/003·`replacement_authorization_current`(expiry) 주입 소비(`afg/predicates.py:794/713`·`afg/state.py`; §4.6 핵심 판정) |
| **[소비]** FQP adequacy / atomic-replace semantics / idempotency / rate | `bool`·StrEnum | brokercap `fqp_adequate`/replace-amend-semantics/`same_order_retry_allowed`/`rate_admission_ok` | replacement PR-EV-004/012/003/007 주입 소비(`brokercap/predicates.py:595/377/437`·`vocabulary.py:203` "5 replace/amend semantics") |
| **[소비]** old/new order·attempt 상태 | StrEnum | orthostate `BrokerOrderState`/`TransmissionAttemptState` | replacement PR-EV-004/003 좌표 소비(`orthostate/vocabulary.py:92`(broker-order; CANCELLED `:115`+later-fill `:103–104`)·`:61`(attempt; SENT_UNCONFIRMED `:86`·SEND_FAILED_PROVEN `:88`)) |
| **[소비]** capacity state / partition verdict / headroom | StrEnum·value·`bool` | rcl `CapacityState`/`partition_verdict`/`aggregate_usage`·`effective_limit` | replacement overlap-first headroom·partition·PR-EV-009 주입 소비(`rcl/vocabulary.py:15`(TRAPPED_CONSUMED `:30`)·`predicates.py:711`·`vector.py` `aggregate_usage`/`effective_limit`; None⇒UNKNOWN 전파) |
| **[소비]** HALT precedence | StrEnum·`bool` | authority `AuthorityState.HALTED`·`PRECEDENCE_RANK`·`restrictive_dominates` | replacement PR-EV-011 주입 소비(`authority/vocabulary.py:47/54`·`restrictive_dominates`) |
| **[소비]** recovery conservative bound | value | recon `ConservativeBound` | replacement PR-EV-009 주입 소비(`recon/records.py:28`) |
| **[소비]** aggregate-risk 비교값 | `CanonicalDecimal` | are aggregate-risk projection(ADR-002-021) | replacement overlap-first reversal-bounded·§9 주입 소비(#13 are; 수치 미산출 §0.2) |
| **[생산]** overlap-first/partial-fill/cancel-first/authorization completeness·gate | `bool`·`ReplacementOutcome` | 미래 Protective Action Controller·rcl-admission·final-egress 런타임 | replacement 술어 산출(§5/§6); 소비자 배선은 런타임(§9.1) |
| **[생산]** all-false authority block | (all-false) | 미래 런타임 (label-grants-nothing) | replacement `ReplacementAuthorityEffect`(로컬 fresh, `_base` `AllFalseAuthority`; 어떤 True도 unconstructable — rcl `authority.py` 동형) |

**(b) 정직 공개 — 전용 술어 실재 vs 좌표-의존 구분 (under-realization 봉합 #7/#11/#16 M7)**: 전용 술어가 **실재**
하는 상대(주입 결과를 정의된 replacement 술어로 소비): protective(`cancellation_admissible`·`partition_lease_
admissible`·`protective_classification`·`retry_admissible`)·afg(`cancel_ack_not_final_quantity_proof`·`no_blind_
retry`·`economic_effect_persists`)·brokercap(`fqp_adequate`·`same_order_retry_allowed`·`rate_admission_ok`·5 replace/
amend semantics) — 이들은 §3.4 표에서 **produced-bool/StrEnum 전용 슬롯**으로 소비되고 §7에 전용 seam 테스트를 둔다.
반면 아래 seam은 **전용 replacement-bool 슬롯이 부재한 좌표-의존**이라 정직 이연:
- **orthostate**: order/attempt 상태는 replacement 술어가 **좌표 소비**(주입 StrEnum)하나 orthostate records에 전용
  replacement-bool 필드는 **부재**(#13 are-orthostate·#16 afg-orthostate 동형 정직 이연). replacement PR-EV-004는
  afg `cancel_ack_not_final_quantity_proof`(정의 술어)를 소비하고 orthostate CANCELLED+later-fill을 좌표 입력으로 받는다.
- **rcl `partition_verdict`/`aggregate_usage`**: 주입 verdict/value. replacement는 rcl capacity를 판정·mutate하지
  않는다(§0.2).
- **authority/recon/are**: 전부 주입 opaque flag/bound/scalar. replacement는 이들을 판정하지 않는다.

> **명제 동일성 검사(시리즈 규율 개선 3 — v1.1 C2 category-error 재발 방지)**: 형제 술어를 주입 슬롯으로 소비하기
> 전, **형제 술어 docstring 명제 ↔ 소비하려는 ADR 조항 명제**가 **동일한지** 대조한다. 다르면 좌표-의존 이연/
> 별개 슬롯으로 강등한다. **본 사이클 적용(C2 exemplar)**: v1.0은 overlap-first sequencing의 "new Protection
> Sufficiency Proof current"(§6.2:159, ADR §10 per-field·ADR-002-006)를 protective `protective_classification_
> present`(명제="PROTECTIVE_PROVEN via aggregate-risk analysis")로 조달 — **명제가 다르다**(aggregate-risk 축 ≠
> per-field sufficiency 축). ⇒ v1.1에서 **분리**: sequencing은 (i) `new_protection_sufficiency_current`(§10 field-
> proof, evidence/brokercap, PR-EV-006) + (ii) `protective_classification_present`(aggregate-risk, 별개) + (iii)
> `cancellation_admissible`(arbiter) **3-입력 conjunction**으로 조달(§5.1). ADR §1:34 "a request emitted or transport
> ACK ... does not count as effective protection"이 (i)의 fail-closed 근거다(§4.6a 신규 불변식).

**(c) replacement는 mutate/transmit/issue/claim/commit하지 않는다(§1 line 21·§17 런타임·§5 line 137).** replacement는
completeness/gate bool·`ReplacementOutcome`·워크플로 레코드만 생산하고 capacity mutation·egress transmit·capability
issue·arbiter override·live-scope set 메서드가 **부재**하다(§4.4). 소비 authority(protective arbiter·rcl serialize/원자
commit·final egress)가 실제 action을 gate한다.

**(d) seam cross-check = MANDATED(test-only).** Phase 1은 **test-only** 모듈(`tos/tests/replacement/test_seam_
protective.py`·`test_seam_afg.py`·`test_seam_brokercap.py`·`test_seam_orthostate.py`·`test_seam_rcl.py`)에서
replacement·(각 상대)를 **둘 다 import**해 (i) replacement sequencing ↔ protective `cancellation_admissible`
(`is not True⇒not admissible`)·partition ↔ `partition_lease_admissible` **3값(ADMISSIBLE/TRAPPED/PROHIBITED)+None
전수 polarity — `is ADMISSIBLE`만 통과**, (ii) replacement PR-EV-004 좌표 ↔ afg `cancel_ack_not_final_quantity_proof`·
orthostate CANCELLED+later-fill polarity, (iii) replacement PR-EV-012 ↔ brokercap 5 replace/amend semantics·
`fqp_adequate`, (iv) replacement overlap-first headroom ↔ rcl `aggregate_usage`/`effective_limit`(None⇒UNKNOWN) 정합을
assert한다. **이 테스트는 package edge가 아니다** — 테스트 import는 §7.1 package-closure 불계상(#11/#13/#16 동형).
**acyclic**: replacement↛{18 형제} ∧ 그들↛replacement(전부 replacement 조건을 주입 flag로 소비·생산; protective
`cancellation_admissible`의 `equivalent_replacement_live` 인자가 replacement 조건 주입 슬롯 — replacement가 상류).

### 3.5 소유권 분할표 — replacement가 소유 / 형제에서 소비·생산 (본 문서 최대 함정 지대, #11/#16 §3.5 상속)

> **소유권 분할 명시(#8 C1·#11·#16 교훈 — cross-section 혼동 선제 봉합)**: ADR-002-011은 **broker-directed
> protective-order replacement의 mode 선택·overlap-first reservation 완전성·cancel-first admission·gap/overlap
> 상태·workflow lifecycle·FQP-gated retirement·partial-fill re-evaluation 결정 프로토콜**만 결정하며 capacity
> serialization/원자 commit(rcl)·Cancellation Arbiter admissibility(protective)·partition-lease-admissibility
> (protective)·protective classification/retry(protective)·cancel-ACK≠FQP/missing-ACK L1(afg)·FQP/atomic-replace/
> idempotency(brokercap)·order/attempt state(orthostate)·HALT precedence(authority)·recovery(recon)·aggregate-risk
> (are)를 **소유하지 않는다**. 함정: replacement가 protective의 `cancellation_admissible`·afg의 `cancel_ack_not_
> final_quantity_proof`·brokercap의 `fqp_adequate`를 재저작하면 권위 중복(#8 lesson). 아래 표가 경계를 코드 실측으로
> 고정한다. 인용은 전부 **코드 실측 signature+라인**(sibling 설계 서사 아님).

| ADR 조항/개념 | replacement 소유 (Phase 1) | 형제 소유 (재저작 금지) | seam 방향(실측) |
|---|---|---|---|
| §6.2 overlap-first + §9 credible outcomes | `overlap_first_reservation_complete`·`overlap_first_sequencing_valid`·`CredibleIntermediateOutcomeKind`(§5.1) | rcl `CapacityVector`/`aggregate_usage`/`effective_limit` 산술·원자 commit(`vector.py`·`predicates.py:711`)·are aggregate-risk 투영 | replacement가 9-outcome 완전성·no-netting 판정 → rcl이 vector 합산·commit(주입 verdict 소비); are가 risk 투영(주입 값) — §0.4d 이중 계상 정합 |
| §12 partial-fill re-evaluation | `partial_fill_reevaluation_complete`·`ReevaluationTargetKind`·no-hiding-clamp(§5.2) | rcl capacity 재commit·orthostate fill state·brokercap lot/multiplier | replacement가 6-target 완전성·clamp-금지 판정 → rcl/orthostate가 실 재계산(주입 소비) |
| §6.3 cancel-first admission | `cancel_first_admission_gate`(8조건, §6.1) | protective `cancellation_admissible`(`predicates.py:523`)·brokercap resource·time-trust | protective cancellation bool → replacement 주입 소비; replacement가 8 replacement-mode 조건 추가(arbiter 재저작 아님) |
| §7 replacement authorization | `ReplacementAuthorization` 레코드·`replacement_authorization_current`(§6.2) | authority/liveauth epoch·revocation·final-egress identity(런타임) | replacement가 authorization 스키마·material-change 무효·expiry-blocks-transmission 소유; afg `economic_effect_persists`(expiry≠effect) 주입 소비 |
| §8 Cancellation Arbiter Rules | (미소유) sequencing/gate가 소비만 | **protective `cancellation_admissible`**(§11.4 no-optimistic-credit 포함, `predicates.py:523`) | protective arbiter → replacement 주입 소비(§0.2 — 재저작 금지) |
| §5/§9/§16 partition lease | (미소유) partition 처리가 소비만 | **protective `partition_lease_admissible`**(→`Admissibility`, `predicates.py:460`) | protective partition-lease → replacement 주입 소비(§5 line 139 "ADR-002-001 owns this rule"); PR mode→protective action-kind 매핑 |
| §11 FQP + old-order retirement | (미소유) retirement 좌표 소비만 | **afg `cancel_ack_not_final_quantity_proof`**(L1)·**brokercap `fqp_adequate`**·orthostate CANCELLED+later-fill | afg cancel-ACK≠FQP L1 + brokercap FQP + orthostate 좌표 → replacement 주입 소비(§4.6 3-ADR 판정); PR-EV-004는 L3+Broker 통합(닫지 않음) |
| §14 missing-ACK/idempotency | (미소유) 좌표 소비만 | **afg `no_blind_retry`**(L1)·**brokercap `same_order_retry_allowed`** | afg missing-ACK L1 + brokercap idempotency → replacement 주입 소비(PR-EV-003, +Broker) |
| §10 protection sufficiency | (미소유) sequencing이 소비만 | **protective `protective_classification`**·brokercap field-level proof | protective classification + brokercap field-proof → replacement 주입 소비(PR-EV-006, +Broker) |
| §13 broker-resource exhaustion | (미소유) 소비만 | **protective `retry_admissible`/`protective_capacity_exhausted`**·brokercap `rate_admission_ok` | protective retry/exhaustion + brokercap rate → replacement 주입 소비(PR-EV-007, L3/5) |
| §6.1 atomic-replace scope | (미소유) mode 소비만 | **brokercap "5 replace/amend semantics"**(`vocabulary.py:203`, ADR-002-004 §8.8) | brokercap capability profile → replacement 주입 소비(PR-EV-012, L3/5) |
| §8 HALT precedence | (미소유) 소비만 | **authority `AuthorityState.HALTED`·`PRECEDENCE_RANK`·`restrictive_dominates`** | authority HALT precedence → replacement 주입 소비(PR-EV-011); "necessary existing protection not blindly cancelled"(§8 line 225)은 protective arbiter |
| §16 crash/recovery | (미소유) workflow 상태만 | **recon `ConservativeBound`**·rcl recovery·fence(런타임) | recon/rcl → replacement 주입 소비(PR-EV-009); `RECOVERY_REQUIRED` workflow label 소유·barrier enforce는 런타임 |
| §5 workflow lifecycle | `ReplacementWorkflowState`·no-collapse·label-grants-nothing(§4.4·§5.3) | orthostate order/attempt/knowledge(별개 축)·rcl capacity state | replacement가 workflow-coordination 축 소유; order/attempt/capacity는 주입 좌표(§2.2-5 비붕괴) |
| §17 failure containment | `ReplacementOutcome.REPLACEMENT_CONTAINED` 판정 | authority/egress/rcl containment 실행(런타임) | replacement가 containment **판정**; enforce는 런타임 |
| §18 evidence | frozen digest-bound 레코드 재구성(§5.4) | ADR-002-016 replay ENGINE(런타임) | replacement 레코드; replay engine 런타임(Evidence Is Not Authority §5 line 137·§18 line 410) |

> **핵심 소유권 판정 3건(사전 브리핑 응답)**:
> 1. **protective ↔ replacement 분할**: protective가 Cancellation Arbiter(`cancellation_admissible`)·partition-lease
>    (`partition_lease_admissible`)·classification·bounded-retry를 소유하고, replacement는 그 위에 **일반(비-partition)
>    replacement 워크플로**(mode 선택·overlap-first reservation 완전성·cancel-first 8조건 gate·gap/overlap 상태·
>    partial-fill re-eval·FQP-gated retirement)를 소유한다. **분할 축 = 컨텍스트**: protective = degraded/partition
>    경로(bounded pre-proven lease), replacement = normal 워크플로. replacement §5 line 139가 partition-time
>    admissibility를 protective(ADR-002-001)로 **명시 이연**하고 protective §3.5(설계 #11 line 726)가 gap/overlap/
>    non-atomic replacement를 replacement(ADR-002-011)로 **명시 이연** — 상호 명시 경계로 중복 0.
> 2. **cancel-ACK≠FQP 3-ADR 좌표(§4.6 상술)**: 같은 금지 규칙이 3 ADR에 나타난다 — (a) **afg 소유 L1 술어**
>    `cancel_ack_not_final_quantity_proof`(AFG-EV-004 `EV-L1/3+Broker` core L1); (b) **protective 소유 arbiter 적용**
>    `cancellation_admissible`의 `equivalent_replacement_live` no-optimistic-credit(§11.4 line 506); (c) **PR-EV-004
>    = L3+Broker 통합 좌표**(broker가 cancel ACK 후 late fill 실증) — L1 슬라이스 부재·본 Phase-1 미저작·afg+brokercap
>    (`fqp_adequate`)+orthostate(CANCELLED+later-fill) 주입 소비. **replacement는 cancel-ACK≠FQP L1을 재저작하지
>    않는다.**
> 3. **overlap-first 이중 계상(§0.4d 상술)**: replacement가 9-outcome completeness+no-netting을 소유하고, rcl이
>    `aggregate_usage` 합산(이중 계상=보수적)·hard-envelope 강제, are가 aggregate-risk 투영을 소유한다. 중복 아님 —
>    다른 좌표축(§2.2-5).

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **앵커는 PR-EV-001..012·PR-AC-001..012
(§19)·§-clause·SAFE-###(§22)**이며 **새 시리즈를 창작하지 않는다**(§0.4f). **fail-closed discipline**: 미포함/미증명/
netting/None/stale/expired/label에 대한 술어는 절대 vacuous permissive가 되지 않으며, ADMISSIBLE/complete는 *양성
conjunction identity 증명*을 요구하고(잔여 fall-through 금지 — #16 CRITICAL), 각 가드에 **both-ways canary**(가드가
실제로 발화함 ∧ 정당한 통과를 막지 않음)를 붙인다.

### 4.1 overlap-first reservation completeness + no-netting + sequencing 중앙 불변식 (ADR §6.2·§9; PR-EV-001; PR-AC-001)

**중앙 결정**: overlap-first는 old·new 동시 커버를 요구하며(§6.2 line 157 "Before transmission it requires capacity
for the worst credible simultaneous executions and broker resources for both orders"), old는 new sufficiency proof가
current이고 arbiter가 removal 안전을 판정할 때까지 취소 불가다(§6.2 line 159). 실현(구조적):

1. **`overlap_first_reservation_complete`에 permissive 기본값 부재**: 오직 9종 `CredibleIntermediateOutcomeKind`
   (§2.2-3, §9 line 234–243)가 전부 reservation에 포함(`required ⊆ reserved`)되고 **구조적 no-netting 파생 성립**
   일 때만 `True`. 하나라도 누락 ⇒ **incomplete·`False`**(§9 line 231 "an outcome not bounded by these is treated
   conservatively as UNKNOWN"). "assume-covered" 생성자·기본 True 경로 부재.
2. **구조적 no-netting(§0.4d·§20.2 line 443·v1.1 C1/M6 처방(b))**: **flag 극성이 아니라 magnitude 병존 파생**이다.
   `netting_absent`는 `OverlapReservationClaim.magnitudes`의 **`old_order_remaining`·`new_order_remaining`·
   `simultaneous_fills`가 셋 다 present(not None)·비음수**일 때만 True — netting을 적용하면 둘 중 하나가 소거/감액
   되므로 셋의 별개 비음수 병존이 no-netting을 **구조적으로 증명**한다(caller가 flag 위조 불가). 하나라도 None/음수
   ⇒ `False`(가드 발화; **`is not True` 사용 금지 — v1.0 injected-flag의 fail-open을 §0.4d에서 제거**).
3. **reversal-bounded(§6.2·PR-AC-001 "prevents unbounded reversal")**: 이중 계상된 reservation이 hard envelope
   이하 — **rcl `aggregate_usage ≤ effective_limit`(주입 verdict `within_hard_envelope: bool|None`)**. PR은 산술을
   하지 않고 verdict를 소비(§0.4c; `within_hard_envelope is True`만 통과·None⇒UNKNOWN — 양극성 `is True`).
4. **sequencing(§6.2 line 159·v1.1 C2 3-입력 분리·M1 leg-slot)**: `overlap_first_sequencing_valid`는 **(i) new
   Protection Sufficiency Proof current**(`new_protection_sufficiency_current is True` — §10 per-field, evidence/
   brokercap 주입, PR-EV-006 좌표·§1:34 "ACK alone ≠ effective") ∧ **(ii) protective classification present**
   (`protective_classification_present is True` — aggregate-risk 축, 별개) ∧ **(iii) Cancellation Arbiter가 removal이
   required protection을 줄이지 않음 판정**(`cancellation_admissible is True`) ∧ **(iv) leg admissibility current**
   (`leg_admissibility is True` — §5:139 (B) -019, VTG 주입)일 때만 old 취소 허용. **넷 다 `is True`(양극성)** — 어느
   하나라도 `is not True` ⇒ old 취소 불가(`False`). (v1.0은 (i)을 (ii)로 오조달 — C2 정정: classification[aggregate-
   risk] ≠ sufficiency[per-field].)

**canary(both-ways, PR-AC-001)**: (a) 9-outcome 중 하나 누락, 또는 old/new/simultaneous magnitude 중 None/음수(netting
의심), 또는 `within_hard_envelope is not True`, 또는 4-입력 sequencing 중 하나라도 `is not True`인데 old 취소 시도 ⇒
`False`(가드 발화); 빈 outcome set ⇒ `REPLACEMENT_UNKNOWN`(§4.7); leg admissibility 부재 ⇒ `REPLACEMENT_TRAPPED`;
(b) 9-outcome 전부 포함 + old/new/simultaneous 비음수 병존 + `within_hard_envelope is True` + 4-입력 전부 `is True`
⇒ `True`(양성 side — 정당한 overlap-first를 막지 않음). [SAFE-002·SAFE-004·SAFE-013 hard envelope·gap/overlap
aggregate risk]

### 4.2 partial-fill re-evaluation completeness + no-hiding-clamp 중앙 불변식 (ADR §12; PR-EV-005; PR-AC-005)

- **6-target 완전성**(§12 line 292–298): `partial_fill_reevaluation_complete(fill_event, reevaluated_targets:
  frozenset[ReevaluationTargetKind], inputs) -> bool`는 6종 `ReevaluationTargetKind`(§2.2-4)가 전부 재평가될 때만
  `True`. 하나라도 누락 ⇒ `False`(stale quantity calc 잔존). §12 line 291 "Every fill or recognized exposure change
  ... triggers atomic re-evaluation" — 원자적 전부.
- **no-hiding-clamp**(§12 line 302): `no_hiding_clamp(quantity, clamp_applied, hides_uncovered_or_reversing:
  bool|None) -> bool`는 rounding/clamp가 uncovered/reversing quantity를 은닉하지 않을 때만 `True`. lot-size/fractional/
  multiplier/instrument 제약은 explicit conservative treatment(§12 line 302). `hides_uncovered_or_reversing is not
  False` ⇒ `False`.
- **risk-increasing ⇒ deny/contain(§12 line 300·v1.1 C1 음극성)**: `partial_fill_egress_disposition(*,
  became_risk_increasing: bool|None, already_transmitted: bool|None) -> ReplacementOutcome`. `became_risk_increasing`
  은 **음극성 bool|None(안전값=False)** — `became_risk_increasing is not False`(None 또는 True) ⇒ 보수적 deny/
  contain(None을 risk-increasing으로 취급; `is not True` 사용 금지). risk-increasing ∧ not-transmitted ⇒
  `REPLACEMENT_DENIED`, risk-increasing ∧ transmitted ⇒ `REPLACEMENT_CONTAINED`, `became_risk_increasing is False`
  ⇒ 양성 identity(진행 가능).
- **canary(both-ways, PR-AC-005)**: (a) 6-target 중 하나 미재평가, 또는 `hides_uncovered_or_reversing is not False`
  (clamp 은닉/미상), 또는 `became_risk_increasing is not False` ⇒ `False`/deny(가드 발화); 빈 target set ⇒
  restrictive(§4.7); (b) 6-target 전부 재평가 + `hides_uncovered_or_reversing is False` + `became_risk_increasing is
  False` ⇒ `True`. [SAFE-023·SAFE-025 partial fills·asynchronous outcomes]

### 4.3 cancel-first admission gate 불변식 (ADR §6.3; PR-EV-002 predicate-only)

`cancel_first_admission_gate(...) -> bool`는 **8 전제조건(§6.3 line 166–174 verbatim)이 전부 양성**일 때만 `True`;
하나라도 unknown ⇒ `False`(§6.3 line 176 "If any condition is unknown, cancel-first replacement is denied"):

1. no safer proven replacement mode available(§6.3 line 167);
2. active Safety Profile explicitly permits the mode for the scope(line 168);
3. gap's worst credible exposure within aggregate hard envelope(line 169);
4. capacity for unprotected risk, late old-order fills, and new order committed in advance(line 170);
5. approved maximum gap bound and containment action exist(line 171);
6. necessary broker session/route/rate-limit/order capacity positively available or conservatively accounted(line 172);
7. current time basis trustworthy(line 173);
8. action has current Safety Authority and final egress approval(line 174).

protective `cancellation_admissible`(order 취소 가능성)·brokercap resource·time-trust는 **주입 소비**; replacement는
8 replacement-mode 조건을 conjunction으로 판정(arbiter 재저작 아님 §3.5). **추가 leg-slot(v1.1 M1-②)**: cancel-first는
**cancellation-involving leg**이므로 §5:139 (B)에 따라 `leg_admissibility is True`(current exact -019 admissibility)를
**9번째 conjunct**로 요구 — `leg_admissibility is not True` ⇒ `REPLACEMENT_TRAPPED`(§2.2·§5:139 "a cancellation-
involving replacement leg outside that scope ... SHALL NOT proceed"). **canary(both-ways, PR-AC-002)**: (a) 8조건
중 하나라도 unknown/False, 또는 `leg_admissibility is not True` ⇒ `False`/trapped(가드 발화; 특히 no-safer-mode
미확인·gap bound 미승인·time 미신뢰·leg admissibility 미current); 빈 조건 set ⇒ restrictive(§4.7); (b) 8조건 전부
양성 + `leg_admissibility is True` ⇒ `True`. **최소 `EV-L2/3` — 닫지 않음.** [SAFE-011·SAFE-040·SAFE-043 exit
unavailability]

### 4.4 representation ≠ enforcement / workflow-label-grants-nothing (ADR §1 line 21·§5 line 137·§17; core substrate)

`ReplacementWorkflowState`·`ReplacementOutcome`·completeness/gate bool은 **비전송·비-enforcing representation**이다 —
어떤 워크플로 label(`COMPLETED` 포함)도 capacity를 release하거나 protection을 제거하거나 order를 전송하지 않는다.
§5 line 137 verbatim "No lifecycle label by itself authorizes capacity release or removal of protection"·line 139
"No lifecycle label or 'protective' classification proves that cancel, amend, replace, reduce-only, or new
protection is executable"·§9 line 245 "Workflow completion, timeout, authority expiry, cancel ACK, or local
terminal state is insufficient [to reduce capacity]." ⇒ replacement에 **egress transmit·capacity mutate·capability
issue·arbiter override·live-scope set 메서드가 부재**(구성적 부재). `ReplacementAuthorityEffect` all-false가 타입
수준으로 봉인(§5.3). **orthogonality(§5 line 107)**: workflow record는 order/transmission/knowledge/capacity/
protection 상태를 **하나의 enum으로 붕괴하지 않고** 별개 필드로 보존.

### 4.5 방향 극성 검산 — overlap-first ↔ cancel-first 진리표 (ADR §6.2/§6.3; #16 C1 방향-반전 교훈 선제 봉합)

**overlap-first(new→old)와 cancel-first(old→new)는 반대 방향 규칙**이므로 진리표로 검산한다(#16이 §1:25 smallest
vs §10:276 largest를 혼동한 CRITICAL 교훈 — 동일 ADR 내 유사 문구 이형 규칙 병존 시 방향 검산 필수):

| 축 | `OVERLAP_FIRST`(§6.2) | `CANCEL_FIRST`(§6.3) |
|---|---|---|
| 순서 | new 확립 **먼저** → old 제거 나중 | old 제거 **먼저** → new 확립 나중 |
| Protection Gap | **없음**(old이 new 확립까지 유지) | **생성**(§6.3 line 165 "This mode creates or may create a Protection Gap") |
| Protection Overlap | **있음**(old+new 동시 live, §4.5) | 없음 |
| worst credible state | 둘 다 체결 ⇒ over-close/reversal(§20.2) | gap 중 exposure 이동 + late old fill(§9) |
| **reserve 대상**(§9 line 233 "SHALL include **at least** [9종]" — **mode-무관 9종 공통 필수집합**, v1.1 M2) | **9종 공통** + overlap-first **강조분**: `SIMULTANEOUS_OLD_AND_NEW_FILLS`·`OVER_CLOSE_AND_REVERSAL`(둘 다 live) | **9종 공통** + cancel-first **강조분**: `CURRENT_EXPOSURE_UNPROTECTED`(gap)·late-old-fill(§6.3 line 170 "capacity for unprotected risk, late old-order fills, and the new order") |
| 선호도 | **preferred**(§6.2 line 157 "preferred when it can keep every intermediate state within the aggregate hard envelope") | **fallback**(§6.3 line 165 "MAY be authorized only when all of the following hold" — 8조건) |
| 실패 시 기본 | intermediate가 envelope 초과 ⇒ cancel-first 또는 `NO_SAFE_MODE` | 8조건 중 하나 unknown ⇒ **denied**(§6.3 line 176) |

**검산 규칙**: overlap-first의 "old not cancelled until new proven"(§6.2 line 159)과 cancel-first의 "old removed
before new"(§6.3 line 163 "The old protection is removed before the new protection is established")는 **정확히
반대 sequencing**이다 — `overlap_first_sequencing_valid`(new-first)와
`cancel_first_admission_gate`(old-first)를 혼동하면 fail-open이다. `NO_SAFE_MODE`(§6.4)는 둘 다 unsafe일 때의 보수적
기본이며 `BROKER_PROVEN_ATOMIC`(§6.1)은 broker capability 증거가 있을 때만(brokercap 주입). **mode 선택 술어
`replacement_mode_admissible`은 각 mode의 방향-특정 전제를 별도 conjunction으로 검사**(fall-through로 mode 승격 금지).

### 4.6 cancel-ACK ≠ FQP (ADR §11·§1 line 32; 3-ADR 좌표 — 소비, 재저작 금지)

**중앙 판정(사전 브리핑 응답 — ADR 원문 대조)**: "cancel ACK is not Final Quantity Proof"는 §1 line 32("A cancel
request, cancel ACK, timeout, missing query result, or lease expiry is not Final Quantity Proof")·§4.6 line 101
("Cancel ACK alone is not Final Quantity Proof")·§11 line 273("The old order remains in the worst-case executable
set until Final Quantity Proof establishes its remaining economic possibilities")에 규정된 **금지 규칙**이다. 이는
**3 ADR에 같은 규칙, 다른 EV 좌표**로 나타난다:

- **afg(ADR-002-022 §15) = L1-decidable 술어 소유**: `cancel_ack_not_final_quantity_proof`(`predicates.py:794`,
  **AFG-EV-004 `EV-L1/3+Broker` core L1·AFG-INV-009** 앵커). 순수 boolean "cancel ACK가 capacity release·replacement
  reuse·retry를 정당화 못 함." **상호 이연 실측(v1.1 m4)**: ADR-002-022 line 358 verbatim "A cancel acknowledgement
  is not Final Quantity Proof. The original order and any replacement remain covered for worst credible overlap,
  late fill, reversal, and protection gap **under ADR-002-002 and ADR-002-011**" — afg가 본 ADR-002-011로 명시
  상호 이연(중복 아님·좌표 분담).
- **protective(ADR-002-001 §11.4) = arbiter 적용 소유**: `cancellation_admissible`의 `equivalent_replacement_live`
  no-optimistic-credit(`predicates.py:523`, "a submitted/transmitted/acknowledged replacement gets **no** optimistic
  protection credit §11.4 line 506").
- **PR(ADR-002-011 §11) = L3+Broker 통합 좌표**: PR-EV-004 `EV-L3+Broker`(**L1 슬라이스 부재**) — broker가 cancel
  ACK 후 late fill을 보내는 실증(§11 line 277 "fills received before, during, and after cancellation")은 L1-decidable이
  아니라 broker 통합이다. ⇒ **본 Phase-1은 PR-EV-004의 L1 술어를 저작하지 않고** afg `cancel_ack_not_final_quantity_
  proof`(L1) + brokercap `fqp_adequate`(`predicates.py:595`) + orthostate `BrokerOrderState.CANCELLED`+later-fill
  (`vocabulary.py:103–104`) 좌표를 **주입 소비**한다(§3.5·§4.6 seam). old-order retirement(§11 line 273–285)의 완전성
  (7종 fill/query/session/adjustment 고려 §11 line 276–283)은 recon/brokercap 런타임(PR-EV-004/009 통합·닫지 않음).

**replacement는 cancel-ACK≠FQP L1을 재저작하지 않는다**(권위 중복 배제 §0.2). FQP 자체는 ADR-002-004/006(brokercap/
evidence) 소유(§4.6 line 99). [SAFE-022·SAFE-023 reconciliation·asynchronous]

### 4.6a new-protection-sufficiency established — ACK ≠ effective protection (ADR §1 line 34·§10 line 267; v1.1 C2-③/G1)

**중앙 판정(v1.1 C2/G1 신규 불변식)**: ADR §1 line 34 verbatim "A new protective order does not count as effective
protection merely because a request was emitted or transport ACK was received. Its **identity, quantity, side,
price or trigger semantics, remaining quantity, venue state, broker capability, and relation to current exposure**
SHALL be positively established within approved freshness and confidence bounds." (**8 필드 — 항목 수 대조 = 8**).
overlap-first sequencing(§4.1·§5.1)의 `new_protection_sufficiency_current` 슬롯은 **이 규칙의 fail-closed 게이트**다:

- **ACK/emit ≠ sufficiency**: request emitted·transport ACK received 만으로 `new_protection_sufficiency_current`을
  `True`로 두는 경로 **구조적 부재** — 8 필드 positive establishment(§10 line 254–263 per-field, ADR-002-006
  evidence + brokercap `broker_capability_sufficient` 주입)가 있을 때만 `True`(§4.1 (i)).
- **no-inertia(§10 line 267)**: "If the proof becomes stale, contradicted, or insufficient, the protection state
  becomes `UNKNOWN` or gap-exposed ... It does not remain sufficient by inertia." ⇒ stale/contradicted ⇒
  `new_protection_sufficiency_current is not True` ⇒ sequencing 차단(old 취소 불가).
- **classification과 분리(C2)**: `new_protection_sufficiency_current`(§10 per-field 축)은 `protective_classification_
  present`(aggregate-risk 축, §4.1 (ii))과 **별개 conjunct**다 — v1.0이 후자로 전자를 오조달한 category error를 봉합.
- **canary(both-ways)**: (a) ACK-만·field-proof 미확립·stale-by-inertia로 sufficiency 주장 ⇒ old 취소 불가(가드
  발화); (b) 8 필드 positive + not-stale ⇒ `new_protection_sufficiency_current is True`(양성 side). **PR-EV-006 좌표·
  최소 `EV-L3+Broker`(field-proof broker 통합) — 닫지 않음.** [SAFE-021·SAFE-023 evidence·reconciliation]

### 4.7 ∅-공허 fail-closed (양방향 명시 — #10/#11/#16 code-review MAJOR 교훈)

빈 입력의 **모든 방향**을 명문화한다(#12 교훈: 표의 방향이 하나뿐이면 불변식의 전 금지 동사와 대조해 커버리지
명시). PR 금지 동사(**ADR 전 조항 스윕 §1–§20, v1.1 M5/G4 확장**): **net-old-against-new**(§0.4d·§20.2)·**cancel-
old-before-new-proven**(§6.2 line 159)·**cancel-first-without-8-conditions**(§6.3 line 176)·**proceed-leg-without-
current-admissibility**(§5 line 139 (B) — v1.1 M1)·**clamp-hiding-quantity**(§12 line 302)·**treat-cancel-ACK-as-FQP**
(§1 line 32)·**treat-ACK-as-effective-protection**(§1 line 34 — v1.1 C2)·**reduce-capacity-on-label**(§9 line 245)·
**optimistic-credit-on-submitted-replacement**(§11.4 line 506)·**expire-economic-effect-on-authorization-expiry**
(§7 line 203)·**assume-atomic-by-method-name**(§6.1 line 149)·**blind-cancel-on-resource-unavailability**(§13 line
320)·**priority-as-reserved-capacity**(§9 line 247·§20.5 — v1.1 m6)·**extend-authority-on-bound-exceed**·**widen-
capacity-on-bound-exceed**·**declare-complete-on-bound-exceed**(§15 line 351 3 SHALL NOT — v1.1 M5)·**clear-workflow-
and-restart**(§20.7 line 463).

| 빈 입력 | 금지 방향(vacuous permissive 차단) | 허용 방향(양성 side) | 근거 |
|---|---|---|---|
| **빈 outcome set** | 평가 outcome 부재 ⇒ "no risk" 아님 ⇒ completeness 증명 불가 ⇒ `REPLACEMENT_UNKNOWN`(conservative) | 9종 credible outcome 전부 포함 + no-netting ⇒ 평가 가능 | §9 line 231·234–243; PR-AC-001 |
| **빈 reevaluation-target set** | 재평가 target 부재 ⇒ "no change" 아님 ⇒ stale calc 잔존 ⇒ incomplete `False` | 6종 target 전부 재평가 ⇒ 평가 가능 | §12 line 292–298; PR-AC-005 |
| **빈 cancel-first 조건 set** | 조건 부재 ⇒ 공허 admissible 금지 ⇒ `False`(denied) | 8조건 전부 양성 ⇒ 통과 | §6.3 line 176 |
| **old/new/simultaneous magnitude 중 None/음수**(구조적 no-netting, C1/M6) | 셋 중 하나라도 None/음수 ⇒ netting 의심·미증명 ⇒ `False`(**flag `is not True` 아니라 magnitude 병존 파생**) | old·new·simultaneous 셋 다 present·비음수 ⇒ 구조적 no-netting ⇒ 통과 | §0.4d; §4.1 (2) |
| **None magnitude/limit/risk** | None ⇒ `REPLACEMENT_UNKNOWN`/`DENY`(rcl `aggregate_usage` None⇒None) | finite magnitude + finite limit ⇒ 비교 가능 | §9; §4.1 |
| **new_protection_sufficiency_current=None**(§10 field-proof, C2-④) | None/미확립 ⇒ old 취소 불가(**양극성 `is True`만**; ACK/emit·stale-inertia ≠ sufficiency) | 8 필드 positive establishment + not-stale ⇒ `is True` ⇒ 통과 | §1 line 34·§10 line 267; §4.1 (i)·§4.6a |
| **protective_classification_present=None**(aggregate-risk, C2-④) | None ⇒ old 취소 불가(양극성 `is True`만; 별개 축) | PROTECTIVE_PROVEN ⇒ `is True` ⇒ 통과 | §4.1 (ii); §6.2 line 159 |
| **cancellation_admissible=None**(arbiter, C2-④) | None ⇒ old 취소 불가(양극성 `is True`만) | arbiter 승인 ⇒ `is True` ⇒ 통과 | §4.1 (iii); §8 |
| **leg_admissibility=None**(-019, M1) | None/미current ⇒ leg proceed 불가 ⇒ `REPLACEMENT_TRAPPED`(양극성 `is True`만) | current exact -019 admissibility ⇒ `is True` ⇒ leg 통과 | §5 line 139 (B); §4.1 (iv)·§4.3 |
| **bound_exceeded**(§15 line 351, M5) | bound 초과 ⇒ `REPLACEMENT_CONTAINED`(authority 확장·capacity widen·complete 선언 금지) | bound 내 ⇒ 통과 | §15 line 351 |
| **빈 Admissibility**(partition) | protective `partition_lease_admissible` None/TRAPPED/PROHIBITED ⇒ deny(`is Admissibility.ADMISSIBLE`만 통과) | ADMISSIBLE ⇒ overlap-first/add-only 허용 | §5 line 139; §3.4 |
| **빈 workflow state** | 상태 부재 ⇒ label-grants-nothing ⇒ 어떤 authority도 없음 | (양성 side 없음 — label은 결코 authority 부여 안 함) | §5 line 137 |

**양방향 규율**: 각 빈-입력 가드는 (a) 금지 방향(가드 발화 canary)과 (b) 허용 방향(정당 통과 canary)을 **둘 다**
property로 검증한다(§7). vacuous-admissible도 vacuous-block도 결함이다 — 전자는 안전 위반, 후자는 가용성 위반(#12
both-ways 교훈). **동사별 전용 canary**: net-old-against-new(§5.1 구조적 magnitude)·cancel-before-proven(§5.1)·
cancel-first-without-8(§6.1)·**proceed-leg-without-admissibility(§5.1/§6.1/§5.3 leg-slot·M1)**·clamp-hiding(§5.2)·
became-risk-increasing(§5.2 음극성)·cancel-ACK-as-FQP(§4.6 consumed)·**ACK-as-effective-protection(§4.6a·§5.1 (i)·
C2)**·label-authority(§5.3)·optimistic-credit(§5.1 arbiter consumed)·expire-effect(§6.2)·**priority-as-reserved-
capacity(§9:247 consumed·m6)**·**bound-exceed-3-SHALL-NOT(§5.3·§7 M5)**가 각 절에 전용 named canary를 갖는다.

---

## 5. core 술어 — overlap-first · partial-fill · workflow (PR-EV-001/005 substrate + core substrate)

**핵심 난제**: overlap-first replacement의 "원본+대체 동시 커버" 완전성과 partial-fill 재평가 완전성을 **순수
함수**로 저작하되, (i) gap/overlap/aggregate-risk 수치를 **주입 파라미터**로 두어 하드코딩·broker 판정을 배제하고
(§8), (ii) **fail-closed(§4)를 구조로** 지키며(permissive 기본·vacuous 부재·양성 identity 도달), (iii) missing
outcome·netting·cancel-before-proven·clamp-hiding를 **most-restrictive**로 처리한다.

### 5.1 overlap-first reservation completeness + no-netting + sequencing (§6.2/§9; PR-EV-001 substrate, core L1 슬라이스)

`overlap_first_reservation_complete(claim: OverlapReservationClaim|None, required_outcomes: frozenset[Credible
IntermediateOutcomeKind], *, within_hard_envelope: bool|None) -> bool` (**v1.1 M6: `netting_applied` flag 제거 —
no-netting은 `claim.magnitudes`에서 구조적 파생**):

- `True` **only** when claim 존재 ∧ `required_outcomes ⊆ claim.reserved_outcome_kinds`(9종 §9 line 234–243) ∧
  **`netting_absent(claim)`**(아래) ∧ `within_hard_envelope is True`. **양성 conjunction identity 도달**(fall-through
  `return True` 부재 — #16 CRITICAL). 하나라도 미충족 ⇒ `False`.
- **구조적 no-netting 파생**(§0.4d·§20.2 line 443·v1.1 M6 처방(b)): `netting_absent(claim) -> bool`는
  `claim.magnitudes`의 `OLD_ORDER_REMAINING_EXECUTABLE`·`NEW_ORDER_REMAINING_EXECUTABLE`·`SIMULTANEOUS_OLD_AND_NEW_
  FILLS`가 **셋 다 not None·비음수**일 때만 `True` — netting은 old를 new로 상쇄해 둘 중 하나를 소거/감액하므로,
  셋의 별개 비음수 병존이 no-netting을 구조 증명한다(caller flag 위조 불가). 하나라도 None/음수 ⇒ `False`
  (**`is not True` 미사용 — fail-open 제거**).
- **reversal-bounded**(PR-AC-001): `within_hard_envelope`는 rcl `aggregate_usage`(`vector.py:103`)`≤ effective_limit`
  (`vector.py:139`) verdict 주입(**양극성 `is True`만 통과**·None⇒UNKNOWN; §0.4c PR 산술 미소유).
- **빈 required_outcomes canary(§4.7)**: 빈 set ⇒ `REPLACEMENT_UNKNOWN`(§9 line 231; completeness 증명 불가).

`overlap_first_sequencing_valid(*, new_protection_sufficiency_current: bool|None, protective_classification_present:
bool|None, cancellation_admissible: bool|None, leg_admissibility: bool|None) -> bool` (**v1.1 C2 3-입력 분리 +
M1 leg-slot — 4 conjunct**):

- `True` **only** when **(i)** `new_protection_sufficiency_current is True`(§10 per-field Protection Sufficiency
  Proof — evidence/brokercap 주입, PR-EV-006; §1 line 34 "ACK alone ≠ effective protection"·§4.6a) ∧ **(ii)**
  `protective_classification_present is True`(protective aggregate-risk 축 — **별개 축**, `protective/predicates.py:
  309`) ∧ **(iii)** `cancellation_admissible is True`(protective arbiter, `predicates.py:523`) ∧ **(iv)**
  `leg_admissibility is True`(§5 line 139 (B) -019, VTG 주입) — §6.2 line 159 "The old order SHALL NOT be cancelled
  until the new Protection Sufficiency Proof is current and the Cancellation Arbiter determines that removal will
  not reduce required protection." **넷 다 양극성 `is True`** — 어느 하나라도 `is not True` ⇒ old 취소 불가(`False`;
  leg admissibility 부재 시 `REPLACEMENT_TRAPPED`). **v1.1 C2 정정**: v1.0은 (i)을 (ii)로 오조달 — sufficiency(§10
  per-field) ≠ classification(aggregate-risk)이며, ADR §10을 not-Phase-1(PR-EV-006)로 분류한 설계 자체와도 정합.
- **cancel-before-proven 전용 canary(§4.7)**: 4 conjunct 중 하나라도 미current인데 old 취소 시도 ⇒ `False`(가드 발화).
- **canary(both-ways, PR-AC-001)**: (a) outcome 누락·magnitude None/음수·envelope 초과·4-conjunct 중 미proven-old취소
  ⇒ `False`/trapped; 빈 outcome ⇒ UNKNOWN(§4.7); (b) 9-outcome 완비 + 구조적 no-netting + envelope 이하 + 4-conjunct
  전부 `is True` ⇒ `True`(양성 side).

### 5.2 partial-fill re-evaluation completeness + no-hiding-clamp (§12; PR-EV-005 substrate, core L1 슬라이스)

`partial_fill_reevaluation_complete(reevaluated: frozenset[ReevaluationTargetKind], required_targets: frozenset[
ReevaluationTargetKind], *, fill_recognized: bool|None) -> bool`:

- `True` **only** when `fill_recognized is True` ∧ `required_targets ⊆ reevaluated`(6종 §12 line 292–298). §12 line
  291 "Every fill or recognized exposure change ... triggers atomic re-evaluation" — 원자적 전부. 하나라도 미재평가
  ⇒ `False`(stale calc 잔존).
- **no-hiding-clamp**(§12 line 302): `no_hiding_clamp(*, clamp_applied: bool|None, hides_uncovered_or_reversing:
  bool|None) -> bool`는 `hides_uncovered_or_reversing is False`일 때만 `True`(None⇒`False` 보수적). lot-size/
  fractional/multiplier/instrument는 explicit conservative treatment.
- **risk-increasing ⇒ deny/contain**(§12 line 300·v1.1 C1 음극성): `partial_fill_egress_disposition(*, became_risk_
  increasing: bool|None, already_transmitted: bool|None) -> ReplacementOutcome`. `became_risk_increasing`은 **음극성
  bool|None(안전값=False)** — `became_risk_increasing is not False`(None 또는 True; None을 risk-increasing으로 보수
  취급) ∧ not-transmitted ⇒ `REPLACEMENT_DENIED`, `is not False` ∧ transmitted ⇒ `REPLACEMENT_CONTAINED`,
  `became_risk_increasing is False` ⇒ 양성 identity(진행). **`is not True` 미사용**(fail-open 제거).
- **빈 required_targets canary(§4.7)**: 빈 set ⇒ restrictive(재평가 없이 통과 금지).
- **canary(both-ways, PR-AC-005)**: (a) 6-target 중 하나 미재평가·`hides_uncovered_or_reversing is not False`·
  `became_risk_increasing is not False` ⇒ `False`/deny; 빈 target ⇒ restrictive(§4.7); (b) 6-target 완비 +
  `hides_uncovered_or_reversing is False` + `became_risk_increasing is False` ⇒ `True`.

### 5.3 workflow lifecycle + label-grants-nothing + mode admissibility (§5/§6.4; core substrate)

- **`ReplacementAuthorityEffect` all-false**(§5 line 137·§4.4): rcl `AllFalseAuthority` 동형·어떤 True도
  unconstructable + `workflow_label_grants_nothing(effect: ReplacementAuthorityEffect) -> bool`(무조건 True —
  어떤 label도 capacity release·protection removal·transmission 부여 안 함). `ReplacementWorkflowRecord`는
  orthogonal 축을 별개 필드로 보존(no-collapse §5 line 107).
- **`ReplacementWorkflowState` 전이 술어 = NOT Phase-1 판정(v1.1 Q3)**: Phase-1은 `ReplacementWorkflowState`
  **어휘 + label-grants-nothing(all-false) + orthogonality(no-collapse 구조)**만 저작한다. 전이 **유효성**(예:
  `CAPACITY_COMMITTED`→`FIRST_LEG_SENT` 허용 여부)은 rcl capacity commit·orthostate attempt 상태·leg admissibility
  등 **런타임 게이트에 의존**하므로 orthostate `attempt_transition_allowed`가 orthostate 소관인 것과 동형으로 **전이
  술어를 Phase-1에 저작하지 않는다**(런타임 EV-L3). PR은 상태 label을 set하지 않고 completeness/gate bool만 생산.
- **`replacement_mode_admissible` — 완결 signature(v1.1 G5 — `...` 제거)**: `replacement_mode_admissible(mode:
  ReplacementMode, *, atomic_proven: bool|None, overlap_reservation_complete: bool|None, overlap_sequencing_valid:
  bool|None, cancel_first_gate_passed: bool|None, leg_admissibilities: frozenset[bool], bound_exceeded: bool|None)
  -> ReplacementOutcome`. 각 mode의 **방향-특정 전제를 별도 conjunction으로 검사**(§4.5 진리표; fall-through mode
  승격 금지·양성 identity 도달) — `BROKER_PROVEN_ATOMIC`은 `atomic_proven is True`(brokercap 증거) ∧ leg 전부 admissible;
  `OVERLAP_FIRST`은 `overlap_reservation_complete is True` ∧ `overlap_sequencing_valid is True`(§5.1); `CANCEL_FIRST`은
  `cancel_first_gate_passed is True`(§6.1); **mode 합성점 = 전 leg admissibility 양성**(`all(a is True for a in
  leg_admissibilities)` ∧ non-empty; 하나라도 False/빈 집합 ⇒ `REPLACEMENT_TRAPPED`, M1). **`bound_exceeded is True`
  ⇒ `REPLACEMENT_CONTAINED`**(§15 line 351 3 SHALL NOT — authority 확장·capacity widen·complete 선언 금지, M5).
  셋 다 불가 ⇒ `NO_SAFE_MODE` ⇒ `REPLACEMENT_CONTAINED`(§6.4 line 180 "retain or escalate the safest existing
  protection, block new risk, preserve capacity, and enter containment").
- **HALT-blind-cancel 전용 both-ways canary(v1.1 G7 — §8 line 225 PR측)**: HALT 활성 시 `replacement_mode_admissible`은
  ordinary 워크플로 개시를 차단하되(`REPLACEMENT_CONTAINED`), **"a protective order already necessary to contain
  existing exposure SHALL not be blindly cancelled"**(§8 line 225)는 protective `cancellation_admissible` 주입에
  위임 — PR은 HALT 중 blind-cancel을 **생성하지 않음**(canary (a): HALT + necessary-protection에 blind cancel 시도 ⇒
  차단; (b): HALT-compatible 신규 authorized containment는 통과). authority HALT precedence 주입 소비(PR-EV-011).
- **canary(both-ways)**: (a) label로 capacity release 시도·mode fall-through 승격·leg 미admissible·bound 초과·
  no-safe-mode인데 replacement 진행 ⇒ `False`/contain/trapped(가드 발화); (b) 정당 mode 전제 충족 + 전 leg admissible
  + bound 내 ⇒ 해당 mode identity.

### 5.4 evidence 재구성 substrate (§18; PR-EV-001..012 공통)

- **frozen digest-bound 레코드**: `ReplacementAuthorization`·`ReplacementWorkflowRecord`가 각 결정을 durable
  evidence에서 재구성 가능케 함(§18 line 396–406 **10항**: replacement workflow/obligation version·intent/attempt/
  broker-order lineage·arbiter inputs·rcl commitments·capability/session·sufficiency/FQP inputs·gap/overlap start/
  end/bound·fill/exposure re-eval·egress/containment/recovery). **replay ENGINE 자체는 ADR-002-016**(not-Phase-1).
  **Evidence Is Not Authority**(§18 line 410 "Written cases and logs are not completed evidence"·§5 line 137).
  evidence 참조는 scalar(id/gen/digest).
- **§18 line 408 9 metrics 명시 이연(v1.1 G8)**: ADR §18 line 408은 required metrics **9종**을 열거한다 — gap
  duration·overlap duration·unknown-old-order duration·proof staleness·capacity held for replacement·denied unsafe
  cancellations·late fills after cancel ACK·duplicate-attempt containment·shared protective-resource exhaustion.
  이 9 metric의 **측정·집계는 런타임 관측(EV-L2/L3)**이며 Phase-1 밖이다 — PR은 레코드 구조(위 10항)만 저작하고
  metric 산출을 하지 않는다(관측성 ≠ authority §18 line 410).
- **canary**: id⊥digest이므로 same-id/diff-bytes authorization·double-commit workflow ⇒ `classify_record_pair`
  `CRITICAL_CONFLICT`(위조·contradictory authorization·재발행 위조 탐지·양쪽 보존, no last-write-wins).

---

## 6. predicate-only 술어 — cancel-first gate · authorization expiry (+ consumed 좌표) (PR-EV-002/008 substrate + 003/004/006/007/009/010/011/012 consumed, 최소 ≥ L2·닫지 않음)

각각 **L1-decidable substrate**를 저작하거나(002·008) 형제 L1 술어를 **주입 소비**(003·004·006·007·009·010·011·012)
하되 **어떤 PR-EV도 닫지 않는다**(최소 ≥ L2·+Broker/+L3/+L5 잔여).

### 6.1 cancel-first admission gate (§6.3; PR-EV-002 substrate, predicate-only)

`cancel_first_admission_gate(...) -> bool` — §4.3 중앙 불변식. 8 전제(§6.3 line 166–174) 전부 양성 conjunction일
때만 `True`; 하나라도 unknown ⇒ `False`(§6.3 line 176). protective `cancellation_admissible`(order 취소 가능성)·
brokercap resource(`rate_admission_ok`)·time-trust flag 주입 소비. **cancel-first가 gap을 생성**하므로(§4.5) gap
worst exposure ≤ hard envelope(조건 3, 주입) + max gap bound 승인(조건 5, VP-002 `B_protection_gap`) 필수. **∅/None
canary(양방향)**: 8조건 전부 None ⇒ `False`(미증명 ⇒ denied); positive 8-tuple ⇒ 통과. **최소 `EV-L2/3` — 닫지
않음**(component fault·integration 잔여).

### 6.2 replacement-authorization currentness / expiry (§7; PR-EV-008 substrate, predicate-only)

`replacement_authorization_current(*, material_change: bool|None, expired: bool|None, economic_effect_persists:
bool|None) -> bool` ∧ expiry disposition:

- **material change ⇒ 무효**(§7 line 201): `material_change is not False` ⇒ `False`(re-evaluation 필요; invalidating
  changes = exposure/fill/order-state/capability/session/time-health/capacity/profile/epoch/instrument-identity/
  market-state/deployment-generation).
- **expiry는 future transmission만 차단**(§7 line 203 "Authorization expiry blocks further transmission. It does
  not expire the economic effect of an already transmitted old or new order"): `expired is True` ⇒ 신규 전송 차단
  이나 **이미 전송된 old/new의 economic effect는 불변** — afg `economic_effect_persists`(`tos.afg.state:545`) 주입
  소비(§4.6 관련; expiry ≠ effect-expiry). **극성 축 명확화(v1.1 Q2)**: `economic_effect_persists`는 **양극성(안전값
  =True: "effect 지속"이 보수적)** — expiry가 economic effect를 소멸시키지 못함을 **`economic_effect_persists is
  True`로 확인**(None/False ⇒ 보수적으로 effect 지속 가정·release 금지). `no_hiding`류 음극성과 반대 축이다. **expire-
  economic-effect 전용 canary(§4.7)**: expiry로 economic effect 소멸 가정 ⇒ 거부(가드 발화).
- **∅/None canary(양방향)**: material_change/expired/economic_effect None ⇒ 보수적(`False`/effect 지속); 정당한
  current authorization(material_change False·not expired) ⇒ 통과. **최소 `EV-L2/3` — 닫지 않음.**

### 6.3 consumed 좌표 술어 (PR-EV-003/004/006/007/009/010/011/012 — not-Phase-1, 형제 L1 소비·닫지 않음)

**어떤 L1 술어도 저작하지 않고** 형제 술어/좌표를 주입 소비한다(§3.5). 각각 **최소 ≥ L2** — 닫지 않는다:

- **PR-EV-003 (Missing ACK, §14, `EV-L3+Broker`)**: afg `no_blind_retry`(`predicates.py:713`, L1) + brokercap
  `same_order_retry_allowed`(`predicates.py:377`) 주입 소비. missing ACK ⇒ potentially live(orthostate
  `SENT_UNCONFIRMED` 좌표); replacement retry는 broker idempotency 양성 증명 시에만. **broker 통합은 +Broker 이연.**
- **PR-EV-004 (Cancel ACK≠FQP, §11, `EV-L3+Broker`)**: afg `cancel_ack_not_final_quantity_proof`(`predicates.py:794`,
  L1) + brokercap `fqp_adequate`(`predicates.py:595`) + orthostate `BrokerOrderState.CANCELLED`+later-fill
  (`vocabulary.py:103–104`) 주입 소비(§4.6 3-ADR 판정). **L1 슬라이스 부재 — broker late-fill 실증은 +Broker/L3 이연.**
- **PR-EV-006 (New Protection Sufficiency, §10, `EV-L3+Broker`)**: **evidence(ADR-002-006) per-field proof(§10 line
  254–263 9-field) + brokercap `broker_capability_sufficient`(`predicates.py:206`)** 주입 소비 → `new_protection_
  sufficiency_current`(§4.1 (i)·§4.6a·§5.1 sequencing conjunct). **C2 정정**: protective `protective_classification`
  (`predicates.py:246/309`)은 **aggregate-risk 축(별개)**이며 §10 per-field sufficiency의 조달원이 **아니다** — 둘은
  §5.1 sequencing의 별개 conjunct다. broker ACK alone ≠ sufficiency(§1 line 34·§10 line 265). **field-level broker
  proof는 +Broker 이연.**
- **PR-EV-007 (Broker-Resource Exhaustion, §13, `EV-L3/5`)**: protective `retry_admissible`/`protective_capacity_
  exhausted`(`predicates.py:588/623`) + brokercap `rate_admission_ok`(`predicates.py:437`) 주입 소비. resource
  unavailability ⇒ no blind cancel/unbounded retry(§13 line 320). shared path ⇒ PRIORITIZED_ONLY/BEST_EFFORT(§13
  line 318, protective `GuaranteeLevel`). **common-mode·L5는 이연.**
- **PR-EV-009 (Crash/Failover, §16, `EV-L3`)**: recon `ConservativeBound`(`records.py:28`) + rcl recovery + fence
  주입 소비. **recovery 9-step 전수(§16 line 362–371, v1.1 M3 복원)**: (1)fence stale workflow/ledger writers·(2)block
  new risk·(3)restore committed capacity(no inferred release)·(4)reconcile old/new order id·quantities with broker·
  **(5)reconcile current exposure and recognized non-trade changes**(ADR-002-010 seam — v1.0 누락분 복원)·(6)classify
  unresolved UNKNOWN·capacity-consuming·(7)reassess protection sufficiency·gap/overlap risk·(8)obtain new authority·
  (9)require governed re-arm — 전부 recon/rcl/liveauth 런타임. `RECOVERY_REQUIRED` workflow label만 소유. **barrier
  enforce는 런타임 L3.**
- **PR-EV-010 (Partition, §5 line 139/§16, `EV-L3`)**: protective `partition_lease_admissible`(`predicates.py:460`,
  →`Admissibility`) 주입 소비. §5 line 139 "ADR-002-001 ... owns this rule"; partition 중 overlap-first/add-only만
  scope 내 허용, cancel-first는 scope 밖·staleness 초과 ⇒ 금지(TRAPPED). **`verdict is Admissibility.ADMISSIBLE`로만
  통과.** **quorum/fence enforce는 런타임 L3.**
- **PR-EV-011 (HALT Precedence, §8, `EV-L3`)**: authority `AuthorityState.HALTED`·`PRECEDENCE_RANK`·`restrictive_
  dominates` 주입 소비. §8 line 225 "HALT dominates ordinary replacement initiation. Only a HALT-compatible
  protective or containment workflow ... MAY proceed. A protective order already necessary to contain existing
  exposure SHALL not be blindly cancelled" — 후자는 protective arbiter(`cancellation_admissible`) 소유. **precedence
  enforce는 authority 런타임 L3.**
- **PR-EV-012 (Atomic Replace Scope, §6.1, `EV-L3/5`)**: brokercap "5 replace/amend semantics"(`vocabulary.py:203`,
  ADR-002-004 §8.8) 주입 소비. atomic은 profile이 exact semantics를 executed evidence로 증명할 때만(§6.1 line 147);
  method name·happy-path ≠ 증명(§6.1 line 149); 미증명 ⇒ non-atomic(§6.1 line 151). **broker sandbox 증거는 +Broker/
  L5 이연.**

**규율 태그**: 위 8종은 전부 **형제 소유 L1을 소비**하거나 **런타임 L3**이며 replacement가 L1 술어를 저작하지 않는다
(권위 중복 배제 §0.2·§3.5). **어떤 PR-EV도 닫지 않는다.**

---

## 7. property-test 하네스 타깃

§1 분류에 정렬한다. **닫는 PR-EV = 0건** — 어떤 test-target도 PR-EV closure·acceptance를 주장하지 않는다(규율 태그
부착). 각 술어에 **both-ways canary**(§4·§5·§6)와 **fixture clean-vs-illegal 정합**(#8 교훈)을 건다. **hypothesis
전략은 forgery/∅ 케이스를 명시 포함**한다(아래).

- **core(L1 슬라이스, PR-EV-001/005 substrate)**: `overlap_first_reservation_complete`+`overlap_first_sequencing_
  valid`(§5.1); `partial_fill_reevaluation_complete`+`no_hiding_clamp`+`partial_fill_egress_disposition`(§5.2);
  `replacement_mode_admissible`+`workflow_label_grants_nothing`(§5.3); frozen digest-bound 레코드 재구성·
  `classify_record_pair` CRITICAL_CONFLICT(§5.4).
  **hypothesis property**: `OverlapReservationClaim`(per-outcome magnitude 포함)/`ReplacementWorkflowRecord`/outcome-
  set/target-set/mode를 무작위 생성해 (i) **completeness**(required 9-outcome/6-target 부분집합 관계·미포함⇒False),
  (ii) **구조적 no-netting**(v1.1 M6 — `old_order_remaining`·`new_order_remaining`·`simultaneous_fills` magnitude를
  None/음수/비음수 조합 생성; 셋 다 not-None·비음수일 때만 `netting_absent`; 하나라도 None/음수⇒False), (iii)
  **sequencing 4-입력 polarity**(v1.1 C2/M1 — `new_protection_sufficiency_current`×`protective_classification_present`
  ×`cancellation_admissible`×`leg_admissibility` 2⁴ 진리표; 넷 다 `is True`만 통과), (iv) **방향 극성**(overlap-first
  vs cancel-first mode가 §4.5 진리표대로 별도 전제 요구·fall-through 승격 시 실패), (v) **reversal-bounded**
  (`within_hard_envelope` None⇒UNKNOWN·`is True`만), (vi) **label-grants-nothing**(모든 workflow state에서 authority
  effect all-false), (vii) **leg-admissibility 합성**(`leg_admissibilities` 빈 집합/일부 False⇒`REPLACEMENT_TRAPPED`),
  (viii) **bound-exceed**(`bound_exceeded is True`⇒`REPLACEMENT_CONTAINED`)를 검사.
  - **forgery 케이스(명시)**: same-id/diff-canonical-digest `ReplacementAuthorization`·`ReplacementWorkflowRecord`
    쌍 생성 ⇒ `classify_record_pair` `CRITICAL_CONFLICT` 회귀(위조·contradictory authorization·double-commit
    workflow·양쪽 보존·no last-write-wins).
  - **∅ 케이스(명시, §4.7 표와 1:1)**: 빈 outcome set⇒`REPLACEMENT_UNKNOWN`; 빈 target set⇒restrictive; 빈
    cancel-first 조건⇒`False`; old/new/simultaneous magnitude None/음수⇒`False`(구조적 no-netting); None magnitude/
    limit⇒UNKNOWN/DENY; `new_protection_sufficiency_current`/`protective_classification_present`/`cancellation_
    admissible` None⇒old취소불가; `leg_admissibility` None⇒`REPLACEMENT_TRAPPED`; `bound_exceeded`⇒CONTAINED;
    None/TRAPPED/PROHIBITED Admissibility⇒deny; 빈 workflow state⇒label-grants-nothing.
  - **truthy-sentinel property(양축·극성 분기 v1.1 C1)**: `ReplacementOutcome` 게이트 `is REPLACEMENT_ADMISSIBLE`만·
    protective `Admissibility` 게이트 `is ADMISSIBLE`만 통과(DENY/UNKNOWN·TRAPPED/PROHIBITED/None 관통 시 실패);
    **양극성 필드(`within_hard_envelope`·`new_protection_sufficiency_current`·`cancellation_admissible`·`leg_
    admissibility`)는 `is True`만·None으로 관통 시 실패; 음극성 필드(`hides_uncovered_or_reversing`·`material_change`·
    `became_risk_increasing`)는 `is False`만·None으로 관통 시 실패**(음극성에 `is not True` 사용 시 회귀 실패).
  - **좌표 비붕괴 property(§2.2-5)**: `ReplacementMode` 값 ∩ protective `ProtectiveActionKind` 값·`CredibleIntermediate
    OutcomeKind` ∩ rcl `CapacityState`·are `RiskDimensionKind`가 별개 타입임(토큰 겹침 무관) 회귀.
- **predicate-only(PR-EV-002/008 substrate, EV 미주장)**: `cancel_first_admission_gate`(§6.1, 8조건 전수 None⇒False);
  `replacement_authorization_current`(§6.2, material-change/expiry/economic-effect polarity).
- **consumed 좌표(PR-EV-003/004/006/007/009/010/011/012, EV 미주장·seam test로만)**: 형제 술어 주입 소비 polarity만
  검증(§6.3) — 형제 L1을 재검증하지 않는다(권위 중복 배제).
- **seam cross-check(test-only, MANDATED §3.4)**: `test_seam_protective`(replacement sequencing ↔ `cancellation_
  admissible` **양극성 `is True`만·None⇒not admissible**·classification ↔ `protective_classification_present`
  **aggregate-risk 축·`is True`만**·partition ↔ `partition_lease_admissible` **3값+None 전수 — `is ADMISSIBLE`만
  통과**·**HALT both-ways(G7): HALT+necessary-protection blind-cancel 시도 차단 ↔ `cancellation_admissible`**)·
  **`test_seam_evidence`(v1.1 C2 — `new_protection_sufficiency_current` ↔ evidence per-field proof·brokercap
  `broker_capability_sufficient`:206 — §10 field-proof, ACK-alone⇒False)**·`test_seam_afg`(PR-EV-004 ↔
  `cancel_ack_not_final_quantity_proof`·PR-EV-003 ↔ `no_blind_retry`·expiry ↔ `economic_effect_persists` **양극성
  `is True`**)·`test_seam_brokercap`(PR-EV-012 ↔ `ReplaceSemantics`(`vocabulary.py:202`, `ATOMIC_REPLACE`)·PR-EV-004
  ↔ `fqp_adequate`·PR-EV-003 ↔ `same_order_retry_allowed`)·**`test_seam_vtg`(v1.1 M1 — **작성됨**(v1.2 에라타):
  `leg_admissibility` ↔ venue `OrderAdmissibilityResult` **4토큰+None 전수 접기 polarity**(`is ADMISSIBLE`만 True·
  `RESTRICTED_PROTECTIVE_ONLY` 직접 접기 False 실증)·`bool(token)` **TypeError 봉인 확인**·venue
  `protective_label_no_bypass` **실구동 조합 경로**(4조건 양성 ⇒ protective-only leg 통과; 1조건 결손 ⇒ trapped)·
  missing/unknown⇒`REPLACEMENT_TRAPPED`)**·`test_seam_orthostate`(PR-EV-004 ↔
  `BrokerOrderState.CANCELLED`+later-fill·PR-EV-003 ↔ `SENT_UNCONFIRMED`)·`test_seam_rcl`(overlap-first headroom ↔
  `aggregate_usage`/`effective_limit` None⇒UNKNOWN·partition ↔ `partition_verdict`). 테스트 import는 package closure
  불계상(§7.1).
- **∅-공허 회귀(양방향, §4.7 표 12행 ↔ 본 §7 목록 1:1)**: 각 빈-입력의 금지 방향 + 완비 입력의 정당 통과 canary
  **둘 다**.

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#5..#16 §7.1 상속)

**allowlist 형식(denylist 열거 금지 — #16 M9 교훈)**: `import` 후 `{m for m in sys.modules if m.startswith("tos.")}`
의 top-level 패키지 ⊆ **{`tos.canonical`, `tos.ordering`, 자기 자신}** assert(그 외 모든 tos 형제 — protective/rcl/
orthostate/afg/brokercap/authority/recon/are/spg/liveauth/capsule/evidence/dsl/ioc/iap/time 및 미래 형제 — 등장 시
실패) + `shared.config`·`os.environ` 흔적·`numpy`/`pandas`/`yaml` 부재 assert. **allowlist가 미래-견고**(신규 형제
추가에 자동 방어). required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter` layer-②
전이)와 함께 green이어야 §0.3 선언이 능동 성립.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

(1) 목적: replacement Phase-1(EV-L1) 순수 모델+property test. (2) 명령: `pytest tos/tests/replacement/ -v`. (3)
격리: hermetic(`.env` 비주입·clock 미접근·네트워크 없음). (4) 결정론: hypothesis 시드 고정·`CanonicalDecimal` scale-
normalize·NaN/infinity 구성-거부. (5) 산출물: property test 결과(EV closure 아님 — 규율 태그). (6) 게이트:
`tos-firewall` required green. (7) 비-acceptance: 어떤 PR-EV도 닫지 않음(§0.2·VER-002-001 §5).

---

## 8. bounds 주입 + Phase-0

**§8.0 replacement decision 구조에 numeric bound 부재**: 전부 enum(`ReplacementMode`/`ReplacementWorkflowState`/
`CredibleIntermediateOutcomeKind`/`ReevaluationTargetKind`/`ReplacementOutcome`)·boolean·집합 논리·주입
`CanonicalDecimal`(gap/overlap duration·exposure·aggregate-risk·timing). ADR §15 line 353 "Numeric values remain
unapproved until human approval and executed evidence are recorded"는 수치를 **명시 배제**한다 — 전부 Verification/
Broker Capability Profile INSTANCE 측정값이며 주입 opaque param으로만 담는다. 값 부재 ⇒ fail-closed(§4). 값 승인은
Bounds-Approver 게이트(§9.2).

**§8.1 Verification-Profile 키 실측(`measurement_source` 전수 확인)**: ADR §15 line 338–347이 요하는 **8 timing
bound(항목 수 대조 = 8, 절단 인용 금지 #16 M4)** 및 VERIFICATION-PROFILE-002.yaml 키 상태(전수 grep):

§15 요구 8 bound(verbatim): (1) authorization-to-first-leg transmission; (2) first-leg-to-intermediate-state
evidence; (3) maximum Protection Gap duration; (4) maximum overlap duration; (5) restrictive-state propagation to
egress; (6) Final Quantity Proof acquisition; (7) replacement completion or containment; (8) broker-query and
reconciliation staleness.

**PR-전용 키(실재·null 확인)**:
- **(3) Protection Gap**: `B_protection_gap`(line 625, `value_ms: null`, "Maximum permitted interval without
  sufficient protection during an explicitly approved cancel-first replacement; an unknown or exceeded gap is
  containment (ADR-002-011)", `measurement_source: protective_replacement_and_broker_log`) — **실재·null**.
- **(4) overlap duration**: `B_protection_overlap`(line 632, `value_ms: null`, source `protective_replacement_and_
  broker_log`) — **실재·null**.
- **(7) replacement completion/containment**: `B_protective_replacement_contain`(line 639, `value_ms: null`,
  "Maximum interval from replacement deviation or proof failure to authoritative containment (ADR-002-011)") —
  **실재·null**.
- **(6) FQP acquisition**: `B_final_quantity_proof`(line 569, `value_ms: null`) — **실재·null**. **소유 구조 각주
  (v1.1 Q4)**: `B_final_quantity_proof`은 FQP **취득 시간 bound**로 본 replacement(§11 FQP-gated retirement)가
  참조하나, FQP **규칙·adequacy** 자체는 ADR-002-004/006(brokercap `fqp_adequate`·evidence) 소유다(§4.6 line 99).
  즉 **키는 공유 참조**(replacement가 gap/overlap bounding에 소비)이되 FQP 판정 소유는 brokercap/evidence — bound
  값 승인도 그 프로파일과 정합해야 한다(Phase-0).

**나머지 timing point(1·2·5·8) — 리뷰어 실측 후보 키 명기(v1.1 §8.1 보강)**: 결함이 아니라 **generic/other-ADR
키 또는 per-broker INSTANCE 귀속**이며 리뷰어가 실측한 후보 키(전부 실재):
- **(1) authorization-to-first-leg**: `B_protective_request_start`(line 583) 계열.
- **(2) first-leg-to-intermediate**: `B_protective_request_complete`(line 590, "informs protection-gap bounding") 계열.
- **(5) restrictive-state propagation to egress**: `B_restrictive_fence_commit`(line 331)/`B_currentness_fence_to_
  egress`(line 338) 계열(ADR-002-024 fence).
- **(8) broker-query/reconciliation staleness**: `B_broker_query_consistency`(line 597) 계열.
- **확정은 Phase-0(Bounds-Approver)**이며 정확한 §15↔VP 키 매핑은 그 게이트가 확정한다. ⇒ **confirmed candidate
  신규 VP-002 키 = 0건**(PR-전용 4키 실재·null + 후보 4키 실재 — 신규 키 불요 추정이나 매핑 확정은 이연; over-
  claim/under-claim 양쪽 봉합). per-broker gap/overlap 수치는 **Broker Capability Profile INSTANCE**(§15 line 353·
  VP 주석 line 626/633 "APPROVE per broker/order/
replacement profile"). replacement는 전 수치를 신뢰하지 않으며(VP status PROPOSED·unapproved bound ≠ approved,
VER-002-001 §6) fail-closed 처리(§4).

**§8.2 self-referential 주의(경미)**: replacement `ReplacementAuthorization`은 VP scope가 pin하는 profile version을
주입 scalar로만 담고 VP를 import·파싱하지 않는다(YAML은 하네스 #3). VP status PROPOSED ⇒ 전 수치 불신.

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

1. `tos/src/tos/replacement/` 5-module 저작(`_base.py` shim + all-false `ReplacementAuthorityEffect`·`vocabulary.py`·
   `records.py`·`predicates.py`·`state.py`[workflow lifecycle·label-grants-nothing]) + `tos/tests/replacement/`
   property test(§7) + seam cross-check(§3.4) + import-closure(§7.1).
2. core 술어(§5): `overlap_first_reservation_complete`·**`netting_absent`(구조적 magnitude 파생·M6)**·`overlap_first_
   sequencing_valid`(**4-입력: new_protection_sufficiency_current+protective_classification_present+cancellation_
   admissible+leg_admissibility·C2/M1**)·`partial_fill_reevaluation_complete`·`no_hiding_clamp`·`partial_fill_egress_
   disposition`·`replacement_mode_admissible`(**완결 signature·leg_admissibilities+bound_exceeded·G5**)·`workflow_
   label_grants_nothing` + predicate-only(§6.1/§6.2 `cancel_first_admission_gate`[+leg_admissibility]·`replacement_
   authorization_current`) + 5-어휘(`ReplacementOutcome` **5종·REPLACEMENT_TRAPPED 포함·M1/Q1**)· 2 digest-bound
   레코드·`ProtectionObligation`·`OverlapReservationClaim`(**per-outcome magnitudes·M6**)·all-false authority(§2)
   구현 + `CredibleIntermediateOutcomeKind`(9)·`ReevaluationTargetKind`(6)·`ReplacementMode`(4)·`ReplacementWorkflowState`
   (7+2) frozenset + 좌표 비붕괴 property(§2.2-5).
3. 미래 caller 런타임(Protective Action Controller / rcl-admission / Final Egress / Reconciliation Service)이
   replacement 산출 completeness/gate bool·`ReplacementOutcome`·all-false authority를 소비자(protective arbiter·rcl
   원자 commit·final egress)로 배선(§3.4; Phase 1 밖·EV-L3). **`CapacityVector` REUSE 미채택**이라 축약 reducer 불요
   (§0.4c; are aggregate-risk 주입 소비).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

ADR §23 Open Questions(6항)·§24 Approval Gate(9조건)에서 Phase-1 밖으로 이연:
1. **broker/order-type별 atomic-replace 증명 가능 조합**(§23 q1·§6.1) — brokercap INSTANCE(5 replace/amend
   semantics 주입).
2. **overlap-first를 reversal 위험 없이 쓸 수 있는 first restricted-live scope**(§23 q2) — 런타임 배선.
3. **numeric gap/overlap/proof/containment bound 승인 후 cancel-first 허용 여부**(§23 q3·§6.3) — Bounds-Approver +
   Safety Profile.
4. **broker resource reservation 증거 per profile**(§23 q4·§13) — brokercap INSTANCE.
5. **broker capability class별 FQP를 만족하는 event sequence**(§23 q5·§11) — brokercap/evidence 런타임(afg
   `cancel_ack_not_final_quantity_proof` + brokercap `fqp_adequate` 통합).
6. **numeric gap/overlap/proof/containment bound 승인**(§23 q6·§15·§24 item 2) — VP-002 4키(§8.1 실재·null) +
   미매핑 4 timing point의 Bounds-Approver 확정 + fault-injection 측정; per-broker는 Broker Capability Profile
   INSTANCE. **confirmed candidate 신규 키 0건.**
7. **rcl 원자 replacement-reservation commit protocol**(§9 line 231·§24 item 5) — rcl 런타임(`CapacityVector` 합산·
   원자 commit; PR은 completeness 판정까지).
8. **ADR-002-013 final egress·credential/route boundary·recovery 독립 리뷰 + EGRESS evidence**(§24 item 5) — 런타임.
9. **ADR-002-016 request/order/claim/ACK/fill/cancel/gap/overlap/FQP/recovery lineage(missing evidence ≠ release
   proof) + ERI evidence**(§24 item 6) — replay ENGINE 런타임(§5.4 레코드 substrate만 Phase-1).
10. **ADR-002-019 exact current admissibility per cancellation/replacement leg(halt/auction/price-limit/rate/
    session/reduce-only/trapped) + VTG evidence**(§24 item 7) — 런타임(§5 line 139 partition-scope는 protective
    `partition_lease_admissible` 주입).
11. **residual broker-resource·market-liquidity risk 명시 수용**(§24 item 8) — 운영자 게이트.
12. **ARCHITECTURE-GATE-STATUS 명시 acceptance 결정**(§24 item 9) — 실행된 PR-EV-001..012 + cross-system evidence +
    독립 리뷰(Independent-Safety-Reviewer 하드 배제, IMPLEMENTATION-PLAN-002 §3).

---

## 10. 개정 로그 + 비준 체크리스트 + 판단 지점

### 10.1 개정 로그

- **v1.2 (2026-07-26) — 에라타(의미 변경 아님·비준 효력 유지). 발견 경로: 구현 후 적대적 코드 리뷰
  MAJOR-1**(판정 ACCEPT-WITH-FIXES; CRITICAL 0·fail-open 0). v1.1은 ADR-002-019 producer를 "세션 A WIP·코드 부재"로
  보고 `leg_admissibility`를 `bool|None` 주입 슬롯으로만 서술했으나, **producer가 `tos.venue`로 착지**(설계 #19)해
  그 사유가 소멸했다. 정정 3건:
  - **§3.4 -019 행 정정(실측 signature)**: 실 producer `OrderAdmissibilityResult`(`venue/vocabulary.py:91`)는
    **4토큰**(`ADMISSIBLE`/`RESTRICTED_PROTECTIVE_ONLY`/`INADMISSIBLE`/`UNKNOWN`)이며 `__bool__`이 `TypeError`를
    올리는 **truthy-untestable 봉인**을 갖는다(설계 #19 §2.2(1)/M1). 접기 규칙을 **caller-side
    `is OrderAdmissibilityResult.ADMISSIBLE`만 True**로 확정하고(나머지 3토큰·`None` ⇒ fail-closed),
    `RESTRICTED_PROTECTIVE_ONLY` 하 protective-라벨 leg의 세부 허용은 **venue 소유 `protective_label_no_bypass`**
    (`venue/predicates.py:599`, 4조건)를 caller가 조합해 산출한 bool로만 착륙시킨다 — replacement 재결정 0
    (§3.5 권위 중복 배제 유지).
  - **§7 MANDATED seam 목록**: `test_seam_vtg` 항목을 "이연"에서 **"작성됨"**으로 갱신(4토큰+None 전수 polarity·
    `bool()` TypeError 확인·`protective_label_no_bypass` 실구동 조합 경로 포함).
  - **제목/비준 parenthetical**: v1.1 → **v1.2 에라타** 표기 + 상단 에라타 고지 블록 신설.

  **효력 판정**: 접기 규칙은 **보수 방향**(4토큰 중 1개만 True)이라 어떤 허용도 넓히지 않는다 ⇒ v1.1 비준 효력·
  §0.2 비-acceptance·**닫는 PR-EV = 0건** 규율 전부 **불변**. 코드 측 동반 변경은 `vocabulary.py`
  `ORDER_ADMISSIBILITY_ADMISSIBLE` 토큰 상수 1개(+drift lock 테스트)이며 **술어 로직 변경 0건**.
  동반 반영된 리뷰 지적(설계 텍스트 무영향, 테스트 전용): MAJOR-2 StrEnum member→value 바인딩 고정·MINOR-1
  `_ID_FIELD` drift lock·MINOR-2 NaN/Inf 도달 가능 가드 고정·MINOR-3 HALT 합성 순서 고정·NIT-1 `netting_absent`
  보증 범위 명시(서명 탐지기 — 회계 정확성은 evidence/런타임 소관).
- **v1.1 (2026-07-26) — 독립 비평 리뷰 REVISE(CRITICAL 2·MAJOR 6·MINOR 8·Gap 8·Open Q 5) 반영, 운영자 비준 대기.**
  전 1차 소스 재실측(받아쓰기 금지·phantom 재발 0; 오케스트레이터가 C1·C2·M1 재실측 확정, 저작자가 전 항목 1차
  소스 재확인 — 반론 0). 문서 번호 **#18 확정**(세션 A #17 SBR 완결·다음 VTG=#19; 제목 "(잠정)" 제거, Q5).
  - **C1 (netting 극성 3중 모순·∅-vacuous permissive)**: §0.4d·§4.1의 `netting_applied is not True`(None 통과=
    fail-open)를 제거하고 **no-netting을 구조적 magnitude 파생**으로 전환(M6 처방(b) — old/new/simultaneous 비음수
    병존). §4.7 라벨 정정. **§0.1(j) truthy-sentinel 극성 분기 명문화**(양극성 `is True`/음극성 `is False`, 음극성에
    `is not True` 금지) + §10.2(10) 음극성 필드 전수 목록(`hides_uncovered_or_reversing`·`material_change`·
    `became_risk_increasing`) + 양극성 목록.
  - **C2 (new sufficiency 조달원 category error·fail-open)**: `overlap_first_sequencing_valid`를 **4-입력 conjunction**
    으로 분리 — `new_protection_sufficiency_current`(§10 per-field, evidence/brokercap, PR-EV-006 좌표) + `protective_
    classification_present`(aggregate-risk 축, 별개) + `cancellation_admissible` + `leg_admissibility`. protective
    `protective_classification_present`(:309) docstring 명제="PROTECTIVE_PROVEN via aggregate-risk"가 §10 per-field
    sufficiency와 **다른 축**임을 실측 확정. §3.4 **9번째 생산자 행**(evidence/brokercap field-proof) 신설. **§4.6a
    신규 불변식**(§1:34 ACK≠effective 8필드 + §10:267 no-inertia). §4.7 sufficiency/classification/arbiter 3행 분리.
  - **M1 (§5:139 (B) leg별 -019 admissibility 슬롯 전무)**: §1 표 (A)/(B)/(C) 3규범 분할. `overlap_first_sequencing_
    valid`·`cancel_first_admission_gate`·`replacement_mode_admissible`에 **`leg_admissibility` 주입 슬롯**(mode
    합성점=전 leg frozenset 양성). §3.4 -019/VTG 생산자 행(VTG-EV 4/12 L1 슬라이스 실측). §4.7 `proceed-leg-without-
    current-admissibility` 금지동사+행. **`ReplacementOutcome`에 `REPLACEMENT_TRAPPED` 5번째 값**(Q1 해소).
  - **M2 (§4.5 reserve 행 ↔ §5.1 9종 모순)**: reserve 행을 "**9종 mode-무관 공통(§9:233 'at least')** + mode 강조분"
    형식으로 정정·행 제목 개칭.
  - **M3 (§16 recovery 9-step 절단)**: 탈락 5번 "reconcile current exposure and recognized non-trade changes"
    (ADR-002-010) 복원(§6.3). **§10.2(12) 카운트 대조를 ADR 전 열거로 확장**(§5:10·§7:12·§10:9·§11:7·§16:9·§18:10;
    상단 리뷰 이력 (i)도 확장).
  - **M4 (§7 authorization 12항 중 189/191후반/199 누락)**: §2.1·§2.3에 scope tuple(189)·current exposure version
    (191)·completion/failure/containment conditions(199) 복원 + "(§7 line 188–199, 12항)" 병기(199=§15:351 pre-
    authorized containment digest 근거).
  - **M5 (§15:351 3 SHALL NOT 무매핑)**: §4.7 금지동사 3종(extend-authority/widen-capacity/declare-complete on
    bound-exceed) + §1 표 부기 + §5.3 `bound_exceeded ⇒ REPLACEMENT_CONTAINED` canary. §4.7 스코프를 ADR 전 조항
    스윕으로 확장.
  - **M6 (edge-0 근거 재작성 + no-netting 실질화)**: are `records.py:19–25`("REUSES the type only") 실측 인용 —
    "타입 REUSE ≠ 산술 소유" 인정 후 edge-0 근거 재작성(are=credible-set/risk 축 소유·PR L1=set/polarity/magnitude
    논리·좌표 충돌 회피·protective #11 동형). **no-netting을 injected flag→구조적 magnitude 파생**(처방(b) 채택;
    `OverlapReservationClaim.magnitudes`). §10.3-1 (a) edge-1 vs (b) 판단 지점.
  - **MINOR m1–m8**: m1 리스트 범위 off-by-one(§7 186→188·§5 109→110·§10 253→254·§11 275→276·§16 361→362·§18
    395→396) · m2 §4.5 line 163→165(Protection Gap "creates") · m3 §0.4d line 237→238 · m4 cancel-ACK≠FQP 앵커
    `AFG-EV-004/AFG-INV-009` 병기 + ADR-002-022:358 상호 이연 인용(§4.6) · m5 형제 카운트 18→**19**(sbr `9eb13bba`
    커밋) · m6 §1 표 §2·§3 행 + Driver 6/§9:247/§20.5 priority≠capacity 소유자 배정 · m7 §20 행 §20.1–20.7 보강 ·
    m8 `ProtectionObligation` 소비처 배정(§12 REMAINING_PROTECTIVE_OBLIGATION target·max-overlap/gap 좌표, §2.1).
  - **Gap G1–G8**: G1=§4.6a(§1:34 불변식·C2와 동일) · G2=priority≠capacity(m6) · G3=§15:351(M5) · G4=§4.7 스코프
    (M5) · G5=`replacement_mode_admissible` 완결 signature(`...` 제거·leg/bound/sufficiency 착륙, §5.3) · G6=
    `ProtectionObligation`(m8) · G7=§8:225 HALT-blind-cancel both-ways canary(§5.3/§7) · G8=§18:408 9 metrics 이연
    문장(§5.4).
  - **Open Q1–Q5**: Q1=`REPLACEMENT_TRAPPED` 5번째 값(M1-⑤) · Q2=§6.2 `economic_effect_persists` 양극성 축 명확화
    (`is True` 요구) · Q3=`ReplacementWorkflowState` **전이 술어 NOT Phase-1 판정**(어휘+label-grants-nothing만; §5.3) ·
    Q4=`B_final_quantity_proof` 소유 구조 각주(FQP 규칙=brokercap/evidence, 키=공유 참조, §8.1) · Q5=#18 확정.
  - **§8.1 보강**: 미매핑 4 timing point 리뷰어 실측 후보 키 명기((1)`B_protective_request_start:583`·(2)`B_protective_
    request_complete:590`·(5)`B_restrictive_fence_commit:331`/`B_currentness_fence_to_egress:338`·(8)`B_broker_query_
    consistency:597`; 확정은 Phase-0). **시리즈 규율 개선 4건** 상단 리뷰 이력에 명문화(극성 분기·카운트 전수·seam
    명제 동일성 열·§-row normative 문장 단위). **리뷰 처방 전건 정확 판정(반론 0).**
- **v1.0 (2026-07-26) — 초안, 독립 비평 리뷰 대기.** ADR-002-011을 Phase 1(EV-L1) 설계 계약으로 실현. 패키지
  `tos.replacement`(대안 `tos.pr`[cryptic·prefix]·`tos.protrepl`/`tos.protreplace`[cryptic/verbose]·`tos.gap`[좁음]·
  `tos.replace`[collision] 기각, §0.4a). 어휘 5종(`ReplacementMode` 4·`ReplacementWorkflowState` 7+2·`Credible
  IntermediateOutcomeKind` 9·`ReevaluationTargetKind` 6·`ReplacementOutcome` 4[v1.1 M1: +TRAPPED=5]) + digest-bound 2 레코드
  (`ReplacementAuthorization`·`ReplacementWorkflowRecord`, 전부 IndependentIdArtifact·generation-immutable append-only)
  + value(`ProtectionObligation`·`OverlapReservationClaim`·all-false `ReplacementAuthorityEffect`)(§2). EV 분류:
  **core 2행(PR-EV-001·005, #11 protective형 core tier) / predicate-only 2행(002·008) / not-Phase-1 8행 — 닫는
  PR-EV = 0건**(§1). **실측 확인**: 오케스트레이터 사전 카운트 "L1 슬라이스 2행 = 001·005"가 register CSV-aware
  파싱과 일치(정정 없음). seam: **9-생산자(protective·afg·brokercap·orthostate·rcl·authority·recon·are·evidence
  [v1.1 C2로 evidence 9번째 추가]) 주입 소비 + produced-bool 생산, sibling edge 0건(권장·protective #11 동형),
  PROMOTE 0**(코드 실측: protective `predicates.py:
  523/460/246/588`·`vocabulary.py:180/118/60`, afg `predicates.py:794/713`·`state.py`, brokercap `predicates.py:
  595/377/437`·`vocabulary.py:203`, orthostate `vocabulary.py:92/61/103–104/86/88`, rcl `vector.py:74`·`predicates.py:
  711`·`vocabulary.py:15/94`·`authority.py:39–40`·`records.py:185`, recon `records.py:28`).
  **핵심 아키텍처 판정 3건**: (i) **overlap-first 이중 계상 정합**(§0.4d) — replacement가 9-outcome completeness +
  no-netting 소유, rcl이 `aggregate_usage` 합산(이중 계상=보수적)·hard-envelope 강제, are가 aggregate-risk 투영 소유;
  (ii) **cancel-ACK≠FQP 3-ADR 좌표**(§4.6) — L1 술어=afg, arbiter 적용=protective, PR-EV-004=L3+Broker 통합(닫지
  않음·재저작 금지); (iii) **protective↔replacement 컨텍스트 분할**(§3.5) — protective=partition/degraded lease·
  arbiter·classification·retry, replacement=normal 워크플로 mode/overlap-first/cancel-first gate/gap-overlap/partial-
  fill/FQP-retirement; 상호 명시 이연(replacement §5:139 ↔ protective 설계 #11:726). **edge 결정**: `CapacityVector`
  REUSE(edge-1) 검토 후 **기각**(§0.4c [v1.1 M6 재작성: are는 "type only" REUSE·산술 소유 아님; 근거를 are=
  credible-set/risk 축 소유·PR L1=set/polarity/magnitude 논리·좌표 충돌 회피·rcl `GrantDecisionRef` replacement
  미커버·protective #11 edge-0 동형으로 재정립]) — edge 0 권장·판단 지점. 중심 fail-closed 술어: `overlap_first_
  reservation_complete`(구조적 no-netting)·`overlap_first_sequencing_valid`(new-first·4-입력)·`partial_fill_
  reevaluation_complete`(6-target)·
  `cancel_first_admission_gate`(8조건)·`replacement_authorization_current`(§5/§6). **∅-공허 양방향**(§4.7 8행). **방향
  극성 진리표**(overlap-first↔cancel-first §4.5). **truthy-sentinel**(`ReplacementOutcome is ADMISSIBLE`·protective
  `Admissibility is ADMISSIBLE`·bool `is True`·양성 identity 도달·fall-through 금지 #16 CRITICAL). 앵커: PR-EV-001..012·
  PR-AC-001..012(§0.4f; PR-INV 부재 실측). **bounds 실측**: VP-002 PR-전용 4키(`B_protection_gap`·`B_protection_
  overlap`·`B_protective_replacement_contain`·`B_final_quantity_proof`) 전부 실재·null(confirmed candidate 신규 키
  0건; 나머지 4 timing point 매핑 Phase-0, §8.1). 선제 봉합: fail-open(§4)·∅-공허 양방향(§4.7)·truthy-sentinel
  (§2.2)·방향 극성(§4.5)·under-realization(형제 전용 술어엔 정의 술어·orthostate 좌표-의존 정직 이연 §3.4 (b))·
  phantom 0(전 인용 grep 실측)·전사 완전성(§9 9항·§12 6항·§15 8항 항목 수 대조)·좌표 비붕괴(§2.2-5). **어떤 EV도
  닫지 않음·acceptance 미선언.** **문서 번호 #18**(v1.0 잠정 — 세션 A #17 SBR 선점 우려; v1.1 확정 — Q5).

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

1. **패키지 명명** `tos.replacement`(변별 토큰 "Replacement") 승인 — 또는 대안(§0.4a `pr`/`protrepl`/`protreplace`/
   `gap`/`replace` 기각 근거 검토; naming은 load-bearing 아님·운영자 치환 가능). **문서 번호 #18 확정**(v1.1 —
   세션 A #17 SBR 완결·다음 VTG=#19; Q5).
2. **seam 결정**: 9-생산자 주입 소비 + produced-bool 생산(sibling edge 0건) — §3.4/§0.4b. **[운영자 판단 지점]**.
   protective/afg/brokercap/orthostate/rcl 슬롯이 실재함을 코드로 재확인(리뷰어: `protective/predicates.py:523/460`·
   `afg/predicates.py:794/713`·`brokercap/predicates.py:595`·`orthostate/vocabulary.py:103–104`·`rcl/vector.py:74`
   인용 라인 검증 — sibling 서사 아님).
3. **`CapacityVector` REUSE 미채택 결정**: overlap-first reservation을 edge-0(주입 verdict)로 두고 `CapacityVector`
   REUSE(edge-1, pr→rcl)를 기각한 근거(§0.4c: are aggregate-risk 소유·rcl `GrantDecisionRef` replacement 미커버·
   protective #11 edge-0 동형) 검토. **[운영자 판단 지점]**: edge 0(채택) vs edge-1 REUSE. 이중 계상 정합(§0.4d)이
   edge-0에서도 성립함(rcl 합산·hard-envelope 주입 verdict) 재확인.
4. **overlap-first 이중 계상 판정(§0.4d)**: "원본+대체 동시 커버"가 rcl `aggregate_usage` 합산과 정합(이중 계상=
   보수적·no-netting이 핵심), replacement가 completeness+no-netting 소유·rcl이 산술·are가 risk 투영 소유임을 재확인.
   **[핵심 설계 지점]**.
5. **cancel-ACK≠FQP 3-ADR 판정(§4.6)**: afg `cancel_ack_not_final_quantity_proof`(L1)·protective `cancellation_
   admissible`(arbiter)·PR-EV-004(L3+Broker 통합·미저작)의 분할이 정확한지·replacement가 L1 재저작하지 않음 재확인.
   **[핵심 소유권 지점]**.
6. **protective↔replacement 분할(§3.5)**: replacement가 Cancellation Arbiter(`cancellation_admissible`)·partition-
   lease(`partition_lease_admissible`)·classification·bounded-retry·capacity 산술·FQP·atomic-replace·attempt 상태·
   HALT precedence·recovery를 **재저작하지 않음** 확인(#8·#11·#16 권위 중복 교훈). protective §3.5(설계 #11:726)의
   gap/overlap 이연과 replacement §5:139의 partition 이연이 상호 정합함 재확인.
7. **EV 분류·실측**: core 2 / predicate-only 2 / not-Phase-1 8 판정과 **닫는 PR-EV = 0건** 규율 확인. "EV-L1-complete
   주장 금지" 부착 self-consistency pass(§1↔§4/§5/§6↔§7).
8. **fail-closed·∅-공허 양방향(§4.7)**: 빈 outcome⇒UNKNOWN·빈 target⇒restrictive·빈 조건⇒False·old/new/simultaneous
   magnitude None/음수⇒False(구조적 no-netting)·None magnitude⇒UNKNOWN/DENY·sufficiency/classification/arbiter/leg
   None⇒old취소불가·leg None⇒TRAPPED·bound 초과⇒CONTAINED·빈 Admissibility⇒deny, **각각 금지+허용 canary 둘 다**
   확인(#6 fail-open·#10/#11/#16 ∅-void 교훈; §4.7 표(12행)↔§7 목록 1:1). 금지 동사 커버리지 대조(§4.7 ADR 전 조항
   스윕·M5 3 SHALL NOT·M1 proceed-leg-without-admissibility·C2 ACK-as-effective 포함).
9. **방향 극성(§4.5)**: overlap-first(new→old·gap 없음·overlap)와 cancel-first(old→new·gap·overlap 없음)가 반대
   방향 규칙임을 진리표로 검산, `overlap_first_sequencing_valid`(new-first)와 `cancel_first_admission_gate`(old-first)
   혼동 0·mode fall-through 승격 0 확인(#16 C1 방향-반전 교훈).
10. **truthy-sentinel 극성 분기(§2.2·§0.1(j), v1.1 C1)**: `ReplacementOutcome` 게이트 `is REPLACEMENT_ADMISSIBLE`·
    protective `Admissibility` 게이트 `is ADMISSIBLE`·**양극성 필드(`within_hard_envelope`·`new_protection_
    sufficiency_current`·`protective_classification_present`·`cancellation_admissible`·`leg_admissibility`·afg
    `economic_effect_persists`)는 `is True`만**·**음극성 필드(`netting`[→구조적 magnitude 파생]·`hides_uncovered_or_
    reversing`·`material_change`·`became_risk_increasing`)는 `is False`만**(음극성에 `is not True` 사용 0건 전수
    확인)·**완료/허용 결과 양성 conjunction identity 도달(fall-through 금지 #16 CRITICAL)** — StrEnum/bool|None truthy
    관통 0건 확인.
11. **실측-원천·phantom 0**: 전 인용 타입/필드(`cancellation_admissible`·`partition_lease_admissible`·`Admissibility`·
    `ProtectiveActionKind`·`protective_classification`/`protective_classification_present`·`retry_admissible`·afg
    `cancel_ack_not_final_quantity_proof`/`no_blind_retry`/`economic_effect_persists`(state.py:545)·brokercap
    `fqp_adequate`/`broker_capability_sufficient`(:206)/`same_order_retry_allowed`/`rate_admission_ok`/`ReplaceSemantics`
    (`vocabulary.py:202`)·orthostate `BrokerOrderState`/`TransmissionAttemptState`/CANCELLED+later-fill·rcl
    `CapacityVector`/`aggregate_usage`(:103)/`effective_limit`(:139)/`partition_verdict`/`TransitionCause.FINAL_
    QUANTITY_PROOF`/`GrantDecisionRef`·recon `ConservativeBound`·evidence per-field·ADR-002-019 VTG)이 실코드/스펙에
    존재함을 grep 재확인(#10 MAJOR phantom 교훈). PR-AC(12)·PR-EV(12)·VTG-EV(4/12 L1) 수·seam 라인이 원문/코드와
    일치. **형제 카운트 19(sbr `9eb13bba` 커밋 반영·m5)·untracked 인용 0건** 확인.
12. **전사 완전성(카운트 대조 전수화·M3)**: `CredibleIntermediateOutcomeKind` 9종(§9:234–243)·`ReevaluationTargetKind`
    6종(§12:292–298)·§15 timing bound 8종·**§5 orthogonal 10항·§7 authorization 12항·§10 sufficiency 9항·§11 FQP 7항·
    §16 recovery 9항·§18 evidence 10항+metrics 9항**이 ADR 원문 항목 수와 전수 대조 일치(절단 인용 0·off-by-one
    리스트 시작 라인 정정 — #16 M4·v1.1 M3/m1 교훈).
13. **bounds 실측(§8.1)**: VP-002 PR-전용 4키 실재·null·confirmed 신규 키 0건·per-broker INSTANCE·미매핑 4 timing
    point Phase-0 이연(over-claim/under-claim 양쪽 봉합) 재확인.
14. **broker-agnostic·숫자 하드코딩 0·firewall(§0.3)·verbatim 전사(§2.2)** 확인.
15. **비-acceptance**: 어떤 PR-EV/ADR acceptance·restricted-live·production도 선언 안 함(§0.2)·Independent-Safety-
    Reviewer 하드 배제·비준 기록 = "v1.1 개정 완료 — 운영자 비준 대기".
16. **C2/M1 신규 검증(v1.1)**: (a) `overlap_first_sequencing_valid` 4-입력 분리(sufficiency[§10 per-field, evidence/
    brokercap] ≠ classification[aggregate-risk] — 명제 동일성 §3.4)·(b) `leg_admissibility` 슬롯이 sequencing/gate/
    mode 합성점에 착륙·(c) §4.6a §1:34 불변식·(d) 구조적 no-netting magnitude 파생(injected flag 부재) 재확인.

### 10.3 운영자 판단 지점 (요약)

1. **no-netting 실현 방식 (a) `CapacityVector` REUSE(edge-1) vs (b) 구조적 magnitude 파생(edge-0) — (b) 채택·권장**
   (v1.1 M6·리뷰어·오케스트레이터 모두 (b) 권장) — §0.4c/§0.4d. **(b)**: `OverlapReservationClaim.magnitudes`의 old/
   new/simultaneous 비음수 병존으로 no-netting 구조 증명(injected flag 위조 불가·edge 0 유지). **edge-0 근거 재정립
   (M6)**: are는 `CapacityVector` **타입만 REUSE**(`records.py:19–25` "REUSES the type only")하고 산술은 rcl 소유 —
   "타입 REUSE ≠ 산술 소유"; PR L1은 set/polarity/magnitude 논리이므로 타입 불요·are=credible-set/risk 축 소유·좌표
   충돌 회피·protective #11 edge-0 동형. 미래 런타임에서 vector 직접 조립 필요 시 (a) edge-1(pr→rcl 7번째 후보;
   are→rcl·afg→rcl·ioc→rcl 선례)로 승격 가능. 리뷰어 확인 지점.
2. **seam decoupled(edge 0, produced-bool·9-생산자)** vs 대안 B(소비자 측 edge) — §0.4b. protective #11 동형·권장.
3. **overlap-first 이중 계상 정합(§0.4d)** — completeness+no-netting은 PR, 합산은 rcl, risk 투영은 are. 핵심 설계
   지점·리뷰어 확인.
4. **cancel-ACK≠FQP 3-ADR 분할(§4.6)** — L1=afg·arbiter=protective·PR-EV-004=L3+Broker 통합. 재저작 금지 판정 확인.
5. **VP-002 bounds Bounds-Approver 승인** — PR-전용 4키 실재·null·미매핑 4 timing point(1·2·5·8) 매핑 확정·per-broker
   INSTANCE(§8.1·§9.2 item 6).
6. **문서 번호 #18 확정(v1.1, Q5)** — 세션 A #17 SBR 완결·다음 VTG=#19로 메모리 조율(#16 AFG #15→#16 개번 선례와
   달리 본 문서는 확정).

### 10.4 독립 리뷰어 공격 지점 (open questions)

1. **overlap-first가 edge-0(주입 verdict)로 충분한지** vs `CapacityVector` REUSE(edge-1)가 필요한지 — 특히 이중
   계상(§0.4d)이 completeness+no-netting 술어 + rcl 합산 주입 verdict로 온전히 표현되는지(protective #11 edge-0
   선례로 정합 판단이나 운영자 확인).
2. **cancel-ACK≠FQP를 PR-EV-004(L3+Broker)로 이연하고 afg L1을 소비**한 판정이 정확한지 vs PR이 replacement-특유
   FQP-retirement L1 술어를 저작해야 하는지(§4.6; afg AFG-EV-004가 이미 core L1이라 재저작=권위 중복 판단).
3. **protective `cancellation_admissible`가 replacement cancellation을 이미 커버**(§11.4 no-optimistic-credit)하므로
   PR이 arbiter를 재저작하지 않고 sequencing/gate가 소비만 하는 경계(§3.5)가 정확한지.
4. **`ReplacementWorkflowState`(7+2)가 orthostate order/attempt 축과 별개**(§5 no-collapse·§2.2-5 좌표 비붕괴)이며
   workflow label이 어떤 authority도 부여하지 않는(§4.4 all-false) 판정이 정확한지.
5. **방향 극성(§4.5)** overlap-first↔cancel-first 진리표가 §6.2/§6.3 원문과 정확히 정합하는지·mode 선택이 fall-through
   승격을 구조적으로 배제하는지(#16 C1 교훈).
6. **core 2행(001·005)이 실제로 전부 L1-decidable substrate**(completeness/no-netting/sequencing·6-target/no-hiding-
   clamp)를 갖고 `/3` overlay(integration fault·adversarial interleaving)와 분리가 정확한지.
7. **§8.1 미매핑 4 timing point(1·2·5·8)**를 "confirmed 신규 키 0건·Phase-0 매핑"으로 정직 이연한 판정이 under-claim/
   over-claim 아닌지(#16 M4 절단 인용 교훈 반대편 — 확인 못 한 것을 확정하지 않음; v1.1 후보 키 명기 후에도 확정은 Phase-0).
8. **(v1.1 C2) new Protection Sufficiency Proof 조달원 분리**: `new_protection_sufficiency_current`(§10 per-field,
   evidence/brokercap, PR-EV-006)와 `protective_classification_present`(aggregate-risk)를 별개 conjunct로 분리한 것이
   정확한지 — protective `protective_classification_present`(:309) docstring 명제가 §10 sufficiency와 다른 축임을 재확인.
   §1:34 "ACK alone ≠ effective"의 fail-closed(§4.6a)가 sufficiency 슬롯에 온전히 착륙하는지.
9. **(v1.1 M1) per-leg -019 admissibility 슬롯**: §5:139을 (A)label/(B)leg-admissibility/(C)partition 3규범으로
   분할하고 (B)를 `leg_admissibility` 주입 슬롯(mode 합성점=전 leg frozenset 양성)으로 착륙시킨 것이 정확한지·
   `REPLACEMENT_TRAPPED` 5번째 값이 protective `Admissibility.TRAPPED`와 좌표 비붕괴 유지하는지(§2.2-5).
10. **(v1.1 M6) 구조적 no-netting 파생**: `netting_applied` injected flag를 제거하고 `OverlapReservationClaim.
    magnitudes`의 old/new/simultaneous 비음수 병존으로 no-netting을 파생한 것이 fail-open을 완전히 제거하는지·
    caller 위조 불가한지·edge-0을 유지하면서 이중 계상 정합(§0.4d)을 온전히 표현하는지.

---

**규율 태그(문서 전체 적용)**: predicate/coordinate substrate only; PR-EV-001..012 전부 NOT_IMPLEMENTED — core
2행(001·005)은 `/3` 통합·독립 리뷰 대기, 나머지 10행(002·003·004·006·007·008·009·010·011·012)은 EV-L2/L3 fault
injection·adversarial·+Broker evidence 대기. **EV-L1-complete 주장 금지. 닫는 PR-EV = 0건. cancel-ACK≠FQP L1 술어는
afg 소유(재저작 0)·Cancellation Arbiter는 protective 소유(재저작 0)·new Protection Sufficiency Proof(§10 per-field)는
evidence/brokercap 소유(재저작 0·C2)·per-leg -019 admissibility는 VTG 소유(재저작 0·M1)·capacity 산술은 rcl 소유
(재저작 0). no-netting은 구조적 magnitude 파생(injected flag 부재·M6). truthy 극성 분기(양극성 `is True`/음극성
`is False`·C1). sibling edge 0(권장)·PROMOTE 0. 문서 번호 #18 확정. 어떤 ADR acceptance·restricted-live·production도
미승인.**
