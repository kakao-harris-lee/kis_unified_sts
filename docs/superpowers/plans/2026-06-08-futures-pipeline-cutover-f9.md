# F-9 Futures Cutover — Dormant Compose Wiring + Runbook — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (or direct execution by the controller for this declarative-config + docs change). Steps use `- [ ]` checkboxes.

**Goal:** Wire the decoupled futures daemon chain into `docker-compose.yml` as default-off `futures-ingest` / `futures-pipeline` / `futures-killswitch` profiles (dormant, shadow-default), add the mode knobs to the env templates, guard the shape with a compose test, and write the cutover runbook. No live behavior change; fully reversible.

**Architecture:** Mirror the stock `stock-ingest` / `stock-pipeline` profiles. Single `FUTURES_PIPELINE_MODE` knob (shadow→live) for decision/risk/monitor + a separate `FUTURES_ORDER_ROUTER_MODE` (paper→live) for order_router. Shadow reuses the orchestrator's `raw_data`; futures-ingest is cutover-only.

**Tech Stack:** docker-compose YAML, pytest (`/home/deploy/project/kis_unified_sts/.venv/bin/pytest`, cwd=worktree), Markdown runbook.

**Spec:** `docs/superpowers/specs/2026-06-08-futures-pipeline-cutover-f9-design.md`
**Templates to mirror:** `docker-compose.yml` (stock-* services, anchors), `docs/runbooks/stock-pipeline-cutover-m5d.md`, `tests/unit/test_compose_runtime_env.py::test_stock_pipeline_compose_services_are_profile_gated`.

---

### Task 1: Rename the shared pipeline anchor (DRY)

**Files:** Modify `docker-compose.yml`.

- [ ] **Step 1: Rename the anchor definition.** Change line ~59
  `x-stock-pipeline-service: &stock-pipeline-service` → `x-pipeline-service: &pipeline-service`.

- [ ] **Step 2: Repoint the 6 stock services.** Replace every `<<: *stock-pipeline-service`
  (in `stock-market-ingest`, `stock-strategy`, `stock-risk-filter`, `stock-order-router`,
  `stock-exit`, `stock-monitor`) with `<<: *pipeline-service`.

- [ ] **Step 3: Validate byte-identical resolution.**

```bash
cd /tmp/wt-f9-futures-cutover
git show HEAD:docker-compose.yml > /tmp/compose_before.yml
docker compose -f /tmp/compose_before.yml config 2>/dev/null > /tmp/cfg_before.txt || true
docker compose -f docker-compose.yml config 2>/dev/null > /tmp/cfg_after.txt || true
diff /tmp/cfg_before.txt /tmp/cfg_after.txt && echo "IDENTICAL (anchor rename safe)"
```
Expected: `IDENTICAL`. (If docker is unavailable, instead confirm no `*stock-pipeline-service` remains: `grep -c "stock-pipeline-service" docker-compose.yml` → 0.)

- [ ] **Step 4: Commit.**

```bash
git add docker-compose.yml
git commit -m "refactor(compose): rename stock-pipeline anchor to generic pipeline-service"
```

---

### Task 2: Add futures pipeline services (dormant profiles)

**Files:** Modify `docker-compose.yml` — insert after the `stock-monitor` service block (before the `dashboard` section comment).

- [ ] **Step 1: Insert the futures services block.**

```yaml
  # =============================================================================
  # Futures decoupled pipeline daemons (Compose-managed, DORMANT by default).
  # Profile-gated: nothing starts unless a futures-* profile is passed to
  # `docker compose up`. Modes default to the SAFE end (shadow / paper). Cutover
  # is operator-gated (Phase-5 Gate 1-3 + written approval) — see
  # docs/runbooks/futures-pipeline-cutover-f9.md. Double-trade guard:
  # set FUTURES_ORCHESTRATOR_ENABLED=false on trader-futures at cutover.
  #
  #   Shadow run (reuses trader-futures' raw_data; NO ingest):
  #     docker compose --profile futures-pipeline up -d \
  #       futures-decision-engine futures-risk-filter futures-order-router futures-monitor
  #   Cutover (live): also bring up futures-ingest + futures-killswitch and set
  #     FUTURES_PIPELINE_MODE=live FUTURES_ORDER_ROUTER_MODE=live.
  # =============================================================================
  futures-market-ingest:
    <<: *pipeline-service
    container_name: ${COMPOSE_PROJECT_NAME:-kis}-futures-market-ingest
    profiles: ["futures-ingest"]
    command: ["python", "-m", "services.market_ingest.main"]
    environment:
      <<: [*redis-runtime-env, *runtime-storage-env, *kis-runtime-env]
      INGEST_ASSET: "futures"
      INGEST_REFRESH_SECONDS: "${FUTURES_INGEST_REFRESH_SECONDS:-3600}"

  futures-decision-engine:
    <<: *pipeline-service
    container_name: ${COMPOSE_PROJECT_NAME:-kis}-futures-decision-engine
    profiles: ["futures-pipeline"]
    command: ["python", "-m", "services.decision_engine.main"]
    environment:
      <<: [*redis-runtime-env, *runtime-storage-env]
      FUTURES_STRATEGY_DAEMON: "${FUTURES_PIPELINE_MODE:-shadow}"
      FUTURES_STRATEGY_SYMBOL: "${FUTURES_STRATEGY_SYMBOL:-}"
      FUTURES_TICK_STREAM: "${FUTURES_TICK_STREAM:-raw_data}"

  futures-risk-filter:
    <<: *pipeline-service
    container_name: ${COMPOSE_PROJECT_NAME:-kis}-futures-risk-filter
    profiles: ["futures-pipeline"]
    command: ["python", "-m", "services.risk_filter.main"]
    environment:
      <<: [*redis-runtime-env, *runtime-storage-env]
      FUTURES_RISK_FILTER: "${FUTURES_PIPELINE_MODE:-shadow}"

  futures-order-router:
    <<: *pipeline-service
    container_name: ${COMPOSE_PROJECT_NAME:-kis}-futures-order-router
    profiles: ["futures-pipeline"]
    command: ["python", "-m", "services.order_router.main"]
    environment:
      <<: [*redis-runtime-env, *runtime-storage-env, *kis-runtime-env]
      FUTURES_ORDER_ROUTER: "${FUTURES_ORDER_ROUTER_MODE:-paper}"

  futures-monitor:
    <<: *pipeline-service
    container_name: ${COMPOSE_PROJECT_NAME:-kis}-futures-monitor
    profiles: ["futures-pipeline"]
    command: ["python", "-m", "services.futures_monitor.main"]
    environment:
      <<: [*redis-runtime-env, *runtime-storage-env, *alert-runtime-env]
      FUTURES_MONITOR_DAEMON: "${FUTURES_PIPELINE_MODE:-shadow}"
      FUTURES_MONITOR_STATUS_INTERVAL: "${FUTURES_MONITOR_STATUS_INTERVAL:-5}"
      FUTURES_TICK_STREAM: "${FUTURES_TICK_STREAM:-raw_data}"

  futures-kill-switch:
    <<: *pipeline-service
    container_name: ${COMPOSE_PROJECT_NAME:-kis}-futures-kill-switch
    profiles: ["futures-killswitch"]
    command: ["python", "-m", "services.kill_switch.main"]
    environment:
      <<: [*redis-runtime-env, *runtime-storage-env, *alert-runtime-env]
      KIS_FUTURES_EQUITY_KRW: "${KIS_FUTURES_EQUITY_KRW:-100000000}"
```

- [ ] **Step 2: Validate compose parses.**

```bash
cd /tmp/wt-f9-futures-cutover
docker compose -f docker-compose.yml config -q && echo "COMPOSE OK" || echo "CHECK (docker maybe absent)"
python -c "import yaml; yaml.safe_load(open('docker-compose.yml')); print('YAML OK')"
```
Expected: `YAML OK` (and `COMPOSE OK` if docker present).

- [ ] **Step 3: Commit.**

```bash
git add docker-compose.yml
git commit -m "feat(compose): dormant futures pipeline profiles (futures-ingest/pipeline/killswitch)"
```

---

### Task 3: Mode knobs in env templates

**Files:** Modify `.env.paper.example`, `.env.live.example`.

- [ ] **Step 1: Append futures pipeline knobs after the `STOCK_MAX_SYMBOLS` line** in
  **both** `.env.paper.example` and `.env.live.example`:

```
# Futures decoupled pipeline (dormant; profiles futures-ingest/futures-pipeline/futures-killswitch).
# Shadow-default. Cutover: set FUTURES_PIPELINE_MODE=live and FUTURES_ORDER_ROUTER_MODE=live
# (see docs/runbooks/futures-pipeline-cutover-f9.md). FUTURES_STRATEGY_SYMBOL = KOSPI200 mini
# front-month code (required for shadow/live; updates quarterly at rollover).
FUTURES_PIPELINE_MODE=shadow
FUTURES_ORDER_ROUTER_MODE=paper
FUTURES_STRATEGY_SYMBOL=
```

(Same three keys/values in both files — `FUTURES_STRATEGY_SYMBOL` is intentionally empty.)

- [ ] **Step 2: Commit.**

```bash
git add .env.paper.example .env.live.example
git commit -m "docs(env): futures pipeline mode knobs in paper/live templates"
```

---

### Task 4: Compose-shape test

**Files:** Modify `tests/unit/test_compose_runtime_env.py`.

- [ ] **Step 1: Add the futures pipeline test** (append after
  `test_stock_pipeline_compose_services_are_profile_gated`):

```python
def test_futures_pipeline_compose_services_are_profile_gated():
    compose = yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    services = compose["services"]

    ingest = services["futures-market-ingest"]
    assert ingest["profiles"] == ["futures-ingest"]
    assert ingest["command"] == ["python", "-m", "services.market_ingest.main"]
    assert ingest["environment"]["INGEST_ASSET"] == "futures"
    assert "KIS_FUTURES_APP_KEY" in ingest["environment"]
    assert "KIS_FUTURES_APP_SECRET" in ingest["environment"]

    # shadow|live daemons share FUTURES_PIPELINE_MODE; order_router uses paper|live.
    expected_pipeline = {
        "futures-decision-engine": (
            ["python", "-m", "services.decision_engine.main"],
            "FUTURES_STRATEGY_DAEMON",
            "${FUTURES_PIPELINE_MODE:-shadow}",
        ),
        "futures-risk-filter": (
            ["python", "-m", "services.risk_filter.main"],
            "FUTURES_RISK_FILTER",
            "${FUTURES_PIPELINE_MODE:-shadow}",
        ),
        "futures-order-router": (
            ["python", "-m", "services.order_router.main"],
            "FUTURES_ORDER_ROUTER",
            "${FUTURES_ORDER_ROUTER_MODE:-paper}",
        ),
        "futures-monitor": (
            ["python", "-m", "services.futures_monitor.main"],
            "FUTURES_MONITOR_DAEMON",
            "${FUTURES_PIPELINE_MODE:-shadow}",
        ),
    }
    for service_name, (command, mode_env_key, mode_value) in expected_pipeline.items():
        service = services[service_name]
        service_env = service["environment"]
        assert service["profiles"] == ["futures-pipeline"]
        assert service["command"] == command
        assert service["depends_on"]["redis"]["condition"] == "service_healthy"
        assert service_env[mode_env_key] == mode_value

    # order_router self-feeds a real KIS WS — needs futures creds.
    order_env = services["futures-order-router"]["environment"]
    assert "KIS_FUTURES_APP_KEY" in order_env
    assert "KIS_FUTURES_APP_SECRET" in order_env

    # monitor needs futures Telegram (live alerts).
    monitor_env = services["futures-monitor"]["environment"]
    assert "TELEGRAM_FUTURES_BOT_TOKEN" in monitor_env
    assert "TELEGRAM_FUTURES_CHAT_ID" in monitor_env

    # kill_switch is live-only safety, isolated in its own profile.
    kill = services["futures-kill-switch"]
    assert kill["profiles"] == ["futures-killswitch"]
    assert kill["command"] == ["python", "-m", "services.kill_switch.main"]
    assert "TELEGRAM_FUTURES_BOT_TOKEN" in kill["environment"]
    assert (
        kill["environment"]["KIS_FUTURES_EQUITY_KRW"]
        == "${KIS_FUTURES_EQUITY_KRW:-100000000}"
    )
```

- [ ] **Step 2: Extend the env-template test.** In
  `test_paper_and_live_env_templates_separate_kis_markets`, after the existing
  `paper[...]` assertions add:

```python
    assert paper["FUTURES_PIPELINE_MODE"] == "shadow"
    assert paper["FUTURES_ORDER_ROUTER_MODE"] == "paper"
    assert paper["FUTURES_STRATEGY_SYMBOL"] == ""
```

  and after the `live[...]` assertions add:

```python
    assert live["FUTURES_PIPELINE_MODE"] == "shadow"
    assert live["FUTURES_ORDER_ROUTER_MODE"] == "paper"
    assert live["FUTURES_STRATEGY_SYMBOL"] == ""
```

- [ ] **Step 3: Run the test.**

```bash
cd /tmp/wt-f9-futures-cutover
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/test_compose_runtime_env.py -v -p no:cacheprovider
```
Expected: PASS (all, including the two updated/added tests).

- [ ] **Step 4: Commit.**

```bash
git add tests/unit/test_compose_runtime_env.py
git commit -m "test(compose): assert futures pipeline profiles + env-template knobs"
```

---

### Task 5: Cutover runbook

**Files:** Create `docs/runbooks/futures-pipeline-cutover-f9.md`.

- [ ] **Step 1: Write the runbook** mirroring `docs/runbooks/stock-pipeline-cutover-m5d.md`,
  with these sections (futures-specific content):

  - **Title + intro:** Flip futures **paper** from the in-process `trader-futures`
    orchestrator to the decoupled chain (decision_engine → risk_filter → order_router →
    futures_monitor [+ kill_switch]). Operational risks: silent stop, double trading,
    stale market data, **dual KIS futures WS**.
  - **Spec link + Compose plan link.**
  - **Compose Profiles:** `trading` (trader-futures), `futures-pipeline` (decision/risk/
    order/monitor), `futures-ingest` (futures-market-ingest = KIS futures WS owner /
    raw_data producer), `futures-killswitch` (kill_switch, live-only). Note futures-ingest
    is separate on purpose — do not run it while `trader-futures` owns the futures WS.
  - **Gate 0 Prerequisites:** `.env.paper`/`.env.live` filled; redis/dashboard/caddy up;
    `trader-futures` running; `FUTURES_PIPELINE_MODE=shadow` + `FUTURES_ORDER_ROUTER_MODE=paper`
    (or unset → compose defaults); set `FUTURES_STRATEGY_SYMBOL` to the current KOSPI200 mini
    front-month; verify `config/kill_switch.yaml::enabled`.
  - **Gate 1 Shadow Validation (≥3–5 trading days):** start futures-pipeline ONLY (reuse
    `trader-futures`' `raw_data`, NO ingest):
    ```bash
    docker compose --env-file .env.paper --profile futures-pipeline up -d \
      futures-decision-engine futures-risk-filter futures-order-router futures-monitor
    ```
    Per-day checks: `.shadow` dashboard keys (`trading:futures:*:shadow`) show decoupled
    signals/fills/positions; `risk:state:futures:shadow` populates; no unbounded stream
    backlog (`signal.candidate.futures.shadow`, `signal.final.futures.shadow`,
    `order.fill.futures.shadow`); no restart loop (`docker compose ps`); compare shadow
    decisions vs orchestrator paper trades for direction (not fill parity).
    **DUAL-WS CAVEAT:** order_router self-feeds a real KIS futures WS even in paper mode →
    2 concurrent futures WS on one account (orchestrator + order_router). Verify KIS allows
    this, or run shadow in a window where `trader-futures` is paused.
  - **Gate 2 Operator Approval + Phase-5:** record date + one-line shadow summary.
    **HARD PREREQUISITE: Phase-5 Gate 1–3 + written approval** — cross-link
    `docs/runbooks/phase5-verification.md`. Do not proceed without it.
  - **Cutover Sequence (off-hours):**
    1. Flatten/clear paper state (optional flatten; stop `trader-futures`; redis del
       `futures:monitor:positions trading:futures:positions risk:state:futures`).
    2. Block the orchestrator futures path (double-trade guard): set
       `FUTURES_ORCHESTRATOR_ENABLED=false` in the env file (F-8 guard → `sts trade start
       --asset futures` refuses).
    3. **(live only)** enable real orders: `config/futures_live.yaml::enabled: true` +
       `redis-cli -n 1 del futures:live:suspended` (LiveModeGuard). For a paper cutover keep
       `FUTURES_ORDER_ROUTER_MODE=paper`.
    4. Start the decoupled chain + ingest (+ killswitch for live):
       ```bash
       FUTURES_PIPELINE_MODE=live FUTURES_ORDER_ROUTER_MODE=live \
         docker compose --env-file .env.live \
           --profile futures-ingest --profile futures-pipeline --profile futures-killswitch up -d \
           futures-market-ingest futures-decision-engine futures-risk-filter \
           futures-order-router futures-monitor futures-kill-switch
       ```
       (Paper cutover: `--env-file .env.paper`, `FUTURES_ORDER_ROUTER_MODE=paper`, omit
       futures-killswitch.)
    5. Post-cutover verify: `docker compose ps` for all futures services up; unsuffixed
       dashboard keys (`trading:futures:*`) populate; `raw_data` fresh.
    6. First 09:00 KST session observation: `raw_data` fresh; live dashboard keys show
       positions/fills/signals; no restart loop or backlog growth.
  - **Rollback Triggers:** live verify fails, market data stale during hours, fills stop
    while final signals present, unbounded backlog, restart loop, or any WS-conflict /
    double-trade symptom.
  - **Rollback:**
    ```bash
    docker compose --env-file .env.paper stop \
      futures-market-ingest futures-decision-engine futures-risk-filter \
      futures-order-router futures-monitor futures-kill-switch
    # re-enable the orchestrator futures path:
    #   FUTURES_ORCHESTRATOR_ENABLED=true   (in env file)
    docker compose --env-file .env.paper --profile trading up -d trader-futures
    ```
    For a live rollback also set `config/futures_live.yaml::enabled: false` (or
    `redis-cli -n 1 set futures:live:suspended 1`).
  - **Notes:** `futures:monitor:positions` = monitor working store;
    `risk:state:futures[:shadow]` = PseudoOCO risk PnL writer; `trading:futures:*[:shadow]`
    = dashboard-native (TradingStatePublisher). The F-8 `FUTURES_ORCHESTRATOR_ENABLED` guard
    prevents orchestrator↔decoupled double-trading. Dual-WS caveat (above). kill_switch is
    config-gated (`kill_switch.yaml::enabled`) and live-only. Automated futures cutover
    verify/rollback scripts (stock has `scripts/ops/stock_cutover_{verify,rollback}`) are a
    documented follow-up; this runbook uses inline commands.

- [ ] **Step 2: Cross-link from the decoupling state.** (Memory-only; no repo file edit needed.)

- [ ] **Step 3: Commit.**

```bash
git add docs/runbooks/futures-pipeline-cutover-f9.md
git commit -m "docs(runbook): futures decoupled pipeline cutover (F-9)"
```

---

## Self-Review (applied)

- **Spec coverage:** anchor rename (T1), dormant profiles for all 6 services (T2), env knobs (T3), compose-shape + env-template tests (T4), cutover runbook (T5). ✓
- **Type/name consistency:** profiles `futures-ingest`/`futures-pipeline`/`futures-killswitch`; knobs `FUTURES_PIPELINE_MODE`/`FUTURES_ORDER_ROUTER_MODE`/`FUTURES_STRATEGY_SYMBOL` used identically in compose, env templates, test, runbook. order_router=paper|live everywhere; decision/risk/monitor=shadow|live everywhere. ✓
- **No placeholders:** full YAML, env lines, test code, and runbook section content provided. ✓
- **Safety:** all services profile-gated/dormant; safe defaults (shadow/paper); kill_switch isolated; cutover needs operator gates. ✓
