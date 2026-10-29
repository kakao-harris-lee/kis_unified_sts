# 모의 주식 «조회 결과 없음» 봉투 실측 — `VTTC0081R` · `VTTC8434R` (issue #990)

- 측정: `mock-stock-empty-result-20261029.json:measured_at_kst=20261029` (2026-10-29 KST) ·
  `mock-stock-empty-result-20261029.json:environment=MOCK_VTS` ·
  `mock-stock-empty-result-20261029.json:rest_base=https://openapivts.koreainvestment.com:29443`
- 계좌: 모의 주식 `mock-stock-empty-result-20261029.json:account_masked=5020******` (주문 0건 · 보유 0종목)
- 왜: issue #990 은 「KIS 는 빈 조회 결과를 `rt_cd='7'` + `msg_cd='KIOK0560'` 으로 답하므로
  `tos_runtime.recon.witness_kis.KisStockBrokerWitness._walk_continuation` 의 `rt_cd != "0"` 거부가
  **주문 0건 모의 계좌에서 영구 불가**가 되고 모든 해제가 HOLD 된다」를 우려했다. 그 근거(`KIOK0560`)는
  `../2026-07-29-p02-t2-campaign/P-BAL-20260731T114344Z.json` — **실전 선물** 잔고 TR 이다. 이 디렉터리는
  witness 가 실제로 읽는 **모의 주식 두 표면**을 직접 측정한 것이다.
- 안전: **GET 전용 · 주문 0건.** 조회 경로 GET 7회(≥2.5s 간격)와 토큰 발급 1회(`POST /oauth2/tokenP`)뿐이다.
  실전 계좌 미접촉. 아티팩트의 계좌번호는 마스킹했고 자격증명·토큰은 담기지 않는다.
- ⚠ **`evidence_refs[]` 에 쓰지 않는다** — 프로브 하네스 아티팩트가 아니므로 런북
  `../../../runbooks/kis-capability-probes.md` §6.2 체크리스트(`mode`·`provenance_class: MEASURED`·
  `repo_commit` 등)를 통과할 수 없다. 측정 기록(루트 `CLAUDE.md` R7)으로만 보존한다.
  capability `status`·`assurance_level` 무변경.

## 파일

| 파일 | 무엇 |
|---|---|
| `mock-stock-empty-result-20261029.json` | 7회 GET 의 축자 응답(`raw_reads[]`, `raw_body` 포함)과 witness 자신의 판정(`witness_verdicts[]`) |

## 값

요청 파라미터는 `tos/runtime/src/tos_runtime/recon/witness_kis.py` 의 `_read_order_rows`·`_read_balance`
`build_params` 를 그대로 복제했다(계좌 2키는 아티팩트에서 제외). `INQR_STRT_DT == INQR_END_DT` 로 한 날짜씩,
`CCLD_DVSN=00`(전체) · `INQR_DVSN=00`(역순)이다.

| 읽은 면 | 날짜 | HTTP | `rt_cd` | `msg_cd` | `output1` | `output2` | `tr_cont` 헤더 |
|---|---|---|---|---|---|---|---|
| 체결조회 `mock-stock-empty-result-20261029.json:raw_reads[0].tr_id=VTTC0081R` (일요일) | `mock-stock-empty-result-20261029.json:raw_reads[0].request_params.INQR_STRT_DT=20261025` | `mock-stock-empty-result-20261029.json:raw_reads[0].http_status=200` | `mock-stock-empty-result-20261029.json:raw_reads[0].summary.rt_cd=0` | `mock-stock-empty-result-20261029.json:raw_reads[0].summary.msg_cd=70070000` | `mock-stock-empty-result-20261029.json:raw_reads[0].summary.output1_type=list` 길이 `mock-stock-empty-result-20261029.json:raw_reads[0].summary.output1_len=0` | `mock-stock-empty-result-20261029.json:raw_reads[0].summary.output2_type=dict` 5키 | `mock-stock-empty-result-20261029.json:raw_reads[0].tr_cont_response_header=E` |
| 체결조회 (수요일) | `mock-stock-empty-result-20261029.json:raw_reads[1].request_params.INQR_STRT_DT=20261028` | `mock-stock-empty-result-20261029.json:raw_reads[1].http_status=200` | `mock-stock-empty-result-20261029.json:raw_reads[1].summary.rt_cd=0` | `mock-stock-empty-result-20261029.json:raw_reads[1].summary.msg_cd=70070000` | `mock-stock-empty-result-20261029.json:raw_reads[1].summary.output1_type=list` 길이 `mock-stock-empty-result-20261029.json:raw_reads[1].summary.output1_len=0` | `mock-stock-empty-result-20261029.json:raw_reads[1].summary.output2_type=dict` 5키 | `mock-stock-empty-result-20261029.json:raw_reads[1].tr_cont_response_header=E` |
| 체결조회 (당일) | `mock-stock-empty-result-20261029.json:raw_reads[2].request_params.INQR_STRT_DT=20261029` | `mock-stock-empty-result-20261029.json:raw_reads[2].http_status=200` | `mock-stock-empty-result-20261029.json:raw_reads[2].summary.rt_cd=0` | `mock-stock-empty-result-20261029.json:raw_reads[2].summary.msg_cd=70070000` | `mock-stock-empty-result-20261029.json:raw_reads[2].summary.output1_type=list` 길이 `mock-stock-empty-result-20261029.json:raw_reads[2].summary.output1_len=0` | `mock-stock-empty-result-20261029.json:raw_reads[2].summary.output2_type=dict` 5키 | `mock-stock-empty-result-20261029.json:raw_reads[2].tr_cont_response_header=E` |
| 잔고조회 `mock-stock-empty-result-20261029.json:raw_reads[3].tr_id=VTTC8434R` | — | `mock-stock-empty-result-20261029.json:raw_reads[3].http_status=200` | `mock-stock-empty-result-20261029.json:raw_reads[3].summary.rt_cd=0` | `mock-stock-empty-result-20261029.json:raw_reads[3].summary.msg_cd=20310000` | `mock-stock-empty-result-20261029.json:raw_reads[3].summary.output1_type=list` 길이 `mock-stock-empty-result-20261029.json:raw_reads[3].summary.output1_len=0` | `mock-stock-empty-result-20261029.json:raw_reads[3].summary.output2_type=list` 1행 | `mock-stock-empty-result-20261029.json:raw_reads[3].tr_cont_response_header=E` |

- `msg1` — 체결조회 3건 전부 `mock-stock-empty-result-20261029.json:raw_reads[0].summary.msg1=모의투자 조회할 내역(자료)이 없습니다.`,
  잔고는 `mock-stock-empty-result-20261029.json:raw_reads[3].summary.msg1=모의투자 조회가 완료되었습니다.`
  — 빈 결과를 **거부 문구가 아니라 정상 종료 문구**로 적는다.
- 체결조회 `output2` 는 리스트가 아니라 **dict** 이고 합계가 전부 0 이다
  (`mock-stock-empty-result-20261029.json:raw_reads[0].raw_body.output2.tot_ord_qty=0` ·
  `mock-stock-empty-result-20261029.json:raw_reads[0].raw_body.output2.tot_ccld_qty=0` ·
  `mock-stock-empty-result-20261029.json:raw_reads[0].raw_body.output2.tot_ccld_amt=0` ·
  `mock-stock-empty-result-20261029.json:raw_reads[0].raw_body.output2.prsm_tlex_smtl=0` ·
  `mock-stock-empty-result-20261029.json:raw_reads[0].raw_body.output2.pchs_avg_pric=0.0000`).
  잔고 `output2` 는 24키 1행이며 예수금은
  `mock-stock-empty-result-20261029.json:raw_reads[3].raw_body.output2[0].dnca_tot_amt=10000000` 이다.
- 연속조회 키 — 네 응답 모두 `ctx_area_fk100`·`ctx_area_nk100` 을 **공백 100자**로 돌려준다
  (`mock-stock-empty-result-20261029.json` 의 `raw_reads[*].raw_body.ctx_area_fk100`; 값이 공백 100자라
  인용 토큰으로 적으면 읽을 수 없어 토큰을 달지 않았다). `tr_cont` 가 `E` 이므로 `{M,F}` 밖이고,
  walk 은 페이지 0 에서 끝난다 — 키 형상과 무관하게 종료된다.

## witness 자신의 판정 (같은 세션, 같은 자격증명)

| 호출 | 결과 |
|---|---|
| `mock-stock-empty-result-20261029.json:witness_verdicts[0].label=D-witness.order_rows(weekend)` | `mock-stock-empty-result-20261029.json:witness_verdicts[0].outcome=OK` · 반환 `mock-stock-empty-result-20261029.json:witness_verdicts[0].value=('20261025', ())` |
| `mock-stock-empty-result-20261029.json:witness_verdicts[1].label=F-witness.observe(today)` | `mock-stock-empty-result-20261029.json:witness_verdicts[1].outcome=OK` · 아래 스냅샷 |

```text
WitnessSnapshot(observed_at_generation=None, orders=(), positions=(), positions_complete=True,
                cash=Decimal('10000000'), provenance='kis-mock-stock',
                independent_of_evidence_store=True, order_inquiry_date='20261029')
```

(`mock-stock-empty-result-20261029.json:witness_verdicts[1].value` 의 축자값. 줄바꿈만 넣었다.)

## 성립한 것

- **모의 주식은 빈 조회 결과를 거부로 적지 않는다** — 두 표면 모두 `rt_cd: '0'` + **빈 리스트** `output1`.
  `msg_cd` 는 `KIOK0560` 이 아니라 체결조회 `70070000` / 잔고 `20310000` 이다(이 저장소 첫 기록).
- **`KIOK0560` 은 이 두 표면에서 관측되지 않았다.** 저장소의 모든 `KIOK0560` 기록은 실전 선물 잔고 TR 이다 —
  주간 `../2026-07-29-p02-t2-campaign/P-BAL-20260731T114344Z.json`(`CTFO6118R`), 야간
  `../2026-07-29-p02-t2-campaign/N-16-20260729T132749Z.json`(`CTFN6118R`). 즉 INSTANCE 의
  «`KIOK0560` 의 rt_cd 비대칭» 항은 주식 쪽을 **모의 표면 실측으로** 뒷받침받았다.
- **빈 계좌의 종료 신호는 `'E'`** — wave-4 가 실전·모의 주식 잔고에서 본 `'D'` 와 또 다른 값이다.
  `{M,F}` 만 more 로 읽는 구현에는 둘 다 종료로 같다.
- **issue #990 은 재현되지 않는다** — witness 는 주식 전용이고(`refuse_futures_asset`) `rt_cd != '0'` 만
  거부로 읽으므로, 주문 0건·보유 0종목 모의 계좌에서 정상 스냅샷을 돌려준다(위 판정 2건).

## 성립하지 않은 것

- **페이지 크기·절단** — 0행이므로 어떤 페이지 크기와도 정합한다. 이 세션은 절단을 실증도 반증도 하지 않는다.
- **행 스키마** — 0행이므로 모의 주식 체결조회 행 스키마는 미확립 유지(기존 `P-11-*` 아티팩트가 담당).
- **선물 표면** — 측정하지 않았다. 선물 witness 가 생기면 `rt_cd: '7'` + `KIOK0560` 은 그쪽에서 다뤄야 한다.
- **`70070000` 의 일반성** — 빈 결과 1형상만 봤다. 범위 밖 날짜(3개월 초과)·잘못된 파라미터가 같은 코드로
  오는지는 측정하지 않았다.

## 재현

```text
GET /uapi/domestic-stock/v1/trading/inquire-daily-ccld   tr_id VTTC0081R   # 주문 0건 날짜
GET /uapi/domestic-stock/v1/trading/inquire-balance      tr_id VTTC8434R   # 보유 0종목
```

파라미터는 위 「값」 절이 가리키는 `witness_kis.py` 의 `build_params` 두 곳이 정본이고, 아티팩트의
`raw_reads[*].request_params` 가 실제로 보낸 셋이다(계좌 2키 제외). 분리 워크트리 · `PYTHONPATH` 에
`tos/runtime/src`·`tos/src` · 자격증명은 `.env.mock`. 일회성 측정 스크립트는 저장소에 넣지 않았다 —
같은 값은 `tools/broker_probes` 의 `stock_daily_ccld`·잔고 프로브나 witness 의 `order_rows`/`observe`
로도 다시 얻을 수 있다.
