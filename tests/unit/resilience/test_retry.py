"""Tests for retry resilience utilities."""

from __future__ import annotations

import pytest

from shared.resilience import retry_on_disconnect


class CustomTransientError(Exception):
    """Custom transient exception used by retry tests."""


class RecordingSleep:
    """Async sleep stub that records requested delays."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


@pytest.mark.asyncio
async def test_retries_default_transient_exception_then_returns_result():
    """Retry matching default transient exceptions before returning success."""
    sleep = RecordingSleep()
    attempts = 0

    @retry_on_disconnect(max_retries=2, delay=0.1, backoff=2.0, sleep=sleep)
    async def flaky_call() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("redis disconnected")
        return "ok"

    result = await flaky_call()

    assert result == "ok"
    assert attempts == 3
    assert sleep.delays == [0.1, 0.2]


@pytest.mark.asyncio
async def test_non_matching_exception_propagates_without_retry_or_sleep():
    """Do not retry exceptions outside the configured transient tuple."""
    sleep = RecordingSleep()
    attempts = 0

    @retry_on_disconnect(max_retries=3, delay=0.1, sleep=sleep)
    async def failing_call() -> None:
        nonlocal attempts
        attempts += 1
        raise ValueError("bad payload")

    with pytest.raises(ValueError, match="bad payload"):
        await failing_call()

    assert attempts == 1
    assert sleep.delays == []


@pytest.mark.asyncio
async def test_non_disconnect_os_error_propagates_without_default_retry():
    """Do not retry broad OS errors unless the caller opts into them."""
    sleep = RecordingSleep()
    attempts = 0

    @retry_on_disconnect(max_retries=3, delay=0.1, sleep=sleep)
    async def failing_file_call() -> None:
        nonlocal attempts
        attempts += 1
        raise FileNotFoundError("missing token file")

    with pytest.raises(FileNotFoundError, match="missing token file"):
        await failing_file_call()

    assert attempts == 1
    assert sleep.delays == []


@pytest.mark.asyncio
async def test_raises_last_matching_exception_after_retries_exhausted():
    """Raise the final matching exception after the retry budget is exhausted."""
    sleep = RecordingSleep()
    errors = [
        TimeoutError("first timeout"),
        TimeoutError("last timeout"),
    ]

    @retry_on_disconnect(max_retries=1, delay=0.5, sleep=sleep)
    async def always_timeout() -> None:
        raise errors.pop(0)

    with pytest.raises(TimeoutError, match="last timeout"):
        await always_timeout()

    assert errors == []
    assert sleep.delays == [0.5]


@pytest.mark.asyncio
async def test_custom_exception_tuple_controls_retry_matching():
    """Retry caller-provided transient exceptions and leave other errors alone."""
    sleep = RecordingSleep()
    attempts = 0

    @retry_on_disconnect(
        max_retries=1,
        delay=0.1,
        exceptions=(CustomTransientError,),
        sleep=sleep,
    )
    async def custom_transient_call() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise CustomTransientError("temporary")
        return "recovered"

    assert await custom_transient_call() == "recovered"
    assert attempts == 2
    assert sleep.delays == [0.1]


def test_preserves_wrapped_function_metadata():
    """Preserve metadata for logging, tracing, and diagnostics."""

    @retry_on_disconnect()
    async def fetch_quote() -> str:
        """Fetch the current quote."""
        return "quote"

    assert fetch_quote.__name__ == "fetch_quote"
    assert fetch_quote.__doc__ == "Fetch the current quote."
