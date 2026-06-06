"""Flag routing for the stock strategy daemon entrypoint."""

from __future__ import annotations

import services.stock_strategy.main as m


def test_resolve_mode_default_off(monkeypatch):
    monkeypatch.delenv("STOCK_STRATEGY_DAEMON", raising=False)
    assert m._resolve_mode() == "off"


def test_resolve_mode_shadow(monkeypatch):
    monkeypatch.setenv("STOCK_STRATEGY_DAEMON", "shadow")
    assert m._resolve_mode() == "shadow"
    assert m._candidate_stream_for("shadow") == "signal.candidate.stock.shadow"
    assert m._candidate_stream_for("off") == "signal.candidate.stock"


def test_live_mode_is_active_and_unsuffixed() -> None:
    assert m._is_active_mode("live") is True
    assert m._candidate_stream_for("live") == "signal.candidate.stock"
    assert m._is_active_mode("off") is False
