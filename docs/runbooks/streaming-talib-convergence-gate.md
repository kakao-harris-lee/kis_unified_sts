# Runbook — Streaming 지표 엔진 → TA-Lib 표준 수렴 (데이터 서버 백테스트 게이트)

- 작성일: 2026-07-06
- 성격: 데이터 서버 실행 런북 (값이 바뀌는 라이브 변경의 승격 게이트)
- 선행 계획: [../plans/2026-07-06-talib-builder-alignment.md](../plans/2026-07-06-talib-builder-alignment.md) (Phase C/F)
- 형식 참고: [../plans/2026-07-04-indicator-m2-handoff.md](../plans/2026-07-04-indicator-m2-handoff.md) (ADX/RSI Wilder 게이트)

## 배경

TA-Lib 정합화(2026-07-06) 이후 지표 계산에는 두 엔진이 공존한다:

- `default_engine()` = TALibBackend + NumpyBackend — **표준 규약**. 노코드 빌더가 사용.
- `streaming_indicator_engine()` = `StreamingCompatBackend` — **비표준 손구현 규약**
  (first-delta-seeded RSI, ddof=1 Bollinger, fast %K Stochastic, lenient ADX warmup).
  실시간/페이퍼 런타임이 사용.

손구현 `_calc_*` 원본은 이미 파기됐고, `services/trading/indicator_calculations.py`의
`_calc_rsi`/`_calc_bb`/`_calc_adx`/`_calc_stochastic`/`_calc_mfi`/`_calc_rvol`은 현재
`streaming_indicator_engine()`에 위임하는 얇은 델리게이트다. 따라서 "값 보존" 명분이
사라졌고, **streaming 백엔드를 `default_engine`(TA-Lib 표준)으로 수렴**시키면 같은 심볼의
cockpit 표시값과 빌더 계산값이 일치하게 된다.

**단, 이 변경은 라이브 시그널 값을 이동시킨다.** 그러므로 이 런북의 A/B 백테스트를
데이터 서버에서 통과하기 전에는 main(→ live)에 머지하지 않는다. 개발 세션은 시장데이터가
없어 로컬 실행이 불가하다 (verify는 모의투자/데이터 서버에서).

## 구현 상태 (config 게이트, main-safe)

Phase C는 **config 게이트**로 main에 이미 구현돼 있다 (StochRSI default-off 선례). 값이
바뀌는 코드를 브랜치에 묶어두는 대신, 런타임 델리게이트가 셀렉터를 통해 엔진을 고른다:

- `shared/indicators/engine/registry.py::runtime_indicator_engine()` — env
  `STS_INDICATOR_CONVENTION`(기본 `streaming`)로 streaming/talib 엔진 선택. 알 수 없는 값은
  `streaming`으로 폴백(오타로 라이브 값이 바뀌지 않도록).
- `services/trading/indicator_calculations.py` — 6개 `_calc_*`가
  `streaming_indicator_engine()` → `runtime_indicator_engine()`로 위임 변경.
- `StreamingCompatBackend`와 `test_streaming_backend_golden.py`는 **그대로 유지** — 기본
  경로가 여전히 streaming이므로 라이브 값·골든 핀 불변.

**기본값 `streaming`이라 라이브 영향 0.** 이 런북의 게이트 통과 후, 데이터 서버에서만
`STS_INDICATOR_CONVENTION=talib`로 플립한다.

## 예상 값 이동 (참고)

`docs/plans/2026-07-04-indicator-m2-handoff.md`의 사전 측정과 동일 방향:

- RSI: first-delta seed → Wilder 표준. 초기 세션 창에서 유의미한 델타 (핸드오프에서 Δ13 관측).
- Bollinger: ddof=1(sample) → ddof=0(population). 밴드 폭 축소.
- Stochastic: fast %K → STOCH slow %K. 값 이동.
- ADX: lenient partial-DX warmup → 표준. warmup 구간 값 이동.

## 사전조건 (데이터 서버)

- Parquet 시장데이터 store 채워짐 (`config/storage.yaml::market_data.parquet.root`).
- Redis DB1 up (`redis://localhost:6379/1`).
- `pip install -e ".[dev]"`, TA-Lib wheel 설치됨.

## 게이트 절차 (A/B 백테스트)

동일 코드(main)에서 **env 플래그만 바꿔** baseline vs candidate를 동일 기간·유니버스로
백테스트한다. 브랜치 체크아웃 불필요.

대상 전략 (streaming rsi/bollinger/adx/stochastic/mfi 소비):
- `config/strategies/futures/bb_reversion_15m.yaml`
- `config/strategies/stock/bb_reversion.yaml`
- (RSI/Stochastic/ADX를 참조하는 그 외 등록 전략)

1. **baseline 측정** (`streaming`, 기본값):
   ```bash
   unset STS_INDICATOR_CONVENTION   # 또는 =streaming
   python -m cli.main backtest run --strategy bb_reversion --start <YYYY-MM-DD> --end <YYYY-MM-DD>
   python -m cli.main backtest best
   ```
2. **candidate 측정** (`talib`, 수렴):
   ```bash
   STS_INDICATOR_CONVENTION=talib python -m cli.main backtest run --strategy bb_reversion --start <YYYY-MM-DD> --end <YYYY-MM-DD>
   python -m cli.main backtest best
   ```
   ※ 백테스트 엔진이 런타임 `_calc_*` 경로를 태우는지 확인. 백테스트가 별도 지표
   경로를 쓴다면 그 경로에도 동일 셀렉터가 걸리는지 점검(현재 빌더/런타임은
   `runtime_indicator_engine()`/`default_engine()` 사용).
3. **델타 비교** — Sharpe / MDD / 승률 / Profit Factor / 총 시그널 수.
4. **판정 기준**:
   - Sharpe / MDD / 승률 유의미 악화 없음 → 통과.
   - 시그널 수 급변(예: warmup 규약 변화로 조기 시그널 소멸)은 원인 규명 후 판정.
   - 악화 시: 전략 임계값(RSI/BB/ADX 경계)이 옛 규약에 튜닝돼 있었을 수 있으므로,
     계산 되돌리기보다 **임계값 재튜닝**이 정석 (m2-handoff 게이트 B와 동일 논리).
5. 통과 시: 운영 env에 `STS_INDICATOR_CONVENTION=talib` 설정 → shadow/paper 관찰 → live.

## shadow-우선 승격

- 게이트 통과 전까지 운영 env는 플래그 미설정(=`streaming`) 유지 → 라이브 영향 0.
- `talib` 플립은 shadow/paper 먼저. live 승격은 CLAUDE.md 규칙 준수:
  `config/futures_live.yaml::enabled` + Redis `futures:live:suspended` 절차,
  hard stop / EOD close 안전장치 확인.

## 담당

- backtest-engineer: A/B 백테스트 실행 + Sharpe/MDD/승률 델타 판정.
- regime-gate-analyst: ADX 규약 변화가 RegimeGate에 영향 시 characterization / 임계값 재튜닝.
- model-deployer: 게이트 통과 후 shadow→paper→live 승격 (운영 env 플래그 관리).

## 로컬 검증 (게이트 아님)

게이트 로직 자체는 로컬에서 단위 검증 가능 (시장데이터 불요):
```bash
python -m pytest tests/unit/indicators/engine/test_registry.py -q   # 컨벤션 게이트 (default=streaming, talib 플립, 오타 폴백)
python -m pytest tests/unit/trading/test_indicator_engine_helpers.py -q  # _calc_* 델리게이트 불변
```
