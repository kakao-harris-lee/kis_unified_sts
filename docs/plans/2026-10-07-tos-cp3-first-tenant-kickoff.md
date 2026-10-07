# CP-3 착수 — 첫 paper tenant 후보 비교와 운영자 결정표 (2026-10-07)

상태: **조사 완료 · 운영자 승인 2026-10-07 · §5 1 (B1a) 착수** (2회차: #874 리뷰 처분 반영). 상위 계획은
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

구축물 넷(§4 결정 7 로 승인됨 — **B1a 착수·구현됨**(`tools/tos_cp3/`), B1b·B2·B3·B4 미착수).
⛔ **방화벽은 양방향이다**: `tos` 밖의 어떤
파일도 `tos`/`tos_runtime` 을 import 할 수 없고(`tools/tos_firewall_check.py` TOS-FW-R, `tools/` 도 검사
대상), `tos` 는 `shared.indicators` 는 되지만 `shared.backtest` 는 안 된다. 그래서 `Bar` 튜플을 만들거나
`BacktestDriver` 를 모는 코드는 **`tos/` 안**에만 둘 수 있다.

| # | 구축물 | 자리(방화벽 준수) | 왜 |
|---|---|---|---|
| B1a | Parquet → 봉별 **정수 필드 JSONL** 생산자(vwap·atr14·z·ATR p90·스톨·역전·세션 창; `shared/decision/setups/vwap_reversion.py` 의 산식과 봉별 일치를 테스트로 고정; lineage 기록 포함) | `tools/tos_cp3/`(레거시 쪽; `tos` import 0) | 양쪽이 **같은 산식**을 쓰게 — 아니면 비교가 밴드 수학을 잰다 |
| B1b | JSONL → `tuple[Bar,...]` 로더 + `BacktestDriver` 실행기 → trace JSONL | **`tos/runtime/`(또는 `tos/tests/backtest` 식 러너) 안**; 바깥과는 파일로만 만난다(`render_paper_config.py` 의 서브프로세스 경계와 같은 모양) | `Bar`·`BacktestDriver` 는 `tos.backtest` 타입 |
| B2 | 레거시 봉별 후보·거부 기록기 | `shared/backtest/` 하네스 래퍼 | `signals_writer` 가 no-op 이라 거부 사유가 없다 |
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
| 9 | **venue 수량 상한의 출처** | 오늘 paper 의 `venue_constraint_policy.yaml::max_quantity` 는 **null(의도된 fail-closed)** 이라 Proposal 이 전부 `STAGE_DENIED | venue quantity constraint incomplete` 다(10-07 세션 2,510건). 값이 들어오기 전까지 paper 단계는 **결정 수준 관측만** 가능하고 청산 규칙·영수증 증거는 못 만든다. 권고: 모의 계좌 **P0-2 식 GET 프로브**로 출처를 만들어 값을 넣는 것 — 실전 계좌·실주문은 영구 차단 | 값 없이 가면 §5 4 의 범위를 「체결 없음」으로 줄여 적는다 |

**운영자 승인 2026-10-07: 아홉 전부 권고대로.**

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
2. **B1b·B2·B3** — `tos/` 안의 러너가 JSONL 을 `Bar` 로 읽어 `BacktestDriver` trace 를 쓰고, 레거시
   하네스 래퍼가 봉별 후보·거부를 뽑고, `tools/tos_cp3/` 가 둘을 봉별로 diff 한다. 산출물:
   `reports/tos-cp3/<dataset>/{legacy,tos,diff}.jsonl` + 요약(일치율, 불일치 사유 분포). 불일치는
   **미해결로 남기되**, 결정 5·6 의 두 의도된 차이는 승인 근거와 함께 따로 센다.
3. **Setup D DSL 콘텐츠 + 부팅 경로** — `config/tos_runtime/<tenant>/strategies/setup_d_vwap_reversion.strategy.yaml`,
   `config/tos_runtime/<tenant>/strategy_bindings.yaml`(strategies/ 아래가 아니라 설정 루트), 예산 64 안
   (규칙 3개면 비교 ≤ 20). 렌더의 전략 파일 상수·다섯 digest 재도출·`safety_activation.yaml::members`
   갱신. LONG/SHORT 는 각각 렌더.
4. **paper 검증**(결정 3·4·8·9) — 방향별 data dir, 런북 §3 절차, 재시작·리플레이·콜드 백업 복원 drill
   증거. 결정 9 가 닫히기 전엔 체결·영수증(부분/중복/미지)이 없으므로 그 항목은 **미관측**으로 적는다.
5. **완료 증거**(계획 §3 CP-3) — 이관 artifact + digest, 데이터셋 lineage(커버리지 매니페스트), 판단/거부/
   위험 차이 보고서(의도된 차이 둘 + 미해결), 양방향·재시작·복구 증거. **PnL 동일성은 완료 조건이
   아니다**(TOS 가 못 낸다).

범위 밖(명시): 커널·DSL 변경(GOV-001 절차), `Proposal.direction` 런타임 배선, 상주 코퍼스·설정 교체,
live·실전·증거금. 레거시 코드 삭제는 CP-4.

## 6. 이 문서가 바꾸지 않은 것

코드·설정·cron·호스트 스크립트 0 건. 상위 계획은 두 줄을 바꿨다 — 상태 줄(CP-1 「관측 대기」 → 관측됨,
남은 둘 명시)과 §4 의 「첫 tenant 전략 … 미정」 행. `docs/plans/INDEX.md` 는 같은 상태를 적는다. 독립
리뷰는 PR #874 에서 받았고 처분은 그 코멘트에 있다.
