"""Async retry helpers for transient infrastructure disconnects."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

AsyncSleep = Callable[[float], Awaitable[None]]
ExceptionTypes = tuple[type[BaseException], ...]

DEFAULT_DISCONNECT_EXCEPTIONS: ExceptionTypes = (
    ConnectionError,
    TimeoutError,
)


def retry_on_disconnect(
    *,
    max_retries: int = 3,
    delay: float = 0.1,
    backoff: float = 2.0,
    exceptions: ExceptionTypes = DEFAULT_DISCONNECT_EXCEPTIONS,
    sleep: AsyncSleep | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Retry async calls that fail with transient disconnect exceptions."""
    sleeper = sleep if sleep is not None else asyncio.sleep

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            retries_remaining = max_retries
            next_delay = delay

            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions:
                    if retries_remaining <= 0:
                        raise

                    retries_remaining -= 1
                    await sleeper(next_delay)
                    next_delay *= backoff

        return wrapper

    return decorator
