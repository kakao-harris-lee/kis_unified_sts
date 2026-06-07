"""WS disconnect/reconnect counter wiring (Increment 1 observability).

These tests verify the best-effort metric helpers in the WebSocket feeds:
- stock feed (`shared.kis.stock_feed`): disconnect on `_on_close`, reconnect
  success via the `_record_ws_metric` helper.
- futures adapter (`shared.kis.websocket`): disconnect on `_on_close`.

All wiring must be best-effort: a missing/failing collector must never raise
out of the WS thread.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import shared.kis.stock_feed as stock_feed
import shared.kis.websocket as ws_mod


class TestStockFeedWsMetricHelper:
    """`_record_ws_metric` is the shared best-effort helper for stock feed."""

    def test_records_disconnect(self):
        fake = MagicMock()
        with patch(
            "services.monitoring.metrics.get_metrics_collector",
            return_value=fake,
        ):
            stock_feed._record_ws_metric("record_ws_disconnect", "stock")
        fake.record_ws_disconnect.assert_called_once_with("stock")

    def test_records_reconnect(self):
        fake = MagicMock()
        with patch(
            "services.monitoring.metrics.get_metrics_collector",
            return_value=fake,
        ):
            stock_feed._record_ws_metric("record_ws_reconnect", "stock")
        fake.record_ws_reconnect.assert_called_once_with("stock")

    def test_swallows_collector_construction_failure(self):
        with patch(
            "services.monitoring.metrics.get_metrics_collector",
            side_effect=RuntimeError("boom"),
        ):
            # must not raise — WS thread protection
            stock_feed._record_ws_metric("record_ws_disconnect", "stock")

    def test_swallows_method_failure(self):
        fake = MagicMock()
        fake.record_ws_disconnect.side_effect = RuntimeError("boom")
        with patch(
            "services.monitoring.metrics.get_metrics_collector",
            return_value=fake,
        ):
            stock_feed._record_ws_metric("record_ws_disconnect", "stock")  # no raise


class TestStockFeedOnClose:
    """`_on_close` records a stock disconnect (no new log line)."""

    def _make_feed(self):
        from shared.kis.auth import KISAuthConfig
        from shared.kis.stock_feed import KISStockPriceFeed

        config = KISAuthConfig(app_key="k", app_secret="s", is_real=False)
        return KISStockPriceFeed(config)

    def test_on_close_records_disconnect(self):
        feed = self._make_feed()
        feed._running = False  # avoid spawning a reconnect thread
        with patch.object(stock_feed, "_record_ws_metric") as rec:
            feed._on_close(None, 1000, "Normal closure")
        rec.assert_called_once_with("record_ws_disconnect", "stock")

    def test_on_close_does_not_raise_when_collector_absent(self):
        feed = self._make_feed()
        feed._running = False
        with patch(
            "services.monitoring.metrics.get_metrics_collector",
            side_effect=RuntimeError("boom"),
        ):
            feed._on_close(None, 1000, "Normal closure")  # must not raise


class TestFuturesAdapterDisconnect:
    """Futures WS adapter records a disconnect on `_on_close`."""

    def test_record_ws_disconnect_helper_calls_collector(self):
        fake = MagicMock()
        with patch(
            "services.monitoring.metrics.get_metrics_collector",
            return_value=fake,
        ):
            ws_mod._record_ws_disconnect("futures")
        fake.record_ws_disconnect.assert_called_once_with("futures")

    def test_record_ws_disconnect_helper_swallows_failure(self):
        with patch(
            "services.monitoring.metrics.get_metrics_collector",
            side_effect=RuntimeError("boom"),
        ):
            ws_mod._record_ws_disconnect("futures")  # must not raise

    def test_on_close_records_futures_disconnect(self, mock_adapter):
        with patch.object(ws_mod, "_record_ws_disconnect") as rec:
            mock_adapter._on_close(None, 1000, "Normal closure")
        rec.assert_called_once_with("futures")
        assert mock_adapter.is_connected is False

    def test_on_close_does_not_raise_when_collector_absent(self, mock_adapter):
        with patch(
            "services.monitoring.metrics.get_metrics_collector",
            side_effect=RuntimeError("boom"),
        ):
            mock_adapter._on_close(None, 1000, "Normal closure")  # must not raise
        assert mock_adapter.is_connected is False
