# TOS 아크 계획 — `run` 구동 · (c2) 실 시세 · 브로커 증인(P-BAL) · 커널 라운드 #4

- 작성: 2026-09-17 · 세션 모델 단독 저작(운영자 지시 2026-09-04)
- 기준선 실측(main `7b76e217`): 런타임 **2292 passed**(exit 0) · 커널 **9522 passed**(exit 0)
- 선행: (a′) 웨이브 `f702ea07` 착지(`docs/plans/2026-09-16-tos-aprime-envelope-order-shape-plan.md`)
- 운영자 지시(2026-09-17): 「ConstructionConfig 로더, (c2) 실 시세 어댑터, 브로커 증인(P-BAL),
  커널 라운드 #4 진행」 — (a′) 계획 §6 ④ 의 잔여 순서와 동일(단 「실 HSE 인스턴스」는 미언급,
  §6 ① 참조)

---

## 0. 서베이 실측 (요지)

네 갈래를 병렬 서베이했다. **첫 항목의 전제가 다시 한 번 뒤집혔다.**

### 0.1 ★ `run` 을 막는 것은 로더가 아니다

(a′) 계획 §4.4 는 「웨이브가 끝나면 `ConstructionConfig` 는 스칼라 7개만 남고, 그것들을 설정
파일에서 읽는 로더 하나면 `run` 이 실제로 구성할 수 있다」고 적었다. **로더는 필요조건이고,
부팅의 충분조건이 아니다.**

| 실측 (상수를 값으로 해소해 기계적으로 열거) | 값 |
|---|---|
| `config_dir` 에서 읽는 YAML 이름 | **30종** — 여기에 은퇴명 `egress_attestations.yaml` 이 **포함**된다(존재하면 부팅 거부 · `_session_wiring.py:95-101`). 활성은 **29종** |
| 적재 대상 총계 | **30** = 활성 YAML 29 + `strategies/` 디렉터리 |
| 그중 승인된 배포 인스턴스(`config/tos_runtime/paper/`) | **6종** — `calendar` · `venue_constraint_policy` · `order_construction_policy` · `aggregate_risk_policy` · `action_flow_policy` · `risk` |
| 미승인 | **24** = 활성 YAML 23(전부 `tos/runtime/config/*.example.yaml` 뿐 · 전 리프 `null`) + `strategies/`(승인 전략 파일 0건 — `example.strategy.yaml` 뿐) |
| 그중 **실제로 부팅을 막는 것** | **19**. 나머지 **5 는 진짜 옵트인** — `strategy_bindings.yaml`(`strategy/bindings.py:151-153` 이 `present=False` 를 돌려줌) · `marketfeed.yaml`+`critical_input_policy.yaml`(`_marketfeed_wiring.py:228-232`) · `nontrade.yaml`(`root.py:511`) · `kis_mock_transport.yaml`(`--transport synthetic` 기본에서 미접촉) |
| `config_dir` 밖 | `custody.manifest.yaml`(`--custody-root` 소속) · `approvals/**`(digest·seq 키잉) |
| 고아 2종 (레인 D 발견) | `backtest_calibration.yaml` · `evidence_retention.yaml` — example 과 fail-closed 로더가 **있는데** 컴포즈 호출부가 **0건**. 부팅을 막지도, 옵트인도 아닌 **미결선** |
| 이미 채택된 6종 안의 `TBD` 리프 | `scope.accounts`/`scope.instruments`·`account_scope`/`instrument_scope`·`admitted_quantity_bases`·`authorized_axes` 의 `DIRECTION`·`canonical_digest`/`policy_version`/`activation_record_id` |

즉 **로더를 쓰고 `run` 을 결선해도 배포 인스턴스는 부팅하지 않는다.** 부팅하지 않는 이유가
「로더가 없다」에서 「승인된 값이 없다」로 바뀔 뿐이고, 후자는 코드가 아니라 **운영자 승인**이
해소한다. 이 계획은 두 문장을 분리해서 쓴다 — 레인은 「(로더가) 결선됐다」를 쓰고,
「`run` 이 배포 인스턴스를 부팅한다」는 24종이 승인되기 전에는 **쓰지 않는다**.

### 0.2 W1 나머지 실측

- `cli.py:935` — `if isinstance(args, Args): return 0`. `Args` 7필드(`config_dir`·`data_dir`·
  `custody_root`·`environment_label`·`transport`·`projection_path`·`backup_root`)는 **이미 전부
  파싱된다** — 선언 `cli.py:218-230` · 플래그 `_add_run_arguments` `cli.py:321-385` · 생성 `cli.py:552-560`.
- `compose_paper_runtime` (`root.py:150-172`)의 필수 인자 중 CLI 가 못 주는 것은 **`construction`
  하나뿐**. 나머지 **11개**는 전부 기본값이 있고, risk provider 2종은 (b) 웨이브가 `None` 기본으로
  이미 해소했다.
- `ConstructionConfig` (`compose/_types.py:135-179`)는 스칼라 7 + `price: AdmittedPriceObservation
  | None` 8필드. `price` 는 `_wiring.py:536` 한 곳에서만 읽히고, **틱 원천이 있으면 per-tick
  value view 가 이긴다** — `OrderConstructionStage._price_for`(`tos/src/tos/egressgw/
  construction.py:986-997`)가 `price_field_key` + view 동시 존재 시 view 를 택한다(`:997` 이 실제
  `admitted_price_from_view` 반환 줄).
- 루프는 **이미 있다**: `TickScheduler.run_forever(*, sleep, stop)`(`marketfeed/scheduler.py:392`),
  `tick_once`(`:341`)는 실제로 컴포즈된 런타임에서 e2e 실증됨
  (`tests/compose/test_marketfeed_wiring.py:158`). `run_forever` 자체는 주입 `sleep`/`stop` 으로
  단위 테스트만 됨(`tests/marketfeed/test_scheduler.py:262`) — 컴포즈 런타임 상대 e2e 는 없다.
- **후보 결함(레인이 실측 후 처분)**: `_wiring.py:562`
  `required_authority_scope=(f"scope-{construction.instrument}",)` — 권한 스코프 문자열을
  instrument 에서 **합성**한다. 거버넌스 원천이 없는 값이 술어의 인자로 들어가는 모양이며,
  (a′) 가 정체성 리터럴에서 잡은 것과 같은 부류일 수 있다.

### 0.3 W2 — (c2) 실 시세 어댑터

- **플러그 지점은 하나**: `ObservationIntake.poll(*, instrument, after_as_of_ms) ->
  Sequence[RawObservation]`(`marketfeed/ports.py:105-131`)를 구현해
  `TickScheduler(intake=…)`(`scheduler.py:293`)에 넘긴다. **marketfeed 의 다른 모듈은 무변경.**
  포트 독스트링이 이미 이 후속을 지명하고 있다(`ports.py:109-113` — 다만 리터럴은 「(c2)」가 아니라
  「plan §6 ①」이다).
- HTTP 는 **stdlib 만**. 런타임 스코프는 `socket`/`ssl`/`http`/`urllib.request` 카브아웃을
  갖지만(`tools/tos_firewall_check.py:245-246`) 서드파티 HTTP 클라이언트는 허용목록에 없다
  (`THIRD_PARTY_ALLOWED` `:164-166`). 선례 `KisMockHttpClient`(`transport/kis_mock/client.py`)가
  **호스트 씰 · TR id 형상 가드 · 토큰 발급 · fail-closed 로더**를 전부 갖고 있다.
- 헤르메틱: `tests/transport/kis_mock/_fake_kis_server.py`(stdlib `ThreadingHTTPServer`,
  `127.0.0.1`) + autouse 네트워크/쓰기 가드(**`tos/runtime/tests/conftest.py`** — 네트워크 `:151-158`, 쓰기 `:203-244`. 루트 `tests/conftest.py` 가 **아니다**). **새 테스트
  인프라 불요.**
- **측정된 브로커 사실**(`docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml`):
  - 모의 자격증명으로 **실제 시세 본문 수신 실증** — P-16 `20260729T133539Z`, 005930, n=5,
    errors 0 (`:2316`, `:2347`). 서베이가 「모의 지원 확인 불가」로 남긴 항목은 이 실측이 해소한다.
  - **환경 분리는 도메인이 아니라 TR 계열 단위로 강제된다**(`:4348-4361`): 실전 도메인이 모의
    앱키에 대해 **시세 TR 은 정상 응답**하고 거래 TR 만 `EGW02004` 로 거부한다. 함의가 그대로
    적혀 있다 — 「모의 앱키로 실전 도메인 시세를 읽는 구성은 **조용히 동작한다**」. 그러므로
    호스트 씰은 문서가 아니라 **구조 가드**여야 한다(kis_mock 선례 `config.py:303-354` 그대로).
  - 시세 TR: 주식 `FHKST01010100` `/uapi/domestic-stock/v1/quotations/inquire-price`
    (`shared/kis/client.py:594-605`) · 지수선물 `FHMIF10000000`
    `/uapi/domestic-futureoption/v1/quotations/inquire-price`(`:662-669`). *레거시는 참조용이며
    import 하지 않는다(방화벽).*
- **두 개의 정직한 공백 — 계획이 앞에 세운다.**
  1. `inquire-price` 응답에서 현행 코드가 읽는 **서버측 이벤트 시각 필드가 없다**. 레거시는
     `"timestamp": time.time()` 로 자기 시각을 찍는다(`shared/kis/client.py:648`). 그대로 옮기면
     `as_of_ms` 가 **수신 시각**이 되어 「관측 시각」을 참칭한다.
  2. 서버 네이티브 `raw_event_id` 가 없다 → 합성해야 하는데, per-observation distinctness 가
     스냅샷 digest 의 근거이므로(`ports.py:25-29`) 아무 합성이나 되지 않는다.
  → 레인은 **먼저 실측**한다(체결가 계열 TR 이 `stck_cntg_hour` 같은 체결 시각을 싣는지). 실으면
  그것을 `as_of` 로 쓰고, 안 실으면 **`as_of` 를 수신 시각으로 쓰되 그 사실을 필드·독스트링·
  §7 에 등재**한다. 「라이브 피드」라고 쓰지 않는다.
- `snapshot_age_bound` 는 여전히 **측정이 아니라 주입 경계값**이다(틱 원천 계획 §7). (c2) 가
  자동으로 해소하지 않는다.
- 단일 instrument 제약 유지 — FORWARD-OBLIGATION-MS1 미비준(`tos/src/tos/backtest/driver.py:78-86`).

### 0.4 W3 — 브로커 증인 (P-BAL)

- 포트는 **이미 있다**: `BrokerWitness.observe(scope) -> WitnessSnapshot`
  (`recon/ports.py:136-149`). 구현은 합성 1종뿐이고
  `independent_of_evidence_store=False` 가 **기계적으로** 고정돼 있다
  (`witness_synthetic.py:209-218`, 독립검토 F2).
- 커널은 독립성을 **계산하지 않는다 — 주입된 판단**이다(`tos/src/tos/recon/state.py:1-13`,
  `EvidencePathObservation.independence_class`). 따라서 실 증인이 들어오는 순간
  `CORROBORATED` 가 구조적 라벨에서 **실질**로 바뀐다. 이것이 이 웨이브의 값어치다.

  > **★ 이 문장은 W3 착지 과정에서 반증됐다(2026-09-17).** 오더 축에서는 성립하지 않는다 —
  > KIS 주문체결조회 응답에 `attempt_id` 개념이 없어 `WitnessOrder.attempt_id` 가 구조적으로
  > 항상 `None` 이고, `ReconciliationService.reconcile` 은 `attempt_id` 로만 조인한다
  > (`broker_execution_id` 교차조회 없음). 그 결과 같은 주문이 한쪽에서
  > `STALE_RESERVATION` 으로 강등되고 다른 쪽에서 `ORPHAN_BROKER_ORDER` 로 다시 등장한다 —
  > 화해가 아니라 **이중 계상**이다. 방향은 fail-closed 라 안전 불변식은 깨지지 않으며,
  > 이는 술어로 증명됐다(`WitnessOrder` 생성 지점 1곳 · `attempt_id=None` 무조건 →
  > `witness_by_attempt` 항상 공집합 → `MATCHED` 분기 도달 불가 → `rearm_ok`/`capacity_ok`
  > 항상 False). **`positions`/`cash` 축은 영향 없다** — 포지션은 attempt 조인이 필요 없고,
  > 독립적이고 연속키를 완주한 포지션 읽기가 이 웨이브가 실제로 배달한 것이다.
  > 상세: §7.2 W3 행 · PR #726.
- P-BAL 은 `kind=REAL_READ_ONLY` · `emits_orders=False` · `risk=LOW`
  (`tools/broker_probes/registry.py:733-770`). **정책 금지 대상이 아니다** — 영구 차단은 P-R5
  계열(실주문·실자금)뿐이고 루트 `CLAUDE.md:40` 이 「GET-only real reads are fine」로 명시한다.
- **측정 증거가 이미 있다 — 그리고 그것이 설계를 강제한다.** PR #676(**OPEN**, 모의 서버 캠페인)에
  P-BAL 아티팩트 7건: 모의 주식 잔고 **25행 / 2페이지 · `page_size` 20 ·
  `TRUNCATION_RISK_DEMONSTRATED`**. 즉 **한 페이지만 읽는 증인은 포지션을 과소보고한다.**
  레거시가 정확히 그 모양이고(`shared/kis/client.py:931-932` 한 페이지), 그 과소보고가
  `services/trading/broker_verification.py:188-190` 에서 `remove_position(reason="broker_absent")`
  로 포지션을 파괴한다. **새 증인은 연속키를 완주하거나 `WitnessUnavailable` 을 올린다. 조용한
  절단은 없다.**
- 선물 모의 잔고 TR 은 **존재하지 않는다**(`shared/kis/client.py:1040` NOTE, 가드 `:1055`) →
  선물 증인은 P-CA 선례대로 **거부**한다.
- **잔고 TR 하나로는 `orders` 를 답할 수 없다.** `WitnessSnapshot.orders` 를 빈 튜플로 돌려주면
  포트 독스트링이 허용하는 「조회했고 없었다」와 **조회조차 안 했다**가 구별되지 않는다 —
  고아 주문 탐지가 구조적으로 불가능해진다(같은 부류의 금지가 `recon/ports.py:22-27` 모듈 독스트링과 `:124-135` `WitnessUnavailable` 독스트링에 있다 — 「답하지 못한 증인」은 빈 스냅샷이 아니다).
  → 운영자 확인 ③.

### 0.5 W4 — 커널 라운드 #4 후보

| 후보 | 근거 | 커널 diff |
|---|---|---|
| ① `construct_candidate_command` 에 OCP **approval/signer** 결속 | DR-0002 §6 이 「a kernel round that binds the Order Construction Policy's approval fields」로 **명시 예견** · venue 계획 `:133`/`:160` | 예. **정정(리뷰 HIGH)**: 이 함수는 키워드 인자 14개를 받고 `policy_id`/`policy_version`/`policy_generation` 은 **이미 결속한다**(`construction.py:556-570`). 빠진 것은 인자 개수가 아니라 **종류** — 이 모듈 전체에 `signer`/`approval` 개념이 **0건**이다(grep 실측). 「좌표 3개만 받는다」는 앞선 서술은 「정책 사실 중 식별 좌표 3개만 결속한다」는 뜻이었고, 문언이 총 인자 수로 오독될 수 있어 정정한다 |
| ② 주식 **가격대별 tick 표** | venue 계획 `:133` — 현재 선물 단일 `tick_size` 만 | 예 (`tos/src/tos/venue/records.py:113`) |
| ③ `tos.position` — 체결 합·보수 사용량 **술어 패키지** | DR-0003 §6 · risk-state 계획 `:136` | 예 (신규 패키지) |
| ④ RCL 예약 행에 **committed 벡터 영속** | risk-state 계획 `:136` — 「RCL 투영에 크기 없음」 | 예 (`tos/src/tos/rcl/`) |
| ⑤ Phase 3 §7.11 미해소 이월 | `docs/plans/2026-09-09-tos-phase3-event-core-plan.md:294` — ⓐ 전역 new-risk 래치 · ⓑ · ⓓ · ⓕ · ⓗ · ⓘ · ⓙ | 항목별 |

- 서베이 정정: 「라운드 #2 이월 6건」은 오독이었다. 라운드 #2 의 "deferred 6" 은 이월 항목이
  아니라 `SendBoundaryContext` 에 추가된 **안전-attestation 입력 필드 6개**다.
  **재정정(리뷰 MEDIUM — 정정문 자체가 과장이었다)**: 라운드 #2 §7 「이월」 줄은 2건이 아니라
  **4건**이고(① `load_egress_attestations` docstring · ② 계약문서 인용 드리프트 · ③ 운영자 확인 ⑵
  `False⇒DENIED` 극성 · ④ 운영자 확인 ⑴ W2-K/ⓖ), 라운드 #3 에서 해소가 확인되는 것은 **③④ 둘뿐**이다.
  ①② 는 해소 근거를 찾지 못했다(성격상 「이월」보다 동결 기록에 가깝다) — **확인 불가**로 남긴다.
### 0.5.1 항목별 정밀 실측 (2026-09-17 · 운영자 처분 ④ 이후)

운영자가 ①②③④ 를 전부 선택한 뒤 항목별로 다시 실측했다. **둘의 성격이 바뀌었다.**

| 항목 | 실측 결과 |
|---|---|
| ① OCP approval 결속 | **★ 정정(정밀 실측)**: 커널 레코드 타입은 이미 갖고 있다 — `OrderConstructionPolicy._COVERED_FIELDS`(`tos/src/tos/ioc/records.py:278-289`)가 `signer_identity`/`approval_identity`/`evidence_package_ref` 를 **digest 커버 대상으로 이미 열거**한다. 빠진 것은 세 곳이다: (a) `construct_candidate_command` 이 `.issue()` 에 그것들을 **넘기지 않는다**(`construction.py:626-631` → 전부 `None` 기본값) · (b) 런타임 로더가 셋을 **의도적으로 `None` 으로 고정**한다(`_order_construction_policy_loader.py:719-724`) — 오늘 충돌이 없는 이유는 커널이 막아서가 아니라 **양쪽이 똑같이 비워서**다 · (c) **OCP 스펙 템플릿에 해당 키가 아예 없다**(`ORDER-CONSTRUCTION-POLICY-template.yaml`). 즉 ① 은 커널 diff 만이 아니라 **검증 템플릿 저작(비-코드 거버넌스 산출물)** 을 포함한다. 착지 시 `tos/tests/egressgw/_egressgw_fixtures.py:216 construction()` 이 단일 초크포인트(11개 테스트 파일이 의존)이고, 새 kwarg 가 실값을 실으면 **픽스처 파생 digest 가 전부 바뀐다** |
| ② 주식 가격대별 tick 표 | **★ 이 저장소에 측정된 KRX 주식 호가단위 원천이 0건이다.** 브로커 프로필의 tick 은 전부 KOSPI200 선물(0.05/0.02pt)이고 등급 C(로컬 설정, 브로커 조회 아님) · `price_band_tick_lot_and_quantity_semantics: UNKNOWN` 이 명시 상태. 즉 ② 는 **형상만** 추가할 수 있고, 실값은 OCP sizing 제안표와 같은 **새 승인 경로**가 필요하다 — 운영자 확인 ⑦ |
| ③ `tos.position` | 추출 경계가 깨끗하다: `PositionObservation` · `worst_credible_directional_usage` · `conservative_current_usage` · `in_flight_overlap_effect` · `_sign_of` · `_classify_sealed_sends`(DR-0003 §2.2 분류표 그 자체)가 순수. `SqliteEvidenceStore`/SQL 은 전부 런타임 잔류 |
| ④ RCL committed 벡터 | **★ 순수 커널 변경이 아니고, 커널 레코드도 반쯤 이미 있다** — `ReservationRecord`(`tos/src/tos/rcl/records.py:35-116`)는 `adverse_increment_vector` 를 **이미 갖고 있다**. 빠진 것은 커밋된 전이의 실제 와이어 형상인 `CapacityReservationTransition`(`rcl/commitlog.py:258-291`)에 벡터 필드가 없다는 것과, 런타임 투영 행에 크기가 없다는 것이다. `apply_reservation_transition` 은 커널이 아니라 `tos_runtime.rcl.log.SqliteCommitLog` 의 메서드다. 영속화는 `reservations` 테이블 **새 컬럼 + RCL 스키마 v1→v2 마이그레이션**(`rcl/schema.py` 와 `operations/schema_migrations.py` 두 곳 미러)을 강제하고, 커널 쪽은 `CapacityReservationTransition` 에 필드를 더하는 일이다 → **`migration-reviewer` 게이트가 추가로 붙는다**(리뷰 레인 규약 §3) |

**라운드 의식(라운드 #3 §1~§5 실측)**: 커널 라운드는 **레인 하나(K)** 로 간다 — venue/OCP 웨이브처럼 팬아웃하지 않는다. 번호 붙은 하위 커밋을 위험 낮은 순서로 쌓고, 각 하위 커밋마다 커널·런타임 스위트가 green 이어야 다음으로 간다. 「런타임 소스 diff 0」은 문자 그대로 0줄이 아니라 **런타임발 판단 0**(커널 변경이 구조적으로 강제하는 소비자 갱신만 허용)을 뜻한다. §5 는 뮤테이션 표와 저자와 다른 sonnet 리뷰를 요구한다.

**착수 시점**: ① 이 `construct_candidate_command` 시그니처를 바꾸면 런타임 소비자(`_wiring.py`)가 따라 바뀐다. W1/W2/W3 브랜치가 전부 그 근방을 만지므로 **W4 는 세 웨이브가 머지된 뒤 착수**한다.

- **③ 은 W3 이 선행이어야 의미가 있다.** DR-0003 §6 이 「브로커 포지션 증인 · 커널 포지션 술어 ·
  valuation 원천」을 같은 줄에 두고, 그중 **어느 하나라도** §2.2 의 한계를 대체한다고 적는다.

---

## 1. 목표 · 범위 · 비범위

**목표.** 네 웨이브를 순서대로 착지시키되, 각 웨이브가 **자기가 실제로 한 것만** 주장하게 한다.

**범위.**
- W1: `construction.yaml` 로더 · `run` 결선(컴포즈 + 루프 + 신호 처리 + 정직한 종료 코드) ·
  컴포즈 런타임 상대 `run` e2e · 배포 인스턴스 **인벤토리와 거부 메시지**.
- W2: `ObservationIntake` 를 구현하는 KIS 모의 시세 어댑터 + 설정 로더(호스트 씰·TR 가드) +
  헤르메틱 테스트 + `as_of`/`raw_event_id` 실측과 등재.
- W3: `BrokerWitness` 를 구현하는 실 잔고 증인(연속키 완주) + `independent_of_evidence_store=True`
  경로의 의미 변화 실증 + 헤르메틱 테스트.
- W4: 운영자가 §6 ④ 에서 고르는 후보만.

**비범위 (명시).**
- **24종 설정값의 저작.** 값은 운영자 승인 사항이다. 레인은 값을 **지어내지 않는다** —
  (a′)·venue·risk-state 웨이브가 지킨 것과 같은 규율(지어낸 거버넌스 값 0).
- 다심볼(FORWARD-OBLIGATION-MS1 미비준) · 파생 지표(`TransformationLineage` 필요) ·
  `snapshot_age_bound` 의 측정화(§8 규칙 후속) · 실주문 경로(P-R5 영구 차단).
- 실 모의 서버에서의 **실행 측정**은 로컬에서 불가하다 — 핸드오버 사항(§6 ②).

---

## 2. 결정 (초안 · 운영자 확인 대상은 §6)

1. **순서**: W1 → (W2 ∥ W3) → W4. W2/W3 는 파일 집합이 서로 겹치지 않는다
   (`marketfeed/`+새 transport 패키지 ∥ `recon/`), 병렬 워크트리로 간다.
   W4 는 커널 전용이라 런타임과 충돌 0 이지만 후보 ③ 이 W3 산출에 의존하므로 마지막.
2. **로더는 `price` 를 표현하지 않는다.** `ConstructionConfig.price` 는 value-free 틱의 임시
   대역이고(`_price_for`), 설정 파일이 가격 리터럴을 싣는 순간 (a′) 가 제거한 **주입 리터럴이
   되돌아온다**. 로더는 항상 `None` 을 넘기고, 필드가 테스트 시임으로만 남는지 레인이 실측해
   — 남을 이유가 없으면 **제거**한다(무시하지 말고).
3. **`run` 은 틱 원천이 없으면 거부한다.** `composed.marketfeed is None` 은 컴포즈에서는 적법한
   상태지만(`_marketfeed_wiring.py` 독스트링), `run` 에게는 **구동할 것이 없다는 뜻**이다.
   0 을 돌려주고 도는 대신 비영 종료 + 이유 출력.
4. **(c2) 의 호스트 씰·TR 가드는 구조 가드다**(문서 아님). 측정된 「조용히 동작한다」(§0.3)가
   근거다. 시세 TR 은 `V` 접두사 규칙이 적용되지 않으므로 **주문용 형상 가드를 그대로 복사하지
   않는다** — 시세 계열의 실제 형상을 실측해 그 형상으로 가드한다.
5. **P-BAL 증인은 연속키를 완주하거나 `WitnessUnavailable`.** 측정된
   `TRUNCATION_RISK_DEMONSTRATED` 가 근거다. 절단을 조용히 보고하는 경로는 만들지 않는다.
6. **W1 은 24종 인벤토리를 코드가 아니라 거부 메시지로 표면화한다.** `run` 이 어느 파일의 어느
   리프에서 멈췄는지 이름으로 말하게 한다(기존 fail-closed 로더들이 이미 그렇게 한다) —
   새 검사 하네스를 만들지 않는다(리뷰 레인 규약 §5).
7. **저작과 검토는 다른 패스**(전역 규약). 레인마다 `model: sonnet` 리뷰 레인을 별도로 띄우고,
   PR 코멘트에 판정을 남긴다. 리뷰어는 **뮤테이션 1건 이상 직접 실행**한다
   ([[review-lane-without-controls-is-opinion]]).

---

## 3. 기각 대안

| 대안 | 기각 사유 |
|---|---|
| W1 에서 24종 설정값을 레인이 채운다 | 승인 원천이 없는 값을 지어내는 것. (a′)·venue·risk-state 가 전부 「TBD 유지 + 로더 거부」로 간 것과 반대 방향 |
| (c2) 에 `requests`/`httpx` 도입 | 허용목록 밖. 설계 문서 PR 사안이며, stdlib 선례가 이미 동작한다 |
| P-BAL 증인이 한 페이지만 읽고 보고 | 측정된 절단 위험을 무보고로 삼키는 것. 레거시의 `broker_absent` 파괴 경로와 같은 결함 |
| 증인이 `orders=()` 를 돌려주고 「없었다」로 처리 | 「조회했고 없었다」와 「조회 안 했다」가 구별 불가 — 고아 탐지가 구조적으로 죽는다 |
| 커널 라운드 #4 를 W1 과 동시에 착수 | 후보 ③ 이 W3 산출 의존. 후보 선택 자체가 운영자 결정(§6 ④) |
| 새 검증 하네스/자동 심판 루프 신설 | 전역 리뷰 레인 규약 §5 가 금지 |

---

## 4. 웨이브 · 레인 (초안)

### W1 — `run` 구동

| 레인 | 범위 | 종료 조건 |
|---|---|---|
| A | `construction.yaml` 로더 + `construction.example.yaml` · named-TBD fail-closed · `"TBD"` 거부 · `price` 미표현(결정 2) | 로더 단위 테스트(정상·누락·`TBD`·형식 오류) · `ConstructionConfig.price` 운명 실측 보고 |
| B | `cli.py` `run` 결선 — `compose_paper_runtime` 호출 · `composed.marketfeed` 부재 시 거부(결정 3) · `run_forever` + SIGINT/SIGTERM → `stop` · 종료 코드 | `main()` 의 `return 0` 제거 · 신호 경로 테스트 |
| C | e2e — 컴포즈된 런타임 상대 `run` 이 실제로 N 틱 돌고 멈춘다(`sleep`/`stop` 주입) · 거부 경로 전수 | `run_forever` 의 첫 컴포즈-상대 e2e |
| D | 배포 인스턴스 인벤토리 — 30종 표 · 6 채택 / 24 미승인 · 각 파일의 결정 소유자 · `config/tos_runtime/README.md` 갱신 · **값 저작 0** | 표가 실측과 일치(스크립트 아닌 실측) |

레인 A 가 발견한 `required_authority_scope` 합성(§0.2)은 **레인 A 가 실측해 처분**한다 — 원천이
있으면 원천화, 없으면 §7 에 등재. 지어내지 않는다.

### W2 — (c2) 실 시세 어댑터

| 레인 | 범위 |
|---|---|
| A | 시세 HTTP 클라이언트 — `KisMockHttpClient` 선례(stdlib, 1요청/호출, 재시도 없음) · 토큰 발급 재사용 |
| B | 설정 로더 `kis_quote.yaml` — 호스트 씰(모의 도메인만) · 시세 TR 형상 가드(실측 형상) · named-TBD |
| C | `ObservationIntake` 구현 — `RawObservation` 생성 · `as_of`/`raw_event_id` **실측 후 결정**(§0.3) · fail-closed |
| D | 헤르메틱 테스트 — `_fake_kis_server` 확장 · 시크릿 비노출 핀 · 네트워크 가드 |

### W3 — 브로커 증인 (P-BAL)

| 레인 | 범위 |
|---|---|
| A | 잔고 HTTP 경로 — 모의 주식 잔고 TR · **연속키 완주** · 완주 실패 시 `WitnessUnavailable` · 선물 거부 |
| B | `BrokerWitness` 구현 — `positions`/`cash` 매핑 · `provenance` · `independent_of_evidence_store=True` |
| C | `ReconciliationService` 경로 실증 — 실 증인일 때 `CORROBORATED` 의 의미가 바뀌는 지점을 테스트로 고정 · 합성 증인과의 차이 |
| D | 헤르메틱 테스트 + 절단 시나리오(2페이지 이상) 재현 |

### W4 — 커널 라운드 #4

운영자가 §6 ④ 에서 고른 후보만. 라운드 규율(라운드 #1~#3 선례): 커널 diff 는 한 라운드에 묶고,
런타임 소스 diff 0 를 유지하며, 문언·예산·극성표를 함께 재등재한다.

---

## 5. 종료 조건 · 게이트 (전 웨이브 공통)

- 게이트: `tools/tos_firewall_check.py` · `lint-imports` · `tos_size_budget.py --check`(**신규 예외 0**) ·
  `ruff`/`black`/`mypy` · 런타임 스위트 · 커널 스위트.
- W1~W3 는 **커널 diff 0**. W4 만 커널을 건드린다.
- 각 레인은 뮤테이션을 정의하고, 리뷰 레인이 **직접 실행**해 red 를 확인한다.
- 테스트 수는 **머지 후 main 에서 재실측**한다(레인 합산 금지 —
  [[parallel-worktrees-share-one-editable-install]]).
- `pytest … | tail` 금지 — 출력 파일의 `passed`/`FAILED` 줄을 인용한다
  ([[pytest-pipe-tail-masks-exit-code]]).

---

## 6. 운영자 확인

1. **W1 의 범위 — 「로더+결선」인가, 「부팅하는 인스턴스」인가.**
   후자는 24종 설정값 승인이 전부 운영자 소관이고, 그중 `safety_envelope.yaml`(실 HSE)·
   `safety_activation.yaml`(digest 손기입)·`time.yaml`·`strategies/` 는 각각 별도 판단이다.
   (a′) §6 ④ 의 원래 순서에는 「실 HSE 인스턴스」가 별도 항목으로 있었는데 이번 지시에는 없다 —
   **W1 에 편입할지, 별도 트랙으로 둘지** 결정 필요. 추천: **W1 은 로더+결선+인벤토리까지**,
   값 승인은 별도 트랙(값마다 승인 근거가 달라 한 웨이브로 묶이지 않는다).
2. **W2/W3 의 실행 측정 위치.** 로컬에서 가능한 것은 **헤르메틱 테스트까지**다. 실 모의 시세
   수신과 실 잔고 페이지네이션 완주는 자격증명이 있는 **모의 서버**에서만 측정된다
   (`docs/runbooks/2026-09-10-p02-probe-handover-paper-server.md` 선례). 코드는 로컬에서 착지시키고
   측정은 핸드오버로 갈지 확인.
3. **W3 의 `orders` 축(§0.4).** 잔고 TR 만으로는 답할 수 없다. (a) 주문체결조회 GET TR 을 증인
   범위에 넣는다 — 새 TR 이 런타임 허용 경로에 들어오므로 승인 필요 · (b) `positions`/`cash` 만
   답하고 orders 축은 **답하지 않음을 명시**한다(포트가 그 표현을 갖고 있지 않으므로 포트 변경이
   따라온다) · (c) W3 를 positions 전용으로 좁히고 orders 는 후속. **추천: (a)** — GET-only이고,
   증인의 값어치(고아 탐지·독립 corroboration)가 orders 축에 있다.
4. **W4 후보 선택(§0.5).** ①~⑤ 중 이번 라운드에 담을 것. **추천: ① + ③**
   (① 은 DR-0002 §6 이 명시 예견한 유일한 항목이고, ③ 은 W3 착지 직후가 가장 싸다).
   ⑤ 의 ⓐ(전역 new-risk 래치)는 **정책 승인**이 선행이라 코드 라운드에 넣지 않는다.
5. **PR #676(OPEN) 처리.** 모의 서버 캠페인 증거 16파일 — 그중 P-BAL 아티팩트 7건이 W3 설계의
   근거다. 계획이 그 값을 인용하므로 **W3 착수 전 머지 여부** 결정 필요. 미머지면 W3 는
   「머지되지 않은 브랜치의 측정」을 인용하게 된다.
6. **Codex 부착 여부.** 이 아크에서 **되돌리기 어려운 경로**에 닿는 것은 W3 의 자격증명 처리와
   (해당 시) W4 의 approval 결속이다. 유료 외부 호출이므로 범위·비용 제시 후 승인받아야 하며,
   기본값은 **미부착**(Claude 측 리뷰 레인 + 게이트).

---

### 6.1 운영자 처분 기록 (2026-09-17)

| # | 항목 | 처분 | 결과 |
|---|---|---|---|
| ① | W1 범위 | **로더 + 결선 + 인벤토리까지** | 24종 설정값 저작은 **별도 트랙**. 레인은 값을 지어내지 않고, `run` 이 어느 파일의 어느 리프에서 멈추는지만 이름으로 말한다 |
| ③ | W3 `orders` 축 | **주문체결조회 GET TR 추가** | 증인이 잔고(포지션·현금)와 주문 둘 다 답한다. 둘 다 GET-only이므로 P-R5 금지와 무관. 새 TR 이 런타임 허용 경로에 들어오는 것이 이 처분의 내용 |
| ④ | 커널 라운드 #4 범위 | **① OCP approval 결속 · ③ `tos.position` · ② 주식 tick 표 · ④ RCL committed 벡터 — 4건 전부** | ⑤ Phase 3 §7.11 이월은 **미선택**(ⓐ 전역 new-risk 래치는 정책 승인 선행이라 애초에 코드 라운드 밖) |
| ⑤ | PR #676 | **W3 착수 전 머지** | W3 설계가 인용하는 P-BAL 측정치(25행/2페이지 · `TRUNCATION_RISK_DEMONSTRATED`)가 main 에 있게 된다 |

**⑦ (신규 · §0.5.1 에서 나옴) 커널 라운드 #4 항목 ② 의 처리.** 이 저장소에 측정된 주식 호가단위
원천이 **0건**이므로 ② 는 형상만 추가할 수 있다. (a) 형상만 넣고 값은 `None` 으로 남겨 커널이
`UNKNOWN` 을 내게 한다(계획 §2 의 「원천 없는 수치는 null」 규율 그대로) · (b) 새 승인 경로(제안표)를
만들어 값까지 채운다 · (c) 측정 원천이 생길 때까지 ② 를 이번 라운드에서 뺀다. **추천: (a)** — 형상이
있어야 값이 «표현 가능하고 따라서 거부 가능»해지며, 지어낸 값은 0 이다.

②(실행 측정 위치)·⑥(Codex 부착)은 미질의 — ② 는 W2/W3 코드 착지 시점에, ⑥ 은 되돌리기 어려운
경로가 실제로 생길 때 범위·비용과 함께 올린다.

## 7. 착지 기록 · 정직 상태

### 7.1 정직 등재 (원천이 없어 해소하지 않고 적는 것)

- **`required_authority_scope` 는 합성값이다.** `compose/_wiring.py:562` 가 권한 스코프를
  `(f"scope-{construction.instrument}",)` 로 instrument 에서 만들어 낸다. W1 레인 A 가 실측한
  결과(계획 §0.2 가 부여한 처분 의무): 커널 전역에서 이 필드의 **내용을 검증하는 소비자가 0건**이고
  (`ioc/records.py` 와 `egressgw/construction.py` 두 곳에만 등장), 통과 조건은 「비어 있지 않음」
  하나다. 필드 독스트링은 「없거나 비면 UNKNOWN/NON_CONFORMANT」라는 규범적 기대를 적지만 그것을
  집행하는 코드는 이 트리에 없다.
  **원천화하지 않는다** — 어떤 정책 문서도 권한 스코프를 선언하지 않으므로 원천화는 값을 지어내는
  일이 된다. 커널 라운드 #4 후보 ①(OCP approval/signer 결속)이 실제 권한 스코프가 나와야 할 자리다.
  지어낸 거버넌스 값 0.

### 7.2 웨이브 착지 (2026-09-17)

**상태 정직 표기.** 운영자 지시 4항 중 **main 에 착지한 것은 2항**(① `run` 구동 · ③ 브로커
증인)이고, ② (c2) 실 시세는 **심사 통과·머지 대기**(PR #727 OPEN), ④ 커널 라운드 #4 는
착수 단계다. 기준선 main `7b76e217` **2292** → 현재 main `a8a694f5` **2374**(실측) →
W2 병합 시 **2445**(PR 브랜치 실측). 전 웨이브 **커널 diff 0**.

> fact-check 지적(2026-09-17): 이 절의 초고가 W2 를 「착지 완료」로, 2445 를 「최종」으로
> 적었다. **착지하기 전에 착지 기록을 쓴 것**이며, 이 아크가 내내 잡아온 과잉 주장과 같은
> 부류다. 정정해 남긴다.

| 웨이브 | PR → main | 무엇이 착지했나 | 리뷰 |
|---|---|---|---|
| **W1** `run` 구동 | #725 → `ae3c967c` (2333) | `construction.yaml` fail-closed 로더 · `run` 이 실제로 `compose_paper_runtime` 호출 후 `run_forever` 구동 · 틱 원천 없으면 거부 · SIGINT/SIGTERM 정지 | 1차 HIGH 1·MEDIUM 2·LOW 1 → 조치 → **재심 0/0/0/0** |
| **레인 D** 인벤토리 | #728 → `44b35658` | 배포 인스턴스 설정 30종 표(로더·호출부·필수/옵션·승인 근거 **종류**) · 저작한 값 0 | fact-check **지적 0** |
| **W3** 브로커 증인 | #726 → `3dae36a3` (2374) | 실 KIS 모의 `BrokerWitness` — 잔고(positions/cash) + 주문체결조회(orders), 둘 다 GET-only · **연속키 완주 아니면 `WitnessUnavailable`** · 선물 생성 시점 거부 | code HIGH 0·MEDIUM 2 → 조치 · **`privacy-gate` 위반 0·확인 불가 0** |
| **W2** (c2) 실 시세 | #727 **(미병합)** | KIS 모의 시세 `ObservationIntake` · 토큰 수명주기 공유 추출 · `intake_kind` 명시 선택 · 팬텀 틱 방지 | 1차 HIGH 1 → 조치 → 재심 MEDIUM 1·LOW 1 → 조치 · `privacy-gate` 위반 0 |

#### 이 아크가 실제로 바꾼 것

**`run` 이 처음으로 구동한다.** 다만 「배포 인스턴스가 부팅한다」는 아니다 — 부팅하지 않는
이유가 「로더가 없다」에서 **「승인된 값이 없다」**로 바뀌었고, 후자는 코드가 아니라 운영자
승인이 해소한다(§0.1 · 인벤토리 문서).

#### 정직 상태 (해소하지 않고 적는 것)

1. **W3 오더 축**: 위 §0.4 인용 — 실 증인이 `CORROBORATED` 를 실질화하지 못한다. 후속 처분 필요.
2. **`VTTC0081R` 다중 페이지 미실측**: 주문체결조회 자체의 continuation 은 측정된 적이 없다.
   잔고조회에서 **실측된** `tr_cont`/`CTX_AREA_FK100·NK100` 프로토콜을 일반화 적용했다.
3. **`as_of_ms` 는 수신 시각**: 이 어댑터가 폴링하는 TR 응답 본문에 소스 이벤트 시각이 없다.
   단 「KIS 에 이벤트 시각이 없다」는 뜻이 **아니다** — 실시간 WebSocket 체결 피드(`H0STCNT0`)는
   `STCK_CNTG_HOUR` 를 싣고 레거시가 그것을 `time.time()` 으로 **버린다**
   (`shared/kis/stock_feed.py:67` 파싱 → `:120` 폐기). 그 필드를 싣는 REST TR 은 이 저장소에
   없고, WebSocket 은 다른 트랜스포트라 전환은 별도 설계 결정이다.
4. **`snapshot_age_bound` 는 여전히 측정이 아니라 주입 경계값**이다. 이 아크가 해소하지 않았다.
5. **실 모의 서버 실행 0.** W2·W3 둘 다 헤르메틱 테스트만 돌았다 — 실행은 운영자 핸드오버.
6. **단일 instrument 유지**(FORWARD-OBLIGATION-MS1 미비준).
7. **`required_authority_scope` 는 합성값**(§7.1).

#### 후속 처분 (등재만, 이 아크에서 해소하지 않음)

| # | 항목 | 발견 경위 |
|---|---|---|
| F-1 | `ReconciliationService` 에 `broker_execution_id` 교차조회 추가 — 없으면 오더 축 재무장·캐파시티 해제가 구조적으로 영구 차단 | W3 레인이 빠뜨린 레인 C 를 채우다 실측 |
| F-2 | **토큰 추상 충돌**: W3 `KisWitnessTokenSession` 은 매 요청 평문 앱키/시크릿 반환을 요구하고, W2 `KisTokenLifecycle` 은 좁은 `with` 밖으로 평문을 내보내지 않는다(F5). 둘은 **합성되지 않으며 얇은 어댑터로도 안 된다** — 감쌀 대상이 없어 adapter 가 제2의 자격증명 로딩 경로가 된다. 제약: KIS 가 매 인증 호출에 시크릿 헤더를 요구하므로 **평문은 어느 선택지에서도 요청마다 실체화된다**. 질문은 「누가 소유하고 얼마나 오래, 몇 군데서 로드하는가」 | 팀리드 통합 실측 · W2 레인 독립 확인 · 재심이 (a)(b)(c) 전건 확인 |
| F-3 | 읽기 전용 경로(시세·잔고)에 **별도 KIS 앱 등록**으로 자격증명 분리 여부 — 분리하지 않으면 지금 형상이 정상 운영 형상으로 확정된다 | `privacy-gate` 확인 불가 1건 |
| F-4 | 증거 README 에 값을 적을 때 **어느 아티팩트의 어느 필드**인지 함께 적게 하기 — 출처 없는 값이 쓸 자리가 없어진다 | #676 지적이 #729 에서 재발 |

#### 교훈

- **세 웨이브 모두 리뷰가 저자가 못 본 실결함을 잡았고, 전부 뮤테이션에서 나왔다**(정적 읽기 0).
  W1: 웨이브 전체를 되돌려도 red 1건 · W2: 「자동 대체 없음」을 지우니 전건 green ·
  W1 조치물에는 **무한 행**이 잠복(저널을 비우자 30초 뒤 `SIGKILL`).
- **「지적을 고쳤는가」가 아니라 「같은 지적이 또 나올 수 있는가」.** W2 마무리에서 부류 감사를
  하니 같은 결함이 하나 더 나왔고(8건 중 2건), #729 는 부류를 안 닫아 한 PR 만에 재발했다.
- **통합 측정이 아니면 못 보는 것**: 토큰 추상 충돌(F-2)은 두 레인 각자 green·각자 리뷰 통과.
- **예시 파일을 로드하는 테스트가 없으면 「픽스처 전건 green」과 「예시가 유효」는 다른 문장**이다.

**W1 (`run` 결선) — PR #725, 브랜치 `feat/tos-run-loader`, 3+3 커밋(레인 A/B/C 착지 + 리뷰
HIGH/MEDIUM2/LOW 조치).** `tos_runtime.compose.cli` 모듈독스트링(`cli.py:78-93`)의 "Canonical
blocker list" 가 아래와 같은 `(a′)`/`(b′)`/`(c)` 레이블·해소 상태를 유지한다(드리프트 핀
`tests/compose/test_cli.py::test_run_blocker_list_labels_match_between_cli_and_plan_section_7`
가 정규식으로 두 사본을 대조) — 아래는 그 사본, 항목마다 열 0 에서 시작(핀의 정규식이 그 형태를
요구):

- (a′) **RESOLVED** — envelope/order_shape 웨이브: 둘 다 OCP/파생 원천, 호출자 주입 리터럴
  없음.
- (b′) **잔존** — 리스크 상태 서비스 자신이 이미 공시한 한계(단일 원천 포지션 관측, 계약 수
  차원만). 그 웨이브의 운영자 확인점 5, 이번 웨이브 범위 밖.
- (c) **RESOLVED** — 틱 원천 웨이브: `TickScheduler` 가 실 `DECISION_TICK` 를 `EngineDriver`
  로 흘린다.

그 밖의 W1 착지 사실(레이블 목록이 아닌 것):

- **로더 갭 RESOLVED**(이번 웨이브, 레인 A): `construction.yaml` 이 fail-closed 로 로드된다
  (`compose/_construction_config.py`) — `run` 이 `return 0` 대신 실제로
  `compose_paper_runtime` 을 호출한다.
- `required_authority_scope` 합성값 처분은 위 §7.1 을 본다(레인 A 가 실측·등재,
  `_wiring.py:562` 의 주석이 이 절을 역참조).
- **레인 C — `run_forever` 첫 컴포즈 상대 e2e** + `cli.main(["run", ...])` argv 경로
  e2e(리뷰 HIGH 조치, 실 SIGINT 로 유일하게 지원되는 정지 수단을 구동해 실 durable 파일에서
  틱 발생을 확인).
- **게이트**: firewall PASS · lint-imports 3 kept/0 broken · size-budget PASS(신규 예외 0 —
  `_wiring.py` 재등재 1122→1132, `cli.py` 는 분리로 858줄까지 내려감) · ruff/black/mypy 클린 ·
  커널 diff 0.
- **런타임 스위트**: 기준선(main `7b76e217`) 2292 passed → 이 웨이브 착지 후 **2333
  passed**(브랜치 실측, exit 0).
- **뮤테이션**: 로더가 누락 리프를 조용히 기본값 처리 → 19개 red · `run` 이
  `composed.marketfeed is None` 에서도 0 반환 → 2개 red(단위+e2e 양쪽) · `main()` 의
  `_dispatch_run` 호출을 `return 0` 으로 되돌림(전체 웨이브 되돌리기) → red 1(최초
  리뷰)→2(HIGH 조치 후, 신규 argv e2e 포함) · 정지 술어 핸들러를 no-op 로 바꿈 → 1개 red.
- **비범위 확인**: 24 종 미승인 설정값 중 어느 것도 이 웨이브가 채우지 않았다(§0.1 의 19
  부팅차단/5 옵트인 구분 — 값 저작은 운영자 소관, 계획 §2 비범위).
