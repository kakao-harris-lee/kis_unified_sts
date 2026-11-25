#!/usr/bin/env bash
# P-SC 1회차 — 주식 MOCK 취소 행 모양 측정 (#948 순서 1).
#
# 실행일: **2026-11-02 (월) 10:30 KST** (운영자 승인 2026-10-29).
#   10-30(금)·11-02(월) 모두 거래일이고 휴장 목록에 없다
#   (config/tos_runtime/paper/calendar.yaml holidays — 11월 항목 없음).
#   11-02 을 고른 이유는 **그날 주식 MOCK 세션이 없다**는 것이다: 공용 모의 주식
#   계좌에 다른 레인의 주문·보유가 없어야 프로브가 시작할 수 있고
#   (assert_flat_start), 있으면 그 자체로 거부다.
#   10:30 은 개장 직후 변동 구간을 피하면서 YAML 창(09:00-15:20) 한가운데다.
#
# 무인 실행 ≠ 무인 결정. 이 래퍼는 저장소의 추적 템플릿
# tools/broker_probes/runners/run_p_sc.sh 를 분리 워크트리(detached origin/main)
# 에서 **한 번** 호출한다. 가드·중단 정책·증거 기록·판정은 전부 템플릿과 프로브의
# 것이고, 여기 있는 것은 인스턴스 값과 통지뿐이다. 한도(페이싱·주문 호출 예산·
# 수량 상한·창·관측 길이)는 **이 파일에도 템플릿에도 없다** —
# config/broker_probes/stock_cancel_probe.yaml 에 있다.
#
# 슬롯은 하나뿐이고 재무장하지 않는다. P-SC 의 order_state_unknown 중단은 사람이
# 장부를 봐야 하는 상태이고, 그 위에 다시 주문을 올리는 것이 이 러너가 하지
# 말아야 할 단 하나의 일이다.
#
# ⚠ 실행 전 운영자가 직접 채워야 하는 값 2개가 아래 <CHANGE_ME> 로 남아 있다:
#   PSC_EXPECT_KEY_FP     = printf '%s' "$KIS_STOCK_APP_KEY" | sha256sum | cut -c1-12
#   PSC_EXPECT_ACCOUNT_FP = python -c 'import os;from tools.broker_probes.common \
#                             import account_fingerprint;\
#                             print(account_fingerprint(os.environ["KIS_STOCK_ACCOUNT_NO"]))'
# 둘 다 .env.mock 의 **주식** 자격증명에서 나온다. 템플릿이 프로브 시작 전에
# 대조하며, 어긋나면 ABORT 한다 — 2026-09-23 INVALID_CHECK_ACNO 사고는 전파
# 지연이 아니라 이전 계좌에 묶인 키였다.
#
# 자기 자신을 지우지 않는다. 크론 줄은 템플릿(PSC_CRON_MARK)이 지우고, 템플릿이
# 지우지 못한 경우에만 아래 disarm 이 해제한다 — 일회성 날짜 슬롯이라 남겨 두면
# 2027-11-02 에 다시 발화한다. **모든 조기 종료 경로가 disarm 을 거친다.**
set -u

MAIN=/home/deploy/project/kis_unified_sts
W=/home/deploy/.local/state/kis/wt-p-sc-20261102
LOG=/home/deploy/.config/kis-probes/p-sc-20261102.log
EVID=/home/deploy/.local/state/kis/p-sc-evidence   # 내구 호스트 경로; 캠페인 README 편입은 수동
CRON_MARK=run-p-sc-20261102

# 셀프테스트는 **첫 줄을 찍기 전에** 갈라진다. 실행 로그에는 한 글자도 쓰지
# 않는다: summarize() 가 LOG 에서 ' VERDICT: ' 의 마지막 줄을 집으므로 가짜
# 한 줄이 남으면 당일 ABORT 때 그 가짜가 보고된다.
SELFTEST=0
if [ "${1:-}" = "--selftest" ]; then
  SELFTEST=1
  LOG=${PSC_SELFTEST_LOG:-${LOG%.log}-selftest.log}
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
  if crontab -l 2>/dev/null | grep -Fq -- "$CRON_MARK"; then
    crontab -l 2>/dev/null | grep -Fv -- "$CRON_MARK" | crontab - &&
      log "crontab: '$CRON_MARK' 줄 해제(래퍼) — 일회성 슬롯이라 남기면 2027 에 재발화한다"
  else
    log "crontab: '$CRON_MARK' 줄 없음(템플릿이 이미 해제했거나 처음부터 없었다)"
  fi
}

# $1 = 아티팩트를 찾을 results 디렉터리. VERDICT·flat 경고·아티팩트 목록을 조립한다.
summarize() {
  local resdir arts verdict flatwarn
  resdir=$1
  # shellcheck disable=SC2012  # 하네스가 만든 <ID>-<UTC>Z.json 이름뿐 (공백·개행 없음)
  arts=$(ls -t "$resdir"/P-SC-*.json 2>/dev/null | head -5 | xargs -r -n1 basename | tr '\n' ' ')
  [ -n "$arts" ] || arts="(none)"
  verdict=$(grep -F ' VERDICT: ' "$LOG" 2>/dev/null | tail -1 | cut -c1-600)
  [ -n "$verdict" ] || verdict="(VERDICT 줄 없음 — 템플릿이 프로브 호출에 닿기 전에 ABORT 했다)"
  flatwarn=$(grep -F 'NOT verified flat' "$LOG" 2>/dev/null | tail -1 | cut -c1-300)
  printf '%s\n' "$verdict"
  [ -n "$flatwarn" ] && printf '⚠ %s\n' "$flatwarn"
  printf 'artifacts: %s\n' "$arts"
  return 0
}

# 로그 디렉터리가 먼저다. 없으면 log() 의 tee 가 조용히 실패해 모든 줄이
# cron stdout 으로만 흘러간다 — 「시도가 사라졌다」는 모양 그 자체다.
# 실패해도 disarm 은 거쳐야 한다.
if ! mkdir -p -- "$(dirname -- "$LOG")"; then
  printf 'ABORT: 로그 디렉터리 생성 실패 %s\n' "$(dirname -- "$LOG")"
  disarm
  exit 2
fi

# 자기 sha256 — 호스트 파일이 실행되는 것이고 저장소의 instances/ 사본은 기록이다.
log "=== 래퍼 $0 sha256=$(sha256sum -- "$0" 2>/dev/null | cut -d' ' -f1 || echo UNKNOWN)"

mkdir -p "$EVID" || {
  log "ABORT: evidence dir 생성 실패 $EVID"
  disarm
  exit 2
}

# --- selftest: 브로커도 git 도 건드리지 않고 summarize + notify 만 돌린다 ----
if [ "$SELFTEST" = "1" ]; then
  log "=== SELFTEST (브로커 호출 없음, 워크트리 없음, crontab 손대지 않음) log=$LOG"
  SELF_RES=${2:-$EVID}
  SUM=$(summarize "$SELF_RES")
  log "selftest summary ↓"
  printf '%s\n' "$SUM" | tee -a "$LOG"
  notify "[SELFTEST] P-SC 1회차(2026-11-02 10:30 KST, 005930) 예약 점검 — 실제 실행 아님
$SUM
로그 $LOG"
  log "=== SELFTEST 끝"
  exit 0
fi

log "=== P-SC 1회차 무인 실행 시작 (005930 · 모의 주식 · 실주문 0)"
git -C "$MAIN" fetch -q origin || { log "ABORT: git fetch failed"; disarm; notify "P-SC 1회차 ABORT: git fetch failed"; exit 2; }
if [ -d "$W" ]; then git -C "$MAIN" worktree remove --force "$W" 2>/dev/null || rm -rf "$W"; fi
git -C "$MAIN" worktree add -q --detach "$W" origin/main || { log "ABORT: worktree add failed"; disarm; notify "P-SC 1회차 ABORT: worktree add failed"; exit 2; }
log "worktree $W at $(git -C "$W" rev-parse --short HEAD)"

export PSC_PYTHON="$MAIN/.venv/bin/python"
export PSC_LOG="$LOG"
export PSC_CREDENTIAL_FILE=.env.mock         # 상대경로 → 워크트리; gitignore 확인 뒤 주 체크아웃에서 복사
export PSC_SYMBOL=005930                     # 삼성전자 — 모의 주식 계좌에서 P-11 이 쓴 종목
export PSC_TRIAL=both                        # A 쉬는 주문 취소 + B 부분체결 시도
# ⚠ 비워 둔 채로 커밋한다. 템플릿의 require_env 가 「required env … is unset」로
# ABORT 하므로, 운영자가 채우지 않은 슬롯은 **브로커를 건드리기 전에** 멈춘다.
# 자리표시자 문자열을 넣어 두면 대신 「fingerprint mismatch」로 멈추는데, 그것은
# 「아직 안 채웠다」와 「다른 계좌의 키다」를 같은 메시지로 만든다.
export PSC_EXPECT_KEY_FP=""                  # .env.mock 의 **주식** 앱키 지문 (위 헤더의 명령)
export PSC_EXPECT_ACCOUNT_FP=""              # 모의 **주식** 계좌 지문 (위 헤더의 명령)
export PSC_TOKEN_CACHE=/home/deploy/.config/kis-probes/p-sc-20261102-token-cache
export PSC_EVIDENCE_DIR="$EVID"
export PSC_CRON_MARK="$CRON_MARK"            # 프로브가 실제로 돈 뒤에만 템플릿이 지운다
# PSC_CONFIG 는 일부러 설정하지 않는다 — 기본
# config/broker_probes/stock_cancel_probe.yaml 이 그날의 한도이고, 그 파일이
# 워크트리의 origin/main 커밋에 들어 있으므로 아티팩트의 repo_commit 이 곧
# 「어떤 한도로 돌았는가」의 증거가 된다.
export PSC_NOTE="P-SC trial 1 (unattended host cron 2026-11-02 10:30 KST): #948 step 1 — measure the stock MOCK cancel row shape (cncl_yn flag vs a separate row whose orgn_odno points at the original) and whether a fill can land after the cancel ack. Mock stock account, real orders 0. Chosen for a day with no stock MOCK session so the shared mock account is flat. Tracked runner template run_p_sc.sh + probes_stock_cancel (policy p-sc-cancel-shape/1) from a detached origin/main worktree; limits from config/broker_probes/stock_cancel_probe.yaml"

"$W/tools/broker_probes/runners/run_p_sc.sh"
rc=$?
log "=== 템플릿 종료 rc=$rc"

disarm
SUM=$(summarize "$W/tools/broker_probes/results")
printf '%s\n' "$SUM" >>"$LOG"
notify "P-SC 1회차(2026-11-02, 005930) 무인 실행 종료 rc=$rc
$SUM
증거 사본: $EVID (캠페인 README 편입은 수동)
워크트리 $W (results/ 보존)
로그 $LOG"
exit $rc
