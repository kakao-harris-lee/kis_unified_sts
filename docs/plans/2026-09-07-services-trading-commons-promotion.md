# services/trading 공용 모듈 승격 — 모놀리식 은퇴 선행 작업

- 날짜: 2026-09-07 · 저자: 세션 모델(단독) · 상태: 구현 착수
- 선행: «TOS 이후 레거시 제거 3층 판정»(2026-09-07) — `services/trading/` 은
  디커플 서비스 5개가 경계 너머로 임포트하고 있어 통째 은퇴가 불가하다.

## 0. 측정 (main `b0bb74e7`)

경계 너머 임포터 16곳(비테스트)이 `services.trading.*` 8개 모듈에 의존한다.
그중 `shared/backtest/adapter.py`·`shared/indicators/engine/streaming_backend.py`
(docstring)·`shared/llm/unified_market_analyzer.py`(docstring)는 **shared → services
역방향 의존**으로 계층 위반이다.

| 모듈 (services/trading/) | 줄 | 경계 너머 임포터 | 폐쇄 집합 내 의존 |
|---|---|---|---|
| `stream_consumer_feed` | 207 | stock_strategy·stock_exit·stock_monitor·futures_monitor·decision_engine | 없음 |
| `indicator_engine` | 576 | stock_strategy·decision_engine·shared/backtest/adapter·scripts 1 | calculations·candles·queries |
| `indicator_calculations` | 292 | shared/indicators/engine/streaming_backend(docstring)·scripts 2 | candles |
| `indicator_candles` | 204 | scripts 1 | 없음 |
| `indicator_queries` | 813 | (engine 경유) | candles |
| `strategy_manager` | 868 | stock_strategy·scripts 1 | llm_context_provider |
| `llm_context_provider` | 186 | (manager 경유) | 없음 |
| `llm_context_publisher` | 537 | shared/llm/unified_market_analyzer(docstring)·scripts 1 | 없음 |

폐쇄 집합의 외부 의존은 전부 `shared.*` 뿐이다(`services.*`·`cli` 0). 따라서
8개를 `shared/` 로 옮기면 **위 세 파일의** 역방향 의존이 사라지고 `services/trading/`
에는 오케스트레이터 전용 코드만 남는다. 테스트 파일 43개가 옛 경로를 임포트한다.
(리뷰 정정 2026-09-07: `shared/` 전체의 역방향 의존이 0 이 되는 것은 아니다 —
`shared/kis/{stock_feed,client,futures_feed,websocket}.py`·`shared/scanner/accumulation.py`
의 `services.monitoring.*` 지연 임포트 5건은 기존 것이며 이번 범위 밖.)

주의(리뷰 적발): 옛 부모 패키지 `services/trading/__init__.py` 는 지연 `__getattr__`
파사드였고 `shared/llm/__init__.py` 는 즉시 임포트 패키지다. `strategy_manager` 의
`llm_context_provider` 모듈 수준 임포트를 그대로 옮기면 StrategyManager 임포트가
LLM SDK 전체를 끌어온다(449→2523 모듈). 사용 지점 지연 임포트로 고정하고
서브프로세스 테스트로 핀한다.

## 1. 목적지 (기존 패키지 재사용, 신설은 하위 패키지 하나)

| 원본 | 목적지 | 근거 |
|---|---|---|
| `stream_consumer_feed.py` | `shared/streaming/consumer_feed.py` | 이미 `shared.streaming.{codec,audit,trading_state}` 만 사용 |
| `indicator_engine.py` | `shared/indicators/streaming/engine.py` | `shared/indicators/engine/` 은 백엔드 레지스트리라 이름 충돌 — 스트리밍 런타임은 별도 하위 패키지 |
| `indicator_calculations.py` | `shared/indicators/streaming/calculations.py` | `streaming_backend` 가 이미 이 믹스인을 참조 |
| `indicator_candles.py` | `shared/indicators/streaming/candles.py` | |
| `indicator_queries.py` | `shared/indicators/streaming/queries.py` | |
| `strategy_manager.py` | `shared/strategy/manager.py` | `shared.strategy.{base,registry,filters,decision_cadence}` 소비자. `shared/strategy/__init__` 은 manager 를 임포트하지 않는다(순환 방지) |
| `llm_context_provider.py` | `shared/llm/context_provider.py` | |
| `llm_context_publisher.py` | `shared/llm/context_publisher.py` | `shared/llm/__init__` 에 추가하지 않는다(순환 방지) |

## 2. 규칙

- `git mv` 로 이동(이력 보존). **재수출 shim 을 옛 경로에 남기지 않는다** — 임포터
  전부(서비스·shared·scripts·cli·tests 43파일·`services/trading/` 내부)를 새 경로로
  기계적으로 고친다. 옛 경로가 남으면 은퇴 시 또 한 번 청소해야 한다.
- 모듈 본문은 임포트 줄 외 변경 0(값-보존). 클래스·함수 이름 불변.
- 테스트 파일은 제자리에 두고 임포트만 고친다(`tests/unit/trading/test_indicator_*`
  이동은 후속 — 이번 PR 의 diff 를 «이동+임포트» 로 한정).
- 문서: `CLAUDE.md` «Current Runtime Architecture» 와 `docs/runtime_storage_architecture.md`
  등 옛 경로를 언급하는 현행 문서만 갱신(`docs/archive/**`·`docs/plans/archive/**` 제외).
- 순환 임포트 검증: `python -c "import shared.strategy.manager, shared.llm.context_publisher,
  shared.indicators.streaming.engine, shared.streaming.consumer_feed"` 가 깨끗해야 한다.

## 3. 검증

`ruff`(unused/relative import 정리 포함) · `black --check` 변경 파일 · `mypy shared/`
변경 파일의 오류 수가 이동 전과 같거나 적을 것 · `tests/unit` 2-pass ·
`tools/tos_firewall_check.py` · `grep -rn "services\.trading\.\(stream_consumer_feed\|
indicator_\|strategy_manager\|llm_context\)"` 가 저장소 전체(archive 제외)에서 0.

## 4. 범위 밖 (이번 PR 아님)

- 백테스트 엔진 기본값 `vectorbt` 전환: 계획 2026-07-08 §249 운영자 flip 게이트
  (paper 관찰 + 허용목록 확장 선행). CI `backtest-extra` 가 parity 테스트를 계속
  녹색으로 유지 중이라는 사실만 기록.
- 단일 리스크 오케스트레이터(P6)·KIS facade(F-9 컷오버 후): 전제 미개방.
