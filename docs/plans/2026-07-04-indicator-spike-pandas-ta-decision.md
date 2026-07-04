# M1 Spike — pandas-ta 채택 결정 (batch/reference 레이어)

- 날짜: 2026-07-04
- 성격: 순수 평가/의사결정 스파이크 (프로덕션 코드·`pyproject.toml` 미수정)
- 관련 계획: §2.5 "지표 통합/커버리지" — pandas-ta를 batch/참조 레이어로 채택, 런타임
  incremental 핫패스는 유지 + parity pin
- 재현 아티팩트: `scratchpad/compare_values.py`, `scratchpad/bench_speed.py`
  (격리 venv, 레포·전역 미변경)

## TL;DR (결정)

- **채택 권고: 예.** `pandas-ta-classic`(xgboosted 유지보수 포크)를 **batch/reference·
  backtest 전용** 레이어로 채택한다. 런타임 incremental 핫패스(`services/trading/
  indicator_calculations.py`, `shared/indicators/*`)는 **그대로 유지**하고 parity pin으로
  대조한다.
- **추천 포크 1개: `pandas-ta-classic` 0.6.52** (2026-06-24 릴리스, MIT, numpy≥2.0 /
  pandas≥2.0, Python≥3.10, numba 선택 가속). 원본 `pandas-ta`는 2026-07-01 아카이브
  예고 상태라 배제.
- **값 대조 결론(표준 = pandas-ta):**
  - RSI → `shared.indicators.momentum.RSICalculator`(Wilder)가 표준과 **일치**.
    런타임 `_calc_rsi`(rolling-SMA)는 **불일치**(≈4.6pt 차이, Cutler 변형).
  - ADX → 런타임 `_calc_adx`(Wilder)가 표준과 **일치**.
  - Bollinger → 런타임 `_calc_bb`(sample std, ddof=1)는 pandas-ta를 **ddof=1로 맞출
    때만 일치**. 업계/TA-Lib/pandas-ta **기본값은 population std(ddof=0)** 이므로
    규약 불일치가 존재 → **WS2-d 게이트 항목**.
- **Tier2 커버(실제 import 확인): 6/6 전부 존재** — SuperTrend, Donchian, Keltner,
  Parabolic SAR, ROC, Momentum.
- **배치 속도(100K 행 ≈ 1년치 1분봉, numba 없이): RSI 1.83ms / ADX 34.1ms /
  BB 3.54ms, 3종 합 39.5ms, 8종 패널 104ms.** TA-Lib 없이도 백테스트 스케일에서
  충분히 수용 가능.

## 1. 포크 선정

원본 `pandas-ta`(twopirllc)는 유지보수 지속 불가로 **2026-07-01 아카이브 예고**
상태다. 유지보수 포크 3종을 조사했다.

| 후보 | 최신 버전 / 릴리스일 | Python | numpy / pandas | 라이선스 | 유지보수 상태 |
|---|---|---|---|---|---|
| **pandas-ta-classic** (xgboosted) | **0.6.52 / 2026-06-24** | ≥3.10 | numpy≥2.0, pandas≥2.0 | MIT | **활발** — 2025-08~2026-06 월 단위 릴리스, numba 선택 가속 |
| pandas-ta-openbb (OpenBB) | 0.4.24 / 2026-03-27 | ≥3.10 (3.10–3.14) | numpy 2 호환 | MIT | 활발하나 원본 코드 기반 + 원본 아카이브 리스크 승계 |
| pandas-ta-remake | 1.0.4 / 2025-01-12 | ≥3.11 | 미명시 | MIT | **정체** — 2025-01 이후 릴리스 없음 |

**추천: `pandas-ta-classic` 0.6.52.**

- 셋 중 **가장 최신**(스파이크 시점 기준 ~10일 전 릴리스)이고 릴리스 케이던스가 실제로
  살아있음.
- numpy 2.x / pandas 2.x 명시 지원(설치 시 numpy 2.5.0 / pandas 3.0.3 해석됨).
- MIT 라이선스, 의존성 footprint가 가벼움(`numpy, pandas, python-dateutil, six`),
  `numba`는 `[performance]` 선택 extra(numpy loop 6–230× 가속, 채택 필수 아님).
- 224+ 지표 + 62 캔들패턴, Tier2 지표 전부 네이티브 포함.
- pandas-ta-openbb는 원본을 얇게 감싼 배포라 원본 아카이브의 코드 정체 리스크를
  그대로 승계. pandas-ta-remake는 1년 넘게 정체 → 둘 다 배제.

## 2. 격리 설치 (레포·전역 미변경)

```bash
SCRATCH=".../scratchpad"
/Users/harris/.pyenv/versions/3.12.0/bin/python -m venv "$SCRATCH/ptaenv"
"$SCRATCH/ptaenv/bin/python" -m pip install "pandas-ta-classic"
# 해석 결과: numpy 2.5.0, pandas 3.0.3, pandas-ta-classic 0.6.52
```

레포 `pyproject.toml`·환경 전역 패키지는 건드리지 않았다. 모든 계산은 이 격리 venv에서
수행했다.

## 3. 값 대조 (pandas-ta = 업계 표준 기준)

결정론적 OHLCV(`np.random.default_rng(42)`, 500 bars)로 최종 bar 값을 대조.
레포 코드는 **파일 경로 기준 read-only import**로 로드(패키지 `__init__` 부작용 회피),
수정 없음. 재현: `ptaenv/bin/python scratchpad/compare_values.py`.

| 지표 | 레포 구현 | 규약 | vs pandas-ta 기본 | 판정 |
|---|---|---|---|---|
| RSI(14) | `shared.indicators.momentum.RSICalculator` | Wilder RMA (`ewm α=1/14`) | Δ=1.4e-14 | **일치 (표준)** |
| RSI(14) | 런타임 `_calc_rsi` | rolling-SMA (Cutler 변형) | Δ≈4.60 (33.32 vs 37.92) | **불일치** |
| ADX(14) | 런타임 `_calc_adx` | Wilder smoothing | Δ=7.1e-15 | **일치 (표준)** |
| BB(20,2) | 런타임 `_calc_bb` | sample std (ddof=1) | Δ≈0.046 (vs ddof=0 기본) | **규약 불일치** |
| BB(20,2) | 런타임 `_calc_bb` | sample std (ddof=1) | Δ=0.0 (vs ddof=1 명시) | 일치 (ddof 맞출 때) |

측정 수치(최종 bar):

```
RSI(14):
  pandas-ta rsi (Wilder RMA)         = 37.924181
  shared RSICalculator (Wilder)      = 37.924181   MATCH  (Δ=1.4e-14)
  runtime _calc_rsi (rolling-SMA)    = 33.320943   DIFFER (Δ=4.60)

ADX(14):
  pandas-ta adx (Wilder)             = 21.454314
  runtime _calc_adx (Wilder)         = 21.454314   MATCH  (Δ=7.1e-15)

Bollinger(20,2) lower/upper:
  pandas-ta ddof=0 (population, 기본) = 96.160253 / 99.718947
  pandas-ta ddof=1 (sample)          = 96.114028 / 99.765171
  runtime _calc_bb (ddof=1 sample)   = 96.114028 / 99.765171
    vs pandas-ta 기본(ddof=0): DIFFER (Δ=0.046)
    vs pandas-ta ddof=1:       MATCH  (Δ=0.0)
```

**해석**

- **RSI:** `shared` 쪽 `RSICalculator`가 Wilder = 업계/TA-Lib/pandas-ta 표준과 정확히
  정합. 반면 런타임 핫패스 `_calc_rsi`는 gains/losses의 단순 평균(rolling-SMA, Cutler
  변형)이라 값이 다르다. 백테스트(batch)를 pandas-ta로 돌리고 런타임을 `_calc_rsi`로
  돌리면 **동일 심볼에서 RSI가 수 포인트 갈린다** → 임계값 기반 시그널이 어긋날 수 있음.
  런타임을 그대로 유지하는 방침이면 **parity pin 대상은 pandas-ta(Wilder)가 아니라
  `_calc_rsi`(rolling-SMA)** 임을 명시해야 하고, batch/reference도 RSI만은 Wilder와
  rolling-SMA 중 어느 규약을 정본으로 쓸지 WS2-d에서 확정해야 한다. (권고: 표준 Wilder로
  통일하고 런타임 `_calc_rsi`를 Wilder로 정렬하는 후속 티켓 — 단, 프로덕션 변경이라 이
  스파이크 범위 밖.)
- **ADX:** 런타임 `_calc_adx`는 이미 표준 Wilder와 완전 일치 → parity 리스크 없음.
- **Bollinger:** 런타임 `_calc_bb`의 sample std(ddof=1)는 Polars `rolling_std` 기본을
  맞추려는 의도적 선택이나, **Bollinger 원전·TA-Lib·pandas-ta 기본은 population
  std(ddof=0)** 이다. reference 레이어에서 pandas-ta `bbands`를 쓸 때는 **`ddof=1`을
  명시**해 런타임과 일치시키거나, 반대로 런타임을 표준 ddof=0으로 옮길지 WS2-d 게이트에서
  결정해야 한다. 이 한 줄 규약이 밴드 폭을 ~0.05(20-bar, σ≈0.9 샘플에서 ~0.05%) 흔든다.

## 4. Tier2 커버 확인 (실제 import 실행)

`ptaenv/bin/python`에서 각 함수를 결정론적 OHLCV(300 bars)로 실제 호출해 출력 컬럼까지
확인. 6종 전부 존재/정상 계산.

| Tier2 지표 | 함수 | 출력 컬럼(예) | 판정 |
|---|---|---|---|
| SuperTrend | `ta.supertrend(h,l,c,10,3.0)` | `SUPERT_10_3.0`, `SUPERTd_10_3.0`, `SUPERTl_…`, `SUPERTs_…` | OK |
| Donchian | `ta.donchian(h,l,20,20)` | `DCL_20_20`, `DCM_20_20`, `DCU_20_20` | OK |
| Keltner | `ta.kc(h,l,c,20)` | `KCLe_20_2`, `KCBe_20_2`, `KCUe_20_2` | OK |
| Parabolic SAR | `ta.psar(h,l,c)` | `PSARl_…`, `PSARs_…`, `PSARaf_…`, `PSARr_…` | OK |
| ROC | `ta.roc(c,10)` | `ROC_10` | OK |
| Momentum | `ta.mom(c,10)` | `MOM_10` | OK |

전체 노출 지표/유틸: 427종(`dir()` 기준). SuperTrend·PSAR 등 loop 지표는 numba 설치 시
가속(선택).

## 5. 배치 속도 측정 (TA-Lib 없이)

100,000 행(≈1년치 1분봉) 단일 시계열, best-of-N, warmup 1회, numba 미설치.
재현: `ptaenv/bin/python scratchpad/bench_speed.py`.

| 계산 | 시간 (100K 행) |
|---|---|
| RSI(14) | 1.83 ms |
| ADX(14) | 34.13 ms |
| BBands(20, 2) | 3.54 ms |
| **RSI+ADX+BB 합** | **39.50 ms** |
| 8종 패널(RSI/ADX/BB/MACD/Stoch/WillR/CCI/ATR) | 104.46 ms |

환경: numpy 2.5.0, pandas 3.0.3, pandas-ta-classic 0.6.52, Python 3.12.0 (macOS/arm64).

**판정: 수용.** 백테스트 1회 지표 프리컴퓨트가 심볼당 100K 행에서 8종 100ms 수준.
Optuna 수백~수천 trial에서도 지표 계산은 병목이 아니며(데이터 로드/시뮬 루프가 지배),
필요 시 `[performance]` extra(numba)로 loop 지표를 추가 가속 가능. TA-Lib(C 확장)
빌드 의존 없이 이 성능을 얻는 게 채택 근거.

## 6. 채택 경계 (Scope)

- **채택: batch / reference / backtest 전용.** 지표 정의의 "정본(reference)" 및
  백테스트 feature-build에서 pandas-ta-classic 사용.
- **제외: 런타임 incremental 핫패스.** `services/trading/indicator_calculations.py`,
  `shared/indicators/*`의 스트리밍/증분 경로는 **변경 없이 유지**. pandas-ta는 전체
  시리즈 재계산형이라 tick 단위 증분 핫패스에는 부적합.
- **parity pin:** 런타임 핫패스와 reference 사이 값 규약을 고정. 핵심 pin 포인트:
  - RSI: 런타임 `_calc_rsi`(rolling-SMA) ↔ reference(Wilder) **불일치**를 명시적으로
    문서화하고, 게이트/시그널이 두 규약을 혼용하지 않도록 정본을 하나로 확정(WS2-d).
  - BB: reference에서 `ddof=1` 명시로 런타임 `_calc_bb`와 정합.
  - ADX: 이미 일치, pin 불필요(회귀 테스트만).
- 설치 형태: **선택 extra**(`indicators-ref` 또는 `backtest`)로 격리해 런타임/핫패스
  기본 설치 footprint에 영향 없도록 한다.

## 7. 리스크

| 리스크 | 영향 | 완화 |
|---|---|---|
| **값 규약 차이 (RSI SMA vs Wilder, BB ddof)** | 백테스트↔런타임 시그널 불일치 | **WS2-d 게이트**: 정본 규약 확정 + parity 테스트(런타임 vs reference 허용오차 assert). RSI는 특히 4.6pt까지 벌어짐 |
| **포크 정체 리스크** | 원본 아카이브 예고, 포크 유지보수 지속 불확실 | **버전 고정**(`==0.6.52`), 필요 지표만 사용, 자체 회귀 테스트로 upstream 회귀 조기 탐지. 최악의 경우 필요한 소수 지표만 vendored |
| **numpy 2.x 강제** | pandas-ta-classic이 numpy≥2.0 요구. 레포 현재 pin은 `numpy>=1.26`(1.x 허용) | 채택 전 `shared/**`·`services/**`의 numpy 2.x 호환 확인(별도 WS2 게이트). 하한을 `numpy>=2.0`로 올리는 결정 필요 |
| **pandas 3.x 드리프트** | 포크가 pandas≥2.0 허용 → 미고정 시 fresh install이 pandas 3.0으로 해석(레포는 3.0 미검증) | reference 채택과 별개로 레포 pandas에 상한(`pandas<3`) 검토, 또는 포크를 격리 extra로 두고 CI에서 레포 실제 pandas와 함께 해석 검증 |
| **컬럼 네이밍 규약 (`SUPERT_10_3.0` 등)** | 다운스트림에서 파라미터 인코딩된 컬럼명 파싱 필요 | reference 어댑터에서 표준 컬럼명으로 정규화 |

## 8. 제안 diff (미적용 — 다른 브랜치가 `pyproject.toml` 수정 중)

런타임/핫패스 기본 설치에 영향을 주지 않도록 **선택 extra**로 격리한다. 아래는 제안일
뿐 적용하지 않음.

```diff
 [project.optional-dependencies]
+# 지표 reference / batch backtest 전용 레이어 (런타임 incremental 핫패스 제외).
+# 원본 pandas-ta는 2026-07 아카이브 예고 → 유지보수 포크 pandas-ta-classic 고정.
+indicators-ref = [
+    "pandas-ta-classic==0.6.52",  # numpy>=2.0, pandas>=2.0, MIT
+    # 선택 가속(loop 지표 SuperTrend/PSAR 등 6-230x): 필요 시 numba 추가
+    # "numba>=0.58.0",
+]
 dev = [
     ...
+    "pandas-ta-classic==0.6.52",  # backtest/reference parity 테스트용
 ]
```

동반 검토 필요(별도 결정, 이 스파이크 범위 밖):

```diff
-    "numpy>=1.26",
+    "numpy>=2.0",          # pandas-ta-classic 요구; shared/services numpy 2.x 호환 확인 후
-    "pandas>=2.1",
+    "pandas>=2.1,<3.0",    # pandas 3.0 미검증 → 상한 고려(reference 격리 시 선택)
```

## 9. 재현 명령

```bash
# 1) 격리 venv
PY=/Users/harris/.pyenv/versions/3.12.0/bin/python
$PY -m venv scratchpad/ptaenv
scratchpad/ptaenv/bin/python -m pip install "pandas-ta-classic"

# 2) 값 대조 (레포 hand-roll vs pandas-ta)
scratchpad/ptaenv/bin/python scratchpad/compare_values.py

# 3) Tier2 커버 + 배치 속도
scratchpad/ptaenv/bin/python scratchpad/bench_speed.py
```

## 10. 후속 작업 (WS2)

1. **WS2-d 규약 게이트:** 지표별 정본 규약 확정(RSI Wilder vs SMA, BB ddof) +
   런타임↔reference parity 테스트(허용오차 assert).
2. numpy 2.x 호환 스윕(`shared/**`, `services/**`) 후 `numpy>=2.0` 승격 결정.
3. reference 어댑터: pandas-ta 컬럼명 → 레포 표준 컬럼명 정규화 레이어.
4. RSI 정본을 표준 Wilder로 통일하는 후속 티켓(런타임 `_calc_rsi` 정렬, 프로덕션 변경).
