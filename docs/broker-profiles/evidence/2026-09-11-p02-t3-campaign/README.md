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

이후 남은 것: **P-CA**(1차 2026-09-17 SK텔레콤, 위 표), **P-EXT ×5**·**P-8 ×5**(모의 선물 주문 권한 복구 후, 운영자 MTS 동석).

## 수동 개입 기록

- 2026-09-10: 없음(실전 GET 2건은 무인 실행, HTS/MTS 미사용).

## 반환 항목 (핸드오버 §4)

- `git rev-parse HEAD`: 야간 실전 GET = `296c0e5f`; 모의 블록은 실행 로그의 `repo_commit=` 줄.
- 계좌 지문: 실전 선물 `8304d859b87f` · 모의 선물/주식은 모의 블록 아티팩트에서.
- `python -m tools.broker_probes.run --coverage` 출력: 모의 블록 종료 후 첨부.
