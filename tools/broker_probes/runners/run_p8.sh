#!/usr/bin/env bash
# P-8 runner TEMPLATE — tracked on purpose, instance values from the environment.
#
# Why this file is in the repository: the 2026-09-28 P-8 cron runner lived only
# in ~/.config/kis-probes/ and is gone, so the only record of what it decided
# is the VERDICT line transcribed into the campaign README — and that line was
# wrong. It read
#
#   VERDICT: STOP: P-8 2/5 오류 1건(브로커 거부 포함) — 1/5 성공 후 중단(재시도 금지)
#
# when what had actually happened was a ConnectionError in the middle of the
# coexistence poll. The transport recovered within seconds (the cleanup cancel
# issued right afterwards returned rt_cd=0), but trials 3, 4 and 5 were
# cancelled, and `capabilities.replace_semantics.mode` still has no N>=5.
#
# So this runner counts the two separately and never adds them up:
#
#   * a BROKER REJECTION (P8_STOP=rejected) stops the series. Every trial would
#     be refused the same way — 2026-09-11 "모의투자 주문이 불가한 계좌입니다",
#     2026-09-16 "인증 시점의 계좌번호와 요청 계좌번호가 일치하지 않습니다".
#   * a RATE-LIMIT stop (P8_STOP=rate_limited) stops the series too. That one
#     is OUR call rate, and "stop, never retry" is an account-protection rule
#     (plan §3, unchanged).
#   * an UNANSWERED poll series (P8_STOP=query_unanswered) stops the series:
#     nothing came back rt_cd=0 for a whole window, and the next trial is
#     another walk down the same path.
#   * an ORDER-STATE-UNKNOWN stop (P8_STOP=order_state_unknown) stops the
#     series. A submit or amend that never answered may be resting on the
#     book under an ODNO nobody saw; the probe walks the book and cancels
#     what it can, and placing another order on top of that is the one thing
#     this runner must not do.
#   * a TRANSPORT stop (P8_STOP=transient:*, the POLL phase only) does NOT. The probe already waited
#     a whole poll interval and tried again; the series continues until
#     P8_MAX_TRANSIENT_STOPS of them, because a link that keeps dropping is a
#     reason to come back later and not a measurement.
#
# Guards, instance values, credential copying and the POLICY_VERSION handshake
# are the shared ones in _common.sh beside this file — the same guards
# run_p_ca.sh uses, so there is one copy of each.
#
# This script never deletes itself. With P8_CRON_MARK set it removes the one
# matching crontab line, and only after at least one trial has actually run.
#
# See tools/broker_probes/runners/README.md for an instantiation recipe.

set -u

# --- 0. the shared guards --------------------------------------------------

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P) || exit 2
# shellcheck source=tools/broker_probes/runners/_common.sh
# shellcheck disable=SC1091
. "$SCRIPT_DIR/_common.sh"
# Before the first log() call, so even step 1's ABORT lands in the operator's
# log file. P8_LOG is only PROVEN usable in step 3.
set_log_file "${P8_LOG:-}"

# --- 1. the checkout -------------------------------------------------------

guard_checkout "$SCRIPT_DIR" "${P8_ALLOW_SHARED_CHECKOUT:-0}" \
  P8_ALLOW_SHARED_CHECKOUT

# --- 2. runner and probe must be the same generation -----------------------
#
# '/1': probe_p8 classifies a transport failure and an EGW00215 ledger throttle
# as transient (one retry, one poll interval later) and prints the anchored
# P8_STOP= / P8_COEXISTENCE= lines this script reads. An older probe prints
# neither, and the loop below would classify every trial as "unknown" and stop
# — loudly, which is the point of the handshake.
EXPECT_POLICY_VERSION=p-8-transient-policy/1

# --- 3. instance values (no defaults) --------------------------------------

require_env \
  P8_LOG P8_PYTHON P8_CREDENTIAL_FILE P8_SYMBOL P8_TRIALS P8_QUANTITY \
  P8_PRICE_OFFSET_PCT P8_POLL_MS P8_PACE_S P8_VISIBILITY_TIMEOUT_S \
  P8_INTER_TRIAL_S P8_MAX_TRANSIENT_STOPS P8_EXPECT_KEY_FP \
  P8_EXPECT_ACCOUNT_FP P8_TOKEN_CACHE P8_EVIDENCE_DIR P8_NOTE

# Both are compared with -le/-gt below, and `[` on a non-number is a syntax
# error that would abort mid-series with a shell diagnostic instead of a
# reason.
case "$P8_TRIALS" in
*[!0-9]* | '' | 0) die "P8_TRIALS must be a positive integer (got '$P8_TRIALS')" ;;
esac
case "$P8_MAX_TRANSIENT_STOPS" in
*[!0-9]* | '')
  die "P8_MAX_TRANSIENT_STOPS must be a non-negative integer (got '$P8_MAX_TRANSIENT_STOPS')"
  ;;
esac
# This one reaches `sleep`, and `set -u` without `set -e` means a failed sleep
# is a WARNING on stderr and then trial N+1 fires back to back against the
# same account — the pacing hazard the inter-trial gap exists for. Seconds, so
# a decimal is fine; "30s" and "abc" are not (review F7).
case "$P8_INTER_TRIAL_S" in
'' | *[!0-9.]* | *.*.* | .)
  die "P8_INTER_TRIAL_S must be a non-negative number of seconds, digits and at most one '.' (got '$P8_INTER_TRIAL_S')"
  ;;
esac

# Step 5 appends every trial's whole output to P8_LOG, so prove the path first.
ensure_log_file "$P8_LOG" P8_LOG

PY="$P8_PYTHON"
guard_python_module "$PY" P8_PYTHON tools.broker_probes.probes_order \
  "$EXPECT_POLICY_VERSION"

[ -d "$P8_EVIDENCE_DIR" ] || die "evidence dir missing: $P8_EVIDENCE_DIR"

# --- 3b. the credential file, copied into the worktree if it is not there ---
#
# Relative -> this worktree, copied in from the primary checkout when absent
# and refused outright when the name is not gitignored; absolute -> used as
# given, never copied. The whole rule is in _common.sh.
resolve_credential_file "$P8_CREDENTIAL_FILE"

# --- 4. credentials, checked by fingerprint --------------------------------
#
# FUTURES keys, not stock: P-8 places a 모의 futures order. The 2026-09-23
# INVALID_CHECK_ACNO outage was an app key still bound to the PREVIOUS account
# after a re-application, which looks exactly like a propagation delay from the
# probe's side and is not one.
#
# There is no mock/real switch here and no Redis live-flag check. P-8 is
# mock-only in CODE — every order call goes through assert_mock_host() and
# assert_mock_trading_tr(), and _setup() runs assert_no_live_futures_config()
# before the first socket — so a guard in bash would only be a second,
# weaker copy of a refusal that already cannot be bypassed.

set -a
# The path is operator-supplied by design, so it cannot be followed statically.
# shellcheck disable=SC1090
. "$CRED_FILE"
set +a

mkdir -p "$P8_TOKEN_CACHE" && chmod 700 "$P8_TOKEN_CACHE"

check_key_fingerprint futures "${KIS_FUTURES_APP_KEY:-}" "$P8_EXPECT_KEY_FP" \
  "$CRED_FILE"
check_account_fingerprint futures "$PY" KIS_FUTURES_ACCOUNT_NO \
  "$P8_EXPECT_ACCOUNT_FP"

# --- 5. the trial series ---------------------------------------------------

# What the results dir already held, so a trial that wrote nothing cannot copy
# somebody else's artifact into the evidence corpus.
ART_BEFORE=$(newest_artifact P-8)

# $1: the trial label, for the log line.
copy_trial_artifact() {
  _art=$(newest_artifact P-8)
  if [ -z "$_art" ]; then
    log "WARN: no P-8 artifact under $REPO/tools/broker_probes/results/ — nothing copied (trial $1)"
  elif [ "$_art" = "$ART_BEFORE" ]; then
    log "WARN: newest artifact ($(basename "$_art")) predates trial $1 — NOT copied"
  elif cp "$_art" "$P8_EVIDENCE_DIR"/; then
    log "artifact copied: $(basename "$_art") -> $P8_EVIDENCE_DIR (trial $1)"
    # Only once the copy SUCCEEDED: advancing on failure would tell the next
    # trial this artifact was already secured, and a copy that never happened
    # would leave no trace at all.
    ART_BEFORE=$_art
  else
    log "WARN: could NOT copy $(basename "$_art") to $P8_EVIDENCE_DIR (trial $1) — this trial's evidence is only in $REPO/tools/broker_probes/results/"
  fi
  return 0
}

MEASURED=0
REJECTIONS=0
RATE_LIMIT_STOPS=0
QUERY_UNANSWERED=0
ORDER_STATE_UNKNOWN=0
TRANSPORT_STOPS=0
TRIALS_RUN=0
VERDICT=
trial=1

while [ "$trial" -le "$P8_TRIALS" ]; do
  log "=== START P-8 trial $trial/$P8_TRIALS $P8_SYMBOL qty=$P8_QUANTITY offset=${P8_PRICE_OFFSET_PCT}% poll=${P8_POLL_MS}ms pace=${P8_PACE_S}s"
  # argv as an ARRAY and expanded quoted: the note carries spaces, and an
  # unquoted scalar would split it into several argv words.
  PROBE_ARGS=(
    --asset futures --symbol "$P8_SYMBOL" --quantity "$P8_QUANTITY"
    --price-offset-pct "$P8_PRICE_OFFSET_PCT"
    --poll-ms "$P8_POLL_MS" --pace-s "$P8_PACE_S"
    --visibility-timeout-s "$P8_VISIBILITY_TIMEOUT_S"
    --confirm --token-cache-dir "$P8_TOKEN_CACHE"
    --note "$P8_NOTE | trial $trial/$P8_TRIALS"
  )
  OUT=$("$PY" -m tools.broker_probes.run P-8 "${PROBE_ARGS[@]}" 2>&1)
  rc=$?
  printf '%s\n' "$OUT" >>"$P8_LOG"
  TRIALS_RUN=$((TRIALS_RUN + 1))
  log "=== END P-8 trial $trial/$P8_TRIALS rc=$rc"
  copy_trial_artifact "$trial/$P8_TRIALS"

  STOP=$(printf '%s\n' "$OUT" | sed -n 's/^P8_STOP=//p' | tail -1)
  COEXISTENCE=$(printf '%s\n' "$OUT" | sed -n 's/^P8_COEXISTENCE=//p' | tail -1)

  # A non-zero exit first, and before the token is believed: the probe can
  # print a clean verdict and still die writing the artifact (run.py rc 5).
  # Same rule run_p_ca.sh applies to HELD= and REFERENCE_STATUS=.
  if [ "$rc" -ne 0 ]; then
    VERDICT="STOP: trial $trial exited $rc (P8_STOP=${STOP:-<none>}) — the probe did not complete, so its classification is not trustworthy and an order may be unaccounted for"
    break
  fi

  case "$STOP" in
  none)
    if [ "$COEXISTENCE" = "measured" ]; then
      MEASURED=$((MEASURED + 1))
      log "trial $trial: completed, coexistence measured"
    else
      # The loop ran to its end but recorded nothing. Not a stop, not a
      # sample; said out loud so it is not counted as either.
      log "WARN: trial $trial: P8_STOP=none but P8_COEXISTENCE=${COEXISTENCE:-<none>} — no sample from a trial that did not stop; read the artifact"
    fi
    ;;
  transient:*)
    TRANSPORT_STOPS=$((TRANSPORT_STOPS + 1))
    log "trial $trial: TRANSPORT stop ($STOP) — no coexistence sample, and NOT a broker rejection. The series continues (transport stops so far: $TRANSPORT_STOPS, budget $P8_MAX_TRANSIENT_STOPS)"
    ;;
  rejected)
    REJECTIONS=$((REJECTIONS + 1))
    VERDICT="STOP: the broker REJECTED trial $trial's submit — every remaining trial would be refused the same way"
    break
    ;;
  rate_limited)
    RATE_LIMIT_STOPS=$((RATE_LIMIT_STOPS + 1))
    VERDICT="STOP: trial $trial was rate-limited (HTTP 429 / EGW00201) — that is OUR call rate, and it stays a no-retry stop"
    break
    ;;
  order_state_unknown)
    ORDER_STATE_UNKNOWN=$((ORDER_STATE_UNKNOWN + 1))
    VERDICT="STOP: trial $trial lost an order-mutating call in transport, so whether the broker accepted it is UNKNOWN — the probe walked the book and its unaccounted_live_orders measurement says what it found. Placing another order on top of that is the one thing this runner must not do"
    break
    ;;
  query_unanswered)
    QUERY_UNANSWERED=$((QUERY_UNANSWERED + 1))
    VERDICT="STOP: trial $trial got no rt_cd=0 answer out of the open-order surface in its whole window — the surface is not answering, and the next trial is another walk down the same path"
    break
    ;;
  *)
    # Includes an EMPTY token. A missing line is what a probe that crashed
    # before its finally block looks like from here, and an unknown one is a
    # probe this runner was not written for — the handshake in step 2 should
    # have caught that, so reaching here means something else is wrong.
    VERDICT="STOP: trial $trial reported P8_STOP=${STOP:-<none>}, which this runner cannot classify — it will not keep placing orders on a state it cannot name"
    break
    ;;
  esac

  if [ "$TRANSPORT_STOPS" -gt "$P8_MAX_TRANSIENT_STOPS" ]; then
    VERDICT="STOP: $TRANSPORT_STOPS transport stop(s) exceeds P8_MAX_TRANSIENT_STOPS=$P8_MAX_TRANSIENT_STOPS — the link is not healthy enough to measure on, which is a reason to come back later and not a finding"
    break
  fi

  trial=$((trial + 1))
  if [ "$trial" -le "$P8_TRIALS" ]; then
    sleep "$P8_INTER_TRIAL_S"
  fi
done

if [ -z "$VERDICT" ]; then
  VERDICT="COMPLETE: the series ran to its end"
fi

# The counts are separate fields, never a sum. "오류 1건(브로커 거부 포함)" is
# the exact sentence this line exists to make unwriteable.
log "VERDICT: $VERDICT | trials_run=$TRIALS_RUN/$P8_TRIALS measured=$MEASURED broker_rejections=$REJECTIONS rate_limit_stops=$RATE_LIMIT_STOPS query_unanswered_stops=$QUERY_UNANSWERED order_state_unknown_stops=$ORDER_STATE_UNKNOWN transport_stops=$TRANSPORT_STOPS"
if [ "$ORDER_STATE_UNKNOWN" -gt 0 ]; then
  log "⚠ an order-mutating call was lost in transport — read the trial artifact's unaccounted_live_orders before scheduling P-8 again"
fi
if [ "$MEASURED" -ge 5 ]; then
  log "mode_determination: $MEASURED measured trial(s) — N>=5 is met; map to ReplaceSemantics only if they AGREE"
else
  log "mode_determination: $MEASURED measured trial(s) — N>=5 is NOT met, so capabilities.replace_semantics.mode stays unwritten"
fi

# --- 6. crontab (never self-deletion) --------------------------------------
#
# Only once a trial has actually run: an early ABORT leaves the schedule alone
# so the next slot can retry.
if [ -n "${P8_CRON_MARK:-}" ] && [ "$TRIALS_RUN" -gt 0 ]; then
  if crontab -l 2>/dev/null | grep -Fq -- "$P8_CRON_MARK"; then
    crontab -l 2>/dev/null | grep -Fv -- "$P8_CRON_MARK" | crontab - &&
      log "crontab entry matching '$P8_CRON_MARK' removed"
  else
    log "no crontab entry matched '$P8_CRON_MARK'"
  fi
fi

case "$VERDICT" in
COMPLETE:*) exit 0 ;;
*) exit 1 ;;
esac
