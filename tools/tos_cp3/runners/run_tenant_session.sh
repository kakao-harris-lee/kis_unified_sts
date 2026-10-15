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
# A producer that HALTED IN the session is reported as an ABORT (exit 5) rather
# than killing the runtime mid-session (plan §3.5). A producer that ended WITH
# the session — the normal full-day shape, since it stops one minute past the
# last bar and the stop time is later — is not (step 12b).
#
# This script never deletes itself and touches no crontab.
#
# See docs/runbooks/tos-paper-boot.md §7.2-c for the instantiation recipe.

set -u

# --- -1. no execution trace, ever (Codex review HIGH) ----------------------
#
# `set -x` prints every word AFTER expansion, so one traced line can put a real
# app key on the operator's terminal and into TENANT_LOG — and nothing in this
# file has to ask for it: `bash -x run_tenant_session.sh`, or an exported
# `SHELLOPTS=xtrace` from the calling shell, turns tracing on before line 1
# runs. The first cut's credential guard expanded the value into its own test
# (`[ -z "$(printenv "$_real_key")" ]`), so under a trace the guard that exists
# to keep the key out of the runtime printed it instead.
#
# Two defences, because either alone is thin: tracing is turned OFF here,
# before anything reads an environment, and the guard in step 3b is rewritten
# to test for the NAME's presence without ever expanding its value. `+v` goes
# with it — verbose echoes the source line, which is harmless today and would
# not be if a value ever became a literal.
#
# The debugging a reader wants is the log() stream: it carries paths, pids and
# refusals, and never a value.
set +x +v

# --- -0.5. the modes everything this session creates is born with ----------
#
# 0600 files inside 0700 directories, for the whole process and every child.
#
# Why PROCESS-WIDE and not another `(umask 077; …)` subshell: the runtime and
# the renderer pass no mode to their own `mkdir`/sqlite calls, so the modes are
# whatever the inherited umask makes them. The first cut wrapped only the three
# `mkdir`s here, which narrowed the DIRECTORIES and left every FILE inside them
# at the caller's umask — measured on the 2026-10-15 LONG genesis session: the
# four tenant stores (evidence/inbox/marketfeed/rcl sqlite) and the session
# artifacts were 0644 inside 0700 dirs. Decision records carry the account
# number in plaintext (runbook §7.2 좌표 규율), and a 0700 parent is traversal
# protection, not file protection — it stops at the first `chmod` or copy.
#
# Same defect, same fix as the resident wrapper's (runbook §7.2-a, operator
# approved 2026-10-04) — except for the resident wrapper's second half. It adds
# a post-run `chmod` for a durable set an earlier session genesis'd; this
# template deliberately does NOT, because that sweep cannot be made race-free
# here. Step 12c records why, and the runbook carries the operator's one-time
# manual command instead. So `umask` is the ONLY mechanism here, and it is
# enough for everything this session creates.
#
# ⚠ The resident wrapper deliberately does NOT do this globally, because its
# own `git worktree add` must leave the public 0755 checkout alone. That
# exception does not apply here: this template creates no worktree — the
# operator hands it one — and every path it does create (render output, data
# parent and leaf, producer session dir, journal, log) carries coordinates.
umask 077

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
#
# ⚠ The test is on the NAME, never on the value (Codex review HIGH). The first
# cut read the value — `[ -z "$(printenv "$_real_key")" ]` — which is correct
# logic and a leak: under `bash -x` (or an inherited `SHELLOPTS=xtrace`) the
# trace prints the expanded word, so the guard against the key reaching the
# runtime wrote the key into the operator's log. `${!name+x}` expands to `x`
# or to nothing and NEVER to the value, so there is nothing for a trace to
# print even if one were somehow on (step -1 turns it off).
#
# PRESENCE, not non-emptiness: an exported-but-empty `KIS_FUTURES_APP_KEY` is
# an operator who believes they are handing a credential to something. The
# honest answer is the same refusal, not a quiet pass.
for _real_key in KIS_FUTURES_APP_KEY KIS_FUTURES_APP_SECRET; do
  [ -z "${!_real_key+x}" ] ||
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

# --- 6b. the session paths must be what they say they are -----------------
#
# PR #904 review round 1 item B. Fail closed HERE, before a child exists and
# therefore before a store does: a session path that is not the path it names
# is a session whose EVIDENCE lands somewhere the operator did not choose, and
# everything downstream — the guard's containment rule, the data leaf the
# runbook pins, the modes `umask` gives what we create — is stated about the
# path as written. By stop time that is unrecoverable: the stores have already
# been written through the link.
#
# ⚠ This is a check on the paths, NOT a guarantee held across the session. An
# ancestor swapped AFTER this point is not caught, which is exactly why step
# 12c refuses to do a post-stop `chmod` sweep on the strength of it — see the
# Codex MEDIUM recorded there.
#
# Three predicates per path, and the second is the one that catches an
# ancestor: absolute; no component is a symlink; and the fully resolved path
# equals the normalized path it was given. Only components that already EXIST
# can be links, and `realpath` resolves what exists and leaves the rest, so a
# leaf that does not exist yet is still checked against its real ancestors.
PATH_GUARD=$(
  "$PY" - "$TENANT_DATA_PARENT" "$DATA_LEAF" "$TENANT_PRODUCER_SESSION_DIR" \
    "$TENANT_RENDER_OUT" <<'PY' 2>&1
import os
import sys
from pathlib import Path

bad = []
for raw in sys.argv[1:]:
    given = os.path.normpath(raw)
    if not os.path.isabs(raw):
        bad.append(f"{raw!r} is not absolute")
        continue
    for component in [Path(given), *Path(given).parents]:
        if component.is_symlink():
            bad.append(f"{raw!r}: component {str(component)!r} is a symlink")
    resolved = os.path.realpath(raw)
    if resolved != given:
        bad.append(f"{raw!r} resolves to {resolved!r}")
print("; ".join(dict.fromkeys(bad)))
PY
) || die "session path guard failed to run: $PATH_GUARD"
[ -z "$PATH_GUARD" ] ||
  die "a session path is not the path it names, so narrowing its modes at stop would land outside the session: $PATH_GUARD"
log "session paths are literal (no symlinked component, resolve to themselves)"

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
# All three PIDs are initialized (#892 re-review L1) so `set -u` has nothing to
# stumble on no matter where the first failure lands.
RUN_PID=""
PRODUCER_PID=""
WAIT_PID=""

stop_run() {
  stop_supervised "$RUN_PID" "$SIGKILL_AFTER_S" run
}

stop_producer() {
  stop_supervised "$PRODUCER_PID" "$PRODUCER_SIGKILL_AFTER_S" producer
}

# The first-row waiter (step 8b). It is not under `timeout` — it has its own
# deadline — so `stop_supervised`'s group signal finds no group of its own and
# falls back to the pid, which is the right target. Five seconds is ample: it
# sleeps in one-second steps and holds nothing open.
stop_wait() {
  stop_supervised "$WAIT_PID" 5 "first-row wait"
}

# The runtime first, the producer second: the producer is the one writing the
# journal the runtime reads, and stopping it first would make the runtime's
# last passes look like a feed that went silent. The waiter last — it is the
# one that may still be sleeping when a signal arrives.
on_exit() {
  stop_run
  stop_producer
  stop_wait
}

# 128+signo, the conventional shell exit code, so a caller can tell an
# interrupted session from a clean one.
on_signal() {
  log "=== SIGNAL $1 received by the runner — forwarding to the children"
  stop_run
  stop_producer
  stop_wait
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
#
# ⚠ Called TWICE (Claude lane LOW L2): once here, to wait, and once in step 11
# immediately before `run` starts. The guard, the render and the label check
# take seconds, and a bar the producer publishes during them is pre-boot too —
# recorded at first-row time only, it would reach the extractor as a line the
# runtime "failed to consume", which is the defect shape. The second call
# returns at once (rows exist) and rewrites the snapshot as of the boot.
#
# ⚠ In the BACKGROUND, with `wait` (Claude lane MEDIUM M2). As a foreground
# `$(…)` this blocked the shell for up to FIRST_LINE_TIMEOUT_S, and bash runs
# a trap only BETWEEN commands — so a TERM sent to the runner during the wait
# was deferred for up to ten minutes, with the producer running all the while.
# `wait` is interruptible: the handler runs when the signal lands, and
# `stop_wait` ends the waiter with it.
BOOT_SNAPSHOT=$TENANT_PRODUCER_SESSION_DIR/boot-journal-snapshot.json
WAIT_LOG=$TENANT_PRODUCER_SESSION_DIR/first-row-wait.log
(umask 077; mkdir -p -- "$TENANT_PRODUCER_SESSION_DIR") ||
  die "cannot create the producer session directory $TENANT_PRODUCER_SESSION_DIR"

# $1 the bound in seconds, $2 a label for the log line.
first_row_wait() {
  _bound=$1
  _label=$2
  "$PY" - "$TENANT_JOURNAL" "$_bound" "$PRODUCER_PID" \
    "$BOOT_SNAPSHOT" >"$WAIT_LOG" 2>&1 <<'PY' &
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
  WAIT_PID=$!
  log "$_label: pid=$WAIT_PID (bound ${_bound}s, log $WAIT_LOG)"
  if wait "$WAIT_PID"; then
    WAIT_PID=""
  else
    WAIT_PID=""
    die "producer never produced a usable first row ($_label): $(tail -2 "$WAIT_LOG" 2>/dev/null | tr '\n' ' ')"
  fi
  while IFS= read -r line; do log "  $line"; done <"$WAIT_LOG"
}

first_row_wait "$FIRST_LINE_TIMEOUT_S" "first-row wait"

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
# First, the boot-moment snapshot (Claude lane LOW L2). Everything between the
# first row and here — the guard, the render, the label check — is time the
# producer kept publishing in, and those bars are pre-boot too. Taken here,
# the snapshot is what the runtime will actually find already written; taken
# only at first-row time, those bars reach §3.6 as lines the runtime "failed
# to consume", which is the one shape that count exists to make visible.
# The bound is 1 s: the rows are already there, so this returns on its first
# look and never waits — but it is not 0, because a bound of zero would make
# "the file is momentarily unreadable" an ABORT at the last step before boot.
first_row_wait 1 "boot-moment snapshot"

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
# The liveness question is about the GROUP, here as in `stop_supervised`: the
# pid is `timeout`'s, and the runtime outliving its own supervisor is exactly
# the state a leader-only test reports as "exited on its own" (Codex review
# MEDIUM).
DEADLINE=$STOP_S
while [ "$(TZ=Asia/Seoul date +%s)" -lt "$DEADLINE" ]; do
  supervised_group_alive "$RUN_PID" || break
  sleep 1
done

if supervised_group_alive "$RUN_PID"; then
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
#
# Asked BEFORE stopping it: did it last the session, or had it already stopped?
# Plan §3.5 — a producer that halts mid-session (five consecutive
# `produce_error`s, a fetch path that gave up) is reported as an ABORT, because
# from that minute on the journal stops growing and every remaining pass reads
# a frozen one. The runtime keeps running to its own stop time — truncating a
# durable set loses the very evidence the session exists to leave — so the
# report is the EXIT CODE, not a kill.
#
# ⚠ "Already stopped" is NOT the same question as "halted mid-session", and the
# first cut asked only the first one (measured 2026-10-15, the LONG genesis
# session: exit 5 at 15:50:02 on a session that ran its whole day). The
# producer ENDS BY DESIGN after the session's last bar — `run_session` walks
# minute boundaries to `window.end_boundary(target)` (15:46 for a 15:45 close)
# and returns, `main` returns 0 — and the runner's STOP is later than that by
# however long the operator set it. So every full-day session had the producer
# gone before the stop, and every full-day session exited 5.
PRODUCER_SELF_STOPPED=0
supervised_group_alive "$PRODUCER_PID" || PRODUCER_SELF_STOPPED=1
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

# --- 12b. did the producer END the session, or HALT in it? ----------------
#
# ONE clause, and it is the only signal that can answer the question. That is
# the finding of PR #904's review round 1, which measured the first cut's
# other two clauses and found neither could fail on a real input:
#
#   * The SUMMARY's existence and its `stage` cannot discriminate. `finish()`
#     runs in `main`'s `finally`, and `main` returns 0 only after it, so an
#     rc of 0 ALREADY implies a written `stage: "finish"` summary. (A producer
#     SIGKILLed before the `finally` leaves no summary — and rc 137.)
#   * `session_end_reached` could not discriminate either, and that one was
#     measured red: it was the wall clock against `end_boundary` at finish
#     time, and EVERY rc-0 path only returns after the loop has walked past
#     that boundary, so it was always true. Two real producer inputs proved
#     it — a feed dead all day (fetch_error 324, published 0, rc 0, flag TRUE)
#     and a boot after the close (loop never ran, rc 0, flag TRUE). Both are
#     now refusals in the producer itself, where the knowledge lives:
#     `halt_policy.assert_worth_continuing` (the fetch give-up, config key
#     `max_consecutive_fetch_error_minutes`) and
#     `halt_policy.assert_the_session_can_still_happen` (the late boot).
#
# So the producer's EXIT CODE carries the whole verdict, and each side of it
# has a concrete real input:
#   rc 0   -> ENDED the session (the 2026-10-15 genesis shape)
#   rc 1   -> HALTED: a §3.5 give-up (produce_error run, dead-feed minutes),
#             a late boot, a seed/journal/lock refusal, or any traceback
#   rc 137 -> HALTED: killed
PRODUCER_ENDED_THE_SESSION=0
if [ "$producer_rc" -eq 0 ]; then
  PRODUCER_ENDED_THE_SESSION=1
fi
log "producer end: rc=$producer_rc (self-stopped=$PRODUCER_SELF_STOPPED, ended-the-session=$PRODUCER_ENDED_THE_SESSION)"

# --- 12c. there is NO mode repair here, deliberately ----------------------
#
# ⛔ **Do not add one.** PR #904's Codex re-review (MEDIUM, at ccf1f0d0) found
# that a post-stop `chmod` sweep cannot be made safe in this script, and the
# disposition was to REFUSE the automatic repair rather than keep narrowing it.
#
# The first cut did `find -P "$DATA_LEAF" … -type f -links 1 -exec chmod 600`.
# `-P` stops `find` following symlinks and `-links 1` skips hard-linked
# inodes, which closes the shapes a test can construct up front — but both are
# checks made BEFORE the `chmod` that acts on the result, and the gap between
# them is the defect:
#   * an ANCESTOR of the leaf swapped for a symlink after step 6b's check
#     redirects the whole walk;
#   * an entry replaced, or given a second name, between `find`'s test and
#     `chmod`'s syscall is chmodded through the name `find` approved.
# Neither is fixable with `find`; it would need an fd-based walk
# (`openat`/`fchmodat` with `O_NOFOLLOW` at every level), which is not a thing
# this shell template should be growing.
#
# So the modes come from ONE mechanism, which has no window at all: step
# -0.5's process-wide `umask 077` means everything this session CREATES is
# born 0600 inside 0700 — the stores, the journal, the render output, the
# session log, the producer's artifacts. There is nothing left to repair for a
# session that starts here.
#
# What that leaves uncovered, stated rather than silently dropped: a durable
# leaf that an EARLIER, pre-umask session genesis'd keeps the modes it was
# born with. That is one manual `chmod 600` by the operator, once per such
# leaf, and the runbook (§7.2-d 「모드」) carries the command. It is not this
# runner's job: a session cannot safely re-mode a tree it did not create.

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

# Exit code 5: the runtime finished the way it was asked to, and the producer
# HALTED IN the session (step 12b) rather than ending with it.
#
# "The way it was asked to" is 0 OR 143: a session that reaches TENANT_STOP_AT
# is stopped by SIGTERM from this script's own stop path, so 143 is the
# ORDINARY end of a full session, not a failure. Those two are the codes a
# producer's silence has something to add to. Any OTHER code is a runtime
# failure and keeps its own: it is the earlier and larger fact, and replacing
# it with 5 would report a boot that died as a feed that stopped.
#
# ⚠ The middle field is the 2026-10-15 fix: a producer that is gone at the
# stop AND ended the session is the NORMAL full-day shape, not an ABORT.
#
# ⛔ What this does NOT catch, written down rather than implied: a producer
# still ALIVE at the stop. It gives SELF_STOPPED=0, our own stop path SIGTERMs
# it, and no clause here fires — so a producer WEDGED but breathing (a hung
# socket read with no timeout, a `sleep` that never returns) ends a session
# that reports clean. The producer's own give-ups cannot see that either:
# they are checked between boundaries, and a wedged producer never reaches the
# next one. Closing it needs a liveness signal from the producer (a heartbeat
# the runner reads, or a per-boundary watchdog), which this round does not
# build.
case "$PRODUCER_SELF_STOPPED:$PRODUCER_ENDED_THE_SESSION:$run_rc" in
1:0:0 | 1:0:143)
  log "ABORT: the producer halted in the session (producer rc=$producer_rc, run rc=$run_rc) — every pass after that read a journal that was no longer growing, so this session is not a clean one"
  exit 5
  ;;
esac

exit "$run_rc"
