"""Futures WS auto-reconnect: config knobs, metric helper, supervisor backoff."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import shared.kis.futures_feed as ff
from shared.kis.auth import KISAuthConfig
from shared.kis.futures_feed import KISFuturesPriceFeed


def _make_feed() -> KISFuturesPriceFeed:
    return KISFuturesPriceFeed(
        config=KISAuthConfig(app_key="k", app_secret="s", is_real=True)
    )


class TestReconnectConfigKnobs:
    def test_reads_reconnect_delays_from_config(self):
        feed = _make_feed()
        # streaming.yaml::futures_feed provides 1.0 / 60.0
        assert feed._reconnect_initial_delay == 1.0
        assert feed._reconnect_max_delay == 60.0

    def test_defaults_when_keys_absent(self):
        cfg = {
            "max_symbols": 10,
            "subscription_delay": 0.05,
            "connection_timeout": 10.0,
            "shutdown_timeout": 5.0,
        }
        with patch.object(ff, "_load_futures_feed_config", return_value=cfg):
            feed = _make_feed()
        assert feed._reconnect_initial_delay == 1.0
        assert feed._reconnect_max_delay == 60.0


class TestRecordWsReconnectHelper:
    def test_calls_collector(self):
        fake = MagicMock()
        with patch(
            "services.monitoring.metrics.get_metrics_collector",
            return_value=fake,
        ):
            ff._record_ws_reconnect("futures")
        fake.record_ws_reconnect.assert_called_once_with("futures")

    def test_swallows_collector_construction_failure(self):
        with patch(
            "services.monitoring.metrics.get_metrics_collector",
            side_effect=RuntimeError("boom"),
        ):
            ff._record_ws_reconnect("futures")  # must not raise

    def test_swallows_method_failure(self):
        fake = MagicMock()
        fake.record_ws_reconnect.side_effect = RuntimeError("boom")
        with patch(
            "services.monitoring.metrics.get_metrics_collector",
            return_value=fake,
        ):
            ff._record_ws_reconnect("futures")  # must not raise
