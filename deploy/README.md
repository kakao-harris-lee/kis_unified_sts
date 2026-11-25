# Deployment Notes

Docker Compose is the canonical runtime surface. The default stack is five
services — `dashboard`, `strategy-builder-ui`, `caddy`, `redis`, `prometheus` —
and the only profile left is `test`:

```bash
docker compose up -d
docker compose --profile test run --rm tests
```

The trading, news and LLM pipeline services and their profiles went with the
legacy runtime (`docs/plans/2026-11-07-legacy-removal-plan.md`, L1/L2); they
last existed at tag `legacy-final` (`6fc17c0f8d25`). The TOS CP-3 tenant and
resident paper sessions are **not** Compose services — they run from host
wrappers under `~/.config/kis-probes/` (see
`docs/runbooks/tos-paper-boot.md`).

Host systemd units are not part of the supported runtime.

## Scheduler

Removed. One-shot scheduled jobs used to run through the Compose `scheduler`
service with supercronic, driven by `scheduler.crontab`. That service and its
crontab went with the legacy runtime
(`docs/plans/2026-11-07-legacy-removal-plan.md`, L1/L2); every job in it
invoked a deleted service or script.

Do not install host crontab entries for the current paper/live runtime. Historical
host-cron notes are kept under `docs/archive/operations/crontab.md`.
