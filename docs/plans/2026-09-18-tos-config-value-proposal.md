# TOS 배포 설정값 제안표 (2026-09-18) — W-A / A-1

- 작성: 2026-09-18 · 세션 모델 단독 저작
- 상위 계획: `docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md` (§0 부류 정의 · §4 W-A)
- 운영자 승인: **2026-09-18 「설정값은 승인함」** — 이 표 전체에 대한 승인으로 기록한다
- 대상: `config/tos_runtime/paper/` 에 아직 없는 **19종** + `construction.yaml`

---

## 0. 이 표가 무엇이고 무엇이 아닌가

**이것은 첫 부팅 프로파일이지 운영 안전 태세가 아니다.**

여기 적힌 값들은 `run` 이 **로컬 헤르메틱 환경에서 구동**하도록 만드는 값이다. 구조적으로 유효하고
서로 정합하지만, **실 자금·실 주문을 전제한 안전 한도가 아니다.** 실 배포 태세는 별도 승인 사안이며,
이 표를 근거로 그 승인을 대신할 수 없다. 채택되는 각 파일에 이 문장을 주석으로 박는다.

### 0.1 값의 출처 강도 — 네 등급

| 등급 | 뜻 | 이 표에서의 표기 |
|---|---|---|
| **S — 강제** | 로더가 받는 값이 **하나뿐**이다. 판단의 여지가 없다 | `[S]` |
| **A — 승인 전사** | `VERIFICATION-PROFILE-002.yaml` 에 **승인 기록이 붙은 값**이 있다. 그대로 옮긴다 | `[A]` + 줄 번호 |
| **D — 도출** | 명령을 실행해 나온 값을 옮긴다. **손으로 짓지 않는다** | `[D]` + 명령 |
| **O — 운영자 판단** | 상위 원천이 없다. **2026-09-18 승인이 곧 원천**이다 | `[O]` |

**⚠ 표시**는 틀리면 비싼 값이다. 승인을 받았어도 운영자가 눈으로 볼 자리를 만든다.

### 0.2 이 표에 **없는** 것

- **주식 가격대별 호가단위 표** — 브로커 측정값이다(상위 계획 §0 (다)). 승인으로 만들 수 없다.
  실측 경로는 W-B3 에서 설계한다. 배포 값은 `null` 유지.
- **`canonical_digest` 계열** — `check_canonical_digest`(`venue/_policy_primitives.py:241-247`)가
  `"TBD"` 를 **항상 통과**시킨다. 정상 배포 형태는 「정책 파일은 TBD, `safety_activation::members` 만
  정확」이다. **채우지 않는다.**
- **`activation_record_id`** — 프로덕션 코드에서 **0건** 읽힌다(죽은 리프). **채우지 않는다.**

---

## 1. [S] 강제 — 로더가 값 하나만 받는다

| 파일 | 키 | 값 | 근거 |
|---|---|---|---|
| `coordinator_preconditions.yaml` | `live_authorization_state` | **`"NOT_AUTHORIZED"`** ⚠ | `compose/_preconditions.py:94` 의 `_SUPPORTED_LIVE_AUTHORIZATION_STATES = {"NOT_AUTHORIZED"}` — 다른 값은 로더가 거부. `tos-spec/src/AUTHORITY-STATUS.csv` 의 `restricted_live` 행도 이 값뿐. **CLAUDE.md 비협상 규칙의 기술적 집행점이다** |

**⚠ 이 값은 「실거래 절대 금지」가 코드로 서는 자리다.** 미래에 `_SUPPORTED_...` 집합이 넓어지는 변경이
있을 때 이 값이 잘못 바뀌면 유일한 게이트가 무너진다. 값 자체는 선택지가 없지만 **감시 대상**으로 둔다.

---

## 2. [A] 승인 전사 — VER-002 에 승인 기록이 있다

전부 `tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml`.
승인 주체 `operator (Bounds-Approver)` · 재검토일 `2027-01-29`.

### 2.1 `time.yaml`

| 키 | 값 | VER-002 | 승인일 |
|---|---|---|---|
| `MAX_time_source_precision_ms` | **50** | L1076 | 2026-07-29 |
| `MAX_time_source_sequence_gap_ms` | **50** | L1077 | 2026-07-29 |
| `MAX_time_transport_and_queue_uncertainty_ms` | **50** | L1069 | 2026-07-29 |
| `MAX_time_source_disagreement_ms` | **50** | L1071 | 2026-07-29 |
| `MAX_clock_domain_conversion_uncertainty_ms` | **50** | L1070 | 2026-07-29 |
| `MAX_future_timestamp_tolerance_ms` | **50** | L1074 | 2026-07-29 |
| `MAX_time_conservative_freshness_age_ms` | **1000** | L1078 | **2026-09-04** (UNCHK-024 처분 §4 도출 — Σ 지연 한도 200ms 보다 큼, 보수 방향 LOWER) |
| `MAX_critical_input_consumer_receipt_age_ms` | **1000** | L1067 | 2026-07-29 |
| `MAX_process_suspension_ms` | **2000** | L1009 | 2026-07-29 |

### 2.2 `engine.yaml`

| 키 | 값 | 근거 |
|---|---|---|
| `max_unresolved_send_per_scope` | **1** | VER-002 L1010 `MAX_unresolved_send_per_scope: 1` — 「at most one unresolved send per scope」, APPROVED 2026-07-29. `engine.example.yaml` 주석이 이 참조점을 명시적으로 가리킨다 |

### 2.3 `currentness.yaml`

| 키 | 값 | 근거 |
|---|---|---|
| `B_capability_claim_to_send` | **500** ⚠ | VER-002 L301-302 `value_ms: 500`. **단 그 항목은 `RECHECK: APPROVE after the fenced egress journal and broker transport are implemented` 이고 `rationale: "MEASURE"` 다** — 아직 측정되지 않은 값이다. `applicable_scope: non-live-test` 이고 **우리가 정확히 non-live-test 다.** 그 범위에서 전사하되 **측정 대기 상태임을 파일 주석에 남긴다** |

**⚠ 이것이 이 표에서 가장 약한 [A] 다.** 상위 승인이 **조건부**이고 그 조건(펜스된 egress 저널 +
브로커 트랜스포트 구현)이 **아직 충족되지 않았다.** 값을 쓰되 「승인된 측정값」이 아니라
「측정 대기 중인 잠정값」으로 기록한다.

---

## 3. [D] 도출 — 명령으로 얻는다, 손으로 짓지 않는다

| 파일 | 키 | 도출 명령 | 선행 조건 |
|---|---|---|---|
| `release.yaml` | `expected_code_digest` · `expected_dependency_set_digest` | **`print-digests`** (인자 없음 — `print-policy-digests` 와 **다른 서브커맨드**) | **설치 상태**가 선행. 정책 파일과 무관 |
| `safety_activation.yaml` | `members[]` 의 `(kind, member_id, generation, digest)` | **`print-policy-digests --config-dir <dir>`** | **정책 파일의 (가) 값 확정이 선행.** 출력 3필드를 전사하고 `kind` 는 `BundleMemberKind` enum 으로 사람이 옮긴다 |
| `safety_activation.yaml` | `activation.envelope_digest` · `profile_digest` · `bundle_digest` | **도출 절차 미확인** — A-3 에서 확정한다 | envelope/profile 확정이 선행 |
| `authority.yaml` | `trading_approval_policy_generation` | 현재 활성 `TradingApprovalPolicy` 의 `policy_generation` 을 그대로 | 그 정책이 먼저 존재해야 함 |

**세 번째 행은 정직하게 미확인으로 둔다.** 도출 도구를 확인하지 못했으므로 **값을 짓지 않는다.**
A-3 에서 절차를 찾거나, 못 찾으면 **못 찾았다고 보고**한다.

---

## 4. [O] 운영자 판단 — 2026-09-18 승인이 원천

### 4.1 ⚠ 안전 계열 — **여기만 봐주시면 됩니다**

| 파일 | 키 | 제안값 | 왜 이 값인가 |
|---|---|---|---|
| `broker_scopes.yaml` | `active_scope` | **`SYNTHETIC_FUTURES_ORDER`** ⚠ | example 의 네 스코프 중 **브로커에 전혀 닿지 않는 유일한 것**이다. `REAL_ORDER`(`authorization_class: REAL_ORDER`)는 비협상 규칙상 영구 차단. `MOCK_STOCK_ORDER`(`endpoint_class: BROKER_ORDER`)와 `REAL_READ`(GET)는 **외부 호출이 생기므로 로컬 첫 부팅의 범위가 아니다.** 부팅을 증명하는 데 필요한 최소 권한이 이것이다 |
| `coordinator_preconditions.yaml` | `nonlive_broker_consuming.admitted` | **`false`** ⚠ | `active_scope` 가 SYNTHETIC 이면 **이 자세는 아예 평가되지 않는다**(게이트 ②가 먼저 통과시킨다 — `compose/_preconditions.py` 모듈 독스트링). `true` 로 둘 이유가 없고, `false` 가 **더 좁은** 태세다. MOCK 전송을 켤 때 별도 승인으로 바꾼다 |
| `release.yaml` | `admission_result` | **`ADMIT`** ⚠ | 이 값이 없으면 어떤 서비스도 구성되지 않는다(design #40 §5). 로컬 부팅을 위해 허용으로 두되, **`restriction_present: false`** 와 짝이어야 한다. **정정(fact-check)**: 초고는 **`ADMITTED`** 라고 적었는데 **그런 멤버는 없다** — `tos.sci.AdmissionResult`(`tos/src/tos/sci/vocabulary.py:100`)는 `ADMIT`/`DENY`/`UNKNOWN` 뿐이고 `release/config.py:122-130` 이 `member.value` 와 **정확히** 대조한다. 그대로 썼으면 **부팅이 거부**됐다 |
| `risk_attestations.yaml` | 6개 `attested` | **전부 `true`** ⚠ | 이것은 **측정이 아니라 운영자 확약**이다(Phase 2 에 실측 인프라가 없어 명시적 스탠드인). **`false` 면 부팅이 막힌다.** 로컬 합성 경로에서는 6개 성질이 실제로 성립한다(실 자금 없음·실 주문 없음·필드 귀속은 합성 경로가 전부 채움). **실 전송을 켜는 순간 이 확약은 재검토 대상이다** |

### 4.2 상위 원천이 없는 값 — 내가 고르고 근거를 적는다

| 파일 | 키 | 제안값 | 근거 |
|---|---|---|---|
| `time.yaml` | `MIN_time_independent_reference_count` | **1** | VER-002 에 **키가 없다**(grep 0건). 로컬 단일 호스트에는 독립 시계 참조가 하나뿐이다 — **2 를 적으면 거짓**이다. 실제 구성을 적는다 |
| `time.yaml` | `MAX_send_result_wait_ms` | **2000** | VER-002 에 키가 없다. `MAX_process_suspension_ms`(2000, 승인됨)와 같은 자릿수로 맞춘다 — 프로세스 정지 한도보다 짧으면 정지 중 전송 결과를 못 기다린다 |
| `engine.yaml` | `dsl_evaluation_budget_steps` | **1000** | VER-002 에 키가 **없다**(`EngineConfiguration` 독스트링 자신이 「key absent from VERIFICATION-PROFILE-002 — provisional」). **벽시계 인터럽트가 아니라 정적 작업 수 비교**라 과대 설정의 위험이 낮다. 2026-09-08 부터 열려 있던 운영자 결정 항목이다 |
| `authority.yaml` | `containment_bound_ms` | **1000** | VER-002 에 이 경계를 이름 붙인 키가 **없다**(example 주석이 2026-09-08 grep 결과로 명시). `MAX_time_conservative_freshness_age_ms`(1000, 승인됨)와 정렬한다 — 봉쇄 경계가 신선도 경계보다 길면 만료된 witness 로 봉쇄를 주장하게 된다 |
| `engine_driver.yaml` | `replay_window_events` | **0 = 전체**(로더가 0 을 거부하면 충분히 큰 정수) ⚠ | example 이 **명시적으로 경고**한다 — 창이 전체 인박스보다 작으면 **거짓 divergence** 를 보고할 수 있다(원장 컨텍스트 소실). 「전체를 덮으라」가 문서의 권고다. **로더가 양의 정수만 받으므로**(`compose/_engine_wiring.py:142-156`, 0·음수는 「조용히 꺼진 창」이라며 별도 거부) **`1000000`** 으로 둔다 |
| `finality.yaml` | `currency` | **`"KRW"`** | KRX 거래이고 이 저장소는 KST/원화 네이티브다 |
| `finality.yaml` | `release_proof_wait_ms` | **60000** | VER-002 `MAX_live_authorization_validity_ms`(60000, 승인됨)와 정렬. 이 값은 **상태를 바꾸지 않고 증거 행만 남긴다**(incident candidate) — 과대해도 안전 방향 |
| `finality.yaml` | `value_date` · `source_revision` · `proof_recipe_id` | **미확정** | `proof_recipe_id` 는 「Phase-0 승인 recipe identity(ADR-002-030 §29 Q3)」다 — **그 ADR 에서 승인된 식별자를 찾아야 하고, 못 찾으면 짓지 않는다.** A-2 에서 확인 |

### 4.3 식별자 — **이름 짓기는 정책 행위다**

`envelope_id` · `profile_id` · `activation_id` · `coverage_manifest_id` · `active_set_id` 등은
**측정값이 아니라 이름**이다. 규칙을 정하고 일관되게 쓴다:

```
tos-paper-<무엇>-g<세대>      예: tos-paper-envelope-g1 · tos-paper-profile-g1
```

`*_generation` 계열은 전부 **1**(첫 세대). `not_expired: true`(운영자 확약 — spg 가 시간 연산을 하지
않으므로 명시), `is_complete`/`is_current` 계열은 **이 프로파일이 실제로 완결이므로 `true`**.

**빈 목록으로 두는 것**: `governed_dimensions` · `permitted_scope` · `prohibited_fallbacks` ·
`approval_ids` · `compatibility_attestation_refs` · `members`(deviations/incidents) ·
`applicable_decision_ids` — **아직 지배할 차원도, 기록된 승인도, 발생한 이탈·사고도 없다.
빈 것이 사실이다.** 있는 척 채우지 않는다.

---

## 5. 순서 (뒤집을 수 없다)

1. **[S]·[A]·[O] 값 기입** — 정책 파일들이 먼저 서야 digest 가 계산된다
2. **`print-policy-digests`** → `safety_activation.yaml::members` 전사
3. **`print-digests`** → `release.yaml` 두 digest (설치 상태가 선행 — 1·2 와 독립)
4. **`construction.yaml`** — `price_field_key`/`shape_price_field_key` 는
   `critical_input_policy.yaml::fields[].field_key` 와 일치해야 하는데 **그 파일도 아직 채택되지
   않았다.** 둘을 같이 정하거나, `critical_input_policy` 없이 부팅하고 `price=None` 을 받는다
   ((a′) 웨이브의 의도된 설계)
5. **부팅**

**주의**: `admitted_quantity_bases`(OCP)가 전략의 `quantity_basis` 와 어긋나면 **부팅은 통과하고
주문 구성 때마다 거부된다**(`tos/src/tos/egressgw/construction.py:396` — 런타임 강제, 부팅 검증 아님).
**부팅 성공을 성공으로 읽으면 안 되는 지점이다.**

---

## 6. 확인 불가 · 미확정 (짓지 않고 남긴다)

1. `finality.yaml::proof_recipe_id` — ADR-002-030 §29 Q3 의 승인 식별자를 찾지 못했다
2. `finality.yaml::value_date` · `source_revision` — 「불투명 주입 토큰」이라 형식 자유이나 **의미 있는
   값을 정할 근거가 없다.** A-2 에서 example 주석을 더 읽고 확정
3. `safety_activation.yaml` 의 `envelope_digest`/`profile_digest`/`bundle_digest` 도출 절차
4. `release.yaml::admission_result` 의 정확한 enum 멤버명
5. `monitor_coverage.yaml::bounds` 3값(`max_evidence_tip_stall_ms`·`healthy_time_states`·
   `max_inbox_unconsumed`) — 상위 원천 미확인
6. `currentness.yaml::required_dimensions` — 21개 MANDATED_DIMENSION_FLOOR 를 그대로 복사하면
   **`policy_covers_mandated_dimensions` 가 항진명제가 된다**(과거 버그, example 주석에 기록).
   floor 이상이어야 하되 **의미 있게 독립적으로 편집 가능한 선언**이어야 한다 — 설계 판단이 필요
7. `strategies/example.strategy.yaml` 의 10개 리프 — 전략 DSL 은 거래 의미가 있는 값이라
   **부팅용으로 아무거나 넣으면 안 된다.** A-2 에서 별도로 다룬다

**6·7 은 값을 정하기 전에 판단이 더 필요하다.** 부팅이 이것들 때문에 막히면 그것이 A-5 의 결과물이다.
