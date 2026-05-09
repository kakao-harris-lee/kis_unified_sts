# Project Status — KIS Unified Trading Platform

**Last updated**: 2026-05-09
**Update cadence**: After every plan version bump (v3.x → v3.y) or operational milestone.

This is a quick-orientation dashboard for an operator or engineer returning to
the project.  For full plan detail see
[docs/plans/2026-05-03-llm-primary-rl-minimization.md](plans/2026-05-03-llm-primary-rl-minimization.md)
(currently v4.1).

---

## Current Phase

**Phase 2 paper validation — cutover scheduled 2026-05-11 (Mon) 08:55 KST.**

All pre-cutover engineering, automation, and documentation is complete.
The cutover itself is a process restart triggered by the existing
`scripts/cron/rl_paper.sh` watchdog — no manual command required.

## Active Strategies (production)

| Asset | Strategy | Mode | Note |
|-------|----------|------|------|
| Stock | `bb_reversion`, `opening_volume_surge`, `volume_accumulation` | Paper | Phase 2 cutover does NOT change stock side |
| Futures (today) | `rl_mppo` | Paper, **primary** | Will demote to `shadow_mode: true` at next 08:55 KST restart |
| Futures (post-cutover) | `setup_a_gap_reversion`, `setup_c_event_reaction` | Paper, **primary** | LLM-augmented threshold + veto + size scaling |
| Futures (post-cutover) | `rl_mppo` | Paper, **shadow** | No Signal emitted; predictions logged to `kospi.rl_shadow_predictions` for counterfactual |

## Automation Schedule (all UTC unless noted)

| Cadence | Job | Channel |
|---------|-----|---------|
| Mon-Fri 08:55 KST (00:55 UTC weekdays — handled by 5-min watchdog) | Orchestrator restart → Phase 2 begins each session | systemd / cron |
| Every 60s during process | RL shadow logger flush | ClickHouse `kospi.rl_shadow_predictions` |
| Every 60s during process | LLM veto logger flush | ClickHouse `kospi.signals_all` (skip_reason=llm_veto) |
| Every 60s during process | Shadow logger Prometheus metrics | Prometheus + 4 alert rules |
| Mon-Fri 16:00 KST | Phase 2 daily verification (4-gate) | Telegram briefing + `reports/daily_verification/YYYY-MM-DD.json` |
| Mon 07:00 KST | Counterfactual weekly report (prev ISO week) | Telegram briefing + `reports/counterfactual/YYYY-WNN.json` |
| Continuous | kill_switch (6 conditions) | Prometheus + Redis |
| Operator-run, Fri EOD | Pre-flight check (8-gate) | `bash scripts/cron/phase2_preflight_check.sh` |

## Key Recent Decisions (2026-05-08)

- **RL_mppo demoted to `shadow_mode: true`**.  No live RL trades; predictions
  retained for 6 months for counterfactual analysis vs Setup A/C.
- **Setup A (gap reversion) + Setup C (event reaction) become primary entries**
  — paper-only since `futures_live.enabled: false`.
- **LLM veto authority** activated for both setups (operator §7-1 grant).
- **§10.2 verification fully automated**: pre-flight → daily → weekly.
- **CI signal restored** for the first time after weeks of false-negative
  collection failures (PR #191–#195 batch).

## What Could Block Phase 2

| Risk | Mitigation in place | Detection time |
|------|---------------------|---------------|
| Orchestrator fails to boot Mon 08:55 KST | watchdog cron retries every 5 min | First 10 min: heartbeat absence; full failure visible by 09:30 KST |
| RL inference loop dead | shadow_logger empty | `rl_shadow_predictions_today=0` gate FAIL @ daily 16:00 KST |
| ClickHouse outage | `dropped_batches` Prometheus metric → alert | `ShadowLoggerBatchesDropped` alert (10 min window) |
| Setup A never fires | (correct on no-gap days; alarm only after 5d) | Daily 16:00 KST gate; week-1 review |
| Telegram silence | TELEGRAM_BRIEFING_* env missing | Pre-flight check |
| Crontab not registered | Pre-flight check |
| futures_live.enabled accidentally true | Pre-flight check |

## Open Items (deferred / wait-state)

| Item | Owner | When |
|------|-------|------|
| Phase 3 Track A operator gates (legal review §1-6, KIS Real smoke test, 증거금, position-recovery drill, kill-switch unit, `futures_live.enabled: true` flip, Gate 3 14d 1-contract live) | Operator (운영자) | After Phase 2 stable for ≥ 2 weeks |
| Phase 4 — RL aux 활성/폐지/재학습 결정 | Engineer + Operator | After 3 months of `signals_all` data accumulation, EV+ confirmed |

## Key References

- **Plan (master)**: [docs/plans/2026-05-03-llm-primary-rl-minimization.md](plans/2026-05-03-llm-primary-rl-minimization.md) — currently v4.1, full PR table in §3.1
- **All plans index**: [docs/plans/INDEX.md](plans/INDEX.md) — categorized Active / Reference / Archive
- **Phase 2 startup runbook**: [docs/runbooks/phase2-startup.md](runbooks/phase2-startup.md)
- **All runbooks**: [README.md § 운영 런북](../README.md#운영-런북-runbooks)
- **CLAUDE.md (Claude Code instructions)**: [../CLAUDE.md](../CLAUDE.md)
- **Grafana — Phase 2 monitoring**: dashboard UID `llm-primary-phase2-monitoring`

## Recent PRs (last 14 days)

See `git log --oneline --since='14 days ago' main` for the full list.  Phase
2 cutover was assembled across PRs #158–#199 (~40 PRs over 6 days).

Highlights:
- #158 (Gate-2 prep) → #171 (Phase 2 wiring)
- #173/#174 (kill_switch real-data conditions)
- #178 (Counterfactual analysis script) + #180 (Grafana dashboard) + #184 (weekly cron) + #186 (Prometheus alerts) + #188 (daily verification) + #197 (pre-flight check)
- #190 (Phase 2 startup runbook) + #199 (README index)
- #191–#195 (CI signal restoration batch)
