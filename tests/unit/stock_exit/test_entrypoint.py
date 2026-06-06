"""M4-X flag routing: off -> inert; fill-stream mapping; config loads."""

from __future__ import annotations

import asyncio

import pytest

import services.stock_exit.main as m


def test_resolve_mode_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STOCK_EXIT_DAEMON", raising=False)
    assert m._resolve_mode() == "off"


def test_resolve_mode_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_EXIT_DAEMON", "shadow")
    assert m._resolve_mode() == "shadow"


def test_fill_stream_for() -> None:
    assert m._fill_stream_for("shadow") == "order.fill.stock.shadow"
    assert m._fill_stream_for("off") == "order.fill.stock"


def test_off_mode_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_EXIT_DAEMON", "off")
    # off path returns 0 without a running redis (lazy pool, no daemon constructed).
    assert asyncio.run(m._build_and_run()) == 0


def test_stock_exit_config_loads() -> None:
    from shared.config.loader import ConfigLoader
    from shared.strategy.exit.three_stage import ThreeStageExitConfig

    raw = ConfigLoader.load("stock_exit.yaml").get("stock_exit", {})
    cfg = ThreeStageExitConfig.from_dict(raw)
    assert cfg.eod_exempt_maximize is True
    assert cfg.enable_bear_exit is False
