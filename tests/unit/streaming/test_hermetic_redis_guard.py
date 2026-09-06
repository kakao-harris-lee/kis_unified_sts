"""Regression test for the hermetic Redis guard in tests/unit/conftest.py.

Without the autouse ``_hermetic_redis_guard`` fixture, ``RedisClient.get_client()``
falls through to ``redis.Redis(...).ping()`` against whatever Redis the host
environment provides. When that server is unreachable, redis-py 7.x's default
connection retry policy (3 retries with exponential backoff) makes the failed
acquisition take about 9.6 seconds. This test asserts both halves of the fix:
the guarded client fails fast, and the production degrade path
(``acquire_infra_clients()``) stays permissive rather than propagating.
"""

from __future__ import annotations

import time

import pytest
import redis

from shared.strategy.gates.adapter_helper import acquire_infra_clients
from shared.streaming.client import RedisClient


def test_get_client_fails_fast_without_real_redis() -> None:
    """RedisClient.get_client() must raise quickly, not hang on retry-backoff."""
    start = time.monotonic()
    with pytest.raises(redis.exceptions.ConnectionError):
        RedisClient.get_client()
    elapsed = time.monotonic() - start

    assert elapsed < 1.0, (
        f"get_client() took {elapsed:.2f}s — expected a fast hermetic failure, "
        "not the ~9.6s redis-py retry-backoff path"
    )


def test_acquire_infra_clients_degrades_permissively_and_fast() -> None:
    """acquire_infra_clients() must return (None, None) quickly on failure."""
    start = time.monotonic()
    redis_cli, event_reader = acquire_infra_clients()
    elapsed = time.monotonic() - start

    assert (redis_cli, event_reader) == (None, None)
    assert elapsed < 1.0, (
        f"acquire_infra_clients() took {elapsed:.2f}s — expected a fast "
        "permissive degrade, not the ~9.6s redis-py retry-backoff path"
    )
