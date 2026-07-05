# ATR 단일-진실-소스(SoT) 통합 계획

- 작성일: 2026-07-05
- 배경: 지표 전수 감사(2026-07-05)의 발견 #3 — ATR이 7곳에 divergent 구현.
- 선행: [indicator-m2-handoff](2026-07-04-indicator-m2-handoff.md)(RSI/ADX SoT 수렴 선례),
  메모리 [[indicator-audit-2026-07-05]].
- 규율: RSI(#565)·ADX(#562)와 동일하게, **값이 바뀌는 소비자 이관은 백테스트 게이트 뒤**에서만 main 머지.

## 문제 — ATR 7중 발산

TR 공식(`max(H-L, |H-Cp|, |L-Cp|)`)은 7개 전부 일치하나, **스무딩·정규화·warmup·입력타입**이 갈린다.

| # | 구현 | 위치 | 스무딩 | 정규화 | warmup fallback | 입력 |
|---|---|---|---|---|---|---|
| 1 | reference ADX-internal | `reference.py::_dmi_frame`(`wilder_rma`) | **Wilder RMA** | raw | NaN | np |
| 2 | technical `_calc_atr` | `shared/indicators/technical.py:219` | SMA | raw | **mean(H−L)** ⚠️ TR gap항 누락 | streaming deque |
| 3 | llm `calc_atr_pct` | `shared/llm/stock_screening.py:106` | SMA | **fraction** (atr/close) | 0.0 | pd(한글 컬럼) |
| 4 | llm `_calc_atr_pct` | `shared/llm/unified_trading_analyzer.py:161` | →#3 위임 | →#3 | →#3 | →#3 |
| 5 | trix `_calc_atr_pct` | `shared/strategy/entry/trix_golden.py:461` | SMA | **fraction** | 0.0 | pd(영문 컬럼) |
| 6 | runtime `_calc_atr_raw` | `services/trading/indicator_calculations.py:200` | SMA | raw | 0.0 | Candle list |
| 6b | runtime `_calc_atr_normalized` | `services/trading/indicator_calculations.py:212` | SMA | **fraction** (atr/(close+1e-10)) | 0.0 | Candle list |
| 7 | regime `_calc_atr` | `shared/regime/adaptive_detector.py:422` | SMA | raw | **mean(tr)** 부분평균 | np |

### 핵심 리스크
1. **스무딩 분열**: standalone 소비자 6곳 전부 **SMA-of-TR**, ADX-internal만 **Wilder RMA**. 실데이터(005930)에서 **24.4% 차**(SMA 207.14 vs Wilder 257.77). canonical standalone ATR 부재 → 누가 "reference에 맞춰" Wilder로 고치면 모든 `stop_atr_mult × ATR`·트레일링·`atr_pct` 필터가 동시에 24% 이동(RSI/ADX와 같은 함정).
2. **정규화 함정**: `calc_atr_pct`/`_calc_atr_pct`는 이름은 "pct"인데 **fraction(atr/close)** 반환 → percent 기대 호출부는 100× 오차.
3. **warmup 결함**: #2는 TR 대신 `mean(H−L)`(갭 항 누락 → 갭/개장바에서 과소), #7은 `mean(tr)` 부분평균.

## 목표 — canonical `ATRCalculator` (reference.py)

Bollinger의 `ddof` 노브 선례를 따라, **SMA/Wilder 선택을 명시 노브로** 만든 단일 계산기. `mode="sma"`가 repo standalone 관례(6곳)와 동일, `mode="wilder"`가 ADX-internal과 동일.

```python
ATRCalculator(period=14, mode="sma"|"wilder")
  .true_range(high, low, close)      # max-of-3, 바 1..n-1, causal
  .atr_series(high, low, close)      # 길이 n, NaN warmup
  .atr_last(high, low, close)        # 스칼라 (None if 부족)
  .atr_fraction_last(...)            # atr/close 명시 fraction (pct 함정 회피)
  .calculate(df, ...)                # 'atr' 컬럼 (LookaheadGuard 지원)
```

### Phase 0 — additive (본 PR, 게이트 불필요)
`ATRCalculator`를 `shared/indicators/reference.py`에 **순수 additive**로 추가(M2-A ADX/Bollinger/StochRSI 선례와 동일 — 아무 소비자도 재배선 안 함 → 값 변화 0 → 안전). 테스트로 다음을 고정:
- `mode="sma"` == 런타임 `_calc_atr_raw`(1e-9) → **값-보존 drop-in 증명**
- `mode="wilder"` == `wilder_rma(TR)` → ADX-internal과 동일
- 두 모드 발산 / TR=max-of-3 / NaN warmup / fraction 헬퍼 / 잘못된 mode 거부

## 소비자 이관 계획 (Phase 1~2, 게이트 대기)

### Phase 1 — 값-보존 통합 (parity 게이트)
6개 standalone 소비자를 `ATRCalculator(mode="sma")` 위임으로 교체하되 **각자의 정규화·입력 어댑터를 보존**해 값이 안 바뀌게 한다. `_calc_rsi`(#561)/VR RSI(#565)와 동일 패턴. 각 이관은 **parity 테스트(before==after)** 필수.

**Phase 1a — DONE (값-보존 확정)**: 아래 4개 stateless 소비자 이관 완료. 단위 parity 1e-9 + 실증 1e-17 + trix_golden 백테스트(035720, 2026-03~06) before==after **bit-identical**(5거래/-26,048원/Sharpe -17.09 동일). `unified_trading_analyzer._calc_atr_pct`는 #3 위임이라 자동 포함.

| 소비자 | 위임 형태 | 보존할 계약 | 상태 |
|---|---|---|---|
| runtime `_calc_atr_raw`(6) | `atr_last(mode=sma)`, None→0.0 | raw, <period+1→0.0 | ✅ 1a |
| runtime `_calc_atr_normalized`(6b) | `_calc_atr_raw`/(close+1e-10) | atr/(close+1e-10) | ✅ 1a |
| llm `calc_atr_pct`(3) | 한글컬럼 어댑터→`atr_fraction_last` | fraction | ✅ 1a |
| trix `_calc_atr_pct`(5) | 영문컬럼 어댑터→`atr_fraction_last` | fraction | ✅ 1a (#3와 동일 로직) |

**Phase 1b — regime DONE, technical은 dead code로 판정**:

| 소비자 | 위임 형태 | 결과 |
|---|---|---|
| regime `_calc_atr`(7) | `atr_last(mode=sma)`, None→0.0 | ✅ **완료**. detector가 `len(df) >= min_bars(50) > period+1`로 게이트하므로 옛 `mean(tr)` warmup 분기는 **도달 불가** → steady-state 값-보존(parity 1e-9). regime **dormant**([[indicator-audit-2026-07-05]]). |
| technical `_calc_atr`(2) | — | ⛔ **dead code (미이관)**. `shared/indicators/technical.py::TechnicalCalculator`는 `__init__` re-export + docstring 예제에서만 언급, **실 import·인스턴스화·테스트 전무**. trend/engine이 쓰는 건 동명의 별도 `shared/trend/technical_calculator.py`(Wilder ATR)이고 그 TrendEngine조차 live 서비스 미사용. → ATR SoT 대상 아님. 별도 dead-code 검토(제거 후보). |

Phase 1 정리: 활성 standalone ATR 5개(6/6b/3/5=1a, 7=1b) 전부 canonical 위임 완료. 남은 divergence는 dead #2와 `shared/trend/technical_calculator`(Wilder, TrendEngine 미가동)뿐.

- **정규화 함정 정리**: `*_pct` 이름이 fraction을 반환하는 3·5는 이관 시 로직이 canonical(`atr_fraction_last`)로 통일됨. 리네이밍은 호출부 광범위라 보류(현행 유지).

### Phase 2 — Wilder 전환 (평가 완료 2026-07-05 → KEEP SMA 권고)
standalone ATR을 `mode="wilder"`로 전환해 ADX-internal과 일치시킬지 실 데이터로 평가.

**교정: "~24% 이동"은 과장된 단일-지점 아티팩트였음.** 감사의 24%는 005930 전체 200바 한 지점 측정. 실 데이터 trailing 60바 윈도우(다중 심볼·다중 지점)로 재측정한 **Wilder/SMA ATR 비율**:

| 자산 | 평균 | 중앙값 | p10–p90 | Wilder vs SMA |
|---|---|---|---|---|
| stock-daily (120심볼, 2828표본) | 1.008 | 0.996 | 0.86–1.15 | +0.8% |
| stock-minute (40심볼, 9380표본) | 1.051 | 1.011 | 0.91–1.15 | +5.1% |
| futures-minute (16심볼, 4783표본) | 1.099 | 1.016 | 0.87–1.26 | +9.9% |

**Head-to-head 백테스트**(trix_golden, 4심볼): SMA vs Wilder **완전 동일**(trades/PnL 불변) — trix의 `max_atr_pct: 0.008`(0.8%) 필터 임계가 실제 주식 atr_pct(~0.1%)보다 훨씬 커서 양쪽 다 필터 미발동.

**권고: `mode="sma"` 유지.** 근거: (a) 실 divergence 작음(~1-10%, 24% 아님), (b) SMA는 모든 백테스트·임계값이 보정된 검증된 status quo, (c) trix A/B 영향 0, (d) 전환 시 모든 ATR-stop 전략(Setup A/C)을 futures 게이트로 재검증해야 하나 이득 미입증. Phase 1 consolidation으로 **divergence 리스크는 이미 제거**됐고, `mode="wilder"` 노브는 향후 특정 전략(예: Setup A/C stop을 ADX-consistent ATR로 튜닝) 평가용으로 남겨둠. 재현: `scripts/analysis/`(ATR 비율 probe는 인라인).

## 진행 상태 (2026-07-05)
- **Phase 0** (canonical `ATRCalculator`) — ✅ #567.
- **Phase 1a** (runtime raw/normalized, llm, trix) — ✅ #568 (값-보존, 백테스트 bit-identical).
- **Phase 1b** (regime `_calc_atr`) — ✅ #569 (값-보존). technical `_calc_atr`은 dead code로 판정(미이관).
- **Phase 2** (Wilder 전환) — ✅ **평가 완료 → KEEP SMA 권고** (divergence ~1-10%, trix A/B 영향 0). 전환 안 함.
- 남은 divergence: dead technical `_calc_atr`(별도 dead-code 검토) + `shared/trend/technical_calculator`(Wilder, TrendEngine 미가동).

## 담당
- (Phase 1은 값-보존이라 일반 리뷰로 충분, 백테스트로 재확인 완료. Phase 2는 평가 후 status quo 유지.)

## 검증 스냅샷 (main, Phase 0)
`pytest tests/unit/indicators/test_reference.py -k atr` 그린(8 pass). `mode="sma"`가 런타임 `_calc_atr_raw`와 1e-9 일치, `mode="wilder"`가 `wilder_rma(TR)`와 일치. ruff/black/mypy 신규 에러 0. 소비자 재배선 없음 → 라이브 동작 불변.
