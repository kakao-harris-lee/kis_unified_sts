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
#   3b. the two REAL futures query keys are NOT in this shell's environment
#      (plan §3.4). The producer reads them itself from the file its own config
#      names; every child inherits this environment, so a shell that exported
#      them would hand the real keys to the RUNTIME too.
#   4. the stop time parses, is in the future, and is within MAX_SESSION_S.
#   5. TENANT_PYTHON runs, and the tools.tos_cp3 it loads is THIS checkout's,
#      reporting the POLICY_VERSION this template was written for.
#   6. the contract month is derived ONCE and given to the data-dir leaf, the
#      render (--instrument) and the producer, exactly as the resident wrapper
#      does it (runbook §7.3 5-a) — two places computing it separately disagree
#      silently on a roll day.
#   7. the stop path is armed BEFORE anything is launched, as an EXIT trap as
#      well as a signal trap (plan §3.5): from here on every `die` stops the
#      producer, so a refusal below cannot leave it calling the real quotation
#      API all day.
#   8. the producer is started (seed), and the session waits — bounded, else
#      ABORT — for its first real `tos-cp3-live/…` journal row. That row is
#      already STALE by the time the boot finishes, so the rows present at boot
#      are counted as `consumed_stale_at_boot` and written to a snapshot file
#      the §3.6 extractor reads.
#   9. the data-dir refusal (plan §2.5, as corrected by the review of PR #892):
#      the resident durable set is never a target; otherwise EVERY row's
#      source_id must come from an approved real producer — which step 8 is what
#      makes true. The check lives in tools/tos_cp3/bootproof_guard.py, which
#      tools/tos_cp3/bootproof_journal.py calls too, so the two entry points
#      cannot drift.
#  10. the boot label must equal the rendered tree's own `environment` — the
#      loader does not compare them, so a mismatch is wrong evidence, quietly.
#
# Then: render (the tenant tree declares journal.mode "external", so
# --journal-path is required and the renderer writes no journal of its own) →
# boot → stop at TENANT_STOP_AT → stop the producer → post-stop evidence counts.
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
EXPECT_POLICY_VERSION=cp3-tenant-bootproof/2

# The driver's own SIGKILL_AFTER_S (~/.config/kis-probes/tos_paper_session.py):
# SIGTERM, then this many seconds, then SIGKILL. One number, so the stop path
# here and the resident one mean the same thing.
SIGKILL_AFTER_S=120

# The producer's own grace. It is NOT the runtime's 120 s: the producer has one
# in-flight HTTP request and a summary file to finish, while the runtime has a
# replay and a durable set to close. Ten seconds is above the configured
# request timeout (config/tos_probes/cp3-live-producer.yaml request_timeout_s)
# so a stop lands after the call in flight, not through it.
PRODUCER_SIGKILL_AFTER_S=10

# How long the session waits for the producer's FIRST real journal row before
# giving up (plan §3.5 「상한 있음, 넘으면 ABORT」). Derived, not picked: the
# producer first seeds (it walks back trading days until the strategy's
# vol_window is filled, tens of paginated GETs at the configured pace — PR-1
# measured 「시드 ≈ 수십 콜」), and only then waits for the next minute boundary
# plus G. Ten minutes is well above that and still fails fast against a trading
# day. It is a hang ceiling, not a tuning knob: a producer that has not
# published inside it has something wrong with it, and the session must not
# boot onto a journal it is still hoping for.
FIRST_LINE_TIMEOUT_S=600

# A typo ceiling on the session window, not a tuning knob: TENANT_STOP_AT is a
# wall-clock time, and "2027" instead of "2026" is a session that never ends.
# One trading day is the widest a one-off boot proof can honestly need.
MAX_SESSION_S=28800

# --- 3. instance values (no defaults) --------------------------------------

require_env \
  TENANT_LOG TENANT_PYTHON TENANT_TREE TENANT_DIRECTION TENANT_RENDER_OUT \
  TENANT_DATA_PARENT TENANT_JOURNAL TENANT_STOP_AT TENANT_ENV_FILE \
  TENANT_CUSTODY_ROOT TENANT_ENVIRONMENT_LABEL \
  TENANT_PRODUCER_CONFIG TENANT_PRODUCER_SESSION_DIR

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

# Absolute, so --source names THIS checkout's tree no matter what the renderer
# later resolves it against.
TREE_DIR=$REPO/config/tos_runtime/$TENANT_TREE
[ -d "$TREE_DIR" ] ||
  die "TENANT_TREE='$TENANT_TREE' names no config tree: $TREE_DIR"

[ -d "$TENANT_CUSTODY_ROOT" ] ||
  die "TENANT_CUSTODY_ROOT does not exist: $TENANT_CUSTODY_ROOT"

[ -f "$TENANT_PRODUCER_CONFIG" ] ||
  die "TENANT_PRODUCER_CONFIG names no file: $TENANT_PRODUCER_CONFIG"

# --- 3b. credential separation (plan §3.4) ---------------------------------
#
# Three environments, and only ONE of them may hold a real-money credential:
#
#   runner   — this shell. Mock-only: TENANT_ENV_FILE is `.env.mock` (above).
#   producer — reads the two REAL futures QUERY keys ITSELF, from the file its
#              own config names (`env_file:` in TENANT_PRODUCER_CONFIG). This
#              template never reads, passes or prints them; the producer keys
#              its own token cache by the app key's committed fingerprint, so
#              not even a cache path carries a secret value.
#   runtime  — mock-only, and the one process that must never hold a real key.
#
# A child inherits this environment, so a shell that exported the query keys
# would hand them to the RUNTIME as well — silently, because nothing downstream
# looks. That is the whole failure mode, and the refusal below is its red
# proof's input. Paths are logged; values never are.
for _real_key in KIS_FUTURES_APP_KEY KIS_FUTURES_APP_SECRET; do
  [ -z "$(printenv "$_real_key" || true)" ] ||
    die "$_real_key is set in this shell. The producer reads the real query keys itself, from the env_file its own config names; the runner and the runtime must not carry them, because every child inherits this environment (plan §3.4)"
done
log "credential separation ok: no real futures query key in this environment"

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

# --- 6. the contract month — computed ONCE, given to all three -------------
#
# Runbook §7.3 5-a / operator decision 2026-10-04: the durable set is one per
# contract month, the leaf is that code, and the render gets the SAME value —
# and since PR-3 so does the producer (plan §3.5: "instrument 은 인자로만 받는다").
# Two places computing it separately disagree on a roll day and nobody finds out.
INSTRUMENT=$(PYTHONPATH="$REPO" "$PY" -c \
  'from shared.instruments.futures import get_front_month_code; print(get_front_month_code(product="mini"))' 2>&1) ||
  die "front-month lookup failed in $REPO: $INSTRUMENT"
case "$INSTRUMENT" in
A0[0-9][0-9][0-9][0-9]) : ;;
*) die "instrument '$INSTRUMENT' does not look like a mini front-month code (^A0[0-9]{4}\$)" ;;
esac
DATA_LEAF=$TENANT_DATA_PARENT/$INSTRUMENT
log "instrument=$INSTRUMENT · data leaf $DATA_LEAF"

# --- 7. the stop path, armed BEFORE anything is launched ------------------
#
# ONE stop path, reached four ways: the deadline in step 12, a signal sent to
# THIS script, a child exiting on its own, and — new in PR-3 — ANY `die` below.
# The resident driver forwards signals the same way
# (~/.config/kis-probes/tos_paper_session.py:264 installs the handlers,
# :439-441 and :525-529 are the SIGTERM -> SIGKILL_AFTER_S -> SIGKILL block).
#
# ⚠ The traps go in BEFORE the first `… &`, not after it. A signal arriving in
# the window between a launch and the `trap` statements would otherwise kill
# the runner with the default disposition and leave the child orphaned — the
# very thing the traps exist to prevent, in the one moment nothing is watching
# for it.
#
# ⚠ And the EXIT trap, not only the signal traps (plan §3.5, v2 re-review M1).
# #892 armed the traps after the render, which was enough while nothing ran
# before the boot. The producer starts in step 8, BEFORE the guard, the render
# and the label check — so every refusal between here and the boot would have
# left it running, calling the REAL quotation API all day with nobody watching.
# `die` exits, and an EXIT trap is the one handler an exit cannot skip.
#
# Both PIDs are initialized (#892 re-review L1) so `set -u` has nothing to
# stumble on no matter where the first failure lands.
RUN_PID=""
PRODUCER_PID=""

stop_run() {
  stop_supervised "$RUN_PID" "$SIGKILL_AFTER_S" run
}

stop_producer() {
  stop_supervised "$PRODUCER_PID" "$PRODUCER_SIGKILL_AFTER_S" producer
}

# The runtime first, the producer second: the producer is the one writing the
# journal the runtime reads, and stopping it first would make the runtime's
# last passes look like a feed that went silent.
on_exit() {
  stop_run
  stop_producer
}

# 128+signo, the conventional shell exit code, so a caller can tell an
# interrupted session from a clean one.
on_signal() {
  log "=== SIGNAL $1 received by the runner — forwarding to the children"
  stop_run
  stop_producer
  exit "$2"
}
trap 'on_exit' EXIT
trap 'on_signal TERM 143' TERM
trap 'on_signal INT 130' INT
trap 'on_signal HUP 129' HUP

# --- 8. the producer: seed, then the first real line (plan §3.5) -----------
#
# The boot order is ① producer → ② first real row → ③ guard → render → boot.
# It is not a convenience: the #892 guard refuses an empty journal ("holds no
# rows") and every row must carry an APPROVED producer's source_id, and ③ is
# what makes both true. Nothing here changes what the guard means.
#
# Under `timeout`, for the same reason the boot is: a SIGKILLed runner runs no
# trap, and an orphaned producer spends the day on the real quotation API. The
# ceiling is the stop window plus the producer's own grace, so the external
# alarm never pre-empts a graceful stop already under way.
#
# ONE producer per session — and that lock is NOT re-implemented here. The
# producer takes an exclusive, non-blocking `flock` on its own market root
# (tools/tos_cp3/live_producer/sinks.py::acquire_session_lock) before any other
# check, so a second one refuses itself with a message naming the first. A
# second copy of that rule in this template would be a lock whose two owners
# disagree about what it covers.
PRODUCER_CEILING_S=$((RUN_S + PRODUCER_SIGKILL_AFTER_S))
log "=== PRODUCER instrument=$INSTRUMENT config=$TENANT_PRODUCER_CONFIG session-dir=$TENANT_PRODUCER_SESSION_DIR journal=$TENANT_JOURNAL ceiling ${PRODUCER_CEILING_S}s"
PYTHONPATH="$REPO" \
  timeout --kill-after="${PRODUCER_SIGKILL_AFTER_S}s" "${PRODUCER_CEILING_S}s" \
  "$PY" -m tools.tos_cp3.live_producer.producer \
  --config "$TENANT_PRODUCER_CONFIG" \
  --instrument "$INSTRUMENT" \
  --session-dir "$TENANT_PRODUCER_SESSION_DIR" \
  --journal "$TENANT_JOURNAL" \
  --confirm >>"$TENANT_LOG" 2>&1 &
PRODUCER_PID=$!
log "producer pid=$PRODUCER_PID (supervised by timeout, ceiling ${PRODUCER_CEILING_S}s)"

# --- 8b. wait for the first real row, then snapshot what is there ----------
#
# The predicate is the GUARD's own (`unapproved_rows`, allowlist + delimiter
# rule), not a grep for a prefix in this file: the two must not be able to
# disagree about what "a real producer" means.
#
# The rows present when this returns are the ones the runtime will consume
# STALE — write-to-first-evaluation spans the guard, a render, a boot and a
# replay, i.e. seconds, against a 800 ms budget. They are counted as
# `consumed_stale_at_boot` and their ids are written to a snapshot file, which
# is how tools/tos_cp3/session_inputs.py later tells a structurally
# unconsumable pre-boot line from one the runtime failed to consume (plan §5
# M5, §3.6).
BOOT_SNAPSHOT=$TENANT_PRODUCER_SESSION_DIR/boot-journal-snapshot.json
WAIT_OUT=$("$PY" - "$TENANT_JOURNAL" "$FIRST_LINE_TIMEOUT_S" "$PRODUCER_PID" \
  "$BOOT_SNAPSHOT" <<'PY' 2>&1
import json
import os
import sys
import time
from pathlib import Path

from tools.tos_cp3.bootproof_guard import BootProofGuardRefused, unapproved_rows

journal, timeout_s, producer_pid, snapshot = (
    Path(sys.argv[1]),
    float(sys.argv[2]),
    int(sys.argv[3]),
    Path(sys.argv[4]),
)


def alive(pid: int) -> bool:
    """Is the supervising `timeout` still there?

    The producer is the SHELL's background child, so when it exits the shell
    reaps it and the pid is gone — which is what makes this question cheap to
    ask from here. Without it a producer that refused at boot (a seed that
    cannot fill vol_window, an env pin mismatch) would hold the session for
    the whole ceiling instead of reporting its refusal at once.
    """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


deadline = time.monotonic() + timeout_s
while True:
    try:
        unapproved = unapproved_rows(journal)
    except BootProofGuardRefused:
        unapproved = None  # not written yet, or still empty
    else:
        if unapproved:
            raise SystemExit(
                f"the producer wrote {len(unapproved)} row(s) whose source_id is "
                f"not an approved real producer (lines {list(unapproved)[:5]}) — "
                "the guard would refuse this journal, and waiting longer cannot "
                "unwrite them"
            )
        rows = [
            json.loads(line)
            for line in journal.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(
            json.dumps(
                {
                    "pre_boot_raw_event_ids": [row["raw_event_id"] for row in rows],
                    "consumed_stale_at_boot": len(rows),
                    "journal": str(journal),
                    "note": (
                        "the rows the producer had published when the runtime "
                        "was about to boot; they are STALE by the time it "
                        "evaluates them (plan §5 M5) and are excluded from the "
                        "two M5 counts"
                    ),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(
            f"first real row seen · consumed_stale_at_boot={len(rows)} · "
            f"last={rows[-1]['raw_event_id']} · snapshot {snapshot}"
        )
        break
    if not alive(producer_pid):
        raise SystemExit(
            f"the producer (pid {producer_pid}) exited before writing a usable "
            f"journal row; its refusal is in the session log and in "
            f"{journal.parent}"
        )
    if time.monotonic() >= deadline:
        raise SystemExit(
            f"no approved producer row in {journal} within {timeout_s:.0f}s — "
            "the session does not boot onto a journal it is still hoping for"
        )
    time.sleep(1.0)
PY
) || die "producer never produced a usable first row: $(printf '%s' "$WAIT_OUT" | tail -2 | tr '\n' ' ')"
log "$WAIT_OUT"

# --- 9. the data-dir refusal (plan §2.5, as corrected by review) -----------
#
# BEFORE the leaf is created, so the "newly created and empty" half of the rule
# still has something to say. The journal's own existence is this guard's first
# refusal — not re-checked here, because a second copy of it would be a clause
# that can never fire on its own. (Since PR-3 that refusal is also unreachable
# from THIS entry point: step 8b does not return until the journal holds an
# approved row. It still guards tools/tos_cp3/bootproof_journal.py, the other
# caller.)
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

# --- 10. render ------------------------------------------------------------
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

# --- 10b. the boot label must be the tree's own environment ----------------
#
# `--environment-label` is free-form and the critical-input loader does NOT
# compare its own `environment` token against it (measured; the tenant tree's
# critical_input_policy.yaml header says so in as many words). So a mismatched
# label boots QUIETLY and every snapshot and capsule this session issues carries
# the wrong environment inside its covered content — evidence that is wrong
# rather than missing, in an append-only store. The rendered tree is what
# `compose` actually loads, so that is the copy compared (review LOW).
CIP=$TENANT_RENDER_OUT/critical_input_policy.yaml
TREE_ENV=$("$PY" -c \
  'import sys,yaml;d=yaml.safe_load(open(sys.argv[1],encoding="utf-8"));print(d["environment"])' \
  "$CIP" 2>&1) ||
  die "cannot read environment from $CIP: $TREE_ENV"
[ "$TREE_ENV" = "$TENANT_ENVIRONMENT_LABEL" ] ||
  die "TENANT_ENVIRONMENT_LABEL='$TENANT_ENVIRONMENT_LABEL' but the rendered tree declares environment '$TREE_ENV' ($CIP). The loader does not compare these, so booting would issue capsules whose covered content names the wrong environment"
log "environment label $TENANT_ENVIRONMENT_LABEL matches the rendered tree"

# --- 11. boot --------------------------------------------------------------
#
# Verbatim the resident boot invocation: the one-liner is
# ~/.config/kis-probes/tos_paper_session.py's CLI constant and runbook §3's
# `run` call, and PYTHONPATH is exactly that driver's
# `tos/src:tos/runtime/src` — the repo root is deliberately NOT on it, so the
# runtime composes with the same path it has in production.
#
# ⚠ Under `timeout`, which the traps above CANNOT replace. A trap handles a
# signal this script lives to see; SIGKILL on the runner (or the runner's own
# host dying) delivers nothing, and `run` would then be an orphan with no
# deadline writing into a durable set. `timeout` is a separate supervising
# process with its own alarm, so the child still ends even when this script
# does not get to say so. The ceiling is the stop window plus the same grace
# the runner's own stop path allows, so the external alarm never pre-empts a
# graceful stop that is already under way; `--kill-after` is that same grace
# again, for a child that ignores TERM.
CHILD_CEILING_S=$((RUN_S + SIGKILL_AFTER_S))
CLI="import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))"
log "=== BOOT label=$TENANT_ENVIRONMENT_LABEL custody=$TENANT_CUSTODY_ROOT stop in ${RUN_S}s ($TENANT_STOP_AT) · child ceiling ${CHILD_CEILING_S}s"
PYTHONPATH="$REPO/tos/src:$REPO/tos/runtime/src" \
  timeout --kill-after="${SIGKILL_AFTER_S}s" "${CHILD_CEILING_S}s" \
  "$PY" -c "$CLI" run \
  --config-dir "$TENANT_RENDER_OUT" \
  --data-dir "$DATA_LEAF" \
  --custody-root "$TENANT_CUSTODY_ROOT" \
  --environment-label "$TENANT_ENVIRONMENT_LABEL" >>"$TENANT_LOG" 2>&1 &
RUN_PID=$!
log "run pid=$RUN_PID (supervised by timeout, ceiling ${CHILD_CEILING_S}s)"

# --- 12. stop --------------------------------------------------------------

# The ABSOLUTE stop second, not "now + the window measured back in step 4": the
# steps between then and here cost real time (a front-month lookup, the seed,
# the first-row wait, the guard, a render), so a relative deadline computed
# here would run past TENANT_STOP_AT by however long they took.
DEADLINE=$STOP_S
while [ "$(TZ=Asia/Seoul date +%s)" -lt "$DEADLINE" ]; do
  kill -0 "$RUN_PID" 2>/dev/null || break
  sleep 1
done

if kill -0 "$RUN_PID" 2>/dev/null; then
  stop_run
else
  log "run exited on its own before the stop time"
fi
wait "$RUN_PID" 2>/dev/null
run_rc=$?
log "=== END run rc=$run_rc"

# The producer outlives the runtime by exactly this much: it is stopped here,
# explicitly, so its own `finish()` summary (counters, frozen-frame sha256) is
# on disk before step 13 reads it. The EXIT trap would stop it anyway — this is
# the ordering, not a second mechanism.
stop_producer
wait "$PRODUCER_PID" 2>/dev/null
producer_rc=$?
log "=== END producer rc=$producer_rc"
PRODUCER_SUMMARY=$TENANT_PRODUCER_SESSION_DIR/producer-summary.json
if [ -f "$PRODUCER_SUMMARY" ]; then
  log "producer summary $PRODUCER_SUMMARY:"
  while IFS= read -r line; do log "  $line"; done <"$PRODUCER_SUMMARY"
else
  log "WARN: no producer summary at $PRODUCER_SUMMARY"
fi

# --- 13. what the durable set holds now (runbook §4) -----------------------
#
# The evidence is the STORE, not the log: run_forever writes nothing per pass,
# and a pass that did not TICK leaves no row (runbook §4). The kind breakdown is
# what §7.9 records — in particular whether anything was CONSUMED or whether the
# fifteen fields read STALE. At max_age_ms 800 that is not an open question but
# a certainty — write-to-first-evaluation spans this guard, a render, a boot and
# a replay, i.e. seconds — so the record CONFIRMS it rather than discovering it
# (runbook §7.2-c). Whether the fields are ever CONSUMED is ③'s question: it
# would need an after-boot append path, which is deliberately not built.
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
