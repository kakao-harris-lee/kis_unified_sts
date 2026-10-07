# CP-3 착수 — 첫 paper tenant 후보 비교와 운영자 결정표 (2026-10-07)

상태: **조사 완료 · 운영자 결정 대기 · 코드 0 줄**. 상위 계획은
[Control Plane 및 첫 tenant 계획](2026-10-06-tos-control-plane-and-first-tenant-plan.md) §3 CP-3 이고,
그 계획이 「전략 선택은 미정 · 후보 비교표 필요」로 남긴 자리를 이 문서가 채운다.
이 문서는 실행·배포·live 승인 문서가 아니다. 실전 선물 주문·증거금 투입은 영구 정책 차단이다.

조사는 세 갈래를 읽기 전용으로 돌렸다 — 레거시 전략 재고, TOS DSL 표현력, 데이터·재생 경로.
아래 모든 행은 저장소의 파일·행을 가리키며, 요약은 가리키는 자리의 대체물이 아니다.

## 0. 한 줄 결론

후보는 **Setup D VWAP 되돌림** 하나로 좁혀진다(§1). 그러나 TOS 커널은 **「공개된 정수 스칼라를
비교해 한 (account, instrument)·한 방향에 ACTION/FLAT/NO_ACTION 을 내는 것」**만 할 수 있어(§2),
Setup D 의 지표 수학·세션 창·스톨 가드·스톱/타깃은 전부 **상류 Critical Input 생산자**로 간다.
동일 입력 비교는 clock-free `tos.backtest` 하네스로만 가능하고, 그 앞에 **새 구축물 넷**이 필요하다(§3).
그래서 CP-3 의 1차 슬라이스는 「전략을 DSL 로 옮기는 일」이 아니라 **「공유 지표 생산자 + 결정 수준
비교 하네스」**다(§5). 운영자 결정 일곱이 §4 에 있다.

## 1. 후보 비교표

CP-3 계획의 네 기준(레거시 의존도 · DSL 표현 가능성 · 데이터 가용성 · long/short 검증 가능성)으로
현재 `enabled: true` 인 여섯을 비교했다. 2026-02-26 재설계 뒤 꺼진 셋(`bb_reversion` ·
`opening_volume_surge` · `volume_accumulation`)과 NO-SHIP 판정 계열(추세 추종·ORB·CTA·고확신 홀드,
`docs/plans/2026-07-06-futures-strategy-improvement-roadmap.md` 8·44행)은 재논의하지 않는다.

| 후보 | 레거시 의존 | DSL 표현(§2 기준) | 데이터 | L/S 대칭 | 검증 근거 | 판정 |
|---|---|---|---|---|---|---|
| **Setup D VWAP 되돌림** `config/strategies/futures/setup_d_vwap_reversion.yaml` | **없음** — `atr`·`vwap` 둘뿐(`shared/strategy/entry/setup_d_adapter.py` 154–156행). 매크로·이벤트·LLM·스크리너·Redis 상태 없음. `regime_gate`·`trend_filter` 둘 다 off. 유일한 연결은 `short_blocked_regimes:[BULL_STRONG]`(133행) 한 줄 | **부분** — 밴드 트리거는 상류 정수 필드 비교로 가능(출하된 `lower_band` 와 같은 꼴). 세션 창·ATR 백분위 게이트·스톨 가드·역전 확인·스톱/타깃은 상류로 | 검증 창 = `101S6000` 2025-12-01~04-30(연속물). paper 종목 `A05610` 분봉은 2026-05-01~10-07 101일 **있으나 신뢰 범위 문서 없음** | **정확한 거울** — 방향 = VWAP 괴리 부호(`vwap_reversion.py` 79–80행) | OOS Sharpe **+2.135**, 135 거래, 4/4 폴드, L +130.5 / S +45.2 pt(`docs/analysis/2026-07-06-futures-strategy-backtest-reexamination.md` 37행). 09-08 섀도 20 체결 전부 이 전략 | **1순위** |
| Setup A 갭 되돌림 | **강함** — `stream:macro.overnight` 필수(24 h 신선도), RegimeGate on, LLM veto | 부분(같은 한계) + 매크로를 Critical Input 으로 올려야 함 | 같음 | 갭 방향 거울이나 `long_blocked_regimes` 비대칭 | Sharpe 5.12 **N=14**, CLI 백테스트 0 거래(하네스가 매크로 미주입) | 2순위 — 하루 50 분 창 |
| Setup C 이벤트 반응 | **강함** — 손으로 쓰는 월별 이벤트 파일, 장중 발화 가능 이벤트 3종 | 부분 | 같음 | 거울이나 같은 비대칭 | **2026-06-25 이후 신호 0**, N=7, 다음 장중 이벤트 10-22 | 보류 |
| momentum_breakout(주식) | 스크리너 유니버스·Redis 일봉 지표·regime gate | 부분 + 오프닝 레인지 상류 | 주식 분봉 종목별 들쭉날쭉 | **long-only** | 재튜닝 Sharpe ≈ −5.24(`ROADMAP.md` 311행) | 탈락 |
| williams_r(주식) | 같은 유니버스·시장상태 | 부분 — 교차(이전 봉) 불가 | 같음 | **`allow_short:false`** | OOS 기록 없음 | 탈락 |
| pattern_pullback(주식) | 일봉 ≥200 · 유니버스 · 25M/10M 설정 충돌 | 부분 | 일봉 2023~ 있음 | **long-only** | in-sample 만 | 탈락 |

주식 셋은 전부 long-only 라 계획의 네 번째 기준을 통과하지 못하고, 스크리너·일봉 Redis 를 끌고 온다.
선물 셋 중 Setup D 만 자족적이다. **Setup D 의 알려진 결함**은 그대로 상속한다 — 2026-07-07 하루 13 연속
역추세 롱(−8.4 pt, `docs/superpowers/specs/2026-07-07-setup-d-trend-filter-design.md` 11–22행),
추세 필터는 구현됐으나 수용 기준 미달로 off. 워밍업 상태(780·15·30 봉 deque, `vwap_reversion.py`
339–358행)는 메모리에만 있어 **콜드 스타트 뒤 약 2 시간은 느슨한 전략**이 돈다 — 재시작/리플레이
증거를 요구하는 CP-3 에서 가장 큰 설계 질문이다.

## 2. DSL 이 오늘 할 수 있는 것 — 그래서 무엇이 상류로 가는가

`tos/src/tos/dsl/vocabulary.py` 기준(57–83행 노드 10종, 119–127행 연산자 EQ/NE/LT/LE/GT/GE):

- 산술·집계·함수·루프 없음(스파이크 메모 G1). OR/NOT 없음 — 분리 규칙·연산자 반전으로(G2).
- 봉 히스토리 없음 — 현재 캡슐의 평면 스칼라만(G3, 330–354행). 시계·세션 시각 없음 —
  `session_and_tradability` 슬롯은 런타임 빌더가 채우지 않아 UNKNOWN(`marketfeed/capsule.py` 109–115행).
- **지표 프리미티브 0** — VWAP·ATR·RSI 무엇도 커널이 계산하지 않는다. 모든 값은
  `critical_input_policy.yaml` 에 선언된 **정수**(minor 단위) 필드로 상류에서 들어온다(float 거부:
  `marketfeed/value.py` 325–359행). 오늘 paper 가 공개하는 필드는 `close`·`lower_band`·`upper_band` 셋뿐.
- Proposal 에 **숫자 필드 없음**(G5) — 수량·가격·스톱·타깃 없음. 수량은 OCP 의 정적 SizingBound
  (`order_construction_policy.yaml` 160–178행, 현재 1 계약 고정). 부분 청산 없음.
- **방향은 구성(composition)당 하나** — 런타임이 아직 `Proposal.direction` 을 읽지 않는다
  (`compose/_envelope_wiring.py` 150–190행). 대칭 전략 파일은 파싱되지만 한 구성으로 배포 불가.
- 예산 `dsl_evaluation_budget_steps=64`(`config/tos_runtime/paper/engine.yaml` 26행) ≈ 비교 21개.

따라서 Setup D 를 TOS 에 올리면 **tenant 콘텐츠는 얇은 정책**이 된다 — 상류가 매 봉마다
`z_x1000`(또는 `below_lower`·`above_upper` 플래그) · `hi_vol`(ATR 백분위) · `stall_ok` · `reversal_ok` ·
`entry_window`(09:00~컷오프) · `vwap_reverted` · `eod` 같은 정수 플래그를 공개하고, DSL 은 그 플래그의
AND 로 ACTION/FLAT 을 낸다. **지표 수학의 정본은 상류 생산자**이며, 그 생산자를 레거시 지표 엔진과
**같은 코드**로 두지 않으면 비교는 정책이 아니라 밴드 산식을 재게 된다(§3). 이것이 CP-3 의 설계
중심이고, 「전략을 DSL 로 다시 쓴다」는 계획 문장은 이 사실 위에서 읽어야 한다.

## 3. 동일 입력 비교 — 가능한 경로 하나와 구축물 넷

- 레거시 재생: `sts backtest run` → `shared/backtest/market_context_replay.py` →
  `decision_harness.py` `BacktestDecisionHarness.run` → `TradeRecord`. 디스크 산출물 없음(MLflow 만),
  **거부 후보 기록기는 no-op**(`shared/backtest/signals_writer.py`) → 거부 사유는 숫자 하나.
- TOS 재생: **런타임 marketfeed 저널 경로는 불가** — `TickScheduler` 가 벽시계 기준이라 과거
  `as_of_ms` 가 전부 STALE(#807 모양, `time.yaml` 1000 ms). 가능한 것은 clock-free
  `tos/src/tos/backtest`(`BacktestDriver`, 주입된 timestamp 좌표) 뿐이며 그것은 ① 로더 없음(의도적
  out-of-tree, `bars.py` 4–7행) ② **스코프당 실행당 주문 1 개**(`__init__.py` 57–62행 — 두 번째부터는
  용량 거부) ③ 성과 표면 봉인(Sharpe/PnL 구성 불가, `results.py` 84행) ④ 「인정된 백테스트 아님」 자기
  선언. 그러므로 TOS 쪽 비교는 **결정·의도 수준**(규칙 발화·거부 사유)이지 PnL 이 아니다. ②는 체결만
  막고 규칙 발화는 trace 에 남으므로 「봉마다 발화했는가」 비교는 된다 — 체결 대 체결 비교는 안 된다.
- `tos_runtime.backtest` 는 재생기가 아니라 paper↔backtest 체결 **보정 게이트**다(비교 어휘로는 유용).
- 데이터: `data/market/futures/minute/` 에 `101S6000` 316일(2025-07-01~2026-10-07), `A05610` 101일.
  신뢰 범위(`101S6000` 2025-12-01~04-30)는 분석 문서 산문에만 있고 기계가 읽는 커버리지 매니페스트는
  없다(`data/market/manifest.yaml` 부재). 선물 **일봉은 2026-06-25 에서 멈춰** 있다.

구축물 넷(코드, 전부 미착수 — §4 결정 7 이 승인 대상):

| # | 구축물 | 자리(방화벽 준수) | 왜 |
|---|---|---|---|
| B1 | Parquet → `tuple[Bar,...]` 로더 **+ 공유 지표 생산자**(vwap·atr14·z·ATR p90·스톨·역전·세션 창 → 정수 필드) | `tools/tos_cp3/`(out-of-tree; `tos` 는 `shared.indicators` 를 import 할 수 있으나 `shared.backtest` 는 금지) | 양쪽이 **같은 산식**을 쓰게 — 아니면 비교가 밴드 수학을 잰다 |
| B2 | 레거시 후보·거부 기록기 | `shared/backtest/` 재활성 또는 하네스 래퍼 | `signals_writer` 가 no-op 이라 거부 사유가 없다 |
| B3 | 결정 수준 diff 포맷(봉별: 레거시 후보/거부 ↔ TOS 발화/NO_ACTION/거부 사유) | `tools/tos_cp3/` | TOS 는 PnL 을 못 낸다 |
| B4 | 스코프당 주문 1 개 캡의 처분 | 설계 결정(커널 변경은 RFC-008 §14 거버넌스) | 체결 비교를 포기할지, 하루 1 실행으로 쪼갤지 |

## 4. 운영자 결정표

| # | 결정 | 권고 | 대안 · 비용 |
|---|---|---|---|
| 1 | **첫 tenant 전략** | **Setup D** — 유일한 자족·대칭·검증 후보 | Setup A 는 매크로 Critical Input 추가 + 50 분 창; C 는 신호 0 |
| 2 | **비교 데이터셋** | parity 실행은 `101S6000` **2025-12-01~2026-04-30**(검증 수치와 같은 창). paper tenant 는 상주와 같은 mini `A056xx` | `A05610` 2026-05~ 를 쓰면 종목은 맞지만 신뢰 범위가 없고 포인트 값·틱이 달라 OOS 수치와 못 잇는다 |
| 3 | **paper 환경** | **별도 tenant data dir**(런북 §3 식 1회성·스크래치, 상주 코퍼스 불변). 상주 잎에 콘텐츠를 바꾸면 전략 키 변화로 부팅 리플레이가 held 가 된다(런북 §7.10 6) | 다음 롤 genesis(**2026-11-13** 잎 `A05612` 첫 세션)에 올리는 것은 가능하나 §5 의 parity 가 먼저다. 10-12 롤은 너무 이르다 |
| 4 | **방향** | LONG 구성 + SHORT 구성 **둘**로 paper 검증(상주 LONG·SHORT 분기 패턴과 같음) | 런타임이 `Proposal.direction` 을 읽게 배선하는 것은 커널/런타임 변경 — CP-3 범위 밖 |
| 5 | **정책 값 동결** | 컷오프 **345**(현 YAML), `trend_filter` **off**(현 상태 상속, 07-07 노출 명시), `short_blocked_regimes` **삭제**(TOS 에 regime 없음), 수량 **1 계약**(OCP 현 값 = `futures_live` 최대와 일치) | 345 vs 360, 추세 필터 on 은 YAML 에 미결로 남아 있던 운영자 결정 — 여기서 닫는다 |
| 6 | **스톱/타깃·EOD 의 자리** | 1차 슬라이스 청산 = `vwap_reverted` FLAT + `eod` FLAT(15:15) 둘. **ATR 스톱(1.5×)은 1차 범위 밖**으로 명시 — DSL 에 진입가·수치 출력이 없다 | 스톱을 TOS 보호 레인(aggregate risk / safety mesh)에 매핑하는 것은 별도 설계. 1차 결과가 레거시와 다른 이유의 첫째가 이것일 것이다 — 미해결 차이로 기록 |
| 7 | **구축물 B1~B4 승인(범위·비용)** | B1·B3 먼저(각 하루 안팎, Sonnet 실행 에이전트), B2 는 작게, B4 는 「체결 비교 포기」로 처분 | B4 를 커널 수정으로 풀면 RFC-008 §14 거버넌스 항목 |
| 8 | 검증 기간·담당자 | parity 1회 + paper 10 거래일(LONG 5·SHORT 5), 담당 = 운영자(실행은 Claude) | — |

결정 1·2·3·5·6 은 §5 착수 전에 필요하다. 7 은 코드 첫 줄 전에, 4·8 은 paper 단계 전에.

## 5. 1차 슬라이스 (결정 뒤 착수 — 코드 0 줄 상태)

1. **B1 공유 지표 생산자 + 로더** — 입력 Parquet(결정 2), 출력 = 봉별 정수 필드 JSONL(또는 `Bar`
   튜플 + 필드 dict). 산식은 `shared/decision/setups/vwap_reversion.py` 와 **같은 함수**를 호출하거나
   그 수치와 봉별 일치를 테스트로 고정한다. `critical_input_policy.yaml` 에 새 필드 선언(unit/scale).
2. **B2·B3** — 레거시 하네스에서 후보·거부를 봉별로 뽑고, TOS `BacktestDriver` trace 의 발화·NO_ACTION·
   거부 사유와 봉별 diff. 산출물: `reports/tos-cp3/<dataset>/{legacy,tos,diff}.jsonl` + 요약(일치율,
   불일치 사유 분포). 불일치는 **미해결로 남긴다**(계획 §3 CP-3 완료 증거 문장).
3. **Setup D DSL 콘텐츠** — `config/tos_runtime/<tenant>/strategies/setup_d_vwap_reversion.strategy.yaml`
   LONG/SHORT 두 파일, 바인딩 `strategy_bindings.yaml`, 예산 64 안(비교 ≤ 21).
4. **paper 검증**(결정 3·4·8) — 별도 data dir, 런북 §3 절차, 재시작·리플레이·콜드 백업 복원 drill 증거.
5. **완료 증거**(계획 §3 CP-3) — 이관 artifact + digest, 데이터셋 lineage, 판단/거부/위험 차이 보고서,
   양방향·재시작·복구 증거. **PnL 동일성은 완료 조건이 아니다**(TOS 가 못 낸다).

범위 밖(명시): 커널·DSL 변경(RFC-008 §14), `Proposal.direction` 런타임 배선, 상주 코퍼스 교체,
live·실전·증거금. 레거시 코드 삭제는 CP-4.

## 6. 이 문서가 바꾸지 않은 것

코드·설정·cron·호스트 스크립트 0 건. 상위 계획 §4 의 「첫 tenant 전략 … 미정」 행만 이 문서를 가리키게
갱신했다. 독립 리뷰는 PR 에서 받는다.
