# 설계 문서 #8 — Intent·Transmission Attempt·Broker Order·Knowledge State 계약 (2026-07-25, v1.1)

> **문서 번호 규약**: #1 경계·import-firewall, #2 Decision Context Capsule, #4 Evidence
> Store, #5 Risk Capacity Ledger(RCL), #6 Safety Authority, #7 Live Authorization이
> 이미 존재한다(#3은 folded). Trustworthy Time·DSL은 병렬 트랙(A/C)이었고 트랙 A는
> 완료됐다. **#8 = 본 Orthogonal Trading State 문서**이며 ADR-002-005를 실현한다.
> 다섯 orthogonal 차원(Intent·Transmission Attempt·Broker Order·Knowledge/Evidence·
> Capacity)의 **순수·비전송 데이터 모델 + property test**를 그린필드
> `tos/src/tos/orthostate/`에 저작한다.
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**
> 이며 스펙 텍스트(RFC/ADR/템플릿/프로파일)를 **변경하지 않는다.** broker-agnostic 원칙
> (project memory `tos-spec-broker-agnostic`): KIS 등 특정 브로커 사실은 프로젝트 측 예시로만
> 등장하며 규범 주장이 아니다. 다섯 차원·상태·coupling·conservative-direction·ownership·
> restart 술어는 전부 broker-agnostic이며, 브로커 제약은 capability class(Broker Capability
> Profile, ADR-002-004)로만 표현한다. 본 문서는 IMPLEMENTATION-PLAN-002 §4 Phase 1(EV-L1)의
> **ADR-002-005 부분**을 실현한다.
>
> **선행 문서(의존)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   본 계약의 모든 모델은 §2.4 레이아웃(전용 top-level 패키지)에 놓이고 §3.2 허용목록 안에서만
>   의존한다(§0.3). line 164 "naming은 load-bearing이 아니다 — 내부 세분화는 후속 설계 문서가
>   정의한다"에 따라 본 문서가 그 패키지 내부를 정의한다.
> - [설계 #4 — Evidence Store 계약 (v1.1, 비준·구현됨)](2026-07-20-tos-evidence-store-design.md)
>   + 코드 `tos/src/tos/canonical/`. **canonicalization/digest-binding substrate(`tos.canonical`)·
>   `DigestBoundArtifact`·`IndependentIdArtifact`(이미 core)·`classify_record_pair`(이미 core)·
>   `ArtifactStatus`를 REUSE**한다(재정의 금지). evidence의 `id=f(digest)` **미채택** 결정을
>   본 문서가 **동형으로 상속**한다(§2.1/§3.1). **본 문서 PROMOTE = 0건**(필요 core 원소가 이미
>   전부 core).
> - [설계 #5 — Risk Capacity Ledger 계약 (v1.1, 비준)](2026-07-21-tos-risk-capacity-ledger-design.md)
>   + 코드 `tos/src/tos/rcl/`. **Capacity는 다섯 차원 중 하나이며 rcl이 소유한다** —
>   `CapacityState`(9종, `vocabulary.py:23–31`)·`transition_allowed`(capacity 보수성 lattice,
>   `predicates.py:438–471`)·`_CONSERVATISM_RANK`(동 425–435). 본 문서의 **중심 아키텍처 결정**이
>   이 경계다(§0.4b/§3.4): orthostate는 `tos.rcl`을 **import해 CapacityState를 REUSE**하되
>   capacity의 lattice는 **재저작하지 않는다**(설계 결정 #3). `tos.orthostate → tos.rcl`은 본
>   시리즈의 **세 번째 sibling→sibling edge**이며 운영자 판단 지점이다.
> - [설계 #6 — Safety Authority 계약 (v1.2, 비준·구현됨)](2026-07-23-tos-safety-authority-design.md)
>   + [설계 #7 — Live Authorization 계약 (v1.2, 비준·구현됨)](2026-07-24-tos-live-authorization-design.md).
>   **좌표 비붕괴(coordinate non-collapse)**(#6 §4.7)·**lifecycle-state-out-of-digest**(#7 §2.2)·
>   **all-false effect 로컬 재표현**(#7 §0.4f) 패턴을 REUSE(로컬 재표현). `tos.authority`·
>   `tos.liveauth`는 **import하지 않는다**(형제; §12 transition 소유자는 로컬 role enum + 주입
>   actor 좌표로만 담는다 — §3.5).
> - [설계 — Trustworthy Time 모델 계약 (v1.1, 비준)](2026-07-21-tos-trustworthy-time-design.md)
>   + 코드 `tos/src/tos/time/`. Knowledge 차원의 `STALE`(§8 line 141 freshness 상실)은 시간
>   모델에 의존하나, **numeric freshness bound(STALE threshold)는 Verification Profile 소관**
>   (ADR-002-005 §18 line 249)이므로 Phase 1은 freshness를 **주입 opaque flag**(bool\|None,
>   fail-closed)로만 담고 **`tos.time`을 import하지 않는다**(closure 최소화 — rcl이 time을
>   import하지 않은 선례 동형). 상세 §3.5.
>
> **규범 원천**: `ADR-002-005` — Intent, Transmission Attempt, Broker Order, and Knowledge State
> Model (Status: **Proposed**, 264 line). **Amends** RFC-002 §12 Orthogonal Trading State Model
> (dimension 모델을 normative·complete하게 만듦 — ADR line 8). **Depends On** RFC-000
> constitutional safe state; RFC-001 SAFE-020/021/022/024/025/030; ADR-002-002(Capacity 차원)·
> ADR-002-003(authority epochs)·ADR-002-004(broker evidence)·ADR-002-001 v0.2(protective actions)
> (ADR line 9). 매핑 대상 EV: `verification/EVIDENCE-REGISTER-002.csv`의 `STATE-EV-001..005`
> (line 91–95). **AC**: `AC-005-1..5`(§17 line 237–241). **Coupling 불변식**: `CPL-1..7`(§10 line
> 156–162). ADR-002-005는 **자체 INV 시리즈를 정의하지 않는다**(실측: CPL-*·AC-005-* 뿐 — §0.4g).
>
> **비준 기록**: **2026-07-25 운영자 비준(v1.1) — 효력 발생.** §10.2 판단 지점 3건 승인:
> **`tos.orthostate → tos.rcl` import**(세 번째 sibling edge) · **rcl additive comparator**
> (`capacity_at_least_as_conservative` 공개 노출 — ratified rcl 접촉, 순수 additive) ·
> **§5.0 static-vs-transition project-side 판독**(권위적 해소는 §9.2 item 10 ADR-owner 이관;
> 안전 거동 flag·hold·never-normalize는 어느 읽기에서도 불변). 효력: `tos/src/tos/orthostate/`
> Phase 1(EV-L1) 순수·비전송 모델 + property test 착수(선행 소단계 = rcl comparator 노출).
> **STATE-EV 0건 완결(core 001/003도 L1 슬라이스만)** — acceptance 주장 없음; §9.2 Phase-0
> 10항목은 별도 게이트 유지.
>
> **리뷰 이력**: **v1.1 — 독립 비평 리뷰 REJECT 반영(CRITICAL 1 / MAJOR 1 / MINOR 3 / gap 1).**
> 리뷰는 transcription apparatus(DENIED column 측정·enum·guard·CPL 방향·rank·`WEAK_CAUSES`
> divergence·EV 레벨)를 **byte 수준 전량 clean 검증**했고, safety-core의 **cross-section 모순**을
> 지적했다(§10.1): [C1] §7 STATE-EV-001 fixture 행이 5개 §14 composite 전부 `no_coupling_violation
> ==True`라 단언 → 14_2/14_4가 자신의 CPL-5를 발화하므로 §5.3 canary와 상호 모순(representability를
> coupling-cleanliness와 혼동; naive 구현이 CPL-5 canary를 drop하면 SAFE-030 fail-open). [M1]
> §5.3이 satisfiable overlap만 다룸 → exact-vs-exact contradictory overlap 미분석. 전건 반영: §5.0
> 신설(representability≠coupling), 14_2/14_4=coupling-negative 재분류, §5.3 contradictory-overlap
> 확장, §7 test class 추가, m1/m2/m3/Gap 정정(§10.1). 직전 시리즈 — #6 v1.0 **REJECTED**(fail-open
> seam), #7 v1.0 **REVISE**(SAFE-053 under-realization); 두 건 모두 비준 후 transcription 에라타를
> 요했다. 본 문서가 선제 봉합한 defect class: (a) **§11 weak-basis를 rcl의 더 좁은 `WEAK_CAUSES`로
> 대체하지 않고** ADR §11 line 172 verbatim(로컬)으로 저작(under-realization 방지 — §0.4c/§6.1); (b)
> Intent 다이어그램 `DENIED` 분기점·`ACTIVE→WITHDRAWN` guard를 **column alignment + 의미 대조로 명시
> 확정·인용**(§2.2, 에라타 defect class). 수용 서명 게이트는 IMPLEMENTATION-PLAN-002 §3 하드 배제
> (Independent-Safety-Reviewer는 본 문서의 저자/통합자여서는 안 됨)를 따른다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-005 조항별 **Phase 1(EV-L1) 도달성 경계**(§1). `STATE-EV-001..005`의 **core(L1
   슬라이스만) / predicate-only / not-Phase-1** 삼분류. **핵심 사실: STATE-EV-001·003은 register
   최소 레벨에 EV-L1 슬라이스를 가진다**(001=`EV-L1/2`, 003=`EV-L1/3`) — 이는 Time/#6/#7의
   "EV 0건 완결"과 다른 **RCL-형 shape(코어 tier 존재)**다. 단 **어떤 STATE-EV도 authoring으로
   닫지 않는다**(§1 규율; VER-002-001 §5 "written test is not evidence").
2. 다섯 orthogonal 차원의 **데이터 모델 계약**(§2): 네 로컬 차원 enum(`IntentState`·
   `TransmissionAttemptState`·`BrokerOrderState`·`KnowledgeState`) + rcl REUSE `CapacityState`;
   frozen product `CompositeState`(STATE-EV-001 L1 슬라이스); append-only `DimensionTransitionRecord`.
3. **no-mixed-enum 구조 불변식**(§4.1, 중앙): 다섯 차원은 **각기 별개 StrEnum 좌표**이고 composite는
   **frozen product**다 — dimension-collapse(하나의 order-status enum으로 붕괴)가 **구조적으로 표현
   불가**하다. RFC-002 §12(line 1212 "SHALL NOT ... single order-status enumeration")·ADR §1(line 15)
   의 중앙 결정을 타입 수준으로 실현. `RECONCILED`는 Knowledge 좌표에만·`UNKNOWN`은 Broker/Capacity
   좌표에만 존재(ADR line 27).
4. **rcl `CapacityState` REUSE 결정(중심 아키텍처)**(§0.4b/§3.4): coupling 술어(CPL-1..7)가 capacity
   상태 **값**을 타입-안전하게 참조하므로 `tos.rcl`을 import하며(세 번째 sibling edge), capacity의
   보수성 lattice(`transition_allowed`/`_CONSERVATISM_RANK`)는 **재저작하지 않는다**(설계 결정 #3).
   대안(opaque scalar·로컬 재표현) 기각 근거 §0.4b.
5. **cross-dimension coupling 술어**(§5, STATE-EV-003 L1 슬라이스): `CPL-1..7`을 composite 위 순수
   위법-판정 술어로. **CPL-1 ∧ CPL-5 중첩 시 더 보수적 의무(QUARANTINED_UNKNOWN)가 conjunction으로
   지배**(§5.3). ADR가 결정하지 않은 조합은 **CPL 위반 없음 = 위반-미탐지**로만 주장(충분조건 아님 —
   over-claim 금지, §5.4).
6. **conservative-direction 술어**(§6.1, STATE-EV-002 substrate): 네 로컬 차원의 보수성 방향 규칙 —
   **§11 weak-basis 집합을 로컬 verbatim으로**(rcl `WEAK_CAUSES`보다 넓음: `local cache`·
   `recovery/reconnect` 포함); capacity는 `rcl.transition_allowed` REUSE.
7. **transition-ownership 술어**(§6.2, STATE-EV-005 substrate): §12 authority 표를 로컬 role enum +
   주입 actor 좌표 위 `may_transition` 술어로. +Security(actor 인증·rejection evidencing) 이연.
8. **restart-reconstruction 술어**(§6.3, STATE-EV-004 substrate): §13의 보수적 재구성을 순수 projection
   `reconstruct_conservative(pre)->post`로(SEND_STARTED⇒POTENTIALLY_LIVE·non-terminal broker⇒UNKNOWN·
   knowledge≠RECONCILED). 실제 durable reload·crash recovery는 이연.
9. **fail-closed 규율 + named canary**(§4·§5·§6): unknown/None 차원값⇒most-conservative; **누락 차원
   필드⇒invalid(default 없음)**; illegal composite⇒**탐지 후 restrictive(silent normalize 금지)**;
   dimension-swap⇒구조적 거부; 각 가드에 both-ways canary.
10. **property-test 하네스 타깃**(§7) + §14 다섯 composite를 **named fixture**로 + import-closure
    검증(§7.1) + run manifest 7항목(§7.2).
11. **bounds 주입 계약 + 누락 프로파일 키 Phase-0**(§8): 실측 결과 **확정 신규 누락 키 0건 + Phase-0
    candidate 1건**(knowledge/reconciliation-staleness는 `MAX_currentness_vector_age_ms` cross-ref하되
    ADR-002-006-의존 dedicated 키 여부 flag; 기타 STALE freshness는 기존 per-domain age 키 — 중복 계상 회피).

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR-002-005
  §19(line 264) "authorizes design and implementation-planning work only; it does not authorize live
  trading." ADR acceptance는 오직 *실행된* evidence로만 온다(project memory `tos-spec-rfc-authoring-track`).
- **persistence 기술·durability·크래시 후 실제 복원을 구현하지 않는다.** ADR §4(line 61) "does not
  decide the persistence technology"; §13(line 197) durable/reconstructable 요구는 **메커니즘 이연**.
  Phase 1은 composite/transition **데이터 + 불변식**만 저작한다. 따라서 **STATE-EV-001의 /2(durable
  persistence)·STATE-EV-004의 restart 실기(EV-L3)는 이연**(§1).
- **egress / 전송을 구현하지 않는다.** 설계 #1 §4대로 tos는 정의상 non-transmitting이다(자격증명·
  라우트·주문구성 부재 + egress 코드 firewall 차단). CPL-6(§10 line 161 "verifiable at final egress")의
  실제 egress 검증·send boundary는 이연하고 Phase 1은 **binding 전제 술어(주입 epoch-current flag)** 만
  저작한다(§5.2).
- **Capacity 차원 내부를 재정의하지 않는다.** ADR §9(line 148) "Defined by ADR-002-002 §10 ... owned
  solely by the Risk Capacity Ledger. This ADR governs only how the Capacity dimension couples to the
  other four." ⇒ `CapacityState`·`transition_allowed`·`_CONSERVATISM_RANK`는 **rcl REUSE**이고 본
  문서는 **coupling만** 저작한다(§3.4). capacity의 9-상태 lattice를 재저작하면 DRY 위반 + 설계 결정 #3
  위반.
- **authority epoch / reconciliation confidence / broker evidence 규칙을 결정하지 않는다.** ADR §4(line
  61): authority-epoch(ADR-002-003)·reconciliation confidence(ADR-002-006)·broker evidence·Final
  Quantity Proof(ADR-002-004)는 **각 ADR 소관**이고 본 모델에 **conform**할 뿐이다. Knowledge 차원의
  `RECONCILED` 진입 증명·Broker 차원의 evidence-under-profile은 **주입 proof flag**로만 담는다(§6.1).
- **어떤 STATE-EV도 authoring으로 닫지 않는다.** `STATE-EV-001..005`는 전부 `Critical`이고 최소 레벨은
  001/003이 EV-L1 슬라이스를 **포함**하나(002=`EV-L2/3`, 004=`EV-L3`, 005=`EV-L2/3+Security`), authoring
  ≠ evidence(VER-002-001 §5 line 243). core 두 항목조차 L1 슬라이스뿐이며 `/2`·`/3` 꼬리가 남아
  "EV-L1-complete"가 아니다(§1 규율).
- **numeric bounds를 승인하지 않는다.** VERIFICATION-PROFILE-002 bounds 승인·누락 키 신설(§8)·독립
  리뷰어 지정은 Phase-0 인간 게이트(§9.2).

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

orthostate 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml`도
  import하지 않는다** — 다섯 차원은 전부 StrEnum, coupling·ownership은 boolean/집합 논리, conservative
  direction은 정수 rank 비교(capacity는 rcl REUSE)라 수치 백엔드가 불필요하고, 모든 bound는 주입
  파라미터이며 YAML 파싱은 하네스(설계 #3) 소관이다(closure 최소화 — #5 §0.3·#7 §0.3 동형).
- tos 자기 자신: `tos.canonical`(FrozenModel·DigestBoundArtifact·**이미 core인 `IndependentIdArtifact`**·
  **이미 core인 `classify_record_pair`**·`RecordPairKind`·`ArtifactStatus` — §3.1), **`tos.rcl`**
  (`CapacityState`·`transition_allowed` + §9.1 추가 comparator — §3.4의 세 번째 sibling edge),
  `tos.ordering`(append-only transition/observation 순서 — §3.2), `tos.orthostate.*`. **`tos.time`·
  `tos.evidence`·`tos.capsule`·`tos.authority`·`tos.liveauth`·`tos.dsl`을 import하지 않는다**(형제 또는
  하류 투영; scalar/주입 좌표로만 참조 — §3.5).
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이
  `shared.config.secrets`(→ `os.environ`)를 무조건 전이 import한다. orthostate는 애초에 어떤 `shared.*`도
  필요로 하지 않는 순수 커널이다.
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`, `shared.llm`,
  `shared.storage`, `shared.backtest`, `services.*`, `cli.*`(설계 #1 §2.3; `.importlinter` forbidden set).
- **firewall 구조 확인(실측)**: `.importlinter`는 **`forbidden` 계약**(source=`tos`; forbidden=
  {shared.execution/kis/streaming/llm/storage/backtest, shared.config.secrets, services, cli})
  **뿐이며 `layered` 계약이 아니다** — 즉 intra-tos sibling→sibling edge는 구조적으로 금지되지 않고,
  설계 #1 §3.2의 "자기 자신 `tos.*`" 허용 조항이 이를 커버한다. `tos.orthostate → tos.rcl`은
  firewall-clean이며, "세 번째 sibling→sibling edge" 표현은 **설계 규율상의 결합-최소화 주석**(운영자
  판단 지점 §10.2)이지 하드 firewall 규칙이 아니다(#7 §0.3 실측 결론 상속).
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(`import tos.orthostate` closure에 금지·
  `shared.config`·`os.environ`·numpy/pandas/yaml·**`tos.time`·`tos.evidence`·`tos.capsule`·
  `tos.authority`·`tos.liveauth`·`tos.dsl`** 부재 assert; **`tos.canonical`·`tos.rcl`·`tos.ordering`은
  존재 허용**). required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter`
  layer-② 전이 방어)와 함께 green이어야 본 선언이 능동 성립한다.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 위치·명명 = `tos/src/tos/orthostate/`.** RFC-002 §12 / ADR-002-005는 "다섯 orthogonal
state dimension"을 first-class 모델로 세운다. 명명 대안 비교:

- **`tos.state`(기각)**: `tos/src/tos/authority/state.py`·`liveauth/state.py`·`rcl/state.py`가 **이미
  존재**한다(실측) — top-level `tos.state` 패키지는 이 module들과 import 혼동(`from tos.state import X`
  vs `from tos.rcl.state import Y`)을 일으키고 "state"는 orthogonal-dimension 모델을 특정하기엔 지나치게
  generic이다.
- **`tos.dimensions`(기각)**: rcl이 capacity vector의 **"dimension" 어휘**(`DimensionDescriptor`·
  `CapacityComponent`)를 이미 쓴다 — `tos.dimensions`는 그 capacity-vector 차원과 개념 충돌.
- **선택 `tos.orthostate`**: ADR §1 line 15 "five orthogonal state dimensions" 개념을 직접 명명, 두 충돌
  회피, terse. naming은 load-bearing이 아니다(설계 #1 line 164) — 운영자 치환 가능; **load-bearing은
  layering**(orthostate → canonical·rcl·ordering 한 방향; time·evidence·capsule·authority·liveauth·dsl과
  형제/하류). 내부 module(`vocabulary.py`·`records.py`·`state.py`·`predicates.py`·`_base.py`)은 rcl/liveauth
  선례 동형이며, `tos.orthostate.state` **module**은 `tos.state` **package** 충돌과 무관하다(rcl.state
  선례).

**(b) `CapacityState` REUSE — `tos.orthostate → tos.rcl` import(세 번째 sibling edge, 중심 결정).**
Capacity는 다섯 차원 중 하나이나 ADR §9(line 148)가 그 정의를 ADR-002-002/rcl에 위임한다. coupling
술어(CPL-1..7)는 capacity **상태 값**(POTENTIALLY_LIVE·RELEASED·QUARANTINED_UNKNOWN·POSITION_CONSUMED·
RELEASE_PENDING_PROOF·TRAPPED_CONSUMED)과 그 보수성 순서를 타입-안전하게 참조해야 한다. 대안 비교(#7 §0.4b
형식):

- **대안 A — opaque scalar(no import; #7의 rcl 참조 방식)**: capacity를 `str`/불투명 토큰으로 담고
  coupling을 stringly-typed로. **기각(주요)**: #7의 liveauth는 capacity **값을 절대 추론하지 않고**
  reservation_id를 불투명 link로만 담았지만, orthostate의 coupling 계층은 **정의상 capacity 값 대 다른 네
  차원의 제약**이다(CPL-1의 "at least as conservative as POTENTIALLY_LIVE" 등). opaque scalar면 CPL-1/2/4/5/7이
  L1에서 타입-안전 술어로 저작 불가(매직 문자열화)하고 capacity 보수성 순서를 재도출해야 해 STATE-EV-003
  core L1 슬라이스가 약화된다. **liveauth와 precedent가 다른 것은 원칙적**이다(값 추론 여부).
- **대안 B — `CapacityState`를 로컬 재표현 + `authority._REARM_PREREQUISITES` 식 drift 회귀 테스트**: rcl과
  동형인 9-상태 enum을 orthostate에 재선언하고 item-for-item drift 테스트로 동기. **기각**: DRY 비협상 규칙
  위반(CLAUDE.md) — capacity 상태는 ADR-002-002 §10.1의 단일 진리원이고 rcl `vocabulary.py:23–31`이 그
  구현이다. 재표현은 두 진리원·drift 위험이며 ADR §9(line 148 "Defined by ADR-002-002")에 반한다. (drift
  테스트는 #7이 *authority가 구조상 노출 못 하는* 신호에 대해 쓴 우회로였지 *이미 import 가능한 enum*을
  복제하는 근거가 아니다.)
- **대안 C — `CapacityState`를 core로 PROMOTE**(ordering/classify/IndependentIdArtifact 선례): **기각**.
  `CapacityState`는 `transition_allowed`·`_CONSERVATISM_RANK`·`CapacityVector`·capacity-math 전체에
  본질적으로 결부돼 있어 core로 옮기면 rcl을 hollow-out한다(clean shared-atom PROMOTE가 아님 — #7 §0.4b가
  authority 술어 PROMOTE를 기각한 것과 동일 근거).
- **선택 — import-and-REUSE**: `tos.orthostate → tos.rcl`, `CapacityState`·`transition_allowed` REUSE.
  근거: (i) ADR 의존 방향 정합 — ADR-002-005 Depends-On ADR-002-002(line 9 "ADR-002-002 (Capacity
  dimension)"); orthostate가 rcl capacity의 **하류 소비자**(coupling 계층)다. (ii) DRY·설계 결정 #3
  ("capacity lattice 재저작 금지") 동시 충족. (iii) acyclic — rcl은 `tos.canonical`·`tos.ordering`만
  import하고(실측: `rcl/__init__.py:31`, `_base.py:37`, `predicates.py:39`) time/evidence/capsule/orthostate를
  전혀 참조하지 않으므로 `orthostate → rcl → {canonical, ordering}` 단방향, cycle 없음. (iv) 좌표 비붕괴
  유지 — capacity는 별개 차원 좌표로 유지되고 다른 넷과 붕괴하지 않는다(§4.1). **firewall 허용**:
  `.importlinter`는 forbidden 계약뿐(§0.3), intra-tos edge 무제한. 단 **세 번째 sibling→sibling edge**이므로
  운영자 판단 지점(§10.2). Fallback: 운영자가 cross-sibling edge를 더 늘리길 원치 않으면 대안 A(opaque
  scalar)로 후퇴하되 CPL-1/2/4/5/7이 predicate-only로 강등됨(STATE-EV-003 L1 슬라이스 약화 — 비권장).
  **부속 결정(§9.1 후속)**: CPL-1/CPL-4가 요구하는 "capacity 보수성 비교"에 필요한 `_CONSERVATISM_RANK`는
  rcl **private**이다(`predicates.py:425`) — 구현은 rcl에 **thin public comparator**
  `capacity_at_least_as_conservative(a, b) -> bool`(기존 private rank 위 read-only wrapper, 동작 변경·
  PROMOTE 없음)를 **additive로 노출**하고 orthostate가 REUSE한다. orthostate 내 재도출 금지(DRY/drift).
  fragile한 `transition_allowed` 우회(weak-cause로 방향성 추론)는 RELEASED 특례에 의존하므로 기각.

**(c) conservative-direction weak-basis = 로컬 verbatim(§11), rcl `WEAK_CAUSES` 미재사용(under-realization
방지 — 선제 봉합).** **실측 핵심 발견**: rcl `WEAK_CAUSES = {TIMEOUT, ABSENCE, OPERATOR_ASSUMPTION}`
(`vocabulary.py:102–108`, ADR-002-002 §10.2 앵커)는 ADR-002-005 §11(line 172)의 weak-basis
{`timeout`, `absence`, **`local cache`**, `operator assertion`}보다 **좁다** — `local cache`가 빠져 있고,
§11 line 173–175의 collapse 금지(UNKNOWN→NONE/CANCELLED/UNFILLED; cancel/ACK를 capacity terminal로;
recovery/reconnect를 특정 상태 knowledge로)도 없다. ⇒ **네 로컬 차원의 conservative-direction은 rcl
`WEAK_CAUSES`를 재사용하지 않고** ADR §11 verbatim의 **넓은 로컬 basis 집합**을 저작한다. rcl `WEAK_CAUSES`를
로컬 차원에 재사용하면 "local cache" 근거의 conservatism-reduction이 걸러지지 않는 **fail-open**이 된다
(#7 SAFE-053 under-realization defect class 재발 방지). **capacity 차원만** `rcl.transition_allowed`
(rcl의 좁은 WEAK_CAUSES 사용 — ADR-002-002 §10.2에 충실)를 REUSE한다. 두 basis 집합이 다른 것은 **의도**이며
(rcl은 §10.2에, orthostate는 §11에 각각 충실) §6.1이 관계를 명시한다: orthostate 로컬 weak-basis ⊋
rcl `WEAK_CAUSES`.

**(d) `tos.canonical` REUSE + `id=f(digest)` 미채택 + PROMOTE 0건.** composite/transition ledger 시민은
`tos.canonical.IndependentIdArtifact`(id⊥digest; `_base.py:328`)·`DigestBoundArtifact`(digest 검증;
`_base.py:98`)를 REUSE한다. **`id=f(digest)`(`IdDerivedArtifact`) 미채택**: composite/transition은 intent
identity에 link되는 서비스-할당 identity(ADR §5 line 76 "Intent identity is immutable and globally unique
(SAFE-020); ... A terminal Intent identity SHALL NOT be reused")를 가지며, same-id/diff-bytes(위조·재제출)
탐지에 `classify_record_pair`(이미 core, `record_pair.py:52`)를 쓰려면 id⊥digest여야 한다. 설계 #4·#5·#6·#7
§3.1과 완전 동형(capsule의 content-addressed `id=f(digest)`와 정반대). **필요 core 원소(IndependentIdArtifact·
classify_record_pair)가 #5/#6 PROMOTE로 이미 core**이므로 **PROMOTE = 0건**(#7과 동일 형).

**(e) `tos.time`·`tos.evidence`·`tos.capsule`·`tos.authority`·`tos.liveauth`·`tos.dsl` 미import(형제/하류).**
- **`tos.evidence` 미import(layering)**: Knowledge/Evidence 차원(UNOBSERVED..RECONCILED..STALE)은
  **decision-side representation**(Reconciliation Service 소유, ADR §8 line 128; ADR-002-006이 confidence를
  정의)이지 evidence **ledger**(append-only 증거 레코드·gap 탐지·segment commitment)가 아니다. evidence
  store는 **하류 투영**(설계 #5 §3.1이 인용한 ADR-002-012 §19 line 478 "evidence stores are downstream
  projections")이므로 decision-side 상류 모델이 하류 투영을 import하면 layering 역전(#5가 rcl→evidence를
  금지한 것과 동일). ⇒ `KnowledgeState`는 **로컬 저작**; evidence 레코드는 scalar(evidence_id/digest) 참조만.
  **실측 확인**: `tos.evidence`에 `KnowledgeState`/reconciliation-confidence enum **부재**(reconcil 히트는
  ledger gap 필드뿐).
- **`tos.capsule` 미import(다른 축)**: capsule `FieldState`(`INVALID>CONFLICTED>STALE>UNKNOWN>VALID`,
  `field_state.py:7`, ADR-002-018)는 **per-field context freshness** 축이지 trading-action의 Knowledge 축이
  아니다. 토큰 `CONFLICTED`/`STALE`/`UNKNOWN`을 공유하나 **다른 좌표계**다 — 재사용하면 축 붕괴. ⇒
  `KnowledgeState`는 로컬(좌표 비붕괴 canary: `KnowledgeState.CONFLICTED` ≠ `FieldState.CONFLICTED`).
- **`tos.authority`·`tos.liveauth` 미import**: §12 transition 소유자(Intent Registry·Execution Coordinator·
  Broker Adapter/Egress·Reconciliation Service·Risk Capacity Ledger)는 **role 라벨**이지 authority 아티팩트가
  아니다 — 로컬 `TransitionAuthority` enum + 주입 actor 좌표로 담는다(§6.2). CPL-6의 authority-epoch-currentness는
  **주입 flag**(bool\|None, fail-closed). ⇒ orthostate는 authority/liveauth를 import하지 않고 rcl 단일
  sibling edge만 유지.
- **`tos.time` 미import**: (b)의 freshness 이연(§3.5).
- all-false effect 블록이 필요한 경우(§4.6 representation≠effect)는 **orthostate-local 재표현**(패키지별
  로컬 규칙, #7 §0.4f 상속) — PROMOTE 아님.

**(f) 불변식 명명 규약 — INV 시리즈 창작 금지.** **실측(grep)**: ADR-002-005는 **INV 시리즈를 정의하지
않는다** — `CPL-1..7`(§10)·`AC-005-1..5`(§17)·`STATE-EV-001..005`만 가진다(단 §6 line 98이 ADR-002-002의
`INV-005`를 cross-cite). ⇒ 본 계약은 모델 불변식·술어를 **`CPL-1..7` / `AC-005-1..5` / §-clause 번호 /
`STATE-EV-###`**에 앵커하고, RFC-001 앵커는 ADR Depends-On line 9가 할당한 **SAFE-020/021/022/024/025/030**을
인용한다. **새 INV 시리즈를 창작하지 않는다**(#6이 SA-INV에 앵커한 것과 대비 — 여기엔 앵커할 INV가 없다).

---

## 1. 범위 매핑 — ADR-002-005 조항별 EV-L1 도달성 (STATE-EV core tier)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine exploration, model
checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integration/Adversarial**, **+Security = 전용 fault injection**. Phase 1은 EV-L1만이다.

> **결정적 사실 1 — core tier 존재(RCL-형 shape, Time/#6/#7과 다름)**: `STATE-EV-001..005`(전부
> `Critical`, register line 91–95 실측) 중 **STATE-EV-001(`EV-L1/2`)·STATE-EV-003(`EV-L1/3`)은 register
> 최소 레벨에 EV-L1 슬라이스를 포함**한다. 나머지는 002=`EV-L2/3`, 004=`EV-L3`, 005=`EV-L2/3+Security`.
> ⇒ Time "TIME-EV 0건"·#6 "SA-EV 0건"·#7 "REARM-EV 0건"과 달리 **코어 tier가 있다**(설계 #5 RCLP-EV와
> 동형 shape). 분류는 **core(L1 슬라이스만) / predicate-only / not-Phase-1** 3분류.
>
> **결정적 사실 2 — authoring ≠ acceptance(닫는 STATE-EV = 0건)**: core tier가 있어도 **Phase 1 authoring이
> STATE-EV를 닫지 않는다.** (a) core 두 항목조차 **L1 슬라이스뿐**이고 `/2`(durable persistence)·`/3`(런타임
> coupling 강제) 꼬리가 남으며, (b) VER-002-001 §5(ADR line 243 "Registration is not execution. A written
> test is not evidence") — 실행·아티팩트·독립 리뷰가 필요하다. ⇒ **"EV-L1-complete 주장 금지"**(설계 #2 §7·
> #4 §7·Time §1·#5 §1·#6 §1·#7 §1 규율 상속). Owner/Reviewer는 register상 TBD.

| STATE-EV | 제목 | register 최소 (line) | Phase-1 분류 | L1 슬라이스 / substrate (닫지 않음) | ADR 근거 |
|---|---|---|---|---|---|
| **-001** | Orthogonal Composite Persistence | `EV-L1/2` (91) | **core (L1 슬라이스만)** | 다섯 차원 = 별개 StrEnum, composite = frozen product(§4.1); §14 다섯 composite **전부 표현 가능**(§7 fixture); canonical digest **결정성**. **/2 = 실제 durable 저장·크래시 후 복원(persistence 기술 — ADR §4 line 61 미결정).** | AC-005-1 (237), §1 (15–27), §14 (204–212) |
| **-002** | Conservative Direction | `EV-L2/3` (92) | **predicate-only** | per-dimension 보수성 방향 술어(§6.1): weak §11 basis는 conservatism 감소 불가·증가는 항상 허용; capacity=`rcl.transition_allowed` REUSE. **injected timeout/absence/restart가 실제로 less-conservative 전이를 못 만든다는 fault-injection 강제는 EV-L2/3.** | AC-005-2 (238), §11 (168–177) |
| **-003** | Cross-Dimension Coupling | `EV-L1/3` (93) | **core (L1 슬라이스만)** | `CPL-1..7` 위법-판정 pure predicate over composite(§5). **/3 = partial-fill·cancel-crossing-fill·replace-overlap·UNKNOWN 이벤트 시퀀스에서의 런타임 coupling 강제(ADR §17 AC-005-3 fault 조건).** | AC-005-3 (239), §10 (152–164) |
| **-004** | Conservative Restart Reconstruction | `EV-L3` (94) | **predicate-only** | `reconstruct_conservative(pre)->post` 순수 projection(§6.3): SEND_STARTED⇒POTENTIALLY_LIVE·non-terminal broker⇒UNKNOWN·knowledge≠RECONCILED. **실제 durable reload·crash recovery·Recovery Barrier는 EV-L3(no L2 — 가장 이연).** | AC-005-4 (240), §13 (195–200) |
| **-005** | Dimension Transition Ownership | `EV-L2/3+Security` (95) | **predicate-only** | `may_transition(actor, dimension[, region])` over §12 표(§6.2). **actor 인증·비-owner 거부의 rejection+evidencing은 EV-L2/3+Security.** | AC-005-5 (241), §12 (181–191) |

**Phase-1 분류 요약**: **core(L1 슬라이스)** = {`STATE-EV-001`, `STATE-EV-003`}. **predicate-only(EV 주장
금지)** = {`STATE-EV-002`, `STATE-EV-004`, `STATE-EV-005`}. **not-Phase-1** = **{ } (없음)** — 다섯 항목
모두 L1-decidable substrate가 저작 가능하되, 002/004/005는 최소 레벨이 EV-L2+라 predicate-substrate로만
저작하고 EV를 닫지 않으며, 001/003은 L1 슬라이스만 저작하고 `/2`·`/3`는 이연한다. **닫는 STATE-EV = 0건.**

> **규율 태그(모든 주장에 부착)**: "**EV-L1 슬라이스/predicate substrate only; STATE-EV-001/003은 L1
> 부분만(‥/2·/3 잔존), STATE-EV-002/004/005는 predicate substrate만, 전부 NOT_IMPLEMENTED — EV-L2/L3
> (005 +Security) fault injection·durable persistence·런타임 coupling 강제·실기 restart 대기.**"
>
> **ADR-002-005 조항 → 모델 산출물 매핑**: §1/§14 dimension 모델·composite → §2·§4.1; §5 Intent → §2.2
> `IntentState`; §6 Attempt → §2.2 `TransmissionAttemptState`; §7 Broker Order → §2.2 `BrokerOrderState`;
> §8 Knowledge → §2.2 `KnowledgeState`; §9 Capacity → §3.4 rcl REUSE; §10 CPL-1..7 → §5; §11 conservative
> direction → §6.1; §12 ownership → §6.2; §13 restart → §6.3; §17 AC-005-* → §7 하네스.

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True, extra="forbid")`,
`tos.canonical.FrozenModel` REUSE — `_base.py:73`)로 저작한다. frozen은 append-only(§13 durable/
reconstructable; §5 line 76 intent identity immutable·non-reuse)의 레코드 수준 실현이며, **모델에는
update/delete 연산이 존재하지 않는다**(설계 #4 §2.0 규율 상속). enum 값·필드명은 ADR §5–§9의 용어를 그대로
쓴다(스펙 용어 = 코드 용어, 설계 #1 §2.4).

### 2.0 소유권 골격 — orthostate는 canonical의 하류, rcl(capacity)의 하류-형제, evidence/capsule/authority의 상류-형제

orthostate가 **소유·저작하는 것은 네 로컬 차원 enum + composite/transition 레코드 + coupling/direction/
ownership/restart 술어**다. Capacity 차원은 **rcl REUSE**(§3.4). Knowledge 차원이 참조하는 실제 evidence·
reconciliation confidence(ADR-002-006)·Broker evidence(ADR-002-004)·authority epoch(ADR-002-003)·freshness
bound(Verification Profile)는 **scalar/주입 좌표**로만 담고 클래스를 import하지 않는다(§3.5).

### 2.1 digest-bound / plain-frozen / reference 분류 (총괄)

| 아티팩트 | 종류 | id 필드(독립) | digest 필드 | covered = ? |
|---|---|---|---|---|
| `CompositeState` (§1 line 15–27; §14 line 204–212) | **IndependentIdArtifact + 독립 id** | `composite_state_id`(+`observation_revision`) | `canonical_digest` | intent_identity + 다섯 차원 좌표 + version 참조(§2.3) |
| `DimensionTransitionRecord` (§12 line 181–191; §13) | **IndependentIdArtifact + 독립 id** | `transition_id` | `canonical_digest` | intent_identity·dimension·from/to·owning authority·basis·evidence 참조·revision(§2.4) |
| 네 로컬 차원 enum (§5/§6/§7/§8) | **StrEnum(값 타입)** | — | — | (composite/transition의 covered 원소) |
| `CapacityState` (§9 line 148) | **rcl REUSE StrEnum** | — | — | (composite의 다섯째 좌표 — `tos.rcl`) |
| Coupling 주입 side-condition (§5.2/§5.3) | **plain FrozenModel** | — | — | proof-required·epoch-current·trapped flag(bool\|None fail-closed) |
| Ownership query (§6.2) | **plain FrozenModel** | — | — | actor(role)·dimension·region 좌표 |
| Restart 입력 (§6.3) | **plain FrozenModel** | — | — | pre `CompositeState` + provably-terminal/proof flag |
| evidence / capsule / authority-epoch 참조 블록 | **plain FrozenModel(참조)** | id+generation+digest scalar | — | tos 미소유(ADR-002-004/006/003/018) |

> **`IdDerivedArtifact` 채택 아티팩트 = 0건. PROMOTE = 0건.** composite/transition은 intent-linked
> **서비스-할당 identity**를 가진다(§5 line 76 SAFE-020 immutable·non-reuse) — same-id/diff-bytes 위조·
> 재제출 탐지(`classify_record_pair`)에 id⊥digest 필수. ⇒ 전부 `IndependentIdArtifact`(이미 core) 상속,
> `IdDerivedArtifact`(capsule 전용) 미채택. `tos.orthostate._base`는 rcl/liveauth 동형의 thin re-export
> shim(신규 PROMOTE·형제 edge 없음).

### 2.2 네 로컬 차원 enum + composite (verbatim 전사 — 에라타 defect class 주의)

> **전사 규율**: 아래 enum 값·전이·guard는 ADR §5–§8에서 **verbatim**이며, 다이어그램 ASCII 정렬이
> 모호한 지점은 **column alignment + 의미 대조로 확정하고 인용**한다(#6/#7 비준후 에라타 defect class —
> 부등호 방향·필드명 — 선제 방지).

**(1) `IntentState`(StrEnum) — ADR §5 (line 65–77), owned by Intent Registry (line 66).**
7종 verbatim: `PROPOSED`, `APPROVED`, `AUTHORIZED_FOR_CAPACITY`, `ACTIVE`, `CLOSED`, `DENIED`, `WITHDRAWN`.
전이(line 69–73):

```text
PROPOSED -> APPROVED -> AUTHORIZED_FOR_CAPACITY -> ACTIVE -> CLOSED
                     \-> DENIED
ACTIVE -> WITHDRAWN            (only if no attempt may be live; see §11)
```

- **`DENIED` 분기점 확정(에라타 주의)**: line 71 `\-> DENIED`의 `\`는 **column 22**에 있다(실측: line 71은
  21 leading space + `\->`). line 70에서 column 22는 **`APPROVED` 직후 화살표 `->`의 첫 글자**다
  (`APPROVED`가 col 13–20, space 21, `-` 22, `>` 23). ⇒ **`DENIED`는 `APPROVED`에서 분기**한다(`PROPOSED`가
  아니다). 의미 대조가 이를 확증: line 75 "`AUTHORIZED_FOR_CAPACITY` means Approval + Aggregate-Risk policy
  granted" — 즉 `APPROVED`(독립 승인 소비 완료) 후 aggregate-risk 정책 단계가 grant면 `AUTHORIZED_FOR_CAPACITY`,
  deny면 `DENIED`. 따라서 `APPROVED -> {AUTHORIZED_FOR_CAPACITY | DENIED}`. (모델: `IntentState` 전이 술어가
  이 분기를 허용 집합으로 인코딩; property로 `PROPOSED->DENIED` 직접 전이는 **비허용**으로 고정 — 근거 line
  71 column alignment + line 75.)
- **`ACTIVE -> WITHDRAWN` guard verbatim(line 72)**: "`(only if no attempt may be live; see §11)`". 이를
  §5 line 77과 결합: "`CLOSED`/`WITHDRAWN` are permitted only when the Capacity and Knowledge dimensions
  prove no potentially-live effect remains (§11)." ⇒ `WITHDRAWN`(및 `CLOSED`) 진입 술어는 **capacity·
  knowledge가 no-potentially-live-effect를 증명할 때만** 참(주입 proof flag; 미증명/None ⇒ fail-closed
  거부). 이는 cross-dimension guard이므로 §5.3 coupling과 정합한다.
- 기타 근거: `AUTHORIZED_FOR_CAPACITY`는 capacity commit·transmission을 의미하지 **않는다**(line 75);
  intent identity는 immutable·globally-unique(SAFE-020, line 76), terminal 재사용 금지.

**(2) `TransmissionAttemptState`(StrEnum) — ADR §6 (line 81–99).** owned by Execution Coordinator(prep) +
Broker Adapter/Egress(send boundary)(line 82). 8종 verbatim: `NONE`, `PREPARED`, `CAPABILITY_ISSUED`,
`SEND_STARTED`, `SENT_UNCONFIRMED`, `ACK_OBSERVED`, `SEND_FAILED_PROVEN`, `SUPERSEDED`. 전이(line 85–92):
`NONE -> PREPARED -> CAPABILITY_ISSUED -> SEND_STARTED -> SENT_UNCONFIRMED -> {ACK_OBSERVED |
SEND_FAILED_PROVEN | SUPERSEDED}`. 보수 규칙: `SEND_STARTED`는 external call 전 durable(write-ahead, line
96); `SEND_FAILED_PROVEN`은 **positive evidence** 필요 — timeout/missing-ACK/reset/restart는 도달 불가(line
97); `SEND_STARTED` 도달 후 TTL/restart/authority-expiry가 capacity-releasing 상태로 retire 불가(line 98).
> **canary(NONE ≠ None)**: `TransmissionAttemptState.NONE`("no attempt yet")은 **정당한 값**이며, composite
> 필드가 **누락/`None`**인 것(§4.4 completeness 위반)과 구별된다.

**(3) `BrokerOrderState`(StrEnum) — ADR §7 (line 102–122).** established **only from broker/venue evidence
under Broker Capability Profile(ADR-002-004)**; no internal component sets from assumption(line 104). 9종
verbatim(line 106–115): `NONE_OBSERVED`, `WORKING`, `PARTIALLY_FILLED`, `FILLED`, `CANCEL_PENDING`,
`CANCELLED`, `REJECTED`, `EXPIRED`, `UNKNOWN`. (ADR는 이 차원을 전이 그래프가 아닌 **상태 집합**으로 준다 —
전이 방향은 §6.1 conservative-direction으로 다룸.) 보수 규칙: 한 query/page/session/stream의 부재는
`NONE_OBSERVED`/`CANCELLED`의 proof가 **아니다**(line 120, confidence만 낮춤 = Knowledge 차원); 이후 valid
fill은 관측된 `CANCELLED`/`REJECTED` 후에도 accept·미폐기(line 121); `UNKNOWN`은 Capacity를
`QUARANTINED_UNKNOWN`으로 **force**(line 122 — CPL-5 근거).

**(4) `KnowledgeState`(StrEnum) — ADR §8 (line 126–142).** owned by Reconciliation Service(line 128;
confidence 표현은 ADR-002-006). 7종 verbatim(line 130–136): `UNOBSERVED`, `CONSISTENT`, `CONFLICTED`,
`RECONCILING`, `RECONCILED`, `QUARANTINED`, `STALE`. 전이: `UNOBSERVED -> {CONSISTENT | CONFLICTED}`;
`CONSISTENT -> CONFLICTED`; `CONFLICTED -> RECONCILING -> {RECONCILED | QUARANTINED}`; `STALE`(prior
knowledge가 freshness bound 초과). 보수 규칙: `RECONCILED`는 **positive corroborating evidence(ADR-002-006)
+ broker order 관여 시 Final Quantity Proof(ADR-002-004)** 필요 — single source·silence로 추론 불가(line
140); freshness 상실 ⇒ `STALE`, new risk authorize 불가(line 141); `QUARANTINED`는 안정 보수 상태, 탈출은
evidence 필요(line 142).
> **로컬 저작 근거(§0.4e)**: `KnowledgeState`는 decision-side로 로컬 저작(evidence ledger·capsule
> `FieldState` 미재사용). `KnowledgeState.CONFLICTED`("이 trading action에 대한 confidence") ≠
> `FieldState.CONFLICTED`("한 context field의 freshness") — 별개 축(좌표 비붕괴).

**(5) `CompositeState`(IndependentIdArtifact) — ADR §1/§14.** 다섯 차원을 **각기 별개-타입 필드**로 담는
frozen product:

- `intent_identity`(link, SAFE-020) — scalar.
- `intent_state: IntentState`, `transmission_attempt_state: TransmissionAttemptState`,
  `broker_order_state: BrokerOrderState`, `knowledge_state: KnowledgeState`,
  `capacity_state: CapacityState`(rcl REUSE) — **다섯 required·non-Optional 필드**(§4.4 completeness).
- `observation_revision`(append-only observation 순서 — §3.2), version 참조 scalar.
- **`_REQUIRED_COVERED`**(ISSUED에서 concrete 필수): intent_identity + 다섯 차원 좌표(전부 present여야
  ISSUED; §4.4).

전역-구분 실측(dimension-swap canary 근거): 다섯 enum의 **string 값이 서로 전역 중복 없음**(예:
`TransmissionAttemptState.NONE`="NONE" vs `BrokerOrderState.NONE_OBSERVED`="NONE_OBSERVED";
`KnowledgeState.QUARANTINED`="QUARANTINED" vs `CapacityState.QUARANTINED_UNKNOWN`="QUARANTINED_UNKNOWN";
`KnowledgeState.UNKNOWN` 부재 vs `BrokerOrderState.UNKNOWN` 존재). ⇒ 한 차원 값을 다른 차원 필드에 넣으면
pydantic coercion이 실패(§4.2 canary).

### 2.3 `CompositeState` covered + self-exclusion (설계 #4 §3.3 상속)

covered(Layer-1) = intent_identity + 다섯 차원 좌표 + version 참조. preimage 제외: `composite_state_id`·
`canonical_digest`·`canonicalization_version`·`status`(ArtifactStatus lifecycle 마커)·ledger 배치 시
결정되는 `observation_revision`·파생 역참조. **TBD/null이 covered에 하나라도 있으면 pre-issuance(status=
DRAFT), digest 불가**(`_base.py:174` 부근). `composite_state_id` ⊥ `canonical_digest`(§3.1).

> **핵심 설계 결정 — composite는 observation append-only, lifecycle-state-out-of-collision(#7 §2.2 상속)**:
> 다섯 차원은 시간에 따라 **독립적으로 전이**한다(ADR §1 line 25 "The dimensions MAY disagree temporarily").
> 만약 하나의 stable id에 mutable 좌표를 담으면 정당한 전이(예: Broker `WORKING`→`PARTIALLY_FILLED`)가
> same-id/diff-bytes `CRITICAL_CONFLICT`로 **오탐**된다. ⇒ **각 관측(observation)은 fresh
> `composite_state_id`를 가진 immutable append-only 레코드**다. same `composite_state_id` + diff bytes ⇒
> `CRITICAL_CONFLICT`(위조·재제출만); 정당한 전이 ⇒ **새 observation(새 id)**. lifecycle 순서는
> `observation_revision`(§3.2 ordering)로 담고 전이 자체는 §2.4 transition record로 담는다.

### 2.4 `DimensionTransitionRecord` (IndependentIdArtifact) — ADR §12/§13

covered = intent_identity·`dimension: StateDimension`(어느 차원)·`from_state`/`to_state`(해당 차원 값)·
`owning_authority: TransitionAuthority`(§12 소유자)·`basis`(§6.1 conservative-direction basis)·evidence
참조 scalar·`observation_revision`. append-only(§13 durable/reconstructable). 이 레코드가 **ownership
술어(§6.2)·restart substrate(§6.3)·audit**의 입력이다. 실제 evidence emit·causal edge는 설계 #4 소관
(orthostate는 scalar만 남긴다). `transition_id` ⊥ `canonical_digest`; same-id/diff-bytes ⇒
`CRITICAL_CONFLICT`(§4.5).

---

## 3. canonical / ordering REUSE + rcl(capacity) 경계 + evidence/capsule/time 경계

### 3.1 canonical REUSE + `id=f(digest)` 미채택 (설계 #4·#5·#6·#7 §3.1 상속)

composite/transition ledger 시민은 `tos.canonical.IndependentIdArtifact`(`_base.py:328`)·
`DigestBoundArtifact`(digest 검증 `canonical_digest == H_ver(canonicalize(covered))`, `_base.py:98`)를
REUSE한다. canonicalizer는 `tos.canonical` registry + `EVL1ProvisionalCanonicalizer`(`ev-l1-provisional-0`)
REUSE, **신규 canonicalizer 없음**(프로덕션 canonical form은 Phase-0, §9.2). **`id=f(digest)`
(`IdDerivedArtifact`) 미채택**: §2.1 근거(SAFE-020 immutable·non-reuse + same-id/diff-bytes 위조 탐지 —
`classify_record_pair`, `record_pair.py:52`, `RecordPairKind.CRITICAL_CONFLICT`, line 43). capsule의
content-addressed `id=f(digest)`와 정반대. **필요 core 원소(IndependentIdArtifact·classify_record_pair)가
#5/#6 PROMOTE로 이미 core**이므로 **PROMOTE = 0건**(#7 동형).

### 3.2 ordering REUSE (observation/transition append-only 순서)

composite observation·transition 레코드의 append-only 순서는 신규 저작하지 않고 `tos.ordering`(Trustworthy
Time 설계 §5로 PROMOTE 완료; 코드 `tos/src/tos/ordering/`)의 `Ordering`·`OrderingEvent`·`compare_order`를
REUSE한다. `observation_revision`은 committed observation 순서(ADR §13 restart 재구성이 참조하는 순서)를
담는다. **wall clock은 순서를 만들지 않는다**(`tos.ordering` 규율) — orthostate는 clock을 읽지 않는다(§3.5).
light REUSE(core 의존, 신규 edge 아님).

### 3.3 REUSE 요약 표

| substrate | 결정 | 근거 |
|---|---|---|
| `FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`ArtifactStatus` | **REUSE(core `tos.canonical`)** | §3.1; 신규 없음 |
| `classify_record_pair`·`RecordPairKind` | **REUSE(core, 이미 PROMOTE됨)** | §3.1; same-id/diff-bytes |
| `Ordering`·`OrderingEvent`·`compare_order` | **REUSE(core `tos.ordering`)** | §3.2; observation 순서 |
| `CapacityState`·`transition_allowed` | **REUSE(sibling `tos.rcl`)** | §3.4; capacity 차원·lattice |
| capacity 보수성 comparator(`capacity_at_least_as_conservative`) | **rcl에 additive 노출 후 REUSE** | §3.4·§9.1; `_CONSERVATISM_RANK` private |
| `KnowledgeState`·세 로컬 차원 enum·§11 weak-basis | **로컬 저작** | §0.4c/§0.4e; §11 verbatim·decision-side |
| PROMOTE | **0건** | §3.1 |

### 3.4 rcl(Capacity 차원) 경계 — import-and-REUSE, lattice 재저작 금지 (중심 결정)

**(a) import 결정**: `tos.orthostate → tos.rcl`(세 번째 sibling→sibling edge, §0.4b). `CapacityState`
(`vocabulary.py:23–31`, 9종)를 composite의 다섯째 좌표로 REUSE하고, capacity 차원의 conservative-direction은
`transition_allowed(from_state, to_state, cause)`(`predicates.py:438–471`)를 REUSE한다 — **capacity의 9-상태
보수성 lattice·`_CONSERVATISM_RANK`(동 425–435)·`WEAK_CAUSES`를 재저작하지 않는다**(설계 결정 #3; DRY;
ADR §9 line 148 "Defined by ADR-002-002"). acyclic 확인(§0.4b): rcl은 canonical·ordering만 import.

**(b) capacity 보수성 comparator(핵심 난제)**: CPL-1("at least as conservative as `POTENTIALLY_LIVE`")·
CPL-4("at most `RELEASE_PENDING_PROOF`")는 capacity 상태의 **보수성 비교**를 요구하나 rcl의
`_CONSERVATISM_RANK`는 **private**(`predicates.py:425`)이고 rcl은 `transition_allowed`만 public이다. ⇒ 결정:
구현 선행 소단계로 rcl에 **thin public** `capacity_at_least_as_conservative(a: CapacityState, b: CapacityState)
-> bool`(기존 private rank 위 read-only wrapper; **동작 변경 없음·PROMOTE 아님·shim 불요**)를 additive로
노출하고 orthostate가 REUSE한다. **orthostate 내 재도출 금지**(rank 복제 = DRY/drift, 설계 결정 #3 위반).
`transition_allowed`를 weak-cause로 호출해 방향성을 추론하는 우회는 `RELEASED` 특례(`from RELEASED`⇒False,
`to RELEASED`⇒FINAL_QUANTITY_PROOF only)에 의존해 fragile하므로 기각. **실측 rank**(`predicates.py:425–435`,
0=least→8=most conservative): `RELEASED`0·`COMMITTED_UNBOUND`1·`ATTEMPT_BOUND`2·`POTENTIALLY_LIVE`3·
`PARTIALLY_CONSUMED`4·`POSITION_CONSUMED`5·`RELEASE_PENDING_PROOF`6·`TRAPPED_CONSUMED`7·`QUARANTINED_UNKNOWN`8.
이 rank가 §5.3 CPL-1/CPL-5 지배 관계의 근거다.

**(c) 운영자 판단 지점**: (i) 세 번째 sibling edge 허용, (ii) rcl에 comparator additive 노출 허용
(ratified rcl 접촉 — 순수 additive). Fallback: 둘 다 불허 시 opaque-scalar(대안 A)로 후퇴하되 CPL-1/2/4/5/7
predicate-only 강등(§0.4b).

### 3.5 evidence / capsule / time / authority 경계 — 형제/하류, scalar·주입 좌표만, import 금지

§0.4e대로: **`tos.evidence` 미import**(Knowledge = decision-side 상류; evidence store = 하류 투영 —
layering 역전 금지; `KnowledgeState` 로컬); **`tos.capsule` 미import**(`FieldState`는 다른 축 — 좌표 비붕괴);
**`tos.authority`·`tos.liveauth` 미import**(§12 소유자는 로컬 `TransitionAuthority` role enum + 주입 actor;
CPL-6 epoch-currentness는 주입 flag); **`tos.time` 미import**(Knowledge `STALE` freshness는 numeric bound가
Verification Profile 소관(ADR §18 line 249)이므로 **주입 opaque flag**(`fresh_within_bound: bool|None`,
None⇒STALE-보수)로만 담음 — rcl이 time 미import한 선례 동형·closure 최소화). §7.1 import-closure가 이
부재를 assert한다.

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **fail-closed discipline**:
빈/누락에 대한 술어는 절대 vacuous True가 되지 않으며, 보수성은 *양성 증명*을 요구하고, 각 가드에 **negative/
canary property**(가드가 실제로 발화함)를 붙인다.

### 4.1 no-mixed-enum 구조 불변식 (중앙 — RFC-002 §12; ADR §1)

**중앙 결정**: 다섯 차원은 **각기 별개 StrEnum 좌표**이고 composite는 **frozen product**다 —
dimension-collapse(하나의 order-status enum으로 붕괴)가 **구조적으로 표현 불가**하다. 실현:

1. **단일 mixed enum 부재**: intent+order+evidence+capacity를 섞는 `OrderStatus` 류 enum이 **존재하지
   않는다**(RFC-002 §12 line 1212 "SHALL NOT ... single order-status enumeration"; ADR §2 line 33 "A single
   enum forces false coupling"). composite는 스칼라 하나로 구성 불가 — 다섯 별개-타입 좌표를 **전부** 공급
   해야 구성된다(§4.4).
2. **차원별 값 격리(RECONCILED/UNKNOWN)**: ADR line 27 "`RECONCILED` is a value of the Knowledge dimension,
   not of the Broker Order dimension." ⇒ `RECONCILED` ∈ `KnowledgeState`, ∉ `BrokerOrderState`(구조적).
   `UNKNOWN` ∈ `BrokerOrderState`(first-class, capacity-consuming — line 27 "never means rejected,
   cancelled, unfilled, or safe to retry"), `KnowledgeState`에는 `UNKNOWN` 부재(대신 `UNOBSERVED`/
   `CONFLICTED`). property: 각 enum 멤버십을 회귀로 고정.
3. **disagreement 표현 가능**: ADR line 25 "The dimensions MAY disagree temporarily; the system SHALL
   represent that disagreement rather than collapse it." ⇒ §14 예시(예: Broker=`UNKNOWN` ∧
   Knowledge=`CONFLICTED` ∧ Capacity=`POTENTIALLY_LIVE`)가 **전부 구성 가능**(§7 fixture; STATE-EV-001 L1
   슬라이스의 핵심).

### 4.2 좌표 비붕괴 + dimension-swap canary (#6 §4.7 상속)

- **구조적 swap 거부**: 다섯 차원은 별개 타입이므로 한 차원 값을 다른 차원 필드에 넣으면 pydantic이 거부.
  **string 값 전역-구분**(§2.2 실측)이라 StrEnum coercion 수준에서도 실패한다. property(dimension-swap
  canary): 모든 (차원 A, 차원 B≠A) 쌍에 대해 A의 어떤 값도 B 필드 구성에 성공하지 못함(공유 string 값
  0건이 이를 보장).
- **좌표 비붕괴**: composite id·`observation_revision`·intent_identity·ArtifactStatus lifecycle은 서로
  **별개 좌표**이며 붕괴하지 않는다(#6 §4.7·#7 §4.4 동형). `KnowledgeState.CONFLICTED` ≠
  `FieldState.CONFLICTED`(capsule, 다른 축) — canary로 고정(단 capsule 미import이므로 문서 수준 회귀).

### 4.3 conservative-direction 구조 (STATE-EV-002 substrate — §6.1 상술)

§11 conservative-direction의 **구조적 부분**: (a) **weak §11 basis는 conservatism을 감소시킬 수 없다**
(어느 차원이든); (b) **conservatism 증가는 항상 허용**(§11 line 177 "Increasing conservatism ... is always
permitted and never blocked", 예: `RECONCILED`→`CONFLICTED`); (c) conservatism **감소**는 차원별 **positive
proof rule**을 요구. 세부·per-dimension rank·basis 집합은 §6.1.

### 4.4 composite completeness — 누락 차원 = invalid(default 없음), unknown 값 = most-conservative

- **completeness(구조적)**: `CompositeState`의 다섯 차원 필드는 **required·non-Optional**이며 **default가
  없다**. 하나라도 누락/`None` ⇒ 구성 실패(pydantic). 4-차원 composite는 표현 불가(§4.1). **canary**: 임의
  차원 필드 누락/None ⇒ 구성 예외; 어떤 차원도 silent default로 채워지지 않는다(rcl 주입 reducer 모델이
  Optional default를 가진 것과 **대비** — composite는 authoritative 관측이라 all-required).
- **unknown 값 = most-conservative(값 선택 규율)**: 차원에 대한 불확실성은 **누락/None이 아니라 그 차원의
  명시적 most-conservative 값**으로 표현해야 한다 — Broker⇒`UNKNOWN`, Knowledge⇒`CONFLICTED`/`UNOBSERVED`,
  Capacity⇒`QUARANTINED_UNKNOWN`(CPL-5). 즉 "모르면 비운다"가 아니라 "모르면 보수 값을 명시"한다. 이후
  §5의 coupling이 보수 composite를 강제.
- **주입 side-flag fail-closed**: 술어 입력의 proof/epoch/trapped/freshness flag(§5.2/§6.1/§6.3)는
  `bool|None`이며 **None ⇒ fail-closed(restrictive)**(설계 #2 `Freshness{within_bound: bool|None}`⇒UNKNOWN
  패턴 REUSE).

### 4.5 append-only + same-id/diff-bytes 충돌 (§13; §2.3)

모델에 update/delete 연산 부재(§2.0). composite 전이·정정은 새 observation/transition의 append로 표현.
same `composite_state_id`/`transition_id` + diff canonical digest ⇒ `classify_record_pair` =
`CRITICAL_CONFLICT`(contain 양쪽 보존, no last-write-wins). property: id⊥digest이므로 CRITICAL_CONFLICT
reachable(가드 발화); id=f(digest)면 unreachable임을 회귀로 고정(§3.1).

### 4.6 representation ≠ effect (§12 line 191)

composite/transition 레코드는 **비전송 representation**이며 상태를 **causation하지 않는다** — "Broker=FILLED"
기록이 체결을 만들지 않는다. 상태 변화는 오직 **소유 authority의 committed 전이**로만 일어난다(ADR §12 line
191 "Cross-dimension effects occur only through the owning authority's defined transition (e.g., a broker
fill event is presented as evidence; the Ledger performs the CPL-3 transfer)"). 모델에는 "다른 차원을 mutate
하는" 메서드가 **부재**(구성적 부재 — 설계 #5 capacity≠authority 정신 동형). all-false effect 블록이 필요하면
orthostate-local 재표현(§0.4e). 이 불변식이 evidence(하류 투영) 미import의 근거이기도 하다(§3.5).

---

## 5. cross-dimension coupling 술어 세부 (§10 CPL-1..7 — STATE-EV-003 L1 슬라이스)

**핵심 난제**: `CPL-1..7`(ADR §10 line 152–164)을 composite 위 **순수 static 위법-판정 술어**로 저작하되,
(i) **representability와 coupling-cleanliness를 분리**하고(§5.0), (ii) 겹치는 CPL 중 **satisfiable overlap은
더 보수적 의무가 이기며 contradictory overlap(exact-vs-exact)은 무조건 illegal로 flag**하고(§5.3), (iii)
결정되지 않은 조합을 **over-claim하지 않는다**(§5.4).

### 5.0 static-vs-transition 판정 — representability ≠ coupling-cleanliness (C1 해소, ADR-내부 tension)

본 계약은 `CPL-1..7`을 composite 위 **static detect-and-flag 술어**로 실현한다. STATE-EV-001(AC-005-1)의
**"representable"** 과 STATE-EV-003의 **"coupling-clean"** 은 **별개 주장**이다 — 혼동하면 fail-open이다(C1).

- **ADR §14 "all valid" = 전부 REPRESENTABLE**(coupling-satisfied 아님). 근거: AC-005-1(line 237) "the
  composite states in §14 are **all representable and persisted; no dimension is forced by another except
  through the CPL invariants**" — §14는 표현가능성 주장이고, CPL invariant가 한 차원이 다른 차원을 forcing하는
  *메커니즘*이다. §1 line 25 "The dimensions **MAY disagree temporarily; the system SHALL represent that
  disagreement rather than collapse it**"; §2 line 43은 (Broker=`UNKNOWN` ∧ Knowledge=`CONFLICTED` ∧
  Capacity=`POTENTIALLY_LIVE`) 조합(=14_2 shape)을 "must be holdable"로 명시.
- **transient disagreement = representable-but-coupling-flagged**: 14_2·14_4는 **구성 가능**(STATE-EV-001
  슬라이스)하나 **CPL-5 위반**(`coupling_violations` ⊇ {CPL-5})이다. 이는 모순이 아니라 **두 별개 주장의
  동시 성립**이다 — composite는 **HELD**(§10 line 164 "an invariant violation is a Critical incident and an
  immediate new-risk halt condition"; **결코 silent normalize 안 됨** — §5.5), violation set nonempty, 해소는
  소유 authority(RCL/Reconciliation)의 **런타임 작업(/3)**이다.
- **ADR-내부 tension 명시(project-side 읽기, non-amend)**: §14 예시(14_2를 "valid"로)와 §10 CPL-5("SHALL
  force `QUARANTINED_UNKNOWN`")는 **문면상 긴장**한다. 본 계약의 판정("valid"=representable, CPL=static flag)은
  **프로젝트 측 읽기**이며 **ADR을 amend하지 않는다**(non-normative). §14 예시가 정상-상태인지 transient인지의
  **권위적 해소는 Phase-0/ADR-owner 항목**(§9.2)이다. 안전 거동(flag·hold·never-normalize)은 어느 읽기에서도
  **불변**이다.

### 5.1 coupling 술어 형태

`coupling_violations(composite, side) -> frozenset[CplId]` (빈 집합 = 위반 미탐지) 및 `no_coupling_violation(
composite, side) -> bool`. `side`는 §5.2 주입 side-condition(proof/epoch/trapped/fresh flag). 각 CPL은
**필요조건**(위반 시 illegal)이며, 술어는 **적용되는 모든 CPL의 conjunction**이다(ADR §10 line 164 "A
composite state is valid only if all applicable coupling invariants hold"). 위반은 **탐지 후 restrictive**
이며 **silent normalize 없음**(§5.5).

### 5.2 CPL 표 (per-cell grounding)

| CPL | 조건(antecedent) | 의무(consequent) | 술어(fail-closed) | ADR 근거 |
|---|---|---|---|---|
| **CPL-1** | Attempt ∈ {`SEND_STARTED`, `SENT_UNCONFIRMED`} ∨ Broker=`UNKNOWN` | Capacity **≥ `POTENTIALLY_LIVE`**(보수성) | `capacity_at_least_as_conservative(cap, POTENTIALLY_LIVE)`(§3.4 comparator) | line 156 |
| **CPL-2** | Capacity=`RELEASED` | Knowledge=`RECONCILED`(또는 proof-rule 하 `CONSISTENT`) **∧** Broker ∈ {`CANCELLED`,`REJECTED`,`EXPIRED`,`FILLED`} (필요 시 FQP) | proof-required flag None ⇒ FQP 요구(restrictive) | line 157 |
| **CPL-3** | Broker=`FILLED`(완전) ∨ `PARTIALLY_FILLED` | (static, Gap 확정) Broker=`FILLED` ⇒ Capacity=`POSITION_CONSUMED`; `PARTIALLY_FILLED` ⇒ Capacity=`PARTIALLY_CONSUMED` — aggregate-state 일관성; 미반영이면 illegal | **static exact-value 일관성 술어**(§5.3b 참여); quantity별 원자 transfer·잔량 `POTENTIALLY_LIVE` split은 rcl `CapacityVector`/런타임(/3) | line 158 (ADR-002-002 §15.1) |
| **CPL-4** | Broker=`CANCEL_PENDING` ∨ **bare cancel-ACK**(=Broker=`CANCELLED` ∧ FQP proof-flag 부재/None) | Capacity **≠ `RELEASED`**(cancel 단독은 release 불가) | `cap != RELEASED`. **static view에서 CPL-2에 subsume**(m2): `CANCEL_PENDING` ∉ CPL-2 release-set이고 proof-부재 `CANCELLED`는 CPL-2 proof 조건 실패 ⇒ 양쪽 다 CPL-2가 이미 RELEASED 금지. CPL-4 고유 content "at most `RELEASE_PENDING_PROOF`"는 **transitional(/3)**. (proven `CANCELLED`+release는 CPL-2가 허용) | line 159 (ADR-002-002 §16.2) |
| **CPL-5** | Broker=`UNKNOWN` ∨ Knowledge ∈ {`CONFLICTED`,`QUARANTINED`} | Capacity **= `QUARANTINED_UNKNOWN`** ∧ scope 내 new risk 차단 | `cap == QUARANTINED_UNKNOWN`(정확 일치) | line 160 (§7 line 122, §8) |
| **CPL-6** | Attempt→`SEND_STARTED` 전이 | authority epoch·live scope가 final egress에서 verifiable; stale epoch fail-closed | **주입 `epoch_current: bool|None`**; None/False ⇒ 전이 거부(binding 술어만; 실제 egress 검증 이연) | line 161 (ADR-002-003) |
| **CPL-7** | 확정 non-reducible exposure(주입 flag) | Capacity **= `TRAPPED_CONSUMED`** — pending exit Intent/Attempt 무관 | `cap == TRAPPED_CONSUMED`; pending exit가 이를 감소 못 함 | line 162 (ADR-002-002 §24) |

- **fail-closed 공통**: side-flag None ⇒ 해당 CPL은 보수적으로 위반-처리(vacuous pass 금지). composite
  completeness(§4.4)로 다섯 차원 값은 항상 present.

### 5.3 겹치는 CPL 해소 — satisfiable overlap(보수 의무 지배) vs contradictory overlap(무조건 illegal)

CPL이 같은 capacity 차원에 동시 적용될 때 **두 종류**가 있고, "더 보수적 의무가 이긴다"는 **한 종류에만**
성립한다.

**(a) satisfiable overlap — 더 보수적 의무가 conjunction으로 지배(lower-bound vs exact).** Broker=`UNKNOWN`
에서 CPL-1(Capacity ≥ `POTENTIALLY_LIVE`, rank ≥ 3)과 CPL-5(Capacity = `QUARANTINED_UNKNOWN`, rank 8)가
동시 적용된다. conjunction(§5.1)이므로 **둘 다** 만족해야 하고, `QUARANTINED_UNKNOWN`(rank 8 ≥ 3)만이 둘을
만족한다 — **CPL-5(더 보수적·exact)가 지배**. **canary**: Broker=`UNKNOWN` ∧ Capacity=`POTENTIALLY_LIVE`
(=14_2 shape)는 **illegal**(CPL-5 위반; CPL-1 단독이면 admit) — 회귀 고정. rank 의존이므로 property로
`capacity_at_least_as_conservative(QUARANTINED_UNKNOWN, POTENTIALLY_LIVE) == True`를 **assert**한다(rank
재도출 아님, rcl comparator 검증 — §3.4b; rcl rank가 바뀌면 test가 포착).

**(b) contradictory overlap — exact-vs-exact on different values ⇒ 무조건 illegal, flagged, never
normalized(M1).** "더 보수적 의무가 이긴다"는 lower-bound vs exact에만 성립하고 **exact-vs-exact에는 성립하지
않는다** — 서로 다른 정확 값을 요구하므로 순서로 해소 불가. capacity에 **exact 값**을 forcing하는 CPL(실측
열거): **CPL-5**(=`QUARANTINED_UNKNOWN`)·**CPL-7**(=`TRAPPED_CONSUMED`)·**CPL-3**(=`POSITION_CONSUMED`/
`PARTIALLY_CONSUMED`, §5.2 Gap). pairwise co-trigger 만족가능성:

- **CPL-5 ∧ CPL-7**: trigger 공존(Knowledge∈{`CONFLICTED`,`QUARANTINED`} ∨ Broker=`UNKNOWN`, **AND**
  trapped=True). `QUARANTINED_UNKNOWN` ≠ `TRAPPED_CONSUMED` ⇒ **어떤 capacity 값도 둘을 못 만족 ⇒ 무조건
  illegal**(모든 9 값 위법).
- **CPL-3 ∧ CPL-5**: Broker=`FILLED`/`PARTIALLY_FILLED`(CPL-3) **AND** Knowledge∈{`CONFLICTED`,`QUARANTINED`}
  (CPL-5). `POSITION_CONSUMED`/`PARTIALLY_CONSUMED` ≠ `QUARANTINED_UNKNOWN` ⇒ **무조건 illegal**.
- **CPL-3 ∧ CPL-7**: Broker=`FILLED`(CPL-3) **AND** trapped=True(CPL-7). `POSITION_CONSUMED` ≠
  `TRAPPED_CONSUMED` ⇒ **무조건 illegal**.

이 경우 composite는 **모든 capacity 값에 대해 위법**이며 **flagged·HELD**된다(§5.5). **구현이 한 CPL을 drop해
"resolve"하는 것은 금지** — CPL-5 drop은 quarantine(SAFE-030) 신호 상실, CPL-7 drop은 trapped-exposure
(ADR-002-002 §24) 신호 상실이며 **어느 쪽도 fail-open**이다. **canary(§7)**: Knowledge=`CONFLICTED` ∧
trapped=True에서 **9개 capacity 값 전부** `coupling_violations` nonempty(sweep).

> **exact-value subsumption의 ADR-owner 이관**: exact-value CPL이 서로를 subsume하는지(예: `TRAPPED_CONSUMED`가
> CPL-3의 `POSITION_CONSUMED`를 subsume하는가)의 권위적 해소는 ADR-owner 소관(§9.2 static-vs-transition 항목).
> 그러나 **flag·hold·no-drop** 안전 거동은 그 해소와 무관하게 불변이다(보수적 기본값 = 무조건 illegal·flag).

### 5.4 결정되지 않은 조합 — over-claim 금지 (충분조건 아님)

`CPL-1..7`은 **필요조건**이다. ADR는 **모든 legal composite를 열거하지 않는다**(§14는 5개 *예시*일 뿐).
⇒ `no_coupling_violation`은 "`CPL-1..7` 위반 미탐지"만 주장하고 **"완전 legal"을 주장하지 않는다**(후속
ADR가 추가 제약을 얹을 수 있음). CPL이 다루지 않는 차원 조합은 **위반-미탐지**로 통과시키되, 이것이
"safe/legal 승인"이 아님을 규율 태그로 명시. CPL-3의 원자적 transfer 강제(ADR-002-002 §15.1, Ledger 수행 —
§4.6)와 CPL-6의 실제 egress 검증은 **런타임(/3)**이며 Phase 1은 static 일관성·binding 술어만(STATE-EV-003
`/3` 꼬리).

### 5.5 illegal composite = 탐지 후 restrictive, silent normalize 금지 (§10 line 164)

illegal composite는 **표현 가능**(그래야 시스템이 "탐지된 위법 상태"로 잡아 halt)하되 **위법으로 탐지**되고
**결코 silent normalize되지 않는다**. ADR §10 line 164 "An invariant violation is a Critical incident and
an immediate new-risk halt condition." **canary(구성적 부재)**: "가장 가까운 legal composite로 보정/normalize"
연산이 **부재**한다 — `coupling_violations`는 위반 집합을 **반환**할 뿐 composite를 **변경하지 않는다**.
(dimension-collapse는 구조적 표현 불가(§4.1)이나, well-formed illegal composite는 표현 가능·탐지됨 — 두
보장을 구분.)

---

## 6. conservative-direction · ownership · restart-reconstruction 술어 세부

### 6.1 conservative-direction (§11 — STATE-EV-002 substrate; weak-basis 로컬 verbatim)

**핵심 난제(선제 봉합)**: §11의 weak-basis를 rcl의 더 좁은 `WEAK_CAUSES`로 대체하면 under-realization
(fail-open)이다. ⇒ 네 로컬 차원용 **로컬 basis taxonomy**를 §11 verbatim으로 저작한다.

**(a) 로컬 basis 집합(ADR §11 line 172–175 verbatim)**. `ConservatismBasis`(StrEnum) — weak 집합
`WEAK_BASES`:
- `TIMEOUT`, `ABSENCE`, `LOCAL_CACHE`, `OPERATOR_ASSERTION` (line 172 "timeout, absence, local cache, or
  operator assertion" — **4개**).
- 추가 금지 패턴(line 173–175): `RECOVERY_RECONNECT`("treating recovery/reconnect as knowledge of a
  specific state"), 및 collapse 금지 규칙(`UNKNOWN`→`NONE`/`CANCELLED`/`UNFILLED`; cancel/ACK를 capacity
  terminal로)은 별도 술어로.
> **rcl `WEAK_CAUSES`와의 divergence 명시(의도)**: rcl `WEAK_CAUSES = {TIMEOUT, ABSENCE, OPERATOR_ASSUMPTION}`
> (`vocabulary.py:102–108`, ADR-002-002 §10.2)는 **`LOCAL_CACHE`·`RECOVERY_RECONNECT`를 포함하지 않는다** —
> orthostate `WEAK_BASES` ⊋ rcl `WEAK_CAUSES`. 두 집합이 다른 것은 각 ADR에 충실한 **의도**이며(rcl §10.2,
> orthostate §11), **네 로컬 차원에 rcl `WEAK_CAUSES`를 재사용하지 않는다**(재사용 시 "local cache" 근거
> conservatism-reduction이 걸러지지 않는 fail-open — #7 SAFE-053 under-realization defect class 방지).
> capacity 차원**만** `rcl.transition_allowed`(rcl `WEAK_CAUSES` 사용)를 REUSE한다.

**(b) direction 술어**: `conservative_direction_allowed(dimension, from_state, to_state, basis) -> bool`:
- dimension=`CAPACITY` ⇒ `rcl.transition_allowed(from, to, rcl_cause)` **REUSE**(재저작 금지, §3.4).
- 그 외 네 차원 ⇒ 로컬 규칙: conservatism 증가/동일 ⇒ 임의 basis 허용(§11 line 177); conservatism 감소 ⇒
  **strong dimension-specific proof basis만** 허용, `WEAK_BASES` ∋ basis면 항상 거부; **basis None ⇒
  fail-closed(weak 취급, 감소 불가)**.
- 차원별 strong proof(감소 허용 조건): Broker `UNKNOWN`→definite = **broker-evidence-under-profile**(§7 line
  104/120); Knowledge →`RECONCILED` = **positive corroborating evidence + FQP where broker involved**(§8
  line 140); Attempt →`SEND_FAILED_PROVEN` = **positive proof broker did not/cannot accept**(§6 line 97);
  Intent authority 증가(PROPOSED→…→ACTIVE) = **approval/aggregate-risk decision**(§5 line 67/75).
- **collapse 금지 canary(§11 line 173–175)**: `UNKNOWN`(Broker)→`NONE_OBSERVED`/`CANCELLED` under weak basis
  ⇒ 거부; cancel/ACK를 capacity terminal로 취급 ⇒ 거부(CPL-4 정합); recovery/reconnect(`RECOVERY_RECONNECT`)
  를 특정 상태 knowledge로 ⇒ 거부.

**(c) per-dimension rank의 해석 여지(정직한 under-claiming)**: capacity는 rcl rank(권위적)를 REUSE하나,
네 로컬 차원의 **완전한 conservatism total-order**는 ADR §11이 명시 열거하지 **않는다**(서술적 규칙만). ⇒
Phase 1은 **§11이 명시한 방향 규칙**(weak-can't-reduce·increase-always·차원별 명시 proof·collapse 금지)만
저작하고, 명시되지 않은 pair의 감소는 **fail-closed(strong basis 요구)**로 보수 처리하며, 완전 per-dimension
lattice의 권위적 ratification은 **Phase-0 판단 지점**(§9.2)으로 남긴다. STATE-EV-002는 어차피 predicate-only
(EV 비주장)이므로 이 substrate가 EV를 닫지 않는다.

### 6.2 transition-ownership (§12 — STATE-EV-005 substrate)

`may_transition(actor: TransitionAuthority, dimension: StateDimension, from_state, to_state) -> bool`. 로컬
enum: `TransitionAuthority` = {`INTENT_REGISTRY`, `EXECUTION_COORDINATOR`, `BROKER_ADAPTER_EGRESS`,
`BROKER_ADAPTER_EVIDENCE`, `RECONCILIATION_SERVICE`, `RISK_CAPACITY_LEDGER`}; `StateDimension` = {`INTENT`,
`TRANSMISSION_ATTEMPT`, `BROKER_ORDER`, `KNOWLEDGE`, `CAPACITY`}. §12 표(line 183–189) verbatim 매핑:

| dimension | 허용 actor(들) | 근거 |
|---|---|---|
| INTENT | `INTENT_REGISTRY` | line 185 |
| TRANSMISSION_ATTEMPT | `EXECUTION_COORDINATOR`(prep 영역 `NONE`..`CAPABILITY_ISSUED`) + `BROKER_ADAPTER_EGRESS`(send-boundary `SEND_STARTED`..) | line 186 (§6 line 82 region split) |
| BROKER_ORDER | `BROKER_ADAPTER_EVIDENCE`(broker evidence under profile — assumption 아님) | line 187 (§7 line 104) |
| KNOWLEDGE | `RECONCILIATION_SERVICE` | line 188 |
| CAPACITY | `RISK_CAPACITY_LEDGER` only | line 189 |

- **fail-closed**: 미지의 actor/dimension ⇒ 거부. **canary(§12 line 191 "No component SHALL write a
  dimension it does not own")**: 비-owner ⇒ 거부(예: `RECONCILIATION_SERVICE`가 CAPACITY 전이 시도 ⇒ False;
  CAPACITY는 `RISK_CAPACITY_LEDGER` only). Attempt의 **region split** 정확 반영(prep vs send-boundary
  from/to로 owner 결정).
- **경계(+Security 이연)**: 실제 actor 인증·비-owner 거부의 rejection+evidencing은 EV-L2/3+Security
  (STATE-EV-005 최소 레벨). Phase 1은 role 좌표 위 순수 ownership 술어만. Broker `UNKNOWN`→definite의
  "under profile" evidence 조건은 주입 flag(미증명 ⇒ 거부).

### 6.3 restart-reconstruction (§13 — STATE-EV-004 substrate, predicate-only)

`reconstruct_conservative(pre: CompositeState, terminal_proof: ...) -> CompositeState`: §13(line 195–200)의
보수적 재구성을 순수 projection으로:
- Attempt가 `SEND_STARTED` 도달(∈ {`SEND_STARTED`, `SENT_UNCONFIRMED`, provably-terminal 아닌 후속}) ⇒
  Capacity를 **≥ `POTENTIALLY_LIVE`**로(line 198).
- Broker가 **provably terminal 아님**(∈ {`FILLED`,`CANCELLED`,`REJECTED`,`EXPIRED`} + proof가 아님) ⇒
  **`UNKNOWN`**(line 198).
- Knowledge ⇒ evidence로 **재도출**, default `UNOBSERVED`/`CONFLICTED`, **결코 `RECONCILED` 아님**(line 199).
- **property(보수성 단조)**: `reconstruct_conservative(pre)`는 결코 pre보다 less-conservative composite를
  산출하지 않는다. **canary(구성적 불가능)**: post에 Knowledge=`RECONCILED`가 **도달 불가**(pre가
  `RECONCILED`여도 post는 `CONFLICTED`/`UNOBSERVED`) — "restart가 특정 상태를 알게 됨"(§11 line 175 recovery/
  reconnect 금지)이 표현 불가.
- **경계(EV-L3)**: 실제 durable reload·crash recovery·§13 line 200 Recovery Barrier + fresh re-arm chain
  (ADR-002-017/007)은 out-of-scope(scalar/flag). STATE-EV-004 = EV-L3(no L2 — 가장 이연); 이 projection은
  substrate일 뿐 EV를 닫지 않는다.

---

## 7. property-test 하네스 타깃

§1 분류에 정렬. property는 bound를 **hypothesis 생성 주입값**으로 다뤄 "임의 유효 bound 하 보수적 성립"을
검증(특정 값 비의존, 하드코딩 없음 — §8). **§14 다섯 composite를 named fixture**로 둔다:
`COMPOSITE_14_1_CAPABILITY_ISSUED`(Intent=APPROVED, Attempt=CAPABILITY_ISSUED, Broker=NONE_OBSERVED,
Knowledge=CONSISTENT, Capacity=ATTEMPT_BOUND), `COMPOSITE_14_2_SENT_UNKNOWN`(ACTIVE, SENT_UNCONFIRMED,
UNKNOWN, CONFLICTED, POTENTIALLY_LIVE), `COMPOSITE_14_3_PARTIAL_FILL`(ACTIVE, ACK_OBSERVED, PARTIALLY_FILLED,
CONSISTENT, PARTIALLY_CONSUMED), `COMPOSITE_14_4_SUPERSEDED_CANCEL`(ACTIVE, SUPERSEDED, CANCEL_PENDING,
CONFLICTED, RELEASE_PENDING_PROOF), `COMPOSITE_14_5_FILLED_RECONCILED`(ACTIVE, ACK_OBSERVED, FILLED,
RECONCILED, POSITION_CONSUMED) — ADR §14 line 207–211 verbatim. **coupling 분류(§5.0)**: 14_1/14_3/14_5 =
**coupling-clean positive**(`no_coupling_violation`==True); **14_2/14_4 = coupling-NEGATIVE**(Broker=`UNKNOWN`
또는 Knowledge=`CONFLICTED`가 CPL-5를 발화 ⇒ `coupling_violations` ⊇ {CPL-5}). 다섯 전부 **구성 가능**
(STATE-EV-001 representability)이나 **coupling-cleanliness는 셋만**(STATE-EV-003) — 두 축은 별개(§5.0).

| family | Phase-1 타깃 | substrate / 근거 |
|---|---|---|
| composite canonicalization + digest 검증 | **REUSE 설계 #4 must-pass suite**(`tos.canonical`) | §2.3; frozen digest 일관성 |
| §14 다섯 composite **표현 + digest 결정성 ONLY** | **core(L1 슬라이스)** | §4.1; STATE-EV-001. 5 fixture 전부 **구성 가능(constructible frozen product) + canonical digest 결정성**. **coupling-cleanliness는 이 행 소관 아님** — STATE-EV-003 행(§5.0 representability≠coupling). *(C1: 이전 `no_coupling_violation==True` 단언 제거 — 14_2/14_4는 CPL-5 위반)* |
| no-mixed-enum + dimension-swap | **구조 불변식** | §4.1/§4.2. swap ⇒ 구성 실패; RECONCILED∉Broker·UNKNOWN∈Broker 회귀 |
| composite completeness | **구성 불변식** | §4.4. 차원 누락/None ⇒ 구성 실패(default 없음 canary) |
| same-id/diff-bytes 충돌 | **REUSE core `classify_record_pair`** | §4.5; CRITICAL_CONFLICT reachable(id⊥digest) |
| CPL-1..7 위법 판정 **(clean positive)** | **core(L1 슬라이스)** | §5; STATE-EV-003. **14_1/14_3/14_5** ⇒ `no_coupling_violation`==True(guard **both-ways** 양성 side) |
| CPL-1..7 위법 판정 **(coupling-negative)** | **core(L1 슬라이스)** | §5; STATE-EV-003. **14_2/14_4** ⇒ `coupling_violations` ⊇ {CPL-5}(§5.3a); **CPL-1∧CPL-5 지배 canary**(Broker=UNKNOWN∧Capacity=POTENTIALLY_LIVE ⇒ illegal); fail-closed(None side ⇒ 위반); **런타임 강제는 /3** |
| **representable-but-coupling-flagged** (C1 test class) | **core(001∧003 교차)** | §5.0; **14_2/14_4는 구성 성공(STATE-EV-001 슬라이스) AND `coupling_violations` nonempty(STATE-EV-003 슬라이스) 동시 성립** — 두 별개 주장(모순 아님) |
| **contradictory overlap sweep** (M1) | **core(L1 슬라이스)** | §5.3b; STATE-EV-003. Knowledge=`CONFLICTED` ∧ trapped=True ⇒ **9개 capacity 값 전부** `coupling_violations` nonempty(CPL-5∧CPL-7 exact-vs-exact 무조건 illegal); **no-drop** canary |
| conservative-direction(로컬 §11 weak-basis) | **predicate** | §6.1; STATE-EV-002. **WEAK_BASES ⊋ rcl WEAK_CAUSES**(local_cache/recovery-reconnect 감소 불가 canary); capacity=rcl.transition_allowed REUSE |
| transition-ownership | **predicate** | §6.2; STATE-EV-005. 비-owner ⇒ 거부(RCL-only capacity canary); Attempt region split |
| restart-reconstruction | **predicate** | §6.3; STATE-EV-004. SEND_STARTED⇒POTENTIALLY_LIVE·non-terminal broker⇒UNKNOWN·knowledge≠RECONCILED(post-RECONCILED 도달불가 canary) |
| representation ≠ effect | **구성적 부재 + 술어** | §4.6. mutate-other-dimension 메서드 부재; normalize 연산 부재(§5.5) |

- **core(L1 슬라이스)** = {STATE-EV-001, STATE-EV-003} 관련 family. **predicate-only** = {002, 004, 005}.
  **닫는 STATE-EV = 0건**(§1 규율). bound는 hypothesis 주입, 하드코딩 없음(§8).

### 7.1 import-closure 검증 테스트 (C1 강제 — 설계 #4 §7.1·#6·#7 §7.1 확장)

서브프로세스에서 `import tos.orthostate`(및 `tos.canonical`·`tos.rcl`·`tos.ordering`)만 한 뒤 `sys.modules`를
검사해 assert: (1) 설계 #1 §2.3 금지 패키지 부재; (2) **`shared.config`·`shared.config.secrets` 부재**(전이
유입 런타임 포착); (3) `os.environ`/`os.getenv` 미참조; (4) **`numpy`·`pandas`·`yaml`(pyyaml) 부재**(bound
주입·YAML은 하네스 소관, §0.3); (5) **`tos.time`·`tos.evidence`·`tos.capsule`·`tos.authority`·`tos.liveauth`·
`tos.dsl` 부재**(§3.5 layering — 형제/하류; evidence·capsule·authority·time은 scalar/주입 좌표로만 참조);
(6) **`tos.canonical`·`tos.rcl`·`tos.ordering` 존재 허용**(§3.1/§3.4/§3.2 — 세 번째 sibling edge
`orthostate→rcl`을 명시적 허용 대상으로 기록: import-closure가 이 edge를 *봉인*하지 않고 *한정*한다). required
check(`tos-firewall`)와 함께 green이어야 §0.3 준수 선언이 능동 성립한다.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

orthostate 전용 템플릿은 없으므로 설계 #1 §5.1 규율을 REUSE한다. evidence를 산출하는 모든 property-test run은:
(1) git commit digest + `tos` 버전; (2) 인터프리터 + 고정 의존성 버전(pydantic/hypothesis); (3) 실행 환경;
(4) 하네스 git digest; (5) **property-test seed**(hypothesis seed/derandomize, append-only); (6) **소비 설정
아티팩트 digest**(주입 STATE bound 프로파일 + `canonicalization_version` + `tos.ordering`·**`tos.rcl`**
primitive 버전); (7) 산출 아티팩트 sha256. (VER-002-001 §2.3 재현성·§9.1 seed·§9.2 digest의 EV-L1 부분집합.)

---

## 8. bounds 주입 + 누락 프로파일 키 Phase-0

`VERIFICATION-PROFILE-002.yaml`은 전체 `status: PROPOSED`·`approved_by: []`·`effective_from: null`(배너
"an unapproved or placeholder bound is not an approved bound"). ADR-002-005 §18(line 249) "Numeric freshness
bounds (`STALE` thresholds) belong in the Verification Profile / Safety Profile."

- **결정**: STATE 관련 bound(Knowledge `STALE` freshness threshold·startup reconciliation·external-activity
  detect 등)는 **주입 policy 파라미터**로만 들어온다. **어떤 숫자도 하드코딩하지 않는다**(CLAUDE.md). 값
  누락 ⇒ `UNKNOWN` ⇒ fail-closed(§4.4 side-flag None⇒restrictive; §6.3 freshness None⇒STALE-보수).

- **실측 확인(evidence-based) — 프로파일에 존재하는 STATE-관련 키**(grep). **키 명으로 인용**하고 line은 참고;
  파일은 `VERIFICATION-PROFILE-002.yaml`(설계 #5/#7 인용과 동일 non-template)이며, 동일 키가
  `VERIFICATION-PROFILE-002-template.yaml`에는 다른 line에 있다 — 아래 괄호 **[non-template / template]**
  (m1 정정):
  - `B_stale_epoch_reject`[177 / 156]: `0` / PROPOSED, "synchronous ... compare-and-set; 0 = no time window"
    (ADR-002-002 INV-008, ADR-002-003). ⇒ CPL-6 epoch-currentness·ownership을 **동기 순수 술어**로 모델링함을
    지지(시간 창 없음).
  - `B_external_activity_detect`[184 / 163]·`B_startup_reconciliation`[198 / 177]: Knowledge `CONFLICTED`→
    `RECONCILING` 및 restart 후 reconciliation 타이밍(ADR-002-006/017 소유; latency=런타임).
  - `MAX_currentness_vector_age_ms`[724 / 702]: `null`, "unknown or stale vector age denies admission" —
    Knowledge/currentness staleness의 **가장 가까운 기존 키**(누락-키 항목 2 참조).
  - 기타 `MAX_*_age_ms`(recovery readiness·decision context·capability age)·`B_*_invalid_to_egress` 계열
    (ADR-002-018/019/020/021/022 material invalidation→egress denial): per-domain freshness/`STALE`·invalidation
    — 각 소유 ADR(002-017/018/019/003) 소관, latency=런타임(egress).

- **누락 distinct 키 (Phase-0 Bounds-Approver 플래그)**: 실측 대조 결과 —
  1. **구조 조항(차원·coupling·ownership·conservative-direction·restart)에는 numeric bound 부재** — 전부 상태
     enum·boolean·rank(capacity=rcl) 논리라 승인할 숫자가 없다. ADR-002-005가 도입하는 유일한 수치 의존은
     §18 line 249의 `STALE` freshness threshold다.
  2. **Knowledge/reconciliation-staleness 키 = Phase-0 CANDIDATE(genuinely-new 가능; m3 정밀화).** Knowledge
     차원 `STALE`(§8 line 141 "prior knowledge older than its approved freshness bound")에 대응하는 **전용**
     키는 프로파일에 **없다**. 가장 가까운 기존 키는 `MAX_currentness_vector_age_ms`[724/702](currentness
     vector 신선도)이나, ADR-002-005 §8 Knowledge는 **reconciliation confidence**(ADR-002-006 소유) 축이라
     그것과 정확히 일치하지 않는다. ⇒ knowledge/reconciliation-staleness가 **dedicated 신규 키를 요하는지**는
     **ADR-002-006-의존 Phase-0 candidate**로 flag한다(확정-누락도 확정-커버도 아님 — 정직한 under-claim).
     기존 per-domain age 키(recovery/context/currentness)는 **재계상하지 않는다**(중복 계상 회피 — 설계 #4 §8·
     #5 §8·#6 §8·#7 §8 규율 동형).

  ⇒ **확정 신규 누락 키 0건, Phase-0 candidate 1건**(knowledge/reconciliation-staleness — ADR-002-006 의존).
  Phase 1은 freshness를 **주입 opaque flag**(§3.5)로 담는다. 값·키 승인은 Bounds-Approver 게이트(Live-Armer와
  분리 — IMPLEMENTATION-PLAN §3)의 소관이다. [SAFE-030 conservative UNKNOWN 정합]

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

- **`tos/src/tos/orthostate/` 모델·술어·property·import-closure 테스트 저작**(§2–§7): 설계 #3(EV-L1 하네스)이
  property suite를 실행. `tos.canonical`(digest+id+classify) + `tos.ordering`(순서) + **`tos.rcl`
  (CapacityState·transition_allowed)** REUSE, 신규 canonicalizer/ordering/capacity-lattice 없음. **PROMOTE
  0건**(IndependentIdArtifact·classify_record_pair 이미 core).
- **rcl에 `capacity_at_least_as_conservative` additive 노출(구현 선행 소단계 — §3.4b)**: 기존 private
  `_CONSERVATISM_RANK`(`predicates.py:425`) 위 thin public read-only comparator를 rcl에 추가(동작 변경·
  PROMOTE·shim 없음), orthostate가 REUSE. **orthostate 내 rank 재도출 금지**(DRY/drift, 설계 결정 #3).
  ratified rcl 접촉이므로 운영자 승인(§10.2). Fallback: 불허 시 opaque-scalar 후퇴(CPL predicate-only 강등).
- **의존 방향**: orthostate ⟸ `tos.canonical`·`tos.ordering`·`tos.rcl`. orthostate는 time/evidence/capsule/
  authority/liveauth/dsl을 import하지 않음(형제/하류, scalar·주입 좌표만). acyclic 확인: rcl은 orthostate
  미참조(rcl→{canonical,ordering}만).
- **의존성 관찰(결정 아님)**: 완전 per-dimension conservatism lattice(§6.1c)와 Capacity comparator 노출은
  ADR-002-006(reconciliation confidence)·프로파일 ratification과 함께 재검토될 수 있음(지금은 미채택; 본
  문서는 rcl/ADR을 변경하지 않는 non-normative).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

1. **`tos.orthostate → tos.rcl` 세 번째 sibling edge + rcl comparator additive 노출 승인**(§3.4/§10.2).
2. **프로덕션 canonical serialization·digest 알고리즘 선택**(설계 #4 §9.2 item 1과 동일 게이트):
   `ev-l1-provisional-0`·sha256은 비프로덕션.
3. **완전 per-dimension conservatism lattice ratification**(§6.1c): ADR §11이 명시 열거하지 않은 네 로컬
   차원의 total conservatism order(특히 Intent lifecycle)는 해석 여지가 있어 정책/독립리뷰 승인.
4. **`STALE` freshness threshold 값 승인 + knowledge/reconciliation-staleness 전용 키 여부**(§8; ADR §18
   line 249; ADR-002-006): 기존 per-domain age 키(recovery/context/`MAX_currentness_vector_age_ms`)로
   cross-ref하되, Knowledge 차원 전용 STALE 키가 genuinely-new로 필요한지는 **ADR-002-006-의존 candidate** —
   Bounds-Approver ≠ Live-Armer.
5. **broker-specific evidence·Final Quantity Proof 규칙**(ADR-002-004): Broker 차원 evidence-under-profile·
   Knowledge `RECONCILED` FQP의 *양성 proof token* 내용은 Broker Capability Profile(승인, broker-agnostic
   capability class) 소관 — §5.2 CPL-2·§6.1 direction의 주입 flag.
6. **reconciliation confidence 모델**(ADR-002-006): Knowledge 차원의 confidence 표현·`RECONCILING`→
   `{RECONCILED|QUARANTINED}` 판정은 ADR-002-006 소관 — orthostate는 `KnowledgeState` enum + 주입 proof flag만.
7. **authority epoch 메커니즘**(ADR-002-003): CPL-6 epoch-currentness는 주입 flag; 실제 epoch/egress
   currentness는 authority/liveauth 런타임.
8. **persistence 기술 + restart 실기 + 런타임 coupling 강제**(ADR §4 line 61·§13): STATE-EV-001 `/2`·
   STATE-EV-003 `/3`·STATE-EV-004 EV-L3 — **Phase B(EV-L2/L3)**, Phase 1 EV-L1 밖(§0.2).
9. **Independent-Safety-Reviewer 지정 + §7 EV-L1 evidence 수용 서명**(저자 배제 — IMPLEMENTATION-PLAN §3).
10. **static-vs-transition 판정 + exact-vs-exact contradictory overlap의 ADR-owner 해소**(§5.0/§5.3b; v1.1
    C1/M1): ADR §14 예시("valid")와 §10 CPL-5/CPL-7("SHALL force" exact 값)의 문면상 tension — §14 조합이
    정상-상태인지 transient(representable-but-coupling-flagged)인지, exact-value CPL 간 subsumption(예:
    `TRAPPED_CONSUMED` vs CPL-3의 `POSITION_CONSUMED`)을 어떻게 볼지 — 의 권위적 해소는 **ADR-002-005 owner
    소관**이다. 본 계약의 읽기("valid"=representable, CPL=static flag, contradictory⇒hold·no-drop)는
    non-normative project-side이며 **ADR을 amend하지 않는다**. 안전 거동(flag·hold·never-normalize)은 해소와
    무관하게 불변.

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- 2026-07-25: **v1.0 초안 최초 작성.** ADR-002-005 EV-L1 실현 계약. 설계 #1(경계·firewall)·#2(all-false·
  좌표 어휘)·#4(canonical substrate + id⊥digest)·#5(**Capacity 차원 = rcl REUSE**·capacity lattice·rank)·
  #6(좌표 비붕괴)·#7(lifecycle-state-out-of-digest·sibling-edge 선례·bounds under-report 정정)에 정렬.
  주요 결정: (§0.4a) 전용 패키지 `tos/src/tos/orthostate/`(`tos.state`는 per-package `state.py` 충돌·
  `tos.dimensions`는 rcl capacity-vector "dimension" 충돌 — 둘 다 기각); (§0.4b/§3.4) **`CapacityState`
  import-and-REUSE** — 본 시리즈 **세 번째 sibling→sibling edge**(ADR Depends-On 002-002 정합; coupling이
  capacity 값 추론이라 opaque-scalar 부적합 — liveauth와 원칙적 차이; DRY·설계결정#3로 capacity lattice
  재저작 금지; acyclic), 대안 3종(opaque-scalar/로컬-재표현+drift/core-PROMOTE) 기각; **capacity comparator는
  rcl에 additive 노출**(`_CONSERVATISM_RANK` private, `transition_allowed` 우회 fragile); (§0.4c/§6.1)
  **conservative-direction weak-basis 로컬 verbatim**(§11 line 172 — `local cache` 포함) — **rcl
  `WEAK_CAUSES` 미재사용**(더 좁음, under-realization/fail-open 방지 — #7 SAFE-053 defect class 선제 봉합);
  (§0.4d/§3.1) canonical REUSE + `id=f(digest)` 미채택 + **PROMOTE 0건**; (§0.4e/§3.5) evidence(하류 투영·
  layering)·capsule(다른 축)·authority/liveauth(role은 로컬 enum)·time(freshness 주입) **미import**;
  (§0.4f) **INV 시리즈 창작 금지**(ADR엔 CPL-*·AC-005-*만 — 실측), STATE-EV/CPL/AC/§-clause/SAFE 앵커;
  (§1) **STATE-EV core tier 존재**(001/003 EV-L1 슬라이스 — RCL-형; Time/#6/#7과 다름) but **닫는 STATE-EV
  0건**(authoring≠evidence), core(001/003 L1슬라이스)/predicate-only(002/004/005)/not-Phase-1(없음);
  (§2) composite/transition = **IndependentId + 독립 id**, **observation append-only + lifecycle-state-
  out-of-collision**(정당 전이의 CRITICAL_CONFLICT 오탐 방지); (§2.2) **Intent `DENIED` 분기점 = APPROVED**
  (line 71 column-22 alignment + line 75 의미 대조로 확정)·**`ACTIVE→WITHDRAWN` guard**(line 72/77 verbatim);
  (§4.1) **no-mixed-enum 구조 불변식**(중앙; dimension-collapse 표현불가; RECONCILED∈Knowledge·UNKNOWN∈Broker);
  (§4.4) **completeness**(차원 누락⇒invalid, default 없음)·**unknown-value⇒most-conservative**; (§5) CPL-1..7
  술어·**CPL-1∧CPL-5 conjunction 지배**(Broker=UNKNOWN⇒QUARANTINED_UNKNOWN이 POTENTIALLY_LIVE를 이김, rank
  8>3 실측)·over-claim 금지(필요조건, 충분 아님)·silent-normalize 금지; (§6) conservative-direction/ownership/
  restart 술어; (§8) **신규 누락 키 0건**(STALE freshness = 기존 per-domain age 키 cross-reference, 중복
  계상 회피). **선제 fail-open 봉합**: §11 weak-basis under-realization·에라타 defect class(부등호/필드명/
  분기점)·CPL 중첩 지배. 이후 독립 비평 리뷰.
- 2026-07-25: **v1.1 — 독립 비평 리뷰 REJECT 반영(CRITICAL 1 / MAJOR 1 / MINOR 3 / gap 1).** 리뷰는
  transcription apparatus(DENIED column 측정·enum·guard·CPL 방향·rank·`WEAK_CAUSES` divergence·EV 레벨)를
  **byte 수준 전량 clean 검증**했고, safety-core의 **cross-section 모순**을 지적했다. 전건 반영: **[C1 —
  REJECT driver]** §7 STATE-EV-001 fixture 행이 5개 §14 composite 전부 `no_coupling_violation==True`라 단언
  → 14_2/14_4가 자신의 CPL-5를 발화하므로 §5.3 canary와 **상호 모순**(naive 구현이 CPL-5 canary drop 시
  SAFE-030 fail-open). 원인: **representability(AC-005-1)와 coupling-cleanliness(STATE-EV-003) 혼동.** 수정:
  (i) §7 STATE-EV-001 행을 **표현+digest 결정성 ONLY**로 축소(`no_coupling_violation` 제거); (ii) 14_2/14_4를
  **coupling-negative fixture**(⊇{CPL-5})로·14_1/14_3/14_5를 clean positive로 재분류; (iii) **§5.0
  static-vs-transition 판정 신설**(§14 "valid"=representable, transient disagreement=representable-but-
  coupling-flagged·HELD·never-normalize; AC-005-1 line 237·§1 line 25·§2 line 43 근거; ADR-내부 tension은
  project-side·non-amend·§9.2 ADR-owner 이관); (iv) §7에 **representable-but-coupling-flagged** test class
  추가. **[M1]** §5.3이 satisfiable overlap만 다룸 → **contradictory overlap(exact-vs-exact)** 추가:
  exact-value CPL(CPL-5/CPL-7/CPL-3) 열거, co-trigger 무조건-illegal(CPL-5∧CPL-7·CPL-3∧CPL-5·CPL-3∧CPL-7),
  **한 CPL drop 금지**(quarantine/trapped 신호 상실=fail-open), §7 sweep canary(Knowledge=CONFLICTED∧
  trapped=True ⇒ 9 capacity 전부 nonempty). **[m1]** §8 line 인용 정정 — `B_external_activity_detect`
  ~195→**184**, 키-명 인용 전환·non-template/template line 병기·파일명 명시. **[m2]** §5.2 CPL-4가 static
  view에서 **CPL-2에 subsume**됨 명시(고유 content "at most `RELEASE_PENDING_PROOF`"는 transitional/3),
  bare cancel-ACK=Broker=`CANCELLED`∧FQP proof None(proven `CANCELLED`+release는 CPL-2 허용). **[m3]** §8
  freshness 키 정밀화 — `MAX_currentness_vector_age_ms` nearest 명시 + knowledge/reconciliation-staleness를
  **ADR-002-006-의존 Phase-0 candidate**로 flag(확정 신규 0 → candidate 1). **[Gap]** §5.2 CPL-3 static
  content 확정(FILLED⇒`POSITION_CONSUMED`·PARTIALLY_FILLED⇒`PARTIALLY_CONSUMED` aggregate-state 일관성;
  quantity transfer·잔량 split은 /3). §9.2 +1항목(static-vs-transition ADR-owner, 총 10). 아키텍처 핵심
  (패키지·rcl import·PROMOTE-0·id⊥digest·§11 weak-basis divergence·transcription)은 v1.0 그대로.

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

- [ ] §0.2 NO 목록(persistence 기술·egress·capacity 내부·authority/reconciliation/broker 규칙·**닫는
      STATE-EV 0건**·bounds 미승인)과 §0.3 firewall 준수(numpy/pandas/pyyaml·shared.config·**tos.time·
      tos.evidence·tos.capsule·tos.authority·tos.liveauth·tos.dsl 배제, tos.canonical·tos.rcl·tos.ordering만
      허용**; `.importlinter`는 forbidden 계약뿐 — intra-tos edge firewall-clean)에 동의.
- [ ] §0.4a 전용 패키지 `tos/src/tos/orthostate/`(`tos.state`/`tos.dimensions` 충돌 기각; naming
      비-load-bearing) 채택에 동의.
- [ ] §0.4b/§3.4 **`CapacityState` import-and-REUSE**(세 번째 sibling→sibling edge; ADR Depends-On 정합·
      coupling이 capacity 값 추론·DRY·설계결정#3·acyclic; 대안 opaque-scalar/로컬-재표현/core-PROMOTE 기각)
      + **capacity lattice 재저작 금지** + **rcl에 `capacity_at_least_as_conservative` additive 노출**에
      동의. **[운영자 판단 지점: 세 번째 sibling edge + rcl comparator additive 노출 vs opaque-scalar fallback
      (CPL predicate-only 강등 — 비권장)]**
- [ ] §0.4c/§6.1 **conservative-direction weak-basis 로컬 verbatim(§11 line 172, `local cache`·`recovery/
      reconnect` 포함)** + **rcl `WEAK_CAUSES` 미재사용(orthostate WEAK_BASES ⊋ rcl WEAK_CAUSES — 의도적
      divergence, under-realization 방지)** + capacity만 `rcl.transition_allowed` REUSE에 동의.
- [ ] §0.4d/§3.1 canonical REUSE + `id=f(digest)` 미채택 + **PROMOTE 0건**(IndependentId·classify_record_pair
      이미 core)에 동의.
- [ ] §1 **STATE-EV core tier 존재**(001=EV-L1/2·003=EV-L1/3 L1 슬라이스 — RCL-형, Time/#6/#7의 "0건 완결"과
      다름) but **authoring이 STATE-EV를 닫지 않음**(core 두 항목도 L1 슬라이스뿐·/2·/3 잔존; VER §5) +
      core(001/003)/predicate-only(002/004/005)/not-Phase-1(없음) + "EV-L1-complete 주장 금지"에 동의.
- [ ] §2 데이터 모델(다섯 차원 별개 StrEnum + rcl `CapacityState`; composite/transition = **IndependentId +
      독립 id**, `IdDerivedArtifact` 0건; **observation append-only + lifecycle-state-out-of-collision**)과
      **§2.2 Intent 다이어그램 전사**(`DENIED`←`APPROVED` 분기 line 71 column-22 + line 75; `ACTIVE→WITHDRAWN`
      guard line 72/77)에 동의.
- [ ] §4.1 **no-mixed-enum 구조 불변식**(중앙; dimension-collapse 구조적 표현불가; RECONCILED∈Knowledge only·
      UNKNOWN∈Broker first-class) + §4.2 dimension-swap canary(string 값 전역-구분) + §4.4 **completeness
      (누락 차원⇒invalid, default 없음)·unknown-value⇒most-conservative** + §4.6 representation≠effect에 동의.
- [ ] **§5.0 static-vs-transition 판정(C1)**: `CPL-1..7`=static detect-and-flag; **ADR §14 "valid"=
      representable ≠ coupling-clean**(AC-005-1 line 237·§1 line 25·§2 line 43); transient disagreement
      (14_2/14_4)=**representable-but-coupling-flagged**(HELD·never-normalize); ADR-내부 tension은
      project-side 읽기·non-amend·§9.2 ADR-owner 이관에 동의.
- [ ] §5 coupling(CPL-1..7 static 위법 판정; **§5.3a satisfiable overlap — CPL-1∧CPL-5 더 보수적 exact가
      지배**(Broker=UNKNOWN⇒QUARANTINED_UNKNOWN, rank 실측); **§5.3b contradictory overlap(M1) — exact-vs-
      exact(CPL-5∧CPL-7·CPL-3∧CPL-5·CPL-3∧CPL-7)은 무조건 illegal·flag·no-drop**(한 CPL drop=quarantine/
      trapped 신호 상실=fail-open; 9-capacity sweep canary); **over-claim 금지**(필요조건, 충분 아님);
      **silent normalize 금지**; CPL-3 static(FILLED⇒POSITION_CONSUMED·PARTIALLY_FILLED⇒PARTIALLY_CONSUMED,
      quantity transfer /3)·CPL-4 CPL-2-subsume(고유 content transitional /3)·CPL-6 egress /3 이연)에 동의.
- [ ] §6 conservative-direction(로컬 §11 basis·capacity=rcl REUSE·완전 lattice는 §6.1c 해석여지 flag)·
      ownership(§12 표·비-owner 거부 canary·Attempt region split·+Security 이연)·restart(reconstruct_
      conservative·post-RECONCILED 도달불가 canary·실기 EV-L3 이연)에 동의.
- [ ] §7 하네스 타깃(**§14 다섯 named fixture**: **14_1/14_3/14_5=coupling-clean positive·14_2/14_4=
      coupling-negative(⊇{CPL-5})**; STATE-EV-001 fixture 행은 **표현+digest ONLY**(C1); **representable-but-
      coupling-flagged·contradictory-overlap sweep test class 추가**; core/predicate 구분; "EV-L1-complete
      주장 금지"), §7.1 import-closure(tos.time/evidence/capsule/authority/liveauth/dsl 부재 + tos.canonical/
      rcl/ordering 허용), §7.2 run manifest 7항목에 동의.
- [ ] §8 bounds 주입 + **확정 신규 누락 키 0건 + Phase-0 candidate 1건**(knowledge/reconciliation-staleness
      — `MAX_currentness_vector_age_ms` nearest, ADR-002-006-의존 dedicated 키 여부 flag; 기타 STALE freshness=
      기존 per-domain age 키 cross-ref, 중복 계상 회피; m1 line 인용 정정)에 동의.
- [ ] §9.2 Phase-0 이관 10항목(sibling edge+comparator·프로덕션 canon·conservatism lattice ratification·STALE
      freshness 값·broker FQP proof·reconciliation confidence·authority epoch·persistence/restart/coupling
      런타임·독립 리뷰어)을 별도 게이트로 유지에 동의.
- [ ] 명명 규약(§0.4f): 모델 불변식을 **CPL-1..7 / AC-005-1..5 / §-clause / STATE-EV-### / SAFE-xxx**에
      앵커하고 **새 INV 시리즈를 창작하지 않음**(ADR-002-005엔 INV 부재 — 실측)에 동의.

비준 시 효력: IMPLEMENTATION-PLAN-002 §4 Phase 1의 ADR-002-005 부분을 `tos/src/tos/orthostate/`에 순수·
비전송 모델 + property test로 작성 착수 승인(`tos.canonical`·`tos.ordering`·`tos.rcl` REUSE, PROMOTE 0건,
rcl comparator additive 노출 1건). §9.2 Phase-0 10항목과 bounds 승인·독립 리뷰어 지정, Phase B(persistence·
restart 실기·런타임 coupling 강제·+Security ownership) 전체는 별도 게이트로 남는다. **닫는 STATE-EV 0건 —
acceptance 주장 없음.**
