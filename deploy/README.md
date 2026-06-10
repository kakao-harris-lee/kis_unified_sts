# Deployment Notes

Docker Compose is the canonical runtime surface for dev, paper, and live
services. Use the compose profiles documented in
`docs/runtime_storage_architecture.md` and
`docs/plans/2026-06-06-compose-pipeline-services.md` for trading runtimes.
Long-running news/LLM stream daemons also run through Compose:

```bash
docker compose --env-file .env.paper --profile news up -d news-collector news-scorer
docker compose --env-file .env.live --profile news up -d news-collector news-scorer
```

`deploy/systemd/` is retained as historical Phase 1-5 scaffolding and migration
reference only. Do not install stock/news pipeline units from this directory for
new paper/live operation.

## Historical Phase 1 Deployment

## Macro overnight

1. `bash scripts/cron/install_phase1_crontab.sh`
2. Verify: `crontab -l | grep macro_overnight`
