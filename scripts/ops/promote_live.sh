#!/usr/bin/env bash
# promote_live.sh — promote a validated ANNOTATED tag into the LIVE clone:
# fetch tags, checkout (detached), refresh deps, run the preflight guardrail.
# Refuses unknown or lightweight (non-annotated) tags.
#
# Usage: promote_live.sh <annotated-tag>
# Env:
#   KIS_LIVE_PROJECT     live clone dir (default /home/deploy/project/kis_unified_sts_live)
#   PROMOTE_CHECK_REDIS  pass-through to preflight reachability check (default 0 — infra
#                        may start after promotion); the tag/clean/port checks always run
set -euo pipefail

TAG="${1:-}"
[ -n "$TAG" ] || { echo "usage: promote_live.sh <annotated-tag>" >&2; exit 64; }
LIVE_DIR="${KIS_LIVE_PROJECT:-/home/deploy/project/kis_unified_sts_live}"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ -d "$LIVE_DIR/.git" ] || { echo "promote: '$LIVE_DIR' is not a git clone" >&2; exit 1; }

git -C "$LIVE_DIR" fetch --tags --prune origin >/dev/null 2>&1 || true

git -C "$LIVE_DIR" rev-parse "refs/tags/$TAG" >/dev/null 2>&1 \
  || { echo "promote: tag '$TAG' not found (push the tag to origin, then retry)" >&2; exit 1; }

[ "$(git -C "$LIVE_DIR" cat-file -t "refs/tags/$TAG")" = "tag" ] \
  || { echo "promote: '$TAG' is not an annotated tag (validated releases must be annotated)" >&2; exit 1; }

git -C "$LIVE_DIR" checkout --force --detach "refs/tags/$TAG" >/dev/null 2>&1

# Refresh deps into the live venv (idempotent; skipped if the venv does not exist yet).
if [ -x "$LIVE_DIR/.venv/bin/pip" ]; then
  "$LIVE_DIR/.venv/bin/pip" install -e "$LIVE_DIR" >/dev/null
fi

# The guardrail must pass after promotion (validates tag/clean/port; redis
# reachability gated by PROMOTE_CHECK_REDIS so promotion works before infra is up).
KIS_LIVE_PROJECT="$LIVE_DIR" \
  LIVE_PREFLIGHT_CHECK_REDIS="${PROMOTE_CHECK_REDIS:-0}" \
  REDIS_PORT="${REDIS_PORT:-6382}" \
  "$SELF_DIR/live_preflight.sh"

echo "promote: LIVE now pinned to $TAG"
