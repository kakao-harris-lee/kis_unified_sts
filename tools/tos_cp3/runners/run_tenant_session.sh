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
#   3b. no REAL query key of ANY market (futures or stock) is in this shell's
#      environment (plan §3.4; PR #922 review LOW-3). The producer reads them
#      itself from the file its own config names; every child inherits this
#      environment, so a shell that exported them would hand the real keys to
#      the RUNTIME too.
#   4. the stop time parses, is in the future, and is within MAX_SESSION_S.
#   5. TENANT_PYTHON runs, and the tools.tos_cp3 it loads is THIS checkout's,
#      reporting the POLICY_VERSION this template was written for.
#   5b. the producer config's market equals the tree's own RENDER.yaml market,
#      and transport and instrument follow it: futures -> synthetic + the
#      derived front month; stock (the MOCK order tree, PR-3a) -> kis-mock + the
#      named TENANT_INSTRUMENT (matching the tree's instrument.pattern) + the
#      deploy-time TENANT_KIS_MOCK_TRANSPORT_CONFIG. Before the producer starts.
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
# See docs/runbooks/tos-paper-boot-history.md §7.2-c for the superseded recipe; today's procedure is
# docs/runbooks/tos-paper-boot.md §7.2-d.

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
# manual command instead.
#
# So this script executes NO `chmod` and NO `chown`, anywhere (pinned by
# `test_the_runner_runs_no_mode_repair_sweep_after_the_stop`). It has exactly
# two mode mechanisms, and only the first writes anything:
#   1. this `umask`, which decides the mode of everything the session CREATES;
#   2. a READ-ONLY refusal in step 9 — a data parent that already existed and
#      is not mode 700 ends the session instead of being altered.
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

# ⚠ **The band GET is its OWN PROCESS, and this runner owns its clock**
# (band plan v3, 2026-10-16 operator decision). Four review rounds established
# that the producer could not bound its own HTTP call honestly — phase timeouts
# bound one chunk, an `iter_bytes()` deadline sees only decoded content, and a
# worker thread leaves the caller blocking in `close()`, hashes outside the
# budget and strands the token lock. A process under `timeout` has none of
# those holes: SIGKILL does not negotiate. So:
#
#   open + one boundary  ->  launch the band process (its own process group)
#   it exits without a line  ->  exactly ONE retry at the next boundary
#   then  ->  wait for the LINE, then BAND ABSENT or boot
#
# How long one band process may live. Derived, not picked: one attempt is
# bounded by `request_timeout_s` (10 s, config/tos_probes/cp3-live-producer.yaml)
# for the GET, plus up to `pace_s` (1.1 s) of pacing, plus an OAuth token POST
# when the producer's cached token is cold, plus interpreter start and the
# config/calendar read. 30 s covers all of that with room and is still far
# inside one 60 s boundary, so a hung process cannot eat the retry's slot.
BAND_PROCESS_TIMEOUT_S=${CP3_BAND_PROCESS_TIMEOUT_S:-30}

# A ceiling on the "wait until open + one boundary" sleep. Empty in production,
# where the real ceiling is STOP_S: a boot at 08:00 legitimately waits ~46 min,
# and shortening that is how the band gets read pre-open. Set to 0 by the
# runner tests, which cannot sit out a real market morning — they prove the
# anchoring by reading the COMPUTED wait this step logs, not by living through
# it. Deliberately outside the `TENANT_*` namespace, which
# `test_runner_template_carries_no_instance_defaults` pins to carry no
# defaults.
BAND_LAUNCH_MAX_WAIT_S=${CP3_BAND_LAUNCH_MAX_WAIT_S:-}

# The gap before the ONE retry: one minute-bar boundary. Not a tuning knob and
# not shortened for the tests, which sit through it — the whole point of
# waiting is that the cures for the soft failures this retries (a rate-limit
# burst, one expired token, a single 500) arrive with the next minute, so a
# retry fired immediately would spend the day's second and last attempt on the
# same bad minute.
BAND_RETRY_BOUNDARY_S=60

# `band_process_run`'s own return value for "the session stop leaves no room
# to start this attempt" — distinct from every code the attempt itself can
# produce, so the caller never mistakes it for a slow broker and never
# retries it. `timeout` uses 124/125/126/127 and otherwise passes the child's
# code through, and the probe's own codes are 0-4; 200 collides with none of
# them (review round 6, Codex MEDIUM).
BAND_RC_NO_TIME=200

# How far before STOP_S a band attempt must already be finished, kill grace
# included. Five seconds, and it is not a comfort number: it covers (a) the
# whole-second truncation of `date +%s`, which is already handled by a
# separate `- 1`, and (b) the latency between computing the budget and the
# kernel starting `timeout` — two `log` calls here, but on a loaded host a
# shell statement is not instantaneous (Codex measured a 6.1s logging stall
# in exactly this gap, review round 7). Five seconds is small against the
# 30s ceiling and a whole minute-bar boundary, and large against any stall
# this script has been observed to suffer. It is a floor on honesty, not a
# tuning knob: raising it shortens the band's window, lowering it lets an
# attempt outlive the session.
BAND_STOP_MARGIN_S=5

# The band process gets SIGKILL this long after SIGTERM. Five seconds: it has
# one in-flight request and one small file to finish, unlike the runtime's
# durable set (SIGKILL_AFTER_S 120).
BAND_PROCESS_KILL_AFTER_S=5

# How long step 8c waits for the LINE. Short on purpose, and the reason is the
# process split: by the time this wait starts, BOTH attempts have already been
# `wait`ed on and exited, so a usable line is either on disk already or is
# never coming. The allowance covers only the seam — a writer SIGKILLed just as
# it replaced the file, or a line whose three clauses this step re-reads — and
# 20 s is far more than a local atomic replace needs while staying well inside
# one boundary. It is NOT where a slow broker is absorbed: that budget is
# BAND_PROCESS_TIMEOUT_S plus the one retry, above. Past it the band is ABSENT
# for this session, which is the conservative direction (UNKNOWN -> the kernel
# sends nothing) and NOT a reason to abort.
BAND_LINE_EXTRA_WAIT_S=${CP3_BAND_LINE_EXTRA_WAIT_S:-20}

# The outer stop on step 14's B3 reconciliation. NOT its budget — that is
# config/tos_cp3_b3.yaml::total_timeout_s, which the tool hands to each step as
# the time it has left. This is the stop for the case that budget cannot cover:
# the tool's own interpreter wedging before it ever starts a step. It has to
# exist because this runs while the cron wrapper still holds its flock, and a
# step with no ceiling at all would refuse TOMORROW's session ("lock busy").
# Ten minutes, read together with the config value by
# `test_the_b3_budget_stays_under_the_runners_ceiling`.
B3_CEILING_S=${CP3_B3_CEILING_S:-600}

# A typo ceiling on the session window, not a tuning knob: TENANT_STOP_AT is a
# wall-clock time, and "2027" instead of "2026" is a session that never ends.
# One trading day is the widest a one-off boot proof can honestly need — and a
# day KRX shifts an hour late (#924, the exam day: 08:38 cron start -> 16:45
# close + 5 min = 8h12m) is still one trading day, so the ceiling is 9 h, not 8.
MAX_SESSION_S=32400

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
#
# WHICH keys (PR #922 review LOW-3): the first cut named the futures pair only,
# so a STOCK tenant's shell could carry KIS_STOCK_APP_KEY/SECRET into the
# runtime unseen. Every known market's pair is refused now — the runtime must
# hold no real key of ANY market, not just of the one this session trades — so
# this step needs no market at all and runs before any child process exists.
# The table is pinned against `tools.tos_cp3.live_producer.config.MARKETS[*]
# .credential_keys` by tests/tools/test_cp3_bootproof.py, so it cannot drift
# from the producer's own idea of which file keys it reads.
_REAL_KEYS_FUTURES="KIS_FUTURES_APP_KEY KIS_FUTURES_APP_SECRET"
_REAL_KEYS_STOCK="KIS_STOCK_APP_KEY KIS_STOCK_APP_SECRET"
for _real_key in $_REAL_KEYS_FUTURES $_REAL_KEYS_STOCK; do
  [ -z "${!_real_key+x}" ] ||
    die "$_real_key is set in this shell. The producer reads the real query keys itself, from the env_file its own config names; the runner and the runtime must not carry them, because every child inherits this environment (plan §3.4)"
done
log "credential separation ok: no real query key of any market in this environment"

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

# --- 5b. the market: producer and tree must agree (PR-3c) ------------------
#
# Read with the SAME parser the producer's loader uses (yaml.safe_load —
# tools/tos_cp3/live_producer/config.py::load_config), so a config carrying a
# duplicate `market:` key resolves here exactly as it does there (the last one
# wins; #936 review LOW-3 — a first-match `sed` and the loader disagreed). Not
# load_config itself: that validates every producer setting, which is the
# producer's own job at step 8, and refusing on, say, a calendar here would
# report a market fault for a calendar one.
#
# The TREE's market is the tree's own manifest field (RENDER.yaml `market:`),
# never a list of tree names here (#936 review LOW-1): a futures tree paired with
# the stock producer config — or the reverse — is refused HERE, before step 8
# starts the producer's real-quote GETs, not later by the runtime.
#
# The stock instrument is matched against the tree's own `instrument.pattern`
# (#936 review MEDIUM — the same field the renderer enforces): the stock tree is
# single-symbol, so a different six-digit code is refused before anything runs.
# TENANT_INSTRUMENT may be unset (futures); an empty argument then, without the
# default-expansion form this template's no-instance-defaults rule forbids.
_INSTRUMENT_ARG=
[ -z "${TENANT_INSTRUMENT+x}" ] || _INSTRUMENT_ARG=$TENANT_INSTRUMENT
MARKETS_OUT=$("$PY" - "$TENANT_PRODUCER_CONFIG" "$TREE_DIR/RENDER.yaml" \
  "$_INSTRUMENT_ARG" <<'PY' 2>&1
import re
import sys

import yaml

with open(sys.argv[1], encoding="utf-8") as handle:
    producer = yaml.safe_load(handle)
with open(sys.argv[2], encoding="utf-8") as handle:
    tree = yaml.safe_load(handle)
producer = producer if isinstance(producer, dict) else {}
tree = tree if isinstance(tree, dict) else {}
block = tree.get("instrument")
pattern = block.get("pattern") if isinstance(block, dict) else None
instrument = sys.argv[3]
if not instrument:
    match = "none"
elif not isinstance(pattern, str):
    match = "nopattern"
else:
    match = "match" if re.fullmatch(pattern, instrument) else "nomatch"
print(producer.get("market"), tree.get("market"), match)
PY
) || die "cannot read the market from $TENANT_PRODUCER_CONFIG / $TREE_DIR/RENDER.yaml: $(printf '%s' "$MARKETS_OUT" | tail -1)"
read -r _MARKET TREE_MARKET INSTRUMENT_MATCH <<<"$MARKETS_OUT"
case "$_MARKET" in
futures | stock) ;;
*) die "TENANT_PRODUCER_CONFIG declares market='$_MARKET' — expected futures or stock" ;;
esac
[ "$TREE_MARKET" = "$_MARKET" ] ||
  die "TENANT_TREE='$TENANT_TREE' is a '$TREE_MARKET' tree (RENDER.yaml market) but TENANT_PRODUCER_CONFIG reads market='$_MARKET' — refused before the producer starts"

# Transport and instrument follow the market. The stock tenant tree is the MOCK
# order tree (PR-3a, operator decision 2026-10-23): its active scope is
# MOCK_STOCK_ORDER, which the runtime refuses to compose with anything but
# `--transport kis-mock`. The futures tenant trees stay SYNTHETIC. Each market
# refuses the other market's settings rather than ignoring them — an ignored
# setting is one the operator believes is in effect and is not.
#
#   futures — instrument DERIVED (step 6, the mini front month); synthetic.
#   stock   — instrument NAMED by TENANT_INSTRUMENT, matching the tree's own
#             instrument.pattern; kis-mock, with the deploy-time
#             kis_mock_transport.yaml TENANT_KIS_MOCK_TRANSPORT_CONFIG names
#             installed into the render output after the render (step 10).
#             Its credentials come from custody (kis_mock.app_key/app_secret
#             under TENANT_CUSTODY_ROOT), never from this environment.
case "$_MARKET" in
futures)
  TRANSPORT=synthetic
  for _stock_only in TENANT_INSTRUMENT TENANT_KIS_MOCK_TRANSPORT_CONFIG; do
    [ -z "${!_stock_only+x}" ] ||
      die "$_stock_only is set for a futures session — the futures instrument is derived (step 6) and a futures tenant sends nothing, so nothing would read it"
  done
  ;;
stock)
  TRANSPORT=kis-mock
  require_env TENANT_INSTRUMENT TENANT_KIS_MOCK_TRANSPORT_CONFIG
  [ "$INSTRUMENT_MATCH" = match ] ||
    die "TENANT_INSTRUMENT='$TENANT_INSTRUMENT' does not fully match $TENANT_TREE/RENDER.yaml instrument.pattern ($INSTRUMENT_MATCH) — this tree is single-symbol; a new symbol is a new tree generation"
  [ -f "$TENANT_KIS_MOCK_TRANSPORT_CONFIG" ] ||
    die "TENANT_KIS_MOCK_TRANSPORT_CONFIG names no file: $TENANT_KIS_MOCK_TRANSPORT_CONFIG"
  ;;
esac
log "market=$_MARKET (tree and producer agree) · transport=$TRANSPORT"

# --- 5c. today's open delay (#924) ----------------------------------------
#
# The first-row hang ceiling (step 8b) counts from the REGULAR open. On a day the calendar's
# session_overrides moves the open later (#924), the producer cannot publish
# before that later open, so the ceiling moves by exactly that delay — read from
# the producer config's own calendar (tools/tos_cp3/session_day.py), never typed
# here. A regular day adds 0. Read HERE, before the producer starts, so a
# failed read refuses the session instead of killing a running one.
OPEN_DELAY_S=$(PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$REPO" "$PY" -P -m tools.tos_cp3.session_day \
  open-delay --producer-config "$TENANT_PRODUCER_CONFIG" --repo-root "$REPO" \
  --date "$(TZ=Asia/Seoul date +%F)" 2>&1) ||
  die "cannot read today's open delay from $TENANT_PRODUCER_CONFIG: $OPEN_DELAY_S"
case "$OPEN_DELAY_S" in
'' | *[!0-9]*) die "open delay '$OPEN_DELAY_S' is not a whole number of seconds" ;;
esac
[ "$OPEN_DELAY_S" -gt 0 ] && log "dated session override: open is ${OPEN_DELAY_S}s later than the regular open — first-row bound grows by that much"

# --- 6. the contract month — computed ONCE, given to all three -------------
#
# Runbook §7.3 5-a / operator decision 2026-10-04: the durable set is one per
# contract month, the leaf is that code, and the render gets the SAME value —
# and since PR-3 so does the producer (plan §3.5: "instrument 은 인자로만 받는다").
# Two places computing it separately disagree on a roll day and nobody finds out.
if [ "$_MARKET" = stock ]; then
  # Named, not derived (step 3c): a stock symbol does not roll.
  INSTRUMENT=$TENANT_INSTRUMENT
else
  INSTRUMENT=$(PYTHONPATH="$REPO" "$PY" -c \
    'from shared.instruments.futures import get_front_month_code; print(get_front_month_code(product="mini"))' 2>&1) ||
    die "front-month lookup failed in $REPO: $INSTRUMENT"
  case "$INSTRUMENT" in
  A0[0-9][0-9][0-9][0-9]) : ;;
  *) die "instrument '$INSTRUMENT' does not look like a mini front-month code (^A0[0-9]{4}\$)" ;;
  esac
fi
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
BAND_PID=""

# The stop MARKER (#967): set only when this script's own stop path is about to
# signal a live `run` group. Step 12 reads it to tell "ended by our SIGTERM"
# from "ended by itself / by somebody else" — the exit code alone cannot,
# because coreutils >= 9.10 `timeout` propagates the TERM it receives and
# reports 124, the same code as its own alarm firing.
RUN_STOP_SENT=0

stop_run() {
  if [ -n "$RUN_PID" ] && supervised_group_alive "$RUN_PID"; then
    RUN_STOP_SENT=1
  fi
  stop_supervised "$RUN_PID" "$SIGKILL_AFTER_S" run
}

stop_producer() {
  stop_supervised "$PRODUCER_PID" "$PRODUCER_SIGKILL_AFTER_S" producer
}

# Whichever waiter is running — the first-row one (step 8b) or the band-line
# one (step 8c). They never overlap: 8c starts after 8b has returned and
# cleared the pid, so ONE handle covers both and there is no second stop path
# to keep in step with this one. Neither is under `timeout` — each has its own
# deadline — so `stop_supervised`'s group signal finds no group of its own and
# falls back to the pid, which is the right target. Five seconds is ample: both
# sleep in one-second steps and hold nothing open.
stop_wait() {
  stop_supervised "$WAIT_PID" 5 "row/band wait"
}

# The band process (step 8c). Its own `timeout` already bounds it, so this is
# the signal path only: a TERM to the runner must not leave a band process
# holding a REAL quotation connection. Five seconds, the same grace its own
# supervisor allows.
stop_band() {
  stop_supervised "$BAND_PID" "$BAND_PROCESS_KILL_AFTER_S" "band process"
}

# The runtime first, the producer second: the producer is the one writing the
# journal the runtime reads, and stopping it first would make the runtime's
# last passes look like a feed that went silent. The waiter last — it is the
# one that may still be sleeping when a signal arrives.
on_exit() {
  stop_run
  stop_producer
  stop_band
  stop_wait
}

# 128+signo, the conventional shell exit code, so a caller can tell an
# interrupted session from a clean one.
on_signal() {
  log "=== SIGNAL $1 received by the runner — forwarding to the children"
  stop_run
  stop_producer
  stop_band
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

# OPEN_DELAY_S is read in step 5c, before anything is launched (#963 review LOW-1).
first_row_wait "$((FIRST_LINE_TIMEOUT_S + OPEN_DELAY_S))" "first-row wait"

# --- 8c. the BAND process, then the BAND line (band plan v3) ---------------
#
# The band's source is a separate short-lived process: one REAL GET-only read
# of `FHMIF10000000`, written as one line into `band.jsonl`. The runtime holds
# no credential and opens no socket, so if that line is not there before the
# boot this session has no band at all — the kernel folds that to UNKNOWN and
# sends nothing.
#
# ⚠ **Credential separation is unchanged** (③ plan §3.4). The band process
# reads the two real futures QUERY keys ITSELF, from the `env_file` its own
# config names — exactly as the producer does. This template still never reads,
# passes or prints them, and step 3b still refuses to start if they are in this
# shell.
#
# ⚠ **Not before `open + one boundary`.** The band GET belongs at the first
# boundary after the open (§3.1): earlier is when the broker is most likely to
# hand out yesterday's band, and the runtime uses this line all day.
#
# Why the wait is HERE rather than inherited from step 8b: 8b's predicate is
# "an approved producer row exists", which says nothing about the open. What
# would keep it after the open is the producer's own publication floor
# (`first_boundary = max(open + 60s, now)` in producer.py) — a property of a
# DIFFERENT program, and the band's one chance at a correct read is not
# something to hang on a line in another file that no test here pins. So this
# template computes the launch time itself, from the producer config's
# calendar. Capped by STOP_S: never past the window the operator set.
#
# Exit codes are the whole interface to that program:
#   0 -> a line was written
#   2 -> a refusal before any GET: existing journal, pre-open, config or
#        credential refusal (every `LiveProducerRefused`)
#   3 -> a soft failure: the GET ran, no usable line
#   1 -> the allowlist gate refused, or an unexpected exception — including a
#        failed CALENDAR read, which cannot be a "refusal" here because the
#        launch-time computation below already read that same calendar
#        successfully. A DEFECT in this repo, so it is a hard ABORT before the
#        runtime boots.
BAND_JOURNAL=$TENANT_PRODUCER_SESSION_DIR/band.jsonl
BAND_WAIT_LOG=$TENANT_PRODUCER_SESSION_DIR/band-line-wait.log
BAND_PRESENT=0
BAND_PROCESS_RUNS=0

# Sleep until `open + one boundary`, capped by the session stop. The open comes
# from the producer config's own calendar — this template reads no calendar of
# its own (③ plan §3.5).
band_sleep_until_first_boundary() {
  _until=$("$PY" - "$TENANT_PRODUCER_CONFIG" "$REPO" "$STOP_S" <<'PY'
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tools.tos_cp3.live_producer.band_line import session_open_ms

config, repo, stop_s = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
day = datetime.now(ZoneInfo("Asia/Seoul")).date()
open_ms, _trading_date = session_open_ms(config, repo_root=repo, day=day)
# One minute-bar boundary past the open: the first instant the band GET is
# allowed to happen at all.
target_s = open_ms / 1000.0 + 60.0
now_s = time.time()
wait_s = max(0.0, target_s - now_s)
remaining_s = max(0.0, stop_s - now_s)
print(f"{min(wait_s, remaining_s):.0f}")
PY
  ) || die "cannot compute the band launch time from $TENANT_PRODUCER_CONFIG"
  log "band launch: computed ${_until}s until open + one boundary"
  if [ -n "$BAND_LAUNCH_MAX_WAIT_S" ] && [ "$_until" -gt "$BAND_LAUNCH_MAX_WAIT_S" ]; then
    log "band launch: capped to ${BAND_LAUNCH_MAX_WAIT_S}s (CP3_BAND_LAUNCH_MAX_WAIT_S)"
    _until=$BAND_LAUNCH_MAX_WAIT_S
  fi
  if [ "$_until" -gt 0 ]; then
    sleep "$_until" &
    WAIT_PID=$!
    wait "$WAIT_PID" || true
    WAIT_PID=""
  fi
}

# Seconds left before the session stop, floored at 0. The stop is the whole
# session's authority: nothing this template starts may outlive it, least of
# all a process holding REAL quotation credentials.
band_seconds_left() {
  _left=$((STOP_S - $(date +%s)))
  [ "$_left" -gt 0 ] || _left=0
  printf '%s' "$_left"
}

# One band process, in its OWN process group under `timeout`. Returns its rc,
# or BAND_RC_NO_TIME when the session stop leaves no room to run it at all.
#
# ⚠ **The stop is checked HERE, per attempt** (review round 6, Codex MEDIUM).
# Capping the open-anchored sleep was not enough: the sleep returns when the
# stop arrives, and the attempt then ran anyway — Codex reproduced a band
# process starting with `STOP_S=0`, i.e. a real-key OAuth + GET after the
# session had ended. A failure also queued a 60 s wait and a retry, both past
# the stop. So every attempt asks for the remaining time first, and both the
# ceiling and the retry wait are capped by it.
band_process_run() {
  # ⛔ The budget is computed HERE, as late as this script can compute it, and
  # conservatively (review round 7, Codex MEDIUM). Two reasons it cannot be
  # the number from a moment ago:
  #   * `date +%s` is whole seconds, so a reading of N can be anywhere in
  #     [N, N+1) — hence the `- 1`;
  #   * `timeout` counts from the SPAWN, not from the check, so every
  #     statement in between is budget that was already spent. Codex measured
  #     a TERM-resistant child outliving STOP_S by 0.68s, and a 6.1s logging
  #     stall putting the launch 0.78s PAST it.
  # `BAND_STOP_MARGIN_S` covers both, and the only statements between this
  # computation and the spawn are the two `log` calls below.
  #
  # ⚠ Residual, stated plainly: a host stall longer than the margin between
  # that last log line and the spawn cannot be ruled out from a shell script.
  # Bounding THAT needs the supervisor to own the deadline (a `timeout`
  # computed by the thing that also holds the clock), which is a bigger change
  # than this one and not what the operator asked for.
  _remaining=$((STOP_S - $(date +%s) - 1 - BAND_STOP_MARGIN_S))
  # The SIGKILL grace is wall time this attempt can consume, so it has to fit
  # inside the window too — a ceiling of 1s with a 5s grace is a 6s attempt.
  if [ "$_remaining" -le "$BAND_PROCESS_KILL_AFTER_S" ]; then
    log "band: $((STOP_S - $(date +%s)))s left before the session stop — NO attempt started (needs more than the ${BAND_PROCESS_KILL_AFTER_S}s kill grace plus the ${BAND_STOP_MARGIN_S}s margin)"
    return "$BAND_RC_NO_TIME"
  fi
  _ceiling=$BAND_PROCESS_TIMEOUT_S
  _budget=$((_remaining - BAND_PROCESS_KILL_AFTER_S))
  if [ "$_ceiling" -gt "$_budget" ]; then
    log "band: ceiling ${_ceiling}s capped to ${_budget}s by the session stop (${_remaining}s usable after the ${BAND_STOP_MARGIN_S}s margin)"
    _ceiling=$_budget
  fi
  BAND_PROCESS_RUNS=$((BAND_PROCESS_RUNS + 1))
  log "=== BAND PROCESS #$BAND_PROCESS_RUNS instrument=$INSTRUMENT ceiling ${_ceiling}s grace ${BAND_PROCESS_KILL_AFTER_S}s margin ${BAND_STOP_MARGIN_S}s stop_in $((STOP_S - $(date +%s)))s"
  PYTHONPATH="$REPO" \
    setsid timeout --kill-after="${BAND_PROCESS_KILL_AFTER_S}s" \
    "${_ceiling}s" \
    "$PY" -m tools.tos_cp3.live_producer.band_probe \
    --config "$TENANT_PRODUCER_CONFIG" \
    --instrument "$INSTRUMENT" \
    --session-dir "$TENANT_PRODUCER_SESSION_DIR" \
    --confirm >>"$TENANT_LOG" 2>&1 &
  BAND_PID=$!
  wait "$BAND_PID"
  _band_rc=$?
  BAND_PID=""
  log "band process #$BAND_PROCESS_RUNS rc=$_band_rc"
  return "$_band_rc"
}

band_sleep_until_first_boundary
if band_process_run; then
  log "band process wrote a line"
else
  _rc=$?
  if [ "$_rc" -eq 1 ]; then
    # A gate refusal or an unexpected exception: a defect here, not a slow
    # broker. ABORT before the runtime boots — the opposite disposition to
    # BAND ABSENT, and the reason the probe keeps those codes apart.
    die "band process exited rc 1 (allowlist gate refusal or unexpected error) — see $TENANT_LOG"
  fi
  if [ "$_rc" -eq "$BAND_RC_NO_TIME" ]; then
    # The stop arrived before anything could be attempted. Not an abort: band
    # absence is the conservative direction, and a session whose window has
    # closed has nothing left to do here.
    log "band: the session stop left no room for a first attempt — band is ABSENT for this session"
  else
    # Exactly ONE retry, at the next boundary. One bad minute (a 429 burst, one
    # expired token) must not cost the day's band; an unbounded retry would hand
    # the band the minute-bar polling's rate-limit budget.
    _wait=$BAND_RETRY_BOUNDARY_S
    _left=$(band_seconds_left)
    if [ "$_wait" -gt "$_left" ]; then
      log "band retry: wait ${_wait}s capped to ${_left}s by the session stop"
      _wait=$_left
    fi
    log "band process rc=$_rc — one retry at the next boundary (in ${_wait}s)"
    if [ "$_wait" -gt 0 ]; then
      sleep "$_wait" &
      WAIT_PID=$!
      wait "$WAIT_PID" || true
      WAIT_PID=""
    fi
    if band_process_run; then
      log "band process wrote a line on the retry"
    else
      _rc=$?
      if [ "$_rc" -eq 1 ]; then
        die "band process exited rc 1 on the retry (gate refusal) — see $TENANT_LOG"
      fi
      if [ "$_rc" -eq "$BAND_RC_NO_TIME" ]; then
        log "band: the session stop left no room for the retry — band is ABSENT for this session"
      else
        log "band process rc=$_rc on the retry — no further attempts"
      fi
    fi
  fi
fi

# ⚠ **A LINE, not the file** (v2 re-review LOW). Checking existence alone lets
# a stale file pass the instant the probe's own `refuse_if_journal_exists`
# regresses, which is the regression this check exists to survive. The
# predicate is the one the acceptance criterion states: `trading_date` is
# today, `instrument` is this session's contract, and `as_of_ms` is at or after
# the open. It lives in tools/tos_cp3/live_producer/band_line.py, so the writer
# and this check cannot disagree about it, and the session OPEN comes from the
# producer config's own calendar — not from a literal here.
#
# ⚠ **Absence does NOT abort** (§3.1). The session continues and says so
# loudly: price collection and the B3 cross-check are still worth having, and
# band absence is the conservative direction. That session is recorded as a
# FAILURE of band plan §4 acceptance 1 — by this log line, which is the
# evidence for it.
#
# In the background with `wait`, for the same reason as 8b: bash runs a trap
# only BETWEEN commands, so a foreground `$(…)` would defer a TERM.
band_line_wait() {
  "$PY" - "$BAND_JOURNAL" "$TENANT_PRODUCER_CONFIG" "$INSTRUMENT" \
    "$BAND_LINE_EXTRA_WAIT_S" "$REPO" "$STOP_S" \
    >"$BAND_WAIT_LOG" 2>&1 <<'PY' &
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tools.tos_cp3.live_producer.band_line import (
    read_last_band_line,
    reject_reason,
    session_open_ms,
)

band, config, instrument, allowance_s, repo, stop_s = (
    Path(sys.argv[1]),
    Path(sys.argv[2]),
    sys.argv[3],
    float(sys.argv[4]),
    Path(sys.argv[5]),
    int(sys.argv[6]),
)

# TODAY in KST, and the open from the producer's own settings — the runner
# reads no calendar of its own (plan §3.5).
day = datetime.now(ZoneInfo("Asia/Seoul")).date()
open_ms, trading_date = session_open_ms(config, repo_root=repo, day=day)
now_s = time.time()
remaining_s = max(0.0, stop_s - now_s)
wait_s = min(allowance_s, remaining_s)
print(
    f"band wait: allowance={allowance_s:.0f}s (the band processes have already "
    f"had their turns) -> waiting up to {wait_s:.0f}s "
    f"(stop leaves {remaining_s:.0f}s)"
)
deadline = time.monotonic() + wait_s
why = "no band line has been written"
while True:
    line = read_last_band_line(band)
    if line is not None:
        reason = reject_reason(
            line, instrument=instrument, trading_date=trading_date, open_ms=open_ms
        )
        if reason is None:
            print(
                f"band line ok · trading_date={trading_date} "
                f"instrument={instrument} as_of_ms={line['as_of_ms']} "
                f"(open {open_ms}) digest={line['raw_payload_digest']}"
            )
            break
        why = f"the last line is not usable: {reason}"
    if time.monotonic() >= deadline:
        raise SystemExit(f"no usable band line in {band} within {wait_s:.0f}s — {why}")
    time.sleep(1.0)
PY
  WAIT_PID=$!
  log "band-line wait: pid=$WAIT_PID (bound ${BAND_LINE_EXTRA_WAIT_S}s, log $BAND_WAIT_LOG)"
  if wait "$WAIT_PID"; then
    BAND_PRESENT=1
  fi
  WAIT_PID=""
  while IFS= read -r line; do log "  $line"; done <"$BAND_WAIT_LOG"
  if [ "$BAND_PRESENT" -eq 1 ]; then
    log "band line present before the boot (band plan §4 수용 1)"
  else
    log "⛔⛔ BAND ABSENT — 이 세션 전체 band UNKNOWN(송신 0)"
    log "⛔⛔ BAND ABSENT — band plan §4 수용 1 fails for this session; the"
    log "⛔⛔ BAND ABSENT — runtime boots anyway (price collection + B3 still"
    log "⛔⛔ BAND ABSENT — stand) and every venue decision is UNKNOWN."
  fi
}

band_line_wait

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

# The data parent's mode is READ, never written (Codex round 3, MEDIUM).
#
# This line used to be `chmod 700 "$TENANT_DATA_PARENT" 2>/dev/null || true`,
# inherited from main. It was the same defect step 12c was deleted for, one
# step earlier and louder: it runs AFTER step 6b, so a path swapped in between
# gets the mode written to whatever the name now points at — and `2>/dev/null
# || true` meant a failure to do so said NOTHING. It also made this script's
# own claim ("umask is the only mode mechanism here") false.
#
# A parent THIS run created is already 0700, from the `(umask 077; mkdir -p)`
# above. A parent that already existed is someone else's object, and the only
# safe thing to do with someone else's object is look at it: if the mode is
# not exactly 700 the session REFUSES and names the fix, rather than reaching
# in. Fail closed — an over-wide durable parent is a coordinate leak waiting
# to happen (runbook §7.2 좌표 규율), and the operator's one-time command is
# in runbook §7.2-d 「모드」:
#     chmod 700 ~/.local/state/tos/<the parent>
# ⚠ Exactly "700", not "at least as narrow as": `2700` (setgid) and `0700`
# with an ACL are not this mode, and a durable evidence parent carrying either
# is a finding, not a rounding.
PARENT_MODE=$(stat -c %a -- "$TENANT_DATA_PARENT") ||
  die "cannot read the mode of data parent $TENANT_DATA_PARENT"
[ "$PARENT_MODE" = "700" ] ||
  die "data parent $TENANT_DATA_PARENT is mode $PARENT_MODE, not 700. This runner never changes the mode of an object it did not create (step 12c records why) — narrow it to 700 yourself and re-run (runbook §7.2-d 「모드」)"
log "data parent mode $PARENT_MODE"

(umask 077; mkdir -p -- "$DATA_LEAF") ||
  die "cannot create data leaf $DATA_LEAF"

# --- 10. render ------------------------------------------------------------
#
# The tenant tree's RENDER.yaml declares direction.mode "declared" (so
# --direction is COMPARED with the tree's own value, never substituted) and
# journal.mode "external" (so --journal-path is required and the renderer writes
# no journal of its own) — plan §2.3 / §2.4.
#
# `--band-journal-path` (band plan PR-B, docs/plans/2026-10-15-tos-cp3-band-via-
# producer-plan.md §3.2) is REQUIRED by a tree whose venue policy declares
# `_runtime.band_source` and REFUSED by one that does not. The runner asks the
# MANIFEST which it is rather than carrying "LONG has a band" as a literal: the
# day the operator turns the SHORT tree on, that is a config edit and this line
# must not have to change with it. The path is the band probe's own output
# (step 8c), and it need not exist — a session where the probe never wrote is
# `BAND ABSENT`, which the runtime folds to UNKNOWN.
BAND_RENDER_ARGS=()
if grep -q 'value: "band_journal_path"' "$TREE_DIR/RENDER.yaml" 2>/dev/null; then
  BAND_RENDER_ARGS=(--band-journal-path "$BAND_JOURNAL")
  log "render: $TENANT_TREE declares a band_journal_path slot -> $BAND_JOURNAL"
else
  log "render: $TENANT_TREE declares no band source (band stays off for this tree)"
fi
log "=== RENDER tree=$TENANT_TREE direction=$TENANT_DIRECTION out=$TENANT_RENDER_OUT"
RENDER_LOG=$("$PY" scripts/tos/render_paper_config.py \
  --source "$TREE_DIR" \
  --out "$TENANT_RENDER_OUT" \
  --env-file "$TENANT_ENV_FILE" \
  --instrument "$INSTRUMENT" \
  --direction "$TENANT_DIRECTION" \
  "${BAND_RENDER_ARGS[@]}" \
  --journal-path "$TENANT_JOURNAL" 2>&1)
render_rc=$?
printf '%s\n' "$RENDER_LOG" >>"$TENANT_LOG"
[ "$render_rc" -eq 0 ] ||
  die "render refused (rc=$render_rc): $(printf '%s' "$RENDER_LOG" | tail -1 | cut -c1-200)"
log "render ok -> $TENANT_RENDER_OUT"
if [ "$TRANSPORT" = kis-mock ]; then
  # The deploy-time transport document (host seal, TR ids, price_scale) is not a
  # tree file, so the renderer never writes it; the runtime reads it from the
  # config dir. Copied, 0600, after the render so a re-render cannot drop it.
  install -m 0600 "$TENANT_KIS_MOCK_TRANSPORT_CONFIG" \
    "$TENANT_RENDER_OUT/kis_mock_transport.yaml" ||
    die "cannot install the kis-mock transport config into $TENANT_RENDER_OUT"
  log "kis-mock transport config installed -> $TENANT_RENDER_OUT/kis_mock_transport.yaml"
fi

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

# --- 11b. the runtime records its OWN exit status (#987) -------------------
#
# `timeout` is the only process that reaps the runtime, and what it REPORTS for
# the SIGTERM this runner's stop path sent depends on its coreutils version:
# 9.4 (ubuntu-24.04, this host) passes the child's code through, 9.10
# (ubuntu-26.04) answers 124 for any TERM it was asked to forward. #986 read
# that 124 through the stop marker and recorded it as 143 — right for a runtime
# that stopped cleanly, WRONG for one whose shutdown then failed. On 9.10 an
# rc-1 teardown and a clean stop were the same session day (#987's failing
# input: stop SIGTERM → the runtime ends rc 1 while closing its durable set →
# `timeout` 124 → marker set → recorded 143, a normal stop), while the same
# input on 9.4 shows up as the rc 1 it is.
#
# So the runtime's status stops being something `timeout` is asked about. One
# `bash` between the supervisor and the runtime records the code the runtime
# itself ended with, and step 12 reads that back: no version of `timeout` takes
# part in the answer. Everything `timeout` is here for is unchanged — it is
# still the supervising process with its own alarm, still the group leader the
# stop path signals, and the recorder adds no deadline of its own.
#
# ⚠ `trap ":"` is a CATCH, not an ignore, and the difference is the whole
# mechanism. A caught signal is reset to the DEFAULT disposition in children,
# so the runtime still dies of the stop TERM exactly as it did before; an
# ignore (`trap ""`) is INHERITED and would make the runtime deaf to the very
# stop this runner depends on. bash defers a trap until the foreground command
# it is waiting on has finished, so the recorder is still there to see the
# runtime's own code, and `$?` survives the deferred trap.
#
# The record carries a TOKEN for this boot and step 12 accepts no other. This
# template deletes nothing (`test_runner_template_never_removes_itself`), so a
# record left by an earlier run against the same TENANT_LOG has to be
# unreadable rather than plausible: reporting an earlier session's exit code as
# this one's would be the same class of defect as #987 itself — evidence that
# is wrong rather than missing.
RUN_RC_FILE=$TENANT_LOG.run-rc
RUN_RC_TOKEN="$$/$(TZ=Asia/Seoul date +%s)"
RECORD_CHILD_RC='trap ":" TERM INT HUP
token=$1
rc_file=$2
shift 2
"$@"
rc=$?
printf "%s %s\n" "$token" "$rc" >"$rc_file"
exit "$rc"'

log "=== BOOT label=$TENANT_ENVIRONMENT_LABEL custody=$TENANT_CUSTODY_ROOT stop in ${RUN_S}s ($TENANT_STOP_AT) · child ceiling ${CHILD_CEILING_S}s"
PYTHONPATH="$REPO/tos/src:$REPO/tos/runtime/src" \
  timeout --kill-after="${SIGKILL_AFTER_S}s" "${CHILD_CEILING_S}s" \
  "$BASH" -c "$RECORD_CHILD_RC" cp3-run-rc "$RUN_RC_TOKEN" "$RUN_RC_FILE" \
  "$PY" -c "$CLI" run \
  --config-dir "$TENANT_RENDER_OUT" \
  --data-dir "$DATA_LEAF" \
  --custody-root "$TENANT_CUSTODY_ROOT" \
  --transport "$TRANSPORT" \
  --environment-label "$TENANT_ENVIRONMENT_LABEL" >>"$TENANT_LOG" 2>&1 &
RUN_PID=$!
log "run pid=$RUN_PID (supervised by timeout, ceiling ${CHILD_CEILING_S}s; own exit status -> $RUN_RC_FILE token $RUN_RC_TOKEN)"

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
# #987: `timeout` is not asked what the runtime's status was — step 11b's
# recorder wrote it and this reads it back, so the code recorded here is the
# same on 9.4 and on 9.10. #967's shapes, now all one rule:
#
#   stop marker + a record for THIS boot -> the runtime's own code, whatever
#     `timeout` said. 143 (the TERM, the ordinary end of a full session), 0, or
#     a FAILURE while stopping — which on 9.10 was indistinguishable from 143
#     before this and is the whole of #987.
#   stop marker, NO record -> the runtime never got to write one, i.e. it was
#     SIGKILLed (the `--kill-after` grace ran out, or `stop_supervised`
#     escalated). That is not an ordinary stop and is not recorded as one:
#     whatever `timeout` reported stands.
#   NO stop marker -> nothing is read. A 124 here is `timeout`'s own alarm, a
#     runtime that outlived its ceiling, and the record would hold the 143 that
#     alarm's TERM caused — reading it would turn that failure into a clean
#     stop.
RUN_CHILD_RC=""
if [ "$RUN_STOP_SENT" = 1 ] && [ -f "$RUN_RC_FILE" ]; then
  RUN_RC_RECORD=""
  read -r RUN_RC_RECORD <"$RUN_RC_FILE" 2>/dev/null
  case $RUN_RC_RECORD in
  "$RUN_RC_TOKEN "*) RUN_RC_DIGITS=${RUN_RC_RECORD#"$RUN_RC_TOKEN "} ;;
  *) RUN_RC_DIGITS="" ;;
  esac
  case $RUN_RC_DIGITS in
  '' | *[!0-9]*)
    log "WARN: $RUN_RC_FILE holds no exit status for this boot (token $RUN_RC_TOKEN, first line '$RUN_RC_RECORD') — falling back to what timeout reported"
    ;;
  *) RUN_CHILD_RC=$RUN_RC_DIGITS ;;
  esac
fi
if [ -n "$RUN_CHILD_RC" ]; then
  [ "$RUN_CHILD_RC" = "$run_rc" ] ||
    log "run: timeout reported rc=$run_rc for the SIGTERM this runner's stop path sent, but the runtime itself ended rc=$RUN_CHILD_RC ($RUN_RC_FILE) — recording the runtime's own"
  run_rc=$RUN_CHILD_RC
elif [ "$RUN_STOP_SENT" = 1 ] && [ "$run_rc" -eq 124 ]; then
  log "WARN: timeout reported rc=124 for the SIGTERM this runner's stop path sent and the runtime recorded no exit status of its own — it was killed before it could, so this session is NOT recorded as an ordinary stop"
fi
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
# So the only mechanism that WRITES a mode has no window at all: step -0.5's
# process-wide `umask 077` means everything this session CREATES is born 0600
# inside 0700 — the stores, the journal, the render output, the session log,
# the producer's artifacts. There is nothing left to repair for a session that
# starts here.
#
# ⚠ The same reasoning deleted a second, older `chmod` (Codex round 3): step 9
# used to `chmod 700` the data PARENT, inherited from main and silenced with
# `2>/dev/null || true`. An existing parent is now READ and the session
# refuses a mode that is not 700, which is the same answer in the one place
# this script still had to say something about an object it did not create.
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

# --- 14. the §3.6 B3 reconciliation ---------------------------------------
#
# Roadmap §2-1 ("장후 B3 대조에서 unresolved = 0") is measured off
# `<session>/b3/report/summary.json`, and until this step existed no session
# had ever written one: B3 was six commands an operator ran by hand (runbook
# history §7.2-d), so `sts tos status` printed "B3 대조: 결과 없음" every day.
#
# HERE, and not in a later job, for one reason: B1b can only load the strategy
# this session RENDERED ($TENANT_RENDER_OUT). Both committed copies refuse this
# journal — the harness copy pins backtest coordinates, the tenant copy leaves
# them "TBD" — so the comparison has to run while the session directory is
# still around.
#
# ⛔ **It cannot change this session's verdict.** The rc is logged and
# discarded: the session's exit code is about the runtime and the producer
# (step 12b), and a reconciliation that could not run says nothing about
# either. The record of what happened is `<session>/b3/status.json`, which the
# tool writes BEFORE its first step and replaces atomically at the end — so a
# missing input, a refusing step, the budget, or a SIGKILL all leave something
# that says so, and never a summary claiming unresolved=0.
# Where the record goes: the session directory, which in the CRON layout is the
# producer dir one level up. Derived rather than asked for, because every
# TENANT_* value is an instance value with no default and adding a required one
# would mean reinstalling the host cron wrapper that sets them
# (~/.config/kis-probes, sha256-pinned).
#
# ⚠ The derivation holds only for that layout, so it is checked (review-1000
# L1). A producer dir whose basename is not `producer` belongs to some other
# session shape — a one-off boot proof — and `dirname` would then drop `b3/`
# into whatever its parent happens to be, which is evidence landing somewhere
# the operator did not choose. That is the same rule step 6b applies to the
# four session paths; here it SKIPS rather than refuses, because nothing about
# B3 may end a session. CP3_B3_SESSION_DIR runs it anyway.
B3_SESSION_DIR=${CP3_B3_SESSION_DIR:-}
if [ -z "$B3_SESSION_DIR" ]; then
  case "${TENANT_PRODUCER_SESSION_DIR%/}" in
  */producer) B3_SESSION_DIR=$(dirname "${TENANT_PRODUCER_SESSION_DIR%/}") ;;
  esac
fi
if [ -z "$B3_SESSION_DIR" ]; then
  log "=== B3 SKIPPED — TENANT_PRODUCER_SESSION_DIR '$TENANT_PRODUCER_SESSION_DIR' is not a '<session>/producer', so the session directory cannot be derived; set CP3_B3_SESSION_DIR to run the reconciliation anyway"
else
  # The outer ceiling is a stop for a WEDGED interpreter, not the budget: the
  # budget is config/tos_cp3_b3.yaml::total_timeout_s, which the tool applies to
  # each step as the time it has left. It matters because an unbounded step
  # would hold the cron wrapper's flock past midnight and refuse TOMORROW's
  # session ("lock busy") — a bigger loss than a missing comparison.
  # `test_the_b3_budget_stays_under_the_runners_ceiling` pins the ordering.
  log "=== B3 session-dir=$B3_SESSION_DIR instrument=$INSTRUMENT market=$_MARKET ceiling ${B3_CEILING_S}s"
  timeout --kill-after=5s "${B3_CEILING_S}s" \
    "$PY" "$REPO/tools/tos_cp3/post_session_b3.py" \
    --session-dir "$B3_SESSION_DIR" \
    --data-leaf "$DATA_LEAF" \
    --producer-session-dir "$TENANT_PRODUCER_SESSION_DIR" \
    --render-out "$TENANT_RENDER_OUT" \
    --instrument "$INSTRUMENT" \
    --session-day "$(TZ=Asia/Seoul date +%F)" \
    --market "$_MARKET" \
    --python "$PY" >>"$TENANT_LOG" 2>&1
  b3_rc=$?
  # The record's own path is printed by the tool (it knows the configured
  # subdir); this line is the rc, and the rc stops here.
  log "=== END B3 rc=$b3_rc (its record is under $B3_SESSION_DIR · this rc does NOT change the session's)"
fi

# Exit code 5: the runtime finished the way it was asked to, and the producer
# HALTED IN the session (step 12b) rather than ending with it.
#
# "The way it was asked to" is 0 OR 143: a session that reaches TENANT_STOP_AT
# is stopped by SIGTERM from this script's own stop path, so 143 is the
# ORDINARY end of a full session, not a failure (step 12 already resolved
# `run_rc` to the code the RUNTIME ended with, whatever version of `timeout`
# supervised it, and only with RUN_STOP_SENT set). Those two are the codes a
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
