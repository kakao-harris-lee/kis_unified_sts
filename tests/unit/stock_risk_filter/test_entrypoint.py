"""M4-R flag routing: off -> inert (no daemon constructed); stream-name mapping."""

from __future__ import annotations

import asyncio

import pytest

import services.stock_risk_filter.main as m


def test_resolve_mode_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STOCK_RISK_FILTER", raising=False)
    assert m._resolve_mode() == "off"


def test_resolve_mode_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_RISK_FILTER", "shadow")
    assert m._resolve_mode() == "shadow"


def test_streams_for_shadow() -> None:
    candidate, final = m._streams_for("shadow")
    assert candidate == "signal.candidate.stock.shadow"
    assert final == "signal.final.stock.shadow"


def test_streams_for_non_shadow_is_unsuffixed() -> None:
    assert m._streams_for("live") == ("signal.candidate.stock", "signal.final.stock")


def test_live_mode_is_active() -> None:
    assert m._is_active_mode("live") is True
    assert m._is_active_mode("shadow") is True
    assert m._is_active_mode("off") is False


def test_off_mode_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_RISK_FILTER", "off")
    # off path returns 0 without a running redis (lazy pool, no daemon constructed).
    rc = asyncio.run(m._build_and_run())
    assert rc == 0
