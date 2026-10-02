"""Gating for tests that talk to real infrastructure (Redis DB 1).

Two separate questions, deliberately answered separately:

``live_infra_enabled()``
    *May* these tests touch real infrastructure? The default is no, because the
    paper runtime and the test suite share Redis DB 1 on the deploy host and
    these tests write runtime-shaped keys (``trading:{asset}:positions``).
    Opting in is explicit: ``KIS_RUN_LIVE_INFRA_TESTS=1``.

``require_redis()``
    Given that they may, *can* they? If the answer is no, that is a broken
    environment, not a reason to go quiet. A skip here is how the CI
    ``performance`` job measured 13 of 25 benchmarks for four months while
    reporting green: the twelve Redis benchmarks skipped with the reason "Redis
    not available (start with: docker-compose up -d redis)" even though the
    Redis service container was up and healthy — the real cause was the unset
    flag, and nothing in the report distinguished the two. So when the opt-in is
    explicit and Redis is nevertheless unreachable, this raises during
    collection: pytest exits non-zero, and
    ``scripts/performance/check_regression.py`` reports the round as an invalid
    measurement instead of a pass with missing benchmarks.
"""

from __future__ import annotations

import os

LIVE_INFRA_ENV = "KIS_RUN_LIVE_INFRA_TESTS"

_TRUTHY = {"1", "true", "yes"}


def live_infra_enabled() -> bool:
    """Return whether tests may touch real infrastructure."""
    return os.getenv(LIVE_INFRA_ENV, "").lower() in _TRUTHY


def skip_reason() -> str:
    """Why a live-infra module is skipped when the opt-in is absent.

    Names the flag rather than guessing at infrastructure state: the old
    "Redis not available" wording was wrong every time the flag was simply
    unset, which was every time.
    """
    return (
        f"live-infra test skipped by default; set {LIVE_INFRA_ENV}=1 only on an "
        "isolated test host or after stopping paper trading (the suite and the "
        "paper runtime share Redis DB 1)"
    )


def redis_failure() -> str | None:
    """Return why Redis is unusable, or ``None`` when it answers PING.

    Every failure is caught, not just ``redis.ConnectionError``: a bad
    ``REDIS_CONNECT_TIMEOUT_SECONDS`` raises ``ValueError`` from
    ``RedisClient._create_client`` and an unresolvable host raises ``OSError``.
    All of them mean the same thing here — Redis cannot be measured — and the
    caller turns that into a loud failure, so swallowing a class of them would
    reintroduce the silent skip this module exists to remove.
    """
    try:
        from shared.streaming.client import RedisClient

        RedisClient.get_client().ping()
    except Exception as exc:  # noqa: BLE001 - any failure means "cannot measure"
        return f"{type(exc).__name__}: {exc}"
    return None


def require_redis(module_name: str) -> None:
    """Fail collection when live infra is opted into but Redis is unreachable.

    No-op when the opt-in is absent: the module's own ``skipif`` handles that
    case, and the point of this function is the *other* case.
    """
    if not live_infra_enabled():
        return
    failure = redis_failure()
    if failure is None:
        return
    host = os.environ.get("REDIS_HOST", "localhost")
    port = os.environ.get("REDIS_PORT", "6379")
    db = os.environ.get("REDIS_DB", "1")
    raise RuntimeError(
        f"{module_name}: {LIVE_INFRA_ENV} is set, so these benchmarks must run, "
        f"but Redis at {host}:{port}/{db} is unreachable — {failure}. "
        "This is a broken measurement environment, not a reason to skip: a "
        "skipped benchmark leaves the baseline entry unmeasured and the job "
        "green. Start Redis (docker compose up -d redis) or unset "
        f"{LIVE_INFRA_ENV}. Note that these modules read REDIS_HOST/REDIS_PORT/"
        "REDIS_DB via shared.streaming.client.RedisClient — REDIS_URL is not "
        "read on this path."
    )
