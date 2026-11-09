# Copilot Instructions - KIS Unified Trading Platform

## Project Overview

Two projects in one repository. The **TOS kernel** (`tos/`, `tos-spec/`,
`tos-evidence/`, `tools/tos_*`) is the live one — read `tos/CLAUDE.md` before
touching it. The legacy KIS trading runtime it replaced was deleted in
2026-11 (`docs/plans/2026-11-07-legacy-removal-plan.md`, steps L1–L6); it last
existed at tag `legacy-final` (`6fc17c0f8d25`). What survives outside `tos/` is
the CP-3 measurement path, the KIS broker probes, a read-only operator
dashboard, and the `shared/` modules those import.

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

- `tos_runtime/` — TOS tenant trees (calendar, release, profile). Digest-bound —
  do not edit as a side effect of other work.
- `tos_*.yaml` — TOS gates (completion, size budget, status board, CP-3 B3).
- `tos_probes/`, `broker_probes/` — probe configs.
- `kis/` — API authentication; `exit/three_stage.yaml`, `gates/`, `ml/`,
  `strategy_builder/`, `strategy_lab/` — what the surviving `shared/` reads.
- `strategies/futures/setup_d_vwap_reversion.yaml` — the only strategy YAML
  left; it is the CP-3 B3 witness's input.

### Strategy Pattern with Registry

Entry/Exit/Position sizing are **independent, composable components** registered
via decorators or `register_builtin_components()`. All registry classes and
`StrategyFactory` live in `shared/strategy/registry.py`.

Status note (legacy runtime removed in L1–L6): every `shared/strategy/entry/*`
module was deleted, so the entry roster is currently **empty** and
`StrategyFactory` builds nothing. Execution authority today is the TOS kernel,
where a strategy is Tenant Content under `config/tos_runtime/`.

### Key Abstractions

| Interface              | Purpose                        | Location                      |
| ---------------------- | ------------------------------ | ----------------------------- |
| `EntrySignalGenerator` | Generates entry signals        | `shared/strategy/base.py`     |
| `ExitSignalGenerator`  | Determines exit conditions     | `shared/strategy/base.py`     |
| `PositionSizer`        | Calculates position sizes      | `shared/strategy/base.py`     |
| `TradingStrategy`      | Composes entry/exit/sizing     | `shared/strategy/base.py`     |
| `StrategyFactory`      | Creates strategies from config | `shared/strategy/registry.py` |

### What is left of `shared/`

| Area | Purpose |
| --- | --- |
| `shared/backtest/market_context_replay.py`, `shared/decision/` | the CP-3 producer and the **B3 witness** (legacy Setup D). Keep byte-identical until `TOS_PAPER_READY` |
| `shared/strategy/exit/setup_target_exit.py` | the witness's exit; `three_stage`, `momentum_decay`, `trix_golden_exit`, `technical_consensus_exit` are the other registered exits |
| `shared/indicators/`, `shared/instruments/`, `shared/determinism/` | pure commons; four of the six packages the tos import firewall allows |
| `shared/kis/` | KIS auth + REST client + stock feed |
| `shared/storage/` | Parquet/DuckDB market-data store, SQLite runtime ledger |
| `shared/llm/` | Korean market-analysis collectors (still imported, not scheduled) |
| `shared/execution/executor.py` | kept **only** because `docs/broker-profiles/BROKER-TRANSPORT-SYMBOLS.csv` binds the `ORDER_SENDER` symbol to it and `tools/tos_spec_status.py --check` requires the class to exist. Nothing calls it |

### No Code Duplication

Shared logic goes in `shared/` modules.

## CLI Commands

All CLI commands are defined in `cli/main.py` (Click-based):

`sts tos` is the only command group left — `backtest`, `optimize`, `mlflow`,
`collect`, `backfill`, `websocket`, `trade` and `paper` went with the legacy
runtime (removal plan L3).

```bash
sts tos status     # one-page operator status board
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
mypy shared/ --ignore-missing-imports --no-error-summary

# Test
pytest tests/ -q

# TOS checkers (what CI gates on)
python tools/tos_spec_status.py --check
python tools/tos_firewall_check.py
# `lint-imports` as CI runs it (.github/workflows/tos-firewall.yml): plain, after
# an editable install of the root project and tos/runtime. Without that install
# the contracts' root packages do not resolve; a local shortcut is
# `PYTHONPATH=.:tos/src:tos/runtime/src lint-imports`, which is NOT what gates.
lint-imports
```

## Environment Variables

| Variable                                                                  | Purpose                             |
| ------------------------------------------------------------------------- | ----------------------------------- |
| `KIS_STOCK_APP_KEY`, `KIS_STOCK_APP_SECRET`, `KIS_STOCK_ACCOUNT_NO`       | Stock KIS API credentials           |
| `KIS_FUTURES_APP_KEY`, `KIS_FUTURES_APP_SECRET`, `KIS_FUTURES_ACCOUNT_NO` | Futures KIS API credentials         |
| `KIS_STOCK_MARKET`, `KIS_FUTURES_MARKET`                                  | Trading mode (`real`/`mock`)        |
| `KIS_CONFIG_DIR`                                                          | Override config directory path      |
| `REDIS_*`                                                                 | Infrastructure settings (DB 1)      |
| `OPENAI_API_KEY`, `KRX_API_KEY`, `DART_API_KEY`                           | LLM/data APIs                       |
| `TELEGRAM_STOCK_*`, `TELEGRAM_FUTURES_*`, `TELEGRAM_BRIEFING_*`           | Telegram notifications              |
| `API_KEY`, `PROMETHEUS_PORT`                                              | API/monitoring                      |
| `KIS_APP_KEY`, `KIS_APP_SECRET`                                           | Legacy single-account compatibility |

Config YAML supports `${VAR_NAME}` / `${VAR_NAME:default}` syntax for secrets.

## Market Classifier

`shared/strategy/market_classifier.py` provides MFI/ADX-based market state
classification. Its consumer (`MarketRegimeExit`) no longer exists.

## LLM Market Analysis Module

`shared/llm/` provides OpenAI GPT-based market analysis with Korean financial
data collectors. Nothing schedules it any more: the briefing scripts under
`scripts/analysis/` and their cron lines went with the legacy runtime
(removal plan L3). The only cron on the deploy host runs the TOS session
wrappers in `~/.config/kis-probes/` (`docs/runbooks/tos-paper-boot.md` §7.2).

## Key Patterns

### 3-Stage Exit State Machine

`shared/strategy/exit/three_stage.py` — flagship exit strategy:

1. **SURVIVAL** — Hard stop loss protection
2. **BREAKEVEN** — Lock in break-even after threshold gain
3. **MAXIMIZE** — Trailing stop to capture upside (dynamic width: normal/tight)
