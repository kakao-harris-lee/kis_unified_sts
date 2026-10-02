"""Tests for ``tests/support/live_infra.py``.

The subject is the distinction the old per-module helper collapsed: "these
tests are not allowed to touch infrastructure" and "these tests are allowed to
and cannot". Both used to produce the same silent skip with the same wrong
reason ("Redis not available"), which is how the CI ``performance`` job
measured 13 of its 25 benchmarks for four months while reporting green — its
Redis service container was up the whole time and the flag was simply unset
(#768 / #796 / #679).
"""

from __future__ import annotations

import pytest
import redis

from shared.streaming.client import RedisClient
from tests.support.live_infra import (
    LIVE_INFRA_ENV,
    live_infra_enabled,
    redis_failure,
    require_redis,
    skip_reason,
)


class TestLiveInfraEnabled:
    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "Yes"])
    def test_truthy_values_opt_in(self, monkeypatch, value):
        monkeypatch.setenv(LIVE_INFRA_ENV, value)
        assert live_infra_enabled() is True

    @pytest.mark.parametrize("value", ["", "0", "false", "no", "off"])
    def test_everything_else_stays_opted_out(self, monkeypatch, value):
        monkeypatch.setenv(LIVE_INFRA_ENV, value)
        assert live_infra_enabled() is False

    def test_absent_variable_stays_opted_out(self, monkeypatch):
        monkeypatch.delenv(LIVE_INFRA_ENV, raising=False)
        assert live_infra_enabled() is False


class TestSkipReason:
    def test_it_names_the_flag_rather_than_guessing_at_redis(self):
        """The old reason asserted a fact it had not checked.

        "Redis not available (start with: docker-compose up -d redis)" was
        printed whenever the flag was unset, including on a runner whose Redis
        service container was healthy. A reader acting on it would restart a
        Redis that was already up and see no change.
        """
        reason = skip_reason()
        assert LIVE_INFRA_ENV in reason
        assert "not available" not in reason


class TestRedisFailure:
    def test_an_unreachable_redis_is_described_not_swallowed(self):
        # tests/unit/conftest.py's hermetic guard makes the real client raise.
        failure = redis_failure()
        assert failure is not None
        assert "ConnectionError" in failure

    def test_a_reachable_redis_reports_no_failure(self, monkeypatch):
        class _Pingable:
            def ping(self):
                return True

        monkeypatch.setattr(
            RedisClient, "get_client", classmethod(lambda cls: _Pingable())
        )
        assert redis_failure() is None

    def test_a_non_connection_error_is_still_a_failure(self, monkeypatch):
        """A bad REDIS_CONNECT_TIMEOUT_SECONDS raises ValueError, not a redis error.

        Catching only ``redis.ConnectionError``/``TimeoutError``/``OSError`` —
        what the old per-module helper did — would let this one propagate as a
        collection crash with no explanation, or, worse, be read as "available".
        """

        def _boom(cls):
            raise ValueError("Invalid REDIS_CONNECT_TIMEOUT_SECONDS='abc'")

        monkeypatch.setattr(RedisClient, "get_client", classmethod(_boom))
        failure = redis_failure()
        assert failure is not None
        assert "ValueError" in failure


class TestRequireRedis:
    def test_it_is_a_no_op_when_the_opt_in_is_absent(self, monkeypatch):
        """A developer with no Redis must still be able to run the whole suite."""
        monkeypatch.delenv(LIVE_INFRA_ENV, raising=False)

        def _boom(cls):
            raise redis.exceptions.ConnectionError("nothing listening")

        monkeypatch.setattr(RedisClient, "get_client", classmethod(_boom))
        require_redis("tests/performance/test_redis_load.py")  # does not raise

    def test_it_raises_when_opted_in_and_redis_is_down(self, monkeypatch):
        """The concrete input: the CI flag is on and the service container died.

        Skipping here would leave the baseline's Redis benchmarks unmeasured
        and the job green — the exact shape of the defect being fixed.
        """
        monkeypatch.setenv(LIVE_INFRA_ENV, "1")
        monkeypatch.setenv("REDIS_HOST", "localhost")
        monkeypatch.setenv("REDIS_PORT", "6379")
        monkeypatch.setenv("REDIS_DB", "1")

        def _boom(cls):
            raise redis.exceptions.ConnectionError("Connection refused")

        monkeypatch.setattr(RedisClient, "get_client", classmethod(_boom))

        with pytest.raises(RuntimeError) as excinfo:
            require_redis("tests/performance/test_redis_load.py")

        message = str(excinfo.value)
        assert "tests/performance/test_redis_load.py" in message
        assert LIVE_INFRA_ENV in message
        assert "localhost:6379/1" in message
        assert "Connection refused" in message
        # The message has to say why a skip would be wrong, or the next reader
        # "fixes" it by restoring the skip.
        assert "not a reason to skip" in message

    def test_it_returns_quietly_when_opted_in_and_redis_answers(self, monkeypatch):
        monkeypatch.setenv(LIVE_INFRA_ENV, "1")

        class _Pingable:
            def ping(self):
                return True

        monkeypatch.setattr(
            RedisClient, "get_client", classmethod(lambda cls: _Pingable())
        )
        require_redis("tests/performance/test_websocket_load.py")

    def test_the_message_points_at_the_env_vars_that_are_actually_read(
        self, monkeypatch
    ):
        """REDIS_URL is not one of them, and the workflows used to set only it.

        ``RedisClient._create_client`` reads REDIS_HOST / REDIS_PORT /
        REDIS_DB. A reader who sets REDIS_URL and sees no change needs the
        message to say so.
        """
        monkeypatch.setenv(LIVE_INFRA_ENV, "1")

        def _boom(cls):
            raise redis.exceptions.ConnectionError("Connection refused")

        monkeypatch.setattr(RedisClient, "get_client", classmethod(_boom))
        with pytest.raises(RuntimeError, match="REDIS_URL is not"):
            require_redis("m")
