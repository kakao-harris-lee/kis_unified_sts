# P0-2 T3 캠페인 — 모의 운영 서버 실행 (2026-09-10 야간 ~ 2026-09-11)

핸드오버: `docs/runbooks/2026-09-10-p02-probe-handover-paper-server.md` · 런북(정본): `docs/runbooks/kis-capability-probes.md`
실행 호스트: 배포(paper) 서버 · 저장소 체크아웃 `main` · 실행 전 `git status --short` 비어 있음 확인(핸드오버 §1-1)
`config/futures_live.yaml::enabled: false` 확인 · `futures:live:suspended` 미설정(빈 값)

## 서버 측에서 채운 값 (핸드오버 §2)

| 값 | 결정 | 근거 |
|---|---|---|
| mini 근월물 코드 | `A05610` (2026-10월물, 만기 2026-10-08) | `futures:contract:latest` read-model(2026-09-10 08:00): front `A05609` 는 2026-09-10 만기(`roll_state=expired`, `new_entry_front_allowed=false`), `next_symbol=A05610` |
| N-18 주간 / 야간 코드 | `A01612` / `1A01612` | read-model 의 야간 코드 패턴 `1A01609`(= `1` + 주간 코드)를 2026-09-10 만기 뒤 12월물에 적용. N-18c 두 leg 모두 `rt_cd=0`(아래) |
| P-CA 대상 종목 · CA 7-시각 | 조사 중(DART/KIND, 보유 20종목 기준) — 확정 시 이 표를 갱신 | 모의 주식 계좌 보유 1페이지(20행, `get_stock_balance` GET): 000660 005930 005935 006340 006360 009830 010140 010170 017670 028050 030530 032820 034020 035420 035720 047040 058610 073240 098460 119850 (page_size=20 은 2026-08-05 P-BAL 실측) |

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

러너 `~/.config/kis-probes/run-p02-t3-20260911.sh`(09:05 KST 이후, `.env.mock` 만 소싱): **P-8 ×5**(`A05610`, `--pace-s 1.1`, 회차 간 75s) → **P-15** → **N-15**(`A05610`, `--trials 1`) → **P-BAL**(모의 주식, `--env mock`). 중단 규칙: `EGW00201` / `초당 거래건수` 관측 시 재시도 없이 중단(핸드오버 §3). 이후 **P-CA**(운영자 t0 · 대상 확정 후) · **P-EXT ×5**(운영자 MTS 수동 주문 대기). 실행 후 이 절을 채운다.

| 시각(KST) | 프로브 | 아티팩트 | mode / prov / env | errors / skips | 요지 |
|---|---|---|---|---|---|
| (예정) | | | | | |

## 수동 개입 기록

- 2026-09-10: 없음(실전 GET 2건은 무인 실행, HTS/MTS 미사용).

## 반환 항목 (핸드오버 §4)

- `git rev-parse HEAD`: 야간 실전 GET = `296c0e5f`; 모의 블록은 실행 로그의 `repo_commit=` 줄.
- 계좌 지문: 실전 선물 `8304d859b87f` · 모의 선물/주식은 모의 블록 아티팩트에서.
- `python -m tools.broker_probes.run --coverage` 출력: 모의 블록 종료 후 첨부.
