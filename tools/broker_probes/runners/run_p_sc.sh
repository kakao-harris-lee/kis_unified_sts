#!/usr/bin/env bash
# P-SC runner TEMPLATE — tracked on purpose, instance values from the environment.
#
# P-SC measures ONE thing (#948 step 1): what shape a cancel takes on the stock
# 모의투자 query surface — a `cncl_yn` flag on the original row, a separate row
# whose `orgn_odno` points at it, or both. It places 모의 stock orders. Real
# orders: 0, structurally (assert_mock_host + assert_mock_trading_tr on every
# call, plus the probe's own refusal when the environment names a REAL market).
#
# What is DIFFERENT from run_p8.sh / run_p_ca.sh, and why this file is short:
#
#   * **No trial series.** One slot, one probe invocation. P-SC's two trials are
#     internal and the probe sequences them itself, because trial B spends a
#     fill on top of trial A and the decision to continue is a reading of trial
#     A's own stop — not something a shell loop should re-derive.
#   * **No limits here.** Pacing, the order-call budget, the quantity cap, the
#     session window and the observation length all live in
#     config/broker_probes/stock_cancel_probe.yaml. A runner that also carried
#     them would be a second source for every one of them, which is the defect
#     the _common.sh header is about. PSC_CONFIG points at a different FILE; it
#     never overrides a value.
#
# Guards, instance values, credential copying and the POLICY_VERSION handshake
# are the shared ones in _common.sh beside this file — one copy each.
#
# This script never deletes itself. With PSC_CRON_MARK set it removes the one
# matching crontab line, and only after the probe has actually run: an early
# ABORT leaves the schedule in place so the next slot can retry.
#
# See tools/broker_probes/runners/README.md for an instantiation recipe.

set -u

# --- 0. the shared guards --------------------------------------------------

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P) || exit 2
# shellcheck source=tools/broker_probes/runners/_common.sh
# shellcheck disable=SC1091
. "$SCRIPT_DIR/_common.sh"
# Before the first log() call, so even step 1's ABORT lands in the operator's
# log file. PSC_LOG is only PROVEN usable in step 3.
set_log_file "${PSC_LOG:-}"

# --- 1. the checkout -------------------------------------------------------

guard_checkout "$SCRIPT_DIR" "${PSC_ALLOW_SHARED_CHECKOUT:-0}" \
  PSC_ALLOW_SHARED_CHECKOUT

# --- 2. runner and probe must be the same generation -----------------------
#
# '/1': probe_psc prints the anchored PSC_STOP= / PSC_CANCEL_SHAPE= /
# PSC_FLAT_AT_END= lines this script reads, on every path it can leave by, and
# classifies a lost order POST as order_state_unknown rather than letting the
# exception escape. An older probe prints none of them and the verdict below
# would read every run as unclassifiable — loudly, which is the point.
EXPECT_POLICY_VERSION=p-sc-cancel-shape/1

# --- 3. instance values (no defaults) --------------------------------------

require_env \
  PSC_LOG PSC_PYTHON PSC_CREDENTIAL_FILE PSC_SYMBOL PSC_TRIAL \
  PSC_EXPECT_KEY_FP PSC_EXPECT_ACCOUNT_FP PSC_TOKEN_CACHE PSC_EVIDENCE_DIR \
  PSC_NOTE

case "$PSC_TRIAL" in
both | a | b) ;;
*) die "PSC_TRIAL must be one of both|a|b (got '$PSC_TRIAL')" ;;
esac

# Step 5 appends the probe's whole output to PSC_LOG, so prove the path first.
ensure_log_file "$PSC_LOG" PSC_LOG

PY="$PSC_PYTHON"
guard_python_module "$PY" PSC_PYTHON tools.broker_probes.probes_stock_cancel \
  "$EXPECT_POLICY_VERSION"

[ -d "$PSC_EVIDENCE_DIR" ] || die "evidence dir missing: $PSC_EVIDENCE_DIR"

# The limits file, read by the probe and logged here so the log says which one
# governed the run. A relative value resolves against the repo root inside the
# probe; an unreadable path is refused before any credential is sourced.
if [ -n "${PSC_CONFIG:-}" ]; then
  case "$PSC_CONFIG" in
  /*) CONFIG_PATH=$PSC_CONFIG ;;
  *) CONFIG_PATH="$REPO/$PSC_CONFIG" ;;
  esac
  [ -r "$CONFIG_PATH" ] || die "PSC_CONFIG is not readable: $CONFIG_PATH"
  log "limits file: $CONFIG_PATH (PSC_CONFIG)"
else
  log "limits file: $REPO/config/broker_probes/stock_cancel_probe.yaml (default)"
fi

# --- 3b. the credential file, copied into the worktree if it is not there ---
#
# Relative -> this worktree, copied in from the primary checkout when absent
# and refused outright when the name is not gitignored; absolute -> used as
# given, never copied. The whole rule is in _common.sh.
resolve_credential_file "$PSC_CREDENTIAL_FILE"

# --- 4. credentials, checked by fingerprint --------------------------------
#
# STOCK keys, not futures: P-SC places a 모의 stock order.
#
# ⚠ This repo's PAPER stack exports KIS_STOCK_MARKET=real, because stock quotes
# need the real key (memory stock-needs-real-kis-key). So sourcing the paper
# .env here instead of .env.mock would hand the probe a REAL app key while
# every host assertion still passed. The probe refuses that itself
# (assert_mock_only_env, before the first socket); the fingerprint check below
# is the second, independent answer to the same question — the 2026-09-23
# INVALID_CHECK_ACNO outage was a key paired with the wrong account, which no
# market-name check can see.

set -a
# The path is operator-supplied by design, so it cannot be followed statically.
# shellcheck disable=SC1090
. "$CRED_FILE"
set +a

# Stated rather than assumed: if the credential file set a non-mock market the
# probe will refuse, and finding that out here costs no broker call.
log "KIS_STOCK_MARKET=${KIS_STOCK_MARKET:-<unset>} KIS_REAL_TRADING=${KIS_REAL_TRADING:-<unset>}"

mkdir -p "$PSC_TOKEN_CACHE" && chmod 700 "$PSC_TOKEN_CACHE"

check_key_fingerprint stock "${KIS_STOCK_APP_KEY:-}" "$PSC_EXPECT_KEY_FP" \
  "$CRED_FILE"
check_account_fingerprint stock "$PY" KIS_STOCK_ACCOUNT_NO \
  "$PSC_EXPECT_ACCOUNT_FP"

# --- 5. the run ------------------------------------------------------------

# What the results dir already held, so a run that wrote nothing cannot copy
# somebody else's artifact into the evidence corpus.
ART_BEFORE=$(newest_artifact P-SC)

PROBE_ARGS=(
  --asset stock --symbol "$PSC_SYMBOL" --trial "$PSC_TRIAL"
  --confirm --token-cache-dir "$PSC_TOKEN_CACHE"
  --note "$PSC_NOTE"
)
if [ -n "${PSC_CONFIG:-}" ]; then
  PROBE_ARGS+=(--config "$PSC_CONFIG")
fi

log "=== START P-SC $PSC_SYMBOL trial=$PSC_TRIAL"
OUT=$("$PY" -m tools.broker_probes.run P-SC "${PROBE_ARGS[@]}" 2>&1)
rc=$?
printf '%s\n' "$OUT" >>"$PSC_LOG"
log "=== END P-SC rc=$rc"

ART=$(newest_artifact P-SC)
if [ -z "$ART" ]; then
  log "WARN: no P-SC artifact under $REPO/tools/broker_probes/results/ — nothing copied"
elif [ "$ART" = "$ART_BEFORE" ]; then
  log "WARN: newest artifact ($(basename "$ART")) predates this run — NOT copied"
elif cp "$ART" "$PSC_EVIDENCE_DIR"/; then
  log "artifact copied: $(basename "$ART") -> $PSC_EVIDENCE_DIR"
else
  log "WARN: could NOT copy $(basename "$ART") to $PSC_EVIDENCE_DIR — this run's evidence is only in $REPO/tools/broker_probes/results/"
fi

STOP=$(printf '%s\n' "$OUT" | sed -n 's/^PSC_STOP=//p' | tail -1)
SHAPE=$(printf '%s\n' "$OUT" | sed -n 's/^PSC_CANCEL_SHAPE=//p' | tail -1)
FLAT=$(printf '%s\n' "$OUT" | sed -n 's/^PSC_FLAT_AT_END=//p' | tail -1)

# A non-zero exit FIRST, and before the token is believed: the probe can print
# a clean verdict and still die writing the artifact (run.py rc 5), and a
# SafetyViolation (rc 3) leaves no artifact at all. Same rule run_p8.sh applies
# to P8_STOP= and run_p_ca.sh to HELD=.
if [ "$rc" -ne 0 ]; then
  VERDICT="STOP: the probe exited $rc (PSC_STOP=${STOP:-<none>}) — its classification is not trustworthy, and an order may be unaccounted for"
else
  case "$STOP" in
  none)
    case "$SHAPE" in
    ORIGINAL_ROW_FLAGGED | SEPARATE_ROW_WITH_ORGN_ODNO | BOTH)
      VERDICT="COMPLETE: cancel shape MEASURED as $SHAPE"
      ;;
    NEITHER_OBSERVED)
      # The surface answered and showed neither. That IS a measurement, and a
      # consequential one: #948 step 2 cannot build a non-execution proof on a
      # surface that never marks the cancel. Not an error, so not a STOP.
      VERDICT="COMPLETE: the surface ANSWERED and showed neither a cncl_yn flag nor an orgn_odno row — read the artifact before designing #948 step 2 around either"
      ;;
    UNDETERMINED)
      VERDICT="STOP: the query surface did not answer (or every page came back full), so NOTHING was established — this is NOT 'the cancel does not show up'"
      ;;
    *)
      VERDICT="STOP: PSC_CANCEL_SHAPE=${SHAPE:-<none>}, which this runner cannot classify"
      ;;
    esac
    ;;
  rejected)
    VERDICT="STOP: the broker REJECTED a submit or the cancel — read msg_cd/msg1 in the artifact. A rejected CANCEL means trial A's order is still working, which is why no further order was placed"
    ;;
  cancel_not_confirmed)
    # The cancel was ACCEPTED and the order was never seen to stop working.
    # The shape measurement may be complete — that is a different question, and
    # the shape= field above carries its answer.
    VERDICT="STOP: the cancel was accepted but the order was never confirmed to stop working (cancel_confirmed=false) — no further order was placed. The shape verdict above may still be a valid measurement; read measurements.trial_a.cancel_confirmed.reason and check the account"
    ;;
  cancel_not_sendable)
    VERDICT="STOP: the accept response carried no KRX_FWDG_ORD_ORGNO (거래소코드), which order_rvsecncl declares [필수] — so NO cancel could be built for this order. An order is resting that this harness cannot cancel: settle it by hand. This is itself a finding about the accept response"
    ;;
  probe_error)
    VERDICT="STOP: a precondition or a lost GET ended the trials AFTER an order had been accepted. The artifact was still written and carries whatever had been measured plus the error — read measurements.aborted_after_first_order and errors[]"
    ;;
  rate_limited)
    VERDICT="STOP: rate-limited (HTTP 429 / EGW00201) — that is OUR call rate, and it stays a no-retry stop"
    ;;
  order_state_unknown)
    VERDICT="STOP: an order-mutating POST was lost in transport, so whether the broker accepted it is UNKNOWN. It is NOT resent (duplicate-order hazard). Read measurements.cleanup and check the account by hand"
    ;;
  query_unanswered)
    VERDICT="STOP: the order surface refused every snapshot of the observation window"
    ;;
  dry_run)
    VERDICT="COMPLETE: dry-run — nothing was sent"
    ;;
  *)
    # Includes an EMPTY token: that is what a probe that died before its
    # finally block looks like from here.
    VERDICT="STOP: PSC_STOP=${STOP:-<none>}, which this runner cannot classify"
    ;;
  esac
fi

# Separate fields, never a sum — the run_p8.sh rule. "flat" is its own field
# because an account left non-flat needs a human whatever the shape verdict was.
log "VERDICT: $VERDICT | rc=$rc stop=${STOP:-<none>} shape=${SHAPE:-<none>} flat_at_end=${FLAT:-<none>}"
if [ "$FLAT" != "yes" ]; then
  log "⚠ the account was NOT verified flat (flat_at_end=${FLAT:-<none>}) — read measurements.cleanup (holding_final / orders_final_live) and settle the account by hand BEFORE scheduling P-SC again"
fi

# --- 6. crontab (never self-deletion) --------------------------------------
#
# Reaching this line means the probe process actually ran: every guard above
# ends in `die`, which exits. So there is no "ran?" flag here — unlike
# run_p8.sh, which can break out of its trial LOOP before the first trial and
# therefore needs one. An early ABORT leaves the schedule in place so the next
# slot can retry.
if [ -n "${PSC_CRON_MARK:-}" ]; then
  if crontab -l 2>/dev/null | grep -Fq -- "$PSC_CRON_MARK"; then
    crontab -l 2>/dev/null | grep -Fv -- "$PSC_CRON_MARK" | crontab - &&
      log "crontab entry matching '$PSC_CRON_MARK' removed"
  else
    log "no crontab entry matched '$PSC_CRON_MARK'"
  fi
fi

case "$VERDICT" in
COMPLETE:*) exit 0 ;;
*) exit 1 ;;
esac
