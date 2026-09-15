"""F-5 futures monitor entrypoint flag routing."""

from __future__ import annotations

import os

import pytest

import services.futures_monitor.main as m


@pytest.fixture
def restore_state_suffix():
    """Save/restore TRADING_STATE_KEY_SUFFIX around a test.

    ``_ensure_shadow_isolation`` writes ``os.environ`` directly (the daemon's
    own process env is the contract), and ``monkeypatch.delenv(raising=False)``
    records no undo when the variable was absent — so without this the shadow
    test leaked ``TRADING_STATE_KEY_SUFFIX=shadow`` into every later test on
    the same xdist worker (observed: 4 failures in
    tests/unit/streaming/test_trading_state_publisher.py, which then read
    suffixed keys).
    """
    before = os.environ.get("TRADING_STATE_KEY_SUFFIX")
    try:
        yield
    finally:
        if before is None:
            os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)
        else:
            os.environ["TRADING_STATE_KEY_SUFFIX"] = before


def test_resolve_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("FUTURES_MONITOR_DAEMON", raising=False)
    assert m._resolve_mode() == "off"


def test_streams_for_shadow():
    assert m._streams_for("shadow") == (
        "order.fill.futures.shadow",
        "signal.final.futures.shadow",
    )


def test_streams_for_live():
    assert m._streams_for("live") == ("order.fill.futures", "signal.final.futures")


def test_shadow_forces_suffix(restore_state_suffix):
    os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)
    m._ensure_shadow_isolation("shadow")

    assert os.environ.get("TRADING_STATE_KEY_SUFFIX") == "shadow"


def test_live_clears_suffix(restore_state_suffix):
    os.environ["TRADING_STATE_KEY_SUFFIX"] = "shadow"
    m._ensure_shadow_isolation("live")

    assert os.environ.get("TRADING_STATE_KEY_SUFFIX") == ""


def test_config_loads():
    from shared.config.loader import ConfigLoader

    cfg = ConfigLoader.load("futures_monitor.yaml").get("futures_monitor", {})
    assert "telegram" in cfg
