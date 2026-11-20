"""Global fixtures for the unit test suite."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
import redis

from shared.streaming.client import RedisClient

_EXCLUDED_TEST_FILES = frozenset(
    {
        "tests/unit/streaming/test_redis_client.py",
    }
)


def _is_excluded(request: pytest.FixtureRequest) -> bool:
    fspath = str(request.node.fspath).replace("\\", "/")
    return any(fspath.endswith(excluded) for excluded in _EXCLUDED_TEST_FILES)


@pytest.fixture
def restore_root_log_level() -> Iterator[logging.Logger]:
    """Yield the root logger and restore its level afterwards."""
    root = logging.getLogger()
    before = root.level
    try:
        yield root
    finally:
        root.setLevel(before)


@pytest.fixture(autouse=True)
def _hermetic_redis_guard(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Block real Redis connections for unit tests (see module docstring)."""
    if "live_infra" not in request.node.keywords and not _is_excluded(request):
        RedisClient._instance = None

        def _deny_real_connection(cls: type[RedisClient]) -> redis.Redis:
            raise redis.exceptions.ConnectionError(
                "hermetic unit test: real Redis disabled by tests/unit/conftest.py "
                "(_hermetic_redis_guard) — mark the test `live_infra` if it must "
                "reach a real server"
            )

        monkeypatch.setattr(
            RedisClient, "_create_client", classmethod(_deny_real_connection)
        )

        yield

        RedisClient._instance = None
    else:
        yield
