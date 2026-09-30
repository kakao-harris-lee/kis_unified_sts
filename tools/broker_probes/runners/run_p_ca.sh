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
#   3. every required PCA_* variable is set.
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

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P) || exit 2
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

# --- 2. the code this run depends on ---------------------------------------
#
# Each needle is a fix an earlier P-CA trial was lost to, so a checkout without
# it must not be used to produce evidence: `pacer.derive(` is the cross-phase
# pacing fix (2026-09-17, poll #1 went out back-to-back with the reference GET)
# and `_BAL_TRANSIENT` is the transient-retry policy (2026-09-30, four stops).
for _needle in 'pacer.derive(' '_BAL_TRANSIENT'; do
  grep -q -- "$_needle" "$REPO/tools/broker_probes/probes_ca.py" ||
    die "probes_ca.py in this checkout is missing '$_needle' — required fix not present" 4
done
log "required probes_ca.py fixes present"

# --- 3. instance values (no defaults) --------------------------------------

for _name in \
  PCA_LOG PCA_ENV_FILE PCA_KIS_ENV PCA_SYMBOL PCA_EVENT_CLASS PCA_PAYABLE \
  PCA_WINDOW_S PCA_POLL_MS PCA_PACE_S PCA_EXPECT_KEY_FP PCA_EXPECT_ACCOUNT_FP \
  PCA_TOKEN_CACHE PCA_EVIDENCE_DIR PCA_NOTE; do
  _value=$(printenv "$_name" || true)
  [ -n "$_value" ] ||
    die "required env $_name is unset — this template ships no instance defaults"
done

case "$PCA_KIS_ENV" in
  mock | real) ;;
  *) die "PCA_KIS_ENV must be 'mock' or 'real' (got '$PCA_KIS_ENV')" ;;
esac

PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || die "no python at $PY"
[ -r "$PCA_ENV_FILE" ] || die "credential file unreadable: $PCA_ENV_FILE"
[ -d "$PCA_EVIDENCE_DIR" ] || die "evidence dir missing: $PCA_EVIDENCE_DIR"

# --- 4. credentials, checked by fingerprint --------------------------------

set -a
# shellcheck disable=SC1090  # operator-supplied path, by design
. "$PCA_ENV_FILE"
set +a

mkdir -p "$PCA_TOKEN_CACHE" && chmod 700 "$PCA_TOKEN_CACHE"

KEY_FP=$(printf '%s' "${KIS_STOCK_APP_KEY:-}" | sha256sum | cut -c1-12)
log "stock app key fp=$KEY_FP (expect $PCA_EXPECT_KEY_FP)"
[ "$KEY_FP" = "$PCA_EXPECT_KEY_FP" ] ||
  die "app key fingerprint mismatch — $PCA_ENV_FILE is not the credential set this trial was planned against"

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

HELD_OUT=$("$PY" -m tools.broker_probes.probes_ca --check-holding \
  --env "$PCA_KIS_ENV" --symbol "$PCA_SYMBOL" \
  --token-cache-dir "$PCA_TOKEN_CACHE" --pace-s "$PCA_PACE_S" 2>&1)
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

# --- 6. the probe ----------------------------------------------------------
#
# argv is built as an ARRAY and expanded quoted: an ISO-8601 value with a
# SPACE separator ("2026-10-01 09:00:00+09:00") is accepted by the probe's own
# datetime.fromisoformat, and an unquoted scalar would split it into two argv
# words (independent review F6).
PROBE_ARGS=(
  --asset stock --env "$PCA_KIS_ENV" --symbol "$PCA_SYMBOL"
  --event-class "$PCA_EVENT_CLASS"
  --payable-time "$PCA_PAYABLE"
  --window-s "$PCA_WINDOW_S" --poll-ms "$PCA_POLL_MS" --pace-s "$PCA_PACE_S"
  --confirm --token-cache-dir "$PCA_TOKEN_CACHE"
  --note "$PCA_NOTE"
)
# PCA_EFFECTIVE is optional because it is meaningless for a cash dividend
# (N-19 §2.3: the 기준가 adjustment is not on the balance surface). It is
# REQUIRED for every other event class, whose observable leg is the quantity
# leg and pairs with --effective-time: without it such a run polls the cash
# leg only and silently observes the wrong thing.
if [ -n "${PCA_EFFECTIVE:-}" ]; then
  PROBE_ARGS+=(--effective-time "$PCA_EFFECTIVE")
elif [ "$PCA_EVENT_CLASS" != "cash_dividend" ]; then
  die "PCA_EVENT_CLASS=$PCA_EVENT_CLASS observes a QUANTITY leg, which pairs with --effective-time; set PCA_EFFECTIVE"
fi
[ "${PCA_REFERENCE_CHECK:-0}" = "1" ] && PROBE_ARGS+=(--reference-check)

# Record what the results dir already holds, so step 7 can tell this run's
# artifact from a leftover: `ls -t | head -1` on an empty run copies somebody
# else's trial into the evidence corpus.
ART_BEFORE=$(ls -t "$REPO"/tools/broker_probes/results/P-CA-*.json 2>/dev/null | head -1)

log "=== START P-CA $PCA_SYMBOL env=$PCA_KIS_ENV window=${PCA_WINDOW_S}s poll=${PCA_POLL_MS}ms pace=${PCA_PACE_S}s"
printf '\n' | "$PY" -m tools.broker_probes.run P-CA "${PROBE_ARGS[@]}" \
  >>"$PCA_LOG" 2>&1
rc=$?
log "=== END P-CA rc=$rc"

# --- 7. artifact + crontab (never self-deletion) ---------------------------

ART=$(ls -t "$REPO"/tools/broker_probes/results/P-CA-*.json 2>/dev/null | head -1)
if [ -z "$ART" ]; then
  log "WARN: no P-CA artifact under $REPO/tools/broker_probes/results/ — nothing copied"
elif [ "$ART" = "$ART_BEFORE" ]; then
  log "WARN: newest artifact ($(basename "$ART")) predates this run — NOT copied"
else
  cp "$ART" "$PCA_EVIDENCE_DIR"/ && log "artifact copied: $(basename "$ART") -> $PCA_EVIDENCE_DIR"
fi

if [ -n "${PCA_CRON_MARK:-}" ]; then
  if crontab -l 2>/dev/null | grep -Fq -- "$PCA_CRON_MARK"; then
    crontab -l 2>/dev/null | grep -Fv -- "$PCA_CRON_MARK" | crontab - &&
      log "crontab entry matching '$PCA_CRON_MARK' removed"
  else
    log "no crontab entry matched '$PCA_CRON_MARK'"
  fi
fi

exit $rc
