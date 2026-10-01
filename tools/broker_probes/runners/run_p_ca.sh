#!/usr/bin/env bash
# P-CA runner TEMPLATE — tracked on purpose, instance values from the environment.
#
# Why this file is in the repository (plan §2.2, docs/plans/
# 2026-09-30-probe-transient-error-policy-plan.md): the 2026-09-30 runner lived
# only in ~/.config/kis-probes/ and DELETED ITSELF after its first run, so
# attempts 3 and 4 went out through a hand-made copy and the review could not
# establish afterwards which script had actually run. The template is tracked;
# only the instance values (symbol, times, window, fingerprints, credential
# file) come from the environment, and they have NO defaults — an unset one is
# an ABORT, never a silent fallback to somebody else's trial.
#
# Guards, in order, BEFORE any credential file is sourced:
#   1. the checkout this script sits in is clean, DETACHED, and an ancestor of
#      origin/main (#793: a shared checkout lets a parallel lane move the
#      branch under a running probe, and repo_commit is then stamped with a
#      non-main commit). Override: PCA_ALLOW_SHARED_CHECKOUT=1, logged.
#   2. the checkout carries the fixes this probe depends on.
#   3. every required PCA_* variable is set (PCA_EFFECTIVE included, when the
#      event class needs it), and the credential file is present in this
#      worktree — copied from the primary checkout when it is not (§3b).
#   4. PCA_PYTHON runs, and the tools.broker_probes it loads is THIS
#      checkout's — the interpreter is the main checkout's .venv, so that is
#      not automatic, and every guard above is worthless without it.
# Then: credential fingerprints (key + account) must match what the operator
# expected, and the holding must be READ successfully and be non-zero — a
# FAILED balance query is reported as a failure, never as "not held" (the
# 09-30 10:58 attempt logged "held qty=0" for a query that had errored).
#
# This script never deletes itself. With PCA_CRON_MARK set it removes the one
# matching crontab line, and only after the probe has actually run.
#
# See tools/broker_probes/runners/README.md for an instantiation recipe.

set -u

log() {
  _line="$(TZ=Asia/Seoul date '+%F %T') $*"
  printf '%s\n' "$_line"
  if [ -n "${PCA_LOG:-}" ]; then
    printf '%s\n' "$_line" >>"$PCA_LOG"
  fi
  return 0
}

die() {
  log "ABORT: $1"
  exit "${2:-3}"
}

# --- 1. the checkout -------------------------------------------------------

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P) || exit 2
REPO=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null) ||
  die "$SCRIPT_DIR is not inside a git checkout"
cd "$REPO" || exit 2

if [ "${PCA_ALLOW_SHARED_CHECKOUT:-0}" = "1" ]; then
  log "WARN: PCA_ALLOW_SHARED_CHECKOUT=1 — clean/detached/ancestor guards SKIPPED" \
      "by operator override; repo_commit in the artifact may not be an" \
      "origin/main commit (#793)"
else
  DIRTY=$(git -C "$REPO" status --short)
  [ -z "$DIRTY" ] ||
    die "checkout $REPO is dirty; probes run from a clean detached worktree (#793). First line: $(printf '%s' "$DIRTY" | head -1)"

  BRANCH=$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null) ||
    die "cannot read HEAD in $REPO"
  [ "$BRANCH" = "HEAD" ] ||
    die "checkout $REPO is on branch '$BRANCH', not a detached worktree — a parallel lane can move it under a running probe (#793)"

  git -C "$REPO" rev-parse --verify --quiet origin/main >/dev/null ||
    die "origin/main is not present in $REPO — run 'git fetch origin' first"
  git -C "$REPO" merge-base --is-ancestor HEAD origin/main ||
    die "HEAD ($(git -C "$REPO" rev-parse --short HEAD)) is not an ancestor of origin/main — probe evidence must be produced by merged code (#793)"
fi
log "checkout ok: repo=$REPO repo_commit=$(git -C "$REPO" rev-parse HEAD)"

# --- 2. runner and probe must be the same generation -----------------------
#
# The probe's own POLICY_VERSION, checked against the one this template was
# written for. This replaces grepping probes_ca.py for 'pacer.derive(' and
# '_BAL_TRANSIENT': a substring test cannot tell a fix from a mention (this
# PR's plan quotes the literal), and it breaks on a rename — failing a
# scheduled trial with "required fix not present" while the fix is right
# there. Both files live in this checkout, so a mismatch means the runner was
# COPIED OUT of a different tree, which is exactly the 2026-09-30 mistake.
# The comparison happens in step 3, once PCA_PYTHON is known.
#
# '/2' (#830): this template drives a reference-only pre-check (step 5b) and
# parses the probe's REFERENCE_* anchored lines. A '/1' probe has neither, so
# the pay-date comparison would silently never happen.
EXPECT_POLICY_VERSION=p-ca-retry-policy/2

# --- 3. instance values (no defaults) --------------------------------------

for _name in \
  PCA_LOG PCA_PYTHON PCA_CREDENTIAL_FILE PCA_KIS_ENV PCA_SYMBOL PCA_EVENT_CLASS \
  PCA_PAYABLE PCA_WINDOW_S PCA_POLL_MS PCA_PACE_S PCA_EXPECT_KEY_FP \
  PCA_EXPECT_ACCOUNT_FP PCA_TOKEN_CACHE PCA_EVIDENCE_DIR PCA_NOTE; do
  _value=$(printenv "$_name" || true)
  [ -n "$_value" ] ||
    die "required env $_name is unset — this template ships no instance defaults"
done

case "$PCA_KIS_ENV" in
  mock | real) ;;
  *) die "PCA_KIS_ENV must be 'mock' or 'real' (got '$PCA_KIS_ENV')" ;;
esac

# Step 6 appends the probe's whole output to PCA_LOG. If that directory does
# not exist the redirection fails, bash never runs the probe, and every log()
# call has already been silently dropping its line — the "attempt vanished"
# shape this runner exists to prevent (review F1). Make it real here, and fail
# loudly if it cannot be.
mkdir -p -- "$(dirname -- "$PCA_LOG")" ||
  die "cannot create the directory for PCA_LOG=$PCA_LOG"
touch -- "$PCA_LOG" || die "PCA_LOG is not writable: $PCA_LOG"

# Conditionally required, and checked HERE with the rest (review F3): every
# other class's observable leg is the QUANTITY leg, which pairs with
# --effective-time, so without it such a run polls the cash leg only and
# silently observes the wrong thing. It used to be checked at step 6, after
# the credentials were sourced and the holding walk had already been spent on
# the account — a pure configuration error costing broker calls.
if [ -z "${PCA_EFFECTIVE:-}" ] && [ "$PCA_EVENT_CLASS" != "cash_dividend" ]; then
  die "PCA_EVENT_CLASS=$PCA_EVENT_CLASS observes a QUANTITY leg, which pairs with --effective-time; set PCA_EFFECTIVE"
fi

# PCA_RECORD_DATE picks ONE row out of the reference table in step 5b (several
# quarters of the same issuer come back in one answer). It is interpolated into
# a sed pattern there, so its shape is checked here, with the rest, rather than
# trusted at the point of use. Unset means "the latest row".
case "${PCA_RECORD_DATE:-}" in
  "") ;;
  [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;;
  *) die "PCA_RECORD_DATE must be YYYYMMDD (got '${PCA_RECORD_DATE:-}')" ;;
esac

PY="$PCA_PYTHON"
[ -x "$PY" ] || die "PCA_PYTHON is not executable: $PY"

# The interpreter comes from somewhere else (the main checkout's .venv — a
# freshly added detached worktree has no .venv, and installing one into it is
# forbidden), so the code it LOADS has to be proven to be this checkout's.
# Without this the runner's clean/detached/ancestor guards would vouch for a
# tree that never ran: `repo_commit` and the results directory both follow
# `common.py.__file__` (common.py:70,506,512), not $REPO, so an interpreter
# resolving tools.broker_probes from the main checkout would stamp the wrong
# commit and write the artifact where this script does not look (review F1).
LOADED=$(PYTHONPATH="$REPO" "$PY" -c \
  "import tools.broker_probes.probes_ca as m; print(m.__file__); print(m.POLICY_VERSION)" 2>&1) ||
  die "cannot import tools.broker_probes from $REPO with $PY: $(printf '%s' "$LOADED" | tail -1 | cut -c1-160)"
MODULE_PATH=$(printf '%s\n' "$LOADED" | sed -n '1p')
MODULE_POLICY=$(printf '%s\n' "$LOADED" | sed -n '2p')
case "$MODULE_PATH" in
  "$REPO"/*) log "probe module resolves inside the checkout: $MODULE_PATH" ;;
  *) die "probe module resolves OUTSIDE the checkout ($MODULE_PATH) — the guards above would vouch for code that never ran" ;;
esac
[ "$MODULE_POLICY" = "$EXPECT_POLICY_VERSION" ] ||
  die "policy version mismatch: this runner was written for '$EXPECT_POLICY_VERSION', the checkout's probes_ca.py reports '$MODULE_POLICY' — runner and probe are from different trees" 4
log "probe policy version $MODULE_POLICY matches this runner"
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"

[ -d "$PCA_EVIDENCE_DIR" ] || die "evidence dir missing: $PCA_EVIDENCE_DIR"

# --- 3b. the credential file, copied into the worktree if it is not there ---
#
# Operator directive 2026-10-01: "워크트리에 .env가 없으면 기본 디렉토리에서
# 복사해". A RELATIVE PCA_CREDENTIAL_FILE (the documented case, e.g. .env.mock)
# is resolved against this worktree; a freshly added worktree carries none of
# the ignored env files, so it is copied from the PRIMARY checkout — the first
# entry of `git worktree list --porcelain`, never a hardcoded path, so this
# keeps working when the checkout moves. An ABSOLUTE path (e.g. the 09-15
# credential backup under ~/.config) is used exactly as given and never copied.
#
# The copy is mode 600 and the log line carries PATHS ONLY — never a byte of
# the file. It persists in the worktree; `.env.*` is gitignored, so it does not
# make the checkout dirty for the next run's guard.
case "$PCA_CREDENTIAL_FILE" in
  /*)
    CRED_FILE=$PCA_CREDENTIAL_FILE
    [ -r "$CRED_FILE" ] ||
      die "credential file unreadable: $CRED_FILE (absolute path, used as given)"
    ;;
  *)
    CRED_FILE="$REPO/$PCA_CREDENTIAL_FILE"
    # BEFORE anything is written. The repo ignores EXACT names (.env,
    # .env.mock, .env.real, .env.paper, .env.live, .env.production,
    # .env.local, .env.*.local) — not a `.env.*` glob, so `.env.mock.bak-…`,
    # the very name this README once suggested, is NOT ignored (review F2).
    # Copying a filled credential file onto an unignored path puts it where
    # `git add -A` would stage it: CLAUDE.md Non-Negotiable, "never commit
    # real credentials … or filled .env files". `git check-ignore` answers for
    # a path that does not exist yet, so the refusal costs nothing and nothing
    # is ever written to the wrong place.
    git -C "$REPO" check-ignore -q -- "$PCA_CREDENTIAL_FILE" ||
      die "relative credential file '$PCA_CREDENTIAL_FILE' is NOT gitignored in $REPO — refusing to place a filled credential file where 'git add -A' would stage it. Use an ignored name (.env.mock, .env.real, .env.paper, …) or give an absolute path outside the checkout"
    if [ ! -r "$CRED_FILE" ]; then
      PRIMARY=$(git -C "$REPO" worktree list --porcelain |
        awk '/^worktree /{print substr($0, 10); exit}')
      [ -n "$PRIMARY" ] ||
        die "cannot determine the primary checkout from 'git worktree list' in $REPO"
      CRED_SOURCE="$PRIMARY/$PCA_CREDENTIAL_FILE"
      [ -r "$CRED_SOURCE" ] ||
        die "credential file '$PCA_CREDENTIAL_FILE' is in neither checkout — not at $CRED_FILE and not at $CRED_SOURCE"
      install -m 600 "$CRED_SOURCE" "$CRED_FILE" ||
        die "could not copy the credential file: $CRED_SOURCE -> $CRED_FILE"
      log "credential file copied from the primary checkout: $CRED_SOURCE -> $CRED_FILE (mode 600)"
    fi
    ;;
esac

# --- 4. credentials, checked by fingerprint --------------------------------

set -a
# The path is operator-supplied by design, so it cannot be followed statically.
# shellcheck disable=SC1090
. "$CRED_FILE"
set +a

mkdir -p "$PCA_TOKEN_CACHE" && chmod 700 "$PCA_TOKEN_CACHE"

KEY_FP=$(printf '%s' "${KIS_STOCK_APP_KEY:-}" | sha256sum | cut -c1-12)
log "stock app key fp=$KEY_FP (expect $PCA_EXPECT_KEY_FP)"
[ "$KEY_FP" = "$PCA_EXPECT_KEY_FP" ] ||
  die "app key fingerprint mismatch — $CRED_FILE is not the credential set this trial was planned against"

ACCOUNT_FP=$("$PY" -c "
import os
from tools.broker_probes.common import account_fingerprint
print(account_fingerprint(os.environ['KIS_STOCK_ACCOUNT_NO']))") ||
  die "account fingerprint call failed"
log "stock account fingerprint=$ACCOUNT_FP (expect $PCA_EXPECT_ACCOUNT_FP)"
[ "$ACCOUNT_FP" = "$PCA_EXPECT_ACCOUNT_FP" ] ||
  die "account fingerprint mismatch"

# --- 5. the holding: a FAILED query is not "not held" ----------------------
#
# The 09-30 10:58 attempt logged "held qty=0" and stopped, when the balance
# query had in fact errored after 32 s — a direct GET two minutes later showed
# qty 1. The check therefore runs on the PROBE's own reader
# (`probes_ca.check_holding`, which pages and classifies) and not on
# `shared/kis/client.py::get_stock_balance`, which returns [] on every failure
# and reads page 1 only. It prints exactly one of two anchored lines.

# --retry-wait-ms is this trial's own polling interval: a ledger throttle
# (EGW00215) is answered by waiting a whole interval, not by asking again at
# the per-second cadence that just tripped it (review F6). No new constant.
HELD_OUT=$("$PY" -m tools.broker_probes.probes_ca --check-holding \
  --env "$PCA_KIS_ENV" --symbol "$PCA_SYMBOL" \
  --token-cache-dir "$PCA_TOKEN_CACHE" --pace-s "$PCA_PACE_S" \
  --retry-wait-ms "$PCA_POLL_MS" 2>&1)
held_rc=$?
HELD=$(printf '%s\n' "$HELD_OUT" | sed -n 's/^HELD=//p' | tail -1)
HELD_FAILED=$(printf '%s\n' "$HELD_OUT" | sed -n 's/^HOLDING_QUERY_FAILED=//p' | tail -1)

if [ -n "$HELD_FAILED" ]; then
  die "holding check FAILED (this is not a holding verdict): $HELD_FAILED"
fi
if [ -z "$HELD" ]; then
  die "holding check printed neither HELD= nor HOLDING_QUERY_FAILED= (rc=$held_rc): $(printf '%s' "$HELD_OUT" | tail -1 | cut -c1-160)"
fi
if [ "$held_rc" -ne 0 ]; then
  die "holding check exited $held_rc while reporting HELD=$HELD — refusing to trust the number"
fi
if [ "$HELD" = "0" ]; then
  log "held qty($PCA_SYMBOL)=0 (the walk completed; this is a real absence)"
  die "$PCA_SYMBOL is not held — nothing to observe"
fi
log "held qty($PCA_SYMBOL)=$HELD"

# Record what the results dir already holds, so each copy below can tell this
# run's artifact from a leftover: `ls -t | head -1` on a run that wrote nothing
# copies somebody else's trial into the evidence corpus. (shellcheck SC2012,
# info-level, is left standing: these names are generated by the harness as
# P-CA-<UTC timestamp>Z.json — no spaces, no newlines — and `find | sort` for a
# fixed pattern would be the more fragile of the two.)
# shellcheck disable=SC2012
ART_BEFORE=$(ls -t "$REPO"/tools/broker_probes/results/P-CA-*.json 2>/dev/null | head -1)

# $1: phase label for the log line, "" for the main probe (whose wording
#     predates this helper and is quoted verbatim in the campaign README).
# $2: destination directory, defaulting to PCA_EVIDENCE_DIR.
copy_new_artifact() {
  _phase=${1:+ ($1)}
  _dest=${2:-$PCA_EVIDENCE_DIR}
  # shellcheck disable=SC2012
  _art=$(ls -t "$REPO"/tools/broker_probes/results/P-CA-*.json 2>/dev/null | head -1)
  if [ -z "$_art" ]; then
    log "WARN: no P-CA artifact under $REPO/tools/broker_probes/results/ — nothing copied$_phase"
  elif [ "$_art" = "$ART_BEFORE" ]; then
    log "WARN: newest artifact ($(basename "$_art")) predates this run — NOT copied$_phase"
  elif mkdir -p "$_dest" && cp "$_art" "$_dest"/; then
    log "artifact copied: $(basename "$_art") -> $_dest$_phase"
    # Only once the copy SUCCEEDED. Advancing on failure told the next phase
    # this artifact was already secured, so a copy that never happened left no
    # trace at all — not even a WARN, because only the success branch was
    # chained (review #831 F10).
    ART_BEFORE=$_art
  else
    log "WARN: could NOT copy $(basename "$_art") to $_dest$_phase — this run's evidence is only in $REPO/tools/broker_probes/results/"
  fi
  return 0
}

# --- 5b. the broker's own pay date, BEFORE any window is spent -------------
#
# #830. `--reference-check` only RECORDED the ksdinfo row: nothing compared its
# `divi_pay_dt` with the t0 the trial polls against. A broker pay date one day
# off `PCA_PAYABLE` therefore cost a whole window — the probe polled against
# the wrong t0 for 16 h, wrote CENSORED, and the disagreement surfaced only
# afterwards, inside the artifact (campaign README, 2026-10-01 block). One
# extra ksdinfo GET here turns that into an ABORT before the window is spent.
#
# Cash dividends only: `divi_pay_dt` is the CASH leg's field. The other classes
# put their dates in different columns (`stk_div_pay_dt`, …) and pair with
# `--effective-time`, so comparing them against this one would be wrong.
REFERENCE_DONE=0
if [ "${PCA_REFERENCE_CHECK:-0}" = "1" ] && [ "$PCA_EVENT_CLASS" = "cash_dividend" ]; then
  # In KST, not in whatever offset the operator typed (review #831 F3). The
  # broker's divi_pay_dt is a KST calendar date, and the probe deliberately
  # ACCEPTS a non-KST offset on --payable-time (it only warns, finding F8), so
  # slicing the first ten characters off PCA_PAYABLE made
  # `2026-10-21T15:00:00Z` — the same instant as 2026-10-22 00:00 KST —
  # compare as 20261021 and abort the run. CLAUDE.md: convert to KST BEFORE
  # comparing. `date -d` also rejects an unparseable value, which the old
  # prefix match silently let through as empty.
  WANT_PAY=$(TZ=Asia/Seoul date -d "$PCA_PAYABLE" +%Y%m%d 2>/dev/null) ||
    die "PCA_PAYABLE='$PCA_PAYABLE' is not a date this shell can parse, so it cannot be compared with the broker's divi_pay_dt"
  [ -n "$WANT_PAY" ] || die "PCA_PAYABLE='$PCA_PAYABLE' produced no KST date"

  # The ksdinfo window filters on 기준일, which PRECEDES the pay date by an
  # issuer-specific gap. When the operator knows the record date, say so
  # instead of relying on the probe's lookback heuristic — one day of margin,
  # because an F_DT equal to the record date is a boundary and a boundary is
  # not a margin (review #831 F4).
  REF_WINDOW_ARGS=()
  if [ -n "${PCA_RECORD_DATE:-}" ]; then
    _ref_from=$(TZ=Asia/Seoul date -d "$PCA_RECORD_DATE -1 day" +%Y%m%d 2>/dev/null) ||
      die "PCA_RECORD_DATE='$PCA_RECORD_DATE' is not a date this shell can parse"
    REF_WINDOW_ARGS=(--reference-from "$_ref_from")
  fi

  # Same reason as the sleep before the probe: this is a third process with a
  # pacer of its own, and its GET would otherwise follow the holding check's
  # with no interval at all.
  sleep "$PCA_PACE_S"
  log "=== START P-CA reference-only $PCA_SYMBOL (one ksdinfo GET, no polling)"
  REF_OUT=$("$PY" -m tools.broker_probes.run P-CA \
    --asset stock --env "$PCA_KIS_ENV" --symbol "$PCA_SYMBOL" \
    --event-class "$PCA_EVENT_CLASS" --payable-time "$PCA_PAYABLE" \
    --reference-only --pace-s "$PCA_PACE_S" --confirm \
    "${REF_WINDOW_ARGS[@]+"${REF_WINDOW_ARGS[@]}"}" \
    --token-cache-dir "$PCA_TOKEN_CACHE" \
    --note "$PCA_NOTE | reference-only pay-date pre-check" 2>&1)
  ref_rc=$?
  printf '%s\n' "$REF_OUT" >>"$PCA_LOG"
  log "=== END P-CA reference-only rc=$ref_rc"
  REFERENCE_DONE=1
  # Into a subdirectory of its own: a lookup is not a trial, and the 10-22
  # re-arm guard globs `$PCA_EVIDENCE_DIR/P-CA-*.json` to decide whether the
  # event has already been observed. It also reads `args.reference_only`, but
  # a guard that depends on only one of the two is a guard with one way to be
  # wrong (review #831 F1).
  copy_new_artifact "reference-only" "$PCA_EVIDENCE_DIR/reference-only"

  # Exactly one REFERENCE_STATUS= line, on every path the probe can leave by.
  # Anything but a clean answer means the path to the broker is unhealthy
  # right now, and the next thing this script does is walk down it for 16
  # hours — which is the reason the probe stops on two transients in the first
  # place (review #831 F5). A MISSING line counts as unhealthy too: it is what
  # a crash out of the probe looks like from here.
  REF_STATUS=$(printf '%s\n' "$REF_OUT" | sed -n 's/^REFERENCE_STATUS=//p' | tail -1)
  case "${REF_STATUS%%:*}" in
    OK | NO_ROWS | UNSUPPORTED) ;;
    *)
      die "reference check did not complete (REFERENCE_STATUS=${REF_STATUS:-<none>}, probe rc=$ref_rc) — the broker path is unhealthy right now and the trial is a far longer walk down the same path. Not starting a ${PCA_WINDOW_S}s window"
      ;;
  esac

  # Candidate rows: every row the broker returned, narrowed to PCA_RECORD_DATE
  # when one was given. The question is "does ANY candidate confirm
  # PCA_PAYABLE", not "what does one chosen row say" (review #831 F2/F8): a
  # quarterly payer's answer carries several 기준일 — the window reaches 180
  # days past the pay date — so picking the latest row compared the NEXT
  # dividend's pay date and aborted on a row that was never the trial's. The
  # same answer can also carry two rows under one 기준일 (cash and stock), only
  # one of which has a divi_pay_dt.
  ROWS_ALL=$(printf '%s\n' "$REF_OUT" | sed -n 's/^REFERENCE_ROW=//p')
  if [ -n "${PCA_RECORD_DATE:-}" ]; then
    CANDIDATES=$(printf '%s\n' "$ROWS_ALL" | grep "^$PCA_RECORD_DATE|" || true)
    ROW_PICK="record_date=$PCA_RECORD_DATE"
  else
    CANDIDATES=$ROWS_ALL
    ROW_PICK="any returned row (PCA_RECORD_DATE unset)"
  fi
  # A pay field is eight digits or it is not a date. The probe prints digits
  # only, so anything else here is an empty column (the stock-dividend row) or
  # something this cannot read — either way it confirms nothing.
  PAY_DATES=$(printf '%s\n' "$CANDIDATES" | sed -n 's/^[0-9]*|\([0-9]\{8\}\)$/\1/p')
  MATCHED=$(printf '%s\n' "$PAY_DATES" | grep -cx "$WANT_PAY" || true)

  if [ "$MATCHED" -gt 0 ]; then
    log "pay date confirmed by the broker: divi_pay_dt=$WANT_PAY matches $MATCHED of $(printf '%s\n' "$PAY_DATES" | grep -c . || true) candidate row(s) ($ROW_PICK)"
  elif [ -z "$(printf '%s' "$PAY_DATES" | tr -d '[:space:]')" ]; then
    # Record-only, as before this change: a reference table that returns no
    # usable pay date is not evidence that PCA_PAYABLE is wrong, and the
    # trial's t0 is the operator's (DART for 058610, not ksdinfo).
    # PCA_REQUIRE_REFERENCE_ROW=1 is for an unattended slot that would rather
    # skip than measure against an unconfirmed date.
    _why="no candidate row carries a divi_pay_dt"
    [ -z "$(printf '%s' "$CANDIDATES" | tr -d '[:space:]')" ] && _why="no row matched"
    if [ "${PCA_REQUIRE_REFERENCE_ROW:-0}" = "1" ]; then
      die "reference check: $_why ($ROW_PICK, REFERENCE_STATUS=$REF_STATUS) and PCA_REQUIRE_REFERENCE_ROW=1"
    fi
    log "WARN: reference check: $_why ($ROW_PICK, REFERENCE_STATUS=$REF_STATUS) — PCA_PAYABLE=$WANT_PAY (KST) is NOT confirmed by the broker; continuing (record-only)"
  else
    _seen=$(printf '%s\n' "$PAY_DATES" | sort -u | tr '\n' ',' | sed 's/,$//')
    if [ "${PCA_ALLOW_PAYDATE_MISMATCH:-0}" = "1" ]; then
      log "WARN: pay-date MISMATCH allowed by PCA_ALLOW_PAYDATE_MISMATCH=1 — broker divi_pay_dt in {$_seen}, PCA_PAYABLE=$WANT_PAY (KST) ($ROW_PICK); the window will be polled against PCA_PAYABLE"
    else
      die "pay-date mismatch: the broker's candidate rows carry divi_pay_dt in {$_seen}, none equal to PCA_PAYABLE=$WANT_PAY (KST) ($ROW_PICK) — polling a window against the wrong t0 spends it for nothing. Fix PCA_PAYABLE, narrow with PCA_RECORD_DATE, or set PCA_ALLOW_PAYDATE_MISMATCH=1 to proceed anyway"
    fi
  fi
  REF_ROWS_NOTE=$(printf '%s\n' "$ROWS_ALL" | grep . | head -8 | tr '\n' ',' | sed 's/,$//')
fi

# The holding check and the probe are two processes with independent pacers,
# so the probe's baseline GET would otherwise follow the check's last GET with
# no gap at all — the back-to-back pair that produced the 2026-09-17 EGW00201
# stop, which this harness deliberately keeps as "stop, never retry" (review
# F2). One PCA_PACE_S here is the same interval the pacer would have owed; no
# new constant.
sleep "$PCA_PACE_S"

# --- 6. the probe ----------------------------------------------------------
#
# argv is built as an ARRAY and expanded quoted: an ISO-8601 value with a
# SPACE separator ("2026-10-01 09:00:00+09:00") is accepted by the probe's own
# datetime.fromisoformat, and an unquoted scalar would split it into two argv
# words (independent review F6).
#
# The note carries step 5b's rows when it ran, so the trial artifact still
# records what the reference table said without re-asking for it.
TRIAL_NOTE=$PCA_NOTE
[ -n "${REF_ROWS_NOTE:-}" ] &&
  TRIAL_NOTE="$PCA_NOTE | ksdinfo(5b) record|pay: $REF_ROWS_NOTE"
PROBE_ARGS=(
  --asset stock --env "$PCA_KIS_ENV" --symbol "$PCA_SYMBOL"
  --event-class "$PCA_EVENT_CLASS"
  --payable-time "$PCA_PAYABLE"
  --window-s "$PCA_WINDOW_S" --poll-ms "$PCA_POLL_MS" --pace-s "$PCA_PACE_S"
  --confirm --token-cache-dir "$PCA_TOKEN_CACHE"
  --note "$TRIAL_NOTE"
)
# Optional only for a cash dividend, where the 기준가 adjustment is not on
# the balance surface at all (N-19 §2.3). Every other class was required to
# supply it back in step 3.
[ -n "${PCA_EFFECTIVE:-}" ] && PROBE_ARGS+=(--effective-time "$PCA_EFFECTIVE")
# Only when step 5b did NOT run (a non-cash class, say). With 5b the identical
# GET — same TR, same symbol, same window — would go out twice per slot, and
# the second one is one more place a transient can stop the trial, this time
# AFTER the holding walk has been spent on the account (review #831 F6). The
# rows 5b got are in the trial note instead.
[ "${PCA_REFERENCE_CHECK:-0}" = "1" ] && [ "$REFERENCE_DONE" -eq 0 ] &&
  PROBE_ARGS+=(--reference-check)

log "=== START P-CA $PCA_SYMBOL env=$PCA_KIS_ENV window=${PCA_WINDOW_S}s poll=${PCA_POLL_MS}ms pace=${PCA_PACE_S}s"
# A brace GROUP, not a subshell, so the two assignments inside persist. If the
# redirection itself fails, bash runs NEITHER line and PROBE_LAUNCHED stays 0
# — which is how step 7 can tell "the probe ran and failed" from "the probe
# never started", and refuse to retire the cron entry in the second case
# (review F1).
PROBE_LAUNCHED=0
rc=0
{
  printf '\n' | "$PY" -m tools.broker_probes.run P-CA "${PROBE_ARGS[@]}"
  rc=$?
  PROBE_LAUNCHED=1
} >>"$PCA_LOG" 2>&1
[ "$PROBE_LAUNCHED" -eq 1 ] ||
  die "could not append to PCA_LOG ($PCA_LOG), so the probe was never started — the crontab entry is left in place"
log "=== END P-CA rc=$rc"

# --- 7. artifact + crontab (never self-deletion) ---------------------------

copy_new_artifact ""

# Only now, with PROBE_LAUNCHED proven above: an early ABORT leaves the
# schedule alone so the next slot can retry.
if [ -n "${PCA_CRON_MARK:-}" ]; then
  if crontab -l 2>/dev/null | grep -Fq -- "$PCA_CRON_MARK"; then
    crontab -l 2>/dev/null | grep -Fv -- "$PCA_CRON_MARK" | crontab - &&
      log "crontab entry matching '$PCA_CRON_MARK' removed"
  else
    log "no crontab entry matched '$PCA_CRON_MARK'"
  fi
fi

exit "$rc"
