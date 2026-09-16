# TOS action-flow 관측 완결 웨이브 계획 — step 7 GRANT 도달 · dedup/replay 축의 내구 관측(스키마 변경 0)

- **상위**: 리스크 상태 서비스 계획 §7 정직 발견(«step 7 GRANT 범주적 불가 — dedup/replay 축 관측 부재») · §6 ⑤ 다음 순서(운영자 2026-09-16 「3. 다음 순서 진행」 — ★ step 7 해소 먼저) · ADR-002-022 §5.8(증폭 봉투) · `tos/src/tos/afg/state.py:515-524`(restart 를 failover/reconnect 와 같은 증폭 계급으로 묶음) · DR-0003 §2.3(관측/선언 분리 — «duplicate redelivery rejections, recovery replays» 를 관측으로 명시).
- **선행**: 리스크 상태 서비스 웨이브 완료(main `f52e06a3`) · 서베이 `scratchpad/s7-survey.md`(2026-09-16 · `file:line`).
- **저작**: 세션 모델 단독 · **커널 diff 0** · **스키마/마이그레이션 0**(서베이 결론: 두 축 모두 기존 내구 evidence 로 관측 가능) · 권한 부여 0.
- **브랜치**: `feat/tos-action-flow-observation`(워크트리 `../kis_unified_sts-step7`).

## 0. 서베이 실측 (요지)

| 항목 | 실측 | 함의 |
|---|---|---|
| dedup 축 | `flow_observation.py:17-23` 독스트링은 인박스 admission dedup(`InboxReceipt.duplicate` 일시)만 보고 None 으로 둠. 그러나 커널의 두 번째 dedup — `ProvisionalReservationLedger._applied_result_signatures`(`engine/state.py:333-346` · KR3 6-tuple) 가 재주입 `EGRESS_RESULT` 를 `ResultDisposition.DUPLICATE` 로 분류하고 `core.py:705-720` 이 **`RESULT_UNMATCHED` evidence 행에 `result_disposition` + `attempt_id` 를 내구 기록** · `InboxFlowReader.observe`(`:327-334`) 는 이미 그 행을 읽으면서 `result_disposition` 을 버림 | **읽기 측 변경만으로 관측 가능** — 스키마 0 · 방출 지점 0 |
| replay 축 | 부팅 replay 검증(`_engine_wiring.py:286-373`) 은 저장소 전체 1회 verdict(`REPLAY_VERDICT_IDENTICAL`/`REPLAY_DIVERGED`) · 크래시 창 복구(`driver.py:714-863 _process_next` → `_handle_interrupted_event:482-544`) 는 **root event_id 키의 내구 마커** `DECISION_TICK_DROPPED_ON_RECOVERY`/`HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND` 를 남김 · AFG 어휘(`afg/state.py:515-524`) 는 restart 를 failover/reconnect 와 같은 계급으로 봄 · 한계: 같은 미결 행이 두 번째 restart 를 겪어도 마커는 1회(재승인 전까지) | 마커 계수 = «이 root cause 가 겪은 restart 복구 에피소드 수»(정직한 관측 · 과소 계수 가능성은 공시) — 새 방출 지점·부팅 세대 카운터는 후속 |
| 술어 | `amplification_bounded`(`afg/predicates.py:311-361`) 11 축 전부 `bound is not None and count is not None and count <= bound` · **내구 0 은 정당한 통과값** · 봉투 측은 `declares_every_bound` 로 이미 부팅 거부 | 관측 측 None 만 막고 있음 |
| 크기 | `driver.py` 1000 · `_process_next` 149(등재 예외) · `flow_observation.py` 494(`observe` ~88행) | driver 무접촉 · `flow_observation.py` 는 헬퍼 분할로 |

## 1. 목표 · 범위 · 비범위

**목표**: 두 축을 기존 내구 evidence 에서 관측해 step 7 `ACTION_FLOW_DECISION` 이 컴포즈 e2e 에서 **GRANT** 에 도달하게 한다(제공자 미주입 · 정책 인스턴스 + 구조 관측만). 봉투 초과 시 DENY 를 실증한다.

**범위**: `riskstate/flow_observation.py`(두 계수 + 헬퍼 분할 · 독스트링 정정) · `riskstate/service.py`(`absent_fields` 에서 두 축 제거 · 변화 없으면 무접촉) · tests(`tests/riskstate` 단위 · `tests/compose/test_riskstate_wiring.py` e2e GRANT/DENY) · `cli.py` (b′) 문언(step 7 한계 → 해소 · 잔여 = 단일 원천 포지션·계약 수 차원) · README · §7.

**비범위**: 커널 · 스키마/마이그레이션 · 새 evidence 방출 지점 · 부팅 세대 카운터(§6 ① 에서 «옵션 2» 선택 시 별도) · driver 편집 · (a′)(c).

## 2. 결정

1. **dedup 축 = 커널 DUPLICATE disposition 계수.** `duplicates_rejected` = `RESULT_UNMATCHED` 행 중 `result_disposition == "DUPLICATE"` ∧ `attempt_id ∈ cause_attempts`(기존 `_scan_sealed_lineage` 의 집합) 의 수. 스캔이 완료돼 0건이면 **0**(None 아님). 인박스 admission dedup 은 작업을 만들지 않으므로 증폭 0 — 독스트링에 두 dedup 층을 구분해 기록.
2. **replay 축 = 복구 마커 계수(옵션 1).** `replays` = 이 root cause 의 event_id 를 키로 하는 `DECISION_TICK_DROPPED_ON_RECOVERY` + `HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND` 행의 수. 정의: «런타임이 이 원인에 대해 기록한 restart 복구 에피소드 수»(AFG 어휘가 restart 를 같은 계급으로 묶음). 한계(과소 계수 가능: 같은 미결 행의 반복 restart 는 1회 기록)는 모듈 독스트링 + DR-0003 §2.3 문언과 함께 evidence `RISK_STATE_OBSERVED.flow.replays_definition` 로 공시. **운영자 확인 ①**: 이 정의를 받아들일지, «옵션 2»(새 evidence + 부팅 세대 카운터) 를 요구할지.
3. **읽기 헬퍼 분할.** `observe()` 는 100행 예산 근접 → `_count_duplicate_dispositions(...)`/`_count_recovery_markers(...)` 순수 헬퍼(입력 = 이미 읽은 payload 리스트 · 출력 int) — 순수 함수라 단위 테스트 직접.
4. **e2e 수용 기준.** `test_riskstate_wiring.py::TestComposeE2E`: 제공자 미주입 첫 attempt 에서 step 6 GRANT **그리고 step 7 GRANT**(기존 UNKNOWN 단언을 GRANT 로 바꾸고, 그 변화가 이 두 축 때문임을 «두 축을 None 으로 되돌리면 UNKNOWN» 뮤테이션으로 증명) · seed 로 `RESULT_UNMATCHED{DUPLICATE, attempt∈cause}` 행을 봉투 `max_duplicate_redelivery_expansion` 초과만큼 심으면 step 7 **DENY** · 복구 마커 seed 초과 → DENY · 미러(NEW_SHORT) 동일.
5. **`absent_fields`** 에서 두 축 제거(관측됨) · 남는 absent = `committed_flow_vectors`(현행 `()` 사실 유지).

## 3. 기각 대안

| 대안 | 기각 사유 |
|---|---|
| 인박스 스키마에 카운터 + 마이그레이션 | 서베이가 두 축 모두 기존 내구 evidence 로 관측 가능함을 실측 — 스키마 변경은 비용만 |
| 두 축을 정책 선언으로 | 관측 가능한 사실을 선언으로 바꾸면 DR-0003 §2.3 위반 |
| 인박스 admission dedup 을 세기 위해 `enqueue` 에 evidence 방출 추가 | 거부된 중복은 작업을 만들지 않으므로 증폭 0 — 세어도 값이 바뀌지 않음 · 방출 지점 신설 불필요 |
| 두 축 None 유지 + 봉투 축 제거 | 커널 `declares_every_bound` 가 부팅 거부 · 커널 편집 금지 |

## 4. 레인

| 레인 | 파일 | 순서 |
|---|---|---|
| a(executor) | `riskstate/flow_observation.py` · `riskstate/service.py`(필요 시) · `tests/riskstate/test_flow_observation.py` · `tests/compose/test_riskstate_wiring.py` · `compose/cli.py`((b′) 문언) | 단일 레인 |
| c(세션 모델) | README · INDEX · §7 | a 뒤 |
| 리뷰 | `code-reviewer`(sonnet) · 뮤테이션 표 필수 | PR |

## 5. 종료 조건 · 뮤테이션

- 실증: (1) 제공자 미주입 e2e step 6 GRANT ∧ **step 7 GRANT** · `RISK_STATE_OBSERVED.absent_fields` 에 두 축 없음 (2) DUPLICATE seed 초과 → step 7 DENY (3) 복구 마커 seed 초과 → DENY (4) 미러 동일 (5) 단위: 0건 스캔 → 0(None 아님) · cause 밖 attempt 의 DUPLICATE 는 미산입 · 다른 event_id 의 마커 미산입.
- 뮤테이션: M1 두 축을 None 으로 복원 → e2e step 7 GRANT red · M2 DUPLICATE 필터 제거(모든 `RESULT_UNMATCHED` 계수) → 단위 red · M3 cause 필터 제거 → red · M4 마커 kind 하나 누락 → red · M5 `replays_definition` 공시 누락 → red · M6 0 대신 None 반환 → red.
- 정직 상태(예상): replay 축은 «복구 에피소드 계수»라는 정의 하의 관측(과소 계수 공시) · `committed_flow_vectors` 여전히 `()` · `run` 은 (a′)(b′ 잔여: 단일 원천 포지션 · 계약 수 차원)(c) 로 계속 차단.

## 6. 운영자 확인

1. replay 축 정의(옵션 1 «복구 에피소드 계수» 채택 · 추천) vs 옵션 2(새 evidence + 부팅 세대 카운터 · 별도 웨이브).
2. 다음 순서: (c) 틱 원천/marketfeed → (a′) → 브로커 증인(P-BAL) → 커널 라운드 #4.

## 7. 착지 기록

(레인 착지 후 기입)
