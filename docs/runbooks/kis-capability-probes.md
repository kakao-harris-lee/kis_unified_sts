# 런북 — KIS Broker Capability 측정 프로브 (Phase-0 P0-2 / T2)

> **문서 성격**: 운영 런북(비규범). 이 문서도, 프로브 실행도 **어떤 게이트도 닫지
> 않는다.** 프로브는 *측정*하고, 승인은 *사람*이 한다. bound 값 기입은
> **Bounds-Approver**, capability status 승격은 P0-2 승인 사슬의 소관이다
> (초안 메모 §8 — 10개 항목 전부 미충족 상태).

- **하네스**: `tools/broker_probes/` (저작 전용 패키지 — 트레이딩 런타임이 임포트하지 않음)
- **엔트리포인트**: `python -m tools.broker_probes.run --list`
- **근거**: 실행 계획 `docs/plans/2026-07-29-tos-phase0-p02-execution-plan.md` §1 T2 ·
  프로브 정본 `docs/plans/2026-07-29-tos-broker-capability-profile-kis-draft.md` §5
- **대상 INSTANCE**: `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml`
- **대상 bound**: `tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml`

---

## 1. 목적과 범위

P0-2는 "broker-specific bounds는 **MEASURED, not guessed**"를 요구한다. 이 런북은
그 측정을 **재현 가능하고 안전하게** 수행하는 절차다.

**하는 것**: 모의투자(MOCK_VTS) 계좌에서 16건의 프로브를 실행해 JSON 증거
아티팩트를 만든다. 실전(REAL_PROD)은 **조회 전용 3건**(N-16·N-18·P-BAL)뿐이다.

**하지 않는 것**:

- INSTANCE YAML·VERIFICATION-PROFILE 자동 기입 (프로브는 파일을 쓰지 않는다)
- 값의 발명 — 관측되지 않은 것은 `null`로 남기고 UNKNOWN을 유지한다
- 실전 주문 계열 접촉 (구조적으로 불가능 — §2.3)
- MOCK 관측의 REAL 외삽 (ADR-002-004 §13.14 / BC-INV-009 — 샌드박스 증거는
  그 자체로 live capability를 성립시키지 않는다)

---

## 2. 전제

### 2.1 실행 호스트

프로젝트 규약 [[verify-on-paper-server-not-local-cron]]에 따라 **모의투자 서버(배포
호스트)** 에서 실행한다. 로컬 개발기에서의 실행은 네트워크·시각·계정 상태가 달라
측정값의 근거가 되지 못한다.

선행 조건:

- `config/futures_live.yaml::enabled: false` — 주문 계열 프로브는 이 값이 true면
  `SafetyViolation`으로 **거부**된다 (`common.py::assert_no_live_futures_config`)
- 페이퍼 워커 정지 — P-13(쿼터 소모)·P-14(WS 세션 축출)·P-15/N-15(토큰 재발급)는
  가동 중인 시스템을 **교란**한다
- Redis 플래그 `futures:live:suspended` 상태 확인

### 2.2 환경 변수 (이름만 — 값은 절대 커밋·명령행 노출 금지)

프로브는 **환경에서만** 시크릿을 읽는다. 명령행 인자에 키를 넣는 경로는 없다.

| 변수 | 용도 |
|---|---|
| `KIS_FUTURES_APP_KEY` / `KIS_FUTURES_APP_SECRET` | 선물 계열 (`--asset futures`, 기본값) |
| `KIS_FUTURES_ACCOUNT_NO` | 선물 계좌 (숫자 10자리로 정규화됨) |
| `KIS_STOCK_APP_KEY` / `KIS_STOCK_APP_SECRET` | 주식 계열 (`--asset stock`) |
| `KIS_STOCK_ACCOUNT_NO` | 주식 계좌 (P-11 필수) |
| `KIS_APP_KEY` / `KIS_APP_SECRET` | 자산별 변수 부재 시 폴백 |
| `KIS_TOKEN_CACHE_DIR` | **하네스는 무시한다** — 설정돼 있으면 경고만 출력 |

> **⚠ 실전/모의 자격증명은 같은 변수 이름을 공유한다.** 하네스에 `REAL_*` 별도
> 변수는 없고, `is_real` 플래그가 base URL만 바꾼다. 따라서 **N-16/N-18은 실전
> 자격증명을 export한 별도 셸에서** 실행하고, 그 셸에서는 모의 프로브를 실행하지
> 않는다 (§5.4).
>
> 반대 방향은 안전하다: 실전 자격증명이 export된 상태로 모의 주문 프로브를 돌려도
> `assert_mock_host`가 모의 호스트를 강제하므로 **실전 주문은 발생할 수 없다.**

### 2.3 안전 모델 (규약이 아니라 코드로 강제됨)

| # | 강제 | 구현 | 우회 가능? |
|---|---|---|---|
| 1 | 주문 계열은 모의 호스트만 | `assert_mock_host()` — `openapi.koreainvestment.com` 거부 | 불가 (플래그 없음) |
| 2 | 주문 TR은 `V` 접두만 | `assert_mock_trading_tr()` — `TTT*`/`STTN*`/`CTF*` 거부 | 불가 |
| 3 | live 선물 설정 무장 시 주문 프로브 거부 | `assert_no_live_futures_config()` | 불가 |
| 4 | `--confirm` 없이는 브로커 무접촉 | `requires_confirm` + `dry_run_banner()` | — (기본값이 안전) |
| 5 | 실전 프로브는 GET + 3중 allowlist | `assert_read_only_call()` (method ∧ tr_id ∧ path) | 불가 — 모듈에 POST 경로 자체가 없음 |
| 6 | 시크릿·계좌 마스킹 | `redact()` — 아티팩트·로그 전수 | — |
| 7 | 토큰 캐시 격리 | `results/.token_cache` 기본값 | `--token-cache-dir`로 명시적 변경만 |
| 8 | P-11 체결은 이중 확인 | `--confirm` **및** `--allow-fill` | — |

강제 5의 allowlist는 **모듈별**이다: `probes_real.py::ALLOWLIST` 3건(N-16·N-18) +
`probes_balance.py::ALLOWLIST` 3건(P-BAL — 잔고 조회 TR 3종뿐, `/order` 경로 0건).
항목 추가는 상수 편집 = 리뷰 대상 변경이다. 두 모듈 모두 POST/PUT/PATCH/DELETE
경로가 **존재하지 않으며**, `probes_balance.py`의 경우 그 부재가
`tests/tools/test_broker_probes_balance.py`에서 **모듈 AST 대조로 강제**된다(주석이
아니라 테스트). 같은 파일은 `probes_balance.py`가 `probes_order.py`를 임포트하지
않음까지 확인한다 — 임포트하면 주문 경로가 그 모듈의 임포트 그래프에 들어온다.

### 2.4 결과 디렉터리

`tools/broker_probes/results/` — `.gitignore:89`의 `results/` 규칙으로 **커밋되지
않는다.** 이는 시크릿 유출 방지에는 옳지만 §6.3의 증거 보존과 충돌하므로, 인용 전
반드시 승인 패키지로 **복사**한다.

---

## 3. 프로브 전수 표 (12 정본 + 4 census = 16, + 후속 2 = 18)

공통 인자: `--asset {stock,futures}` · `--symbol` · `--quantity`(기본 1) ·
`--price-offset-pct`(기본 10 — 미체결 유지용, **지정가 경로 전용**) · `--samples` ·
`--margin-pct`(기본 50) · `--out-dir` · `--note`. 전수 목록은 `run.py ... --help`.

P-11 전용 인자 2건: `--stock-order-type {market,limit}`(기본 **market**) ·
`--balance-timeout-s`(기본 **120**, 공유 `--visibility-timeout-s` 30초와 별개).

| ID | 차원 | 종류 | 환경 | 명령 | 소요 | 위험 | 주문 발생 |
|---|---|---|---|---|---|---|---|
| **P-1** | ORDER_IDENTITY | SPEC_CROSSCHECK | NONE | `python -m tools.broker_probes.run P-1` | ~0 (offline) | LOW | 아니오 |
| **P-2** | SUBMISSION_IDEMPOTENCY | ORDER | MOCK_VTS | `python -m tools.broker_probes.run P-2 --confirm` | ~5 min | HIGH | 예 |
| **P-5** | OPEN_ORDER_QUERY | ORDER | MOCK_VTS | `python -m tools.broker_probes.run P-5 --confirm` | ~20 min at N=100 | HIGH | 예 |
| **P-5b** | OPEN_ORDER_QUERY | QUERY | MOCK_VTS | `python -m tools.broker_probes.run P-5b --confirm` | ~2 min | LOW | 아니오 |
| **P-8** | REPLACE_OR_AMEND | ORDER | MOCK_VTS | `python -m tools.broker_probes.run P-8 --confirm` | ~10 min | HIGH | 예 |
| **P-11** | POSITIONS_BALANCES_MARGIN | ORDER | MOCK_VTS | `python -m tools.broker_probes.run P-11 --asset stock --symbol 005930 --confirm --allow-fill` | ~15 min | HIGH | 예 |
| **P-13** | RATE_LIMITS | QUERY | MOCK_VTS | `python -m tools.broker_probes.run P-13 --confirm` | ~10 min | MEDIUM | 아니오 |
| **P-14** | SESSION_CONNECTION_MODEL | SESSION | MOCK_VTS | `python -m tools.broker_probes.run P-14 --confirm` | ~10 min | HIGH | 아니오 |
| **P-15** | CREDENTIALS_AUTHORIZATION | AUTH | MOCK_VTS | `python -m tools.broker_probes.run P-15 --confirm` | ~3 min | HIGH | 아니오 |
| **P-16** | BROKER_TIME | QUERY | MOCK_VTS | `python -m tools.broker_probes.run P-16 --confirm` | ~5 min | LOW | 아니오 |
| **P-EXT** | POSITIONS_BALANCES_MARGIN | MANUAL | MOCK_VTS | `python -m tools.broker_probes.run P-EXT --confirm` | ~15 min/trial (운영자 개입) | MEDIUM | 아니오 |
| **P-FQP** | CANCELLATION | ORDER | MOCK_VTS | `python -m tools.broker_probes.run P-FQP --confirm` | ~20 min | HIGH | 예 |
| **N-15** | CREDENTIALS_AUTHORIZATION | AUTH | MOCK_VTS | `python -m tools.broker_probes.run N-15 --confirm` | ~5 min/trial (매 trial ≥60s 대기) | HIGH | 아니오 |
| **N-16** | POSITIONS_BALANCES_MARGIN | REAL_READ_ONLY | REAL_PROD | `python -m tools.broker_probes.run N-16 --confirm` | 1 call | MEDIUM | 아니오 |
| **N-17** | MARKET_INSTRUMENT_CONSTRAINTS | SPEC_CROSSCHECK | NONE | (스크립트 아님 — **§7 체크리스트**) | ~1 h 데스크워크 | LOW | 아니오 |
| **N-18** | MARKET_INSTRUMENT_CONSTRAINTS | REAL_READ_ONLY | REAL_PROD | `python -m tools.broker_probes.run N-18 --confirm` | 3 calls | MEDIUM | 아니오 |
| **P-NMPR** | MARKET_INSTRUMENT_CONSTRAINTS | ORDER | MOCK_VTS | `python -m tools.broker_probes.run P-NMPR --confirm --asset futures` | ~2 min | HIGH | 예 |
| **P-BAL** | POSITIONS_BALANCES_MARGIN | REAL_READ_ONLY | REAL_PROD / MOCK_VTS (`--env`) | `python -m tools.broker_probes.run P-BAL --asset stock --env real --confirm` | ~1 min | LOW | 아니오 |

> **P-NMPR·P-BAL은 정본 16에 속하지 않는다.** 각각 N-17 대조와 wave-3b 런타임
> 트레이스(H4)에서 파생된 **후속 2건**이며, `registry.py`의 `source`가
> "draft"·"plan" 어느 쪽으로도 시작하지 않아 `--coverage`의 정본 12 / census 4
> 카운트를 **바꾸지 않는다**. 캠페인 집계에서 "18건 실행"을 "정본 전건 실행"으로
> 읽지 말 것.
>
> **P-BAL의 표상 `환경`은 두 값을 가질 수 있는 유일한 프로브다.** `registry.py`의
> `environment`는 기본 대상인 `REAL_PROD`이지만, 아티팩트의 `environment`는
> **`--env`가 실제로 접촉한 환경**으로 기록된다(§6.2가 MOCK_VTS 아티팩트의
> REAL_PROD 문서 인용을 금지하므로 spec 값을 그대로 쓰면 안 된다). 인용 전 아티팩트
> 필드를 직접 확인할 것.

### 3.1 프로브별 목적 (한 줄)

| ID | 무엇을 확정하는가 |
|---|---|
| P-1 | 클라이언트 주문번호 필드 존부 — 우리가 안 보낸다는 사실은 broker가 안 준다는 증거가 **아니다**. 판정은 N-17 |
| P-2 | 동일 본문 2회 전송 → ODNO 2개면 dedup 없음. 1개면 창 길이를 **구간**으로 브래킷 |
| P-5 | 주문 수락(t0) → 조회 가시(t1) 수렴 지연. `B_broker_query_consistency`의 유일한 원천 |
| P-5b | 연속조회 키가 실제로 전진하는가 (Q-OOQ-1 — 런타임은 항상 1페이지만 읽는다) |
| P-8 | `RVSE_CNCL_DVSN_CD="01"` 정정의 신/구 ODNO 관계와 **중첩 구간**(비원자성 = 보호 중첩 위험) |
| P-11 | 체결 → 잔고 반영 지연. **주식 전용**(모의는 선물 잔고 미제공 — `client.py:1026` NOTE + 가드 `:1031-1033`). **기본 시장가**(`--stock-order-type market`, `ORD_DVSN=01`) — 지정가는 모의에서 체결되지 않았다(§5.2 주석). 잔고 baseline은 **제출 전**에 읽는다(시장가는 ms 내 체결 → 제출 후 baseline은 자기 체결을 이미 포함, §5.5). 체결 여부는 잔고와 **독립**으로 읽기전용 주식일별주문체결조회(`VTTC0081R`)가 확정하며 `fill_case`는 4상태다. 폴 간격이 `--pace-s`로 하한되므로 산출은 "반영 ≤ 실효 폴 1간격"의 **상한**이지 점추정이 아니다(§8.3) |
| P-13 | 최초 스로틀 지점과 회복 시간. repo의 5/20 rps는 **자가 상한**이지 broker 한도가 아니다 |
| P-14 | 동시 세션 수·구독 상한. `streaming.yaml:50`의 "KIS 제한: 41" 주석을 사실화하거나 반증 |
| P-15 | 1분 내 토큰 재발급 2회 → 거부 코드/메시지 **축자** 확정 |
| P-16 | broker 시각 대 로컬 KST 편차. 시각 미노출이면 그 자체가 결론(BROKER_TIME=UNKNOWN) |
| P-EXT | HTS/MTS 수동 주문의 탐지 지연. push 구독 0건이므로 **폴링 간격이 하한** |
| P-FQP | 취소 직후 late-event 창. 관측 0건은 `0`이 **아니라** "미확립" |
| N-15 | invalidate→재발급 사이 **토큰 공백 창** (계획 §2:68 상호작용 리스크 실측) |
| N-16 | `CTFN6118R` 야간 잔고 응답 **스키마만** 포착 (`tr_ids.yaml` 편입은 별도 커밋) |
| N-17 | 공식 명세 대조 — 주문 요청 필드·TIF·정정취소 값집합 (**§7**) |
| N-18 | 실전 조회 3건: program-trade 행 상한 / SOX 표기 / 야간 코드 응답 |
| P-BAL | 잔고 조회의 **페이지 크기**와 연속조회 키 거동, 그리고 truncation 위험의 **3값 판정**. 런타임은 잔고를 1페이지만 읽고(`client.py:931-932`·`:1055-1056`) 그 사실을 감지할 수단이 없다. 소비자 `services/trading/broker_verification.py`는 잔고에 없는 포지션을 `remove_position(reason="broker_absent")`로 **파괴**한다(`:187-190`) — 지금까지 그 인과는 **추론뿐**이었고 페이지 크기는 한 번도 측정되지 않았다. **1페이지 k행은 페이지 크기 k가 아니다** — `page_size_lower_bound`만 성립 |
| P-NMPR | [필수] 2필드 빈 문자열 vs 명시 코드 A/B — 수락/거부와 등가성 직접 판정. B-arm(빈 값) 거부 = 수정 전 런타임이 계약 위반이었음을 확정 (N-17 소견 2). **수락 동수는 등가성이 아니다** — 조회면이 두 필드를 되돌려주지 않으면 "blank == 01/0"은 UNKNOWN으로 남는다 |

---

## 4. 결과 → broker bounds 10키 / INSTANCE 필드 매핑

### 4.1 bounds 매핑 (설계 #10 `:1168-1171` 10-bullet 전수 = distinct 11키)

`B_external_activity_detect`/`_contain`이 한 bullet을 공유하므로 10 bullet = 11키다.
현재값·semantics·failure_response·measurement_source는 VERIFICATION-PROFILE-002.yaml
직독(행번호 표기).

| bound key | VP-002 행 | 현재값 | semantics | failure_response | measurement_source | 소유 | 공급 프로브 |
|---|---|---|---|---|---|---|---|
| `B_external_activity_detect` | :221 | `null` | hard_maximum | CONTAIN | broker_capability_profile | **broker** | **P-EXT** |
| `B_external_activity_contain` | :230 | 1000 | hard_maximum | CONTAIN | reconciliation_log | our-side | P-EXT (실현가능성 반증만) |
| `B_broker_query_consistency` | :752 | `null` | broker_specific | CONSERVATIVE_UNKNOWN | broker_capability_profile | **broker** | **P-5** (주), P-5b, P-11 |
| `B_final_quantity_proof` | :716 | `null` | broker_specific | QUARANTINE_UNKNOWN | broker_capability_profile | **broker** | **P-FQP** |
| `B_late_fill_observation` | :725 | `null` | broker_specific | PROFILE_CONTRADICTORY | broker_capability_profile | **broker** | **P-FQP** |
| `B_rate_limit_recovery` | :761 | `null` | broker_specific | RESTRICT_OR_CONTAIN | broker_capability_profile | **broker** | **P-13** |
| `B_protective_request_complete` | :743 | `null` | broker_specific | CONTAIN | broker_capability_profile | **broker** | **P-8** |
| `B_startup_reconciliation` | :239 | 60000 | operational_target_and_hard_gate | REMAIN_HALTED | recovery_coordinator_log | our-side | P-11 (실현가능성만) |
| `B_capability_claim_to_send` | :194 | 500 | hard_maximum | QUARANTINE_UNKNOWN | egress_journal_and_broker_transport_trace | our-side | — (egress 소유·프로브 불가) |
| `B_egress_hard_fence` | :203 | 1000 | hard_maximum | HALT | egress_identity_route_session_and_broker_denial_log | our-side | P-15, N-15 (**broker 거부 측면만**) |
| `B_venue_constraint_loss_detect` | :293 | 2000 | source_specific_hard_maximum | STOP_NEW_RISK | venue_constraint_source_and_generation_trace | our-side | — (승인 완료·broker capability 상실은 소스 중 하나) |

**읽는 법**:

- **broker 소유 7키** 중 `value_ms: null`인 6키(`_detect`·`query_consistency`·`fqp`·
  `late_fill`·`rate_limit_recovery`·`protective_request_complete`)가 이 측정 캠페인이
  실제로 채우는 대상이다.
- **our-side 5키는 이미 APPROVED**다. 프로브는 이 값들을 *바꾸지 않는다.* 할 수 있는
  일은 **실현가능성 반증**뿐 — 예: P-EXT의 탐지 지연이 이미 승인된
  `B_external_activity_contain: 1000`과 합쳐 Hard Safety Envelope를 넘기면, 그것은
  detect 값의 문제가 아니라 **봉투 자체의 모순**으로 보고해야 한다.
- 프로브가 공급하지 못하는 2키(`B_capability_claim_to_send`·
  `B_venue_constraint_loss_detect`)를 **커버한 것처럼 기록하지 말 것.**
  `python -m tools.broker_probes.run --coverage`가 이 사실을 기계적으로 출력한다.

### 4.2 인접 키 (10-bullet 밖 — 과대 커버리지 주장 방지)

`registry.py::ADJACENT_BOUND_KEYS`에 별도 등재: `B_protection_gap`(:788)·
`B_protection_overlap`(:797)은 P-8이 **부분 정보만** 준다.
`B_non_trade_event_detect`(:815)·`B_non_trade_reconcile`(:833)은 corporate-action
표면이 repo에 부재(grep 0)하여 **정의된 프로브가 없다.**
`B_post_trade_effect_to_obligation_commit`(:662)는 우리 측 경로로 승인 완료.

### 4.3 INSTANCE 필드 매핑

**갭 해소 완료(Patch-0057, 2026-07-29)**: 아래 표에 "부재"는 더 이상 없다. §9.1이
보고한 8건은 **신설 6 + 재매핑 2**로 처분됐고, 재매핑 2건은 원래 이름 대신 **기존 키**를
기입면으로 쓴다(한 사실에 이름 둘을 만들지 않는다). 처분 근거는 §9.1.

| 프로브 | INSTANCE 필드 (`KIS-BROKER-CAPABILITY-PROFILE-draft.yaml`) | 상태 |
|---|---|---|
| P-1 | `capabilities.client_generated_order_id.status` | 존재 |
| P-2 | `capabilities.submission_idempotency.status` / `.deduplication_window_ms` | 존재 |
| P-5 | `capabilities.open_order_query.eventual_consistency_bound_ms` / `.status` | 존재 |
| P-5b | `capabilities.open_order_query.completeness` / `.pagination` | 존재 |
| P-8 | `capabilities.replace_semantics.mode` / `.status` | 존재 |
| P-11 | `capabilities.position_balance_margin.consistency_model` | 존재 |
| P-13 | `capabilities.rate_limits.hard_limits` / `.scope` / `.sustained_and_burst_semantics` | 존재 |
| P-14 | `capabilities.sessions.concurrent_sessions` | 존재 |
| P-14 | `capabilities.sessions.subscription_limit` | 존재 — **Patch-0057 신설** (`null`) |
| P-15 | `capabilities.credentials_and_revocation.reissue_rejection_semantics` | 존재 — **Patch-0057 신설** (`UNKNOWN`) |
| P-16 | `capabilities.broker_time.timezone` / `.precision` | 존재 |
| P-16 | `capabilities.broker_time.skew_bound_ms` | 존재 — **Patch-0057 신설** (`null`) |
| P-EXT | `external_activity.detection_bound_ms` / `.containment_bound_ms` | 존재 |
| P-FQP | `final_quantity_proof.recipes[]` / `.late_event_window_ms` | 존재 |
| N-15 | `capabilities.credentials_and_revocation.token_blackout_window_ms` | 존재 — **Patch-0057 신설** (`null`) |
| N-16 | `capabilities.position_balance_margin.evidence_refs` (+ `.status`) | 존재 — **재매핑** (was `schema_captured`) |
| N-17 | `live_scope.time_in_force_values` | 존재 |
| N-17 | `capabilities.command_construction_and_wire_semantics.required_and_default_field_semantics` (+ `.duplicate_unknown_and_omitted_field_behavior`, `.unit_multiplier_currency_and_numeric_encoding`) | 존재 — **재매핑** (was `field_inventory`) |
| N-17 | `capabilities.replace_semantics.value_set` | 존재 — **Patch-0057 신설** (`[]`) |
| N-18 | `capabilities.market_and_instrument_constraints.instrument_coverage` | 존재 — **Patch-0057 신설** (`UNKNOWN`) |
| P-NMPR | `capabilities.command_construction_and_wire_semantics.required_and_default_field_semantics` (+ `.duplicate_unknown_and_omitted_field_behavior`) | 존재 — N-17 재매핑분과 **동일 기입면** (§9.1 #8) |
| P-BAL | `capabilities.position_balance_margin.evidence_refs` (+ `.status`) | 존재 — **전용 슬롯 부재** (§9.4) |

> P-NMPR은 N-17이 **문서로** 확정한 것(두 필드가 [필수]다)을 **실측으로** 보강한다
> — 같은 기입면에 들어가되 근거 등급이 다르다(OFFICIAL-DOC vs 실측). 기입 시
> `_kis.measurement`와 `evidence_refs`를 분리해 적어 두 근거가 뭉개지지 않게 할 것.
>
> **P-NMPR은 `live_scope.time_in_force_values`를 채우지 않는다.** 두 arm 모두
> `KRX_NMPR_CNDT_CD` ∈ {`0`(없음), 빈 값}만 보내고 `3`(IOC)·`4`(FOK)는 **전송하지
> 않는다.** TIF 값집합 확정은 N-17(§7 항목 2) 소관이다 — §4.1의 "공급하지 못하는 키를
> 커버한 것처럼 기록하지 말 것"이 여기에 그대로 적용된다.

> **P-BAL은 전용 기입면이 없다 — 신설 여부는 이 런북의 권한이 아니다.**
> `open_order_query`에는 `.completeness`/`.pagination` 2키가 있으나(INSTANCE 초안
> `:3294`·`:3296`) `position_balance_margin`에는 **둘 다 없다**(`:1290-1305` /
> `:3374-…`). 따라서 P-BAL 산출은 N-16의 Patch-0057 재매핑과 **같은 방식**으로
> `evidence_refs`(+ `.status`)에 들어간다. 이는 임시 처분이며 §9.1과 **같은 결함
> 클래스**다 — §9.4에 미처분 항목으로 등재했다. `registry.py`는 없는 필드명을
> **발명하지 않는다**.

---

## 5. 실행 순서와 리스크 규율

### 5.1 원칙

**조회 → 토큰 → 주문** 순. 파괴력이 낮고 되돌릴 수 있는 것부터 한다. 앞 단계가
실패하면 뒤 단계는 **해석 불가**가 되므로 (예: 조회 경로가 안 되면 P-5의 t1을 정의할
수 없다) 순서는 편의가 아니라 **의존성**이다.

### 5.2 모의투자 캠페인 순서

| 순서 | 프로브 | 왜 이 자리인가 | 선행 조건 |
|---|---|---|---|
| 0 | **P-1** | 오프라인. 네트워크 없이 코드 사실만 기록 | 없음 |
| 1 | **P-16** | 조회 전용. 인증 경로와 시각 기준선을 먼저 확립 | `--symbol` |
| 2 | **P-13** | 조회 클래스 rate 측정. 이후 모든 프로브의 호출 예산 판단 근거 | **페이퍼 정지** |
| 3 | **P-15** → **N-15** | 토큰 계열. 연속 실행(둘 다 재발급을 소모) | 앱키 공유 워커 **전부 정지** |
| 4 | **P-14** | WS 세션. 스트리밍 워커 축출 위험 | 스트리밍 워커 정지 |
| 5 | **P-5** | 주문 계열 첫 단추. 이후 P-5b/P-8/P-FQP의 관측 경로를 검증 | 모의 개장·선물 계좌 |
| 6 | **P-5b** | P-5가 만든 이력이 있어야 페이지 경계가 생김 | P-5 선행 |
| 7 | **P-2** | 중복 전송. 실패 시 미체결 2건이 남을 수 있어 정리 여유 필요 | 모의 개장 |
| 8 | **P-NMPR** | A/B 2건 모두 미체결로 남긴 뒤 취소. P-5 의존 없음 — P-2와 같은 "모의 개장·선물 계좌"만 필요하므로 정리 부담이 비슷한 이 자리 | 모의 개장·선물 계좌 (`--asset futures`) |
| 9 | **P-8** | 정정. 신/구 ODNO 2건이 동시 생존할 수 있음 | P-5 선행 |
| 10 | **P-FQP** | 취소 후 창 관측. 가장 김 | P-5 선행 |
| 11 | **P-EXT** | 운영자 수동 개입 필요. 반복 ≥5회 | 운영자 HTS/MTS 대기 |
| 12 | **P-11** | **의도적 체결**. 포지션이 남는다 — 마지막에 배치 | `--asset stock` · `--allow-fill` (주문구분은 기본 **시장가**) |

> **P-11은 시장가로 낸다** (`--stock-order-type` 기본값 `market`,
> `ORD_DVSN=01` 시장가 · `ORD_UNPR=0`). 지정가는 **모의투자에서 체결되지 않았다**:
> 아티팩트 `P-11-20260730T002715Z`는 터치(211,000) 대비 +10%를 호가단위로 정확히
> snap 한 지정가(`ORD_DVSN=00`, `ORD_UNPR=232500`)로 **접수까지 성공**했으나
> (`rt_cd=0`, ODNO `0000008686`) 잔고는 30초 창 안에서 움직이지 않았고, 약 18분 뒤
> 장외 재조회에서도 기준 보유량 그대로였다. 즉 CENSORED의 원인은 잔고 지연이 아니라
> **미체결**이었고, P-11은 실제 모의 주문 1건을 쓰고 측정값을 얻지 못했다.
> `--stock-order-type limit`으로 옛 형태를 재현할 수 있다(비교용).
>
> 시장가 경로는 시세 조회를 하지 않으므로 호가단위에 **의존하지 않는다**(§5.5) —
> `--price-offset-pct`와 snap은 지정가 경로 전용이다. 잔고 폴링 창은
> `--balance-timeout-s`(기본 120초)이며, 만료는 여전히 **CENSORED**로 남는다.
> 관측되지 않은 반영을 측정값으로 바꾸지 않는다. 어느 경우였는지는 아티팩트
> `measurements.fill_case`가 명시한다 — 체결+반영(`FILLED_AND_REFLECTED`)이거나,
> 구분 불가(`UNDETERMINED_NON_FILL_OR_LAG_BEYOND_WINDOW`, 미체결과 창 초과 지연이
> 잔고만으로는 동일하게 보임)이며 후자에는 무엇이 있으면 판별되는지가 함께 적힌다.

### 5.3 rate-limit 프로브(P-13) 특칙

- **점진 상승만**: `--start-rps`(1) → `--step-rps`(1)씩, 각 단계 `--hold-seconds`(3) 유지
- **즉시 중단**: 최초 429 / `EGW00201` 신호에서 램프 전체를 멈춘다. 한계 돌파 모드도,
  스로틀된 호출의 자동 재시도도 **없다**
- **상한 고정**: `--max-rps`(기본 25)를 넘지 않는다. 상한까지 신호가 없으면 결론은
  "한도는 시험 천장보다 **위**" 이며, **천장을 한도로 기록하지 않는다**
- **회복 측정은 단발 간격 호출**로만 (버스트 금지)
- `--endpoint-class`는 `query`만 구현돼 있다. `submit`/`cancel` 클래스는 주문을
  발생시키므로 **별도로 리뷰된 전용 실행**이 필요하다 (HIGH risk)
- 보고 규율: `highest_clean_rps`는 broker 한도의 **하한**, `throttled_at_rps`는
  **상한**이다. 점추정이 아니라 **구간**으로 기록한다

### 5.3.1 주문 계열 프로브의 호출 간격 강제 (`--pace-s`)

P-13이 측정한 구간(clean 하한 **1.0 rps** / 스로틀 상한 **2.0 rps**, `EGW00201`,
아티팩트 `P-13-20260729T063120Z`)은 주문 계열 프로브에도 그대로 적용된다. 이 계좌에서는
호가 조회 직후 주문 전송처럼 **두 호출을 연달아 보내는 것만으로 이미 clean 구간을 벗어난다.**

- **강제 지점**: `MockTradingClient`의 단일 전송 지점에서 `--pace-s`(기본 **1.1초**)
  간격을 **모든 호출 종류**(호가·주문·취소·정정·조회)에 적용한다. 기본값 1.1초는 추정이
  아니라 P-13이 측정한 clean 상한(1.0 rps) 바로 위 값이다.
- **왜 "예의"가 아니라 필수인가**: 한도를 넘긴 주문은 측정값을 흔드는 게 아니라
  **측정을 무효화한다.** 미적용 상태로 실행된 `P-5-20260729T235001Z`는 trial 0에서
  `초당 거래건수를 초과하였습니다`로 거부되어 `n=0` · `NOT_MEASURED`로 끝났다.
- **`--poll-ms`는 조용히 올림된다**: 페이싱 간격보다 작은 `--poll-ms`·`--gap-ms`는
  실제로 일어나지 않는다. 따라서 아티팩트의 `poll_granularity_ms`·`poll_interval_ms`·
  `gap_ms`는 요청값이 아니라 **실효값** `max(--poll-ms, --pace-s)`로 기록된다. 요청값을
  기록하면 §8.3의 가산 오차를 과소평가하게 되고, 그 방향의 오류가 곧 **fail-open**이다.
- **레이턴시 창은 오염되지 않는다**: 페이싱 sleep은 전송 **직전**에 끝나고 t0은 그
  이후에 찍힌다(`MockTradingClient.last_send_instant()`). P-5/P-8/P-11/P-FQP의 t0은
  모두 이 값을 쓰므로 페이싱 대기가 broker 레이턴시로 계상되지 않는다. 호출 앞에서
  `time.monotonic()`을 찍는 형태로 되돌리면 표본마다 약 `--pace-s`만큼 부풀려진다.
- **그래도 스로틀이 보이면 보고한다**: 페이싱을 적용한 실행에서 여전히
  `초당 거래건수를 초과` 또는 `EGW00201`이 나오면 **재시도하지 말고** §5.5에 따라
  보고한다. 측정된 한도와 관측이 불일치한다는 뜻이므로, 한도 가정 자체를 다시 세워야 한다
  (자동 재시도는 P-13 특칙과 동일하게 **없다**).
- **`--pace-s`를 낮추는 것**은 위 실패를 다시 여는 행위다. P-2에서 `--pace-s`보다 짧은
  gap을 시험해야 할 때만 의도적으로 내리고, 그 사실을 아티팩트 `note`에 남긴다.

### 5.4 실전 조회 절차 (N-16 · N-18 · P-BAL) — 분리 실행

1. **운영자 승인**을 먼저 받는다 (실전 자격증명 소비)
2. **별도 셸**에서 실전 자격증명을 export한다 (§2.2 경고)
3. N-16은 **야간 세션 18:00–05:00 KST** 안에서만 실행한다. 창 밖에서는 프로브가
   스스로 거부한다 (`--ignore-session-window`로 강행 시 아티팩트에 라벨 필수)
4. 두 프로브 모두 **GET + allowlist**로 구조적 조회 전용이다. 모듈에 주문 경로가
   존재하지 않는다
5. 실행 후 그 셸을 **종료**한다. 실전 자격증명이 남은 셸에서 모의 프로브를 돌리지 않는다
6. N-16 결과에 따른 `config/kis/tr_ids.yaml` 편입은 **별도 커밋**이다
7. **P-BAL(`--env real`)도 이 절차에 종속된다.** 야간 창 제약은 없고(주간 잔고 TR)
   대상별 자격증명 배선과 계좌 지문 대조가 추가로 필요하다 — **§5.6**

### 5.5 사고 시 대응

- **미체결 잔여**: 프로브는 `finally`에서 자기가 만든 주문을 취소하고, 실패하면
  ODNO를 찍고 `errors[]`에 남긴다. `CLEANUP FAILED`가 보이면 **HTS/MTS로 수동 취소**
- **P-11 포지션 잔존**: 프로브는 청산하지 않는다. 모의 계좌에서 수동 청산
- **`호가단위 오류`** (`모의투자 주문처리가 안되었습니다(호가단위 오류)`, `rt_cd=1`):
  지정가가 해당 종목의 호가단위 배수가 아니라는 뜻 — 주문이 아예 접수되지 않으므로
  그 trial은 열화가 아니라 **표본 0**이다(`P-5-20260730T000608Z.json`). 프로브의
  지정가는 선물은 `config/execution.yaml::futures_contract_spec`의
  `tick_size_points`(심볼 prefix로 해석: `A01`/`101`→full, `A05`→mini), 주식은
  broker가 응답한 호가단위(TR `FHKST01010100`의 `output.aspr_unit`)로 snap 되며,
  snap 방향은 항상 **터치 반대쪽**(resting은 미체결 유지, P-11은 체결 유지)이다.
  사용한 tick과 출처는 아티팩트 `measurements.limit_price_tick`에 남는다.
  이 거부가 다시 보이면 **가격을 손으로 조정해 재시도하지 말고 그대로 보고한다** —
  tick 출처(YAML 등록 누락 / broker 미응답)가 원인이므로 손댄 가격은 증거를 오염시킨다.
  주식에서 호가단위를 확정할 수 없으면 프로브는 `ProbeError`로 멈춘다. 단 **P-11의
  기본 경로(시장가)는 지정가를 보내지 않으므로 호가단위를 조회조차 하지 않는다** —
  이 거부에 걸리는 것은 `--stock-order-type limit`뿐이다. 시장가 실행의
  `measurements.limit_price_tick`은 `applicable: false`로 남아 tick 기계를 의도적으로
  우회했음을 기록한다(키를 비우지 않는다)
- **주문은 수락됐고 취소도 되는데 조회에서 영원히 안 보임** → 브로커 정합성 문제로
  결론짓기 전에 **ODNO 정규화를 먼저 의심한다.** 두 표면의 인코딩이 다르다:
  수락 응답은 `output.ODNO`를 **0 패딩**(`"0000000762"`)으로, `inquire-ccnl` 행은
  같은 주문을 **공백 패딩·선행 0 제거**(`"        762"`)로 돌려준다
  (`P-5-20260731T002112Z`). `.strip()` 문자열 비교는 `"762" == "0000000762"`를
  묻는 셈이라 **항상 거짓**이고, 그 결과는 30초 폴링 후 censored·`n=0`인데 **같은
  ODNO의 정리 취소는 성공**한다 — 이 조합이 곧 진단 지문이다. 현재는
  `odno_key()`가 양쪽을 런타임과 동일 규칙
  (`shared/execution/executor.py::_normalize_odno`)으로 정규화한다. 비교만
  정규화하며, 취소는 브로커가 수락한 형식인 **0 패딩 원문**을 그대로 보낸다.
  이 지문이 다시 보이면 폴링 창을 늘리지 말고 **정규화 경로를 확인**하라 —
  창 확대는 증상을 늦출 뿐이다
- **주문이 체결됐는데 잔고 폴링이 영원히 censored** (P-11) → 창을 늘리기 전에
  **측정 순서를 의심한다.** 지문: `fill_case`가 UNDETERMINED인데
  `baseline_holding_qty == final_holding_qty`이고 폴 수가 창을 다 소진했다
  (`P-11-20260731T015709Z`: baseline 1 / final 1 / 95 polls / 120 s). 원인은
  브로커 지연이 아니라 **잔고 baseline을 제출 후에 읽은 것**이다 — 시장가는 ms 내
  체결되므로 그 baseline에는 프로브 자신의 체결이 이미 들어 있고, `qty > base_qty`는
  창 길이와 무관하게 **영원히 참이 되지 않는다**. 같은 주문은 실제로 체결돼 있었다:
  읽기전용 주식일별주문체결조회(`VTTC0081R`, ODNO `0000018925`,
  `ord_dvsn_name=시장가`, `tot_ccld_qty=1`, `rmn_qty=0`, `cncl_yn=N`, 248,500,
  `ord_tmd=105710`)와 정확히 그 금액만큼의 예수금 변동이 이를 확정했다.
  현재 P-11은 (a) baseline을 **제출 전**에 읽고, (b) 폴링과 **독립적으로** 그
  체결조회를 1회 호출해 `fill_case`를 4상태로 판정한다 — 체결+반영 / 체결+창 내
  미반영(정직한 음성) / 미체결(측정 대상 없음 — censored가 아니라 **부재**) /
  조회 불가(UNDETERMINED, 무엇이 없는지 명시). 이 지문이 다시 보이면
  `--balance-timeout-s`를 늘리지 말고 **baseline이 제출 전에 읽히는지 확인**하라.
  덧붙여 폴 간격은 `--pace-s`로 하한되므로 첫 폴에서 이미 반영된 반영은
  `measurements.resolution_floor`가 **탐지 하한**으로 표시한다 — 그 값(~1100 ms)을
  측정된 지연으로 bound에 넣지 말 것(§8.3)
- **`SafetyViolation`**: 아티팩트를 쓰지 않고 exit 3. 관측이 일어나지 않았으므로
  기록할 것이 없다는 뜻이다 — 재시도하지 말고 **원인을 먼저 밝힌다**
- **exit code**: 0 정상 / 2 미지 프로브 / 3 안전 위반 / 4 선행조건 미충족 /
  5 실행 실패(**아티팩트는 남는다** — 조용한 실패를 "미실행"으로 오인하지 않기 위함)

### 5.6 P-BAL 실행 절차 (잔고 페이지네이션) — 대상 3종

#### 목적

측정 대상은 **잔고 조회의 페이지 경계**다. `shared/kis/client.py`는 잔고를
1페이지만 읽는다 — 주식은 빈 `CTX_AREA_FK100`/`NK100`을 보내고(`:931-932`), 선물은
빈 `CTX_AREA_FK200`/`NK200`을 보내며(`:1055-1056`), 어느 쪽도 응답의 연속조회 키를
읽지 않고 `tr_cont` 응답 헤더를 보지 않고 행 수를 세지 않으며 성공 경로에 로그가
없다. 올바른 walk는 **같은 파일에 이미 있다**(`:303-356` `fetch_invest_opinion`,
`tr_cont != "M"`까지 루프 — `:354`).

이것이 왜 위험한가: `services/trading/broker_verification.py`가 그 잔고를 소비하고
(`:78` 주식 / `:80` 선물), `remove_redis_only`가 켜진 경우(`:105`, 게이트
`:121-127`) 잔고에 없던 포지션을 `remove_position(reason="broker_absent")`로
**트래킹에서 제거**한다(`:187-190`). 읽기가 절단됐다면 페이지 경계 밖의 실보유
포지션은 "부재"와 구분되지 않는다. **이 인과는 현재 추론뿐이며 페이지 크기는 한 번도
측정된 적이 없다.** P-BAL이 그 하나를 측정한다.

#### 선행 조건

- **조회 전용**이다. `probes_balance.py`에는 주문 경로가 없고 POST/PUT/PATCH/DELETE
  리터럴조차 없다(§2.3 강제 5, AST 테스트로 강제). 그래도 `--confirm` 없이는 브로커에
  접촉하지 않는다 — 이 하네스의 모든 네트워크 프로브와 동일 규율이다.
- **`--env real`은 운영자 승인이 먼저다** (실전 자격증명 소비). §5.4의 분리-셸 규율이
  그대로 적용된다: 실전 자격증명을 export한 셸에서 모의 프로브를 돌리지 않고, 실행 후
  그 셸을 종료한다.
- **포지션을 실제로 보유한 계좌**여야 한다. 0행은 "단일 페이지"도 "위험 없음"도
  아니고 **아무것도 확립하지 않는다**(프로브가 명시 `skip`을 남긴다).
- 페이퍼 워커 정지는 **불필요**하다. 주문을 내지 않고 호출이 `--max-pages`회(기본 10)
  뿐이며 페이지 간 간격이 `--inter-page-s`(기본 1.1초, P-13 측정 clean 1.0 rps 바로
  위)로 하한된다. 그래도 `EGW00201`이 보이면 §5.5대로 **재시도하지 말고 보고**한다.
- **자산 교차 배선 금지.** `resolve_credentials`는 `KIS_STOCK_*` / `KIS_FUTURES_*`
  접두를 자산별로 읽으므로 정상 배선에서는 교차가 구조적으로 불가능하다. **단
  자산별 변수가 없고 legacy `KIS_APP_KEY`/`KIS_APP_SECRET`만 export된 셸에서는 폴백이
  두 자산에 동일 키를 공급한다**(`common.py:297-304`) — P-BAL 실행 시에는 반드시
  **자산별 변수를 export**하고 legacy 폴백에 의존하지 말 것.

#### 대상별 명령과 자격증명 배선

자격증명 census는 캠페인 README
(`docs/broker-profiles/evidence/2026-07-29-p02-t2-campaign/README.md` §wave-3 배선
검증 + 2026-07-31 세션)에서 확정된 것이다. **프로브는 자격증명 파일 경로를
하드코딩하지 않는다** — 아래 파일을 소싱해 환경에 올리는 것은 운영자의 단계다.

| # | 대상 | 명령 | 소싱할 파일 |
|---|---|---|---|
| 1 | **실전 주식** (중요한 대상) | `python -m tools.broker_probes.run P-BAL --asset stock --env real --confirm` | 호스트의 유일한 실전 자격증명 = **주식 앱키** (`KIS_STOCK_APP_KEY`/`_APP_SECRET`, `.env`; `.env`의 legacy `KIS_APP_KEY`는 이 값을 가리키는 `${...}` placeholder) |
| 2 | 모의 주식 | `python -m tools.broker_probes.run P-BAL --asset stock --env mock --confirm` | 레포 밖 `/home/deploy/.config/kis-probes/p11-mock-stock.env` (권한 600, 계좌 `50187672-01`) |
| 3 | 실전 선물 | `python -m tools.broker_probes.run P-BAL --asset futures --env real --confirm` | `.env.paper`의 `KIS_FUTURES_*` (2026-07-29 발급된 실전 키, 계좌 지문 `00bcc5b3a87b`) |
| — | 모의 선물 | (실행해도 됨 — 자동 **SKIP**) | 없음. 브로커가 모의에서 선물 잔고를 서비스하지 않는다 (`client.py:1026` NOTE + 가드 `:1031-1033`). 오류가 아니라 스킵으로 남으며, **"위험 없음"으로 읽으면 안 된다** |

> **⚠ 실행 전 반드시 확인 — 이 런북이 확정하지 못한 항목.** 캠페인 census가 확립한
> 것은 "호스트의 실전 앱키는 **주식** 앱키다"까지다. **어느 파일이 실전 주식 계좌
> 번호(`KIS_STOCK_ACCOUNT_NO`)를 담는지는 확립되지 않았다** — 모의 주식 계좌
> `50187672-01`과 혼동될 여지가 있다. 대상 #1을 돌리기 전에 export된 계좌를 확인하고,
> 실행 후 아티팩트의 `credentials.account_masked` / `account_fingerprint`가 의도한
> 실전 주식 계좌인지 **대조**한다. 지문이 다르면 그 아티팩트는 다른 계좌의 관측이므로
> 인용 금지다. (실전 도메인에 모의 앱키를 쓰면 trading 계열은 `EGW02004`로 거부되므로
> 그 방향의 오배선은 시끄럽게 실패한다. 반대로 **맞는 앱키 + 다른 계좌**는 조용히
> 성공하므로 지문 대조가 유일한 방어다.)

선택 인자:

- `--max-pages`(기본 10) — 상한. 여기서 멈추면 종료 원인이 **우리 캡**으로 기록되고
  총 행수는 보고되지 않는다.
- `--known-page-size` + `--known-page-size-source` — 이전 측정의 페이지 크기를
  들여올 때만. **출처 없이는 `ProbeError`로 거부**되며, 이번 실행에서 측정된 값이
  있으면 항상 측정값이 이긴다(불일치는 `page_size_disagreement`로 보고).
- `--record-raw-continuation-keys` — 연속조회 커서 원문을 아티팩트에 넣는다. 기본
  꺼짐(커서는 브로커 불투명 값이고 `redact()`는 그 필드명을 모른다). 기본 상태에서도
  키별 **지문**이 기록되므로 "이 키가 전진했는가"는 답할 수 있다.

#### 확립하는 것

1. **페이지 1 행 수** — 원시 행 수와, 런타임이 실제로 보게 되는 행 수
   (`hldg_qty > 0` 주식 `client.py:1002` / `cblc_qty > 0` 선물 `:1091`)를 **분리
   기록**한다. 페이지네이션은 원시 행 단위이지만 파괴적 소비자는 필터된 행만 본다.
2. **연속조회 거동** — 비어있지 않은 연속조회 키가 돌아왔는지, **어디서** 발견됐는지
   (`body:ctx_area_fk100` 등 실제 스펠링·위치를 기록 — 런타임이 이 키를 읽지 않으므로
   레포에 케이싱 증거가 없다), 그리고 `tr_cont` **응답 헤더** 값. 헤더는 이 모듈의
   `_get()`이 트랜스포트에서 직접 읽는다 — `common.http_json`은 응답 헤더를 버리므로
   그 헬퍼로는 이 질문에 답할 수 없다. `"M"`만 "더 있음"으로 해석하고(`client.py:354`
   근거) 다른 값은 **축자 기록**한다.
3. **walk** — 페이지별 행 수와 **키별** 전진 여부. 두 키를 **매 페이지 각각** 기록한다
   — 이전 캠페인에서 두 키 중 **하나만** 움직인 사례가 있었고, boolean 하나로는 그것이
   사라진다. 한쪽만 전진한 페이지는 `continuation_key_asymmetry`에 모인다.
4. **종료 원인** — `BROKER_END_OF_SET` / `OUR_MAX_PAGES_CAP` / `ERROR` 중 하나로
   **명시**. 이 구분이 프로브의 요점이다: P-5b는 우리 캡에서 멈춰 총 행수를 미확립으로
   남겨야 했다. **캡으로 끝난 walk는 총 행수를 절대 보고하지 않는다** — 하한만 남는다.
5. **truncation 위험 3값 판정** (`measurements.truncation_risk.verdict`):
   `TRUNCATION_RISK_DEMONSTRATED`(관측 행수가 페이지 크기를 초과 — 인과가 추론에서
   실증으로 이동) / `TRUNCATION_RISK_NOT_DEMONSTRATED`(페이지 크기가 알려져 있고
   **브로커가** end-of-set을 알린 지점이 그 아래) / `TRUNCATION_RISK_UNESTABLISHED`.
   판정은 관측에서 **계산**되며 자기신고가 아니다.

#### 확립하지 **않는** 것

- **소액 계좌에서는 페이지 크기를 확립할 수 없다.** 8행 1페이지는 페이지 크기 ≥ 8인
  **모든** 값과 정합한다. 아티팩트는 이 경우 `page_size: null` ·
  `page_size_lower_bound: 8` · `verdict: TRUNCATION_RISK_UNESTABLISHED`로 남는다.
  이것을 "페이지 크기 = 8"이나 "절단 위험 없음"으로 옮겨 적는 것은 **§8.4 위반**이다.
- **`NOT_DEMONSTRATED`는 코드의 속성이 아니다.** 그것은 *이 계좌의 현재 보유량*에 대한
  경계이고 포지션이 하나 열리는 순간 만료된다. `client.py:931-932`의 결함은 그대로다.
- **우리 캡에서 멈춘 walk는 총 보유량을 확립하지 않는다.** "지금까지 본 행수가 페이지
  크기보다 적다"는 "보유량이 적다"의 증거가 **아니다** — 그 방향의 결론이 곧
  fail-open이며 프로브는 그 조합을 `UNESTABLISHED`로 강제한다.
- **파괴적 분기를 바꿀 근거가 되지 않는다.** `remove_redis_only`
  (`broker_verification.py:105`·`:187-190`)는 이 아티팩트만으로 손대지 않는다.
  `verdict: DEMONSTRATED`가 나왔다면 그것은 **수정 근거의 시작**이고, 수정 자체는
  `client.py`의 continuation walk 부재를 고치는 별도 변경이다.
- **MOCK 관측의 REAL 외삽 금지.** 모의 주식 페이지 크기는 실전 페이지 크기에 대해
  아무것도 말하지 않는다(ADR-002-004 §13.14 / §6.2 마지막 항목).
- **거부된 호출은 아무것도 확립하지 않는다.** `rt_cd != "0"`이면 종료 원인은 `ERROR`이고
  판정은 `UNESTABLISHED`다.

#### 아티팩트 처리

- 경로·`artifact_id` 규칙과 `UNAPPROVED_CANDIDATE` 규율은 §6.1과 동일하다.
- **인용 전 §6.2 체크리스트 전건**, 특히 `environment`가 `--env`와 일치하는지
  (P-BAL은 spec 값 대신 실제 접촉 환경을 기록한다) 와 `credentials.account_fingerprint`
  대조(위 ⚠ 항목).
- `results/`는 gitignored이므로 §6.3대로 **승인 패키지로 복사**한 뒤 `evidence_refs`에
  `artifact_id` + 보존 위치를 함께 적는다.
- 기입면은 §4.3의 `capabilities.position_balance_margin.evidence_refs`(+ `.status`)이며
  전용 pagination 슬롯은 **부재**다(§9.4). 값 승격은 자동이 아니다(§6.4).

---

## 6. 결과 기입 절차

### 6.1 아티팩트

경로: `tools/broker_probes/results/{probe_id}-{YYYYMMDDTHHMMSS}Z.json`
(= `artifact_id`). 포함: `mode`·`environment`·`repo_commit`·`credentials`(마스킹·
지문)·`measurements`·`observations`·`skips`·`errors`·`targets`.

모든 아티팩트는 `approval_status: UNAPPROVED_CANDIDATE`로 태어난다. 이 값을 손으로
고치는 것은 절차가 아니다 — 승인은 아티팩트 밖에서 사람이 한다.

### 6.2 인용 적격성 (기입 전 필수 확인)

아래를 **전부** 만족해야 INSTANCE에 인용할 수 있다.

- [ ] `mode: "live"` — `dry-run` 아티팩트는 관측이 아니다
- [ ] `provenance_class: "MEASURED"`
- [ ] `errors: []` — 에러가 있으면 부분 관측이므로 사유와 함께만 인용
- [ ] `skips[]` 검토 — 명시적 스킵은 결측이지 음성이 아니다
- [ ] `repo_commit`이 캠페인 커밋과 일치
- [ ] `environment`가 기입 대상 문서와 일치 (**MOCK_VTS 아티팩트를 REAL_PROD 문서에
      인용 금지** — ADR-002-004 §13.14)

> **예외**: P-1은 오프라인 구조 프로브라 `mode: "live"`·`MEASURED`로 나오지만
> `environment: NONE`이다. 이는 "broker를 측정했다"가 아니라 "**repo 코드 사실을
> 측정했다**"는 뜻이다. P-1 단독으로 capability status를 승격할 수 없다 (판정은 N-17).

### 6.3 증거 보존 (`results/`는 gitignored)

`evidence_refs`가 gitignore된 경로를 가리키면 리뷰어가 재현할 수 없다. 인용 전에
아티팩트를 **승인 패키지로 복사**하고, `evidence_refs`에는 `artifact_id`와 그
보존 위치를 함께 적는다.

### 6.4 INSTANCE 기입

1. 해당 capability 블록의 `_kis.measurement`를 3분류 중 하나로 갱신
   (`CODE-EVIDENCED` / `OFFICIAL-DOC` / `NEEDS-LIVE-MEASUREMENT`) — 실측 완료 시
   `NEEDS-LIVE-MEASUREMENT`에서 벗어난다
2. `evidence_refs[]`에 `artifact_id` 추가
3. `status` / `assurance_level` 승격은 **자동이 아니다**:
   - 측정 1건이 `LEVEL_2_CONTROLLED_TEST_VERIFIED`를 보장하지 않는다 —
     "설계된 통제 시험"이어야 한다
   - `VERIFIED_WITH_RESTRICTION`은 `restriction_approved: true`라는 **명시 승인**이
     동반돼야 한다
4. 값이 확립되지 않았으면 **`null`을 유지**한다. "관측 0건"은 `0`이 아니다
   (VP-002:756 — 창 안의 부재는 비존재의 증명이 아니다)

### 6.5 bound 값 기입 — Bounds-Approver 전용

`VERIFICATION-PROFILE-002.yaml`의 `value_ms`를 쓰는 행위는 **Bounds-Approver의
독점 권한**이다 (Live-Armer와 분리 — IMPLEMENTATION-PLAN §3). 프로브가 내놓는
`recommended_bound_ms`는 `candidate_only: true`가 붙은 **후보**일 뿐이다.

승인 신청 시 함께 제출:

- `artifact_id`(들) 및 보존 위치
- `n`(표본 수)과 관측 창 — 작은 표본의 최대값은 참 최대값을 **과소평가**한다
- 폴링/헤더 해상도 등 **가산 오차항** (예: P-5는 표본마다 최대 1 폴 간격의 오차)
- `applicable_scope` — 계좌·세션·엔드포인트 클래스·자산·환경
- censored(미관측 종료) trial 수 — **버리지 말고 보고한다**

---

## 7. N-17 명세 대조 체크리스트

N-17은 스크립트가 아니라 **문서 대조**다. 모의서버가 필요 없고, 측정으로는 답이
나오지 않는다 (필드의 *부재*는 요청을 보내서 확인할 수 없다).

**수단**: `kis-code-assistant-mcp` (과거 실적 있는 경로). 재가동 불가 시 공식 문서
수동 대조 — 이는 실행 계획 §1 T3의 **결정 D6**에 종속된다.

**원전**: KIS 공식 API 포털 / `github.com/koreainvestment/open-trading-api`.
pykis·mojito 등 2차 커뮤니티 원천은 **값 확정 근거로 쓰지 않는다**.

### 대조 항목 (전수)

| # | 항목 | 확정 대상 | 현재 상태 | 관련 |
|---|---|---|---|---|
| 1 | **주문 요청 필드 전수** — 클라이언트 주문번호 필드 존부 | `capabilities.client_generated_order_id.status` UNKNOWN → UNSUPPORTED/VERIFIED | UNKNOWN. 우리는 안 보냄(P-1 grep 0) — 하지만 **broker가 제공하지 않는다는 증거는 아님** | P-1 |
| 2 | **TIF 허용값 집합** | `live_scope.time_in_force_values` | 빈 리스트 | — |
| 3 | **`RVSE_CNCL_DVSN_CD` 값집합** | 정정/취소 코드 전수 (우리는 `"01"`/`"02"`만 사용) | 코드에 2값만 등장 | P-8 |
| 4 | **`ORD_DVSN`(주식) / `ORD_DVSN_CD`(선물) 값집합** | 주문유형 코드계가 자산군 간 다름(주식 `01`=시장가 vs 선물 `01`=지정가). 미지 값을 `"01"`로 조용히 폴백하던 동작은 **제거됨** — 양 경로 모두 명시 테이블 매핑 후 HTTP 이전에 `OrderExecutionError`로 **거부**(fail-closed) | Q-MIC-3 — 코드 측면 **해소**(`76d43ae9`). 값집합 자체의 공식 전수는 확정 | `executor.py:857-919` (`_map_stock_order_type`·`_map_futures_order_type`) |
| 5 | **숫자 인코딩 파서 동작** | 주식 `ORD_UNPR=str(int(price))`(정수 절단) vs 선물 `UNIT_PRICE=str(price)`(float 문자열) — broker 파서가 어느 쪽을 어떻게 받는가 | Q-WIRE-1 미확인 | `executor.py:321`, `:393` |
| 6 | **필수/선택 필드 구분과 기본값 의미론** | `NMPR_TYPE_CD`·`KRX_NMPR_CNDT_CD`는 공식 명세 **[필수]**이며 이제 `ORD_DVSN_CD`에서 파생 전송된다(`executor.py:104-115`, `76d43ae9`) — 빈 문자열 전송 아님. **여전히 빈 값**인 것은 [선택] `CTAC_TLNO`·`FUOP_ITEM_DVSN_CD` 2필드이고, 이들의 **생략 시 broker 기본값**은 미확인 | 명세 측면 확정([필수] 2 + [선택] 2). **빈 값의 broker 해석**은 미확인 | **P-NMPR**이 [필수] 2필드에 한해 실측 판정 |
| 7 | **중복/미지/누락 필드 동작** | 미지 필드 무시인가 거부인가 (permissive 파서면 오타가 조용히 통과) | 미확인 | — |
| 8 | **토큰 `expires_in` 공식 값** | 우리 fallback 86400은 **우리 기본값**이지 broker 보증이 아님 | 미확인 | `auth.py:472`, `:583` |
| 9 | **`approval_key` 유효기간** | repo 주석 "~24h"는 공식 미확인 | 미확인 | `approval_cache.py:3,22` |
| 10 | **WebSocket 동시 구독 상한** | `streaming.yaml:50` 주석 "KIS 제한: 41" — 커뮤니티 출처만 존재 | 미확인 | P-14가 실측 시도 |
| 11 | **REST 유량 수치 (실전/모의)** | "실전 20건/s·모의 2건/s" 통설의 **공식 원전 부재 확인**. 확인된 공식 진술은 정성적 방향뿐("모의투자 계좌는 REST API 호출 제한이 낮습니다") | folklore 철회 확정 | P-13이 실측 |
| 12 | **자격증명 폐기 API / 전파 시한** | `capabilities.credentials_and_revocation.revocation_bound_ms` | 미확인 | — |
| 13 | **야간 세션 TR 계열** | 모의에 야간 TR **부재**(order/cancel/inquire 3계열 모두 `*_night_real`만) — MOCK→REAL 외삽 금지의 구체 근거 | Q-MIC-1 확정 | `tr_ids.py:40-50` |
| 14 | **SOX 해외지수 TR id·경로** | 로드맵 `:395`가 `HHDFC55020100`을 **후보로만** 언급 — 검증된 TR id 아님. 확정 후 `probes_real.py::ALLOWLIST` 추가 → N-18b 재실행 | N-18b 스킵 사유 | N-18 |
| 15 | **ATS(넥스트레이드) 주문 경로** | TR 4종 + `order-ats` 엔드포인트 존재하나 `ats_routing.enabled: false`로 실사용 증거 없음 | Q-MIC-2 | `tr_ids.py:35-38` |
| 16 | **잔고 조회 TR 정본** | `config/kis/tr_ids.yaml`에 잔고 TR **0건** — 실사용 TR은 `client.py` 인라인, `CTFN6118R`은 문서만. `futures-legal-review.md:38` 감사 항목이 구조적으로 충족 불가 | SoT 결손 | N-16 |

각 항목의 결론은 **출처 URL + 접근 일자**와 함께 기록한다. 확인 실패는
"미확인"으로 남기며, **추정값으로 채우지 않는다.**

---

## 8. 통계 규율 (bounds semantics = hard_maximum)

이 캠페인이 채우는 bound들은 `hard_maximum` 또는 `broker_specific` **최대값**이다.
백분위수가 **아니다.**

### 8.1 규칙

```
recommended_bound_ms = ceil( max_observed × (1 + margin_pct/100) )
```

- 기본 마진 50% (`--margin-pct`). Bounds-Approver가 조정할 수 있다
- **p95/p99는 분포 모양 진단용으로만** 기록한다. 백분위수를 bound로 제안하는 것은
  "어떤 사건도 이를 넘지 않는다"는 계약을 "대부분의 사건은 넘지 않는다"로
  **바꿔치기**하는 것이다
- `summarize_latencies()`가 이 규칙을 코드로 강제하고, 결과에
  `candidate_only: true`와 규칙 문자열을 함께 박아 넣는다

### 8.2 표본 적정성

작은 표본에서 추정한 최대값은 **참 최대값을 과소평가한다.** 따라서 값과 함께
`n`·관측 창·관측 조건을 반드시 남기고, `n`이 충분한지는 Bounds-Approver가 판단한다.
P-5는 N≥100, P-8은 N≥5, P-EXT는 ≥5 trial을 권고한다.

### 8.3 가산 오차

폴링 기반 관측은 표본마다 최대 1 폴 간격의 오차를 갖는다. 승인 bound는
`max_observed + poll_granularity_ms`를 **넘어야** 하며 `max_observed`만으로는 부족하다.
여기서 `poll_granularity_ms`는 아티팩트에 기록된 **실효** 폴 간격
`max(--poll-ms, --pace-s)`이다 (§5.3.1) — 요청한 `--poll-ms`가 아니다.
P-16의 HTTP `Date` 헤더는 1초 해상도이므로 |skew| < 1000 ms는 "헤더 해상도 이내"이지
측정값이 아니다. P-EXT의 t0은 사람의 키 입력이므로 수백 ms 오차를 마진에 접는다.

### 8.4 정직한 음성 (가장 중요)

- **관측 0건 ≠ 0.** P-FQP에서 late change가 하나도 안 보였다면
  `late_event_window_ms: 0`이 아니라 **"미확립"**이며 필드는 `null`, capability는
  UNKNOWN을 유지한다 (VP-002:756 — "absence within it is not proof of non-existence")
- **천장까지 무신호 ≠ 한도.** P-13이 `--max-rps`까지 스로틀을 못 봤다면 결론은
  "한도는 시험 천장보다 위"이고 `hard_limits`는 **비운 채로 둔다**
- **미관측 종료(censored) trial을 버리지 않는다.** 최대값 계산에서 censored를
  제외하면 최대값이 체계적으로 낮아진다 — 그 방향의 오류가 곧 fail-open이다
- **단발 관측으로 원자성을 주장하지 않는다.** P-8에서 중첩 0으로 나와도 폴링 간격보다
  짧은 중첩은 못 본다. 원자적 replace 모드 선언은 N≥5 합치 후에만
- **한쪽으로 치우친 skew와 양쪽 jitter를 합치지 않는다** (P-16) — 전자는 보정 가능한
  체계 오차, 후자는 보정 불가한 흔들림으로 처방이 다르다

---

## 9. 알려진 갭 (실행 전 처분 필요)

### 9.1 INSTANCE에 대응 필드가 없던 프로브 산출 8건 — **처분 완료 (Patch-0057)**

§4.3에서 **부재**로 표시됐던 필드들이다. 템플릿(Patch-0056 반영 후 기준)에 대응 키가
없어 **측정해도 기입할 곳이 없었다**. 이는 T1 blocker B-1~B-4와 **같은 결함 클래스**다
(템플릿만으로는 모델의 안전 게이트를 표현하지 못함).

**2026-07-29 Patch-0057이 8건 전건을 처분했다: 신설 6 · 재매핑 2.** 신설분은
`BROKER-CAPABILITY-PROFILE-template.yaml`에 슬롯으로 등록되고 INSTANCE 초안 2문서
(MOCK_VTS·REAL_PROD)에 보수 기본값으로 동기화됐다. **값은 하나도 채워지지 않았다** —
슬롯 등록은 승인이 아니다.

| # | 프로브 산출 | 처분 | 기입면 (확정) | 기본값 |
|---|---|---|---|---|
| 1 | `sessions.subscription_limit` (P-14) | **신설** | 동명 | `null` |
| 2 | `credentials_and_revocation.reissue_rejection_semantics` (P-15) | **신설** | 동명 | `UNKNOWN` |
| 3 | `credentials_and_revocation.token_blackout_window_ms` (N-15) | **신설** | 동명 | `null` |
| 4 | `broker_time.skew_bound_ms` (P-16) | **신설** | 동명 | `null` |
| 5 | `replace_semantics.value_set` (N-17) | **신설** | 동명 | `[]` |
| 6 | `market_and_instrument_constraints.instrument_coverage` (N-18) | **신설** | 동명 | `UNKNOWN` |
| 7 | `position_balance_margin.schema_captured` (N-16) | **재매핑** | `capabilities.position_balance_margin.evidence_refs` (+ `.status`) | 기존 `[]` |
| 8 | `command_construction_and_wire_semantics.field_inventory` (N-17) | **재매핑** | `…command_construction_and_wire_semantics.required_and_default_field_semantics` (+ `.duplicate_unknown_and_omitted_field_behavior`, `.unit_multiplier_currency_and_numeric_encoding`) | 기존 `UNKNOWN` |

**재매핑 2건의 근거 (§9.1 초판의 "재매핑 검토 우선" 지시를 실측 재확인한 결과)**:

- **#7 N-16**: 산출은 응답 스키마 키 목록(`top_level_keys`/`output1_keys`/
  `output2_keys`)이다. ADR §8.10:408-417의 8개 항목에 "스키마"는 **없다** — 즉 이것은
  프로파일 *속성*이 아니라 *증거 아티팩트*다. 공통 블록 `evidence_refs`가 정확히 그
  자리이고(§6.3의 보존 규율이 그대로 적용된다), 도달 가능성 자체는 `status`가 담는다.
  전용 키를 신설하면 증거를 속성으로 승격시키는 셈이 된다.
- **#8 N-17**: 산출은 주문 요청 필드 전수(필수/선택 구분과 생략 시 기본값)다. 이는
  §7 대조표 항목 6과 **같은 사실**이고, 템플릿 `required_and_default_field_semantics`가
  이미 그 이름이다 (ADR §8.17:512 "evidenced API/SDK defaults, field-presence rules").
  잔여 성분도 전부 기존 키로 간다 — 항목 7 → `duplicate_unknown_and_omitted_field_behavior`,
  항목 5 → `unit_multiplier_currency_and_numeric_encoding`, 항목 1 →
  `client_generated_order_id.status`. **잔여 0**이므로 신설은 중복 명명이다.

**#6 N-18은 재매핑하지 않았다 (초판 판정 정정).** §9.1 초판은 N-18도 "기존 키로 재매핑
검토 우선"으로 적었으나, 실측 결과 기존 4키 중 어느 것도 N-18a(1회 조회 행 상한)와
N-18b(해외지수 심볼 표기)를 담지 못한다. `session_phase_semantics`로 N-18c만 부분
매핑하면 나머지 두 산출이 **조용히 사라진다** — Patch-0056 §1이 지목한 바로 그
"표현 불가능한 판단이 소리 없이 증발하는" 결함이다. 따라서 신설이 정답이다.

**주의 (변함없음)**: 이 8건은 `docs/broker-profiles/` 및 tos-spec 템플릿 소관이며
병렬 트랙과 겹친다. 처분은 Patch-0057 문서와 그 병합 기록(ARCHITECTURE-GATE-STATUS
§3.24)이 정본이며, 이 런북은 **매핑을 표기**할 뿐 승인 권한을 갖지 않는다.

**남은 사실**: 슬롯이 생겼다는 것은 **기입면이 생겼다**는 뜻이지 값이 생겼다는 뜻이
아니다. 6건 전부 §6.4의 "값이 확립되지 않았으면 `null`을 유지한다" 상태이며, 실측
후에도 `status`/`assurance_level` 승격은 자동이 아니다.

### 9.2 프로브가 정의되지 않은 broker 관련 키

`B_non_trade_event_detect`(:815) / `B_non_trade_reconcile`(:833) — corporate-action
표면이 repo에 부재하여(grep 0) **측정 대상 자체가 없다.** 이 두 키는 이번 캠페인으로
채워지지 않으며, "프로브 전건 실행 = 전 키 확보"가 아님을 승인 패키지에 명시할 것.

### 9.3 결과 디렉터리 잔재

`results/`에 하네스 스모크 테스트 산출물이 남아 있을 수 있다(dry-run 14건 +
P-1 오프라인 1건). 전부 gitignored이며 `NOT_MEASURED`(P-1 제외)라 §6.2 적격성을
통과하지 못하지만, **캠페인 시작 전 비우는 것을 권고**한다 — 오래된 `repo_commit`을
가진 아티팩트가 증거로 오인될 여지를 없애기 위함이다.

### 9.4 P-BAL 전용 기입면 부재 — **미처분** (§9.1과 같은 결함 클래스)

`position_balance_margin`에는 `open_order_query`가 가진
`.completeness`/`.pagination` 쌍이 **없다**(INSTANCE 초안: `open_order_query`
`:3294`·`:3296` 존재 / `position_balance_margin` `:1290-1305`에 둘 다 부재). 따라서
P-BAL의 산출 — 페이지 크기·연속조회 거동·truncation 3값 판정 — 은 **전용 슬롯이
없다.**

임시 처분: N-16의 Patch-0057 재매핑(§9.1 #7)과 동일하게 `evidence_refs`(+ `.status`)에
기입한다. 그 근거는 같다 — 아티팩트는 증거이며, 도달 가능성은 `status`가 담는다.

**남은 판단(이 런북의 권한 밖)**: truncation 위험 3값 판정은 증거가 아니라 **속성**에
가깝다(`open_order_query.completeness`가 정확히 그 성격의 키다). 신설이 옳은지
`consistency_model`로 흡수하는 것이 옳은지는 `docs/broker-profiles/` 및 tos-spec
템플릿 소관이며, §9.1이 세운 규율("한 사실에 이름 둘을 만들지 않는다" vs "표현 불가능한
판단이 조용히 증발하게 하지 않는다")로 판정해야 한다. **판정 전까지 P-BAL의 판정값은
`evidence_refs`가 가리키는 아티팩트 안에만 존재하고 INSTANCE 본문에는 올라가지
않는다** — 그것이 조용한 증발을 막는 최소 조치다. `registry.py`는 없는 필드명을
발명하지 않는다.

---

## 부록 A — 사전 점검 명령

```bash
# 프로브 목록과 위험도
python -m tools.broker_probes.run --list

# 커버리지 (12 정본 + 4 census, 미커버 bound 키 포함)
python -m tools.broker_probes.run --coverage

# 개별 프로브 도움말 (--confirm 없이 — 브로커 무접촉)
python -m tools.broker_probes.run P-5 --help

# 드라이런 (요청 형태만 출력, 소켓 미개방)
python -m tools.broker_probes.run P-5 --symbol 101S6000
python -m tools.broker_probes.run P-BAL --asset stock --env real
```

## 부록 B — 축약 인용 해소표

본문의 `파일명:행` 축약(초안 메모 §5와 동일 관례)은 아래로 해소한다.

| 축약 | 실제 경로 |
|---|---|
| `executor.py` | `shared/execution/executor.py` |
| `client.py` | `shared/kis/client.py` |
| `auth.py` | `shared/kis/auth.py` |
| `approval_cache.py` | `shared/kis/approval_cache.py` |
| `tr_ids.py` | `shared/execution/tr_ids.py` |
| `tr_ids.yaml` | `config/kis/tr_ids.yaml` |
| `streaming.yaml` | `config/streaming.yaml` |
| `common.py` · `registry.py` · `probes_*.py` · `run.py` | `tools/broker_probes/` |
| `broker_verification.py` | `services/trading/broker_verification.py` |
| `futures-legal-review.md` | `docs/runbooks/futures-legal-review.md` |

## 부록 C — 관련 문서

- 실행 계획: `docs/plans/2026-07-29-tos-phase0-p02-execution-plan.md`
- 프로브 정본·quirk 17건: `docs/plans/2026-07-29-tos-broker-capability-profile-kis-draft.md`
- 설계 #10 (bounds 10-bullet 열거 `:1168-1171`): `docs/plans/2026-07-25-tos-broker-capability-design.md`
- 인간 게이트 레지스터 (P0-2 행): `docs/plans/2026-07-29-tos-phase0-human-gate-register.md:50`
- INSTANCE: `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml`
- bounds: `tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml`
