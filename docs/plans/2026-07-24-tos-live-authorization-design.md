# 설계 문서 #7 — Live Authorization + Limit Governance + Re-arm 계약 (2026-07-24, v1.2)

> **문서 번호 규약**: #1 경계·import-firewall, #2 Decision Context Capsule, #4 Evidence
> Store, #5 Risk Capacity Ledger(RCL), #6 Safety Authority가 이미 존재한다(#3은 folded).
> Trustworthy Time·DSL은 병렬 트랙이었다. **#7 = 본 Live Authorization 문서**이며,
> **트랙 A(ADR-002-003/007/008 묶음)의 세 번째이자 마지막 §2 코어**다 — 순서는
> Time(ADR-002-008) → Authority(ADR-002-003, #6) → **본 문서(ADR-002-007)**. authority가
> capability·epoch·lease를 소유하고 time이 monotonic 좌표를 소유하는 위에, 본 문서는
> **Live Authorization 아티팩트·limit governance·re-arm 소비**를 얹는 최상류 소비자다.
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**
> 이며 스펙 텍스트(RFC/ADR/템플릿/프로파일)를 **변경하지 않는다.** broker-agnostic 원칙
> (project memory `tos-spec-broker-agnostic`): KIS 등 특정 브로커 사실은 프로젝트 측 예시로만
> 등장하며 규범 주장이 아니다. Live Authorization·layering·re-arm·dual-control·§14.1 delta
> 불변식은 전부 broker-agnostic이며, 브로커 제약은 capability class(Broker Capability
> Profile)로만 표현한다. 본 문서는 IMPLEMENTATION-PLAN-002 §4 Phase 1(EV-L1)의
> **ADR-002-007 부분**을 그린필드 `tos/src/tos/liveauth/`에 **순수·비전송 데이터 모델 +
> property test**로 실현한다.
>
> **선행 문서(의존)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   설계 #1 §2.1(line 117–118)이 **"Live Authorization"을 IMPLEMENTATION-PLAN §2의 9개 코어
>   중 하나(first-class)** 로 열거한다(RCL·Safety Authority·Trustworthy Time·Live Authorization·
>   Egress Gateway·Reconciliation·Recovery Coordinator …). 본 계약의 모든 모델은 그 코어의 전용
>   패키지 `tos/src/tos/liveauth/`에 놓이고 §3.2 허용목록 안에서만 의존한다(§0.3). line 164
>   "내부 세분화는 후속 설계 문서가 정의한다"에 따라 본 문서가 그 패키지 내부를 정의한다.
> - [설계 #6 — Safety Authority 계약 (v1.2, 비준·구현됨)](2026-07-23-tos-safety-authority-design.md)
>   + 코드 `tos/src/tos/authority/`. **본 문서의 중심 아키텍처 결정**이 authority와의 경계다:
>   Live Authorization은 authority의 epoch currentness(`authority_epoch_current`)·precedence
>   (`restrictive_dominates`/`PRECEDENCE_RANK`)·**re-arm 전제 checklist(`rearm_gate`)**·capability
>   validity(`permissive_capability_valid`)·`CapabilityType.REARM/LIMIT_ACTIVATION`의 **하류
>   소비자**다. **`tos.authority`를 import**하는 것이 본 시리즈 **두 번째 sibling→sibling edge**
>   이며 정당화가 §0.4b/§3.4의 핵심이다. authority.rearm_gate SoD가 **strict-distinct-only**
>   (SAFE-053 variant 미모델 — `predicates.py` line 771–775)이므로 §13 two-lawful-paths dual
>   control은 liveauth가 **ADD**한다(§0.4e/§6).
> - [설계 #4 — Evidence Store 계약 (v1.1, 비준·구현됨)](2026-07-20-tos-evidence-store-design.md)
>   + 코드 `tos/src/tos/canonical/`. **canonicalization/digest-binding substrate(`tos.canonical`)·
>   `IndependentIdArtifact`(이미 core — #6 PROMOTE 완료)·`classify_record_pair`·ordering를 REUSE**
>   한다(재정의 금지). evidence의 `id=f(digest)` **미채택** 결정을 Live Authorization이 **동형으로
>   상속**한다(§2.1/§3.1). **본 문서 PROMOTE = 0건**(IndependentIdArtifact가 이미 core라 #6과 다름).
> - [설계 #5 — Risk Capacity Ledger 계약 (v1.1, 비준)](2026-07-21-tos-risk-capacity-ledger-design.md)
>   + 코드 `tos/src/tos/rcl/`. RCL은 **capacity 측** 형제다. Live Authorization은 RCL capacity
>   (reservation/pool/capacity-lease)를 **scalar 참조**만 하고 `tos.rcl`을 import하지 않는다
>   (§0.3/§3.3). RCL의 `ProtectiveLease.safety_authority_epoch_binding` scalar-참조 선례가
>   scalar-only 경계 방향을 확정한다(#6 §0.4d 상속).
> - [설계 — Trustworthy Time 모델 계약 (v1.1, 비준)](2026-07-21-tos-trustworthy-time-design.md)
>   + 코드 `tos/src/tos/time/`. ADR-002-007 §9(line 261)의 "Time is `TRUSTED`" 지속-유효성
>   조건과 authorization freshness는 `tos.time`의 술어(`state_permits_new_normal_risk`·
>   `snapshot_age_admissible`·`conservative_usable_lifetime`)가 **substrate**다. **`tos.liveauth`가
>   `tos.time`을 (authority 경유가 아니라) 직접 import**한다 — ADR Depends-On 002-008 정합, diamond
>   acyclic(§0.4c/§3.4).
> - [설계 #2 — Decision Context Capsule 계약 (v2, 비준·구현됨)](2026-07-20-tos-decision-context-capsule-snapshot-design.md).
>   `SnapshotAuthority._all_authority_false` 패턴(`tos/src/tos/capsule/_base.py`)·capsule의
>   `generation_vector` 어휘를 REUSE(로컬 재표현/scalar 참조)한다. `tos.capsule` 자체는 import하지
>   않는다(형제). Decision Context Capsule은 **scalar 참조**(ADR-002-018 소유).
>
> **규범 원천**: `ADR-002-007` — Live Authorization, Limit Governance, and Re-arm (Status:
> **Proposed**, **v0.3**, 724 line). Amends RFC-002 §19/§23; Depends-On RFC-000 constitutional
> safe state, RFC-001(SAFE-003/004/011/013/015/021/022/024/025/035/041/042/044/045/046/047/048/
> 050/051/052), ADR-002-001..006, **ADR-002-008**(line 11). §24 interfaces: ADR-002-009/012/013/
> 014/015/017/018/019/020/021/024/025/026/029/030 + VER-002-001. 매핑 대상 EV:
> `verification/EVIDENCE-REGISTER-002.csv`의 `REARM-EV-001..012`(line 79–90). **v0.3 이력 필독**:
> §14.1 In-Place Scope Expansion(v0.2, Wave 8 U2), SAFE-053 variant-path 인식(v0.3, Wave-1 CR-02
> propagation gap — §13/§14.1 item 3/REARM-AC-005에 strict conditional exception 추가;
> ARCHITECTURE-GATE-STATUS §3.16). 본 문서는 v0.3 텍스트를 규범 원천으로 삼는다.
>
> **비준 기록**: **2026-07-24 운영자 비준(v1.1) — 효력 발생.** *(v1.2 = §6.4 item 4 게이트 필드명
> 오기 에라타만 — `automatic_rearm_denied`→`live_rearm_denied`; 의미 변경 아님(오기 필드는 무조건
> True라 문면대로면 전 re-arm 차단되는 과잉제한), 비준 효력 유지; §10.1 v1.2.)* §10.2 판단 지점 3건 승인:
> **`tos.liveauth → tos.authority` import**(두 번째 sibling edge) · **`tos.time` 직접 import**(diamond
> acyclic) · **SAFE-053 variant = liveauth-local 14항 재표현 + drift 회귀 테스트**(compose 폐기;
> RearmVerdict 확장은 §9.1 의존성 관찰로만). 효력: `tos/src/tos/liveauth/` Phase 1(EV-L1) 순수·비전송
> 모델 + property test 착수(PROMOTE 0건). **REARM-EV 0건 완결** — acceptance 주장 없음; §9.2 Phase-0
> 9항목(+§17.1.6 variant evidence-debt는 Phase-0 소관)은 별도 게이트 유지.
>
> **리뷰 이력**: **v1.1(2026-07-24) — 독립 비평 리뷰 REVISE 반영.** v1.0 초안 → 별도 컨텍스트
> adversarial 리뷰(fail-open seam·인용 fidelity vs primary source·firewall/layering·overclaim/EV 정직성)
> **REVISE**(MAJOR 2 / MINOR 2 / gap 2). 리뷰는 EV 정직성·#6 4개 defect class 선제봉합·acyclicity/PROMOTE-0/
> firewall/프로파일 키/~20 인용·lifecycle arrow·layering 방향을 **전부 clean 검증**했고, REVISE는 **최고-위험 §
> (SAFE-053 dual-control ADD)에 집중된 2 MAJOR** + 2 MINOR + 2 gap이었다. v1.1은 전 항목 반영(§10.1):
> **[M1]** §6.4 variant-path compose를 **quorum 직접 소비 + variant 14항 로컬 재표현 + drift 회귀 테스트**로
> 확정(합성-principal compose 폐기 — `RearmVerdict`가 14전제/SoD 미분해, `state.py:163–174`), **[M2]** §6.3/§2.7
> SAFE-053 controls에 **§17.1.2 time-separation·§17.1.3 attestation** 추가(5→7), external-reviewer 구성은 Path 1
> 라우팅. m1/m2 인용 정정, Gap-1/Gap-2 봉합. **REARM-EV 0건 완결** — acceptance 주장 없음; §9.2 Phase-0 항목은
> 별도 게이트. 직전 #6 v1.0 REJECT defect class(claimant/subset vacuous-True·type-gated disjunction·부등호
> 전치)는 v1.0에서 선제봉합했고 리뷰가 확인했다. 수용 서명 게이트는 IMPLEMENTATION-PLAN-002 §3 하드 배제
> (Independent-Safety-Reviewer는 본 문서의 저자/통합자여서는 안 됨)를 따른다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-007 조항별 **EV-L1 도달성 경계**와 **REARM-EV 0건 완결** 결정적 사실(§1). REARM-EV
   12행을 **predicate-only / not-Phase-1** 2분류(코어 tier 없음 — EV-L1-최소 행 0건).
2. Live Authorization ledger 시민(**Live Authorization · authorization-transition · re-arm-approval**
   레코드)과 injected 술어 상태(scope·layering·continuous-validity·dual-control·§14.1 delta)의
   **데이터 모델 계약**(§2).
3. **authority·time·canonical·ordering REUSE + tos.authority/tos.time import 결정**(§3): `tos.canonical`
   REUSE + `id=f(digest)` **미채택**; **`IndependentIdArtifact`는 이미 core라 PROMOTE 0건**(#6과의
   차이); `tos.ordering` REUSE(authorization issue-sequence/lifecycle 감사); **`tos.authority` import**
   (두 번째 sibling→sibling edge — epoch/precedence/rearm/capability 술어 compose, §0.4b);
   **`tos.time` 직접 import**(TRUSTED/freshness, §0.4c); **`tos.rcl`·`tos.capsule`·`tos.evidence`·
   `tos.dsl`은 import 금지**(형제·scalar 참조만).
4. **authorization ≠ enforcement 중앙 불변식**(§4.1): Live Authorization의 발행·보유·서명은 **live가
   아니다** — `ACTIVE`는 지속-유효성(continuous validity)이 *현재* 성립할 때만이고 issued 사실로부터
   추론되지 않는다(§8.1 line 242–244). 모델은 non-transmitting 데이터이며 유효성 술어 True도
   authorization을 **완결하지 않는다**(§1 조건 6 = §16 final egress 독립검증은 런타임). 설계 #4
   evidence≠authority·#5 capacity≠authority·#6 authority≠enforcement 동형.
5. **default-non-live·non-revival·fresh-identity·좌표 비붕괴 상속** 불변식(§4): authorization 부재
   (None/empty) ⇒ **non-live**(zero-value 케이스); terminal(REVOKED/EXPIRED/SUSPENDED/SUPERSEDED/
   DENIED) ⇒ `ACTIVE` 복귀 불가·revive 없음; re-arm ⇒ **새 authorization identity**; restrictive
   generation 전진은 future 무효화이며 결코 복원하지 않음; authorization identity ≠ safety_authority_epoch
   ≠ revocation-generation ≠ ArtifactStatus lifecycle(좌표 비붕괴, #6 §4.7 상속).
6. **Live Authorization validity/scope/freshness 술어 세부**(§5): default-non-live 술어, 6-part
   continuous-validity 필요조건(egress 조건 비주장 경계), **subset scope coverage(empty ⇒ 아무것도
   미포함 — vacuous-True 봉합)**, freshness(time compose), lifecycle 전이 술어, fresh-identity.
7. **limit governance·re-arm·SoD·§14.1 delta 술어 세부**(§6): layering 불변식(per-action ≤ LiveAuth ≤
   RuntimeProfile ≤ HardEnvelope — 부등호 방향 명시·이중검증), atomic activation, **two-lawful-paths
   dual-control(quorum ∨ SAFE-053 variant, type-gated)**, re-arm 소비(authority.rearm_gate compose +
   fresh Live Authorization), no-automatic-rearm, partial-scope narrowing, **§14.1 delta-proportional
   in-place expansion(delta용 새 authorization, old은 결코 확장 안 됨)**.
8. **property-test 하네스 타깃**(§7) + import-closure 검증 확장(§7.1) + run manifest 7항목(§7.2).
9. **bounds 주입 계약 + 누락 프로파일 키 Phase-0 게이트 플래그**(§8): **Live Authorization
   maximum-validity(duration) 전용 키 부재**(실측 — 신규 누락).

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR-002-007
  §25(line 705) "authorizes design and non-live implementation-planning work only. It does not
  authorize ADR acceptance, restricted-live operation, or production live trading." ADR acceptance는
  오직 *실행된* evidence로만 온다(project memory `tos-spec-rfc-authoring-track`).
- **실제 egress 강제·fenced 단일-사용 capability 프로토콜을 구현하지 않는다.** §9.1–§9.5(line
  286–337 fenced single-use capability/currentness session/deny latch/claim-to-send)·§16(line
  520–544 final egress enforcement)은 **런타임+broker+security**다. 설계 #1 §4대로 tos는 정의상
  **non-transmitting**이다(자격증명·라우트·주문구성 부재 + egress firewall 차단). §1 조건 6·REARM-AC-010
  (final egress)의 *egress* 부분은 Phase 1에서 **egress가 소비하는 identity/scope/version/revocation-
  generation binding 술어**만 저작하고 실제 전송·fenced claim은 이연한다(REARM-EV-010 not-Phase-1).
- **실제 human dual-control 인증·approval 소비를 구현하지 않는다.** §13(line 422–435)의 인증된
  human principal·quorum·approval-consumption 메커니즘은 **ADR-002-015 런타임**이다(§24 OQ1). Phase 1은
  principal **좌표**(identity distinctness) 위 순수 술어와 SAFE-053 variant compensating-control
  **attestation flag**만 저작한다(REARM-EV-005 +Security 이연).
- **실제 safety-configuration 아티팩트(Hard Safety Envelope·Runtime Safety Profile)를 저작하지
  않는다.** §4.1/§4.2는 이들을 **ADR-002-014 소관**으로 둔다(자체 governance/atomic activation).
  liveauth는 version+generation+digest를 **scalar 참조**만 하고 layering 술어를 그 위에 얹는다.
- **Recovery Readiness Decision·Recovery Evidence Package를 저작하지 않는다.** §4.3/§11은 이들을
  **ADR-002-017 소관**으로 둔다. liveauth는 id+generation+digest scalar 참조만; readiness는 re-arm
  전제(§6.6)의 injected flag로만 소비한다.
- **실제 clock을 읽지 않는다.** authorization freshness는 time-bounded이나 모든 시간 값은 `tos.time`의
  **opaque 주입 좌표**다(Time 설계 §0.3). liveauth 어디에도 clock read가 없다(`time`/`datetime`/
  `monotonic` firewall 금지).
- **authority를 부여하지 않는다.** 모든 Live Authorization 아티팩트의 `authority_effect.*`
  (`is_live_by_possession`·`self_transmits`·`self_arms`·`self_activates`·`self_expands_scope`·
  `self_revives`)는 **false 상수**이며 모델이 강제한다(§4.1). "authority 경로가 어디에도 없다"의
  전수 증명은 EV-L3+Security(REARM-EV-001/004/010)다.
- **어떤 REARM-EV도 완결하지 않는다(§1). REARM-EV 0건 완결.** `REARM-EV-001..012`는 register 최소
  레벨이 **전부 EV-L2 이상**이다(csv line 79–90 실측: `REARM-EV-012`만 `EV-L2`, `-001/-004/-005/-010`
  = `EV-L3+Security`, 나머지 = `EV-L3`; **EV-L1 최소 항목 0건**). ⇒ Time "TIME-EV 0건"·#6 "SA-EV
  0건"과 **동형**. "EV-L1-complete 주장 금지"(설계 #2 §7·#4 §7·Time §1·#5 §1·#6 §1 규율 상속).
- **numeric bounds를 승인하지 않는다.** VERIFICATION-PROFILE-002 bounds 승인·누락 키 신설(§8)·독립
  리뷰어 지정은 Phase-0 인간 게이트(§9.2).

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

Live Authorization 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`도 import하지
  않는다** — scope는 frozenset, epoch·generation·limit은 정수, freshness 산술은 `tos.time`이 정수/
  `Decimal`로 이미 수행하므로 수치 백엔드가 불필요(closure 최소화 — #6 §0.3 동형). **`pyyaml`도 import
  하지 않는다** — 모든 bound는 **주입 policy 파라미터**로 들어오고(§8), YAML 파싱은 하네스(설계 #3)
  소관이지 liveauth closure 안이 아니다.
- tos 자기 자신: `tos.canonical`(digest-binding substrate + **이미 core인 `IndependentIdArtifact`** +
  `classify_record_pair` — §0.4d), `tos.ordering`(authorization issue-sequence/lifecycle 감사 — §3.2),
  **`tos.time`**(TRUSTED·freshness 술어·좌표 타입 — §0.4c/§3.4), **`tos.authority`**(epoch currentness·
  precedence/dominance·rearm_gate·capability validity·`CapabilityType` — §0.4b/§3.5), `tos.liveauth.*`.
  **`tos.rcl`·`tos.capsule`·`tos.evidence`·`tos.dsl`을 import하지 않는다.** RCL capacity(reservation/
  pool/lease)·Decision Context Capsule(ADR-002-018)·Recovery(ADR-002-017)·safety-config(ADR-002-014)은
  오직 **scalar 참조**(id·version·generation·digest)로만 담고 클래스를 import하지 않으며, 역으로
  이들도 liveauth를 import하지 않는다(§3.3 layering — 형제).
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter` line 41): `shared.config.__init__`이
  `shared.config.secrets`(→ `os.environ`)를 무조건 전이 import한다. liveauth는 애초에 어떤 `shared.*`도
  필요로 하지 않는 순수 커널이다.
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`, `shared.llm`,
  `shared.storage`, `shared.backtest`, `services.*`, `cli.*`(설계 #1 §2.3; `.importlinter` forbidden
  set line 34–43).
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(`import tos.liveauth` closure에 금지·
  `shared.config`·`os.environ`·numpy/pandas/yaml·**`tos.rcl`·`tos.capsule`·`tos.evidence`·`tos.dsl`**
  부재 assert; **`tos.authority`·`tos.time`·`tos.ordering`·`tos.canonical`는 존재 허용**). required
  check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter` layer-② 전이 방어)와
  함께 green이어야 본 선언이 능동 성립한다.
- **firewall 구조 확인(실측)**: `.importlinter`(line 29–43)는 **`forbidden` 계약**(source=`tos`,
  forbidden={shared.execution/kis/streaming/llm/storage/backtest, shared.config.secrets, services, cli})
  **뿐**이며 **`layered` 계약이 아니다** — 즉 intra-tos sibling→sibling edge는 구조적으로 금지되지
  않고, 설계 #1 §3.2의 "자기 자신 `tos.*`" 허용 조항이 이를 커버한다. `tos.liveauth → tos.authority`·
  `tos.liveauth → tos.time`은 firewall-clean이며, "두 번째 sibling→sibling edge" 표현은 **설계
  규율상의 결합-최소화 주석**(운영자 판단 지점)이지 하드 firewall 규칙이 아니다(§10.2).

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 위치 = 전용 `tos/src/tos/liveauth/`.** 설계 #1 §2.1(line 117–118)이 **"Live
Authorization"을 IMPLEMENTATION-PLAN §2의 9개 코어 중 하나**로 명시 열거한다(Safety Authority가
`tos/src/tos/authority/`를 얻은 것과 동일 근거). `authority`(ADR-002-003)와 **다른 ADR·다른 acceptance
시리즈(REARM-AC ≠ SA-AC)·다른 EV 패밀리(REARM-EV ≠ SA-EV)**이므로 별도 top-level 패키지가 정당하다.
naming(`liveauth`)은 load-bearing이 아니다(설계 #1 line 164 원칙) — 운영자 치환 가능; **load-bearing은
layering**(liveauth → authority·time·ordering·canonical 한 방향; rcl·capsule·evidence·dsl과 형제,
scalar만). 대안 명(`live_authorization`·`authorization`·`livegov`)은 verbose 또는 `authority`와 혼동
위험; `liveauth`는 terse + ADR 제목("Live Authorization") 정합 + `authority`와 비충돌.

**(b) `tos.authority` import — 본 시리즈 두 번째 sibling→sibling edge(§3.5 상술).** ADR-002-007은
ADR-002-003의 **하류 소비자**다: §9 continuous-validity가 "Safety Authority epoch and currentness are
valid"(line 260)·"no dominating `CONTAINED` or `HALTED` state"(line 275)를 요구하고, §12 re-arm은
authority의 re-arm 전제(current epoch 확립·stale fence·§17.1 checklist)를 전제하며, §16 final egress는
Transmission Capability(authority.SafetyAuthorityCapability)를 검사한다. **결정: liveauth는
`tos.authority`를 import해 그 술어들 위에 compose한다.** 대안 비교(#6 §0.4b 형식):
- **대안 A — authority 술어 재저작**: 기각. `authority_epoch_current`·`restrictive_dominates`·
  `rearm_gate`를 liveauth에 **중복**하면 DRY 위반(CLAUDE.md) + **#6 REJECT가 강제한 안전 수정을 재복제**
  해야 한다 — M1 claimant-parameterized `lease_scope_exclusive`, M2 type-gated `permissive_capability_valid`
  조건4, v1.2 부등호 전치 에라타(`predicates.py` line 616). 재저작은 이 세 수정을 liveauth가 재현할
  의무를 지고 drift 위험을 진다. #6 §0.4b "재저작 = DRY + 안전-수정 중복"의 구체 사례화.
- **대안 C — injected-boolean scalar(no import)**: liveauth가 `epoch_current: bool`·`rearm_armable:
  bool`·`no_dominating_restriction: bool`을 주입받음. 기각(주요) — 이는 시리즈가 봉합해온 injected-boolean
  seam(Time MEDIUM-2·#6 M1/M2)을 **재개방**한다: 잘못된 `rearm_armable=True` 주입이 14항 checklist가
  실제로 통과하지 않았는데도 Live Authorization을 발행시킨다(리뷰어가 정확히 hunt하는 fail-open).
- **대안 B — authority 술어를 core로 PROMOTE**: 기각. `authority_epoch_current`·`rearm_gate`·
  `restrictive_dominates`는 `AuthorityEpochState`·`RearmChecklist`·`AuthorityState`/`PRECEDENCE_RANK`
  (authority 도메인)에 본질적으로 결부돼 있어, core로 옮기면 `tos.authority`를 hollow-out한다(clean
  shared-atom PROMOTE가 아님 — ordering/classify/IndependentIdArtifact와 다름). #6이 time 술어 PROMOTE를
  기각한 것과 동일 근거.
- **선택(A/B/C 모두 기각) — import-and-compose**: `tos.liveauth → tos.authority`. 근거: (i) ADR 의존
  방향 정합 — ADR-002-007 Depends-On ADR-002-003; liveauth가 authority의 하류 소비자다. (ii) seam 봉합 —
  continuous-validity·re-arm 술어가 `authority_epoch_current`·`restrictive_dominates`·`rearm_gate`를
  **내부 호출**해 injected-boolean seam 부재(#6 M1/M2 방침 계승). (iii) acyclic — authority는 liveauth를
  전혀 참조하지 않으므로(authority가 먼저 구현됨; ADR-002-003 ⊅ ADR-002-007) `liveauth → authority →
  time → {ordering, canonical}` 단방향. (iv) 좌표 비붕괴 유지 — liveauth는 authority의
  `safety_authority_epoch` 좌표를 `authority_epoch_current`로 소비하되, Live Authorization identity·
  revocation generation은 **별개 좌표**이며 결코 epoch에 붕괴시키지 않는다(§4.4). **firewall 허용**:
  `.importlinter`는 forbidden 계약뿐(§0.3), intra-tos edge 무제한; 설계 #1 §3.2 `tos.*` 자기참조 허용.
  단 **두 번째 sibling→sibling edge**이므로 운영자 판단 지점(§10.2). Fallback: 운영자가 cross-sibling
  edge를 더 늘리길 원치 않으면 대안 C(주입 scalar)로 후퇴하되, continuous-validity 술어가 seam-봉합
  wrapper를 별도 요구(그때까지 미확정 — 비권장).

**(c) `tos.time` 직접 import(authority 경유 아님) — diamond acyclic(§3.4).** §9(line 261)의 "Time is
`TRUSTED` under ADR-002-008"와 authorization freshness는 `tos.time`의 **TRUSTED/freshness 술어**를 쓴다.
authority는 `tos.time`에서 `HealthState`·`TimeContinuityIdentity`·`anchor_valid`·`conservative_usable_
lifetime`(lease 유효성용)만 import하며 `state_permits_new_normal_risk`·`snapshot_age_admissible`(liveauth가
필요한 TRUSTED/authorization-freshness)를 **re-export하지 않는다**. ⇒ **결정: liveauth가 `tos.time`을
직접 import한다**(authority 경유 강제 시 authority가 자신이 안 쓰는 time 술어를 re-export해야 함).
근거: ADR-002-007 Depends-On ADR-002-008(line 11) 직접 정합; diamond `liveauth → {authority, time}` +
`authority → time`은 **acyclic**(time은 어느 쪽도 참조 안 함 — cycle 아님). `tos.time`·`tos.authority`
둘 다 §7.1 import-closure의 **허용 대상**으로 기록.

**(d) canonical REUSE + `id=f(digest)` 미채택 + PROMOTE 0건.** Live Authorization ledger 시민(Live
Authorization·authorization-transition·re-arm-approval)은 `tos.canonical.DigestBoundArtifact`(digest 검증)와
**이미 core인 `IndependentIdArtifact`**(id⊥digest; `tos.canonical._base` line 328–362 — #6 §0.4c에서
rcl+dsl→canonical PROMOTE 완료)를 REUSE한다. **본 문서는 신규 PROMOTE가 없다** — #6이 이미 core로 올려둔
대칭 쌍을 그대로 상속하며, `tos.liveauth._base`는 authority/rcl/dsl과 동형의 **thin re-export shim**
(형제 import edge 없음)이다. **`id=f(digest)`(`IdDerivedArtifact`) 미채택** 근거: REARM-AC-004(line 619)
fresh-identity + §8.3(line 250–252) non-revival + replay/forgery 탐지 — same-authorization-id/diff-bytes
(위조·재제출된 authorization)를 `classify_record_pair`로 `CRITICAL_CONFLICT`로 탐지하려면 id⊥digest여야
한다(id=f(digest)면 re-arm이 새 content에서 새 id를 자동 파생해 same-id/diff-bytes가 unreachable —
탐지 불능). 설계 #4·#5·#6 §3.1과 완전 동형(capsule content-addressed와 정반대).

**(e) 경계 대 `tos.authority` — REUSE vs ADD vs scalar-reference(중심 결정).** ADR-002-003 §17이 re-arm
전제를 정의하고 #6이 `rearm_gate`(14항 checklist)를 구현했다. ADR-002-007이 그 위에 **genuinely 추가**하는
것을 정확히 구분한다:
- **REUSE**: `rearm_gate`+`RearmChecklist`+`RearmVerdict`(re-arm 전제 substrate — **SoD 재유도 금지**; quorum
  경로는 `rearm_gate(...).armable`을 직접 소비, variant 경로 규칙은 §6.4/M1), `authority_epoch_current`(§9 epoch
  currentness), `restrictive_dominates`+`PRECEDENCE_RANK`+`AuthorityState`(§9 dominating state·§17 HALT
  precedence), `halt_denies`(§17 HALT가 risk-increasing/re-arm/limit-activation 거부), `permissive_capability_
  valid`(§16 Transmission Capability = per-action 층), `SafetyAuthorityCapability`+`CapabilityType.{REARM,
  LIMIT_ACTIVATION, NORMAL_RISK_INCREASING}`(re-arm/limit 활성/risk-increasing capability type).
- **ADD(ADR-002-007 고유)**: **Live Authorization 아티팩트 자체**(scoped·fresh-identity·time-bounded·
  non-transferable — §4.5/§7/§8; authority.rearm_gate item 13 "fresh_live_authorization_issued"는 단지
  bool이나 liveauth가 실제 artifact+lifecycle+fresh-identity를 저작); **limit governance layering**(§6.1
  per-action ≤ LiveAuth ≤ RuntimeProfile ≤ HardEnvelope); **§13 two-lawful-paths dual control** — **authority.
  rearm_gate의 SoD는 strict-distinct-only**(`predicates.py` line 771–775: `limit_enlarger_principal !=
  armer_principal`, SAFE-053 variant 미모델)이므로 SAFE-053 Governed Single-Operator Re-Arm Variant 경로는
  liveauth가 저작한다(§6.3); **continuous validity**(§9); **partial/staged re-arm scope narrowing**(§14);
  **§14.1 delta-proportional in-place expansion**(delta용 새 authorization); **default-non-live**(§1).
- **scalar-reference(tos 미소유)**: Hard Safety Envelope·Runtime Safety Profile(ADR-002-014), Recovery
  Readiness Decision·Recovery Evidence Package(ADR-002-017), Decision Context Capsule(ADR-002-018), RCL
  capacity(reservation/pool/lease). id+version+generation+digest scalar만 담고 클래스 미import.

  **re-arm 경계 세부(핵심 난제, M1 확정 설계)**: `authority.RearmVerdict`(`state.py:163–174`)는 `armable` +
  `authority_effect`만 노출하고 **14전제 결과와 SoD를 분해하지 못한다**; `rearm_gate`는 `armable = all_
  prerequisites AND separation_of_duties`(strict `!=`, `predicates.py:768–779`)로 계산한다. ⇒ single-operator
  variant(enlarger==armer가 *합법*)는 `armable`이 반드시 False이고, authority로부터 14항 신호를 얻는 길은
  (a) 합성 distinct principal 주입(authority SA-INV-014 **스푸핑**) 또는 (b) liveauth에서 14항 재표현뿐 —
  **제3의 길은 없다**. 게다가 ADR-002-015 §17.1.3(line 476–483)은 attestation이 "non-authorizing precondition
  gate, **not the second principal**"이라 명시하므로 solo variant에는 **애초에 두 번째 principal이 없다** —
  합성 principal compose는 스푸핑이자 SAFE-053 의미 왜곡이다. **확정(reviewer 권고 채택)**: **quorum 경로**는
  `authority.rearm_gate(...).armable`을 **그대로 직접 소비**(strict SoD = quorum SoD, 미완화·미변경). **variant
  경로만** liveauth가 14 환경 전제를 **로컬 재표현**하고, `authority._REARM_PREREQUISITES`(`predicates.py:96–111`)
  와 **item-for-item 일치**를 강제하는 **drift 회귀 테스트**(§7 하네스)로 두 목록의 silent divergence를 차단한다.
  규칙은 "**SoD 재유도 금지**"(SoD 로직은 §6.3 two-lawful-paths가 소유) + "14 환경 항목은 variant 경로에서만
  재표현하되 drift 테스트로 authority와 동기". "second-effective-principal compose" 표현은 **폐기**(스푸핑으로만
  실현 가능). 더 깨끗한 장기 대안 — #6 `RearmVerdict`에 `all_prerequisites`를 별도 노출하도록 **미래 #6 개정** —
  은 §9.1에 의존성 관찰로 기록(지금은 #6가 ratified+implemented라 미채택; **결정 아님**). **[운영자 판단 지점:
  variant-path 로컬 재표현 + drift 회귀 테스트(**확정 채택**) vs 미래 #6 `RearmVerdict.all_prerequisites` 노출
  확장(운영자 선호/veto 대상)]**(§10.2). 재저작(대안 A)·injected-boolean(대안 C) 기각은 §0.4b대로 유지.

**(f) `writer_fenced`·`tos.rcl` 미재사용 · `tos.capsule`/`tos.evidence`/`tos.dsl` 미import(형제).** RCL의
capacity fence·`ProtectiveLease`·`partition_verdict`는 capacity 좌표계다; liveauth는 authorization 좌표계이며
RCL capacity를 scalar 참조만 한다(#6 §0.4d 상속 — `ProtectiveLease.safety_authority_epoch_binding` scalar
선례가 방향 확정). Decision Context Capsule(ADR-002-018)은 scalar 참조(§9 265 continuous-validity 전제 flag).
all-false 블록(§4.1 `LiveAuthorizationEffect`)은 각 패키지 로컬 재표현 규칙(capsule/time/evidence/rcl/dsl/
authority 전부 로컬, flag 이름 상이 — #6 §3.3)대로 **liveauth-local**(PROMOTE 아님). §7.1 import-closure가
`tos.rcl`·`tos.capsule`·`tos.evidence`·`tos.dsl` 부재를 assert.

**(g) 불변식 명명 규약 — INV 시리즈 창작 금지.** **실측(grep)**: ADR-002-007은 **INV 시리즈를 정의하지
않는다** — `REARM-AC-001..012`(§21 line 616–627)와 register `REARM-EV-001..012`만 가지며(§25 line 697에
관련 `SBR-EV-001..012` cross-reference), "LA-INV"·"REARM-INV" 등의 numbered invariant series는 **부재**다
(#6이 ADR-002-003의 `SA-INV-001..014`에 앵커한 것과 대비). ⇒ 본 계약은 모델 불변식·술어를 **`REARM-AC-001..012`
+ ADR-002-007 §-clause 번호**에 앵커하고, RFC-001 앵커는 ADR Depends-On line 11 + §23 traceability(line
645–659)가 할당한 **SAFE-xxx**(예: SAFE-003/004/011/044/045/046/047/048/050/051/052)를 인용한다. **새 INV
시리즈를 창작하지 않는다**(정확한 SAFE 본문은 RFC-001 소관 — 본 문서는 ADR이 선언한 앵커만 참조).

---

## 1. 범위 매핑 — ADR-002-007 조항별 EV-L1 도달성 (REARM-EV 0건 완결)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine exploration,
model checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**,
**EV-L3 = Integration/Adversarial**, **+Security/+Broker = 전용 fault injection**. Phase 1은 EV-L1만이다.

> **결정적 사실 — REARM-EV 0건 완결**: `REARM-EV-001..012`(ADR-002-007 acceptance)는 register 최소
> 레벨이 **전부 EV-L2 이상**이다(`EVIDENCE-REGISTER-002.csv` line 79–90 실측: `REARM-EV-012` = `EV-L2`,
> `-001/-004/-005/-010` = `EV-L3+Security`, `-002/-003/-006/-007/-008/-009/-011` = `EV-L3`; **EV-L1
> 최소 항목 0건**). ⇒ **Phase 1은 어떤 REARM-EV도 닫지 않는다**(Time "TIME-EV 0건"·#6 "SA-EV 0건"과
> **동형**). **코어 tier가 없다** — EV-L1 최소 행이 **0건**이라 분류는 **predicate-only / not-Phase-1
> 2분류**뿐이다. 모델은 각 항목의 **L1-decidable 술어 substrate**만 주장한다.

| REARM-EV | AC 제목 | register 최소(csv line) | Phase-1 분류 | Phase-1 EV-L1 substrate (닫지 않음) | ADR 근거 |
|---|---|---|---|---|---|
| **-001** | Default Non-Live | EV-L3+Security (79) | **predicate-only** | default-non-live 술어: authorization None/absent ⇒ not live; `is_live`는 `ACTIVE`+continuous-validity 요구(§8.1 issued≠active); startup/restart/failover/rollback 입력이 live 합성 불가(구성적 부재) | §1 (17), §15 (502–504), REARM-AC-001 (616) |
| -002 | Complete Re-arm Gate | EV-L3 (80) | **predicate-only** | full-gate 결합: §12 전제 중 하나 제거 ⇒ not admissible(**authority.rearm_gate 14항 REUSE-compose** + dual-control + fresh-auth) | §12 (397–418), REARM-AC-002 (617) |
| -003 | Automatic Re-arm Prevention | EV-L3 (81) | **predicate-only** | no-auto-rearm: health/timeout/reconciliation-complete/leader-election 입력이 armable 생성 불가(authority.rearm_gate SA-INV-013 REUSE + partition `automatic_rearm_denied=True`) | §1 (38), §17 (555), REARM-AC-003 (618) |
| **-004** | Fresh Authorization Identity | EV-L3+Security (82) | **predicate-only(강 substrate)** | fresh-identity: re-arm 새 authorization id ≠ prior; terminal(REVOKED/EXPIRED/SUSPENDED/SUPERSEDED/DENIED) ⇒ revive 불가; **classify_record_pair** same-id/diff-bytes ⇒ CRITICAL_CONFLICT(id⊥digest 보존) | §8.3 (250–252), §1 (42), REARM-AC-004 (619) |
| **-005** | Human Dual Control | EV-L3+Security (83) | **predicate-only** | **two-lawful-paths dual-control**: quorum(distinct principals) ∨ SAFE-053 variant(type-gated compensating controls); None principal ⇒ denied; same principal + variant 미완 ⇒ denied | §13 (424–435), §5 표 (124), REARM-AC-005 (620) |
| -006 | Atomic Safety Configuration | EV-L3 (84) | **predicate-only** | atomic-activation: partial/mixed-version profile ⇒ fail closed; **layering** per-action ≤ LiveAuth ≤ RuntimeProfile ≤ HardEnvelope | §6.4 (171–173), §6.1 (144–149), REARM-AC-006 (621) |
| -007 | UNKNOWN and Conservative Capacity | EV-L3 (85) | **predicate-only** | UNKNOWN-blocks: 미해결 order/exposure/external-activity(주입 flag None/True) ⇒ risk-increasing re-arm denied; capacity scalar 참조(보수적·불변) | §11 (389), §1 (44), REARM-AC-007 (622) |
| **-008** | Continuous Invalidation Bound | EV-L3 (86) | **predicate-only(강 substrate)** | continuous-validity 상실 ⇒ suspend/revoke; **restrictive generation 전진 ⇒ future 무효·비복원**(authority+time compose); bounds B_risk_increase_revoke+B_revocation_to_egress 주입(latency=런타임) | §9 (258–284), §10 (343–359), REARM-AC-008 (623) |
| -009 | Partial Re-arm Scope | EV-L3 (87) | **predicate-only** | partial-scope: 좁은 scope만; **subset semantics**(narrow는 wider 미포함; **empty ⇒ 아무것도 미포함**); broader fallback 금지; §14.1 delta ⇒ 새 authorization | §14 (441–454), §14.1 (456–496), REARM-AC-009 (624) |
| -010 | Final Egress Authorization Currentness | EV-L3+Security (88) | **not Phase-1** | egress+security: fenced claim-to-send은 런타임+broker; tos non-transmitting(firewall §4). (파생: liveauth는 egress가 소비하는 authorization identity/scope/version/revocation-generation **binding 술어**만 저작; 실제 fenced 전송 이연) | §16 (520–544), §9.4 (320–332), REARM-AC-010 (625) |
| -011 | HALT Restrictive Precedence | EV-L3 (89) | **predicate-only(강 substrate)** | HALT dominance: **authority.restrictive_dominates REUSE**(순서-무관 양방향); HALT가 risk-increasing/re-arm/limit-activation 거부(authority.halt_denies); B_halt_to_egress latency=런타임 | §17 (547–555), REARM-AC-011 (626) |
| **-012** | Authorization Evidence Replay | EV-L2 (90) | **predicate-only(최강 substrate)** | authorization/approval/transition 레코드 = DigestBoundArtifact(§18 audit 필드) + ordering; 결정적 replay substrate; classify_record_pair | §18 (559–576), REARM-AC-012 (627) |

**Phase-1 EV-L1 substrate 강도**: 가장 강한 것은 **-012**(register 최저 EV-L2; DigestBound+ordering 결정적
replay — #6 SA-EV-015 선례), **-004**(fresh-identity + classify_record_pair — id⊥digest 위조 탐지), **-008**
(continuous-invalidation — authority+time 술어 compose, restrictive-generation 비복원), **-011**(HALT dominance
— authority.restrictive_dominates 순서-무관 property REUSE)다.

**predicate-only(EV 주장 금지)** = {001, 002, 003, 004, 005, 006, 007, 008, 009, 011, 012} (11행).
**not-Phase-1** = {010(+Security final egress — tos non-transmitting)} (1행). **닫는 REARM-EV = 0건.**

> **완결 주장 규율(설계 #2 §7·#4 §7·Time §1·#5 §1·#6 §1 상속)**: Phase 1은 *모델 + property test 저작*
> 까지다. **어떤 항목도 "EV-L1-complete"로 주장하지 않는다** — REARM-EV는 최소 레벨이 전부 EV-L2 이상
> 이라 애초에 EV-L1으로 닫을 수 없다. 모든 주장에 규율 태그: **"EV-L1 predicate substrate only;
> REARM-EV-### remains NOT_IMPLEMENTED pending EV-L2/L3 (001/004/005/010 +Security) fault injection."**
> VER register의 Owner/Reviewer는 TBD이고 수용은 Independent-Safety-Reviewer(저자 아님)의 별도 서명
> (IMPLEMENTATION-PLAN §3)이다.

**ADR-002-007 조항 → 모델 산출물 매핑**: §1 default/four-artifacts → §4.1/§4.2·§2; §4 governed artifacts →
§2(Live Authorization 저작; envelope/profile/recovery/capsule scalar 참조); §5 SoD 표 → §6.3; §6 limit
governance → §6.1/§6.2; §7 Live Authorization claims → §2.2; §8 state model → §2.2·§5.4; §9 continuous
validity → §5.2(§9.1–§9.5 fenced protocol 런타임 이연); §10 invalidation → §5.2·§4.5; §11 recovery
readiness → §6.6(ADR-002-017 scalar 참조); §12 re-arm workflow → §6.4; §13 dual control → §6.3; §14
partial/staged → §6.5; §14.1 in-place expansion → §6.6; §15 startup → §4.2; §16 final egress → §4.1(경계)·
§5.2(binding 술어; 강제 이연); §17 halt → §6.7; §18 evidence → §2(covered 필드); §19 failure responses →
전 술어 fail-closed.

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True, extra="forbid")`,
`tos.canonical.FrozenModel` REUSE)로 저작한다. frozen은 authorization immutability(§7 "issue identity …
maximum validity")와 append-only(§18 audit)의 레코드 수준 실현이며, **모델에는 update/delete 연산이
존재하지 않는다**(설계 #4 §2.0 규율 상속). 필드명은 ADR §4(governed artifacts)·§7(claims)·§8(state)·§18
(audit)의 용어를 그대로 쓴다(스펙 용어 = 코드 용어, 설계 #1 §2.4).

### 2.0 소유권 골격 — liveauth는 authority·time의 하류-형제, safety-config/recovery/capsule/capacity는 scalar만

Live Authorization은 authority·time·capacity·recovery·safety-config·capsule의 **최상류 소비자**다.
ADR-002-007 §1(line 19–27)의 5-층 교집합 —

```text
Hard Safety Envelope ∩ Validated Runtime Safety Profile ∩ Current Live Authorization
    ∩ Current Safety Authority / Transmission Capability ∩ Current reconciled economic/operational state
```

— 에서 liveauth가 **소유·저작하는 것은 Live Authorization 층뿐**이고, 나머지 4층은 REUSE(authority
Transmission Capability) 또는 scalar 참조(Hard Envelope·Runtime Profile=ADR-002-014; reconciled state=
runtime injected flag)다. §1 line 29 "The most restrictive applicable scope and limit always governs"·
"No lower layer may expand a higher layer"는 **layering 술어**(§6.1)가 실현한다. ⇒ liveauth 모델은:

- Hard Safety Envelope·Runtime Safety Profile을 **scalar 참조 블록**으로만 담는다(`hard_safety_envelope_
  version`·`_generation`·`_digest`·`runtime_safety_profile_version`·`_generation`·`_digest` — 문자열/정수;
  **ADR-002-014 소유, `tos` 미저작**). 프로파일 scope 블록(profile line 27–34: `hard_safety_envelope_id/
  version/generation/digest`, `runtime_safety_profile_*` 전부 TBD/null)이 이 scalar 참조가 Phase-0까지
  미확정임을 확인한다.
- Recovery Readiness Decision·Recovery Evidence Package(ADR-002-017)를 **scalar 참조**(`recovery_readiness_
  decision_id`·`recovery_generation`·`recovery_evidence_package_id`·`_digest`)로 담는다. Decision Context
  Capsule(ADR-002-018)도 scalar 참조(`decision_context_capsule_id`·`context_generation`·`_digest`).
- RCL capacity(reservation/protective pool/capacity-lease)를 **scalar 참조**만(`reservation_identity`·
  `reservation_revision`·`protective_pool_identity` — #6 §2.0 동형; `tos.rcl` 미import).
- Transmission Capability은 **authority.SafetyAuthorityCapability REUSE**(§16 final egress = per-action
  층; liveauth 미저작).
- Time Health Snapshot을 scalar 참조(`trustworthy_time_snapshot_id`·`time_health_generation`); 단
  authorization freshness *계산*에 필요한 monotonic 좌표 타입·TRUSTED/freshness 술어는 `tos.time` import
  (§3.4) — snapshot 참조(scalar)와 freshness-계산(import)은 별개다.

### 2.1 digest-bound / plain-frozen / reference 분류 (총괄)

| 아티팩트 | 종류 | id 필드(독립) | digest 필드 | covered = ? |
|---|---|---|---|---|
| Live Authorization (§4.5; §7 line 186–214) | **DigestBoundArtifact + 독립 id** | `authorization_id`(+`authorization_version`) | `canonical_digest` | §7 immutable claims(§2.2) |
| Live Authorization Transition Record (§8 line 224–252; §18 line 566) | **DigestBoundArtifact + 독립 id** | `transition_id` | `canonical_digest` | authorization_id·from/to state·reason·restrictive/revocation generation·evidence(§2.3) |
| Re-arm Approval Record (§4.4 line 98–100; §13; §18) | **DigestBoundArtifact + 독립 id** | `approval_record_id` | `canonical_digest` | approver principals·requested scope·reason·residual-risk acks·evidence-package identity·dual-control path(§2.4) |
| Live Authorization Scope (§7 scope; §14) | **plain FrozenModel** | — | — | subset 좌표(§5.3 입력 — 7-dimension frozensets + numeric bound) |
| Limit Layering (§6.1 line 140–151) | **plain FrozenModel** | — | — | per-action/live-auth/runtime-profile/hard-envelope 한계 tuple + version scalar(§6.1) |
| Continuous Validity Inputs (§9 line 258–276) | **plain FrozenModel** | — | — | §5.2 입력(authority/time compose 좌표 + 주입 bool\|None conditions) |
| Dual Control Attestation + SAFE-053 Variant (§13) | **plain FrozenModel** | — | — | §6.3 입력(armer/approver principals + variant compensating controls) |
| In-Place Expansion Inputs (§14.1) | **plain FrozenModel** | — | — | §6.6 입력(delta scope·new-auth-id·proportional flags·dual-control·progressive gate·continuity-unbroken) |
| Re-arm Outcome (§12; `authority.RearmVerdict` non-authorizing 동형) | **plain FrozenModel** | — | — | §6.4 출력(`admissible: bool` + `authority_effect: LiveAuthorizationEffect` all-false) |
| Hard Envelope / Runtime Profile 참조 (ADR-002-014) | **plain FrozenModel(참조)** | id+version+generation+digest scalar | — | tos 미소유 |
| Recovery / Capsule 참조 (ADR-002-017/018) | **plain FrozenModel(참조)** | id+generation+digest scalar | — | tos 미소유 |
| RCL capacity 참조 블록 | **plain FrozenModel(참조)** | id+revision scalar | — | `tos.rcl` 미import |
| Transmission Capability (ADR-002-003) | **REUSE `tos.authority.SafetyAuthorityCapability`** | (authority 소유) | (authority) | authority 층(§16 per-action) |

> **IdDerivedArtifact 채택 아티팩트 = 0건. PROMOTE = 0건.** 모든 Live Authorization ledger 시민은
> **독립·서비스 할당 identity**를 가진다 — authorization identity·version(§7 line 189), issue sequence
> (line 211)는 content가 아니라 서비스 할당이고, REARM-AC-004(line 619)/§8.3(line 250–252) fresh-identity
> + replay 탐지가 same-id/diff-content 탐지를 요구하므로 `id⊥digest`여야 한다(id=f(digest)면 re-arm이
> 새 content에서 새 id를 자동 파생해 same-id/diff-bytes가 unreachable). ⇒ **전부 `IndependentIdArtifact`
> (이미 core, #6 PROMOTE 완료) 상속, `IdDerivedArtifact`(capsule 전용) 미채택**. `tos.liveauth._base`는
> authority/rcl/dsl 동형의 thin re-export shim(신규 PROMOTE·형제 edge 없음).

### 2.2 Live Authorization (§4.5 line 102–104; §7 line 186–220; §8 line 224–252)

`IndependentIdArtifact` 서브클래스, 독립 `authorization_id` + `authorization_version`. covered(Layer-1) =
§7(line 188–214)의 immutable claims:

- **식별·발행**: `issuer_identity`, `approval_record_identity`(→ §2.4 Re-arm Approval Record scalar),
  `issue_sequence`, `activation_condition`, `maximum_validity`(≡ authorization 자신의 validity interval —
  §9 line 282 "shall also remain within the artifact's own validity interval"; **누락 프로파일 키 §8**).
- **epoch·scope**: `authority_domain`, `safety_authority_epoch`(→ §5.2가 authority.authority_epoch_current로
  검사 — 좌표 비붕괴 §4.4), `live_authorization_scope`(→ §2.5 Scope; account/portfolio/strategy/
  instrument-class/broker/venue/session/order-type/action-class), `maximum_quantity_notional_risk_margin_
  concentration_rate_constraints`(→ §2.6 Limit Layering의 LiveAuth 층).
- **version 바인딩(scalar 참조)**: `hard_safety_envelope_version`, `runtime_safety_profile_version`,
  `broker_capability_profile_version`(+conformance class), `software_artifact_digest`,
  `configuration_digest`, `deployment_provenance`, `recovery_evidence_package_identity`+`recovery_generation`,
  `decision_context_capsule_identity`+`context_generation`(§7 line 202–210의 cross-ADR digest 다수는 scalar
  참조 블록으로 축약 — ADR-002-017/018/019/020/021/029/030 소유; **tos 미저작**). **ADR-002-019/020/021 (§9 line
  266–268) currentness 및 029/030 binding은 "for the exact order"·per-send 한정이라 continuous-validity(scope-
  level)가 아니라 final egress로 명시 이연**된다(REARM-EV-010 not-Phase-1; §5.2 Gap-1 — 묵시 부재 아님).
- **무효화·잔여**: `revocation_generation`(발행 시점 — §9 line 282), `residual_risk_approvals`,
  `restricted_scope_conditions`, `integrity_evidence`(구조만; MAC 검증 이연 — §16 egress security,
  REARM-EV-010 not-Phase-1). **mutable lifecycle state는 covered에 담지 않는다**(아래 좌표 비붕괴).
- `authority_effect` = all-false(§4.1 `LiveAuthorizationEffect`).

- **`authorization_id`·`authorization_version` ⊥ `canonical_digest`**(§3.1): §8.3 fresh-identity + replay
  위조 탐지. same authorization_id + diff bytes ⇒ `classify_record_pair` = CRITICAL_CONFLICT(REUSE core).
- **lifecycle state 좌표 비붕괴(핵심 설계 결정)**: `LiveAuthorizationState`(REQUESTED→VALIDATED→APPROVED→
  ISSUED→ACTIVE; terminal DENIED/SUSPENDED/REVOKED/EXPIRED/SUPERSEDED — §8 line 228–240 verbatim)는
  `tos.canonical.ArtifactStatus`(DRAFT/ISSUED/…)와 **별개 축**이다(§8 line 226 "an explicit lifecycle
  separate from the trading operating mode"). **Live Authorization 레코드는 immutable claims만 covered로
  담고 mutable lifecycle state(REQUESTED..terminal)는 담지 않는다** — 그래야 같은 authorization의 정당한
  상태 전이(ACTIVE→SUSPENDED)가 same-id/diff-bytes CRITICAL_CONFLICT로 **오탐되지 않는다**(정당 전이는
  digest를 바꾸지 않음). lifecycle 전이는 별도 §2.3 Transition Record가 append-only로 담는다. `is_live`/
  continuous-validity 술어는 *현재* state를 **주입 파라미터**로 받는다(§5.1/§5.4). 이름 충돌
  (ArtifactStatus.ISSUED/SUPERSEDED vs LiveAuthorizationState.ISSUED/SUPERSEDED)은 서로 다른 좌표이며
  vocabulary가 이를 별 enum으로 분리한다(§4.4 좌표 비붕괴).
- **`_REQUIRED_COVERED`**(ISSUED에서 concrete 필수): **구조적 식별·scope·epoch·version** 필드로 한정 —
  `issuer_identity`, `authority_domain`, `safety_authority_epoch`, `live_authorization_scope`,
  `hard_safety_envelope_version`, `runtime_safety_profile_version`, `broker_capability_profile_version`,
  `issue_sequence`, `activation_condition`. **numeric bound(`maximum_quantity_…_constraints`·`maximum_
  validity`)는 required로 넣지 않는다** — 프로파일 bound가 Phase-1에서 null/PROPOSED이므로 required면 모든
  authorization이 DRAFT로 떨어진다(Time §2.1·#5 §2.2·#6 §2.2 규율 상속). 대신 numeric claim 누락은
  **소비 술어(§5.2 continuous-validity·§6.1 layering)의 precondition에서 `None`⇒invalid**로 거부된다
  (§7 line 216 "Missing, empty, wildcarded, defaulted, stale, or conflicting Critical claims SHALL be
  denial"). 즉 `_REQUIRED_COVERED` 밖(ISSUED 도달성 보존)이되 **validity 술어가 소비 시점에 fail-closed**.
- **"no implicit open-ended scope"**(§7 line 218): `live_authorization_scope`는 wildcard/"all"/None을
  담을 수 없다 — §5.3 `scope_covers`가 wildcard/None ⇒ 미포함으로 거부한다(§5.3 canary).

### 2.3 Live Authorization Transition Record (§8 line 224–252; §18 line 566)

`IndependentIdArtifact`, 독립 `transition_id`. covered = §18(line 566 "every Live Authorization lifecycle
transition") audit 필드: `authorization_id`(참조), `from_state`·`to_state`(`LiveAuthorizationState`),
`transition_reason`, `restrictive_or_revocation_generation`(§9 line 282; §10), `evidence_reference`,
`operator_context`. append-only 시퀀스 원소(§18 audit — REARM-EV-012 replay substrate).

- **전이 legality는 §5.4 술어가 판정**(`live_authorization_transition_allowed(from, to)`) — §8(line
  228–240)의 arrow만 허용; terminal({DENIED,SUSPENDED,REVOKED,EXPIRED,SUPERSEDED})→ACTIVE 전이는 **모델이
  제공하지 않는다**(§8.3 line 250–252 "cannot return to `ACTIVE`"; 구성적 부재 = non-revival).
- **restrictive generation 단조**(§9 line 282 "Every restrictive authorization transition SHALL advance an
  authenticated, monotonically ordered revocation or restriction generation"): 전이 record의 generation은
  단조 증가만; 감소/재사용 연산 부재(#6 epoch 단조 동형). 실제 generation serialize는 런타임(§0.2).

### 2.4 Re-arm Approval Record (§4.4 line 98–100; §13 line 422–435)

`IndependentIdArtifact`, 독립 `approval_record_id`. covered = §4.4/§13 필드: `approver_principals`(tuple),
`requested_scope`(→ §2.5 Scope), `reason`, `residual_risk_acknowledgements`, `recovery_evidence_package_
identity`(scalar 참조), `decision_context_capsule_identity`(scalar 참조), `dual_control_path`
(`ReArmPathKind` = QUORUM ∨ GOVERNED_SINGLE_OPERATOR — §6.3). `authority_effect` = all-false(**approval ≠
authorization** — §11 readiness ≠ authority; §5 SoD 표 line 126 "Assemble recovery readiness … Prohibited:
Issuing Live Authorization or approving itself").

- **§13 line 431–432 "approvals SHALL be bound to the exact evidence package, versions, requested scope …;
  changed evidence or scope invalidates prior approvals"**: approval record는 evidence-package·capsule·scope
  를 covered로 바인딩하므로, 이들이 바뀌면 digest가 바뀌어 **새 record**가 되고 옛 approval은 소비 불가
  (§6.4가 approval↔authorization scope 일치를 검사). same-approval-id + diff scope ⇒ CRITICAL_CONFLICT.

### 2.5 Live Authorization Scope (§7 scope; §14) — subset 좌표

plain FrozenModel. `scope_covers`(§5.3) 좌표: `accounts: frozenset[str]`, `strategies`,
`instrument_classes`, `venues`, `sessions`, `order_types`, `action_classes`(7 dimension, 전부 frozenset)
+ `numeric_limits`(→ §2.6 Limit Layering LiveAuth 층). **frozenset 채택 근거**: subset(⊆) 판정이 자연스럽고
(§5.3), wildcard가 표현 불가하며(§7 line 218 no "all"), 빈 집합이 "아무것도 미포함"으로 명확하다(§5.3
vacuous-True 봉합). None dimension ⇒ §5.3에서 fail-closed.

### 2.6 Limit Layering (§6.1 line 140–151) — 4-층 한계

plain FrozenModel. 각 governed dimension(account/strategy/instrument/venue/order type/action class/quantity/
notional/risk vector/margin/concentration/rate/session/time — §6.1 line 151 verbatim)에 대해 4개 한계 tuple:
`per_action_limit`, `live_authorization_limit`, `runtime_safety_profile_limit`(scalar 참조 — ADR-002-014),
`hard_safety_envelope_limit`(scalar 참조 — ADR-002-014). + version scalar. `layering_within_bounds`(§6.1)의
입력. 값 null(Phase-1 프로파일 미승인) ⇒ **소비 술어에서 fail-closed**(§8).

### 2.7 Injected 술어 상태 모델 (plain FrozenModel — §5/§6 입력)

- **`ContinuousValidityInputs`**(§9 line 258–276): authority/time compose 좌표(`claimed_epoch`,
  `authority_domain`, `authority_epoch_state: AuthorityEpochState`, `currentness_witness: CurrentnessWitness`,
  `time_health_state: HealthState`, time-freshness 좌표, `dominating_state: AuthorityState`, `outstanding_
  capabilities`) + 주입 런타임 bool\|None conditions(`account_wide_reconciled`, `no_unknown_or_unattributed`,
  `rcl_capacity_consistent`, `hard_and_runtime_versions_match`, `broker_capability_sufficient`,
  `deployment_and_identity_digests_match`, `protective_coverage_valid`, `recovery_current`, `capsule_current`,
  `no_critical_alert_or_invalidation`). 임의 None/False ⇒ invalid(§5.2).
- **`DualControlAttestation`**(§13): `armer_principal: str|None`, `limit_change_approver_principal: str|None`,
  `distinct_approver_count: int|None`, `path: ReArmPathKind|None`, `variant: Safe053VariantAttestation|None`.
- **`Safe053VariantAttestation`**(§13 line 429; ADR-002-015 §17.1.1–§17.1.5): 7개 type-gated control —
  `variant_approved: bool|None`(§17.1.1 Pre-Approved Explicit Mode, line 463), `pre_declared_exact_scope:
  bool|None`(§17.1.1), `time_separated_reauthenticated_confirmation: bool|None`(**§17.1.2** Time-Separated
  Re-Authenticated Self-Approval — two-event cooling interval, line 467–474), `independent_nonauthorizing_
  attestation_current: bool|None`(**§17.1.3** mandatory Independent Non-Authorizing Attestation, line 476–483),
  `smallest_approved_scope_delta: bool|None`(§17.1.5 / ADR-002-025 §5.11), `hard_safety_envelope_not_expanded:
  bool|None`(§17.1.5), `non_waivable_boundary_preserved: bool|None`(§17.1.5). 임의 None/False ⇒ variant 경로
  미개방(§6.3 type-gate). **`variant_approved`는 §17.1.2/§17.1.3을 subsume하지 않는다** — 이 둘은 별개 주입
  attestation이며(§17.1.4 line 489가 solo config의 affirmative independence control로 명시), subsume하면 본
  시리즈가 봉합해온 coarse injected-boolean seam을 재생성한다. External Independent Reviewer 구성(§17.1.4 line
  487)은 **Path 1**(두 번째 effective principal 실재)로 처리하며 variant(Path 2)가 아니다(§6.3).
- **`InPlaceExpansionInputs`**(§14.1): `delta_scope: LiveAuthorizationScope`, `new_delta_authorization_id:
  str|None`, `existing_authorization_id: str|None`, `continuous_validity_unbroken: bool|None`, proportional
  flags(`account_reconciliation_for_added_scope`, `unknown_resolved_added`, `rcl_consistency_delta`,
  `capacity_reserved_for_delta`, `protective_coverage_added`, `envelope_profile_covers_enlarged`,
  `broker_capability_added`, `no_critical_alert_added`, `recovery_readiness_enlarged`, `capsule_enlarged` —
  전부 bool\|None), `dual_control: DualControlAttestation`, `progressive_promotion_gate_satisfied: bool|None`.
- **`ReArmOutcome`**(§6.4 출력): `admissible: bool`, `authority_effect: LiveAuthorizationEffect`(all-false).

---

## 3. canonical / ordering / time / authority REUSE 계약 (+ rcl/capsule/evidence/dsl 경계)

### 3.1 canonical REUSE + `id=f(digest)` 미채택 + PROMOTE 0건 (설계 #4·#5·#6 §3.1 상속)

Live Authorization ledger 시민(§2.1 표 상단 3종)은 `tos.canonical.DigestBoundArtifact`(digest 검증,
`_base.py` line 178–212)와 **이미 core인 `IndependentIdArtifact`**(`_base.py` line 328–362)의 "issued 시
concrete 독립 id" 검증을 REUSE한다. canonicalizer는 `EVL1ProvisionalCanonicalizer`(`ev-l1-provisional-0`)
REUSE, 신규 canonicalizer 없음(§8). **본 문서 PROMOTE = 0건**(#6이 IndependentIdArtifact를 rcl+dsl→canonical
으로 올려둠 — liveauth는 그대로 REUSE, `tos.liveauth._base`가 re-export shim). **`id=f(digest)` 미채택**
근거는 §0.4d·§2.1(§8.3 fresh-identity + replay 위조 탐지). `classify_record_pair`(core, `record_pair.py`
line 52–105)를 authorization/approval/transition 쌍에 적용해 `CRITICAL_CONFLICT`(위조/replay)·`IDEMPOTENT_DUP`
(정당 재관측)을 구분한다. null digest(DRAFT) ⇒ `NOT_COMPARABLE`로 false conflict 방지(REUSE 그대로).

### 3.2 ordering REUSE (§7 issue sequence · §8 lifecycle 순서)

liveauth는 authorization 발행 순서·lifecycle 전이 순서를 **신규 저작하지 않고** `tos.ordering`
(`_ordering.py`)의 `OrderingEvent`·`compare_order`를 REUSE한다(authority §3.2 동형):

- authorization `issue_sequence`(§7 line 211)를 `OrderingEvent.source_native_sequence`(same-issuer
  continuity)에 매핑. 발행자 continuity가 다르면 `compare_order`가 `AMBIGUOUS` 반환(교차-continuity 순서
  미생성).
- **wall clock은 순서를 만들지 않는다**(`_ordering.py`) — authorization 순서는 issue-sequence 정수 좌표이지
  시각이 아니다.

> **주의(리뷰어 선제)**: HALT dominance(§6.7)·restrictive precedence(REARM-AC-011)는 **`compare_order`에
> 의존하지 않는다** — authority.restrictive_dominates(순서-무관 우선순위)를 REUSE한다(#6 §5.3). ordering은
> 오직 same-issuer audit용. 두 개념을 섞지 않는다(Time MAJOR-1 좌표 혼동 방지 정신 계승).

### 3.3 `tos.rcl`·`tos.capsule`·`tos.evidence`·`tos.dsl` 경계 — 형제, scalar만, import 금지 (§0.4f)

이들은 **형제**다. liveauth는 재사용하지 않고 import하지 않는다:

- **`tos.rcl`**(capacity 측): RCL capacity(reservation/pool/lease)는 **scalar 참조**만(§2.0). §11 line 391
  "Recovery Coordinator, Live Authorization Service … SHALL NOT mutate or release capacity. The Risk Capacity
  Ledger remains the sole capacity serialization and mutation authority" — capacity≠authorization을 scalar
  경계로 실현(#5 §0.4d 상속).
- **`tos.capsule`**(ADR-002-018): Decision Context Capsule은 scalar 참조(§9 line 265 continuous-validity
  전제 flag `capsule_current`; §12 step 13 fresh capsule = injected flag). capsule 아티팩트는 tos.capsule
  소유.
- **`tos.evidence`**(ADR-002-016): §18 audit 레코드는 liveauth의 DigestBoundArtifact 시민으로 저작하되,
  evidence store append/ledger는 tos.evidence 소관(scalar 참조로 evidence receipt id만).
- **`tos.dsl`**: 무관(전략 DSL).

`tos.rcl`/`tos.capsule`/`tos.evidence`/`tos.dsl` import는 형제 규율 위반이므로 **금지**. §7.1 import-closure가
이들의 부재를 assert.

### 3.4 `tos.time` REUSE — 직접 import-and-compose (§0.4c)

authorization freshness·"Time TRUSTED"는 time-bounded이므로 liveauth는 `tos.time`을 **직접 import**해 다음
순수 술어·타입을 REUSE한다(재저작 금지 — DRY·안전):

| ADR-002-007 조항 | REUSE 대상(`tos.time`) | 근거 |
|---|---|---|
| §9 line 261 "Time is `TRUSTED`" | `state_permits_new_normal_risk(...)`·`HealthState.TRUSTED` | continuous-validity의 time 조건 — TRUSTED 아님/unknown ⇒ fail-closed |
| §9 line 262/282 "authorization validity and snapshot age … positively established" | `snapshot_age_admissible(...)`·`conservative_usable_lifetime(...)` | authorization freshness; **음수항 fail-closed 가드**(Time v1.2 REJECT 수정) 상속 |
| §7 line 211 "maximum validity" | `conservative_usable_lifetime` + 주입 `MAX_live_authorization_validity` bound(§8 누락 키) | authorization 자신의 validity interval — monotonic-bounded |
| §9 line 280 "cached `ACTIVE` … not sufficient" | (구조적) `is_live`가 issued/보유로부터 ACTIVE 미도출 | possession≠active(§4.1) |

- **compose로 seam 봉합**(Time MEDIUM-2·#6 계승): continuous-validity(§5.2)의 time 조건은
  `state_permits_new_normal_risk`·`snapshot_age_admissible`를 **내부 호출**해 injected-boolean seam을 두지
  않는다. 잘못된 `time_trusted=True` 주입 경로가 존재하지 않는다.
- **의존 방향**: `liveauth → time → {ordering, canonical}`(단방향); time은 liveauth를 참조하지 않는다.

### 3.5 `tos.authority` REUSE — 직접 import-and-compose (§0.4b/§0.4e; 두 번째 sibling→sibling edge)

liveauth는 authority 술어를 **신규 저작하지 않고** compose한다:

| ADR-002-007 조항 | REUSE 대상(`tos.authority`) | 근거 |
|---|---|---|
| §9 line 260 "Safety Authority epoch and currentness are valid" | `authority_epoch_current(...)`·`currentness_admissible(...)` | continuous-validity의 epoch/currentness 조건 |
| §9 line 275 "no dominating `CONTAINED` or `HALTED`" | `restrictive_dominates(current_state, outstanding)` | continuous-validity의 dominating-state 조건(순서-무관) |
| §17 line 551–553 HALT dominates / precedence | `restrictive_dominates`·`halt_denies`·`PRECEDENCE_RANK` | REARM-AC-011 restrictive precedence(§6.7) |
| §12 step 2 / **ADR-002-003** §17.1 re-arm 전제(14항) | `rearm_gate(checklist)`·`RearmChecklist`·`RearmVerdict` | REARM-AC-002 full gate substrate(§6.4) — quorum 직접 소비·**SoD 재유도 금지**(variant만 14항 로컬 재표현+drift 테스트, M1) |
| §16 line 524 Transmission Capability | `permissive_capability_valid(...)`·`SafetyAuthorityCapability` | final egress per-action 층(binding 술어만; 강제 이연) |
| §7/§12 REARM·LIMIT_ACTIVATION | `CapabilityType.{REARM, LIMIT_ACTIVATION, NORMAL_RISK_INCREASING}` | re-arm/limit-activation capability type |

- **compose로 seam 봉합**: continuous-validity·re-arm 술어가 authority 술어를 **내부 호출**한다 —
  `epoch_current: bool`·`rearm_armable: bool` 주입 seam 부재(대안 C 기각의 실체).
- **strict SoD 경계(핵심)**: authority.rearm_gate SoD는 strict-distinct-only(`predicates.py` line 771–775).
  §13 SAFE-053 two-lawful-paths는 liveauth가 ADD(§6.3) — quorum 경로만 authority.rearm_gate.armable로 직접
  소비하고(strict SoD = quorum SoD, 미완화), variant 경로는 14 환경 전제를 liveauth-local 재표현 + drift 회귀
  테스트로 확인(§6.4/M1 — 합성-principal compose 폐기, SoD 재유도 금지).
- **의존 방향·acyclic**: `liveauth → authority → time → {ordering, canonical}` + diamond `liveauth → time`.
  authority는 liveauth를 참조하지 않는다(ADR-002-003 ⊅ ADR-002-007). §7.1 import-closure가 `tos.authority`·
  `tos.time` **존재 허용**(두 sibling→sibling edge를 봉인이 아니라 한정).

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **fail-closed discipline**:
빈/누락 집합·None 좌표에 대한 술어는 절대 vacuous permit이 되지 않으며, permissive는 *양성 증명*을 요구하고,
각 가드에 **negative/canary property**(가드가 실제로 발화함)를 붙인다. 부등호는 **명시 정의된 순서** 위에서만
쓰고 방향을 이중검증한다(#6 v1.2 부등호 전치 에라타 교훈).

### 4.1 authorization ≠ enforcement (중앙 불변식 — §8.1; §1; §16)

설계 #4 evidence≠authority·#5 capacity≠authority·#6 authority≠enforcement의 **live-authorization 측
변주**다. 4개 층:

1. **발행·보유·서명 ≠ live**(§8.1 line 242–244 "`ACTIVE` means every continuous validity condition
   currently passes. It is not inferred from the artifact merely being issued"; §9 line 280 "A cached
   `ACTIVE` state is not sufficient proof"). 모델은 Live Authorization을 **보유/발행**하는 것으로부터 live를
   도출하는 경로를 **제공하지 않는다** — live는 오직 `is_live`(§5.1)=`ACTIVE state + continuous_validity`
   술어를 통해서만이고, 그조차 **필요조건**이지 완결이 아니다(조건 6 = §16 egress 독립검증은 런타임 — §0.2).
   **canary**: issued authorization + continuous-validity 미성립 ⇒ `is_live` False.
2. **모델은 non-transmitting·grants-no-runtime-effect**(all-false 블록): 모든 Live Authorization 아티팩트의
   `authority_effect` = `LiveAuthorizationEffect`(liveauth-local, §3.3 all-false-block 로컬 규칙), flag =
   `{is_live_by_possession, self_transmits, self_arms, self_activates, self_expands_scope, self_revives}`
   전부 `False`; 하나라도 `True`면 **구성 실패**(설계 #6 `AuthorityEffect` 패턴 로컬 재표현 — `_base.py`
   line 80–95). 근거: §1 line 38 "No health signal, timeout, restart, failover … may automatically create
   any of these permissive artifacts"; §8.3 non-revival.
3. **loss of proof = loss of live**(§9 line 278 "Loss of any required predicate SHALL suspend or revoke
   new-risk authority"): 임의 continuous-validity 좌표 None/UNKNOWN ⇒ 거부. 전 술어 fail-closed. **canary**:
   빈 witness·None epoch·None reconciled-flag는 vacuous permit로 빠지지 않는다.
4. **approval/readiness ≠ authorization**(§5 표 line 126; §4.3 line 96 "grants no authority"): Re-arm
   Approval Record·Recovery Readiness scalar는 `authority_effect` all-false; re-arm outcome의 `admissible`은
   전제 충족일 뿐 authorization을 부여하지 않는다(§6.4). documentation/audit ≠ authorization(§18 line 576
   "Audit and replay do not substitute for enforcement").

### 4.2 default-non-live (REARM-AC-001; §1 line 17; §15)

"The default operational state of every TOS deployment SHALL be non-live"(§1 line 17). **zero-value/absence
케이스가 non-live**여야 한다: `is_live(authorization=None, ...)` ⇒ **False**(§5.1). 모델은 startup/restart/
failover/deployment/rollback 입력으로부터 live authority를 합성하는 연산을 **제공하지 않는다**(§15 line 502
"Cold start, warm restart, failover, rollback, scaling, or deployment SHALL default to non-live"; §15 line
504 "A replacement instance SHALL NOT inherit authority"; 구성적 부재). **canary**: `is_live(None) == False`;
어떤 재시작/복구 flag 조합도 authorization 없이는 live 불가.

### 4.3 non-revival + fresh-identity (REARM-AC-004; §8.3; §1 line 42)

- **terminal ⇒ ACTIVE 복귀 불가**(§8.3 line 250–252): `DENIED`/`SUSPENDED`/`REVOKED`/`EXPIRED`/`SUPERSEDED`
  authorization은 `ACTIVE`로 못 돌아간다 — `live_authorization_transition_allowed`(§5.4)가 terminal→ACTIVE를
  거부하고 모델은 revive 연산 부재(`authorization_revived_by_nothing`, 항상 True — authority/time/#5
  `recovery_generation_revives_nothing` 동형). **canary**: `(REVOKED, ACTIVE)`·`(EXPIRED, ACTIVE)` 전이
  False; generation N에서 무효화된 authorization은 N+1에도 revive 안 됨.
- **re-arm ⇒ 새 identity**(§1 line 42 "A revoked, expired, suspended, superseded, or stale authorization
  SHALL NOT be revived"; §8.3 "issues a new authorization identity"): `fresh_authorization_identity`(§5.5)는
  re-arm의 새 authorization_id ≠ 임의 prior authorization_id. same-id ⇒ False; classify_record_pair로
  same-id/diff-bytes ⇒ CRITICAL_CONFLICT. **canary**: prior id 재사용 ⇒ not fresh; id⊥digest이므로
  CRITICAL_CONFLICT reachable(id=f(digest)면 unreachable을 회귀로 고정).

### 4.4 좌표 비붕괴 상속 (#6 §4.7; §9; §10)

- **authorization identity ≠ safety_authority_epoch ≠ revocation-generation ≠ ArtifactStatus lifecycle**:
  continuous-validity(§5.2)는 authority.authority_epoch_current로 `safety_authority_epoch` **좌표만** 소비하며,
  Live Authorization identity·`revocation_generation`·`LiveAuthorizationState`·ArtifactStatus는 **각 독립
  좌표**다. 어느 두 좌표를 equal/substitutable로 다루는 연산은 모델에 **없다**(#6 GenerationVector 규율 상속;
  liveauth는 authority가 소유한 epoch 좌표를 *소비*하되 소유·fence하지 않는다 — authority 소관). **canary**:
  `safety_authority_epoch` 자리에 `revocation_generation` 값을 넣어도 continuous-validity를 만족시키지 못한다.
- **broker-agnostic**: 어떤 좌표도 KIS 전용 아님.

### 4.5 restrictive-generation 전진 ≠ 경제효과 release (§10 line 359; §9 line 282)

"Revocation of future authority does not cancel orders, release capacity, or expire economic effect"(§10
line 359); §9 line 282 authorization expiry는 경제효과를 만료시키지 않는다(§9.4 line 331 "Capability expiry
or authority expiry after `SEND_STARTED` does not expire economic effect"). ⇒ 모델은 restrictive-generation
전진·authorization revoke/expire로부터 capacity release·order cancel·quantity erase를 도출하는 연산을
**제공하지 않는다**(구성적 부재; #5 no-expiry-of-economic-effect·#6 §4.2 동형, capacity 측은 RCL scalar).
**canary**: revoke/expire 후에도 참조된 potentially-live/UNKNOWN capacity scalar는 불변.

### 4.6 append-only + same-id/diff-bytes 충돌 (§18; §8.3)

- 모델에 update/delete 연산 부재(§2.0). authorization lifecycle 변화는 §2.3 Transition Record append로 표현
  (§2.2 lifecycle 좌표 비붕괴 — Live Authorization 자체는 immutable claims만 담아 정당 전이가 CRITICAL_CONFLICT로
  오탐되지 않음).
- **충돌 술어**(§3.1): `classify_record_pair`(core REUSE). same authorization/approval/transition identity +
  diff content ⇒ `CRITICAL_CONFLICT`(contain + 양쪽 보존, no merge — §8.3 replay/위조). same id + same bytes ⇒
  `IDEMPOTENT_DUP`. **canary**: id⊥digest이므로 CRITICAL_CONFLICT reachable.

---

## 5. Live Authorization validity / scope / freshness 술어 세부 (§7/§8/§9)

**핵심 난제**: 실제 egress·dual-control 인증·safety-config activation 없이, **주입 상태 + authority/time
compose 위 순수 술어**로 authorization validity를 fail-closed 모델링. 실제 강제(final egress·fenced claim·
dual-control 소비)는 런타임(§0.2).

### 5.1 default-non-live (REARM-AC-001; §1 line 17; §8.1)

`is_live(authorization: LiveAuthorization | None, current_state: LiveAuthorizationState | None, inputs:
ContinuousValidityInputs) -> bool`: 다음이 **모두** 성립할 때만 True — `authorization is not None`;
`current_state == LiveAuthorizationState.ACTIVE`; `continuous_validity(authorization, inputs) == True`.
`authorization is None`(absence — default) 또는 state ≠ ACTIVE 또는 continuous-validity 미성립 ⇒ **False**
(non-live). [REARM-AC-001; SAFE-045/046/047]

- **canary(fail-closed·zero-value)**: `is_live(None, ...) == False`(absence ⇒ non-live — default 케이스);
  `is_live(auth, ISSUED, ...) == False`(issued ≠ active — §8.1); `is_live(auth, ACTIVE, inputs)`는 continuous
  -validity가 실제 True일 때만 True(가드가 True로도 발화 — 존재성).

### 5.2 continuous validity — authority+time compose (§9 line 258–284)

`continuous_validity(authorization, inputs: ContinuousValidityInputs) -> bool`: §9의 조건 결합. EV-L1-decidable
조건은 **compose**(seam 봉합), 런타임 사실은 injected bool\|None(fail-closed):

- **compose(seam-sealed, EV-L1)**:
  1. `authority_epoch_current(inputs.claimed_epoch, inputs.authority_domain, inputs.authority_epoch_state)`
     **및** `currentness_admissible(inputs.currentness_witness)`(§9 line 260 — authority REUSE).
  2. `state_permits_new_normal_risk(inputs.time_health_state, ...)`(§9 line 261 Time TRUSTED — time REUSE;
     TRUSTED 아님/unknown ⇒ False).
  3. `not restrictive_dominates(inputs.dominating_state, inputs.outstanding_capabilities)`(§9 line 275 — no
     dominating CONTAINED/HALTED; authority REUSE, 순서-무관).
  4. authorization freshness(§9 line 262/282): `snapshot_age_admissible(...)` **및** `conservative_usable_
     lifetime(...) is not None`(주입 `MAX_live_authorization_validity` bound — §8 누락 키; time REUSE, 음수항
     fail-closed 상속).
- **injected bool\|None(런타임, None/False ⇒ False)**: `account_wide_reconciled`(§9 263), `recovery_current`
  (§9 264 — ADR-002-017), `capsule_current`(§9 265 — ADR-002-018), `no_unknown_or_unattributed`(§9 269),
  `rcl_capacity_consistent`(§9 270), `hard_and_runtime_versions_match`(§9 271 — ADR-002-014),
  `broker_capability_sufficient`(§9 272), `deployment_and_identity_digests_match`(§9 273), `protective_
  coverage_valid`(§9 274), `no_critical_alert_or_invalidation`(§9 276).
- **egress 조건 비주장 경계**(§9 line 280 "checked … independently at final broker egress"; §16): 술어 True는
  "continuous-validity 필요조건 충족"일 뿐 authorization 완결이 아니다(§4.1). 이 경계를 술어 docstring·
  property에 명시(overclaim 방지 — #6 §5.2 egress 경계 동형; REARM-EV-010 not-Phase-1).
- **per-order/egress-scoped 조건 명시 이연(Gap-1)**: §9 line 266–268의 ADR-002-019(Venue Constraint)·
  ADR-002-020(Order Construction)·ADR-002-021(Aggregate Risk) currentness 및 §7 line 202–210의 ADR-002-029
  (Release)·ADR-002-030(Post-Trade) binding은 전부 **"for the exact order"·per-send 한정**이므로 continuous-
  validity(scope-level)에 injected flag로 넣지 **않고** final egress(REARM-EV-010 not-Phase-1)로 **folded**한다 —
  **묵시적 부재가 아니라 명시적 이연**이다(§2.2). 비대칭 근거: 017(recovery)·018(capsule)은 **scope-level**
  전제라 `recovery_current`·`capsule_current` flag로 모델링하지만, 019/020/021/029/030은 **per-order** 라 개별
  주문 egress 시점 검증 대상이고 tos non-transmitting(§0.2)이 그 시점을 갖지 않는다.

- **canary**: 임의 injected 조건 None ⇒ invalid; epoch stale ⇒ invalid(compose); time not-TRUSTED ⇒ invalid;
  dominating HALT/CONTAIN ⇒ invalid; **all-but-one True ⇒ invalid**(각 조건 load-bearing). **restrictive-
  invalidation(REARM-AC-008)**: restrictive generation N 전진 ⇒ generation < N 참조 authorization invalid,
  이후 recovery generation이 revive 안 함(§4.3 `authorization_revived_by_nothing` compose). B_risk_increase_
  revoke/B_revocation_to_egress **latency는 런타임**(§8) — 모델은 무효화 *논리*(older-generation⇒invalid,
  단조)만.

### 5.3 subset scope coverage (REARM-AC-009; §7 line 216–218; §14)

`scope_covers(authorization_scope: LiveAuthorizationScope, requested: LiveAuthorizationScope) -> bool`(M-계열
vacuous-True 선제 봉합, #6 M1 동형): 다음이 **모든 7 dimension에서** 성립할 때만 True — (i) `authorization_
scope[dim]`·`requested[dim]` 둘 다 None 아님, (ii) `authorization_scope[dim]` **비어있지 않음**, (iii)
`requested[dim]` **비어있지 않음**, (iv) `requested[dim] ⊆ authorization_scope[dim]`. **빈 authorization scope ⇒
covers nothing(False); 빈 requested ⇒ 유효 action 아님(False); narrow authorization은 wider request 미포함
(⊄ ⇒ False); None/wildcard ⇒ False**. [REARM-AC-009; §7 line 218 no implicit "all"]

- **부등호/집합 방향 명시·이중검증(#6 v1.2 교훈)**: 정의된 순서 = **집합 포함 ⊆**(requested가 inner/narrow,
  authorization이 outer/wide). "narrow never covers wider" ⇒ `requested ⊆ authorization`이 **필수**(역방향
  아님). `∅ ⊆ ∅ = True`의 vacuous-True fail-open을 (ii)(iii) 비어있지-않음 요구로 **봉합**한다(#6 §6.1
  `lease_scope_exclusive` `0≤1` 봉합과 동일 defect class). **canary(양방향 발화)**: `scope_covers(∅_auth,
  nonempty_req) == False`(빈 authorization ⇒ 아무것도 미포함); `scope_covers(narrow, wide) == False`;
  `scope_covers(auth, ∅_req) == False`; `scope_covers(auth, subset) == True`(가드 True로도 발화); wildcard/
  None dimension ⇒ False.

### 5.4 lifecycle 전이 술어 (§8 line 224–252)

`live_authorization_transition_allowed(from_state: LiveAuthorizationState | None, to_state:
LiveAuthorizationState | None) -> bool`: §8(line 228–240)의 arrow만 True — `REQUESTED→VALIDATED→APPROVED→
ISSUED→ACTIVE`; `{REQUESTED,VALIDATED,APPROVED}→DENIED`; `{ISSUED,ACTIVE}→{SUSPENDED,REVOKED,EXPIRED,
SUPERSEDED}`. **terminal({DENIED,SUSPENDED,REVOKED,EXPIRED,SUPERSEDED})에서의 outgoing 전이 없음**(§8.3 —
특히 →ACTIVE 부재); None ⇒ False(fail-closed). [REARM-AC-004; §8.3]

- **canary**: `(REVOKED, ACTIVE)`·`(SUSPENDED, ACTIVE)`·`(EXPIRED, ACTIVE)`·`(SUPERSEDED, ACTIVE)`·
  `(DENIED, ACTIVE)` 전부 False(non-revival); `(ISSUED, ACTIVE)` True(정상); `(None, *)` False.

### 5.5 fresh authorization identity (REARM-AC-004; §8.3; §1 line 42)

`fresh_authorization_identity(new_authorization_id: str | None, prior_authorization_ids: frozenset[str]) ->
bool`: `new_authorization_id is not None` **및** `new_authorization_id not in prior_authorization_ids`일 때만
True. None 또는 prior 재사용 ⇒ False. 위조/replay 탐지는 `classify_record_pair`(same-id/diff-bytes ⇒
CRITICAL_CONFLICT — §4.6). [REARM-AC-004; §8.3 line 250–252]

- **canary**: `new_id ∈ prior ⇒ False`(prior 재사용 금지); `None ⇒ False`; 빈 prior 집합 + concrete new ⇒
  True(첫 authorization); id⊥digest이므로 same-id/diff-bytes CRITICAL_CONFLICT reachable.

---

## 6. limit governance · re-arm · SoD · §14.1 delta 술어 세부 (§6/§12/§13/§14)

### 6.1 limit layering 불변식 (REARM-AC-006; §6.1 line 140–151)

`layering_within_bounds(layering: LimitLayering) -> bool`: 각 governed dimension에서 **`per_action_limit ≤
live_authorization_limit ≤ runtime_safety_profile_limit ≤ hard_safety_envelope_limit`**(§6.1 line 144–149
verbatim)일 때만 True. 임의 한계 None ⇒ False(fail-closed — 미확립 한계는 소비 불가); 임의 inner > outer ⇒
False(§1 line 29 "No lower layer may expand a higher layer"). [REARM-AC-006; SAFE-003/004/050]

- **부등호 방향 명시·이중검증(#6 v1.2 교훈)**: 정의된 순서 = **한계 magnitude**(작을수록 tighter/더 제한적).
  per-action이 **가장 tight(최소 허용)**, Hard Envelope이 **가장 wide(최대 허용)**. ⇒ `per_action ≤ live_auth
  ≤ runtime_profile ≤ hard_envelope`(inner ≤ outer). ADR §6.1 line 145–149와 문자 그대로 대조 확인:
  "per-action authority ≤ Live Authorization ≤ Runtime Safety Profile ≤ Hard Safety Envelope". **canary(양방향)**:
  `live_auth > runtime_profile ⇒ False`(inner가 outer 초과 = 확장 시도); `hard_envelope < runtime_profile ⇒
  False`; 정상 사슬 ⇒ True; 임의 None ⇒ False.

### 6.2 atomic activation (REARM-AC-006; §6.4 line 171–173; §6.5 rollback)

`atomic_activation_ok(*, version_fully_active: bool | None, mixed_versions_present: bool | None, units_
compatible: bool | None, envelope_bounded: bool | None) -> bool`: **모두 양성**일 때만 True — `version_fully_
active is True` **및** `mixed_versions_present is False` **및** `units_compatible is True` **및** `envelope_
bounded is True`(§6.4 line 173 "Partial distribution, mixed versions, missing values, incompatible units, or
unverifiable activation state SHALL fail closed"). None/불안전 ⇒ False. **rollback(§6.5 line 175–177)**:
`authority_increasing_change`(§6.2)가 True면 full 승인 경로 요구 — rollback도 broader/incompatible이면
authority-increasing. [REARM-AC-006; SAFE-003/004/050]

- **canary**: `mixed_versions_present is None ⇒ False`(unknown ⇒ fail-closed); `version_fully_active is None ⇒
  False`; partial/mixed 조합 ⇒ False.

### 6.3 two-lawful-paths dual control (REARM-AC-005; §13 line 429; §5 표 line 124)

**핵심 난제(SAFE-053 표현)**: §13(line 429)은 "the principal who approves an authority-increasing limit change
SHALL NOT be the sole principal who arms that enlarged scope, **except through the approved Governed
Single-Operator Re-Arm Variant (ADR-002-015 §17.1) satisfying RFC-001 SAFE-053, whose compensating controls
substitute for the second effective principal**." authority.rearm_gate SoD는 strict-distinct-only이므로 이
two-lawful-paths는 liveauth가 저작한다.

`rearm_dual_control_satisfied(attestation: DualControlAttestation) -> bool`(type-gated disjunction — #6 M2
동형): 다음 **두 경로 중 하나**가 양성일 때만 True —

- **Path 1 (quorum)**: `attestation.limit_change_approver_principal is not None` **및** `attestation.armer_
  principal is not None` **및** `limit_change_approver_principal != armer_principal` **및** `distinct_approver_
  count >= 2`(두 자연인 — §13 line 428). [이 경로는 authority.rearm_gate.armable로 직접 소비 가능, §6.4]
- **Path 2 (Governed Single-Operator Re-Arm Variant, SAFE-053 — solo config 전용)**: `attestation.variant is
  not None` **및** variant의 **7개** control **모두** 양성 — `variant_approved is True`(§17.1.1) **및**
  `pre_declared_exact_scope is True`(§17.1.1) **및** `time_separated_reauthenticated_confirmation is True`
  (**§17.1.2** time-separation, line 467–474) **및** `independent_nonauthorizing_attestation_current is True`
  (**§17.1.3** attestation, line 476–483) **및** `smallest_approved_scope_delta is True`(§17.1.5) **및**
  `hard_safety_envelope_not_expanded is True`(§17.1.5) **및** `non_waivable_boundary_preserved is True`
  (§17.1.5). solo variant에는 두 번째 principal이 **없다** — §17.1.2 time-separation + §17.1.3 attestation이
  "compensating independence control"로 두 번째 principal의 *provenance*를 대신할 뿐(§17.1.4 line 489)이고,
  §17.1.3 attestation은 "non-authorizing precondition gate, **not the second principal**"(line 483)이다.
  **`variant_approved`는 §17.1.2/§17.1.3을 subsume하지 않는다**(별개 주입; subsume 시 coarse injected-boolean
  seam 재생성 — §2.7).
- **External Independent Reviewer 구성은 Path 1**(§17.1.4 line 487): recognized external reviewer는 **genuine
  second effective principal**이므로 Path 1의 distinct-principal 테스트를 충족하는 two-effective-principal
  quorum으로 평가하며 **Path 2가 아니다**. Path 2는 external reviewer가 없는 **solo** 구성 전용이다(§17.1.4
  line 485–489).

**두 경로 모두 실패 ⇒ False(fail-closed)**. [REARM-AC-005; SAFE-053; §13; §5 표 line 124; ADR-002-015 §17.1.1–§17.1.5]

- **type-gate(핵심 fail-open 봉합)**: Path 2는 variant가 present **이고** 모든 control이 양성 True일 때만
  개방된다 — variant None 또는 임의 control None/False면 single-operator 경로 **미개방**(그때는 Path 1만이
  유일한 lawful 경로이고 single operator는 Path 1 실패). #6 M2 type-gated disjunction(lease_ok는 DEGRADED_
  PROTECTIVE에서만 조건4 충족)과 동일 구조 — disjunction의 각 branch가 **양성 establish를 요구**해 "빈/None
  입력의 vacuous OR"가 되지 않는다.
- **canary(다방향 발화)**: `armer==approver ∧ variant=None ⇒ False`(single operator, variant 없음);
  `armer==approver ∧ variant 7 control 모두 True ⇒ True`(lawful solo variant 경로); `armer==approver ∧
  variant 임의 control(§17.1.2·§17.1.3 포함) None/False ⇒ False`(불완전 variant는 경로 미개방); `approver=None
  ∨ armer=None ⇒ False`(None principal ⇒ denied); 두 distinct principal + count≥2 ⇒ True(quorum·external-
  reviewer 구성 포함).

### 6.4 re-arm 소비 — quorum 직접 소비·variant 로컬 재표현 + fresh Live Authorization (REARM-AC-002/003; §12; ADR-002-003 §17.3)

`rearm_admissible(checklist: RearmChecklist, dual_control: DualControlAttestation, new_authorization_id: str
| None, prior_authorization_ids: frozenset[str], partition_control_plane_verifiable: bool | None) ->
ReArmOutcome`: §12 re-arm workflow의 EV-L1-decidable 결합. `admissible=True`는 다음이 **모두** 성립할 때만 —

1. **환경 전제(§12; M1 확정)**: **quorum 경로**는 `rearm_gate(checklist).armable`(14항 + strict SoD)을
   **그대로 직접 소비**. **variant 경로**는 solo config라 `rearm_gate.armable`이 반드시 False이므로(강제 `!=`,
   그리고 `RearmVerdict`가 14전제/SoD를 분해 못 함 — `state.py:163–174`/`predicates.py:768–779`), liveauth가
   **14 환경 전제만 로컬 재표현**하고 `authority._REARM_PREREQUISITES`(`predicates.py:96–111`)와 **item-for-item
   일치 drift 회귀 테스트**(§7)로 동기한다. SoD는 이 conjunction에서 **재유도하지 않고** §6.3 `rearm_dual_control_
   satisfied`가 소유한다. **규칙: SoD 재유도 금지**(합성 principal compose 폐기 — 스푸핑 + §17.1.3 "not the second
   principal" 위반); 14 환경 항목은 variant 경로에서만 재표현하되 drift 테스트로 authority와 불가분.
2. **dual control**: `rearm_dual_control_satisfied(dual_control) == True`(§6.3 two-lawful-paths).
3. **fresh Live Authorization**: `fresh_authorization_identity(new_authorization_id, prior_authorization_ids)
   == True`(**ADR-002-003 §17.3 line 678** "Re-arm SHALL issue new capabilities under the current epoch.
   Previously issued live capabilities are not revived"; **ADR-002-007 §1 line 42** "Re-arm always issues a
   new Live Authorization and new capabilities").
4. **no partition auto-rearm**: `partition_authority_verdict(partition_control_plane_verifiable).live_
   rearm_denied`가 **False**(= control-plane verifiable이 양성 True)일 때만 admissible 가능; unverifiable
   (None/False) ⇒ `live_rearm_denied=True` ⇒ admissible 불가(authority REUSE — §6.6).
   **[v1.2 에라타]** v1.1은 본 항의 게이트 필드를 `automatic_rearm_denied`로 오기했다 — 그 필드는
   authority 구현에서 **무조건 True**(quorum 복구≠auto-rearm의 문서화, authority `predicates.py` line 740)
   이므로 문면대로 게이트하면 admissible이 **항상 False**가 되어 전 re-arm이 차단된다(fail-open 아닌
   과잉제한이나 계약 오기). 올바른 게이트는 **`live_rearm_denied`**(verifiability 판정: None/False ⇒
   denied — fail-closed 유지). 구현이 올바른 필드를 사용·공개했고 독립 코드 리뷰가 확정했다(§10.1 v1.2).

`admissible=False`면 non-live 유지. **`ReArmOutcome.authority_effect` = all-false**(§4.1) — admissible=True도
**live authority를 부여하지 않는다**(§11 readiness≠authority; re-arm은 **ADR-002-007 §1(line 42)**대로 새 Live
Authorization을, **ADR-002-003 §17.3**대로 새 capability를 발행하는 별도 행위이고, 그 발행 자체가 §5.2
continuous-validity를 다시 통과). [REARM-AC-002; §12]

- **no-automatic-rearm(REARM-AC-003; §1 line 38; §17 line 555)**: `no_automatic_rearm(*, health_recovered,
  timeout_elapsed, reconciliation_completed, leader_elected, restart_completed) -> bool` = **항상 True**(이
  입력들 중 어느 것도 armable을 만들 수 없음 — 구성적: `rearm_admissible`이 이 flag들을 **읽지 않는다**;
  authority.rearm_gate SA-INV-013 REUSE + partition automatic_rearm_denied). **canary**: 모든 recovery/timeout/
  restart flag True여도 `rearm_admissible`은 checklist/dual-control/fresh-id만 보고 이들을 무시 ⇒ armable 불가;
  **all-but-one prerequisite True ⇒ not admissible**(각 전제 load-bearing).

### 6.5 partial / staged re-arm scope narrowing (REARM-AC-009; §14 line 441–454)

`partial_rearm_scope_narrows(prior_scope: LiveAuthorizationScope, new_scope: LiveAuthorizationScope) ->
bool`: 모든 dimension에서 `new_scope[dim] ⊆ prior_scope[dim]`(§14 line 442 "restore the smallest proven
scope"; line 447 "distinct Live Authorization identity and scope")일 때만 True. **broader fallback 금지**(§14
line 449 "prevent fallback to a broader prior scope"): 모델은 new_scope을 prior보다 넓히는 연산을 **제공하지
않는다**(frozen scope; 확장은 §14.1 새 authorization 요구). [REARM-AC-009; SAFE-046/047]

- **canary**: `new ⊄ prior ⇒ False`(broader fallback 금지); partial re-arm은 distinct authorization_id
  요구(§14 line 447 — `fresh_authorization_identity` compose); "success ≠ auto expansion"(§14 line 454 "Successful
  operation of a narrow scope is evidence for review, not automatic authorization for expansion") — 모델은
  success flag로부터 scope 확장을 도출하지 않는다(구성적 부재).
- **narrowing-to-empty(Gap-2)**: `new_scope = ∅`은 `∅ ⊆ prior`로 `partial_rearm_scope_narrows` True이며 이는
  **full de-authorization** 케이스다 — §5.3와 일관되게(빈 authorization은 아무것도 미포함) de-authorized scope는
  이후 어떤 action도 validate하지 않는다(`scope_covers(∅, *) == False`). narrowing-to-∅은 합법(scope 축소의
  극한)이되 그 결과 authorization은 non-permissive다.

### 6.6 §14.1 delta-proportional in-place expansion (§14.1 line 456–496)

`in_place_expansion_admissible(inputs: InPlaceExpansionInputs, existing_authorization: LiveAuthorization) ->
bool`: LIVE_RESTRICTED→LIVE_NORMAL in-place 확장의 §14.1 조건 결합. 다음이 **모두** 성립할 때만 True —

1. **continuous-validity unbroken(§14.1 line 492–496)**: `inputs.continuous_validity_unbroken == True` —
   깨졌으면 이 경로 **불가**(full §12 re-arm from non-live 요구; 술어 False 반환이 "full 경로로 가라" 신호).
2. **delta용 새 authorization(§14.1 item 1, line 463–465)**: `inputs.new_delta_authorization_id is not None`
   **및** `inputs.new_delta_authorization_id != inputs.existing_authorization_id` **및** `existing_
   authorization.authorization_id == inputs.existing_authorization_id`. **old authorization은 결코 확장되지
   않는다** — 모델은 existing authorization의 scope를 in-place 확장하는 연산을 **제공하지 않는다**(frozen;
   확장 = 새 authorization; §14.1 line 465 "scope expansion is never an automatic rollover or an in-place
   widening of the existing authorization").
3. **proportional re-establishment(§14.1 item 2, line 466–481)**: delta scope에 대한 모든 proportional flag
   양성 — `account_reconciliation_for_added_scope`, `unknown_resolved_added`, `rcl_consistency_delta`,
   `capacity_reserved_for_delta`, `protective_coverage_added`, `envelope_profile_covers_enlarged`, `broker_
   capability_added`, `no_critical_alert_added`, `recovery_readiness_enlarged`, `capsule_enlarged`(전부
   True; None/False ⇒ False).
4. **dual control 보존(§14.1 item 3, line 482–486; two effective principals)**: `rearm_dual_control_
   satisfied(inputs.dual_control) == True`(§6.3 — quorum ∨ SAFE-053 variant).
5. **progressive-promotion gate(§14.1 item 4, line 487–490)**: `inputs.progressive_promotion_gate_satisfied
   == True`(ADR-002-025 — success count/elapsed time/no-incident은 자동 확장 불가).

임의 None/False ⇒ **False**. [REARM-AC-009; §14.1; SAFE-046/047]

- **canary(핵심)**: `new_delta_authorization_id == existing_authorization_id ⇒ False`(old이 stretch 안 됨 —
  delta는 새 authorization); `continuous_validity_unbroken != True ⇒ False`(깨진 연속성 ⇒ full §12 경로);
  임의 proportional flag None ⇒ False; single operator + variant 미완 ⇒ False(§6.3); progressive gate None ⇒
  False. **old authorization scope in-place 확장 연산 부재**(구성적 — frozen).

### 6.7 HALT restrictive precedence (REARM-AC-011; §17 line 547–555)

`halt_dominates_authorization(dominating_state: AuthorityState, outstanding_capabilities, capability_type:
CapabilityType) -> bool`: authority REUSE 결합 — `restrictive_dominates(dominating_state, outstanding_
capabilities)`(§17 line 551 "HALT SHALL dominate outstanding permissive capabilities and Live Authorization";
순서-무관 양방향, #6 §5.3) **또는** `halt_denies(capability_type)`(HALT가 risk-increasing/re-arm/limit-
activation 거부). True ⇒ authorization/capability가 HALT에 지배됨(거부). [REARM-AC-011; §17; SAFE-042]

- **no blind cancel-all(§17 line 551)**: 모델은 HALT로부터 cancel-all을 도출하지 않는다(authority.halt_denies
  REUSE — cancel은 protective ownership + aggregate-risk = RCL 소관 scalar; 구성적 부재, #6 §5.5 동형).
- **canary(양방향, 순서-무관)**: HALT-먼저·permissive-먼저 **양 순서**로 주입 ⇒ 두 경우 모두 HALT dominates
  (§17 line 551 "HALT SHALL dominate outstanding permissive capabilities and Live Authorization"; §19 line 592
  halt-vs-transmission race "locally accepted HALT dominates later sends"; authority.restrictive_dominates가
  이미 순서-무관 보장 — REUSE로 상속). B_halt_to_egress **latency는 런타임**(§8).

---

## 7. property-test 하네스 타깃

§1의 EV-L1 분류에 정렬. **전부 predicate substrate이며 어떤 REARM-EV도 닫지 않는다**(§1 규율). property는
bound를 **hypothesis 생성 주입값**으로 다뤄 "임의 유효 bound 하 보수적 성립"을 검증(특정 값 비의존, 하드코딩
없음 — §8).

| family | Phase-1 타깃 | substrate / 근거 |
|---|---|---|
| Live Authorization canonicalization + digest 검증 | **REUSE 설계 #4 must-pass suite** (`tos.canonical`) | authorization/approval/transition covered로 재적용; frozen digest 일관성 |
| same-authorization-id/diff-bytes 충돌 + idempotency | **REUSE core `classify_record_pair`** | §4.6; REARM-EV-004/012 substrate |
| default-non-live (`is_live`) | **core 술어(강)** | §5.1; REARM-EV-001. `is_live(None)==False`(zero-value canary); issued≠active |
| continuous validity (authority+time compose) | **core 술어(강)** | §5.2; REARM-EV-008. epoch/time/dominance/freshness compose(injected-bool seam 부재); all-but-one⇒invalid; **egress 조건 비주장** |
| subset scope coverage | **술어** | §5.3; REARM-EV-009. **빈 auth⇒covers nothing, 빈 req⇒False, narrow⊅wide**(vacuous-True 봉합 — #6 M1 동형); wildcard/None⇒False |
| lifecycle 전이 (non-revival) | **술어** | §5.4; REARM-EV-004. terminal→ACTIVE⇒False; None⇒False |
| fresh authorization identity | **술어(강)** | §5.5; REARM-EV-004. prior 재사용⇒False; classify same-id/diff-bytes⇒CRITICAL_CONFLICT |
| limit layering 불변식 | **술어** | §6.1; REARM-EV-006. per-action ≤ … ≤ hard-envelope **부등호 방향 명시·이중검증**; inner>outer⇒False; None⇒False |
| atomic activation | **술어** | §6.2; REARM-EV-006. partial/mixed/None⇒fail-closed |
| two-lawful-paths dual control | **술어(강)** | §6.3; REARM-EV-005. **type-gated disjunction**(quorum/external-reviewer=Path 1 ∨ SAFE-053 solo variant=Path 2, **7 control** 모두 양성 incl. §17.1.2 time-separation/§17.1.3 attestation; `variant_approved` 미subsume); None principal⇒denied; variant 미완⇒경로 미개방 |
| re-arm 소비 (quorum 직접 소비·variant 로컬 재표현) | **core 술어(강)** | §6.4; REARM-EV-002/003. quorum=`rearm_gate(...).armable` 직접; variant=14 환경 로컬 재표현(**SoD 재유도 금지**); authority_effect all-false; all-but-one⇒not-admissible; no-auto-rearm(flag 무시) |
| re-arm prerequisite drift 회귀 (M1) | **회귀 테스트** | §6.4/M1. liveauth variant 14항 목록 == `authority._REARM_PREREQUISITES`(`predicates.py:96–111`) item-for-item assert; silent divergence 차단 |
| partial re-arm scope narrowing | **술어** | §6.5; REARM-EV-009. new⊆prior; broader fallback 부재; success≠auto-expansion |
| §14.1 delta in-place expansion | **술어(강)** | §6.6; REARM-EV-009. **delta≠existing id**(old 미확장); continuity-unbroken 아니면 full-§12; proportional/dual-control/progressive 전부 True |
| HALT restrictive precedence | **술어(강)** | §6.7; REARM-EV-011. authority.restrictive_dominates REUSE(순서-무관 양방향); halt_denies; no blind cancel-all |
| authorization≠enforcement (flag 불변식 + 거부 술어) | **flag 불변식 + 거부 술어** | §4.1; REARM-EV-001/010. authority_effect all-false; possession≠active; approval≠authorization |
| non-revival + restrictive-gen≠release | **flag 불변식 + 술어** | §4.3/§4.5; REARM-EV-004/008. revive 연산 부재; revoke/expire≠경제효과 release |

- **core(술어) 강도**: -012·-004(replay/fresh-identity)·-008(continuous-invalidation compose)·-011(HALT
  dominance REUSE)이 가장 강함. **전부 predicate substrate — "EV-L1-complete 주장 금지"**(§1).

### 7.1 import-closure 검증 테스트 (C1 강제 — 설계 #4 §7.1·#6 §7.1 확장)

서브프로세스에서 `import tos.liveauth`(및 `tos.authority`·`tos.time`·`tos.ordering`·`tos.canonical`)만 한 뒤
`sys.modules`를 검사해 assert: (1) 설계 #1 §2.3 금지 패키지 부재; (2) **`shared.config`·`shared.config.secrets`
부재**(전이 유입 런타임 포착); (3) `os.environ`/`os.getenv` 미참조; (4) **`numpy`·`pandas`·`yaml`(pyyaml)
부재**(bound는 주입·YAML은 하네스 소관, §0.3); (5) **`tos.rcl`·`tos.capsule`·`tos.evidence`·`tos.dsl` 부재**
(§3.3 layering — liveauth는 이들의 형제; capacity/capsule/recovery/config 참조는 scalar/술어 REUSE로만); (6)
**`tos.authority`·`tos.time`·`tos.ordering`·`tos.canonical` 존재 허용**(§3.4/§3.5 두 sibling→sibling edge를
명시적으로 허용 대상으로 기록 — import-closure가 이 edge를 *봉인*하지 않고 *한정*한다). required check
(`tos-firewall`)와 함께 green이어야 §0.3 준수 선언이 능동 성립한다.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

liveauth 전용 run-manifest 템플릿은 없으므로 설계 #1 §5.1 규율을 REUSE한다. evidence를 산출하는 모든
property-test run은 다음을 기록: (1) git commit digest + `tos` 버전; (2) 인터프리터 + 고정 의존성 버전
(pydantic/hypothesis); (3) 실행 환경; (4) 하네스 git digest; (5) **property-test seed**(hypothesis seed/
derandomize, append-only); (6) **소비 설정 아티팩트 digest**(주입 authorization/layering/dual-control bounds
프로파일 + `canonicalization_version` + `tos.ordering`·`tos.time`·**`tos.authority`** primitive 버전);
(7) 산출 아티팩트 sha256. (VER-002-001 §2.3 재현성·§3 baseline·§9.1 seed·§9.2 digest의 EV-L1 부분집합.)

---

## 8. bounds 주입 + 누락 프로파일 키 Phase-0

`VERIFICATION-PROFILE-002.yaml`은 전체 `status: PROPOSED`·`approved_by: []`·`effective_from: null`(line
16–20; 배너 line 3–5 "an unapproved or placeholder bound is not an approved bound"). ADR-002-007 §24(line
662–677)·§25(line 699)는 numeric bound·authorization duration·context/readiness age·invalidation bound를
승인 프로파일 소관으로 못박는다.

- **결정**: 모든 bound(authorization maximum-validity·revocation-to-egress·halt-to-egress·capability-age·
  readiness-age 등)는 **주입 policy 파라미터**로만 모델에 들어온다. **어떤 숫자도 하드코딩하지 않는다**
  (CLAUDE.md 설정 기반). 값 누락 ⇒ `UNKNOWN` ⇒ fail-closed(§5·§6). property는 bound를 hypothesis 생성
  주입값으로 다룬다(§7).

- **실측 확인(evidence-based) — 프로파일에 존재하는 REARM-관련 키**(grep):
  - `B_risk_increase_revoke`(line 128) / `B_revocation_to_egress`(135, rationale가 **ADR-002-007 §§9,16**
    직접 인용) / `B_halt_to_egress`(142): REARM-AC-008/011 latency(런타임 egress).
  - `B_capability_claim_to_send`(163, rationale **ADR-002-007 §§9.4-9.5** 인용) / `B_egress_hard_fence`(170):
    §9.4 fenced claim-to-send·hard fence — **런타임+broker+security**(REARM-EV-010 not-Phase-1).
  - `MAX_normal_capability_age_ms`(697): `1000` / PROPOSED — §9.2/§16 Transmission Capability freshness
    (authority 층 — #6가 이미 사용; 재계상 없음).
  - `MAX_recovery_readiness_age_ms`(708): `null` — §11 readiness age(ADR-002-017 소유; scalar 참조).
  - `MAX_decision_context_age_ms`(710): `null` — §9 line 265 capsule age(ADR-002-018/#2 소유; scalar 참조).
  - `B_recovery_trigger_to_barrier`(205) / `B_recovery_barrier_to_egress`(212) / `B_evidence_persist`(674) /
    `B_evidence_gap_detect`(681) / `B_evidence_gap_contain`(688): §25 approval-gate 목록 — 전부 존재(ADR-002-017/
    016 소유; latency=런타임).
  - **§25(line 699) 나열 bound 전부 프로파일에 존재**: `B_risk_increase_revoke`·`B_revocation_to_egress`·
    `B_halt_to_egress`·`B_recovery_trigger_to_barrier`·`B_recovery_barrier_to_egress`·`MAX_recovery_readiness_
    age`·`MAX_normal_capability_age`·`B_capability_claim_to_send`·`B_egress_hard_fence`·`B_evidence_persist`·
    `B_evidence_gap_detect`·`B_evidence_gap_contain` — 실측 confirm(누락 아님).

- **누락 distinct 키 (Phase-0 Bounds-Approver 플래그)**: 실측 대조(grep `authoriz|live|duration|valid|
  context_age`) 결과 —
  1. **Live Authorization maximum-validity(duration) 전용 키 부재(핵심 신규)**: §7(line 211 "issue identity,
     issue sequence, activation condition, and **maximum validity**")·§9(line 282 "shall also remain within
     the artifact's own validity interval")·§24 OQ8(line 673 "What maximum readiness age, **authorization
     duration**, context age, and invalidation bounds are approved?")에 대응하는 distinct 프로파일 키가
     **없다**. `MAX_recovery_readiness_age_ms`(readiness age)·`MAX_normal_capability_age_ms`(capability age)·
     `MAX_decision_context_age_ms`(context age)는 **다른 양**이다 — authorization maximum-validity는 *Live
     Authorization 아티팩트 자신의 유효 구간*이다(§5.2 freshness의 근거값). ⇒ **주입 슬롯으로 선언**하되
     값·키 승인은 Bounds-Approver로 넘긴다(누락 시 UNKNOWN⇒§5.2 freshness fail-closed). REARM-AC-008 안전
     직결.
  2. **readiness/context/capability age**: 각각 `MAX_recovery_readiness_age_ms`·`MAX_decision_context_age_ms`·
     `MAX_normal_capability_age_ms`로 **이미 존재**하며 ADR-002-017/018/003 소유다 — liveauth는 scalar 참조/
     compose로 소비만 한다. **중복 계상 않고 cross-reference**(설계 #4 §8·Time §8·#5 §8·#6 §8 under-report
     정정 동형).
  3. **invalidation bound**: `B_risk_increase_revoke`+`B_revocation_to_egress`(REARM-AC-008)·`B_halt_to_
     egress`(REARM-AC-011)로 **이미 존재** — cross-reference(중복 계상 없음; latency는 런타임).
  4. **lease-expiry-fence / transport / margin**: **#6 §8·Time §8이 이미 플래그**한 authority/time 항목 —
     liveauth는 재계상하지 않는다(cross-reference).

  본 계약은 (1)을 **genuinely 신규 누락 키**로, (2)(3)(4)를 **기존 존재 또는 다른 설계가 플래그한 항목**으로
  구분해 기록한다(중복 계상 회피). 값·키 승인은 **Bounds-Approver 게이트**(Live-Armer와 분리 — 프로파일 배너
  line 11–12; IMPLEMENTATION-PLAN §3)로 넘긴다. [SAFE-048]

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

- **`tos/src/tos/liveauth/` 모델·술어·property·import-closure 테스트 저작**(§2–§7): 설계 #3(EV-L1 하네스)이
  property suite를 실행. `tos.canonical`(digest+id+classify) + `tos.ordering`(순서) + `tos.time`(TRUSTED·
  freshness) + **`tos.authority`(epoch·precedence·rearm·capability)** REUSE, 신규 canonicalizer/ordering/time-
  math/authority-예측자 없음. **PROMOTE 0건**(IndependentIdArtifact 이미 core — #6).
- **의존 방향**: liveauth ⟸ `tos.canonical`·`tos.ordering`·`tos.time`·`tos.authority`. liveauth는 rcl/capsule/
  evidence/dsl를 import하지 않음(형제, scalar만). RCL capacity·safety-config·recovery·capsule은 scalar 참조.
- **cross-sibling edge 기록(§3.4/§3.5)**: `liveauth → authority`(두 번째 형제간 edge)·`liveauth → time`(직접,
  diamond)은 §7.1 import-closure가 **허용 대상으로 명시**(봉인 아님)하고, 설계 #1 §3.2 "자기 자신 `tos.*`"
  조항이 이를 커버함을 교차-주석. acyclic 확인: authority/time 모두 liveauth 미참조.
- **의존성 관찰(결정 아님) — 미래 #6 `RearmVerdict` 확장**: variant 경로의 14항 로컬 재표현(§6.4/M1)은 #6
  `authority.RearmVerdict`(`state.py:163–174`)가 `armable`만 노출하고 `all_prerequisites`를 SoD와 분리 노출하지
  않는 데서 비롯한다. 더 깨끗한 장기 형태는 #6가 `RearmVerdict.all_prerequisites: bool`을 별도 노출하도록
  **개정**해 variant 경로도 재표현 없이 그 필드를 compose하는 것이다. 지금은 **미채택** — #6가 ratified+implemented
  이고 본 문서는 #6를 변경하지 않는다(non-normative). 이는 **의존성 관찰**이지 결정이 아니며, drift 회귀 테스트가
  그 사이의 안전 격차를 메운다(§6.4/§7).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

1. **VERIFICATION-PROFILE-002 bounds 승인 + 누락 키 신설**(§8): **Live Authorization maximum-validity
   (duration)** 전용 키(신규); readiness/context/capability age·invalidation bound는 기존/타-설계 공유
   (Bounds-Approver ≠ Live-Armer — 프로파일 배너 line 11–12).
2. **프로덕션 canonical serialization·digest 알고리즘 선택**(설계 #4 §9.2 item 1과 동일 게이트):
   `ev-l1-provisional-0`·sha256은 비프로덕션.
3. **First restricted-live profile scope 결정**(§24 OQ5 line 670 "What exact scope dimensions and risk
   vectors are supported by the first restricted-live profile?"): §5.3 `scope_covers`·§6.1 layering은 scope-
   무관하게 성립하되 실제 scope 차원·risk vector는 정책 승인. ADR-002-014 safety-config 소관.
4. **Fenced single-use capability / final egress 프로토콜(§9.1–§9.5; §16; §24 OQ3)**: 자격증명·라우트·
   consensus·hard-fence — **런타임+broker+security(EV-L2/L3+Security, Phase B)** 이며 Phase 1 EV-L1 밖(§0.2).
   REARM-EV-010 not-Phase-1.
5. **Human dual-control 메커니즘**(§13; §24 OQ1; ADR-002-015 interface): effective-principal·quorum·SAFE-053
   variant compensating-control 인증·approval-소비·Human HALT. §6.3 술어는 principal 좌표 + variant
   attestation flag만; 실제 인증/승인-소비는 ADR-002-015 런타임. REARM-EV-005 +Security not-Phase-1.
6. **Safety-configuration artifacts + atomic activation(§4.1/§4.2/§6.4; §24 OQ6; ADR-002-014)**: Hard Safety
   Envelope·Runtime Safety Profile 아티팩트·semantic validation·atomic activation은 ADR-002-014 소관 —
   liveauth는 version/generation/digest scalar 참조 + layering 술어만.
7. **Recovery Readiness / Evidence(§11; ADR-002-017)**: Recovery Coordinator·barrier·readiness decision은
   ADR-002-017 소관 — liveauth는 scalar 참조 + re-arm 전제 flag만.
8. **evidence before partial expand(§24 OQ10 line 675)**: partial scope 확장에 필요한 evidence는 정책 승인;
   §6.6 술어는 proportional flag·progressive gate만.
9. **Independent-Safety-Reviewer 지정 + §7 EV-L1 evidence 수용 서명**(저자 배제 — IMPLEMENTATION-PLAN §3).

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- 2026-07-24: **v1.0 초안 최초 작성.** ADR-002-007 EV-L1 실현 계약(트랙 A 세 번째·마지막 §2 코어).
  설계 #1(경계·firewall)·#2(capsule all-false·generation_vector)·#4(canonical substrate + id⊥digest)·#5
  (RCL capacity 측 형제 scalar)·Time(TRUSTED·freshness 술어)·**#6(Safety Authority — epoch·precedence·rearm·
  capability 소비)**에 정렬. 주요 결정: (§0.4a) 전용 패키지 `tos/src/tos/liveauth/`(설계 #1 §2.1 line
  117–118 "Live Authorization" = 9 코어); (§0.4b/§3.5) **`tos.authority` import-and-compose** — 본 시리즈
  **두 번째 sibling→sibling edge**(ADR Depends-On 002-003 정합; injected-boolean seam 봉합; DRY — #6 안전-수정
  재복제 회피; acyclic), 대안 3종(재저작/core-PROMOTE/scalar-injection) 기각; (§0.4c/§3.4) **`tos.time` 직접
  import**(ADR Depends-On 002-008; diamond acyclic; authority가 TRUSTED/freshness 술어를 re-export 안 함);
  (§0.4d/§3.1) `tos.canonical` REUSE + `id=f(digest)` 미채택(same-authorization-id/diff-content 위조·replay
  탐지 보존), `classify_record_pair` core REUSE, **PROMOTE 0건**(IndependentIdArtifact 이미 core — #6 PROMOTE
  완료; #6과의 핵심 차이); (§0.4e/§6) **경계 대 authority** — rearm_gate/checklist/restrictive_dominates/
  permissive_capability_valid/CapabilityType REUSE(중복 금지, compose), Live Authorization 아티팩트·limit
  layering·§13 SAFE-053 two-lawful-paths dual-control(authority.rearm_gate SoD가 strict-distinct-only이므로
  ADD)·continuous validity·partial re-arm·§14.1 delta = liveauth ADD, safety-config/recovery/capsule/capacity =
  scalar 참조; (§0.4f) `tos.rcl`·`tos.capsule`·`tos.evidence`·`tos.dsl` 미import(형제, scalar); (§0.4g) **INV
  시리즈 창작 금지** — ADR-002-007엔 INV 부재(실측), `REARM-AC-001..012` + §-clause + SAFE-xxx에 앵커;
  (§1) **REARM-EV 0건 완결**(register 최소 전부 EV-L2+) + **predicate-only(11)/not-Phase-1(1=010 egress),
  코어 tier 없음**, "EV-L1-complete 주장 금지"; (§2) Live Authorization/transition/approval = **IndependentId
  + 독립 id**, `IdDerivedArtifact` 0건; **lifecycle state 좌표 비붕괴**(immutable claims만 covered, 전이는
  Transition Record — 정당 전이의 CRITICAL_CONFLICT 오탐 방지); (§4.1) **authorization ≠ enforcement** 중앙
  불변식(발행·보유 ≠ live; ACTIVE = continuous-validity 성립 시만, issued에서 미추론; all-false; approval/
  readiness ≠ authorization); (§4.2) **default-non-live**(absence ⇒ non-live, zero-value canary); (§4.3)
  non-revival + fresh-identity; (§5) default-non-live·continuous-validity(authority+time compose, egress
  조건 비주장)·**subset scope coverage(빈 auth⇒covers nothing — vacuous-True 선제 봉합)**·lifecycle 전이·
  fresh-identity; (§6) **layering 부등호 방향 명시·이중검증**·atomic activation·**two-lawful-paths dual-control
  (type-gated disjunction — #6 M2 동형)**·re-arm 소비(authority.rearm_gate compose, authority_effect all-false)·
  no-auto-rearm·partial narrowing·**§14.1 delta(old 미확장, delta≠existing id)**·HALT precedence(REUSE);
  (§8) **Live Authorization maximum-validity(duration)** 누락 키 실측 후 Phase-0 플래그(readiness/context/
  capability age·invalidation bound는 기존/타-설계 공유, 중복 계상 회피). **선제 fail-open 봉합**: #6 v1.0
  REJECT defect class(claimant/subset vacuous-True·type-gated disjunction·부등호 전치)를 §5.3/§6.1/§6.3에서
  미리 봉합해 저작. 이후 독립 비평 리뷰 대기.
- 2026-07-24: **v1.1 — 독립 비평 리뷰 REVISE 반영(MAJOR 2 / MINOR 2 / gap 2).** 리뷰는 EV 정직성·#6 4개 defect
  class 선제봉합·acyclicity/PROMOTE-0/firewall/프로파일 키/~20 인용·lifecycle arrow·layering 방향을 **전부 clean
  검증**했고, 2 MAJOR는 **최고-위험 §(SAFE-053 dual-control ADD)**에 집중되었다. 7건 전부 반영: **[M1]** §6.4
  variant-path "second-effective-principal compose"를 **폐기**하고 **quorum=`rearm_gate(...).armable` 직접 소비 +
  variant-path 14 환경 전제 로컬 재표현 + `authority._REARM_PREREQUISITES`(`predicates.py:96–111`) item-for-item
  drift 회귀 테스트**로 확정(근거: `RearmVerdict`가 `armable`+`authority_effect`만 노출·14전제/SoD 미분해,
  `state.py:163–174`; `rearm_gate` strict `!=`, `predicates.py:768–779`; 합성-principal 주입은 SA-INV-014 스푸핑
  + ADR-002-015 §17.1.3 "not the second principal" 위반). "재나열 금지" → **"SoD 재유도 금지"**로 정밀 완화
  (§0.4e/§3.5/§6.4/§7). **[M2]** §6.3/§2.7 SAFE-053 compensating controls에 **§17.1.2 Time-Separated Re-
  Authenticated Self-Approval(line 467–474)·§17.1.3 Independent Non-Authorizing Attestation(line 476–483)** 2개
  추가(5→7 control), external-reviewer 구성(§17.1.4 line 487)은 **Path 1**(genuine second principal)로 라우팅·
  Path 2는 solo 전용, §17.1.1–§17.1.5 line 인용, `variant_approved`가 §17.1.2/§17.1.3 미subsume 명시. **[m1]**
  §6.4 header·item 3·문단의 "§17.3 line 676–678"을 **ADR-002-003 §17.3 line 678**로 정정(+ ADR-002-007 §1 line
  42 병기); §3.5 표의 §17.1을 **ADR-002-003 §17.1**로 정정. **[m2]** §8/§9.2 프로파일 배너 cite를 **line 11–12**
  로 정정. **[Gap-1]** §5.2/§2.2에 **ADR-002-019/020/021/029/030 per-order 조건의 egress 명시 이연**(REARM-EV-010;
  017/018 scope-level flag 모델링과의 비대칭 근거) 추가. **[Gap-2]** §6.5에 **narrowing-to-∅ = full
  de-authorization**(§5.3 일관) 주석 추가. §9.1에 미래 #6 `RearmVerdict.all_prerequisites` 확장을 **의존성
  관찰(결정 아님)**로 기록. 아키텍처 핵심 결정(패키지·import 방향·PROMOTE-0·REARM-EV 0건·id⊥digest)은 v1.0 그대로.
  2026-07-24 운영자 비준(판단 지점 3건 승인).
- 2026-07-24: **v1.2 — §6.4 item 4 게이트 필드명 오기 에라타(의미 변경 아님, 비준 효력 유지).** 구현
  (`tos/src/tos/liveauth/predicates.py`)과 독립 코드 리뷰(ACCEPT-WITH-MINOR, CRITICAL 0/MAJOR 0/fail-open
  0 — rcl·authority에 이어 **3연속 클린**)가 발견: v1.1 §6.4 item 4가 partition 게이트 필드를
  `automatic_rearm_denied`로 오기 — 그 필드는 authority 구현에서 **무조건 True**(quorum 복구≠auto-rearm
  문서화)라 문면대로 게이트하면 admissible이 항상 False(전 re-arm 차단 — fail-open 아닌 과잉제한이나 계약
  오기). 올바른 게이트 = **`live_rearm_denied`**(verifiability: None/False⇒denied, fail-closed 유지).
  구현이 올바른 필드를 사용·공개(docstring), 리뷰가 확정 → 본 에라타로 계약-코드 정합. §1 표(-003 행)·
  §6.4 no-auto-rearm 절의 `automatic_rearm_denied=True` 언급은 SA-INV-013 문맥의 **올바른 사용**이라
  불변. 코드 리뷰 부수 판정: 공개 편차 2건(epoch을 authorization 자신에서 읽기 — 결합-seam 봉쇄 강화 /
  frozenset 정렬 serializer — digest 결정론) **둘 다 "의도 충실+더 강함"**; MINOR-2(quorum `count>=2`
  리터럴)는 ADR §13 규범 상수로 무조치. 그 외 조항·비준 효력(2026-07-24, v1.1) 불변.

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

- [ ] §0.2 NO 목록(egress/fenced 프로토콜·dual-control 인증·safety-config·recovery·capsule·실제 clock·
      authority·**REARM-EV 0건**·bounds 미승인)과 §0.3 firewall 준수(numpy/pandas/pyyaml·shared.config·
      **tos.rcl·tos.capsule·tos.evidence·tos.dsl** 배제, **tos.authority·tos.time·tos.ordering·tos.canonical
      만 허용**; `.importlinter`는 forbidden 계약뿐 — intra-tos edge firewall-clean)에 동의.
- [ ] §0.4a 전용 패키지 `tos/src/tos/liveauth/`(설계 #1 §2.1 line 117–118 "Live Authorization" = 9 코어;
      naming 비-load-bearing) 채택에 동의.
- [ ] §0.4b/§3.5 **`tos.authority` import-and-compose**(두 번째 sibling→sibling edge; ADR Depends-On 정합·
      seam 봉합·DRY(#6 안전-수정 재복제 회피)·acyclic; 대안 재저작/core-PROMOTE/scalar-injection 기각)에 동의.
      **[운영자 판단 지점: cross-sibling import(두 번째 edge) vs injected-boolean scalar fallback(seam 재개방 —
      비권장)]**
- [ ] §0.4c/§3.4 **`tos.time` 직접 import**(authority 경유 아님; ADR Depends-On 002-008; authority가 TRUSTED/
      freshness 술어 re-export 안 함; diamond acyclic)에 동의. **[운영자 판단 지점: 직접 edge vs authority
      re-export 경유]**
- [ ] §0.4d/§3.1 `tos.canonical` REUSE + `id=f(digest)` 미채택 + **PROMOTE 0건**(IndependentIdArtifact 이미
      core — #6과 차이; `tos.liveauth._base` re-export shim), `classify_record_pair` core REUSE에 동의.
- [ ] §0.4e/§6 **경계 대 authority** — REUSE(rearm_gate 14항/restrictive_dominates/permissive_capability_valid/
      CapabilityType, **SoD 재유도 금지**) vs ADD(Live Authorization 아티팩트·layering·**SAFE-053 two-lawful-paths
      dual-control** — authority SoD가 strict-distinct-only이므로·continuous validity·§14.1 delta) vs
      scalar-reference(ADR-002-014/017/018·RCL)에 동의. **[운영자 판단 지점(M1 확정): variant-path 14항 로컬
      재표현 + `authority._REARM_PREREQUISITES` drift 회귀 테스트(**채택**; quorum은 `rearm_gate(...).armable`
      직접 소비, SoD 재유도 금지) vs 미래 #6 `RearmVerdict.all_prerequisites` 노출 확장(운영자 선호/veto 대상 —
      §9.1 의존성 관찰). "second-effective-principal compose"는 스푸핑으로만 실현되어 폐기]**
- [ ] §1 **REARM-EV 0건 완결**(register line 79–90 최소 전부 EV-L2+) + **predicate-only(001/002/003/004/005/
      006/007/008/009/011/012)/not-Phase-1(010 +Security final egress), 코어 tier 없음** + "EV-L1-complete
      주장 금지"에 동의.
- [ ] §2 데이터 모델(Live Authorization·transition·approval = **IndependentId + 독립 id**, `IdDerivedArtifact`
      0건; **lifecycle state 좌표 비붕괴** — immutable claims만 covered, 전이는 Transition Record; safety-config/
      recovery/capsule/RCL은 scalar/술어 참조, 클래스 미import)에 동의.
- [ ] §4.1 **authorization ≠ enforcement** 중앙 불변식(발행·보유 ≠ live; ACTIVE = continuous-validity 성립
      시만·issued 미추론; all-false 모델; approval/readiness ≠ authorization; documentation ≠ authorization)과
      §4.2 **default-non-live**(absence ⇒ non-live, zero-value canary)·§4.3 non-revival/fresh-identity·§4.4
      좌표 비붕괴 상속·§4.5 restrictive-gen≠경제효과 release에 동의.
- [ ] §5 validity 술어 — **default-non-live `is_live(None)==False`**, **continuous-validity의 authority+time
      compose(injected-bool seam 부재)·egress 조건 비주장 경계·ADR-002-019/020/021/029/030 per-order 조건은
      egress(REARM-EV-010)로 명시 이연(Gap-1, 묵시 부재 아님)**, **subset scope coverage(빈 auth⇒covers
      nothing·narrow⊅wide — vacuous-True 봉합, #6 M1 동형)**, lifecycle 전이(terminal→ACTIVE 부재), fresh-
      identity에 동의.
- [ ] §6 limit governance/re-arm 술어 — **layering 부등호 방향 명시·이중검증**(per-action ≤ … ≤ hard-envelope,
      #6 v1.2 교훈), atomic activation, **two-lawful-paths dual-control(type-gated disjunction; quorum/external-
      reviewer=Path 1 ∨ SAFE-053 solo variant=Path 2, **7 control** 모두 양성 incl. §17.1.2 time-separation·
      §17.1.3 attestation; `variant_approved`가 §17.1.2/§17.1.3 미subsume; None principal⇒denied)**, re-arm 소비
      (**quorum=`rearm_gate(...).armable` 직접·variant=14 환경 로컬 재표현+drift 테스트, SoD 재유도 금지**·
      authority_effect all-false·all-but-one⇒not-admissible), no-auto-rearm(recovery/timeout/restart flag 무시),
      partial narrowing(broader fallback 부재·**narrowing-to-∅=full de-authorization**), **§14.1 delta(delta≠
      existing id·old 미확장·continuity-unbroken 아니면 full-§12)**, HALT precedence(REUSE 순서-무관)에 동의.
- [ ] §7 하네스 타깃(전부 predicate substrate; "EV-L1-complete 주장 금지"), **§7.1 import-closure**(tos.rcl/
      capsule/evidence/dsl 부재 + tos.authority/time/ordering/canonical 허용), §7.2 run manifest 7항목에 동의.
- [ ] §8 bounds 주입 + **Live Authorization maximum-validity(duration)** 신규 누락 키 Phase-0 플래그(readiness/
      context/capability age·invalidation bound는 기존/타-설계 공유, 중복 계상 회피)에 동의.
- [ ] §9.2 Phase-0 이관 9항목(bounds·프로덕션 canon·first restricted-live scope·fenced egress 프로토콜·
      dual-control 메커니즘·safety-config·recovery·evidence-before-expand·독립 리뷰어)을 별도 게이트로 유지에
      동의.
- [ ] 명명 규약(§0.4g): 모델 불변식을 **REARM-AC-001..012 / §-clause / SAFE-xxx**에 앵커하고 **새 INV 시리즈를
      창작하지 않음**(ADR-002-007엔 INV 부재 — 실측)에 동의.

비준 시 효력: IMPLEMENTATION-PLAN-002 §4 Phase 1의 ADR-002-007 부분을 `tos/src/tos/liveauth/`에 순수·비전송
모델 + property test로 작성 착수 승인(`tos.canonical`·`tos.ordering`·`tos.time`·`tos.authority` REUSE, PROMOTE
0건). §9.2 Phase-0 9항목과 bounds 승인·독립 리뷰어 지정, Phase B(fenced egress 프로토콜·dual-control 인증·
safety-config activation·recovery·leader/consensus) 전체는 별도 게이트로 남는다. **REARM-EV 0건 완결 —
acceptance 주장 없음.**
