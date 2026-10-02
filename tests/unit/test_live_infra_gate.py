"""Tests for the live-infra gate: ``tests/support/live_infra.py`` + the hooks
in ``tests/conftest.py`` that use it.

The subject is the distinction the old per-module helper collapsed: "these
tests are not allowed to touch infrastructure" and "these tests are allowed to
and cannot". Both used to produce the same silent skip with the same wrong
reason ("Redis not available"), which is how the CI ``performance`` job
measured 13 of its 25 benchmarks for four months while reporting green — its
Redis service container was up the whole time and the flag was simply unset
(#768 / #796 / #679).

The gate lives in ONE place. An earlier draft of this change raised at import
time inside two test modules, which aborted collection for the entire session
(``Interrupted: 2 errors during collection``, zero tests run) and left the
other seven live-infra modules unchecked.
"""

from __future__ import annotations

import pytest
import redis

import tests.conftest as root_conftest
from shared.streaming.client import RedisClient
from tests.support.live_infra import (
    LIVE_INFRA_ENV,
    live_infra_enabled,
    redis_failure,
    redis_unreachable_message,
    skip_reason,
)


class _Item:
    """The slice of a pytest item the hook actually reads."""

    def __init__(self, *markers: str) -> None:
        self.keywords = dict.fromkeys(markers, True)


@pytest.fixture
def unprobed(monkeypatch):
    """Reset the per-process Redis probe cache around a test."""
    monkeypatch.setattr(root_conftest, "_REDIS_PROBE", None)


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


class TestOneMessage:
    def test_the_skip_reason_names_the_flag_rather_than_guessing_at_redis(self):
        """The old reason asserted a fact it had not checked.

        "Redis not available (start with: docker-compose up -d redis)" was
        printed whenever the flag was unset, including on a runner whose Redis
        service container was healthy. A reader acting on it would restart a
        Redis that was already up and see no change.
        """
        reason = skip_reason()
        assert LIVE_INFRA_ENV in reason
        assert "not available" not in reason

    def test_the_conftest_skip_uses_that_same_text(self):
        """One gate, one message — no second wording to keep in sync."""
        import inspect

        source = inspect.getsource(root_conftest.pytest_collection_modifyitems)
        assert "skip_reason()" in source


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
        collection crash with no explanation, or be read as "available".
        """

        def _boom(cls):
            raise ValueError("Invalid REDIS_CONNECT_TIMEOUT_SECONDS='abc'")

        monkeypatch.setattr(RedisClient, "get_client", classmethod(_boom))
        failure = redis_failure()
        assert failure is not None
        assert "ValueError" in failure


class TestUnreachableMessage:
    def test_it_names_the_endpoint_and_why_a_skip_would_be_wrong(self, monkeypatch):
        monkeypatch.setenv("REDIS_HOST", "localhost")
        monkeypatch.setenv("REDIS_PORT", "6379")
        monkeypatch.setenv("REDIS_DB", "1")
        message = redis_unreachable_message("ConnectionError: Connection refused")

        assert LIVE_INFRA_ENV in message
        assert "localhost:6379/1" in message
        assert "Connection refused" in message
        # Without this the next reader "fixes" the failure by restoring a skip.
        assert "not a reason to skip" in message

    def test_it_points_at_the_env_vars_that_are_actually_read(self):
        """REDIS_URL is not one of them, and the workflows used to set only it.

        ``RedisClient._create_client`` reads REDIS_HOST / REDIS_PORT /
        REDIS_DB. A reader who sets REDIS_URL and sees no change needs the
        message to say so.
        """
        assert "REDIS_URL is not" in redis_unreachable_message("x")


class TestRuntestSetupGate:
    """The gate itself: fail the gated items, run everything else."""

    def test_a_live_infra_item_fails_when_redis_is_down(self, monkeypatch, unprobed):
        """The concrete input: the CI flag is on and the service container died.

        Skipping would leave the baseline's Redis benchmarks unmeasured and
        the job green — the exact shape of the defect being fixed.
        """
        monkeypatch.setenv(LIVE_INFRA_ENV, "1")

        def _boom(cls):
            raise redis.exceptions.ConnectionError("Connection refused")

        monkeypatch.setattr(RedisClient, "get_client", classmethod(_boom))

        with pytest.raises(pytest.fail.Exception) as excinfo:
            root_conftest.pytest_runtest_setup(_Item("live_infra"))
        assert "not a reason to skip" in str(excinfo.value)

    def test_an_item_that_is_not_live_infra_is_untouched(self, monkeypatch, unprobed):
        """Blast radius: a Redis outage must not fail the rest of the session."""
        monkeypatch.setenv(LIVE_INFRA_ENV, "1")

        def _boom(cls):
            raise redis.exceptions.ConnectionError("Connection refused")

        monkeypatch.setattr(RedisClient, "get_client", classmethod(_boom))
        root_conftest.pytest_runtest_setup(_Item("unit"))  # does not raise

    def test_it_is_a_no_op_when_the_opt_in_is_absent(self, monkeypatch, unprobed):
        """A developer with no Redis must still be able to run the whole suite."""
        monkeypatch.delenv(LIVE_INFRA_ENV, raising=False)
        called = []

        monkeypatch.setattr(
            root_conftest, "redis_failure", lambda: called.append(1) or "down"
        )
        root_conftest.pytest_runtest_setup(_Item("live_infra"))
        # Not even probed: the collection hook already skipped the item.
        assert called == []

    def test_it_passes_when_redis_answers(self, monkeypatch, unprobed):
        monkeypatch.setenv(LIVE_INFRA_ENV, "1")
        monkeypatch.setattr(root_conftest, "redis_failure", lambda: None)
        root_conftest.pytest_runtest_setup(_Item("live_infra"))

    def test_redis_is_probed_once_per_process_not_once_per_test(
        self, monkeypatch, unprobed
    ):
        """Twelve gated benchmarks must not pay twelve connect timeouts."""
        monkeypatch.setenv(LIVE_INFRA_ENV, "1")
        calls = []

        def _probe():
            calls.append(1)
            return None

        monkeypatch.setattr(root_conftest, "redis_failure", _probe)
        for _ in range(5):
            root_conftest.pytest_runtest_setup(_Item("live_infra"))
        assert len(calls) == 1


class TestThePerformanceModulesHaveNoSecondGate:
    """F6: two gates meant two reason strings to keep in sync."""

    @pytest.mark.parametrize(
        "module",
        [
            "tests/performance/test_redis_load.py",
            "tests/performance/test_websocket_load.py",
        ],
    )
    def test_no_module_level_skipif_or_import_time_raise(self, module):
        """Checked on the AST, not the text: the comments explain the history."""
        import ast

        tree = ast.parse((root_conftest.project_root / module).read_text())
        names = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        } | {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        assert "skipif" not in names
        assert "require_redis" not in names
        # ...and the conftest still owns them.
        assert module in root_conftest._LIVE_INFRA_TEST_PATHS
