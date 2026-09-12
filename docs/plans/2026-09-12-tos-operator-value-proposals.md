# TOS 런타임 named-TBD 값 제안표 (2026-09-12 · main `837afad3`)

- **목적**: Phase 5 §11 처분 13~16 — 런타임이 부팅을 거부하는 모든 named-TBD `null` 에 대해 **개발 측 제안값 + 근거 + 보수 방향** 을 한 곳에 모아 운영자 승인을 받는다. 승인 전에는 예시 파일의 `null` 을 유지한다(부팅 거부 = 정직). 승인 후 적용은 «런타임 엔트리포인트 웨이브» 가 실파일(`config/*.yaml`)로 착지시킨다.
- **원천 등급**: **A** = 규범 문서에 이미 승인된 값(VER-002 `APPROVED`) · **B** = 공식 SDK/런북/측정 근거 · **C** = 개발 측 보수 제안(근거 명시 · 서버 실측 후 하향 가능) · **M** = 운영자·서버에서만 산출 가능(수동).
- **실측 근거**: `scratchpad/ops-values-survey.md`(26 예시 파일 전수 · 로더 거부 규칙 `file:line` · e2e 픽스처 값 · VER-002 대조). 픽스처 값은 테스트용이며 제안이 아니다(VER-002 승인치와 어긋나는 픽스처 4건은 별도 표기).
- **읽는 법**: 각 표의 «제안» 열이 승인 대상. «보수 방향» 은 그 값을 틀렸을 때 안전한 쪽(작게/크게).

## 1. `time.yaml` — Trustworthy Time 경계

| 키 | 제안 | 등급 | 근거 · 보수 방향 |
|---|---|---|---|
| `MAX_time_source_precision_ms` | **50** | A | VER-002:1076 APPROVED(2026-07-29) · 픽스처 5 는 테스트값 · 작을수록 보수 |
| `MAX_time_transport_and_queue_uncertainty_ms` | **50** | A | VER-002:1069 |
| `MAX_time_conservative_freshness_age_ms` | **1000** | A | VER-002:1078(UNCHK-024 처분 2026-09-04 · Σ지연 200ms 초과 · 작을수록 보수) · 픽스처 60000 은 테스트값 |
| `MAX_future_timestamp_tolerance_ms` | **50** | A | VER-002:1074 · 픽스처 1000 은 테스트값 |
| `MAX_process_suspension_ms` | **2000** | A | VER-002:1009 · 픽스처 5000 은 테스트값 |
| `MAX_time_source_disagreement_ms` | **50** | A | VER-002:1071 |
| `MAX_clock_domain_conversion_uncertainty_ms` | **50** | A | VER-002:1070(continuity pair 단위) |
| `MIN_time_independent_reference_count` | **1** | C | Phase 2 는 참조 원천 종류가 하나뿐 — 2 이상이면 TRUSTED 에 영구 미도달(정직) · 둘째 원천(예: NTP 독립 리더) 착지 시 2 로 상향 |
| `MAX_send_result_wait_ms` | **6000** | C | VER-002 좌표 없음(신규) · 전송 `request_timeout_s=5.0` + 여유 1000ms — 전송 타임아웃보다 짧으면 결과를 기다리지 않고 TIMEOUT 처리해 예약이 불필요하게 점유됨 · 0/음수는 로더가 거부 · **서버 실측(P-13 류) 후 하향** |
| `tz_db_version` | **배포 호스트의 tzdata 버전 문자열**(예 `2025b`) | M | `/usr/share/zoneinfo/+VERSION` 또는 컨테이너 tzdata 패키지 버전 · 캘린더 owner 가 이 값과 관측치를 대조(관측 원천 부재 시 conflict=False 공시) |
| `trading_calendar_version` | **`krx-2026.09`** | A(§11 결정 11) | `calendar.yaml` 의 `calendar_version` 과 바이트 일치 필수(불일치 = 부팅 거부) |
| `verification_profile_version` | **`VER-002`** 의 현재 문서 버전 문자열(spec `VERIFICATION-PROFILE-002.yaml` 헤더의 version 값) | M | spec 에서 복사 · 라벨일 뿐 판정 입력 아님 |
| `safety_profile_version` | **`prof-paper-1@v1`**(§4 profile_id@version) | C | 안전 메시 프로필 문서와 동일 식별자 |

## 2. `currentness.yaml` · `authority.yaml` · `engine*.yaml` · `coordinator_preconditions.yaml`

| 파일 · 키 | 제안 | 등급 | 근거 · 보수 방향 |
|---|---|---|---|
| `currentness.B_capability_claim_to_send` | **500** | A | VER-002:301 APPROVED(단, «fenced egress journal·broker transport 구현 후 RECHECK» 표기 — 이 소비 지점에 대한 재승인이 이 표의 승인) |
| `currentness.required_dimensions` | **커널 `MANDATED_DIMENSION_FLOOR` 17 키 전부를 명시 나열** | C | 운영자 선언이어야 하며 커널 floor 에서 재파생하면 항등식(W3.1 MEDIUM-3) · floor 보다 좁게 선언 = 부팅 거부 |
| `authority.containment_bound_ms` | **60000** | C | Safety Authority epoch 온라인 currentness witness 봉쇄 경계(ADR-002-003 §12.1) · VER-002 키 없음 · 작을수록 보수(짧은 봉쇄) · epoch 갱신 주기 서버 실측 후 하향 |
| `authority.trading_approval_policy_generation` | **1** | C | 현재 로드되는 `TradingApprovalPolicy.policy_generation` 과 일치해야 함(승인 파일 세대 1) |
| `engine.dsl_evaluation_budget_steps` | **64** | C | VER-002 미등재(«provisional») · 등록 전략(band)의 정적 스텝 수 상한 · 전략 추가 시 정적 계수 재측정 · 작을수록 보수 |
| `engine.max_unresolved_send_per_scope` | **1** | A | VER-002:1010 APPROVED |
| `engine_driver.replay_window_events` | **100000** | C | 재생 창이 inbox 전체를 덮지 않으면 창 밖 접두에 미해결 원장 상태가 없어야만 건전 — paper 일일 이벤트 수(수천)의 수십 배로 전체 이력을 덮음 · 클수록 보수(부팅 시간 비용만) |
| `coordinator_preconditions.live_authorization_state` | **`NOT_AUTHORIZED`** | A | 로더가 이 값만 수용 · spec `AUTHORITY-STATUS.csv` restricted_live 행 |
| `coordinator_preconditions.nonlive_broker_consuming.admitted` | **`false`**(기본) → KIS MOCK dry_run 캠페인 시점에 운영자가 `true` | B | transport 계획 §2 결정 7 · REAL 형상 스코프는 이 값과 무관하게 조건 3 에서 영구 차단 |

## 3. `risk.yaml`(AFG 축 · 시나리오 집합) · `risk_attestations.yaml`

| 키 | 제안 | 등급 | 근거 · 보수 방향 |
|---|---|---|---|
| `max_amplification_per_cause` | **3** | A | VER-002:1028 APPROVED(«3~5 중 보수 하단») · 픽스처 10 은 테스트값 |
| `max_in_flight` | **1** | C | `max_unresolved_send_per_scope=1` 과 정합 |
| `max_fan_out` / `max_depth` / `max_attempts` / `max_mutations` | **4 / 3 / 2 / 3** | C | 단일 instrument paper 흐름의 실측 상한(tick→proposal→approval→send = 깊이 3) + 1 여유 · 작을수록 보수 |
| `max_queries` / `max_queue_depth` | **8 / 8** | C | 틱당 조회·큐 상한 · 작을수록 보수 |
| `max_elapsed_monotonic` | **30000**(ms) | C | 한 틱의 액션 플로 총 경과 상한 · `MAX_send_result_wait_ms` 6000 의 5배 · 작을수록 보수 |
| `max_duplicate_redelivery_expansion` / `max_failover_reconnect_replay_expansion` | **1 / 1** | C | 중복 재전달·재접속 재생으로 인한 확장 허용 0 배 초과 금지 |
| `scenario_set_id` / `scenario_set_generation` / `policy_binding_id` | **`paper-adverse-set-1` / 1 / `paper-risk-policy-1`** | C | 식별자 |
| `covered_scenario_kinds` / `required_scenario_kinds` | **`[ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ]`** 둘 다 | C | 현재 생산자가 있는 유일한 시나리오 종류 — 생산자 없는 종류를 required 에 넣으면 정직하게 영구 UNKNOWN |
| `risk_attestations.*.attested`(6 키) | **`true` 유지 불가 → 각 항목을 실 생산자로 교체할 때까지 `true` 를 운영자 attestation 으로 서명** | C | Phase 4 가 실 생산자(밸류에이션·리니지·RCL 배타성 질의) 착지 전까지 attestation · 서명 주체·일자를 yaml 주석에 기록 |

## 4. 안전 메시 정책 문서(W3.1 이월 · `safety_envelope` · `safety_profile` · `safety_activation` · `monitor_coverage` · `safety_deviations` · `safety_incidents`)

paper(합성 transport · KIS MOCK dry_run) 용 최소 보수 문서. 실선물은 영구 부재이므로 선물 차원 없음.

| 문서 · 키 | 제안 | 등급 | 근거 · 보수 방향 |
|---|---|---|---|
| envelope `envelope_id`/`generation`/`version` | **`env-paper-1` / 1 / `v1`(effective 2026-09-15 · approver = 운영자 id · expiration 2027-03-15)** | C | 6개월 재검증 주기 |
| envelope `governed_dimensions` | **`max_order_notional_krw` = 1,000,000 · `max_open_orders` = 1 · `max_daily_orders` = 20**(unit KRW/count · sign POSITIVE · precision 0 · rounding NEAREST · boundary INCLUSIVE) | C | MOCK 계좌 dry_run 규모 · 작을수록 보수 |
| envelope `permitted_scope` / `prohibited_fallbacks` / `residual_risk_ceiling` | **`[MOCK_STOCK_ORDER]` / `[market_order, real_scope]` / `null`** | C | fallback 으로 시장가·REAL 스코프 전환 금지 |
| profile `profile_id`/`generation`/`target_envelope` | **`prof-paper-1` / 1 / `env-paper-1`@1** | C | |
| profile `governed_dimensions` | **notional 500,000 · open_orders 1 · daily_orders 10**(envelope 의 절반) | C | 프로필 ≤ envelope 커널 검증 |
| profile `scope`/`permitted_behaviors`/`fallback_rules` | **`[MOCK_STOCK_ORDER]` / `[NEW_LONG, CLOSE, CANCEL]` / `[]`** | C | 숏·증액·교체 행위는 프로필 밖(step 3 admitting 집합과 정합) |
| activation | **`act-paper-1` · profile_generation 1 · digests = 문서 실 digest(운영자 산출 · `sha256sum`) · scope `[MOCK_STOCK_ORDER]` · approval_ids `[운영자 승인 id]` · compatibility_attestation_refs `[본 문서 §4 승인 기록]` · predecessor null · `not_expired: true`(만료일 전까지)** | M | digest 는 파일 확정 후 산출 |
| coverage manifest | **`cov-paper-1` · generation 1 · digest = 실 digest · `is_complete: true`** · items 3(`evidence-tip-currency`, `time-service-health`, `inbox-backlog`) 전부 `restrictive_response_present/alert_path_present/evidence_path_present/currentness_rule_present/closure_1_to_12_complete: true` · criticality `CRITICAL` | C/M | 세 항목 모두 실 감지기가 있음(W3.1 stm) |
| coverage bounds | **`max_evidence_tip_stall_ms` 60000 · `healthy_time_states` `[TRUSTED]` · `max_inbox_unconsumed` 100** | C | stall 60s 는 driver 무동작 감지 · 작을수록 보수(오탐 증가) · 서버 실측 후 하향 |
| deviations active_set | **`dev-set-paper-1` · gen 1 · `is_complete: true` · `combined_within_envelope: true`(attestation) · members `[]`** | C | 활성 이탈 0 이 정상 상태 |
| incidents active_set | **`inc-set-paper-1` · gen 1 · `safety_cell = paper-cell-1` · `shared_dependencies: []` · `is_complete/is_current: true` · members `[]`** | C | |

## 5. `finality.yaml` · `evidence_retention.yaml` · `backtest_calibration.yaml`

| 키 | 제안 | 등급 | 근거 · 보수 방향 |
|---|---|---|---|
| `finality.currency` | **`KRW`** | B | KRX 주식 |
| `finality.value_date` | **`T+2`**(토큰 · KRX 주식 결제일) | B | 커널은 불투명 토큰 · 배포 시점 고정 |
| `finality.source_revision` | **배포 git SHA** | M | |
| `finality.proof_recipe_id` | **ADR-002-030 §29 Q3 의 Phase-0 승인 recipe 식별자** | M | spec 에서 복사(문서에 리터럴 미고정 — spec PR 로 고정 요청) |
| `finality.release_proof_wait_ms` | **259,200,000**(3일) | C | 결제 T+2 도달 후 증빙 수집 여유 1일 · 길수록 보수(용량이 더 오래 점유) |
| `evidence_retention.minimum_days_by_class.{TOMBSTONE, RESTORE_COMPARISON, KEY_ROTATION}` | **`null` 유지 = 삭제 불가** | C | Phase 5 «삭제 0» 원칙 · 로더는 개별 null 을 부팅 거부하지 않음 |
| `backtest_calibration.*` | **`max_price_bps` 20 · `max_fill_ratio_shortfall` 0.05 · `max_latency_bars` 2 · `min_observations` 30** | C | 현 슬라이스는 가격·바 좌표가 없어 결과가 항상 INSUFFICIENT — 값은 후속 측정 웨이브를 위한 예산 선언 |

## 6. KIS MOCK transport(T2 이월 · 런북 `docs/runbooks/tos-kis-mock-transport.md` §4 통합)

| 키 | 제안 | 등급 | 근거 |
|---|---|---|---|
| `endpoint_rest_base` | `https://openapivts.koreainvestment.com:29443` | B | INSTANCE MOCK_VTS · REAL 호스트는 구조적으로 불가 |
| `order_path` / `token_path` | `/uapi/domestic-stock/v1/trading/order-cash` / `/oauth2/tokenP` | B | 공식 SDK `order_cash.py:22` · `auth_token.py:28` |
| `tr_id_buy` / `tr_id_sell` | `VTTC0012U` / `VTTC0011U` | B | SDK `order_cash.py:103-118`(demo) |
| `field_map` | account→`CANO` · instrument→`PDNO` · quantity→`ORD_QTY` · price→`ORD_UNPR` | B | SDK 필드명 |
| `static_body_fields.ORD_DVSN` / `EXCG_ID_DVSN_CD` / `SLL_TYPE` / `CNDT_PRIC` | `"00"`(지정가) / `"KRX"` / `""` / `""` | B | 시장가 `"01"` 은 별도 승인 |
| `static_body_fields.ACNT_PRDT_CD` | **`"01"`**(위탁종합 상품코드 관례) — **계좌 개설 서류로 확인 후 확정** | M | 계좌별 상이 가능 |
| `min_send_interval_ms` | **1100** | B | P-13 실측 1.0 rps 한도 + 100ms |
| `token_reissue_min_interval_s` | **60** | C | KIS 공지 «접근토큰 발급 1분당 1회» 관례 · N-15 서버 실측 4/4 실패 → 실측 후 확정 |
| `request_timeout_s` | **5.0** | C | `MAX_send_result_wait_ms` 6000 과 정합 |
| `mode` | `dry_run`(운영자 캠페인 완료 전) | B | `live` 는 codec 결속 + Coordinator non-live admission + P0-2 종결 후 |

## 7. `calendar.yaml`(§11 결정 11 · 채택됨 — 실파일 형태)

```yaml
calendar_version: "krx-2026.09"
tz_id: "Asia/Seoul"
closed_phase: "CLOSED"
holidays:            # config/market_schedule.yaml:88-106 의 2026 항목 19건을 그대로 옮김(정본) · shared/calendar.py 표는 정정 대상
  - 2026-01-01   # 신정
  - 2026-02-16   # 설날 연휴
  - 2026-02-17   # 설날
  - 2026-02-18   # 설날 연휴
  - 2026-03-01   # 삼일절(일요일)
  - 2026-03-02   # 대체휴일
  - 2026-05-05   # 어린이날
  - 2026-05-24   # 부처님오신날(일요일)
  - 2026-05-25   # 대체휴일
  - 2026-06-06   # 현충일(토요일)
  - 2026-08-15   # 광복절(토요일)
  - 2026-08-17   # 대체휴일
  - 2026-09-24   # 추석 연휴
  - 2026-09-25   # 추석
  - 2026-09-26   # 추석 연휴(토요일)
  - 2026-10-03   # 개천절(토요일)
  - 2026-10-05   # 대체휴일
  - 2026-10-09   # 한글날
  - 2026-12-25   # 크리스마스
  # 운영자 검토 후보(정본 파일에 없음 · 확인 후 정본에 먼저 추가): 2026-06-03(지방선거일) · 2026-12-31(KRX 연말 휴장)
sessions:
  krx-stock:
    - {phase: PRE_OPEN,    start: "08:30", end: "08:40", days: [MON,TUE,WED,THU,FRI], crosses_midnight: false}
    - {phase: CONTINUOUS,  start: "09:00", end: "15:30", days: [MON,TUE,WED,THU,FRI], crosses_midnight: false}
    - {phase: AFTER_HOURS, start: "15:40", end: "16:00", days: [MON,TUE,WED,THU,FRI], crosses_midnight: false}
  krx-index-futures:
    - {phase: CONTINUOUS,  start: "08:45", end: "15:45", days: [MON,TUE,WED,THU,FRI], crosses_midnight: false}
    # 야간 18:00→05:00 은 실선물 전용(MOCK 에 야간 TR 없음 · U-4) — 실선물 영구 부재이므로 창을 두지 않는다
futures_expiry:
  krx-index-futures: {weekday: THU, ordinal: 2, months: [3,6,9,12], expired_phase: EXPIRED}
```
- 휴장일 19건은 `config/market_schedule.yaml:88-106` 과 1:1 대조 완료(2026-09-12). 주말에 걸린 공휴일도 정본대로 포함(캘린더는 요일 창으로 이미 닫힘 · 무해). 정본에 없는 지방선거일·연말휴장은 운영자가 정본 파일에 먼저 추가한 뒤 여기 반영. `PRE_OPEN` 은 step 3 admitting 집합 밖(주문 불가 · 정보용).

## 8. 디스크 파일(§11 결정 16 · 운영자 수동)

| 파일 | 스키마 · 제안 |
|---|---|
| `<custody_root>/approvals/rearm/roster.yaml` | `environment_label: paper` · `principals: [{id: <운영자 A id>}, {id: <운영자 B id>}]`(서로 다른 실인물 · 2인) · `control_edges: []` · `unresolved_control: false` · 모드 0600 · 소유자 = 런타임 uid. **주의**: `ReArmWorkflow` 는 아직 `compose_paper_runtime` 에 미결선(엔트리포인트 웨이브 항목) — 파일 배치는 선행 가능 |
| `<custody_root>/approvals/rearm/<latched_evidence_seq>.yaml` | 재무장 시마다 `latched_evidence_seq` · `approvals: [{principal_id, decision: APPROVE}, …]` 2인 |
| `<custody_root>/custody.manifest.yaml` `expected_sha256` | 배포 후 `sha256sum <scope 파일>` 로 고정(런북 §5) |
| `release.yaml` `expected_code_digest` / `expected_dependency_set_digest` | paper 서버에서 `tos-runtime print-digests`(§11 결정 12) |

## 9. 키 없음(제안 불가 · 후속 웨이브에서 키 신설 시 제안)

- 복구 장벽 timeout(Phase 5 §7 item 2 «장벽 timeout») — 현재 설정 키 없음 · 신설 시 **30000ms**(장벽 입력 수집 상한 · 초과 = NOT_READY 유지) 제안.
- 키 회전 주기 — 회전은 운영자 CLI `rotate-key` 트리거(§11 결정 7) · 주기 강제 키 없음 · 운영 절차로 **90일** 권고(모니터링 항목화는 후속).
- 마이그레이션 정책 · admitted dependency manifest — §11 결정 8·12 로 종결(키 아님).

## 10. 승인 방식

- 이 문서의 표 단위로 «채택 / 수정값 / 보류» 를 답하면, 엔트리포인트 웨이브가 채택 항목을 실파일로 착지시키고 각 파일 상단 주석에 «승인: 본 문서 §n · 일자» 를 남긴다.
- 등급 M 항목은 운영자가 서버에서 산출한 값을 직접 기입한다(개발 측 값 제안 없음).
