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
| 09:24:27 | P-BAL(모의 주식) | `P-BAL-20260911T002427Z.json` | live / MEASURED / MOCK_VTS | [] / [] | `VTTC8434R` 2페이지 walk, **양수 수량 25행 > page_size 20** → `TRUNCATION_RISK_DEMONSTRATED`(런타임은 1페이지만 읽음, `client.py:931-932`). 종료 원인 `BROKER_END_OF_SET`(page 1 `tr_cont='D'`), `tr_cont` 헤더 관측, 연속조회 지원. 2026-08-05 측정과 일치. 계좌 `50******01`(`54e7f8a5d841`). |

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

**⚠ 예약 시각과 실제 실행 시각이 다르다.** 세션 예약은 08:31 KST 에 발화해 사전 확인(계좌 지문 일치·잔고 20행 정상, `P-BAL-20260916T233126Z.json` — 종목 식별은 이 아티팩트 범위 밖, 아래 표 주석 참조)까지 08:31 에 마쳤으나, 세션이 중단돼 **프로브 본체는 22:02:46 KST 에 실행**됐다. 프로브가 스스로 다시 읽은 baseline 도 `hldg_qty=1`(예수금 6,686,725원)로 같다. payable(00:00)은 두 시각 모두 이미 지난 뒤였지만, 창 8시간은 22:02→익일 06:02 로 밀렸다.

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 08:31:26 | P-BAL(사전 확인) | `P-BAL-20260916T233126Z.json` | live / MEASURED / MOCK_VTS | [] / [] | 예전 계좌 **20행 정상** — 초기화로 리셋되지 않음. ⚠ 이 아티팩트는 페이지별 행 수·`rt_cd`·연속조회 키만 담고 `pdno`/종목명/단가 필드가 **없다**(`raw_excerpt` 도 빈 문자열) — **어느 종목을 보유하는지는 이 아티팩트로 확인 불가**다. SK텔레콤 1주 보유는 아래 P-CA 본체의 `measurements.baseline.hldg_qty=1`(프로브가 `--symbol 017670` 로 스코프된 상태에서 스스로 읽은 값)이 뒷받침한다 |
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

## 수동 개입 기록

- 2026-09-10: 없음(실전 GET 2건은 무인 실행, HTS/MTS 미사용).

## 반환 항목 (핸드오버 §4)

- `git rev-parse HEAD`: 야간 실전 GET = `296c0e5f`; 모의 블록은 실행 로그의 `repo_commit=` 줄.
- 계좌 지문: 실전 선물 `8304d859b87f` · 모의 선물/주식은 모의 블록 아티팩트에서.
- `python -m tools.broker_probes.run --coverage` 출력: 모의 블록 종료 후 첨부.
