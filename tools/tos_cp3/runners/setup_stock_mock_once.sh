#!/usr/bin/env bash
# CP-3 주식 MOCK 세션 1회 준비 (종목 하나) — 런북 docs/runbooks/tos-paper-boot.md §7.2-f «1회 준비» 의 정본.
# 시험: tests/tools/test_setup_stock_mock_once.py (스크래치 · 가짜 값). TOS_STATE_ROOT / TOS_ENV_MOCK 로 자리를 바꾼다.
# 사용법:  bash setup_stock_mock_once.sh [종목]            # 점검만(dry-run): 무엇을 만들지 보여 주고 아무것도 쓰지 않는다
#          bash setup_stock_mock_once.sh [종목] --apply    # 실제로 만든다
# 종목을 생략하면 러너의 STOCK_LEGACY_SYMBOL — cp3_tenant_daily.sh 의 `STOCK` 과 같은
# 기본값이고, 그 tenant 의 호스트 경로에는 종목이 붙지 않는다(2026-11-06 에 태어난 배포
# 그대로). 종목 집합과 그 예외는 러너에서 읽는다(아래). 다른 종목은
# `…-<종목>-data` · `…-<종목>-ops` · `…-<종목>-custody` 로 자기 자리를 갖는다 —
# **custody 는 절대 공유하지 않는다**: 상시 승인 산출물 경로가 custody 루트 기준 고정이고
# 승인 문서는 그 tenant 의 «렌더된» 설정에 묶이므로, 공유하면 한 tenant 의 부팅이 다른
# tenant 의 승인을 바인드한다.
# 종목마다 한 번씩 돌린다 (운영자 지시 2026-11-19 — 종목당 tenant 하나).
# 비밀값(키·시크릿·계좌번호)은 화면에 찍지 않는다. 이미 있는 파일은 덮어쓰지 않고 멈춘다.
set -euo pipefail
umask 077

# 종목 집합과 예외 종목은 **러너가 정본**이다 — 두 벌로 적으면 한쪽만 고쳐진다.
# 러너에 없는 종목으로 준비해 봐야 그 tenant 는 돌지 않고, 디렉터리만 남는다.
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P) || exit 2
RUNNER="$SCRIPT_DIR/cp3_tenant_daily.sh"
[[ -f "$RUNNER" ]] || { echo "ERROR: $RUNNER 가 없다 — 종목 집합을 읽을 수 없다" >&2; exit 2; }
read_runner() { sed -n "s/^$1=\"\{0,1\}\([^\"]*\)\"\{0,1\}\$/\1/p" "$RUNNER" | head -1; }
STOCK_SYMBOLS=$(read_runner STOCK_SYMBOLS)
STOCK_LEGACY_SYMBOL=$(read_runner STOCK_LEGACY_SYMBOL)
[[ -n "$STOCK_SYMBOLS" && -n "$STOCK_LEGACY_SYMBOL" ]] ||
  { echo "ERROR: $RUNNER 에서 STOCK_SYMBOLS / STOCK_LEGACY_SYMBOL 을 읽지 못했다" >&2; exit 2; }

SYMBOL="$STOCK_LEGACY_SYMBOL"
APPLY=0
for a in "$@"; do
  case "$a" in
  --apply) APPLY=1 ;;
  [0-9][0-9][0-9][0-9][0-9][0-9]) SYMBOL=$a ;;
  *) echo "사용법: $0 [6자리 종목코드] [--apply]   (종목: $STOCK_SYMBOLS)" >&2; exit 2 ;;
  esac
done
case " $STOCK_SYMBOLS " in
*" $SYMBOL "*) ;;
*) echo "ERROR: $SYMBOL 은 러너의 tenant 가 아니다 — $RUNNER 의 STOCK_SYMBOLS 는 '$STOCK_SYMBOLS' 다." >&2
   echo "       트리·생산자 설정·cron 줄을 먼저 올린 뒤에 준비한다 (그 전에는 돌 tenant 가 없다)." >&2
   exit 2 ;;
esac
# 예외 종목만 호스트 경로에 종목이 없다 (위 주석 · 러너의 STOCK_LEGACY_SYMBOL).
HOST_SUFFIX=""
[[ "$SYMBOL" == "$STOCK_LEGACY_SYMBOL" ]] || HOST_SUFFIX="-$SYMBOL"
ST="${TOS_STATE_ROOT:-$HOME/.local/state/tos}"
MAIN="/home/deploy/project/kis_unified_sts"
ENV_MOCK="${TOS_ENV_MOCK:-$MAIN/.env.mock}"
DATA="$ST/cp3-setup-d-stock-$SYMBOL-data"
OPS="$ST/cp3-setup-d-stock${HOST_SUFFIX}-ops"
C="$ST/cp3-setup-d-stock${HOST_SUFFIX}-custody"
TRANSPORT="$OPS/kis_mock_transport.yaml"
# 토큰과 요청 슬롯은 **tenant 별이 아니라 앱 키별**이다 — 모든 주식 tenant 가 같은 파일을 가리킨다.
# KIS 는 앱 키 하나에 분당 토큰 한 장만 내주고 초당 건수도 앱 키로 센다. tenant 셋은 프로세스
# 셋이라 11-20 에 둘 다 터졌다: 12:50 에 005930 이 매번 TokenResponseError → 브로커 사실 None
# → SEND_REFUSED, 13:00~13:20 에는 셋이 제각각 페이싱해 합산 요청률이 모의 한도를 넘어
# VTTC0081R·VTTC8434R 이 HTTP 500(EGW00201) → 증인 미확증 → 모든 CLOSE 가 ZERO_POSITION.
# custody 와 달리 공유가 맞다: 공유하는 것은 승인이 아니라 그 앱 키 자신의 상태다.
TOKEN_CACHE="$ST/kis-mock-token/stock-mock.json"
SHARED_PACER="$ST/kis-mock-token/stock-mock.pace"

die() { echo "ERROR: $*" >&2; exit 1; }
say() { echo "  $*"; }

# ── 0. 전제 점검 ────────────────────────────────────────────────────────────
[[ -d "$ST" ]] || die "$ST 가 없다 (상주 paper 상태 루트)"
[[ -f "$ENV_MOCK" ]] || die "$ENV_MOCK 가 없다"
val() { grep -E "^$1=" "$ENV_MOCK" | tail -1 | cut -d= -f2- | sed -E "s/^['\"]//; s/['\"]$//" | tr -d '\r\n'; }
for k in KIS_STOCK_APP_KEY KIS_STOCK_APP_SECRET KIS_STOCK_ACCOUNT_NO; do
  [[ -n "$(val $k)" ]] || die ".env.mock 에 $k 가 비어 있다"
done
ACCT="$(val KIS_STOCK_ACCOUNT_NO | tr -d '-')"
[[ "$ACCT" =~ ^[0-9]{10}$ ]] || die "KIS_STOCK_ACCOUNT_NO 가 10자리 숫자(8-2)가 아니다"
PRDT="${ACCT:8:2}"     # ACNT_PRDT_CD = 계좌 뒤 2자리 (다르면 코덱이 송신 거부)
echo "점검 OK: .env.mock 에 모의 주식 키·시크릿·계좌(10자리, 8-2) 있음"

for p in "$DATA" "$OPS" "$C"; do
  if [[ -e "$p" ]] && [[ -n "$(ls -A "$p" 2>/dev/null)" ]]; then die "$p 가 이미 있고 비어 있지 않다 — 덮어쓰지 않는다"; fi
done

echo "만들 것:"
say "디렉터리 (700): $DATA  $OPS  $C  $C/approvals"
say "custody 파일 (600): read.principal evidence.key evidence.key.1 replay.params (난수 32B)"
say "custody 파일 (600): kis_mock.app_key kis_mock.app_secret (.env.mock 의 모의 주식 키에서)"
say "custody.manifest.yaml (600): 위 5개 scope"
say "$TRANSPORT (600): mode: live · VTS 호스트 · price_scale 100 · ACNT_PRDT_CD=계좌 뒤 2자리"
say "앱 키 공용 디렉터리 (700): $(dirname "$TOKEN_CACHE") — 토큰 캐시 + 합산 페이서, 주식 tenant 전부 공용"
say "데이터 잎 $DATA/$SYMBOL 은 만들지 않는다 — 첫 거래일 run(genesis)이 만든다"

if [[ $APPLY -eq 0 ]]; then echo; echo "DRY-RUN — 아무것도 쓰지 않았다. 실행하려면 --apply"; exit 0; fi

# ── 1. 디렉터리 ────────────────────────────────────────────────────────────
install -d -m 700 "$DATA" "$OPS" "$C" "$C/approvals"

# ── 2. custody: 난수 4종 + 모의 키 2종 ────────────────────────────────────
for f in read.principal evidence.key evidence.key.1 replay.params; do head -c 32 /dev/urandom >"$C/$f"; done
printf '%s' "$(val KIS_STOCK_APP_KEY)"    >"$C/kis_mock.app_key"
printf '%s' "$(val KIS_STOCK_APP_SECRET)" >"$C/kis_mock.app_secret"
{
  echo "environment_label: paper"
  echo "scopes:"
  for s in read.principal:read-principal-v1 evidence.key:evidence-key-v1 replay.params:replay-params-v1 \
           kis_mock.app_key:kis-mock-order-paper kis_mock.app_secret:kis-mock-order-paper; do
    echo "  ${s%%:*}: {file: ${s%%:*}, principal: ${s##*:}, expected_sha256: null}"
  done
} >"$C/custody.manifest.yaml"
chmod 600 "$C"/*.* "$C"/read.principal "$C"/evidence.key "$C"/replay.params 2>/dev/null || true

# ── 3. kis_mock_transport.yaml (런북 tos-kis-mock-transport.md §4 제안표 + §7.2-f) ──
cat >"$TRANSPORT" <<YAML
# CP-3 주식 MOCK 세션 전송 설정 — setup_stock_mock_once.sh 가 만듦 ($(TZ=Asia/Seoul date '+%F %T KST'))
# 값 근거: docs/runbooks/tos-kis-mock-transport.md §4 · tos-paper-boot.md §7.2-f
mode: live
endpoint_rest_base: "https://openapivts.koreainvestment.com:29443"
order_path: "/uapi/domestic-stock/v1/trading/order-cash"
token_path: "/oauth2/tokenP"
tr_id_buy: "VTTC0012U"
tr_id_sell: "VTTC0011U"
field_map:
  account: "CANO"
  instrument: "PDNO"
  quantity: "ORD_QTY"
  price: "ORD_UNPR"
static_body_fields:
  ACNT_PRDT_CD: "$PRDT"
  ORD_DVSN: "00"
  EXCG_ID_DVSN_CD: "KRX"
  SLL_TYPE: ""
  CNDT_PRIC: ""
price_scale: 100
min_send_interval_ms: 2000              # 앱 키의 모든 요청 간격 (#970 — 주문·토큰·조회 공용)
app_key_request_wait_budget_ms: 4000    # 슬롯 대기 상한 = 2 × 간격 (루프·FETCH 두 스레드, #970)
# 실패 뒤 재발급 대기. 60 이 아니라 65 다 (#1125): 11-20 에 폴링 주기(~60s)와 이 값이 같아
# 재시도가 쿨다운 0.4s 안쪽(59.6s)에 떨어져 번번이 TokenStale 로 버려졌고, 실제로 나간
# 시도는 120s 에 한 번뿐이었다. 65 면 나가는 시도는 반드시 KIS 의 분당 창을 넘긴 뒤다.
token_reissue_min_interval_s: 65
# 앱 키를 공유하는 tenant 프로세스들이 토큰 한 장을 함께 쓰는 파일 (#1125).
# flock 아래에서만 읽고 쓰며, 항목 키는 앱 키의 sha256 이다 — 앱 키 자체는 들어가지 않는다.
token_cache_path: "$TOKEN_CACHE"
# 만료 이 초 전부터 재발급 대상으로 본다. 10분: 토큰 수명(86400s)의 0.7% 이고, 한 번의
# 재발급 실패 + 쿨다운(65s)을 몇 번 더 견딜 수 있는 여유다. 그 사이 재발급이 거부되면
# 아직 유효한 캐시 토큰을 그대로 쓴다(런타임 token.py 의 fallback).
token_cache_refresh_margin_s: 600
# 앱 키를 공유하는 tenant 프로세스들의 **합산** 요청 간격을 정하는 파일 (#1125).
# min_send_interval_ms 는 프로세스 하나의 간격이라, tenant 셋이 같은 순간에 각자 한 건씩
# 보내면 평균은 맞아도 그 1초 안에 3건이다 — 11-20 13:00~13:20 의 HTTP 500(EGW00201).
shared_pacer_path: "$SHARED_PACER"
# 앱 키 전체의 상한. 2.0: P-13 실측에서 스로틀이 관측된 지점이 2.0 rps 이고(런북 §4),
# tenant 셋의 평균 합산(3 × 0.5 = 1.5 rps)은 그 아래로 그대로 들어간다. 바꾸는 것은
# 간격이 아니라 **동시성**이다 — 어떤 두 요청도 0.5s 안에 붙지 않는다.
shared_max_rps: 2.0
# SAFETY: 허가 시각은 요청이 나가기 전에 찍히고 KIS 는 도착을 센다 — TLS 지터(cold 120ms vs warm 20ms)가 이 여유보다 크면 1초에 세 건이 도착한다 (#1155)
shared_window_margin_s: 0.25
request_timeout_s: 10
allow_plaintext_for_tests: false
YAML
chmod 600 "$TRANSPORT"
install -d -m 700 "$(dirname "$TOKEN_CACHE")"

# ── 4. 확인 (값은 찍지 않는다) ─────────────────────────────────────────────
echo; echo "완료. 확인:"
stat -c '  %a %n' "$DATA" "$OPS" "$C" "$C/approvals" "$TRANSPORT" "$C"/kis_mock.app_* "$C/custody.manifest.yaml" \
  "$(dirname "$TOKEN_CACHE")"
for f in kis_mock.app_key kis_mock.app_secret; do
  [[ -s "$C/$f" ]] && ! grep -q '"' "$C/$f" && say "$f: 비어 있지 않음 · 따옴표 없음" || die "$f 이상"
done
echo "다음: 첫 거래일 장전 상시 승인 작성 → 런북 §7.2-f 시작 블록 (첫 run = genesis, 되돌릴 수 없음)."
echo "      cron 이 이미 이 tenant 를 걸고 있으면 그 줄이 상시 승인까지 쓴다 — 손으로 쓸 필요 없다."
