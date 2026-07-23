# 설계 문서 #6 — Safety Authority Validity + Epoch Fencing + Partition Behavior 계약 (2026-07-23, v1.1)

> **문서 번호 규약**: #1 경계·import-firewall, #2 Decision Context Capsule, #4 Evidence
> Store, #5 Risk Capacity Ledger(RCL)가 이미 존재한다(#3은 folded). Trustworthy Time·
> DSL은 병렬 트랙이었다. **#6 = 본 Safety Authority 문서**이며, **트랙 A(ADR-002-003/
> 007/008 묶음)의 두 번째 §2 코어**다 — 첫 §2 코어는 Trustworthy Time(ADR-002-008)이었고,
> 본 문서는 그 위에 서는 authority 층(ADR-002-003)이다.
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**
> 이며 스펙 텍스트(RFC/ADR/템플릿/프로파일)를 **변경하지 않는다.** broker-agnostic 원칙
> (project memory `tos-spec-broker-agnostic`): KIS 등 특정 브로커 사실은 프로젝트 측 예시로만
> 등장하며 규범 주장이 아니다. authority domain·epoch·capability·lease·precedence·partition
> 불변식은 전부 broker-agnostic이며, 브로커 제약은 capability class(Broker Capability
> Profile)로만 표현한다. 본 문서는 IMPLEMENTATION-PLAN-002 §4 Phase 1(EV-L1)의
> **ADR-002-003 부분**(line 165–168 "the … **authority epoch/lease** … models
> (ADR-002-003/007/008) **as pure, non-transmitting models**")을 그린필드
> `tos/src/tos/authority/`에 **순수·비전송 데이터 모델 + property test**로 실현한다.
>
> **선행 문서(의존)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   본 계약의 모든 모델은 설계 #1 §2.4 레이아웃(`tos/src/tos/authority/`)에 놓이고 §3.2
>   허용목록 안에서만 의존한다(§0.3). `tos.*` 자기참조·`pydantic`만 신규 사용.
> - [설계 #4 — Evidence Store + append-only ledger 계약 (v1.1, 비준·구현됨)](2026-07-20-tos-evidence-store-design.md)
>   + 코드 `tos/src/tos/canonical/`. **canonicalization/digest-binding substrate(`tos.canonical`)·
>   `classify_record_pair`·ordering를 REUSE한다(재정의 금지).** evidence의 `id=f(digest)`
>   **미채택** 결정을 authority가 **동형으로 상속**한다(§2.1/§3.1).
> - [설계 #5 — Risk Capacity Ledger 계약 (v1.1, 비준)](2026-07-21-tos-risk-capacity-ledger-design.md)
>   + 코드 `tos/src/tos/rcl/`. RCL은 **capacity 측** 형제다. RCL의 `ProtectiveLease.
>   safety_authority_epoch_binding`·`writer_fenced`·`partition_verdict`·`AllFalseAuthority`·
>   `IndependentIdArtifact`와 본 authority 층의 경계가 본 문서의 중심 아키텍처 결정이다(§0.4·§3).
>   **`tos.rcl`은 import하지 않는다**(형제 — scalar 참조만; §0.3/§3.3).
> - [설계 — Trustworthy Time 모델 계약 (v1.1, 비준)](2026-07-21-tos-trustworthy-time-design.md)
>   + 코드 `tos/src/tos/time/`. ADR-002-003의 lease 유효성은 **monotonic-time-bounded**이며
>   (§14.3/§15) time 패키지의 술어(`conservative_usable_lifetime`·`anchor_valid`·
>   `elapsed_within_continuity`·`recovery_generation_revives_nothing`)가 **그 substrate**다.
>   **`tos.authority`가 `tos.time`을 import**하는 것이 본 시리즈 최초의 sibling→sibling
>   edge이며 정당화가 §0.4b/§3.4의 핵심이다. **time 산술을 재저작하지 않는다.**
> - [설계 #2 — Decision Context Capsule + Snapshot 계약 (v2, 비준·구현됨)](2026-07-20-tos-decision-context-capsule-snapshot-design.md).
>   `SnapshotAuthority._all_authority_false` 패턴(`tos/src/tos/capsule/_base.py` line 70–78)을
>   REUSE(로컬 재표현)한다. `DECISION-CONTEXT-CAPSULE.generation_vector`(template line 47)가
>   generation-vector 어휘의 SoT다(§4.7). `tos.capsule` 자체는 import하지 않는다(형제).
>
> **규범 원천**: `ADR-002-003` — Safety Authority Validity, Epoch Fencing, and Partition
> Behavior (Status: **Proposed**, 988 line). Amends RFC-002; Depends-On RFC-000, RFC-001
> (SAFE-011/035/041/048), ADR-002-001 v0.2, ADR-002-002(line 9). §26 interfaces:
> ADR-002-001/002/004/005/007/008/009/012/013/014/015 + VER-002-001(line 929–944).
> 매핑 대상 EV: `verification/EVIDENCE-REGISTER-002.csv`의 `SA-EV-001..015`(line 20–34).
>
> **비준 기록**: **2026-07-24 운영자 비준(v1.1) — 효력 발생.** 독립 비평 리뷰 **REJECT**(CRITICAL 0 /
> MAJOR 3 / MINOR 3 + Gap 1) → v1.1 전 항목 반영·오케스트레이터 실측 검수 후 비준. §10.2 판단 지점 2건
> 승인: **`tos.authority → tos.time` import-and-compose**(시리즈 최초 sibling→sibling edge) ·
> **`IndependentIdArtifact` (rcl+dsl)→canonical PROMOTE**. 효력: `tos/src/tos/authority/` Phase 1
> (EV-L1) 순수·비전송 모델 + property test 착수(선행 소단계 = PROMOTE + 두 shim 무회귀). SA-EV 0건
> 완결 — acceptance 주장 없음; §9.2 Phase-0 8항목은 별도 게이트 유지.
>
> **리뷰 이력**: v1.0 초안 → 별도 컨텍스트 독립 비평 리뷰 **REJECT**(3 MAJOR / 3 MINOR / 1 gap;
> fail-open·firewall/layering·overclaim·인용 fidelity adversarial 탐색, ADR-002-003 line·register·
> `.importlinter`·tos 코드 primary-source 재검증) → **v1.1**. 리뷰는 **인용 fidelity·EV 정직성·아키텍처
> 3결정**(`tos.time` edge / PROMOTE 대칭 / `writer_fenced` 미재사용 — 전부 clean 검증)을 승인했고,
> rejection은 좁게 **두 fail-open seam(§6.1/§6.3 exclusivity, §5.2 조건 4)** + **한 PROMOTE 완전성 누락
> (§0.4c `tos.dsl` 복제)**이었다. v1.1은 M1/M2/M3 + m1/m2/m3 + Gap **7건 전부 반영**(§10.1). **비준 대기**
> (ratification pending). 수용 서명 게이트는 IMPLEMENTATION-PLAN-002 §3(line 153/157) 하드 배제
> (Independent-Safety-Reviewer는 본 문서의 저자/통합자여서는 안 됨)를 따른다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-003 조항별 **EV-L1 도달성 경계**와 **SA-EV 0건 완결** 결정적 사실(§1). SA-EV
   15행을 **predicate-only / not-Phase-1** 2분류(코어 tier 없음 — L1-최소 행 0건).
2. Safety Authority ledger 시민(**capability·authority-epoch transition·degraded-lease
   ownership** 레코드)과 injected 술어 상태(epoch-floor·generation-vector·currentness
   witness·precedence·partition·re-arm checklist)의 **데이터 모델 계약**(§2).
3. **canonical/ordering/time REUSE + `tos.rcl` 경계 결정**(§3): `tos.canonical` REUSE +
   `id=f(digest)` **미채택**; `tos.ordering` REUSE; **`IndependentIdArtifact`를 `tos.rcl`
   →`tos.canonical` core로 PROMOTE**(Phase-1 PROMOTE 1건, §0.4c); **`tos.time` import**
   (최초 sibling→sibling edge, §0.4b); **`tos.rcl`·`tos.capsule`·`tos.evidence`는 import
   금지**(scalar 참조만).
4. **authority ≠ enforcement 중앙 불변식**(§4.1): capability의 서명·보유·계산은 **현재
   authority가 아니다**(§1 line 17; §5.3 line 121). 모델은 non-transmitting 데이터이며, 유효성
   술어가 True를 반환해도 그것이 authorization을 **완결하지 않는다**(§1 조건 6 egress 독립검증은
   런타임). 설계 #4 evidence≠authority·#5 capacity≠authority 동형.
5. **fail-closed·비복원·epoch 좌표 비붕괴** 불변식(§4): 미지 currentness ⇒ 거부; epoch advance는
   경제효과를 release하지 않음; restart/restore/rotation/re-arm은 옛 capability를 revive하지
   않음; **Safety Authority Epoch ≠ Writer Epoch ≠ membership/restore generation**(좌표 비붕괴).
6. **validity/dominance/HALT 술어 세부**(§5): 6-part authority validity, restrictive
   dominance(양방향 발화), precedence lattice, cached≠current.
7. **lease exclusivity·partition·re-arm 술어 세부**(§6): 단일 exclusive owner, overlapping
   failover 금지(hard-fence ∨ lease-expiry-fence), degraded-lease 유효성(time 술어 compose),
   partition deny-table, 비-authorizing re-arm conjunctive checklist(SoD 포함).
8. **property-test 하네스 타깃**(§7) + import-closure 검증 확장(§7.1) + run manifest 7항목(§7.2).
9. **bounds 주입 계약 + 누락 프로파일 키 Phase-0 게이트 플래그**(§8): Lease-Expiry-Fence 지속시간
   전용 키 부재(실측).

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.**
  ADR-002-003 §28(line 988) "authorizes implementation and verification work but not production
  live trading." ADR acceptance는 오직 *실행된* evidence로만 온다(project memory
  `tos-spec-rfc-authoring-track`).
- **leader election·distributed lock·consensus·epoch registry를 구현하지 않는다 — 이것들이
  ADR-002-003의 런타임 코어이며 EV-L1이 아니다.** §8.2 Authority Epoch Registry(linearizable
  authority, line 259–270), §10 epoch 할당/전진의 실제 serialize, §11 fencing enforcement의 실제
  강제는 **런타임 분산 속성**이며 순수 모델이 증명할 수 없다(§25 line 925 "implementation based
  solely on … Kubernetes leader election, a Redis lock without proven fencing … is non-conforming"
  — 그 non-conforming 목록 자체가 런타임 메커니즘 층임을 확인). Phase 1은 (a) epoch/capability/
  lease **레코드 데이터 구조**, (b) **단조 epoch floor·좌표-비붕괴 불변식**, (c) **authority-fence·
  validity·dominance·exclusivity·re-arm 술어**(주입 상태 위 순수 함수)만 저작한다.
- **실제 fencing·hard fence·egress를 구현하지 않는다.** §5.8 Hard Fence(line 147–151)·§11.3
  egress reachability(line 433–440)·§12 currentness witness·§8.3 egress verify(line 272–288)는
  **런타임+broker**다. 설계 #1 §4대로 tos는 정의상 **non-transmitting**이다(자격증명·라우트·
  주문구성 부재 + egress 코드 firewall 차단). §1 조건 6(egress 독립검증)·SA-INV-012(egress final
  gate)의 *egress* 부분은 Phase 1에서 **capability/lease binding 술어**만 저작하고 실제 전송·강제는
  이연한다(SA-EV-008/013 not-Phase-1).
- **실제 clock을 읽지 않는다.** lease 유효성은 monotonic-time-bounded이나(§14/§15), 모든 시간
  값은 `tos.time`의 **opaque 주입 좌표**다(Time 설계 §0.3/§3). authority 어디에도 clock read가
  없다(`time`/`datetime`/`monotonic`은 firewall 금지).
- **authority를 부여하지 않는다.** 모든 authority 아티팩트의 `authority_effect.*`
  (`is_current_authority_by_possession`·`self_transmits`·`self_mutates_capacity`·
  `self_releases_capacity`·`self_rearms`)는 **false 상수**이며 모델이 강제한다(§4.1). "authority
  경로가 어디에도 없다"의 전수 증명은 EV-L2/L3+Security(SA-EV-008/013)이다.
- **어떤 SA-EV도 완결하지 않는다(§1). SA-EV 0건 완결.** `SA-EV-001..015`는 register 최소 레벨이
  **전부 EV-L2 이상**이다(csv line 20–34 실측: `SA-EV-015`만 `EV-L2`, `SA-EV-005`는 `EV-L2/3`,
  나머지 `EV-L3`/`+Broker`/`+Security`; **EV-L1 최소 항목 0건**). ⇒ Trustworthy Time "TIME-EV
  0건 완결"과 **동형**. "EV-L1-complete 주장 금지"(설계 #2 §7·#4 §7·Time §1·#5 §1 규율 상속).
- **numeric bounds를 승인하지 않는다.** VERIFICATION-PROFILE-002 bounds 승인·누락 키 신설·독립
  리뷰어 지정은 Phase-0 인간 게이트(§8·§9.2).

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

authority 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`도
  import하지 않는다** — epoch·generation은 정수, lease lifetime 산술은 `tos.time`이 정수/`Decimal`
  로 이미 수행하므로 수치 백엔드가 불필요하다(closure 최소화 — 설계 #4 §0.3·Time §0.3·#5 §0.3 동일
  규율). **`pyyaml`도 import하지 않는다** — 모든 bound는 **주입 policy 파라미터**로 들어오고
  (§8), YAML 파싱은 하네스(설계 #3) 소관이지 authority closure 안이 아니다(#5 §0.3 동형).
- tos 자기 자신: `tos.canonical`(digest-binding substrate + `classify_record_pair` +
  **PROMOTE될 `IndependentIdArtifact`** — §0.4a/c), `tos.ordering`(capability 발행/HALT-vs-permissive
  순서 — §3.2), **`tos.time`**(lease 유효성 monotonic 술어·좌표 타입 — §0.4b/§3.4), `tos.authority.*`.
  **`tos.rcl`·`tos.capsule`·`tos.evidence`를 import하지 않는다.** RCL capacity 측(reservation/
  pool/lease/writer-epoch)은 오직 **scalar 참조**(id·revision·digest·epoch 정수)로만 담고 RCL
  클래스를 import하지 않으며, 역으로 RCL도 authority를 import하지 않는다(§3.3 layering — 형제; RCL의
  `ProtectiveLease.safety_authority_epoch_binding`이 이미 authority epoch을 *scalar*로 참조하는
  선례가 이 방향을 확정한다).
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter` line 41): `shared/config/__init__`이
  `shared.config.secrets`(→ `os.environ`)를 무조건 전이 import한다. authority는 애초에 어떤
  `shared.*`도 필요로 하지 않는다(순수 authority 커널). `shared.determinism` 포함 전 `shared.*`
  미import(closure 최소화; Time §0.3·#5 §0.3 동형).
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`, `shared.llm`,
  `shared.storage`, `shared.backtest`, `services.*`, `cli.*`(설계 #1 §2.3; `.importlinter`
  forbidden set line 34–43). authority는 자산군·실행 경로와 무관한 순수 커널이다.
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(`import tos.authority` closure에
  금지·`shared.config`·`os.environ`·numpy/pandas/yaml·**`tos.rcl`·`tos.capsule`·`tos.evidence`**
  부재 assert; `tos.time`·`tos.ordering`·`tos.canonical`는 **존재 허용**). required check
  (`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter` layer-② 전이 방어)와
  함께 green이어야 본 선언이 능동 성립한다.

### 0.4 REUSE / PROMOTE / import 결정 요지 (핵심 아키텍처)

**(a) REUSE(canonical·ordering) + `id=f(digest)` 미채택.** authority ledger 시민(capability·
epoch-transition·lease-ownership)은 `tos.canonical.DigestBoundArtifact`(digest 검증, id 파생
없음)와 `tos.ordering`(발행·HALT 순서)를 **REUSE**한다. capability identity(§9.1 line 317)·epoch은
**서비스/도메인 할당**이지 content-address가 아니다: §9.1은 "capability identity"·"issue sequence"를
독립 claim으로 요구하고, §18.3(line 701–703) replay protection은 same-capability-id/diff-content를
**탐지**하도록 요구한다. ⇒ **`id=f(digest)`(`IdDerivedArtifact`) 미채택** — 그래야 same-capability-id
+ different-bytes(위조/replay) 충돌을 `classify_record_pair`로 CRITICAL_CONFLICT로 탐지할 수 있다
(설계 #4·#5 §3.1과 동형; capsule의 content-addressed와 정반대). same-capability-id/idempotent replay는
§9.3 single-use semantics의 정당한 재제출이다. **`classify_record_pair`는 이미 core**(`tos.canonical`,
#5 §0.4b PROMOTE 완료)이므로 authority가 그대로 REUSE.

**(b) `tos.time` import — 본 시리즈 최초의 sibling→sibling edge(§3.4 상술).** ADR-002-003의 lease
유효성은 **monotonic-time-bounded**다: §14.2(line 545–556)는 lease를 local monotonic anchor에
결부시키고, §14.3(line 558–561)의 "usable local lifetime = signed lease duration reduced by
approved uncertainty and safety margins"는 `tos.time.conservative_usable_lifetime`의 공식과 **동일**
하며, §14.4(line 563–576)의 invalidating events(restart/reboot/monotonic reset/discontinuity/
suspension)는 `tos.time.anchor_valid`가 이미 판정한다. **결정: authority는 `tos.time`을 import해
lease 유효성 술어를 그 예측자들 위에 compose한다**(§6.3). 대안 비교:
- **대안 A — time 산술 재저작**: 기각. 안전-critical monotonic-time 산술을 **중복**하면 drift 위험
  (DRY 위반, CLAUDE.md). 특히 Time v1.2 code-review는 **음수 주입항 fail-closed 가드**(음수 elapsed/
  drift/transport/margin이 lease를 *연장*하는 fail-open)를 REJECT로 강제했다(`predicates.py` line
  168–199) — 재저작은 이 안전 수정을 재현할 의무를 authority에 부과한다.
- **대안 B — time 술어를 core로 PROMOTE**: 기각. `conservative_usable_lifetime`·`anchor_valid`는
  `TimeContinuityIdentity`·`MonotonicReading`·health-domain에 본질적으로 결부돼 있어, core로 옮기면
  `tos.time` 패키지를 hollow-out한다(clean shared-atom PROMOTE가 아님 — ordering/classify와 다름).
- **대안 C — injected-boolean scalar(no import)**: authority가 `lease_time_valid: bool`·
  `remaining_lifetime: int` 를 주입받고 time을 import하지 않음. 기각(주요) — 이는 Time 설계 리뷰의
  **MEDIUM-2 injected-boolean seam** 지적(`effective_snapshot_age_bound`의 `consumer_anchor_valid`
  seam을 `_from_continuity` compose로 봉합)을 **재개방**한다: 잘못된 `True` 주입이 만료·discontinuity
  lease를 통과시킨다. 시리즈가 이미 채택한 seam-봉합 방침에 역행.
- **선택(A/B/C 모두 기각) — import-and-compose**: `tos.authority → tos.time`. 근거: (i) ADR 의존
  방향과 정합 — ADR-002-003 Depends-On/interfaces ADR-002-008(§26 line 936); authority가 time의
  **하류 소비자**다. (ii) seam 봉합 — lease 유효성 술어가 `conservative_usable_lifetime`·`anchor_valid`를
  내부 호출해 injected-boolean seam 부재(Time MEDIUM-2 방침 계승). (iii) acyclic — time은 authority를
  전혀 참조하지 않으므로 `authority → time → ordering → canonical` 단방향. (iv) 좌표 비붕괴 유지 —
  time을 쓰는 것은 *monotonic 시간* 좌표이며 *authority epoch* 좌표와 무관(§4.7). **firewall 허용**:
  `tos.*` 자기참조는 §3.2 허용(기존 rcl/evidence/time이 모두 `tos.canonical`·`tos.ordering` import).
  단 **최초의 sibling→sibling edge**이므로 운영자 판단 지점으로 명시(§10.2). Fallback: 운영자가
  cross-sibling edge를 원치 않으면 대안 C(주입 scalar)로 후퇴하되 §6.3 유효성 술어는 seam-봉합
  wrapper를 별도 요구(그때까지 미확정).

**(c) PROMOTE 1건 — `IndependentIdArtifact`를 `tos.rcl._base` **및** `tos.dsl._base` → `tos.canonical`.**
authority ledger 시민은 **`DigestBoundArtifact` + 독립·주입 id(id⊥digest, issued 시 concrete 필수)** 를
필요로 한다 — 정확히 `tos.rcl._base.IndependentIdArtifact`(rcl `_base.py` line 53–80)가 저작한 것이다.
**실측 정정(M3)**: 동일 base가 `tos.dsl._base.IndependentIdArtifact`(dsl `_base.py` line 53–79; 소비자
`NoActionOutcome`·`PortfolioVector`·`AdmissibilityResult`·`CapabilityManifest`·`BoundOutcome`)에도 **이미 병렬
존재**한다 — 그 docstring이 "Defined DSL-locally to keep the `tos.dsl` import closure free of `tos.evidence`"라
밝히듯, **core home이 없던 병렬-트랙 scope 결정**의 산물이다(리뷰어 open question 답: dsl 로컬 복제는 병렬 트랙에서
core home 부재로 저작된 것이며 본 PROMOTE로 통합된다). `tos.canonical`에는 **`IdDerivedArtifact`(id=f(digest))만**
있고 그 **쌍**인 id-independent base는 rcl·dsl **두 곳에 로컬 복제**돼 있다(second home = classify single-home
선례 위반). **결정: `IndependentIdArtifact`를 `tos.canonical`로 PROMOTE하고 `tos.rcl._base` **와** `tos.dsl._base`를
**둘 다** re-export shim으로 전환**(구조적으로 `IdDerivedArtifact` 옆에 놓이는 core substrate — 두 id-전략 subclass가
core에 함께), rcl·dsl **양 property suite 무회귀 확인**, rcl·dsl·authority가 **동일 core primitive REUSE**.
근거: #5 §0.4b **통일 PROMOTE 규칙** — 형제들이 공유하는 순수 substrate는 상호 import·재저작 없이 core로 PROMOTE
(ordering·canonicalization·`classify_record_pair` 선례와 **완전 동형**: classify는 evidence→canonical + evidence
shim, 여기는 `IndependentIdArtifact`가 **rcl+dsl→canonical + 두 shim**). 대안(authority-local 재저작, 4패키지
all-false-block 선례처럼)은 기각 — all-false는 **flag 이름이 패키지별로 다른** 5줄 validator라 로컬이 정당하지만,
`IndependentIdArtifact`는 **로직에 패키지별 변이가 없는**(동일 `_ID_FIELD` ClassVar + 동일 validator) 15줄
id⊥digest 안전 base이며 이미 core인 `IdDerivedArtifact`의 대칭 쌍이다 — classify에 가깝고, 지금 **두 곳에 중복**돼
있어 single-home 선례상 반드시 통합되어야 한다. **[운영자 판단 지점: promote(rcl+dsl 흡수) vs authority-local
재저작(세 번째 복제 — 비권장)]**(§10.2).

**(d) `writer_fenced` 미재사용·`tos.rcl` 미import — authority epoch은 다른 좌표계.** RCL의
`writer_fenced`(rcl `predicates.py` line 479–524)는 **Writer Epoch/membership/restore/revision**
4좌표 위 fence다 — RCL/consensus-ledger 좌표계. **Safety Authority Epoch은 별개 좌표계**다: ADR-002-003
§5.2(line 111–115) authority epoch은 Authority Domain별이고, §27 OQ2(line 953–954)는 이를 "ADR-002-012's
Safety Commit Log 위에서 **authority separation을 붕괴시키지 않고**" 구현하라 요구한다 — 즉 **collapse
금지가 명시 규범**이다. ⇒ authority는 `writer_fenced`를 **재사용하지 않고**(재사용은 좌표 붕괴) 자체
`authority_epoch_fenced`/`authority_epoch_current`를 **authority-local `AuthorityEpochState` 위에** 저작한다.
공유 원자는 trivial한 monotonic-floor scalar(`value None ∨ floor None ∨ value<floor ⇒ fenced`)뿐이며,
이는 authority-fence가 **capability-type 비대칭**(restrictive HALT는 stale epoch에도 적용 가능 §7 line 241,
permissive는 불가 line 242)이라 각 호출부에서 다르게 감싸지므로, all-false-block 선례대로 **로컬 재표현이
정당**하다(과도한 추상화 방지 — "PROMOTE를 강요하지 않는다", #5 §0.4b). 이 fence-primitive PROMOTE는
**검토 후 기각**을 명시한다(리뷰어 선제). `tos.rcl` import는 형제 규율 위반 + 좌표 붕괴이므로 금지;
RCL capacity 참조는 scalar만.

**(e) 패키지 위치 = 전용 `tos/src/tos/authority/`.** 설계 #1 §2.4/§2.1(line 117)이 "Safety Authority"를
IMPLEMENTATION-PLAN §2의 9개 코어 중 하나(first-class)로 열거하고, capsule/·evidence/·time/·rcl/을 전용
top-level 패키지로 둔 선례에 부합한다(RFC-002 §10 컴포넌트 = 코드 패키지). naming은 load-bearing이
아니다 — 운영자 치환 가능; **load-bearing은 layering**(authority → time·ordering·canonical 한 방향;
rcl·capsule·evidence와 형제, scalar만).

**(f) 불변식 명명 규약.** ADR-002-003은 **`SA-INV-001..014` register(§6 line 165–219)** 와
**`SA-AC-001..015`(§23 line 811–873)** 를 가진다. 따라서 본 계약은 **새 INV 시리즈를 창작하지 않고**
모델 불변식·술어를 **SA-INV-001..014 / SA-AC-001..015**에 앵커하며, RFC-001 앵커는 ADR Depends-On line 9의
**SAFE-011/035/041/048**을 인용한다(정확한 SAFE 본문은 RFC-001 소관 — 본 문서는 ADR이 선언한 앵커만 참조).

---

## 1. 범위 매핑 — ADR-002-003 조항별 EV-L1 도달성 (SA-EV 0건 완결)

EV-level 정의(VER-002-001 line 142–152): **EV-L1 = Model and Property Verification**(state-machine
exploration, model checking, property-based testing, deterministic simulation). **EV-L2 = Component
Fault Test**. Phase 1은 EV-L1만이다.

> **결정적 사실 — SA-EV 0건 완결**: `SA-EV-001..015`(ADR-002-003 acceptance)는 register 최소 레벨이
> **전부 EV-L2 이상**이다(`EVIDENCE-REGISTER-002.csv` line 20–34 실측: `SA-EV-015` = `EV-L2`,
> `SA-EV-005` = `EV-L2/3`, `SA-EV-008` = `EV-L3+Broker`, `SA-EV-013` = `EV-L3+Security`, 나머지 =
> `EV-L3`; **EV-L1 최소 항목 0건**). ⇒ **Phase 1은 어떤 SA-EV도 닫지 않는다**(Trustworthy Time
> "TIME-EV 0건 완결"·#5 "RC-EV 0건 완결"과 **동형**). **코어 tier가 없다** — #5의 RCLP-EV는 3개가
> `EV-L1/3` 최소라 "core(L1 슬라이스)"가 있었지만, SA-EV는 EV-L1 최소 행이 **0건**이라 분류는
> **predicate-only / not-Phase-1 2분류**뿐이다. 모델은 각 항목의 **L1-decidable 술어 substrate**만
> 주장한다.

| SA-EV | 제목 | register 최소(csv line) | Phase-1 분류 | Phase-1 EV-L1 substrate (닫지 않음) | ADR 근거 |
|---|---|---|---|---|---|
| -001 | Duplicate Active Safety Authority | EV-L3 (20) | **predicate-only** | 도메인당 단일 current epoch 불변식 + `authority_epoch_current`(stale⇒거부) | §6 SA-INV-001/002 (165–171), §7 |
| -002 | Stale Leader Resume | EV-L3 (21) | **predicate-only** | stale-epoch 거부 술어(advance 후 하위 epoch 무효) | SA-INV-002 (169–171), §10.2 (384–394) |
| -003 | Partition After Normal Grant | EV-L3 (22) | **predicate-only** | partition deny-table + no-cached-risk(§4.1) | SA-INV-005 (181–183), §13.1 (475–487) |
| -004 | Valid Degraded Protective Lease | EV-L3 (23) | **predicate-only** | degraded-lease 유효성 술어(§13.2 8조건 중 7개 모델링·broker-egress 런타임 이연, §6.3) | §13.2 (489–500), §14 |
| **-005** | Monotonic Lease Expiry | EV-L2/3 (24) | **predicate-only(최강 substrate)** | `conservative_usable_lifetime` REUSE — monotonic 초과⇒무효(signed wall이 valid로 보여도) | §14.3 (558–561), §15.2 (595–603) |
| -006 | Lease Owner Restart | EV-L3 (25) | **predicate-only** | `anchor_valid` REUSE — restart/boot 변화⇒무효 | SA-INV-009 (197–199), §14.4 (563–576) |
| -007 | Overlapping Lease Failover | EV-L3 (26) | **predicate-only** | exclusivity + `overlapping_failover_forbidden`(hard-fence ∨ expiry-fence) | SA-INV-006/007 (185–191), §14.5 (578–585) |
| -008 | Hard Fence | EV-L3+Broker (27) | **not Phase-1** | hard fence = "former authority가 broker 도달 불가" 증명 ⇒ 런타임+broker. (파생: reassignment 전제 술어가 주입 `hard_fence_proven` flag 소비, §6.2) | §5.8 (147–151), §11.3 (433–440) |
| **-009** | HALT Versus Permissive Capability | EV-L3 (28) | **predicate-only(강 substrate)** | restrictive dominance — HALT가 발행순서 무관하게 permissive 지배(**양방향 property**) | SA-INV-010/011 (201–207), §7 (223–242) |
| -010 | Re-arm Gate | EV-L3 (29) | **predicate-only** | 비-authorizing conjunctive re-arm checklist(임의 미충족/미지⇒not-armable) + SoD | §17.1 (651–668), SA-INV-013/014 (213–219) |
| -011 | Time Discontinuity | EV-L3 (30) | **predicate-only** | `anchor_valid`+`conservative_usable_lifetime` under discontinuity/suspension; unknown time-health⇒무효 | §15.3 (605–607), SA-INV-008 (193–195) |
| -012 | Key Rotation and Revocation | EV-L3 (31) | **not Phase-1** | key 자료·custody·서명검증 = 런타임+security(MAC 이연, 설계 #4/#5 동형). (파생: capability validity가 주입 `issuer_key_status` revoked/unknown⇒무효 소비) | §18.2 (692–699) |
| -013 | Egress Bypass Test | EV-L3+Security (32) | **not Phase-1** | egress+security bypass = 런타임; tos는 non-transmitting(firewall §4). (파생: capability의 env/mode claim + cross-env 거부 술어, §18.4) | §18.4 (705–707), §11.3 |
| -014 | Epoch Registry Failure | EV-L3 (33) | **predicate-only** | registry-unavailable(주입 flag)⇒새 permissive 전부 DENIED + 기존 PRESERVED | §20 표 (749), §13.1 |
| **-015** | Authority Evidence Replay | EV-L2 (34) | **predicate-only** | authority 레코드 = DigestBoundArtifact(§19 audit 필드) + ordering; 결정적 replay substrate | §19 (711–731), §23 SA-AC-015 (871–873) |

**Phase-1 EV-L1 substrate 강도**: 가장 강한 것은 **-005**(`conservative_usable_lifetime` REUSE — Time
TIME-EV-006 substrate 선례; register 최저 EV-L2/3)와 **-009**(restrictive dominance 양방향 property —
순수 우선순위 판정)다. **-006/-011**은 `anchor_valid` REUSE(Time TIME-EV-004/005 substrate 선례).
나머지는 술어 substrate.

**predicate-only(EV 주장 금지)** = {001, 002, 003, 004, 005, 006, 007, 009, 010, 011, 014, 015} (12행).
**not-Phase-1** = {008(+Broker hard fence), 012(key/custody), 013(+Security egress)} (3행). **닫는 SA-EV
= 0건.**

> **완결 주장 규율(설계 #2 §7·#4 §7·Time §1·#5 §1 상속)**: Phase 1은 *모델 + property test 저작*까지다.
> **어떤 항목도 "EV-L1-complete"로 주장하지 않는다** — SA-EV는 최소 레벨이 전부 EV-L2 이상이라 애초에
> EV-L1으로 닫을 수 없다. 모든 주장에 규율 태그: **"EV-L1 predicate substrate only; SA-EV-### remains
> NOT_IMPLEMENTED pending EV-L2/L3 (008 +Broker, 013 +Security) fault injection."** VER register의
> Owner/Reviewer는 TBD이고 수용은 Independent-Safety-Reviewer(저자 아님)의 별도 서명(IMPLEMENTATION-PLAN
> §3 line 153/157)이다.

**ADR-002-003 조항 → 모델 산출물 매핑**: §5 정의 → §2 어휘/모델; §6 SA-INV → 전 절 불변식 라벨; §7
precedence → §5.3; §8 roles → §2(비권위 role 주석) + §4.1; §9 capability → §2.2; §10 epoch lifecycle →
§2.3·§5.1; §11 fencing → §5·§6(술어; 실제 강제 이연); §12 currentness → §5.4; §13 partition → §6.5;
§14 lease validity → §6.3·§6.4; §15 clock → §3.4(time REUSE); §16 halt → §5.3; §17 re-arm → §6.6;
§18 security → §4.1·§2(env/mode·key-status 주입); §19 audit → §2(covered 필드).

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True, extra="forbid")`,
`tos.canonical.FrozenModel` REUSE — `_base.py` line 66–69)로 저작한다. frozen은 capability/epoch
immutability와 append-only(§10.4 "Epoch state SHALL survive process restart", §19 audit)의 레코드
수준 실현이며, **모델에는 update/delete 연산이 존재하지 않는다**(설계 #4 §2.0 규율 상속). 필드명은 ADR
§9(capability claims)·§14.2(lease anchor)·§19(audit)의 용어를 그대로 쓴다(스펙 용어 = 코드 용어, 설계
#1 §2.4).

### 2.0 소유권 골격 — authority는 capacity·time의 상류-형제, scalar만 참조

Safety Authority는 capability를 **발행**하고 epoch advance·lease 발행을 **승인**하나(§8.1 line 249–256),
**직접 broker 주문을 전송하거나 risk capacity를 mutate하지 못한다**(§8.1 line 257 "SHALL NOT directly
transmit broker orders or mutate risk capacity outside defined authoritative interfaces"). 이는 #5
capacity≠authority의 **authority 측 대칭**이다: authority가 issue한 capability/grant는 RCL에 대해 **비권위
입력**이고(#5 §4.1), 오직 RCL commit만 capacity를 mutate한다. ⇒ authority 모델은:

- RCL capacity 아티팩트(reservation·protective pool·capacity-lease)를 **scalar 참조 블록**으로만 담는다
  (`reservation_identity`·`reservation_revision`·`protective_pool_identity`·`capacity_lease_id`·
  `capacity_lease_digest` — 문자열/정수). **`tos.rcl` 미import.** 선례: RCL의 `ProtectiveLease.
  safety_authority_epoch_binding`(rcl `records.py` line 389)이 이미 authority epoch을 *scalar 정수*로
  담는다 — 즉 capacity↔authority 링크는 **이미 scalar**이며 본 문서는 그 대칭 방향(authority가 capacity를
  scalar 참조)을 확정할 뿐이다.
- Time Health **Snapshot**을 **scalar 참조**(`trustworthy_time_snapshot_id`·`time_health_generation`)로
  담는다(capsule/evidence가 time snapshot을 scalar로만 담은 것과 동형 — Time §2.0). 단 lease 유효성
  *계산*에 필요한 monotonic **좌표 타입**(`TimeContinuityIdentity`·`MonotonicReading`)과 **술어**는
  `tos.time`에서 import한다(§0.4b) — snapshot 참조(scalar)와 좌표-계산(import)은 별개다.

### 2.1 digest-bound / plain-frozen / reference 분류 (총괄)

| 아티팩트 | 종류 | id 필드(독립) | digest 필드 | covered = ? |
|---|---|---|---|---|
| Safety Authority Capability (§9 line 313–360) | **DigestBoundArtifact + 독립 id** | `capability_id`(+`nonce`) | `canonical_digest` | §9.1 claim list(§2.2) |
| Authority Epoch Transition Record (§10, §19 line 713–729) | **DigestBoundArtifact + 독립 id** | `transition_id` | `canonical_digest` | domain·old/new epoch·leader·reason·witness·fence 결과(§2.3) |
| Degraded Lease Ownership Record (§14.2 line 545–556) | **DigestBoundArtifact + 독립 id** | `lease_ownership_id` | `canonical_digest` | receipt/host identity·monotonic anchor·approved duration·drift/susp 가정·authority epoch·capability digest·exclusive scope(§2.4) |
| Authority Epoch State / floor (§8.2, §10) | **plain FrozenModel** | — | — | (§5 술어 입력 — `authority_epoch_current` floor) |
| Generation Vector (§4.7; capsule 템플릿 naming 재사용 distinct superset) | **plain FrozenModel** | — | — | (좌표 비붕괴 vocabulary — §4.7) |
| Currentness Witness (§12.1 line 454–456) | **plain FrozenModel** | — | — | (§5.4 witness 술어 입력; `within_bound: bool\|None`) |
| Authority State (precedence lattice, §7) | **StrEnum + plain** | — | — | (§5.3 dominance/transition 입력) |
| Partition Authority Verdict (§13.1) | **plain FrozenModel** | — | — | (§6.5 deny-table 출력) |
| Re-arm Checklist / Verdict (§17.1) | **plain FrozenModel** | — | — | (§6.6 conjunctive checklist) |
| Capability Validity Inputs (§1 6-part; §9.4 cache; §18) | **plain FrozenModel** | — | — | (§5.2 validity 술어 입력 — currentness/revocation/consumption/key-status/env-mode) |
| Lease Reassignment Inputs (§14.5) | **plain FrozenModel** | — | — | (§6.2 — `hard_fence_proven`·`lease_expiry_fence_elapsed`: bool\|None) |
| RCL capacity 참조 블록 (reservation·pool·capacity-lease) | **plain FrozenModel(참조)** | id+revision+digest scalar | — | (`tos.rcl` 미import) |
| Time snapshot 참조 블록 | **plain FrozenModel(참조)** | snapshot_id+generation scalar | — | (좌표 타입은 `tos.time` import) |
| Live Auth / Hard Envelope / Runtime Profile 참조 | **plain FrozenModel(참조)** | id+version+digest scalar | — | (ADR-002-007/014 소유) |

> **IdDerivedArtifact 채택 아티팩트 = 0건.** 모든 authority ledger 시민은 **독립·서비스 할당 identity**를
> 가진다 — capability identity(§9.1 line 317), issue sequence(line 331), epoch(§5.2 line 113 "durable
> generation number")은 content가 아니라 서비스/도메인 할당이고, §18.3 replay protection(line 701–703)이
> same-id/diff-content 탐지를 요구하므로 `id⊥digest`여야 한다. `id=f(digest)`면 same-capability-id +
> different-bytes(위조·replay) 충돌이 unreachable이 된다(§3.1). ⇒ **전부 `IndependentIdArtifact`(PROMOTE된
> core base) 상속, `IdDerivedArtifact`(capsule 전용) 미채택**(설계 #4·Time·#5 동형의 일관 판정).

### 2.2 Safety Authority Capability (§9 line 311–367)

`IndependentIdArtifact` 서브클래스, 독립 `capability_id` + `nonce`. covered(Layer-1) = §9.1(line
313–335) 필수 claim: `capability_type`(§9.2), `issuer_identity`, `authority_domain`,
`safety_authority_epoch`, `subject_service_identity`, `environment_and_mode`(live/paper — §18.4),
`account_scope`, `instrument_or_class_scope`, `permitted_action_class`, `maximum_quantity`,
`maximum_risk_vector_effect_or_reservation_identity`(RCL scalar 참조), `hard_safety_envelope_version`,
`runtime_safety_profile_version`, `issue_sequence`, `validity_rule`, `use_semantics`(single/bounded/
idempotency — §9.3), `parent_authorization_or_protective_lease_identity`, `integrity_evidence`
(구조만; MAC 검증 이연 — §9.2 (f)). `authority_effect` = all-false(§4.1).

- **`capability_type`(§9.2 line 341–354)**: `CapabilityType(StrEnum)` = `{NORMAL_RISK_INCREASING,
  NORMAL_RISK_REDUCING, DEGRADED_PROTECTIVE, CANCEL_REQUEST, PROTECTIVE_CANCEL_OR_REPLACE, HALT,
  CONTAIN, RECONCILIATION_ONLY, REARM, LIMIT_ACTIVATION}`(ADR verbatim). **type 이름이 안전을
  결정하지 않는다**(§9.2 line 356 "The names do not determine economic safety") — restrictive/permissive
  분류는 §5.3의 별도 술어이고, HALT/CONTAIN/REARM/LIMIT_ACTIVATION도 하나의 capability 레코드로
  표현된다(별도 record class 없음 — §9.2가 이를 capability *type*으로 규정하므로).
- **`command_identity` ⊥ `canonical_digest`**(§3.1): §18.3 replay + §9.3 single-use 위조 탐지. same
  capability_id + diff bytes ⇒ `classify_record_pair` = CRITICAL_CONFLICT(REUSE core).
- **`_REQUIRED_COVERED`**(ISSUED에서 concrete 필수, TBD/null이면 DRAFT — `_base.py` line 135–155):
  **구조적 식별·스코프·type·epoch·버전** 필드로 한정 — `capability_type`, `issuer_identity`,
  `authority_domain`, `safety_authority_epoch`, `subject_service_identity`, `environment_and_mode`,
  `account_scope`, `permitted_action_class`, `issue_sequence`, `hard_safety_envelope_version`,
  `runtime_safety_profile_version`. **numeric bound(`maximum_quantity`·risk-vector magnitude)는 required로
  넣지 않는다** — 프로파일 bound가 Phase-1에서 null/PROPOSED이므로 required면 모든 capability가 DRAFT로
  떨어진다(Time §2.1·#5 §2.2 규율 상속). 대신 numeric claim 누락은 **소비 술어(§5.2)의 numeric-claim
  precondition 조항에서 `None`⇒invalid**로 거부된다(Gap 봉합 — §5.2 하단; §9.1 "missing claims are denial").
  즉 `_REQUIRED_COVERED` 밖(ISSUED 도달성 보존)이되 **validity 술어가 소비 시점에 fail-closed**로 막는다.
- **"Missing claims are denial, not defaults"**(§9.1 line 337): validity 술어(§5.2)는 필수 claim 중
  하나라도 None이면 **invalid**를 반환한다(default로 채우지 않음). issue()는 `tos.canonical` registry +
  `EVL1ProvisionalCanonicalizer`(`ev-l1-provisional-0`) REUSE, 신규 canonicalizer 없음(프로덕션 canonical
  form은 Phase-0, §9.2).

### 2.3 Authority Epoch Transition Record (§10 line 370–408; §19 line 711–729)

`IndependentIdArtifact`, 독립 `transition_id`. covered = §19(line 713–729) audit 필드: `authority_domain`,
`old_epoch`·`new_epoch`, `leader_identity`, `transition_reason`(§10.2 line 385–394 8종 trigger),
`currentness_witness`(§2.4), `capability_digest_and_type`, `subject_identity`, `scope`,
`fencing_result`, `egress_acceptance_or_rejection`, `safer_state_precedence_applied`,
`operator_approvals`, `rearm_prerequisites_and_outcome`, `local_monotonic_anchor_evidence`(degraded
lease용). append-only 시퀀스 원소.

- **단조 epoch(§5.2 line 113, §10.5 line 406–408)**: `new_epoch > old_epoch` 엄격 증가; **reset/
  wraparound 금지**(§10.5 "Epoch reuse, reset, or wraparound is prohibited") — 모델은 epoch을 감소/재사용
  시키는 연산을 제공하지 않는다(구성적 부재).
- **§10.4 line 402–404**: "Epoch state … SHALL NOT be reconstructed from the highest epoch observed in
  an asynchronous event stream without authoritative proof." ⇒ 모델은 event stream max로부터 epoch을
  구성하는 경로를 **제공하지 않는다**(Time "wall로부터 anchor 재구성 없음" 동형의 구성적 부재).

### 2.4 Degraded Lease Ownership Record (§14.2 line 545–556) — authority/ownership 측, RCL capacity lease와 구분

`IndependentIdArtifact`, 독립 `lease_ownership_id`. **RCL의 `ProtectiveLease`(capacity 측 — 소비 vector·
pool 소속)와 개념적으로 구분되는 authority/ownership 측 레코드**다: §14.2는 execution-side owner가 lease를
받을 때 durably 결부해야 할 것을 규정한다. covered = `receipt_process_identity`, `host_or_runtime_identity`,
`local_monotonic_anchor`(**`tos.time.TimeContinuityIdentity` REUSE** — §3.4), `approved_maximum_duration`,
`drift_and_suspension_assumptions`, `safety_authority_epoch`, `capability_digest`, `exclusive_scope`,
`referenced_capacity_lease_id`(RCL scalar 참조), `referenced_protective_pool_identity`(RCL scalar).

- **§14.2 line 547–556의 최소 바인딩을 1:1 저작**하되 monotonic anchor는 time 타입을 REUSE(재정의 금지).
- **exclusivity 좌표**: `exclusive_scope` + `safety_authority_epoch` + `current_owner_identity`가 SA-INV-006
  (exclusive offline protective scope, line 185–187) 술어의 좌표다(§6.1).
- **RCL capacity lease와의 관계**: authority ownership 레코드는 RCL capacity lease를 **scalar
  (`referenced_capacity_lease_id`·digest)로 참조**한다. RCL `ProtectiveLease.safety_authority_epoch_binding`이
  역방향 scalar 참조를 이미 담으므로 두 레코드는 **서로 import 없이 epoch·id scalar로 교차 참조**한다(§0.3).

### 2.5 Injected 술어 상태 모델 (plain FrozenModel — §5/§6 입력)

RCL이 `WriterFenceState`·`FenceCoordinates`·`PartitionVerdict`를 저작한 것과 동형으로(rcl `state.py`),
authority는 술어가 fold하는 **주입 상태**를 plain frozen으로 저작한다(§0.2: 전부 주입 상태 위 순수 함수):

- **`AuthorityEpochState`**: `{authority_domain, current_epoch_floor: int|None}` (도메인당 current
  accepted epoch floor). `authority_epoch_current` 입력. `None` floor ⇒ fail-closed(§5.1).
- **`GenerationVector`**(§4.7): 좌표 비붕괴 vocabulary — 상술 §4.7.
- **`CurrentnessWitness`**(§12.1): `{present: bool, within_containment_bound: bool|None, witness_source:
  str|None, conflicting: bool}`. 설계 #2 `Freshness{within_bound: bool|None}` fail-closed 패턴 REUSE —
  `within_containment_bound=None` ⇒ UNKNOWN ⇒ deny(§5.4).
- **`CapabilityValidityInputs`**: `{currentness: CurrentnessWitness, revocation_status:
  str|None, superseded: bool|None, consumed: bool|None, issuer_key_status: str|None,
  environment_and_mode_matches: bool|None, dominating_restriction: bool}` — §1 6-part + §9.4 cache +
  §18 key/env. 임의 None ⇒ invalid(§5.2).
- **`LeaseReassignmentInputs`**(§14.5): `{prior_owner_scope, hard_fence_proven: bool|None,
  lease_expiry_fence_elapsed: bool|None}`. 둘 다 아니거나 None ⇒ 재할당 금지(§6.2).
- **`RearmChecklist`**(§17.1): 14개 전제 각각 `bool|None` + `limit_enlarger_principal`·`armer_principal`
  (SoD). `RearmVerdict{armable: bool, authority_effect: AllFalse}` 출력(§6.6).
- **`AuthorityState`**(§7): `StrEnum = {HALTED, CONTAINED, DEGRADED_PROTECTIVE, LIVE_RESTRICTED,
  LIVE_NORMAL}`(ADR line 228–233 verbatim). precedence rank는 §5.3.

---

## 3. canonical / ordering / time REUSE 계약 (+ rcl 경계)

### 3.1 canonical REUSE + `id=f(digest)` 미채택 (설계 #4·#5 §3.1 상속)

authority ledger 시민(§2.1 표 상단 3종)은 `tos.canonical.DigestBoundArtifact`(`_base.py` line 91–246)의
digest 검증(`canonical_digest == H_ver(canonicalize(covered))`, line 171–205)과 **PROMOTE될
`IndependentIdArtifact`**(§0.4c)의 "issued 시 concrete 독립 id" 검증을 REUSE한다. canonicalizer는
`EVL1ProvisionalCanonicalizer`(`ev-l1-provisional-0`) REUSE, 신규 canonicalizer 없음(§9.2). **`id=f(digest)`
미채택** 근거는 §0.4a·§2.1(§18.3 replay + §9.3 single-use 위조 탐지). same-capability-id/diff-bytes 충돌
분류기 `classify_record_pair`는 **이미 core**(`tos.canonical`, #5 PROMOTE 완료 — `record_pair.py`)이므로 그대로
REUSE: authority가 capability/epoch/lease 쌍에 적용해 `CRITICAL_CONFLICT`(§18.3 위조/replay)·`IDEMPOTENT_DUP`
(§9.3 정당 재제출)을 구분한다. `NOT_COMPARABLE`(null digest = DRAFT)로 false conflict 방지(REUSE 그대로).

### 3.2 ordering REUSE (§7 HALT-vs-permissive 순서 · §9.1 issue sequence)

authority는 발행 순서·HALT-vs-permissive 순서를 **신규 저작하지 않고** `tos.ordering`(Time §5로 PROMOTE
완료, `tos/src/tos/ordering/_ordering.py`)의 `OrderingEvent`·`compare_order`를 REUSE한다:

- capability `issue_sequence`(§9.1 line 331)를 `OrderingEvent.source_native_sequence`(same-continuity)에
  매핑. 발행자 continuity가 다르면 `compare_order`가 `AMBIGUOUS`를 반환(교차-continuity 순서 미생성 —
  §7 line 241–242의 "stale HALT는 적용 가능하나 stale permissive는 불가"를 순서로 강제하지 않고, dominance는
  §5.3의 별도 술어가 순서-무관하게 판정한다).
- **wall clock은 순서를 만들지 않는다**(`_ordering.py` line 22–24) — §5.2 line 115 "An epoch is not a
  timestamp"와 정합. epoch은 정수 좌표이지 시각이 아니다.

> **주의(리뷰어 선제)**: HALT dominance(§5.3)는 **`compare_order`에 의존하지 않는다.** dominance는
> "restrictive는 permissive를 지배(발행순서 무관)"라는 **순수 우선순위 판정**이며(SA-INV-010), ordering은
> 오직 same-issuer sequence 감사용이다. 두 개념을 섞지 않는다(Time MAJOR-1의 좌표 혼동 방지 정신 계승).

### 3.3 `tos.rcl` 경계 — 형제, scalar만, import 금지 (§0.4d)

RCL은 **capacity 측 형제**다. authority는 다음을 **재사용하지 않고 import하지 않는다**:

- **`writer_fenced`(rcl `predicates.py` line 479)**: Writer Epoch/membership/restore/revision 4좌표 fence.
  **Safety Authority Epoch은 별개 좌표계**(§5.2, §27 OQ2 line 953–954 collapse 금지). authority는 자체
  `authority_epoch_current`/`authority_epoch_fenced`를 `AuthorityEpochState` 위에 저작(§5.1). 공유 원자는
  trivial monotonic-floor scalar뿐이며 capability-type 비대칭 때문에 로컬 재표현이 정당(§0.4d) — **fence
  PROMOTE 검토 후 기각.**
- **`ProtectiveLease`(rcl `records.py` line 346)**: capacity 측 lease(소비 vector·pool). authority는
  **ownership 측**(§2.4)을 별도 저작하고 capacity lease를 scalar 참조. RCL `ProtectiveLease.
  safety_authority_epoch_binding`이 이미 authority epoch scalar를 담으므로 링크는 scalar.
- **`partition_verdict`(rcl `predicates.py` line 683)**: RCL은 *capacity* action(mutation/claim/release)에
  대한 deny-table. authority는 *authority* action(new risk-increasing/capability authorization/renewal/
  re-arm/limit-enlargement — §13.1 line 480–485)에 대한 별도 `partition_authority_verdict`를 저작(§6.5) —
  action 집합이 다르므로 재사용 아님(둘 다 quorum/control-plane unknown⇒전부 DENIED fail-closed 정신은 동형).
- **`AllFalseAuthority`(rcl `_base.py` line 83)**: 각 패키지가 **로컬 재표현**하는 패턴(capsule
  `SnapshotAuthority`·time `AllFalseAuthority`·evidence `AllFalseFlags`·rcl `AllFalseAuthority`·**dsl
  `AllFalseAuthority`(dsl `_base.py` line 98)** — 전부 로컬, flag 이름 상이). authority도 authority-specific
  flag(§4.1)로 **로컬** 저작. **PROMOTE 아님** — 이것이 §0.4c `IndependentIdArtifact` PROMOTE와 다른 축임에
  주의: all-false는 **flag 이름이 패키지별로 달라** 로컬이 정당하나, `IndependentIdArtifact`는 **로직 변이가
  없어** promote 대상이다(§0.4c).

`tos.rcl` import는 형제 규율 위반 + 좌표 붕괴이므로 **금지**. §7.1 import-closure가 `tos.rcl` 부재를 assert.

### 3.4 `tos.time` REUSE — import-and-compose (§0.4b; 최초 sibling→sibling edge)

lease 유효성은 monotonic-time-bounded(§14/§15)이므로 authority는 `tos.time`을 **import**해 다음 순수 술어·
타입을 REUSE한다(재저작 금지 — DRY·안전):

| ADR-002-003 조항 | REUSE 대상(`tos.time`) | 근거 |
|---|---|---|
| §14.2 local monotonic anchor (545–556) | `TimeContinuityIdentity`·`MonotonicReading` (element 타입) | lease를 monotonic anchor에 결부 — 좌표 타입 재사용 |
| §14.3 conservative lifetime (558–561) | `conservative_usable_lifetime(...)` | "signed duration − uncertainty − safety margin" 공식 동일; **음수항 fail-closed 가드**(Time v1.2 REJECT 수정) 상속 |
| §14.4 invalidating events (563–576) | `anchor_valid(...)` | restart/reboot/monotonic reset/discontinuity/suspension⇒무효(SA-INV-009 동형) |
| §15.3 unknown time health invalidates (605) | `state_permits_new_normal_risk`·`anchor_valid` None⇒invalid | unknown⇒fail-closed |
| §16.3/§17.3 non-revival (678) | `recovery_generation_revives_nothing` (패턴 REUSE 또는 authority-local 미러) | 무효화된 lease/capability는 새 generation에서도 revive 안 됨 |
| §15.1 wall clock (591–593) | (구조적 배제) | wall은 lease expiry 단독 근거 금지 — time이 이미 wall을 결정에서 배제 |
| §10 ordering ambiguity | `tos.ordering.compare_order` | (§3.2) |

- **compose로 seam 봉합**(Time MEDIUM-2 계승): authority의 `degraded_lease_valid`(§6.3)·
  `degraded_lease_invalidated`(§6.4)는 `conservative_usable_lifetime`·`anchor_valid`를 **내부 호출**해
  injected-boolean seam을 두지 않는다(Time `effective_snapshot_age_bound_from_continuity` compose 선례
  동형). 잘못된 `lease_time_valid=True` 주입 경로가 존재하지 않는다.
- **의존 방향**: `authority → time → ordering → canonical`(단방향, acyclic). time은 authority를 참조하지
  않는다. §7.1 import-closure가 `tos.time`·`tos.ordering`·`tos.canonical` **존재 허용**, 나머지 tos 형제
  부재를 assert.

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **fail-closed discipline**:
빈/누락 집합·None 좌표에 대한 술어는 절대 vacuous permit이 되지 않으며, permissive는 *양성 증명*을
요구하고, 각 가드에 **negative/canary property**(가드가 실제로 발화함)를 붙인다.

### 4.1 authority ≠ enforcement (중앙 불변식 — SA-INV-003; §1; §5.3; §8.1)

설계 #4 evidence≠authority(ERI-INV-001/014)·#5 capacity≠authority(RCLP-INV-001/012)의 **authority 측
변주**다. **여기서 authority 아티팩트(capability)가 발행되는 대상이므로 "permissive capability는 비권위"라고
말할 수 없다** — 대신 4개 층:

1. **서명·계산·보유 ≠ 현재 authority**(§1 line 17 "A Safety Authority instance may calculate or sign a
   decision, but an execution path may accept a permissive decision only when it can prove [6 things]";
   §5.3 line 121 "A signature alone is not Current Epoch Proof"; §21.2 line 760–762 "Signed Token Without
   Epoch … Rejected"). 모델은 capability를 **보유/서명**하는 것으로부터 authorization을 도출하는 경로를
   **제공하지 않는다** — 유효성은 오직 `permissive_capability_valid` 술어(§5.2)를 통해서만이고, 그조차
   **필요조건**이지 완결이 아니다(조건 6 egress 독립검증은 런타임 — §0.2). **canary**: 서명 필드가 present여도
   currentness None이면 술어는 invalid.
2. **모델은 non-transmitting·grants-no-runtime-effect**(all-false 블록): 모든 authority 아티팩트의
   `authority_effect` = `AllFalseAuthority` 서브클래스(authority-local, §3.3), flag = `{is_current_
   authority_by_possession, self_transmits, self_mutates_capacity, self_releases_capacity, self_rearms}`
   전부 `False`; 하나라도 `True`면 **구성 실패**(설계 #2 `SnapshotAuthority._all_authority_false` 패턴
   로컬 REUSE — capsule `_base.py` line 70–78). 근거: §8.1 line 257(leader "SHALL NOT directly transmit
   … or mutate risk capacity").
3. **loss of proof = loss of authority**(SA-INV-003 line 173–175; §1 line 28 "The system SHALL NOT infer
   permissive authority from silence, cached success, prior health, or an unavailable control plane"):
   임의 currentness/epoch/witness 좌표가 None/UNKNOWN ⇒ risk-increasing 거부. 전 술어 fail-closed.
   **canary**: 빈 witness·None epoch은 vacuous permit로 빠지지 않는다.
4. **documentation/audit ≠ authority**(§19 line 731 "Audit evidence is required for reconstruction but
   does not substitute for runtime prevention"): validity 술어는 audit/reason/operator-note 필드를
   authorization 입력으로 **읽지 않는다**(입력은 epoch/currentness/lease/dominating-state 좌표뿐). 이 불변식이
   authority가 하류 evidence를 import하지 않는 firewall 근거이기도 하다(§0.3).

### 4.2 epoch advance ≠ economic-effect release (SA-INV-004 line 177–179)

"Advancing the Safety Authority epoch revokes future authority. It does not release capacity, cancel
broker orders, erase potentially-live quantity, or prove that old economic effects no longer exist."
⇒ 모델은 epoch advance로부터 capacity release·order cancel·quantity erase를 도출하는 연산을 **제공하지
않는다**(구성적 부재; #5 INV-005 no-expiry-of-economic-effect 동형, capacity 측은 RCL 소관 — scalar 참조).
**canary**: `advance_epoch` 후에도 참조된 potentially-live/UNKNOWN capacity scalar는 불변.

### 4.3 단조 epoch floor + 좌표 비붕괴 (SA-INV-001/002; §5.2; §10.5; §27 OQ2)

- **단조 floor**: `AuthorityEpochState.current_epoch_floor`는 committed epoch advance로만 전진하며 **결코
  역행하지 않는다**(§5.2 line 113). floor 미만 epoch은 fenced(§5.1). property: floor monotone; reset/
  wraparound 표현 불가(§10.5).
- **좌표 비붕괴(핵심 canary)**: `authority_epoch_current`는 `safety_authority_epoch` **좌표만** 검사하며
  Writer Epoch/membership/restore/recovery/time-health generation을 **대입 불가**하다. **canary**:
  `safety_authority_epoch` 자리에 `writer_epoch` 값을 넣어도 authority fence를 만족시키지 못한다(두 좌표는
  서로 다른 floor를 가진다 — §4.7 GenerationVector가 이를 구조적으로 분리). 근거: §27 OQ2 "without
  collapsing authority separation."

### 4.4 non-revival (§10.5; §16.3; §17.3; §14.4)

- **restart/restore/rotation/re-arm은 옛 capability를 revive하지 않는다**: §17.3 line 676–678 "Re-arm
  SHALL issue new capabilities under the current epoch. Previously issued live capabilities are not
  revived." 모델은 "generation/epoch 증가 ⇒ 무효 capability 유효성 복원" 연산을 **제공하지 않는다**
  (`recovery_generation_revives_nothing` 패턴 REUSE/미러 — Time·#5 동형, 항상 True). **canary**: generation
  N에서 무효화된 lease/capability는 N+1 이후에도 revive 안 됨.
- **HALT는 명시 re-arm까지 단조**(SA-INV-011 line 205–207): 일단 HALTED면 이전 발행 permissive는 live를
  복원 못 함; re-arm은 새 시퀀스 + current epoch 요구(§5.3·§6.6).

### 4.5 append-only + same-id/diff-bytes 충돌 (§19; §18.3)

- 모델에 update/delete 연산 부재(§2.0). epoch/capability/lease lifecycle 변화는 새 레코드 append로 표현.
- **충돌 술어**(§3.1): `classify_record_pair`(core REUSE). same capability/epoch/lease identity + diff
  content ⇒ `CRITICAL_CONFLICT`(contain + 양쪽 보존, no merge — §18.3 replay/위조). same id + same bytes ⇒
  `IDEMPOTENT_DUP`(§9.3 single-use 정당 재제출). **canary**: id⊥digest이므로 CRITICAL_CONFLICT reachable
  (id=f(digest)면 unreachable을 회귀로 고정).

### 4.6 restrictive dominance는 발행순서 무관 (SA-INV-010/011; §7)

`HALT`·restrictive state transition은 임의 outstanding permissive capability를 **지배**하며, 이는 **발행/
도착 순서와 무관**하다(§7 line 239–242; §20 표 line 746 "HALT races with permissive grant; HALT
dominates"). 상술 §5.3.

### 4.7 generation-vector 좌표 vocabulary (§4.7 결정; §27 OQ2)

**핵심 난제**: ADR-002-003 epoch, ADR-002-012 Writer Epoch, membership/restore/recovery generation,
time-health generation, process generation/consensus term을 **하나의 좌표로 붕괴시키지 않는다**(§27 OQ2;
Time §2.0 generation_vector; ADR들이 "SHALL NOT be treated as equivalent unless proven"). `GenerationVector`
(plain FrozenModel)를 **한 번만, coherently** 저작한다. **이는 `DECISION-CONTEXT-CAPSULE-template.yaml`의
`generation_vector` 블록(template line 44–52)의 복사본이 아니다(m3 정정)** — 그 블록은
`safety_configuration_generation`·`broker_capability_profile_version`·`time_health_generation`·
`recovery_generation`·`authority_epoch`·`deployment_generation`·`identity_generation`·
`evidence_policy_generation`라는 **materially 다른 좌표 세트**를 쓴다. authority의 `GenerationVector`는 그 템플릿의
**겹치는 좌표 naming을 재사용하는 distinct superset**이며(스펙 용어 = 코드 용어 원칙 하 `time_health_generation`·
`recovery_generation`을 동명 재사용), authority 고유 좌표(Writer Epoch·membership/restore/process generation)를
추가한다. **naming 정책(m3)**: 템플릿은 `authority_epoch`를 쓰나 authority 층은 **좌표 명료성**을 위해
`safety_authority_epoch`를 유지하고(Writer Epoch과의 비붕괴를 필드명으로 강제), 템플릿의 `authority_epoch`는
**동일 좌표·다른 이름으로 교차참조**한다(§4.3 canary가 이 비붕괴를 검증).

| 좌표 | 필드 | 소유 ADR | authority 처리 |
|---|---|---|---|
| Safety Authority Epoch | `safety_authority_epoch` | ADR-002-003 §5.2 | **authority가 소유·fence**(§5.1) |
| Writer Epoch | `writer_epoch` | ADR-002-012 | **reference-only scalar**(RCL이 fence; authority는 대입/fence 금지) |
| membership generation | `membership_generation` | ADR-002-012 | reference-only scalar |
| restore generation | `restore_generation` | ADR-002-012/017 | reference-only scalar |
| recovery generation | `recovery_generation` | ADR-002-017 | reference-only scalar(re-arm 전제 §6.6) |
| time-health generation | `time_health_generation` | ADR-002-008 | reference-only scalar(time snapshot 참조) |
| process generation / consensus term | `process_generation` | (§27 OQ2 non-collapse) | reference-only scalar |
| profile generations | `hard_safety_envelope_generation`·`runtime_safety_profile_generation` | ADR-002-014 | reference-only scalar |

- **불변식(§4.3 canary)**: 각 fence/currentness 술어는 **자기 좌표만** 검사한다. 두 좌표를 equal/substitutable로
  다루는 연산은 모델에 **없다**. **canary**: 임의 두 서로 다른 좌표를 교환해도 authority fence 결과가 바뀌지
  않음(각자 독립 floor). broker-agnostic(어떤 좌표도 KIS 전용 아님).

---

## 5. validity / dominance / HALT 술어 세부 (§5)

**핵심 난제**: 실제 leader election·registry·egress 없이, **주입 상태 위 순수 술어**로 authority validity·
dominance를 fail-closed 모델링. 실제 강제(egress fence·hard fence·registry serialize)는 런타임(§0.2).

### 5.1 authority epoch currentness / fence (SA-INV-001/002; §5.1/§5.2)

`authority_epoch_current(claimed_epoch: int|None, authority_domain: str|None, state: AuthorityEpochState)
-> bool`: 다음이 **모두** 성립할 때만 True — `claimed_epoch`·`authority_domain`·`state.current_epoch_floor`
None 아님; `authority_domain == state.authority_domain`; `claimed_epoch >= state.current_epoch_floor`.
하나라도 None 또는 domain 불일치 또는 stale(< floor) ⇒ **False**(fenced). `authority_epoch_fenced`는 그
부정(True=fenced). [SA-INV-002; SAFE-011]

- **canary(fail-closed)**: `∀ 임의 좌표 None ⇒ fenced`(vacuous admit 방지, RCL `writer_fenced` None⇒fenced
  동형); `claimed < floor ⇒ 항상 fenced`; **가드 발화 존재성**(fenced가 되는 입력이 반드시 존재).
- **§5.2 line 115 "An epoch is not a timestamp"**: epoch은 정수 좌표; 술어는 wall/monotonic과 비교하지
  않는다(좌표 비붕괴 §4.3).
- **B_stale_epoch_reject = 0**(프로파일 line 177–181, "synchronous … compare-and-set; 0 = no time window"):
  이 fence를 **시간 창 없는 동기 순수 술어**로 모델링함을 프로파일이 지지(§8).

### 5.2 permissive capability validity — 6-part 결합 (§1 line 17–24)

`permissive_capability_valid(capability, state: AuthorityEpochState, inputs: CapabilityValidityInputs,
lease_ok: bool) -> bool`: §1의 6조건 중 EV-L1-decidable 5개를 결합(6번째 egress 독립검증은 런타임 — 아래
경계):

1. **authorized issuer identity**(§1-1): `inputs.issuer_key_status == "valid"`(revoked/unknown/None ⇒
   invalid — §18.2 key; SA-EV-012 파생). 
2. **current domain + epoch**(§1-2): `authority_epoch_current(capability.safety_authority_epoch,
   capability.authority_domain, state)`.
3. **capability scope matches action**(§1-3): `capability.permitted_action_class`·`account_scope`·
   `instrument_scope`가 요청과 일치(주입 요청 좌표와 비교) + `environment_and_mode_matches`(§18.4 cross-env —
   None/False ⇒ invalid; SA-EV-013 파생).
4. **validity positively established — capability-type로 gate(M2 봉합)**(§1-4; §9.4 line 366; SA-INV-005):
   **risk를 늘리는 normal type**(`NORMAL_RISK_INCREASING` 등)은 조건 4 = **online currentness ONLY**
   (`inputs.currentness.within_containment_bound == True`) — `lease_ok`로 **대체 불가**(§9.4 line 366 "Normal
   risk-increasing capabilities require an online currentness witness"; SA-INV-005 "No Cached Risk-Increasing
   Authority During Partition"). `lease_ok` 경로는 **오직 `capability_type == DEGRADED_PROTECTIVE`**일 때만
   조건 4를 충족하며 그조차 §6.3 degraded-lease 유효성을 통과해야 한다. None/False ⇒ invalid. **canary**:
   `NORMAL_RISK_INCREASING` + `lease_ok=True` + witness 부재 ⇒ **invalid**(lease가 normal risk의 currentness를
   대체하지 못함 — ungated OR fail-open 제거). (§9.4 cache≠current — §5.5; §5.4 currentness.)
5. **not consumed/superseded/revoked/invalidated**(§1-5): `inputs.consumed`·`superseded`·`revocation_status`
   중 any-true/None ⇒ invalid(fail-closed).
6. **egress independent verification**(§1-6): **런타임(§0.2)** — 모델은 이 조건을 **주장하지 않으며**,
   술어 True는 "execution-path 필요조건 5/6 충족"일 뿐 authorization 완결이 아니다(§4.1). 이 경계를 술어
   docstring·property에 명시(overclaim 방지).

- **필수 claim missing ⇒ invalid**(§9.1 line 337 "Missing claims are denial, not defaults"): capability의
  `_REQUIRED_COVERED` 미충족(DRAFT) 또는 조건들이 읽는 필수 좌표(issuer/epoch/domain/scope/type) None ⇒ 즉시
  invalid. **canary**: 모든 claim present여도 epoch stale이면 invalid; currentness None이면 invalid.
- **numeric-claim precondition ⇒ invalid(Gap 봉합 — §2.2 fail-closed의 술어 실체)**: `permissive_capability_valid`는
  위 6-part 결합에 **더해**, capability의 필수 numeric claim(`maximum_quantity`, `maximum_risk_vector_effect_or_
  reservation_identity` 링크)이 `None`이면 **소비 불가⇒invalid**를 **별도 precondition 조항**으로 검사한다(§9.1
  "missing claims are denial"). 이 numeric claim은 `_REQUIRED_COVERED`에 **넣지 않아**(§2.2) Phase-1 null 프로파일
  bound 하에서도 capability가 ISSUED에 도달하지만, **소비 시점**(validity 술어)에서 fail-closed로 거부된다.
  **canary**: `maximum_quantity=None`인 ISSUED capability ⇒ `permissive_capability_valid` **False**.

### 5.3 restrictive dominance + precedence lattice (SA-INV-010/011; §7)

- **precedence rank**(§7 line 227–233): `_PRECEDENCE_RANK = {HALTED:4, CONTAINED:3, DEGRADED_PROTECTIVE:2,
  LIVE_RESTRICTED:1, LIVE_NORMAL:0}` (높을수록 safer/dominant). `restrictive_dominates(current_state,
  permissive_capability) -> bool`: `current_state`가 DEGRADED_PROTECTIVE 이상(rank≥2)이거나 HALT/CONTAIN
  capability가 outstanding이면, 임의 permissive capability는 **거부**(True=dominated). **발행/도착 순서
  무관**(SA-INV-010 line 201–203). [SA-INV-010; SAFE-041]
- **양방향 canary(SA-EV-009 강 substrate)**: HALT와 permissive를 (a) HALT-먼저·(b) permissive-먼저 **양
  순서**로 주입 ⇒ **두 경우 모두** HALT dominates(§20 표 line 746). 순서 뒤집어도 결과 불변임을 property로
  고정(리뷰어 "order-dependence" 선제).
- **safer transition은 broad, permissive transition은 current authority 요구**(§7 line 239): 
  `safer_transition_allowed(from, to) -> bool` = `rank[to] >= rank[from]`(safer 방향은 항상 허용; monotonic·
  enlarge 불가); `permissive_transition_allowed(from, to, epoch_current: bool) -> bool` = `rank[to] <
  rank[from]`인 전이는 `epoch_current == True`일 때만(current Safety Authority 요구). **canary**: 
  `epoch_current=None/False` ⇒ permissive 방향 전이 불가.
- **stale HALT 적용 가능·stale permissive 불가**(§7 line 241–242): `restrictive_may_apply_when_stale`
  (HALT/restrictive는 authentic + enlarge-불가면 stale currentness에도 적용 가능 — §16.2 line 628–630);
  permissive는 §5.2 currentness 요구. **단 stale HALT의 "authentic" 판정은 서명/replay 검증(런타임+security,
  §18) 이므로 Phase-1은 "authentic 주입 flag + enlarge-불가 구조" 술어만**(SA-EV-013 not-Phase-1 경계).

### 5.4 currentness witness / cache≠current (§9.4; §12)

- `currentness_admissible(witness: CurrentnessWitness) -> bool`: `witness.present == True` **및**
  `within_containment_bound == True` **및** `conflicting == False`일 때만 True. `within_containment_bound
  is None`(미확립) 또는 witness 부재/stale/conflicting ⇒ **False**(deny; §12.2 line 458–465). 설계 #2
  `Freshness{within_bound: bool|None}`⇒UNKNOWN fail-closed 패턴 REUSE. [SA-INV-005; SAFE-011]
- **cache ≠ currentness**(§9.4 line 362–366 "Cached data SHALL NOT be interpreted as proof that its epoch
  is still current"): validity 술어는 capability 보유/캐시로부터 currentness를 도출하지 않는다 — currentness는
  오직 `CurrentnessWitness` 주입으로만(§4.1-1). **canary**: capability present + witness absent ⇒ risk-
  increasing invalid.
- **no grace period for new risk**(§12.3 line 467–469): validity 구간이 있어도 currentness 상실은 risk-
  increasing에 추가 grace를 만들지 않는다 — 모델은 "currentness 상실 후 grace" 연산 부재.

### 5.5 HALT effects·no-blind-cancel (§16.3/§16.4) — 술어 경계

- `halt_denies(capability_type) -> bool`(§16.3 line 634–641): HALT 상태에서 new risk-increasing·capability
  renewal·re-arm은 DENIED; protective control은 safe-state 정의대로 preserve. 순수 분류 술어.
- **§16.4 no blind cancel-all**(line 643–645): "SHALL NOT blindly cancel every protective order if
  cancellation could increase aggregate risk." 모델은 HALT로부터 "cancel-all" 연산을 도출하지 않는다(cancel은
  protective ownership + aggregate-risk 평가 = RCL capacity 소관, scalar 참조 — 구성적 부재).

---

## 6. lease exclusivity · partition · re-arm 술어 세부 (§13/§14/§17)

### 6.1 degraded lease exclusivity (SA-INV-006 line 185–187)

`lease_scope_exclusive(claimant_ownership_id: str|None, owner_records: Sequence[DegradedLeaseOwnershipRecord])
-> bool`(M1 봉합): 청구자(claimant)가 `(exclusive_scope, referenced_capacity_lease_id)`의 **유일한 현재
owner일 때만** True — 구체적으로 (i) `claimant_ownership_id`가 `owner_records` 안에 **present**하고, (ii) 그
scope+underlying capacity를 소유하는 owner가 **청구자 하나뿐**일 때만 True. **빈 집합 ⇒ False; 청구자 부재 ⇒
False; 2개 이상 owner ⇒ False(overlapping — CRITICAL, 양쪽 보존)**. v1.0의 `≤1 ⇒ True`는 빈 집합에서
`0 ≤ 1`로 **vacuous-True fail-open**(SA-INV-006 위반, ADR §24 Critical alert)이었고, 청구자-present+unique
요구가 이를 봉합한다. [SA-INV-006; SAFE-041]

- **overlapping은 표현 가능하되 탐지⇒CRITICAL**(리뷰어 "unrepresentable vs detected" 명시): 모델은 두
  overlapping owner 레코드를 **표현할 수 있게** 두고(탐지 대상), 술어가 이를 False로 판정한다(ADR §24 Critical
  alert 대응 — RCL `credible_union_capacity`가 conflicting branch를 drop하지 않고 보존한 정신 동형).
- **canary(양방향 발화, M1)**: **빈 집합 ⇒ False**(vacuous True 금지); **청구자 부재 ⇒ False**(`0 ≤ 1`
  fail-open 제거); **동일 scope 2 owner ⇒ False**; **청구자가 유일 present ⇒ True**(가드가 True로도 발화).
  빈 집합·청구자 부재는 "안전"이 아니라 exclusivity **미성립**이며, §6.3이 이 값을 소비해 fail-closed한다.

### 6.2 overlapping failover 금지 — hard-fence ∨ lease-expiry-fence (SA-INV-007 line 189–191; §14.5)

`overlapping_reassignment_forbidden(inputs: LeaseReassignmentInputs) -> bool`(True=금지): 새 owner에게
겹치는 scope를 할당하려면 §14.5(line 582–585)의 둘 중 하나가 **양성 확립**돼야 한다 — `hard_fence_proven ==
True`(former owner 전송 불가 증명) **또는** `lease_expiry_fence_elapsed == True`(worst-case 가정 하 경과).
**둘 다 아니거나 None ⇒ 금지(True)**. [SA-INV-007; §5.9 Lease-Expiry Fence; SAFE-048]

- **canary(fail-closed)**: `hard_fence_proven=None ∧ lease_expiry_fence_elapsed=None ⇒ 금지`; 
  `epoch advance 단독으로는 금지 해제 불가`(§14.5 line 580 "Epoch advancement alone does not prove that
  the former offline lease can no longer transmit" — `advance_epoch`가 이 술어 입력을 바꾸지 않음).
- **hard fence 자체는 런타임+broker(SA-EV-008 not-Phase-1)**: Phase-1은 `hard_fence_proven`을 **주입 flag**로
  받고 판정만; 실제 hard-fence(§5.8 broker 도달 불가 증명)는 이연.
- **lease-expiry-fence 지속시간은 누락 프로파일 키(§8)**: `lease_expiry_fence_elapsed` 판정에 필요한 worst-case
  duration(max-duration+drift+suspension+comms-delay, §5.9 line 153–155)에 대응하는 프로파일 키가 **없다**
  (실측 §8) — Phase-0 플래그.

### 6.3 degraded lease validity — time 술어 compose (§13.2; §14; SA-EV-004/005)

`degraded_lease_valid(lease_ownership, owner_registry_view: Sequence[DegradedLeaseOwnershipRecord], *,
time 좌표·bounds 주입, health_state, dominating_state: AuthorityState) -> bool`: ADR §13.2(line 491–500)의
**8조건 중 7개를 모델링**하고, 8번째(broker-egress-validation, **line 499** "broker egress validates the lease
and action")는 §5.2 조건 6과 **동형으로 런타임 이연**한다(tos non-transmitting, SA-EV-008/013 경계; m2 정정 —
v1.0의 "7전제"는 8조건 중 1개를 누락한 오기였다). 모델링하는 7조건 —

1. protective classification(ADR-002-001 소관, 주입 flag) present (line 493);
2. pre-committed protective capacity + exclusive sub-consumption(RCL capacity, scalar 참조 present) (line 494);
3. valid Degraded Protective Lease 존재(ownership 레코드 ISSUED) (line 495);
4. **local monotonic validity positively established**: `conservative_usable_lifetime(...) is not None`
   **및** `anchor_valid(...) == True`(**`tos.time` compose** — §3.4) (line 496);
5. **scope not overlapping — `lease_scope_exclusive` 내부 compose(M1 봉합)** (line 497): `exclusivity_ok: bool`
   주입 파라미터를 **제거**하고 `degraded_lease_valid`가 `lease_scope_exclusive(lease_ownership.lease_ownership_id,
   owner_registry_view)`(§6.1)를 **내부 호출**한다 — §3.4 time-compose seam-봉합과 동형(Time MEDIUM-2 규율 계승);
   잘못된 `exclusivity_ok=True` 주입 경로가 존재하지 않는다;
6. broker capability permits(주입 flag — broker-agnostic capability class) (line 498);
7. no dominating safer state(`_PRECEDENCE_RANK[dominating_state] < rank[DEGRADED_PROTECTIVE]`이면 거부 —
   §5.3) (line 500); + health_state가 DEGRADED_HOLDOVER 또는 TRUSTED(§15; degraded lease는 DEGRADED_HOLDOVER에서
   pre-issued만 허용 — Time §2.4).

하나라도 미충족/None ⇒ **invalid**. [SA-INV-008; §14.3; SAFE-048]

> **honest 경계(registry-view completeness는 런타임)**: `lease_scope_exclusive`는 **전달된
> `owner_registry_view` 안에서만** exclusivity를 판정한다. view가 모든 활성 owner를 담았는지(완전성)는
> **런타임 속성**(레지스트리 linearizability·전파 지연)이며 Phase-1 모델이 증명할 수 없다 — 모델은 자신이 본
> view에 대해서만 fail-closed로 판정한다(§0.2 경계; SA-EV-007 완전성은 EV-L3 fault injection이 검증). 이
> 명시가 M1 봉합이 injected-bool을 view-compose로 바꾸되 완전성을 overclaim하지 않게 한다.

- **음수 주입항 canary(Time v1.2 REJECT 회귀)**: `conservative_usable_lifetime`에 음수 elapsed/drift/
  transport/margin 주입 ⇒ `None`(lease 연장 불가) — Time이 REJECT로 강제한 fail-closed를 authority가
  compose로 상속함을 property로 고정. **monotonic 초과⇒무효(SA-EV-005 강 substrate)**: signed wall deadline이
  valid로 보여도 monotonic usable lifetime ≤ 0 ⇒ invalid.

### 6.4 degraded lease invalidating events (§14.4 line 563–576; SA-INV-009; SA-EV-006/011)

`degraded_lease_invalidated(...) -> bool`(True=무효): §14.4의 사건 중 하나라도 — process restart/host
reboot/monotonic reset/discontinuity(`anchor_valid == False`), suspension 초과(anchor_valid False),
exclusive owner proof 상실(`lease_scope_exclusive(claimant, view) == False` — §6.1 내부 compose, 주입 bool
아님), protective capacity 고갈(RCL scalar), Hard Envelope
incompat, broker profile revocation, dominating CONTAINED/HALTED(§5.3), holdover budget 만료
(`conservative_usable_lifetime is None`). **canary**: restart(boot_id 변화) ⇒ 무효(SA-EV-006);
discontinuity/suspension unknown ⇒ 무효(SA-EV-011). `anchor_valid`·`conservative_usable_lifetime` compose
(§3.4).

### 6.5 partition authority deny-table + registry-unavailable (§13.1; SA-EV-003/014)

`partition_authority_verdict(control_plane_verifiable: bool|None) -> PartitionAuthorityVerdict`: control
plane이 verifiable하지 않으면(False **또는** None) §13.1(line 480–485)의 {new normal risk-increasing,
new aggregate capacity commitment, normal capability renewal, live re-arm, limit enlargement} = **전부
DENIED**; 기존 orders/fills/positions/reservations = **conservatively tracked(불변)**(line 487).
`automatic_rearm_denied = True`(무조건 — §13.5 line 517 "Rejoin does not automatically restore live mode").
[SA-INV-005; SAFE-011]

- **canary(RCL `partition_verdict` None⇒DENIED 동형)**: `None`(unknown) ⇒ 전부 DENIED(vacuous permit
  금지); registry 복구가 자동 re-arm하지 않음.
- **registry unavailable(SA-EV-014)**: §20 표 line 749 "Epoch Registry unavailable → no new permissive
  authority; existing effects remain tracked" — 동일 verdict(`control_plane_verifiable`에 registry
  availability 포함, 주입 flag). 실제 registry 장애는 런타임.
- **RCL 재사용 아님**: action 집합(authority renewal/re-arm/limit-enlargement)이 RCL capacity action과
  다르므로 authority-local(§3.3).

### 6.6 re-arm gate — 비-authorizing conjunctive checklist (§17.1; SA-INV-013/014; SA-EV-010)

`rearm_gate(checklist: RearmChecklist) -> RearmVerdict`: §17.1(line 653–668) 14전제가 **전부 양성**일
때만 `armable=True`; **임의 하나라도 미충족(False)/미지(None) ⇒ `armable=False`**. 14전제: trustworthy time
restored, current epoch established, stale epochs fenced, account-wide reconciliation complete, UNKNOWN
resolved, external activity resolved, RCL consistency verified, protective leases reconciled, Hard/Runtime
versions verified, broker capability current, no unresolved Critical alert, Recovery Coordinator evidence
complete, fresh Live Authorization issued, explicit human dual control complete.

- **비-authorizing(핵심 — SA-INV-013 line 213–215; §8.4 line 291 "does not grant live authority")**:
  `RearmVerdict.authority_effect` = **all-false**(§4.1). checklist가 armable=True를 반환해도 그것은
  **전제 충족 여부**일 뿐 **live authority를 부여하지 않는다** — re-arm은 §17.3대로 **새 capability를 current
  epoch 하에 발행**하는 별도 행위이고(그 발행 자체는 §5.2 validity를 다시 통과), Phase-1은 checklist 판정만
  저작한다. **canary**: `armable=True`여도 `authority_effect` 전부 false; **all-but-one true ⇒ not armable**
  (각 전제 load-bearing); **None ⇒ not armable**(SA-INV-013 "No timeout, service recovery, leader election,
  reconciliation completion event, or system restart may automatically re-arm").
- **SoD(SA-INV-014 line 217–219)**: `checklist.limit_enlarger_principal != checklist.armer_principal`
  아니면 not armable(§17.2 line 670–674 "The principal approving limit enlargement SHALL NOT be the sole
  principal arming"; Recovery Coordinator는 자기 re-arm 승인 불가). **canary**: 동일 principal ⇒ not armable.
- **partial re-arm(§17.4 line 680–682)**: re-arm은 halt 이전보다 **좁은** scope를 복원할 수 있다(full
  restoration 불요) — 모델은 좁은 scope의 새 capability 발행을 표현(§17.3 non-revival과 결합; 옛 capability는
  revive 안 됨).

---

## 7. property-test 하네스 타깃

§1의 EV-L1 분류에 정렬. **전부 predicate substrate이며 어떤 SA-EV도 닫지 않는다**(§1 규율). property는
bound를 **hypothesis 생성 주입값**으로 다뤄 "임의 유효 bound 하 보수적 성립"을 검증(특정 값 비의존, 하드코딩
없음 — §8).

| family | Phase-1 타깃 | substrate / 근거 |
|---|---|---|
| capability canonicalization + digest 검증 | **REUSE 설계 #4 §3.4 (A) must-pass suite** (`tos.canonical`) | capability/epoch/lease covered로 재적용; frozen digest 일관성(`_base.py` 171–205) |
| same-capability-id/diff-bytes 충돌 + idempotency | **REUSE core `classify_record_pair`** | §4.5; SA-EV-015 substrate / §18.3 / §9.3 |
| authority epoch currentness / fence | **core 술어** | §5.1; SA-EV-001/002/014 substrate. None⇒fenced canary + 좌표 비붕괴 canary(§4.3) |
| permissive capability validity (6-part, type-gated, egress 경계) | **core 술어** | §5.2; SA-EV-001/003 substrate. **type-gate 조건4**(normal risk⇒online currentness only, lease 대체 불가 — M2); **numeric-claim None⇒invalid**(Gap); missing-claim⇒invalid; egress 조건 비주장 |
| restrictive dominance + precedence | **core 술어(강 substrate)** | §5.3; SA-EV-009. **양방향(순서-무관) property** |
| currentness witness / cache≠current | **술어** | §5.4; SA-EV-003. within_bound=None⇒deny(capsule Freshness 선례) |
| degraded lease validity (time compose) | **core 술어(강 substrate)** | §6.3; SA-EV-004/005. `conservative_usable_lifetime`/`anchor_valid` compose; **음수항⇒연장불가**(Time v1.2 회귀) |
| lease invalidating events | **술어** | §6.4; SA-EV-006/011. restart/discontinuity/suspension⇒무효 |
| lease exclusivity + overlapping failover | **술어** | §6.1/§6.2; SA-EV-007. **claimant-present+unique**(빈/부재⇒False — M1 봉합); §6.3가 `lease_scope_exclusive` 내부 compose(주입 bool seam 제거); overlapping⇒CRITICAL; hard-fence∨expiry-fence 없으면 재할당 금지; epoch-advance 단독 불가 |
| partition authority deny-table | **술어** | §6.5; SA-EV-003/014. None⇒전부 DENIED |
| re-arm conjunctive checklist + SoD | **술어** | §6.6; SA-EV-010. all-but-one⇒not-armable; authority_effect all-false; SoD |
| non-revival + epoch-advance≠release | **flag 불변식 + 술어** | §4.2/§4.4; SA-INV-004/011. revive 연산 부재 |
| authority≠enforcement (flag 불변식 + 거부 술어) | **flag 불변식 + 거부 술어** | §4.1; SA-INV-003. authority_effect all-false; possession≠currentness |

- **core(술어) 강도**: -005·-009가 가장 강함(-005는 `conservative_usable_lifetime` REUSE, register 최저
  EV-L2/3; -009는 순수 순서-무관 우선순위). **전부 predicate substrate — "EV-L1-complete 주장 금지"**(§1).

### 7.1 import-closure 검증 테스트 (C1 강제 — 설계 #4 §7.1 확장)

서브프로세스에서 `import tos.authority`(및 `tos.time`·`tos.ordering`·`tos.canonical`)만 한 뒤 `sys.modules`를
검사해 assert: (1) 설계 #1 §2.3 금지 패키지 부재; (2) **`shared.config`·`shared.config.secrets` 부재**(전이
유입 런타임 포착); (3) `os.environ`/`os.getenv` 미참조; (4) **`numpy`·`pandas`·`yaml`(pyyaml) 부재**(bound는
주입·YAML은 하네스 소관, §0.3); (5) **`tos.rcl`·`tos.capsule`·`tos.evidence` 부재**(§3.3 layering — authority는
이들의 형제이므로 closure에 없어야 하며, capacity/time 참조는 scalar/술어 REUSE로만); (6) **`tos.time`·
`tos.ordering`·`tos.canonical` 존재 허용**(§3.4 최초 sibling→sibling edge를 명시적으로 허용 대상으로 기록 —
import-closure가 이 edge를 *봉인*하지 않고 *한정*한다). required check(`tos-firewall`)와 함께 green이어야
§0.3 준수 선언이 능동 성립한다.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

authority 전용 run-manifest 템플릿은 없으므로 설계 #1 §5.1 규율을 REUSE한다. evidence를 산출하는 모든
property-test run은 다음을 기록: (1) git commit digest + `tos` 버전; (2) 인터프리터 + 고정 의존성 버전
(pydantic/hypothesis); (3) 실행 환경; (4) 하네스 git digest; (5) **property-test seed**(hypothesis
seed/derandomize, append-only); (6) **소비 설정 아티팩트 digest**(주입 authority/lease bounds 프로파일 +
`canonicalization_version` + `tos.ordering`·**`tos.time`** primitive 버전); (7) 산출 아티팩트 sha256.
(VER-002-001 §2.3 재현성·§3 baseline·§9.1 seed·§9.2 digest의 EV-L1 부분집합.)

---

## 8. bounds 주입 + 누락 프로파일 키 Phase-0

`VERIFICATION-PROFILE-002.yaml`은 전체 `status: PROPOSED`·`approved_by: []`·`effective_from: null`
(line 16–20; 배너 line 3–5 "an unapproved or placeholder bound is not an approved bound"). ADR-002-003
§27(line 956–962)·§28(line 982 "time holdover assumptions are documented and tested")은 numeric bound·
holdover/drift/transport 가정을 승인 프로파일 소관으로 못박는다.

- **결정**: 모든 bound(authority validity window·holdover budget·drift·suspension·lease-expiry-fence
  duration 등)는 **주입 policy 파라미터**로만 모델에 들어온다. **어떤 숫자도 하드코딩하지 않는다**
  (CLAUDE.md 설정 기반). 값 누락 ⇒ `UNKNOWN` ⇒ fail-closed(§5·§6). property는 bound를 hypothesis 생성
  주입값으로 다룬다(§7).

- **실측 확인(evidence-based) — 프로파일에 존재하는 SA-관련 키**:
  - `B_stale_epoch_reject`(line 177–181): `value_ms: 0` / PROPOSED. "synchronous … compare-and-set; 0 = no
    time window(ADR-002-002 INV-008, **ADR-002-003**)." ⇒ authority epoch fence를 **동기 순수 술어**(§5.1)로
    모델링함을 지지.
  - `B_authority_partition_detect`(line 121–126): `2000` / PROPOSED, rationale가 **ADR-002-003 heartbeat**를
    직접 인용. `B_risk_increase_revoke`(128) `500`; `B_halt_to_egress`(142) `null`(§16); `B_human_halt_to_
    commit`(149) `null`. ⇒ §12/§16 currentness/HALT 전파는 런타임(egress).
  - `B_egress_hard_fence`(line 170–176): `null` / "APPROVE after credential, session, signer, route, and
    broker fence mechanisms are selected and measured … proof that the superseded principal cannot create a
    broker-accepted order mutation." ⇒ **hard fence latency**(SA-EV-008, +Broker) — not-Phase-1임을 프로파일이
    확인. **주의: 이는 §14.5의 hard-fence *증명 지연*이지, lease-expiry-fence *대기 지속시간*이 아니다.**
  - `MAX_degraded_lease_holdover_ms`(line 699): `5000` / PROPOSED — §5.10 Authority Holdover Budget
    (`conservative_usable_lifetime` 총예산).
  - `MAX_clock_drift_ppm`(line 700): `200`; `MAX_process_suspension_ms`(line 701): `2000` — §14.4/§15.2
    (`anchor_valid` 입력). `MAX_normal_capability_age_ms`(line 697): `1000` — §9.4/§12.1 currentness witness
    freshness. `MAX_time_health_snapshot_age_ms`(line 698): `null`.

- **누락 distinct 키 (Phase-0 Bounds-Approver 플래그)**: 실측 대조(grep `lease|fence|holdover|epoch|reassign|
  overlap|expiry|handover`) 결과 —
  1. **Lease-Expiry Fence 지속시간 전용 키 부재(핵심 신규)**: §5.9(line 153–155)·§14.5(line 584)의 "conservative
     waiting barrier … until every previously issued lease … must have expired under maximum duration, clock-
     drift, process-suspension, and communication-delay assumptions"에 대응하는 distinct 프로파일 키가 **없다**.
     `B_egress_hard_fence`(hard-fence 증명 지연)·`MAX_degraded_lease_holdover_ms`(holdover 예산)는 **다른 양**
     이다 — expiry-fence는 *former lease 만료 보장 후 재할당까지의 worst-case 대기*다(§6.2 `lease_expiry_fence_
     elapsed` 판정의 근거값). ⇒ **주입 슬롯으로 선언**하되 값·키 승인은 Bounds-Approver로 넘긴다(누락 시
     UNKNOWN⇒§6.2 재할당 금지 fail-closed). SA-INV-007 안전에 직결.
  2. **lease transport/communication-delay bound**: §14.3(line 561 "If transport delay cannot be bounded, the
     local usable lifetime SHALL be reduced")는 `conservative_usable_lifetime`의 `source_transport_uncertainty`
     항에 대응하나, 이는 **Time 설계 §8이 이미 "transport-and-queue uncertainty 전용 키 부재"로 Phase-0 플래그**
     한 항목과 **동일**하다 — **중복 계상 않고 Time §8 항목을 cross-reference**한다(authority는 그 주입 슬롯을
     lease 맥락으로 소비).
  3. **holdover safety margin**: §14.3(line 559 "reduced by approved uncertainty and safety margins")는 Time
     §8이 이미 "`MAX_degraded_lease_holdover_ms`에 folded, margin 전용 키 부재"로 플래그한 항목과 **동일** —
     cross-reference(중복 계상 없음).
  4. **authority epoch — numeric bound 불요(명시)**: epoch은 unbounded 단조 정수 좌표(§5.2 "not a timestamp")
     이므로 magnitude bound 키가 **필요 없다**(#5가 epoch에 magnitude bound 불요를 명시한 것과 동형). 누락이
     아니라 해당 없음.

  본 계약은 (1)을 **genuinely 신규 누락 키**로, (2)(3)을 **Time §8과 공유되는 기존 플래그**로 구분해 기록한다
  (설계 #4 §8·Time §8·#5 §8 under-report 정정 동형; 중복 계상 회피). 값·키 승인은 **Bounds-Approver 게이트**
  (Live-Armer와 분리 — IMPLEMENTATION-PLAN §3)로 넘긴다. [SAFE-048]

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

- **`IndependentIdArtifact` core PROMOTE(지금 — §0.4c/§3.1; rcl+dsl 둘 다 흡수 — M3)**: 구현 **선행 소단계**로
  `tos.rcl._base.IndependentIdArtifact`(line 53–80) **및** `tos.dsl._base.IndependentIdArtifact`(line 53–79)를
  `tos.canonical._base`로 이동(구조적으로 `IdDerivedArtifact` 옆 — 두 id-전략 subclass가 core에 함께),
  `tos.canonical.__init__`에 export 추가, `tos.rcl._base`·`tos.dsl._base`를 **둘 다** re-export shim으로 무회귀
  (rcl **및 dsl** property suite green 확인 — dsl 소비자 `NoActionOutcome`·`PortfolioVector`·`AdmissibilityResult`·
  `CapabilityManifest`·`BoundOutcome` 포함), rcl·dsl·authority가 **동일 core primitive REUSE**(second home 제거 —
  classify single-home 선례). **형제간 신규 import edge 없음**(shim은 core를 import).(Phase-1 PROMOTE 1건 —
  classify PROMOTE 절차 동형, 대상만 2 패키지.)
- **`tos/src/tos/authority/` 모델·술어·property·import-closure 테스트 저작**(§2–§7): 설계 #3(EV-L1 하네스)이
  property suite를 실행. `tos.canonical`(digest+id+classify) + `tos.ordering`(순서) + **`tos.time`(lease
  monotonic 술어·좌표)** REUSE, 신규 canonicalizer/ordering/time-math 없음.
- **의존 방향**: authority ⟸ `tos.canonical`·`tos.ordering`·`tos.time`(core+time). authority는 rcl/capsule/
  evidence를 import하지 않음(형제, scalar만). RCL capacity·time snapshot은 scalar 참조.
- **cross-sibling edge 기록(§3.4)**: `authority → time`은 본 시리즈 최초의 형제간 edge이므로 §7.1 import-
  closure가 이를 **허용 대상으로 명시**(봉인 아님)하고, 설계 #1 §3.2 허용목록의 "자기 자신 `tos.*`" 조항이
  이를 이미 커버함을 교차-주석한다.

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

1. **VERIFICATION-PROFILE-002 bounds 승인 + 누락 키 신설**(§8): **Lease-Expiry Fence 지속시간** 전용 키
   (신규); transport/margin은 Time §8과 공유(Bounds-Approver ≠ Live-Armer).
2. **프로덕션 canonical serialization·digest 알고리즘 선택**(설계 #4 §9.2 item 1과 동일 게이트):
   `ev-l1-provisional-0`·sha256은 비프로덕션.
3. **Authority Domain granularity**(§27 OQ1 line 952 "What exact Authority Domain granularity is used?"):
   account/portfolio/기타 scope. §5.1 술어는 scope-무관하게 성립하되 실제 scope는 정책 승인.
4. **Epoch Registry consensus product + Safety Commit Log 위 epoch ordering(authority separation 비붕괴)**
   (§27 OQ2 line 953–954; §8.2). 이는 **런타임(EV-L2/L3, Phase B)** 이며 Phase 1 EV-L1 밖(§0.2).
5. **authority signing key rotation·MAC/서명 검증**(§18.2; §27 OQ9): 키 자료·custody 부재로 Phase 1은
   `issuer_key_status`를 주입 flag로만 소비하고 실제 서명/rotation 검증은 L2+ 이연(설계 #4 §3.4·Time §9.2
   item 5·#5 §9.2 item 6 동형). SA-EV-012 not-Phase-1.
6. **Hard Egress Fence + broker fencing(§5.8/§11.3; §27 OQ3/OQ4)**: broker-specific — SA-EV-008/013,
   런타임+Broker/Security. Broker Capability Profile(broker-agnostic capability class) 승인 소관.
7. **re-arm dual-control 메커니즘**(§17.2; §27 OQ10; ADR-002-015 interface): effective-principal·quorum·
   Human HALT 메커니즘. §6.6 SoD 술어는 principal 좌표만; 실제 인증/승인-소비는 ADR-002-015 런타임.
8. **Independent-Safety-Reviewer 지정 + §7 EV-L1 evidence 수용 서명**(저자 배제 — IMPLEMENTATION-PLAN §3
   line 153/157).

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- 2026-07-23: **v1.0 초안 최초 작성.** ADR-002-003 EV-L1 실현 계약(트랙 A 두 번째 §2 코어). 설계 #1(경계·
  firewall)·#2(capsule all-false)·#4(canonical substrate + id⊥digest)·#5(RCL capacity 측 형제 + 통일 PROMOTE
  규칙)·Time(monotonic lease 술어)에 정렬. 주요 결정: (§0.4a/§3.1) `tos.canonical` **REUSE + `id=f(digest)`
  미채택**(same-capability-id/diff-content 위조·replay 탐지 보존), `classify_record_pair` core REUSE;
  (§0.4b/§3.4) **`tos.time` import-and-compose** — 본 시리즈 **최초 sibling→sibling edge**(ADR Depends-On
  002-003→002-008 정합; injected-boolean seam 봉합, Time MEDIUM-2 계승; DRY; acyclic), 대안 3종(재저작/core
  PROMOTE/scalar-injection) 기각; (§0.4c/§3.1/§9.1) **`IndependentIdArtifact` rcl→canonical PROMOTE**(Phase-1
  PROMOTE 1건 — `IdDerivedArtifact`의 대칭 쌍, classify PROMOTE 절차 동형, rcl shim 무회귀); (§0.4d/§3.3)
  **`writer_fenced` 미재사용·`tos.rcl` 미import**(Safety Authority Epoch ≠ Writer Epoch 좌표 비붕괴 — §27 OQ2;
  fence-primitive PROMOTE 검토 후 기각 — capability-type 비대칭 + trivial atom), `partition_authority_verdict`·
  all-false 블록 authority-local; (§1) **SA-EV 0건 완결**(register 최소 전부 EV-L2+) + **predicate-only(12)/
  not-Phase-1(3) 2분류, 코어 tier 없음**, "EV-L1-complete 주장 금지"; (§2) capability/epoch-transition/
  lease-ownership = **IndependentId + 독립 id**, `IdDerivedArtifact` 0건; HALT/CONTAIN/REARM은 capability
  *type*(별도 record class 없음, §9.2); (§4.1) **authority ≠ enforcement** 중앙 불변식(서명·보유 ≠ 현재
  authority; 모델 non-transmitting; loss-of-proof=loss-of-authority; documentation≠authority); (§4.7)
  **generation-vector 좌표 비붕괴** vocabulary(SA Epoch/Writer Epoch/membership/restore/recovery/time-health/
  process/profile 8좌표, 각 독립 floor); (§5) 6-part validity(egress 조건 비주장 경계)·restrictive dominance
  **양방향 property**·precedence lattice·cache≠current; (§6) lease exclusivity(overlapping⇒CRITICAL)·
  overlapping-failover(hard-fence∨expiry-fence, epoch-advance 단독 불가)·degraded-lease validity(time
  compose, **음수항⇒연장불가** Time v1.2 회귀)·partition deny-table(None⇒전부 DENIED)·비-authorizing re-arm
  checklist(all-but-one⇒not-armable, authority_effect all-false, SoD); (§8) **Lease-Expiry Fence 지속시간**
  누락 키 실측 후 Phase-0 플래그(transport/margin은 Time §8 공유, 중복 계상 회피). 이후 독립 비평 리뷰.
- 2026-07-23: **v1.1 — 독립 비평 리뷰 REJECT 반영(3 MAJOR / 3 MINOR / 1 gap).** 리뷰는 인용 fidelity·EV 정직성·
  아키텍처 3결정(`tos.time` edge / PROMOTE 대칭 / `writer_fenced` 미재사용 — 전부 clean 검증)을 승인했고,
  rejection은 좁게 **두 fail-open seam + 한 PROMOTE 완전성 누락**이었다. 7건 전부 반영: **[M1]** §6.1
  `lease_scope_exclusive`를 **claimant-present+unique**로 재정의(빈/부재⇒False, `0≤1` vacuous-True 제거)하고 §6.3에서
  `exclusivity_ok` 주입 bool을 **제거·내부 compose**(§3.4 time-compose seam-봉합 동형; registry-view 완전성은 런타임
  경계로 명시). **[M2]** §5.2 조건 4를 **capability-type로 gate**(normal risk-increasing ⇒ online currentness ONLY,
  `lease_ok` 대체 불가 — §9.4 line 366·SA-INV-005; canary 추가). **[M3]** PROMOTE를 **`tos.dsl._base.
  IndependentIdArtifact`까지 확장**(rcl+dsl 둘 다 → core + 두 shim; dsl 복제는 core-home 부재의 병렬-트랙 scope
  결정으로 이제 통합 — §0.4c/§9.1/§10.2). **[m1]** capability identity 인용 §9.1 line 316→**317**(§0.4a·§2.1).
  **[m2]** §6.3 "§13.2 7전제"→**"8조건 중 7개 모델링, broker-egress-validation(line 499) 런타임 이연"**. **[m3]**
  §4.7 GenerationVector를 capsule 템플릿 `generation_vector`(line 44–52)의 **복사본이 아니라 겹치는 좌표 naming을
  재사용하는 distinct superset**으로 재서술(템플릿은 `authority_epoch`·`safety_configuration/deployment/identity/
  evidence_policy_generation` 등 다른 좌표 세트; authority는 좌표 명료성 위해 `safety_authority_epoch` 유지·템플릿명
  교차참조). **[Gap]** §2.2 "magnitude 누락⇒fail-closed" 주장을 §5.2의 **numeric-claim precondition 조항**으로
  실체화(`maximum_quantity`/risk-vector 링크 None⇒invalid; `_REQUIRED_COVERED` 밖 유지로 ISSUED 도달성 불변;
  canary 추가). 헤더 리뷰 이력 REJECT→v1.1 갱신, 비준 대기. 아키텍처 3결정·SA-EV 0건·인용 line은 v1.0 그대로 유지.

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

- [ ] §0.2 NO 목록(leader election/consensus/registry·실제 fencing/hard-fence/egress·실제 clock·authority·
      **SA-EV 0건**·bounds 미승인)과 §0.3 firewall 준수(numpy/pandas/pyyaml·shared.config·**tos.rcl·tos.capsule·
      tos.evidence** 배제, **tos.time·tos.ordering·tos.canonical만 허용**)에 동의.
- [ ] §0.4b/§3.4 **`tos.time` import-and-compose**(최초 sibling→sibling edge; ADR Depends-On 정합·seam 봉합·
      DRY·acyclic; 대안 재저작/core-PROMOTE/scalar-injection 기각)에 동의. **[운영자 판단 지점: cross-sibling
      import vs injected-boolean scalar fallback]**
- [ ] §0.4c/§3.1/§9.1 **`IndependentIdArtifact` rcl+dsl→canonical PROMOTE**(Phase-1 PROMOTE 1건, **두 패키지
      흡수** — dsl 복제는 병렬-트랙 scope 결정, second home 제거; `IdDerivedArtifact` 대칭 쌍; rcl·dsl 두 shim
      무회귀; classify single-home 선례 동형)에 동의. **[운영자 판단 지점: promote(rcl+dsl) vs authority-local
      재저작(세 번째 복제 — 비권장)]**
- [ ] §0.4d/§3.3 **`writer_fenced` 미재사용·`tos.rcl` 미import**(Safety Authority Epoch ≠ Writer Epoch 좌표
      비붕괴 — §27 OQ2; fence-primitive PROMOTE 검토 후 기각; `partition_authority_verdict`·all-false authority-
      local)에 동의.
- [ ] §1 **SA-EV 0건 완결**(register line 20–34 최소 전부 EV-L2+) + **predicate-only(001/002/003/004/005/006/
      007/009/010/011/014/015)/not-Phase-1(008 +Broker/012 key/013 +Security), 코어 tier 없음** + "EV-L1-complete
      주장 금지"에 동의.
- [ ] §2 데이터 모델(capability·epoch-transition·lease-ownership = **IndependentId + 독립 id**, `IdDerivedArtifact`
      0건; HALT/CONTAIN/REARM = capability *type*; RCL·time은 scalar/술어 참조, 클래스 미import)에 동의.
- [ ] §4.1 **authority ≠ enforcement** 중앙 불변식(서명·계산·보유 ≠ 현재 authority; all-false 모델; loss-of-
      proof=loss-of-authority; epoch-advance≠release; non-revival; documentation≠authority)과 §4.7 **generation-
      vector 좌표 비붕괴**(8좌표 각 독립 floor, 교환-canary)에 동의.
- [ ] §5 validity/dominance 술어 — 특히 **6-part validity의 egress 조건 비주장 경계**(술어 True ≠ authorization
      완결), **조건 4 capability-type gate**(normal risk-increasing ⇒ online currentness ONLY, lease 대체 불가 —
      M2 봉합), **numeric-claim None⇒invalid precondition**(Gap 봉합), **restrictive dominance 양방향(순서-무관)
      property**(SA-EV-009)에 동의.
- [ ] §6 lease exclusivity(**claimant-present+unique, 빈/부재⇒False — M1 봉합**; overlapping⇒CRITICAL)·
      degraded-lease validity(**`lease_scope_exclusive` 내부 compose — exclusivity_ok 주입 seam 제거, M1**;
      **§13.2 8조건 중 7개 모델링·broker-egress(line 499) 런타임 이연 — m2**; **time compose, 음수항⇒연장불가**
      Time v1.2 회귀; registry-view 완전성=런타임 경계)·overlapping-failover(**hard-fence ∨ lease-expiry-fence**,
      epoch-advance 단독 불가·None⇒금지)·partition deny-table(None⇒전부 DENIED)·**비-authorizing re-arm
      checklist**(all-but-one⇒not-armable, authority_effect all-false, SoD)에 동의.
- [ ] §7 하네스 타깃(전부 predicate substrate; "EV-L1-complete 주장 금지"), **§7.1 import-closure**(tos.rcl/
      capsule/evidence 부재 + tos.time/ordering/canonical 허용), §7.2 run manifest 7항목에 동의.
- [ ] §8 bounds 주입 + **Lease-Expiry Fence 지속시간** 신규 누락 키 Phase-0 플래그(transport/margin은 Time §8
      공유)에 동의.
- [ ] §9.2 Phase-0 이관 8항목(bounds·프로덕션 canon·Authority Domain granularity·Epoch Registry consensus
      제품(OQ2)·key/MAC·broker hard-fence·re-arm dual-control·독립 리뷰어)을 별도 게이트로 유지함에 동의.
- [ ] 명명 규약(§0.4f): 모델 불변식을 **SA-INV-001..014 / SA-AC-001..015 / SAFE-011/035/041/048**에 앵커하고
      새 INV 시리즈를 창작하지 않음에 동의.

비준 시 효력: IMPLEMENTATION-PLAN-002 §4 Phase 1의 ADR-002-003 부분을 `tos/src/tos/authority/`에 순수·비전송
모델 + property test로 작성 착수 승인(`tos.canonical`·`tos.ordering`·`tos.time` REUSE, `IndependentIdArtifact`
core PROMOTE 1건 — rcl+dsl 흡수). §9.2 Phase-0 8항목과 bounds 승인·독립 리뷰어 지정, Phase B(leader election/consensus/
registry/egress fencing) 전체는 별도 게이트로 남는다.
