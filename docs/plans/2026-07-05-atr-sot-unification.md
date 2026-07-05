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

| 소비자 | 위임 형태 | 보존할 계약 | 부수 개선 |
|---|---|---|---|
| runtime `_calc_atr_raw`(6) | `atr_last(mode=sma)`, None→0.0 | raw, <period+1→0.0 | — |
| runtime `_calc_atr_normalized`(6b) | `atr_fraction_last`, None→0.0 | atr/(close+1e-10) | 1e-10 vs None 처리 정렬 |
| regime `_calc_atr`(7) | `atr_last(mode=sma)`, None→0.0 | raw | **warmup mean(tr)→정식 SMA/None** (regime dormant, [[indicator-audit-2026-07-05]]) |
| technical `_calc_atr`(2) | deque→arrays 어댑터, `atr_last` | raw | **warmup mean(H−L)→TR 기반** (갭 정확) |
| llm `calc_atr_pct`(3) | 한글컬럼 어댑터→`atr_fraction_last` | fraction | 이름 유지(호출부 광범위) 또는 `*_fraction` 리네이밍 검토 |
| trix `_calc_atr_pct`(5) | 영문컬럼 어댑터→`atr_fraction_last` | fraction | #3와 DRY 통합 |

- **게이트**: 각 소비자 이관 브랜치는 parity 테스트가 before==after(1e-9)를 증명하면 통과. warmup을 실제로 바꾸는 #2/#7은 해당 소비 전략(technical=trend engine, regime=dormant) 영향 범위 확인 + 필요 시 백테스트.
- **정규화 함정 정리**: `*_pct` 이름이 fraction을 반환하는 3·5는 호출부가 fraction을 전제하는지 grep 확인 후, 이름 유지(안전) 또는 `atr_fraction`으로 리네이밍(명확). 호출부 단위 검증 필요.

### Phase 2 — Wilder 전환 (전체 백테스트 게이트, 선택)
standalone ATR을 `mode="wilder"`로 전환해 ADX-internal과 완전 일치시킬지 결정. **라이브 stop distance ~24% 이동** → 시장데이터 백테스트 필수(Sharpe/MDD/승률/거래수 델타). 계산은 이미 canonical이므로 되돌리기보다 `stop_atr_mult` 등 **임계값 재튜닝**이 정석(ADX 게이트 B와 동일 논리, [indicator-m2-handoff](2026-07-04-indicator-m2-handoff.md)). 통과 못 하면 `mode="sma"` 유지.

## 서버에서 이어서 (게이트 실행)
사전조건: Parquet 시장데이터 + Redis DB1 + `pip install -e ".[dev]"`.
1. Phase 1: 소비자별 이관 브랜치 + parity 테스트 → 각각 독립 머지.
2. Phase 2(선택): sma vs wilder head-to-head 백테스트 → 통과 시에만 wilder + 임계값 재튜닝.

## 담당
- backtest-engineer: Phase 2 sma/wilder head-to-head.
- (Phase 1은 값-보존이라 일반 리뷰로 충분, 백테스트 불요.)

## 검증 스냅샷 (main, Phase 0)
`pytest tests/unit/indicators/test_reference.py -k atr` 그린(8 pass). `mode="sma"`가 런타임 `_calc_atr_raw`와 1e-9 일치, `mode="wilder"`가 `wilder_rma(TR)`와 일치. ruff/black/mypy 신규 에러 0. 소비자 재배선 없음 → 라이브 동작 불변.
