# CP-3 결정 9 — venue 수량 상한의 출처(KRX 규정) + 모의 GET 보강 프로브 설계 + band 원천 웨이브 분리

- 작성: 2026-10-08 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `a9aa6037`
- 상위: `docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md` §4 결정 9(운영자 선택 2026-10-08:
  **(a) KRX 규정 문서를 1차 출처로, 모의 계좌 GET 프로브는 보강**) ·
  `docs/plans/2026-09-15-tos-venue-constraint-service-plan.md` §6 ⑤(band/limit 원천 웨이브 — 「broker 조회 vs
  marketfeed 기준가」로 유보돼 있던 자리).
- 종료조건: ① `max_quantity` 값과 그 조문·개정일·재현 경로가 적혀 있고 ② 프로브가 **무엇을 닫고 무엇을 못 닫는지**가
  레그별로 적혀 있으며 ③ 「결정 9 만으로는 paper 가 송신에 도달하지 않는다」는 사실과 그 다음 결정(§6)이 분리돼 있다.
- 성격: **설계 문서다. 코드와 배포 값은 넣지 않았다.** 프로브 구현(§4)·증거 README·정책 값 착지는 각각 별도 PR.

## 0. 한 줄 요약

paper venue 정책의 `max_quantity: null` 은 「출처 없음」의 fail-closed 상태였고(아래 §1), 그 출처는 **KRX 파생상품시장
업무규정 제71조 → 시행세칙 제61조제1항 → 별표 17의2** 의 「코스피200선물거래 정규거래 2,000 계약」이다(§2, 원문 확보).
모의 계좌 GET(`VTTO5105R`)은 **예수금 파생값**이라 이 상한을 줄 수 없고, 보강으로 쓸 수 있는 것은 「주문가능수량 ≥ 1」과
「가격제한폭 응답이 규정 계산과 일치」뿐이다(§4). 한편 `price_min/price_max` 는 **일별 동적 값**이라 정책 YAML 의 정적
리터럴이 될 수 없고 런타임에 원천 경로가 없으므로, 결정 9 를 닫아도 `order_shape_admissible` 는 UNKNOWN 으로 남는다 —
그 해소는 §6 의 별도 결정이다.

## 1. 지금 있는 것 (실측, main `a9aa6037`)

| 무엇 | 어디 | 상태 |
|---|---|---|
| 배포 값 | `config/tos_runtime/paper/venue_constraint_policy.yaml:121-127` — `price_min/price_max: null` · `tick_size: 5` · `lot_size/min_quantity: 1` · `max_quantity: null`; 헤더 17-25행 「NO SOURCE … Never fill by hand」 | 의도된 fail-closed |
| 핀 | `tos/runtime/tests/compose/test_deploy_policies.py:207-209, 294` — 세 null 을 단언 | 값을 넣는 PR 은 이 테스트도 바꾼다(거버넌스 변경, 운영자 승인) |
| 로더 | `tos/runtime/src/tos_runtime/venue/_venue_policy_loader.py:300-318` — 각 bound 는 **int 또는 null** 만, 값별 `source:` 필드 없음(출처는 헤더 주석 + 정책 `evidence:` 블록) | 정수 스케일: 가격 ×100, 수량은 계약 수 |
| 소비 1 — 수량 | `tos/src/tos/egressgw/construction.py:457-463` — `max_quantity is None` → `DENIED "the venue / broker quantity constraint is incomplete"` (step 2) | 10-07 세션 2,510 건 STAGE_DENIED 의 원인 |
| 소비 2 — 형상 | `tos/src/tos/venue/predicates.py:282-291` — `price_min`·`price_max`·`max_quantity` 중 **하나라도** null → `UNKNOWN`; `:308-309` 가격이 band 밖 → INADMISSIBLE; `:319` 수량 > max → INADMISSIBLE | ⚠ `max_quantity` 만 채우면 step 2 는 열리지만 step 3 는 band null 로 UNKNOWN 유지 |
| 원천 경로 | `tos/runtime/src/tos_runtime/venue/service.py:196-199` 부팅 시 YAML 에서 고정 · `:262-274` 스냅샷에 가격/수량 필드 없음 · marketfeed·broker 조회에서 band 를 채우는 코드 **0** | spec 은 band 를 Critical Input 사실로 봄(ADR-002-019 §9) — 런타임 미구현 |
| 하네스 — 실전 전용 레그 | `tools/broker_probes/probes_real_order.py:1094-1097` `PreflightClient.get` 이 `REAL_BASE_URL` + `assert_real_host` 로 **실전 호스트 고정**; `TTTO5105R`(`:181`)·`FHMIF10000000`(`:151`) 레그와 band 읽기(`:1717-1718` `futs_llam/futs_mxpr`)·틱 대조(`_corroborate_tick :1444-1474`, 순수 함수) | 모의로 **그대로 못 씀** — 순수 함수(`_corroborate_tick`, `resolve_smallest_contract`)만 재사용 |
| 하네스 — 모의 레그 | `tools/broker_probes/probes_query.py:212-219` P-16 이 모의 호스트로 `FHMIF10000000` 을 치지만 **시계 필드만** 기록 | 가격 필드 기록 없음 |
| 공식 TR 표 | KIS `examples_llm/domestic_futureoption/inquire_psbl_order/inquire_psbl_order.py` — `real: TTTO5105R` / `demo: VTTO5105R`, 필수 파라미터 `CANO/ACNT_PRDT_CD(03)/PDNO/SLL_BUY_DVSN_CD/UNIT_PRICE/ORD_DVSN_CD`; `inquire_price/inquire_price.py` — `FHMIF10000000` 실전·모의 동일 | `VTTO5105R` 은 레포에 아직 없음 |
| P0-2 미결 | `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:2364, 4427` `price_band_tick_lot_and_quantity_semantics: UNKNOWN` | 이 문서의 프로브가 **부분** 해소(§5) |

## 2. 1차 출처 — KRX 규정 (원문 확보 2026-10-08)

출처는 **KRX 법무포털** `https://rule.krx.co.kr/out/index.do` (`KRX규정 → 파생상품시장규정`). ⚠ `law.krx.co.kr` 은
2026-10-08 현재 응답하지 않는다(DNS 는 풀리나 HTTP/HTTPS 모두 0 바이트 타임아웃) — 인용하지 말 것. 포털은 POST 전용이라
조문별 고정 URL 이 없다 → 아래 재현 레시피와 문서 id 로 인용한다.

| 문서 | 판 | 포털 bookid |
|---|---|---|
| 파생상품시장 업무규정 | 제42차 일부개정 2026-04-15 규정 제2432호, 시행 2026-06-29 | `210199976` |
| 파생상품시장 업무규정 시행세칙 | **제164차 일부개정 2026-07-06 세칙 제2474호, 시행 2026-07-06** | `210228709` |

### 2.1 값 표 (코스피200선물거래)

| 항목 | 값 | 조문 체인 | 최종개정 |
|---|---|---|---|
| **호가수량한도(1 호가당 최대 계약 수)** | **정규거래 2,000 계약** · 야간거래 1,000 계약 · (유동성관리상품 지정 시 200/100) | 업무규정 제71조 → 시행세칙 제61조제1항 → **별표 17의2 제1호** | 별표 17의2 2025-05-29 |
| 호가수량단위 = 거래수량단위 | 1 계약 | 업무규정 제9조의2제1항 → 시행세칙 제4조의5제1항·제2항 | 2014-08-28 신설 |
| 호가가격단위 | 0.05 포인트(×100 스케일 = 5) | 업무규정 제12조 → 시행세칙 제4조의9제1호 | 2024-11-01 |
| 거래승수 | 25만 | 시행세칙 제4조의8제1호 | 2024-11-01 |
| 가격제한비율 | 1단계 8% · 2단계 15% · 3단계 20% (주가지수선물거래) | 업무규정 제70조 → 시행세칙 제56조·제56조의2 → **별표 14 제1호** | 별표 14 2025-05-29 |
| 기준가격 | **직전 거래일의 정산가격**(규정 제96조) — 전일 종가가 아님 | 시행세칙 제55조제1항제2호 | 2025-05-29 |
| 상·하한가 산출 | 상한가 = 기준가격 + 기준가격×비율, **호가가격단위로 내림** · 하한가 = 기준가격 − …, **올림** | 시행세칙 제56조제1항·제2항 단서 | 2014-11-03 |
| 단계 확대 | **정규거래 전용** · 개시 후 15분 경과 이후 · 기준종목이 해당 단계 상(하)한가 도달 후 5분 경과 시 상·하 **각각** 확대 · 종가단일가 시간엔 확대 없음 · 야간 및 08:45~09:00 은 1단계만 | 시행세칙 제56조의2제2항 | 2026-06-11 |

원문(별표 17의2, 파싱 텍스트 29-31행): 「코스피200선물거래, KRX300선물거래, 코스피200변동성지수선물거래, ETF선물거래 —
정규거래: 2,000(200)계약, 야간거래: 1,000(100)계약 … 비고. 괄호안 숫자는 해당 상품이 유동성관리상품인 경우」.
원문(별표 14, 19-25행): 「주가지수선물거래 — 1단계: 8%, 2단계: 15%, 3단계: 20%」.

⚠ 웹 검색 요약에 흔한 「코스피200선물 호가수량한도 1,000(야간 500)」은 **별표 17의2 의 코스닥150/국채/금/돈육 행**을 잘못
읽은 것이다. 2차 요약을 값의 출처로 쓰지 않는다.

### 2.2 정책 파일에 적을 때 반드시 같이 적는 세 가지 단서

1. **회원(증권사)은 이보다 낮게 정할 수 있다** — 시행세칙 제61조제3항 「회원은 제1항에도 불구하고 제1항에 따른 수량 이내로
   호가수량한도 … 를 정할 수 있다」. 2,000 은 **상한**이지 KIS 가 받아 준다는 보장이 아니다. KIS 측 한도는 GET 으로 관측
   불가(§4.3) → 값 옆에 「venue 상한 · broker 한도 미확인」으로 적는다.
2. **거래소가 시장관리상 변경할 수 있다** — 제61조제1항 단서 · 제56조제3항. 값은 「공표 규정값」이지 불변식이 아니다.
3. **누적호가수량한도는 다른 한도**(제61조제2항: 회원 자기거래계좌·사후위탁증거금계좌 한정) — 위탁계좌인 paper/모의에는
   적용되지 않는다. 정책에 넣지 않는다.

### 2.3 증거 보존

- 호스트: `~/.local/state/tos/measure/krx-rules-20261008/` — 별표 17의2 HWP `sha256 3fed6e68…2d71d`, 별표 14 HWP
  `sha256 a3c75362…2648`, 시행세칙 제164차·업무규정 제42차 전문 텍스트, 파서 `hwpread.py`(순수 표준 라이브러리, 조사용).
- 레포: `docs/broker-profiles/evidence/2026-10-08-krx-venue-limits/` 에 두 별표의 **파싱 텍스트**와 README(인용 체인·sha256·
  재현 레시피). HWP 바이너리는 커밋하지 않는다(sha256 으로 결속).
- 재현(법무포털): `GET /out/index.do` 로 세션+CSRF → `POST /out/sch/outsearch.do` (`stxt=호가수량한도`) → `POST
  /out/regulation/regulationViewPop.do` (`bookid=210228709`) → `POST /login/getData.do` 로 다운로드 토큰 →
  `POST /Download.do` (`Serverfile=210064641.hwp` = 별표 17의2, `210064610.hwp` = 별표 14, `210217359.hwp` = 별표 25).

## 3. 값 제안 (운영자 채택 대상 — 캘린더·§6 ② 표와 같은 절차)

| 키 | 제안값 | 출처·등급 | 어디에 |
|---|---|---|---|
| `max_quantity` | **2000** | 별표 17의2 제1호(공식 규정 · **B**) + 단서 §2.2 ① | CP-3 tenant 트리(결정 3) `venue_constraint_policy.yaml`; paper 트리는 별도 채택(digest 재렌더 → `safety_activation.yaml::members` 수동, 09-15 계획 §6 ③) |
| `min_quantity`/`lot_size` | 1/1 (변경 없음) | 등급 B → 조문 인용 추가(제4조의5) | 헤더 주석만 |
| `tick_size` | 5 (변경 없음) | 등급 **C → B** 승격(제4조의9제1호 0.05) | 헤더 주석만 |
| `price_min`/`price_max` | **null 유지** | 일별 동적 값 — 정적 리터럴 금지(§6) | — |
| 비율 `[8, 15, 20]`% · 기준가격 규칙 · 내림/올림 | §6 웨이브의 **입력**으로 기록 | 별표 14 · 제55조 · 제56조 | 이 문서 §2.1 |

채택 효과(코드 추적 §1): step 2 의 `quantity constraint incomplete` DENIED 는 사라지고, step 3 는 band null 로 **UNKNOWN
유지** → 송신 0 은 그대로다. 즉 **결정 9 는 필요조건이지 충분조건이 아니다.** 이 사실은 kickoff §5 4 의 범위 문장
(「결정 9 가 닫히기 전엔 체결·영수증 없음」)을 「결정 9 **와 §6** 이 닫히기 전엔」으로 고쳐 적는다.

## 4. 프로브 설계 — `P-VL`(venue limits · GET-only · MOCK_VTS)

레지스트리 `tools/broker_probes/registry.py` 에 `kind: QUERY · environment: MOCK_VTS · emits_orders: False ·
requires_confirm: False · risk: LOW` 로 등록(P-13/P-16 과 같은 꼴). 새 클라이언트는 `MOCK_BASE_URL` + `assert_mock_host`
(P-16 관용구) — `probes_real_order.py` 의 실전 고정 클라이언트는 **재사용하지 않는다**(§1). 재사용하는 것은 순수 함수
`_corroborate_tick`·`resolve_smallest_contract` 뿐.

### 4.1 레그

| # | TR | 입력 | 기록(`measurements`) | 닫는 것 |
|---|---|---|---|---|
| L1 시세 | `FHMIF10000000` (`F`, `<symbol>`) | 상주 paper 세션이 쓰는 **현재 잎**의 결제월 코드(`paper-data/<종목>`)를 `--symbol` 로 — 리터럴 금지 | `output1.futs_prpr · futs_prdy_clpr · futs_sdpr(기준가) · futs_mxpr · futs_llam`, `Date` 헤더, KST 시각 | band 의미론(§5) · 기준가가 「전일 정산가」인지(= `futs_sdpr` vs `futs_prdy_clpr` 비교) |
| L2 규정 계산 | (네트워크 없음) | L1 의 `futs_sdpr`, 비율 0.08, 틱 0.05 | `expected_upper = floor_tick(sdpr×1.08)`, `expected_lower = ceil_tick(sdpr×0.92)`, 일치 여부, 단계 추정(8/15/20 중 어느 비율이 응답과 맞는지) | 응답 band 가 제56조 산식과 일치하는지(**1단계 창에서는 일치가 기대값**) |
| L3 주문가능 ① | `VTTO5105R` | `PDNO=<symbol>`, `SLL_BUY_DVSN_CD=02`(매수), `UNIT_PRICE=futs_prpr`, `ORD_DVSN_CD=01`(지정가) | `output.ord_psbl_qty · tot_psbl_qty · bass_idx`, `rt_cd/msg_cd` | 「모의 계좌가 1 계약 이상 주문 가능」(≥1) — **보강만**. 값은 예수금 파생이라 구조 상한과 무관(§4.3) |
| L4 주문가능 ② | `VTTO5105R` | 같되 `UNIT_PRICE = futs_llam`(하한가) | 동일 | 하한가 **경계 포함** 여부(GET 수준에서 거부/수량 0 이면 band 경계 의미론의 공짜 증거) |
| L5 주문가능 ③ | `VTTO5105R` | 같되 `UNIT_PRICE = futs_mxpr + 0.05`(상한가 + 1틱, band 밖) | 동일 | GET 수준에서 band 밖 가격을 거부하는지(`rt_cd≠0`·`msg_cd`) — 거부 코드를 **관측값**으로만 기록, 해석하지 않음 |

페이싱 1.1 s(`probes_order.py:201-208` P-13 실측). 호출 5 + 토큰 1 → 10 초 미만.

### 4.2 언제·어디서

- **CONTINUOUS 08:45~15:45 KST 의 거래일**(`calendar.yaml:56`). 두 번 찍는다: ① **08:50±3분**(제56조의2 — 확대 불가
  창, 1단계가 보장됨 → L2 의 기대값이 정해짐) ② **09:20 이후** 한 번(확대 가능 창 — 보통 여전히 1단계; 다르면 그날의
  확대 사실을 **기록**만). 두 샘플은 별도 아티팩트.
- 분리 워크트리(origin/main detached, `_common.sh guard_checkout`) · `.env.mock`(워크트리에 없으면 기본 체크아웃에서 복사,
  600 권한) · 실전 자격증명·실주문 없음.
- 상주 paper 세션(08:45 부팅)과 **같은 시간대**에 돈다. 프로브는 GET 5 회라 레이트 영향은 없지만, **같은 앱키**를 쓰면
  토큰 1분 재발급 한도(N-15)에 걸릴 수 있다 → `.env.mock` 의 키가 paper 세션의 키와 **다른지** 실행 전 지문으로 확인하고,
  같으면 09:20 샘플 하나만 찍는다.
- 아티팩트: `tools/broker_probes/results/P-VL-<UTC>.json`(gitignore) → 증거 디렉터리
  `docs/broker-profiles/evidence/2026-10-xx-cp3-venue-limits/` 에 복사 + README(인용 토큰 형식 `CITATION-RULE.md`,
  `tools/tos_evidence_citation_check.py` 통과).

### 4.3 이 프로브가 **못 닫는** 것 (먼저 적는다)

- **KIS 측 호가수량한도.** `VTTO5105R` 의 `ord_psbl_qty` 는 예수금·증거금 파생이다(P-R5-PRE 08-03: 예수금 0 계좌에서 0).
  구조 상한(2,000 또는 KIS 가 제61조제3항으로 낮춘 값)은 **주문을 넣어 거부 코드를 받아야** 보인다. 모의 주문이면
  정책상 가능하나(실전 아님) 결정 7 의 범위(체결 비교 포기)와 이 문서의 GET-only 성격 밖이다 → **후속 선택지**로만 적는다
  (§7 ④).
- **2/3단계 확대의 의미론.** 확대는 기준종목의 도달 사건에 달려 있어 프로브가 일으킬 수 없다. 관측되면 기록, 아니면 미관측.
- **band 의 런타임 공급.** 프로브는 값을 관측할 뿐, 런타임에 band 를 넣는 경로는 §6 이다.

## 5. 판정

| 레그 | PASS | FAIL / 미관측 |
|---|---|---|
| L1 | `rt_cd=0`, 다섯 필드 모두 양의 소수, 0.05 단위 정합(`_corroborate_tick`) | 필드 누락·0·틱 불일치 → `ProbeError`, 아티팩트에 그대로 |
| L2 | ①샘플에서 `futs_mxpr == expected_upper ∧ futs_llam == expected_lower`(1단계) | 불일치 → 「기준가가 정산가가 아니거나 내림/올림 규칙이 다르다」를 **해석 아님**으로 기록, 비율 15/20 으로 재계산해 맞는 단계가 있으면 그 사실만 기록 |
| L3 | `rt_cd=0 ∧ ord_psbl_qty ≥ 1` | 0 이면 「예수금 0 또는 조회 거부」로 기록(P-CA 교훈: `held=0` 오판 금지), 상한과 무관 |
| L4·L5 | 관측만 — PASS/FAIL 없음 | `rt_cd`·`msg_cd`·수량을 그대로 |

P0-2 `price_band_tick_lot_and_quantity_semantics` 의 처분: L1·L2 PASS 면 **band 의미론(기준가·비율·내림/올림)은 모의에서
관측됨**, 수량 상한은 **규정값·broker 미확인** → 프로파일에 `PARTIAL` 로 적고 미확인 축을 나열한다(UNKNOWN 을 한 글자로
뒤집지 않는다).

## 6. band 원천 웨이브 — 운영자 결정 (후속, 이 문서로 열어 둠)

`price_min/price_max` 는 **매 거래일** 바뀌고 장중에도 확대될 수 있다(§2.1). 정적 정책 리터럴은 틀린 값이 되므로 금지.
spec 은 band 를 Critical Input 사실(출처·연속성·as_of·max_age 결속)로 본다(ADR-002-019 §9). 런타임에는 그 경로가 없다(§1).

| 선택지 | 내용 | 장점 | 단점 |
|---|---|---|---|
| (i) broker 조회 | 세션 부팅(08:45) 직후 `FHMIF10000000` GET 1회 → `VenueConstraintSnapshot` 에 band 사실 + as_of + max_age 결속, `shape_constraints` 를 세션 단위로 재구성 | 확대 사실을 **그대로** 반영 · broker 증거 | 런타임 변경(venue service 가 부팅 후 1 GET · 스냅샷 필드 확장 · `critical_input_snapshot_digest` 채움) · 장중 확대는 재조회 주기 필요 |
| (ii) 규정 계산 | marketfeed 의 전일 정산가 × 1단계 비율, 제56조 내림/올림 | 네트워크 없음 · 규정 기반 | 2/3단계 확대를 못 본다 → **보수적**(좁은 band) 이나 확대 시 유효 주문을 INADMISSIBLE 로 오판 · 정산가 원천(marketfeed 에 있는지) 확인 필요 |
| (iii) (i)+(ii) 상호 보강 | (ii) 를 기대값, (i) 를 관측값으로 두고 불일치면 UNKNOWN | 둘의 결함을 서로 가림 | 구현 둘 |

**권고: (i) 먼저, (ii) 는 L2 가 PASS 한 뒤 corroboration 으로.** 이유: 확대 상태는 관측으로만 알 수 있고, 프로브 L1 이 그
경로의 리허설이다. 커널 술어(`order_shape_admissible`)는 바꾸지 않는다 — 바뀌는 것은 런타임이 `constraints` 객체를 **언제
어떤 출처로** 만드는가이며, GOV-001 범위 밖. 이 결정은 CP-3 §5 3(tenant 트리·부팅 경로)과 같은 PR 묶음이 아니라 **별도
계획 문서**로 간다(09-15 계획 §6 ⑤ 의 후속).

## 7. 기각한 대안

| 대안 | 이유 |
|---|---|
| (b) `VTTO5105R` 예수금 파생값을 「불일치 선언」하고 사용 | 값이 예수금에 따라 날마다 다르고 구조 상한과 무관 — 정책 값은 「공표 규정값」이어야 한다(README 규칙) |
| (c) null 유지 | 결정 수준 관측만 가능 — 운영자가 (a) 를 골랐다 |
| `data.krx.co.kr` 의 일별 상·하한가 수치로 대조 | 2026-10-08 현재 통계 화면이 로그인 월 뒤(`getJsonData.cmd` → `LOGOUT`) — 1차 확인 불가라 **전제로 쓰지 않음**. 규정 산식 대조(L2)가 대체 |
| ④ 모의 주문 2,001 계약으로 거부 코드 관측(KIS 한도 확인) | 가능은 하나(모의·실전 아님) GET-only 범위 밖 · 결정 7 과 별개 → 운영자가 원하면 별도 프로브(P-VL-2)로 |
| `probes_real_order.py` 레그를 모의로 돌리기 | `assert_real_host` 고정 — 풀면 실전 안전장치를 약화시킨다 |

## 8. 핸드오버 — 순서

1. **운영자**: 이 문서 승인(§3 값 표 채택 여부 · §6 선택). 승인 전엔 아무 값도 착지하지 않는다.
2. 실행 에이전트: `P-VL` 구현(레지스트리 + `probes_venue_limits.py` + hermetic 테스트: 레그별 레드 증명 — band 불일치·
   `ord_psbl_qty` 비정수·`rt_cd≠0`·틱 불일치 각 1건, 실전 호스트 거부 1건) → PR → 리뷰 → 머지.
3. 거래일 장중 실행(§4.2, 분리 워크트리) → 증거 디렉터리 + README(인용 토큰) → PR.
4. 브로커 프로파일 초안 `price_band_tick_lot_and_quantity_semantics` 처분(§5) — 같은 PR.
5. CP-3 §5 3 tenant 트리 생성 시 `max_quantity: 2000` 과 §2.2 단서를 헤더에 적어 착지; `test_deploy_policies.py` 의
   null 단언은 **tenant 트리에 대해** 2000 으로, paper 트리는 운영자가 별도 채택할 때까지 null 유지.
6. §6 결정 → 별도 계획 문서.
