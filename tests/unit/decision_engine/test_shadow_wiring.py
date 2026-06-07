"""Flag routing for the futures strategy daemon entrypoint."""

from __future__ import annotations

import services.decision_engine.main as dem


def test_resolve_candidate_stream_default_is_live_inert(monkeypatch):
    monkeypatch.delenv("FUTURES_STRATEGY_DAEMON", raising=False)
    assert dem._resolve_mode() == "off"


def test_resolve_candidate_stream_shadow(monkeypatch):
    monkeypatch.setenv("FUTURES_STRATEGY_DAEMON", "shadow")
    assert dem._resolve_mode() == "shadow"
    assert dem._candidate_stream_for("shadow") == "signal.candidate.futures.shadow"
    assert dem._candidate_stream_for("off") == "signal.candidate.futures"
    assert dem._candidate_stream_for("live") == "signal.candidate.futures"
