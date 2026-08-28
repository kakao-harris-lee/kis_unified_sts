# 작업 메모 — TOS 엔진 층(Part 2/3) 수직 슬라이스 #1 스코핑 서베이 (2026-07-29)

> **문서 성격 (규범성 선언)**: 본 문서는 **비규범 작업 메모**다(엔진 완주 경로 평가
> `docs/plans/2026-07-29-tos-engine-completion-path-assessment.md`·Phase-0 register `…-phase0-human-gate-register.md`
> 동형). **비준(ratification) 대상이 아니며**, GOV-001의 세 거버넌스 행위(비준 / ADR acceptance /
> live authorization) 중 어느 것도 수행하지 않는다. ADR·RFC·VER·register·VERIFICATION-PROFILE의 어떤
> 상태도 변경하지 않고, 어떤 EV 항목도 이동시키지 않는다. 유일한 산출은 **수직 슬라이스 #1
> (DSL 전략 1개 → 이벤트 기반 백테스트 → paper 주문 1건)의 조항 하중·seam·의존·설계 분해에 대한
> 운영자-검증용 스코핑 실측**이다. 여기의 권고는 후속 **설계 사이클의 입력물**일 뿐, 설계 비준도
> 구현 승인도 아니다. 본 서베이 자체가 설계 문서가 아니다 — 규범 판정(EV 매핑·소유권·seam 채택)은
> 후속 각 설계 문서가 스스로 수행한다(엔진 메모 §5:109-111).

- **발단**: 엔진 완주 경로 평가 §5:109 — "ADR-002 시리즈 완주(#28 SIR·#29 SCI·#30 STM) 후, 본 메모
  §3-1의 수직 슬라이스 설계 문서 저작이 다음 사이클이다." ADR-002 30문서 완주(디스크 실측: tos/ 32
  패키지 — §7-1 관측), 본 서베이는 그 설계 사이클의 **선행 스코핑**이다.
- **방법**: anti-phantom 규율(존재/부재 양방향 grep·file:line·`grep|head` 절단 금지) 하 실측. RFC-003/004/005/006
  (part-2-decision)·RFC-008/010 + ADR-DEV-001/002/007/010 (part-3-development)·tos/src/tos/ 32 패키지 export
  표면·Phase-0 register·엔진 메모를 원천 실측. 부재 주장은 negative-grep 병기(§3-3·§7-1).

---

## 0. 요약 판정 (한눈 표)

**판정 1 — 슬라이스 #1은 RFC의 방법론 깊이를 싣지 않는다. 싣는 것은 (a) 단일 결정→주문을 Normal
Commitment Flow로 통과시키는 구조 골격과 (b) Proposal/outcome 출력 계약뿐이다.** 결정적 실측:
**RFC-005 §7:193-199 한 문장이 슬라이스 실행 경로 전체를 열거한다** — "deterministic candidate
construction, venue admissibility, independent approval and Intent registration, conservative
economic-effect derivation, aggregate-risk evaluation, action-flow evaluation, atomic RCL capacity
commitment, conformance proof, attempt binding, single-use Transmission Capability issuance, and
final-egress verification with `SEND_STARTED` durability … `POTENTIALLY_LIVE`." 이 각 단계가 **이미
구현된 술어 패키지에 1:1 대응**한다(§3). 슬라이스의 신규 표면은 술어가 아니라 그 술어를 순서대로
호출하는 **owning runtime(이벤트 루프)**뿐이다 — 엔진 메모 §2:45-47("fail-open은 술어 내부가 아니라
배선에 산다")의 정밀화.

**판정 2 — 최소 조항 하중.** 슬라이스 #1이 하중을 받는(realize) 조항 집합:

| RFC/ADR | Realize (슬라이스 하중) | Defer (명시 이연) |
|---|---|---|
| **RFC-003** 결정 | §7 파이프라인(:187)·§9 Proposal 출력(:256)·§9.1 outcome types(:285-339, 단일 심볼)·§10 결정론(:343) | §12 positive-expectancy 증명(:438)·§13 replaceability(:470) |
| **RFC-004** 시장 | §7 시장상태 일부(:179, bar OHLCV)·§9 market data = Critical Input(:233-260) | §8 volatility/regime 전체(:206)·§11 Korean structure 대부분(:294) |
| **RFC-005** 실행 | §7 Approved-Intent path=Normal Commitment Flow(:187-214)·§11 UNKNOWN 표현(:314-343) | §8 slicing/최적실행(:217-248)·§9 TCA 전체(cost-realism만 §2) |
| **RFC-006** 리스크 | §9 자명한 고정 size 1건(:247) | §7 VaR/ES(:188)·§8 netting(:219)·§11 통계 유의성(:308) — **대부분 이연** |
| **RFC-008** DSL | §7 authoring(:206)·§8 Proposal-only-output(:249-275)·§9 결정론/isolation(:278)·§10 consuming layers(:321-353) — **대부분 tos.dsl 기구현** | 없음(코어 전체가 슬라이스) |
| **RFC-010** 테스트 | §7 authored-strategy(:209)·§8 DSL containment(:239)·§9 hermeticity(:269)·§10 limits/live-gate(:301) | 커버리지 수치 목표(config) |
| **ADR-DEV-010** 백테스트 | §7 admissibility bar 中 cost-realism·no-look-ahead·reproducible(:155-171) | §7-8 population/significance·not-overfit(:163-192) — **슬라이스는 edge 미증명**(§7-2) |

**판정 3 — 설계 문서 분해: 4편(수평 30-ADR 재분해 아님; runtime 컴포넌트 축 수직 분해).**

| # | 설계 문서 (owning runtime) | 주 원천 | 예상 신규 pkg | 착수 |
|---|---|---|---|---|
| **D-E1** | 결정 파이프라인 + Execution Coordinator 이벤트 코어(단일 코어=백/라이브 패리티) | RFC-003 §7·RFC-005 §7·RFC-002 §10.7·엔진 §3-2 | `tos.engine` | **1st(단독)** |
| **D-E2** | Market-Data → Decision Context Capsule(Critical Input 구성) | RFC-004 §9·§7·ADR-002-018(capsule)·RFC-008 §10·ADR-002-008(time) | `tos.marketfeed` | D-E1 후 ∥ |
| **D-E3** | 이벤트 백테스트 + paper fill 모델(cost-realism·패리티·차등 오라클) | ADR-DEV-010(스코프 한정)·RFC-005 §9·RFC-004 impact·엔진 §3-2/3-3b/3-4 | `tos.backtest` | D-E1 후 ∥ |
| **D-E4** | Order Construction Service + Broker Egress Gateway + Broker Adapter(paper 송신) | RFC-005 §7 tail·§11·ioc·egress·cur·brokercap·KIS Profile INSTANCE(트랙 d) | `tos.egressgw`+`tos.brokeradapter` | D-E1 후 ∥ |

착수 순서: **D-E1 선행 단독**(오케스트레이션 인터페이스 확정) → **D-E2·D-E3·D-E4 병렬**(각각 D-E1
인터페이스 의존; D-E3는 D-E2의 capsule 출력을 공동설계). DSL 전략 인스턴스(구체 단순 전략 1개 저작)는
tos.dsl 기구현이라 **경량** — D-E1의 선(先)-de-risking 스파이크로 흡수(별도 설계 문서 불요).

**판정 4 — 슬라이스는 지금 착수 가능하되, 산출은 provisional이다.** paper 주문은 `environment:
non-live-test`(register §3:88 — 유일 확정 scope 값) 스코프라 live-track 게이트(P0-2 live bounds·G7
restricted-live·Live-Armer) **불요**. 그러나 G2 프로덕션 canonicalization 미결(register §6:132 "EV-L2+ 실행
전 필요")·P0-1/P0-3 미완(register §4:108) 때문에 슬라이스 증거는 **EV-L2 PASS가 아니라 엔지니어링-통합
provisional 산출**로 스코프해야 한다(§4·§7-3).

**미결/운영자 판단(요지, 전문 §7)**: (A) **Part-2/3 설계 비준 위임 미결** — 2026-07-25 위임 자동비준은
"남은 ADR-002 구현" 스코프였고 엔진 설계는 그 밖(§6-3). **[해소 2026-07-29: 운영자 지시로 Part-2/3 설계
비준도 위임 자동비준 연장 — §6-3 해소 주석 참조.]** (B) 슬라이스 목표 = 엔지니어링-통합(provisional,
지금 착수) vs 정식 EV-L2(G2/P0-1/P0-3 차단) 택일. (C) ADR-DEV-010 admissibility 스코프 한정(§7-2). (D)
`tos.egressgw` 명명이 `tos.egress`(ADR-002-013 QCC 커널) 잠식 금지(§7-4).

---

## 1. 슬라이스 #1 정의 (경계)

엔진 메모 §3-1:59-62 정의를 원천으로: **"DSL로 표현한 단순 전략 1개 → 이벤트 기반 백테스트 → paper 주문
1건 — 을 끝까지 뚫는 … 슬라이스에 필요한 ADR만 선별 분해(RFC-005 실행 모델 + RFC-008 DSL 코어 + RFC-004
시장 모델 일부)."**

**포함(IN)**:
1. **단일 심볼·단일 전략.** RFC-003 §9.1:327-331의 atomic unit 중 **per-instrument target(one Proposal)**만.
   portfolio vector(다심볼 set)는 이연. no-action(hold)/explicit-flat(target=0) outcome은 포함(RFC-003
   §9.1:292-301 — tos.dsl.outcome 기구현).
2. **단일 이벤트 코어 = 백테스트/라이브 패리티 구조.** 엔진 메모 §3-2:63-65 — "백테스트와 라이브가 단일
   이벤트 기반 코어를 공유." 같은 결정 파이프라인·같은 Normal Commitment Flow 순서를 백테스트 이벤트와
   paper 이벤트가 공유(구조적 괴리 축소). 이것이 NT에서 훔치는 "Rust가 아니라 구조."
3. **Normal Commitment Flow 전 단계 실통과(happy path).** RFC-005 §7:193-199의 12단계를 실제 이벤트로 1회
   통과 — 술어 28+패키지 seam이 실제 입력을 받는 첫 실증(엔진 메모 §3-1a:60).
4. **paper 주문 1건 = `environment: non-live-test`.** register §3:88의 유일 확정 scope 값. 모의 계좌 송신
   1건(라이브 아님).

**명시 제외(OUT, YAGNI — 엔진 메모 §3-5:74-75)**:
1. **멀티 거래소·나노초 클록·범용 자산.** KIS 단일·KRX 시간·분봉(+필요 시 틱).
2. **라이브 실주문.** GOV-001 제3행위·Live-Armer 미지정(role-scheme :20 fail-closed).
3. **최적실행·slicing.** RFC-005 §8:217-248(Almgren-Chriss/VWAP/TWAP) 전체 이연 — 단일 주문은 slice 불요.
   §8:245-246 "concrete slicing algorithm … modeling and configuration choices."
4. **통계적 edge 증명.** RFC-006 §11 population/significance·ADR-DEV-010 §7:163 — 슬라이스는 **기계 실증**,
   전략 우위 증명 아님(§7-2 핵심 긴장).
5. **다심볼 portfolio vector·all-or-none 상호의존.** RFC-003 §9.1:333-337·RFC-008 outcome `PortfolioVector`
   (tos.dsl 기구현이나 슬라이스 미사용).
6. **완전 Evidence Store 런타임(durable/replay/integrity).** ADR-002-016 ENGINE(register G5:135) 이연 —
   슬라이스는 provisional 증거 sink(`tos-evidence/` 예약 경로, role-scheme :35-36)만.

---

## 2. RFC 조항 하중 지도 (anti-phantom: 인용 전 grep·file:line)

각 RFC의 §3 Scope/Non-Scope가 소유권 경계를 명문화하며, **Non-Scope 항목이 곧 슬라이스가 재구현하지 않고
소비하는 기존 패키지의 ADR 소유자를 열거한다**(§3 seam 지도의 규범 근거).

### 2-1. RFC-005 실행 (슬라이스 실행 경로의 척추)
- **Realize.** §7:187-214 Approved-Intent Execution Path. 규범 원천 = ADR-002-002 §11 Normal Commitment
  Flow(:190). §7:193-199이 12단계 열거(§0 판정 1). §7:210-213 "SHALL NOT invent, default, normalize,
  round, or repair any broker-command field" — 슬라이스 egress 층의 fail-closed 계약. §11:314-343 UNKNOWN
  표현(§5 fault-injection 접합).
- **Defer.** §8:217-248 slicing/최적실행(§1 OUT-3). §9 TCA 전체 — 단 §9의 **cost-realism 부분**은 백테스트가
  ADR-DEV-010 §7:159-161을 통해 소비(realize).
- **Non-Scope(소비만, §3:82-97).** trade 판단(RFC-003)·canonical command/OCP/economic-effect(ADR-002-020=ioc,
  :86-87)·capacity(ADR-002-002=rcl, :88-89)·action-flow budget(ADR-002-022=afg, :90-91)·final-egress
  currentness(ADR-002-024=cur, :92-93)·venue tradability(ADR-002-019=venue, :94)·impact 모델(RFC-004).

### 2-2. RFC-008 DSL (대부분 기구현 — tos.dsl)
- **Realize.** §7:206 authoring surface·§8:249-275 Proposal-only-output(§8:256-258 effect-free Proposal
  Builder — 부작용 없음·capacity 미예약; §8:259-261 exact Capsule identity+digest 바인딩; §8:262-264 no
  wildcard/"latest")·§9:278 결정론/isolation·§10:321-353 consuming layers. §10:327-331 "Critical Input,
  always"(어떤 datum도 ADR-002-018 지배)·§10:347-350 "UNKNOWN is restrictive."
- **Defer.** 없음 — RFC-008 코어 전체가 슬라이스이나, **layer 2(capability-restricted eval)·layer 3(isolation
  boundary)·DCE-INV-005 mechanism verification·numeric bounds는 tos.dsl 미구현**(dsl/__init__ :20-26 자기
  선언) → 슬라이스 배선/신규(§3).

### 2-3. RFC-003 결정 (파이프라인 골격)
- **Realize.** §7:187 pipeline·§8:224 inputs·§9:256 Proposal output·**§9.1:285-339 outcome types**(no-action
  :292-295·explicit-flat :296-301·"invalid context is not a decision" :320-326·atomic unit :327-339)·§10:343
  결정론. §9.1은 ADR-DEV-007 SOS-INV-001/002/006을 결정층 규범으로 채택(:288-289).
- **Defer.** §12:438 positive-expectancy(증거 한계)·§13:470 replaceability(다전략 전제 — 슬라이스 단일 전략).

### 2-4. RFC-004 시장 (일부만)
- **Realize.** §9:233-260 Market Data as Critical Input — 어떤 시장 datum도 ADR-002-018(capsule) 지배
  (:235-238); §9:242-243 "admitted Critical Input with source identity, continuity, and provenance, never
  by unattributed fetch"; §9:256-257 관측시각은 trustworthy-time(ADR-002-008) 기반. §7:179 시장상태 일부
  (bar OHLCV만).
- **Defer.** §8:206 volatility/regime 전체·§11:294 Korean structure 대부분(세션시각만 필요 — KIS 사실은
  비규범 Broker Capability Profile INSTANCE[트랙 d]로).
- **Non-Scope(:77-90).** tradability(ADR-002-019=venue)·Critical Input 정의/provenance(ADR-002-018=capsule).

### 2-5. RFC-006 리스크 (대부분 이연)
- **Realize.** §9:247 자명한 고정 size 1건(단일 주문 sizing은 상수). 그 이상 없음.
- **Defer.** §7:188 VaR/ES·§8:219 netting·§10:280 drawdown·§11:308 positive-expectancy 방법론 전체.
- **Non-Scope(:84-99).** capacity(ADR-002-002=rcl)·Aggregate Risk(ADR-002-021=are)·Hard Safety
  Envelope(RFC-001 §5.20)·protective 분류(ADR-002-001=protective).

### 2-6. RFC-010 테스트 + ADR-DEV-010 백테스트 admissibility
- **Realize.** RFC-010 §7:209 authored-strategy 결정론/isolation/containment·§8:239 DSL containment·§9:269
  hermeticity·§10:301 테스트 한계/live-gate. **ADR-DEV-010 §7:155-171 admissibility bar 中**: cost-realism
  (:159-161, RFC-005 §9 apparatus)·no-look-ahead(:165-166, 모든 입력이 context timestamp 경계)·hermetic/
  reproducible(:167-168, ADR-DEV-002; 헤더 §7:176/§8:195/§9:219).
- **Defer/스코프 긴장.** ADR-DEV-010 §7:163-164 population/significance·§7:169-171 not-overfit·§8:184-192
  disqualifier(unrepresentative population 등) — **슬라이스 단일-런 백테스트는 이 바를 원리적으로 통과
  불가**(§7-2). RFC-010 §3 Non-Scope: replay 프로토콜(ADR-002-016)·acceptance(VER-002-001)·admission
  (ADR-002-029=sci)·live 승격(ADR-002-025=rlp).

### 2-7. ADR-DEV 실측 요약
- **ADR-DEV-001**(DSL Realization) §7:176 Realization Form·§8:205 Enforcement — **tos.dsl 기구현**(dsl/__init__
  :3-5 계약 인용). 슬라이스는 소비만.
- **ADR-DEV-007**(Output Semantics) §7:183 No-Action vs Explicit-Flat·§8:206 Atomic Unit — 내용은 RFC-003
  §9.1:288-289로 미러(SOS-INV-001/002/006). tos.dsl.outcome 기구현.
- **ADR-DEV-010**(Backtest) — §2-6·§7-2.
- **ADR-DEV-002**(Reproducibility) §7:176 identity·§8:195 behavioral·§9:219 recorded input set — 백테스트
  재현성 근거(ADR-DEV-010 §7:167-168 경유).

---

## 3. 기존 패키지 seam 지도 (REUSE / WIRING / NEW)

**구조 실측(패키지 docstring 원천)**: 32 패키지는 전부 **순수 결정 커널** — frozen pydantic 모델 + **주입된
스칼라를 소비해 bool/verdict를 생산하는** conservative fail-closed 술어. 어느 것도 transmit/serialize/sign
않고, 어느 것도 clock을 읽지 않는다(ioc/__init__ :18-24·brokercap/__init__ :11-15·venue/__init__ :25-33·
time/__init__ :7-14). **각 패키지가 "future owning runtime"을 명시 위임**한다:
- ioc/__init__ :20-24 — "conformance-decision kernel, not a serializer / signer / egress engine … the
  owning runtime (a future **Order Construction Service / Broker Egress Gateway**) enforces them."
- brokercap/__init__ :13-15 — "produces decision bools / scalars; the owning runtime (a future **Broker
  Adapter**, ADR §19/§27) enforces them."
- venue/__init__ :28-30·time/__init__ 등 동형. **⇒ 슬라이스의 신규 표면 전체 = 이 owning runtime들.**

RFC-002(part-1-foundation) owning-actor roster :553-574가 그 runtime 명부를 확정: **Order Construction
Service**(:553)·**Broker Egress Gateway**(:553,566)·**Venue Constraint Gate**(:554)·**Risk Capacity
Ledger**(:557 sole mutation authority)·**Execution Coordinator**(:557,565,574)·**Broker Adapter**(:565,566).

### 3-1. REUSE (기구현 술어/모델 — 재저작 불요)
| seam 단계(RFC-005 §7 순서) | 패키지·심볼(file:line) |
|---|---|
| 전략 평가·Proposal 조립 | dsl: `evaluate`/`build_proposal`/`Proposer`/outcome(dsl/__init__ :70-98); capsule 읽기(dsl/__init__ :12) |
| Decision Context 모델 | capsule: `DecisionContextCapsule`/`CriticalInputSnapshot`/`FieldState`(capsule/__init__ :46-53) |
| deterministic candidate construction | ioc: `compile_command`/`command_conforms`/`OrderConformanceProof`(ioc/__init__ :76-99) |
| venue admissibility | venue: `session_phase_admits`/`order_shape_admissible`/`OrderAdmissibilityDecision`(venue/__init__ :102-152) |
| conservative economic-effect | ioc `EconomicEffectEnvelope`=rcl `CapacityVector`(ioc/__init__ :33-34, 5번째 edge) |
| aggregate-risk / action-flow / RCL commit | are·afg·rcl(패키지 기구현; 슬라이스는 술어 호출) |
| conformance proof / attempt binding | ioc `OrderConformanceProof`/`mutation_fence_holds`(ioc/__init__ :86-99) |
| final-egress currentness | cur·egress(ADR-002-024/013 커널; egress/__init__ :1 QCC 모델) |
| broker capability gate | brokercap: `capability_admissible`/`fqp_adequate`/`environment_binding_ok`(brokercap/__init__ :58-92) |
| trustworthy time 술어 | time: `session_open_positively`/`freshness_verdict`/`snapshot_age_admissible`(time/__init__ :60-78) |
| 이벤트 인과 순서 | ordering: `compare_order`(ordering/__init__ :19); 디지털 substrate canonical(canonical/__init__ :25-43) |
| 증거 모델 | evidence: `SafetyEvidenceEnvelope`/`ReplayCapsule`/`compute_replay_result`(evidence/__init__ :54-100) |

### 3-2. WIRING (주입 입력 구성 + 술어 순서 배선 — 신규 배선, 술어 재사용)
| 배선 | 무엇을 어느 술어에 공급 | 소유 설계 |
|---|---|---|
| market bar → Critical Input Snapshot → capsule | RFC-004 §9:242-243 admitted Critical Input(source/continuity/provenance) → dsl.evaluate 입력 | D-E2 |
| bar timestamp → 주입 time 좌표 | time은 clock 미독(time/__init__ :7-9) → 백테스트=bar ts, paper=주입 clock; `freshness_verdict` 입력 | D-E2 |
| KRX 세션시각 → `SessionPhase` opaque token + venue policy | venue `session_phase_admits`(SessionPhase=주입 opaque token, venue/__init__ :42-44); KIS 사실은 Profile INSTANCE(트랙 d) | D-E2/D-E4 |
| KIS Broker Capability Profile INSTANCE → brokercap | `BrokerCapabilityProfile`/`RequiredCapabilitySet`(brokercap/__init__ :79-92) 주입값; **P0-2**(register §1:50) | D-E4 |
| Normal Commitment Flow 순서 배선 | RFC-005 §7:193-199 12단계를 ADR-002-002 §11 순서로 술어 순차 호출 | **D-E1(핵심)** |

### 3-3. NEW (owning runtime — 존재하지 않음)
negative-grep 실측: `ls tos/src/tos/*engine*/*backtest*/*event*/*feed*/*gateway*/*market*` → **매칭 0**(부재
확정). 신규 저작 대상:
1. **Execution Coordinator 이벤트 코어**(D-E1) — RFC-002 §10.7·roster :557,565,574. 결정 파이프라인
   (RFC-003 §7) + Normal Commitment Flow 시퀀서. 백/라이브 단일 코어(엔진 §3-2).
2. **Market-Data feed → Capsule adapter**(D-E2) — RFC-004 §9. `tos.marketfeed`.
3. **이벤트 백테스트 + paper fill 모델**(D-E3) — ADR-DEV-010 cost-realism + RFC-005 §9. `tos.backtest`.
   차등 오라클: `shared/backtest`(실재 — adapter.py·ats_simulator.py·bootstrap.py 실측)를 **문서/오라클로
   대조**(엔진 §3-3b:69-70) — import-firewall(전략 B) 때문에 `shared/*` 직접 재사용 불가·`shared/determinism/
   lookahead_guard.py`(실재)도 지식 참조일 뿐, tos/는 look-ahead 가드 **네이티브 재저작**.
4. **Order Construction Service + Broker Egress Gateway + Broker Adapter**(D-E4) — RFC-002 roster :553,565,566.
   `tos.egressgw`+`tos.brokeradapter`. ⚠ `tos.egress`(ADR-002-013 QCC 커널, egress/__init__ :1)와 명명 충돌
   금지(§7-4).
5. **provisional 증거 sink**(D-E1 부속) — 완전 Evidence Store 런타임(ADR-002-016 ENGINE·G5) 아님.

---

## 4. Phase-0 / bounds 의존 (paper=non-live 스코프)

- **소비 scope 값**: `environment: non-live-test`(register §3:88 — 유일 확정 scope 값; 나머지 scope TBD 62/
  null 26). 슬라이스 paper 주문이 정확히 이 값에서 돈다. brokercap `environment_binding_ok`(brokercap/__init__
  :67)이 이 바인딩을 게이트.
- **불요 게이트(라이브 아님)**: P0-2 broker-specific **live** bounds 측정(register §1:50)·G7 첫 restricted-live
  scope(register §6:137)·Live-Armer(role-scheme :20 미지정 fail-closed). paper는 GOV-001 제3행위 밖.
- **소비 bounds 키(대부분 미승인 — P0-1)**: register §3:89-90 확정값은 **12개뿐**(bounds 7 PROPOSED·limits 5).
  슬라이스 직접 접촉 후보: DSL 평가 time/resource bound(**DCE-INV-007** — register §8-1:223 `strategy-dsl:540-546`,
  프로파일에 **키 자체 부재**·신설 대상)·`MAX_clock_drift_ppm 200`·time freshness 계열(§8-1:204-211 신설
  대상 다수). ⇒ **슬라이스가 소비할 bounds 다수가 null/미신설** — provisional 값으로 배선하되 승인 전이므로
  증거는 provisional(§7-3).
- **G2 프로덕션 canonicalization 의존**: register §6:132 — "프로덕션 canonical serialization·digest 알고리즘
  승인(`ev-l1-provisional-0`·sha256 = 비프로덕션) … **EV-L2+ 실행 전 필요**." tos.capsule/canonical/evidence는
  전부 `EVL1ProvisionalCanonicalizer`/`EV_L1_PROVISIONAL_*`(capsule/__init__ :39-45·canonical/__init__ :34-42·
  evidence/__init__ :62)만 보유. **슬라이스가 정식 EV-L2 PASS를 노리면 G2 선결**; 엔지니어링-통합 provisional
  이면 provisional canonicalizer로 진행 가능(산출은 provisional).
- **acceptance 차단**: register §4:108 — P0-1/P0-3 완료 + 정식 실행·서명 전에는 어떤 행도 READY/PASS 불가.
  ⇒ 슬라이스 산출은 99행 L1 슬라이스 증거 **후보**이나 자동으로 EV가 되지 않음.

---

## 5. Fault-injection 접합점 (EV-L2+ 트랙 b — 표기만, 설계 안 함)

엔진 메모 §3-4:71-73(파이프라인 변형: 결정론적 리플레이·장애 주입·보정 게이트) 및 §2:48-49(비동기·장애)의
접합점. **지금은 접합 위치만 표기**하고 주입 시나리오 설계는 후속 EV-L2 트랙 소관.

| 접합 | 위치(패키지/설계) | 나중에 주입될 것 |
|---|---|---|
| **J1 실행 UNKNOWN/retry** | RFC-005 §11:314-343 SAFE-021; Broker Egress Gateway(D-E4) | ack 드롭·중복 ack·부분후 timeout — UNKNOWN은 worst-credible 소비, blind resubmit 금지(:326-328) |
| **J2 time 불연속/staleness** | time `HealthState`/`freshness_verdict`; feed adapter(D-E2) | feed gap·clock jump·stale bar |
| **J3 크래시-복구 재조정** | recon·sbr·orthostate·ioc `recovery_revives_nothing`(ioc/__init__ :100-104); 이벤트 코어(D-E1) 재기동 | `SEND_STARTED` 후 크래시=`POTENTIALLY_LIVE`(RFC-005 §7:198-199·§11:335-337) |
| **J4 부분체결/post-trade 괴리** | posttrade·nontrade; fill 모델(D-E3/D-E4) | 부분·과다·phantom fill |
| **J5 보정 편차** | wdr deviation budget(엔진 §3-4:73); 백/paper 패리티(D-E3) | paper-fill vs backtest-fill 편차 > budget |

---

## 6. 설계 사이클 분해 제안

### 6-1. 4편 근거 (수평 재분해 회피)
엔진 메모 §3-1:58 경고 — "RFC-003~007을 또 하나의 30-ADR 수평 시리즈로 분해하는 관성은 좌초 경로." 본 분해는
**RFC 조항 축이 아니라 owning-runtime 컴포넌트 축**(§3-3의 5 신규 표면)으로 수직 절단한다. 4편 = §0 판정 3 표.
각 편은 기존 품질 파이프라인 **전체**(저작→1차 심사→독립 비평→개정→비준→구현→적대적 코드 리뷰) 적용,
anti-phantom·구조 파생>자기신고·음극성 `is False`·뮤테이션 canary 등 시리즈 교훈 승계.

### 6-2. 착수 순서·병렬성
- **Phase A**: **D-E1 단독 선행**. 이벤트 코어가 Normal Commitment Flow 시퀀싱 인터페이스를 확정해야 나머지
  3편이 그에 배선. D-E1 착수 직전 **de-risking 스파이크**(단순 전략 1개를 tos.dsl로 저작해 Proposal 1건
  emit — tos.dsl이 실전략을 한 번도 안 받아봤으므로 §8:256-258 effect-free builder 실검증).
- **Phase B**: **D-E2 · D-E3 · D-E4 병렬**(각 D-E1 인터페이스 의존). D-E3는 D-E2의 capsule 출력을 소비하므로
  경계 계약을 공동설계(D-E2 소폭 선행). D-E4는 KIS Profile INSTANCE(트랙 d) 착지 여부를 구현 시점 실측해
  착지 시 값 배선, 미착지면 provisional 값·명시 이연(venue/PR seam 선례 — 병렬 트랙 in-flight 처리 규율).
- **seam 규율**: 각 설계는 병렬 트랙이 사이클 중 착지시키는 심볼을 구현 시점 디스크 재실측(WDR/VTG 선례 —
  "WIP 무접촉" 사유가 사이클 중 소멸할 수 있음).

### 6-3. 비준 권한 (⚠ 운영자 미결 — 강조)
**2026-07-25 운영자 위임 자동비준은 "남은 ADR 구현"(ADR-002 시리즈) 스코프였다**(MEMORY 인덱스 원천).
D-E1~D-E4는 **Part-2/3 RFC 실현이지 ADR-002가 아니다** — 따라서 **위임 자동비준이 적용되지 않는다.** 각
설계의 비준 경로(운영자 명시 비준 vs 새 위임 vs project-workflow 비준[P0-4 동형])는 **운영자 결정 사항**이며
본 서베이는 이를 미결로 표기한다. (예외 후보: ADR-002-016 ENGINE 런타임[Evidence Store]은 ADR-002 스코프라
위임이 포괄할 수 있으나, 슬라이스 #1은 그 완전 런타임을 이연하고 provisional sink만 쓰므로 §6에서 제외 —
§1 OUT-6.)

> **[해소 2026-07-29, 오케스트레이터 주석]** 본 서베이 저작 완료 직후 운영자 지시로 **Part-2/3 설계
> 비준도 위임 자동비준으로 연장**되었다(ADR-002 때와 동일 조건 — 독립 비평 리뷰 통과·upgrade 조건 충족을
> 오케스트레이터가 검증한 뒤 "운영자 위임 자동 비준(2026-07-29 연장 지시)"으로 기록·즉시 진행; 품질
> 파이프라인[저작→1차 심사→독립 비평→개정→구현→적대적 코드 리뷰→게이트] 전부 유지). **ADR acceptance
> (EV 실행 증거)·live authorization은 위임 밖 별개 게이트로 잔존.** D-E1~D-E4는 이 경로로 진행한다.

---

## 7. 리스크·미결 (운영자 판단 필요)

**7-1. 관측: 패키지 수 32 vs 브리프 "30".** 디스크 실측 `ls -d tos/src/tos/*/ | grep -v __pycache__` = **32**
(afg are authority brokercap canonical capsule cur dsl egress evidence failuredomain hag iap ioc liveauth
nontrade ordering orthostate posttrade protective rcl recon replacement rlp sbr sci sir spg stm time venue
wdr). "30"은 ADR-002 문서 계수와의 conflation로 판정 — 2 잉여는 **PROMOTE 공유 substrate** `tos.canonical`
(capsule에서 승격, canonical/__init__ :1-9)·`tos.ordering`(evidence/time에서 승격, ordering/__init__ :1-15)로,
독립 ADR 없음. 이상 아님(사실 기록). pytest 7482는 본 서베이에서 미실행(재실측 미수행 — 추측 표기).

**7-2. ⚠ ADR-DEV-010 admissibility 스코프 긴장(설계 리스크).** ADR-DEV-010 §8:184-192는 "unrepresentative
population(too few decisions, a single favorable run)"을 **disqualifier**로 규정하고 §8:196-197 "not 'weaker
evidence' … it is out." **슬라이스 #1의 단일-전략 단일-런 백테스트는 이 바를 원리적으로 통과 불가**(edge를
증명하지 않으므로). ⇒ D-E3 설계는 슬라이스 백테스트를 **"기계·패리티 실증"**(이벤트 코어가 백/paper에서
동일 결정 생산·cost-realism 적용·look-ahead 구조적 불가)으로 **명시 스코프**해야 하며, "가설 증거로서의
admissible backtest"로 제시하면 ADR-DEV-010 §8로 **자기-disqualify**된다. cost-realism·no-look-ahead·
reproducible(§7:159-168)만 realize하고 population/significance·not-overfit(§7:163-171)은 명시 이연.

**7-3. ⚠ 슬라이스 목표 이원성(운영자 택일).** (a) **엔지니어링-통합**: provisional canonicalizer·provisional
bounds로 seam 통합·fail-open 발견(엔진 §3-1의 실가치) — G2/P0-1/P0-3 **무의존, 지금 착수 가능**, 산출은
provisional. (b) **정식 EV-L2 수용**: G2(register §6:132)·P0-1·P0-3·독립 서명 **선결**(register §4:108). 
**권고: (a) 선행** — 슬라이스 가치(seam 통합 발견)는 (a)로 완결되고 정식 수용은 나중 재실행. 이로써 슬라이스가
Phase-0 게이트 임계경로에서 분리된다. 운영자 확정 필요.

**7-4. ⚠ 명명 충돌.** `tos.egress`(ADR-002-013 QCC commit-proof 커널, egress/__init__ :1)가 이미 "Egress
Gateway"를 이름에 포함. D-E4의 Broker Egress Gateway **런타임**은 별도 패키지(`tos.egressgw` 등 제안)로 —
커널/런타임 혼동은 seam fail-open 온상. D-E4 설계 §명명 절에서 확정(register §9 명명 판단 지점 규율 승계).

**7-5. import-firewall vs shared/ 지식 이전.** 전략 B 방화벽(설계 #1)이 `shared/*` 직접 import 차단 →
`shared/backtest`(실재)·`shared/determinism/lookahead_guard.py`(실재)·`shared/kis`는 **차등 오라클·지식
참조**일 뿐(엔진 §3-3:66-70). tos/는 네이티브 재저작 — REUSE 아님·NEW. 코드 차용 필요 시 SCI(ADR-002-029)
게이트·라이선스 선행(엔진 §4.3:99-105).

**7-6. KIS Profile INSTANCE(트랙 d) 의존.** D-E2 세션시각·D-E4 brokercap 값이 비규범 Broker Capability
Profile INSTANCE에 의존(P0-2, register §1:50). 초안 작성 중(트랙 d) — 미착지 시 D-E4 provisional 배선·명시
이연. KIS 사실은 tos-spec 규범 텍스트 금지([[tos-spec-broker-agnostic]]).

**7-7. Part-2/3 비준 권한(§6-3 재게시).** 저작 시점 미결이었으나 **해소(2026-07-29): 운영자 지시로 위임
자동비준 연장 — §6-3 해소 주석 참조.**

**7-8. 스테일 문구 상속.** IMPLEMENTATION-PLAN-002:3 "no implementation code has been written"은 현 32패키지와
모순(register §10-2 기록). 엔진 설계 착수 시 이 스테일이 오독 유발 가능 — 패치 트랙(register §11 D4)과 조율.

---

## 8. 실측 규율 기록
- 모든 file:line 인용은 2026-07-29 실측값(설계/RFC 개정 시 행 이동 — 재사용 시 재실측).
- 부재 주장 negative-grep: §3-3(신규 패키지 부재 `ls … → 매칭 0`)·§7-1(패키지 32 전수 나열).
- 미실행 표기: pytest 7482 미재실행(§7-1 — 추측). RFC-002 roster는 part-1-foundation grep :553-574 실측
  (파일 suffix 미확정 — RFC-002 §10.7/§10.8은 RFC-005 §7:191-192 경유 인용).
- 본 서베이는 설계가 아니다: EV 매핑·소유권·seam 채택의 규범 판정은 후속 D-E1~D-E4가 자체 수행(엔진 §5:110-111).
