# KRX 주식 호가단위 표 — 실측 경로 설계 + 핸드오버 (W-B B-3)

- 작성: 2026-09-26 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `d209d279`
- 상위: `docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md` §4 W-B B-3
  (「② tick 표 실측 경로 설계. GET-only 로 `FHKST01010100::output.aspr_unit` 을 가격대별로 수집하는
  프로브 설계 + 핸드오버 문서. **실행은 운영자**」).
- 종료조건(상위 계획 그대로): 어느 종목 · 어느 가격대를 몇 건 찍어야 표가 되는지가 **수치로** 적혀
  있음 · GET-only 준수 · 배포 값은 여전히 `null`.
- 성격: **설계 문서다. 코드는 넣지 않았다.** 프로브 구현(§5)은 운영자가 실행 일정을 잡을 때 함께 착지한다.

## 0. 한 줄 요약

`VenueShapeConstraints.price_band_ticks`(커널 round #4 K-1, `tos/src/tos/venue/records.py:114-159`)는
**형상만** 있고 값은 없다. 값의 원천은 브로커 응답 `output.aspr_unit` 하나뿐이고, 실측은 지금 **한
점**(005930 · 232,500원 → 500, `P-11-20260730T002715Z.json`)이다. 이 문서는 그 한 점을 **7개 가격대
× 2개 시장 표**로 넓히는 GET-only 수집 절차와 합격 판정을 수치로 정한다. 공표된 호가단위 개편안은
**어떤 후보를 고를지 정하는 가설**로만 쓰고, 표의 값으로는 쓰지 않는다.

## 1. 지금 있는 것 (실측)

| 무엇 | 어디 | 상태 |
|---|---|---|
| 표 형상 | `PriceBandTick(band_min, band_max, tick)` — 양끝 포함, 행 비연속·비망라 허용, 범위 밖 가격은 **해석 불가**(외삽 없음) | 착지(K-1) |
| 술어 | `order_shape_admissible` — 표 우선 → 평탄 `tick_size` 폴백 → 둘 다 없으면 `UNKNOWN` (`tos/src/tos/venue/predicates.py:224-233`) | 착지 |
| 실측 1점 | `P-11-20260730T002715Z.json` → `measurements.limit_price_tick`: `wire_value "232500"` · `tick_size "500"` · `tick_source` = TR `FHKST01010100` `output.aspr_unit='500'` | 테스트 픽스처로만 사용 (`tos/tests/venue/_venue_strategies.py::MEASURED_KRX_PRICE_BAND_ROW`) |
| 호출 수단 | `probes_order.py` `stock_quote()`(:846-867) → `_stock_tick()`(:658-695): `FID_COND_MRKT_DIV_CODE=J` · `FID_INPUT_ISCD=<종목>` · 모의 호스트 · `aspr_unit` 이 없거나 ≤0 이거나 소수면 `ProbeError` | 한 번에 **한 종목** — 여러 종목을 도는 프로브는 없다 |
| 속도 | `DEFAULT_PACE_S = 1.1` (`probes_order.py:201-208`, P-13 실측: 모의 조회 1.0 rps 정상 · 2.0 rps `EGW00201`) | 재사용 |

배포 쪽은 영향이 없다: 현 paper 배포의 venue 는 **KRX 지수선물**(`config/tos_runtime/paper/venue_constraint_policy.yaml`
— 평탄 `tick_size: 5`, 등급 C)이고, 주식 venue 는 아직 배포돼 있지 않다. 이 표는 **주식 venue 가 생길 때**
쓰일 값의 원천이다. 선물 tick 은 상품별 상수라 이 문서의 대상이 아니다.

## 2. 가설 — 후보를 고르는 데만 쓴다

2023-01-25 KRX 신시장시스템(EXTURE3.0) 가동과 함께 시행된 호가가격단위 개편(공표 2022-11, 보도 기준 —
공식 규정 원문 대조는 하지 않았다). 코스피·코스닥 공통:

| 밴드 | 가격 구간(원) | 가설 호가단위 |
|---|---|---|
| B1 | 1 ~ 1,999 | 1 |
| B2 | 2,000 ~ 4,999 | 5 |
| B3 | 5,000 ~ 19,999 | 10 |
| B4 | 20,000 ~ 49,999 | 50 |
| B5 | 50,000 ~ 199,999 | 100 |
| B6 | 200,000 ~ 499,999 | 500 |
| B7 | 500,000 ~ | 1,000 |

실측 1점(232,500 → 500)은 B6 가설과 **정합**한다. 그 이상은 아무것도 말하지 않는다.

**이 표는 값의 원천이 아니다.** 보도 요약은 등급이 없고, 경계 포함 여부(2,000원이 B1 인지 B2 인지)는
공표문 요약에서 확정되지 않는다. 표의 값은 §4 의 판정을 통과한 **관측**만으로 만든다.

## 3. 수집 설계 — 몇 종목 · 몇 번

### 3.1 대상

- **보통주만.** ETF · ETN · ELW · 리츠 등은 호가단위 체계가 다를 수 있어 제외한다(섞이면 밴드 판정이 오염된다).
- 시장 2개: 코스피 · 코스닥. `FID_COND_MRKT_DIV_CODE=J` 는 둘 다 조회하므로 시장은 **운영자의 후보 목록**이
  정한다(응답 필드에서 시장을 파생하지 않는다 — 파생 규칙을 지어내지 않기 위해).
- **밴드 배정은 관측 가격(`output.stck_prpr`)으로 한다.** 후보 목록은 가설 밴드로 짜지만, 호출 시점 가격이
  다른 밴드로 넘어갔으면 그 관측은 **넘어간 밴드**의 표본이다.

### 3.2 표본 수

| 구분 | 수 | 근거 |
|---|---|---|
| 밴드 내부 | **7 밴드 × 2 시장 × 3 종목 = 42 호출** | 밴드당 시장별 3종목 — 1종목은 우연, 2종목은 불일치 시 판정 불가, 3종목이면 한 종목의 이상치를 드러낸다 |
| 경계 근처 | **6 경계 × 2 방향 × 1 종목 = 최대 12 호출** | 경계 바로 아래·위(가설 호가단위로 **3틱 이내**) 종목. 그날 그런 종목이 없으면 **미수집으로 기록**하고 억지로 채우지 않는다 |
| 합계 | **최대 54 호출** + 토큰 1회 | 1.1 s 간격 → **약 60 초** |
| 반복 | 종목당 **1회** | `aspr_unit` 은 가격의 함수다. 같은 종목 반복은 표본 수를 부풀릴 뿐 정보가 없다 |

B7(≥500,000원)은 코스닥에 해당 종목이 드물 수 있다. 없으면 **코스닥 B7 = 미수집**이다.

### 3.3 언제 · 어디서

- **정규장(09:00~15:30 KST)** 중 1회. 장외에는 `stck_prpr` 가 직전 종가라 밴드 배정 자체는 유효하지만,
  가격이 움직이는 장중이 경계 근처 표본을 구하기 쉽다.
- **1단계 = 모의 호스트**(`openapivts…:29443`, `assert_mock_host`). P-11·P-16 이 모의에서 실제 시세 본문을
  받았다(t2 캠페인 README). 주문 경로 없음 · `emits_orders=False`.
- **2단계(선택) = 실 호스트 GET 교차확인**: 밴드당 1종목 = **7 호출**. 모의의 `aspr_unit` 이 실 도메인과
  같은지 확인한다. 루트 `CLAUDE.md` 가 「GET-only real reads are fine」로 허용하는 범주다. 다만
  `probes_real.ALLOWLIST`(`probes_real.py:69-100`)에 `FHKST01010100` 이 **없으므로** 허용목록 추가가 선행돼야
  하고, 그건 이 문서의 결정이 아니라 운영자 승인 사안이다.

## 4. 판정 — 무엇이 표가 되는가

관측 하나 = `(종목, 시장, stck_prpr, aspr_unit)`.

1. **자기 정합**: `stck_prpr` 가 `aspr_unit` 의 배수가 아니면 그 관측은 **폐기**하고 사유를 남긴다
   (가격과 호가단위가 서로 맞지 않는 응답은 어느 쪽도 믿을 수 없다).
2. **밴드 MEASURED**: 한 (밴드, 시장)에 자기 정합 관측이 **3건 이상**이고 `aspr_unit` 이 **전부 같다**.
3. **밴드 CONFLICTED**: 같은 (밴드, 시장) 안에서 `aspr_unit` 이 둘 이상 → 승격 금지. 가설 밴드 경계가
   틀렸다는 신호일 수 있으므로 경계 근처 표본과 함께 보고한다.
4. **밴드 PARTIAL**: 관측 1~2건 → 승격 금지, 값은 기록만.
5. **경계**: 경계 아래·위 표본이 각각 이웃 밴드의 MEASURED 값과 같으면 「경계 정합」. **정확히 경계 가격**의
   관측이 있을 때만 포함 여부를 확정한다 — 없으면 행의 `band_min`/`band_max` 는 **관측된 가격 범위의 안쪽**으로
   잡는다(표가 모르는 구간은 표 밖에 둔다 — `PriceBandTick` 의 「비망라 허용 · 외삽 없음」 그대로).
6. **최상단(B7)**: 상한이 없지만 `band_max` 는 정수여야 한다. **관측된 최고가**로 닫는다. 그 위는 해석 불가.

코스피·코스닥이 같은 밴드에서 같은 값이면 한 행으로 합칠 수 있다. 다르면 시장별 표 두 개다.

## 5. 프로브 명세 (구현은 실행 일정과 함께)

`tools/broker_probes/registry.py` 의 `ProbeSpec` 에 한 항목:

| 필드 | 값 |
|---|---|
| `probe_id` | `P-TICK` |
| `kind` / `environment` | `QUERY` / `ENV_MOCK` (2단계는 `--env real` 에서 `REAL_READ_ONLY` — N-17/P-BAL 의 환경 재정의 선례, `registry.py:735-780`) |
| `risk` / `emits_orders` / `requires_confirm` | `LOW` / `False` / `True` |
| `entrypoint` | `probes_query:probe_tick_table` (모듈은 `run.py:33-41` `_ARG_ADDERS` 에 이미 있음) |
| 인자 | `--candidates FILE` — `symbol,market,hypothesis_band` CSV. 운영자가 만든다(§3.1). `--samples` 는 쓰지 않는다 |
| 재사용 | `stock_quote()` / `_stock_tick()` 그대로(`aspr_unit` 부재·비정상 = `ProbeError` 도 그대로) · `_CallPacer(1.1 s)` |
| 아티팩트 `measurements` | `tick_observations[]`: `symbol` · `market` · `hypothesis_band` · `stck_prpr` · `aspr_unit` · `self_consistent` · `discard_reason` / `tick_table[]`: `market` · `band_min` · `band_max` · `tick` · `n` · `verdict`(MEASURED/CONFLICTED/PARTIAL) / `coverage`: 밴드×시장 16칸의 판정과 미수집 칸 목록 |

## 6. 핸드오버 — 운영자가 할 일

1. 보통주 후보 CSV 작성: 밴드마다 시장별 **5종목**(3종목 판정 + 가격 이동 여유 2) + 경계마다 위·아래 1종목씩.
   → 최대 **7×2×5 + 12 = 82 후보**, 호출은 §3.2 상한(54) 이하로 끊는다.
2. 정규장 중 `python -m tools.broker_probes.run P-TICK --confirm --candidates <CSV>` (구현 착지 후).
3. 아티팩트를 캠페인 디렉터리에 커밋하고, README 의 값은 **`CITATION-RULE.md` 형식**으로 적는다 —
   예: `` `P-TICK-…Z.json:measurements.tick_table[5].tick=500` ``. `tools/tos_evidence_citation_check.py` 가
   통과해야 한다.
4. 표를 배포 값으로 올릴지는 **별도 제안표**(OCP sizing 제안표 2026-09-16 형식)로 결정한다. 이 문서도, 프로브
   실행도 배포 값을 바꾸지 않는다 — `venue_constraint_policy` 의 가격 관련 값은 여전히 `null`/등급 C 그대로다.

## 7. 기각한 대안

| 대안 | 기각 이유 |
|---|---|
| 공표 개편안을 그대로 표로 배포 | 원천 등급 없음 · 경계 포함 여부 미확정 · 「브로커가 실제로 무엇을 요구하는가」를 측정하지 않음 |
| 한 종목의 가격이 밴드를 지나기를 기다려 반복 조회 | 하루에 밴드를 넘는 종목은 드물고 결과가 날씨에 달림 — 종목을 여러 개 고르는 쪽이 결정적 |
| 주문(지정가) 거부로 호가단위를 역추적 | 주문 경로 — GET-only 위반. 모의라도 이 목적에 주문을 쓰지 않는다 |
| 가설 밴드로 관측을 배정 | 호출 시점 가격이 밴드를 넘었으면 틀린 칸에 들어간다 — 관측 가격으로 배정한다 |
