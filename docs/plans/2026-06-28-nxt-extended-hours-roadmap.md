# NXT (넥스트레이드 / Korea ATS) Extended-Hours Support — Phased Strategic Roadmap

> **For agentic workers**: This is a paper-only R&D roadmap. Default every new capability to `enabled: false` / dormant. Keep the engineering rigor (branch → PR → independent review → CI), but there is **no live order risk** in any phase here — both stock and futures accounts are 0 and execution is VirtualBroker + local-DB minute-bar paper recording. "Compliance/legal sign-off" and "ATS order routing" are FUTURE-LIVE concerns and are **out of scope** (see §6), not blockers.

- **Date**: 2026-06-28 (revised 2026-06-29)
- **Author**: Prometheus (strategic planning)
- **Status**: ROADMAP — paper R&D; phases gated only by code review + paper-observation results
- **Scope**: kis_paper stack, **stock-side**. VirtualBroker + local-DB paper recording. No live order path is in scope.
- **Operator goal (verbatim)**: "월요일부터 NXT 프리마켓 대응, KRX 정규장, NXT 애프터마켓 대응이 잘 되어야 한다." + "Phase 1을 연장거래 하는것보다는 데이터를 바라봐, 주식 유니버스의 움직임을 봐야해."
- **NXT session hours (target)**: pre-market 08:00–08:50 · main 09:00–15:30 (concurrent with KRX) · after-market 15:30–20:00 KST

---

## 1. Executive Summary

### The reality (low-risk paper R&D, not a compliance program)
Everything here is **paper**. Execution is VirtualBroker + local-DB minute-bar recording; both stock and futures accounts are 0; the system **cannot place live orders today**. So there is **no order risk** in observing NXT data or in paper-trading NXT extended hours. This is a **low-risk paper R&D program**, sequenced by data first, then paper trading.

The two real engineering facts that shape the work:
- Today the stock path is **KRX-regular-hours only (09:00–15:30)**, with a 15:30 `effective_close_time()` cap and a 15:30 **EOD force-flatten** in `three_stage.py`. To paper-trade extended hours we must generalize the session model and lift that cap **for paper** — a real but contained code change.
- A substantial **dormant NXT scaffold already exists** (KIS unified-quote support, `ats_simulator.py`, and — for the future-live concern only — `venue_router.py` + `submit_ats_order()`).

This is **stock-side**: futures is now **day-only with an 08:45 open** (MERGED #552/#553, deployed+verified) and the futures night session stays disabled. Extended-hours/NXT work lives on the **decoupled stock daemon + screener/fusion + LLM universe** surfaces.

### The priority: look at the data first
The operator chose **data over best-execution**. The lead deliverable is **Phase 0 — observe NXT pre/regular/after minute data and stock-universe movement**. Then **Phase 1 — NXT trading (paper)**: generate paper signals and record trades to the same local-DB / VirtualBroker path across the extended-hours windows.

### KIS keystone (verified)
Unified quotes are a documented single-parameter mechanism: `FID_COND_MRKT_DIV_CODE ∈ {J:KRX, NX:NXT, UN:통합}` on `inquire_price` (TR `FHKST01010100`). NXT and unified data are reachable today via the existing client surface.

### The phases
| Phase | Title | Risk | Headline acceptance |
|---|---|---|---|
| **0** | Data & Universe Observation (lead) | None (read-only paper) | Clean pre/after NXT+unified minute data + stock-universe movement surfaced; parity/coverage pass |
| **1** | NXT Trading (paper) | Paper only (VirtualBroker/local-DB) | Paper trades recorded across pre/regular/after windows via the SAME paper path; ≥4–6wk obs per strategy |
| **Out of scope** | Best-execution / ATS order routing (`venue_router`) | Future LIVE only | Deferred — see §6 |

**Default for everything new: `enabled: false` / dormant** (project convention: Setup D, bear-override, LLM-discovery all shipped dormant). Every phase rolls back to dormant via config alone.

---

## 2. Constraints (carry into every phase)

1. **Paper-only, no live order path.** VirtualBroker + local-DB minute-bar recording. Nothing here enables live trading.
2. **Stock-side.** Futures is day-only @ 08:45 open (#552/#553); futures night session stays `enabled:false`. Surfaces: decoupled stock daemon, screener/fusion, LLM universe.
3. **Config-driven, KST-native** (never UTC); Redis DB1 with TTLs; no secrets in code; hermetic tests (no live `.env`).
4. **Code-quality gates stay**: branch → PR → independent code review → CI green → merge. Never commit to `main`. Parallel branch agents use worktree isolation.
5. **Deploy = Docker compose** with `--env-file .env.paper`, `--no-deps`, never `down`. Crontab changes require a **scheduler image rebuild** (crontab is baked into the image).
6. **Phase gates are paper-observation + review**, not legal sign-off. The only thing that needs legal/compliance is a *future live* path — explicitly out of scope (§6).

---

## 3. Phase 0 — Data & Universe Observation (lead, read-only paper)

**Goal**: Ingest, validate, and surface NXT + unified minute data across pre-market / regular / after-market windows, **and observe stock-universe movement** across those windows. Read-only — zero order risk. This is the operator's stated priority ("데이터를 바라봐, 주식 유니버스의 움직임을 봐야해") and de-risks Phase 1.

### 3.0 Scope
- KIS-API confirmation of market-div/TR IDs + WS feeds for NXT and unified quotes across all windows.
- NXT/unified **minute-bar** ingestion (REST + WS) into the local DB / Redis DB1, covering pre + after windows.
- **Stock-universe movement observation**: how the screener/fusion/LLM universe behaves in pre/after windows (which symbols move, liquidity, spread, gap behavior).
- Data-quality / coverage validation (parity vs KRX during the 09:00–15:30 overlap; coverage for pre/after).
- Dashboard surfacing of extended-hours data + universe movement (observation only).
- Backtest/replay characterization via `ats_simulator.py`.

### 3.1 Subsystems / files touched (cite the audit)
- **KIS client / quotes**: `shared/kis/client.py` — add unified/NXT minute & quote reads via `FID_COND_MRKT_DIV_CODE = UN/NX` (default `J`, no behavior change). (ATS order code at `:1053` is **not touched** — future-live, §6.)
- **Calendar / windows**: `shared/calendar.py:156` — PREMARKET 08:00–08:55 defined but only read by `is_premarket_hours()`; Phase 0 starts *reading* window config for data. Real NXT after-market extends to **20:00**, beyond anything currently modeled.
- **Market schedule config**: `config/market_schedule.yaml::stock.extended` is **DEAD** (08:30–08:40 / 15:40–16:00, narrower than real NXT, zero readers) — **replace, don't reuse**. Add an `nxt` data-window block (pre 08:00–08:50, after 15:30–20:00) + loader.
- **Data feeds / ingest**: KIS WS/REST ingestion + market-data loaders (KRX-assuming today) — add unified/NXT venue handling on the **read path only**, with REST fallback parity for off-hours (WS resets historically severe — see WS-stability memory).
- **Universe surfaces**: screener / fusion_ranker / LLM universe — observe (don't gate trading on) their behavior in the new windows.
- **Dashboard**: `services/dashboard` — extended-hours quotes/coverage + universe-movement panels.
- **Backtest**: `shared/backtest/ats_simulator.py` — replay captured NXT data to characterize fills/spreads.

### 3.2 Bite-sized tasks (TDD, frequent commits — one PR per logical group)
1. **KIS-API confirmation** (docs/spike): confirm via `kis-code-assistant-mcp` the TR IDs / market-div codes for (a) unified+NXT current price (confirmed: `inquire_price` `FHKST01010100`, `FID_COND_MRKT_DIV_CODE ∈ {J,NX,UN}`), (b) NXT/unified orderbook (호가), (c) NXT/unified minute & time-conclusion charts, (d) WS real-time venue codes for NXT. **Commit**: docs only.
2. **Config: NXT data-window block** — add `market_schedule.yaml::nxt` (pre 08:00–08:50, after 15:30–20:00, `enabled` flags) + loader; remove the dead `stock.extended`. Hermetic loader tests. **Commit**.
3. **Unified/NXT minute & quote read path** — extend KIS client quote/minute methods to accept a venue/market-div param (`UN`/`NX`/`J`, default `J`). Unit tests with mocked KIS responses. **Commit**.
4. **Off-hours NXT/unified ingest** — wire pre/after windows into a read-only ingest writing to Redis DB1 (new TTL'd keys/streams) and/or the local minute-bar DB. No strategy consumes it yet. Include REST fallback for off-hours WS gaps. **Commit**.
5. **Universe-movement observation** — capture screener/fusion/LLM-universe symbol movement across windows into an observation log/store. **Commit**.
6. **Data-quality / coverage validators** — overlap parity (NXT vs KRX vs unified), pre/after coverage (no phantom/echo bars — reuse futures dedup lessons), coverage alerts (Telegram STOCK channel). **Commit**.
7. **Dashboard observation panels** — extended-hours data + universe movement (read-only). **Commit**.
8. **Backtest/replay** — drive `ats_simulator.py` with captured NXT data to characterize fills/spreads (input to Phase 1 risk params). **Commit**.

### 3.3 Risks
- KIS unified vs NXT-only semantics differ from assumptions → mitigated by Task 1 before coding.
- NXT after-market to 20:00 is beyond any modeled window → new modeling required.
- Off-hours WS feed fragility (historical resets) → REST fallback parity for new windows is mandatory.

### 3.4 Validation method
Overlap parity report; pre/after coverage report over ≥1–2 weeks of paper observation; universe-movement log reviewed; dashboard visual confirmation. **No trading.**

### 3.5 Acceptance criteria
- Clean, validated NXT + unified **minute** data for pre/regular/after windows persisted (local DB + Redis DB1).
- Overlap parity within tolerance; discrepancies documented.
- Pre/after coverage alerts functioning; gaps explainable.
- Stock-universe movement observable across windows (dashboard + log).
- `ats_simulator.py` replay characterization produced.
- **Zero changes to any order or session-gating path.**

### 3.6 Rollback
Config flags (`market_schedule.yaml::nxt.*.enabled`, dashboard panel flags) → off; disable ingest jobs (scheduler rebuild if cron-driven). Read-only — no order-path impact.

---

## 4. Phase 1 — NXT Trading (paper)

**Goal (headline "NXT 거래" deliverable)**: After data, let opted-in strategies **generate paper signals and record trades to the same local-DB / VirtualBroker path** on NXT extended-hours minute bars — across pre (08:00–08:50), regular (09:00–15:30), and after (15:30–20:00) windows. Paper-only; no live path.

### 4.1 Scope
- **Phase-aware session model (for paper)**: replace the hard 09:00–15:30 gate with `PRE` / `REGULAR` / `AFTER` phases, config-driven (KST).
- **Lift the 15:30 caps for paper**: generalize `effective_close_time()`'s 15:30 cap and `three_stage.py`'s 15:30 EOD force-flatten so extended-hours paper holds are possible — while preserving exact 15:30 behavior for `REGULAR`-only strategies (no silent change).
- **Per-strategy `session_phases` opt-in**, default `[REGULAR]` and dormant (`enabled:false`) → no behavior change for existing strategies.
- **Extended-hours risk as paper-observation parameters**: thinner liquidity / wider spreads / different vol expressed as tighter spread/depth gates + smaller size caps (paper-observation knobs, not live guards).
- **EOD / overnight policy for after-market paper holds** (survive past 15:30? past 20:00? flatten at after-close?).
- **Scheduler jobs** for pre/after producer + exit cadence.
- Trades flow through the **same VirtualBroker + local-DB minute-bar recording** as regular paper trading.

### 4.2 Subsystems / files touched (the heavy lift)
- `shared/strategy/market_time.py` — generalize `is_regular_session_open()` (`:52`) into a phase resolver (`current_session_phase()`); make `effective_close_time()`'s 15:30 cap (`:44`) phase-aware so after-market paper holds are possible while REGULAR-only stays 15:30.
- `shared/strategy/exit/three_stage.py:404-409` — make the EOD force-flatten **phase-aware**: REGULAR-only positions flatten at 15:30; after-market-enabled strategies follow the new policy. **Most safety-critical change** (stranded vs premature flatten) — even in paper this corrupts the recorded P&L if wrong.
- Stock entry strategies / producers (screener, fusion, signal) gated by `is_regular_session_open()` — add `session_phases` opt-in so only opted-in strategies wake in pre/after.
- `config/market_schedule.yaml::nxt` — promote the Phase-0 data-window block to a **session** block with per-phase `enabled` + risk overrides.
- `config/execution.yaml` — extended-hours risk overrides (spread/depth/size), modeled on the existing `paper_override` and `slippage_model.time_of_day_multipliers` patterns.
- `deploy/scheduler.crontab` — add pre (≥08:00) and after (15:30–20:00) producer/exit jobs; **scheduler image rebuild required**. (Today's 06:30/08:30/08:50/08:58 jobs are data-prep and 15:32/15:40/16:05+ are batch/observation — **none trade**.)
- VirtualBroker / local-DB minute-bar recording path — extended-hours paper fills recorded identically to regular paper fills (no new execution venue; this is the existing paper path over a wider clock).

### 4.3 Risks
- **Stranded / premature-flatten bug** in the phase-aware EOD rework (highest severity, even in paper — it corrupts recorded results). Mitigated by exhaustive TDD with **KST clock pins** (note the known "green AM / red PM" EOD test fragility).
- Thin extended-hours liquidity → unrealistic paper fills if the slippage/spread model isn't tuned for the windows → mitigated by Phase-0 `ats_simulator` characterization feeding the paper risk params.
- Off-hours WS fragility → inherits Phase-0 REST fallback.
- Scheduler/cron correctness across new windows (KST, not UTC).

### 4.4 Validation method
Per opted-in strategy: paper trading in each window for **≥4–6 weeks** (Setup-D-style observation), EOD/overnight policy exercised, with a digest (analogous to the Setup A/C paper-observation digest). Backtest/replay via `ats_simulator.py` precedes any window go-live.

### 4.5 Acceptance criteria
- **Paper trades recorded across pre / regular / after windows through the SAME local-DB / VirtualBroker path.**
- Phase-aware session model: REGULAR-only strategies bit-for-bit unchanged (15:30 EOD preserved); only `session_phases`-opted strategies act in pre/after.
- EOD/overnight policy behaves exactly per config (no stranded, no premature flatten) — proven by clock-pinned tests.
- ≥4–6 weeks paper observation per extended-hours strategy with a published digest.
- All new capability ships `enabled:false`/dormant; opt-in is explicit.

### 4.6 Rollback
Per-phase `enabled:false` in `market_schedule.yaml::nxt`; strategy `session_phases` back to `[REGULAR]` → reverts to today's 09:00–15:30 behavior. Scheduler jobs disabled (rebuild). No code rollback required.

---

## 5. Cross-Cutting Concerns

### 5.1 Risk Controls (paper-observation parameters)
Extended-hours risk profile = tighter spread/depth gates + reduced size caps + possibly limit-only, expressed as paper-observation knobs. Reuse `slippage_model.time_of_day_multipliers`, `paper_broker` staleness/deviation guards, the reentry guard and stale-position timeout (`execution.yaml`) — extend windows/params for thin liquidity.

### 5.2 Observability
- Dashboard: extended-hours data + universe movement (Phase 0); extended-hours paper positions/fills (Phase 1).
- Telegram STOCK channel: coverage alerts (Phase 0), paper-observation digests (Phase 1).
- Redis DB1 keys/streams (TTL'd) for new venues/windows.

### 5.3 Rollback (uniform principle)
**Every phase flips back to dormant via config alone** — no code rollback. Standing project convention (Setup D, bear-override, LLM-discovery).

### 5.4 Test Strategy
- Hermetic, no live `.env`; fakeredis; serial-mark any redis-double publisher tests that flake under xdist.
- **Clock-pinned** EOD/session-phase tests (KST) — the EOD path is time-fragile ("green AM / red PM"); pin `now_kst`.
- Loader tests for all new config blocks; mocked KIS responses for unified/NXT reads.
- `ats_simulator.py` replay parity before any window activation.

---

## 6. Out of Current Scope — Future LIVE Concern (deferred)

The operator chose **data over best-execution**, and there is no live path today. The following are **deferred** and explicitly **not near-term phases**:

- **Best-execution / venue order routing** — `shared/execution/venue_router.py` (complete KRX↔ATS smart router: price-improvement/liquidity/spread/fill-rate/time-of-day) and `config/execution.yaml:104` `ats_routing` (`enabled:false`).
- **Live ATS order submission** — `shared/kis/client.py:1053` `submit_ats_order()` (ATS TR IDs real `TTTC0852U/0851U`, demo `VTTC0852U/0851U`; path `/uapi/domestic-stock/v1/trading/order-ats`).
- **Compliance / legal sign-off** — `services/stock_order_router/main.py:209` ("must not be enabled until the market-structure policy runbook gates are satisfied") and the futures night-session legal-gate pattern (`is_futures_night_session_enabled()`). These bind a **future live** ATS-routed path, not paper data or paper trading.

When/if a live path is ever pursued, this becomes its own program with its own legal gate, fail-closed flags, and operator sign-off — **separate from this roadmap**.

---

## 7. Operator Decisions / Open Questions (paper reality)

> These are the operator's calls. None require legal sign-off (that's future-live, §6). Phase 0 can start immediately with defaults.

1. **NXT data-window definitions** — confirm exact pre (08:00–08:50) and after (15:30–20:00) windows, and whether to capture **unified (`UN`)**, **NXT-only (`NX`)**, or both. *(Shapes Phase 0 config; sensible default = both, pre 08:00–08:50 / after 15:30–20:00.)*
2. **Sequencing of windows** — all three windows at once, or **pre-market first** (closest to the "Monday" framing) then after-market? *(Phase 0 task ordering.)*
3. **Which strategies trade extended hours in paper** — default `[REGULAR]` for all (no change). Extended-hours liquidity is thin; likely only a subset opts in. *(Blocks Phase 1 strategy work, not Phase 0.)*
4. **After-market EOD / overnight policy for paper holds** — survive past 15:30 into after-market? past 20:00 overnight? or flatten at after-close? *(Drives the most safety-critical Phase-1 code change.)*

**Immediately startable with no blockers:** Phase 0, Tasks 1–2 (KIS-API confirmation + NXT data-window config) — read-only, defaults are reasonable.

---

## 8. Sequencing & Handoff

```
Phase 0 (data + universe observation, read-only)  ──►  Phase 1 (NXT trading, paper)
        │                                                     │
   start now (lead priority)              after Q3/Q4 + ≥4–6wk paper obs per strategy

   [Out of scope: best-exec / ATS routing / live — §6, deferred]
```

- **Start immediately (no blockers):** Phase 0, Task 1 (KIS-API confirmation) + Task 2 (NXT data-window config).
- Branch → PR → independent review → CI → merge per task group. `--env-file .env.paper`, `--no-deps`, never `down`. Scheduler changes ⇒ rebuild.
- Recommended next action: confirm Operator Decisions 1–4 (defaults are fine for Phase 0), then `/start-work` on Phase 0.

---

## Appendix A — Verified Audit Citations
- `shared/strategy/market_time.py:52` `is_regular_session_open()` = trading-day + 09:00–close only.
- `shared/strategy/market_time.py:44` `effective_close_time()` = `min(config, 15:30)` — hard 15:30 cap.
- `shared/strategy/market_time.py:65` `is_futures_night_session_enabled()` — fail-closed gate pattern (future-live reference only).
- `shared/strategy/exit/three_stage.py:404-409` — EOD force-flatten at `effective_close_time` (→ all stock flat by 15:30).
- `shared/kis/client.py:1053` `submit_ats_order()` — ATS TR IDs (real `TTTC0852U/0851U`, demo `VTTC0852U/0851U`), path `/uapi/domestic-stock/v1/trading/order-ats`. **(Future-live, §6 — not used in this roadmap.)**
- `shared/execution/venue_router.py` — complete KRX↔ATS router. **(Future-live, §6.)**
- `config/execution.yaml:104` `ats_routing` block, `enabled:false`. **(Future-live, §6.)**
- `services/stock_order_router/main.py:209` — compliance-gate comment. **(Future-live, §6.)**
- `shared/backtest/ats_simulator.py` — Korean ATS execution simulator (used in Phase 0/1 paper characterization).
- `config/market_schedule.yaml::stock.extended` — DEAD (08:30–08:40 / 15:40–16:00, zero readers, narrower than real NXT) → replace, don't reuse.
- `shared/calendar.py:156-157` PREMARKET 08:00–08:55 — defined, only read by `is_premarket_hours()`, no trading path.
- `deploy/scheduler.crontab` — pre-open jobs (06:30/08:30/08:50/08:58) = data-prep; after-close (15:32/15:40/16:05+) = batch/observation; **none trade**. Baked into image → rebuild to change.
- **Futures context**: day-only @ 08:45 open (MERGED #552/#553, deployed+verified); night session `enabled:false`. NXT/extended-hours is a **stock-side** program.
- **KIS API (verified via kis-code-assistant-mcp)**: `inquire_price` TR `FHKST01010100`, `FID_COND_MRKT_DIV_CODE ∈ {J:KRX, NX:NXT, UN:통합}` — documented unified-quote mechanism (Phase-0 keystone).
