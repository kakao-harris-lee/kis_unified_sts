"""Unit tests for services.night_futures_collector (O9 night close capture).

No real network / Redis: the WS adapter is a fake emitting canned
NightFuturesTrade objects and Redis is fakeredis (sync).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import fakeredis
import pytest

from services.night_futures_collector.config import NightCloseCaptureConfig
from services.night_futures_collector.main import (
    EXIT_CONFIG_ERROR,
    NightCloseCapture,
    build_snapshot_fields,
    main,
    run_capture,
)
from shared.kis.websocket import NightFuturesTrade

KST = ZoneInfo("Asia/Seoul")

CAPTURE_DAY = datetime(2026, 7, 2, 5, 48, 0, tzinfo=KST)


def _trade(
    *,
    ts: float,
    price: float = 412.35,
    trade_time: str | None = "055930",
    symbol: str = "101W9000",
    market_basis: float | None = 0.85,
    disparity_rate: float | None = 0.21,
    open_interest: float | None = 24810.0,
    cumulative_volume: float | None = 5321.0,
) -> NightFuturesTrade:
    return NightFuturesTrade(
        symbol=symbol,
        timestamp=ts,
        trade_time=trade_time,
        price=price,
        open_price=410.0,
        high_price=413.05,
        low_price=409.55,
        tick_volume=1.0,
        cumulative_volume=cumulative_volume,
        market_basis=market_basis,
        disparity_rate=disparity_rate,
        open_interest=open_interest,
    )


class _FakeAdapter:
    """Emits canned trades synchronously inside subscribe_night_trades."""

    def __init__(self, trades: list[NightFuturesTrade] | None = None) -> None:
        self.trades = trades or []
        self.connected = False
        self.disconnected = False
        self.subscribed_symbols: list[str] = []
        self.until: float | None = None

    def connect(self) -> None:
        self.connected = True

    def subscribe_night_trades(self, symbols, callback, *, until=None) -> None:
        self.subscribed_symbols = list(symbols)
        self.until = until
        for trade in self.trades:
            callback(trade)

    def disconnect(self) -> None:
        self.disconnected = True


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------


class TestNightCloseCaptureConfig:
    def test_defaults_match_shipped_yaml_contract(self):
        cfg = NightCloseCaptureConfig()
        assert cfg.enabled is True
        assert cfg.tr_key == "101W9000"
        assert cfg.window_start_kst == "05:50"
        assert cfg.window_end_kst == "06:00"
        assert cfg.redis_key == "market:structure:night_close"
        assert cfg.redis_ttl_seconds == 86400

    def test_from_yaml_absolute_path_reads_section(self, tmp_path):
        yaml_path = tmp_path / "night_futures.yaml"
        yaml_path.write_text(
            "night_close_capture:\n"
            "  enabled: false\n"
            '  tr_key: "101X9000"\n'
            '  window_start_kst: "05:45"\n'
            '  window_end_kst: "05:55"\n'
            '  redis_key: "market:structure:night_close"\n'
            "  redis_ttl_seconds: 3600\n",
            encoding="utf-8",
        )
        cfg = NightCloseCaptureConfig.from_yaml(str(yaml_path))
        assert cfg.enabled is False
        assert cfg.tr_key == "101X9000"
        assert cfg.window_start_kst == "05:45"
        assert cfg.redis_ttl_seconds == 3600

    def test_shipped_repo_yaml_parses(self):
        from pathlib import Path

        repo_yaml = (
            Path(__file__).resolve().parents[3] / "config" / "night_futures.yaml"
        )
        cfg = NightCloseCaptureConfig.from_yaml(str(repo_yaml))
        assert cfg.redis_key == "market:structure:night_close"
        assert cfg.window_start_kst < cfg.window_end_kst

    @pytest.mark.parametrize("bad", ["5:50", "05:5", "24:00", "05:60", "0550", ""])
    def test_invalid_window_time_rejected(self, bad):
        with pytest.raises(ValueError):
            NightCloseCaptureConfig(window_start_kst=bad)

    def test_window_start_must_precede_end(self):
        with pytest.raises(ValueError, match="earlier than"):
            NightCloseCaptureConfig(window_start_kst="06:00", window_end_kst="05:50")

    def test_window_bounds_on_now_date_kst(self):
        cfg = NightCloseCaptureConfig()
        start, end = cfg.window_bounds(CAPTURE_DAY)
        assert start == datetime(2026, 7, 2, 5, 50, 0, tzinfo=KST)
        assert end == datetime(2026, 7, 2, 6, 0, 0, tzinfo=KST)


# ---------------------------------------------------------------------------
# Last-trade selection
# ---------------------------------------------------------------------------


class TestNightCloseCapture:
    def _capture(self) -> NightCloseCapture:
        start, end = NightCloseCaptureConfig().window_bounds(CAPTURE_DAY)
        return NightCloseCapture(start, end)

    def test_trade_before_window_ignored(self):
        cap = self._capture()
        before = datetime(2026, 7, 2, 5, 49, 59, tzinfo=KST).timestamp()
        cap.on_trade(_trade(ts=before))
        assert cap.last_trade is None
        assert cap.trades_seen == 0

    def test_trade_at_or_after_window_end_ignored(self):
        cap = self._capture()
        at_end = datetime(2026, 7, 2, 6, 0, 0, tzinfo=KST).timestamp()
        cap.on_trade(_trade(ts=at_end))
        assert cap.last_trade is None

    def test_last_in_window_trade_wins(self):
        cap = self._capture()
        t1 = datetime(2026, 7, 2, 5, 51, 0, tzinfo=KST).timestamp()
        t2 = datetime(2026, 7, 2, 5, 59, 58, tzinfo=KST).timestamp()
        cap.on_trade(_trade(ts=t1, price=411.0))
        cap.on_trade(_trade(ts=t2, price=412.9))
        cap.on_trade(_trade(ts=t2 + 10.0, price=999.0))  # past end — ignored
        assert cap.trades_seen == 2
        assert cap.last_trade is not None
        assert cap.last_trade.price == 412.9


# ---------------------------------------------------------------------------
# Snapshot fields
# ---------------------------------------------------------------------------


class TestBuildSnapshotFields:
    def test_all_fields_present(self):
        cfg = NightCloseCaptureConfig()
        ts = datetime(2026, 7, 2, 5, 59, 30, tzinfo=KST).timestamp()
        fields = build_snapshot_fields(
            _trade(ts=ts, trade_time="055930"), cfg, CAPTURE_DAY
        )
        assert fields == {
            "close": "412.35",
            "mrkt_basis": "0.85",
            "dprt": "0.21",
            "open_interest": "24810.0",
            "acml_vol": "5321.0",
            "asof_ts": "2026-07-02T05:59:30+09:00",
            "product_code": "101W9000",
        }

    def test_missing_optionals_degrade_to_empty_string(self):
        cfg = NightCloseCaptureConfig()
        ts = datetime(2026, 7, 2, 5, 59, 30, tzinfo=KST).timestamp()
        fields = build_snapshot_fields(
            _trade(
                ts=ts,
                market_basis=None,
                disparity_rate=None,
                open_interest=None,
                cumulative_volume=None,
            ),
            cfg,
            CAPTURE_DAY,
        )
        assert fields["mrkt_basis"] == ""
        assert fields["dprt"] == ""
        assert fields["open_interest"] == ""
        assert fields["acml_vol"] == ""
        assert fields["close"] == "412.35"

    def test_asof_falls_back_to_receive_time_when_no_trade_time(self):
        cfg = NightCloseCaptureConfig()
        ts = datetime(2026, 7, 2, 5, 58, 12, tzinfo=KST).timestamp()
        fields = build_snapshot_fields(_trade(ts=ts, trade_time=None), cfg, CAPTURE_DAY)
        assert fields["asof_ts"] == "2026-07-02T05:58:12+09:00"

    def test_blank_symbol_falls_back_to_config_product_code(self):
        cfg = NightCloseCaptureConfig(product_code="101W9000-cfg")
        ts = datetime(2026, 7, 2, 5, 58, 12, tzinfo=KST).timestamp()
        fields = build_snapshot_fields(_trade(ts=ts, symbol=""), cfg, CAPTURE_DAY)
        assert fields["product_code"] == "101W9000-cfg"


# ---------------------------------------------------------------------------
# run_capture end-to-end (fake adapter + fakeredis)
# ---------------------------------------------------------------------------


class TestRunCapture:
    def _redis(self) -> fakeredis.FakeRedis:
        return fakeredis.FakeRedis(decode_responses=True)

    def test_publishes_last_in_window_trade_with_ttl(self):
        cfg = NightCloseCaptureConfig()
        t1 = datetime(2026, 7, 2, 5, 51, 0, tzinfo=KST).timestamp()
        t2 = datetime(2026, 7, 2, 5, 59, 58, tzinfo=KST).timestamp()
        adapter = _FakeAdapter(
            [
                _trade(ts=t1, price=411.0, trade_time="055100"),
                _trade(ts=t2, price=412.9, trade_time="055958"),
            ]
        )
        redis_client = self._redis()

        rc = run_capture(
            cfg, adapter=adapter, redis_client=redis_client, now=CAPTURE_DAY
        )

        assert rc == 0
        assert adapter.connected and adapter.disconnected
        assert adapter.subscribed_symbols == [cfg.tr_key]
        window_end = datetime(2026, 7, 2, 6, 0, 0, tzinfo=KST)
        assert adapter.until == window_end.timestamp()

        snapshot = redis_client.hgetall(cfg.redis_key)
        assert snapshot["close"] == "412.9"
        assert snapshot["asof_ts"] == "2026-07-02T05:59:58+09:00"
        assert snapshot["product_code"] == "101W9000"
        ttl = redis_client.ttl(cfg.redis_key)
        assert 0 < ttl <= cfg.redis_ttl_seconds

    def test_zero_in_window_trades_publishes_nothing_and_warns(self, caplog):
        cfg = NightCloseCaptureConfig()
        before_window = datetime(2026, 7, 2, 5, 49, 0, tzinfo=KST).timestamp()
        adapter = _FakeAdapter([_trade(ts=before_window)])
        redis_client = self._redis()

        with caplog.at_level(logging.WARNING):
            rc = run_capture(
                cfg, adapter=adapter, redis_client=redis_client, now=CAPTURE_DAY
            )

        assert rc == 0
        assert not redis_client.exists(cfg.redis_key)
        assert any("NOT publishing" in rec.message for rec in caplog.records)
        assert adapter.disconnected

    def test_started_after_window_end_is_config_error(self):
        cfg = NightCloseCaptureConfig()
        adapter = _FakeAdapter()
        redis_client = self._redis()
        late = CAPTURE_DAY + timedelta(minutes=20)  # 06:08 KST

        rc = run_capture(cfg, adapter=adapter, redis_client=redis_client, now=late)

        assert rc == EXIT_CONFIG_ERROR
        assert adapter.connected is False
        assert not redis_client.exists(cfg.redis_key)

    def test_ws_failure_returns_1_and_publishes_nothing(self):
        cfg = NightCloseCaptureConfig()

        class _BrokenAdapter(_FakeAdapter):
            def connect(self) -> None:
                raise ConnectionError("WebSocket connection timeout")

        adapter = _BrokenAdapter()
        redis_client = self._redis()

        rc = run_capture(
            cfg, adapter=adapter, redis_client=redis_client, now=CAPTURE_DAY
        )

        assert rc == 1
        assert not redis_client.exists(cfg.redis_key)
        assert adapter.disconnected  # teardown still runs


# ---------------------------------------------------------------------------
# main() entrypoint guards
# ---------------------------------------------------------------------------


class TestMainGuards:
    def test_disabled_config_short_circuits(self, monkeypatch):
        monkeypatch.setattr(
            NightCloseCaptureConfig,
            "from_yaml",
            classmethod(lambda cls, *a, **kw: cls(enabled=False)),
        )
        assert main() == 0

    def test_missing_credentials_is_config_error(self, monkeypatch):
        monkeypatch.setattr(
            NightCloseCaptureConfig,
            "from_yaml",
            classmethod(lambda cls, *a, **kw: cls()),
        )
        monkeypatch.delenv("KIS_FUTURES_APP_KEY", raising=False)
        monkeypatch.delenv("KIS_FUTURES_APP_SECRET", raising=False)
        assert main() == EXIT_CONFIG_ERROR
