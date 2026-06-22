"""Tests for configurable throttle limits in backfill module.

Covers:
- Default semaphore permits == 3 and rate limiter rps == 5 (KIS-safe defaults).
- Env override: BACKFILL_RPS=8 / BACKFILL_CONCURRENCY=4 are reflected in
  the constructed limiter/semaphore.

The module uses lazy singletons (_semaphore / _rate_limiter); we reset them
to None between tests via monkeypatch so each test gets a fresh construction.
"""

from __future__ import annotations

import asyncio
import importlib


def _get_backfill_module():
    """Import the actual module (not the __init__ re-export which is a function)."""
    return importlib.import_module("shared.collector.historical.backfill")


def _reset_singletons(mod, monkeypatch):
    """Reset module-level singletons so _get_semaphore/_get_rate_limiter reconstruct."""
    monkeypatch.setattr(mod, "_semaphore", None)
    monkeypatch.setattr(mod, "_semaphore_loop", None)
    monkeypatch.setattr(mod, "_rate_limiter", None)
    monkeypatch.setattr(mod, "_rate_limiter_loop", None)


def test_default_concurrency_and_rps(monkeypatch):
    """Without any env override the module uses concurrency=3 and rps=5."""
    mod = _get_backfill_module()
    _reset_singletons(mod, monkeypatch)

    # Remove any accidental env overrides
    monkeypatch.delenv("BACKFILL_RPS", raising=False)
    monkeypatch.delenv("BACKFILL_CONCURRENCY", raising=False)

    async def _check():
        sem = mod._get_semaphore()
        rl = mod._get_rate_limiter()
        return sem, rl

    sem, rl = asyncio.run(_check())

    assert sem._value == 3, f"Expected concurrency=3, got {sem._value}"
    actual_rps = 1.0 / rl._min_interval
    assert abs(actual_rps - 5.0) < 1e-9, f"Expected rps=5, got {actual_rps}"


def test_env_override_concurrency_and_rps(monkeypatch):
    """BACKFILL_RPS and BACKFILL_CONCURRENCY env vars are respected."""
    mod = _get_backfill_module()
    _reset_singletons(mod, monkeypatch)

    monkeypatch.setenv("BACKFILL_RPS", "8")
    monkeypatch.setenv("BACKFILL_CONCURRENCY", "4")

    async def _check():
        sem = mod._get_semaphore()
        rl = mod._get_rate_limiter()
        return sem, rl

    sem, rl = asyncio.run(_check())

    assert sem._value == 4, f"Expected concurrency=4, got {sem._value}"
    actual_rps = 1.0 / rl._min_interval
    assert abs(actual_rps - 8.0) < 1e-9, f"Expected rps=8, got {actual_rps}"
