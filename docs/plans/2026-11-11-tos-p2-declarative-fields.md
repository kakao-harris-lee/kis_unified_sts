# P2 — 선언형 지표 필드: `fields.yaml` 과 필드 카탈로그

- 작성: 2026-11-11 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 상위: [플랫폼 로드맵 §P2](2026-11-11-tos-platform-roadmap.md)
- 근거: 운영자 2026-11-11 「다시 코드 기반으로 돌아 가면 안돼. 우리는 돈을 다루는 시스템을 만들거라서 버그, 회귀를
  최소화 하려는 노력이 기본적으로 필요해.」 · 「P2 작업 바로 시작해」

## 1. 지금 무엇이 코드에 묶여 있나 (실측)

`tools/tos_cp3/produce_fields.py::produce_bars` 가 레거시 `SetupDVWAPReversion.check()` 를 바마다 한 번 불러
`last_eval` 을 필드로 옮긴다. 15 필드 중 어떤 것이 어디서 오는가:

| 필드 | 출처 | 성질 |
| --- | --- | --- |
| `open/high/low/close_x100` · `volume` · `session_token` | 분봉 행 | 바 원값 |
| `vwap_x100` · `atr14_x100` | `MarketContextReplay` (`ctx.vwap` 세션 typical-price VWAP, `ctx.atr_14`) | 상태 없는 창 지표 |
| `z_x1000` | `vwap_extension_z(close, vwap, atr)` = (close−vwap)/atr, 0 쪽 절사 ×1000 | 파생 |
| `entry_window` | `valid_minutes_min ≤ minutes_since_open ≤ no_entry_after…` | 시간창 |
| `hi_vol` · `stall_ok` · `reversal_ok` | `check()` 안의 **조기 반환 사슬** | 상태형 + 사슬 |
| `vwap_reverted` · `eod` | `abs(z) ≤ revert_band` · 시각 ≥ EOD | 파생 |

**사슬이 핵심이다.** `check()` 는 entry_window → 입력 유효(atr>0, price>0) → hi_vol → extreme(|z|≥1.8) →
(trend, 꺼짐) → stall → reversal → confidence 순으로 조기 반환한다. 그래서:

- `stall_ok` 는 «정체 조건»이 아니라 «앞 관문을 다 지났고 정체 조건도 참»이다. 11-10 주식 세션의 `stall_ok`
  351/351 거짓은 대부분 정체 실패가 아니라 앞 관문(hi_vol 97%, z 60%)에서 끊긴 것이다 — P1 inspect 가 지금
  보여 주는 %는 이 사슬 때문에 뒤쪽 필드일수록 부풀어 있다.
- **세 상태창(ATR 백분위 창 780, 종가 범위 창 15, 직전 종가)은 사슬이 `inputs_usable` 까지 온 바에서만 전진한다.**
  즉 창 밖 바·무효 입력 바는 창에 들어가지 않는다. 선언형이 이 «언제 표본을 넣는가»를 놓치면 hi_vol 이 다르게 나온다.
- 방향은 z 부호로 정해진다(z ≥ +1.8 → short 쪽 정체·반전 조건, z ≤ −1.8 → long 쪽).
- 웜업 동안(ATR 창 < 120, 종가 창 < 5)은 관문이 **허용**이다(막지 않는다).
- `confidence ≥ 0.6` 관문은 필드가 아니다 — TOS 결정에는 없고 레거시 Signal 에만 있다(B3 대조의 차이 원인 후보, 이 계획 범위 밖).

## 2. 설계

### 2.1 원칙

- **카탈로그 연산은 전략 이름을 갖지 않는다.** 파라미터로만 다르다(로드맵 §5 위험 2).
- **DSL 은 그대로다**(비교·결합만). 필드 쪽에도 자유 산술식은 없다 — 연산은 이름 있는 고정 모양
  (`ratio_z`, `gated_percentile` …)이고 입력은 앞 필드 이름 참조뿐이다.
- **P2-a 는 지금 필드를 바이트 동일하게 재현한다.** 사슬도 카탈로그의 일반 불 연산(`all`·`any`·`not`)으로
  그대로 옮긴다. 사슬을 DSL 로 푸는 것(독립 필드 + R1 이 결합)은 P3 리플레이 정답이 생긴 뒤의 tenant 변경이다.
  이유: 생산자 교체와 의미 변경을 한 번에 하면 결정이 달라졌을 때 어느 쪽 탓인지 못 가른다.

### 2.2 `fields.yaml` (tenant 트리마다)

```yaml
schema: tos-fields/1
catalog: tos-field-catalog/1          # 카탈로그 버전 고정 — 다르면 부팅 거부
fields:                               # 순서 = 평가 순서. 참조는 앞 필드만
  - {name: close,   op: bar.close}
  - {name: vwap,    op: session.vwap_typical}
  - {name: atr,     op: atr, params: {period: 14}}
  - {name: mso,     op: session.minutes_since_open}
  - {name: entry_window, op: between, inputs: [mso], params: {lo: 15, hi: 345}}
  - {name: usable,  op: all, inputs: [entry_window, atr_pos, close_pos]}
  - {name: vol_ref, op: gated_percentile, inputs: [atr], params: {q: 90, window: 780, warmup: 120, sample_when: usable}}
  - {name: hi_vol,  op: all, inputs: [usable, vol_ok]}
  # … stall_ok, reversal_ok 도 같은 모양
publish:                              # 저널로 나가는 필드와 스케일 (FIELD_ORDER 와 같은 순서)
  - {field: close,  as: close_x100, scale: {mult: 100, round: half_up}}
  - {field: z,      as: z_x1000,    scale: {mult: 1000, round: toward_zero}}
  - {field: hi_vol, as: hi_vol}
```

- 파라미터 값의 정본은 지금처럼 `config/strategies/futures/setup_d_vwap_reversion.yaml` 이 아니라 **이 파일**이 된다
  (P2-c 에서). P2-a/b 동안은 동등성 비교를 위해 두 곳이 같은 값이어야 하고, 테스트가 그것을 고정한다.
- 거부(부팅·생산자 시작 시): 모르는 op · 카탈로그 버전 불일치 · 앞에 없는 입력 참조 · 순환 · publish 가 없는 필드
  지목 · **전략 DSL 이 참조하는 `capsule.resolved_values.*` 가 publish 에 없음**(기존 `resolve.py` 바인딩 거부 자리).

### 2.3 카탈로그 `tos-field-catalog/1` (첫 판)

| op | 뜻 | 상태 |
| --- | --- | --- |
| `bar.open/high/low/close/volume` · `session.token` | 분봉 원값 | – |
| `session.vwap_typical` · `atr` · `session.minutes_since_open` | `MarketContextReplay` 와 같은 정의 — **그 계산을 재사용**하고 다시 쓰지 않는다 | 창 |
| `ratio_z(a,b,c)` | (a−b)/c | – |
| `abs` · `gt/ge/le/lt(a, b \| const, mult?)` · `between` · `time_ge` | 비교 | – |
| `all` · `any` · `not` | 불 결합 | – |
| `gated_percentile(x; q, window, warmup, sample_when)` | 과거 표본의 q 백분위, 현재 바는 읽은 **뒤** 넣는다, 웜업이면 `None` | 상태 |
| `gated_max/min(x; window, warmup, sample_when)` | 같은 규칙의 최대/최소 | 상태 |
| `gated_lag(x; sample_when)` | 마지막 표본(현재 바 제외) | 상태 |
| `permissive(cond, when_missing=true)` | 웜업(`None`) 이면 참 | – |

상태 연산은 **«읽고 나서 넣는다»(엄격 인과)** 와 `sample_when` 을 하나의 기반 클래스가 강제한다 — 연산마다
따로 구현하지 않는다. `None` 은 «아직 값 없음»이며 비교에 들어가면 거짓이 아니라 `permissive` 가 아닌 한 거부된다.

위치: `shared/indicators/fields/` (순수 — `shared.indicators` 는 `tos` 가 import 할 수 있는 비준 패키지라
나중에 커널 쪽 생산자도 쓸 수 있다). 지표 엔진 `shared/indicators/engine` 의 창 지표가 있으면 그것을 백엔드로 쓴다.

### 2.4 동등성 — 이식의 정답 (P2-b)

- 같은 Parquet 구간을 **레거시 구동 `produce_bars`** 와 **선언형 생산자** 둘로 돌려 `FieldRecord` 열을 비교한다.
  비교 단위는 **바 × publish 필드, 바이트 동일**(스케일 정수·불). 생략된 바(`_inputs_unusable`) 목록도 같아야 한다.
- 구간: 세 트리(LONG A056xx · SHORT · STOCK 005930) 각각 저장소에 있는 데이터로 **20 거래일 이상**, 롤과 스티치
  경계를 하나 이상 포함.
- 불일치는 «필드 · 첫 바 · 두 값 · 레거시 `last_eval` 키»로 보고한다. 근사(허용오차)로 넘기지 않는다 — 부동소수
  순서 차이면 레거시와 같은 연산 순서로 고친다.
- 이 비교는 레거시를 **읽기만** 한다. B3 증인 바이트 동결(`TOS_PAPER_READY` 까지)과 충돌하지 않는다.

## 3. 단계

| 단계 | 내용 | 등급 | 언제 |
| --- | --- | --- | --- |
| **P2-a** | 카탈로그 `shared/indicators/fields/` · `fields.yaml` 스키마·로더·거부 · 평가기 · 카탈로그 단위 정답 테스트(손계산·look-ahead 금지·결정성) | B | 지금 |
| **P2-b** | Setup D 세 트리의 `fields.yaml` 작성 · 동등성 하네스 `tools/tos_cp3/fields_equivalence.py` · 20일 전 필드 일치 | B | P2-a 뒤 |
| **P2-c** | 생산자 전환: `produce_fields.py` 가 `fields.yaml` 만 읽는다(로딩·스티치·lineage 는 그대로) · 저널 바이트 동일을 하루 그림자 실행으로 확인 · 레거시 `SetupDVWAPReversion` import 제거 | B (생산 경로) | **`TOS_PAPER_READY` 선언 뒤**, P2-b 통과 뒤 |
| **P2-d** | 두 번째 전략: 주식 RSI/Williams %R 되돌림 — `config/` 만 추가(카탈로그에 `rsi`·`williams_r` 가 없으면 P2-a 카탈로그 PR 로 먼저) · MOCK 세션 부팅 | B | P2-c 뒤 |

P2-c 를 `TOS_PAPER_READY` 뒤로 미루는 이유: 그 전에는 매일 아침 CP-3 세션이 깨끗한 날 누적을 세고 있다.
생산자 교체가 그 셈을 깨뜨릴 위험을 감수할 이유가 없다 — 동등성이 이미 증명돼 있으면 하루 미뤄도 잃을 것이 없다.

## 4. 하지 않는 것

- DSL 확장(산술식·함수). 필드에도 자유 식 없음 — 필요한 계산은 이름 있는 카탈로그 op 로.
- 사슬 해체(독립 `stall_long_ok` 같은 필드 + R1 결합) — P3 리플레이 정답 뒤의 tenant 변경.
- `confidence` 관문 이식 — 지금 TOS 결정에 없는 것을 이 계획이 추가하지 않는다. 필요하면 별도 운영자 결정.
- 레거시 `shared/decision/setups/vwap_reversion.py` · `shared/backtest/market_context_replay.py` 수정(B3 동결).

## 5. 완료 (로드맵 §P2 완료의 측정 문장)

1. 세 트리의 `fields.yaml` 생산자가 20 거래일에서 레거시 구동과 **전 바 × 전 필드 바이트 동일**(하네스 출력 1표).
2. P2-c 뒤 첫 세션의 저널이 전날 그림자 실행 결과와 바이트 동일, `produce_fields.py` 에 `SetupDVWAPReversion` import 0.
3. 두 번째 전략이 `git diff --stat` 상 `config/` 만 바꾸고 MOCK 세션이 부팅한다.

## 6. 위험

| 위험 | 대응 |
| --- | --- |
| `sample_when` 의미 차이로 hi_vol 이 웜업 직후부터 갈린다 | P2-b 가 첫 불일치 바와 `last_eval` 키를 보여 준다. 기반 클래스 하나라 고칠 곳도 하나 |
| `np.percentile` 보간·부동소수 순서 | 같은 함수·같은 입력 순서로 계산. 허용오차 금지 |
| 카탈로그가 Setup D 전용 op 로 부푼다 | op 이름에 전략명 금지, 리뷰에서 확인. 표 2.3 밖의 op 는 실제 두 번째 사용처와 함께만 추가 |
| 파라미터가 두 곳(전략 YAML · fields.yaml)에 있는 동안 어긋남 | P2-a/b 동안 두 값 일치 테스트. P2-c 에서 정본을 fields.yaml 로 옮긴다 |
