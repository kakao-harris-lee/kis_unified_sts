# Deployment Notes

Docker Compose is the canonical runtime surface for dev, paper, and live
services. Use the compose profiles documented in
`docs/runtime_storage_architecture.md` and
`docs/plans/archive/2026-06-06-compose-pipeline-services.md` for trading runtimes.
Long-running news/LLM stream daemons also run through Compose:

```bash
docker compose --env-file .env.paper --profile news up -d news-collector news-scorer
docker compose --env-file .env.live --profile news up -d news-collector news-scorer
```

Host systemd units are not part of the supported runtime. Do not install stock,
futures, news, or LLM pipeline daemons through systemd; run both paper and live
stacks with Docker Compose profiles instead.

## Scheduler

Removed. One-shot scheduled jobs used to run through the Compose `scheduler`
service with supercronic, driven by `scheduler.crontab`. That service and its
crontab went with the legacy runtime
(`docs/plans/2026-11-07-legacy-removal-plan.md`, L1/L2); every job in it
invoked a deleted service or script.

Do not install host crontab entries for the current paper/live runtime. Historical
host-cron notes are kept under `docs/archive/operations/crontab.md`.
