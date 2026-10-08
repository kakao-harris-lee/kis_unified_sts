# config/tos_runtime/cp3-setup-d-short/

CP-3 tenant 설정 트리 — Setup D VWAP 되돌림, **SHORT 배포**. 착지 2026-10-09.

> 이 디렉터리는 **값**이다. 아무것도 부팅하지 않았고, 아래 §5 「무엇이 증명되지 않았나」가
> 그 목록이다. 부모 `config/tos_runtime/README.md` 의 규칙(인용 없는 값은 여기 있을 자격이
> 없다)이 그대로 적용된다.

## 1. 무엇이고 무엇이 아닌가

- **무엇**: kickoff `docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md` §4 **결정 4**
  (「LONG 배포 + SHORT 배포 **각각 렌더**(설정 트리·data dir 분리)」)가 요구한 **SHORT 쪽
  트리**다. 결정 3 의 「tenant 전용 설정 트리 + data dir, **방향마다 따로**」와 짝이다.
  운영자 승인 2026-10-07(아홉 전부 권고대로).
- **LONG 트리의 거울이다**: `config/tos_runtime/cp3-setup-d-long/` 의 사본 + **선언된 방향
  차이**(아래 §3). 그 외의 값은 전부 LONG 트리와 같고, LONG 트리는 다시 상주
  `config/tos_runtime/paper/` 의 바이트 사본 + 선언된 차이다.
- **아니다**: 상주 paper 배포가 아니다. 상주 트리와 그 data dir
  (`~/.local/state/tos/paper-data/<월물>`)을 이 트리는 **건드리지 않는다**.
- **아니다**: 상주 런북 §0 의 「양방향 부팅 증명」이 아니다. 그쪽은 같은 픽스처를
  `--direction SHORT` 로 **렌더**해 한 세션 띄우는 것이고(분기 1회, 런북 §7.10 3), 이쪽은
  **자기 설정 트리와 자기 코퍼스를 갖는 별도 배포**다.

## 2. 환경 라벨은 `paper` 다 — tenant 식별자가 아니다

`critical_input_policy.yaml::environment` · `venue_constraint_policy.yaml::scope.environments` ·
`order_construction_policy.yaml` 의 라벨은 모두 **`paper`** 다. 이유는 kickoff §5 1 이
적는다: 로더는 그 토큰을 `--environment-label` 과 **대조하지 않으므로** 어긋나도 조용히
부팅하고 증거만 틀린 라벨을 단다. compose 는 정책들끼리는 대조하므로
(`_cross_check_scope` → `VenuePolicyScopeMismatch`) 셋이 같아야 한다.

그러므로 **같은 라벨 아래 세 배포**(상주 세션 · LONG tenant · 이 SHORT tenant)가 존재한다.
셋을 가르는 것은 라벨이 아니라 **설정 트리와 data dir** 이다(결정 3 · §4).

## 3. LONG 트리와 무엇이 다른가 (실측 2026-10-09)

**31 파일 = 바이트 동일 23 + YAML 이 다름 6 + 산문이 다름 1(`README.md`) + SHORT 전용 1**
(LONG 트리도 31 파일이다; LONG 의 `strategies/setup_d_long.strategy.yaml` 은 이 트리에
**없고** 그 자리를 `strategies/setup_d_short.strategy.yaml` 이 차지한다).

측정은 작업트리 `cmp` 가 아니라 `tos/runtime/tests/compose/test_tenant_tree_short.py` 다 —
바이트 동일 23 은 **바이트**로, 다름 6 은 **파싱된 YAML 경로 집합의 등식**으로, `README.md`
는 **자기 트리를 설명하는가**로 각각 검사한다. 그 테스트가 아래 표를 **기계로 읽는 리터럴**로
들고 있다: 파일을 더하고 분류를 빼먹으면 red 이고, 한 이름이 두 분류에 들어가거나 **어느
단언도 훑지 않는 분류에 들어가도** red 다(초판이 `README.md` 를 「한 트리에만 있음」으로
분류해 **아무 검사도 받지 않던** 결함 — 2026-10-09 자기 점검에서 발견).

| 파일 | 무엇이 다른가 |
| --- | --- |
| `construction.yaml` | `action_class` **NEW_LONG → NEW_SHORT** · `outbound_side` **BUY → SELL** (+ 그 두 줄의 주석) |
| `order_construction_policy.yaml` | `_runtime.construction.axes` 의 **DIRECTION 축 LONG → SHORT** · `policy_id` SHORT 전용 (+ 주석) |
| `marketfeed.yaml` | `direction` **LONG → SHORT** (+ 주석). ⚠ LONG 트리에서 이 파일은 상주와 **바이트 동일**이었는데 이 트리에서는 갈라진다 |
| `strategies/setup_d_short.strategy.yaml` | **SHORT 전용 파일.** R1 진입 `direction: SHORT`/`OPEN` + 비교 **GE** · R2·R3 `direction: LONG`/`CLOSE`(숏을 **매수로** 닫는다) · rationale 토큰 전부 |
| `strategy_bindings.yaml` | 키 `setup_d_short.strategy` · 바인딩 **`z_entry_min_x1000: 1800`**(LONG 은 `z_entry_max_x1000: -1800`) |
| `venue_constraint_policy.yaml` | `policy_id` SHORT 전용 (+ 헤더 제목·주석). **값은 LONG 과 같다**(`tick_size: 2` · `max_quantity: 10000`) |
| `critical_input_policy.yaml` | `policy_id`·`issuer_principal_id` SHORT 전용 (+ 헤더 제목). **열다섯 필드와 다섯 값은 LONG 과 같다**(`max_age_ms: 180000` 포함) |
| `README.md` (이 파일) | **산문이 다름** — 각 트리가 자기 방향의 배포를 설명한다. YAML 이 아니라 경로 비교 대상이 아니므로 테스트가 「자기 트리를 설명하는가」로 검사한다 |
| 나머지 **23 개** | **바이트 동일** — LONG 트리에서 그대로 복사됐다. 그 중 22 개는 상주 트리의 사본이기도 하다(§3.0) |

### 3.0 ⛔ 사본 의무 — 상주 쪽을 바꾸는 PR 은 **같은 PR 에서** 이 트리도 갱신한다

위 24 개 중 **22 개는 상주 `config/tos_runtime/paper/` 파일의 바이트 사본**이다(나머지 둘은
`README.md` 와 `strategy_bindings.yaml` 로 tenant 전용이고, 이 트리는 거기에
`marketfeed.yaml` 을 상주와 **다르게** 들고 있다 — LONG 트리에서는 그것이 상주 사본이다).
그러므로 상주 파일 하나를 바꾸는 PR 은 **같은 PR 에서** 두 tenant 트리의 사본을 함께
갱신해야 한다.

⚠ **`release.yaml` 은 조용히 낡는 것으로 끝나지 않는다** — `expected_code_digest` 를 싣는다.
런타임 코드를 바꾸는 PR 은 그 핀을 **상주 트리에서만** 재도출하고, 상주 세션은 매일 재도출해
대조하지만(런북 §5 ①) tenant 트리는 **부팅한 적이 없어** 낡은 핀이 드러날 레인이 없다 —
첫 부팅이 digest 불일치로 **ABORT** 한다.

`tos/runtime/tests/compose/test_tenant_tree_copies.py` 가 이 의무를 고정하고, `release.yaml`
은 실패 메시지가 「두 트리에서 같은 PR 에 재도출하라」고 말하도록 **따로** 단언된다.

### 3.1 방향이 사는 자리 넷 — 런북 §7.10 3 의 체크리스트

런북 `docs/runbooks/tos-paper-boot.md` §7.10 3 은 「대칭이 깨지는 계기는 날짜가 아니라
**코드 변경**」이라며 방향이 사는 자리를 **셋**으로 열거한다
(`construction.yaml::action_class`/`outbound_side` · OCP 의 DIRECTION 축 · 전략 파일의
`direction`). 이 트리는 거기에 **넷째**를 더한다 — `marketfeed.yaml::direction`(발행되는
모든 캡슐의 `SafetyCriticalFacts` 로 들어간다) — 그리고 **다섯째**가 DSL 때문에 생긴다:
**진입 비교의 변과 그 바인딩**(`op: GE` + `z_entry_min_x1000`). 다섯 자리 전부를
`test_tenant_tree_short.py` 가 LONG 사본과 대조해 고정한다.

⚠ **런타임은 이 중 어느 것도 서로 대조하지 않는다.** `marketfeed.yaml::direction` 이 OCP 축과
어긋나도 로더는 거부하지 않고(캡슐이 틀린 방향을 달고 조용히 부팅한다), 활성화 기록도
방향을 결속하지 않는다(런북 §5 ⑤ · OCP 헤더의 KNOWN LIMITATION: LONG 렌더와 SHORT 렌더는
다섯 정책 kind 전부에서 **바이트 동일한 digest** 를 낸다). **실측 2026-10-09 로 그보다 한
걸음 더 나쁘다**: OCP 의 `canonical_digest` 는 DIRECTION 축을 바꿔도, **`policy_id` 를 바꿔도**
달라지지 않는다. 그래서 이 트리의 OCP `policy_id` rename 이 digest 를 가르지는 못하고,
활성화 키 `(kind, member_id, generation)` 의 **`member_id` 만** 두 문서를 구별한다 — rename
이 그 자리를 위한 것이다.

⚠ **VCP 도 이 두 트리를 가르지 못한다 — 다른 이유로.** VCP 의 digest 는 OCP 와 달리
`_model_view.shape_constraints` 를 **덮는다**(`tick_size` 하나만 바꿔도 달라진다 — 실측).
그런데 **`policy_id` 는 덮지 않고**, LONG 과 SHORT 의 shape 는 **같다**(tick 2 · lot 1 ·
min 1 · max 10000 · band null). 그래서 **두 트리의 VCP digest 는 동일하다**(실측
2026-10-09). 결론은 OCP 와 같다: 두 VCP 문서를 가르는 것은 digest 가 아니라 활성화 키의
**`member_id`** 뿐이고, 그래서 **이 트리의 VCP rename 도 장식이 아니라 유일한 판별 수단**
이다. 「VCP digest 는 내용을 덮으므로 두 배포를 구별한다」로 읽지 말 것 — 덮는 내용이
같으면 구별하지 않는다. 이 사실은
`test_tenant_tree_short.py::test_policy_digests_cannot_tell_the_two_trees_apart` 가 고정한다.

### 3.2 `direction` 토큰의 두 뜻 — 섞지 말 것

FLAT 규칙의 `direction` 은 **닫는 액션의 방향**이고(`tos/src/tos/dsl/proposal.py::build_flat`
「The direction of the **closing action**」) OCP `action_class_shape` 의 `CLOSE` 아래 키는
**닫히는 포지션의 방향**이다(`CLOSE.LONG = {side: SELL}` · `CLOSE.SHORT = {side: BUY}`).
그래서 이 트리의 R2·R3 는 `direction: LONG`(매수로 닫는다)이고 OCP 축은 `SHORT` 인데, 그
둘은 **같은 사실의 다른 표기**다: 런타임은 전략 target 의 토큰을 construction 에 쓰지 않고
(`Proposal.direction` 배선 없음), `CLOSE` 의 방향을 **OCP 축**에서 읽으므로
(`compose/_envelope_wiring.py::resolve_construction_direction` — 방향을 푸는 **유일한** 자리)
축 `SHORT` → `CLOSE.SHORT` → **BUY** 가 된다. 두 표기를 고정하는 것은 주석이 아니라
`test_tenant_tree_short.py::test_flat_rule_direction_is_the_closing_action_not_the_position` 이다.

### 3.3 ⚠ SHORT parity 공백 — **이 방향에는 parity 증거가 0 이다**

1. **B1b parity 실행은 LONG 단독이었다 — 선언된 차이 `B1b-D5`.** B3 실측
   (kickoff §5 2, `101S6000` 2025-12-01~2026-04-30, 35,612 봉)에서 레거시 FIRED 550 =
   **LONG 374 / SHORT 176** 이었고, 규칙 수준 진입 일치 **374/374 = 100 %** 는 **LONG 쪽
   수치다**. SHORT 176 은 전부 `LEGACY_ONLY_ENTRY` 버킷에 들어가 **B1b-D5 로 귀속**됐다 —
   「TOS 쪽이 틀렸다」가 아니라 「TOS 쪽에 SHORT 렌더가 없어서 비교가 성립하지 않았다」는
   뜻이다. 그러므로 **이 트리의 진입 규칙은 한 번도 레거시와 대조된 적이 없다.**
   닫으려면 B1b 를 이 전략 파일로 다시 돌려 B3 를 다시 내야 한다(미착수).
2. **레거시의 SHORT 전용 가드가 삭제됐다 — 결정 5 의 의도된 차이.** 레거시
   `config/strategies/futures/setup_d_vwap_reversion.yaml` 은
   `short_blocked_regimes: ["BULL_STRONG"]` 를 들고 있고(`long_blocked_regimes` 는 **빈
   리스트**다), 그 주석이 근거를 적는다: 「강한 추세 레지임에 맞서 VWAP 스파이크를 페이드하는
   것이 추세 지속일의 **지배적 실패 모드**」. TOS 에는 regime 입력이 없어 이 가드를 옮길 수
   없고 결정 5 가 **삭제를 의도된 차이로 등재**했다. ⚠ **그 가드는 SHORT 에만 걸려 있었으므로
   손실은 이 트리에 비대칭적으로 떨어진다** — LONG 트리는 잃은 것이 없다. 결정 5 는 그래서
   「07-07 노출이 **둘 다** 열린다」고 적고 parity 보고서의 SHORT 편향 diff 를 이 항목에
   귀속시킨다.
3. **ATR 스톱(1.5×)과 `min_confidence` 는 LONG 과 같은 이유로 없다** — 결정 6 · B1a-D1.
   대칭이므로 SHORT 전용 공백은 아니지만, SHORT 쪽 검증이 아예 없는 상태에서 함께 읽어야
   하는 항목이라 여기 적는다.

**필드는 LONG 과 같은 열다섯이고 SHORT 변종을 만들지 않았다** — 그 실측 근거(게이트 불린의
방향 의존이 **z 의 부호**에서 나오므로 SHORT 규칙이 발화할 수 있는 봉에서는 이미 숏 쪽
게이트가 평가돼 있다)는 전략 파일 헤더에 있다. **없는 필드를 지어내지 않았다.**

## 4. data dir · 렌더된 설정 — 지정 2026-10-09 (결정 3)

| 무엇 | 어디 | 비고 |
| --- | --- | --- |
| durable set **부모** | `~/.local/state/tos/cp3-setup-d-short-data` | **0700** · 저장소 밖 · **아직 없다** |
| durable set **잎** | `cp3-setup-d-short-data/<종목>` | 계약월마다 하나 · **0700**(디렉터리) · **0600**(스토어 넷) · **그 잎의 첫 세션 genesis 가 만든다** |
| 렌더된 설정 | `~/.config/tos/cp3-setup-d-short-config` | **0700** · 부팅 직전 재렌더(저널 신선도) · **아직 없다** |

이름 규칙은 **「설정 트리 이름 + `-data` / `-config`」**다. 경로만 보고 어느 코퍼스가 어느
트리로 부팅됐는지 알 수 있어야 하기 때문이다(런북 §5 ⑤: **활성화 기록은 방향을 결속하지
않으므로** 경로가 그 역할을 한다 — §3.1 의 digest 실측도 같은 결론이다).

- ⛔ **LONG 과 섞지 않는다 — 부모부터 다르다.** 상주 잎에도 절대 섞지 않는다(런북 §7.10 3).
- ⚠ **디렉터리를 만들지 않았다.** genesis 는 첫 부팅이고 그것은 ④ 다(§5 2).
- ⚠ **콜드 백업에 아직 들어 있지 않다** — 래퍼는 `COLD_DATA_DIR`(기본 `paper-data`)의 직접
  자식 중 `A0####` 만 잎으로 세고 `~/.local/state/tos/*` 를 글로브하지 않는다. 켜는 것은
  **운영자 결정**이다.
- ⚠ **이름 인접 주의**: `~/.config/tos/paper-config-short` 가 **이미 있다** — 2026-09-28
  **상주** SHORT 부팅증명 캠페인의 산출물이고 이 트리와 **무관**하다.
- 전체 표·충돌 실측은 런북 **§7.2-b**.

## 5. 무엇이 증명되지 않았나 (이 PR 이 하지 않은 것)

1. **부팅 0 회.** 이 트리로 `run` 을 돌리지 않았다. 검증된 것은 테스트가 보는 것뿐이다
   (`tos/runtime/tests/compose/test_tenant_tree_short.py` · `test_deploy_policies.py`):
   ① `venue_constraint_policy.yaml` 이 좌표 미채움 상태에서 **거부되고** 좌표를 채우면
   `tick_size: 2` · `max_quantity: 10000` 으로 적재된다 · ② `critical_input_policy.yaml` 이
   **적재되고** 어느 리프든 `max_age_ms` 가 `null` 이면 그 키 이름으로 거부된다 ·
   ③ `construction.yaml` 의 두 price 키가 이 트리의 critical_input 필드 집합 안에 있다 ·
   ④ 방향 다섯 자리가 LONG 사본과 **선언된 집합에서만** 갈린다 · ⑤ 진입 임계 등식
   `z_entry_min_x1000 == +trunc(extreme_atr_mult × 1000)`.
   ⚠ **「적재된다」를 「부팅하면 돈다」로 읽지 말 것** — LONG 트리 README §5 의 ⚠⚠ 와 같은
   이유(커널 시간 경로의 800 ms 보수 예산)가 이 트리에도 그대로 적용된다.
2. **렌더가 이 트리를 처리하지 못한다** — kickoff §5 3 ④. LONG 트리와 같은 두 이유
   (`_STRATEGY_FILE` 고정 · 앵커 1회 매칭 요구)이고, 전략 파일 헤더가 적는다.
   ⚠ **그러므로 이 트리는 `--direction SHORT` 렌더가 만든 것이 아니다.**
3. **실시간 필드 생산자가 없다** — kickoff §5 3 ③. B1a 는 Parquet 배치 도구다.
4. **SHORT parity 증거 0** — §3.3. 이것이 이 트리의 가장 큰 공백이다.
5. **체결·영수증 증거 없음** — band 가 null 인 동안 step 3 는 UNKNOWN 이다.
   실주문은 어느 경우에도 0 이다(채택 스코프 `SYNTHETIC_FUTURES_ORDER`, `broker_scopes.yaml`).
6. **활성화 0** — `safety_activation.yaml::members` 는 `null` 이다. digest 리터럴을 지어내지
   않았다. 활성화는 ④ 의 일이다.

## 6. 운영자 미결 항목

1. **`max_age_ms` 의 실제 원천** — LONG 과 같은 등급 C 값(180000)을 들고 있다. ③ 생산자
   측정 뒤의 하향·재도출이 남는다. 도출은 그 파일 헤더에 있다.
2. **SHORT parity 실행** — §3.3 1. B1b 를 이 전략 파일로 돌려 B3 를 다시 내는 일.
3. **data dir genesis 와 콜드 백업 편입** — §4.
