# N-17 — KIS 공식 명세 대조 결과

- **작업**: P0-2 N-17 (문서 대조, 측정 아님)
- **정본 체크리스트**: `docs/runbooks/kis-capability-probes.md` §7 (16항목)
- **수단**: `kis-code-assistant-mcp` (조회 전용 — 주문 발생 없음)
- **원전**: `github.com/koreainvestment/open-trading-api` `examples_llm/` (KIS 공식 1차 저장소)
- **접근 일자**: 2026-07-29 (표 내 모든 근거의 접근 일자 동일 — 개별 반복 표기 생략)
- **커밋**: 금지 (본 문서 미커밋)
- **draft YAML / 템플릿 / 런북**: 무접촉

> **비규범 INSTANCE 트랙 산출물.** KIS 고유명사 사용이 허용되는 문서다.
> RFC/ADR 본문으로 이 내용을 옮기지 말 것 (broker-agnostic 규율).

---

## 0. 증거 등급과 부재 판정 규율

본 대조에서 쓴 근거는 전부 **KIS 공식 저장소의 예제 래퍼 코드**다. 이것이 무엇을
증명하고 무엇을 증명하지 않는지 먼저 고정한다.

| 등급 | 의미 | 본 문서에서의 사용 |
|---|---|---|
| **E1** | 래퍼가 실제 전송하는 `params` dict 전체를 확보 | 그 **요청 body의 전수**로 인정 → 필드 *부재* 확정 가능 |
| **E2** | docstring이 값집합을 `ex.` 로 명시 열거 | 열거된 값은 확정. "그 외 없음"은 **불확정** |
| **E3** | 카테고리 검색이 `total_count` 와 함께 전건 반환 | 그 **색인 범위 내** 부재 확정 (포털 문서 전체의 부재는 아님) |

**부재 판정 규율 (anti-phantom 대칭)**: `params` dict는 래퍼가 broker로 보내는
body의 완전한 구성이므로 "이 dict에 없음 = 이 문서면(surface)에 없음"은 정당하다.
그러나 **"KIS 포털 명세 전체에 없음"으로 확대하지 않는다.** 각 항목에 부재의
**범위**를 명시했다.

**금지 준수**: pykis·mojito·블로그 등 2차 커뮤니티 원천은 값 확정 근거로
**단 한 건도 사용하지 않았다.** 확인 실패는 전부 "미확인"으로 남겼고 추정값으로
채우지 않았다.

**repo 측 현재 상태**(런북 표의 `file:line`)는 런북이 이미 실측한 값이라 재실측하지
않았다. 아래 표의 "현재 상태" 인용은 전부 런북 §7 전재다.

---

## 1. 16항목 대조 표

| # | 항목 | 판정 | 근거 (MCP 반환 요지) | 출처 (TR / 경로 / 필드) | INSTANCE 반영 **제안** |
|---|---|---|---|---|---|
| 1 | 주문 요청 필드 전수 — 클라이언트 주문번호 존부 | **확정** (부재) | 주식·선물 주문 래퍼의 `params` dict **전수 확보**. 양쪽 모두 클라이언트가 채우는 주문 식별자 필드 **없음**. 응답은 broker 채번 `ODNO`(주문번호)+`KRX_FWDG_ORD_ORGNO`+`ORD_TMD` | 주식 `order_cash` `/uapi/domestic-stock/v1/trading/order-cash`, body 9필드: `CANO`·`ACNT_PRDT_CD`·`PDNO`·`ORD_DVSN`·`ORD_QTY`·`ORD_UNPR`·`EXCG_ID_DVSN_CD`·`SLL_TYPE`·`CNDT_PRIC` / 선물 `order` `/uapi/domestic-futureoption/v1/trading/order`, body 12필드: `ORD_PRCS_DVSN_CD`·`CANO`·`ACNT_PRDT_CD`·`SLL_BUY_DVSN_CD`·`SHTN_PDNO`·`ORD_QTY`·`UNIT_PRICE`·`NMPR_TYPE_CD`·`KRX_NMPR_CNDT_CD`·`ORD_DVSN_CD`·`CTAC_TLNO`·`FUOP_ITEM_DVSN_CD` | `capabilities.client_generated_order_id.status`: UNKNOWN → **UNSUPPORTED**. 근거 범위를 "주문 2개 write-surface의 body 전수"로 필드 주석에 명기 |
| 2 | TIF 허용값 집합 | **부분** | **선물 확정**: `KRX_NMPR_CNDT_CD` = `0`:없음, `3`:IOC, `4`:FOK (E2 전수 열거). 추가로 `ORD_DVSN_CD`가 TIF를 주문유형에 접어 인코딩 (10~15). **주식 미확정**: 주식 `ORD_DVSN`의 TIF 값 열거를 어느 문서면에서도 확보 못 함 | 선물 `order` docstring `krx_nmpr_cndt_cd (str): [필수] ... (ex. 0:없음, 3:IOC, 4:FOK)` / 선물 `order_rvsecncl` 동일 필드 `(ex. 0:취소/없음, 3:IOC, 4:FOK)` | `live_scope.time_in_force_values`: **선물만** `["0","3","4"]` 기입 제안. 주식은 **빈 채로 유지**(미확인). 자산군별 분리 기입이 불가한 스키마면 기입 보류 |
| 3 | `RVSE_CNCL_DVSN_CD` 값집합 | **확정** | 주식·선물 **양쪽 독립 확인**, 둘 다 `01`:정정 / `02`:취소 **2값**. 우리가 쓰는 2값과 일치 — 미지 값 없음 | 주식 `order_rvsecncl` `/uapi/domestic-stock/v1/trading/order-rvsecncl` (TR `TTTC0013U`/`VTTC0013U`) docstring `(ex. 01:정정,02:취소)` / 선물 `order_rvsecncl` `/uapi/domestic-futureoption/v1/trading/order-rvsecncl` (TR `TTTO1103U`/`TTTN1103U`/`VTTO1103U`) `(ex. 01:정정, 02:취소)` | 정정/취소 코드 열거를 `["01","02"]`로 확정 기입. **P-8 관련 미지값 리스크 해소** — 런북 "우리는 2값만 사용"이 곧 전수임이 확인됨 |
| 4 | `ORD_DVSN`(주식) / `ORD_DVSN_CD`(선물) 값집합 | **부분** | **선물 확정 (전수 10값)**: `01`:지정가 `02`:시장가 `03`:조건부 `04`:최유리 `10`:지정가(IOC) `11`:지정가(FOK) `12`:시장가(IOC) `13`:시장가(FOK) `14`:최유리(IOC) `15`:최유리(FOK). **주식 부분**: `00`:지정가, `01`:시장가 2값만 확보, 전수 미확정 (조건부지정가·IOC 존재는 서술되나 코드 미부여) | 선물 `order` docstring `ord_dvsn_cd (str): [필수] 주문구분코드 (ex. 01:지정가, ... 15:최유리(FOK))` / 주식 `inquire_psbl_order` `/uapi/domestic-stock/v1/trading/inquire-psbl-order` (TR `TTTC8908R`/`VTTC8908R`) docstring `ORD_DVSN:00(지정가)` · `"반드시" ORD_DVSN:01(시장가)로 지정` | 선물 주문유형 열거 10값 기입 제안. 주식은 **미확인 유지**. ⚠ **§2 안전 소견 1 참조 — Q-MIC-3 폴백은 이 항목의 확정만으로 이미 위험 판정 가능** |
| 5 | 숫자 인코딩 파서 동작 | **부분** | **확정된 것**: 전 필드 **String 전송이 명시적 요구**("ORD_QTY(주문수량), ORD_UNPR(주문단가) 등을 String으로 전달해야 함에 유의"). 시장가/최유리 시 가격은 `"0"` 문자열. **미확정**: broker 파서가 소수점 포함 문자열을 어떻게 받는지(절단/반올림/거부) 서술 **없음**. 정수 절단 vs float 문자열 차이(Q-WIRE-1)의 답은 명세에 부재 | 주식 `order_cash` docstring `※ ORD_QTY(주문수량), ORD_UNPR(주문단가) 등을 String으로 전달해야 함에 유의 부탁드립니다.` / 선물 `order` `unit_price (str): [필수] 주문가격1 (ex. 시장가나 최유리 지정가인 경우 0으로 입력)` | 타입 = string 확정 기입. **소수 허용 여부는 미확인 유지** → P-WIRE 계열 프로브 또는 운영자 문의로 이월. 추정 기입 금지 |
| 6 | 필수/선택 구분과 기본값 의미론 | **부분** | **필수/선택 확정**: `NMPR_TYPE_CD` **[필수]**, `KRX_NMPR_CNDT_CD` **[필수]**, `CTAC_TLNO` **선택**, `FUOP_ITEM_DVSN_CD` **선택**. `FUOP_ITEM_DVSN_CD`만 기본값 서술 존재("공란(Default)"). **미확정**: 나머지 3필드의 **생략 시 broker 기본값** 서술 없음 | 선물 `order` 시그니처 — `nmpr_type_cd`·`krx_nmpr_cndt_cd`는 위치인자+`ValueError` 검증, `ctac_tlno: str = ""`·`fuop_item_dvsn_cd: str = ""`는 기본값 인자. docstring `fuop_item_dvsn_cd (str): 선물옵션종목구분코드 (ex. 공란(Default))` | 필수/선택 구분 기입. `FUOP_ITEM_DVSN_CD` 기본값 "공란" 기입. **`CTAC_TLNO` 생략 시 동작은 미확인 유지**. ⚠ **§2 안전 소견 2 참조 — 필수 2필드를 빈 문자열로 보내는 현행은 계약 위반 소지** |
| 7 | 중복/미지/누락 필드 동작 | **미확인** | 미지 필드를 broker가 무시하는지 거부하는지에 대한 서술을 **어느 문서면에서도 확보 못 함**. 래퍼는 고정 dict만 구성하므로 이 질문 자체를 다루지 않는다. **부재 범위**: 예제 래퍼 문서면 한정 — 포털 공통 규약 문서를 못 봤으므로 "명세에 없다"고 확정하지 않음 | — (해당 서술 미발견) | 기입 없음. permissive-parser 리스크는 **UNKNOWN 유지**. 후속: 운영자 문의(포털 공통 규약) 또는 모의서버 프로브(미지 필드 1개 주입 후 응답코드 관찰) |
| 8 | 토큰 `expires_in` 공식 값 | **부분** | **필드 존재·의미 확정**: 응답에 `expires_in` = "접근토큰 유효기간(초)". 동반 필드 `access_token`·`token_type`("Bearer")·`access_token_token_expired`(일시표시). **값 미확정**: 86400인지 등 **구체 수치 서술 없음** — 우리 fallback 86400이 broker 보증이 아니라는 런북 판정이 **유지됨** | `/oauth2/tokenP` (`auth_token`), 응답 필드는 `chk_auth_token.py` `COLUMN_MAPPING` + docstring `Response Fields` 4건 전수 | `expires_in`은 **응답에서 읽어 쓰는 값**으로 다루고 상수 기입 금지. 우리 fallback 86400은 "broker 보증 아님" 주석 유지. 값 자체는 **미확인 유지** |
| 9 | `approval_key` 유효기간 | **미확인** | 발급 API는 확정(`/oauth2/Approval`, 요청 `grant_type`/`appkey`/`secretkey`/(선택)`token`, 응답 `approval_key`·`code`·`message`). **유효기간 필드도 서술도 없음** — 토큰과 달리 `expires_in` 대응물이 응답에 **부재**. repo 주석 "~24h"의 공식 근거는 **여전히 없음** | `/oauth2/Approval` (`auth_ws_token`), 응답 필드는 `chk_auth_ws_token` `COLUMN_MAPPING` 3건(`code`·`message`·`approval_key`) | 유효기간 **미확인 유지**, 필드 `null`. repo 주석 "~24h"를 **공식 근거 없음**으로 강등 표기 제안. 후속: 운영자 문의 |
| 10 | WebSocket 동시 구독 상한 | **미확인** | 실시간 카테고리 25건 색인 확인, 대표 샘플(`ccnl_notice`) 전문 확보 — **구독 상한 수치·서술 없음**. 래퍼는 구독 등록("1")/해제("0") 토글만 노출. **부재 범위**: 예제 래퍼 한정 (상한은 포털 문서 소관으로 보임) | `H0STCNI0`(실전)/`H0STCNI9`(모의) 국내주식 실시간체결통보. `tr_type` 1=등록/0=해제 | `sessions.subscription_limit`: **`null` 유지** (Patch-0057 슬롯). `streaming.yaml:50` 주석 "KIS 제한: 41"은 **커뮤니티 출처**이므로 값 확정 근거로 승격 금지. 후속: **P-14 실측** |
| 11 | REST 유량 공식 수치 | **미확인** (folklore 반증 **유지**) | 공식 예제 어디에도 **"20건/s"·"2건/s" 등 수치 진술 없음**. 대신 유량 제어가 `ka.smart_sleep()` 호출(연속조회 페이지 넘김 시)로만 표현됨 — 즉 **정성적 지연 권고**이지 계약 수치가 아님. 런북의 "folklore 철회 확정" 판정과 **일치** | 연속조회 루프의 `ka.smart_sleep()  # 시스템 안정적 운영을 위한 지연` (`inquire_balance` 주식·선물, `inquire_time_indexchartprice` 공통) | `hard_limits`: **비운 채 유지**(런북 §8.4 "천장까지 무신호 ≠ 한도"). 통설 수치 기입 **금지**. 후속: **P-13 실측** |
| 12 | 자격증명 폐기 API / 전파 시한 | **미확인** | 인증 카테고리 **전건 열거 2회 수행 — 두 번 모두 `total_count: 2`** (`auth_token`, `auth_ws_token`)뿐. revoke/폐기 API **색인 내 부재**. **부재 범위**: 이 MCP의 auth 카테고리 색인 한정 — KIS 포털에 폐기 엔드포인트가 존재할 가능성을 배제하지 않음 (E3) | `search_auth_api` subcategory="인증" → 2건 / query="접근토큰 폐기 revoke 토큰 삭제" → 동일 2건 | `capabilities.credentials_and_revocation.revocation_bound_ms`: **`null`/UNKNOWN 유지**. "MCP 색인 내 폐기 API 미발견"을 근거 주석으로 기록하되 **UNSUPPORTED로 확정하지 말 것**(색인 범위 한계). 후속: 운영자 문의 |
| 13 | 야간 세션 TR 계열의 모의 지원 | **확정** (모의 미지원) | **3계열 독립 확인**. ① 주문: `demo`는 `day`만 허용, `night` 요청 시 `ValueError` — 모의 야간 TR **부재**. ② 정정취소: 동일 구조, `demo`+`night` → `ValueError`. ③ 야간 잔고: 함수에 **`env_dv` 파라미터 자체가 없고** TR이 실전용으로 **하드코딩** — 모의 분기가 애초에 존재하지 않음. **MOCK→REAL 외삽 금지의 직접 근거** | 주문 `TTTO1101U`(실전주간)/`STTN1101U`(실전야간)/`VTTO1101U`(모의주간) + `raise ValueError("ord_dv can only be 'day' for demo environment")` / 정정취소 `TTTO1103U`/`TTTN1103U`/`VTTO1103U` + 동일 가드 / 야간잔고 `CTFN6118R` 하드코딩 (`/uapi/domestic-futureoption/v1/trading/inquire-ngt-balance`) | Q-MIC-1 **확정 근거로 승격**. MOCK_VTS INSTANCE에 "야간 세션 write/read 경로 미제공"을 명시하고, MOCK 관측을 REAL 야간으로 외삽하는 것을 **구조적으로 금지**하는 근거로 인용 |
| 14 | SOX 해외지수 TR id·경로 | **확정** (후보 **반증**) | 해외지수 조회 API 실존 확인 — 단 TR id는 **`FHKST03030200`**이며 로드맵 후보 `HHDFC55020100`이 **아니다**. 시장분류 `N`=해외지수(예시 `SPX`), `X`=환율, `KX`=원화환율. `fid_input_iscd`에 지수 심볼을 넣는 구조라 SOX도 동일 TR로 조회하는 형태. **부재 범위**: 해외주식 기본시세 13건 색인 중 지수 관련은 이 1건 — `HHDFC55020100`은 색인 내 **미발견** | `inquire_time_indexchartprice` = 해외지수분봉조회[v1_해외주식-031], `/uapi/overseas-price/v1/quotations/inquire-time-indexchartprice`, TR **`FHKST03030200`**, params `FID_COND_MRKT_DIV_CODE`·`FID_INPUT_ISCD`·`FID_HOUR_CLS_CODE`·`FID_PW_DATA_INCU_YN` | 로드맵 `:395`의 `HHDFC55020100`을 **미검증 후보에서 반증됨으로 강등**. `probes_real.py::ALLOWLIST`에 추가할 값은 **`FHKST03030200`**. ⚠ 단 "SOX 심볼로 실제 조회 가능"은 **미검증** — N-18b 재실행 전 심볼 확인 필요 |
| 15 | ATS(넥스트레이드) 주문 경로 | **부분** | **확정**: ATS 라우팅은 **별도 엔드포인트가 아니라 기존 주문 API의 `EXCG_ID_DVSN_CD` 값**으로 표현됨 — `KRX`:한국거래소, **`NXT`:대체거래소**, `SOR`:SOR. 주식 주문·정정취소 양쪽 [필수] 필드. 잔고 조회에도 `AFHR_FLPR_YN`에 `X`:NXT 값 존재. 실시간에도 NXT 전용 TR 존재. **미확정**: 런북이 말한 별도 `order-ats` 엔드포인트+TR 4종은 **색인 내 미발견** (`order*` 함수 **전건 8개** 열거 — ATS 전용 없음) | `order_rvsecncl` docstring `excg_id_dvsn_cd (str): [필수] 거래소ID구분코드 (ex. KRX: 한국거래소, NXT:대체거래소,SOR:SOR)` / `order_cash` 동일 필드 [필수] / `inquire_balance` `afhr_flpr_yn ... (ex. N:기본값, Y:시간외단일가, X:NXT)` / 실시간 `member_nxt`(국내주식 실시간회원사(NXT)) / `function_name="order"` 검색 `total_count: 8` = `order_cash`·`order_credit`·`order_rvsecncl`·`order_resv`·`order_resv_ccnl`·`order_resv_rvsecncl`·`inquire_psbl_order`·`pension_inquire_psbl_order` | 현행 공식 경로 = **통합 엔드포인트 + `EXCG_ID_DVSN_CD`**로 기록. `ats_routing` 관련 필드에 venue 값집합 `["KRX","NXT","SOR"]` 기입 제안. **별도 `order-ats` TR 4종은 미확인 유지** — repo `tr_ids.py:35-38`의 4종이 구(舊)경로/미사용인지 운영자 확인 필요 |
| 16 | 잔고 조회 TR 정본 | **확정** | 3계열 전부 확보. 런북 기재와 **대조 결과 일치 + 신규 1건**: 선물 주간 모의 TR **`VTFO6118R`**은 런북에 없던 값 | 주식 `TTTC8434R`(실전)/`VTTC8434R`(모의) `/uapi/domestic-stock/v1/trading/inquire-balance` [v1_국내주식-006] / 선물 주간 `CTFO6118R`(실전)/**`VTFO6118R`**(모의) `/uapi/domestic-futureoption/v1/trading/inquire-balance` [v1_국내선물-004] / 선물 야간 `CTFN6118R`(실전 전용) `/uapi/domestic-futureoption/v1/trading/inquire-ngt-balance` [국내선물-010] | `config/kis/tr_ids.yaml` 잔고 TR **0건** 결손을 위 5개 TR로 채우는 것을 제안(SoT 복원). `futures-legal-review.md:38` 감사 항목의 구조적 충족 불가 사유 해소. ⚠ **본 문서는 제안만** — YAML 수정은 별도 승인 레인 |

---

## 2. 대조 중 발견한 안전 소견 (계획 외 산출)

대조 과정에서 **런북이 예상한 것보다 강한 위험 신호** 2건이 나왔다. 값 기입 제안이
아니라 **판정 근거의 격상**이므로 별도로 남긴다.

### 소견 1 — `ORD_DVSN` 폴백 `"01"`은 자산군에 따라 의미가 **반대**다 (Q-MIC-3 격상)

항목 4의 확정분만으로 이미 결론이 난다.

| 자산군 | 코드 `01`의 의미 |
|---|---|
| **주식** (`ORD_DVSN`) | **시장가** |
| **선물** (`ORD_DVSN_CD`) | **지정가** |

런북 §7 #4가 지적한 "미지 값을 `"01"`로 조용히 폴백"(`executor.py:785-795`)은
따라서 단순한 permissive-repair 위반을 넘어선다 — **주식 경로에서는 미지 주문유형이
조용히 시장가 주문으로 변환**된다. 가격 통제를 잃는 방향의 폴백이며, 이는
fail-open이다. (선물 경로에서는 지정가로 접히므로 방향이 반대다.)

**제안**: Q-MIC-3의 심각도를 재평가하고, 폴백 제거(미지 값 → fail-closed 거부)를
INSTANCE quirk가 아니라 **코드 수정 후보**로 올린다. 본 문서는 대조 산출물이므로
코드 변경은 하지 않았다.

### 소견 2 — 선물 [필수] 필드 2개를 빈 문자열로 전송 중 (항목 6 파생)

공식 명세에서 `NMPR_TYPE_CD`(호가유형코드)와 `KRX_NMPR_CNDT_CD`(한국거래소호가조건코드)는
**[필수]**이며, 공식 래퍼는 빈 문자열이면 `ValueError`로 **호출 자체를 막는다**.
런북 §7 #6은 우리가 이 둘을 **빈 문자열로 보낸다**고 기록하고 있다.

이는 "생략 시 기본값" 문제가 아니라 **필수 필드 계약 위반** 가능성이다. 나아가
`KRX_NMPR_CNDT_CD`는 TIF(IOC/FOK) 캐리어이므로, 빈 값 전송은 **TIF 의미론이
broker 측 암묵 기본값에 위임**되고 있다는 뜻이다.

**제안**: 이 2필드의 현행 전송값을 재확인하고(런북 실측 재사용), 빈 문자열 전송이
사실이면 **P0-2 blocker 후보**로 승격. 값 확정 없이도 "빈 값 전송 금지"는 판정 가능.

### 부수 관측 (참고, 값 확정 아님)

- 주식 주문 TR이 **`TTTC0011U`(매도)/`TTTC0012U`(매수)/`TTTC0013U`(정정취소)** 및
  모의 `VTTC0011U`/`VTTC0012U`/`VTTC0013U`로 확인됨. `order_cash` docstring은
  구 TR `TTC0802U`를 별건(미수매수)으로 언급 — **repo가 쓰는 TR과의 대조는 미수행**
  (N-17 범위 밖, repo 재실측 불요 규율).
- 주식 주문 `EXCG_ID_DVSN_CD`가 현행 명세에서 **[필수]**다. repo가 이를 보내는지는
  본 대조 범위 밖이나, 미전송이면 항목 15와 함께 확인 대상이다.
- 실시간 체결통보는 모의 지원(`H0STCNI9`)이 **있다** — 항목 13의 "야간 부재"와
  혼동 금지. 야간 미지원은 **선물 야간 세션** 한정이다.
- 웹소켓 실시간 데이터는 **AES256 KEY/IV 복호화 필요**로 명시.

---

## 3. 집계

| 판정 | 건수 | 항목 |
|---|---|---|
| **확정** | **5** | 1, 3, 13, 14, 16 |
| **부분** | **6** | 2, 4, 5, 6, 8, 15 |
| **미확인** | **5** | 7, 9, 10, 11, 12 |
| 합계 | 16 | — |

**확정 5건 중 2건은 기존 가설을 반증/격상시켰다**: #14는 후보 TR id
`HHDFC55020100`을 **반증**(정답 `FHKST03030200`), #13은 Q-MIC-1을 **추정에서
구조적 확정으로 승격**.

**미확인 5건은 모두 "값이 없다"가 아니라 "예제 래퍼 문서면에 서술이 없다"**이며,
전부 부재 범위를 명시했다. 추정으로 채운 항목은 **0건**이다.

---

## 4. 미확인 항목의 후속 경로

| # | 항목 | 후속 경로 | 비고 |
|---|---|---|---|
| 7 | 미지/중복 필드 처리 | **운영자 문의**(포털 공통 규약) 또는 모의 프로브 | 프로브 설계: 미지 필드 1개 주입 → 응답코드 관찰. 주문 write-surface라 **모의 한정** |
| 9 | `approval_key` 유효기간 | **운영자 문의** | 응답에 만료 필드 자체가 없어 측정으로는 상한만 얻음. 문의가 정공법 |
| 10 | WS 구독 상한 | **P-14 실측** (런북 기정) | 관측 실패 시 §8.4 "천장까지 무신호 ≠ 한도" 적용, `null` 유지 |
| 11 | REST 유량 | **P-13 실측** (런북 기정) | folklore 반증은 이미 확정 — 실측은 `hard_limits` 채움이 아니라 **하한 확인**용 |
| 12 | 자격증명 폐기 | **운영자 문의** | MCP 색인 한계로 부재 확정 불가. UNSUPPORTED 확정 **금지** |

**부분 판정 6건 중 이월분**: #2 주식 TIF, #4 주식 `ORD_DVSN` 전수, #5 소수 허용
여부, #6 `CTAC_TLNO` 생략 시 동작, #15 `order-ats` TR 4종 — 전부 위와 동일하게
**추정 기입 금지**, 프로브 또는 운영자 문의로 이월한다. #8은 런타임 응답에서 읽으므로
정적 확정이 불필요하다.

---

## 5. 규율 준수 자기점검

- [x] 각 항목에 출처(TR id·API 경로·필드 목록) + 접근 일자(2026-07-29) 병기
- [x] 확인 실패는 "미확인" — 추정값 채움 **0건**
- [x] 커뮤니티 통설(pykis·mojito·블로그) 값 확정 근거 사용 **0건**
- [x] 부재 판정은 전수 확보(E1) 또는 색인 전건(E3) 시에만, **범위 명시**와 함께
- [x] repo 측 현재 상태는 런북 실측 전재 — 재실측 안 함
- [x] draft YAML·템플릿·런북 **무접촉**
- [x] 주문/거래 코드 생성 **없음** (MCP 조회 전용, 주문 발생 0)
- [x] 커밋 **안 함**
