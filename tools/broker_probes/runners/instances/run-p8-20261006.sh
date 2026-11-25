#!/usr/bin/env bash
# P0-2 T3 — P-8 캠페인 3~6회차 (모의 선물 replace/amend 공존 측정).
#
# 트라이얼 수는 4다(세션 리드 결정 2026-10-02): 09-28 의 MEASURED 1회 + 이번 4회로
# mode_determination 의 N>=5 를 한 슬롯에서 채울 수 있게 했다. 3회였다면 누적 4회로
# 모자랐다. ⚠ 템플릿의 mode_determination 줄은 자기 시리즈만 세므로 4회가 전부
# 측정돼도 "N>=5 is NOT met" 을 찍는다 — 누적 판정은 사람이 한다.
#
# 무인 실행 (운영자 승인 2026-10-02). 이 래퍼는 저장소의 추적 템플릿
# tools/broker_probes/runners/run_p8.sh (PR #841) 를 분리 워크트리(detached
# origin/main)에서 호출한다. 가드·중단 정책·증거 기록·판정은 전부 템플릿의 것이고,
# 여기 있는 것은 인스턴스 값과 통지뿐이다.
#
# 실행일: 2026-10-06 (화) 09:05 KST.
#   운영자 지시서의 10-05 (월) 는 **휴장일**이다 — config/market_schedule.yaml
#   「2026-10-05 대체휴일」(개천절 10-03 토요일의 대체) ·
#   config/tos_runtime/paper/calendar.yaml:46 도 동일. 10-03 토 / 10-04 일 /
#   10-05 대체휴일 → 다음 KRX 거래일은 10-06 (화).
#
# P8_SYMBOL=A05610 — 2026-10-06 의 mini 근월물. 추측이 아니라 저장소의 리졸버로
#   도출했다: shared.instruments.futures.get_front_month_code("mini",
#   date(2026,10,6)) == "A05610", 만기 = 둘째 목요일 2026-10-08. 같은 종목으로
#   09-28 1·2회차가 접수됐다(아티팩트 args.symbol=A05610). 리졸버는 순수 날짜
#   연산이라 브로커 호출이 필요 없다. ⚠ 10-08 이 만기이므로 이 슬롯이 불발되면
#   A05610 으로 쓸 수 있는 거래일은 10-07 뿐이다. 리졸버는 **만기 다음 날인
#   10-09 부터** A05611 을 돌려준다(실측: 10-08→A05610, 10-09→A05611); 10-09 는
#   한글날 휴장이고 10-12 가 그 다음 거래일일 뿐, 롤오버 날짜가 10-12 인 것은
#   아니다. (만기 지난 종목은 측정이 아니라 거부 — runners/README.md.)
#
# 이 파일의 추적 사본이 저장소에 있다: tools/broker_probes/runners/instances/
#   run-p8-20261006.sh. **실행되는 것은 이 호스트 파일이고, 저장소 사본은 기록이다.**
#   둘이 어긋나면 기록이 틀린 것이므로, 시작할 때 자기 sha256 을 로그에 찍어
#   아티팩트와 대조할 수 있게 한다(2026-09-28 러너가 사라져 README 한 줄만
#   남았고 그 줄이 틀렸던 사고 — run_p8.sh 헤더).
#
# 슬롯은 하나뿐이고 재무장하지 않는다: P-8 의 order_state_unknown 중단은 사람이
# 장부를 봐야 하는 상태(unaccounted_live_orders)이고, 그 위에 다시 주문을 올리는
# 것이 이 러너가 하지 말아야 할 단 하나의 일이다(run_p8.sh 헤더).
#
# 끝나면 로그 요약을 텔레그램 briefing 채널로 보낸다(.env 전체 소싱 없이 두 줄만 읽는다).
# 자기 자신을 지우지 않는다. 크론 줄은 템플릿(P8_CRON_MARK)이 지우고, 템플릿이
# 지우지 못한 경우에만 아래에서 해제한다 — 이 항목은 일회성 날짜 슬롯이라 남겨
# 두면 2027-10-06 에 다시 발화한다. **모든 조기 종료 경로가 disarm 을 거친다**
# (로그 디렉터리 생성 실패·증거 디렉터리 생성 실패·fetch 실패·워크트리 실패):
# 해제를 템플릿에만 맡기면 템플릿은 트라이얼이 한 번도 안 돌았을 때 줄을 지우지
# 않으므로(TRIALS_RUN -gt 0 조건), 디스크가 막힌 날 ABORT 한 슬롯이 1년 뒤
# 만기가 한참 지난 A05610 으로 되살아난다.
set -u

MAIN=/home/deploy/project/kis_unified_sts
W=/home/deploy/.local/state/kis/wt-p8-20261006
LOG=/home/deploy/.config/kis-probes/p8-20261006.log
EVID=/home/deploy/.local/state/kis/p-8-evidence     # 내구 호스트 경로; 캠페인 README 편입은 수동
CRON_MARK=run-p8-20261006

# 셀프테스트는 **첫 줄을 찍기 전에** 갈라진다. 실행 로그에는 한 글자도 쓰지
# 않는다: summarize() 가 LOG 에서 ' VERDICT: ' 의 마지막 줄을 집으므로 가짜
# 한 줄이 남으면 당일 ABORT 때 그 가짜가 보고되고, 「실행 로그가 아직 없다」가
# 「아직 안 돌았다」의 신호 구실을 못 하게 된다.
SELFTEST=0
if [ "${1:-}" = "--selftest" ]; then
  SELFTEST=1
  LOG=${P8_SELFTEST_LOG:-${LOG%.log}-selftest.log}
fi

log() { printf '%s %s\n' "$(TZ=Asia/Seoul date '+%F %T')" "$*" | tee -a "$LOG"; }

notify() {
  # $1 = text. briefing 두 변수만 읽는다; .env 전체를 소싱하지 않는다.
  local tok chat
  tok=$(grep -E '^(export )?TELEGRAM_BRIEFING_BOT_TOKEN=' "$MAIN/.env" | tail -1 | sed -E 's/^(export )?[A-Z_]+=//; s/^"//; s/"$//')
  chat=$(grep -E '^(export )?TELEGRAM_BRIEFING_CHAT_ID=' "$MAIN/.env" | tail -1 | sed -E 's/^(export )?[A-Z_]+=//; s/^"//; s/"$//')
  [ -n "$tok" ] && [ -n "$chat" ] || { log "notify skipped: briefing credentials not found"; return 0; }
  # A && B || C 가 아니라 if: log() 는 tee 의 종료 코드를 돌려주므로, curl 이
  # 성공했는데 로그 쓰기가 실패하면 "FAILED" 를 찍는 거짓 보고가 된다.
  if curl -sS -m 20 -X POST "https://api.telegram.org/bot${tok}/sendMessage" \
    --data-urlencode "chat_id=${chat}" --data-urlencode "text=$1" >/dev/null 2>&1; then
    log "telegram notified"
  else
    log "telegram notify FAILED"
  fi
}

disarm() {
  # 셀프테스트는 crontab 에 손대지 않는다. 점검하다가 진짜 슬롯을 해제하는 것이
  # 이 함수로 낼 수 있는 가장 나쁜 사고다.
  if [ "$SELFTEST" = "1" ]; then
    log "disarm: SELFTEST — crontab 손대지 않음"
    return 0
  fi
  # 템플릿이 이미 지웠으면 아무 것도 하지 않는다.
  if crontab -l 2>/dev/null | grep -Fq -- "$CRON_MARK"; then
    crontab -l 2>/dev/null | grep -Fv -- "$CRON_MARK" | crontab - &&
      log "crontab: '$CRON_MARK' 줄 해제(래퍼) — 일회성 슬롯이라 남기면 2027 에 재발화한다"
  else
    log "crontab: '$CRON_MARK' 줄 없음(템플릿이 이미 해제했거나 처음부터 없었다)"
  fi
}

# $1 = 아티팩트를 찾을 results 디렉터리. VERDICT·mode_determination·경고·아티팩트 목록을 조립한다.
summarize() {
  local resdir arts verdict modeline warnline
  resdir=$1
  # shellcheck disable=SC2012  # 하네스가 만든 <ID>-<UTC>Z.json 이름뿐 (공백·개행 없음) — _common.sh::newest_artifact 와 같은 판단
  arts=$(ls -t "$resdir"/P-8-*.json 2>/dev/null | head -5 | xargs -r -n1 basename | tr '\n' ' ')
  [ -n "$arts" ] || arts="(none)"
  verdict=$(grep -F ' VERDICT: ' "$LOG" 2>/dev/null | tail -1 | cut -c1-600)
  [ -n "$verdict" ] || verdict="(VERDICT 줄 없음 — 템플릿이 트라이얼 루프에 닿기 전에 ABORT 했다)"
  modeline=$(grep -F ' mode_determination: ' "$LOG" 2>/dev/null | tail -1 | cut -c1-300)
  warnline=$(grep -F 'order-mutating call was lost' "$LOG" 2>/dev/null | tail -1 | cut -c1-300)
  printf '%s\n' "$verdict"
  [ -n "$modeline" ] && printf '%s\n' "$modeline"
  [ -n "$warnline" ] && printf '⚠ %s\n' "$warnline"
  printf 'artifacts: %s\n' "$arts"
  return 0
}

# 로그 디렉터리가 먼저다. 없으면 log() 의 tee 가 조용히 실패해 모든 줄이
# cron stdout 으로만 흘러간다 — 「시도가 사라졌다」는 모양 그 자체다.
# 실패해도 disarm 은 거쳐야 한다(헤더의 「모든 조기 종료 경로」 참조).
if ! mkdir -p -- "$(dirname -- "$LOG")"; then
  printf 'ABORT: 로그 디렉터리 생성 실패 %s\n' "$(dirname -- "$LOG")"
  disarm
  exit 2
fi

# 자기 sha256 — 호스트 파일이 실행되는 것이고 저장소의 instances/ 사본은 기록이다.
# 둘이 어긋났는지는 이 줄과 저장소 사본의 해시를 대조하면 바로 보인다.
log "=== 래퍼 $0 sha256=$(sha256sum -- "$0" 2>/dev/null | cut -d' ' -f1 || echo UNKNOWN)"

mkdir -p "$EVID" || {
  log "ABORT: evidence dir 생성 실패 $EVID"
  disarm
  exit 2
}

# --- selftest: 브로커도 git 도 건드리지 않고 summarize + notify 만 돌린다 ----
if [ "$SELFTEST" = "1" ]; then
  # LOG 는 이미 파일 머리에서 셀프테스트용으로 갈아끼웠다(SELFTEST 블록).
  log "=== SELFTEST (브로커 호출 없음, 워크트리 없음, crontab 손대지 않음) log=$LOG"
  SELF_RES=${2:-$EVID}
  SUM=$(summarize "$SELF_RES")
  log "selftest summary ↓"
  printf '%s\n' "$SUM" | tee -a "$LOG"
  notify "[SELFTEST] P-8 3~6회차(2026-10-06 09:05 KST, A05610) 예약 점검 — 실제 실행 아님
$SUM
로그 $LOG"
  log "=== SELFTEST 끝"
  exit 0
fi

log "=== P-8 3~6회차 무인 실행 시작 (A05610, 만기 2026-10-08)"
git -C "$MAIN" fetch -q origin || { log "ABORT: git fetch failed"; disarm; notify "P-8 3~6회차 ABORT: git fetch failed"; exit 2; }
if [ -d "$W" ]; then git -C "$MAIN" worktree remove --force "$W" 2>/dev/null || rm -rf "$W"; fi
git -C "$MAIN" worktree add -q --detach "$W" origin/main || { log "ABORT: worktree add failed"; disarm; notify "P-8 3~6회차 ABORT: worktree add failed"; exit 2; }
log "worktree $W at $(git -C "$W" rev-parse --short HEAD)"

export P8_PYTHON="$MAIN/.venv/bin/python"
export P8_LOG="$LOG"
export P8_CREDENTIAL_FILE=.env.mock          # 상대경로 → 워크트리; gitignore 확인 뒤 주 체크아웃에서 복사
export P8_SYMBOL=A05610                      # 2026-10-06 mini 근월물 (만기 2026-10-08)
export P8_TRIALS=4                           # 캠페인 3·4·5·6 회차 (이 시리즈 안에서는 1/4..4/4). 09-28 MEASURED 1 + 4 = N>=5 도달 가능 (세션 리드 결정 2026-10-02)
export P8_QUANTITY=1
export P8_PRICE_OFFSET_PCT=10.0
export P8_POLL_MS=200
export P8_PACE_S=1.1
export P8_VISIBILITY_TIMEOUT_S=30
export P8_INTER_TRIAL_S=1                    # 09-28 실행과 동일 (아티팩트 args.inter_trial_s=1.0)
export P8_MAX_TRANSIENT_STOPS=2
export P8_EXPECT_KEY_FP=39a004459922         # .env.mock 선물 앱키 (09-23 교체분, 09-28 블록과 동일)
export P8_EXPECT_ACCOUNT_FP=46c39c54d3bb     # 모의 선물 계좌 (09-28 아티팩트 credentials.account_fingerprint)
export P8_TOKEN_CACHE=/home/deploy/.config/kis-probes/p8-20261006-token-cache
export P8_EVIDENCE_DIR="$EVID"
export P8_CRON_MARK="$CRON_MARK"             # 트라이얼이 실제로 돈 뒤에만 템플릿이 지운다
# P8_CANCEL_UNACCOUNTED 는 일부러 설정하지 않는다 (기본 off): 잃어버린 주문과 몸이
# 일치하는 행이라도 이 모의 계좌는 캠페인 공용이므로 기록하고 멈춘다.
export P8_NOTE="t3 P-8 campaign trials 3-6 (unattended host cron 2026-10-06 09:05 KST; this series labels them 1/4..4/4; 4 trials so that 09-28's 1 MEASURED + 4 can reach N>=5): resuming after the 09-28 series stopped at trial 2 on a ConnectionError mid coexistence poll (1 MEASURED). Tracked runner template run_p8.sh + probes_order transient policy (PR #841) from a detached origin/main worktree; mock futures account 46c39c54d3bb, futures app key 39a004459922 (09-23 rotation); symbol A05610 = mini front month on the day per shared.instruments.futures.get_front_month_code, expiry 2026-10-08"

"$W/tools/broker_probes/runners/run_p8.sh"
rc=$?
log "=== 템플릿 종료 rc=$rc"

disarm
SUM=$(summarize "$W/tools/broker_probes/results")
printf '%s\n' "$SUM" >>"$LOG"
notify "P-8 3~6회차(2026-10-06, A05610) 무인 실행 종료 rc=$rc
$SUM
증거 사본: $EVID (캠페인 README 편입은 수동)
워크트리 $W (results/ 보존)
로그 $LOG"
exit $rc
