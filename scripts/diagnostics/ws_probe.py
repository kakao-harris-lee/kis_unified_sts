#!/usr/bin/env python3
"""KIS WebSocket diagnostic probe — reproduce and characterise the connect→reset.

Runs a SINGLE raw WebSocket attempt (no reconnect loop, no circuit breaker) and
reports exactly what KIS does at each step:

  1. approval-key fetch   (REST POST /oauth2/Approval — succeeds today)
  2. TCP reachability     (raw socket connect to the WS host:port)
  3. WS open              (on_open fired? after how long?)
  4. subscribe            (H0STCNT0 stock / H0IFCNT0 futures — same frame as prod)
  5. first tick / reset   (did any data arrive, or did KIS reset the socket — with
                           the close code/message and elapsed time)

The handshake mirrors ``shared/kis/stock_feed.py`` / ``shared/kis/websocket.py``
so the output is a faithful reproduction to attach to a KIS 고객센터 inquiry.

Run inside a container that already has the KIS env:

    docker compose --env-file .env.paper exec stock-market-ingest \\
        python -m scripts.diagnostics.ws_probe --asset stock --symbol 005930
    docker compose --env-file .env.paper exec trader-futures \\
        python -m scripts.diagnostics.ws_probe --asset futures

Or on the host with the env loaded:

    set -a; . .env.paper; set +a
    .venv/bin/python -m scripts.diagnostics.ws_probe --asset stock

Exit code: 0 if the WS stayed up and ticks arrived; 1 if it reset / no data.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import websocket

KST = ZoneInfo("Asia/Seoul")

# Mirrors shared/kis/stock_feed.py + shared/kis/websocket.py
WS_URL_REAL = "ws://ops.koreainvestment.com:21000"
WS_URL_MOCK = "ws://ops.koreainvestment.com:31000"
TR_STOCK_TRADE = "H0STCNT0"
TR_FUTURES_TRADE = "H0IFCNT0"
TR_FUTURES_ASK = "H0IFASP0"


def _now() -> str:
    return datetime.now(KST).strftime("%H:%M:%S.%f")[:-3]


def _log(msg: str) -> None:
    print(f"[{_now()}] {msg}", flush=True)


def _resolve_auth(asset: str) -> tuple[str, str, bool, str]:
    """Return (app_key, app_secret, is_real, rest_base_url) from env for *asset*."""
    if asset == "stock":
        key = os.environ.get("KIS_STOCK_APP_KEY", "")
        secret = os.environ.get("KIS_STOCK_APP_SECRET", "")
        is_real = os.environ.get("KIS_STOCK_MARKET", "mock").lower() == "real"
    else:
        key = os.environ.get("KIS_FUTURES_APP_KEY", "")
        secret = os.environ.get("KIS_FUTURES_APP_SECRET", "")
        is_real = os.environ.get("KIS_FUTURES_MARKET", "real").lower() == "real"
    if not key or not secret:
        sys.exit(
            f"ERROR: KIS_{asset.upper()}_APP_KEY/SECRET not in env. Run inside a "
            f"container with the KIS env, or `set -a; . .env.paper; set +a` first."
        )
    base = (
        "https://openapi.koreainvestment.com:9443"
        if is_real
        else "https://openapivts.koreainvestment.com:29443"
    )
    return key, secret, is_real, base


def _tcp_check(ws_url: str, timeout: float = 5.0) -> bool:
    host = ws_url.split("://", 1)[1].split(":")[0]
    port = int(ws_url.rsplit(":", 1)[1])
    _log(f"2) TCP connect {host}:{port} ...")
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        _log("   TCP OK (network/firewall fine)")
        return True
    except Exception as e:  # noqa: BLE001 — diagnostic
        _log(f"   TCP FAILED: {e!r}")
        return False


def _get_approval_key(base_url: str, app_key: str, app_secret: str) -> str | None:
    _log("1) Approval key POST /oauth2/Approval ...")
    try:
        resp = requests.post(
            f"{base_url}/oauth2/Approval",
            json={
                "grant_type": "client_credentials",
                "appkey": app_key,
                "secretkey": app_secret,
            },
            headers={"content-type": "application/json"},
            timeout=10,
        )
        data = resp.json()
    except Exception as e:  # noqa: BLE001 — diagnostic
        _log(f"   approval request FAILED: {e!r}")
        return None
    if "approval_key" not in data:
        code = data.get("error_code", data.get("msg_cd", "unknown"))
        _log(f"   approval FAILED: code={code} msg={data.get('msg1', data)}")
        if str(code).startswith("EGW"):
            _log("   ^ EGW = KIS server-side error state (check EGW server info)")
        return None
    _log(f"   approval OK (HTTP {resp.status_code})")
    return str(data["approval_key"])


def _subscribe_frame(approval_key: str, tr_id: str, symbol: str) -> str:
    return json.dumps(
        {
            "header": {
                "approval_key": approval_key,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8",
            },
            "body": {"input": {"tr_id": tr_id, "tr_key": symbol}},
        }
    )


def _futures_symbol() -> str:
    try:
        from shared.collector.historical.futures import get_front_month_code

        return get_front_month_code(product="mini")
    except Exception:  # noqa: BLE001
        return ""


def probe(
    asset: str, symbol: str, duration: float, tr_id: str, trace: bool = False
) -> int:
    app_key, app_secret, is_real, base = _resolve_auth(asset)
    ws_url = WS_URL_REAL if is_real else WS_URL_MOCK
    if trace:
        # Wire-level handshake log: prints the exact HTTP Upgrade request we send
        # and KIS's response (or a bare TCP RST with no response = IP/firewall
        # block rather than an HTTP-level rejection).
        websocket.enableTrace(True)
    _log(
        f"=== KIS WS probe: asset={asset} env={'REAL' if is_real else 'MOCK'} "
        f"symbol={symbol} tr_id={tr_id} ws={ws_url} ==="
    )

    approval = _get_approval_key(base, app_key, app_secret)
    if approval is None:
        _log("VERDICT: approval-key step failed — cannot test the WS.")
        return 1
    _tcp_check(ws_url)

    state: dict[str, object] = {
        "opened_at": None,
        "closed_at": None,
        "close_code": None,
        "close_msg": None,
        "error": None,
        "messages": 0,
        "first_msg": None,
    }
    started = time.monotonic()

    def on_open(ws):  # noqa: ANN001
        state["opened_at"] = time.monotonic() - started
        _log(f"3) WS OPEN after {state['opened_at']*1000:.0f}ms — subscribing {symbol}")
        ws.send(_subscribe_frame(approval, tr_id, symbol))

    def on_message(ws, message):  # noqa: ANN001, ARG001
        state["messages"] = int(state["messages"]) + 1  # type: ignore[arg-type]
        if state["first_msg"] is None:
            state["first_msg"] = message[:160]
            _log(
                f"4) FIRST MESSAGE after {(time.monotonic()-started)*1000:.0f}ms: "
                f"{message[:160]}"
            )

    def on_error(ws, error):  # noqa: ANN001, ARG001
        state["error"] = repr(error)
        _log(f"   WS ERROR: {error!r}")

    def on_close(ws, code, msg):  # noqa: ANN001, ARG001
        state["closed_at"] = time.monotonic() - started
        state["close_code"] = code
        state["close_msg"] = msg
        opened = state["opened_at"]
        since = (
            f"{(state['closed_at']-opened)*1000:.0f}ms after open"  # type: ignore[operator]
            if opened is not None
            else "before open"
        )
        _log(f"   WS CLOSED: code={code} msg={msg} ({since})")

    ws_app = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    # ping_interval=0 mirrors production (KIS uses app-level PINGPONG, not WS ping).
    t = threading.Thread(
        target=ws_app.run_forever, kwargs={"ping_interval": 0}, daemon=True
    )
    t.start()
    _log(f"observing for {duration:.0f}s ...")
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        if state["closed_at"] is not None and state["messages"] == 0:
            break  # reset before any data — no point waiting
        time.sleep(0.5)
    ws_app.close()
    t.join(timeout=3.0)

    # ---- verdict -------------------------------------------------------------
    msgs = int(state["messages"])  # type: ignore[arg-type]
    _log("=== VERDICT ===")
    if msgs > 0:
        _log(f"✅ WS HEALTHY — received {msgs} message(s). KIS WS is working.")
        return 0
    if state["opened_at"] is None:
        _log("❌ WS never opened (KIS refused the upgrade / TCP-level reset).")
    elif state["closed_at"] is not None:
        dur_ms = (
            state["closed_at"] - state["opened_at"]
        ) * 1000  # type: ignore[operator]
        _log(
            f"❌ KIS RESET the session {dur_ms:.0f}ms after open, ZERO ticks "
            f"(close code={state['close_code']}, err={state['error']}). "
            f"This is the account/IP-level WS block — share this with KIS 고객센터."
        )
    else:
        _log("❌ No ticks and no clean close within the window (silent stall).")
    return 1


def main() -> int:
    p = argparse.ArgumentParser(description="KIS WebSocket diagnostic probe")
    p.add_argument("--asset", choices=["stock", "futures"], default="stock")
    p.add_argument(
        "--symbol",
        default="",
        help="override symbol (default: 005930 / front-month mini)",
    )
    p.add_argument(
        "--duration", type=float, default=20.0, help="observe seconds (default 20)"
    )
    p.add_argument(
        "--tr",
        choices=["trade", "orderbook"],
        default="trade",
        help="futures only: trade=H0IFCNT0 (default), orderbook=H0IFASP0",
    )
    p.add_argument(
        "--trace",
        action="store_true",
        help="wire-level WS handshake trace (the bytes sent + KIS's response/RST)",
    )
    args = p.parse_args()

    if args.asset == "stock":
        symbol = args.symbol or "005930"
        tr_id = TR_STOCK_TRADE
    else:
        symbol = args.symbol or _futures_symbol()
        if not symbol:
            return int(
                bool(
                    print(
                        "ERROR: could not resolve a front-month futures code; "
                        "pass --symbol explicitly.",
                        file=sys.stderr,
                    )
                )
                or 2
            )
        tr_id = TR_FUTURES_ASK if args.tr == "orderbook" else TR_FUTURES_TRADE

    return probe(args.asset, symbol, args.duration, tr_id, trace=args.trace)


if __name__ == "__main__":
    sys.exit(main())
