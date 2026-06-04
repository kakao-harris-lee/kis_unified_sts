# Runbook — Paper/Live Source-Code Separation

Design: `docs/superpowers/specs/2026-06-04-paper-live-code-separation-design.md`

LIVE trading runs only validated (annotated-tag) code from a **separate clone**.
paper/dev keeps tracking `main` in the existing checkout.

```
/home/deploy/project/kis_unified_sts        paper/dev — main (unchanged)
/home/deploy/project/kis_unified_sts_live   live — pinned to a validated tag
```

## 1. One-time: create the live clone (operator)

> Secrets (`.env.live`) are operator-owned. Do NOT commit them or hand them to tooling.

```bash
cd /home/deploy/project
git clone git@github.com:kakao-harris-lee/kis_unified_sts.git kis_unified_sts_live
cd kis_unified_sts_live
python3 -m venv .venv
.venv/bin/pip install -e .

# Live env: copy the template, fill REAL live KIS credentials.
cp .env.live.example .env
#   set KIS_FUTURES_APP_KEY/SECRET/ACCOUNT_NO (real), KIS_REAL_TRADING=true,
#   KIS_FUTURES_MARKET=real, REDIS_PORT=6382, RUNTIME_STORAGE_SQLITE_PATH=data/runtime/live/runtime.db
```

## 2. Start the isolated live Redis

```bash
cd /home/deploy/project/kis_unified_sts_live
docker compose --env-file .env up -d redis   # -> 127.0.0.1:6382, container kis_live-redis
```

## 3. Promote a validated build (paper -> live)

On the paper/dev checkout, after validation passes (backtest/Optuna, paper trading,
Phase 5 Gates, regime-gate counterfactual):

```bash
cd /home/deploy/project/kis_unified_sts
git tag -a v2026.06.04 -m "validated: <evidence / gate refs>"
git push origin v2026.06.04
```

Then promote into the live clone:

```bash
cd /home/deploy/project/kis_unified_sts_live
KIS_LIVE_PROJECT=$PWD scripts/ops/promote_live.sh v2026.06.04
```

`promote_live.sh` fetches the tag, checks it out (detached), refreshes the live venv,
and runs the preflight guardrail. It REFUSES lightweight/unknown tags.

## 4. Install the LIVE cron

> Only after Gate 1-3 pass + written approval. See `docs/runbooks/phase5-verification.md`.

Append `deploy/cron/kis-live.crontab.example` to the host crontab (`crontab -e`).
Every trade-start line is gated by `scripts/ops/live_preflight.sh`.

## 5. Verify

```bash
cd /home/deploy/project/kis_unified_sts_live
set -a && . ./.env && set +a
bash scripts/ops/live_preflight.sh   # expect: "live-preflight: OK — tag=... (clean), redis=127.0.0.1:6382"
git -C . describe --tags --exact-match HEAD   # must print the validated tag
```

If preflight prints `REFUSE`, live trading will NOT start — fix the cause:
- "not pinned to an annotated tag" -> run `promote_live.sh <tag>`
- "working tree is dirty" -> `git -C . restore .` (never hand-edit the live clone)
- "Redis ... isolation" -> `.env` `REDIS_PORT` must be `6382`
- "Redis ... not reachable" -> start the live compose redis (step 2)

## 6. Rollback

```bash
cd /home/deploy/project/kis_unified_sts_live
KIS_LIVE_PROJECT=$PWD scripts/ops/promote_live.sh <previous-validated-tag>
```

For an immediate halt independent of code: set the kill switch
`redis-cli -p 6382 -n 1 set futures:live:suspended 1` (see futures-paradigm-rollback runbook).

## Guarantees

- Live runs only clean, annotated-tag code (preflight refuses anything else).
- paper (6381) and live (6382) use separate Redis instances — no position/state collision.
- paper/dev checkout and its cron are unchanged; the existing live gates
  (`futures_live.enabled`, `futures:live:suspended`, `--yes-live`) still apply.
