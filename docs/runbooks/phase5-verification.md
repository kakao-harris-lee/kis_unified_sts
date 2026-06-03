# Phase 5 Verification Runbook

Gate-by-gate verification checklist matching the rollout spec
`docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md` §2.

Use this runbook **in order** — each gate has prerequisite checks that
must pass before the next begins.

## Pre-flight (always)

- [ ] Phase 4 paper run is healthy and has accumulated ≥ 2 weeks of clean
      data (Phase 4 verification runbook signed off)
- [ ] Phase 3 final sign-off via `scripts/walk_forward_paper_foldin.py`
      has either passed or has a documented reason for proceeding under
      "conditional provisional sign-off" (paper data is the primary
      evidence path — see `phase3-verification.md` § "Phase 3 status
      determination")
- [ ] All Phase 5 PRs merged: #142–#147 + Tasks 7–10 (this runbook lives
      in Task 7's PR; verify other Task PRs merged before declaring Gate 1
      complete)

---

## Gate 1 — Paper extension (≥ 2 weeks)

Paper-mode continuation past Phase 4's 2-week gate, with the new
operational tooling (Weekly Edge Review, recover_positions, flatten_all)
exercised at least once.

- [ ] Paper run continued ≥ 2 weeks past Phase 4 sign-off date
- [ ] At least 1 Weekly Edge Review delivered via Telegram (Mon 06:00 KST)
      with no `pause` actions — see `scripts/analysis/weekly_edge_review.py`
- [ ] `scripts/trading/recover_positions.py` exercised in dry-run mode at
      least once during the paper window (no divergence found, OR
      divergence handled per runbook)
- [ ] `python -m scripts.trading.flatten_all` (no `--confirm`) printed a
      reasonable dry-run summary at least once
- [ ] React Dashboard / ClickHouse reports have 2+ weeks of populated paper data

**Fallback**: If paper data is < 2 weeks at this point (e.g. interrupted
by infra issue), restart the 2-week clock. Do *not* substitute backtest
fold-in — Phase 3 § "Phase 3 status determination" already explained why.

---

## Gate 2 — Real-account preparation (no live trades yet)

Per spec §2.2.

- [ ] **Legal review complete and committed** — `docs/runbooks/futures-legal-review.md`
      sections 1–6 all filled in and signed off
- [ ] **Tax/derivatives capital-gains process documented** (legal review §2)
- [ ] **KIS Real-account API smoke test passed** — production TR IDs
      respond, balance query returns expected fields, WebSocket quote
      feed connects on real (not mock)
- [ ] **Margin deposited** — at least 1 contract × KOSPI200 mini margin
      requirement + buffer (≈ 2M KRW per spec)
- [ ] **Contract spec re-verified** (CLAUDE.md §Q4): multiplier 50_000 /
      tick 0.02pt / tick_value 1_000 — `config/execution.yaml ::
      futures_contract_spec`
- [ ] **Commission rate confirmed** with KIS account manager and updated
      in `config/execution.yaml`
- [ ] **Position-recovery drill** — manually create a divergence
      (e.g. Redis key delete) and verify `recover_positions.py` writes
      the sentinel + Telegram alert; clear via
      `scripts/recover_positions_clear.sh`
- [ ] **`config/futures_live.yaml::enabled` flipped to `true`** (this is
      the explicit go-live switch — only do this after all above are
      checked)

---

## Gate 3 — 1-contract live, 2 weeks

Per spec §2.3. All conditions must hold for **all 14 calendar days**
(weekends counted in the window but no trades expected). Any miss → Gate 3
fails, immediate rollback per `futures-paradigm-rollback.md`, return to
Gate 1.

- [ ] `futures_live.max_position_size_contracts: 1` enforced
- [ ] `futures_live.max_daily_trades: 2` enforced (no day exceeded)
- [ ] **Daily MDD -3% breaches: 0 events**
- [ ] **Cumulative net PnL > slippage + fees** (positive after costs) by end of window
- [ ] Average entry slippage ≤ 0.4 ticks (rolling 14-day) from ClickHouse
      `kospi.order_fills`
- [ ] Kill-switch trips: 0 (any trip → fail)
- [ ] API error rate < 2% on 5-min rolling window from Prometheus alerts

**Daily check** (record in operator log):

```text
Day N (YYYY-MM-DD):
  - trades:           <n>/2
  - pnl_today:        <KRW>
  - cum_pnl_window:   <KRW>
  - mdd_today_pct:    <-x.x%>
  - slip_avg_today:   <x.x ticks>
  - kill_switch_trips:<n>
  - api_error_rate:   <x.x%>
```

---

## Gate 4 — Increment decision (1 → 2 contracts)

Per spec §2.4.

- [ ] Gate 3 passed cleanly (all conditions held for full 14 days)
- [ ] **Operator written approval recorded** in this runbook (PR comment
      or commit message linking back to Gate 3 daily-check log)
- [ ] `config/risk.yaml::max_position_size_contracts` raised to 2
- [ ] `config/futures_live.yaml::max_position_size_contracts` raised to 2
- [ ] Position-sizer caps reviewed and adjusted
- [ ] **Re-run Gate 3** at 2-contract size (another 14-day window)

**Hard ceiling: 5 contracts** (≈ 25M KRW risk per spec §2.4 "무한 증량 금지").
Any progression past 5 requires a new strategic-planning round, not just
an operational sign-off.

---

## Phase 5 completion gate (per spec §8)

After Gate 4's first 2-contract success:

- [ ] Gates 1, 2, 3 all passed (each documented above)
- [ ] React Dashboard, Prometheus alerts, and Telegram reports consulted regularly
- [ ] Weekly Edge Review delivered for **8 consecutive weeks** (Phase 4
      end → Phase 5 end) without breaking
- [ ] Rollback drill performed at least once (output committed to
      `reports/drills/`)
- [ ] CLAUDE.md updated per spec §7.2 (Setup A/C in "현재 운용 전략",
      ML/RL removed, link to `futures_contract_spec`)
- [ ] Operator written sign-off (PR comment or commit on this file)

Spec: `docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md` §2 + §8.
