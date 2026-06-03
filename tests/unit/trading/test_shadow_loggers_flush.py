"""Tests for TradingOrchestrator shadow-loggers periodic flush (Phase 2).

Covers:
  - ``_start_shadow_loggers_flush`` spawns the background task with correct interval
  - ``_shadow_loggers_flush_loop`` calls both loggers' flush APIs each tick
  - Flushed row counts are logged at INFO level
  - Exception in a flush call → logged as WARNING, loop continues (no crash)
  - ``_shadow_loggers_final_flush`` drains remaining buffer on stop
  - ``final_flush_on_stop: false`` → final flush skipped
  - CH client not initialised → final flush is a no-op
  - Both loggers called per tick, not just one
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers: import the three methods under test directly from the orchestrator
# module and bind them to plain objects.  This avoids standing up the full
# TradingOrchestrator (KIS credentials, Redis, etc.) while still exercising
# the real implementation.
# ---------------------------------------------------------------------------


def _import_methods() -> tuple[Any, Any, Any]:
    """Return (start_fn, loop_fn, final_fn) from TradingOrchestrator."""
    from services.trading.orchestrator import TradingOrchestrator

    return (
        TradingOrchestrator._start_shadow_loggers_flush,
        TradingOrchestrator._shadow_loggers_flush_loop,
        TradingOrchestrator._shadow_loggers_final_flush,
    )


_start_fn, _loop_fn, _final_fn = _import_methods()


class _Stub:
    """Minimal stand-in that holds only the attributes the three methods touch.

    All three orchestrator methods are bound here so that
    ``_start_shadow_loggers_flush`` can call ``self._shadow_loggers_flush_loop``
    via normal method dispatch.
    """

    from services.trading.orchestrator import TradingOrchestrator

    _shadow_loggers_flush_loop = TradingOrchestrator._shadow_loggers_flush_loop

    def __init__(self) -> None:
        self._shadow_loggers_flush_task: asyncio.Task | None = None
        self._shadow_loggers_ch_client: Any | None = None
        # final_flush_on_stop is now cached at startup by
        # _start_shadow_loggers_flush; tests that call _shadow_loggers_final_flush
        # directly should set this attribute to control the gate.
        self._shadow_loggers_final_flush_enabled: bool = True


def _stub() -> _Stub:
    return _Stub()


def _ch() -> MagicMock:
    client = MagicMock()
    client.execute = MagicMock(return_value=None)
    return client


# ---------------------------------------------------------------------------
# Tests: _start_shadow_loggers_flush
# ---------------------------------------------------------------------------


class TestStartShadowLoggersFlush:
    """Startup behaviour of _start_shadow_loggers_flush."""

    @pytest.mark.asyncio()
    async def test_spawns_task_when_ch_ok(self) -> None:
        """Successful CH client init → background task is spawned."""
        stub = _stub()
        sl_yaml = {"shadow_loggers": {"flush_interval_seconds": 5.0}}

        ch_mock = _ch()

        with (
            patch(
                "services.trading.orchestrator.ConfigLoader.load",
                return_value=sl_yaml,
            ),
            patch(
                "shared.storage.create_sync_clickhouse_client",
                return_value=ch_mock,
            ),
        ):
            await _start_fn(stub)

        assert stub._shadow_loggers_flush_task is not None
        # Tidy up the spawned task
        stub._shadow_loggers_flush_task.cancel()
        await asyncio.gather(stub._shadow_loggers_flush_task, return_exceptions=True)

    @pytest.mark.asyncio()
    async def test_no_task_when_ch_init_fails(self) -> None:
        """CH client init raises → task NOT spawned (graceful degradation)."""
        stub = _stub()
        sl_yaml = {"shadow_loggers": {"flush_interval_seconds": 60.0}}

        with (
            patch(
                "services.trading.orchestrator.ConfigLoader.load",
                return_value=sl_yaml,
            ),
            patch(
                "shared.storage.create_sync_clickhouse_client",
                side_effect=OSError("CH unreachable"),
            ),
        ):
            await _start_fn(stub)

        assert stub._shadow_loggers_flush_task is None
        assert stub._shadow_loggers_ch_client is None

    @pytest.mark.asyncio()
    async def test_missing_config_falls_back_to_defaults(self) -> None:
        """Absent config file → 60 s default used, no exception propagated."""
        from shared.exceptions import MissingConfigError

        stub = _stub()

        with (
            patch(
                "services.trading.orchestrator.ConfigLoader.load",
                side_effect=MissingConfigError("not found"),
            ),
            patch(
                "shared.storage.create_sync_clickhouse_client",
                side_effect=OSError("no CH in test env"),
            ),
        ):
            # Must complete without raising
            await _start_fn(stub)

        # Either no task (CH failed) or task spawned — both are valid outcomes.
        # The key invariant: no unhandled exception propagated to the caller.


# ---------------------------------------------------------------------------
# Tests: _shadow_loggers_flush_loop
# ---------------------------------------------------------------------------


class TestShadowLoggersFlushLoop:
    """Behaviour of the periodic _shadow_loggers_flush_loop.

    The loop catches CancelledError internally (breaks the while-True),
    so the coroutine returns normally.  Tests that want to terminate the
    loop early inject CancelledError via the asyncio.sleep mock and then
    simply await the coroutine directly (no pytest.raises needed).
    """

    @pytest.mark.asyncio()
    async def test_calls_both_loggers_each_tick(self) -> None:
        """Both rl_shadow and llm_veto flush APIs are called on the first tick."""
        stub = _stub()
        stub._shadow_loggers_ch_client = _ch()

        rl_flush = AsyncMock(return_value=3)
        veto_flush = AsyncMock(return_value=2)

        # First sleep returns normally (tick 1), second raises CancelledError
        # which the loop catches → coroutine returns normally.
        tick = 0

        async def _one_real_then_cancel(delay: float) -> None:  # noqa: ARG001
            nonlocal tick
            tick += 1
            if tick >= 2:
                raise asyncio.CancelledError()

        with (
            patch(
                "shared.strategy.rl_shadow_logger.flush_rl_shadow_predictions",
                rl_flush,
            ),
            patch(
                "shared.strategy.llm_veto_logger.flush_llm_veto_events",
                veto_flush,
            ),
            patch("asyncio.sleep", side_effect=_one_real_then_cancel),
        ):
            await _loop_fn(stub, 0.001)  # returns normally (CancelledError caught)

        rl_flush.assert_awaited_once()
        veto_flush.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_logs_nonzero_counts_at_info(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Non-zero flush counts are logged at INFO level."""
        stub = _stub()
        stub._shadow_loggers_ch_client = _ch()

        rl_flush = AsyncMock(return_value=5)
        veto_flush = AsyncMock(return_value=1)

        tick = 0

        async def _one_real_then_cancel(delay: float) -> None:  # noqa: ARG001
            nonlocal tick
            tick += 1
            if tick >= 2:
                raise asyncio.CancelledError()

        with (
            patch(
                "shared.strategy.rl_shadow_logger.flush_rl_shadow_predictions",
                rl_flush,
            ),
            patch(
                "shared.strategy.llm_veto_logger.flush_llm_veto_events",
                veto_flush,
            ),
            patch("asyncio.sleep", side_effect=_one_real_then_cancel),
            caplog.at_level(logging.INFO, logger="services.trading.orchestrator"),
        ):
            await _loop_fn(stub, 0.001)

        all_messages = " ".join(r.message for r in caplog.records)
        assert "rl_shadow=5" in all_messages
        assert "veto=1" in all_messages

    @pytest.mark.asyncio()
    async def test_exception_in_flush_logged_and_loop_continues(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Exception from rl flush → WARNING logged, loop continues to next tick."""
        stub = _stub()
        stub._shadow_loggers_ch_client = _ch()

        rl_call_count = 0

        async def _bad_rl(_client: Any) -> int:
            nonlocal rl_call_count
            rl_call_count += 1
            raise RuntimeError("CH insert failed")

        veto_flush = AsyncMock(return_value=0)

        # Three ticks: tick 1 → rl raises (caught); tick 2 → CancelledError (loop breaks).
        tick = 0

        async def _two_ticks(delay: float) -> None:  # noqa: ARG001
            nonlocal tick
            tick += 1
            if tick >= 3:
                raise asyncio.CancelledError()

        with (
            patch(
                "shared.strategy.rl_shadow_logger.flush_rl_shadow_predictions",
                side_effect=_bad_rl,
            ),
            patch(
                "shared.strategy.llm_veto_logger.flush_llm_veto_events",
                veto_flush,
            ),
            patch("asyncio.sleep", side_effect=_two_ticks),
            caplog.at_level(logging.WARNING, logger="services.trading.orchestrator"),
        ):
            await _loop_fn(stub, 0.001)

        # rl flush was called (and failed) on both ticks
        assert rl_call_count >= 1
        # The independent try/except now logs the rl-specific message
        assert any(
            "shadow_loggers rl_shadow flush error" in r.message
            for r in caplog.records
        )

    @pytest.mark.asyncio()
    async def test_independent_flushes_per_tick(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Regression: rl_shadow flush failure on tick must NOT skip llm_veto
        flush on the same tick.  The previous shared try/except would silently
        drop veto buffer rows whenever rl_shadow raised.
        """
        stub = _stub()
        stub._shadow_loggers_ch_client = _ch()

        async def _bad_rl(_client: Any) -> int:
            raise RuntimeError("rl_shadow CH dropped")

        veto_flush = AsyncMock(return_value=4)

        tick = 0

        async def _two_ticks(delay: float) -> None:  # noqa: ARG001
            nonlocal tick
            tick += 1
            if tick >= 3:
                raise asyncio.CancelledError()

        with (
            patch(
                "shared.strategy.rl_shadow_logger.flush_rl_shadow_predictions",
                side_effect=_bad_rl,
            ),
            patch(
                "shared.strategy.llm_veto_logger.flush_llm_veto_events",
                veto_flush,
            ),
            patch("asyncio.sleep", side_effect=_two_ticks),
            caplog.at_level(logging.WARNING, logger="services.trading.orchestrator"),
        ):
            await _loop_fn(stub, 0.001)

        # llm_veto MUST have been called at least once even though rl_shadow
        # raised on every tick. Without independent try/except this would be 0.
        assert veto_flush.await_count >= 1, (
            "Independence invariant violated: rl_shadow failure prevented "
            "llm_veto flush within the same tick"
        )

    @pytest.mark.asyncio()
    async def test_cancelled_error_breaks_loop_cleanly(self) -> None:
        """CancelledError from asyncio.sleep breaks the loop; coroutine returns."""
        stub = _stub()
        stub._shadow_loggers_ch_client = _ch()

        rl_flush = AsyncMock(return_value=0)
        veto_flush = AsyncMock(return_value=0)

        async def _cancel_immediately(delay: float) -> None:  # noqa: ARG001
            raise asyncio.CancelledError()

        with (
            patch(
                "shared.strategy.rl_shadow_logger.flush_rl_shadow_predictions",
                rl_flush,
            ),
            patch(
                "shared.strategy.llm_veto_logger.flush_llm_veto_events",
                veto_flush,
            ),
            patch("asyncio.sleep", side_effect=_cancel_immediately),
        ):
            # Coroutine returns normally; CancelledError is caught inside the loop.
            await _loop_fn(stub, 0.001)

        # No flush calls: cancelled before the first flush could run.
        rl_flush.assert_not_awaited()
        veto_flush.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tests: _shadow_loggers_final_flush
# ---------------------------------------------------------------------------


class TestShadowLoggersFinalFlush:
    """Shutdown drain via _shadow_loggers_final_flush."""

    @pytest.mark.asyncio()
    async def test_drains_both_loggers_on_stop(self) -> None:
        """Both loggers flushed when final_flush_on_stop=true."""
        stub = _stub()
        ch = _ch()
        stub._shadow_loggers_ch_client = ch

        sl_yaml = {"shadow_loggers": {"final_flush_on_stop": True}}
        rl_flush = AsyncMock(return_value=7)
        veto_flush = AsyncMock(return_value=3)

        with (
            patch(
                "services.trading.orchestrator.ConfigLoader.load",
                return_value=sl_yaml,
            ),
            patch(
                "shared.strategy.rl_shadow_logger.flush_rl_shadow_predictions",
                rl_flush,
            ),
            patch(
                "shared.strategy.llm_veto_logger.flush_llm_veto_events",
                veto_flush,
            ),
        ):
            await _final_fn(stub)

        rl_flush.assert_awaited_once_with(ch)
        veto_flush.assert_awaited_once_with(ch)
        # CH client nulled after final flush
        assert stub._shadow_loggers_ch_client is None

    @pytest.mark.asyncio()
    async def test_skipped_when_flag_false(self) -> None:
        """final_flush_on_stop=false → no flushing performed.

        The flag is cached at startup (in _start_shadow_loggers_flush) so
        the final-flush method reads it from the instance attribute, not
        from the YAML.  Tests set it directly.
        """
        stub = _stub()
        stub._shadow_loggers_ch_client = _ch()
        stub._shadow_loggers_final_flush_enabled = False

        rl_flush = AsyncMock(return_value=0)
        veto_flush = AsyncMock(return_value=0)

        with (
            patch(
                "shared.strategy.rl_shadow_logger.flush_rl_shadow_predictions",
                rl_flush,
            ),
            patch(
                "shared.strategy.llm_veto_logger.flush_llm_veto_events",
                veto_flush,
            ),
        ):
            await _final_fn(stub)

        rl_flush.assert_not_awaited()
        veto_flush.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_skipped_when_no_ch_client(self) -> None:
        """CH client never initialised → final flush is a no-op."""
        stub = _stub()
        stub._shadow_loggers_ch_client = None

        sl_yaml = {"shadow_loggers": {"final_flush_on_stop": True}}
        rl_flush = AsyncMock(return_value=0)
        veto_flush = AsyncMock(return_value=0)

        with (
            patch(
                "services.trading.orchestrator.ConfigLoader.load",
                return_value=sl_yaml,
            ),
            patch(
                "shared.strategy.rl_shadow_logger.flush_rl_shadow_predictions",
                rl_flush,
            ),
            patch(
                "shared.strategy.llm_veto_logger.flush_llm_veto_events",
                veto_flush,
            ),
        ):
            await _final_fn(stub)

        rl_flush.assert_not_awaited()
        veto_flush.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_exception_logged_not_raised(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Exception during final flush → WARNING logged, not re-raised.

        With independent try/except per logger, an rl_shadow failure must
        not prevent the llm_veto flush from running.  Verify the WARNING
        identifies the specific logger (rl_shadow) that failed.
        """
        stub = _stub()
        stub._shadow_loggers_ch_client = _ch()
        stub._shadow_loggers_final_flush_enabled = True

        async def _bad(_client: Any) -> int:
            raise OSError("CH dropped")

        veto_flush = AsyncMock(return_value=0)
        with (
            patch(
                "shared.strategy.rl_shadow_logger.flush_rl_shadow_predictions",
                side_effect=_bad,
            ),
            patch(
                "shared.strategy.llm_veto_logger.flush_llm_veto_events",
                veto_flush,
            ),
            caplog.at_level(logging.WARNING, logger="services.trading.orchestrator"),
        ):
            await _final_fn(stub)  # must NOT raise

        # Specific rl_shadow failure logged (not the legacy generic message)
        assert any(
            "shadow_loggers final flush rl_shadow failed" in r.message
            for r in caplog.records
        )
        # Independence invariant: llm_veto flush still ran despite rl failure
        veto_flush.assert_awaited_once()
        # CH client nulled in finally block even on exception
        assert stub._shadow_loggers_ch_client is None

    @pytest.mark.asyncio()
    async def test_logs_flush_counts_at_info(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Flush row counts appear in the final-flush INFO log."""
        stub = _stub()
        stub._shadow_loggers_ch_client = _ch()

        sl_yaml = {"shadow_loggers": {"final_flush_on_stop": True}}
        rl_flush = AsyncMock(return_value=12)
        veto_flush = AsyncMock(return_value=4)

        with (
            patch(
                "services.trading.orchestrator.ConfigLoader.load",
                return_value=sl_yaml,
            ),
            patch(
                "shared.strategy.rl_shadow_logger.flush_rl_shadow_predictions",
                rl_flush,
            ),
            patch(
                "shared.strategy.llm_veto_logger.flush_llm_veto_events",
                veto_flush,
            ),
            caplog.at_level(logging.INFO, logger="services.trading.orchestrator"),
        ):
            await _final_fn(stub)

        all_messages = " ".join(r.message for r in caplog.records)
        assert "rl_shadow=12" in all_messages
        assert "veto=4" in all_messages


# ---------------------------------------------------------------------------
# Tests: Prometheus metric publishing
# ---------------------------------------------------------------------------


class TestPrometheusMetricPublishing:
    """The loop publishes per-logger health gauges every tick.

    These tests verify the wiring between the orchestrator loop and
    ``MetricsCollector.record_shadow_logger_state``.
    """

    @pytest.mark.asyncio()
    async def test_metrics_published_each_tick(self) -> None:
        """rl_shadow and llm_veto metrics are both published each tick."""
        stub = _stub()
        stub._shadow_loggers_ch_client = _ch()
        stub._metrics = MagicMock()

        rl_flush = AsyncMock(return_value=7)
        veto_flush = AsyncMock(return_value=3)

        tick = 0

        async def _one_then_cancel(delay: float) -> None:  # noqa: ARG001
            nonlocal tick
            tick += 1
            if tick >= 2:
                raise asyncio.CancelledError()

        with (
            patch(
                "shared.strategy.rl_shadow_logger.flush_rl_shadow_predictions",
                rl_flush,
            ),
            patch(
                "shared.strategy.llm_veto_logger.flush_llm_veto_events",
                veto_flush,
            ),
            patch(
                "shared.strategy.rl_shadow_logger.pending_count",
                return_value=42,
            ),
            patch(
                "shared.strategy.rl_shadow_logger.dropped_counts",
                return_value=(1, 5),
            ),
            patch(
                "shared.strategy.llm_veto_logger.pending_count",
                return_value=8,
            ),
            patch(
                "shared.strategy.llm_veto_logger.dropped_counts",
                return_value=(0, 0),
            ),
            patch("asyncio.sleep", side_effect=_one_then_cancel),
        ):
            await _loop_fn(stub, 0.001)

        # Both loggers published exactly once on the single completed tick
        assert stub._metrics.record_shadow_logger_state.call_count == 2

        calls = {
            call.kwargs["logger"]: call.kwargs
            for call in stub._metrics.record_shadow_logger_state.call_args_list
        }
        assert "rl_shadow" in calls
        assert "llm_veto" in calls

        rl = calls["rl_shadow"]
        assert rl["pending_rows"] == 42
        assert rl["dropped_batches"] == 1
        assert rl["dropped_rows"] == 5
        assert rl["last_flush_rows"] == 7
        assert rl["last_flush_unix"] > 0

        veto = calls["llm_veto"]
        assert veto["pending_rows"] == 8
        assert veto["dropped_batches"] == 0
        assert veto["dropped_rows"] == 0
        assert veto["last_flush_rows"] == 3

    @pytest.mark.asyncio()
    async def test_metrics_published_even_on_flush_failure(self) -> None:
        """Per-tick metric publish runs even if one flush raised — operators
        can detect persistent failures via the dropped-batches counter.
        """
        stub = _stub()
        stub._shadow_loggers_ch_client = _ch()
        stub._metrics = MagicMock()

        rl_flush = AsyncMock(side_effect=RuntimeError("CH down"))
        veto_flush = AsyncMock(return_value=0)

        tick = 0

        async def _one_then_cancel(delay: float) -> None:  # noqa: ARG001
            nonlocal tick
            tick += 1
            if tick >= 2:
                raise asyncio.CancelledError()

        with (
            patch(
                "shared.strategy.rl_shadow_logger.flush_rl_shadow_predictions",
                rl_flush,
            ),
            patch(
                "shared.strategy.llm_veto_logger.flush_llm_veto_events",
                veto_flush,
            ),
            patch(
                "shared.strategy.rl_shadow_logger.pending_count",
                return_value=100,
            ),
            patch(
                "shared.strategy.rl_shadow_logger.dropped_counts",
                return_value=(3, 90),
            ),
            patch(
                "shared.strategy.llm_veto_logger.pending_count",
                return_value=0,
            ),
            patch(
                "shared.strategy.llm_veto_logger.dropped_counts",
                return_value=(0, 0),
            ),
            patch("asyncio.sleep", side_effect=_one_then_cancel),
        ):
            await _loop_fn(stub, 0.001)

        # Both loggers' state was still published (regression guard for
        # CH-down silent-failure mode).
        assert stub._metrics.record_shadow_logger_state.call_count == 2
        rl = next(
            c.kwargs
            for c in stub._metrics.record_shadow_logger_state.call_args_list
            if c.kwargs["logger"] == "rl_shadow"
        )
        # The 3-batch / 90-row drop counts surface in the gauge so the
        # ShadowLoggerBatchesDropped alert can fire.
        assert rl["dropped_batches"] == 3
        assert rl["dropped_rows"] == 90

    @pytest.mark.asyncio()
    async def test_metric_publish_failure_does_not_kill_loop(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """If MetricsCollector raises, the loop continues + logs at DEBUG."""
        stub = _stub()
        stub._shadow_loggers_ch_client = _ch()
        stub._metrics = MagicMock()
        stub._metrics.record_shadow_logger_state.side_effect = RuntimeError(
            "prometheus broken"
        )

        rl_flush = AsyncMock(return_value=0)
        veto_flush = AsyncMock(return_value=0)

        tick = 0

        async def _one_then_cancel(delay: float) -> None:  # noqa: ARG001
            nonlocal tick
            tick += 1
            if tick >= 2:
                raise asyncio.CancelledError()

        with (
            patch(
                "shared.strategy.rl_shadow_logger.flush_rl_shadow_predictions",
                rl_flush,
            ),
            patch(
                "shared.strategy.llm_veto_logger.flush_llm_veto_events",
                veto_flush,
            ),
            patch(
                "shared.strategy.rl_shadow_logger.pending_count",
                return_value=0,
            ),
            patch(
                "shared.strategy.rl_shadow_logger.dropped_counts",
                return_value=(0, 0),
            ),
            patch(
                "shared.strategy.llm_veto_logger.pending_count",
                return_value=0,
            ),
            patch(
                "shared.strategy.llm_veto_logger.dropped_counts",
                return_value=(0, 0),
            ),
            patch("asyncio.sleep", side_effect=_one_then_cancel),
            caplog.at_level(logging.DEBUG, logger="services.trading.orchestrator"),
        ):
            await _loop_fn(stub, 0.001)

        # Loop returned normally despite metric raise
        debug_msgs = [r.message for r in caplog.records if r.levelname == "DEBUG"]
        assert any("metric publish failed" in m for m in debug_msgs)
