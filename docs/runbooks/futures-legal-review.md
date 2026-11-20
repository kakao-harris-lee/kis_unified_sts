# Futures — 법적·컴플라이언스 체크리스트 (§3 TR ID · §4 세션)

> ⛔ **이 문서는 실전 선물 주문을 여는 경로가 아니다.** 실전 선물 계좌 미펀딩과
> 실주문 경로 차단은 **영구 정책**이다(루트 `CLAUDE.md` 비협상 규칙) — 이 체크리스트를
> 채운다고 `config/futures_live.yaml::enabled` 를 뒤집지 않는다.
>
> 남긴 이유는 하나다: **코드와 설정이 §3 · §4 를 인용한다.**
> `shared/execution/tr_ids.py` · `config/kis/tr_ids.yaml` 가 §3 을,
> `shared/strategy/market_time.py` 가 §4 의 야간세션 조항을 가리킨다. 2026-11-20 에
> 나머지 절(ToS · 세금 · 감사 보존 · 서명란)과 그것이 가리키던 삭제된 모듈·계획 참조를
> 지웠다 — `git log --diff-filter=D -- docs/runbooks/`.

## 3. KIS API — TR ID (모의 → 실전)

모의 서버는 시뮬레이션 TR ID 를 쓴다. 실전 계좌 제출에는 운영 TR ID 가 필요하다.

- **정본은 `config/kis/tr_ids.yaml`** 이고 `shared/execution/tr_ids.py::tr_id()` 가 읽는다.
  이 파일을 KIS 계좌 담당자의 명세와 대조한다(선물 주문·정정·취소·잔고 조회·체결 조회).
- 실전 API 키는 **같은 KIS 계좌**에 등록돼 있어야 한다(교차 계좌 드리프트 금지).
- 단일 계좌 전제 — 자동매매와 수동 데스크가 계좌를 공유하면 포지션 상태가 오염된다.

⚠ 이 저장소에서 실전 키는 **GET 전용**이다. 선물 주문 프로브(`tools/broker_probes/`)는
`tools/broker_probes/common.py::assert_no_live_futures_config` 가
`config/futures_live.yaml::enabled` 를 보고 거부한다.

## 4. 거래 세션

- **야간 세션(18:00–05:00)은 `config/market_schedule.yaml::market_schedule.futures.night.enabled`
  에서 명시적으로 `false` 다.** `shared/strategy/market_time.py` 가 그 값을 읽고, 읽기에
  실패하면 **비활성으로 취급한다**(fail-closed). 켜려면
  [market-structure-policy.md](market-structure-policy.md) 의 Futures Night Session Gate 를
  먼저 통과해야 한다.
- 정규장 창은 같은 파일의 `stock.regular`(09:00–15:30) · `futures.regular`(08:45–15:45) 다.
  TOS tenant 트리의 세션 창은 이 파일이 아니라 각 트리의 `calendar.yaml` 이 정한다.
