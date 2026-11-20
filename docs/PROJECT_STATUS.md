# Project Status — KIS Unified STS

기준: 2026-11-20. **지금 도는 것만 적는다.** 끝난 일의 서사는 git 이력에 있다
(`git log --diff-filter=D -- docs/`). 계층 이름과 비협상 규칙은 루트
`CLAUDE.md`, tos 작업 규율은 `tos/CLAUDE.md` 가 정본이다.

## 무엇이 돈다

| 축 | 지금 | 정본 |
| --- | --- | --- |
| 실행 권한 | TOS 커널(`tos/`) + 런타임(`tos/runtime/`). 레거시 거래 런타임은 없다(L1–L7, 코드는 태그 `legacy-final` `6fc17c0f8d25`) | [legacy removal](plans/2026-11-07-legacy-removal-plan.md) |
| 운영자 표면 | `sts tos status` · `inspect` · `perf` · `export-bars`, 대시보드 `/api/tos/*`+`/health`, UI `/tos` | [public interfaces](architecture/tos-public-interfaces.md) |
| 웹 입구 | Caddy 호스트 `DASHBOARD_HOST_PORT=5081` 하나. `dashboard:8001` · `strategy-builder-ui:3100` 은 내부 전용 | [ports](ports.md) |
| 실주문 | **0.** 실전 키는 GET 전용, 선물은 SYNTHETIC, 실전 선물 주문·증거금은 영구 정책 차단 | CLAUDE.md 비협상 규칙 |

## 도는 tenant (`config/tos_runtime/`)

| 트리 | 전송 | 역할 | cron(KST, 평일) |
| --- | --- | --- | --- |
| `paper` | SYNTHETIC | 상주 부팅증명 세션 | 08:45 start · 15:45 stop |
| `cp3-setup-d-long` | SYNTHETIC 미니선물 | Setup D LONG 신호 관측 | 08:38 |
| `cp3-setup-d-short` | SYNTHETIC 미니선물 | 대칭 관측 | 08:40 |
| `cp3-setup-d-stock-005930` | KIS **MOCK** 주식 | 카나리아 — 주문 경로가 매일 살아 있는지 | 08:53 |
| `cp3-setup-d-stock-000660` | KIS **MOCK** 주식 | 실험 A 예정 — Setup D LONG | 08:55 |
| `cp3-setup-d-stock-005380` | KIS **MOCK** 주식 | 실험 B 예정 — RSI/%R | 08:57 |

주식 셋은 **지금 전부 R4 프로브 진입 규칙**으로 돈다(`strategy_bindings.yaml::m2_probe_entry_enabled:
true` 셋 다, 2026-11-20 실측). 전략이 아니라 「경로가 살아 있나」를 매일 재는 카나리아이고,
역할 분화(000660 Setup D · 005380 RSI/%R)는 [활용 계획](plans/2026-11-19-tos-usage-plan.md) §4.1
의 다음 단계다.

콜드 백업은 18:00(paper) · 18:20(LONG) · 18:40(SHORT) 에 돈다
([런북](runbooks/tos-evidence-cold-backup.md)). 부팅·재시작 절차는
[paper 운영 런북](runbooks/tos-paper-boot.md).

## 완료 기준과 다음 단계

- **`TOS_PAPER_READY` 선언됨 — 2026-11-18**, main `40aa8705`. 다섯 문장 전부 ✅
  ([판정과 근거](plans/2026-11-11-tos-paper-ready-relaxation.md) §6).
- 지금 재는 것: 대형주 3종목이 매일 매수→매도→해제→재매수를 막힘 없이 도는가
  ([활용 계획](plans/2026-11-19-tos-usage-plan.md) §3 · 운용 규칙 U1~U6).
- 그다음: 종목별 운영 화면 → 카탈로그 `rsi`/`williams_r` 와 두 번째 전략 YAML →
  리플레이(P3) → 손절·목표(P4). 순서는 [로드맵](plans/2026-11-11-tos-platform-roadmap.md)
  과 활용 계획 §5.

## CI 가 막는 것

`tos-gate`(`tools/tos_redigest.py --check`) · `tos-firewall` · `ruff` 가 필수 체크다.
방화벽 계약은 [boundary design](plans/2026-07-20-tos-boundary-and-import-firewall-design.md)
§3, 테스트 병렬 규칙은 [CI_PARALLEL_NOTES](CI_PARALLEL_NOTES.md).

## 알려진 위험

- **달력은 2027년에 대해 fail-open 이다.** `config/tos_runtime/*/calendar.yaml` 의
  `holidays` 에 2027 항목이 0건이라, 2027-01-01 부터 모든 평일이 거래일로 판정된다 —
  건너뛰는 쪽이 아니라 **부팅하는 쪽으로** 틀린다. 해결은 휴장 목록을 먼저 채우는 것이다.
- 코퍼스가 커널 리비전을 가로지른다: 래퍼가 매일 `origin/main` 으로 워크트리를 새로
  만들므로, 리플레이가 재해석하는 배선(전략 레지스트리 키·스테이지 구성·정책 스코프)을
  바꾼 PR 은 다음 날 아침 잎을 held 로 떨어뜨릴 수 있다. 종목 축만 월물별 잎으로 닫혀
  있다(`tos/runtime/tests/compose/test_contract_roll_replay.py`).
