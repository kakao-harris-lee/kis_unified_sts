"""Flag routing for the futures strategy daemon entrypoint."""

from __future__ import annotations

import pytest

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


def test_is_producing_mode():
    assert dem._is_producing_mode("shadow") is True
    assert dem._is_producing_mode("live") is True
    assert dem._is_producing_mode("off") is False
    assert dem._is_producing_mode("garbage") is False


@pytest.mark.asyncio
async def test_resolve_context_provider_off_is_inert_stub():
    cp, feed, sync = await dem._resolve_context_provider("off", object())
    assert feed is None
    assert sync is None
    assert await cp() is None  # stub emits nothing


@pytest.mark.asyncio
async def test_resolve_context_provider_live_builds_real(monkeypatch):
    called = {}

    async def _fake_builder(redis_client):
        called["redis"] = redis_client
        return ("PROVIDER", "FEED", "SYNC")

    monkeypatch.setattr(dem, "_build_context_provider", _fake_builder)
    sentinel = object()
    cp, feed, sync = await dem._resolve_context_provider("live", sentinel)
    assert called["redis"] is sentinel  # real builder invoked for live
    assert (cp, feed, sync) == ("PROVIDER", "FEED", "SYNC")


@pytest.mark.asyncio
async def test_resolve_context_provider_shadow_builds_real(monkeypatch):
    async def _fake_builder(redis_client):
        return ("PROVIDER", "FEED", "SYNC")

    monkeypatch.setattr(dem, "_build_context_provider", _fake_builder)
    cp, feed, sync = await dem._resolve_context_provider("shadow", object())
    assert cp == "PROVIDER"
