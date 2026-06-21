"""Tests for KIS WS PINGPONG keepalive detection + feed echo wiring.

Regression for the production incident: KIS keys the PINGPONG keepalive frame by
``header.tr_id == "PINGPONG"`` (per KIS reference kis_auth.py), but the feeds
checked ``header.tr_cd`` — a field KIS never sends — so the echo never fired and
KIS idle-closed the socket every ~105s, churning reconnects into an IP block.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from shared.kis.auth import KISAuthConfig
from shared.kis.stock_feed import KISStockPriceFeed
from shared.kis.websocket import KISWebSocketAdapter
from shared.kis.ws_keepalive import is_pingpong


class TestIsPingpong:
    def test_detects_real_kis_tr_id_field(self):
        # The authoritative KIS frame: {"header":{"tr_id":"PINGPONG",...}}
        assert is_pingpong({"tr_id": "PINGPONG", "datetime": "20220830144632"})

    def test_detects_legacy_tr_cd_field(self):
        # Back-compat / regression guard: a stray tr_cd must still be honored.
        assert is_pingpong({"tr_cd": "PINGPONG"})

    def test_non_pingpong_header(self):
        assert not is_pingpong({"tr_id": "H0STCNT0"})

    def test_empty_or_none_header(self):
        assert not is_pingpong({})
        assert not is_pingpong(None)


def _stock_feed() -> KISStockPriceFeed:
    return KISStockPriceFeed(
        config=KISAuthConfig(app_key="k", app_secret="s", is_real=True)
    )


class TestStockFeedPingpongEcho:
    def test_echoes_pingpong_on_real_tr_id(self):
        feed = _stock_feed()
        feed._ws = MagicMock()
        feed._connected.set()

        frame = {"header": {"tr_id": "PINGPONG", "datetime": "20220830144632"}}
        feed._handle_json(frame)

        feed._ws.send.assert_called_once()
        # Echo must be the verbatim frame KIS expects back.
        sent = json.loads(feed._ws.send.call_args[0][0])
        assert sent == frame

    def test_does_not_echo_non_pingpong(self):
        feed = _stock_feed()
        feed._ws = MagicMock()
        feed._connected.set()

        feed._handle_json({"header": {"tr_id": "H0STCNT0"}, "body": {}})
        feed._ws.send.assert_not_called()


class TestFuturesAdapterPingpongEcho:
    def test_echoes_pingpong_on_real_tr_id(self):
        adapter = KISWebSocketAdapter(
            KISAuthConfig(app_key="k", app_secret="s", is_real=True)
        )
        adapter._set_connected(True)
        adapter.ws = MagicMock()

        raw = '{"header":{"tr_id":"PINGPONG","datetime":"20220830144632"},"body":{}}'
        adapter._process_message(raw)

        adapter.ws.send.assert_called_once()
        sent = json.loads(adapter.ws.send.call_args[0][0])
        assert sent["header"]["tr_id"] == "PINGPONG"
