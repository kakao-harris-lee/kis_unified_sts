#!/bin/bash
# CP-3 tenant — one unattended trading-day session per call, one direction each.
#
#   cp3_tenant_daily.sh LONG|SHORT                      # the cron call (runs the session)
#   cp3_tenant_daily.sh LONG|SHORT --preflight [DATE]   # read-only check for DATE (KST, default today)
#
# Rescope plan docs/plans/2026-10-22-tos-rescope-plan.md M1 (operator 2026-10-22:
# 「tenant 세션 cron 상시화 진행해」「SHORT도 같은 방식으로 상시화해」).
# Runbook: docs/runbooks/tos-paper-boot.md §7.2-e.
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
#   5. holiday/weekend check against the tenant calendar IN THAT TREE (+ the KRX
#      year-end close, not yet in the calendar) — closed means SKIP: worktree
#      removed, exit 0, no alert.
#   6. run_tenant_session.sh from that tree, every TENANT_* value set here.
#   7. one telegram line at the end: rc 0/143 is a normal end, anything else is a
#      failure line. Pre-runner refusals (1-3, fetch, worktree) are failure lines.
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
#                           gives 15:45 + 5 = 15:50, the value this knob defaulted to.
#   CP3_DAILY_STOP_AFTER_CLOSE_MIN  5
#   CP3_DAILY_EXTRA_CLOSED  "2026-12-31"  space-separated extra closed dates
#                           (calendar.yaml lists 12-31 only as an operator review
#                           candidate; drop it here once the calendar carries it)
#   CP3_DAILY_NOTIFY        1   — 0 logs the body instead of sending it
#   ⛔ CP3_DAILY_TODAY      test-only date override (YYYY-MM-DD). Never in a cron
#                           line: the runner itself still runs on the real clock.
set -u
umask 077

DIR=${1:-}
case "$DIR" in
LONG) lc=long ;;
SHORT) lc=short ;;
*) echo "usage: $0 LONG|SHORT [--preflight [YYYY-MM-DD]]" >&2; exit 2 ;;
esac
MODE=run
if [ "${2:-}" = "--preflight" ]; then
  MODE=preflight
elif [ -n "${2:-}" ]; then
  echo "usage: $0 LONG|SHORT [--preflight [YYYY-MM-DD]]" >&2; exit 2
fi

MAIN=${CP3_DAILY_MAIN:-/home/deploy/project/kis_unified_sts}
STATE=${CP3_DAILY_STATE:-$HOME/.local/state/tos}
LOCK_DIR=${CP3_DAILY_LOCK_DIR:-/tmp}
STOP_AT=${CP3_DAILY_STOP_AT:-}
STOP_AFTER_CLOSE_MIN=${CP3_DAILY_STOP_AFTER_CLOSE_MIN:-5}
EXTRA_CLOSED=${CP3_DAILY_EXTRA_CLOSED-2026-12-31}
PY=$MAIN/.venv/bin/python
TREE=cp3-setup-d-$lc
CAL_REL=config/tos_runtime/$TREE/calendar.yaml
PRODUCER_REL=config/tos_probes/cp3-live-producer.yaml
DATA_PARENT=$STATE/cp3-setup-d-$lc-data

TODAY=${CP3_DAILY_TODAY:-$(TZ=Asia/Seoul date +%F)}
if [ "$MODE" = preflight ] && [ -n "${3:-}" ]; then TODAY=$3; fi
case "$TODAY" in
[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
*) echo "bad date '$TODAY' (want YYYY-MM-DD)" >&2; exit 2 ;;
esac
STAMP=${TODAY//-/}
WT=$STATE/measure/wt-cp3-$lc-$STAMP
SESSION=$STATE/cp3-sessions/$lc-$STAMP

log() { printf '%s [%s] %s\n' "$(TZ=Asia/Seoul date '+%F %T')" "$DIR" "$*"; }

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
  inst=$(PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$MAIN "$PY" -c 'import datetime, sys
from shared.instruments.futures import get_front_month_code
print(get_front_month_code(product="mini", target_date=datetime.date.fromisoformat(sys.argv[1])))' "$TODAY" 2>&1) || {
    log "PREFLIGHT front-month lookup failed: $inst"; exit 2; }
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
# the host zone is. If that ever changes, the 08:38 line fires at the wrong hour.
[ "$(date +%z)" = "+0900" ] || fail 2 "host zone is $(date +%z), not +0900 — cron times are not KST (CRON_TZ is ignored by this cron)"

mkdir -p "$LOCK_DIR" 2>/dev/null
# `.wrapper.lock`, not the `.lock` the 2026-10-22 hand-installed lines take with an
# OUTER flock: an outer and an inner flock on one path would refuse every call.
LOCK=$LOCK_DIR/cp3-$lc-tenant-daily.wrapper.lock
exec 9>"$LOCK" || fail 2 "cannot open lock $LOCK"
flock -n 9 || fail 75 "lock busy ($LOCK) — 앞선 $DIR 호출이 아직 돈다. 오늘 세션은 시작하지 않았다"

[ -e "$SESSION" ] && fail 2 "$SESSION already exists — refusing (one session per day)"
[ -d "$DATA_PARENT" ] || fail 2 "data parent missing: $DATA_PARENT (create it 0700 first — runbook §7.2-b)"

# Earlier days' worktrees of this direction (registered ones only, never --force).
git -C "$MAIN" worktree prune
for old in "$STATE"/measure/wt-cp3-$lc-2*; do
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

if [ -z "$STOP_AT" ]; then
  STOP_AT=$(session_day stop-at "$WT" "$WT/$PRODUCER_REL" 2>&1) || {
    git -C "$MAIN" worktree remove "$WT" 2>/dev/null
    fail 2 "stop time not derivable from $WT/$PRODUCER_REL's calendar for $TODAY: $STOP_AT"
  }
  log "stop_at $STOP_AT ($(session_day show "$WT" "$WT/$PRODUCER_REL" 2>&1) + ${STOP_AFTER_CLOSE_MIN}m)"
else
  log "stop_at $STOP_AT (CP3_DAILY_STOP_AT)"
fi

mkdir -p "$SESSION"
TENANT_LOG=$SESSION/session.log \
TENANT_PYTHON=$PY \
TENANT_TREE=$TREE \
TENANT_DIRECTION=$DIR \
TENANT_RENDER_OUT=$SESSION/config \
TENANT_DATA_PARENT=$DATA_PARENT \
TENANT_JOURNAL=$SESSION/journal.jsonl \
TENANT_STOP_AT=$STOP_AT \
TENANT_ENV_FILE=$MAIN/.env.mock \
TENANT_CUSTODY_ROOT=$STATE/paper-custody \
TENANT_ENVIRONMENT_LABEL=paper \
TENANT_PRODUCER_CONFIG=$WT/$PRODUCER_REL \
TENANT_PRODUCER_SESSION_DIR=$SESSION/producer \
  "$WT/tools/tos_cp3/runners/run_tenant_session.sh" >"$SESSION/runner.out" 2>&1
rc=$?
log "runner rc=$rc session=$SESSION"

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
129 | 130) why="신호를 받고 끝났다" ;;
*) why="예상하지 못한 종료" ;;
esac
fail "$rc" "runner rc=$rc: $why
세션 $SESSION (runner.out · session.log)"
