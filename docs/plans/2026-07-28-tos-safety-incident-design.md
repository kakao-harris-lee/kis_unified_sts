# 설계 문서 #28 — Safety Incident Declaration / Containment / Controlled Shutdown / Closure Governance 계약 (ADR-002-027, EV-L1) (2026-07-28, v1.2)

> **v1.2 에라타(2026-07-28, 적대적 코드 리뷰 ACCEPT-WITH-FIXES 후속 — 구현이 계약보다 충실한 4곳 정직화·#26 WDR
> MAJOR-2 "코드 약화 아닌 에라타" 선례)**: **(E1)** §2.4 `ActiveSetMember.resolved`·`OngoingSafetyObligation.
> resolved`의 "음극성" 표기 삭제 → **양극성**(§5.2 conjunct 3 operative 문면 `resolved is not True ⇒ unresolved`가
> 우선·ADR §10:314 unknown⇒미해결 지지·음극성이면 "미해결=clear" 의미 역전 — 계약 내부 모순의 §2.4 측이 오류,
> 코드 리뷰 FAITHFUL 확정). **(E2)** §4.4 malformed-∅ 검출 소유 정정 — `dominating_open_incident_present`는
> 1-인자(active_set)라 `applicable`을 볼 수 없음; `members=() ∧ applicable≠∅` 거부는 `scope_exact_combined_no_
> favorable_subset`(§5.2 conjunct 1) 소유(구현 실측 거부 확인·리뷰 MINOR-1). **(E3)** §2.4 carrier 공백 소급 등재
> — §6.5/§6.6/§6.3/§6b 술어 시그니처의 담지 모델 4종(`IncidentUnknownState`·`BrokerFinalityTokens`·
> `RecoveryRevivalInputs`·`ExternalActivityClaim`)·§6.4 carrier 필드 3종(`protection_blindly_cancelled`[§14:388]·
> `cancellation_arbiter_approved`[§12 step 6]·`exposure_reported_safely_closed`[§14:397])·`IncidentDependencyClosure.
> dependency_closure_complete` 필드(§4.3 표 소급 — 구조 파생과 AND로만 소비·플래그 단독 통과 불가)를 계약 표면으로
> 등재(§7.2(a) field-closure 성립 필요조건·코드 리뷰 FAITHFUL 확정). **(E4)** 극성 canary 범위 정밀화 — `is not
> True` 금지는 **음극성 등록 필드 소비**에 한함(양극성 deny 정규화 `is not True`는 §4.3 문면대로 합법); AST 검출은
> 직접형+등가 표기(`!= True`·`not (x is True)`·`not in (True,)` 계열)이며 중간 변수·헬퍼 경유 미검출은 **비전수
> 정직 명기**(#25 wildcard denylist 교훈 동형). 코드 리뷰 최종: **ACCEPT-WITH-FIXES**(CRITICAL 0·MAJOR 3[hag
> verdict 소비 배선·AMBIGUOUS 양성-증명 반전·보수 분기 커버]·MINOR 4) → 전건 처방 적용·뮤테이션 26/26 KILLED·
> sir 391 tests.

> **v1.1 개정(2026-07-28, 독립 비평 REVISE 반영 — CRITICAL 2·MAJOR 8·MINOR 9·NIT 3)**: 아키텍처 4판정
> (greenfield·sibling edge 0·rcl edge 0·PROMOTE 0)은 리뷰 지지로 **유지**. 핵심 정정: **(C1)** §0.5 anti-phantom
> 자체 실패 교정 — grep 패턴이 `-i`/`INCIDENT`/`incident generation`을 누락해 committed 소비 3건을 놓쳤다(`wdr/
> predicates.py:14`·`wdr/state.py:48-49`이 "-027 incident generation" 주입 소비를 자기증언·`spg/vocabulary.py:215-216`
> `SAFETY_INCIDENT_POLICY`/`ACTIVE_SAFETY_INCIDENT_SET` governed-artifact-kind 토큰·`cur/vocabulary.py:143`
> `DimensionKey.INCIDENT`가 mandated floor 소속). §3.5 cur 행 반증 정정(cur는 `DimensionKey.INCIDENT`를 이미
> 보유 — SIR은 그 차원의 *값*을 생산·완전성 판정은 cur 소유·forward seam **보강**)·`NO_INCIDENT` phantom 삭제
> (grep 빈 결과·ADR §16:429는 금지 조항으로만 인용). **(C2)** 노른자 2·forward-seam 술어 전 입력 수용 확장
> (#21 NT C1·#24 PTF C1 동형 재발 방지)·`ActiveSafetyIncidentSet` per-member 구조(`ActiveSetMember`) 도입으로
> 자기신고→구조 파생. **(M1–M8)** protective 필드 `:202`/docstring `:181-183` 분리·phantom quote→§1 line 23/29·
> SIR-INV anchor 16곳 `§6 SIR-INV-0NN`으로 정정(§16=Currentness·§23=Failure Matrix 예약)·22차원 legal-portfolio
> 복원·`principals_collapsed` hag 주입 verdict 전환(M5·리뷰어 (a))·9-token 강도 전순서 철회(M7)·§4.4 ∅ 재도출
> (M8·A안·§5.5:126 "applicable to" + §16:423-424 근거·WDR 792-793 선례). **(MINOR)** `_NonTruthyStrEnum` 10패키지
> (ioc 제거·wdr 추가)·`AllFalse*Authority` 16파일·29패키지 정정·극성 표 폐포·field skeleton 5종 추가·line 정오.
> upgrade 조건 5항(§7.2 field-closure + anchor-resolution property 신설 포함) 충족.
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며 스펙 텍스트
> (RFC/ADR/템플릿/프로파일/register)를 **변경하지 않는다.** 본 문서는 ADR-002-027(Safety Incident Declaration,
> Containment, Controlled Shutdown, and Closure Governance — "SIR")을 그린필드 `tos/src/tos/sir/` 신규 패키지의
> Phase 1(EV-L1) **순수·비전송 predicate substrate**로 실현하는 계약이다. 코드·git 커밋은 본 문서 범위 밖이다
> (비준은 오케스트레이터 소관).
>
> **비준 기록**: 2026-07-27 운영자 위임 자동 비준 대상(v1.0 초안; 2026-07-25 표준지시 — "남은 ADR 구현 자동 비준
> 승인으로 계속 진행. 끝까지 진행"). 게이트: 독립 비평 리뷰 통과 + upgrade 조건 충족을 오케스트레이터가 검증 후
> "운영자 위임 자동 비준(2026-07-25 지시)"으로 기록·집행. 품질 파이프라인[저작→1차 심사→독립 비평→개정→구현→
> 적대적 코드 리뷰→게이트] 전량 유지. 본 문서는 GOV-001의 세 거버넌스 행위(비준 / ADR acceptance / live
> authorization) 중 어느 것도 수행하지 않으며 어떤 SIR-EV/SIR-AC/acceptance도 선언하지 않는다.
>
> **패치 반영**: `PATCH-ADR-002-027-v0.2-Single-Operator-Re-Arm-Recognition.md`는 **MERGED**(patch line 1
> "MERGED — see ARCHITECTURE-GATE-STATUS §3.4")되어 ADR 원문이 이미 v0.2다(SIR-INV-016·§7·§20 item 10에
> Governed Single-Operator Re-Arm Variant 인정 반영·ADR line 218/242/501·§30 Review History line 767–772). `patches/`
> 디렉토리 전수 확인 결과 **-027을 타깃하는 패치는 이 v0.2 1건뿐**이다(`ADR-002-028-Patch-0027.md`는 파일명이
> "Patch-0027"이나 **타깃은 ADR-002-028**로 -027 무관·실측). 본 계약은 v0.2 반영본을 기준으로 한다.
>
> **broker-agnostic**(project memory `tos-spec-broker-agnostic`): incident·signal·scope·containment·shutdown·closure·
> external-activity 어휘·술어는 전부 broker-agnostic이다. broker/order/fill/exposure state·credential/route·external
> broker activity는 §13·§15에서 **capability class**로만 표현하며 KIS 등 특정 broker 고유명사는 등장하지 않는다
> (브로커 능력은 brokercap 주입·§3.5).
>
> **선행 문서(의존)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   모든 모델은 설계 #1 §2.4 레이아웃에 놓이고 §3.2 허용목록 안에서만 의존한다(§0.3).
> - [설계 #26 — Safety-Waiver / Deviation / Residual-Risk Governance 계약 (WDR, v1.2)](2026-07-27-tos-safety-waiver-design.md)
>   — **거버넌스 content-owner 형식 모범**. SIR은 WDR과 동형의 greenfield content owner(§0.4b)이며 5-artifact
>   digest-bound + all-false authority + 극성 규율 + reconcile + anchor-drift 형식을 상속한다.
> - [설계 #27 — Failure-Domain Isolation 계약 (FD, v1.2)](2026-07-27-tos-failure-domain-design.md) — **§0.5
>   anti-phantom 규율 원천**(부재 주장/존재 주장 양방향 grep)·소유권 분할표 형식.
> - **형제 소유 경계의 규범 원천**(재저작 금지, §3.5): sbr(ADR-002-017)·hag(ADR-002-015)·spg(ADR-002-014)·
>   evidence(ADR-002-016)·liveauth(ADR-002-007)·rcl(ADR-002-002/012)·egress(ADR-002-013)·cur(ADR-002-024)·
>   authority(ADR-002-003)·protective(ADR-002-001)·iap(ADR-002-023)·time(ADR-002-008)·rlp(ADR-002-025)·wdr(ADR-002-026)·
>   afg(ADR-002-022)·orthostate·recon·brokercap. 인용은 전부 **committed 코드 실측 signature+라인**이다.
>
> **규범 원천**: `ADR-002-027` (Status: Proposed, Version 0.2). ADR §29 line 757 "Authorship … does not satisfy
> these gates. This ADR authorizes architecture and implementation planning only. It does not authorize acceptance,
> restricted-live or production operation, broker transmission, incident closure, scope restoration, or automatic
> re-arm." 본 계약도 마찬가지다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. **패키지 명명** `tos.sir`(register prefix `SIR` 소문자 1:1·terse-lowercase 관행·§0.4a). **naming은 WDR과
   동형의 약한 soft load-bearing**: `tos.sir`는 세 firewall allowlist-배제 목록(`wdr/__init__.py:47`·
   `rlp/__init__.py:39`·`cur/__init__.py:51`)이 "미래 형제"로 열거(grep 실측·§0.4a). runner-up `tos.incident`
   (기각·§10.1).
2. **핵심 아키텍처 판정 — SIR = greenfield incident-governance content owner·피이연 없음·단 forward concept-seam
   1건 committed(본 문서 최대 판정·§0.4b).** WDR(#26)와 동형의 순수 생산자이되 **WDR과의 결정적 차이**: SIR이
   생산할 "dominating open incident restriction" 개념이 **이미 committed 코드에 주입 소비되고 있다** —
   `protective/predicates.py:395`(`return inputs.dominating_halt_or_incident is False`)·`sbr/predicates.py:731`
   (`if dominating_halt_or_incident is not False`)이 `dominating_halt_or_incident: bool | None`을 "ADR-002-027 /
   015 injected verdict"로 소비한다(grep 실측·§0.4b·§3.6). 그러나 이 소비는 **익명 bool 주입**이며 `tos.sir`
   타입을 이연받지 않는다 — 따라서 SIR은 RLP식 피이연자가 아니라 **greenfield 생산자**이고 **sibling edge = 0**이다.
3. **EV 3분류(행별 정직)** — **core(L1 슬라이스) 3행 {SIR-EV-001 Restrictive Detection and Declaration
   `EV-L1/3+Security`·002 Exact Scope and Combined Incidents `EV-L1/3`·009 Evidence, Communication, and Status
   Honesty `EV-L1/3`}**(register 실측 md line 348–356 / csv line 317–325·survey §4.3) / **predicate-only(≥ L2)
   6행 {003 `EV-L2/3+Security`·005 `EV-L2/3+Broker`·006 `EV-L2/3+Broker`·010 `EV-L2/3+Security`·011
   `EV-L2/3+Broker+Security`·012 `EV-L2/3+Security`}** / **not-Phase-1(하한 L3) 3행 {004 `EV-L3+Broker+Security`·
   007 `EV-L3+Security`·008 `EV-L3+Security`}**. **닫는 SIR-EV = 0건**(§1). "EV-L1-complete 주장 금지".
   **WDR/거버넌스 6부작 중 하한 L3 행이 3건으로 최다**(survey line 303–304) — register 표면 자체가 통합 시스템
   결함 시험 쪽으로 기울어 있다.
4. **INV 밀도 > L1 행 판정 — 닫지 않는 predicate substrate 비중이 본 문서 최대(§0.4c·§6).** SIR-INV-001..016
   16건이 L1 3행에 대해 **불변식 밀도가 높다**(survey line 305–306 "닫지 않는 predicate substrate 비중이 클 것").
   16 INV 중 **L1 3행이 닫는 데 직접 기여하는 것은 001·002·003·004·014 + §18:472 honesty 5~6건뿐**이고 나머지
   10건(005·006·007·008·009·010·011·012·013·015·016)은 **≥ L2/L3 substrate로 저작하되 어떤 SIR-EV도 닫지 않는다**.
   이 큰 predicate-only substrate가 본 계약의 규모 절반 이상을 차지한다(§6).
5. **중심 L1 술어(§5·3 노른자)** — `restrictive_declaration_non_authorizing`(SIR-EV-001·노른자 1·§8 restrictive
   declaration·SIR-INV-001/002/003)·`scope_exact_combined_no_favorable_subset`(SIR-EV-002·노른자 2·§10 exact scope +
   dependency closure + combined incidents·SIR-INV-003/004)·`evidence_communication_status_honest`(SIR-EV-009·노른자
   3·§18 evidence/communication honesty·SIR-INV-014 + §18:472 9-token ladder). 전부 순수·fail-closed·전 owner
   verdict/generation/digest는 주입.
6. **소유권/seam 분할표(§3.5·§3.6) — 본 문서 최대 함정.** sbr(Recovery Barrier/Recovery Session·소유)·hag(Effective
   Principal collapse/quorum/Governed Single-Operator Re-Arm Variant·소유)·spg(Safety Incident Policy activation via
   ADR-002-014 + Hard Safety Envelope·소유)·evidence(incident evidence custody/causal-chain/gap·소유)·liveauth(Live
   Authorization·소유)·rcl(capacity mutation/worst-credible·소유·**edge 0**)·egress(final-egress enforcement·소유)·
   cur(Active Currentness·소유·**forward: Incident Generation 소비**)·authority(Safety Authority/HALT/generation
   fence·소유)·protective(Protective Action Controller/Cancellation Arbiter·소유·**forward: dominating incident 주입
   소비**)·iap(single-use consumption shape·선례)·time(Trustworthy Time·소유)·rlp(demotion/production scope·소유)·
   wdr(Non-Waivable Boundary/no-post-hoc-waiver·소유)를 **SIR이 재저작하지 않는다**. **sibling edge 0**(§3.4).
7. **선제 봉합** — ∅ 양방향(active set / dependency closure / scope 부재 ⇒ deny·단 §9 lifecycle의 명시-허용
   상태는 applicable 측 확인 선행·§4.4)·집합 양방향(active set ⊇ applicable incidents 양방향·closure ⊇ affected
   양방향)·truthy-sentinel 구조 봉인(`IncidentLifecycleState`·`ClosureDecisionResult`·`IncidentRecordState`·
   `CommunicationAssertionKind` `__bool__ ⇒ TypeError`)·all-false incident authority·malformed-model 자기방어
   (positive-claim + incomplete-scope coexistence seal — WDR/RLP/egress QCC 동형)·**극성 규율 전 적용(음극성 소비는
   `is False`만·`is not True` 금지·#18/#22/#23/#25 재발 방지 + committed `dominating_halt_or_incident is False`
   극성 정합)**·**그룹 reconcile(Active Safety Incident Set 전-entry 보수·no favorable subset·SIR-INV-004)**·
   **manually-transcribed regression anchor**(§9 8-state lifecycle·§18:472 9-token honesty ladder·§20 12-item closure
   contract — enum-drift 정직화)·금지 동사 canary(§4.1).

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR §29는 15개 게이트 조건
  전부 완료 전까지 **Proposed** 유지를 요구한다(line 737–757). ADR acceptance는 오직 *실행된* evidence로만 온다
  (project memory `tos-spec-rfc-authoring-track`).
- **어떤 SIR-EV도 완결하지 않는다(§1).** register 최소 레벨이 core 3행조차 전부 staged `EV-L1/3`(001은 `+Security`
  추가)이고 나머지 9행은 ≥ L2/L3(+Broker/+Security)이다. Phase 1은 **SIR-EV 0건**을 닫는다. "EV-L1-complete 주장
  금지." 모든 substrate 주장에 규율 태그를 붙인다: **"L1 슬라이스 3행(001·002·009), 전 행 NOT_IMPLEMENTED 유지,
  001은 +Security 조직 게이트 미충족; L1-decidable 술어를 저작하되 어떤 SIR-EV도 EV-L1 증거로 닫지 않는다."**
- **incident-management 런타임을 구현하지 않는다.** signal detection·severity/scope classifier·dependency-graph/
  common-mode engine·Incident Generation registry/writer-fence·restrictive ingress·controlled-shutdown
  orchestrator·notification/timeline·closure quorum counting은 **전부 런타임/인간/형제-owned**(ADR §28 OQ 1–12·§6c).
  §5 매트릭스·레코드는 **문서-레벨 frozen 레코드 shape**만이다.
- **어떤 restriction/HALT/fence를 강제(enforce)하지 않는다.** ADR §1 line 27 "Process termination, deployment
  scale-to-zero, connection closure, credential disablement, or strategy stop is **not proof** that an order was not
  accepted." 본 계약의 술어는 *분류·fail-closed*만 하고 실제 fence·partition·credential 격리 **메커니즘**은 형제
  (egress/rcl/authority/spg/sbr/protective)와 런타임이 소유한다(§3.5).
- **egress/전송·authority 부여·capacity mutation·protective classification을 구현하지 않는다.** 설계 #1 §4대로 tos는
  정의상 non-transmitting이다. SIR 좌표의 authority-effect는 전부 **false 상수**(`AllFalseIncidentAuthority`·SIR-INV-001)
  이며 "incident 좌표가 authority로 쓰이면 거부" 술어를 둔다(§4·§5.1).
- **controlled-shutdown 실행·hard-fence 메커니즘을 저작하지 않는다.** ADR §12 10-step ordering과 §17 partition
  matrix의 실제 fence는 형제가 **injected positive-proof**(`X_hard_fenced: bool|None`·fail-closed)로 소유한다(§3.5·§6).
- **신규 VP-002 키를 저작하지 않는다.** ADR §28 item 12의 `B_incident_*`·`MAX_incident_*` bound 승인·측정은 Phase-0
  Bounds-Approver 게이트다(§8).
- **수치 하드코딩 0.** signal-to-restriction·scope-expansion·generation-fence·shutdown·status-age·plan-age·
  closure-evidence-age bound은 전부 주입/이연이며 어떤 숫자도 모델에 넣지 않는다(CLAUDE.md 설정 기반·§8).
- **미착지 상류/하류 코드 인용 금지** — STM(-028)·SCI(-029)는 미착지(`tos/src/tos/` 하 부재·§0.4f). §5.4 line 122의
  ADR-002-029(SCI) compromise-as-signal·survey line 341의 STM→SIR incident handoff는 **ADR 원문만·코드 인용 0**.
- **EV/acceptance/비준 선언 금지.** tos-spec 수정 금지·기존 docs/plans 무수정. 미비준 문서 인용 없음.

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

`tos.sir`는 **순수 모델·술어 패키지**다: `pydantic` + stdlib + `tos.canonical`(digest-bound artifact substrate) +
`tos.ordering`(Incident Generation 순서)만 import. `shared.*`·`services.*`·`cli.*`·`numpy`/`pandas`/`yaml`·
`os.environ`·동적 escape(`exec`/`eval`/`importlib`/`__import__`) **전면 부재**. **형제 tos 패키지(canonical·ordering
제외 전부: sbr·hag·spg·evidence·liveauth·rcl·egress·cur·authority·protective·iap·time·rlp·wdr·afg·orthostate·recon·
brokercap·capsule·venue·nontrade·posttrade·failuredomain·are·ioc·dsl·replacement + 미래 stm/sci) 전부 import
부재** — 형제 상호작용은 **주입 scalar/digest/bool/verdict/enum-token**으로만(sibling edge 0·§3.4). clock·network·
egress·persistence 미접근. `tos/tests/sir/test_sir_import_closure.py`가 import-closure를 allowlist(`closure ⊆
{canonical, ordering, sir}`)로 강제하고 `tools/tos_firewall_check.py`(§3.2 ratified allowlist·default-deny) required
check와 함께 green이어야 본 선언이 능동 성립. **firewall 구조 확인(실측·#21/#24/#27 §0.3 상속)**: `.importlinter`는
`[importlinter:contract:tos-operational-firewall]` type=forbidden·source_modules=`tos` 단일 계약이며 intra-tos
sibling→sibling edge를 구조적으로 금지하지 않는다 — 설계 #1 §3.2 "자기 자신 `tos.*`" 허용 조항이 커버한다.
**신규 sir 패키지는 firewall 도구 무수정 자동 포섭**된다(WDR §0.3 `check:147` 선례). 본 문서는 그럼에도 **sibling
edge 0건**을 **설계 규율**로 유지한다.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 명명 = `tos.sir` (register-prefix 1:1·naming = WDR와 동형의 약한 soft load-bearing).**

- **선택(확정) `tos.sir`** — 근거: (1) **register prefix 1:1**: 시리즈가 `SIR-INV`/`SIR-AC`/`SIR-EV`를 사용
  (register 실측 md line 348–359·csv 317–328·ADR §6/§26·VER-002-001 line 7 evidence family "SIR"). terse-lowercase
  관행(rcl·spg·iap·hag·are·ioc·afg·sbr·cur·egress·rlp·wdr)과 정합. (2) **firewall 배제 목록이 이름을 이미 지명(약한
  load-bearing)**: `wdr/__init__.py:47`·`rlp/__init__.py:39`·`cur/__init__.py:51`이 "미래 형제 `tos.sir`"를 §7.1
  allowlist 자동 배제 대상으로 열거(grep 실측). WDR과 동형 — 다른 이름 선택 시 기능 orphan은 없고 목록 주석만
  부정확해진다(약한 soft load-bearing). (3) **충돌 없음**: `sir`은 미점유(현 29패키지 실측·ls 확인·§0.4b).
- **runner-up `tos.incident`(기각)** — full-word 관행(liveauth·brokercap·orthostate·protective·replacement·nontrade·
  posttrade·failuredomain)도 존재하나 register-prefix 1:1(egress/hag/sbr/cur/rlp/wdr 최근 선례)이 더 강하다.
  **§10.1 운영자 판단 지점**: `tos.sir` 채택 권고(운영자 치환 가능·naming load-bearing 아님·설계 #1 line 164).

**(b) SIR = greenfield incident-governance content owner·피이연 없음·forward concept-seam 1건 committed (본 문서
최대 판정·WDR과의 결정적 대비).**

- **실측(inbound 이연 seam 0건 / forward committed 소비 3-clade)**: **v1.1 grep 패턴 교정(C1·§0.5 자체 실패
  수정)** — v1.0의 좁은 패턴(`tos.sir`·`dominating_halt_or_incident`만)이 committed 소비 3건을 놓쳤다. 교정 패턴:
  `grep -rin "-027|SIR[-_]|INCIDENT|[Ii]ncident [Gg]eneration|incident_generation|dominating_halt_or_incident|tos\.sir"
  tos/src/tos/ --include="*.py"` 결과 전수 —
  1. **firewall 배제 목록 명명(내용 이연 아님·WDR과 동형)**: `wdr/__init__.py:47`·`rlp/__init__.py:39`·
     `cur/__init__.py:51`의 `tos.sir`.
  2. **forward 개념 소비 (protective/sbr·committed·§3.6)**: `protective/records.py:202`(필드 `dominating_halt_or_
     incident: bool | None`)·`:181-183`(docstring "must be positively `False` … ADR-002-027 / SIR-INV-015 injected
     verdict")·`protective/predicates.py:359-360,395`(`return inputs.dominating_halt_or_incident is False`)·
     `sbr/predicates.py:692,706-707,731`(`if dominating_halt_or_incident is not False`). **익명 bool 주입·`tos.sir`
     타입 미참조.**
  3. **forward 좌표 소비 (wdr·committed·v1.1 신규 등재)**: `wdr/predicates.py:14`("-027 incident generation is not
     landed (injected opaque coordinate). wdr **consumes** …")·`wdr/state.py:48-49`(주입 좌표 목록에 "-027 incident
     generation" 열거). wdr가 SIR Incident Generation을 **주입 opaque 좌표로 자기증언 소비**(WDR §2.1 reference·§3.5
     wdr 행). **익명 generation 주입·`tos.sir` 타입 미참조.**
  4. **정책/차원 토큰 name-collision (spg/cur·committed·v1.1 신규 등재·name-similarity ≠ proposition-identity)**:
     `spg/vocabulary.py:215-216`(`SAFETY_INCIDENT_POLICY`·`ACTIVE_SAFETY_INCIDENT_SET` — spg governed-artifact-**kind
     문자열 토큰**·spg가 ADR-002-014 config로 관장하는 아티팩트-종류 열거이지 SIR 아티팩트 모델 아님)·
     `cur/vocabulary.py:143`(`DimensionKey.INCIDENT = "INCIDENT"` — cur가 이미 보유하는 currentness **차원 키**·
     `:172` `MANDATED_DIMENSION_FLOOR` 소속). **둘 다 SIR이 생산할 *값*의 종류/차원 이름이며 SIR 아티팩트/술어를
     이연받지 않는다**(§3.5 name-collision seal·§0.5).
- **⇒ 판정(4판정 유지·forward seam 보강)**: 어떤 착지 형제도 incident-**content**를 `tos.sir`로 이연하지 않는다
  (RLP식 피이연 0건). 단 SIR이 생산할 것의 **좌표/개념**은 이미 4-clade committed 소비 중이다 — (2) protective/sbr의
  incident-restriction 개념(익명 bool), (3) wdr의 Incident Generation(익명 opaque 좌표), (4) spg governed-artifact-
  kind 토큰·cur `DimensionKey.INCIDENT`(값 종류/차원 이름). 이는 **greenfield·edge 0 결론을 보강**한다: 소비 형태가
  전부 `tos.sir` 타입이 아닌 익명 bool/opaque-scalar/문자열-토큰이라 **sibling edge = 0**이고, SIR은 그 좌표들의
  *값·완전성 판정·아티팩트*를 소유하는 **WDR식 greenfield 생산자**(RLP 미러 아님)다. **cur는 `DimensionKey.INCIDENT`
  차원을 이미 보유하나** SIR은 그 차원의 *값*(Incident Generation·Active Set digest)을 생산하고 **완전성 판정은 cur
  소유**(재저작 0·§3.5 cur 행). SIR이 소유하는 잔여 = **incident-declaration/containment/shutdown/closure governance
  계약 전체**(§1·§5·§6). **리뷰어 공격 지점(§10.2-①)**: "SIR이 RLP처럼 피이연자여야" — 반론: inbound content 이연
  0건·forward 소비는 전부 익명 좌표·SIR은 순수 생산자·naming은 약한 soft load-bearing.

**(c) INV 밀도 > L1 행 — 닫지 않는 predicate substrate가 규모 절반 이상(본 문서 특유 규율·survey line 305–306).**
SIR-INV 16건 중 L1 3행이 닫는 데 기여하는 것은 **정확히 5건(001·002·003·004·014·§12/§14 정합)**이고, 나머지
**11건**(005 containment authority·006 rcl/egress exclusivity·007 controlled-shutdown≠broker-finality·008
obligations-survive-shutdown·009 UNKNOWN-conservative·010 broker-finality-unchanged·011 currentness·012 closure-non-
permissive·013 economic-effect-outlives·015 recovery-non-revival·016 closure-independence)은 **≥ L2/L3 substrate**다. 이들을 L1으로 오주장하면 안 된다(over-realization). 그러나 각 INV의 **L1-decidable 순수 판정 부분**
(all-false·극성·구조 파생·no-relabel)은 저작하되 **어떤 SIR-EV도 닫지 않는 predicate-only substrate**(§6)로 정직
분류한다. **이 정직한 경계가 본 문서의 최대 규율**이다(WDR §0.1-5 over-realization 경계 상속).

**(d) canonical `IndependentIdArtifact` + `classify_record_pair` REUSE (WDR 선례·FD와 대비).** SIR의 6개 digest-
bound 아티팩트(Policy·Record·Active-Set·Containment-Plan·Recovery-Handoff·Closure-Decision)는 **append-only
ledger citizen**이다(§5.3 "immutable versioned record"·§5.5 "immutable canonical set"·§5.10 "immutable independent
result"·§20:505 "single-use record transition"). ⇒ `IndependentIdArtifact`(id ⊥ digest·`_base.py:328`) 채택 +
`classify_record_pair`(`record_pair.py:52`)로 same-id/different-bytes 위조/replay를 `CRITICAL_CONFLICT` 탐지(WDR/rcl/
egress/cur/rlp 선례). **FD와 대비**: FD는 문서-레벨 plain FrozenModel(digest 소비자 부재)였으나 SIR은 immutable
versioned incident 레코드·Incident Generation fence·closure single-use가 명시되어 digest-bound가 정답이다.

**(e) ordering REUSE — Incident Generation monotonic fence.** §5.4 Incident Generation은 "A monotonic generation
fencing earlier incident scope, state, plans, closure eligibility, recovery handoff, configuration requests,
authority requests, and consumers"(line 118–120)다. `tos.ordering`(`compare_order`·`_ordering.py:86`)를 REUSE해
generation floor·predecessor·monotonic fence를 표현. Incident Generation은 ordering identity이지 wall-clock 아님 —
SIR는 clock-free(`MAX_incident_*_ms` wall-clock age는 secondary +Security/INSTANCE·§8). **PROMOTE 0**(canonical/
ordering 외 신규 core 없음).

**(f) 미착지 상류 028/029 차원 (phantom 봉합).** **실측**: `tos/src/tos/` 하 stm·sci **부재**(ls 확인). §5.4 line
122가 ADR-002-029(SCI) compromise를 "a Safety Signal for the greatest credible dependent scope"로 참조하고, survey
line 341–343이 STM-EV-008(-028) "Restrictive and Incident Handoff"의 ADR-002-028 → ADR-002-027 참조 9회를 기록한다.
- **판정: SIR는 이를 주입 generation/digest/signal 좌표로만 소비/생산.** ADR 원문만 참조하고 **코드 인용 0**
  (미착지·phantom 금지). SCI compromise-signal은 opaque 주입 Safety Signal로 수용하고, STM incident-handoff는 SIR가
  생산할 좌표(하류 STM 소비·forward)이나 STM 미착지라 배선 없음. **리뷰어 공격 지점(§10.2-⑤)**: "미착지 028/029
  substrate 오인용" — 반론: ADR 원문만·코드 0·주입 좌표·§0.2 NO-list.

### 0.5 anti-phantom 규율 (FD #27 §0.5 상속 — 부재 주장·존재 주장 양방향 grep)

**시리즈 교훈(defect class `anti-phantom`·FD #27)**: 존재 인용은 grep했으나 **부재 주장**("형제 미소유"·"타입 없음"·
"tos 전역 무주인")은 grep하지 않은 **검증 비대칭**이 FD v1.0 REJECT의 유일 결함군이었고, 대칭으로 **미검증 존재
주장**(FD가 `rcl.CapabilityClaim`을 산문에서 심볼명화 → 실명 `rcl.ClaimRecord`)도 사각이었다(FD §10.2). 본 계약은
**모든 부재/무주인/유일-소유/존재 주장에 grep 근거를 병기**한다:
- (i) `grep -rln <name> ⇒ 빈 결과` 명시로 부재를 증명(예: `Incident*` 타입 tos 전역 부재·`ClosureDecisionResult`/
  `CLOSE_ADMINISTRATIVELY` 부재 — §0.4b·§3.5 실측).
- (ii) "유일 소유"는 대안 소유자 전수 배제 grep(예: incident lifecycle 8-state는 SIR 소유이되 evidence는
  `GapStatus.SUSPECTED`라는 **동명이축**을 소유 — §3.5 name-collision seal).
- (iii) "무주인"은 tos 전역 grep 0 + Phase-0 등재(§8)로 fail-open 차단.
- (iv) **존재 주장도 실측**: 본 문서의 모든 file:line 인용은 저작 시점 grep 결과이며 구현 단계 drift-lock 테스트
  (§7.2)가 형제 심볼 실 resolve로 재고정한다(FD §10.2 교훈 — "산문을 심볼명화" 금지).

**v1.1 자체 실패 고지(C1·정직성)**: v1.0의 §0.4b/§0.5 grep 패턴이 `-i`·`INCIDENT`·`[Ii]ncident [Gg]eneration`를
누락해 committed 소비 3건(`wdr/predicates.py:14`·`wdr/state.py:48-49`·`spg/vocabulary.py:215-216`·`cur/vocabulary.py:143`)을
놓쳤다 — **anti-phantom 규율을 자기 문서에 미적용한 FD §10.2 동형 사례**. v1.1은 case-insensitive 광역 패턴으로
재실측하고 전 committed 참조를 §0.4b 4-clade·§3.5에 등재한다. 이는 forward seam을 **보강**할 뿐 greenfield·edge 0
결론을 바꾸지 않는다(소비 형태 전부 익명 좌표).

**본 문서에 적용된 anti-phantom 실측 요지(v1.1 재실측)**:
- **존재(committed·교정 패턴 `grep -rin`)**: `protective/predicates.py:395`·`protective/records.py:202`(필드)/
  `:181-183`(docstring)·`sbr/predicates.py:731`의 `dominating_halt_or_incident`(§3.6); `wdr/predicates.py:14`·
  `wdr/state.py:48-49`의 "-027 incident generation" 주입 소비(§0.4b-3); `spg/vocabulary.py:215-216`
  `SAFETY_INCIDENT_POLICY`/`ACTIVE_SAFETY_INCIDENT_SET`·`cur/vocabulary.py:143` `DimensionKey.INCIDENT`(§0.4b-4·
  name-collision); firewall 배제 `tos.sir` 3곳(§0.4a); iap single-use shape `iap/predicates.py:176`(§6);
  `_NonTruthyStrEnum` 10패키지(cur·egress·hag·iap·nontrade·posttrade·rlp·sbr·venue·wdr·grep 실측·**ioc 제외** —
  ioc는 `ConformanceResult.__bool__`(vocabulary.py:63) 동종 봉인 별도)·`AllFalse*Authority` **16파일**(afg·are·
  authority·cur·dsl·egress·failuredomain·iap·ioc·liveauth·nontrade·rcl·replacement·rlp·time·wdr·grep 실측)·canonical
  `IndependentIdArtifact`(`_base.py:328`)/`classify_record_pair`(`record_pair.py:52`)/`RecordPairKind`
  (`record_pair.py:31`)·ordering `compare_order`(`_ordering.py:86`)(§3.1).
- **부재(negative-grep·유지)**: `grep -rln "class .*Incident|IncidentGeneration|ActiveSafetyIncident|
  SafetyIncidentRecord|IncidentClosure|ClosureDecisionResult" tos/src/tos --include="*.py" ⇒ 빈 결과`(SIR **아티팩트
  모델·술어** greenfield 확정 — spg/cur의 토큰/차원 이름은 아티팩트 모델 아님·아래 seal); `CLOSE_ADMINISTRATIVELY|
  CONTAINMENT_PLAN|CONTROLLED_SHUTDOWN ⇒ 빈 결과`; `NO_INCIDENT ⇒ 빈 결과`(v1.0 §4.4/§10.2의 "cur/egress
  NO_INCIDENT 소유" phantom **삭제**·오케스트레이터 재확인·ADR §16:429는 금지 조항으로만 인용); evidence는
  communication-assertion/honesty-ladder enum **미소유**(`observed_fact|conservative_assumption|CommunicationAssertion|
  enforcement_ack ⇒ 빈 결과`).
- **동명이축 함정 3건(name-similarity ≠ proposition-identity·FD 교훈·§3.5 seal)**:
  (1) `evidence/gap.py:41 GapStatus.SUSPECTED`(gap lifecycle `SUSPECTED→CONFIRMED→CONTAINED→REPAIRED→
  INDEPENDENTLY_REVIEWED`·gap.py:10) ≠ SIR `IncidentLifecycleState.SUSPECTED`(§9 incident lifecycle) — 문자열만 충돌.
  (2) `spg/vocabulary.py:215-216 SAFETY_INCIDENT_POLICY/ACTIVE_SAFETY_INCIDENT_SET`(spg governed-artifact-**kind
  문자열 토큰**) ≠ SIR `SafetyIncidentPolicy`/`ActiveSafetyIncidentSet`(**아티팩트 모델**) — spg는 ADR-002-014가
  관장하는 아티팩트 *종류 이름*을 열거하고 SIR은 그 아티팩트를 *저작*·명제 상이.
  (3) `cur/vocabulary.py:143 DimensionKey.INCIDENT`(currentness *차원 키*·mandated floor) ≠ SIR incident *값·
  아티팩트* — cur는 차원의 완전성 판정을 소유하고 SIR은 그 차원의 값을 생산·명제 상이.

---

## 1. 범위 매핑 — ADR-002-027 조항별 EV-L1 도달성 (닫는 SIR-EV 0건)

EV-level 정의(VER-002-001 실측): **EV-L1 = Model and Property Verification**(line 142–144: "State-machine
exploration, model checking, property-based testing, and deterministic simulation") · **EV-L2 = Component Fault
Test**(line 146–148) · **EV-L3 = Integrated System Fault Test**(line 150: "Multiple live-path components … real
persistence, identity, and network boundaries") · **`+Security`** = 독립 security-boundary assessment(line 172) ·
**`+Broker`** = Broker Capability Profile evidence(line 172) · **`EV-Ln/Lm` = staged scope, not a free choice**
(line 173). Phase 1은 EV-L1만이다. VER line 175 "A lower level cannot substitute for a required higher level."

> **결정적 사실 1 — SIR-EV core 3행(거버넌스 6부작 중 하한 L3 최다 그룹)**: register 실측(md line 348–359 /
> csv 317–328·survey §4.3 line 283–294): **core(L1 슬라이스) 3행 = {001 Restrictive Detection and Declaration
> `EV-L1/3+Security`·002 Exact Scope and Combined Incidents `EV-L1/3`·009 Evidence, Communication, and Status
> Honesty `EV-L1/3`}**. **predicate-only(≥ L2) 6행 = {003 Containment Authority Separation `EV-L2/3+Security`·005
> Protection and Ongoing Obligations `EV-L2/3+Broker`·006 UNKNOWN, Broker Finality, and Capacity `EV-L2/3+Broker`·
> 010 Independent Non-Permissive Closure `EV-L2/3+Security`·011 External Activity and Demotion `EV-L2/3+Broker+
> Security`·012 Recovery and Non-Revival `EV-L2/3+Security`}**. **not-Phase-1(하한 L3) 3행 = {004 Controlled
> Shutdown and Hard Fencing `EV-L3+Broker+Security`·007 Incident Currentness and Send Race `EV-L3+Security`·008
> Partition, Common Mode, and Compromise `EV-L3+Security`}**. **닫는 SIR-EV = 0건**. 히스토그램(survey line
> 296–297): `EV-L2/3+Security` ×3 · `EV-L3+Security` ×2 · `EV-L1/3` ×2 · `EV-L2/3+Broker` ×2 · `EV-L1/3+Security`
> ×1 · `EV-L3+Broker+Security` ×1 · `EV-L2/3+Broker+Security` ×1.
>
> **결정적 사실 2 — core 3행 중 001만 `+Security` 잔여(정직성 핵심)**: 002·009는 순수 `EV-L1/3`(태그 0)이고
> 001은 `EV-L1/3+Security`. 즉 001은 **L1 슬라이스가 존재하나 그 행의 최종 closing에 +Security 축(signal
> forgery/suppression/downgrade 저항·§22)이 남는다** — L1 술어는 저작하되 그 행을 **닫지 못한다**(§5.1 명기).
>
> **결정적 사실 3 — 하한 L3 행 3건 = 거버넌스 6부작 최다(survey line 303–304)**: 004·007·008이 하한 `EV-L3`로
> register 표면 자체가 통합 시스템 결함 시험 쪽으로 기울어 있다. 이는 SIR이 **통합·소유권-분할 레이어**(controlled
> shutdown ordering·send race·partition/compromise가 본질적으로 L3)임을 반영한다 — FD(#27)의 "0건 완결"과 WDR
> (#26)의 "5행 core" 사이의 중간 성격.
>
> **결정적 사실 4 — authoring ≠ acceptance (닫는 SIR-EV = 0건)**: (a) core 3행 전부 `/3`(integration/adversarial)
> 잔여 + 001은 +Security 추가 잔여, (b) predicate-only 6행은 최소 ≥ L2(+Broker/+Security), (c) not-Phase-1 3행은
> L3 런타임, (d) VER line 175·ADR §26 line 644 "Written cases are not completed evidence"·§29 line 757 "Authorship
> … does not satisfy these gates." ⇒ **"EV-L1-complete 주장 금지"**(#12–#27 §1 규율 상속). register status 전 12행
> `NOT_IMPLEMENTED`(csv 실측).

**규율 태그(모든 주장에 부착)**: "**restrictive-declaration / exact-scope-combined / evidence-honesty predicate
substrate only; SIR-EV-001..012 전부 NOT_IMPLEMENTED — core 3행(001·002·009)은 `/3` 통합·adversarial 대기 + 001은
+Security 추가 잔여, predicate-only 6행은 component-fault L2·+Broker/+Security 대기, not-Phase-1 3행(004·007·008)은
L3 런타임. EV-L1-complete 주장 금지·signal classifier·dependency-graph engine·controlled-shutdown orchestrator·
closure quorum·per-action egress binding·worst-credible-effect 계산·Live Authorization 발급은 재저작/런타임/인간/
+Security/+Broker/형제-owned. L1은 declaration/scope/honesty 구조 판정만.**"

**SIR-EV core 3행 ↔ AC(1:1) ↔ ADR 조항 ↔ INV 매핑(실측)**:

| SIR-EV | register 제목(verbatim, md line) | 최소 레벨 | SIR-AC(1:1) | ADR 조항 앵커 | 관련 INV | L1 substrate 술어(§5) |
|---|---|---|---|---|---|---|
| **001** | Restrictive Detection and Declaration (348) | `EV-L1/3+Security` | AC-001(§26 line 646) | §8 Classification·restrictive declaration | INV-001/002/003 | `restrictive_declaration_non_authorizing`(노른자 1) + `declaration_creates_no_authority`·`low_severity_no_narrow`(§5.1) |
| **002** | Exact Scope and Combined Incidents (349) | `EV-L1/3` | AC-002(§26 line 650) | §10 Exact Scope·§5.5 Active Set·§5.6 Closure | INV-003/004 | `scope_exact_combined_no_favorable_subset`(노른자 2) + `active_set_is_canonical_union`·`no_favorable_subset`·`dependency_closure_complete`(§5.2) |
| **009** | Evidence, Communication, and Status Honesty (356) | `EV-L1/3` | AC-009(§26 line 678) | §18 Evidence/Communications | INV-014 (+ §18:472) | `evidence_communication_status_honest`(노른자 3) + `communication_assertions_distinguished`·`message_ack_not_enforcement_ack`·`analysis_not_prevention`(§5.3) |

**ADR-002-027 조항 → Phase-1 분류(core / predicate-only / not-Phase-1 / 형제·런타임)**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | SIR-EV |
|---|---|---|---|---|
| **§8** (line 246–270) | 8-class classification·restrictive declaration before workflow·low-severity no-narrow | **core (L1)·+Security 잔여** | `restrictive_declaration_non_authorizing`(§5.1) — 8-class anchor·declaration은 restrictive/asymmetric(INV-002)·all-false(INV-001)·low-severity가 Critical/unknown-scope narrow 불가(§8:269). 실 signal forgery/suppression 저항은 +Security. | **001** |
| **§10** (line 301–315)·**§5.5**(124–126)·**§5.6**(128–130) | Exact greatest-credible scope·Active Set canonical union·no favorable subset·no self-exempt | **core (L1 슬라이스)** | `scope_exact_combined_no_favorable_subset`(§5.2) — greatest-credible dependency closure 완전성 + Active Safety Incident Set = union of open/suspected/overlapping/parent/child/common-mode + no child-only closure while shared cause open. 가장 깨끗한 L1(순수 `EV-L1/3`). | **002** |
| **§18** (line 457–475) | Evidence≠prevention·9-token honesty·message-ack≠enforcement-ack·analysis≠authorize | **core (L1 슬라이스)** | `evidence_communication_status_honest`(§5.3) — INV-014 evidence not prevention + §18:472 9-token assertion 구분 + message-ack≠enforcement-ack + root-cause/replay/postmortem이 past effect authorize 불가(§18:474). | **009** |
| **§11** (318–336)·**§7** (222–243) | Containment labels·severity·priority·commander가 authority 아님·bypass 불가 | **predicate-only (+Security)** | `containment_uses_normal_authority`(§6.1·INV-005·all-false — label/severity/priority/commander ≠ classify-protective/reserve-capacity/waive-constraint/issue-authority/bypass-egress·§11:333). 실 authority separation은 +Security. | **003** |
| **§14** (386–401)·**§12** step 6 (348) | Protection/obligation survive shutdown·no blind cancel/liquidate | **predicate-only (+Broker)** | `obligations_survive_shutdown`(§6.4·INV-008·§14:388 "SHALL NOT be blindly cancelled"). 실 protection/exit feasibility·late-fill은 +Broker. | **005** |
| **§13** (368–383)·**§16** (418–431) | UNKNOWN⇒block+worst-credible·missing-ACK≠non-acceptance·Cancel-ACK≠FQP·expiry≠release | **predicate-only (+Broker)** | `unknown_remains_conservative`(§6.5·INV-009·음극성 UNKNOWN 전수) + `broker_finality_unchanged`(§6.6·INV-010·§13:372–373) + `economic_effect_outlives_incident_state`(§6.7·INV-013·§13:377 authority-shape). 실 broker-finality 정량화는 +Broker. | **006** |
| **§20** (488–506)·**§7** (236)·**§16-018 independence** | Closure administrative·non-permissive·independent·no favorable subset·Single-Operator Variant | **predicate-only (+Security)** | `closure_administrative_non_permissive`(§6.8·INV-012·all-false·§20:503 item 12) + `closure_independence_non_self_exemption`(§6.9·INV-016·principals no-collapse·unknown-independence⇒deny·hag 주입). 실 quorum counting·Effective Principal은 hag·+Security. | **010** |
| **§15** (403–415)·**§19** (478–485) | External/manual broker activity conservative·demotion no auto-scope·no post-hoc deviation | **predicate-only (+Broker+Security)** | `external_activity_conservative`(§6b·§15:407 "does not become retroactively compliant"·no RCL release by statement·no HALT-clear) + demotion→rlp/wdr 주입(§19). 실 external procedure/credential custody는 +Broker+Security. | **011** |
| **§21** (509–523)·**§16-INV-015** | Recovery non-revival·Recovery Barrier closed·no auto-re-arm | **predicate-only (+Security)** | `recovery_revives_nothing`(§6.3·INV-015·음극성 non-revival 전수·**committed `dominating_halt_or_incident` forward seam 정합**·§3.6). 실 hard-fence·Recovery Session은 sbr·+Security. | **012** |
| **§12** (339–365)·**§17** (437–454) | Controlled shutdown 10-step ordering·hard fencing·partition | **not-Phase-1 (하한 L3·런타임)** | `controlled_shutdown_not_broker_finality`(§6.2·INV-007·§12:356 SHALL-NOT — process stop≠finality) substrate만; 실 10-step ordering·hard-fence·partition matrix는 L3 런타임/형제(egress/rcl/authority). | **004·008** |
| **§16** (418–435)·**§11** race | Incident Generation current at egress·send race·no permissive cache | **not-Phase-1 (런타임 race)** | 얇은 순서 permutation model(§6b·`RESTRICT<SEND⇒deny`·`SEND<RESTRICT<FIRST_BYTE⇒potentially-live+capacity-covered`·§16:431). 실 cache-free currentness·`B_incident_restriction_to_egress`·deny-first latch는 +Security 런타임·egress. | **007** |
| **§5.1·§9·§20 item 10·§28·§29** | Policy activation·quorum counting·numeric·acceptance | **not-Phase-1 (Phase-0/INSTANCE·런타임/형제)** | policy activation=spg(ADR-002-014) 주입·quorum=hag·numeric=§8 Phase-0·acceptance=거버넌스. | (전 행 분산) |

---

## 2. 데이터 모델 계약

### 2.1 digest-bound / value / reference 분류

| 분류 | 모델 | 근거 |
|---|---|---|
| **digest-bound `IndependentIdArtifact`** (id ⊥ digest·6종) | `SafetyIncidentPolicy`(§5.1)·`SafetyIncidentRecord`(§5.3)·`ActiveSafetyIncidentSet`(§5.5)·`IncidentContainmentPlan`(§5.7·`ControlledShutdownProcedure` 포함)·`IncidentRecoveryHandoffPackage`(§5.9)·`IncidentClosureDecision`(§5.10) | append-only ledger citizen(§5.3 "immutable versioned record"·§5.5 "immutable canonical set"·§5.7/§5.9 "immutable non-authorizing"·§5.10 "immutable independent result"·§20:505 "single-use record transition"). id 서비스 부여(≠ `f(digest)`·canonical `IndependentIdArtifact`·`_base.py:328`·WDR/rcl/egress/cur/rlp 선례). same-id/different-bytes 위조/replay를 `classify_record_pair` `CRITICAL_CONFLICT`로 탐지(§3.1·§22 line 536 "incident closure replay or duplicate consumption" 방어). |
| **value (frozen, id 없음)** | `SafetySignal`(§5.2)·`IncidentDependencyClosure`(§5.6·§10)·`IncidentScope`(§10 exact scope)·`ControlledShutdownProcedure`(§5.8 value·plan 내부)·`OngoingSafetyObligation`(§5.11)·`CommunicationHonestyLadder`(§18:472 9-token view)·`ClosureIndependenceLadder`(§7/§20 item 10/§6 SIR-INV-016 line 216–218 Effective Principal roles)·`IncidentClassificationInput`(§8 8-class) | id 미도출·mutate 없음. `IncidentDependencyClosure`·`IncidentScope`의 dimension 집합·`CommunicationHonestyLadder`의 9-token·§9 8-state는 §5.6/§10/§18/§9 조항을 손전사한 **manually-transcribed anchor**(§7.2 drift property). |
| **enum-token (`_NonTruthyStrEnum`·6종)** | `IncidentLifecycleState`{SUSPECTED..CLOSED 8-state·§9}·`ClosureDecisionResult`{DENY/HOLD/CLOSE_ADMINISTRATIVELY·§5.10}·`IncidentRecordState`{DRAFT/ACTIVE/SUPERSEDED/REOPENED 4·§5.3}·`CommunicationAssertionKind`{observed_fact..administrative_decision 9-token·§18:472}·`SignalClassificationClass`{8-class·§8}·`ClosureDimension`{22-token·§5.6·v1.1} | 어휘(§2.2). `__bool__ ⇒ TypeError`(truthy 봉인·비-clear 멤버가 non-empty string). **`_NonTruthyStrEnum` 로컬 재표현**(cur/egress/hag/iap/nontrade/posttrade/rlp/sbr/venue/wdr `vocabulary.py` 10패키지 선례·grep 실측·**ioc 제외**·import 아님). |
| **reference (scalar/digest only, 주입)** | spg Safety Incident Policy activation verdict + Hard Safety Envelope·hag Effective Principal collapse verdict + quorum satisfied + Single-Operator Variant·rcl worst-credible capacity 좌표·egress final-egress currentness verdict·cur Active Currentness Vector generation·evidence causal_chain_complete + gap-status + custody·liveauth Live Authorization generation·authority Safety Authority/HALT/generation·protective Protective Action Controller/Cancellation Arbiter verdict·time Trustworthy Time gen·rlp demotion/production-scope·wdr Non-Waivable Boundary verdict·**Incident Generation**(SIR 생산·§5.4·cur 하류 소비)·**028/029 incident-handoff/compromise(미착지·주입)** | 형제/미착지 소유 — 주입 scalar/digest/verdict로만 참조(§3.4/§3.5). SIR는 이들을 저작·import하지 않음(Incident Generation은 SIR 생산이나 cur 하류 소비는 cur 소유·forward). **-028/-029는 미착지 — ADR 원문만·코드 인용 0(§0.4f).** |

### 2.2 어휘 (verbatim 전사 + truthy 봉인)

**(1) `IncidentLifecycleState` (§9 line 277–286, non-truthy StrEnum — 8-state·핵심 truthy 봉인).** `SUSPECTED`·
`DECLARED`·`CONTAINING`·`STABILIZED_NON_LIVE`·`INVESTIGATING`·`REMEDIATION_PENDING`·`ELIGIBLE_FOR_CLOSURE`·`CLOSED`.
**`_NonTruthyStrEnum` 로컬 재표현**(`__bool__ ⇒ TypeError`). **근거**: §9 line 277–286 verbatim lifecycle +
line 290 "`SUSPECTED` is restrictive for the greatest credible scope; it is not permission to wait"·line 295
"`CLOSED` is administrative only and does not transition to `ACTIVE`, `ARMED`, `READY`, or any live state." **어떤
상태도 authority 무부여** — `CLOSED`조차 all-false(§6.8). `if state:`가 pre-closure restrictive 상태를 truthy "go"로
오독하는 fail-open을 봉인. **동명이축 주의(§0.5)**: evidence `GapStatus.SUSPECTED`(gap.py:41)와 문자열만 충돌·명제
상이(SIR=incident lifecycle·evidence=gap lifecycle).

**(2) `ClosureDecisionResult` (§5.10 line 144–146, non-truthy StrEnum — 3-token·closure 봉인).** `DENY`·`HOLD`·
`CLOSE_ADMINISTRATIVELY`. **`_NonTruthyStrEnum`**. **근거**: §5.10 verbatim "An immutable independent result of
`DENY`, `HOLD`, or `CLOSE_ADMINISTRATIVELY` for one exact current incident and Active Safety Incident Set digest.
**It creates no permissive state**." `DENY`/`HOLD`는 non-empty string이라 `if result:`가 거부를 truthy로 오독하는
치명적 fail-open. 소비 게이트는 **`result is ClosureDecisionResult.CLOSE_ADMINISTRATIVELY` 명시 비교 강제**(§4.2).
`CLOSE_ADMINISTRATIVELY` 자체도 authority 아님(§5.10·§20:503 item 12·all-false·§6.8). **전역 부재 실측**: `grep
CLOSE_ADMINISTRATIVELY|ClosureDecisionResult ⇒ 빈 결과`(SIR greenfield 소유·§0.5).

**(3) `CommunicationAssertionKind` (§18 line 472, non-truthy StrEnum — 9-token honesty ladder·SIR-owned).**
`OBSERVED_FACT`·`CONSERVATIVE_ASSUMPTION`·`UNRESOLVED_UNKNOWN`·`PLANNED_ACTION`·`AUTHORIZED_ACTION`·
`TRANSMITTED_ATTEMPT`·`BROKER_EVIDENCE`·`VERIFIED_RESULT`·`ADMINISTRATIVE_DECISION`. **`_NonTruthyStrEnum`**.
**근거**: §18 line 472 verbatim: "Communications SHALL distinguish observed fact, conservative assumption, unresolved
UNKNOWN, planned action, authorized action, transmitted attempt, broker evidence, verified result, and
administrative decision. A message acknowledgement is never an enforcement acknowledgement." ⇒ 9개 assertion kind가
서로 축약/승격 불가(§5.3). **실측: evidence 미소유**(`observed_fact|CommunicationAssertion|enforcement_ack ⇒ 빈
결과`·§0.5) ⇒ SIR 로컬 저작(WDR `WaivedEvidenceStatus` 선례·seam 충돌 0).

**(4) `SignalClassificationClass` (§8 line 248–257, non-truthy StrEnum — 8-class).** `HARD_ENVELOPE_VIOLATION`·
`CONTROL_BYPASS`(RCL/writer-fence/capacity/currentness/authority/credential/route/egress)·`BROKER_STATE_ANOMALY`
(missing/contradictory/stale/externally-changed)·`PROTECTION_LOSS`(replacement-gap/action-flow-exhaustion/venue-
restriction/trapped-exposure)·`CRITICAL_INPUT_COMPROMISE`(config/identity/time/evidence/recovery/failure-domain)·
`UNAUTHORIZED_CROSSOVER`(live/non-live/external broker)·`FAILED_GATE`(bound/security-control/independent-approval/
restricted-live)·`UNESTABLISHED_SCOPE_SEVERITY`(§8:257 "any condition whose scope or severity cannot yet be
established conservatively"). **`_NonTruthyStrEnum`**. **근거**: §8 line 248–257 8-class 손전사(§부록 C·§7.2 drift).
`UNESTABLISHED_SCOPE_SEVERITY`가 노른자 1의 fail-closed 수렴점(§5.1).

**(5) `IncidentRecordState` (§5.3·record lifecycle, non-truthy StrEnum·멤버 전수 열거·What's-Missing).** append-only
record 버전 상태 — `DRAFT`·`ACTIVE`(현행 버전)·`SUPERSEDED`(신 버전으로 대체)·`REOPENED`(§9:296 post-closure signal ⇒
new/reopened record). **`_NonTruthyStrEnum`**. **주의**: `ACTIVE`는 *record 버전이 현행*이라는 뜻이지 incident가
live/permissive라는 뜻이 아니다(§9:295 CLOSED≠live와 별개 축·all-false 유지). §5.3 "immutable versioned record"·
§9:296 "a new or reopened immutable record; it does not edit history". 비-permissive 상태가 non-empty string이라 `if
state:` fail-open 봉인.

**(6) `ClosureDimension` (§5.6 line 128–130, non-truthy StrEnum — 22 closed 토큰·cur `DimensionKey` 선례·What's-
Missing).** dependency closure 22차원의 닫힌 토큰: `SAFETY_CELL`·`CAPACITY_DOMAIN`·`LEGAL_PORTFOLIO`·`ACCOUNT`·
`BROKER`·`VENUE`·`INSTRUMENT`·`STRATEGY`·`ORDER`·`POSITION`·`COMMITMENT`·`PROTECTION`·`CREDENTIAL`·`ROUTE`·`SESSION`·
`GENERATION`·`COMPONENT`·`ARTIFACT`·`FAILURE_DOMAIN`·`EVIDENCE_PATH`·`EXTERNAL_ACTIVITY`·`DOWNSTREAM_CONSUMER`.
**`_NonTruthyStrEnum`**. `scope_exact_combined_no_favorable_subset`(§5.2 conjunct 4)의 완전성 판정 대상·closed enum ==
§5.6 22차원(§7.2 3자 drift — 부록 A verbatim ↔ §5.2 operative list ↔ `ClosureDimension`). cur `DimensionKey`(currentness
차원)와 **별개 축**(SIR closure 차원·name-collision 아님·§0.5).

### 2.3 아티팩트 covered + self-exclusion + malformed-model 자기방어 (설계 #4 §3.3·WDR §2.3·#20/#22/#23/#25 상속)

- 모든 digest-bound 아티팩트는 `IndependentIdArtifact`(canonical `_base.py:328`)를 상속 — `_ID_FIELD`(독립 id·
  digest preimage self-exclusion)·`_COVERED_FIELDS`(digest cover)·`_REQUIRED_COVERED`(구조 identity 최소 필수)를
  선언(WDR·spg·ioc·rcl·egress·cur·rlp 선례).
- **coordinate 비붕괴(설계 #4 §4.4)**: mutable lifecycle 좌표(record `IncidentLifecycleState`·closure
  `single_use_consumed`·주입 verdict[hag/spg/evidence/egress/protective])는 covered digest에 **미포함** — 정당한
  전이(declare/contain/close/consume)가 digest를 바꿔 same-id/different-bytes `CRITICAL_CONFLICT`로 오탐되지 않도록.
  현재 상태는 술어에 주입·별도 append-only record(§9:296 "does not edit history").
- **malformed-model 자기방어 — positive-claim + incomplete-scope coexistence seal(WDR `SafetyDeviationDecision`·
  RLP `ExactTrialPlan`·egress QCC 동형·본 문서 핵심 seal)**: `IncidentClosureDecision`/`ActiveSafetyIncidentSet`
  `model_validator`가 **불완전 scope/set과 permissive 주장의 공존을 구조로 봉인**. `result is
  ClosureDecisionResult.CLOSE_ADMINISTRATIVELY`인데 §20 mandated 조건(active-set digest·dependency closure·obligation
  transfer 필드) 중 하나라도 `None`이면 **`ArtifactIntegrityError` at construction**. 동일하게
  `ActiveSafetyIncidentSet`(is_complete 주장 + applicable member 누락 공존 ⇒ unconstructable)·`SafetyIncidentRecord`
  (declared 주장 + greatest-credible scope 부재 ⇒ unconstructable). 술어 층에서 validator 통과 후 재확인(defense-in-
  depth·`model_construct` 우회 대비·2층). **리뷰어 공격 지점(§10.2-⑦)**: `model_construct`로 malformed closure 구성
  → validator + 술어 2층 봉인.
- **`ActiveSetMember` 구조 무결성(C2-2·평행 tuple 제거)**: v1.0의 `member_incidents`/`member_digests` 평행 tuple을
  `members: tuple[ActiveSetMember, ...]`로 대체 — 평행 tuple의 길이 불일치/순서 어긋남 결함 클래스를 구조로 제거.
  `model_validator`가 (i) `incident_id` 중복 없음, (ii) `parent_id`가 present이면 members 내 존재(dangling parent
  금지), (iii) `shared_cause_ids`가 `shared_dependencies`의 부분집합을 봉인. 위반 ⇒ `ArtifactIntegrityError`.
- **`_REQUIRED_COVERED`는 구조 identity/generation/digest만·digest 규칙 명문화(Open Q 3)** — 각 아티팩트의
  `_COVERED_FIELDS`는 **self-digest 필드(자기 `*_digest`)를 제외**(preimage self-exclusion·canonical
  `IndependentIdArtifact` 규칙)하되 **외부 참조 digest(`active_set_digest`·`request_digest` 류)는 포함**한다 —
  `IncidentClosureDecision`이 `active_set_digest`를 cover해 "어느 active-set을 닫는가"를 위조 불가로 바인딩(§5.10
  "one exact … Active Safety Incident Set digest"). status-age·plan-age·closure-evidence-age·quorum N 같은 numeric
  bound은 제외(Phase-1 null profile 하 구성 가능·§8); 누락 numeric claim은 fail-closed(§4.2).

### 2.4 핵심 모델 필드 골격 (§ref·형제 seam·all-false)

**`SafetyIncidentPolicy`(§5.1)** — immutable ADR-002-014 governed policy content model. 필드: `policy_id`(독립 id)·
`policy_generation`·`policy_digest`·`authoritative_signal_classes: frozenset[SignalClassificationClass]`·
`severity_rules`·`scope_closure_rules`·`required_restrictions`·`escalation_paths`·`controlled_shutdown_rules`·
`evidence_obligations`·`independence_requirements`·`closure_conditions`·`failure_behavior`·`authority_effect:
AllFalseIncidentAuthority`. **활성화/generation은 spg/ADR-002-014 주입**(§5.1·§7 line 226). `_REQUIRED_COVERED` =
{policy_id·policy_generation·policy_digest}.

**`SafetyIncidentRecord`(§5.3)** — immutable versioned record. 필드: `incident_id`(독립 id)·`record_version`·
`record_digest`·`predecessor_record_id`·`incident_generation`(ordering·§5.4)·`signals: tuple[SafetySignal, ...]`·
`severity`·`incident_scope: IncidentScope`·`dependency_closure: IncidentDependencyClosure`·`restrictions`·`actions`·
`ongoing_obligations: tuple[OngoingSafetyObligation, ...]`·`evidence_gaps`·`external_activity`·`owners`·
`lifecycle_state: IncidentLifecycleState`·`record_state: IncidentRecordState`·`classification:
IncidentClassificationInput`·`greatest_credible_scope_computed: bool | None`(양극성·§8 step 2·구조 파생)·
`restriction_workflow_gated: bool | None`(음극성·§5.1 conjunct 4·§4.3)·`severity_label_narrows_scope: bool | None`
(음극성·§5.1 conjunct 5·§4.3·§8:269)·`authority_effect: AllFalseIncidentAuthority`. **§5.3 verbatim "It grants no
authority"**·all-false. `_REQUIRED_COVERED` = {incident_id·record_version·incident_generation}.

**`ActiveSafetyIncidentSet`(§5.5/§10·C2-2 per-member 구조)** — immutable canonical combined set. 필드: `active_set_id`
(독립 id)·`active_set_generation`·`active_set_digest`·`incident_generation`·`safety_cell`·**`members: tuple[
ActiveSetMember, ...]`**(v1.0 평행 tuple `member_incidents`/`member_digests`를 per-member 구조로 대체·C2-2)·
`shared_dependencies: tuple[str, ...]`·`is_complete: bool | None`(양극성·§5.5 "canonical set")·`is_current: bool |
None`(양극성·§10:311)·`state: IncidentLifecycleState`(집합 상태 = members 구조 파생 또는 주입·§10.2)·`authority_
effect: AllFalseIncidentAuthority`. §5.5 verbatim "One immutable canonical set of every suspected or open incident
and shared dependency applicable to an exact Safety Cell and scope"·**§6 SIR-INV-004 line 170** "A consumer cannot
select, union, or close artifacts to create broader permission." `_REQUIRED_COVERED` = {active_set_id·active_set_
generation·incident_generation·safety_cell}.

**`ActiveSetMember`(value·§5.5/§10·C2-2 신규·구조 파생 substrate)** — per-incident 구조 원소. 필드: `incident_id`·
`incident_digest`·`lifecycle_state: IncidentLifecycleState`·`parent_id: str | None`·`shared_cause_ids: frozenset[
str]`·`resolved: bool | None`(**양극성** — v1.2 E1: §5.2 conjunct 3 operative가 우선·`is not True ⇒ unresolved`·
ADR §10:314). `no_favorable_subset`(§5.2 conjunct 3)이 `open_parent_present`/
`shared_cause_unresolved`/`common_mode_present`를 이 구조에서 **파생**(자기신고 제거). members tuple 길이/평행성/중복
id는 §2.3 malformed-model validator가 봉인.

**`IncidentContainmentPlan`(§5.7)** — immutable non-authorizing plan(§11 line 320–329 전 필드군). 필드: `plan_id`
(독립 id)·`plan_generation`·`plan_digest`·`incident_id`·`active_set_digest`·`incident_generation`(§11:322)·`scope`·
`severity`·`signals`·`hazards`·`dependency_closure`·`committed_restrictions`·`hard_fences`·`stale_owner_disposition`·
`positions`·`orders`·`potentially_live_quantity`·`external_activity`·`rcl_commitments`·`protection_obligations`·
`proposed_actions: tuple[ContainmentAction, ...]`(각 action의 classifier/authority/capacity/currentness/egress
prerequisite·§11:327)·`controlled_shutdown: ControlledShutdownProcedure | None`(§5.8)·`evidence`·`notification`·
`handoff`·`escalation`·`failure_behavior`·`recovery_barrier_trigger`·`authority_effect: AllFalseIncidentAuthority`.
§11 line 332 "The plan cannot authorize its actions." `_REQUIRED_COVERED` = {plan_id·plan_generation·incident_
generation·active_set_digest}.

**`ControlledShutdownProcedure`(value·§5.8/§12)** — ordered non-authorizing section. 필드: `ordered_steps:
tuple[ShutdownStep, ...]`(§12 line 343–352 10-step)·`deny_before_stop: bool | None`(양극성·§12 step 1)·
`preserved_functions`(HALT/egress-latch/reconciliation/time/evidence/notification/recovery·§12 step 7)·
`hard_fenced_paths`·`prohibited: frozenset[str]`(§12 line 354–362 SHALL-NOT 7-item). value·id 미도출.

**`IncidentRecoveryHandoffPackage`(§5.9/§21)** — immutable non-authorizing package. 필드: `handoff_id`(독립 id)·
`handoff_generation`·`handoff_digest`·`incident_id`·`active_set_generation`·`unresolved_obligations: tuple[
OngoingSafetyObligation, ...]`(§5.9 "every unresolved economic, protection, capacity, evidence, external-activity,
fencing, and recovery obligation")·`recovery_barrier_closed: bool | None`(양극성·sbr 주입·§21)·`accepted_by_recovery_
session: bool | None`(양극성·sbr 주입·§5.9 "No obligation transfers until one current ADR-002-017 Recovery Session
explicitly accepts")·`authority_effect: AllFalseIncidentAuthority`. `_REQUIRED_COVERED` = {handoff_id·handoff_
generation·incident_id}.

**`IncidentClosureDecision`(§5.10/§20)** — immutable single-use. 필드: `closure_id`(독립 id)·`closure_generation`·
`closure_digest`·`incident_id`·`active_set_digest`(§5.10 "one exact current incident and Active Safety Incident Set
digest")·`incident_generation`·`result: ClosureDecisionResult`·`closure_contract_items: tuple[bool | None, ...]`
(§20 12-item·각 양/음극성 §4.3)·`effective_principal_verdict: bool | None`(hag 주입·양극성·§20 item 10)·`single_
use_consumed: bool | None`(음극성·§20:505 "single-use record transition")·`consumed_by_live_authority: bool | None`
(음극성·§20:505 "cannot be consumed by a live-authority path")·`authority_effect: AllFalseIncidentAuthority`. §5.10
"It creates no permissive state"·all-false. `_REQUIRED_COVERED` = {closure_id·closure_generation·incident_id·active_
set_digest}. malformed-model validator: `result is CLOSE_ADMINISTRATIVELY` + incomplete closure_contract ⇒ error(§2.3).

**`SafetySignal`(value·§5.2)**: `signal_id`·`source_identity`·`trustworthy_time_basis`(time 주입)·`classification:
SignalClassificationClass`·`is_material: bool | None`(양극성)·`is_authenticated: bool | None`(양극성·§5.2
"authenticated observation or conservative inference")·`scope_establishable: bool | None`(음극성 — §8:257 unknown
scope⇒UNESTABLISHED). §5.2 verbatim view.

**`CommunicationHonestyLadder`(value·§18:472)**: `assertion_kind: CommunicationAssertionKind`·`claimed_as: CommunicationAssertionKind | None`·`is_message_ack: bool | None`·`treated_as_enforcement_ack: bool | None`(음극성·
§18:472 "never an enforcement acknowledgement"). `communication_assertions_distinguished`(§5.3)이 소비.

**`AnalysisClaim`(value·§18:474·What's-Missing)**: root-cause/replay/postmortem이 무엇을 주장하는지 — `analysis_kind:
str`·`substitutes_prevention: bool | None`(음극성·§5.3 conjunct 4·§6 SIR-INV-014)·`authorizes_past_effect: bool |
None`(음극성·§5.3 conjunct 5·§18:474 "cannot authorize past effects, mark preventive evidence complete, or permit
current operation"). `evidence_communication_status_honest`(§5.3)이 소비.

**`IncidentDependencyClosure`(value·§5.6·22차원 담지·What's-Missing)**: `present_dimensions: frozenset[
ClosureDimension]`(§5.6 22차원 중 실제 present)·`affected_ids_by_dimension: Mapping[ClosureDimension, frozenset[str]]`·
`closure_unknown: bool | None`(음극성·§10:314 "Unknown dependency closure means the broader plausible set remains
contained"). `scope_exact_combined_no_favorable_subset`(§5.2 conjunct 4)이 `present_dimensions ⊇ applicable_
dimensions` 양방향 판정.

**`IncidentScope`(value·§10·exact scope)**: greatest-credible affected scope의 exact 좌표(§8 step 2·§10:303 "cannot
self-exempt") — `scope_by_dimension: Mapping[ClosureDimension, frozenset[str]]`·`self_exempted: bool | None`(음극성·
§10:303)·`wildcard_or_narrowed: bool | None`(음극성·§8:269). `SafetyIncidentRecord.incident_scope`가 담지.

**`OngoingSafetyObligation`(value·§5.11)**: incident workflow 상태를 초과 생존하는 obligation — `obligation_id`·
`kind: str`(position/potentially-live-order/unknown-broker-effect/protection/capacity/reconciliation/evidence/
external-activity/settlement/recovery/monitoring·§5.11 line 148–150 전수)·`resolved: bool | None`(**양극성** —
v1.2 E1·§5.2 동형)·
`transferred_with_owner_and_evidence: bool | None`(양극성·§20 item 4/9). `obligations_survive_shutdown`(§6.4)·closure
contract item 4/9(§6.8b)가 소비.

**`IncidentClassificationInput`(value·§8)**: `classification: SignalClassificationClass`·`policy_class_match: bool |
None`(양극성)·`severity`·`unestablished: bool | None`(음극성 — §8:257 ⇒ `UNESTABLISHED_SCOPE_SEVERITY`). §8 8-class
분류의 입력 view·`restrictive_declaration_non_authorizing`(§5.1)이 소비.

**`ContainmentAction`(value·§11)·`ShutdownStep`(value·§12)**: `ContainmentAction` = `action_kind:
str`(protective/cancel/replace/reconciliation/query/credential/route/config/deployment·§11:326)·`classifier_ref`·
`authority_ref`·`capacity_ref`·`currentness_ref`·`egress_ref`(§11:327 각 action의 separately-owned prerequisite·전부
주입 ref)·`assumed_executable: bool | None`(음극성·§11:333 "not assumed executable"). `ShutdownStep` = `step_ordinal:
int`·`step_kind: str`(§12 line 343–352 10-step)·`completed: bool | None`(음극성·§17:451 "assume not completed where
that is safer"). 둘 다 value·id 미도출·plan/procedure가 tuple로 담지.

**`ClosureIndependenceLadder`(value·§7/§6 SIR-INV-016/§20 item 10)**: `detector: str | None`·`affected_owner: str |
None`·`response_implementer: str | None`·`evidence_producer: str | None`·`performance_beneficiary: str | None`·
`live_armer: str | None`·**`principals_collapsed: bool | None`(hag 주입 verdict·음극성·M5 — hag `effective_principal_
collapse`(`predicates.py:199`) 결과)**·`independence_resolved: bool | None`(**양극성**·명명 반전·§6 SIR-INV-016 line 218 "Unknown
independence denies closure")·`single_operator_variant_supplies_second: bool | None`(hag 주입·양극성·§6 SIR-INV-016 line 218·§20
item 10). **collapse 판정 owner = hag**(§6.9 M5) — 6-role 이름 겹침은 SIR 보조 힌트일 뿐 단독 근거 아님(hag verdict
AND).

**`AllFalseIncidentAuthority`(all-false·§6.8·SIR-INV-001/§7)**: `creates_capacity: bool = False`·`creates_protection:
bool = False`·`creates_safety_authority: bool = False`·`issues_live_authorization: bool = False`·`creates_
transmission_capability: bool = False`·`grants_broker_permission: bool = False`·`clears_halt: bool = False`·
`creates_production_scope: bool = False`·`re_arms: bool = False`·`classifies_protective_action: bool = False`·
`establishes_recovery_readiness: bool = False`. `model_validator` any-True ⇒ `ArtifactIntegrityError`(rcl/egress/cur/
rlp/are/afg/ioc/nontrade/replacement/failuredomain `AllFalse*Authority` 10패키지 선례·grep 실측·**로컬 재표현·import
아님**). **근거**: SIR-INV-001 line 158 verbatim: "Policy, signal, record, severity, plan, task, message, timeline,
evidence, review, and closure artifacts create **no** capacity, protection, Safety Authority, Live Authorization,
Transmission Capability, broker permission, HALT clear, production scope, or re-arm authority." + §7 line 237
(classify protective) + §7 line 237 (recovery readiness).

---

## 3. canonical / ordering REUSE + sibling edge 0 + 형제 경계 + forward seam

### 3.1 canonical REUSE

`tos.canonical` **REUSE**(import): `IndependentIdArtifact`(id ⊥ digest base·`_base.py:328`·실측)·`classify_record_
pair` + `RecordPairKind`{IDEMPOTENT_DUP/CRITICAL_CONFLICT/DIVERGENT_EMISSION/DISTINCT/NOT_COMPARABLE}(`record_pair.py:
52`/`:31`·실측·policy/record/active-set/plan/handoff/closure의 append-only 무결성·same-id/different-bytes 탐지·§22
line 536 "closure replay or duplicate consumption" 방어)·`CanonicalDecimal`(필요 시)·`FrozenModel`·
`EVL1ProvisionalCanonicalizer`(digest 결정론). **canonical만이 base 의존**(WDR/rcl/ioc/evidence/egress/cur/rlp 선례
동형). **주의**: pre-issuance(digest None) 아티팩트는 `classify_record_pair`가 `NOT_COMPARABLE`로 분류(false
conflict 방지·canonical MINOR-1 discipline). restriction-vs-send 런타임 race 탐지는 +Security(SIR-EV-007).

### 3.2 ordering REUSE (Incident Generation·generation floor)

`tos.ordering` **REUSE**(import·`compare_order`·`_ordering.py:86` 실측): policy/record/active-set/plan/handoff/closure
generation 순서·**Incident Generation** monotonic fence(§5.4·§16 line 423)·predecessor floor(§5.3 predecessor)·
generation `>=` shape REUSE(non-revival·§21). **PROMOTE 0**(신규 core 승격 없음 — canonical/ordering이 충분·WDR/cur/
rlp 선례). Incident Generation(§5.4)은 ordering identity이지 wall-clock 아님 — SIR는 clock-free(`MAX_incident_*_ms`
wall-clock age는 secondary +Security/INSTANCE·§8).

### 3.3 REUSE 요약 표

| 대상 | 결정 | 근거 |
|---|---|---|
| `tos.canonical`(IndependentIdArtifact·classify_record_pair·RecordPairKind·CanonicalDecimal·FrozenModel·EVL1ProvisionalCanonicalizer) | **REUSE (import)** | base digest substrate·replay/substitution 구조 분류·전 시리즈 선례·§22 replay 방어 |
| `tos.ordering`(compare_order·Ordering·OrderingEvent) | **REUSE (import)** | Incident Generation floor·predecessor·monotonic fence·WDR/authority 선례 |
| 형제 tos 패키지 전부(sbr·hag·spg·evidence·liveauth·rcl·egress·cur·authority·protective·iap·time·rlp·wdr·afg·orthostate·recon·brokercap·capsule·venue·nontrade·posttrade·failuredomain·are·ioc·dsl·replacement + 미래 stm/sci) | **NO import (sibling edge 0)** | 형제 상호작용은 주입 scalar/digest/bool/verdict/enum-token으로만(§3.4). **rcl edge 0 판정: §3.5**(SIR은 capacity 산술 미수행·WDR 선례) |
| `_NonTruthyStrEnum` | **로컬 재표현 (import 아님)** | cur/egress/hag/iap/nontrade/posttrade/rlp/sbr/venue/wdr `vocabulary.py` **10패키지** 선례(grep 실측·MINOR-1 정정 — **ioc 제외**: ioc는 `ConformanceResult.__bool__`(`vocabulary.py:63`) 동종 봉인이나 `_NonTruthyStrEnum` 명칭 미사용·별도 표기) — 각 패키지 로컬 정의 |
| `AllFalseIncidentAuthority` | **로컬 재표현 (import 아님)** | afg/are/authority/cur/dsl/egress/failuredomain/iap/ioc/liveauth/nontrade/rcl/replacement/rlp/time/wdr `AllFalse*Authority` **16파일** 선례(grep 실측·MINOR-2 정정) |
| iap single-use consumption *shape* | **로컬 재표현 (import 아님)** | `closure_single_use_non_authorizing`가 iap shape REUSE(§6.8·`iap/predicates.py:176` `single_use is not True` 선례) |
| `CommunicationAssertionKind`·`ClosureDecisionResult`·`IncidentLifecycleState` (incident 어휘) | **SIR 로컬 저작** | **실측 tos 전역 미소유**(§0.5 negative-grep·seam 충돌 0) |

### 3.4 sibling edge 0 정책

SIR는 **어떤 형제 tos 패키지도 import하지 않는다.** 형제/미착지 owner의 verdict/generation/digest는 전부 **주입
좌표**(scalar/digest/bool/verdict/enum-token). 이는 (a) **계층 분리**: SIR content 생산 → cur/egress/protective/sbr
boundary 소비(forward·§3.6), (b) firewall allowlist(`closure ⊆ {canonical, ordering, sir}`·§7.1), (c) **rcl edge
회피**(§3.5 — SIR은 capacity 산술 미수행·worst-credible은 주입 opaque·WDR §0.4g 선례)를 강제한다. **PROMOTE 0**.

### 3.5 소유권 / seam 분할표 (본 문서 최대 함정 — 코드 실측·anti-phantom §0.5)

각 행은 **§0.4e 이연 판정 테스트**("형제가 명제-동일 술어를 committed 코드로 보유하는가?" — YES ⇒ 형제 이연·NO ⇒
SIR 저작/Phase-0)를 적용. 존재 인용은 grep file:line, 부재 주장은 negative-grep.

| incident/governance 관련 아티팩트/술어 | 소유 (실측) | SIR 관계 (재저작 금지) |
|---|---|---|
| sbr Recovery Barrier·Recovery Session·`IsolationFacts`·recovery isolation proof | **sbr (#17·ADR-002-017·착지)** | §1:33·§21 "Recovery … behind ADR-002-017's closed Recovery Barrier". SIR = `IncidentRecoveryHandoffPackage`(§5.9) 생산·`recovery_barrier_closed`/`accepted_by_recovery_session` **주입 소비**·재저작 안 함. **최다 상류 참조(6회·survey line 484)** |
| hag Effective Principal collapse·quorum·Governed Single-Operator Re-Arm Variant·`effective_principal_collapse`(`predicates.py:199`)·`quorum_independence_satisfied`(`:283`) | **hag (#20·ADR-002-015·착지)** | §7 line 236·**§6 SIR-INV-016**·§20 item 10·patch v0.2. SIR = collapse/quorum/variant verdict **주입 소비**(`principals_collapsed` = hag verdict·§6.9 M5)·SIR-EV-010 L2+. **2위 상류(5회)** |
| spg Safety Incident Policy activation(ADR-002-014)·Hard Safety Envelope·`bundle_complete`·governed-artifact-kind 토큰(`vocabulary.py:215-216`) | **spg (#12·ADR-002-014·착지)** | §5.1 "immutable ADR-002-014 governed policy"·§7 line 226 "ADR-002-014 activation". SIR = policy activation verdict **주입 소비**·재저작 안 함. **name-collision seal**: spg `SAFETY_INCIDENT_POLICY`/`ACTIVE_SAFETY_INCIDENT_SET`(artifact-**kind 문자열 토큰**·spg가 관장하는 아티팩트 종류 이름) ≠ SIR `SafetyIncidentPolicy`/`ActiveSafetyIncidentSet`(**아티팩트 모델**)·명제 상이(§0.5). **3위 상류(3회)** |
| evidence custody·causal-chain·gap·`GapStatus`·`ReceiptVerificationStatus`·`SegmentCommitmentScheme` | **evidence (ADR-002-016 / register family ERI·착지)** | §18 "ADR-002-016 governs incident evidence integrity". SIR = causal-chain/gap/custody **주입 소비**. **동명이축 seal**: evidence `GapStatus.SUSPECTED`(gap.py:41) ≠ SIR `IncidentLifecycleState.SUSPECTED`(§9)·명제 상이(§0.5). **3위 상류(3회)** |
| liveauth Live Authorization·re-arm 체인 | **liveauth (ADR-002-007·착지)** | §7 line 238·§21 "fresh ADR-002-007/015 governed chain". SIR 주입 소비·발급 안 함(INV-001). **3위 상류(3회)** |
| rcl capacity mutation/serialization·worst-credible·`within_limits` | **rcl (ADR-002-002/012·착지)** | §13 line 380 "RCL remains the sole capacity mutation and serialization authority"·§13 line 382 "incident budget, severity … is never headroom"(WDR `budget_is_not_capacity`/afg `is never capacity` 동형·grep 실측). SIR budget/severity ≠ capacity·worst-credible은 **주입 opaque 좌표**·**edge 0**(WDR §0.4g 선례·SIR L1 capacity 산술 미수행)·계산 +Broker |
| egress final-egress enforcement·credential/route confinement·per-action currentness | **egress (#22·ADR-002-013·착지)** | §16 final egress·§15 line 414 "confined by ADR-002-013"·INV-006. SIR 주입·재저작 안 함·incident-system no-route(§6.1·§22 line 538) |
| cur Active Currentness Vector·`DimensionKey.INCIDENT`(`vocabulary.py:143`·`MANDATED_DIMENSION_FLOOR` 소속 `:172`)·final-egress admission fencing | **cur (#23·ADR-002-024·착지)** | §16 line 433 "consumed through ADR-002-024's currentness protocol". **v1.1 정정(C1·반증)**: cur는 **`DimensionKey.INCIDENT` 차원을 이미 mandated floor로 보유** — SIR은 그 차원의 *값*(Incident Generation·Active Set digest)을 **생산**하고, 차원 completeness/currentness 판정은 **cur 소유**(재저작 0). 이는 forward seam **보강**(WDR §0.4b greenfield 정합·이연 seam 0). name-collision: cur 차원 키 ≠ SIR 아티팩트·값(§0.5 seal 3) |
| authority Safety Authority·HALT·generation fence | **authority (ADR-002-003·착지)** | §7 line 229·§8 step 3. SIR = HALT/restriction/generation **주입 소비**·`recovery_generation_revives_nothing` shape REUSE(§6.3) |
| protective Protective Action Controller·Cancellation Arbiter·de-restriction | **protective (#·ADR-002-001·착지)** | §12 step 6 "obtain Cancellation Arbiter approval"·§14. **forward seam(committed)**: protective `dominating_halt_or_incident`(`predicates.py:395`·필드 `records.py:202`·docstring `:181-183`) SIR 개념 주입 소비(§3.6·M1). SIR = incident-restriction 개념 생산·protective classification 재저작 안 함 |
| iap `single_use`/`exact_intent_only`·consume gate(`predicates.py:176`) | **iap (#15·ADR-002-023·착지)** | **single-use consumption shape 선례**(grep 실측). `closure_single_use_non_authorizing`가 REUSE(재저작 아님·§6.8·§20:505) |
| time Trustworthy Time·timestamp evidence | **time (ADR-002-008·착지)** | §8 step 1 "trustworthy-time evidence"·§18. SIR = time gen **주입 소비**(§5.2 signal timestamp). **3위 상류(liveauth와 병렬·survey는 -007 계상)** |
| rlp demotion·restricted-live/production scope | **rlp (#25·ADR-002-025·착지)** | §19 line 480 "under ADR-002-025". SIR = demotion verdict **주입 소비**·scope 재저작 안 함(§6b·3회 참조) |
| wdr Non-Waivable Boundary·no-post-hoc-waiver·Safety Deviation Decision·**-027 incident generation 주입 소비**(`predicates.py:14`·`state.py:48-49`) | **wdr (#26·ADR-002-026·착지)** | §19 line 482 "ADR-002-026 prohibits post-hoc waiver". SIR = deviation verdict **주입 소비**·§19 "Incident response cannot create a Safety Deviation Decision"(3회 참조). **forward(committed·v1.1 등재)**: wdr가 SIR Incident Generation을 "injected opaque coordinate"로 자기증언 소비(`predicates.py:14`·`state.py:48-49`) — 익명 좌표·`tos.sir` 미참조·greenfield 정합(§0.4b-3) |
| afg action-flow capacity·orthostate position state·recon reconciliation·brokercap broker class | **afg/orthostate/recon/brokercap (착지)** | §11·§13 action-flow·§12 step 5 reconciliation·§15 broker class. SIR 주입 소비·재저작 안 함 |
| 028 incident-handoff(STM)·029 compromise-signal(SCI) | **미착지 owner (-028/-029)** | SIR = incident-handoff 좌표 생산(하류 STM·forward·survey line 341 9회) + SCI compromise를 Safety Signal 주입 소비(§5.4:122)·**내용 재판정 금지(phantom·§0.4f)** |
| **incident lifecycle·classification·Active Set·Containment Plan·Closure Decision·Communication honesty (아티팩트 모델·술어)** | **SIR (greenfield 신규)** | **SIR 아티팩트 모델·술어는 tos 전역 부재 실측**(§0.5 negative-grep: `class .*Incident`/`ClosureDecisionResult`/`CLOSE_ADMINISTRATIVELY` 빈 결과). **spg name-collision seal(v1.1·C1)**: `spg/vocabulary.py:215-216 SAFETY_INCIDENT_POLICY/ACTIVE_SAFETY_INCIDENT_SET`은 spg governed-artifact-**kind 문자열 토큰**(ADR-002-014 config가 관장하는 아티팩트 *종류 이름*)이지 SIR 아티팩트 *모델*이 아니다 — `GapStatus.SUSPECTED` seal과 동형·명제 상이. SIR 저작 정당(재저작 아님·§4·§5·§6) |

### 3.6 forward seam — SIR 생산 · protective/sbr/cur 소비 (committed·본 문서 특유)

**실측(committed 코드·M1 라인 정정)**: SIR이 생산할 "dominating open incident restriction" 개념이 **이미 두 형제에
주입 소비**된다.
- `protective/records.py:202` (DeRestrictionInputs 필드): `dominating_halt_or_incident: bool | None = None`;
  docstring `:181-183` "must be positively `False` (a dominating stronger restriction denies; ADR-002-027 /
  SIR-INV-015 injected verdict)"; 주석 `:201` "no dominating stronger restriction (§8.5; ADR-002-027 / 015)".
- `protective/predicates.py:395`: `return inputs.dominating_halt_or_incident is False` (de-restriction 술어의 마지막
  conjunct — `is False`일 때만 de-restrict 허용).
- `sbr/predicates.py:706-707,731`: "the injected protective `dominating_halt_or_incident` coordinate" ·
  `if dominating_halt_or_incident is not False: return <deny>` (True 또는 None ⇒ deny).

**판정**: 이 좌표의 **극성은 음극성**이다 — `is False`(positively no dominating incident) = clear, `True`/`None` =
deny/restrict(committed·§4.3 극성 표에 반영). SIR은 **incident 절반**(Active Safety Incident Set의 member lifecycle
state로부터 "dominating open incident 존재"를 **구조 파생**·§5.2·§6.3)을 생산하고, HALT 절반(authority-owned)과의
결합 및 protective/sbr로의 주입은 downstream/런타임이다. SIR L1의 `dominating_open_incident_present(active_set) ->
bool`은 **자기신고 플래그가 아니라 `ActiveSetMember` 구조에서 파생**(CLOSED 아닌 restrictive lifecycle_state ∃ ⇒
True; 파생 불능[`is_complete`/`is_current` 미확립] ⇒ **보수적으로 True**·§4.4·§6.3)한다.

> **Ambiguity 처방(리뷰어 지적·명문화)**: `dominating_open_incident_present`의 **negation은 consumer 결합 좌표
> `dominating_halt_or_incident`의 *필요조건 성분일 뿐*이다 — SIR 출력을 그 좌표에 직접 대입하지 않는다.** 결합
> 좌표는 `NOT(dominating_open_incident) AND NOT(dominating_halt)`이며 **HALT 성분은 authority-owned**(§3.5 authority
> 행). SIR은 incident 성분만 생산하고 HALT 성분·결합·주입은 downstream/authority/런타임 소유. 이 "직접 배선 금지"를
> §4.1 canary(`dominating_halt_or_incident` 문자열이 SIR 모듈에 부재)와 §7.2 seam 회귀로 봉인한다.

**이 forward seam이 naming을 WDR보다 강하게 만들지만**(개념이 committed 소비 중), 소비 형태는 익명 bool이라 **sibling
edge는 여전히 0**이고 **naming은 약한 soft load-bearing**이다(§0.4b). **리뷰어 공격 지점(§10.2-⑧)**: "protective가
`tos.sir` 타입을 이연받았으니 inbound edge" — 반론: 익명 `bool | None` 주입·`tos.sir` 미참조·SIR은 개념 성분
생산자·edge 0.

---

## 4. 술어 규율 (canary·극성·reconcile·집합·∅ 양방향)

### 4.1 금지 동사 canary (`test_sir_void_canaries.py`)

SIR 모듈은 **순수·비전송·비변이·clock-free**임을 정적 회귀로 봉인한다: `tos/src/tos/sir/**`에 `send`/`transmit`/
`emit`/`sign`/`arm`/`rearm`(실행)·`mutate`/`reserve`/`release`/`transfer`/`commit_capacity`(capacity)·`declare`/
`contain`/`shutdown`/`close`(**실행 동사** — SIR는 incident *구조 판정*만·실 declaration/containment/shutdown/
closure 아님)·`clear_halt`·`open`/`connect`/`socket`·`time.time`/`datetime.now`/`monotonic`(clock)·`os.environ`·
`exec`/`eval`/`importlib`/`__import__` 문자열이 **부재**함을 grep 회귀로 확인(egress/cur/rlp/wdr `test_*_void_
canaries.py` 동형). incident artifact가 authority/enforcement를 생성하지 않음을 코드 수준에서 증언(SIR-INV-001·§1:17
"do not create economic authority"). **주의**: 술어 이름의 명사형(`restrictive_declaration_*`·`controlled_shutdown_*`)은
허용(판정 술어)이나 동사형 실행 함수는 금지 — canary가 `def declare(`/`def shutdown(` 같은 실행 시그니처 부재를 확인.

**forward-seam 직접 배선 금지 canary(v1.1·§3.6 Ambiguity 처방)**: SIR 모듈에 `dominating_halt_or_incident` 문자열이
**부재**함을 grep 회귀로 확인 — SIR은 incident 성분(`dominating_open_incident_present`)만 생산하고 HALT-결합 좌표
`dominating_halt_or_incident`를 **직접 저작·대입하지 않는다**(HALT 성분은 authority-owned·결합은 downstream). 이
canary가 SIR이 consumer 좌표를 참칭하지 않음을 봉인한다.

### 4.2 truthy-sentinel 봉인 (`test_sir_truthy_sentinel.py`)

`IncidentLifecycleState`·`ClosureDecisionResult`·`IncidentRecordState`·`CommunicationAssertionKind`·
`SignalClassificationClass`·`ClosureDimension`(6종·v1.1 ClosureDimension 추가)는 `_NonTruthyStrEnum`(`__bool__ ⇒
TypeError`). 회귀: 각 멤버에 `bool(x)`가 `TypeError`;
소비 게이트는 `result is ClosureDecisionResult.CLOSE_ADMINISTRATIVELY`·`state is IncidentLifecycleState.CLOSED`
명시 비교만 사용(`if result:`/`if state:` 부재 grep). `DENY`/`HOLD`/`SUSPECTED`/`CONTAINING`/`STABILIZED_NON_LIVE`를
truthy로 오독하는 fail-open 방지. **결과 타입 `__bool__ ⇒ TypeError` 구조봉인**(#14 M1 `ConformanceResult.__bool__`
선례) — 술어가 sentinel 가능 값의 truthiness를 쓰지 않음을 타입이 강제.

### 4.3 극성 규율 (§4.2 — #18/#22/#23/#25 재발 방지 + committed forward-seam 정합·전수 점검)

**핵심 교훈(#18/#22 MAJOR-2·#23/#25 상속)**: `bool | None` 필드에 `if field:`/`if not field:`를 쓰면 `None`이
극성에 따라 **fail-open**한다. **규율(task 명시)**: **음극성 소비의 allow/clear 조건은 `is False`만 사용하고
`is not True`를 절대 쓰지 않는다**(`x is not True`는 `None`을 clear로 오독하는 fail-open — #18/#22/#23/#25 재발
결함). 양극성 allow는 `is True`. `None`은 **양쪽 극성 모두에서 UNKNOWN ⇒ deny/restrict**로 수렴. deny 정규화:
양극성 `is not True`·음극성 `is not False`(둘 다 None ⇒ deny). **committed 정합**: forward seam
`dominating_halt_or_incident`은 protective/sbr이 이미 음극성 `is False`(clear)·`is not False`(deny)로 소비 중(§3.6)
이며 SIR 극성 표가 이를 준수한다.

| 필드 | 극성 | clear(allow) 조건 | deny 조건 | deny 정규화 | 근거 |
|---|---|---|---|---|---|
| `is_material`(signal) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ non-material 취급 시 보수 declare` | §8 "material signal"·§9:290 SUSPECTED restrictive |
| `is_authenticated`(signal) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §5.2 "authenticated observation" |
| `greatest_credible_scope_computed` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §8 step 2·INV-003 |
| `dependency_closure_complete` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §10·§5.6·INV-003 |
| `active_set.is_complete` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny(broader set contained)` | §5.5·§10:311 |
| `active_set.is_current` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §10:311·INV-011 |
| `effective_principal_verdict`(hag 주입) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny closure` | §20 item 10·INV-016 |
| `recovery_barrier_closed`(sbr 주입) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny handoff` | §21·§5.9 |
| `accepted_by_recovery_session`(sbr 주입) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ obligation 미전이` | §5.9 |
| `single_operator_variant_supplies_second`(hag 주입) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ 2nd principal 미충족` | §6 SIR-INV-016:218·§20 item 10 |
| `final_quantity_proof_present` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ potentially-live 유지` | §20 item 3·INV-010 |
| `dominating_halt_or_incident`(**committed forward seam**·§3.6) | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny/restrict` | protective predicates.py:395·sbr predicates.py:731·INV-015 |
| `single_use_consumed`(closure) | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ reject reuse` | §20:505·INV-012 "single-use" |
| `consumed_by_live_authority`(closure) | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny` | §20:505 "cannot be consumed by a live-authority path" |
| `broker_state_unknown`/`order_state_unknown`/`fill_state_unknown`/`exposure_unknown`/`containment_outcome_unknown`/`protection_state_unknown`/`external_activity_unknown`/`shutdown_result_unknown`/`evidence_state_unknown`/`currentness_unknown` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny + worst-credible capacity` | §13·§16:423–431·INV-009 |
| `open_parent_present`/`open_child_present`/`shared_cause_unresolved`/`common_mode_present`(**`ActiveSetMember` 구조 파생**·§5.2 C2) | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny closure` | §10:305–312·§20 item 11·§6 SIR-INV-004 |
| `restriction_workflow_gated`(record·§5.1 conjunct 4) | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny`(선언이 workflow 대기 = 비-restrictive) | §1 line 21·§8 step 3·§6 SIR-INV-002 |
| `severity_label_narrows_scope`(record·§5.1 conjunct 5) | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny`(low-severity가 scope narrow) | §8:269·§6 SIR-INV-003 |
| `independence_resolved`(closure·**양극성**·명명 반전 주의) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny closure` | §6 SIR-INV-016:218 "Unknown independence denies closure" |
| `principals_collapsed`(**hag 주입 verdict**·§6.9 M5) | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny closure` | §6 SIR-INV-016·§22:535 |
| `treated_as_enforcement_ack`(communication) | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ 부정직` | §18:472 "never an enforcement acknowledgement" |
| `is_message_ack`(communication·입력 표지) | **양극성** | `is True` | `is False` / `None` | (표지 — True일 때 enforcement-ack 게이트 발동·§5.3 conjunct) | §18:472 |
| `substitutes_prevention`(analysis·§5.3 conjunct 4) | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ 부정직` | §6 SIR-INV-014·§18:474 |
| `authorizes_past_effect`(analysis·§5.3 conjunct 5) | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny` | §18:474 "cannot authorize past effects" |
| `deny_before_stop`(shutdown·§6.2) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §12 step 1·§6 SIR-INV-007 |
| `re_armed`/`self_reverted`/`revived_prior_authority`/`resumed_trial`/`restored_production_scope` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny`(non-revival) | §21·§6 SIR-INV-015 |
| `scope_establishable`(signal) | **음극성** | — | — | `is False ⇒ UNESTABLISHED_SCOPE_SEVERITY⇒greatest-credible restrict` | §8:257 |

> **주의(양극성으로 정규화한 unknown 필드·MINOR-5 위생)**: `independence_resolved`는 **양극성(명명 반전 주의)** —
> "resolved"가 긍정어이나 fail-closed 방향이 `is True`만 allow(`None`⇒deny·§6 SIR-INV-016:218 unknown⇒deny)이므로 양극성으로
> 소비한다. 반면 `principals_collapsed`(hag 주입 verdict·§6.9)는 음극성(`is False`=collapse 없음=clear). 두 축을
> 분리해 이중 부정 혼동을 차단한다. **폐포 규율(§7.2 field-closure property)**: 위 표의 전 필드가 §2.4 선언 모델에
> 실재하고 술어가 소비함을 property test로 강제(v1.1 upgrade 조건 (a)).

**전수 점검 회귀(`test_sir_polarity.py`)**: 모든 음극성 필드에 대해 `None` 입력이 **restricted/deny로 수렴**함을
property test(hypothesis)로 확인 — `dominating_halt_or_incident=None`이 "no incident"로 fail-open하거나
`broker_state_unknown=None`이 "known"으로 fail-open하는 재발을 구조 봉인. **`is not True`가 음극성 필드 소비에
나타나지 않음을 grep 회귀로 강제**(task 명시 규율). 모든 양극성 필드에 대해 `None`/`False`가 deny로 수렴.
**committed 정합 회귀**: `dominating_open_incident_present`의 출력 negation이 protective/sbr의 `is False` clear
극성과 일치함을 문서-레벨 property로 고정(§3.6).

### 4.4 그룹 reconcile 규율 (#22 MAJOR-1 재발 방지 — 전-entry 보수·no favorable subset·SIR-INV-004) + ∅ 양방향

**핵심 교훈(#22 MAJOR-1)**: 여러 entry가 한 그룹/set에 매핑될 때 판정은 **첫-entry가 아니라 전-entry를 보수적으로
reconcile**해야 한다. SIR의 reconcile 지점(§10 Active Safety Incident Set이 특히 강·SIR-INV-004):

- **`no_favorable_subset`(§5.2·§10:307–312·§6 SIR-INV-004 line 168–170)**: 여러 incident를 **favorable subset으로
  선택하지 않음**(§6 SIR-INV-004 line 170 "A consumer cannot select, union, or close artifacts to create broader
  permission"·§1 line 23 "A consumer SHALL NOT select a favorable subset, close one child while a shared unresolved
  cause remains"·§10 line 307). 결합은 교집합/최광(greatest-credible) 방향·유리한 부분집합 선택 아님.
- **`active_set_is_canonical_union`(§5.5·§10:305)**: Active Safety Incident Set = every open/suspected/overlapping/
  parent/child/common-mode incident의 canonical union(§5.5). member 누락 하나라도 ⇒ **invalid**(§10:311 "the
  remaining Active Safety Incident Set is complete and current"). entry 순서 무관·누락 하나라도 ⇒ deny.
- **Incident Generation floor(§5.4·§16)**: 여러 generation entry ⇒ **MAX(최신 fence)** 채택(§5.4 monotonic·§16
  line 427 "absence of a newer declaration, scope expansion … ordered before the claim/send boundary")·첫-generation
  아님.

**∅ 가드 양방향(M8 재도출·A안·WDR v1.1 shape 상속)**: 공허 통과(vacuous pass)와 **과잉 봉합**(fail-closed 방향
과잉 거부) 모두 결함 클래스다. **v1.0 §9 lifecycle 논증은 삭제한다(M8)** — 개별 incident 상태기계(§9 SUSPECTED→…→
CLOSED)는 **집합 cardinality에 무언명**(한 incident의 상태와 "active-set이 비어도 되는가"는 별개 축)이라 근거가
될 수 없었다. **정정된 근거(2건)**:
1. **§5.5 line 126 "every … applicable to an exact Safety Cell and scope"**: canonical set은 "applicable" 원소의
   집합이며 applicable = ∅이면 정준 표현은 **explicit empty set**이다(무-incident 정상 운영).
2. **§16 line 423–424**: 매 final-egress마다 "current Incident Generation and exact Active Safety Incident Set
   digest"·"absence of an applicable open or suspected restriction"를 **능동 확립**해야 한다 — 무-incident
   상태에서도 Active Set digest가 요구되므로 **∅를 표현 불가하면 §16을 위반**한다. ⇒ explicit-empty는 유효하고
   거부는 결함(과잉 봉합).

**규칙(WDR 792–793 explicit-empty 선례 동형)**:
- `members=() ∧ applicable=∅ ∧ is_complete is True ∧ is_current is True` ⇒ **유효한 explicit-empty**(무-incident
  정상 번들의 명시 표현·거부는 결함).
- `members=() ∧ applicable≠∅` ⇒ **deny**(applicable 누락·§10:311).
- `active_set is None` ⇒ deny(§5.5 canonical set 부재는 판정 불가).
- `applicable=∅ ∧ members≠()` ⇒ deny(surplus/conflicting·both-ways).
- **`dominating_open_incident_present(유효-∅) = False`**(무-incident ⇒ dominating 없음)·**`(파생 불능
  [is_complete/is_current 미확립]) = True`**(보수·§3.6·§6.3). **v1.2 E2**: `members=() ∧ applicable≠∅`
  (malformed-∅)는 1-인자 시그니처가 `applicable`을 볼 수 없어 이 술어의 소관이 아님 — 그 거부는 위 두 번째
  불릿대로 `scope_exact_combined_no_favorable_subset`(§5.2 conjunct 1)이 소유하며 실제로 거부한다(구현 실측).

> **v1.0 phantom 삭제(C1)**: v1.0의 "no incident는 cur/egress `NO_INCIDENT` 소유" 주장은 **삭제**한다 —
> `grep NO_INCIDENT tos/src/tos ⇒ 빈 결과`(오케스트레이터 재확인). ADR §16:429 "Cached `NO_INCIDENT` … is not
> currentness proof"는 **금지 조항**(캐시된 무-incident를 currentness 증거로 쓰지 말라)일 뿐 소유자 지정이 아니다.
> 무-incident의 정준 표현은 위 explicit-empty `ActiveSafetyIncidentSet`이며 **SIR이 저작**한다.
> **리뷰어 공격 지점(§10.2-⑨)**: "빈 active-set 정상 케이스를 SIR이 거부해 과잉 봉합" — 반론: explicit-empty를
> §5.5:126 + §16:423-424 근거로 유효 판정·WDR 792-793 선례·both-ways.

**회귀(`test_sir_reconcile.py`)**: entry/incident 순서 permutation에 대해 verdict 불변(순서 독립) + 가장 보수적
(no-favorable-subset·member-완전·MAX-generation) 지배 + **explicit-empty 유효·malformed-∅ deny 양방향**을 property
test로 확인.

---

## 5. 핵심 L1 술어 (§5 — 3 노른자 + 지지)

> 전 술어 규율 태그: **restrictive-declaration / exact-scope-combined / evidence-honesty predicate substrate only;
> SIR-EV-001/002/009 전부 NOT_IMPLEMENTED(001은 +Security 잔여·전 행 `/3` 통합·adversarial 대기). 전 owner
> verdict/generation/digest는 주입. L1은 declaration/scope/honesty 구조 판정만.**

### 5.1 `restrictive_declaration_non_authorizing` (SIR-EV-001 노른자·§8·+Security 잔여)

**시그니처(계약)**: `restrictive_declaration_non_authorizing(record: SafetyIncidentRecord | None, signal:
SafetySignal | None) -> bool` — **`True` = 선언이 정합**(restrictive·asymmetric·non-authorizing), `False` = 부정합/
판정 불가.

**판정(전부 AND·fail-closed)**:
1. **∅-seal**: `record is None` 또는 `signal is None` ⇒ `False`.
2. **all-false authority(핵심·§6 SIR-INV-001)**: `record.authority_effect`의 전 필드 `is False`(§6.8·
   `AllFalseIncidentAuthority` model_validator any-True ⇒ error). declaration/signal이 capacity/protection/authority/
   Live-Auth/transmission/broker-permission/HALT-clear/production/re-arm/protective-classification/recovery-readiness
   무부여(§1 line 17·§6 SIR-INV-001 line 158). authority-effect True 하나라도 ⇒ deny.
3. **인식·증거 두 축 분리(M6·§5.2:110 disjunction 정합)** — 산문과 conjunct 일치:
   - **인식 축(declaration subject)**: `signal.is_material is True` **OR** `signal.scope_establishable is not True`
     ⇒ 선언 대상(§23 line 549 "Unclassified material signal | declare suspected; deny new risk in greatest credible
     scope"·§8 line 257 "any condition whose scope or severity cannot yet be established conservatively"). 즉
     material이거나 scope 미확립이면 선언한다(비-material이면서 scope 확립된 것만 비대상).
   - **증거 축(authenticated ≠ 필수·disjunction)**: §5.2 line 110 "An authenticated observation **or** conservative
     inference" — signal은 authenticated observation *또는* conservative inference다. `signal.is_authenticated is
     not True`(관측이 아닌 보수 추론)여도 signal 자격은 유지되며 `classification`을 `UNESTABLISHED_SCOPE_SEVERITY`로
     두고 greatest-credible 확장(§8:257). ⇒ authenticated를 AND 필수 게이트로 두던 v1.0의 산문-conjunct 불일치를
     제거(M6).
4. **restrictive/asymmetric(§6 SIR-INV-002)**: declaration이 permissive quorum을 대기하지 않음(§8 step 3 "commits a
   HALT, deny, demotion, quarantine, or fence **without waiting for ordinary workflow**"·§1 line 21 "Formal ticket
   creation, human availability, or classification completion SHALL NOT delay an independently available Human HALT"·
   §6 SIR-INV-002 line 162). 구조: `record.restriction_workflow_gated is False`(음극성·§4.3·§2.4 필드).
5. **low-severity no-narrow(§8:269·비-공허 판정 필드·C2-4)**: `record.severity_label_narrows_scope is False`(음극성·
   §4.3·§2.4 필드) — low-severity label이 Critical invariant를 override하거나 unknown scope를 narrow하면 deny(§8
   line 269 "A low-severity label cannot override a Critical invariant or make unknown scope narrow"). `classification
   is SignalClassificationClass.UNESTABLISHED_SCOPE_SEVERITY`이면 greatest-credible로 확장(§8:257). **v1.0의 공허
   산문 conjunct를 판정 필드로 치환(C2-4).**
6. **greatest-credible scope 파생(양극성·§6 SIR-INV-003)**: `record.greatest_credible_scope_computed is True`(§8 step
   2 "the greatest credible affected dependency scope is calculated conservatively"). `None`/`False` ⇒ deny.

**반환**: 위 전부 성립시에만 `True`. **SIR-EV-001을 닫지 않음**(`/3` 통합 + **+Security signal forgery/suppression/
downgrade/reordering 저항** 잔여 — §22 line 532 "signal suppression, forgery, downgrade, or reordering"은 +Security
런타임). 8-class anchor == `SignalClassificationClass` 필드집합(§7.2 drift·§부록 C).

### 5.2 `scope_exact_combined_no_favorable_subset` (SIR-EV-002 노른자·§10·§5.5·§5.6·가장 깨끗한 L1)

**시그니처(C2-1 전 입력 수용 확장·#21 NT C1/#24 PTF C1 동형 방지)**: `scope_exact_combined_no_favorable_subset(
active_set: ActiveSafetyIncidentSet | None, dependency_closure: IncidentDependencyClosure | None, applicable_
incidents: frozenset[str], applicable_shared_causes: frozenset[str], applicable_dimensions: frozenset[
ClosureDimension]) -> bool`. **완전성 판정 대상(dependency_closure·applicable_dimensions)을 시그니처에 명시** —
`dependency_closure is None` ⇒ deny(판정 불가). **가장 깨끗한 L1 슬라이스**(순수 `EV-L1/3`·좌표 태그 0·survey line 284).

**판정(전부 AND·fail-closed)**:
1. **∅-seal 양방향(§4.4 M8)**: `active_set is None` 또는 `dependency_closure is None` ⇒ `False`. **explicit-empty
   유효**: `active_set.members=() ∧ applicable_incidents=∅ ∧ is_complete is True ∧ is_current is True` ⇒ 무-incident
   정상(§5.5:126·§16:423-424·§4.4). `members=() ∧ applicable_incidents≠∅` ⇒ deny(누락).
2. **`active_set_is_canonical_union`(집합 양방향·§5.5·§10:305·per-member 구조·C2-2)**: `applicable_incidents ⊆
   {m.incident_id for m in active_set.members}` AND 역방향(member에만 있고 applicable 아닌 원소는 conflicting ⇒
   deny). 누락된 open/suspected/overlapping/parent/child/common-mode incident 하나라도 ⇒ **invalid**(§10:311).
   **집합 both-ways**(#10 교훈). `members` tuple 길이/순서/평행성은 §2.3 malformed-model validator가 봉인.
3. **`no_favorable_subset`(§6 SIR-INV-004·핵심·구조 파생·C2-2)**: `open_parent_present`/`open_child_present`/
   `shared_cause_unresolved`/`common_mode_present`를 **`ActiveSetMember` 구조에서 파생**(자기신고 아님) — 어떤 member의
   `parent_id`가 members에 있고 그 parent가 CLOSED 아니면 `open_parent_present=True`; 어떤 member의 `shared_cause_ids`
   ∩ 다른 member의 것이 비어있지 않고 `resolved is not True`이면 `shared_cause_unresolved=True`. 하나라도 `is not
   False` ⇒ child-only 축소/favorable subset 불가(§6 SIR-INV-004 line 170 "cannot select, union, or close artifacts
   to create broader permission"·§1 line 23·§10:307). `applicable_shared_causes ⊆ active_set.shared_dependencies`.
4. **`dependency_closure_complete`(§5.6·§10:303·M4 22차원 복원)**: greatest-credible dependency closure의 **전 22차원**
   (Safety Cell·Capacity Domain·**legal portfolio**·account·broker·venue·instrument·strategy·order·position·
   commitment·protection·credential·route·session·generation·component·artifact·failure-domain·evidence-path·
   external-activity·downstream-consumer — §5.6 line 128–130 전수)이 `dependency_closure`에 present:
   `applicable_dimensions ⊆ dependency_closure.present_dimensions` 양방향. 미표현 차원 ⇒ incomplete ⇒ deny(vacuous-
   True 차단·§10:303 "cannot self-exempt"). `ClosureDimension` closed enum == 22차원(§2.2·§7.2 3자 drift).
5. **combined current(양극성)**: `active_set.is_complete is True` AND `active_set.is_current is True`(§10:311·§4.3).
   `None`/`False` ⇒ deny(§10:314 "Unknown dependency closure means the broader plausible set remains contained").
6. **generation 정합**: `active_set.incident_generation`이 mixed 아님·MAX-generation floor(§4.4·§16:427).

**반환**: 위 전부 성립시에만 `True`. **SIR-EV-002를 닫지 않음**(`/3` 잔여·순수 `EV-L1/3`이나 integration은 Phase-1
밖). **exactness 정직 명기(#25 MAJOR-1 교훈)**: dependency closure 22차원은 §5.6 손전사 closed anchor이나, 실
common-mode 탐지(같은 credential/route/session 공유 판정)는 **dependency-graph engine·+Security/런타임 소유**
(§10.2-⑩·ADR §28 OQ3). **§7.2 drift property(M4)** = 부록 A verbatim(§5.6 line 128–130) ↔ operative list(위 conjunct
4) ↔ `ClosureDimension` enum **3자 일치**.

### 5.3 `evidence_communication_status_honest` (SIR-EV-009 노른자·§18·honesty ladder·SIR-owned 어휘)

**시그니처**: `evidence_communication_status_honest(ladder: CommunicationHonestyLadder | None, analysis_claim:
AnalysisClaim | None) -> bool` — **`True` = evidence/communication이 정직**(prevention·finality·authority를 substitute
하지 않음), `False` = 부정직/판정 불가. `CommunicationHonestyLadder`(§2.4)·`AnalysisClaim`은 root-cause/replay/
postmortem이 무엇을 주장하는지의 value view.

**판정(전부 AND·fail-closed)**:
1. **∅-seal**: `ladder is None` 또는 `analysis_claim is None` ⇒ `False`.
2. **distinction obligation(M7·발명한 강도 전순서 철회·ADR 명시 쌍만)**: §18:472는 9-token을 "distinguish"하라는
   **구별 의무**이지 강도 전순서(total order)가 아니다 — v1.0의 "강한 등급 승격" 판정은 **발명이라 철회**한다. L1-
   decidable 판정은 (i) `ladder.assertion_kind`가 9개 `CommunicationAssertionKind` 중 정확히 하나이고, (ii)
   `ladder.claimed_as`가 present이면서 `claimed_as is not ladder.assertion_kind`(관측 사실을 다른 종류로 라벨)이면
   **구별 위반 ⇒ deny**(§18:472 "SHALL distinguish observed fact, conservative assumption, unresolved UNKNOWN,
   planned action, authorized action, transmitted attempt, broker evidence, verified result, and administrative
   decision"). **강도 순서(어느 assertion이 더 강한가)가 필요하면 policy-owned·§8 Phase-0 이관**(L1 아님).
3. **message-ack ≠ enforcement-ack(§18:472)**: `ladder.is_message_ack is True`인데 `ladder.treated_as_enforcement_
   ack is not False`(True 또는 None) ⇒ **deny**(§18 line 472 "A message acknowledgement is never an enforcement
   acknowledgement"·음극성 `is False`만 clear).
4. **evidence not prevention(§6 SIR-INV-014·§18)**: tickets/pages/chat/dashboards/status/timelines/postmortems/audit/
   replay/root-cause/notification이 preventive/containment enforcement를 substitute하지 않음(§6 SIR-INV-014 line 210
   "support response and learning but do not substitute for preventive or containment enforcement"). 구조:
   `analysis_claim.substitutes_prevention is False`(음극성·`is not False` ⇒ deny).
5. **`analysis_not_prevention`(§18:474)**: `analysis_claim.authorizes_past_effect is False`(음극성·root-cause/replay/
   postmortem이 past effect authorize·preventive evidence complete 표시·current operation permit ⇒ `is not False` ⇒
   **deny**·§18 line 474 "Root-cause analysis, replay, and postmortem findings may improve future controls but cannot
   authorize past effects, mark preventive evidence complete, or permit current operation").
6. **truthy 봉인**: 모든 assertion-kind 비교는 `is` 명시(§4.2·`CommunicationAssertionKind` truthy-untestable).

**반환**: 위 전부 성립시에만 `True`. **SIR-EV-009를 닫지 않음**(`/3` 잔여). **지지 술어 `emergency_evidence_no_
suppress`**: 즉시 restrictive action이 ordinary evidence pipeline을 대기하지 않되(§18 line 470 "SHALL NOT wait for
the ordinary evidence pipeline when an approved emergency evidence path exists"), evidence loss는 incident로 남고
closure를 차단하나 필요한 HALT를 suppress하지 않음(§18 line 470). custody/causal-chain/gap 무결성은 evidence
(ADR-002-016) 주입·재저작 아님(§3.5).

---

## 6. predicate-only substrate (§6 — 닫지 않음·규모 절반 이상·§0.4c) + not-Phase-1 (§6b) + 순수 런타임/인간 (§6c)

> 전 술어 규율 태그: **predicate substrate only; 해당 SIR-EV 전부 NOT_IMPLEMENTED(≥ L2 component-fault +
> +Security/+Broker 대기). L1-decidable 순수 판정을 저작하되 어떤 SIR-EV도 닫지 않는다.** INV 밀도 > L1 행이므로
> 이 §6가 본 계약 규모의 절반 이상이다(§0.4c).

### 6.1 `containment_uses_normal_authority` (§11·§7·SIR-EV-003 substrate·+Security·INV-005)
`containment_uses_normal_authority(plan: IncidentContainmentPlan | None) -> bool`: incident label/severity/priority/
commander approval/emergency status가 protection classify·capacity reserve·broker/venue constraint waive·authority
issue·final egress bypass **불가**(§11 line 333·SIR-INV-005 line 174·§7 line 240 "coordinators … SHALL NOT accumulate
the authorities of the components they coordinate"). all-false 축 + 각 broker-directed action이 normal exact chain
(classifier/authority/capacity/currentness/egress prerequisite·§11:327) present. 실 authority separation은 +Security.
`EV-L2/3+Security`.

### 6.2 `controlled_shutdown_not_broker_finality` (§12·SIR-EV-004 substrate·+Broker+Security·INV-007)
`controlled_shutdown_not_broker_finality(procedure: ControlledShutdownProcedure | None) -> bool`: process stop/scale-
to-zero/disconnect/session-close/credential-revocation/route-removal/deployment-shutdown이 non-acceptance/Final-
Quantity/absence-of-fills/absence-of-external-effect **증명 아님**(§12 line 356 "does not infer broker finality from
process or connection state"·SIR-INV-007 line 182). `deny_before_stop is True`(§12 step 1) + prohibited 7-item(§12
line 354–362 SHALL-NOT — no blind cancel·no forced liquidation·no stop-sole-protection·no capacity-release-on-expiry·
no delete-queues·no clean-shutdown-as-closure) 준수. 실 10-step ordering·hard-fence·late-fill은 **L3+Broker+Security
런타임**(§6b). `EV-L3+Broker+Security`.

### 6.3 `recovery_revives_nothing` (§21·SIR-EV-012 substrate·+Security·INV-015·**committed forward seam**)
`recovery_revives_nothing(inputs) -> bool`: restart/reconnect/restore/rollback/remediation-deployment/root-cause-
completion/evidence-repair/replay-match/reconciliation/time-recovery/workflow-recovery/quiet-time/operator-return이
prior authority revive·trial resume·production scope restore·auto-re-arm **불가**(§21 line 522·SIR-INV-015 line 214).
`re_armed is False` AND `self_reverted is False` AND `revived_prior_authority is False` AND `resumed_trial is False`
AND `restored_production_scope is False`(전 음극성·`is False`만·None ⇒ deny). **forward seam 정합(§3.6·Ambiguity
처방)**: 지지 함수 `dominating_open_incident_present(active_set)`(`ActiveSetMember` 구조 파생·CLOSED 아닌 restrictive
lifecycle_state ∃ ⇒ True; 파생 불능 ⇒ 보수적 True·§4.4)의 negation은 consumer 결합 좌표 `dominating_halt_or_incident`의
**필요조건 성분일 뿐이며 SIR이 그 좌표를 직접 저작·대입하지 않는다**(HALT 성분은 authority-owned·결합은 downstream·
§4.1 canary). fresh ADR-002-007/015 chain은 liveauth/hag 주입(§21·§3.5). 실 hard-fence·Recovery Session은 sbr·+Security.
`EV-L2/3+Security`.

### 6.4 `obligations_survive_shutdown` (§14·§12 step 6·SIR-EV-005 substrate·+Broker·INV-008)
`obligations_survive_shutdown(plan) -> bool`: shutdown이 required protection·RCL commitment·currentness fence·
reconciliation·evidence·notification·settlement·external-activity·trapped-exposure·recovery obligation을 preserve/
deliberately-transfer(§12 step 5·SIR-INV-008 line 186). protection은 blindly cancel 불가(§14 line 388 "SHALL NOT be
blindly cancelled")·Cancellation Arbiter 승인 선행(§12 step 6·protective 주입). failed protection ⇒ ongoing obligation·
exposure represented·no report-safely-closed(§14 line 397). 실 exit feasibility·late-fill·protection replacement는
+Broker. `EV-L2/3+Broker`.

### 6.5 `unknown_remains_conservative` (§13·§16·SIR-EV-006 substrate·+Broker·INV-009·극성 봉합)
`unknown_remains_conservative(state) -> bool`: `broker_state_unknown`·`order_state_unknown`·`fill_state_unknown`·
`exposure_unknown`·`containment_outcome_unknown`·`protection_state_unknown`·`external_activity_unknown`·`shutdown_
result_unknown`·`evidence_state_unknown`·`currentness_unknown` 전부 `is False`(§4.3·§16 line 423·SIR-INV-009 line
190 "blocks new risk and consumes worst-credible capacity where economic effect may exist"). **하나라도 `is not
False`(True 또는 None) ⇒ deny + worst-credible capacity**(주입 opaque 좌표·rcl 계산·**edge 0**). **음극성 소비는
`is False`만**(task 규율). worst-credible 정량화는 +Broker. `EV-L2/3+Broker`.

### 6.6 `broker_finality_unchanged` (§13·SIR-EV-006 substrate·+Broker·INV-010)
`broker_finality_unchanged(tokens) -> bool`: missing-ACK은 non-acceptance **아님**(potentially-accepted 유지·§13 line
372)·Cancel-ACK은 Final Quantity Proof **아님**(§13 line 373·SIR-INV-010 line 194). broker query omission이 order/
fill absence 증명 아님(§13 line 374). 구조 token 판정(missing-ack/cancel-ack sentinel의 truthiness 미사용·§4.2). 실
broker-finality는 +Broker. `EV-L2/3+Broker`.

### 6.7 `economic_effect_outlives_incident_state` (§13·§20·SIR-EV-006 substrate·+Broker·INV-013·authority-shape)
`economic_effect_outlives_incident_state(authority: AllFalseIncidentAuthority | None) -> bool`: **all-false authority
shape 소비**(WDR v1.2 `economic_effect_persists` 교훈 정합 — expiry 필드를 직접 clear로 소비하면 INV 역전 위험) —
`creates_capacity is False` ∧ `classifies_protective_action is False`(None/True⇒deny)로 "signal dismissal·record
expiry·task completion·incident closure·credential/authority expiry·workflow deletion이 orders/attempts/fills/
positions/obligations/external-activity/capacity-consumption을 erase/release 불가"를 강제(§13 line 377 "Incident,
authority, plan, task, credential, session, or evidence expiry does not expire economic effect"·SIR-INV-013 line
206). **v1.0 규율(WDR v1.2 상속)**: `is_expired is False`를 직접 clear로 소비하지 않는다(만료⇒effect 소멸 오독 회피)
— expiry future-use 거부는 §6b send-race·§6.3 non-revival 축이 소유. 실 broker-finality는 +Broker. `EV-L2/3+Broker`.

### 6.8 `closure_administrative_non_permissive` (§20·SIR-EV-010 substrate·+Security·INV-012)
`closure_administrative_non_permissive(closure: IncidentClosureDecision | None) -> bool`: **∅-seal** + `result is
ClosureDecisionResult.CLOSE_ADMINISTRATIVELY`(§4.2 truthy 봉인·DENY/HOLD ⇒ non-closure) AND `all_false_incident_
authority`(§2.4·closure가 safe-state/capacity-release/HALT-clear/UNKNOWN-clear/config-validate/scope-restore/recovery-
satisfy/transmission 무부여·§20 line 503 item 12·SIR-INV-012 line 202) AND `single_use_consumed is False`(음극성·
§20:505 "single-use record transition") AND `consumed_by_live_authority is False`(음극성·§20:505 "cannot be consumed
by a live-authority path") AND 12-item closure contract 전부 present(§20 line 490–503·아래 §6.8b). **iap single-use
consumption shape REUSE**(재저작 아님·`iap/predicates.py:176` 선례). 실 registry replay/quorum은 +Security. `EV-L2/3+Security`.

**§6.8b closure contract 12-item(§20 line 490–503·`closure_contract_items` 전수)**: signals/severity/scope/closure/
common-mode/chronology complete(1)·restriction/hard-fence current(2)·every broker attempt FQP-or-obligation(3)·
positions/orders/fills/external/margin/settlement/protection reconciled-or-retained(4)·containment/shutdown disposition
(5)·Evidence Gaps resolved-or-block(6)·root-cause recorded-not-substituting(7)·remediation/rollback fresh-config(8)·
recovery obligations transferred behind Recovery Barrier(9)·independent Effective Principal review OR Single-Operator
Variant(10·hag 주입)·no open parent/child/overlapping/shared-cause/common-mode(11·음극성)·explicit no-authority
statement(12). 각 item bool | None·§4.3 극성·하나라도 미달 ⇒ deny. **manually-transcribed anchor**(§7.2 drift·§부록 B).

### 6.9 `closure_independence_non_self_exemption` (§20 item 10·§7·§6 SIR-INV-016·SIR-EV-010 substrate·+Security)
`closure_independence_non_self_exemption(ladder: ClosureIndependenceLadder | None) -> bool`: **∅-seal** +
**`ladder.principals_collapsed is False`(M5·hag 주입 verdict·음극성)** — 6-role(detector·affected-owner·response-
implementer·evidence-producer·performance-beneficiary·live-armer)의 Effective Principal collapse **판정 자체는 hag가
소유**(`hag/predicates.py:199 effective_principal_collapse`·`:283 quorum_independence_satisfied`)하고 SIR은 그
verdict를 `principals_collapsed`로 **주입 소비**한다(§6 SIR-INV-016 line 217 "cannot collapse into one Effective
Principal for closure"). `is not False`(True 또는 None) ⇒ deny. **문자열 구조 파생 철회(M5·리뷰어 (a))**: v1.0의
"같은 natural person 식별자 2역 ⇒ collapse" 문자열 판정은 hag `EffectivePrincipalGraph`(같은 인간 2계정을 string
`!=` 너머로 병합·`hag/predicates.py:213-214` fail-closed merge)와 **명제 동일**이므로 hag 귀속이 옳다. SIR이
6-role 이름 겹침을 **보조 구조 힌트**로 계산할 수는 있으나 **단독 근거 금지**(hag verdict AND 보조 힌트·필요-불충분
한계 docstring 의무). AND `independence_resolved is True`(양극성·명명 반전·§6 SIR-INV-016:218 "Unknown independence denies
closure"·None ⇒ deny) AND (2인 미가용 시) `single_operator_variant_supplies_second is True`(hag 주입·§6 SIR-INV-016:218·§20
item 10·patch v0.2). Governed Single-Operator Re-Arm Variant는 satisfaction path 추가일 뿐 independence 의무·unknown-
independence fail-closed를 완화하지 않음(§6 SIR-INV-016 line 218·patch CHANGE-002). 실 quorum counting·Effective Principal 검증은
hag·+Security. `EV-L2/3+Security`.

### 6b. not-Phase-1 얇은 모델 property (SIR-EV-004·007·008·011 — 닫지 않음)
- **incident currentness send-race(§16·SIR-EV-007·`EV-L3+Security`)**: 순서 permutation model(`RESTRICT<SEND ⇒
  deny`·`SEND<RESTRICT<FIRST_BYTE ⇒ potentially-live + capacity-covered`·unknown ⇒ potentially-live·no-blind-retry·
  §16 line 431 "If an incident restriction or scope expansion races a capability claim or first broker byte and
  ordering cannot be proven, the attempt is potentially live, remains capacity-covered, cannot be blindly retried").
  실 cache-free currentness(§16 line 429 "Cached `NO_INCIDENT` … is not currentness proof")·`B_incident_restriction_
  to_egress` bound·deny-first latch는 **전부 +Security 런타임·egress**. WDR-EV-006·CUR-EV-005 동형 계층.
- **controlled shutdown 10-step / partition / compromise(§12·§17·§22·SIR-EV-004/008·`EV-L3+`)**: 10-step ordering
  proof·hard-fence·partition matrix(§17)·compromise expansion(§22)은 통합/적대 L3. §6.2 substrate만 L1.
- **external/manual emergency activity(§15·SIR-EV-011·`EV-L2/3+Broker+Security`)**: `external_activity_conservative` —
  external broker activity가 retroactively compliant TOS transmission 아님(§15 line 408)·operator statement로 RCL
  release 불가(§15 line 411)·HALT clear/close/re-arm 불가(§15 line 412). 실 external procedure·credential custody·
  reconciliation은 +Broker+Security 런타임.

### 6c. 순수 런타임 / 인간 절차 (L1 model property 없음·§0.4c over-realization 경계)
authoritative signal registry + deterministic severity/scope classifier(§8·ADR §28 OQ2·런타임)·dependency-graph +
common-mode engine(§10·OQ3·런타임)·Incident Generation registry + writer-fence + canonical active-set transaction
(§5.4·OQ4·런타임)·restrictive ingress + local latch + final-egress currentness(§16·OQ5·egress 런타임·+Security)·
controlled-shutdown orchestrator ordering proof(§12·OQ6·런타임)·Effective Principal quorum counting + delegation(§7·
OQ7·hag·인간·+Security)·external broker procedure + credential custody(§15·OQ8·+Broker+Security)·evidence/emergency-
journal/notification/timeline/root-cause/closure-retention(§18·OQ9·evidence)·ADR-002-025 demotion + ADR-002-017
Recovery Barrier handoff(§19·§21·OQ10·rlp/sbr)·security controls(§22·OQ11·+Security)·policy activation generation
advance(§5.1·spg). 전부 런타임/인간/+Security/+Broker/형제-owned — §9 Phase-0.

---

## 7. firewall allowlist + 회귀 스위트

### 7.1 import-closure allowlist (`test_sir_import_closure.py`)

`tos.sir`의 전이 import closure는 **`{canonical, ordering, sir}`에 국한**되어야 한다(egress/cur/rlp/wdr `test_*_
import_closure.py` 동형·allowlist 형식). `tools/tos_firewall_check.py`(§3.2 ratified allowlist·default-deny)가
`shared.*`/`services.*`/`cli.*`/외부 수치 라이브러리/동적 escape/**형제 tos 패키지 import(특히 rcl — edge 0·protective
— forward seam은 익명 bool이라 SIR→protective import 부재)**를 **차단**. 이 required check가 green이어야 §0.3
firewall 선언이 능동 성립. **naming(§0.4a)은 약한 soft load-bearing**(firewall 배제 목록 `wdr:47`/`rlp:39`/`cur:51`이
`tos.sir` 명명) — 미래 형제 stm/sci는 allowlist가 자동 배제.

### 7.2 회귀 스위트 (예정 — `tos/tests/sir/`)

`test_sir_declaration.py`(restrictive_declaration_non_authorizing 노른자 1·∅/all-false/material/asymmetric/low-
severity/greatest-credible property + **8-class anchor drift**[§8 line 248–257 == `SignalClassificationClass`])·
`test_sir_scope_combined.py`(scope_exact_combined_no_favorable_subset 노른자 2·∅/집합 양방향/no-favorable-subset/
closure 완전 + **dependency-closure dimension anchor drift**[§5.6 line 128–130])·`test_sir_evidence_honesty.py`
(evidence_communication_status_honest 노른자 3·9-token distinguished·message-ack≠enforcement·analysis≠prevention +
**9-token honesty ladder anchor drift**[§18:472 == `CommunicationAssertionKind`])·`test_sir_lifecycle.py`(**8-state
lifecycle anchor drift**[§9 line 278–286 == `IncidentLifecycleState`]·CLOSED≠live·explicit-empty 부재 고정·§4.4)·
`test_sir_polarity.py`(극성 전수·§4.3·**`is not True` 음극성 부재 grep**·**committed `dominating_halt_or_incident`
극성 정합**)·`test_sir_reconcile.py`(그룹 reconcile 순서독립·no-favorable-subset·MAX-generation·§4.4)·`test_sir_
truthy_sentinel.py`(§4.2·5 enum)·`test_sir_void_canaries.py`(§4.1·실행 동사 부재)·`test_sir_authority.py`(all-false·
model_validator any-True⇒error)·`test_sir_malformed_model.py`(positive-claim + incomplete-scope coexistence seal·
model_construct 우회 2층·§2.3)·`test_sir_closure_contract.py`(**12-item closure contract anchor drift**[§20 line
490–503])·`test_sir_predicate_only.py`(§6 substrate·전부 closes-no-EV 태그)·`test_sir_seam_siblings.py`(**forward
seam 정합** — 지지 함수 `dominating_open_incident_present`의 negation이 `dominating_halt_or_incident`의 **필요조건
성분**임을 확인하되 **직접 대입 부재**를 검증[§3.6 Ambiguity·§4.1 canary]·drift-lock·FD §10.2 교훈으로 형제 심볼
실 resolve)·`test_sir_import_closure.py`(§7.1).

**v1.1 신규 회귀 2종(upgrade 조건 5·리뷰어 요구)**:
- **(a) field-closure property(`test_sir_field_closure.py`)**: §4.3 극성 표·§5/§6 술어가 참조하는 **전 필드가 §2.4
  선언 모델에 실재**하고 그 극성이 표와 일치함을 기계 검증(양방향 — 표에 있으나 모델에 없는 필드 0·모델 소비 필드가
  표에 없음 0). `restriction_workflow_gated`·`severity_label_narrows_scope`·`substitutes_prevention`·
  `authorizes_past_effect`·`deny_before_stop`·`is_message_ack`·`principals_collapsed` 신규 필드 실재 확인.
- **(b) anchor-resolution property(`test_sir_anchor_resolution.py`)**: 문서 전 `§N line M` / `§6 SIR-INV-0NN` 인용의
  **ADR 소속 섹션 일치를 기계 검증**(FD §10.2 교훈 확장 — 존재 주장도 잠금). INV은 §6, currentness는 §16, failure
  matrix는 §23, closure contract는 §20으로 각 앵커가 실제 ADR 섹션에 소속함을 대조(v1.0 §16 INV-016·§23 line 170
  misattribution 재발 방지).

**property-based(hypothesis)** 중심(EV-L1 = model/property). **anchor drift property가 최우선**(8-state lifecycle·
8-class signal·9-token honesty·12-item closure·22-dim closure가 손전사 anchor와 일치·cur/WDR §7.2 교훈). **양방향
canary**: 각 노른자에 대해 "모든 조건 충족 ⇒ True" 및 "각 조건 개별 위반 ⇒ False"를 property로 확인(단방향 seal
방지·FD §9.2 both-ways 상속·explicit-empty 유효·malformed-∅ deny 포함).

**mandated property test (L1 3행·§13 AC 표와 정합)**: SIR-EV-001↔`test_sir_declaration.py`·SIR-EV-002↔`test_sir_
scope_combined.py`·SIR-EV-009↔`test_sir_evidence_honesty.py`가 각 AC(AC-001/002/009)의 L1-decidable 부분을 model/
property로 검증하되 **어떤 SIR-EV도 닫지 않는다**(register status NOT_IMPLEMENTED 유지·§1).

---

## 8. 수치 → Phase-0 / INSTANCE (숫자 하드코딩 0)

SIR 관련 numeric은 **전부 Profile INSTANCE 측정/승인·주입**(현재 전부 `null`/`TBD`·ADR §28 item 12·`VERIFICATION-
PROFILE-002.yaml` INSTANCE):

| 키 (ADR §28 item 12·line 729) | 소유 | 상태 | 근거 |
|---|---|---|---|
| `B_incident_signal_to_restriction` | **SIR** | MEASURE·null | §8 material signal→restriction 지연(런타임·SIR-EV-001/007) |
| `B_incident_restriction_to_egress` | **SIR** | MEASURE·null | §16 restriction→egress deny(런타임·SIR-EV-007) |
| `B_incident_scope_expansion` | **SIR** | MEASURE·null | §8 step 2/§10 scope expansion 지연(런타임) |
| `B_incident_generation_fence` | **SIR** | MEASURE·null | §5.4/§16 Incident Generation→predecessor 무능 증명 |
| `B_controlled_shutdown_hard_fence` | **SIR** | MEASURE·null | §12 shutdown→hard-fence(런타임·SIR-EV-004) |
| `MAX_incident_status_age_ms` | **SIR** | APPROVE·null | §16 stale status ⇒ deny(wall-clock secondary·+Security) |
| `MAX_incident_containment_plan_age_ms` | **SIR** | APPROVE·null | §11 stale plan ⇒ deny(wall-clock secondary) |
| `MAX_incident_closure_evidence_age_ms` | **SIR** | APPROVE·null | §20 stale closure evidence ⇒ deny(trustworthy time 주입) |

**주의**: worst-credible-effect *계산*(§13)은 rcl + +Broker(ADR §29 gate 8)·SIR는 envelope를 주입 opaque 좌표로 소비
(**edge 0**·WDR §0.4g 선례). **L1 아티팩트는 전 numeric이 `null` 상태에서 구성 가능**해야 하며(§2.3 `_REQUIRED_
COVERED` numeric 제외), 누락 numeric claim은 fail-closed(§4.2). broker proper noun/KIS 특정값 부재(broker-agnostic·
정규 텍스트).

---

## 9. Phase-0 / not-Phase-1 체크리스트

### 9.1 Phase-1(EV-L1) 산출물 (본 계약이 실현 지침을 제공)
1. `tos.sir` 패키지(canonical/ordering만 의존·firewall green·**rcl edge 0**·sibling edge 0).
2. 모델: `SafetyIncidentPolicy`·`SafetyIncidentRecord`·`ActiveSafetyIncidentSet`·`IncidentContainmentPlan`·
   `IncidentRecoveryHandoffPackage`·`IncidentClosureDecision`(6 digest-bound) + value(`SafetySignal`·`ActiveSetMember`
   [C2-2]·`IncidentDependencyClosure`·`IncidentScope`·`ControlledShutdownProcedure`·`OngoingSafetyObligation`·
   `CommunicationHonestyLadder`·`ClosureIndependenceLadder`·`IncidentClassificationInput`·`AnalysisClaim`·
   `ContainmentAction`·`ShutdownStep`) + `AllFalseIncidentAuthority` + enum(`IncidentLifecycleState`[8]·
   `ClosureDecisionResult`[3]·`IncidentRecordState`[4]·`CommunicationAssertionKind`[9]·`SignalClassificationClass`[8]·
   **`ClosureDimension`[22·신설]**).
3. 노른자 술어 3종(§5) + 지지 + predicate-only substrate 9종(§6.1–6.9) + 얇은 not-Phase-1 model(§6b).
4. malformed-model validator(positive-claim + incomplete-scope seal)·truthy 봉인·극성(음극성 `is False`만·committed
   forward-seam 정합)·reconcile·all-false·canary·**anchor drift**(8-state lifecycle·8-class signal·9-token honesty·
   12-item closure·dependency-closure dimension) 회귀(§4·§7.2).

### 9.2 Phase-0 / 미착지 / +Security / 런타임 / 인간 (닫지 않음 — 15 항목·ADR §29 gate 1–15 정합)
1. Policy/Record/Active-Set/Containment-Plan+Shutdown/Recovery-Handoff/Closure canonical schema **승인**(§29-1·거버넌스).
2. signal registry + deterministic severity/scope classifier 독립 리뷰(§29-2·+Security·런타임).
3. Incident Generation·active-set publication·owner fencing·restore·final-egress currentness(§29-3·egress 런타임·
   cache-free·SIR-EV-007).
4. Human HALT + automated restrictive ingress incident-workflow 독립(§29-4·authority·런타임).
5. incident coordinator/responder/workflow/evidence/notification/closure identity가 capacity/authority/protective/
   broker 미도달(§29-5·+Security·§22).
6. controlled shutdown deny-before-stop·hard-fencing·broker-ambiguity·RCL/protection/evidence continuity·Recovery
   Barrier closure(§29-6·런타임·SIR-EV-004).
7. broker-directed containment/cancellation/replacement/retry/query/external activity normal chain(§29-7·+Broker·rcl/egress).
8. closure independence/obligations/currentness/evidence/single-use/non-permissive + security review(§29-8·hag·+Security).
9. ADR-002-025 demotion·ADR-002-026 deviation separation·ADR-002-017 recovery handoff no-scope-restore(§29-9·rlp/wdr/sbr).
10. partition/common-mode/stale-owner/conflicting-restore/workflow-compromise/evidence-loss/send-race/alternate-route
    fault injection(§29-10·L3·+Security).
11. SIR-EV-001..012 required-level pass + 독립 review(§29-11·**전 EV**).
12. numeric bound 측정/승인(§8·§29-12·**INSTANCE·+Broker·+Security**).
13. 전 economic effect conservatively represented + capacity-covered(§29-13·rcl).
14. Critical/Major finding 0 + RFC/ADR/VER/Evidence Register traceability(§29-14).
15. ARCHITECTURE-GATE-STATUS 명시 ADR acceptance(§29-15·거버넌스).

**추가 형제/미착지 이관**: Effective Principal quorum + Single-Operator Variant(hag·인간·§6.9)·Live Authorization
발급(liveauth·§7)·Hard Safety Envelope 봉입(spg·§8)·worst-credible-effect 계산(rcl·+Broker·§13)·evidence custody/
causal-chain(evidence·§18)·**028 incident-handoff 하류 배선(STM 착지 후·forward·§0.4f)**·**029 compromise-signal
주입(SCI 착지 후·§5.4:122)**.

**cross-EV 의존(§29-11)**: SIR-EV closure는 sbr/hag/spg/evidence/liveauth/rcl/egress/cur/authority/protective/iap/
time/rlp/wdr 및 -028/-029가 required level에서 pass해야 성립 — Phase-1 범위 밖.

---

## 10. 명명 결정 + 리뷰어 공격 지점

### 10.1 운영자 판단 지점
- **패키지 명명 `tos.sir`**(§0.4a) — register-prefix 1:1·firewall 배제 목록이 이름 지명(wdr:47·rlp:39·cur:51)·
  WDR과 동형 약한 soft load-bearing. runner-up `tos.incident` 기각. naming load-bearing 아님(운영자 치환 가능·설계
  #1 line 164).
- **SIR = greenfield content owner·forward concept-seam 1건 committed**(§0.4b·§3.6) — WDR(#26)와의 대비. SIR은
  inbound 이연 0건이나 protective/sbr이 이미 `dominating_halt_or_incident` 개념을 익명 bool로 소비 중. **독립 리뷰어
  재검토 지점**(RLP 미러 구조를 SIR에 잘못 적용하지 않았는지·forward seam이 inbound edge로 오인되지 않았는지).
- **INV 밀도 > L1 행 — predicate-only substrate 규모 절반 이상**(§0.4c·§6) — over-realization 최대 위험. 닫는
  SIR-EV 0·§6 9종 substrate가 어떤 EV도 닫지 않음. **독립 리뷰어 재검토 지점**(§6 substrate가 L1으로 오주장되지
  않았는지·INV 16/16 매핑 정직성·§12).
- **rcl edge 0 판정**(§3.5·WDR §0.4g 선례) — SIR L1은 capacity 산술 미수행·worst-credible envelope 주입 opaque·
  §13 line 382 "never headroom". **독립 리뷰어 재검토 지점**.
- **not-Phase-1 vs predicate-only 세분**(§1) — 004/007/008만 not-Phase-1(하한 L3·유일 `EV-L3+` 행)·003/005/006/010/
  011/012는 predicate-only(L2 floor·얇은 substrate 존재)·register EV-level과 정합하는 증거기반 세분.

### 10.2 리뷰어 공격 지점 (선제 반론)
1. **"SIR가 RLP처럼 피이연자여야"** — 반론: inbound 이연 실측 0건(§0.4b grep)·SIR은 순수 greenfield 생산자·forward
   concept-seam(protective/sbr)은 익명 bool·`tos.sir` 타입 미참조·RLP 미러 오적용 회피.
2. **"SIR incident lifecycle = evidence GapStatus 중복"** — 반론: evidence `GapStatus.SUSPECTED`(gap.py:41)는 gap
   lifecycle·SIR `IncidentLifecycleState`는 incident lifecycle·**동명이축**(§0.5·§3.5 seal)·명제 상이.
3. **"CommunicationAssertionKind = evidence status 중복"** — 반론: 실측 tos 전역 미소유(`observed_fact|enforcement_
   ack ⇒ 빈 결과`·§0.5)·§18:472 honesty ladder는 evidence custody와 다른 축·SIR 로컬 저작(WDR `WaivedEvidenceStatus`
   선례)·seam 충돌 0.
4. **"SIR가 hag quorum/Effective Principal 재저작"** — 반론: collapse/quorum/Single-Operator-Variant = hag(ADR-002-015)·
   SIR verdict 주입 소비·SIR-EV-010 `EV-L2/3+Security`·edge 0(§3.5·§6.9).
5. **"미착지 028/029 phantom 인용"** — 반론: ADR 원문만·코드 인용 0·주입 opaque generation/signal(§0.4f·§0.2).
6. **"rcl worst-credible을 위해 CapacityVector 필요"** — 반론: SIR L1은 vector 비교 미수행·정량화 +Broker/rcl-owned·
   §13 line 380/382·edge 0이 ADR 정합(§3.5·WDR §0.4g 선례).
7. **"model_construct로 malformed closure/active-set 통과"** — 반론: positive-claim + incomplete-scope validator +
   술어 2층(§2.3·WDR/RLP/egress QCC 동형·#20 상속).
8. **"protective forward seam이 inbound edge"** — 반론: 익명 `bool | None` 주입·`tos.sir` 미참조·SIR은 개념 생산자·
   sibling edge 0·naming 약한 soft load-bearing(§3.6).
9. **"빈 active-set 정상 케이스 과잉 봉합"** — 반론(M8 재도출): explicit-empty `ActiveSafetyIncidentSet`은 **유효**·
   근거 = §5.5:126 "applicable to"(applicable ∅ ⇒ 정준 ∅) + §16:423-424(무-incident에도 매 final-egress마다 Active
   Set digest 능동 확립)·WDR 792-793 선례·both-ways(malformed-∅ deny). **v1.0 "cur NO_INCIDENT 소유" 주장은 phantom
   삭제**(grep 빈 결과·§4.4·§0.5).
10. **"common-mode/dependency-closure 전수 판정을 L1 주장"** — 반론: closure dimension anchor는 손전사(closed)이나
    실 common-mode 탐지(credential/route/session 공유)는 dependency-graph engine·+Security/런타임(§5.2·ADR §28 OQ3).
11. **"음극성 필드 `is not True` 사용"** — 반론: **task 규율 전 적용**(§4.3) — 음극성 allow는 `is False`만·`is not
    True` 부재를 grep 회귀로 강제·committed `dominating_halt_or_incident is False` 정합·#18/#22/#23/#25 재발 봉인.
12. **"over-realization: shutdown ordering/quorum/worst-effect를 L1 주장"** — 반론: 닫는 SIR-EV 0·004/007/008
    not-Phase-1·§6c 순수 런타임/인간 명시(§1·§9.2)·core 3행 중 001만 +Security 잔여 정직 명기.

### 10.3 Open Questions 처분 (리뷰어 제기·v1.1)
1. **INV-006 다중-EV 귀속(§12 SIR-EV-003/004)**: INV은 EV와 1:1 제약이 없다 — 하나의 invariant가 여러 EV의 여러
   측면에 걸칠 수 있다(RCL/egress exclusivity는 containment authority separation[003]과 controlled shutdown[004]
   양쪽에 관여). §12 매핑의 다중-EV 표기는 정합(각주 명시).
2. **survey "not-Phase-1" vs 본 문서 "predicate-only" 세분(§1·§10.1)**: survey는 L1 슬라이스 유무만 이분했고 본
   문서는 register 최소 레벨로 refinement(하한 L2 = predicate-only·하한 L3 = not-Phase-1). 이는 세분화 맵이지 survey
   반박이 아니다(각주 유지).
3. **`IncidentContainmentPlan._REQUIRED_COVERED` digest 규칙**: §2.3에 명문화 — self-`*_digest` 제외·외부 참조
   digest(`active_set_digest`) 포함(위조 불가 바인딩). 처분 완료.
4. **clock-free vs `MAX_incident_*_ms`(§8)**: SIR 술어는 clock-free이고 `MAX_incident_*_ms`는 **주입-age**(SIR이
   계산하지 않고 time/egress 런타임이 계산해 주입하는 wall-clock age)다 — 구현 판정은 §9.2 이관(secondary +Security/
   INSTANCE). 처분: 주입-age 명시.

---

## 11. 선제 defect-class 봉합 (전 시리즈 교훈)

| defect class | 출처 | SIR 봉합 |
|---|---|---|
| grep head 절단 카운트 오류 | #12 | register 전수 파싱(csv line 317–328 직접·§1·naive grep 금지) |
| RLP 미러 오적용(피이연 가정) | #26 WDR | inbound 이연 실측 0건 명기·SIR=greenfield 생산자·forward concept-seam은 익명 bool(§0.4b·§3.6·§10.2-①/⑧) |
| **anti-phantom (부재/존재/광역 grep)** | **#27 FD·본 v1.1 C1 자체 실패** | 부재 negative-grep(`Incident*`/`ClosureDecisionResult`/`NO_INCIDENT` 빈 결과)·존재 file:line·**동명이축 seal 3건**(evidence GapStatus·spg 토큰·cur DimensionKey)·**광역 `-i` 패턴으로 committed 소비 4-clade 재실측**(v1.0 좁은 패턴이 wdr/spg/cur 소비 누락·C1 교정)·anchor-resolution property(§7.2·§0.5·§3.5) |
| truthy-sentinel fail-open | #13·#14 M1 | `_NonTruthyStrEnum` 5종 처음부터·`__bool__ ⇒ TypeError`(§2.2·§4.2) |
| ∅ 단방향 seal / 과잉 봉합 | #8·#15·#26 MAJOR-1 | active-set/closure/scope ∅ 양방향·**explicit-empty 유효(§5.5:126 + §16:423-424 + WDR 792-793 선례)·malformed-∅ deny**(M8 재도출·v1.0 §9 lifecycle 논증·NO_INCIDENT phantom 삭제·§4.4) |
| 집합 단방향 | #10 | applicable ⊆ member 양방향·closure ⊇ affected 양방향(§5.2) |
| enum 전수 매핑 누락 | #21 NT C1 | 8-state lifecycle·8-class signal·9-token honesty·`ClosureDecisionResult` 3-token 전수·closure 12-item 전수(§2.2·§6.8b·§부록) |
| disposition 시그니처 부분 수용 | #21 NT·#24 PTF C1 | closure 술어가 §20 12-item 전 입력 수용·`closure_contract_items` 전수(§6.8b) |
| malformed-model model_construct 우회 | #20 | positive-claim + incomplete-scope validator + 술어 2층(§2.3) |
| 미표현 요소 vacuous pass | #20·#23 | 미표현 closure 차원/member incident ⇒ incomplete(§5.2) |
| phantom id/코드 인용 | #17·#20·#23·#27 | 인용 전 grep·미착지 028/029 코드 0(§0.4f)·seam은 실측 코드 line·존재 주장도 실측(§0.5) |
| **극성 fail-open(unknown/consumed/dominating None)** | **#18·#22 MAJOR-2** | **극성 전수 표 + 음극성 `is False`만·`is not True` 금지·None ⇒ deny 수렴·committed `dominating_halt_or_incident` 정합(§4.3·§3.6)** |
| **그룹 첫-entry/favorable-subset 판정** | **#22 MAJOR-1** | **Active Safety Incident Set 전-entry 보수·no-favorable-subset·MAX-generation·member-완전(§4.4·§5.2)** |
| **INV-012 역전(expiry 직접 소비)** | **#26 WDR v1.2** | `economic_effect_outlives_incident_state`가 all-false authority-shape 소비·expiry 직접 clear 금지(§6.7) |
| enum-drift 참조집합 부정직 | #14 anchor·cur v1.1 | manually-transcribed anchor 명시(8-state·8-class·9-token·12-item·§7.2 drift·§부록) |
| seam 재저작(거버넌스 내용 중복) | #19·#22·#23·#25·#26 | sbr/hag/spg/evidence/liveauth/rcl/egress/cur/authority/protective/iap/rlp/wdr 소유 실측·주입 소비(§3.5·§10.2) |
| rcl edge 과잉(불필요 import) | #26 WDR | SIR L1 capacity 산술 미수행·edge 0·§13 line 382 "never headroom"(§3.5·§10.2-⑥) |
| **over-realization(INV 밀도 > L1 행)** | **본 문서 특유·survey line 305** | **§6 predicate-only substrate 9종이 어떤 SIR-EV도 닫지 않음·닫는 SIR-EV 0·core 3행 중 001만 +Security 잔여 명기(§0.4c·§1·§12)** |
| 과대 주장(authoring=acceptance) | 전 시리즈 | 닫는 SIR-EV 0·"EV-L1-complete 주장 금지"(§1) |

---

## 12. SIR-INV 16/16 전수 매핑 (Phase-1 제공 vs 명시 이연·task 요구)

**계수: 정확히 16종(SIR-INV-001~016·ADR line 156–219·결번 없음·survey line 299). 過(초과) 0·不(누락) 0.** 각 INV에
대해 Phase-1이 제공하는 것(모델/predicate/property) vs 명시 이연(어느 EV 레벨/owner로).

| INV | 제목(ADR line) | Phase-1 L1 제공 | 명시 이연 (레벨/owner) |
|---|---|---|---|
| **001** (156) | Incident Artifacts Are Not Authority | `AllFalseIncidentAuthority`(§2.4) + `restrictive_declaration_non_authorizing` conjunct 2(§5.1) | — (L1 완전 판정·닫는 건 SIR-EV-001 `/3`+Security) |
| **002** (160) | Declaration Is Restrictive and Asymmetric | `restrictive_declaration_non_authorizing` conjunct 4(§5.1·asymmetric·no-permissive-quorum) | 실 restrictive ingress 런타임·+Security(§6c·§29-4) |
| **003** (164) | Exact Greatest-Credible Scope | `scope_exact_combined_no_favorable_subset`·`dependency_closure_complete`(§5.2) + `greatest_credible_scope_computed`(§5.1) | dependency-graph engine·common-mode(런타임·§6c·§29-2) |
| **004** (168) | Combined Incidents, No Favorable Subset | `active_set_is_canonical_union`·`no_favorable_subset`(§5.2·§4.4 reconcile) | 실 combined-response-risk·common-mode(+Security·런타임) |
| **005** (172) | Containment Uses Normal Authority | `containment_uses_normal_authority`(§6.1·predicate-only) | **SIR-EV-003 `EV-L2/3+Security`**(authority separation) |
| **006** (176) | RCL and Egress Exclusivity | `containment_uses_normal_authority` all-false + incident-system no-route(§6.1) | **SIR-EV-003/004**·rcl/egress-owned·**edge 0**(§3.5) |
| **007** (180) | Controlled Shutdown Is Not Broker Finality | `controlled_shutdown_not_broker_finality`(§6.2·predicate-only) | **SIR-EV-004 `EV-L3+Broker+Security`**(10-step·hard-fence 런타임·§6b) |
| **008** (184) | Protection and Obligations Survive Shutdown | `obligations_survive_shutdown`(§6.4·predicate-only) | **SIR-EV-005 `EV-L2/3+Broker`**(protection replacement·+Broker) |
| **009** (188) | UNKNOWN Remains Conservative | `unknown_remains_conservative`(§6.5·음극성 전수·predicate-only) | **SIR-EV-006 `EV-L2/3+Broker`**(worst-credible 정량화·rcl·+Broker) |
| **010** (192) | Broker Finality Rules Do Not Change | `broker_finality_unchanged`(§6.6·predicate-only) | **SIR-EV-006 `EV-L2/3+Broker`**(broker-finality·+Broker) |
| **011** (196) | Incident Generation Is Current at Egress | 얇은 send-race permutation model(§6b) | **SIR-EV-007 `EV-L3+Security`**(cache-free currentness·egress 런타임) |
| **012** (200) | Closure Is Administrative and Non-Permissive | `closure_administrative_non_permissive`(§6.8·all-false·predicate-only) | **SIR-EV-010 `EV-L2/3+Security`**(quorum·registry replay·+Security) |
| **013** (204) | Economic Effect Outlives Incident State | `economic_effect_outlives_incident_state`(§6.7·authority-shape·predicate-only) | **SIR-EV-006/012**·broker-finality·+Broker |
| **014** (208) | Evidence and Communication Are Not Prevention | `evidence_communication_status_honest`·`analysis_not_prevention`(§5.3·노른자 3) | — (L1 판정·닫는 건 SIR-EV-009 `/3`) |
| **015** (212) | Recovery Does Not Revive | `recovery_revives_nothing`(§6.3·음극성 전수·**committed forward seam**·predicate-only) | **SIR-EV-012 `EV-L2/3+Security`**(hard-fence·Recovery Session·sbr·+Security) |
| **016** (216) | Closure Independence and Non-Self-Exemption | `closure_independence_non_self_exemption`(§6.9·**hag 주입 verdict**·M5·predicate-only) | **SIR-EV-010 `EV-L2/3+Security`**(Effective Principal quorum·hag·Single-Operator Variant·+Security) |

**요지(MINOR-4 계수 정합·5+11=16)**: 16 INV 중 **L1 노른자가 직접 닫는 데 기여 = 정확히 5건(001·002·003·004·014·
+§18:472)**; 나머지 **정확히 11건(005·006·007·008·009·010·011·012·013·015·016)은 §6 predicate-only substrate로
저작하되 어떤 SIR-EV도 닫지 않는다**(5+11=16·§0.4c "닫지 않는 predicate substrate 비중이 절반 이상"·survey line
305–306 예측 정합·§14 self-check 정합).

---

## 13. SIR-AC 12/12 ↔ SIR-EV 1:1 표 + L1 3행 mandated property test (task 요구)

**계수: 정확히 12종(SIR-AC-001~012·ADR line 646–693). 1:1 근거(ADR §26 line 644 verbatim)**: "The following cases
are mandatory and **map one-to-one to `SIR-EV-001` through `SIR-EV-012`**." **AC↔EV 제목 12/12 일치**(csv register
title == AC title·survey line 300 실측).

| SIR-AC (ADR line) | ↔ SIR-EV | register 최소 레벨 | Phase-1 분류 | mandated property test (L1 3행만) |
|---|---|---|---|---|
| **AC-001** Restrictive Detection and Declaration (646) | EV-001 | `EV-L1/3+Security` | **core L1** | `test_sir_declaration.py`(§5.1·§7.2 — ∅/all-false/material/asymmetric/low-severity/greatest-credible + 8-class drift) |
| **AC-002** Exact Scope and Combined Incidents (650) | EV-002 | `EV-L1/3` | **core L1** | `test_sir_scope_combined.py`(§5.2·§7.2 — ∅/집합 양방향/no-favorable-subset/closure 완전 + dependency-closure dimension drift) |
| **AC-003** Containment Authority Separation (654) | EV-003 | `EV-L2/3+Security` | predicate-only | (닫지 않음·§6.1 substrate) |
| **AC-004** Controlled Shutdown and Hard Fencing (658) | EV-004 | `EV-L3+Broker+Security` | not-Phase-1 | (닫지 않음·§6.2/§6b) |
| **AC-005** Protection and Ongoing Obligations (662) | EV-005 | `EV-L2/3+Broker` | predicate-only | (닫지 않음·§6.4) |
| **AC-006** UNKNOWN, Broker Finality, and Capacity (666) | EV-006 | `EV-L2/3+Broker` | predicate-only | (닫지 않음·§6.5/§6.6/§6.7) |
| **AC-007** Incident Currentness and Send Race (670) | EV-007 | `EV-L3+Security` | not-Phase-1 | (닫지 않음·§6b send-race) |
| **AC-008** Partition, Common Mode, and Compromise (674) | EV-008 | `EV-L3+Security` | not-Phase-1 | (닫지 않음·§6b) |
| **AC-009** Evidence, Communication, and Status Honesty (678) | EV-009 | `EV-L1/3` | **core L1** | `test_sir_evidence_honesty.py`(§5.3·§7.2 — 9-token distinguished/message-ack≠enforcement/analysis≠prevention + 9-token honesty drift) |
| **AC-010** Independent Non-Permissive Closure (682) | EV-010 | `EV-L2/3+Security` | predicate-only | (닫지 않음·§6.8/§6.9) |
| **AC-011** External Activity and Demotion (686) | EV-011 | `EV-L2/3+Broker+Security` | predicate-only | (닫지 않음·§6b external) |
| **AC-012** Recovery and Non-Revival (690) | EV-012 | `EV-L2/3+Security` | predicate-only | (닫지 않음·§6.3) |

**mandated property test 총계(L1 3행)**: 3종 핵심(`test_sir_declaration`·`test_sir_scope_combined`·`test_sir_evidence_
honesty`) + 지지 회귀 11종(§7.2). **닫는 SIR-EV = 0**(전 mandated test가 L1-decidable 부분만 검증·register status
NOT_IMPLEMENTED 유지·ADR §26 line 644 "Written cases are not completed evidence").

---

## 14. Self-Check (task 요구·독립 비평 리뷰 전 자가 확인)

- [x] **§0.5 anti-phantom 준수(v1.1 C1 자체 실패 교정 반영)**: **v1.0 자찬 철회** — v1.0은 좁은 grep 패턴으로
  committed 소비 3건(wdr/spg/cur)을 놓쳤고 "cur incident 차원 미소유"를 반증당했다. v1.1은 광역 `-i` 패턴으로
  재실측(§0.4b 4-clade)·존재 file:line 교정(`protective/records.py:202`[필드]/`:181-183`[docstring]·`predicates.py:
  395`·`sbr:731`·`wdr/predicates.py:14`·`wdr/state.py:48-49`·`spg/vocabulary.py:215-216`·`cur/vocabulary.py:143`)·
  부재 negative-grep(`class .*Incident`/`ClosureDecisionResult`/`CLOSE_ADMINISTRATIVELY`/**`NO_INCIDENT`**/
  `observed_fact` ⇒ 빈 결과)·**동명이축 seal 3건**(evidence GapStatus·spg 토큰·cur DimensionKey). anchor-resolution
  property(§7.2)로 인용 재고정. **미착지 028/029 코드 인용 0**(§0.4f).
- [x] **극성 표 폐포(§4.3·MINOR-5)**: 양극성·음극성 전 필드 + **v1.1 신규 소비 필드 등재**(`restriction_workflow_
  gated`·`severity_label_narrows_scope`·`substitutes_prevention`·`authorizes_past_effect`·`deny_before_stop`·
  `is_message_ack`·`principals_collapsed`)·`independence_resolved`는 **양극성(명명 반전 주의)** 단일 표기. 음극성
  `is False`만·`is not True` 부재 grep 강제. **committed `dominating_halt_or_incident` 음극성 정합**(§3.6). field-
  closure property(§7.2 (a))로 표↔모델 실재 양방향 검증.
- [x] **INV 16/16 매핑(§12·MINOR-4)**: SIR-INV-001~016 전수·過 0·不 0. **L1 기여 정확히 5건(001·002·003·004·014)
  + predicate-only 11건**(005~013·015·016) = 16(§0.4c·§12·§14 정합).
- [x] **AC 12/12 표(§13)**: SIR-AC-001~012 ↔ SIR-EV-001~012 1:1(ADR §26 line 644 verbatim)·제목 12/12 일치·L1 3행
  mandated property test 명시·닫는 SIR-EV 0.
- [x] **∅ 양방향 검토(§4.4·M8 재도출)**: 공허 통과 차단(active-set None/member 누락 ⇒ deny) + **과잉 봉합 차단
  (explicit-empty 유효)** — **v1.0 §9 lifecycle 논증·cur NO_INCIDENT 소유 주장 삭제**, 정정 근거 = §5.5:126
  "applicable to" + §16:423-424(무-incident에도 Active Set digest 능동 확립) + WDR 792-793 선례.
- [x] **EV-L1-complete 주장 금지(§1)**: 닫는 SIR-EV 0·전 12행 NOT_IMPLEMENTED·001 +Security 조직 게이트 미충족·
  규율 태그 전 주장 부착.
- [x] **구조 파생 > 자기신고(§3.6·§5.2·§6.9)**: `dominating_open_incident_present`·`open_parent_present`류는
  `ActiveSetMember` 구조 파생(C2-2·자기신고 제거)·`principals_collapsed`는 **hag 주입 verdict**(M5·문자열 파생 철회)·
  `active_set_is_canonical_union`은 member 집합 구조 판정.
- [x] **Enum 전수 매핑(§2.2·§6.8b)**: 8-state lifecycle·8-class signal·9-token honesty·3-token closure·**22-token
  `ClosureDimension`(신설)**·`IncidentRecordState` 4멤버 전수·12-item closure contract 전수·`__bool__ ⇒ TypeError`.
- [x] **Broker-agnostic**: broker/order/fill/external activity는 capability class로만·KIS 고유명사 0(§헤더·§13/§15).
- [x] **sibling edge 0 + rcl edge 0(§3.4·§3.5)**: SIR는 canonical/ordering만 import·형제 verdict 주입 소비·capacity
  산술 미수행·forward 소비(protective/sbr/wdr/spg/cur)는 전부 익명 좌표(§3.6·§0.4b).
- [x] **disposition 시그니처 전 입력 수용(C2)**: `scope_exact_combined_no_favorable_subset`가 dependency_closure +
  applicable_dimensions 수용(#21/#24 C1 동형 방지)·closure 12-item 전수·§5.1 공허 conjunct 제거.
- [x] **패치 반영(§헤더)**: v0.2 Single-Operator Re-Arm Variant가 SIR-INV-016(§6.9)·§7·§20 item 10(§6.8b)에 반영·
  patches/ 전수 확인(-027 타깃 1건·`ADR-002-028-Patch-0027.md`는 -028 타깃 무관).

---

## 15. 요약

`tos.sir`는 시리즈의 **safety-incident-governance greenfield content owner(피이연 없음·forward concept-seam 1건
committed)**를 실현한다. WDR(#26)와 동형의 순수 생산자이되 **결정적 차이**: SIR이 생산할 "dominating open incident
restriction" 개념이 **이미 `protective/predicates.py:395`·`sbr/predicates.py:731`에 익명 `dominating_halt_or_incident:
bool | None`으로 committed 소비 중**이다(forward seam·§3.6). 그러나 소비 형태가 `tos.sir` 타입이 아닌 익명 bool이라
**sibling edge = 0·naming은 약한 soft load-bearing**(firewall 배제 목록 wdr:47/rlp:39/cur:51). 본 계약의 core는
**3행(SIR-EV-001 Restrictive Detection and Declaration·002 Exact Scope and Combined Incidents·009 Evidence,
Communication, and Status Honesty)**이며 노른자 술어 3종(`restrictive_declaration_non_authorizing`·`scope_exact_
combined_no_favorable_subset`·`evidence_communication_status_honest`)으로 저작한다. **닫는 SIR-EV = 0**(authoring ≠
acceptance·core 3행 중 001만 +Security 잔여 정직 명기).

**본 문서 최대 규율(WDR와 다른 SIR 특유)**: **INV 밀도 > L1 행**이라 SIR-INV 16건 중 10건이 **어떤 SIR-EV도 닫지
않는 predicate-only substrate**(§6 9종)로 저작되며 이것이 계약 규모의 절반 이상이다(§0.4c·survey line 305–306 예측
정합). 이들을 L1으로 오주장하는 over-realization을 §6·§6c·§12로 봉합한다. 동시에 sbr Recovery Barrier·hag Effective
Principal quorum/Single-Operator Variant·spg policy activation·evidence custody·liveauth Live Authorization·rcl
capacity(**edge 0**·§13:382 "never headroom")·egress final-egress·cur Active Currentness·authority HALT·protective
Cancellation Arbiter·rlp demotion·wdr Non-Waivable Boundary는 **전부 주입 소비**이며 SIR가 재저작하지 않는다
(duplication 경계·§3.5). #18/#22 MAJOR-2(극성 `is False`만·committed forward-seam 정합)·#22 MAJOR-1(reconcile/no-
favorable-subset)·#26 WDR v1.2(INV-012 역전 회피)·#27 FD(anti-phantom·동명이축 seal)를 §4.3–4.4·§6.7·§0.5로 선제
봉합한다.

**비준 기록: 2026-07-27 운영자 위임 자동 비준 대상(v1.0 초안 — 상세는 문서 헤더 비준 기록 블록).** 본 문서는 EV 행을
0개 닫으며 어떤 EV 수용도 주장하지 않는다(§1·§29 gate). tos-spec 무수정·기존 docs/plans 무수정·커밋 없음.

---

## 부록 A — §5 정의 11종 verbatim 전사 (ADR line 104–151·過/不 양방향 계수)

**계수: 정확히 11종(5.1~5.11). 過 0·不 0.** 각 정의는 ADR 원문 손전사.

- **§5.1 Safety Incident Policy** (104–106): "An immutable ADR-002-014 governed policy defining authoritative
  signals, classification, severity, scope closure, required restrictions, containment and shutdown obligations,
  independence, evidence, currentness, escalation, closure, and recovery behavior." → `SafetyIncidentPolicy`(§2.4).
- **§5.2 Safety Signal** (108–112): "An authenticated observation or conservative inference that a safety invariant,
  authority boundary, economic-state assumption, broker contract, protective obligation, currentness fact, evidence
  path, or operational gate may be violated, unavailable, stale, bypassed, or unverifiable." (+line 112 ADR-002-028
  telemetry governance·-029 compromise-as-signal) → `SafetySignal`(§2.4).
- **§5.3 Safety Incident Record** (114–116): "An immutable versioned record of one incident identity, current
  Incident Generation, signals, severity, scope, dependency closure, restrictions, actions, obligations, evidence
  gaps, external activity, owners, and lifecycle state. **It grants no authority**." → `SafetyIncidentRecord`(§2.4·all-false).
- **§5.4 Incident Generation** (118–122): "A monotonic generation fencing earlier incident scope, state, plans,
  closure eligibility, recovery handoff, configuration requests, authority requests, and consumers after any material
  signal, scope, severity, restriction, obligation, evidence, cause, plan, owner, policy, or recovery change."
  (+line 122 ADR-002-029 compromise = Safety Signal) → ordering REUSE(§3.2).
- **§5.5 Active Safety Incident Set** (124–126): "One immutable canonical set of every suspected or open incident and
  shared dependency applicable to an exact Safety Cell and scope. It is restrictive input to separately owned
  authority and currentness controls, not authority itself." → `ActiveSafetyIncidentSet`(§2.4·§5.2·INV-004).
- **§5.6 Incident Dependency Closure** (128–130): "Every Safety Cell, Capacity Domain, legal portfolio, account,
  broker, venue, instrument, strategy, order, position, commitment, protection, credential, route, session,
  generation, component, artifact, failure domain, evidence path, external activity, and downstream consumer that may
  be affected by the signal or response." → `IncidentDependencyClosure`(§2.4·§5.2).
- **§5.7 Incident Containment Plan** (132–134): "An immutable non-authorizing plan that orders restrictions, hard
  fences, reconciliation, protection review, capacity quarantine, evidence preservation, external-activity handling,
  notifications, and recovery prerequisites for one exact Incident Generation." → `IncidentContainmentPlan`(§2.4).
- **§5.8 Controlled Shutdown Procedure** (136–138): "The ordered non-authorizing section of an Incident Containment
  Plan that defines how new economic action is denied and components are fenced or stopped while required protection,
  RCL, reconciliation, evidence, currentness, notification, and external-obligation functions remain safe." →
  `ControlledShutdownProcedure`(§2.4·value).
- **§5.9 Incident Recovery Handoff Package** (140–142): "An immutable non-authorizing package binding the exact
  incident and Active Safety Incident Set generation to every unresolved economic, protection, capacity, evidence,
  external-activity, fencing, and recovery obligation. **No obligation transfers until one current ADR-002-017
  Recovery Session explicitly accepts the exact package**." → `IncidentRecoveryHandoffPackage`(§2.4).
- **§5.10 Incident Closure Decision** (144–146): "An immutable independent result of `DENY`, `HOLD`, or
  `CLOSE_ADMINISTRATIVELY` for one exact current incident and Active Safety Incident Set digest. **It creates no
  permissive state**." → `IncidentClosureDecision` + `ClosureDecisionResult`(§2.2).
- **§5.11 Ongoing Safety Obligation** (148–150): "An unresolved position, potentially-live order, unknown broker
  effect, protection duty, capacity commitment, reconciliation gap, evidence gap, external activity, settlement duty,
  recovery task, or monitoring/fencing duty that survives incident workflow state." → `OngoingSafetyObligation`(§2.4).

## 부록 B — §6 SIR-INV 16종 + §9 lifecycle + §20 closure 12-item verbatim (過/不 양방향)

**INV 계수: 정확히 16종(SIR-INV-001~016·line 156–219). 過 0·不 0.** (제목·매핑은 §12 표.) verbatim 앵커:
- **001** (158) "create **no** capacity, protection, Safety Authority, Live Authorization, Transmission Capability,
  broker permission, HALT clear, production scope, or re-arm authority." → `AllFalseIncidentAuthority`.
- **002** (162) "Declaration and restriction do not wait for a permissive quorum, while closure and authority
  increase require full independent governance." → `restrictive_declaration_non_authorizing`(§5.1).
- **004** (170) "A consumer cannot select, union, or close artifacts to create broader permission." → `no_favorable_subset`(§5.2).
- **009** (190) "blocks new risk and consumes worst-credible capacity where economic effect may exist." → `unknown_remains_conservative`(§6.5).
- **012** (202) "It does not establish safe state, release capacity, clear UNKNOWN or HALT, validate configuration,
  restore scope, satisfy recovery, or authorize transmission." → `closure_administrative_non_permissive`(§6.8).
- **013** (206) "cannot erase orders, attempts, fills, positions, obligations, external activity, or capacity
  consumption." → `economic_effect_outlives_incident_state`(§6.7·authority-shape).
- **015** (214) "cannot revive prior incident-dependent authority, resume a trial, restore production scope, or
  automatically re-arm." → `recovery_revives_nothing`(§6.3·committed forward seam §3.6).
- **016** (217–218) "cannot collapse into one Effective Principal for closure. Unknown independence denies closure.
  Where two distinct natural persons are unavailable, the approved Governed Single-Operator Re-Arm Variant
  (ADR-002-015 §17.1, RFC-001 SAFE-053) MAY supply the second independent effective principal … this adds a
  satisfaction path and does not relax the independence obligation or the fail-closed default on unknown
  independence." → `closure_independence_non_self_exemption`(§6.9·patch v0.2 반영).

**§9 lifecycle 계수: 8-state(line 278–286). 過 0·不 0.** `IncidentLifecycleState`(§2.2): `SUSPECTED → DECLARED →
CONTAINING → STABILIZED_NON_LIVE → INVESTIGATING → REMEDIATION_PENDING → ELIGIBLE_FOR_CLOSURE → CLOSED`. (290)
"`SUSPECTED` is restrictive … not permission to wait." (295) "`CLOSED` is administrative only and does not
transition to `ACTIVE`, `ARMED`, `READY`, or any live state." (296) post-closure signal ⇒ new generation·"does not
edit history." **explicit-empty 상태 부재**(§4.4 과잉 봉합 검토 근거).

**§20 closure contract 계수: 12-item(line 490–503). 過 0·不 0.** `closure_contract_items`(§6.8b): (1) signals/
severity/scope/closure/common-mode/chronology complete·(2) restriction/hard-fence current·(3) broker attempt FQP-or-
obligation·(4) reconciled-or-retained·(5) containment/shutdown disposition·(6) Evidence Gaps resolved-or-block·(7)
root-cause recorded-not-substituting·(8) remediation fresh-config·(9) recovery obligations transferred behind
Recovery Barrier·(10) independent Effective Principal review **or** Governed Single-Operator Re-Arm Variant (patch
v0.2)·(11) no open parent/child/overlapping/shared-cause/common-mode·(12) explicit no-authority statement. (505)
"single-use record transition … cannot be consumed by a live-authority path."

## 부록 C — §8 8-class classification + §18:472 9-token honesty ladder verbatim (過/不 양방향)

**§8 classification 계수: 8-class(line 248–257). 過 0·不 0.** `SignalClassificationClass`(§2.2): (250) Hard Safety
Envelope violation·(251) RCL/writer-fence/capacity/currentness/authority/credential/route/egress bypass·(252) broker/
order/fill/exposure state missing/contradictory/stale/externally-changed·(253) protection loss/replacement gap/
action-flow exhaustion/venue restriction/trapped exposure·(254) Critical Input/config/identity/time/evidence/recovery/
failure-domain compromise·(255) unauthorized live/non-live crossover or external broker activity·(256) failed bound/
security control/independent approval/restricted-live gate·(257) "any condition whose scope or severity cannot yet be
established conservatively" → `UNESTABLISHED_SCOPE_SEVERITY`(§5.1 fail-closed 수렴점).

**§18 honesty ladder 계수: 9-token(line 472). 過 0·不 0.** `CommunicationAssertionKind`(§2.2): observed fact ·
conservative assumption · unresolved UNKNOWN · planned action · authorized action · transmitted attempt · broker
evidence · verified result · administrative decision. (472) "A message acknowledgement is never an enforcement
acknowledgement." → `message_ack_not_enforcement_ack`(§5.3·음극성).

## 부록 D — 매트릭스·차원 계수 (v1.1 신규·What's-Missing·過/不 양방향)

- **§9 lifecycle: 8-state(line 278–286). 過 0·不 0.** `IncidentLifecycleState`(§2.2): `SUSPECTED → DECLARED →
  CONTAINING → STABILIZED_NON_LIVE → INVESTIGATING → REMEDIATION_PENDING → ELIGIBLE_FOR_CLOSURE → CLOSED`.
- **§5.6 dependency closure: 22-dimension(line 128–130). 過 0·不 0.** `ClosureDimension`(§2.2): Safety Cell ·
  Capacity Domain · **legal portfolio**(M4 복원) · account · broker · venue · instrument · strategy · order ·
  position · commitment · protection · credential · route · session · generation · component · artifact · failure
  domain · evidence path · external activity · downstream consumer.
- **§17 Partition/Failure/Compromise matrix: 11-row(line 441–451·헤더/구분자 제외). 過 0·不 0.** signal source
  unavailable · registry/active-set unavailable · coordinator unavailable · control-plane partition · stale
  coordinator/restored DB · conflicting histories · notification fails · evidence path fails · closure workflow
  compromised · incident system broker access · shutdown step ambiguous. → §6.2/§6b not-Phase-1 substrate·L3 런타임.
- **§23 Failure Response Matrix: 12-row(line 549–560·헤더/구분자 제외). 過 0·不 0.** unclassified material signal ·
  unknown/incomplete scope · Incident Generation stale · restriction propagation uncertain · containment action
  rejected · protection unavailable · controlled shutdown incomplete · broker/order state unknown · evidence missing/
  forked · closure quorum unavailable · recovery/remediation succeeds · status page vs owner facts. → §5.1(unclassified
  ⇒ declare·§23:549)·§6.5(unknown)·§6.8(quorum) substrate; 실 fault injection은 §9.2.

---
*문서 끝. 본 설계는 EV 행을 0개 닫으며 어떤 EV 수용도 주장하지 않는다(§1·§29 gate·ADR §26 line 644 "Written cases
are not completed evidence"). tos-spec 무수정·기존 docs/plans 무수정·커밋 없음(비준은 오케스트레이터 소관).*





