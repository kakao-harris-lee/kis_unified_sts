#!/bin/bash
# Install / remove the CP-3 tenant daily cron block. DRY-RUN BY DEFAULT.
#
#   install_tenant_cron.sh             # dry-run: print the crontab diff and the copy plan
#   install_tenant_cron.sh --apply     # copy the wrapper from origin/main, write the block
#   install_tenant_cron.sh --remove    # dry-run of removing the block
#   install_tenant_cron.sh --remove --apply
#
# Runbook docs/runbooks/tos-paper-boot.md §7.2-e. Idempotent: the block is
# delimited by BEGIN/END markers and replaced whole; lines tagged
# `# cp3-long-tenant-daily` / `# cp3-short-tenant-daily` outside the block (the
# hand-installed 2026-10-22 lines) are dropped so a direction is never scheduled
# twice. Every other crontab line is kept byte for byte.
#
# Provenance: the wrapper copied to $DEST is read with `git show origin/main:…`,
# never from a working tree, and --apply refuses unless THIS installer's bytes
# equal origin/main's — an unmerged installer cannot install anything.
#
# Time zone: Ubuntu's cron (3.0pl1) does not implement CRON_TZ — the line is kept
# for the house convention (every block in this crontab declares it), but the
# KST guarantee is the host zone. --apply refuses unless `date +%z` is +0900.
#
# Knobs: CP3_CRON_REPO (default: this script's checkout), CP3_CRON_DEST_DIR
# (default $HOME/.config/kis-probes), CP3_CRON_STATE (default $HOME/.local/state/tos).
set -u
umask 077

APPLY=0
REMOVE=0
for a in "$@"; do
  case "$a" in
  --apply) APPLY=1 ;;
  --remove) REMOVE=1 ;;
  --dry-run) APPLY=0 ;;
  *) echo "usage: $0 [--remove] [--apply|--dry-run]" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P) || exit 2
REPO=${CP3_CRON_REPO:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)} || {
  echo "ABORT: $SCRIPT_DIR is not in a git checkout" >&2; exit 2; }
DEST_DIR=${CP3_CRON_DEST_DIR:-$HOME/.config/kis-probes}
STATE=${CP3_CRON_STATE:-$HOME/.local/state/tos}
DEST=$DEST_DIR/run-cp3-tenant-daily.sh
SRC_REL=tools/tos_cp3/runners/cp3_tenant_daily.sh
SELF_REL=tools/tos_cp3/runners/install_tenant_cron.sh

# Schedule (KST). LONG and SHORT are two minutes apart: both producers share the
# REAL read key and KIS issues at most one token per minute. Both start before
# the 08:45 CONTINUOUS open (calendar.yaml krx-index-futures) and before the
# resident paper session's own 08:45 line.
LONG_AT="38 8"
SHORT_AT="40 8"
BEGIN_MARK="# BEGIN CP3_TENANT_DAILY"
END_MARK="# END CP3_TENANT_DAILY"

die() { echo "ABORT: $*" >&2; exit 2; }

git -C "$REPO" rev-parse --verify --quiet origin/main >/dev/null ||
  die "origin/main not found in $REPO — git fetch origin first"
REF=$(git -C "$REPO" rev-parse --short=12 origin/main)
SRC=$(mktemp) || exit 2
CUR=$(mktemp) || exit 2
NEW=$(mktemp) || exit 2
trap 'rm -f "$SRC" "$CUR" "$NEW"' EXIT
git -C "$REPO" show "origin/main:$SRC_REL" >"$SRC" 2>/dev/null ||
  die "$SRC_REL is not on origin/main ($REF) — merge the PR first"
SRC_SHA=$(sha256sum "$SRC" | cut -c1-64)

# Current crontab. "no crontab for <user>" is an empty crontab, not an error.
crontab -l >"$CUR" 2>/dev/null || : >"$CUR"

line() { # line DIR lc AT
  printf '%s * * 1-5 /bin/bash %s %s >> %s/cp3-%s-tenant-daily.cron.log 2>&1 # cp3-%s-tenant-daily\n' \
    "$3" "$DEST" "$1" "$STATE" "$2" "$2"
}

# Everything except our block and the hand-installed tagged lines.
awk -v b="$BEGIN_MARK" -v e="$END_MARK" '
  index($0, b) == 1 { skip = 1; next }
  skip && index($0, e) == 1 { skip = 0; next }
  skip { next }
  /# cp3-(long|short)-tenant-daily[[:space:]]*$/ { next }
  { print }
' "$CUR" >"$NEW"

if [ "$REMOVE" = 0 ]; then
  {
    echo "$BEGIN_MARK (tools/tos_cp3/runners/install_tenant_cron.sh · runbook tos-paper-boot.md §7.2-e · wrapper origin/main $REF sha256 ${SRC_SHA:0:12})"
    echo "CRON_TZ=Asia/Seoul"
    line LONG long "$LONG_AT"
    line SHORT short "$SHORT_AT"
    echo "$END_MARK"
  } >>"$NEW"
fi

echo "== crontab diff ($([ "$REMOVE" = 1 ] && echo remove || echo install))"
diff -u --label current --label proposed "$CUR" "$NEW" && echo "(no change)"
if [ "$REMOVE" = 0 ]; then
  if [ -f "$DEST" ] && cmp -s "$SRC" "$DEST"; then
    echo "== wrapper $DEST already equals origin/main $REF:$SRC_REL"
  else
    echo "== wrapper copy origin/main $REF:$SRC_REL -> $DEST (sha256 ${SRC_SHA:0:12})$([ -f "$DEST" ] && echo ' — existing file backed up first')"
  fi
else
  echo "== wrapper $DEST is left in place (remove it by hand if wanted)"
fi
[ "$(date +%z)" = "+0900" ] || echo "WARN host zone is $(date +%z), not +0900 — cron would not fire at KST times (--apply refuses)"

if [ "$APPLY" = 0 ]; then
  echo "DRY-RUN — nothing written. Re-run with --apply."
  exit 0
fi

# ---------------------------------------------------------------- apply ----
[ "$(date +%z)" = "+0900" ] || die "host zone is $(date +%z); this cron has no working CRON_TZ"
SELF_HEAD=$(git -C "$REPO" show "origin/main:$SELF_REL" 2>/dev/null | sha256sum | cut -c1-64)
SELF_NOW=$(sha256sum "$SCRIPT_DIR/install_tenant_cron.sh" | cut -c1-64)
[ "$SELF_HEAD" = "$SELF_NOW" ] ||
  die "this installer differs from origin/main:$SELF_REL — run the merged one"

stamp=$(TZ=Asia/Seoul date +%Y%m%dT%H%M%S)
mkdir -p "$DEST_DIR"
cp -p "$CUR" "$DEST_DIR/crontab.bak.$stamp" || die "crontab backup failed"
echo "backed up crontab -> $DEST_DIR/crontab.bak.$stamp"

if [ "$REMOVE" = 0 ]; then
  [ -d "$STATE" ] || die "state dir $STATE missing — the cron log would have nowhere to go"
  if ! { [ -f "$DEST" ] && cmp -s "$SRC" "$DEST"; }; then
    if [ -f "$DEST" ]; then
      old=$(sha256sum "$DEST" | cut -c1-12)
      cp -p "$DEST" "$DEST.bak.$old" || die "wrapper backup failed"
      echo "backed up wrapper -> $DEST.bak.$old"
    fi
    install -m 700 "$SRC" "$DEST" || die "wrapper copy failed"
    echo "installed wrapper -> $DEST"
  fi
fi

if cmp -s "$CUR" "$NEW"; then
  echo "crontab unchanged"
else
  crontab "$NEW" || die "crontab write failed (backup $DEST_DIR/crontab.bak.$stamp)"
  echo "crontab written"
fi
