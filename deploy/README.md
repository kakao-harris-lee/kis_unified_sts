# Deployment Notes

Docker Compose is the canonical runtime surface for dev, paper, and live
services. Use the compose profiles documented in
`docs/runtime_storage_architecture.md` and
`docs/plans/2026-06-06-compose-pipeline-services.md` for trading runtimes.

`deploy/systemd/` is retained as historical Phase 1-5 scaffolding and migration
reference only. Do not install stock pipeline units from this directory for new
paper/live operation.

## Historical Phase 1 Deployment

## News collector

1. `sudo cp deploy/systemd/kis-news-collector.service /etc/systemd/system/`
2. `sudo systemctl daemon-reload && sudo systemctl enable --now kis-news-collector`
3. Verify: `systemctl status kis-news-collector; journalctl -u kis-news-collector -f`

## Macro overnight

1. `bash scripts/cron/install_phase1_crontab.sh`
2. Verify: `crontab -l | grep macro_overnight`
