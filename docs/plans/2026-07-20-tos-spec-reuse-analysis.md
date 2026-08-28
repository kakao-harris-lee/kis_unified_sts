# tos-spec 재사용성 분석 및 리팩토링 유불리 판정 (2026-07-20)

> **목적**: tos-spec을 kis_unified_sts 프로젝트 안에서 구현할 때 (1) 기존 코드가 어느
> 정도 재사용 가능한지, (2) 기존 시스템 리팩토링과 그린필드 구축 중 무엇이 유리한지를
> 근거와 함께 판정하고, 설계 단계 진입의 출발점을 확정한다.
>
> **조사 방법**: 병렬 2-트랙 탐사(트랙 1: tos-spec 47개 구현 컴포넌트 맵 추출,
> 트랙 2: shared/·services/ 전 모듈 재사용성 인벤토리) + 결정에 핵심적인 제약 5건의
> 소스 spot-check + 종합 판정. 정량치는 근거를 명시한 **추정**이며 범위로 제시한다.
>
> **관련 문서**: [ARCHITECTURE-GATE-STATUS §7/§8](../../tos-spec/src/part-1-foundation/ARCHITECTURE-GATE-STATUS.md) ·
> [IMPLEMENTATION-PLAN-002](../../tos-spec/src/part-1-foundation/verification/IMPLEMENTATION-PLAN-002.md) ·
> [2026-07-08 신규 아키텍처 Gap Analysis](2026-07-08-new-architecture-gap-analysis.md) ·
> [2026-07-15 tos-spec Part 3 ADR 결정 지도](2026-07-15-tos-spec-part3-adr-decision-map.md)

---

## 0. 결론 요약 (TL;DR)

1. **재사용 가능성은 낮고 편중되어 있다.** 기존 코드는 spec의 *권한 없는 순수 계산
   계층*(지표·백테스트·설정·인프라 유틸)에서만 강하게 재사용되고, spec 노력의
   대부분을 차지하는 **safety core / evidence / DSL-runtime / egress-admission /
   governance**에는 재사용 가능한 substrate가 사실상 존재하지 않는다(≈0%).
2. **정량 추정**: (a) spec 구현 표면 중 기존 코드가 실질적 head-start를 주는 비율
   ≈ **12~18% (effort-weighted)**; (b) 기존 runtime 152k LOC 중 TOS runtime으로
   살아남는(리팩터 후) 비율 ≈ **10~15%**, source-material까지 관대하게 세면 ~20~25%.
3. **판정: 그린필드가 유리하다.** 단, 별도 repo가 아니라 **동일 repo 내 그린필드
   `tos/` 패키지 + 기계적으로 강제되는 단방향 import firewall**(전략 B). in-place
   리팩토링(전략 A)은 SAFE-045상 구조적으로 불가능하며 운영 중인 paper/live 시스템
   오염 위험이 최대라 기각. 별도 repo(전략 C)는 live gate 시점에 재검토하는 후속 옵션.
4. **경계 배치 원칙**: *authority·ordering·integrity·containment을 보유하는 것은
   전부 그린필드(경계 안), 순수·무권한·evidence-producing 계산은 재사용(경계 밖에서
   단방향 import)*. 이 원칙이 IMPLEMENTATION-PLAN-002 §2 "greenfield TOS boundary"
   비준 대상의 정확한 배치를 결정한다.

---

## 1. 분석 프레임 — spec이 이미 정해둔 것

이 분석은 백지에서 출발하지 않는다. 비준된 스펙과 게이트 문서가 이미 절반을 정했다.

- **구현 진입은 승인 상태다.** ARCHITECTURE-GATE-STATUS §8:
  `Ready for implementation and test-harness work: YES` (ADR acceptance / restricted
  live / production은 전부 NO). §7이 13단계 엔지니어링 시퀀스를 정의한다.
- **안전 코어는 스펙 자체가 그린필드로 규정한다.** IMPLEMENTATION-PLAN-002 §2:
  RCL·Safety Authority·Trustworthy Time·Live Authorization·Egress Gateway·
  Reconciliation·Recovery Coordinator·Protective Action Controller·Safety Profile
  Validator는 "**not constrained by an existing trading implementation**"인 신규
  safety core다. 이 경계 자체가 비준 대상이며, 본 분석은 그 경계의 정확한 배치에
  근거를 공급한다.
- **broker-agnostic 원칙.** KIS 고유 사실(TR-id, 필드 의미론, 세션/rate 특성)은
  Broker Capability Profile 인스턴스 + Broker Adapter(ADR-002-004)에만 존재할 수
  있고 코어에는 들어갈 수 없다.
- **검증 규모.** EVIDENCE-REGISTER-002 372건 + EVIDENCE-REGISTER-DEV 98건, 전부
  NOT_IMPLEMENTED. 현 단계에서 허용되는 것은 EV-L1..L3(비전송·시뮬레이션)뿐이다.
- **선행 리팩토링 맥락.** [2026-07-08 gap analysis](2026-07-08-new-architecture-gap-analysis.md)가
  이미 "TA-Lib SoT + vectorbt + 선언형 YAML + Registry/Adapter로의 절반 진행된
  마이그레이션"을 판정해 둔 상태다. 이 트랙과 TOS 트랙의 관계는 §5에서 정리한다.

### 1.1 결정을 좌우한 소스 확인 사실 (spot-check)

| # | 확인 사실 | 소스 | 함의 |
|---|---|---|---|
| S1 | live 가부가 YAML `enabled` + Redis suspend 플래그로 토글됨 | `shared/execution/live_mode_guard.py`, `config/futures_live.yaml` | SAFE-045("non-live component SHALL NOT gain live capability by changing a runtime flag") **정면 비적합** → 기존 live 게이팅 경로는 재사용 불가 |
| S2 | runtime ledger에 hash-chain/integrity-anchor/append-only 원시요소 전무, orders/fills/trades는 TEXT-PK upsert 가능 | `shared/storage/runtime_ledger.py` | ADR-002-016 Evidence Store 기준 미달 — **최대 격차** |
| S3 | 코드베이스 전체에 consensus/quorum/writer-epoch/fencing substrate 부재 | 전역 grep (hit는 무관한 indicator "technical_consensus"뿐) | ADR-002-012 RCL(2f+1 quorum Safety Commit Log)은 기존 저장 계층에서 진화 불가 |
| S4 | 전략 순수성은 convention뿐 — ABC에 I/O 차단 구조 없음 | `shared/strategy/base.py` | RFC-008 "containment by construction" 불충족; denylist 래핑은 ADR-DEV-001이 명시적 비적합 판정 |
| S5 | executor가 broker 필드를 invent/default (`setdefault("custtype","P")`, KRX 기본값, ODNO fallback) | `shared/execution/executor.py` | ADR-002-020(no invent/default/round) 비적합 → 현행 주문 조립은 Canonical Broker Command compiler의 소재일 뿐 |

### 1.2 기존 코드베이스 규모

| 범위 | Python 파일 | LOC |
|---|---|---|
| `shared/` | 444 | 101,088 |
| `services/` | 170 | 51,474 |
| `tests/` | 733 | 164,761 |

KIS 결합(`shared.kis` import)은 프로젝트 전체 20개 파일에 국한 — 브로커 어댑터는
비교적 잘 격리되어 있다. 실주문 이그레스는 `OrderExecutor._send_kis_*`로 상당히
수렴되어 있으나 단일 choke point는 아니다(paper 경로 `VirtualBroker`가 별도, dead
경로 `KISClient.submit_ats_order` 존재).

---

## 2. 재사용 매트릭스

spec 47개 컴포넌트를 9개 family로 묶어 판정한다.
Verdict ∈ { **REUSE-AS-IS**(그대로) / **REUSE-AFTER-REFACTOR**(수정 후) /
**SOURCE-MATERIAL**(로직만 재작성 소재) / **NO-REUSE**(신규) }.

### F1. Safety Core & Authority
(Aggregate Risk Authority, **Risk Capacity Ledger**, Safety Authority, Hard Safety
Envelope Registry, Live Authorization, Trustworthy Time, Protective Action
Controller, Safety Profile Validator, Recovery Coordinator)

| 컴포넌트 | 기존 모듈 | Verdict | 근거 |
|---|---|---|---|
| Risk Capacity Ledger | `shared/risk` RiskManager (Redis persist) | **NO-REUSE** | RCL은 quorum-replicated deterministic Safety Commit Log(2f+1) + Writer Epoch fencing 요구. consensus substrate 부재(S3). Redis 단일 인스턴스와 아키텍처적으로 불연속. |
| Protective Action Controller / Recovery Coordinator | `services/kill_switch` | **SOURCE-MATERIAL** | fail-closed 센티널 + 이벤트 스트림 + 스크립트로만 해제되는 파일 센티널 — **의미론이 spec과 가장 근접한 기존 자산**. 그러나 monotonic Recovery Generation·closed barrier·quorum backing 부재. 의미론은 이식, runtime은 신규. |
| Live Authorization | `shared/execution/live_mode_guard.py` | **NO-REUSE** | S1. 플래그 토글 모델은 default non-live·scope-bound·revocable 모델과 개념적으로 반대. |
| Safety Authority / Envelope / Trustworthy Time / Aggregate Risk Authority / Profile Validator | 없음 | **NO-REUSE** | epoch-fenced authority, time-health-as-state, conservative projection(Potentially-Live/UNKNOWN/trapped), break-before-make — 대응 코드 없음. |

### F2. Egress & Order Construction
(Independent Approval, Intent Registry, Execution Coordinator, **Broker Egress
Gateway**, Cancellation Arbiter, Venue Constraint Gate, Order Construction, Action
Flow Governor, Currentness Sequencer & Final-Egress Admission)

| 컴포넌트 | 기존 모듈 | Verdict | 근거 |
|---|---|---|---|
| Broker Egress Gateway / Currentness Sequencer | `shared/execution/executor.py` | **NO-REUSE (runtime) / SOURCE-MATERIAL (KIS 지식)** | deny-first hard fence·per-send Egress Currentness Proof·Final Egress Trust Boundary 요구. 현행은 S1 플래그 게이팅 + S5 필드 invent. KIS REST/TR-id 지식 자체는 Broker Adapter 소재로 가치 큼. |
| Order Construction | executor 내부 payload 조립 | **SOURCE-MATERIAL** | deterministic compiler → Canonical Broker Command + Economic Effect Envelope + Conformance Proof 필요. 현행 조립 로직은 참고 소재. |
| Intent Registry / Independent Approval / Action Flow Governor / Cancellation Arbiter / Venue Constraint Gate | 없음 | **NO-REUSE** | immutable single-use intent, 독립 recomputation, RCL-serialized single-use Permit 등 대응 개념 부재. dead `submit_ats_order`는 폐기 대상. |

### F3. Decision & DSL
(Decision Service, **Strategy DSL**, DSL Enforcement, Authoring pipeline, LLM-value capture)

| 컴포넌트 | 기존 모듈 | Verdict | 근거 |
|---|---|---|---|
| Strategy DSL / Enforcement | `shared/strategy` ABC+Protocol, ~30 generators (17.3k LOC) | **NO-REUSE (runtime) / SOURCE-MATERIAL (알고리즘)** | S4. DSL은 17개 금지 효과가 *표현 불가능*해야 함(containment by construction). 알고리즘 콘텐츠(시그널 수식)는 이식 가능, runtime shape는 불가. |
| Decision Service | `services/decision_engine`, `stock_strategy` | **SOURCE-MATERIAL** | proposer-only·deterministic·Capsule-only 계약 부재. 구조 참고물. |
| LLM-value capture | `shared/llm/*` | **SOURCE-MATERIAL** | evaluation 중 live LLM 호출 금지 → seed와 함께 Capsule로 pre-capture. 기존 파이프라인은 값 소스. |
| Authoring pipeline | ComponentRegistry/decorator | **SOURCE-MATERIAL** | registry 패턴 참고. content-addressed artifact identity·AI 저작 독립 리뷰는 신규. |

### F4. Market-data & Context
(Context Integrity Service, Reconciliation, Position/Order Projection)

| 컴포넌트 | 기존 모듈 | Verdict | 근거 |
|---|---|---|---|
| Context Integrity Service | `services/market_ingest`, `shared/streaming`, Entry/ExitContext | **SOURCE-MATERIAL** | Critical Input provenance·immutable Snapshot·Decision Context Capsule·correction fan-out 부재. 어휘/구조 소재. |
| Reconciliation | executor inquire 경로 | **NO-REUSE** | per-field confidence·UNKNOWN-until-corroborated 모델 부재(브로커 응답을 그대로 신뢰). |
| Position/Order Projection | `shared/models` | **SOURCE-MATERIAL** | conservative/potentially-live projection 아님. dataclass 어휘만 재사용. |

### F5. Evidence-producing Models (RFC-004..007) — **최강 재사용 지점**

| 컴포넌트 | 기존 모듈 | Verdict | 근거 |
|---|---|---|---|
| Market/Execution/Risk/Hedge Models | `shared/indicators` (6.4k) + `shared/risk` filters (8.1k) | **REUSE-AFTER-REFACTOR** | indicators는 multi-backend + shadow-compare로 사실상 순수; risk 필터 로직은 evidence-producing model 소재. RFC-004..007은 "evidence-producing, no authority"라 계산 코어가 부합. 단 (i) Capsule-consuming 재배선, (ii) hermetic·no-authority 래핑 필요. `execution_venue "KRX"/"ATS"` 누수는 Broker Capability Profile로 이관. |

### F6. Evidence, Replay & Audit

| 컴포넌트 | 기존 모듈 | Verdict | 근거 |
|---|---|---|---|
| Evidence Store | `shared/storage/runtime_ledger.py` | **NO-REUSE (구조) / SOURCE-MATERIAL (Protocol/스키마)** | S2. append-only·pre-effect durability·integrity anchoring·gap detection 요구 대비 **최대 격차**. |
| Safety Commit Log substrate | 없음 | **NO-REUSE** | S3. 2f+1 quorum consensus product 필요. |
| Replay/Evidence Service | `shared/backtest/market_context_replay` | **REUSE-AFTER-REFACTOR** | deterministic replay + seeded RNG는 상당히 근접한 자산 → 리팩터로 흡수 가능. |
| Post-Trade Obligation Ledger | 없음 | **NO-REUSE** | 대응 부재. |

### F7. Testing & Verification Harness — **두 번째 최강 재사용**

| 컴포넌트 | 기존 모듈 | Verdict | 근거 |
|---|---|---|---|
| Backtest harness (ADR-DEV-010) | `shared/backtest` — LookaheadGuard, seeded ats_simulator, MLflow | **REUSE-AFTER-REFACTOR** | LookaheadGuard(off/warn/assert + fingerprint) + seeded 결정론은 no-look-ahead·hermetic·reproducible 요구의 핵심 자산. "never claims live edge"·완전 hermetic으로 강화 필요. |
| Fault-injection + evidence harness (EV-L1..L3) | 없음 (733개 테스트는 대부분 unit) | **NO-REUSE** | evidence package(manifest/jsonl timeline/sha256sums/독립 리뷰어 서명)는 신규 구축. pytest 자산은 관행 참고. |

### F8. Governance & Release-Admission
(Deployment/Identity, Restricted-Live Trial, Deviation, Incident, Telemetry
Conformance, Supply-Chain Admission, Egress Authority, Failure-Domain Matrix,
Human Authority)

| 컴포넌트 | 기존 모듈 | Verdict | 근거 |
|---|---|---|---|
| 전 항목 | 사실상 없음 | **NO-REUSE** | ~60종 artifact contract(YAML 템플릿은 tos-spec 측에 존재), content-addressed 아티팩트·hermetic build provenance·runtime attestation, Effective Principal Graph·phishing-resistant auth, evidence-backed failure-domain — 전부 신규. 기존 flag-gated 승격 절차는 SAFE-045와 상충. |

### F9. Operator & Ops Runtime

| 컴포넌트 | 기존 모듈 | Verdict | 근거 |
|---|---|---|---|
| Operator Control Interface | `services/dashboard`, kill_switch HALT | **SOURCE-MATERIAL** | Human HALT 의미론 + UI 소재. phishing-resistant auth·분리된 safety-critical control path로 재설계 필요. |
| Operator runtime governance (RFC-011) | 없음 | **NO-REUSE** | 대응 부재. |

### 횡단 인프라

| 모듈 | Verdict | 근거 |
|---|---|---|
| `shared/config` | **REUSE-AFTER-REFACTOR** | ConfigLoader·`${VAR}` 해석·Pydantic 견고. config version이 DSL 순수함수 서명의 일부. content-addressing 추가 필요. |
| `shared/resilience`·utils·exceptions·http | **REUSE-AS-IS** | 범용, 무권한. tos/에서 안전하게 import 가능. |
| `shared/streaming` StreamStage | **부분 REUSE / 부분 NO-REUSE** | non-safety telemetry에는 재사용. at-least-once Redis stream은 Safety Commit Log/Currentness Ordering Domain이 될 수 **없음** — safety-critical ordering 승격 시도 금지. |
| `shared/kis` (5.6k) | **SOURCE-MATERIAL** | KIS 지식(TR-id·엔드포인트·필드 의미론)은 Broker Adapter + Capability Profile로만. god-object 분해 + Final Egress Trust Boundary 내부로 confine. |
| `services/trading/orchestrator.py` (7.0k) | **NO-REUSE** | 레거시 모놀리스, 폐기 예정. |
| 디커플드 파이프라인 토폴로지 | **SOURCE-MATERIAL (참조 아키텍처)** | ingest→decision→risk→order→egress 관심사 분리는 TOS trading-plane 분해의 검증 자산. 단 failure-domain isolation이 evidence-backed 아니고 ordering이 at-least-once → runtime 재사용 아님. |

---

## 3. 정량 추정

### 3.1 spec 구현 표면 대비 기존 코드 커버리지 (effort-weighted)

family별 (spec 전체 노력 중 비중 추정) × (기존 코드의 실질 기여도) 가중 합산:

| Family | spec 노력 비중 | 기존 기여도 | 가중 기여 |
|---|---|---|---|
| F1 Safety Core & Authority | ~18% | ~5% | ~0.9% |
| F2 Egress & Construction | ~14% | ~10% | ~1.4% |
| F3 Decision & DSL | ~12% | ~15% | ~1.8% |
| F4 Market-data & Context | ~7% | ~20% | ~1.4% |
| F5 Evidence-producing Models | ~8% | ~65% | ~5.2% |
| F6 Evidence/Replay/Audit | ~10% | ~15% | ~1.5% |
| F7 Testing/Verification Harness | ~9% | ~45% | ~4.1% |
| F8 Governance/Release Admission | ~16% | ~2% | ~0.3% |
| F9 Operator & Ops | ~6% | ~20% | ~1.2% |
| **합계** | 100% | — | **≈ 17.8%** |

보수적으로 **하한 ~12%**, 관대하게 **상한 ~20%**. 가중치는 evidence-item 수가 아닌
판단 기반 추정이라 ±5%p 변동 가능.

> **핵심 진술**: "재사용률이 낮다"기보다 **"재사용이 spec의 쉬운 부분에만
> 존재한다"**. 재사용은 가장 안전하지 않은 EV-L1 계층(F5 모델·F7 하네스)에 집중되고,
> spec 노력의 절반 이상(F1+F2+F6+F8 ≈ 58%)을 차지하는 safety·evidence·governance
> 계층의 기여는 합쳐도 ~4%다.

### 3.2 기존 runtime 152k LOC의 TOS 기여율

| 모듈군 | LOC | TOS runtime 생존(리팩터 후) | source-material |
|---|---|---|---|
| indicators | 6.4k | ~5k | — |
| backtest | 8.0k | ~5.5k | — |
| config | 1.9k | ~1.5k | — |
| resilience/utils/http | 1.9k | ~1.5k | — |
| models | 0.9k | ~0.2k | ~0.5k |
| strategy | 17.3k | 0 | ~4k (알고리즘) |
| risk | 8.1k | ~1.5k | ~1.5k |
| streaming | 3.6k | ~1k (non-safety) | — |
| kis | 5.6k | 0 | ~1.7k |
| execution | 5.0k | 0 | ~1k |
| 기타 shared (~42k) | 42k | ~1k | ~2k |
| services 전체 | 51k | ~1k | ~5k |
| **합계** | **152k** | **≈18k (10~15%)** | **+≈16k** |

**~75~80%는 TOS에 기여하지 않는다** — 모놀리스, 대시보드 대부분, KIS god-object
구조, 플래그 게이팅 execution, Redis-stream safety 경로. **safety-critical 코어에
기여하는 기존 LOC는 사실상 0.**

---

## 4. 리팩토링 유불리 판정

### 4.1 세 전략 비교

| 기준 | (A) in-place refactor | (B) 동일 repo 그린필드 `tos/` | (C) 별도 repo |
|---|---|---|---|
| IMPLEMENTATION-PLAN §2 그린필드 위임 | ✗ 위반 | ✓ 충족 | ✓ 충족 |
| SAFE-045 non-live/live 분리 | ✗ **구조적 불가** (S1: live 경로가 동일 아티팩트에 플래그로 내재) | ✓ Phase 1 non-transmitting: tos/에서 egress 코드 도달 불가 | ✓ 가장 깨끗 |
| ADR-002-029 content-addressed release | △ 기존 빌드에 얽힘 | ✓ per-artifact 빌드는 repo layout과 직교 | ✓ 독립 provenance |
| hermetic test | ✗ 기존 .env/Redis 결합 상속 | ✓ tos/ 전용 hermetic 게이트 | ✓ |
| failure-domain evidence | ✗ 비증거 토폴로지 상속 | ○ 빌드/배포에서 증명(설계 필요) | ✓ |
| 2026-07-08 리팩토링 계획과의 관계 | 경쟁(같은 코드 동시 개조) | **상보**(dual-use는 shared/, 코어는 tos/) | 분리(dual-use 이점 상실) |
| 단일 운영자 유지비 | 최악(레거시+신규 얽힘) | **최선**(1 repo/툴체인/공유 lib) | 높음(2 repo, cross-repo dep) |
| 운영 중 paper/live 오염 위험 | **최대** | 낮음(import firewall) | 최소 |

### 4.2 핵심 통찰

1. **소스 트리 위치는 failure/trust 도메인과 직교한다.** SAFE-045는 *런타임
   capability 경로*와 *deploy/identity·credential 분리*에 관한 것이고,
   ADR-002-029는 *per-artifact* content-addressing이다. 둘 다 **build/deploy 시점
   속성**이지 repo 레이아웃 속성이 아니다. monorepo라도 (i) tos/에서 egress 코드가
   import-도달 불가하고 (ii) 빌드가 분리된·attested·content-addressed 아티팩트를
   산출하면 만족 가능. → "별도 repo여야 안전하다"는 통념은 성립하지 않는다.
2. **그린필드 경계 배치 원칙**: IMPLEMENTATION-PLAN §2의 9개 코어에 더해
   **DSL runtime, Evidence Store, Currentness Sequencer, Safety Commit Log
   substrate, 전 governance/release-admission**을 경계 *안*(그린필드)으로 넣고,
   **F5 모델·F7 하네스 원시요소·config·resilience는 경계 *밖***에 두어 단방향
   import한다.

   > **authority · ordering · integrity · containment → 그린필드(경계 안).**
   > **순수 · 무권한 · evidence-producing 계산 → 재사용(경계 밖, 단방향 import).**

### 4.3 권고: 전략 (B) + 비협상 조건 3가지

**현 단계(Phase 1, EV-L1, non-transmitting)는 (B)를 채택한다.**

- **C1 — 기계적 import firewall**: `tos/`는 허용목록(`shared/indicators`,
  `shared/backtest`(LookaheadGuard·replay), `shared/config`, `shared/models`(어휘),
  `shared/resilience`/utils)만 import 가능. `shared/execution`·`shared/kis`·
  `shared/streaming`(safety 경로)·`services/*`는 **CI import-linter hard gate로
  차단**. convention 금지 — S4가 보여주듯 convention 순수성은 이미 실패한 전례다.
- **C2 — 플래그 금지**: tos/ 내 어떤 capability도 런타임 플래그로 확장되지 않는다
  (SAFE-045-by-construction). live 경로 코드는 Phase 1 tos/에 아예 부재.
- **C3 — 아티팩트 분리 설계**: 빌드가 tos/를 running system과 분리된
  content-addressed 아티팩트로 산출하도록 계약을 지금 고정(EV-L1엔 배포가 없어도).

**(A) 기각**: SAFE-045 구조적 불충족(S1), 운영 시스템 오염 위험 최대, 레거시
god-object 견인. **(C)는 유효한 후속 옵션**: live gate(ADR acceptance) 근접 시
tos/는 이미 import 격리·아티팩트 분리되어 있어 저마찰 추출 가능 — 결정을 지금
강제하지 않고 live gate로 이연한다. (B)→(C)는 low-regret 가역 경로다.

---

## 5. Dual-use 리팩토링 vs 낭비 리팩토링

### 5.1 두 시스템 모두에 이득 (우선순위 순)

1. **Indicator TA-Lib SoT 수렴** (`shared/indicators`) — 최강 dual-use. 현행은
   backend 일관성, tos/는 EV-L1 모델의 단일 순수 소스. 2026-07-08 계획 P1과 일치.
2. **Config artifact identity** (`shared/config`) — 현행은 재현 가능 provenance,
   TOS는 DSL 순수함수 서명의 config version. content-addressing만 추가.
3. **Append-only ledger hardening** (`runtime_ledger` → hash-chain·append-only·gap
   detection) — 현행은 tamper-evident 감사추적, TOS는 Evidence Store *규율·스키마*
   토대. **ceiling**: 단일 writer SQLite는 quorum Safety Commit Log가 아니다.
4. **선언형 전략 콘텐츠 추출** (builder_v1 승격, 2026-07-08 계획 P2) — 현행은
   노코드 빌더, TOS는 알고리즘 콘텐츠를 DSL에 근접한 이식형으로. **ceiling**:
   선언형 YAML ≠ 3-layer containment-by-construction.
5. **Kill-switch/protective-action hardening** — 현행은 견고한 HALT, TOS는
   PAC/Recovery의 fail-closed·no-auto-re-arm 의미론 소재.
6. **Egress choke-point 통일** (OrderExecutor 단일화, dead `submit_ats_order` 제거,
   S5 field-invent 제거) — 현행 안전성↑, TOS는 깨끗한 Broker Adapter 소재.
   **ceiling**: TOS Egress Gateway 자체는 그린필드.

### 5.2 그린필드 경계 하에서 낭비인 "매력적" 리팩토링 (하지 말 것)

1. **OrderExecutor를 spec-conformant로 in-place 개조** — tos/는 이를 import조차
   안 한다. 현행 안전 목적의 최소 하드닝만 수행.
2. **vectorbt 교체를 "TOS 대비" 명분으로 추진** — TOS 백테스트 가치는 벡터화
   속도가 아니라 LookaheadGuard+seeded 결정론+hermetic이다. (현행 시스템 자체
   가치로만 판단할 것.)
3. **Redis streaming을 safety-grade ordering으로 하드닝** — at-least-once는
   consensus 요구를 못 채운다. non-safety telemetry로 유지.
4. **orchestrator.py 모놀리스 하드닝** — 폐기 예정, 음의 가치.
5. **strategy ABC를 denylist/sandbox로 "안전화"** — ADR-DEV-001 명시적 비적합.
   알고리즘을 DSL 콘텐츠로 추출만.
6. **RiskManager(Redis)를 RCL로 진화** — quorum+fencing과 불연속. 필터 로직만
   dual-use, 저장 계층 진화는 금지.

> **패턴**: 경계 *밖* 순수 계산 자산의 개선은 dual-use, 경계 *안*
> authority/ordering/integrity 컴포넌트를 기존 코드에서 진화시키려는 시도는 낭비.

---

## 6. 설계 단계 진입 — 첫 설계 문서 제안

§7 시퀀스 + IMPLEMENTATION-PLAN Phase 1(EV-L1 순수 모델 + property test,
non-transmitting) 기준. 모든 것이 의존하는 두 계약(경계·Capsule)을 먼저 고정한다.

| 순서 | 설계 문서 | 내용 | 왜 먼저 |
|---|---|---|---|
| 1 | **`tos/` 경계 & import-firewall 계약** | tos/ 레이아웃, 재사용 허용목록, CI import-linter hard gate, SAFE-045-by-construction 논증, 아티팩트 분리(C3) 계약 | 재사용 매트릭스를 기계적으로 강제하고 §4 결정을 운영화. IMPLEMENTATION-PLAN §2 경계의 정확한 배치를 확정 — **비준 대상 문서** |
| 2 | **Decision Context Capsule + Snapshot 계약 (ADR-002-018)** | 스키마·provenance(Critical Input)·immutability·content-addressing·LLM-value pre-capture | 모든 EV-L1 모델이 Capsule을 소비 → 모델보다 선행 |
| 3 | **EV-L1 순수 모델 계층 + property-test 하네스 (RFC-004..007, ADR-DEV-010)** | 기존 indicators/risk-logic을 Capsule-only·no-authority·evidence-producing 모델로 래핑; hermetic·seeded 결정론; evidence-package 산출(manifest/jsonl/sha256) | 최강 재사용(F5·F7)이 실현되고 Phase 1 증거가 생산되는 지점 |
| 4 | **Evidence Store 계약 + append-only ledger (ADR-002-016)** | hash-chain 스키마, pre-effect durability, gap detection | 최대 격차(S2)이자 하류 전부의 의존점 — 조기 착수로 트랙 전체 de-risk. dual-use ledger hardening 견인 |

- **import 허용**: `shared/indicators`, `shared/backtest`(LookaheadGuard·seeded
  replay·market_context_replay), `shared/config`, `shared/models`(어휘),
  `shared/resilience`/utils.
- **import 금지**: `shared/execution`, `shared/kis`, `shared/streaming`(safety
  경로), `services/*`, 그리고 모든 flag-based mode switch.
- **DSL 설계(RFC-008/ADR-DEV-001)는 즉시 후속**이되 EV-L1 크리티컬 패스가 아니다
  — EV-L1은 무권한 순수 *모델*이므로 full DSL이 선행 조건이 아니다. #1~#4와 병렬
  착수하되 Phase 1 모델 작업을 블로킹하지 않게 배치.

### 거버넌스 유의점

IMPLEMENTATION-PLAN-002 §0/§6에 따라 **구현 코드는 plan-first 비준 후에만
착수한다**: (i) 본 분석이 제안하는 경계 배치(설계 문서 #1)의 비준, (ii)
VERIFICATION-PROFILE-002 bounds 승인, (iii) 독립 리뷰어 지정이 선행 게이트다.
설계 문서 작성 자체는 게이트에 걸리지 않는다.

---

## 7. 위험 / 반론

1. **"152k LOC 매몰자산 대비 10~15% 재사용은 낭비 — (A)가 경제적."** → 불성립.
   못 옮기는 LOC는 정확히 safety-critical 경로이고, 이를 재사용하면 절감이 아니라
   **부채 수입**이다(S1·S5가 능동적 비적합으로 만듦). 진짜 자산(순수 모델·백테스트·
   config)은 (B)가 이미 취한다.
2. **"동일 repo는 SAFE-045/failure-domain 위반."** → 부분 성립 → 요구사항으로
   전환. 소스 트리 co-location은 런타임 trust 도메인과 직교(§4.2). 단 **live
   gate에서는** 분리된 identity/credential·evidence-backed isolation으로
   빌드/배포되어야 하며, monorepo 빌드가 이를 못 내면 그 시점에 (C)로 추출.
3. **"2026-07-08 리팩토링을 끝내면 재사용률이 오른다."** → 부분 성립. 모델/콘텐츠
   축의 dual-use는 오르나(§5.1), safety core 재사용은 여전히 ~0%. 완주해도
   ~12% → ~18~22% 이동 — 유의미하나 결정적이지 않다. 그 계획을 "TOS 진척"으로
   오인해 우선순위를 왜곡하지 말고 dual-use enabler로 sequence할 것.
4. **"단일 운영자에게 두 시스템 운영은 과부하."** → 부분 성립하나 이연됨. Phase
   1(non-transmitting)은 test/CI 부하만 추가하고 운영(on-call) 부하 0. 실제 2-시스템
   운영비는 live gate에서 발생하며 그 시점이 (C) 재검토 지점.
5. **"in-repo는 결국 비적합 의존이 샌다."** → 부분 성립 → C1을 hard gate로 만든
   이유. CI import-linter는 저비용·고신뢰 통제다. 게이트가 반복 우회되면 그것이
   (C) 추출 트리거다.

**잔여 불확실성**: (i) family별 노력 가중치는 판단 기반 추정(±5%p). (ii)
strategy/risk 알고리즘 소재의 실제 가치는 DSL 최종 형태에 의존. (iii) consensus
substrate는 외부 제품(예: raft 계열)으로 *조달* 가능 — "그린필드"가 "from-scratch
구현"을 뜻하지 않는다.

---

## 부록 — 조사 출처

- 트랙 1(spec 컴포넌트 맵): RFC-002 전문, IMPLEMENTATION-PLAN-002 전문, RFC-003
  (§9.1까지), RFC-004..007 구조, RFC-008 전문, RFC-010 §5-11, ADR-DEV-001 전문,
  VER-002-001 §5-9, EVIDENCE-REGISTER-002/DEV, ADR-002-004/-005/-008/-009/-012/
  -013/-024 §1.
- 트랙 2(코드 인벤토리): shared/ 전 모듈 + services/ 파이프라인 서비스, LOC 실측,
  KIS-import 결합도 grep, Redis 스트림 키 패턴(117 call sites), egress 경로 추적,
  테스트 스위트 규모.
- spot-check(S1~S5): `shared/execution/live_mode_guard.py`,
  `shared/storage/runtime_ledger.py`, 전역 consensus grep,
  `shared/strategy/base.py`, `shared/execution/executor.py`.
