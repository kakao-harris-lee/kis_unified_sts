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

**32 파일 = 바이트 동일 23 + YAML 이 다름 7 + 산문이 다름 1(`README.md`) + SHORT 전용 1**
(LONG 트리도 32 파일이다; LONG 의 `strategies/setup_d_long.strategy.yaml` 은 이 트리에
**없고** 그 자리를 `strategies/setup_d_short.strategy.yaml` 이 차지한다). 31 → 32 · 다름
6 → 7 은 2026-10-10 PR-B 가 더한 **`RENDER.yaml`**(렌더 매니페스트) 때문이다.

측정은 작업트리 `cmp` 가 아니라 `tos/runtime/tests/compose/test_tenant_tree_short.py` 다 —
바이트 동일 23 은 **바이트**로, 다름 7 은 **파싱된 YAML 경로 집합의 등식**으로, `README.md`
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
| `critical_input_policy.yaml` | `policy_id`·`issuer_principal_id` SHORT 전용 (+ 헤더 제목). **열다섯 필드와 다섯 값은 LONG 과 같다**(`max_age_ms: 800` 포함) |
| `RENDER.yaml` | 렌더 매니페스트(2026-10-10 PR-B). `tree_id` · `direction.value` **LONG → SHORT** · `slots` 의 **방향 결속 다섯 줄과 전략 파일 이름**. 모드는 둘 다 `declared` + `external` 이다. `slots` 는 리스트라 경로 비교에서 **한 잎으로 접히므로** 전용 좁히기 테스트(`test_the_render_manifest_slot_list_differs_only_in_the_direction_bearing_rows`)가 따로 있다 |
| `README.md` (이 파일) | **산문이 다름** — 각 트리가 자기 방향의 배포를 설명한다. YAML 이 아니라 경로 비교 대상이 아니므로 테스트가 「자기 트리를 설명하는가」로 검사한다 |
| 나머지 **23 개** | **바이트 동일** — LONG 트리에서 그대로 복사됐다. 그 중 22 개는 상주 트리의 사본이기도 하다(§3.0) |

### 3.0 ⛔ 사본 의무 — 상주 쪽을 바꾸는 PR 은 **같은 PR 에서** 이 트리도 갱신한다

LONG 트리와 **바이트 동일한 23 개** 가운데 **22 개가 상주 `config/tos_runtime/paper/` 파일의
바이트 사본**이고, 남는 **하나는 `engine.yaml`** 이다(상주와 **주석이 다르다** — 상주 주석이
상주 전략 `bootproof_band` 를 인용해 이 트리에서 거짓이 되므로 tenant 적용 문단을 덧붙였다.
두 tenant 트리끼리는 같다). 실측은 blob 재계수다(2026-10-09 리뷰 L2 — 초판은 「위 24 개 중
22 개」라고 적고 남는 둘을 `README.md`·`strategy_bindings.yaml` 로 지목했는데, **총계와 지목이
모두 틀렸다**: 그 둘은 LONG 과도 다르므로 애초에 그 23 에 들어 있지 않다).

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

### 3.3 ✅ SHORT parity — **닫혔다 (2026-10-09 실측)**

> 이 절은 2026-10-09 까지 「이 방향에는 parity 증거가 0 이다」였다. 운영자 지시
> (「short 전략 파일로 다시 돌려줘」)로 B1b 를 SHORT 로 돌려 B3 를 다시 냈고, 아래가 그
> 수치다. **남은 공백은 §3.3-2 하나**(regime 가드)이고 그것은 이 비교가 **원리상** 볼 수
> 없는 종류의 차이라는 것까지 실측됐다.

1. ✅ **SHORT 규칙 수준 진입 일치 176/176 = 100 %** (`101S6000` 2025-12-01~2026-04-30,
   35,612 봉 · 깨끗한 분리 워크트리 `dirty:false`). 레거시 FIRED 550 = **LONG 374 /
   SHORT 176** 은 같은 B2 아티팩트이고(바이트 동일 재현), 이번에는 **SHORT 176 쪽**이
   분모다. 포지션 모델 수준 **56/56 = 100 %**, TOS 쪽에서 본 **176/188 = 93.62 %**,
   **UNRESOLVED 0**. 초과한 12 는 전부 레거시 `LOW_CONFIDENCE`(B1a-D1·B2-L9 — 공개 필드가
   `min_confidence` 를 표현할 수 없어 정책이 「레거시 발화」의 상위집합이다). 레거시 LONG
   발화 374 는 이제 **거울로** `LEGACY_ONLY_ENTRY` → 귀속 `legacy_long_entry`(B1b-D5)다.
   전체 수치와 산출물 sha256 은 kickoff §5 2 의 SHORT 문단에 있다.
   ⚠ **이 트리의 전략 파일이 직접 실행된 것은 아니다** — 실행된 것은 B1b 쪽 사본
   `tos/runtime/cp3/short/strategies/setup_d_short.strategy.yaml` 이고(이 파일은 좌표가
   `"TBD"` 라 적재되지 않는다, §5 1), 둘이 **좌표 정규화 뒤 같은 파싱 YAML** 이라는 것은
   `tos/runtime/cp3/tests/test_cp3_short_strategy_content.py` 의 드리프트 가드가 고정한다
   (레드 증명 다섯). 그 가드는 이 PR 전까지 **LONG 쪽에도 없었다**.
2. **레거시의 SHORT 전용 가드가 삭제됐다 — 결정 5 의 의도된 차이.** 레거시
   `config/strategies/futures/setup_d_vwap_reversion.yaml` 은
   `short_blocked_regimes: ["BULL_STRONG"]` 를 들고 있고(`long_blocked_regimes` 는 **빈
   리스트**다), 그 주석이 근거를 적는다: 「강한 추세 레지임에 맞서 VWAP 스파이크를 페이드하는
   것이 추세 지속일의 **지배적 실패 모드**」. TOS 에는 regime 입력이 없어 이 가드를 옮길 수
   없고 결정 5 가 **삭제를 의도된 차이로 등재**했다. ⚠ **그 가드는 SHORT 에만 걸려 있었으므로
   손실은 이 트리에 비대칭적으로 떨어진다** — LONG 트리는 잃은 것이 없다.
   ⚠⚠ **그러나 그 손실은 이 비교에 나타날 수 없다 — 그리고 그 근거는 `B1b-D8` 의 0 이
   아니다.** 기계장치는 **B2 가 이미 자기 차이 `B2-L1` 로 선언해 둔 것**이다(「this emitter
   runs `SetupDVWAPReversion.check()` ALONE … that block CANNOT fire here」): B2 는
   `tools/tos_cp3/emit_legacy_decisions.py:946`·`:990` 에서 setup 을 만들어 `check()` 를
   **직접** 몰고, 그 블록은 한 겹 위 `shared/strategy/entry/setup_d_adapter.py:174` —
   `check()` 가 반환하는 `:166` **뒤** — 에 있다. 즉 **레거시 쪽도 그 블록을 적용한 적이
   없고** 양쪽이 똑같이 무방비다. 그러므로 결정 5 가 말한 「parity 보고서의 SHORT 편향 diff
   를 이 항목에 귀속」은 **이 결정 수준 비교에서는 성립하지 않는다**.
   ⛔ **`summary.json` 의 `attribution_ids['B1b-D8'] == 0` 을 그 증거로 읽지 말 것**
   (2026-10-09 리뷰 L1): **어떤 귀속 규칙도 B1b-D8 을 인용하지 않으므로**(B1b-D9 도 같다)
   그 0 은 **구조적으로** 0 이고 가드가 실제로 물었어도 0 이었다. 「이 창에 숨은 regime 차이가
   없다」를 받치는 것은 **UNRESOLVED 0** 이다 — regime 에 막혔어야 할 레거시 SHORT 발화에
   이 정책이 발화했다면 그 봉은 `TOS_ONLY_ENTRY` 에 어떤 규칙도 맞지 않는 채로 남는다.
   닫으려면 B2 가 어댑터의 판정을 공개해야 하고 그것은 B2 변경이다. 배포(paper/live)는
   어댑터를 타므로 차이는 **거기서** 실재한다. 이 문단은 `B1b-D8` 의 note 와
   `test_cp3_short_strategy_content.py::test_the_regime_guard_difference_says_why_it_cannot_show_up`
   이 고정한다 — 그 테스트는 어댑터에서 `check()` 가 블록보다 **앞**인지, 그리고
   `shared/decision/setups/vwap_reversion.py` 안에 regime 블록이 **없는지**(음의 단언)까지
   읽는다.
3. **ATR 스톱(1.5×)과 `min_confidence` 는 LONG 과 같은 이유로 없다** — 결정 6 · B1a-D1.
   대칭이므로 SHORT 전용 공백은 아니다. `min_confidence` 는 위 1 의 초과 12 로 **관측됐다**
   (B1a-D1·B2-L9 을 인용하는 귀속 규칙이 **있기** 때문에 그 12 는 측정값이다).
   ⛔ ATR 스톱(`B1b-D9`)의 흡수 봉 0 은 위 2 의 `B1b-D8` 과 **같은 이유로 구조적**이다 —
   그것을 인용하는 귀속 규칙이 없다. 청산 비교 자체가 `B1b-D7` 의 **미이행 의무** 아래에
   있다는 것이 그 항목의 실제 상태다(kickoff §5 2 · B3 `summary.json` 의
   `scope.b1b_d7_obligation` = UNMET).

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
- ⛔ **켤 때 `COLD_DATA_DIR` 만 지정하면 안 된다**(2026-10-09 리뷰 H1). 그 변수만 바꾼 실행은
  `COLD_CONFIG_DIR` 기본값 `~/.local/state/tos/paper-ops` 를 쓰고, 래퍼는 `COLD_ROOT` 를 그
  기준 설정 세 경로의 **공유 부모**(= `paper-cold`)로 유도하므로 잎별 설정·보관소가 **상주**
  `paper-ops/leaves/<잎>` · `paper-cold/<잎>` 에 들어간다. 잎 이름은 계약월이라 상주·LONG·
  SHORT 가 **같은 잎 이름**을 갖고, 그 두 경로는 **잎 이름만**으로 키를 잡는다(`:443-444`).
  결과는 **동시성에 따라 갈린다** — 기본 락이 공유라 직렬이면 거부가 아니라 **섞인다**
  (세대는 `backup_root` 단위 `:49-51`, 잎별 파생 설정은 매 실행 재생성 `:54`), 락을 우회해
  동시가 되면 `:49-55` 대로 **둘째가 산출물 충돌로 거부된다**. (래퍼 헤더의 `COLD_LOCK`
  항목 `:86-92` 는 같은 말을 **락 우회**라는 다른 계기로 하는 유사 진술이고 기본 설정 tenant
  실행에 대한 진술이 아니다 — 2026-10-09 재검토.)
  그래서 셋을 함께 지정한다 — `COLD_DATA_DIR` ·
  **`COLD_CONFIG_DIR=~/.local/state/tos/cp3-setup-d-short-ops`** ·
  **`COLD_TARGET_BORN_ON=<이 잎의 첫 부팅일>`**(기본 `2026-10-06` 을 두면 genesis 전 부재가
  조용한 rc 0 이 아니라 **rc 1 refused** 다). 그리고 그 ops 의 `evidence_cold_backup.yaml`
  세 경로는 **`~/.local/state/tos/cp3-setup-d-short-cold/`** 아래여야 한다. ⚠ 그 ops·cold
  디렉터리도 **아직 없다**.
- ⚠ **이름 인접 주의**: `~/.config/tos/paper-config-short` 가 **이미 있다** — 2026-09-28
  **상주** SHORT 부팅증명 캠페인의 산출물이고 이 트리와 **무관**하다.
- 전체 표(ops·cold 열 포함)·충돌 실측은 런북 **§7.2-b**.

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
   이유가 이 트리에도 그대로 적용된다: `max_age_ms` = 800 은 커널의 보수 예산 **그 자체**
   이고, 라벨 스탬프 1분봉은 최소 나이가 60,000 ms 라 열다섯 전부 `(UNKNOWN, "stale")` 다.
2. ✅ **렌더는 이 트리를 처리한다 — 2026-10-10(계획 2026-10-09 PR-B).** LONG 트리 README
   §6 2 와 같은 두 처분(슬롯 표가 `RENDER.yaml` 로 · 전략 파일 R1 앵커 + R2·R3 별칭)이다.
   이 트리의 `RENDER.yaml` 은 `direction.mode: declared` + `value: "SHORT"` ·
   `journal.mode: external` 이다.

   ```bash
   python scripts/tos/render_paper_config.py \
     --source config/tos_runtime/cp3-setup-d-short \
     --out ~/.config/tos/cp3-setup-d-short-config \
     --env-file .env.mock \
     --instrument <근월물 mini 코드> \
     --direction SHORT \
     --journal-path <③ 생산자의 출력>
   ```

   ⚠ **그래도 이 트리는 `--direction SHORT` 렌더가 만든 것이 아니다** — 트리는 여전히
   LONG 사본 + 선언된 방향 차이로 **커밋**돼 있고, 렌더는 그 방향을 **검증만** 한다
   (`--direction LONG` 은 거부된다). ⚠ **아직 안 돌렸다** — 위 `--out` 디렉터리는 §4 대로
   없다. 첫 실제 genesis 는 ③ 뒤의 운영자 결정이다.
3. **실시간 필드 생산자가 없다** — kickoff §5 3 ③. B1a 는 Parquet 배치 도구다.
   ⛔ ③ 에는 **저널 append 시각 스탬프**라는 구속 요구가 붙어 있다(운영자 결정 2026-10-09 ·
   LONG README §5) — 라벨 스탬프 생산자로는 이 트리도 결정까지 가지 못한다.
4. ✅ **SHORT parity 증거 — 2026-10-09 에 생겼다**(§3.3 1: 규칙 수준 176/176 = 100 %,
   UNRESOLVED 0). ⚠ 그 실행은 이 트리의 전략 파일이 아니라 **좌표만 다른 B1b 사본**으로
   돌았고(이 파일은 `"TBD"` 라 적재되지 않는다), 둘의 등식은 드리프트 가드가 고정한다.
   그리고 그것은 **결정 수준** 증거이지 체결·PnL 증거가 아니다 — B3 의 `scope` 가 그렇게
   적는다. 남은 공백은 §3.3 2(regime 가드는 이 비교가 보는 지점이 아니다)와 위 1~3 이다.
   ⚠ 그 parity 실행은 **clock-free `tos.backtest`** 라 위 1 의 `max_age_ms` = 800 문제와
   무관하다(주입된 시간 경계로 신선도를 판정한다 — 선언된 차이 **B1b-D3**). parity 가 생긴
   것이 ③·그 append-시각 요구를 대신하지 않는다.
5. **체결·영수증 증거 없음** — band 가 null 인 동안 step 3 는 UNKNOWN 이다.
   실주문은 어느 경우에도 0 이다(채택 스코프 `SYNTHETIC_FUTURES_ORDER`, `broker_scopes.yaml`).
6. **활성화 0** — 이 **커밋된** 트리의 `safety_activation.yaml::members` 는 `null` 이고 그대로
   둔다. digest 리터럴을 지어내지 않았다. 렌더는 그 칸을 **산출 dir 에서만** 채운다
   (손으로 적는 경로는 없다 — `print-policy-digests` 다섯 줄에서 **도출**하고 새 프로세스로
   재검증한다, 위 2). 그러므로 활성화 기록은 **렌더된 사본에만** 생기고, 첫 실제 부팅은
   ③ 뒤의 운영자 결정이다.

## 6. 운영자 미결 항목

1. **`max_age_ms` 가 실제로 만족 가능한가** — LONG 과 같은 **등급 A(운영자 결정 2026-10-09)**
   값(800 = 커널 시간 예산 1000 − Σ지연 200; 두 항 다 VER-002 APPROVED)을 들고 있다. 값·등급은
   미결이 아니고, 남은 것은 ③ 생산자의 발행 지연 측정이다. ⛔ 그 측정이 나빠도 처분은
   **한도 상향이 아니라 ③ 쪽**이다. 좌표와 근거는 그 파일 헤더에 있다.
2. **SHORT parity 실행** — §3.3 1. B1b 를 이 전략 파일로 돌려 B3 를 다시 내는 일.
3. **data dir genesis 와 콜드 백업 편입** — §4.
