# CP-3 착수 — 첫 paper tenant 후보 비교와 운영자 결정표 (2026-10-07)

상태: **조사 완료 · 운영자 승인 2026-10-07 · 결정 9 는 10-08 (a) 로 재결정 · §5 1 (B1a)·2 (B1b·B2·B3) 구현** (6회차: #874·#876·#877 리뷰 처분 + #879 결정 9 + B3 반영). 상위 계획은
[Control Plane 및 첫 tenant 계획](2026-10-06-tos-control-plane-and-first-tenant-plan.md) §3 CP-3 이고,
그 계획이 「전략 선택은 미정 · 후보 비교표 필요」로 남긴 자리를 이 문서가 채운다.
이 문서는 실행·배포·live 승인 문서가 아니다. 실전 선물 주문·증거금 투입은 영구 정책 차단이다.

조사는 세 갈래를 읽기 전용으로 돌렸다 — 레거시 전략 재고, TOS DSL 표현력, 데이터·재생 경로.
아래 모든 행은 저장소의 파일·행을 가리키며, 요약은 가리키는 자리의 대체물이 아니다. 경로 없는
「런북」은 전부 `docs/runbooks/tos-paper-boot.md` 다.

## 0. 한 줄 결론

후보는 **Setup D VWAP 되돌림** 하나로 좁혀진다(§1). 그러나 TOS 커널은 **「공개된 스칼라(bool·int·str)를
비교해 한 (account, instrument) 에 ACTION/FLAT/NO_ACTION 을 내는 것」**만 할 수 있어(§2),
Setup D 의 지표 수학·세션 창·스톨 가드는 **상류 Critical Input 생산자**로 가고, 스톱/타깃은 1차
범위 밖이다(§4 결정 6). 동일 입력 비교는 clock-free `tos.backtest` 하네스로만 가능하고, 그 앞에
**새 구축물 넷**이 필요하다(§3). 그래서 CP-3 1차 슬라이스의 **중심**은 「공유 지표 생산자 + 결정
수준 비교 하네스」이고, DSL 콘텐츠는 그 뒤에 얇게 얹힌다(§5). 운영자 결정 **아홉**이 §4 에 있다.

## 1. 후보 비교표

CP-3 계획의 네 기준(레거시 의존도 · DSL 표현 가능성 · 데이터 가용성 · long/short 검증 가능성)으로
현재 `enabled: true` 인 여섯을 비교했다. 2026-02-26 재설계 뒤 꺼진 셋(`bb_reversion` ·
`opening_volume_surge` · `volume_accumulation`)과 NO-SHIP 판정 계열(추세 추종·ORB·CTA·고확신 홀드,
`docs/plans/2026-07-06-futures-strategy-improvement-roadmap.md` 8·44행)은 재논의하지 않는다.

| 후보 | 레거시 의존 | DSL 표현(§2 기준) | 데이터 | L/S 대칭 | 검증 근거 | 판정 |
|---|---|---|---|---|---|---|
| **Setup D VWAP 되돌림** `config/strategies/futures/setup_d_vwap_reversion.yaml` | **거의 없음** — 지표는 `atr`·`vwap` 둘(`shared/strategy/entry/setup_d_adapter.py` 154–156행). 매크로·이벤트·스크리너 없음. `regime_gate`·`trend_filter` 둘 다 off. 남은 하나가 `short_blocked_regimes:[BULL_STRONG]`(133행)인데 **이 한 줄이 비어 있지 않으면** 어댑터가 `setup_llm_gate.py` 67–84행의 regime 라벨(LLM 컨텍스트 → 메타데이터 폴백)을 읽는다 — 즉 오늘은 LLM 읽기가 살아 있고, 결정 5 뒤에야 「없음」이 된다 | **부분** — 밴드 트리거는 상류 필드 비교로 가능(출하된 `lower_band` 와 같은 꼴). 세션 창·ATR 백분위 게이트·스톨 가드·역전 확인은 상류로, 스톱/타깃은 1차 범위 밖 | 검증 창 = `101S6000` 2025-12-01~04-30(연속물). paper 종목 `A05610` 분봉은 2026-05-01~10-07 101일 **있으나 신뢰 범위 문서 없음** | **정확한 거울** — 방향 = VWAP 괴리 부호(`shared/decision/setups/vwap_reversion.py` 79–80행) | OOS Sharpe **+2.135**, 135 거래, 4/4 폴드, L +130.5 / S +45.2 pt(`docs/analysis/2026-07-06-futures-strategy-backtest-reexamination.md` 37행; 같은 문서 38행은 이전 전용 실행의 **~1.77** 과 「폴드 절단이 다르다」를 병기하고, `…improvement-roadmap.md` P1.3 은 **08:45 앵커 재검증**을 승격 전제로 둔다 — 미실행). 2026-09-08 **orchestrator(paper) 체결 20건 전부 이 전략**이고 같은 날 디커플 섀도 후보는 **0**(`docs/runbooks/futures-pipeline-cutover-f9.md` 09-08 행 · `docs/plans/2026-09-08-setup-d-decoupled-port.md` 5–7행) | **1순위** |
| Setup A 갭 되돌림 | **강함** — `stream:macro.overnight` 필수(24 h 신선도), RegimeGate on, LLM veto | 부분(같은 한계) + 매크로를 Critical Input 으로 올려야 함 | 같음 | 갭 방향 거울이나 `long_blocked_regimes` 비대칭 | Sharpe 5.12 **N=14**, CLI 백테스트 0 거래(하네스가 매크로 미주입) | 2순위 — 하루 50 분 창 |
| Setup C 이벤트 반응 | **강함** — 손으로 쓰는 월별 이벤트 파일, 장중 발화 가능 이벤트 **4종**(`config/scheduled_events.yaml` 11–15행) | 부분 | 같음 | 거울이나 같은 비대칭 | N=7 · CLI 0 거래. 브레이크아웃 검사가 라이브에서 도달 불가라는 2026-06-25 코드 갭 기록(`docs/superpowers/specs/archive/2026-06-25-futures-mr-highvol-setup-d.md` 247–262행) · 다음 장중 이벤트 10-22 | 보류 |
| momentum_breakout(주식) | 스크리너 유니버스·Redis 일봉 지표·regime gate | 부분 + 오프닝 레인지 상류 | 주식 분봉 종목별 들쭉날쭉 | **long-only** | 재튜닝 Sharpe ≈ −5.24(`docs/ROADMAP.md` 311행) | 탈락 |
| williams_r(주식) | 같은 유니버스·시장상태 | 부분 — 교차(이전 봉) 불가 | 같음 | **`allow_short:false`** | OOS 기록 없음 | 탈락 |
| pattern_pullback(주식) | 일봉 ≥200 · 유니버스 | 부분 | 일봉 2023~ 있음 | **long-only** | in-sample 만 | 탈락 |

주식 셋은 전부 long-only 라 계획의 네 번째 기준을 통과하지 못하고, 스크리너·일봉 Redis 를 끌고 온다.
선물 셋 중 Setup D 만 자족적이다. **Setup D 의 알려진 결함**은 그대로 상속한다 — 2026-07-07 하루 13 연속
역추세 롱(−8.4 pt, `docs/superpowers/specs/2026-07-07-setup-d-trend-filter-design.md` 11–22행),
추세 필터는 구현됐으나 수용 기준 미달로 off(같은 문서 4–5행). 워밍업 상태(780·15·30 봉 deque,
`vwap_reversion.py` 339–358행)는 메모리에만 있고 게이트는 `vol_warmup_bars: 120`(YAML 70행) 아래에서
관대하므로 **콜드 스타트 뒤 약 2 시간은 느슨한 전략**이 돈다 — 재시작/리플레이 증거를 요구하는
CP-3 에서 가장 큰 설계 질문이다.

## 2. DSL 이 오늘 할 수 있는 것 — 그래서 무엇이 상류로 가는가

`tos/src/tos/dsl/vocabulary.py` 기준(57–83행 노드 10종, 119–127행 연산자 EQ/NE/LT/LE/GT/GE). DSL 갭
번호는 `docs/plans/2026-07-29-tos-dsl-spike-findings.md` 66–95행의 **DSL-G** 번호다(상위 계획 §3 CP-4 가
링크하는 레거시 처분 게이트 G1~G5 와 **다른 것**).

- 산술·집계·함수·루프 없음(DSL-G1). OR/NOT 없음 — 분리 규칙·연산자 반전으로(DSL-G2).
- 봉 히스토리 없음 — 현재 캡슐의 평면 스칼라만(DSL-G3, 330–354행). 세션 시각 없음 — DSL 의 `capsule`
  소스는 `critical_input_snapshot` 만 푼다(`tos/src/tos/marketfeed/resolver.py` 170–192행); 캡슐의
  `session_and_tradability` 슬롯은 런타임 빌더가 채우지도 않지만(`tos/runtime/src/tos_runtime/marketfeed/capsule.py`
  109–115행) 채워도 DSL 이 읽을 자리가 아니다.
- **지표 프리미티브 0** — VWAP·ATR·RSI 무엇도 커널이 계산하지 않는다. 모든 값은
  `critical_input_policy.yaml` 에 선언된 필드로 상류에서 들어오며 모양은 **bool·int·str**(float 만
  거부: `tos/src/tos/marketfeed/value.py` 325–359행). 오늘 paper 가 공개하는 필드는
  `close`·`lower_band`·`upper_band` 셋뿐이고, 필드마다 `unit/scale/multiplier/sign/max_age_ms` 다섯을
  출처와 함께 적어야 한다(`config/tos_runtime/paper/critical_input_policy.yaml` 66–86행 「출처 없는
  수치는 넣지 않는 것이 이 디렉터리의 규칙이다」).
- Proposal 에 **숫자 필드 없음**(DSL-G5) — 수량·가격·스톱·타깃 없음. 수량은 OCP 의 정적 SizingBound
  (`order_construction_policy.yaml` 160–178행, 현재 1 계약 고정). 부분 청산 없음.
- **방향은 배포(구성)당 하나** — 근거는 `config/tos_runtime/paper/order_construction_policy.yaml`
  194–213행(「DIRECTION 은 구성당 사실 · 배포 세대 전체에 정적 값 하나」), 캡슐 빌더의 단일
  `direction`(`marketfeed/capsule.py` 54·65·112행), 렌더가 함께 고쳐 쓰는 앵커 다섯
  (`scripts/tos/render_paper_config.py` 215–228행)이다. ⚠ `compose/_envelope_wiring.py` 150–190행은
  이와 **반대 방향의 교정**을 담는다 — 「방향은 시도마다 결정되며 정책 상수가 아니다(2026-09-16)」,
  액션 클래스에서 LONG/SHORT 를 유도 — 그러나 「런타임에 아직 Proposal 경로가 없다」는 같은 문단이
  말하듯 Proposal.direction 은 아직 소비되지 않는다. 그래서 대칭 전략 파일은 파싱되지만 **한 렌더 배포로
  양방향을 돌릴 수는 없다**.
- 예산 `dsl_evaluation_budget_steps=64`(`config/tos_runtime/paper/engine.yaml` 26행) = 규칙 + 비교 +
  피연산자 ≤ 64 → 규칙 1개면 비교 ≤ 21, 규칙 3개(진입 + FLAT 둘)면 ≤ 20.

따라서 Setup D 를 TOS 에 올리면 **tenant 콘텐츠는 얇은 정책**이 된다 — 상류가 매 봉마다
`z_x1000` · `hi_vol`(ATR 백분위) · `stall_ok` · `reversal_ok` · `entry_window`(09:00~컷오프) ·
`vwap_reverted` · `eod` 같은 필드를 공개하고, DSL 은 그 AND 로 ACTION/FLAT 을 낸다.
**지표 수학의 정본은 상류 생산자**이며, 그 생산자를 레거시 지표 엔진과 **같은 코드**로 두지 않으면
비교는 정책이 아니라 밴드 산식을 재게 된다(§3). 두 가지를 같이 적어 둔다: ① `entry_window`·`eod` 는
**제한적 전략 게이트**일 뿐 거래 가능성·세션 위상의 증거가 아니다(RFC-008 §10 「전략은 tradability 를
단언하지 않는다」 · ADR-002-019 「예정 시각은 위상의 유일한 증거가 아니다」) — 세션 슬롯은 비워 둔다.
② 780봉 집계(`hi_vol`·`stall_ok`)는 ADR-002-018 §10 의 **파생 Critical Input lineage**(부모·변환 그래프·
버전·집계 규칙) 대상인데 배포된 필드 모양에는 lineage 슬롯이 없다 — 어디에 둘지는 B1 의 설계 질문이고,
「같은 함수 호출」은 같은 절이 말하듯 **독립 확증이 아니라 공통 모드**다(parity 가 확증하는 것은 정책이지
밴드 수학이 아니다).

## 3. 동일 입력 비교 — 가능한 경로 하나와 구축물 넷

- 레거시 재생: Setup D 의 OOS 수치는 `scripts/analysis/walkforward_setup_d_vwap_reversion.py`
  (160행에서 `MarketContextReplay` + `SetupDVWAPReversion.check()`; 기본 창 2025-12-01~04-30 = 결정 2 의
  창)가 냈고 **폴드 집계 JSON**(`--output`, 559–580행)을 쓴다. 하네스 진입은
  `shared/backtest/harness_engine.py::run_futures_backtest` 이고, `sts backtest run` 은 **다른 경로**
  (`shared/backtest/adapter.py` + `backend.py`)다 — 그쪽은 재검토 문서 44–47행이 Setup A/C 0 거래로 적는
  경로이니 보내지 말 것. 어느 쪽도 **봉별 후보/거부 산출물이 없다** — `shared/backtest/signals_writer.py`
  는 no-op 이고 거부는 `total_rejected_by_filter` 숫자 하나다.
- TOS 재생: **런타임 marketfeed 저널 경로는 불가** — `TickScheduler` 가 벽시계 기준이라 과거
  `as_of_ms` 가 전부 STALE(#807 모양, `time.yaml` 1000 ms). 가능한 것은 clock-free
  `tos/src/tos/backtest`(`BacktestDriver`, 주입된 timestamp 좌표) 뿐이며 그것은 ① 로더 없음(의도적
  out-of-tree, `bars.py` 4–7행) ② **스코프당 실행당 주문 1 개**(`__init__.py` 55–59행 — 두 번째부터는
  용량 거부) ③ 성과 표면 봉인(Sharpe/PnL 구성 불가, `results.py` 84행) ④ 「인정된 백테스트 아님」 자기
  선언. 그러므로 TOS 쪽 비교는 **결정·의도 수준**(규칙 발화·거부 사유)이지 PnL 이 아니다. ②는 체결만
  막고 규칙 발화는 trace 에 남으므로 「봉마다 발화했는가」 비교는 된다 — 체결 대 체결 비교는 안 된다.
- `tos_runtime.backtest` 는 재생기가 아니라 paper↔backtest 체결 **보정 게이트**다(비교 어휘로는 유용).
- 데이터: `data/market/futures/minute/` 에 `101S6000` 316일(2025-07-01~2026-10-07), `A05610` 101일.
  신뢰 범위(`101S6000` 2025-12-01~04-30)는 분석 문서 산문에만 있고 기계가 읽는 커버리지 매니페스트는
  없다(`data/market/manifest.yaml` 부재) — §5 5 의 「데이터셋 lineage」는 그 매니페스트를 만드는 일이다.
  선물 **일봉은 2026-06-25 에서 멈춰** 있다.

구축물 넷(§4 결정 7 로 승인됨 — **B1a·B2·B3 구현됨**(`tools/tos_cp3/`) · **B1b 구현됨**(`tos/runtime/cp3/`) ·
B4 는 「체결 비교 포기」로 처분되어 B3 의 `summary.json` 이 그 범위 제한을 명시한다).
⛔ **방화벽은 양방향이다**: `tos` 밖의 어떤
파일도 `tos`/`tos_runtime` 을 import 할 수 없고(`tools/tos_firewall_check.py` TOS-FW-R, `tools/` 도 검사
대상), `tos` 는 `shared.indicators` 는 되지만 `shared.backtest` 는 안 된다. 그래서 `Bar` 튜플을 만들거나
`BacktestDriver` 를 모는 코드는 **`tos/` 안**에만 둘 수 있다.

| # | 구축물 | 자리(방화벽 준수) | 왜 |
|---|---|---|---|
| B1a | Parquet → 봉별 **정수 필드 JSONL** 생산자(vwap·atr14·z·ATR p90·스톨·역전·세션 창; `shared/decision/setups/vwap_reversion.py` 의 산식과 봉별 일치를 테스트로 고정; lineage 기록 포함) | `tools/tos_cp3/`(레거시 쪽; `tos` import 0) | 양쪽이 **같은 산식**을 쓰게 — 아니면 비교가 밴드 수학을 잰다 |
| B1b | JSONL → `tuple[Bar,...]` 로더 + `BacktestDriver` 실행기 → trace JSONL — **구현됨 `tos/runtime/cp3/`** (`runner.py` · `strategies/setup_d_long.strategy.yaml` · `strategy_bindings.yaml` · `tests/`) | **`tos/runtime/`(또는 `tos/tests/backtest` 식 러너) 안**; 바깥과는 파일로만 만난다(`render_paper_config.py` 의 서브프로세스 경계와 같은 모양). ⛔ **설치 패키지 루트 둘(`tos/src/tos/`·`tos/runtime/src/tos_runtime/`) 아래에는 단 한 바이트도 두지 않는다** — paper 릴리스 핀 `config/tos_runtime/paper/release.yaml::expected_code_digest` 가 그 두 루트의 모든 `*.py` 를 접은 sha256 이고(`tos_runtime/operations/dependency_admission.py::observe_source_tree_digest` + `default_package_roots`) 상주 paper 세션이 매일 아침 origin/main 에서 재도출해 불일치면 ABORT 하므로, 파일 하나만 더해도 상주가 멈춘다. 동시에 `tos/cp3/` 는 쓸 수 없다 — 방화벽의 범위 판정(`tools/tos_firewall_check.py::scope_for_tos_path`)이 `tos/runtime/**` 만 RUNTIME 으로 보고 그 밖의 `tos/` 는 KERNEL 로 보아 `tos_runtime` import 를 TOS-FW-G 로 막는다(실측: `tos/cp3/_probe.py` 가 전략 로더를 import 하면 게이트 red). 두 제약을 동시에 만족하는 자리는 `tos/runtime/cp3/` 뿐이다. 모듈 경로는 그래서 `cp3.runner`(`PYTHONPATH=…:tos/runtime`)이고 `tos.cp3.runner` 가 아니다 — 후자는 커널 패키지 루트에 파일을 넣어야 해서 digest 제약과 충돌한다 | `Bar`·`BacktestDriver` 는 `tos.backtest` 타입 |
| B2 | 레거시 봉별 후보·거부 기록기 | `tools/tos_cp3/`(레거시 쪽; 당초 이 행은 `shared/backtest/` 래퍼로 적었으나, B1a 의 창 로더·조인 키·생략 술어를 **같은 코드로** 써야 조인이 성립하므로 같은 패키지에 두었다) | `signals_writer` 가 no-op 이라 거부 사유가 없다 |
| B3 | 결정 수준 diff(봉별: 레거시 후보/거부 ↔ TOS 발화/NO_ACTION/거부 사유) | `tools/tos_cp3/`(아티팩트 대 아티팩트, 설계 #33 §6.1) | TOS 는 PnL 을 못 낸다 |
| B4 | 스코프당 주문 1 개 캡의 처분 | 설계 결정(커널 변경은 `tos-spec/src/part-1-foundation/GOV-001-Ratification-and-Change-Governance.md` 절차) | 체결 비교를 포기할지, 하루 1 실행으로 쪼갤지 |

B1~B3 와 별도로 **부팅 경로 작업**이 따라온다(§5 3): 렌더의 `_STRATEGY_FILE`
(`scripts/tos/render_paper_config.py` 150행)이 `bootproof_band` 로 고정돼 있고, 새 Critical Input 필드는
CRITICAL_INPUT 정책 digest 를 바꾸므로 다섯 digest 를 다시 뽑아 `safety_activation.yaml::members` 에
적어야 부팅이 받는다(런북 §5). 이것은 구축물이 아니라 절차지만 빠뜨리면 첫 부팅이 거부된다.

## 4. 운영자 결정표

| # | 결정 | 권고 | 대안 · 비용 |
|---|---|---|---|
| 1 | **첫 tenant 전략** | **Setup D** — 유일한 자족·대칭·검증 후보 | Setup A 는 매크로 Critical Input 추가 + 50 분 창; C 는 라이브 도달 불가 코드 갭 |
| 2 | **비교 데이터셋** | parity 실행은 `101S6000` **2025-12-01~2026-04-30**(검증 수치와 같은 창; 08:45 앵커 재검증은 미실행임을 병기). paper tenant 는 상주와 같은 mini `A056xx` | `A05610` 2026-05~ 를 쓰면 종목은 맞지만 신뢰 범위가 없고 포인트 값·틱이 달라 OOS 수치와 못 잇는다 |
| 3 | **paper 환경** | **tenant 전용 설정 트리 + data dir**, 방향마다 **따로**(런북 §7.10 3: 한 디렉터리에 두 방향을 섞는 경로는 설계에 없다; §3 의 1회성 절차). 상주 잎·상주 설정 불변 | 상주 잎에 콘텐츠를 바꾸면 전략 키 변화로 부팅 리플레이가 held(런북 §7.10 6 ⚠ 문단). 롤 genesis 에 올리는 것(그 다음 롤 **2026-11-13**, 잎 `A05612`)은 §5 의 parity 뒤 |
| 4 | **방향** | LONG 배포 + SHORT 배포 **각각 렌더**(설정 트리·data dir 분리). SHORT 는 상주 패턴처럼 **한 세션**부터 | `Proposal.direction` 을 런타임이 읽게 배선하는 것은 커널/런타임 변경 — CP-3 범위 밖 |
| 5 | **정책 값 동결** | 컷오프 **345**(현 YAML), `trend_filter` **off**(현 상태 상속), `short_blocked_regimes` **삭제 — 의도된 차이로 등재**(TOS 에 regime 입력이 없고 대칭 규칙에도 맞지만, 추세 지속일의 지배적 실패를 막던 가드라 07-07 노출이 **둘 다** 열린다; parity 보고서는 SHORT 편향 diff 를 이 항목에 귀속), 수량 **1 계약**(OCP 현 값) | 345 vs 360, 추세 필터 on 은 YAML 에 미결로 남아 있던 운영자 결정 — 여기서 닫는다 |
| 6 | **스톱/타깃·EOD 의 자리** | 1차 슬라이스 청산 = `vwap_reverted` FLAT + `eod` FLAT(15:15) 둘. **ATR 스톱(1.5×)은 1차 범위 밖 — 의도된 차이로 승인 근거를 남긴다**(DSL 에 진입가·수치 출력이 없고, 보호 분류는 PAC 소관이라 전략이 자칭 못 함) | 스톱을 TOS 보호 레인(aggregate risk / safety mesh)에 매핑하는 것은 별도 설계 |
| 7 | **구축물 B1a·B1b·B2·B3·B4 승인(범위·비용)** | B1a·B1b·B3 먼저, B2 는 작게, B4 는 「체결 비교 포기」로 처분. 공수는 착수 뒤 첫 PR 에서 실측으로 | B4 를 커널 수정으로 풀면 GOV-001 절차 |
| 8 | 검증 기간·담당자 | parity 1회 + paper: YAML 131행의 **「≥4 주」**를 기본으로, 더 짧게 자르면 그 근거를 적는다. 담당 = 운영자(실행은 Claude) | — |
| 9 | **venue 수량 상한의 출처** | 오늘 paper 의 `venue_constraint_policy.yaml::max_quantity` 는 **null(의도된 fail-closed)** 이라 Proposal 이 전부 `STAGE_DENIED | venue quantity constraint incomplete` 다(10-07 세션 2,510건). 값이 들어오기 전까지 paper 단계는 **결정 수준 관측만** 가능하고 청산 규칙·영수증 증거는 못 만든다. 권고: 모의 계좌 **P0-2 식 GET 프로브**로 출처를 만들어 값을 넣는 것 — 실전 계좌·실주문은 영구 차단. **10-08 재결정: 위 권고(프로브가 출처)는 불가로 판정됐다 — `VTTO5105R` 은 예수금·레그 파라미터 파생값이라 구조 상한을 못 준다 — 운영자 선택 2026-10-08 (a) 「KRX 규정 문서를 1차 출처로, 모의 GET 은 보강」이 권고를 대체한다.** 설계 `docs/plans/2026-10-08-tos-cp3-venue-limit-source-and-probe-design.md`(값 **10,000** = 시행세칙 별표 17의2 **미니코스피200선물거래** 행 — tenant·paper 상품은 결정 2 의 mini `A056xx`; full `101xxxx` 행 2,000 은 parity 데이터셋에만 · ⚠ `price_min/max` 는 일별 동적 값이라 결정 9 만으로는 `order_shape_admissible` UNKNOWN 유지 → band 원천은 그 문서 §6 의 별도 결정 · ⚠ 부수 발견: 배포 `tick_size: 5` 는 full 의 0.05, mini 규정값은 0.02 — §6 전제로 정정) **✅ 값 착지 완료 2026-10-09**(채택 2026-10-08 · 설계 §8 1·5단계): 운영자가 세 가지를 결정했다 — ① `max_quantity: 10000` 은 **CP-3 tenant 트리에만**(`config/tos_runtime/cp3-setup-d-long/venue_constraint_policy.yaml`), **상주 `paper` 트리는 `null` 유지**(paper 채택 보류) · ② `tick_size` 5 → **2 승인**, 단 착지 소유자는 **band 원천 웨이브**(별도 계획 문서) — band 가 null 인 동안 tick 검사는 step 3 UNKNOWN 에 가려져 무효이고 둘은 같은 PR 에서 움직인다 · ③ band 원천 = **(i) broker 조회**, 역시 그 웨이브. ⚠ 그래서 **step 2 의 `quantity constraint incomplete` DENY 는 tenant 트리에서 사라졌지만 송신은 열리지 않았다**(band null → step 3 UNKNOWN; 설계 §3 「필요조건이지 충분조건이 아니다」) | 값 없이 가면 §5 4 의 범위를 「체결 없음」으로 줄여 적는다 |

**운영자 승인 2026-10-07: 아홉 전부 권고대로.** — 단, **결정 9 는 2026-10-08 에 (a) 로 재결정**(행 9 의 10-08 줄: 10-07 권고가 불가로 판정돼 출처가 프로브 → KRX 규정으로 바뀌었다).

결정 1·2·3·5·6·9 는 §5 착수 전에 필요하다. 7 은 코드 첫 줄 전에, 4·8 은 paper 단계 전에.

## 5. 1차 슬라이스 (운영자 승인 2026-10-07 · 1 착수)

1. **B1a 공유 지표 생산자 — 착수(2026-10-07)**: `tools/tos_cp3/produce_fields.py`
   (패키지 `tools/tos_cp3/`, 레거시 쪽 · `tos`/`tos_runtime` import 0 · 테스트
   `tests/tools/test_cp3_produce_fields.py`). 산식은 레거시
   `shared/decision/setups/vwap_reversion.py` 를 봉마다 몰아 그 자신의 평가 기록
   (`SetupDVWAPReversion.last_eval`, 같은 PR 에서 추가한 읽기 전용 관측 슬롯)을 읽는다 —
   §3 이 경고한 「두 번째 구현」을 두지 않기 위해서다. 입력 Parquet(결정 2), 출력 = 봉별 필드
   JSONL + lineage 블록. 새 필드는
   **tenant 설정 트리**의 `critical_input_policy.yaml` 에 다섯 값(unit/scale/multiplier/sign/max_age_ms)과
   출처를 적어 선언한다(상주 `paper` 트리는 건드리지 않는다 — 건드리면 런북 §7.10 6 의 두 번 부팅
   의무가 따라온다). 트리의 `environment`·`scope.environments` 는 `paper` 로 둔다(로더가
   `--environment-label` 과 대조하지 않아 어긋나도 조용히 부팅한다 — 같은 파일 56–62행).
2. **B1a·B1b·B2·B3 구현됨** — `tos/` 안의 러너가 JSONL 을 `Bar` 로 읽어
   `BacktestDriver` trace 를 쓰고, 레거시 쪽 기록기가 봉별 후보·거부를 뽑고, `tools/tos_cp3/` 가
   둘을 봉별로 diff 한다. 네 자리:
   **B1a** `tools/tos_cp3/produce_fields.py` · **B2** `tools/tos_cp3/emit_legacy_decisions.py` ·
   **B1b** `tos/runtime/cp3/`(`runner.py` 외 여덟 모듈 · `strategies/setup_d_long.strategy.yaml` ·
   `strategy_bindings.yaml` · `tests/`) · **B3** `tools/tos_cp3/diff_decisions.py`. 산출물은
   넷 다 `--out/<payload>.jsonl` + `lineage.json` 이고 B3 는 거기에 `summary.json` 을 더한다;
   **배치는 B3 가 이렇게 정했다** —
   `reports/tos-cp3/<symbol>_<window_start>_<window_end>/`(합의된 window identity 로 키를 잡아
   같은 창의 두 실행이 같은 자리에 떨어지고 경로만 보고 어느 창인지 알 수 있게; `reports/**` 는
   gitignore 라 아티팩트는 커밋하지 않는다) + 요약(일치율, 불일치 사유 분포). 불일치는
   **미해결로 남기되**, 결정 5·6 의 두 의도된 차이는 승인 근거와 함께 따로 센다.

   **B2 착수·구현(2026-10-08)**: `tools/tos_cp3/emit_legacy_decisions.py`
   (테스트 `tests/tools/test_cp3_emit_legacy_decisions.py`). 창은 B1a 의
   `produce_fields.load_window` 를 그대로 호출하고 조인 키도 B1a 의
   `derive_raw_event_id`/`derive_as_of_ms` 를 import 하므로 두 아티팩트는 봉 단위로 맞물린다.
   봉마다 `check()` 의 결과(FIRED 또는 닫힌 집합으로 분류된 거부 사유)와 그 자신의 평가 기록을
   정수·불린으로 투영해 적고, 별도 불린
   `would_be_admitted_by_legacy_position_model` 로 워크포워드 하네스의 단일 포지션 게이트
   (`scripts/analysis/walkforward_setup_d_vwap_reversion.py::collect_entries` 150–203행,
   청산은 같은 파일 `_simulate_exit` 206–263행을 **그대로 호출**)까지 함께 센다.
   자리는 `tools/tos_cp3/`(§3 표 B2 행에 이유를 적었다). lineage 는 `config_source_diff` 로
   **워크포워드 하네스가 전략 YAML 을 읽지 않는다**는 사실을 기계적으로 적는다(컷오프 345 vs 360 ·
   stall 1.5 vs 1.0 · `min_confidence` 0.6 vs 0.0 · `reversal_confirm_enabled` true vs false) —
   그래서 공표된 수치의 실행에서는 `LOW_CONFIDENCE` 와 `awaiting_reversal_confirm` 셋이
   **도달 불가**였고, admitted 수를 공표된 135 와 비교할 수 없다(135 는 OOS 폴드 연결이기도 하다).
   공표 수치의 앵커는 **미해결**로 적는다(09:00 을 가리키는 근거 둘 vs 재검토 문서 날짜).

   **B1b 착수·구현(2026-10-08)**: 자리와 그 이유는 §3 의 B1b 행에 있고, 한 줄로 다시 적으면 —
   **설치 패키지 루트 둘(`tos/src/tos/`·`tos/runtime/src/tos_runtime/`) 아래에 0 바이트**를 두어야
   하고(paper 릴리스 핀 `expected_code_digest` 가 그 두 루트를 접으며 상주 세션이 매일 재도출해
   불일치면 ABORT) 동시에 `tos_runtime` 을 import 할 수 있어야 해서(방화벽이 `tos/runtime/**` 만
   RUNTIME 으로 본다) **두 제약을 같이 만족하는 자리는 `tos/runtime/cp3/` 뿐**이다. CLI 는
   `python -m cp3.runner --fields … --strategy … --bindings … --out …` (모듈 경로가 `cp3.runner` 이고
   `tos.cp3.runner` 가 아닌 것도 같은 digest 제약 때문이다)이고 타입 거부는 종료코드 2 다.
   값이 DSL 에 닿는 경로는 **이미 있던 타입 seam** 이다 — 봉마다 Capsule 을 발행해 그 `SnapshotRef` 를
   해석기가 되읽어 `DecisionTickPayload.value_view`(`tos.dsl.ContextValueView`)를 공개하면
   `tos.engine.pipeline` 이 그것을 `evaluate_resolved` 로 넘기고 `build_environment` 가
   `capsule.resolved_values.<field>` 로 병합한다. 뷰의 `canonical_digest` 는 커널
   `tos.marketfeed.value.context_value_view_digest` 로 계산한다(직접 계산하면 `view_digest_matches`
   가 거짓이 되고 그 digest 가 모든 `outcome_digest` 로 흐른다 — 2026-10-08 리뷰 실측). 커널·런타임
   변경 0. 하네스에는 `critical_input_policy` 주입 자리가 없어 필드는 **이미 승인된 값**으로
   들어가고, 다섯 값(unit/scale/multiplier/sign/max_age_ms)은 lineage 의 `versions.field_policy` 에
   기록된다(의도된 차이 B1b-D3).

   **B3 착수·구현(2026-10-08)**: `tools/tos_cp3/diff_decisions.py`
   (테스트 `tests/tools/test_cp3_diff_decisions.py`). CLI 는
   `diff_decisions --fields <B1a fields.jsonl> --legacy <B2 decisions.jsonl> --tos <B1b trace.jsonl>
   --out <dir>` 이고 각 아티팩트의 `lineage.json` 은 형제로 자동 발견된다(`--*-lineage` 로 덮어쓴다).
   자리는 `tools/tos_cp3/`(§3 표 B3 행)이고 `tos`/`tos_runtime` import 0 — B1b 의 trace 는 **파일로**
   읽는다. B1a 의 `produce_fields` 도 import 하지 않는다: B3 의 주장은 세 **파일**에 관한 것이므로
   그 파일을 만든 밴드 수학이 사라진 뒤(CP-4)에도 유효해야 한다. 그래서 provenance 헬퍼 둘
   (`render_json`·`_git_identity`)만 자기 사본으로 두고, 둘이 **같은 구현**이라는 것을 테스트가
   **정규화 AST 대조**로 고정한다(이름·인자명만 정규화 — 한 샘플 문서의 바이트 비교는 `sort_keys`
   드리프트를 통과시킨다; 프로젝트 메모 `guards-that-admit-what-they-name`).

   **먼저 거부한다** — 검사 **열다섯**(`diff_decisions.CHECK_NAMES`), 종료코드 2. 거부된 실행은
   **아무것도 쓰지 않으므로** 출력 lineage 의 `checks` 는 성립한 검사만 열거하고 `status` 필드는
   없다(항상 "PASS" 인 리터럴은 검사가 아니다). 각 항목을 **가드**로 만드는 것은 테스트의
   레드 증명 하나씩이다. 거부 순서는 기록 순서와 **같다**:
   ① 귀속표가 어떤 lineage 에도 없는 선언된 차이 id 를 가리킴 · ② 이 도구가 분기하는 두 outcome
   리터럴(`FIRED`·`LOW_CONFIDENCE`)이 B2 의 닫힌 집합 밖 · ③ B1a 의 투영된 window identity ≠ B2 의
   `join.window_identity`(B2 의 `b3_contract` 가 요구하는 거부 — B1a 에는 `join` 블록이 없으므로
   identity 는 `dataset`·`strategy` 에서 투영하고 그 투영표를 lineage 에 적는다) · ④ B1a 와 B2 의
   `strategy.path`·`strategy.sha256`·`dataset.input_files` digest·파일 수 불일치(여섯 identity
   필드는 YAML 파라미터 수정이나 다시 쓰인 Parquet 을 **못 본다**; (B1a,B1b) 변은 이미 sha 로
   고정돼 있어 비대칭이었다) · ⑤ 세 파일이 각자의 lineage 가 적은 sha256·줄수와 다름 · ⑥ B1b lineage 의
   `parents.fields_jsonl.sha256`(과 `parents.fields_lineage_json.sha256`) ≠ 준 fields.jsonl ·
   ⑦ 줄수 불일치 · ⑧ `raw_event_id` 순서 불일치(위치를 지목) · ⑨ `as_of_ms` 불일치 ·
   ⑩ 페이로드의 **float**(`json.loads` 의 `parse_float`/`parse_constant` 훅이라 `1.0` 같은 정수값
   리터럴과 `NaN` 도 거부) · ⑪ B2 의 닫힌 집합 밖 outcome · ⑫ B2 의 `direction` 이
   `{LONG, SHORT}` 밖, 또는 `FIRED` 인데 방향 없음(방향이 `AGREE_ENTRY`↔`LEGACY_ONLY_ENTRY` 를
   가르므로 토큰 변화는 조용히 버킷을 옮기는 대신 거부해야 한다 — B2 는 이 토큰을 lineage 에
   선언하지 않아 리터럴이고, 테스트가 `emit_legacy_decisions.DIRECTION_TOKENS` 에 고정한다) ·
   ⑬ `outcome_kind` 가 셋 밖 · ⑭ 버킷 합이 **digest 패스에서 센 입력 줄수**와 다름(파싱 전에 센
   개행 수라 `sum(buckets)==len(records)` 같은 항등식이 아니다) · ⑮ **자기 출력**의 float —
   `summary.json` **과 `lineage.json`** 의 렌더된 바이트를 둘 다 훑는다(lineage 는 입력 sidecar 의
   `producer` 블록을 그대로 복사하고 sidecar 의 float 은 허용되므로, `"version": 1.0` 한 줄이
   이 도구의 출력에 float 을 넣을 수 있었다).

   봉마다 한 줄(`diff.jsonl`)에 레거시 `outcome`·`direction`·
   `would_be_admitted_by_legacy_position_model`, TOS `outcome_kind`·`rule_id`·`capacity_denied`,
   B1a 의 게이트 불린 넷 + `z_x1000`, **버킷**(`AGREE_NO_ACTION` · `AGREE_ENTRY` ·
   `TOS_ONLY_ENTRY` · `LEGACY_ONLY_ENTRY` · `TOS_EXIT_ON_LEGACY_<outcome>`; 전수·배타)과 **귀속**을
   적는다. 귀속표는 모듈 수준의 (술어, 선언된 차이 id) **순서 있는 목록**이고 첫 일치가 이긴다 —
   레거시 SHORT 발화 → B1b-D5 · 레거시 `LOW_CONFIDENCE` 인데 TOS ACTION → B1a-D1·B2-L9(L9 가 그
   귀속을 자기 문장으로 적어 둔다) · **레거시 미발화 봉의** TOS FLAT → B1b-D7 · 결정은 일치했으나
   포지션 모델이 거부 → B1b-D7·B2-L3·B2-L10 · 결정은 일치했으나 용량 거부 → B1b-D1 ·
   그 밖은 **UNRESOLVED**(이유를 만들지 않고 id 를 적는다). **포괄 규칙(catch-all)은 없다.**
   용량·포지션 모델 규칙을 ACTION 규칙 **뒤**에 두고 `AGREE_ENTRY` 버킷으로 한정한 것은 의도다:
   B1b 실행에서 첫 실현 주문 뒤의 모든 ACTION 이 용량 거부라, 앞에 두면 모든 진입 불일치를 흡수해
   원인을 가린다. 임계 `z_entry_max_x1000` 은 리터럴이 아니라 B1b lineage 의
   `parents.strategy_bindings_file.bindings` 에서 읽는다(귀속 술어는 이 값을 읽지 않는다 — 아래).

   ⚠ **z 양자화 경계 규칙은 없다**(2026-10-08 독립 리뷰 ①, 네 명이 재현). 초판은 그런 규칙을
   표의 **마지막**에 사인 무관 ±1 포괄 규칙으로 두었는데, 그 전제가 규칙이 인용하던 B1a-D8 자신과
   **모순**이었다. 도출: `m = extreme_atr_mult`, `f = m×1000`, `T = -trunc(f)` 일 때 B1a 는 0 쪽으로
   절사하므로 TOS 조건 `trunc(z×1000) ≤ T` 는 `floor(|z|×1000) ≥ floor(f)` 이고 레거시 조건은
   `|z|×1000 ≥ f` 다. ① **f 가 정수면** 정수 `n` 에 대해 `floor(y) ≥ n ⟺ y ≥ n` 이므로 **두 조건은
   동일**하다 — 경계가 없다. ② **f 가 비정수면**(예 `m = 1.8005`) TOS 가 `z_x1000 == T` **한 정수**
   에서만 더 관대한데, 그 봉에서 `check()` 는 4단계에서 `NOT_EXTREME` 으로 거부하므로 `stall_ok`·
   `reversal_ok` 는 평가되지 않고 B1a 가 **False 로 공개**한다(그 D5, fail-closed) → R1 의 AND 가
   거짓이라 TOS 도 NO_ACTION 이다. 즉 간극은 **D5 에 가려져** 불일치를 만들 수 없고, 실측 행렬의
   `NOT_EXTREME × ACTION` 은 **0** 이다. 그래서 규칙을 **삭제**했고 그 자리에 도출을 고정하는
   테스트를 남겼다 — 임계는 `tos/runtime/cp3/strategy_bindings.yaml`, `extreme_atr_mult` 는
   `config/strategies/futures/setup_d_vwap_reversion.yaml` 에서 **읽고**(테스트 지역 리터럴 금지:
   리터럴이면 두 YAML 을 바꿔도 초록이고 출하된 도출이 거짓이 된다), z 는 **격자 사이**
   (예 `-1.7995`)까지 훑어 B1a 의 실제 양자화기 `scaled_int_toward_zero` 를 통과시킨다 —
   그래서 trunc→floor 치환이 레드가 된다(격자 위 점만 보면 네 양자화기가 전부 일치해 구별이
   안 된다). 레드 증명 셋 실측: 바인딩 −1800→−1801 · `extreme_atr_mult` 1.8→1.8005 ·
   양자화기 trunc→floor. `summary.json`/`lineage.json` 의 `config.quantization_edge` 가 이 도출을
   싣는다.

   ⚠ **B1b-D7 의 B3 의무는 미이행으로 적는다.** B1b-D7 의 note 는 「B3's diff has to scope the
   legacy side to bars where a position was held」를 요구하지만, B2 의 봉별 페이로드에 포지션·노출
   필드가 없고 세 아티팩트 어디에도 「이 봉에 레거시 포지션이 열려 있었나」가 없다
   (`would_be_admitted_by_legacy_position_model` 은 「이 발화가 받아들여졌나」이지 「지금 열려
   있나」가 아니다). 그래서 `TOS_EXIT_ON_LEGACY_*` 버킷과 `tos_flat_without_legacy_fire` 귀속은
   그 비교의 **상한**이고, `summary.json` 의 `scope.b1b_d7_obligation` 과 그 규칙의 `why` 가
   **UNMET** 으로 적는다. 포지션 상태를 **추론하지 않는다** — admitted 플래그 + 청산 시뮬레이션으로
   만들면 하네스 청산 경로의 **네 번째 구현**(B2-L3)이 되고 그 오차가 정책 차이로 보고된다.
   닫으려면 생산자가 노출 필드를 공개해야 하고 그것은 B2 또는 커널 변경이다.

   **실측(2026-10-08, `101S6000` 2025-12-01~2026-04-30, 35,612 봉)**: 레거시 FIRED **550**
   (LONG **374** / SHORT **176**), TOS R1 ACTION **392**. 버킷 = `AGREE_NO_ACTION` 31,691 ·
   `AGREE_ENTRY` **374** · `TOS_ONLY_ENTRY` 18 · `LEGACY_ONLY_ENTRY` 176 ·
   `TOS_EXIT_ON_LEGACY_*` 3,353(AFTER_CUTOFF 1,918 · VOL_BELOW_GATE 652 · BEFORE_WINDOW 549 ·
   NOT_EXTREME 234). **규칙 수준 진입 일치 374/374 = 100 %**, **포지션 모델 수준 96/96 = 100 %**,
   TOS 쪽에서 본 374/392 = 95.41 %. **UNRESOLVED 0** — LONG 쪽 레거시 발화는 TOS ACTION 과
   **정확히** 일치하고, 초과한 18 은 전부 레거시 `LOW_CONFIDENCE`(B1a-D1·B2-L9: 공개 필드가
   `min_confidence` 를 표현할 수 없어 정책이 「레거시 발화」의 **상위집합**)다. 176 은 전부
   SHORT(B1b-D5: LONG 단독 렌더). ACTION **392 전부**가 용량 거부다(바닥 봉의 R2 FLAT 이 유일한
   주문을 썼다) — 결정 수준의 차이는 아니지만 `summary.json` 의 `totals`·`scope` 가 B1b 의
   `realized_orders`·`handoffs` 와 함께 적는다. 산출물은 커밋하지 않는다
   (`/home/deploy/.local/state/tos/measure/cp3-b3-run1/`, diff sha256
   `ce36450f68f7cb669b0680faa185d1aa906a91c91a80894e8434c13ca5af5677`).
   ⚠ 이 실측은 **리뷰 처분 뒤 깨끗한 커밋 상태**(`git status --porcelain` 빈 상태)에서 다시 돌려
   lineage 의 `tool.git.commit` 이 HEAD 와 같고 `dirty: false` 임을 확인한 산출물이다 — 초판은
   커밋 전 트리에서 돌아 리뷰된 코드가 들어 있지 않은 커밋으로 기록됐다(독립 리뷰 ②).
3. **Setup D DSL 콘텐츠 — LONG 구현됨(2026-10-08) · 부팅 경로 미착수** — 콘텐츠는
   `tos/runtime/cp3/strategies/setup_d_long.strategy.yaml` +
   `tos/runtime/cp3/strategy_bindings.yaml`(strategies/ 아래가 아니라 그 형제 — 안에 두면 로더의
   stray-file 규칙이 디렉터리 전체를 거부한다)로 **먼저 B1b 실행기 쪽에** 들어갔다. 규칙 셋(진입 1 +
   FLAT 2) + 기본값이고 `policy_work_steps` = 3 + 7 + 14 = **24 ≤ 64**(비교 7 ≤ 20). 진입 임계는
   리터럴이 아니라 바인딩 `z_entry_max_x1000 = -1800 = -trunc(extreme_atr_mult × 1000)` 이고 그 등식은
   테스트가 `config/strategies/futures/setup_d_vwap_reversion.yaml` 74행을 직접 읽어 고정한다.
   파일은 **운영 로더**(`tos_runtime.strategy.loader.load_strategies` + 실제 `parse_strategy` /
   `strategy_admissible` + `resolve` 의 바인딩 다섯 규칙)로 적재·승인되는 것을 테스트로 증명했다.
   ⚠ 그래도 `config/tos_runtime/<tenant>/` 로 옮기는 것은 **「복사만」이 아니다**(2026-10-08 리뷰).
   최소 넷이 더 필요하다: ① tenant 설정 트리 자체(렌더가 만드는 열몇 개 YAML — 상주 `paper` 트리는
   건드리지 않는다) · ② 열다섯 필드 × 다섯 값을 `critical_input_policy.yaml` 에 선언하되
   **`max_age_ms` 는 이 경로에서 도출할 수 없다**(B1b 는 전부 `null` 로 두고 의도된 차이 B1b-D3 로
   등재했다 — 백테스트는 주입된 시간 경계로 신선도를 판정하고 필드별 수명 소비자가 없다; 값은
   **운영자 출처**여야 한다) · ③ 그 열다섯 필드를 **paper 런타임에서 매 봉 발행하는 생산자** — B1a 는
   Parquet 배치 도구이고 실시간 발행기가 아니다 · ④ §5 3 의 **부팅 경로**(렌더의 전략 파일 상수·다섯
   digest 재도출·`safety_activation.yaml::members` 갱신).

   **① 착지 완료 2026-10-09 — LONG tenant 트리 `config/tos_runtime/cp3-setup-d-long/`.**
   **31 개 파일 = 바이트 동일 23 + 다름 5 + tenant 전용 3**이고, 더해서 상주 트리의
   `strategies/bootproof_band.strategy.yaml` **하나가 이 트리에 없다**(상주 29 기준).
   측정은 작업트리 비교가 아니라 **git blob OID 대조**(`origin/main:config/tos_runtime/paper`)다.
   다른 다섯 —
   `venue_constraint_policy.yaml`(결정 9 (a) `max_quantity: 10000` · 아래 ②와 별개 · `policy_id`
   tenant 전용) · `critical_input_policy.yaml`(사본이 아니다 — 아래 ②) ·
   `construction.yaml`(**리뷰 2026-10-09 H1**: `price_field_key`·`shape_price_field_key` 가 상주의
   `"close"` → **`"close_x100"`**. 상주의 그 키는 이 트리의 critical_input 에 **없고**, 두 로더가
   서로를 보지 못해 그 불일치를 거부하지 못한다 — `compose/_construction_config.py` 모듈
   독스트링이 그 갭을 자기 입으로 적는다. 고치지 않으면 `_price_for` 가 **값 없는** 가격 관측을
   내고 `derive_order_size` 가 「no positive finite value」로 거부하는데, 그 사유가 설정 불일치를
   지목하지 않는다) · `engine.yaml` · `order_construction_policy.yaml`(뒤 둘은 **주석만**: 두 파일의
   기존 주석이 상주 전략 `bootproof_band` 를 인용해 이 트리에서 거짓이 되므로 tenant 적용 문단을
   덧붙였고, 그 과정에서 스텝 수 24 ≤ 64 를 재측정해 적었다). tenant 전용 셋은 전략 · 바인딩 ·
   트리 자신의 `README.md` 다. 상주 전략 파일은 이 트리에 **없고** 그 자리를
   `strategies/setup_d_long.strategy.yaml` 이 차지한다. `environment`·`scope.environments` 는
   §5 1 대로 `paper` 다. 전략 파일의 B1b 하네스 리터럴 둘(`account: cp3-b1b-long` ·
   `instrument: 101S6000` — 후자는 parity 전용 **full** 월물)은 이 트리의 다른 좌표 칸과 같은
   named-TBD `"TBD"` 로 바뀌었고(세 규칙 × 두 칸 = **여섯 리프**), 그 `"TBD"` 거부가 운영자-채움
   게이트다 — 그러므로 **배포 사본은 B1b 사본과 달리 커밋 상태로 적재되지 않는다.**
   ⛔ **렌더로 만들지 못했다 — 「저장소의 렌더러를 쓸 것」이 성립하지 않는다**(실측):
   `scripts/tos/render_paper_config.py` 는 설계상 **출력이 저장소 안이면 거부**하고
   (`_refuse_output_inside_repo` — 렌더 산출물은 계좌 좌표를 담는다), `.env.mock` 계좌 ·
   종목 · 호스트 digest 를 요구한다. 그 스크립트는 **커밋된 트리를 만드는 도구가 아니라 커밋된
   트리를 소비하는 도구**다(`--source`). 그래서 트리는 상주 트리의 바이트 사본 + 선언된 차이로
   만들었고, 그것이 바로 그 스크립트가 나중에 `--source` 로 받을 모양이다.

   **② 착지 완료 — 다섯 값 전부(`max_age_ms` 포함, 2026-10-09).** 열다섯 필드를 B1a 의
   `FIELD_ORDER` 순서로 선언하고 unit/scale/multiplier/sign 을 **B1a 필드
   lineage**(`produce_fields._field_lineage`)에서 가져왔다.

   `max_age_ms` 는 초판에서 **열다섯 전부 `null`** 이었고 그래서 그 파일이 로드되지 않았다
   (로더가 `null` `max_age_ms` 를 거부한다) — 출처가 없었기 때문이고, 상주 트리가 출처 없는
   값에 쓰는 fail-closed 규율과 같은 상태였다(`finality.yaml::source_revision` ·
   `safety_activation.yaml::members`). **운영자 지시 2026-10-09**(「출처가 없어도 설정이
   필요하니 적용」)로 **180000** 을 적용했다 — 등급 **C**(개발 측 보수 제안,
   `docs/plans/2026-09-12-tos-operator-value-proposals.md:4`).

   도출은 **봉 주기에서** 나온다(실측): B1a 의 봉은 1분(`derive_raw_event_id` 의 `:1m:`),
   `as_of_ms` 는 봉의 **라벨 = OPEN**(`derive_as_of_ms`: 「The label, not label+60s」), 런타임이
   재는 것은 `now_ms - as_of_ms`(`marketfeed/snapshot.py::_derive_field_state`, `now_ms` 는 실
   벽시계). 라벨 T 의 봉은 T+1P 에 닫히고 T+2P 에 교체되므로 **2P = 120,000 은 하한이지
   안전값이 아니다** — 발행 지연 0 에서만 만족되고 그 모양은 이미 측정된 결함(#807)이다.
   세 번째 P 가 지연 여유 → **3P = 180,000**. 보수 방향은 **작게**.
   상주의 600000 은 베껴 오지 않았다: 그 근거는 **배치 저널 부팅**의 지연 흡수다.

   ⚠⚠ **그러나 이 값은 ③ 를 대신하지 않는다(실측 2026-10-09).** 커널 시간 수용 경로는
   **같은 양**(`source_age = wall_clock_now() - as_of`, `marketfeed/time_projection.py`)을
   `time.yaml::MAX_time_conservative_freshness_age_ms` 1000 − Σdelay_bounds 200 = **800 ms**
   예산에 댄다. 라벨 스탬프 1분봉은 그 **75 배**다. 즉 채운 효과는 「파일이 로드된다」뿐이고
   시간 경로는 여전히 STALE 로 읽는다 — ③ 이 그것을 닫는다. ③ 이 상주 수집기처럼 **append
   시각**을 `as_of_ms` 로 찍으면 올바른 한도는 180,000 이 아니라 **800 ms 자리수**이므로,
   ③ 착지 시 이 키 ×15 · `poll_interval_ms` · `journal_pass_allowance_ms` 를 함께 다시 본다.
   `tos/runtime/tests/compose/test_deploy_policies.py` 가 ① 열다섯 값 + 도출 문장 핀, ②
   **하나라도 `null` 이면 로더가 그 키 이름으로 거부한다**(tmp 사본), ③ 위 산술(1분봉 ≥
   800 ms 예산)을 고정한다.

   **✅ data dir · 렌더된 설정 — 지정 2026-10-09 (결정 3 의 「방향마다 따로」).**
   **이름만 지정했고 디렉터리는 만들지 않았다** — genesis 는 첫 부팅(④)이다.

   | 배포 | durable set 부모 | 잎 | 렌더된 설정 |
   | --- | --- | --- | --- |
   | 상주 paper (불변) | `~/.local/state/tos/paper-data` | `<종목>` | `~/.config/tos/paper-config` |
   | tenant **LONG** | `~/.local/state/tos/cp3-setup-d-long-data` | `<종목>` | `~/.config/tos/cp3-setup-d-long-config` |
   | tenant **SHORT** | `~/.local/state/tos/cp3-setup-d-short-data` | `<종목>` | `~/.config/tos/cp3-setup-d-short-config` |

   이름 규칙은 **「설정 트리 이름 + `-data`/`-config`」**다 — 경로만 보고 어느 코퍼스가 어느
   트리로 부팅됐는지 알 수 있어야 한다(런북 §5 ⑤: 활성화 기록은 방향을 결속하지 않는다).
   모드·규율은 상주와 같다(부모·잎 0700 · 스토어 0600 · 저장소 밖). ⛔ 방향을 한 data dir
   에 섞지 않고 상주 잎에도 섞지 않으므로 LONG·SHORT 는 **부모부터** 다르다(런북 §7.10 3).

   **충돌 실측 2026-10-09(읽기 전용 점검)**: ① 콜드 백업 래퍼
   `~/.config/kis-probes/cold-backup-nightly.sh` 는 `COLD_DATA_DIR`(기본 `paper-data`)의
   **직접 자식** 중 `A0[0-9][0-9][0-9][0-9]` 만 잎으로 세고 **`~/.local/state/tos/*` 를
   글로브하지 않는다** → 두 부모는 보이지 않으므로 **백업되지 않는다**(켜는 것은 운영자
   결정; 잎을 `<종목>` 으로 둔 덕에 래퍼 수정 없이 `COLD_DATA_DIR` 지정만으로 된다).
   ② 설정 `~/.local/state/tos/paper-ops/evidence_cold_backup.yaml` 의 세 경로는 전부
   `paper-cold/` 아래 절대경로 리터럴 — 글로브·`~` 전개 없음, 충돌 없음. ③ A1 측정
   아티팩트는 `~/.local/state/tos/measure/` 아래 — 충돌 없음. ④ ⚠ 상주 세션 래퍼의 렌더
   출력 경로 `CONFIG=/home/deploy/.config/tos/paper-config` 는 **하드코딩**(환경 손잡이가
   아니다)이라 **그 래퍼로는 이 tenant 를 띄울 수 없다** — ④ 의 일이다. ⑤ ⚠ 이름 인접:
   `~/.config/tos/paper-config-short` 가 이미 있는데 그것은 **2026-09-28 상주 SHORT
   부팅증명**의 산출물이고 CP-3 SHORT 와 무관하다. 전체 표는 런북 **§7.2-b**.

   **③·④ 는 여전히 미착수다.** ④ 에 대해 2026-10-09 에 **새로 측정된 사실**: ④ 는
   「렌더의 전략 파일 상수 한 줄 교체」가 **아니다** — 그 스크립트의 좌표 규칙은 앵커 줄이
   **정확히 1회** 매칭될 것을 요구하는데(`_apply_rules`) tenant 전략 파일은 규칙이 셋이라
   `account: "TBD"`·`instrument: "TBD"` 가 **각 3회** 나오고, `direction` 은 줄마다 값이 다르다
   (R1 = LONG 진입, R2·R3 = 롱을 닫는 반대쪽 SHORT)이므로 `--direction SHORT` 렌더의 일괄
   치환이 성립하지 않는다.

   ✅ **정책 식별자 충돌은 ④ 로 넘기지 않고 같은 PR 에서 닫았다(2026-10-09 리뷰 L4).** 초판은
   「tenant `venue_constraint_policy.yaml` 의 `policy_id`/`policy_generation` 이 상주와 같은 값인데
   내용이 달라 digest 가 다르고, `(kind, member_id, generation)` 만으로는 두 문서를 구별할 수 없다」를
   ④ 로 미뤘는데, **지금 바꾸는 것이 공짜**라는 지적이 맞았다 — 이 트리는 부팅한 적이 없고 활성화
   기록·증거가 0 이므로 rename 이 무효화할 것이 없다. `vcp-paper-cp3-setup-d-long-krx-index-futures`
   로 바꿨고 **세대는 1 그대로**(상주 정책의 다음 세대가 아니라 **다른 배포의 정책**이다). 기준은
   트리가 다른가가 아니라 **내용이 갈렸는가**이므로 타입 콘텐츠가 같은
   `order_construction_policy.yaml`(주석만 다름) · `aggregate_risk_policy.yaml` ·
   `action_flow_policy.yaml` 의 id 는 **바꾸지 않았다**(같은 id·세대·digest 는 「같은 문서」라는 참인
   진술이고, 거기서 이름을 가르면 같은 것을 둘로 보이게 만든다). `safety_activation.yaml::members` 는
   여전히 `null` 이라 갱신할 활성화 기록이 없고 **digest 리터럴을 지어내지 않았다** — 활성화 자체는
   ④ 의 일로 남는다.

   ✅ **SHORT 트리 착지 2026-10-09 — `config/tos_runtime/cp3-setup-d-short/`** (결정 4 의
   나머지 반쪽). LONG 트리의 사본 + **선언된 방향 차이**이고, **31 파일 = LONG 과 바이트 동일
   23 + YAML 이 다름 6 + 산문이 다름 1(`README.md`) + SHORT 전용 1
   (`strategies/setup_d_short.strategy.yaml`; LONG 의 전략 파일은 이 트리에 없다)**.
   DSL 에 `abs()` 가 없어 진입 비교가 한 변뿐이므로 SHORT 는
   `z_x1000 >= +1800`(op **GE**, 바인딩 `z_entry_min_x1000: 1800`)을 쓰는 자기 파일을 갖는다.

   **방향이 사는 자리 다섯** — 런북 §7.10 3 이 셋을 열거하고(`construction.yaml::action_class`
   `/outbound_side` · OCP 의 DIRECTION 축 · 전략 파일의 `direction`) 이 트리가 둘을 더한다:
   `marketfeed.yaml::direction`(발행되는 모든 캡슐의 `SafetyCriticalFacts` 로 들어간다) ·
   **진입 비교의 변과 그 바인딩**. 다섯 전부를
   `tos/runtime/tests/compose/test_tenant_tree_short.py` 가 LONG 사본과 대조해 고정한다.
   정책 id 는 **셋**이 SHORT 전용이다(venue · critical_input · **OCP**) — OCP 가 LONG 트리에서
   rename 대상이 아니었던 이유는 타입 콘텐츠가 같았기 때문이고, 이 트리는 DIRECTION 축이
   갈리므로 같은 기준(「내용이 갈렸는가」)으로 rename 된다.
   ⚠ **실측 2026-10-09**: OCP 의 `canonical_digest` 는 DIRECTION 축을 바꿔도, **`policy_id` 를
   바꿔도** 달라지지 않는다(OCP 헤더의 KNOWN LIMITATION 보다 한 걸음 더 나쁘다). 그래서 그
   rename 은 digest 를 가르지 못하고 활성화 키의 **`member_id` 만** 두 문서를 구별한다.
   VCP 는 반대로 digest 가 `_model_view.shape_constraints` 를 덮는다(`tick_size` 하나로 달라짐).

   ⚠ **SHORT 에는 parity 증거가 0 이다** — 그 트리 `README.md` §3.3. B1b 실행이 LONG 단독
   (**B1b-D5**)이었으므로 §5 2 의 「규칙 수준 374/374 = 100 %」는 **LONG 쪽 수치**이고, 레거시
   SHORT 발화 176 은 전부 `LEGACY_ONLY_ENTRY` 로 그 차이에 귀속됐다. 더해서 결정 5 가 삭제한
   `short_blocked_regimes` 는 레거시에서 **SHORT 에만** 걸려 있던 가드이므로
   (`long_blocked_regimes` 는 빈 리스트다) 그 손실은 이 방향에 **비대칭적으로** 떨어진다.
   ⚠ **B1a 필드에 SHORT 변종을 만들지 않았다 — 실측 근거**: 방향 의존 게이트
   (`stall_ok`·`reversal_ok`)의 방향은 배포 설정이 아니라 **z 의 부호**에서 나오므로
   (`shared/decision/setups/vwap_reversion.py`: `z >= +extreme` → short) SHORT 규칙이 발화할 수
   있는 봉에서는 이미 숏 쪽 게이트가 평가돼 있다. `vwap_reverted` 는 `abs(z) <= band` 로 대칭,
   `entry_window`·`eod`·`hi_vol` 은 방향 무관이다. **long 전용 필드는 없었다.**
   ⚠ **이 트리는 `--direction SHORT` 렌더가 만든 것이 아니다** — ④ 가 미착수라 그 경로가 없다.
4. **paper 검증**(결정 3·4·8·9) — 방향별 data dir, 런북 §3 절차, 재시작·리플레이·콜드 백업 복원 drill
   증거. 결정 9 **와 band 원천 웨이브**(2026-10-08 설계 §6 — `price_min/max` 가 null 이면 step 3 가 UNKNOWN)가 닫히기
   전엔 체결·영수증(부분/중복/미지)이 없으므로 그 항목은 **미관측**으로 적는다.
   🆕 2026-10-08: 결정 9 의 **보강 측정은 ② 샘플에 한해 끝났다**(설계 §8 3·4단계 — `P-VL` 2건, 증거
   `docs/broker-profiles/evidence/2026-10-08-cp3-venue-limits/`, PR #881). ⚠ 설계 §4.2 의 **① 샘플
   (08:50±3분, 확대 불가 창)은 없다** — 공유키 규칙이 같은 날 둘을 금지한다. 그래서 band **필드와 값**은
   모의에서 관측됐지만 **확대 단계는 판별되지 않았고**, 프로파일 band 축도 `OBSERVED_ON_MOCK` 가 아니라
   `L2_STAGE_RECORDED_ONLY` 다. 호가수량한도는 규정값으로 남는다. ⚠ 값 착지(§8 5단계 — tenant 트리 `max_quantity: 10000`)와 band 원천
   웨이브는 **여전히 미착수**이므로 이 항목의 「체결·영수증 미관측」은 그대로다. 부수로 배포
   `tick_size: 5` 가 mini 잎에 틀렸다는 **브로커 측 정황**이 나왔다(관측 band 가 0.02 격자에만 떨어진다).
5. **완료 증거**(계획 §3 CP-3) — 이관 artifact + digest, 데이터셋 lineage(커버리지 매니페스트), 판단/거부/
   위험 차이 보고서(의도된 차이 둘 + 미해결), 양방향·재시작·복구 증거. **PnL 동일성은 완료 조건이
   아니다**(TOS 가 못 낸다).
   **판단/거부/위험 차이 보고서 = B3 의 `summary.json`**(`<out>/summary.json`, §5 2): 버킷별·귀속별
   카운트, 레거시 outcome × TOS kind 행렬, 두 일치율(규칙 수준·포지션 모델 수준)과 정의,
   UNRESOLVED 봉 목록(상한 있음), 세 아티팩트의 선언된 차이 전부와 각각이 흡수한 봉 수, 그리고
   **체결·PnL 은 비교하지 않는다**는 `scope` 문단(B4 「체결 비교 포기」 — §3 B4 가 묻고 §4 결정 7
   이 처분한다; 실행당 주문 1 개 + 봉인된 성과 표면)과 **B1b-D7 의무 미이행** 기록. 아직 없는 것은
   데이터셋 lineage(커버리지 매니페스트) · §5 3 의 부팅 경로 · §5 4 의 paper 증거 **셋**이다.

범위 밖(명시): 커널·DSL 변경(GOV-001 절차), `Proposal.direction` 런타임 배선, 상주 코퍼스·설정 교체,
live·실전·증거금. 레거시 코드 삭제는 CP-4.

## 6. 이 문서가 바꾸지 않은 것

코드·설정·cron·호스트 스크립트 0 건. 상위 계획은 두 줄을 바꿨다 — 상태 줄(CP-1 「관측 대기」 → 관측됨,
남은 둘 명시)과 §4 의 「첫 tenant 전략 … 미정」 행. `docs/plans/INDEX.md` 는 같은 상태를 적는다. 독립
리뷰는 PR #874 에서 받았고 처분은 그 코멘트에 있다.
