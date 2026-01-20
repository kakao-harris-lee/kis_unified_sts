# Copilot Instructions - KIS Unified Trading Platform

## Project Overview

Unified short-term trading system for Korean stocks and futures via KIS (Korea Investment & Securities) API. The core goal is **optimizing entry/exit timing** through configuration-driven strategies with MLflow-tracked backtesting.

## Architecture Principles

### Configuration-Driven Development
**All values must come from YAML config files** - never hardcode numbers or thresholds.

```python
# ❌ Never do this
if pnl_pct >= 2.0:  # hardcoded threshold
    state = "BREAKEVEN"

# ✅ Always use config
if pnl_pct >= self.config.breakeven_threshold_pct:
    state = PositionState.BREAKEVEN
```

Config files live in `config/` with this structure:
- `strategies/{stock,futures}/` - Strategy YAML files
- `exit/` - Exit strategy configs (e.g., `three_stage.yaml`)
- `kis/` - API authentication
- `risk/` - Risk management rules

### Strategy Pattern with Registry

Entry/Exit/Position sizing are **independent, composable components** registered via decorators:

```python
@EntryRegistry.register("bb_reversion")
class BBReversionEntry(EntrySignalGenerator):
    CONFIG_CLASS = BBReversionConfig  # Auto-converts params dict to typed config
    ...
```

Create strategies from config using `StrategyFactory`:
```python
strategy = StrategyFactory.create_from_file("stock", "bb_reversion")
```

### Key Abstractions

| Interface | Purpose | Location |
|-----------|---------|----------|
| `EntrySignalGenerator` | Generates entry signals | [shared/strategy/base.py](shared/strategy/base.py) |
| `ExitSignalGenerator` | Determines exit conditions | [shared/strategy/base.py](shared/strategy/base.py) |
| `PositionSizer` | Calculates position sizes | [shared/strategy/base.py](shared/strategy/base.py) |
| `TradingStrategy` | Composes entry/exit/sizing | [shared/strategy/base.py](shared/strategy/base.py) |

### No Code Duplication

Shared logic goes in `shared/` modules - never duplicate across `domains/stock/` and `domains/futures/`. Use:
- `shared/indicators/` - Technical indicators (BB, RSI, OFI, VPIN)
- `shared/models/` - Data models (Position, Signal, ExitSignal)
- `shared/backtest/` - Backtesting engine with MLflow integration

## Adding a New Strategy

1. Create config: `config/strategies/{stock,futures}/{name}.yaml`
2. Implement Entry/Exit classes in `shared/strategy/entry/` or `exit/` (if needed)
3. Register with decorator: `@EntryRegistry.register("name")`
4. **No further code changes needed** - config activates it automatically

## CLI Commands

```bash
sts backtest run -s bb_reversion -a stock -d ./data/sample.csv
sts optimize --strategy bb_reversion --trials 100 --metric sharpe_ratio
sts mlflow ui
```

## Git Worktree Workflow

**모든 작업은 반드시 Git Worktree를 사용해야 합니다.** 메인 브랜치에서 직접 작업하지 마세요.

### 새 기능 개발 시작

```bash
# 1. 워크트리 생성 (feature 브랜치 자동 생성)
git worktree add ../kis_unified_sts-feature-name -b feature/feature-name

# 2. 워크트리로 이동
cd ../kis_unified_sts-feature-name

# 3. 작업 진행...
```

### 버그 수정

```bash
git worktree add ../kis_unified_sts-fix-issue-123 -b fix/issue-123
```

### 워크트리 관리

```bash
# 활성 워크트리 목록 확인
git worktree list

# 작업 완료 후 워크트리 제거
git worktree remove ../kis_unified_sts-feature-name

# 또는 디렉토리 삭제 후 정리
rm -rf ../kis_unified_sts-feature-name
git worktree prune
```

### 브랜치 네이밍 규칙

| 접두사 | 용도 | 예시 |
|--------|------|------|
| `feature/` | 새 기능 | `feature/cnn-lstm-migration` |
| `fix/` | 버그 수정 | `fix/streaming-timeout` |
| `refactor/` | 리팩토링 | `refactor/strategy-registry` |
| `docs/` | 문서 | `docs/api-reference` |

### Worktree 디렉토리 구조

```
~/Development/private/
├── kis_unified_sts/                    # main 브랜치 (원본)
├── kis_unified_sts-feature-lstm/       # feature/cnn-lstm-migration
├── kis_unified_sts-fix-redis/          # fix/redis-connection
└── kis_unified_sts-docs-api/           # docs/api-reference
```

### 주의사항

- 워크트리 디렉토리명은 `{repo}-{short-description}` 형식 사용
- PR 머지 후 반드시 워크트리 정리: `git worktree remove <path>`
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

- `KIS_APP_KEY`, `KIS_APP_SECRET` - KIS API credentials
- `KIS_CONFIG_DIR` - Override config directory path
- `OPENAI_API_KEY` - OpenAI API key for LLM analysis
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` - Telegram notifications
- `DART_API_KEY` - DART 전자공시 API key

## LLM Market Analysis Module

The `shared/llm/` module provides OpenAI GPT-based market analysis with Korean financial data collectors.

### Data Sources

| Source | URL | Data |
|--------|-----|------|
| pykrx | - | 주식 시세 (기본) |
| KRX | data.krx.co.kr | 거래소 공식, 투자자별 동향 |
| SEIBRO | seibro.or.kr | 증권정보, 배당, 주주현황 |
| DART | dart.fss.or.kr | 공시정보, 재무제표 |
| KSD | ksd.or.kr | 공매도, 대차잔고 |
| MK Stock | stock.mk.co.kr | 증권뉴스, 감성분석 |

### Usage

```python
from shared.llm import run_unified_analysis, get_stock_detail_briefing
from shared.notification import TelegramNotifier

# 통합 분석 실행
notifier = TelegramNotifier()
stock_plans, futures_plan, data = await run_unified_analysis(
    notifier=notifier,
    mode='all',
    send_telegram=True
)

# 개별 종목 상세 브리핑
briefing = await get_stock_detail_briefing("005930", notifier=notifier)
```

### Cron Scripts

| Script | Time | Description |
|--------|------|-------------|
| `scripts/analysis/llm_nightly_analysis.py` | 21:00 | 익일 트레이딩 분석 |
| `scripts/analysis/llm_premarket_briefing.py` | 08:30 | 장전 최종 브리핑 |
| `scripts/analysis/llm_market_close_briefing.py` | 15:30 | 장 마감 요약 |

## Key Patterns

### 3-Stage Exit State Machine
The flagship exit strategy in [shared/strategy/exit/three_stage.py](shared/strategy/exit/three_stage.py):
1. **SURVIVAL** - Hard stop loss protection
2. **BREAKEVEN** - Lock in break-even after threshold gain
3. **MAXIMIZE** - Trailing stop to capture upside

### Environment Variable Resolution in Config
Config schema supports `${VAR_NAME}` syntax for secrets:
```yaml
auth:
  app_key: ${KIS_APP_KEY}
  app_secret: ${KIS_APP_SECRET}
```
