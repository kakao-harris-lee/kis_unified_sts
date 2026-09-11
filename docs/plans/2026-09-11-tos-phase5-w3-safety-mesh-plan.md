# TOS Phase 5 W3 계획 — 안전 메시 런타임 owner (spg·wdr·sir·stm 서비스 · deferred 입력 · 래치/용량 owner · HAG 재무장)

- **상위**: Phase 5 계획(`2026-09-10-tos-phase5-recovery-governance-plan.md`) §2 결정 1(1차원=1커밋 · attestation 삭제 + 잔존 키 = 부팅 거부) · 5(4 서비스 같은 형상 · (i) currentness owner (ii) deferred 입력 (iii) Coordinator 전제) · 6(보호 행위·통제 종료·재무장 · HAG) · §4 W3 행 · §8 처분 1(전역 new-risk 래치 + 명시 재무장 · HAG 2인 승인) · 커널 라운드 #2(`2026-09-11-tos-kernel-round-2-mesh-plan.md` · deferred 6 필드 · `False⇒DENIED` 확인 ⑵ 미결).
- **선행**: main `4b72a5cc`(PR #677). 서베이 `scratchpad/w3-survey.md`(2026-09-11).
- **저작**: 세션 모델 단독 · 권한 부여 0 · 실 브로커 송신 0 · EV 상태 변경 0 · **커널 diff 0**(제3 전제조건은 T2 레인 B 관용구 «두 질문» 으로 · Protocol 확장은 커널 라운드 #3 후보).

## 0. 서베이 실측 (요지)

| 항목 | 실측 |
|---|---|
| 17차원 | `compose/_pending_dimensions.py:69` = `MANDATED_DIMENSION_FLOOR`(21) − owned 4 · attestation 4필드 · `owner_identity` 코드 상수 · `context.py:587-594` 2-pass assemble `extra_dimensions` 로 편입 · **잔존 키 부팅 거부 관용구 없음**(`_egress_attestations.py:78,146-154` 에만 존재) |
| 리더 시임 | `currentness/vector.py:190` `CurrentnessAssembler` 가 `DimensionReport` 리더 2개(SAFETY_AUTHORITY·ACTION_FLOW)를 kwarg 로 하드코딩 → `_injected_dimensions` |
| egress attestation 3 | `venue_session_account_facts_current`(W5) · `restrictive_latch_state`·`worst_credible_capacity`(W3) · 용량은 기술적 기록(게이팅 아님 · `test_egress_attestations.py:188` 핀) |
| 커널 메시 | spg 2256 · wdr 2878 · sir 3791 · stm 3935 · protective 1660 · replacement 2364 · hag 2292 — 순수 술어 · 헤르메틱 테스트 14~18파일씩 · `tos_runtime` 에서 `tos.hag` import 0 |
| Coordinator | Protocol 두 메서드로 닫힘(`engine/core.py:136`) · 제3 질문은 `live_scope_authorized` 내부(T2 레인 B 관용구) · 생성 `_engine_wiring.py:391-421` |
| deferred 6 | 커널 필드 존재 · 런타임 공급 0 · UNKNOWN {4,5,7,8,9,10} 핀 = T3 e2e + 커널 4파일 |
| 래치 | `inbox.py:148` 싱글턴 · 운영자 문 `_types.py:230 clear_new_risk_halt(latched_evidence_seq, operator_attestation)` = **1인 자유텍스트(sha256 기록)** · HAG 정족수 결속 0 · 기계 핀 `test_no_direct_latch_clear.py` |
| 예산 | `_wiring.py` 1087(성장 금지) · `driver.py` 974 · `context.py` 762 · 후결선 관용구 `_recovery_wiring`/`_release_wiring`(root.py 253·259) |

## 1. 범위 — W3 는 두 서브웨이브

| **W3.1 (이 계획 · 즉시)** | **W3.2 (후속 · 별도 계획)** |
|---|---|
| 4 안전 메시 서비스(spg·wdr·sir·stm) · deferred **4·7·8·9·10** 공급(5 는 확인 ③) · Coordinator 제3 질문 · 차원 owner **9/17**: SAFETY_ENVELOPE_PROFILE·DEVIATION·INCIDENT·MONITORING(4 서비스) · RECOVERY(W1 barrier) · TRADING_APPROVAL(iap) · CURRENTNESS_POLICY(cur) · EGRESS_IDENTITY(egress) · ENVIRONMENT_SCOPE(brokercap) · `restrictive_latch_state`·`worst_credible_capacity` owner · `ReArmWorkflow`(HAG 2인) · `_pending_dimensions` 잔존 키 부팅 거부 관용구 | 나머지 8차원(AGGREGATE_RISK·CONSTRAINT·CONSTRUCTION·CONTEXT·CRITICAL_INPUT·DECISION_PROOF_INTENT·POST_TRADE·RELEASE) · `ProtectiveActionService`(protective+replacement) · `ControlledShutdown`(sir) · G-1/G-2 owner · `_pending_dimensions` 17→0 완결 |

제외(공통): 커널 diff · W5 venue/session · 대시보드 · 실 브로커.

## 2. 결정

1. **공유 포트** `tos_runtime/safety/ports.py`: `SafetyMeshService` Protocol — `identity: str`(owner_identity 스탬프) · `dimension_key: DimensionKey` · `dimension_report() -> DimensionReport | None`(currentness owner · `vector.py:107` 형상) · `clear() -> bool | None`(deferred 입력 극성: `True` 양성 · `False` 명시 음성 · `None` 불명) · `describe() -> Mapping[str, Any]`(evidence 용 · 비밀 0). 네 서비스는 이 하나의 형상. 판정 저작 0 — 각 `clear()`/`dimension_report()` 는 커널 술어 결과의 결합만.
2. **서비스별 입력·술어**(정책 문서 = YAML named-TBD null ⇒ 부팅 거부 · `owner_identity` 는 서비스 identity):
   - `SafetyProfileService`(spg · item 7 · SAFETY_ENVELOPE_PROFILE): `hard_envelope.yaml`+`runtime_profile.yaml`+`activation.yaml` → `HardSafetyEnvelope`/`RuntimeSafetyProfile`/`ActivationRecord` → `profile_within_envelope` ∧ `hard_and_runtime_versions_match` ∧ `activation_atomic` 양성 ∧ `expiry_suspends_new_risk` 미발동 ⇒ `clear=True` · 만료/불일치 ⇒ `False` · 문서 부재 ⇒ 부팅 거부(None 아님) · `dimension_report.bound_generation` = `active_envelope_generation`.
   - `DeviationService`(wdr · item 8 · DEVIATION): `deviations.yaml`(활성 편차 집합 · 빈 집합 허용 — **명시적 빈 리스트**, null 아님) → `DeviationClassification`/`DeviationScope` → `combined_set_no_permissive_union` ∧ ¬`unresolved_is_non_waivable` 위반 ∧ `revocation_dominates_send` 양성 ⇒ True · 미해소 편차 존재 ⇒ False.
   - `IncidentService`(sir · item 9 · INCIDENT): `incidents.yaml`(활성 집합 · 명시적 빈 리스트 허용) → `ActiveSetMember` → `active_set_is_canonical_union` ∧ ¬`dominating_open_incident_present` ∧ `restriction_dominates_send` ⇒ True · 열린 지배 인시던트 ⇒ False.
   - `MonitoringService`(stm · item 10 · MONITORING): `monitor_coverage.yaml`(커버리지 매니페스트 · 항목 ≥1) + 평가 입력은 **런타임 자기 관측**(evidence store tip 신선도 · time_service `health_state` · inbox 미소비 수 — 각 `MonitorEvaluation`) → `critical_coverage_complete_or_gap` ∧ `conformance_requires_complete_current_valid`=CONFORMING ⇒ True · RESTRICTED/NON_CONFORMING ⇒ False · UNKNOWN(gap) ⇒ **None**(`unknown_is_restrictive` — 커널이 UNKNOWN 으로 거부). alert 발행 = evidence `STM_ALERT`(전달 채널은 레거시 소관 · §2 결정 8).
3. **currentness 편입**: `CurrentnessAssembler` 를 리더 **맵**으로 일반화 — `dimension_readers: Mapping[DimensionKey, Callable[[], DimensionReport | None]]`(기존 2개는 맵 항목으로 이전 · 동작 불변 핀) · 4 서비스 + RECOVERY(barrier verdict) + TRADING_APPROVAL(iap `decision_current`) + CURRENTNESS_POLICY(`policy_covers_mandated_dimensions`) + EGRESS_IDENTITY(egress 술어 over 좌표) + ENVIRONMENT_SCOPE(`environment_binding_ok` over 활성 스코프) 리더 등록 · `_pending_dimensions` 에서 그 9키 **삭제** + 설정에 잔존 시 `PendingDimensionConfigError`(관용구 이식 · 1차원=1커밋) · `currentness_dimensions.example.yaml` 8블록만 남김 · conftest 픽스처 동기.
4. **deferred 입력 공급**: `compose/context.py` 에 `_deferred_mesh_fields()` → dict 5키(`safety_authority_epoch_current` ← `SafetyAuthorityEpochService.epoch_current(bound)` · `safety_profile_current`/`deviation_clear`/`incident_clear`/`monitoring_clear` ← 각 서비스 `clear()`) 를 `send_boundary_context(**…)` 로 스프레드(`_egress_gate_stand_in_fields` 관용구) · `live_scope_valid` 는 **None 유지**(확인 ③) · 합성 경로는 NON_BROKER_SYNTHETIC ⇒ N/A 불변(커널) · T3 e2e 의 UNKNOWN 집합은 {5} 로 축소되어야 하며(4·7·8·9·10 SATISFIED · 스코프 MOCK 정직 deny 는 item 5 + item 6/12 로 유지) 그 테스트를 **정직하게 갱신**.
5. **Coordinator 제3 질문**(결정 5 (iii) · 커널 diff 0): `RuntimeCoordinatorPreconditions` 에 `safety_mesh: Sequence[SafetyMeshService] = ()` 주입 · `live_scope_authorized` 는 기존 ①∧(②∨admission) 에 **∧ mesh_clear** 추가 — `mesh_clear = all(s.clear() is True for s in safety_mesh)`(빈 시퀀스 ⇒ **False** · 비공허) · 단 합성(non-broker) 경로는 mesh 미결선 시 기존과 동일해야 하므로 mesh 는 **broker-reaching 경로에만 요구**(②가 True 인 합성은 mesh 없이 통과 — 합성 e2e 불변) · 사유는 evidence `COORDINATOR_MESH_HELD`(어느 서비스가 비양성인지).
6. **래치/용량 owner**: `tos_runtime/safety/latch.py` `RestrictiveLatchOwner.state() -> RestrictiveLatchState` = `new_risk_halt` 래치(inbox) ∨ `IncidentService` 지배 인시던트 ∨ spg 만료 ⇒ 비-CLEAR · `CapacityOwner.worst_credible_capacity()` = RCL 투영 `outstanding_count(scope)` 기반(기술적 기록 — 게이팅 아님 유지) · `_egress_attestations` 에서 두 키 삭제 + 잔존 시 부팅 거부(관용구 그대로) · `EgressAttestations` 는 `venue_session_account_facts_current` 1필드만(W5 까지) · 커널 docstring 재계수 링크 테스트(라운드 #2 LOW-3)를 **3→1** 로 갱신(커널 docstring 문언은 커널 diff 라 `tos.egressgw.__doc__` 대조 부분은 «attested 필드 ⊆ docstring 명명» 방향만 유지 — 커널 라운드 #3 이월 기록).
7. **ReArmWorkflow(HAG 2인)**: `tos_runtime/safety/rearm.py` — `clear_new_risk_halt` 의 자유텍스트 attestation 을 **`approvals/rearm/<latched_evidence_seq>.yaml` 2인 결정 파일**로 대체: `RoleAssignment`(`REARM_APPROVER` ×2 · 서로 다른 principal) · `QuorumRule`(2/2) · 커널 `dual_control_effective_distinct` ∧ `quorum_independence_satisfied` ∧ `approval_binding_exact`(latched seq 결속) ∧ `approval_set_single_use` ∧ `no_automatic_rearm`(자동 경로 0 — 파일 부재 ⇒ 거부) · evidence 선기록 `REARM_APPROVED` → clear · 거부 `REARM_REFUSED`(사유) · `_types.py::clear_new_risk_halt` 시그니처는 `(latched_evidence_seq, approvals_dir)` 로 · `test_no_direct_latch_clear.py` 허용 파일 유지(스토리지 clear 호출 지점은 `_types.py` 1곳 그대로). break-glass 는 W3.2.
8. **결선**: `compose/_safety_wiring.py`(신설) — 서비스 4 + 래치/용량 owner 생성 · `apply_safety_wiring(runtime, config_dir, …)` 후결선 관용구 **불가**(context resolver·assembler 는 `_finalize` 전에 필요) ⇒ `_boot_services`/`_build_risk_and_currentness` 단계에서 호출되되 `_wiring.py` 는 **1호출 + import 만** · 설정 파일 5종 `safety_{envelope,profile,activation,deviations,incidents}.yaml` + `monitor_coverage.yaml`(named-TBD null · 예시) · boot-integrity 에 digest 행.
9. 값형 설정 전부 named-TBD null → 운영자 제안표(런북 `docs/runbooks/tos-safety-mesh.md`) · 테스트 픽스처만 실값.

## 3. 기각 대안

- 4 서비스를 하나로 → 세대·scope 독립(§3 상위). · Coordinator Protocol 확장 → 커널 diff(라운드 #3). · deferred `False` 를 None 으로 접기 → 명시 음성 손실(확인 ⑵ 미결이나 커널이 이미 DENIED). · 17→0 을 한 번에 → 8차원은 다른 패키지 owner(W3.2). · attestation 을 서비스가 읽어 그대로 반환 → 판정 저작 금지 위반(서비스는 술어만).

## 4. 레인 (파일 소유 1레인 · 병렬)

| 레인 | 파일 | 내용 |
|---|---|---|
| **W3-a1** | `safety/{profile,deviation}.py` · 설정 3+1 · 테스트 | spg·wdr 서비스(결정 2) |
| **W3-a2** | `safety/{incident,monitoring}.py` · 설정 1+1 · 테스트 | sir·stm 서비스(결정 2) · `STM_ALERT` evidence |
| **W3-b** | `currentness/vector.py`(리더 맵) · `compose/{_pending_dimensions,_currentness_wiring,context,_preconditions,_engine_wiring,_safety_wiring}.py` · `_wiring.py` 1호출 · conftest · T3 e2e 갱신 | 결정 3·4·5·8 — 서비스는 포트로 결선(a1/a2 착지 전엔 테스트 fake) · 9차원 삭제(1차원=1커밋) |
| **W3-c** | `safety/{latch,rearm}.py` · `compose/{_egress_attestations,_types}.py` · `authority/` approvals 읽기 재사용 · 테스트 | 결정 6·7 |
| 리뷰 | — | a1/a2/c 착지 후 1회 · b 통합 후 재심 |

공유 파일 규칙: `_wiring.py`·`root.py` 는 b 만 · `_types.py` 는 c 만 · `context.py` 는 b 만 · conftest 는 b 만(c 의 egress 2키 삭제도 b 가 conftest 반영 — c 는 자기 테스트 픽스처 사용).

## 5. 종료 조건

- 런타임·커널 green(«N passed» 인용) · 커널 diff 0 · ruff/black/mypy 0 · firewall · lint-imports · budget(`_wiring.py` ≤1087 · 신규 모듈 ≤1000 · 함수 ≤100) · contract/completion/spec GREEN(bound 무접촉) · EV 0.
- `_pending_dimensions` **17→8** · `_egress_attestations` **3→1** · deferred 공급 5(4·7·8·9·10) · T3 e2e UNKNOWN 집합 정직 갱신({5}) · 합성 e2e 불변.
- 뮤테이션 red: M1 서비스 `clear()` 상수 True(술어 미호출) · M2 리더 맵에서 차원 하나 누락 ⇒ `vector_complete` False · M3 잔존 attestation 키 허용 · M4 mesh 비공허 제거(빈 시퀀스 True) · M5 2인 승인 1인으로 · M6 rearm 파일 없이 clear · M7 래치 owner 가 inbox 무시.
- 독립 리뷰 approve · 판정 PR 코멘트.

## 6. 운영자 확인 지점

1. W3 서브웨이브 분할(W3.1/W3.2) 수용.
2. (라운드 #2 ⑵) deferred `False ⇒ DENIED` 극성 — 이 계획은 커널 현행을 따름.
3. **item 5 `live_scope_valid`** — 비-live MOCK 송신에서 «valid live scope» 의 정직한 값: (a) None 유지(UNKNOWN ⇒ MOCK 은 item 5 로 계속 deny · Phase 6 라이브 인가 전까지) · (b) non-live admission 통과 시 True(«이 송신의 live-scope 질문은 non-live 로 확정됨»). 계획 기본 = **(a)**.
4. 정책 문서 값(envelope·profile·activation·coverage) 제안표 → 승인 전 null.
5. 재무장 2인 principal 의 custody/approvals 배치(운영 서버).
