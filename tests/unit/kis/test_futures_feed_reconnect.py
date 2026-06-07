"""Futures WS auto-reconnect: config knobs, metric helper, supervisor backoff."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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


class TestStartUsesSupervisor:
    @pytest.mark.asyncio
    async def test_start_thread_targets_supervisor(self):
        feed = _make_feed()
        feed._adapter = MagicMock()  # connect() is a no-op mock
        feed.update_symbols(["A05603"])
        captured = {}

        class FakeThread:
            def __init__(self, *a, **kw):
                captured.update(kw)

            def start(self):
                pass  # mocked: nothing runs

        # Patch asyncio.to_thread to avoid a thread-pool / threading.Thread
        # conflict: patching threading.Thread globally (via ff.threading) also
        # breaks the executor threads used by asyncio.to_thread, causing a hang.
        with (
            patch("asyncio.to_thread", new=AsyncMock(return_value=None)),
            patch.object(ff.threading, "Thread", FakeThread),
        ):
            await feed.start()

        assert captured["target"] == feed._run_with_reconnect


class TestSupervisorNoReconnectAfterStop:
    def test_no_reconnect_when_not_running(self):
        feed = _make_feed()
        feed._symbols = ["A05603"]
        feed._running = False  # deliberate stop state
        initial_adapter = MagicMock()
        feed._adapter = initial_adapter

        with (
            patch.object(ff, "KISWebSocketAdapter") as ctor,
            patch.object(ff, "_record_ws_reconnect") as rec,
            patch.object(ff.time, "sleep") as sleep,
        ):
            feed._run_with_reconnect()

        initial_adapter.subscribe.assert_called_once()  # initial loop only
        ctor.assert_not_called()  # no fresh adapter
        rec.assert_not_called()
        sleep.assert_not_called()


class TestSupervisorBackoff:
    def test_reconnects_and_records_metric(self):
        feed = _make_feed()
        feed._symbols = ["A05603"]
        feed._running = True
        feed._reconnect_initial_delay = 1.0
        feed._reconnect_max_delay = 60.0
        feed._adapter = MagicMock()  # initial subscribe returns immediately

        sleeps: list[float] = []

        def fake_sleep(d):
            sleeps.append(d)
            if len(sleeps) >= 2:
                feed._running = False  # stop after second loop entry

        fresh = MagicMock()  # connect ok, subscribe returns immediately

        with (
            patch.object(ff, "KISWebSocketAdapter", return_value=fresh) as ctor,
            patch.object(ff, "_record_ws_reconnect") as rec,
            patch.object(ff.time, "sleep", side_effect=fake_sleep),
        ):
            feed._run_with_reconnect()

        ctor.assert_called_once_with(feed._config)
        fresh.connect.assert_called_once()
        rec.assert_called_once_with("futures")
        assert sleeps[0] == 1.0  # initial delay used

    def test_backoff_escalates_and_caps_on_connect_failure(self):
        feed = _make_feed()
        feed._symbols = ["A05603"]
        feed._running = True
        feed._reconnect_initial_delay = 1.0
        feed._reconnect_max_delay = 3.0  # low cap to prove min()
        feed._adapter = MagicMock()

        sleeps: list[float] = []

        def fake_sleep(d):
            sleeps.append(d)
            if len(sleeps) >= 4:
                feed._running = False

        failing = MagicMock()
        failing.connect.side_effect = RuntimeError("server down")

        with (
            patch.object(ff, "KISWebSocketAdapter", return_value=failing),
            patch.object(ff, "_record_ws_reconnect") as rec,
            patch.object(ff.time, "sleep", side_effect=fake_sleep),
        ):
            feed._run_with_reconnect()

        # 1.0 -> 2.0 -> min(4.0,3.0)=3.0 -> capped 3.0
        assert sleeps == [1.0, 2.0, 3.0, 3.0]
        rec.assert_not_called()  # connect never succeeded

    def test_resets_backoff_after_successful_reconnect(self):
        feed = _make_feed()
        feed._symbols = ["A05603"]
        feed._running = True
        feed._reconnect_initial_delay = 1.0
        feed._reconnect_max_delay = 60.0
        feed._adapter = MagicMock()

        sleeps: list[float] = []

        def fake_sleep(d):
            sleeps.append(d)
            if len(sleeps) >= 2:
                feed._running = False

        fresh = MagicMock()  # both reconnects succeed, subscribe returns

        with (
            patch.object(ff, "KISWebSocketAdapter", return_value=fresh),
            patch.object(ff, "_record_ws_reconnect"),
            patch.object(ff.time, "sleep", side_effect=fake_sleep),
        ):
            feed._run_with_reconnect()

        # success resets delay, so both sleeps are the initial delay
        assert sleeps == [1.0, 1.0]

    def test_backoff_escalates_when_connect_ok_but_subscribe_fails(self):
        feed = _make_feed()
        feed._symbols = ["A05603"]
        feed._running = True
        feed._reconnect_initial_delay = 1.0
        feed._reconnect_max_delay = 60.0
        feed._adapter = MagicMock()

        sleeps: list[float] = []

        def fake_sleep(d):
            sleeps.append(d)
            if len(sleeps) >= 3:
                feed._running = False

        flapping = MagicMock()  # connect ok, but subscribe raises each time
        flapping.subscribe.side_effect = RuntimeError("subscribe dropped")

        with (
            patch.object(ff, "KISWebSocketAdapter", return_value=flapping),
            patch.object(ff, "_record_ws_reconnect"),
            patch.object(ff.time, "sleep", side_effect=fake_sleep),
        ):
            feed._run_with_reconnect()

        # reset is now AFTER subscribe(); a connect-ok/subscribe-fail flap must
        # escalate, not pin at the floor: 1.0 -> 2.0 -> 4.0
        assert sleeps == [1.0, 2.0, 4.0]
