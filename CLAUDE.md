# CLAUDE.md - KIS Unified STS Operational Guide

This file is the compact operational source of truth for coding agents in this
repo. Keep historical rationale in `docs/plans/` or `docs/superpowers/`; keep
this file focused on current runtime rules.

If the deploy-host memory file exists at
`/home/deploy/.claude/projects/-home-deploy-project-kis-unified-sts/memory/MEMORY.md`,
read it as supplemental operational memory. Local checkouts may not have it.

## Core Objective

Optimize trading entry and exit timing through a configuration-driven loop:

```text
strategy config -> backtest -> tracking/optimization -> paper/live validation -> feedback
```

## Non-Negotiable Rules

- Configuration-driven only: thresholds, symbols, risk values, ports, Redis DBs,
  schedules, and feature gates belong in YAML/env/config files, not hardcoded
  branches.
- DRY: shared behavior belongs in `shared/`; avoid duplicating logic in
  per-asset service code.
- Redis: use DB 1 for this project (`redis://localhost:6379/1` unless an env file
  intentionally overrides it). New Redis keys need TTLs; default operational TTL
  is 24h, accumulation snapshots use 48h.
- Timezone: trading/session logic and cron schedules are KST-native. Convert
  timestamps to KST before comparing against Korean market hours.
- Secrets: never commit real credentials, `.kis_token_*`, or filled `.env` files.
  Reference secrets through env vars and `${VAR}` in YAML.
- Stock swing exits are signal-driven. Do not add blanket EOD liquidation.
- Futures must preserve long/short symmetry. Entry/exit direction follows
  `signal_direction`.
- The real futures account is never funded with margin (operator directive): dev-stage mis-orders plus fast-compounding futures losses make real margin unacceptable. Never propose, script, or gate work on depositing margin. Real-money futures order paths — the P-R5 stage-2 probe and anything that emits real futures orders — are permanently blocked by policy; a zero-deposit preflight ABORT is a terminal verdict, not "pending funding". GET-only real reads are fine; measurements needing a real fill use the mock-derived bound.

## Current Runtime Architecture

- `shared/`: reusable strategy, execution, indicators, streaming, storage,
  forecasting, risk, models, and config logic.
- `services/`: runtime processes.
  - `services/trading/`: monolithic orchestrator, still used for futures paper/live
    unless a decoupled futures cutover is explicitly performed.
  - `services/stock_strategy`, `stock_risk_filter`, `stock_order_router`,
    `stock_exit`, `stock_monitor`: decoupled stock M4/M5 pipeline.
  - `services/market_ingest`, `decision_engine`, `risk_filter`, `order_router`,
    `futures_monitor`, `kill_switch`: decoupled futures pipeline services.
  - `services/dashboard`: the single FastAPI API/metrics app behind Caddy.
- `strategy-builder-ui/`: the only frontend. It serves Cockpit, positions,
  signals, trades, experiments, strategy builder, and executor pages.
- `config/`: YAML strategy/risk/execution/storage/infra config.
- `cli/main.py`: `sts` command entrypoint.

## Web/API Surface

- Caddy is the only host-published web entry. Default host port is
  `DASHBOARD_HOST_PORT=5081`; local/operator env files may override it. Caddy
  still listens on container/internal `:5080`.
- Internal Docker ports stay private: `dashboard:8001` and
  `strategy-builder-ui:3100`.
- Do not resurrect the old `services/api` REST gateway or host `:8000` route.
  New API routes go under `services/dashboard`.
- Host port 3000 belongs to another local project and is not used here.

## Trading Runtime Rules

### Stock

- Standard stock paper flow is the decoupled Compose pipeline:
  `stock-ingest` + `stock-pipeline`.
- After stock cutover, block the monolithic stock orchestrator with
  `STOCK_ORCHESTRATOR_ENABLED=false`.
- Rollback path: restore `STOCK_ORCHESTRATOR_ENABLED=true` and follow
  `docs/runbooks/stock-pipeline-cutover-m5d.md`.
- Active stock behavior is screener/universe driven plus configured strategies
  such as `bb_reversion`, `opening_volume_surge`, `volume_accumulation`, and
  newer registry strategies as enabled in YAML.
- Three-stage exit is stock-only unless a future design explicitly generalizes it.

### Futures

- Current primary futures strategy path is Setup A/C:
  `setup_a_gap_reversion` and `setup_c_event_reaction`.
- Futures ML/RL/TFT runtime paths are removed. Do not reintroduce `sts rl *`,
  `sts tft *`, `shared/ml/rl`, `shared/ml/tft`, `RLMPPOEntry`, `RLMPPOExit`, or
  RL/TFT config profiles.
- Futures strategy expansion should use LLM market context plus explicit
  indicator/strategy-native rules such as Williams %R, RSI, MACD, ATR, momentum
  decay, or Setup target exits.
- Live futures is guarded by `config/futures_live.yaml::enabled` plus Redis flag
  `futures:live:suspended`. See `shared/execution/live_mode_guard.py`.
- Decoupled futures services are available through Compose profiles
  `futures-ingest`, `futures-pipeline`, and `futures-killswitch`; perform cutover
  only via `docs/runbooks/futures-pipeline-cutover-f9.md`.
- Real futures account is never funded — see Non-Negotiable Rules. Real-money order probes (P-R5 stage 2) are policy-blocked; paper stays VirtualBroker (real orders 0).

## Storage And Data

- Runtime ledger: SQLite WAL via `shared/storage/runtime_ledger.py`.
- Runtime streams/state: Redis DB 1.
- Historical market data: Parquet/DuckDB through
  `shared/storage/market_data_store.py`.
- ClickHouse is not an active runtime, collection, backtest, or compose
  dependency. Do not add new direct ClickHouse usage.
- Backtests must avoid look-ahead bias. Use `LookaheadGuard` and keep indicator
  inputs bounded by the current context timestamp.

## Strategy Implementation Pattern

- Strategy components register through `shared/strategy/registry.py`.
- Entry generators, exit generators, and position sizers are composed through
  `TradingStrategy`; keep asset-specific code thin.
- New strategy work should include:
  1. YAML config under `config/strategies/{stock,futures}/`.
  2. Shared implementation under `shared/strategy/...`.
  3. Registry wiring and focused unit tests.
  4. Backtest or paper validation artifacts when behavior changes materially.

## Development Discipline (operator directive, 2026-08-19)

- **Research first, then plan, then implement.** Before building any feature:
  1. Survey libraries, frameworks, and standard tools that already solve the
     problem (official docs first — `document-specialist` / Context7).
  2. Check what this repo already implements (`shared/`, `tos/`, `tools/`,
     `services/`) — reuse or extend before writing new surfaces.
  3. Write the plan (reuse targets, rejected alternatives with a one-line
     reason, minimal new surface), then implement. **Goals, milestones,
     roadmaps, and specs are written solo by the session model (Opus 5 [1m] or
     Fable 5.1 [1m]) — operator directive 2026-09-04.** No planner / architect /
     deep-reasoner pipeline and no `codex-gate` on plan documents: the session
     model reads the repo and types the plan directly; the operator reviews it.
     Routine fixes, config edits, and doc changes go straight to implementation.
- **Do not reinvent the wheel.** A bespoke parser/tokenizer/checker is the
  last resort, not the first move; prefer proven tooling and existing modules.
- **Read the index before the contract (operator directive, 2026-09-01).** Any
  task touching the Phase-0 completion contract
  (`docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`, 10k lines /
  1.3MB) starts with the derived index, not the document:

  ```bash
  python tools/tos_contract_index.py --locate S-26     # section/identifier -> line range
  python tools/tos_contract_index.py                   # full derived map
  ```

  Locate the identifier or section first, then read only that range. Do not scan
  the whole file, and do not summarize it — this arc failed seven consecutive
  reviews writing summaries (`dad94fd3`); the disposition that passed was
  "point at the source, do not paraphrase". The index is a generated artifact:
  if `--check` reports stale, regenerate it rather than trusting it.
  The contract body is frozen and blob-bound (`bound_set_digest`) — never edit
  it as a side effect of other work; any byte change resets the S-26 closure
  counter and blocks D0-A entry.

## Development Commands

```bash
pip install -e ".[dev]"
pytest tests/ -v --cov=shared --cov=services
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

## Harness: Trading Platform Agent Team

**Goal:** Route platform work to specialist agents, and keep adjudication (code and
plan review) in an independent model lane.

**Triggers:**

- Platform work (strategy, ops, frontend, DevX, data, execution) → use the
  `trading-harness` skill.
- **Codex review excludes code and plans (operator directive 2026-09-04).**
  Code diffs, PRs, implementation results, and plan/spec documents are never
  sent to Codex. Code review is a Claude-side pass (`code-reviewer` /
  `review-synthesizer`, separate from the author); plans are reviewed by the
  operator. `codex-gate` remains only for non-code artifacts the operator names
  explicitly, still opt-in — finishing an implementation, passing tests, or
  making a commit is not a trigger. Reason: paid external calls had become too
  frequent.
- Scope every gate run to the diff or plan under question. Do not re-adjudicate
  already-disposed material; a fresh full-corpus review is an operator decision.
- Keep the OpenAI Codex Claude Code plugin enabled, but keep its optional
  stop-time review gate disabled. Run scoped reviews explicitly through
  `codex-gate`; do not launch a fresh generic Codex task on every Claude stop.
- Plan *authoring* is the session model's solo job (see Development Discipline);
  plan *adjudication* by Codex was withdrawn on 2026-09-04.
- Simple questions can be answered directly without the harness.

**Adjudication override:** A Codex verdict never overrides the Non-Negotiable Rules
above. Reject any finding that would violate them and record the reason.

**Model lanes (cost discipline):** orchestration and `deep-reasoner` run on Opus;
every implementation, test, debugging, and frontend agent runs on Sonnet 5, and so
do the audit lenses except `architecture-auditor` and `security-auditor`, which
stay on Opus along with the fallback review lane (`code-reviewer`,
`review-synthesizer`) (`model:` in each `.claude/agents/*.md` file governs — do not
override at call time); `runner`-class chores run on Haiku; the Codex forwarders
stay on Haiku because they only relay Codex stdout. Opus for a coding agent is an exception that
needs a stated reason (sonnet actually failed, or the change is hard to reverse).
The `sonnet -> Opus` env remap in `~/.claude/fable/env.sh` was removed — sonnet
means sonnet.

Agent roster, skill list, directory layout, and execution detail live under
`.claude/` — not here.

### Harness Change Log

| Date | Change | Scope | Reason |
| --- | --- | --- | --- |
| 2026-03-12 | Initial harness setup (commit `531ec227`) | all | - |
| 2026-08-11 | Adjudication moved to Codex — added `codex-reviewer` / `codex-plan-reviewer` / `codex-gate`; demoted `code-reviewer` and `review-synthesizer` to fallback-only; replaced the `code-audit` fan-in | `agents/`, `skills/` | Prevent self-approval and secure cross-model independent adjudication |
| 2026-08-21 | Disabled per-turn Codex stop review; kept explicit scoped `codex-gate` reviews and moved thin reviewer forwarders to Haiku | review harness | Prevent duplicate fresh Codex tasks, long Stop-hook stalls, and avoidable Claude token use |
| 2026-08-25 | Cost rebalance — pinned `model:` per agent (Sonnet 5 for execution/audit lenses, Opus only for `architecture-auditor`, `security-auditor`, and the fallback review lane), removed the global `sonnet -> Opus` env remap, made Codex adjudication explicitly operator-triggered | `agents/`, `~/.claude/fable/`, harness docs | Every subagent was silently running on Opus; review ran more often than it was asked for |
| 2026-09-04 | **Codex review excludes code and plans** — `codex-gate` / `codex-reviewer` / `codex-plan-reviewer` return `SCOPE_EXCLUDED` for code diffs and plan docs; code review is the Claude-side fallback lane, plan review is the operator · **plans/specs/roadmaps authored solo by the session model (Opus 5 [1m] / Fable 5.1 [1m])**, no planner/deep-reasoner pipeline | CLAUDE.md, codex-gate, codex-reviewer, codex-plan-reviewer | Operator directive — paid external calls too frequent, spec authoring too slow |
| 2026-08-30 | Doc-only fix to the model-lanes paragraph: it claimed every audit lens runs on Sonnet 5, contradicting the 2026-08-25 row and the actual frontmatter (`architecture-auditor`/`security-auditor` are Opus) | CLAUDE.md | Cost audit found the prose had drifted from the pinned `model:` values; agent files unchanged |

## Documentation Map

- Project snapshot: `docs/PROJECT_STATUS.md`
- Documentation index: `docs/INDEX.md`
- Plan index: `docs/plans/INDEX.md`
- Superpowers plan archive/index: `docs/superpowers/plans/INDEX.md`
- Port policy: `docs/ports.md`
- Runtime storage: `docs/runtime_storage_architecture.md`
- Stock cutover: `docs/runbooks/stock-pipeline-cutover-m5d.md`
- Futures cutover: `docs/runbooks/futures-pipeline-cutover-f9.md`
- Paper/live source separation: `docs/runbooks/paper-live-code-separation.md`
