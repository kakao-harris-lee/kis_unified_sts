# Futures Paradigm — Legal & Compliance Review

Gate 2 deliverable per `docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md`
§2.2. Template — fill in *during* the operator's review with a regulator
or compliance counsel; commit the completed document before flipping
`futures_live.enabled: true`.

This is **not** legal advice produced by the engineering team. It is a
checklist of items that an operator must verify with appropriate
counsel and KIS account managers, with space to record their findings.

## 1. Broker Terms of Service — Automated trading

KIS (한국투자증권) account ToS reference: <fill in URL/section/date>.

- [ ] Automated/algorithmic trading explicitly **permitted** for the operator's account type (real account, individual or corporate as applicable)
- [ ] No order-rate limit is exceeded by the configured Phase 4/5 pipeline (current cap: spec §2.3 "1계약, 일일 최대 2회"). Document the broker's stated rate limit:
  - Throughput cap: <e.g. 5 req/s per account>
  - Daily order cap: <e.g. unlimited / N orders/day>
- [ ] Disclosure obligations — does the broker require notification of automated trading? <yes/no, doc-ref>
- [ ] Any account-tier upgrade required (e.g. 일반/전문 투자자 distinction) for futures + algorithmic? <answer>

## 2. Tax — Derivatives capital-gains (파생상품 양도세)

As of 2026, Korean derivatives are taxed under the 양도소득세 regime (separate
schedule from regular capital gains). Operator must confirm:

- [ ] Tax rate applicable to operator's account type (currently 11% incl. 지방세 for individuals)
- [ ] Annual exemption threshold (currently 2.5 million KRW basic deduction)
- [ ] **Reporting cadence**: 양도소득세 is filed semi-annually — confirm operator has the bookkeeping to support it
- [ ] Brokerage-issued tax statement (거래내역) — verify it matches our internal `kospi.rl_trades` ledger; reconciliation script TBD if mismatch is possible

## 3. KIS API — TR ID transition (Paper → Real)

The mock server uses simulation TR IDs. Real-account submission requires
the production TR IDs in `config/kis/tr_ids.yaml`. Confirm:

- [ ] Production TR IDs verified for: futures order place, modify, cancel, balance query, fill query — **canonical source: `config/kis/tr_ids.yaml`** (loaded by `shared/execution/tr_ids.py::tr_id()` and consumed via `ExecutionConfig` `default_factory` fields). Diff this file against the KIS account-manager spreadsheet.
- [ ] Real-account API key registered to the same KIS account (no cross-account drift)
- [ ] WebSocket session works in real (not just mock) — `H0IFASP0` quote feed connects + receives live ticks
- [ ] Single-account-only assumption holds — no shared account between automated trading and manual desk activity (would corrupt position state)

## 4. Trading session compliance

- [ ] Day-session window 09:00–15:30 KST stock / 09:00–15:45 KST futures, EOD-flat at 15:15 KST (`eod_close_hour=15, eod_close_minute=15` in `shared/strategy/exit/{three_stage,williams_r_exit,atr_dynamic,setup_target_exit}.py`) — verified, no after-hours fills
- [ ] Night session (`야간 18:00–05:00`) explicitly disabled in `config/market_schedule.yaml` — confirm
- [ ] Holiday calendar source: `services/trading/holiday_cache.py` → KIS official 휴장일 — last refresh date: <YYYY-MM-DD>

## 5. Monitoring & audit-trail obligations

Some jurisdictions require automated trading to retain order/fill audit
trails for N years. Confirm the operator's obligation and our implementation:

- [ ] Required retention period: <N years>
- [ ] Implementation: `kospi.order_fills` TTL = 5 years (V3 migration); `kospi.rl_trades` TTL = 5 years (V4 migration, aligned with order_fills)
- [ ] Audit-bundle-on-demand: `reports/incidents/<ts>/` (rollback runbook §5) — sufficient for a regulator request? <yes/no — note any gap>

## 6. Sign-off

- [ ] Counsel/compliance officer reviewing: <name, date>
- [ ] Operator (final accountable): <name, date>
- [ ] Document committed to repo: <PR#>

**Until all 6 sections are filled in and committed, do not flip
`config/futures_live.yaml::enabled` to `true`.**

Spec: `docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md` §2.2,
"법적 검토" Gate 2 checkpoint.
