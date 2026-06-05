"""M4-R flag routing: off -> inert (no daemon constructed); stream-name mapping."""

from __future__ import annotations

import asyncio

import pytest

import services.stock_risk_filter.main as m


def test_resolve_mode_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STOCK_RISK_FILTER", raising=False)
    assert m._resolve_mode() == "off"


def test_streams_for_shadow() -> None:
    candidate, final = m._streams_for("shadow")
    assert candidate == "signal.candidate.stock.shadow"
    assert final == "signal.final.stock.shadow"


def test_off_mode_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_RISK_FILTER", "off")
    # off path must return 0 without constructing a daemon or touching a real redis.
    rc = asyncio.run(m._build_and_run())
    assert rc == 0
