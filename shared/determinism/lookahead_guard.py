"""LookaheadGuard: enforce that time-indexed data has no look-ahead bias.

The guard verifies that every value handed to a strategy is anchored at or
before the current context timestamp (``timestamp <= ctx.timestamp``), so a
backtest cannot accidentally consume future information.

Modes:
    - ``off``: no check.
    - ``warn``: log a warning when a violation is detected.
    - ``assert``: raise :class:`AssertionError` when a violation is detected.

Default: ``assert`` for backtest/optimize, ``off`` for live/paper.

This module is a pure, dependency-light commons primitive (stdlib only). It
carries no dependency on execution, storage, streaming, LLM, or backtest
orchestration packages, so it is safe to reuse from any deterministic harness.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any


class LookaheadGuardMode(StrEnum):
    """Enforcement mode for :class:`LookaheadGuard`."""

    OFF = "off"
    WARN = "warn"
    ASSERT = "assert"


class LookaheadGuard:
    """Detect look-ahead bias in time-indexed strategy inputs.

    Attributes:
        mode: Active :class:`LookaheadGuardMode` controlling the response to a
            detected violation.
        logger: Logger used to emit warnings in ``warn`` mode.
    """

    def __init__(self, mode: LookaheadGuardMode = LookaheadGuardMode.ASSERT) -> None:
        """Initialize the guard.

        Args:
            mode: Enforcement mode. Defaults to ``assert``.
        """
        self.mode = mode
        self.logger = logging.getLogger("LookaheadGuard")

    def check(
        self,
        arr: Any,
        timestamps: Any,
        ctx_timestamp: Any,
        context_info: str | None = None,
    ) -> None:
        """Assert that no timestamp exceeds the current context timestamp.

        Args:
            arr: Array-like of values (unused for the timestamp comparison but
                kept for signature symmetry with callers).
            timestamps: Array-like of timestamps, aligned with ``arr``.
            ctx_timestamp: Reference (current) timestamp; values timestamped
                after this are considered future / look-ahead.
            context_info: Optional label appended to any warning/error message.

        Raises:
            AssertionError: If a future timestamp is found and ``mode`` is
                ``assert``.
        """
        if self.mode == LookaheadGuardMode.OFF:
            return
        if arr is None or timestamps is None or ctx_timestamp is None:
            return
        # Find any value with timestamp > ctx_timestamp
        for i, ts in enumerate(timestamps):
            if ts is not None and ts > ctx_timestamp:
                msg = f"Lookahead bias detected: value at idx={i} ts={ts} > ctx={ctx_timestamp}"
                if context_info:
                    msg += f" ({context_info})"
                if self.mode == LookaheadGuardMode.ASSERT:
                    raise AssertionError(msg)
                elif self.mode == LookaheadGuardMode.WARN:
                    self.logger.warning(msg)
                return

    def check_fingerprint(
        self,
        arr: Any,
        prev_fingerprint: Any,
        context_info: str | None = None,
    ) -> None:
        """Detect array mutation for inputs that carry no explicit timestamps.

        Compares a cheap ``(length, first, last-but-one)`` fingerprint against a
        previously captured one; a mismatch indicates the array was mutated
        after the context was established.

        Args:
            arr: Array-like of values to fingerprint.
            prev_fingerprint: Previously captured ``(length, first, last-1)``
                fingerprint tuple.
            context_info: Optional label appended to any warning/error message.

        Raises:
            AssertionError: If the fingerprint changed and ``mode`` is
                ``assert``.
        """
        if self.mode == LookaheadGuardMode.OFF:
            return
        if arr is None or prev_fingerprint is None:
            return
        length = len(arr)
        first = arr[0] if length > 0 else None
        last1 = arr[-2] if length > 1 else None
        fp = (length, first, last1)
        if fp != prev_fingerprint:
            msg = f"LookaheadGuard: array fingerprint changed (possible mutation after context): {fp} != {prev_fingerprint}"
            if context_info:
                msg += f" ({context_info})"
            if self.mode == LookaheadGuardMode.ASSERT:
                raise AssertionError(msg)
            elif self.mode == LookaheadGuardMode.WARN:
                self.logger.warning(msg)
            return
        # else OK
