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
- `kis/` — API authentication; `storage.yaml` / `streaming.yaml` /
  `execution.yaml` — what the surviving `shared/` reads.
- `strategies/futures/setup_d_vwap_reversion.yaml` — the only strategy YAML
  left; it is the CP-3 B3 witness's input.

### Strategy Pattern with Registry (retired)

Entry/Exit/Position sizing used to be independent, composable components
registered through `shared/strategy/registry.py` and assembled by
`StrategyFactory`. L6 deleted every `shared/strategy/entry/*` module, which left
the entry roster empty, and L7 deleted the registry, the factory and the
remaining exits and sizers — all of them outside the surviving import closure
(`docs/plans/2026-11-07-legacy-removal-plan.md` §3). Execution authority today
is the TOS kernel, where a strategy is Tenant Content under
`config/tos_runtime/`. Do not reintroduce the registry here.

### Key Abstractions

| Interface              | Purpose                        | Location                      |
| ---------------------- | ------------------------------ | ----------------------------- |
| `EntrySignalGenerator` | Generates entry signals        | `shared/strategy/base.py`     |
| `ExitSignalGenerator`  | Determines exit conditions     | `shared/strategy/base.py`     |
| `PositionSizer`        | Calculates position sizes      | `shared/strategy/base.py`     |
| `TradingStrategy`      | Composes entry/exit/sizing     | `shared/strategy/base.py`     |

Only the base classes survive; the one concrete implementation left is the
witness's exit (below).

### What is left of `shared/`

| Area | Purpose |
| --- | --- |
| `shared/backtest/market_context_replay.py`, `shared/decision/` | the CP-3 producer and the **B3 witness** (legacy Setup D). Keep byte-identical until `TOS_PAPER_READY` |
| `shared/strategy/exit/setup_target_exit.py` | the witness's exit, and the only exit implementation left — L7 deleted `three_stage`, `momentum_decay`, `trix_golden_exit` and `technical_consensus_exit` with the registry |
| `shared/{models,indicators,resilience,utils,exceptions,determinism}/` | the six packages the tos import firewall allows; kept whole even where unused, because narrowing that surface is a boundary-design change |
| `shared/instruments/` | futures contract specs the witness reads |
| `shared/kis/auth.py` | KIS auth for the CP-3 quote client |
| `shared/storage/{config,market_data_store}.py` | Parquet/DuckDB market-data store |
| `shared/llm/{data_classes,market_context}.py` | the two type-hint modules `shared/strategy/base.py` still names; L7 deleted the other 35 |
| `shared/execution/executor.py`, `shared/kis/client.py` **and their import closures** | kept **only** because `docs/broker-profiles/BROKER-TRANSPORT-SYMBOLS.csv` binds `ORDER_SENDER` / `BROKER_CLIENT_READ` to them and `tools/tos_spec_status.py --check` requires those classes to exist. Nothing calls them; `services/monitoring/`, `shared/streaming/`, `shared/observability/` and `shared/http/` are in the tree only because those two import them |

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

## Removed in L7 — do not look for these

`shared/strategy/registry.py` · `factory.py` · `market_classifier.py` ·
`technical_consensus.py` · `builtin_components.py` · `shared/strategy/exit/`
(all but `setup_target_exit.py`) · `shared/strategy/position/` ·
`shared/strategy/gates/` · `shared/strategy_builder/` · `shared/strategy_lab/` ·
`shared/regime/` · `shared/notification/` · `shared/features/` ·
`shared/llm/` (all but `data_classes.py` and `market_context.py`) ·
`shared/backtest/` (all but `market_context_replay.py`) ·
`shared/storage/runtime_ledger*` · `shared/kis/stock_feed.py` ·
`shared/collector/` (all but `historical/ohlcv_parser.py`).

They were outside the import closure the TOS roots reach
(`docs/plans/2026-11-07-legacy-removal-plan.md` §3); the code is in git history
from tag `legacy-final` (`6fc17c0f8d25`) onward. The 3-stage exit state machine,
the MFI/ADX market classifier and the Korean LLM market-analysis collectors
documented here until L7 all went with that set — nothing scheduled them, and
the only cron on the deploy host runs the TOS session wrappers in
`~/.config/kis-probes/` (`docs/runbooks/tos-paper-boot.md` §7.2).
