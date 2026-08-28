"""Backward-compat test for the shared.backtest.lookahead_guard re-export.

The implementation moved to shared.determinism (2026-07-20 import-firewall
design §3.4); the historical import path must keep resolving to the same
objects so existing backtest consumers are unaffected. Behavioural coverage
lives in tests/unit/determinism/test_lookahead_guard.py.
"""

from shared.backtest.lookahead_guard import LookaheadGuard, LookaheadGuardMode
from shared.determinism import (
    LookaheadGuard as CanonicalGuard,
)
from shared.determinism import (
    LookaheadGuardMode as CanonicalMode,
)


def test_reexport_is_canonical_object():
    """The backtest path re-exports the exact commons classes."""
    assert LookaheadGuard is CanonicalGuard
    assert LookaheadGuardMode is CanonicalMode


def test_reexport_still_functional():
    """A guard built via the legacy path still enforces look-ahead safety."""
    guard = LookaheadGuard(mode=LookaheadGuardMode.ASSERT)
    # timestamps all <= ctx -> no raise
    guard.check([1, 2, 3], [10, 20, 30], 30, "compat")
