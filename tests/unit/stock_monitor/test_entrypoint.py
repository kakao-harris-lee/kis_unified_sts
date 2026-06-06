"""M5a flag routing: off -> inert; stream mapping; shadow forces key-suffix; config loads."""

from __future__ import annotations

import asyncio
import os

import pytest

import services.stock_monitor.main as m


def test_resolve_mode_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STOCK_MONITOR_DAEMON", raising=False)
    assert m._resolve_mode() == "off"


def test_streams_for_shadow_and_live() -> None:
    assert m._streams_for("shadow") == (
        "order.fill.stock.shadow",
        "signal.final.stock.shadow",
    )
    assert m._streams_for("live") == ("order.fill.stock", "signal.final.stock")


def test_off_mode_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_MONITOR_DAEMON", "off")
    assert asyncio.run(m._build_and_run()) == 0


def test_shadow_forces_key_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    # setenv (not delenv) so monkeypatch TRACKS the key and removes it on
    # teardown — _ensure_shadow_isolation writes os.environ directly, which a
    # delenv-on-absent would NOT undo, leaking the suffix into later tests.
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "")
    m._ensure_shadow_isolation("shadow")
    assert os.environ["TRADING_STATE_KEY_SUFFIX"] == "shadow"


def test_live_leaves_suffix_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # Tracked via setenv so teardown restores cleanly (see note above).
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "")
    m._ensure_shadow_isolation("live")
    assert os.environ.get("TRADING_STATE_KEY_SUFFIX", "") == ""


def test_config_loads() -> None:
    from shared.config.loader import ConfigLoader

    tg = (
        ConfigLoader.load("stock_monitor.yaml")
        .get("stock_monitor", {})
        .get("telegram", {})
    )
    assert tg.get("pnl_alert_pct") == 3.0
