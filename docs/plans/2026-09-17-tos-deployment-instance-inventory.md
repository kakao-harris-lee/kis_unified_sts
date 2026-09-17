# TOS 배포 인스턴스 설정 인벤토리 (2026-09-17)

W1 레인 D(`feat/tos-deploy-inventory`) — "run 구동" 웨이브의 배포 격차 측정.
`docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md` §0.1, §2 결정 6,
§6.1 ① 소관. **이 문서는 값을 하나도 저작하지 않는다** — 모든 셀은 소스 코드에서
측정한 사실이거나, 운영자가 채워야 할 결정의 종류를 이름 붙인 것뿐이다.

## 0. 측정 방법

`tos_runtime.compose.root.compose_paper_runtime`(구성 루트, `compose/root.py`)와
그 하위 wiring 모듈(`compose/_*.py`)이 `config_dir / "<name>.yaml"` 형태로 참조하는
모든 고정 파일명을 소스에서 추출했다 — `grep -rn "_CONFIG_NAME" tos/runtime/src/tos_runtime/`
+ 각 로더 정의부(`^def load_*`)와 그 호출부를 직접 대조. 파일 상태는
`config/tos_runtime/paper/`(채택)와 `tos/runtime/config/*.example.yaml`(example)을
`ls`로 비교했다.

**필수/옵션 판정 방법**: 각 로더가 호출되는 지점이 (a) 무조건 호출인지, (b) 호출 전에
`if (config_dir / X).is_file(): ...` 게이트가 있는지를 직접 읽었다. 로더 자체의
`if not path.is_file(): raise ...`는 "그 로더가 불려지면 파일이 필수"라는 뜻일 뿐,
그 로더가 무조건 불려지는지는 별개로 확인해야 한다 — 이 둘을 섞으면 오판한다.

## 1. 측정 결과 요약

- **compose_paper_runtime이 참조하는 고정 config-dir 파일명: 정확히 30개**
  (§2 표). 이 중 `strategies/`는 디렉터리이지 단일 yaml 이름이 아니다 — 표에 포함하되
  구분 표시했다.
- **채택(config/tos_runtime/paper/): 6개** — `calendar.yaml`, `risk.yaml`,
  `aggregate_risk_policy.yaml`, `action_flow_policy.yaml`,
  `venue_constraint_policy.yaml`, `order_construction_policy.yaml`.
- **example 뿐(미채택, `tos/runtime/config/*.example.yaml` 또는 `strategies/` 템플릿만 존재): 24개.**
- **은퇴: 1개** (`egress_attestations.yaml` — 30개 목록 밖의 별도 이름; example 없음).
- **해당없음(단일 config-dir yaml 이름이 아니거나 config_dir 밖): 4개 부류** —
  `strategies/`(디렉터리, 그러나 30개 안에 포함), `custody.manifest.yaml`(커스터디 루트),
  `approvals/<digest>.yaml` + `approvals/rearm/<seq>.yaml` + `approvals/alerts/<seq>.yaml`
  + `approvals/rearm/roster.yaml`(승인 디렉터리, 동적/고정 파일명 혼재).
- **궤도 이탈(orphaned) — 30개 목록에 없는데 example만 존재: 2개** —
  `backtest_calibration.yaml`, `evidence_retention.yaml`. 각각 자기 로더
  (`load_backtest_calibration_config`, `RetentionPolicy.load`)가 존재하고 fail-closed
  검증도 갖췄지만, `tos/runtime/src/tos_runtime/compose/*.py` 어디에서도 호출되지
  않는다(측정: `grep -rn "load_backtest_calibration_config\|RetentionPolicy" tos/runtime/src/tos_runtime/compose/`
  결과 0건) — 테스트(`tos/runtime/tests/**`)에서만 단위 검증된 미결선 모듈이다.
  "24개가 배포를 막는다"는 전제와 별개로, 이 둘은 막지도 돕지도 않는 죽은 배선이다.

**핵심 발견 — "24개가 배포를 막는다"는 전제는 반증된다.** 미채택 24개 중
**보수적으로 세도 부팅을 실제로 막는 것은 19개뿐**이고, **5개는 옵트인 기능이라
부재해도 부팅이 성공한다**(§2 표의 "필수/옵션" 열, 근거는 각 행의 file:line).

| 구분 | 개수 | 목록 |
| --- | --- | --- |
| 필수(무조건 호출, 부재 시 그 로더 자신이 raise) | 18 | time, authority, release, safety_envelope, safety_profile, safety_activation, safety_deviations, safety_incidents, monitor_coverage, currentness, currentness_dimensions, risk_attestations, egress_coordinates, broker_scopes, engine, engine_driver, coordinator_preconditions, finality |
| 필수(디렉터리, 없으면 `allow_no_strategies=False` 기본값에서 refuse) | 1 | `strategies/` |
| 사실상 필수(운영 기본 경로에서 필수; 캐치는 테스트 시임뿐) | 0 (이미 채택된 2개가 이 부류였음: aggregate_risk_policy, action_flow_policy) | — |
| 옵션(부재해도 부팅 성공, 기능이 꺼질 뿐) | 5 | `strategy_bindings.yaml`(타입화된 부재), `marketfeed.yaml`+`critical_input_policy.yaml`(함께 옵트인), `nontrade.yaml`, `kis_mock_transport.yaml`(`--transport kis-mock`일 때만) |

이미 채택된 6개 중 `risk.yaml`/`calendar.yaml`은 위 "필수 18/19"에 포함되고,
`aggregate_risk_policy.yaml`/`action_flow_policy.yaml`은 "사실상 필수"(운영 기본
경로 — `root.py:325-336` 참조, 아래 표), `venue_constraint_policy.yaml`/
`order_construction_policy.yaml`은 "필수 18/19"에 포함된다.

## 2. 전체 표 — compose_paper_runtime이 읽는 30개 고정 이름

열 설명: **상태** = 채택/example뿐/은퇴/해당없음. **필수/옵션** = 그 값이 없으면
`compose_paper_runtime`이 실제로 raise하는지, 측정 근거 file:line 포함.
**승인 근거 종류** = 이 파일을 채우는 데 필요한 결정의 **종류**(값 자체를 제안하지 않음):
`측정값`(순수 도출 가능), `운영자 정책 판단`(risk/policy 결정), `파생 digest`(다른 파일에서
계산), `외부 승인 문서`(broker/거래소 공식 자료).

| # | 파일명 | 로더 (function + file:line) | 호출부 (file:line) | 상태 | 필수/옵션 (근거) | 승인 근거 종류 |
|---|---|---|---|---|---|---|
| 1 | `time.yaml` | `load_time_config` — `time/config.py:229` | `compose/_wiring.py:368` (`_build_custody_evidence_time`, 무조건) | example 뿐 | **필수** — 무조건 호출, 로더 자체가 `time/config.py:165`에서 `if not path.is_file(): raise` | 운영자 정책 판단 (시계 소스/허용 지연 임계값) |
| 2 | `authority.yaml` | `load_authority_config` — `authority/epoch.py:211` | `compose/_wiring.py:424` (무조건) | example 뿐 | **필수** — 무조건 호출 | 운영자 정책 판단 |
| 3 | `release.yaml` | `load_release_config` — `release/config.py:164` | `compose/_wiring.py:1029` (`_boot_services`, 무조건, Stage A probe) | example 뿐 | **필수** — 무조건 호출, 이 값이 없으면 어떤 서비스도 구성되지 않음(design #40) | 운영자 정책 판단 (릴리스 승인 게이트 기준) |
| 4 | `safety_envelope.yaml` | (`_safety_wiring.py` 내부, `build_safety_mesh`) | `compose/_safety_wiring.py:517` (무조건) | example 뿐 | **필수** — `build_safety_mesh`는 `_boot_services`에서 무조건 호출 | 운영자 정책 판단 (Hard Safety Envelope) |
| 5 | `safety_profile.yaml` | 상동 | `compose/_safety_wiring.py:518` (무조건) | example 뿐 | **필수** | 운영자 정책 판단 |
| 6 | `safety_activation.yaml` | `load_activation_members` — `venue/activation.py:68` | `_safety_wiring.py:519`, `_riskstate_wiring.py:235`, `_venue_wiring.py:261` (모두 무조건, 같은 파일을 3곳에서 읽음) | example 뿐 | **필수** | 파생 digest (각 policy의 `policy_id`/`generation`/`canonical_digest` — 값 자체는 다른 승인된 정책 파일에서 옴) |
| 7 | `safety_deviations.yaml` | (`_safety_wiring.py` 내부) | `_safety_wiring.py:524` (무조건) | example 뿐 | **필수** | 운영자 정책 판단 |
| 8 | `safety_incidents.yaml` | 상동 | `_safety_wiring.py:527` (무조건) | example 뿐 | **필수** | 운영자 정책 판단 |
| 9 | `monitor_coverage.yaml` | 상동 | `_safety_wiring.py:531` (무조건) | example 뿐 | **필수** | 운영자 정책 판단 |
| 10 | `risk.yaml` | `load_adverse_scenario_set`/`load_required_scenario_kinds` — `risk/aggregate.py:142,196`; `_load_action_flow_envelope` — `_currentness_wiring.py:125` | `_currentness_wiring.py:230,232,237` (무조건, 한 파일을 3개 로더가 읽음) | **채택** | **필수** | (이미 채택됨 — Adverse Scenario Set + 증폭 envelope) |
| 11 | `currentness.yaml` | `load_currentness_config` — `currentness/config.py:80` | `_currentness_wiring.py:205` (무조건) | example 뿐 | **필수** | 운영자 정책 판단 (`required_dimensions` 선언) |
| 12 | `currentness_dimensions.yaml` | `load_pending_currentness_dimensions` — `compose/_pending_dimensions.py:196` | `_currentness_wiring.py:275` (무조건) | example 뿐 | **필수** | 운영자 정책 판단 (17개 pending dimension당 4필드) |
| 13 | `risk_attestations.yaml` | `load_risk_attestations` — `compose/_risk_attestations.py:161` | `_currentness_wiring.py:278` (무조건) | example 뿐 | **필수** | 운영자 정책 판단 (6개 step 6/7 admission witness) |
| 14 | `egress_coordinates.yaml` | `load_egress_coordinates` — `compose/_egress_coordinates.py:145` | `compose/_wiring.py:943` (무조건) | example 뿐 | **필수** | 외부 승인 문서 (broker 좌표) + 운영자 정책 판단 |
| 15 | `broker_scopes.yaml` | `load_broker_scopes` — `brokercap/scopes.py:747` | `compose/_wiring.py:947` (무조건) | example 뿐 | **필수** | 운영자 정책 판단 (broker scope 테이블) |
| 16 | `calendar.yaml` | `load_calendar_config` — `calendar/config.py:350` | `compose/root.py:260` (무조건, 로더 자체는 `calendar/config.py:362`에서 `if not path.is_file(): raise`) | **채택** | **필수** | (이미 채택됨 — 2026-09-16 §6②) |
| 17 | `venue_constraint_policy.yaml` | `load_venue_constraint_policy` — `venue/_venue_policy_loader.py:381` | `compose/_venue_wiring.py:249` (무조건, `build_venue_service`는 root.py에서 항상 호출) | **채택** | **필수** | (이미 채택됨) |
| 18 | `order_construction_policy.yaml` | `load_order_construction_policy` — `venue/_order_construction_policy_loader.py:637` | `compose/_venue_wiring.py:252` (무조건) | **채택** | **필수** | (이미 채택됨) |
| 19 | `engine.yaml` | `load_engine_config` — `compose/_engine_config.py:64` | `compose/_finalize_wiring.py:78` (무조건) | example 뿐 | **필수** | 측정값/운영자 정책 판단 혼합 (`dsl_evaluation_budget_steps`, `max_unresolved_send_per_scope` — 2026-09-08 명시적 운영자 결정 대상으로 이월된 값) |
| 20 | `engine_driver.yaml` | `load_engine_driver_config` — `compose/_engine_wiring.py:159` | `_finalize_wiring.py:109`, `_recovery_wiring.py:127` (모두 무조건) | example 뿐 | **필수** | 운영자 정책 판단 (replay window) |
| 21 | `coordinator_preconditions.yaml` | `load_coordinator_preconditions_config` — `compose/_preconditions.py:124` | `_finalize_wiring.py:152` (무조건) | example 뿐 | **필수** | 운영자 정책 판단 (`live_authorization_state`, `nonlive_broker_consuming.admitted`) |
| 22 | `finality.yaml` | `load_finality_config` — `posttrade/config.py:121` | `_finalize_wiring.py:155`(무조건), `_release_wiring.py:103`(무조건, `apply_release_wiring`도 root.py에서 항상 호출) | example 뿐 | **필수** | 운영자 정책 판단 (SYNTHETIC post-trade finality) |
| 23 | `strategies/` (디렉터리, 단일 yaml 아님) | `load_strategies` — `strategy/loader.py:230` | `strategy/resolve.py:558` 부근, `resolve_strategy_registry` 경유 — `compose/_wiring.py:1080`에서 호출 | example 뿐 (`tos/runtime/config/strategies/` 템플릿만) | **필수** (조건부) — `allow_no_strategies=False`(기본값)이고 `injected_registry`도 없으면 디렉터리 부재 시 `StrategyRegistryResolutionRefused` (`resolve.py:544-":` 부근) — 운영 기본 경로에서 필수, 우회는 테스트 전용 주입 경로뿐 | 해당없음 — 전략 DSL 파일 자체(각 전략의 config 값) |
| 24 | `strategy_bindings.yaml` | `load_strategy_bindings` — `strategy/bindings.py:133` | `strategy/resolve.py:559` 부근 (`strategies/` 사용 시에만 호출) | example 뿐 | **옵션** — `bindings.py:150-153`: 파일 부재 시 예외가 아니라 `LoadedStrategyBindings(present=False, ...)` 타입화된 부재를 반환 (fail-closed 아님, "부재는 합법적 상태") | 운영자 정책 판단 (전략별 config-ref 바인딩; 필요한 전략이 없으면 안 채워도 됨) |
| 25 | `aggregate_risk_policy.yaml` | `load_aggregate_risk_policy` — `riskstate/_aggregate_risk_policy_loader.py:373` | `compose/root.py:326` (존재 검사), `_riskstate_wiring.py:226` (무조건 호출, 파일이 있을 때만 도달), `_cli_ops.py:105`(CLI print-policy-digests 전용, boot 무관) | **채택** | **사실상 필수** — `root.py:328-336`: 이 파일과 `action_flow_policy.yaml` 둘 다 없고 동시에 `aggregate_risk_inputs_provider`/`action_flow_inputs_provider` 콜러블이 모두 주어지지 않으면 `RiskStateConfigError`로 부팅 거부. 운영 기본 경로(`RiskStateService` 프로덕션 사용, provider=None)는 이 파일을 요구함 — 명시적 콜러블 주입은 테스트 시임(같은 라인의 주석) | (이미 채택됨) |
| 26 | `action_flow_policy.yaml` | `load_action_flow_policy` — `riskstate/_action_flow_policy_loader.py:494` | `compose/root.py:327`, `_riskstate_wiring.py:229`, `_cli_ops.py:113`(CLI 전용) | **채택** | **사실상 필수** (25와 동일 쌍 판정) | (이미 채택됨) |
| 27 | `marketfeed.yaml` | `load_marketfeed_config` — `compose/_marketfeed_wiring.py:160` | `compose/_marketfeed_wiring.py:228` (호출 전 `if not config_path.is_file(): return None` 가드 — `_marketfeed_wiring.py:229`) | example 뿐 | **옵션** — `build_tick_scheduler`(root.py:543에서 무조건 호출되지만 함수 내부가 옵션 처리) 자신의 docstring: "``None`` when ``marketfeed.yaml`` is absent (an operator who has not adopted this wave)" | 운영자 정책 판단 (tick 소스 계측) — 2026-09-16 틱 원천 웨이브가 이미 서베이함 |
| 28 | `critical_input_policy.yaml` | `load_critical_input_policy` — `marketfeed/policy.py:270` | `_marketfeed_wiring.py:233` — **오직 `marketfeed.yaml`이 존재할 때만 도달**(둘 다 없으면 둘 다 안 읽음; `marketfeed.yaml`만 있고 이게 없으면 그때는 이 로더가 raise) | example 뿐 | **옵션 (marketfeed.yaml과 함께)** — `_marketfeed_wiring.py` 모듈 docstring이 "optional-together"로 명명 | 운영자 정책 판단 |
| 29 | `nontrade.yaml` | `load_required_legs_config` — `nontrade/config.py:79` | `_session_wiring.py:303`(호출 전 가드는 호출부인 `root.py:511`: `if (config_dir / NONTRADE_CONFIG_NAME).is_file() else None`) | example 뿐 | **옵션** — `root.py:495-498` 주석: "config_dir with no nontrade.yaml at all ... leaves composed.nontrade None ... never a boot refusal" | 운영자 정책 판단 (non-trade 승인 leg) |
| 30 | `kis_mock_transport.yaml` | `load_kis_mock_transport_config` — `transport/kis_mock/config.py:402` | `compose/_transport_wiring.py:203` — `resolve_transport_boot`가 `kind is TransportKind.SYNTHETIC`이면 즉시 `return None`(`_transport_wiring.py:177-178`), `kis-mock`일 때만 로더 도달 | example 뿐 | **옵션 (기본 synthetic 전송에서는 무관)** — `--transport kis-mock`을 명시할 때만 필수로 전환 | 외부 승인 문서 (KIS MOCK REST base 등) + 운영자 정책 판단 |

## 3. 30개 목록 밖 — 특수 케이스

| 파일명/경로 | 위치 | 상태 | 비고 |
|---|---|---|---|
| `egress_attestations.yaml` | `config_dir` 직속 | **은퇴** | `_session_wiring.py:95-101`(`RETIRED_EGRESS_ATTESTATIONS_CONFIG_NAME`), `_session_wiring.py:179-183`: **존재하면** `RetiredConfigPresent`로 부팅 거부(내용을 읽지 않음 — 존재 자체가 신호). example 파일 없음(의도적 — 사용을 유도하면 안 됨). |
| `custody.manifest.yaml` | `custody_root` (config_dir 아님) | 해당없음 | `custody/file_custody.py:91` `MANIFEST_FILENAME`. `tos/runtime/config/custody.manifest.example.yaml`은 example 존재하나, 이건 D4 커스터디 루트의 파일이지 `config_dir`의 파일이 아니다. |
| `approvals/<proposal_digest>.yaml` | `custody_root/approvals/` | 해당없음 | `compose/_wiring.py:248` — IAP(Independent Approval) 결정, digest로 키잉된 동적 파일명. 고정 이름 없음. |
| `approvals/rearm/<latched_evidence_seq>.yaml` | 상동 | 해당없음 | `safety/rearm.py:541` — re-arm 승인, seq로 키잉. |
| `approvals/rearm/roster.yaml` | 상동 | 해당없음 | `safety/rearm.py:647` — 유일하게 고정 이름이지만 approvals 디렉터리 소속(config_dir 아님). |
| `approvals/alerts/<alert_seq>.yaml` | 상동 | 해당없음 | `safety/ack.py:252` — alert ack, seq로 키잉. |
| `backtest_calibration.yaml` | `config_dir` 직속 (주장상) | 궤도 이탈 (example 뿐, 그러나 미결선) | 로더 `load_backtest_calibration_config` — `backtest/config.py:42,122`. `tos/runtime/config/backtest_calibration.example.yaml` 존재. **측정: `tos/runtime/src/tos_runtime/compose/*.py` 어디에도 호출부 없음** — compose 부팅과 무관. 테스트(`tos/runtime/tests/backtest/`로 추정)에서만 단위 검증. |
| `evidence_retention.yaml` | `config_dir` 직속 (주장상) | 궤도 이탈 (example 뿐, 그러나 미결선) | 로더 `RetentionPolicy.load` — `evidence/retention.py:76`. `tos/runtime/config/evidence_retention.example.yaml` 존재. **측정: `grep -rn "RetentionPolicy" tos/runtime/src/tos_runtime/compose/` 결과 0건** — `evidence/__init__.py`의 재export와 `tos/runtime/tests/evidence/test_retention.py` 외에는 아무도 부르지 않는다. |

## 4. 이미 채택된 6종 안에 남은 TBD 리프 (정확한 키 경로)

측정: `grep -n "TBD" config/tos_runtime/paper/*.yaml`.

- **`calendar.yaml`**: TBD 없음.
- **`risk.yaml`**: TBD 없음.
- **`aggregate_risk_policy.yaml`**: `policy_version`(L36), `canonical_digest`(L38),
  `account_scope: ["TBD"]`(L43), `instrument_scope: ["TBD"]`(L46),
  `envelope_id`(L50), `envelope.canonical_digest`(L52), `profile_id`(L54),
  `profile.canonical_digest`(L56), `activation_record_id`(L93).
- **`action_flow_policy.yaml`**: `policy_version`(L46), `canonical_digest`(L48),
  `account_scope: ["TBD"]`(L54), `envelope_id`(L60), `envelope.canonical_digest`(L62),
  `profile_id`(L64), `profile.canonical_digest`(L66), `activation_record_id`(L107).
  (`instrument_scope` 키 자체가 이 파일에는 없음 — `aggregate_risk_policy.yaml`과
  스키마가 다르다.)
- **`venue_constraint_policy.yaml`**: `canonical_digest`(L49),
  `scope.accounts: ["TBD"]`(L58), `scope.instruments: ["TBD"]`(L61),
  `activation_record_id`(L109).
- **`order_construction_policy.yaml`**: `canonical_digest`(L71),
  `scope.accounts: ["TBD"]`(L79), `scope.instruments: ["TBD"]`(L82),
  `activation_record_id`(L132), `admitted_quantity_bases: ["TBD"]`(L169),
  중첩 sizing 값 `value: "TBD"`(L187).

**공통 패턴**: `canonical_digest`/`*_id`/`activation_record_id` 계열은 **파생 digest**
(다른 승인된 정책 문서 + `safety_activation.yaml`의 `members:`에서 계산되어야 함 —
README §"...`print-policy-digests`가 그 digest를 출력한다"). `account_scope`/
`instrument_scope`/`scope.accounts`/`scope.instruments`는 **운영자 정책 판단**
(어느 계좌/종목에 이 정책이 적용되는지). `admitted_quantity_bases`/sizing `value`는
**운영자 정책 판단**(전략 파일의 `quantity_basis`가 먼저 정해져야 함 — 순서 의존).

## 5. 확인 불가

- `engine.yaml`의 두 필드(`dsl_evaluation_budget_steps`, `max_unresolved_send_per_scope`)가
  정확히 어떤 값이어야 하는지는 이 인벤토리의 범위 밖이다 — 2026-09-08 운영자 처분 로그에
  "값 자체는 운영자 결정 이월"로 남아 있고, 이 레인은 그 결정을 내리지 않는다.
- `time.yaml`/`authority.yaml`의 세부 임계값(허용 지연, epoch 정책)이 실제 KIS MOCK
  paper 환경에 맞는 구체적 수치가 무엇인지는 각 example 파일의 주석 이상으로 조사하지
  않았다 — 코드 경로(필수 여부)만 측정했고 값의 타당성은 판단하지 않았다.
- `strategies/` 디렉터리에 실제로 어떤 전략 파일이 배치될지는 strategy-lab/운영자
  소관이며, 이 레인은 "디렉터리가 없으면 거부된다"는 배선 사실만 측정했다.
