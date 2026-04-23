# Phase 1 Deployment

## News collector

1. `sudo cp deploy/systemd/kis-news-collector.service /etc/systemd/system/`
2. `sudo systemctl daemon-reload && sudo systemctl enable --now kis-news-collector`
3. Verify: `systemctl status kis-news-collector; journalctl -u kis-news-collector -f`

## Macro overnight

1. `bash scripts/cron/install_phase1_crontab.sh`
2. Verify: `crontab -l | grep macro_overnight`
