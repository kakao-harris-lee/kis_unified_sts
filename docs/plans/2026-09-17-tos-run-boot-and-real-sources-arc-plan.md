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

②(실행 측정 위치)·⑥(Codex 부착)은 미질의 — ② 는 W2/W3 코드 착지 시점에, ⑥ 은 되돌리기 어려운
경로가 실제로 생길 때 범위·비용과 함께 올린다.

## 7. 착지 기록

(비어 있음 — 웨이브가 착지할 때마다 여기 적는다.)
