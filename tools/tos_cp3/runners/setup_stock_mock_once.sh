#!/usr/bin/env bash
# CP-3 주식 MOCK 세션(005930) 1회 준비 — 런북 docs/runbooks/tos-paper-boot.md §7.2-f «1회 준비» 의 정본.
# 시험: tests/tools/test_setup_stock_mock_once.py (스크래치 · 가짜 값). TOS_STATE_ROOT / TOS_ENV_MOCK 로 자리를 바꾼다.
# 사용법:  bash setup_stock_mock_once.sh            # 점검만(dry-run): 무엇을 만들지 보여 주고 아무것도 쓰지 않는다
#          bash setup_stock_mock_once.sh --apply    # 실제로 만든다
# 비밀값(키·시크릿·계좌번호)은 화면에 찍지 않는다. 이미 있는 파일은 덮어쓰지 않고 멈춘다.
set -euo pipefail
umask 077

APPLY=0; [[ "${1:-}" == "--apply" ]] && APPLY=1
ST="${TOS_STATE_ROOT:-$HOME/.local/state/tos}"
MAIN="/home/deploy/project/kis_unified_sts"
ENV_MOCK="${TOS_ENV_MOCK:-$MAIN/.env.mock}"
DATA="$ST/cp3-setup-d-stock-005930-data"
OPS="$ST/cp3-setup-d-stock-ops"
C="$ST/cp3-setup-d-stock-custody"
TRANSPORT="$OPS/kis_mock_transport.yaml"

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
say "데이터 잎 $DATA/005930 은 만들지 않는다 — 월요일 첫 run(genesis)이 만든다"

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
token_reissue_min_interval_s: 60   # 미실측 제안값 (N-15) — 런북 §4
request_timeout_s: 10
allow_plaintext_for_tests: false
YAML
chmod 600 "$TRANSPORT"

# ── 4. 확인 (값은 찍지 않는다) ─────────────────────────────────────────────
echo; echo "완료. 확인:"
stat -c '  %a %n' "$DATA" "$OPS" "$C" "$C/approvals" "$TRANSPORT" "$C"/kis_mock.app_* "$C/custody.manifest.yaml"
for f in kis_mock.app_key kis_mock.app_secret; do
  [[ -s "$C/$f" ]] && ! grep -q '"' "$C/$f" && say "$f: 비어 있지 않음 · 따옴표 없음" || die "$f 이상"
done
echo "다음: 월요일 장전 상시 승인 작성 → 08:55 런북 §7.2-f 시작 블록 (첫 run = genesis, 되돌릴 수 없음)"
