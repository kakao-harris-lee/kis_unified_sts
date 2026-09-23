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
| `risk_attestations.yaml` | 6개 `attested` | **전부 `true`** ⚠ | 이것은 **측정이 아니라 운영자 확약**이다(Phase 2 에 실측 인프라가 없어 명시적 스탠드인). **정정(fact-check)**: 초고는 「`false` 면 **부팅이 막힌다**」고 적었는데 **틀렸다** — `_require_bool` 은 `null`/비-bool 만 거부하고 `False` 는 **유효한 값으로 로드에 성공**한다. `False` 는 `_restrictive_merge` 를 거쳐 **개별 step 6/7 결정을 거부**하는 방식으로 작동한다(부팅 실패가 아니라 그 결정이 거부됨). **그리고 「6개 성질이 실제로 성립한다」도 코드로 뒷받침되지 않는다** — `all_fields_attributed`/`economic_commitment_exclusive`/`flow_commitment_exclusive` 는 코드 독스트링 자신이 「Phase 2 에 추적 인프라가 없다」고 명시한 성질이라 **참/거짓을 코드로 판정할 수 없다. 순수 운영자 판단이다** — ⚠ 로 올리는 이유가 이것이고, 이 행은 **운영자가 직접 판단해야 한다.** 값 제안은 `true` 로 유지하되 근거는 「코드가 성립을 보장한다」가 아니라 「합성 경로라 위반 경로가 없다고 판단한다」이다 |

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

---

## 7. 채택 기록

**2026-09-23 · 운영자 「제안된 그대로 채택」**(⚠ 행 4건 포함). 착지 상세는 상위 계획
`docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md` **§7.8**.
**2026-09-23 2차(review-794 조치 + 운영자 답변 4건)** 내용을 §7.3~§7.5 로 덧붙인다.

### 7.1 1차 채택 (2026-09-23)

- **채택 18종** — `config/tos_runtime/paper/` 신설. 각 파일 헤더에 승인 출처와 **§0 문장**을 박았다.
  `construction.yaml` 은 **채택하지 않았다**: 이 표가 §0 에서 대상에 넣었으나 7개 리프 어디에도 값을
  주지 않고, `account`/`instrument` 는 venue/OCP 의 「never committed here」 운영자 좌표와 같아야 한다.
- **§6 1항 재측정**: ADR-002-030 §29 는 절 제목이 "Open Implementation Questions" 이고 Q3 은 열린
  질문이다 — 승인된 `proof_recipe_id` 는 **찾지 못한 게 아니라 아직 존재하지 않는다.**
- **§6 3항 확정**: envelope/profile/bundle digest 를 계산하는 서브커맨드는 **없다**
  (`print-policy-digests` 는 governed **policy** 5종만 출력). 커널이 세 필드를 `X | None` 로 선언해
  `null` 이 로드된다 — 「거부가 빠진 것」이 아니라 **「도출이 없는 것」**이다.
- **§6 4항 해소**: `admission_result` 의 정확한 enum 멤버는 `ADMIT` 이다(§4.1 의 fact-check 가 옳았다).
  실부팅으로 확인: `release.yaml` 이 그 값으로 로드된다.
- **§3 2행(members) 보류** — `print-policy-digests` 가 **2026-09-16 채택분**의 잔여 TBD
  (`venue_constraint_policy::scope.accounts`)에서 거부했다. 이 표의 대상 범위가
  「아직 없는 19종 + construction」이라 그 값의 행이 없으므로 지어내지 않고 `members: null` 로 남겼다.

### 7.2 운영자 답변 (2026-09-23, 2차)

1. **좌표는 커밋하지 않는다** — 「이 장비가 운영 장비. 여기 있는 `.env` 와 `.env.mock` 환경 파일을
   그대로 활용」. 즉 `construction.yaml::account`/`instrument` 와 2026-09-16 채택분 4종의
   `scope.accounts`/`scope.instruments`/`account_scope`/`instrument_scope` 는 **런타임에 이 호스트의
   env 파일에서 와야 하고, 커밋되어서는 안 된다.** → **기존 주입 수단 서베이 결과 그런 수단이 없다**
   (상위 계획 §7.8 「B1 서베이」). **새로 만들지 않고 설계 선택지만 보고**했다 — 이 표에는 값이 들어가지 않는다.
2. **`currentness.yaml::required_dimensions` — 「그대로 사용」.** §6 6항이 설계 판단으로 남긴 것을
   커널 `MANDATED_DIMENSION_FLOOR` 21키 전부로 채웠다. 추천 출처
   `docs/plans/2026-09-12-tos-operator-value-proposals.md` §2(등급 C). **항진명제 경고는 파일 헤더에
   그대로 이월**했다 — 이 목록이 floor 와 같은 한 `policy_covers_mandated_dimensions` 가 참인 것은
   증거가 아니다.
3. **「확정할 부분 추천 값이 있으면 활용」** — §6 미확정 5건을 저장소 전수 재조사했다.

   | §6 항목 | 추천값 | 출처 | 처분 |
   |---|---|---|---|
   | `monitor_coverage::bounds` 3값 | `60000` · `["TRUSTED"]` · `100` | 2026-09-12 §4(등급 C, 「서버 실측 후 하향」) | **채움** — 런타임 자기관측 임계값이라 자산군 무관 |
   | `currentness::required_dimensions` | 커널 floor 21키 | 2026-09-12 §2(등급 C) | **채움**(답변 2) |
   | `finality::proof_recipe_id` | **없음** | ADR-002-030 §29 = 열린 질문 · 2026-09-12 §5 = 등급 M(「개발 측 값 제안 없음」) | `null` 유지 |
   | `finality::source_revision` | **없음**(등급 M) | 2026-09-12 §5 — 「배포 git SHA」는 산출 *방법*이고, 이 파일을 담는 커밋의 SHA 는 쓰는 시점에 존재하지 않는다(자기참조) | `null` 유지 |
   | `finality::value_date` | ⚠ **있으나 범위 불일치** | 2026-09-12 §5 `T+2`(등급 B) — 근거가 「KRX **주식** 결제일」인데 이 배포의 스코프는 `SYNTHETIC_FUTURES_ORDER` | `null` 유지 — 넣으면 **틀린 값에 인용을 입히는 것** · 운영자 한 줄 확인 대기 |
   | `strategies/` 10 리프 | **없음** | 2026-09-12·2026-09-18 양 표 · example 주석 전수 | 미채택 |
   | `marketfeed.yaml` + `critical_input_policy.yaml` | **없음** | 두 표 모두 이 두 파일의 행이 없다(2026-09-12 는 틱 원천 웨이브 이전 문서) · 특히 `fields[].max_age_ms` 는 신선도 한도 = 안전 값 | 미채택 · 좌표는 답변 1 에 걸림 |

4. **PR 본문 이탈 1~4 — 운영자 확인(2026-09-23).** 아래 §7.3 이 그 4건을 포함한 **전수 목록**이다.

### 7.3 이 표가 행으로 다루지 않은 채워진 리프 — **전수 41건** (review-794 HIGH-3)

review-794 는 PR 본문이 이탈을 **4건**으로 열거한 것을 지적했다: 「운영자는 저 19건의 양의 안전
주장을 보지 못한 채 서명하게 된다」. 분류기로 18종 156 리프를 전수 분류해 재현했다 —
**제안표 §1/§2/§3/§4.1/§4.2 행 43 · §4.3 이 이름을 댄 규칙 36 · `broker_scopes` example 본문 7 ·
나머지 70**, 그 70 중 **채워진 것(명시적 `[]` 포함)이 정확히 41**(나머지 12 는 `null`,
17 은 아래 (ㄹ)(ㅁ)(ㅂ) = PR 이 이미 이탈로 공시한 것). 성격별 전수:

**(ㄱ) 양의 안전 주장 19건** — 틀리면 감시가 스스로 「건강하다」고 말한다.

| 리프 | 값 | 출처 |
|---|---|---|
| `monitor_coverage::coverage.items.{evidence-tip-currency,time-service-health,inbox-backlog}.{restrictive_response_present,alert_path_present,evidence_path_present,currentness_rule_present,closure_1_to_12_complete}` (3×5=15) | `true` | **2026-09-12 §4** 「coverage manifest」 행(등급 C/M · 「세 항목 모두 실 감지기가 있음(W3.1 stm)」) |
| `monitor_coverage::coverage.items.*.criticality` (3) | `"CRITICAL"` | 동 |
| `safety_deviations::deviations.active_set.combined_within_envelope` (1) | `true` | 2026-09-12 §4 「deviations active_set」 행 · 이탈 0 건이라 **공허하게 참** |

**(ㄴ) `*_digest` 이름인데 계산값이 아닌 이름 토큰 5건** (review-794 LOW-2)

`currentness_dimensions::{CONTEXT,CRITICAL_INPUT,EGRESS_IDENTITY}.bound_digest` ·
`monitor_coverage::coverage.manifest.{coverage_manifest_digest,policy_digest}`.
**§0.2 위반이 아니다**: §0.2 의 대상은 *정책 문서의* `canonical_digest` 계열이고(그 검사기가 `"TBD"`
를 항상 통과시키는 것이 이유), 이 다섯은 **계산 원천이 아예 없는 불투명 참조 토큰**이며 로더가 `null`
을 거부하므로 「비워 둔다」가 선택지가 아니다. 18종에 `canonical_digest` 실값은 **0건**이다.
2026-09-12 §4 는 여기에 「실 digest(운영자 산출 · `sha256sum`)」를 등급 M 으로 제안했다 — 그 산출이
생기면 대체할 자리다. 각 파일 헤더에 §0.2 와의 관계를 명시했다.

**(ㄷ) 버전 메타 6건 · `restrictive_floor` 3건 · `safety_cell` 1건 · §4.3 이 이름을 대지 않은 빈 목록 7건**

| 리프 | 값 | 출처 |
|---|---|---|
| `safety_envelope::envelope.envelope_version.{version,effective_date,approver_identity}` · `safety_profile::profile.profile_version.{…}` (6) | `"1"` · `"2026-09-23"` · `"operator (System Owner) …"` | 2026-09-12 §4 가 `v1`/effective/approver 를 제안(등급 C). **표기 차이**: 원천은 `v1`, 채운 값은 `"1"`(§4.3 식별자 규칙의 세대 번호 표기에 맞춤 — 로더는 불투명 문자열로 받는다). **만료일은 채우지 않았다** — 그 표의 `expiration 2027-03-15`(6개월 재검증)는 이번 답변 범위 밖 |
| `currentness_dimensions::*.restrictive_floor` (3) | `0` | 제안표 행 없음 — 「차원별 추가 하한을 선언하지 않는다」가 사실이고 0 이 그 표기다(파일 헤더) |
| `safety_incidents::incidents.active_set.safety_cell` (1) | `"tos-paper-cell-g1"` | 2026-09-12 §4 는 `paper-cell-1` 제안 · 이름만 제안표 §4.3 최신 규칙으로 |
| `safety_profile::profile.{scope,permitted_behaviors,fallback_rules}` · `safety_activation::activation.{scope,restrictive_generation_effects}` · `safety_incidents::incidents.{active_set.shared_dependencies,applicable_incident_ids}` (7) | `[]` | §4.3 의 「빈 것이 사실이다」를 **이름이 나열되지 않은 목록에도** 적용한 확장분 |

**(ㄹ)(ㅁ)(ㅂ) PR 이 이미 이탈로 공시한 17건** — 운영자 확인(2026-09-23, 답변 4):

| # | 리프 | 출처 |
|---|---|---|
| 이탈 ① | `release::restriction_state_resolved` = `true` (1) | §4.1 이 채택한 「ADMIT + `restriction_present: false`」 태세의 **귀결** — SCI-INV-014 상 미해소 조회는 무엇이든 보수적으로 거부하므로 `false` 면 채택된 ADMIT 이 무효가 된다 |
| 이탈 ② | `currentness_dimensions::*.positively_established` = `true` (3) | §4.3 의 양의 확약 부류를 확장 적용 · 근거는 「합성 경로라 위반 경로가 없다는 판단」 · 런타임이 `owner_identity="operator-attestation-pending-phase-5"` 를 스스로 찍어 구조적으로 드러낸다 |
| 이탈 ③ | `egress_coordinates::*` 9값 | 코드가 외부화하기 **전에** 갖고 있던 리터럴의 전사 — `compose/_egress_coordinates.py` 모듈 독스트링이 아홉을 이름과 값으로 나열한다(review-794 가 축자 대조 확인) |
| 이탈 ④ | `time::{tz_db_version,trading_calendar_version,verification_profile_version,safety_profile_version}` (4) | 호스트 tzdata 실측 · `calendar.yaml` 강제 일치 · VER-002 자기 식별 전사 · §4.3 식별자 |
| **이탈 ⑤ (신규 · review-794 MEDIUM-3)** | `authority::trading_approval_policy_generation` = `1` | §3 4행이 **[D] 도출**로 두고 「현재 활성 `TradingApprovalPolicy` 의 `policy_generation` 을 그대로」를 지시했으나 **배포 디렉터리에 그 정책 파일이 없어 도출 원천이 없다.** 「명령으로 얻는다, 손으로 짓지 않는다」가 붙은 값을 규칙으로 치환한 자리다. 독립 두 원천이 같은 1 을 가리킨다(2026-09-12 §2 등급 C · 제안표 §4.3) |

**다음 개정에서 (ㄱ)~(ㄷ)과 이탈 ①~⑤ 를 이 표의 행으로 흡수할 것.**

### 7.4 review-794 조치

| 지적 | 조치 |
|---|---|
| HIGH-1 `replay_window_events` 값 미핀(`1000000`→`1` GREEN) | 값 등식 핀 + 「핀이 실제로 발화하는가」 시험에 그 뮤테이션 자체를 넣었다 |
| HIGH-2 [A] 전사 bound 전건 값 미핀(17종 GREEN) | **부류로 닫았다** — 18종 156 리프 전부가 `_VALUE_PINS`(149) 또는 사유가 붙은 `_UNPINNED_BY_DESIGN`(broker_scopes 본문 7, byte-identity 핀이 더 강하게 덮는다) 중 하나에 속해야 하고, 둘 다 아니면 실패하는 전수 시험을 넣었다. 역방향 드리프트(없어진 리프를 가리키는 핀)와 **게이트 자신의 죽은 검사 여부**도 시험한다. 모듈 독스트링의 과대 주장을 실제 범위로 정정했다 |
| HIGH-3 이탈 목록 불완전(실측 41) | 위 §7.3 전수 |
| MEDIUM-1 README `five`→`four` | 재측정 결과 이제 **`two`**(B3 로 `currentness`·`monitor_coverage` 가 채워졌다) |
| MEDIUM-2 §7 이 이탈 ② 누락 | §7.3 (ㄹ)(ㅁ)(ㅂ) 표에 ①~⑤ 전건 등재 |
| MEDIUM-3 `authority` [D]→§4.3 치환 미공시 | 이탈 ⑤ 로 등재 + 파일 헤더에 ⚠ 명시 |
| MEDIUM-4 「25중 15」 재현 불가 | `tos/runtime/tests/compose/_loader_probe.py` 를 **커밋**했다(직접 실행 가능) · 테스트가 분할을 **이름으로** 고정한다. 현재 **17 PASS / 25** |
| LOW-1 `monitor_coverage:26` §4.3 과대 인용 | 실제 출처(2026-09-12 §4)로 정정 |
| LOW-2 `*_digest` 이름 5건 | §0.2 와의 관계를 두 파일 헤더에 명시 + §7.3 (ㄴ) |
| LOW-3 `safety_activation` 은 절반만 로드 | 프로브가 `safety_activation.yaml::members` 를 **별도 행**으로 세므로 집계가 이 파일을 온전히 로드되는 것처럼 보이지 않는다 |

- **뮤테이션 방법론** — review-794 의 지적대로 `yaml.safe_dump` 왕복을 버리고 **텍스트 치환**으로
  바꿨다(왕복은 헤더 주석을 날려 출처 시험이 먼저 터지는 공허한 RED 를 만든다).
