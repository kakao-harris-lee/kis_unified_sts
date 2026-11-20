"""Gating for tests that talk to real infrastructure (Redis DB 1)."""

from __future__ import annotations

import os

LIVE_INFRA_ENV = "KIS_RUN_LIVE_INFRA_TESTS"


def live_infra_enabled() -> bool:
    """Return whether tests may touch real infrastructure."""
    from shared.config import env_flag

    return env_flag(LIVE_INFRA_ENV)


def skip_reason() -> str:
    """Why a live-infra module is skipped when the opt-in is absent."""
    return (
        f"live-infra test skipped by default; set {LIVE_INFRA_ENV}=1 only on an "
        "isolated test host or after stopping paper trading (the suite and the "
        "paper runtime share Redis DB 1)"
    )


def redis_failure() -> str | None:
    """Return why Redis is unusable, or ``None`` when it answers PING."""
    try:
        from shared.streaming.client import RedisClient

        RedisClient.get_client().ping()
    except Exception as exc:  # noqa: BLE001 - any failure means "cannot measure"
        return f"{type(exc).__name__}: {exc}"
    return None


def redis_unreachable_message(failure: str) -> str:
    """The failure text for a live-infra test that cannot reach Redis."""
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
