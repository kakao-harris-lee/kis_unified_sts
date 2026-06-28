# NXT (넥스트레이드 / Korea ATS) Extended-Hours Support — Phased Strategic Roadmap

- **Date**: 2026-06-28
- **Author**: Prometheus (strategic planning)
- **Status**: ROADMAP — not approved for implementation; Phase gates require operator sign-off
- **Scope**: kis_paper stack (paper-first). No live order path enabled by any phase of this roadmap.
- **Operator goal (verbatim)**: "월요일부터 NXT 프리마켓 대응, KRX 정규장, NXT 애프터마켓 대응이 잘 되어야 한다."
- **NXT session hours (target)**: pre-market 08:00–08:50 · main 09:00–15:30 (concurrent with KRX) · after-market 15:30–20:00 KST

---

## 1. Executive Summary

### The honest reality
This is **not a Monday toggle.** Today the platform is **KRX-regular-hours only (09:00–15:30)**, with a *hard* 15:30 cap that no config can lift, and **every stock position is force-flattened by 15:30**. NXT/ATS order code exists but is **dormant behind a compliance gate that is not yet satisfied**. Turning NXT on safely is a **multi-phase, compliance-gated** program. What *is* achievable quickly and safely is **Phase 0 (data + observation, zero order risk)** — and that is the correct first move because it de-risks everything downstream and is the long pole (data fidelity across new windows).

### What already exists (the leverage — all dormant)
The previous engineering left a substantial dormant scaffold:
- `shared/kis/client.py:1053` — `submit_ats_order()` fully written (ATS TR IDs: real `TTTC0852U/TTTC0851U`, demo `VTTC0852U/VTTC0851U`; path `/uapi/domestic-stock/v1/trading/order-ats`).
- `shared/execution/venue_router.py` — complete KRX↔ATS smart venue router (price-improvement, liquidity, spread, fill-rate, time-of-day rules).
- `config/execution.yaml:104` — `ats_routing` block, `enabled: false`.
- `shared/backtest/ats_simulator.py` — Korean ATS execution simulator for paper/backtest.
- **KIS API confirmed**: unified quotes are a *documented single-parameter* mechanism — `FID_COND_MRKT_DIV_CODE` accepts `J:KRX / NX:NXT / UN:통합` on `inquire_price` (TR `FHKST01010100`). This is the Phase-0 keystone.

### What blocks "trading":
1. **Compliance/legal gate** (hard precondition, mirrors the futures night-session legal gate) — `services/stock_order_router/main.py:209` states ATS routing "must not be enabled until the market-structure policy runbook gates are satisfied." **Fail-closed by default.**
2. **Session model is hard-coded to 09:00–15:30** — `is_regular_session_open()` and the 15:30 `effective_close_time()` cap must be generalized to a phase-aware (pre/regular/after) model before any extended-hours strategy can run.
3. **EOD force-flatten at 15:30** — `three_stage.py` liquidates all stock positions; after-market holding is structurally impossible today.

### The phases
| Phase | Title | Order risk | Compliance gate | Headline acceptance |
|---|---|---|---|---|
| **0** | Data & Observation | None | Not required (read-only) | Clean pre/after-window NXT+unified data; dashboard surfacing; parity checks pass |
| **1** | Regular-hours KRX+NXT best-execution | Paper only | **Required** before any ATS-routed order | Routing decisions logged; paper fills ≥ KRX-only; zero regression to regular trading |
| **2** | Extended-hours trading (pre 08:00–08:50 + after 15:30–20:00) | Paper only | **Required** + per-window risk gates | Paper trading in each window under explicit thin-liquidity risk gates; ≥4–6wk observation per strategy |

**Default for everything new: `enabled: false` / dormant** (project convention: Setup D, bear-override, LLM-discovery all shipped dormant). Every phase has a config-only rollback to dormant.

---

## 2. Hard Constraints (carry into every phase)

1. **Paper-first.** This is `kis_paper`. No live order path is enabled by this roadmap. Each capability ships `enabled: false`.
2. **Compliance gate is a hard precondition** for any NXT *order routing* (Phase 1+). Mirror the futures night-session legal gate: a config flag that is **fail-closed** (read/parse error → disabled), explicitly `false` until the operator completes the market-structure/legal review, with an order-path refusal when the relevant window is active and the flag is false.
3. **Config-driven, KST-native** (never UTC); Redis DB1 with TTLs; no secrets in code; hermetic tests (no live `.env` injection).
4. **Deploy = Docker compose** with `--env-file .env.paper`, `--no-deps`, never `down`. Crontab changes require a **scheduler image rebuild** (crontab is baked into the image).
5. **Branch → PR → independent code review → merge** for every change. Never commit to `main` directly. Parallel branch agents use worktree isolation.

---

## 3. Phase 0 — Data & Observation (no trading, no order risk)

**Goal**: Ingest, validate, and surface NXT + unified market data across pre-market / regular / after-market windows. This is read-only; it carries **zero order risk** and is the safe first step that de-risks Phases 1–2 (we learn NXT data fidelity, hours behavior, and liquidity *before* anything trades).

### 3.0 Scope
- KIS-API research: confirm market-div/TR IDs and WS feeds for NXT and unified quotes across all windows.
- Add NXT/unified data ingestion to REST and WS paths (pre + after windows included).
- Data-quality / coverage validation for the new windows (parity vs KRX during the concurrent 09:00–15:30 overlap).
- Dashboard surfacing of extended-hours data (observation only).
- Backtest/replay harness using `ats_simulator.py`.

### 3.1 Subsystems / files touched (cite the audit)
- **KIS client / quotes**: `shared/kis/client.py` (add unified/NXT quote reads via `FID_COND_MRKT_DIV_CODE = UN/NX`; ATS order code already at `:1053` — *not touched in Phase 0*).
- **Calendar / session windows**: `shared/calendar.py:156` (PREMARKET 08:00–08:55 already defined but unused — Phase 0 starts *reading* it for data windows; note real NXT after-market extends to 20:00, beyond anything currently modeled).
- **Market schedule config**: `config/market_schedule.yaml::stock.extended` is **DEAD** (08:30–08:40 / 15:40–16:00, narrower than real NXT, zero readers) — **replace, do not reuse**. Introduce a proper NXT window block (pre 08:00–08:50, after 15:30–20:00) as *data-window* config in Phase 0; it becomes *session* config in Phase 2.
- **Data feeds**: KIS WS/REST ingestion + market-data loaders (currently KRX-assuming). Add unified/NXT venue handling on the read path only.
- **Dashboard**: `services/dashboard` (surface extended-hours quotes/coverage as observation panels).
- **Backtest**: `shared/backtest/ats_simulator.py` (drive replay/what-if with captured NXT data).

### 3.2 Bite-sized tasks (TDD, frequent commits — one PR per logical group)
1. **KIS-API research spike** (no code): confirm, via `kis-code-assistant-mcp`, the exact TR IDs / market-div codes for (a) unified + NXT current price (confirmed: `inquire_price` `FHKST01010100` with `FID_COND_MRKT_DIV_CODE ∈ {J,NX,UN}`), (b) NXT/unified orderbook (호가), (c) NXT/unified minute & time-conclusion charts, (d) WS real-time feed venue codes for NXT. Capture findings in a short runbook section. **Commit**: docs only.
2. **Config: NXT data-window block** — add `market_schedule.yaml::nxt` (pre 08:00–08:50, after 15:30–20:00, `enabled` flags) and a loader; deprecate/remove dead `stock.extended`. Tests for the loader (hermetic). **Commit**.
3. **Unified/NXT quote read path** — extend the KIS client quote method(s) to accept a venue/market-div parameter (`UN`/`NX`/`J`), default `J` (no behavior change). Unit tests with mocked KIS responses. **Commit**.
4. **Ingestion of NXT/unified data into the off-hours windows** — wire the pre/after windows into a *read-only* ingest path that writes to Redis DB1 (new keys/streams, TTL'd) and/or parquet. No strategy consumes it yet. **Commit**.
5. **Data-quality / coverage validators** — parity check: during 09:00–15:30 overlap, NXT-vs-KRX-vs-unified price/volume sanity; coverage check for pre/after windows (bars present, no phantom/echo class — reuse the futures dedup lessons). Telegram/coverage alert on gaps. **Commit**.
6. **Dashboard observation panels** — surface extended-hours quotes + coverage status (read-only). **Commit**.
7. **Backtest/replay** — feed captured NXT data through `ats_simulator.py` to characterize fill behavior and spreads (input to Phase 1/2 risk sizing). **Commit**.

### 3.3 Risks
- KIS unified/NXT data semantics differ from assumptions (e.g., unified quote consolidates venues; NXT-only quote needed for routing). Mitigated by Task 1 spike before coding.
- NXT after-market to 20:00 is **beyond** any modeled window (calendar caps at 08:55 pre; nothing after 16:00) — new modeling required.
- Off-hours feed reliability (WS resets historically severe — see WS stability memory). Phase 0 must include REST fallback parity for the new windows.

### 3.4 Validation method
Parity checks during the concurrent overlap; coverage report across pre/after windows for ≥1–2 weeks of paper observation; visual confirmation on dashboard. **No trading.**

### 3.5 Acceptance criteria
- Clean, validated NXT + unified data for pre/regular/after windows persisted to Redis DB1/parquet.
- Parity report: unified/NXT vs KRX during overlap within tolerance; documented discrepancies.
- Coverage alerts functioning; gaps explainable.
- Dashboard shows extended-hours data.
- `ats_simulator.py` replay produces a characterization of NXT fills/spreads.
- **Zero changes to any order or session-gating path.**

### 3.6 Rollback
Config flags (`market_schedule.yaml::nxt.*.enabled`, dashboard panel flag) → off. Read-only; no order-path impact. Disable ingest jobs (scheduler rebuild if cron-driven).

---

## 4. Phase 1 — Regular-Hours KRX+NXT Best-Execution (09:00–15:30, paper)

**Goal**: During the existing regular session, compute a unified NBBO price reference and (paper-only) activate `venue_router` for price-improvement routing — **behind the compliance gate**. This is *independent of extended-hours trading* (see Operator Decisions) and is the lowest-risk way to exercise the routing stack on a known session.

### 4.1 Scope
- Unified NBBO reference (best bid/ask across KRX+NXT) during 09:00–15:30.
- Populate `venue_router.MarketData` with real KRX + NXT quotes (Phase 0 feed).
- Activate `ats_routing` (`config/execution.yaml:104`) in **paper** behind the compliance gate; log routing decisions; route paper fills accordingly.
- No change to session hours or EOD; strategies unchanged.

### 4.2 Subsystems / files touched
- `shared/execution/venue_router.py` (already complete) — feed it live `MarketData` (KRX + NXT bid/ask/qty) from Phase 0.
- `config/execution.yaml::ats_routing` (`:104`, flip to `enabled: true` **only** in paper config, **only** after compliance gate).
- `services/stock_order_router/main.py:209` — replace the "KRX-only for v1" policy comment with the **compliance-gated** activation; add the fail-closed gate (analogous to `is_futures_night_session_enabled()` in `shared/strategy/market_time.py:65`).
- `shared/kis/client.py:1053` — `submit_ats_order()` becomes reachable on ATS routing (paper broker / VirtualBroker in paper).
- Compliance gate helper — new fail-closed reader (e.g. `is_ats_routing_enabled()`), mirroring the night-session pattern.

### 4.3 Risks
- Routing to ATS on bad/ stale NXT data → worse fills. Mitigated by reusing existing router liquidity/spread/fill-rate guards + paper-broker price-staleness guard (`execution.yaml::paper_broker`).
- Regression to existing KRX-only regular trading. Mitigated by default `enabled: false` and A/B (KRX-only vs routed) on paper.
- Compliance gate must be **genuinely binding** — order path must refuse ATS routing if the flag is false even if `ats_routing.enabled: true` is mis-set.

### 4.4 Validation method
Paper A/B over a defined observation window: routed vs KRX-only fills, measured price improvement (bps), fill rates, and **zero regression** to regular-session entry/exit. Routing decision logs audited.

### 4.5 Acceptance criteria
- Every routing decision logged with reason (router already emits this).
- Paper fills via routing show **non-negative** price improvement vs KRX-only and no fill-rate degradation.
- No regression to existing regular-hours stock trading (entries/exits/EOD unchanged).
- Compliance gate verified fail-closed (flag false → ATS refused, even with `ats_routing.enabled:true`).
- **Compliance/legal sign-off recorded before this phase's gate flips.**

### 4.6 Rollback
`config/execution.yaml::ats_routing.enabled: false` (paper config) and/or compliance flag false → instant revert to KRX-only. No code rollback needed.

---

## 5. Phase 2 — Extended-Hours Trading (pre 08:00–08:50 + after 15:30–20:00, paper)

**Goal**: Generalize the session model and allow opted-in strategies to trade in the pre/after windows under explicit thin-liquidity risk gates — paper only, compliance-gated, per-strategy opt-in.

### 5.1 Scope
- Replace the hard 09:00–15:30 session model with a **phase-aware** model: `PRE` / `REGULAR` / `AFTER`, config-driven (KST).
- Per-strategy `session_phases` opt-in (default `[REGULAR]` → no behavior change for existing strategies).
- Extended-hours-specific risk profile (thinner liquidity, wider spreads, different vol): tighter spread/depth gates, smaller size caps, possibly limit-only.
- EOD / overnight policy for after-market holds (does a position survive past 15:30? past 20:00? overnight?).
- Scheduler jobs for pre/after windows (producers, exits, observation).

### 5.2 Subsystems / files touched (the heavy lift)
- `shared/strategy/market_time.py` — **generalize** `is_regular_session_open()` (`:52`) into a phase resolver (`current_session_phase()`), and **lift/redefine** the `effective_close_time()` 15:30 cap (`:44`) so after-market holds are *possible* under config — while preserving the existing 15:30 behavior for `REGULAR`-only strategies (no silent change to current EOD).
- `shared/strategy/exit/three_stage.py:404` — EOD force-flatten must become **phase-aware**: regular-only positions still flatten at 15:30; after-market-enabled strategies follow the new overnight/after-close policy. This is the single most safety-critical change — get it wrong and you either strand positions overnight or flatten extended-hours positions prematurely.
- Stock entry strategies / producers (screener, fusion, signal) currently gated by `is_regular_session_open()` — add `session_phases` opt-in so only opted-in strategies wake in pre/after windows.
- `config/market_schedule.yaml::nxt` — promote Phase-0 data-window block to a **session** block with per-phase `enabled` + risk overrides.
- `deploy/scheduler.crontab` — add pre (≥08:00) and after (15:30–20:00) jobs; **scheduler image rebuild required**. Today's pre-market jobs (06:30/08:30/08:50/08:58) are data-prep for the 09:00 open and after-close jobs (15:32/15:40/16:05+) are batch/observation — **none currently trade**; new windows need their own producer/exit cadence.
- `config/execution.yaml` — extended-hours risk overrides (spread/depth/size), analogous to the existing `paper_override` and `slippage_model.time_of_day_multipliers` patterns.
- ATS order path (`shared/kis/client.py:1053`) — extended-hours orders route via ATS/NXT under the compliance gate.

### 5.3 Risks
- **Stranded-position / premature-flatten bug** in the phase-aware EOD rework (highest severity). Mitigated by exhaustive TDD around `three_stage` EOD with clock pins (note the known "green AM / red PM" EOD test fragility — pin KST clock in all exit tests).
- Thin extended-hours liquidity → adverse fills, wide spreads, gaps. Mitigated by extended-hours risk profile (tighter gates, smaller size, limit-only) + Phase-0 liquidity characterization.
- Overnight risk if after-market holds are allowed past 20:00 — explicit operator policy required (see Open Questions).
- Off-hours WS feed fragility (historical) — must inherit Phase-0 REST fallback.
- Scheduler complexity / cron correctness across new windows (KST, not UTC).

### 5.4 Validation method
Per opted-in strategy: paper trading in each window for **≥4–6 weeks** (Setup-D-style observation cadence) with explicit risk gates, EOD/overnight policy exercised, and a digest (analogous to the Setup A/C paper-observation digest). Backtest/replay via `ats_simulator.py` precedes any window go-live.

### 5.5 Acceptance criteria
- Phase-aware session model: existing REGULAR-only strategies bit-for-bit unchanged (15:30 EOD preserved); only `session_phases`-opted strategies act in pre/after.
- Paper trading demonstrably occurring in each window under explicit risk gates.
- EOD/overnight policy behaves exactly per config (no stranded, no premature flatten) — proven by clock-pinned tests.
- ≥4–6 weeks paper observation per extended-hours strategy with a published digest before any further escalation.
- Compliance gate satisfied for extended-hours/ATS-routed orders; fail-closed verified.

### 5.6 Rollback
Per-phase `enabled: false` in `market_schedule.yaml::nxt`, strategy `session_phases` back to `[REGULAR]`, compliance flag false → reverts to today's 09:00–15:30 KRX-only behavior. Scheduler jobs disabled (rebuild). No code rollback required.

---

## 6. Cross-Cutting Concerns

### 6.1 Compliance / Legal Gate (the binding precondition)
- A **fail-closed** config flag (read/parse error → disabled), modeled on `is_futures_night_session_enabled()` (`shared/strategy/market_time.py:65`) and the night-session runbook precedent.
- Required **before any ATS-routed or extended-hours order** can fire (Phase 1 and Phase 2). Phase 0 is exempt (read-only).
- A new section in `docs/runbooks/market-structure-policy.md` (the existing home of the futures gates) documenting: NXT/ATS regulatory conditions, the operator sign-off checklist, and the explicit `enabled: false` default until sign-off.
- Order path must **refuse** ATS/extended-hours orders when the gate is false, regardless of other config.

### 6.2 Risk Controls
- Extended-hours risk profile: tighter spread/depth gates, reduced size caps, possibly limit-only; reuse `venue_router` guards + `slippage_model` time-of-day multipliers + `paper_broker` staleness/deviation guards.
- Reentry guard + stale-position timeout already exist (`execution.yaml`) — extend windows/params for thin liquidity.

### 6.3 Observability
- Dashboard panels for extended-hours data (Phase 0), routing decisions (Phase 1), extended-hours positions/fills (Phase 2).
- Telegram: coverage alerts (Phase 0), routing/observation digests (Phase 1/2) on the existing STOCK channel.
- Redis DB1 keys/streams (TTL'd) for new venues/windows.

### 6.4 Rollback (uniform principle)
**Every phase flips back to dormant via config alone** — no code rollback. This is the project's standing convention (Setup D, bear-override, LLM-discovery).

### 6.5 Test Strategy
- Hermetic, no live `.env`; fakeredis; serial-mark any redis-double publisher tests that flake under xdist.
- **Clock-pinned** EOD/session-phase tests (KST) — the EOD path is time-fragile ("green AM / red PM"); pin `now_kst`.
- Loader tests for all new config blocks.
- Mocked KIS responses for unified/NXT quote reads and ATS orders.
- Backtest/replay parity via `ats_simulator.py` before any window activation.

---

## 7. Operator Decisions / Open Questions (these are the operator's calls — not guessed)

> **Top 3 that block Phase 0 / Phase 1 start are marked ⛔.**

1. ⛔ **Compliance/legal approval process & owner.** Who owns the NXT/ATS market-structure & legal sign-off, and what is the process? This is the hard precondition for *any* order routing (Phase 1+). Phase 0 (data) can start without it, but Phase 1 cannot. *Without an owner and a path to sign-off, Phases 1–2 are blocked indefinitely.*
2. ⛔ **Is Phase 1 best-execution wanted independently of extended-hours trading?** Best-exec routing during 09:00–15:30 delivers value on its own and is lower-risk than extended-hours trading. If yes, Phase 1 can proceed (post-compliance) without committing to Phase 2. If the only goal is pre/after-market trading, we may sequence Phase 0 → Phase 2 and treat Phase 1 as optional. *This decision sets the whole sequencing.*
3. ⛔ **Phase 0 priority/timeline & which windows first.** Phase 0 is the safe, immediately-startable step. Confirm priority and whether to target all three windows at once or pre-market first (closest to the operator's "Monday" framing) then after-market. *This is what we'd start on now.*
4. **Which strategies (if any) should trade extended hours vs remain regular-only?** Default is `[REGULAR]` for all (no change). Extended-hours liquidity is thin and different in character — likely only a subset (or none initially) should opt in. (Blocks Phase 2 strategy work, not Phase 0/1.)
5. **Capital / risk limits for thin extended-hours liquidity.** Size caps, limit-only vs market, max spread/slippage tolerance for pre/after windows. (Blocks Phase 2 risk config.)
6. **EOD / overnight policy for after-market holds.** Do positions survive past 15:30 into after-market? Past 20:00 overnight? Or flatten at the after-market close? This drives the most safety-critical code change in Phase 2. (Blocks Phase 2 EOD rework.)
7. **Live escalation (out of scope here).** This roadmap is paper-only end-to-end. Any move to live is a separate operator-gated decision after Phase 2 paper observation, mirroring the Phase-5 Setup A/C promotion gates.

---

## 8. Sequencing & Handoff

```
Phase 0 (data, no risk)  ──►  Phase 1 (best-exec, paper, compliance-gated)  ──►  Phase 2 (extended-hours trading, paper, compliance-gated)
        │                              │                                                │
   start now (Q3)              after compliance sign-off (Q1)              after Q4/Q5/Q6 + ≥4–6wk paper per strategy
```

- **Start immediately (no blockers):** Phase 0, Task 1 (KIS-API spike) and Task 2 (NXT data-window config) — read-only, no compliance needed.
- **Branch → PR → independent review → merge** per task group. `--env-file .env.paper`, `--no-deps`, never `down`. Scheduler changes ⇒ image rebuild.
- Recommended next action: confirm Operator Decisions ⛔1–3, then `/start-work` on Phase 0.

---

## Appendix A — Verified Audit Citations
- `shared/strategy/market_time.py:52` `is_regular_session_open()` = trading-day + 09:00–close only.
- `shared/strategy/market_time.py:44` `effective_close_time()` = `min(config, 15:30)` — hard 15:30 cap.
- `shared/strategy/market_time.py:65` `is_futures_night_session_enabled()` — fail-closed gate pattern to mirror.
- `shared/strategy/exit/three_stage.py:404-409` — EOD force-flatten at `effective_close_time` (→ all stock flat by 15:30).
- `shared/kis/client.py:1053` `submit_ats_order()` — ATS TR IDs (real `TTTC0852U/0851U`, demo `VTTC0852U/0851U`), path `/uapi/domestic-stock/v1/trading/order-ats`.
- `shared/execution/venue_router.py` — complete KRX↔ATS router (price-improvement/liquidity/spread/fill-rate/time-of-day).
- `config/execution.yaml:104` `ats_routing` block, `enabled: false`, no time-of-day legal rules.
- `services/stock_order_router/main.py:209` — "KRX-only for v1 … must not be enabled until the market-structure policy runbook gates are satisfied" (compliance-gate precedent).
- `shared/backtest/ats_simulator.py` — Korean ATS execution simulator.
- `config/market_schedule.yaml::stock.extended` — DEAD (08:30–08:40 / 15:40–16:00, zero readers, narrower than real NXT) → replace, don't reuse.
- `shared/calendar.py:156-157` PREMARKET 08:00–08:55 — defined, only read by `is_premarket_hours()`, no trading path.
- `deploy/scheduler.crontab` — pre-open jobs (06:30/08:30/08:50/08:58) = data-prep; after-close (15:32/15:40/16:05+) = batch/observation; **none trade**. Baked into image → rebuild to change.
- **KIS API (verified via kis-code-assistant-mcp)**: `inquire_price` TR `FHKST01010100`, `FID_COND_MRKT_DIV_CODE ∈ {J:KRX, NX:NXT, UN:통합}` — documented unified-quote mechanism (Phase-0 keystone).
