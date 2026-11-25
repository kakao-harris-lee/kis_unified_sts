#!/usr/bin/env bash
# 장중 bars 내보내기 — 오늘 날짜의 CP-3 tenant 세션 전부를 한 번씩.
#
# 세션이 끝난 뒤 한 번 내보내던 것(cp3_tenant_daily.sh)에 더해, 장중에도 같은
# 문서를 다시 쓴다. 그 wrapper 의 주석이 적어 둔 그대로 「장중 갱신은 자기
# cron 줄」이고, 이 스크립트가 그 줄이 부르는 것이다.
#
# 측정(2026-11-25 세션 5개, 이 호스트): 세션당 1.3~1.5s, 다섯 개 직렬 6.6s,
# 최대 RSS 122MB. 5분 주기 안에 넉넉히 들어간다.
set -uo pipefail

REPO="${TOS_REPO:-/home/deploy/project/kis_unified_sts}"
STS="${TOS_STS:-$REPO/.venv/bin/sts}"
STATE="${TOS_STATE_DIR:-$HOME/.local/state/tos}"
OUT="${TOS_OPERATOR_PROJECTION_DIR:-$STATE/paper-projection}"
SESSIONS="${TOS_SESSIONS_DIR:-$STATE/cp3-sessions}"
LOCK="${TOS_EXPORT_BARS_LOCK:-/tmp/tos-export-bars-intraday.lock}"
CEILING_S="${TOS_EXPORT_BARS_CEILING_S:-120}"
DRY_RUN="${TOS_EXPORT_BARS_DRY_RUN:-0}"
TODAY="${TOS_EXPORT_BARS_DATE:-$(date +%Y%m%d)}"

# SAFETY: 겹치는 틱을 쌓지 않는다 — 앞 틱이 아직 돌면 조용히 빠진다. 블로킹으로 기다리면 5분마다 한 줄씩 밀려 결국 동시에 다섯 개가 돈다
exec 9>"$LOCK" || exit 0
flock -n 9 || {
  echo "$(date -Is) busy — 앞 틱이 아직 돈다, 건너뜀"
  exit 0
}

shopt -s nullglob
found=0
for dir in "$SESSIONS"/*-"$TODAY"; do
  [ -d "$dir" ] || continue
  name="$(basename "$dir")"
  found=$((found + 1))
  if [ "$DRY_RUN" = "1" ]; then
    echo "$(date -Is) would export $name"
    continue
  fi
  # SAFETY: 증거 저장소는 sqlite `mode=ro` 로만 열린다(session_inputs._connect_ro · inspect_evidence._read_only) — 도는 tenant 의 잎에 쓰지 않고, WAL 이라 쓰기를 막지도 않는다
  timeout --kill-after=5s "${CEILING_S}s" \
    "$STS" tos export-bars "$name" --out-dir "$OUT" --state-dir "$STATE"
  echo "$(date -Is) $name rc=$?"
done

[ "$found" = 0 ] && echo "$(date -Is) $TODAY 세션 없음"
# SAFETY: 내보내기 실패로 cron 을 붉게 만들지 않는다 — 이 문서는 읽기 표면이고, 실패는 위 rc 줄이 로그에 남긴다
exit 0
