# Design Spec §3.2/§4.2 Risk Alignment Audit (2026-07-03)

**Status**: Completed read-only audit (Phase 2B). No code/config changes made.
**Source of truth checked**:
[../통합_투자_시스템_전략_설계서.md](../통합_투자_시스템_전략_설계서.md) §3.2/§4.2/§4.3,
[../plans/2026-07-02-unified-investment-system-roadmap.md](../plans/2026-07-02-unified-investment-system-roadmap.md) §5.1/§5.2,
그리고 HEAD 기준 현행 구현/설정:
`config/risk.yaml`, `config/kill_switch.yaml`, `config/risk_management.yaml`,
`config/stock_exit.yaml`, `config/futures_live.yaml`,
`config/strategies/{stock,futures}/*.yaml`, `shared/risk/**`,
`shared/strategy/{exit,position}/**`, `services/{stock_exit,risk_filter,order_router,kill_switch,trading}/**`.

이 문서는 감사 기록이다. 방향 결정은 로드맵(§5.1/§5.2)이 소유하며, 여기서는
규격 항목별 판정·수렴 경로·권고만 남긴다. 우선순위 규칙(로드맵 §0): 리스크
규칙 충돌 시 설계서 > 로드맵 > 자산별 로드맵, 단 CLAUDE.md 불변 규칙이 설계서보다
우선("일괄 EOD 청산 금지", "백테스트 근거 없는 완화 금지" 등).

## 감사 방법

- 설계서 §3.2(주식 5개 항목), §4.2+§4.3(선물 6개 항목) 총 11개 규격을 추출.
- 각 항목에 대해 현행 값/구현 위치(파일:라인 또는 YAML 키), 판정(일치/부분/부재),
  수렴 방법(config-only 가능 여부), 권고(수렴 vs 명시적 편차 유지)를 기록.
- **판정 원칙**: 현행이 설계서보다 보수적이면 "편차 유지"를 우선 검토. 백테스트
  근거 없이 규격 수치를 맞추려 파라미터를 완화하는 권고는 하지 않는다.
- 워킹트리의 타 레인 미커밋 변경은 무시하고 HEAD 기준으로 감사했다.

## 트랙 B — 주식 §3.2 (5개 항목)

현행 주식 런타임 청산은 decoupled M4-X `StockExitDaemon`이 **전 종목 단일**
`ThreeStageExit`(`config/stock_exit.yaml`)로 수행한다
(`services/stock_exit/main.py:56-62`에서 클래스가 고정 생성됨 — per-strategy exit는
"v1; follow-up"으로 명시된 미구현 상태). 전략 YAML의 exit 블록(`atr_dynamic`,
`chandelier_exit` 등)은 백테스트 엔진 경로에서 사용된다. 활성 전략(2026-07-03):
`momentum_breakout`, `pattern_pullback`, `williams_r`.

| # | 설계서 §3.2 규격 | 현행 값 / 구현 위치 | 판정 | 수렴 방법 | 권고 |
|---|---|---|---|---|---|
| B① | 손절 = 진입가 − 2.0×ATR(14), 최대 손실 −7% 캡 | 런타임(M4-X): 고정 −1.5% (`config/stock_exit.yaml:4` `stop_loss_pct: -0.015`; `shared/strategy/exit/three_stage.py:98`). ATR 미사용. 역량은 존재: `ATRDynamicExit`(`shared/strategy/exit/atr_dynamic.py:44-65` — `stop_atr_multiplier` + `max_loss_pct` 캡), 전략 YAML 백테스트 경로에는 이미 2.0×ATR(`config/strategies/stock/momentum_breakout.yaml:60-63`), −7% 하드스톱(`pattern_pullback.yaml:85-90` `hard_stop_pct: -0.07`) 존재 | **부분** (방식 상이; 손실 한도는 스펙 캡보다 훨씬 타이트) | 런타임 수렴은 **코드 필요** (M4-X가 ThreeStageExit 하드코딩 → per-strategy/타입 선택 배선). 백테스트 경로는 config-only (`atr_dynamic: stop_atr_multiplier: 2.0, max_loss_pct: 7.0`) | **당분간 편차 유지.** 현행 −1.5%는 −7% 캡 이내(건당 손실은 더 보수적, 대신 잦은 손절 — 트레이드오프는 백테스트 사안). ATR 방식 전환은 C3(per-strategy exit 배선) 티켓과 함께 evidence 게이트로 |
| B② | 1차 익절 = 진입가 + 2.0×ATR(14), 보유량 50% 청산 | **부재.** ThreeStageExit는 부분청산 없음(breakeven +1.5%/maximize +3% 전환은 전량 기준; `three_stage.py:101-107`). 프레임워크는 부분청산 지원: `ExitSignal.quantity`(`shared/models/signal.py:131`), 50% 분할청산 선례 `trix_golden_exit.py:50,434-436` | **부재** | **코드 필요** — three_stage 확장 또는 신규 스윙 exit generator + M4-X 배선 | Phase 2 후속 티켓(C3). 부분청산 상태 추적(1차 익절 여부)이 포지션 레코드에 필요하므로 설계 포함 |
| B③ | 트레일링 = 1차 익절 후 10일 최저가 이탈 시 잔량 청산 | **부재.** 현행 트레일링은 진입 후 최고가 대비 −3%(`config/stock_exit.yaml:7`) 또는 ATR-거리(`atr_dynamic.py:53-54`), chandelier는 highest-high−ATR(`chandelier_exit.py`). 10일 **최저가**(Donchian low) 기반 청산은 어느 exit에도 없음 | **부재** | **코드 필요** — 10일 저가 채널 계산 + B②의 부분청산 이후 상태와 연동 | Phase 2 후속 티켓(C3와 동일 티켓). 구조적 유의점: 스펙 §3.2는 멀티데이 스윙 프레임인데 현행 런타임 exit는 인트라데이 지향(time_cut 20분, EOD 15:15 + MAXIMIZE 예외 `config/stock_exit.yaml:10-13`) — 수렴 시 exit 전체 프레임 재설계가 됨 |
| B④ | 1회 리스크 = 트랙 B 자본의 1.0%, 수량 = 리스크액 ÷ (진입가−손절가) | 공식 자체는 `RiskBasedSizer`가 정확히 구현(`shared/strategy/position/sizers.py:215-228`, `risk_per_trade_pct` 기본 1.0). 그러나 **활성 3전략 모두 `fixed` 사이저**: williams_r 1M/최대2종목(`williams_r.yaml position:`), momentum_breakout 1M/최대2(`momentum_breakout.yaml:71-75`), pattern_pullback 25M/최대3(`pattern_pullback.yaml:95-102`). 참고: `risk.yaml:22 risk_stock.max_position_risk_pct: 0.02`(2%)는 8-필터 어디에서도 소비되지 않는 선언값 | **부분** (역량 존재, 활성 전략 미사용) | **config-only 가능** — 전략 YAML `position.type: risk_based` + `risk_per_trade_pct: 1.0`. 단 RiskBasedSizer는 %기반 stop hint(`signal.metadata.stop_loss_pct`)를 쓰므로 ATR 손절가와의 정합은 B① 수렴과 묶임 | 조건부 수렴 — 사이징 변경은 노출 프로파일을 바꾸므로(특히 pattern_pullback 25M→리스크 기반) **백테스트/paper 비교 근거 후** 적용. 즉시 무근거 전환 금지 |
| B⑤ | 진입 시 3가격(손절/1차익절/트레일링) 동시 확정, 진입 후 변경 금지 | **부재(설계상 편차).** ThreeStageExit는 의도적으로 동적 스탑 스테이트 머신(SURVIVAL→BREAKEVEN 본전 이동→MAXIMIZE 트레일링; `three_stage.py:7-16`). 반면 선물 Setup A/C는 진입 시 절대 stop/target 고정(`setup_target_exit.py:49-55`) — 스펙 ⑤의 철학은 선물 쪽에 이미 존재 | **부재** (의도적 편차) | 수렴하려면 exit 전면 교체(B②③과 동일 작업). "규칙의 사전 확정"으로 해석하면 B①~③ 수렴 시 자동 충족 | **명시적 편차 유지 기록.** 현행 동적 본전-확보는 주식 파이프라인의 확정 설계(CLAUDE.md "signal-driven exits"). B①~③ 수렴 티켓이 완료되면 재평가 |

## 트랙 C — 선물 §4.2+§4.3 (6개 항목)

배경: 현행 선물 1차 운용 경로는 **모놀리식 orchestrator (paper)**. decoupled
파이프라인(`risk_filter`/`order_router`/`kill_switch`)은 compose 프로파일 뒤에
있고 F-9 런북으로만 컷오버한다. 아래 "일치" 판정 중 kill_switch/필터 기반
항목에는 §"배선 관찰" 캐비앳이 적용된다.

| # | 설계서 규격 | 현행 값 / 구현 위치 | 판정 | 수렴 방법 | 권고 |
|---|---|---|---|---|---|
| C① | 1회 최대 리스크 = 트랙 C 자본의 1.5% | 공식 구현 존재: `FixedFractionalFuturesSizer`(`sizers.py:285-358`) + `risk.yaml:5,37 max_position_risk_pct: 0.015`. 그러나 **활성 Setup A/C는 `llm_adaptive` 사이저**(base 1계약, cap 1계약 + risk-score 티어 ×1.0/0.7/0.4/0.0; `setup_a_gap_reversion.yaml:123-141`) — 수량 캡 방식이며 리스크-분율 검증은 하지 않음. 1계약 최소 단위 특성상 소액 계좌에서는 stop거리×승수가 1.5%를 넘을 수 있는데 이를 막는 가드 없음 | **부분** | 진입 시 risk-fraction 가드(stop거리×승수/자본 > 1.5% → skip)는 **코드 필요**(llm_adaptive 옵션 또는 별도 필터). fixed_fractional로의 사이저 교체는 config-only지만 Phase 1.3 LLM 사이징 설계를 되돌리는 결정 | paper 단계에서는 현행 유지(1계약 하드캡 + `futures_live.yaml max_position_size_contracts: 1`은 단순하고 보수적). **라이브 승격 전** risk-fraction 가드 티켓(C6) 검토 |
| C② | 일일 손실 3% → 당일 매매 중단 | `config/kill_switch.yaml:32-34 daily_loss.limit_pct: 0.03`(트립 시 force-flatten + sentinel 파일 → `order_router`가 주문 차단, `services/order_router/main.py:150`) + `DailyMDDFilter`(`risk.yaml:3 daily_mdd_limit_pct: 0.03`, 09:00 KST daily reset `runtime_state.py:66-74`) | **일치** (sentinel은 수동 해제라 스펙보다 보수적) | — | 유지. 배선 관찰(하단) 확인만 |
| C③ | 주간 손실 7% → 시스템 재검증 (실매매 정지, 페이퍼 전환) | 한도 일치: `kill_switch.yaml:35-37 weekly_loss.limit_pct: 0.07` + `WeeklyMDDFilter`(`risk.yaml:4 weekly_mdd_limit_pct: 0.07`). 액션 갭: (a) "페이퍼 강등" 자동화 없음 — 트립 액션은 flatten+중단이며 live→paper 전환은 수동 플래그(`futures:live:suspended`, `futures_live.yaml`; 현재 live 자체가 `enabled: false`라 실질 무영향). (b) `weekly_pnl_krw` 리셋 로직 부재 — `runtime_state.py`에 `reset_daily`만 있고 주간 리셋 없음; Redis 키 24h idle TTL(`state.py:66`) 소멸에만 의존해 주간 윈도우가 캘린더/롤링 어느 쪽도 아님 | **부분** (한도 일치, 액션·윈도우 semantics 갭) | 페이퍼 강등: 현 단계(paper-only)에서는 **운영 절차 문서화**로 충분, 라이브 후 자동화는 코드. weekly 리셋 semantics는 **코드 필요**(C5) | 한도는 그대로 유지. C5(주간 윈도우 정의) 티켓 + 라이브 승격 게이트 문서에 "주간 7% 트립 시 수동 재검증 절차" 명시 |
| C④ | 연속 4패 → 2주간 포지션 사이즈 50% 축소 | **축소 액션은 이미 존재** — 로드맵 §5.2의 "현행은 연속 6패 중단만" 서술보다 실제 커버리지가 넓음: ① `ConsecutiveLossFilter` soft 4 → `size_multiplier=0.5`(`shared/risk/filters/consecutive_loss.py:94-99`; `risk.yaml:8 soft_threshold: 4`) → `order_router._resolve_quantity`가 적용(`order_router/main.py:84-95,228-236`); ② `FixedFractionalFuturesSizer.soft_reduce_threshold: 4` → `size//2`(`sizers.py:353-358`). 잔여 갭: (a) **"2주간" 지속성 부재** — 첫 승리로 카운터 리셋(`runtime_state.py:61-64`) 즉시 원복; (b) base 1계약에서는 floor-at-1로 실효 없음(`order_router/main.py:94-95`); (c) 모놀리식 경로에는 RiskFilterLayer 미배선. 추가로 hard 6 → 진입 거부 + kill_switch 6패 트립(`kill_switch.yaml:38-40`)은 스펙에 없는 더 보수적 상위 계층 | **부분** (축소 존재, 2주 지속성 부재) | 2주 지속성은 **코드 필요** — 예: 축소 만료 시각을 risk state에 기록(`size_reduction_until`)하고 필터/사이저가 참조. config-only 불가 | C2 티켓. hard 6 중단 계층은 스펙에 없어도 **유지**(더 보수적). 로드맵 §5.2의 갭 서술은 "축소 액션 부재"가 아니라 "**2주 지속성** 부재"로 정정 권고(로드맵 수정은 오케스트레이터 소유) |
| C⑤ | 월간 손실 15% → 당월 완전 중단 + 원인 분석 후 재개 (§4.3) | **부재.** 월간 PnL 추적 자체가 없음 — `RiskStateSnapshot`은 daily/weekly만(`shared/risk/state.py:29-31`), kill_switch 조건에 monthly 없음(`kill_switch/main.py:78-116`), 어떤 YAML에도 월간 한도 키 없음 | **부재** | **코드 필요** — RuntimeRiskState monthly 누적+월초 리셋 + kill_switch `monthly_loss` 조건(또는 MonthlyMDDFilter). 이후 한도값은 YAML | C1 티켓 (로드맵 §5.2 명시 항목). "당월 내내 중단" semantics(리셋 없는 월 단위 래치)가 기존 daily/weekly와 다르므로 설계 주의 |
| C⑥ | 분기 수익 인출·초기 증거금 리셋 (수동 절차, §4.3) | **부재.** `docs/runbooks/`에 해당 런북 없음(분기/인출/증거금 검색 무일치) | **부재** | **docs-only** — 런북 작성(코드 불필요). 로드맵 §5.2가 이미 "수동 운영 절차로 런북화" 지정 | D1: `docs/runbooks/futures-quarterly-margin-reset.md` 작성 (트리거 시점, 인출 계산식, Tier 2 주식 계좌 이체, 체크리스트) |

## 판정 요약

| 트랙 | 일치 | 부분 | 부재 | 계 |
|---|---|---|---|---|
| B (주식 §3.2) | 0 | 2 (B①, B④) | 3 (B②, B③, B⑤ — B⑤는 의도적 편차) | 5 |
| C (선물 §4.2+§4.3) | 1 (C②) | 3 (C①, C③, C④) | 2 (C⑤, C⑥) | 6 |

핵심 요지:

1. **선물 생존 규칙은 스펙에 근접** — 일 3%/주 7% 한도는 일치, 연속 4패 50% 축소도
   필터+사이저 양쪽에 이미 존재(로드맵의 갭 서술보다 좁음). 진짜 갭은 "2주 지속성",
   "월간 15% 래치", "주간 윈도우 리셋 semantics" 3가지.
2. **주식 §3.2은 구조적 편차** — 스펙은 ATR 기반 멀티데이 스윙 리스크 프레임(고정
   3가격 + 부분청산 + 10일 저가 트레일링)이고, 현행 런타임은 단일 ThreeStageExit
   동적 인트라데이 프레임. 개별 파라미터 조정이 아니라 per-strategy exit 배선 +
   신규 스윙 exit 구현이 수렴의 전제.
3. 현행이 스펙보다 보수적인 지점(주식 −1.5% 손절, 선물 1계약 캡, 연속 6패 하드
   중단)은 **백테스트 근거 없이 완화하지 않는다** — 전부 편차 유지 권고.

## Config-only 수렴 후보

즉시(무조건) 적용 가능한 항목은 **없다**. 조건부 후보:

| 후보 | 변경 | 조건 |
|---|---|---|
| B④ 주식 1% 리스크 사이징 | 활성 전략 YAML `position.type: fixed → risk_based` (`risk_per_trade_pct: 1.0`) | 노출 프로파일이 변하므로 백테스트/paper 비교 근거 필수. B①(ATR 손절)과 정합 필요 — stop hint 배선 확인 |
| B① 백테스트 경로 정렬 | 전략 exit YAML `atr_dynamic: stop_atr_multiplier: 2.0, max_loss_pct: 7.0` | 백테스트 전용(런타임 M4-X 미반영). 런타임 정렬은 C3 코드 티켓 선행 |
| C⑥ 분기 리셋 | 런북 문서 1건 (docs-only) | 없음 — 바로 작성 가능 (D1) |

## 코드 필요 항목 (Phase 2 후속 티켓 후보)

| ID | 항목 | 내용 | 근거 규격 |
|---|---|---|---|
| C1 | 선물 월간 15% 완전 중단 | `RuntimeRiskState`에 monthly 누적/월초 리셋 + kill_switch `monthly_loss` 조건(월 단위 래치 semantics). 한도는 YAML | §4.3 (로드맵 §5.2 명시) |
| C2 | 연속 4패 축소의 2주 지속성 | 축소 만료 시각을 risk state에 기록, `ConsecutiveLossFilter`/사이저가 만료 전까지 ×0.5 유지. 1계약 base에서의 실효성(floor-at-1) 정책도 함께 결정 | §4.2 (로드맵 §5.2 명시) |
| C3 | 주식 스윙 exit 규격 | 신규 exit generator(2×ATR 손절+−7% 캡 / 2×ATR 1차익절 50% 부분청산 / 10일 저가 트레일링) + M4-X per-strategy exit 선택 배선(`services/stock_exit/main.py` 하드코딩 해소) + 부분청산 상태의 포지션 레코드 반영 | §3.2 ①②③⑤ |
| C5 | 주간 PnL 윈도우 semantics | `weekly_pnl_krw` 리셋 규칙 정의(주초 리셋 or 롤링) — 현재는 24h idle TTL 소멸에만 의존 | §4.2 ③ 정확성 |
| C6 | (라이브 전) 선물 risk-fraction 가드 | 진입 시 stop거리×승수/자본 > 1.5%면 skip하는 가드 (llm_adaptive 옵션 또는 필터) | §4.2 ① |
| D1 | 분기 인출/증거금 리셋 런북 | docs-only | §4.3 |

## 배선 관찰 (판정 외 — 별도 확인 권고)

1. **kill_switch 스냅샷 조건의 데이터 공급이 decoupled 파이프라인 전제**:
   `risk:state:futures`는 decoupled `order_router`만 기록한다
   (`services/order_router/main.py:463-481`; 모놀리식 `services/trading/`에는
   RuntimeRiskState/`risk:state` 기록 코드가 없음). 또한 kill_switch 모니터
   서비스 자체가 `futures-killswitch` compose 프로파일 뒤에 있다
   (`docker-compose.yml:346-350`) — 모놀리식 orchestrator는 트립 이벤트
   **소비자**만 내장(`orchestrator.py:4554`). 즉 현행 모놀리식 paper 운용에서
   일 3%/주 7%/연속 6패 kill 조건은 평가되지 않고 있을 가능성이 높으며,
   운용 중인 일일 가드는 `RiskManager`(`config/risk_management.yaml:12`
   `daily_loss_limit_pct` 기본 **5.0%** — kill_switch의 3%보다 느슨)다.
   C② "일치" 판정은 config·decoupled 경로 기준임을 유의. F-9 컷오버 전까지의
   커버리지 정책(모놀리식에 3% 가드를 맞출지, 컷오버를 앞당길지)은 별도 결정 필요.
2. **`risk_stock.max_position_risk_pct: 0.02`(`risk.yaml:22`)는 미소비 선언값** —
   8-필터 어디에서도 읽지 않는다. B④ 수렴 시 스펙 1%와 함께 정리 대상.
3. **주식 EOD 15:15 청산**(`stock_exit.yaml:11-13`, MAXIMIZE만 예외)은 CLAUDE.md의
   "blanket EOD liquidation 금지" 원칙과 긴장 관계 — 본 감사 범위 밖이나 B③/C3
   스윙 exit 재설계 시 함께 재검토할 것.
