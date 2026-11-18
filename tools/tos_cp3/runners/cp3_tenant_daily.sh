#!/bin/bash
# CP-3 tenant — one unattended trading-day session per call, one direction each.
#
#   cp3_tenant_daily.sh LONG|SHORT|STOCK                      # the cron call (runs the session)
#   cp3_tenant_daily.sh LONG|SHORT|STOCK --preflight [DATE]   # read-only check for DATE (KST, default today)
#   cp3_tenant_daily.sh LONG|SHORT|STOCK --catch-up HH:MM     # @reboot: run the day's session if the HH:MM line was missed
#
# Rescope plan docs/plans/2026-10-22-tos-rescope-plan.md M1 (operator 2026-10-22:
# 「tenant 세션 cron 상시화 진행해」「SHORT도 같은 방식으로 상시화해」) and M2
# (operator 2026-11-05: 「주식 트리 매일 cron 등록 진행해」 — the 11-03 delegated
# one-off sequence, every trading day).
# Runbook: docs/runbooks/tos-paper-boot.md §7.2-e (cron) · §7.2-f (the stock tenant).
#
# LONG and SHORT are the two synthetic FUTURES tenants: they send nothing. STOCK is
# the kis-mock tenant (005930, 1 share, Setup D LONG) and it DOES send — to the KIS
# 모의투자 order endpoint, with the mock account's keys from custody. Everything the
# stock direction needs beyond the futures path is marked «STOCK» below.
#
# This is the tracked source of ~/.config/kis-probes/run-cp3-tenant-daily.sh.
# tools/tos_cp3/runners/install_tenant_cron.sh copies it there FROM origin/main
# (never from a working tree) and writes the cron block that calls the copy.
# Before 2026-10-23 the host copy was hand-made and untracked; the probe runners
# already paid for that once (tools/broker_probes/runners/README.md).
#
# What one call does (run mode):
#   1. flock on $LOCK_DIR/cp3-<dir>-tenant-daily.wrapper.lock, non-blocking. Busy means
#      the previous call is still running — that is a failure, and it alerts.
#   2. one session per day: an existing session dir is a refusal (alerts).
#   3. the durable-set parent must already exist (alerts) — its first genesis is
#      the operator's call (runbook §7.2-d), never this script's.
#   4. remove this direction's earlier worktrees (registered ones, never --force),
#      fetch, add a fresh DETACHED worktree of origin/main.
#   5. holiday/weekend check against the tenant calendar IN THAT TREE (+ any
#      CP3_DAILY_EXTRA_CLOSED dates) — closed means SKIP: worktree
#      removed, exit 0, no alert.
#   5b. STOCK only, after the holiday check and before the runner — two steps
#      that decide whether the session can send at all:
#        * the operation transport config
#          ($STATE/cp3-setup-d-stock-ops/kis_mock_transport.yaml) is written once
#          at setup and never updated, so a new required key on main is a boot
#          refusal and 0 sends (10-30 r1, runbook §7.2-f). Its top-level keys are
#          compared with setup_stock_mock_once.sh's at origin/main.
#        * the standing approval artifact's path is FIXED, so yesterday's file has
#          to leave it before the runtime boots — otherwise today's write is
#          refused and, worse, boot binds the stale digest (review-1031 HIGH-1).
#          A file carrying another day's date is MOVED to approvals-archive/.
#      Either one differing from what the day needs is a refusal that alerts; both
#      run after the holiday check so a weekday holiday still skips silently.
#   6. run_tenant_session.sh from that tree, every TENANT_* value set here. STOCK
#      takes that set from the tracked env example in that tree (one definition,
#      the file §7.2-f's start block sources) and this wrapper only names the
#      host's paths through TOS_*.
#   6b. STOCK only: wait (bounded) for the runner's `render ok` line, then write
#      today's standing approval (#955) — without it the flow stops at step 4 and
#      the session sends nothing. The bound grows by this day's open delay, because
#      the render follows the open (#924, §7.2-g). A session that ended before the
#      render gets no approval; a slot that already carried today's date is left
#      alone; a failed write alerts but never stops the session.
#   7. one telegram line at the end: rc 0/143 is a normal end, anything else is a
#      failure line. Pre-runner refusals (1-3, 5b, fetch, worktree) are failure lines.
#
# What `--catch-up HH:MM` adds (#1038 — the 2026-11-06 reboot): the host came back
# at 09:00:53 and this cron (Ubuntu 3.0pl1) does NOT replay a missed line, so the
# 08:38 · 08:40 · 08:53 lines never fired and that day's sessions only happened
# because a session was resumed by hand at 09:09-09:13. The installer's `@reboot`
# lines call this mode with the direction's OWN regular minute, and it enters the
# run path above only when all four of these hold — otherwise it logs ONE line and
# exits 0, with no alert:
#   a. today is a trading day — not a second calendar decision: the day goes through
#      step 5 above and takes its existing silent SKIP when the market is closed;
#   b. now (KST) >= HH:MM — a boot earlier than the regular minute leaves the day to
#      the regular line, which is still going to fire;
#   c. now < this day's stop_at — the same derivation the run path uses, so a dated
#      override (#924) moves this bound with the close;
#   d. today's session dir does not exist — a session cut by a mid-day reboot is NOT
#      restarted here. A second session on one day stays the operator's RUN=2
#      decision (runbook §7.2-f).
# A lock held by that direction's REGULAR run is the same kind of no-op (one more
# line, exit 0): the day is already being started by the line that owns the lock, so
# the `lock busy` failure a regular call reports would be a false alarm here.
# When it does proceed it sends one telegram line saying the start is a reboot
# catch-up, and then runs exactly as the cron line would: same lock, same steps.
#
# Telegram reuses the resident wrapper's channel (briefing bot) and the same rule:
# read only the two TELEGRAM_BRIEFING_* lines from $MAIN/.env, never source it.
# Bodies carry rc, direction, date and paths only — no runner output, because
# render.log and session.log hold account fingerprints (runbook §7.2 좌표 규율).
#
# Environment knobs (defaults are the designated host paths, runbook §7.2-b):
#   CP3_DAILY_MAIN          /home/deploy/project/kis_unified_sts
#   CP3_DAILY_STATE         $HOME/.local/state/tos
#   CP3_DAILY_LOCK_DIR      /tmp
#   CP3_DAILY_STOP_AT       (unset) — HH:MM to force a stop time. Unset, the stop is
#                           DERIVED: this day's session close from the tree's calendar
#                           (tools/tos_cp3/session_day.py, the producer config's
#                           calendar/session — a dated session_overrides entry wins,
#                           #924) plus CP3_DAILY_STOP_AFTER_CLOSE_MIN. A regular day
#                           gives 15:45 + 5 = 15:50 for futures and 15:30 + 10 =
#                           15:40 for STOCK, the values the two paths started with.
#   CP3_DAILY_STOP_AFTER_CLOSE_MIN  5 (LONG/SHORT) · 10 (STOCK)
#   CP3_DAILY_EXTRA_CLOSED  ""  space-separated extra closed dates (empty by
#                           default — KRX closures belong in the tenant calendar)
#   CP3_DAILY_NOTIFY        1   — 0 logs the body instead of sending it
#   ⛔ CP3_DAILY_TODAY      test-only date override (YYYY-MM-DD). Never in a cron
#                           line: the runner itself still runs on the real clock.
#   ⛔ CP3_DAILY_NOW        test-only clock override (HH:MM), read by `--catch-up`
#                           only. Never in a cron line, same reason.
#   ⛔ CP3_DAILY_APPROVAL_WAIT_TRIES / _SLEEP_S  120 / 10 — test-only: the STOCK
#                           `render ok` wait (20 minutes, PLUS this day's open
#                           delay — #924). Never in a cron line.
set -u
umask 077

DIR=${1:-}
case "$DIR" in
LONG) lc=long ;;
SHORT) lc=short ;;
STOCK) lc=stock ;;
*) echo "usage: $0 LONG|SHORT|STOCK [--preflight [YYYY-MM-DD] | --catch-up HH:MM]" >&2; exit 2 ;;
esac
MODE=run
CATCH_UP_AT=
case "${2:-}" in
"") ;;
--preflight) MODE=preflight ;;
--catch-up)
  MODE=catchup
  CATCH_UP_AT=${3:-}
  # Strict: the cron line carries this time, and a time this script cannot read
  # exactly is a time it must not compare against.
  case "$CATCH_UP_AT" in
  [01][0-9]:[0-5][0-9] | 2[0-3]:[0-5][0-9]) ;;
  *) echo "bad --catch-up time '$CATCH_UP_AT' (want HH:MM, 00:00-23:59)" >&2; exit 2 ;;
  esac
  # Nothing follows the time (review-1039 LOW-2): this mode is called from a cron
  # line, and a 4th word there is a typo whose silent half-meaning would be a
  # session nobody asked for.
  [ -z "${4:-}" ] ||
    { echo "unexpected argument '$4' after --catch-up $CATCH_UP_AT" >&2
      echo "usage: $0 LONG|SHORT|STOCK [--preflight [YYYY-MM-DD] | --catch-up HH:MM]" >&2
      exit 2; }
  ;;
*) echo "usage: $0 LONG|SHORT|STOCK [--preflight [YYYY-MM-DD] | --catch-up HH:MM]" >&2; exit 2 ;;
esac

MAIN=${CP3_DAILY_MAIN:-/home/deploy/project/kis_unified_sts}
STATE=${CP3_DAILY_STATE:-$HOME/.local/state/tos}
LOCK_DIR=${CP3_DAILY_LOCK_DIR:-/tmp}
STOP_AT=${CP3_DAILY_STOP_AT:-}
EXTRA_CLOSED=${CP3_DAILY_EXTRA_CLOSED-}
PY=$MAIN/.venv/bin/python

# Per-direction coordinates. The two futures tenants differ only in `$lc`; the
# STOCK tenant is a different tree, producer config, custody root and durable set
# (§7.2-b/§7.2-f) and carries two settings a futures session refuses.
case "$DIR" in
LONG | SHORT)
  MARKET=futures
  TREE=cp3-setup-d-$lc
  PRODUCER_REL=config/tos_probes/cp3-live-producer.yaml
  DATA_PARENT=$STATE/cp3-setup-d-$lc-data
  CUSTODY_ROOT=$STATE/paper-custody
  DEFAULT_AFTER_CLOSE_MIN=5
  ;;
STOCK)
  MARKET=stock
  TREE=cp3-setup-d-stock-005930
  PRODUCER_REL=config/tos_probes/cp3-live-producer-stock-005930.yaml
  DATA_PARENT=$STATE/cp3-setup-d-stock-005930-data
  CUSTODY_ROOT=$STATE/cp3-setup-d-stock-custody
  TRANSPORT_CONFIG=$STATE/cp3-setup-d-stock-ops/kis_mock_transport.yaml
  SETUP_REL=tools/tos_cp3/runners/setup_stock_mock_once.sh
  STOCK_ENV_REL=tools/tos_cp3/runners/stock-mock-session.env.example
  # 15:30 close + 10 = 15:40, the stop the 11-03 operator-approved sequence used
  # (TOS_STOCK_STOP_AT=15:40, runbook §7.2-f start block). Wider than the futures
  # 5 because 15:20-15:30 is the closing auction: the day's last minute bars and
  # the post-close evidence counts land after the close itself.
  DEFAULT_AFTER_CLOSE_MIN=10
  # Cron is always run 1. A second session on the same day stays the operator's
  # own RUN=2 start block (§7.2-f); this wrapper refuses one (session dir check).
  RUN=1
  APPROVAL_FILE=$CUSTODY_ROOT/approvals/standing-session.yaml
  APPROVAL_ARCHIVE=$CUSTODY_ROOT/approvals-archive
  APPROVAL_TODAY_PRESENT=0
  ;;
esac
CAL_REL=config/tos_runtime/$TREE/calendar.yaml
STOP_AFTER_CLOSE_MIN=${CP3_DAILY_STOP_AFTER_CLOSE_MIN:-$DEFAULT_AFTER_CLOSE_MIN}

TODAY=${CP3_DAILY_TODAY:-$(TZ=Asia/Seoul date +%F)}
if [ "$MODE" = preflight ] && [ -n "${3:-}" ]; then TODAY=$3; fi
case "$TODAY" in
[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
*) echo "bad date '$TODAY' (want YYYY-MM-DD)" >&2; exit 2 ;;
esac
# Only `--catch-up` reads a clock — every other mode is decided by the date alone.
NOW=
if [ "$MODE" = catchup ]; then
  NOW=${CP3_DAILY_NOW:-$(TZ=Asia/Seoul date +%H:%M)}
  case "$NOW" in
  [01][0-9]:[0-5][0-9] | 2[0-3]:[0-5][0-9]) ;;
  *) echo "bad time '$NOW' (want HH:MM, 00:00-23:59)" >&2; exit 2 ;;
  esac
fi
STAMP=${TODAY//-/}
if [ "$MARKET" = stock ]; then
  # `stock-r<RUN>-<날짜>` — the name the status board parses (_SESSION_DIR_RE) and
  # the runbook's own start/stop blocks use. Cron is r1; a manual restart is r2.
  SESSION=$STATE/cp3-sessions/stock-r$RUN-$STAMP
  WT=$STATE/measure/wt-cp3-stock-r$RUN-$STAMP
  WT_OLD_GLOB="wt-cp3-stock-r*-2*"
else
  SESSION=$STATE/cp3-sessions/$lc-$STAMP
  WT=$STATE/measure/wt-cp3-$lc-$STAMP
  WT_OLD_GLOB="wt-cp3-$lc-2*"
fi

log() { printf '%s [%s] %s\n' "$(TZ=Asia/Seoul date '+%F %T')" "$DIR" "$*"; }

# hhmm_min HH:MM — minutes since midnight, for the `--catch-up` comparisons.
# `10#` because `$((08))` is an invalid octal literal, and 08:38 is a real cron time.
hhmm_min() { echo $((10#${1%%:*} * 60 + 10#${1##*:})); }

notify() {
  local tok chat
  if [ "${CP3_DAILY_NOTIFY:-1}" = "0" ]; then
    log "notify SUPPRESSED by CP3_DAILY_NOTIFY=0 — body follows"
    log "notify-body: $1"
    return 0
  fi
  tok=$(grep -E '^(export )?TELEGRAM_BRIEFING_BOT_TOKEN=' "$MAIN/.env" 2>/dev/null | tail -1 | sed -E 's/^(export )?[A-Z_]+=//; s/^"//; s/"$//')
  chat=$(grep -E '^(export )?TELEGRAM_BRIEFING_CHAT_ID=' "$MAIN/.env" 2>/dev/null | tail -1 | sed -E 's/^(export )?[A-Z_]+=//; s/^"//; s/"$//')
  if [ -z "$tok" ] || [ -z "$chat" ]; then
    log "telegram notify FAILED: $([ -z "$tok" ] && echo TELEGRAM_BRIEFING_BOT_TOKEN)$([ -z "$tok" ] && [ -z "$chat" ] && echo ' and ')$([ -z "$chat" ] && echo TELEGRAM_BRIEFING_CHAT_ID) missing in $MAIN/.env — nothing was sent"
    log "notify-body: $1"
    return 0
  fi
  # Body before sending, so the log says WHAT was delivered (resident wrapper, review H1).
  log "notify-body(sending): $1"
  if curl --fail -sS -m 20 -X POST "https://api.telegram.org/bot${tok}/sendMessage" \
    --data-urlencode "chat_id=${chat}" --data-urlencode "text=$1" >/dev/null 2>&1; then
    log "telegram notified"
  else
    log "telegram notify FAILED"
  fi
}

# fail RC MESSAGE — log, alert, exit RC.
fail() {
  log "FAIL rc=$1 — $2"
  notify "CP-3 tenant $DIR 일일 세션 실패 ($TODAY) rc=$1
$2
cron 로그 $STATE/cp3-$lc-tenant-daily.cron.log"
  exit "$1"
}

# market_open CALENDAR_FILE DATE — exit 0 open, 10 closed, 11 the calendar has no
# holiday for DATE's year (a stale calendar would call every holiday open). Every
# other code — a traceback (exit 1: bad date, missing yaml), an unreadable file —
# is an error, never a skip: only 10 may become a silent SKIP.
MARKET_CLOSED=10
CALENDAR_STALE=11
market_open() {
  "$PY" - "$1" "$2" "$EXTRA_CLOSED" <<'PY'
import datetime, sys
import yaml
path, today, extra = sys.argv[1], sys.argv[2], sys.argv[3].split()
try:
    with open(path, encoding="utf-8") as fh:
        holidays = {str(h) for h in (yaml.safe_load(fh).get("holidays") or [])}
except Exception as exc:  # noqa: BLE001 — any unreadable calendar is a refusal
    print(f"calendar unreadable: {path}: {exc}", file=sys.stderr)
    sys.exit(2)
d = datetime.date.fromisoformat(today)  # 2026-02-30 raises -> exit 1 -> error
if not any(h.startswith(f"{d.year}-") for h in holidays):
    print(f"calendar {path} lists no holiday in {d.year}", file=sys.stderr)
    sys.exit(11)
sys.exit(10 if d.weekday() >= 5 or today in holidays or today in extra else 0)
PY
}

# session_day CMD TREE_ROOT PRODUCER_CONFIG [CALENDAR] — one value on stdout from
# tools/tos_cp3/session_day.py (stdlib + yaml), imported from TREE_ROOT. `-P` keeps
# the cwd off sys.path so only TREE_ROOT can answer the import.
session_day() {
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$2 "$PY" -P -m tools.tos_cp3.session_day "$1" \
    --producer-config "$3" --repo-root "$2" --date "$TODAY" \
    --after-close-min "$STOP_AFTER_CLOSE_MIN" ${4:+--calendar "$4"}
}

# STOCK — stock_transport_keydiff: compare the operation transport config's
# top-level keys with the canonical set in origin/main's setup_stock_mock_once.sh
# (its `mode: live` … `allow_plaintext…` heredoc). Exactly the §7.2-f eve-of-session
# check, and the 11-03 wrapper's first step.
#
# Why keys and not the whole file: the values are deployment facts (account product
# code, host) that the setup script fills in per host, while a MISSING key is the
# failure that actually happened — #979 added `app_key_request_wait_budget_ms` on
# 10-28 and the 10-26 operation file did not have it, so the 10-30 r1 session
# refused at boot with 0 sends. The file is written once and never updated.
#
# stdout: the diff (live vs canonical) or the reason. Exit 0 equal · 1 differ ·
# 2 either side unreadable. Secret-free: key NAMES only, never values.
stock_transport_keydiff() {
  local setup canon live
  setup=$(git -C "$MAIN" show "origin/main:$SETUP_REL" 2>/dev/null) || {
    echo "cannot read $SETUP_REL at origin/main in $MAIN"
    return 2
  }
  canon=$(printf '%s\n' "$setup" |
    sed -n '/^mode: live/,/^allow_plaintext/p' | grep -oE '^[a-z_A-Z]+:' | sort)
  [ -n "$canon" ] || {
    echo "origin/main:$SETUP_REL has no 'mode: live' … 'allow_plaintext' block to compare against"
    return 2
  }
  [ -f "$TRANSPORT_CONFIG" ] || {
    echo "transport config missing: $TRANSPORT_CONFIG (1회 준비 — 런북 §7.2-f)"
    return 2
  }
  live=$(grep -oE '^[a-z_A-Z]+:' "$TRANSPORT_CONFIG" | sort)
  [ "$live" = "$canon" ] && return 0
  diff <(printf '%s\n' "$live") <(printf '%s\n' "$canon")
  return 1
}

# STOCK — approval_slot FILE: whose trading date the standing approval artifact
# carries. stdout `absent` · `today` · `stale <YYYYMMDD>`, exit 0; exit 2 with the
# reason when a file IS there but cannot be read as one (review-1031 HIGH-1: the
# one thing not to do here is guess).
approval_slot() {
  "$PY" - "$1" "$STAMP" <<'PY'
import sys
import yaml
path, stamp = sys.argv[1], sys.argv[2]
try:
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
except FileNotFoundError:
    print("absent")
    sys.exit(0)
except Exception as exc:  # noqa: BLE001 — an unreadable artifact is a refusal
    print(f"unreadable: {path}: {exc}")
    sys.exit(2)
if not isinstance(doc, dict):
    print(f"not a YAML mapping: {path}")
    sys.exit(2)
raw = doc.get("trading_date")
# `trading_date: '20261103'` as the writer emits it. An unquoted 20261103 loads as
# an int and str() gives the same 8 digits; a `2026-11-03` date does NOT, and that
# is refused rather than normalised — a file this script cannot read exactly is a
# file it must not move.
text = "" if raw is None else str(raw).strip()
if len(text) != 8 or not text.isdigit():
    print(f"trading_date is {raw!r}, not YYYYMMDD: {path}")
    sys.exit(2)
print("today" if text == stamp else f"stale {text}")
PY
}

# STOCK — write_standing_approval: today's session-scoped standing approval (#955,
# runbook §7.2-f). Without it a signal stops at step 4 and the session sends
# nothing, so this is part of the unattended run, not an extra.
#
# Written only after the runner's `render ok`: the approval binds to the RENDERED
# config, and a session that ended before the render has none. The `-c` form is
# deliberate — `python -m tos_runtime.compose.cli` has no __main__, so it would do
# nothing and exit 0, logging a silent success (§7.2-f ⚠).
#
# A failed write alerts and returns 0: the session is already up and its own end
# line still has to carry the run rc.
# A file already carrying TODAY's date is not rewritten (the writer would refuse
# it anyway, and re-deriving it is the operator's `--replace` call). Set by the
# pre-runner slot step below.
#
# ⏳ The wait bound counts from the cron minute, and `render ok` lands after the
# runner's own first-row wait, which ends at the OPEN (on 11-05 the stock session
# started waiting at 08:53:06 and rendered at 09:01:25). On a dated-override day
# (#924) the open moves later, so the render moves with it — a 10:00 open puts it
# past 10:01, hours beyond the fixed 1200 s, and the wait would expire with no
# approval written: the whole day would send 0 (review-1021 r1 HIGH). The runner
# already grows its first-row bound by exactly this delay (run_tenant_session.sh
# step 5c), so the wrapper grows its wait by the same number of seconds, read from
# the same place (`session_day open-delay`) — never typed here.
# A failed read falls back to 0 with a log line rather than aborting: the runner
# reads the same calendar itself in step 5c and refuses the session if it cannot.
APPROVAL_WAIT_TRIES=${CP3_DAILY_APPROVAL_WAIT_TRIES:-120}
APPROVAL_WAIT_SLEEP_S=${CP3_DAILY_APPROVAL_WAIT_SLEEP_S:-10}
write_standing_approval() {
  local sl=$SESSION/session.log i=0 arc delay extra=0 tries=$APPROVAL_WAIT_TRIES
  if [ "$APPROVAL_TODAY_PRESENT" = 1 ]; then
    log "오늘($STAMP) 날짜 상시 승인이 이미 있다 — 쓰지 않는다 (재작성은 운영자의 --replace · 런북 §7.2-f)"
    return 0
  fi
  delay=$(session_day open-delay "$WT" "$WT/$PRODUCER_REL" 2>&1)
  case "$delay" in
  '' | *[!0-9]*)
    log "오늘 개장 지연을 읽지 못했다 — 상시 승인 대기는 기본 $((tries * APPROVAL_WAIT_SLEEP_S))s 그대로: $delay"
    ;;
  *)
    # The ternary short-circuits, so a test-only _SLEEP_S=0 does not divide by zero.
    extra=$((APPROVAL_WAIT_SLEEP_S > 0 ? delay / APPROVAL_WAIT_SLEEP_S : 0))
    if [ "$extra" -gt 0 ]; then
      tries=$((tries + extra))
      log "개장이 정규보다 ${delay}s 늦다 (#924) — 상시 승인 대기를 $((tries * APPROVAL_WAIT_SLEEP_S))s 로 늘린다"
    fi
    ;;
  esac
  while [ "$i" -lt "$tries" ]; do
    grep -q 'render ok' "$sl" 2>/dev/null && break
    kill -0 "$runner_pid" 2>/dev/null || break
    sleep "$APPROVAL_WAIT_SLEEP_S"
    i=$((i + 1))
  done
  if ! grep -q 'render ok' "$sl" 2>/dev/null; then
    if kill -0 "$runner_pid" 2>/dev/null; then
      log "no 'render ok' within $((tries * APPROVAL_WAIT_SLEEP_S))s — 상시 승인을 쓰지 않았다 (세션은 그대로 둔다)"
      notify "CP-3 tenant $DIR 상시 승인 못 씀 ($TODAY) — render ok 가 오지 않았다. 승인 없이는 송신 0
세션 $SESSION (session.log)"
    else
      log "세션이 render ok 전에 끝났다 — 상시 승인을 쓰지 않았다"
    fi
    return 0
  fi
  # PYTHONDONTWRITEBYTECODE, like the wrapper's other in-tree calls: a
  # `__pycache__` the wrapper itself left behind would make the next day's
  # `git worktree remove` refuse this tree as untracked-dirty.
  (
    cd "$WT" &&
      PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tos/runtime/src:tos/src "$PY" -c \
        'import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))' \
        write-standing-approval --config-dir "$SESSION/render" \
        --custody-root "$CUSTODY_ROOT" --environment-label paper --trading-date "$TODAY"
  ) >"$SESSION/approval.out" 2>&1
  arc=$?
  log "write-standing-approval rc=$arc ($SESSION/approval.out)"
  [ "$arc" = 0 ] && return 0
  notify "CP-3 tenant $DIR 상시 승인 쓰기 실패 ($TODAY) rc=$arc — 승인 없이는 송신 0
세션 $SESSION (approval.out)"
  return 0
}

# ---------------------------------------------------------------- preflight --
# Read-only: no lock, no fetch, no worktree, no telegram, writes nothing outside
# a mktemp file. Reads the calendar from the LOCAL origin/main ref (fetch first)
# and the contract month from $MAIN's working tree.
if [ "$MODE" = preflight ]; then
  ref=$(git -C "$MAIN" rev-parse --short=12 origin/main 2>/dev/null) || {
    log "PREFLIGHT origin/main not found in $MAIN"; exit 2; }
  cal=$(mktemp) || exit 2
  trap 'rm -f "$cal"' EXIT
  git -C "$MAIN" show "origin/main:$CAL_REL" >"$cal" 2>/dev/null || {
    log "PREFLIGHT $CAL_REL missing at origin/main $ref"; exit 2; }
  market_open "$cal" "$TODAY"
  mrc=$?
  case $mrc in
  0) open=OPEN ;;
  "$MARKET_CLOSED") open=CLOSED ;;
  "$CALENDAR_STALE") log "PREFLIGHT calendar has no holiday in ${TODAY:0:4} — a run would refuse"; exit 2 ;;
  *) log "PREFLIGHT calendar check failed (rc=$mrc)"; exit 2 ;;
  esac
  pcfg=$(mktemp) || exit 2
  # The reader comes from origin/main too, like the two files it reads — never
  # from $MAIN's working tree, whatever branch that is on (#963 review LOW-2).
  rdr=$(mktemp -d) || exit 2
  trap 'rm -f "$cal" "$pcfg"; rm -rf "$rdr"' EXIT
  git -C "$MAIN" show "origin/main:$PRODUCER_REL" >"$pcfg" 2>/dev/null || {
    log "PREFLIGHT $PRODUCER_REL missing at origin/main $ref"; exit 2; }
  mkdir -p "$rdr/tools/tos_cp3"
  git -C "$MAIN" show "origin/main:tools/tos_cp3/session_day.py" >"$rdr/tools/tos_cp3/session_day.py" 2>/dev/null || {
    log "PREFLIGHT tools/tos_cp3/session_day.py missing at origin/main $ref"; exit 2; }
  if [ "$open" = OPEN ]; then
    win=$(session_day show "$rdr" "$pcfg" "$cal" 2>&1) || {
      log "PREFLIGHT session window unreadable: $win"; exit 2; }
    stop=${STOP_AT:-$(session_day stop-at "$rdr" "$pcfg" "$cal" 2>&1)} || {
      log "PREFLIGHT stop time unreadable: $stop"; exit 2; }
    log "PREFLIGHT session $win · stop_at=$stop$([ -n "$STOP_AT" ] && echo ' (CP3_DAILY_STOP_AT)')"
  fi
  if [ "$MARKET" = stock ]; then
    # A stock symbol does not roll, and it is named in ONE place — the env example
    # the runner is handed (TENANT_INSTRUMENT). Read from origin/main, like the
    # files above, so the preflight never reports $MAIN's working tree.
    inst=$(git -C "$MAIN" show "origin/main:$STOCK_ENV_REL" 2>/dev/null |
      sed -n 's/^TENANT_INSTRUMENT=//p' | tail -1)
    [ -n "$inst" ] || {
      log "PREFLIGHT TENANT_INSTRUMENT not found in origin/main:$STOCK_ENV_REL"; exit 2; }
    kd=$(stock_transport_keydiff)
    case $? in
    0) log "PREFLIGHT transport config keys = 정본 ($TRANSPORT_CONFIG)" ;;
    1)
      log "PREFLIGHT transport config keys DIFFER from origin/main:$SETUP_REL — a run would refuse (송신 0):"
      printf '%s\n' "$kd"
      ;;
    *) log "PREFLIGHT transport config not comparable — a run would refuse: $kd" ;;
    esac
    # Read-only: says what the run WOULD do with the approval slot, moves nothing.
    slot=$(approval_slot "$APPROVAL_FILE")
    case $? in
    0) case "$slot" in
      absent) log "PREFLIGHT standing approval slot free — the run writes today's after 'render ok'" ;;
      today) log "PREFLIGHT standing approval slot already carries $STAMP — the run would keep it and write nothing" ;;
      *) log "PREFLIGHT standing approval slot carries ${slot#stale } — the run would archive it to $APPROVAL_ARCHIVE/standing-session.${slot#stale }.yaml" ;;
      esac ;;
    *) log "PREFLIGHT standing approval slot not readable — a run would refuse: $slot" ;;
    esac
  else
    inst=$(PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$MAIN "$PY" -c 'import datetime, sys
from shared.instruments.futures import get_front_month_code
print(get_front_month_code(product="mini", target_date=datetime.date.fromisoformat(sys.argv[1])))' "$TODAY" 2>&1) || {
      log "PREFLIGHT front-month lookup failed: $inst"; exit 2; }
  fi
  leaf=$DATA_PARENT/$inst
  log "PREFLIGHT date=$TODAY market=$open origin/main=$ref instrument=$inst"
  log "PREFLIGHT data parent $DATA_PARENT $([ -d "$DATA_PARENT" ] && echo present || echo MISSING)"
  log "PREFLIGHT leaf $leaf $([ -d "$leaf" ] && echo 'present (continues)' || echo 'absent (first session genesis)')"
  log "PREFLIGHT session dir $SESSION $([ -e "$SESSION" ] && echo 'EXISTS (run would refuse)' || echo free)"
  log "PREFLIGHT worktree $WT $([ -e "$WT" ] && echo 'EXISTS (run would refuse)' || echo free)"
  exit 0
fi

# ---------------------------------------------------------------------- run --
# The host cron (Ubuntu 3.0pl1) ignores CRON_TZ: the schedule is KST only because
# the host zone is. If that ever changes, the 08:38/08:40/08:53 lines fire at the
# wrong hour.
[ "$(date +%z)" = "+0900" ] || fail 2 "host zone is $(date +%z), not +0900 — cron times are not KST (CRON_TZ is ignored by this cron)"

# `--catch-up` gates b and d (#1038). Both before the lock and the fetch: a reboot
# catch-up that has nothing to do must cost nothing and must not alert. d first asks
# the cheapest question there is — a path — and asking it here is also what keeps a
# RUNNING session from being reported as `lock busy`: the live session holds the
# lock AND owns a session dir. The run path's own `$SESSION already exists` refusal
# below stays as the backstop for the race between these two lines.
if [ "$MODE" = catchup ]; then
  if [ "$(hhmm_min "$NOW")" -lt "$(hhmm_min "$CATCH_UP_AT")" ]; then
    log "CATCH-UP SKIP — 지금 $NOW 은 정규 cron 시각 $CATCH_UP_AT 전이다; 그 줄이 발화한다"
    exit 0
  fi
  if [ -e "$SESSION" ]; then
    log "CATCH-UP SKIP — 오늘 세션 디렉터리가 이미 있다 ($SESSION); 끊긴 세션을 자동 재기동하지 않는다 (RUN=2 는 운영자 결정 · 런북 §7.2-f)"
    exit 0
  fi
fi

mkdir -p "$LOCK_DIR" 2>/dev/null
# `.wrapper.lock`, not the `.lock` the 2026-10-22 hand-installed lines take with an
# OUTER flock: an outer and an inner flock on one path would refuse every call.
LOCK=$LOCK_DIR/cp3-$lc-tenant-daily.wrapper.lock
exec 9>"$LOCK" || fail 2 "cannot open lock $LOCK"
flock -n 9 || {
  # In catch-up mode a held lock is the regular run, not a failure (review-1039
  # LOW-1). The windows are real: LONG's `@reboot sleep 90` lands inside the 08:38
  # call when the host boots around 08:36:30-08:37, STOCK's `sleep 390` inside the
  # 08:53 one when it boots around 08:46:30-08:47 — and that call has not created
  # its session dir yet, so gate d above cannot see it. The day is already being
  # started by the line that owns the lock; alerting would be a false alarm.
  if [ "$MODE" = catchup ]; then
    log "CATCH-UP SKIP — lock held by the regular run ($LOCK); 정규 줄의 호출이 오늘 세션을 이미 시작하고 있다"
    exit 0
  fi
  fail 75 "lock busy ($LOCK) — 앞선 $DIR 호출이 아직 돈다. 오늘 세션은 시작하지 않았다"
}

[ -e "$SESSION" ] && fail 2 "$SESSION already exists — refusing (one session per day)"
[ -d "$DATA_PARENT" ] || fail 2 "data parent missing: $DATA_PARENT (create it 0700 first — runbook §7.2-b)"

# Earlier days' worktrees of this direction (registered ones only, never --force).
git -C "$MAIN" worktree prune
for old in "$STATE"/measure/$WT_OLD_GLOB; do
  [ -d "$old" ] || continue
  [ "$old" = "$WT" ] && continue
  if git -C "$MAIN" worktree remove "$old" 2>/dev/null; then
    log "removed old worktree $old"
  else
    log "WARN could not remove $old (dirty or unregistered) — left in place"
  fi
done

git -C "$MAIN" fetch -q origin || fail 1 "git fetch failed in $MAIN"
[ -e "$WT" ] && fail 2 "$WT already exists — refusing"
mkdir -p "$STATE/measure"
git -C "$MAIN" worktree add -q --detach "$WT" origin/main || fail 1 "worktree add failed: $WT"
log "worktree $WT @ $(git -C "$WT" rev-parse --short=12 HEAD) (detached origin/main)"

market_open "$WT/$CAL_REL" "$TODAY"
mrc=$?
case $mrc in
0) ;;
"$MARKET_CLOSED")
  log "market closed on $TODAY (weekend/holiday per $TREE calendar or extra '$EXTRA_CLOSED') — SKIP"
  git -C "$MAIN" worktree remove "$WT" && log "removed $WT"
  exit 0
  ;;
"$CALENDAR_STALE")
  git -C "$MAIN" worktree remove "$WT" 2>/dev/null
  fail 2 "$CAL_REL lists no holiday in ${TODAY:0:4} — calendar not updated for this year; refusing rather than treating holidays as open"
  ;;
*)
  git -C "$MAIN" worktree remove "$WT" 2>/dev/null
  fail 2 "holiday check failed (rc=$mrc) on $WT/$CAL_REL for $TODAY — not skipped, not run"
  ;;
esac

# The stop time, and — in catch-up mode — the last of the four gates (#1038 c).
# It sits here, between the holiday check and the STOCK pre-runner steps, because a
# catch-up that is already past the stop has to decide BEFORE those steps move this
# host's standing-approval file or alert about its transport keys: a reboot
# catch-up that is not going to run a session changes nothing and says nothing.
if [ -z "$STOP_AT" ]; then
  STOP_AT=$(session_day stop-at "$WT" "$WT/$PRODUCER_REL" 2>&1) || {
    git -C "$MAIN" worktree remove "$WT" 2>/dev/null
    fail 2 "stop time not derivable from $WT/$PRODUCER_REL's calendar for $TODAY: $STOP_AT"
  }
  log "stop_at $STOP_AT ($(session_day show "$WT" "$WT/$PRODUCER_REL" 2>&1) + ${STOP_AFTER_CLOSE_MIN}m)"
else
  log "stop_at $STOP_AT (CP3_DAILY_STOP_AT)"
fi

if [ "$MODE" = catchup ]; then
  if [ "$(hhmm_min "$NOW")" -ge "$(hhmm_min "$STOP_AT")" ]; then
    log "CATCH-UP SKIP — 지금 $NOW 은 오늘 정지 시각 $STOP_AT 이후다; 남은 세션 시간이 없다"
    git -C "$MAIN" worktree remove "$WT" && log "removed $WT"
    exit 0
  fi
  # Gates a-d all hold: this is a start the day would not otherwise have had.
  notify "CP-3 tenant $DIR 재부팅 catch-up 기동 ($TODAY) — 정규 cron $CATCH_UP_AT 줄이 재부팅으로 미발화했다
지금 $NOW · 정지 $STOP_AT · 세션 $SESSION"
fi

# ------------------------------------------------- STOCK pre-runner steps ----
#
# AFTER the holiday check (review-1031 LOW-1): a weekday holiday has to SKIP
# silently, and it would not if a stale operation file refused the day first.
# BEFORE the runner, because both of these decide whether the session can send.
#
# fail_wt — the two refusals above spell these two steps out inline; from here on
# a refusal has the same shape often enough to name it.
fail_wt() {
  git -C "$MAIN" worktree remove "$WT" 2>/dev/null
  fail "$1" "$2"
}

if [ "$MARKET" = stock ]; then
  # 1) the operation transport config's keys (header step 4b).
  kd=$(stock_transport_keydiff)
  case $? in
  0) log "transport config keys = 정본 ($TRANSPORT_CONFIG)" ;;
  1) fail_wt 2 "운영 전송 설정 키가 정본(origin/main:$SETUP_REL)과 다르다 — 이대로 부팅하면 거부되고 송신 0 이다. 그 키를 정본과 같은 값으로 손으로 넣을 것 (런북 §7.2-f):
$kd" ;;
  *) fail_wt 2 "전송 설정 키 대조 실패 — $kd" ;;
  esac

  # 2) one approval slot, and it must be today's (review-1031 HIGH-1).
  #
  # The artifact path is FIXED — $CUSTODY_ROOT/approvals/standing-session.yaml
  # (tos_runtime STANDING_APPROVAL_RELPATH). Two facts about it meant the second
  # cron day onwards would send nothing:
  #   * the writer REFUSES an existing file unless --replace
  #     (authority/standing_cli.py write_standing_document), so yesterday's file
  #     makes today's write exit 1 and every signal stops at step 4;
  #   * --replace alone does not fix it: the runtime's bind_at_boot() binds
  #     whatever is in that path WHEN IT BOOTS, and any other digest afterwards is
  #     refused as `digest_changed_since_bound` for the life of that process
  #     (authority/standing.py). So the stale file has to be gone before boot.
  # Hence: moved out here, before the runner starts. Moved and not deleted — it is
  # the record of that day's authority — and moved OUTSIDE approvals/, because
  # per-proposal approval files live in that directory.
  slot=$(approval_slot "$APPROVAL_FILE")
  case $? in
  0) ;;
  *) fail_wt 2 "상시 승인 파일을 읽을 수 없다 — $slot
손으로 보고 치우거나 고칠 것(런북 §7.2-f). 추측해서 옮기지 않았다 — 송신 0" ;;
  esac
  case "$slot" in
  absent)
    log "standing approval slot free ($APPROVAL_FILE)"
    ;;
  today)
    APPROVAL_TODAY_PRESENT=1
    log "standing approval slot already carries today ($STAMP) — 보존하고 쓰지 않는다"
    ;;
  "stale "*)
    was=${slot#stale }
    mkdir -m 700 -p "$APPROVAL_ARCHIVE" || fail_wt 2 "cannot create $APPROVAL_ARCHIVE"
    dest=$APPROVAL_ARCHIVE/standing-session.$was.yaml
    n=1
    while [ -e "$dest" ]; do
      # Never overwrite an archived file: one more day's authority record.
      dest=$APPROVAL_ARCHIVE/standing-session.$was.$n.yaml
      n=$((n + 1))
      [ "$n" -gt 99 ] && fail_wt 2 "cannot find a free archive name for $APPROVAL_FILE ($was) under $APPROVAL_ARCHIVE"
    done
    mv -n "$APPROVAL_FILE" "$dest" || fail_wt 2 "cannot archive $APPROVAL_FILE -> $dest"
    # `mv -n` does nothing and still exits 0 when the target appeared in between.
    [ -e "$APPROVAL_FILE" ] && fail_wt 2 "$APPROVAL_FILE is still there after mv -n to $dest — refusing (a stale approval at boot binds its digest for the whole session)"
    log "archived the $was standing approval -> $dest"
    ;;
  *) fail_wt 2 "approval_slot said '$slot', which this script does not understand" ;;
  esac
fi

mkdir -p "$SESSION"
if [ "$MARKET" = stock ]; then
  # The stock session's TENANT_* set is the tracked env example IN THAT TREE — the
  # same file §7.2-f's start block sources, so there is one definition of it and
  # this wrapper only supplies the TOS_* values that name the host's paths.
  # Backgrounded (the futures path runs in the foreground) because the approval
  # has to be written while the session is already up; the end line still carries
  # the run rc, because `wait` below is what produces it.
  (
    cd "$WT" || exit 70
    export TOS_REPO=$WT TOS_PYTHON=$PY \
      TOS_STOCK_SESSION_ROOT=$SESSION \
      TOS_STOCK_DATA_PARENT=$DATA_PARENT \
      TOS_STOCK_ENV_MOCK=$MAIN/.env.mock \
      TOS_STOCK_CUSTODY_ROOT=$CUSTODY_ROOT \
      TOS_STOCK_KIS_MOCK_TRANSPORT_CONFIG=$TRANSPORT_CONFIG \
      TOS_STOCK_STOP_AT=$STOP_AT
    set -a
    # shellcheck source=/dev/null
    . "./$STOCK_ENV_REL" || exit 70
    set +a
    exec bash tools/tos_cp3/runners/run_tenant_session.sh
  ) >"$SESSION/runner.out" 2>&1 &
  runner_pid=$!
  echo "$runner_pid" >"$SESSION/runner.pid"
  log "runner pid=$runner_pid session=$SESSION — waiting for 'render ok' to write today's standing approval"
  write_standing_approval
  wait "$runner_pid"
  rc=$?
else
  TENANT_LOG=$SESSION/session.log \
  TENANT_PYTHON=$PY \
  TENANT_TREE=$TREE \
  TENANT_DIRECTION=$DIR \
  TENANT_RENDER_OUT=$SESSION/config \
  TENANT_DATA_PARENT=$DATA_PARENT \
  TENANT_JOURNAL=$SESSION/journal.jsonl \
  TENANT_STOP_AT=$STOP_AT \
  TENANT_ENV_FILE=$MAIN/.env.mock \
  TENANT_CUSTODY_ROOT=$CUSTODY_ROOT \
  TENANT_ENVIRONMENT_LABEL=paper \
  TENANT_PRODUCER_CONFIG=$WT/$PRODUCER_REL \
  TENANT_PRODUCER_SESSION_DIR=$SESSION/producer \
    "$WT/tools/tos_cp3/runners/run_tenant_session.sh" >"$SESSION/runner.out" 2>&1
  rc=$?
fi
log "runner rc=$rc session=$SESSION"

# --- the bar-document export (roadmap §P1 ②) -------------------------------
#
# HERE, and not inside run_tenant_session.sh, for one reason: the session AND
# its B3 reconciliation (that script's step 14) must both be finished, and
# "the runner returned" is exactly that point. Before the exit-code `case`
# below, because that case `exit`s on the normal codes.
#
# ⛔ **It cannot change this session's verdict.** Same discipline as B3: the rc
# is logged and discarded. The session's exit code is about the runtime and the
# producer, and a read-only export that could not run says nothing about
# either. Nothing between here and the `case` may fail the script, so every
# expansion is `${VAR:-}` (this script runs under `set -u`) and the only
# command is wrapped in `timeout`.
#
# It READS the session directory and the tenant durable set — both 0700, both
# owned by the user this cron runs as — and WRITES only into
# $TOS_OPERATOR_PROJECTION_DIR (the directory the dashboard already has
# bind-mounted read-only) plus its own log beside the session's others.
#
# ⚠ "outside the session and data trees", NOT "outside $STATE": on this host
# TOS_OPERATOR_PROJECTION_DIR is $STATE/paper-projection, i.e. UNDER the state
# root. What the hook never touches is any session directory's contents beyond
# its own log, and any tenant durable set.
#
# ⚠ Unset variable = SKIP, logged. That variable is not part of the tenant
# cron's environment today (it lives in .env.paper, for the resident paper
# session), so until an operator exports it for this wrapper the hook says so
# and does nothing. A guessed destination would write a document the container
# does not mount, which from the page is indistinguishable from no document.
BARS_CEILING_S=${CP3_BARS_CEILING_S:-120}
# `timeout 0s` disables the ceiling, so 0 and non-numbers fall back to 120.
case $BARS_CEILING_S in ''|*[!0-9]*|0) BARS_CEILING_S=120 ;; esac
if [ -z "${TOS_OPERATOR_PROJECTION_DIR:-}" ]; then
  log "=== BARS EXPORT SKIPPED — TOS_OPERATOR_PROJECTION_DIR is unset, so there is no directory the dashboard reads; set it for this wrapper to enable the /tos bar panel (this does NOT affect the session)"
elif [ "${TOS_OPERATOR_PROJECTION_DIR#/}" = "$TOS_OPERATOR_PROJECTION_DIR" ]; then
  log "=== BARS EXPORT SKIPPED — TOS_OPERATOR_PROJECTION_DIR=$TOS_OPERATOR_PROJECTION_DIR is not absolute; a relative path resolves against cron's cwd, not the dashboard mount (this does NOT affect the session)"
elif [ ! -f "$WT/tools/tos_cp3/export_bars.py" ]; then
  # `-f` alone: the file is run as `"$PY" <script>`, so its execute bit is
  # irrelevant and the earlier `! -x && ! -f` pair could only ever agree with
  # `! -f`.
  log "=== BARS EXPORT SKIPPED — $WT/tools/tos_cp3/export_bars.py is absent at this origin/main revision (this does NOT affect the session)"
else
  # ⚠ The `--kill-after` SIGKILL can land between the exporter's `mkstemp` and
  # its `os.replace`, leaving one `.<name>.<rand>.tmp` in the bars directory.
  # DOCUMENTED, not swept (decision, review of #1060): the route lists only
  # `*.json` and such a file's suffix is `.tmp`, so it is invisible to the page
  # and to `latest`, and `os.replace` means no half-written document is ever
  # served. One dotfile per kill in a 0700 directory does not earn a sweeper
  # (CLAUDE.md R5 — a new guard needs a real incident beside it). Both halves
  # are pinned on the Python side: `_write_atomically`'s docstring records the
  # decision and `test_latest_ignores_a_leftover_temp_file` proves the listing
  # cannot mistake one for a document.
  log "=== BARS EXPORT session=$SESSION -> ${TOS_OPERATOR_PROJECTION_DIR}/bars ceiling ${BARS_CEILING_S}s"
  timeout --kill-after=5s "${BARS_CEILING_S}s" \
    "$PY" "$WT/tools/tos_cp3/export_bars.py" "$SESSION" \
    --out-dir "$TOS_OPERATOR_PROJECTION_DIR" \
    --state-dir "$STATE" >>"$SESSION/bars-export.out" 2>&1
  bars_rc=$?
  log "=== END BARS EXPORT rc=$bars_rc (record: $SESSION/bars-export.out · this rc does NOT change the session's)"
fi

# Exit codes: runbook §7.2-d 「종료 코드」.
case $rc in
0 | 143)
  notify "CP-3 tenant $DIR 일일 세션 종료 ($TODAY) rc=$rc — 정상
세션 $SESSION"
  exit "$rc"
  ;;
3) why="ABORT — 가드·렌더·라벨 등 (runner.out 의 ABORT 줄)" ;;
4) why="가드 모듈 세대 불일치" ;;
5) why="런타임은 끝났는데 생산자가 세션 중에 멈췄다 — 깨끗한 세션이 아니다" ;;
# Only the STOCK branch produces this: its subshell could not cd into the
# worktree or could not read the env example, so the runner never started.
70) why="세션을 시작하지 못했다 — 워크트리 진입 또는 env 예시 읽기 실패 (runner.out)" ;;
129 | 130) why="신호를 받고 끝났다" ;;
*) why="예상하지 못한 종료" ;;
esac
fail "$rc" "runner rc=$rc: $why
세션 $SESSION (runner.out · session.log)"
