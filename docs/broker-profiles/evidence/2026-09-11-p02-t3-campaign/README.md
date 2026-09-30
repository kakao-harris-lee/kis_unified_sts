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

별도 서브셸에서 `.env.real` 소싱(값 미출력) → 실행 → 서브셸 종료. 실전 선물 계좌 지문 `8304d859b87f`(마스킹 `43******03`, 운영자 확정 `03` 계좌, 예수금·증거금 의도적 0 — never-fund). `repo_commit` `296c0e5f`. stdout 사본 `n16-n18-20260910-stdout.log`.

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 20:15:07 | N-16 | `N-16-20260910T111508Z.json` | live / MEASURED / REAL_PROD | [] / [] | `CTFN6118R` HTTP 200 · `rt_cd=0` · `KIOK0530`. `output1` 0행(야간 포지션 없음 = 설계 상태), `output2` 31키 스키마 포착. 행 스키마는 여전히 미확립 — 빈 응답 ≠ 빈 스키마(아티팩트 `empty_response_caveat`). 정책 종결(45735d2a) 전제 불변. |
| 20:15:08 | N-18 | `N-18-20260910T111508Z.json` | live / MEASURED / REAL_PROD | [] / [] | N-18a `FHPPG04600001` 150일 요청 → 단일 호출 102행(cap 여부는 범위 내 거래일 수 대조 후 판정, 아티팩트 `n18a_cap_determination`). N-18b `FHKST03030200`: 통제 leg `SPX` 102행 · `SOX` 102행(**표기 확정**) · `.SOX` / `^SOX` 0행(rt_cd 0 이나 빈 결과). N-18c `FHMIF10000000`: 주간 `A01612` `futs_prpr=1112.00` / `futs_prdy_clpr=1119.00` · 야간 `1A01612` `rt_cd=0` 이나 `futs_prpr`/`futs_prdy_clpr` **null** → REST 는 야간 세션 시세를 서비스하지 않음(WS-only 야간 캡처 설계 확인, `n18c_interpretation`). |

`approval_status` 는 전부 `UNAPPROVED_CANDIDATE`(§6.1). 인용 적격성(§6.2)은 개발 측 확인.

### 2026-09-11 (금) — 모의(MOCK_VTS) 블록

러너 `~/.config/kis-probes/run-p02-t3-20260911.sh`(`.env.mock` 만 소싱, 09:18 KST 시작 — 세션 스케줄 09:04 는 미발화, 운영자 수동 트리거): 계획은 **P-8 ×5** → **P-15** → **N-15** → **P-BAL**. `repo_commit` `7f3ffa52`, 작업트리 clean, `futures_live.enabled: false`, 앱키 공유 워커 0(러너 내장 지문 대조 `shared_workers=none`). 로그 사본 `p02-t3-20260911-runner.log`, 커버리지 `coverage-20260911.json`.

**⛔ P-8 은 브로커가 거부** — 2회 모두 `rt_cd=1 모의투자 주문이 불가한 계좌입니다`(계좌 `60******03`, 지문 `5e175fd232de` = 2026-07-31 wave-3 에서 주문이 접수됐던 것과 **동일 계좌**; 앱키·토큰·조회는 정상). 모의 선물옵션 계좌의 **주문 권한이 만료/해지된 것**으로 판단 → 운영자가 KIS 모의투자(선물옵션) 재신청 후 P-8 ×5·P-EXT ×5 를 재실행해야 한다. 3~5회차는 건너뛰고(재시도 금지 규칙 준용) 주문과 무관한 P-15 → N-15 → P-BAL 만 이어서 실행했다.

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 09:18:17 | P-8 1/5 | `P-8-20260911T001817Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / [] | `submit rejected rt_cd=1 msg=모의투자 주문이 불가한 계좌입니다.` — 관측 0건 |
| 09:19:37 | P-8 2/5 | `P-8-20260911T001938Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / [] | 동일 거부. 3~5회차 미실행 |
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
| 22:10:09 | P-BAL(**예전** 모의 주식) | `P-BAL-20260915T131009Z.json` | live / MEASURED / MOCK_VTS | [] / [] | 판별 실험: 같은 앱키로 **예전 계좌 `54e7f8a5d841` 는 정상 25행**(SK텔레콤 017670 보유 포함) → **앱키가 아직 예전 계좌에 묶여 있다** |

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

**⚠ 예약 시각과 실제 실행 시각이 다르다.** 세션 예약은 08:31 KST 에 발화해 사전 확인(지문·SK텔레콤 1주 보유·잔고 20행 정상, `P-BAL-20260916T233126Z.json`)까지 08:31 에 마쳤으나, 세션이 중단돼 **프로브 본체는 22:02:46 KST 에 실행**됐다. 프로브가 스스로 다시 읽은 baseline 도 `hldg_qty=1`(예수금 6,686,725원)로 같다. payable(00:00)은 두 시각 모두 이미 지난 뒤였지만, 창 8시간은 22:02→익일 06:02 로 밀렸다.

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 08:31:26 | P-BAL(사전 확인) | `P-BAL-20260916T233126Z.json` | live / MEASURED / MOCK_VTS | [] / [] | 예전 계좌 20행 정상, **SK텔레콤 017670 1주 보유**(평단 90,900) — 초기화로 리셋되지 않음 |
| 22:02:46 | P-CA 1차 | `P-CA-20260917T130246Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / 2 | 아래 |

- **✅ `--reference-check` 는 성공 — 모의에서 CA 참조 TR 이 동작한다.** `mock_reference_support: SUPPORTED`. 반환 행: SK텔레콤 017670 · `divi_kind=분기` · `per_sto_divi_amt=830` · `record_date=20260831` · `divi_pay_dt=2026/09/17`. N-19 §3 의 "모의 CA 처리 여부 UNKNOWN" 중 **참조원 존부는 이 관측으로 해소**된다(값 인용은 §6.2 대로 MOCK 한정).
- **⛔ 현금 leg 는 CENSORED** — 폴링 #1 에서 브로커 rate-limit(`is_rate_limited`: HTTP 429 또는 `EGW00201`) → 중단 규칙대로 재시도 없이 종료, `polls_used=1`. **미관측이지 "반영 없음"이 아니다**(VP-002:772 'observed 0 != 0'). 직전 1.5초 안에 baseline 잔고 walk + 참조 조회가 나갔고 모의 조회 한도가 [1,2) rps 인 것과 정합적이나, 아티팩트가 축자 응답 본문을 남기지 않아 **429 인지 EGW00201 인지는 미확정**(하네스 갭).
- **ex leg 는 설계상 SKIP** — 기준가 조정은 잔고 TR 로 관측 불가(N-19 §2.3).
- `B_non_trade_event_detect` / `B_non_trade_reconcile` 두 키 모두 **NOT_ESTABLISHED 유지**.

이후 남은 것: **P-CA 재시도**(2차 대상 에스피지 058610 10-22, 또는 SK텔레콤 재실행 시 폴링 전 rate-limit 여유 확보), **P-EXT ×5**·**P-8 ×5**(모의 선물 주문 권한 복구 후, 운영자 MTS 동석).

### 2026-09-28 (월) — P-8 재실행 (호스트 cron · 분리 워크트리)

09-23 에 운영자가 앱키↔새 선물 계좌 연결을 보고한 뒤 첫 재실행. 호스트 cron 이 **분리 워크트리**(detached `origin/main`, 로그 표현 "clean by construction")에서 돌렸다 — `repo_commit=ac2efb0f2b1698b87cac4d927886583c77e5357a`(아티팩트 `repo_commit` `ac2efb0f`). 러너 가드: `futures:live:suspended=''`, 모의 선물 앱키 지문 `39a004459922` · `shared_workers=none`, 선물 계좌 지문 `46c39c54d3bb`(09-15 재신청으로 받은 **새** 계좌, 마스킹 `60******03`), mini 근월물 `A05610`. 로그 `~/.config/kis-probes/p8-20260928.log`.

**✅ 모의 선물 주문이 처음으로 접수됐다.** 09-11 의 `모의투자 주문이 불가한 계좌입니다`·09-16 의 `인증 시점의 계좌번호와 요청 계좌번호가 일치하지 않습니다` 거부가 사라지고, 제출·정정·취소가 모두 `rt_cd=0` 으로 돌아갔다.

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 09:05:06 | P-8 1/5 | `P-8-20260928T000506Z.json` | live / **MEASURED** / MOCK_VTS | [] / [] | 지정가 `1002.22`(unrounded `1002.2399999999999`, `tick_size 0.02`, `rounding floor`) → 정정 `992.18`(unrounded `992.1978`). `amend_rt_cd=0` `모의투자 정정주문이 완료 되었습니다.` 원 ODNO `0000000512` → 신 ODNO `0000000513`. `replace_issues_new_odno: true` · `replace_rejected: false` · `coexistence_ms: 0.0` (`poll_granularity_ms: 1100.0`). 소요 36.791s |
| 09:06:58 | P-8 2/5 | `P-8-20260928T000658Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / [] | 지정가 `1005.26`(unrounded `1005.264`) → 정정 `995.2`(unrounded `995.2074`), `amend_rt_cd=0`, ODNO `0000000558` → `0000000560`. 정정·취소까지는 갔으나 `ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))` 로 중단 → `coexistence_ms` 등 공존 측정 필드 미기록. 소요 33.363s |

- **ODNO 표기 비대칭 재확인(양쪽 정규화 필요).** 제출 응답은 zero-pad, 조회 행은 space-pad 다. 1회차 제출 `"0000000512"`·`"0000000513"` vs 조회 행 `"       513"`·`"       512"`; 2회차 제출 `"0000000558"`·`"0000000560"` vs 조회 행 `"       560"`·`"       558"`·`"       528"`. 아티팩트 `odno_wire_format.scope` 대로 **모의 계좌 1개·세션 1회의 관측이며 실전으로 외삽하지 않는다**.
- **정정 뒤 원 주문은 취소 대상이 남지 않는다.** 1회차 `cleanup_cancel 0000000512` → `ok: false` `msg: 모의투자 정정/취소할 수량이 없습니다.` `disposition: NOTHING_TO_CANCEL_NO_LIVE_ROW`, liveness 증거 `pages_walked 1 / rows_seen 2 / outcome COMPLETE_WALK`; 신 ODNO `0000000513` 은 `CANCELLED`. 2회차도 동일한 형태(`0000000558` NOTHING_TO_CANCEL_NO_LIVE_ROW, `rows_seen 5`; `0000000560` CANCELLED). `original_not_cancellable_after_amend: true` 이지만 아티팩트 `amend_consumption_note` 가 못박은 대로 **체결도 똑같은 관측을 낳으므로 이 필드는 구조적 사실만 말하고 원인을 지목하지 않는다**(P-8 은 체결 조회를 하지 않음).
- **⛔ 판정에는 못 쓴다.** 아티팩트 `mode_determination`: "Map to ReplaceSemantics only after N>=5 trials agree. A single trial showing zero coexistence does NOT prove atomicity — polling can miss an interval shorter than poll_granularity_ms". MEASURED 는 1회뿐이고 2회차는 연결 오류로 끊겼다. 러너 판정 `VERDICT: STOP: P-8 2/5 오류 1건(브로커 거부 포함) — 1/5 성공 후 중단(재시도 금지)` → **3~5회차 미실행**. 따라서 `capabilities.replace_semantics.mode` 기입 불가, `B_protective_request_complete` **NOT_ESTABLISHED 유지**.
- `approval_status` 두 건 모두 `UNAPPROVED_CANDIDATE`.

### 2026-09-30 (수) — P-CA 2차 (SK하이닉스 현금배당) — **3회 모두 ABORT**

대상은 SK하이닉스 `000660` `cash_dividend`, `payable_time 2026-09-30T00:00:00+09:00`(375원/주, record `20260831`) — 위 표의 2차 후보(에스피지 058610)보다 지급일이 일러 먼저 실행했다. 계좌는 09-17 과 같은 **예전** 모의 주식 계좌 지문 `54e7f8a5d841`(마스킹 `50******01`)이고, 09-23 키 로테이션 뒤라 아티팩트 `--note` 대로 **09-15 백업의 자격증명 한 벌**(예전 앱키 지문 `7763f26aac49`)을 그대로 썼다. GET-only(`read_only_attestation`: 잔고 2 TR + ksdinfo 참조 12 TR 허용목록, 모듈에 주문 경로 없음). `repo_commit aec37535`, 토큰 캐시 `/home/deploy/.config/kis-probes/p-ca-20260930-token-cache`. 로그 `~/.config/kis-probes/p-ca-20260930.log`.

러너 로그의 ABORT/START/END 줄(시각 KST):

| 시각(KST) | 로그 줄 | 결과 |
|---|---|---|
| 00:20:01 | `ABORT: worktree dirty` | 아티팩트 없음(호스트 cron 1차). 원인은 main 체크아웃의 untracked `.claude/settings.local.json.bak.*` — 증거 파일이 아니라 설정 백업이어서 `~/.claude/backups/` 로 옮겼다 |
| 10:58:37 | `held qty(000660)=0` → `ABORT: 000660 not held (or balance query rejected) — nothing to observe` | 아티팩트 없음. **보유 판정이 아니라 거부된 잔고 조회**(10:58:05 시작 → 10:58:37, 32초). 11:00 경 직접 GET 은 20행·`000660` 수량 1 을 반환했다 |
| 10:59:46 | `=== START P-CA 000660 window=21018s poll=30000ms pace=1.5s` | → `P-CA-20260930T015946Z.json` |
| 11:06:27 | `=== END P-CA rc=0` | |
| 11:27:35 | `=== START P-CA 000660 window=19351s poll=30000ms pace=1.5s (attempt 3)` | → `P-CA-20260930T022735Z.json` |
| 11:31:34 | `=== END P-CA rc=5` | |
| 12:47:27 | `=== START P-CA 000660 window=14554s poll=30000ms pace=1.5s (attempt 3)` | → `P-CA-20260930T034727Z.json`. 로그의 "attempt 3" 은 스크래치 러너의 START 줄을 안 고친 것이고, 아티팩트 `--note` 는 **attempt 4** 다 |
| 12:47:48 | `=== END P-CA rc=5` | |

| 시각(KST) | 시도 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| 10:59:46 | 2 | `P-CA-20260930T015946Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / 2 | 폴 13회 완료, #14 에서 `rt_cd='1' msg_cd='EGW00215'` HTTP 500 거부. 소요 401.343s |
| 11:27:35 | 3 | `P-CA-20260930T022735Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / 1 | baseline·참조 조회 뒤 폴 7건 기록, 그다음 `ReadTimeout`. 소요 238.674s |
| 12:47:27 | 4 | `P-CA-20260930T034727Z.json` | live / **NOT_MEASURED** / MOCK_VTS | 1 / [] | `measurements` 비어 있고 `baseline_call`·`reference_dates` 관측 없음 → 첫 조회 단계에서 `ReadTimeout`, 폴 0회. 소요 20.446s |

- **✅ `--reference-check` 는 2·3차 시도 모두 성공 — `mock_reference_support: SUPPORTED`.** 09-17 SK텔레콤에 이은 두 번째 확인이다. 반환 행(축자): `record_date=20260831` · `sht_cd=000660` · `isin_name=에스케이하이닉스` · `divi_kind=분기` · `face_val=5000` · `per_sto_divi_amt=375` · `divi_rate=7.50` · `stk_divi_rate=0.00` · `divi_pay_dt=2026/09/30` · `stk_div_pay_dt=`(빈 값) · `odd_pay_dt=`(빈 값) · `stk_kind=보통` · `high_divi_gb=`(빈 값). 값 인용은 §6.2 대로 MOCK 한정.
- **⛔ 2차 시도 — `legs.cash_dividend.cash` = `ABORTED`.** `class_leg_table` 행: `status ABORTED` · `window_s 21018.0` · `polled_elapsed_s 394.072` · `stop_reason rejected` · `polls_used 14` · `polls_completed 13`. skip 사유(축자): "ABORTED — polling stopped early (stop_reason=rejected, polls_used=14 (attempts), polls_completed=13); polling ran 394.072s, so --window-s=21018.0s did NOT elapse. This is not even a censored observation: the window never ran, so nothing at all was observed about this leg." `poll_stop_evidence`: `http_status 500` · `rt_cd '1'` · `msg_cd 'EGW00215'` · `msg1 원장에서 허용 가능한 초당 거래건수를 초과하였습니다.` · `body_excerpt {"rt_cd":"1","msg1":"원장에서 허용 가능한 초당 거래건수를 초과하였습니다.","msg_cd":"EGW00215"}`.
  - **1차(09-17)의 하네스 갭은 이 경로에서 닫혔다** — 축자 응답 본문이 아티팩트에 남았다. 그리고 코드는 1차 때 추정했던 `EGW00201`(앱키 유량)도 HTTP 429 도 아닌 **`EGW00215`(원장 초당 거래건수)** 였다.
  - 호출 간격은 30 s 였고(`poll_interval_ms_effective: 30000.0`, `pace_s 1.5`), 이 계좌 `54e7f8a5d841` 을 쓰는 프로세스는 이 호스트에 없다(paper 스택 계좌 지문 `a43943c80cc3`, 현재 `.env.mock` `ee1bdb5f1ca2`). 따라서 `EGW00215` 는 우리 호출률이 아니라 **모의 서버 원장의 공유 스로틀**로 읽는다 — **해석이지 측정이 아니다**.
- **3·4차 — `ReadTimeout: HTTPSConnectionPool(host='openapivts.koreainvestment.com', port=29443): Read timed out. (read timeout=20.0)`.** 3차는 폴 7건까지 기록됐고(4차 아티팩트 `--note`: "attempt 3 (11:27) ABORTED poll #8 ReadTimeout 20s on openapivts"), 4차는 baseline 도 못 남겼다.
- **ex leg 는 설계상 SKIP**(2·3차): `NOT_OBSERVABLE_ON_BALANCE_SURFACE — 기준가 조정은 잔고 TR로 관측 불가(N-19 §2.3: 주식잔고조회 72필드 중 가격 필드 없음); 현금 leg만 관측 가능.` 4차는 그 단계 전에 끊겨 `skips` 가 비어 있다.
- **⛔ 판정: P-CA 2차 = ABORTED ×3 (전부 브로커 측 일시 오류) — 현금 leg 미관측.** **CENSORED 가 아니다**: 2차 아티팩트가 스스로 적었듯 "This is not even a censored observation: the window never ran". 남은 유일한 관측은 **10:59:46 ~ 11:31 KST 사이 baseline 2건 + 폴 20건(13+7) 전부 `hldg_qty 1` · `dnca_tot_amt 6686725.0` 으로 변화 없음**이라는 사실뿐이고, 이것이 "배당이 반영되지 않았다"는 뜻은 아니다(VP-002:772 'observed 0 != 0'). 이 예수금 값은 09-17 1차 baseline 과도 같다.
- `B_non_trade_event_detect` / `B_non_trade_reconcile` 두 키 모두 **NOT_ESTABLISHED 유지**. `approval_status` 세 건 모두 `UNAPPROVED_CANDIDATE`.
- **실행이 payable(00:00 KST)보다 크게 늦다.** 00:20 cron 이 ABORT 하는 바람에 본 실행이 10:59 로 밀렸고, 17:05 보고 cron 이 아티팩트를 보도록 창 종료를 16:50 KST 로 줄였다(`window_s` 2차 `21018.0` → 3차 `19351.0` → 4차 `14554.0`). 3·4차는 자기삭제된 러너의 **스크래치 사본**에서 돌렸다 — 가드와 프로브 명령은 같고, 보유 수량 파싱만 "조회 실패"와 "0주"를 구분하도록 갈랐다(10:58 의 오판을 막기 위해).
- **남은 것**: **P-8 3~5회차**(주문 권한이 돌아왔으므로 재개 가능) → **P-EXT ×5**(운영자 MTS 동석) → **N-15**(마지막). **P-CA 는 다음 대상 후보가 에스피지 `058610`(위 표의 2차 후보)이지만 실행 여부·시점은 운영자 결정이며 미정이다.**

## 수동 개입 기록

- 2026-09-10: 없음(실전 GET 2건은 무인 실행, HTS/MTS 미사용).
- 2026-09-28: 없음(P-8 ×2 는 호스트 cron 무인 실행, HTS/MTS 미사용).
- 2026-09-30: 00:20 cron ABORT 뒤 수동 재실행 3회(10:59 · 11:27 · 12:47). main 체크아웃의 untracked `.claude/settings.local.json.bak.*` 를 `~/.claude/backups/` 로 이동(증거 파일 아님, 워크트리 dirty 가드 해제 목적). 10:58 ABORT 의 원인 판별을 위해 11:00 경 보유 확인용 직접 GET 1회(20행, `000660` 수량 1). HTS/MTS 미사용, 주문 0건.

## 반환 항목 (핸드오버 §4)

- `git rev-parse HEAD`: 야간 실전 GET = `296c0e5f`; 모의 블록은 실행 로그의 `repo_commit=` 줄.
- 계좌 지문: 실전 선물 `8304d859b87f` · 모의 선물/주식은 모의 블록 아티팩트에서.
- `python -m tools.broker_probes.run --coverage` 출력: 모의 블록 종료 후 첨부.
