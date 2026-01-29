#!/bin/bash
# WebSocket 실시간 선물 데이터 수집기 관리 스크립트
#
# crontab 예시:
#   # 장 시작 전 WebSocket 시작 (08:45)
#   45 8 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/websocket.sh start
#   # 장 종료 후 WebSocket 중지 (16:05)
#   5 16 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/websocket.sh stop
#
# 사용법:
#   ./scripts/cron/websocket.sh start           # 기본 근월물로 시작
#   ./scripts/cron/websocket.sh start 101V01    # 특정 코드로 시작
#   ./scripts/cron/websocket.sh stop            # 중지
#   ./scripts/cron/websocket.sh status          # 상태 확인
#   ./scripts/cron/websocket.sh restart         # 재시작

set -e

PROJECT_DIR="/home/deploy/project/kis_unified_sts"
PID_DIR="$PROJECT_DIR/pids"
PID_FILE="$PID_DIR/websocket.pid"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/websocket_$(date +%Y%m%d).log"
VENV="$PROJECT_DIR/.venv/bin/activate"

# 디렉토리 생성
mkdir -p "$PID_DIR" "$LOG_DIR"

# 환경 로드
cd "$PROJECT_DIR"
source "$VENV"

# 거래일 확인 함수
is_trading_day() {
    python3 -c "
from datetime import date
from shared.collector.historical.calendar import is_trading_day
print('1' if is_trading_day(date.today()) else '0')
" 2>/dev/null || echo "0"
}

# 프로세스 실행 확인
is_running() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# 시작
start() {
    local codes="$@"

    # 거래일 체크
    IS_TRADING_DAY=$(is_trading_day)
    if [ "$IS_TRADING_DAY" != "1" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 오늘은 휴장일입니다. WebSocket 시작 스킵." | tee -a "$LOG_FILE"
        exit 0
    fi

    # 이미 실행 중인지 확인
    if is_running; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WebSocket collector already running (PID: $(cat "$PID_FILE"))" | tee -a "$LOG_FILE"
        exit 0
    fi

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting WebSocket collector..." | tee -a "$LOG_FILE"

    # 코드 인자 구성
    code_args=""
    if [ -n "$codes" ]; then
        for code in $codes; do
            code_args="$code_args -c $code"
        done
    fi

    # 백그라운드 실행
    nohup sts websocket start $code_args >> "$LOG_FILE" 2>&1 &
    local pid=$!

    # PID 저장
    echo "$pid" > "$PID_FILE"

    # 프로세스 시작 확인
    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WebSocket collector started (PID: $pid)" | tee -a "$LOG_FILE"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Failed to start WebSocket collector" | tee -a "$LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# 중지
stop() {
    if ! is_running; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WebSocket collector not running" | tee -a "$LOG_FILE"
        rm -f "$PID_FILE"
        exit 0
    fi

    local pid=$(cat "$PID_FILE")
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Stopping WebSocket collector (PID: $pid)..." | tee -a "$LOG_FILE"

    # SIGTERM 전송
    kill -TERM "$pid" 2>/dev/null || true

    # 종료 대기
    local timeout=30
    local count=0
    while kill -0 "$pid" 2>/dev/null && [ $count -lt $timeout ]; do
        sleep 1
        count=$((count + 1))
    done

    # 여전히 실행 중이면 SIGKILL
    if kill -0 "$pid" 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Force killing WebSocket collector..." | tee -a "$LOG_FILE"
        kill -KILL "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WebSocket collector stopped" | tee -a "$LOG_FILE"
}

# 상태 확인
status() {
    if is_running; then
        local pid=$(cat "$PID_FILE")
        echo "WebSocket collector: Running (PID: $pid)"

        # 프로세스 정보
        ps -p "$pid" -o pid,ppid,etime,args --no-headers 2>/dev/null || true

        # Redis 스트림 정보
        python3 -c "
from shared.streaming.client import RedisClient
try:
    client = RedisClient.get_client()
    info = client.xinfo_stream('raw_data')
    print(f'  Stream Length: {info.get(\"length\", \"N/A\")}')
except Exception as e:
    print(f'  Stream: Unable to query ({e})')
" 2>/dev/null || echo "  Stream: Unable to query"

    else
        echo "WebSocket collector: Not running"
    fi
}

# 재시작
restart() {
    stop
    sleep 2
    start "$@"
}

# 헬스체크 (cron용)
healthcheck() {
    # 거래일이 아니면 스킵
    IS_TRADING_DAY=$(is_trading_day)
    if [ "$IS_TRADING_DAY" != "1" ]; then
        exit 0
    fi

    # 장시간인지 확인 (09:00 ~ 15:30)
    current_hour=$(date +%H)
    current_min=$(date +%M)
    current_time=$((current_hour * 60 + current_min))

    # 08:45 ~ 15:35 사이에만 체크
    if [ $current_time -lt 525 ] || [ $current_time -gt 935 ]; then
        exit 0
    fi

    # 실행 중이 아니면 재시작
    if ! is_running; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WebSocket collector not running, restarting..." | tee -a "$LOG_FILE"
        start
    fi
}

# 메인
case "${1:-status}" in
    start)
        shift
        start "$@"
        ;;
    stop)
        stop
        ;;
    restart)
        shift
        restart "$@"
        ;;
    status)
        status
        ;;
    healthcheck)
        healthcheck
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|healthcheck} [futures_codes...]"
        exit 1
        ;;
esac
