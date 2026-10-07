# CP-3 결정 9 — venue 수량 상한의 출처(KRX 규정) + 모의 GET 보강 프로브 설계 + band 원천 웨이브 분리

- 작성: 2026-10-08 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `a9aa6037` · v2 (리뷰 처분 — v1 은
  **코스피200선물(full, `101xxxx`) 행**을 읽었다; 배포·tenant 상품은 **미니코스피200선물(`A056xx`)** 이다, §2.0)
- 상위: `docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md` §4 결정 9 — 10-07 권고(모의 GET 프로브가 출처)는 §4.3 에서
  **불가**로 판정됐고, **운영자 선택 2026-10-08 (a) 「KRX 규정 문서를 1차 출처로, 모의 GET 은 보강」이 그 권고를 대체**한다 ·
  `docs/plans/2026-09-15-tos-venue-constraint-service-plan.md` §6 ⑤(「band/**tradability** 원천 웨이브 — broker 조회 vs
  marketfeed 기준가」로 유보돼 있던 자리; 이 문서는 그중 **band 와 수량 상한**만 다루고 tradability 는 §6 끝에 열린 채로 둔다).
- 종료조건: ① `max_quantity` 값과 그 조문·개정일·재현 경로가 적혀 있고 ② 프로브가 **무엇을 닫고 무엇을 못 닫는지**가
  레그별로 적혀 있으며 ③ 「결정 9 만으로는 paper 가 송신에 도달하지 않는다」는 사실과 그 다음 결정(§6)이 분리돼 있다.
- 성격: **설계 문서다. 코드와 배포 값은 넣지 않았다.** 프로브 구현(§4)·증거 README·정책 값 착지는 각각 별도 PR.

## 0. 한 줄 요약

paper venue 정책의 `max_quantity: null` 은 「출처 없음」의 fail-closed 상태였고(§1), 그 출처는 **KRX 파생상품시장 업무규정
제71조 → 시행세칙 제61조제1항 → 별표 17의2** 의 「**미니코스피200선물거래 정규거래 10,000 계약**」이다(§2, 원문 확보; 같은
별표의 코스피200선물거래 행은 2,000 이며 parity 데이터셋 `101S6000` 에만 해당). 모의 계좌 GET(`VTTO5105R`)은 **예수금·파라미터
파생값**이라 이 상한을 줄 수 없고, 보강으로 쓸 수 있는 것은 「주문가능수량 ≥ 1」과 「가격제한폭 응답이 규정 산식과 일치」뿐이다
(§4). 한편 `price_min/price_max` 는 **일별 동적 값**이라 정책 YAML 의 정적 리터럴이 될 수 없고 런타임에 원천 경로가 없으므로,
결정 9 를 닫아도 `order_shape_admissible` 는 UNKNOWN 으로 남는다 — 그 해소는 §6 의 별도 결정이다. 부수 발견: 배포 정책의
`tick_size: 5`(0.05) 는 mini 의 규정 호가가격단위 0.02 와 **다르다**(§2.0 ⚠).

## 1. 지금 있는 것 (실측, main `a9aa6037`)

| 무엇 | 어디 | 상태 |
|---|---|---|
| 배포 상품 | `config/tos_runtime/paper/calendar.yaml:3-13` 「배포 상품이 KOSPI200 **mini** … 실측 2026-09-24 front=A05610」 · kickoff §4 결정 2 「paper tenant 는 상주와 같은 mini `A056xx`」 · 상주 잎 `~/.local/state/tos/paper-data/A05610/` · `config/execution.yaml:284-289` `kospi200_mini` 승수 50,000 · 틱 **0.02** · 접두 `A05` | parity 데이터셋만 full `101S6000`(결정 2) |
| 배포 값 | `config/tos_runtime/paper/venue_constraint_policy.yaml:121-127` — `price_min/price_max: null` · `tick_size: 5` · `lot_size/min_quantity: 1` · `max_quantity: null`; 헤더 17-25행 「NO SOURCE … Never fill by hand」, 12행 「`tick_size_points: 0.02`/`0.05` — a LOCAL setting, grade C」 | 의도된 fail-closed · ⚠ tick 5 는 두 값 중 full 의 것 |
| 핀 | `tos/runtime/tests/compose/test_deploy_policies.py:207-209, 294` — **paper 트리**(`:63 _DEPLOY_DIR = …/paper`)의 세 null 단언 · `:168-173` 헤더 provenance 문자열 단언(`§6 ②`·`DR-0002`·`2026-09-16`) | tenant 트리에 값을 넣는 PR 은 paper 단언을 **건드리지 않고** tenant 케이스를 **추가**한다(§8 5); paper 에 값을 넣는 PR 만 이 단언을 바꾼다 |
| 로더 | `tos/runtime/src/tos_runtime/venue/_venue_policy_loader.py:300-318` — 각 bound 는 **int 또는 null** 만, 값별 `source:` 필드 없음(출처는 헤더 주석 + 정책 `evidence:` 블록) | 정수 스케일: 가격 ×100, 수량은 계약 수 |
| 소비 1 — 수량 | `tos/src/tos/egressgw/construction.py:457-463` — `max_quantity is None` → `DENIED "the venue / broker quantity constraint is incomplete"` (step 2 = `CANDIDATE_COMMAND_CONSTRUCTION`, `test_deploy_policies.py:288-290`) | 10-07 세션 evidence store(`~/.local/state/tos/paper-data/A05610/evidence.sqlite3`, `entries.payload_json`, 읽기 전용 집계 2026-10-08) 에 그 사유 문자열을 담은 행 **2,510**(kickoff §4 행 9 의 「2,510건」과 정확히 일치) · `STAGE_DENIED`/`CANDIDATE_COMMAND_CONSTRUCTION` 행 **5,020** · 세션 전체 72,103 행 — 거부 행 2 : 사유 행 1 의 비는 제안당 두 행(결정 + 증거)으로 보이나 **매핑은 §8 3 의 재집계에서 확정** |
| 소비 2 — 형상 | `tos/src/tos/venue/predicates.py:282-291` — `price_min`·`price_max`·`max_quantity`(및 price/lot/min) 중 **하나라도** null → `UNKNOWN`; `:308-309` band 밖 → INADMISSIBLE; `:310-315` 틱 불일치 → INADMISSIBLE; `:319` 수량 > max → INADMISSIBLE | ⚠ `max_quantity` 만 채우면 step 2 는 열리지만 step 3 는 band null 로 UNKNOWN 유지 · band 가 생기는 순간 **tick 5 vs 0.02** 가 mini 정상 호가를 INADMISSIBLE 로 만든다(§2.0) |
| 원천 경로 | `tos/runtime/src/tos_runtime/venue/service.py:196-199` 부팅 시 YAML 에서 고정 · `:262-274` 스냅샷의 `critical_input_snapshot_digest/source_continuity_id/max_age` 는 **None 으로 전달**(`:88-92` 「no Phase-1 source」) · marketfeed·broker 조회에서 band 를 채우는 코드 **0** | spec 은 band 를 Critical Input 사실로 봄(ADR-002-019 §9) — 런타임 미구현 |
| 하네스 — 실전 전용 레그 | `tools/broker_probes/probes_real_order.py:1092-1097` `PreflightClient.get` 이 `REAL_BASE_URL` + `assert_real_host` 로 **실전 호스트 고정**; `TTTO5105R`(`:181`)·`FHMIF10000000`(`:151`) 레그와 band 읽기(`:1717-1718`) · `_corroborate_tick`(`:1444-1471`, 순수 함수) · `resolve_smallest_contract`(`:718-780`, 네트워크 없음이나 `config/execution.yaml` 을 읽고 abort 사유가 「real-money probe」 전제) | 모의로 **그대로 못 씀**. ⛔ 이 모듈은 유일한 주문 가능 모듈이라 GET-only 모듈이 **import 하면 안 된다**(`tests/tools/test_broker_probes_real_order.py:312-320` · `test_broker_probes_ca.py:265-273` 카나리) → `_corroborate_tick` 은 중립 모듈로 **이전**(§4) |
| 하네스 — 모의 레그 | `tools/broker_probes/probes_query.py:212-219` P-16 이 모의 호스트로 `FHMIF10000000` 을 치지만 **시계 필드만** 기록 · 페이싱 `probes_order.py:236-242` `DEFAULT_PACE_S = 1.1`(P-13 `P-13-20260729T063120Z` 실측 1.0 rps 정상 / 2.0 rps `EGW00201`) | 가격 필드 기록 없음 |
| 공식 TR 표 | KIS `examples_llm/domestic_futureoption/inquire_psbl_order/inquire_psbl_order.py` — `real: TTTO5105R` / `demo: VTTO5105R`, 필수 파라미터 `CANO/ACNT_PRDT_CD(03)/PDNO/SLL_BUY_DVSN_CD/UNIT_PRICE/ORD_DVSN_CD`; `inquire_price/inquire_price.py` — `FHMIF10000000` 실전·모의 동일 | `VTTO5105R` 은 레포에 아직 없음 |
| P0-2 미결 | `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:2364, 4427` `price_band_tick_lot_and_quantity_semantics: UNKNOWN` · `:2426-2430` 「로컬 설정에서 온 틱 값은 UNKNOWN 유지」 | 이 문서의 프로브가 **부분** 해소(§5) |

## 2. 1차 출처 — KRX 규정 (원문 확보 2026-10-08)

### 2.0 어느 상품의 행인가 — mini

배포·tenant 상품은 **미니코스피200선물(`A056xx`)** 이다(§1 첫 행). 별표 17의2·시행세칙 제4조의8·제4조의9 는 코스피200선물과
미니코스피200선물을 **별도 호**로 적으므로 아래 값 표는 mini 행을 1차로, full 행을 parity 데이터셋(`101S6000`) 참조로 병기한다.
가격제한비율(별표 14)은 「주가지수선물거래」 한 행이라 둘에 공통이다.

⚠ **부수 발견(이 문서 범위 밖, 운영자 확인 필요):** 배포 정책 `tick_size: 5`(= 0.05) 는 full 의 호가가격단위다. mini 의 규정
값은 0.02(제4조의9제2호) 이고 레포 레지스트리도 0.02(`config/execution.yaml:286`)다. 오늘은 band null → step 3 UNKNOWN 이라
가려져 있지만, band 가 들어오는 순간(§6) `predicates.py:310-315` 가 mini 의 정상 호가(0.02 격자)를 INADMISSIBLE 로 판정한다.
처분은 §6 웨이브의 전제 항목으로 올린다(「tick 2 로 정정 + 등급 R」). 이 문서는 tick 등급을 올리지 **않는다**.

출처는 **KRX 법무포털** `https://rule.krx.co.kr/out/index.do` (`KRX규정 → 파생상품시장규정`). ⚠ `law.krx.co.kr` 은
2026-10-08 현재 응답하지 않는다(DNS 는 풀리나 HTTP/HTTPS 모두 0 바이트 타임아웃) — 인용하지 말 것. 포털은 POST 전용이라
조문별 고정 URL 이 없다 → 재현 레시피와 문서 id 로 인용한다(§2.3).

| 문서 | 판 | 포털 bookid |
|---|---|---|
| 파생상품시장 업무규정 | 제42차 일부개정 2026-04-15 규정 제2432호, 시행 2026-06-29 | `210199976` |
| 파생상품시장 업무규정 시행세칙 | **제164차 일부개정 2026-07-06 세칙 제2474호, 시행 2026-07-06** | `210228709` |

### 2.1 값 표

| 항목 | **mini (`A056xx`, 배포·tenant)** | full (`101xxxx`, parity 데이터셋만) | 조문 체인 | 최종개정 |
|---|---|---|---|---|
| **호가수량한도(1 호가당 최대 계약 수)** | **정규거래 10,000 계약** · 야간 5,000 · (유동성관리상품 지정 시 1,000/500) | 정규 2,000 · 야간 1,000 · (200/100) | 업무규정 제71조 → 시행세칙 제61조제1항 → **별표 17의2 제1호** | 별표 17의2 2025-05-29 |
| 호가수량단위 = 거래수량단위 | 1 계약 | 1 계약 | 업무규정 제9조의2제1항 → 시행세칙 제4조의5제1항·제2항 | 2014-08-28 신설 |
| 호가가격단위 | **0.02 포인트**(×100 = 2) | 0.05 포인트(×100 = 5) | 업무규정 제12조 → 시행세칙 제4조의9 제2호 / 제1호 | 2024-11-01 |
| 거래승수 | 5만 | 25만 | 시행세칙 제4조의8 제2호 / 제1호 | 2024-11-01 |
| 가격제한비율 | 1단계 8% · 2단계 15% · 3단계 20% (주가지수선물거래 공통) | 동일 | 업무규정 제70조 → 시행세칙 제56조·제56조의2 → **별표 14 제1호** | 별표 14 2025-05-29 |
| 기준가격 | **직전 거래일의 정산가격**(규정 제96조) — 전일 종가 아님; 제55조④ 로 호가가격단위에 **가장 가까운 값**(둘이면 높은 쪽)으로 조정 · 분기월 mini 는 같은 최종거래일의 코스피200선물 기준가격(제55조① 단서) | 동일 | 시행세칙 제55조제1항제2호·제4항 | 2025-05-29 |
| 상·하한가 산출 | 상한가 = 기준가격 + 기준가격×비율, **호가가격단위로 내림** · 하한가 = 기준가격 − …, **올림** | 동일 | 시행세칙 제56조제1항 본문·단서(2014-11-03) · 제2항 본문·단서(2014-08-28) | 좌동 |
| 단계 확대 | **정규거래 전용** · 개시 후 15분 경과 이후 · 기준종목이 해당 단계 상(하)한가 도달 후 5분 경과 시 상·하 **각각** 확대 · 종가단일가 시간엔 확대 없음 · 야간 및 08:45~09:00 은 1단계만 · **mini 의 비율은 코스피200선물과 동일 적용**(제2항제1호 단서) | 동일 | 시행세칙 제56조의2제2항(본문 2025-05-29) · 제2항제1호가목(2026-06-11) | 좌동 |

원문 위치(파싱 텍스트, 증거 디렉터리 §2.3): 별표 17의2 — mini 행 `byeolpyo17-2_order_quantity_limits.txt:41-45`
(「미니코스피200선물거래 / 정규거래: 10,000(1,000)계약, / 야간거래: 5,000(500)계약」), full 행 `:29-33`, 괄호 의미 비고 `:118`.
별표 14 — `byeolpyo14_price_limit_ratios.txt:19-25` (「주가지수선물거래 — 1단계: 8%, 2단계: 15%, 3단계: 20%」). 조문 본문 —
`derivatives_enforcement_rule_164th_20260706.txt` (제4조의5 `:779-781` · 제4조의8 `:838-841` · 제4조의9 `:851-854`).

⚠ 웹 검색 요약에 흔한 「코스피200선물 호가수량한도 1,000(야간 500)」은 **별표 17의2 의 코스닥150/국채/금/돈육 행**(`:23-27`)을
잘못 읽은 것이고, v1 의 2,000 은 **full 행을 mini 상품에 붙인** 오독이었다. 2차 요약을 값의 출처로 쓰지 않고, 행은 상품 이름으로
고른다.

### 2.2 정책 파일에 적을 때 반드시 같이 적는 세 가지 단서

1. **회원(증권사)은 이보다 낮게 정할 수 있다** — 시행세칙 제61조제3항 「회원은 제1항에도 불구하고 제1항에 따른 수량 이내로
   호가수량한도 … 를 정할 수 있다」. 10,000 은 **상한**이지 KIS 가 받아 준다는 보장이 아니다. KIS 측 한도는 GET 으로 관측
   불가(§4.3) → 값 옆에 「venue 상한 · broker 한도 미확인」으로 적는다.
2. **거래소가 시장관리상 변경할 수 있다** — 제61조제1항 단서 · 제56조제3항. 값은 「공표 규정값」이지 불변식이 아니다.
3. **누적호가수량한도는 다른 한도**(제61조제2항: 회원 자기거래계좌·사후위탁증거금계좌 한정) — 위탁계좌인 paper/모의에는
   적용되지 않는다. 정책에 넣지 않는다.

### 2.3 증거 보존

- 호스트: `~/.local/state/tos/measure/krx-rules-20261008/` — 별표 17의2 HWP `sha256 3fed6e68…2d71d`, 별표 14 HWP
  `sha256 a3c75362…2648`, 시행세칙 제164차·업무규정 제42차 전문 텍스트, 파서 `hwpread.py`(순수 표준 라이브러리, 조사용).
- 레포: `docs/broker-profiles/evidence/2026-10-08-krx-venue-limits/` 에 두 별표의 **파싱 텍스트**와 **시행세칙 제164차 전문
  텍스트**(조문 체인의 근거) + README(판·bookid·sha256·조문 체인·재현). HWP 바이너리는 커밋하지 않고 sha256 으로 결속한다.
- 재현(법무포털): `GET /out/index.do` 로 세션+CSRF → `POST /out/sch/outsearch.do` (`stxt=호가수량한도`) → `POST
  /out/regulation/regulationViewPop.do` (`bookid=210228709`) → `POST /login/getData.do` 로 다운로드 토큰 →
  `POST /Download.do` (`Serverfile=210064641.hwp` = 별표 17의2, `210064610.hwp` = 별표 14, `210217359.hwp` = 별표 25).

### 2.4 2026-09-26 틱 표 설계와의 관계 (「공표 규정은 가설로만」)

`docs/plans/2026-09-26-tos-stock-tick-table-probe-design.md` §0/§7 은 공표된 호가단위 개편안을 **후보 선택 가설**로만 쓰고 값은
관측으로만 만든다고 정했다(기각 사유 셋: 원천 등급 없음 · 경계 포함 여부 미확정 · 「브로커가 실제로 무엇을 요구하는가」 미측정).
이 문서는 그 반대 방향이므로 어디가 다른지 적는다.

- 앞의 둘은 여기서 **해소**된다: 09-26 의 가설은 보도 요약(「공식 규정 원문 대조는 하지 않았다」)이었고, 여기는 현행 시행세칙 원문
  ·조문 체인·개정일·sha256 결속 별표다. 또 `aspr_unit` 은 가격대별 **브로커 표면 관측값**이지만 호가수량한도는 상품별 **공표
  상수**라, 관측으로 표를 만드는 절차 자체가 성립하지 않는다(§4.3).
- 셋째는 **살아남는다**: 제61조제3항 때문에 10,000 은 venue 상한이지 KIS 가 받는 값이 아니다. 그래서 값은 §2.2 ① 단서와
  **반드시** 함께 적고, KIS 측 확인은 §7 ④ 의 별도 선택지로 남긴다. 09-26 의 원칙을 폐기하는 것이 아니라 적용 대상이 다르다.

## 3. 값 제안 (운영자 채택 대상 — 캘린더·09-15 계획 §6 ② 표와 같은 절차)

| 키 | 제안값 | 출처·등급 | 어디에 |
|---|---|---|---|
| `max_quantity` | **10000** (mini) | 별표 17의2 제1호 미니코스피200선물거래 행 + 단서 §2.2 ① · 등급 **R**(공표 규정 원문 — `docs/plans/2026-09-12-tos-operator-value-proposals.md:4` 의 A/B/C/M 어휘에 없던 종류이므로 새로 적는다; B「공식 SDK·런북·측정」과 구분) | CP-3 tenant 트리(결정 3) `venue_constraint_policy.yaml`; paper 트리는 별도 채택(digest 재렌더 → `safety_activation.yaml::members` 수동, 09-15 계획 §6 ③) |
| `min_quantity`/`lot_size` | 1/1 (변경 없음) | 조문 인용 추가(제4조의5) | 헤더 주석만 |
| `tick_size` | **변경 없음(5)** — 단, mini 규정값 2 와 불일치를 §6 전제로 등재 | §2.0 ⚠ · 등급 승격 **없음** | §6 |
| `price_min`/`price_max` | **null 유지** | 일별 동적 값 — 정적 리터럴 금지(§6) | — |
| 비율 `[8, 15, 20]`% · 기준가격 규칙(제55조④ 포함) · 내림/올림 | §6 웨이브의 **입력**으로 기록 | 별표 14 · 제55조 · 제56조 | 이 문서 §2.1 |

채택 효과(§1): step 2 의 `quantity constraint incomplete` DENIED 는 사라지고, step 3 는 band null 로 **UNKNOWN 유지** → 송신 0 은
그대로다. **결정 9 는 필요조건이지 충분조건이 아니다.** kickoff §5 4 의 범위 문장은 「결정 9 **와 §6** 이 닫히기 전엔」으로 고쳤다.

(b) 「예수금 파생값을 불일치로 선언하고 사용」을 기각하는 이유는 **값의 성질**이다: `ord_psbl_qty` 는 예수금·증거금과 그 레그의
가격·방향·주문유형 파라미터에 따라 날마다 다른 수량이고(§4.3), 정책 파일이 담는 「승인된 운영 값」(`config/tos_runtime/README.md:8-11`
— 모든 값은 승인 출처 인용과 함께)과 종류가 다르다. README 가 「공표 규정값이어야 한다」고 말하는 것은 아니다.

## 4. 프로브 설계 — `P-VL`(venue limits · GET-only · MOCK_VTS)

레지스트리 `tools/broker_probes/registry.py` 에 `kind: QUERY · environment: MOCK_VTS · emits_orders: False ·
requires_confirm: True · risk: LOW` 로 등록 — `requires_confirm` 은 P-16 과 같이 **True**(「`--confirm` gates broker contact for
every networked probe, including read-only ones」; P-13 도 True · risk MEDIUM). 새 클라이언트는 `MOCK_BASE_URL` + `assert_mock_host`
(P-16 관용구). ⛔ `probes_real_order.py` 는 **import 하지 않는다**(§1 카나리) — `_corroborate_tick`·`_decimal_field` 를 중립
모듈(`tools/broker_probes/_tick_math.py`)로 이전하고 양쪽이 거기서 import 한다. `resolve_smallest_contract` 는 쓰지 않는다
(`--symbol` 이 이미 상품을 정하고, 그 함수의 abort 전제는 실전용).

틱은 리터럴이 아니라 **레지스트리**에서: `config/execution.yaml::futures_contract_spec` 을 심볼 접두로 풀어(`A05` → 0.02,
`101`/`A01` → 0.05) 쓰고, 배포 정책의 `tick_size` 도 함께 읽어 `tick_registry_matches_policy` 를 기록한다(오늘 mini 는 **불일치**,
§2.0). 단계 비율 {8, 15, 20}% 는 별표 14 인용이 붙은 상수.

### 4.1 레그

| # | TR | 입력 | 기록(`measurements`) | 닫는 것 |
|---|---|---|---|---|
| L1 시세 | `FHMIF10000000` (`F`, `<symbol>`) | 상주 paper 세션이 쓰는 **현재 잎**의 결제월 코드(`paper-data/<종목>`, 오늘 `A05610`)를 `--symbol` 로 — 리터럴 금지 · 접두 `A05`/`101`/`A01` 외 거부 | `output1.futs_prpr · futs_prdy_clpr · futs_sdpr(기준가) · futs_mxpr · futs_llam`, `Date` 헤더, KST 시각, 08:45~09:00 창 안인지 | band 의미론(§5) · 기준가가 「전일 정산가」인지(`futs_sdpr` vs `futs_prdy_clpr`) |
| L2 규정 계산 | (네트워크 없음) | L1 의 `futs_sdpr`, 비율 0.08, 레지스트리 틱 | `expected_upper = floor_tick(sdpr×1.08)`, `expected_lower = ceil_tick(sdpr×0.92)`, 일치 여부, 단계 추정(8/15/20 중 어느 비율이 응답과 맞는지), `Decimal` 연산 | 응답 band 가 제56조 산식과 일치하는지(**1단계 창에서는 일치가 기대값**) |
| L3 주문가능 ① | `VTTO5105R` | `PDNO=<symbol>`, `SLL_BUY_DVSN_CD=02`(매수), `UNIT_PRICE=futs_prpr`, `ORD_DVSN_CD=01`(지정가) | `output.ord_psbl_qty · tot_psbl_qty · bass_idx`, `rt_cd/msg_cd/msg1` | 「모의 계좌가 1 계약 이상 주문 가능」(≥1) — **보강만**(§4.3) |
| L4 주문가능 ② | `VTTO5105R` | 같되 `UNIT_PRICE = futs_llam`(하한가) | 동일 | 하한가 **경계 포함** 여부의 공짜 증거(GET 수준 거부/수량 0 관측) |
| L5 주문가능 ③ | `VTTO5105R` | 같되 `UNIT_PRICE = futs_mxpr + 1 레지스트리 틱`(band 밖) | 동일 | GET 수준에서 band 밖 가격을 거부하는지 — `rt_cd`·`msg_cd` 를 **관측값**으로만 기록, 해석하지 않음 |

페이싱 1.1 s(`probes_order.py:236-242` `DEFAULT_PACE_S`, P-13 실측). 샘플당 호출 5 + 토큰 1; 샘플 2 → **최대 12 호출, 약 15 초**.

### 4.2 언제·어디서

- **CONTINUOUS 08:45~15:45 KST 의 거래일**(`calendar.yaml:56`). 두 번 찍는다: ① **08:50±3분**(제56조의2 — 개시 후 15분 안이라
  확대 불가, 1단계 보장 → L2 기대값 확정) ② **09:20 이후** 한 번(확대 가능 창 — 보통 여전히 1단계; 다르면 그날의 확대 사실을
  **기록**만). 두 샘플은 별도 아티팩트.
- 분리 워크트리(origin/main detached, `_common.sh guard_checkout`) · `.env.mock`(워크트리에 없으면 기본 체크아웃에서 복사,
  600 권한) · 실전 자격증명·실주문 없음.
- 상주 paper 세션(08:45 부팅)과 **같은 시간대**에 돈다. 토큰 재발급 쿨다운은 **값 미확정**(`token_reissue_min_interval_s` 등급 C,
  N-15 서버 실측 4/4 실패 — `docs/plans/2026-09-12-tos-operator-value-proposals.md:95`)이므로 보수적으로: `.env.mock` 의 앱키
  지문이 paper 세션의 키와 **다른지** 실행 전 확인하고, 같으면 09:20 샘플 하나만 찍는다.
- 아티팩트: `tools/broker_probes/results/P-VL-<UTC>.json`(gitignore) → 증거 디렉터리
  `docs/broker-profiles/evidence/2026-10-xx-cp3-venue-limits/` 에 복사 + README(인용 토큰 형식 `CITATION-RULE.md`,
  `tools/tos_evidence_citation_check.py` 가 **토큰 n>0 을 풀어야** 통과로 친다 — 0 토큰 PASS 는 증거가 아니다).

### 4.3 이 프로브가 **못 닫는** 것 (먼저 적는다)

- **KIS 측 호가수량한도.** `VTTO5105R` 의 `ord_psbl_qty` 는 공식 명세상 「주문가능수량」— 예수금·증거금과 **그 레그의 가격·방향·
  주문유형 파라미터**의 함수다(`probes_real_order.py:1651-1658` 「a 0 … could be about the parameters and not the account」).
  ⚠ 이 레포에 `ord_psbl_qty` 관측은 **아직 없다**: P-R5-PRE 08-03 은 예수금 레그(`CTRP6550R` `ord_psbl_cash/ord_psbl_tota = 0`)에서
  **그 레그 전에** ABORT 했다(`P-R5-PRE-20260803T002732Z.json`, 호스트 `tools/broker_probes/results/`). 구조 상한(10,000 또는 KIS 가
  제61조제3항으로 낮춘 값)은 **주문을 넣어 거부 코드를 받아야** 보인다. 모의 주문이면 정책상 가능하나(실전 아님) 결정 7 범위와
  이 문서의 GET-only 성격 밖 → **후속 선택지**(§7 ④).
- **2/3단계 확대의 의미론.** 확대는 기준종목의 도달 사건에 달려 있어 프로브가 일으킬 수 없다. 관측되면 기록, 아니면 미관측.
- **band 의 런타임 공급.** 프로브는 값을 관측할 뿐, 런타임에 band 를 넣는 경로는 §6 이다.

## 5. 판정

| 레그 | PASS | FAIL / 미관측 |
|---|---|---|
| L1 | `rt_cd=0`, 다섯 필드 모두 양의 소수, **레지스트리 틱** 격자 정합(`_corroborate_tick`) | 필드 누락·0·틱 불일치 → `ProbeError`, 아티팩트에 그대로 |
| L2 | ①샘플에서 `futs_mxpr == expected_upper ∧ futs_llam == expected_lower`(1단계) | 불일치 → 「기준가가 정산가가 아니거나 내림/올림 규칙이 다르다」를 **해석 아님**으로 기록, 비율 15/20 으로 재계산해 맞는 단계가 있으면 그 사실만 기록 |
| L3 | `rt_cd=0 ∧ ord_psbl_qty ≥ 1` | 0 이면 「예수금 0 · 조회 거부 · 또는 레그 파라미터 탓」으로 기록(P-CA 교훈: `held=0` 오판 금지), 상한과 무관 |
| L4·L5 | 관측만 — PASS/FAIL 없음 | `rt_cd`·`msg_cd`·수량을 그대로 |

P0-2 `price_band_tick_lot_and_quantity_semantics` 의 처분: 프로파일의 관용구는 한 단어 상태가 아니라 **자기 서술 복합 토큰**
(`:4432 DAY_AND_NIGHT_TR_SURFACE_PRESENT__OTHER_COVERAGE_UNKNOWN` 꼴)이므로, L1·L2 PASS 면
`BAND_SEMANTICS_OBSERVED_ON_MOCK__TICK_FROM_REGULATION_NOT_BROKER__QUANTITY_CAP_RULE_VALUE_BROKER_UNCONFIRMED` 처럼 **관측된 축과
안 된 축을 토큰 안에** 적는다. 프로파일 `:2426-2430` 의 기록(「로컬 설정에서 온 틱 값은 UNKNOWN 유지」)과 정합: 틱·수량 축은 여전히
broker 미확인이다.

## 6. band 원천 웨이브 — 운영자 결정 (후속, 이 문서로 열어 둠)

`price_min/price_max` 는 **매 거래일** 바뀌고 장중에도 확대될 수 있다(§2.1). 정적 정책 리터럴은 틀린 값이 되므로 금지.
spec 은 band 를 Critical Input 사실(출처·연속성·as_of·max_age 결속)로 본다(ADR-002-019 §9). 런타임에는 그 경로가 없다(§1).

**전제 항목(웨이브 시작 전):** 배포 `tick_size` 5 → mini 규정값 **2** 로 정정(§2.0 ⚠, 등급 R, 조문 제4조의9제2호). band 가
들어오면 tick 검사가 살아나므로 이 정정 없이는 mini 정상 호가가 전부 INADMISSIBLE 이다.

| 선택지 | 내용 | 장점 | 단점 |
|---|---|---|---|
| (i) broker 조회 | 세션 부팅(08:45) 직후 `FHMIF10000000` GET 1회 → 런타임이 **기존** 스냅샷 필드 `critical_input_snapshot_digest`·`source_continuity_id`·`max_age`(`service.py:88-92`, 오늘 None)를 채우고 `shape_constraints` 의 **기존** `price_min/price_max` 필드(`tos/src/tos/venue/records.py:131,152`)를 세션 단위로 재구성 — **커널 레코드 필드 추가 없음** | 확대 사실을 **그대로** 반영 · broker 증거 | 런타임 변경(venue service 가 부팅 후 1 GET · 장중 확대 반영은 재조회 주기 필요). ⚠ `VenueConstraintSnapshot` 은 **커널 레코드**(`records.py:450`)라 거기에 band 필드를 **새로** 넣는 길은 커널 변경이고 kickoff 결정 7 의 「커널 수정 → GOV-001 절차」 독법을 따른다 — 이 선택지는 그 길을 **쓰지 않는다** |
| (ii) 규정 계산 | marketfeed 의 전일 정산가 × 1단계 비율, 제55조④ 기준가격 조정 + 제56조 내림/올림 | 네트워크 없음 · 규정 기반 | 2/3단계 확대를 못 본다 → **보수적**(좁은 band) 이나 확대 시 유효 주문을 INADMISSIBLE 로 오판 · 정산가 원천(marketfeed 에 있는지) 확인 필요 |
| (iii) (i)+(ii) 상호 보강 | (ii) 를 기대값, (i) 를 관측값으로 두고 불일치면 UNKNOWN | 둘의 결함을 서로 가림 | 구현 둘 |

**권고: (i) 먼저, (ii) 는 L2 가 PASS 한 뒤 corroboration 으로.** 이유: 확대 상태는 관측으로만 알 수 있고, 프로브 L1 이 그
경로의 리허설이다. 커널 술어(`order_shape_admissible`)와 커널 레코드는 바꾸지 않는다 — 바뀌는 것은 런타임이 `constraints`
객체를 **언제 어떤 출처로** 만드는가다. 이 결정은 CP-3 §5 3 과 같은 PR 묶음이 아니라 **별도 계획 문서**로 간다.

**09-15 §6 ⑤ 의 tradability 반쪽은 이 문서 범위 밖이며 계속 열려 있다** — `venue_constraint_policy.yaml:73` 「no halt/suspension
source → action_tradability map is empty」 · `service.py:270 action_tradability=()` · 프로파일 `halt_and_suspension_semantics:
UNKNOWN`(`:2363, :4425`). 이 문서를 닫아도 ⑤ 는 닫히지 않는다.

## 7. 기각한 대안

| 대안 | 이유 |
|---|---|
| (b) `VTTO5105R` 예수금 파생값을 「불일치 선언」하고 사용 | 값이 예수금·레그 파라미터에 따라 날마다 다르고 구조 상한과 무관(§3 끝) |
| (c) null 유지 | 결정 수준 관측만 가능 — 운영자가 (a) 를 골랐다 |
| `data.krx.co.kr` 의 일별 상·하한가 수치로 대조 | 2026-10-08 현재 통계 화면이 로그인 월 뒤(`getJsonData.cmd` → `LOGOUT`) — 1차 확인 불가라 **전제로 쓰지 않음**. 규정 산식 대조(L2)가 대체 |
| ④ 모의 주문 10,001 계약으로 거부 코드 관측(KIS 한도 확인) | 가능은 하나(모의·실전 아님) GET-only 범위 밖 · 결정 7 과 별개 → 운영자가 원하면 별도 프로브(P-VL-2)로 |
| `probes_real_order.py` 레그를 모의로 돌리기 / 그 모듈을 import | `assert_real_host` 고정 — 풀면 실전 안전장치를 약화 · GET-only 카나리 위반(§1) |
| 상태를 `PARTIAL` 한 단어로 | 프로파일 어휘에 없음 — 복합 토큰(§5) |

## 8. 핸드오버 — 순서

1. **운영자**: 이 문서 승인(§3 값 표 채택 여부 · §2.0 tick 정정 · §6 선택). 승인 전엔 아무 값도 착지하지 않는다.
2. 실행 에이전트: `P-VL` 구현(레지스트리 + `probes_venue_limits.py` + `_tick_math.py` 이전 + hermetic 테스트: 레그별 레드 증명 —
   band 불일치·`ord_psbl_qty` 비정수·`rt_cd≠0`·틱 불일치 각 1건, 실전 호스트 거부 1건, **주문 가능 모듈 미import 카나리** 1건,
   `tick_registry_matches_policy` 불일치 기록 1건) → PR → 리뷰 → 머지.
3. 거래일 장중 실행(§4.2, 분리 워크트리) → 증거 디렉터리 + README(인용 토큰, n>0) → PR. 같은 PR 에 10-07 STAGE_DENIED 의
   evidence store 재집계(`STAGE_DENIED` 행 5,020 ↔ 사유 문자열 행 2,510 의 2:1 매핑)를 적는다(§1 「소비 1」 행).
4. 브로커 프로파일 초안 `price_band_tick_lot_and_quantity_semantics` 처분(§5 복합 토큰) — 같은 PR.
5. CP-3 §5 3 tenant 트리 생성 시 `max_quantity: 10000` 과 §2.2 단서·채택일·결정 id(「결정 9 (a) · 운영자 채택 YYYY-MM-DD · 별표
   17의2 제1호 미니코스피200선물거래 행 · 등급 R」)를 헤더에 적어 착지. 헤더의 「NO SOURCE … Never fill by hand」 문단은 **분리**:
   `price_min/max` 는 그대로, `max_quantity` 줄은 출처 문장으로 교체. `test_deploy_policies.py` 의 **paper 단언 3건은 그대로 두고**
   tenant 트리용 단언(10000 + 헤더 provenance 문자열 핀)을 **추가**한다. paper 트리 헤더의 같은 문단에도 「source exists
   (10-08 결정 9); paper adoption deferred by operator」 한 줄을 더한다.
6. §2.0 tick 정정 + §6 결정 → 별도 계획 문서. `CITATION-RULE.md` 에 규정 텍스트용 `파일명:행` 형식 추가(§2.3 README 의 전제).
