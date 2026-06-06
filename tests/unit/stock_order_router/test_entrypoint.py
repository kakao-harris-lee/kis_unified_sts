"""M4-O flag routing: off -> inert; stream-name mapping."""

from __future__ import annotations

import asyncio

import pytest

import services.stock_order_router.main as m


def test_resolve_mode_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STOCK_ORDER_ROUTER", raising=False)
    assert m._resolve_mode() == "off"


def test_resolve_mode_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_ORDER_ROUTER", "shadow")
    assert m._resolve_mode() == "shadow"


def test_stream_mapping_shadow() -> None:
    assert m._final_stream_for("shadow") == "signal.final.stock.shadow"
    assert m._fill_stream_for("shadow") == "order.fill.stock.shadow"


def test_stream_mapping_non_shadow_is_unsuffixed() -> None:
    assert m._final_stream_for("off") == "signal.final.stock"
    assert m._fill_stream_for("off") == "order.fill.stock"


def test_off_mode_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_ORDER_ROUTER", "off")
    # off path returns 0 without a running redis (lazy pool, no daemon constructed).
    assert asyncio.run(m._build_and_run()) == 0
