# 설계 문서 #34 — tos.egressgw + tos.brokeradapter: Order Construction + Broker Egress Gateway + Broker Adapter(paper send) 계약 (D-E4, 수직 슬라이스 #1 send 경계, provisional·닫는 EV 0건) (2026-07-29, v1.1)

> **⚖ 비준 기록**: **2026-07-29 운영자 위임 자동 비준(v1.1)** — 오케스트레이터가 게이트 조건을 검증하고
> 기록함: 독립 비평 리뷰 REVISE(CRITICAL 0·MAJOR 2 — 단일 근본원인 "live/비-live↔브로커-도달/합성 축
> 혼동"으로 수렴·합성 transport 판정 자체는 리뷰어 concur·17항목 매핑 전수 무결·인용 ~55 phantom 0)
> → v1.1(937행) 전건 처방 반영·실증 반론 0(§2.2 축 재구성[③④ 방어심층 강등]·§4.1/§4.2 broker-applicability
> 양성 게이트["no-broker-reached" 근거 정정]·quirk 17 정정[에라타 `c24844e5` 정합]·§10.2:617 화해·envelope
> 봉입·thin-adapter·드리프트 정정) + 저작자 자체 인용 오류 self-catch(:582→:583, 재grep 실측) → 오케스트레이터
> 재실측 스팟체크 통과(축 문구 7/0·no-broker-reached 5·ADR §11.1:583 원문 대조). 세션한도 사망→디스크
> 실측+트랜스크립트 재개 무손실 복구. 품질 파이프라인 잔여 단계(구현 → 적대적 코드 리뷰) 유지. ADR
> acceptance·live authorization과 무관. 효력: Phase 1 `tos/src/tos/egressgw/`+`tos/src/tos/brokeradapter/`
> 구현 착수(슬라이스 실행 = 합성 paper transport·실 KIS 경로는 설계 보존).

> **⚖ 비준 대상 설계 (위임 자동 비준 2026-07-29 연장 경로)**: 본 문서는 비준 대상이다. 후속 파이프라인 —
> 1차 심사 → 독립 비평 리뷰 → 개정 → **운영자 위임 자동 비준(2026-07-29 연장: "Part-2/3 설계 비준도 위임
> 자동비준으로 연장")** → 구현 → 적대적 코드 리뷰 → 게이트 — 를 전량 유지한다. 오케스트레이터가 게이트 조건
> (독립 비평 리뷰 통과·upgrade 조건 충족·재실측 스팟체크)을 검증 후 비준을 기록·집행한다. 본 비준은 프로젝트
> 측 설계 계약 발효이며, **ADR acceptance(EV 실행 증거)·live authorization과 무관하다**(§1.1). 효력: Phase 1
> `tos/src/tos/egressgw/` + `tos/src/tos/brokeradapter/` 구현 착수.
>
> **v1.1 개정(2026-07-29, 독립 비평 리뷰 REVISE 반영 — CRITICAL 0·MAJOR 2·MINOR 4·NIT 2; 인용 ~55건 phantom 0·
> 17항목 매핑 무결·합성 transport 판정 리뷰어 concur·공격 8종 불발)**: 두 MAJOR는 단일 근본원인(축 혼동)으로
> 수렴하며 **판정 번복이 아니라 정당화 축 정정**이다 — **(MAJOR-1)** 옵션(b) 실 모의 차단 축을 "live/비-live"에서
> **"브로커-도달/합성"**으로 정정(§2.2 재구성·③④ live-축 방어심층 강등)·**(MAJOR-2)** §4.1 Deferred 안전-메시를
> **broker-applicability 양성 게이트**로 봉인(조용한 skip=fail-open·무조건 deny=합성 차단, 둘 다 회피·§4.2). MINOR
> 4·NIT 2 전건 반영(개정 로그 §16). **핵심 판정 5·구조는 리뷰 지지로 유지.**
>
> **⚠ provisional·닫는 EV 0건 (본 문서 최상위 정직 선언 — §1.1)**: 본 슬라이스의 send 경계 산출은 **엔지니어링-통합
> provisional**이며 **어떤 EV-L2+ PASS도 주장하지 않는다.** 세 사유가 합류한다 — (a) 슬라이스의 "send"는
> **합성 paper transport**(네트워크 0)이지 실 브로커 도달이 아니다(§2 판정), (b) **P0-2 미결**(승인된 Broker
> Capability Profile INSTANCE 부재 — register §1:50 `broker_capability_profiles: []`), (c) **KIS 프로파일 VERIFIED
> 0**(어떤 action class도 live로 `capability_admissible`=ADMISSIBLE 불가·§2.2). 따라서 이 문서가 배선하는 send
> 경계(step 15-19)는 **구조·좌표 술어의 기계 실증**이지 currentness/QCC/single-use/credential 격리의 acceptance
> 증거가 아니다. GOV-001의 세 거버넌스 행위 중 어느 것도 수행하지 않는다.
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며 스펙 텍스트
> (RFC/ADR/템플릿/프로파일/register)를 **변경하지 않는다.** 본 문서는 RFC-002 §10.8(Broker Egress Gateway)·
> ADR-002-002 §11.4(Send Boundary step 15-19)·RFC-005 §7/§11/§12(실행 경계)·ADR-002-020(ioc 구성)·ADR-002-013
> (egress 보안)·ADR-002-004(brokercap)를 그린필드 `tos.egressgw` + `tos.brokeradapter` 신규 패키지의 **owning
> runtime**으로 실현하는 계약이다. **`tos.egress`(ADR-002-013 QCC 커널) 잠식 금지** — egressgw는 egress 술어를
> **소비(import)**하되 커널을 수정하지 않는다(§0.3·§11-3).
>
> **broker-agnostic**(project memory `tos-spec-broker-agnostic`): 본 계약의 어휘·인터페이스는 전부 broker-agnostic이다.
> KIS·KRX 사실은 규범으로 등장하지 않으며, broker 능력·quirk는 비규범 Broker Capability Profile INSTANCE(트랙 d·
> `docs/plans/2026-07-29-tos-broker-capability-profile-kis-draft.md`) 참조로만 표현한다.
>
> **선행 문서(의존)**:
> - [설계 #31 — tos.engine 이벤트 코어 (D-E1, v1.1 비준)](2026-07-29-tos-engine-event-core-design.md) — 본 문서의
>   **핸드오프 상류**. §4.5(item-7: fail-closed 보장은 step 1-14·**step 15-19는 D-E4**)·§12-3(SendHandoff·
>   EGRESS_RESULT 재주입·partial fill)·§2.1 D5(비동기 I/O는 send 경계 격리). committed 엔진 코드
>   `tos/src/tos/engine/`(sequencer.py·records.py·vocabulary.py·adapters.py·state.py) 실측.
> - [설계 #1 — tos/ 경계 & import-firewall (v2 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md) — §2.4
>   레이아웃·§3.2/§3.3 firewall.
> - [수직 슬라이스 스코핑 서베이 (비규범)](2026-07-29-tos-engine-vertical-slice-scoping-survey.md) §0·§1·§4·§6-2·§7-5.
> - [KIS Broker Capability Profile INSTANCE 초안 (비규범)](2026-07-29-tos-broker-capability-profile-kis-draft.md) +
>   `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml` — quirk 17(HIGH 6·초안 헤더 "16"은 오산·에라타
>   `c24844e5`)·VERIFIED 0·CLASS-D 실태.
> - [Phase-0 인간 게이트 register (비규범)](2026-07-29-tos-phase0-human-gate-register.md) — P0-2·bound 실태.
>
> **규범 원천(전부 2026-07-29 자체 grep 실측·anti-phantom §0.5)**: RFC-002 §9.1(권위 매트릭스 :549-576)·§10.8
> (Broker Egress Gateway :728-767)·RFC-005 §7(:187-215)·§11(SAFE-021 :314-343)·§12(11 SHALL NOT :346-377)·
> ADR-002-002 §11.4(Send Boundary :603-611)·ADR-002-013 §1(Final Egress Trust Boundary)·ADR-002-020(ioc 구성
> :96-509)·ADR-002-004(brokercap :118-706).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것 (7건)

1. **패키지 2개 명명 `tos.egressgw` + `tos.brokeradapter`** (negative-grep 충돌 0·§0.5·§11.1). `egressgw` =
   Order Construction Service + Broker Egress Gateway(순수 tos 강제/구성 런타임·네트워크 0). `brokeradapter` =
   Broker Adapter transport(firewall seam — 네트워크/자격증명은 tos/ 밖·슬라이스는 합성 paper transport).
2. **슬라이스 send 경계 판정 = 합성 paper transport(네트워크 0)** (§2 — 본 문서의 최대 하중 판정). 실 KIS 모의투자
   API 경로는 **설계**하되(Transport Protocol 경계 + 검증 계약 + 자격증명/경로 격리) **슬라이스 실행은 합성
   transport**다(단계 분리). 4중 구조 차단(firewall·P0-2·VERIFIED 0·Live-Armer 미지정)이 이 정직 경계를 강제.
3. **step 15-19 실현/이연 분할** (§4 — verify list 17항목을 Realize/Provisional/Deferred로 전수 매핑). D-E4가
   실현하는 것은 **구조·좌표 술어**(command↔proof↔effect 정합·좌표등가·single-use nonce·currentness proof 구조·
   credential 격리 술어)이고, **live 안전 거버넌스 메시**(Safety Authority epoch·Live Authorization·Hard Safety
   Envelope·Deviation/Incident/Monitoring)는 런타임 미착지 + 비-live 스코프라 **명시 이연**.
4. **Order Construction 계약 + G5 수량/가격 파생 seam** (§3). Proposal은 수치 필드 전무(quantity_basis str뿐·
   proposal.py:74-76 "evidence, never capacity")이므로 수량/지정가는 **Order Construction이 결정론·유계·무-수선
   규칙으로 파생**하고 ioc `compile_command`(declare-and-verify)로 봉인. 실 sizing 규칙·가격 값 표면은 **D-E2/P0-1
   이연**(provisional).
5. **quirk 구조 봉인** (§5.4·§13). KIS HIGH quirk(Q-IDEMP-1/2 blind retry·Q-CRED-1 자격증명 편재·Q-MIC-3 조용한
   폴백)를 **어댑터·게이트 계약에서 구조적으로 표현 불가능**하게 봉인 — 기존 `shared/execution/executor.py`의 결함을
   **재생산하지 않는 계약**. 근거 술어: brokercap `same_order_retry_allowed`·`uncertain_send_policy`, egress
   `credential_route_authority_disjoint`, ioc `no_silent_widening`.
6. **at-most-one의 send측 절반** (§6). D-E1은 outstanding POTENTIALLY_LIVE **retention**(§4.4) 소유. D-E4는 그
   대칭 절반 — **single-use capability/permit 소비 + attempt-identity 정합 + no-resubmit** — 을 소유(SAFE-021 :319-343).
7. **firewall 준수 + D-E1 핸드오프 타입 정합** (§0.3·§7). 두 신규 패키지는 D-E1의 `Transmit` Protocol
   (sequencer.py:104-116)·`SendHandoff`/`EgressResultPayload`/`AttemptRequest`(records.py) 계약을 **충족**하고,
   D-E1이 선물한 cur 타입 edge `egress_currentness_verdict`(adapters.py:455-509)를 재사용한다.

### 0.2 하지 않는 것 (NO 목록·경계)

1. **실 네트워크 I/O·실 자격증명·실 브로커 경로 = tos/ 밖.** firewall(설계 #1 §2.3 — network stdlib 금지)상
   `tos.brokeradapter`는 **Transport Protocol(추상 경계)** 과 **합성 paper transport**만 담는다. 실 KIS 송신
   대역(자격증명·`shared/kis`·네트워크)은 tos/ 밖 주입 구현이며 슬라이스 실행 대상이 아님(§2·§5.1).
2. **ioc/egress/cur/brokercap/venue 커널 재저작 금지.** 전부 기구현 순수 술어(§8.1 REUSE). D-E4는 **소비·배선**만.
   특히 `tos.egress`(ADR-002-013) **잠식 절대 금지**(§11-3).
3. **live 실주문·라이브 스코프 arming.** GOV-001 제3행위·Live-Armer 미지정(fail-closed). 슬라이스는 비-live-test.
4. **완전 QCC quorum 런타임·byte-level outbound 재구성·route confinement·실 credential inventory 열거.** ADR-002-013
   EGRESS-EV-001..013 런타임 미착지(egress 커널 헤더 :84-85 "Written cases are not completed evidence")·egress
   `exact_binding_holds` docstring:356-359 "byte-level outbound reconstruction … route confinement … env
   non-interchangeability … are +Security (EGRESS-EV-003 not-Phase-1)". D-E4는 **좌표등가 술어**까지만·byte 재구성
   이연(§4.4).
5. **실 SEND_STARTED durable store·실 Evidence Store.** ADR-002-016 ENGINE 이연(D-E1 §5.1)·슬라이스는 provisional
   sink. step 16 durability는 provisional(§4.6).
6. **실 RCL 원자 Permit claim/consume·실 독립 승인·실 Safety Authority/Live Authorization/Deviation/Incident/
   Monitoring 런타임.** 전부 provisional stand-in(D-E1 §4.4) 또는 명시 이연(§4.1 verify list 매핑).
7. **닫는 EV/AC 0건.** §1.1. acceptance는 §10 후속 게이트 소관.
8. **D-E2 Critical Input 가격 값 표면·D-E3 백테스트 fill 모델 코어.** D-E4는 transmit 인터페이스 slot·합성 transport
   구조만·값 표면은 D-E2(§3.1)·백테스트 fill 대역 주입은 D-E3(§5.2 공유 구조).

### 0.3 firewall 준수 선언 (설계 #1 §3.2/§3.3에 대한 본 계약의 준수)

- **두 신규 패키지의 import-closure(부분집합 allowlist·설계 #1 §3.3·D-E1 §7.1 `test_engine_import_closure.py`
  선례)**:

  - `tos.egressgw` (Order Construction + Broker Egress Gateway):
    ```
    {tos, tos.canonical, tos.ordering, tos.ioc, tos.venue, tos.cur, tos.egress, tos.brokercap,
     tos.rcl, tos.capsule, tos.evidence, tos.engine, tos.dsl, tos.egressgw}
    ```
    근거: ioc(구성·conformance·economic effect)·venue(admissibility)·cur(egress currentness)·**egress(QCC/
    single-use/credential 술어 — 소비, 잠식 아님)**·brokercap(profile admissibility·retry/uncertain-send 정책)·
    rcl(CapacityVector·Transmission Capability 타입)·capsule/evidence(증거)·engine(Transmit/SendHandoff/
    AttemptRequest/StageVerdict 타입 + adapters cur edge 재사용)·dsl(ContextValueView 값-표면 캐리어 타입·
    FLAT_QUANTITY_BASIS 단일 진리원 — 설계 #35 §0.3/§6-C9 승인 lockstep; 신규 런타임 closure 멤버 아님:
    dsl ∈ closure(tos.engine)·직접 naming 허가 확대). **로직 결합은 최소·타입/술어 소비가 대부분.**
  - `tos.brokeradapter` (Broker Adapter transport):
    ```
    {tos, tos.canonical, tos.ordering, tos.engine, tos.brokercap, tos.brokeradapter}
    ```
    근거: engine(AttemptRequest→SendHandoff→EgressResultPayload 타입)·brokercap(non-live-test 바인딩·retry/
    uncertain-send 술어). **가장 좁은 closure** — transport는 브로커-특정 행위를 경계 뒤에 격리(RFC-002 §10.8:739
    "Broker-specific behavior SHALL remain isolated behind the Broker Adapter boundary")하되 tos/ 안 부분은
    순수하다.

- **여전히 금지**: `shared.*` 운영 패키지·`os.environ`/`getenv`·**network stdlib**(socket/http/requests/aiohttp/
  urllib)·`importlib`/`exec`/`eval`/`compile` 동적 escape·wall-clock 직접 호출(`time`/`datetime`)·`numpy`/`pandas`.
  **핵심**: `tos.brokeradapter`의 network 금지 canary가 곧 §2 판정의 firewall 근거 — 실 네트워크는 tos/ 밖이어야
  하므로 transport의 실 구현은 구조적으로 tos/ 밖(§5.1). `random`/`secrets`/`uuid`(비결정 nonce) 금지 — attempt-id·
  digest는 content-addressed(D-E1 §4.3 상속).

### 0.4 핵심 아키텍처 판정 요지 (판정 + 경계)

| # | 결정 | 판정 | 근거(요지) | 리스크 |
|---|---|---|---|---|
| **E1** | 슬라이스 send 경계 (§2) | **합성 paper transport(네트워크 0)**. 실 KIS 모의투자 경로는 설계하되 실행 안 함(단계 분리) | firewall(tos/ network 금지)·P0-2 미결·VERIFIED 0(`capability_admissible`=PROHIBITED)·Live-Armer 미지정 — 4중 차단이 실 send를 구조적으로 봉쇄 | 합성 transport를 "실 send로 오독" → §2.4·§11-1 NON-AUTHORITATIVE 라벨·닫는 EV 0 반복 명기 |
| **E2** | step 15-19 실현 분할 (§4) | **구조·좌표 술어만 Realize**(conformance·좌표등가·single-use·currentness 구조·credential 격리); **live 안전 메시 이연** | verify list 17항목 중 ~6 구조 Realize·~4 provisional stand-in·~7 deferred(§4.1 전수표). live 항목(Safety Authority/Live Scope/Envelope/Deviation/Incident/Monitoring)은 런타임 미착지 + 비-live | 부분 실현을 완전 안전으로 과청구 → §4.1 정직표·§10 not-slice-1 |
| **E3** | G5 수량/가격 파생 (§3.1) | **Order Construction이 결정론·유계·무-수선 규칙으로 파생** → ioc `compile_command` declare-and-verify로 봉인 | Proposal 수치 0(proposal.py:74-76). ioc는 값을 파생 안 하고 **검증**만(compile_command declare-and-verify·records.py:14 "injected") | 실 sizing 규칙·가격 값은 D-E2(가격 표면)·P0-1(sizing bound) 이연 → provisional 배선·§3.1 봉인 |
| **E4** | quirk 구조 봉인 (§5.4·§13) | **어댑터/게이트 계약에서 blind-retry·credential 편재·조용한 폴백을 표현 불가능하게** | brokercap `same_order_retry_allowed`(VERIFIED일 때만 True·KIS는 UNKNOWN→False)·`uncertain_send_policy`(구조적 all-restrictive)·egress `credential_route_authority_disjoint`·ioc `no_silent_widening` | 기존 executor.py 결함(Q-IDEMP-1/2·Q-MIC-3) 재유입 → 계약이 구조적으로 차단·§13 전수 매핑 |
| **E5** | 패키지 2분할 (§0.1·§11.1) | **egressgw(순수 강제/구성) + brokeradapter(transport 경계)** | RFC-002 §10.8 — 게이트=final enforcement point·어댑터=브로커-특정 격리. firewall이 network를 어댑터 경계 뒤로 밀어냄 | Order Construction을 별도 3번째 패키지로? → YAGNI + 게이트의 actual-outbound 검증과 밀결합이라 egressgw 내부 모듈(§11.1 대안) |

- **경계·provisional 정책(핵심)**: D-E4는 D-E1의 `Transmit` slot에 **Broker Egress Gateway**(egressgw)를 주입한다.
  게이트는 step 15(verify)·16(provisional SEND_STARTED)·17(POTENTIALLY_LIVE 권위측)을 실행한 뒤 step 18(network
  call)을 **주입 Broker Adapter transport**(brokeradapter)에 위임하고 step 19(evidence)를 기록한다. 슬라이스에서
  transport는 **합성 paper 대역**(네트워크 0)이다. 실 currentness 사실·QCC quorum·byte 재구성·실 credential
  inventory는 provisional 또는 이연이므로 **어떤 currentness/single-use/credential EV도 닫지 못한다**(§1.1).

### 0.5 anti-phantom 규율 (FD #27 §0.5·D-E1 §0.5 상속 — 부재 주장·존재 주장 양방향 grep)

- 본 문서의 **모든 file:line 인용은 2026-07-29 자체 grep/read 실측값**이다. 스펙/코드 개정 시 행 이동 — 재사용 시
  재실측.
- **부재 주장 negative-grep 병기**: (1) `tos.egressgw`/`tos.brokeradapter` 충돌 부재 — `ls -d tos/src/tos/*/ |
  grep -iE 'egressgw|brokeradapter|adapter|gateway|construct'` → **매칭 0**(§11.1). (2) 두 패키지가 firewall 배제
  목록 미예약 — `grep -rniE 'tos\.egressgw|tos\.brokeradapter|"egressgw"|"brokeradapter"' tos/src/tos/*/__init__.py`
  → **0**. (3) tos/ 안 네트워크 부재 — 두 신규 패키지 어느 소스도 network stdlib 미참조(§0.3 canary·구현 시 강제).
- **존재 주장 실측 확인**(SIR #28 교훈 — 미검증 존재 주장이 대칭 사각): 인용한 소비 심볼은 전부 export/시그니처
  read로 확인 — ioc `compile_command`(predicates.py:185)·`command_conforms`(:96)·`no_silent_widening`(:427)·
  `economic_effect_dominated`(:379)·`mutation_fence_holds`(:492) · egress `capability_and_permit_single_use`(:292)·
  `exact_binding_holds`(:337)·`credential_route_authority_disjoint`(:405)·`monotonic_denial_no_revival`(:519) ·
  cur `proof_admissible`(:467)·`proof_structurally_complete`(:438)·`unknown_preserves_capacity`(:593)·
  `broker_reachable_not_authority`(:706) · brokercap `capability_admissible`(:118)·`same_order_retry_allowed`(:377)·
  `uncertain_send_policy`(:349)·`environment_binding_ok`(:644) · engine `Transmit`(sequencer.py:104)·`SendHandoff`
  (records.py:373)·`EgressResultPayload`(records.py:173)·`egress_currentness_verdict`(adapters.py:455)·
  `SEND_BOUNDARY_STEPS`(vocabulary.py:218)·`StageAuthorityClass.DEFERRED_SEND_BOUNDARY`(vocabulary.py:306).

---

## 1. 범위 + provisional 선언 + 조항 하중 지도

### 1.1 provisional 선언 — 왜 send 슬라이스가 EV를 닫지 못하는가 (정직 스코프)

D-E1 §1.1의 세 사유(G2 canonicalization·P0-1/P0-3·권위 런타임 부재)를 **상속**하고, send 경계 고유의 세 사유를
**추가**한다:

1. **슬라이스의 "send"는 실 브로커 도달이 아니다(§2 판정).** 합성 paper transport는 네트워크·자격증명·경로를 갖지
   않으므로 ADR-002-013 §1의 Final Egress Trust Boundary("usable authority to make a broker accept … and a
   broker-order route")를 **성립시키지 않는다** — 실 currentness·QCC·single-use의 집행 대상 자체가 부재. ⇒ 이 축의
   INV(EGRESS-INV·CUR-INV)를 실증하지 못하고 EV를 닫을 수 없다.
2. **P0-2 미결(승인된 Profile 부재).** register §1:50 — `broker_capability_profiles: []`·템플릿만 실재. KIS 초안은
   `status: DRAFT`·`approved_by: []`. brokercap `environment_binding_ok`이 소비할 승인된 INSTANCE가 없으므로
   send 경계의 broker 사실은 전부 provisional.
3. **VERIFIED 0 → live admissibility 구조적 PROHIBITED.** KIS 초안 17차원 전부 `DOCUMENTED_NOT_VERIFIED`(8)/
   `UNKNOWN`(9)·VERIFIED 0(초안 §3.1:93,100). `capability_admissible`(predicates.py:118)은 "every required
   dimension authorizes"일 때만 ADMISSIBLE(:131-134·:194-198)이므로 KIS에 대해 어떤 action class도 **PROHIBITED**
   (초안 §3.1:100-101 실측). ⇒ 실 live send는 게이트가 fail-closed로 거부할 것이고, 슬라이스는 **비-live-test
   합성 경로**만 정직하게 실행 가능.

⇒ send 슬라이스의 가치는 **구조·좌표 술어 배선의 기계 실증**(19-step 시퀀서가 실제 send 경계 계약을 받는 첫 실증)
이지 currentness/QCC/single-use/credential-격리 acceptance가 아니다. **닫는 EV = 0. 정식 수용은 §10 게이트 완료 후.**

### 1.2 조항 하중 지도 (규범 → D-E4 Realize / Defer·자체 실측)

| 원천 | Realize (D-E4 하중) | Defer (명시 이연) |
|---|---|---|
| **RFC-002 §10.8** Broker Egress Gateway | :730-737 책임(serialize/sign under outbound-comparison·transmit·ack/fill 수신·evidence non-authoritative)·:741-759 verify list 구조 항목·:761 "reject … missing/stale/conflicting/unverifiable"·:763 no general-purpose live method to backtest | :767 out-of-band containment(live scope — 비-live 슬라이스 이연·§9)·:765 versioned Profile(P0-2) |
| **ADR-002-002 §11.4** Send Boundary | :605 step 15 verify·:607 step 17 POTENTIALLY_LIVE(권위측)·:609 step 19 evidence·:611 crash=possibly-live | :606 step 16 실 RCL-owned atomic claim/consume(provisional)·:608 step 18 실 network(합성) |
| **RFC-005 §7** Approved-Intent Path | :211-213 no invent/default/normalize/round/repair·**Broker Adapter owns actual-outbound comparison**·:207-208 ADR-002-020 owns construction | §8 slicing(단일 주문·불요) |
| **RFC-005 §11** SAFE-021 | :322-323 missing-ack ≠ not-accepted·:326-328 UNKNOWN worst-credible never-silently-retried·retry=new send·:335-337 POTENTIALLY_LIVE+crash possibly-live·:338-339 partial as partial | :331-334 ADR-002-022 action-flow budget/retry-storm(afg 런타임 이연) |
| **RFC-005 §12** 실행 경계 | :356 item3 no construct/invent/repair·:358 item4 no reuse capability/no route outside gateway·:360 item5 no bypass currentness·:362 item6 no blind-retry UNKNOWN | :364-373 item7-11(aggregate/AFG budget/venue assert/protective/TCA — 각 소유 stage) |
| **ADR-002-013 §1** Final Egress Trust Boundary | 좌표등가(`exact_binding_holds`)·single-use(`capability_and_permit_single_use`)·credential 격리 술어(`credential_route_authority_disjoint`)·monotonic deny latch(`monotonic_denial_no_revival`) | QCC quorum 런타임·byte 재구성·route confinement·실 credential inventory 열거(EGRESS-EV +Security L2+·§4.4) |
| **ADR-002-020** ioc 구성 | `compile_command`(:185 declare-and-verify)·`command_conforms`(:96)·`economic_effect_dominated`(:379)·`no_silent_widening`(:427)·`numerical_safety`(:335)·`mutation_fence_holds`(:492) | 프로덕션 canonicalizer(G2·`EVL1ProvisionalCanonicalizer`만) |
| **ADR-002-004** brokercap | `environment_binding_ok`(:644 non-live-test 바인딩)·`same_order_retry_allowed`(:377)·`uncertain_send_policy`(:349)·`capability_admissible`(:118) | 승인된 Profile INSTANCE 값(P0-2)·측정 프로브 12건(초안 §5) |

### 1.3 send 경계 step 15-19 — 규범 원문 + 슬라이스 도달성 (본 게이트의 척추)

**ADR-002-002 §11.4 (:603-611) 원문 실측**:

| step | 규범 원문(요지) | 소유 | 슬라이스 #1 실현 |
|---|---|---|---|
| **15** (:605) | Broker Adapter가 **모든 바인딩 검증**(capability·command·proof·economic-effect·economic/action-flow capacity·venue·permit·cause-lineage·actual-outbound) | Broker Egress Gateway(egressgw) | **구조 Realize**(§4.1 verify list 매핑 — 구조 술어까지·live 메시 이연) |
| **16** (:606) | Broker Adapter가 **RCL-owned atomic Permit claim/consume-or-quarantine** 요청 + capability claim + **`SEND_STARTED` durable**(외부 호출 전)·**어댑터는 budget 직접 mutate 안 함** | Gateway 요청 → RCL 소유 transition | **provisional**(실 RCL 이연·SEND_STARTED durable=provisional sink·§4.6) |
| **17** (:607) | Reservation → `POTENTIALLY_LIVE` | RCL 상태(권위) / D-E1 projection | **projection은 D-E1 `mark_potentially_live`(sequencer.py:531 — 호출 전)**·권위 transition은 RCL 이연(§4.6) |
| **18** (:608) | Broker Adapter가 **network call** 수행 | Broker Adapter(brokeradapter) | **합성 paper transport**(네트워크 0·§2·§5.2) |
| **19** (:609) | Response/ack/error/timeout을 **evidence 기록** | Gateway/Adapter | **provisional sink**(§4.6)·결과는 `EGRESS_RESULT` 재주입(§5.3) |
| crash note (:611) | SEND_STARTED 후~broker 수신 전 크래시는 **의도적으로 potentially-live 취급**(중복 경제효과 대신 보수적 capacity retention) | — | D-E1 §4.4 retention + §6 send측 절반 |

**정직 귀결**: D-E4가 슬라이스에서 실 코드로 **집행**하는 것은 step 15의 **구조·좌표 verify**(conformance·좌표등가·
single-use·currentness 구조·credential 격리 술어)와 step 18-19의 **합성 transport + provisional evidence**뿐이다.
step 16의 실 RCL atomic claim·SEND_STARTED durable, step 17의 권위 transition, step 15의 live 안전 메시는 provisional
또는 이연이다. 이 구조가 §1.1 "닫는 EV 0"을 강제한다.

---

## 2. E1 — 슬라이스 send 경계 판정 (본 문서 최대 하중 판정)

**문제**: "paper 주문 1건의 send"가 무엇인가 — (a) **합성 paper transport**(네트워크 0·D-E3 백테스트 fill과 구조
공유) vs (b) **실 KIS 모의투자 API 호출**? 서베이 §1:89("paper 주문 1건 = `environment: non-live-test`·모의 계좌
송신 1건")는 (b)를 시사하는 듯 보이나, 구조 사실(**브로커-도달/합성** 축)을 실측하면 슬라이스 실행 대상은 (a)여야
정직하다.

### 2.1 판정: 슬라이스 실행은 합성 paper transport. 실 KIS 경로는 설계하되 실행 이연 (단계 분리)

- **실 KIS 모의투자 API 경로를 설계한다**: `tos.brokeradapter`의 **Transport Protocol**(추상 경계)·게이트의 verify
  계약·ADR-002-013 자격증명/경로 격리 규율(§4.5)·brokercap non-live-test 바인딩(§4.7) — 전부 실 경로가 나중에
  붙을 수 있도록 계약으로 확정.
- **슬라이스 실행은 합성 paper transport다**: `tos.brokeradapter`가 제공하는 **synthetic paper transport**(네트워크
  0·자격증명 0·경로 0)를 D-E1 `Transmit` slot에 주입. 결과(ack/fill/reject/timeout)는 **결정론 paper fill 대역**이
  생성해 `EGRESS_RESULT`로 재주입(§5.2·§5.3). 이 대역은 **D-E3 백테스트 fill 모델과 구조를 공유**(같은 Transport
  Protocol·다른 주입 — D-E1 §12-3 패리티).

### 2.2 근거 — 옵션(b) 실 KIS 모의 경로의 구조 차단 (축: **브로커-도달/합성**, live/비-live 아님)

**⚠ 축 정정(v1.1·MAJOR-1)**: 옵션(b)[실 KIS 모의]는 **비-live**(paper)이므로 live-축 게이트(`capability_admissible`·
Live-Armer)가 **차단하지 않는다** — 비-live는 §4.7이 `environment_binding_ok`(predicates.py:644-672 — profile·
VERIFIED **무관**·환경 좌표 동등성만·BC-INV-009:653)로 라우팅한다. 옵션(b)의 진짜 구조 차단은 **broker-resource-consuming
축**이다. 두 층이 옵션(b) **실행**을 차단하고(①+②), live-축 두 층(③④)은 별개 live 경로 도달불가를 확인하는 방어심층이다.

**옵션(b) 실행 차단 (2층·firewall이 위치를 한정하고 verify가 실행을 막음)**:
1. **① firewall(구조·위치-한정·설계 #1 §2.3).** 실 KIS API 호출은 network stdlib·자격증명을 요구하는데 tos/는 이를
   금지한다. ⇒ **실 transport 구현은 필연적으로 tos/ 밖**(shared/kis 또는 미래 런타임)이라 tos 슬라이스 산출물이 될
   수 없다. **단, firewall만으로는 tos/ 밖 주입 transport의 호출까지 막지 못한다**(D-E1 `Transmit`은 주입 인터페이스)
   — firewall은 위치 한정이고 실행 차단은 ②가 소유.
2. **② broker-resource-consuming verify → fail-closed(충분 차단·정직 이연).** 실 모의 API 호출은 모의 서버에 모의
   주문을 생성하는 **broker-resource-consuming** transmission이다. RFC-002 §10.8:741 — "Before any risk-relevant
   **or broker-resource-consuming** transmission, it SHALL verify"(트리거는 broker-consuming이지 **live/비-live 아님**)
   ⇒ 17항목 전수 verify 대상. 그런데 §4.1 Deferred 안전 메시(항목 4·7·8·9·10)는 **런타임 미착지**이고 P0-2 미승인
   프로파일(register §1:50 `broker_capability_profiles: []`·§10.8:765)이라 broker 사실이 **unverifiable** →
   RFC-002 §10.8:761 "SHALL reject the request when any required fact is missing, stale, conflicting, or
   **unverifiable**." ⇒ 게이트가 실 모의 send를 **fail-closed로 거부**. 이것이 옵션(b) 실행을 막는 충분 조건.

**방어심층 (별개 live 경로 도달불가 확인·옵션(b)의 판별자 아님·orthogonal live 축)**:
3. **③ VERIFIED 0 → live PROHIBITED.** `capability_admissible`(predicates.py:118)은 KIS에 대해 PROHIBITED(VERIFIED
   0). ⚠ 이는 **live 검사**이지 비-live 옵션(b)의 판별자가 아니다 — 비-live paper는 `environment_binding_ok` 경로다.
   (③이 비-live를 gate한다면 동일 profile·VERIFIED 0인 합성 경로도 gate되어 §4.7과 자기모순 — 그래서 ③은 live-축
   전용.) ③은 **어떤 live send도 도달 불가**임을 확인하는 orthogonal 방어심층.
4. **④ Live-Armer 미지정.** live authorization 부재(서베이 §1:98·role-scheme :20 fail-closed·GOV-001 제3행위). 역시
   **live-축 전용** 방어심층.

⇒ **옵션(b)[실 모의] 실행은 ①+②로 차단**(broker-consuming 축)되고, live-축 ③④는 별개 live 경로 도달불가를 확인한다.
**옵션(a)[합성 transport]는 non-broker-resource-consuming**(네트워크·경로 0)이라 §10.8:741 verify 트리거의 대상이
아니고, §4.2 broker-applicability 술어가 이를 **양성 확인 후 N/A**로 통과시킨다 — 슬라이스가 정직하게 실행 가능한
경로다. 합성은 우회가 아니라 **broker-consuming 축의 반대편**(비-broker)이다.

### 2.3 "모의투자 = non-live"의 정직한 지위 (비-live-test ≠ 안전 면제)

`environment: non-live-test`(register §3:88 — 유일 확정 scope 값)는 **실 자본 위험이 없음**을 뜻하지 **안전 요건
면제**를 뜻하지 않는다. 실 KIS 모의투자 서버 호출조차 **broker-resource-consuming external transmission**(모의
서버에 모의 주문 생성)이므로 RFC-002 §10.8:739 "Before any risk-relevant **or broker-resource-consuming**
transmission, it SHALL verify …"의 적용을 받는다 — 즉 실 모의 API 호출도 verify list를 통과해야 한다. 이것이
**실 모의 API 경로를 (b)로 슬라이스에서 실행하지 않는 추가 이유**: verify list의 broker 사실(brokercap)이 P0-2
미결로 provisional이라 실 모의 송신조차 게이트를 정식 통과할 수 없다. 합성 transport는 이 긴장을 정직하게 해소
— 게이트 계약은 완전히 실행하되(구조 술어), transport만 네트워크 0으로 대역.

### 2.4 검토·기각 대안

- **(A) 슬라이스에서 실 KIS 모의 API 직접 호출(tos/ 안에 network 배선)** — **기각**: firewall 정면 위반(설계 #1
  §2.3). tos.brokeradapter에 socket/http를 넣으면 §0.3 network canary가 실패. 커널 순수성 파괴.
- **(B) 실 transport를 tos/ 밖(shared/kis)에 두고 슬라이스에서 주입 호출** — **부분 채택하되 실행 이연**: 이것이 실
  경로의 **설계**다(Transport Protocol이 정확히 이 주입점). 그러나 슬라이스 **실행**은 (1) P0-2 미결·(2) VERIFIED
  0·(3) Live-Armer 미지정으로 정식 통과 불가 → 실행은 합성 대역, 실 대역 배선은 P0-2 종결 후. 단계 분리.
- **(C) send 경계를 슬라이스에서 완전 생략(decision→기록만)** — **기각**: RFC-005 §6 "every child order runs the
  full machinery"·D-E1 시퀀서가 `transmit is None`이면 `TRANSMIT_UNAVAILABLE`로 halt(sequencer.py:515-526 —
  "an absent send boundary is not a licence to skip it"). 생략은 send 경계 배선 실증(슬라이스의 유일 가치)을 무효화.
- **(D) 합성 transport가 아니라 "실 send를 mock 처리"(unittest.mock)** — **기각**: mock은 계약을 실증하지 않고
  숨긴다. 합성 transport는 **명시적 Transport Protocol 구현**(정직한 대역)이라 계약 표면이 드러나고 D-E3와 공유
  가능. mock은 over-realization(EGRESS #22 교훈)의 전형.

---

## 3. Order Construction (tos.egressgw::construction) — step 2·5·11

### 3.1 E3 — G5 수량/가격 파생 seam (결정론·유계·무-수선)

**문제(스파이크 G5)**: `Proposal`에 수치 필드 전무 — `quantity_basis: str | None`(proposal.py:128)뿐, 수량·지정가
없음("evidence, never capacity"·proposal.py:74-76). 반면 ioc `compile_command`(predicates.py:185)는 값을 **파생하지
않고** `ApprovedIntentContract`의 axis binding에 **이미 실린** 값을 declare-and-verify한다(records.py:14 "Every
multiplier / price scale / quantity / limit is an **injected** value"·:246-256 각 축 authorized==intent 검증·
불일치는 denial). ⇒ **Proposal↔ApprovedIntentContract 사이에 수량/가격을 파생하는 단계가 무주인**이고, 그것이
Order Construction(step 2 candidate command construction)의 소유다.

**판정: Order Construction이 수량/가격을 결정론·유계·무-수선 규칙으로 파생하고, ioc `compile_command`가 봉인한다.**

**Decision↔Construction 수량 분업(v1.1·MINOR-2·RFC-002 §10.2:617 화해)**: §10.2:617 — Decision Service는 "intended
account, instrument, direction, **quantity**, and constraints"를 **식별**한다. 즉 Decision은 **추상 수량 의도**(DSL
Proposal의 `quantity_basis` — "risk budget에 맞춰 sizing"류 basis)를 식별하고, **구체 수량 렌더는 Order Construction**이
ADR-002-002 §11.1:583 "proposed Authorized Construction Envelope 하 결정론적 candidate Canonical Broker Command
구성"으로 수행하며, **step 4 Independent Approval이 그 candidate를 exact-unchanged로 검증·승인**(§11.1:585). ⇒
**결정=추상 basis · 구성=결정론 구체화 · 승인=검증**의 3분업(DSL Proposal 수치 0[proposal.py:74-76]은 이 추상성의
표현이지 수량 부재가 아니다).

**⚠ sizing bound = Authorized Construction Envelope 봉입(v1.1·MINOR-3)**: 파생의 유계성(risk budget·per-unit·lot
정책)은 **proposed Authorized Construction Envelope에 봉입**한다(RFC-002 §9.1:553 "Order Construction Policy
governance supplies rules"가 envelope/policy 공급). ⇒ step-2 construction은 **순수 (proposal, envelope) 함수**가
되고 ioc `compile_command`(intent==authorized 강제·:246-256)가 envelope 대조로 봉인. **값은 P0-1 이연·바인딩 구조
(sizing의 envelope 봉입)는 지금 확정** — 저작자가 config로 임의 수량을 주입하는 우회를 구조로 차단.

- **파생 입력(전부 명시)**: (i) Proposal의 `quantity_basis`(예: `"RISK"` — 수량이 아니라 **근거**), (ii) **proposed
  Authorized Construction Envelope 봉입** sizing bound(risk budget·per-unit·lot 정책·§9.1:553 governance 공급·
  MINOR-3), (iii) **admitted Critical Input 가격**(capsule/Snapshot 관측·D-E2 값 표면), (iv) venue/brokercap의 수량
  제약(lot size·max quantity). 파생 규칙은 **주입 유계 함수**(예: `floor(risk_budget / per_unit_risk)` — 단, 반올림은
  **명시적 lot 정책**을 따르고 임의 round 금지).
- **무-수선 규율(RFC-005 §7:211-213·§12:356 item3)**: "SHALL NOT invent, default, normalize, round, or repair any
  broker-command field." ⇒ 파생은 (a) 미지 입력에 default 금지(가격 UNKNOWN이면 파생 실패·no-send), (b) 임의
  round/normalize 금지(lot 정책은 저작 상수로 명시·"조용한 폴백" 금지 — Q-MIC-3 executor.py:785-795 재생산 금지),
  (c) 결과가 envelope 밖이면 repair가 아니라 **denial**(ioc `compile_command` :252-255 "outside authorized
  envelope — denial"). ioc `no_silent_widening`(predicates.py:427)·`numerical_safety`(:335)가 봉인.
- **결정론(IOC-INV-002·predicates.py:196-197)**: 동일 (basis, config, 가격, 제약) → 동일 canonical command·digest.
  D-E1 §4.3 content-addressed 규율 정합. 파생에 wall-clock·RNG 금지.
- **구조 파생 > 자기신고**: 파생 수량은 Proposal이 "선언"하는 게 아니라 입력에서 **계산**되고, ioc가 envelope
  대조로 검증. 저작자가 임의 수량을 주입할 경로 없음(compile_command가 intent==authorized 강제).

**⚠ provisional 봉인(D-E2/P0-1 이연)**: (1) **가격 값 표면은 D-E2 소유**(D-E1 §3.2 — 시장값은 admitted Critical
Input observation으로 `"capsule"` 소스로만·config 재라벨링 금지). D-E2 미착지 시 파생 입력 가격이 provisional. (2)
**sizing bound는 P0-1 미승인**(risk budget·per-unit·lot 정책 — register §3 확정값 아님). ⇒ 슬라이스는 provisional
sizing 값으로 배선·산출 provisional. D-E4는 **파생 seam 계약**(무엇이 흐르고 무엇이 금지인가)만 확정하고 값·bound는
이연.

- **검토·기각 대안**: (A) Order Construction이 수량을 **자기신고**(Proposal에 수량 필드 추가) — 기각: proposal.py
  구조 변경(dsl 재저작·G5 판정 위반)·"evidence, never capacity" 원칙 훼손. (B) 수량 파생을 D-E1 결정 파이프라인에
  넣음 — 기각: 결정(RFC-003·RFC-002 §10.2:617)은 **추상 수량 의도(basis)** 식별이고 **구체 수량 렌더는 실행측
  구성**(ADR-002-020·ADR-002-002 §11.1:583)이 소유(RFC-002 §9.1:553 Order Construction). (C) 미지 가격에 last-known
  default — 기각: RFC-005 §7:211 default 금지·"조용한 폴백"이 정확히
  Q-MIC-3 결함.

### 3.2 ioc를 Stage Protocol로 래핑 (step 2·5·11)

Order Construction은 D-E1 `Stage` Protocol(sequencer.py:88-100 — `(StageRequest) -> StageVerdict`)의 구현을 step 2·
5·11에 제공한다. **기구현 ioc 순수 술어 + D-E1 기구현 어댑터를 재사용**(재저작 0):

| step | Order Construction 행위 | 소비 ioc | StageVerdict 래핑 |
|---|---|---|---|
| **2** CANDIDATE_COMMAND_CONSTRUCTION | §3.1 수량 파생 → `ApprovedIntentContract`/`AuthorizedConstructionEnvelope` 구성 → `compile_command`(:185) → `CanonicalBrokerCommand` | `compile_command`·`command_conforms`(:96) | **신규 얇은 어댑터**(command 존재·CONFORMANT positive 게이트·D-E1 `conformance_proof_verdict` 패턴 동형) |
| **5** ECONOMIC_EFFECT_ENVELOPE | conservative `EconomicEffectEnvelope` 도출(=rcl `CapacityVector`) → `economic_effect_dominated`(:379) | `EconomicEffectEnvelope`·`economic_effect_dominated` | **D-E1 `economic_effect_envelope_verdict` 재사용**(adapters.py:353 — ∅ envelope→UNKNOWN·magnitude None→UNKNOWN) |
| **11** ORDER_CONFORMANCE_PROOF | `OrderConformanceProof` 생성(unchanged intent+command+venue+envelope+RCL dominance 바인딩) → `command_conforms`·`mutation_fence_holds`(:492) | `OrderConformanceProof`·`command_conforms`·`mutation_fence_holds` | **D-E1 `conformance_proof_verdict` 재사용**(adapters.py:145 — CONFORMANT만 admit·UNKNOWN=denial) |

- **positive-admit 재사용**: D-E1 어댑터(adapters.py)가 이미 `result is CONFORMANT`/`ADMISSIBLE` positive 게이트·
  `None`→UNKNOWN·`RESTRICTED_PROTECTIVE_ONLY`→DENY(§4.2)를 강제하므로 D-E4는 **native result만 생산**하고 래핑은
  재사용. step 2 candidate는 D-E1에 전용 어댑터 부재(ioc `compile_command` 결과=command 존재 여부)이므로 **얇은
  신규 어댑터**(§3.2 표) — CONFORMANT 패턴 동형.
- **venue(step 3·MINOR-4)**: `session_phase_admits`/`order_shape_admissible`(venue) 순수 available. **step-3 venue
  Stage = tos.venue 술어 위 non-authorizing thin adapter**(RFC-002 §9.1:554 "Venue Constraint Gate produces a
  non-authorizing decision")로 D-E1 `venue_admissibility_verdict`(adapters.py:82) 재사용. 이는 **step-15 item-11의
  게이트 enforcement와 별개 역할**이다 — step-3은 non-authorizing decision **생산**, step-15는 게이트가 "the exact
  current result를 enforce"(§9.1:554)로 그 결과를 **최종 강제**(§4.1 item 11). SessionPhase는 주입 opaque token(KIS
  세션시각은 Profile INSTANCE·D-E2).

### 3.3 Coordinator 무권위 상속 (Order Construction SHALL NOT)

RFC-002 §9.1:553 — "Order Construction Service SHALL NOT approve, mutate capacity, classify protection, issue
authority, transmit, or arm live scope." ⇒ Order Construction stage는 **candidate·envelope·proof 생성만**·전부
non-authorizing(ioc `construction_grants_no_authority`·all-false authority block). 승인은 step 4(iap)·capacity는
step 8-10(RCL)·transmit은 step 18(adapter)이 소유.

---

## 4. Broker Egress Gateway (tos.egressgw::gateway) — step 15 verify + 16-17

게이트는 D-E1 `Transmit` slot(sequencer.py:104-116)에 주입되는 **Broker Egress Gateway**다. `(AttemptRequest) ->
SendHandoff`를 충족하고, 내부에서 step 15(verify)·16(provisional claim+SEND_STARTED)·17(권위측 표기)·18(adapter
위임)·19(evidence)를 실행한다.

### 4.1 step 15 verify list — RFC-002 §10.8 17항목 전수 매핑 (Realize / Provisional / Deferred)

RFC-002 §10.8:741-759 verify list를 전수 매핑한다(§0.5 anti-phantom — 17항목 grep 실측). **분류 규율**: Realize=
슬라이스에서 shipped 순수 술어로 구조 검증 가능·Provisional=stand-in verdict(권위 없음·D-E1 §4.4)·**Deferred=런타임
미착지·broker-applicability 조건부**(§4.2 — broker-resource-consuming/risk-relevant-live면 required→UNKNOWN→deny·
**양성확인된 합성·non-broker·non-live-test scope에서만 N/A**·조용한 skip 아님).

| # | verify 항목(:741-759) | 분류 | 소비/사유 |
|---|---|---|---|
| 1 | valid and unused Transmission Capability | **Realize(구조)** | egress `capability_and_permit_single_use`(:292)·engine `transmission_capability_verdict`(adapters.py:417)·발급은 provisional(RCL stand-in) |
| 2 | matching intent and reservation identities | **Realize(구조)** | engine `AttemptRequest`(records.py:317 — proof digest+permit identity 바인딩)·`ProvisionalReservation.attempt_id`(records.py:406) 정합 |
| 3 | current commitment epoch | Provisional | RCL stand-in(D-E1 §4.4)·실 epoch fencing 이연 |
| 4 | current Safety Authority epoch **or** valid degraded protective lease | **Deferred(applic.)** | Safety Authority 런타임(RFC-002 §10.11) 미착지·broker-applicability 조건부(§4.2 — broker-consuming/live시 required→deny) |
| 5 | valid live scope | **Deferred(applic.)** | Live Authorization(§10.13) 미착지·broker-applicability 조건부(§4.2)·양성확인된 합성·**non-broker-reached** scope에서 N/A(§4.7 — 근거는 "no-broker-reached", live-arming 아님) |
| 6 | allowed account/instrument/action class/**maximum quantity** | Provisional | brokercap `capability_admissible`(:118)=PROHIBITED(VERIFIED 0)·비-live는 `environment_binding_ok`(§4.7)·max quantity는 §3.1 파생 유계 |
| 7 | Hard Safety Envelope + Runtime Safety Profile versions | **Deferred** | 런타임 미착지 |
| 8 | Safety Deviation(policy/generation/active set/scope/invalidation) | **Deferred** | wdr 커널 predicate-only·런타임 이연 |
| 9 | Safety Incident(policy/generation/active set/scope/restriction) | **Deferred** | sir 커널·런타임 이연 |
| 10 | Safety Monitoring(policy/generation/telemetry/coverage/gaps/disposition) | **Deferred** | stm 커널·런타임 이연 |
| 11 | Venue Constraint Snapshot + Order Admissibility Decision 바인딩 | **Realize** | venue `session_phase_admits`/`order_shape_admissible`·engine `venue_admissibility_verdict`(adapters.py:82)·게이트 enforce |
| 12 | venue/session/halt/tradability/account/margin/settlement/**broker-constraint generation** | Provisional | venue 일부 Realize·broker-constraint generation은 Profile(P0-2) provisional |
| 13 | Order Construction(policy/generation/envelope/**Canonical Broker Command**/**Conformance Proof**/**Economic Effect Envelope**) | **Realize** | §3 ioc `compile_command`/`command_conforms`/`OrderConformanceProof`/`EconomicEffectEnvelope` |
| 14 | Trading Approval(policy/generation/request/decision/consumption/**Intent binding**) | Provisional | iap 승인 stand-in(D-E1 §4.4)·실 독립 승인자 부재 |
| 15 | Action Flow(policy/generation/decision/RCL commitment/**Permit**) | Provisional | afg stand-in·engine `action_flow_permit_verdict`(adapters.py:313)·실 Governor 이연 |
| 16 | Currentness(policy/**Safety Currentness Vector**/Restrictive Fence/**Latch CLEAR**/**Egress Currentness Proof**) | **Realize(구조)** | cur `proof_admissible`(:467)·`proof_structurally_complete`(:438)·engine `egress_currentness_verdict`(adapters.py:455)·egress `monotonic_denial_no_revival`(:519 latch)·**사실(owner submission)은 provisional/D-E2** |
| 17 | conformance of **actual outbound representation** to command + authorized economic effect | **Realize(좌표등가)** | egress `exact_binding_holds`(:337 좌표등가+ioc CONFORMANT)·**byte 재구성은 +Security 이연**(§4.4) |

**집계(전수·17 항목)**: **Realize(구조/좌표) 6**(1·2·11·13·16·17) · **Provisional stand-in 5**(3·6·12·14·15) ·
**Deferred 6**(4·5·7·8·9·10). 합 6+5+6 = **17 전수**(항목 6은 brokercap stand-in이라 Provisional 계상).

**정직 귀결(핵심)**: 17항목 중 D-E4가 실 술어로 **구조 검증**하는 것은 6항목(conformance·좌표등가·single-use·
currentness 구조·venue·attempt/reservation 정합)뿐이고, 나머지 11항목은 provisional stand-in(5)이거나 **broker-consuming
안전 거버넌스 메시**(6·Deferred)다. Deferred 6항목(Safety Authority·Live Scope·Envelope·Deviation·Incident·Monitoring)은
**broker-resource-consuming/risk-relevant-live send를 지키는 항목**이고 런타임 미착지다. §4.2 broker-applicability
양성 게이트가 이를 봉인 — **broker-consuming/live면 required→UNKNOWN→deny**(RFC-002 §10.8:741 트리거→:761 unverifiable
reject)·**양성확인된 합성·non-broker-reached·non-live-test scope면 N/A로 양성 통과**(조용한 skip 아님). ⇒ 게이트의
step 15 verify는 **구조 술어를 완전 실행**하고 broker-consuming 메시를 broker-applicability로 봉인하되, **어떤 currentness/
QCC/single-use/credential-격리 acceptance도 주장하지 않는다**(합성은 실 브로커 미도달·§1.1) — §1.1 "닫는 EV 0"의 구조적
이유. 실 모의(broker-consuming) send라면 §10.8:741 트리거로 미착지 메시가 unverifiable → fail-closed 거부(합성 경로만 통과).

### 4.2 fail-closed 배선 (positive-admit·D-E1 §4.2 상속)

게이트의 verify는 D-E1 시퀀서 fail-closed 규율(sequencer.py:1-38)을 **step 15 내부로 확장**한다:

- **⚠ broker-applicability 양성 게이트(v1.1·MAJOR-2 — §4.1 Deferred 메시의 봉인·먼저 실행)**: 안전-메시 항목
  (4·5·7·8·9·10)은 **조용히 skip하면 fail-open**이고 **무조건 deny하면 합성 경로까지 차단(§2.1 모순)**이다. 게이트는
  per-item positive-admit **전에** send의 broker-applicability를 **양성 확립**한다: (i) transport가 브로커에 **실도달**
  (broker-resource-consuming) **또는** (ii) **risk-relevant-live scope**면 이 항목들은 **required** → 런타임 미착지 →
  **UNKNOWN → deny**(fail-closed·RFC-002 §10.8:741 트리거→:761 unverifiable). (iii) **양성확인된 합성·
  non-broker-resource-consuming·non-live-test scope**에서만 **N/A로 양성 통과**(∅ 양방향 — explicit N/A는 조용한 skip이
  아니라 **기록되는 양성 판정**). **양성 확립은 구조적**: 합성 transport는 Final Egress Trust Boundary(credential+route·
  ADR-002-013 §1)를 **성립시키지 않으므로**(§1.1-1·§4.5) "no-broker-route-reachable"이 구조 사실이고, **미상/unknown
  transport nature는 보수적으로 broker-consuming 취급**(fail-closed·음극성 `is not False`). ⚠ 근거는 **"no-broker-reached"**
  이지 "no-live-arming"이 아니다(§4.7 정정) — 비-live 실 모의도 broker-consuming이라 이 게이트가 deny한다.
- **positive-admit 게이트**: 각 verify 항목은 **명시 positive 술어 True**(`result is CURRENT`/`is CONFORMANT`/
  single-use `is True`)일 때만 통과. `is not DENY`류 음성 게이트 금지(D-E1 §4.2 rule1). D-E1 어댑터가 이미
  `None`→UNKNOWN·positive-identity 강제(adapters.py:17-19).
- **어느 하나라도 admit 아니면 send 금지**: RFC-002 §10.8:761 미러. 게이트는 verify 실패 시 `SendHandoff
  (accepted_for_transmission=None)`(records.py:385 — positive polarity·only `is True` records accepted)로 반환하고
  transmit 안 함·중단 사유 evidence 기록. **D-E1 시퀀서는 이미 step 14까지 fail-closed**(item-7)이므로 게이트는
  step 15-19의 send측 fail-closed를 소유.
- **UNKNOWN-restrictive**: currentness/conformance UNKNOWN → send 금지(cur `unknown_preserves_capacity`:593)·
  reservation POTENTIALLY_LIVE 보수 유지. `broker_reachable_not_authority`(:706) — 브로커 도달성은 권위가 아님
  (합성 transport 정합: 도달 여부와 무관하게 currentness 없으면 send 금지).

### 4.3 send 경계 currentness (cur EgressCurrentnessProof — D-E1 선물 edge 재사용)

- D-E1이 **cur 타입 edge를 선물**했다: `egress_currentness_verdict(result: ProofResult, proof:
  EgressCurrentnessProof)`(adapters.py:455-509·`authority_class=DEFERRED_SEND_BOUNDARY`). docstring(:462-468) —
  "the D-E4 hand-off typing … the send-boundary owner consumes the **same** positive-identity gate the rest of the
  flow uses: only `CURRENT` satisfies … `CURRENT` itself grants no authority." ⇒ 게이트는 이 어댑터를 재사용해
  step 16 currentness를 verdict화.
- **cur 술어 소비**: `proof_structurally_complete`(:438)·`proof_admissible`(:467)로 `EgressCurrentnessProof` 구조
  검증. RFC-002 §10.8:758 — "one new single-use Egress Currentness Proof ordered with the capability claim and
  `SEND_STARTED`." ⇒ currentness proof는 capability claim·SEND_STARTED와 **함께 ordered**(§4.6 순서).
- **⚠ provisional**: `SafetyCurrentnessVector`의 실 owner submission(각 차원 사실)은 provisional/D-E2 의존. cur
  술어는 **구조·좌표**를 검증하되 사실의 진위는 upstream. `MANDATED_DIMENSION_FLOOR`(cur) 충족은 provisional 값.

### 4.4 single-use + 좌표등가 (egress 술어 소비·byte 재구성 이연)

- **single-use capability + permit**: egress `capability_and_permit_single_use`(:292) — 두 nonce가 THIS
  principal+request에 **정확히 한 번** claim(prior claim에 nonce 존재 시 replay/transplant → False). RFC-002
  §12:358 item4 "SHALL NOT issue, extend, or reuse a Transmission Capability." rcl `claim_capability`가 nonce
  ledger 소유(egress docstring:309-311 — egress는 **소비**·재저작 없음). 슬라이스에서 nonce 발급은 provisional(RCL
  stand-in)이나 **single-use 구조 술어는 실행**.
- **좌표등가(actual-outbound comparison)**: egress `exact_binding_holds`(:337) — 모든 egress 좌표가 authorized와
  일치(EGRESS-INV-004 :348 "No field may be substituted after validation")·request digest=capsule chain terminus·
  qcc command digest=request command digest·ioc verdict CONFORMANT. RFC-005 §7:213 "Broker Adapter owns the
  actual-outbound comparison." ⇒ 게이트는 transport가 보낼 **정확한 바이트 표현**이 authorized command와 좌표
  일치함을 검증.
- **⚠ over-realization 경계(egress docstring:356-359)**: L1 egress 술어는 **좌표등가 + ioc verdict**까지다. **실
  byte-level outbound 재구성**(§11.2 step 18)·**route confinement**(§10)·**env non-interchangeability**(§8)는
  **+Security(EGRESS-EV-003 not-Phase-1)** 이연. ⇒ D-E4 게이트는 좌표등가를 검증하되 "실제 wire 바이트가 재구성
  되어 대조됐다"고 **주장하지 않는다**(합성 transport에선 wire 자체가 합성). 이 정직 경계가 Q-WIRE-1(주식 int
  절단 vs 선물 float — executor.py:321,393) 같은 wire 비대칭의 완전 봉인이 **이연**임을 명기.

### 4.5 credential/route 격리 (ADR-002-013 Final Egress Trust Boundary·Q-CRED-1 봉인)

- **규범**: ADR-002-013 §1 — Final Egress Trust Boundary는 usable authority + broker route를 **함께** 가진 마지막
  경계. "No strategy, decision, execution-coordination … component may possess both usable live-order authority and
  a live broker-order route." "Recovery, reconnect, credential rotation … SHALL NOT automatically re-arm
  transmission."
- **술어 소비**: egress `credential_route_authority_disjoint(inventory)`(:405) — 경계 밖(또는 unknown) principal이
  usable credential + route를 **함께** 가지면 False. `inside_boundary is not True` + `usable_credential is not
  False`(True/None=potentially-usable) + `broker_route is not False` → bypass 후보. **empty inventory → False**
  (disjointness 미증명)·**None flag → conservatively potentially-usable**(음극성 규율 — `is not False`).
- **Q-CRED-1 봉인**: KIS 초안 Q-CRED-1(HIGH·초안 §5:167) — "모든 워커가 env로 raw app_key/app_secret 보유"
  (`config/kis/auth.yaml:7-8`). 이는 ADR-002-013 §1 "no component may possess both"의 **정면 위반**. D-E4 계약은
  이를 **구조적으로 배제**: (1) `tos.egressgw` 게이트·`tos.brokeradapter` transport의 tos/ 안 부분은 **자격증명을
  갖지 않는다**(firewall — credential은 tos/ 밖). (2) 실 transport(tos/ 밖)가 자격증명을 갖되 **그것이 유일한 경계**
  여야 하고 `credential_route_authority_disjoint` inventory가 그 격리를 검증. (3) 합성 transport는 자격증명 0·경로
  0이므로 격리 자명(비-live). ⇒ 기존 `shared/` 편재 자격증명 패턴을 tos 계약이 재생산하지 않는다.
- **⚠ over-realization 경계(egress docstring:419-421)**: 실 inventory 열거(hidden operational/recovery/portal/
  CI-CD/support/vendor credential·§9.1)는 **L2+ 이연**. D-E4는 **주입-inventory disjointness 술어**까지만·실
  전수 열거 이연. 이것이 Q-CRED-1 완전 봉인이 P0-2/L2+ 소관임을 명기(슬라이스는 구조 술어 + firewall).

### 4.6 step 16 — SEND_STARTED durable + claim/consume 순서 (provisional)

- **규범(ADR-002-002 §11.4:606)**: Broker Adapter가 **RCL-owned atomic Permit claim/consume-or-quarantine**
  transition을 capability claim과 함께 요청하고 **`SEND_STARTED`를 durable 기록**(외부 호출이 새 send로 재시도되기
  전)·**어댑터는 budget 직접 mutate 안 함**. RFC-002 §10.8:758 — Egress Currentness Proof는 capability claim·
  SEND_STARTED와 **ordered**(RFC-005 §12:360 item5 "claim/`SEND_STARTED`/first-byte ordering" — 순서 금지 우회
  불가).
- **슬라이스 실현(provisional)**: (1) 실 RCL atomic claim/consume은 provisional stand-in(D-E1 §4.4 — 실 linearizable
  ledger 이연). 게이트는 `capability_and_permit_single_use`로 **구조 single-use**를 확인하되 실 원자 transition은
  provisional. (2) SEND_STARTED durable은 **provisional sink**(D-E1 §5.1·완전 Evidence Store=ADR-002-016 이연) —
  durable 보장 없음. (3) **순서는 실행**: 게이트는 verify(15) → claim+SEND_STARTED 기록(16) → transport 위임(18)
  순으로 배선하고 first-byte 전에 SEND_STARTED가 기록됨을 구조적으로 보장.
- **POTENTIALLY_LIVE projection(step 17)**: D-E1 시퀀서가 **transmit 호출 전** `ledger.mark_potentially_live()`
  (sequencer.py:531)로 이미 projection을 진행(SendHandoff docstring:380-382 — "advanced *before* the call,
  mirroring §11.4 step 16"). ⇒ 게이트가 실패하거나 크래시해도 reservation은 보수적으로 POTENTIALLY_LIVE(INV-005:168·
  crash note :611). **권위 transition은 RCL 이연**·projection은 D-E1 소유·게이트는 그 사이 SEND_STARTED 기록.

### 4.7 non-live-test admissibility (brokercap·CLASS-D)

- **환경 바인딩**: brokercap `environment_binding_ok`(:644) — attempt가 `environment: non-live-test`(register §3:88)
  에 바인딩됨을 확인. 게이트는 send 전 이 바인딩을 positive 확인(합성 transport는 non-live-test로만 바인딩).
- **live admissibility는 PROHIBITED(정직)**: `capability_admissible`(:118)은 KIS에 대해 PROHIBITED(VERIFIED 0·
  §1.1-3). conformance class는 미참조(:144-146 "class cannot override a failed mandatory dimension" — CLASS-D는
  요약 라벨). ⇒ 게이트는 **live send를 admit하지 않는다**. CLASS_D_NON_LIVE(vocabulary.py:146)는
  `NON_LIVE_OR_SUPERVISED_CLASSES`(:152 — "NOT full deterministic/serialized live") 소속 = 명시적 비-live.
- **정직 귀결(v1.1 정정·MAJOR-2)**: item 5("valid live scope")의 양성-확인 근거는 **"no-broker-reached"**(§4.2
  broker-applicability)이지 "no-live-arming"이 아니다 — 비-live 실 모의도 broker-consuming이라 통과 못 한다. 게이트의
  admissibility 경로는 **양성확인된 non-broker-reached·non-live-test 합성 send만** 통과시킨다: (1) `environment_binding_ok`
  으로 non-live-test 바인딩 양성 확인, (2) §4.2로 **non-broker-reached** 양성 확인(안전-메시 N/A), (3) live는
  `capability_admissible` 구조적 PROHIBITED. 이것이 §2 판정(합성 transport)의 게이트 층 미러.

---

## 5. Broker Adapter (tos.brokeradapter) — step 18-19 transport

### 5.1 Transport Protocol 경계 (firewall seam — 네트워크는 tos/ 밖)

- **규범(RFC-002 §10.8:739)**: "Broker-specific behavior SHALL remain isolated behind the Broker Adapter
  boundary." ⇒ `tos.brokeradapter`는 **Transport Protocol**(추상 `(verified outbound) -> raw broker result`)만
  tos/ 안에 정의하고, **브로커-특정·네트워크·자격증명 구현은 경계 뒤**(tos/ 밖 주입)에 격리.
- **firewall 귀결**: tos/는 network stdlib 금지(설계 #1 §2.3). ⇒ Transport Protocol의 **실 구현은 필연적으로
  tos/ 밖**(shared/kis 대역 또는 미래 런타임). tos.brokeradapter가 담는 것은 (a) Protocol 정의, (b) **합성 paper
  transport**(순수·네트워크 0). 이 구조가 §2 판정의 firewall 근거이자 ADR-002-013 credential 격리(§4.5)의 자연
  귀결 — 자격증명은 tos/ 밖 실 transport에만.

### 5.2 합성 paper transport (슬라이스 실행·D-E3 공유 구조)

- **합성 transport**: 네트워크·자격증명·경로 0. 게이트가 넘긴 verified outbound(AttemptRequest 바인딩)를 받아
  **결정론 paper fill 대역**으로 결과를 생성. RFC-002 §10.8:763 — "SHALL NOT expose a general-purpose live-order
  method to strategy, research, simulation, **backtest**, or operator-interface." ⇒ 합성 transport는 **범용 live
  메서드가 아니다**(구조적으로 브로커 도달 불가).
- **D-E3 공유**: D-E1 §12-3 — "D-E3=fill-model 대역·D-E4=paper 계좌 송신 대역·동일 시퀀서·다른 주입." 합성 paper
  transport의 fill 대역은 **D-E3 백테스트 fill 모델과 Transport Protocol을 공유**(D-E3 소폭 선행 공동설계·서베이
  §6-2). 차이는 이벤트 소스(역사 bar vs 실시간 feed)·fill 대역 파라미터뿐. **cost-realism·차등 오라클은 D-E3 소유**
  (D-E4는 구조만).

### 5.3 Transmit 인터페이스 충족 ((AttemptRequest) -> SendHandoff·EGRESS_RESULT 재주입)

- **동기 반환(D-E1 §2.1 D5)**: 게이트(Transmit slot)는 `(AttemptRequest) -> SendHandoff`(sequencer.py:114)를
  충족·**즉시 반환**(코어는 블로킹 network에 안 매임). `SendHandoff`(records.py:373-386)는 **hand-off ack**이지
  주문 결과가 아님·positive polarity(`accepted_for_transmission is True`만 accepted 기록).
- **비동기 결과 = EGRESS_RESULT**: 주문 결과(ack/fill/reject/timeout)는 나중에 `EgressResultPayload`(records.py:
  173-230)로 `EGRESS_RESULT` 이벤트로 재주입. **attempt_id는 필수 positive identity**(records.py:187,196-200 —
  concrete 강제)·늦거나 재정렬된 결과가 다른 reservation을 전이 못 함(§6). 합성 transport에선 결정론 fill 대역이
  EGRESS_RESULT를 생성.
- **비동기 격리 구조**: transport의 실 비동기 I/O(실 경로)는 **tos/ 밖 경계 뒤**(§5.1). tos/ 안 코어는 동기·결정론
  유지(D-E1 D5)·경계만 비동기. 합성 transport는 동기 결정론(비동기조차 불요).

### 5.4 E4 — no blind resubmit (구조 봉인·Q-IDEMP-1/2 재생산 금지)

**규범**: RFC-002 §9.1:574 "UNKNOWN outcome SHALL NOT cause blind resubmission"·"Broker Adapter SHALL NOT invent
an unbound attempt"(:565). RFC-005 §11:326-328 "SHALL NOT resubmit … UNKNOWN without the reconciliation,
attempt-identity, and capacity conditions … retry is a new send under §11.4, not a free repeat." §12:362 item6
"blind-retry an UNKNOWN outcome" 금지.

**판정: Broker Adapter 계약에서 blind retry를 구조적으로 표현 불가능하게 봉인.**

- **transport는 재시도 능력 0(single-shot)**: Transport Protocol은 **한 번의 verified outbound → 한 번의 결과**만
  표현. transport 내부에 재시도 루프 없음(executor.py:218,225-232,238-241의 3회 재전송·`retry_once_on_token_expiry`
  래퍼 — Q-IDEMP-1/2 — **재생산 금지**). 재시도는 transport 밖 **새 attempt**로만 가능하고, 새 attempt는 **새
  permit + 새 currentness proof → 새 content-addressed attempt-id**(D-E1 §4.3)를 요구하며 19-step 전체를 재통과.
  동일 (proof, permit, 좌표)로는 동일 attempt-id가 나와 ledger가 이미-bound로 거부(single-use).
- **brokercap 술어 봉인**: `same_order_retry_allowed`(:377) — SUBMISSION_IDEMPOTENCY가 **VERIFIED일 때만** True.
  KIS는 UNKNOWN(초안 §3.1 dim2)이므로 **False**(fail-closed·:388-389 "no blind retry"). ⇒ 같은 주문 network 재전송
  구조적 금지. `uncertain_send_policy`(:349) — **구조적 all-restrictive**(:359-362 "a permissive combination is
  unrepresentable"·timeout이 capacity 해제 못 함). 게이트/어댑터는 UNKNOWN 시 이 verdict를 소비 — no blind retry·
  no capacity release·no assume-rejection·start reconciliation·enter UNKNOWN/CONTAINED.
- **Q-IDEMP-2 특수(토큰 만료 재전송)**: executor.py:403의 `_request_json`이 주문 POST를 만료 재시도로 감싸는
  결함(서버 수락 후 만료 응답 배제 못 함). D-E4 계약: transport는 **인증/토큰 관심사를 주문 전송과 분리** — 토큰
  갱신은 send 전 별개 관심사이고 주문 POST 자체는 재전송 래퍼를 갖지 않는다. 만료 응답은 **UNKNOWN**(수락 여부
  미상)으로 처리·resubmit 금지(RFC-005 §11:322-323 missing-ack ≠ not-accepted).

### 5.5 partial fill·UNKNOWN/timeout 표현 (EGRESS_RESULT payload)

- **partial as partial**: `EgressResultPayload`(records.py:173-230)·`EgressResultKind`(vocabulary.py:108-124 —
  ACK/FULL_FILL/**PARTIAL_FILL**/REJECT/UNKNOWN/TIMEOUT). 구조 파생 검증(records.py:221-229 — `remaining_quantity
  > 0`이면 PARTIAL_FILL·FULL_FILL로 기록 불가)이 이미 D-E1에 있음. transport는 partial을 partial로 보고·**기체결분
  재요청 금지**(RFC-005 §11:338-339·§6:176-178). Q-CXL-2(POSITIVE·초안 §5:187 — 취소 후 재조회로 체결수량 갱신·
  "취소 ack 단독 미사용")는 **보존할 정합 패턴** — FQP 관점에서 옳은 기존 행위.
- **UNKNOWN/timeout**: 결과 미도래(J1) → **timeout 이벤트**가 `EgressResultKind.TIMEOUT` → EGRESS_RESULT로 재주입
  → UNKNOWN(D-E1 §2.1(i)·§4.2 rule3). reservation POTENTIALLY_LIVE 보수 유지·no resubmit. `EgressKnowledge`
  (vocabulary.py:133-149 — SENT_UNCONFIRMED/UNKNOWN이 명시 멤버)가 capacity projection과 orthogonal.

---

## 6. at-most-one의 send측 절반 (SAFE-021·§11:319-343)

- **분업**: D-E1은 **retention 절반** 소유(§4.4 — provisional RCL stand-in이 outstanding POTENTIALLY_LIVE를 retain·
  겹치는 economic-effect를 capacity-stage에서 deny·sequencer.py:382-401 `AT_MOST_ONE_EXPOSURE_HELD`). D-E4는
  **소비 절반** 소유 — send 경계의 single-use 집행이 그 대칭.
- **send측 3중 봉인**: (1) **single-use capability/permit**(egress `capability_and_permit_single_use` — nonce가
  THIS request에 정확히 한 번·prior claim 존재 시 False)·(2) **attempt-identity 정합**(EGRESS_RESULT의 attempt_id가
  정확히 그 attempt만 전이·records.py:181-183)·(3) **no blind resubmit**(§5.4). ⇒ retry·reconnect·duplicate가
  originating Intent 노출을 초과 못 함(SAFE-021·:319-322).
- **crash 정합(ADR-002-002 :611)**: SEND_STARTED 후 크래시는 possibly-live — D-E1 projection이 POTENTIALLY_LIVE
  유지(§4.6)·D-E4는 재시작 시 blind resend 안 함(새 attempt는 새 permit/currentness 요구). 실 crash-recovery
  재조정(recon/sbr/orthostate·J3)은 슬라이스 이연(D-E1 §9-7).
- **슬라이스 내 영구-deny 정직(v1.1·NIT-2)**: 슬라이스는 reconciliation을 이연하므로, 동일 scope의 재시도는
  provisional reservation이 **해소될 때까지 capacity-stage에서 영구 deny**된다(D-E1 §4.4 retention·
  `AT_MOST_ONE_EXPOSURE_HELD`·sequencer.py:382-401). 이는 보수적 정합(중복 노출 대신 영구 보류)이고, **해소
  (reconciliation으로 POTENTIALLY_LIVE 종결)는 슬라이스 밖 이연**(recon/sbr·J3·D-E1 §9-7).
- **⚠ 정직**: 이 send측 봉인은 **실 linearizable ledger의 원자성을 주장하지 않는다**(D-E1 §4.4 상속) — single-use는
  구조 술어까지, 실 fencing/CAS는 RCL 런타임 이연. 동시성 권위 미실증 → capacity EV 미봉.

---

## 7. fail-closed 규율 + 극성 (시리즈 술어 규율의 send 경계 적용)

- **positive-admit(양성 identity·D-E1 §6 상속)**. 게이트 verify·transport hand-off 전부 positive 술어 True만 진행.
  `is not DENY`류 음성 게이트 금지. D-E1 `_NonTruthyStrEnum`(vocabulary.py:59-77 — `__bool__` raises) 상속:
  StageOutcome/EgressResultKind는 truthy-untestable(bare `if verdict:` = TypeError).
- **음극성 bool|None은 `is False`만**(시리즈 교훈·`is not True` 금지). 예: credential `usable_credential is not
  False`(True/None=potentially-usable·§4.5)·cur `expiry_denies_future_use_only`(:572)·`unknown_preserves_capacity`
  (:593). **주의**: `SendHandoff.accepted_for_transmission`은 **positive polarity**(`is True`만 accepted·records.py
  :379,385)이므로 `is True` 소비가 정합.
- **UNKNOWN-restrictive + no blind retry**. §4.2·§5.4·cur `unknown_preserves_capacity`·brokercap
  `uncertain_send_policy`(구조적 all-restrictive).
- **∅ 양방향**. empty inventory → False(egress `credential_route_authority_disjoint` — disjointness 미증명·§4.5)·
  ∅ envelope → UNKNOWN(engine `economic_effect_envelope_verdict` — "empty vector is not no effect"·adapters.py
  :385-392). missing(부재) vs explicit-empty 구분.
- **구조 파생 > 자기신고**. 수량 파생(§3.1 — 계산·검증)·partial 판정(magnitude·records.py:221)·좌표등가(§4.4 —
  좌표 대조)·attempt-id(content-addressed) 전부 구조/아티팩트 파생.
- **broker 도달성 ≠ 권위**(cur `broker_reachable_not_authority`:706). 합성 transport가 "도달했다"고 currentness/
  admissibility가 성립하지 않음 — 권위는 별개 술어.

---

## 8. seam 지도 (REUSE / WIRING / NEW + 소유권 분할)

### 8.1 REUSE (기구현·재저작 금지·자체 실측 file:line)

| seam | 심볼(file:line) |
|---|---|
| Order Construction | ioc: `compile_command`(predicates.py:185)·`command_conforms`(:96)·`no_silent_widening`(:427)·`numerical_safety`(:335)·`economic_effect_dominated`(:379)·`mutation_fence_holds`(:492)·`OrderConformanceProof`/`CanonicalBrokerCommand`/`ApprovedIntentContract`/`AuthorizedConstructionEnvelope`/`EconomicEffectEnvelope`(records.py) |
| venue admissibility | venue: `session_phase_admits`/`order_shape_admissible`/`OrderAdmissibilityResult`(venue/__init__:112-141) |
| send currentness | cur: `proof_admissible`(predicates.py:467)·`proof_structurally_complete`(:438)·`unknown_preserves_capacity`(:593)·`broker_reachable_not_authority`(:706)·`EgressCurrentnessProof`/`SafetyCurrentnessVector`/`EgressProofCoordinateSet` |
| single-use·좌표등가·credential·latch | egress: `capability_and_permit_single_use`(predicates.py:292)·`exact_binding_holds`(:337)·`credential_route_authority_disjoint`(:405)·`monotonic_denial_no_revival`(:519)·`replay_or_substitution_detected`(:259) |
| broker admissibility·retry·uncertain | brokercap: `environment_binding_ok`(predicates.py:644)·`capability_admissible`(:118)·`same_order_retry_allowed`(:377)·`uncertain_send_policy`(:349)·`CLASS_D_NON_LIVE`(vocabulary.py:146) |
| D-E1 핸드오프 타입·어댑터 | engine: `Transmit`(sequencer.py:104)·`SendHandoff`(records.py:373)·`EgressResultPayload`(records.py:173)·`AttemptRequest`(records.py:317)·`egress_currentness_verdict`(adapters.py:455)·`conformance_proof_verdict`(:145)·`economic_effect_envelope_verdict`(:353)·`venue_admissibility_verdict`(:82)·`transmission_capability_verdict`(:417)·`SEND_BOUNDARY_STEPS`(vocabulary.py:218)·`StageAuthorityClass.DEFERRED_SEND_BOUNDARY`(:306) |

### 8.2 NEW (owning runtime — negative-grep 부재 확정·§0.5)

- **`tos.egressgw`**: (1) Order Construction stage(수량 파생 seam §3.1 + ioc 래핑 §3.2·candidate 전용 얇은 어댑터)·
  (2) Broker Egress Gateway(step 15 verify list 배선 §4.1·§4.2 fail-closed·§4.6 SEND_STARTED 순서·`Transmit` 충족).
- **`tos.brokeradapter`**: (3) Transport Protocol(§5.1 firewall seam)·(4) synthetic paper transport(§5.2·결정론 fill
  대역·D-E3 공유)·(5) EGRESS_RESULT 생성(§5.3).
- 전부 부재(`ls tos/src/tos/*/ | grep -iE 'egressgw|brokeradapter'` → 0·§0.5).

### 8.3 소유권 분할표 (D-E4 vs 이연·최대 함정)

| 관심사 | D-E4 소유 | 이연 소유 |
|---|---|---|
| 수량/가격 파생 | **seam 계약**(§3.1) | **D-E2** 가격 값 표면·**P0-1** sizing bound |
| candidate/envelope/proof 구성 | ioc 래핑 배선(§3.2) | — (ioc 기구현) |
| step 15 verify(구조 술어) | 배선·positive 게이트(§4.1) | live 안전 메시(Safety Authority/Live Scope/Envelope/Deviation/Incident/Monitoring — Deferred 6) |
| single-use·좌표등가·credential | 구조 술어 소비(§4.4·§4.5) | QCC quorum·byte 재구성·route confinement·실 inventory 열거(+Security L2+) |
| SEND_STARTED durable·claim/consume | 순서 배선(§4.6) | 실 RCL atomic·실 Evidence Store(ADR-002-016) |
| network call(step 18) | Transport Protocol + 합성 대역(§5) | **실 KIS 대역**(tos/ 밖·P0-2 후) |
| fill 모델·cost-realism | 합성 fill 구조(§5.2) | **D-E3** cost-realism·차등 오라클 |
| POTENTIALLY_LIVE projection | — (D-E1 `mark_potentially_live`) | RCL 권위 transition |
| at-most-one retention | — (D-E1 §4.4) | 실 linearizable ledger |
| at-most-one 소비(single-use·no-resubmit) | **§6** | — |

---

## 9. 수치 → Phase-0 / INSTANCE (숫자 하드코딩 0)

D-E1 §8 상속 — 수치 하드코딩 0·전부 주입 bound/INSTANCE:

| 수치 | 소유 | 현상태(register 실측) |
|---|---|---|
| `environment: non-live-test`(§4.7 바인딩) | scope(P0-2·brokercap INSTANCE) | register §3:88 **유일 확정 scope 값** |
| `MAX_normal_capability_age_ms 1000`(capability age·§4.4 single-use) | limits(register §3:90) | 확정 5중·주입 소비 |
| `MAX_unresolved_send_per_scope 1`(at-most-one·§6) | limits(register §3:90) | 확정·D-E1 `EngineConfiguration.max_unresolved_send_per_scope`(records.py:447) 소비 |
| sizing bound(risk budget·per-unit·lot 정책·§3.1) | P0-1(Bounds-Approver) | **미승인·미신설**(register §3 확정값 아님)·provisional |
| broker-specific bound(rate/admission·detection/containment·late-event window) | P0-2(Broker Capability Profile) | **미결**(KIS 초안 §7 item3 `hard_limits: {}`·null 다수)·provisional |
| currentness dimension floor(§4.3) | cur `MANDATED_DIMENSION_FLOOR` + owner 사실 | provisional/D-E2 |

⇒ 슬라이스 소비 수치 다수가 null/미승인 → **provisional 값 배선·산출 provisional**(§1.1). broker bound 승인=P0-2·
sizing bound 승인=P0-1(둘 다 인간 게이트).

---

## 10. Phase-0 / not-slice-1 체크리스트 (닫지 않음·후속 게이트)

**본 계약이 실현 지침 제공(슬라이스 #1 send 경계)**: Order Construction 래핑·수량 파생 seam·step 15 verify 구조
배선·합성 transport·quirk 구조 봉인·at-most-one 소비 절반·property test 타깃(§12).

**닫지 않음(명시 이연·후속)**:
1. **정식 EV-L2 PASS** — G2 canonicalization·P0-1 bounds·P0-2 profile·P0-3 독립 리뷰어·정식 실행·서명 선결. 슬라이스
   산출은 provisional(§1.1).
2. **실 KIS 모의투자 transport 배선**(§2·§5.1) — P0-2 종결 + 승인된 Profile + credential inventory 격리 검증 후·
   tos/ 밖 구현.
3. **live 안전 거버넌스 메시**(§4.1 Deferred 6 — Safety Authority·Live Scope·Envelope·Deviation·Incident·Monitoring
   런타임) — 각 미래 owning-runtime·비-live 슬라이스 밖.
4. **완전 QCC quorum·byte-level outbound 재구성·route confinement·실 credential inventory 열거**(§4.4·§4.5 — egress
   +Security EGRESS-EV L2+).
5. **실 RCL atomic Permit claim/consume·실 SEND_STARTED durable store·완전 Evidence Store**(§4.6 — ADR-002-016).
6. **D-E2 가격 값 표면·D-E3 fill cost-realism/차등 오라클**(§3.1·§5.2).
7. **out-of-band containment**(RFC-002 §10.8:767 — live scope 종료 경로·비-live 슬라이스 이연·live 착지 시 필수).
8. **broker bound·sizing bound 신설·승인**(§9·P0-1/P0-2).
9. **crash-recovery 재조정·fault-injection J1-J5**(§6·서베이 §5 — EV-L2+ 트랙 b·접합 위치만 표기).
10. **wire 비대칭 완전 봉인**(Q-WIRE-1·§4.4 — byte 재구성 +Security 이연)·**실 idempotency 측정**(초안 §5 P-2 프로브·
    `same_order_retry_allowed` VERIFIED 승격 전제).

---

## 11. 명명 결정 + 리뷰어 공격 지점

### 11.1 명명 `tos.egressgw` + `tos.brokeradapter` (운영자 판단 지점)

- **`tos.egressgw`**: Order Construction + Broker Egress Gateway 통합 런타임. 서베이 §7-5:326이 이미 제안("Broker
  Egress Gateway **런타임**은 별도 패키지(`tos.egressgw` 등) — 커널/런타임 혼동은 seam fail-open 온상"). negative-grep
  충돌 0(§0.5). **`tos.egress`(ADR-002-013 QCC 커널) 잠식 절대 금지** — egressgw는 egress 술어를 소비(import)하되
  커널 미수정. runner-up: `tos.finalgress`(과장식)·`tos.sendgate`(모호).
- **`tos.brokeradapter`**: Broker Adapter transport 경계. RFC-002 §10.8 명명 그대로. negative-grep 충돌 0.
  runner-up: `tos.transport`(과광범)·`tos.brokergw`(egressgw와 혼동).
- **Order Construction 별도 3번째 패키지?** — 검토·기각: (a) YAGNI(단일 주문·slice 불요), (b) Order Construction의
  actual-outbound 검증이 게이트의 `exact_binding_holds`와 밀결합(§4.4)이라 egressgw 내부 모듈(`construction.py`)이
  응집도 높음, (c) 3패키지는 seam 표면 증가(fail-open 온상). 채택: egressgw 내부 `construction.py`(step 2·5·11) +
  `gateway.py`(step 15-19). 대안(3패키지 `tos.ordercon`)은 다심볼/복잡 구성 확장 시 재검토.
- **register prefix 부재**: D-E1과 동일 — Part-2/3 RFC 실현·닫는 EV 0·ADR-EV register 행 없음. 명명은 순수 설계
  선택·운영자 확정 지점.

### 11.2 리뷰어 공격 지점 (선제 반론)

1. **"합성 transport는 send를 실증하지 않는다 — 슬라이스가 허구 아닌가?"** — 반론: 아니다. 슬라이스가 실증하는
   것은 **send 경계 계약의 기계**(step 15-19 배선·verify 순서·fail-closed·hand-off/재주입 타입)이지 실 브로커 왕복이
   아니다. 실 왕복은 firewall·P0-2·VERIFIED 0·Live-Armer 4중 차단(§2.2)으로 슬라이스 불가. 합성 transport는
   **정직한 유일 실행 경로**이고 §1.1이 닫는 EV 0을 최상위 선언. 실 경로는 계약으로 설계됨(단계 분리).
2. **"step 15 verify가 6/17만 실현 — 게이트가 안전을 준다고 오독될 위험."** — 반론: §4.1 전수표가 각 항목을
   Realize/Provisional/Deferred로 **명시 라벨**·Deferred 6이 live 안전 메시임을 정직 명기. 게이트는 구조 술어만
   실행하고 live acceptance 미주장. 실 live send면 다수 provisional/deferred로 fail-closed 거부.
3. **"egressgw가 tos.egress를 잠식하는가?"** — 반론: 아니다. egressgw는 egress 술어를 **import(소비)**하되 커널
   파일 미수정. import-closure allowlist(§0.3)에 tos.egress 포함은 소비 edge·잠식 아님. planted-leak canary는
   egress **수정** 아닌 **소비**를 허용(§12).
4. **"수량 파생이 RFC-005 §7 no-invent 위반?"** — 인정+반론: 파생은 invent가 아니라 **명시 유계 규칙 계산**
   (risk budget/per-unit·lot 정책=저작 상수)이고 ioc `compile_command`가 envelope 대조로 봉인(§3.1). default/round/
   repair는 금지(미지 입력→denial). "조용한 폴백"(Q-MIC-3)과 정반대.
5. **"비-live-test인데 verify list 전체가 필요한가?"** — 반론: RFC-002 §10.8:739 "risk-relevant **or
   broker-resource-consuming**" — 실 모의 API도 broker-resource-consuming이라 verify 대상. 슬라이스는 그래서 합성
   경로로 실행하고 게이트 계약은 완전 배선(§2.3). 게이트가 비-live-test 바인딩을 확인(§4.7)하되 live admissibility는
   PROHIBITED.

---

## 12. 선제 defect-class 봉합 + property test 타깃

### 12.1 property test 타깃 (오케스트레이션 불변식·저작 증거·acceptance 아님·닫는 EV 0)

1. **게이트 fail-closed 전수**: verify 항목 임의 하나가 deny/None/UNKNOWN 반환 시 `SendHandoff
   (accepted_for_transmission=None)`·transmit 미발생·중단 사유 기록(§4.2). positive-admit 뮤테이션 KILLED.
2. **no blind resubmit(§5.4)**: `same_order_retry_allowed`가 KIS(SUBMISSION_IDEMPOTENCY UNKNOWN)에 False·동일
   (proof,permit,좌표) 재시도가 동일 attempt-id→single-use 거부·`uncertain_send_policy` all-restrictive. 뮤테이션
   (retry 루프 삽입) KILLED.
3. **credential 격리(§4.5)**: empty inventory→False·경계 밖 principal이 credential+route 함께→False·None flag
   conservatively usable(`is not False`). Q-CRED-1 시나리오 봉인.
4. **좌표등가(§4.4)**: `exact_binding_holds`가 좌표 불일치/비-CONFORMANT/digest 불일치에 False. field substitution
   뮤테이션 KILLED. (byte 재구성은 이연 — 좌표등가까지만 주장.)
5. **수량 파생 결정론·무-수선(§3.1)**: 동일 입력→동일 command/digest·미지 가격→denial(no default)·envelope 밖→
   denial(no repair). Q-MIC-3 조용한 폴백 뮤테이션 KILLED.
6. **partial as partial·UNKNOWN(§5.5)**: remaining>0→PARTIAL_FILL(FULL 기록 불가·records.py:221)·timeout→UNKNOWN·
   기체결분 재요청 0·POTENTIALLY_LIVE 유지.
7. **at-most-one 소비(§6)**: single-use nonce 재claim 거부·EGRESS_RESULT attempt_id 정합(다른 attempt 전이 불가).
8. **firewall**: egressgw/brokeradapter closure ⊆ allowlist(§0.3)·**network stdlib 미참조**(brokeradapter canary —
   실 network는 tos/ 밖 강제)·`tos.egress` 소비하되 미수정·RNG/uuid 미참조(content-addressed).

### 12.2 선제 defect-class 봉합 (전 시리즈 교훈)

| defect class | 봉합 |
|---|---|
| **fail-open in wiring**(시리즈 핵심) | positive-admit 게이트(§4.2)·전 verify 항목 중단 canary(§12.1-1) |
| **음성 게이트/극성 회귀**(#18/#22/#23/#25) | `is not DENY` 금지·음극성 `is False`(credential/expiry)·양극성 `is True`(SendHandoff)·극성별 명기(§7) |
| **UNKNOWN 무처리/blind retry**(RFC-005 §11·Q-IDEMP) | `uncertain_send_policy` all-restrictive·`same_order_retry_allowed` fail-closed·transport single-shot(§5.4·§12.1-2) |
| **over-realization**(EGRESS #22·합성=실 오독) | 합성 transport NON-AUTHORITATIVE·byte 재구성/route/inventory +Security 이연 명기(§4.4·§4.5)·닫는 EV 0(§1.1) |
| **phantom 인용** | anti-phantom §0.5·전 file:line 재실측·부재 negative-grep |
| **over-claim**(verify 완전성) | §4.1 전수표 Realize/Provisional/Deferred 라벨·6/17만 구조 실현 명기 |
| **자기신고 fail-open**(#21/#24) | 수량 구조 파생(§3.1)·좌표등가(§4.4)·partial magnitude·attempt-id content-addressed |
| **∅ vacuous/과잉거부**(#17/#26) | empty inventory→False(disjointness 미증명)·∅ envelope→UNKNOWN·missing vs explicit-empty(§7) |
| **credential 편재**(Q-CRED-1·신규) | ADR-002-013 credential 격리·firewall(credential tos/ 밖)·`credential_route_authority_disjoint`(§4.5) |
| **조용한 폴백/wire 수선**(Q-MIC-3/Q-WIRE-1·신규) | no invent/default/round/repair(§3.1)·ioc `no_silent_widening`·좌표등가(§4.4·완전 봉인 이연 명기) |

---

## 13. quirk → 구조 봉인/이연 매핑 (KIS 초안 17건 전수)

KIS 초안 §5의 quirk **17건(HIGH 6·MEDIUM 7·INFO/POS 4)**을 D-E4 계약이 어떻게 처리하는지 전수 매핑. **심각도=TOS
fail-open 관점**(운영 버그 아님). **⚠ 실계수 정정(v1.1·MINOR-1)**: KIS 초안 §5 헤더 "16건·MEDIUM 6"은 오산이다 —
MEDIUM 표의 실제 행은 **7건**(Q-OOQ-2·Q-POS-1·Q-SESS-2·Q-SESS-3·Q-CRED-2·Q-WIRE-1·Q-MIC-2)이라 총 **17**. 초안
헤더 정정은 오케스트레이터가 별도 에라타 커밋(`c24844e5`)으로 처리했다(본 설계는 초안 무수정·실계수 17로 매핑).

| ID | 심각도 | quirk | D-E4 처리 |
|---|---|---|---|
| Q-IDEMP-1 | HIGH | 예외 경로 order_no 미상 3회 재전송(executor.py:225-232) | **구조 봉인**: transport single-shot·재시도=새 attempt(§5.4)·`same_order_retry_allowed`=False |
| Q-IDEMP-2 | HIGH | 주문 POST 만료 재전송 래퍼(executor.py:403) | **구조 봉인**: 토큰/주문 분리·만료=UNKNOWN·no resubmit(§5.4) |
| Q-OOQ-1 | HIGH | 연속조회 키 미사용→1페이지(executor.py:562-563) | **이연**(open-order query는 reconciliation·슬라이스 밖)·§10-9. FQP recipe 전제 |
| Q-SESS-1 | HIGH | 평문 ws://(websocket.py:433-434) | **이연**(시세 전용·transport 경계 밖)·실 transport 배선 시 wss 요건·§10-2 |
| Q-CRED-1 | HIGH | 워커 raw credential 편재(auth.yaml:7-8) | **구조 봉인**: credential 격리(§4.5)·firewall·`credential_route_authority_disjoint`(완전 열거 L2+ 이연) |
| Q-MIC-1 | HIGH | 모의에 야간 TR 없음(tr_ids.py:40-50) | **이연**(MOCK→REAL 외삽 금지·비상속·초안 §3.2)·야간 profile 별도(초안 U-4) |
| Q-OOQ-2 | MED | 조회창 today/today-1 하드제한 | **이연**(reconciliation) |
| Q-POS-1 | MED | 잔고 broker↔Redis 조정 로직 존재(불일치 정황) | **이연**(position/balance query·recon 소관) |
| Q-SESS-2 | MED | KIS 자체 PINGPONG·ping_interval 0 | **이연**(세션 모델·transport 실 구현 tos/ 밖) |
| Q-SESS-3 | MED | 무한 재연결→계정 차단·circuit breaker | **이연**(연결 관리·transport 밖)·retry-storm은 afg budget(§1.2 defer) |
| Q-CRED-2 | MED | 인증/인프라 오류 같은 차단기 | **이연**(인증 계층·transport 밖) |
| Q-WIRE-1 | MED | 숫자 인코딩 자산군 비대칭(executor.py:321,393) | **부분 봉인**: 좌표등가(§4.4)가 authorized wire 일치 요구·**완전 byte 재구성 봉인 이연**(+Security)·§10-10 |
| Q-MIC-2 | MED | ATS TR 존재하나 미사용 | **이연**(venue routing·비활성) |
| Q-CXL-1 | INFO | 취소 응답이 새 ODNO | **정합 반영**: 취소 ack가 원주문 최종수량 미증명(FQP)·§5.5 partial 규율 |
| Q-CXL-2 | POSITIVE | 취소 후 재조회로 체결수량 갱신(executor.py:511-520) | **보존**: FQP 관점 옳은 패턴·"ack 단독 미사용"·§5.5 |
| Q-MIC-3 | INFO | 미지 주문유형 `"01"` 조용한 폴백(executor.py:785-795) | **구조 봉인**: no invent/default(§3.1)·ioc `no_silent_widening`·미지→denial |
| Q-RATE-1 | INFO | 5/20 req/s 모순(둘 다 미근거) | **이연**(rate bound P0-2 측정·초안 §5 P-13)·§9 |

**집계(전수·17)**: 구조 봉인 **4**(Q-IDEMP-1/2·Q-CRED-1·Q-MIC-3) · 부분 봉인 **1**(Q-WIRE-1) · 정합 반영/보존
**2**(Q-CXL-1/2) · 이연 **10**(reconciliation/세션/연결/venue/rate — 슬라이스 밖 관심사). 합 4+1+2+10 = **17**.
**HIGH 6 중 3(Q-IDEMP-1/2·Q-CRED-1)가 D-E4 소관·전부 구조 봉인**·3(Q-OOQ-1·Q-SESS-1·Q-MIC-1 = reconciliation/세션/
외삽)는 슬라이스 밖 이연. RR-1(초안 U-7) Q-IDEMP residual risk 처분은 P0-2 인간 게이트.

---

## 14. Self-Check (task 요구·독립 비평 리뷰 전 자가 확인)

- [x] **닫는 EV 0·provisional 최상위 선언** — 배너·§1.1(send 고유 3사유). EV-L2 PASS 미주장.
- [x] **슬라이스 send 경계 판정** — §2 합성 paper transport(**브로커-도달/합성 축**·①firewall+②broker-consuming-verify가
      옵션(b) 차단·③④ live 방어심층·v1.1)·실 경로 설계하되 실행 이연(단계 분리).
- [x] **step 15-19 실현/이연 분할** — §1.3·§4.1 verify list 17항목 전수표(Realize 6·Provisional 5·Deferred 6)·
      **§4.2 broker-applicability 양성 게이트**(v1.1 — 조용한 skip·무조건 deny 둘 다 회피).
- [x] **quirk 구조 금지** — §5.4·§13 전수 매핑(**17건**·구조 봉인 4·부분 1·보존 2·이연 10)·기존 executor.py 결함 재생산 금지.
- [x] **G5 수량/가격 파생** — §3.1 결정론·유계·무-수선 seam·ioc 봉인·D-E2/P0-1 이연.
- [x] **at-most-one send측 절반** — §6 single-use·attempt-identity·no-resubmit·D-E1 retention과 분업.
- [x] **비동기 격리·transport Protocol** — §5.1·§5.3(코어 동기·경계 비동기·network tos/ 밖).
- [x] **credential/route 격리(ADR-002-013)** — §4.5·Q-CRED-1 봉인·firewall 정합.
- [x] **`tos.egress` 잠식 금지** — §0.3·§11-3(소비 import·커널 미수정).
- [x] **anti-phantom(존재/부재 양방향 grep·file:line)** — §0.5·전 인용 실측·negative-grep 3건.
- [x] **음극성 `is False`·양성 identity·구조 파생·∅ 양방향·UNKNOWN-restrictive·broker 도달성≠권위** — §7·§12.2.
- [x] **seam 지도(소비 file:line·소유권 분할)** — §8.
- [x] **수치 하드코딩 0·Phase-0 provisional** — §9.
- [x] **명명 결정·리뷰어 공격 선제 반론** — §11.
- [x] **provisional·닫는 EV 0 정직 선언** — 배너·§1.1·§10.
- [x] **v1.1 축 정정(독립 비평 REVISE)** — MAJOR-1 브로커-도달/합성 축(§2.2)·MAJOR-2 broker-applicability 양성
      게이트(§4.2)·§4.7 근거 "no-broker-reached" 정정·MINOR 1-4·NIT 1-2 전건(§16 개정 로그).
- [ ] **미해결(운영자/후속)**: 명명 `tos.egressgw`/`tos.brokeradapter` 확정(§11.1)·Order Construction 패키지 배치
      (egressgw 내부 모듈 vs 3패키지)·D-E2 가격 표면 착지 여부(§3.1)·P0-2 profile 승인(§2·§9)·실 transport 배선
      시점(§5.1).

---

## 15. 요약

**tos.egressgw + tos.brokeradapter(D-E4)는 수직 슬라이스 #1의 send 경계다** — Normal Commitment Flow step 15-19 소유.
확정: (1) **슬라이스 send = 합성 paper transport**(네트워크 0)·실 KIS 모의투자 경로는 설계하되 실행 이연(**축=
브로커-도달/합성**·①firewall[위치-한정]+②broker-consuming-verify→§10.8:761 fail-closed가 옵션(b) 실행 차단·③④
VERIFIED 0/Live-Armer는 별개 live 경로 방어심층·단계 분리·v1.1), (2) **step 15-19 실현/이연 분할**(verify list
17항목 중 구조 술어 6 Realize·provisional stand-in 5·broker-consuming 안전 메시 6 Deferred — §4.2 broker-applicability
양성 게이트로 봉인·게이트는 구조 검증하되 live acceptance 미주장), (3) **Order Construction 수량/가격 파생 seam**
(결정론·유계·무-수선·**추상 basis→구체화→검증** 3분업[§10.2:617]·sizing은 Authorized Construction Envelope 봉입·
ioc declare-and-verify 봉인·
값은 D-E2/P0-1 이연), (4) **quirk 구조 봉인**(blind-retry·credential 편재·조용한 폴백을 계약에서 표현 불가능하게 —
brokercap/egress/ioc 술어·기존 executor.py 결함 재생산 금지), (5) **at-most-one send측 절반**(single-use·
attempt-identity·no-resubmit — D-E1 retention과 분업).

**정직 스코프**: 닫는 EV 0. send 슬라이스는 **구조·좌표 술어 배선의 기계 실증**이지 currentness/QCC/single-use/
credential-격리 acceptance가 아님 — 합성 transport(실 브로커 미도달)·P0-2 미결·VERIFIED 0(§1.1). D-E4가 슬라이스
에서 실 코드로 집행하는 것은 step 15 구조 verify·step 18-19 합성 transport + provisional evidence뿐이고, live 안전
메시·실 RCL atomic·byte 재구성·실 credential 열거는 provisional 또는 이연이다.

**재실측 발견(입력물 정정/보강)**: (a) 서베이 §1:89 "paper 주문 1건 = 모의 계좌 송신"은 (b) 실 API를 시사하나,
구조 차단 실측상 슬라이스 실행은 (a) 합성 transport여야 정직 — **차단 축은 "브로커-도달/합성"**(옵션(b) 실 모의는
broker-resource-consuming이라 RFC-002 §10.8:741 verify 트리거→미착지 안전 메시 :761 unverifiable로 fail-closed;
live-축 VERIFIED 0/Live-Armer는 방어심층·**v1.1 MAJOR-1 정정** — `capability_admissible`은 live 검사이고 비-live는
`environment_binding_ok`[:644-672] 경로라 옵션(b) 판별자 아님)(§2 — 단계 분리로 실 경로는 설계). (b) D-E1이
`egress_currentness_verdict`(adapters.py:455)·`SEND_BOUNDARY_STEPS`(vocabulary.py:218)·`StageAuthorityClass.
DEFERRED_SEND_BOUNDARY`로 send 경계 타입 edge를 **이미 선물**했고 sequencer가 15-19 stage host를 구조 거부
(validate_stage_map:158-163)하므로, D-E4는 `Transmit` slot 충족 + 그 타입들 소비로 배선(신규 타입 최소). (c) egress
`exact_binding_holds`·`credential_route_authority_disjoint`가 **좌표등가·주입-inventory까지만**(byte 재구성·실 열거는
+Security L2+)이라 D-E4의 좌표/격리 실현이 구조까지임을 명기 — over-claim 방지.

---

## 16. 개정 로그 (v1.1 — 2026-07-29 독립 비평 리뷰 REVISE 반영)

**평결**: REVISE(CRITICAL 0·MAJOR 2·MINOR 4·NIT 2). 인용 ~55건 phantom 0·verify list 17항목 매핑 무결·**합성
transport 판정은 리뷰어 concur**·리뷰어 공격 8종 전부 불발. 두 MAJOR는 단일 근본원인(축 혼동)으로 수렴하며 **판정
번복이 아니라 정당화 축 정정**이다. 핵심 판정 5·구조는 리뷰 지지로 **유지**. finding별 처분(전건 적용·실증 반론 0 —
전 finding이 리뷰어 file:line 실증으로 정당):

| finding | 처분 | 변경 위치 |
|---|---|---|
| **MAJOR-1** 옵션(b) 차단 축 혼동(live/비-live) | 적용(전건) | §2.2 재구성 — 옵션(b) 실행 차단=①firewall(위치-한정)+②broker-consuming-verify→§10.8:741 트리거→:761 fail-closed·**③④ VERIFIED 0/Live-Armer는 별개 live 경로 도달불가 방어심층으로 강등**·"4중 독립"/"유일 실행" 문구 수정·§2 intro 축 표기·§15 재실측 발견 (a) |
| **MAJOR-2** Deferred 메시 applicability 봉인 부재(조용한 skip=fail-open·무조건 deny=합성 차단·§2.1 모순) | 적용(전건) | §4.2 **broker-applicability 양성 게이트 신설**(per-item positive-admit 前 실행·broker-consuming/risk-relevant-live면 required→UNKNOWN→deny·**양성확인 합성·non-broker·non-live-test만 N/A**·∅ 양방향·미상은 보수적 broker-consuming)·§4.1 분류 규율/item 4·5 rationale/정직 귀결 조건부화·§4.7 근거 **"no-live-arming"→"no-broker-reached" 정정** |
| **MINOR-1** quirk 실계수(초안 헤더 16 오산) | 적용 | §13 16→**17**·MEDIUM 6→**7**·이연 9→**10**·HIGH명명 4→3/2→3·배너 line 38·초안 헤더 오산 각주(에라타 오케스트레이터 커밋 `c24844e5`)·§14 |
| **MINOR-2** §10.2:617 화해 | 적용 | §3.1 Decision↔Construction **3분업**(§10.2:617 "identify … quantity" → 추상 basis 식별·§11.1:583 결정론 구체화·:585 검증)·"결정=방향·근거만" 대안 B 문구 대체 |
| **MINOR-3** Authorized Construction Envelope 봉입 | 적용 | §3.1 sizing bound를 **proposed Authorized Construction Envelope에 봉입**(§9.1:553 governance)·step-2=**순수 (proposal, envelope) 함수**·파생 입력 (ii) 정정 |
| **MINOR-4** venue thin-adapter | 적용 | §3.2 step-3 = **non-authorizing thin adapter**(tos.venue 술어 위)·**step-15 item-11 게이트 enforcement와 별개 역할** 명시(§9.1:554) |
| **NIT-1** 인용 드리프트 | 적용 | `DEFERRED_SEND_BOUNDARY` :305→**:306**(§0.5·§8.1)·RFC-002 §10.8 item16 :757→**:758**(§4.3·§4.6) |
| **NIT-2** 영구-deny 정직 | 적용 | §6 슬라이스 내 동일 scope 재시도=provisional reservation 해소까지 capacity-stage 영구 deny(보수적 정합·해소는 reconciliation 이연) |

**리뷰어 공격 8종 불발(§11.2 선제 반론 유지·v1.1이 강화)**: 합성=허구·verify 6/17 과청구·egress 잠식·수량 파생
no-invent 위반·비-live verify 불요 등 — 전부 방어. v1.1 축 정정은 이 방어를 **정확화·강화**(옵션(b) 차단의 진짜
축을 broker-consuming으로 명시)하지 약화하지 않는다.

**재실측 인용(쓰기 전 재grep·anti-phantom §0.5)**: `environment_binding_ok`(brokercap/predicates.py:644-672 —
profile/VERIFIED **무관**·`evidence_environment==scope_environment`·`inherited is False`·BC-INV-009:653) ·
`capability_admissible`(:118 — live 검사·conformance class 미참조) · RFC-002 §10.8:741(risk-relevant **or
broker-resource-consuming** verify 트리거)·:761(missing/stale/conflicting/**unverifiable**→reject)·:758(item16 Egress
Currentness Proof) · §10.2:617(Decision "identify … account, instrument, direction, **quantity**, and constraints") ·
ADR-002-002 §11.1:583(step 2 — candidate from exact proposal + **proposed Authorized Construction Envelope**)·
:585(step 4 approval validates candidate) · `StageAuthorityClass.DEFERRED_SEND_BOUNDARY`(engine/vocabulary.py:306).
**전건 실측 일치·MAJOR 2건 코드/규범 실증 확인**(environment_binding_ok profile-무관·§10.8:741 broker-consuming
트리거).
