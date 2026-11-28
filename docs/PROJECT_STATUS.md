# Project Status — KIS Unified STS

기준: 2026-11-27. **지금 도는 것만 적는다.** 끝난 일의 서사는 git 이력에 있다
(`git log --diff-filter=D -- docs/`). 계층 이름과 비협상 규칙은 루트
`CLAUDE.md`, tos 작업 규율은 `tos/CLAUDE.md` 가 정본이다.

## 무엇이 돈다

| 축 | 지금 | 정본 |
| --- | --- | --- |
| 실행 권한 | TOS 커널(`tos/`) + 런타임(`tos/runtime/`). 레거시 거래 런타임은 없다(L1–L7, 코드는 태그 `legacy-final` `6fc17c0f8d25`) | [legacy removal](plans/2026-11-07-legacy-removal-plan.md) |
| 운영자 표면 | `sts tos status` · `inspect` · `replay` · `perf` · `export-bars` · `export-symbols` · `export-status`, 대시보드 `/api/tos/*`+`/health`, UI `/tos`(상태 띠 · tenant 카드 · 판단 근거 · 거래 현황 · 사건 기록 · 시스템 내부 — [가독성 계획](plans/2026-11-25-tos-operator-page-legibility-plan.md) P1–P3 머지, 장중 5분 갱신) | [public interfaces](architecture/tos-public-interfaces.md) |
| 웹 입구 | Caddy 호스트 `DASHBOARD_HOST_PORT=5081` 하나. `dashboard:8001` · `strategy-builder-ui:3100` 은 내부 전용 | [ports](ports.md) |
| 실주문 | **0.** 실전 키는 GET 전용, 선물은 SYNTHETIC, 실전 선물 주문·증거금은 영구 정책 차단 | CLAUDE.md 비협상 규칙 |

## 도는 tenant (`config/tos_runtime/`)

| 트리 | 전송 | 역할 | cron(KST, 평일) |
| --- | --- | --- | --- |
| `paper` | SYNTHETIC | 상주 부팅증명 세션 | 08:45 start · 15:45 stop |
| `cp3-setup-d-long` | SYNTHETIC 미니선물 | Setup D LONG 신호 관측 | 08:38 |
| `cp3-setup-d-short` | SYNTHETIC 미니선물 | 대칭 관측 | 08:40 |
| `cp3-setup-d-stock-005930` | KIS **MOCK** 주식 | 카나리아 — 주문 경로가 매일 살아 있는지 | 08:53 |
| `cp3-setup-d-stock-000660` | KIS **MOCK** 주식 | 실험 A — Setup D LONG (R4 프로브 끔) · **YAML 손절·목표**(`position_context` 켬) | 08:55 |
| `cp3-setup-d-stock-005380` | KIS **MOCK** 주식 | 실험 B — RSI / Williams %R 되돌림 | 08:57 |

주식 셋의 역할은 갈라져 있다([활용 계획](plans/2026-11-19-tos-usage-plan.md) §4.1, 2026-11-27
설정 실측). 005930 만 R4 프로브 진입 규칙을 켠 카나리아다
(`strategy_bindings.yaml::m2_probe_entry_enabled: true`) — 전략이 아니라 「경로가 살아 있나」를
매일 잰다. 000660 은 같은 값이 `false` 라 Setup D LONG 규칙만 발화하고, 005380 은
`strategies/rsi_wr_reversion_long.strategy.yaml` 로 돈다(Setup D 를 쓰지 않는다).

000660 은 **포지션 값을 읽는 첫 tenant** 다([P4 계획](plans/2026-11-27-tos-p4-position-fields-plan.md)
§3): `marketfeed.yaml::position_context` 를 켜고, 손절(`R5-EXIT-STOP-LOSS`)과
목표(`R6-EXIT-TAKE-PROFIT`)를 `strategy_bindings.yaml` 의 두 숫자(`stop_loss_bp` ·
`take_profit_bp`, bp 단위)로 선언한다. 두 진입 규칙(R1 · R4)에는
`capsule.position.side EQ "FLAT"` 가드가 붙었다. 시간 청산은 없다(운영자 결정 2026-11-28 §11 #3).
다른 네 트리는 `position_context` 를 켜지 않으므로 payload·환경·서명이 그대로다.
⚠ 규칙이 바뀌었으니 이 트리의 잎은 **재-genesis** 해야 배포된다
([런북](runbooks/tos-paper-boot.md) §7.2-f-1).

콜드 백업은 18:00(paper) · 18:20(LONG) · 18:40(SHORT) · 19:00/19:05/19:10(주식 005930·000660·005380) 에 돈다
([런북](runbooks/tos-evidence-cold-backup.md)). 부팅·재시작 절차는
[paper 운영 런북](runbooks/tos-paper-boot.md).

## 완료 기준과 다음 단계

- **`TOS_PAPER_READY` 선언됨 — 2026-11-18**, main `40aa8705`. 다섯 문장 전부 ✅
  ([판정과 근거](plans/2026-11-11-tos-paper-ready-relaxation.md) §6).
- 지금 재는 것: 대형주 3종목이 매일 매수→매도→해제→재매수를 막힘 없이 도는가
  ([활용 계획](plans/2026-11-19-tos-usage-plan.md) §3 · 운용 규칙 U1~U6).
- 끝난 것: `sts tos perf` · 종목별 운영 화면 · 카탈로그 `rsi`/`williams_r` 와 두 번째 전략 YAML ·
  리플레이(P3 — `sts tos replay` · CI 잡 `tos-replay-golden`, 2026-11-27).
- 손절·목표·수량(P4 — [계획](plans/2026-11-27-tos-p4-position-fields-plan.md)): 구현 단계 S0–S6 은
  2026-11-28 에 전부 머지됐다(#1190 · #1195 · #1196 · #1197 · #1198 · #1200). **남은 것은 관측이다** —
  ① 000660 새 잎(generation 3)의 첫 부팅(2026-11-30), ② 보유 중 포지션 값이 실제로 실리는지,
  ③ MOCK 에서 손절이 체결되는 날. 수량의 위험 단위 필드(`per_unit_risk_field_key`)는 **어느 트리도
  켜지 않았다** — 켜는 PR 이 #1199 를 함께 닫는다. 선물 두 트리에 같은 규칙을 적용하는 일은 ①~③ 뒤다.
- 주식 트리는 `config/tos_stock_tenants/TENANTS.yaml` 에서 렌더한다(생성물은 손으로 고치지 않는다 —
  `python scripts/tos/render_stock_tenant_trees.py` 가 검사, `--write` 가 재생성).
- 그다음: 성과 측정(P5). 순서는 [로드맵](plans/2026-11-11-tos-platform-roadmap.md) 과 활용 계획 §5.

## CI 가 막는 것

`tos-gate`(`tools/tos_redigest.py --check`) · `tos-firewall` · `ruff` 가 필수 체크다.
방화벽 계약은 [boundary design](plans/2026-07-20-tos-boundary-and-import-firewall-design.md)
§3, 테스트 병렬 규칙은 [CI_PARALLEL_NOTES](CI_PARALLEL_NOTES.md).

## 알려진 위험

- **2027 달력은 채웠지만 잠정값이다.** 2026-11-28 에 `config/tos_runtime/*/calendar.yaml`
  여섯 트리와 `config/market_schedule.yaml` 에 2027 휴장일 25건(평일 휴장 16건)과
  2028학년도 수능 세션 창(2027-11-18, 교육부 2025-06-01 발표 시행일)을 넣었다. 출처는
  **2027년 월력요항**(우주항공청 2026-06-29 발표)이고, KRX 2027 휴장일 공지는 아직
  없다(12월 중순 예상). 남은 일: ① KRX 공지가 나오면 25건과 수능 거래시간(+1h)을 한
  건씩 대조할 것 — 특히 노동절·제헌절 대체휴일(2027-05-03 · 07-19)은 두 날이 2026 부터
  공휴일이 된 뒤 처음 생기는 대체휴일이라 KRX 선례가 없다. ② 2026 목록에
  **2026-05-01(근로자의날) · 2026-06-03(지방선거) · 2026-07-17(제헌절)** 세 평일 휴장이
  빠져 있다(KRX 2026-05-19 공지가 뒤 둘을 휴장으로 고지). 모두 과거이고 CP-3 세션
  개시(2026-10) 이전이라 운영 영향은 없지만, 과거 구간 리플레이·백테스트의 거래일
  판정은 틀린다 — 지난 날짜를 고치는 일은 리플레이 표면이 따로 있어 운영자 결정 사항으로
  남긴다. ③ `shared/calendar.py::HOLIDAYS_2027`(동결된 Setup D 증인이 닿는
  하드코딩 목록)은 2027-06-07 을 현충일 대체휴일로 잘못 담고 있고 노동절·제헌절과 그
  대체휴일·12-31 이 빠져 있다. 증인 동결(`TOS_PAPER_READY`) 때문에 손대지 않았다.
- 코퍼스가 커널 리비전을 가로지른다: 래퍼가 매일 `origin/main` 으로 워크트리를 새로
  만들므로, 리플레이가 재해석하는 배선(전략 레지스트리 키·스테이지 구성·정책 스코프)을
  바꾼 PR 은 다음 날 아침 잎을 held 로 떨어뜨릴 수 있다. 종목 축만 월물별 잎으로 닫혀
  있다(`tos/runtime/tests/compose/test_contract_roll_replay.py`).
- 부팅은 잎의 전 이력을 재도출한다(`engine_driver.yaml::replay_window_events: 1000000`). 2026-11-27
  실측은 잎당 1.8~6.2초(1,200~4,200 이벤트)다. **잎당 60초를 넘으면** 창을 줄일지 다시 논의한다
  (운영자 결정 2026-11-28) — 선물 잎은 월물 롤마다 새로 열려 스스로 줄어든다.
- 크기 예산 등재 11건의 기한은 **2027-03-31** 이다(`config/tos_size_budget.yaml`). 지나면 필수 체크
  `tos-firewall` 이 모든 PR 에서 빨갛다. 분해는 P4 뒤 별도 작업이다.
