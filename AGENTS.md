# Repository Guidelines

This repository keeps detailed operational rules in [CLAUDE.md](CLAUDE.md).
Read that file first for trading/runtime constraints. This file is intentionally
thin to avoid duplicated instructions drifting over time.

## Source Of Truth

- Current runtime/coding rules: [CLAUDE.md](CLAUDE.md)
- Project snapshot: [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)
- Documentation index: [docs/INDEX.md](docs/INDEX.md)
- Plan index: [docs/plans/INDEX.md](docs/plans/INDEX.md)
- Deploy-host memory, when present:
  `/home/deploy/.claude/projects/-home-deploy-project-kis-unified-sts/memory/MEMORY.md`

## Working Rules

- Keep code configuration-driven; put thresholds, symbols, risk values, Redis DBs,
  ports, and schedules in YAML/env/config files.
- Put shared behavior in `shared/`; keep `domains/` and per-service code thin.
- Use Redis DB 1 for this project and define TTLs for new Redis keys.
- Preserve stock swing behavior: no blanket EOD liquidation.
- Preserve futures long/short symmetry and do not reintroduce removed ML/RL/TFT
  runtime paths.
- Do not commit secrets, `.kis_token_*`, or filled `.env` files.

## Common Commands

```bash
pip install -e ".[dev]"
pytest tests/ -v --cov=shared --cov=services --cov=domains
ruff check .
black --check .
mypy shared/ --ignore-missing-imports --no-error-summary
docker compose up -d
sts --help
```

Frontend:

```bash
cd strategy-builder-ui
npm run dev
npm run build
npm run lint
```
