# D2 — P0-1 Bounds Approval Draft Package (candidate proposal) (2026-07-29)

> ## ⚠ 부분 승인됨 (2026-07-29) — 본 문서는 더 이상 순수 제안서가 아니다
>
> 운영자(Bounds-Approver 자격)가 **2026-07-29**에 §5/§6 제안 134키(범위 키는 권고값)와 §9 재확인 12키,
> 합 **146키를 일괄 승인**했다. 승인은 `VERIFICATION-PROFILE-002.yaml`(actual)에 적용 완료되었고, 그
> 적용 기록·잔존 항목·정정 사항은 **아래 신설 §15**에 있다. §7(instance/architecture 6키)·§8(broker 10키)·
> `MIN_evidence_retention_ms` 합 **17키는 승인되지 않았고 값 null·`owner: TBD`로 fail-closed 유지**된다.
> 프로파일은 잔여 null 때문에 **`status: PROPOSED`·`approved_by: []` 그대로**다.
>
> **아래 §0–§14의 원문은 승인 당시의 후보 제안 상태 그대로 보존**한다(승인 근거의 감사 추적). 따라서
> 본문의 "어떤 값도 승인 효력이 없다"·"YAML 무수정"·"P0-3 미충족" 같은 서술은 **2026-07-29 이전 시점의
> 진술**로 읽어야 하며, 현행 상태는 §15가 정본이다.

> **문서 성격 (규범성 선언).** 본 문서는 **후보 제안서**다. 여기에 적힌 **어떤 값도 승인 효력이 없다**.
> `VERIFICATION-PROFILE-002.yaml`은 **무수정**이며 본 패키지는 그 파일의 어떤 키/값/상태도 바꾸지 않는다
> (`status: PROPOSED`·`approved_by: []` 그대로). 규범 허용 근거는 IMPLEMENTATION-PLAN-002 §1:38 —
> *"I will not fabricate any of these. I can **draft candidates** (done for bounds; role scheme in §3) for you to
> ratify."* 즉 **초안 후보 저작**은 규범이 허가한 준비 행위이고, 승인(P0-1)은 정의상 Bounds-Approver(운영자,
> disposition §1)만 수행한다. 본 문서는 프로젝트-워크플로 산출물이며 GOV-001의 세 거버넌스 행위(비준 /
> ADR acceptance / live authorization) 중 어느 것도 수행하지 않고 어떤 EV 행도 이동시키지 않는다. **커밋 대상
> 아님**(운영자 검토용 드래프트).
>
> 근거 문서(실측 정독): `docs/plans/2026-07-29-tos-phase0-human-gate-register.md` §3·§8·§11 ·
> `docs/plans/2026-07-29-tos-phase0-role-scheme-and-disposition.md` §1·§2.2·§3-3 ·
> `tos-spec/src/part-1-foundation/patches/VERIFICATION-PROFILE-002-IMPLEMENTATION-PLAN-002-Patch-0054.md` ·
> `tos-spec/src/part-1-foundation/VER-002-001-…-Specification.md` §6.

---

## 0. 환경 스코프 — 이 값들이 무엇인가 (읽기 전 필수)

프로파일 `scope.environment: non-live-test` (YAML:27). 따라서 여기 후보값은 **live 운영 캘리브레이션이 아니다.**
그것들은 **EV-L1~L3 테스트 하네스가 강제해야 할 안전 성질의 pass/fail 임계**다. 도출 원칙:

- 각 `B_*` bound은 "안전 사건 발생 → 안전 반응 완료"까지의 **최대 허용 전파 간격**이다. 후보값 = *하네스가
  통과로 인정할 최대치*(초과 = fail).
- 각 `MAX_*` limit은 소비자-로컬 신선도/유효 상한이다. 후보값 = *하네스가 통과로 인정할 최대 age*.
- 각 `MIN_*` limit은 **floor**다(보수적 대기·예약 하한). 후보값 = *하네스가 통과로 인정할 최소치*; 이 방향은
  절대 역전 금지(Patch-0054 §2.4 — "Writing these as `MAX_` would invert their safety direction").
- **정직한 한계 1 (레벨 정합).** 현 구현은 EV-L1(순수 predicate/property 모델, 벽시계 타이밍 미측정 — 30패키지
  pytest 7482, memory index). **타이밍 bound 대부분은 EV-L1에서 수치로 소비되지 않는다.** 그것들은 실제 클럭이
  도는 EV-L2/L3(통합·fault-injection)에서 비로소 측정된다. 그러므로 아래 후보값은 **"EV-L2/L3 하네스가 강제할
  천장"**으로 제안하는 것이고, EV-L1에서는 구조적 성질(예: UNKNOWN⇒DENY, ∅⇒restrictive)만 게이트하며 ms를
  소비하지 않는다. 이 사실은 승인 시 프로파일의 `scope.environment`가 여전히 `non-live-test`임과 정합한다.
- **정직한 한계 2 (임의성).** 다수 키는 "선택된 메커니즘 측정 후 확정"(rationale의 `MEASURE`)을 전제로 한다.
  메커니즘 미선택 상태에서 정확한 수치는 발명이다. 따라서 임의성이 큰 키는 **단일값 대신 범위 + 권고값**으로
  제시하고, 매 행의 후보값은 **"제안"**임을 명시한다(발명 수치 라벨 규율, 아래 §4).

---

## 1. 대상 전수 census — 84 bounds + 79 limits = 163 (누락 0 증명)

실측: `.venv/bin/python`+`yaml.safe_load`로
`tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml` 파싱(Patch-0054 반영 후 디스크 상태).

| 블록 | 키 수 | 본 패키지 처리 |
|---|---:|---|
| `scope:` | 91 | **범위 밖** — 정책 id/generation/digest 슬롯(수치 임계 아님). P0-3/substrate 트랙 소관. |
| `bounds:` | **84** | 7 재확인 + 67 비-broker 후보 + 10 broker P0-2 이연 (아래 분해) |
| `limits:` | **79** | 5 재확인 + (비-broker 후보 + 4 시간-불확실성군 + 6 floor + 5~6 instance/architecture 이연) |
| `review:` | 3 | 범위 밖(independent_reviewer·evidence_location·approval_record — P0-3 소관) |
| **합** | **257** | 수치-임계 대상 = **84 + 79 = 163** (task 명세와 일치) |

**bounds 84 분해(전수·상호배타·합=84):**

| 버킷 | 수 | 판정 근거 |
|---|---:|---|
| B-재확인 (기존 PROPOSED 값) | 7 | `value_ms ≠ null` (§9) |
| B-broker (P0-2 이연·값 제안 금지) | 10 | `measurement_source`에 `broker_capability_profile` 포함 **또는** `semantics ∈ {broker_specific, source_and_broker_specific}` (§8) |
| B-비-broker 후보 (타이밍 전파 간격) | 67 | 나머지 — 전부 `B_*` ms 전파 간격, 내부 로그/트레이스 측정원 (§5) |
| **합** | **84** | ✓ |

**limits 79 분해(전수·상호배타·합=79):**

| 버킷 | 수 | 판정 근거 |
|---|---:|---|
| L-재확인 (기존 값) | 5 | `value ≠ null` (§9) |
| L-비-broker 후보 (신선도/age/human/기간/불확실성/DSL/count) | 64 | §6 L1·L1h·L2·L3·L4·L5·L6 — ms 상한·정책 신선도(내부 정책 선택) |
| L-시간 floor 값제시 (`MIN_`) | 4 | §6-F — 방향 역전 금지(클수록 안전) |
| L-instance/architecture 이연 | 6 | §7 — 경제 magnitude·capacity/quorum floor(배포 Matrix·trial scope·Capacity Domain 합의모델 의존); 이 중 `MIN_` 2개 |
| **합** | **79** | 5+64+4+6=79 (상호배타·부록 A per-key 재증명) |

> **계수 주의(정직).** `MIN_` floor 6개는 성격에 따라 두 절에 **분산**된다: 시간-안전 파생 4개(§6-F) + 경제/합의
> 의존 2개(§7 `MIN_reserved_protective_capacity`·`MIN_capacity_domain_voter_quorum`). 각 limit 키는 **정확히 한
> 절에만** 등장하며(상호배타), 79키 전수 1회 커버를 **부록 A**가 per-key 리스트로 증명한다(누락 0·중복 0).

**MIN_ 키 계수 정정(anti-phantom).** task는 "`MIN_*` 4키"라 했으나 **디스크 실측 = MIN_ 키 6개**:
`MIN_evidence_retention_ms`(Patch-0054 이전부터 존재), `MIN_time_stabilization_interval_ms`,
`MIN_holdover_safety_margin_ms`, `MIN_lease_expiry_fence_ms`, `MIN_reserved_protective_capacity`,
`MIN_capacity_domain_voter_quorum`. Patch-0054 §2.4가 "four quantities are floors"라 부른 것은 **그 패치가
신설한** 4개(stabilization·holdover·lease-fence·reserved-capacity)를 가리키며, `MIN_evidence_retention_ms`(기존
precedent)와 `MIN_capacity_domain_voter_quorum`(패치는 이를 "architecture gap"으로 별도 취급)은 그 "4"에서
빠졌다. **6개 전부 floor이고 방향 역전 금지**임은 동일하다 — 승인 시 6개 모두 `MIN_` 의미(≥)로 다뤄야 한다.

---

## 2. 분류 규율 — 왜 3-way(+재확인)인가

task는 "비-broker vs broker"의 2분류를 지시했으나, 실측 semantics는 **값을 제안할 수 없는 두 종류**를 드러낸다.
fail-closed 정직성을 위해 이연 사유를 분리한다:

1. **비-broker 후보 (값 제안 가능).** 값이 *우리 시스템 내부 전파/정책*의 성질(감지→반응 지연, 소비자-로컬
   신선도)이라 broker 없이 도출 가능. → §5·§6.
2. **broker 측정 이연 (P0-2).** 값이 *외부 broker의 타이밍/의미*(poll cadence·late fill·rate 회복·query
   수렴·replacement gap)에 의존. broker-agnostic 원칙상 값 발명 금지. → §8. **fail-closed: 값 없음 = 해당 EV 행
   READY 불가 유지.**
3. **instance/architecture 이연 (P0-2/INSTANCE — broker 아님).** 값이 *배포 Allocation Matrix·live-trial
   scope·Capacity Domain 합의모델*에 의존(경제 magnitude·quorum). broker 문제는 아니나 그래도 지금 발명 불가.
   → §7. (task 지시대로 "venue-class 캘리브레이션은 P0-2/INSTANCE 이연".)
4. **재확인 (기존 값).** 12키(7 bounds + 5 limits) — 유지/수정 재검토. → §9. 이 12키가 아래 모든 후보값의
   **앵커(calibration basis)**이므로 재확인이 패키지 전체 정합의 하중 지점.

**discriminator 실측 표(broker 판정 두 축).** 아래 10 bounds만 broker. `measurement_source==broker_capability_profile`
6키(정확 일치) + `broker_capability_profile` 부분포함 2키(non_trade) + `semantics: broker_specific`이나
measurement_source가 `*_broker_log`인 2키(protection_gap/overlap). 후자 2키는 measurement_source 문자열만 보면
"비-broker"로 오분류되나 **semantics가 broker_specific**이라 값이 broker order-handling에 의존 → **보수적으로 P0-2
이연**(의심 시 이연 = fail-closed). 이 2-축 판정을 §8에 명시.

---

## 3. broker-agnostic 준수

본 패키지 전체에 고유명사(브로커명)·특정 시장 미시구조(예: 특정 거래소 세션시간·호가단위) **미등장**. venue-class
의존 값은 전부 "P0-2/INSTANCE 이연"으로 표기했다. 앵커 스케일(0·500·1000·2000·30000·60000ms)은
**어느 broker에도 특정되지 않은 일반 안전-전파 스케일**이며, 실 브로커 값은 P0-2 Broker Capability Profile
INSTANCE에서 측정한다.

---

## 4. 값 도출 규율 (전부 강제)

- **보수 방향 판정(YAML semantics 실측).** `B_*` = hard_maximum → **짧을수록 안전**(반응 빠름) → 후보 = 보수적
  하한 근처. `MAX_*` = 상한 → **짧을수록 안전**(더 일찍 deny) → 후보 = 낮은 쪽. `MIN_*` = floor → **클수록
  안전**(더 오래 대기/더 많이 예약) → 후보 = 높은 쪽; **역전 금지**.
- **앵커 정합.** 후보값은 기존 7 PROPOSED bounds + 5 valued limits(§9)의 스케일에서 **파생**한다(발명 최소화).
  앵커: `B_stale_epoch_reject=0`(동기 compare-and-set) · `B_risk_increase_revoke=500`(권한 취소 전파) ·
  `B_external_activity_contain=1000`(감지 후 봉쇄) · `B_authority_partition_detect=2000`(감지) ·
  `B_operator_escalation=30000`(운영자 에스컬레이션) · `B_startup_reconciliation=60000`(기동 게이트) ·
  `MAX_normal_capability_age_ms=1000`(정상 신선도) · `MAX_degraded_lease_holdover_ms=5000`(열화 holdover).
- **근거 앵커 3종** 매 family: (a) YAML semantics/rationale verbatim 위치, (b) rationale에 이미 기재된 ADR
  anchor, (c) 앵커 키와의 계열 일관성.
- **"제안" 라벨.** 모든 후보값은 제안이다. 특히 발명도가 높은 키는 **[제안·범위]**로 표기(단일 확정 아님).
- **owner 후보.** 비-broker = `operator`(Bounds-Approver 승인 대상, disposition §1) · broker = `pending-P0-2` ·
  instance/architecture = `operator`(승인 주체) + 값-게이트 주석.

---

## 5. 후보 bounds — 비-broker 67키 (family별)

전부 `semantics: hard_maximum`(별도 표기 제외), `owner` 후보 `operator`, 방향 = **짧을수록 안전**. 후보값은
EV-L2/L3 하네스 천장 제안이다.

### 5-A. 무효화 → final-egress 거부 leg (18키) · 후보 **500ms** [제안]
앵커: `B_risk_increase_revoke=500`의 rationale — "Final egress denial then follows within B_revocation_to_egress"
(YAML:135). 이 leg는 권한 취소가 egress에서 거부로 반영되는 간격. 계열 일관 500ms.

| 키 | 현재 | 후보 | ADR anchor(rationale) | 리스크 노트 |
|---|---|---|---|---|
| B_revocation_to_egress | null | 500 | ADR-002-007 §§9,16 | chain: revoke(500)+egress(500) ≤ ~1s |
| B_halt_to_egress | null | 500 | ADR-002-007 §§16-17; -015 §15 | HALT 전파 leg |
| B_time_health_to_egress | null | 500 | ADR-002-008 §§8,14.6 | |
| B_recovery_barrier_to_egress | null | 500 | ADR-002-017 §§9,18 | |
| B_critical_input_invalid_to_egress | null | 500 | ADR-002-018 §16 | |
| B_venue_constraint_invalid_to_egress | null | 500 | ADR-002-019 §17 | |
| B_order_conformance_invalid_to_egress | null | 500 | ADR-002-020 §§17-18 | |
| B_aggregate_risk_invalid_to_egress | null | 500 | ADR-002-021 §17 | |
| B_action_flow_invalid_to_egress | null | 500 | ADR-002-022 §17 | |
| B_approval_invalid_to_egress | null | 500 | ADR-002-023 §15 | |
| B_currentness_fence_to_egress | null | 500 | ADR-002-024 §§11-15 | |
| B_trial_abort_to_egress_deny | null | 500 | ADR-002-025 | |
| B_deviation_revoke_to_egress | null | 500 | ADR-002-026 | permissive cache는 currentness proof 아님(rationale) |
| B_incident_signal_to_egress_deny | null | 500 | ADR-002-027 | |
| B_incident_scope_expansion_to_egress_deny | null | 500 | ADR-002-027 | failure_response=EXPAND_CONTAINMENT_AND_HALT(unknown⇒확대) |
| B_monitoring_gap_to_egress_deny | null | 500 | ADR-002-028 §18 | |
| B_release_restriction_to_egress_deny | null | 500 | ADR-002-029 | |
| B_post_trade_invalid_to_egress_deny | null | 500 | ADR-002-030 | |

### 5-B. 무효화 → 권한/RCL 제한 leg (13키) · 후보 **500ms** [제안]
앵커: `B_risk_increase_revoke=500` 직접 일반화(권한 발급자에서 새-위험 허가 취소). 동일 500ms.

| 키 | 현재 | 후보 | ADR anchor | 리스크 노트 |
|---|---|---|---|---|
| B_critical_input_invalid_to_authority | null | 500 | ADR-002-018 §§15-17 | failure_response=HALT_OR_CONTAIN |
| B_venue_constraint_invalid_to_authority | null | 500 | ADR-002-019 §§16-18 | |
| B_aggregate_risk_invalid_to_rcl | null | 500 | ADR-002-021 §§16-18 | RCL admission 거부 |
| B_action_flow_invalid_to_rcl | null | 500 | ADR-002-022 §§13,19 | |
| B_approval_invalid_to_intent | null | 500 | ADR-002-023 §§12,14 | Intent 등록/사용 차단 |
| B_restrictive_fence_commit | null | 500 | ADR-002-024 §§10-11 | Restrictive Fence Record commit |
| B_deviation_revoke_to_authority | null | 500 | ADR-002-026 | |
| B_incident_signal_to_authority_restrict | null | 500 | ADR-002-027 | "administrative confirmation cannot hide inside"(rationale) |
| B_monitoring_gap_to_authority_restrict | null | 500 | ADR-002-028 §§13,17 | alert ack가 bound 연장 불가 |
| B_release_restriction_to_authority_restrict | null | 500 | ADR-002-029 | |
| B_trial_abort_to_authority_revoke | null | 500 | ADR-002-025 | |
| B_post_trade_break_to_restrict | null | 500 | ADR-002-030 | |
| B_post_trade_effect_to_obligation_commit | null | 500 | ADR-002-030 | ⚠ broker-effect 감지 의존 leg — P0-2 교차확인 권고 |

### 5-C. 감지 latency (9키) · 후보 **2000ms** [제안]
앵커: `B_authority_partition_detect=2000`(감지 = 모니터링 cadence의 작은 배수, YAML:128). source-specific은
"per source class; ≤2000, 빠른 소스는 더 짧게".

| 키 | 현재 | 후보 | semantics | 리스크 노트 |
|---|---|---|---|---|
| B_critical_input_loss_detect | null | 2000 | source_specific_hard_maximum | per source class |
| B_venue_constraint_loss_detect | null | 2000 | source_specific_hard_maximum | per venue/session/account/source class |
| B_safety_telemetry_loss_detect | null | 2000 | hard_maximum | ADR-002-028 §§8-13 |
| B_supply_chain_compromise_detect | null | 2000 | hard_maximum | ADR-002-029; 공급망 감지는 더 느릴 수 있음 → [제안·범위 2000–30000] |
| B_runtime_artifact_drift_detect | null | 2000 | hard_maximum | ADR-002-029 |
| B_failure_domain_detect | null | 2000 | hard_maximum | ADR-002-009; per Safety Cell |
| B_post_trade_change_detect | null | 2000 | hard_maximum | ADR-002-030; statement cadence 의존 → [제안·범위] |
| B_evidence_gap_detect | null | 2000 | hard_maximum | ADR-002-016 §14 |
| B_statement_coverage_gap_detect | null | 2000 | hard_maximum | ADR-002-030; source 의존 |

> ⚠ `B_supply_chain_compromise_detect`·`B_post_trade_change_detect`·`B_statement_coverage_gap_detect`는 외부
> 소스/스캔 cadence에 의존(내부 감지만이 아님) → 2000 하한 대신 **[제안·범위 2000–30000ms]**, 소스 cadence 확정 후
> 좁힐 것.

### 5-D. 봉쇄/전이 완료 (7키) · 후보 **1000ms** [제안]
앵커: `B_external_activity_contain=1000`(감지 후 봉쇄, YAML:195). 봉쇄/비허가-전이 완료 계열.

| 키 | 현재 | 후보 | ADR anchor | 리스크 노트 |
|---|---|---|---|---|
| B_action_flow_violation_to_containment | null | 1000 | ADR-002-022 §19 | rate/burst/amplification 위반 봉쇄 |
| B_failure_domain_contain | null | 1000 | ADR-002-009 | detect(2000)와 별 quantity |
| B_trial_evidence_gap_to_containment | null | 1000 | ADR-002-025 | |
| B_protective_replacement_contain | null | 1000 | ADR-002-011 | replacement 실패 봉쇄 |
| B_non_trade_transition_apply | null | 1000 | ADR-002-010 | 완전 비허가 전이; failure_response=REMAIN_HALTED |
| B_evidence_gap_contain | null | 1000 | ADR-002-016 §§14,18 | unknown scope ⇒ 봉쇄 확대 |
| B_cell_halt_to_global_halt | null | 1000 | ADR-002-009 §§13-14 | Patch-0054 신설; blast radius 미확정 시 상위 HALT 에스컬레이션 |

### 5-E. barrier/handoff 순서-commit (2키) · 후보 **1000ms** [제안]
| 키 | 현재 | 후보 | ADR anchor | 리스크 노트 |
|---|---|---|---|---|
| B_recovery_trigger_to_barrier | null | 1000 | ADR-002-017 §§8-9 | 순서 barrier closure 또는 local hard fence |
| B_incident_handoff_to_recovery_barrier | null | 1000 | ADR-002-027 | 불완전 handoff = 의무 미이전(fail-closed) |

### 5-F. generation fence (superseded predecessor 무력화, 8키) · 후보 **500ms** [제안]
newer generation commit → 모든 predecessor가 dependent 허가 생성/사용 불가 증명까지. 동기 compare-and-set
substrate면 0(=`B_stale_epoch_reject`), 분산 전파면 revoke-egress 봉투(500). substrate 미선택 상태에서 0은
동기 메커니즘을 **과잉 주장** → 보수적으로 **500**(권한-전파 봉투) 제안, 동기 substrate 확정 시 0으로 조일 것.

| 키 | 현재 | 후보 | ADR anchor |
|---|---|---|---|
| B_approval_generation_fence | null | 500 | ADR-002-023 §17 |
| B_currentness_generation_fence | null | 500 | ADR-002-024 §§15,19 |
| B_scope_promotion_generation_fence | null | 500 | ADR-002-025 |
| B_deviation_generation_fence | null | 500 | ADR-002-026 |
| B_incident_generation_fence | null | 500 | ADR-002-027 |
| B_monitoring_generation_fence | null | 500 | ADR-002-028 §§12,18,24 |
| B_release_generation_fence | null | 500 | ADR-002-029 |
| B_post_trade_generation_fence | null | 500 | ADR-002-030 |

### 5-G. hard-fence 완결성 (superseded principal이 broker-accepted mutation 불가, 3키) · 후보 **1000ms** [제안·broker-leg 주의]
measurement_source에 `broker`/`broker_transport` 포함(단 `broker_capability_profile`은 아님 → 규칙상 비-broker).
그러나 "broker-accepted mutation 불가" leg는 broker transport 의존. 후보 제시하되 **P0-2 교차확인 필수**.

| 키 | 현재 | 후보 | ADR anchor | 리스크 노트 |
|---|---|---|---|---|
| B_egress_hard_fence | null | 1000 | ADR-002-013 §§13-16 | credential/session/signer/route/broker fence; ⚠ broker-accepted leg P0-2 |
| B_controlled_shutdown_hard_fence | null | 1000 | ADR-002-027 | "cooperative process stop is not proof"; ⚠ broker leg P0-2 |
| B_capability_claim_to_send | null | 500 | ADR-002-007 §§9.4-9.5 | send-path 발급; ⚠ broker transport leg P0-2; 짧아야(hot path) |

### 5-H. 잔여 특수 bounds (7키)
| 키 | 현재 | 후보 | 근거·리스크 노트 |
|---|---|---|---|
| B_human_halt_to_commit | null | **1000** [제안] | 인간 HALT **수용 후** 시스템 commit 지연(인간 반응시간 아님). failure_response=LATCH_LOCAL_HALT_AND_ESCALATE(local latch=fail-closed 바닥). ADR-002-015 §15 |
| B_currentness_gap_to_local_deny | null | **500** [제안] | final egress가 currentness loss 감지 → local DENY_LATCHED. 로컬·빠름. ADR-002-024 §§11,14 |
| B_currentness_proof_issue | null | **500** [제안] | 벡터 검증+single-use proof 원자 생성. send hot path → 짧아야. ADR-002-024 §§12-13 |
| B_evidence_persist | null | **[제안·범위 500–1000]** | durability class 의존(pre-effect+SEND_STARTED durability). substrate 미선택 → 범위. ADR-002-016 §10 |
| B_evidence_anchor | null | **[제안·범위, 정책 cadence]** | Integrity Anchor commit 간 **cadence**(더 긺). Evidence Integrity Policy가 cadence 선언 → 값은 정책 파생. ADR-002-016 §13 |
| B_critical_alert_delivery | null | **[제안·범위 5000–30000]** | detective·병렬 경로, "cannot delay restriction". egress 게이트 아님. ADR-002-028 §16 |
| B_alert_escalation | null | **30000** [제안] | 미달 후 다음 독립 escalation 단계; 앵커 `B_operator_escalation=30000`. 원 deadline 리셋 금지. ADR-002-028 §16 |

**§5 소계: 18+13+9+7+2+8+3+7 = 67 ✓**

---

## 6. 후보 limits — 비-broker (family별)

방향: `MAX_*` 짧을수록 안전 · `MIN_*` 클수록 안전(역전 금지). owner 후보 `operator`.

### 6-L1. 정상-신선도 age 상한 (38키) · 후보 **1000ms** [제안], "per scope; ≤ MAX_normal_capability_age_ms=1000, 느린 소스 클래스만 상향"
앵커: `MAX_normal_capability_age_ms=1000`(YAML:714). 전부 소비자-로컬 proof/snapshot/decision age → 신선도 봉투.

MAX_time_health_snapshot_age_ms · MAX_recovery_readiness_age_ms · MAX_critical_input_snapshot_age_ms ·
MAX_decision_context_age_ms · MAX_venue_constraint_snapshot_age_ms · MAX_order_admissibility_decision_age_ms ·
MAX_canonical_broker_command_age_ms · MAX_order_conformance_proof_age_ms · MAX_aggregate_risk_state_snapshot_age_ms ·
MAX_aggregate_risk_decision_age_ms · MAX_action_flow_state_snapshot_age_ms · MAX_action_flow_decision_age_ms ·
MAX_action_flow_permit_age_ms · MAX_proposal_approval_request_age_ms · MAX_independent_approval_decision_age_ms ·
MAX_egress_currentness_proof_age_ms · MAX_currentness_vector_age_ms · MAX_trial_evidence_age_ms ·
MAX_deviation_decision_age_ms · MAX_incident_scope_snapshot_age_ms · MAX_incident_containment_plan_age_ms ·
MAX_incident_recovery_handoff_age_ms · MAX_incident_closure_decision_age_ms · MAX_critical_telemetry_age_ms ·
MAX_continuous_conformance_snapshot_age_ms · MAX_safety_alert_age_ms · MAX_alert_acknowledgement_age_ms ·
MAX_build_provenance_age_ms · MAX_artifact_admission_decision_age_ms · MAX_admitted_release_set_age_ms ·
MAX_runtime_artifact_attestation_age_ms · MAX_release_key_status_age_ms ·
MAX_post_trade_obligation_snapshot_age_ms · MAX_post_trade_finality_proof_age_ms ·
MAX_statement_coverage_manifest_age_ms · MAX_critical_input_consumer_receipt_age_ms ·
MAX_compatibility_attestation_age_ms · MAX_activation_staging_age_ms.

> 리스크 노트: `MAX_canonical_broker_command_age_ms`·`MAX_action_flow_state_snapshot_age_ms`는 코멘트에
> "per broker/shared-broker-resource scope"라 하나 **값은 우리 command/snapshot의 age**(정책 신선도)이지
> broker-측정치 아님 → 비-broker. `MAX_*_finality_proof_age_ms`·`MAX_post_trade_*`는 "expiry never expires
> economic effect"(코멘트) — age 만료가 경제효과를 소멸시키지 않음을 하네스가 검증해야(§13 참조).

### 6-L1h. 인간-권한 age 상한 (3키) · **[제안·범위, 분~세션 스케일]**
정상 신선도(1000ms)와 다른 스케일 — 인간 권한은 초 단위가 아니라 분~세션 유효. 짧을수록 안전(stale⇒권한 거부).
"per approval type / authority direction / delegation policy". owner 후보 `operator`.

| 키 | 현재 | 후보 posture | ADR·리스크 노트 |
|---|---|---|---|
| MAX_human_approval_age_ms | null | [범위: 분~세션] | stale/unknown age⇒authority increase 거부 |
| MAX_human_session_age_ms | null | [범위: 세션] | unknown age⇒command 거부 |
| MAX_human_delegation_age_ms | null | [범위: delegation policy별] | expiry가 approval 이전/부활 금지 |

### 6-L2. 유효기간/기간/리뷰-주기 상한 (7키) · **[제안·범위, 거버넌스 지평]**
정상 신선도(1000ms)와 다른 훨씬 긴 스케일(세션~일). 짧을수록 안전(잦은 재-attestation 강제). 권고 posture:
"클래스별 최단 유효기간 — 단일 세션~단일 일 이내, 자동 갱신 금지."

| 키 | 현재 | 후보 posture | ADR |
|---|---|---|---|
| MAX_safety_profile_validity_ms | null | [범위: ≤1 세션~1일] | -014 §7 |
| MAX_live_authorization_validity_ms | null | [범위: ≤1 세션·짧게] | -007 §§7,9 |
| MAX_deviation_duration_ms | null | [범위: reduced scope 최단] | -026 |
| MAX_trial_duration_ms | null | [범위: exact run 최단] | -025 |
| MAX_envelope_review_interval_ms | null | [범위: 정기 리뷰 주기] | -014 §7 |
| MAX_residual_risk_review_interval_ms | null | [범위: risk class별] | -026 |
| MAX_monitoring_suppression_duration_ms | null | [범위: 최단·자동 재개 금지] | -028 |

### 6-L3. 에스컬레이션-deadline 상한 (4키) · 후보 **30000ms** [제안], "escalation deadline only; 초과가 봉쇄 완화 아님"
앵커: `B_operator_escalation=30000`. "age never converts to resolved"(코멘트).

MAX_unresolved_post_trade_break_age_ms · MAX_quarantined_capacity_age_ms · MAX_replay_start_delay_ms ·
MAX_pending_external_transfer_age_ms.

> 리스크 노트: `MAX_pending_external_transfer_age_ms`는 "per transfer rail; timeout never proves
> non-acceptance/finality" — 전송 rail(은행/broker) 지평이 길 수 있음 → [제안·범위 30000–수 시간], escalation
> 전용. `MAX_replay_start_delay_ms`는 incident/review 타깃(더 느슨 가능).

### 6-L4. 시간-불확실성 항 (10키) · **[제안·범위, per reference-source class]**
Trustworthy-Time 보수적 신선도 입력. snapshot age에 **가산**되는 작은 불확실성(음의 값 아님). `MAX_clock_drift_ppm=200`
(이미 값)과 정합. 대부분 작게(수십~수백 ms) 제안, correction_horizon은 소스-클래스 의존(길 수 있음).

| 키 | 현재 | 후보 posture | ADR |
|---|---|---|---|
| MAX_time_transport_and_queue_uncertainty_ms | null | [범위 ~50–500] | -008 §§8-9 |
| MAX_clock_domain_conversion_uncertainty_ms | null | [범위 ~50–500] | -008 §§8-9 |
| MAX_time_source_disagreement_ms | null | [범위 ~50–500; 초과⇒TRUSTED 상실] | -008 §§7,13 |
| MAX_clock_offset_ms | null | [범위; drift와 별 bound] | -008 §§7-8 |
| MAX_future_timestamp_tolerance_ms | null | [범위 작게; 초과⇒거부, 0으로 강제금지] | -008 §9 |
| MAX_time_source_precision_ms | null | [범위, source class별] | -008 §9 |
| MAX_time_source_sequence_gap_ms | null | [범위; unknown/unbounded⇒TRUSTED 거부] | -008 §9 |
| MAX_critical_input_source_production_delay_ms | null | [범위, source class별] | -018 §14 |
| MAX_critical_input_transport_and_queue_delay_ms | null | [범위; unknown/unbounded⇒deny] | -018 §14 |
| MAX_critical_input_correction_horizon_ms | null | [범위, **길 수 있음** — 정정 미도착이 지평 축소 아님] | -018 §14 |

### 6-L5. DSL 평가 예산 (1키) · **[제안·범위 10–100ms]**
| 키 | 현재 | 후보 | 근거 |
|---|---|---|---|
| MAX_dsl_evaluation_ms | null | [제안·범위 10–100] | RFC-008 §6; hot-path 컴퓨트 예산; 소진⇒no action(안전 degrade)·partial 금지 |

### 6-L6. amplification 카운트 (1키) · **[제안·소정수]**
| 키 | 현재 | 후보 | 근거 |
|---|---|---|---|
| MAX_action_amplification_per_cause | null | [제안·소정수, 예: ≤3–5 per cause/action class] | -022; runaway 증폭 안전-핵심 → 보수적 작게; 초과⇒containment |

### 6-F. 시간 floor `MIN_*` (4키, 값 제시 가능분) · 방향 = **클수록 안전, 역전 금지** [제안·범위]
| 키 | 현재 | 후보 posture | 근거·리스크 |
|---|---|---|---|
| MIN_time_stabilization_interval_ms | null | [≥ 수 초, 예: 1000–5000+] | -008 §16; 재-신뢰 전 sync 지속 최소; **짧으면 안정성 미증명** |
| MIN_holdover_safety_margin_ms | null | [≥ 수백 ms~수 초] | -008 §11.2; holdover(5000)에서 차감할 여유; margin이 클수록 보수적 |
| MIN_lease_expiry_fence_ms | null | [≥ holdover+suspension+margin, 예: ≥ ~7000–10000] | -003 §§5.9,14.5; **critical** — offline owner가 여전히 전송 못하도록 재배정 대기; Hard Fence 증명 없으면 이 floor 필수 |
| MIN_evidence_retention_ms | null | **[INSTANCE/정책 이연]** | -016; economic-effect+검증 지평(일~년) 지배 → §7로 이연(값 미발명); floor·축소 금지 |

> `MIN_evidence_retention_ms`는 floor이나 경제/법무 지평 의존이라 **§7 instance 이연**으로 처리(값 미제시).
> 나머지 3 floor는 시간-안전 파생이라 범위 제시 가능.

**§6 소계: L1(38) + L1h(3) + L2(7) + L3(4) + L4(10) + L5(1) + L6(1) + F(4, MIN_evidence 포함) = 68키**
(전부 null; 이 중 `MIN_evidence_retention_ms`는 §6-F 표에 두되 값 미제시·§7 성격 이연 주석).

---

## 7. instance/architecture 이연 (broker 아님·값 미발명, 6키)

값이 배포 Allocation Matrix / live-trial scope / Capacity Domain 합의모델 / 경제·법무 지평에 의존. task 지시:
"venue-class 캘리브레이션은 P0-2/INSTANCE 이연". **값 없음 = 해당 EV 행 READY 불가 유지(fail-closed).**

| 키 | 유형 | 이연 사유 | 방향 | owner 후보 |
|---|---|---|---|---|
| MAX_safety_cell_blast_radius | 경제 magnitude | Failure-Domain Allocation Matrix INSTANCE 필요; unbounded⇒scope 확대 | MAX(짧을수록 안전) | operator(값=INSTANCE 게이트) |
| MAX_trial_authorized_economic_effect | 경제 magnitude | live-trial scope별; unknown/unbounded⇒trial 금지 | MAX | operator(값=trial INSTANCE) |
| MAX_trial_concurrent_potential_effect | 경제 magnitude | 공유 capacity scope; abort/recovery overlap 포함 | MAX | operator(값=trial INSTANCE) |
| MAX_trial_action_count | 카운트 | exact plan별 | MAX | operator(값=trial INSTANCE) |
| MIN_reserved_protective_capacity | capacity **floor** | per capacity scope; 정상 활동이 소비 불가한 최소 예약 | **MIN(클수록 안전)** | operator(값=capacity INSTANCE) |
| MIN_capacity_domain_voter_quorum | 합의 **floor** | Patch-0054 §2.5 명시: Capacity Domain 경계+fault-tolerance 모델은 **별도 아키텍처 결정**; 이 키는 수치 gap만 등록 | **MIN** | operator(값=**architecture 결정** 게이트) |

**§7 소계: 6키** (그중 MIN 2 = floor).

---

## 8. broker-측 키 — P0-2 이연 (값 제안 금지·전수 열거, 10 bounds · 0 limits)

**값 제안 절대 금지.** 승인된 Broker Capability Profile INSTANCE에서 **측정**해야 함(broker-agnostic). fail-closed:
값 null 유지 = 해당 EV 행 READY 불가. owner 후보 = `pending-P0-2`.

| 키 | semantics | measurement_source | broker 판정축 |
|---|---|---|---|
| B_external_activity_detect | hard_maximum | broker_capability_profile | ms==profile (poll cadence) |
| B_final_quantity_proof | broker_specific | broker_capability_profile | 양축 |
| B_late_fill_observation | broker_specific | broker_capability_profile | 양축 |
| B_protective_request_complete | broker_specific | broker_capability_profile | 양축 |
| B_broker_query_consistency | broker_specific | broker_capability_profile | 양축 |
| B_rate_limit_recovery | broker_specific | broker_capability_profile | 양축 |
| B_protection_gap | broker_specific | protective_replacement_and_broker_log | **semantics축**(ms는 *_broker_log이나 broker_specific) |
| B_protection_overlap | broker_specific | protective_replacement_and_broker_log | **semantics축** |
| B_non_trade_event_detect | source_and_broker_specific | reference_source_and_broker_capability_profile | 양축 |
| B_non_trade_reconcile | source_and_broker_specific | reconciliation_and_broker_capability_profile | 양축 |

**limits 중 broker-측정 필요분 = 0 (증명).** 79개 limit을 전수 검토했을 때 `measurement_source` 필드 자체가 없고
(limits는 flat scalar), 코멘트에 "per broker scope"가 등장하는 키(`MAX_canonical_broker_command_age_ms` 등)도 값은
**우리 시스템의 신선도/정책 상한**이지 broker 타이밍 측정치가 아니다(§6-L1 리스크 노트). 따라서 broker-측정을
요구하는 limit은 없다 — limit의 이연은 전부 **instance/architecture**(§7)이지 broker(P0-2 profile)가 아니다. 이
구분이 중요한 이유: P0-2 Broker Capability Profile INSTANCE가 착지해도 limit 값은 자동 해소되지 않는다(별도 정책
승인 필요).

**§8 소계: 10 bounds + 0 limits.**

---

## 9. 재확인 — 기존 PROPOSED 7 bounds + 값 5 limits (유지/수정)

전부 **유지(수정 불요) 권고**. 이 12키는 §5–§6 후보값의 앵커이므로 재확인이 패키지 정합의 하중 지점. 승인 시
이 값들도 `PROPOSED→APPROVED` 상태 전이 대상.

**bounds(7):**
| 키 | 현재값 | 권고 | 근거 재기술(rationale 실측) |
|---|---|---|---|
| B_authority_partition_detect | 2000 | 유지 | ~500ms heartbeat×3 missed; ADR-002-003 heartbeat 설계와 재대조 조건부(rationale 자체 명시) |
| B_risk_increase_revoke | 500 | 유지 | 손실 감지 후 new-risk 허가 취소; **§5-A/B 앵커** |
| B_stale_epoch_reject | 0 | 유지 | 동기 compare-and-set; stale epoch 변이 window 없음; ADR-002-002 INV-008 |
| B_external_activity_contain | 1000 | 유지 | 외부활동 감지 후 권한 정지+reconcile; **§5-D 앵커** |
| B_startup_reconciliation | 60000 | 유지 | operational_target_and_hard_gate; 초과⇒에스컬레이션(게이트 완화 아님) |
| B_protective_request_start | 1000 | 유지 | degraded 진입→첫 protective request; ADR-002-001 |
| B_operator_escalation | 30000 | 유지 | Critical 운영 이벤트 에스컬레이션; **§5-H/§6-L3 앵커** |

**limits(5):**
| 키 | 현재값 | 권고 | 근거 재기술 |
|---|---|---|---|
| MAX_normal_capability_age_ms | 1000 | 유지 | 정상 capability/currentness proof age; **§6-L1 앵커** |
| MAX_degraded_lease_holdover_ms | 5000 | 유지 | pre-issued degraded lease 최대 수명; MIN_holdover/lease-fence의 기준 |
| MAX_clock_drift_ppm | 200 | 유지 | 초과⇒time confidence 상실·fail closed; ADR-002-003 (비-시간 ppm) |
| MAX_process_suspension_ms | 2000 | 유지 | 초과 정지⇒resume 시 fence; MIN_lease_expiry_fence 입력 |
| MAX_unresolved_send_per_scope | 1 | 유지 | 구조적: scope당 미해결 send 최대 1(template 유래) |

**§9 소계: 7 bounds + 5 limits = 12키.**

---

## 부록 A — 79 limits 정본 커버리지 (누락 0·중복 0 증명)

**limits (79):** §6-L1(38) + §6-L1h(3) + §6-L2(7) + §6-L3(4) + §6-L4(10) + §6-L5(1) + §6-L6(1) +
§6-F(4, `MIN_evidence_retention_ms` 포함) = §6 전체 **68**(전부 null) ; + §7 instance/architecture(6, 전부 null) +
§9-limits(5, valued) = **79** ✓. (null 74 = 68 + 6 ; valued 5. 각 키 정확히 한 절에만.)

**bounds (84):** §5(67) + §8(10) + §9-bounds(7) = **84** ✓.

**총 커버 = 84 + 79 = 163, 누락 0·중복 0.** (anti-phantom 스크립트 검증: 프로파일 84 bounds·79 limits를 파서
출력 전수와 1:1 대조 — 문서 미등장 키 0, 문서-유일 phantom 0. `B_example`은 동봉 1의 스키마 예시 스니펫이라
실키 아님.)

---

## 10. 동봉 1 — per-bound 스키마 보강 제안 (VER-002-001 §6, 후속 Patch-0055)

**실측.** VER-002-001 §6(:242–250)은 **모든 bound에** 7속성을 요구:
① owner ② rationale ③ measurement source ④ percentile/hard-maximum semantics ⑤ **applicable broker/profile/scope**
⑥ failure response ⑦ **review date**. 현 프로파일 bound은 6필드
(`value_ms·semantics·owner·rationale·measurement_source·failure_response`) — ⑤·⑦ **per-bound 부재**(scope는
프로파일 전역 `scope:` 블록에만, review는 전역 `review_due`만 존재). register §3:96·§11 D2-b가 지목한 gap.

**제안(적용은 Patch-0055 — 본 패키지는 제안만, YAML 무수정):** 각 bound의 6필드 shape에 2필드 추가 → 8필드:

```yaml
  B_example:
    value_ms: null
    semantics: hard_maximum
    owner: TBD
    rationale: "..."
    measurement_source: ...
    failure_response: ...
    applicable_scope: TBD        # NEW (VER §6 ⑤): broker/profile/scope 적용 범위
    review_date: null            # NEW (VER §6 ⑦): 이 bound 값의 재검토 기한(전역 review_due와 별개 per-bound)
```

- **적용 범위:** VER §6은 "for every bound"라 bounds 84개에 우선 적용. limits는 flat scalar(구조화 시 큰 변경)
  → 본 제안은 bounds 한정, limits는 전역 `review_due` 유지 또는 병렬 후속 결정으로 명시 분리.
- **null/TBD 신설 원칙:** Patch-0054 선례(키 등록 ≠ 승인) 준수 — 신설 필드는 `TBD`/`null`, 승인 흐름에 합류.
  key-set identity(actual↔template) 보존 필수(양 파일 동시 편집).
- **주의:** 이 보강은 **키 구조 변경**이라 profile version-bearing 여부를 Patch-0055에서 판정(Patch-0054는
  "registering a key is not version-bearing"이라 unchanged 유지 — 구조 필드 추가도 동일 논리 적용 가능).

---

## 11. 동봉 2 — dimension-id 전역 namespace 규약 초안 (AFG §10.3 항목 6 / disposition §2.2)

**문제(Gap-1).** `CapacityVector.dimension_id`는 자유 문자열(`tos/src/tos/rcl/vector.py:67` `dimension_id: str | None`).
**4 소비자**가 같은 컨테이너 타입에 dimension-id를 실음:
- **rcl** — 소유(CapacityVector/CapacityComponent). 경제/capacity 차원.
- **are** — `AdverseIncrement`가 CapacityVector REUSE(`are/records.py:61,289`; are→rcl edge).
- **ioc** — `EconomicEffectEnvelope = CapacityVector`(`ioc/records.py:69` 별칭; ioc→rcl edge).
- **afg** — `ActionFlowVector = CapacityVector`(`afg/records.py:86` 별칭; afg→rcl edge).

afg 설계 §7(:466–484)는 REUSE 정당화("좌표 붕괴 방지")가 성립하려면 **afg action-flow dimension-id 집합 ∩ 경제
dimension-id 집합 = ∅**이어야 함을 §7 core property로 두되, **afg 몫만 확정**하고 전역 규약은 §10.3 항목 6(Gap-1)로
이연했다. 현 상태:
- afg 토큰: `ActionFlowDimensionKind` StrEnum 13개(`afg/vocabulary.py:198–210` — `BROKER_REQUEST`·`ORDER`·
  `ORDER_MUTATION`·`CANCEL_AMEND_REPLACE`·`QUERY`·`SESSION`·`CONNECTION`·`CREDENTIAL`·`ROUTE`·`ENDPOINT`·
  `QUEUE`·`IN_FLIGHT`·`CAUSE_AMPLIFICATION`) — **무접두사** 대문자 자원 토큰.
- 경제 토큰(rcl/are/ioc): **enum/상수 없음** — 순수 ad-hoc 자유 문자열(테스트 실측: `GROSS_NOTIONAL`·`qty`·
  `notional`). 구조적 disjointness 강제 장치 부재 → 미래 경제 dimension이 afg 토큰과 충돌하면 fail-closed 산술이
  좌표 붕괴로 깨질 잠재 결함.

**규약 초안(disposition §2.2 권고):** dimension-id에 **패키지 접두사 의무화** — `rcl.`/`are.`/`ioc.`/`afg.` —
**무접두사 = rcl 소유 기존 id로 한정**. 접두사 유일성이 disjointness를 **구조적으로** 보장(afg.* ∩ rcl.* = ∅ 자명).

**채택 시 코드 영향 실측(grep 근거):**

- **rcl/are/ioc 소스: 영향 0 (증명).** `grep -rnE 'dimension_id\s*=\s*["'"'"'][^"'"'"']+["'"'"']' tos/src/tos` →
  **0 hit**. `grep -rnE 'Capacity(Component|Vector)\([^)]*["'"'"']' tos/src/tos` → **0 hit**. rcl/are/ioc 소스에
  경제 dimension-id enum/literal **부재**(dimension_id는 전부 `applicable_dimensions: Sequence[str]` 등
  **호출자 주입 변수**). ⇒ 접두사 규약 채택해도 이 3패키지 소스는 **무변경**; go-forward INSTANCE/테스트 데이터
  저작만 접두사 채택.
- **afg 소스: 영향 있음 (비-0·전수 열거).** 유일하게 구체 토큰을 가진 패키지. 규약 초안("무접두사=rcl 한정")을
  엄격 적용하면 afg의 무접두사 13토큰이 **규약 위반**(afg 소유인데 무접두사) → 다음이 변경 대상:
  1. `afg/vocabulary.py:198–210` `ActionFlowDimensionKind` 13값 → `afg.BROKER_REQUEST` 등 접두사화.
  2. `ACTION_FLOW_DIMENSION_IDS`(:219–221)·`is_action_flow_dimension_id`(:344–360)는 enum 파생이라 **자동
     정합**(코드 로직 무변경, 값만 변경).
  3. 그 13토큰을 쓰는 afg 테스트 fixture + Gap-1 disjointness property test(테스트 레인).
- **전역 disjointness property의 HOME 결정 필요.** afg는 rcl/are/ioc를 **import 불가**(firewall)라 현재 afg
  테스트 레인은 **afg 몫만** 검증한다. 4-namespace 전역 disjointness를 검증하려면 4패키지를 모두 볼 수 있는
  **cross-package 테스트 레인**(예: `tos/tests/replacement/test_seam_*` 패턴)에 property를 둬야 함 —
  테스트-아키텍처 결정 사항.

**두 변형(운영자 D2 택1):**
- **변형 A(엄격·구조적).** 접두사 의무화 + afg 13토큰 접두사화. 이득: disjointness 구조 보장. 비용: afg
  vocabulary+fixtures+property 변경(bounded, 위 열거) + 전역 property HOME 신설.
- **변형 B(저영향·registry).** 신규 dimension-id만 접두사 의무화, 기존 enum 토큰은 grandfather(afg 무접두사 유지,
  registry가 소유 귀속). 이득: **코드 변경 0**. 비용: 구조적 아닌 registry 규율 의존(약함) — afg 무접두사 토큰과
  미래 경제 토큰 충돌 방지는 registry 검사에 의존.

**권고:** disjointness의 안전 하중을 고려하면 **변형 A** 우선(구조적 fail-closed), 단 afg 접두사화는 별도
Patch로 afg 사이클 재검토 지점(#16 소급 승인 대상, disposition §2.2)과 함께 처리. 채택 여부·변형은 **D2 승인 시
운영자 결정**(초안 제시만).

---

## 12. 승인 방법 (운영자 일괄 검토·승인 절차)

승인은 Bounds-Approver(운영자, disposition §1)만. 승인 시 **YAML 갱신 절차**(별도 편집 작업 — 본 문서는 절차만
기술):

1. **키별 값 확정.** §5·§6·§9의 후보값/범위를 검토해 각 `value_ms`(또는 limit scalar)를 확정/치환. 범위 제시
   키는 단일값 선택. instance/architecture(§7)·broker(§8) 키는 **null 유지**(승인 대상 아님).
2. **프로파일 헤더 상태 전이:** `status: PROPOSED → APPROVED` · `approved_by: [] → [operator]`(또는 실체
   식별자) · `effective_from: null → <ISO ts>` · `review_due: null → <ISO ts>`.
3. **키별 owner 지정:** `owner: TBD → operator`(비-broker) / `pending-P0-2`(broker) — register §8-3 "키별 owner
   지정도 승인 작업의 일부".
4. **broker/instance 키 명시 분리 기록:** §7·§8 키는 승인 세션에서 "P0-2/INSTANCE 이연"으로 명기(승인 누락이
   아니라 의도적 fail-closed 보류임을 approval_record에 기록).
5. **후속 Patch 트랙:** (a) Patch-0055 = per-bound `applicable_scope`·`review_date` 필드 신설(동봉 1). (b)
   dimension-id 규약 채택 시 별도 Patch(동봉 2 변형 A/B). (c) 승인 반영은 GOV-001 change process 준수 —
   actual+template key-set identity 보존, ARCHITECTURE-GATE-STATUS §4 계수 갱신(Patch-0054 §5 owed follow-up:
   "82 bounds/55 limits" → "84/79" 갱신도 함께).

---

## 13. 승인이 의미하지 **않는** 것 (정직 절)

- **READY 자동 전이 아님.** bounds 승인(P0-1)은 EV 행의 `NOT_IMPLEMENTED → READY` 6요소 중 하나(Profile-dependent
  해소)일 뿐. **P0-3(owner/evidence-owner/독립 리뷰어 지정 372행)이 여전히 선행 미충족**이면 어떤 행도 READY 불가
  (register §2 사슬). 승인은 "bounds were measured" 조건 1개를 여는 것이지 acceptance가 아니다.
- **broker 행은 P0-2 잔존.** §8의 10 bounds는 값 null 유지 → 그 bound에 의존하는 EV 행은 **승인 후에도 READY
  불가**. 이것은 결함이 아니라 fail-closed 설계(값 없음 = 차단 유지).
- **instance/architecture 키도 미해소.** §7의 6키는 broker와 무관하게 INSTANCE/아키텍처 결정 전까지 null 유지.
- **EV 실행은 별개.** 승인은 하네스 임계를 확정할 뿐, 실제 EV-L1~L3 실행·fault 주입·독립 리뷰어 서명(PASS)·ADR
  acceptance는 전부 후속 별도 게이트(register §2·§5).
- **범위 제시 키는 미확정.** `[제안·범위]` 키는 운영자가 단일값을 고르기 전엔 승인 미완(부분 승인 시 명기).
- **환경 스코프 유지.** 승인해도 `scope.environment: non-live-test` 불변 — 이 값들은 테스트 하네스 임계이지 live
  캘리브레이션이 아니다(§0). live 캘리브레이션은 별도 트랙.

---

## 14. 판단이 필요했던 키 목록 (재량 행사 지점 — 운영자 특별 검토 권고)

아래는 semantics만으로 값이 일의적이지 않아 **오케스트레이터가 보수적 재량**을 행사한 지점. 승인 시 우선 검토:

1. **generation fence 8키(§5-F): 0 vs 500 선택.** 동기 compare-and-set substrate면 0(=stale_epoch_reject)이
   가장 안전하나 미선택 substrate에서 0은 동기 메커니즘 과잉주장 → **500 제안**. substrate 확정 시 재검토.
2. **hard-fence 3키(§5-G): broker-transport leg.** measurement_source에 broker 포함(단 profile 아님) → 규칙상
   비-broker이나 "broker-accepted mutation" leg는 broker 의존 → 값 제시+**P0-2 교차확인 필수** 병기.
3. **protection_gap/overlap(§8): semantics-축 broker 판정.** measurement_source=`*_broker_log`(profile 아님)라
   문자 규칙으론 비-broker이나 semantics=broker_specific → **보수적 P0-2 이연**(의심 시 이연).
4. **detect 3키(§5-C): 외부 cadence 의존.** supply_chain/post_trade_change/statement_coverage detect는 외부
   스캔/statement cadence 의존 → 2000 단일값 대신 **[범위 2000–30000]**.
5. **L2 유효기간 7키·L4 시간-불확실성 10키(§6): 발명도 높음.** 메커니즘/소스-클래스 미선택 → **범위+posture만**,
   단일값 미제시.
6. **MIN_ floor 방향(§6-F·§7): 역전 금지.** 6개 floor 전부 "클수록 안전" — MAX 앵커에서 파생 금지. 특히
   `MIN_lease_expiry_fence_ms`는 offline-owner 전송 방지 critical floor.
7. **MIN_evidence_retention_ms 분류.** floor이나 경제/법무 지평 의존 → §6-F에서 §7(instance 이연)로 이동(값
   미발명). 분류 재량 지점.
8. **MIN_ 계수 6 vs task "4".** 디스크 실측 6개 — Patch-0054 §2.4 "4"는 신설분만 지칭. 6개 전부 floor 처리(§1).
9. **dimension-id 규약 변형 A/B(동봉 2).** 구조적(A) vs 저영향(B) — 안전 하중상 A 권고하나 afg 코드 변경 수반 →
   운영자 결정.

---

## 15. 승인 기록 (2026-07-29, 운영자 Bounds-Approver) — 적용 완료

> 본 절이 **현행 상태의 정본**이다. §0–§14는 승인 당시의 후보 제안 원문으로 보존된다(§헤더 노트).

### 15.1 결정

운영자가 Bounds-Approver 자격(role-scheme/disposition §1)으로 **2026-07-29**에 다음을 결정했다:

- §5/§6의 **제안 134키 일괄 승인**. 범위(`[제안·범위]`) 키는 **권고값 채택**.
- §9의 **재확인 12키 승인**(값 유지 + owner/승인 표기).
- **§7(6키)·§8(10키)·`MIN_evidence_retention_ms`(1키) = 17키는 승인하지 않음** — 의도적 fail-closed 보류.
- 후속 **Patch-0055 착수**(동봉 1 = per-bound `applicable_scope`/`review_date` 신설).

### 15.2 무엇이 승인됐나 — 146키 (전수 계수)

| 구분 | 절 | 키 수 | 적용 내용 |
|---|---|---:|---|
| 신규 승인 bounds | §5-A..§5-H | **67** | `value_ms` 기입 · `owner: TBD → operator` · rationale 말미 승인 표기 · `review_date: 2027-01-29` |
| 재확인 bounds | §9-bounds | **7** | 값 유지 · owner/표기/`review_date` 동일 적용 |
| 신규 승인 limits | §6-L1..§6-F | **67** | scalar 값 기입 · 인라인 코멘트에 승인 표기 + `owner=operator; review_date=2027-01-29` |
| 재확인 limits | §9-limits | **5** | 값 유지 · 코멘트 표기 동일 적용 |
| **합** | | **146** | |

승인 표기 문자열: `[APPROVED 2026-07-29 operator (Bounds-Approver); draft d6babce9 <절>]`.
`d6babce9`는 본 패키지의 커밋으로, 승인된 값의 **정본 출처**다.

패밀리별 채택값(§5/§6 표 그대로): §5-A 500 ×18 · §5-B 500 ×13 · §5-C 2000 ×9 · §5-D 1000 ×7 ·
§5-E 1000 ×2 · §5-F 500 ×8 · §5-G 1000/1000/500 · §5-H 1000/500/500/500/30000/5000/30000 ·
§6-L1 1000 ×38 · §6-L3 30000 ×4 · §6-L5 10 · §6-L6 3.

### 15.3 무엇이 잔존하나 — 17키 (값 null · owner TBD · fail-closed)

| 키 | 절 | 이연 사유 |
|---|---|---|
| `B_external_activity_detect`·`B_final_quantity_proof`·`B_late_fill_observation`·`B_protective_request_complete`·`B_broker_query_consistency`·`B_rate_limit_recovery`·`B_protection_gap`·`B_protection_overlap`·`B_non_trade_event_detect`·`B_non_trade_reconcile` | §8 (10 bounds) | **P0-2** — 승인된 Broker Capability Profile INSTANCE에서 측정. broker-agnostic 원칙상 값 발명 금지 |
| `MAX_safety_cell_blast_radius`·`MAX_trial_authorized_economic_effect`·`MAX_trial_concurrent_potential_effect`·`MAX_trial_action_count`·`MIN_reserved_protective_capacity`·`MIN_capacity_domain_voter_quorum` | §7 (6 limits) | **INSTANCE/architecture** — Allocation Matrix · live-trial scope · Capacity Domain 합의모델 의존 |
| `MIN_evidence_retention_ms` | §6-F→§7 (1 limit) | 경제/법무 보존 지평 의존(floor·축소 금지) |

**owner 처분(정직).** 패키지 §4는 broker 키의 owner 후보를 `pending-P0-2`로 제안했으나, 승인 세션은
**`owner: TBD` 유지**를 택했다 — 해당 bound의 rationale에 `pending-P0-2` 문자열이 없어 owner 필드에만
새 어휘를 도입하면 프로파일 어디에도 정의되지 않은 owner 값이 생기기 때문이다. 이연 사유는 owner 필드가
아니라 §8/§15.3·프로파일 헤더 노트·본 절이 기록한다.

### 15.4 프로파일 전역이 `PROPOSED`로 남는 이유

프로파일 헤더의 비준 규칙(YAML:7–13)은 `status: APPROVED` 전이의 선행 조건으로 **"each `value_ms` is
confirmed or replaced by the accountable owner"**를 요구한다. 잔여 null 17키가 있는 한 이 조건은
미충족이므로:

- `status: PROPOSED` **불변**, `approved_by: []` **불변**, `version: "2.1-PROPOSED"` **불변**,
  `effective_from: null` **불변**.
- `review_due: null → "2027-01-29"` **설정함**. 같은 규칙 목록이 `effective_from`/`review_due`를
  APPROVED의 **선행 조건**으로 열거하므로(금지가 아니라 요구), PROPOSED 상태에서 설정하는 것이 규칙에
  부합한다. per-bound `review_date`와 동일한 6개월 주기다.
- `scope.environment: non-live-test` **불변** — 승인된 값은 EV-L1~L3 하네스 임계이지 live 캘리브레이션이
  아니다(§0).

### 15.5 §13 정정 — "P0-3 미충족"은 stale

§13 첫 항목은 "**P0-3**(owner/evidence-owner/독립 리뷰어 지정 372행)이 여전히 선행 미충족"이라고
서술한다. 이 서술은 본 패키지 저작 시점 기준이며 **현재는 사실이 아니다**: P0-3은 병렬 작업으로
**커밋 `f85434c3`**("chore(tos-spec): P0-3 — assign owners/reviewer across all 372 evidence items",
2026-07-29)에서 닫혔다 — 372행 전체에 impl owner·evidence owner·independent reviewer가 지정되었고,
+Broker 64행은 `pending-P0-2`로 표시되었다.

**단, §13의 결론은 유효하다.** P0-1(본 승인)과 P0-3이 모두 닫혀도 EV 행은 자동으로 READY가 되지 않는다.
`f85434c3` 자신이 "Status untouched: 372/372 NOT_IMPLEMENTED (READY still gated on P0-1)"라 기록했고,
P0-1이 **부분** 승인이므로 §8·§7 키에 의존하는 행은 계속 차단된다. §13의 나머지 항목(broker 행 P0-2 잔존 ·
instance/architecture 미해소 · EV 실행은 별개 · 환경 스코프 유지)은 전부 그대로 유효하다.

### 15.6 재량 행사 지점 — 표에 수치가 없어 보수 측을 택한 19키

§14는 승인 **전** 재량을, 본 절은 승인 **적용 시** 재량을 기록한다. 패키지 표가 단일 수치도 수치 대역도
제시하지 않은 키는 "값 재발명 금지" 규율상 보수 측(`MAX_`=짧게, `MIN_`=길게)을 택하고 여기 전수 기록한다.
파생 사다리(문서화된 앵커): `MINUTE = 60000`(프로파일 기존 최장 앵커 `B_startup_reconciliation`) ·
`SESSION = 3600000`(60×MINUTE; 시장 미시구조 비의존 일반 운영 세션) · `DAY = 86400000` ·
`REVIEW_CYCLE = 15552000000`(180일 = 본 승인이 정한 6개월 주기).

| 키 | 패키지 제시 | 채택값 | 보수 근거 |
|---|---|---:|---|
| `B_evidence_anchor` | [범위, 정책 cadence] | 30000 | detect/contain 스케일보다 길되(§5-H "더 긺") 최장 앵커 60000보다 짧은 쪽 |
| `MAX_human_approval_age_ms` | [분~세션] | 60000 | 대역 최단(MINUTE) |
| `MAX_human_session_age_ms` | [세션] | 3600000 | SESSION |
| `MAX_human_delegation_age_ms` | [delegation policy별] | 60000 | L1h 대역 최단(MINUTE) |
| `MAX_safety_profile_validity_ms` | [≤1 세션~1일] | 3600000 | 대역 최단(SESSION) |
| `MAX_live_authorization_validity_ms` | [≤1 세션·짧게] | 60000 | "짧게" = 세션보다 짧은 유일 앵커(MINUTE) |
| `MAX_deviation_duration_ms` | [reduced scope 최단] | 60000 | "최단" ⇒ MINUTE |
| `MAX_trial_duration_ms` | [exact run 최단] | 60000 | "최단" ⇒ MINUTE |
| `MAX_envelope_review_interval_ms` | [정기 리뷰 주기] | 15552000000 | REVIEW_CYCLE(프로파일 `review_due`와 정합) |
| `MAX_residual_risk_review_interval_ms` | [risk class별] | 15552000000 | REVIEW_CYCLE |
| `MAX_monitoring_suppression_duration_ms` | [최단·자동 재개 금지] | 60000 | "최단" ⇒ MINUTE |
| `MAX_clock_offset_ms` | [범위] | 50 | L4 family posture "수십~수백 ms"의 최단 |
| `MAX_future_timestamp_tolerance_ms` | [범위 작게; 0 강제금지] | 50 | 최단이되 0 아님 |
| `MAX_time_source_precision_ms` | [범위, source class별] | 50 | L4 최단 |
| `MAX_time_source_sequence_gap_ms` | [범위] | 50 | L4 최단 |
| `MAX_critical_input_source_production_delay_ms` | [범위, source class별] | 50 | L4 최단 |
| `MAX_critical_input_transport_and_queue_delay_ms` | [범위] | 50 | L4 최단 |
| `MAX_critical_input_correction_horizon_ms` | [범위, **길 수 있음**] | 86400000 | ⚠ **방향 반전 키**: §4의 "MAX_는 낮은 쪽" 규율이 여기선 fail-open이다(정정 지평을 짧게 잡으면 미도착 정정을 확정으로 오인). 패키지 자신의 "정정 미도착이 지평 축소 아님"에 따라 **긴 쪽**(DAY)을 택함 |
| `MIN_holdover_safety_margin_ms` | [≥ 수백 ms~수 초] | 2000 | floor ⇒ 높은 쪽이되, holdover(5000)를 소진하지 않는 최대 — 기존 값 앵커 `MAX_process_suspension_ms=2000` 채택 |

수치 대역이 제시되어 대역 끝을 그대로 택한 키(재량 아님·기계적): `B_supply_chain_compromise_detect`·
`B_post_trade_change_detect`·`B_statement_coverage_gap_detect` 2000(대역 하단) · `B_evidence_persist` 500 ·
`B_critical_alert_delivery` 5000 · `MAX_pending_external_transfer_age_ms` 30000 ·
`MAX_time_transport_and_queue_uncertainty_ms`·`MAX_clock_domain_conversion_uncertainty_ms`·
`MAX_time_source_disagreement_ms` 50 · `MAX_dsl_evaluation_ms` 10 · `MAX_action_amplification_per_cause` 3 ·
`MIN_time_stabilization_interval_ms` 5000(floor 상단) · `MIN_lease_expiry_fence_ms` 10000(floor 상단).

**floor 방향 무결 실측:** `MIN_lease_expiry_fence_ms`(10000) ≥ `MAX_degraded_lease_holdover_ms`(5000) +
`MAX_process_suspension_ms`(2000) + `MIN_holdover_safety_margin_ms`(2000) = 9000 ✓ (§6-F 요구 부등식).

### 15.7 Patch-0055 (동봉 1) — 적용됨

`tos-spec/src/part-1-foundation/patches/VERIFICATION-PROFILE-002-Patch-0055.md`.
84 bounds 전부(actual+template)에 `applicable_scope`·`review_date` 2필드 신설 → VER-002-001 §6의
7속성 완성(6필드 → 8필드). `limits:`는 flat scalar 구조 유지(§6은 "for every **bound**"). `applicable_scope`는
3규칙 파생(발명 0): 프로파일 자신의 `per X` 인라인 코멘트 verbatim **13** · `measurement_source ==
broker_capability_profile` **4** · 나머지는 프로파일 스코프 상속 `non-live-test` **67**. template은
shape 정본이므로 `TBD`/`null`.

### 15.8 이 승인이 여전히 의미하지 **않는** 것

§13이 그대로 유효하다(§15.5의 P0-3 정정만 반영). 추가로:

- **프로파일은 승인되지 않았다.** 146키에 값이 있어도 프로파일 `status`는 PROPOSED다. VER-002-001 §6의
  "placeholder or undocumented default is not an approved bound"은 **키 단위** 판정이고, 프로파일 단위
  APPROVED는 별개의 더 강한 게이트다.
- **EV-L1은 이 수치를 소비하지 않는다.** §0의 정직한 한계 1 그대로 — 타이밍 임계는 벽시계가 도는
  EV-L2/L3에서 강제된다. 승인은 그 하네스가 쓸 천장을 확정한 것이다.
- **동봉 2(dimension-id 규약)는 미결.** 변형 A/B 결정은 본 승인에 포함되지 않았다.
