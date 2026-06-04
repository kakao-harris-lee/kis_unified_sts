#!/usr/bin/env bash
# live_preflight.sh — refuse to start LIVE trading unless the live checkout is
# pinned to a CLEAN ANNOTATED git tag (= validated code) and the isolated live
# Redis is configured + reachable. Exits 0 only when all checks pass.
#
# Env:
#   KIS_LIVE_PROJECT            live clone dir (default: repo root of this script)
#   REDIS_PORT                  live Redis port from .env (must equal expected port)
#   LIVE_EXPECT_REDIS_PORT      expected live Redis port (default 6382)
#   REDIS_HOST                  default 127.0.0.1
#   LIVE_PREFLIGHT_CHECK_REDIS  1=check reachability (default), 0=skip
set -euo pipefail

DIR="${KIS_LIVE_PROJECT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-}"
EXPECT_REDIS_PORT="${LIVE_EXPECT_REDIS_PORT:-6382}"
CHECK_REDIS="${LIVE_PREFLIGHT_CHECK_REDIS:-1}"

fail() { echo "live-preflight: REFUSE — $1" >&2; exit 1; }

# 1) HEAD must be pinned to an ANNOTATED tag (a validated release).
annotated=""
while read -r t; do
  [ -n "$t" ] || continue
  if [ "$(git -C "$DIR" cat-file -t "refs/tags/$t" 2>/dev/null)" = "tag" ]; then
    annotated="$t"
    break
  fi
done < <(git -C "$DIR" tag --points-at HEAD 2>/dev/null)
[ -n "$annotated" ] || fail "HEAD is not pinned to an annotated tag (validated code required)"

# 2) Working tree must be clean (no edits after validation).
[ -z "$(git -C "$DIR" status --porcelain 2>/dev/null)" ] || fail "working tree is dirty"

# 3) Redis isolation: live .env must target the live port, not paper's.
[ "$REDIS_PORT" = "$EXPECT_REDIS_PORT" ] \
  || fail "REDIS_PORT='$REDIS_PORT' but expected live port $EXPECT_REDIS_PORT (Redis isolation)"

# 4) Live Redis reachable (TCP port open).
if [ "$CHECK_REDIS" = "1" ]; then
  if ! (exec 3<>"/dev/tcp/$REDIS_HOST/$REDIS_PORT") 2>/dev/null; then
    fail "live Redis $REDIS_HOST:$REDIS_PORT not reachable"
  fi
  exec 3>&- || true
fi

echo "live-preflight: OK — tag=$annotated (clean), redis=$REDIS_HOST:$REDIS_PORT"
