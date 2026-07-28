# 설계 문서 #30 — Safety Telemetry Integrity / Continuous Conformance Monitoring / Alert Escalation Governance 계약 (ADR-002-028, EV-L1) (2026-07-29, v1.1)

> **v1.1 개정(2026-07-29, 독립 비평 REVISE 반영 — CRITICAL 2·MAJOR 7·MINOR 10·NIT 4·오케스트레이터 C1/M2/M7
> 재실측 확정·뒤집기 0)**: 사실 계층 43항목 중 41개 무결점(4-clade forward 소비·TAB-INV-006 해소·#28 C1 재발 0)은
> 리뷰 지지로 유지. 두 노른자 fail-open 교정이 핵심. **(C1)** 노른자 1 극성 자기모순 — §5.1 conjunct 3 필터를
> `item.excluded is not True`→**`is False`**로, conjunct 4 게이트를 **`is not False`**(True 또는 None ⇒ approved-proof
> 요구)로 교정(음극성 `excluded=None` unknown-exclusion이 coverage 계상 우회 → STM-INV-002:163 "Missing or **unknown**
> coverage is a gap, not an exemption" 정면 위반이었음 — 내가 §4.3에 세운 "음극성 clear는 `is False`만" 규율의
> 자기위반). `excluded=None` 픽스처를 두 conjunct 각각 mandated. **(C2)** 노른자 2 전면-∅ 공허 True — §5.2 시그니처에
> `required_evaluation_keys`·`applicable_bound_refs` 추가·∅ 양방향(required≠∅ ∧ corpus=() ⇒ deny)·관계 술어 (a)
> 단독의 ∅=True는 유지(presence는 required-측이 소유·STM-INV-004:171 "empty query proves safety" 자기-노른자 위반
> 봉인). **(M1)** digest-bound 3종(`SafetyMonitoringGap`·`SafetyAlertRecord`·`AlertEscalationRecord`) §2.4 skeleton
> 신설 + 각 소비 conjunct(`MonitoringGapKind` 고아 해소·`bound_alert_id` phantom 해소). **(M2)** `CoverageDimension`을
> §2.2 8번째 어휘로 정식 선언(anchor §13:347 11차원+§12:327·"§9 차원" phantom 삭제·enum 7→8·모델 31→32). **(M3)**
> `bound_integrity_preserved` denylist→**whitelist 반전**(#25 RLP MAJOR-1 동형)·`BoundSemanticKind` 9→12(INV-007:183
> local_threshold·hidden_grace_period·favorable_sampling_rule 편입). **(M4)** `ApprovedBoundBinding.bound_binding_
> digest` 결속 + 노른자 2에 subset conjunct(#22 no-favorable-union). **(M5)** 극성 표 폐포(미등재 ≥17필드·판정/표지
> 열 분리)·파라미터 `submitted_monitored_assumptions`→`submitted_assumption_ids` 개명·conjunct 7 3층(admitted_as_
> coverage_item·runtime_falsity_invalidates_property 실소비). **(M6)** ADR 열거→필드 폐포 3건(`AllFalseMonitoring
> Authority`+`satisfies_preventive_control`=14·`MonitoringSuppression` §5.11:151 6금지 복원·`RestrictiveMonitoring
> Signal`+`clears_local_latch`=4)·§7.2 신규 회귀 (c) `test_stm_adr_enumeration_closure.py`. **(M7)** STM-INV 앵커
> 16건 본문행(159·163·…·219) 일괄 교정(off-by-one — 빈 줄 인용)·`§15:151`→`§5.11:151`·`§28 OQ`→`§29 OQ`·§18:408
> phantom→실문장·§7.2(b)에 인용 텍스트 일치 포함. **(MINOR/OQ)** MINOR-2 무조건 해석·MINOR-3 dependency-closure
> 포함-only(초과 무해)·MINOR-8 name-similarity 5후보 추가·MINOR-9 패키지 31·OQ1 미소비 표지 처분(SilenceObservation
> 명시 이연·MonitoringRecoveryInputs 구조 파생)·OQ2 §14:355 17-item closed anchor·OQ3 SendRaceOrdering capability-
> claim 3점 복원(§18:421 실재). upgrade 조건 9건 전부 + §14 Self-Check 실측 재작성(허위 체크박스 4건 정정).
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며 스펙 텍스트
> (RFC/ADR/템플릿/프로파일/register)를 **변경하지 않는다.** 본 문서는 ADR-002-028(Safety Telemetry Integrity,
> Continuous Conformance Monitoring, and Alert Escalation Governance — "STM")을 그린필드 `tos/src/tos/stm/` 신규
> 패키지의 Phase 1(EV-L1) **순수·비전송·비수집 predicate substrate**로 실현하는 계약이다. 코드·git 커밋은 본 문서
> 범위 밖이다(비준은 오케스트레이터 소관).
>
> **비준 기록**: 2026-07-28 운영자 위임 자동 비준 대상(v1.0 초안; 2026-07-25 표준지시 — "남은 ADR 구현 자동 비준
> 승인으로 계속 진행. 끝까지 진행"). 게이트: 독립 비평 리뷰 통과 + upgrade 조건 충족을 오케스트레이터가 검증 후
> "운영자 위임 자동 비준(2026-07-25 지시)"으로 기록·집행. 품질 파이프라인[저작→1차 심사→독립 비평→개정→구현→
> 적대적 코드 리뷰→게이트] 전량 유지. 본 문서는 GOV-001의 세 거버넌스 행위(비준 / ADR acceptance / live
> authorization) 중 어느 것도 수행하지 않으며 어떤 STM-EV/STM-AC/acceptance도 선언하지 않는다.
>
> **패치 반영(전수 확인)**: `tos-spec/src/part-1-foundation/patches/` 전수 스캔 결과 **ADR-002-028을 타깃하는 패치는
> `ADR-002-028-Patch-0027.md` 1건**이다(born-MERGED·patch line 1 "MERGED — see ARCHITECTURE-GATE-STATUS §3.9"·
> Result Version 0.2). 이 패치는 §9에 **assumption-derived intake**(Monitored Assumption·ADR-DEV-011 TAB-INV-006)를
> 삽입하고 Version 0.2·§31 Review History를 부여했으며, patch line 39–41 verbatim "No SAFE-xxx requirement, numeric
> bound, or new EV ID is introduced; the Evidence Register count is unchanged (372)." 즉 **EV 불변**(register 372·
> STM-EV 12행 그대로)이나 **§9 coverage 술어가 이 intake를 반영**해야 한다(§5.1·§12 STM-INV-002). ADR 원문은 이미
> v0.2 반영본이며(§9 line 288·§31 line 710–711) 본 계약은 v0.2 기준이다. **`ADR-002-028-Patch-0027.md`는 파일명이
> "Patch-0027"이나 타깃은 ADR-002-028 자신**이며 -027(SIR) 무관이다(실측·#28 §0 각주 동형 확인).
>
> **broker-agnostic**(project memory `tos-spec-broker-agnostic`): telemetry·conformance·gap·alert·escalation·
> monitor-generation 어휘·술어는 전부 broker-agnostic이다. broker/order/fill/exposure state·credential/route·metrics
> DB/collector/paging vendor는 §16·§19·§22에서 **capability class / non-scope**로만 표현하며 KIS 등 특정 broker·
> 벤더 고유명사는 등장하지 않는다(§4 line 95–97 "It does not select: … a metrics database, collector, message bus, paging
> vendor, dashboard, on-call product, or observability stack").
>
> **선행 문서(의존)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   모든 모델은 설계 #1 §2.4 레이아웃에 놓이고 §3.2 허용목록 안에서만 의존한다(§0.3).
> - [설계 #28 — Safety Incident Declaration/Containment/Shutdown/Closure 계약 (SIR, v1.2)](2026-07-28-tos-safety-incident-design.md)
>   — **직전 완결 모범·거버넌스 content-owner 형식 모범**. STM은 SIR과 동형의 greenfield content owner이며
>   6-artifact digest-bound + all-false authority + 극성 규율 + reconcile + anchor-drift + field-closure/
>   anchor-resolution property + 3치 접기 규율 + 보수 분기 독립 노출 + carrier 모델 §2.4 선언 형식을 상속한다.
> - [설계 #27 — Failure-Domain Isolation 계약 (FD, v1.2)](2026-07-27-tos-failure-domain-design.md) — **§0.5
>   anti-phantom 규율 원천**(부재 주장/존재 주장 양방향 grep).
> - [설계 #26 — Safety-Waiver/Deviation/Residual-Risk 계약 (WDR, v1.2)](2026-07-27-tos-safety-waiver-design.md)
>   — greenfield content owner·explicit-empty ∅ 양방향·economic_effect all-false authority-shape 선례.
> - **형제 소유 경계의 규범 원천**(재저작 금지, §3.5): cur(ADR-002-024)·spg(ADR-002-014)·rlp(ADR-002-025)·
>   sir(ADR-002-027)·egress(ADR-002-013)·evidence(ADR-002-016)·authority(ADR-002-003)·liveauth(ADR-002-007)·
>   rcl(ADR-002-002/012)·protective(ADR-002-001)·time(ADR-002-008)·hag(ADR-002-015)·wdr(ADR-002-026)·iap(ADR-002-023)·
>   sbr(ADR-002-017)·afg(ADR-002-022)·orthostate·recon·brokercap·capsule·venue·nontrade·posttrade·failuredomain·
>   are·ioc·dsl·replacement. 인용은 전부 **committed 코드 실측 signature+라인**이다.
> - **미착지·미인용 형제**: `tos.sci`(ADR-002-029·**병렬 세션 C 소유·untracked 진행 중**)는 **언급만·코드 인용
>   금지**(§0.4f). `tos/src/tos/sci/`·`tos/tests/sci/`는 저작 시점 untracked WIP 산출물이라 file:line 참조 불가.
>
> **규범 원천**: `ADR-002-028` (Status: Proposed, Version 0.2, 711행). ADR §30 line 698 "Authorship, EV-L0 review, a
> monitor definition, dashboard, page, alert acknowledgement, passing replay, incident-free interval, policy approval,
> configuration activation, recovery status, or registered evidence item does not satisfy these gates. This ADR
> authorizes architecture and implementation planning only." 본 계약도 마찬가지다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. **패키지 명명** `tos.stm`(register prefix `STM` 소문자 1:1·terse-lowercase 관행·§0.4a). **naming은 SIR/WDR과
   동형의 약한 soft load-bearing**: `tos.stm`는 **네 firewall allowlist-배제 목록**(`wdr/__init__.py:47`·
   `rlp/__init__.py:39`·`cur/__init__.py:51`·`sir/__init__.py:67`)이 "미래 형제"로 명시 열거(grep 실측·§0.4a).
   runner-up `tos.telemetry`·`tos.monitoring`(기각·§10.1).
2. **핵심 아키텍처 판정 — STM = greenfield telemetry-integrity/conformance-monitoring content owner·inbound 내용
   이연 0건·단 forward committed 소비 4-clade(본 문서 최대 판정·§0.4b·§3.6).** SIR(#28)와 동형의 순수 생산자이되
   **SIR보다 forward 소비가 풍부**: STM이 생산할 좌표(Monitor Generation·Continuous Conformance 결과·Safety
   Monitoring artifact-kind·MONITORING currentness 차원)가 **이미 네 형제에 committed 주입 소비 중**이다 —
   (i) `cur/vocabulary.py:144` `DimensionKey.MONITORING`(mandated floor 소속·`:172`), (ii) `spg/vocabulary.py:217-219`
   3개 governed-artifact-kind 토큰, (iii) `rlp/predicates.py:774-780` `monitoring_not_preventive` + "injected -028
   (STM) coordinate, not landed", (iv) `sir/predicates.py:15`·`sir/state.py:46` "-028 handoff … not landed (injected
   opaque coordinates)". 그러나 소비 형태는 전부 **익명 bool/opaque-generation/문자열-토큰/차원-이름**이며 `tos.stm`
   타입을 이연하지 않는다 — 따라서 STM은 RLP식 피이연자가 아니라 **greenfield 생산자**이고 **sibling edge = 0**이다.
3. **EV 3분류(행별 정직·register 실측)** — **core(L1 슬라이스) 2행 {STM-EV-001 Complete Critical Coverage
   `EV-L1/3+Security`·STM-EV-005 Deterministic Evaluation and Bound Integrity `EV-L1/3+Security`}**(csv line 329·333·
   survey §4.4 line 315·319) / **predicate-only(≥ L2) 8행 {002 `EV-L2/3+Security`·003 `EV-L2/3`·004 `EV-L2/3+Security`·
   006 `EV-L2/3+Security`·007 `EV-L2/3+Security`·008 `EV-L2/3+Security`·010 `EV-L2/3+Broker`·012 `EV-L2/3+Security`}** /
   **not-Phase-1(하한 L3) 2행 {009 Active Currentness and Send Race `EV-L3+Security`·011 Compromise, Fencing, and
   Failure Domains `EV-L3+Security`}**. **닫는 STM-EV = 0건**(§1). "EV-L1-complete 주장 금지".
4. **L1 슬라이스 = 거버넌스 6부작 중 최소(2행)이고 두 행 모두 `+Security` 잔여·좌표 태그 없는 L1 행 0건.**
   `+Security` = **10/12(거버넌스 최고)**·`+Broker` = 1/12(010)·무태그 = 1/12(003). 규율 태그에 "**사이클 산출물
   대비 EV 진전 기여 최저·조직 게이트 전면 미충족**"을 명시(survey §4.4 line 521 경고 승계). 두 L1 노른자를 저작하되
   **어떤 행도 닫지 않는다**(001·005는 `/3` 통합 + `+Security` signal-forgery/suppression 저항 잔여·§5).
5. **중심 L1 술어(§5·2 노른자)** — `critical_coverage_complete_or_gap`(STM-EV-001·노른자 1·§9 Monitor Coverage
   Manifest·STM-INV-001/002/004 + §9 Monitored-Assumption intake)·`deterministic_evaluation_bound_integrity`(STM-EV-005·
   노른자 2·§11·**결정론 property가 핵심** — 동일 (evaluator_digest, canonical_input_digest) ⇒ 동일 result·불일치 ⇒
   fail-closed·STM-INV-007). 전부 순수·fail-closed·전 owner verdict/generation/digest는 주입.
6. **INV 밀도 > L1 행 판정 — 닫지 않는 predicate substrate가 규모 절반 이상(§0.4c·§6).** STM-INV-001..016 16건이
   L1 2행에 대해 불변식 밀도가 높다. 16 INV 중 **L1 2행이 직접 닫는 데 기여하는 것은 001·002·003·004·007 5건뿐**이고
   나머지 **11건**(005·006·008·009·010·011·012·013·014·015·016)은 **≥ L2/L3 substrate로 저작하되 어떤 STM-EV도 닫지
   않는다**. 이 큰 predicate-only substrate가 본 계약 규모의 절반 이상이다(§6).
7. **소유권/seam 분할표(§3.5·§3.6) — 본 문서 최대 함정.** cur(Active Currentness Vector + **`DimensionKey.MONITORING`
   차원 소유**·완전성 판정 소유·**STM은 그 차원의 값 생산자**·forward)·spg(Safety Monitoring Policy activation via
   ADR-002-014·governed-artifact-kind 토큰 소유·name-collision)·rlp(EV-L6 monitor-result non-authorizing 개념 소비·
   demotion·forward)·sir(Incident Generation·incident classification·restrictive fence·**STM handoff signal 소비**·
   forward)·egress(final-egress enforcement·credential/route confinement)·evidence(incident/monitoring evidence
   custody)·authority(Safety Authority/HALT/generation)·liveauth(Live Authorization)·rcl(capacity mutation/
   worst-credible·**edge 0**)·protective(Protective Action Controller)·time(Trustworthy Time)·hag(Effective
   Principal)·wdr(Non-Waivable Boundary)·iap(single-use shape·선례)를 **STM이 재저작하지 않는다**. **sibling edge 0**(§3.4).
8. **선제 봉합** — ∅ 양방향(coverage manifest / applicable obligations / evaluation corpus 부재 ⇒ **판정 방향에
   따라 deny 또는 valid-True**·§4.4 — coverage-completeness ∅ 과 determinism-consistency ∅ 은 **극성이 반대**·둘의
   구별이 본 문서 핵심 ∅ 규율)·집합(coverage ⊇ applicable **양방향**·dependency-closure ⊇ dimensions **포함-only**·
   MINOR-3 초과 무해)·truthy-sentinel 구조 봉인(**8 enum**: `AggregateConformanceResult`·`DashboardStatusToken`·
   `MonitoringGapKind`·`NumericInputState`·`BoundSemanticKind`·`TelemetryCriticality`·`SuppressionLifecycleState`·
   `CoverageDimension` `__bool__ ⇒ TypeError`·ioc
   `ConformanceResult` 선례)·all-false monitoring authority·malformed-model 자기방어(CONFORMING-claim + incomplete-scope
   coexistence seal)·**극성 규율 전 적용(음극성 clear는 `is False`만·`is not True` 금지·전수 표·#18/#22/#23/#25 재발
   방지 + committed `dominating`/`monitoring` 좌표 극성 정합)**·**그룹 reconcile(coverage 전-entry 보수·no favorable
   union·item-level closure)**·**ordering 3치 접기(§4.3·§4.4 — "증명 불가"와 "부정 확정"을 같은 bool 버킷에 접지
   않음)**·**보수 분기 독립 노출**(∅·malformed·unknown 픽스처 명시·§4.4)·manually-transcribed anchor drift(§9 12-item·
   §11 12-token numeric·§12 4-token result·§18 8-fact vector·§23 7-token dashboard·§21 12-row matrix·§8 binding)·
   금지 동사 canary(§4.1).

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR §30은 13개 게이트 조건
  전부 완료 전까지 **Proposed** 유지를 요구한다(line 682–698). ADR acceptance는 오직 *실행된* evidence로만 온다
  (project memory `tos-spec-rfc-authoring-track`).
- **어떤 STM-EV도 완결하지 않는다(§1).** L1 슬라이스 2행(001·005) 모두 staged `EV-L1/3+Security`이고 나머지 10행은
  ≥ L2/L3(+Broker/+Security). Phase 1은 **STM-EV 0건**을 닫는다. "EV-L1-complete 주장 금지." 모든 substrate 주장에
  규율 태그를 붙인다: **"L1 슬라이스 2행(001·005), 전 12행 NOT_IMPLEMENTED 유지, 두 행 모두 +Security 조직 게이트
  미충족·`/3` 통합 대기; L1-decidable 술어를 저작하되 어떤 STM-EV도 EV-L1 증거로 닫지 않는다."**
- **monitoring 런타임을 구현하지 않는다 — STM은 수집기/모니터가 아니라 telemetry "무결성 판정"의 순수 모델이다.**
  telemetry 수집·전송·scrape·collector admission·metric emit·모니터 rule 실행·alert 발송/paging·escalation 전달·
  dashboard 렌더·queue/backpressure·delivery ack 수신은 **전부 런타임/벤더/형제-owned**(ADR §4 line 97 non-scope·
  §29 OQ 1–12·§6c). §5 술어·§2 레코드는 **문서-레벨 frozen 레코드 shape + 순수 판정**만이다.
- **어떤 telemetry 값을 수집·측정·전송하지 않는다.** ADR §1 line 23 "Dashboard labels, aggregate scores, heartbeats,
  service health, cached green state, elapsed quiet time, page acknowledgement, or absence of a new alert are not
  proof that the monitored fact is safe or current." 본 계약의 술어는 *분류·fail-closed*만 하고 실제 수집·전송·
  clock read **메커니즘**은 런타임이 소유한다. "Stale Green State"류 시간성 판정은 **주입 age/generation 좌표로만**
  (clock-free·§8).
- **egress/전송·authority 부여·capacity mutation·incident 선언·protective classification을 구현하지 않는다.** 설계
  #1 §4대로 tos는 정의상 non-transmitting이다. STM 좌표의 authority-effect는 전부 **false 상수**
  (`AllFalseMonitoringAuthority`·STM-INV-001·§1 line 25 CONFORMING "does not approve … issue authority … permit
  transmission … close an incident … re-arm")이며 "monitoring 좌표가 authority로 쓰이면 거부" 술어를 둔다(§4·§5.1).
- **cur의 MONITORING 차원 완전성/currentness 판정을 재저작하지 않는다(#28 C1 트랩 정면 처리).** `cur/vocabulary.py:144`
  `DimensionKey.MONITORING`는 **cur가 이미 mandated floor로 보유**하는 currentness 차원이다(`:172` 실측). STM은 그
  차원의 *값*(Monitor Generation·Continuous Conformance Snapshot digest)을 **생산**하고, 차원 completeness/currentness
  판정은 **cur 소유**다(재저작 0·forward seam·§3.5 cur 행·§3.6). "cur가 MONITORING 차원 미소유"라는 주장은 **반증되며
  금지**한다(#28 SIR가 INCIDENT 차원 "미소유"를 주장해 CRITICAL을 받은 동형 함정·본 문서 §0.5·§3.5에서 실측 등재).
- **신규 VP-002 키를 저작하지 않는다.** ADR §29 OQ 12(Open Implementation Questions)의 `B_safety_telemetry_loss_detect`·
  `B_monitoring_gap_to_*`·`B_critical_alert_delivery`·`B_alert_escalation`·`B_monitoring_generation_fence`·
  `MAX_*_age_ms`·`MAX_monitoring_suppression_duration_ms` bound 승인·측정은 Phase-0 Bounds-Approver 게이트다(§8).
- **수치 하드코딩 0.** telemetry-loss·gap-to-restrict·gap-to-egress·alert-delivery·escalation·generation-fence·
  age bound은 전부 주입/이연이며 어떤 숫자도 모델에 넣지 않는다(CLAUDE.md 설정 기반·§8).
- **미착지 하류 코드 인용 금지** — SCI(-029)는 **병렬 세션 C 소유·untracked**(§0.4f). ADR §8 line 253 ADR-002-029
  release-lineage·§22 compromise-as-signal는 **ADR 원문만·코드 인용 0**. `tos/src/tos/sci/`는 언급만.
- **EV/acceptance/비준 선언 금지.** tos-spec 수정 금지·기존 docs/plans 무수정. 미비준 문서 인용 없음.

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

`tos.stm`는 **순수 모델·술어 패키지**다: `pydantic` + stdlib + `tos.canonical`(digest-bound artifact substrate) +
`tos.ordering`(Monitor Generation 순서)만 import. `shared.*`·`services.*`·`cli.*`·`numpy`/`pandas`/`yaml`·
`os.environ`·동적 escape(`exec`/`eval`/`importlib`/`__import__`) **전면 부재**. **형제 tos 패키지(canonical·ordering
제외 전부: cur·spg·rlp·sir·egress·evidence·authority·liveauth·rcl·protective·time·hag·wdr·iap·sbr·afg·orthostate·
recon·brokercap·capsule·venue·nontrade·posttrade·failuredomain·are·ioc·dsl·replacement + 미착지 sci) 전부 import
부재** — 형제 상호작용은 **주입 scalar/digest/bool/verdict/enum-token/generation**으로만(sibling edge 0·§3.4).
clock·network·egress·persistence·metrics-scrape 미접근. `tos/tests/stm/test_stm_import_closure.py`가 import-closure를
allowlist(`closure ⊆ {canonical, ordering, stm}`)로 강제하고 `tools/tos_firewall_check.py`(§3.2 ratified allowlist·
default-deny) required check와 함께 green이어야 본 선언이 능동 성립. **firewall 구조 확인(실측·#28 §0.3 상속)**:
`.importlinter`는 `[importlinter:contract:tos-operational-firewall]` type=forbidden·source_modules=`tos` 단일 계약
이며 설계 #1 §3.2 "자기 자신 `tos.*`" 허용 조항이 intra-tos self를 커버한다. **신규 stm 패키지는 firewall 도구
무수정 자동 포섭**된다(WDR §0.3 `check:147`·SIR §0.3 선례). 본 문서는 그럼에도 **sibling edge 0건**을 **설계 규율**로
유지한다.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 명명 = `tos.stm` (register-prefix 1:1·naming = SIR/WDR과 동형의 약한 soft load-bearing).**

- **선택(확정) `tos.stm`** — 근거: (1) **register prefix 1:1**: 시리즈가 `STM-INV`/`STM-AC`/`STM-EV`를 사용
  (register 실측 csv line 329–340·ADR §6/§27·VER-002-001 evidence family "STM"). terse-lowercase 관행(rcl·spg·iap·
  hag·are·ioc·afg·sbr·cur·egress·rlp·wdr·sir)과 정합. (2) **firewall 배제 목록이 이름을 이미 지명(약한 load-bearing)**:
  `wdr/__init__.py:47`·`rlp/__init__.py:39`·`cur/__init__.py:51`·`sir/__init__.py:67`이 "미래 형제 `tos.stm`"를
  §7.1 allowlist 자동 배제 대상으로 열거(grep 실측). SIR/WDR과 동형 — 다른 이름 선택 시 기능 orphan은 없고 목록
  주석만 부정확해진다(약한 soft load-bearing). (3) **충돌 없음**: `stm`은 미점유(현 **31패키지** 실측·`ls
  tos/src/tos/` 확인 — **30 tracked + sci untracked**[병렬 세션 C·언급만]·stm 디렉토리 부재·stm 신설 시 32).
- **runner-up `tos.telemetry`·`tos.monitoring`(기각)** — full-word 관행(liveauth·brokercap·orthostate·protective·
  replacement·nontrade·posttrade·failuredomain)도 존재하나 register-prefix 1:1(egress/hag/sbr/cur/rlp/wdr/sir 최근
  선례)이 더 강하다. 또한 `monitoring`은 cur `DimensionKey.MONITORING`·wdr `CompensatingControlKind.MONITORING`과
  이름 혼동을 키운다(§0.5 name-similarity seal). **§10.1 운영자 판단 지점**: `tos.stm` 채택 권고(운영자 치환 가능·
  naming load-bearing 아님·설계 #1 line 164).

**(b) STM = greenfield telemetry-integrity content owner·inbound 이연 0건·forward committed 소비 4-clade (본 문서
최대 판정·SIR보다 풍부).**

- **실측(inbound 이연 seam 0건 / forward committed 소비 4-clade)** — **광역 패턴 재실측**(#28 C1 교훈 — 좁은 패턴
  금지): `grep -rin "tos\.stm|STM[-_]|ADR-002-028|-028|telemetry|conformance|monitor|MONITORING|monitoring_gap|
  alert.escalation" tos/src/tos/ --include="*.py"` 결과 전수 —
  1. **firewall 배제 목록 명명(내용 이연 아님·SIR/WDR과 동형)**: `wdr/__init__.py:47`·`rlp/__init__.py:39`·
     `cur/__init__.py:51`·`sir/__init__.py:67`의 `tos.stm`(4곳).
  2. **cur MONITORING currentness 차원 (committed·value-producer seam·#28 C1 트랩 정면)**: `cur/vocabulary.py:144`
     `DimensionKey.MONITORING = "MONITORING"`·`:172` `MANDATED_DIMENSION_FLOOR = frozenset(DimensionKey) -
     CONDITIONAL_DIMENSION_KEYS`(CONDITIONAL = {RESTRICTED_LIVE_TRIAL}뿐이므로 **MONITORING은 mandated floor 소속**).
     cur는 MONITORING 차원 **완전성/currentness 판정을 소유**하고(`vector_complete`·`policy_covers_mandated_dimensions`)
     STM은 그 차원의 *값*(Monitor Generation·Continuous Conformance Snapshot digest)을 **생산**한다. **익명 차원-이름·
     `tos.stm` 타입 미참조**(§3.5 cur 행·§3.6).
  3. **spg governed-artifact-kind 토큰 (committed·name-collision·name-similarity ≠ proposition-identity)**:
     `spg/vocabulary.py:217-219` `SAFETY_MONITORING_POLICY`·`CRITICAL_TELEMETRY_MANIFEST`·`MONITOR_COVERAGE_MANIFEST`
     — spg governed-artifact-**kind 문자열 토큰**(spg가 ADR-002-014 config로 관장하는 아티팩트-종류 열거이지 STM
     아티팩트 모델 아님·§3.5 name-collision seal·§0.5).
  4. **rlp forward 개념 소비 (committed·EV-L6 monitor-result non-authorizing + injected -028 generation)**:
     `rlp/predicates.py:774` `monitoring_not_preventive(authority: AllFalseTrialAuthority | None)`·docstring `:775-781`
     "an EV-L6 monitor is **detective**, non-authorizing (RLP-INV-015 … 'A `CONFORMING` monitor result remains
     non-authorizing and cannot promote, resume, or re-arm'). … The monitoring generation is an **injected -028
     (STM) coordinate, not landed** (§0.4f)." rlp가 STM의 "CONFORMING monitor result는 non-authorizing" 개념 +
     Monitor Generation을 **주입 all-false authority + opaque 좌표로 자기증언 소비**. **익명 authority/generation
     주입·`tos.stm` 타입 미참조.**
  5. **sir forward handoff 좌표 (committed·SIR가 STM handoff를 anticipate)**: `sir/predicates.py:15`·`sir/state.py:46`
     "the **not-landed -028** / -029 handoff and compromise coordinates are … injected opaque coordinates. sir
     **consumes** every produced fact as an injected scalar/bool/verdict/digest/generation and re-authors none of
     them (sibling edge 0, design #28 §3.5)". SIR가 STM incident-handoff signal을 **주입 opaque 좌표로 예정 소비**.
     STM은 §17에서 SIR에 handoff signal 생산(하류·forward·§3.6). **익명 좌표·`tos.stm` 타입 미참조.**
- **⇒ 판정(greenfield·edge 0·forward 보강)**: 어떤 착지 형제도 telemetry-**content**를 `tos.stm`로 이연하지 않는다
  (RLP식 피이연 0건). 단 STM이 생산할 것의 **좌표/개념**은 이미 4-clade committed 소비 중이다 — (2) cur MONITORING
  차원(값 종류 이름), (3) spg governed-artifact-kind 토큰(아티팩트 종류 이름), (4) rlp의 monitor-result-non-authorizing
  개념 + Monitor Generation(익명 authority/generation), (5) sir의 -028 handoff(익명 opaque 좌표). 소비 형태가 전부
  `tos.stm` 타입이 아닌 익명 bool/generation/문자열-토큰/차원-이름이라 **sibling edge = 0**이고, STM은 그 좌표들의
  *값·완전성 판정·아티팩트*를 소유하는 **SIR식 greenfield 생산자**(RLP 미러 아님)다. STM이 소유하는 잔여 =
  **safety-telemetry-integrity / continuous-conformance-monitoring / alert-escalation governance 계약 전체**(§1·§5·§6).
  **리뷰어 공격 지점(§10.2-①)**: "STM이 RLP처럼 피이연자여야" — 반론: inbound content 이연 0건·forward 소비는 전부
  익명 좌표·STM은 순수 생산자·naming은 약한 soft load-bearing.

**(c) INV 밀도 > L1 행 — 닫지 않는 predicate substrate가 규모 절반 이상(SIR §0.4c 상속·본 문서 특유 규율).**
STM-INV 16건 중 L1 2행이 닫는 데 기여하는 것은 **정확히 5건(001·002·003·004·007)**이고, 나머지 **11건**(005
UNKNOWN-restrictive·006 common-mode·008 suppression·009 alert-orthogonal·010 loss-preserves-negative·011
authority-ownership·012 generation-negative-gate·013 broker-finality·014 evidence-not-prevention·015 recovery-non-
revival·016 stale-writer-fence)은 **≥ L2/L3 substrate**다. 이들을 L1으로 오주장하면 안 된다(over-realization). 그러나
각 INV의 **L1-decidable 순수 판정 부분**(all-false·극성·구조 파생·no-default-green·no-favorable-union)은 저작하되
**어떤 STM-EV도 닫지 않는 predicate-only substrate**(§6)로 정직 분류한다. **이 정직한 경계가 본 문서의 최대 규율**
이다(SIR/WDR over-realization 경계 상속). survey §4.4 line 521 "L1 6건 중 최소·+Security 10/12로 최고" 경고를 정면
승계한다.

**(d) canonical `IndependentIdArtifact` + `classify_record_pair` REUSE (SIR/WDR 선례).** STM의 7개 digest-bound
아티팩트(Policy·Critical-Telemetry-Manifest·Coverage-Manifest·Conformance-Snapshot·Monitoring-Gap·Alert-Record·
Escalation-Record)는 **append-only ledger citizen**이다(§5.1 "immutable governed policy"·§5.3 "immutable registry"·
§5.4 "immutable mapping"·§5.6 "immutable Continuous Conformance Snapshot"·§5.7 "immutable record"·§5.8/§5.9 "immutable
non-authorizing record"). ⇒ `IndependentIdArtifact`(id ⊥ digest·`_base.py:328`) 채택 + `classify_record_pair`
(`record_pair.py:52`)로 same-id/different-bytes 위조/replay를 `CRITICAL_CONFLICT` 탐지(SIR/rcl/egress/cur/rlp/wdr
선례·§22 line 476 "raw and derived telemetry integrity" 방어). **§5.9 AlertEscalationRecord single-binding**(§5.9
line 143 "records cannot be unioned, substituted, or used to narrow the alert scope or reset its first-observed
time")은 iap single-use shape로 봉인(§3.5 iap 행).

**(e) ordering REUSE — Monitor Generation monotonic fence.** §5.5 Monitor Generation은 "A monotonic generation
identifying the current Safety Monitoring Policy, manifests, approved monitor logic, owners, and active restrictive
state … Restore, rollback, failover, replacement, or policy change cannot reuse a superseded generation"(line
126–127)다. `tos.ordering`(`compare_order`·`_ordering.py:86`)를 REUSE해 generation floor·predecessor·monotonic
fence·stale-writer 봉인(STM-INV-016·§12 line 337 "A stale owner is treated as potentially active until hard fencing
is proven")을 표현. Monitor Generation은 ordering identity이지 wall-clock 아님 — STM은 clock-free(`MAX_*_age_ms`
wall-clock age는 secondary +Security/INSTANCE·§8). **PROMOTE 0**(canonical/ordering 외 신규 core 없음).

**(f) 미착지 하류 029/SCI 차원 (phantom 봉합·언급만).** **실측**: `tos/src/tos/sci/`는 **병렬 세션 C 소유·untracked
진행 중**(저작 시점 git-tracked 아님·언급만·코드 인용 금지). ADR §8 line 253이 ADR-002-029(SCI) release-lineage를
Critical Telemetry Manifest binding에 열거하고, §22 line 481이 compromise expansion을 기술한다.
- **판정: STM은 이를 주입 generation/digest/signal 좌표로만 소비/생산.** ADR 원문만 참조하고 **SCI 코드 인용 0**
  (미착지·untracked·phantom 금지). SCI release-attestation은 opaque 주입 Critical Telemetry로 수용하고, STM이 생산할
  좌표(하류 SCI 소비·forward)이나 SCI 미착지라 배선 없음. **리뷰어 공격 지점(§10.2-⑤)**: "미착지 029/SCI 오인용" —
  반론: ADR 원문만·코드 0·주입 좌표·§0.2 NO-list·SCI는 언급만.

### 0.5 anti-phantom 규율 (FD #27·SIR #28 §0.5 상속 — 부재 주장·존재 주장 양방향 grep·광역 패턴)

**시리즈 교훈(defect class `anti-phantom`·FD #27·#28 C1)**: 존재 인용은 grep했으나 **부재 주장**("형제 미소유"·"타입
없음"·"tos 전역 무주인")을 grep하지 않은 **검증 비대칭**이 FD v1.0 REJECT의 결함군이었고, 대칭으로 **미검증 존재
주장**도 사각이었다. **#28 C1 특유 교훈**: 좁은 grep 패턴(`tos.sir`만)이 committed 소비(cur `DimensionKey.INCIDENT`
등)를 놓쳐 "cur가 incident 차원 미소유"를 오주장 → CRITICAL. **본 문서는 그 동형 트랩을 정면 처리**한다: cur는
`DimensionKey.MONITORING`을 **이미 보유**(mandated floor·`cur/vocabulary.py:144`·`:172` 실측)하며, STM은 그 차원의
*값 생산자*일 뿐 **완전성 판정은 cur 소유**임을 §0.4b-2·§3.5·§3.6에 등재한다. 본 계약은 **모든 부재/무주인/유일-소유/
존재 주장에 grep 근거를 병기**한다:
- (i) `grep -rln <name> ⇒ 빈 결과` 명시로 부재를 증명(예: `class .*Telemetry|MonitorCoverage|ContinuousConformance|
  MonitoringGap|AlertEscalation|SafetyAlert|MonitorGeneration` tos 전역 부재 — 유일 hit는 `spg/vocabulary.py`의
  `CRITICAL_TELEMETRY_MANIFEST` 토큰이며 이는 아티팩트 모델 아닌 kind-토큰·seal·§0.4b-3).
- (ii) "유일 소유"는 대안 소유자 전수 배제 grep(예: STM aggregate result는 STM 소유이되 ioc는 `ConformanceResult`
  라는 **동명이축**을 소유·§0.5 seal).
- (iii) "무주인"은 tos 전역 grep 0 + Phase-0 등재(§8)로 fail-open 차단.
- (iv) **존재 주장도 실측**: 본 문서의 모든 file:line 인용은 저작 시점 grep 결과이며 구현 단계 drift-lock 테스트
  (§7.2 anchor-resolution property)가 형제 심볼 실 resolve로 재고정한다.

**본 문서에 적용된 anti-phantom 실측 요지(광역 `-i` 패턴)**:
- **존재(committed)**: `cur/vocabulary.py:144` `DimensionKey.MONITORING`·`:172` mandated floor(§0.4b-2·§3.5·§3.6);
  `spg/vocabulary.py:217-219` 3개 artifact-kind 토큰(§0.4b-3); `rlp/predicates.py:774-780` `monitoring_not_preventive`
  + "injected -028 (STM) coordinate, not landed"(§0.4b-4·§3.6); `sir/predicates.py:15`·`sir/state.py:46` "-028
  handoff … not landed"(§0.4b-5·§3.6); firewall 배제 `tos.stm` 4곳(`wdr:47`·`rlp:39`·`cur:51`·`sir:67`·§0.4a);
  ioc `ConformanceResult`{CONFORMANT/NON_CONFORMANT/UNKNOWN}·`__bool__ ⇒ TypeError`(`ioc/vocabulary.py:40-72`·
  truthy-sentinel 선례·name-collision·§0.5 seal); iap single-use shape `iap/predicates.py:176`(`single_use is not
  True ⇒ deny`·§3.5); `_NonTruthyStrEnum` **11 패키지 citable**(cur·egress·hag·iap·nontrade·posttrade·rlp·sbr·sir·
  venue·wdr·grep 실측·**sci 제외**[untracked·언급만]·**ioc 제외**[ioc는 `ConformanceResult.__bool__` 동종 봉인이나
  `_NonTruthyStrEnum` 명칭 미사용])·`AllFalse*Authority` **17 패키지 citable**(afg·are·authority·cur·dsl·egress·
  failuredomain·iap·ioc·liveauth·nontrade·rcl·replacement·rlp·sir·time·wdr·grep 실측·**sci 제외**)·canonical
  `IndependentIdArtifact`(`_base.py:328`)/`classify_record_pair`(`record_pair.py:52`)/`RecordPairKind`
  (`record_pair.py:31`)·ordering `compare_order`(`_ordering.py:86`)(§3.1).
- **부재(negative-grep·유지)**: `grep -rln "class .*Telemetry|class .*MonitorCoverage|class .*ContinuousConformance|
  class .*MonitoringGap|class .*AlertEscalation|class .*SafetyAlert|class .*MonitorGeneration|MonitoringSuppression"
  tos/src/tos --include="*.py" ⇒ (유일 hit = `spg/vocabulary.py` `CRITICAL_TELEMETRY_MANIFEST` kind-토큰·아티팩트
  모델 아님)`(STM **아티팩트 모델·술어** greenfield 확정); `monitor_generation|conformance.snapshot|monitoring_gap|
  alert.escalation|safety.telemetry|continuous.conformance|safety_alert ⇒ 빈 결과`(sci 제외·committed STM 좌표-소비
  아티팩트 부재 — 소비는 §0.4b 4-clade 익명 좌표뿐); `AGGREGATE_CONFORMANCE|CONFORMING.*RESTRICTED.*NON_CONFORMING
  ⇒ STM 외 부재`(aggregate result enum greenfield).
- **동명이축/동명유사 함정 4건(name-similarity ≠ proposition-identity·FD/#28 교훈·§3.5 seal)**:
  (1) `cur/vocabulary.py:144 DimensionKey.MONITORING`(currentness *차원 키*·mandated floor) ≠ STM Monitor Generation·
  Continuous Conformance *값·아티팩트* — cur는 차원 완전성 판정을 소유·STM은 그 차원의 값을 생산·명제 상이(**#28 C1
  동형 — cur가 MONITORING 차원을 실제로 보유함을 명기·"미소유" 주장 금지**).
  (2) `spg/vocabulary.py:217-219 SAFETY_MONITORING_POLICY/CRITICAL_TELEMETRY_MANIFEST/MONITOR_COVERAGE_MANIFEST`
  (spg governed-artifact-**kind 문자열 토큰**·ADR-002-014 config가 관장하는 아티팩트 *종류 이름*) ≠ STM
  `SafetyMonitoringPolicy`/`CriticalTelemetryManifest`/`MonitorCoverageManifest`(**아티팩트 모델**) — spg는 종류를
  열거하고 STM은 그 아티팩트를 *저작*·명제 상이.
  (3) `ioc/vocabulary.py:40-72 ConformanceResult`{CONFORMANT/NON_CONFORMANT/UNKNOWN}(intent-to-order **command**
  conformance·ADR-002-020) ≠ STM `AggregateConformanceResult`{CONFORMING/RESTRICTED/NON_CONFORMING/UNKNOWN}
  (**continuous conformance monitoring** aggregate·§12) — 멤버·명제 모두 상이·다만 `__bool__ ⇒ TypeError`
  truthy-sentinel 봉인 **패턴은 동일하게 REUSE**(§2.2·§4.2).
  (4) `wdr/vocabulary.py:268 CompensatingControlKind.MONITORING`(compensating-control descriptive label·`:251`)·
  `brokercap/vocabulary.py:110 AssuranceLevel.LEVEL_4_CONTINUOUSLY_MONITORED`(broker assurance level·ADR-002-004)
  ≠ STM continuous-conformance-monitoring — 둘 다 "monitoring" 문자열만 유사·축 상이(§0.5·§3.5 seal).
  **추가 name-similarity 후보(MINOR-8·대표·비전수)**: brokercap `ConformanceClass`(broker conformance class·ADR-002-004)·
  ioc `ConformanceAxis`(command conformance 축·ADR-002-020)·cur `ProofResult`(currentness proof 결과) ≠ STM
  `AggregateConformanceResult`(continuous conformance)·evidence `GapResponse.escalation_id`·sir `escalation_paths`
  (incident escalation) ≠ STM `AlertEscalationRecord`(alert escalation)·명제 상이. **정직 명기**: 이 seal 목록은
  **대표적이며 전수가 아니다** — "conformance"/"escalation"/"monitoring" 토큰은 tos 전역에서 축이 다른 여러 형제가
  공유하므로, 구현 단계 anchor-resolution property(§7.2)가 STM 심볼의 명제-구별을 기계 재고정한다(FD §10.2 교훈).

---

## 1. 범위 매핑 — ADR-002-028 조항별 EV-L1 도달성 (닫는 STM-EV 0건)

EV-level 정의(VER-002-001 실측): **EV-L1 = Model and Property Verification**("State-machine exploration, model
checking, property-based testing, and deterministic simulation") · **EV-L2 = Component Fault Test** · **EV-L3 =
Integrated System Fault Test**("Multiple live-path components … real persistence, identity, and network
boundaries") · **`+Security`** = 독립 security-boundary assessment · **`+Broker`** = Broker Capability Profile
evidence · **`EV-Ln/Lm` = staged scope, not a free choice** · "A lower level cannot substitute for a required
higher level." Phase 1은 EV-L1만이다.

> **결정적 사실 1 — STM-EV L1 슬라이스 = 2행(거버넌스 6부작 중 최소·survey §4.4 line 521)**: register 실측(csv line
> 329–340·survey §4.4 line 315–326): **core(L1 슬라이스) 2행 = {001 Complete Critical Coverage `EV-L1/3+Security`·
> 005 Deterministic Evaluation and Bound Integrity `EV-L1/3+Security`}**. **predicate-only(≥ L2) 8행 = {002
> Provenance, Continuity, Semantics, and Time `EV-L2/3+Security`·003 UNKNOWN, Silence, and Stale Green State
> `EV-L2/3`·004 Effective Independence and Common Mode `EV-L2/3+Security`·006 Suppression and Maintenance Safety
> `EV-L2/3+Security`·007 Alert Correlation, Delivery, and Escalation `EV-L2/3+Security`·008 Restrictive and Incident
> Handoff `EV-L2/3+Security`·010 UNKNOWN, Broker Finality, and Economic Continuity `EV-L2/3+Broker`·012 Evidence,
> Recovery, and Non-Revival `EV-L2/3+Security`}**. **not-Phase-1(하한 L3) 2행 = {009 Active Currentness and Send
> Race `EV-L3+Security`·011 Compromise, Fencing, and Failure Domains `EV-L3+Security`}**. **닫는 STM-EV = 0건**.
> 히스토그램(csv 실측): `EV-L1/3+Security` ×2(001·005) · `EV-L2/3+Security` ×6(002·004·006·007·008·012) · `EV-L2/3`
> ×1(003) · `EV-L2/3+Broker` ×1(010) · `EV-L3+Security` ×2(009·011). 합 12.
>
> **결정적 사실 2 — 두 L1 행 모두 `+Security` 잔여·좌표 태그 없는 L1 행 0건(정직성 핵심)**: SIR과 대비 — SIR은
> L1 3행 중 2행(002·009)이 순수 `EV-L1/3`(태그 0)이었으나, **STM은 L1 2행(001·005) 모두 `EV-L1/3+Security`**로
> **좌표 태그 없는 청정 L1 행이 0건**이다. 즉 001·005는 L1 슬라이스가 존재하나 그 행의 최종 closing에 **+Security
> 축**(001=signal/coverage forgery·suppression 저항·§22·005=evaluator differential·parser drift 저항·§22·§30 gate 4)
> 이 남는다 — L1 술어는 저작하되 그 행을 **닫지 못한다**(§5 명기). 이것이 survey §4.4 line 521 "`+Security` 10/12로
> 최고·EV 진전 기여 최저" 경고의 실체다.
>
> **결정적 사실 3 — `+Security` 10/12 = 거버넌스 6부작 최고(조직 게이트 전면 미충족)**: 12행 중 10행이 `+Security`
> (001·002·004·005·006·007·008·009·011·012)·`+Broker` 1행(010)·무태그 1행(003)뿐. STM은 **security-boundary
> assessment 밀도가 최고**인 거버넌스 계약이다(telemetry publisher/collector admission·evaluator artifact·generation
> registry·restrictive ingress identity·dashboard query boundary가 전부 §22 보안 대상). Phase-1 L1 술어는 **조직
> security 게이트를 어느 것도 충족하지 않는다**(§30 gate 3·4·7·12·§9.2).
>
> **결정적 사실 4 — authoring ≠ acceptance (닫는 STM-EV = 0건)**: (a) core 2행 전부 `/3+Security`(integration +
> security 잔여), (b) predicate-only 8행은 최소 ≥ L2(+Security/+Broker), (c) not-Phase-1 2행은 L3 런타임, (d)
> VER "A lower level cannot substitute"·ADR §27 line 594 "Written cases define obligations only. They are not
> completed evidence."·§30 line 698 "Authorship … does not satisfy these gates." ⇒ **"EV-L1-complete 주장 금지"**
> (#12–#28 §1 규율 상속). register status 전 12행 `NOT_IMPLEMENTED`(csv 실측).

**규율 태그(모든 주장에 부착)**: "**coverage-completeness / deterministic-evaluation predicate substrate only;
STM-EV-001..012 전부 NOT_IMPLEMENTED — core 2행(001·005)은 `/3` 통합·adversarial + `+Security` signal/evaluator
forgery 저항 대기, predicate-only 8행은 component-fault L2·+Security/+Broker 대기, not-Phase-1 2행(009·011)은 L3
런타임. EV-L1-complete 주장 금지·telemetry collector·monitor evaluator 런타임·coverage compiler·Monitor Generation
registry/writer-fence·alert delivery/escalation·per-send egress currentness·worst-credible-effect 계산은 재저작/
런타임/벤더/+Security/+Broker/형제-owned. L1은 coverage/determinism/bound 구조 판정만.**"

**STM-EV core 2행 ↔ AC(1:1) ↔ ADR 조항 ↔ INV 매핑(실측)**:

| STM-EV | register 제목(verbatim, csv line) | 최소 레벨 | STM-AC(1:1·제목 일치) | ADR 조항 앵커 | 관련 INV | L1 substrate 술어(§5) |
|---|---|---|---|---|---|---|
| **001** | Complete Critical Coverage (329) | `EV-L1/3+Security` | AC-001(§27 line 596) | §9 Monitor Coverage Manifest·§8 Classification | INV-001/002/004 | `critical_coverage_complete_or_gap`(노른자 1) + `coverage_grants_no_authority`·`no_self_exemption`·`monitored_assumption_intake_closed`(§5.1) |
| **005** | Deterministic Evaluation and Bound Integrity (333) | `EV-L1/3+Security` | AC-005(§27 line 612) | §11 Deterministic Evaluation·§12 aggregate result | INV-007 (+ INV-003) | `deterministic_evaluation_bound_integrity`(노른자 2) + `evaluation_is_deterministic`·`bound_integrity_preserved`·`numeric_result_not_conforming_by_default`(§5.2) |

**AC↔EV 1:1 근거(ADR에 "map one-to-one" 문장 없음·gate-status 실측)**: ADR §27 line 594 "Written cases define
obligations only"은 있으나 SIR/PTF류의 "map one-to-one to STM-EV-001 through STM-EV-012" 문장은 **부재**(ADR §27
전수 실측). 대신 근거는 **AC 제목 12/12 == EV 제목 12/12 일치**(csv register title == §27 AC 소절 title·
ARCHITECTURE-GATE-STATUS.md line 797 "STM acceptance/evidence titles now match exactly"·commit `c442dd82`로 정합
확정). ⇒ AC-00N ↔ EV-00N은 제목-일치 기반 1:1이며 §13에 전수 등재.

**ADR-002-028 조항 → Phase-1 분류(core / predicate-only / not-Phase-1 / 형제·런타임)**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | STM-EV |
|---|---|---|---|---|
| **§9** (line 271–292)·**§8**(246–267) | Monitor Coverage Manifest 1–12 closure·no self-exempt·Monitored-Assumption intake·no favorable union·coverage%≠closure | **core (L1)·+Security 잔여** | `critical_coverage_complete_or_gap`(§5.1) — 매 applicable Critical obligation이 manifest item으로 매핑(INV-002)·missing⇒gap not exemption(INV-004)·all-false(INV-001)·item-level closure(§9:292)·Monitored-Assumption(TAB-INV-006) intake는 manifest item·never out-of-band(§9:288 patch). 실 coverage compiler·registry·common-mode는 +Security/런타임. | **001** |
| **§11** (line 310–318)·**§12**(322–337) | Deterministic evaluator·hard-max≠percentile·UNKNOWN/NaN never CONFORMING·CONFORMING requires complete+current+independent | **core (L1 슬라이스)·+Security 잔여** | `deterministic_evaluation_bound_integrity`(§5.2) — **동일 (evaluator_digest, input_digest) ⇒ 동일 result**(determinism relation·핵심)·hard-max bound-kind 보존(§11:314)·non-well-formed numeric ⇒ never CONFORMING(§11:316). 실 evaluator differential·parser drift는 +Security(§30 gate 4). | **005** |
| **§10** (296–306)·**INV-003** | Provenance/continuity/semantics/units/time immutable·no reinterpret·cross-host monotonic no-subtract | **predicate-only (+Security)** | `telemetry_semantics_exact`(§6.1·INV-003·§10:302 no-subtract·§10:300 identical-values≠continuity). 실 source-continuity 런타임은 +Security. | **002** |
| **§4**(43–56)·**INV-004/005** | Absence≠health·UNKNOWN restrictive·no green-default | **predicate-only (하한 L2·유일 무태그)** | `absence_is_not_health`(§6.2·INV-004·§1:23) + `unknown_is_restrictive`(§6.3·INV-005·음극성 전수). 003은 유일 무태그 `EV-L2/3`이나 floor L2라 predicate-only. | **003** |
| **§14** (353–359)·**INV-006** | Shared source/collector/parser/clock ≠ independent·no self-health-proof | **predicate-only (+Security)** | `common_mode_is_not_independence`(§6.4·INV-006·§14:359 "SHALL NOT … treat its own health endpoint as proof"). 실 effective-control 분석은 +Security. | **004** |
| **§15** (363–378)·**INV-008** | Suppression presentation-only·8 preserved-active·expiry⇒restrictive | **predicate-only (+Security)** | `suppression_cannot_suppress_safety`(§6.5·INV-008·§15:367–376 8-function·§15:378 maintenance). 실 suppression 승인·expiry 런타임은 +Security. | **006** |
| **§16** (382–392)·**INV-009/010** | Alert state orthogonal·ack≠containment·dedup preserves scope·loss preserves negative | **predicate-only (+Security)** | `alert_state_is_orthogonal`(§6.6·INV-009·§16:388) + `loss_preserves_negative_facts`(§6.6·INV-010·§16:390). 실 delivery/escalation 런타임은 +Security. | **007** |
| **§17** (396–402)·**INV-011** | Monitoring proposes signal·ADR-002-027 owns incident·no downgrade/narrow/NO_INCIDENT | **predicate-only (+Security)·sir forward seam** | `handoff_is_non_authorizing`(§6.7·INV-011·§17:400/402·**sir handoff signal 생산·§3.6**). 실 restrictive ingress·incident classification은 sir·+Security. | **008** |
| **§19** (425–433)·**INV-013** | Missing-ACK≠non-acceptance·Cancel-ACK≠FQP·expiry≠release·UNKNOWN capacity-consuming | **predicate-only (+Broker)** | `broker_finality_unchanged`(§6.8·INV-013·§19:429) + `economic_effect_outlives_monitor_state`(§6.8·authority-shape·§19:431). 실 broker-finality 정량화는 +Broker. | **010** |
| **§23** (487–501)·**§24**(505–511)·**INV-014/015/016** | Evidence≠prevention·dashboard 7-token no-green-default·recovery non-revival·stale-writer fenced | **predicate-only (+Security)** | `evidence_and_status_honest`(§6.9·INV-014·§23:499 no-green-default) + `recovery_revives_nothing`(§6.9·INV-015·§24:511). 실 evidence custody·Recovery Barrier는 evidence/sbr·+Security. | **012** |
| **§18** (406–421)·**§16 race** | Monitor Generation current at egress·send race·no permissive cache | **not-Phase-1 (런타임 race·L3)** | 얇은 순서 permutation model(§6b·`RESTRICT<SEND⇒deny`·`SEND<RESTRICT<FIRST_BYTE⇒potentially-live+capacity-covered`·§18:421). 실 cache-free currentness·`B_monitoring_gap_to_egress_deny`·deny-first는 +Security 런타임·egress. | **009** |
| **§22** (468–483)·**§21**(447–464)·**INV-016** | Compromise expansion·stale-writer fence·partition/failure matrix | **not-Phase-1 (하한 L3·런타임)** | `stale_writer_fenced`(§6b·INV-016·generation `compare_order` 봉인) substrate만; 실 compromise expansion·partition matrix·failure-domain은 L3 런타임/형제(failuredomain/egress). | **011** |
| **§5.1·§9 compiler·§28·§29·§30** | Policy activation·coverage compiler·numeric·acceptance | **not-Phase-1 (Phase-0/INSTANCE·런타임/형제)** | policy activation=spg(ADR-002-014) 주입·coverage compiler=런타임·numeric=§8 Phase-0·acceptance=거버넌스. | (전 행 분산) |

---

## 2. 데이터 모델 계약

### 2.1 digest-bound / value / reference 분류

| 분류 | 모델 | 근거 |
|---|---|---|
| **digest-bound `IndependentIdArtifact`** (id ⊥ digest·7종) | `SafetyMonitoringPolicy`(§5.1)·`CriticalTelemetryManifest`(§5.3)·`MonitorCoverageManifest`(§5.4)·`ContinuousConformanceSnapshot`(§5.6)·`SafetyMonitoringGap`(§5.7)·`SafetyAlertRecord`(§5.8)·`AlertEscalationRecord`(§5.9) | append-only ledger citizen(§5.1 "immutable governed policy"·§5.3 "immutable registry … It grants no authority"·§5.4 "immutable mapping"·§5.6 "non-authorizing consistency cut"·§5.7 "immutable record"·§5.8/§5.9 "immutable non-authorizing record"). id 서비스 부여(≠ `f(digest)`·canonical `IndependentIdArtifact`·`_base.py:328`·SIR/rcl/egress/cur/rlp 선례). same-id/different-bytes 위조/replay를 `classify_record_pair` `CRITICAL_CONFLICT`로 탐지(§3.1·§22 line 476 "raw and derived telemetry integrity" 방어). `AlertEscalationRecord`는 §5.9 single-binding(union/substitute 금지)를 iap shape로 보강(§2.3·§3.5). |
| **value (frozen, id 없음)** | `MonitorEvaluation`(§5.10a·§11)·`ApprovedBoundBinding`(§11)·`CoverageItem`(§9)·`MonitoredAssumptionIntake`(§9 patch)·`CriticalTelemetryIdentity`(§8)·`TelemetrySemanticView`(§10)·`SilenceObservation`(§4)·`MonitoringUnknownState`(§13)·`CommonModeDisclosure`(§14)·`MonitoringSuppression`(§5.11·§15)·`AlertStateVector`(§16)·`BrokerFinalityTokens`(§19)·`DashboardStatusView`(§23)·`MonitoringRecoveryInputs`(§24)·`RestrictiveMonitoringSignal`(§5.10·§17)·`SendRaceOrdering`(§18) | id 미도출·mutate 없음. `CoverageItem`의 dependency-closure dimension 집합·`MonitorEvaluation`의 (evaluator_digest,input_digest,result)·`DashboardStatusView`의 7-token·§9 12-item·§11 12-token numeric은 §9/§11/§12/§23 조항을 손전사한 **manually-transcribed anchor**(§7.2 drift property). |
| **enum-token (`_NonTruthyStrEnum`·8종)** | `AggregateConformanceResult`{CONFORMING/RESTRICTED/NON_CONFORMING/UNKNOWN·§12}·`DashboardStatusToken`{CURRENT_CONFORMING/RESTRICTED/NON_CONFORMING/UNKNOWN/STALE/GAP/UNVERIFIED·7·§23}·`MonitoringGapKind`{10·§5.7:135}·`NumericInputState`{12·§11:316}·`BoundSemanticKind`{**12**·§11:314+§6:183}·`TelemetryCriticality`{3·§8:249}·`SuppressionLifecycleState`{4·§15}·`CoverageDimension`{**11**·§12:327/§13:347·M2 신설} | 어휘(§2.2). `__bool__ ⇒ TypeError`(truthy 봉인·비-clear 멤버가 non-empty string). **`_NonTruthyStrEnum` 로컬 재표현**(cur/egress/hag/iap/nontrade/posttrade/rlp/sbr/sir/venue/wdr `vocabulary.py` **11패키지** 선례·grep 실측·**ioc 제외**[동종 `ConformanceResult.__bool__` 봉인이나 명칭 미사용]·**sci 제외**[untracked]·import 아님). `AggregateConformanceResult`는 ioc `ConformanceResult`와 **name-collision·멤버 상이·패턴만 REUSE**(§0.5 seal). |
| **reference (scalar/digest only, 주입)** | cur Active Currentness Vector generation + **MONITORING 차원 완전성 verdict**·spg Safety Monitoring Policy activation + Hard Safety Envelope·rlp EV-L6 monitor-result 소비 verdict + demotion·sir Incident Generation + restrictive-fence verdict·egress final-egress currentness verdict + credential/route confinement·evidence causal-chain/custody/gap-status·authority Safety Authority/HALT/generation·liveauth Live Authorization generation·rcl worst-credible capacity 좌표·protective Protective Action Controller verdict·time Trustworthy Time gen·hag Effective Principal·wdr Non-Waivable Boundary·**Monitor Generation**(STM 생산·§5.5·cur 하류 소비·forward)·**029/SCI release-attestation/compromise-signal(미착지·주입·언급만)** | 형제/미착지 소유 — 주입 scalar/digest/verdict/generation으로만 참조(§3.4/§3.5). STM는 이들을 저작·import하지 않음(Monitor Generation은 STM 생산이나 cur 하류 소비·차원 완전성 판정은 cur 소유·forward). **-029/SCI는 미착지·untracked — ADR 원문만·코드 인용 0(§0.4f).** |

### 2.2 어휘 (verbatim 전사 + truthy 봉인)

**(1) `AggregateConformanceResult` (§12 line 335, non-truthy StrEnum — 4-token·핵심 truthy 봉인·ioc name-collision).**
`CONFORMING`·`RESTRICTED`·`NON_CONFORMING`·`UNKNOWN`. **`_NonTruthyStrEnum` 로컬 재표현**(`__bool__ ⇒ TypeError`).
**근거**: §12 line 335 verbatim "Allowed aggregate results are `CONFORMING`, `RESTRICTED`, `NON_CONFORMING`, and
`UNKNOWN`. `CONFORMING` requires every required item to be current, complete, and independently valid under policy.
`RESTRICTED`, `NON_CONFORMING`, or `UNKNOWN` denies dependent new risk." **`CONFORMING`조차 authority 무부여**(§1
line 25·all-false·§6.9). `RESTRICTED`/`NON_CONFORMING`/`UNKNOWN`은 non-empty string이라 `if result:`가 거부를
truthy "go"로 오독하는 치명적 fail-open. 소비 게이트는 **`result is AggregateConformanceResult.CONFORMING` 명시
비교 강제**(§4.2·ioc `result is ConformanceResult.CONFORMANT` 선례). **name-collision seal**: ioc
`ConformanceResult`(`vocabulary.py:40-72`·CONFORMANT/NON_CONFORMANT/UNKNOWN·command conformance)와 **멤버·명제 상이**·
truthy-sentinel 패턴만 REUSE(§0.5). **전역 부재 실측**: `grep AGGREGATE_CONFORMANCE|"CONFORMING"` ⇒ STM 외 아티팩트/enum 부재(단 `rlp/predicates.py:779`
docstring이 RLP-INV-015 인용으로 `CONFORMING` 문자열 1건 포함 — 인용 텍스트이며 심볼 아님·리뷰 MINOR-6 정정).

**(2) `DashboardStatusToken` (§23 line 499, non-truthy StrEnum — 7-token·honesty·no-green-default).** `CURRENT_
CONFORMING`·`RESTRICTED`·`NON_CONFORMING`·`UNKNOWN`·`STALE`·`GAP`·`UNVERIFIED`. **`_NonTruthyStrEnum`**. **근거**:
§23 line 499 verbatim "Dashboards SHALL distinguish at minimum `CURRENT_CONFORMING`, `RESTRICTED`, `NON_CONFORMING`,
`UNKNOWN`, `STALE`, `GAP`, and `UNVERIFIED`. Rendering failures or unknown state SHALL NOT default to green." ⇒ 7개
status가 서로 축약/승격 불가·rendering-failure/unknown ⇒ **never `CURRENT_CONFORMING`**(§6.9). `evidence_and_status_
honest`(§6.9)가 소비. **manually-transcribed anchor**(§7.2 drift·§부록).

**(3) `MonitoringGapKind` (§5.7 line 135, non-truthy StrEnum — 10-token gap taxonomy).** `MISSING`·
`STALE`·`CONFLICTING`·`AMBIGUOUS`·`DISCONTINUOUS`·`INCOMPLETE`·`UNVERIFIED`·`COMMON_MODE`·`FAILED`·`SUPPRESSED`.
**`_NonTruthyStrEnum`**. **근거**: §5.7 line 135 verbatim "missing, stale, conflicting, ambiguous, discontinuous,
incomplete, unverified, common-mode, failed, or suppressed monitoring coverage". §1 line 27은 **별개의 11개
gap-유발 조건 목록**(분류 anchor 아님 — 리뷰 MINOR-1 정정·분류 anchor는 §5.7:135 단독). 모든 gap kind는
restrictive 처분을 갖는다(§13). **전역 부재 실측**: `grep MonitoringGapKind|MONITORING_GAP ⇒ 빈 결과`(STM greenfield).

**(4) `NumericInputState` (§11 line 316, non-truthy StrEnum — 12-token·노른자 2 fail-closed 담지).** `WELL_FORMED`·
`UNKNOWN`·`NAN`·`INFINITY`·`OVERFLOW`·`UNDERFLOW`·`NON_CONVERGENT`·`UNIT_MISMATCH`·`PARSER_DIFFERENTIAL`·
`MISSING_SAMPLE`·`INSUFFICIENT_HISTORY`·`EVALUATOR_DISAGREEMENT`. **`_NonTruthyStrEnum`**. **근거**: §11 line 316
verbatim "Unknown numeric input, NaN, infinity, overflow, underflow, non-convergence, unit mismatch, parser
differential, missing sample, insufficient history, or evaluator disagreement yields `UNKNOWN` or a restrictive
result. It never yields `CONFORMING` by default." ⇒ `WELL_FORMED` 외 11 state는 **result가 `CONFORMING`이면 deny**
(§5.2 conjunct·§6.3). 11 malformed state 손전사(§7.2 drift·§부록).

**(5) `BoundSemanticKind` (§11 line 314 + STM-INV-007 line 183, non-truthy StrEnum — **12-token** bound taxonomy·
노른자 2 integrity 담지·M3 whitelist).** **HARD 4** `HARD_MAXIMUM`·`HARD_MINIMUM`·`EXACT_MATCH`·`MONOTONIC_SEQUENCE`
· **NEUTRAL 2** `RANGE`·`RATE` · **WEAK 6** `PERCENTILE`·`AVERAGE`·`BEST_EFFORT_TARGET`·`LOCAL_THRESHOLD`·
`HIDDEN_GRACE_PERIOD`·`FAVORABLE_SAMPLING_RULE`. **`_NonTruthyStrEnum`**. **근거**: §11 line 314 verbatim "An approved
hard maximum cannot be implemented as a percentile, average, best-effort target, or window that permits an individual
exceedance." + **STM-INV-007 line 183 verbatim** "cannot be replaced by a percentile, average, **local threshold,
hidden grace period, or favorable sampling rule**"(5 weak-form·§부록 C). ⇒ **whitelist 판정(M3·denylist→whitelist
반전·#25 RLP MAJOR-1 동형)**: approved-kind ∈ **HARD**이면 implemented-kind ∈ **HARD AND implemented is approved**
(정확 보존)여야 통과·그 외(WEAK·NEUTRAL·미지 신규 멤버) 전부 **자동 deny**(§5.2·denylist는 새 weak 멤버가 샘). "hard/
weak" 구분은 명시 멤버 집합 membership이지 강도 전순서 아님(전순서 발명 금지·§4.3 3치 접기 규율). HARD_KINDS/WEAK_
KINDS frozenset 파생·enum-drift property가 §11:314+§부록 C와 정합 강제.

**(6) `TelemetryCriticality` (§8 line 249, non-truthy StrEnum — 3-token·UNKNOWN⇒CRITICAL).** `CRITICAL`·
`NON_CRITICAL_APPROVED_EXCLUSION`·`UNKNOWN_MATERIALITY`. **`_NonTruthyStrEnum`**. **근거**: §8 line 249 verbatim
"Unknown materiality is Critical. A producer, monitor owner, dashboard owner, or consumer SHALL NOT self-classify a
telemetry item as non-Critical merely because the underlying preventive control exists elsewhere." ⇒
`UNKNOWN_MATERIALITY`는 `CRITICAL`로 접힌다(fail-closed)·`NON_CRITICAL_APPROVED_EXCLUSION`은 §9:290 independent-
governance proof 선행. `critical_coverage_complete_or_gap`(§5.1)이 소비.

**(7) `SuppressionLifecycleState` (§15 line 365, non-truthy StrEnum — 4-token·expiry⇒restrictive).** `REQUESTED`·
`ACTIVE`·`EXPIRED`·`UNKNOWN`. **`_NonTruthyStrEnum`**. **근거**: §15 line 365 "automatically restrictive on expiry or
uncertainty" + §21 line 458 "suppression state missing, stale, or expired → treat monitoring state as restricted and
unsuppressed". ⇒ `EXPIRED`/`UNKNOWN` ⇒ restrictive+unsuppressed(§6.5). `suppression_cannot_suppress_safety`(§6.5)가
소비. **주의(§4.2)**: `ACTIVE`는 *suppression 창이 유효*라는 뜻이지 safety-monitoring이 disable이라는 뜻 아님 —
8 preserved-active function은 계속 활성(§15:367–376·§6.5).

**(8) `CoverageDimension` (§12 line 327 + §13 line 347, non-truthy StrEnum — **11-token** scope/dependency-closure
차원·M2 신설·cur `DimensionKey` 선례).** `ACCOUNT`·`CAPACITY_DOMAIN`·`SAFETY_CELL`·`BROKER_SESSION`·`CREDENTIAL`·
`ROUTE`·`DATASTORE`·`CLOCK`·`DEPLOYMENT`·`POLICY`·`FAILURE_DOMAIN`. **`_NonTruthyStrEnum`**. **근거**: §12 line 327
"exact scope and dependency closure"(snapshot binding 차원 축) + **§13 line 347 verbatim** "the scope expands across
shared **accounts, Capacity Domains, Safety Cells, broker sessions, credentials, routes, datastores, clocks,
deployments, policies, or failure domains** until isolation is positively proven"(11 차원 손전사·§부록 L). `critical_
coverage_complete_or_gap`(§5.1 conjunct 6)의 dependency-closure 완전성 판정 대상·closed enum == §13:347 11차원(§7.2
3자 drift). **v1.0 phantom 삭제(M2)**: v1.0의 "closed enum == §9 차원" 주장은 **삭제**한다 — **§9에는 차원 열거가
부재**(§9는 1–12 closure 항목 리스트·차원 catalogue 아님·실측)이며 정당한 anchor는 §12:327+§13:347이다. cur
`DimensionKey`(currentness 차원·mandated floor)와 **별개 축**(STM coverage/dependency 차원·§0.5 seal 1과 정합·
name-collision 아님).

### 2.3 아티팩트 covered + self-exclusion + malformed-model 자기방어 (설계 #4 §3.3·SIR §2.3·#20/#22/#23 상속)

- 모든 digest-bound 아티팩트는 `IndependentIdArtifact`(canonical `_base.py:328`)를 상속 — `_ID_FIELD`(독립 id·
  digest preimage self-exclusion)·`_COVERED_FIELDS`(digest cover)·`_REQUIRED_COVERED`(구조 identity 최소 필수)를
  선언(SIR·wdr·spg·ioc·rcl·egress·cur·rlp 선례).
- **coordinate 비붕괴(설계 #4 §4.4)**: mutable lifecycle 좌표(snapshot `aggregate_result`·suppression `lifecycle_
  state`·주입 verdict[cur/spg/rlp/sir/evidence])는 covered digest에 **미포함** — 정당한 전이(evaluate/gap/suppress/
  escalate)가 digest를 바꿔 same-id/different-bytes `CRITICAL_CONFLICT`로 오탐되지 않도록. 현재 상태는 술어에 주입·
  별도 append-only record(§5.7 "immutable record"·§5.9 "records cannot be unioned").
- **malformed-model 자기방어 — CONFORMING-claim + incomplete-scope coexistence seal(SIR `IncidentClosureDecision`·
  WDR `SafetyDeviationDecision`·egress QCC 동형·본 문서 핵심 seal)**: `ContinuousConformanceSnapshot`/
  `MonitorCoverageManifest` `model_validator`가 **불완전 coverage/scope와 CONFORMING 주장의 공존을 구조로 봉인**.
  `ContinuousConformanceSnapshot.aggregate_result is AggregateConformanceResult.CONFORMING`인데 §12 mandated 조건
  (required monitor 전부 present·source-continuity/age/completeness 필드·active violation 목록) 중 하나라도 `None`/
  누락이면 **`ArtifactIntegrityError` at construction**(§12 line 335 "`CONFORMING` requires **every** required item
  to be current, complete, and independently valid"). 동일하게 `MonitorCoverageManifest`(is_complete 주장 + applicable
  obligation 누락 공존 ⇒ unconstructable). 술어 층에서 validator 통과 후 재확인(defense-in-depth·`model_construct`
  우회 대비·2층). **리뷰어 공격 지점(§10.2-⑦)**: `model_construct`로 malformed CONFORMING snapshot 구성 → validator +
  술어 2층 봉인.
- **`MonitorEvaluation` corpus 무결성(determinism 담지·평행-tuple 제거)**: determinism 관계는 `evaluations: tuple[
  MonitorEvaluation, ...]`(per-evaluation 구조)로 담지 — 평행 tuple(evaluator_digests/results 분리)의 길이 불일치/순서
  어긋남 결함 클래스를 구조로 제거. `MonitorEvaluation` value의 `(evaluator_digest, canonical_input_digest, result,
  numeric_input_state)`가 원자 — determinism 판정은 이 원자 튜플 키-비교(§5.2).
- **`_REQUIRED_COVERED`는 구조 identity/generation/digest만·digest 규칙 명문화(§29 gate 1)** — 각 아티팩트의
  `_COVERED_FIELDS`는 **self-digest 필드(자기 `*_digest`)를 제외**(preimage self-exclusion·canonical 규칙)하되
  **외부 참조 digest(`policy_digest`·`coverage_manifest_digest`·`bound_alert_id` 류)는 포함**한다 —
  `AlertEscalationRecord`가 `bound_alert_id`를 cover해 "어느 alert에 bound인가"를 위조 불가로 바인딩(§5.9 "bound to
  exactly one Safety Alert Record"). telemetry-age·snapshot-age·alert-age·quorum N 같은 numeric bound은 제외(Phase-1
  null profile 하 구성 가능·§8); 누락 numeric claim은 fail-closed(§4.2).

### 2.4 핵심 모델 필드 골격 (§ref·형제 seam·all-false·carrier 전수)

**`SafetyMonitoringPolicy`(§5.1)** — immutable ADR-002-014 governed policy content model. 필드: `policy_id`(독립 id)·
`policy_generation`·`policy_digest`·`critical_telemetry_classes`·`coverage_requirements`·`approved_monitor_digests`·
`bound_bindings: tuple[ApprovedBoundBinding, ...]`·`independence_requirements`·`suppression_rules`·`alert_escalation_
paths`·`evidence_obligations`·`currentness_rules`·`recovery_behavior`·`failure_behavior`·`authority_effect:
AllFalseMonitoringAuthority`. **활성화/generation은 spg/ADR-002-014 주입**(§5.1·§7 line 228). `_REQUIRED_COVERED` =
{policy_id·policy_generation·policy_digest}.

**`CriticalTelemetryManifest`(§5.3/§8)** — immutable registry (§5.3 "It grants no authority"). 필드: `manifest_id`
(독립 id)·`manifest_generation`·`manifest_digest`·`telemetry_identities: tuple[CriticalTelemetryIdentity, ...]`
(§8:253–265 binding·각 owner/source/scope/units/schema/semantics/continuity/derivation/time-basis/freshness/
failure-domains/consumers)·`authority_effect: AllFalseMonitoringAuthority`. §5.3 verbatim "It grants no authority"·
all-false. `_REQUIRED_COVERED` = {manifest_id·manifest_generation·manifest_digest}.

**`MonitorCoverageManifest`(§5.4/§9·노른자 1 carrier)** — immutable mapping. 필드: `coverage_manifest_id`(독립 id)·
`coverage_generation`·`coverage_manifest_digest`·`policy_digest`·`coverage_items: tuple[CoverageItem, ...]`·
`approved_exclusions: tuple[CoverageItem, ...]`·`submitted_monitored_assumptions: tuple[MonitoredAssumptionIntake,
...]`(§9:288 patch intake)·`is_complete: bool | None`(양극성·§9 "complete and exact")·`coverage_score_present: bool |
None`(음극성 — §9:292 "Coverage percentages … cannot replace item-level closure"·score가 closure 대체 시 deny)·
`authority_effect: AllFalseMonitoringAuthority`. `_REQUIRED_COVERED` = {coverage_manifest_id·coverage_generation·
policy_digest}. malformed-model validator: is_complete 주장 + applicable obligation 누락 ⇒ error(§2.3).

**`CoverageItem`(value·§9·노른자 1 element)** — per-obligation 매핑 원소(§9:275–286 1–12). 필드: `obligation_ref:
str`·`monitor_ref: str | None`·`scope_dimensions: frozenset[CoverageDimension]`·`dependency_closure_dimensions:
frozenset[CoverageDimension]`·`restrictive_response_present: bool | None`(양극성·§9 item 7)·`alert_path_present: bool
| None`(양극성·item 8)·`evidence_path_present: bool | None`(양극성·item 9)·`currentness_rule_present: bool | None`
(양극성·item 11)·`closure_1_to_12_complete: bool | None`(양극성·§9 1–12 전수·구조 파생 또는 주입)·`excluded: bool |
None`(**음극성** — 배제 주장·§4.3 표)·`approved_exclusion_proof_present: bool | None`(양극성·§9:290 independent-
governance proof)·`criticality: TelemetryCriticality`. **no self-exemption 구조(C1 교정)**: coverage 계상 필터는
`item.excluded is False`(음극성 clear·`is not True` 금지·§4.3)만 통과시키고, `item.excluded is not False`(True 또는
**None=unknown-exclusion**)인 item은 `approved_exclusion_proof_present is True`를 요구하며 아니면 deny(§8:249 "Unknown
materiality is Critical"·STM-INV-002:163 "Missing or **unknown** coverage is a gap, not an exemption"). `CoverageDimension`
은 §12:327/§13:347 dependency-closure 차원 closed enum(M2·§부록 L).

**`MonitoredAssumptionIntake`(value·§9 patch/ADR-DEV-011 TAB-INV-006·What's-Missing)** — assumption-derived manifest
item. 필드: `assumption_id: str`·`admitted_as_coverage_item: bool | None`(양극성·§9:288 "a manifest item subject to
the same 1–12 closure"·**never out-of-band**)·`runtime_falsity_invalidates_property: bool | None`(양극성·ADR-DEV-011
line 119 Monitored Assumption 정의). **§9:288 patch 요건**: 제출된 Monitored Assumption이 `admitted_as_coverage_item
is not True`이면 out-of-band addition ⇒ deny(STM-INV-002·`critical_coverage_complete_or_gap`·§5.1). ADR-DEV-011
TAB-INV series(별개·§0 각주)의 런타임 validity를 monitored obligation으로 편입.

**`ContinuousConformanceSnapshot`(§5.6/§12)** — non-authorizing consistency cut. 필드: `snapshot_id`(독립 id)·
`snapshot_generation`·`snapshot_digest`·`monitor_generation`(ordering·§5.5)·`policy_digest`·`critical_telemetry_
manifest_digest`·`coverage_manifest_digest`·`scope`·`owner_epoch`·`monitor_results: tuple[MonitorEvaluation, ...]`·
`source_continuity_present: bool | None`(양극성·§12)·`active_violations`·`active_unknowns`·`active_gaps`·`active_
suppressions`·`delivery_failures`·`aggregate_result: AggregateConformanceResult`·`authority_effect:
AllFalseMonitoringAuthority`. §5.6/§1:25 "non-authorizing"·all-false. `_REQUIRED_COVERED` = {snapshot_id·snapshot_
generation·monitor_generation·policy_digest}. malformed-model validator: `aggregate_result is CONFORMING` +
incomplete ⇒ error(§2.3·§12:335).

**`SafetyMonitoringGap`(§5.7/§13·M1 신설 skeleton·`MonitoringGapKind` 고아 해소)** — immutable gap record. 필드:
`gap_id`(독립 id)·`gap_generation`·`gap_digest`·`monitor_generation`·**`gap_kind: MonitoringGapKind`**(§5.7 10-kind)·
`exact_scope`·`first_observation`·`credible_start_interval`·`source_evaluator_state`·`missing_evidence`·`common_modes`·
`greatest_credible_impact`·`required_restrictions`·`alert_state`·`closure_proof_present: bool | None`(양극성·§13:349
"Closure requires continuity re-established … missed violations conservatively reconstructed")·`authority_effect:
AllFalseMonitoringAuthority`. §13 line 343 "immutable **Safety Monitoring Gap**. It SHALL record exact scope, first
observation, credible start interval …"·all-false. `_REQUIRED_COVERED` = {gap_id·gap_generation·monitor_generation}.
**소비(M1·고아 해소)**: 지지 술어 `gap_is_restrictive_not_exemption(gap: SafetyMonitoringGap | None) -> bool`이
`gap.gap_kind is not None`(10-kind 중 하나로 분류) AND `all_false_monitoring_authority(gap.authority_effect)` AND
`gap.closure_proof_present`가 clear의 유일 경로임(§13:349 "Monitoring recovery does not close the gap by itself")을
판정 — `critical_coverage_complete_or_gap`(§5.1)의 missing-coverage 분기가 이 gap을 산출(§5.1 반환·§13). `MonitoringGapKind`
enum이 이 술어·gap 필드에서 실소비되어 고아 아님.

**`SafetyAlertRecord`(§5.8/§16·M1 신설 skeleton)** — immutable non-authorizing alert record. 필드: `alert_id`(독립
id)·`alert_generation`·`alert_digest`·`monitor_generation`·`signal_lineage`·`exact_scope`·`first_known_time`·
`severity_proposal`·`correlation_facts`·`required_delivery_policy`·`required_escalation_policy`·`restriction_linkage`·
`incident_classification_rule`·`authority_effect: AllFalseMonitoringAuthority`. §5.8 line 139 "An immutable **non-
authorizing** record of one alert identity, signal lineage, exact scope, severity proposal, correlation facts,
required delivery and escalation policy" + §16 line 384 바인딩(signal lineage·exact scope·Monitor Generation·first-
known time·severity proposal·required restriction·incident-classification rule = 7요소)·all-false. `_REQUIRED_COVERED`
= {alert_id·alert_generation·monitor_generation}. **소비(M1)**: `alert_state_is_orthogonal`(§6.6)이 alert 상태 직교성
판정 시 참조·correlation이 scope/lineage/first-observed 보존(§16:386).

**`AlertEscalationRecord`(§5.9/§16·M1 신설 skeleton·`bound_alert_id` phantom 해소·single-binding)** — immutable non-
authorizing escalation record. 필드: `escalation_id`(독립 id)·`escalation_generation`·`escalation_digest`·**`bound_
alert_id: str`**(§5.9 "bound to exactly one Safety Alert Record"·§2.3 cover·phantom 해소)·`policy_digest`·`monitor_
generation`·`ordered_delivery_attempts`·`acknowledgements`·`escalation_stages`·`failures`·`alternate_paths`·`handoffs`·
`retirement_criteria`·`unioned_or_substituted: bool | None`(음극성·§5.9:143 "records cannot be unioned, substituted,
or used to narrow the alert scope or reset its first-observed time")·`authority_effect: AllFalseMonitoringAuthority`.
§5.9 line 143 verbatim·all-false. `_REQUIRED_COVERED` = {escalation_id·escalation_generation·bound_alert_id}(§2.3
외부 참조 digest cover·"어느 alert에 bound인가" 위조 불가). **소비(M1·single-binding)**: 지지 술어 `escalation_single_
binding(record: AlertEscalationRecord | None) -> bool`이 `record.bound_alert_id`가 정확히 하나 present AND
`record.unioned_or_substituted is False`(음극성·`is not False` ⇒ deny·iap single-use shape REUSE·§3.5)를 판정.

**`MonitorEvaluation`(value·§11·노른자 2 carrier·determinism 원자)** — 한 evaluator의 한 입력에 대한 판정 원자.
필드: `evaluator_digest: str`·`canonical_input_digest: str`·`result: AggregateConformanceResult`·`numeric_input_
state: NumericInputState`·`bound_binding_digest: str`. **determinism 키 = (evaluator_digest, canonical_input_digest)**;
같은 키·다른 result ⇒ 비결정론 위반(§5.2). `canonical_input_digest`는 canonical `EVL1ProvisionalCanonicalizer`의
결정론적 digest(같은 입력 ⇒ 같은 digest·§3.1). value·id 미도출.

**`ApprovedBoundBinding`(value·§11·노른자 2 carrier·integrity·M4 결속 키)** — approved bound의 semantics. 필드:
**`bound_binding_digest: str`**(M4·`MonitorEvaluation.bound_binding_digest`와 결속되는 참조 키·§5.2 subset conjunct)·
`approved_bound_kind: BoundSemanticKind`·`implemented_as_kind: BoundSemanticKind`·`units_exact: bool | None`(양극성·
§11:312)·`permits_individual_exceedance: bool | None`(음극성·§11:314 "window that permits an individual exceedance"
금지)·`window_inside_bound: bool | None`(양극성·§11:314 "Debounce, grace, hysteresis … count inside the applicable
detection or containment bound")·`uncertainty_treated: bool | None`(양극성·§11:312). `bound_integrity_preserved`
(§5.2)가 소비. **M4 결속**: 노른자 2가 `{e.bound_binding_digest for e in evaluations} ⊆ {b.bound_binding_digest for
b in bounds}`를 요구(evaluation이 참조하는 bound가 미제출이면 favorable-subset 우회 ⇒ deny·#22 no-favorable-union).

**`CriticalTelemetryIdentity`(value·§8/§10·EV-002 carrier)** — telemetry의 semantic identity(§8:256–265). 필드:
`telemetry_id: str`·`source_identity: str`·`units: str`·`schema_digest: str`·`derivation_lineage_digest: str`·
`trustworthy_time_basis: str`(time 주입)·`continuity_fact: str | None`·`criticality: TelemetryCriticality`·
`semantics_reinterpreted: bool | None`(음극성·§10:302 "A consumer cannot reinterpret or silently default them")·
`hash_equality_claims_equivalence: bool | None`(음극성·§8:267 "Hash equality … alone does not establish semantic
equivalence"). `telemetry_semantics_exact`(§6.1)가 소비.

**`TelemetrySemanticView`(value·§10·EV-002·What's-Missing)** — provenance/continuity view. 필드: `cross_host_
monotonic_subtracted: bool | None`(음극성·§10:302 "Cross-host monotonic values SHALL NOT be directly subtracted")·
`identical_values_claim_continuity: bool | None`(음극성·§10:300 "Identical values before and after a discontinuity do
not prove continuity")·`age_clamped_from_unbounded: bool | None`(음극성·§10:302 "Future, negative, unknown, or
unbounded age cannot be clamped into freshness"). `telemetry_semantics_exact`(§6.1)가 소비.

**`SilenceObservation`(value·§4/§1:23·EV-003·INV-004·MINOR-2 무조건·OQ1 표지 이연)** — 침묵/부재 표지. **판정
필드(음극성·§4.3)**: `treated_as_healthy: bool | None`(§1:23·**INV-004 line 171** "No alert, repeated health
heartbeat, quiet time, successful scrape, empty query, or green dashboard proves safety"). **표지 필드(비판정·명시
이연·OQ1)**: `no_alert`·`repeated_heartbeat`·`quiet_time`·`empty_query`·`green_dashboard`(각 `bool | None`) —
**어느 침묵이 관측되었는지의 런타임 기록이며 L1 판정에 참여하지 않는다**(화이트리스트 사유: MINOR-2 무조건 해석과
양립 — 판정은 침묵 종류와 무관하게 `treated_as_healthy` 소비·표지는 §22 forgery/런타임 감사용·docstring 명기·무성
미소비 아님). `absence_is_not_health`(§6.2·**MINOR-2 무조건**): `obs.treated_as_healthy is False`를 **상시 요구**
(silence 표지 유무 무관·`is not False`[True 또는 None] ⇒ deny). **보수 분기 독립 노출(#28 MAJOR-3)**:
"`treated_as_healthy is False`"[정직한 침묵 — allow]·"`is True`"[fail-open 시도 — deny]·"`is None`"[unknown — deny]
3 픽스처를 §7.2에 **각각 명시**(지배 분기 없는 픽스처).

**`MonitoringUnknownState`(value·§13·EV-003·INV-005)** — UNKNOWN 축(음극성 전수). 필드: `telemetry_missing`·
`state_stale`·`state_conflicting`·`state_ambiguous`·`state_discontinuous`·`generation_mixed`·`state_unverifiable`
(전부 `bool | None`·음극성·§4.3·INV-005 line 175 "Missing, stale, conflicting, ambiguous, discontinuous, mixed-
generation, or unverifiable monitoring state blocks dependent new risk and expands to the greatest credible scope").
`unknown_is_restrictive`(§6.3)가 소비.

**`CommonModeDisclosure`(value·§14·EV-004·INV-006)** — 공유 의존 disclosure. 필드: `shared_dependencies: frozenset[
str]`(source/collector/parser/clock/datastore/network/admin/identity/deployment/route/vendor·§14:355)·`claimed_
independent: bool | None`(양극성 표지)·`residual_common_mode_disclosed: bool | None`(양극성·§14:357)·`self_health_
as_proof: bool | None`(음극성·§14:359 "treat its own health endpoint as proof")·`validates_own_continuity_by_own_
output: bool | None`(음극성·§14:359). `common_mode_is_not_independence`(§6.4): `shared_dependencies ≠ ∅ ∧ claimed_
independent is True` ⇒ deny(공유 의존이 있으면 independent 주장 불가·disclosed common mode).

**`MonitoringSuppression`(value·§5.11/§15·§5.11:151 6금지 폐포·M6)** — governed suppression. 필드: `suppression_id:
str`·`scope`·`purpose`·`lifecycle_state: SuppressionLifecycleState`·`preserved_functions: frozenset[str]`(§15:367–376
8-function·gap-creation 포함)·**§5.11:151 6금지(전 음극성)**: `disables_collection: bool | None`·`disables_evaluation:
bool | None`(invariant evaluation)·`disables_restrictive_signaling: bool | None`·**`disables_evidence: bool | None`**
(M6 복원)·**`disables_generation_advancement: bool | None`**(M6 복원·§5.11 line 151 "generation advancement")·
`disables_final_egress_denial: bool | None`. **근거**: §5.11 line 151 verbatim "It SHALL NOT disable source
collection, invariant evaluation, restrictive signaling, evidence, generation advancement, or final-egress denial"
(6금지·부록). `suppression_cannot_suppress_safety`(§6.5)가 6필드 전부 `is False` 소비. gap-creation은 §15:367–376
8-function preserved_functions 소속(별개 축·§6.5).

**`AlertStateVector`(value·§16·EV-007·INV-009)** — alert 상태 직교 축. 필드: `detection_state`·`delivery_state`·
`acknowledgement_state`·`escalation_state`·`containment_state`·`incident_state`·`recovery_state`·`economic_finality_
state`(각 str|None·직교)·`ack_implies_containment: bool | None`(음극성·§16:388 "acknowledgement … is not
containment")·`advance_of_one_implies_another: bool | None`(음극성·INV-009 line 191 "Advancement of one never implies
another")·`adverse_record_dropped: bool | None`(음극성·INV-010 line 195)·`elapsed_time_reset: bool | None`(음극성·
INV-010 line 195 "reset elapsed detection and escalation time"). `alert_state_is_orthogonal`·`loss_preserves_
negative_facts`(§6.6)가 소비.

**`BrokerFinalityTokens`(value·§19·EV-010·INV-013)** — broker finality 축. 필드: `missing_ack_treated_as_non_
acceptance: bool | None`(음극성·§19:429 "Missing broker ACK remains possible acceptance")·`cancel_ack_treated_as_
fqp: bool | None`(음극성·§19:429 "Cancel ACK is not Final Quantity Proof")·`unknown_effect_capacity_released: bool |
None`(음극성·§19:429 "preserves the worst credible economic effect in RCL capacity"). `broker_finality_unchanged`
(§6.8)가 소비.

**`DashboardStatusView`(value·§23·EV-012·honesty carrier)** — dashboard status 정직성. 필드: `status_token:
DashboardStatusToken`·`rendering_failed: bool | None`·`state_unknown: bool | None`·`defaulted_to_green: bool | None`
(음극성·§23:499 "Rendering failures or unknown state SHALL NOT default to green"). `evidence_and_status_honest`(§6.9):
`(rendering_failed is True ∨ state_unknown is True) ∧ status_token is DashboardStatusToken.CURRENT_CONFORMING` ⇒ deny.

**`MonitoringRecoveryInputs`(value·§24·EV-012·INV-015·OQ1 표지 구조 파생)** — recovery non-revival 축(음극성 전수).
**표지 필드(구조 파생 입력·OQ1)**: `restart`·`reconnect`·`failover`·`restore`·`queue_drain`·`alert_ack`·`replay`·
`operator_return`·`quiet_time`(각 `bool | None`) — **recovery 이벤트 관측 표지·`recovery_revives_nothing`이 이들의
disjunction을 게이트로 소비**(무성 미소비 아님·§24:511 "Startup, restart, reconnect, failover, restore … or operator
return occurs behind the Recovery Barrier"). **판정 필드(음극성·§4.3)**: `revived_prior_authority: bool | None`
(§24:511)·`resumed_trial: bool | None`·`restored_production_scope: bool | None`·`auto_re_armed: bool | None`(§24:511
"a fresh ADR-002-007/015 governed re-arm chain remains mandatory"). `recovery_revives_nothing`(§6.9): **어떤 recovery
표지라도 present(`is True`)이면 4 판정 필드 전부 `is False` 요구**(표지 disjunction ⇒ non-revival 게이트 발동·구조
파생).

**`RestrictiveMonitoringSignal`(value·§5.10/§17·EV-008·sir forward seam·§17:402 4금지 폐포·M6)** — monitoring이 sir/
cur에 제안하는 signal. 필드: `signal_id: str`·`source_identity: str`·`scope`·`monitor_generation`·`confidence`·
`common_modes`·**§17:402 4금지(전 음극성)**: `downgrades_existing_fence: bool | None`·`selects_narrower_scope: bool |
None`·**`clears_local_latch: bool | None`**(M6 복원·§17:402 "clear a local latch")·`publishes_no_incident: bool |
None`·`authority_effect: AllFalseMonitoringAuthority`. **근거**: §17 line 402 verbatim "No monitor or alert may
downgrade an existing fence or incident, select a narrower scope, clear a local latch, or publish `NO_INCIDENT`"
(4금지·부록). §5.10 "It cannot clear a restriction or create permission"·all-false. `handoff_is_non_authorizing`
(§6.7)가 4필드 전부 `is False` 소비·sir가 하류 주입 소비(§3.6).

**`SendRaceOrdering`(value·§18·EV-009 thin·not-Phase-1·OQ3 capability-claim 3점 복원)** — invalidation-vs-send 순서
permutation. 필드: `restrict_event: OrderingEvent`(gap/restriction ordered)·**`capability_claim_event: OrderingEvent`**
(OQ3 복원·§18:421 "the capability claim")·`first_byte_event: OrderingEvent | None`(first broker-directed byte)·
`ordering_provable: bool | None`(양극성·§18:421). **근거(§18 line 421 verbatim)**: "If a gap or restriction is ordered
before **the capability claim**, the send is denied. If ordering between a material monitoring invalidation and first
broker-directed byte cannot be proven, the attempt remains potentially live, capacity-covered, and ineligible for
blind retry." 얇은 model(§6b): `RESTRICT<CAPABILITY_CLAIM ⇒ deny`·`(invalidation↔FIRST_BYTE 순서 미증명 ∨ ordering_
provable is not True) ⇒ potentially-live+capacity-covered+no-blind-retry`. ordering 3치(증명됨-deny / 증명됨-safe /
증명불가-potentially-live)를 같은 bool에 접지 않음(§4.3).

**`AllFalseMonitoringAuthority`(all-false·§6.9·INV-001/§1:25·**14 필드**·M6)**: `creates_capacity: bool = False`·
`approves_action: bool = False`·`creates_headroom: bool = False`·`marks_requirement_pass: bool = False`·
**`satisfies_preventive_control: bool = False`**(M6·§1:25 "satisfy preventive control" 복원)·`establishes_broker_
finality: bool = False`·`activates_configuration: bool = False`·`issues_authority: bool = False`·`permits_
transmission: bool = False`·`closes_incident: bool = False`·`establishes_recovery_readiness: bool = False`·`restores_
scope: bool = False`·`re_arms: bool = False`·`classifies_protective: bool = False`. `model_validator` any-True ⇒
`ArtifactIntegrityError`
(afg/are/authority/cur/dsl/egress/failuredomain/iap/ioc/liveauth/nontrade/rcl/replacement/rlp/sir/time/wdr
`AllFalse*Authority` **17패키지 citable** 선례·grep 실측·**로컬 재표현·import 아님**). **근거**: §1 line 25 verbatim
CONFORMING "does not approve an action, create headroom, mark an RFC requirement `PASS`, satisfy preventive control,
establish broker finality, activate configuration, issue authority, permit transmission, close an incident, establish
recovery readiness, restore scope, or re-arm." + INV-001 line 159 (no capacity/approval/live authority/transmission/
incident closure/readiness/re-arm) + §7 line 236 (classify protective).

---

## 3. canonical / ordering REUSE + sibling edge 0 + 형제 경계 + forward seam

### 3.1 canonical REUSE

`tos.canonical` **REUSE**(import): `IndependentIdArtifact`(id ⊥ digest base·`_base.py:328`·실측)·`classify_record_
pair` + `RecordPairKind`{IDEMPOTENT_DUP/CRITICAL_CONFLICT/DIVERGENT_EMISSION/DISTINCT/NOT_COMPARABLE}(`record_pair.py:
52`/`:31`·실측·policy/manifest/snapshot/gap/alert/escalation의 append-only 무결성·same-id/different-bytes 탐지·§22
line 476 "raw and derived telemetry integrity and continuity" 방어)·`CanonicalDecimal`(필요 시)·`FrozenModel`·
**`EVL1ProvisionalCanonicalizer`(digest 결정론·노른자 2 근간)**. **canonical만이 base 의존**(SIR/wdr/rcl/ioc/evidence/
egress/cur/rlp 선례 동형). **노른자 2 핵심 연결**: `MonitorEvaluation.canonical_input_digest`의 결정론(같은 입력 ⇒
같은 digest)은 canonical `EVL1ProvisionalCanonicalizer`의 이미-테스트된 결정론에 근거한다 — STM의 evaluation-determinism
property(§5.2)는 canonical determinism 위에 얹힌다. **주의**: pre-issuance(digest None) 아티팩트는 `classify_record_
pair`가 `NOT_COMPARABLE`로 분류(false conflict 방지·canonical MINOR-1 discipline). restriction-vs-send 런타임 race
탐지는 +Security(STM-EV-009).

### 3.2 ordering REUSE (Monitor Generation·generation floor·stale-writer fence)

`tos.ordering` **REUSE**(import·`compare_order`·`_ordering.py:86` 실측): policy/manifest/snapshot/alert generation
순서·**Monitor Generation** monotonic fence(§5.5·§12 line 337)·predecessor floor·generation `>=` shape REUSE(stale-
writer 봉인·INV-016·§12:337 "A stale owner is treated as potentially active until hard fencing is proven"·§18 item 3
"current Monitor Generation and fenced owner epoch"). **PROMOTE 0**(신규 core 승격 없음 — canonical/ordering이 충분·
SIR/cur/rlp 선례). Monitor Generation(§5.5)은 ordering identity이지 wall-clock 아님 — STM는 clock-free(`MAX_*_age_ms`
wall-clock age는 secondary +Security/INSTANCE·§8). **cur seam**: STM이 생산한 Monitor Generation은 cur가 MONITORING
차원 좌표로 하류 소비(§3.5 cur 행·§3.6)·순서 판정 shape는 ordering REUSE·완전성 판정은 cur 소유.

### 3.3 REUSE 요약 표

| 대상 | 결정 | 근거 |
|---|---|---|
| `tos.canonical`(IndependentIdArtifact·classify_record_pair·RecordPairKind·CanonicalDecimal·FrozenModel·EVL1ProvisionalCanonicalizer) | **REUSE (import)** | base digest substrate·replay/substitution 구조 분류·**evaluation-determinism 근간**·전 시리즈 선례·§22 telemetry-integrity 방어 |
| `tos.ordering`(compare_order·Ordering·OrderingEvent) | **REUSE (import)** | Monitor Generation floor·predecessor·monotonic fence·stale-writer 봉인·SIR/cur 선례 |
| 형제 tos 패키지 전부(cur·spg·rlp·sir·egress·evidence·authority·liveauth·rcl·protective·time·hag·wdr·iap·sbr·afg·orthostate·recon·brokercap·capsule·venue·nontrade·posttrade·failuredomain·are·ioc·dsl·replacement + 미착지 sci) | **NO import (sibling edge 0)** | 형제 상호작용은 주입 scalar/digest/bool/verdict/enum-token/generation으로만(§3.4). **rcl edge 0 판정: §3.5**(STM은 capacity 산술 미수행·SIR/WDR 선례) |
| `_NonTruthyStrEnum` | **로컬 재표현 (import 아님)** | cur/egress/hag/iap/nontrade/posttrade/rlp/sbr/sir/venue/wdr `vocabulary.py` **11패키지 citable** 선례(grep 실측·**ioc 제외**[`ConformanceResult.__bool__` 동종 봉인·명칭 미사용]·**sci 제외**[untracked]) — 각 패키지 로컬 정의 |
| `AllFalseMonitoringAuthority` | **로컬 재표현 (import 아님)** | afg/are/authority/cur/dsl/egress/failuredomain/iap/ioc/liveauth/nontrade/rcl/replacement/rlp/sir/time/wdr `AllFalse*Authority` **17패키지 citable** 선례(grep 실측·**sci 제외**) |
| iap single-use consumption *shape* | **로컬 재표현 (import 아님)** | `AlertEscalationRecord` single-binding(§5.9 no-union/substitute)이 iap shape REUSE(`iap/predicates.py:176` `single_use is not True ⇒ deny` 선례·§2.3) |
| `AggregateConformanceResult`·`DashboardStatusToken`·`MonitoringGapKind`·`NumericInputState`·`BoundSemanticKind` (STM 어휘) | **STM 로컬 저작** | **실측 tos 전역 미소유**(§0.5 negative-grep·유일 hit는 spg `CRITICAL_TELEMETRY_MANIFEST` kind-토큰·ioc `ConformanceResult`는 name-collision·멤버 상이·seam 충돌 0) |

### 3.4 sibling edge 0 정책

STM는 **어떤 형제 tos 패키지도 import하지 않는다.** 형제/미착지 owner의 verdict/generation/digest/차원-완전성은
전부 **주입 좌표**(scalar/digest/bool/verdict/enum-token/generation). 이는 (a) **계층 분리**: STM content 생산 →
cur/spg/rlp/sir/egress boundary 소비(forward·§3.6), (b) firewall allowlist(`closure ⊆ {canonical, ordering, stm}`·
§7.1), (c) **rcl edge 회피**(§3.5 — STM은 capacity 산술 미수행·worst-credible은 주입 opaque·SIR/WDR 선례)를 강제한다.
**PROMOTE 0**.

### 3.5 소유권 / seam 분할표 (본 문서 최대 함정 — 코드 실측·anti-phantom §0.5)

각 행은 **이연 판정 테스트**("형제가 명제-동일 술어/아티팩트를 committed 코드로 보유하는가?" — YES ⇒ 형제 이연·NO ⇒
STM 저작/Phase-0)를 적용. 존재 인용은 grep file:line, 부재 주장은 negative-grep.

| telemetry/monitoring 관련 아티팩트/술어 | 소유 (실측) | STM 관계 (재저작 금지) |
|---|---|---|
| cur Active Currentness Vector·**`DimensionKey.MONITORING`(`vocabulary.py:144`·`MANDATED_DIMENSION_FLOOR` 소속 `:172`)**·`vector_complete`·`policy_covers_mandated_dimensions`·final-egress admission | **cur (#23·ADR-002-024·착지)** | **§1 line 31** "as part of the ADR-002-024 currentness transaction"(§18:408 "the Broker Egress Gateway SHALL include these facts in the ADR-002-024 Safety Currentness Vector"·M7 phantom 정정). **#28 C1 트랩 정면**: cur는 **`DimensionKey.MONITORING` 차원을 이미 mandated floor로 보유**(실측·`:144`/`:172`) — STM은 그 차원의 *값*(Monitor Generation·Continuous Conformance Snapshot digest)을 **생산**하고, **차원 completeness/currentness 판정은 cur 소유**(재저작 0). forward seam(§3.6)·greenfield 정합. **name-collision seal**: cur 차원 키(currentness *차원*) ≠ STM 아티팩트·값(§0.5 seal 1). **"cur가 MONITORING 미소유" 주장 금지**(#28 SIR가 INCIDENT 차원 미소유 오주장 → CRITICAL·동형). **최상류 참조** |
| spg Safety Monitoring Policy activation(ADR-002-014)·Hard Safety Envelope·governed-artifact-kind 토큰(`vocabulary.py:217-219`) | **spg (#12·ADR-002-014·착지)** | §5.1 "One active ADR-002-014 governed Safety Monitoring Policy"·§7 line 228. STM = policy activation verdict **주입 소비**·재저작 안 함. **name-collision seal**: spg `SAFETY_MONITORING_POLICY`/`CRITICAL_TELEMETRY_MANIFEST`/`MONITOR_COVERAGE_MANIFEST`(artifact-**kind 문자열 토큰**·spg가 관장하는 아티팩트 종류 이름) ≠ STM `SafetyMonitoringPolicy`/`CriticalTelemetryManifest`/`MonitorCoverageManifest`(**아티팩트 모델**)·명제 상이(§0.5 seal 2) |
| rlp EV-L6 monitor-result non-authorizing·demotion·`monitoring_not_preventive`(`predicates.py:774`) | **rlp (#25·ADR-002-025·착지)** | §20 line 439 "ADR-002-025 EV-L6 monitoring SHALL use this protocol". **forward seam(committed·§3.6)**: rlp가 STM "CONFORMING monitor result는 non-authorizing" 개념 + Monitor Generation을 all-false authority + "injected -028 (STM) coordinate, not landed"로 자기증언 소비(`predicates.py:774-780`·RLP-INV-015). STM = 개념·generation 생산·rlp demotion/scope 재저작 안 함. 익명 authority/generation·`tos.stm` 미참조 |
| sir Incident Generation·incident classification·restrictive fence·Active Safety Incident Set·`IncidentRecoveryHandoffPackage`(`records.py:510`) | **sir (#28·ADR-002-027·착지)** | §17 line 400 "ADR-002-027 remains responsible for materiality, severity, greatest-credible incident scope, Incident Generation, active incident set, containment, shutdown, handoff, and closure". **forward seam(committed·§3.6)**: sir가 STM "-028 handoff" 좌표를 "not landed (injected opaque coordinates)"로 예정 소비(`sir/predicates.py:15`·`sir/state.py:46`). STM = §17 restrictive-monitoring-signal(handoff) 생산·incident authority 재저작 안 함(INV-011·§17:402 no-downgrade/narrow/NO_INCIDENT) |
| egress final-egress enforcement·credential/route confinement·per-send currentness | **egress (#22·ADR-002-013·착지)** | §18 final egress·§7 line 241 "no … identity may hold a usable live-order credential and broker route"·§22:483. STM 주입·재저작 안 함·monitoring/alert/dashboard identity no-route(§6.7·§7:241) |
| evidence custody·causal-chain·gap·`GapStatus`·`ReceiptVerificationStatus` | **evidence (ADR-002-016·착지)** | §7 line 231 "ADR-002-016 Evidence Store"·§23. STM = evidence custody/gap **주입 소비**. **동명이축 seal**: evidence `GapStatus`(gap.py) ≠ STM `MonitoringGapKind`(§5.7)·명제 상이(gap-integrity vs monitoring-coverage-gap·§0.5) |
| authority Safety Authority·HALT·generation fence | **authority (ADR-002-003·착지)** | §7 line 234·§29. STM = HALT/authority/generation **주입 소비**·발급 안 함(INV-001) |
| liveauth Live Authorization·re-arm 체인 | **liveauth (ADR-002-007·착지)** | §7 line 239 "ADR-002-007/015 governed chain"·§24:511. STM 주입 소비·발급 안 함(INV-001) |
| rcl capacity mutation/serialization·worst-credible·`within_limits` | **rcl (ADR-002-002/012·착지)** | §7 line 235 "Risk Capacity Ledger … monitoring never writes capacity"·§19 line 429 "preserves the worst credible economic effect in RCL capacity". STM worst-credible은 **주입 opaque 좌표**·**edge 0**(SIR/WDR 선례·STM L1 capacity 산술 미수행)·계산 +Broker |
| protective Protective Action Controller·classify-protective | **protective (ADR-002-001·착지)** | §7 line 236 "Protective Action Controller … alert severity is not protective classification". STM 주입·재저작 안 함·`AllFalseMonitoringAuthority.classifies_protective=False`(§2.4) |
| time Trustworthy Time·timestamp evidence | **time (ADR-002-008·착지)** | §10 line 298 "ADR-002-008 trustworthy-time rules"·§18 item 8. STM = time gen/age **주입 소비**(clock-free·§8) |
| hag Effective Principal·quorum·independence | **hag (#20·ADR-002-015·착지)** | §14 independence·§22. STM = independence verdict 주입 소비(common-mode 판정은 §6.4 substrate·실 effective-control은 hag/+Security) |
| wdr Non-Waivable Boundary·no-post-hoc-waiver·Safety Deviation Decision | **wdr (#26·ADR-002-026·착지)** | §15 line 365 "Suppression approval is not a Safety Deviation Decision unless ADR-002-026 separately authorizes". STM = deviation verdict 주입 소비·suppression≠deviation(§6.5) |
| iap `single_use`/consume gate(`predicates.py:176`) | **iap (#15·ADR-002-023·착지)** | **single-binding shape 선례**(grep 실측). `AlertEscalationRecord` single-binding(§5.9)이 REUSE(재저작 아님·§2.3) |
| afg action-flow·orthostate position·recon reconciliation·brokercap broker class·capsule/venue/nontrade/posttrade/failuredomain/are/ioc/dsl/replacement | **각 형제 (착지)** | §16·§19 참조. STM 주입 소비·재저작 안 함 |
| 029 release-attestation/compromise-signal(SCI) | **미착지·untracked owner (-029·세션 C)** | STM = §8:253 release-lineage를 Critical Telemetry로 주입 소비 + compromise를 Safety Signal 주입 소비(§22)·**내용 재판정 금지(phantom·§0.4f)**·언급만 |
| **telemetry-classification·coverage-manifest·conformance-snapshot·monitoring-gap·alert-record·escalation-record·aggregate-result·dashboard-honesty (아티팩트 모델·술어)** | **STM (greenfield 신규)** | **STM 아티팩트 모델·술어는 tos 전역 부재 실측**(§0.5 negative-grep: `class .*Telemetry`/`MonitorCoverage`/`ContinuousConformance`/`MonitoringGap`/`AlertEscalation`/`SafetyAlert` 빈 결과·유일 hit spg kind-토큰). **spg/cur/ioc name-collision seal(§0.5)**: spg 토큰·cur 차원·ioc `ConformanceResult`는 종류-이름/차원-키/command-conformance이지 STM 아티팩트 *모델*이 아니다. STM 저작 정당(재저작 아님·§4·§5·§6) |

### 3.6 forward seam — STM 생산 · cur/rlp/spg/sir 소비 (committed·본 문서 특유·SIR §3.6보다 풍부)

**실측(committed 코드)**: STM이 생산할 telemetry-integrity 좌표가 **이미 네 형제에 주입 소비**된다(SIR의 forward seam
2-clade보다 풍부·본 문서 최대 판정 §0.4b).

- **cur MONITORING 차원(value-producer seam·#28 C1 트랩 정면)**: `cur/vocabulary.py:144` `DimensionKey.MONITORING`·
  `:172` mandated floor 소속. cur가 Safety Currentness Vector의 MONITORING 차원 **완전성·currentness 판정을 소유**하고
  (`vector_complete`), STM은 그 차원의 *값*(Monitor Generation·Continuous Conformance Snapshot digest)을 **생산**한다.
  §18 line 410–417 currentness vector가 STM 좌표(policy identity/generation/digest·Monitor Generation·coverage
  completeness·conformance result)를 열거하나 **판정은 cur/egress transaction 소유**.
- **rlp EV-L6 monitor-result(concept seam)**: `rlp/predicates.py:774` `monitoring_not_preventive(authority)`·
  docstring `:775-781` "A `CONFORMING` monitor result remains non-authorizing … The monitoring generation is an
  injected -028 (STM) coordinate, not landed." rlp가 STM의 "CONFORMING monitor result는 non-authorizing" 명제 +
  Monitor Generation을 **주입 all-false authority + opaque 좌표**로 소비(RLP-INV-015).
- **spg governed-artifact-kind(name-collision)**: `spg/vocabulary.py:217-219` 3 토큰 — spg가 STM 아티팩트 *종류
  이름*을 열거(§3.5 seal 2).
- **sir -028 handoff(anticipation seam)**: `sir/predicates.py:15`·`sir/state.py:46` "-028 handoff … not landed
  (injected opaque coordinates)". sir가 STM restrictive-monitoring-signal(§17 handoff)을 예정 주입 소비.

**판정**: 이 네 좌표는 전부 STM이 생산할 것의 **개념/값/종류-이름/차원-이름**이며, 소비 형태는 익명 bool/generation/
문자열-토큰/차원-이름이라 **sibling edge는 여전히 0**이고 **naming은 약한 soft load-bearing**(§0.4a). STM은 각 좌표의
*아티팩트·완전성 판정 substrate·값*을 소유하는 **greenfield 생산자**(RLP 미러 아님)다.

> **직접 배선 금지(#28 SIR §3.6 Ambiguity 처방 동형·명문화)**: STM의 L1 술어는 cur의 MONITORING 차원 완전성 판정을
> **직접 대입·재저작하지 않는다** — STM은 Monitor Generation·Continuous Conformance Snapshot digest만 생산하고, 그
> 값이 cur vector의 MONITORING 슬롯을 채우는 것은 downstream(cur/egress transaction) 소유다. 이 "직접 배선 금지"를
> §4.1 canary(`DimensionKey`·`vector_complete` 문자열이 STM 모듈에 부재)와 §7.2 seam 회귀로 봉인한다.

**이 forward seam이 naming을 SIR보다 강하게 만들지만**(4-clade committed 소비), 소비 형태는 전부 익명 좌표라 **sibling
edge는 여전히 0**이다. **리뷰어 공격 지점(§10.2-⑧)**: "rlp/cur가 `tos.stm` 타입을 이연받았으니 inbound edge" —
반론: 익명 `bool`/generation/차원-이름·`tos.stm` 미참조·STM은 개념·값 생산자·edge 0.

---

## 4. 술어 규율 (canary·극성·reconcile·집합·∅ 양방향·3치 접기)

### 4.1 금지 동사 canary (`test_stm_void_canaries.py`)

STM 모듈은 **순수·비전송·비수집·비변이·clock-free**임을 정적 회귀로 봉인한다: `tos/src/tos/stm/**`에 `send`/
`transmit`/`emit`/`scrape`/`collect`/`publish`(수집·전송)·`sign`/`arm`/`rearm`(실행)·`mutate`/`reserve`/`release`/
`commit_capacity`(capacity)·`page`/`alert`/`escalate`/`deliver`(**실행 동사** — STM는 alert *구조 판정*만·실 발송
아님)·`clear_halt`·`open`/`connect`/`socket`(network)·`time.time`/`datetime.now`/`monotonic`(clock)·`os.environ`·
`exec`/`eval`/`importlib`/`__import__` 문자열이 **부재**함을 grep 회귀로 확인(egress/cur/rlp/wdr/sir `test_*_void_
canaries.py` 동형). monitoring artifact가 authority/enforcement/collection을 생성하지 않음을 코드 수준에서 증언(STM-
INV-001·§1 line 29 "It SHALL NOT own the underlying business fact … transmit to a broker"). **주의**: 술어 이름의
명사형(`deterministic_evaluation_*`·`coverage_*`·`alert_state_*`)은 허용(판정 술어)이나 동사형 실행 함수는 금지 —
canary가 `def deliver(`/`def scrape(`/`def escalate(` 같은 실행 시그니처 부재를 확인.

**cur 직접 배선 금지 canary(§3.6)**: STM 모듈에 `DimensionKey`·`vector_complete`·`MANDATED_DIMENSION_FLOOR` 문자열이
**부재**함을 grep 회귀로 확인 — STM은 Monitor Generation·Continuous Conformance Snapshot digest(값)만 생산하고 cur의
MONITORING 차원 완전성 판정을 **직접 저작·대입하지 않는다**(완전성은 cur-owned·§3.6). 이 canary가 STM이 cur 차원
판정을 참칭하지 않음을 봉인한다(#28 C1 재발 방지).

### 4.2 truthy-sentinel 봉인 (`test_stm_truthy_sentinel.py`)

`AggregateConformanceResult`·`DashboardStatusToken`·`MonitoringGapKind`·`NumericInputState`·`BoundSemanticKind`·
`TelemetryCriticality`·`SuppressionLifecycleState`·`CoverageDimension`(**8종**·M2 CoverageDimension 추가)는
`_NonTruthyStrEnum`(`__bool__ ⇒ TypeError`). `CoverageDimension`은 cur `DimensionKey`처럼 set-membership(⊆)으로
소비되나 truthy-seal은 방어적 상위집합(무해). 회귀: 각 멤버에 `bool(x)`가 `TypeError`; 소비 게이트는 `result is
AggregateConformanceResult.CONFORMING`·`state is
NumericInputState.WELL_FORMED`·`token is DashboardStatusToken.CURRENT_CONFORMING` 명시 비교만 사용(`if result:`/
`if state:` 부재 grep). `RESTRICTED`/`NON_CONFORMING`/`UNKNOWN`/`STALE`/`GAP`/`UNVERIFIED`/`NAN`/`PERCENTILE`를
truthy로 오독하는 fail-open 방지. **결과 타입 `__bool__ ⇒ TypeError` 구조봉인**(ioc `ConformanceResult.__bool__`
`vocabulary.py:63` 선례·#14 M1) — 술어가 sentinel 가능 값의 truthiness를 쓰지 않음을 타입이 강제. **가장 위험한
케이스**: `AggregateConformanceResult`의 `if snapshot.aggregate_result:`는 `RESTRICTED`/`NON_CONFORMING`/`UNKNOWN`
(전부 non-empty string)을 truthy "CONFORMING"으로 오독하는 **치명적 silent fail-open** — 이것이 truthy-sentinel의
1순위 방어 대상이다.

### 4.3 극성 규율 (§4.2 — #18/#22/#23/#25 재발 방지 + committed 좌표 정합·전수 점검·3치 접기)

**핵심 교훈(#18/#22 MAJOR-2·#23/#25 상속)**: `bool | None` 필드에 `if field:`/`if not field:`를 쓰면 `None`이
극성에 따라 **fail-open**한다. **규율(task 명시)**: **음극성 소비의 allow/clear 조건은 `is False`만 사용하고
`is not True`를 절대 쓰지 않는다**(`x is not True`는 `None`을 clear로 오독하는 fail-open — #18/#22/#23/#25 재발
결함). 양극성 allow는 `is True`. `None`은 **양쪽 극성 모두에서 UNKNOWN ⇒ deny/restrict**로 수렴. deny 정규화:
양극성 `is not True`·음극성 `is not False`(둘 다 None ⇒ deny).

**3치 접기 규율(#28 MAJOR-2 상속·본 문서 노른자 2에 특히 중요)**: "증명 불가"와 "부정 확정"을 **같은 bool 버킷에
접지 않는다** — clear는 **양성 증명만**. 예: `ordering_provable`(§5.10 SendRaceOrdering)는 (증명됨-RESTRICT<SEND ⇒
deny) / (증명됨-safe ⇒ ok) / (증명불가 ⇒ potentially-live+capacity-covered)의 **3치**이며 뒤 둘을 같은 True로 접지
않는다(§6b). 마찬가지로 `AggregateConformanceResult`는 `CONFORMING`(양성 증명) ≠ `UNKNOWN`(증명 불가) ≠
`NON_CONFORMING`(부정 확정)의 3+치이며 `if result:`로 뭉개지 않는다(§4.2).

**표 구조(M5 열 분리)**: 아래 표는 **판정 필드(술어 conjunct에서 직접 clear/deny를 결정)**만 등재한다. 판정에
참여하지 않는 **표지(비판정) 필드**는 표 아래 별도 목록에 분리 등재(§2.4 disposition·무성 미소비 금지·OQ1).

| 판정 필드 | 극성 | clear(allow) 조건 | deny 조건 | deny 정규화 | 근거 |
|---|---|---|---|---|---|
| `MonitorCoverageManifest.is_complete` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §9 "complete and exact"·INV-002:163 |
| `CoverageItem.closure_1_to_12_complete` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny(item incomplete)` | §9 line 275–286·INV-002:163 |
| `CoverageItem.restrictive_response_present`/`alert_path_present`/`evidence_path_present`/`currentness_rule_present` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §9 item 7/8/9/11 |
| `CoverageItem.approved_exclusion_proof_present` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny(no proof⇒no exclusion)` | §9:290 independent-governance proof |
| `MonitoredAssumptionIntake.admitted_as_coverage_item` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny(out-of-band)` | §9:288 patch "never as an out-of-band addition" |
| `MonitoredAssumptionIntake.runtime_falsity_invalidates_property` (M5 신규) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny(non-invalidating)` | §9:288·ADR-DEV-011 Monitored Assumption |
| `ApprovedBoundBinding.units_exact`/`window_inside_bound`/`uncertainty_treated` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §11:312–314·INV-007:183 |
| `ContinuousConformanceSnapshot.source_continuity_present` (M5 신규) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §12 snapshot binding |
| `SafetyMonitoringGap.closure_proof_present` (M1/M5 신규) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ gap 미종결` | §13:349 "Closure requires continuity re-established" |
| `SendRaceOrdering.ordering_provable` | **양극성(3치 상위)** | `is True`(+RESTRICT<CAPABILITY_CLAIM 아님) | `is False` / `None` | `is not True ⇒ potentially-live+capacity-covered` | §18:421·§4.3 3치 |
| `CoverageItem.excluded` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ approved-proof 게이트 발동(C1)` | §8:249·§9·§5.1 conjunct 3/4 |
| `MonitorCoverageManifest.coverage_score_present` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ score≠closure deny` | §9:292 "cannot replace item-level closure" |
| `ApprovedBoundBinding.permits_individual_exceedance` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny(hard-max violated)` | §11:314 "window that permits an individual exceedance" |
| `CriticalTelemetryIdentity.semantics_reinterpreted`/`hash_equality_claims_equivalence` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny` | §10:302·§8:267 |
| `TelemetrySemanticView.cross_host_monotonic_subtracted`/`identical_values_claim_continuity`/`age_clamped_from_unbounded` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny` | §10:300–302 |
| `SilenceObservation.treated_as_healthy` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny(absence≠health)` | §1:23·INV-004:171 |
| `MonitoringUnknownState.telemetry_missing`/`state_stale`/`state_conflicting`/`state_ambiguous`/`state_discontinuous`/`generation_mixed`/`state_unverifiable` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny + greatest-credible` | §13·INV-005:175 |
| `MonitoringSuppression.disables_collection`/`disables_evaluation`/`disables_restrictive_signaling`/`disables_evidence`/`disables_generation_advancement`/`disables_final_egress_denial` (§5.11:151 6금지·M6) | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny(suppression suppresses safety)` | §5.11:151·§15:367–376·INV-008 |
| `CommonModeDisclosure.self_health_as_proof`/`validates_own_continuity_by_own_output`/`residual_common_mode_disclosed`(양) | 혼합 | 음: `is False`·양: `is True` | 각 극성 반대/`None` | 음 `is not False`·양(residual) `is not True` ⇒ deny | §14:357/359 |
| `AlertStateVector.ack_implies_containment`/`advance_of_one_implies_another`/`adverse_record_dropped`/`elapsed_time_reset` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny` | §16:388/390·INV-009/010 |
| `BrokerFinalityTokens.missing_ack_treated_as_non_acceptance`/`cancel_ack_treated_as_fqp`/`unknown_effect_capacity_released` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny + worst-credible capacity` | §19:429·INV-013 |
| `DashboardStatusView.defaulted_to_green` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny(no-green-default)` | §23:499 no-green-default |
| `MonitoringRecoveryInputs.revived_prior_authority`/`resumed_trial`/`restored_production_scope`/`auto_re_armed` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny(non-revival)` | §24:511·INV-015 |
| `RestrictiveMonitoringSignal.downgrades_existing_fence`/`selects_narrower_scope`/`clears_local_latch`/`publishes_no_incident` (§17:402 4금지·M6) | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny` | §17:402·INV-011 |
| `AlertEscalationRecord.unioned_or_substituted` (M1 신규) | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny(single-binding 위반)` | §5.9:143 no-union/substitute |

**표지(비판정) 필드 분리 등재(M5·OQ1·무성 미소비 금지)**:
- `SilenceObservation`: `no_alert`·`repeated_heartbeat`·`quiet_time`·`empty_query`·`green_dashboard`(5) — **명시 이연**
  (§2.4·판정은 `treated_as_healthy` 무조건 소비·표지는 런타임 관측 기록·MINOR-2 무조건 해석과 양립·docstring 화이트리스트).
- `MonitoringRecoveryInputs`: `restart`·`reconnect`·`failover`·`restore`·`queue_drain`·`alert_ack`·`replay`·
  `operator_return`·`quiet_time`(9) — **구조 파생 입력**(§2.4·표지 disjunction이 non-revival 4필드 게이트 발동·OQ1).
- `CommonModeDisclosure.claimed_independent`(표지·§6.4에서 `shared_dependencies≠∅ ∧ claimed_independent is True` 결합
  판정)·`DashboardStatusView.rendering_failed`/`state_unknown`(표지·§6.9 no-green-default 게이트 발동).

> **폐포 규율(§7.2 field-closure property·M5)**: 위 판정 표·표지 목록의 전 필드가 §2.4 선언 모델에 실재하고 **실제
> 소비 conjunct까지 존재**함을 property test로 양방향 강제(표에 있으나 모델에 없는 필드 0·모델 소비 필드가 표/목록에
> 없음 0·#28 MAJOR-1 교훈·upgrade 조건 (a)).

**전수 점검 회귀(`test_stm_polarity.py`)**: 모든 음극성 필드에 대해 `None` 입력이 **restricted/deny로 수렴**함을
property test(hypothesis)로 확인 — **`excluded=None`(C1·unknown-exclusion)이 coverage 계상을 우회하거나**·`treated_
as_healthy=None`이 "not-healthy-claim"으로·`disables_final_egress_denial=None`이 "not-disabling"으로 fail-open하는
재발을 구조 봉인. **`is not True`가 음극성 필드 소비에 나타나지 않음을 grep 회귀로 강제**(task 명시 규율·C1 자기위반
재발 방지). 모든 양극성 필드에 대해 `None`/`False`가 deny로 수렴.

### 4.4 그룹 reconcile 규율 (#22 MAJOR-1 재발 방지 — 전-entry 보수·no favorable union·INV-002) + ∅ 양방향

**핵심 교훈(#22 MAJOR-1)**: 여러 entry가 한 그룹/set에 매핑될 때 판정은 **첫-entry가 아니라 전-entry를 보수적으로
reconcile**해야 한다. STM의 reconcile 지점(§9 Monitor Coverage Manifest가 특히 강·INV-002):

- **`no_favorable_union`(§9:292·핵심·구조 파생)**: 여러 narrow manifest를 **유리한 union으로 넓은 coverage로 위조
  불가**(§9 line 292 "A favorable union of narrow manifests cannot create broader coverage"·"Coverage percentages,
  monitor counts, or dashboard completeness scores cannot replace item-level closure"). coverage 판정은 **item-level
  closure**(각 applicable obligation이 자기 coverage item + 1–12 closure)·aggregate score 아님. `coverage_score_
  present is not False` ⇒ deny(§4.3).
- **coverage completeness 집합 양방향(§9·INV-002·C1 극성)**: `applicable_obligations ⊆ {item.obligation_ref for item
  in coverage_items if item.excluded is False}` AND 역방향(coverage item에만 있고 applicable 아닌 phantom coverage는
  conflicting ⇒ 무시하되 완전성엔 무영향, 단 phantom exclusion은 deny). **C1**: 계상 필터는 음극성 clear `is False`만
  (`excluded=None` unknown-exclusion은 제외·conjunct 4 게이트로 회부·§5.1). 누락된 applicable obligation 하나라도 ⇒
  **gap, not exemption**(INV-002 line 163·§13). **집합 both-ways**(#10 교훈).
- **Monitor Generation floor(§5.5·§12·§18)**: 여러 generation entry ⇒ **MAX(최신 fence)** 채택(§5.5 monotonic·§12
  line 337 stale-owner)·첫-generation 아님·stale-writer 봉인(INV-016).

**∅ 가드 양방향(WDR/SIR v1.1 explicit-empty 선례·본 문서 특유 = 극성 반대 두 ∅)**: 공허 통과(vacuous pass)와 **과잉
봉합**(fail-closed 방향 과잉 거부) 모두 결함 클래스다. **본 문서 핵심 ∅ 규율 — coverage-completeness ∅ 과 determinism-
consistency ∅ 은 극성이 반대다**:

1. **coverage-completeness ∅ (완전성 술어·∅ = 판정 방향 확인 필수)**: `coverage_items=() ∧ applicable_obligations=∅`
   ⇒ **유효한 explicit-empty**(무-obligation 정상 운영·거부는 과잉 봉합)·단 `is_complete is True` 양성 확립 선행.
   `coverage_items=() ∧ applicable_obligations≠∅` ⇒ **deny**(누락·§9 gap·INV-002). `manifest is None` ⇒ deny(판정
   불가). `applicable_obligations=∅ ∧ coverage_items≠()` ⇒ deny(surplus/phantom·both-ways). **∅ 거부 전에 applicable
   측 확인**(WDR MAJOR-1 교훈 — ∅ 거부 방향 과잉 봉합 금지).
2. **determinism-consistency ∅ (관계 술어·∅ = valid True·극성 반대)**: `evaluations=()` 또는 singleton ⇒
   **`evaluation_is_deterministic = True`가 정답**(충돌 쌍 부재 = 비결정론 없음·safety property의 vacuous-True는
   건전). 단 이는 "어떤 evaluation이 존재함"을 주장하지 **않는다** — presence/completeness는 coverage 술어(§5.1)
   소관이다. **두 ∅의 극성 구별이 본 문서 최대 ∅ 함정**: 완전성 술어의 ∅ 는 (applicable 측 확인 후) deny 또는 valid-
   empty, 관계-일관성 술어의 ∅ 는 valid-True — 같은 `()` 입력이 술어 종류에 따라 반대 극성. 이 구별을 §7.2 both-ways
   canary와 §5.2 docstring에 명문화한다(리뷰어 공격 지점 §10.2-⑨).

**회귀(`test_stm_reconcile.py`)**: entry/obligation/evaluation 순서 permutation에 대해 verdict 불변(순서 독립) +
가장 보수적(no-favorable-union·item-완전·MAX-generation) 지배 + **coverage explicit-empty 유효·missing-obligation
deny·determinism ∅=True 양방향**을 property test로 확인.

---

## 5. 핵심 L1 술어 (§5 — 2 노른자 + 지지)

> 전 술어 규율 태그: **coverage-completeness / deterministic-evaluation predicate substrate only; STM-EV-001/005 전부
> NOT_IMPLEMENTED(둘 다 `EV-L1/3+Security` — `/3` 통합 + +Security forgery/drift 저항 대기). 전 owner verdict/
> generation/digest는 주입. L1은 coverage/determinism/bound 구조 판정만.**

### 5.1 `critical_coverage_complete_or_gap` (STM-EV-001 노른자·§9·§8·+Security 잔여)

**시그니처(전 입력 수용 확장·#21 NT C1/#24 PTF C1 동형 방지·M5 파라미터 개명)**: `critical_coverage_complete_or_
gap(manifest: MonitorCoverageManifest | None, applicable_obligations: frozenset[str], applicable_dimensions:
frozenset[CoverageDimension], submitted_assumption_ids: frozenset[str]) -> bool` — **완전성 판정 대상(applicable_
obligations·applicable_dimensions·submitted_assumption_ids)을 시그니처에 명시** — `manifest is None` ⇒ deny.
**M5 개명**: 파라미터명을 `submitted_assumption_ids`로(§2.4 모델 필드 `MonitorCoverageManifest.submitted_monitored_
assumptions: tuple[MonitoredAssumptionIntake, ...]`와 동명 이형 충돌 해소 — 파라미터는 id 집합·모델 필드는 intake
객체 tuple). **`True` = coverage가 complete & exact & 무-authority**, `False` = incomplete/gap/부정합/판정 불가.

**판정(전부 AND·fail-closed)**:
1. **∅-seal 양방향(§4.4·완전성 술어)**: `manifest is None` ⇒ `False`. **explicit-empty 유효**: `manifest.coverage_
   items=() ∧ applicable_obligations=∅ ∧ manifest.is_complete is True` ⇒ 무-obligation 정상(거부는 과잉 봉합). `coverage_
   items=() ∧ applicable_obligations≠∅` ⇒ deny(누락·gap·§9·INV-002). `applicable_obligations=∅ ∧ coverage_items≠()`
   ⇒ deny(surplus phantom·both-ways). **∅ 거부 전 applicable 측 확인**(WDR MAJOR-1 교훈).
2. **all-false authority(핵심·INV-001)**: `manifest.authority_effect`의 전 필드 `is False`(§2.4·`AllFalseMonitoring
   Authority` model_validator any-True ⇒ error). coverage manifest가 capacity/approval/live-auth/transmission/
   incident-closure/readiness/re-arm/protective 무부여(§1 line 25·**INV-001 line 159**). authority-effect True 하나라도
   ⇒ deny.
3. **coverage completeness 집합 양방향(§9·INV-002·구조·C1 극성 교정)**: `applicable_obligations ⊆ {item.obligation_
   ref for item in manifest.coverage_items if item.excluded is False}` AND 각 매핑 item의 `closure_1_to_12_complete
   is True`(§9 1–12 전수·§4.3). **C1 교정**: 계상 필터를 `item.excluded is False`(음극성 clear·`is not True` 금지·
   §4.3)로 — `excluded=None`(unknown-exclusion) item은 계상집에서 제외되고 conjunct 4 approved-proof 게이트로 회부.
   누락된 applicable obligation 하나라도 ⇒ **gap, not exemption**(**INV-002 line 163** "Missing or unknown coverage
   is a gap, not an exemption"). **집합 both-ways**(phantom coverage 무영향·phantom exclusion deny).
4. **no self-exemption(§8:249·§9·C1 게이트 교정)**: 어떤 item이 `excluded is not False`(True 또는 **None=unknown-
   exclusion**)이면 `approved_exclusion_proof_present is True`(양극성·§9:290 "independent policy governance proves that
   telemetry corruption or omission cannot affect a safety decision")여야 하고, 아니면 deny. **C1 교정**: 게이트를
   `excluded is not False`로 — `excluded=None`이 게이트를 비켜가 무검증 계상되던 fail-open 봉인(§4.3 음극성 deny
   정규화 `is not False`). `criticality is TelemetryCriticality.UNKNOWN_MATERIALITY`인 item은 `CRITICAL`로 접혀 배제
   불가(§8:249 "Unknown materiality is Critical"). producer/monitor-owner self-classify non-Critical 금지.
5. **item-level closure·no favorable union(§9:292·구조 파생)**: `manifest.coverage_score_present is False`(음극성·
   §4.3) — coverage %·monitor count·dashboard completeness score가 item-level closure를 대체하면 deny(§9:292). 여러
   narrow manifest의 유리한 union으로 넓은 coverage 위조 불가(§4.4 reconcile).
6. **dependency-closure completeness(§9 item 2·MINOR-3 포함-only·vacuous-True 차단)**: 각 매핑 item의 `applicable_
   dimensions ⊆ item.dependency_closure_dimensions`(**포함만·MINOR-3 — 초과 차원은 더 넓은 closure라 무해·WDR MAJOR-1
   과잉 봉합 회피·"양방향" 삭제**). 미표현(applicable에 있으나 closure에 없는) 차원 하나라도 ⇒ incomplete ⇒ deny
   (cur `CONTEXT` vacuous-pass 교훈 동형·§0.5). `CoverageDimension` closed enum == **§12:327/§13:347 11차원**(M2·§7.2
   3자 drift·§부록 L·v1.0 "§9 차원" phantom 삭제).
7. **Monitored-Assumption intake 3층 폐포(§9:288 patch·TAB-INV-006·survey line 619 해소·M5 실소비)**: (i)
   `submitted_assumption_ids ⊆ {item.obligation_ref for item in manifest.coverage_items}`(id 편입) AND (ii) 대응하는
   각 `MonitoredAssumptionIntake.admitted_as_coverage_item is True`(양극성·§4.3) AND (iii)
   `runtime_falsity_invalidates_property is True`(양극성). **M5 3층**: patch-0027 요건 필드(`admitted_as_coverage_item`·
   `runtime_falsity_invalidates_property`)를 **실제 소비**(§9:288 "a manifest item subject to the same §9 1–12 closure
   … admitted through the coverage-completeness discipline (STM-INV-002) and **never as an out-of-band addition**").
   out-of-band(id 부재) 또는 미편입(`admitted is not True`) 또는 non-invalidating(`runtime_falsity is not True`) ⇒
   deny. **ADR-DEV-011 TAB-INV series(별개·§0 각주)의 런타임 validity를 monitored obligation으로 강제 편입** —
   patch-0027 핵심 요건이며 EV 불변(register 372).

**반환**: 위 전부 성립시에만 `True`. **STM-EV-001을 닫지 않음**(`/3` 통합 + **+Security coverage/manifest forgery·
suppression 저항** 잔여 — §22 line 472–479 "monitor policy, manifests … registry"·§30 gate 2 conservative coverage
compiler·독립 리뷰는 +Security 런타임). §9 12-item anchor == `CoverageItem` closure 필드(§7.2 drift·§부록).

### 5.2 `deterministic_evaluation_bound_integrity` (STM-EV-005 노른자·§11·§12·결정론 property 핵심·+Security 잔여)

> **노른자 2 특유 — 결정론(determinism)이 핵심**(task 명시): 동일 입력 ⇒ 동일 판정. STM은 evaluator를 *실행하지
> 않으므로*(런타임·§0.2) L1-decidable 결정론은 **evaluation 레코드 corpus의 일관성 관계**로 표현한다 — 같은
> (evaluator_digest, canonical_input_digest)를 가진 두 레코드가 다른 result를 가지면 **비결정론 위반**(fail-closed).
> 이것이 VER EV-L1 정의("property-based testing, and deterministic simulation")의 정면 실현이다.

**시그니처(4부 합성·C2 presence 게이트 신설)**: 노른자는 네 부분의 합성이다.
- (0) **presence + ∅ 양방향(C2·신설·전면-∅ 공허 True 봉인)** — required-측 입력을 시그니처에 명시.
- (a) **관계 결정론** `evaluation_is_deterministic(evaluations: tuple[MonitorEvaluation, ...]) -> bool`.
- (b) **per-bound integrity** `bound_integrity_preserved(bound: ApprovedBoundBinding | None) -> bool`.
- (c) **per-evaluation fail-closed numeric** `numeric_result_not_conforming_by_default(evaluation: MonitorEvaluation
  | None) -> bool`.
합성 노른자 `deterministic_evaluation_bound_integrity(evaluations: tuple[MonitorEvaluation, ...], bounds: tuple[
ApprovedBoundBinding, ...], required_evaluation_keys: frozenset[tuple[str, str]], applicable_bound_refs:
frozenset[str]) -> bool` = **(0)** AND (a) AND (전 evaluation에 대해 (c)) AND (전 bound에 대해 (b)).

**(0) presence + ∅ 양방향(C2·§4.4·전면-∅ 공허 True 봉인·핵심)**:
1. **evaluation presence ∅ 양방향(완전성 술어 극성)**: `required_evaluation_keys=∅ ∧ evaluations=()` ⇒ **valid-empty
   True**(무-required monitor 정상·거부는 과잉 봉합). `required_evaluation_keys≠∅ ∧ evaluations=()` ⇒ **deny**(§1:23·
   **STM-INV-004 line 171** "empty query … proves safety" 자기-노른자 위반 봉인). `required_evaluation_keys=∅ ∧
   evaluations≠()` ⇒ **surplus deny**(both-ways). AND `required_evaluation_keys ⊆ {(e.evaluator_digest, e.canonical_
   input_digest) for e in evaluations}`(각 required 키가 corpus에 present·미충족 ⇒ deny).
2. **bound presence(M4 결속·favorable-subset 봉인)**: `applicable_bound_refs ⊆ {b.bound_binding_digest for b in
   bounds}` AND `{e.bound_binding_digest for e in evaluations} ⊆ {b.bound_binding_digest for b in bounds}`(evaluation이
   참조하는 bound가 미제출이면 favorable-subset 우회 ⇒ deny·#22·M4). surplus bound(참조 없는 bound)는 무해.
3. **C2 근거 명문화(두 ∅ 극성 구별 강화)**: 이 (0) presence 게이트가 "빈 corpus + non-empty required ⇒ False"를
   강제하므로 노른자 2는 더 이상 전면-∅에서 공허 True를 반환하지 않는다. (a) 관계 술어 **단독의** ∅=True는 유지
   (충돌 쌍 부재 = 안전 property의 건전한 vacuous-True)·presence는 (0)이 소유 — 완전성 술어(0·§4.4 좌측)와 관계-
   일관성 술어(a·§4.4 우측)의 **극성 반대 두 ∅**가 이제 노른자 내부에서 함께 성립(§10.2-⑨).

**(a) `evaluation_is_deterministic`(관계·§11 line 312·핵심)**:
1. **∅-seal(관계 술어·극성 반대·§4.4·C2 정합)**: `evaluations=()` 또는 singleton ⇒ `True`(충돌 쌍 부재 = 비결정론
   없음·vacuous-True 건전). **단 presence 미주장** — "어떤 evaluation이 존재함"은 **합성 노른자의 (0) presence 게이트
   소관**(C2·§4.4 두 ∅ 극성 구별). (a)를 단독 호출하면 ∅=True이나 합성 노른자는 (0)이 required≠∅ ∧ corpus=()를
   deny하므로 전면-∅ 공허 통과 없음. docstring에 "이 True는 결정론 위반 부재만 주장하고 evaluation 존재를 주장하지
   않음·존재는 (0)이 강제"를 명기(리뷰어 §10.2-⑨).
2. **결정론 관계(§11 line 312 "deterministic for identical inputs")**: 임의의 두 `e1, e2 ∈ evaluations`에 대해
   `(e1.evaluator_digest, e1.canonical_input_digest) == (e2.evaluator_digest, e2.canonical_input_digest)` ⇒
   `e1.result is e2.result AND e1.numeric_input_state is e2.numeric_input_state`. 하나라도 위반(같은 키·다른 판정)
   ⇒ **비결정론 위반 ⇒ `False`**(fail-closed·§11:316 "evaluator disagreement yields UNKNOWN or a restrictive
   result"). **canonical determinism 근간**: `canonical_input_digest`는 canonical `EVL1ProvisionalCanonicalizer`의
   결정론적 digest이므로(§3.1) 같은 입력 ⇒ 같은 digest ⇒ 같은 키 — 키 자체의 결정론은 canonical의 이미-테스트된
   성질에 위임(재저작 아님).
3. **truthy 봉인**: result/state 비교는 `is` 명시(§4.2).

**(b) `bound_integrity_preserved`(per-bound·§11 line 314·INV-007)**:
1. **∅-seal**: `bound is None` ⇒ `False`.
2. **hard-bound kind 보존(§11:314+§6:183·M3 whitelist 반전·denylist→whitelist)**: `bound.approved_bound_kind ∈
   HARD_KINDS`(= {HARD_MAXIMUM, HARD_MINIMUM, EXACT_MATCH, MONOTONIC_SEQUENCE})이면 **`bound.implemented_as_kind ∈
   HARD_KINDS AND bound.implemented_as_kind is bound.approved_bound_kind`**(정확 보존·**whitelist**)여야 통과·그
   외(WEAK 6·NEUTRAL 2·미지 신규 멤버) 전부 **자동 deny**(§11 line 314 "cannot be implemented as a percentile,
   average, best-effort target" + §6:183 "local threshold, hidden grace period, or favorable sampling rule"). **M3
   근거(#25 RLP MAJOR-1 동형)**: v1.0의 denylist(`implemented ∈ {PERCENTILE,AVERAGE,BEST_EFFORT}` ⇒ deny)는 새 weak
   멤버(LOCAL_THRESHOLD 등)가 자동으로 샜다 — whitelist는 미지/신규 멤버를 자동 deny. **전순서 발명 금지**(§4.3 3치)
   — hard/weak 판정은 명시 멤버 집합 membership이지 강도 순위 아님·HARD_KINDS frozenset은 enum 파생.
3. **no individual exceedance(§11:314 음극성)**: `bound.permits_individual_exceedance is False`(음극성·`is not
   False` ⇒ deny·§4.3) — hard-max window가 개별 초과를 허용하면 deny(§11:314 "window that permits an individual
   exceedance").
4. **units/window/uncertainty(§11:312–314 양극성)**: `bound.units_exact is True` AND `bound.window_inside_bound is
   True`(debounce/grace/hysteresis가 detection/containment bound 안에 계상·§11:314 "count inside the applicable
   detection or containment bound unless the approved Verification Profile explicitly defines otherwise") AND
   `bound.uncertainty_treated is True`. `None`/`False` ⇒ deny.

**(c) `numeric_result_not_conforming_by_default`(per-evaluation·§11 line 316·INV-007)**:
1. **∅-seal**: `evaluation is None` ⇒ `False`.
2. **fail-closed numeric(§11:316 핵심)**: `evaluation.result is AggregateConformanceResult.CONFORMING` ⇒
   `evaluation.numeric_input_state is NumericInputState.WELL_FORMED`여야 한다. 대우: `numeric_input_state`가
   `WELL_FORMED`가 아닌데(UNKNOWN/NAN/INFINITY/OVERFLOW/UNDERFLOW/NON_CONVERGENT/UNIT_MISMATCH/PARSER_DIFFERENTIAL/
   MISSING_SAMPLE/INSUFFICIENT_HISTORY/EVALUATOR_DISAGREEMENT — 11 malformed state) `result is CONFORMING`이면
   **deny**(§11 line 316 "It never yields `CONFORMING` by default"). malformed numeric ⇒ result는 반드시 {RESTRICTED,
   NON_CONFORMING, UNKNOWN} 중 하나.
3. **truthy 봉인**: `is` 명시 비교만(§4.2·`AggregateConformanceResult`·`NumericInputState` truthy-untestable).

**반환(합성)**: **(0) presence+∅** AND (a) 관계 결정론 AND (전 evaluation (c)) AND (전 bound (b)) 성립시에만 `True`.
**STM-EV-005를 닫지 않음**(`EV-L1/3+Security` — `/3` 통합 + **+Security evaluator differential·parser drift·threshold
weakening 저항** 잔여·§30 gate 4 "deterministic monitor evaluators and independent differential tests reject … parser
drift, numeric failure, and threshold weakening"은 +Security 런타임). §11 **12-token numeric·12-token bound** anchor ==
`NumericInputState`·`BoundSemanticKind`(§7.2 drift·§부록 B/C). **mandated 픽스처(C2·M4)**: "빈 corpus + non-empty
required ⇒ False"·"약한 binding 참조 + 미제출 bound ⇒ False"·"같은 키 다른 result ⇒ False"·"hard-approved + weak-
implemented ⇒ False"를 §7.2 `test_stm_determinism.py`에 명시.

> **지지 술어 `conformance_requires_complete_current_valid(snapshot: ContinuousConformanceSnapshot) -> bool`(§12:335·리뷰 MINOR-4 시그니처 확정)**: `ContinuousConformanceSnapshot.aggregate_
> result is AggregateConformanceResult.CONFORMING`이면 모든 required monitor present·source-continuity·completeness·
> independence 필드가 확립(§12 line 335 "`CONFORMING` requires every required item to be current, complete, and
> independently valid under policy"). malformed-model validator(§2.3)가 construction 시 이미 봉인·술어 2층 재확인.
> **CONFORMING조차 authority 무부여**(all-false·§6.9·§1:25).

---

## 6. predicate-only substrate (§6 — 닫지 않음·규모 절반 이상·§0.4c) + not-Phase-1 (§6b) + 순수 런타임/벤더 (§6c)

> 전 술어 규율 태그: **predicate substrate only; 해당 STM-EV 전부 NOT_IMPLEMENTED(≥ L2 component-fault +
> +Security/+Broker 대기). L1-decidable 순수 판정을 저작하되 어떤 STM-EV도 닫지 않는다.** INV 밀도 > L1 행이므로
> 이 §6가 본 계약 규모의 절반 이상이다(§0.4c·§0.1-6). 16 INV 중 11건이 여기 substrate.

### 6.1 `telemetry_semantics_exact` (§10·STM-EV-002 substrate·+Security·INV-003)
`telemetry_semantics_exact(identity: CriticalTelemetryIdentity | None, view: TelemetrySemanticView | None) -> bool`:
**∅-seal** + identity/scope/source/units/schema/meaning/derivation/continuity/time-basis가 immutable·verified·
consumer가 reinterpret/default 불가(§10 line 300–302·INV-003 line 167). 구조: `identity.semantics_reinterpreted is
False` AND `identity.hash_equality_claims_equivalence is False`(§8:267) AND `view.cross_host_monotonic_subtracted is
False`(§10:302 "SHALL NOT be directly subtracted") AND `view.identical_values_claim_continuity is False`(§10:300) AND
`view.age_clamped_from_unbounded is False`(§10:302). 전 음극성 `is False`만(§4.3). 실 source-continuity 런타임은
+Security. `EV-L2/3+Security`.

### 6.2 `absence_is_not_health` (§4·§1:23·STM-EV-003 substrate·하한 L2·INV-004·보수 분기 명시)
`absence_is_not_health(obs: SilenceObservation | None) -> bool`: **∅-seal** + no-alert/heartbeat/quiet-time/empty-
query/green-dashboard가 safety/completeness/currentness/containment **증명 아님**(§1 line 23·INV-004 line 171 "No
alert, repeated health heartbeat, quiet time, successful scrape, empty query, or green dashboard proves safety").
구조: `obs.treated_as_healthy is False`(음극성·`is not False` ⇒ deny). **보수 분기 독립 노출(#28 MAJOR-3 상속)**:
"모든 silence 표지 True + `treated_as_healthy is False`"[정직한 침묵 — allow]와 "임의 silence 표지 + `treated_as_
healthy is True`"[fail-open 시도 — deny] 픽스처를 §7.2에 **각각 명시**(지배 분기 없는 픽스처). `EV-L2/3`.

### 6.3 `unknown_is_restrictive` (§13·STM-EV-003 substrate·하한 L2·INV-005·음극성 전수)
`unknown_is_restrictive(state: MonitoringUnknownState | None) -> bool`: **∅-seal** + `telemetry_missing`·`state_
stale`·`state_conflicting`·`state_ambiguous`·`state_discontinuous`·`generation_mixed`·`state_unverifiable` 전부
`is False`(§4.3·INV-005 line 175 "blocks dependent new risk and expands to the greatest credible scope"). **하나라도
`is not False`(True 또는 None) ⇒ deny + greatest-credible 확장**(주입 opaque scope 좌표). **음극성 소비는 `is False`
만**(task 규율). `EV-L2/3`.

### 6.4 `common_mode_is_not_independence` (§14·STM-EV-004 substrate·+Security·INV-006)
`common_mode_is_not_independence(disc: CommonModeDisclosure | None) -> bool`: **∅-seal** + shared source/collector/
parser/clock/datastore/network/admin/identity/deployment/route/vendor가 independent path로 **불계상**(§14 line 355·
INV-006 line 179). 구조: `disc.shared_dependencies ≠ ∅ ∧ disc.claimed_independent is True` ⇒ deny(공유 의존이 있으면
independent 주장 불가·disclosed common mode) AND `disc.self_health_as_proof is False`(§14:359 "treat its own health
endpoint as proof") AND `disc.validates_own_continuity_by_own_output is False`(§14:359) AND `disc.residual_common_
mode_disclosed is True`(양극성·§14:357 잔여 공유 disclose). 실 effective-control 분석·독립 transport는 +Security/hag.
`EV-L2/3+Security`.

### 6.5 `suppression_cannot_suppress_safety` (§15·STM-EV-006 substrate·+Security·INV-008)
`suppression_cannot_suppress_safety(sup: MonitoringSuppression | None) -> bool`: **∅-seal** + suppression이 source
collection·invariant evaluation·restrictive signaling·evidence·generation advancement·final-egress denial을 disable
**불가**(**§5.11 line 151**·INV-008 line 187). 구조(§5.11:151 6금지·전 음극성·M6): `sup.disables_collection is False`
AND `sup.disables_evaluation is False` AND `sup.disables_restrictive_signaling is False` AND `sup.disables_evidence is
False` AND `sup.disables_generation_advancement is False` AND `sup.disables_final_egress_denial is False`(전 음극성·
§4.3·`is not False` ⇒ deny) AND (§15:367–376 8 preserved-active function이 전부 `sup.preserved_functions`에 present)
AND (`sup.lifecycle_state is SuppressionLifecycleState.EXPIRED ∨ ... UNKNOWN` ⇒ restrictive+unsuppressed·§21:458).
suppression≠Safety Deviation Decision(§15:365·wdr 주입·§3.5). 실 승인·expiry 런타임은 +Security. `EV-L2/3+Security`.

### 6.6 `alert_state_is_orthogonal` + `loss_preserves_negative_facts` (§16·STM-EV-007 substrate·+Security·INV-009/010)
`alert_state_is_orthogonal(vec: AlertStateVector | None) -> bool`: **∅-seal** + detection/delivery/ack/escalation/
containment/incident/recovery/economic-finality가 **독립 상태**·advancement of one never implies another(§16 line 388·
INV-009 line 191). 구조: `vec.ack_implies_containment is False`(§16:388 "acknowledgement … is not containment,
remediation, broker finality, incident closure, recovery readiness, or re-arm") AND `vec.advance_of_one_implies_
another is False`. `loss_preserves_negative_facts(vec)`: overflow/queue-pressure/retry/dedup/delivery-failure가 adverse
state 우선 폐기·elapsed time reset **불가**(§16 line 390·INV-010 line 195). 구조: `vec.adverse_record_dropped is
False` AND `vec.elapsed_time_reset is False`(전 음극성). 실 delivery/escalation 런타임은 +Security. `EV-L2/3+Security`.

### 6.7 `handoff_is_non_authorizing` (§17·STM-EV-008 substrate·+Security·INV-011·**sir forward seam**)
`handoff_is_non_authorizing(signal: RestrictiveMonitoringSignal | None) -> bool`: **∅-seal** + monitoring이 sir/cur에
제안하는 signal이 **non-authorizing**(§17·INV-011 line 199 "Monitoring may request restriction and incident evaluation
only"). 구조(§17:402 4금지·전 음극성·M6): `all_false_monitoring_authority(signal.authority_effect)` AND
`signal.downgrades_existing_fence is False` AND `signal.selects_narrower_scope is False` AND `signal.clears_local_latch
is False` AND `signal.publishes_no_incident is False`(전 음극성·§17 line 402 "No monitor or alert may downgrade an
existing fence or incident, select a narrower scope, clear a local latch, or publish `NO_INCIDENT`"). **forward seam 정합(§3.6)**: STM은 §17 handoff signal(restrictive-monitoring-signal)을
생산하고 sir가 이를 주입 opaque 좌표로 하류 소비(`sir/predicates.py:15` "-028 handoff … not landed")·incident
authority(materiality/severity/Incident Generation)는 sir 소유·재저작 안 함. **NO_INCIDENT 봉인 주의(#28 SIR §4.4
phantom 교훈)**: `publishes_no_incident`는 STM signal이 `NO_INCIDENT`를 발행하지 않음을 봉인하는 음극성 필드이지
`NO_INCIDENT` enum-token 소유가 아니다(ADR §17:402는 금지 조항). 실 restrictive ingress·classification은 sir·+Security.
`EV-L2/3+Security`.

### 6.8 `broker_finality_unchanged` + `economic_effect_outlives_monitor_state` (§19·STM-EV-010 substrate·+Broker·INV-013)
`broker_finality_unchanged(tokens: BrokerFinalityTokens | None) -> bool`: **∅-seal** + missing-ACK은 non-acceptance
**아님**(§19 line 429 "Missing broker ACK remains possible acceptance")·Cancel-ACK은 FQP **아님**(§19:429 "Cancel ACK
is not Final Quantity Proof")·UNKNOWN effect는 capacity-consuming(§19:429). 구조: `tokens.missing_ack_treated_as_non_
acceptance is False` AND `tokens.cancel_ack_treated_as_fqp is False` AND `tokens.unknown_effect_capacity_released is
False`(전 음극성). `economic_effect_outlives_monitor_state(authority: AllFalseMonitoringAuthority | None) -> bool`:
**all-false authority shape 소비**(WDR v1.2 `economic_effect_persists` 교훈 — expiry 필드를 직접 clear로 소비하면 INV
역전 위험) — `creates_capacity is False` ∧ `establishes_broker_finality is False`로 "policy/telemetry/snapshot/alert/
ack/suppression/page/incident/credential/session expiry가 economic effect/protective obligation/capacity commitment를
erase/release 불가"를 강제(§19 line 431 "expiry only restricts future authority. It never expires existing economic
effect …"·INV-013 line 207). **expiry 직접 clear 금지**(WDR v1.2 상속). 실 broker-finality 정량화는 +Broker.
`EV-L2/3+Broker`.

### 6.9 `evidence_and_status_honest` + `recovery_revives_nothing` (§23·§24·STM-EV-012 substrate·+Security·INV-014/015)
`evidence_and_status_honest(dash: DashboardStatusView | None) -> bool`: **∅-seal** + metrics/logs/alerts/dashboards/
pages/audit/replay/reports/postmortems가 preventive/restrictive enforcement **substitute 불가**(§23·INV-014 line 211)
+ dashboard가 7-token 구별·rendering-failure/unknown ⇒ **never green**(§23 line 499). 구조: `(dash.rendering_failed
is True ∨ dash.state_unknown is True) ∧ dash.status_token is DashboardStatusToken.CURRENT_CONFORMING` ⇒ deny·즉
`dash.defaulted_to_green is False`(음극성·§23:499 "Rendering failures or unknown state SHALL NOT default to green").
`recovery_revives_nothing(inputs: MonitoringRecoveryInputs | None) -> bool`: restart/reconnect/failover/restore/queue-
drain/alert-ack/replay/operator-return/quiet-time가 prior authority revive·trial resume·production scope restore·
auto-re-arm **불가**(§24 line 511·INV-015 line 215). 구조: `inputs.revived_prior_authority is False` AND `inputs.
resumed_trial is False` AND `inputs.restored_production_scope is False` AND `inputs.auto_re_armed is False`(전 음극성·
`is False`만·None ⇒ deny). fresh ADR-002-007/015 chain은 liveauth/hag 주입(§24·§3.5). 실 evidence custody·Recovery
Barrier는 evidence/sbr·+Security. `EV-L2/3+Security`.

### 6b. not-Phase-1 얇은 모델 property (STM-EV-009·011 — 닫지 않음)
- **monitor generation send-race(§18·STM-EV-009·`EV-L3+Security`)**: 순서 permutation model(`RESTRICT<SEND ⇒
  deny`·`SEND<RESTRICT<FIRST_BYTE ⇒ potentially-live + capacity-covered`·`ordering_provable is not True ⇒
  potentially-live`·no-blind-retry·§18 line 421 "If ordering between a material monitoring invalidation and first
  broker-directed byte cannot be proven, the attempt remains potentially live, capacity-covered, and ineligible for
  blind retry"). **3치 접기(§4.3)** — (증명됨-deny / 증명됨-safe / 증명불가-potentially-live)를 같은 bool에 접지
  않음. 실 cache-free currentness(§18 line 419 "Cached green state, TTL, heartbeat … is not proof")·`B_monitoring_
  gap_to_egress_deny` bound·deny-first latch는 **전부 +Security 런타임·egress**. SIR-EV-007·CUR-EV-005 동형 계층.
- **compromise / fencing / failure-domain(§22·§21·STM-EV-011·`EV-L3+Security`)**: `stale_writer_fenced` substrate만
  L1(superseded generation이 publish/accept 불가·`compare_order` 봉인·INV-016 line 219). 실 compromise expansion
  (§22 line 481 "expands to its greatest credible shared scope")·partition matrix(§21)·failure-domain 격리는 통합/
  적대 L3·failuredomain/egress 형제·런타임. §21 12-row failure matrix는 손전사 anchor(§7.2·§부록).

### 6c. 순수 런타임 / 벤더 절차 (L1 model property 없음·§0.4c over-realization 경계)
metrics DB/collector/message-bus/paging vendor/dashboard/on-call product/observability stack 선택(§4 line 97 non-
scope·벤더)·requirement/hazard/control registry + conservative coverage compiler(§9·§30 gate 2·런타임·+Security)·
source-continuity/semantic/unit/derivation/trustworthy-time/raw-retention/correction paths(§10·§30 gate 3·런타임·
+Security)·**deterministic monitor evaluator 런타임 + independent differential tests**(§11·§30 gate 4·+Security — 단
determinism *property*는 §5.2 L1)·Monitor Generation registry + owner-fencing + final-egress currentness(§12·§18·§30
gate 5·egress 런타임·+Security)·suppression/correlation/dedup/backpressure/delivery/ack/escalation/handoff protocol
(§15·§16·§30 gate 6·런타임·+Security)·monitoring/alert/dashboard/paging/ticket/evidence/replay identity no-route(§7·
§22·§30 gate 7·+Security)·ADR-002-025 EV-L6 demotion + ADR-002-027 incident handoff(§17·§20·§30 gate 8·rlp/sir)·
numeric bound 측정/승인(§8·§30 gate 9·INSTANCE·+Broker/+Security)·fault injection(§30 gate 11·L3·+Security)·policy
activation generation advance(§5.1·spg). 전부 런타임/벤더/+Security/+Broker/형제-owned — §9 Phase-0.

---

## 7. firewall allowlist + 회귀 스위트

### 7.1 import-closure allowlist (`test_stm_import_closure.py`)

`tos.stm`의 전이 import closure는 **`{canonical, ordering, stm}`에 국한**되어야 한다(egress/cur/rlp/wdr/sir `test_*_
import_closure.py` 동형·allowlist 형식). `tools/tos_firewall_check.py`(§3.2 ratified allowlist·default-deny)가
`shared.*`/`services.*`/`cli.*`/외부 수치 라이브러리/동적 escape/**형제 tos 패키지 import(특히 rcl — edge 0·cur —
forward seam은 익명 차원-이름이라 STM→cur import 부재)**를 **차단**. 이 required check가 green이어야 §0.3 firewall
선언이 능동 성립. **naming(§0.4a)은 약한 soft load-bearing**(firewall 배제 목록 `wdr:47`/`rlp:39`/`cur:51`/`sir:67`이
`tos.stm` 명명) — 미래 형제 stm은 allowlist가 자동 배제·미착지 sci도 동일.

### 7.2 회귀 스위트 (예정 — `tos/tests/stm/`)

`test_stm_coverage.py`(critical_coverage_complete_or_gap 노른자 1·∅ 양방향/all-false/집합 양방향/no-self-exemption/
item-level closure/Monitored-Assumption intake property + **§9 12-item anchor drift**[§9 line 275–286 == `CoverageItem`
closure])·`test_stm_determinism.py`(**노른자 2 핵심** — evaluation_is_deterministic 관계·같은 키·다른 result ⇒ False·
∅/singleton ⇒ True·bound_integrity_preserved·numeric_result_not_conforming_by_default + **§11 12-token numeric·
12-token bound anchor drift**[§11 line 316/314 == `NumericInputState`/`BoundSemanticKind`])·`test_stm_conformance_
result.py`(4-token aggregate·`is CONFORMING` 게이트·CONFORMING all-false + **§12 4-token drift**)·`test_stm_dashboard_
honesty.py`(7-token dashboard·no-green-default + **§23 7-token drift**[§23 line 499 == `DashboardStatusToken`])·
`test_stm_polarity.py`(극성 전수·§4.3·**`is not True` 음극성 부재 grep**·None ⇒ deny 수렴)·`test_stm_reconcile.py`
(그룹 reconcile 순서독립·no-favorable-union·MAX-generation·**두 ∅ 극성 구별**·§4.4)·`test_stm_truthy_sentinel.py`
(§4.2·**8 enum**)·`test_stm_void_canaries.py`(§4.1·실행 동사 부재·**cur `DimensionKey`/`vector_complete` 문자열 부재**)·
`test_stm_authority.py`(all-false·model_validator any-True⇒error)·`test_stm_malformed_model.py`(CONFORMING-claim +
incomplete-scope coexistence seal·model_construct 우회 2층·§2.3)·`test_stm_seam_siblings.py`(**forward seam 정합** —
STM이 cur MONITORING 차원 완전성 판정을 직접 저작·대입하지 않음을 확인[§3.6·§4.1 canary]·rlp `monitoring_not_
preventive`·sir "-028 handoff" 실 심볼 resolve로 drift-lock·FD §10.2 교훈)·`test_stm_predicate_only.py`(§6 substrate·
전부 closes-no-EV 태그)·`test_stm_import_closure.py`(§7.1).

**신규 회귀 3종(upgrade 조건·리뷰어 요구·SIR §7.2 상속·M6 (c) 추가)**:
- **(a) field-closure property(`test_stm_field_closure.py`)**: §4.3 극성 표·§5/§6 술어가 참조하는 **전 필드가 §2.4
  선언 모델에 실재**하고 그 극성이 표와 일치하며 **실제 소비 conjunct까지 존재**함을 기계 검증(양방향 — 표에 있으나
  모델에 없는 필드 0·모델 소비 필드가 표에 없음 0·**#28 MAJOR-1 교훈: 주입 verdict는 선언·등록만으로 부족·실제 소비
  conjunct까지 설계에 명시**). `coverage_score_present`·`permits_individual_exceedance`·`treated_as_healthy`·
  `disables_evidence`·`disables_generation_advancement`·`clears_local_latch`·`ack_implies_containment`·`defaulted_to_
  green`·`admitted_as_coverage_item`·`runtime_falsity_invalidates_property`·`source_continuity_present`·`closure_proof_
  present`·`unioned_or_substituted`·`satisfies_preventive_control` 신규 필드 실재 + 술어 소비 확인.
- **(b) anchor-resolution property(`test_stm_anchor_resolution.py`·M7 텍스트 일치 포함)**: 문서 전 `§N line M` /
  `INV-0NN` 인용의 **ADR 소속 섹션 일치 + 인용 라인 텍스트 일치를 기계 검증**(FD §10.2·#28 교훈 확장 — 존재 주장도
  잠금·**off-by-one 통과 봉인 = 라인 번호뿐 아니라 인용 텍스트가 그 라인에 실재함까지 대조**·M7 교훈). INV은 §6
  본문행(159·163·…·219), aggregate result는 §12:335, dashboard는 §23:499, numeric은 §11:316, bound는 §11:314+§6:183,
  currentness vector는 §18:410–417, failure matrix는 §21:451–462, coverage closure는 §9:275–286, OQ numeric은 §29:674로
  각 앵커가 실제 ADR 섹션·라인·텍스트에 소속함을 대조(misattribution·off-by-one 재발 방지).
- **(c) ADR-enumeration-closure property(`test_stm_adr_enumeration_closure.py`·M6 신규)**: 부록 A/K의 **전 ADR 열거
  앵커의 항목수·항목명 ↔ 모델 필드 집합을 양방향 기계 검증**((a) field-closure 내부 폐포·(b) 섹션 소속의 **사각
  축** — ADR 산문 열거가 모델에 1:1 폐포되는지). 예: §1:25 all-false 14-verb ↔ `AllFalseMonitoringAuthority` 14필드·
  §5.11:151 6금지 ↔ `MonitoringSuppression` 6 disable 필드·§17:402 4금지 ↔ `RestrictiveMonitoringSignal` 4필드·
  §13:347 11차원 ↔ `CoverageDimension` 11멤버·§11:316 12-numeric ↔ `NumericInputState`·§11:314+§6:183 6-weak ↔
  `BoundSemanticKind` WEAK 부분집합. ADR 열거 항목이 모델에서 누락되거나(不) 모델이 ADR에 없는 항목을 추가하면(過)
  fail(§부록 過/不 계수와 정합).

**property-based(hypothesis)** 중심(EV-L1 = model/property). **determinism property가 노른자 2 최우선**(같은 입력 ⇒
같은 판정·§5.2·task 명시)·**anchor drift property가 최우선**(§9 12-item·§11 12-token numeric·12-token bound·§12
4-token·§23 7-token이 손전사 anchor와 일치·cur/WDR §7.2 교훈). **양방향 canary**: 각 노른자에 대해 "모든 조건 충족 ⇒
True" 및 "각 조건 개별 위반 ⇒ False"를 property로 확인(단방향 seal 방지·both-ways·coverage explicit-empty 유효·
missing-obligation deny·determinism ∅=True 극성 구별 포함).

**mandated property test (L1 2행·§13 AC 표와 정합)**: STM-EV-001↔`test_stm_coverage.py`·STM-EV-005↔`test_stm_
determinism.py`가 각 AC(AC-001/005)의 L1-decidable 부분을 model/property로 검증하되 **어떤 STM-EV도 닫지 않는다**
(register status NOT_IMPLEMENTED 유지·§1·ADR §27 line 594 "Written cases … are not completed evidence").

---

## 8. 수치 → Phase-0 / INSTANCE (숫자 하드코딩 0)

STM 관련 numeric은 **전부 Profile INSTANCE 측정/승인·주입**(현재 전부 `null`/`TBD`·ADR §29 OQ 12 line 674·§30 gate
9·`VERIFICATION-PROFILE-002.yaml` INSTANCE):

| 키 (ADR §29 OQ 12·line 674) | 소유 | 상태 | 근거 |
|---|---|---|---|
| `B_safety_telemetry_loss_detect` | **STM** | MEASURE·null | §10 telemetry loss 탐지 지연(런타임·STM-EV-002) |
| `B_monitoring_gap_to_authority_restrict` | **STM** | MEASURE·null | §13 gap→restriction 지연(런타임·STM-EV-008) |
| `B_monitoring_gap_to_egress_deny` | **STM** | MEASURE·null | §18 gap→egress deny(런타임·STM-EV-009) |
| `B_critical_alert_delivery` | **STM** | MEASURE·null | §16 alert delivery 지연(런타임·STM-EV-007) |
| `B_alert_escalation` | **STM** | MEASURE·null | §16 escalation 지연(런타임·STM-EV-007) |
| `B_monitoring_generation_fence` | **STM** | MEASURE·null | §5.5/§12 Monitor Generation→predecessor 무능 증명 |
| `MAX_critical_telemetry_age_ms` | **STM** | APPROVE·null | §10 stale telemetry ⇒ deny(wall-clock secondary·+Security) |
| `MAX_continuous_conformance_snapshot_age_ms` | **STM** | APPROVE·null | §12/§18 stale snapshot ⇒ deny(wall-clock secondary) |
| `MAX_safety_alert_age_ms` | **STM** | APPROVE·null | §16 stale alert ⇒ deny(trustworthy time 주입) |
| `MAX_monitoring_suppression_duration_ms` | **STM** | APPROVE·null | §15 suppression expiry ⇒ restrictive |
| `MAX_alert_acknowledgement_age_ms` | **STM** | APPROVE·null | §16 stale ack ⇒ deny(wall-clock secondary) |

**주의**: worst-credible-effect *계산*(§19)은 rcl + +Broker(§30 gate 9)·STM는 envelope를 주입 opaque 좌표로 소비
(**edge 0**·SIR/WDR 선례). **L1 아티팩트는 전 numeric이 `null` 상태에서 구성 가능**해야 하며(§2.3 `_REQUIRED_COVERED`
numeric 제외), 누락 numeric claim은 fail-closed(§4.2). broker/vendor proper noun/KIS 특정값 부재(broker-agnostic·
§4 line 97 non-scope·정규 텍스트).

---

## 9. Phase-0 / not-Phase-1 체크리스트

### 9.1 Phase-1(EV-L1) 산출물 (본 계약이 실현 지침을 제공)
1. `tos.stm` 패키지(canonical/ordering만 의존·firewall green·**rcl edge 0**·sibling edge 0·cur 직접 배선 canary).
2. 모델: `SafetyMonitoringPolicy`·`CriticalTelemetryManifest`·`MonitorCoverageManifest`·`ContinuousConformanceSnapshot`·
   `SafetyMonitoringGap`·`SafetyAlertRecord`·`AlertEscalationRecord`(7 digest-bound) + value(`MonitorEvaluation`·
   `ApprovedBoundBinding`·`CoverageItem`·`MonitoredAssumptionIntake`·`CriticalTelemetryIdentity`·`TelemetrySemanticView`·
   `SilenceObservation`·`MonitoringUnknownState`·`CommonModeDisclosure`·`MonitoringSuppression`·`AlertStateVector`·
   `BrokerFinalityTokens`·`DashboardStatusView`·`MonitoringRecoveryInputs`·`RestrictiveMonitoringSignal`·
   `SendRaceOrdering`) + `AllFalseMonitoringAuthority`(14 필드) + **enum 8종**(`AggregateConformanceResult`[4]·
   `DashboardStatusToken`[7]·`MonitoringGapKind`[10]·`NumericInputState`[12]·`BoundSemanticKind`[**12**]·
   `TelemetryCriticality`[3]·`SuppressionLifecycleState`[4]·`CoverageDimension`[**11**·M2]) = **32 모델**.
3. 노른자 술어 2종(§5·coverage + determinism **4부 합성**[(0) presence+∅·(a) 관계 결정론·(b) bound-integrity·(c)
   fail-closed numeric]) + 지지(gap-restrictive·escalation-single-binding·conformance-complete) + predicate-only
   substrate 9종(§6.1–6.9) + 얇은 not-Phase-1 model(§6b).
4. malformed-model validator(CONFORMING-claim + incomplete-scope seal)·truthy 봉인·극성(음극성 `is False`만)·
   reconcile(no-favorable-union·두 ∅ 극성 구별)·all-false·canary(cur 직접 배선 금지 포함)·**anchor drift**(§9 12-item·
   §11 12-token numeric·12-token bound·§12 4-token·§23 7-token) + field-closure + anchor-resolution 회귀(§4·§7.2).

### 9.2 Phase-0 / 미착지 / +Security / 런타임 / 벤더 (닫지 않음 — 13 항목·ADR §30 gate 1–13 정합)
1. canonical policy/telemetry/coverage/snapshot/gap/alert-escalation schema **승인**(§30-1·거버넌스).
2. requirement/hazard/control registry + conservative coverage compiler 독립 리뷰(§30-2·런타임·+Security).
3. source continuity/semantic/unit/derivation/trustworthy-time/raw-retention/correction 구현·보안 리뷰(§30-3·+Security).
4. deterministic monitor evaluator + independent differential test가 omission/stale/parser-drift/numeric-failure/
   threshold-weakening 거부(§30-4·+Security·런타임 — 단 determinism *property*는 §5.2 L1).
5. Monitor Generation·owner fencing·invalidation·restrictive ingress·local latch·final-egress currentness(§30-5·
   egress 런타임·cache-free·STM-EV-009).
6. suppression/maintenance/test/correlation/dedup/backpressure/delivery/ack/escalation/handoff protocol fail-closed
   (§30-6·런타임·+Security).
7. monitoring/alert/dashboard/paging/ticket/evidence/replay identity가 live broker route·capacity/authority 미도달
   (§30-7·+Security·§22·§7).
8. ADR-002-025 EV-L6 + ADR-002-027 incident handoff가 exact current monitoring contract 사용·authority 무전이(§30-8·
   rlp/sir).
9. numeric bound + age/suppression limit 측정/승인(§8·§30-9·**INSTANCE·+Broker·+Security**).
10. STM-EV-001..012 required-level pass + 독립 review(§30-10·**전 EV**).
11. restart/failover/partition/common-mode/suppression/queue-overflow/notification-failure/compromise/stale-restore/
    send-race/recovery/non-revival fault injection(§30-11·L3·+Security).
12. Critical/Major finding 0(coverage/source-semantic/numeric/currentness/broker-route/suppression/escalation·§30-12).
13. Architecture Gate 명시 ADR acceptance(§30-13·거버넌스).

**추가 형제/미착지 이관**: cur MONITORING 차원 완전성 판정(cur·§3.5·§3.6)·Live Authorization 발급(liveauth·§7)·
Hard Safety Envelope 봉입(spg·§8)·worst-credible-effect 계산(rcl·+Broker·§19)·evidence custody/causal-chain(evidence·
§23)·Effective Principal independence(hag·§14)·**029/SCI release-attestation·compromise-signal 주입(SCI 착지 후·
untracked·§0.4f·언급만)**.

**cross-EV 의존(§30-10)**: STM-EV closure는 cur/spg/rlp/sir/egress/evidence/authority/liveauth/rcl/protective/time/
hag/wdr 및 -029가 required level에서 pass해야 성립 — Phase-1 범위 밖.

---

## 10. 명명 결정 + 리뷰어 공격 지점

### 10.1 운영자 판단 지점
- **패키지 명명 `tos.stm`**(§0.4a) — register-prefix 1:1·firewall 배제 목록이 이름 지명(wdr:47·rlp:39·cur:51·
  sir:67)·SIR/WDR과 동형 약한 soft load-bearing. runner-up `tos.telemetry`·`tos.monitoring` 기각(monitoring은 cur
  차원·wdr label과 이름 혼동 키움). naming load-bearing 아님(운영자 치환 가능·설계 #1 line 164).
- **STM = greenfield content owner·forward committed 소비 4-clade**(§0.4b·§3.6) — SIR(#28)과의 대비. STM은 inbound
  이연 0건이나 cur가 `DimensionKey.MONITORING`을 이미 보유하고 rlp/spg/sir이 STM 좌표를 익명 소비 중. **독립 리뷰어
  재검토 지점**(RLP 미러 구조를 STM에 잘못 적용하지 않았는지·forward seam이 inbound edge로 오인되지 않았는지·**cur
  MONITORING 차원 소유를 부정하지 않았는지 = #28 C1 재발 여부**).
- **INV 밀도 > L1 행 — predicate-only substrate 규모 절반 이상**(§0.4c·§6) — over-realization 최대 위험. 닫는
  STM-EV 0·§6 9종 substrate가 어떤 EV도 닫지 않음. **독립 리뷰어 재검토 지점**(§6 substrate가 L1으로 오주장되지
  않았는지·INV 16/16 매핑 정직성·§12).
- **두 L1 행 모두 +Security 잔여·청정 L1 행 0건**(§1 결정적 사실 2) — SIR(청정 L1 2행 보유)과 대비·STM은 001·005
  모두 `EV-L1/3+Security`. **독립 리뷰어 재검토 지점**(청정 L1 0건·+Security 10/12 정직 명기 여부).
- **rcl edge 0 판정**(§3.5·SIR/WDR 선례) — STM L1은 capacity 산술 미수행·worst-credible 주입 opaque·§19:429
  "preserves the worst credible economic effect in RCL capacity". **독립 리뷰어 재검토 지점**.

### 10.2 리뷰어 공격 지점 (선제 반론)
1. **"STM이 RLP처럼 피이연자여야"** — 반론: inbound 이연 실측 0건(§0.4b grep)·STM은 순수 greenfield 생산자·forward
   concept-seam(cur/rlp/spg/sir)은 익명 차원-이름/generation/토큰·`tos.stm` 타입 미참조·RLP 미러 오적용 회피.
2. **"STM이 cur의 MONITORING 차원 미소유를 전제해야(SIR INCIDENT 동형)"** — 반론(**#28 C1 정면**): cur는
   `DimensionKey.MONITORING`을 **이미 mandated floor로 보유**(`cur/vocabulary.py:144`·`:172` 실측)·STM은 그 차원의
   *값 생산자*·완전성 판정은 cur 소유(§3.5·§3.6). "cur 미소유" 주장 금지·§0.5 seal 1에 등재.
3. **"AggregateConformanceResult = ioc ConformanceResult 중복"** — 반론: ioc `ConformanceResult`(command conformance·
   CONFORMANT/NON_CONFORMANT/UNKNOWN·`vocabulary.py:40-72`)와 **멤버·명제 상이**(STM = continuous conformance
   monitoring·CONFORMING/RESTRICTED/NON_CONFORMING/UNKNOWN)·truthy-sentinel 패턴만 REUSE·name-collision seal(§0.5 seal 3).
4. **"STM aggregate result·coverage manifest = spg 토큰 중복"** — 반론: spg `SAFETY_MONITORING_POLICY`/`CRITICAL_
   TELEMETRY_MANIFEST`/`MONITOR_COVERAGE_MANIFEST`(`vocabulary.py:217-219`)는 governed-artifact-**kind 문자열 토큰**·
   STM은 그 아티팩트 *모델*을 저작·명제 상이(§0.5 seal 2).
5. **"미착지 029/SCI phantom 인용"** — 반론: ADR 원문만·SCI 코드 인용 0·untracked·주입 opaque generation/signal
   (§0.4f·§0.2)·SCI는 언급만.
6. **"rcl worst-credible을 위해 CapacityVector 필요"** — 반론: STM L1은 vector 비교 미수행·정량화 +Broker/rcl-owned·
   §19:429·edge 0이 ADR 정합(§3.5·SIR/WDR 선례).
7. **"model_construct로 malformed CONFORMING snapshot 통과"** — 반론: CONFORMING-claim + incomplete-scope validator +
   술어 2층(§2.3·§5.2 지지·SIR/egress QCC 동형·#20 상속).
8. **"cur/rlp forward seam이 inbound edge"** — 반론: 익명 차원-이름/`bool`/generation 주입·`tos.stm` 미참조·STM은
   개념·값 생산자·sibling edge 0·naming 약한 soft load-bearing(§3.6).
9. **"determinism ∅=True가 vacuous 통과(coverage ∅ deny와 모순)"** — 반론(**본 문서 특유 ∅ 규율**): 두 ∅ 는 극성이
   반대다 — coverage-completeness ∅(완전성)는 applicable 측 확인 후 deny-or-valid-empty, determinism-consistency ∅
   (관계)는 valid-True(충돌 부재 = 안전 property의 건전한 vacuous-True·presence 미주장)·§4.4·§5.2 docstring 명문화·
   both-ways.
10. **"deterministic evaluation을 L1 주장하나 evaluator 미실행"** — 반론: STM은 evaluator를 실행하지 않고(런타임·§0.2)
    determinism을 **evaluation 레코드 corpus의 일관성 관계**(같은 키·다른 result ⇒ False)로 표현·VER EV-L1
    "property-based testing, deterministic simulation" 정면·canonical determinism 위임(§5.2·§3.1). 실 evaluator
    differential은 +Security(§30 gate 4).
11. **"음극성 필드 `is not True` 사용"** — 반론: **task 규율 전 적용**(§4.3) — 음극성 allow는 `is False`만·`is not
    True` 부재를 grep 회귀로 강제·None ⇒ deny 수렴·#18/#22/#23/#25 재발 봉인.
12. **"over-realization: coverage compiler/evaluator 런타임/escalation을 L1 주장"** — 반론: 닫는 STM-EV 0·009/011
    not-Phase-1·§6c 순수 런타임/벤더 명시(§1·§9.2)·L1 2행 모두 +Security 잔여 정직 명기.
13. **"TAB-INV-006이 STM-INV 17번째(미조사·survey 619)"** — 반론(**survey line 619 해소**): TAB-INV-006은
    **ADR-DEV-011(part-3-development)의 자체 TAB-INV-001..007 시리즈**·STM-INV-001..016과 별개(ADR-DEV-011은 STM-INV
    미언급·grep 0)·교차점은 §9 manifest intake 1곳(Monitored Assumption을 coverage item으로 편입·STM-INV-002/AC-001
    소유·gate-status M-23 "no new EV·DEV count 97·Evidence Register 372 불변"). STM-INV = 정확히 16(§12).

### 10.3 Open Questions 처분 (리뷰어 제기 대비)
1. **INV 다중-EV 귀속(§12)**: INV은 EV와 1:1 제약이 없다 — 하나의 invariant가 여러 EV에 걸칠 수 있다(INV-003 semantics는
   EV-002 provenance와 EV-005 bound-units 양쪽·INV-016 stale-writer는 EV-009 currentness와 EV-011 fencing 양쪽). §12
   매핑의 다중-EV 표기는 정합(각주 명시).
2. **survey "not-Phase-1" vs 본 문서 "predicate-only" 세분(§1·§10.1)**: survey §4.4는 L1 슬라이스 유무만 이분(001·005
   ✔·나머지 ✗)했고 본 문서는 register 최소 레벨로 refinement(하한 L2 = predicate-only 8행·하한 L3 = not-Phase-1 2행).
   세분화 맵이지 survey 반박 아니다(각주 유지·survey line 317이 003을 "predicate-only"로 이미 표기·정합).
3. **determinism 관계 술어 시그니처**: corpus `tuple[MonitorEvaluation, ...]` 전 입력 수용(#21/#24 C1 동형 방지)·
   pairwise 전수(첫-pair 아님·§4.4 reconcile). 처분 완료.
4. **clock-free vs `MAX_*_age_ms`(§8)**: STM 술어는 clock-free이고 `MAX_*_age_ms`는 **주입-age**(STM이 계산하지 않고
   time/egress 런타임이 계산해 주입하는 wall-clock age)다 — 구현 판정은 §9.2 이관(secondary +Security/INSTANCE).
   처분: 주입-age 명시.

---

## 11. 선제 defect-class 봉합 (전 시리즈 교훈)

| defect class | 출처 | STM 봉합 |
|---|---|---|
| **노른자 극성 자기위반(음극성 clear에 `is not True`)** | **v1.0 C1(자기위반)** | **conjunct 3 필터 `excluded is False`·conjunct 4 게이트 `excluded is not False`(§5.1·§4.4·C1)·`excluded=None` 두 conjunct 각각 mandated 픽스처·§4.3 규율의 자기위반이 노른자에 재발했던 사례를 grep 회귀로 봉인** |
| **합성 노른자 전면-∅ 공허 True(presence 부재)** | **v1.0 C2** | **§5.2 (0) presence+∅ 게이트 신설(`required_evaluation_keys`·`applicable_bound_refs`)·required≠∅ ∧ corpus=() ⇒ deny·(a) 관계 술어 단독 ∅=True 유지·STM-INV-004:171 자기-노른자 위반 봉인** |
| **weak-kind denylist 누수(신규 멤버 샘)** | **#25 RLP MAJOR-1·v1.0 M3** | **`bound_integrity_preserved` denylist→whitelist 반전(hard⇒hard 정확 보존·미지/신규 멤버 자동 deny)·`BoundSemanticKind` 9→12(INV-007:183 3 weak-form 편입·§5.2·§2.2)** |
| grep head 절단 카운트 오류 | #12 | register 전수 파싱(csv line 329–340 직접·§1·naive grep 금지) |
| RLP 미러 오적용(피이연 가정) | #26 WDR·#28 SIR | inbound 이연 실측 0건 명기·STM=greenfield 생산자·forward concept-seam은 익명 좌표 4-clade(§0.4b·§3.6·§10.2-①/⑧) |
| **cur 차원 미소유 오주장(narrow-grep C1)** | **#28 SIR C1** | **cur `DimensionKey.MONITORING` mandated floor 보유 실측(`:144`/`:172`)·STM=값 생산자·완전성 cur 소유·광역 `-i` 패턴 재실측·§0.4b-2·§0.5 seal 1·§3.5·§3.6·§10.2-②** |
| **anti-phantom (부재/존재/광역 grep)** | **#27 FD·#28 C1** | 부재 negative-grep(`class .*Telemetry`/`MonitorCoverage`/`ContinuousConformance`/`AlertEscalation` 빈 결과·유일 hit spg kind-토큰)·존재 file:line·**동명이축/동명유사 seal 4건**(cur DimensionKey·spg 토큰·ioc ConformanceResult·wdr/brokercap MONITORING)·anchor-resolution property(§7.2·§0.5·§3.5) |
| truthy-sentinel fail-open | #13·#14 M1 | `_NonTruthyStrEnum` 7종 처음부터·`__bool__ ⇒ TypeError`·**`if snapshot.aggregate_result:` 1순위 방어**(§2.2·§4.2·ioc 선례) |
| ∅ 단방향 seal / 과잉 봉합 | #8·#15·#26 MAJOR-1 | **coverage explicit-empty 유효(applicable 측 확인 선행)·determinism ∅=True — 두 ∅ 극성 반대 구별이 본 문서 핵심**(§4.4·§5.1·§5.2·§10.2-⑨) |
| 집합 단방향 | #10 | applicable ⊆ coverage 양방향·dependency-closure ⊇ dimensions 양방향(§5.1) |
| enum 전수 매핑 누락 | #21 NT C1 | 4-token result·7-token dashboard·10-token gap·12-token numeric·12-token bound·3-token criticality·4-token suppression·**11-token CoverageDimension**(M2) 전수(§2.2·§부록) |
| disposition/관계 시그니처 부분 수용 | #21 NT·#24 PTF C1 | coverage 술어가 4-입력 전수·determinism 관계가 corpus 전 pair·bound_integrity 전 bound(§5.1·§5.2·§10.3-3) |
| malformed-model model_construct 우회 | #20 | CONFORMING-claim + incomplete-scope validator + 술어 2층(§2.3·§5.2) |
| 미표현 요소 vacuous pass | #20·#23·cur CONTEXT | 미표현 dependency-closure 차원·미매핑 applicable obligation ⇒ incomplete deny(§5.1) |
| phantom id/코드 인용 | #17·#20·#23·#27 | 인용 전 grep·미착지 029/SCI 코드 0(§0.4f)·seam은 실측 코드 line·존재 주장도 실측(§0.5) |
| **극성 fail-open(unknown/disable/expiry None)** | **#18·#22 MAJOR-2** | **극성 전수 표 + 음극성 `is False`만·`is not True` 금지·None ⇒ deny 수렴(§4.3)** |
| **그룹 첫-entry/favorable-union 판정** | **#22 MAJOR-1** | **coverage 전-entry 보수·no-favorable-union·item-level closure·MAX-generation(§4.4·§5.1)** |
| **INV 역전(expiry 직접 소비)** | **#26 WDR v1.2** | `economic_effect_outlives_monitor_state`가 all-false authority-shape 소비·expiry 직접 clear 금지(§6.8) |
| **ordering 3치 접기(증명불가=부정확정)** | **#28 MAJOR-2** | send-race 3치(증명deny/증명safe/증명불가-potentially-live) 미접기·`AggregateConformanceResult` CONFORMING≠UNKNOWN≠NON_CONFORMING(§4.3·§6b) |
| **보수 분기 지배(픽스처 은폐)** | **#28 MAJOR-3** | `absence_is_not_health` 정직-침묵/fail-open-시도 픽스처 각각 명시·지배 분기 없음(§6.2·§7.2) |
| **carrier 모델 §2.4 미선언** | **#28 E3** | 술어 시그니처 담지 모델 16종 value + 7 digest-bound 전부 §2.4 field skeleton 선언(§2.4) |
| enum-drift 참조집합 부정직 | #14 anchor·cur v1.1 | manually-transcribed anchor 명시(§9 12-item·§11 12-token·§12 4-token·§23 7-token·§7.2 drift·§부록) |
| seam 재저작(거버넌스 내용 중복) | #19·#22·#23·#25·#26·#28 | cur/spg/rlp/sir/egress/evidence/authority/liveauth/rcl/protective/time/hag/wdr/iap 소유 실측·주입 소비(§3.5·§10.2) |
| rcl edge 과잉(불필요 import) | #26 WDR·#28 SIR | STM L1 capacity 산술 미수행·edge 0·§19:429(§3.5·§10.2-⑥) |
| **over-realization(INV 밀도 > L1 행)** | **본 문서 특유·survey line 521** | **§6 predicate-only substrate 9종이 어떤 STM-EV도 닫지 않음·닫는 STM-EV 0·L1 2행 모두 +Security 잔여 명기(§0.4c·§1·§12)** |
| **TAB-INV-006 미조사(survey 619)** | **survey §4.4 line 619** | **ADR-DEV-011 자체 TAB-INV-001..007 시리즈·STM-INV와 별개·§9 intake 1곳 교차·EV 불변(§0 각주·§10.2-⑬·§12 계수)** |
| 과대 주장(authoring=acceptance) | 전 시리즈 | 닫는 STM-EV 0·"EV-L1-complete 주장 금지"(§1) |

---

## 12. STM-INV 16/16 전수 매핑 (Phase-1 제공 vs 명시 이연·task 요구)

**계수: 정확히 16종(STM-INV-001~016·ADR line 156–219·결번 없음). 過(초과) 0·不(누락) 0.** 각 INV에 대해 Phase-1이
제공하는 것(모델/predicate/property) vs 명시 이연(어느 EV 레벨/owner로).

| INV | 제목(ADR line) | Phase-1 L1 제공 | 명시 이연 (레벨/owner) |
|---|---|---|---|
| **001** (159) | Monitoring Artifacts Are Not Authority | `AllFalseMonitoringAuthority`(§2.4) + `critical_coverage_complete_or_gap` conjunct 2(§5.1) | — (L1 완전 판정·닫는 건 STM-EV-001 `/3`+Security) |
| **002** (163) | Coverage Is Complete and Exact | `critical_coverage_complete_or_gap`(§5.1·노른자 1·Monitored-Assumption intake 포함) | 실 coverage compiler·registry·+Security(§6c·§30-2) |
| **003** (167) | Telemetry Semantics Are Exact | `telemetry_semantics_exact`(§6.1) + 노른자 2 bound-units 정합(§5.2) | **STM-EV-002 `EV-L2/3+Security`**(source-continuity 런타임) |
| **004** (171) | Absence Is Not Health | `absence_is_not_health`(§6.2·보수 분기 명시) + coverage missing⇒gap(§5.1) | **STM-EV-003 `EV-L2/3`**(런타임 silence 판정) |
| **005** (175) | UNKNOWN Is Restrictive | `unknown_is_restrictive`(§6.3·음극성 전수·predicate-only) | **STM-EV-003 `EV-L2/3`**(런타임 UNKNOWN 확장) |
| **006** (179) | Common Mode Is Not Independence | `common_mode_is_not_independence`(§6.4·predicate-only) | **STM-EV-004 `EV-L2/3+Security`**(effective-control·hag·+Security) |
| **007** (183) | Approved Bound Semantics Are Preserved | **L1 제공**: `deterministic_evaluation_bound_integrity`(§5.2·노른자 2·**bound-kind whitelist**[M3·hard⇒hard 정확 보존]·**determinism 관계**[같은 키 다른 result⇒False]·fail-closed numeric[non-well-formed⇒never CONFORMING]) | **+Security 이연(M3 분리)**: evaluator differential·parser drift·threshold weakening 실 거부는 §30 gate 4·런타임. 닫는 건 STM-EV-005 `/3`+Security |
| **008** (187) | Suppression Cannot Suppress Safety | `suppression_cannot_suppress_safety`(§6.5·predicate-only) | **STM-EV-006 `EV-L2/3+Security`**(승인·expiry 런타임·+Security) |
| **009** (191) | Alert State Is Orthogonal | `alert_state_is_orthogonal`(§6.6·predicate-only) | **STM-EV-007 `EV-L2/3+Security`**(delivery/escalation·+Security) |
| **010** (195) | Loss and Backpressure Preserve Negative Facts | `loss_preserves_negative_facts`(§6.6·predicate-only) | **STM-EV-007 `EV-L2/3+Security`**(backpressure 런타임·+Security) |
| **011** (199) | Authority Ownership Remains Separate | `handoff_is_non_authorizing`(§6.7·all-false·sir forward seam·predicate-only) | **STM-EV-008 `EV-L2/3+Security`**(restrictive ingress·sir·+Security) |
| **012** (203) | Current Monitor Generation Is a Negative Gate | 얇은 send-race permutation model(§6b·3치) | **STM-EV-009 `EV-L3+Security`**(cache-free currentness·egress 런타임) |
| **013** (207) | Broker Finality and Economic Continuity Do Not Change | `broker_finality_unchanged`·`economic_effect_outlives_monitor_state`(§6.8·authority-shape·predicate-only) | **STM-EV-010 `EV-L2/3+Broker`**(broker-finality 정량화·rcl·+Broker) |
| **014** (211) | Evidence Is Not Prevention | **L1 제공(M6 정직화)**: `evidence_and_status_honest`(§6.9)는 **dashboard-honesty 부분**(7-token no-green-default)·**evidence≠prevention shape**는 `AllFalseMonitoringAuthority.satisfies_preventive_control=False`(§2.4·M6 신규 필드)가 제공(metrics/logs/replay가 preventive control 대체 불가) | **STM-EV-012 `EV-L2/3+Security`**(evidence custody·+Security) |
| **015** (215) | Monitoring Recovery Does Not Revive | `recovery_revives_nothing`(§6.9·음극성 전수·predicate-only) | **STM-EV-012 `EV-L2/3+Security`**(Recovery Barrier·sbr·+Security) |
| **016** (219) | Stale Writers and Consumers Are Fenced | `stale_writer_fenced` 얇은 generation-fence(§6b·`compare_order` 봉인) | **STM-EV-011 `EV-L3+Security`**(compromise expansion·partition·failuredomain·+Security) |

**요지(계수 정합·5+11=16)**: 16 INV 중 **L1 노른자가 직접 닫는 데 기여 = 정확히 5건(001·002·003·004·007)**; 나머지
**정확히 11건(005·006·008·009·010·011·012·013·014·015·016)은 §6 predicate-only substrate/얇은 model로 저작하되
어떤 STM-EV도 닫지 않는다**(5+11=16·§0.4c "닫지 않는 predicate substrate 비중이 절반 이상"·survey §4.4 line 521 경고
정합·§14 self-check 정합). **주의(다중-EV·§10.3-1)**: INV-003은 EV-002/005 양쪽·INV-016은 EV-009/011 양쪽에 걸치나
*직접 닫기 기여*는 위 표 대표 EV로 계상.

---

## 13. STM-AC 12/12 ↔ STM-EV 1:1 표 + L1 2행 mandated property test (task 요구)

**계수: 정확히 12종(STM-AC-001~012·ADR line 596–642). 1:1 근거(ADR "map one-to-one" 문장 부재·제목-일치 기반)**:
ADR §27은 SIR/PTF류의 명시 "map one-to-one" 문장이 **없다**(실측). 근거는 **AC 제목 12/12 == EV 제목 12/12 일치**
(csv register title == §27 AC 소절 title·ARCHITECTURE-GATE-STATUS.md line 797 "STM acceptance/evidence titles now
match exactly"·commit `c442dd82`). ⇒ AC-00N ↔ EV-00N은 제목-일치 1:1.

| STM-AC (ADR line) | ↔ STM-EV | register 최소 레벨 | Phase-1 분류 | mandated property test (L1 2행만) |
|---|---|---|---|---|
| **AC-001** Complete Critical Coverage (596) | EV-001 | `EV-L1/3+Security` | **core L1** | `test_stm_coverage.py`(§5.1·§7.2 — ∅ 양방향/all-false/집합 양방향/no-self-exemption/item-closure/Monitored-Assumption + §9 12-item drift) |
| **AC-002** Provenance, Continuity, Semantics, and Time (600) | EV-002 | `EV-L2/3+Security` | predicate-only | (닫지 않음·§6.1 substrate) |
| **AC-003** UNKNOWN, Silence, and Stale Green State (604) | EV-003 | `EV-L2/3` | predicate-only | (닫지 않음·§6.2/§6.3) |
| **AC-004** Effective Independence and Common Mode (608) | EV-004 | `EV-L2/3+Security` | predicate-only | (닫지 않음·§6.4) |
| **AC-005** Deterministic Evaluation and Bound Integrity (612) | EV-005 | `EV-L1/3+Security` | **core L1** | `test_stm_determinism.py`(§5.2·§7.2 — **determinism 관계**/bound-integrity/fail-closed-numeric + §11 12-token numeric·12-token bound drift) |
| **AC-006** Suppression and Maintenance Safety (616) | EV-006 | `EV-L2/3+Security` | predicate-only | (닫지 않음·§6.5) |
| **AC-007** Alert Correlation, Delivery, and Escalation (620) | EV-007 | `EV-L2/3+Security` | predicate-only | (닫지 않음·§6.6) |
| **AC-008** Restrictive and Incident Handoff (624) | EV-008 | `EV-L2/3+Security` | predicate-only | (닫지 않음·§6.7·sir forward seam) |
| **AC-009** Active Currentness and Send Race (628) | EV-009 | `EV-L3+Security` | not-Phase-1 | (닫지 않음·§6b send-race 3치) |
| **AC-010** UNKNOWN, Broker Finality, and Economic Continuity (632) | EV-010 | `EV-L2/3+Broker` | predicate-only | (닫지 않음·§6.8) |
| **AC-011** Compromise, Fencing, and Failure Domains (636) | EV-011 | `EV-L3+Security` | not-Phase-1 | (닫지 않음·§6b compromise) |
| **AC-012** Evidence, Recovery, and Non-Revival (640) | EV-012 | `EV-L2/3+Security` | predicate-only | (닫지 않음·§6.9) |

**mandated property test 총계(L1 2행)**: 2종 핵심(`test_stm_coverage`·`test_stm_determinism`) + 지지 회귀 13종(§7.2).
**닫는 STM-EV = 0**(전 mandated test가 L1-decidable 부분만 검증·register status NOT_IMPLEMENTED 유지·ADR §27 line
594 "Written cases define obligations only. They are not completed evidence").

---

## 14. Self-Check (task 요구·독립 비평 리뷰 전 자가 확인)

**v1.1 개정 검증(REVISE 전건 반영·실측 재작성)**:
- [x] **C1 노른자 1 극성 자기위반 교정**: §5.1 conjunct 3 필터 `item.excluded is False`·conjunct 4 게이트
  `item.excluded is not False`(§4.4·§2.4 CoverageItem·§4.3 표 정합)·`excluded=None` 두 conjunct 각각 mandated 픽스처
  (§4.3 전수 회귀·§7.2). INV-002:163 "Missing or **unknown** coverage is a gap" 정면 준수.
- [x] **C2 노른자 2 전면-∅ 공허 True 봉인**: §5.2 (0) presence+∅ 게이트 신설(`required_evaluation_keys`·`applicable_
  bound_refs`)·required≠∅ ∧ corpus=() ⇒ deny·(a) 관계 술어 단독 ∅=True 유지·STM-INV-004:171 자기-노른자 위반 봉인·
  "빈 corpus + non-empty required ⇒ False" mandated 픽스처.
- [x] **M1 digest-bound 3종 skeleton + 소비 conjunct**(§2.4·§4.3 표·§7.2 (a)); **M2 CoverageDimension 8번째 어휘**
  (§2.2·anchor §12:327/§13:347·"§9 차원" phantom 삭제·§부록 L·enum 8·모델 32); **M3 whitelist 반전 + BoundSemanticKind
  12**(§5.2·§2.2·§부록 C); **M4 bound_binding_digest subset**(§2.4·§5.2 (0)); **M5 극성 표 폐포 + 파라미터 개명 +
  conjunct 7 3층**(§4.3·§5.1); **M6 열거 폐포 3건(all-false 14·suppression 6·signal 4) + 회귀 (c)**(§2.4·§7.2·§부록
  K); **M7 INV 본문행 16건 + §5.11:151 + §29 OQ + §18:408 실문장 + anchor 텍스트 일치**(전수·§7.2 (b)).
- [x] **MINOR/OQ**: MINOR-2 무조건(§6.2)·MINOR-3 포함-only(§5.1 conjunct 6)·MINOR-8 name-similarity 5후보(§0.5)·
  MINOR-9 패키지 31(§0.4a)·OQ1 표지 처분(§2.4 Silence 이연/Recovery 구조 파생·§4.3 표지 목록)·OQ2 §14:355 anchor(§부록)·
  OQ3 capability-claim 3점(§2.4 SendRaceOrdering).

- [x] **§0.5 anti-phantom 준수(광역 `-i` 패턴·#28 C1 정면 처리)**: 존재 file:line(`cur/vocabulary.py:144`/`:172`·
  `spg/vocabulary.py:217-219`·`rlp/predicates.py:774-780`·`sir/predicates.py:15`·`sir/state.py:46`·firewall `tos.stm`
  4곳·ioc `ConformanceResult`·iap `:176`)·부재 negative-grep(`class .*Telemetry`/`MonitorCoverage`/`Continuous
  Conformance`/`MonitoringGap`/`AlertEscalation` ⇒ 유일 hit spg kind-토큰)·**동명이축/동명유사 seal 4건**(cur
  DimensionKey.MONITORING·spg 토큰·ioc ConformanceResult·wdr/brokercap MONITORING). anchor-resolution property(§7.2)로
  인용 재고정. **미착지 029/SCI 코드 인용 0**(§0.4f·untracked·언급만).
- [x] **#28 C1 재발 방지(cur MONITORING 차원)**: cur가 `DimensionKey.MONITORING`을 **실제 보유**(mandated floor·
  `:144`/`:172`)함을 §0.4b-2·§3.5·§3.6·§0.5 seal 1에 등재·"cur 미소유" 주장 부재. STM = 값 생산자·완전성 cur 소유·
  직접 배선 금지 canary(§4.1).
- [x] **극성 표 폐포(§4.3)**: 양극성·음극성 전 필드 등재·음극성 clear `is False`만·`is not True` 부재 grep 강제·
  3치 접기(send-race·aggregate result). field-closure property(§7.2 (a))로 표↔모델 실재 + **소비 conjunct 존재**
  양방향 검증(#28 MAJOR-1 교훈).
- [x] **∅ 양방향(본 문서 특유 = 두 ∅ 극성 반대)**: coverage-completeness ∅(applicable 측 확인 후 deny-or-valid-
  empty)와 determinism-consistency ∅(valid-True·presence 미주장)의 극성 구별을 §4.4·§5.1·§5.2·§10.2-⑨에 명문화·
  both-ways 회귀.
- [x] **enum 전수·carrier §2.4 선언(M1 허위 체크박스 실측 정정)**: **8 enum**(4/7/10/12/**12**/3/4/**11** 토큰·
  CoverageDimension 추가·M2) 전수·16 value + **7 digest-bound carrier 전부 §2.4 field skeleton 선언**(**v1.0은
  `SafetyMonitoringGap`·`SafetyAlertRecord`·`AlertEscalationRecord` 3종 skeleton 누락 상태에서 "7종 전부" 허위 체크 —
  M1으로 3종 신설·소비 conjunct 부여·`MonitoringGapKind` 고아·`bound_alert_id` phantom 해소**·#28 E3 교훈).
- [x] **INV 16/16 매핑(§12)**: STM-INV-001~016 전수·過 0·不 0. **L1 기여 정확히 5건(001·002·003·004·007) +
  predicate-only 11건**(005·006·008~016) = 16(§0.4c·§12·§14 정합).
- [x] **AC 12/12 ↔ EV 1:1(§13)**: 제목-일치 기반(ADR "map one-to-one" 문장 부재 명기·gate-status:797). L1 2행
  (001·005)만 mandated property test·나머지 10행 닫지 않음.
- [x] **닫는 STM-EV = 0·EV-L1-complete 주장 금지(§1)**: L1 2행(001·005) 모두 `EV-L1/3+Security`·청정 L1 0건·
  +Security 10/12·+Broker 1/12(010)·무태그 1/12(003)·전 12행 NOT_IMPLEMENTED. 규율 태그 전 §5/§6 부착.
- [x] **greenfield·sibling edge 0·forward 4-clade·rcl edge 0·PROMOTE 0(§0.4b·§3)**: inbound 이연 0·forward 소비
  익명 좌표 4-clade(cur/rlp/spg/sir)·canonical/ordering만 REUSE.
- [x] **TAB-INV-006 해소(survey 619)**: ADR-DEV-011 자체 TAB-INV-001..007 시리즈·STM-INV와 별개·§9 intake 1곳 교차·
  EV 불변(§0 각주·§5.1 conjunct 7·§10.2-⑬·§11).
- [x] **broker-agnostic·clock-free·수치 하드코딩 0**: vendor/KIS 고유명사 부재(§4:97 non-scope)·Monitor Generation
  ordering identity·`MAX_*_age_ms` 주입-age·11 numeric 전부 Phase-0(§8).
- [x] **결정론 property 핵심 반영(task 명시)**: 노른자 2가 동일 (evaluator_digest, input_digest) ⇒ 동일 result 관계·
  canonical determinism 위임·VER EV-L1 "property-based testing, deterministic simulation" 정면(§5.2).
- [x] **STM = 순수 무결성 판정·수집기/모니터 아님(§0.2)**: collect/scrape/emit/deliver/escalate 실행 canary·telemetry
  수집·전송 미구현·"Stale Green State"류 주입 age/generation(§4.1·§6b·§8).

---

## 부록 A — ADR verbatim 앵커 전사 (manually-transcribed·§7.2 drift property 대상·過/不 양방향 계수)

> 각 앵커는 **부록 verbatim ↔ §5/§6 operative list ↔ enum/model 3자 일치**를 property test로 강제(cur/WDR §7.2 교훈).

**(A) §12 line 335 aggregate result 4-token(`AggregateConformanceResult`)**: "`CONFORMING`, `RESTRICTED`, `NON_
CONFORMING`, and `UNKNOWN`." — **계수 4**(過 0·不 0). `CONFORMING` requires every required item current+complete+
independently-valid.

**(B) §11 line 316 numeric malformed 11-state + WELL_FORMED(`NumericInputState` 12-token)**: "Unknown numeric input,
NaN, infinity, overflow, underflow, non-convergence, unit mismatch, parser differential, missing sample, insufficient
history, or evaluator disagreement" — **계수 11 malformed + WELL_FORMED = 12**(過 0·不 0). 전부 ⇒ never CONFORMING.

**(C) §11 line 314 + STM-INV-007 line 183 bound-kind(`BoundSemanticKind` 12-token·M3)**: §11:314 "cannot be
implemented as a **percentile, average, best-effort target**, or window that permits an individual exceedance" +
INV-007:183 "cannot be replaced by a percentile, average, **local threshold, hidden grace period, or favorable
sampling rule**." — **WEAK = {PERCENTILE·AVERAGE·BEST_EFFORT_TARGET·LOCAL_THRESHOLD·HIDDEN_GRACE_PERIOD·FAVORABLE_
SAMPLING_RULE} 계수 6** + **HARD = {HARD_MAXIMUM·HARD_MINIMUM·EXACT_MATCH·MONOTONIC_SEQUENCE} 4** + **NEUTRAL =
{RANGE·RATE} 2** = **총 12**(過 0·不 0). whitelist: approved ∈ HARD ⇒ implemented ∈ HARD ∧ == approved(§5.2 M3).

**(D) §23 line 499 dashboard 7-token(`DashboardStatusToken`)**: "`CURRENT_CONFORMING`, `RESTRICTED`, `NON_CONFORMING`,
`UNKNOWN`, `STALE`, `GAP`, and `UNVERIFIED`." — **계수 7**(過 0·不 0). Rendering failures/unknown ⇒ never green.

**(E) §5.7 line 135 gap 10-kind(`MonitoringGapKind`)**: "missing, stale, conflicting, ambiguous,
discontinuous, incomplete, unverified, common-mode, failed, or suppressed." — **계수 10**(過 0·不 0).

**(F) §9 line 275–286 Monitor Coverage Manifest 12-item closure(`CoverageItem` closure)**: (1) exact requirement/
hazard/invariant/gate/bound/obligation·(2) scope+dependency closure·(3) preventive/restrictive owner·(4) telemetry+
source continuity·(5) deterministic evaluator+states·(6) trigger/bound/start/stop/uncertainty·(7) restrictive action+
containment owner·(8) alert delivery+escalation·(9) evidence+independent-review·(10) failure-domain+common-mode·(11)
final-egress/recovery currentness·(12) approved exclusions with proof. — **계수 12**(過 0·不 0).

**(G) §18 line 410–417 final-egress currentness vector 8-fact**: (1) Safety Monitoring Policy identity/generation/
digest·(2) Critical Telemetry + Monitor Coverage Manifest digests·(3) Monitor Generation + fenced owner epoch·(4)
action-scope coverage completeness·(5) conformance result + absence of unresolved gaps·(6) suppression state + no-
disable proof·(7) restrictive signal/fence/incident/trial-abort generations·(8) Snapshot age/trustworthy-time/
invalidation. — **계수 8**(過 0·不 0·not-Phase-1 §6b 담지).

**(H) §15 line 367–376 suppression preserved-active 8-function**: telemetry collection+continuity·monitor evaluation+
violation state·Monitoring Gap creation·restrictive signaling+local deny latching·incident-signal handoff·evidence
capture+audit·escalation on suppression failure/expiry·final-egress currentness+denial. — **계수 8**(過 0·不 0).

**(I) §21 line 451–462 partition/failure matrix 12-row**: telemetry-loss·collector-unavailable·owner/generation-
conflict·partition-while-egress-reachable·queue-overflow·delivery/escalation-unproven·common-mode-fail·suppression-
missing/stale/expired·time-confidence-lost·evidence-path-unavailable·dashboard/paging-compromised·recovery/backlog-
drain-completes. — **계수 12**(過 0·不 0·§6b 담지).

**(J) §8 line 253–265 Critical Telemetry Manifest binding**: ADR-002-029 release-lineage·ADR-002-030 post-trade·
canonical identity·owner/publisher epoch·environments/cells/domains/accounts/brokers/venues/instruments/strategies·
value-type/units/scale/sign/cardinality/states/missing-semantics·source-identity/continuity/sequence/schema/lineage·
trustworthy-time/event-time/observation-time/receipt/age/skew/uncertainty·cadence/completeness/aggregation/sampling/
loss·derivation/invariant-evaluator digests·dependency-closure/consumers/restrictive-response/evidence-class·failure-
domains/common-modes/access/retention/security. — binding 필드군(§2.4 `CriticalTelemetryIdentity` 담지).
**計數 12**(過 0·不 0 — §8:253–265는 253·254 포함 연속 **12불릿**·255는 렌더링 공백행일 뿐 열거 분절 아님;
코드 리뷰 검증 (c)에서 확정·구현 drift-lock이 live ADR 재파싱으로 12를 잠금. 이 항목만 計數 선언이 누락되어
있던 것을 리뷰 NIT-2로 보정).

**(K) §1 line 25 all-false authority 12-verb + 2(`AllFalseMonitoringAuthority` 14-field·M6)**: §1:25 CONFORMING "does
not approve an action(1), create headroom(2), mark an RFC requirement `PASS`(3), **satisfy preventive control(4)**,
establish broker finality(5), activate configuration(6), issue authority(7), permit transmission(8), close an
incident(9), establish recovery readiness(10), restore scope(11), or re-arm(12)." (**12 verbs**) + `creates_capacity`
(INV-001) + `classifies_protective`(§7 line 236) = **14 필드**(過 0·不 0·§2.4·**v1.0은 `satisfies_preventive_control`
누락으로 13 오계수 — M6 복원**).

**(L) §12 line 327 + §13 line 347 coverage/dependency-closure 11-dimension(`CoverageDimension`·M2 신규)**: §13:347
verbatim "the scope expands across shared **accounts, Capacity Domains, Safety Cells, broker sessions, credentials,
routes, datastores, clocks, deployments, policies, or failure domains**" — **계수 11**(ACCOUNT·CAPACITY_DOMAIN·
SAFETY_CELL·BROKER_SESSION·CREDENTIAL·ROUTE·DATASTORE·CLOCK·DEPLOYMENT·POLICY·FAILURE_DOMAIN·過 0·不 0). §12:327
"exact scope and dependency closure"가 차원 축 근거. **v1.0 "§9 차원" phantom 삭제**(§9는 차원 열거 부재·실측).

**(M) §14 line 355 shared-dependency 17-item closed anchor(`CommonModeDisclosure.shared_dependencies`·OQ2)**: §14:355
verbatim "Shared **source, collector, exporter, parser, schema registry, library, time source, message bus, datastore,
network, region, credential, administrator, CI pipeline, deployment, notification provider, or policy owner**" —
**계수 17**(過 0·不 0). 필드는 **open `frozenset[str]` 유지 정당**(§14 "remaining common mode is recorded as residual
risk"·disclosed common mode는 개방 열거 독법·OQ2)·anchor는 정직성용 closed 목록.

**계수 검증(過/不 양방향)**: 위 앵커 계수(A=4·B=12·C=12·D=7·E=10·F=12·G=8·H=8·I=12·**J=12**·K=14·L=11·M=17)가 §2.2 enum·
§2.4 model·§5/§6 술어와 **양방향 일치**(anchor에 있으나 enum/model에 없음 0·enum/model에 있으나 anchor에 없음 0).
§7.2 (a) field-closure + (b) anchor-drift + **(c) ADR-enumeration-closure**(M6 신규)가 구현 단계에서 이를 기계 강제한다.

## 부록 B — 규모 요약

- **모델**: 7 digest-bound(`IndependentIdArtifact`) + 16 value + 1 all-false(14 필드) + **8 enum**(`_NonTruthyStrEnum`·
  CoverageDimension 포함·M2) = **32 모델**.
- **술어**: 노른자 2(§5.1 coverage·§5.2 determinism **4부 합성** = (0) presence+∅ + evaluation_is_deterministic +
  bound_integrity_preserved + numeric_result_not_conforming_by_default) + 지지 3(conformance_requires_complete_current_
  valid·gap_is_restrictive_not_exemption·escalation_single_binding) + predicate-only substrate 9종(§6.1–6.9) +
  not-Phase-1 얇은 model 2(§6b send-race·stale-writer) ≈ **19 술어**.
- **회귀 스위트**: **16종**(coverage·determinism·conformance-result·dashboard-honesty·polarity·reconcile·truthy-
  sentinel·void-canaries·authority·malformed-model·seam-siblings·predicate-only·import-closure + field-closure·
  anchor-resolution·**adr-enumeration-closure**[M6]).
- **EV**: core 2(001·005) / predicate-only 8(002·003·004·006·007·008·010·012) / not-Phase-1 2(009·011) = 12·**닫는
  STM-EV 0**.
- **INV**: 16(L1 기여 5 + predicate-only 11). **AC**: 12(제목-일치 1:1). **edge**: sibling 0·rcl 0·forward committed
  소비 4-clade(cur/rlp/spg/sir·전부 익명 좌표).
- **naming**: `tos.stm`(약한 soft load-bearing·firewall 배제 4곳). **REUSE**: canonical·ordering(PROMOTE 0).
- **수치**: 하드코딩 0(11 키 전부 Phase-0/INSTANCE·§8).

---

*End of design #30 (STM, ADR-002-028, EV-L1, v1.1).*
