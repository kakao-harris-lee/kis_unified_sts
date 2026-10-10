#!/usr/bin/env bash
# CP-3 tenant session runner TEMPLATE — tracked on purpose, instance values from
# the environment.
#
# Plan docs/plans/2026-10-09-tos-cp3-tenant-render-and-boot-path-plan.md §2.6.
# The resident wrapper (~/.config/kis-probes/tos-paper-session.sh, host-local and
# uncommitted) CANNOT boot a tenant: its render output path
# CONFIG=/home/deploy/.config/tos/paper-config is hardcoded, not an environment
# handle (runbook tos-paper-boot.md §7.2-b, measured 2026-10-09). This template is
# the tenant's own call path. It is NOT a cron job: the first real tenant session
# is an operator decision after ③ lands.
#
# Precedent: tools/broker_probes/runners/run_p_ca.sh (#825). The guards are the
# same ones and they come from the same file — _common.sh beside that runner —
# because a guard kept in two places is a POLICY kept in two places, and this
# harness has already paid for that once (#825 independent review F4).
#
# Guards, in order:
#   1. the checkout this script sits in is clean, DETACHED, and an ancestor of
#      origin/main (#793: a shared checkout lets a parallel lane move the branch
#      under a running session). Override: TENANT_ALLOW_SHARED_CHECKOUT=1, logged.
#   2. every TENANT_* instance value is set. There are NO defaults — the
#      designated tenant paths (runbook §7.2-b) live in the runbook, never here.
#   3. the direction is LONG or SHORT, and the env file is named `.env.mock`
#      (mirrors scripts/tos/render_paper_config.py's own ENV_FILE_NAME guard —
#      a tenant session is mock-only and never reaches a real-money account).
#   4. the stop time parses, is in the future, and is within MAX_SESSION_S.
#   5. TENANT_PYTHON runs, and the tools.tos_cp3 it loads is THIS checkout's,
#      reporting the POLICY_VERSION this template was written for.
#   6. the contract month is derived ONCE and given to both the data-dir leaf and
#      the render (--instrument), exactly as the resident wrapper does it
#      (runbook §7.3 5-a) — two places computing it separately disagree silently
#      on a roll day.
#   7. the boot-proof refusal (plan §2.5): a journal carrying the
#      `cp3-bootproof-synthetic` marker on ANY row may only genesis a fresh,
#      empty directory under the scratch root. The check itself lives in
#      tools/tos_cp3/bootproof_guard.py, which tools/tos_cp3/bootproof_journal.py
#      calls too, so the two entry points cannot drift.
#
# Then: render (the tenant tree declares journal.mode "external", so
# --journal-path is required and the renderer writes no journal of its own) →
# boot → stop at TENANT_STOP_AT → post-stop evidence counts.
#
# This script never deletes itself and touches no crontab.
#
# See docs/runbooks/tos-paper-boot.md §7.2-c for the instantiation recipe.

set -u

# --- 0. the shared guards --------------------------------------------------

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P) || exit 2
# shellcheck source=tools/broker_probes/runners/_common.sh
# shellcheck disable=SC1091
. "$SCRIPT_DIR/../../broker_probes/runners/_common.sh"
# Before the first log() call, so even step 1's ABORT lands in the operator's
# log file (same "tee if set" behaviour run_p_ca.sh has).
set_log_file "${TENANT_LOG:-}"

# --- 1. the checkout -------------------------------------------------------

guard_checkout "$SCRIPT_DIR" "${TENANT_ALLOW_SHARED_CHECKOUT:-0}" \
  TENANT_ALLOW_SHARED_CHECKOUT

# --- 2. generations --------------------------------------------------------
#
# The guard module's own POLICY_VERSION, checked against the one this template
# was written for. Both files live in this checkout, so a mismatch means the
# template was COPIED OUT of a different tree — and a template driving a guard
# of a different generation is a template whose refusals are not the ones its
# header describes.
EXPECT_POLICY_VERSION=cp3-tenant-bootproof/1

# The driver's own SIGKILL_AFTER_S (~/.config/kis-probes/tos_paper_session.py):
# SIGTERM, then this many seconds, then SIGKILL. One number, so the stop path
# here and the resident one mean the same thing.
SIGKILL_AFTER_S=120

# A typo ceiling on the session window, not a tuning knob: TENANT_STOP_AT is a
# wall-clock time, and "2027" instead of "2026" is a session that never ends.
# One trading day is the widest a one-off boot proof can honestly need.
MAX_SESSION_S=28800

# --- 3. instance values (no defaults) --------------------------------------

require_env \
  TENANT_LOG TENANT_PYTHON TENANT_TREE TENANT_DIRECTION TENANT_RENDER_OUT \
  TENANT_DATA_PARENT TENANT_JOURNAL TENANT_STOP_AT TENANT_ENV_FILE \
  TENANT_CUSTODY_ROOT TENANT_ENVIRONMENT_LABEL

ensure_log_file "$TENANT_LOG" TENANT_LOG

case "$TENANT_DIRECTION" in
LONG | SHORT) ;;
*) die "TENANT_DIRECTION must be 'LONG' or 'SHORT' (got '$TENANT_DIRECTION')" ;;
esac

# The renderer refuses any other basename (render_paper_config.py ENV_FILE_NAME,
# design §2 guard "계좌 원천이 모의 파일"). Refusing it HERE too means the
# refusal arrives before the data dir is created and before anything is
# rendered, and it means this template cannot be instantiated against a
# real-money credential file at all.
ENV_BASENAME=${TENANT_ENV_FILE##*/}
[ "$ENV_BASENAME" = ".env.mock" ] ||
  die "TENANT_ENV_FILE must name a file called '.env.mock' (got '$ENV_BASENAME') — a tenant session is mock-only; the renderer refuses any other name and so does this template"
[ -f "$TENANT_ENV_FILE" ] ||
  die "TENANT_ENV_FILE does not exist: $TENANT_ENV_FILE"

TREE_DIR=config/tos_runtime/$TENANT_TREE
[ -d "$REPO/$TREE_DIR" ] ||
  die "TENANT_TREE='$TENANT_TREE' names no config tree: $REPO/$TREE_DIR"

[ -d "$TENANT_CUSTODY_ROOT" ] ||
  die "TENANT_CUSTODY_ROOT does not exist: $TENANT_CUSTODY_ROOT"

# --- 4. the stop time ------------------------------------------------------
#
# In KST, never in whatever offset the operator typed (CLAUDE.md: convert to KST
# BEFORE comparing). `date -d` also rejects an unparseable value, which a prefix
# match would silently let through as empty.
NOW_S=$(TZ=Asia/Seoul date +%s)
STOP_S=$(TZ=Asia/Seoul date -d "$TENANT_STOP_AT" +%s 2>/dev/null) ||
  die "TENANT_STOP_AT='$TENANT_STOP_AT' is not a time this shell can parse"
[ -n "$STOP_S" ] || die "TENANT_STOP_AT='$TENANT_STOP_AT' produced no epoch second"
RUN_S=$((STOP_S - NOW_S))
[ "$RUN_S" -gt 0 ] ||
  die "TENANT_STOP_AT='$TENANT_STOP_AT' is ${RUN_S}s away — it is already past, so the session would stop before it started"
[ "$RUN_S" -le "$MAX_SESSION_S" ] ||
  die "TENANT_STOP_AT='$TENANT_STOP_AT' is ${RUN_S}s away, past the ${MAX_SESSION_S}s ceiling — a one-off boot proof does not run longer than a trading day"

# --- 5. interpreter and guard-module provenance ----------------------------

PY=$TENANT_PYTHON
guard_python_module "$PY" TENANT_PYTHON tools.tos_cp3.bootproof_guard \
  "$EXPECT_POLICY_VERSION"

# --- 6. the contract month — computed ONCE, given to both ------------------
#
# Runbook §7.3 5-a / operator decision 2026-10-04: the durable set is one per
# contract month, the leaf is that code, and the render gets the SAME value. Two
# places computing it separately disagree on a roll day and nobody finds out.
INSTRUMENT=$(PYTHONPATH="$REPO" "$PY" -c \
  'from shared.instruments.futures import get_front_month_code; print(get_front_month_code(product="mini"))' 2>&1) ||
  die "front-month lookup failed in $REPO: $INSTRUMENT"
case "$INSTRUMENT" in
A0[0-9][0-9][0-9][0-9]) : ;;
*) die "instrument '$INSTRUMENT' does not look like a mini front-month code (^A0[0-9]{4}\$)" ;;
esac
DATA_LEAF=$TENANT_DATA_PARENT/$INSTRUMENT
log "instrument=$INSTRUMENT · data leaf $DATA_LEAF"

# --- 7. the boot-proof refusal (plan §2.5) ---------------------------------
#
# BEFORE the leaf is created, so the "newly created and empty" half of the rule
# still has something to say. The journal's own existence is this guard's first
# refusal — not re-checked here, because a second copy of it would be a clause
# that can never fire on its own.
GUARD_OUT=$("$PY" -m tools.tos_cp3.bootproof_guard \
  --journal "$TENANT_JOURNAL" --data-dir "$DATA_LEAF" \
  --instrument "$INSTRUMENT" 2>&1) ||
  die "boot-proof guard refused: $GUARD_OUT"
log "$GUARD_OUT"

if [ ! -d "$TENANT_DATA_PARENT" ]; then
  (umask 077; mkdir -p -- "$TENANT_DATA_PARENT") ||
    die "cannot create data parent $TENANT_DATA_PARENT"
fi
chmod 700 "$TENANT_DATA_PARENT" 2>/dev/null || true
(umask 077; mkdir -p -- "$DATA_LEAF") ||
  die "cannot create data leaf $DATA_LEAF"

# --- 8. render -------------------------------------------------------------
#
# The tenant tree's RENDER.yaml declares direction.mode "declared" (so
# --direction is COMPARED with the tree's own value, never substituted) and
# journal.mode "external" (so --journal-path is required and the renderer writes
# no journal of its own) — plan §2.3 / §2.4.
log "=== RENDER tree=$TENANT_TREE direction=$TENANT_DIRECTION out=$TENANT_RENDER_OUT"
RENDER_LOG=$("$PY" scripts/tos/render_paper_config.py \
  --source "$TREE_DIR" \
  --out "$TENANT_RENDER_OUT" \
  --env-file "$TENANT_ENV_FILE" \
  --instrument "$INSTRUMENT" \
  --direction "$TENANT_DIRECTION" \
  --journal-path "$TENANT_JOURNAL" 2>&1)
render_rc=$?
printf '%s\n' "$RENDER_LOG" >>"$TENANT_LOG"
[ "$render_rc" -eq 0 ] ||
  die "render refused (rc=$render_rc): $(printf '%s' "$RENDER_LOG" | tail -1 | cut -c1-200)"
log "render ok -> $TENANT_RENDER_OUT"

# --- 9. boot ---------------------------------------------------------------
#
# Verbatim the resident boot invocation: the one-liner is
# ~/.config/kis-probes/tos_paper_session.py's CLI constant and runbook §3's
# `run` call, and PYTHONPATH is exactly that driver's
# `tos/src:tos/runtime/src` — the repo root is deliberately NOT on it, so the
# runtime composes with the same path it has in production.
CLI="import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))"
log "=== BOOT label=$TENANT_ENVIRONMENT_LABEL custody=$TENANT_CUSTODY_ROOT stop in ${RUN_S}s ($TENANT_STOP_AT)"
PYTHONPATH="$REPO/tos/src:$REPO/tos/runtime/src" "$PY" -c "$CLI" run \
  --config-dir "$TENANT_RENDER_OUT" \
  --data-dir "$DATA_LEAF" \
  --custody-root "$TENANT_CUSTODY_ROOT" \
  --environment-label "$TENANT_ENVIRONMENT_LABEL" >>"$TENANT_LOG" 2>&1 &
RUN_PID=$!
log "run pid=$RUN_PID"

# --- 10. stop --------------------------------------------------------------

# The ABSOLUTE stop second, not "now + the window measured back in step 4": the
# steps between then and here cost real time (a front-month lookup, the guard, a
# render), so a relative deadline computed here would run past TENANT_STOP_AT by
# however long they took.
DEADLINE=$STOP_S
while [ "$(TZ=Asia/Seoul date +%s)" -lt "$DEADLINE" ]; do
  kill -0 "$RUN_PID" 2>/dev/null || break
  sleep 1
done

if kill -0 "$RUN_PID" 2>/dev/null; then
  log "=== STOP SIGTERM -> pid $RUN_PID"
  kill -TERM "$RUN_PID" 2>/dev/null || true
  waited=0
  while kill -0 "$RUN_PID" 2>/dev/null && [ "$waited" -lt "$SIGKILL_AFTER_S" ]; do
    sleep 1
    waited=$((waited + 1))
  done
  if kill -0 "$RUN_PID" 2>/dev/null; then
    log "WARN: run did not stop within ${SIGKILL_AFTER_S}s of SIGTERM — SIGKILL"
    kill -KILL "$RUN_PID" 2>/dev/null || true
  fi
else
  log "run exited on its own before the stop time"
fi
wait "$RUN_PID" 2>/dev/null
run_rc=$?
log "=== END run rc=$run_rc"

# --- 11. what the durable set holds now (runbook §4) -----------------------
#
# The evidence is the STORE, not the log: run_forever writes nothing per pass,
# and a pass that did not TICK leaves no row (runbook §4). The kind breakdown is
# what §7.9 records — in particular whether anything was CONSUMED or whether the
# fifteen fields read STALE, which is the question plan §2.5 leaves open.
COUNTS=$(
  "$PY" - "$DATA_LEAF" <<'PY' 2>&1
import sqlite3
import sys
from pathlib import Path

data = Path(sys.argv[1])


def rows(db: Path, query: str) -> list[tuple]:
    if not db.is_file():
        return [("<no store>", db.name)]
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return list(conn.execute(query))
    finally:
        conn.close()


print("snapshots:", rows(data / "marketfeed.sqlite3", "SELECT COUNT(*) FROM snapshots"))
print("entries:", rows(data / "evidence.sqlite3", "SELECT COUNT(*) FROM entries"))
for kind, count in rows(
    data / "evidence.sqlite3",
    "SELECT kind, COUNT(*) FROM entries GROUP BY kind ORDER BY 2 DESC LIMIT 25",
):
    print(f"  {kind}: {count}")
PY
) || true
log "post-stop durable set $DATA_LEAF:"
printf '%s\n' "$COUNTS" | while IFS= read -r line; do log "  $line"; done

exit "$run_rc"
