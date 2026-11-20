#!/usr/bin/env bash
# CP-3 주식 MOCK tenant 장중 재시작 — 정지 → 평탄 확인(GET) → 잎 보관 → origin/main 새 워크트리로 시작.
#
# 런북 docs/runbooks/tos-paper-boot.md §7.2-f «장중 모의 tenant 재시작» 의 정본.
# 시험: tests/tools/test_cp3_ops_restart.py (스크래치 · 가짜 값 · 브로커 호출 0).
# 운영자 상시 승인 2026-11-20: 모의 tenant 는 장중에 묻지 않고 고친다(커널 코드만 15:40 뒤).
#
# 사용법:
#   CP3_EXPECT_ACCOUNT_FP=<지문> bash tools/tos_cp3/ops/restart_stock_tenant.sh <종목> [태그]
#   bash tools/tos_cp3/ops/restart_stock_tenant.sh <종목> [태그] --expect-account-fingerprint <지문>
# <태그> 는 보관되는 잎 이름에만 들어간다(기본 restart) — 왜 치웠는지가 디렉터리 이름에 남는다.
#
# 무엇을 하는가 (하나라도 어긋나면 멈추고, 그때까지 치운 것은 없다):
#   1. 지문·종목·주 체크아웃 확인. 모의 계좌 지문이 없으면 rc 2 — 여기까지 아무것도 건드리지 않는다.
#   2. 오늘 이 tenant 의 살아 있는 run 전부 TERM. pid 는 /proc 로 신원을 확인하고 보내며(pid 재사용),
#      기다리는 상한은 러너의 정지 상수 합에서 **읽는다**(아래 STOP_WAIT_S).
#   3. 평탄 확인(GET 전용 · mock_flat_check.py). 보유가 있거나 **미체결 주문이 남아 있거나** 읽지
#      못하면 rc 2 로 끝내고 **잎을 그대로 둔다** — 포지션이 열린 잎을 보관하면 그 포지션은 어느
#      증거 사슬의 것도 아니게 된다. 보유는 mock_flatten.py 로, 미체결 주문은 모의투자 HTS 에서
#      취소한 뒤(런타임에 취소가 없다 · #948) 이 스크립트를 다시 돌린다.
#   4. 잎을 `<data>/archive/<종목>.<태그>-<날짜>-<시각>` 으로 **옮긴다**(지우지 않는다).
#   5. origin/main 새 detached 워크트리 · 다음 run 번호 · 그날 정지 시각(달력에서 읽는다).
#   6. **러너를 띄우기 전에** 상시 승인 파일을 approvals-archive/ 로 옮긴다. 런타임은 부팅 시점에
#      그 경로에 있던 것을 결속하므로(bind_at_boot), 나중에 쓰면 `digest_changed_since_bound` 로
#      거부되고 그 세션은 송신 0 이다.
#   7. 세션 시작 → `render ok` 를 기다려 그날 상시 승인을 쓴다. 승인은 렌더된 설정의 코드 digest 에
#      묶이므로 머지 뒤의 옛 승인은 `code_digest_mismatch` 다 — 그래서 재시작마다 다시 쓴다.
#
# rc: 0 시작됨 · 1 실패(정지 안 됨 · fetch · 워크트리 · 달력) · 2 거부(지문·종목·평탄 아님) ·
#     4 세션이 `render ok` 전에 끝났다(승인 없음 = 송신 0).
#
# 환경 (cp3_tenant_daily.sh 와 같은 이름·기본값을 쓴다 — 새 이름을 만들지 않는다):
#   CP3_EXPECT_ACCOUNT_FP            모의 주식 계좌 지문. 필수 · 프로브 러너의 *_EXPECT_ACCOUNT_FP 와 같은 꼴
#   CP3_DAILY_MAIN                   주 체크아웃(.venv · .env.mock · git)  기본 /home/deploy/project/kis_unified_sts
#   CP3_DAILY_STATE                  상주 상태 루트                        기본 $HOME/.local/state/tos
#   CP3_DAILY_STOP_AT                정지 시각 강제(HH:MM). 비우면 그 트리의 달력에서 읽는다(#924 지연일 포함)
#   CP3_DAILY_STOP_AFTER_CLOSE_MIN   종료 + 분 (기본 10 — 러너와 같은 값)
#   CP3_DAILY_APPROVAL_WAIT_TRIES    `render ok` 대기 횟수 (기본 120)
#   CP3_DAILY_APPROVAL_WAIT_SLEEP_S  그 간격 초 (기본 10)
#   TOS_ENV_MOCK                     .env.mock 자리 (기본 $CP3_DAILY_MAIN/.env.mock)
#
# 코드(python 헬퍼 · 종목 집합)는 **이 스크립트가 있는 트리**에서 돌고, 세션은 origin/main 새
# 워크트리에서 돈다. 일부러 다르다: 고친 판을 손으로 돌리면서도 세션은 머지된 판만 띄운다.
# 비밀값은 찍지 않는다 — 계좌 지문은 비가역 12자이고 키·토큰·계좌번호는 어디에도 나오지 않는다.
set -euo pipefail
umask 077

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P) || exit 2
# 이 스크립트가 있는 트리의 루트. 워크트리에서도 그 워크트리를 가리킨다.
REPO=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null) ||
  REPO=$(CDPATH='' cd -- "$SCRIPT_DIR/../../.." && pwd -P)

MAIN=${CP3_DAILY_MAIN:-/home/deploy/project/kis_unified_sts}
ST=${CP3_DAILY_STATE:-$HOME/.local/state/tos}
PY=$MAIN/.venv/bin/python
ENV_MOCK=${TOS_ENV_MOCK:-$MAIN/.env.mock}
STOP_AFTER_CLOSE_MIN=${CP3_DAILY_STOP_AFTER_CLOSE_MIN:-10}
WAIT_TRIES=${CP3_DAILY_APPROVAL_WAIT_TRIES:-120}
WAIT_SLEEP_S=${CP3_DAILY_APPROVAL_WAIT_SLEEP_S:-10}

log() { printf '%s [restart %s] %s\n' "$(TZ=Asia/Seoul date '+%F %T')" "${SYM:-?}" "$*"; }
die() { log "FAIL rc=$1 — $2"; exit "$1"; }

# ── 1. 인자 · 지문 · 종목 ──────────────────────────────────────────────────
SYM=
TAG=
EXPECT_FP=${CP3_EXPECT_ACCOUNT_FP:-}
USAGE="사용법: $0 <6자리 종목> [태그] [--expect-account-fingerprint <지문>]"
while [ $# -gt 0 ]; do
  case "$1" in
  --expect-account-fingerprint)
    [ $# -ge 2 ] || { echo "$USAGE" >&2; exit 2; }
    EXPECT_FP=$2
    shift 2
    ;;
  -h | --help) echo "$USAGE"; exit 0 ;;
  -*) echo "알 수 없는 선택지 '$1'. $USAGE" >&2; exit 2 ;;
  *)
    if [ -z "$SYM" ]; then SYM=$1
    elif [ -z "$TAG" ]; then TAG=$1
    else echo "인자가 너무 많다. $USAGE" >&2; exit 2
    fi
    shift
    ;;
  esac
done
TAG=${TAG:-restart}
case "$SYM" in
[0-9][0-9][0-9][0-9][0-9][0-9]) ;;
*) echo "ERROR: 종목이 6자리 숫자가 아니다. $USAGE" >&2; exit 2 ;;
esac
case "$TAG" in
*[!A-Za-z0-9._-]*) echo "ERROR: 태그는 영숫자·._- 만 (보관 디렉터리 이름이 된다)" >&2; exit 2 ;;
esac
# 모의 계좌 지문은 **먼저** 요구한다 — 없으면 세션을 멈추기도 전에 거부한다(fail closed).
# 지문 자체는 비밀이 아니다(계좌번호의 sha256 앞 12자). 모르면 런북 §7.2-f 의 명령으로 구한다.
[ -n "$EXPECT_FP" ] ||
  { echo "ERROR: CP3_EXPECT_ACCOUNT_FP(또는 --expect-account-fingerprint)가 필요하다 — 어느 계좌를 읽어도 되는지 추측하지 않는다. 런북 §7.2-f" >&2; exit 2; }

# 종목 집합과 호스트 경로 예외는 **러너가 정본**이다 (setup_stock_mock_once.sh 와 같은 읽기).
RUNNER=$SCRIPT_DIR/../runners/cp3_tenant_daily.sh
[ -f "$RUNNER" ] || { echo "ERROR: $RUNNER 가 없다 — 종목 집합을 읽을 수 없다" >&2; exit 2; }
read_runner() { sed -n "s/^$1=\"\{0,1\}\([^\"]*\)\"\{0,1\}\$/\1/p" "$RUNNER" | head -1; }
STOCK_SYMBOLS=$(read_runner STOCK_SYMBOLS)
STOCK_LEGACY_SYMBOL=$(read_runner STOCK_LEGACY_SYMBOL)
if [ -z "$STOCK_SYMBOLS" ] || [ -z "$STOCK_LEGACY_SYMBOL" ]; then
  echo "ERROR: $RUNNER 에서 STOCK_SYMBOLS / STOCK_LEGACY_SYMBOL 을 읽지 못했다" >&2
  exit 2
fi
case " $STOCK_SYMBOLS " in
*" $SYM "*) ;;
*) echo "ERROR: $SYM 은 러너의 tenant 가 아니다 — STOCK_SYMBOLS 는 '$STOCK_SYMBOLS' 다" >&2; exit 2 ;;
esac

# 005930 만 호스트 경로에 종목이 없다 (2026-11-06 에 태어난 배포 그대로 · 러너의 같은 예외).
SUF=""
[ "$SYM" = "$STOCK_LEGACY_SYMBOL" ] || SUF="-$SYM"
LC=stock$SUF

[ -x "$PY" ] || die 2 "$PY 가 없다 (주 체크아웃 = CP3_DAILY_MAIN=$MAIN)"
[ -f "$ENV_MOCK" ] || die 2 "$ENV_MOCK 가 없다 (TOS_ENV_MOCK)"
[ -d "$ST/cp3-sessions" ] || die 2 "$ST/cp3-sessions 가 없다 (CP3_DAILY_STATE=$ST)"

# 정지 상한도 **세션 러너가 정본이다** — 120 을 여기에 또 적지 않는다. run_tenant_session.sh 의
# 정지 경로는 차례로 run(SIGKILL_AFTER_S) → producer(PRODUCER_SIGKILL_AFTER_S) →
# band(BAND_PROCESS_KILL_AFTER_S) → 대기자(stop_wait 의 5s)이고, 그 합이 TERM 한 번이 끝나는
# 데 걸릴 수 있는 최대다. 셋 중 하나라도 못 읽으면 추측하지 않고 거부한다(아직 아무것도 안 건드렸다).
SESSION_RUNNER=$SCRIPT_DIR/../runners/run_tenant_session.sh
[ -f "$SESSION_RUNNER" ] || die 2 "$SESSION_RUNNER 가 없다 — 정지 상한을 읽을 수 없다"
read_stop_const() { sed -n "s/^$1=\([0-9][0-9]*\)\$/\1/p" "$SESSION_RUNNER" | head -1; }
RUN_KILL_S=$(read_stop_const SIGKILL_AFTER_S)
PRODUCER_KILL_S=$(read_stop_const PRODUCER_SIGKILL_AFTER_S)
BAND_KILL_S=$(read_stop_const BAND_PROCESS_KILL_AFTER_S)
# stop_wait() 의 유예는 상수가 아니라 호출의 리터럴(`stop_supervised "$WAIT_PID" 5`)이다.
WAITER_KILL_S=5
if [ -z "$RUN_KILL_S" ] || [ -z "$PRODUCER_KILL_S" ] || [ -z "$BAND_KILL_S" ]; then
  die 2 "$SESSION_RUNNER 에서 정지 상수(SIGKILL_AFTER_S · PRODUCER_SIGKILL_AFTER_S · BAND_PROCESS_KILL_AFTER_S)를 읽지 못했다"
fi
STOP_WAIT_S=$((RUN_KILL_S + PRODUCER_KILL_S + BAND_KILL_S + WAITER_KILL_S))
STOP_POLL_S=2
STOP_TRIES=$(((STOP_WAIT_S + STOP_POLL_S - 1) / STOP_POLL_S + 1))

TODAY=$(TZ=Asia/Seoul date +%F)
D=${TODAY//-/}
DATA_PARENT=$ST/cp3-setup-d-stock-$SYM-data
CUSTODY_ROOT=$ST/cp3-setup-d-stock$SUF-custody
TRANSPORT_CONFIG=$ST/cp3-setup-d-stock$SUF-ops/kis_mock_transport.yaml
PRODUCER_REL=config/tos_probes/cp3-live-producer-stock-$SYM.yaml
log "트리 코드 $REPO · 주 체크아웃 $MAIN · 상태 $ST · 계좌 지문 $EXPECT_FP"

# ── 2. 오늘 이 tenant 의 run 전부 정지 ────────────────────────────────────
for R in "$ST/cp3-sessions/$LC"-r*-"$D"; do
  [ -f "$R/runner.pid" ] || continue
  P=$(cat "$R/runner.pid")
  kill -0 "$P" 2>/dev/null || continue
  # pid 는 재사용된다. 세션이 죽은 뒤 runner.pid 에 남은 번호를 지금 다른 프로세스가 갖고
  # 있으면, 여기서 TERM 을 보내는 것은 남의 프로세스를 죽이는 것이다. 그래서 보내기 전에
  # /proc 로 신원을 확인하고, 맞지 않으면 **죽이지 않고 건너뛴다**(한 줄 남긴다).
  CMDLINE=$(tr '\0' ' ' <"/proc/$P/cmdline" 2>/dev/null) || CMDLINE=""
  case "$CMDLINE" in
  *run_tenant_session.sh*) ;;
  *)
    log "skip $R (pid $P 는 run_tenant_session.sh 가 아니다 — pid 재사용으로 본다)"
    continue
    ;;
  esac
  # environ 은 같은 사용자의 프로세스만 읽을 수 있다. 읽히면 그 세션 자리까지 맞는지 보고,
  # 못 읽으면 cmdline 확인만으로 간다(읽기 실패를 불일치로 읽지 않는다).
  ENVIRON=$(tr '\0' '\n' <"/proc/$P/environ" 2>/dev/null) || ENVIRON=""
  if [ -n "$ENVIRON" ] && printf '%s\n' "$ENVIRON" | grep -q '^TOS_STOCK_SESSION_ROOT='; then
    printf '%s\n' "$ENVIRON" | grep -qxF "TOS_STOCK_SESSION_ROOT=$R" || {
      log "skip $R (pid $P 의 TOS_STOCK_SESSION_ROOT 가 이 자리가 아니다)"
      continue
    }
  fi
  kill -TERM "$P"
  log "stop sent $R (pid $P · 상한 ${STOP_WAIT_S}s = 러너의 정지 상수 합)"
  for _ in $(seq 1 "$STOP_TRIES"); do kill -0 "$P" 2>/dev/null || break; sleep "$STOP_POLL_S"; done
  kill -0 "$P" 2>/dev/null && die 1 "${STOP_WAIT_S}s 뒤에도 살아 있다: $R (pid $P)"
done

# ── 3. 평탄 확인 — GET 전용. 보유가 있으면 잎을 그대로 두고 멈춘다 ────────
rc=0
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$REPO "$PY" -P \
  -m tools.tos_cp3.ops.mock_flat_check "$SYM" \
  --expect-account-fingerprint "$EXPECT_FP" --env-file "$ENV_MOCK" || rc=$?
[ "$rc" = 0 ] ||
  die 2 "평탄하지 않거나(보유 · 미체결 주문) 읽지 못했다 (mock_flat_check rc=$rc) — 잎을 그대로 두고 재시작하지 않았다.
보유가 있으면 먼저: PYTHONPATH=$REPO $PY -P -m tools.tos_cp3.ops.mock_flatten $SYM --expect-account-fingerprint <지문> --env-file $ENV_MOCK
미체결 주문이 남아 있으면 모의투자 HTS 에서 취소한다 — 런타임에 취소가 없다(#948)"

# ── 4. 잎 보관 (옮긴다 · 지우지 않는다) ───────────────────────────────────
if [ -d "$DATA_PARENT/$SYM" ]; then
  mkdir -p "$DATA_PARENT/archive"
  ARCHIVED=$DATA_PARENT/archive/$SYM.$TAG-$D-$(TZ=Asia/Seoul date +%H%M%S)
  [ -e "$ARCHIVED" ] && die 1 "$ARCHIVED 이 이미 있다 — 덮어쓰지 않는다"
  mv "$DATA_PARENT/$SYM" "$ARCHIVED"
  log "잎 보관: $ARCHIVED (다음 run 이 새 genesis 를 만든다)"
else
  log "잎 $DATA_PARENT/$SYM 이 없다 — 다음 run 이 genesis 다"
fi

# ── 5. run 번호 · origin/main 새 워크트리 · 그날 정지 시각 ────────────────
N=1
while [ -e "$ST/cp3-sessions/$LC-r$N-$D" ]; do N=$((N + 1)); done
SESSION=$ST/cp3-sessions/$LC-r$N-$D
WT=$ST/measure/wt-cp3-$LC-r$N-$D
[ -e "$WT" ] && die 1 "$WT 이 이미 있다 — 거부"
git -C "$MAIN" fetch -q origin || die 1 "git fetch 실패 ($MAIN)"
mkdir -p "$ST/measure"
git -C "$MAIN" worktree add -q --detach "$WT" origin/main || die 1 "worktree add 실패: $WT"
log "워크트리 $WT @ $(git -C "$WT" rev-parse --short=12 HEAD) (detached origin/main)"

# 정지 시각은 **그 트리의 달력**에서 읽는다 — 개장 지연일(#924)에 15:40 을 박아 두면 그날
# 세션이 장중에 멎는다. 러너와 같은 읽기(tools/tos_cp3/session_day.py) · 같은 손잡이.
STOP_AT=${CP3_DAILY_STOP_AT:-}
if [ -z "$STOP_AT" ]; then
  STOP_AT=$(PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$WT "$PY" -P -m tools.tos_cp3.session_day \
    stop-at --producer-config "$WT/$PRODUCER_REL" --repo-root "$WT" --date "$TODAY" \
    --after-close-min "$STOP_AFTER_CLOSE_MIN" 2>&1) || {
    git -C "$MAIN" worktree remove "$WT" 2>/dev/null || true
    die 1 "정지 시각을 $WT/$PRODUCER_REL 의 달력에서 구하지 못했다: $STOP_AT"
  }
  log "stop_at $STOP_AT (달력 + ${STOP_AFTER_CLOSE_MIN}m)"
else
  log "stop_at $STOP_AT (CP3_DAILY_STOP_AT)"
fi

# ── 6. 세션 자리 · 상시 승인 치우기 (러너를 띄우기 **전에**) ──────────────
export TOS_REPO=$WT TOS_PYTHON=$PY TOS_STOCK_SYMBOL=$SYM TOS_STOCK_BOOT_DELAY_S=0 \
  TOS_STOCK_SESSION_ROOT=$SESSION TOS_STOCK_DATA_PARENT=$DATA_PARENT \
  TOS_STOCK_ENV_MOCK=$ENV_MOCK TOS_STOCK_CUSTODY_ROOT=$CUSTODY_ROOT \
  TOS_STOCK_KIS_MOCK_TRANSPORT_CONFIG=$TRANSPORT_CONFIG TOS_STOCK_STOP_AT=$STOP_AT
mkdir -m 700 "$SESSION"
mkdir -p "$CUSTODY_ROOT/approvals-archive"
APPROVAL=$CUSTODY_ROOT/approvals/standing-session.yaml
if [ -f "$APPROVAL" ]; then
  PREV=$CUSTODY_ROOT/approvals-archive/standing-session.$D-r$N-prev-$(TZ=Asia/Seoul date +%H%M%S).yaml
  mv "$APPROVAL" "$PREV"
  log "이전 상시 승인 보관: $PREV"
fi

# ── 7. 시작 ───────────────────────────────────────────────────────────────
cd "$WT"
set -a
# shellcheck source=/dev/null
. tools/tos_cp3/runners/stock-mock-session.env.example
set +a
nohup bash tools/tos_cp3/runners/run_tenant_session.sh >"$SESSION/runner.out" 2>&1 &
RUNNER_PID=$!
echo "$RUNNER_PID" >"$SESSION/runner.pid"
log "시작: $LC r$N pid $RUNNER_PID · 세션 $SESSION"

# 그날 상시 승인은 **렌더된** 설정에 묶인다. 머지 뒤의 옛 승인은 `code_digest_mismatch` 이므로
# 재시작마다 다시 쓴다 — `render ok` 뒤, 첫 진입 전. 대기는 유한하다(기본 20분): 장중 재시작의
# 렌더는 개장 뒤라 몇 분 안에 오고, 걸린 세션에서 이 루프가 운영자 터미널을 영구히 붙잡지 않는다.
# 승인을 손으로 쓰는 **그대로의** 명령. 아래 자동 쓰기가 실패했거나 rc 4 로 끝났을 때 이 한 줄을
# 찍는다 — 운영자가 런북을 찾아 조립하지 않도록, 실제로 돌릴 수 있는 꼴로.
approval_cmd() {
  printf '%s\n' "cd $WT && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tos/runtime/src:tos/src $PY -c 'import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))' write-standing-approval --config-dir $SESSION/render --custody-root $CUSTODY_ROOT --environment-label paper --trading-date $TODAY"
}

i=0
while [ "$i" -lt "$WAIT_TRIES" ]; do
  grep -q 'render ok' "$SESSION/session.log" 2>/dev/null && break
  kill -0 "$RUNNER_PID" 2>/dev/null || break
  sleep "$WAIT_SLEEP_S"
  i=$((i + 1))
done
if ! grep -q 'render ok' "$SESSION/session.log" 2>/dev/null; then
  if kill -0 "$RUNNER_PID" 2>/dev/null; then
    log "복구 — 'render ok' 가 $SESSION/session.log 에 뜬 뒤 이 줄 그대로:"
    log "  $(approval_cmd)"
    die 4 "$((WAIT_TRIES * WAIT_SLEEP_S))s 안에 'render ok' 가 없다 — 승인을 쓰지 않았다(송신 0). 세션은 그대로 둔다: $SESSION/session.log"
  fi
  die 4 "세션이 'render ok' 전에 끝났다 — 승인 없음(송신 0): $SESSION/runner.out"
fi
arc=0
(
  cd "$WT" &&
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tos/runtime/src:tos/src "$PY" -c \
      'import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))' \
      write-standing-approval --config-dir "$SESSION/render" \
      --custody-root "$CUSTODY_ROOT" --environment-label paper --trading-date "$TODAY"
) >"$SESSION/approval.out" 2>&1 || arc=$?
log "write-standing-approval rc=$arc ($SESSION/approval.out)"
if [ "$arc" != 0 ]; then
  log "복구 — 고친 뒤 이 줄 그대로(쓰다 만 파일이 이미 있으면 끝에 --replace):"
  log "  $(approval_cmd)"
  die 1 "상시 승인 쓰기 실패 rc=$arc — 승인 없이는 송신 0 ($SESSION/approval.out)"
fi
log "완료 — 볼 것: $SESSION/session.log (band line ok · === BOOT) · sts tos status"
