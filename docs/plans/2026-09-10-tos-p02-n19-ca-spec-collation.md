# N-19 — KIS 기업행위(corporate action) 반영 모델 명세 대조

- **작업**: P0-2 N-19 (문서 대조, 측정 아님)
- **정본 정의**: `docs/plans/2026-08-07-tos-p02-nontrade-probe-definition.md` §5.1 (4항목·검증
  어휘·"반영 시점 없으면 UNKNOWN이지 0/즉시 아님")
- **선례 형식**: `docs/plans/2026-07-29-tos-p02-n17-spec-collation.md` (E-등급·표·부재판정 규율 미러링)
- **원전 (1순위)**: 로컬 체크아웃 `open-trading-api/`(gitignored, 공식 SDK, `examples_llm/domestic_stock/`)
  — 2차 커뮤니티 원천(pykis·mojito·블로그) 사용 **0건**
- **원전 (2순위, 실패)**: `https://apiportal.koreainvestment.com` — WebFetch 2회 시도(최상위 페이지 +
  `ksdinfo/dividend` 경로), 접근일자 2026-09-10. 결과: **페이지가 JS 렌더링**(`javascript:;` 내비게이션)이라
  본문 텍스트가 정적으로 노출되지 않음 — TR 상세·필드표·모의투자 제약 서술을 **확보하지 못함**.
  이후 모든 판정은 SDK 코드 근거만으로 수행하고, 등급을 그에 맞게 낮춘다(과제 지시 §"포털 미확보 시" 대응).
- **접근일자**: 2026-09-10 (표 내 모든 SDK 근거 동일 — 개별 반복 표기 생략)
- **커밋**: 금지(본 문서 미커밋) · draft YAML/템플릿/런북/`tools/broker_probes/registry.py` **무접촉**

> **비규범 INSTANCE 트랙 산출물.** KIS 고유명사 사용 허용. RFC/ADR 본문으로 이관 금지(broker-agnostic 규율).

---

## 0. 증거 등급 (N-17 §0 그대로 차용)

| 등급 | 의미 | 본 문서 사용 |
|---|---|---|
| **E1** | 응답 필드 rename dict(`COLUMN_MAPPING`) 전체를 확보 | 그 **응답면 전수**로 인정 → 필드 *부재* 확정 가능(이 TR 응답면 한정) |
| **E2** | docstring이 값집합을 `ex.`로 명시 열거 | 열거된 값은 확정. 열거 외 존재 가능성은 **불확정** |
| **E3** | 코드 분기(`if svr == "vps"` 등)로 실전/모의 TR id 쌍이 확인됨 | 그 항목만 확정. 다른 TR로 일반화 안 함 |
| **E0 (신설)** | 포털 미확보로 SDK 래퍼 코드만 근거 | "명세에 없다" 주장은 **이 SDK 문서면 한정**. 포털 원본에 서술이 있을 가능성 배제하지 않음 |

부재 판정은 항상 범위를 명시한다. 추정 기입 **0건**.

---

## §1. 4항목 판정 요약

| # | 항목 | 판정 | 근거 요지 |
|---|---|---|---|
| 1 | CA 조회/통지 API 존부 | **VERIFIED(SDK, E1)** — `github.com/koreainvestment/open-trading-api`, 접근 2026-09-10 | 예탁원정보(ksdinfo) 계열 **12개 TR**이 실재. 배당·무상증자·자본감소·합병분할·유상증자·액면교체·실권주·상장정보·공모주청약·의무예치·주식매수청구·주주총회 전수 커버(§2.1) |
| 2 | 7-시각별 반영 모델 | **UNKNOWN** (문서 침묵) | 각 TR의 응답 필드는 CA **일정**(record/ex/effective/payable 후보)을 주되, **balance/position/체결통보에 언제 반영되는지는 12개 TR 중 어느 docstring·필드에도 서술 없음**(§2.2). "즉시/당일 반영"으로 추정하지 않음 |
| 3 | reconciliation 증거·finality 필드 | **UNSUPPORTED(이 응답면 한정, E1)** | 주식잔고조회(`TTTC8434R`/`VTTC8434R`) 응답 72필드 전수 확보 — CA 전후 구분·현금대용(cash-in-lieu)·단수 잔여(rounding) 전용 필드 **부재 확정**(이 TR 응답면 한정). 타 TR(기간별손익 등) 미조사 — 전사 UNSUPPORTED 아님 |
| 4 | 독립 참조원 후보 | **UNKNOWN/미확정** | ksdinfo 12종은 **KIS가 예탁원(KSD) 데이터를 중계**하는 broker-side TR — ADR-002-010 §7 공통모드 규율상 "동일 vendor/parser/clock"이라 **독립 아님**. repo 내 SEIBRO/DART 직접 수집기는 존재하나 CA 일정 파싱 없음(stub). KRX 엔드포인트 무CA. 독립 참조원은 **미구현 후보뿐** |

---

## §2. 항목별 상세 근거

### §2.1 항목 1 — CA 조회/통지 API 존부 (VERIFIED, E1)

`open-trading-api/examples_llm/domestic_stock/ksdinfo_*/` 아래 12개 TR을 전수 확인(디렉터리 listing +
각 파일 `tr_id` 리터럴 직접 인용). 전부 **조회 전용**(GET, 파라미터에 계좌번호 없음 — 계좌 무관 레퍼런스
데이터), **`cts`(연속조회 키) + `f_dt`/`t_dt`(조회기간) + `sht_cd`(종목코드, 공백=전체) 공통 패턴**.

| CA 클래스 (ADR §4.1 CORPORATE_ACTION) | TR id | API 경로 | 소스 (file:line) | MOCK(VTS) 지원 |
|---|---|---|---|---|
| 배당(현금·주식·중간) | `HHKDB669102C0` | `/uapi/domestic-stock/v1/ksdinfo/dividend` | `ksdinfo_dividend/ksdinfo_dividend.py:88` | **UNKNOWN**(E0) |
| 무상증자 | `HHKDB669101C0` | `/uapi/domestic-stock/v1/ksdinfo/bonus-issue` | `ksdinfo_bonus_issue/ksdinfo_bonus_issue.py:80` | **UNKNOWN**(E0) |
| 유상증자 | `HHKDB669100C0` | `/uapi/domestic-stock/v1/ksdinfo/paidin-capin` | `ksdinfo_paidin_capin/ksdinfo_paidin_capin.py:83` | **UNKNOWN**(E0) |
| 자본감소(감자) | `HHKDB669106C0` | `/uapi/domestic-stock/v1/ksdinfo/cap-dcrs` | `ksdinfo_cap_dcrs/ksdinfo_cap_dcrs.py:76` | **UNKNOWN**(E0) |
| 합병/분할 | `HHKDB669104C0` | `/uapi/domestic-stock/v1/ksdinfo/merger-split` | `ksdinfo_merger_split/ksdinfo_merger_split.py:77` | **UNKNOWN**(E0) |
| 액면교체(액면분할/병합) | `HHKDB669105C0` | `/uapi/domestic-stock/v1/ksdinfo/rev-split` | `ksdinfo_rev_split/ksdinfo_rev_split.py:86` | **UNKNOWN**(E0) |
| 실권주 | `HHKDB669109C0` | `/uapi/domestic-stock/v1/ksdinfo/forfeit` | `ksdinfo_forfeit/ksdinfo_forfeit.py:79` | **UNKNOWN**(E0) |
| 상장정보 | `HHKDB669107C0` | `/uapi/domestic-stock/v1/ksdinfo/list-info` | `ksdinfo_list_info/ksdinfo_list_info.py:77` | **UNKNOWN**(E0) |
| 공모주청약 | `HHKDB669108C0` | `/uapi/domestic-stock/v1/ksdinfo/pub-offer` | `ksdinfo_pub_offer/ksdinfo_pub_offer.py:77` | **UNKNOWN**(E0) |
| 의무예치 | `HHKDB669110C0` | `/uapi/domestic-stock/v1/ksdinfo/mand-deposit` | `ksdinfo_mand_deposit/ksdinfo_mand_deposit.py:78` | **UNKNOWN**(E0) |
| 주식매수청구권 | `HHKDB669103C0` | `/uapi/domestic-stock/v1/ksdinfo/purreq` | `ksdinfo_purreq/ksdinfo_purreq.py:79` | **UNKNOWN**(E0) |
| 주주총회(참고 — 값 변환 아님) | `HHKDB669111C0` | `/uapi/domestic-stock/v1/ksdinfo/sharehld-meet` | `ksdinfo_sharehld_meet/ksdinfo_sharehld_meet.py:81` | **UNKNOWN**(E0) |

**MOCK 지원 판정 근거(E3 미충족 이유):** 12개 파일 전부에서 `tr_id`가 **단일 리터럴**로 하드코딩되어 있고
(`env_dv`/`svr` 분기, `V`-접두 변형, "모의투자 미지원" 문구를 grep 0건 — 명령: `grep -rn "모의투자\|모의서버\|미지원" ksdinfo_*/*.py` → 무매치),
N-17 항목 13(§0.5 대조 대상)이 확정한 **실전/모의 TR id 쌍 패턴**(`TTTO.../VTTO...`, `H0STCNI0/H0STCNI9`)과
**형태가 다르다** — 이 12개 TR은 계좌 비의존 레퍼런스 조회라 애초에 실전/모의 분기 자체가 코드에 없다.
이는 "모의에서도 그대로 동작한다"의 증거가 **아니라** "래퍼가 이 질문에 침묵한다"의 증거다. ⇒ **모의서버가
이 TR들에 실데이터를 반환하는지는 실측(P-CA feasibility 관측) 전까지 UNKNOWN** — 추정 금지.

대조군: 체결통보(`ccnl_notice/ccnl_notice.py:56-58`)는 `H0STCNI0`(실전)/`H0STCNI9`(모의) **명시 분기**가
있다 — "래퍼가 분기 안 하면 모의 미지원"이라는 역추론이 성립하지 않음을 보여주는 대조 사례로 인용.

### §2.2 항목 2 — 7-시각 반영 모델 (UNKNOWN, 구조 부분 확정)

**구조(어느 시각 *필드*가 존재하는가)는 E1로 부분 확정**되나, **반영 시점(그 시각이 balance/position/
체결통보에 언제 나타나는가)은 12개 TR 문서면 전체에서 grep 0** —
명령: `grep -rn "반영\|익일\|T\+\|결제" ksdinfo_*/ksdinfo_*.py ksdinfo_*/chk_*.py` → 무매치.
`tos/src/tos/nontrade/records.py:359-366`의 7-시각 어휘에 매핑:

| 7-시각(ADR §5 line 106) | 존재하는 CA 클래스 · 필드명(한글) | 부재 클래스 |
|---|---|---|
| `record_time`(기준일) | 배당·무상증자·자본감소·합병분할·유상증자·액면교체·주식매수청구·주주총회·공모주청약 전부 `record_date`(기준일) | 상장정보·의무예치·실권주(대신 `list_dt`/`depo_date`/`subscr_dt`) |
| `ex_time`(배당락/권리락) | **무상증자**(`right_dt` 권리락일, `ksdinfo_bonus_issue/chk_ksdinfo_bonus_issue.py:30`) · **유상증자**(`right_dt`, `ksdinfo_paidin_capin/chk_ksdinfo_paidin_capin.py:32`) | **현금배당(부재 확정, E1)** — `ksdinfo_dividend` 응답 12필드 어디에도 배당락일 없음(`chk_ksdinfo_dividend.py:25-37`). **자본감소·합병분할·액면교체도 부재**(해당 chk 파일 필드 목록에 `right_dt` 없음) |
| `effective_time`(신주 효력) | `list_date`/`list_dt`(상장/등록일) — 무상증자·자본감소·합병분할·유상증자·실권주·상장정보·공모주청약·액면교체 공통 | — |
| `payable_time`(지급) | `divi_pay_dt`/`stk_div_pay_dt`(배당금·주식배당지급일, `ksdinfo_dividend`) · `odd_pay_dt`(단주대금지급일, 배당·무상증자·합병분할) · `pay_dt`(납입일, 공모주청약) · `buy_amt_pay_dt`(매수대금지급일, 주식매수청구) | 자본감소·액면교체(단수처리 지급일 필드 부재) |
| `settlement_time`(결제) | **부재 — 12개 TR 전수(E1)**. "결제일" 명칭 필드가 어느 응답에도 없음 | 전부 |
| `announcement_time`/`observation_time`(공시/우리 관측) | **개념상 부재** — 이 TR들은 broker가 확정한 **예정 일정 조회**이지 공시 원문 타임스탬프나 자사 관측 타임스탬프를 반환하지 않음 | 전부 |

**핵심 발견 (MAJOR):** 현금배당은 `ex_time`(배당락일) **전용 필드가 없다** — 배당락은 통상
"배당기준일(record_date) 직전 영업일"로 **거래소 계산 규칙에서 파생**되며 KSD/KIS가 별도 필드로
공표하지 않는 것으로 보인다(이 문서면 한정 E1 확정; 파생 규칙 자체는 UNKNOWN — 포털 미확보로 검증 못함).
⇒ P-CA가 현금배당 `ex_time`을 t0로 쓰려면 **레코드-일 파생 규칙을 별도로 확립**해야 하며, 이는 N-19
범위를 넘는 후속 질문이다(§5).

**반영 지연 자체(clock (c))는 완전 UNKNOWN.** 12개 TR 중 어느 것도 "이 정보가 잔고/포지션에 언제
반영되는지"를 서술하지 않는다 — 설계 문서(§0.4 인용)의 "문서에 반영 시점이 없으면 UNKNOWN이지 0/즉시가
아니다" 규율을 그대로 적용한다.

### §2.3 항목 3 — reconciliation 증거·finality 필드 (UNSUPPORTED, 응답면 한정)

주식잔고조회 TR(`TTTC8434R`실전/`VTTC8434R`모의 — N-17 항목16 기정, 재확인 안 함)의 응답
`COLUMN_MAPPING` **72필드 전수**(`open-trading-api/examples_llm/domestic_stock/inquire_balance/chk_inquire_balance.py:21-71`)를
확보. CA 이후 최종 수량·현금대용·단수 처리에 대응할 만한 필드:

| 찾은 것 | 필드 | 비고 |
|---|---|---|
| 보유 수량 | `hldg_qty`(보유수량, :29) | **CA 전/후 구분 없음** — 단일 현재값 |
| 전일/금일 매수매도 수량 | `bfdy_buy_qty`/`bfdy_sll_qty`/`thdt_buyqty`/`thdt_sll_qty`(:25-28) | **거래(trade) 기준**이지 non-trade 조정 기준이 아님 — CA 수량 변경이 여기 잡히는지 불명 |
| 익일정산금액 | `nxdy_excc_amt`(:49) | 결제 관련이나 CA 현금대용과의 연결 서술 없음 |

**부재 확정(E1, 이 TR 응답면 한정):** `cash_in_lieu`류, `rounding_residual`류, CA 이벤트 참조 ID,
`per_field_confidence`류 필드는 **72필드 중 0건**. ⇒ `B_non_trade_reconcile`의 "final quantity·
cash-in-lieu·rounding" 상한을 이 TR 응답만으로는 **관측할 수단이 없다** — CA 발생 전후로
`hldg_qty` 스냅샷을 폴링 비교하는 것이 유일한 간접 관측 경로(§3).

**범위 경고:** 기간별손익(`inquire_balance_rlz_pl`)·체결내역 등 다른 TR은 이번 대조에서 미조사.
"KIS 전체에 finality 필드가 없다"는 **전사 판정이 아니다** — 항목 3은 UNSUPPORTED를
**주식잔고조회 응답면 한정**으로 기입한다.

### §2.4 항목 4 — 독립 참조원 후보 (UNKNOWN/미확정)

ADR-002-010 §7(design doc §0.4 인용) — "동일 vendor/parser/clock을 쓰는 다중 피드는 공통모드이며
독립 corroboration으로 서술 금지". 이 잣대로 후보를 판정:

| 후보 | 독립성 판정 | 근거 |
|---|---|---|
| ksdinfo 12종(예탁원 데이터, KIS 중계) | **독립 아님** | KIS가 KSD 원천을 자사 API로 **중계**하는 구조(§2.1) — vendor/parser/clock이 broker(KIS) 그 자체와 동일. §13.13 "independent reference"의 정의를 충족하지 못함 |
| SEIBRO 직접 수집 | **미구현 — 후보만** | `shared/llm/collectors.py:20-33,56-58`에 `SEIBRODataCollector` 실재하나, `_get_dividend_info`는 **`{"status": "available"}`만 반환**(effective-date·비율 파싱 없음 — 설계 문서 §1 표 기정 사실, 본 문서에서 재확인 안 함). 만약 이 stub을 채워 SEIBRO 웹/API를 **직접** 파싱하면 KIS 파서·클록과 분리되어 독립성 성립 후보가 됨 |
| DART 공시 | **미구현 — 후보만·텍스트뿐** | `shared/llm/collectors.py`의 `DARTDataCollector`는 공시 **원문 텍스트**를 news 파이프라인에 공급(`unified_trading_analyzer.py:61-62` "공시정보, 재무제표") — 구조화된 CA 일정 필드 파싱 없음. 시각 필드 추출 로직 신설 필요 |
| KRX Open API | **엔드포인트 자체 부재** | 리포 `shared/llm/CLAUDE.md`(design doc §1 표 인용, 본 문서 재확인 안 함) — CA 전용 엔드포인트 없음 |
| `config/kis/`·`shared/kis/` 배선 | **grep 0** | 명령 재실행: `grep -rn "배당\|권리\|분할\|합병\|무상\|유상\|ksdinfo\|corp_action\|dividend" config/kis shared/kis` → 무매치(설계 문서 §1 표와 **일치·재확인**) |

**판정:** 현재 시점에 리포에 **가동 중인 독립 참조원은 없다.** ksdinfo는 broker-native 참조원
후보(항목1 충족)이지만 §13.13 "independent"의 정의(공통모드 배제)는 만족하지 못한다 — 즉
ksdinfo는 **"KIS가 CA를 아는가"엔 답하지만 "KIS 스스로의 반영 오류를 잡아낼 제3자 corroboration"은
못 된다.** 독립성 확보는 SEIBRO/DART/KRX 중 하나를 **KIS 경로 밖에서 직접** 통합해야 성립 — 현재는
미착수.

---

## §3. P-CA에 대한 함의

1. **t0 앵커 가능 여부(클래스×leg):** 무상증자·유상증자는 `ex_time`(권리락일)까지 ksdinfo에서
   broker-native로 확보 가능 — **P-CA t0 앵커 가능(MOCK 실데이터 반환 여부는 별개 미지, 아래 4).**
   현금배당은 `ex_time` 전용 필드가 없어 **파생 규칙 확립 전까지 앵커 불가** — `record_time` +
   `payable_time`만 broker-native, `ex_time`은 operator 수기 기록(운영, §5.2 선행조건 2)에 의존해야
   한다. 자본감소·합병분할·액면교체는 `ex_time` 자체가 개념상 없을 수 있음(단순 비율 조정 이벤트) —
   `effective_time`(`list_dt`)이 사실상 t0 후보.
2. **`settlement_time` leg은 전 클래스 미앵커.** 12개 TR 중 어느 것도 결제 완결 시점을 반환하지
   않으므로, `B_non_trade_reconcile`의 상한은 **여전히 `hldg_qty` 스냅샷 비교라는 간접 관측**에만
   의존한다(§2.3). P-CA 절차(설계 문서 §5.2 ④)의 "operator가 각 시각을 축자 기록"은 **settlement만은
   broker 문서가 아니라 순수 operator 관측/추정에 의존**해야 함을 명시한다.
3. **모의서버가 CA를 실제로 반영하는지 자체가 N-19로는 미확정(§2.1 MOCK 열).** 설계 문서 §4의
   `ENV_MOCK` 기본 정책은 유지되나, P-CA의 **1차 산출물은 값 확립이 아니라 "모의서버가 이 12개 TR에
   대해 응답하는가 / 잔고에 CA를 반영하는가"라는 feasibility 관측**이어야 한다(설계 문서 §5.2 통계 규율과
   합치 — "모의가 CA 미반영이면 그 자체 findings"). 이 문서는 그 **첫 관측 후보**로 다음을 제안한다:
   무상증자 1건을 대상으로 `ksdinfo_bonus_issue`(MOCK 인증 세션)를 호출해 응답 존부만 확인하는 것 —
   주문 0, GET 1회, 위험 LOW.
4. **선물 CA는 본 문서 범위 밖.** `open-trading-api/examples_llm/domestic_futureoption/`에서
   만기/결제 관련 TR(`inquire_balance_settlement_pl` 등)이 존재하나(디렉터리 listing만 확인, 필드 미조사),
   설계 문서 §4가 이미 정책적으로 모의·실전 양 경로를 차단했으므로(모의 선물잔고 미지원·실선물
   무증거금) 이번 대조는 **의도적으로 얕게** 다뤘다 — 후속 N-19b 후보로 이월(§5).

---

## §4. INSTANCE 기입 후보 (제안만 — `draft.yaml` 무편집)

`capabilities.corporate_actions.*`(draft.yaml:1771 템플릿 / :4179 INSTANCE, HEAD 44fc4343) 대상:

| 필드 | 제안 값(후보 — Bounds-Approver/스펙 트랙 승인 전까지 비공식) | 근거 |
|---|---|---|
| `status` | `PARTIAL` — "broker-native 일정 조회 있음, 반영시점 문서 없음, 모의지원 미확인" | §1 |
| `fallback_reference` | `NOT_ESTABLISHED` — 가동 중 독립 참조원 없음(§2.4). SEIBRO 직접 통합을 **후보**로 명기 | §2.4 |
| `evidence_refs[]` | 본 문서 경로 1건 + §2.1 표의 12개 `file:line` 개별 인용 | §2.1-2.3 |
| `_kis.measurement` | `OFFICIAL-DOC`(항목1, TR 존부 한정) / 그 외 `NEEDS-LIVE-MEASUREMENT`(반영시점·MOCK지원·finality) | §0 등급 |

값 기입 실행은 이 문서의 소관이 아니다(설계 문서 §6.4-3 자동 승격 금지). 전용 수치 슬롯 부재
문제(설계 문서 §6 M-status)는 본 문서가 재론하지 않는다.

---

## §5. 열린 질문 (후속 이월)

1. **현금배당 `ex_time` 파생 규칙** — KSD/거래소가 배당락일을 record_date로부터 어떻게 산출하는지
   공식 문서 미확보(포털 미접근). 운영자 문의 또는 별도 포털 재시도 후보.
2. **MOCK(VTS)이 12개 ksdinfo TR에 응답하는가** — §2.1에서 UNKNOWN으로 남김. P-CA 1차 feasibility
   관측 대상(§3-3).
3. **자본감소·합병분할·액면교체의 `ex_time`(권리락) 부재가 진짜 부재인지, 이 SDK 문서면의 누락인지** —
   포털 원본 대조가 필요(E0 → E1/E2 격상 후속 과제).
4. **선물 CA(만기/결제) TR 필드** — `domestic_futureoption/inquire_balance_settlement_pl` 등 미조사.
   설계 문서 §4 정책 차단과 별개로, 문서 대조 자체는 저비용이라 N-19b 후보.
5. **SEIBRO 직접 통합이 §13.13 독립 참조원 요건을 실제로 충족하는지** — 웹 스크레이핑/공식 API
   존부 자체가 미리서치. 별도 리서치 선행(운영자 CLAUDE.md "Development Discipline" 리서치 선행 지침 적용).
6. **`config/kis/tr_ids.yaml`에 12개 ksdinfo TR을 등재할지** — SoT 복원 여부는 별도 승인 레인
   (N-17 항목16 선례와 동일 구조) — 본 문서는 제안하지 않는다(등재는 코드 변경, N-19 범위 밖).

---

## 규율 준수 자기점검

- [x] 각 항목 출처(TR id·file:line) + 접근일자(2026-09-10) 병기
- [x] 확인 실패는 "미확인/UNKNOWN" — 추정값 채움 0건("즉시 반영" 등 추정 금지 준수)
- [x] 커뮤니티 통설(pykis·mojito·블로그) 사용 0건
- [x] 부재 판정은 전수 확보(E1) 시에만, 응답면 범위 명시와 함께
- [x] 포털 미확보를 은폐하지 않고 등급(E0)으로 명시 하향
- [x] draft YAML·템플릿·런북·`tools/broker_probes/registry.py` 무접촉
- [x] 주문/거래 코드 생성 없음 (GET 조회 코드조차 실행하지 않음 — 정적 대조만)
- [x] 커밋 안 함, git 명령 미실행
