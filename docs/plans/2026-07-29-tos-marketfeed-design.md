# 설계 문서 #32 — tos.marketfeed: 시장 데이터 → Critical Input 값 표면 (D-E2, 수직 슬라이스 #1 데이터 공급 레이어, provisional·닫는 EV 0건) (2026-07-29, v1.2)

> **⚖ 비준 기록**: **2026-07-29 운영자 위임 자동 비준(v1.1)** — 2026-07-29 운영자 지시(Part-2/3 설계 비준
> 위임 연장)에 따라, 오케스트레이터가 게이트 조건을 검증하고 기록함: 독립 비평 리뷰 REVISE(CRITICAL 0·
> MAJOR 2) → v1.1 전건 처방 반영(F1 값-carrier shape→tos.dsl `ContextValueView`·재현성 서명 digest append·
> 신뢰 seam 정직 명기) → **리뷰어 델타 재검증 ACCEPT-WITH-MINOR 승급**(MAJOR 2 봉합 코드 실측·새 결함 0·
> sanction 전제 (a)(b)(c) 전부 충족 판정) → 오케스트레이터 최종 실측(engine→dsl 기존 edge records.py:28-33
> 직접 확인). **dsl/engine additive 터치 sanction 성립**(§15 미결-1 터치 전모 공개 조건 충족 — 순환 0·
> allowlist 무변경·committed 테스트 파괴 0). 델타 리뷰의 비차단 MINOR 3건(deterministic-float 규칙 확정 전
> fail-closed 유지·disjointness 발행-시점 실검사·carrier field_state defense-in-depth 재량)은 구현·적대적
> 코드 리뷰 단계 지침으로 이월. 품질 파이프라인 잔여 단계 유지. ADR acceptance·live authorization과 무관.
> 효력: Phase 1 `tos/src/tos/marketfeed/` + 승인된 dsl/engine additive 확장 구현 착수(단, 구현 순서는
> D-E3 구현 완결 후 — committed 파일 경합 회피, 오케스트레이터 일정 소관).

> **⚖ 문서 지위**: kis_unified_sts 프로젝트 측 설계 계약 **v1.1 개정본**(독립 비평 리뷰 REVISE 반영). **아직
> 비준 전이다** — 후속: 리뷰어 델타 재검증(타입 소유권 재배정 규모라 예정됨·§16) → 운영자 위임 자동 비준(2026-07-29
> 연장 지시) → 구현 → 적대적 코드 리뷰. tos-spec에 대해 **non-normative**이며 스펙 텍스트(RFC/ADR/템플릿/
> 프로파일/register)를 **변경하지 않는다.** 본 문서는 RFC-004 §9(Market Data as Critical Input)·RFC-008
> §9/§10(DSL 소비)·ADR-002-018 §9/§10/§11/§14(Critical Input 무결성·provenance)를 그린필드 `tos/src/tos/
> marketfeed/` 신규 패키지의 **값 표면 계약**으로 실현하며, 비준·구현 완료된 `tos.capsule` 계약을 **변경하지
> 않는다**(§0.2·§15).
>
> **v1.1 개정 요지(2026-07-29 독립 비평 리뷰 REVISE 반영·CRITICAL 0·MAJOR 2·MINOR 4·Gap 1·NIT 1·인용
> 52/52 정확·phantom 0·capsule 무변경 실측 성립·접근법 지지)**: **(MAJOR-1·타입 소유권 재배정)** 값-carrier
> **형(shape)을 `tos.dsl`로 이동**(`ContextValueView`/`ContextValue`) — `DecisionTickPayload.value_view`가
> marketfeed 타입이면 `tos.engine.records`가 marketfeed를 런타임 import해야 해 committed engine import-closure
> allowlist(14패키지·`tos/tests/engine/test_engine_import_closure.py:59-76` marketfeed 부재) subset 테스트를
> 깨고 `engine→marketfeed→engine` 순환을 낳음. **처방 F1**: shape=dsl 소유(engine→dsl·dsl→capsule 기존 edge)·
> **생산/검증 로직=marketfeed 소유**(marketfeed→dsl 기존 방향의 생산자). engine→marketfeed·dsl→marketfeed edge
> 둘 다 불요·순환 0·engine allowlist 무변경(§3.2·§3.4·§12·§15 터치 전모). **(MAJOR-2·재현성 서명 충분성)**
> resolved_context는 4번째 결정입력인데 `_captured_value_refs`는 snapshot digest만 담아(determinism.py:118-119)
> 부정직 resolver가 같은 서명·다른 outcome 생성 가능 → resolved-value 진입점(v1.2 에라타 `evaluate_resolved`·§16.1)이 resolved_context 제공 시 **value-view의
> canonical digest를 `captured_external_value_refs`(determinism.py:78·이미 tuple)에 append**하도록 계약·값⟺digest는
> **발행 시점 검증·env-주입 지점 미재검증 신뢰 seam**을 D-E1 부분봉인 동형으로 정직 명기(§2.3·§3.2·§4.3·§11·Gap-1).
> MINOR 1-4·NIT-1 전건 반영(§16 개정 로그). **핵심 접근법(값을 covered snapshot으로 옮겨 side-channel·
> distinctness 동시 봉인)·capsule 무변경은 리뷰 지지로 유지.**
>
> **v1.2 에라타 요지(2026-07-29 구현 단계 발견·오케스트레이터 경로 (a) 재정 — 비준 아래 계약 정정·비준 기록 무변경)**:
> v1.1 §3.2가 명세한 "`evaluate`에 6번째 keyword-only 파라미터 `resolved_context` 추가" 시그니처 확장이 **committed
> canary와 충돌**한다 — `tos/tests/dsl/test_dsl_determinism.py:136-146`의 `test_evaluate_signature_exposes_no_ambient_source`가
> `inspect.signature(evaluate).parameters`를 정확히 5개({strategy, capsule, config, scheme, enforcement_mechanism_version})로
> 잠근다(keyword-only 6번째도 이 canary를 깬다). **오케스트레이터 재정: 경로 (a)** — 구현이 더 충실하므로 canary를
> 무력화(경로 b·neutered-canary 결함)하지 않고 **설계를 구현에 맞춰 정정**(WDR #26 MAJOR-2 선례). 구현 착지: 실체는
> **신규 public 진입점 `evaluate_resolved(…, resolved_context=None)`(determinism.py:362)**로 실현되고, 기존
> `evaluate`(determinism.py:319)는 **5-파라미터·byte-identical 유지**(canary intact); 공유 본체 `_evaluate`(determinism.py:277)가
> env merge(:292)·서명 append(:297-303)를 수행. `build_environment(…, resolved_context)`(determinism.py:93·env merge)·
> `evaluate_policy` 무변경·capsule 무변경·F1·서명 append·값⟺digest 신뢰 seam은 **전부 v1.1 설계대로**. **신규 교훈(§15.2③)**:
> sanction 전제 "committed 테스트 파괴 0"은 터치 표면의 **모든** committed canary(시그니처·closure·drift anchor)를 전수
> grep해야 성립 — v1.1은 engine closure allowlist만 실측하고 **dsl 시그니처 canary를 놓쳤다**(저작·리뷰·델타 재검증 모두).
>
> **선행 문서(의존)**:
> - [설계 #31 — tos.engine 단일 이벤트 코어 (D-E1, v1.1, 운영자 위임 자동 비준 2026-07-29)](2026-07-29-tos-engine-event-core-design.md).
>   특히 §3.2 env-seam 계약(시장값=admitted Critical Input observation→Snapshot body→`"capsule"` 소스 전용·
>   `config.bindings`=저작자-상수 전용)·§12 D-E2 핸드오프(§12-1 `DecisionContextResolver`)를 본 설계가 **소비·
>   실현**한다. **committed 엔진 코드**(`tos/src/tos/engine/`)의 seam slot을 본 문서가 채운다.
> - [설계 #2 — Decision Context Capsule + Snapshot 계약 (v2, 운영자 비준)](2026-07-20-tos-decision-context-capsule-snapshot-design.md).
>   capsule/observation/snapshot/lineage/field_evaluation 모델은 **비준·구현 완료**다 — 본 문서는 그 위에 값-싣는
>   표면을 **greenfield 확장**(신규 패키지 + dsl shape 소유)으로 얹고, capsule 모델을 수정하지 않는다.
> - [tos.dsl 실전략 de-risking 스파이크 (비규범)](2026-07-29-tos-dsl-spike-findings.md) — 본 문서가 소유하는
>   갭(G6·G8·G9·G10·G13·G1/G3)의 실측 원천.
> - [설계 #1 — tos/ 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md) §2.4 레이아웃·§3.2 허용목록.
> - [Phase-0 인간 게이트 register (비규범)](2026-07-29-tos-phase0-human-gate-register.md)·[Broker Capability Profile KIS 초안 (비규범)](2026-07-29-tos-broker-capability-profile-kis-draft.md) — provisional 제약·KIS 사실 참조 전용(§8).
>
> **⚠ provisional·닫는 EV 0건 (본 문서 최상위 정직 선언 — §1.1, D-E1 §1.1 동형)**: 본 슬라이스 산출은
> **엔지니어링-통합 provisional**이며 **어떤 EV-L2+ PASS도 주장하지 않는다.** 이유 3중: (a) G2 프로덕션
> canonicalization 미결 — 값↔digest 바인딩(§2.3 payload_digest 검증)·value-view digest(§3.2)가 전부
> `ev-l1-provisional-0` 위에서 돈다(register §6:132; canonical/__init__:35-39). (b) P0-1 bounds 승인·P0-3 독립
> 리뷰어 미완(register §4:108). (c) 값 표면은 **모델+property 저작**이지 실 Context Integrity Service 런타임
> (관측 수집·조립·발행)이 아니다(설계 #2 §0.2 — 그 런타임은 비-scope). GOV-001 세 거버넌스 행위(비준/ADR
> acceptance/live authorization) 중 어느 것도 수행하지 않는다.
>
> **broker-agnostic**(project memory `tos-spec-broker-agnostic`): 값 표면 어휘는 전부 broker-agnostic이다.
> KIS·KRX 사실은 등장하지 않으며, 시장 값의 provider·feed·instrument는 opaque 주입 provenance 스칼라로만
> 표현한다. KIS 실사용 예시는 비규범 Broker Capability Profile INSTANCE 참조로만(§8·§12).
>
> **규범 원천(전부 2026-07-29 자체 grep 실측·anti-phantom §0.5)**: RFC-004 §6:162-175·§7:200-202·§8:227-229·
> §9:233-260("never by unattributed fetch or side channel" :244·derived lineage :245-247·no relabel :251-252)·
> RFC-008 §7:222-240·§9:284-317(:290-301 captured-before-eval·:302-306 recorded provenance)·§10:327-350·
> ADR-002-018 §9:249-272·§10:276-291·§11:294-311·§14:350-367·§15:373-390. 코드 원천: `tos.dsl`(vocabulary.py:88·
> 93·167-168·316-340·343-376·determinism.py:53-108·118-119·238-284)·`tos.capsule`(observation.py·snapshot.py·
> capsule.py·lineage.py·field_evaluation.py·field_state.py:70-87·predicates.py:182-253)·`tos.engine`(core.py:86-120·
> records.py:28-33·157-170·pipeline.py:311-317·admission.py:114·__init__.py:52-57·`tos/tests/engine/test_engine_
> import_closure.py:59-76·305-327`).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것 (7건)

1. **패키지 명명 `tos.marketfeed`** (negative-grep 충돌 0·§10.1). 순수·비전송 값-**생산/검증** owning 패키지 —
   네트워크 feed 런타임이 아니라 **admitted Critical Input 값이 DSL에 도달하는 계약**(§10.1 명명 주의).
2. **값-싣는 표면 형태 + 소유권 분할**(§2·핵심 결정 A·**v1.1 MAJOR-1**) — env-값 **형(shape)은 `tos.dsl`
   소유**(신규 `ContextValueView`/`ContextValue`·dsl이 env-shape 소유), **생산/검증 로직은 `tos.marketfeed`
   소유**(admitted 관측 → 검증된 `ContextValueView` 생산). 각 값은 **covered `observation.raw.payload_digest`에
   구조 바인딩**되어 side channel이 아닌 admitted Critical Input임을 발행 시점 보증. 기존 capsule 모델 **무변경**.
3. **env-조립 seam 계약**(§3·핵심 결정 B·**본 문서의 하중 콘텐츠**) — 값이 `resolve_operand`가 걷는
   `env["capsule"]` 밑 governed sub-path의 **스칼라 leaf**로 도달하는 유일 채널. `evaluate_policy`(인터프리터)
   **무변경**, `build_environment`(resolved_context 추가)와 **신규 진입점 `evaluate_resolved`**(v1.2 에라타·기존
   `evaluate`는 5-파라미터 유지)가 dsl-타입 소비 **additive 확장**(D-E1 §3.2(A) 위임 "입력 조립")·resolved_context
   제공 시 서명에 value-view digest **append**(재현성 4번째 입력 커버·MAJOR-2), `DecisionTick
   Payload`는 **dsl-타입 optional 필드**(D-E1 이연 records.py:157-163·engine→dsl 기존 edge). **capsule 계약 무변경**(§15).
4. **per-bar identity distinctness**(§4·핵심 결정 C·D-E1 Gap-1 이연분 해소) — 값이 covered snapshot으로 흐르면
   distinct bar → distinct **covered `source_event_time`** → distinct observation → distinct snapshot digest →
   distinct capsule digest → distinct proposal_id가 **구조 corollary**(MINOR-1: 하중=source_event_time·payload_
   digest는 값-provenance). capsule `_REQUIRED_COVERED` **무변경**.
5. **지표 파이프라인의 Critical Input 化**(§5·핵심 결정 D) — 밴드·이동평균 등 파생값은 상류 계산·admit되고
   기구현 `TransformationLineage`(REUSE)로 lineage를 싣는 admitted observation. look-ahead 경계·계산 주체·
   estimator=config 규율 확정. D-E2는 estimator를 **구현하지 않는다**(§5.3).
6. **슬라이스 경계**(§6.5·§12) — 단일 심볼 분봉·백테스트(D-E3)·paper(D-E4)가 **같은 값 표면 계약**을 소비.
   히스토리 데이터 소스 자체·실 feed 전송은 주입 seam(D-E3/D-E4).
7. **firewall 준수 + property-test 타깃**(§7) — `tos.marketfeed`는 pure·non-transmitting·closure 최소·**순환 0**.
   property는 저작(authoring) 증거·닫는 EV 0.

### 0.2 하지 않는 것 (NO 목록·경계)

1. **기존 capsule 모델 변경 금지 — 원칙.** `Observation`·`CriticalInputSnapshot`·`DecisionContextCapsule`·
   `FieldEvaluation`·`TransformationLineage`는 비준·구현 완료 계약(설계 #2). 값 표면은 **greenfield(신규 marketfeed
   패키지 + dsl shape 확장)으로만** 설계한다. **본 설계는 어떤 capsule 모델 필드도 추가/변경/제거하지 않는다**
   (§15 실측 확인). 불가피 판정 시 그 항목은 설계하지 않고 미결 보고(§15) — 에라타는 오케스트레이터 소관.
2. **evaluate_policy 재작성 금지.** `tos.dsl.vocabulary.evaluate_policy`(:384)·`resolve_operand`(:316)는
   출하·작동(스파이크 §1). 값 표면은 그들이 걷는 **env를 채울 뿐** 인터프리터를 바꾸지 않는다(§3.1).
3. **estimator·window·지표 수식 미구현.** 밴드 stddev 배수·period·HAR 창 등은 config·상류 모델 선택
   (RFC-004 §7:200-202·§8:227-229). D-E2는 파생값의 **lineage-싣는 admitted observation 계약**만 정한다(§5.3).
4. **실 Context Integrity Service 런타임 미구현.** 관측 수집·조립·snapshot 발행의 런타임 경로는 비-scope
   (설계 #2 §0.2). D-E2는 그 산출물(admitted snapshot)을 **소비·해소(resolve)**하는 계약과 값 표면만.
5. **실 market feed·네트워크 I/O·라이브 전송 = D-E4/상류.** `tos.marketfeed`는 값을 **열지 않고 주입받는다**
   (§6.5·§7.1). feed 어댑터·brokercap INSTANCE·KIS WebSocket은 본 문서 밖.
6. **히스토리 데이터 소스·fill·cost-realism = D-E3.** 값 표면은 소스-무관(EventSource 동형·§6.5).
7. **닫는 EV/AC 0건.** §1.1 — provisional. acceptance는 §9 후속 게이트 소관.
8. **soft-evidence vs determining 분류·강제 = 결정/승인 레이어(RFC-003 §10).** capsule/값 표면은 그 판정의
   **근거만 노출**(field_state·lineage reproducible·독립성)하지 지위를 부여/부정하지 않는다(설계 #2 §6.4:650-655).

### 0.3 firewall 준수 선언 (설계 #1 §3.2/§3.3·capsule 설계 #2 §0.3에 대한 본 계약의 준수)

**v1.1 소유권 재배정(MAJOR-1)**: env-값 **형은 dsl에** 산다(§2.2·§3.2 F1). 따라서 `tos.marketfeed`는 커널이
아니라 그 dsl 형의 **생산/검증 어댑터**다. marketfeed 소스 import closure:

```
{tos, tos.canonical, tos.ordering, tos.capsule, tos.dsl, tos.time, tos.engine, tos.marketfeed}
```

- **생산 edge**: `tos.dsl`(생산 대상 `ContextValueView` 형 + `ScalarValue` — dsl/__init__:111·§2.2) ·
  `tos.capsule`(Observation/CriticalInputSnapshot/FieldState/TransformationLineage/FieldEvaluation/AdmissionResult
  REUSE — capsule/__init__:49-53) · `tos.canonical`(`EVL1ProvisionalCanonicalizer`/`EV_L1_PROVISIONAL_VERSION`
  digest — canonical/__init__:39·35) · `tos.time`(freshness/as-of — time/__init__:66·71·50·38) · `tos.engine`
  (구체 resolver가 `DecisionTickPayload`/`InstrumentKey`/`TimeAdmissionInputs` 생산 — records.py:157·93·125).
- **핵심 방향성(순환 0)**: marketfeed는 dsl·capsule·engine을 **소비(생산 대상)**하되, **dsl·engine은 marketfeed를
  import하지 않는다**(§3.2 F1·§3.4·§12.2). `engine→marketfeed`·`dsl→marketfeed` edge **부재** ⇒
  `engine→marketfeed→engine`·`dsl→marketfeed→dsl` 순환 원천 차단. committed `tos/tests/engine/
  test_engine_import_closure.py` allowlist 14패키지(:59-76) **무변경**·subset 테스트(:310-315)·declared-edge
  테스트(:318-327) 둘 다 여전히 통과(marketfeed가 engine closure에 안 들어옴·§7.1 negative canary).
- **패키지 분할**(§3.4): `tos.marketfeed.value`(순수 검증 술어·env 투영 헬퍼·`ContextValueView` 생산자 — closure에
  `tos.engine` 없음) / `tos.marketfeed.resolver`(구체 `DecisionContextResolver` — `tos.engine` edge). 순수 층
  오염 방지·§7.1 canary 2단.
- **여전히 금지**(설계 #1 §2.3): `shared.*` 운영·`shared.config`(→ `shared.config.secrets` ambient·설계 #2
  §0.3 C1)·`os.environ`/`getenv`·network stdlib·`importlib`/`exec`/`eval`/`compile`·`numpy`/`pandas`·**`shared.llm`**
  (EXV-INV-001 captured-not-called 구조 강제). marketfeed는 값을 **주입**받되 스스로 fetch하지 않는다 — RFC-004
  §9:242-244 "never by unattributed fetch or side channel"의 구조 강제(§7.1 canary).
- **형제 잠식 금지**(D-E1 §5.4 상속): `tos.egress`(QCC 커널)·`tos.venue`·`tos.ioc` 등 미접촉. marketfeed는
  값 표면만 소유·tradability 미정의(RFC-008 §10:332-335 — consume as evidence·no tradability assertion).

### 0.4 핵심 아키텍처 판정 요지 (4개 핵심 결정 + 경계)

| # | 결정 | 판정 | 근거(요지) | 리스크 |
|---|---|---|---|---|
| **A** | 값-싣는 표면 형태 + 소유권 (§2) | env-값 **형=dsl 소유**(`ContextValueView`/`ContextValue`·§2.2)·**생산/검증=marketfeed 소유**. 값은 covered `payload_digest`에 **발행 시점** 구조 바인딩(값⟺digest·§2.3)·VALID-gate=worst(3상태)==VALID(§2.2). VALID만 노출·그 외 key 부재(→ UNKNOWN restrictive). capsule 모델 **무변경** | Observation은 수치 leaf 0·`raw.payload_digest`만(G6·G8·observation.py:70-74). 값은 covered raw payload 뒤에 산다(ADR §9:256·259). **shape=dsl**은 engine 순환 회피(MAJOR-1·records.py:28-33 engine→dsl 기존 edge) | 값⟺digest 미바인딩 시 side channel(RFC-004 §9:244)·distinctness 붕괴. 바인딩이 두 위반 동시 봉인·검증은 발행 seam(§4.3 정직) |
| **B** | env-조립 seam (§3·**하중**) | 값은 `env["capsule"]` 밑 governed **스칼라 leaf**로만 도달(resolve_operand dict-walk·scalar-leaf 전용·vocabulary.py:334·338). `build_environment`(resolved_context)+**신규 진입점 `evaluate_resolved`** dsl-타입 소비 **additive**(D-E1 §3.2(A)·v1.2 에라타: `evaluate` 5-파라미터 유지)·resolved_context 서명 digest **append**(재현성 4입력·MAJOR-2·determinism.py:297-303)·`evaluate_policy` **무변경**·`DecisionTickPayload` dsl-타입 필드(D-E1 이연) | 시장값=`"capsule"` 소스 전용(D-E1 §3.2·`ADMISSIBLE_CONTEXT_SOURCES`={capsule,config} vocabulary.py:88). 3rd `"market"` 소스 기각(core.py:96) | dsl/engine additive 터치가 **capsule 계약 아님**·순환 0·allowlist 무변경 — 오케스트레이터 sanction 조건=터치 전모 공개(§15 미결-1) |
| **C** | per-bar distinctness (§4) | distinct bar → distinct **covered `source_event_time`**(observation.py:85·covered snapshot.py:131) → distinct snapshot digest → distinct capsule digest → distinct proposal_id **구조 corollary**. 발행 gate가 `source_event_time`(as-of)+`payload_digest` concrete 강제. capsule `_REQUIRED_COVERED` **무변경** | G13 근인=스파이크가 값을 uncovered `config`로 relabel(G10)→capsule_id 불변. 값을 covered 관측으로 옮기면 근본 해소(D-E1 §7.2-5) | 진부 producer가 as-of 누락 시 붕괴 — 발행 gate fail-closed. 완전 봉인 producer 정직 의존(정직 명기·§4.3) |
| **D** | 지표 파이프라인 (§5) | 밴드·MA 등 파생값=상류 계산·admitted observation + 기구현 `TransformationLineage`(REUSE·lineage.py:96-115). look-ahead: 파생 parent as-of ≤ 파생 as-of(RFC-004 §6:162-165). D-E2는 estimator **미구현** | RFC-008 §9:290-301 "captured *outside and before* DSL evaluation and delivered into the Capsule as Critical Input". DSL 산술/bar 이력 부재(G1·G3) | 완전 look-ahead 강제는 D-E3 LookaheadGuard 소관. D-E2는 lineage로 표현·검증 가능케만(정직 명기·§5.4) |

### 0.5 anti-phantom 규율 (FD #27 §0.5·D-E1 §0.5 상속 — 부재 주장·존재 주장 양방향 grep)

- 본 문서의 **모든 file:line 인용은 2026-07-29 자체 grep/read 실측값**이다(v1.1 개정 인용 전부 재grep·§16).
  스펙/코드 개정 시 행 이동 — 재사용 시 재실측.
- **부재 주장 negative-grep 병기**: (1) `tos.marketfeed` 충돌 부재 — `ls -d tos/src/tos/*/ | grep -iE
  'marketfeed|feed|market|value|observation|resolver'` → 매칭 0. (2) `marketfeed`가 tos 어디에도 미예약 —
  `grep -rniE 'tos\.marketfeed|"marketfeed"|marketfeed' tos/src/tos/` → 0. (3) capsule 패키지에 수치 값 carrier
  부재 — `grep -rniE 'observed_value|numeric_value|magnitude|: *float|price' tos/src/tos/capsule/` →
  `price_and_order_constraints: tuple[str,...]`(capsule.py:79 — 문자열)·mapping 메타뿐, **스칼라 값 leaf 0**.
  (4) DSL 3rd 컨텍스트 소스 부재 — `ADMISSIBLE_CONTEXT_SOURCES = frozenset({"capsule","config"})`(vocabulary.py:88)
  — `"market"` 미포함. (5) `resolve_operand` list 인덱싱 불가 — vocabulary.py:334 `isinstance(value, dict) and
  part in value`(dict 전용). (6) **engine allowlist에 marketfeed 부재**(MAJOR-1 근거·`grep -niE 'marketfeed'
  tos/tests/engine/test_engine_import_closure.py` → 0) → F1이 engine→marketfeed edge를 안 만들므로 이 테스트
  무변경 통과.
- **존재 주장 실측 확인**(SIR #28 교훈): 인용 심볼 전부 read 확인 — `DecisionContextResolver`(core.py:86-105·
  __init__:111)·`DecisionTickPayload`(records.py:157-170)·`build_environment`(determinism.py:88-108)·`evaluate`
  (:238-284)·`captured_external_value_refs: tuple[str,...]`(determinism.py:78)·`_captured_value_refs`(:111-119
  snapshot digest만 반환)·`resolve_operand`(vocabulary.py:316-340)·`Observation.raw.payload_digest`
  (observation.py:74)·`observation.time.source_event_time`(observation.py:85·80-82)·`CriticalInputSnapshot.
  observations`(snapshot.py:157·covered :131)·`TransformationLineage`(lineage.py:96-115)·`FieldState`/`worst`
  (field_state.py:24-31·70-87)·`admitted_field_state`(predicates.py:239-253)·`ScalarValue`(vocabulary.py:93)·
  `EVL1ProvisionalCanonicalizer`(canonical/__init__:39)·`compare_has_capsule_operand`(admission.py:114)·
  **engine→dsl edge**(records.py:28-33)·**dsl→capsule edge**(determinism.py:35)·engine allowlist 14패키지
  (test_engine_import_closure.py:59-76).

---

## 1. 범위 + provisional 선언 + 조항 하중 지도

### 1.1 provisional 선언 — 왜 슬라이스가 EV를 닫지 못하는가 (정직 스코프·D-E1 §1.1 동형)

세 독립 사유가 합류한다(D-E1 §1.1과 동일 구조):

1. **G2 프로덕션 canonicalization 미결.** 값↔digest 바인딩(§2.3 payload_digest 검증)·value-view canonical
   digest(§3.2 서명 append)는 전부 `EVL1ProvisionalCanonicalizer`/`EV_L1_PROVISIONAL_VERSION`(canonical/__init__:
   35-39) 위에서 돈다. register §6:132 — 프로덕션 canonical·digest 승인은 "EV-L2+ 실행 전 필요." 산출 digest 비프로덕션.
2. **P0-1 bounds 승인·P0-3 독립 리뷰어 미완**(register §4:108). 값 표면이 소비할 freshness/validity-window
   bound(§8)가 다수 null/미신설.
3. **모델+property 저작이지 런타임 아님.** 실 관측 수집·snapshot 조립·발행은 Context Integrity Service 런타임
   (설계 #2 §0.2 비-scope). 본 슬라이스는 **admitted snapshot을 소비해 값을 §10-conformant로 노출하는 계약**을
   실증하지, 그 조립의 acceptance를 산출하지 않는다.

⇒ 슬라이스 #1 D-E2의 가치는 **값이 재라벨링(§10 위반)이 아니라 admitted Critical Input 채널로 흐르는 계약의
기계·property**다. **닫는 EV = 0.** 정식 수용은 §9 게이트 완료 후 재실행.

### 1.2 조항 하중 지도 (RFC-004/008 + ADR-002-018 → D-E2 Realize / Defer·자체 실측)

| 원천 | Realize (D-E2 하중) | Defer (명시 이연) |
|---|---|---|
| **RFC-004 §9** Market Data as Critical Input | 242-244 admitted·source/continuity/provenance·**no side channel**(§2.3 값⟺digest)·245-247 derived lineage(§5)·248-250 restrictive uncertainty(§6)·251-252 no relabel(§3 D-E1 계약 실현) | 253-255 self-certify/health-infer 완전 강제(런타임·§9) |
| **RFC-004 §6** Market Model Principles | 162-165 principle 3 admitted observation·no forward-fill(§5 look-ahead)·172-175 principle 6 파생 결정성(§5.2 lineage reproducible) | estimator 값·§7:200-202 window params(=config·§5.3) |
| **RFC-008 §9** Determinism | 290-301 captured-before-eval·delivered into Capsule as Critical Input(§2·§3 규범 앵커)·302-306 recorded provenance(§3.2 서명 append·MAJOR-2)·307-310 bounded eval(D-E1 §3.4 소유) | bit-identical(ADR-DEV-002·설계 #2 §4.3) |
| **RFC-008 §10** Consuming | 327-331 Critical Input always·no relabel(§3)·347-350 UNKNOWN restrictive(§6) | 332-335 tradability(ADR-002-019·미접촉·§0.3) |
| **RFC-008 §7** Authoring Surface | 237-238 no rename-escape(§3)·239-240 no wildcard field ref(§2.4 field_key governed) | 나머지 containment(DSL 소유) |
| **ADR-002-018 §9** Source/Continuity/Admission | 249-261 관측 provenance 바인딩(REUSE)·263-270 admission reject/uncertain(§2.2 gate)·272 continuity not inferred(§6) | fault-injection 재현(EV-L2·설계 #2 §7) |
| **ADR-002-018 §10** Transformation Lineage | 276-287 파생 lineage 바인딩(REUSE·§5)·288 no hidden default/forward-fill·unreproducible→INVALID·290 common-mode | 완전 재현 실행(런타임) |
| **ADR-002-018 §11** Snapshot/Cut | 294-307 snapshot 필드-상태·worst-credible(REUSE)·309 individually-fresh≠valid·311 no averaging/majority(§6) | 실 조립 런타임(§0.2) |
| **ADR-002-018 §14** Freshness | 350-352 trustworthy-time·365 negative/future/missing not clamped(§4·§6)·367 last-known-good≠new-risk(§5) | bound 값 승인(§8·P0-1) |
| **ADR-002-018 §15** Binding | 373-386 exact Capsule 바인딩·reject mismatch·**no silent substitute more permissive**(§3.3 resolver 바인딩 무결) | 8-point 소비자 구현(각 ADR) |
| **설계 #2 §6.2** Validity Window | 600-625 as-of 앵커=`source_event_time`(wrap 아님)·re-wrap 불변(§4.2) | — |

### 1.3 스파이크 갭 → D-E2 소유 지도 (전수·소유권 명시)

| 갭 | 스파이크 근거 | D-E2 처분 |
|---|---|---|
| **G6** Capsule 수치 leaf 0·`price_and_order_constraints: tuple[str,…]`뿐 | capsule.py:79 | §2 — dsl shape + marketfeed 생산이 수치 leaf 소유·capsule 무변경 |
| **G8** Observation 값 미탑재·`raw.payload_digest` 포인터만 | observation.py:70-74 | §2.3 — 값⟺payload_digest 구조 바인딩(값은 covered raw payload 뒤·provenance는 관측이) |
| **G9** Capsule은 `SnapshotRef`만 내장·snapshot body 미내장 | capsule.py:41-51·233 | §3.3 — resolver가 SnapshotRef→body 해소(주입 store·바인딩 무결 검증) |
| **G10** 유일 작동 채널=`config.bindings` 재라벨링(§10 위반) | determinism.py:60 | §3 — D-E1 계약 실현(값=capsule 소스·config=상수)·admission 부분 봉인(admission.py:114) |
| **G13** per-bar identity가 capsule digest 차이에 전적 의존·붕괴 | 스파이크 §2-G13 | §4 — 값을 covered snapshot(source_event_time)으로 옮기면 distinctness 구조 corollary |
| **G1/G3** DSL 산술·bar 이력 부재 → 파생 지표 상류 계산 필요 | vocabulary.py:70-83·338-340 | §5 — 지표=상류 Critical Input·lineage-싣는 admitted observation |
| **G7** config_version per-bar churn 오염 | determinism.py:59·281 | §4.4 — D1이 root 해소(값이 config 미경유 → config_version 안정) |

---

## 2. 값-싣는 표면 모델 (핵심 결정 A — 형=dsl 소유·생산/검증=marketfeed 소유·capsule 무변경)

### 2.1 문제 (스파이크 G6/G8 재실측)

`Observation`(observation.py:148-166)은 provenance 레코드다 — `source`/`trust_identity`/`continuity`/`raw`/
`time`/`semantics`/`mapping`/`admission`/`field_state` 등을 갖되 **수치 값 leaf가 없다.** 실측 확인: ADR-002-018
§9:249-261 관측 바인딩 열거에도 **관측된 수치 값 자체는 없다** — "raw event identity and payload digest"(:256)·
"instrument … unit, scale, multiplier, and sign metadata"(:259)만 있다. **값은 covered raw payload 뒤에 산다**
(payload_digest가 가리킴). ADR 모델은 provenance/admission/validation 층이고, 실제 수치는 raw event가 담는다.

⇒ 결정에 필요한 수치(예 `close`·`lower_band`)를 DSL에 노출하려면 covered raw payload의 수치를 꺼내 admitted
관측에 귀속시켜 스칼라로 표면화해야 한다. 이 표면은 capsule에 없으므로(무변경 원칙) **greenfield**다.

### 2.2 판정 — env-값 형은 dsl `ContextValueView`, 생산/검증은 marketfeed (v1.1 MAJOR-1)

**소유권 분할(F1)**: DSL이 env-shape(resolve_operand 항법·ADMISSIBLE_CONTEXT_SOURCES)를 소유하므로 env-값
**형은 `tos.dsl`에 정의**한다. `tos.marketfeed`는 그 형의 **생산자/검증자**다. (근거: `DecisionTickPayload.
value_view`가 marketfeed 타입이면 `tos.engine.records`가 marketfeed를 런타임 import → engine import-closure
allowlist(14패키지·marketfeed 부재·test_engine_import_closure.py:59-76) 위반 + `engine→marketfeed→engine` 순환.
dsl 타입이면 engine→dsl 기존 edge(records.py:28-33)로 순환 0·allowlist 무변경.)

**dsl 신규 형(shape only·값 데이터 컨테이너)**:

`ContextValue`(env-값 1항목·dsl):

| 필드 | 타입 | 의미·근거 |
|---|---|---|
| `field_key` | `str` | DSL-가시 안정 이름(예 `"close"`·`"lower_band"`·`"session"`). governed·wildcard-free(§2.4·RFC-008 §7:239-240) |
| `value` | `ScalarValue`(=bool\|int\|float\|str·vocabulary.py:93) | admitted 수치/상태 스칼라. **DSL-비교 가능 형**(§2.5 — 수치는 정수 tick-scale 우선·Decimal 금지) |
| `as_of` | `int`(epoch-ms) | 값의 recorded as-of/production 시각 = 귀속 관측 `time.source_event_time`(observation.py:85). Validity Window 앵커(§4.2)·**distinctness 하중**(§4.1 MINOR-1) |
| `payload_digest` | `str` | 값-**provenance** 포인터 = 귀속 관측 `raw.payload_digest`(observation.py:74). covered(§4.1) |
| `observation_ref` | `str` | 귀속 admitted 관측 식별(구조 파생 링크·§2.3) |

`ContextValueView`(dsl·컨테이너):

| 필드 | 타입 | 의미 |
|---|---|---|
| `snapshot_id` / `snapshot_canonical_digest` | `str` | 귀속 snapshot 바인딩(§3.3 resolver 무결 검증·capsule.SnapshotRef 대조) |
| `values` | `tuple[ContextValue, ...]` | 노출 값(전수·중복 field_key 금지·§6 source disagreement) |
| `canonical_digest` | `str` | **value 집합의 canonical digest** — `evaluate` 서명에 append(재현성 4입력·MAJOR-2·§3.2) |
| `canonicalization_version` | `str` | `ev-l1-provisional-0`(§1.1·provisional) |

`ContextValue.field_state`는 dsl 형이 **재보유하지 않는다** — VALID-gate(아래)가 marketfeed 생산 시점에 적용되어
`values`는 **VALID by construction**이다(dsl→capsule.FieldState 결합 최소·형은 lean container). 검증 책임은
marketfeed 생산자 + property(§7.2)에 있다(§4.3 신뢰 seam).

**marketfeed 생산/검증 로직(형 밖·§3.3)**: admitted snapshot body를 받아 (i) 값⟺payload_digest 검증(§2.3)·
(ii) VALID-gate 적용·(iii) `ContextValueView.canonical_digest` 계산·(iv) dsl `ContextValueView` 발행.

**VALID-gate — 단일 정의(v1.1 MINOR-4)**: 한 값이 노출되려면
`worst( admitted_field_state(obs.admission.result),  obs.field_state,  ⋃ matching field_evaluations[].state )
== FieldState.VALID` (predicates.py:239-253·field_state.py:57-87 REUSE). **∅ 봉인**: 대응 field_evaluation이
없으면(무평가) `worst`에 **명시 `UNKNOWN` floor**를 넣는다(field_state.py:73-75 — "empty aggregates to VALID …
callers must supply explicit UNKNOWN floor") → 무평가 값은 VALID 불가(vacuous-VALID 봉인). VALID 아니면 항목
부재 → env에서 key 없어 `resolve_operand` UNKNOWN(§3.2) → 비교 False → restrictive. RFC-004 §9:248-250·RFC-008
§10:347-350 "UNKNOWN restrictive" 구조 실현.

### 2.3 값⟺digest 구조 바인딩 (side channel 봉인·발행 시점 검증·신뢰 seam·v1.1 MAJOR-2b)

**RFC-004 §9:244 "never by unattributed fetch or side channel"의 구조 강제**: `ContextValue.value`는 자유부동
스칼라가 아니라 covered `payload_digest`에 바인딩된다 — 값은 그 digest가 어드레스하는 raw payload 안의 수치여야
한다. **marketfeed 생산자가 발행 시점에** 검증: `payload_digest == obs.raw.payload_digest` AND `value`가 그
payload의 canonical preimage에서 나옴(EV-L1 provisional: `canonical(value-bearing payload) == payload_digest`).

- **결과 1(side channel 봉인)**: 값이 covered digest에 바인딩되므로 임의 값 주입 불가 — 값을 바꾸면 payload가
  바뀌고 payload_digest가 바뀌며, 이를 담은 관측이 snapshot covered set(snapshot.py:131 `"observations"` ∈
  `_COVERED_FIELDS`)에 있어 **snapshot digest가 바뀐다**. 값은 snapshot identity에 묶인다.
- **⚠ 신뢰 seam 정직 명기(v1.1 MAJOR-2b·Gap-1)**: 이 검증은 **marketfeed 생산 시점**에 일어난다. **env-주입
  지점(`build_environment`)은 값⟺digest를 재검증하지 않고** 발행된 `ContextValueView`를 신뢰한다. 즉 부정직·버그
  producer가 payload_digest와 불일치하는 값을 실은 view를 발행하면 env가 그대로 소비한다 — 이는 **D-E1의
  "부분 봉인" 신뢰 seam과 동형**(D-E1 §3.2 (3)·admission.py:22-23). D-E2 봉인: (a) 생산자 검증 + property(§7.2-1)·
  (b) **서명 append**(§3.2·MAJOR-2a — 다른 값 집합→다른 view digest→다른 서명→replay/audit 검출 가능)·
  (c) 완전 강제는 상류 Context Integrity Service(§0.2). over-claim 금지: 구조 바인딩은 생산자 검증 + 서명 검출을
  주지 env-주입 지점의 재검증을 주지 않는다.
- **preimage 정직**: raw payload의 정확한 canonical preimage 형태(전체 native event vs 추출 필드)는 D-E2 구현·G2
  승인 후 확정(미결-3). 본 계약이 고정하는 것은 **바인딩 속성**(값⟺covered digest)이지 preimage 바이트가 아니다.

### 2.4 field_key governance (wildcard 금지·admitted 관측 대응)

`field_key`는 DSL ref leaf 이름(operand.ref 마지막 성분)이다. governance:
- **wildcard/latest 금지**(RFC-008 §7:239-240). concrete 문자열·`_is_wildcard_scope` 형(records.py:76-90 REUSE) 거부.
- **admitted 관측 대응 강제**: 각 `field_key`는 귀속 snapshot `field_evaluations[].field_ref`(field_evaluation.py:56)에
  대응하고 그 state가 VALID여야 한다(§2.2 gate) — self-report 아니라 snapshot governance에 귀속(구조 파생 >
  자기신고·property §7.2-7). field_ref↔field_key 대응은 marketfeed 생산자가 검증(§3.3).
- **∅ 양방향**(§6): admitted 값 0개 explicit-empty view(정의된 무값) vs snapshot 해소 실패(missing) 구분.

### 2.5 값 타입 제약 (정수 tick-scale 우선·Decimal fail-closed·v1.1 MINOR-2)

⚠ `resolve_operand`는 `bool|int|float|str` leaf만 스칼라로 인정(vocabulary.py:338)·순서비교(LT/LE/GT/GE)는
int/float 전용·bool 제외(vocabulary.py:366-368). 귀결(v1.1 강화):

- **수치 순서비교 값은 정수 tick-scale로 노출한다(우선)**: 가격 등은 minor-unit/tick 정수로 노출(예 원 정수·틱
  정수). scale/unit/multiplier는 관측 `mapping`(observation.py:107-115·경제적 유의 별개 안전 필드)에 provenance로
  보존. 정수는 **플랫폼-독립·exact**라 float 이진오차·경계 비결정을 원천 제거.
- **분수 수량이 불가피하면 deterministic float 투영만**(canonical decimal → 명세된 결정적 규칙). **`Decimal`
  직접 노출 금지·silent 강제변환 금지**: canonical 값이 exact 정수/deterministic-float로 투영 불가면 값을 **노출
  안 함**(구조적 UNKNOWN·fail-closed) — silent `float()` 강제 금지.
- **긴장 정직 명기**: capsule 잠정 canonicalizer는 magnitude를 decimal 정규화(설계 #2 §3.4:397-403). env-가시 값
  = 정수 tick / deterministic-float 투영, provenance/digest = canonical decimal, 둘 바인딩. `model_dump(mode=
  "json")`(determinism.py:106)는 JSON-native라 이 규약과 정합.
- 상태 값(예 `session`=REGULAR/PRE_OPEN)은 **str**·EQ/NE(vocabulary.py:361-364). 스파이크 `session == REGULAR`
  술어가 이 형(스파이크 §0·line 33-34).

### 2.6 검토·기각 대안

- **(A) Observation에 `value` 필드 추가** — 기각: capsule 계약 변경(무변경 원칙). 불가피 아니므로 미결 승격 안
  함(§15) — 값⟺payload_digest 바인딩(§2.3)이 greenfield로 동등 provenance.
- **(B) 값-carrier 형을 marketfeed에 정의**(v1.0 판정) — **기각(v1.1 MAJOR-1)**: engine→marketfeed 순환·
  allowlist 위반. F1(형=dsl)로 대체.
- **(C) Capsule `price_and_order_constraints`(capsule.py:79)에 수치 문자열** — 기각: 안전 fact 요약(승인 대조·
  설계 #2 §4.2:447)이지 값 표면 아님·문자열 파싱 governance 우회.
- **(D) SnapshotRef를 body로 확장** — 기각: capsule.py:233 변경. resolver가 밖에서 body 해소(§3.3)·capsule 무변경.
- **(E) 값을 관측 없이 스칼라만** — 기각: side channel·distinctness 붕괴·provenance 부재. 값⟺digest 필수(§2.3).

---

## 3. env-조립 seam 계약 (핵심 결정 B — 본 문서의 하중·D-E1 §3.2/§12-1 실현·F1)

### 3.1 문제 (committed 엔진 경로 재실측 — 값이 도달할 통로가 없다)

실측 경로:
1. `DecisionTickPayload`(records.py:157-170)는 `instrument_key`/`capsule`/`time`/`reference`만 — **값 필드 없음**.
   docstring:161-163 명시: "The Critical Input **value surface** … is D-E2's to add … slice #1 binds the
   Capsule's `SnapshotRef` only."
2. `run_decision_pipeline`(pipeline.py:230)은 `evaluate(entry.strategy, payload.capsule, entry.config, …)`
   (pipeline.py:311-317) 호출 — `payload.capsule`(frozen·값 없음)만.
3. `evaluate`(determinism.py:238)는 `build_environment(capsule, config)`(:267)를 부르고, 반환은 정확히
   `{"capsule": capsule.model_dump(mode="json"), "config": dict(config.bindings)}`(:105-108).
4. `resolve_operand`(vocabulary.py:316-340)는 env를 **dict-키로만** 걷고(:334 — list/tuple 인덱싱 불가) **스칼라
   leaf**(:338)를 요구한다.

⇒ capsule dump에 값이 없다(SnapshotRef만·G9). `DecisionTickPayload`·`evaluate` 호출에도 값 통로가 없다. ⇒ 값을
`env["capsule"]`에 넣는 유일 길은 env-조립이 resolved 값을 병합하는 것이며, capsule 무변경으로 하려면
`build_environment`의 입력 조립을 확장해야 한다.

### 3.2 판정 — governed scalar leaf + dsl-타입 additive 조립 + 서명 append (F1·MAJOR-2)

**시장값은 `env["capsule"]` 밑 governed sub-path 스칼라 leaf로만 도달한다. 통로는 build_environment의 additive
확장(dsl-타입 소비)이며, evaluate_policy·capsule 모델은 무변경. resolved_context는 서명에 digest append로
재현성을 확보한다.**

1. **노출 위치 + namespace 무충돌(v1.1 MINOR-3)**: `env["capsule"][VALUE_NAMESPACE][field_key] = scalar`.
   `VALUE_NAMESPACE`(권장 예약 키·예 `"resolved_values"`)는 `DecisionContextCapsule.model_dump(mode="json")`
   top-level 키 집합과 **구조적 disjoint**여야 한다(capsule top-level 17: `artifact_type`·`schema_version`·
   `issuer_principal_id`·`critical_input_policy`·`context_generation`·`critical_input_snapshot`·`scope`·
   `safety_critical_facts`·`generation_vector`·`independent_validation`·`validity`·`authority`·`venue_constraint_
   policy`·`venue_constraint_snapshot`·`order_admissibility_decision`·`bindings`·`capsule_id` + Layer-0
   `canonical_digest`/`status`/`canonicalization_version` — capsule.py:225-245). 병합은 **키 충돌 시 발행 거부**
   (fail-closed·기존 covered 필드 덮어쓰기 금지)·property로 disjointness 강제(§7.2-3). DSL ref 예:
   `("capsule", "resolved_values", "close")`. `"capsule"` 소스라 D-E1 §3.2 계약·`ADMISSIBLE_CONTEXT_SOURCES`
   (vocabulary.py:88·3rd 소스 미신설) 정합.
2. **왜 dict-of-scalars인가**: resolve_operand는 list 인덱싱 불가·스칼라 leaf 전용(§3.1). field_key-키잉 평면
   dict만 도달 — §2.4 field_key governance의 기계적 근거.
3. **additive 확장(D-E1 §3.2(A) 위임 "입력 조립"·dsl 타입·MAJOR-1 F1)**:
   - `build_environment(capsule, config, *, resolved_context: ContextValueView | None = None)` — 신규 **keyword-
     only** optional param(dsl 타입). `None`이면 오늘과 **바이트 동일**(하위호환). 제공 시 `env["capsule"]
     [VALUE_NAMESPACE] = {v.field_key: v.value for v in resolved_context.values}` 병합.
   - **신규 public 진입점 `evaluate_resolved(…, resolved_context=None)`(v1.2 에라타·determinism.py:362)** — threading + **서명 조립(MAJOR-2a)**: resolved_context 제공 시
     `signature.captured_external_value_refs`(determinism.py:78·이미 `tuple[str,...]`)에 **`resolved_context.
     canonical_digest`를 append** → `_captured_value_refs(capsule) + (resolved_context.canonical_digest,)`(공유 본체 `_evaluate`·determinism.py:297-303). 다른
     값 집합 → 다른 view digest → 다른 서명 → replay/audit 검출(재현성 4번째 입력 커버). **⚠ v1.2 정정: 기존 `evaluate`(determinism.py:319)는 5-파라미터·byte-identical 유지**(committed 시그니처 canary test_dsl_determinism.py:136-146 green·§15.2③). `evaluate_policy` 호출부
     (`_evaluate`·determinism.py:293)·`_decision_to_outcome`·`RecordedInputSignature` 나머지는 **무변경**.
   - `DecisionTickPayload`에 `value_view: ContextValueView | None = None` **additive dsl-타입 필드**(D-E1 이연
     records.py:157-163·engine→dsl 기존 edge records.py:28-33). `run_decision_pipeline`이 `payload.value_view`를
     `evaluate_resolved(…, resolved_context=…)`에 전달(pipeline.py:311 additive).
4. **소유권**: dsl이 env-shape·형·조립·서명을 소유하고, marketfeed는 형의 **값 데이터**(검증된 ContextValueView)를
   공급한다 — "dsl owns shape+env, marketfeed owns value production/verification."

### 3.3 `DecisionContextResolver` 구현 계약 (D-E1 §12-1 slot 충족·marketfeed)

D-E1 Protocol(core.py:86-105): `(capsule, *, instrument_key) -> DecisionTickPayload`. marketfeed 구체 구현:

1. **snapshot body 해소**: `capsule.critical_input_snapshot`(SnapshotRef·capsule.py:233)의 id/digest로 **주입
   snapshot store**에서 `CriticalInputSnapshot` body 조회(상류 발행 content-addressed·D-E3=히스토리·D-E4=라이브
   주입·§6.5).
2. **바인딩 무결(ADR-002-018 §15:386 — no silent substitute more permissive)**: body의 `snapshot_id`/
   `canonical_digest`가 ref와 일치. 불일치·missing → **fail-closed**(`value_view=None` → 전 capsule-operand
   UNKNOWN → restrictive no-action).
3. **`ContextValueView` 생산**: admitted(ADMITTED·VALID·§2.2 gate) 관측에서 §2.3 바인딩으로 값 추출·검증·
   field_key↔field_ref 대응 검증(§2.4)·값 집합 canonical digest 계산·dsl `ContextValueView` 발행.
4. **reference time 좌표**: `TimeAdmissionInputs`(records.py:125-154)를 관측 `source_event_time`(as-of)+주입 clock
   판독으로. 코어는 wall-clock 미호출(D-E1 §2.3·core.py:16-18).
5. **반환**: `DecisionTickPayload(instrument_key, capsule, time, reference, value_view)`.

⚠ **정직(D-E1 core.py:93-98 반향)**: resolver는 값 표면을 **발명하지 않고** 상류 admitted snapshot을 소비·해소·
검증할 뿐이다. 관측이 admitted 아니면 값 미노출(over-realization 금지).

### 3.4 패키지 분할 (closure 최소·순환 0·F1)

- **`tos.marketfeed.value`(순수 검증·§2)**: 값⟺digest 검증 술어·VALID-gate·env 투영 헬퍼·`ContextValueView`
  **생산자**(dsl 형을 채워 반환). closure = {tos, tos.canonical, tos.ordering, tos.capsule, tos.dsl, tos.time,
  tos.marketfeed} — **`tos.engine` 없음**. §7.1 순수-closure canary 대상.
- **`tos.marketfeed.resolver`(어댑터·§3.3)**: 구체 `DecisionContextResolver` — `DecisionTickPayload` 생산 →
  `tos.engine` edge. downstream 의존(정상)·순수 층 분리로 오염 방지.
- **핵심(순환 0)**: `ContextValueView` 형은 **dsl에** 산다 → `dsl→marketfeed`·`engine→marketfeed` edge 불요 →
  `engine→marketfeed→engine`·`dsl→marketfeed→dsl` 순환 없음. build_environment/evaluate/DecisionTickPayload의
  additive 확장은 dsl/engine **내** 변경이고 dsl-타입만 참조(§15 미결-1 sanction 대상·터치 전모 §15.2).

### 3.5 검토·기각 대안

- **(A) capsule 모델 값-싣게 변경** — 기각: 무변경 원칙. 불가피 아님 → 미결 승격 없음(§15).
- **(B) 엔진이 env 직접 조립·`evaluate_policy` 직호출** — 기각: `evaluate` outcome/signature 조립
  (determinism.py:269-283)을 엔진에 중복(DRY 위반). env-조립 dsl 소유가 정합(§3.2 소유권).
- **(C) 3rd `"market"` 컨텍스트 소스 신설** — 기각: D-E1 §3.2 alt C·core.py:96 — vocabulary 변경·`"capsule"`
  이미 Critical Input governance라 중복.
- **(D) 값을 `config.bindings`로** — 기각: G10 재라벨링·RFC-008 §10:329·RFC-004 §9:251-252 정면 위반·distinctness
  붕괴. D-E2 존재 이유.
- **(E) 값-병합 capsule-dump를 payload에 실음** — 기각: dict라 payload.capsule 타이핑(capsule_admitted·scope
  pipeline.py:185-196) 붕괴. capsule은 typed·값은 별도 dsl-타입 필드.
- **(F) 값-carrier 형을 marketfeed에 두고 engine allowlist에 marketfeed 추가** — **기각(v1.1 MAJOR-1)**: allowlist
  추가는 declared-edge 테스트(test_engine_import_closure.py:318-327 — 선언된 edge는 실제로 closure에 있어야)를
  만족하려면 engine→marketfeed 실 edge 필요 → 층위 역전·순환. F1(형=dsl)이 유일 무순환 해법.

---

## 4. per-bar identity distinctness (핵심 결정 C — G13 해소·D-E1 Gap-1 이연분)

### 4.1 판정 — distinctness는 covered `source_event_time`을 탄 구조 corollary (v1.1 MINOR-1)

**값이 covered snapshot 관측으로 흐르면 distinct bar → distinct proposal_id가 구조적으로 따라온다.** v1.1 하중
재서술(MINOR-1): 사슬의 하중을 **covered `source_event_time`**에 둔다(payload_digest preimage 선택 무관 robust).

연쇄(전부 실측 근거):
1. distinct bar → **distinct `time.source_event_time`**(관측 as-of·observation.py:85·발행 gate가 concrete 강제
   §4.2). 두 bar는 서로 다른 as-of 시각을 갖는다.
2. `source_event_time`은 관측 필드이고 관측은 snapshot `_COVERED_FIELDS`(snapshot.py:131 `"observations"`)에
   있다 → **distinct snapshot `canonical_digest`**(설계 #2 §3.4 (A)-3 covered 민감성).
3. capsule Layer-1은 `critical_input_snapshot.canonical_digest` 포함(capsule.py:193-194·covered) → **distinct
   capsule `canonical_digest`**(설계 #2 §3.3:377-379 snapshot→capsule 단방향 DAG).
4. `evaluate` outcome id는 capsule_id 파생(determinism.py:197·228) → **distinct proposal_id**. 붕괴 없음.

**payload_digest 역할 분리(MINOR-1)**: `payload_digest`도 값이 다르면 달라져 distinctness를 **부수 강화**하나,
그 preimage 형태는 미결(§2.3·미결-3)이므로 distinctness의 **1차 하중은 source_event_time**에 둔다. payload_digest는
값-**provenance**(side-channel 봉인·§2.3)로 역할 분리.

### 4.2 발행 gate — as-of + payload_digest concrete 강제 (greenfield·capsule 무변경)

`ContextValue` 발행(marketfeed 생산)이 강제:
- `as_of`(=관측 `time.source_event_time`) **concrete 필수**(None 거부·fail-closed). Validity Window 앵커(설계 #2
  §6.2:600-615)이자 **distinctness 1차 하중**(§4.1).
- `payload_digest` **concrete 필수**(None 거부). 값 provenance(§2.3).

이는 **marketfeed 발행 gate**(greenfield)이지 capsule `_REQUIRED_COVERED`(snapshot.py:112-120·capsule.py:189-204)
변경이 **아니다** — 관측 모델은 두 필드를 이미 갖되 optional(observation.py:74·85). marketfeed가 값 씌울 때
concrete 요구할 뿐. **capsule 무변경 확인.** **re-wrap 불변**(설계 #2 §6.2:623-625): staleness는 as-of 기준
(`now - source_event_time`)·wrap time 미사용.

### 4.3 정직 경계 (완전 봉인은 producer 정직 의존·신뢰 seam·MAJOR-2b/Gap-1 통합)

distinctness는 producer가 bar마다 distinct 관측(distinct as-of)을 실을 때 성립한다. 진부·버그 producer가 두 bar에
동일 as-of를 실으면 붕괴하나, 이는 **발행 gate가 잡지 못하는 producer 정직 문제**(D-E1의 D1↔D4 "부분 봉인"
동형·§2.3 신뢰 seam과 같은 축). D-E2는 (a) 발행 gate로 as-of/payload_digest 부재를 fail-closed·(b) property로
"distinct as-of → distinct snapshot digest"를 실증하되·(c) producer가 실제로 bar를 구별해 실었는지의 완전 강제·
값⟺digest 재검증은 상류 Context Integrity Service + 서명 append 검출(§3.2)이 담당. reproducibility는 실증,
distinctness는 구조 보장+정직 경계. **over-claim 금지**(v1.1).

### 4.4 G7 부수 해소

G7(config_version이 매 bar 바뀌어 replay signature 오염·스파이크 G7·determinism.py:59·281)은 **D1이 root 해소**:
값이 `config`를 안 거치므로(§3 값=capsule 소스) `config_version`이 bar마다 안 바뀐다. config는 저작자-상수만
싣는다(D-E1 §3.2 (2)). ⇒ replay signature는 capsule digest + value-view digest(§3.2)로 bar를 구별하고
config_version은 안정.

---

## 5. 지표 파이프라인 (핵심 결정 D — 파생 지표의 Critical Input 化·look-ahead 경계)

### 5.1 판정 — 파생 지표 = 상류 계산·lineage-싣는 admitted observation

**밴드·이동평균·regime 등 파생값은 DSL 내부가 아니라 상류에서 계산되어, 기구현 `TransformationLineage`(REUSE)를
실은 admitted 관측으로 snapshot에 진입한다.** 규범 앵커:
- RFC-008 §9:290-301 — 외부/파생 값은 "produced *outside and before* DSL evaluation and delivered into the
  Decision Context Capsule as Critical Input." DSL 평가는 live 계산 안 함(captured-not-called·determinism.py:11-15).
- DSL algebra는 산술/집계 노드·bar 이력 부재(G1·G3·vocabulary.py:70-83·:338-340). ⇒ 밴드 DSL-내부 계산 불가 —
  상류 Critical Input(스파이크 G1 소유).
- RFC-004 §9:245-247 — "SHALL derive every indicator or feature with complete deterministic or explicitly
  stochastic lineage from admitted observations."

### 5.2 lineage 계약 (REUSE `TransformationLineage`·재저작 금지)

파생값 관측은 snapshot `transformation_lineage`(snapshot.py:158·기구현 lineage.py:96-115) 노드를 가진다:
- `parents`(lineage.py:106) — 정확한 부모 관측+digest(밴드 부모=close 관측들).
- `transform_graph`·`versions`·`unit_conversions`·`numeric_behavior`·`stochastic`(seed/nondeterminism)·
  `output_spec`·`reproducible: bool`·`field_state`.
- **재현불가/부모 누락 → INVALID**(설계 #2 §2.3:238-240·CII-EV-004·ADR §10:288) → §2.2 gate 미노출. RFC-004
  §6:172-175 결정성 실현.
- **hidden-default 금지**(ADR §10:288 — forward/zero fill·silent coercion·symbol alias·fallback source):
  `numeric_behavior` 미기록 imputation은 lineage 불완전 → INVALID. look-ahead·last-known-good 우회 봉인.

### 5.3 D-E2는 estimator를 구현하지 않는다 (경계 명시)

- **estimator·window·수식·k 배수는 config·상류 모델 선택**(RFC-004 §7:200-202·§8:227-229). D-E2는 파생값이
  admitted·lineage-싣는 관측으로 표면화되는 계약만 정한다 — 밴드 계산법은 상류(D-E3 백테스트=히스토리 재계산·
  D-E4/live=상류 파이프라인) 소유.
- 저작자-상수(k·period)는 **config.bindings**(D-E1 §3.2 (2)·determinism.py:60 저작자-상수 전용). 시장 파생 수치
  (계산된 밴드 값)는 **capsule 값 표면**(§2). 이 분할이 §10 재라벨링 경계.

### 5.4 look-ahead 금지 경계 (D-E2 표현·D-E3 강제)

- **규범**: RFC-004 §6:162-165 principle 3 — "no out-of-context fetch, default, forward-fill, or last-known-good
  substitution." ADR §14:367 — last-known-good는 ordinary new risk authorize 못 함.
- **D-E2 소유**: 파생값 관측 parent `as_of` ≤ 파생값 `as_of`를 **lineage로 표현**·property 검증("파생값 parent
  source_event_time 전부 ≤ 파생값 source_event_time"). 지표 입력이 현 컨텍스트 timestamp에 bounded(CLAUDE.md
  백테스트 규율·`LookaheadGuard` 정신).
- **D-E3 소유(강제)**: 백테스트에서 producer가 실제로 미래 bar를 안 봤는지의 **런타임 강제**는 D-E3 LookaheadGuard
  (지식 참조·import 아님). D-E2는 lineage로 표현·검증 가능케 하되 dishonest producer를 완전 차단하진 않는다(정직
  명기·§4.3 동형).

### 5.5 검토·기각 대안

- **(A) DSL 산술 노드 추가해 밴드 DSL-내부 계산** — 기각: vocabulary 변경·RFC-008 §7 containment·bar 이력 부재·
  §14 확장 governance. 지표=상류 Critical Input이 규범(RFC-008 §9:290-301).
- **(B) 파생값 lineage 없이 스칼라만** — 기각: RFC-004 §9:245-247 lineage 필수·재현성/common-mode 판정 근거 상실.

---

## 6. fail-closed 규율 + 극성 + ∅ (시리즈 술어 규율의 값-표면 적용)

- **positive-admit(양성 gate·단일 정의·MINOR-4)**: 값은 `worst(admitted_field_state, obs.field_state,
  ⋃field_evaluations[].state)==VALID`일 때만 노출(§2.2·∅ field_evaluation→UNKNOWN floor로 vacuous-VALID 봉인·
  field_state.py:73-75). `!= INVALID` 음성 gate 금지 — VALID는 모든 차단 술어 통과의 유일 상태(field_state.py:27).
  None·미확정 → key 부재 → UNKNOWN.
- **음극성 bool|None은 `is False`만**(시리즈 교훈): `continuity.continuity_gap`(observation.py:67)·`freshness.
  within_bound: bool|None`(field_evaluation.py:43)·lineage `reproducible: bool`(lineage.py:114) 소비 시 —
  `within_bound is False`·`continuity_gap is True`(양극성 gap)를 restrictive로 읽고, `within_bound is None`은
  fail-closed(field_evaluation.py:37-38 "missing window … UNKNOWN"). 극성별 규율 각 소비 지점 명기(§7.2 canary).
- **UNKNOWN-restrictive**: RFC-008 §10:347-350·RFC-004 §9:248-250. 값 부재/미확정 → resolve_operand UNKNOWN
  (vocabulary.py:337·340) → 비교 False → action set narrow only. permissive default 금지.
- **∅ 양방향**(D-E1 §6 상속): **explicit-empty**(admitted 값 0개 발행 view — 정의된 무값 → 전 capsule operand
  UNKNOWN → restrictive) vs **missing**(snapshot 해소 실패·바인딩 불일치 → fail-closed·§3.3). 둘 다 restrictive이나
  **사유 구별 기록**.
- **source disagreement(ADR §14:365·§11:311)**: 같은 field_key 상충 관측은 **majority/평균 금지**.
  `ContextValueView.values`는 field_key 중복 **거부**(발행 fail-closed) 또는 CONFLICTED → 미노출. 임의 하나로 접기
  금지(§2.2 gate·property §7.2-7).
- **negative/future/missing as_of(ADR §14:365 — cannot be clamped)**: freshness gate(엔진 `time_admits`·
  pipeline.py:199·tos.time)가 restrictive 처리. 값 view는 as_of를 그대로 실어 clamp 안 함.

---

## 7. firewall allowlist + property test 타깃

### 7.1 import-closure allowlist (2단·순수/어댑터·순환 0)

- **순수 값 모델**(`tos.marketfeed.value`·§3.4): fresh interpreter import 후 top-level `tos.*` ⊆ `{tos,
  tos.canonical, tos.ordering, tos.capsule, tos.dsl, tos.time, tos.marketfeed}` — **`tos.engine` 미포함**.
  planted-leak canary: `shared.*`·`shared.config`(→ secrets)·`tos.engine`·`tos.egress`가 새면 실패.
- **resolver 어댑터**(`tos.marketfeed.resolver`): `tos.engine` edge 허용(downstream)·그 외 금지 동일.
- **순환 0 canary(v1.1 MAJOR-1)**: committed `tos/tests/engine/test_engine_import_closure.py` allowlist(14패키지·
  :59-76)·subset 테스트(:310-315)·declared-edge 테스트(:318-327)가 **marketfeed 무추가로 여전히 green**임을
  negative-grep(`marketfeed` ∉ engine closure·§0.5-6)으로 병기. dsl closure도 marketfeed 미포함(dsl→marketfeed
  edge 부재)·capsule은 이미 dsl closure(determinism.py:35 dsl→capsule) — 새 dsl 형 모듈이 capsule.FieldState 참조해도
  dsl closure 무변경.
- 추가 assert(설계 #1 §3.4·설계 #2 §7.1): 어떤 marketfeed 소스도 `os.environ`/`getenv`·network stdlib·
  `importlib`/`exec`/`eval`/`compile`·`shared.llm`·`numpy`/`pandas` 미참조 — 값을 fetch 안 하고 주입받음의 구조
  강제(RFC-004 §9:242-244). 서브프로세스 격리·run manifest 기록(설계 #2 §7).

### 7.2 property test 타깃 (오케스트레이션/값-표면 불변식·저작 증거·acceptance 아님)

닫는 EV 0이므로 저작 증거다(설계 #2 §7·D-E1 §7.2 동형). 타깃:

1. **값⟺digest 바인딩(발행 시점·§2.3)**: `ContextValue.value` 변경 → payload_digest 변경 → 귀속 snapshot digest
   변경. 임의 값(digest 미대응) marketfeed 발행 거부. side-channel 뮤테이션 KILLED. **(신뢰 seam 명시: env-주입
   지점은 재검증 안 함·§4.3.)**
2. **distinctness(§4·G13)**: distinct **as_of** → distinct snapshot digest → distinct capsule digest → distinct
   proposal_id. 같은 값+같은 as_of → 같은 digest(reproducibility). `as_of`/`payload_digest` None 발행 거부.
3. **VALUE_NAMESPACE disjointness(v1.1 MINOR-3)**: 병합 namespace 키가 capsule model_dump top-level 키와 disjoint·
   충돌 시 발행 거부(§3.2·기존 covered 필드 덮어쓰기 금지).
4. **VALID-gate 단일 정의(v1.1 MINOR-4)**: `worst(3상태)==VALID`만 노출·∅ field_evaluation→UNKNOWN floor→미노출
   (vacuous-VALID 봉인). UNCERTAIN/REJECTED/STALE/CONFLICTED/무평가 → 항목 부재. `!= INVALID` 음성 뮤테이션 KILLED.
5. **env 도달성(§3.2)**: 병합 `env["capsule"][VALUE_NAMESPACE][field_key]`가 resolve_operand로 스칼라 도달. list
   노출 뮤테이션은 UNKNOWN(도달 실패·§3.1 dict-전용).
6. **바인딩 무결(§3.3·ADR §15:386)**: resolved snapshot이 capsule SnapshotRef와 id/digest 불일치 → `value_view=
   None` → restrictive. more-permissive substitute 뮤테이션 KILLED.
7. **field_key governance(§2.4)**: wildcard/latest·중복 field_key 거부·field_key↔field_evaluation.field_ref VALID
   대응 강제(source disagreement §6).
8. **재현성 서명 충분성(v1.1 MAJOR-2a·v1.2 진입점 `evaluate_resolved`)**: `evaluate_resolved(…, resolved_context=v)` 서명의 `captured_external_value_refs`가
   `v.canonical_digest`를 포함. 다른 값 집합→다른 서명. resolved_context=None → 서명 오늘과 동일(하위호환).
9. **하위호환 + 시그니처 canary(v1.2)**: `build_environment(capsule, config)`(resolved_context=None) 반환 오늘과 바이트 동일·**기존 `evaluate` 5-파라미터 불변**(committed `test_dsl_determinism.py:136-146` green — resolved-value는 별도 진입점 `evaluate_resolved`).
10. **lineage look-ahead(§5.4)**: 파생값 parent as_of ≤ 파생값 as_of. reproducible=false/parent 누락→INVALID→미노출.
11. **∅ 양방향(§6)**: explicit-empty view(값 0) vs missing snapshot 구별 기록·둘 다 restrictive.
12. **값 타입(§2.5)**: 순서비교 수치=정수 tick-scale·Decimal 노출→미노출(구조 UNKNOWN·silent float 금지)·bool
    순서비교 False(vocabulary.py:366-368).
13. **순환 0/closure(v1.1 MAJOR-1)**: engine·dsl closure에 marketfeed 부재·committed engine closure 테스트 green.

---

## 8. 수치 → Phase-0 / INSTANCE (숫자 하드코딩 0)

marketfeed는 **어떤 수치도 하드코딩하지 않는다**(RFC-005 §13 시리즈 규율·설계 #2 §8). 소비 수치 전부 주입:

| 수치 | 소유 | 현상태(register 실측) |
|---|---|---|
| Validity Window·freshness bound(as-of staleness·§4.2·§6) | ADR-002-018 §14 freshness bound | **다수 신설 대상**(register §8-1·설계 #2 §8)·provisional |
| snapshot max-age(`trustworthy_time.maximum_age_ms`·snapshot.py:65) | trustworthy-time bound | 주입·P0-1 미승인 |
| canonicalization_version(값⟺digest·value-view digest·§2.3·§3.2) | G2 canonicalization | `ev-l1-provisional-0`(canonical/__init__:35)·비프로덕션·**EV-L2+ 전 필요** |
| 밴드 stddev 배수 k·period·tick scale(저작자-상수·§5.3·§2.5) | config.bindings(저작자)·관측 mapping | D-E1 §3.2 (2)·저작자-상수·mapping provenance |
| provider/feed/instrument scope(§0.3) | brokercap INSTANCE(비규범·§12) | KIS 사실=Broker Capability Profile 초안 참조·트랙 d |

⇒ 소비 bound 다수 null/미신설 → **provisional 값 배선·산출 provisional**(§1.1). 승인 P0-1(운영자·Bounds-Approver).

---

## 9. Phase-0 / not-slice 체크리스트 (닫지 않음·후속 게이트)

**본 계약이 실현 지침 제공(D-E2)**: 값-싣는 표면(형=dsl·생산=marketfeed)·env-조립 seam+서명 append·per-bar
distinctness·지표 lineage 계약·property 타깃(저작 증거)·resolver slot 충족.

**닫지 않음(명시 이연·후속)**:
1. **정식 EV-L2 PASS** — G2 canonicalization·P0-1 bounds·P0-3 독립 리뷰어 선결(§1.1·register §4:108·§6:132).
2. **실 Context Integrity Service 런타임**(관측 수집·조립·발행·설계 #2 §0.2) — 슬라이스는 소비만.
3. **실 market feed 전송·네트워크·brokercap INSTANCE**(§0.2·§6.5) — D-E4/상류.
4. **히스토리 데이터 소스·백테스트 fill·cost-realism·LookaheadGuard 런타임 강제**(§5.4) — D-E3.
5. **soft-evidence vs determining 분류·강제**(RFC-003 §10·설계 #2 §6.4) — 결정/승인 레이어.
6. **완전 side-channel/look-ahead 강제·env-주입 재검증**(dishonest producer·신뢰 seam) — 상류 정직·§2.3·§4.3·§5.4.
7. **freshness/validity-window bound 신설·승인**(§8·register §8-1·P0-1).
8. **fault-injection 시나리오**(source reset/gap/rollback·설계 #2 §7 CII-EV-002 EV-L2) — 접합 위치만 표기.

---

## 10. 명명 결정 + 리뷰어 공격 지점

### 10.1 명명 `tos.marketfeed` (운영자 판단 지점·주의)

- **선정**: `tos.marketfeed` — 시장 데이터의 Critical Input 값을 **생산/검증**하는 owning 패키지(env-값 형은 dsl·
  §2.2). negative-grep 충돌 0·미예약(§0.5). ⚠ **명명 주의**: "feed"가 네트워크 전송 런타임을 암시할 수 있으나
  본 패키지는 pure·비전송 값 생산/검증이다(§0.3·§7.1) — 실 feed(전송)는 D-E4/상류 주입. docstring·__init__에
  축소 의미 봉인. runner-up: `tos.marketvalue`·`tos.contextvalue`(전송 오해 없음이나 "값 표면" 명시 약함). **운영자
  확정 지점.**
- **register prefix 부재**: D-E1과 동일하게 ADR-EV register 행 없음(Part-2/3 RFC 실현·닫는 EV 0). 명명이 register
  CSV 배제 목록 soft load-bearing을 갖지 않음 — 순수 설계 선택.

### 10.2 리뷰어 공격 지점 (선제 반론)

1. **"capsule 무변경이라며 값을 어떻게 넣나 — 사실상 capsule 우회 side channel?"** — 반론: 값은 covered
   `payload_digest`에 발행 시점 바인딩(§2.3)되어 snapshot identity에 묶인다 — capsule covered 관측 뒤에 산다.
   side channel은 **digest-미커버 경로**(config·G10)이고, 본 설계는 그것을 covered 경로로 옮긴다. **단 env-주입
   지점은 재검증 안 하는 신뢰 seam**임을 정직 명기(§2.3 MAJOR-2b)·검출은 서명 append(§3.2).
2. **"build_environment/DecisionTickPayload 터치 = 계약 위반?"** — 인정+반론: capsule 계약 아니라 dsl/engine이며
   additive·하위호환·D-E1 명시 이연(§3.2(A)·records.py:157-163·core.py:93-98). **형=dsl(F1·MAJOR-1)로 engine→
   marketfeed 순환 회피**·engine allowlist 무변경. `evaluate_policy`·capsule 무변경. **오케스트레이터 sanction
   대상·터치 전모 공개가 조건**(§15 미결-1).
3. **"재현성 서명이 4번째 입력(값)을 안 담는다"**(v1.1 MAJOR-2 반영) — 해소: resolved_context 제공 시 `evaluate_resolved`(v1.2 에라타·별도 진입점)가
   value-view canonical digest를 `captured_external_value_refs`(determinism.py:78)에 append(§3.2) → 다른 값 집합→
   다른 서명→replay 검출. 검증은 발행 시점·env-주입은 신뢰 seam임을 정직 명기(§2.3·§4.3).
4. **"값 타입 float 투영이 decimal 정규화(설계 #2 §3.4)와 모순?"**(v1.1 MINOR-2 반영) — 해소: 순서비교 수치=정수
   tick-scale 우선(exact·플랫폼독립)·deterministic-float fallback·Decimal→구조 UNKNOWN(silent 강제 금지·§2.5).
5. **"distinctness가 producer 정직 의존 — over-claim?"** — 인정: §4.3 명시 — 발행 gate(as-of/payload_digest
   concrete)+property는 구조 보장하되 완전 강제는 상류·서명 검출. 하중=covered source_event_time(§4.1 MINOR-1).
6. **"지표를 상류로 밀면 D-E2가 뭘?"** — 반론: D-E2는 값이 §10-conformant 채널로 DSL에 도달하는 계약(env 형태·
   값⟺digest 바인딩·VALID gate·lineage 계약·서명)을 소유. estimator는 config/상류이나 그 표면화 계약이 D-E2이며,
   없으면 D-E3/D-E4가 §10 위반 seam에 배선(스파이크 §5-2).

---

## 11. 선제 defect-class 봉합 (전 시리즈 교훈 적용)

| defect class | 봉합 |
|---|---|
| **side channel/재라벨링**(RFC-004 §9:244·G10) | 값⟺covered digest 바인딩(§2.3)·값=capsule 소스·env-조립이 admitted snapshot 해소(§3) |
| **재현성 서명 과청구**(v1.1 MAJOR-2) | resolved_context digest 서명 append(§3.2)·env-주입 신뢰 seam 정직 명기(§2.3·§4.3) |
| **closure 역전/순환**(v1.1 MAJOR-1) | 형=dsl(F1)·engine→marketfeed·dsl→marketfeed edge 부재·순환 0 canary(§7.1·§7.2-13) |
| **음성 gate/극성 회귀**(#18/#22/#23) | VALID-only worst() 단일 gate(양성·§2.2·MINOR-4)·`!= INVALID` 금지·음극성 `is False`(§6)·canary(§7.2-4) |
| **UNKNOWN 무처리/permissive default**(RFC-008 §10) | 값 부재 → resolve_operand UNKNOWN → restrictive(§6·§7.2) |
| **∅ vacuous/과잉거부**(#17/#26 WDR) | explicit-empty(값 0) vs missing 구별(§6)·∅ field_evaluation→UNKNOWN floor(vacuous-VALID 봉인·§2.2) |
| **namespace 충돌/covered 덮어쓰기**(v1.1 MINOR-3) | VALUE_NAMESPACE disjointness·충돌 시 발행 거부(§3.2·§7.2-3) |
| **decimal→float 비결정**(v1.1 MINOR-2) | 정수 tick-scale 우선·Decimal 구조 UNKNOWN·silent 강제 금지(§2.5) |
| **phantom 인용** | anti-phantom §0.5·전 file:line 재실측(v1.1 재grep)·부재 negative-grep 병기 |
| **over-claim**(distinctness/look-ahead/env-검증) | producer 정직·신뢰 seam 경계 명시(§2.3·§4.3·§5.4)·구조 보장과 강제 구별 |
| **자기신고 fail-open**(#21/#24) | field_key↔field_evaluation VALID·값⟺digest·바인딩 무결 구조 파생(§2.4·§3.3) |
| **provisional over-realization**(EGRESS #22) | resolver 값 표면 발명 안 함·admitted snapshot 소비만(§3.3·core.py:93-98) |
| **DRY 위반** | env-조립 dsl 소유·evaluate 로직 엔진 중복 금지(§3.5 B) |
| **기존 계약 잠식** | capsule 모델 무변경 실측(§15)·형제 미접촉(§0.3)·dsl/engine additive만·sanction 미결 승격(§15) |

---

## 12. seam 지도 (REUSE / WIRING / NEW / 주입 + 소유권 분할)

### 12.1 REUSE (기구현·재저작 금지·자체 실측 file:line)

| seam | 심볼(file:line) |
|---|---|
| 관측·snapshot·field-state·lineage·field-eval | capsule: `Observation`/`AdmissionResult`(observation.py:148·25)·`CriticalInputSnapshot`(snapshot.py:96)·`FieldState`/`worst`/`restrictiveness`(field_state.py:24·70·45)·`TransformationLineage`(lineage.py:96)·`FieldEvaluation`(field_evaluation.py:47) — capsule/__init__:49-53 |
| admission/validity 술어 | capsule: `compute_admission`/`admitted_field_state`(predicates.py:182·239)·`aggregate_snapshot_validity`(:84) |
| DSL 스칼라·wildcard·env 항법·인터프리터(무변경) | dsl: `ScalarValue`(vocabulary.py:93)·`WILDCARD_TOKENS`(dsl/__init__:65)·`resolve_operand`(vocabulary.py:316)·`evaluate_policy`(:384)·`ADMISSIBLE_CONTEXT_SOURCES`(:88)·`build_environment`/`evaluate`/`captured_external_value_refs`(determinism.py:88·238·78) |
| digest 검증 | canonical: `EVL1ProvisionalCanonicalizer`/`EV_L1_PROVISIONAL_VERSION`(canonical/__init__:39·35) |
| as-of·freshness | time: `freshness_verdict`(:66)·`snapshot_age_admissible`(:71)·`SessionContext`/`HealthState`(:50·38) |
| 이벤트 payload·resolver slot | engine: `DecisionContextResolver`(core.py:86)·`DecisionTickPayload`(records.py:157)·`InstrumentKey`/`TimeAdmissionInputs`(records.py:93·125)·engine→dsl edge(records.py:28-33) |

### 12.2 WIRING (additive·기존 코드 최소 확장·dsl-타입·§15 sanction 대상)

- **dsl 신규 형**: `ContextValue`/`ContextValueView`(env-값 shape·§2.2·신규 dsl 모듈). dsl closure 무변경(capsule
  이미 포함·determinism.py:35).
- dsl `build_environment(capsule, config, *, resolved_context=None)` + **신규 public 진입점 `evaluate_resolved(…, resolved_context=None)`**(v1.2 에라타·기존 `evaluate` 5-파라미터 byte-identical 불변·공유 본체 `_evaluate`) —
  additive keyword-only·하위호환·서명에 view digest append(MAJOR-2a·determinism.py:297-303). `evaluate_policy` 무변경.
- engine `DecisionTickPayload.value_view: ContextValueView | None = None` — additive dsl-타입 필드(engine→dsl
  기존 edge). pipeline `run_decision_pipeline`이 `payload.value_view` 전달(pipeline.py:311). **engine allowlist
  무변경·순환 0.**

### 12.3 NEW (owning·negative-grep 부재 확정·§0.5)

`tos.marketfeed` 신규: (1) 값⟺digest 검증 술어·VALID-gate·env 투영·`ContextValueView` **생산자**(dsl 형을 채움·
`tos.marketfeed.value`)·(2) 구체 `DecisionContextResolver`(SnapshotRef→body 해소·`tos.marketfeed.resolver`).
전부 부재(`ls tos/src/tos/*marketfeed*` → 0·§0.5). **형 자체는 dsl에**(§2.2 F1).

### 12.4 주입 seam + forward seam (구현 시점 디스크 재실측·D-E1 §5.4 상속)

- **주입 snapshot store**(§3.3): D-E3=히스토리·D-E4/live=상류 발행 snapshot. 동일 resolver 계약·다른 주입(패리티).
- **raw-event 값 carrier preimage**(§2.3): canonical preimage 형태 D-E2 구현·G2 후 재실측(미결-3).
- **estimator/lineage producer**(§5.3): 상류 모델·D-E2 밖.

### 12.5 소유권 분할표

| 관심사 | D-E2(marketfeed) 소유 | 이연/타 소유 |
|---|---|---|
| env-값 형(shape) | — | **tos.dsl**(`ContextValueView`·F1·§2.2) |
| 값 생산·검증·값⟺digest 바인딩·VALID gate | **전부**(§2·§3.3) | — |
| env-조립·서명 append | 계약(형·값 공급) | **tos.dsl**(build_environment/evaluate·§3.2) |
| per-bar distinctness | 구조 corollary+발행 gate(§4) | producer 정직(완전 강제·상류) |
| 지표 lineage 계약 | admitted observation+lineage(§5) | estimator·window(config/상류)·D-E3 LookaheadGuard 강제 |
| snapshot 조립·발행 런타임 | — | Context Integrity Service(설계 #2 §0.2) |
| market feed 전송·brokercap·network | — | D-E4/상류 |
| capsule 모델 | **무변경**(§0.2·§15) | capsule 계약(설계 #2·비준·구현 완료) |

---

## 13. Self-Check (task 요구·리뷰어 델타 재검증 전 자가 확인)

- [x] **닫는 EV 0·provisional 최상위 선언** — 배너·§1.1.
- [x] **값 표면 형태 + 소유권(v1.1 F1)** — 형=dsl `ContextValueView`·생산/검증=marketfeed·값⟺digest·VALID gate·
      capsule 무변경(§2)·engine 순환 회피.
- [x] **env-조립 seam(§3·핵심 B)** — governed scalar leaf·additive·서명 append(MAJOR-2)·evaluate_policy 무변경·대안 6 기각.
- [x] **per-bar distinctness(§4·핵심 C)** — covered source_event_time 하중(MINOR-1)·발행 gate·G13/G7 해소·정직 경계.
- [x] **지표 파이프라인(§5·핵심 D)** — 상류 계산·lineage REUSE·look-ahead 경계·estimator 미구현.
- [x] **RFC-004 §9 attributed-provenance 위반 0** — 값⟺covered digest·no side channel·신뢰 seam 정직(§2.3·§10.2-1).
- [x] **재현성 서명 충분성(v1.1 MAJOR-2)** — resolved_context digest 서명 append·env-주입 신뢰 seam 명기.
- [x] **순환 0·committed 테스트 무파괴(v1.1 MAJOR-1)** — 형=dsl·edge 부재 negative-grep·allowlist 무변경(§7.1·§15).
- [x] **anti-phantom(존재/부재 양방향 grep·file:line·v1.1 재grep)** — §0.5·§16.
- [x] **음극성 `is False`·양성 gate·구조 파생·∅ 양방향·UNKNOWN-restrictive** — §6·§11.
- [x] **형제 잠식 금지·KIS 사실 tos-spec 금지** — §0.3·§8.
- [x] **기존 capsule 계약 충돌 실측** — **capsule 모델 변경 0**(§15)·미결 승격 없음.
- [ ] **미해결(운영자/후속·§15)**: dsl/engine additive 터치 sanction(터치 전모 공개)·명명 확정·bound 신설·
      raw-payload preimage(G2 후)·resolver store 주입 상세.

---

## 14. 요약

**tos.marketfeed(D-E2)는 수직 슬라이스 #1의 데이터 공급 레이어다** — 시장 수치가 재라벨링(§10 위반)이 아니라
admitted Critical Input 채널로 DSL에 도달하는 값 표면 계약. 확정(v1.1): (1) env-값 **형은 dsl 소유**
(`ContextValueView`·MAJOR-1 F1로 engine 순환 회피)·**생산/검증은 marketfeed 소유**, 각 값을 covered
`payload_digest`에 발행 시점 바인딩해 side channel·distinctness 붕괴를 동시 봉인하되 **env-주입 지점은 신뢰 seam**
임을 정직 명기(§2), (2) 값은 `env["capsule"]` 밑 governed scalar leaf로만 도달하며 통로는 `build_environment`
additive 확장(dsl-타입·신규 진입점 `evaluate_resolved`·v1.2 에라타)·resolved_context는 서명에 view digest **append**(재현성 4입력·MAJOR-2)이고 `evaluate_
policy`·**capsule 모델 무변경**(§3), (3) per-bar distinctness는 값을 covered `source_event_time`으로 옮긴 구조
corollary(G13 해소·§4), (4) 밴드 등 파생 지표는 상류 계산·기구현 `TransformationLineage`(REUSE)·look-ahead 경계
명시(§5). D-E1 §12-1 `DecisionContextResolver` slot을 채운다.

**정직 스코프**: 닫는 EV 0. 값 표면은 모델+property 저작이지 실 Context Integrity 런타임 아님 — G2·P0-1·P0-3
미결·distinctness/look-ahead/env-검증 완전 강제는 producer 정직/서명 검출/D-E3 소관(§1.1·§2.3·§4.3·§5.4).

**기존 capsule 계약 충돌**: **없음**(capsule 모델 변경 0). dsl/engine additive 터치는 capsule 계약이 아니며
형=dsl(F1)로 순환 0·allowlist 무변경, D-E1이 명시 이연했으나 ratified/committed 패키지라 오케스트레이터 sanction
필요(§15 미결-1·터치 전모 공개가 조건).

---

## 15. 기존 계약 충돌 유무 + 미결 목록 (task 필수 보고)

### 15.1 capsule 계약 충돌 — **없음 (실측 확인)**

본 설계는 `tos.capsule`의 어떤 모델 필드도 추가/변경/제거하지 않는다. 값 표면은 전부 greenfield(marketfeed
생산/검증 + dsl 형·§2)이고, 값은 **이미 존재하는** covered 필드(`observation.raw.payload_digest` observation.py:74·
`observation.time.source_event_time` :85·`observations ∈ _COVERED_FIELDS` snapshot.py:131)에 **바인딩**될 뿐이다.
distinctness도 `_REQUIRED_COVERED` 변경 없이 marketfeed 발행 gate로 달성(§4.2). ⇒ **capsule 불가피 변경 항목 0.**

### 15.2 미결 목록 (오케스트레이터/운영자 소관)

1. **[미결-1·주된·sanction 조건] dsl/engine additive 터치 — 터치 전모 공개(v1.1 sanction 조건 충족)**:
   - **① dsl**: (a) 값-carrier **형** 모듈 신설 — `ContextValue`/`ContextValueView`(§2.2·필드 field_key/value/
     as_of/payload_digest/observation_ref + snapshot 바인딩/canonical_digest/canonicalization_version). dsl→capsule
     기존 edge(determinism.py:35)로 `FieldState` 참조 가능·**dsl closure 무변경**. (b) `build_environment(capsule,
     config, *, resolved_context=None)`(keyword-only additive·determinism.py:93)·**신규 public 진입점
     `evaluate_resolved(…, resolved_context=None)`(determinism.py:362)**·하위호환(None→오늘과 바이트 동일).
     **⚠ v1.2 정정**: v1.1 원안은 `evaluate` 자체에 6번째 param을 얹었으나 committed 시그니처 canary
     (`test_dsl_determinism.py:136-146`)와 충돌 → 기존 `evaluate`(determinism.py:319)는 **5-파라미터·byte-identical
     유지**·실체는 별도 진입점 `evaluate_resolved`·공유 본체 `_evaluate`(determinism.py:277). (c) **서명 조립 변경**
     (MAJOR-2c): resolved_context 제공 시 `captured_external_value_refs`(determinism.py:78)에
     `resolved_context.canonical_digest` append(`_evaluate`:297-303). `evaluate_policy`(호출부 `_evaluate`·
     determinism.py:293)·인터프리터 **무변경**.
   - **② engine**: `DecisionTickPayload`에 `value_view: ContextValueView | None = None`(dsl-타입 optional 필드·
     D-E1 records.py:157-163 자기증언 slot 충족). `run_decision_pipeline`이 `payload.value_view`를 `evaluate`에
     전달(pipeline.py:311). **engine→dsl 기존 edge**(records.py:28-33)·**engine allowlist(14패키지) 무변경**·
     **engine closure에 marketfeed 미유입**.
   - **③ 순환 0·committed 테스트 파괴(v1.2 정직 정정)**: `dsl→marketfeed`·`engine→marketfeed` edge **부재**
     (negative-grep·§0.5-6) → `engine→marketfeed→engine`·`dsl→marketfeed→dsl` 순환 없음. committed
     `test_engine_import_closure.py` subset(:310-315)·declared-edge(:318-327) 둘 다 green 유지(marketfeed ∉ engine
     closure). marketfeed만 dsl·engine을 소비(생산 대상). **⚠ v1.2 정직 정정**: v1.1의 "committed 테스트 파괴 0"
     검증 범위는 **engine closure allowlist만 실측**했고 **dsl 시그니처 canary(`test_dsl_determinism.py:136-146` —
     `evaluate` 5-파라미터 잠금)를 놓쳤다**(저작·리뷰·델타 재검증 3중 누락). 그 canary는 `evaluate`에 6번째 param을
     얹으면 깨진다 → 구현이 `evaluate_resolved` 별도 진입점으로 착지(경로 a·§16.1). **신규 교훈: sanction 전제
     "committed 테스트 파괴 0"은 터치 표면의 모든 committed canary(시그니처·closure·drift anchor)를 전수 grep해야
     성립 — closure allowlist만으로 부족**(neutered-canary 결함 클래스 회피).
   - **판정**: 셋 다 capsule 계약 아님·additive·하위호환. **오케스트레이터 sanction 권고**(전제 (a) 서명 충분성이
     v1.1에서 참이 됨 — MAJOR-2 반영). 은폐-변경 아님을 이 공개로 성립.
2. **[미결-2]** 명명 `tos.marketfeed` 확정(§10.1). runner-up `tos.marketvalue`/`tos.contextvalue`. 운영자.
3. **[미결-3]** raw-payload preimage 형태(값⟺payload_digest·§2.3) — G2 프로덕션 canonicalization 승인 후 재실측.
4. **[미결-4]** resolver snapshot store 주입 계약(§3.3) — 구현 시점 재실측.
5. **[미결-5]** freshness/validity-window bound 신설·승인(§8·register §8-1·P0-1).

### 15.3 입력물과 어긋난 재실측 발견

- **재실측 발견 1(D-E1 §12-1 정합)**: D-E1이 `DecisionContextResolver`(core.py:86-105)·`EventSource`(core.py:
  108-120)를 Protocol slot으로 구현·export하고 `DecisionTickPayload` docstring(records.py:161-163)이 값 표면을
  D-E2 이연으로 명문화. 본 설계는 slot의 정확한 충족·D-E1 어긋남 0.
- **재실측 발견 2(ADR §9 관측 바인딩에 값 부재)**: ADR §9:249-261 관측 바인딩 열거에 관측 수치 값 자체가 없다
  (provenance/digest/metadata만·:256·259). ADR 모델은 provenance 층·값은 covered raw payload 뒤(§2.1 근거·스파이크
  G8 정합).
- **재실측 발견 3(resolve_operand list 인덱싱 불가)**: vocabulary.py:334 dict 전용. 값은 field_key-키잉 평면 dict로만
  도달(§3.1·§3.2)·field_key governance(§2.4) 근거.
- **재실측 발견 4(v1.1 MAJOR-1 근거·리뷰어 실증 확인)**: committed `tos/tests/engine/test_engine_import_closure.
  py`의 `_ALLOWED_TOS_PACKAGES`(:59-76)는 14패키지·**marketfeed 부재**이고, subset(:310-315)+declared-edge
  (:318-327) 테스트가 marketfeed를 engine closure에 넣으면(payload가 marketfeed 타입이면) FAIL. **engine→dsl**
  (records.py:28-33)·**dsl→capsule**(determinism.py:35) edge는 기존 존재 → F1(형=dsl)이 무순환 유일해. v1.0의
  "value_view: AdmittedValueView(marketfeed 타입)" 판정을 실측이 반증 — v1.1에서 형=dsl로 재배정.

---

## 16. 개정 로그 (v1.1 — 2026-07-29 독립 비평 리뷰 REVISE 반영)

**평결**: REVISE(CRITICAL 0·MAJOR 2·MINOR 4·Gap 1·NIT 1). 인용 52/52 정확·phantom 0·capsule 무변경 실측 성립·
접근법(값을 covered snapshot으로 옮겨 side-channel·distinctness 동시 봉인) 리뷰 지지. finding별 처분(전건 반영·
오케스트레이터 재정 병기):

| finding | 처분 | 변경 위치(§) |
|---|---|---|
| **MAJOR-1** `DecisionTickPayload.value_view: AdmittedValueView`(marketfeed 타입)가 engine 순환·allowlist 위반 | 적용(처방 F1·타입 소유권 재배정) | 배너·§0.1(2)·§0.3·§0.4 A/B·§2.2(형=dsl `ContextValueView`·생산/검증=marketfeed)·§3.2·§3.4·§3.5(F)·§7.1·§7.2-13·§12.2/12.3/12.5·§15.2 ①②③·§15.3 발견4 |
| **MAJOR-2** 재현성 서명이 4번째 결정입력(resolved values) 미커버 → 부정직 resolver 같은 서명·다른 outcome | 적용((a)서명 digest append·(b)신뢰 seam 정직·(c)터치 명시) | §2.2(canonical_digest 필드)·§2.3(신뢰 seam)·§3.2(3b 서명 append)·§4.3(통합)·§7.2-8·§10.2-3·§11·§15.2 ①(c)·Gap-1 통합 |
| **MINOR-1** distinctness 하중을 payload_digest→covered `source_event_time`으로 | 적용 | §0.4 C·§4.1(사슬 재서술)·§4.2·§2.2(as_of=distinctness 하중)·payload_digest=provenance 분리 |
| **MINOR-2** decimal→float 결정성/Decimal fail-closed | 적용(정수 tick-scale 우선·Decimal 구조 UNKNOWN·silent 강제 금지) | §2.5·§7.2-12·§10.2-4·§11 |
| **MINOR-3** VALUE_NAMESPACE ↔ capsule dump 키 disjointness | 적용(예약 키·충돌 발행 거부·property) | §3.2(1)·§7.2-3·§11 |
| **MINOR-4** VALID-gate 3상태 worst()==VALID 단일 정의·∅→UNKNOWN floor | 적용 | §2.2(단일 gate 정의)·§6·§7.2-4·§11 |
| **Gap-1** 값⟺digest 신뢰 seam(env-검증 부재) | 적용(MAJOR-2b 통합) | §2.3·§4.3·§9-6·§11 |
| **NIT-1** "evaluate_policy(:268)"→"evaluate_policy 호출부(determinism.py:268)" | 적용 | §3.2(3b)·§15.2 ①(c) |

**델타 요약(리뷰어 재검증용·변경 § 목록)**: 배너(v1.1 개정 요지 신설)·§0.1(2)·§0.3(closure 재배정·순환 0)·§0.4
(결정 A/B 재서술)·§0.5(negative-grep 6·edge 존재 확인 추가)·§1.1·§1.2(RFC-008 §9 302-306 서명 추가)·§1.3·**§2.2
(형=dsl·생산=marketfeed·VALID-gate 단일 정의 — 최대 변경)**·§2.3(신뢰 seam)·§2.4·§2.5(정수 tick-scale)·§2.6(B/F
기각)·**§3.2(F1·서명 append·namespace disjoint — 최대 변경)**·§3.3·§3.4(순환 0)·§3.5(F 신설)·§4.1(source_event_
time 하중)·§4.2·§4.3(신뢰 seam 통합)·§4.4·§6(worst gate)·§7.1(순환 canary)·§7.2(타깃 8·12·13 신설·재배치)·§8·
§9-6·§10.1·§10.2(공격점 3 신설)·§11(defect 3 신설)·§12.1/12.2/12.3/12.5(소유권 재배정)·§13·§14·**§15.2 미결-1
(터치 전모 공개 — sanction 조건)**·§15.3(발견4 신설)·§16(본 로그). **미변경 핵심**: 접근법(covered snapshot 이전)·
capsule 무변경·per-bar distinctness 구조 corollary·지표 상류 lineage·provisional 닫는 EV 0.

**재실측 인용(쓰기 전 재grep·anti-phantom §0.5)**: `_ALLOWED_TOS_PACKAGES` 14패키지·marketfeed 부재
(test_engine_import_closure.py:59-76)·subset(:310-315)·declared-edge(:318-327)·engine→dsl(records.py:28-33)·
dsl→capsule(determinism.py:35)·`captured_external_value_refs: tuple[str,...]`(determinism.py:78)·`_captured_value_
refs` snapshot digest만(:118-119)·`worst` empty→VALID+UNKNOWN floor(field_state.py:70-87·73-75)·`admitted_field_
state`(predicates.py:239-253)·capsule top-level 17필드(capsule.py:225-245)·`resolve_operand` dict-전용
(vocabulary.py:334)·순서비교 int/float(vocabulary.py:366-368)·observation `payload_digest`/`source_event_time`
(observation.py:74·85)·`observations ∈ _COVERED_FIELDS`(snapshot.py:131). **전건 실측 일치.**

---

### 16.1 에라타 v1.2 (2026-07-29 — 구현 단계 발견·오케스트레이터 경로 (a) 재정)

**발견 경위(구현자 실측)**: v1.1 §3.2가 명세한 "`evaluate`에 6번째 keyword-only 파라미터 `resolved_context` 추가" 시그니처 확장이 committed
`tos/tests/dsl/test_dsl_determinism.py:136-146`(`test_evaluate_signature_exposes_no_ambient_source` —
`inspect.signature(evaluate).parameters`를 정확히 5개 {strategy, capsule, config, scheme,
enforcement_mechanism_version}로 잠금)와 충돌. keyword-only 6번째 파라미터도 이 canary를 깬다.

**재정(오케스트레이터·경로 (a) 채택·WDR #26 MAJOR-2 선례 "구현이 더 충실할 때는 코드 약화가 아닌 에라타가
정답")**: canary 개정(경로 b)은 기각 — canary는 만들어진 목적(비준된 표면의 무성 시그니처 드리프트 검출) 그대로
작동했다(neutered-canary 회피). 설계를 구현에 맞춰 정정.

**구현 착지 위치**: 실체 = **신규 public 진입점 `evaluate_resolved(…, resolved_context=None)`(determinism.py:362)**·
기존 `evaluate`(determinism.py:319)는 **5-파라미터·byte-identical 유지**(canary intact)·공유 본체
`_evaluate`(determinism.py:277)가 env merge(build_environment 호출:292)·서명 append(:297-303) 수행.
`build_environment`(:93, resolved_context 보유)·`evaluate_policy`(호출부 `_evaluate`:293)·capsule·F1·값⟺digest
신뢰 seam은 **전부 v1.1 설계대로**. dsl export `ContextValue`/`ContextValueView`/`evaluate_resolved`
(dsl/__init__:75-76·85·195) 착지 확인.

| finding | 처분 | 변경 위치(§) |
|---|---|---|
| **에라타-1** `evaluate`에 6번째 param `resolved_context` 추가 시그니처 확장 ↔ committed 5-파라미터 canary 충돌 | 경로 (a): `evaluate_resolved` 별도 public 진입점으로 정정·`evaluate` byte-identical 유지·canary intact | 배너 v1.2 블록·§0.1(3)·§0.4 B·§3.2(3)·§7.2-8/9·§10.2-3·§12.2·§14·§15.2①(b)(c)·본 §16.1 |
| **에라타-2(교훈)** sanction 전제 "committed 테스트 파괴 0"이 dsl 시그니처 canary 미검증(engine closure allowlist만 실측) | §15.2③ 정직 정정 + 신규 교훈 명문화 | §15.2③·배너 v1.2 블록 |

**신규 defect class(교훈)**: **neutered-canary 회피 + sanction 전제 canary 전수-grep**. sanction 전제 "committed
테스트 파괴 0"은 터치 표면의 **모든** committed canary(시그니처·closure·drift anchor)를 전수 grep해야 성립한다 —
closure allowlist만으로 부족. v1.1은 engine closure만 보고 dsl 시그니처 canary를 놓쳤다(저작·리뷰·델타 재검증 3중
누락). canary를 깨는 실현이 아니라 canary를 존중하는 실현(별도 진입점)이 정답이며, 구현자가 이를 실행했다.

**정정된 인용 + determinism.py 행 이동 지도(v1.1 → v1.2·구현 refactor)**: 구현자가 `tos.dsl.context_value` import
(determinism.py:41)·VALUE_NAMESPACE merge(:137-143)·공유 본체 `_evaluate`(:277)·`evaluate_resolved`(:362)를 추가해
determinism.py 다수 행이 하향 이동했다. **§1-§3의 determinism.py 인용은 저작 시점(pre-implementation) 기준값**이며,
현행 disk 앵커 지도: `captured_external_value_refs`(필드) :78→**83** · `config.bindings` :60→**65** · `config_version`
:59→**64** · `build_environment`(def) :88→**93** · build_environment return/`model_dump` :105-108/:106→**:144-147** ·
`_captured_value_refs`(def) :118-119→**150** · `evaluate`(def) :238→**319** · `evaluate_policy` 호출 :268→**293** ·
서명 append **:297-303**(공유 `_evaluate`) · `_decision_to_outcome`/`RecordedInputSignature` :269-283→하향. **불변
(재확인)**: `from tos.capsule.capsule import DecisionContextCapsule` **:35**(dsl→capsule edge)·captured-not-called
docstring **:11-15**는 이동 없음. **정본 post-impl 앵커** = 본 §16.1·§3.2(3)·§15.2①(b)(c)의 값(:319/:362/:277/:293/
:297-303/:93/:83). 리뷰어 델타 재검증은 이 지도를 기준으로 §1-§3 pre-impl 인용의 행 이동을 phantom이 아닌
refactor-이동으로 판정할 것.

**재실측 인용(v1.2·쓰기 전 재grep·anti-phantom §0.5)**: `def test_evaluate_signature_exposes_no_ambient_source`
(test_dsl_determinism.py:136·`assert params == {5개}`:139-146)·`def evaluate`(determinism.py:319, 5-param)·
`def evaluate_resolved`(:362)·`def _evaluate`(:277)·`def build_environment`(:93·resolved_context:97)·
`evaluate_policy` 호출(:293)·서명 append(:297-303)·dsl export(dsl/__init__:75-76·85·195). **전건 실측 일치.**
