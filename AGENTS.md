# Repository Guidelines

## Primary References
Treat `CLAUDE.md` and project memory (`/home/deploy/.claude/projects/-home-deploy-project-kis-unified-sts/memory/MEMORY.md`) as operational source-of-truth for trading/runtime rules.

## Project Structure & Module Organization
- `shared/`: core reusable logic (strategy, execution, indicators, streaming, models).
- `services/`: runtime apps (`trading/`, `api/`, `dashboard/`, `monitoring/`).
- `domains/`: domain-specific code (keep minimal; prefer shared implementations).
- `config/`: YAML configs (`strategies/{stock,futures}`, `exit/`, `ml/`, infra configs).
- `cli/main.py`: `sts` command entrypoint.
- `tests/unit`, `tests/integration`: backend test suites.
- `strategy-builder-ui/`: Next.js (App Router) UI — the single frontend. Serves the dashboard (Cockpit/positions/signals/trades) and the strategy builder/executor.

## Architecture & Trading Rules
- Configuration-driven only: do not hardcode thresholds, symbols, or risk values; place them in YAML.
- Keep code DRY: shared behavior belongs in `shared/`, not duplicated by asset domain.
- Standard runtime path is `services/trading/orchestrator.py` (including futures RL paper/live flow).
- Futures: `rl_mppo` entry + `rl_mppo_exit` policy are default; preserve long/short symmetry.
- Stock swing behavior: do not force blanket EOD liquidation; exits should remain strategy-signal based.

## Infrastructure Rules (Redis/Caching)
- Use Redis DB 1 only (`REDIS_URL=redis://localhost:6379/1`); DB 0 is reserved elsewhere.
- New Redis keys must define TTL. Default operational TTL is 24h; accumulation snapshots use 48h.
- For containerized services, Redis host binding must allow Docker access (`0.0.0.0`).

## Build, Test, and Development Commands
- `pip install -e ".[dev]"`: install backend + dev tools.
- `pytest tests/ -v --cov=shared --cov=services --cov=domains`: CI-aligned backend tests.
- `ruff check .` / `black --check .` / `mypy shared/ --ignore-missing-imports --no-error-summary`.
- `docker compose up -d`: start local stack.
- `sts --help`: inspect CLI flows (trade, paper, backtest, optimize, mlflow).
- Frontend: `cd strategy-builder-ui && npm run dev|build|lint`.

## Testing, Commits, and PRs
- Test naming: `tests/**/test_*.py`; use markers `unit`, `integration`, `slow`, `backtest`.
- Integration tests should run with Redis on DB 1.
- Commit style follows current history: `feat:`, `fix:`, `docs:`, `perf:`, `refactor:`.
- PRs must include scope, linked issues, config/env changes, and validation artifacts (test output, dashboard screenshots when UI changes).

## Security & Config Hygiene
- Copy `.env.example` to `.env`; never commit secrets or `.kis_token_*` files.
- Keep credentials in env vars and reference via `${VAR}` in YAML.
