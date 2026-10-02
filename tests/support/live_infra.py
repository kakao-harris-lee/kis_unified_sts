"""Gating for tests that talk to real infrastructure (Redis DB 1).

Two separate questions, deliberately answered separately:

``live_infra_enabled()``
    *May* these tests touch real infrastructure? The default is no, because the
    paper runtime and the test suite share Redis DB 1 on the deploy host and
    these tests write runtime-shaped keys (``trading:{asset}:positions``).
    Opting in is explicit: ``KIS_RUN_LIVE_INFRA_TESTS=1``.

``redis_failure()``
    Given that they may, *can* they? If the answer is no, that is a broken
    environment, not a reason to go quiet. A skip here is how the CI
    ``performance`` job measured 13 of 25 benchmarks for four months while
    reporting green: the twelve Redis benchmarks skipped with the reason "Redis
    not available (start with: docker-compose up -d redis)" even though the
    Redis service container was up and healthy — the real cause was the unset
    flag, and nothing in the report distinguished the two.

The two answers are combined in ONE place, ``tests/conftest.py``, which already
owns the list of live-infra modules (``_LIVE_INFRA_TEST_PATHS``): not allowed →
skip; allowed but unreachable → the gated items FAIL at setup. Doing it there
rather than per module covers all nine modules instead of two, and keeps the
blast radius to those items — an earlier draft raised at import time in two
modules, which aborted collection for the whole session and ran zero tests.
"""

from __future__ import annotations

import os

LIVE_INFRA_ENV = "KIS_RUN_LIVE_INFRA_TESTS"


def live_infra_enabled() -> bool:
    """Return whether tests may touch real infrastructure.

    Reads the flag through ``shared.config.env_flag`` so this project has one
    truthy set rather than one per helper. Two readings of this same variable
    with different sets is not hypothetical: ``KIS_RUN_LIVE_INFRA_TESTS=on``
    used to drop ``tests/conftest.py``'s hermetic session while leaving every
    live-infra test skipped — credentials loaded, nothing gained, and no test
    noticing (#698 round-2 review).
    """
    from shared.config import env_flag

    return env_flag(LIVE_INFRA_ENV)


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


def redis_unreachable_message(failure: str) -> str:
    """The failure text for a live-infra test that cannot reach Redis.

    Says why a skip would be the wrong answer, so the next reader does not
    "fix" this by restoring one, and names the variables the client actually
    reads — a reader who sets ``REDIS_URL`` and sees no change needs to be told
    that ``RedisClient`` does not read it.
    """
    host = os.environ.get("REDIS_HOST", "localhost")
    port = os.environ.get("REDIS_PORT", "6379")
    db = os.environ.get("REDIS_DB", "1")
    return (
        f"{LIVE_INFRA_ENV} is set, so this live-infra test must run, but Redis "
        f"at {host}:{port}/{db} is unreachable — {failure}. This is a broken "
        "test environment, not a reason to skip: a skipped benchmark leaves "
        "its baseline entry unmeasured and the job green. Start Redis "
        f"(docker compose up -d redis) or unset {LIVE_INFRA_ENV}. Note that "
        "these tests read REDIS_HOST/REDIS_PORT/REDIS_DB via "
        "shared.streaming.client.RedisClient — REDIS_URL is not read on this "
        "path."
    )
