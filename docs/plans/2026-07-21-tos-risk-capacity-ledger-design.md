# 설계 문서 #5 — Risk Capacity Ledger + Aggregate Risk-Capacity Commitment 계약 (2026-07-21, v1.1)

> **문서 번호 규약**: #1 경계·import-firewall, #2 Decision Context Capsule, #4 Evidence
> Store가 이미 존재한다(#3은 folded). DSL·Trustworthy Time은 병렬 트랙 A/C였다. **#5 =
> 본 Risk Capacity Ledger(RCL) 문서**다.
>
> **비준 기록**: **2026-07-21 운영자 비준(v1.1) — 효력 발생.** 독립 비평 리뷰
> **ACCEPT-WITH-MINOR**(CRITICAL 0 / MAJOR 0; MINOR 3) 반영 개정 후 비준; `classify_record_pair`
> core PROMOTE 결정(§10.2 판단 지점) 승인. **구현은 운영자 지시로 보류(작업 대기) — 다음 세션에서
> 이어감.** 비준 효력은
> IMPLEMENTATION-PLAN-002 §4 Phase 1(EV-L1)의 **ADR-002-002 부분 + ADR-002-012 부분**을
> 그린필드 `tos/src/tos/rcl/`에 **순수·비전송 데이터 모델 + property test**로 실현하는
> 프로젝트 측 설계 계약을 확정하는 것에 한한다. **어떤 RCLP-EV/RC-EV도 수용(acceptance)
> 하지 않는다**(§1). §9.2 Phase-0 항목(bounds 승인·독립 리뷰어·프로덕션 canonicalization·
> Capacity Domain/failure-tolerance 모델·segment-commitment PROMOTE 여부·누락 프로파일 키)은
> 별도 게이트로 유지한다.
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**
> 이며 스펙 텍스트(RFC/ADR/템플릿/프로파일)를 **변경하지 않는다.** broker-agnostic 원칙
> (project memory `tos-spec-broker-agnostic`): KIS 등 특정 브로커 사실은 프로젝트 측 예시로만
> 등장하며 규범 주장이 아니다. capacity 차원·상태·불변식·writer-fence 술어는 전부
> broker-agnostic이며, 브로커 제약은 capability class(Broker Capability Profile)로만 표현한다.
>
> **선행 문서(의존)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   본 계약의 모든 모델은 설계 #1 §2.4 레이아웃(`tos/src/tos/rcl/`)에 놓이고 §3.2 허용목록
>   안에서만 의존한다(§0.3).
> - [설계 #4 — Evidence Store + append-only ledger 계약 (v1.1, 비준·구현됨)](2026-07-20-tos-evidence-store-design.md)
>   + 코드 `tos/src/tos/canonical/`, `tos/src/tos/evidence/`. **canonicalization/digest-binding
>   substrate(`tos.canonical`)를 REUSE한다(재정의 금지).** evidence의 `id=f(digest)` **미채택**
>   결정(§2.1/§3.1, same-id/diff-bytes 탐지 보존)을 RCL이 **동형으로 상속**한다 — 상세 §3.1.
>   `tos.evidence`(ledger·predicates 포함)는 **import하지 않는다** — RCL Safety Commit Log는
>   Evidence Store의 **상류**(ADR-002-012 §19 line 478 "evidence stores are downstream
>   projections")이므로 상류가 하류 투영을 의존하면 layering 역전이다(§0.4·§3.1).
> - [설계 — Trustworthy Time 모델 계약 (v1.1, 비준)](2026-07-21-tos-trustworthy-time-design.md)
>   + 코드 `tos/src/tos/ordering/`. **ordering primitive(`tos.ordering`)를 REUSE한다.**
>   `OrderingEvent.quorum_commit_index`가 곧 RCL의 **Log Revision**(ADR-002-012 §5.6)이고
>   `egress_journal_sequence`가 §12 claim 순서다 — 이 필드들은 애초에 ADR-002-012/016 개념을
>   담아 core로 승격된 것이다(time 설계 §0.4b line 166–168). 상세 §3.2.
> - [설계 #2 — Decision Context Capsule + Snapshot 계약 (v2, 비준·구현됨)](2026-07-20-tos-decision-context-capsule-snapshot-design.md).
>   `SnapshotAuthority._all_authority_false` 패턴(`tos/src/tos/capsule/_base.py` line 70–78)과
>   `Freshness{within_bound: bool|None}` fail-closed 패턴을 REUSE한다(§4.1·§5.3). `tos.capsule`
>   자체는 **import하지 않는다**(형제 패키지 — §0.3).
>
> **규범 원천**:
> - `ADR-002-002` — Aggregate Risk-Capacity Commitment Model (Status: Proposed, 1648 line).
>   capacity semantics의 소유 ADR(§36 line 1556).
> - `ADR-002-012` — Risk Capacity Ledger Persistence, Consensus, and Writer Fencing
>   (Status: Proposed, v0.2, 717 line). persistence·consensus·writer-fencing 계층.
> - 매핑 대상 EV: `verification/EVIDENCE-REGISTER-002.csv`의 `RCLP-EV-001..012`(ADR-002-012)
>   및 `RC-EV-001..018`(ADR-002-002).
>
> **리뷰 이력**: v1.0 초안 → 독립 비평 리뷰(별도 컨텍스트, fail-open·firewall 위반·overclaim
> adversarial 탐색; ~50개 ADR 인용·register·`.importlinter`·tos 코드 primary-source 재검증)
> **ACCEPT-WITH-MINOR**(CRITICAL 0 / MAJOR 0; MINOR 3: 인용 off-by-one·open-Q3 DRY 비대칭·
> pyyaml 필요성) → v1.1에서 3건 전부 반영(§10.1). 선행 문서(#1/#2/#4/Time)와 동일 리듬.
> 수용 서명 게이트는 IMPLEMENTATION-PLAN-002 §3
> (line 153/157) 하드 배제(Independent-Safety-Reviewer는 본 문서의 저자/통합자여서는 안 됨)를
> 따른다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-012 조항별·ADR-002-002 조항별로 **Phase 1(EV-L1)에서 모델·property로 도달 가능한
   것과 이연할 것의 경계**(§1). 특히 RCLP-EV의 **core / predicate-only / not-Phase-1** 삼분류와
   **RC-EV 0건 완결** 사실.
2. RCL ledger 시민(reservation·command·capability·transition·snapshot 레코드)과 aggregate
   commitment 요소(Capacity Vector, Adverse Increment/Economic Effect Envelope, allocation
   request, capacity-state)의 **데이터 모델 계약**(§2).
3. **canonicalization + digest 계약의 REUSE 결정**(§3): 설계 #4 `tos.canonical`을 REUSE하되
   RCL ledger 레코드 **identity는 digest에서 파생하지 않는다**(`id=f(digest)` **미채택** —
   §9 line 270 same-command-id/diff-content 충돌을 표현·탐지하기 위해). ordering은
   `tos.ordering` REUSE. **PROMOTE 1건**(§0.4b: `classify_record_pair`를 core로; segment-commitment은 이연 — §3.2·§9.1).
4. **capacity ≠ authority 불변식**(§4.1, 중앙): GRANT/DECISION 객체(Aggregate Risk Decision,
   Action Flow Decision/Permit, capacity grant decision)는 **비권위 입력**이며 capacity를
   mutate/commit/release하지 못한다. **오직 RCL commit(결정적 State Machine이 적용한 committed
   transition)만이 capacity를 mutate한다.** 설계 #4의 evidence ≠ authority(ERI-INV-001/014)
   동형.
5. **append-only·단조 epoch/generation·writer-fence fail-closed·same-command-id/diff-bytes
   충돌** 불변식(§4).
6. **aggregate commitment 세부**(§5): conservative projection 단조성, **netting/hedge/
   diversification/correlation benefit = 0 unless positively proven**, **missing-dimension =
   restrictive**(빈-집합 fail-open 방지 canary 포함), capacity-state 보수성 lattice.
7. **writer fencing 술어 세부**(§6): 단조 epoch/generation floor, stale/minority/removed/
   restored/conflicting fencing을 **주입 epoch 상태 위 순수 술어**로(실제 consensus 없음),
   fail-closed. capacity→capability 순서 binding.
8. **property-test 하네스 타깃**(§7) + import-closure 검증 확장(§7.1, `tos.evidence`·
   `tos.capsule` 부재 포함) + run manifest 7항목(§7.2).
9. **bounds 주입 계약 + 누락 프로파일 키의 Phase-0 게이트 플래그**(§8).

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.**
  ADR-002-002 §39(line 1640) "authorizes implementation and verification work but does not
  authorize production live trading"; ADR-002-012 §28(line 704) "does not authorize
  acceptance, restricted-live operation, production operation, or automatic re-arm." ADR
  acceptance는 오직 *실행된* evidence로만 온다(project memory `tos-spec-rfc-authoring-track`).
- **consensus / quorum / Safety Commit Log replication을 구현하지 않는다 — 이것이 ADR-002-012의
  코어이며 EV-L1이 아니다(EV-L2+/Phase B).** `2f+1` voting(§8.1 line 219), durable quorum
  commit(§8.2 line 224–233), leader election, linearizable read 메커니즘(§8.4 line 242–246),
  partition/membership 실제 거동은 **런타임 분산 속성**이며 순수 모델이 증명할 수 없다. Phase 1은
  (a) ledger 레코드·epoch/generation/writer-identity fence의 **데이터 구조**, (b) **단조 순서
  불변식**, (c) **writer-fence 술어**(주입 epoch 상태에서 "이 writer가 fenced인가"), (d)
  same-revision/diff-bytes 충돌 탐지 — 를 **주입 상태 위 순수 함수**로만 저작한다. 그 단일
  committed order를 동시성/파티션에서 quorum이 *산출*함(RCLP-INV-002/003의 quorum 측면)은 비-scope.
- **persistence I/O·durability·프로세스 간 실제 serialization 순서를 구현하지 않는다.** 데이터 +
  불변식만 저작하고 메커니즘은 이연한다. 따라서 **RCLP-EV-005의 idempotency 술어는 순수로 저작
  되나 실제 crash/response-loss는 fault injection ⇒ /3**(§1).
- **egress / 전송을 구현하지 않는다.** 설계 #1 §4대로 tos는 정의상 non-transmitting이다
  (자격증명·라우트·주문구성 부재 + egress 코드 firewall 차단). §12 fenced egress claim→
  first-byte(ADR-002-012 line 335–345), INV-004 "No Transmission Without Capacity"의 *전송*
  부분은 Phase 1에서 **capability binding 술어**만 저작하고 실제 send·nonce 소비 순서의 런타임
  강제는 이연한다(RCLP-EV-007 not-Phase-1).
- **authority를 부여하지 않는다.** 모든 GRANT/DECISION/capability/snapshot 아티팩트의
  `authority_effect.*`(creates_capacity·may_mutate_live_state·may_release_capacity·
  permits_broker_transmission·may_rearm)는 **false 상수**이며 모델이 강제한다(§4.1). "capacity
  mutation/broker 경로가 어디에도 없다"의 전수 증명은 EV-L2/L3+Security(RCLP-EV-002/007)이다.
- **RC-EV를 0건 완결한다(§1).** ADR-002-002의 acceptance evidence `RC-EV-001..018`은 register
  최소 레벨이 **전부 EV-L2 이상**이다(csv 실측: -009/-018만 EV-L2, 나머지 EV-L3/+Broker; EV-L1
  최소 항목 0). ⇒ Phase 1은 어떤 RC-EV도 닫지 않고 순수 capacity-math substrate만 저작한다
  (Trustworthy Time 설계의 "TIME-EV 0건 완결" 동형). RCLP-EV 중 core도 **L1 슬라이스뿐이며
  "EV-L1-complete"를 주장하지 않는다**.
- **numeric bounds를 승인하지 않는다.** VERIFICATION-PROFILE-002 bounds 승인·누락 키 신설·독립
  리뷰어 지정은 Phase-0 인간 게이트(§8·§9.2).

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

rcl 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`pyyaml`는 rcl 순수
  모델이 import하지 않는다** — §8대로 모든 bound는 **주입 policy 파라미터**로 들어오고(§7.2
  item 6은 프로파일을 *하네스*가 소비·digest 기록), YAML 파싱은 설계 #3 하네스 소관이지 rcl
  closure 안이 아니다(rcl 모델은 자체적으로 YAML을 로드하지 않는다). **`numpy`/`pandas`도
  import하지 않는다** — capacity
  vector 산술은 **정수/`Decimal`** 만으로 충분하고(차원→값 매핑에 대한 합·비교·보수 상한),
  수치 백엔드가 불필요하므로 closure를 최소화한다(설계 #4 §0.3·Time 설계 §0.3 동일 규율).
  `tos.canonical.canonicalization`의 `_num_token`이 이미 `Decimal` 정규화를 제공한다.
- tos 자기 자신: `tos.canonical`(digest-binding substrate — §3.1), **`tos.ordering`**(committed
  order·Log Revision — §3.2), `tos.rcl.*`. **`tos.capsule`·`tos.evidence`를 import하지
  않는다.** capsule/evidence가 RCL 개념을 참조할 때는 오직 scalar(예: evidence causal edge
  `CAPACITY_COMMIT`의 `target_id`/`target_digest`, reservation/revision 참조)로만 담고 RCL
  모델 클래스를 import하지 않으며, **역으로 RCL도 그들을 import하지 않는다**(§3.1 layering —
  세 패키지는 core에만 한 방향 의존하는 형제다; RCL은 evidence의 **상류**이므로 특히 금지).
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter` line 12–17): `shared/config/
  __init__.py`가 `shared.config.secrets`(→ `os.environ`)를 무조건 전이 import한다. bounds
  프로파일 로딩은 `pyyaml`만으로 수행한다. `shared.{models,indicators,resilience,utils,
  exceptions,determinism}`는 firewall 허용이나 rcl 순수 모델은 이들에 대한 필요가 없어
  **의존하지 않는다**(closure 최소화). 특히 `shared.determinism`은 (i) `replay.py`가 `pandas`를
  물고 (ii) look-ahead/backtest용이지 ledger 프리미티브가 아니므로 미import(Time 설계 §0.3 동형).
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`, `shared.llm`,
  `shared.storage`, `shared.backtest`, `services.*`, `cli.*`(설계 #1 §2.3; `.importlinter`
  forbidden set). RCL은 자산군·실행 경로와 무관한 순수 커널이다.
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(`import tos.rcl` closure에
  금지·shared.config·os.environ·numpy/pandas·**tos.capsule·tos.evidence** 부재 assert).
  required check(`tos-firewall`, `tools/tos_firewall_check.py` + `.importlinter`)와 함께
  green이어야 본 선언이 능동 성립한다.

### 0.4 REUSE / PROMOTE 결정 요지 (핵심 아키텍처)

**(a) REUSE(canonical·ordering) + `id=f(digest)` 미채택.** RCL ledger는 설계 #4 `tos.canonical.DigestBoundArtifact`
(digest 검증, **id 파생 없음**)와 `tos.ordering`(committed order)을 **REUSE**한다. capacity
commitment 레코드는 evidence 레코드와 동일하게 **ledger 시민**이며, 그 identity(reservation_id·
command_identity·capability id·epoch id)는 **서비스/도메인 할당**이지 content-address가 아니다
(ADR-002-002 §9 line 475 "immutable globally unique reservation_id"; §8.5 line 465–469 command
idempotency by command identity). ⇒ **`id=f(digest)`(`IdDerivedArtifact`) 미채택** — ADR-002-012
§9 line 270 "duplicate identity with different content" 거부와 RCLP-INV-006(line 169–171)이
**same command_identity + different canonical content = 충돌**을 **표현·탐지**하려면
identity ⊥ content-digest여야 한다(설계 #4 §2.1/§3.1과 동형; capsule의 immutable
content-addressed `id=f(digest)`와 정반대). 근거·상세 §3.1.

**(b) 형제 evidence 순수 프리미티브 = 통일 PROMOTE 규칙(classify 지금, segment-commitment 이연).**
RCL과 evidence는 둘 다 ledger-시민 패키지라 두 순수 프리미티브를 공유한다: same-id/diff-content
**충돌 분류기** `classify_record_pair`와 tamper-evident **segment-commitment**. **통일 규칙**:
RCL이 필요로 하는 evidence(형제) 순수 프리미티브는 **core로 PROMOTE하고(ordering·canonicalization
PROMOTE 선례) evidence는 shim으로 무회귀 유지**하며, `tos.evidence`를 import하거나(RCL은 evidence의
**상류** — ADR-012 §19 line 478 — 이므로 layering 역전) RCL 안에 재저작하지 않는다(CLAUDE.md DRY
비협상 규칙). **차이는 필요 시점뿐**: **(1) `classify_record_pair`는 Phase-1 core가 *지금* 필요**
(same-command-id/diff-bytes 충돌·idempotency = RCLP-EV-005 core, §4.5) ⇒ **지금 core로 PROMOTE**
(리뷰 확인: evidence-특화 결합 없는 순수 `(identity, digest)→kind` 분류기; 정확한 core home은
ordering PROMOTE 선례대로 구현 시 결정; §3.1c). **(2) segment-commitment**은 Phase-1 core 불요
이므로 아래대로 이연한다. RCL Safety Commit Log의
tamper-evident segment commitment은 구조적으로 `tos.evidence.ledger.SegmentCommitmentScheme`
(설계 #4 §3.4)과 **동일 프리미티브**다. 그러나 (i) RCL은 evidence의 **상류**(ADR-002-012 §19
line 478)이므로 `tos.rcl → tos.evidence` edge는 layering 역전이고, (ii) **Phase 1 core
EV-L1 슬라이스는 이 프리미티브가 필요 없다** — committed-prefix 단조성(RCLP-INV-005)은
`tos.ordering.OrderingEvent.quorum_commit_index`(=Log Revision) 단조 술어로 충분하고, 암호학적
prefix/fork tamper-detection은 predicate-only인 snapshot/rollback substrate(RCLP-EV-010,
L2/3)의 **메커니즘**이라 Phase 1이 주장하지 않는다. ⇒ 결정: **segment-commitment은 지금
PROMOTE하지 않는다(이연).** 향후 그 substrate를 저작한다면 (b) 통일 규칙대로 `evidence.ledger`의
scheme을 **core로 PROMOTE**할 것이며(ordering PROMOTE 선례), **결코 `tos.evidence`를 import하지
않고 RCL 안에 중복 저작하지도 않는다**(§3.2·§9.1).

**(c) 패키지 위치 = 전용 `tos/src/tos/rcl/`.** 설계 #1 §2.4가 capsule/·evidence/·time/을 전용
top-level 패키지로 둔 선례에 부합한다(RFC-002 §10의 "Risk Capacity Ledger"는 first-class 컴포넌트).
naming은 load-bearing이 아니다 — 운영자 치환 가능; **load-bearing은 layering**(RCL은 core에만
한 방향 의존, evidence의 상류, capsule/evidence와 형제)이다.

---

## 1. 범위 매핑 — ADR-002-012 + ADR-002-002 조항별 EV-L1 도달성

EV-level 정의(VER-002-001 line 142–152): **EV-L1 = Model and Property Verification**(state-machine
exploration, model checking, property-based testing, deterministic simulation). **EV-L2 =
Component Fault Test**. Phase 1은 EV-L1만이다. 아래는 register 실측 최소 레벨을 기준으로 한
**core / predicate-only / not-Phase-1** 삼분류다(설계 #4 §1 형식).

> **결정적 사실 1 — RC-EV 0건 완결**: `RC-EV-001..018`(ADR-002-002 acceptance)은 register 최소
> 레벨이 **전부 EV-L2 이상**이다(csv 실측: `RC-EV-009`·`RC-EV-018`만 `EV-L2`, 나머지 `EV-L3`/
> `EV-L3+Broker`; EV-L1 최소 항목 **0건**). ⇒ **Phase 1은 어떤 RC-EV도 닫지 않는다**(Trustworthy
> Time "TIME-EV 0건 완결" 동형). 대신 ADR-002-002의 **순수 capacity-math substrate**(§2·§4·§5)를
> 저작한다. 이 substrate는 `RCLP-EV-001`의 L1 슬라이스(동시 commitment의 aggregate-envelope
> 검사 = ADR-002-002 AC-001 line 1378–1382)를 통해 **부분적으로 표면화**된다.
>
> **결정적 사실 2 — RCLP-EV는 3개만 L1 최소를 가진다**: `RCLP-EV-001/005/006`이 `EV-L1/3`(-006은
> `+Security`)이다. 나머지(-002/-003/-004/-007/-008/-009/-010/-011/-012)는 최소 `EV-L2` 이상.
> ⇒ core는 이 3개의 **L1 슬라이스뿐이며, 그조차 `/3` 꼬리(quorum·fault injection·egress)가 남아
> "EV-L1-complete"가 아니다.**

| EV | 요지 | Phase 1(EV-L1) 분류 | 근거 |
|---|---|---|---|
| **RCLP-EV-001** | Quorum-Serialized Concurrent Commitment (`EV-L1/3`) | **core (L1 슬라이스만)** | 주어진 committed order 위에서 결정적 reducer가 double-spend하지 않음 + 결정성(ADR-002-012 §9 line 276; ADR-002-002 §8.4 CAS line 449–463, AC-001). **단일 order를 quorum이 산출함은 /3.** |
| **RCLP-EV-005** | Commit Response Loss and Crash Idempotency (`EV-L1/3`) | **core (L1 슬라이스만)** | command identity별 idempotency: 1 command_identity ⇒ ≤1 transition·안정 결과(RCLP-INV-006 line 169–171; ADR-002-002 §8.5 line 465–469; §21 line 522). **실제 crash/response-loss는 fault injection ⇒ /3.** |
| **RCLP-EV-006** | Capacity-to-Capability Commit Ordering (`EV-L1/3+Security`) | **core (L1 슬라이스만)** | capability authorization이 **이미 committed된 reservation revision + 정확한 worst-case effect + 현재 generation vector**에 bind됨을 검증하는 순수 술어(§11 line 317–327). **실제 egress·minority-issued 거부는 /3+Security.** |
| RCLP-EV-003 | Stale Writer Resume (`EV-L3+Security`) | **predicate-only** | writer-fence 술어(state-machine fencing = §13 line 359 layer-2; RCLP-INV-004 line 161–163). consensus fencing(layer-1)·egress fencing(layer-3)은 런타임. |
| RCLP-EV-004 | Quorum Loss Preserves Capacity (`EV-L3`) | **predicate-only** | partition deny-table(§15 line 389–397) + 경제효과 보존(RCLP-INV-008 line 177–179). quorum-unavailable은 **주입 flag**. |
| RCLP-EV-008 | Stale Read Cannot Create Permission (`EV-L2/3`) | **predicate-only** | 비권위 read(follower/cache/snapshot/projection) 분류·거부 술어(RCLP-INV-007 line 173–175, §8.4 line 245). **linearizability 자체는 런타임.** |
| RCLP-EV-010 | Snapshot/Compaction/Restore Integrity (`EV-L2/3`) | **predicate-only** | snapshot 완전성(RCLP-INV-009 line 181–183) + committed-prefix 단조(RCLP-INV-005 line 165–167) 술어. **실제 store compaction·암호학적 tamper-detection은 L2+.** |
| RCLP-EV-012 | Disaster Recovery and Conflicting History (`EV-L3+Security`) | **predicate-only** | worst-credible-union·no-last-write-wins-merge·non-revival 술어(§18 line 459–472; RCLP-INV-011 line 189–191). **reconstructable histories 조립은 런타임.** |
| RCLP-EV-002 | Minority Leader With Broker Reachability (`EV-L3+Security`) | **not Phase-1** | 실제 consensus + broker reachability + security. 순수 모델로 표현할 코어 없음. |
| RCLP-EV-007 | Quorum-Committed Claim and Send Boundary (`EV-L3+Security`) | **not Phase-1** | egress + security. (파생: claim nonce-once 술어는 -006과 함께 L1이나 **send boundary는 비주장**.) |
| RCLP-EV-009 | Joint Membership and Removed-Voter Fence (`EV-L3+Security`) | **not Phase-1** | joint consensus + security. (파생: membership-generation fence 술어는 §6 writer-fence에 포함되나 EV로 비주장.) |
| RCLP-EV-011 | Protective Sub-Ledger Rejoin (`EV-L3`) | **not Phase-1** | 실제 partition/rejoin + broker reconciliation. (파생: sub-ledger no-enlarge/recycle/overlap/merge 술어는 §5.5에 포함되나 비주장.) |

**Phase-1 EV-L1 타깃(core, L1 슬라이스)**: `RCLP-EV-001, -005, -006`. **predicate-only(EV
주장 금지)**: `-003, -004, -008, -010, -012`. **not Phase-1**: `-002, -007, -009, -011` + **모든
RC-EV**.

> **인접 ADR 경계 주의**: `ARE-EV-001..012`(csv에 `EV-L1/3` 행 존재)는 **ADR-002-021 — Aggregate
> Risk Evaluation** 소관이며 **본 문서 scope가 아니다.** ADR-002-021이 산출하는 Aggregate Risk
> Decision / allocation request는 RCL에 대해 **비권위 입력**이다(§4.1 capacity≠authority;
> ADR-002-002 §11.1 step 6 line 587). ARE-EV의 L1 행이 본 scope처럼 보이지 않도록 명시한다.

> **완결 주장 규율(설계 #2 §7·#4 §7·Time §1 상속)**: Phase 1은 *모델 + property test 저작*
> 까지다. **어떤 항목도 "EV-L1-complete"로 주장하지 않는다.** core 3항목조차 L1 슬라이스뿐이고
> RC-EV·나머지 RCLP-EV는 애초에 EV-L2+라 EV-L1로 닫을 수 없다. 모든 주장에 규율 태그를 붙인다:
> **"EV-L1 슬라이스/predicate substrate only; RCLP-EV-001/005/006은 L1 부분만(‥/3 잔존),
> 나머지 RCLP-EV·전 RC-EV는 NOT_IMPLEMENTED, EV-L2/L3(+Security/+Broker) fault injection 대기."**
> VER register의 Owner/Reviewer는 TBD이고 수용은 Independent-Safety-Reviewer(저자 아님)의 별도
> 서명(IMPLEMENTATION-PLAN §3 line 153/157)이다.
>
> **ADR 자체 Phase-1 정합**: ADR-002-002 §38 "Phase 1 — Model and Simulation"(line 1583–1587)이
> 정확히 "implement the capacity state machine **without live transmission**; run deterministic
> concurrency and fault simulations; verify invariants through **property-based and model-based
> tests**"를 명령한다. 본 계약은 그 **순수·비전송 부분**을 실현한다.

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True,
extra="forbid")`, `tos.canonical.FrozenModel` REUSE — `_base.py` line 66–69)로 저작한다. frozen은
ledger append-only(ADR-002-012 RCLP-INV-005; ADR-002-002 §28 line 1218 "immutable or
tamper-evident")의 레코드 수준 실현이며, **모델에는 update/delete 연산이 존재하지 않는다**
(설계 #4 §2.0 규율 상속). 필드명은 ADR §9(reservation)·§27(command)·§10(state)의 용어를 그대로
쓴다(스펙 용어 = 코드 용어, 설계 #1 §2.4).

### 2.0 ledger 골격 — append-only 시퀀스, RCL은 evidence의 상류

RCL은 **committed command의 append-only 시퀀스**(Safety Commit Log, §5.2 line 113–115)와 그로부터
결정적으로 파생되는 **capacity state**로 구성된다. lifecycle 변화(resize·transfer·release·
quarantine·correction)는 **원본을 변경하지 않고 새 committed command/transition을 append**하여
표현한다. `tos.ordering.OrderingEvent.quorum_commit_index`가 Log Revision(§5.6 line 133–135,
"ordering identity, not a wall-clock time")이다. **evidence는 하류 투영**(§19 line 478)이므로
RCL 모델은 evidence 아티팩트를 담지 않고, 반대로 RCL transition이 evidence로 emit되는 경로는
설계 #4 소관이다(RCL은 `decision`·`revision` scalar만 남긴다).

### 2.1 digest-bound / plain-frozen / reference 분류 (총괄)

| 아티팩트 | 종류 | id 필드(독립) | digest 필드 | covered = ? |
|---|---|---|---|---|
| Reservation/Commitment Record (§9 line 473–503) | **DigestBoundArtifact** | `reservation_id` | `canonical_record_digest` | §9 field list(§2.2) |
| Ledger Command Record (§27 line 1176–1213; ADR-012 §9 line 253–277) | **DigestBoundArtifact** | `command_identity` | `canonical_command_digest` | command envelope(§2.4) |
| RCL Transition Record (§28 line 1216–1229; ADR-012 §19 line 489) | **DigestBoundArtifact** | `transition_id` | `canonical_transition_digest` | prev/new state·revision·vectors·epoch·cause(§2.6) |
| Transmission Capability (§12 line 615–634) | **DigestBoundArtifact** | `capability_id`(+`nonce`) | `canonical_capability_digest` | reservation·attempt·epoch·effect·qty binding(§2.5) |
| Protective Pool / Lease (§19 line 862–913) | **DigestBoundArtifact** | `pool_id`/`lease_id` | `canonical_digest` | pool/lease vector·scope·owner epoch(§2.7) |
| Authoritative Snapshot (ADR-012 §17.1 line 423–433) | **DigestBoundArtifact** | `snapshot_id` | `canonical_digest` | 완전성 세트(§2.8) |
| Capacity Vector + Dimension Descriptor (§6.1 line 218–248) | **plain FrozenModel** | — | — | (다른 레코드의 covered 내용) |
| Adverse Increment / Economic Effect Envelope (§6.3; §11.1 step 5) | **plain FrozenModel / 참조 블록** | — | (Envelope은 ADR-002-020 소유, id+digest 참조) | conservative vector(§5.1) |
| Grant / Decision 참조 블록 (Aggregate Risk / Action Flow Decision·Permit) | **plain FrozenModel(참조)** | id+generation+digest scalar | — | (§4.1 authority_effect=false) |
| Writer/Generation Fence State (§5.5–5.7; §13) | **plain FrozenModel** | — | — | (§6 술어 입력) |

> **IdDerivedArtifact 채택 아티팩트 = 0건.** 모든 RCL ledger 시민은 **독립·서비스 할당 identity**
> 를 가진다 — reservation_id는 terminal release 후 재사용 금지(§9 line 502)이고 retry/replication/
> restore 전반에 안정해야 하며(§8.5, RCLP-INV-006), command_identity는 same-id/diff-content 충돌
> 탐지의 좌표(§9 line 270)다. `id=f(digest)`면 이 모두가 vacuous가 된다(§3.1). ⇒ **전부
> `DigestBoundArtifact`(base), `IdDerivedArtifact`(capsule 전용) 미채택**(설계 #4·Time 동형의
> 일관 판정).

### 2.2 Reservation / Commitment Record (§9 line 473–503)

`DigestBoundArtifact` 서브클래스, 독립 `reservation_id`. covered(Layer-1) = ADR §9 line 477–500
필드: parent Intent identity, account/portfolio scope, instrument/underlying scope, action
class, normal/protective pool identity, approved quantity upper bound, **Adverse Increment
Vector**(§5.1), applicable risk scopes, Aggregate Risk Authority grant identity, evidence
snapshot identity, Hard Safety Envelope version, Runtime Safety Profile version, **ledger epoch +
creation revision**, current reservation revision, **current capacity state**(§2.3), bound attempt
identities, filled qty lower/upper bounds, remaining executable qty upper bound, protective
ownership, Trustworthy Time timestamps, audit causation/actor.

- self-제외(digest preimage 밖): `reservation_id`, `canonical_record_digest`, `status`
  (lifecycle 마커), `canonicalization_version`, **`current_reservation_revision`**(ledger
  배치 시 결정 — §2.6 transition이 소유), 파생 역참조. (설계 #4 §3.3 self-exclusion 규율 상속.)
- **identity ⊥ digest**(§3.1): `reservation_id`는 생성 후 불변·안정이며 content-digest에서 파생
  하지 않는다.
- `_REQUIRED_COVERED`(ISSUED에서 concrete 필수, TBD/null이면 DRAFT — `_base.py` line 135–155):
  **구조적 식별·스코프·버전·epoch** 필드로 한정 — parent Intent, account/portfolio·instrument
  scope, action class, pool identity, Adverse Increment Vector의 적용 차원 세트, grant identity,
  Hard/Runtime 버전, ledger epoch. **numeric bound(qty·vector magnitude)는 required로 넣지
  않는다** — 프로파일 bound가 Phase-1에서 null/PROPOSED이므로 required면 모든 snapshot이 DRAFT로
  떨어진다(Time 설계 §2.1 규율 상속). 대신 magnitude 누락은 **소비 술어에서 UNKNOWN⇒fail-closed**
  (§5.3).

### 2.3 Capacity State (§10 line 506–563)

`CapacityState(StrEnum)` = ADR §10.1의 9개: `COMMITTED_UNBOUND`, `ATTEMPT_BOUND`,
`POTENTIALLY_LIVE`, `PARTIALLY_CONSUMED`, `POSITION_CONSUMED`, `RELEASE_PENDING_PROOF`,
`QUARANTINED_UNKNOWN`, `TRAPPED_CONSUMED`, `RELEASED`. capacity state는 Intent/transmission/
broker-order/knowledge state와 **독립**(§10 line 508). `RELEASED`는 reservation identity에 대해
terminal(§10.1 line 562). 전이 원칙 §10.2(line 564–575)는 §5.4 보수성 lattice 술어로 실현.

### 2.4 Ledger Command Record (§27 line 1176–1213; ADR-012 §9·§10)

`DigestBoundArtifact`, 독립 `command_identity`. ADR-012 §10(line 294–311)의 command 의미론
(ActivateWriterEpoch, CommitReservation, ResizeReservation, BindAttempt,
AuthorizeTransmissionCapability, InvalidateCapabilities, ClaimCapabilityAndMarkSendStarted,
RecordFillAndTransferUsage, QuarantineUnknown, ApplyFinalQuantityProof, ReleaseReservation,
CommitProtectivePool, IssueProtectiveLease, ReconcileProtectiveLease, AdvanceRestoreGeneration,
ChangeMembership) + ADR-002-002 §27 command를 `CommandType(StrEnum)`으로. command envelope
covered(ADR-012 §9 line 255–264): command identity·canonical schema version, Capacity Domain·
cluster identity, **expected Writer Epoch·membership generation·Restore Generation**, expected
revision, actor identity·permitted role, causation/intent/attempt/reservation/evidence/profile
identities, requested transition, trustworthy-time evidence.

- **`command_identity` ⊥ `canonical_command_digest`**(§3.1): §9 line 270 "duplicate identity
  with different content" 거부 + RCLP-INV-006를 표현·탐지하기 위해 필수.
- **conservatism 표식**: "commands reducing conservatism require stronger proof"(ADR-002-002 §27
  line 1212; ADR-012 §9 line 273 "missing proof for a less-conservative transition" 거부) —
  §5.4 술어 입력.

### 2.5 Transmission Capability (§12 line 615–634)

`DigestBoundArtifact`, 독립 `capability_id` + `nonce`. covered = single-use 표식, reservation·
attempt binding, account/instrument/side/max-qty binding, ledger epoch binding, live
authorization/protective lease binding, Hard/Runtime 버전. **capability는 non-mutating token**
이다 — capability 발행/보유가 capacity를 mutate하지 않으며, 오직 RCL의 `ClaimCapabilityAndMark
SendStarted` command(§2.4)만이 nonce를 **정확히 1회** 소비하고 `POTENTIALLY_LIVE`로 전이한다
(§4.1 capacity≠authority; ADR-012 §12 line 337–344). `authority_effect.*` = false(§4.1).
Phase 1은 **capability binding 술어 + claim nonce-once idempotency**(§6.4)만 저작하고, 실제
send boundary는 이연(RCLP-EV-007 not-Phase-1, §1).

### 2.6 RCL Transition Record (§28 line 1216–1229; ADR-012 §19 line 489)

`DigestBoundArtifact`, 독립 `transition_id`. covered = previous state·revision, new state·
revision, **capacity vectors before/after**, limits·versions used, authority epoch, command·actor
identity, causation/correlation, evidence references, rejection reason, trustworthy-time evidence.
transition record는 append-only 시퀀스의 원소이며, 그 `new_authoritative_revision`이 reservation
의 현재 revision을 정한다(§2.2 self-exclusion 근거). 이 레코드가 evidence로 emit되는 것은 설계 #4
소관(RCL은 scalar만 남긴다).

### 2.7 Protective Pool / Lease + Sub-Ledger 경계 (§19; ADR-012 §16)

- `ProtectivePool`(DigestBoundArtifact): pool_id, capacity vector, scope. normal headroom에서
  제거됨(§19.1 line 866–874; INV-009).
- `ProtectiveLease`(DigestBoundArtifact): lease_id, parent pool identity, capacity vector, scope,
  **current owner identity·lease owner epoch·monotonic authorization lifetime·Safety Authority
  epoch binding**, Hard/Runtime 버전(§19.2 line 877–891).
- **sub-ledger 경계는 데이터 불변식으로만**(§5.5): sub-ledger는 normal headroom에서 이미 제거된
  소비에 대한 별도 상태 기계이며 **parent capacity를 enlarge/recycle/overlap/last-write-wins
  merge할 수 없다**(§19.3 line 894–905; ADR-012 §16 line 409–417). 실제 partition/rejoin
  reconciliation은 런타임(RCLP-EV-011 not-Phase-1).

### 2.8 Authoritative Snapshot (ADR-012 §17.1 line 423–433)

`DigestBoundArtifact`, 독립 `snapshot_id`. covered = cluster identity·Capacity Domain·membership
generation·Restore Generation·Writer Epoch·last included revision, 전체 RCL state·aggregate
invariant inputs, **non-terminal reservations·attempts·capability authorizations·claims·
send-start records**, **command-idempotency keys·conflicting-duplicate evidence**, protective
pools·leases·sub-ledger import state·UNKNOWN/external/trapped/replacement allocations, profile·
Hard Envelope generations, integrity commitment. **완전성 술어**(RCLP-INV-009)는 §5.6·§4.4.
암호학적 rollback-detection 메커니즘은 이연(§3.2 (b)).

---

## 3. canonicalization + digest REUSE 계약

### 3.1 REUSE 결정 + `id=f(digest)` 미채택 (핵심 아키텍처)

**(a) REUSE.** RCL ledger 시민(§2.1 표의 DigestBoundArtifact 6종)은 설계 #4 `tos.canonical.
DigestBoundArtifact`(`_base.py` line 91–246)의 **digest 검증**(`canonical_digest ==
H_ver(canonicalize(covered))`, line 171–205)을 REUSE한다. canonicalizer는 `tos.canonical`
registry + `EVL1ProvisionalCanonicalizer`(`ev-l1-provisional-0`) REUSE, 신규 canonicalizer
없음(프로덕션 canonical form은 Phase-0, §9.2). `_num_token`의 `Decimal` 정규화가 capacity
magnitude(1.0 == 1.00, float 잡음 제거 — `canonicalization.py` line 78–97)를 정규화하되
`scale`/`unit`/`sign` 메타 필드는 별개 문자열로 보존한다(안전-유의 구분 보존, 동 line 81–85).

**(b) `id=f(digest)`(`IdDerivedArtifact`) 미채택.** RCL 레코드 identity는 **digest에서 파생하지
않는다**. 근거(evidence §2.1/§3.1과 동형, capsule과 정반대):

- **same-command-id/diff-content 탐지**: ADR-002-012 §9 line 270은 "duplicate identity with
  different content"를 State Machine이 **거부**하도록, RCLP-INV-006(line 169–171)은 "One command
  identity produces at most one authoritative transition and one stable result"를 요구한다.
  이를 **표현·탐지**하려면 `command_identity` ⊥ `canonical_command_digest`여야 한다 —
  `id=f(digest)`면 same-id ⟹ same-bytes이므로 "same id + different content" 거부가 **vacuous**가
  되고 idempotent-retry(same id + same bytes ⇒ same result, §21 line 522)와 conflict(same id +
  different bytes ⇒ 거부)의 구분이 사라진다.
- **reservation_id 재사용 금지·안정성**: §9 line 502 "reservation identity SHALL never be reused
  after terminal release"와 §8.5 retry/failover 전반의 안정성은 identity가 content와 무관한
  서비스 할당 좌표임을 전제한다.

⇒ **전부 `DigestBoundArtifact`(base)를 상속하고 독립 identity 필드를 갖는다.** 설계 #4가 이미
base/subclass를 분할해 두었으므로(`_base.py` line 91–107 "This base derives **no** id"; evidence가
직접 상속) **RCL은 코드 변경 없이 그 base를 REUSE**한다.

**(c) same-command-id/diff-bytes 충돌 분류기 = core로 PROMOTE(§0.4b), 재저작 아님.** 설계 #4
`classify_record_pair`(`tos/src/tos/evidence/predicates.py` line 84–130)는 **evidence-특화 결합이
없는 순수** `(identity, digest) → {IDEMPOTENT_DUP, CRITICAL_CONFLICT, DISTINCT, NOT_COMPARABLE}`
분류기다(null digest ⇒ `NOT_COMPARABLE`, line 109 — false conflict 방지, 설계 #4 MINOR-1 규율).
RCL도 same-command-id/diff-bytes 충돌·idempotency(RCLP-EV-005 core)에 **이 정확한 술어**가
필요하므로 — **재저작(중복 = DRY 위반) 대신 core로 PROMOTE**하여(ordering·canonicalization
PROMOTE 선례; DRY·layering 동시 clean) RCL·evidence가 **동일 core primitive를 REUSE**한다.
evidence는 shim으로 무회귀 유지한다(ordering PROMOTE가 `tos.evidence.predicates` shim으로
ERI-EV-006 green을 유지한 선례 동형). RCL은 이 core 분류기를 command/reservation 쌍에 적용한다.
정확한 core home(canonical 인접 vs 전용 core 모듈)은 구현 시 결정(§9.1). §4.5 상술.

### 3.2 ordering REUSE + segment-commitment 이연

**(a) ordering REUSE.** RCL은 committed order·Log Revision을 **신규 저작하지 않고**
`tos.ordering`(Trustworthy Time 설계 §5로 PROMOTE 완료, 코드 `tos/src/tos/ordering/_ordering.py`)의
`Ordering`·`OrderingEvent`·`compare_order`를 REUSE한다. `OrderingEvent`(line 49–75)의 필드는
**애초에 ADR-002-012/016 개념을 담아 core로 승격된 것**이다(Time 설계 §0.4b line 166–168):

- `quorum_commit_index`(line 67) = RCL **Log Revision**(§5.6 line 133–135). committed prefix의
  단조 좌표(RCLP-INV-003 "one total order" line 157–159, RCLP-INV-005 "committed prefix does
  not regress" line 165–167).
- `egress_journal_sequence`(line 68) = §12 `ClaimCapabilityAndMarkSendStarted` 순서.
- **wall clock은 순서를 만들지 않는다**(`_ordering.py` line 22–24) — ADR-012 §8.5 line 247–249
  "Consensus ordering does not depend on wall clock"와 정합. `compare_order`는 이를 이미 강제.

**(b) segment-commitment PROMOTE 이연**(§0.4b): RCL Safety Commit Log의 tamper-evident segment
commitment은 `tos.evidence.ledger.SegmentCommitmentScheme`(설계 #4 §3.4)과 동일 프리미티브지만,
**RCL은 evidence의 상류**(ADR-012 §19 line 478)이므로 `tos.rcl → tos.evidence` edge는 layering
역전이다. 그리고 **Phase 1 core는 이 프리미티브가 필요 없다**: committed-prefix 단조(RCLP-INV-005)
는 `quorum_commit_index` 단조 술어(§4.3)로 충분하고, 암호학적 prefix/fork tamper-detection은
predicate-only인 RCLP-EV-010의 **메커니즘**이라 Phase 1이 주장하지 않는다. ⇒ **지금 PROMOTE하지
않는다.** 향후 그 substrate를 저작할 때 `evidence.ledger`의 scheme을 **core로 PROMOTE**하며(§9.1),
**결코 `tos.evidence`를 import하거나 RCL 안에 중복 저작하지 않는다.**

### 3.3 digest 커버리지 + 자기제외 (설계 #4 §3.3 상속)

`covered = Layer-1`(레코드별 §2.2/§2.4/§2.5/§2.6/§2.8). preimage 제외: identity 필드(§2.1),
`canonical_*_digest`, `canonicalization_version`, `status`(lifecycle 마커), ledger 배치 시
결정되는 값(`current_reservation_revision`·`new_authoritative_revision` — transition이 소유),
서명 필드, 파생 역참조. **TBD/null이 covered에 하나라도 있으면 pre-issuance(status=DRAFT),
digest 불가**(`_base.py` line 174–184).

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **fail-closed
discipline**: 빈/누락 집합에 대한 술어는 절대 vacuous True가 되지 않으며, 보수성은 *양성 증명*을
요구하고, 각 가드에 **negative/canary property**(가드가 실제로 발화함)를 붙인다.

### 4.1 capacity ≠ authority (중앙 불변식 — RCLP-INV-001/012 + ADR-002-002 §1/§7.1)

설계 #4의 evidence ≠ authority(ERI-INV-001/014) 동형. 4개 층으로 실현:

1. **grant/decision/capability/snapshot은 비권위**: 모든 GRANT/DECISION 참조 블록·Transmission
   Capability·Snapshot의 `authority_effect` 블록은 **전부 false 상수**이며, true면 **구성 실패**
   (설계 #2 `SnapshotAuthority._all_authority_false` 패턴 REUSE — `capsule/_base.py` line 70–78;
   `grants_no_authority` 술어 `evidence/predicates.py` line 622–634 동형 저작). 근거: ADR-002-002
   §7.1 line 322–331(Aggregate Risk Authority "issues a capacity grant decision; does not
   directly mutate the Ledger; does not transmit; does not release capacity"); ADR-012 §1 line 31
   ("Sharing the consensus substrate does not grant … the right to mutate capacity"); §10 line
   282–290.
2. **오직 RCL commit만 mutate**: capacity state 변화는 **결정적 reducer가 검증된 command를
   적용할 때만** 일어난다. GRANT/DECISION/SNAPSHOT 객체에는 mutated capacity를 반환하는 메서드가
   **존재하지 않는다**(구성적 부재 — Time 설계 "no method to reconstruct anchor from wall" 동형).
   RCLP-INV-001(line 149–151) "Only the deterministic RCL State Machine may create, reserve,
   commit, transfer, quarantine, remap, resize, or release capacity."
3. **grant는 정확한 allocation request만 authorize**: `grant_authorizes_exact_request(grant,
   committed_reservation) -> bool` — grant가 **정확한 committed reservation revision + effect
   digest + 현재 generation vector**에 bind되어야 유효(§11 line 317–327; §8.4 line 461–463
   "stale approval cannot be committed against changed Ledger state"). 정확 binding 실패 ⇒
   비권위(거부). **canary**: 다른 revision/digest에 bind된 grant는 반드시 거부.
4. **documentation/projection ≠ authority**(RCLP-INV-012 line 193–195): capacity-affecting
   술어는 projection/audit/runbook/human-declaration 필드를 **authorization 입력으로 읽지
   않는다.** reducer의 입력은 committed command뿐이며, projection 계열은 display-only(§8.4 line
   245, ADR-002-002 §26.3 line 1166–1168). 이 불변식이 **RCL이 `tos.evidence`(하류 투영)를
   import하지 않는** firewall 근거이기도 하다(§0.3).

### 4.2 append-only (ADR-012 RCLP-INV-005; ADR-002-002 §28)

모델에 **update/delete 연산 부재**(§2.0). resize/transfer/release/quarantine/correction은 전부
새 committed command/transition의 append로 표현. property: 임의 lifecycle 시나리오에서 기존
레코드의 covered 필드 불변; 변화는 오직 append로만 관측.

### 4.3 단조 epoch/generation floor + committed-prefix 단조 (RCLP-INV-003/004/005)

- **Log Revision 단조**: committed prefix의 `quorum_commit_index`는 엄격 증가하며 prefix 보존
  (RCLP-INV-003 line 157–159, RCLP-INV-005 line 165–167). property: 재정렬/역행/누락이 표현
  불가; `compare_order`로 committed order를 계산(§3.2).
- **Writer Epoch / membership generation / Restore Generation 단조 floor**: 각 floor는 결코
  역행하지 않으며, floor 미만 값은 fenced(§6). (§5.5 line 129, §5.7 line 137, §14 line 371.)

### 4.4 same-command-id/diff-bytes 충돌 + snapshot 완전성 (RCLP-INV-006/009)

- **충돌 술어**(§4.5, §3.1c): `classify_record_pair`(core PROMOTE). same command_identity + diff content ⇒
  `CRITICAL_CONFLICT`(contain + 양쪽 보존, no merge — ADR-012 §21 line 522 참조; ADR-002-002
  §16.4 late-fill breach와 정신 동형). same id + same bytes ⇒ idempotent dup(같은 결과 반환,
  RCLP-INV-006).
- **snapshot 완전성**(§5.6): `snapshot_admissible_for_restore(snapshot) -> bool` — non-terminal
  reservation·idempotency key·generation fence·capability-use·proof-gated release·history
  commitment 중 **하나라도 누락이면 inadmissible**(RCLP-INV-009 line 181–183; ADR-012 §21 line
  528 "Snapshot missing idempotency or capability-use state ⇒ reject snapshot"). 설계 #4
  `tombstone_admissible`(line 371–386) fail-closed 패턴 동형. **canary**: idempotency key 없는
  snapshot은 inadmissible(vacuous admissible 금지).

### 4.5 same-command-id/diff-bytes 충돌 상세

`classify_record_pair(a, b)` (§0.4b/§3.1c대로 설계 #4에서 **core로 PROMOTE**된 공유 분류기;
RCL이 command/reservation 쌍에 적용 — 재저작·evidence import 아님):

- 어느 하나라도 null digest(DRAFT) ⇒ `NOT_COMPARABLE`(ledger 시민 아님, false conflict 방지).
- same `command_identity` + same digest ⇒ `IDEMPOTENT_DUP`(retry — 같은 committed 결과 반환,
  RCLP-INV-006, §21 line 522).
- same `command_identity` + diff digest ⇒ `CRITICAL_CONFLICT`(§9 line 270 거부; contain, no
  last-write-wins).
- 그 외 ⇒ `DISTINCT`.

property(중앙): identity ⊥ digest이므로 위 4분류가 모두 도달 가능(가드 발화); id=f(digest)면
CRITICAL_CONFLICT가 unreachable이 됨을 회귀로 고정.

### 4.6 conservative economic-effect·release 불변식 (ADR-002-002 §5, 순수)

- **INV-001 Aggregate Envelope**(line 127–152): 모든 usage category 합 ≤ EffectiveLimit =
  min(Hard, Runtime). **순수 산술**, transfer는 원자적 이전(중복 계상 금지, line 152). core
  property(RCLP-EV-001 L1 슬라이스의 핵심 검사, §5.2).
- **INV-003 Exclusive Headroom**(line 160–162): 같은 headroom 단위를 두 reservation/pool/lease/
  quarantine에 커밋 금지. 순수.
- **INV-005 No Expiry of Economic Effect**(line 168–172): TTL/lease expiry/restart/operator
  declaration/missing query가 potentially-live/UNKNOWN을 release하지 못함. 순수 release 술어
  (설계 #4 §4.5 retention orthogonality 동형).
- **INV-006 UNKNOWN Consumes**(line 174–176): 불확실성 ⇒ 보수 상한이 capacity 소비. 순수(§5.3
  missing-dimension=restrictive와 결합).
- **INV-007 Final Quantity Before Release**(line 178–185): release는 final cumulative filled +
  zero remaining, 또는 profile-승인 stronger proof 후에만. 순수 release 술어.
- **INV-009 Protective Reserve Non-Borrowable**(line 198–200): normal usage 합 ≤ EffectiveLimit
  − ProtectivePoolCommitted. 순수.
- **INV-011 Trapped Non-Reducible**(line 206–208): trapped exposure는 계획된/미확인 exit로
  discount 금지. 순수(계획 exit 입력이 trapped usage를 줄이지 않음).
- **INV-012 Reconciliation Cannot Optimistically Free**(line 210–212): reconciliation은 정의된
  transition의 evidence만 제공; optimistic snapshot으로 overwrite하거나 "한 소스가 미보고" 만으로
  release 금지. 구성적 부재("overwrite from snapshot" 연산 없음) + 술어.
- **INV-010 Partition Does Not Create Capacity**(line 202–204): §6.5 deny-table 술어.

not-pure(이연): **INV-002**(unique commitment mapping, "executable broker attempt"는 broker/
런타임 — +Broker/L3; 파생 술어만), **INV-004**(no transmission without capacity — *transmission*은
egress/L3; binding 술어는 §6.4 L1), **INV-008**(stale authority cannot mutate/**transmit** —
fence 술어는 §6 L1, transmit은 egress/L3).

---

## 5. aggregate commitment 세부 (ADR-002-002)

### 5.1 conservative projection — 단조성 + benefit=0 unless proven + missing-dim=restrictive

**Adverse Increment Vector**(§6.3 line 268–279): "maximum credible increase in usage over all
approved execution paths"; "never made negative merely because the intended final action is risk
reducing"(line 277). 세 fail-closed 규칙:

1. **단조성**: 주입 불확실성 항이 커질수록 projected vector는 **비감소**(더 큰 불확실성 ⇒ 더 많은
   capacity 소비). property: 각 불확실성 항에 대해 monotone non-decreasing(Time
   `conservative_usable_lifetime` 단조성의 부호 반대 동형). 음수-clamp 없음.
2. **benefit = 0 unless positively proven**: `apply_benefit(base_vector, benefit_claim, proof)
   -> vector` — netting/hedge/diversification/correlation benefit은 **양성 proof token**
   (broker/profile-proven, §6.5 line 316 "only when the Broker Capability Profile proves the
   enforcement scope and behavior"; scope-proven)이 **동반될 때만** base_vector를 감소시킨다.
   proof 부재 ⇒ base_vector 그대로(감소 없음). **canary**(리뷰어 지적 "unverified conservatism"
   선제): `apply_benefit(v, claim, proof=None) == v`; "no-benefit flag 부재"만으로는 감소 불가 —
   *양성* proof token을 요구한다. (ADR-002-021 §5 ARE-EV-005 "Netting Hedge Correlation and
   Common Mode"가 인접 규범; 본 문서는 ADR-002-002 §6.3/§6.5 순수 규칙만 저작.)
3. **missing-dimension = restrictive**(빈-집합 fail-open 방지 — 핵심 canary): `within_limits(
   effect, limits, applicable_dimensions) -> bool` — (i) `applicable_dimensions`가 **비어 있으면
   거부**(False), (ii) 적용 차원 중 하나라도 effect 또는 limit에서 누락/UNKNOWN이면 거부. 즉
   `all(dim within limit for dim in dims)`의 **vacuous True를 금지**하기 위해, 적용 차원 세트가
   명시적·비어있지-않음 + 모든 적용 차원이 양쪽에 concrete 값으로 present여야 통과. 근거: §6.2 line
   265 "accepted only if **every** applicable scope remains within its Effective Limit"; §6.1 line
   240–248 "every dimension SHALL have unit/scope/…". **canary**: 빈 차원 세트 ⇒ `within_limits`
   == False(절대 True 아님); None 차원은 0으로 취급되지 않음.

### 5.2 결정적 reducer / no-double-spend (RCLP-EV-001 L1 슬라이스)

`apply_committed(state, command) -> state'`는 committed order 위의 순수 fold다. property:

- **결정성**(ADR-012 §9 line 276): 출력은 (ordered command sequence, initial state)에만 의존;
  randomness/local clock/network/env/unordered-collection이 결과를 바꾸지 않는다.
- **no-double-spend**(INV-001 + AC-001 line 1378–1382): 개별적으로는 맞지만 합쳐 한 limit을 초과
  하는 두 CommitReservation을 한 order로 fold하면 **정확히 하나만** admit되고 다른 하나는
  거부/재평가(§8.4 CAS line 449–463; 두 번째는 변경된 usage/revision을 보고 실패). **producer
  optimism 방지 canary**(리뷰어 지적 선제): `available_headroom(state)`는 **committed 상태에서만**
  계산; producer-local counter·scheduler priority를 주입해도 headroom이 변하지 않는다(§11.2 step
  10 line 594 "producer-local counters and scheduler priority create no headroom").
- **경계**: 이 슬라이스는 "주어진 committed order 위 no-double-spend + 결정성"만 주장한다. 그
  단일 order를 동시성/파티션에서 quorum이 산출함은 EV-L3(Phase B, §0.2).

### 5.3 UNKNOWN·conservative bound 소비 (INV-006, §22.2)

capacity vector의 한 차원 magnitude가 `None`(UNKNOWN)이면 **fail-closed**: 그 차원은 보수 상한이
없으므로 within-limit 증명 불가 ⇒ 거부(§5.1 규칙 3). reconciliation은 upper bound만 사용하고
lower bound는 위험을 과소평가하지 않을 때만(§22.2 line 1051–1057); optimistic midpoint/blended
score 금지. 설계 #2 `Freshness{within_bound: bool|None}`⇒UNKNOWN fail-closed 패턴 REUSE.

### 5.4 capacity-state 보수성 lattice (§10.2 line 564–575)

`transition_allowed(from_state, to_state, cause) -> bool`: 상태를 **보수성 부분순서**로 두고,
**less-conservative 방향 전이는 강한 cause를 요구**한다 — strongly-authorized command /
broker-evidence-under-profile / reconciliation-evidence-meeting-proof / recognized-external-change
/ containment. **timeout/absence/operator-assumption은 오직 보수성을 *증가*시킬 수만 있다**(§10.2
line 573–575 "No transition to a less conservative state may be made solely from timeout,
absence, or operator assumption"; §18.6 UNKNOWN no auto-release line 848–852; §18.7 TTL line
854–858). "commands reducing conservatism require stronger proof"(§27 line 1212; ADR-012 §9 line
273). **canary**: `RELEASED`로의 전이는 final-quantity proof 없이는 불가; `QUARANTINED_UNKNOWN`→
less-conservative는 timeout만으로 불가. 설계 #4 gap-state forward-only(`gap_transition_allowed`
line 190–203) 정신 동형(단 여기는 부분순서 + cause-gated).

### 5.5 protective pool / lease / sub-ledger (§19)

순수 불변식: (i) partition 중 새 parent pool 생성·lease enlarge·소비 recycle 금지(§19.5 line
915–924; INV-010); (ii) sub-ledger는 lease vector 초과 소비 금지·stale owner epoch 거부·duplicate
command 거부(§19.3 line 894–905); (iii) authorization expiry만으로 parent 재할당 금지(§19.4 line
907–913, reconciliation 필요). 실제 partition/rejoin/broker reconciliation은 런타임(RCLP-EV-011
not-Phase-1). protective owner split-brain(§20.4 line 967–971): 한 lease는 한 owner epoch;
reconcile 전 재할당 금지 — §6 fence 술어로.

### 5.6 committed-prefix 단조 + snapshot 완전성 (RCLP-EV-010 predicate-only)

- committed-prefix 단조: §4.3 `quorum_commit_index` 술어.
- snapshot 완전성: §4.4 `snapshot_admissible_for_restore`.
- **restore 비활성 기본 + non-revival**(§6.5, RCLP-INV-011): restore는 새 Restore Generation을
  만들고 default non-live, prior capability/session 무효화(ADR-012 §17.4 line 445–453). "restored
  older snapshot이 최신 backup이라는 이유만으로 authoritative가 되지 않음"(line 455) — authority는
  명시적 re-arm(out-of-scope)을 요구; 모델은 "newest backup ⇒ authoritative" 연산을 제공하지 않음.

---

## 6. writer fencing 술어 세부 (ADR-012 §13, RCLP-INV-004)

**핵심 난제**: 실제 consensus 없이, **주입 epoch 상태 위 순수 술어**로 writer fencing을 fail-closed
모델링. ADR-012 §13(line 357–363)의 3층 중 **layer-2(state-machine fencing)만 EV-L1**이다:
layer-1(consensus fencing — minority/former leader가 commit 불가)과 layer-3(egress fencing)은
런타임(RCLP-EV-002/007 not-Phase-1). 본 절은 layer-2를 저작한다.

### 6.1 fence 술어 (fail-closed)

`writer_fenced(command, current_fence_state) -> bool` (True = FENCED/거부). 다음 중 **하나라도**
성립하면 FENCED:

- `command.writer_epoch < current.writer_epoch_floor`(stale writer, §13 line 355; RCLP-INV-004).
- `command.membership_generation != current.membership_generation`(removed/stale voter, §14 line
  375–376).
- `command.restore_generation != current.restore_generation`(restore 횡단, §5.7 line 139;
  RCLP-INV-011).
- `command.expected_revision != current.revision`(stale expected revision / CAS 불일치, §9 line
  259; ADR-002-002 §8.4).
- **위 좌표 중 하나라도 `None`(UNKNOWN) ⇒ FENCED**(fail-closed: currentness 증명 불가 ⇒ 거부).

**canary properties**(리뷰어 지적 "empty-set/optimism" 선제):

- `∀ command: 임의 currentness 좌표가 None ⇒ writer_fenced == True`(누락 상태가 vacuous admit로
  빠지지 않음 — 설계 #4 `eip_binding_ok` null-generation fail-closed, `predicates.py` line
  512–515 동형).
- `command.writer_epoch < floor ⇒ 항상 FENCED`.
- **가드 발화 존재성**: FENCED가 되는 command가 반드시 존재(술어가 constant-False가 아님).

### 6.2 단조 floor

`epoch_floor`·`membership_generation`·`restore_generation`은 committed ActivateWriterEpoch/
ChangeMembership/AdvanceRestoreGeneration으로만 전진하며 **결코 역행하지 않는다**(§5.5 line 129;
§13 line 353). property: floor는 monotone; 재활성/재부팅/restore/failover를 가로질러 continuous
임을 증명 못 하는 모든 stale 좌표는 fenced.

### 6.3 stale / minority / removed / restored / conflicting

- **stale**: epoch < floor ⇒ FENCED(§6.1).
- **minority**: consensus 개념 — EV-L1 순수 술어로는 "current-quorum commit-proof currentness
  flag가 false/unknown ⇒ FENCED"까지만(fail-closed). quorum-proof 자체는 L3(§0.2). Commit
  Proof(§5.4 line 121–125 "A leader signature or local success response alone is not Commit
  Proof")의 *구조*만 담고 검증은 이연.
- **removed**: membership_generation 불일치 ⇒ FENCED(§14).
- **restored**: restore_generation 불일치 ⇒ FENCED + non-live default(§5.6, RCLP-INV-011).
- **conflicting**: 같은 epoch·같은 expected_revision에서 서로 다른 content의 두 command ⇒
  `CRITICAL_CONFLICT`(§4.5, contain 양쪽 보존; fork 시도 = §18 observed-branch 정신, no merge).

### 6.4 capacity → capability 순서 binding (RCLP-EV-006 L1)

`capability_authorization_valid(auth, committed_reservation, fence_state) -> bool`: **이미
committed된 reservation revision을 참조**하고(§11 line 317), reservation active·attempt bound·
unused, **capacity vector가 정확한 worst-case effect를 cover**, Writer Epoch·Safety Authority
epoch·Live Authorization·profile·Restore/Recovery/membership generation이 **현재**, dominating
restriction/UNKNOWN 없음(§11 line 319–326)일 때만 유효. 하나라도 불충족 ⇒ 거부(uncommitted/
minority/stale/capacity-unbound capability는 서명돼도 무효 — §11 line 329). **claim nonce-once**:
`ClaimCapabilityAndMarkSendStarted`는 nonce를 정확히 1회 소비; 재claim은 원본 committed 결과 반환
(ADR-012 §12 line 343). **canary**: 다른 reservation revision·미cover effect·stale generation에
bind된 auth는 반드시 거부; missing generation은 fail-closed. (send boundary·egress는 이연 — §0.2.)

### 6.5 partition deny-table + non-revival (RCLP-EV-004/012 predicate-only)

- `partition_verdict(quorum_available: bool|None) -> Verdict`: quorum 미가용(또는 unknown)이면
  {new normal mutation, capability authorization, capability claim, normal transmission, capacity
  release, membership change(governed DR 제외), automatic re-arm} = **전부 DENIED**; 기존
  committed/potentially-live/UNKNOWN/trapped/protective usage = **PRESERVED(불변)**(§15 line
  389–401; RCLP-INV-008). quorum_available은 **주입 flag**(탐지는 런타임). **canary**:
  `None`(unknown) ⇒ 전부 DENIED(vacuous permit 금지); quorum 복구가 자동 re-arm하지 않음(§1 line
  37 "Quorum restoration … SHALL NOT automatically re-arm").
- **worst-credible-union / no-merge**(§18 line 459–472): `credible_union_capacity(histories,
  credible_state_space)` — capacity는 reconstructable histories의 **합집합**을 cover; Broker
  Capability Profile + Adverse Scenario Set에 bound되지 않는 history 상태는 **conservative
  UNKNOWN·capacity-consuming, 절대 drop 금지**(§18 line 472 Credible State Space, broker-agnostic).
  conflicting branch는 **last-write-wins merge 금지**, 전부 보존(설계 #4 observed_branches 동형).
  reconstructable histories 조립은 런타임(predicate-only).
- **non-revival**(RCLP-INV-011): generation N에서 무효화된 capability/lease/authority는 N+1
  이후에도 revive 안 됨(항상 True; Time `recovery_generation_revives_nothing` 동형). 모델은
  "generation 증가 ⇒ 유효성 복원" 연산을 제공하지 않는다.

---

## 7. property-test 하네스 타깃

§1의 EV-L1 분류에 정렬. property는 bound를 **hypothesis 생성 주입값**으로 다뤄 "임의 유효 bound
하 보수적 성립"을 검증한다(특정 값 비의존, 하드코딩 없음 — §8).

| family | Phase-1 타깃 | substrate / 근거 |
|---|---|---|
| record canonicalization + digest 검증 | **REUSE 설계 #4 §3.4 (A) must-pass suite** (`tos.canonical`) | RCL 레코드 covered로 재적용; frozen digest 일관성(`_base.py` 171–205) |
| same-command-id/diff-bytes 충돌 + idempotency | **core** | `classify_record_pair`(core PROMOTE, §4.5); RCLP-EV-005 L1 / §9 line 270 |
| 결정적 reducer / no-double-spend / aggregate envelope | **core (L1 슬라이스)** | §5.2; RCLP-EV-001 L1 / INV-001 / AC-001. producer-optimism canary |
| conservative projection (단조·benefit=0-unless-proven·missing-dim=restrictive) | **core** | §5.1; §6.3/§6.5 (빈-집합 fail-open canary) — RC-EV substrate(EV 비주장) |
| capacity→capability binding + claim nonce-once | **core (binding)** | §6.4; RCLP-EV-006 L1 (send는 비주장) |
| writer-fence 술어 (stale/removed/restored/revision + missing⇒fenced) | **predicate** | §6.1–§6.3; RCLP-EV-003 substrate (§13 layer-2) |
| partition deny-table + 경제효과 보존 | **predicate** | §6.5; RCLP-EV-004 (§15) |
| capacity-state 보수성 lattice (timeout/absence는 보수성만 증가) | **predicate** | §5.4; §10.2 line 573–575 |
| release 규칙 (final-quantity / UNKNOWN / TTL / trapped) | **predicate** | §4.6; INV-005/007/011, §18 |
| snapshot 완전성 + committed-prefix 단조 | **predicate** | §4.4/§5.6; RCLP-EV-010 (INV-009/005) |
| worst-credible-union + no-merge + non-revival | **predicate** | §6.5; RCLP-EV-012 (§18), RCLP-INV-011 |
| capacity≠authority (flag 불변식 + grant-binds-exact + documentation≠authority) | **flag 불변식 + 거부 술어** | §4.1; RCLP-INV-001/012 |

- **core(L1 슬라이스)**: RCLP-EV-001/005/006 + RC-EV substrate invariants(INV-001/003/006 등).
  **어떤 항목도 EV를 닫지 않는다**(§1 규율).
- **predicate-only**: RCLP-EV-003/004/008/010/012.
- **not-Phase-1**: RCLP-EV-002/007/009/011 + 전 RC-EV.
- **bound 처리**(설계 #2 §7·#4 §7 상속): property는 bound를 hypothesis 생성 주입값으로 다룬다.
  어떤 숫자도 하드코딩하지 않는다(§8, CLAUDE.md 설정 기반).

### 7.1 import-closure 검증 테스트 (C1 강제 — 설계 #4 §7.1 확장)

서브프로세스에서 `import tos.rcl`(및 `tos.canonical`·`tos.ordering`)만 한 뒤 `sys.modules`를
검사해 assert: (1) 설계 #1 §2.3 금지 패키지 부재; (2) **`shared.config`·`shared.config.secrets`
부재**(전이 유입 런타임 포착); (3) `os.environ`/`os.getenv` 미참조; (4) **`numpy`·`pandas`·`yaml`(pyyaml) 부재**(bound는 주입·YAML 파싱은 하네스 소관)
(§0.3); (5) **`tos.capsule`·`tos.evidence` 부재**(§0.3/§3.1 layering — RCL은 evidence의 상류이자
capsule의 형제이므로 closure에 이들이 없어야 하며, ordering은 core `tos.ordering`에서만 온다).
required check(`tos-firewall` — `tools/tos_firewall_check.py` layer-① AST 게이트 + `.importlinter`
layer-② 전이 방어)와 함께 green이어야 §0.3 준수 선언이 능동 성립한다.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

evidence를 산출하는 모든 property-test run은 다음을 기록: (1) git commit digest + `tos` 버전;
(2) 인터프리터 + 고정 의존성 버전(pydantic/hypothesis); (3) 실행 환경; (4) 하네스 git digest;
(5) **property-test seed**(hypothesis seed/derandomize, append-only); (6) **소비 설정 아티팩트
digest**(주입 RCL/capacity bounds 프로파일 + `canonicalization_version` + `tos.ordering`
primitive 버전); (7) 산출 아티팩트 sha256. (VER-002-001 §2.3 재현성·§3 baseline·§9.1 seed·§9.2
digest의 EV-L1 부분집합.) RCL 전용 run-manifest 템플릿은 없으므로 설계 #1 §5.1 규율을 REUSE한다.

---

## 8. bounds 주입 + 누락 프로파일 키 Phase-0

`VERIFICATION-PROFILE-002.yaml`은 전체 `status: PROPOSED`·`approved_by: []`·`effective_from:
null`(line 18–20; 배너 line 3–5 "an unapproved or placeholder bound is not an approved bound").
ADR-002-002 §37(line 1560–1577)·ADR-002-012 §27(line 660–680)·§28 gate 14(line 701)는 numeric
bound·Failure-Domain Allocation Matrix를 승인 프로파일 소관으로 못박는다.

- **결정**: 모든 bound(EffectiveLimit 차원 magnitude·protective reserve minimum·`B_stale_epoch_
  reject`·`B_capability_claim_to_send`·external-activity detection window·startup-reconciliation·
  quarantine escalation horizon·f/2f+1 voting 등)는 **주입 policy 파라미터**로만 모델에 들어온다.
  **어떤 숫자도 하드코딩하지 않는다**(CLAUDE.md). 값 누락 ⇒ `UNKNOWN` ⇒ fail-closed(§5.3, §6.1).

- **실측 확인(evidence-based)** — 프로파일에 **존재하는** 관련 키:
  - `B_stale_epoch_reject`(line 177–181): `value_ms: 0` / PROPOSED. rationale: "Rejection of a
    stale ledger/authority epoch is **synchronous** at the ledger transition and final egress
    (compare-and-set); 0 = no time window(ADR-002-002 INV-008, ADR-002-003)." ⇒ writer-fence를
    **동기 순수 술어**(§6)로 모델링함을 프로파일이 지지(시간 창 없음).
  - `B_capability_claim_to_send`(line 163–169): `value_ms: null` / APPROVE, `failure_response:
    QUARANTINE_UNKNOWN`. ⇒ RCLP-EV-007(claim→send) egress, not-Phase-1.
  - `B_external_activity_detect`(line 184) `2000` / PROPOSED, `B_external_activity_contain`(191);
    `B_startup_reconciliation`(198); `B_final_quantity_proof`(569) — ADR-002-002 §23.4/§21.6/§16.3.
  - `B_aggregate_risk_invalid_to_rcl`(268) / `B_action_flow_invalid_to_rcl`(282): `null` /
    "APPROVE after … RCL admission fencing" — grant→RCL currentness(§4.1 capacity≠authority).
  - `MAX_unresolved_send_per_scope: 1`(line 702, "from template: at most one unresolved send per
    scope") — INV-002 unique-commitment-mapping의 count 표현(주입, 하드코딩 아님).
  - `B_failure_domain_detect`/`_contain`(611/618): `null` / "APPROVE per concrete **Failure-Domain
    Allocation Matrix**" — ADR-012 §27 Q2·§28 gate 1/14의 Capacity Domain/failure-tolerance 모델이
    미승인임을 프로파일이 확인.

- **누락 distinct 키 (Phase-0 Bounds-Approver 플래그)**: 실측 대조 결과 —
  1. **Reserved Protective Capacity 최소치(magnitude) 전용 키 부재**: ADR-002-002 INV-009(line
     198–200)·§19.1(line 866–874)의 "configured minimum Reserved Protective Capacity"에 대응하는
     distinct 프로파일 키가 **없다**(grep `protective_reserve|reserve_min|min_protective` 0건;
     `B_protective_request_start/complete`(583/590)·`B_protection_gap/overlap`(625/632)은
     *지연* bound이지 *예약 최소치*가 아니다). ⇒ INV-009는 **주입 슬롯으로 선언**하되 값·키 승인은
     Bounds-Approver로 넘긴다(누락 시 UNKNOWN⇒normal usage 술어가 보수적으로 fail-closed).
  2. **Capacity Domain 경계 + f/`2f+1` voting 모델**: ADR-012 §27 Q2·§28 gate 1은 이를 미승인
     으로 둔다(`B_failure_domain_detect` null이 이를 확인). 이는 **Phase B(consensus)** 소관이며
     Phase 1 EV-L1 scope 밖(§0.2).
  3. **quarantine escalation horizon**: ADR-002-002 §37 Q10 "How long may capacity remain
     quarantined before mandatory operator escalation?"에 대한 *capacity-quarantine 전용* 키는
     없다(`B_operator_escalation`(667)은 generic). Phase-0 플래그.

  본 계약은 이 누락/generic-folded 키를 **Phase-0 프로파일 보강 항목으로 플래그**한다(설계 #4 §8·
  Time §8 동형). 모델은 각 항을 **주입 슬롯으로 선언**하되(누락 시 UNKNOWN fail-closed), 값·키
  승인은 **Bounds-Approver 게이트**(Live-Armer와 분리 — IMPLEMENTATION-PLAN §3)로 넘긴다.

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

- **`tos/src/tos/rcl/` 모델·술어·property·import-closure 테스트 저작**(§2–§7): 설계 #3(EV-L1
  하네스)이 property suite를 실행. `tos.canonical`(digest) + `tos.ordering`(committed order)
  **REUSE**, 신규 canonicalizer/ordering 없음.
- **`classify_record_pair` core PROMOTE(지금 — §0.4b/§3.1c)**: 구현 **선행 소단계**로
  `tos.evidence.predicates.classify_record_pair`(pure `(identity,digest)→kind`)를 core로 이동
  (정확한 home은 ordering PROMOTE 선례대로 결정 — `tos.canonical` 인접 또는 전용 core 모듈),
  `tos.evidence.predicates` shim으로 ERI-EV 무회귀 확인, RCL·evidence가 **동일 core primitive
  REUSE**. **`tos.rcl → tos.evidence` edge 금지·중복 저작 금지.** (Phase-1 PROMOTE 1건.)
- **segment-commitment PROMOTE 여부(이연 — §3.2b)**: 향후 RCLP-EV-010의 암호학적 prefix/fork
  tamper-detection substrate를 저작한다면, `tos.evidence.ledger`의 `SegmentCommitmentScheme`을
  **core로 PROMOTE**(ordering PROMOTE 선례)해 RCL·evidence가 공유한다. **원칙: `tos.rcl →
  tos.evidence` edge 금지(RCL은 evidence의 상류), RCL 내 중복 저작 금지.** Phase 1은 이 substrate를
  저작하지 않으므로 PROMOTE 불요.
- **의존 방향**: rcl ⟸ `tos.canonical`·`tos.ordering`·`classify_record_pair` core home(core). rcl은 capsule/evidence를 import하지
  않음(형제, evidence의 상류). evidence는 RCL commit을 scalar(`CAPACITY_COMMIT` causal edge)로만
  참조(설계 #4 §2.5A).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

1. **VERIFICATION-PROFILE-002 bounds 승인 + 누락 키 신설**(§8): Reserved Protective Capacity
   최소치·quarantine escalation horizon 전용 키(Bounds-Approver ≠ Live-Armer).
2. **프로덕션 canonical serialization·digest 알고리즘 선택**(설계 #4 §9.2 item 1/2와 동일 게이트):
   `ev-l1-provisional-0`·sha256은 비프로덕션.
3. **Capacity Domain 경계 + failure-tolerance(f, `2f+1`) + Failure-Domain Allocation Matrix
   승인**(ADR-012 §27 Q2·§28 gate 1/14). **consensus 제품·durable commit·linearizable read
   메커니즘 선택**(ADR-012 §28 gate 2). 이는 **Phase B(EV-L2/L3)** 이며 Phase 1 EV-L1 밖(§0.2).
4. **writer-epoch scope**(ADR-002-002 §37 Q2: account/portfolio/global 중 무엇이 한 epoch scope
   인가). §6 술어는 scope-무관하게 성립하되 실제 scope는 정책 승인.
5. **broker-specific Final Quantity Proof·capability-idempotency 규칙**(ADR-002-002 §37 Q8/Q9):
   §4.6 INV-007·§5.1 benefit-proof의 *양성 proof token* 내용은 Broker Capability Profile(승인,
   broker-agnostic capability class) 소관.
6. **`integrity.source_signature_or_mac`의 암호학적 검증**(§2.x): 키 자료·custody 부재로 Phase 1은
   필드 존재·구조만 담고 MAC 검증은 L2+ 이연(설계 #4 §3.4 (i) 동형).
7. **Independent-Safety-Reviewer 지정 + §7 EV-L1 evidence 수용 서명**(저자 배제 —
   IMPLEMENTATION-PLAN §3 line 153/157).

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- 2026-07-21: **v1.0 초안 최초 작성.** ADR-002-002 + ADR-002-012 EV-L1 실현 계약. 설계 #1(경계·
  firewall)·#2(capsule)·#4(evidence, canonical substrate + append-only + same-id/diff-bytes 선례)·
  Time(ordering PROMOTE)에 정렬. 주요 결정: (§0.4/§3.1) `tos.canonical` **REUSE + `id=f(digest)`
  미채택**(same-command-id/diff-content 충돌 탐지 보존), `tos.ordering` REUSE(`quorum_commit_index`
  = Log Revision), **신규 PROMOTE 없음**(segment-commitment은 evidence 상류 layering·core-불요로
  이연); (§1) **RC-EV 0건 완결** + RCLP-EV **core(001/005/006 L1 슬라이스)/predicate-only(003/004/
  008/010/012)/not-Phase-1(002/007/009/011)** 삼분류, "EV-L1-complete 주장 금지"; (§4.1)
  **capacity ≠ authority** 중앙 불변식(GRANT는 비권위 입력, RCL commit만 mutate); (§5.1)
  conservative projection 3규칙(단조·benefit=0-unless-*positively*-proven·missing-dim=restrictive
  빈-집합 canary); (§6) writer-fence를 **주입 epoch 상태 위 fail-closed 순수 술어**(layer-2만 L1)로,
  missing⇒fenced canary + producer-optimism canary; (§8) 누락 Reserved-Protective-minimum/
  quarantine-escalation 키 실측 후 Phase-0 플래그. 이후 독립 비평 리뷰.
- 2026-07-21: **v1.1 — 독립 비평 리뷰 ACCEPT-WITH-MINOR 반영.** 별도 컨텍스트 독립 리뷰어가
  7개 attack surface(A overclaim·B fail-open·C firewall/layering·D id=f(digest)·E 인용 fidelity·
  F Phase-0 키·G ARE-EV 경계)를 primary-source(양 ADR ~50개 인용·register·`.importlinter`·tos
  코드)로 재검증 → **CRITICAL 0 / MAJOR 0**(시리즈 최초 first-pass 무-REJECT). MINOR 3 전부 정정:
  (1) §3.2a `quorum_commit_index` 인용 line 68 → **67**(`_ordering.py` 실측; `egress_journal_sequence`가 68);
  (2) **open Q3(DRY 비대칭) 해소** — `classify_record_pair`와 segment-commitment을 **통일 PROMOTE
  규칙**으로 봉합(§0.4b): 둘 다 evidence 상류 layering·DRY상 evidence import·재저작 금지, 차이는
  *필요 시점*뿐 ⇒ classify는 Phase-1 core 필요라 **지금 core로 PROMOTE**(재저작 폐기), segment-
  commitment은 불요라 이연(§3.1c·§9.1·§10.2 [운영자 판단 지점] 반영);
  (3) §0.3 **pyyaml 명확화** — rcl 순수 모델은 YAML을 로드하지 않음(bound 주입, YAML 파싱=하네스
  소관), §7.1 import-closure 부재 assert에 `yaml` 추가. 리뷰어 저-리스크 open 항목(구현 시 확인):
  `eip_binding_ok` null-fail-closed cite·`_REQUIRED_COVERED` numeric-bound 제외로 ISSUED 도달성.

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

- [ ] §0.2 NO 목록(consensus/quorum/replication·persistence I/O·egress·authority·RC-EV 0건·
      bounds 미승인)과 §0.3 firewall 준수(numpy/pandas·shared.config·**tos.capsule·tos.evidence**
      배제)에 동의.
- [ ] §0.4/§3.1 **`tos.canonical` REUSE + `id=f(digest)` 미채택**(same-command-id/diff-content
      충돌 탐지 보존) + §3.2 `tos.ordering` REUSE(`quorum_commit_index`=Log Revision) + **통일
      PROMOTE 규칙**: `classify_record_pair`는 Phase-1 core 필요 ⇒ **지금 core로 PROMOTE**(재저작
      아님, evidence shim 무회귀), segment-commitment은 core 불요 ⇒ 이연(둘 다 evidence import
      금지 — RCL은 evidence 상류)에 동의. **[운영자 판단 지점: classify 지금-PROMOTE vs 재저작]**
- [ ] §1 조항별 EV-L1 도달성: **RC-EV 0건 완결**(register 최소 전부 EV-L2+) + RCLP-EV **core
      (001/005/006 L1 슬라이스만)/predicate-only(003/004/008/010/012)/not-Phase-1(002/007/009/
      011)** 삼분류 + "EV-L1-complete 주장 금지"에 동의. ARE-EV(ADR-002-021)는 out-of-scope 인접
      ADR임에 동의.
- [ ] §2 데이터 모델(ledger 시민 전부 **DigestBoundArtifact + 독립 identity**, `IdDerivedArtifact`
      0건; capacity-state 9종; Transmission Capability = non-mutating token)에 동의.
- [ ] §4.1 **capacity ≠ authority** 중앙 불변식(4층: authority_effect=false 구성 불변식 / RCL
      commit만 mutate 구성적-부재 / grant-binds-exact 거부 술어 / documentation≠authority)에 동의.
- [ ] §4·§5 순수 불변식(append-only·단조 epoch/generation·aggregate envelope INV-001·exclusive
      headroom·UNKNOWN 소비·no-expiry·final-quantity-before-release·trapped non-reducible·
      reconciliation-cannot-optimistically-free·protective non-borrowable)과 그 core/predicate
      경계에 동의.
- [ ] §5.1 conservative projection 3규칙 — 특히 **benefit = 0 unless *positively* proven**
      (proof token 요구, "no-benefit flag 부재"로 감소 불가)와 **missing-dimension = restrictive**
      (빈 차원 세트 ⇒ within_limits==False, vacuous True 금지) canary에 동의.
- [ ] §5.2 결정적 reducer no-double-spend(RCLP-EV-001 L1 슬라이스; **producer-optimism canary** —
      producer-local counter가 committed headroom을 만들지 않음)와 "단일 order는 quorum이 산출 =
      /3" 경계에 동의.
- [ ] §6 writer-fence 순수 술어(layer-2만 EV-L1; **missing 좌표 ⇒ FENCED fail-closed canary**;
      단조 floor; stale/minority/removed/restored/conflicting) + §6.4 capacity→capability binding
      (RCLP-EV-006 L1, send는 이연) + §6.5 partition deny-table/non-revival(quorum-unknown ⇒ 전부
      DENIED)에 동의.
- [ ] §7 하네스 타깃 core/predicate 구분과 "EV-L1-complete 주장 금지" 규율, §7.1 import-closure
      확장(**tos.capsule·tos.evidence 부재** 포함), §7.2 run manifest 7항목에 동의.
- [ ] §8 bounds 주입 + 누락 **Reserved-Protective-minimum·quarantine-escalation** 키 Phase-0
      플래그(+ Capacity Domain/f-2f+1은 Phase B)에 동의.
- [ ] §9.2 Phase-0 이관 7항목(bounds·프로덕션 canon·Capacity Domain/consensus 제품·writer-epoch
      scope·broker FQP proof·MAC 검증·독립 리뷰어)을 별도 게이트로 유지함에 동의.

비준 시 효력: IMPLEMENTATION-PLAN-002 §4 Phase 1의 ADR-002-002 + ADR-002-012 부분을
`tos/src/tos/rcl/`에 순수·비전송 모델 + property test로 작성 착수 승인(`tos.canonical`·
`tos.ordering` REUSE, `classify_record_pair` core PROMOTE 1건·segment-commitment 이연). §9.2 Phase-0 7항목과 bounds 승인·독립 리뷰어 지정,
Phase B(consensus/quorum) 전체는 별도 게이트로 남는다.
