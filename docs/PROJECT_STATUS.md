# Project Status — KIS Unified Trading Platform

**Last updated**: 2026-05-10
**Update cadence**: After every plan version bump (v3.x → v3.y) or operational milestone.

This is a quick-orientation dashboard for an operator or engineer returning to
the project.  For full plan detail see
[docs/plans/2026-05-03-llm-primary-rl-minimization.md](plans/2026-05-03-llm-primary-rl-minimization.md)
(currently v4.7).

---

## Current Phase

**Phase 2 paper validation — LIVE since 2026-05-11 (Mon) 08:55 KST.**

Cutover incident 발견 + 복구 (2026-05-11 10:48):
- Issue: `sts rl paper --strategy rl_mppo` CLI default가 single-strategy mode 강제 → Setup A/C 사일런트 드롭 (2시간)
- Fix: PR #215 (CLI default → None) + PR #216 (9th pre-flight gate)
- Impact: 1-day 영향 (Setup A window 09:10–10:30 미스); 내일(2026-05-12 화) 08:55 KST 자동 가동 시 정상 작동 예상

내일부터 정상 자동 운영 흐름 — operator는 daily verification Telegram만 모니터링.

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

- **Plan (master)**: [docs/plans/2026-05-03-llm-primary-rl-minimization.md](plans/2026-05-03-llm-primary-rl-minimization.md) — currently v4.7, full PR table in §3.1
- **All plans index**: [docs/plans/INDEX.md](plans/INDEX.md) — categorized Active / Reference / Archive
- **Phase 2 startup runbook**: [docs/runbooks/phase2-startup.md](runbooks/phase2-startup.md)
- **All runbooks**: [README.md § 운영 런북](../README.md#운영-런북-runbooks)
- **CLAUDE.md (Claude Code instructions)**: [../CLAUDE.md](../CLAUDE.md)
- **Grafana — Phase 2 monitoring**: dashboard UID `llm-primary-phase2-monitoring`

## Recent PRs (Phase 2 cutover assembly: 2026-05-08~09)

Total: **41 PRs (#168–#208)** assembled over 2 days. Live list: `git log --oneline --since='14 days ago' main`.

### Phase 2 wiring + kill_switch (Day 1)
- **#168/#169/#170/#171** — multi-tier LLM size scaling, LLM veto authority, kill-switch consumer, shadow-logger flush + demote RL + activate Setup A/C
- **#172** — plan v3.1 → v3.2 tracking
- **#173/#174** — KIS API error rate + ClickHouse insert fail trackers (kill_switch 6/6 conditions on real data)
- **#175** — plan v3.2 → v3.3
- **#176/#177** — DRY refactor: `RollingRateTracker` base class + docstring cleanup

### §10.2 Counterfactual + monitoring tooling (Day 1)
- **#178** — counterfactual analysis script (Setup A/C vs RL shadow)
- **#179** — plan v3.3 → v3.4
- **#180** — Grafana dashboard `llm-primary-phase2-monitoring` (7 panels)
- **#181** — plan v3.4 → v3.5 (V4/V5 ClickHouse migrations applied to production)
- **#182/#183** — `rl_shadow_logger` unit tests + stale docstring cleanup
- **#184** — counterfactual weekly cron + OHLCV schema bug fix
- **#185** — `clickhouse_client_from_env` 8123 → 9000 native port fallback (DRY with config)
- **#186** — Prometheus 5 metrics + 4 alerts for shadow loggers
- **#187** — plan v3.5 → v3.6
- **#188** — Phase 2 daily verification cron (4 gates)
- **#189** — plan v3.6 → v3.7

### Phase 2 startup runbook + CI signal restoration (Day 1→2)
- **#190** — `docs/runbooks/phase2-startup.md`
- **#191** — unbreak CI test collection (16 ImportErrors → 0; sibling test dir `__init__.py` collision)
- **#192** — fix time-fragile test_orchestrator
- **#193** — fix retraining pipeline TELEGRAM env independence
- **#194** — exclude `tests/performance/` from main test job
- **#195** — fix time-fragile test_ats_routing AUTO band
- **#196** — plan v3.7 → v3.8
- **#197** — pre-flight check (8-gate operator-run)
- **#198** — plan v3.8 → v3.9
- **#199** — README runbook index expanded
- **#200** — `docs/PROJECT_STATUS.md` 60s dashboard
- **#201** — `reports/` rotation cron (Sun 04:00 KST)
- **#202** — plan v3.9 → v4.0 (major milestone — Phase 2 cutover READY)

### Documentation polish (Day 2)
- **#203** — archive 22 completed plans + `docs/plans/INDEX.md`
- **#204** — plan v4.0 → v4.1
- **#205** — archive 2 stale snapshots + `docs/INDEX.md`
- **#206** — plan v4.1 → v4.2
- **#207** — pytest-xdist as opt-in dev tool (CI keeps serial; 2 parallel-unsafe tests documented for post-cutover fix)
- **#208** — plan v4.2 → v4.7

### Production verification (Day 3)
- 2026-05-10 04:00 KST: `rotate_reports.sh` first-fired automatically (exit=0, no-op as expected — no files past retention threshold yet)
