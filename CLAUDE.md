# CLAUDE.md - KIS Unified STS Operational Guide

This file is the compact operational source of truth for coding agents in this
repo. `docs/plans/` and `docs/superpowers/` hold the rationale for what runs
**today**; rationale for finished work lives in git history
(`git log --diff-filter=D -- docs/`), not in a kept file. Keep this file focused
on current runtime rules.

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
  is 24h, accumulation snapshots use 48h. Any other TTL is an exception that
  must be justified in a comment next to the YAML value (e.g. the night-futures
  close key uses 51h so Friday's capture survives to Monday premarket) and every
  freshness check on that key must read the same config value, not a second
  hardcoded bound.
- Timezone: trading/session logic and cron schedules are KST-native. Convert
  timestamps to KST before comparing against Korean market hours.
- Secrets: never commit real credentials, `.kis_token_*`, or filled `.env` files.
  Reference secrets through env vars and `${VAR}` in YAML.
- Stock swing exits are signal-driven. Do not add blanket EOD liquidation.
- Futures must preserve long/short symmetry. Entry/exit direction follows
  `signal_direction`.
- The real futures account is never funded with margin (operator directive): dev-stage mis-orders plus fast-compounding futures losses make real margin unacceptable. Never propose, script, or gate work on depositing margin. Real-money futures order paths — the P-R5 stage-2 probe and anything that emits real futures orders — are permanently blocked by policy; a zero-deposit preflight ABORT is a terminal verdict, not "pending funding". GET-only real reads are fine; measurements needing a real fill use the mock-derived bound.

## Current Runtime Architecture

The legacy trading runtime is **gone** (removal plan
`docs/plans/2026-11-07-legacy-removal-plan.md`, steps L1–L6, merged 2026-11).
What runs is the TOS kernel plus a read-only operator surface.

- `tos/`, `tools/tos_*`: the TOS kernel and the CP-3 measurement tools. See
  `tos/CLAUDE.md`. The spec corpus `tos-spec/` and its evidence `tos-evidence/`
  were retired on 2026-11-13 (`docs/plans/2026-11-13-tos-code-halving-plan.md`
  §S3); they are in git history.
- `tools/broker_probes/`: KIS capability probes (mock-account GET reads; order
  probes are interlocked by `config/futures_live.yaml::enabled`).
- `shared/`: what the surviving roots import — the CP-3 producer and Setup D
  witness path (backtest replay, Setup D decision, instruments, determinism, market-data
  store), KIS auth, indicators, config, storage, risk primitives, LLM
  analysis. `shared/execution/executor.py`, `shared/kis/client.py` and the
  packages only they pulled in (`shared/http`, `shared/observability`,
  `services/monitoring`) went on 2026-11-13 with the checker that was their only
  remaining reason to exist; `shared/execution/{tr_ids,contract_spec}.py` stay
  because the broker probes and the Setup D walk-forward script import them.
- `services/dashboard`: the FastAPI app behind Caddy. Its whole surface is
  `/api/tos/*`, `/health` and the OpenAPI docs.
- `strategy-builder-ui/`: the only frontend. It serves the `/tos` operator page,
  a `/` redirect to it, and the `/api` proxy.
- `config/`: YAML config for what remains — `config/tos_runtime/` tenant trees,
  `config/tos_*.yaml` gates, KIS/execution/risk/storage/streaming settings, and
  one strategy file (`config/strategies/futures/setup_d_vwap_reversion.yaml`,
  the legacy Setup D witness's).
- `cli/main.py`: `sts` entrypoint; the only command group is `sts tos`.
- `scripts/`: `scripts/tos/` tenant-tree rendering and the Setup D walk-forward
  script the legacy Setup D path loads by path.

## tos Kernel Boundary (two projects in one repo)

- `tos/` is the greenfield Trading Operating System kernel: its own
  distribution (`tos/pyproject.toml`), hermetic tests, pinned deps, and a
  CI-enforced **asymmetric import firewall**: nothing outside `tos/` may
  import `tos`; `tos/` may import only six ratified pure-commons packages
  (`shared.models`, `.indicators`, `.resilience`, `.utils`, `.exceptions`,
  `.determinism`); every other direct import is denied by the AST gate, and
  `.importlinter` additionally forbids transitive reach into the §2.3
  operational set (`shared.execution/kis/streaming/llm/storage/backtest`,
  `shared.config.secrets`, `services`, `cli`)
  (design: `docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md` §3).
- **tos work starts from `tos/CLAUDE.md`**, which lists the tos working set
  (`tos/`, `tools/tos_*`, `tests/tools/test_tos_*`,
  `docs/plans/*tos*`). Agents on tos tasks should
  search and edit inside that set and treat `shared/`, `services/`, and the
  frontend as out of scope.
- Repo split is deferred to the live gate (design §6.2) and, when it happens,
  removes the legacy runtime rather than moving `tos/`: Phase-0 governance is
  bound to this repo's git history. Do not relocate `tos/` as a side effect.
- CI: `tos-gate` (required) and `tos-firewall` run on every PR without path
  gating; the legacy `test` workflow is path-gated away from tos and docs-only
  changes and no longer runs the tos governance tests (they live in
  `tos-firewall.yml`).

## Official Layer Names

Use [system context](docs/architecture/tos-system-context.md) for these names:
`tos` = **TOS Kernel**; `tos_runtime` = **Application Runtime + Infrastructure
Adapters**; dashboard's TOS-facing surface = **Control Plane API (BFF)**;
`strategy-builder-ui` = **Product / Operator UI**. Strategy DSL, profiles, and
governed configuration are **Tenant Content**, not another execution authority.
Dashboard still serves legacy APIs; its TOS surface is currently read-only.
[Public interface catalog](docs/architecture/tos-public-interfaces.md) distinguishes
external contracts from runtime-internal ports. These names do not change the
import firewall or authorize trading.

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

The legacy stock and futures runtimes no longer exist. There is no stock
pipeline, no futures orchestrator, no decoupled futures services, and no strategy
registry roster: L6 deleted every `shared/strategy/entry/*` module, so
`EntryRegistry` is empty and no strategy can be built. The only trading-shaped
thing that runs is the TOS CP-3 tenant session (`tos/`), which is paper/synthetic
except for the KIS **mock** stock tenant.

What is still true and still enforced:

- **No legacy live-futures runtime remains** (the `live_mode_guard` module and
  the order router are gone). One real-money order path does remain:
  `tools/broker_probes/probes_real_order.py` (P-R5 stage 2), permanently blocked
  by policy (see Non-Negotiable Rules). Every futures order probe calls
  `tools/broker_probes/common.py::assert_no_live_futures_config`, which refuses
  to run while `config/futures_live.yaml::enabled` is true — that is why the file
  stays. Absence is not what stops a live futures order here; policy is.
- **Real futures account is never funded** — see Non-Negotiable Rules.
  Real-money order probes (P-R5 stage 2) are policy-blocked.
- Futures ML/RL/TFT runtime paths are removed. Do not reintroduce `sts rl *`,
  `sts tft *`, `shared/ml/rl`, `shared/ml/tft`, `RLMPPOEntry`, `RLMPPOExit`, or
  RL/TFT config profiles.
- Futures strategy expansion should use LLM market context plus explicit
  indicator/strategy-native rules such as Williams %R, RSI, MACD, ATR, momentum
  decay, or Setup target exits. (The modules that implemented these were removed
  in L1–L6; the rule is kept for future work.)
- Three-stage exit is stock-only unless a future design explicitly generalizes
  it. (The stock runtime that drove it was removed in L1–L6, and
  `shared/strategy/exit/three_stage.py` itself went in L7; the rule is kept for
  future work.)
- `shared/decision/setups/vwap_reversion.py` and its dependencies are the
  **legacy Setup D witness**: `tools/tos_cp3/produce_fields.py` still drives this
  implementation bar by bar to produce the CP-3 field stream, until the P2-c
  producer switch lands. Keep it byte-identical until `TOS_PAPER_READY`
  (`docs/plans/2026-11-07-legacy-removal-plan.md` §2, operator decision 3). The
  post-session **B3 대조** that also read it retired on 2026-11-13
  (`docs/plans/2026-11-11-tos-platform-roadmap.md` §7 결정 3), its condition —
  P2-b 동등성(626,745 셀 0 불일치, #1065 · #1066) — being met.
- The retired cutover runbooks (`stock-pipeline-cutover-m5d.md`,
  `futures-pipeline-cutover-f9.md`, `paper-live-code-separation.md`) were deleted
  on 2026-11-13 with the rest of the legacy-runtime docs; they are history, not
  procedure. Their code last existed at tag `legacy-final` (`6fc17c0f8d25`).

## Storage And Data

- Runtime ledger: the legacy SQLite WAL ledger (`shared/storage/runtime_ledger.py`)
  fell outside the surviving import closure and went in L7
  (`docs/plans/2026-11-07-legacy-removal-plan.md` §3). There is no legacy runtime
  ledger any more; `tos_runtime` owns its own per-session stores.
- Runtime streams/state: Redis DB 1.
- Historical market data: Parquet/DuckDB through
  `shared/storage/market_data_store.py`.
- ClickHouse is not an active runtime, collection, backtest, or compose
  dependency. Do not add new direct ClickHouse usage.
- Backtests must avoid look-ahead bias. Use `LookaheadGuard` and keep indicator
  inputs bounded by the current context timestamp.

## Strategy Implementation Pattern (retired)

Strategy components used to register through `shared/strategy/registry.py` and be
composed by `StrategyFactory` into a `TradingStrategy`. L6 deleted every
`shared/strategy/entry/*` module, which left the entry roster empty, and L7
deleted `registry.py`, `factory.py`, `builtin_components.py` and the remaining
exits and sizers — all of them outside the surviving import closure
(`docs/plans/2026-11-07-legacy-removal-plan.md` §3).

What is left of `shared/strategy/` is `base.py` (the abstract classes),
`market_data.py`, `market_time.py`, and `exit/setup_target_exit.py` — the legacy
Setup D witness's exit and the helpers it reaches. The only strategy YAML left is
`config/strategies/futures/setup_d_vwap_reversion.yaml`, that witness's input.

Execution authority today is the TOS kernel, where a strategy is Tenant Content
(DSL + profile) under `config/tos_runtime/`. Do not reintroduce the registry here.

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
     deep-reasoner pipeline: the session model reads the repo and types the plan
     directly; the operator reviews it. A Codex plan critique via `codex-gate` is
     not part of authoring — the operator requests it explicitly when wanted.
     Routine fixes, config edits, and doc changes go straight to implementation.
- **Do not reinvent the wheel.** A bespoke parser/tokenizer/checker is the
  last resort, not the first move; prefer proven tooling and existing modules.
- **Phase-0 판정 장치는 퇴역했다 (2026-11-12,
  `docs/plans/2026-11-12-phase0-retirement-plan.md`).** 완료 계약서, 그 인덱스
  도구(`tos_contract_index.py`), 완료/계약 검사기(`tos_completion_status.py` ·
  `tos_contract_check.py`), U-17 예방 통제, 그리고 그들의 CI 단계가 전부
  삭제됐다 — Phase 0 는 2026-10-22 서명(#920)으로 닫혔고 완료 기준은
  `TOS_PAPER_READY` 다. 내용은 git 이력에 그대로 있다
  (`git log --diff-filter=D -- docs/plans/2026-08-12-*`).

## Development Commands

```bash
pip install -e ".[dev]"
pytest tests/ -q                  # tests/tools is ~60% of the wall time
ruff check .
black --check .
mypy shared/ --ignore-missing-imports --no-error-summary
docker compose up -d              # dashboard + strategy-builder-ui + caddy + redis + prometheus
sts tos status                    # the one-page operator status board
sts tos inspect <session>         # per-bar: fields, per-compare pass/fail, decision, halt
```

TOS checkers (what CI gates on — see `.github/workflows/tos-{gate,firewall}.yml`):

```bash
python tools/tos_firewall_check.py
python tools/tos_redigest.py --check   # the `tos-gate` required check, since 2026-11-12
python tools/tos_size_budget.py --check
mypy tools/tos_*.py tools/tos_cp3 --ignore-missing-imports --explicit-package-bases  # tos-firewall-static runs this
# `lint-imports` as CI runs it (.github/workflows/tos-firewall.yml): plain, after
# an editable install of the root project and tos/runtime. Without that install
# the contracts' root packages do not resolve; a local shortcut is
# `PYTHONPATH=.:tos/src:tos/runtime/src lint-imports`, which is NOT what gates.
lint-imports
```

Frontend:

```bash
cd strategy-builder-ui
npm run dev
npm run build
npm run lint
npm test
```

## Harness: Trading Platform Agent Team

**Goal:** Route platform work to specialist agents, and keep adjudication (code and
plan review) in an independent model lane.

**Triggers:**

- Platform work (strategy, ops, frontend, DevX, data, execution) → use the
  `trading-harness` skill.
- **Codex code scope is limited to hard-to-reverse paths (operator directive
  2026-09-11; supersedes the blanket exclusion of 2026-09-04).** Live order paths,
  money movement, risk limits, auth and credential handling, DB migrations, and data
  purge may go to Codex once the operator approves scope and cost. Every other code
  diff or PR stays with the Claude-side pass (`code-reviewer` / `review-synthesizer`,
  separate from the author) and is never sent to Codex. `codex-gate` also remains for
  plan critiques and other non-code artifacts. All of it is opt-in — finishing an
  implementation, passing tests, or making a commit is not a trigger. Reason: the
  2026-09-04 exclusion was aimed at paid-call frequency; bounding the scope keeps that
  cost down without leaving Claude to approve its own code.
- Scope every gate run to the diff or plan under question. Do not re-adjudicate
  already-disposed material; a fresh full-corpus review is an operator decision.
- Keep the OpenAI Codex Claude Code plugin enabled, but keep its optional
  stop-time review gate disabled. Run scoped reviews explicitly through
  `codex-gate`; do not launch a fresh generic Codex task on every Claude stop.
- Plan *authoring* is the session model's solo job (see Development Discipline);
  plan *adjudication* by Codex is available on explicit operator request only.
- Simple questions can be answered directly without the harness.

**Adjudication override:** A Codex verdict never overrides the Non-Negotiable Rules
above. Reject any finding that would violate them and record the reason.

**Review policy (operator directive 2026-10-22, `docs/plans/2026-10-22-tos-rescope-plan.md` §5).**
Review effort follows risk, rounds are capped, and judging machinery may not outgrow
the thing it judges. These rules govern every PR in this repo, TOS included.

- **R1 — review by risk grade.** State the grade and a one-line reason in the PR body.
  - **A**: live/broker order sending, credentials and auth, risk limits, data purge,
    DB migrations. One independent Claude-side review, plus Codex when the operator
    approves scope and cost (the Codex scope rule above is unchanged).
  - **B**: all other code, and any document that records facts an operator decision
    rests on (permissions, branch protection, order paths). One Claude-side review.
  - **C**: other docs, measurement records, evidence PRs. No review lane — the author
    checks each cited value against its source, then merges once CI is green.
- **R2 — two rounds at most.** Findings left after round 2 become issues and the PR
  merges. A LOW is fixed and merged without another review round.
- **R3 — what blocks.** Only a HIGH or worse that names a concrete failing input
  ("this input → this wrong result") blocks a merge. Wording, citation line numbers,
  and phrasing precision never block.
- **R4 — plan size.** A new plan document is at most 300 lines; past that, split the
  scope. Plans are not sent to a review lane — the operator reads and approves them.
- **R5 — cost of a new guard.** A new checker, control group, or register needs one
  real incident it would have stopped, written next to it. A hypothetical attack path
  alone does not justify one.
- **R6 — no meta-judgment.** Do not build judging machinery about judging machinery
  ("completion conditions for the completion conditions"). Completion is a few
  measurable sentences, as in the rescope plan §2.
- **R7 — light measurement records.** A session or measurement record is one table:
  command, resulting numbers, log path. Citing log line numbers is not required.

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
| 2026-09-04 | **Codex review excludes code** — `codex-gate` / `codex-reviewer` return `SCOPE_EXCLUDED` for code diffs; code review is the Claude-side fallback lane; Codex plan critique stays available on explicit operator request · **plans/specs/roadmaps authored solo by the session model (Opus 5 [1m] / Fable 5.1 [1m])**, no planner/deep-reasoner pipeline | CLAUDE.md, codex-gate, codex-reviewer, codex-plan-reviewer | Operator directive — paid external calls too frequent, spec authoring too slow |
| 2026-09-11 | **Codex code scope reopened, bounded** — hard-to-reverse paths (live order paths, money movement, risk limits, auth/credentials, DB migrations, data purge) may go to `codex-gate` / `codex-reviewer` once the operator approves scope and cost; every other code diff stays with the Claude-side lane. Supersedes the 2026-09-04 blanket exclusion | CLAUDE.md, codex-gate, codex-reviewer, codex-plan-reviewer | A week with zero cross-model review of code left Claude approving its own code; cost is bounded by scope, not by prohibition |
| 2026-10-22 | **Review policy R1–R7** — review by risk grade (A/B/C, docs and evidence PRs need no review lane), at most two rounds, only a HIGH with a concrete failing input blocks, plans ≤300 lines, a new guard needs a real incident, no meta-judgment, one-table measurement records · Phase-0 contract becomes a historical record (TOS rescope) | CLAUDE.md | Three months of TOS work moved zero Evidence rows; the Phase-0 contract grew to 10,723 lines over 81 reviews and one docs PR took four rounds — the review process, not the code, was the bottleneck |
| 2026-08-30 | Doc-only fix to the model-lanes paragraph: it claimed every audit lens runs on Sonnet 5, contradicting the 2026-08-25 row and the actual frontmatter (`architecture-auditor`/`security-auditor` are Opus) | CLAUDE.md | Cost audit found the prose had drifted from the pinned `model:` values; agent files unchanged |
| 2026-11-12 | **Phase-0 판정 장치 퇴역** — 완료 계약서·인덱스 도구·완료/계약 검사기·U-17 예방 통제와 그 CI 단계를 삭제. 필수 체크 `tos-gate` 는 이름을 유지하고 내용만 `tos_redigest --check`(살아 있는 핀 게이트)로 교체 | CLAUDE.md, tos/CLAUDE.md, `.github/workflows/tos-{gate,firewall,test}.yml`, `tools/`, `tos-spec/`, `docs/` | Phase 0 는 2026-10-22 서명(#920)으로 닫혔고 완료 기준은 `TOS_PAPER_READY` 다. 역사 기록이 된 판정 장치가 PR 마다 수 분의 CI 와 저장소 부피의 큰 몫을 계속 먹었다 (계획: `docs/plans/2026-11-12-phase0-retirement-plan.md`) |
| 2026-11-14 | **역사 계획·증거 은퇴 (S3/§4)** — 끝난 계획 35건과 측정 캠페인 증거 5건, 그리고 「historical rationale 는 `docs/plans/` 에 둔다」는 문장을 「끝난 근거는 git 이력에 둔다」로 교체 | CLAUDE.md, `docs/` | 운영자 지시: 문서 부피 절반화. `docs/` 68,135 → 38,485 줄 (계획: `docs/plans/2026-11-13-tos-code-halving-plan.md` §S3/§4) |
| 2026-11-13 | **명세·증거 코퍼스 은퇴 (S3)** — `tos-spec/`(66k 줄) · `tos-evidence/`(25k) 전체와 그들만 읽던 도구(`tos_spec_status` · `tos_evidence_run` · `tos_profile_census`)·테스트·CI 단계(mdBook 빌드, 코퍼스 무결성), `BROKER-TRANSPORT-SYMBOLS.{csv,md}`, 명세 앵커 커널 테스트를 삭제. 그 검사기가 유일한 존속 이유였던 `shared/execution/executor.py` · `shared/kis/client.py` 와 그 폐쇄(`shared/http` · `shared/observability` · `services/monitoring`)도 함께 삭제 | CLAUDE.md, tos/CLAUDE.md, `.github/workflows/tos-{firewall,test}.yml`, `tools/`, `tos-spec/`, `tos-evidence/`, `shared/`, `services/`, `docs/` | 운영자 지시: 코드·문서 부피 절반화 (계획: `docs/plans/2026-11-13-tos-code-halving-plan.md` §S3) |

## Documentation Map

- Project snapshot: `docs/PROJECT_STATUS.md`
- Documentation index: `docs/INDEX.md`
- Plan index: `docs/plans/INDEX.md`
- Superpowers plan archive/index: `docs/superpowers/plans/INDEX.md`
- Port policy: `docs/ports.md`
- Runbook index: `README.md` § Runbooks
- 2026-11-13 에 레거시 런타임 시절의 런북·루트 문서와 2026-07~08 RFC 설계
  코퍼스를 지웠다 (`docs/plans/2026-11-13-tos-code-halving-plan.md` §S3). 그중
  은퇴 런북(`stock-pipeline-cutover-m5d` · `futures-pipeline-cutover-f9` ·
  `paper-live-code-separation`)과 `docs/runtime_storage_architecture.md` ·
  `docs/ROADMAP.md` 를 포함해 전부 git 이력에 있다:
  `git log --diff-filter=D -- docs/`.
- 2026-11-14 에 끝난 계획 35건(2026-07~09 커널·런타임 착지 기록 · 상위 제안표 ·
  측정 계획)과 끝난 측정 캠페인 증거 5건을 지웠다 (같은 계획 §S3/§4). 남긴
  계획은 지금 도는 것의 결정 기록과 `TOS_PAPER_READY` 기준, 방화벽 설계 계약뿐
  이다. 코드·설정에 남은 은퇴 문서 인용은 git 이력을 가리키는 주석이다.
