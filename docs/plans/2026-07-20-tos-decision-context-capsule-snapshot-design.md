# 설계 문서 #2 — Decision Context Capsule + Snapshot 계약 (2026-07-20, v2)

> **비준 기록**: **2026-07-20 운영자 비준 (v2)**. 효력 발생 — IMPLEMENTATION-PLAN-002
> §4 Phase 1(EV-L1)의 ADR-002-018 부분을 그린필드 `tos/src/tos/capsule/`에 순수·비전송
> 데이터 모델 + property test로 작성 착수 승인. §9.2 Phase-0 6항목(bounds 승인·독립 리뷰어
> 지정·digest 자기제외 비준·프로덕션 canonicalization·수치 canonical form·id↔digest 할당
> 정책)은 별도 게이트로 유지. `id=f(digest)` 파생은 현행 §4.1대로 확정하되 외부-할당 대안은
> §9.2 item 6 Phase-0 옵션으로 열어 둔다. (v1 독립 비평 리뷰 REJECT → v2 전 항목 반영 후 비준.)
> 비준 시 효력 —
> [IMPLEMENTATION-PLAN-002](../../tos-spec/src/part-1-foundation/verification/IMPLEMENTATION-PLAN-002.md)
> §4 Phase 1(EV-L1)의 ADR-002-018 부분(§165, line 182–183: "Critical Input Policy,
> source continuity, observation, transformation lineage, consistency cut, Snapshot,
> Decision Context Capsule, common-mode, correction, invalidation, egress-binding
> **models**")을 그린필드 `tos/src/tos/capsule/`에 **순수·비전송 데이터 모델 +
> property test**로 실현하는 프로젝트 측 설계 계약을 확정한다.
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해
> **non-normative**이며 스펙 텍스트(RFC/ADR/템플릿)를 변경하지 않는다. broker-agnostic
> 원칙(project memory `tos-spec-broker-agnostic`): KIS 등 특정 브로커 사실은 프로젝트 측
> 예시(§6)로만 등장하며 규범 주장이 아니다.
>
> **선행 문서(의존)**: [설계 문서 #1 — `tos/` 경계 & import-firewall 계약
> (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md). 본 계약의
> 모든 모델은 설계 #1 §2.4 레이아웃(`tos/src/tos/capsule/`)에 놓이고 §3.2 import
> 허용목록 안에서만 의존한다(§0.3에 명시). 설계 #1 §5.1 run manifest 7항목이 본 계약의
> property-test 실행 기록 형식이다.
>
> **규범 원천**: `ADR-002-018` (Critical Input Integrity, Provenance, and
> Decision-Context Fencing, Status: Proposed). 필드 구조 SoT: `verification/`의
> `DECISION-CONTEXT-CAPSULE-template.yaml`, `CRITICAL-INPUT-SNAPSHOT-template.yaml`,
> `CRITICAL-INPUT-POLICY-template.yaml`, `HUMAN-APPROVAL-SET-template.yaml`,
> `REPLAY-CAPSULE-template.yaml`. **schema_version 실측(m1 정정)**: 모델링 대상인
> capsule/snapshot 2종만 `schema_version: "1.0-DRAFT"`; 참조 템플릿은
> `HUMAN-APPROVAL-SET-template.yaml:2` = `schema_version: "TBD"`,
> `REPLAY-CAPSULE-template.yaml:2` = `version: "TBD"`(schema_version 필드 없음).
>
> **리뷰 이력**: v1 독립 비평 리뷰 **REJECT** — C1(CRITICAL, 코드 실증):
> `shared/config/__init__.py:8`이 `shared.config.secrets`를 무조건 import하고
> `secrets.py:51`이 `os.environ.get(...)`을 읽어, `shared.config` 허용이 ambient 자격증명
> 접근(설계 #1 §4 3차 방어 위반)을 전이로 유입하며 설계 #1 §3.3 게이트가 이를 못 잡음(설계 #1
> v1 REJECT와 동형); M1(MAJOR): §3.4 decimal-form 자기모순; m1–m4 정정. **v2가 전 항목을
> 반영**(§10.1). 이후 다시 독립 비평 리뷰 대기. (IMPLEMENTATION-PLAN-002 §3 line 153/157의
> 하드 배제 규칙: Independent-Safety-Reviewer는 본 문서의 저자/통합자여서는 안 된다.)

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-018 조항별로 **Phase 1(EV-L1)에서 모델·property로 도달 가능한 것과 이연할
   것의 경계**(§1).
2. Critical Input Observation / Transformation Lineage / Field Evaluation /
   Consistency Cut / Critical Input Snapshot / Decision Context Capsule의 **per-element
   데이터 모델 계약**(§2) — canonical 템플릿에 정렬하고, 템플릿이 빈 배열로만 남긴
   Observation·Lineage 원소 스키마를 ADR §9/§10 prose에서 저작.
3. **canonicalization + digest 계약**(§3): 정책 주입 파라미터화, digest 자기제외 집합,
   `canonicalization_version`, 커버리지 규칙, property test용 잠정 EV-L1 canonicalization.
4. **불변성·바인딩 불변식**(§4): frozen 모델 불변식으로서 CII-INV-003/007/008/009,
   소비자 바인딩 표면, 순환 digest 임베딩의 2단계 발행(레이어) 해소 규칙.
5. **보수적 모호성 모델**(§5): field-state 격자와 보수적 집계, "individually fresh ≠
   valid snapshot", common-mode 붕괴.
6. **외부값 캡처 통합**(§6, ADR-DEV-003): captured-not-called의 firewall 구조적 강제,
   Validity Window as-of 앵커, re-wrap 불변, KIS LLM 경로(프로젝트 측 예시).
7. **property-test 하네스 타깃**(§7): EV-L1 도달 항목 vs predicate-only 항목, run
   manifest 정렬.
8. **bounds 주입 파라미터 계약과 누락 프로파일 키의 Phase-0 게이트 플래그**(§8).

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.**
  ARCHITECTURE-GATE-STATUS의 NO 3종은 그대로다. ADR acceptance는 오직 *실행된* evidence로만
  온다(project memory `tos-spec-rfc-authoring-track`).
- **런타임 Context Integrity Service를 구현하지 않는다.** ADR-002-018 §7 표는 "Validate and
  assemble Snapshot/Capsule"의 소유자를 Context Integrity Service로 두지만, Phase 1은 그
  서비스가 산출할 **아티팩트의 순수 데이터 모델**과 그 불변식만 저작한다. 관측 수집·조립·
  발행의 런타임 경로는 비-scope다.
- **어떤 권한도 부여하지 않는다** (CII-INV-011, ADR-002-018 §6 line 190–192; §12 line 326).
  모든 모델의 `authority.*`는 `false` 상수이며, 이는 §4.4에서 모델 불변식으로 강제된다.
- **egress 런타임을 구현하지 않는다.** 설계 #1 §4의 논증대로 tos는 정의상
  non-transmitting이다(자격증명·라우트·주문구성 부재 + 이그레스 코드 firewall 차단). 최종
  egress currentness(§16, CII-EV-009)는 Phase 1에서 **predicate 모델**만 저작한다(§7).
- **CII-INV-014 (Evidence Does Not Replace Prevention)를 Phase-1 out-of-scope로 명시
  배제한다** (m4). "logs·lineage·dashboards·audit·replay·later correction이 admission·
  invalidation·authority·capacity·egress 강제를 대체할 수 없다"(ADR §6 line 202–204)는
  **비-모델 강제 불변식**으로, 순수 데이터 모델이 실현할 대상이 아니라 시스템 강제 게이트
  (설계 #3 하네스·#4 Evidence Store·런타임 egress)의 속성이다. 본 계약의 모델은 evidence를
  *산출*하되(§6.3 EXV-INV-005; §9.1) 그 evidence가 prevention을 대체하지 않음을 스스로
  강제하지는 않는다.
- **venue_constraint_snapshot / order_admissibility_decision 자체 모델을 저작하지
   않는다** (ADR-002-019 소관, 별도 문서). 본 계약은 capsule이 그들의 digest를 **참조로만**
   담는 경계와 순환 해소 규칙만 정한다(§4.3).
- **digest 알고리즘·canonical serialization의 프로덕션 선택을 하지 않는다**(ADR-002-018
  OQ1 line 641, §28 gate item 1 line 660). §3은 이를 주입 파라미터로 두고, property test용
  잠정 canonicalizer만 픽스처로 정의한다.
- **VERIFICATION-PROFILE-002 bounds 승인·독립 리뷰어 지정을 대체하지 않는다**(Phase-0의
  별도 인간 게이트; 설계 #1 §0과 동일). 본 계약 비준으로는 *모델+property test 작성*만
  착수 가능해진다.

### 0.3 firewall 제약 (설계 #1 §3.2에 대한 본 계약의 준수 선언)

capsule/snapshot 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만), `pyyaml`(템플릿·정책
  YAML 로드 — **정책/템플릿 로딩의 유일한 수단**). **`numpy`/`pandas`는 capsule/snapshot
  순수 모델이 import하지 않는다** — 수치 계산이 없으므로 closure를 최소화한다(설계 #1 §4
  잔여 리스크 최소화에 기여).
- 커먼즈: `shared.exceptions`, `shared.utils`만(리뷰 실측상 두 패키지의 closure는 clean).
  `shared.determinism`은 하네스(설계 #3)용이지 순수 모델의 의존이 아니다.
- **`shared.config`는 의존하지 않는다 (C1 — v1 REJECT의 CRITICAL, 코드 실증)**:
  `shared/config/__init__.py:8` = `from shared.config.secrets import SecretsManager,
  require_secret`로 패키지 `__init__`이 secrets를 **무조건 즉시 import**하고,
  `shared/config/secrets.py:51` = `os.environ.get(...)`으로 ambient 자격증명을 읽는다. 따라서
  `shared.config`를 허용하면 (i) 설계 #1 §4 3차 방어("`os.environ` 금지")가 전이로 뚫리고,
  (ii) 설계 #1 §3.3-① AST 게이트는 문면 top-level import만 보아 이를 못 잡으며, ②
  import-linter는 secrets가 §2.3 금지 목록에 없어 못 잡는다(강제 사각). 정책·템플릿 YAML
  로딩은 위 `pyyaml`만으로 수행하며 `shared.config`는 firewall closure에서 배제한다. 이
  수정으로 §6.1의 "captured, not called" 구조적 강제 논증이 **더 강해진다**(config 경유
  ambient 접근도 원천 차단). 이 배제를 능동적으로 강제하는 것이 §7.1 import-closure 검증
  테스트다.
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`,
  **`shared.llm`**, `shared.storage`, `shared.backtest`, `services.*`, `cli.*`
  (설계 #1 §2.3). 특히 `shared.llm` 금지는 §6의 EXV-INV-001("captured, not called")을
  **구조적으로** 강제한다: 모델이 LLM 엔드포인트를 import할 수 없으므로 LLM 값은 오직
  캡처된 데이터로만 진입한다.
- **`shared.models` 재사용 주의**: `shared/models`는 firewall 허용이나 그 내용은
  트레이딩 런타임 어휘(broker_position, futures_context, position, signal — 실측)로,
  broker-agnostic 안전 커널에 부적합하다. 따라서 `safety_critical_facts` 등은 **중립
  스칼라/enum**으로 표현하고(템플릿이 plain scalar를 쓰는 것과 일치), `shared.models`
  트레이딩 타입은 import하지 않는다. 이는 DRY(CLAUDE.md)와 broker-agnostic를 함께 만족한다.

---

## 1. 범위 매핑 — ADR-002-018 조항별 EV-L1 도달성

EV-level 정의(VER-002-001 line 142–152): **EV-L1 = Model and Property Verification**
(state-machine exploration, model checking, property-based testing, deterministic
simulation). **EV-L2 = Component Fault Test**(controlled failure injection +
authoritative state inspection). Phase 1은 EV-L1만이다.

| ADR-002-018 조항 | Phase 1(EV-L1)에서 | 근거 |
|---|---|---|
| §5.1 Critical Input Policy (line 110–112) | **모델(불변 governing 아티팩트 참조)** | 정책은 §3 주입 파라미터의 원천. 정책 *활성화*(ADR-002-014)는 비-scope |
| §5.2/§9 Observation (line 114–116; 249–272) | **모델 + property** (gap 1) | 순수 데이터 스키마; admission reject/uncertain 판정은 순수 술어 |
| §5.4/§10 Transformation Lineage (122–124; 276–290) | **모델 + property** (gap 1) | 재현불가/불완전 lineage ⇒ INVALID는 순수 술어 (CII-EV-004) |
| §5.5/§11 Snapshot + Consistency Cut (126–128; 294–312) | **모델 + property** | field-state 집계·cut 비호환·common-mode 붕괴 순수 모델 (CII-EV-005) |
| §5.6/§12 Decision Context Capsule (130–132; 315–328) | **모델 + property** | frozen 불변성·digest 커버리지·바인딩 표면 (CII-EV-007 core) |
| §5.7 Context Generation (134–136) | **모델(monotonic generation 술어)** | 순서 술어; 분산 fence의 런타임은 비-scope |
| §5.8 Material Context Change (138–140) | **모델(보수적 기본값 술어)** | "unknown materiality ⇒ material"은 순수 술어 |
| §5.9 Consistency Cut (142–144) | **모델** | 템플릿 `consistency_cut` 실현 |
| CII-INV-001..010,012 | **모델 불변식** | §4·§5에서 frozen 모델 불변식/술어로 |
| CII-INV-011 (authority 부재) | **불변식(authority.*:false)만** | "경로 없음"의 전수 증명은 L2+; §0.2·§4.4 |
| CII-INV-013 (Restriction Dominates Recovery) | **모델(non-revival 상태 술어)** | recovery가 옛 Capsule/approval/authority를 못 살림; §4.4·§7 CII-EV-012 |
| CII-INV-014 (Evidence ≠ Prevention) | **out-of-scope (명시 배제)** | 비-모델 강제 불변식(§6 line 202–204); §0.2 |
| §13 Independent Approval Inputs (332–346) | **바인딩 표면만** | 승인 *서비스*는 ADR-002-023; capsule이 노출하는 recompute 표면만(§4.2) |
| §14 Freshness/Uncertainty (350–367) | **모델(주입 bound 술어)** | bound는 §8 주입 파라미터; 값은 미승인 |
| §15 Binding (371–390) | **바인딩 표면 계약** | 소비자 목록·거부 규칙; 소비자 *구현*은 각 ADR |
| §16 Final-Egress Currentness (394–409) | **predicate 모델만** | CII-EV-009는 EV-L2/L3; §7·§0.2 |
| §17 Correction/Invalidation (413–431) | **모델(dependency-closure 술어)** | fan-out + "economic effect persists"는 상태 모델 (CII-EV-008) |
| §18 Degraded/Protective (435–446) | **부분(deny-new-risk 술어)** | CII-EV-010 core는 L1; +Broker는 이연 |
| §19–20 Failure/Recovery/Non-Revival (450–482) | **모델(non-revival 상태 술어)** | CII-EV-012 core는 L1; +Security는 L2+ |

세부 EV 항목별 도달성(VER-002-001 Part XVIII §218–229, line 1889–1971 재확인)은 §7 표로
정리한다.

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**
(`model_config = ConfigDict(frozen=True)`)로 저작한다. frozen은 §12(line 328) "A Capsule
is immutable"의 모델 실현이다 — 어떤 필드도 사후 변경 불가하며, 변경은 **새 객체 생성 →
digest 재계산 → 새 identity**를 강제한다(§4.1). 모든 필드는 canonical 템플릿의 필드명을
그대로 쓴다(스펙 용어 = 코드 용어, 설계 #1 §2.4).

### 2.1 공통 field-state enum

ADR-002-018 §11 (line 302)이 규정한 5-값 격자를 모든 원소 평가에 사용한다:

```
FieldState = VALID | UNKNOWN | STALE | CONFLICTED | INVALID
```

보수성 격자(restrictiveness lattice, §5.1에서 집계에 사용):
`INVALID ≻ CONFLICTED ≻ STALE ≻ UNKNOWN ≻ VALID`. VALID는 **모든** 차단 술어를 통과할
때만 도달하는 유일한 허용 상태다(CII-INV-005, line 166–168).

### 2.2 Critical Input Observation (gap 1 — 신규 저작)

템플릿의 `CRITICAL-INPUT-SNAPSHOT-template.yaml:observations: []` (line 27)는 원소 스키마가
없다. ADR §5.2(114–116) + §9(249–272)의 필드 목록에서 저작한다:

| 그룹 | 필드 | 근거(ADR §9 line) |
|---|---|---|
| `source` | principal_id, provider, product_feed, endpoint, environment, account_scope, venue_scope | 253 |
| `trust_identity` | credential_ref(비밀 노출 금지), trust_class | 254 |
| `continuity` | source_continuity_id, connection_session_id, native_sequence, native_revision, page_cursor, completeness_claim, **continuity_gap: bool** | 255, 272 |
| `raw` | raw_event_id, payload_digest | 256 |
| `time` | source_event_time, receipt_trustworthy_time_anchor, source_time_uncertainty, transport_uncertainty | 257 |
| `semantics` | schema_version, semantic_contract_version | 258 |
| `mapping` | instrument, contract, venue, account, currency, unit, scale, multiplier, sign | 259 |
| `correction_links` | correction_of, retraction_of, supersedes, predecessor_ids[] | 260 |
| `ingestion_generations` | software_gen, parser_gen, policy_gen, deployment_gen, evidence_gen | 261 |
| `admission` | result: `ADMITTED\|REJECTED\|UNCERTAIN`, reject_reasons[] | 263–272 |
| `field_state` | FieldState (§2.1) | §11 line 302 |

- **비밀 금지 불변식**: `trust_identity.credential_ref`는 참조만 담고 secret 값을 담지
  않는다(§9 line 254 "without exposing secrets"). 이는 firewall가 `shared.config`(→ 전이
  `shared.config.secrets`) 자체를 closure에서 배제하는 것(§0.3 C1)과 이중으로 정합한다 —
  모델은 secret 소스에 **접근할 수 없고**, 관측 스키마도 secret 값을 담지 않는다.
- **admission 술어(순수)**: §9 line 263–272의 reject/uncertain 조건(unknown source, seq
  reset/rollback/gap, schema drift, wrong env/account/venue/unit/scale/sign/multiplier,
  unverifiable timestamp, out-of-trust endpoint)은 관측 하나에 대한 순수 함수로 property
  테스트한다(CII-EV-002의 L1-modelable 부분 — 단, 실제 fault injection은 L2+, §7).
- **continuity_gap 불변식**: 연속성이 TCP health·uptime·credential validity·동일
  payload·cached sequence로부터 **추론되지 않는다**(§9 line 272). 미확정 연속성은
  `continuity_gap=true`이고 의존 새 위험을 차단한다.

### 2.3 Transformation Lineage (gap 1 — 신규 저작)

템플릿 `transformation_lineage: []` (line 28) 원소 스키마. ADR §5.4(122–124) +
§10(276–290)에서 저작:

| 그룹 | 필드 | 근거(ADR §10 line) |
|---|---|---|
| identity | output_id, output_digest | §10 그래프 노드 |
| `parents` | [{parent_id, digest}] (exact parents + digests) | 280 |
| `transform_graph` | ordered op list | 281 |
| `versions` | code_build, model, formula, library, schema, config | 282 |
| `unit_conversions` | [{before_unit, after_unit, factor}] | 283 |
| `numeric_behavior` | rounding, clipping, interpolation, imputation, aggregation, missing_data | 284 |
| `stochastic` | is_stochastic: bool, params, **random_seed \| nondeterminism_declaration** | 285 |
| `output_spec` | type, range, precision, uncertainty, intended_scope | 286 |
| `common_mode_tags` | [] (예: 공유 library id) | 290 |
| `reproducible` | bool | 288 |
| `field_state` | FieldState | §11 line 302 |

- **재현성 불변식(CII-EV-004)**: `reproducible=false` 또는 parent 누락 ⇒ 파생 입력은
  new-risk용 `INVALID`(§10 line 288). property: `not reproducible OR any(parent missing)
  ⟹ field_state == INVALID`.
- **hidden-default 금지**: 정책 밖의 forward fill·zero fill·silent coercion·symbol
  alias·fallback source는 표현 불가/불법(§10 line 288). 모델은 이런 변환을 명시 op로만
  담을 수 있고, `numeric_behavior`에 기록되지 않은 imputation은 lineage 불완전으로 간주.
- **common-mode 태깅**: "proposer와 approver가 같은 library" ⇒ common-mode(§10 line 290).
  `common_mode_tags`가 §5.4의 붕괴 판정 입력이 된다.

### 2.4 Field Evaluation (gap 1 — 신규 저작)

템플릿 `field_evaluations: []` (line 29) 원소. ADR §11(294–312):

| 필드 | 의미 | 근거 |
|---|---|---|
| field_ref | 평가 대상(safety fact 또는 observation 필드) | §11 line 299 |
| state | FieldState | §11 line 302 |
| checks | {range, rate, crossed_state, cross_field, mapping, unit, venue_session} | §11 line 304 |
| freshness | {source_age, receipt_age, within_bound: bool, bound_ref} | §11 line 303; §14 |
| worst_credible_bound | 최악 신뢰 경계 | §11 line 306 |
| blocking | bool (차단 의존 여부) | §11 line 307, 311 |

- **freshness는 주입 bound로만**(§8): `within_bound`는 `bound_ref`가 가리키는 정책
  파라미터에 대해 평가되며 임계값을 하드코딩하지 않는다.

### 2.5 Consistency Cut (템플릿 정렬 + 1필드 추가)

템플릿 `consistency_cut` (line 20–26)을 그대로 쓰되, §11의 "individually fresh ≠ valid"
게이트를 명시 필드로 만든다:

```
consistency_cut:   # 템플릿(line 20–26) SoT와 1:1 — 신규 저장 필드 없음
  cut_id, source_continuity_vector[], source_revision_vector[],
  receipt_interval, atomicity_proven: bool (기본 false),
  uncertainty: FieldState (기본 UNKNOWN)
```

- **`cut_compatible`는 저장 필드가 아니라 파생 술어**(비저장, digest-covered 아님; m3 정정):
  `source_continuity_vector`·`source_revision_vector`·field_evaluations로부터 계산되는 순수
  함수다. 저장하지 않으므로 snapshot canonical bytes는 템플릿 SoT와 바이트 정렬을 유지한다
  (§2.6). 파생 술어 `cut_compatible(snapshot)=false`이면 개별 필드가 모두 VALID여도 snapshot은
  VALID가 될 수 없다(§11 line 309, CII-INV-007 line 174–176). 이것이 §5.1/§5.2의 핵심.

### 2.6 Critical Input Snapshot (템플릿 SoT 정렬)

`CRITICAL-INPUT-SNAPSHOT-template.yaml`(51 line) 구조를 1:1로 모델링한다(신규 **저장** 필드
없음 — §2.2–2.4의 원소 스키마는 빈 배열이던 `observations`/`transformation_lineage`/
`field_evaluations`의 *원소* 타입일 뿐 새 top-level 키가 아니며, §2.5 `cut_compatible`는 파생
술어라 저장되지 않는다). 따라서 snapshot canonical bytes는 템플릿 SoT와 정렬한다. 배열 원소는
§2.2–2.4의 저작 스키마를 사용한다. `validity.result`(line 39)의 집계 규칙은 §5.1에서 정의한다.
`authority.*:false`(line 44–50)는 §4.4 불변식.

### 2.7 Decision Context Capsule (템플릿 SoT 정렬 + 레이어 구분)

`DECISION-CONTEXT-CAPSULE-template.yaml`(83 line) 구조를 모델링하되, **필드를 3레이어로
분류**한다(§3·§4에서 digest·순환에 사용):

- **Layer-1 (context identity, digest-covered)**: `artifact_type`, `schema_version`,
  `issuer_principal_id`, `critical_input_policy{...}`, `context_generation`,
  `critical_input_snapshot{snapshot_id, canonical_digest}`, `scope{...}`,
  `safety_critical_facts{...}`, `generation_vector{...}`, `independent_validation{...}`,
  `validity{...}`, `authority{...}`. — ADR §12(line 317–326) 열거 집합에 대응.
- **Layer-0 (identity outputs, self-excluded)**: `capsule_id`, `canonical_digest`,
  `status`, (서명). — §3.2.
- **Layer-2 (downstream back-references, self-excluded, Phase 1 미populate)**:
  `bindings{proposal_id..egress_request_digest}` (line 66–74),
  `venue_constraint_policy`·`venue_constraint_snapshot`·`order_admissibility_decision`
  (line 15–25). — ADR §12는 이들을 열거하지 **않는다**(ADR-002-019 소관); §4.3에서 순환
  해소. **`venue_constraint_policy`를 Layer-2로 두는 근거(리뷰 지적)**: ADR §12 line 320의
  "policy"는 §5.1/§8의 **Critical Input Policy(= `critical_input_policy`)만** 지칭한다;
  `venue_constraint_policy`는 ADR-002-019 소관의 별개 governing 아티팩트로 capsule의 context
  identity가 아니라 downstream 참조이므로 Layer-2다.

> **주의(broker-agnostic)**: `safety_critical_facts`(account, instrument, direction,
> quantity_basis, unit, price_and_order_constraints[], exposure_effect,
> session_and_tradability, expiration; 템플릿 line 34–43)는 중립 스칼라로 표현한다(§0.3).
> `session_and_tradability`는 **fact**로서 Layer-1(covered)에 있으므로, venue 사실 자체는
> capsule identity에 포함된다 — Layer-2로 빠지는 것은 ADR-002-019의 *아티팩트 digest*뿐이다.

### 2.8 Context Generation (§5.7 실현)

monotonic generation 정수와 순서 술어만 모델링한다: "older generation이 newer
restrictive generation 이후 new-risk를 authorize할 수 없다"(§5.7 line 134–136). 분산 배포·
fence의 런타임은 비-scope(§0.2). capsule은 `context_generation`(Layer-1)과
`validity.invalidation_generation`(Layer-1)으로 이를 노출한다.

---

## 3. Canonicalization + digest 계약

### 3.1 파라미터화 (프로덕션 선택 금지)

ADR-002-018 OQ1(line 641)과 §28 gate item 1(line 660)은 canonicalization·digest 알고리즘을
**미승인 open question**으로 둔다. 따라서:

- digest 알고리즘과 canonical serialization은 **governing 정책에서 주입**하는 파라미터다
  (`EVIDENCE-INTEGRITY-POLICY-template.yaml`의 `content_digest_algorithm: TBD`,
  `canonical_serialization: TBD`, `canonicalization_version: TBD` — dossier §6 선례).
- 모든 아티팩트는 `canonicalization_version`을 versioned 필드로 담는다(선례:
  `ORDER-CONFORMANCE-PROOF.construction_identity.canonicalization_version`; ADR-002-020
  §9 "supported canonicalization versions"). 모델은 이 버전을 **입력으로 받고**, 특정
  알고리즘을 하드코딩하지 않는다.

### 3.2 digest 자기제외 집합 (gap 3 — **프로젝트 측 신규 결정**)

어떤 규범 원천도 `canonical_digest`가 자기 preimage에서 제외됨을 명시하지 않는다(dossier
§6 gap 3). 본 계약이 명시적으로 정의한다. **preimage(canonicalize 입력)에서 제외되는
집합**:

1. **identity outputs**: `canonical_digest`(수학적 필연 — 출력을 입력에 넣을 수 없음),
   `capsule_id`/`snapshot_id`. — id는 발행 시 digest에서 **파생**(`id=f(digest)`, §4.1)되어
   preimage에서 제외된다. **id와 digest는 항상 쌍으로 함께 바인딩된다**(모든 바인딩 사이트가
   `{..._id, canonical_digest}` 쌍을 담는다 — dossier §2). id를 digest에서 파생하면 id↔digest
   순환을 피하면서 content-addressing 규율(ADR-DEV-002 ARI-INV-001)을 만족하고, factory가 그
   관계를 검증한다(§4.1). 외부-할당 id 정책은 §9.2 item 6.
2. **`status`**: lifecycle 마커(DRAFT/ISSUED/...). content identity에서 제외하고
   서명/evidence 레이어가 attest한다. 근거: CII-INV-003(line 158–160)의 "same exact
   Capsule digest" 바인딩은 발행 lifecycle 전반에서 digest가 안정적일 것을 요구하므로,
   status를 covered에 넣으면 동일 콘텐츠의 lifecycle 전이마다 identity가 바뀌어 바인딩이
   깨진다.
3. **서명 필드**: preimage → digest → 서명 순서이므로 서명은 preimage에서 제외(표준).
4. **Layer-2 downstream back-references**(capsule): `bindings.*`,
   `venue_constraint_policy`, `venue_constraint_snapshot`, `order_admissibility_decision`.
   — §4.3 순환 해소.

**TBD/null placeholder 처리**: "TBD 필드 제외"가 아니라 — **covered 집합에 TBD/null이
하나라도 있으면 그 아티팩트는 아직 digest 불가(pre-issuance, status=DRAFT)**로 규정한다.
canonical_digest는 covered 필드가 모두 구체값으로 채워진 발행 시점에만 정의된다. (템플릿의
`status: DRAFT` + 다수 `TBD`는 정확히 이 pre-digest 상태다.)

### 3.3 digest 커버리지 규칙

ADR-002-019 §14(dossier §6, line 343) "canonical digest SHALL cover all fields that can
change the decision or economic effect" + ADR-002-018 §12(line 328) "Updating one field ...
creates a new identity and digest"를 다음으로 실현:

- **covered = Layer-1 전체**(§2.7 capsule; §2.6 snapshot의 관측/lineage/field_eval/cut/
  validity.result/scope/intended_use/trustworthy_time). 즉 economic effect를 바꿀 수 있는
  모든 필드.
- **snapshot digest는 capsule digest의 입력**이다(capsule Layer-1이
  `critical_input_snapshot.canonical_digest`를 포함). 이는 **snapshot → capsule의 단방향
  DAG**로, 순환이 아니다(순환은 §4.3의 venue/adm/bindings만).

### 3.4 잠정 EV-L1 canonicalization (gap 2 — property test 픽스처, 非프로덕션)

프로덕션 선택 없이 EV-L1 property test를 가능케 하기 위해:

- 테스트는 **특정 바이트가 아니라 canonicalizer의 계약 속성**을 검증한다. 속성을 두 등급으로
  분리한다(M1 — v1의 수치 규칙 자기모순 봉합):
- **(A) must-pass 불변식 — 어떤 conforming/프로덕션 canonicalizer도 만족해야 함**:
  1. **결정성**: 같은 covered 콘텐츠 ⟹ 같은 digest.
  2. **매핑 키 순서 독립**: dict 키 순서를 바꿔도 digest 불변.
  3. **covered 민감성**: covered 필드 한 개라도 바뀌면 digest가 (거의 확실히) 바뀐다.
  4. **excluded 불감성**: §3.2 제외 집합만 바뀌면 digest 불변.
  5. **injective(도메인 한정)**: 서로 다른 covered 콘텐츠가 같은 canonical form으로 접히지
     않는다(충돌 저항은 알고리즘 몫).
  이 (A) suite는 프로덕션 canonicalizer 선택 시에도 그대로 회귀 검증된다.
- **(B) 잠정 전용 fixture-level property — `ev-l1-provisional-0`에만 bound, 프로덕션
  불변식 아님**:
  6. **수치 표현 정규화(잠정)**: 잠정 canonicalizer는 magnitude를 decimal로 정규화한다(예
     `1.0`≡`1.00`, float 이진 오차 배제). **이것은 프로덕션 canonical form 선택을 선점하지
     않으며** (A) must-pass suite에서 **제외**된다(§9.2 item 4). 결정적으로, 이 magnitude
     정규화는 **`scale`·`unit`·`multiplier`·`sign`의 구별을 접지 않는다** — 이들은 ADR §9
     (line 259, 268)·§12(line 323)가 경제적으로 유의미한 안전 필드로 취급하는 **별개 covered
     필드**이며, `1.0`≡`1.00` 정규화는 값의 magnitude에만 적용될 뿐 scale/unit 메타데이터를
     병합하지 않는다(안전-유의 구별 보존).
- 잠정 인스턴스: `canonicalization_version = "ev-l1-provisional-0"` — 재귀 key-sorted,
  UTF-8, (B)의 magnitude 정규화, 제외 집합 제거 후 해시. **명시적으로 non-production 픽스처**
  이며 run manifest(§7)의 `canonicalization_version`에 기록된다. 프로덕션 canonicalizer가
  승인되면 **(A) suite를 통과**해야 하므로 잠정 인스턴스 교체가 (A) property를 무효화하지
  않는다. **프로덕션 수치 canonical form은 미결(§9.2 item 4)이며 (B)는 그 선택을 선점하지
  않는다** — 이것이 §3.4 안정성 주장과 §9.2 이관의 봉합점이다.

---

## 4. 불변성·바인딩 불변식

### 4.1 frozen + digest 일관성 (CII-INV-003, §12)

- 모델은 frozen. 생성자/팩토리는 **canonical_digest == H_ver(canonicalize(covered))**를
  검증하고, 불일치면 구성 실패(잘못된 digest를 가진 아티팩트는 형성 불가). 이로써 "필드
  변경 = 새 객체 = 새 digest"(§12 line 328)가 타입 수준에서 강제된다.
- **id↔digest 바인딩 강제 (리뷰 지적)**: 위 factory는 `digest==H(covered)`만 검증할 뿐
  `capsule_id↔canonical_digest` 관계를 검증하지 않으면 id-substitution에 취약하다. **Phase 1
  결정**: id를 digest에서 **파생**한다(`{artifact_prefix}-{canonical_digest}` 형태의 결정적
  함수 `id=f(digest)`). factory가 `id == f(canonical_digest)`도 함께 검증하므로 임의 id
  재부착·digest 교체가 구성 실패로 걸린다. 외부-할당 id 정책(파생 불가)을 택하면
  id-substitution(같은 digest에 다른 id, 또는 그 역)이 CII-EV-007 substitution-resistance와
  긴장하므로 그 정책은 Phase-0로 이관한다(§9.2 item 6).
- property: 임의 capsule `c`에 대해 covered 필드 하나를 바꾼 `c'`는 `c'.canonical_digest !=
  c.canonical_digest`이고 `c'.capsule_id != c.capsule_id`(파생 id; §4.3 excluded 제외).
  (CII-EV-007 core, VER §224.)

### 4.2 소비자 바인딩 표면 + recompute 표면 (gap 7 해소)

ADR-002-018 §15(line 373–382)의 8개 바인딩 포인트와 RFC-003의 두 조항이 **긴장**한다:
- RFC-003 §8(line 234–235): decision layer는 Critical Input을 **capsule을 통해서만** 소비
  (direct fetch/cache/side-channel 금지).
- RFC-003 §10 proviso(line 365–382): Independent Approval Service는 safety-critical
  facts(account, instrument, direction, quantity, price constraints, exposure)를 **Critical
  Input Snapshot에서** 재도출(proposer의 값을 신뢰하지 않음).

**해소(모델 표면으로 조화)**: capsule은 **단일 진입점**이되, snapshot을 **capsule을 통해
참조로 도달**하게 한다. 모델은 두 표면을 모두 노출한다:

1. `critical_input_snapshot{snapshot_id, canonical_digest}` (Layer-1, covered) — snapshot은
   content-addressed이므로 이 digest로 **grounded 관측/field_evaluations에 도달**하는 경로.
   §13 step 3의 recompute 대상은 이 snapshot이다. approver는 capsule을 우회하지 않고
   capsule이 임베드한 snapshot 참조를 **따라간다**.
2. `safety_critical_facts{...}` (Layer-1, covered) — proposer가 주장하는 **요약 fact**.
   §13 step 4의 "compare recomputed facts to the proposal and Capsule" 대상.

따라서 §8("through the capsule")과 §10/§13("from the snapshot")은 모순이 아니다:
safety_critical_facts는 *주장*, snapshot은 *근거*이며, 둘의 일치가 승인 전제다. **그리고
snapshot 재도출이 §13 독립성을 위반하지 않는 이유(리뷰 지적)**: approver는 snapshot 값을
*신뢰*하는 것이 아니라, snapshot이 노출한 observation/lineage를 **독립·공통모드-분석된
corroboration 경로**(§13 step 2/5; §5.2 common-mode 붕괴)로 재검증한다. snapshot은 "무엇을
재계산할지"의 대상 명세이지 "정답"이 아니며, proposer/approver가 같은 소스·parser·library를
공유하면 그 경로는 독립으로 계수되지 않는다(§10 line 290). capsule 모델은 (a) snapshot
id+digest 임베드, (b) safety_critical_facts 노출, (c) `independent_validation{required,
required_facts[], approved_paths[], common_mode_dependencies[], residual_risk_ids[]}`
(template line 53–58) 노출로 이 recompute 계약을 완비한다.

**Net 바인딩 표면**(dossier §2 요구; 모델이 반드시 노출): `capsule_id`,
`canonical_digest`, `context_generation`, `critical_input_snapshot.{snapshot_id,
canonical_digest}`, `validity.{maximum_age_ms, expires_at, invalidation_generation,
invalidation_conditions}`, 전체 `scope`, 전체 `safety_critical_facts`, `generation_vector`,
`independent_validation.{required_facts, common_mode_dependencies, residual_risk_ids}`.

### 4.3 순환 digest 임베딩 — 2단계(레이어) 발행 (gap 4 해소)

**순환의 실체**: 템플릿상 capsule은 venue_constraint_snapshot·order_admissibility_decision
digest를 임베드하고(line 19–25), 두 아티팩트는 역으로 capsule digest를 임베드한다(dossier
§2b). 또한 capsule `bindings.*`(proposal_id, intent_id, ..., egress_request_digest)도
**downstream** 식별자다 — 같은 종류의 전방 순환.

**근거 기반 관찰**: ADR-002-018 §12(line 317–326)는 capsule covered 집합에
venue_constraint_snapshot·order_admissibility_decision을 **열거하지 않는다**(그들은
ADR-002-019 산출물). 그리고 ADR-002-023 §13 바인딩 체인(dossier §2d)은 **capsule을
먼저** 두고 → proposal → candidate command → venue snapshot+decision → 승인 순서로 흐른다.
즉 venue/adm/bindings는 **capsule보다 downstream**이다.

**해소 규칙 — 레이어드 발행**:
- **Phase A (capsule identity 발행)**: snapshot digest를 먼저 계산 → capsule Layer-1
  preimage(snapshot digest 포함, venue/adm/bindings **미포함**) → `capsule.canonical_digest`
  계산 → `capsule_id` 할당. capsule identity는 **downstream에 의존하지 않고** 확정된다.
- **Phase B (downstream 체인 바인딩)**: proposal·venue_constraint_snapshot·
  order_admissibility_decision·HUMAN-APPROVAL-SET 등이 각자 확정된 `capsule.{id, digest}`를
  **권위 있게** 바인딩(그들의 템플릿과 §15가 이를 요구). 순환의 "역방향 엣지"는 여기서만
  authoritative하다.
- **Phase 1 결정**: **capsule 모델의 Layer-2 필드(venue/adm 블록, bindings.*)는 Phase
  1에서 미populate(null)**한다. 이들은 digest에서 제외(§3.2)되어 순환을 원천 차단하고,
  전체 체인은 downstream 아티팩트 + Evidence Store(설계 #4)에서 재구성한다. capsule은 그들
  digest를 **참조로만** 담을 수 있는 자리(스키마)를 선언하되, Phase 1 순수 모델은 그것을
  채우지 않는다(§0.2 경계).

→ 결과: "어느 digest를 먼저 계산하는가?"의 답은 **snapshot → capsule (Phase A)이 먼저,
venue/adm/bindings는 그 다음(Phase B)**이며, capsule digest는 절대 downstream digest에
의존하지 않는다.

### 4.4 authority 부재 불변식 (CII-INV-011)

모든 아티팩트의 `authority.*`는 `false` 리터럴이며 모델이 이를 강제한다(값이 true면 구성
실패). capsule/snapshot/policy 템플릿의 `authority` 블록(각 line 44–50 / 75–82 / 28–35)과
정합. 이는 §16(egress)·§13(approval)의 권한이 이 모델 밖에 있음을 타입으로 보증한다. **단
"권한 경로가 어디에도 없다"의 전수 증명은 EV-L2/L3(CII-EV-011)이며, Phase 1은 이 불변식
술어만 property 테스트한다**(§7, gap 6).

### 4.5 correction/invalidation fan-out + economic-effect 지속 (CII-INV-008/009)

- **CII-INV-008**(line 178–180): material correction/retraction/continuity/policy/mapping
  변경은 영향받는 미소비 downstream permission을 future new-risk send 전에 무효화. 모델은
  `invalidation_generation`·`invalidation_conditions[]`(capsule validity line 64–65;
  snapshot line 42–43)과 dependency-closure 술어로 표현. correction은 **파괴적 덮어쓰기가
  아니라 superseded 레코드에 연결된 새 immutable 관측**(§17 line 415; observation
  `correction_links`, §2.2).
- **CII-INV-009**(line 182–184): snapshot/capsule/policy expiry·invalidation은 order·fill·
  exposure·UNKNOWN·capacity를 **만료시키지 않는다**. 모델 불변식: invalidation은 context
  아티팩트의 validity만 바꾸고, 어떤 economic-effect 상태도 삭제하지 않는다(상태 모델에서
  economic-effect는 context lifecycle과 **직교**). (CII-EV-008, VER §225.)

---

### 4.6 "Approval Set" 명명과 Phase-1 바인딩 타깃 (gap 9)

ADR-002-018 §13(line 342) "Approval Set"은 ADR-002-023이 Independent Approval Decision +
Approval Consumption Record로 실현하며, 별도 `HUMAN-APPROVAL-SET-template.yaml`이
capsule/context 바인딩 필드를 보유한다.

- **Phase-1 바인딩 타깃 = HUMAN-APPROVAL-SET**: 이 아티팩트가 capsule/context 바인딩을
  담는다 — `decision_context_capsule_id`(line 7), `decision_context_capsule_digest`(line 8),
  `context_generation`(line 9), `context_invalidation_generation`(line 10), 그리고
  `validation.{exact_context_current, source_continuity_current, common_mode_analysis_current,
  exact_candidate_command_current, replay_checked}`(line 47–56).
- **capsule → approval set 필드 매핑**(본 계약이 확정하는 것): capsule
  `{capsule_id, canonical_digest}` → `{decision_context_capsule_id,
  decision_context_capsule_digest}`; capsule `context_generation`(Layer-1) →
  `context_generation`; capsule `validity.invalidation_generation`(Layer-1) →
  `context_invalidation_generation`. 즉 capsule은 이 4개 좌변 필드를 바인딩 표면(§4.2 Net
  목록)으로 노출해야 하며, 이미 §2.7 Layer-1에 모두 포함된다.
- **경계**: 본 계약(#2)은 Approval Set / Independent Approval Decision **자체를 모델링하지
  않는다**(ADR-002-023 소관, 후속 문서). #2는 capsule이 그 바인딩을 위해 **노출하는
  필드**(위 매핑의 좌변)만 확정하고, HUMAN-APPROVAL-SET을 Phase-1 바인딩 *소비자* 타깃으로
  명시한다. approval set은 §4.3 Phase B의 downstream 아티팩트로서 확정된 capsule digest를
  권위 있게 바인딩한다(single-use consumption, template line 58–65는 ADR-002-023 소관).

---

## 5. 보수적 모호성 모델

### 5.1 Snapshot validity 집계 (§11, CII-INV-005)

`snapshot.validity.result`는 **평균·다수결·필드 무시로 산출 불가**(§11 line 311). 보수적
집계:

```
result = VALID  ⟺  (모든 blocking field_evaluation.state == VALID)
                  ∧ cut_compatible(snapshot)          # §2.5 파생 술어(비저장)
                  ∧ (요구된 corroboration_paths 충족)
                  ∧ (미해소 common_mode 없음)
그 외        ⟹  §2.1 격자의 worst state (INVALID≻CONFLICTED≻STALE≻UNKNOWN)
```

- property: 개별 필드가 전부 VALID여도 `cut_compatible=false`이면 `result != VALID`
  ("individually fresh ≠ valid snapshot", §11 line 309; CII-INV-007). (CII-EV-005, VER §222.)
- property: last-known-good·majority·cache·health·TTL·heartbeat 중 어느 것도 UNKNOWN을
  permission으로 바꾸지 못한다(§1 line 27; §14 line 367).

### 5.2 field-state 해소 + common-mode 붕괴 (CII-INV-004)

- **common-mode 붕괴**(§13 line 344; §10 line 290): 두 corroboration path가 같은 effective
  control/origin/parser/mapping/library/cache/administrator/failure-domain을 공유하면
  독립으로 계수되지 **않는다**. 모델: `corroboration_paths[]`와 `common_mode_dependencies[]`
  를 교차 분석해, 공유 태그가 있으면 독립도를 붕괴시키는 순수 술어. 미확정 common-mode
  scope는 shared로 취급(§22 line 522). (CII-EV-006 L1-modelable 부분; +Security는 L2+, §7.)
- **CII-INV-012 (UNKNOWN 보수 소비)**(line 194–196): 불확실 입력이 기존/잠재 economic
  effect를 숨길 수 있으면 그 worst-credible effect는 capacity-consuming으로 남고, 불확실성이
  headroom·new-risk permission을 만들지 못한다. 모델: `field_evaluation.worst_credible_bound`
  가 이 술어의 입력. (단 capacity *상태*는 RCL 소관 — 모델은 "unknown ⟹ worst-credible
  consuming" 술어만 노출.)

### 5.3 non-atomic 관측 (CII-INV-007)

incompatible cut의 필드는 하나의 coherent 상태로 결합 불가(§11 line 309). §2.5의
`cut_compatible`와 §5.1 집계가 이를 강제. equality between reads·absence from one query는
completeness 증명이 아니다(§11 line 309).

---

## 6. 외부값 캡처 통합 (ADR-DEV-003) — 프로젝트 측 예시 포함

### 6.1 captured, not called (EXV-INV-001) — firewall 구조적 강제

ADR-DEV-003 EXV-INV-001(line 130–132) + §7(168–177): 외부/LLM 파생 값은 평가 **전에·밖에서**
생산되어 **Decision Context Capsule에 Critical Input으로 전달**되며, DSL 평가는 live fetch를
하지 않는다(ADR-DEV-001 DCE-INV-003). 본 계약은 이를 **firewall로 구조적으로 강제**한다:
tos는 `shared.llm`(및 네트워크 stdlib)을 import할 수 없으므로(§0.3, 설계 #1 §2.3/§4), capsule
모델 안에서 live fetch가 **표현 불가**하다. **v2에서 이 논증은 더 강해진다**: §0.3 C1 수정으로
`shared.config` 경유 ambient 접근(`os.environ`, 자격증명)도 closure에서 원천 차단되므로, 어떤
ambient·live 소스도 순수 모델 closure에 존재하지 않는다(§7.1이 이를 능동 검증). 값은 오직
캡처된 Observation(§2.2, external-source provider)으로만 진입한다.

### 6.2 Validity Window = as-of 앵커 (EXV-INV-002) — gap 8 해소

ADR-DEV-003 EXV-INV-002(line 133–146) + §8(186–200) + §15(347–360, 해소된 Major EV-L0
finding):

- 각 캡처 외부값은 **Validity Window**를 가지며, 이는 ADR-002-018 currentness/max-age
  (CII-INV-006)의 external-value-scoped alias다(§15 line 356).
- **Window는 값의 recorded as-of/production time에 앵커**하며(§8 line 188), **capsule wrap
  time이 아니다**. **re-wrapping(새 capsule에 재전달)은 currentness를 리셋하지 않는다**
  (§8 line 189–193; EXV-INV-002 line 137). 이는 "old authoring-time value re-wrapped ...
  could read fresh forever"를 막는 §12.6 데모의 근거.
- **소유권 분리(gap 8)**: 외부값의 as-of/production 기록은 **ADR-DEV-003 capture provenance
  소관이며 ADR-DEV-004 minimum record의 필드가 아니다**(ADR-DEV-003 EXV-INV-002 line 136;
  ADR-DEV-004는 이를 §4 out-of-scope로 둠). 따라서 capsule Observation의 `time.
  source_event_time`(as-of, §2.2)이 Validity Window 앵커의 원천이고, capsule의 wrap 시각
  (`validity.issued_at`)은 앵커가 **아니다**.
- window 부재 ⟹ `UNKNOWN` ⟹ new risk 차단(§8 line 197; fail-closed). window는 소스 실제
  freshness에 **adequate**해야 한다(§8 line 199, v0.2 adequacy 요건).

**모델·property**:
- Observation은 `time.source_event_time`(as-of)과 별도로 capsule `validity.issued_at`(wrap)을
  갖는다. Validity Window staleness 판정은 `now - source_event_time > window`이며 **wrap
  time을 쓰지 않는다**.
- property (re-wrap 불변): 같은 Observation을 두 capsule `c1`(wrap t1), `c2`(wrap t2>t1)에
  넣어도, 두 capsule에서 그 값의 staleness는 **동일 as-of 기준**으로 판정된다 —
  `stale(c1.obs) == stale(c2.obs)` (as-of 고정). (EXV-INV-002 §12.6의 property화.)

### 6.3 correction invalidates (EXV-INV-004) / evidence-not-authority (EXV-INV-005)

- 소스의 material correction/continuity 변경은 캡처값 + 의존 Snapshot/Capsule/proposal을
  new-risk send 전에 무효화(EXV-INV-004 line 151–154; ADR-002-018 CII-INV-008). §4.5와 동일
  메커니즘.
- 캡처값+provenance+seed+response는 Recorded Input Set의 재현 evidence이지 **authority가
  아니다**(EXV-INV-005 line 155–158). §4.4 authority 부재와 정합.

### 6.4 KIS LLM 시장분석 경로 (프로젝트 측 첫 실사용 예시 — 규범 아님)

> **broker-agnostic 고지**: 아래는 kis_unified_sts 프로젝트 측 예시일 뿐이며, tos-spec의
> 규범 주장이 아니다(project memory `tos-spec-broker-agnostic`). KIS 사실은 이 절에만 존재.

- 현행 `shared/llm`의 `UnifiedMarketAnalyzer`가 산출하는 야간/장전/장마감 브리핑
  값(시장 컨텍스트 점수 등)은, TOS-hosted 미래(설계 #1 §1.2 콘텐츠 이주)에서 **결정 전에
  캡처**되어 capsule에 Critical Input Observation으로 진입한다. Validity Window는 그 LLM
  응답의 as-of/production 시각에 앵커한다(§6.2).
- **중요한 역할 제약(RFC-003 §10, line 365–382)**: LLM 파생 값은 replay는 되지만
  **독립 recompute가 불가**하므로(seed+response로 감사는 되나 first-principles 재도출
  불가), 그것이 direction/quantity/exposure를 **결정하는** Critical Input이면 non-approvable
  (restrictive/fail-closed)이고, **soft evidence로만**(결정 입력이 스스로 독립
  recompute되는 결정을 corroborate) 사용 가능하다. 값을 relabel해도 분류는 안 바뀐다(§8;
  §11 item 10).
- **모델 경계**: soft-evidence vs determining의 *분류·강제*는 **decision/approval
  레이어(RFC-003 §10) 소관**이지 capsule 모델의 구조 필드가 아니다. capsule 모델은 그
  판단에 필요한 evidence를 **표현할 수 있어야** 한다 — 즉 값의 field_state·lineage
  reproducible 플래그(§2.3)·`independent_validation.required_facts`를 통해 "이 값이 독립
  recompute 가능한가"를 downstream이 판정하도록 노출한다. capsule은 soft-evidence 지위를
  부여하지도 부정하지도 않고, 그 판정의 근거만 담는다.

---

## 7. property-test 하네스 타깃

**EV-level 재확인**(VER-002-001 line 142–152; Part XVIII §218–229 line 1889–1971). 각 항목의
**Minimum Level의 선두 레벨**이 EV-L1이면 모델 도달 가능, EV-L2면 Phase 1에서 predicate-only:

| CII-EV | VER Min Level | Phase 1 하네스 | 근거 |
|---|---|---|---|
| -001 Classification Completeness | EV-L1/L3 | **EV-L1 property** | dependency-closure 분류 순수 술어 |
| -002 Source Continuity/Replay Fencing | **EV-L2/L3+Sec** | **predicate-only** (gap 6) | transport-healthy 상태의 reset/gap/rollback/replay는 fault injection ⟹ L2+ |
| -003 Identity/Unit/Scale/Mapping | EV-L1/L3 | **EV-L1 property** | mismatch reject 순수 property (§2.2 admission) |
| -004 Lineage/Hidden-Default | EV-L1/L3 | **EV-L1 property** | reproducible=false ⟹ INVALID (§2.3) |
| -005 Freshness/Conflict Conservatism | EV-L1/L3 | **EV-L1 property** (주입 time bound) | §5.1 집계; bound는 §8 주입 |
| -006 Independent Approval/Common-Mode | EV-L1/L3+Sec | **partial** | 붕괴 로직 L1(§5.2); 실패경로 독립성 L2+ |
| -007 Capsule Binding/Substitution | EV-L1/L3+Sec | **EV-L1 property (core)** | mutate/union/partial-refresh/digest-substitute ⟹ reject (§4.1) |
| -008 Correction/Invalidation Fan-Out | EV-L1/L3 | **EV-L1 property** | closure 무효화 + economic 지속 (§4.5) |
| -009 Final-Egress Currentness | **EV-L2/L3+Sec** | **predicate-only** (gap 6) | race/partition/suppress at irreversible boundary ⟹ L2+; egress 비전송(§0.2) |
| -010 Degradation/Protective Confinement | EV-L1/L3+Broker | **partial** | deny-new-risk 술어 L1; +Broker 이연 |
| -011 Authority Separation/Override Denial | **EV-L2/L3+Sec** | **predicate-only** (gap 6) | "경로 없음" 전수증명 L2+; L1은 `authority.*:false` 불변식만(§4.4) |
| -012 Restart/Restore/Non-Revival | EV-L1/L3+Sec | **EV-L1 property (core)** | new-continuity-required/no-revival 상태 술어; +Sec L2+ |

**EV-L1 property-test 타깃(core)**: `-001, -003, -004, -005, -007(core), -008,
-012(core)`. **partial 모델 커버리지**: `-006, -010`. **predicate-only(EV-L1-complete
주장 금지, gap 6)**: `-002, -009, -011`.

> **Phase 1 완결 주장 규율**: Phase 1은 *모델 + property test 저작*까지다. EV-L1
> 항목조차 **evidence acceptance가 아니다** — VER register의 Owner/Reviewer는 TBD이고,
> 수용은 Independent-Safety-Reviewer(저자 아님, IMPLEMENTATION-PLAN §3 line 153/157)의
> 별도 서명 게이트다. 어떤 항목도 "EV-L1-complete"로 주장하지 않는다.

**run manifest 정렬(설계 #1 §5.1 7항목)**: evidence를 산출하는 모든 property-test run은 —
(1) git commit digest + `tos` 버전, (2) 인터프리터 + 고정 의존성 버전(pydantic/hypothesis
등), (3) 실행 환경 식별자, (4) 하네스 git digest, (5) **property-test seed**(hypothesis
seed/derandomize 정책, append-only), (6) 소비 설정 아티팩트 digest(정책·bound 프로파일 +
`canonicalization_version`), (7) 산출 아티팩트 sha256 — 을 기록한다. seed와 의존성 버전이
있어야 "같은 커밋"이 재현성으로 성립한다(설계 #1 §5.1).

### 7.1 import-closure 검증 테스트 (C1 강제 수단 — v2 신설)

C1(v1 REJECT의 CRITICAL)은 정확히 이 테스트의 부재로 firewall 강제 사각을 빠져나갔다. 설계
#1 §3.4의 determinism closure 검증 테스트와 **동형**으로, 다음을 §7 하네스의 필수 타깃에
포함한다:

- **서브프로세스**에서 순수 모델 패키지(`import tos.capsule` 등)만 import한 뒤 `sys.modules`를
  검사하여 다음을 assert:
  1. §2.3(설계 #1) 금지 패키지(`shared.execution`·`shared.kis`·`shared.streaming`·
     `shared.llm`·`shared.storage`·`shared.backtest`·`services.*`·`cli.*`)가 closure에
     **없다**.
  2. **`shared.config` 및 `shared.config.secrets`가 closure에 없다**(C1 직격 — top-level
     import만 보는 AST 게이트가 놓치는 전이 유입을 런타임 closure로 포착).
  3. `os`가 로드되더라도 모델 코드가 `os.environ`/`os.getenv`를 참조하지 않는다(AST 스캔
     보강; ambient 자격증명 리더 부재).
- 이 테스트는 서브프로세스 격리로 실행해 부모 인터프리터의 기존 import 오염을 배제하며, run
  manifest(§7)에 기록된다. **required check**(설계 #1 §3.3-③ `tos-firewall`)와 함께 이
  테스트가 green이어야 §0.3 firewall 준수 선언이 능동적으로 성립한다.

---

## 8. bounds 주입 파라미터 + 누락 프로파일 키 (gap 5)

`VERIFICATION-PROFILE-002.yaml`은 `status: PROPOSED`, `approved_by: []`,
`effective_from: null`이고 모든 ADR-002-018 bound가 `value_ms: null`이다(dossier §5;
banner: "unapproved or placeholder bound is not an approved bound"). ADR-002-018 §4(line
104)는 "numeric freshness ... bounds belong in approved policies and the Verification
Profile"로 못박는다.

- **결정**: 모든 임계값(`B_critical_input_loss_detect`,
  `B_critical_input_invalid_to_authority`, `B_critical_input_invalid_to_egress`,
  `MAX_critical_input_snapshot_age_ms`, `MAX_decision_context_age_ms`, 소스별 freshness)은
  **주입 policy 파라미터**로만 모델에 들어온다. 어떤 숫자도 하드코딩하지 않는다(CLAUDE.md
  설정 기반; 파일 ratification 규칙). field_evaluation은 `bound_ref`로 정책 파라미터를
  가리킬 뿐이다(§2.4).
- **property의 bound 처리**: property test는 bound를 **hypothesis가 생성하는 주입값**으로
  다뤄, "임의의 유효 bound 하에서 술어가 보수적으로 성립"함을 검증한다(특정 값에 의존하지
  않음).

**Phase-0 게이트 플래그 (누락 프로파일 키 — v2 실측 재확인, under-report 정정)**: ADR §14는
freshness delay를 **8종**으로 분리 정의한다(line 356 source production delay; 357 transport
and queue delay; 358 consumer receipt age; 359 transformation and Snapshot age; 360 Capsule
age; 361 session and venue-state age; 362 correction and late-revision horizon; 363
source-loss detection and invalidation propagation). `VERIFICATION-PROFILE-002.yaml`을 직접
grep한 결과:

- **distinct key 존재 (4/8)**: #359 → `MAX_critical_input_snapshot_age_ms`(line 709;
  transformation age는 이에 접힘); #360 → `MAX_decision_context_age_ms`(710); #361 →
  `MAX_venue_constraint_snapshot_age_ms`(711); #363 → `B_critical_input_loss_detect`(219) +
  `B_critical_input_invalid_to_authority`(226) + `B_critical_input_invalid_to_egress`(233).
- **distinct key 부재 (4/8) — Phase-0 보강 대상**: (a) **source production delay**(§14 line
  356); (b) **transport-and-queue delay**(§14 line 357 — transport uncertainty는 line 352에도
  언급되나, profile상 `MAX_time_health_snapshot_age_ms`(line 698) 주석에 "including transport
  uncertainty"로 **접힘**만 될 뿐 critical-input 전용 distinct key는 없다); (c) **consumer
  receipt age**(§14 line 358); (d) **correction/late-revision horizon**(§14 line 362 — OQ12
  line 652에만 언급). (모든 ADR-002-018 critical-input bound의 `value_ms`는 `null`/PROPOSED.)

본 계약은 이 **4개 누락 distinct key**를 Phase-0 인간 게이트의 프로파일 보강 항목으로
플래그한다(v1은 2개만 플래그 — under-report였음) — 모델은 8종 delay 각각을 주입 슬롯으로
**선언**하되(주입값 누락 시 `UNKNOWN` fail-closed), 값·키 승인은 Bounds-Approver 게이트로
넘긴다(§9.2 item 3).

---

## 9. 후속 설계 문서 의존 + Phase-0 인간 게이트 이관 항목

### 9.1 후속 설계 문서 (설계 #1 §6.3 정렬)

- **설계 #3 (EV-L1 순수 모델 계층 + property-test 하네스)**: 본 계약의 §2 모델과 §7 타깃을
  **실행**한다. 본 계약이 정의한 canonicalizer property suite(§3.4)·field-state 집계(§5)·
  frozen digest 불변식(§4.1)이 하네스의 검증 대상. `shared.determinism`(이미 추출됨) 의존.
- **설계 #4 (Evidence Store + append-only ledger, ADR-002-016)**: §4.3 Phase B의 downstream
  체인 재구성과 §4.5 correction lineage의 custody. capsule/snapshot canonical bytes·digest
  vector(REPLAY-CAPSULE line 41–45 선례)의 보존 계약.
- **의존 방향**: #3 ⟸ #2(본 문서) ⟸ 설계 #1. #4 ⟸ #2. DSL(RFC-008)은 EV-L1 크리티컬
  패스가 아님(설계 #1 §6.3 병렬).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

1. digest 알고리즘·canonical serialization의 **프로덕션 선택**(OQ1; §3.1). — §3.4 잠정
   canonicalizer는 프로덕션 승인을 대체하지 않는다.
2. §3.2 digest 자기제외 집합의 **비준**(프로젝트 측 신규 결정이므로 독립 리뷰 필요) — 특히
   `status`가 digest와 서명 preimage 양쪽에서 제외되면 서명이 lifecycle 상태를 bind하지
   않으므로, **status attestation 경로는 서명/evidence 레이어(ADR-002-016) 설계로 이관**
   된다(Phase-1 순수 모델 밖의 잔여 리스크).
3. VERIFICATION-PROFILE-002 **bounds 승인** + **correction-horizon/transport-uncertainty
   키 신설**(§8; Bounds-Approver, Live-Armer와 분리).
4. **수치 canonical form(프로덕션 규칙)의 정책화** — §3.4 (B) property 6은
   `ev-l1-provisional-0`에 bound된 **잠정 fixture 전용**이며 이 프로덕션 선택을 **선점하지
   않는다**(scale/unit/multiplier/sign은 별개 covered 필드로 보존, §3.4).
5. Independent-Safety-Reviewer 지정 및 §7 EV-L1 evidence 수용 서명(저자 배제).
6. **id↔digest 바인딩 정책** — Phase 1은 `id=f(digest)` 파생을 채택(§4.1). 외부-할당 id
   정책을 택할 경우 그 정책의 비준 + substitution-resistance(CII-EV-007)와의 긴장 검토.

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- 2026-07-20: **v1 초안 최초 작성**. ADR-002-018 EV-L1 실현 계약. 9개 결정 의제(gap 1–9)
  전부 결정 또는 Phase-0 이관 명시. 설계 #1(경계·firewall) 및 canonical 템플릿 5종에 정렬.
- 2026-07-20: **v2 — 독립 비평 리뷰 REJECT 반영.**
  - **C1(CRITICAL)**: `shared.config`를 firewall closure에서 제거(§0.3) — `__init__`이
    `shared.config.secrets`를 무조건 import하여 `os.environ` ambient 접근을 전이 유입하고
    설계 #1 게이트가 이를 못 잡음을 코드로 실증. 정책/템플릿 로딩은 `pyyaml`만 사용. §2.2·§6.1
    정합 문구 수정, §6.1 논증 강화. **§7.1 import-closure 검증 테스트 신설**로 능동 강제.
  - **M1(MAJOR)**: §3.4 수치 property를 (A) must-pass 불변식과 (B) 잠정 fixture 전용으로
    분리; magnitude 정규화가 scale/unit/multiplier/sign 구별을 접지 않음을 명시; §9.2 item 4
    이관과의 봉합점 명시(자기모순 해소).
  - **m1**: 배너 schema_version 실측 정정(capsule/snapshot=1.0-DRAFT, HUMAN-APPROVAL-SET=
    schema_version TBD, REPLAY-CAPSULE=version TBD).
  - **m2**: §8 transport-uncertainty 인용 정정(ADR §14 line 352/357; correction-horizon만 362).
  - **m3**: §2.5 `cut_compatible`를 저장 필드가 아닌 파생 술어로 명시(snapshot canonical
    bytes 템플릿 SoT 정렬 유지); §2.6 1:1 확인 보강.
  - **m4**: §1 표에 CII-INV-013(non-revival 상태 술어) 명시·CII-INV-014 추가; §0.2에
    CII-INV-014 out-of-scope 명시 배제.
  - **missing/ambiguity**: §8 8종 delay 실측 열거(누락 distinct key 4개로 정정, under-report
    해소); §4.1 id↔digest 파생·검증 강제(+§9.2 item 6); §2.7 venue_constraint_policy Layer-2
    근거; §4.2 snapshot-재도출-독립성 비위반 논거; §9.2 item 2 status attestation 서명 레이어
    이관.
- 2026-07-20: **v2 운영자 비준.** 독립 비평 리뷰(v1 REJECT → v2 전 항목 반영, C1 firewall
  전이 import는 코드 실증 후 해소) 통과. 신규 판단 요소 3건(id=f(digest) 파생, §7.1 런타임/정적
  분담, §8 delay 매핑 해석성)을 운영자에게 명시 고지하고 비준. `id=f(digest)`는 §4.1대로 확정,
  외부-할당 대안은 §9.2 item 6 Phase-0 옵션. 효력: Phase 1(EV-L1) `tos/src/tos/capsule/`
  모델+property test 작성 착수.

### 10.2 비준 체크리스트 (운영자·독립 리뷰어 확인 사항)

- [ ] §0.2 NO 목록(런타임 서비스·authority·egress·venue/adm 모델·프로덕션 canon·bounds
      미승인)과 §0.3 firewall 준수 선언에 동의.
- [ ] §1 조항별 EV-L1 도달성 매핑에 동의(특히 -002/-009/-011의 L2+ 이연).
- [ ] §2 per-element 스키마(Observation·Lineage·Field Eval·Cut) 저작이 ADR §9/§10/§11
      prose에 충실함을 확인(gap 1).
- [ ] §3.2 digest 자기제외 집합(**프로젝트 측 신규 결정**)과 §3.3 커버리지, §3.4 잠정
      canonicalizer(非프로덕션)에 동의(gap 2, 3).
- [ ] §4.2 recompute 표면 조화(gap 7)와 §4.3 레이어드 발행 순환 해소(gap 4)에 동의.
- [ ] §5 보수적 집계·"individually fresh ≠ valid"·common-mode 붕괴에 동의(gap 6 중 -005/-006).
- [ ] §6 as-of 앵커·re-wrap 불변(gap 8)과 KIS 예시의 broker-agnostic 격리에 동의.
- [ ] §7 하네스 타깃 구분과 "EV-L1-complete 주장 금지" 규율, **§7.1 import-closure 검증
      테스트(C1 강제)** 신설에 동의(gap 6).
- [ ] **§0.3 C1 수정**(`shared.config` firewall closure 제거, 로딩은 `pyyaml`만)에 동의.
- [ ] §8 8종 delay 실측 열거(누락 distinct key **4개**)와 §4.6 gap 9 바인딩 매핑에 동의(gap 5).
- [ ] **§3.4 M1 봉합**((A) must-pass vs (B) 잠정 fixture 분리; scale/unit/multiplier 보존)에 동의.
- [ ] §9.2 Phase-0 이관 **6항목**(id↔digest 정책 포함)을 별도 게이트로 유지함에 동의.

비준 시 효력: IMPLEMENTATION-PLAN-002 §4 Phase 1의 ADR-002-018 부분을
`tos/src/tos/capsule/`에 순수 모델 + property test로 작성 착수 승인. §9.2 Phase-0 6항목과
bounds 승인·독립 리뷰어 지정은 별도 게이트로 남는다.
