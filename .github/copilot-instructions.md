# Copilot Instructions - KIS Unified Trading Platform

## Project Overview

Unified short-term trading system for Korean stocks and futures via KIS (Korea Investment & Securities) API. The core goal is **optimizing entry/exit timing** through configuration-driven strategies with MLflow-tracked backtesting.

## Architecture Principles

### Configuration-Driven Development

**All values must come from YAML config files** — never hardcode numbers or thresholds.

```python
# ❌ Never do this
if pnl_pct >= 2.0:
    state = "BREAKEVEN"

# ✅ Always use config
if pnl_pct >= self.config.breakeven_threshold_pct:
    state = PositionState.BREAKEVEN
```

Config files live in `config/` with this structure:

- `strategies/{stock,futures}/` — Strategy YAML files
- `exit/` — Exit strategy configs (three_stage, market_regime, time_decay)
- `kis/` — API authentication
- `ml/` — ML model configs (cnn_lstm, rl_mppo)

### Strategy Pattern with Registry

Entry/Exit/Position sizing are **independent, composable components** registered via decorators or `register_builtin_components()`. All registry classes and `StrategyFactory` live in `shared/strategy/registry.py`.

### Key Abstractions

| Interface              | Purpose                        | Location                      |
| ---------------------- | ------------------------------ | ----------------------------- |
| `EntrySignalGenerator` | Generates entry signals        | `shared/strategy/base.py`     |
| `ExitSignalGenerator`  | Determines exit conditions     | `shared/strategy/base.py`     |
| `PositionSizer`        | Calculates position sizes      | `shared/strategy/base.py`     |
| `TradingStrategy`      | Composes entry/exit/sizing     | `shared/strategy/base.py`     |
| `StrategyFactory`      | Creates strategies from config | `shared/strategy/registry.py` |

### Runtime Trading Layer

| Component             | Purpose                                        | Location                               |
| --------------------- | ---------------------------------------------- | -------------------------------------- |
| `TradingOrchestrator` | Full trading lifecycle & main loop             | `services/trading/orchestrator.py`     |
| `StrategyManager`     | Multi-strategy management & signal aggregation | `services/trading/strategy_manager.py` |
| `MarketDataProvider`  | Market data collection                         | `services/trading/data_provider.py`    |
| `IndicatorEngine`     | Indicator calculation/caching                  | `services/trading/indicator_engine.py` |
| `PositionTracker`     | Position tracking                              | `services/trading/position_tracker.py` |
| `HolidayCache`        | Trading holiday cache                          | `services/trading/holiday_cache.py`    |
| `TradingPipeline`     | Data pipeline orchestration                    | `services/trading/pipeline.py`         |

### No Code Duplication

Shared logic goes in `shared/` modules — never duplicate across `domains/stock/` and `domains/futures/`. Use:

- `shared/indicators/` — Technical indicators (TechnicalCalculator, OrderBookAnalyzer, VolumeAcceleration, VWAP)
- `shared/models/` — Data models (Position, Signal, ExitSignal, PositionState)
- `shared/backtest/` — Backtesting engine with MLflow integration

### Registered Entry Strategies

| Name                   | Class                             | Location                                        |
| ---------------------- | --------------------------------- | ----------------------------------------------- |
| `mean_reversion`       | `MeanReversionEntry`              | `shared/strategy/entry/mean_reversion.py`       |
| `microstructure`       | `MicrostructureEntry`             | `shared/strategy/entry/microstructure.py`       |
| `ofi_momentum`         | `OFIMomentumEntry`                | `shared/strategy/entry/ofi_momentum.py`         |
| `breakout`             | `BreakoutEntry`                   | `shared/strategy/entry/breakout.py`             |
| `opening_volume_surge` | `OpeningVolumeSurgeEntry`         | `shared/strategy/entry/opening_volume_surge.py` |
| `stochrsi_trend`       | `StochRSITrendEntry`              | `shared/strategy/entry/stochrsi_trend.py`       |
| `v35_optimized`        | `V35OptimizedEntry`               | `shared/strategy/entry/v35_optimized.py`        |
| `volume_accumulation`  | `VolumeAccumulationBreakoutEntry` | `shared/strategy/entry/volume_accumulation.py`  |
| `rl_mppo`              | `RLMPPOEntry`                     | `shared/strategy/entry/rl_mppo.py`              |
| `futures_dl_trend`     | `DLTrendEntry`                    | `domains/futures/strategies/dl_trend.py`        |

### Registered Exit Strategies

| Name             | Class               | Location                                 |
| ---------------- | ------------------- | ---------------------------------------- |
| `three_stage`    | `ThreeStageExit`    | `shared/strategy/exit/three_stage.py`    |
| `atr_trailing`   | `ATRTrailingExit`   | `shared/strategy/exit/atr_trailing.py`   |
| `market_regime`  | `MarketRegimeExit`  | `shared/strategy/exit/market_regime.py`  |
| `time_decay`     | `TimeDecayExit`     | `shared/strategy/exit/time_decay.py`     |
| `momentum_decay` | `MomentumDecayExit` | `shared/strategy/exit/momentum_decay.py` |

## Adding a New Strategy

1. Create config: `config/strategies/{stock,futures}/{name}.yaml`
2. Implement Entry/Exit classes in `shared/strategy/entry/` or `exit/` (if reusing existing, skip)
3. Register: `@EntryRegistry.register("name")` or add to `register_builtin_components()`
4. **No further code changes needed** — `enabled: true` in YAML activates it

## CLI Commands

All CLI commands are defined in `cli/main.py` (Click-based):

```bash
sts backtest run --strategy bb_reversion --asset futures --data ./data.csv
sts backtest best --strategy bb_reversion --asset futures
sts backtest list --asset stock
sts optimize --strategy bb_reversion --asset futures --data ./data.csv --trials 100
sts mlflow ui
sts mlflow list
sts collect start -s 005930
sts backfill today
sts stock-backfill run --days 7
sts websocket start
sts trade start --strategy bb_reversion --asset stock --paper
sts paper start --strategy bb_reversion --asset stock
sts rl train --algo mppo
sts rl evaluate --model mppo_best
```

## Git Worktree Workflow

**모든 작업은 반드시 Git Worktree를 사용해야 합니다.** 메인 브랜치에서 직접 작업하지 마세요.

```bash
# 새 기능: 워크트리 생성 → 이동 → 작업
git worktree add ../kis_unified_sts-feature-name -b feature/feature-name
cd ../kis_unified_sts-feature-name

# 버그 수정
git worktree add ../kis_unified_sts-fix-issue-123 -b fix/issue-123

# 워크트리 관리
git worktree list
git worktree remove ../kis_unified_sts-feature-name
git worktree prune
```

### 브랜치 네이밍 규칙

| 접두사      | 용도      | 예시                         |
| ----------- | --------- | ---------------------------- |
| `feature/`  | 새 기능   | `feature/cnn-lstm-migration` |
| `fix/`      | 버그 수정 | `fix/streaming-timeout`      |
| `refactor/` | 리팩토링  | `refactor/strategy-registry` |
| `docs/`     | 문서      | `docs/api-reference`         |

### 주의사항

- 워크트리 디렉토리명: `{repo}-{short-description}` 형식
- PR 머지 후 반드시 워크트리 정리
- 같은 브랜치를 여러 워크트리에서 체크아웃 불가

## Development Commands

```bash
# Format & lint
black . && ruff check --fix .

# Type check
mypy shared/ domains/

# Test
pytest tests/ -v --cov=shared
```

## Environment Variables

| Variable                                                                  | Purpose                             |
| ------------------------------------------------------------------------- | ----------------------------------- |
| `KIS_STOCK_APP_KEY`, `KIS_STOCK_APP_SECRET`, `KIS_STOCK_ACCOUNT_NO`       | Stock KIS API credentials           |
| `KIS_FUTURES_APP_KEY`, `KIS_FUTURES_APP_SECRET`, `KIS_FUTURES_ACCOUNT_NO` | Futures KIS API credentials         |
| `KIS_STOCK_MARKET`, `KIS_FUTURES_MARKET`                                  | Trading mode (`real`/`mock`)        |
| `KIS_CONFIG_DIR`                                                          | Override config directory path      |
| `CLICKHOUSE_*`, `REDIS_*`, `MLFLOW_TRACKING_URI`                          | Infrastructure settings             |
| `OPENAI_API_KEY`, `KRX_API_KEY`, `DART_API_KEY`                           | LLM/data APIs                       |
| `TELEGRAM_STOCK_*`, `TELEGRAM_FUTURES_*`, `TELEGRAM_BRIEFING_*`           | Telegram notifications              |
| `API_KEY`, `GRAFANA_*`, `PROMETHEUS_PORT`                                 | API/monitoring                      |
| `KIS_APP_KEY`, `KIS_APP_SECRET`                                           | Legacy single-account compatibility |

Config YAML supports `${VAR_NAME}` / `${VAR_NAME:default}` syntax for secrets.

## Market Classifier

`shared/strategy/market_classifier.py` provides MFI/ADX-based market state classification used by `MarketRegimeExit`.

## LLM Market Analysis Module

`shared/llm/` provides OpenAI GPT-based market analysis with Korean financial data collectors (14 modules).

Key exports: `run_unified_analysis()`, `get_stock_detail_briefing()`

### Cron Scripts

| Script                                          | Time  | Description        |
| ----------------------------------------------- | ----- | ------------------ |
| `scripts/analysis/llm_nightly_analysis.py`      | 21:00 | 익일 트레이딩 분석 |
| `scripts/analysis/llm_premarket_briefing.py`    | 08:30 | 장전 최종 브리핑   |
| `scripts/analysis/llm_market_close_briefing.py` | 15:30 | 장 마감 요약       |

## Key Patterns

### 3-Stage Exit State Machine

`shared/strategy/exit/three_stage.py` — flagship exit strategy:

1. **SURVIVAL** — Hard stop loss protection
2. **BREAKEVEN** — Lock in break-even after threshold gain
3. **MAXIMIZE** — Trailing stop to capture upside (dynamic width: normal/tight)
