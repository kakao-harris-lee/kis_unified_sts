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
- **SHORT 는 여기 없다.** DSL 에 `abs()` 가 없어 진입 비교가 한 변뿐이므로 SHORT 는
  `z_x1000 >= +1800` 을 쓰는 **자기 파일·자기 트리**를 갖는다(결정 4; kickoff §5 3 마지막 줄).

## 2. 환경 라벨은 `paper` 다 — tenant 식별자가 아니다

`critical_input_policy.yaml::environment` 와 `venue_constraint_policy.yaml::scope.environments`
· `order_construction_policy.yaml` 의 라벨은 모두 **`paper`** 다. 이유는 kickoff §5 1 이
적는다: 로더는 그 토큰을 `--environment-label` 과 **대조하지 않으므로** 어긋나도 조용히
부팅하고 증거만 틀린 라벨을 단다. compose 는 정책들끼리는 대조하므로(`_cross_check_scope`
→ `VenuePolicyScopeMismatch`) 셋이 같아야 한다.

그러므로 **같은 라벨 아래 두 배포**(상주 세션과 이 tenant)가 존재한다. 둘을 가르는 것은
라벨이 아니라 **설정 트리와 data dir** 이다(결정 3).

## 3. 상주 트리와 무엇이 다른가 (실측 2026-10-09)

| 파일 | 상태 |
| --- | --- |
| `venue_constraint_policy.yaml` | **다름** — `max_quantity` null → **10000**(결정 9 (a), 아래 §4). 런타임이 읽는 값 차이는 이 한 곳뿐이다 |
| `critical_input_policy.yaml` | **다름** — 사본이 아니다. 상주 쪽은 부팅 증명 픽스처의 **세 필드**, 이쪽은 tenant 상류 **열다섯 필드**(아래 §5) |
| `strategies/setup_d_long.strategy.yaml` | **신규** — 상주의 `strategies/bootproof_band.strategy.yaml` 을 **대체**한다(그 파일은 이 트리에 없다) |
| `strategy_bindings.yaml` | **신규** — `z_entry_max_x1000: -1800`. `strategies/` 의 **형제**다(안에 두면 로더의 stray-file 규칙이 디렉터리 전체를 거부한다) |
| `engine.yaml` · `order_construction_policy.yaml` | **주석만 다름** — 값은 상주 승인값 그대로다. 두 파일의 기존 주석이 상주 전략(`bootproof_band`)을 인용하고 있어 이 트리에서 거짓이 되므로, 각 자리에 tenant 적용 한 문단을 덧붙였다(스텝 수 24 ≤ 64 재측정 · `quantity_basis` 선언 자리) |
| 나머지 **23 개** | **바이트 동일** — 상주 트리에서 그대로 복사된 승인값이다. 아래 ⚠ 를 볼 것 |

> ⚠ **바이트 동일한 23 개 안의 `config/tos_runtime/paper/...` 인용을 「이 트리의 형제
> 파일」로 읽을 것.** 그 파일들은 서로를 **절대 경로 꼴**로 인용한다(예 `time.yaml` 의
> 「강제 일치: config/tos_runtime/paper/calendar.yaml 의 `calendar_version`」 ·
> `construction.yaml`·`marketfeed.yaml`·`safety_profile.yaml`·`safety_activation.yaml` ·
> `calendar.yaml`·`broker_scopes.yaml`). 런타임의 그 대조는 **하나의 `--config-dir` 안에서**
> 일어나므로 실제로 가리키는 것은 **이 트리의 같은 이름 파일**이다. 경로를 일괄 치환하지
> 않은 이유는 그렇게 하면 「상주 승인값의 사본」이라는 **기계로 확인 가능한 성질**
> (`cmp` 로 23/23 동일)을 잃기 때문이다. 치환 규칙은 이 줄이 유일한 기록이다 — 값을
> 바꿀 때는 그 파일이 더 이상 사본이 아니므로 §3 표의 행을 옮긴다.

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
- **`tick_size` 는 5 그대로다.** mini 규정값 2 로의 정정은 승인됐으나 **band 원천 웨이브
  (설계 §6)의 전제 항목**이고 이 PR 범위 밖이다. band 가 null 인 동안 tick 검사는 step 3
  UNKNOWN 에 가려져 효력이 없다.
- **`price_min`/`price_max` 는 null 그대로다** — 일별 동적 값이라 정적 리터럴 금지(설계 §6).

## 5. `critical_input_policy.yaml` — 열다섯 필드, `max_age_ms` 는 출처 없음

필드 목록·순서는 B1a 의 `FIELD_ORDER`(`tools/tos_cp3/produce_fields.py`) 그대로이고,
각 필드의 `unit`/`scale`/`multiplier`/`sign` 은 **B1a 의 필드 lineage** 에서 온다
(`produce_fields._field_lineage` — 그 독스트링이 「이 파일이 쓰는 모양으로 적는다」고 말한다).

**`max_age_ms` 는 열다섯 전부 `null` 이고, 그래서 이 파일은 오늘 로드되지 않는다.** 로더가
`null` `max_age_ms` 를 거부한다(`marketfeed/policy.py`). 이것은 결함이 아니라 상주 트리가
출처 없는 값에 쓰는 **fail-closed 규율**(`finality.yaml::source_revision` ·
`safety_activation.yaml::members`)과 같은 상태다. 근거는 그 파일 헤더에 있다: 제안표에 행이
없고(안전 값이라 의도적으로 채택 안 됨), B1a lineage 도 이 키를 적지 않으며, 상주의 600000
은 **배치 저널 부팅**의 근거로 정당화된 값이라 생산자가 없는 이 tenant 로 옮길 수 없다.
→ **운영자 출처가 필요한 미결 항목**(§7).

## 6. 무엇이 증명되지 않았나 (이 PR 이 하지 않은 것)

1. **부팅 0 회.** 이 트리로 `run` 을 돌리지 않았다. 검증된 것은 `venue_constraint_policy.yaml`
   이 좌표 미채움 상태에서 **거부되고**(운영자-채움 게이트) 좌표를 채우면 `max_quantity: 10000`
   으로 적재된다는 것뿐이다(`tos/runtime/tests/compose/test_deploy_policies.py`).
2. **렌더가 이 트리를 아직 처리하지 못한다** — kickoff §5 3 ④. `scripts/tos/render_paper_config.py`
   는 (a) `_STRATEGY_FILE` 이 `strategies/bootproof_band.strategy.yaml` 로 고정이고
   (b) 좌표 규칙이 앵커 **정확히 1회** 매칭을 요구하는데 이 트리의 전략 파일은 규칙이 셋이라
   `account: "TBD"`·`instrument: "TBD"` 가 각 3회 나오며 `direction` 은 줄마다 값이 다르다
   (R1 LONG 진입 / R2·R3 는 롱을 닫는 SHORT). 즉 ④ 는 「상수 한 줄 교체」가 아니다.
   그 뒤에 digest 다섯 재도출 + `safety_activation.yaml::members` 갱신이 따라온다(런북 §5).
3. **실시간 필드 생산자가 없다** — kickoff §5 3 ③. B1a 는 Parquet 배치 도구이고 발행기가
   아니다. 복사된 `marketfeed.yaml` 은 상주와 같은 **저널 기반** 좌표를 들고 있다.
4. **체결·영수증 증거 없음** — band 가 null 인 동안 step 3 는 UNKNOWN 이다(설계 §3).
   실주문은 어느 경우에도 0 이다(채택 스코프 `SYNTHETIC_FUTURES_ORDER`, `broker_scopes.yaml`).

## 7. 운영자 미결 항목

1. **`critical_input_policy.yaml::fields[].max_age_ms` ×15** — 신선도 한도. 출처 없음(§5).
2. **정책 식별자** — `venue_constraint_policy.yaml` 의 `policy_id`/`policy_generation` 은
   상주 트리의 것과 **같은 값인데 내용은 다르다**. 두 트리는 따로 활성화되므로 한 bound set
   안에서 충돌하지 않지만, `(kind, member_id, generation)` 만으로는 두 문서를 구별할 수 없다.
   tenant 전용 식별자로 바꿀지는 부팅 경로(④)에서 처분한다 — 이 PR 은 결정하지 않았다.
3. **SHORT 트리** — 결정 4 의 나머지 반쪽. 별도 렌더·별도 트리·별도 data dir.
4. **data dir** — 결정 3 의 「방향마다 따로」. 상주 잎에 절대 섞지 않는다(런북 §7.10 3).
