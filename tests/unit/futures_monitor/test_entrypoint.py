"""F-5 futures monitor entrypoint flag routing."""

from __future__ import annotations

import services.futures_monitor.main as m


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


def test_shadow_forces_suffix(monkeypatch):
    monkeypatch.delenv("TRADING_STATE_KEY_SUFFIX", raising=False)
    m._ensure_shadow_isolation("shadow")
    import os

    assert os.environ.get("TRADING_STATE_KEY_SUFFIX") == "shadow"


def test_live_clears_suffix(monkeypatch):
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "shadow")
    m._ensure_shadow_isolation("live")
    import os

    assert os.environ.get("TRADING_STATE_KEY_SUFFIX") == ""


def test_config_loads():
    from shared.config.loader import ConfigLoader

    cfg = ConfigLoader.load("futures_monitor.yaml").get("futures_monitor", {})
    assert "telegram" in cfg
