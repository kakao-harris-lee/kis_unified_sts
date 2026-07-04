# Stock Monitor / Observability Bridge (M5a) — Design

- Date: 2026-06-06
- Status: Design (pending implementation plan)
- Parent effort: `docs/superpowers/specs/2026-06-04-stream-pipeline-decoupling-design.md` (M5 cutover)
- Predecessors merged: M4-P (#415), M4-R/O (#416), M4-X (#417)
- Scope: **M5a — the first M5 sub-project.** A shadow-first, default-off observability/notification bridge daemon that consumes the decoupled stock daemon streams and republishes the dashboard-native state (positions/trades/signals/status) + sends **selective, important-only** Telegram alerts — so the React Cockpit and operator alerting keep working once the monolithic orchestrator's stock path is cut over.

## 1. Goal & scope

The decoupled stock pipeline (M4-P/R/O/X) produces fills (`order.fill.stock.shadow`), final signals (`signal.final.stock.shadow`), and a code-keyed positions working store (`stock:daemon:positions`). The monolithic orchestrator currently produces the **dashboard-native** state the React Cockpit reads (`trading:stock:status/trades/signals` + id-keyed positions snapshot) and sends Telegram alerts. M5a bridges the gap: it aggregates the daemon streams into the dashboard-native keys and owns alerting — the prerequisite "eyes" for a safe M5 cutover.

**Success criterion:** A shadow-first, default-off daemon that, running in parallel to the still-live orchestrator, consumes the daemon shadow streams and publishes an equivalent dashboard state to an **isolated** key namespace (`trading:stock:*:shadow`) for side-by-side validation, plus emits important-only Telegram (suppressed-to-log in shadow). The dashboard, `TradingStatePublisher`, and all M4 daemons are **unchanged** — M5a is a pure consume/translate layer. At M5d (separate spec) the same daemon promotes to `live` (no suffix → live keys + real Telegram).

비목표(out of scope): the actual cutover flag-flip / orchestrator shutdown (M5d), LLM context publishing (M5b), daily risk reset (M5c), orchestrator reduction (M5e), exit-reason/realized-pnl enrichment of the shared fill schema, equity-timeline / running-totals continuity (follow-up), futures.

## 2. Locked decisions (브레인스토밍 2026-06-06)

| 결정 | 선택 | 근거 |
|---|---|---|
| M5 분해 | 5 서브프로젝트 (M5a 관측/알림 → M5b LLM컨텍스트 → M5c 리셋 → M5d 컷오버 → M5e 축소), **M5a 먼저** | M5는 다중 서브시스템 — 단일 spec 불가. M5a는 컷오버 선행조건이자 shadow 단독 검증 가능 |
| shadow 동작 | **격리 키(`trading:stock:*:shadow`) + Telegram 서프레스** | orchestrator가 live 키·실 Telegram 중 → side-by-side 비교 검증, 이중알림/clobber 방지 |
| v1 범위 | positions + trades + status (fill 스트림) + **signals** (`signal.final.stock.shadow`) | 대시보드 4페이지 전부 — 완전한 관측성 브리지 |
| 배치 | **신규 집계 데몬** `services/stock_monitor/`, `TradingStatePublisher` raw-dict 재사용 | 관심사 단일, 대시보드/publisher/M4 무변경 |
| **Telegram 정책** | **중요 정보만 선별** (per-fill 금지) — 임계 초과 청산 + 헬스 이상 + 주기 다이제스트 | per-fill 알림은 멀티종목 포트폴리오에서 노이즈. signal-vs-noise |

## 3. Current state (감사 2026-06-06)

- **`TradingStatePublisher`** (`shared/streaming/trading_state.py`): 이미 **raw-dict 발행 메서드 보유** — `publish_raw_position(position_id, dict)`, `publish_raw_trade(dict)`, `publish_raw_signal(dict)`, `remove_position(id)`, `publish_status(dict)`. 주석: *"for non-orchestrator publishers"* (정확히 M5a 용). 모든 메서드 fire-and-forget(log, never raise).
- **`TRADING_STATE_KEY_SUFFIX`** (`_key()`, L48–54): 프로세스 env. 설정 시 모든 키에 `:<suffix>` 부착. **코드 변경 0으로 shadow 격리** — M5a 프로세스가 `shadow`로 설정→`trading:stock:status:shadow` 등. 대시보드 `TradingStateReader`도 동일 `_key` 사용.
- **대시보드 reader** (`TradingStateReader`): `get_status/positions/trades/signals` → `trading:stock:status`(HASH)/`positions`(HASH field=id)/`trades`(LIST max500)/`signals`(LIST max200). dashboard FastAPI(`services/dashboard/routes/trading.py`)가 사용.
- **대시보드 스키마**(M5a가 만들 dict 포맷):
  - position: `{id, code, name, side, quantity, entry_price, current_price, unrealized_pnl, pnl_pct, entry_time, strategy, state, highest_price, lowest_price, fee_rate, stop_price, client_order_id}`
  - trade(closed): `{id, symbol, name, side, quantity, entry_price, exit_price, pnl, pnl_pct, strategy, entry_time, exit_time, exit_reason}`
  - signal: `{id, symbol, name, side, signal_type, strategy, price, confidence, timestamp, executed, reason, stage}`
- **fill 스트림**(`order.fill.stock.shadow`, FillLogger 스키마): `signal_id, order_id, symbol, side, order_type, requested_price, filled_price, tick_size_points, slippage_ticks, quantity, requested_at_ms, filled_at_ms, latency_ms, venue, trade_role(entry|exit), broker_error_code`. **strategy/name 없음**.
- **final 스트림**(`signal.final.stock.shadow`): M4-P candidate(`code, name, strategy, direction, price, quantity, confidence, generated_at_ms, metadata_json, signal_id`) + M4-R(`size_multiplier, filtered_at_ms`). **strategy/name 보유** → fill 보강 소스.
- **M4-X 페어링 사실**: 청산 fill `signal_id == pos.id == 진입 signal_id` (M4-X `log_fill(signal_id=pos.id)`, pos.id=진입 레코드 signal_id). 1포지션/종목(OpenPositionFilter) → code 페어링 안전.
- **데몬 working store**: `stock:daemon:positions` (M4-O/X, field=code, value `{code, entry_price, quantity, opened_at_ms, state, signal_id, high_water, low_water}`). dashboard-native `trading:stock:positions[:shadow]`와 분리해 live monitor publish가 M4-X working-store를 덮어쓰지 않게 한다.
- **Telegram**: `shared/notification/telegram.py::notifier_for_domain("stock")` → notifier 또는 None.

## 4. Target architecture

### 4.1 모듈
```
services/stock_monitor/
  __init__.py
  daemon.py   # StockMonitorDaemon (consumer task + status task)
  main.py     # flag-gated entrypoint
```
StreamStage(단일 스트림) 부적합 — fill+signal 2스트림 + 주기 status. asyncio 동시 태스크 데몬.

### 4.2 소비 / 발행 매핑
| 소비 | → | 발행 (TradingStatePublisher, suffix 제어) |
|------|---|------|
| `order.fill.stock.shadow` entry fill | → | `publish_raw_position(code, dict)` + `_open[code]` 등록 + (Telegram 정책 평가) |
| `order.fill.stock.shadow` exit fill | → | 페어링 → `publish_raw_trade(dict)` + `remove_position(code)` + (Telegram 정책 평가) |
| `signal.final.stock.shadow` | → | `publish_raw_signal(dict)` + `_signal_meta[signal_id]` 캐시 |
| 주기(N초) status 태스크 | → | `publish_status(dict)` heartbeat + positions **mark-to-market** 재발행 |
| `market:ticks` (StreamConsumerFeed, read-only) | — | MTM용 현재가 |
| `stock:daemon:positions` (read, opened_at_ms 가드) | — | 재시작 open-entry 복구 |

### 4.3 데몬 태스크
1. **consumer**: XREADGROUP(group `stock_monitor`, fill+signal 두 스트림 1콜) → stream key 라우팅 → handle_fill / handle_signal → XACK.
2. **status**: `STOCK_MONITOR_STATUS_INTERVAL`초마다 status heartbeat + `_open` MTM 재발행(feed 가격).
3. feed.start/stop 수명주기, SIGTERM/SIGINT graceful.

## 5. Stateful 집계

### 5.1 상태
- `_open: dict[code, OpenEntry]` (entry_price, quantity, entry_time, signal_id, strategy, name, side)
- `_signal_meta: dict[signal_id, {strategy, name, code, direction, confidence}]` (bounded, cap `STOCK_MONITOR_SIGNAL_META_MAX`)
- `_digest: SessionDigest` (trades, realized_pnl_sum, wins — 일일 다이제스트용, 09:00 KST 리셋)

### 5.2 상관 + 페어링
```
final signal:  _signal_meta[signal_id] = {strategy, name, code, direction, confidence}
               publish_raw_signal({... signal_type=direction, executed=True ...})

ENTRY fill:    meta = _signal_meta.get(signal_id, {})         # 미스→빈값(graceful)
               publish_raw_position(code, build_position(fill, meta))
               _open[code] = OpenEntry(entry_price=filled_price, qty, entry_time, signal_id, meta)

EXIT fill:     entry = _open.pop(code) or _recover_open(code)  # hash fallback
               if entry is None: WARN + remove_position(code); return   # 엉터리 pnl 안 냄
               pnl = (exit_filled-entry.entry_price)*qty - (entry.entry_price+exit_filled)*qty*(fee_rate/2)
               publish_raw_trade(build_trade(entry, exit_fill, pnl))
               remove_position(code)
               _digest.add(pnl)
```

### 5.3 pnl 정합
`fee_rate`를 **M4-X와 동일** `config/stock_exit.yaml::stock_exit.fee_rate`에서 읽어 대시보드 trade pnl ↔ RuntimeRiskState pnl 일치.

### 5.4 재시작 복구
startup 시 `STOCK_POSITIONS_KEY`(데몬 working store) 읽어 `opened_at_ms` 가드 통과 레코드로 `_open` 재구성 + positions 스냅샷 재발행 → M5a 시작 전 open 포지션도 페어링·표시.

### 5.5 mark-to-market
status 태스크가 `_open[code]`별 feed 현재가로 current_price/unrealized_pnl 갱신해 `publish_raw_position(code, …)` 재발행 → orchestrator 패리티(미실현 PnL 표시).

### 5.6 알려진 스키마 갭 (명시)
- exit fill에 **exit_reason 없음** → trade `exit_reason="exit"`(또는 빈값). M4-X fill 확장은 follow-up.
- `_signal_meta` 미스(M5a가 시그널 후 시작) → strategy/name 빈 문자열(대시보드 graceful degrade).

## 6. Shadow 격리 & 컷오버 훅

### 6.1 플래그
`STOCK_MONITOR_DAEMON` = `off`(기본, inert) | `shadow` | `live`(M5d 예약).

### 6.2 출력 격리 (fail-safe)
- **shadow**: 엔트리포인트가 `TRADING_STATE_KEY_SUFFIX` 비어 있으면 `"shadow"`로 강제(fail-safe) → `:shadow` 키. orchestrator live 키 무충돌·clobber 방지.
- **live (M5d)**: suffix 비움 → live 키. base systemd unit의 shadow suffix가 남아 있어도 entrypoint가 비움. orchestrator stock off라 단독.

### 6.3 입력 스트림 (mode별)
- shadow: `order.fill.stock.shadow` + `signal.final.stock.shadow`
- live: `order.fill.stock` + `signal.final.stock`
- env 오버라이드 `STOCK_FILL_STREAM`/`STOCK_FINAL_STREAM`.

### 6.4 working store 읽기
`STOCK_POSITIONS_KEY`(기본 `stock:daemon:positions`) + `opened_at_ms` 가드. dashboard-native `trading:stock:positions[:shadow]`는 `TradingStatePublisher`가 쓰는 별도 key.

### 6.5 컷오버 훅
M5a v1 = off/shadow 구현 + live 모드 **배선만**(스트림 매핑·suffix·telegram 게이트). 실제 flip·runbook·롤백은 **M5d 별도 spec**.

## 7. Telegram — 중요 정보만 (선별 정책)

**핵심 원칙: per-fill 알림 금지** (멀티종목 paper에서 매 체결 알림은 노이즈). M5a는 **신호 대 잡음**을 위해 다음 3종만 발신한다. 이 정책은 **live 실발송과 shadow would-alert 로그 양쪽에 동일 적용** — shadow 로그도 per-fill로 도배하지 않는다.

| 종류 | 트리거 | 빈도 |
|------|--------|------|
| **① 주목 청산 (notable exit)** | 청산 pnl% 절댓값 ≥ `telegram.pnl_alert_pct`(기본 3.0%) — 큰 이익/손실만 | 드묾 |
| **② 헬스 이상 (health anomaly)** | 장중(09:00–15:30 KST)에 `telegram.health_stale_seconds`(기본 600s) 동안 fill 처리 0 + feed staleness 초과 / poison-pill 급증 | 이벤트성, dedup(쿨다운 `telegram.health_cooldown_seconds` 기본 1800s) |
| **③ 세션 다이제스트 (digest)** | `telegram.digest_time_kst`(기본 15:40) 1회/일 — 거래수·실현 PnL 합·승률·미청산수 | 1/일 |

- **진입 fill = 무알림**(routine). 소액 청산(임계 미만) = 무알림(다이제스트에만 집계).
- **mode 게이트**: `live`=실제 `notifier_for_domain("stock")` 전송; `shadow`=전송 안 함, 대신 `logger.info("would-alert: …")` (단 위 3종에만 — per-fill 로그 없음).
- 임계/시각/쿨다운은 `config/stock_monitor.yaml::telegram` 설정(하드코딩 금지).

## 8. 플래그 · systemd · config

### 8.1 env
`STOCK_MONITOR_DAEMON`(off) · `STOCK_FILL_STREAM`/`STOCK_FINAL_STREAM`(mode별) · `STOCK_POSITIONS_KEY`(`stock:daemon:positions`) · `TRADING_STATE_KEY_SUFFIX`(shadow=auto `shadow`) · `STOCK_TICK_STREAM`(`market:ticks`) · `STOCK_MONITOR_STATUS_INTERVAL`(`5`) · `STOCK_MONITOR_SIGNAL_META_MAX`(`1000`).

### 8.2 config (신규 — Telegram 정책 + fee 참조)
`config/stock_monitor.yaml`:
```yaml
stock_monitor:
  telegram:
    pnl_alert_pct: 3.0            # 청산 |pnl%| ≥ 3% 만 알림
    health_stale_seconds: 600    # 장중 600s 무활동 → 헬스 이상
    health_cooldown_seconds: 1800
    digest_time_kst: "15:40"     # 일 1회 세션 다이제스트
```
`fee_rate`는 `config/stock_exit.yaml::stock_exit.fee_rate` 재사용(M4-X 정합).

### 8.3 systemd
`deploy/systemd/kis-stock-monitor-daemon.service` **disabled**, `Environment=STOCK_MONITOR_DAEMON=shadow` + `Environment=TRADING_STATE_KEY_SUFFIX=shadow`(명시), ExecStart `-m services.stock_monitor.main`.

### 8.4 DRY 재사용
`TradingStatePublisher`(raw-dict) · `StreamConsumerFeed` · `notifier_for_domain` · `ConfigLoader` · 엔트리포인트 패턴. 신규는 집계/페어링/telegram 정책뿐.

## 9. Error handling
| 상황 | 정책 |
|------|------|
| fill/signal 파싱 실패 | poison-pill → XACK drop + log |
| publish 실패 | TradingStatePublisher fire-and-forget(영향 없음) |
| Telegram 전송 실패(live) | log, continue(best-effort) |
| 청산 fill인데 open-entry 없음 + hash fallback 실패 | trade skip + WARN, positions remove |
| 재시작 복구 read 실패 | log, 빈 `_open` 시작 |
| consumer 루프 예외 | per-message catch+log; 루프 지속 |
| SIGTERM/SIGINT | 태스크 cancel → feed.stop + redis close |

**멱등성(한계)**: consumer group at-least-once → 크래시 직전 미-XACK 청산 fill 재전달 시 trades LIST 중복 1건 가능(positions는 code-keyed 멱등). 관측 대시보드라 수용; order_id dedup은 follow-up.

## 10. Testing
- **단위**: build_position/build_trade/build_signal dict · entry↔exit 페어링(pnl=(exit−entry)×qty−round-trip fee) · exit-without-entry→skip+WARN · signal_meta 보강/미스 graceful · 재시작 복구(opened_at_ms 가드) · MTM 갱신 · **Telegram 정책**(per-fill 무알림 / notable exit≥임계 알림 / 진입 무알림 / shadow=would-alert 로그·live=notifier mock 호출 / health·digest) · shadow 격리(suffix→`:shadow` 키, TradingStateReader read-back) · 플래그 off=inert · `_signal_meta` cap.
- **통합(핵심)**: entry fill+final signal 주입 → `trading:stock:positions:shadow`(strategy/name 보강)+`signals:shadow` → exit fill 주입 → `trades:shadow`(pnl 정합)+positions remove. **TradingStateReader(suffix=shadow) read-back**으로 대시보드 가시성 증명.
- **회귀**: 대시보드/`TradingStatePublisher`/M4 데몬 무변경 → 기존 테스트 green. full gate.

## 11. Acceptance criteria
- [ ] StockMonitorDaemon이 fill+signal 스트림(consumer group) 소비 → `TradingStatePublisher`로 `:shadow` 키 발행.
- [ ] entry fill→포지션(strategy/name 상관), exit fill→페어링 trade(pnl 정합)+remove, final→signals, 주기 status+MTM.
- [ ] **Telegram 중요-정보만**: 진입 무알림, 임계 초과 청산·헬스 이상·세션 다이제스트만. shadow=would-alert 로그(3종 한정)·live=실발송(mode 게이트).
- [ ] 재시작 복구(positions hash + opened_at_ms 가드).
- [ ] **shadow 격리(fail-safe suffix)로 live `trading:stock:*` clobber 안 함**.
- [ ] default-off, systemd disabled, 대시보드/publisher/M4 데몬 무변경, ClickHouse-free.
- [ ] pnl fee_rate를 M4-X와 동일 소스(stock_exit.yaml)에서.

### 운영 검증 (머지 후, M5d 선행)
M4-P/R/O/X shadow + M5a shadow 동시 활성화 → `trading:stock:*:shadow` vs orchestrator live `trading:stock:*` side-by-side 비교 → 동등 확인 → M5d 디리스킹.

## 12. Open questions (구현 계획에서 확정)
- status 스냅샷 정확한 필드(대시보드 status 페이지 기대치).
- signal `executed` 의미(final=will-execute=True vs fill 상관) — v1은 True.
- 세션 다이제스트 메시지 포맷·다이제스트 카운터 일일 리셋 트리거(09:00 KST cron vs 데몬 내부 타이머; M5c 리셋과 무관한 표시용).
- trades order_id dedup 지금 vs 연기.
