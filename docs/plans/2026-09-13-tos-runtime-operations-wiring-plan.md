# TOS 런타임 운영 결선 웨이브 계획 — G-1 결선 · nontrade 엔진 경로 · 운영 CLI(`rearm`·`ack-alert`·`nontrade-eval`) · 승인값 실파일 · `run` 차단 목록 정본화

- **상위**: Phase 5 계획 §11 처분(2026-09-12 · 결정 2 «라운드 #3 → 엔트리포인트 웨이브(G-1 결선 포함)» · 결정 3 G-1 승인 «TRUSTED 게이트 뒤 노출 + `wall_clock_observation` 기입» · 결정 11 캘린더 값 채택 · 결정 19 ack workflow 예 · 11.5) · 커널 라운드 #3 계획 §2.2(d)·§6 ⑤(드라이버 래치 · nontrade 엔진 경로 결선은 엔트리포인트 웨이브) · W5 계획 §6 ①⑧ · W4 계획 §7 정직 상태(`compose_paper_runtime` 프로덕션 호출부 0) · ADR-002-028 :159/:187/:191/:388(확인은 권한·해소·재무장이 아니다) · ADR-002-010 §10(용량은 rcl).
- **선행**: 커널 라운드 #3 MERGED → main `3142b700`. 서베이 `scratchpad/ep-survey-{entry,wiring}.md`(2026-09-13 · `file:line`).
- **저작**: 세션 모델 단독 · **커널 diff 0** · 권한 부여 0 · 실 브로커 송신 0 · EV 상태 변경 0 · bound 문서 무접촉.
- **브랜치**: `feat/tos-runtime-entrypoint`(워크트리 `../kis_unified_sts-entry` · main `3142b700` 기점).

## 0. 서베이 실측 (요지)

| 항목 | 실측 | 함의 |
|---|---|---|
| `run` | `main()` 은 `Args` 파싱 후 `return 0`(`cli.py:404-419`) · `compose_paper_runtime` 의 프로덕션 원천 없는 인자 3: `construction: ConstructionConfig` · `aggregate_risk_inputs_provider` · `action_flow_inputs_provider`(`root.py:135-157`) · `ConstructionConfig` 의 커널 필드는 **발행 아티팩트**(`VenueConstraintPolicy/Snapshot`·`OrderAdmissibilityDecision` 을 픽스처가 `.issue()` 로 손 발행 · `_fixtures.py:432-471`) · Order Construction Policy 미비준(`root.py:49-57`) · 틱 원천 0(`DECISION_TICK` 생산자는 픽스처만) · `tos.marketfeed` 런타임 어댑터 0 | «YAML→발행 아티팩트 로더» 는 stand-in 을 설정으로 굳히는 판정 저작 → **`run` 은 차단 유지** · 차단 목록을 문서 정본으로 · 해소는 후속 웨이브(venue constraint 서비스 · 리스크 상태 서비스 · marketfeed 어댑터) |
| G-1 두 갈래 | (a) 캘린더 포트 `WallClockReference`(`calendar/ports.py` · `Absent` 기본 · `Local` 미결선 · `root.py:156`) (b) `TrustworthyTimeService._issue_snapshot`(`time/service.py:449-489`)이 `wall_clock_observation`·`suspension_status` 를 넘기지 않음 · `LocalSystemClockReader.read` 가 값을 버림(`sources.py:131`) · 소비자 `iap.py:475-483` 은 None 이면 미래일자 승인 검사 **건너뜀** · `_anchor_ok` `suspension_ms=0` 리터럴(`service.py:258`) · `iap.py:773-775` 는 `suspension_ms None` 을 fail-closed | (a)(b) 를 **같은 판독** 에서 공급 · TRUSTED 게이트 · suspension 은 케이던스 기대값 없이는 산출 불가 → named-TBD 신설 |
| nontrade 경로 2 | 엔진: `driver.py:792-801` 이 `nontrade_outcome.disposition` 을 영수증에만 기록(래치 0) · 문: `_types.py:465-508` `observe_nontrade` 가 `NonTradeEventProcessor` 로 판정 후 래치 · 두 경로 판정 동치는 테스트로만(`test_engine_processor_equivalence.py`) · `inbox.enqueue` 는 CA 이벤트를 이미 수용 · `capacity_remap_proposal` 소비자 0(RCL `apply_reservation_transition(cause=RECOGNIZED_EXTERNAL_CHANGE)` API 는 존재 `rcl/log.py:585`) | 경로를 **엔진 하나로** · 문은 enqueue 만 · 래치 로직 공유 · remap 적용은 이월 |
| ack | `STM_ALERT` payload 에 alert id 없음(seq 가 키 · `monitoring.py:727-734`) · `STM_ALERT_RESOLVED` 생산자 0 · `_read_resolved` 는 `()`(`_operations_wiring.py:337-339`) · 커널 `acknowledgements`/`acknowledgement_state` 필드는 **음성**(확인 ≠ 봉쇄 · `stm/state.py:460`) · ADR-002-028 :159/:187/:191/:388/:511 | kind 는 **`STM_ALERT_ACKNOWLEDGED`**(해소 아님) · 메시 `clear()`·래치·재무장에 영향 0 을 구조로 |
| `ReArmWorkflow` | `prepare_new_risk_halt_clear` 는 `ComposedRuntime.clear_new_risk_halt` 에서만 도달(CLI 0) · 생성자 4 인자는 `ConstructionConfig` 무관(`rearm.py:485-524`) · roster/결정 파일 custody 게이트 | `rotate-key` 관용구(저장소 직접 열기)로 `rearm` CLI 가능 |
| 승인값 | 배포 설정 디렉터리 부재(`tos/runtime/config/*.example.yaml` 만) · `calendar.yaml` 필수 키(`calendar/config.py:350-406`) · 채택값 = 제안표 §7 | `config/tos_runtime/<env>/calendar.yaml` 실파일 신설(`config/tos_*` 글롭 안) |
| 픽스처 핀 | `tests/authority/conftest.py:250-289` FakeTimeService(«실 서비스는 못 채운다») · `tests/calendar/test_ports.py:19-59` Absent 기본 · `test_session_wiring.py:219-247` 부재 경로 | 정직 개정(사유 병기) |

## 1. 범위

| 포함 | 제외 (사유) |
|---|---|
| **G-1**(결정 3): `time/sources.py` 로컬 판독기가 값을 **보존**(`ReferenceObservation.wall_clock_unix_ms`) · `_issue_snapshot` 이 `wall_clock_observation` 기입 · `suspension_status` 는 `expected_evaluate_cadence_ms`(time.yaml 신설 named-TBD) 가 있을 때만 `max(0, Δmonotonic − cadence)` 로 기입, null 이면 None(현행) · `calendar/ports.py` `TrustedWallClockReference(time_service)`: `health_state is TRUSTED` 이고 최신 스냅샷의 `wall_clock_observation` 이 있을 때만 판독(같은 값) · 컴포즈 기본 = **Trusted**(프로덕션) · `Absent`/`Fixed` 는 명시 주입 · 핀 개정 · **nontrade 단일 경로**: `observe_nontrade(obs)` 는 `CorporateActionPayload` 로 변환해 **inbox enqueue**(드라이버 결선 시 `enqueue_and_run`, 장벽 보류 시 enqueue 만) · 드라이버가 `EventResult.nontrade_outcome.restrictive is True` 이면 공유 `nontrade/latch.py::latch_restrictive(...)`(`INCIDENT_CANDIDATE` 선기록 → `record_new_risk_halt`) · `NonTradeEventProcessor` 는 `nontrade-eval` 드라이런 전용(evidence 0 · 상태 0) · **운영 CLI**: `rearm`(저장소 직접 열기 · `prepare_new_risk_halt_clear` · roster/결정 파일 필수) · `ack-alert`(`approvals/alerts/<seq>.yaml` 단일 운영자 · custody 게이트 · `STM_ALERT_ACKNOWLEDGED` evidence) · `nontrade-eval`(관측 yaml → disposition 표준출력) · projection `_read_resolved` → ACKNOWLEDGED seq 집합(v1 필드명 유지 · 의미 문서화) · **승인값 실파일** `config/tos_runtime/paper/calendar.yaml`(제안표 §7 · 휴장일 19 정본 대조) + 실파일로 부팅하는 e2e · **`run` 차단 목록 정본**(cli 모듈 docstring + 본 계획 §7 · INDEX) | `run` 실구성(발행 아티팩트 로더 = 판정 저작 · 후속 웨이브) · `shutdown`/`projection` CLI(구성 런타임 필요 → `run` 과 함께) · `capacity_remap_proposal` 소비(용량 적용 · §6 ④ 별도 웨이브) · 틱 원천/marketfeed 어댑터 · 제안표 미승인 값의 실파일(캘린더 외) · 커널 편집 · spec 편집 · 프론트 |

## 2. 결정

1. **벽시계 판독은 하나, 소비자는 둘**: `time/sources.py::LocalSystemClockReader.read` 가 `ReferenceObservation.wall_clock_unix_ms: int | None` 을 채운다(값 보존 · 여전히 `LOCAL_WALL` 도메인은 판정 입력 아님 — 커널 audit-only 불변). `TrustworthyTimeService._issue_snapshot` 은 그 판독을 `wall_clock_observation` 으로 기입(단위 = 커널 필드 문서 기준 · 레인이 확인) · `service.wall_clock_now() -> int | None` 리더(최신 스냅샷의 관측 · TRUSTED 아니면 None). `calendar/ports.py::TrustedWallClockReference(time_service)`: `read()` = `service.health_state is TRUSTED` ∧ 관측 존재 ⇒ `WallClockReading(unix_ms, "trusted-time-service")` · 아니면 None(`SESSION_FACTS_SOURCE_ABSENT` 는 «TRUSTED 미도달» 사유로 1회). 컴포즈: `wall_clock=None` ⇒ `TrustedWallClockReference(time_service)`(프로덕션) · 테스트는 `FixedWallClockReference` 명시 주입 유지 · `AbsentWallClockReference` 는 «G-1 이전 상태 재현» 테스트 전용으로 격하(docstring 정정). `iap.py:475` 소비자는 이제 실값을 받는다 → 미래일자 승인 거부 e2e 핀 신설.
2. **suspension 은 케이던스 기대값이 있을 때만**: `time.yaml` 에 `expected_evaluate_cadence_ms: int | null` 신설(named-TBD · null = «미설정» · 제안표 §1 추가 행 · 값은 드라이버 루프 케이던스가 정해질 때). 설정 시 `_issue_snapshot` 이 `suspension_status = SuspensionStatus(suspended=(gap > max_process_suspension_ms), suspension_ms=max(0, Δmonotonic_between_evaluates − cadence))` 기입 · `_anchor_ok` 의 `suspension_ms=0` 리터럴을 같은 관측으로 교체(미설정 시 None → 커널 `anchor_valid` 가 None 을 어떻게 다루는지 레인이 확인 · 거부면 정직하게 거부 = 현 리터럴이 팬텀이었다는 뜻이므로 §7 에 기록).
3. **nontrade 는 엔진 경로 하나**: `nontrade/convert.py::payload_from_observation(obs) -> CorporateActionPayload`(라운드 #3 동치 테스트의 변환기를 프로덕션으로) · `nontrade/latch.py::latch_restrictive(*, inbox, evidence_store, disposition, reason_source, event_id, evidence_seq) -> LatchOutcome`(`INCIDENT_CANDIDATE` 선기록 → `record_new_risk_halt` 첫 호출 승 · 유일 문) · `engine/driver.py`: `_process_next` 뒤 후크(after-turn 아님 — 결과 처리 직후)에서 `result.nontrade_outcome.restrictive is True` ⇒ `latch_restrictive` · `ComposedRuntime.observe_nontrade(obs)`: payload 변환 → `EngineEvent(CORPORATE_ACTION)` → 드라이버 결선 시 `enqueue_and_run`, 장벽 보류 시 `inbox.enqueue` 만(evidence `NONTRADE_QUEUED_UNTIL_RECOVERY`) · 반환 = 엔진 `EventResult` 기반 `NonTradeOutcome`(런타임 dataclass 유지 · 필드 매핑) · `NonTradeEventProcessor.process` 는 evidence 를 기록하지 않는 `evaluate()` 로 재명명(드라이런) · W5 롤오버/래치 테스트는 엔진 경로로 재핀(사유 병기).
4. **ack 는 확인이지 해소가 아니다**: `safety/ack.py::AlertAcknowledgement`: 파일 `approvals/alerts/<stm_alert_seq>.yaml`(`principal_id` · `acknowledged_at_label`(자유 문자열 · 시간 판정 입력 아님) · `environment_label`) · custody 게이트(0600 · 소유자 · 라벨 일치 — `authority/iap.py:333` 로더 재사용 또는 동일 관용구) · 대상 seq 가 실제 `STM_ALERT` 행이어야 함(아니면 거부) · evidence `STM_ALERT_ACKNOWLEDGED{alert_seq, principal_id}` · **구조 핀**: `safety/ack.py` 는 `safety/monitoring.py`·`safety/latch.py`·`safety/rearm.py`·`engine/inbox.py` 를 import 하지 않는다(확인이 `clear()`·래치·재무장에 닿을 수 없음) · projection `_read_resolved` → ACKNOWLEDGED seq 집합(v1 필드 `unresolved_stm_alert_seqs` 는 «미확인» 의미 — `operator/projection.py` docstring 과 대시보드 DTO 주석에 명시 · 스키마 v1 불변).
5. **운영 CLI 3**(`compose/cli.py` · `rotate-key` 관용구 = 저장소 직접 열기 · 컴포즈 0): `rearm --data-dir --custody-root --approvals-dir --environment-label --seq` → `prepare_new_risk_halt_clear`(roster/결정 파일 필수 · 결과 코드 출력) · `ack-alert --data-dir --custody-root --approvals-dir --environment-label --seq` → 결정 4 · `nontrade-eval --observation <yaml>` → `NonTradeEventProcessor.evaluate` 표준출력(evidence 0). `run`/`restore-drill` 은 불변.
6. **승인값 실파일**: `config/tos_runtime/paper/calendar.yaml`(제안표 §7 그대로 · 상단 주석 «승인: Phase 5 §11 결정 11 · 2026-09-12» · 휴장일 19 는 `config/market_schedule.yaml:88-106` 과 1:1) · `tests/compose/test_deploy_config.py`: 그 실파일을 `config_dir/calendar.yaml` 로 복사해 부팅(다른 파일은 픽스처) + `FixedWallClockReference` 로 정규장 10:00 → CONTINUOUS · 15:35 → CLOSED · 2026-08-17 → CLOSED(대체휴일) · 만기일(2026-09-10 둘째 목요일) 마감 후 → EXPIRED. 캘린더 외 실파일은 제안표 승인 후.
7. **`run` 차단 목록 정본**(코드 0): `cli.py` 모듈 docstring 과 본 계획 §7 에 «`run` 이 구성하지 못하는 이유 3 + 해소 웨이브»를 고정 — (a) `ConstructionConfig` 의 발행 아티팩트 3(venue constraint **서비스** + Order Construction Policy 비준) (b) 리스크 입력 제공자 2(포지션/리스크 상태 서비스) (c) 틱 원천(marketfeed 어댑터) · 대시보드/`shutdown`/projection CLI 는 (a)(b)(c) 뒤.
8. evidence kinds(런타임 상수): `STM_ALERT_ACKNOWLEDGED` · `NONTRADE_QUEUED_UNTIL_RECOVERY` · (기존 `INCIDENT_CANDIDATE`) · `TIME_WALL_CLOCK_EXPOSED`(부팅 1회 · G-1 발효 공시).

## 3. 기각 대안

- `run` 에 YAML→`VenueConstraintSnapshot/Decision` 로더 → 서비스가 발행해야 할 아티팩트를 설정이 발행(stand-in 고착 · 판정 저작). · 벽시계를 캘린더 포트에서 `time.time()` 직접 → TRUSTED 게이트 우회 · 스냅샷과 두 값. · suspension 을 «Δmonotonic 이 곧 suspension» 으로 → 케이던스 없이 상시 양수(팬텀). · ack kind `STM_ALERT_RESOLVED` → ADR :388 위반 문언. · ack 가 메시 `clear()` 입력 → :187 위반. · nontrade 두 경로 유지 → 판정 원천 둘(라운드 #3 §6 ⑤ 미해소). · remap 적용을 이번에 → 용량 적용(별도 웨이브 · 운영자). · 캘린더 외 값 실파일 → 미승인.

## 4. 레인 (sonnet · 파일 소유 1레인 · 커널 diff 0)

| 레인 | 파일 | 내용 | 착수 |
|---|---|---|---|
| g1 | `time/{sources,service,config}.py` · `config/time.example.yaml` · `calendar/ports.py`(Trusted 추가) · `compose/_session_wiring.py`·`root.py`(기본값) · `tests/time/*` · `tests/calendar/test_ports.py` · `tests/compose/test_session_wiring.py` · `tests/authority/*`(FakeTimeService 문언·미래일자 핀) | 결정 1·2·8(`TIME_WALL_CLOCK_EXPOSED`) | 즉시 |
| g2 | `nontrade/{convert,latch,processor}.py` · `engine/driver.py`(후크) · `compose/_types.py`(`observe_nontrade`) · `compose/_session_wiring.py` 의 nontrade 결선 블록(g1 과 파일 공유 → **g1 커밋 후** 그 블록만) · `tests/nontrade/*` · `tests/compose/test_rollover_scenario.py` 재핀 · `tests/engine/*` | 결정 3 | 즉시(`_session_wiring.py` 만 g1 후) |
| g3 | `safety/ack.py` · `compose/cli.py`(서브커맨드 3) · `compose/_operations_wiring.py`(`_read_resolved`) · `operator/projection.py` docstring · `tests/safety/test_ack.py` · `tests/compose/test_cli.py` · `tests/compose/test_operations_wiring.py` | 결정 4·5 | 즉시(`nontrade-eval` 은 g2 의 `evaluate` 이름 확정 후 — 기존 `process` 로 시작해도 됨) |
| g4 | `config/tos_runtime/paper/calendar.yaml` · `tests/compose/test_deploy_config.py` · `cli.py` 모듈 docstring 차단 목록(g3 파일 → g3 에 위임) | 결정 6·7 | 즉시 |

- 공통 규율: 명시 `git add` · stash/checkout/reset 금지 · `-q` 금지 · 레인 시작 시 임포트 경로 확인 · 상수 인자 금지 · 원천 없으면 None · 모듈 ≤1000 · 함수 ≤100(분할) · `_wiring.py` 무성장 · 소스 트리 digest 특성상 다른 레인 편집 중 compose 스위트 일시 실패 가능 → 트리 정지 후 재실행.

## 5. 종료 조건

- 런타임·커널 green · 커널 diff 0 · ruff/black/mypy 0 · firewall · lint-imports · budget(신규 등재 0) · completion GREEN · EV 변경 0.
- 실증: (1) 프로덕션 기본 부팅(`wall_clock=None`)에서 TRUSTED 후 세션 사실 실값 · `SESSION_FACTS_SOURCE_ABSENT` 0 · `wall_clock_observation` 기입 · `TIME_WALL_CLOCK_EXPOSED` 1 · UNTRUSTED 강제 시 판독 None (2) `expected_evaluate_cadence_ms` null ⇒ `suspension_status` None(현행) · 설정 시 실값 (3) 미래일자 승인 파일이 실 스냅샷 값으로 거부 (4) `observe_nontrade` → 엔진 경로 → restrictive ⇒ `INCIDENT_CANDIDATE` + 래치 · 장벽 보류 시 enqueue 만 · 옛 프로세서 경로 evidence 0 (5) `rearm` CLI: roster 부재 거부 · 2인 승인 파일로 해제 · `ack-alert`: 실 seq 만 · evidence 1 · 메시 `clear()`/래치 상태 불변 · projection 미확인 집합에서 제외 (6) 실파일 `calendar.yaml` 부팅 + 4 순간 핀 (7) `run` 여전히 파싱 전용 + docstring 차단 목록.
- 뮤테이션(리뷰 실행 필수): **M1** `TrustedWallClockReference` 가 UNTRUSTED 에서도 판독 → red · **M2** `_issue_snapshot` 기입 제거 → 미래일자 승인 핀 red · **M3** 드라이버 후크가 restrictive 무시 → 래치 핀 red · **M4** `safety/ack.py` 에 `monitoring` import 삽입 → 구조 핀 red · **M5** `rearm` CLI 가 roster 검사 우회 → red · **M6** 실파일 `calendar.yaml` 의 한 값을 null 로 → 부팅 거부 핀 red · **M7** cadence 미설정인데 suspension 채움 → red · **M8** `observe_nontrade` 가 엔진 밖 프로세서로 래치 → 단일 경로 핀 red · **M9** ack 대상 seq 검증 제거 → 존재하지 않는 seq 확인 성공 = red.
- 독립 리뷰(sonnet · 저자와 다른 패스 · 뮤테이션 표 필수) approve · 판정 PR 코멘트.

## 6. 운영자 확인 지점

1. 컴포즈 기본을 `TrustedWallClockReference`(프로덕션 · 플래그 없음)로 — 승인(결정 3 의 구현 형상).
2. `expected_evaluate_cadence_ms` 값 — 드라이버 루프 케이던스 미정이라 named-TBD · 제안표 §1 에 행 추가(해소 웨이브에서 값).
3. ack kind `STM_ALERT_ACKNOWLEDGED` · projection v1 `unresolved_stm_alert_seqs` = «미확인» 의미(스키마 이름 불변) — 승인.
4. `capacity_remap_proposal` 소비(용량 remap 적용 · RCL cause `RECOGNIZED_EXTERNAL_CHANGE`)는 별도 웨이브 — 순서 확인.
5. **`run` 해소 순서**(후속 웨이브 후보): (a) venue constraint 서비스 + Order Construction Policy 비준(spec) (b) 포지션/리스크 상태 서비스(`aggregate_risk`/`action_flow` 입력) (c) marketfeed 어댑터·틱 스케줄러 — 어느 것을 먼저 열지.
6. 배포 설정 디렉터리 `config/tos_runtime/<environment_label>/` 관례 승인.
7. `NonTradeEventProcessor` 를 드라이런 전용으로 격하 — 승인.
