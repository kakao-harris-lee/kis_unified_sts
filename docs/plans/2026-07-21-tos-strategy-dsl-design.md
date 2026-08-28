# 설계 문서 — Strategy DSL 실현 + Purity/Escape-Closure 강제 계약 (2026-07-21, v1.1)

> **비준 기록**: **2026-07-21 운영자 비준 (v1.1)**. 효력 발생 — 설계 #1 §6.3 병렬
> 트랙으로서 `tos/src/tos/dsl/` Phase 1(EV-L1, 비전송) 모델 + property test 작성 착수
> 승인. escape-checker는 AST 정적분석만(no exec/eval/import), capability-runtime·
> isolation·mechanism verification·bounds 승인·독립 리뷰어 지정·ADR acceptance는 Phase-0
> 별도 게이트로 유지. Proposal identity(content-addressed vs 독립 id)·실현 family·
> DCE-INV-007 numeric bound은 downstream(ADR-002-020/023)·Phase-0 확정 대기.
> (독립 비평 리뷰 ACCEPT-WITH-MINOR → MINOR-1~5 + open-question 2 정정 후 비준.)
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며 스펙 텍스트를
> 변경하지 않고, `tos/` 코드를 작성하지 않는다. EVIDENCE-REGISTER-DEV의 어떤
> status도 뒤집지 않는다(DCE-EV-001..007 = NOT_IMPLEMENTED 유지).
>
> **실현 대상(규범 원천)**: RFC-008 — Strategy DSL (Ratified v0.2, 2026-07-18) +
> ADR-DEV-001 — DSL Realization and Purity/Escape-Closure Enforcement (Proposed
> v0.1). 교차 규범: ADR-DEV-003(External Value Capture), ADR-DEV-007(Strategy
> Output Semantics), ADR-DEV-002(Reproducibility/Identity), ADR-DEV-004(Authoring
> Provenance), VER-DEV-001(DCE/EXV/SOS Evidence Cases).
>
> **실현 범위**: 그린필드 `tos/src/tos/dsl/`에 **Phase 1(EV-L1): 순수·비전송
> 모델 + property test**. 이는 설계 #1 §6.3(L363)이 명시한 **병렬 트랙**이며
> **EV-L1 크리티컬 패스가 아니다.**
>
> **선행 계약(효력 발생)**: 설계 #1 `2026-07-20-tos-boundary-and-import-firewall-design.md`
> (§2.1 "DSL runtime/Enforcement가 경계 안" L120-126; §2.3 금지 패키지·R-역방향
> L143-148/L192-194; §3.3 AST 게이트 L196-218 — 본 계약 escape-checker의 구조적
> 쌍둥이; §4 SAFE-045 계층 방어 L238-270), 설계 #2
> `2026-07-20-tos-decision-context-capsule-snapshot-design.md`(§6 captured-not-called
> L587-655 — DCE-INV-003을 `shared.llm` 금지로 구조 강제). 두 계약 모두
> 2026-07-20 운영자 비준 완료.
>
> **선행 코드(REUSE 강제, 재정의 금지)**: `tos/src/tos/canonical/{_base.py,
> canonicalization.py}`(digest-binding substrate), `tos/src/tos/capsule/`(read-only
> 입력 표면).
>
> **broker-agnostic**: 본문 어디에도 KIS 등 특정 브로커 고유명사를 규범적으로
> 넣지 않는다(project memory `tos-spec-broker-agnostic`). 프로젝트 측 예시는
> 명시적으로 "규범 아님"으로 격리한다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

RFC-008/ADR-DEV-001은 **런타임 강제 아키텍처**(3층: static admissibility analysis
· capability-restricted evaluation · isolation boundary — ADR-DEV-001 §8
L206-236)를 규정한다. 그러나 Phase 1은 "순수·비전송 모델 + property test"이므로,
본 계약은 **런타임 없이 순수하게 realize 가능한 facet만** 저작하고 나머지는
정직하게 이연한다. 이 분리를 흐리는 것이 본 트랙 최대의 리스크이므로 §0에서
경계를 못박는다.

**확정하는 것**
1. §1 — 조항별 EV-L1 도달성 매핑(DCE-EV/EXV-EV/SOS-EV 각각의 L1 facet vs 이연
   facet). **어떤 DCE-EV도 "L1-complete"로 주장하지 않는다.**
2. §2 — DSL 아티팩트 데이터 모델(Authored Strategy · Proposal · Outcome[No-Action/
   Explicit Flat/Portfolio Vector] · 강제-evidence 레코드), 템플릿 부재분을 prose에서
   저작하되 downstream 계약(ADR-002-020) 재정의 금지.
3. §3 — purity 3층 중 **layer 1(static admissibility)의 순수 술어**(closed typed AST
   vocabulary + fail-closed 판정 + ambient/escape/reflection 탐지). layer 2/3 이연.
4. §4 — determinism 술어(`evaluate(Capsule, config)`의 순수성 + captured-not-called
   입력 서명). reproducibility granularity는 ADR-DEV-002로 이연.
5. §5 — 정합성 서술(firewall ↔ escape-checker 구조적 쌍둥이 표 + "no live fetch"
   세 altitude).
6. §6 — property-test 타깃(static slice + SOS + 결정성 + import-closure) + run manifest.
7. §7 — bounds / Phase-0 프로파일 소관 항목.

**하지 않는 것 (미구현 NO — 명시)**
- **capability-restricted evaluation 런타임(layer 2) 미구현.** ADR-DEV-001 §8
  L217-220의 "런타임이 Capsule + Proposal Builder만 넘기고 ambient capability를
  scope에 두지 않음"은 **런타임 강제**이며 Phase 1 대상이 아니다.
- **isolation boundary(layer 3) 미구현.** §8 L221-225의 host-process/dynamic-loading/
  network-fs egress 차단 + 실 time/resource bound 강제는 런타임/샌드박스 대상.
- **mechanism verification(DCE-INV-005) 미충족.** ADR-DEV-001 §9 L242-261 + VER-DEV-001
  DCE-EV-005(L87-91)가 요구하는 RFC-010 §8 adversarial containment suite + ADR-002-029
  admission + 독립 리뷰는 Phase 1 밖이다. 본 계약이 만드는 escape-checker 모델 자체가
  Enforcement Mechanism 구성요소이므로 **자기 인증 불가**(DCE-INV-005) — provisional·
  non-authorizing 모델로만 취급한다(§3.5).
- **authority 부재.** 본 계약의 어떤 모델도 approval/capacity/transmission/live-arm/
  protective classification을 부여하지 않는다(RFC-008 §11 L364-406, 17개 unexpressible
  effect). Proposal·Outcome은 candidate일 뿐이다(RFC-008 §8 L272-274). ADR acceptance·
  restricted-live·production 어느 것도 승인하지 않는다.
- **EVIDENCE-REGISTER-DEV status 불변.** DCE-EV-001..007(rows 2-8)·EXV-EV-001(row 15)·
  SOS-EV-001..006(rows 40-45) 전부 `Critical/EV-L1/NOT_IMPLEMENTED` 유지. Phase 1
  property test는 evidence *입력/모델 커버리지*를 산출할 뿐 evidence *완결*이 아니다.
- **realization family 확정 안 함.** RFC-008 §14 Q1의 family 선택(standalone/embedded/
  API)은 ADR-DEV-001 §7 L193-201·§4 L92-93이 "safety 결정이 아니라 approved design/
  config"로 못박은 사안이다. 본 계약은 family-독립 property만 모델링한다(§3.2).

**firewall 준수(설계 #1)**: `tos/dsl/`는 `ast`(stdlib)·`pydantic`·`hypothesis`(tests)
+ `tos.canonical`·`tos.capsule`만 쓴다. `services/*`·`core/`·`shared.{execution,kis,
llm,streaming,storage,backtest}`에서 아무것도 import하지 않는다(설계 #1 §2.3 L143-148,
R-역방향 §3.2 L192-194). **escape-checker 자체가 firewall를 준수한다 — `importlib`/
`__import__`/`exec`/`eval` 사용 금지(설계 #1 §3.3-①d L206), 후보 아티팩트를 import·
execute하지 않고 AST를 정적 분석만 한다.**

**정합성 요지(§5 상술)**: "no live fetch"는 **세 altitude의 동일 불변식**이다 —
ADR-DEV-001 escape-closure(unexpressible = mechanism) / 설계 #1 firewall(no network·
`shared.llm`·`os.environ` capability = runtime 구조) / ADR-DEV-003 captured-not-called
(값이 이미 Capsule Critical Input = data).

**REUSE 요지(§2·§7 상술)**: digest-bound DSL 아티팩트는 `tos.canonical`의
`IdDerivedArtifact`(content-addressed Authored Strategy/Proposal identity) 또는
`DigestBoundArtifact`(강제-evidence 레코드, 독립 id)를 상속한다. `CanonicalizationScheme`
+ `EVL1ProvisionalCanonicalizer`(`ev-l1-provisional-0`) + registry를 재사용하고
`canonicalization_version`을 기록한다. **digest 경로를 fork하지 않는다.**

---

## 1. 조항별 EV-L1 도달성 — "EV-L1-complete 주장 금지"

VER-DEV-001 §5는 DCE-EV-001..007을 전부 `Minimum Level: EV-L1`로 등재한다(L61-103).
그러나 각 EV의 **as-registered injection**은 대부분 *런타임/adversarial-mechanism*
facet을 포함하므로, Phase 1 순수 모델은 그것을 **완결하지 못한다.** 아래 표는 각
EV가 요구하는 것 중 **Phase 1이 순수 모델·property test로 실현하는 facet**과
**이연하는 facet**을 분리하고, L1 커버리지를 정직하게 표기한다.

| Evidence | 지지 INV | as-registered injection (VER-DEV-001) | Phase-1 실현 facet (순수 모델) | 이연 facet (L2+) | L1 커버리지 |
|---|---|---|---|---|---|
| **DCE-EV-001** Default-Deny | DCE-INV-001 (§6 L140-144) | 어휘 밖 표현 시도 + denylist-over-host 실현 시도 (L66-67) | closed typed AST vocabulary(§3.1) — 금지 construct가 vocabulary에 **absent**(구성 불가)임을 property로; membership 판정 | 실 realized surface가 denylist-over-host가 **아님**을 보이는 것은 production realization 필요 | 높음(모델), 완결 아님 |
| **DCE-EV-002** Layered Non-Self-Trusting | DCE-INV-002 (§6 L145-149) | **한 layer를 isolate해 무력화**(L69-73) | 없음 — layer 1 하나만 존재. 단일 layer의 내부 fail-closed 규율(전제 입력)만 | §13.7(L354-357) 3개 single-layer failure(static/capability/isolation) 각각 시뮬 + 나머지 2층 containment → **3층 전부 필요** | **없음(L2+)** |
| **DCE-EV-003** No Ambient Authority | DCE-INV-003 (§6 L150-153) | **평가 중** ambient clock/rand/net/fs/global/builtin 도달 시도(L78) | escape-checker가 authored AST의 ambient **참조(naming)** 를 inadmissible 처리(static facet) + firewall closure가 tos 런타임에 ambient capability **부재** 보장(설계 #1 §4) | 실제 "평가 중 도달 불가"는 capability-restricted runtime(layer 2) 필요 | 중간(static naming) |
| **DCE-EV-004** Escape-Closure | DCE-INV-004 (§6 L154-160) | FFI/embedded host/dynamic loading/reflection/extension 재도입 시도(L84) | escape-detection 순수 술어 — import/importlib/`__import__`/exec/eval/reflection/extension **노드** 를 inadmissible 처리 | 실 embedded host가 API를 우회해 도달되는지의 런타임 containment는 layer 2/3 | 중간(static 탐지) |
| **DCE-EV-005** Verified Non-Authorizing Artifact | DCE-INV-005 (§6 L161-165) | unverified/unversioned/bypassable mechanism을 보장으로 제시(L90-91) | 강제-evidence 레코드에 **enforcement-mechanism version 필드**만(§2.4) | RFC-010 §8 adversarial suite + ADR-002-029 admission + 독립 리뷰 → mechanism 검증 전부 | **최소(version 필드)** |
| **DCE-EV-006** Inadmissible Is Conservative | DCE-INV-006 (§6 L166-169) | vocabulary 내 정적 증명 불가 아티팩트 제출(L96-97) | `not provably_admissible(x) ⇒ inadmissible(x)` fail-closed 순수 술어(§3.3) — unknown 노드 도메인 전수 | 실 mechanism이 확립 불가할 때의 admission 거부는 admission 프로세스 필요 | 높음 |
| **DCE-EV-007** Bounded → No-Action | DCE-INV-007 (§6 L170-172) | 평가 중 time/resource bound 소진(L102) | bound-exhausted ⇒ `NoActionOutcome` **상태기계 전이**(symbolic bound, §3.4) | 실 wall-time/CPU/메모리 계측·강제 = 런타임; **numeric bound는 프로파일 부재 → Phase-0**(§7) | 중간(전이 모델) |
| **EXV-EV-001** Captured Not Called | EXV-INV-001 (ADR-DEV-003 §6 L130-132) | 평가 중 external value **live fetch** 시도(L148) | `evaluate` 서명에 fetch capability **부재** + captured value가 Capsule Observation으로만 진입(§4) + firewall import-closure(§6.4) | live fetch 런타임 도달 불가의 실측(capability runtime) | 중간(구조/static) |
| **SOS-EV-001** No-Action ≠ Explicit Flat | SOS-INV-001 (ADR-DEV-007 §6 L139-143) | no-action/flat을 error/null로 혼동(VER-DEV-001 L306) | 별개 타입 union — `NoActionOutcome` vs zero-target `Proposal`, 서로 opposite exposure, 둘 다 non-null 1급(§2.3) | 재현성 완결은 ADR-DEV-002 replay | 높음(모델) |
| **SOS-EV-002** Atomic Unit Explicit | SOS-INV-002 (§6 L144-146) | 단위 추론 시도 | per-instrument vs portfolio-vector 둘 다 표현 + 단위 declared 필드(§2.3) | per-Proposal 승인/capacity 결합 = downstream | 높음(모델) |
| **SOS-EV-003** No Combined Authority | SOS-INV-003 (§6 L147-153) | vector를 aggregate authority로 union 시도 | vector = per-instrument `Proposal`의 **set**, union/aggregate-authority 필드 **부재**(§2.3) | Independent Approval per-target(ADR-002-023)은 downstream | 높음(구조) |
| **SOS-EV-004** Well-Formed & Bounded | SOS-INV-004 (§6 L154-157) | wildcard/"latest" target | 각 target이 ADR-002-020 §8 field set을 채우고 wildcard-free + Capsule bind(§2.3) | 실 canonical 구성 fencing = downstream | 높음(모델) |
| **SOS-EV-005** Grant No Authority | SOS-INV-005 (§6 L158-160) | output이 authority 부여 시도 | 모든 Outcome에 all-false authority block(§2.3) — approve/commit/transmit 필드 없음 | — | 높음(모델) |
| **SOS-EV-006** Vector Interdependence Declared | SOS-INV-006 (§6 L161-179) | undeclared vector partial 실현 | `VectorInterdependenceDeclaration`(atomic/independent, 부재 ⇒ atomic fail-closed) + partial-approval ⇒ whole-vector 비실현 상태 전이(§2.3) | 실 partial-approval·재평가는 downstream + 런타임 | 중간(모델/전이) |

**결론(§4 gap)**: Phase 1은 **static / purity / determinism / outcome-semantics facet**을
순수 함수 + property test로 realize한다. **DCE-INV-002(layered)·DCE-INV-005(mechanism
verification)는 L1-complete가 될 수 없다** — 전자는 3개 런타임 layer의 single-failure
시뮬(§13.7)을, 후자는 RFC-010 §8 suite + ADR-002-029 admission을 요구하기 때문이다.
7개 DCE-EV는 **전부 NOT_IMPLEMENTED로 유지**되고, ADR-DEV-001 gate는 DCE-EV-001..007
전부 + 독립 adversarial 리뷰(ADR-DEV-001 §14 L375-376; reviewer provenance ADR-DEV-005)를
필요로 한다. Phase 1이 산출하는 것은 그 gate의 **입력**이지 gate 통과가 아니다.

---

## 2. 데이터 모델 (템플릿 부재분 prose 저작)

DSL/Authored-Strategy/Proposal 아티팩트의 표준 템플릿은 tos-spec에 **없다**(dossier
§3 exhaustive check). 따라서 스키마를 prose에서 저작하되, downstream Approval 소비자
`PROPOSAL-APPROVAL-REQUEST-template.yaml`의 어휘 + all-false authority block(L72-82)을
앵커로 삼고 ADR-002-020 downstream 계약을 재정의하지 않는다.

권장 패키지 레이아웃(설계 #1 §2.4 원칙 "subpackage = RFC-002 §10 컴포넌트, 스펙
용어 = 코드 용어"). **Phase 1 범위 한정**:

```text
tos/src/tos/dsl/
  __init__.py
  vocabulary.py     # closed typed AST node algebra (Authoring Surface Vocabulary) — DCE-INV-001
  candidate.py      # 후보-AST 표현 (UnknownNode escape hatch 포함) — adversarial 입력 도메인
  admissibility.py  # 순수 is_admissible 술어 + AdmissibilityResult — DCE-INV-001/003/004/006 static facet
  outcome.py        # Outcome union: NoActionOutcome / Proposal / PortfolioVector — SOS-INV-001..006
  proposal.py       # Proposal(IdDerivedArtifact) + effect-free Proposal Builder(순수) — RFC-008 §8
  strategy.py       # AuthoredStrategy(IdDerivedArtifact) — RFC-008 §5 L154-156 / §9 L302-306
  determinism.py    # 순수 evaluate(capsule, config) 모델 + recorded-input 서명 — RFC-008 §9
  bounds.py         # bounded-evaluation 상태기계(symbolic bound) → NoAction — DCE-INV-007
  evidence.py       # 강제-evidence 레코드: AdmissibilityResult/CapabilityManifest/BoundOutcome — ADR-DEV-001 §8 L234-236
tos/tests/dsl/      # hermetic property test + import-closure test
```

### 2.1 Authored Strategy (identity·versioning)

RFC-008 §5 L154-156: "Authored Strategy = a versioned Decision Policy expressed in
the DSL, together with its declared configuration bindings." §9 L302-306: 평가는
Capsule id/digest + Authored Strategy version + DSL version + configuration version을
recorded provenance로 남긴다.

**결정.** `AuthoredStrategy`는 `tos.canonical.IdDerivedArtifact`를 상속한다(content-
addressed identity; ADR-DEV-002 ARI-INV-001 — mutable name/tag/"latest" 불가; 변경은
ADR-DEV-004 APA-INV-005 Versioned Substitution = 새 Artifact Identity). covered field:

- `artifact_type` / `schema_version`
- `dsl_version` — RFC-008 §9 L303
- `config_binding_version` — declared configuration bindings (RFC-008 §5 L155)
- `policy_ref` — AST/source 참조. **저장은 content-addressed digest 참조**(candidate
  AST의 canonical digest)로 하여 identity에 결선. source 원문 저장 여부는 ADR-DEV-004
  APA-INV-002("generated source is source") 통합 시점의 세부이므로 Phase-0로 이연.
- `authority` — all-false block(§2.5), 강제.

id 유도: `strategy_id = derive_id("astrat", canonical_digest)`(`_base.py:derive_id`
L72-88). prefix `"astrat"`는 design/config(safety 아님).

### 2.2 Proposal (유일 출력 · effect-free builder)

RFC-008 §8: Proposal이 유일 출력이며 ADR-002-020 §8 Approved Intent Contract field
set을 채운다(field 추가·요건 완화 금지, L251-254). effect-free Proposal Builder로만
조립(L256-258), 발행 시 complete+immutable하며 소비한 exact Capsule identity+digest를
bind(L259-261), wildcard/"latest" 거부(L262-264, ADR-002-020 §8), rationale + Authored
Strategy version + DSL version + config version 부착(L265-267), "emission is the end"
(L268-270).

**결정.** `Proposal`은 `IdDerivedArtifact`를 상속(content-addressed·immutable·Capsule
bind). covered field는 `PROPOSAL-APPROVAL-REQUEST-template.yaml`의 어휘에 정렬(재정의
아님):

- `proposer.{strategy_id, strategy_version}`(template L8-12 대응)
- 의도 행위(RFC-008 §7 L214 MAY-express): `account`/`instrument`/`direction`/
  `position_effect` — **단수 per-instrument scope**(capsule `CapsuleScope`와 정합,
  wildcard 불가)
- `quantity_basis` + `edge_or_confidence` — **evidence로만**: quantity basis와
  edge/confidence는 evidence(RFC-008 §7 L215); desired size 역시 evidence이며
  authoritative capacity가 아니다(§10 L341-342; §12 L435 verbatim "the estimate is
  evidence, never capacity"). §7 서술은 paraphrase이므로 따옴표로 귀속하지 않는다.
- `timing_and_execution_constraints` — **request로만**(RFC-008 §7 L216, RFC-005;
  command 아님)
- `rationale` — RFC-008 §7 L219, §8 L265
- `decision_context_capsule.{capsule_id, canonical_digest}` — bind(template L31-33)
- `dsl_version` / `config_version`
- `authority` — all-false block(§2.5)

**effect-free Proposal Builder**는 순수 함수 `build_proposal(...) -> Proposal`로
모델링한다 — side effect 없음(capacity reserve/notify/reach 없음, RFC-008 §8 L256-258),
wildcard/"latest" 입력을 `ArtifactIntegrityError`로 거부(SOS-INV-004). Explicit Flat은
zero-position target을 가진 Proposal이다(ADR-DEV-007 §7 L190-193).

id 유도: `proposal_id = derive_id("prop", canonical_digest)`.
**Caveat(Phase-0 확인)**: downstream `PROPOSAL-APPROVAL-REQUEST`는 `proposal.proposal_id`와
`proposal.proposal_digest`를 별개 필드로 둔다(template L14-15). 만약 ADR-002-020/023
downstream이 evidence처럼 **독립(injected) proposal_id**를 요구한다면(설계 #4가
§12 same-id/different-bytes 충돌 탐지를 위해 evidence에 독립 id를 채택한 것과 동형),
Proposal은 `DigestBoundArtifact`(독립 id)로 이동한다. 현재는 content-addressing이
RFC-008 §8 L259-261("complete/immutable/bind digest")에 가장 정합하므로 `IdDerived`를
기본값으로 하고 downstream 확정을 Phase-0로 이연한다.

### 2.3 Outcome — No-Action / Explicit Flat / Portfolio Vector (ADR-DEV-007)

RFC-008 §6 principle 2(L181-182): 유일 출력은 Proposal **또는 explicit no-action**.
ADR-DEV-007 §5-8이 output semantics를 확정한다.

**결정.** `Outcome`은 discriminated union:

- `NoActionOutcome` — 아무것도 제안하지 않고 현 포지션/주문을 그대로 둠(ADR-DEV-007
  §5 L114-116). rationale 필수, non-null 1급, error/null 아님(SOS-INV-001 L139-143).
  기반: `tos.canonical.DigestBoundArtifact`(recorded·immutable·reproducible outcome
  record, 독립 id — SOS-INV-001의 recorded·reproducible 요구를 digest-binding으로 충족).
- `Proposal`(§2.2) — per-instrument 단일. **Explicit Flat**은 zero-position target을
  가진 Proposal(§5 L117-120, §7 L190). No-Action과 **혼동 금지 — opposite exposure
  effect**(SOS-INV-001 L142, §7 L194-196, L201-202).
- `PortfolioVector` — per-instrument `Proposal`의 **frozen set**(각기 ADR-002-020 §8
  single-instrument contract, §5 L121-125, §8 L211-213) + `VectorInterdependenceDeclaration`.
  **union/aggregate-authority 필드 없음**(SOS-INV-003 L147-153). 기반:
  `tos.canonical.DigestBoundArtifact`(독립 id — content-addressed 결합권한 identity가
  아님을 구조로 보강; 구성 `Proposal`은 각기 `IdDerivedArtifact` 유지).

`VectorInterdependenceDeclaration`(ADR-DEV-007 §5 L126-130, SOS-INV-006 L161-179):
`ATOMIC`(all-or-none) | `INDEPENDENT`(mutual). **선언 부재 ⇒ ATOMIC fail-closed.**
partial-approval(per-target rejection) 발생 시 atomic vector는 부분 실현되지 않고,
전체 vector 비실현 + fresh-context 재평가라는 **1급 recorded 상태 전이**로 모델링한다
(silent naked partial 금지, §6 L164-172). 실 approval·재평가는 downstream/런타임이므로
Phase 1은 **전이의 표현 가능성과 fail-closed 기본값**만 property로 확인한다.

### 2.4 강제-evidence 레코드 (ADR-DEV-001 §8 L234-236)

강제 layer들은 evidence(admissibility result, capability manifest, bound outcomes)를
ADR-002-016 replay integrity의 conforming input으로 **산출**하되 그것을 정의하지 않는다.

**결정.** 세 레코드 모두 `tos.canonical.DigestBoundArtifact` 상속(**독립 id** —
evidence는 content-addressed authored-artifact가 아니라 ledger 시민에 해당하므로
설계 #4 §3.1의 evidence 패턴을 따름; `IdDerivedArtifact` 아님):

- `AdmissibilityResult` — layer 1 산출. `verdict`(ADMISSIBLE|INADMISSIBLE),
  `reasons`(inadmissible 근거), `candidate_digest`, `enforcement_mechanism_version`,
  `dsl_version`. **Phase 1에서 실제 채워지는 유일한 강제-evidence.** ADR-DEV-001 §5
  L123-124 명시: admissibility는 authority 부여 아님, **ADR-002-029 software-artifact
  admission과 별개.**
- `CapabilityManifest` — layer 2(capability-restricted evaluation) 산출 예정.
  **Phase 1 = 스키마 슬롯만 선언, 미채움**(런타임 부재). scope에 든 capability 목록을
  기록할 자리이나 Phase 1엔 "Capsule read-only + Proposal Builder"라는 상수만 표현.
- `BoundOutcome` — layer 3/bounded-eval 산출 예정. **Phase 1 = 상태기계 전이 결과
  (NoAction on exhaustion)만 표현, 실 계측 미포함**(§3.4).

세 레코드 모두 `enforcement_mechanism_version`을 기록 — DCE-INV-005의 version-recording
facet(ADR-DEV-001 §9 L254-257)의 L1 부분.

### 2.5 all-false authority block (강제)

capsule `CapsuleAuthority`가 `authority.*`를 강제 false로 두는 것(설계 #2 capsule.py
L22, L239)과 동형으로, 모든 DSL 아티팩트(AuthoredStrategy/Proposal/Outcome)는
`PROPOSAL-APPROVAL-REQUEST-template.yaml` L72-82의 all-false block을 그대로 반영한다:
`grants_approval`/`creates_intent`/`mutates_capacity`/`creates_live_authorization`/
`creates_protective_classification`/`creates_transmission_capability`/
`permits_broker_transmission`/`clears_halt`/`permits_rearm`/`permits_automatic_rearm`
전부 false. pydantic validator로 true 값을 `ArtifactIntegrityError`로 거부한다
(SOS-INV-005 L158-160; RFC-008 §8 L272-274 "candidate only").

---

## 3. Purity — static admissibility (layer 1) 순수 술어

ADR-DEV-001 §8은 3층 강제를 규정한다: (1) Static Admissibility Analysis(평가 전),
(2) Capability-Restricted Evaluation(평가 중), (3) Isolation Boundary(잔여 봉쇄). Phase
1은 **layer 1을 순수 술어로 realize**하고 layer 2/3을 이연한다.

### 3.1 Authoring Surface Vocabulary = closed typed AST algebra (DCE-INV-001)

DCE-INV-001(§6 L140-144): 어휘는 **정확히 RFC-008 §7 permitted expression**이고,
그 밖은 *absent from the surface*이지 blocklist가 아니다. "full host + denylist"는
non-conforming.

**결정.** vocabulary를 **closed typed AST node algebra**로 모델링한다 — frozen
pydantic 노드의 discriminated union(예: `ContextRead`(Capsule field 접근),
`ModelEvidenceRead`(RFC-004..007 evidence 읽기), `Comparison`, `ArithmeticOp`,
`ActionProposalNode`, `NoActionNode`, `RationaleNode`, `TimingConstraintNode`,
`ExplicitFlatNode`, `PortfolioVectorNode`). 이 알고리즘은 DCE-INV-001을 **구성적으로**
만족한다: `import`/`network`/`clock`/`FFI`/`reflection`에 **해당하는 노드 타입이 존재하지
않으므로**, 금지 effect는 blocklist된 것이 아니라 **표현 불가(absent)** 다. 이것이
"default-deny = absent-from-surface, not blocklisted"의 가장 강한 EV-L1 실현이다.

이 typed algebra는 **family-독립**이다 — standalone constrained language의 grammar로도,
embedded subset의 admissible-node set으로도 동일하게 읽힌다. 따라서 RFC-008 §14 Q1의
family 선택(ADR-DEV-001 §7 L193-201: 세 family 모두 default-deny+escape-closure면
conforming, 선택은 approved design/config)을 **선점하지 않는다**(§0 미확정).

### 3.2 candidate-AST 도메인 (adversarial 입력)

DCE-EV-004/006은 **adversarial** — inadmissible한 것을 checker에 먹여 거부를 실증해야
한다. typed algebra만으로는 escape 시도를 *표현조차* 못하므로 거부를 테스트할 수 없다.
따라서 별도의 **후보-AST 표현**(`candidate.py`)을 둔다: vocabulary 노드의 superset이며
`UnknownNode`/`ForeignNode` escape hatch(vocabulary 밖 무엇이든 데이터로 담는 open
노드) + escape 마커 노드(`ImportNode`, `DynamicEvalNode`, `ReflectionNode`,
`FfiNode`, `AmbientReadNode`, `WildcardScopeNode`)를 포함한다. 이것은 **테스트 입력
도메인**이며 authored surface가 아니다.

**firewall 준수(핵심)**: 후보-AST는 **데이터**다. checker는 이 pydantic 트리를 walk할
뿐 **import·compile·exec하지 않는다.** 만약 향후 입력 포맷으로 Python source를
받더라도 `ast.parse`(stdlib, 순수 파싱, 실행 없음)로 얻은 `ast.AST`를 walk할 뿐이며 —
이는 설계 #1 §3.3-① `tools/tos_firewall_check.py`가 하는 것과 **정확히 동일**하다 —
`compile`/`exec`/`eval`/`importlib`는 절대 쓰지 않는다(설계 #1 §3.3-①d L206). 입력
포맷 확정은 family/config 사안이므로 Phase-0.

### 3.3 순수 admissibility 술어 (DCE-INV-001/003/004/006)

`is_admissible(candidate) -> AdmissibilityResult`는 순수 함수(`ast`+`pydantic`만):

- **default-deny membership(DCE-INV-001)**: 후보의 모든 노드가 vocabulary 타입에
  속하면 ADMISSIBLE 후보, 하나라도 밖이면 INADMISSIBLE.
- **ambient 참조 탐지(DCE-INV-003, static naming facet)**: `AmbientReadNode` 또는
  clock/randomness/network/filesystem/mutable-global/host-builtin 심볼 참조 → INADMISSIBLE
  (RFC-008 §11 item 12 L392-393). 이것이 설계 #1 AST firewall 게이트의 **runtime-values
  쌍둥이**(§5).
- **escape 탐지(DCE-INV-004)**: `ImportNode`/`DynamicEvalNode`/`ReflectionNode`/
  `FfiNode`/extension 노드 → INADMISSIBLE(RFC-008 §11 item 17 L404-406; ADR-DEV-001은
  reflection을 conservative 강화로 추가, §6 L158-160).
- **content-defect 탐지**: `WildcardScopeNode`(wildcard/"latest") → INADMISSIBLE
  (RFC-008 §11 item 13 L394-395, ADR-002-020 §8). ADR-DEV-001 §8 L230-234가 명시하듯
  이것은 isolation-contained가 아니라 **layer 1 + effect-free Proposal Builder**가 잡는
  content defect다.
- **fail-closed(DCE-INV-006)**: `not provably_admissible(x) ⇒ inadmissible(x)`.
  `UnknownNode`를 만나면 optimistic admit 없이 즉시 INADMISSIBLE(§6 L166-169). 이것이
  Phase 1 커버리지가 가장 높은 술어다(§1).

### 3.4 bounded evaluation 상태기계 (DCE-INV-007)

DCE-INV-007(§6 L170-172): time/resource bound 소진 시 해당 strategy scope에 대해
no-action으로 degrade, unbounded stall이나 partial unrecorded action 금지.

**결정.** 순수 상태기계로 모델링: state ∈ {`EVALUATING`, `COMPLETED(Outcome)`,
`BOUND_EXHAUSTED`}; 전이 `BOUND_EXHAUSTED ⇒ NoActionOutcome`(recorded). bound은
**symbolic/injected**(예: step counter)이며 **numeric 값은 넣지 않는다** — VERIFICATION-
PROFILE-002에 DSL/DCE bound가 **부재**하기 때문(dossier §6; §7 상술). 실 wall-time/CPU/
메모리 계측은 layer 3 런타임이므로 이연.

### 3.5 layer 2/3 이연 + escape-checker 자기 지위

- **layer 2(capability-restricted evaluation)**: 런타임이 Capsule read-only + effect-free
  Proposal Builder만 scope에 두는 강제(§8 L217-220) — EV-L2.
- **layer 3(isolation boundary)**: host-process/dynamic-loading/network-fs egress 차단
  + 실 bound 강제(§8 L221-225) — EV-L2/L3.
- **escape-checker 자기 지위(중요)**: 본 layer 1 checker는 ADR-DEV-001 §5 L132-134가
  정의하는 **Enforcement Mechanism의 구성요소**다. 따라서 DCE-INV-005(§6 L161-165)에
  의해 **스스로를 인증할 수 없다.** 본 계약은 이를 canonicalizer의
  `ev-l1-provisional-0` 패턴과 동형으로 다룬다 — checker를 **provisional·non-authorizing
  모델**로 명시하고, property test를 *authoring* evidence로만 취급하며(acceptance 아님),
  별도 lane의 독립 adversarial 리뷰(ADR-DEV-001 §14 L375-376, ADR-DEV-005)를 gate로
  남긴다. DCE-EV-005는 NOT_IMPLEMENTED 유지.

---

## 4. Determinism 술어 (RFC-008 §9)

RFC-008 §9 L284-289: Authored Strategy 평가는 fixed Decision Context + fixed
configuration의 **순수 함수**이며, ambient clock/wall-time/randomness/mutable-global/
network/filesystem을 노출하지 않는다; trustworthy-time은 Capsule 안의 값이지 live
clock이 아니다.

### 4.1 input signature + pure evaluate 모델

**결정.** 두 개념을 용어로 분리한다. **(a) 함수 데이터 의존성**: 순수 평가는
`evaluate(strategy: AuthoredStrategy, capsule: DecisionContextCapsule, config:
<versioned config>) -> Outcome` — 결과는 오직 이 세 인자(고정된 Authored Strategy,
고정된 Decision Context, 고정된 configuration)에만 의존한다(RFC-008 §9 L284).
`DecisionContextCapsule`은 `tos.capsule`의 frozen 모델(read-only 입력 표면) — 평가는
이를 읽기만 하고 mutate하지 않는다(frozen이므로 구조적으로 불가). **(b) recorded
provenance**: 재현·감사를 위해 평가가 기록하는 서명은 함수 인자보다 넓다(RFC-008 §9
L302-306 + ADR-DEV-001 §9 L254-257):

```text
recorded_input_signature = {
  capsule_id, capsule.canonical_digest,       # RFC-008 §9 L302-303
  authored_strategy_version,                   # L303
  dsl_version,                                 # L303
  config_version,                              # L303
  enforcement_mechanism_version,               # ADR-DEV-001 §9 L254-257
  captured_external_values ⊆ Recorded Input Set  # ADR-DEV-003 EXV-INV-005 L155-158
}
```

### 4.2 captured-not-called (ADR-DEV-003)

RFC-008 §9 L290-301 + ADR-DEV-003 EXV-INV-001(§6 L130-132) + §7(L168-177): external/
LLM 파생 값은 평가 **밖에서·전에** 생산되어 Capsule에 Critical Input으로 전달되고,
DSL 평가는 그 값을 **읽을 뿐 live fetch하지 않는다.** 모델에서 captured value는 이미
Capsule `Observation`(설계 #2 observation.py, external-source provider; `source_event_time`이
as-of 앵커 L77-89)으로 들어와 있으므로, `evaluate`는 fetch capability를 **서명에
갖지 않는다.** EXV-INV-005(L155-158): captured value + provenance + seed + response는
Recorded Input Set의 재현 evidence이지 authority가 아니다.

### 4.3 determinism property + reproducibility granularity 이연

- **referential transparency**: `evaluate(s, c, cfg) == evaluate(s, c, cfg)`(고정
  strategy s·context c·config cfg; §6 property).
- **ambient-independence**: 순수 함수가 clock/RNG/env를 **서명에 갖지 않으므로**
  구조적으로 성립(firewall가 모델 코드의 ambient 도달을 차단, escape-checker가 authored
  artifact의 ambient naming을 차단 — §5).
- **reproducibility granularity는 ADR-DEV-002로 이연(선점 금지).** Phase 1 property는
  **outcome+rationale 동등성**(reproducible-from-recorded-inputs, ADR-DEV-002 ARI-EV-002
  기본값 L113-117)만 주장한다. **bit-for-bit는 platform이 determinism을 보장하는 경우로만**
  한정하는 판단(ARI-EV-002 L116-117)은 ADR-DEV-002 소관이며 본 계약은 이를 선점하지
  않는다.

---

## 5. 정합성 — firewall ↔ escape-checker, "no live fetch" 세 altitude

### 5.1 "no live fetch"는 세 altitude의 동일 불변식

| Altitude | 원천 | 성격 | 어떻게 "no live fetch"를 보장하나 |
|---|---|---|---|
| **mechanism (unexpressible)** | ADR-DEV-001 escape-closure DCE-INV-004 (§6 L154-160) + RFC-008 §11 item 17 (L404-406) | authored **content**, 평가 전 static 차단 | authored artifact가 network/import/FFI/reflection를 **명명(name)조차 못 함** — escape-checker가 inadmissible 처리 |
| **runtime 구조** | 설계 #1 firewall (§3.2 L182-194, §4 L238-270) | tos **구현 closure**, import-time 강제 | tos closure에 network·`shared.llm`·`os.environ` capability가 **부재** — 유출할 ambient가 애초에 없음 |
| **data** | ADR-DEV-003 captured-not-called EXV-INV-001/005 (§6 L130-132, L155-158) | **data provenance**, 평가 전 캡처 | 필요한 external/LLM 값이 **이미 Capsule Critical Input** — fetch할 대상 자체가 없음 |

세 altitude는 서로를 백업한다: firewall가 capability를 없애고(도달할 것이 없음),
escape-checker가 naming을 없애고(표현할 수 없음), capture가 data를 미리 넣는다(가져올
것이 없음). 어느 한 altitude가 약해도 나머지 둘이 "no live fetch"를 유지한다 — 이는
DCE-INV-002(layered non-self-trusting)의 **정신**을 세 계약에 걸쳐 예시한 cross-contract
defense-in-depth다. **주의(over-claim 차단)**: 이 3-altitude(mechanism/runtime/data =
서로 다른 세 계약)는 DCE-INV-002가 명명하는 3개 **DSL-enforcement layer**(static
admissibility / capability-restricted evaluation / isolation boundary — 모두
ADR-DEV-001 내부)와 **다른 3분할**이며, DCE-INV-002의 **discharge가 아니다**(§1이
DCE-INV-002를 L2+로 등재).

### 5.2 firewall ↔ escape-checker = 구조적 쌍둥이

설계 #1 §3.3의 import firewall AST 게이트와 본 계약의 escape-checker는 **동일 기법
(pure `ast` default-deny walk)을 서로 다른 subject에 적용한** 쌍둥이다:

| 축 | 설계 #1 firewall (import 게이트 §3.3) | DSL escape-checker (static admissibility, ADR-DEV-001 §8 layer 1) |
|---|---|---|
| **subject** | `tos/` **소스** `.py` 파일 | **authored artifact** AST (후보 strategy) |
| **시점** | import-time / CI (설계 #1 §3.3-③) | 평가 전 (pre-eval, static) |
| **기법** | `ast.parse` + walk, default-deny 허용목록 | 노드-모델/`ast` walk, default-deny vocabulary |
| **금지 대상** | network/egress stdlib, `os.environ`, `importlib`/`exec`/`eval`, 금지 pkg (§3.2) | ambient-state 참조, FFI, import, reflection, dynamic-eval, host-builtin, wildcard/"latest" |
| **실패 처리** | CI fail → merge 차단 | inadmissible (fail-closed, DCE-INV-006) |
| **자기 제약** | 게이트가 순수 `ast` (no exec, §3.3-①d) | checker가 순수 `ast`/`pydantic` (no importlib/exec/eval) |
| **보장 방향** | 런타임이 ambient capability를 **갖지 않음** | artifact가 ambient capability를 **명명 못 함** |
| **불변식** | SAFE-045 계층 방어 (설계 #1 §4) | DCE-INV-001/003/004 |

핵심: 둘 다 **candidate를 실행하지 않고 정적으로만 분석**한다. firewall는 구현
source를, escape-checker는 authored content를 스캔한다. 함께 "no live fetch"를 capability
측(도달할 것 없음)과 naming 측(표현 불가)에서 동시에 닫는다.

---

## 6. property-test 타깃 (완결 금지) + run manifest

각 property는 해당 EV의 **static facet에 대한 evidence 입력**을 산출할 뿐 EV를
**완결하지 않는다.** DCE-EV-002/005에는 **L1 property가 없다**(§1). 테스트는 설계 #1
firewall 및 RFC-010 §8 suite가 겨냥하는 것과 같은 escape 벡터를 쓰되, **최소 escape-
vector set은 ADR-DEV-009(RFC-010 §14 Q1) 소관**이므로 Phase 1은 starter set이다.

### 6.1 static / escape slice
- **DCE-EV-001 slice**: closed typed algebra에서 금지 노드 타입은 **구성 불가**(pydantic
  discriminated union이 거부); admissible AST에 forbidden 노드를 하나 추가하면
  admissible→inadmissible로 flip(metamorphic).
- **DCE-EV-003 slice(static naming)**: ambient(clock/rand/net/fs/global/builtin) 참조를
  담은 후보 → INADMISSIBLE. hypothesis가 무작위 ambient 심볼을 주입.
- **DCE-EV-004 slice(escape 탐지)**: import/importlib/`__import__`/exec/eval/reflection/
  FFI/extension 노드를 담은 후보 → INADMISSIBLE.
- **DCE-EV-006(fail-closed)**: `UnknownNode`를 포함한 임의 후보 → INADMISSIBLE, optimistic
  admit 절대 없음(hypothesis가 novel 노드 종류를 생성).
- **DCE-EV-007(전이)**: bounded-eval 상태기계가 `bound_exhausted`에서 `NoActionOutcome`으로만
  전이(partial/stall 없음), symbolic bound.

### 6.2 determinism slice
- **referential transparency**: `evaluate(s, c, cfg) == evaluate(s, c, cfg)`.
- **ambient-independence(구조적)**: `evaluate` 서명이 clock/RNG/env를 받지 않음을
  타입 수준에서 확인 + import-closure(§6.4)로 backing.
- reproducibility granularity는 **주장하지 않음**(ADR-DEV-002 이연, §4.3).

### 6.3 output-semantics slice (SOS-EV-001..006)
- **SOS-EV-001**: `NoActionOutcome` ≠ Explicit-Flat `Proposal` — 별개 타입, opposite
  exposure, 둘 다 non-null·non-error.
- **SOS-EV-002/003**: per-instrument vs `PortfolioVector`(set) 둘 다 표현; vector에
  union/aggregate-authority 필드 부재; 단위 declared.
- **SOS-EV-004**: 각 target이 ADR-002-020 §8 field set을 채우고 wildcard-free + Capsule
  bind; Proposal Builder가 wildcard 입력 거부. (ADR-002-020 §8의 구체 field set은
  그라운딩 밖이므로 downstream 확정 전까지 **provisional** — §8 이관.)
- **SOS-EV-005**: 모든 Outcome의 authority block all-false (true → `ArtifactIntegrityError`).
- **SOS-EV-006**: `VectorInterdependenceDeclaration` 부재 ⇒ ATOMIC; atomic vector의
  partial-approval ⇒ whole-vector 비실현 + recorded 재평가 상태(silent partial 없음).

### 6.4 EXV-EV-001 + import-closure (구조적 backstop)
- **EXV-EV-001 slice**: `evaluate` 서명에 fetch capability 부재; captured value가 Capsule
  `Observation`으로만 진입.
- **import-closure 테스트**(설계 #2 §7.1 패턴 확장): `tos.dsl` 패키지의 import closure가
  §2.3 금지 패키지·network stdlib·`os.environ`를 **전혀 포함하지 않음**을 능동 검증.
  이것이 DCE-EV-003/EXV-EV-001의 구조적 backstop이며 escape-checker가 firewall를 스스로
  준수함(§3.2)의 증거다.

### 6.5 run manifest (설계 #1 §5.1 L281-295, 7항목)
evidence를 산출하는 모든 property-test run은 기록한다: (1) git commit digest + `tos`
버전, (2) 인터프리터 + 고정 의존성 버전, (3) 실행 환경 식별자, (4) 하네스 버전(git
digest 갈음), (5) **hypothesis seed**(derandomize 정책, append-only), (6) 소비 설정
아티팩트 digest, (7) 산출 아티팩트 전체 sha256. **완결 금지 고지**: 이 run은 evidence
*입력*을 append하며 DCE-EV status를 IMPLEMENTED/PASS로 바꾸지 않는다.

---

## 7. Bounds / Phase-0 프로파일 소관

- **DCE-INV-007 numeric bound 부재(핵심)**: VERIFICATION-PROFILE-002에 **DSL-evaluation
  time/resource bound은 0건**이다(`VERIFICATION-PROFILE-002-template.yaml` L699의
  `MAX_proposal_approval_request_age_ms`는 downstream approval-request-age bound이지
  DCE-INV-007의 DSL-evaluation bound이 아니다; dossier §6). 따라서
  §3.4 상태기계는 **symbolic bound**만 쓰고, **numeric 값을 invent하지 않는다.** numeric
  bound 승인은 **Phase-0 프로파일 소관 플래그**(설계 #2 §8 누락 delay key, 설계 #4 §8
  `MAX_anchor_cadence_ms` 부재와 동형).
- **cross-scheme collision caveat**: `canonicalization.py` L29-38 — `canonicalization_version`이
  digest preimage/`id=f(digest)`에서 제외되어, 다중 scheme 공존 시 동일 covered content가
  두 scheme에서 같은 digest→같은 id를 낼 수 있다. 단일 `ev-l1-provisional-0`에선 무해하나
  production canonicalizer 도입 전 해소(version을 preimage/id에 접기 또는 namespacing) —
  Phase-0.
- **`ev-l1-provisional-0` non-production**: `EVL1ProvisionalCanonicalizer`(canonicalization.py
  L136-175)는 **명시적 비-production** fixture다. production scheme 승인 = 새 version 등록
  + must-pass property suite 무변경 회귀(§3.1 canonicalization.py L19-27) — Phase-0.
- **escape-checker version**: `enforcement_mechanism_version`을 강제-evidence에 기록하되
  실제 mechanism 검증(DCE-EV-005)은 이연.

---

## 8. 후속 작업 / Phase-0 이관

| # | 항목 | 소유/의존 |
|---|---|---|
| L2 | capability-restricted evaluation 런타임(layer 2) | EV-L2; DCE-EV-003 runtime facet |
| L2/L3 | isolation boundary(layer 3) + 실 time/resource bound 강제 | EV-L2/L3; DCE-EV-002/007 runtime |
| gate | mechanism verification(DCE-EV-005) | RFC-010 §8 adversarial suite + ADR-002-029 admission + 독립 리뷰(ADR-DEV-005) |
| gate | DCE-EV-002 §13.7 3개 single-layer failure 시뮬 | 3층 전부 필요 → EV-L2+ |
| cfg | realization family production 선택(RFC-008 Q1) + 후보 입력 포맷 | approved design/config (ADR-DEV-001 §7 L193-201) |
| Phase-0 | DCE-INV-007 numeric bound (VERIFICATION-PROFILE-002) | 프로파일 소관 인간 게이트 |
| Phase-0 | production canonicalizer + cross-scheme collision 해소 | 설계 #2/#4 §9 정렬 |
| Phase-0 | Proposal id 유도(IdDerived vs 독립) downstream 확정 | ADR-002-020/023 |
| Phase-0 | Proposal target의 ADR-002-020 §8 구체 field set(provisional) 확정 | ADR-002-020 §8 |
| ADR | reproducibility granularity | ADR-DEV-002 (선점 금지) |
| ADR | authoring provenance 최소 레코드 통합 | ADR-DEV-004 APA-INV-001 |
| ADR | degraded companion model 표현 | ADR-DEV-008 |
| Stage 2 | 운영 registry(`shared/strategy/registry.py`)의 DSL 아티팩트 **재저작** | 설계 #1 §1.2 L78-82 (import 아님) |

---

## 9. 개정 로그 + 비준 체크리스트

### 9.1 개정 로그
- 2026-07-21: **v1 최초 작성.** RFC-008 + ADR-DEV-001을 그린필드 `tos/src/tos/dsl/`에
  Phase 1(EV-L1) 순수·비전송 모델 + property test로 실현하는 프로젝트 측 계약. 6개
  결정 의제 해결(§1 도달성 분할, §2 데이터 모델, §3 static admissibility 순수 술어,
  §4 determinism, §5 정합성, §7 bounds/Phase-0).
- 2026-07-21: **v1.1 — 독립 비평 리뷰 ACCEPT-WITH-MINOR (CRITICAL 0, MAJOR 0).**
  핵심 결정(escape-checker AST 정적분석·no exec/eval/import, DCE-INV-002/005 L2+ 이연,
  IdDerived/DigestBound REUSE, 세 altitude 정합성) 유지. MINOR-1(§1 SOS-EV-001 injection
  라인 L314→VER-DEV-001 L306), MINOR-2(§2.2 "sizing=evidence" 따옴표 해제 → §7 L215 +
  §10 L341-342 이중인용, §12 L435 verbatim), MINOR-3(§4.1 함수 데이터 의존성 ↔ recorded
  provenance 분리 + evaluate에 AuthoredStrategy 인자 명시), MINOR-4(§2.3 NoActionOutcome/
  PortfolioVector = `DigestBoundArtifact` 기반 명시), MINOR-5(§6.3 SOS-INV-004 ADR-002-020
  §8 field set = provisional, §8 이관) + open-question 2건(§5.1 3-altitude ≠ DCE-INV-002
  3-layer over-claim 차단, §7 DSL-evaluation bound 0건 정밀화 — L699 approval-request-age는
  무관) 반영. 스펙 미변경, register status 불변, 코드 미작성.
- 2026-07-21: **v1.1 운영자 비준.** 효력: `tos/src/tos/dsl/` Phase 1(EV-L1) 모델 +
  property test 작성 착수. Proposal identity·실현 family·DCE-INV-007 bound은 Phase-0/
  downstream 확정으로 유지.

### 9.2 비준 체크리스트 (운영자 확인 사항)
- [ ] §0 미확정(capability-runtime·isolation·mechanism-verification·authority 미구현
      NO; register status 불변; family 미확정)에 동의
- [ ] §1 EV-L1 도달성 분할과 **"어떤 DCE-EV도 L1-complete 아님"**(특히 DCE-EV-002/005
      L1 커버리지 없음/최소)에 동의
- [ ] §2 데이터 모델(IdDerived Authored Strategy/Proposal, DigestBound 강제-evidence,
      all-false authority, downstream 재정의 금지)에 동의
- [ ] §3 static admissibility 순수 술어(closed typed algebra + fail-closed + escape/
      ambient/reflection 탐지) + escape-checker의 firewall 자기준수(no importlib/exec/eval)에
      동의
- [ ] §4 determinism 서명(Capsule+config-version) + captured-not-called + reproducibility
      granularity ADR-DEV-002 이연에 동의
- [ ] §5 정합성(세 altitude · firewall↔escape-checker 쌍둥이)에 동의
- [ ] §6 property 타깃의 "완결 금지" + import-closure + run manifest에 동의
- [ ] §7 DCE-INV-007 numeric bound 부재 = Phase-0 프로파일 소관에 동의
- [ ] §8 후속/Phase-0 이관에 동의

비준 시 효력: 설계 #1 §6.3 병렬 트랙으로서 `tos/src/tos/dsl/` Phase 1(EV-L1, 비전송)
모델 + property test **작성 착수 승인**. mechanism verification·bounds 승인·독립
리뷰어 지정·ADR acceptance는 별도 게이트로 남는다(§0/§8).
