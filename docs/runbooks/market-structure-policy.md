# Market Structure Policy

기준: 2026-11-20. 이 런북은 `config/market_schedule.yaml` 의 값 **둘**이 왜 그 값인지와,
바꾸려면 무엇이 먼저 참이어야 하는지를 적는다. 그 파일의 주석이 이 문서를 가리킨다.

> 2026-11-20 에 레거시 거래 런타임 시절의 기록(ATS/SOR 라우팅 게이트 · 2026-06-28 의
> 08:45 전환 작업 기록 · Setup A/C/D 창 재평가 표)을 지웠다. 그것이 설명하던 모듈
> (`services/trading/orchestrator.py` · `stock_order_router` · `shared/strategy/exit/*`)은
> 2026-11 의 레거시 제거(L1–L7)로 사라졌다 — `git log --diff-filter=D -- docs/runbooks/`.
>
> ⚠ **TOS tenant 의 세션 창은 이 파일이 아니다.** 각 트리의 `calendar.yaml`
> (`session_overrides` 포함)이 정하고, 절차는
> [tos-paper-boot.md](tos-paper-boot.md) §7.2-g 다. `market_schedule.yaml` 은 그 밖의
> 잔존 코드(`shared/strategy/market_time.py` · `shared/decision/context.py` ·
> `shared/backtest/market_context_replay.py`)가 읽는다.

## 현재 정책

| 항목 | 정책 | 설정 |
|---|---|---|
| 선물 정규장 | 일중 전용. 개장 08:45 KST (2026-06-28 전환) | `market_schedule.futures.regular.open: "08:45"` · `close: "15:45"` |
| 선물 야간세션 | **fail-closed 로 비활성** | `market_schedule.futures.night.enabled: false` |
| 주식 venue | KRX 전용. ATS/SOR 은 운영자 승인 전까지 쓰지 않는다 | 자동 라우팅 경로는 존재하지 않는다(레거시 제거) |
| 주식 시간외 | 자동 거래 없음 | `market_schedule.stock.extended` 는 자동화에 대해 비권위적이다 |

`night.enabled` 는 `shared/strategy/market_time.py` 가 읽고, **읽기에 실패하면 비활성으로
취급한다** — 설정 부재가 야간 거래를 여는 쪽으로 틀리지 않는다.

## Futures Night Session Gate

`night.enabled: true` 로 바꾸기 전에 전부 참이어야 한다:

- 야간 피드와 주문 API 거동이 주간과 **따로** 검증됐다.
- 야간 주문 유효성·호가 한도가 리스크/주문 가드에 반영됐다.
- 킬 스위치 · 포지션 복구 · 정산 가정이 시험됐다.
- 운영자 승인이 허용 상품과 최대 익스포저를 **이름으로** 적었다.

⛔ 실전 선물 주문·증거금은 비협상 규칙으로 영구 차단이다 — 이 게이트를 통과해도 그것이
열리지 않는다.

## Stock ATS/SOR Gate

자동 ATS/SOR 라우팅을 다시 세운다면 그 전에 전부 있어야 한다:

- 같은 종목·같은 타임스탬프 창에 대한 KRX 와 ATS 호가 수집.
- venue · 가격개선 · 스프레드 · 호가잔량 · 체결 추정 · 사유를 담은 라우팅 결정 감사 기록.
- ATS 체결률·가격개선으로 보정된 paper 시뮬레이터.
- ATS 호가가 없을 때 KRX 로 폴백하는 것을 증명하는 통합 테스트.
