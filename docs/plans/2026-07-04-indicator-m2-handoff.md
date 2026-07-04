# 지표 SoT — 진행 상태 & 데이터 서버 인계 (main 기록)

- 작성일: 2026-07-04
- 목적: 지표 단일-진실-소스(SoT) 작업의 **현재 상태**와, 남은 게이트 작업을 **시장데이터가 있는
  서버에서 이어서** 실행하는 방법을 main에 기록.
- 선행: [indicator-coverage-builder-catalog-roadmap](2026-07-04-indicator-coverage-builder-catalog-roadmap.md)(로드맵),
  [indicator-m2-prepared-fixes](2026-07-04-indicator-m2-prepared-fixes.md)(게이트 커밋 diff 원본),
  [indicator-spike-pandas-ta-decision](2026-07-04-indicator-spike-pandas-ta-decision.md)(pandas-ta 결정)

## main에 머지 완료 (게이트 불필요)

| 작업 | 내용 |
|---|---|
| **공유 설정** | `.gitignore` 네거티브(`!**/CLAUDE.md`)로 전역 무시 재정의 + `shared/llm/CLAUDE.md` 추적 → 다른 장비 공유 |
| **M1 빌더 카탈로그** | 카탈로그 10→18(이미 구현된 지표 노출), 프론트 빌더 동적 capabilities fetch + 배지 활성화, parity 하네스(`tests/unit/indicators/test_calc_parity.py`), pandas-ta 결정 |
| **M2-A 참조 계산기** | `shared/indicators/reference.py`(표준 Wilder RSI/ADX, ddof-param Bollinger, StochRSI 생산자) + 테스트. 순수 additive, 런타임 미배선 |
| **StochRSI 배선** | `services/trading/indicator_queries.py`가 stochrsi_k/d/k_prev 방출. **`stochrsi_enabled=False` 기본 + config `enabled: false` → 라이브 영향 0.** 활성화는 별도 PR |

이들은 결함 함수(`_calc_rsi`, `_calc_adx`)를 **바꾸지 않는다** → RegimeGate/RSI 전략 동작 불변. 안전.

## 게이트 대기 (별도 브랜치, main 미머지)

값이 바뀌어 라이브 동작을 바꾸므로 **시장데이터 백테스트 통과 전 main 머지 금지.**

| 브랜치 | 변경 | 값 변화 | 머지 게이트 |
|---|---|---|---|
| `feat/indicator-adx-wilder-gated` | `adaptive_detector._calc_adx` → `reference.ADXCalculator` 위임 | detector ADX **15.87 → 31.63** (~2×, canonical) | regime characterization + head-to-head + counterfactual + `adx_*` 임계값 재튜닝 (regime-gate-analyst) |
| `feat/indicator-rsi-wilder-gated` | `_calc_rsi` SMA → Wilder | streaming RSI **60.20 → 47.10** (Δ13.1) | 모든 RSI 소비 전략(bb_reversion/mean_reversion 등) full 백테스트 Sharpe/MDD/승률/PF 델타 |

두 브랜치는 각각 **현재 main 위에 단일 게이트 커밋만** 스택 → 독립적으로 백테스트·머지 가능.

## 서버에서 이어서 할 일 (게이트 실행)

### 사전조건
Parquet 시장데이터 store(`config/storage.yaml::market_data.parquet.root`) 채워짐 + Redis DB1 up + `pip install -e ".[dev]"`. (개발 세션엔 데이터/Redis 없어 로컬 실행 불가였음.)

### 게이트 A — RSI (`feat/indicator-rsi-wilder-gated`)
1. baseline = `main`(SMA RSI), candidate = `feat/indicator-rsi-wilder-gated`(Wilder).
2. RSI 소비 전략 동일 기간·유니버스 백테스트: `python -m cli.main backtest run --strategy bb_reversion ...`(각 브랜치), `backtest best`로 결과 비교.
3. 판정: Sharpe/MDD/승률/PF 유의미 악화 없으면 통과 → main 머지. (parity 스냅샷은 브랜치에서 수렴값으로 갱신됨)

### 게이트 B — ADX (`feat/indicator-adx-wilder-gated`, regime-gate-analyst)
1. 수정 전/후 `AdaptiveRegimeDetector` trend/range 분포 characterization.
2. head-to-head + counterfactual EOD-proxy PnL.
3. 필요 시 `adx_period`/`adx_strong_trend`/`adx_weak_trend`(config) 재튜닝. 계산은 이미 canonical이므로 되돌리기보다 임계값 조정이 정석. 통과 시 main 머지.

### 게이트 C — StochRSI 활성화 (별도 activation PR)
배선은 이미 main에 있고 default-off. 활성화 전: `stochrsi_trend` 백테스트 → head-to-head → paper. 통과 시 config `enabled: true` + engine kwargs 배선.

## 머지 순서 권고
main(완료) → 게이트 통과분(ADX/RSI 각각 독립) → StochRSI 활성화(별도).

## 담당
- backtest-engineer: 게이트 A(RSI), 게이트 C(StochRSI 백테스트).
- regime-gate-analyst: 게이트 B(ADX regime characterization / 임계값 재튜닝).

## 검증 스냅샷 (main)
`pytest tests/unit/indicators/ tests/unit/regime/test_adaptive_detector.py tests/unit/strategy/test_stochrsi.py tests/unit/dashboard/test_strategy_builder.py` 그린(polars 1 skip). main은 결함 함수 유지 + divergence 단언 통과(내부 정합). ruff/mypy 신규 에러 0.
