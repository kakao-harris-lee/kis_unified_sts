# TOS Phase 5 W3.2 계획 — 잔여 차원 owner · 보호 행위 verdict 표면 · 통제 종료 · G-1/G-2 (조건부)

- **상위**: W3 계획(`2026-09-11-tos-phase5-w3-safety-mesh-plan.md`) §1 W3.2 열 · Phase 5 계획 §2 결정 1·6·7 · §4 W3 행 · 커널 라운드 #1 계획 `:111-112`(G-1/G-2 는 운영자 결정 항목).
- **선행**: W3.1 MERGED → main `bcf22f65`(PR #680 · 2026-09-11 · 17→**9**(EGRESS_IDENTITY 는 리뷰 M4 로 attestation 복귀) · 3→1 · deferred 4/7/8/9/10 공급 · 런타임 1369). 서베이 `scratchpad/w32-survey.md`(2026-09-11 · 착지 전 스냅샷 `07ff6dca` 기준 — pending 8 로 기술된 곳은 9 로 읽는다).
- **W3.1 이월(이 계획이 이어받는 것)**: EGRESS_IDENTITY 나머지 2 술어(`stale_principal_structurally_rejected` · `egress_generation_monotonic` — `ActiveEgressPrincipalSet`·이전 이벤트 원천 필요) · `DeviationService.combined_within_envelope` attestation(spg 결선 주입점) · sir `restriction_dominates_send`(per-send 세대) · stm `unknown_is_restrictive` 1/7축 · spg `mixed_versions_present` 카디널리티.
- **저작**: 세션 모델 단독 · 커널 diff 0 · 권한 부여 0 · 실 브로커 송신 0 · EV 상태 변경 0.

## 0. 서베이 실측 (요지)

| 차원 | 정직한 런타임 원천 | generation | 판정 |
|---|---|---|---|
| AGGREGATE_RISK | step 6 `RecordingAggregateRiskService.last_decision`(`context.py:175-185`) — 커널 `are` 술어 4종 이미 호출 | `decision_generation` 실값 | 리더 가능 · **하위 3입력(numerically_safe·valuation_ok·all_fields_attributed)은 여전히 attestation**(`_risk_attestations.py:116-118`) — 차원 docstring 에 공시 |
| CONSTRUCTION | step 2 `CandidateConstruction`(`records.py:341-351` · ioc verdict 3종 보유 · denied 면 전부 None) | 없음(compose 리터럴 `1`) | 리더 가능 · generation `None` 명시 |
| CONSTRAINT | step 3 `VenueConstraintStage`(`order_shape_admissible` 호출) — recorder 미부착 | 없음 | 리더 가능 · **부분**(`account_constraint_conservative` 호출자 0 — EGRESS_IDENTITY 공시 관용구) |
| DECISION_PROOF_INTENT | step 12 `AttemptBindVerificationStage`(`exact_binding_holds` 매 attempt) · `proof.result` | `committed_revision.commit_index` | 리더 가능 · TRADING_APPROVAL(step 4)과 축 분리 |
| POST_TRADE | W2-R `FinalityReleaseConsumer` 직전 소비 결과 | 없음 | 리더 가능하나 **send 이후 축** — «이 스코프의 최근 post-trade 처분이 HELD/RELEASED 인가» 로만 정직 |
| RELEASE | 부팅 `release_admitted`(`software_deployment_ok_verdict`) | 없음 | 리더 가능 · `admission_result` 는 정적 설정(자인 `release/config.py:4-6`) 공시 |
| **CONTEXT · CRITICAL_INPUT** | **없음** — `tos.capsule` 런타임 import 0 · `AdmittedPriceObservation` 프로덕션 생산자 0 · `capsule_terminus_fields` 자인 stand-in | — | **리더 불가 → attestation 유지** |
| ProtectiveAction | `tos.protective`/`replacement` 런타임 import 0 · cancel/replace 송신 경로 0(mock 어댑터 `send_once` 만) | — | **verdict-only 표면** |
| ControlledShutdown | `ComposedRuntime` 에 close/stop 0 · 자원 close 4곳 · 래치가 deny-before-stop 을 실제 수행 · W1 barrier verdict = sbr 주입 좌표 | — | 부분 구동 가능(①deny_before_stop ②자원 close step ③handoff barrier) |
| G-1/G-2 | `time/service.py:449` 스냅샷에 wall_clock/suspension 미기입 · `:258` 리터럴 · 슬라이스 #1 «값 비노출» 결정(`sources.py:123-131`) | — | **운영자 결정 선행**(라운드 #1 `:111-112`) |

## 1. 범위

| 포함 | 제외 |
|---|---|
| 6차원 리더(AGGREGATE_RISK·CONSTRUCTION·CONSTRAINT·DECISION_PROOF_INTENT·POST_TRADE·RELEASE) → `_pending_dimensions` **9→3**(EGRESS_IDENTITY 는 3 술어 전부 실 원천 시에만 교체 — d1 에서 시도, 불가 시 attestation 유지·공시) · `ProtectiveActionService`(verdict-only · evidence + afg `protective_classification_digest` 실 공급) · `ControlledShutdown`(`ComposedRuntime.shutdown()` · 정직하게 증명 가능한 step 만) · **조건부** G-1/G-2(확인 ②③ 후) | CONTEXT·CRITICAL_INPUT(capsule 런타임 = 별도 웨이브 · attestation 유지 · 사유 공시) · cancel/replace 송신(어댑터 후속) · 커널 diff · W5 |

## 2. 결정

1. **리더 관용구 = lane b 그대로**(`_currentness_wiring.py:482 _build_dimension_readers` · `(owner_identity, reader)` · late-bound cell · `_READER_OWNED_DIMENSION_KEYS` + stale 검사 · 테스트 3형). 1차원=1커밋.
2. **step 3·12 recorder 부착**: 기존 `VerdictRecorder`(step 4/9)를 step 3(venue)·step 12(bind verification)에 동일 관용구로 부착 → CONSTRAINT·DECISION_PROOF_INTENT 리더는 recorder `last_verdict` 를 읽음(판정 저작 0). `_wiring.py` 는 성장 0 목표(recorder 생성은 `_build_realized_stages` 안 1줄씩 · 초과 시 `_stages_wiring.py` 분리).
3. **generation 정직**: 실 generation 없는 차원(CONSTRUCTION·CONSTRAINT·POST_TRADE·RELEASE)은 `bound_generation=None` + docstring «no generation fact exists — deliberately None» · `restrictive_floor=0` 명시. `DimensionReport.bound_generation` 은 이미 `int | None`.
4. **AGGREGATE_RISK 공시**: `positively_established = last_decision.result is ADMIT`(커널 verdict) 이되 docstring/evidence 에 «numerically_safe·valuation_ok·all_fields_attributed 는 `_risk_attestations` attestation» 명시 · 그 3키의 owner 는 별도(Phase 6 후보) — 이 차원은 «verdict owner» 이지 «입력 owner» 는 아님을 기록.
5. **POST_TRADE 축**: 리더는 `FinalityReleaseConsumer` 가 노출하는 스코프 단위 최근 `ReleaseOutcome`(HELD/RELEASED/none) 을 읽어 `positively_established = (outcome is not HELD-with-conflict)` — **아님**. 정직 정의: «직전 attempt 의 post-trade 처분이 기록됐고(evidence 존재) 충돌(orphan/mismatch) 사유가 없다». 미기록(첫 attempt) ⇒ `None`(차원 부재 ⇒ vector 미완성 ⇒ 첫 송신 불가?) — **아니다**: 첫 attempt 는 post-trade 사실이 없는 것이 정상. 따라서 «충돌 사유 부재» 를 `True` 로, 충돌 존재를 `False` 로, consumer 미결선을 `None` 으로. 근거를 docstring 에.
6. **RELEASE**: `positively_established = runtime.release_admitted`(부팅 verdict · 프로세스 수명 상수) · `admission_result` 정적 설정임을 공시.
7. **CONTEXT·CRITICAL_INPUT**: attestation 유지 · `_pending_dimensions` 주석에 «capsule 런타임(입력 캡슐 체인) 미착지 — 별도 웨이브» · 운영자 확인 ①로 등재(Phase 6 앞에 «capsule 웨이브» 삽입 여부).
8. **`ProtectiveActionService`**(`safety/protective.py`): 입력 = 래치 상태(`RestrictiveLatchOwner`) · 인시던트 clear · time health · RCL 투영 → `derestriction_admissible(DeRestrictionInputs(...))` · `protective_capacity_exhausted` · `protective_classification(...)` 호출(affirmative `bool|None` 필드는 실 원천 있는 것만 채우고 나머지 None — 공시). 출력 = evidence `PROTECTIVE_VERDICT` + afg 입력 `protective_classification_digest`(현재 `flow.py:389-390` None) 실 공급. **집행 경로 0**(cancel/replace 어댑터 부재) 을 docstring·evidence 에 명시. `mode_rank` 공급자 없음 ⇒ `mode_permits_protective` 미호출(공시).
9. **`ControlledShutdown`**(`safety/shutdown.py` + `ComposedRuntime.shutdown()`): `ControlledShutdownProcedure` 를 런타임이 실제 수행하는 step 으로만 구성 — ① deny_before_stop(new-risk 래치 set + evidence) ② inbox close ③ rcl log close ④ evidence store close(마지막 · 그 전 step 의 evidence 기록 후) ⑤ custody close · 각 step `completed` 는 close 반환/예외로 · `step_completion_proven` · `controlled_shutdown_not_broker_finality(procedure)`(금지 7항 = 절차 레코드에 선언) · handoff 패키지에 W1 barrier verdict → `recovery_handoff_requires_accepted_barrier`. `OngoingSafetyObligation` 은 RCL 미해소 예약(POTENTIALLY_LIVE 등)을 evidence 로 이전(`transferred_with_owner_and_evidence`). 재무장/재기동은 W1 barrier 소관 그대로. `run_once` 후 `shutdown()` 호출은 CLI 소관(후속).
10. **G-1/G-2 조건부 레인**: 확인 ②(«값 비노출» 개정 — 벽시계 값·서스펜션 ms 를 스냅샷에 싣기) · 확인 ③(G-2 트리거 발행자 변경) 승인 시에만 레인 d4 착수 · 미승인 시 이 계획에서 제외·기록.

## 3. 기각 대안

- CONTEXT/CRITICAL_INPUT 에 «설정 리더» → 판정 저작(팬텀). · ProtectiveAction 을 어댑터에 cancel 추가로 집행 → transport 계획 후속(CANCEL_REPLACE tuple 만 등재). · POST_TRADE 를 «proof 존재» 로 established → 첫 attempt 를 영구 차단. · `ComposedRuntime.shutdown()` 없이 프로세스 종료 → step 증명 0.

## 4. 레인

| 레인 | 파일 | 내용 |
|---|---|---|
| d1 | `_currentness_wiring.py` · `_pending_dimensions.py` · `_wiring.py`(recorder 2줄) · `context.py`(recorder 필드) · 예시 yaml · conftest · `test_pending_dimensions` · `test_compose_root`(RELEASE 소재 테스트 → 다른 차원으로) | 6 리더 · 8→2 |
| d2 | `safety/protective.py` · `risk/flow.py`(digest 공급 지점만) · `_safety_wiring.py`(생성 1) · 테스트 | 결정 8 |
| d3 | `safety/shutdown.py` · `_types.py`(`shutdown()`) · 테스트 | 결정 9 |
| d4(조건부) | `time/service.py` · `time/sources.py` · `currentness/proof.py` · `authority/iap.py` 소비 | 결정 10 |

## 5. 종료 조건

- 런타임·커널 green · 커널 diff 0 · 게이트 전부 · `_pending_dimensions` **2~3**(CONTEXT·CRITICAL_INPUT 확정 · EGRESS_IDENTITY 는 3 술어 원천 확보 여부에 따라) · `PROTECTIVE_VERDICT` evidence + afg digest 실 공급 · `shutdown()` 이 step 증명·handoff 패키지 evidence 생산 · T3 e2e 불변({5}+item 12).
- 뮤테이션: M1 리더가 recorder 미읽고 True · M2 POST_TRADE 첫 attempt 를 False/None 으로 · M3 shutdown 이 evidence store 를 먼저 닫음 · M4 handoff 가 barrier 없이 accepted · M5 protective digest 상수.
- 독립 리뷰 approve · 판정 PR 코멘트.

## 6. 운영자 확인 지점

1. CONTEXT·CRITICAL_INPUT 은 capsule 런타임 웨이브까지 attestation 유지(17→2 종착) — Phase 6 앞 «capsule 웨이브» 삽입 여부.
2. **G-1**: 슬라이스 #1 «벽시계 값 비노출» 결정 개정(값을 스냅샷에 싣고 서스펜션 ms 실측) — 승인/보류.
3. **G-2**: item 16 보존 의무 트리거를 살리는 발행자 변경 — 승인/보류.
4. ProtectiveAction 집행 경로(cancel/replace 어댑터)는 transport 후속 슬라이스로 — 순서 확인.
