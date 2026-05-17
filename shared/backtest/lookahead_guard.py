"""
LookaheadGuard: Prevent look-ahead bias by enforcing that all time-indexed data
provided to strategies does not reference future values (timestamp > ctx.timestamp).

Modes:
- 'off': No check
- 'warn': Log warning if violation detected
- 'assert': Raise AssertionError if violation detected

Default: 'assert' for backtest/optimize, 'off' for live/paper
"""
import logging
from enum import Enum
from typing import Any, Optional

class LookaheadGuardMode(str, Enum):
    OFF = "off"
    WARN = "warn"
    ASSERT = "assert"

class LookaheadGuard:
    def __init__(self, mode: LookaheadGuardMode = LookaheadGuardMode.ASSERT):
        self.mode = mode
        self.logger = logging.getLogger("LookaheadGuard")

    def check(self, arr, timestamps, ctx_timestamp, context_info: Optional[str] = None):
        """
        arr: array-like (values)
        timestamps: array-like (same length as arr)
        ctx_timestamp: reference timestamp (datetime)
        context_info: optional string for error/warn message context
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

    def check_fingerprint(self, arr, prev_fingerprint, context_info=None):
        """
        Fallback for arrays with no explicit timestamps: check length/first/last-1 for mutation.
        prev_fingerprint: (length, first, last-1)
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
