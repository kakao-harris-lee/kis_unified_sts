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
3. **generation 정직**: 실 generation 없는 차원(CONSTRUCTION·CONSTRAINT·POST_TRADE·RELEASE)은 ~~`bound_generation=None`~~ → **정정(d1 실측 · 2026-09-11)**: 커널 `cur.predicates.dimension_positively_established` 는 `bound_generation=None` 을 «좌표 부재» 로 읽어 차원을 영구 비성립시킨다(실 회귀: 첫 송신도 vector 미완성으로 transport 도달 0). 따라서 generation 사실이 없는 차원은 **명시적 `bound_generation=0`**(RECOVERY/TRADING_APPROVAL 선례) + docstring «no generation fact exists — deliberately 0, not a counter» · `restrictive_floor=0` 명시. `None` 은 «아직 평가 불가(셀 미채움)» 에만 쓴다.
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

## 7. 실행 결과 — W3.2 착지 (2026-09-12 · 브랜치 `feat/tos-phase5-w32-remaining-owners` · main `bcf22f65` 기점)

| 레인 | 커밋 | 내용 |
|---|---|---|
| 계획 | `55a1ef2e`·`6a043a26` | 본 문서 · §2.3 정정(`bound_generation=None` 은 커널이 좌표 부재로 읽음 → 세대 없는 차원은 명시적 `0`, d1 실측 회귀) |
| d2 | `acbe7db7` | `safety/protective.py` `ProtectiveActionService`(verdict-only · 결정 8) — `derestriction_admissible` 를 실 사실 2(time-health TRUSTED · item 16 래치)+incident clearance 로 호출, §8.5 나머지 3 conjunct 는 원천 없어 None(정직하게 항상 False) · `protective_capacity_exhausted(None, None)` 은 프로필 로더·재시도 예산 부재로 정직하게 항상 True · `protective_classification`·`replacement` 술어 미호출(`UNEVALUATED_PROTECTIVE_FACTS` 공시) · `PROTECTIVE_VERDICT` evidence 호출당 1 · 실행 경로 0(transport/RCL 포트 미주입) · `risk/flow.py` `protective_classification_digest_provider` 선택 인자 · `_safety_wiring.py` 틱 스냅샷 공유 생성 · 24 테스트 |
| d3 | `899a7b85` | `safety/shutdown.py` `ControlledShutdown`(결정 9) — ADR-002-027 `SHUTDOWN_STEP_KINDS` 6단계(deny-before-stop 래치 · RCL 의무 이전 · inbox/rcl/evidence 순서 닫기 · custody no-op) 각 완료를 실 결과에서 · `IncidentRecoveryHandoffPackage` evidence(barrier closed/accepted 는 None 유지 → `recovery_handoff_requires_accepted_barrier` 정직 False) · `obligations_survive_shutdown` 미호출 공시 · `_types.py` `ComposedRuntime.shutdown()` · 10 단위+3 e2e |
| d1 | `03be99b4` | 6 차원 owner(결정 2~6): AGGREGATE_RISK(step 6 `last_decision is GRANT` · 실 `decision_generation`) · CONSTRUCTION(step 2 CONFORMANT×2+`no_silent_widening_ok` · gen 0) · CONSTRAINT(step 3 `VerdictRecorder` ADMIT · `account_constraint_conservative` 미호출 공시) · DECISION_PROOF_INTENT(step 13 recorder ADMIT · 자기 proof 원천은 순환이라 기각 기록) · POST_TRADE(`FinalityReleaseConsumer.latest_release_is_conflict_free` — HELD/NOT_CORROBORATED 만 False) · RELEASE(STAGE B 프로브 · 운영자 설정 기반 공시) · `_pending_dimensions` **9→3**(CONTEXT·CRITICAL_INPUT·EGRESS_IDENTITY) |
| d1 후속 | `d1dcc363`·`b92001fe` | protective digest 를 `RecordingActionFlowGovernor` 생성에 결선(실 admitted attempt 후 non-None 핀) · `_currentness_wiring.py` 1081→313 순수 이동(`compose/_dimension_readers.py` 885 신설 · `_build_risk_and_currentness` 101→89 · 예산 등재 42→40) |
| 처분 | `4b42f3ae` | M1: `protective.py` 호출 지점에 부재 원천 2(`ProtectiveCapacityProfile` 로더 · 재시도 예산 트래커)와 귀결(둘 다 생길 때까지 정직 `capacity_exhausted=True`) 공시 주석 + `verdict.unevaluated` 와 `PROTECTIVE_VERDICT` evidence payload 양쪽에 두 이름·`capacity_exhausted=True` 를 핀하는 테스트 1(stand-in 상수 도입 0 · 새 표면 0) · L1: 두 테스트 모듈 docstring 을 자립 문언으로(이연 사슬 `test_shutdown→test_protective→conftest` 해소) |

- **독립 리뷰(sonnet · 저자와 다른 패스) — BLOCKER 0 · HIGH 0 · MEDIUM 1 · LOW 1 · 머지 가능.** 확인: 뮤테이션 M1(리더 recorder 무시 → 3 red) · M3(evidence 먼저 닫기 → 2 red) · M4(digest provider None → 핀 red) · M5(latch/incident 변화에 digest 변동 · 원본 3사실 프리이미지 포함) · M6 상수 스윕(`*_only` 5 bool 은 커널 기본값 · 미확보 사실 5 전부 None) · `bound_generation` 6 리더 중 AGGREGATE_RISK 만 실 세대, 5 는 명시 `0` · 순수 이동 라인 diff(docstring/import/`__all__` 만) · pending 정확히 3 · `shutdown()` 프로덕션 호출부 0(CLI 미결선 공시 일치) · d3 stash 사고 최종 트리 손상 0. 지적: **M1** `protective.py:299` `protective_capacity_exhausted(None, budget_remaining=None)` 하드코딩에 마커 없음 → 호출 지점 공시 주석(부재 원천 2 명시) + 정직 상태 핀 테스트(상수 stand-in 도입 금지) · **L1** 테스트 docstring 순환 인용 → 자립 문언. 확인 불가: ADR-002-027 원문 미대조(커널 코드만) · G-1/G-2 는 범위 밖.
- **재심 approve**(`4b42f3ae` · BLOCKER/HIGH/MEDIUM/LOW 0): 공시 주석은 부재 원천 2 를 이름으로 지목 · 호출 무변경(stand-in 0) · 신규 핀 테스트 비공허 — `UNEVALUATED_PROTECTIVE_FACTS` 에서 두 이름 제거 뮤테이션에 신규+기존 테스트 즉시 red(커널 `protective/predicates.py:652-657` 은 `profile is None` 이면 예산값 무관 exhausted 라 `budget_remaining=0` 뮤턴트는 등가) · docstring 이연 사슬 해소 · `tests/safety` 160 passed.
- **게이트(처분 후)**: 런타임 **1445** · 커널 **9433** · 커널 diff 0 · ruff/black/mypy 0 · firewall PASS · lint-imports 3/0 · budget 0(40 등재) · completion GREEN.
- **종료 조건 대비**: `_pending_dimensions` **9→3**(계획 2~3 — EGRESS_IDENTITY 는 3 술어 원천 미확보로 attestation 유지) · `PROTECTIVE_VERDICT` evidence + afg digest 실 공급 ✓ · `shutdown()` step 증명 6 + handoff evidence ✓ · T3 e2e 불변 ✓ · M1~M5 red ✓(M2 는 d1 테스트 `NOT_CORROBORATED` 경계로 핀).
- **정직 상태·이월**: ProtectiveAction 은 판정만(집행 = transport 후속 · 확인 ④) · `derestriction_admissible` 3 conjunct 원천 부재 → 항상 False · 용량 소진 술어 항상 True(프로필 로더·예산 트래커 부재) · `shutdown()` CLI 미결선(운영자 확인) · CONTEXT/CRITICAL_INPUT 은 capsule 웨이브까지 attestation(확인 ①) · d4(G-1/G-2) 는 확인 ②③ 후 조건부 · 커널 docstring 재계수는 라운드 #3.
- **교훈**: venv editable `.pth` 는 워크트리 하나만 가리킨다 — 레인 시작 시 `tos_runtime.__file__` 선확인(`pip install -e ./tos` 와 `-e ./tos/runtime --no-deps` 는 분리 설치 · 한 호출에 묶으면 pip 해석 충돌) · 계획 §2.3 은 커널 `dimension_positively_established` 의 None 해석을 실측 전에 잘못 가정 — 실행 레인의 회귀가 계획을 정정(문서에 정정 커밋으로 남김) · d3 가 공유 트리에서 `git stash` 실행(규칙 위반) → 손상 0 이었으나 재발 금지 · 리뷰어의 editable `.pth` 재지정은 다른 레인 임포트를 바꾸므로 종료 후 즉시 복구 + 다음 레인은 임포트 경로 선확인.
