# P0-2 T3 캠페인 — 모의 운영 서버 실행 (2026-09-10 야간 ~ 2026-09-11)

핸드오버: `docs/runbooks/2026-09-10-p02-probe-handover-paper-server.md` · 런북(정본): `docs/runbooks/kis-capability-probes.md`
실행 호스트: 배포(paper) 서버 · 저장소 체크아웃 `main` · 실행 전 `git status --short` 비어 있음 확인(핸드오버 §1-1)
`config/futures_live.yaml::enabled: false` 확인 · `futures:live:suspended` 미설정(빈 값)

## 서버 측에서 채운 값 (핸드오버 §2)

| 값 | 결정 | 근거 |
|---|---|---|
| mini 근월물 코드 | `A05610` (2026-10월물, 만기 2026-10-08) | `futures:contract:latest` read-model(2026-09-10 08:00): front `A05609` 는 2026-09-10 만기(`roll_state=expired`, `new_entry_front_allowed=false`), `next_symbol=A05610` |
| N-18 주간 / 야간 코드 | `A01612` / `1A01612` | read-model 의 야간 코드 패턴 `1A01609`(= `1` + 주간 코드)를 2026-09-10 만기 뒤 12월물에 적용. N-18c 두 leg 모두 `rt_cd=0`(아래) |
| P-CA 대상 종목 · CA 7-시각 | **1차: SK텔레콤 `017670` `cash_dividend`, payable 2026-09-17T00:00:00+09:00** (공시 2026-07-23, 기준일 2026-08-31 경과, 권리락 2026-08-28 경과 — DART 접수 `20260723800522`/`20260723800515`). **2차(후속): 에스피지 `058610` `cash_dividend`, 기준일 2026-09-22 · ex 2026-09-21(도출) · payable 2026-10-22** (접수 `20260907900152`/`20260907900150`). 2026-10-31 까지 보유 20종목에 **수량 변동 CA(무상증자·주식배당·액면분할·병합·감자·합병) 없음** — DART 2026 전체 4,855건 + 2025H2 649건 + 자본변동 API 8종 전수 조사(2026-09-10). 최근접 수량 변동은 카카오 인적분할(신주배정기준일 2026-12-31, 거래정지 2026-12-30~2027-01-26, 접수 `20260821000047`) — 1월 `merger` 클래스 후보. 삼성전자 Q3 배당은 미공시(기준일 ~09-30, 지급 11월 = 창 밖). | 모의 주식 계좌 보유 1페이지(20행, `get_stock_balance` GET): 000660 005930 005935 006340 006360 009830 010140 010170 017670 028050 030530 032820 034020 035420 035720 047040 058610 073240 098460 119850 (page_size=20 은 2026-08-05 P-BAL 실측). 현금배당은 ex leg 가 잔고면에서 관측 불가(`NOT_OBSERVABLE_ON_BALANCE_SURFACE`)라 **payable 시각의 `dnca_tot_amt` 변화(현금 leg)만** 관측 대상. 실행 명령(09-17 08:30 KST 경, 관측 창 8h, 창 동안 모의 주식 계좌 다른 활동 금지): `python -m tools.broker_probes.run P-CA --asset stock --symbol 017670 --event-class cash_dividend --payable-time 2026-09-17T00:00:00+09:00 --window-s 28800 --reference-check --confirm` |

앱키 공유 워커 점검(P-15/N-15 선행 조건): 실행 중인 `kis_paper-*` 컨테이너 중 모의 선물 앱키(지문 `f546a47adc88`)를 쓰는 것은 **0개** — paper 런타임(trader-futures · order-router · scheduler)은 실전 선물 앱키(`1d942a9ca6b3`)를 쓴다(2026-09-10 컨테이너 env 지문 대조). 따라서 N-15 는 워커 정지 없이 실행 가능하며 러너가 실행 시점에 같은 대조를 반복한다.

## 실행 기록

### 2026-09-10 (목) 야간 — 실전 GET 2건 (핸드오버 §2 행 6·7 · 런북 §5.4)

별도 서브셸에서 `.env.real` 소싱(값 미출력) → 실행 → 서브셸 종료. 실전 선물 계좌 지문 `8304d859b87f`(마스킹 `43******03`, 운영자 확정 `03` 계좌, 예수금·증거금 의도적 0 — never-fund). `repo_commit` `296c0e5f`. stdout 사본 `n16-n18-20260910-stdout.log` 은 서버의 gitignored `results/` 에 남아 있고 이 디렉터리에는 포함되지 않는다(런북 §6.3 은 아티팩트 JSON 만 복사 대상으로 둔다).

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 20:15:08 | N-16 | `N-16-20260910T111508Z.json` | live / MEASURED / REAL_PROD | [] / [] | `CTFN6118R` HTTP 200 · `rt_cd=0` · `KIOK0530`. `output1` 0행(야간 포지션 없음 = 설계 상태), `output2` 31키 스키마 포착. 행 스키마는 여전히 미확립 — 빈 응답 ≠ 빈 스키마(아티팩트 `empty_response_caveat`). 정책 종결(45735d2a) 전제 불변. |
| 20:15:08 | N-18 | `N-18-20260910T111508Z.json` | live / MEASURED / REAL_PROD | [] / [] | N-18a `FHPPG04600001` 150일 요청 → 단일 호출 102행(cap 여부는 범위 내 거래일 수 대조 후 판정, 아티팩트 `n18a_cap_determination`). N-18b `FHKST03030200`: 통제 leg `SPX` 102행 · `SOX` 102행(**표기 확정**) · `.SOX` / `^SOX` 0행(rt_cd 0 이나 빈 결과). N-18c `FHMIF10000000`: 주간 `A01612` `futs_prpr=1112.00` / `futs_prdy_clpr=1119.00` · 야간 `1A01612` `rt_cd=0` 이나 `futs_prpr`/`futs_prdy_clpr` **null** → REST 는 야간 세션 시세를 서비스하지 않음(WS-only 야간 캡처 설계 확인, `n18c_interpretation`). |

`approval_status` 는 전부 `UNAPPROVED_CANDIDATE`(§6.1). 인용 적격성(§6.2)은 개발 측 확인.

### 2026-09-11 (금) — 모의(MOCK_VTS) 블록

러너 `~/.config/kis-probes/run-p02-t3-20260911.sh`(`.env.mock` 만 소싱, 09:18 KST 시작 — 세션 스케줄 09:04 는 미발화, 운영자 수동 트리거): 계획은 **P-8 ×5** → **P-15** → **N-15** → **P-BAL**. `repo_commit` `7f3ffa52`, 작업트리 clean, `futures_live.enabled: false`, 앱키 공유 워커 0(러너 내장 지문 대조 `shared_workers=none`). 커버리지 `coverage-20260911.json`(포함). 러너 로그 `p02-t3-20260911-runner.log` 은 서버의 gitignored `results/` 에 남아 있고 이 디렉터리에는 포함되지 않는다.

**⛔ P-8 은 브로커가 거부** — 2회 모두 `rt_cd=1 모의투자 주문이 불가한 계좌입니다`(계좌 `60******03`, 지문 `5e175fd232de` = 2026-07-31 wave-3 에서 주문이 접수됐던 것과 **동일 계좌**; 앱키·토큰·조회는 정상). 모의 선물옵션 계좌의 **주문 권한이 만료/해지된 것**으로 판단 → 운영자가 KIS 모의투자(선물옵션) 재신청 후 P-8 ×5·P-EXT ×5 를 재실행해야 한다. 3~5회차는 건너뛰고(재시도 금지 규칙 준용) 주문과 무관한 P-15 → N-15 → P-BAL 만 이어서 실행했다.

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 09:18:17 | P-8 1/5 | `P-8-20260911T001817Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / [] | `submit rejected rt_cd=1 msg=모의투자 주문이 불가한 계좌입니다.` — 관측 0건 |
| 09:19:38 | P-8 2/5 | `P-8-20260911T001938Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / [] | 동일 거부. 3~5회차 미실행 |
| 09:22:31 | P-15 | `P-15-20260911T002231Z.json` | live / MEASURED / MOCK_VTS | [] / [] | 재발급 간격 5s → 2차 시도 **거부 HTTP 403**(`msg_cd`/`msg1` 없음 — 축자 본문 부재). 1차 `expires_in=86400`(브로커 반환값), 2차 null. |
| 09:22:39 | N-15 | `N-15-20260911T002239Z.json` | live / MEASURED / MOCK_VTS | [] / [] | `invalidate_to_reissue_ms` **107,228 ms(n=1)** → 후보 상한 160,843 ms(`candidate_only`, 값 아님). 토큰 endpoint 호출 4회, 거부가 30.9s gap 을 넘김. **held-token 사용성 ACCEPTED 3 / REJECTED 0 / UNDETERMINED 0** → 거부 창은 재발급 쿨다운이지 egress 블랙아웃이 아님(아티팩트 `interaction_verdict`; `B_egress_hard_fence` 기입 불가). 소요 108s(07-29 ≥528s 관측보다 짧음 — 표본 n=1). |
| 09:24:27 | P-BAL(모의 주식) | `P-BAL-20260911T002427Z.json` | live / MEASURED / MOCK_VTS | [] / [] | `VTTC8434R` 2페이지 walk, **양수 수량 25행 > page_size 20** (`P-BAL-20260911T002427Z.json:measurements.rows_with_positive_qty_total=25` · `P-BAL-20260911T002427Z.json:measurements.truncation_risk.page_row_counts=[20,5]` · `P-BAL-20260911T002427Z.json:measurements.truncation_risk.page_size=20`) → `P-BAL-20260911T002427Z.json:measurements.truncation_risk.verdict=TRUNCATION_RISK_DEMONSTRATED`(런타임은 1페이지만 읽음, `client.py:931-932`). 종료 원인 `P-BAL-20260911T002427Z.json:measurements.termination_cause=BROKER_END_OF_SET`(page 1 `tr_cont='D'`), `tr_cont` 헤더 관측, 연속조회 지원. 2026-08-05 측정과 일치. 계좌 `50******01`(`54e7f8a5d841`). |

### 2026-09-15 (화) 밤 — 모의투자 재신청 직후 연결 확인 (GET-only)

운영자가 21:1x 에 KIS 모의투자를 재신청해 **두 계좌 모두 새 번호**를 받았고 `.env.mock` 만 갱신했다(주식 `54e7f8a5d841`→`ee1bdb5f1ca2`, 선물 `5e175fd232de`→`46c39c54d3bb`; 백업 `~/.config/kis-probes/backups/.env.mock.bak-20260915-mock-reapply`). 앱키·시크릿은 바뀌지 않았다. 주문은 한 건도 내지 않았다.

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 21:16:51 | P-BAL(모의 주식) | `P-BAL-20260915T121651Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / 1 | 새 계좌 `ee1bdb5f1ca2` → `rt_cd=2 OPSQ2000 INPUT INVALID_CHECK_ACNO`. 토큰 발급 자체는 성공 |
| 21:16:55 | P-BAL(모의 선물) | `P-BAL-20260915T121655Z.json` | live / — / MOCK_VTS | [] / 1 | 모의는 선물 잔고 조회를 제공하지 않아 SKIP — 선물 계좌 연결 여부는 이 경로로 확인 불가 |
| 22:07:32 | P-BAL(모의 주식) | `P-BAL-20260915T130732Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / 1 | 동일 거부 |
| 22:09:55 | P-BAL(모의 주식) | `P-BAL-20260915T130955Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / 1 | **새 토큰 발급 후에도** 동일 거부 → 토큰 캐시 문제 아님 |
| 22:10:09 | P-BAL(**예전** 모의 주식) | `P-BAL-20260915T131009Z.json` | live / MEASURED / MOCK_VTS | [] / [] | 판별 실험: 같은 앱키로 **예전 계좌 `54e7f8a5d841` 는 정상 25행** → **앱키가 아직 예전 계좌에 묶여 있다**. (이 아티팩트의 `observations` 는 페이지별 행 수·`rt_cd`·연속조회 키만 담고 `pdno`/`raw_excerpt` 는 비어 있다 — 보유 종목 식별은 **이 아티팩트로 확인 불가**이며, SK텔레콤 017670 보유는 같은 계좌 지문의 별도 2026-08-05 측정에서 온 사실이다.) |

운영자 조치: KIS Developers 에서 키·시크릿·번호 일치 확인 후 **'재사용 신청'**, 선물은 **'초기화 신청'**(주문 거부가 주·야간 시간 문제일 가능성도 함께 제기). 09-16 09:00 재확인하기로 함. 판별 결과에 따라 **09-17 P-CA 1차 대상은 예전 계좌로 실행**하도록 복원(운영자 결정).

### 2026-09-16 (수) — 재신청 반영 재확인 (주식 GET + 선물 P-8 1회)

정규장 내(09:02 KST, 선물 08:45~15:45), `futures_live.enabled=false`, `futures:live:suspended` 미설정, 워크트리 clean, 실행 컨테이너 중 모의 선물 앱키(`f546a47adc88`) 공유 0 — 09-11 러너와 같은 가드. mini 근월물 `A05610`(`futures:contract:latest`, 만기 2026-10-08). `repo_commit` `1959656c`.

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 09:02:06 | P-BAL(모의 주식) | `P-BAL-20260916T000206Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / 1 | 새 계좌 `ee1bdb5f1ca2` → `rt_cd=2 OPSQ2000 INPUT INVALID_CHECK_ACNO` **변화 없음** |
| 09:02:36 | P-8 1/5 | `P-8-20260916T000236Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / [] | 새 선물 계좌 `46c39c54d3bb` → `submit rejected rt_cd=1 msg=인증 시점의 계좌번호와 요청 계좌번호가 일치하지 않습니다.` — **09-11 의 `모의투자 주문이 불가한 계좌입니다` 와 다른 문구**. 2~5회차 미실행(거부 시 중단 규칙) |

**해석(측정 아님):** 선물 거부 문구가 "주문 불가 계좌"에서 "인증 계좌 ≠ 요청 계좌"로 바뀐 것은, 토큰이 여전히 **예전 계좌**에 대해 발급되는데 요청만 새 번호로 나간다는 것과 정합적이다 — 주식의 `INVALID_CHECK_ACNO` 와 같은 원인(앱키↔새 계좌 미연결)으로 보인다. 토큰은 이 실행에서 새로 발급됐으므로(프로브 토큰 캐시 `results/.token_cache/futures/` 09:02 갱신) 캐시 노후가 아니다. 재사용/초기화 신청이 아직 반영되지 않았다는 뜻이며, **반영 시점은 브로커 측이라 관측만 가능**하다.

### 2026-09-17 (목) — P-CA 1차 (SK텔레콤 현금배당, **예전** 모의 주식 계좌)

운영자 결정(09-15)대로 `.env.mock` 은 새 계좌 그대로 두고 이 실행에만 예전 계좌번호를 넘겼다(지문 `54e7f8a5d841`, 마스킹 `50******01`). `repo_commit` `1959656c`, 워크트리 clean, `futures_live.enabled=false`. 운영자 attest: 창 동안 이 계좌에 다른 주문·입출금 없음.

**⚠ 예약 시각과 실제 실행 시각이 다르다.** 세션 예약은 08:31 KST 에 발화해 사전 확인(계좌 지문 일치·잔고 20행 정상, `P-BAL-20260916T233126Z.json` — 종목 식별은 이 아티팩트 범위 밖, 아래 표 주석 참조)까지 08:31 에 마쳤으나, 세션이 중단돼 **프로브 본체는 22:02:46 KST 에 실행**됐다. 프로브가 스스로 다시 읽은 baseline 도 `P-CA-20260917T130246Z.json:measurements.baseline.hldg_qty=1`(예수금 `P-CA-20260917T130246Z.json:measurements.baseline.dnca_tot_amt=6686725.0`원)로 같다. payable(00:00)은 두 시각 모두 이미 지난 뒤였지만, 창 8시간은 22:02→익일 06:02 로 밀렸다.

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 08:31:26 | P-BAL(사전 확인) | `P-BAL-20260916T233126Z.json` | live / MEASURED / MOCK_VTS | [] / [] | 예전 계좌 **20행 정상** — 초기화로 리셋되지 않음. ⚠ 이 아티팩트는 페이지별 행 수·`rt_cd`·연속조회 키만 담고 `pdno`/종목명/단가 필드가 **없다**(`raw_excerpt` 도 빈 문자열) — **어느 종목을 보유하는지는 이 아티팩트로 확인 불가**다. SK텔레콤 1주 보유는 아래 P-CA 본체의 `P-CA-20260917T130246Z.json:measurements.baseline.hldg_qty=1`(프로브가 `--symbol 017670` 로 스코프된 상태에서 스스로 읽은 값)이 뒷받침한다 |
| 22:02:46 | P-CA 1차 | `P-CA-20260917T130246Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / 2 | 아래 |

- **✅ `--reference-check` 는 성공 — 모의에서 CA 참조 TR 이 동작한다.** `mock_reference_support: SUPPORTED`. 반환 행: SK텔레콤 017670 · `divi_kind=분기` · `per_sto_divi_amt=830` · `record_date=20260831` · `divi_pay_dt=2026/09/17`. N-19 §3 의 "모의 CA 처리 여부 UNKNOWN" 중 **참조원 존부는 이 관측으로 해소**된다(값 인용은 §6.2 대로 MOCK 한정).
- **⛔ 현금 leg 는 CENSORED** — 폴링 #1 에서 브로커 rate-limit(`is_rate_limited`: HTTP 429 또는 `EGW00201`) → 중단 규칙대로 재시도 없이 종료, `polls_used=1`. **미관측이지 "반영 없음"이 아니다**(VP-002:772 'observed 0 != 0'). 직전 1.5초 안에 baseline 잔고 walk + 참조 조회가 나갔고 모의 조회 한도가 [1,2) rps 인 것과 정합적이나, 아티팩트가 축자 응답 본문을 남기지 않아 **429 인지 EGW00201 인지는 미확정**(하네스 갭).
- **ex leg 는 설계상 SKIP** — 기준가 조정은 잔고 TR 로 관측 불가(N-19 §2.3).
- `B_non_trade_event_detect` / `B_non_trade_reconcile` 두 키 모두 **NOT_ESTABLISHED 유지**.

이후 남은 것: **P-CA 재시도**(2차 대상 에스피지 058610 10-22, 또는 SK텔레콤 재실행 시 폴링 전 rate-limit 여유 확보), **P-EXT ×5**·**P-8 ×5**(모의 선물 주문 권한 복구 후, 운영자 MTS 동석).

### 2026-09-23 (수) — 계좌 연결 재확인 (GET/조회 전용 · 주문 0)

정규장 내(13:06~13:10 KST), `repo_commit` `c2b9761f`(main, PR #787), 워크트리 clean, `futures_live.enabled=false`, `futures:live:suspended` 미설정, 실행 컨테이너 중 모의 선물 앱키 공유 **0**(컨테이너 env 지문 대조 재수행), mini 근월물 `A05610`(`get_front_month_code(product="mini")`). 모의 호스트 `openapivts` 가 이날 느렸다 — 세션 셸의 `curl -w time_total` 3회가 5.2~8.5 s, 실전 호스트 0.1 s(**세션 관측, 아티팩트 없음** — 아티팩트 안의 근거는 `P-BAL-…040808Z` 의 `elapsed_ms: 6365.8` 과 1회차의 20 s ReadTimeout 이다). 목적은 09-15 재신청 계좌의 앱키 연결이 반영됐는지 보는 것이지 페이지네이션 측정이 아니다.

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 13:06:30 | P-BAL(모의 주식) | `P-BAL-20260923T040630Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / [] | `ReadTimeout`(read 20 s, `openapivts`) — 브로커 무응답, 계좌 판정 불가. §3 중단 규칙(rate-limit)과 다른 종류라 1회 재시도 |
| 13:08:08 | P-BAL(모의 주식) | `P-BAL-20260923T040808Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / 1 | 새 계좌 `ee1bdb5f1ca2` → `rt_cd=2 OPSQ2000 INPUT INVALID_CHECK_ACNO` — **09-15·09-16 과 변화 없음** |
| 13:09:18 | P-5b(모의 선물 · 미체결 조회) | `P-5b-20260923T040918Z.json` | live / **MEASURED(스탬프 오류)** / MOCK_VTS | [] / 1 | 새 선물 계좌 `46c39c54d3bb` → page 0 **`rt_cd=2`** 행 0. ⚠ **아티팩트의 `MEASURED` 스탬프와 `continuation_supported: false` · `page_size_observed: 0` · `pages_walked: 1` 은 브로커가 거부한 호출에서 나온 값이라 인용 불가** — 프로브가 `rt_cd≠0` 를 오류로 기록하지 않고(`probes_order.py` 에 `rt_cd≠0 → run.error` 경로 없음, `common.py:617-621` 이 빈 errors 를 MEASURED 로 읽음) `msg_cd`/`msg1` 도 남기지 않아(P-BAL 은 둘 다 기록) 거부 문구 **미확정**. 주식 쪽과 같은 원인(앱키↔새 계좌 미연결)과 정합적이나 측정은 아니다 |
| 13:10:10 | P-5b 재실행(stdout 전량 캡처) | `P-5b-20260923T041010Z.json` | 동일 | 동일 | stdout 에도 브로커 문구 없음 — 갭은 아티팩트가 아니라 프로브 코드(`probes_order.py::probe_p5b`) |

**해석(측정 아님):** 재사용/초기화 신청(09-15 21:1x) 후 8일이 지났지만 앱키는 여전히 예전 계좌에 묶여 있다. **P-8 ×5·P-EXT ×5 차단 유지.** 운영자가 KIS Developers 에서 연결 상태를 확인하기 전까지 같은 GET 을 반복하는 것은 정보가 없다. 후속 후보(비차단): P-5b 가 `rt_cd≠0` 를 `errors` 에 넣고 `msg_cd`/`msg1` 을 기록하도록 — 「거부를 MEASURED 로 적는」 모양은 #732 가 P-CA 에서 고친 것과 같은 부류다.

### 2026-09-23 (수) 저녁 — 운영자 「앱키 연결 확인」 통보 직후 재조회 (GET-only · 주문 0)

운영자가 18:4x KST 에 KIS Developers 에서 모의 계좌의 앱키 연결을 확인했다고 알렸다. `repo_commit` `c1c9bffa`(main, PR #790),
워크트리 clean(추적 파일 기준), `.env.mock` 무변경(09-15 21:16 이후), 실행 컨테이너 중 모의 주식(`7763f26aac49`)·선물(`f546a47adc88`)
앱키 공유 **0**(컨테이너 env 지문 대조). 목적은 연결 반영 여부 하나다.

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 18:49:40 | P-BAL(모의 주식) | `P-BAL-20260923T094940Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / 1 | `ee1bdb5f1ca2` → `rt_cd='2' msg_cd='OPSQ2000' msg1='ERROR : INPUT INVALID_CHECK_ACNO'`(아티팩트 `errors[0]`). 이때 쓰인 토큰은 **13:06 발급 캐시**(연결 통보 이전) |
| 18:50:26 | P-BAL(모의 주식) | `P-BAL-20260923T095026Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / 1 | 13:06 토큰을 `results/.token_cache/stock/.kis_token_mock.pre-relink-20260923-1852` 로 옮기고 **새 토큰(18:50:27 발급)** 으로 재조회 → **같은 거부**(`errors[0]` 동일 문구) |
| 18:56:31 | P-BAL(**예전** 모의 주식) | `P-BAL-20260923T095631Z.json` | live / MEASURED / MOCK_VTS | [] / [] | 판별 실험(09-15 22:10 과 같은 방식): 같은 앱키로 **예전 계좌 `54e7f8a5d841` 는 정상** — `termination_cause: BROKER_END_OF_SET`, 페이지 행 수 `[20, 5]`(`measurements.truncation_risk.page_row_counts`). 계좌번호만 이 실행에서 백업 값으로 오버라이드 |

**해석(측정 아님):** 새 토큰으로도 새 계좌는 거부되고 같은 앱키로 예전 계좌는 조회된다 — **앱키가 여전히 예전 주식 계좌에 묶여 있다**(09-15 판별과 같은 결과). 토큰 캐시 노후는 원인이 아니다. 운영자가 연결을 확인한 앱·계좌가 `.env.mock` 의 앱키·새 계좌와 같은지는 운영자만 대조할 수 있다.
선물 계좌는 모의 잔고 조회 경로가 없어(P-BAL 선물 SKIP) 이 방법으로 판정할 수 없다.

**다음 실행:** P-8 ×5 를 **2026-09-28(월) 09:05 KST 호스트 cron** 으로 예약했다(`~/.config/kis-probes/run-p8-20260928.sh`,
09-24~26 추석 휴장). 러너는 `origin/main` 분리 워크트리에서 돌고, 계좌 지문 `46c39c54d3bb` · 앱키 공유 0 · `futures_live.enabled=false`
를 확인한 뒤 **P-8 1회차 자체를 연결 게이트**로 쓴다 — 1회차가 거부되면 2~5회차를 돌지 않는다(§3 재시도 금지). 근월물은 당일
`get_front_month_code(product="mini")` 로 뽑는다(09-28 기준 `A05610`). 결과는 브리핑 텔레그램으로 보고되고 아티팩트는 이 디렉터리로
복사된다. P-EXT ×5 는 운영자 MTS 동석이 필요해 러너 밖이다.

### 2026-09-23 (수) 19:1x — 운영자 모의 앱키·시크릿 교체 후 연결 확인 (GET/조회 전용 · 주문 0)

운영자가 19:13 KST 에 `.env.mock` 의 **앱키·시크릿을 새 계좌용으로 교체**했다(계좌 번호는 그대로). 새 주식 앱키 지문
`537989e9e63e`, 새 선물 앱키 지문 `39a004459922`(예전 `7763f26aac49` · `f546a47adc88`). 실행 컨테이너 중 새 키 공유 **0**.
예전 키로 발급된 프로브 토큰 캐시는 `results/.token_cache/{stock,futures}/.kis_token_mock.oldkey-20260923-1915` 로 옮겼다.
`repo_commit` **`d6d77caa`**(아티팩트 4건의 기록값) — ⚠ main 커밋이 아니다. 실행 당시 공유 체크아웃이 문서 전용 브랜치
`docs/tos-c2-kis-credential-ownership`(main `c1c9bffa` 위 문서 커밋 2개)에 있었다. `git diff c1c9bffa d6d77caa` 는
`docs/plans/` 두 파일뿐이라 프로브·`shared/`·`tos/` 코드는 main `c1c9bffa` 와 같다. 앞으로 프로브는 분리 워크트리에서 돌린다.

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 19:17:26 | P-BAL(모의 주식, 새 계좌) | `P-BAL-20260923T101726Z.json` | live / MEASURED / MOCK_VTS | [] / 1 | **새 키 + 새 계좌 `ee1bdb5f1ca2` 정상** — `termination_cause: BROKER_END_OF_SET`, 페이지 행 수 `[0]`(보유 0 — skip 1 은 「페이지네이션할 행 없음」). 거부 없음 |
| 19:17:48 | P-5b(모의 선물 · 미체결 조회, 새 계좌) | `P-5b-20260923T101748Z.json` | live / MEASURED / MOCK_VTS | [] / 1 | **새 선물 계좌 `46c39c54d3bb` → `observations[0].rt_cd = "0"`**, 행 0(미체결 없음). 13:09 의 `rt_cd = "2"` 에서 바뀜. ⚠ P-5b 는 거부를 errors 에 넣지 않으므로(위 13:09 행) 판정 근거는 스탬프가 아니라 `rt_cd` 다 |
| 19:18:19 | P-BAL(예전 주식 계좌, **새 키**) | `P-BAL-20260923T101819Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / 1 | 예전 계좌 `54e7f8a5d841` 은 새 키로 `OPSQ2000 INVALID_CHECK_ACNO` — 새 키는 새 계좌에만 묶여 있다 |
| 19:18:38 | P-BAL(예전 주식 계좌, **예전 키**) | `P-BAL-20260923T101838Z.json` | live / MEASURED / MOCK_VTS | [] / [] | 09-15 백업의 자격증명 한 벌(키·시크릿·계좌) + 전용 토큰 캐시로 정상 `[20, 5]` — 예전 앱은 아직 살아 있다 |

**결론(측정):** 새 모의 계좌 둘 다 새 키로 조회가 된다. 09-15 이후 막혀 있던 원인은 **계좌에 맞는 앱키를 쓰지 않은 것**이었다
— 재신청 후 계좌와 연결된 것은 새로 발급된 앱이고, `.env.mock` 은 예전 앱의 키를 들고 있었다.

**후속 조치:**

- **P-8 ×5(09-28 09:05 cron)** 는 실행 시점에 `.env.mock` 을 읽으므로 새 키를 그대로 쓴다. 1회차 게이트는 유지한다.
- **P-CA 2차(09-30 cron)** 는 예전 계좌를 관측해야 하므로, 러너 `~/.config/kis-probes/run-p-ca-20260930.sh` 가 이제
  **자격증명 한 벌 전체를 09-15 백업에서** 읽고(예전 키 지문 `7763f26aac49` 가드), 전용 토큰 캐시
  `~/.config/kis-probes/p-ca-20260930-token-cache` 를 쓴다(운영자 결정 2026-09-23). 러너의 보유 사전 확인을 같은 조건으로 돌려
  **000660 보유 1주**를 확인했다. **예전 앱을 09-30 전에 삭제하면 P-CA 2차는 보유 확인에서 중단된다.**

### 2026-09-28 (월) — P-8 재실행 (호스트 cron · 분리 워크트리)

09-23 19:1x 앱키 교체 뒤 첫 주문 계열 재실행. 예고대로 호스트 cron 러너가 **분리 워크트리**(detached `origin/main`, 로그 표현 "clean by construction")에서 돌렸다 — 로그 `repo_commit=ac2efb0f2b1698b87cac4d927886583c77e5357a`, 아티팩트 `P-8-20260928T000506Z.json:repo_commit=ac2efb0f`. 러너 가드(로그): `futures:live:suspended=''` · 모의 선물 앱키 지문 `39a004459922`(09-23 교체분) · `shared_workers=none` · 선물 계좌 지문 `46c39c54d3bb` · mini 근월물 `A05610`. 아티팩트 쪽 같은 값: `P-8-20260928T000506Z.json:credentials.account_fingerprint=46c39c54d3bb` · `P-8-20260928T000506Z.json:credentials.account_masked=60******03` · `P-8-20260928T000506Z.json:args.symbol=A05610`. 로그 `~/.config/kis-probes/p8-20260928.log`.

**✅ 09-15 재신청 계좌에서 처음으로 주문이 접수됐다(09-11 이후 처음).** 09-11 의 `모의투자 주문이 불가한 계좌입니다`·09-16 의 `인증 시점의 계좌번호와 요청 계좌번호가 일치하지 않습니다` 거부가 사라지고 제출·정정·취소가 전부 통과했다 — `P-8-20260928T000506Z.json:observations[0].amend_rt_cd=0` · `P-8-20260928T000506Z.json:observations[0].amend_msg=모의투자 정정주문이 완료 되었습니다.`. **이로써 09-11 부터 세 번 막혔던 P-8 의 차단 사유(주문 권한)는 해소됐다.** ⚠ 「모의 선물 주문이 **처음** 접수됐다」는 뜻이 아니다 — 2026-07-31 wave-3 에서 **예전** 모의 선물 계좌(지문 `5e175fd232de`, 위 09-11 절)로 P-8 5회가 모두 접수돼 replace 를 측정했다(`P-8-20260731T015220Z` … `P-8-20260731T020121Z`; `tools/broker_probes/probes_order.py::_cleanup` 독스트링). 이번 관측이 새로 말하는 것은 **새 계좌에서도 주문이 받아들여진다**는 것뿐이다.

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 09:05:06 | P-8 1/5 | `P-8-20260928T000506Z.json` | live / **MEASURED** / MOCK_VTS | [] / [] | 지정가 `P-8-20260928T000506Z.json:measurements.limit_price_tick.wire_value=1002.22`(unrounded `P-8-20260928T000506Z.json:measurements.limit_price_tick.unrounded=1002.2399999999999`, `P-8-20260928T000506Z.json:measurements.limit_price_tick.tick_size=0.02`, `P-8-20260928T000506Z.json:measurements.limit_price_tick.rounding=floor`) → 정정 `P-8-20260928T000506Z.json:measurements.amend_price_tick.wire_value=992.18`(unrounded `P-8-20260928T000506Z.json:measurements.amend_price_tick.unrounded=992.1978`). 원 ODNO `P-8-20260928T000506Z.json:observations[0].original_odno=0000000512` → 신 ODNO `P-8-20260928T000506Z.json:observations[0].new_odno=0000000513` @ `P-8-20260928T000506Z.json:observations[0].new_price=992.18`. `P-8-20260928T000506Z.json:measurements.replace_issues_new_odno=true` · `P-8-20260928T000506Z.json:measurements.replace_rejected=false` · `P-8-20260928T000506Z.json:measurements.coexistence_ms=0.0` (폴 간격 `P-8-20260928T000506Z.json:measurements.poll_granularity_ms=1100.0`). 소요 `P-8-20260928T000506Z.json:duration_s=36.791` s |
| 09:06:58 | P-8 2/5 | `P-8-20260928T000658Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / [] | 지정가 `P-8-20260928T000658Z.json:measurements.limit_price_tick.wire_value=1005.26`(unrounded `P-8-20260928T000658Z.json:measurements.limit_price_tick.unrounded=1005.264`) → 정정 `P-8-20260928T000658Z.json:measurements.amend_price_tick.wire_value=995.2`(unrounded `P-8-20260928T000658Z.json:measurements.amend_price_tick.unrounded=995.2074`), `P-8-20260928T000658Z.json:observations[0].amend_rt_cd=0`, ODNO `P-8-20260928T000658Z.json:observations[0].original_odno=0000000558` → `P-8-20260928T000658Z.json:observations[0].new_odno=0000000560`. 정정은 통과했고 **공존 폴링도 최소 1회 돌았다**(아래 재구성). 그 폴링 도중 `P-8-20260928T000658Z.json:errors[0]=ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))` 가 나서 루프 다음의 집계가 기록되지 않았다 — 이 아티팩트에는 `coexistence_ms`·`replace_issues_new_odno`·`poll_granularity_ms` 가 **없다**. 정리 취소는 그 뒤 `finally` 에서 성공했다. 소요 `P-8-20260928T000658Z.json:duration_s=33.363` s |

- **ODNO 표기 비대칭 재확인(양쪽 정규화 필요).** 제출 응답은 zero-pad, 조회 행은 space-pad 다 — 1회차 제출 `P-8-20260928T000506Z.json:measurements.odno_wire_format.submit_response_samples[0].verbatim=0000000512` · `P-8-20260928T000506Z.json:measurements.odno_wire_format.submit_response_samples[1].verbatim=0000000513` vs 조회 행 `P-8-20260928T000506Z.json:measurements.odno_wire_format.query_row_samples[0].verbatim=       513` · `P-8-20260928T000506Z.json:measurements.odno_wire_format.query_row_samples[1].verbatim=       512` (2회차도 같은 형태, 조회 행 3건 `P-8-20260928T000658Z.json:measurements.odno_wire_format.query_row_samples[0].verbatim=       560` · `P-8-20260928T000658Z.json:measurements.odno_wire_format.query_row_samples[1].verbatim=       558` · `P-8-20260928T000658Z.json:measurements.odno_wire_format.query_row_samples[2].verbatim=       528`). 아티팩트 `odno_wire_format.scope` 가 못박은 대로 **모의 계좌 1개·세션 1회의 관측이며 실전으로 외삽하지 않는다**.
- **정정 뒤 원 주문은 취소할 수량이 남지 않는다.** 1회차 정리 취소 `P-8-20260928T000506Z.json:observations[1].ok=false` · `P-8-20260928T000506Z.json:observations[1].msg=모의투자 정정/취소할 수량이 없습니다.` · `P-8-20260928T000506Z.json:observations[1].disposition=NOTHING_TO_CANCEL_NO_LIVE_ROW`, liveness 증거 `P-8-20260928T000506Z.json:observations[1].liveness_evidence.pages_walked=1` 페이지 / `P-8-20260928T000506Z.json:observations[1].liveness_evidence.rows_seen=2` 행 / `P-8-20260928T000506Z.json:observations[1].liveness_evidence.outcome=COMPLETE_WALK`; 신 ODNO 쪽은 `P-8-20260928T000506Z.json:observations[2].disposition=CANCELLED`. 2회차도 같은 형태(`P-8-20260928T000658Z.json:observations[1].disposition=NOTHING_TO_CANCEL_NO_LIVE_ROW`, `P-8-20260928T000658Z.json:observations[1].liveness_evidence.rows_seen=5` 행; `P-8-20260928T000658Z.json:observations[2].disposition=CANCELLED`). `P-8-20260928T000506Z.json:measurements.original_not_cancellable_after_amend=true` 이지만 아티팩트 `amend_consumption_note` 가 못박은 대로 **체결도 똑같은 관측을 낳으므로 이 필드는 구조적 사실만 말하고 원인을 지목하지 않는다**(P-8 은 체결 조회를 하지 않는다).
- **2회차가 끊긴 지점은 「정정·취소 뒤」가 아니라 「공존 폴링 도중」이다(아티팩트 기반 재구성).** `record_odno_wire_format` 은 공존 폴 루프 안(`tools/broker_probes/probes_order.py:1923`)에서만 불리고 `_cleanup`(`:1430`)은 부르지 않는다. 2회차 아티팩트에 `measurements.odno_wire_format.query_row_samples` 3행이 있다는 것은 **루프가 최소 1회 돌았다**는 뜻이고, 루프 **다음** 줄인 `replace_issues_new_odno`·`replace_rejected`·`coexistence_ms` 가 없다는 것은 루프 안에서 끊겼다는 뜻이다. 정리 취소는 `probe_p8` 의 `finally` 에서 돌아 `P-8-20260928T000658Z.json:observations[1].liveness_evidence.outcome=COMPLETE_WALK` 로 끝났다. 순서: 정정 수락 → 공존 폴 ≥1회 → `inquire-ccnl` 폴에서 ConnectionError → `finally` 정리 성공. **불안정한 면은 `inquire-ccnl` 이고, 전송은 수 초 안에 회복했다.**
- **⛔ 판정에는 못 쓴다.** 아티팩트 `mode_determination`: "Map to ReplaceSemantics only after N>=5 trials agree. A single trial showing zero coexistence does NOT prove atomicity — polling can miss an interval shorter than poll_granularity_ms". 여기서 MEASURED 는 1회뿐이고 2회차는 연결 오류로 끊겼다. 러너 판정은 `VERDICT: STOP: P-8 2/5 오류 1건(브로커 거부 포함) — 1/5 성공 후 중단(재시도 금지)`(로그) → **3~5회차 미실행**. 따라서 `capabilities.replace_semantics.mode` 기입 불가, `B_protective_request_complete` **NOT_ESTABLISHED 유지**. ⚠ **다만 이 중단은 러너가 전송 오류와 브로커 거부를 한데 묶은 결과다.** `VERDICT` 문구부터 "오류 1건(브로커 거부 포함)"인데 실제로 난 것은 거부가 아니라 `ConnectionError` 였다. 같은 캠페인의 09-23 절은 정반대로 분류했다 — `ReadTimeout` 을 "§3 중단 규칙(rate-limit)과 다른 종류라 1회 재시도". 이 불일치를 기록해 둔다: **3~5회차가 미실행인 것은 브로커가 막아서가 아니라 러너가 전송 오류에 멈췄기 때문이다.**
- `approval_status` 두 건 모두 `P-8-20260928T000506Z.json:approval_status=UNAPPROVED_CANDIDATE` / `P-8-20260928T000658Z.json:approval_status=UNAPPROVED_CANDIDATE`.

### 2026-09-30 (수) — P-CA 2차 (SK하이닉스 현금배당) — **3회 모두 ABORT**

대상은 SK하이닉스 `P-CA-20260930T015946Z.json:args.symbol=000660` `P-CA-20260930T015946Z.json:args.event_class=cash_dividend` `P-CA-20260930T015946Z.json:args.payable_time=2026-09-30T00:00:00+09:00` — 위 표의 2차 후보(에스피지 058610)보다 지급일이 일러 먼저 실행했다. 계좌는 09-17 과 같은 **예전** 모의 주식 계좌 `P-CA-20260930T015946Z.json:credentials.account_fingerprint=54e7f8a5d841` · `P-CA-20260930T015946Z.json:credentials.account_masked=50******01` 이고, 09-23 키 교체 뒤라 예고(위 09-23 19:1x 절)대로 **09-15 백업의 자격증명 한 벌**(예전 앱키 지문 `7763f26aac49`, 로그 확인)과 전용 토큰 캐시 `P-CA-20260930T015946Z.json:args.token_cache_dir=/home/deploy/.config/kis-probes/p-ca-20260930-token-cache` 를 썼다. GET-only — 아티팩트 `read_only_attestation` 이 잔고 2 TR + ksdinfo 참조 12 TR 허용목록을 적고 모듈에 주문 경로가 없음을 밝힌다. `P-CA-20260930T015946Z.json:repo_commit=aec37535`. 로그 `~/.config/kis-probes/p-ca-20260930.log`.

⚠ **이 실행은 분리 워크트리가 아니라 공유 main 체크아웃 `/home/deploy/project/kis_unified_sts` 에서 돌았다** — 러너의 `REPO` 변수가 그 경로이고 아티팩트도 그 아래 `tools/broker_probes/results/` 에 떨어진 뒤 이 디렉터리로 복사됐다. 러너가 매 START 앞에서 `git status --short` 가 비었는지 보고 비지 않으면 중단하므로(00:20 의 `ABORT: worktree dirty` 가 바로 그 가드다) 세 실행 모두 **작업트리 clean** 이었고, HEAD `P-CA-20260930T015946Z.json:repo_commit=aec37535` 은 그 시각의 `origin/main` 이다(2026-09-30 10:00:56 KST 머지, 첫 실행 58분 전). 그래도 **#793 의 「프로브는 분리 워크트리에서」 규칙은 지켜지지 않았다** — 09-23 절이 "앞으로 프로브는 분리 워크트리에서 돌린다"고 적었는데 운영자 cron 러너가 공유 체크아웃 경로로 하드코딩돼 있었다. 병렬 레인이 10:00~12:47 사이에 그 체크아웃의 브랜치를 바꿨다면 비-main 커밋이 아티팩트에 찍히고 README 에는 아무 흔적도 남지 않았을 것이다. **다음 프로브 전에 고쳐야 할 러너 결함이다.**

러너 로그의 ABORT/START/END 줄(시각 KST, 아티팩트 아님):

| 시각(KST) | 로그 줄 | 결과 |
|---|---|---|
| 00:20:01 | `ABORT: worktree dirty` | 아티팩트 없음(호스트 cron 1차). 원인은 main 체크아웃의 untracked `.claude/settings.local.json.bak.*` — 증거 파일이 아니라 설정 백업이어서 `~/.claude/backups/` 로 옮겼다 |
| 10:58:37 | `held qty(000660)=0` → `ABORT: 000660 not held (or balance query rejected) — nothing to observe` | 아티팩트 없음. 로그에 남은 것은 `held qty(000660)=0` 과 러너 자신의 유보 문구 "(or balance query rejected)" 뿐이다. **해석(측정 아님):** 10:58:05→10:58:37 의 32초는 `rt_cd≠0` 거부와 20 s `ReadTimeout`(같은 날 3·4차의 실패 모드) 어느 쪽과도 맞고, 축자 응답이 없어 **둘 중 어느 것인지 확정할 수 없다**. 「보유 0」이 아니라는 근거는 따로 있다 — 같은 자격증명으로 11:00 경 돌린 확인용 직접 GET 이 11.9 초 만에 20행과 `000660` 수량 1 을 반환했다 |
| 10:59:46 | `=== START P-CA 000660 window=21018s poll=30000ms pace=1.5s` | → `P-CA-20260930T015946Z.json` |
| 11:06:27 | `=== END P-CA rc=0` | |
| 11:27:35 | `=== START P-CA 000660 window=19351s poll=30000ms pace=1.5s (attempt 3)` | → `P-CA-20260930T022735Z.json` |
| 11:31:34 | `=== END P-CA rc=5` | |
| 12:47:27 | `=== START P-CA 000660 window=14554s poll=30000ms pace=1.5s (attempt 3)` | → `P-CA-20260930T034727Z.json`. 로그의 "attempt 3" 은 스크래치 러너의 START 줄을 안 고친 것이고, 아티팩트 `P-CA-20260930T034727Z.json:args.note` 는 **attempt 4** 로 적는다 |
| 12:47:48 | `=== END P-CA rc=5` | |

| 시각(KST) | 시도 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 10:59:46 | 2 | `P-CA-20260930T015946Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / 2 | 폴 `P-CA-20260930T015946Z.json:measurements.polls_completed=13` 회 완료, `P-CA-20260930T015946Z.json:measurements.polls_used=14` 번째에서 거부 — `P-CA-20260930T015946Z.json:errors[0]=poll #14 rejected: rt_cd='1' msg_cd='EGW00215'`. 창 `P-CA-20260930T015946Z.json:args.window_s=21018.0` s 중 `P-CA-20260930T015946Z.json:measurements.polled_elapsed_s=394.072` s 만 돌았다. 소요 `P-CA-20260930T015946Z.json:duration_s=401.343` s |
| 11:27:35 | 3 | `P-CA-20260930T022735Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / 1 | baseline·참조 조회 뒤 폴 `P-CA-20260930T022735Z.json:observations[11].poll.index=7` 건까지 기록하고 `P-CA-20260930T022735Z.json:errors[0]=ReadTimeout: HTTPSConnectionPool(host='openapivts.koreainvestment.com', port=29443): Read timed out. (read timeout=20.0)`. 창 `P-CA-20260930T022735Z.json:args.window_s=19351.0` s. 소요 `P-CA-20260930T022735Z.json:duration_s=238.674` s |
| 12:47:27 | 4 | `P-CA-20260930T034727Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / [] | `P-CA-20260930T034727Z.json:errors[0]=ReadTimeout: HTTPSConnectionPool(host='openapivts.koreainvestment.com', port=29443): Read timed out. (read timeout=20.0)` — `measurements` 가 비어 있고 `baseline_call`·`reference_dates` 관측도 없다(남은 관측은 read-only 진술과 t0 오프셋 2건뿐) → **첫 조회 단계에서 끊겨 폴 0회**. 창 `P-CA-20260930T034727Z.json:args.window_s=14554.0` s. 소요 `P-CA-20260930T034727Z.json:duration_s=20.446` s |

- **✅ `--reference-check` 는 2·3차 시도 모두 성공 — `P-CA-20260930T015946Z.json:observations[4].mock_reference_support=SUPPORTED` · `P-CA-20260930T022735Z.json:observations[4].mock_reference_support=SUPPORTED`.** 09-17 SK텔레콤에 이은 두 번째 확인이다. 2차 반환 행: `P-CA-20260930T015946Z.json:observations[3].reference_dates[0].sht_cd=000660` · `P-CA-20260930T015946Z.json:observations[3].reference_dates[0].isin_name=에스케이하이닉스` · `P-CA-20260930T015946Z.json:observations[3].reference_dates[0].divi_kind=분기` · `P-CA-20260930T015946Z.json:observations[3].reference_dates[0].face_val=5000` · `P-CA-20260930T015946Z.json:observations[3].reference_dates[0].per_sto_divi_amt=375` · `P-CA-20260930T015946Z.json:observations[3].reference_dates[0].divi_rate=7.50` · `P-CA-20260930T015946Z.json:observations[3].reference_dates[0].stk_divi_rate=0.00` · `P-CA-20260930T015946Z.json:observations[3].reference_dates[0].record_date=20260831` · `P-CA-20260930T015946Z.json:observations[3].reference_dates[0].divi_pay_dt=2026/09/30` · `P-CA-20260930T015946Z.json:observations[3].reference_dates[0].stk_kind=보통`(`stk_div_pay_dt`·`odd_pay_dt`·`high_divi_gb` 는 빈 문자열). 값 인용은 §6.2 대로 MOCK 한정이다.
- **⛔ 2차 시도 — 현금 leg 는 `ABORTED` 다.** `class_leg_table` 행: `P-CA-20260930T015946Z.json:measurements.class_leg_table[0].status=ABORTED` · `P-CA-20260930T015946Z.json:measurements.class_leg_table[0].window_s=21018.0` · `P-CA-20260930T015946Z.json:measurements.class_leg_table[0].polled_elapsed_s=394.072` · `P-CA-20260930T015946Z.json:measurements.class_leg_table[0].stop_reason=rejected` · `P-CA-20260930T015946Z.json:measurements.class_leg_table[0].polls_used=14` · `P-CA-20260930T015946Z.json:measurements.class_leg_table[0].polls_completed=13` · `P-CA-20260930T015946Z.json:measurements.leg_provenance_class=NOT_MEASURED`. skip 사유(축자): `P-CA-20260930T015946Z.json:skips[1].reason=ABORTED — polling stopped early (stop_reason=rejected, polls_used=14 (attempts), polls_completed=13); polling ran 394.072s, so --window-s=21018.0s did NOT elapse. This is not even a censored observation: the window never ran, so nothing at all was observed about this leg. See the poll_stop_evidence observation for the broker's verbatim response.`
  - 브로커 응답(축자): `P-CA-20260930T015946Z.json:observations[18].poll_stop_evidence.http_status=500` · `P-CA-20260930T015946Z.json:observations[18].poll_stop_evidence.rt_cd=1` · `P-CA-20260930T015946Z.json:observations[18].poll_stop_evidence.msg_cd=EGW00215` · `P-CA-20260930T015946Z.json:observations[18].poll_stop_evidence.msg1=원장에서 허용 가능한 초당 거래건수를 초과하였습니다.` · `P-CA-20260930T015946Z.json:observations[18].poll_stop_evidence.body_excerpt={"rt_cd":"1","msg1":"원장에서 허용 가능한 초당 거래건수를 초과하였습니다.","msg_cd":"EGW00215"}`
  - **09-17 1차의 하네스 갭이 이 경로에서는 닫혔다** — 1차는 "429 인지 `EGW00201` 인지 미확정"으로 남았는데 여기서는 축자 본문이 아티팩트에 있다. 그리고 코드는 1차 때 추정했던 `EGW00201`(앱키 유량)도 HTTP 429 도 아닌 **`EGW00215`(원장 초당 거래건수)** 였다.
  - **해석(측정 아님).** 폴 간격은 `P-CA-20260930T015946Z.json:measurements.poll_interval_ms_effective=30000.0` (요청 `P-CA-20260930T015946Z.json:args.poll_ms=30000.0` · 페이싱 `P-CA-20260930T015946Z.json:args.pace_s=1.5`)였다. 이 계좌를 건드린 호출을 다 세면 — 10:58:04 러너 사전 확인 GET 1회, 10:59:46 attempt 2 의 baseline walk, 11:00 경 확인용 진단 GET 1회 — **60초를 넘는 구간에 3회**이고 그 뒤 폴은 30초 간격이다. 상주 프로세스도 없다: 이 계좌 `P-CA-20260930T015946Z.json:credentials.account_fingerprint=54e7f8a5d841` 를 쓰는 것은 이 호스트에 없다(paper 스택 계좌 지문 `a43943c80cc3`, 현재 `.env.mock` `ee1bdb5f1ca2`). 그래서 「초당 거래건수 초과」를 우리 호출률로 설명하기는 어렵다 — 이것은 **소거 논증**이지 모의 서버 원장의 공유 스로틀을 관측한 것이 아니다. ⚠ 진단 GET 은 attempt 2 의 폴링 창(10:59:46 시작) **안에** 들어갔다. 읽기 전용이라 잔고를 바꾸지는 않지만 호출 수에는 들어가므로 여기 적어 둔다.
- **3·4차는 같은 전송 오류다** — `P-CA-20260930T022735Z.json:errors[0]=ReadTimeout: HTTPSConnectionPool(host='openapivts.koreainvestment.com', port=29443): Read timed out. (read timeout=20.0)`. 3차는 폴 `P-CA-20260930T022735Z.json:observations[11].poll.index=7` 건까지 남겼고(4차 아티팩트 `P-CA-20260930T034727Z.json:args.note` 가 이를 "attempt 3 (11:27) ABORTED poll #8 ReadTimeout 20s on openapivts" 로 적는다), 4차는 baseline 조차 남기지 못했다.
- **ex leg 는 설계상 SKIP**(2·3차): `P-CA-20260930T015946Z.json:skips[0].what=legs.cash_dividend.ex` — `P-CA-20260930T015946Z.json:skips[0].reason=NOT_OBSERVABLE_ON_BALANCE_SURFACE — 기준가 조정은 잔고 TR로 관측 불가(N-19 §2.3: 주식잔고조회 72필드 중 가격 필드 없음); 현금 leg만 관측 가능.` 4차는 그 단계 전에 끊겨 `skips` 가 비어 있다.
- **⛔ 판정: P-CA 2차 = ABORTED ×3(전부 브로커 측 일시 오류) — 현금 leg 미관측.** **CENSORED 가 아니다** — 09-17 1차는 창이 돌다가 잘린 CENSORED 였지만, 여기서는 2차 아티팩트가 스스로 "This is not even a censored observation: the window never ran" 이라 적었다. 남은 유일한 관측은 **10:59:46 ~ 11:31 KST 사이 baseline 2건 + 폴 20건(13+7)이 전부 같은 값**이라는 것뿐이다 — `P-CA-20260930T015946Z.json:measurements.baseline.hldg_qty=1` · `P-CA-20260930T015946Z.json:measurements.baseline.dnca_tot_amt=6686725.0` 로 시작해 `P-CA-20260930T015946Z.json:observations[17].poll.hldg_qty=1` · `P-CA-20260930T015946Z.json:observations[17].poll.dnca_tot_amt=6686725.0` (2차 마지막 폴), `P-CA-20260930T022735Z.json:measurements.baseline.dnca_tot_amt=6686725.0` (3차 baseline), `P-CA-20260930T022735Z.json:observations[11].poll.dnca_tot_amt=6686725.0` (3차 마지막 폴)로 끝난다. 이 예수금 값은 09-17 1차 baseline 과도 같다. **변화가 없었다는 것이 「배당이 반영되지 않았다」는 뜻은 아니다**(VP-002:772 'observed 0 != 0').
- `B_non_trade_event_detect` / `B_non_trade_reconcile` 두 키 모두 **NOT_ESTABLISHED 유지**. `approval_status` 세 건 모두 `P-CA-20260930T015946Z.json:approval_status=UNAPPROVED_CANDIDATE` · `P-CA-20260930T022735Z.json:approval_status=UNAPPROVED_CANDIDATE` · `P-CA-20260930T034727Z.json:approval_status=UNAPPROVED_CANDIDATE`.
- **실행이 payable(00:00 KST)보다 크게 늦다.** 00:20 cron 이 ABORT 하는 바람에 본 실행이 10:59 로 밀렸고, 17:05 보고 cron 이 아티팩트를 보도록 창 종료를 16:50 KST 로 줄였다 — `P-CA-20260930T015946Z.json:args.window_s=21018.0` → `P-CA-20260930T022735Z.json:args.window_s=19351.0` → `P-CA-20260930T034727Z.json:args.window_s=14554.0`. 3·4차는 11:06 에 자기삭제된 `run-p-ca-20260930.sh` 의 사본에서 돌렸고, 그 사본은 **`~/.config/kis-probes/run-p-ca-20260930-retry.sh`(mode 700)로 보존돼 있다**. 원본과의 차이는 셋뿐이다 — crontab 편집·자기삭제 없음, 보유 수량 파서가 「조회 실패」와 「0주」를 구분함(10:58 오판의 재발 방지), 그리고 `--note` 문구. 가드 넷(`git status --short` · poll-pacer 존재 · 앱키 지문 · 계좌 지문)과 프로브 명령은 같다. ⚠ 이 사본의 START 로그 줄은 4차에도 `(attempt 3)` 을 찍는다 — 위 로그 표의 12:47 행이 그것이다.
- **남은 것**: **P-8 3~5회차** — 주문 권한은 돌아왔으니 재개할 수 있지만, **러너가 전송 오류(1회 재시도)와 `rt_cd≠0`(중단)을 갈라 판정하도록 고친 뒤**에 돌린다(위 09-28 절의 불일치). 이어서 **P-EXT ×5**(운영자 MTS 동석) → **N-15**(마지막). P-CA 는 다음 대상 후보가 에스피지 `058610`(위 표의 2차 후보)이지만 **실행 여부·시점은 운영자 결정이며 아직 정해지지 않았다**. **〔2026-10-01 추가〕 이 절이 적은 관측 실패들(러너의 공유 체크아웃 하드코딩 · 전송 오류 처리)의 수정은 PR #825 로 머지됐다** — 계획 `docs/plans/2026-09-30-probe-transient-error-policy-plan.md`, 추적 러너 템플릿 `tools/broker_probes/runners/run_p_ca.sh`(main `197f5803`). 그 템플릿의 **첫 실사용이 아래 10-01 절**이고 가드는 전부 통과했다. ⚠ **#825 는 P-CA 경로에만 걸린다 — 이 「남은 것」의 선결 조건은 아직 충족되지 않았다.** #825 가 건드린 것은 `probes_ca.py` · `tools/broker_probes/runners/run_p_ca.sh` · 그 테스트뿐이고, **`probes_order.py` 와 P-8 cron 러너는 그대로다**(`_retry_once` 는 `probes_order.py` 에 0건). 위 09-28 절이 적은 불일치 — 러너 `VERDICT` 가 `ConnectionError` 를 「브로커 거부 포함」으로 묶는 것 — 는 살아 있으므로 **P-8 3~5회차는 아직 재개 조건을 만족하지 않는다**.

### 2026-10-01 (목) — P-CA 2차 후속 (지급일 +1 재관측) — **창 완주 · 현금 leg CENSORED**

09-30 과 **같은 사건의 재관측**이다. 대상 `P-CA-20261001T075835Z.json:args.symbol=000660` · `P-CA-20261001T075835Z.json:args.event_class=cash_dividend`, t0 도 그대로 `P-CA-20261001T075835Z.json:args.payable_time=2026-09-30T00:00:00+09:00` 이고 **실행만 지급일 다음 날 오후**다 — `P-CA-20261001T075835Z.json:started_at_utc=2026-10-01T07:58:35.945514+00:00`(16:58:35 KST) → `P-CA-20261001T075835Z.json:finished_at_utc=2026-10-01T08:03:59.385381+00:00`(17:03:59 KST), 소요 `P-CA-20261001T075835Z.json:duration_s=323.44` s. 계좌·자격증명은 09-30 과 동일하다 — 예전 모의 주식 계좌 `P-CA-20261001T075835Z.json:credentials.account_fingerprint=54e7f8a5d841` · `P-CA-20261001T075835Z.json:credentials.account_masked=50******01`, 09-15 백업의 예전 앱키, 전용 토큰 캐시 `P-CA-20261001T075835Z.json:args.token_cache_dir=/home/deploy/.config/kis-probes/p-ca-20260930-token-cache`. GET-only(아티팩트 `read_only_attestation`: 잔고 2 TR + ksdinfo 참조 12 TR 허용목록, 모듈에 주문 경로 없음).

**✅ 09-30 절이 「다음 프로브 전에 고쳐야 할 러너 결함」으로 적은 것이 고쳐진 채로 돌았다.** 공유 체크아웃 하드코딩은 PR #825(계획 `docs/plans/2026-09-30-probe-transient-error-policy-plan.md`)로 닫혔고, 러너가 저장소의 **추적 템플릿** `tools/broker_probes/runners/run_p_ca.sh` 로 들어왔다(main `197f5803`). 이 실행이 그 템플릿의 **첫 실사용**이고, 호스트 래퍼는 환경변수만 넘긴다. 템플릿 가드는 전부 통과했다 — 로그 `~/.config/kis-probes/p-ca-20261001-payplus1.log` 축자:

```text
2026-10-01 16:58:33 checkout ok: repo=/home/deploy/.local/state/kis/wt-pca repo_commit=f23bb4c3a6629a1665dd98151f88fcd35f31fdeb
2026-10-01 16:58:33 probe module resolves inside the checkout: /home/deploy/.local/state/kis/wt-pca/tools/broker_probes/probes_ca.py
2026-10-01 16:58:33 probe policy version p-ca-retry-policy/1 matches this runner
2026-10-01 16:58:33 stock app key fp=7763f26aac49 (expect 7763f26aac49)
2026-10-01 16:58:33 stock account fingerprint=54e7f8a5d841 (expect 54e7f8a5d841)
2026-10-01 16:58:34 held qty(000660)=1
```

`P-CA-20261001T075835Z.json:repo_commit=f23bb4c3` 가 로그의 `repo_commit=` 과 같은 커밋이다(그 시각 `origin/main`). **#793 의 「프로브는 분리 워크트리에서」 규칙이 P-CA 경로에서 처음으로 지켜졌다.**

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 16:58:35 | P-CA 2차 후속(지급일+1) | `P-CA-20261001T075835Z.json` | live / **MEASURED** / MOCK_VTS | `P-CA-20261001T075835Z.json:errors=[]` / 2 | 창 `P-CA-20261001T075835Z.json:args.window_s=300.0` s 를 **끝까지 돌고**(`P-CA-20261001T075835Z.json:measurements.polled_elapsed_s=321.541` s) 현금 leg `P-CA-20261001T075835Z.json:measurements.class_leg_table[0].status=CENSORED`. 폴 `P-CA-20261001T075835Z.json:measurements.polls_completed=10` 회 완료 / `P-CA-20261001T075835Z.json:measurements.polls_used=11` 시도. 전 폴이 baseline 과 같은 값 |

- **✅ ABORT 없이 창이 끝까지 돈 것은 P-CA 세 차례 중 처음이다.** 09-17 은 폴 #1 rate-limit 으로 CENSORED(창 안 돌음), 09-30 은 ABORTED ×3 이었다. 여기서는 `P-CA-20261001T075835Z.json:errors=[]` 이고 재시도 비용도 0 이다 — `P-CA-20261001T075835Z.json:measurements.retries.transport=0` · `P-CA-20261001T075835Z.json:measurements.retries.ledger_throttle=0`. baseline 호출도 정상(`P-CA-20261001T075835Z.json:observations[2].baseline_call.rt_cd=0` · `P-CA-20261001T075835Z.json:observations[2].baseline_call.http_status=200` · `P-CA-20261001T075835Z.json:observations[2].baseline_call.msg_cd=20310000`).
- **⛔ 그래도 현금 leg 는 `CENSORED` 다 — 관측된 반영이 없다.** skip 사유(축자): `P-CA-20261001T075835Z.json:skips[1].reason=CENSORED — no broker-reflect observed within --window-s=300.0s (polls_used=11). Absence of an observed reflection is not evidence of zero latency (VP-002:772 'observed 0 != 0').` leg 출처 등급은 `P-CA-20261001T075835Z.json:measurements.leg_provenance_class=NOT_MEASURED` 다. ⚠ 아티팩트 상단의 `P-CA-20261001T075835Z.json:provenance_class=MEASURED` 는 **실행이 오류 없이 끝났다**는 스탬프이지 leg 가 측정됐다는 뜻이 아니다 — 둘을 같이 읽어야 한다.
- **폴 11회차의 전송 오류는 창이 이미 끝난 뒤라 재시도되지 않았고, 그래서 판정을 바꾸지 않았다.** `P-CA-20261001T075835Z.json:observations[15].retry_evidence.poll_index=11` · `P-CA-20261001T075835Z.json:observations[15].retry_evidence.status_kind=TRANSIENT:transport` · `P-CA-20261001T075835Z.json:observations[15].retry_evidence.retried=false` · `P-CA-20261001T075835Z.json:observations[15].retry_evidence.body_excerpt=ReadTimeout: HTTPSConnectionPool(host='openapivts.koreainvestment.com', port=29443): Read timed out. (read timeout=20.0)`. **이것이 PR #825 가 넣은 F5 규칙이 실제로 동작한 모습이다** — 창 밖 재시도를 거부하므로 CENSORED 가 창 밖 폴에 기대지 않고, 재시도를 안 샀으니 `retries.transport` 도 0 으로 남는다(`tools/broker_probes/probes_ca.py::_retry_once` 의 `can_retry`, `_record_retry` 는 **retried 인 것만** 센다). 09-30 3·4차를 끊은 것과 같은 종류의 `ReadTimeout` 이지만, 이번에는 아무것도 끊지 못했다.
- **모든 읽기값이 동일하다.** baseline `P-CA-20261001T075835Z.json:measurements.baseline.hldg_qty=1` · `P-CA-20261001T075835Z.json:measurements.baseline.dnca_tot_amt=6686725.0`(6,686,725원)로 시작해 첫 폴 `P-CA-20261001T075835Z.json:observations[5].poll.index=1` · `P-CA-20261001T075835Z.json:observations[5].poll.dnca_tot_amt=6686725.0` 부터 마지막 폴 `P-CA-20261001T075835Z.json:observations[14].poll.index=10` · `P-CA-20261001T075835Z.json:observations[14].poll.hldg_qty=1` · `P-CA-20261001T075835Z.json:observations[14].poll.dnca_tot_amt=6686725.0` 까지 10건 전부 같다. 이 예수금 값은 **09-30 지급일 baseline `P-CA-20260930T015946Z.json:measurements.baseline.dnca_tot_amt=6686725.0` 와도, 09-17 1차 baseline `P-CA-20260917T130246Z.json:measurements.baseline.dnca_tot_amt=6686725.0` 와도 같다.**
- **⚠ `--reference-check` — TR 은 여전히 동작하지만 오늘은 반환 행이 0건이다.** `P-CA-20261001T075835Z.json:observations[4].mock_reference_support=SUPPORTED` 로 09-17·09-30 ×2 에 이은 네 번째 확인이지만, `P-CA-20261001T075835Z.json:observations[3].reference_dates=[]` 다. **해석(측정 아님):** ksdinfo 질의 창은 KST 기준 **now−30일 ~ now+180일**(`tools/broker_probes/probes_ca.py::_ksdinfo_window`)이라 10-01 실행의 `F_DT` 는 2026-09-01 이고, 09-30 에 돌아왔던 그 행의 기준일 `P-CA-20260930T015946Z.json:observations[3].reference_dates[0].record_date=20260831` 은 **하루 차이로 창 밖**이다. 즉 행이 사라진 것은 브로커가 CA 를 지운 것이 아니라 질의 창이 지나간 것과 정합적이다 — 확정하려면 `F_DT` 를 넓힌 재질의가 필요하고, 이 실행은 하지 않았다. **`mock_reference_support` 는 행 수와 무관하게 `rt_cd=0` 만 보므로**(같은 파일 `_do_reference_check`) 「SUPPORTED + 0행」은 모순이 아니다.
- **ex leg 는 설계상 SKIP**: `P-CA-20261001T075835Z.json:skips[0].what=legs.cash_dividend.ex` — `P-CA-20261001T075835Z.json:skips[0].reason=NOT_OBSERVABLE_ON_BALANCE_SURFACE — 기준가 조정은 잔고 TR로 관측 불가(N-19 §2.3: 주식잔고조회 72필드 중 가격 필드 없음); 현금 leg만 관측 가능.`
- `B_non_trade_event_detect` / `B_non_trade_reconcile` 두 키 모두 **NOT_ESTABLISHED 유지**. `P-CA-20261001T075835Z.json:approval_status=UNAPPROVED_CANDIDATE`.

#### 캠페인 판정 — 모의 현금배당 반영 (운영자 요청)

**관측(측정):** 사건은 SK하이닉스 000660 분기 현금배당, 지급일 `P-CA-20261001T075835Z.json:args.payable_time=2026-09-30T00:00:00+09:00`(참조행 `P-CA-20260930T015946Z.json:observations[3].reference_dates[0].divi_pay_dt=2026/09/30` · 주당 `P-CA-20260930T015946Z.json:observations[3].reference_dates[0].per_sto_divi_amt=375` 원 · 기준일 `P-CA-20260930T015946Z.json:observations[3].reference_dates[0].record_date=20260831`), 보유 1주. 같은 계좌의 `dnca_tot_amt` 를 두 창에서 읽었다.

| 창 | 시각(KST) | baseline | 완료 폴 | 읽은 값 |
|---|---|---|---|---|
| 지급일 | 10:59:46 ~ 11:31:34 | 2건 | 20건(13+7) | 전부 `6686725.0` |
| 지급일 +1 | 16:58:35 ~ ≈17:03(마지막 성공 읽기) | 1건 | 10건 | 전부 `6686725.0` |

**판정(관측 태그):** 현금 leg 는 **`NOT_REFLECTED_WITHIN_41H`** — 지급일 00:00 KST 로부터 **약 41시간** 뒤까지 **모의(VTS) 주식 계좌의 잔고면에 이 배당이 나타나지 않았다**는 관측 사실이다.

바운드의 끝 앵커는 **마지막으로 성공한 읽기(폴 #10)** 이지 실행 종료 시각이 아니다 — `P-CA-20261001T075835Z.json:finished_at_utc=2026-10-01T08:03:59.385381+00:00`(17:03:59 KST)은 **실패한 20초 `ReadTimeout` 이 돌아온 순간**이고 그때 읽은 값은 없다. 아티팩트에 **폴별 타임스탬프 필드가 없으므로** 폴 #10 의 시각은 도출값이다 — 폴링 경과 `P-CA-20261001T075835Z.json:measurements.polled_elapsed_s=321.541` s 에서 마지막 시도의 20초 타임아웃을 빼면 **t0+≈41.06시간**이다. 소수 둘째 자리의 정밀도는 근거가 없으니 **본문은 「약 41시간」으로 읽는다.**

⚠ **`NOT_REFLECTED_WITHIN_41H` 는 관측 태그이지 `capabilities.corporate_actions.status` 의 값이 아니다.** 그 필드는 닫힌 7값 어휘(`tos/src/tos/brokercap/vocabulary.py::CapabilityStatus` — `VERIFIED` / `VERIFIED_WITH_RESTRICTION` / `DOCUMENTED_NOT_VERIFIED` / `UNSUPPORTED` / `CONTRADICTORY` / `UNKNOWN` / `EXPIRED`, ADR-002-004 §5.3)다. 이 관측이 떠받치는 **어휘 값은 `UNKNOWN` 유지**이고, 많이 가야 `DOCUMENTED_NOT_VERIFIED` 다 — 단일 모의 계좌·단일 사건의 미반영 관측은 `UNSUPPORTED` 를 뒷받침하지 않는다. **이 태그를 INSTANCE 의 status 필드에 그대로 적어서는 안 된다.**

참조 TR(ksdinfo)은 **모의에서 지원된다**(`P-CA-20261001T075835Z.json:observations[4].mock_reference_support=SUPPORTED`) — 09-17 판정에서 바뀐 것이 없다.

**이 판정이 말하지 않는 것(경계):**

- **「영영 반영되지 않는다」가 아니다.** 측정한 것은 **약 41시간**(끝 앵커 = 마지막 성공 읽기) 바운드뿐이다. 그 뒤는 관측하지 않았다.
- 두 창 사이 **약 29.5시간은 폴링하지 않았다.** 그래도 바운드가 그 공백에 걸리는 이유는 예수금이 **수준(level)** 이기 때문이다 — 공백 중에 세전 375원(원천징수 여부와 무관하게 0원이 아니다)이 들어왔다면 10-01 의 값은 달랐을 것이다. **전제는 운영자 attest(창 동안 이 계좌에 다른 주문·입출금 없음)와 09-15 재신청 이후 이 계좌가 정적이라는 것**이고, 정확히 상쇄하는 다른 변동은 배제하지 못한다. **해석(측정 아님)** 으로 분류한다.
- **잔고 TR 72필드 중 이 프로브가 보는 것은 2개뿐이다** — `hldg_qty` 와 `output2[0].dnca_tot_amt`(`tools/broker_probes/probes_ca.py` 모듈 독스트링 · `_read_cash_total`). 모의 서버가 배당을 **다른 필드**(가수도정산·D+2 계열)로 적었다면 이 관측은 그것을 보지 못한다. 「잔고면 미반영」이 「원장 미반영」보다 좁은 주장인 이유다.
- **위 09-30 절의 유보와 모순이 아니다.** 그 절은 「변화가 없었다는 것이 「배당이 반영되지 않았다」는 뜻은 아니다」라고 적었고 그것은 **단일 창 안의 무변화**에 대한 규칙으로 여전히 옳다 — 한 창에서 값이 안 변한 것은 반영이 창 밖에 있었을 뿐일 수 있다. 여기서 다른 것은 **두 창에 걸친 level 비교**다 — 지급일 창과 지급일+1 창의 값이 같다는 것은 그 사이에 들어온 현금이 없다는 뜻이고, 이는 한 창 안의 무변화보다 강한 진술이다. 09-30 블록만 읽는 독자를 위해 적어 둔다: **09-30 의 유보는 철회된 것이 아니라 적용 범위가 다르다.**
- 아티팩트의 `attribution_caveat` 는 **변화가 관측된 경우** 그것을 CA 에 귀속할 수 없다고 적는다. 여기서는 그 반대(변화 0)지만 같은 이유로, 이 관측 하나가 브로커 쪽 CA 처리 유무를 직접 말하지는 않는다.
- 두 바운드 키 `B_non_trade_event_detect` / `B_non_trade_reconcile` 는 **여전히 NOT_ESTABLISHED** 이고, INSTANCE 기입에는 P0-2 승인 체인이 필요하다(`P-CA-20261001T075835Z.json:approval_note`). 위 관측 태그는 **승인 전 후보**이고, `capabilities.corporate_actions.status` 에 들어갈 **어휘 값은 `UNKNOWN` 유지**다.

#### 058610 당일 사전 확인 시도 — 프로브가 거부 (아티팩트 없음)

같은 자격증명으로 17:04:49 에 다음 대상 에스피지 058610 의 참조조회를 미리 돌려 보려 했으나, 템플릿 가드(체크아웃·모듈 경로·정책 버전·앱키 지문·계좌 지문·`held qty(058610)=1`)를 전부 통과한 뒤 **프로브가 전제조건에서 거부했다**(rc 4, 로그 `~/.config/kis-probes/p-ca-20261001-058610-refcheck.log` 축자): `PRECONDITION NOT MET: --payable-time is in the future ('2026-10-22T00:00:00+09:00' > 2026-10-01T08:04:53.228420+00:00) — P-CA pairs a poll against a time that has ALREADY passed; a future t0 would record a negative latency.` 아티팩트는 쓰이지 않았고 러너도 `WARN: newest artifact (P-CA-20261001T075835Z.json) predates this run — NOT copied` 로 **직전 실행의 아티팩트를 복사하지 않았다**(오염 방지 가드가 동작한 것이다). 따라서 **10-22 지급일은 09-17 참조표 값 그대로 둔다** — 그 값은 DART 접수(`20260907900152`/`20260907900150`, 위 §서버 측에서 채운 값)에서 온 것이지 ksdinfo 참조표에서 온 것이 아니다.

⚠ **당일 `--reference-check` 는 「재확인」이 아니라 「기록」이다.** `tools/broker_probes/probes_ca.py::_do_reference_check` 는 ksdinfo 행을 `reference_dates` 에 적을 뿐 **`--payable-time` 으로 되먹이지 않고**, 래퍼도 `divi_pay_dt` 를 t0 와 비교하지 않는다. 그래서 브로커의 지급일이 10-23 이었다면 프로브는 그대로 10-22 를 t0 로 삼아 창을 다 쓰고 CENSORED 를 쓴 뒤에야 아티팩트 안에서 불일치가 드러난다 — **창을 쓰기 전에 막아 주지 않는다.** 이 결합을 푸는 후속(참조 전용 모드 + 지급일 대조)은 **#830 으로 머지됐다** — 계획 `docs/plans/2026-09-30-probe-transient-error-policy-plan.md` §7.14. 이 문단이 적는 두 결함은 **10-01 시점의 상태**이고, 지금 추적 템플릿은 `PCA_REFERENCE_CHECK=1` 인 현금배당에서 폴링 전에 `divi_pay_dt` 를 `PCA_PAYABLE` 과 대조해 불일치면 ABORT 한다.

- **남은 것**:
  - **P-CA 3차(에스피지 `058610`) — 무인 예약 완료, 슬롯 3개.** 운영자 지시(2026-10-01)로 10-22 를 기다리거나 레인을 열어 두지 않는다. 호스트 crontab(`CRON_TZ=Asia/Seoul`)에 **00:20 · 06:20 · 12:20 KST 세 줄**이 있고 셋 다 같은 래퍼를 같은 lock 으로 부른다 — `20 0 22 10 *` / `20 6 22 10 *` / `20 12 22 10 *` → `/usr/bin/flock -n /tmp/p-ca-20261022.lock` + `~/.config/kis-probes/run-p-ca-20261022.sh`, 로그 `~/.config/kis-probes/p-ca-20261022.log`(cron stdout 은 `p-ca-20261022-cron.log`). 래퍼는 호스트 로컬이고, `origin/main` 분리 워크트리 `/home/deploy/.local/state/kis/wt-pca-20261022` 를 새로 만들어 **추적 템플릿**을 호출한다.
    - **창 종료는 슬롯과 무관하게 16:20 KST 고정**이고 `PCA_WINDOW_S` 는 슬롯 시작 시각에서 그때까지로 계산된다(00:20 슬롯이면 57,600 s). 남은 시간이 **30분 미만이면 그 슬롯은 돌지 않고 전부 해제**한다.
    - **한 번의 ABORT 는 종결이 아니다.** 각 슬롯은 시작 전에 **이미 끝난 관측**(058610 · `legs.cash_dividend.cash` 가 `ABORTED` 가 아니고 `errors` 가 빈 아티팩트)이 있는지 보고, 있으면 아무 것도 하지 않고 세 줄을 전부 지운다. 없으면 돌고, 끝난 뒤 같은 검사를 다시 해 **완료면 해제, 미완이면 다음 슬롯에 넘긴다**. 따라서 **세 슬롯이 연달아 ABORT 해야 종결**이다. `PCA_CRON_MARK` 는 **일부러 비워 둔다** — 설정하면 템플릿이 rc 와 무관하게 크론 줄을 지워 재무장이 사라진다.
    - 완료 판정의 아티팩트 글롭은 `P-CA-2026102[12]T*.json` 이다. **아티팩트 id 는 UTC 스탬프**(`tools/broker_probes/common.py::artifact_id` 가 `started_at` 을 그대로 쓴다 — 10-01 의 16:58 KST 실행이 `P-CA-20261001T075835Z` 로 떨어진 것이 그 예다)라 00:20·06:20 KST 슬롯은 `P-CA-20261021T…Z` 로 떨어진다 — 10-21·10-22 **두 UTC 날짜를 다 보는** 이유다.
      ⚠ **이 글롭은 처음에 `P-CA-20261022T*.json` 하나였고, #829 리뷰 레인의 F1 지적을 호스트에 적용하려고 래퍼를 다시 읽다가 잡았다.** 그대로 뒀다면 00:20·06:20 슬롯의 **완료 관측이 탐지되지 않아** — 세 슬롯 중 12:20 만 UTC 10-22 에 떨어진다 — Telegram 이 완료를 「ABORT/미완」으로 보고하고, 크론 줄은 해제되지 않고, 다음 슬롯이 **이미 관측된 사건에 창을 또 썼을 것**이다. 재무장 가드가 자기가 막는다고 적은 것(중복 실행)을 그대로 통과시키는 모양이었다. 자동 검사로는 안 잡힌다 — 10-22 에 한 번 돌 코드이고 실패 모드가 침묵이다.
    - 파라미터: `058610` · `cash_dividend` · payable `2026-10-22T00:00:00+09:00` · poll `30000` ms · pace `1.5` s · 09-15 백업 자격증명 파일 · 토큰 캐시 `p-ca-20260930-token-cache` · `PCA_REFERENCE_CHECK=1`. 끝나면 Telegram briefing 채널로 rc·아티팩트명·판정 줄·다음 슬롯 여부를 보낸다.
    - **아티팩트 복사 목적지는 내구 호스트 경로 `/home/deploy/.local/state/kis/p-ca-evidence/` 다**(`PCA_EVIDENCE_DIR`). 이 PR 브랜치의 워크트리를 가리키지 않는다 — 템플릿은 그 디렉터리가 없으면 **프로브를 돌리기 전에 die** 하므로(`run_p_ca.sh::"evidence dir missing"`), 워크트리 정리가 관측을 통째로 날릴 수 있었다. ⚠ **캠페인 README 편입·커밋·PR 은 그 경로에서 수동으로 한다.**
    - ⚠ **지급일 대조가 10-22 슬롯에서 실제로 돌게 된다**(#830 머지 이후). 래퍼가 `PCA_REFERENCE_CHECK=1` 을 넣고 이벤트 클래스가 `cash_dividend` 이므로, 추적 템플릿은 **슬롯의 첫 브로커 호출로** ksdinfo GET 을 한 번 하고 `divi_pay_dt` 를 `PCA_PAYABLE`(KST 변환 후)과 대조한다 — 참조 TR 은 계좌 무관이라 보유가 필요 없고, 지급일이 틀린 슬롯이 잔고 조회까지 쓰지 않게 보유 점검보다 **앞**이다. 본 시행은 그 아티팩트의 행을 `--reference-rows-from` 으로 **그대로 물려받아** 두 번 묻지 않는다. 브로커가 돌려준 **어느 행이든** 지급일이 맞으면 확인, 행이 있는데 전부 다르면 **ABORT**(우회 `PCA_ALLOW_PAYDATE_MISMATCH=1`), 행이 없으면 경고 후 진행(`PCA_REQUIRE_REFERENCE_ROW=1` 로 차단 가능). `PCA_RECORD_DATE` 는 후보를 한 기준일로 좁히고 `F_DT` 도 거기에 맞춘다(선택). 참조조회가 전송 오류·레이트리밋으로 멈추면 창을 **시작하지 않는다**. 참조 전용 아티팩트는 `$PCA_EVIDENCE_DIR/reference-only/` 로 떨어져 재무장 가드의 글롭에 걸리지 않는다. **058610 의 지급일은 DART 출처이고 ksdinfo 참조표에서 확인된 적이 없으므로, 운영자는 슬롯 전에 이 셋 중 무엇을 둘지 정해야 한다.**
  - 09-30 절에서 이월: **P-8 3~5회차** → **P-EXT ×5**(운영자 MTS 동석) → **N-15**(마지막). ⚠ **P-8 의 선결 조건(러너가 전송 오류와 `rt_cd≠0` 를 갈라 판정하는 것)은 아직 충족되지 않았다** — #825 는 P-CA 경로만 고쳤고 `probes_order.py` 와 P-8 러너는 그대로다(위 09-30 절 주석).
  - 비차단 후속 **#830** — `--reference-only` 모드(미래 지급일의 ksdinfo 참조조회를 t0 없이 허용)와 러너의 `divi_pay_dt`↔t0 대조. 오늘 두 가지가 같은 결합에서 나왔다: 058610 사전 확인이 rc 4 로 거부된 것(미래 t0)과, 10-22 창이 **대조 없이** 돌게 되는 것. ksdinfo 질의 창을 t0 기준으로도 잡는 것(실행 시각 −30일 고정이 10-01 의 0행을 만들었다)도 같은 이슈에 묶었다. **셋 다 머지됨** — 계획 §7.14, 러너 사용법은 `tools/broker_probes/runners/README.md` 「The pay-date pre-check」. 10-22 슬롯에 미치는 영향은 위 「P-CA 3차」 항목 참조.

## 수동 개입 기록

- 2026-09-10: 없음(실전 GET 2건은 무인 실행, HTS/MTS 미사용).
- 2026-09-28: 없음(P-8 ×2 는 호스트 cron 무인 실행, HTS/MTS 미사용).
- 2026-09-30: 브로커에 닿은 것은 **러너 실행 5회 + 확인용 GET 1회**다. 전부 GET, 주문 0건, HTS/MTS 미사용.
  - 00:20:01 호스트 cron — `git status --short` 더티 가드에서 중단. 이 가드는 자격증명 소싱·토큰 발급·조회보다 **앞**에 있어(러너 스크립트 순서) **네트워크 호출 0**. 원인이던 untracked `.claude/settings.local.json.bak.*` 는 증거 파일이 아니라 설정 백업이어서 `~/.claude/backups/` 로 옮겼다.
  - 10:58:04 수동 — 가드를 통과해 러너의 보유 사전 확인 `get_stock_balance()` 가 나갔다. **잔고 GET 1회**, 그 결과로 ABORT(위 로그 표).
  - 10:59:46 · 11:27:35 · 12:47:27 수동 — 각각 attempt 2 · 3 · 4. 3·4차는 보존된 사본 러너(`~/.config/kis-probes/run-p-ca-20260930-retry.sh`).
  - 11:00 경 수동 — 10:58 ABORT 의 원인을 가르기 위한 확인용 직접 GET 1회(20행, `000660` 수량 1, 11.9 초). **attempt 2 의 폴링 창 안에 들어갔다**(위 EGW00215 해석 참조).
- 2026-10-01: 브로커에 닿은 것은 **템플릿 러너 실행 2회**다. 전부 GET, 주문 0건, HTS/MTS 미사용.
  - 16:58:33~17:03:59 수동 — 000660 지급일+1 재관측. 러너 사전 확인 GET 1회(`held qty(000660)=1`) + 프로브 baseline 1회 + ksdinfo 참조조회 1회 + 폴 11회(그중 11회차는 `ReadTimeout`). 아티팩트 `P-CA-20261001T075835Z.json`.
  - 17:04:49~17:04:53 수동 — 058610 사전 확인 시도. 러너 사전 확인 GET 1회(`held qty(058610)=1`) 뒤 프로브가 `PRECONDITION NOT MET: --payable-time is in the future` 로 거부(rc 4) → **아티팩트 없음**, 복사도 없음.
- 2026-10-22 (예정): **수동 개입 없음** — P-CA 3차(058610)는 호스트 cron **무인 실행이고 슬롯이 3개**다(00:20 · 06:20 · 12:20 KST, 위 10-01 절 「남은 것」). 앞 슬롯이 완료 관측을 남기면 뒤 슬롯은 돌지 않고 세 줄이 해제되며, 세 슬롯이 연달아 ABORT 해야 종결이다. 운영자 동석·HTS/MTS 사용 계획 없음. 아티팩트는 `/home/deploy/.local/state/kis/p-ca-evidence/` 로 떨어지고, **README 편입만 수동**이다.

## 반환 항목 (핸드오버 §4)

- `git rev-parse HEAD`: 야간 실전 GET = `296c0e5f`; 모의 블록은 실행 로그의 `repo_commit=` 줄.
- 계좌 지문: 실전 선물 `8304d859b87f` · 모의 선물/주식은 모의 블록 아티팩트에서.
- `python -m tools.broker_probes.run --coverage` 출력: 모의 블록 종료 후 첨부.
