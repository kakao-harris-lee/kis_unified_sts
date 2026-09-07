# F-9 Gate 1b 제어 동등성 CLOSED 경로 — 디커플 선물 체인에 모놀리식 진입 제어 이식

- 날짜: 2026-09-07
- 저자: 세션 모델(단독 저작, 운영자 지시 2026-09-04)
- 상태: 승인된 방향(운영자 «CLOSED 경로로 진행», 2026-09-07) · 구현 착수
- 선행: `docs/runbooks/futures-pipeline-cutover-f9.md` Gate 1b 인벤토리 ·
  «TOS 이후 레거시 제거 3층 판정»(PR #648, 1층 완료)

## 0. 문제

F-9 컷오버(`trader-futures` 정지 → `futures-pipeline` 프로파일)는 모놀리식이
진입 시점에 강제하는 호가·시간 제어 6종을 발화 불가 상태로 만든다. 런북 Gate 1b는
각 행을 CLOSED(배선 SHA + 섀도에서 실제 거부 증거) 또는 ACCEPTED(운영자 서명)로
처분하기 전 Gate 2 진입을 막는다. 운영자는 CLOSED 경로를 택했다.

현재 소스 재검증(2026-09-07, main `ede248ad`):

| 제어 | 모놀리식 | 디커플 | 처분 |
|---|---|---|---|
| 스프레드 | `FuturesSlippageController` `:360` | `SpreadFilter` provider 미배선 | 본 계획 §2-B |
| 호가 깊이 | `:371` | 없음 | §2-B |
| 신호 노후 | `:329` | 없음 | §2-B |
| 변동성 쿨다운(틱 이동) | `:341` | 없음(risk.yaml `volatility`는 ATR 백분위 = 다른 제어) | §2-B |
| 블랙아웃 창 | `:336` | `TradingHoursFilter` 세션 창만 | §2-B (paper override 는 `[]`) |
| 전역 동시 포지션 수 | `position_tracker.can_open_position` `max_positions` | `ConcurrentPositionsFilter` count provider 미배선 | §2-C |

## 1. 리서치 결과 (재사용 대상)

- **`shared/execution/slippage_control.py` 는 이미 공용 모듈이다.** 상태는 심볼별
  deque/쿨다운뿐이고 입력은 `dict` 호가(`bid_price_1/ask_price_1/bid_qty_1/ask_qty_1/
  close/timestamp`)와 `Signal` 시각이다. 모놀리식 전용 코드가 아니다.
- **`services/order_router/main.py` 는 이미 `KISFuturesPriceFeed` 를 실 WS 로
  구동한다**(`:776-778`, paper/live 공통). 이 피드는
  `get_orderbook_snapshot(symbol)` 로 컨트롤러가 요구하는 정확한 payload 를 돌려준다
  (`shared/kis/futures_feed.py:420-435`). 모놀리식도 같은 메서드로 호가를 얻는다
  (`orchestrator.py:4658-4677`).
- 모놀리식의 설정 적재+paper 병합 로직(`orchestrator.py:718-741`)은 오케스트레이터
  private 메서드에 갇혀 있다. 공용화 대상.
- `paper_override`(execution.yaml:233-247)는 paper 에서 스프레드 6틱·깊이 1.0x·
  노후 3.5s·블랙아웃 `[]`·교차자산 off 로 완화한다. **paper 컷오버 동등성 = 같은
  YAML + 같은 병합 규칙**이지 상수 복제가 아니다.
- 호가 제어의 자연스러운 자리는 **order_router 의 전송 직전**이다. 모놀리식도
  `_submit_entry_order` 즉 실행 시점에 평가한다(`orchestrator.py:5781-5790`).
  risk_filter 는 호가를 보지 못하므로 거기 두면 stub provider 를 또 만들게 된다.

### 기각한 대안

- risk_filter 의 `SpreadFilter`/`VolatilityFilter` 에 provider 를 배선: risk_filter 는
  호가 스트림을 소비하지 않아 Redis 경유 호가 캐시가 추가로 필요하고, 깊이·노후·
  블랙아웃은 여전히 필터가 없어 새 필터 3종을 저작해야 한다(바퀴 재발명).
- 컨트롤러를 order_router 에 복제: DRY 위반. 공용 모듈을 그대로 쓴다.
- risk.yaml `volatility.enabled` 전환: 그 필터는 ATR 백분위 게이트(P4 신설)로
  모놀리식에 대응물이 없다. 동등성 범위 밖이며 별도 운영자 결정.

## 2. 변경 (최소 신규 표면)

### A. 설정 적재 공용화 — `shared/execution/slippage_control.py`

`load_futures_slippage_config(exec_cfg: Mapping, *, paper_trading: bool) ->
SlippageControlConfig` 신설. 본문은 `orchestrator.py:728-741` 을 그대로 옮긴다
(`paper_override` pop → `enabled` 참일 때만 deep-merge, `enabled` 키 제외).
리뷰 정정(2026-09-07): 병합(raw dict)과 `from_dict` 코어션은 오케스트레이터의
두 `try` 범위를 그대로 보존하도록 분리한다 — 코어션 `ValueError/TypeError` 는
경고+비활성이지 기동 실패가 아니다.
`_deep_merge_config_dict` 는 `shared/utils` 에 기존 deep-merge 가 있으면 그것을,
없으면 이 모듈로 이동. 오케스트레이터는 헬퍼를 호출하도록 바꾸되 로그·예외 처리는
유지(값-보존 리팩터).

### B. order_router 전송 직전 게이트 — `services/order_router/main.py`

- 데몬 빌드(`_build_and_run`)에서 `load_futures_slippage_config(ConfigLoader.load(
  "execution.yaml"), paper_trading=(mode == "paper"))` → `cfg.enabled` 이고
  `cfg.order_router_gate` 참이면 `FuturesSlippageController(cfg)` 를 데몬에 주입.
  `cross_asset_enabled` 면 피드 심볼에 `cross_asset_symbol` 추가(`update_symbols`).
- `handle_message` 에서 `position_size_cap`(수량 클램프) 다음, **live 일일 거래
  카운터 INCR 보다 앞에**(리뷰 정정 2026-09-07: 초판은 «daily_trade_cap 다음»이라
  적었으나 그러면 차단된 진입이 `max_daily_trades: 2` 를 소진한다 — 모놀리식에는
  이 결합이 없다), `place_passive_limit_futures` 직전에:
  ```python
  decision = controller.evaluate_entry(
      symbol=signal.symbol, is_buy=<signal_direction 이 long>, quantity=quantity,
      signal_price=signal.price, signal_timestamp=signal.timestamp,
      quote_payload=feed.get_orderbook_snapshot(signal.symbol),
      cross_asset_payload=feed.get_orderbook_snapshot(cross) if cross else None)
  ```
  `decision.action` 이 진입 진행이 아니면 `slippage_blocked_count += 1`, 사유·
  spread_ticks 를 warning 로그, `return True`(소비·재시도 없음 — 모놀리식 `:5657`
  abort 와 동일). 진행이면 기존 경로 그대로.
- 틱 공급: 피드가 틱 콜백을 노출하면 `register_trade_tick` 을 연결(모놀리식
  `:1162-1172` 와 동일). 노출하지 않으면 컨트롤러의 자기-공급(`:357`)에 의존하고
  그 사실을 로그 한 줄로 남긴다.
- 롤백 스위치: execution.yaml `futures_slippage_control.order_router_gate:
  ${FUTURES_ROUTER_SLIPPAGE_GATE:true}` 한 키. `SlippageControlConfig.from_dict`
  가 읽고 기본 true. 모놀리식은 이 키를 무시한다.
- 범위 밖: `evaluate_retry`(passive 타임아웃 후 재시도)는 `PassiveMaker` TIF 가
  이미 담당하므로 이번 동등성 범위에 넣지 않는다(런북 인벤토리에 없는 행).

### C. 전역 동시 포지션 수 — `services/risk_filter/main.py`, `config/risk.yaml`

- `open_positions_count_provider` 를 `has_open_position_provider` 와 같은 키
  (`futures:monitor:positions`, HLEN)로 배선. Redis 오류 시 기존 provider 와 같은
  극성(fail-closed)으로.
- `risk.concurrent_positions.enabled: true`, `max_positions_per_asset` 기본값을
  모놀리식 선물 실효 상한과 일치시킨다(오케스트레이터가 `PositionTrackerConfig.
  max_positions` 를 어떻게 정하는지 측정해 그 값을 YAML 주석에 근거로 적는다).
  `risk_stock.concurrent_positions` 는 손대지 않는다.
- `tests/unit/risk/test_provider_wiring.py` 에 count provider 단언 추가(런북
  «Re-verifying» 3항이 요구).

### D. 테스트 (happy + negative)

- `tests/unit/execution/test_slippage_control.py`: 로더 — paper 병합 적용/미적용,
  `enabled:false`, `order_router_gate` 기본·env 오버라이드.
- `tests/unit/services/test_order_router_main.py`: 게이트 차단(넓은 스프레드 →
  소비·전송 0·카운터 1), 통과(전송 1), 컨트롤러 None 이면 기존 경로, 호가 부재 시
  컨트롤러 판정(차단)이 그대로 적용됨.
- `tests/unit/trading/`: 오케스트레이터 특성화 — 같은 YAML 에서 헬퍼 경유 결과가
  리팩터 전과 동일한 `SlippageControlConfig`.
- `tests/unit/services/test_risk_filter_main.py` + provider wiring: count provider.

### E. 런북 갱신 — `docs/runbooks/futures-pipeline-cutover-f9.md`

Gate 1b 인벤토리 6행의 «Decoupled» 칸을 배선 위치+SHA 로 갱신하되 상태는
**«wired @ SHA — shadow rejection evidence pending»** 으로 둔다. CLOSED 는 섀도에서
실제 거부가 관측된 뒤 운영자가 적는다. «Re-verifying» 1항에 주의 추가: risk_filter
의 `SpreadFilter`/`VolatilityFilter` inert 로그는 계속 나오며(그 필터들은 이번
경로가 아님), 동등성 확인은 order_router 기동 로그 «Futures slippage control
enabled (paper|live)» 와 `slippage_blocked_count` 지표로 한다.

## 3. 순서·검증

1. A+B+D(로더·라우터·오케스트레이터 특성화) — 실행 에이전트 1.
2. C+D(risk_filter)+E — 실행 에이전트 2 (파일 집합 disjoint).
3. 오케스트레이터와 별도 레인의 Claude 측 코드 리뷰(저작-검증 분리).
4. `ruff`, `black`(변경 파일), `tests/unit` 2-pass, `tools/tos_firewall_check.py`.
5. paper 서버 재배포 후 Gate 1 섀도 재개(운영자 수동): 거부 카운터가 0 이 아닌
   날이 나와야 CLOSED 기입 가능.

## 4. 비협상 규칙 확인

- 설정 주도: 임계값은 execution.yaml/risk.yaml 만. 코드 상수 없음.
- DRY: 컨트롤러·로더 공용 모듈 재사용, 복제 0.
- 롱/숏 대칭: `is_buy` 는 `signal_direction` 에서 파생.
- 실계좌 무입금·실주문 경로 차단 불변: 이 변경은 전송을 «줄이는» 게이트만 추가한다.
- tos/ 무변경.
