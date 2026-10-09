# config/tos_runtime/cp3-setup-d-long/

CP-3 **첫 tenant** 설정 트리 — Setup D VWAP 되돌림, **LONG 배포**.

> 이 디렉터리는 **값**이다. 아무것도 부팅하지 않았고, 아래 「무엇이 증명되지 않았나」가
> 그 목록이다. 부모 `config/tos_runtime/README.md` 의 규칙(인용 없는 값은 여기 있을 자격이
> 없다)이 그대로 적용된다.

## 1. 무엇이고 무엇이 아닌가

- **무엇**: kickoff `docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md` §4 결정 3·4
  (「tenant 전용 설정 트리 + data dir, **방향마다 따로**」 · 「LONG 배포 + SHORT 배포 각각
  렌더」)가 요구한 **LONG 쪽 트리**다. 운영자 승인 2026-10-07(아홉 전부 권고대로).
- **아니다**: 상주 paper 배포가 아니다. 상주 트리 `config/tos_runtime/paper/` 와 그
  data dir(`~/.local/state/tos/paper-data/<월물>`)은 이 PR 이 **건드리지 않았다**
  (결정 3 「상주 잎·상주 설정 불변」 — 상주 콘텐츠를 바꾸면 전략 키 변화로 부팅 리플레이가
  held 가 된다, 런북 `docs/runbooks/tos-paper-boot.md` §7.10 6).
- **SHORT 는 여기 없다 — 자기 트리에 있다: `config/tos_runtime/cp3-setup-d-short/`**
  (착지 2026-10-09). DSL 에 `abs()` 가 없어 진입 비교가 한 변뿐이므로 SHORT 는
  `z_x1000 >= +1800` 을 쓰는 **자기 파일·자기 트리**를 갖는다(결정 4; kickoff §5 3 마지막 줄).
  두 트리의 차이 목록과 **SHORT parity 공백**은 그 트리의 `README.md` §3 에 있다.

## 2. 환경 라벨은 `paper` 다 — tenant 식별자가 아니다

`critical_input_policy.yaml::environment` 와 `venue_constraint_policy.yaml::scope.environments`
· `order_construction_policy.yaml` 의 라벨은 모두 **`paper`** 다. 이유는 kickoff §5 1 이
적는다: 로더는 그 토큰을 `--environment-label` 과 **대조하지 않으므로** 어긋나도 조용히
부팅하고 증거만 틀린 라벨을 단다. compose 는 정책들끼리는 대조하므로(`_cross_check_scope`
→ `VenuePolicyScopeMismatch`) 셋이 같아야 한다.

그러므로 **같은 라벨 아래 두 배포**(상주 세션과 이 tenant)가 존재한다. 둘을 가르는 것은
라벨이 아니라 **설정 트리와 data dir** 이다(결정 3).

## 3. 상주 트리와 무엇이 다른가 (실측 2026-10-09)

**이 트리는 31 파일이다: 바이트 동일 23 + 다름 5 + tenant 전용 3.** 더해서 상주 트리의
`strategies/bootproof_band.strategy.yaml` **하나가 이 트리에 없다**(상주 29 파일 기준).
측정 방법은 작업트리 `cmp` 가 아니라 **git blob OID 대조**(`git ls-tree -r
origin/main:config/tos_runtime/paper` vs 이 트리 파일들의 `git hash-object`)다 — 양쪽 모두
**커밋된 내용**에 대한 진술이어야 하기 때문이다.

| 파일 | 상태 |
| --- | --- |
| `venue_constraint_policy.yaml` | **다름** — `max_quantity` null → **10000**(결정 9 (a), 아래 §4) · `tick_size` 5 → **2**(mini 규정값 정정 2026-10-09, 아래 §4) + `policy_id` 가 tenant 전용(§7 2). 런타임이 읽는 **값** 차이는 그 **두 곳**이다 |
| `critical_input_policy.yaml` | **다름** — 사본이 아니다. 상주 쪽은 부팅 증명 픽스처의 **세 필드**, 이쪽은 tenant 상류 **열다섯 필드**(아래 §5) + `policy_id` tenant 전용 |
| `construction.yaml` | **다름** — `price_field_key`·`shape_price_field_key` 가 `"close"` → **`"close_x100"`**. 상주의 `"close"` 는 이 트리의 critical_input 에 **없는 키**이고, 두 로더는 서로를 볼 수 없어 그 불일치를 **거부하지 못한다**(그 파일의 해당 주석이 실측 경로를 적는다). 나머지 값은 상주 승인값 그대로 |
| `engine.yaml` | **주석만 다름** — 값은 상주 승인값 그대로다. 기존 주석이 상주 전략(`bootproof_band`)을 인용해 이 트리에서 거짓이 되므로 tenant 적용 한 문단을 덧붙였다(스텝 수 24 ≤ 64 재측정) |
| `order_construction_policy.yaml` | **digest 동일 · template DATA 산문이 다름** — 2026-10-09 tick 정정이 `unit_multiplier_currency_and_numeric_rules` 줄을 고쳤고 그것은 **주석이 아니라 DATA**(DR-0002 §2.1 — 보존되지만 런타임이 해석하지 않는다)다. 그래서 「주석만 다름」은 **더 이상 참이 아니다**(초판에는 참이었고 이 PR 의 첫 커밋이 깨뜨렸다). `canonical_digest` 는 **그대로**다(`c90444b9…` — 상주·LONG·SHORT 셋 다 같다; 그 digest 는 DATA 산문도 `policy_id` 도 추적하지 않는다). 주석 쪽도 `quantity_basis` 선언 자리에 tenant 적용 문단을 덧붙였다 |
| `strategies/setup_d_long.strategy.yaml` | **tenant 전용** — 상주의 `strategies/bootproof_band.strategy.yaml` 을 **대체**한다(그 파일은 이 트리에 없다) |
| `strategy_bindings.yaml` | **tenant 전용** — `z_entry_max_x1000: -1800`. `strategies/` 의 **형제**다(안에 두면 로더의 stray-file 규칙이 디렉터리 전체를 거부한다) |
| `README.md` (이 파일) | **tenant 전용** |
| 나머지 **23 개** | **바이트 동일** — 상주 트리에서 그대로 복사된 승인값이다. 아래 ⚠ 를 볼 것 |

> ⚠ **바이트 동일한 23 개 안의 `config/tos_runtime/paper/...` 인용을 「이 트리의 형제
> 파일」로 읽을 것.** 그 파일들은 서로를 **절대 경로 꼴**로 인용한다(예 `time.yaml` 의
> 「강제 일치: config/tos_runtime/paper/calendar.yaml 의 `calendar_version`」 ·
> `marketfeed.yaml`·`safety_profile.yaml`·`safety_activation.yaml` ·
> `calendar.yaml`·`broker_scopes.yaml`). 런타임의 그 대조는 **하나의 `--config-dir` 안에서**
> 일어나므로 실제로 가리키는 것은 **이 트리의 같은 이름 파일**이다. 경로를 일괄 치환하지
> 않은 이유는 그렇게 하면 「상주 승인값의 사본」이라는 **기계로 확인 가능한 성질**
> (blob OID 로 23/23 동일)을 잃기 때문이다. 치환 규칙은 이 줄이 유일한 기록이다 — 값을
> 바꿀 때는 그 파일이 더 이상 사본이 아니므로 §3 표의 행을 옮긴다(`construction.yaml` 이
> 2026-10-09 리뷰에서 실제로 그렇게 옮겨졌다).

### ⛔ 사본 의무 — 상주 쪽을 바꾸는 PR 은 **같은 PR 에서** tenant 사본도 갱신한다

위 23 개는 **상주 파일의 바이트 사본**이다. 그러므로 `config/tos_runtime/paper/` 의 그 파일
중 하나를 바꾸는 PR 은 **같은 PR 에서** 두 tenant 트리(`cp3-setup-d-long` ·
`cp3-setup-d-short`)의 사본을 함께 갱신해야 한다. 안 하면 사본이 조용히 낡는다.

⚠ **그 중 `release.yaml` 은 조용히 낡는 것으로 끝나지 않는다** — 그 파일이
`expected_code_digest` 를 싣는다. 런타임 코드를 바꾸는 PR(예 band 원천 웨이브 PR-2)은 그
핀을 **상주 트리에서만** 재도출한다. 상주 세션은 매일 재도출해 대조하므로 거기서는 드러나지만
(런북 §5 ①), tenant 트리는 **부팅한 적이 없어** 낡은 핀이 드러날 레인이 없다 — 첫 tenant
부팅이 digest 불일치로 **ABORT** 한다.

`tos/runtime/tests/compose/test_tenant_tree_copies.py` 가 이 의무를 고정한다: 사본 23 개의
**바이트 동일성** · 선언된 차이가 **실제로 다른가** · 분류의 **전수성**(파일을 더하고 분류를
빼먹으면 red) · 분류됐지만 **어느 검사도 안 하는 이름이 없는가** · 그리고 `release.yaml` 은
실패 메시지가 「두 트리에서 같은 PR 에 재도출하라」고 말하도록 **따로** 단언한다.

## 4. `max_quantity: 10000` — 결정 9 (a)

운영자 채택 **2026-10-08**. 출처는 KRX 파생상품시장 업무규정 시행세칙 **별표 17의2 제1호
미니코스피200선물거래 행**(정규거래 10,000 계약), 등급 **R**(공표 규정 원문). 조문 체인과
증거·재현 레시피는 설계
`docs/plans/2026-10-08-tos-cp3-venue-limit-source-and-probe-design.md` §2·§3 과
`docs/broker-profiles/evidence/2026-10-08-krx-venue-limits/` 에 있다.

값과 **반드시 같이 읽을 단서 셋**(설계 §2.2)과 「필요조건이지 충분조건이 아니다」는
`venue_constraint_policy.yaml` 헤더에 그대로 적혀 있다 — 여기서 요약하지 않는다.

- **상주 paper 트리는 이 값을 채택하지 않았다** — 운영자가 paper 채택을 보류했다(결정
  2026-10-08). 상주 트리의 `max_quantity` 는 `null` 그대로다.
- **`tick_size` 는 2 다 (정정 착지 2026-10-09).** 운영자 승인 2026-10-08 · 시행세칙
  **제4조의9 제2호** · 등급 **R** · 브로커 정황 = P-VL band 격자(PR #881). band 원천 웨이브
  계획 `docs/plans/2026-10-08-tos-cp3-band-source-wave-plan.md` §3 의 첫 PR 이다.
  **거동 변화는 0 이다** — band 가 null 인 동안 tick 검사는 step 3 UNKNOWN 에 가려진다.
  지금 고치는 이유는 band 가 들어오는 순간 종전 5(full 계약 값)가 mini 정상 호가를 전부
  INADMISSIBLE 로 만들기 때문이다. 조문·보강 정황 셋은 그 파일 헤더에 있다.
  **상주 `paper` 트리의 tick 은 5 그대로다** — 계획 §3 이 paper 채택과 함께 보류한다.
  ⚠ 이 변경은 tenant VCP 의 `canonical_digest` 를 바꾼다(실측: VCP digest 는
  `_model_view.shape_constraints` 를 덮는다). 이 트리의 `safety_activation.yaml::members`
  는 `null` 이라 갱신할 활성화 기록이 없다.
- **`price_min`/`price_max` 는 null 그대로다** — 일별 동적 값이라 정적 리터럴 금지(설계 §6).

## 5. `critical_input_policy.yaml` — 열다섯 필드 (`max_age_ms` = 800, 등급 A(운영자 결정 2026-10-09))

필드 목록·순서는 B1a 의 `FIELD_ORDER`(`tools/tos_cp3/produce_fields.py`) 그대로이고,
각 필드의 `unit`/`scale`/`multiplier`/`sign` 은 **B1a 의 필드 lineage** 에서 온다
(`produce_fields._field_lineage` — 그 독스트링이 「이 파일이 쓰는 모양으로 적는다」고 말한다).

**`max_age_ms` 는 열다섯 전부 `800` 이다 — 운영자 결정 2026-10-09**(「max_age_ms : 800ms 로
정해」). 그 수는 커널의 시간 수용 예산과 **같은 수**다:
`time.yaml::MAX_time_conservative_freshness_age_ms` **1000** − `Σdelay_bounds`(네 항 × 50 =
**200**) = **800 ms**. 종전 판은 전부 `null` 이어서 로더가 거부했고(`marketfeed/policy.py`),
그 fail-closed 상태는 2026-10-09 에 닫혔다.

**등급은 A(운영자 결정 2026-10-09)** 다(`docs/plans/2026-09-12-tos-operator-value-proposals.md:4`
의 등급 어휘 — A = 「규범 문서에 이미 승인된 값(VER-002 `APPROVED`)」). 800 을 만드는 **두 항이
모두 VER-002 승인치**이기 때문이다(좌표는
`tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml`):

- 피감수 **1000** = `MAX_time_conservative_freshness_age_ms` **:1078** · APPROVED 2026-09-04
  (그 항목 자신이 「> Σ delay-class bounds 200 ms, conservative direction LOWER」를 적는다).
- 감수 **200** = 런타임이 `delay_bounds` 로 더하는 네 항 × 50 —
  `MAX_time_transport_and_queue_uncertainty_ms` **:1069** ·
  `MAX_clock_domain_conversion_uncertainty_ms` **:1070** ·
  `MAX_time_source_precision_ms` **:1076** · `MAX_time_source_sequence_gap_ms` **:1077**,
  전부 APPROVED 2026-07-29. ⚠ 값이 같아 조용히 통과하는 이웃 둘을 섞지 말 것 —
  `MAX_time_source_disagreement_ms`(:1071)는 똑같이 50 이지만 지연 한도가 **아니고**,
  `MAX_critical_input_consumer_receipt_age_ms`(:1067)는 똑같이 1000 이지만 **다른 경계**다.

괄호 안 「운영자 결정 2026-10-09」은 같은 표의 `trading_calendar_version`(:22)이 쓰는
**A(§11 결정 11)** 과 같은 꼴이다 — 값은 규범 승인치이고, 운영자 결정은 **이 키를 그 승인치에
결속한다**는 판단이다. ⛔ **M 이 아니다**(이 PR 초판의 오기, 리뷰 M2 에서 정정): M 은
「운영자·서버에서만 산출 가능」이고 그 표의 M 행은 전부 호스트·운영자만 아는 사실인데
(`tz_db_version` :21 · `verification_profile_version` :23 · `finality.source_revision` :78 ·
`ACNT_PRDT_CD` :93), 800 은 저장소 안에서 도출되고 테스트가 `time.yaml` 에서 다시 계산한다.

⚠⚠ **구속 결과 — ③ 은 저널 append 시각을 `as_of_ms` 로 찍어야 한다.** `max_age_ms` 와 커널
시간 경로는 **같은 양**을 잰다(`snapshot.py::_derive_field_state` 의 `now_ms - as_of_ms` ·
`time_projection.py` 의 `source_age = wall_clock_now() - as_of`). B1a 는 `as_of_ms` 를 봉의
**라벨 = OPEN** 으로 찍으므로(`derive_as_of_ms`: 「The label, not label+60s」, 봉은 1분 —
`derive_raw_event_id` 의 `:1m:`) 관측의 **최소** 나이가 60,000 ms 다. 60,000 > 800 이므로
**현행 B1a 의미론에서는 열다섯 전부 STALE** 이고, `_derive_field_state` 가 필드마다
`(UNKNOWN, "stale")` 를 돌려주며 커널의 ∅/UNKNOWN 바닥이 그 키들을 떨어뜨린다 → R1 거짓 →
NO_ACTION, 송신 0(fail-closed). **한도를 올려서 고칠 수 있는 문제가 아니다** — 올리면 커널
시간 경로가 같은 관측을 같은 양으로 재서 거부한다. 그러므로 이것은 ③ 에 대한 **요구사항**
이다: ③ 실시간 생산자는 상주 저널 수집기처럼 **저널에 append 하는 시각**을 찍어야 한다
(`marketfeed/scheduler.py::_finalize_pending` 의 「an honest source event time」). ③ 착지
시 이 셋이 한 예산을 나눠 쓴다 — 이 키 ×15 · `poll_interval_ms` · `journal_pass_allowance_ms`.

**180000 은 폐기됐다(연혁).** 2026-10-09 초판은 「출처가 없어도 설정이 필요하니 적용」 지시에
**봉 주기에서** 3P = 180,000 을 도출해 적었다(등급 C: 2P = 120,000 은 하한, 세 번째 P 가
발행·폴 지연 여유). 그 판은 파일이 로드되게 할 뿐 시간 경로를 열지 못했고(같은 헤더가
「800 ms 예산의 75 배」로 적었다), 운영자 결정이 그 간극을 **예산 쪽으로** 닫았다.
**그리고 그 옛 헤더는 800 을 이미 지목하고 있었다** — main `bb9a4d4d` 의 그 파일 :72-74 축자:
「…올바른 한도는 180,000 이 아니라 위 800 ms 예산 자리수다」(조건 = ③ 이 append 시각을 찍을
것). 즉 운영자 결정은 개발 측이 **조건부로 이미 지목한 자리수**를 택하면서 그 조건을
**요구사항으로 승격**한 것이다. ⚠ 이 PR 초판은 그 문장을 「현행 ③ 의미론에서는 성립하지 않는
자리수」로 **오인용**해 「개발 측은 800 을 부정했다」는 근거로 썼다(리뷰 M1) — 그런 문장은
`bb9a4d4d` 에 없다. 삭제했다.

보수 방향은 **작게**(작으면 UNKNOWN → NO_ACTION, 크면 낡은 필드가 VALID = fail-OPEN)이고,
800 은 커널 예산을 넘지 않는 **가장 큰** 값이라 이 방향으로 더 키울 수 없다.

상주의 600000 은 **베껴 오지 않았다** — 그 근거(「렌더가 저널을 부팅 직전에 생성하므로 그
여유는 실제로 그 부팅 지연만 덮는다」)는 배치 저널 부팅에만 성립한다.

## 6. 무엇이 증명되지 않았나 (이 PR 이 하지 않은 것)

1. **부팅 0 회.** 이 트리로 `run` 을 돌리지 않았다. 검증된 것은 ① `venue_constraint_policy.yaml`
   이 좌표 미채움 상태에서 **거부되고**(운영자-채움 게이트) 좌표를 채우면 `max_quantity: 10000`
   으로 적재되고 `tick_size: 2` 를 든다는 것, ② `critical_input_policy.yaml` 이 이제
   **적재된다**는 것(`max_age_ms` ×15 = 800, §5) **과** 그 중 하나라도 `null` 이면 로더가
   여전히 **그 키 이름으로 거부한다**는 것, ③ `construction.yaml` 의 두 price 키가 이 트리의
   critical_input 필드 집합 **안에 있다**는 것
   뿐이다(`tos/runtime/tests/compose/test_deploy_policies.py`). ③ 은 두 로더가 서로를 보지
   못하는 자리를 테스트가 대신 보는 것이고, **부팅이 그 교차를 검증한다는 뜻은 아니다.**
   ⚠ ② 의 「적재된다」를 「부팅하면 돈다」로 읽지 말 것 — 800 은 커널의 보수 예산 **그 자체**
   이고, 라벨 스탬프 1분봉은 최소 나이가 60,000 ms 라 **열다섯 전부** `(UNKNOWN, "stale")`
   로 읽힌다(§5 의 ⚠⚠). 그것을 닫는 것은 아래 3(③ 생산자)이고, 이제 ③ 에는 **저널 append
   시각 스탬프**라는 구속 요구가 붙는다.
2. **렌더가 이 트리를 아직 처리하지 못한다** — kickoff §5 3 ④. `scripts/tos/render_paper_config.py`
   는 (a) `_STRATEGY_FILE` 이 `strategies/bootproof_band.strategy.yaml` 로 고정이고
   (b) 좌표 규칙이 앵커 **정확히 1회** 매칭을 요구하는데 이 트리의 전략 파일은 규칙이 셋이라
   `account: "TBD"`·`instrument: "TBD"` 가 각 3회 나오며 `direction` 은 줄마다 값이 다르다
   (R1 LONG 진입 / R2·R3 는 롱을 닫는 SHORT). 즉 ④ 는 「상수 한 줄 교체」가 아니다.
   그 뒤에 digest 다섯 재도출 + `safety_activation.yaml::members` 갱신이 따라온다(런북 §5).
3. **실시간 필드 생산자가 없다** — kickoff §5 3 ③. B1a 는 Parquet 배치 도구이고 발행기가
   아니다. 복사된 `marketfeed.yaml` 은 상주와 같은 **저널 기반** 좌표를 들고 있다.
   ⛔ **2026-10-09 운영자 결정이 ③ 에 구속 요구를 붙였다**: `max_age_ms` = 800 은 커널 시간
   예산 그 자체이므로 ③ 은 `as_of_ms` 를 **저널에 append 하는 시각**으로 찍어야 한다
   (`marketfeed/scheduler.py::_finalize_pending` 의 「an honest source event time」 모양).
   라벨 스탬프 생산자는 이 트리를 결코 결정까지 끌고 가지 못한다(§5).
4. **체결·영수증 증거 없음** — band 가 null 인 동안 step 3 는 UNKNOWN 이다(설계 §3).
   실주문은 어느 경우에도 0 이다(채택 스코프 `SYNTHETIC_FUTURES_ORDER`, `broker_scopes.yaml`).

## 7. 운영자 미결 항목

1. **`max_age_ms` 가 실제로 만족 가능한가** — 값·등급은 미결이 **아니다**(800 · 등급
   **A(운영자 결정 2026-10-09)** · §5: 두 항 다 VER-002 APPROVED). 남은 것은 ③ 실시간
   생산자가 생긴 뒤 그 **발행 지연을 측정**해 이 한도를 실제로 지킬 수 있는지 확인하는 것이다.
   ⛔ 그 측정이 나빠도 **한도를 올리는 처분은 없다** — 커널 시간 경로가 같은 양을 같은 예산에
   대므로 처분은 ③ 쪽(append 시각 스탬프 · 지연 단축)이다.
2. **data dir 의 genesis 와 콜드 백업 편입** — 이름은 **지정됐다**(아래 §8). 남은 것은
   ① 첫 부팅(④)이 만드는 genesis 와 ② 콜드 백업 `COLD_DATA_DIR` 지정(운영자 결정).
3. ✅ **SHORT parity 실행 — 2026-10-09 에 돌았다.** 이 항목은 「그 방향에는 parity 증거가
   0」이었다. 이제 아니다: B1b 를 SHORT 렌더로 다시 돌려 B3 를 냈고 **규칙 수준 176/176 =
   100 % · 포지션 모델 56/56 = 100 % · UNRESOLVED 0** 이다(kickoff §5 2 의 SHORT 문단,
   그 트리 `README.md` §3.3). 공표된 **374/374 는 여전히 LONG 쪽 수치**이고 176/176 이
   SHORT 쪽 수치다 — 두 실행은 같은 B1a·B2 아티팩트를 쓰므로 **같은 봉에 대한 두 절반**이다.
   같은 PR 에서 LONG 쪽 B3 를 새 도구로 다시 돌려 2026-10-08 산출물 `ce36450f…` 가
   **바이트 그대로** 재현되는 것도 확인했다.
   ⚠ 남은 것은 결정 5 가 삭제한 `short_blocked_regimes` 인데, **이 비교는 그것을 볼 수 없다**.
   근거는 **B2 가 자기 차이 `B2-L1` 로 선언해 둔 것**이다 — 그 가드는
   `shared/strategy/entry/setup_d_adapter.py:174` 에서 `check()` 가 반환하는 `:166` **뒤**에
   걸리는데 B2 는 `tools/tos_cp3/emit_legacy_decisions.py:946`·`:990` 에서 `check()` 를
   **직접** 몰므로 레거시 쪽도 적용한 적이 없다.
   ⛔ **`B1b-D8` 의 흡수 봉 0 을 그 근거로 쓰지 말 것** — 어떤 귀속 규칙도 B1b-D8 을(B1b-D9 도)
   인용하지 않으므로 그 0 은 **구조적**이고 가드가 실제로 물었어도 0 이다. 이 창에 숨은 regime
   차이가 없다는 것을 받치는 것은 **UNRESOLVED 0** 이다. 자세한 처분은 그 트리
   `README.md` §3.3 2 다 — 두 트리를 함께 읽어야 하므로 여기에도 적는다.

## 8. data dir · 렌더된 설정 — 지정 2026-10-09 (결정 3)

| 무엇 | 어디 | 비고 |
| --- | --- | --- |
| durable set **부모** | `~/.local/state/tos/cp3-setup-d-long-data` | **0700** · 저장소 밖 · **아직 없다** |
| durable set **잎** | `cp3-setup-d-long-data/<종목>` | 계약월마다 하나 · **0700**(디렉터리) · **0600**(스토어 넷) · **그 잎의 첫 세션 genesis 가 만든다** |
| 렌더된 설정 | `~/.config/tos/cp3-setup-d-long-config` | **0700** · 부팅 직전 재렌더(저널 신선도) · **아직 없다** |

이름 규칙은 **「설정 트리 이름 + `-data` / `-config`」**다 — 이 트리 이름이
`cp3-setup-d-long` 이므로 그대로 따라간다. 경로만 보고 어느 코퍼스가 어느 트리로
부팅됐는지 알 수 있어야 하기 때문이다(런북 §5 ⑤: **활성화 기록은 방향을 결속하지
않으므로** 경로가 그 역할을 한다).

- ⛔ **상주 잎(`~/.local/state/tos/paper-data/<종목>`)에 절대 섞지 않는다**(런북 §7.10 3).
  **SHORT 와도 섞지 않는다** — SHORT 는 `cp3-setup-d-short-data` 로 **부모부터** 다르다.
- ⚠ **디렉터리를 만들지 않았다.** genesis 는 첫 부팅이고 그것은 ④ 다(§6 2).
- ⚠ **콜드 백업에 아직 들어 있지 않다** — 래퍼는 `COLD_DATA_DIR`(기본 `paper-data`)의
  직접 자식 중 `A0####` 만 잎으로 세고 `~/.local/state/tos/*` 를 글로브하지 않으므로
  이 부모는 보이지 않는다. 켜는 것은 **운영자 결정**이다.
- ⛔ **켤 때 `COLD_DATA_DIR` 만 지정하면 안 된다**(2026-10-09 리뷰 H1). 그 변수만 바꾼
  실행은 `COLD_CONFIG_DIR` 기본값 `~/.local/state/tos/paper-ops` 를 쓰고, 래퍼는
  `COLD_ROOT` 를 그 기준 설정 세 경로의 **공유 부모**(= `paper-cold`)로 유도하므로 잎별
  설정·보관소가 **상주** `paper-ops/leaves/<잎>` · `paper-cold/<잎>` 에 들어간다. 잎 이름은
  계약월이라 상주·LONG·SHORT 가 **같은 잎 이름**을 갖고, 그 두 경로는 **잎 이름만**으로 키를
  잡는다(`:443-444`). 결과는 **동시성에 따라 갈린다** — 기본 락이 공유라 직렬이면 거부가
  아니라 **섞인다**(세대는 `backup_root` 단위 `:49-51`, 잎별 파생 설정은 매 실행 재생성
  `:54`), 락을 우회해 동시가 되면 `:49-55` 대로 **둘째가 산출물 충돌로 거부된다**.
  (래퍼 헤더의 `COLD_LOCK` 항목 `:86-92` 는 같은 말을 **락 우회**라는 다른 계기로 하는 유사
  진술이고 기본 설정 tenant 실행에 대한 진술이 아니다 — 2026-10-09 재검토.)
  그래서 셋을 함께 지정한다 —
  `COLD_DATA_DIR` · **`COLD_CONFIG_DIR=~/.local/state/tos/cp3-setup-d-long-ops`** ·
  **`COLD_TARGET_BORN_ON=<이 잎의 첫 부팅일>`**(기본 `2026-10-06` 을 두면 genesis 전 부재가
  조용한 rc 0 이 아니라 **rc 1 refused** 다). 그리고 그 ops 의 `evidence_cold_backup.yaml`
  세 경로는 **`~/.local/state/tos/cp3-setup-d-long-cold/`** 아래여야 한다. ⚠ 그 ops·cold
  디렉터리도 **아직 없다**.
- 전체 표(ops·cold 열 포함)·충돌 실측·상주 래퍼가 이 tenant 를 띄우지 못하는 이유는 런북
  **§7.2-b** 에 있다.

### 닫힌 항목 (여기 있었다가 처분된 것)

- **`critical_input_policy.yaml::fields[].max_age_ms` ×15 — ✅ 적용 2026-10-09
  (등급 A(운영자 결정 2026-10-09)).**
  초판은 「출처 없음 → 열다섯 전부 `null` → 파일이 로드되지 않는다」를 미결로 기록했다.
  같은 날 1차로 **180000**(= 3 × 1분봉 · 등급 C · 「출처가 없어도 설정이 필요하니 적용」)이
  들어갔고, **운영자 결정 2026-10-09**(「max_age_ms : 800ms 로 정해」)가 그것을 **폐기하고**
  **800**(= 커널 시간 예산 1000 − Σ지연 200)으로 닫았다. 등급·구속 결과(③ 의 append 시각
  스탬프)·보수 방향은 §5 와 그 파일 헤더에 있다. 남은 것은 위 1 의 ③ 측정뿐이다.

- **정책 식별자 충돌 — ✅ 해소됨 2026-10-09 (rename).** 초판은 「tenant
  `venue_constraint_policy.yaml` 의 `policy_id`/`policy_generation` 이 상주와 같은 값인데
  내용이 달라 `(kind, member_id, generation)` 으로 구별되지 않는다」를 **미결로 기록**하고
  부팅 경로(④)로 넘겼다. 리뷰(2026-10-09)의 지적대로 **지금 바꾸는 것이 공짜다** — 이 트리는
  부팅한 적이 없고 활성화 기록도 증거도 없으므로 rename 이 무효화할 것이 없다. 그래서
  `vcp-paper-cp3-setup-d-long-krx-index-futures` 로 바꿨고 **세대는 1 그대로**다(다른 배포의
  정책이지 상주 정책의 다음 세대가 아니다). 기준은 **내용이 갈렸는가**이지 트리가 다른가가
  아니므로, digest 가 같은 `order_construction_policy.yaml`(주석 + template DATA 산문만
  다르고 `canonical_digest` 는 `c90444b9…` 그대로다 — §3 표) ·
  `aggregate_risk_policy.yaml` · `action_flow_policy.yaml` 의 id 는 **바꾸지 않았다**.
  `safety_activation.yaml::members` 는 여전히 `null` 이라 갱신할 활성화 기록이 없고
  digest 리터럴도 지어내지 않았다 — 활성화는 ④ 의 일로 남는다.
