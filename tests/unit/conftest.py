"""Global fixtures for the unit test suite.

Hermetic Redis guard
---------------------
``RedisClient._create_client`` (``shared/streaming/client.py``) calls
``redis.Redis(...).ping()`` against whatever ``REDIS_HOST``/``REDIS_PORT`` the
environment provides. When no Redis server is reachable there, redis-py 7.x's
default connection retry policy (3 retries with exponential backoff) makes
every *failed* acquisition take about 9.6 seconds. Any unit test that reaches
the real singleton without mocking it first — e.g. via
``shared/strategy/entry/setup_eval_publisher.py``'s
``publish_setup_eval() -> acquire_infra_clients() -> RedisClient.get_client()``
chain — therefore stalls for that long *per call*. A single test file making
a few dozen such calls can take minutes, making the unit suite look hung even
though CI passes (the ``test`` job runs a real Redis service container).

This autouse fixture makes ``RedisClient._create_client`` raise
``redis.exceptions.ConnectionError`` immediately for every unit test that is
not marked ``live_infra`` (tests carrying that marker intentionally exercise
real infra and are skipped unless ``KIS_RUN_LIVE_INFRA_TESTS=1`` — see the
marker registration in ``pyproject.toml``). Tests built on fakeredis, or that
already monkeypatch/patch Redis at a higher seam (``RedisClient.get_client``,
or the ``RedisClient`` class itself), are unaffected: fakeredis never calls
``_create_client``, and a test's own ``patch``/``monkeypatch.setattr`` on
``get_client`` simply wins for the scope of that call regardless of what this
fixture did to ``_create_client``. ``acquire_infra_clients()`` already
degrades permissively (returns ``(None, None)``) on any exception from
``get_client()``, so production call sites see the same failure mode they'd
see against a genuinely down Redis — just fast instead of ~9.6s slow.

``tests/unit/streaming/test_redis_client.py`` is excluded: it exercises
``_create_client``'s own control flow directly, with ``redis.Redis`` itself
mocked (so it never touches the network or the real retry policy). Patching
``_create_client`` out from under it would neuter what it is testing.
"""

from __future__ import annotations

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


@pytest.fixture(autouse=True)
def _hermetic_redis_guard(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Block real Redis connections for unit tests (see module docstring).

    The ``_instance`` reset is scoped to the SAME condition as the
    ``_create_client`` patch below — ``live_infra``-marked tests and the
    excluded ``test_redis_client.py`` file manage the singleton themselves
    (they exercise ``_create_client``'s own control flow, or intentionally
    reach real infra), so this fixture must not null it out from under them
    on either side of the yield.
    """
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
