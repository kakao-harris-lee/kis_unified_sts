# Setup D 디커플 체인 이식 — 로스터 설정 주도화 · VWAP 공급 · 평가 관측성

작성 2026-09-08 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `aa348ce1`(#654–#658 반영 후 재검증; 초안은 `a8e2d4f0`) · 상태 **초안(운영자 검토 대기, 구현 미착수)**

배경: F-9 Gate 1 섀도 1일차(2026-09-08)에서 디커플 체인은 09:15~15:35 A01609 틱을 정상 소비했지만
`signal.candidate.futures.shadow` 는 0건이었고, 같은 날 `trader-futures` 의 체결 20건은 전부
`setup_d_vwap_reversion` 신호였다(Setup A 종일 `outside_time_window`, C 무발화). 디커플 체인이 paper 가
실제로 거래하는 전략을 보지 못하므로 Gate 1 방향 일치 검증과 Gate 1b `slippage_gate` 실측이 A/C 발화일에만
성립한다. 이 문서는 그 갭을 닫는 최소 변경을 정의하고, 조사 중 드러난 **디커플 A/C 의 설정 드리프트**(§0-2)를
같은 변경으로 함께 닫는다.

## 0. 측정 (main `a8e2d4f0`)

### 0-1. 이식할 "코어"는 이미 있다

| 항목 | 위치 | 상태 |
|---|---|---|
| 결정 코어 | `shared/decision/setups/vwap_reversion.py` `SetupDVWAPReversion(Setup)` 650줄 · `SetupDConfig(ServiceConfigBase)` 26필드 · 내부 상태 `_atr_window(780)`/`_close_window(15)`/`_vwap_window(30)` deque + `last_reject_reason` + `last_signal_details` | 존재 · 테스트 `tests/unit/decision/test_setup_d_vwap_reversion.py`(505줄, 25건) + `test_setup_d_trend_filter.py`(11건) |
| 모놀리식 어댑터 | `shared/strategy/entry/setup_d_adapter.py` 239줄 — 코어 `check(mc)` 를 감싸고 방향 차단·regime gate·`publish_setup_eval` 을 얹음. A/C 어댑터와 동일 패턴 | paper 활성 (`config/strategies/futures/setup_d_vwap_reversion.yaml` `enabled: true`, 2026-06-26~) |
| 컨텍스트 계약 | `shared/decision/context.py` `build_market_context(...)` — 모놀리식 `setup_context_builder.py` 와 디커플 `context_provider.py` 가 공용. `interfaces.py` `FuturesMarketView` docstring 이 이미 "A/C/**D** 가 소비" 라고 명시 | 존재 · 파리티 계약 `tests/unit/decision/test_market_context_parity.py` `_SETUP_READ_FIELDS` 에 `vwap` = Setup D 소비 필드 등재 |
| 하류 계약 | `Signal(stop_loss, take_profit, valid_until, …)` — D 코어는 항상 stop/target 을 채움(`vwap_reversion.py:611-628`). risk_filter 는 둘 다 필수 파싱(`services/risk_filter/main.py:143-144`), PseudoOCO 가 bracket 등록 | 추가 배관 불필요 |
| 디커플 데몬 | `services/decision_engine/main.py:707` `setups = [SetupAGapReversion(), SetupCEventReaction()]` | **Setup D 미등록** |

### 0-2. 디커플 A/C 는 지금 어떤 파라미터로 도는가 — 세 소스가 전부 다르다

`Setup.__init__(config=None)` 은 `CONFIG_CLASS()` 를 **pydantic 기본값**으로 만든다(`shared/decision/setup_base.py:34-43`,
"no YAML load is required for unit-test usage"). 데몬은 인자 없이 생성하므로(`main.py:707`) `config/decision_engine.yaml` 의
`setup_a/c/d_*` 섹션은 **아무도 읽지 않는 죽은 설정**이고, 모놀리식은 `Setup{A,C,D}EntryConfig` 로
`config/strategies/futures/<name>.yaml::strategy.entry.params` 를 읽는다. 2026-09-08 실측(코어 `model_fields` 교집합만):

| 파라미터 | 디커플 실제(pydantic 기본) | `decision_engine.yaml`(죽음) | `strategies/futures/*.yaml`(모놀리식 paper) |
|---|---|---|---|
| A `valid_minutes_max` | 120 | 90 | **60** |
| A `min_sp500_gap_pct` / `min_kr_gap_pct` | 0.3 / 0.2 | 0.5 / 0.3 | 0.3 / 0.3 |
| A `retrace_min`–`max` | 0.2–0.7 | 0.3–0.55 | 0.3–0.55 |
| A `stop_atr_mult` | 1.5 | 1.5 | **3.5** |
| C `window_minutes` | 15 | 720 | **15** |
| C `no_entry_after_minutes_since_open` / `stop_buffer_atr_mult` | 기본 | 미기재 | 375 / 0.5 |
| D `reversal_confirm_enabled` | **False** | True | True |
| D `no_entry_after_minutes_since_open` | 360 | 360 | **345** |
| D `stall_buffer_atr_mult` | 1.0 | 1.0 | **1.5** |
| D `min_confidence` | 0.0(게이트 off) | 미기재 | **0.6** |
| D trend_filter 4키 | 기본(off) | 미기재 | 명시(off) |

함의: (a) 오늘까지의 섀도 A/C 는 paper 가 검증한 운영점이 아니다 — Gate 1 "방향 일치" 는 이 상태로는 해석 불가.
(b) CLAUDE.md 비협상 "임계값은 YAML" 이 디커플 데몬에선 실질적으로 깨져 있었다. (c) 소스를 하나로 정해야 한다(§3-A).
`ServiceConfigBase.from_yaml(path=, section=)` 는 점 경로 섹션과 `extra="ignore"` (`shared/config/base.py:90-92, 105-125`)를
지원하므로 코어 config 가 strategies YAML 의 `strategy.entry.params` 를 **직접** 읽을 수 있다(어댑터 전용 키
`long/short_blocked_regimes`, `regime_gate`, `llm_tuning` 등은 무시됨).

### 0-3. 나머지 갭

3. **VWAP** — `services/decision_engine/context_provider.py:84-96` 은 `vwap=` 을 넘기지 않아 `build_market_context` 폴백
   `vwap := current_price` → `z = (price − vwap)/atr = 0` → Setup D 조용히 inert. 코드가 이를 **F-9 PRECONDITION** 으로
   명시(`shared/decision/context.py` docstring: "provider must source a real session VWAP (engine `get_indicators()['vwap']`);
   only THEN make `vwap` required"). 의도된 tripwire 테스트가 있다: `tests/unit/decision/test_market_context_parity.py:573-618`
   ("FuturesContextProvider now threads vwap … make build_market_context's vwap REQUIRED … then update this pin"),
   `tests/unit/decision_engine/test_context_provider.py:97`, `tests/unit/decision/test_build_market_context.py`. 엔진은 세션
   VWAP 을 이미 계산한다(`shared/indicators/streaming/queries.py:157`, `VWAPCalculator` KST 일자 리셋 — 선물 첫 틱 08:45 앵커).
4. **방향 차단** — 어댑터만 `short_blocked_regimes: ["BULL_STRONG"]` 적용(`setup_d_adapter.py:174-199`, YAML:118-120 — #658 이
   머리말 주석을 정정해 4줄 밀림; `strategy.enabled: true` 는 불변).
   `regime_gate.enabled: false`, `trend_filter_enabled: false` 라 실제 활성 게이트는 이것 하나. 디커플 A/C 도 어댑터 계층
   게이트(LLM veto/tuning, regime gate, daily-bias) 없이 돌며 디커플의 진입 게이트는 `market_risk_gate` 하나다.
5. **관측성** — 데몬은 `signal is None` 을 로그 없이 버린다(`main.py:169-170`, 오늘 evaluation 로그 0줄). `last_reject_reason`
   은 모놀리식 어댑터만 읽어 `shared/strategy/entry/setup_eval_publisher.publish_setup_eval` 로 Redis
   `trading:futures:setup_eval` + 일별 history(7일 TTL)에 쓰고, `scripts/ops/setup_d_paper_observe.py` 가 소비한다.
   디커플에선 "0 신호 = 미평가" 와 "0 신호 = 전건 거부" 를 구별할 수 없다.
6. **청산 의미론** — 모놀리식 D 청산은 `setup_target_exit`(stop/target + **EOD 15:15**). 디커플 PseudoOCO 는
   `register_bracket` 이 `signal.valid_until` 을 받아 `check_expiry` 가 그 시각에 **포지션을 강제 청산**(`shared/execution/
   pseudo_oco.py:96-125, 167-198`, 호출 `order_router/main.py:292`). D 의 `signal_ttl_minutes: 10` 은 코어에선 진입 유효기간인데
   디커플에선 10분 보유 상한이 된다. A(10분)/C(30분)도 같은 구조. 오늘 orchestrator D 왕복 10건 중 다수가 10분 초과
   (12:14→12:27, 13:55→14:05 등) → 방향은 맞아도 손익 궤적은 구조적으로 다르다. EOD flatten 은 디커플에 없다.
7. **재진입 가드 부재** — `services/trading/reentry_guard.py` 는 orchestrator 전용. D 는 세션 내내 발화하며 2026-07-07
   churn(연속 매수 13·손절 11)의 당사자였다. 디커플엔 전략별 post-exit 쿨다운이 없다(`ConsecutiveLossFilter` 는 별개).
8. **상태 창의 연속성** — 데몬은 `ctx is None` 이면 setup 을 호출하지 않고(`main.py:155-158`) 재시작 시 deque 가 비워진다.
   60초 주기에서 `vol_window_bars 780` 워밍업 ≈ 13시간 가동 ≈ 2세션. 워밍업 중엔 vol 게이트가 관대(설계).
9. **이름 공간** — 디커플 `Signal.setup_type` 은 `"D_vwap_reversion"`, 모놀리식 레지스트리/ops 스크립트/증거 번들은
   `"setup_d_vwap_reversion"`. Telegram 승인 게이트(`config/telegram_bot.yaml::approval_gate.gated_strategies`)는 setup_type 키.

### 0-4. 평가 주기

디커플 `tick_interval_seconds=60.0` (`main.py:675`). 모놀리식은 `_handle_entry` → `StrategyManager.check_entries` 가 루프
틱마다 돌며 틱 카운터가 분당 약 90 증가(2026-09-08 11:00 `[tick 16200]→[16290]`). D 코어의 세 창은 `check()` 호출 단위로
채워지므로 백테스트 리플레이(1분봉: 780 ≈ 2세션)와 모놀리식 paper(≈ 8.7분 / 10초 / 20초)는 **이미 다른 전략**이다.
디커플 60초 주기가 백테스트 의미론과 일치한다.

## 1. 목표 · 범위

- 목표: 디커플 체인이 검증된 파라미터로 Setup D 후보를 생성해 F-9 Gate 1(방향 일치)·Gate 1b(`slippage_gate: blocked`
  실측) 증거를 paper 의 실거래 전략에서 얻을 수 있게 한다.
- 범위 안: 로스터·파라미터 설정 주도화(A/C/D 공통) · 컨텍스트 VWAP 공급(tripwire 이행) · setup 단위 평가 관측성 ·
  테스트/계약 갱신 · 런북 Gate 1/1b 갱신.
- 범위 밖: D 코어 로직 변경(0) · 청산 의미론(§0-3-6) · 재진입 가드(§0-3-7) · order-router 피드 소스(DUAL-WS) · 컷오버.

## 2. 파리티 목표 (운영자 결정 ①)

권고: **백테스트 의미론(1분 = `check()` 1회)과 strategies YAML 파라미터를 정본으로 삼는다.** 검증 증거(WF OOS Sharpe
1.77/2.135, `docs/superpowers/specs/archive/2026-06-25-futures-mr-highvol-setup-d.md`)는 1분봉 리플레이에서 나왔고 디커플
60초 주기가 그것을 재현한다. 따라서 Gate 1 "방향 일치" 는 모놀리식 paper 와 발화 **시각·빈도가 같을 것을 기대하지
않는다**: 같은 극단(|z| ≥ 1.8)에서 같은 방향이 나오는지를 보고, 차이는 주기 차이로 설명한다. 대안(틱마다 평가)은 검증되지
않은 운영점의 복제라 기각. 부수 주의: Setup C 의 15분 breakout 은 모놀리식 라이브 경로에서 여전히 inert
(archive spec §7) — A/C/D 대조 시 C 의 부재를 결함으로 읽지 말 것.

## 3. 변경 (신규 모듈 0 · 코어 무변경)

### 3-A. 로스터와 파라미터를 strategies YAML 로 일원화 — `services/decision_engine/main.py`

- `_build_setups()` 헬퍼: 명시 매핑 `{"setup_a_gap_reversion": (SetupAConfig, SetupAGapReversion), "setup_c_event_reaction":
  (SetupCConfig, SetupCEventReaction), "setup_d_vwap_reversion": (SetupDConfig, SetupDVWAPReversion)}` 을 순회하며
  `config/strategies/futures/<name>.yaml` 의 `strategy.enabled` 가 참인 것만 `CoreConfig.from_yaml(path=..., section=
  "strategy.entry.params")` 로 생성. 모놀리식 `StrategyManager._load_strategies(enabled_only=True)` 와 같은 로스터 의미론
  (`FUTURES_TRADING_STRATEGY` 가 비면 enabled 전부) — 필요하면 같은 env 를 존중.
- `config/decision_engine.yaml` 의 `setup_a/c/d_*` 세 섹션은 **삭제**(죽은 설정이 드리프트의 원인). `market_risk_gate` 섹션은
  유지. `SetupXConfig._default_config_file/_default_section` 은 단위 테스트 편의 경로라 그대로 둔다.
- 기동 로그 1줄: `decision_engine setups: [setup_a_gap_reversion, setup_c_event_reaction, setup_d_vwap_reversion]
  (disabled: [])` + 각 setup 의 핵심 파라미터 요약(모놀리식 `stock roster` 로그와 같은 역할).
- 효과: D 등록과 동시에 **A/C 가 처음으로 paper 검증 파라미터로 돈다**(§0-2). 이는 섀도 A/C 의 행동 변화이며 의도된 것.
- 롤백 = 해당 strategies YAML `strategy.enabled: false` + decision-engine 재기동(모놀리식과 같은 스위치).

### 3-B. VWAP 공급 — tripwire 지시대로 이행

- `context_provider.py`: `indicators = engine.get_indicators(symbol) or {}` 한 번 읽어 `atr` 과 `vwap` 을 꺼내고
  `build_market_context(..., vwap=vwap)`. **`vwap <= 0` 이면 `None` 반환**(ATR 부재와 같은 fail-closed — z 붕괴로 조용히
  inert 되는 것보다 낫다).
- `shared/decision/context.py::build_market_context`: `vwap: float` **필수 인자로 승격**, `vwap := current_price` 폴백 제거
  (docstring 과 parity 테스트 :610-618 이 지정한 "F-9 cutover moment"). 호출자는 둘뿐이며 모놀리식 `setup_context_builder.py:52`
  는 이미 값을 넘긴다(그쪽의 `default=current_price` 폴백은 모놀리식 은퇴 트랙 소관, 이 PR 은 건드리지 않음).
- 갱신할 고정 테스트: `test_market_context_parity.py:573-618`(vwap 을 divergence 에서 라이브 공급 필드로 이동),
  `test_context_provider.py:97`(폴백 assert 를 뒤집고 `vwap<=0 → None` 추가), `test_build_market_context.py`(폴백 케이스 삭제).
  `tests/unit/strategy/test_setup_ac_field_invariance.py` 의 `_CASES` 에 **D 를 넣지 않는다**(D 는 vwap 을 읽는다).

### 3-C. 방향 차단 (운영자 결정 ②)

권고: **이식하지 않는다(A/C 관행 유지)** — 디커플의 진입 게이트는 `market_risk_gate` 로 일원화되어 있고, 어댑터 계층 게이트
부재는 D 고유가 아니라 체인 설계다. 대신 §3-D 로 "모놀리식이었다면 차단됐을 short" 를 셀 수 있게 한다. 운영자가 디커플에서도
`BULL_STRONG` short 차단을 원하면 후속 PR 로 `market_risk_gate` 의 방향 반응 행렬에 넣는 것이 자리(어댑터 재복제 아님).

### 3-D. setup 단위 평가 관측성 — 데몬 루프 + 코어 ClassVar 1줄

- 각 코어에 `REGISTRY_NAME: ClassVar[str]` 추가(`"setup_a_gap_reversion"` 등, 3줄) — 디커플 `setup_type`(`"D_vwap_reversion"`)
  과 모놀리식 레지스트리 이름의 대응을 코드 한 곳에 둔다. `_build_setups()` 의 매핑 키도 이것을 쓴다.
- 루프: `signal is None` 이면 `publish_setup_eval(setup.REGISTRY_NAME, "reject", setup.last_reject_reason or
  "setup_rejected")`, 후보를 냈으면 `"fired"`. **모놀리식과 같은 키·history 포맷 재사용** → `scripts/ops/setup_d_paper_observe.py`
  와 증거 번들이 섀도 데이터에 그대로 동작. 데몬의 기존 sync Redis 클라이언트(`market_risk_redis`) 사용.
- 로그는 기존 `ReasonLogThrottle` 로 이유별 5분 1회(`shadow_gate_log_interval_seconds` 재사용). 틱마다 INFO 금지.
- `last_signal_details`(28키)는 `Signal` 에 metadata 슬롯이 없어 스트림에 싣지 않는다 — `reason_tags` 가 이미 z/vol_ratio/target_R
  를 담는다. 필요하면 후속에서 `futures_context` trace 슬롯 재사용.

### 3-E. 문서

- `docs/runbooks/futures-pipeline-cutover-f9.md`: Gate 1 체크리스트에 "D 후보가 `signal.candidate.futures.shadow` 에 등장하고
  `trading:futures:setup_eval` 에 D reject 이유가 누적된다" 추가 · "Mode knobs" 에 로스터/파라미터 소스가 `config/strategies/
  futures/*.yaml` 임을 명시 · Gate 1b 인벤토리에 **의도적 이탈 후보 2행 추가**: (i) 청산 의미론(TTL 강제청산·EOD 부재, §0-3-6),
  (ii) 재진입 쿨다운 부재(§0-3-7) — 운영자 ACCEPT 또는 후속.
- `config/telegram_bot.yaml` 주석의 setup_type 예시에 `"D_vwap_reversion"` 추가(기본 `enabled: false` 라 동작 변화 없음).

## 4. 검토한 대안 (기각 사유)

- D 코어를 디커플용으로 복제 — 코어가 이미 공용. DRY 위반이자 드리프트 원천.
- `decision_engine.yaml` 을 strategies 값으로 동기화하고 그것을 읽음 — 두 파일 동기 유지가 이미 한 번 실패했다(§0-2). 한 파일.
- 데몬이 `Setup{X}EntryConfig`(어댑터 config)를 거쳐 코어 config 로 변환 — 어댑터 계층 의존이 디커플에 생기고 필드 복사
  블록(어댑터 `__init__`)이 4곳이 됨. `from_yaml(section="strategy.entry.params")` + `extra="ignore"` 로 충분.
- `build_market_context` 의 vwap 을 optional 로 유지하고 provider 만 고침 — tripwire 테스트가 명시적으로 required 승격을
  지시하며 호출자가 둘뿐이라 비용이 작다.
- 모놀리식 주기(틱마다)로 데몬 주기 단축 — 검증되지 않은 운영점 복제(§2).
- 방향 차단을 데몬에 어댑터처럼 이식 — 게이트 계층 이중화(§3-C).
- 상태 창을 Redis 에 영속 — 워밍업 permissive 는 설계된 동작이고 백테스트도 매 실행 콜드 스타트. 필요성이 관측되면 후속.

## 5. 검증

단위(hermetic):
- `tests/unit/services/test_decision_engine_main.py`: `_build_setups()` 가 strategies YAML `enabled` 를 존중(D on/off, A off),
  파라미터가 YAML 값으로 로드됨(예: D `min_confidence == 0.6`, A `stop_atr_mult == 3.5`), 기동 로그 문자열.
- 드리프트 가드: 세 코어 config 의 `model_fields` ⊆ 해당 strategies YAML `strategy.entry.params` 키 합집합 ∪ 기본값 허용 목록 —
  코어에 필드가 추가되면 YAML 에도 있어야 함을 강제(§0-2 재발 방지).
- `test_context_provider.py`: vwap 실값 전달 · `vwap<=0 → None`. `test_market_context_parity.py`·`test_build_market_context.py`
  pin 갱신(§3-B). `test_setup_ac_field_invariance.py` 무변경(D 미포함).
- `tests/unit/decision_engine/test_candidate_contract.py`: D `Signal → to_stream_dict → risk_filter._signal_from_stream_fields`
  왕복(기존 A 케이스 템플릿).
- 데몬 루프: reject/fired 시 `publish_setup_eval` 인자, 스로틀. 코어 테스트 36건 무변경 통과(코어 미변경 증거).

섀도 증거(paper 서버, 운영자 실행):
- 재기동 후 첫 세션: `XLEN signal.candidate.futures.shadow > 0` 인 날이 나오고 `HGETALL trading:futures:setup_eval` 에
  `setup_d_vwap_reversion` 행이 있어야 한다. 둘 다 0 이면 §3-B 실패(vwap 미공급) — 기동 setups 로그와 provider `None` 카운트로
  구별.
- 방향 일치: 같은 KST 분의 모놀리식 `[setup_d_vwap_reversion] signal fired: {dir}` 와 섀도 후보 `direction` 대조. 불일치는
  주기 차이(§2)로 설명 가능한지 `reason_tags` 의 z 로 확인.
- `slippage_gate: blocked` 실측은 **order-router 가 켜져 있어야** 가능 — DUAL-WS 해소 전에는 이 항목이 0 으로 남는다.

## 6. 롤아웃 · 롤백

1. PR(코드 3파일 `main.py`/`context_provider.py`/`context.py` + 코어 ClassVar 3줄 + 설정 1파일 + 테스트 + 런북) → Claude 측
   코드 리뷰 → CI green → 머지.
2. paper: `docker compose --env-file .env.paper --profile futures-pipeline build futures-decision-engine` 후 decision-engine 만
   재기동(다른 소비자 무접촉). 기동 로그에서 setups 3개와 파라미터 요약 확인.
3. 롤백: `config/strategies/futures/setup_d_vwap_reversion.yaml` `enabled: false` + 재기동. 단 이 스위치는 모놀리식 로스터와
   공유되므로 **paper orchestrator 의 D 도 함께 꺼진다** — 디커플만 끄려면 `FUTURES_TRADING_STRATEGY` 류의 데몬 전용
   부분집합 env 를 §3-A 에서 함께 두는 것을 권고(운영자 결정 ④: 공유 스위치 vs 데몬 전용 부분집합).

## 7. 수용 기준

- [ ] decision_engine 기동 로그에 로스터(enabled 부분집합)와 파라미터 요약이 찍히고, 값이 strategies YAML 과 일치한다.
- [ ] `ctx.vwap` 이 라이브 provider 경로에서 실값임을 테스트가 증명하고 `build_market_context` 에 vwap 폴백이 없다.
- [ ] 섀도 세션에서 `trading:futures:setup_eval` 에 D reject/fired 이력이 누적된다(0 신호 ≠ 미평가).
- [ ] `config/decision_engine.yaml` 에 setup 파라미터 섹션이 남아 있지 않다(죽은 설정 0).
- [ ] 코어 테스트 무변경 통과 · `tests/unit` 2-pass green · ruff/black clean · tos-firewall PASS(`shared/decision` 은 tos 경계 밖).
- [ ] 런북 Gate 1 항목·Gate 1b 이탈 후보 2행 갱신.
- [ ] 운영자 결정 ①~④ 가 이 문서에 기록됨.

## 8. 범위 밖 (정직 기록)

- **청산 의미론(§0-3-6)**: TTL 강제 청산·EOD flatten 부재는 A/C/D 공통. Gate 1b 이탈 후보로만 등재.
- **재진입 쿨다운(§0-3-7)**: 디커플 대응물 없음. Gate 1b 이탈 후보로만 등재. D 가 켜지면 churn 재현 가능성을 섀도에서 관측.
- **DUAL-WS**: order-router 자체 WS 는 trader-futures 와 같은 계정을 경합(2026-09-08 실측). D 후보가 나와도 order-router 가
  꺼져 있으면 `slippage_gate` 실측은 0. 피드 소스 변경(raw_data 소비) 또는 정지 창 운용은 별도 결정.
- **모놀리식 D 의 틱 단위 평가(§0-4)**: paper 가 검증 운영점과 다른 창 길이로 돌고 있다는 관찰. 모놀리식은 은퇴 트랙이라 고치지
  않는다. 디커플이 정본 주기를 갖는다는 것이 이 계획의 입장.
- **전략별 포지션 상한**: 단일 심볼 배치에서 vacuous(런북 disposition 2026-09-07). D `max_positions: 1` 은 per-symbol 가드로 충족.
- **Setup C 라이브 breakout inert**(archive spec §7): 별개 결함, 미해결.

## 9. 운영자 결정 목록

| # | 결정 | 권고 |
|---|---|---|
| ① | 파리티 정본: 백테스트(1분/strategies YAML) vs 모놀리식 paper(틱) | 백테스트 |
| ② | `BULL_STRONG` short 차단을 디커플에 이식할지 | 이식 안 함, 관측으로 대체 |
| ③ | 디커플 A/C 가 §3-A 로 strategies 파라미터로 바뀌는 것(섀도 행동 변화) 수용 | 수용 — 지금 상태가 결함 |
| ④ | D 스위치를 모놀리식과 공유(`strategy.enabled`) vs 데몬 전용 부분집합 env 추가 | 공유 + 데몬 전용 부분집합 env(둘 다) |
