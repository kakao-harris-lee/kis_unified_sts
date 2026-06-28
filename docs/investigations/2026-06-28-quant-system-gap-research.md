# Quant System Gap Research - 2026-06-28

This note refreshes the roadmap after the 2026-06-27/28 Workbench and theme
leader work, then separates the next system gaps into KOSPI 200 futures and
stock trading. It is an engineering/product gap note, not legal advice.

## Scope

- Repository state: `theme-leader-universe` worktree, latest local HEAD
  `77b5ded5`.
- Runtime source of truth: `config/strategies/{stock,futures}/*.yaml`,
  `config/market_schedule.yaml`, `config/execution.yaml`, `services/dashboard`,
  `services/stock_order_router`.
- External references:
  - KRX, Guide to Night Session in KRX Derivatives Market:
    https://global.krx.co.kr/contents/GLB/02/0201/0201041003/Guide_to_Night_Session_in_KRX_Derivatives_Market.pdf
  - KRX, Guide to Trading in the Korean Stock Market:
    https://global.krx.co.kr/contents/GLB/01/0109/0109000000/guide_to_trading_in_the_korean_stock_market.pdf
  - FSC, Nextrade ATS approval and launch plan:
    https://www.fsc.go.kr/eng/pr010101/83967
  - FSC, derivatives market 08:45 early-open announcement:
    https://www.fsc.go.kr/eng/pr010101/80143

## Yesterday / Today Work To Reflect In Roadmap

- Signal Decision Trace is no longer only a compact list enrichment. The current
  dashboard route exposes `GET /api/signals/{signal_id}/trace` and the frontend
  renders LLM context, strategy inputs, thresholds, risk/orderability detail,
  lifecycle lineage, scorecard, and degraded evidence gaps. Browser QA evidence
  is captured in `docs/testing/quant-ops-workbench-2026-06-27.md`.
- PR #547 hardening addressed review findings around trace lineage, lifecycle
  reuse, risk payload sourcing, PEP 563 config annotations, theme/fusion
  deduplication, config-driven theme scoring, KST formatting reuse, and removal
  of redundant signal fields.
- Theme leader and fusion ranking are now more transparent and config-driven:
  theme discovery writes paper-safe targets, fusion uses theme state and
  configured scoring weights, and stale snapshots are gated by `generated_at`.
- Futures Setup D (`setup_d_vwap_reversion`) is enabled for paper rollout. It is
  still explicitly validation-gated: the config documents a strong clean-window
  result but caveats a single roughly five-month sample, event-concentrated edge,
  and live disabled status.

## Source-Of-Truth Drift Found

- `docs/ROADMAP.md` and `docs/PROJECT_STATUS.md` were still dated 2026-06-25.
  They listed futures Setup A/C as active, but `setup_d_vwap_reversion` is now
  `enabled: true`.
- The Workbench section under-described the new trace endpoint. It should say
  that the trace is decision-level evidence, not just reject/order IDs.
- `docs/api.md` listed `GET /api/signals` but not
  `GET /api/signals/{signal_id}/trace`.
- Stock ATS/SOR support is split: `config/execution.yaml`,
  `shared/execution/venue_router.py`, and integration tests exist, but
  `ats_routing.enabled` defaults false and `services/stock_order_router/main.py`
  is still intentionally KRX-only for the current daemon increment.
- `config/market_schedule.yaml` is behind current market-structure facts:
  stock extended hours are narrower than Nextrade's 08:00-08:50 and 15:30-20:00
  sessions, futures regular open is still 09:00 even though KOSPI 200
  derivatives moved to 08:45, and the disabled night session comment says
  18:00-05:00 while KRX's own night session reference shows 18:00-06:00.

## KOSPI 200 Futures Gaps

| Gap | Why It Matters | Next Action |
|---|---|---|
| F-9 decoupled chain is implemented but not cut over | The futures monolith remains the primary path; the decoupled chain still needs real 3-5 trading-day shadow evidence before Gate 2. | Run the F-9 runbook, collect evidence with `scripts/ops/futures_evidence_bundle.py`, then use strict verifier + written approval. |
| Setup C still lacks enough real scored-event production | Runtime gating and diagnostics exist, but strategy quality cannot be proven while event scores are sparse. | Run `scripts/ops/setup_c_event_score_observe.py` during live market sessions and fix missing producer/scheduler inputs before tuning thresholds. |
| Setup D is active in paper but under-observed | Backtest evidence is promising but sample-concentrated; this is exactly where paper/backtest divergence can hide. | Add Setup D to daily evidence review: signal count, rejection reasons, paper PnL, backtest-vs-paper delta, long/short split, volatility-event attribution. |
| Contract/session governance is incomplete | KRX references distinguish full KOSPI 200 futures (KRW 250,000 multiplier, 0.05 tick) from Mini (KRW 50,000 multiplier, 0.02 tick), second-Thursday expiry, and separate night-session quote validity. Wrong tick/session config can block all entries or misstate risk. | Make the active product explicit in operator docs and dashboards; reconcile `FUTURES_TRADING_PRODUCT`, `FUTURES_SLIPPAGE_TICK_SIZE`, roll/expiry handling, and front-month symbol selection. |
| Futures schedule is stale | The repo still has futures regular open at 09:00. FSC announced KOSPI 200 futures/options 08:45 open; KRX night-session material shows 18:00-06:00 for the new own night session. | Do not blindly enable more trading. First decide whether the product intentionally ignores 08:45 and night trading; then encode that policy in schedule config, docs, and order guards. |
| Night session is policy-disabled but not deeply modeled | KRX night sessions use separate order validity, lower quote limits, and separate accumulated quotation limits. | Keep fail-closed until feed, order, risk, kill-switch, liquidity, and settlement assumptions are explicitly validated. |
| HAR-RV remains pre-cutover | Log-RV/refit paths exist, but real-data validation and shadow evidence remain open. | Complete raw-vs-log report, backtest, and one-week shadow before changing default forecast config. |
| Trace UX needs per-strategy evidence slices | The new decision trace explains a single signal; promotion still needs strategy-level transparency by Setup A/C/D. | Add per-strategy evidence widgets: recent accepted/rejected signals, top reject stages, paper-vs-backtest delta, and gate status. |

## Stock Trading Gaps

| Gap | Why It Matters | Next Action |
|---|---|---|
| ATS/Nextrade/SOR is not operational | FSC describes Nextrade pre-market 08:00-08:50, after-market 15:30-20:00, new midpoint/stop-limit order types, lower fees, and best-execution/SOR obligations. Current daemon is KRX-only and ATS config is disabled. | Make a product decision: KRX-only v1 by policy, or ATS-readiness track. If ATS track, add venue quotes, SOR audit logs, order-type support, paper simulator calibration, and dashboard venue evidence. |
| Stock schedule is stale for multi-market reality | Current extended-hours config is 08:30-08:40 and 15:40-16:00, not the ATS windows. | Either document that stock automation trades KRX regular-session only, or update schedule/guards after ATS feed and routing support exist. |
| Theme leader/fusion is new and needs evidence | Theme matching can create false positives via broad keywords or homonyms, and fusion quality depends on freshness plus LLM/realtime balance. | Track theme target freshness, active/quarantined counts, per-theme hit quality, false-positive examples, and rollback thresholds. |
| Active stock strategies still need performance governance | `momentum_breakout` remains under redesign/observation; `technical_consensus` reactivation is not decided. | Use `scripts/ops/stock_strategy_readiness.py` with paper and experiment evidence before any YAML reactivation/retune. |
| KRX market stabilization rules need first-class orderability signals | Stock-side KRX rules include circuit breakers, sidecars, volatility interruption, individual issue suspension, and short-selling constraints. | Surface halt/VI/sidecar/investment-warning/orderability state consistently from screener/fusion into risk and order-routing traces. |
| Position recovery and E2E restart drills are still open | Decoupled stock pipeline depends on Redis streams plus SQLite ledger for state continuity. | Run Redis+SQLite smoke and restart recovery drill after each cutover; keep no-blanket-EOD stock swing behavior intact. |
| HAR-RV and MLflow operations remain unfinished | Forecast transition and experiment tracking are not yet stable operational inputs. | Finish real-data HAR-RV validation and restart MLflow only as optional experiment tracking, not runtime dependency. |
| Live stock trading remains blocked | Real accounts lack the required approvals; paper safety boundaries must stay clear. | Keep live controls out of Workbench and require separate account/compliance promotion gate. |

## Recommended Priority

1. P0 documentation sync: update ROADMAP, PROJECT_STATUS, docs index, and API
   docs so operators see Setup D, the trace endpoint, and the new research gaps.
2. P1 futures evidence: run F-9 Gate 1, Setup D paper observation, and Setup C
   event-score observation before considering futures cutover/live gates.
3. P1 stock venue policy: explicitly choose KRX-only v1 or open an ATS/SOR
   readiness track. Leaving partial ATS code hidden behind disabled config is
   fine only if the roadmap says that is intentional.
4. P2 schedule and contract governance: reconcile product/session facts against
   current config without changing runtime behavior until operator policy is
   clear.
5. P2 transparency UX: extend Signal Decision Trace into per-strategy and
   per-asset evidence dashboards.
6. P3 platform debt: continue orchestrator decomposition, HAR-RV validation,
   MLflow restart, and restart/recovery drills.
